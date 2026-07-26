"""Shared pagination parameters (CLAUDE.md §7).

Every paginated endpoint takes ``page``/``size`` through this dependency so the
bounds are declared once and enforced at the API boundary. Unvalidated values
otherwise reach Postgres as ``OFFSET -20`` / ``LIMIT -5``, which raises and
surfaces as a 500 instead of the uniform §7 error envelope, and an unbounded
``size`` lets one request pull an entire table.
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Query

# Upper bound on rows per page. Matches the audit list, which set the precedent.
MAX_PAGE_SIZE = 200
DEFAULT_PAGE_SIZE = 20


@dataclass(frozen=True)
class Pagination:
    """Validated page/size plus the derived SQL offset."""

    page: int
    size: int

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.size


def pagination_params(
    page: int = Query(1, ge=1, description="1-indexed page number."),
    size: int = Query(
        DEFAULT_PAGE_SIZE,
        ge=1,
        le=MAX_PAGE_SIZE,
        description=f"Rows per page (1-{MAX_PAGE_SIZE}).",
    ),
) -> Pagination:
    """FastAPI dependency yielding validated pagination parameters."""
    return Pagination(page=page, size=size)
