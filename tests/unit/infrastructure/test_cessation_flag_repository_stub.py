"""Unit tests for CessationFlagRepositoryStub (Story 7.4, FR41, ADR-3).

Tests the dual-channel cessation flag repository stub implementation.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest


class TestCessationFlagRepositoryStubBasics:
    """Test CessationFlagRepositoryStub basic functionality."""

    @pytest.mark.asyncio
    async def test_default_is_not_ceased(self) -> None:
        """Stub should default to not ceased."""
        from src.infrastructure.stubs import CessationFlagRepositoryStub

        stub = CessationFlagRepositoryStub()

        assert await stub.is_ceased() is False

    @pytest.mark.asyncio
    async def test_set_ceased_changes_state(self) -> None:
        """set_ceased() should change state to ceased."""
        from src.domain.models.ceased_status_header import CessationDetails
        from src.infrastructure.stubs import CessationFlagRepositoryStub

        stub = CessationFlagRepositoryStub()
        details = CessationDetails(
            ceased_at=datetime.now(timezone.utc),
            final_sequence_number=100,
            reason="Test",
            cessation_event_id=uuid4(),
        )

        await stub.set_ceased(details)

        assert await stub.is_ceased() is True

    @pytest.mark.asyncio
    async def test_clear_resets_state(self) -> None:
        """clear() should reset to not ceased."""
        from src.domain.models.ceased_status_header import CessationDetails
        from src.infrastructure.stubs import CessationFlagRepositoryStub

        stub = CessationFlagRepositoryStub()
        details = CessationDetails(
            ceased_at=datetime.now(timezone.utc),
            final_sequence_number=100,
            reason="Test",
            cessation_event_id=uuid4(),
        )

        await stub.set_ceased(details)
        stub.clear()

        assert await stub.is_ceased() is False


class TestCessationFlagRepositoryStubDualChannel:
    """Test dual-channel behavior (ADR-3)."""

    @pytest.mark.asyncio
    async def test_set_ceased_writes_to_both_channels(self) -> None:
        """set_ceased() should write to both Redis and DB."""
        from src.domain.models.ceased_status_header import CessationDetails
        from src.infrastructure.stubs import CessationFlagRepositoryStub

        stub = CessationFlagRepositoryStub()
        details = CessationDetails(
            ceased_at=datetime.now(timezone.utc),
            final_sequence_number=500,
            reason="Test",
            cessation_event_id=uuid4(),
        )

        await stub.set_ceased(details)

        assert stub.redis_flag is not None
        assert stub.db_flag is not None
        assert stub.redis_flag.final_sequence_number == 500
        assert stub.db_flag.final_sequence_number == 500

    @pytest.mark.asyncio
    async def test_is_ceased_true_if_redis_has_flag(self) -> None:
        """is_ceased() should return True if Redis has flag."""
        from src.domain.models.ceased_status_header import CessationDetails
        from src.infrastructure.stubs import CessationFlagRepositoryStub

        stub = CessationFlagRepositoryStub()
        details = CessationDetails(
            ceased_at=datetime.now(timezone.utc),
            final_sequence_number=100,
            reason="Test",
            cessation_event_id=uuid4(),
        )

        await stub.set_ceased(details)
        # Simulate DB failure but Redis has data
        stub._db_flag = None

        assert await stub.is_ceased() is True

    @pytest.mark.asyncio
    async def test_is_ceased_true_if_db_has_flag_but_redis_fails(self) -> None:
        """is_ceased() should return True if DB has flag but Redis unavailable."""
        from src.domain.models.ceased_status_header import CessationDetails
        from src.infrastructure.stubs import (
            CessationFlagRepositoryStub,
            FailureMode,
        )

        stub = CessationFlagRepositoryStub()
        details = CessationDetails(
            ceased_at=datetime.now(timezone.utc),
            final_sequence_number=100,
            reason="Test",
            cessation_event_id=uuid4(),
        )

        await stub.set_ceased(details)
        stub.set_failure_mode(FailureMode(redis_read_fails=True))

        assert await stub.is_ceased() is True

    @pytest.mark.asyncio
    async def test_is_ceased_raises_if_both_channels_fail(self) -> None:
        """is_ceased() should raise if both channels fail to read."""
        from src.infrastructure.stubs import (
            CessationFlagRepositoryStub,
            FailureMode,
        )

        stub = CessationFlagRepositoryStub()
        stub.set_failure_mode(
            FailureMode(
                redis_read_fails=True,
                db_read_fails=True,
            )
        )

        with pytest.raises(RuntimeError, match="Both channels unavailable"):
            await stub.is_ceased()


class TestCessationFlagRepositoryStubFailureModes:
    """Test failure mode simulation."""

    @pytest.mark.asyncio
    async def test_redis_write_failure_prevents_set(self) -> None:
        """Redis write failure should prevent set_ceased()."""
        from src.domain.models.ceased_status_header import CessationDetails
        from src.infrastructure.stubs import (
            CessationFlagRepositoryStub,
            FailureMode,
        )

        stub = CessationFlagRepositoryStub()
        stub.set_failure_mode(FailureMode(redis_fails=True))
        details = CessationDetails(
            ceased_at=datetime.now(timezone.utc),
            final_sequence_number=100,
            reason="Test",
            cessation_event_id=uuid4(),
        )

        with pytest.raises(RuntimeError, match="Redis write failure"):
            await stub.set_ceased(details)

        # Verify no partial write
        assert stub.redis_flag is None
        assert stub.db_flag is None

    @pytest.mark.asyncio
    async def test_db_write_failure_prevents_set(self) -> None:
        """DB write failure should prevent set_ceased()."""
        from src.domain.models.ceased_status_header import CessationDetails
        from src.infrastructure.stubs import (
            CessationFlagRepositoryStub,
            FailureMode,
        )

        stub = CessationFlagRepositoryStub()
        stub.set_failure_mode(FailureMode(db_fails=True))
        details = CessationDetails(
            ceased_at=datetime.now(timezone.utc),
            final_sequence_number=100,
            reason="Test",
            cessation_event_id=uuid4(),
        )

        with pytest.raises(RuntimeError, match="DB write failure"):
            await stub.set_ceased(details)

        # Verify no partial write (atomic semantics)
        assert stub.redis_flag is None
        assert stub.db_flag is None

    def test_clear_failure_mode_resets(self) -> None:
        """clear_failure_mode() should reset failure configuration."""
        from src.infrastructure.stubs import (
            CessationFlagRepositoryStub,
            FailureMode,
        )

        stub = CessationFlagRepositoryStub()
        stub.set_failure_mode(FailureMode(redis_fails=True, db_fails=True))
        stub.clear_failure_mode()

        # Should be back to normal (no failures)
        assert stub._failure_mode.redis_fails is False
        assert stub._failure_mode.db_fails is False


class TestCessationFlagRepositoryStubDetails:
    """Test get_cessation_details method."""

    @pytest.mark.asyncio
    async def test_get_cessation_details_returns_none_when_not_ceased(self) -> None:
        """get_cessation_details() should return None when not ceased."""
        from src.infrastructure.stubs import CessationFlagRepositoryStub

        stub = CessationFlagRepositoryStub()

        assert await stub.get_cessation_details() is None

    @pytest.mark.asyncio
    async def test_get_cessation_details_returns_details_when_ceased(self) -> None:
        """get_cessation_details() should return details when ceased."""
        from src.domain.models.ceased_status_header import CessationDetails
        from src.infrastructure.stubs import CessationFlagRepositoryStub

        stub = CessationFlagRepositoryStub()
        ceased_at = datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        event_id = uuid4()
        details = CessationDetails(
            ceased_at=ceased_at,
            final_sequence_number=999,
            reason="Test cessation",
            cessation_event_id=event_id,
        )

        await stub.set_ceased(details)

        result = await stub.get_cessation_details()
        assert result is not None
        assert result.ceased_at == ceased_at
        assert result.final_sequence_number == 999
        assert result.reason == "Test cessation"


class TestCessationFlagRepositoryStubCounters:
    """Test call counting for test verification."""

    @pytest.mark.asyncio
    async def test_set_count_tracks_calls(self) -> None:
        """set_count should track set_ceased() calls."""
        from src.domain.models.ceased_status_header import CessationDetails
        from src.infrastructure.stubs import CessationFlagRepositoryStub

        stub = CessationFlagRepositoryStub()
        details = CessationDetails(
            ceased_at=datetime.now(timezone.utc),
            final_sequence_number=100,
            reason="Test",
            cessation_event_id=uuid4(),
        )

        assert stub.set_count == 0
        await stub.set_ceased(details)
        assert stub.set_count == 1

    @pytest.mark.asyncio
    async def test_check_count_tracks_calls(self) -> None:
        """check_count should track is_ceased() calls."""
        from src.infrastructure.stubs import CessationFlagRepositoryStub

        stub = CessationFlagRepositoryStub()

        assert stub.check_count == 0
        await stub.is_ceased()
        assert stub.check_count == 1
        await stub.is_ceased()
        await stub.is_ceased()
        assert stub.check_count == 3


class TestCessationFlagRepositoryProtocolExport:
    """Test CessationFlagRepositoryProtocol export from ports."""

    def test_protocol_exported(self) -> None:
        """CessationFlagRepositoryProtocol should be exported from application.ports."""
        from src.application.ports import CessationFlagRepositoryProtocol

        assert CessationFlagRepositoryProtocol is not None
