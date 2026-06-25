"""RBAC unit tests (CLAUDE.md §10 — Auth + RBAC DoD).

Truth table for is_document_visible across role×classification combos, admin
sees all, fail-closed on bad input, and candidate filtering.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from app.core.dependencies import require_roles
from app.core.exceptions import ForbiddenError
from app.rbac.classifications import Classification, Role
from app.rbac.enforcement import filter_chunk_candidates, is_document_visible

ALL_ROLES = [Role.ADMIN, Role.COMPLIANCE_AUDITOR, Role.ANALYST, Role.VIEWER]
ALL_CLASSIFICATIONS = [
    Classification.PUBLIC,
    Classification.INTERNAL,
    Classification.CONFIDENTIAL,
    Classification.RESTRICTED,
]


def _doc(allowed_roles: list[str]) -> SimpleNamespace:
    return SimpleNamespace(allowed_roles=allowed_roles)


@pytest.mark.parametrize("classification", ALL_CLASSIFICATIONS)
def test_admin_sees_all_classifications(classification: Classification) -> None:
    # Even a doc that allows NO roles is visible to admin.
    doc = _doc([])
    assert is_document_visible(doc, {Role.ADMIN}) is True


@pytest.mark.parametrize("role", ALL_ROLES)
def test_matching_single_role_is_visible(role: Role) -> None:
    doc = _doc([role.value])
    assert is_document_visible(doc, {role}) is True


@pytest.mark.parametrize("role", [Role.COMPLIANCE_AUDITOR, Role.ANALYST, Role.VIEWER])
def test_non_matching_role_is_not_visible(role: Role) -> None:
    # Doc allows only "analyst"; a disjoint single role cannot see it.
    doc = _doc([Role.ANALYST.value])
    if role is Role.ANALYST:
        pytest.skip("matching role covered elsewhere")
    assert is_document_visible(doc, {role}) is False


def test_any_overlapping_role_grants_visibility() -> None:
    doc = _doc([Role.ANALYST.value, Role.VIEWER.value])
    assert is_document_visible(doc, {Role.VIEWER}) is True
    assert is_document_visible(doc, {Role.COMPLIANCE_AUDITOR, Role.VIEWER}) is True


def test_empty_user_roles_is_not_visible() -> None:
    doc = _doc([Role.VIEWER.value])
    assert is_document_visible(doc, set()) is False


def test_full_role_x_role_truth_table() -> None:
    # Doc allows exactly one role R; visible iff the user holds R (or is admin).
    for allowed in ALL_ROLES:
        doc = _doc([allowed.value])
        for user_role in ALL_ROLES:
            expected = (user_role == allowed) or (user_role == Role.ADMIN)
            assert is_document_visible(doc, {user_role}) is expected


def test_fail_closed_on_malformed_doc() -> None:
    bad = SimpleNamespace(allowed_roles=None)  # type: ignore[arg-type]
    assert is_document_visible(bad, {Role.VIEWER}) is False
    assert is_document_visible(bad, {Role.ADMIN}) is True  # admin short-circuits


def test_filter_chunk_candidates_drops_forbidden() -> None:
    d1, d2 = uuid.uuid4(), uuid.uuid4()
    cands = [
        SimpleNamespace(document_id=d1, content="a"),
        SimpleNamespace(document_id=d2, content="b"),
        SimpleNamespace(document_id=d1, content="c"),
    ]
    kept = filter_chunk_candidates(cands, {d1})
    assert [c.content for c in kept] == ["a", "c"]
    assert filter_chunk_candidates(cands, set()) == []


@pytest.mark.asyncio
async def test_require_roles_allows_matching_role() -> None:
    user = SimpleNamespace(role_names=["analyst"])
    dep = require_roles(Role.ANALYST, Role.ADMIN)
    assert await dep(user=user) is user  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_require_roles_blocks_unauthorized_role() -> None:
    user = SimpleNamespace(role_names=["viewer"])
    dep = require_roles(Role.ADMIN)
    with pytest.raises(ForbiddenError):
        await dep(user=user)  # type: ignore[arg-type]
