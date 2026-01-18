"""Unit tests for CessationExecutionService (Story 7.4, FR41; Story 7.8, FR135).

Tests the cessation execution service for permanent system termination.

Constitutional Constraints Tested:
- FR41: Freeze on new actions except record preservation
- FR135: Final deliberation SHALL be recorded before cessation (Story 7.8)
- CT-11: Silent failure destroys legitimacy -> Log ALL execution details
- CT-12: Witnessing creates accountability -> Cessation must be witnessed
- ADR-3: Dual-channel pattern -> Set flag in both Redis and DB

Acceptance Criteria Tested:
- AC1: Immediate write freeze on cessation
- AC8: Dual-channel cessation flag
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.application.services.cessation_execution_service import (
    CessationExecutionError,
    CessationExecutionService,
)
from src.domain.events.cessation_executed import CESSATION_EXECUTED_EVENT_TYPE


@pytest.fixture
def mock_event_writer() -> AsyncMock:
    """Create a mock EventWriterService."""
    writer = AsyncMock()

    # Create a proper mock event
    mock_event = MagicMock()
    mock_event.event_id = uuid4()
    mock_event.sequence = 100
    mock_event.content_hash = "c" * 64
    mock_event.event_type = CESSATION_EXECUTED_EVENT_TYPE

    writer.write_event = AsyncMock(return_value=mock_event)
    return writer


@pytest.fixture
def mock_event_store() -> AsyncMock:
    """Create a mock EventStorePort."""
    store = AsyncMock()

    # Create a head event for the cessation to reference
    head_event = MagicMock()
    head_event.sequence = 99
    head_event.content_hash = "a" * 64

    store.get_latest_event = AsyncMock(return_value=head_event)
    return store


@pytest.fixture
def mock_cessation_flag_repo() -> AsyncMock:
    """Create a mock CessationFlagRepositoryProtocol."""
    repo = AsyncMock()
    repo.set_ceased = AsyncMock()
    return repo


@pytest.fixture
def cessation_service(
    mock_event_writer: AsyncMock,
    mock_event_store: AsyncMock,
    mock_cessation_flag_repo: AsyncMock,
) -> CessationExecutionService:
    """Create CessationExecutionService with mock dependencies."""
    return CessationExecutionService(
        event_writer=mock_event_writer,
        event_store=mock_event_store,
        cessation_flag_repo=mock_cessation_flag_repo,
    )


class TestCessationExecutionServiceBasics:
    """Test basic CessationExecutionService functionality."""

    @pytest.mark.asyncio
    async def test_execute_cessation_returns_event(
        self,
        cessation_service: CessationExecutionService,
    ) -> None:
        """Test that execute_cessation returns the cessation event."""
        event = await cessation_service.execute_cessation(
            triggering_event_id=uuid4(),
            reason="Test cessation",
        )

        assert event is not None
        assert event.sequence == 100

    @pytest.mark.asyncio
    async def test_execute_cessation_writes_correct_event_type(
        self,
        cessation_service: CessationExecutionService,
        mock_event_writer: AsyncMock,
    ) -> None:
        """Test that cessation event has correct event type."""
        await cessation_service.execute_cessation(
            triggering_event_id=uuid4(),
            reason="Test cessation",
        )

        mock_event_writer.write_event.assert_called_once()
        call_kwargs = mock_event_writer.write_event.call_args.kwargs
        assert call_kwargs["event_type"] == CESSATION_EXECUTED_EVENT_TYPE

    @pytest.mark.asyncio
    async def test_execute_cessation_includes_reason_in_payload(
        self,
        cessation_service: CessationExecutionService,
        mock_event_writer: AsyncMock,
    ) -> None:
        """Test that cessation payload includes the reason."""
        await cessation_service.execute_cessation(
            triggering_event_id=uuid4(),
            reason="Constitutional crisis",
        )

        call_kwargs = mock_event_writer.write_event.call_args.kwargs
        payload = call_kwargs["payload"]
        assert payload["reason"] == "Constitutional crisis"

    @pytest.mark.asyncio
    async def test_execute_cessation_uses_provided_agent_id(
        self,
        cessation_service: CessationExecutionService,
        mock_event_writer: AsyncMock,
    ) -> None:
        """Test that cessation uses the provided agent_id."""
        await cessation_service.execute_cessation(
            triggering_event_id=uuid4(),
            reason="Test",
            agent_id="CUSTOM:AGENT",
        )

        call_kwargs = mock_event_writer.write_event.call_args.kwargs
        assert call_kwargs["agent_id"] == "CUSTOM:AGENT"

    @pytest.mark.asyncio
    async def test_execute_cessation_uses_default_agent_id(
        self,
        cessation_service: CessationExecutionService,
        mock_event_writer: AsyncMock,
    ) -> None:
        """Test that cessation uses default agent_id if not provided."""
        await cessation_service.execute_cessation(
            triggering_event_id=uuid4(),
            reason="Test",
        )

        call_kwargs = mock_event_writer.write_event.call_args.kwargs
        assert call_kwargs["agent_id"] == "SYSTEM:CESSATION"


class TestCessationExecutionServicePayload:
    """Test CessationExecutedEventPayload creation."""

    @pytest.mark.asyncio
    async def test_payload_includes_final_sequence(
        self,
        cessation_service: CessationExecutionService,
        mock_event_writer: AsyncMock,
    ) -> None:
        """Test that payload includes final_sequence_number from head event."""
        await cessation_service.execute_cessation(
            triggering_event_id=uuid4(),
            reason="Test",
        )

        call_kwargs = mock_event_writer.write_event.call_args.kwargs
        payload = call_kwargs["payload"]
        assert payload["final_sequence_number"] == 99  # From head event

    @pytest.mark.asyncio
    async def test_payload_includes_final_hash(
        self,
        cessation_service: CessationExecutionService,
        mock_event_writer: AsyncMock,
    ) -> None:
        """Test that payload includes final_hash from head event."""
        await cessation_service.execute_cessation(
            triggering_event_id=uuid4(),
            reason="Test",
        )

        call_kwargs = mock_event_writer.write_event.call_args.kwargs
        payload = call_kwargs["payload"]
        assert payload["final_hash"] == "a" * 64  # From head event

    @pytest.mark.asyncio
    async def test_payload_includes_triggering_event_id(
        self,
        cessation_service: CessationExecutionService,
        mock_event_writer: AsyncMock,
    ) -> None:
        """Test that payload includes triggering_event_id."""
        trigger_id = uuid4()

        await cessation_service.execute_cessation(
            triggering_event_id=trigger_id,
            reason="Test",
        )

        call_kwargs = mock_event_writer.write_event.call_args.kwargs
        payload = call_kwargs["payload"]
        assert payload["triggering_event_id"] == str(trigger_id)

    @pytest.mark.asyncio
    async def test_payload_is_terminal_true(
        self,
        cessation_service: CessationExecutionService,
        mock_event_writer: AsyncMock,
    ) -> None:
        """Test that payload is_terminal is always True (NFR40)."""
        await cessation_service.execute_cessation(
            triggering_event_id=uuid4(),
            reason="Test",
        )

        call_kwargs = mock_event_writer.write_event.call_args.kwargs
        payload = call_kwargs["payload"]
        assert payload["is_terminal"] is True


class TestCessationExecutionServiceDualChannel:
    """Test dual-channel cessation flag (ADR-3, AC8)."""

    @pytest.mark.asyncio
    async def test_sets_cessation_flag_after_event_write(
        self,
        cessation_service: CessationExecutionService,
        mock_cessation_flag_repo: AsyncMock,
    ) -> None:
        """Test that cessation flag is set after event is written (ADR-3)."""
        await cessation_service.execute_cessation(
            triggering_event_id=uuid4(),
            reason="Test",
        )

        mock_cessation_flag_repo.set_ceased.assert_called_once()

    @pytest.mark.asyncio
    async def test_cessation_details_include_correct_sequence(
        self,
        cessation_service: CessationExecutionService,
        mock_cessation_flag_repo: AsyncMock,
    ) -> None:
        """Test that CessationDetails has correct sequence (from written event)."""
        await cessation_service.execute_cessation(
            triggering_event_id=uuid4(),
            reason="Test",
        )

        call_args = mock_cessation_flag_repo.set_ceased.call_args
        details = call_args[0][0]
        assert details.final_sequence_number == 100  # From written event

    @pytest.mark.asyncio
    async def test_cessation_details_include_reason(
        self,
        cessation_service: CessationExecutionService,
        mock_cessation_flag_repo: AsyncMock,
    ) -> None:
        """Test that CessationDetails includes reason."""
        await cessation_service.execute_cessation(
            triggering_event_id=uuid4(),
            reason="Constitutional breach",
        )

        call_args = mock_cessation_flag_repo.set_ceased.call_args
        details = call_args[0][0]
        assert details.reason == "Constitutional breach"

    @pytest.mark.asyncio
    async def test_cessation_details_include_event_id(
        self,
        cessation_service: CessationExecutionService,
        mock_cessation_flag_repo: AsyncMock,
        mock_event_writer: AsyncMock,
    ) -> None:
        """Test that CessationDetails includes cessation event_id."""
        await cessation_service.execute_cessation(
            triggering_event_id=uuid4(),
            reason="Test",
        )

        call_args = mock_cessation_flag_repo.set_ceased.call_args
        details = call_args[0][0]
        expected_event_id = mock_event_writer.write_event.return_value.event_id
        assert details.cessation_event_id == expected_event_id


class TestCessationExecutionServiceErrorHandling:
    """Test error handling during cessation execution."""

    @pytest.mark.asyncio
    async def test_raises_error_on_empty_store(
        self,
        mock_event_writer: AsyncMock,
        mock_cessation_flag_repo: AsyncMock,
    ) -> None:
        """Test that execution fails if event store is empty."""
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
                reason="Test",
            )

        assert "empty" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_raises_error_on_event_write_failure(
        self,
        mock_event_store: AsyncMock,
        mock_cessation_flag_repo: AsyncMock,
    ) -> None:
        """Test that execution fails if event write fails."""
        failing_writer = AsyncMock()
        failing_writer.write_event = AsyncMock(side_effect=Exception("Write failed"))

        service = CessationExecutionService(
            event_writer=failing_writer,
            event_store=mock_event_store,
            cessation_flag_repo=mock_cessation_flag_repo,
        )

        with pytest.raises(CessationExecutionError) as exc_info:
            await service.execute_cessation(
                triggering_event_id=uuid4(),
                reason="Test",
            )

        assert "Write failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_raises_error_on_flag_set_failure(
        self,
        mock_event_writer: AsyncMock,
        mock_event_store: AsyncMock,
    ) -> None:
        """Test that execution fails if flag setting fails."""
        failing_repo = AsyncMock()
        failing_repo.set_ceased = AsyncMock(
            side_effect=Exception("Redis connection lost")
        )

        service = CessationExecutionService(
            event_writer=mock_event_writer,
            event_store=mock_event_store,
            cessation_flag_repo=failing_repo,
        )

        with pytest.raises(CessationExecutionError) as exc_info:
            await service.execute_cessation(
                triggering_event_id=uuid4(),
                reason="Test",
            )

        assert "Redis connection lost" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_does_not_set_flag_if_event_write_fails(
        self,
        mock_event_store: AsyncMock,
        mock_cessation_flag_repo: AsyncMock,
    ) -> None:
        """Test that flag is NOT set if event write fails first."""
        failing_writer = AsyncMock()
        failing_writer.write_event = AsyncMock(side_effect=Exception("Write failed"))

        service = CessationExecutionService(
            event_writer=failing_writer,
            event_store=mock_event_store,
            cessation_flag_repo=mock_cessation_flag_repo,
        )

        with pytest.raises(CessationExecutionError):
            await service.execute_cessation(
                triggering_event_id=uuid4(),
                reason="Test",
            )

        # Flag should NOT have been set
        mock_cessation_flag_repo.set_ceased.assert_not_called()


class TestCessationExecutionServiceOrdering:
    """Test execution ordering and atomicity."""

    @pytest.mark.asyncio
    async def test_head_fetch_before_event_write(
        self,
        cessation_service: CessationExecutionService,
        mock_event_store: AsyncMock,
        mock_event_writer: AsyncMock,
    ) -> None:
        """Test that head event is fetched before writing."""
        call_order = []

        async def track_get_latest():
            call_order.append("get_latest")
            head_event = MagicMock()
            head_event.sequence = 99
            head_event.content_hash = "a" * 64
            return head_event

        async def track_write_event(**kwargs):
            call_order.append("write_event")
            mock_event = MagicMock()
            mock_event.event_id = uuid4()
            mock_event.sequence = 100
            mock_event.content_hash = "c" * 64
            return mock_event

        mock_event_store.get_latest_event = track_get_latest
        mock_event_writer.write_event = track_write_event

        await cessation_service.execute_cessation(
            triggering_event_id=uuid4(),
            reason="Test",
        )

        assert call_order == ["get_latest", "write_event"]

    @pytest.mark.asyncio
    async def test_event_write_before_flag_set(
        self,
        cessation_service: CessationExecutionService,
        mock_event_writer: AsyncMock,
        mock_cessation_flag_repo: AsyncMock,
    ) -> None:
        """Test that event is written before flag is set."""
        call_order = []

        async def track_write_event(**kwargs):
            call_order.append("write_event")
            mock_event = MagicMock()
            mock_event.event_id = uuid4()
            mock_event.sequence = 100
            mock_event.content_hash = "c" * 64
            return mock_event

        async def track_set_ceased(details):
            call_order.append("set_ceased")

        mock_event_writer.write_event = track_write_event
        mock_cessation_flag_repo.set_ceased = track_set_ceased

        await cessation_service.execute_cessation(
            triggering_event_id=uuid4(),
            reason="Test",
        )

        assert call_order == ["write_event", "set_ceased"]


class TestCessationExecutionServiceWithDeliberation:
    """Test FR135 - Final deliberation recording before cessation."""

    @pytest.fixture
    def mock_deliberation_service(self) -> AsyncMock:
        """Create a mock FinalDeliberationService."""
        from src.application.ports.final_deliberation_recorder import (
            RecordDeliberationResult,
        )

        service = AsyncMock()
        service.record_and_proceed = AsyncMock(
            return_value=RecordDeliberationResult(
                success=True,
                event_id=uuid4(),
                recorded_at=datetime.now(timezone.utc),
                error_code=None,
                error_message=None,
            )
        )
        return service

    @pytest.fixture
    def mock_archon_deliberations(self) -> list:
        """Create 72 mock Archon deliberations."""
        from src.domain.events.cessation_deliberation import (
            ArchonDeliberation,
            ArchonPosition,
        )

        timestamp = datetime.now(timezone.utc)
        deliberations = []
        for i in range(72):
            deliberations.append(
                ArchonDeliberation(
                    archon_id=f"archon-{i + 1:03d}",
                    position=ArchonPosition.SUPPORT_CESSATION,
                    reasoning=f"Support {i + 1}",
                    statement_timestamp=timestamp,
                )
            )
        return deliberations

    @pytest.mark.asyncio
    async def test_execute_with_deliberation_records_deliberation_first(
        self,
        mock_event_writer: AsyncMock,
        mock_event_store: AsyncMock,
        mock_cessation_flag_repo: AsyncMock,
        mock_deliberation_service: AsyncMock,
        mock_archon_deliberations: list,
    ) -> None:
        """FR135: Deliberation should be recorded before cessation."""
        service = CessationExecutionService(
            event_writer=mock_event_writer,
            event_store=mock_event_store,
            cessation_flag_repo=mock_cessation_flag_repo,
            final_deliberation_service=mock_deliberation_service,
        )

        await service.execute_cessation_with_deliberation(
            deliberation_id=uuid4(),
            deliberation_started_at=datetime.now(timezone.utc),
            deliberation_ended_at=datetime.now(timezone.utc),
            archon_deliberations=mock_archon_deliberations,
            triggering_event_id=uuid4(),
            reason="Test cessation",
        )

        # Deliberation service was called
        mock_deliberation_service.record_and_proceed.assert_called_once()

        # Event writer was also called (for cessation event)
        mock_event_writer.write_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_raises_error_without_deliberation_service(
        self,
        mock_event_writer: AsyncMock,
        mock_event_store: AsyncMock,
        mock_cessation_flag_repo: AsyncMock,
        mock_archon_deliberations: list,
    ) -> None:
        """Should raise error if deliberation service not configured."""
        service = CessationExecutionService(
            event_writer=mock_event_writer,
            event_store=mock_event_store,
            cessation_flag_repo=mock_cessation_flag_repo,
            # No final_deliberation_service
        )

        with pytest.raises(CessationExecutionError) as exc_info:
            await service.execute_cessation_with_deliberation(
                deliberation_id=uuid4(),
                deliberation_started_at=datetime.now(timezone.utc),
                deliberation_ended_at=datetime.now(timezone.utc),
                archon_deliberations=mock_archon_deliberations,
                triggering_event_id=uuid4(),
                reason="Test",
            )

        assert "FR135" in str(exc_info.value)
        assert "not configured" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_raises_error_on_complete_deliberation_failure(
        self,
        mock_event_writer: AsyncMock,
        mock_event_store: AsyncMock,
        mock_cessation_flag_repo: AsyncMock,
        mock_archon_deliberations: list,
    ) -> None:
        """FR135: Should raise error if deliberation recording fails completely."""
        from src.application.services.final_deliberation_service import (
            DeliberationRecordingCompleteFailure,
        )

        failing_service = AsyncMock()
        failing_service.record_and_proceed = AsyncMock(
            side_effect=DeliberationRecordingCompleteFailure(
                error_code="CATASTROPHIC_FAILURE",
                error_message="Cannot record anything",
            )
        )

        service = CessationExecutionService(
            event_writer=mock_event_writer,
            event_store=mock_event_store,
            cessation_flag_repo=mock_cessation_flag_repo,
            final_deliberation_service=failing_service,
        )

        with pytest.raises(CessationExecutionError) as exc_info:
            await service.execute_cessation_with_deliberation(
                deliberation_id=uuid4(),
                deliberation_started_at=datetime.now(timezone.utc),
                deliberation_ended_at=datetime.now(timezone.utc),
                archon_deliberations=mock_archon_deliberations,
                triggering_event_id=uuid4(),
                reason="Test",
            )

        assert "FR135" in str(exc_info.value)
        assert "CATASTROPHIC_FAILURE" in str(exc_info.value)

        # Cessation event should NOT have been written
        mock_event_writer.write_event.assert_not_called()

    @pytest.mark.asyncio
    async def test_cessation_not_executed_on_deliberation_failure(
        self,
        mock_event_writer: AsyncMock,
        mock_event_store: AsyncMock,
        mock_cessation_flag_repo: AsyncMock,
        mock_archon_deliberations: list,
    ) -> None:
        """Cessation should NOT proceed if deliberation recording fails."""
        from src.application.services.final_deliberation_service import (
            DeliberationRecordingCompleteFailure,
        )

        failing_service = AsyncMock()
        failing_service.record_and_proceed = AsyncMock(
            side_effect=DeliberationRecordingCompleteFailure(
                error_code="DB_DOWN",
                error_message="Database unavailable",
            )
        )

        service = CessationExecutionService(
            event_writer=mock_event_writer,
            event_store=mock_event_store,
            cessation_flag_repo=mock_cessation_flag_repo,
            final_deliberation_service=failing_service,
        )

        with pytest.raises(CessationExecutionError):
            await service.execute_cessation_with_deliberation(
                deliberation_id=uuid4(),
                deliberation_started_at=datetime.now(timezone.utc),
                deliberation_ended_at=datetime.now(timezone.utc),
                archon_deliberations=mock_archon_deliberations,
                triggering_event_id=uuid4(),
                reason="Test",
            )

        # Flag should NOT have been set
        mock_cessation_flag_repo.set_ceased.assert_not_called()

    @pytest.mark.asyncio
    async def test_deliberation_recorded_before_cessation_event(
        self,
        mock_event_writer: AsyncMock,
        mock_event_store: AsyncMock,
        mock_cessation_flag_repo: AsyncMock,
        mock_archon_deliberations: list,
    ) -> None:
        """FR135: Verify deliberation is recorded BEFORE cessation event."""
        from src.application.ports.final_deliberation_recorder import (
            RecordDeliberationResult,
        )

        call_order = []

        async def track_deliberation(*args, **kwargs):
            call_order.append("record_deliberation")
            return RecordDeliberationResult(
                success=True,
                event_id=uuid4(),
                recorded_at=datetime.now(timezone.utc),
                error_code=None,
                error_message=None,
            )

        async def track_write_event(**kwargs):
            call_order.append("write_cessation_event")
            mock_event = MagicMock()
            mock_event.event_id = uuid4()
            mock_event.sequence = 100
            mock_event.content_hash = "c" * 64
            return mock_event

        tracking_service = AsyncMock()
        tracking_service.record_and_proceed = track_deliberation

        mock_event_writer.write_event = track_write_event

        service = CessationExecutionService(
            event_writer=mock_event_writer,
            event_store=mock_event_store,
            cessation_flag_repo=mock_cessation_flag_repo,
            final_deliberation_service=tracking_service,
        )

        await service.execute_cessation_with_deliberation(
            deliberation_id=uuid4(),
            deliberation_started_at=datetime.now(timezone.utc),
            deliberation_ended_at=datetime.now(timezone.utc),
            archon_deliberations=mock_archon_deliberations,
            triggering_event_id=uuid4(),
            reason="Test",
        )

        # Deliberation MUST be recorded before cessation event
        assert call_order == ["record_deliberation", "write_cessation_event"]
