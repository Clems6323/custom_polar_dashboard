"""Root conftest — shared pytest fixtures available across all test modules.

Fixture philosophy: prefer deterministic, in-memory fixtures over mocks.
Real DuckDB in-memory databases are faster and more reliable than mocking the
storage layer.
"""

from __future__ import annotations

import pytest


@pytest.fixture(scope="session")
def sample_user_id() -> str:
    """Canonical user ID used across test fixtures."""
    return "test-user-001"
