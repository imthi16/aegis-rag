"""Shared pytest fixtures.

Step 1 keeps this minimal; DB/app fixtures are added by later steps. We ensure
tests never accidentally inherit a developer's real ``.env`` by pointing the
settings loader at a non-existent env file per test where relevant.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> None:
    """Drop the cached Settings between tests so env overrides take effect."""
    from app.core.config import get_settings

    get_settings.cache_clear()
