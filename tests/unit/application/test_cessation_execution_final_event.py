"""Unit tests for CessationExecutionService FR43 compliance (Story 7.6).

Tests for:
- Event written before freeze flag
- final_sequence is cessation event's sequence
- Failure handling if freeze flag set fails
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.application.services.cessation_execution_service import (
    CessationExecutionError,
    CessationExecutionService,
)
from src.domain.events.event import Event
from src.domain.models.ceased_status_header import CessationDetails


def create_mock_event(
    *,
    event_id: None | str = None,
    sequence: int = 100,
    content_hash: str | None = None,
) -> Event:
    """Create a mock event for testing."""
    return Event(
        event_id=uuid4() if event_id is None else uuid4(),
        sequence=sequence,
        event_type="test.event",
        payload={},
        prev_hash="0" * 64,
        content_hash=content_hash or ("a" * 64),
        signature="sig",
        witness_id="w1",
        witness_signature="ws1",
        local_timestamp=datetime.now(timezone.utc),
        agent_id="test",
    )


@pytest.fixture
def mock_event_writer() -> AsyncMock:
    """Create mock event writer."""
    writer = AsyncMock()
    writer.write_event = AsyncMock(return_value=create_mock_event(sequence=101))
    return writer


@pytest.fixture
def mock_event_store() -> AsyncMock:
    """Create mock event store."""
    store = AsyncMock()
    store.get_latest_event = AsyncMock(
        return_value=create_mock_event(sequence=100, content_hash="b" * 64)
    )
    return store


@pytest.fixture
def mock_cessation_flag_repo() -> AsyncMock:
    """Create mock cessation flag repository."""
    repo = AsyncMock()
    repo.set_ceased = AsyncMock()
    return repo


class TestEventWrittenBeforeFreezeFlag:
    """Tests for FR43 AC5: Event written BEFORE freeze flag."""

    @pytest.mark.asyncio
    async def test_event_written_before_flag_set(
        self,
        mock_event_writer: AsyncMock,
        mock_event_store: AsyncMock,
        mock_cessation_flag_repo: AsyncMock,
    ) -> None:
        """Event should be written before freeze flag is set."""
        call_order: list[str] = []

        async def track_write_event(*args, **kwargs):
            call_order.append("write_event")
            return create_mock_event(sequence=101)

        async def track_set_ceased(*args, **kwargs):
            call_order.append("set_ceased")

        mock_event_writer.write_event = AsyncMock(side_effect=track_write_event)
        mock_cessation_flag_repo.set_ceased = AsyncMock(side_effect=track_set_ceased)

        service = CessationExecutionService(
            event_writer=mock_event_writer,
            event_store=mock_event_store,
            cessation_flag_repo=mock_cessation_flag_repo,
        )

        await service.execute_cessation(
            triggering_event_id=uuid4(),
            reason="Test cessation",
        )

        assert call_order == ["write_event", "set_ceased"]

    @pytest.mark.asyncio
    async def test_no_flag_set_if_event_write_fails(
        self,
        mock_event_writer: AsyncMock,
        mock_event_store: AsyncMock,
        mock_cessation_flag_repo: AsyncMock,
    ) -> None:
        """If event write fails, freeze flag should NOT be set."""
        mock_event_writer.write_event = AsyncMock(side_effect=Exception("Write failed"))

        service = CessationExecutionService(
            event_writer=mock_event_writer,
            event_store=mock_event_store,
            cessation_flag_repo=mock_cessation_flag_repo,
        )

        with pytest.raises(CessationExecutionError):
            await service.execute_cessation(
                triggering_event_id=uuid4(),
                reason="Test cessation",
            )

        # Flag should NOT have been set
        mock_cessation_flag_repo.set_ceased.assert_not_called()


class TestFinalSequenceIsCessationEventSequence:
    """Tests for final_sequence being the cessation event's sequence."""

    @pytest.mark.asyncio
    async def test_cessation_details_has_cessation_event_sequence(
        self,
        mock_event_writer: AsyncMock,
        mock_event_store: AsyncMock,
        mock_cessation_flag_repo: AsyncMock,
    ) -> None:
        """CessationDetails should have the cessation event's sequence."""
        cessation_event = create_mock_event(sequence=101)
        mock_event_writer.write_event = AsyncMock(return_value=cessation_event)

        captured_details: CessationDetails | None = None

        async def capture_set_ceased(details: CessationDetails) -> None:
            nonlocal captured_details
            captured_details = details

        mock_cessation_flag_repo.set_ceased = AsyncMock(side_effect=capture_set_ceased)

        service = CessationExecutionService(
            event_writer=mock_event_writer,
            event_store=mock_event_store,
            cessation_flag_repo=mock_cessation_flag_repo,
        )

        await service.execute_cessation(
            triggering_event_id=uuid4(),
            reason="Test cessation",
        )

        assert captured_details is not None
        assert captured_details.final_sequence_number == 101  # Cessation event's seq
        assert captured_details.cessation_event_id == cessation_event.event_id


