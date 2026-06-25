"""Seed default roles + the first admin user (CLAUDE.md §6.19, Step 2).

Creates the four default roles (admin, compliance_auditor, analyst, viewer) and
a single admin account whose credentials come from the environment, never
hardcoded. Fully implemented in Step 2 once the DB models and security helpers
exist; this Step-1 stub defines the entrypoint contract.

    python -m infra.scripts.seed_admin
"""

from __future__ import annotations

import sys


def main() -> int:
    # Implemented in Step 2 (depends on db/session, models, security.hash_password).
    print(
        "seed_admin: not yet implemented — wired in Step 2 "
        "(creates default roles + first admin).",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
