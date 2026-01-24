"""
Pytest configuration and shared fixtures for Archon 72 tests.

Testing Standards:
- All async tests use pytest.mark.asyncio (auto mode enabled in pyproject.toml)
- Use AsyncMock for async function mocking
- Unit tests go in tests/unit/
- Integration tests go in tests/integration/

Time Authority (HARDENING-3):
- Time-dependent tests must use `fake_time_authority` fixture
- Never call datetime.now() directly in tests
- Use advance() for simulating time passing
"""

import os
from datetime import datetime, timezone

# Disable crewai telemetry to prevent SystemExit during testing
# Must be set before any crewai imports occur
os.environ["CREWAI_DISABLE_TELEMETRY"] = "true"
os.environ["CREWAI_DISABLE_TRACKING"] = "true"

import pytest

from src.infrastructure.stubs.writer_lock_stub import WriterLockStub
from tests.helpers.fake_time_authority import FakeTimeAuthority


@pytest.fixture
def anyio_backend() -> str:
    """Use asyncio as the async backend."""
    return "asyncio"


@pytest.fixture
def project_version() -> str:
    """Provide the current project version for tests."""
    from src import __version__

    return __version__


# =============================================================================
# Time Authority Fixtures (HARDENING-3)
# =============================================================================


@pytest.fixture
def fake_time_authority() -> FakeTimeAuthority:
    """Provide a fresh FakeTimeAuthority for each test.

    Returns:
        A FakeTimeAuthority instance starting at 2026-01-01T00:00:00 UTC.

    Usage:
        def test_timeout(fake_time_authority):
            service = MyService(time_authority=fake_time_authority)
            fake_time_authority.advance(seconds=3600)
            assert service.is_timed_out()

    Note:
        Each test gets a fresh instance - modifications don't leak between tests.
    """
    return FakeTimeAuthority()


@pytest.fixture
def frozen_time_authority() -> FakeTimeAuthority:
    """Provide a FakeTimeAuthority frozen at a known point in time.

    Returns:
        A FakeTimeAuthority frozen at 2026-01-15T10:00:00 UTC.

    Usage:
        def test_specific_time(frozen_time_authority):
            service = MyService(time_authority=frozen_time_authority)
            assert service.get_hour() == 10

    Note:
        Use this when you need a specific, predictable time value.
        The date 2026-01-15 was chosen to match test conventions.
    """
    return FakeTimeAuthority(
        frozen_at=datetime(2026, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
    )


@pytest.fixture(autouse=True)
def _reset_writer_lock_global_state() -> None:
    """Ensure WriterLockStub shared state does not leak between tests."""
    WriterLockStub.reset_global_state()