class TestFreezeFlagFailureHandling:
    """Tests for FR43 AC5: Freeze flag failure handling."""

    @pytest.mark.asyncio
    async def test_raises_error_if_freeze_flag_fails(
        self,
        mock_event_writer: AsyncMock,
        mock_event_store: AsyncMock,
        mock_cessation_flag_repo: AsyncMock,
    ) -> None:
        """Should raise error if freeze flag setting fails."""
        mock_cessation_flag_repo.set_ceased = AsyncMock(
            side_effect=Exception("Flag set failed")
        )

        service = CessationExecutionService(
            event_writer=mock_event_writer,
            event_store=mock_event_store,
            cessation_flag_repo=mock_cessation_flag_repo,
        )

        with pytest.raises(CessationExecutionError):
            await service.execute_cessation(
                triggering_event_id=uuid4(),
                reason="Test cessation",
            )

    @pytest.mark.asyncio
    async def test_event_still_exists_after_freeze_flag_failure(
        self,
        mock_event_writer: AsyncMock,
        mock_event_store: AsyncMock,
        mock_cessation_flag_repo: AsyncMock,
    ) -> None:
        """Event should still exist after freeze flag failure."""
        write_called = False
        cessation_event = create_mock_event(sequence=101)

        async def track_write(*args, **kwargs):
            nonlocal write_called
            write_called = True
            return cessation_event

        mock_event_writer.write_event = AsyncMock(side_effect=track_write)
        mock_cessation_flag_repo.set_ceased = AsyncMock(
            side_effect=Exception("Flag set failed")
        )

        service = CessationExecutionService(
            event_writer=mock_event_writer,
            event_store=mock_event_store,
            cessation_flag_repo=mock_cessation_flag_repo,
        )

        with pytest.raises(CessationExecutionError):
            await service.execute_cessation(
                triggering_event_id=uuid4(),
                reason="Test cessation",
            )

        # Write was called (event exists)
        assert write_called is True


class TestEmptyEventStoreHandling:
    """Tests for empty event store handling."""

    @pytest.mark.asyncio
    async def test_raises_error_on_empty_store(
        self,
        mock_event_writer: AsyncMock,
        mock_cessation_flag_repo: AsyncMock,
    ) -> None:
        """Should raise error if event store is empty."""
        empty_store = AsyncMock()
        empty_store.get_latest_event = AsyncMock(return_value=None)

        service = CessationExecutionService(
            event_writer=mock_event_writer,
            event_store=empty_store,
            cessation_flag_repo=mock_cessation_flag_repo,
        )

        with pytest.raises(CessationExecutionError) as exc_info:
            await service.execute_cessation(
                triggering_event_id=uuid4(),
                reason="Test cessation",
            )

        assert "empty" in str(exc_info.value).lower()


class TestCessationEventPayload:
    """Tests for cessation event payload correctness."""

    @pytest.mark.asyncio
    async def test_payload_includes_is_terminal(
        self,
        mock_event_writer: AsyncMock,
        mock_event_store: AsyncMock,
        mock_cessation_flag_repo: AsyncMock,
    ) -> None:
        """Cessation event payload should include is_terminal=True."""
        captured_payload: dict | None = None

        async def capture_write(*, event_type, payload, **kwargs):
            nonlocal captured_payload
            captured_payload = payload
            return create_mock_event()

        mock_event_writer.write_event = AsyncMock(side_effect=capture_write)

        service = CessationExecutionService(
            event_writer=mock_event_writer,
            event_store=mock_event_store,
            cessation_flag_repo=mock_cessation_flag_repo,
        )

        await service.execute_cessation(
            triggering_event_id=uuid4(),
            reason="Test cessation",
        )

        assert captured_payload is not None
        assert captured_payload["is_terminal"] is True

    @pytest.mark.asyncio
    async def test_payload_includes_reason(
        self,
        mock_event_writer: AsyncMock,
        mock_event_store: AsyncMock,
        mock_cessation_flag_repo: AsyncMock,
    ) -> None:
        """Cessation event payload should include reason."""
        captured_payload: dict | None = None

        async def capture_write(*, event_type, payload, **kwargs):
            nonlocal captured_payload
            captured_payload = payload
            return create_mock_event()

        mock_event_writer.write_event = AsyncMock(side_effect=capture_write)

        service = CessationExecutionService(
            event_writer=mock_event_writer,
            event_store=mock_event_store,
            cessation_flag_repo=mock_cessation_flag_repo,
        )

        await service.execute_cessation(
            triggering_event_id=uuid4(),
            reason="Constitutional threshold exceeded",
        )

        assert captured_payload is not None
        assert "Constitutional threshold exceeded" in captured_payload["reason"]

    @pytest.mark.asyncio
    async def test_event_type_is_cessation_executed(
        self,
        mock_event_writer: AsyncMock,
        mock_event_store: AsyncMock,
        mock_cessation_flag_repo: AsyncMock,
    ) -> None:
        """Event type should be 'cessation.executed'."""
        captured_event_type: str | None = None

        async def capture_write(*, event_type, payload, **kwargs):
            nonlocal captured_event_type
            captured_event_type = event_type
            return create_mock_event()

        mock_event_writer.write_event = AsyncMock(side_effect=capture_write)

        service = CessationExecutionService(
            event_writer=mock_event_writer,
            event_store=mock_event_store,
            cessation_flag_repo=mock_cessation_flag_repo,
        )

        await service.execute_cessation(
            triggering_event_id=uuid4(),
            reason="Test",
        )

        assert captured_event_type == "cessation.executed"


class TestReturnValue:
    """Tests for execute_cessation() return value."""

    @pytest.mark.asyncio
    async def test_returns_cessation_event(
        self,
        mock_event_writer: AsyncMock,
        mock_event_store: AsyncMock,
        mock_cessation_flag_repo: AsyncMock,
    ) -> None:
        """execute_cessation() should return the cessation event."""
        cessation_event = create_mock_event(sequence=101)
        mock_event_writer.write_event = AsyncMock(return_value=cessation_event)

        service = CessationExecutionService(
            event_writer=mock_event_writer,
            event_store=mock_event_store,
            cessation_flag_repo=mock_cessation_flag_repo,
        )

        result = await service.execute_cessation(
            triggering_event_id=uuid4(),
            reason="Test",
        )

        assert result == cessation_event
