"""
Pytest configuration and shared fixtures for Archon 72 tests.

Testing Standards:
- All async tests use pytest.mark.asyncio (auto mode enabled in pyproject.toml)
- Use AsyncMock for async function mocking
- Unit tests go in tests/unit/
- Integration tests go in tests/integration/
"""

import pytest


@pytest.fixture
def anyio_backend() -> str:
    """Use asyncio as the async backend."""
    return "asyncio"


@pytest.fixture
def project_version() -> str:
    """Provide the current project version for tests."""
    from src import __version__

    return __version__
