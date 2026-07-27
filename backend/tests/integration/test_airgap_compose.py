"""Air-gap overlay assertions (CLAUDE.md Golden Rule 1, §6.19, §10 Infra).

Golden Rule 1 is a *configuration* property, so it is verified by resolving the
compose files exactly as ``docker compose up`` would and asserting the result —
not by reading the overlay and trusting it.

This guards a specific, silent failure mode: compose MERGES sequence keys across
files, so ``networks: [aegis_internal]`` in the overlay ADDS the internal network
while LEAVING each service on the base file's externally-routable ``aegis_net``.
Containers then keep a default gateway and full outbound access while the overlay
still looks correct on inspection. Replacing (rather than extending) requires the
``!override`` tag; ``!reset`` only clears a key.

Skips when the docker CLI is unavailable — the daemon is NOT required, since
``docker compose config`` resolves the files locally.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parents[3]
_BASE = _REPO_ROOT / "docker-compose.yml"
_OVERLAY = _REPO_ROOT / "docker-compose.airgap.yml"

# The one service operators reach; everything else must be unreachable from off-host.
_PUBLIC_SERVICE = "frontend"
_PUBLIC_PORT = "8080"


def _resolved_config() -> dict[str, Any]:
    # Resolve to an absolute path rather than relying on PATH lookup at exec time.
    docker = shutil.which("docker")
    if docker is None:
        pytest.skip("docker CLI not available")
    if not _BASE.is_file() or not _OVERLAY.is_file():
        pytest.skip("compose files not found")

    proc = subprocess.run(  # noqa: S603
        [
            docker,
            "compose",
            "-f",
            str(_BASE),
            "-f",
            str(_OVERLAY),
            "config",
        ],
        capture_output=True,
        text=True,
        cwd=_REPO_ROOT,
        check=False,
    )
    if proc.returncode != 0:
        # Missing .env / unsupported CLI version → skip rather than fail the suite.
        pytest.skip(f"docker compose config unavailable: {proc.stderr.strip()[:200]}")
    parsed: dict[str, Any] = yaml.safe_load(proc.stdout)
    return parsed


@pytest.fixture(scope="module")
def airgap_config() -> dict[str, Any]:
    return _resolved_config()


def _services(cfg: dict[str, Any]) -> dict[str, Any]:
    services: dict[str, Any] = cfg["services"]
    assert services, "overlay resolved to no services"
    return services


def test_every_service_is_only_on_the_internal_network(airgap_config: dict[str, Any]) -> None:
    for name, svc in _services(airgap_config).items():
        nets = sorted((svc.get("networks") or {}).keys())
        assert nets == ["aegis_internal"], (
            f"{name} is attached to {nets}; anything beyond aegis_internal "
            "(notably the base file's aegis_net) restores outbound routing and "
            "breaks Golden Rule 1"
        )


def test_internal_network_is_marked_internal(airgap_config: dict[str, Any]) -> None:
    net = airgap_config.get("networks", {}).get("aegis_internal")
    assert net is not None, "aegis_internal is missing from the resolved config"
    assert (
        net.get("internal") is True
    ), "aegis_internal must be internal:true — that is what removes the gateway"


def test_only_the_frontend_publishes_a_port(airgap_config: dict[str, Any]) -> None:
    for name, svc in _services(airgap_config).items():
        published = [p.get("published") for p in (svc.get("ports") or [])]
        if name == _PUBLIC_SERVICE:
            assert published == [
                _PUBLIC_PORT
            ], f"{name} should publish exactly {_PUBLIC_PORT}, got {published}"
        else:
            assert published == [], f"{name} must not publish ports in air-gap mode: {published}"


def test_external_dns_resolution_is_pinned_off(airgap_config: dict[str, Any]) -> None:
    for name, svc in _services(airgap_config).items():
        dns = svc.get("dns")
        # An empty list does NOT survive compose normalization — it is dropped, so
        # `dns: []` would leave the host resolver in place. Require a real value.
        assert dns, f"{name} has no DNS override (an empty list is silently dropped)"


def test_every_service_is_hardened(airgap_config: dict[str, Any]) -> None:
    for name, svc in _services(airgap_config).items():
        assert "ALL" in (svc.get("cap_drop") or []), f"{name} must cap_drop ALL"
        assert "no-new-privileges:true" in (
            svc.get("security_opt") or []
        ), f"{name} must set no-new-privileges"


def test_the_full_stack_is_still_present(airgap_config: dict[str, Any]) -> None:
    """Isolation must not have been achieved by dropping services."""
    assert {"postgres", "ollama", "backend", "frontend"} <= set(_services(airgap_config))
