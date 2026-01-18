"""Unit tests for FreezeCheckerProtocol (Story 7.4, FR41).

Tests the freeze checker port interface and stub implementation.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest


class TestFreezeCheckerProtocolExport:
    """Test FreezeCheckerProtocol export from ports."""

    def test_freeze_checker_protocol_exported(self) -> None:
        """FreezeCheckerProtocol should be exported from application.ports."""
        from src.application.ports import FreezeCheckerProtocol

        assert FreezeCheckerProtocol is not None


class TestFreezeCheckerStubBasics:
    """Test FreezeCheckerStub basic functionality."""

    @pytest.mark.asyncio
    async def test_default_is_not_frozen(self) -> None:
        """Stub should default to not frozen."""
        from src.infrastructure.stubs import FreezeCheckerStub

        stub = FreezeCheckerStub()

        assert await stub.is_frozen() is False

    @pytest.mark.asyncio
    async def test_set_frozen_changes_state(self) -> None:
        """set_frozen() should change state to frozen."""
        from src.infrastructure.stubs import FreezeCheckerStub

        stub = FreezeCheckerStub()
        stub.set_frozen(
            ceased_at=datetime.now(timezone.utc),
            final_sequence=100,
            reason="Test",
        )

        assert await stub.is_frozen() is True

    @pytest.mark.asyncio
    async def test_clear_frozen_resets_state(self) -> None:
        """clear_frozen() should reset to not frozen."""
        from src.infrastructure.stubs import FreezeCheckerStub

        stub = FreezeCheckerStub()
        stub.set_frozen(
            ceased_at=datetime.now(timezone.utc),
            final_sequence=100,
            reason="Test",
        )
        stub.clear_frozen()

        assert await stub.is_frozen() is False


class TestFreezeCheckerStubDetails:
    """Test FreezeCheckerStub details methods."""

    @pytest.mark.asyncio
    async def test_get_freeze_details_returns_none_when_not_frozen(self) -> None:
        """get_freeze_details() should return None when not frozen."""
        from src.infrastructure.stubs import FreezeCheckerStub

        stub = FreezeCheckerStub()

        assert await stub.get_freeze_details() is None

    @pytest.mark.asyncio
    async def test_get_freeze_details_returns_details_when_frozen(self) -> None:
        """get_freeze_details() should return details when frozen."""
        from src.infrastructure.stubs import FreezeCheckerStub

        stub = FreezeCheckerStub()
        ceased_at = datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        stub.set_frozen(
            ceased_at=ceased_at,
            final_sequence=500,
            reason="Test cessation",
        )

        details = await stub.get_freeze_details()

        assert details is not None
        assert details.ceased_at == ceased_at
        assert details.final_sequence_number == 500
        assert details.reason == "Test cessation"

    @pytest.mark.asyncio
    async def test_get_ceased_at_returns_none_when_not_frozen(self) -> None:
        """get_ceased_at() should return None when not frozen."""
        from src.infrastructure.stubs import FreezeCheckerStub

        stub = FreezeCheckerStub()

        assert await stub.get_ceased_at() is None

    @pytest.mark.asyncio
    async def test_get_ceased_at_returns_timestamp_when_frozen(self) -> None:
        """get_ceased_at() should return timestamp when frozen."""
        from src.infrastructure.stubs import FreezeCheckerStub

        stub = FreezeCheckerStub()
        ceased_at = datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        stub.set_frozen(
            ceased_at=ceased_at,
            final_sequence=100,
            reason="Test",
        )

        assert await stub.get_ceased_at() == ceased_at

    @pytest.mark.asyncio
    async def test_get_final_sequence_returns_none_when_not_frozen(self) -> None:
        """get_final_sequence() should return None when not frozen."""
        from src.infrastructure.stubs import FreezeCheckerStub

        stub = FreezeCheckerStub()

        assert await stub.get_final_sequence() is None

    @pytest.mark.asyncio
    async def test_get_final_sequence_returns_sequence_when_frozen(self) -> None:
        """get_final_sequence() should return sequence when frozen."""
        from src.infrastructure.stubs import FreezeCheckerStub

        stub = FreezeCheckerStub()
        stub.set_frozen(
            ceased_at=datetime.now(timezone.utc),
            final_sequence=12345,
            reason="Test",
        )

        assert await stub.get_final_sequence() == 12345


class TestFreezeCheckerStubConvenience:
    """Test FreezeCheckerStub convenience methods."""

    @pytest.mark.asyncio
    async def test_set_frozen_simple_works(self) -> None:
        """set_frozen_simple() should set frozen with defaults."""
        from src.infrastructure.stubs import FreezeCheckerStub

        stub = FreezeCheckerStub()
        stub.set_frozen_simple()

        assert await stub.is_frozen() is True
        details = await stub.get_freeze_details()
        assert details is not None
        assert details.final_sequence_number == 1000
        assert details.reason == "Test cessation"

    def test_check_count_tracks_calls(self) -> None:
        """check_count should track is_frozen() calls."""
        import asyncio

        from src.infrastructure.stubs import FreezeCheckerStub

        stub = FreezeCheckerStub()

        assert stub.check_count == 0

        asyncio.get_event_loop().run_until_complete(stub.is_frozen())
        assert stub.check_count == 1

        asyncio.get_event_loop().run_until_complete(stub.is_frozen())
        asyncio.get_event_loop().run_until_complete(stub.is_frozen())
        assert stub.check_count == 3
