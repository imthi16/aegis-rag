"""Roles + document classifications (CLAUDE.md §6.3).

Pure enums + ordering. No DB access, no business logic beyond the sensitivity
ordering used by upload authority checks and policy comparisons.
"""

from __future__ import annotations

from enum import Enum


class Role(str, Enum):
    ADMIN = "admin"
    COMPLIANCE_AUDITOR = "compliance_auditor"
    ANALYST = "analyst"
    VIEWER = "viewer"


class Classification(str, Enum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


# Sensitivity ordering (low → high). Used to compare classifications, e.g. an
# uploader may only assign classifications they are authorized for.
_CLASSIFICATION_ORDER: dict[Classification, int] = {
    Classification.PUBLIC: 0,
    Classification.INTERNAL: 1,
    Classification.CONFIDENTIAL: 2,
    Classification.RESTRICTED: 3,
}


def classification_level(c: Classification) -> int:
    """Numeric sensitivity level (higher = more restricted)."""
    return _CLASSIFICATION_ORDER[c]


def all_role_values() -> set[str]:
    return {r.value for r in Role}
