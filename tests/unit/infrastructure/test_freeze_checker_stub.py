"""Unit tests for FreezeCheckerStub (Story 7.4, FR41).

Tests the freeze checker stub implementation.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest


class TestFreezeCheckerStubBasics:
    """Test FreezeCheckerStub basic functionality."""

    @pytest.mark.asyncio
    async def test_default_is_not_frozen(self) -> None:
        """Stub should default to not frozen."""
        from src.infrastructure.stubs.freeze_checker_stub import FreezeCheckerStub

        stub = FreezeCheckerStub()

        assert await stub.is_frozen() is False

    @pytest.mark.asyncio
    async def test_set_frozen_changes_state(self) -> None:
        """set_frozen() should change state to frozen."""
        from src.infrastructure.stubs.freeze_checker_stub import FreezeCheckerStub

        stub = FreezeCheckerStub()
        stub.set_frozen(
            ceased_at=datetime.now(timezone.utc),
            final_sequence=100,
            reason="Test",
        )

        assert await stub.is_frozen() is True

    @pytest.mark.asyncio
    async def test_set_frozen_simple_changes_state(self) -> None:
        """set_frozen_simple() should change state to frozen."""
        from src.infrastructure.stubs.freeze_checker_stub import FreezeCheckerStub

        stub = FreezeCheckerStub()
        stub.set_frozen_simple()

        assert await stub.is_frozen() is True

    @pytest.mark.asyncio
    async def test_clear_frozen_resets_state(self) -> None:
        """clear_frozen() should reset to not frozen."""
        from src.infrastructure.stubs.freeze_checker_stub import FreezeCheckerStub

        stub = FreezeCheckerStub()
        stub.set_frozen_simple()
        stub.clear_frozen()

        assert await stub.is_frozen() is False


class TestFreezeCheckerStubDetails:
    """Test FreezeCheckerStub detail retrieval."""

    @pytest.mark.asyncio
    async def test_get_freeze_details_returns_none_when_not_frozen(self) -> None:
        """get_freeze_details() should return None when not frozen."""
        from src.infrastructure.stubs.freeze_checker_stub import FreezeCheckerStub

        stub = FreezeCheckerStub()

        assert await stub.get_freeze_details() is None

    @pytest.mark.asyncio
    async def test_get_freeze_details_returns_details_when_frozen(self) -> None:
        """get_freeze_details() should return details when frozen."""
        from src.infrastructure.stubs.freeze_checker_stub import FreezeCheckerStub

        stub = FreezeCheckerStub()
        ceased_at = datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        stub.set_frozen(
            ceased_at=ceased_at,
            final_sequence=999,
            reason="Test cessation",
        )

        details = await stub.get_freeze_details()

        assert details is not None
        assert details.ceased_at == ceased_at
        assert details.final_sequence_number == 999
        assert details.reason == "Test cessation"

    @pytest.mark.asyncio
    async def test_get_ceased_at_returns_none_when_not_frozen(self) -> None:
        """get_ceased_at() should return None when not frozen."""
        from src.infrastructure.stubs.freeze_checker_stub import FreezeCheckerStub

        stub = FreezeCheckerStub()

        assert await stub.get_ceased_at() is None

    @pytest.mark.asyncio
    async def test_get_ceased_at_returns_timestamp_when_frozen(self) -> None:
        """get_ceased_at() should return timestamp when frozen."""
        from src.infrastructure.stubs.freeze_checker_stub import FreezeCheckerStub

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
        from src.infrastructure.stubs.freeze_checker_stub import FreezeCheckerStub

        stub = FreezeCheckerStub()

        assert await stub.get_final_sequence() is None

    @pytest.mark.asyncio
    async def test_get_final_sequence_returns_value_when_frozen(self) -> None:
        """get_final_sequence() should return value when frozen."""
        from src.infrastructure.stubs.freeze_checker_stub import FreezeCheckerStub

        stub = FreezeCheckerStub()
        stub.set_frozen(
            ceased_at=datetime.now(timezone.utc),
            final_sequence=12345,
            reason="Test",
        )

        assert await stub.get_final_sequence() == 12345


class TestFreezeCheckerStubCallCounting:
    """Test FreezeCheckerStub call counting."""

    @pytest.mark.asyncio
    async def test_check_count_starts_at_zero(self) -> None:
        """check_count should start at zero."""
        from src.infrastructure.stubs.freeze_checker_stub import FreezeCheckerStub

        stub = FreezeCheckerStub()

        assert stub.check_count == 0

    @pytest.mark.asyncio
    async def test_check_count_increments_on_is_frozen(self) -> None:
        """check_count should increment on each is_frozen() call."""
        from src.infrastructure.stubs.freeze_checker_stub import FreezeCheckerStub

        stub = FreezeCheckerStub()

        await stub.is_frozen()
        assert stub.check_count == 1

        await stub.is_frozen()
        await stub.is_frozen()
        assert stub.check_count == 3

    @pytest.mark.asyncio
    async def test_clear_frozen_resets_check_count(self) -> None:
        """clear_frozen() should reset check_count to zero."""
        from src.infrastructure.stubs.freeze_checker_stub import FreezeCheckerStub

        stub = FreezeCheckerStub()

        await stub.is_frozen()
        await stub.is_frozen()
        assert stub.check_count == 2

        stub.clear_frozen()
        assert stub.check_count == 0


class TestFreezeCheckerStubExport:
    """Test FreezeCheckerStub export from infrastructure.stubs."""

    def test_stub_exported_from_stubs_package(self) -> None:
        """FreezeCheckerStub should be exported from infrastructure.stubs."""
        from src.infrastructure.stubs import FreezeCheckerStub

        assert FreezeCheckerStub is not None
