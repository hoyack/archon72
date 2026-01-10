"""Unit tests for FreezeGuard service (Story 7.4, FR41).

Tests the FreezeGuard service that enforces freeze mechanics.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.domain.errors.ceased import SystemCeasedError


class TestFreezeGuardEnsureNotFrozen:
    """Test FreezeGuard.ensure_not_frozen() method."""

    @pytest.mark.asyncio
    async def test_does_not_raise_when_not_frozen(self) -> None:
        """ensure_not_frozen() should not raise when system not frozen."""
        from src.application.services.freeze_guard import FreezeGuard
        from src.infrastructure.stubs import FreezeCheckerStub

        freeze_checker = FreezeCheckerStub()
        guard = FreezeGuard(freeze_checker=freeze_checker)

        # Should not raise
        await guard.ensure_not_frozen()

    @pytest.mark.asyncio
    async def test_raises_system_ceased_error_when_frozen(self) -> None:
        """ensure_not_frozen() should raise SystemCeasedError when frozen."""
        from src.application.services.freeze_guard import FreezeGuard
        from src.infrastructure.stubs import FreezeCheckerStub

        freeze_checker = FreezeCheckerStub()
        freeze_checker.set_frozen(
            ceased_at=datetime.now(timezone.utc),
            final_sequence=100,
            reason="Test cessation",
        )
        guard = FreezeGuard(freeze_checker=freeze_checker)

        with pytest.raises(SystemCeasedError) as exc_info:
            await guard.ensure_not_frozen()

        assert "FR41" in str(exc_info.value)
        assert "writes frozen" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_error_includes_cessation_details(self) -> None:
        """SystemCeasedError should include cessation timestamp and sequence."""
        from src.application.services.freeze_guard import FreezeGuard
        from src.infrastructure.stubs import FreezeCheckerStub

        freeze_checker = FreezeCheckerStub()
        ceased_at = datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        freeze_checker.set_frozen(
            ceased_at=ceased_at,
            final_sequence=12345,
            reason="Test cessation",
        )
        guard = FreezeGuard(freeze_checker=freeze_checker)

        with pytest.raises(SystemCeasedError) as exc_info:
            await guard.ensure_not_frozen()

        assert exc_info.value.ceased_at == ceased_at
        assert exc_info.value.final_sequence_number == 12345


class TestFreezeGuardGetFreezeStatus:
    """Test FreezeGuard.get_freeze_status() method."""

    @pytest.mark.asyncio
    async def test_returns_none_when_not_frozen(self) -> None:
        """get_freeze_status() should return None when not frozen."""
        from src.application.services.freeze_guard import FreezeGuard
        from src.infrastructure.stubs import FreezeCheckerStub

        freeze_checker = FreezeCheckerStub()
        guard = FreezeGuard(freeze_checker=freeze_checker)

        status = await guard.get_freeze_status()

        assert status is None

    @pytest.mark.asyncio
    async def test_returns_ceased_status_header_when_frozen(self) -> None:
        """get_freeze_status() should return CeasedStatusHeader when frozen."""
        from src.application.services.freeze_guard import FreezeGuard
        from src.domain.models.ceased_status_header import SYSTEM_STATUS_CEASED
        from src.infrastructure.stubs import FreezeCheckerStub

        freeze_checker = FreezeCheckerStub()
        ceased_at = datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        freeze_checker.set_frozen(
            ceased_at=ceased_at,
            final_sequence=500,
            reason="Test cessation",
        )
        guard = FreezeGuard(freeze_checker=freeze_checker)

        status = await guard.get_freeze_status()

        assert status is not None
        assert status.system_status == SYSTEM_STATUS_CEASED
        assert status.ceased_at == ceased_at
        assert status.final_sequence_number == 500


class TestFreezeGuardIsFrozen:
    """Test FreezeGuard.is_frozen() method."""

    @pytest.mark.asyncio
    async def test_returns_false_when_not_frozen(self) -> None:
        """is_frozen() should return False when not frozen."""
        from src.application.services.freeze_guard import FreezeGuard
        from src.infrastructure.stubs import FreezeCheckerStub

        freeze_checker = FreezeCheckerStub()
        guard = FreezeGuard(freeze_checker=freeze_checker)

        assert await guard.is_frozen() is False

    @pytest.mark.asyncio
    async def test_returns_true_when_frozen(self) -> None:
        """is_frozen() should return True when frozen."""
        from src.application.services.freeze_guard import FreezeGuard
        from src.infrastructure.stubs import FreezeCheckerStub

        freeze_checker = FreezeCheckerStub()
        freeze_checker.set_frozen_simple()
        guard = FreezeGuard(freeze_checker=freeze_checker)

        assert await guard.is_frozen() is True


class TestFreezeGuardLogging:
    """Test FreezeGuard logging (CT-11 compliance)."""

    @pytest.mark.asyncio
    async def test_logs_freeze_check_failure(self) -> None:
        """Freeze check failure should be logged per CT-11."""
        from src.application.services.freeze_guard import FreezeGuard
        from src.infrastructure.stubs import FreezeCheckerStub
        from unittest.mock import patch, AsyncMock

        freeze_checker = FreezeCheckerStub()
        freeze_checker.set_frozen(
            ceased_at=datetime.now(timezone.utc),
            final_sequence=100,
            reason="Test cessation",
        )
        guard = FreezeGuard(freeze_checker=freeze_checker)

        with patch("src.application.services.freeze_guard.logger") as mock_logger:
            mock_logger.bind.return_value = mock_logger
            try:
                await guard.ensure_not_frozen()
            except SystemCeasedError:
                pass

            # Should have logged the rejection
            mock_logger.critical.assert_called()


class TestFreezeGuardForOperation:
    """Test FreezeGuard.for_operation() context manager."""

    @pytest.mark.asyncio
    async def test_allows_operation_when_not_frozen(self) -> None:
        """Operation should proceed when not frozen."""
        from src.application.services.freeze_guard import FreezeGuard
        from src.infrastructure.stubs import FreezeCheckerStub

        freeze_checker = FreezeCheckerStub()
        guard = FreezeGuard(freeze_checker=freeze_checker)

        # Should not raise
        async with guard.for_operation("test_operation"):
            pass

    @pytest.mark.asyncio
    async def test_rejects_operation_when_frozen(self) -> None:
        """Operation should be rejected with CeasedWriteAttemptError when frozen."""
        from src.application.services.freeze_guard import FreezeGuard
        from src.domain.errors.ceased import CeasedWriteAttemptError
        from src.infrastructure.stubs import FreezeCheckerStub

        freeze_checker = FreezeCheckerStub()
        freeze_checker.set_frozen_simple()
        guard = FreezeGuard(freeze_checker=freeze_checker)

        with pytest.raises(CeasedWriteAttemptError) as exc_info:
            async with guard.for_operation("write_event"):
                pass

        assert exc_info.value.operation == "write_event"
        assert "FR41" in str(exc_info.value)
