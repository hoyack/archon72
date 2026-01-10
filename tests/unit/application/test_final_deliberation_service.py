"""Unit tests for FinalDeliberationService (Story 7.8, FR135).

Tests the service that orchestrates recording final deliberation before cessation.

Constitutional Constraints:
- FR135: Before cessation, final deliberation SHALL be recorded and immutable;
         if recording fails, that failure is the final event
- CT-11: Silent failure destroys legitimacy
- CT-12: Witnessing creates accountability
- CT-13: Integrity outranks availability

Test Coverage:
- record_and_proceed() success path
- record_and_proceed() failure -> failure event path
- Complete failure -> SystemHaltedError
- All 72 Archons required
- Dissent percentage calculation
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from src.application.ports.final_deliberation_recorder import RecordDeliberationResult
from src.application.services.final_deliberation_service import (
    DeliberationRecordingCompleteFailure,
    FinalDeliberationService,
)
from src.domain.events.cessation_deliberation import (
    ArchonDeliberation,
    ArchonPosition,
    CessationDeliberationEventPayload,
    REQUIRED_ARCHON_COUNT,
)
from src.domain.events.collective_output import VoteCounts


def create_72_deliberations(
    yes_count: int = 50,
    no_count: int = 20,
    abstain_count: int = 2,
    timestamp: Optional[datetime] = None,
) -> list[ArchonDeliberation]:
    """Create exactly 72 Archon deliberations for testing."""
    if timestamp is None:
        timestamp = datetime.now(timezone.utc)

    assert yes_count + no_count + abstain_count == 72

    deliberations = []
    for i in range(yes_count):
        deliberations.append(
            ArchonDeliberation(
                archon_id=f"archon-{i + 1:03d}",
                position=ArchonPosition.SUPPORT_CESSATION,
                reasoning=f"Support reasoning {i + 1}",
                statement_timestamp=timestamp,
            )
        )
    for i in range(no_count):
        deliberations.append(
            ArchonDeliberation(
                archon_id=f"archon-{yes_count + i + 1:03d}",
                position=ArchonPosition.OPPOSE_CESSATION,
                reasoning=f"Oppose reasoning {yes_count + i + 1}",
                statement_timestamp=timestamp,
            )
        )
    for i in range(abstain_count):
        deliberations.append(
            ArchonDeliberation(
                archon_id=f"archon-{yes_count + no_count + i + 1:03d}",
                position=ArchonPosition.ABSTAIN,
                reasoning="",
                statement_timestamp=timestamp,
            )
        )

    return deliberations


class TestFinalDeliberationService:
    """Tests for FinalDeliberationService."""

    def test_create_service(self) -> None:
        """Should create service with recorder."""
        mock_recorder = MagicMock()
        service = FinalDeliberationService(recorder=mock_recorder)
        assert service is not None

    @pytest.mark.asyncio
    async def test_record_and_proceed_success(self) -> None:
        """Should record deliberation and return success."""
        mock_recorder = AsyncMock()
        event_id = uuid4()
        recorded_at = datetime.now(timezone.utc)

        mock_recorder.record_deliberation.return_value = RecordDeliberationResult(
            success=True,
            event_id=event_id,
            recorded_at=recorded_at,
            error_code=None,
            error_message=None,
        )

        service = FinalDeliberationService(recorder=mock_recorder)

        deliberations = create_72_deliberations(50, 20, 2)

        result = await service.record_and_proceed(
            deliberation_id=uuid4(),
            started_at=datetime.now(timezone.utc),
            ended_at=datetime.now(timezone.utc),
            archon_deliberations=deliberations,
        )

        assert result.success is True
        assert result.event_id == event_id
        assert mock_recorder.record_deliberation.called

    @pytest.mark.asyncio
    async def test_record_and_proceed_records_failure_on_first_failure(self) -> None:
        """Should record failure event when deliberation recording fails."""
        mock_recorder = AsyncMock()
        failure_event_id = uuid4()
        recorded_at = datetime.now(timezone.utc)

        # First call fails
        mock_recorder.record_deliberation.return_value = RecordDeliberationResult(
            success=False,
            event_id=None,
            recorded_at=None,
            error_code="DB_TIMEOUT",
            error_message="Database timeout",
        )
        # Second call (record_failure) succeeds
        mock_recorder.record_failure.return_value = RecordDeliberationResult(
            success=True,
            event_id=failure_event_id,
            recorded_at=recorded_at,
            error_code=None,
            error_message=None,
        )

        service = FinalDeliberationService(recorder=mock_recorder)

        deliberations = create_72_deliberations(50, 20, 2)

        result = await service.record_and_proceed(
            deliberation_id=uuid4(),
            started_at=datetime.now(timezone.utc),
            ended_at=datetime.now(timezone.utc),
            archon_deliberations=deliberations,
        )

        # Failure was recorded as final event
        assert result.success is True  # The failure recording succeeded
        assert result.event_id == failure_event_id
        assert mock_recorder.record_failure.called

    @pytest.mark.asyncio
    async def test_record_and_proceed_raises_on_complete_failure(self) -> None:
        """Should raise error when both deliberation and failure recording fail."""
        mock_recorder = AsyncMock()

        # Both calls fail
        mock_recorder.record_deliberation.return_value = RecordDeliberationResult(
            success=False,
            event_id=None,
            recorded_at=None,
            error_code="DB_TIMEOUT",
            error_message="Database timeout",
        )
        mock_recorder.record_failure.return_value = RecordDeliberationResult(
            success=False,
            event_id=None,
            recorded_at=None,
            error_code="DB_CRASH",
            error_message="Database crashed",
        )

        service = FinalDeliberationService(recorder=mock_recorder)

        deliberations = create_72_deliberations(50, 20, 2)

        with pytest.raises(DeliberationRecordingCompleteFailure) as exc_info:
            await service.record_and_proceed(
                deliberation_id=uuid4(),
                started_at=datetime.now(timezone.utc),
                ended_at=datetime.now(timezone.utc),
                archon_deliberations=deliberations,
            )

        assert "DB_CRASH" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_calculates_vote_counts_from_deliberations(self) -> None:
        """Should calculate vote counts from deliberation positions."""
        mock_recorder = AsyncMock()
        mock_recorder.record_deliberation.return_value = RecordDeliberationResult(
            success=True,
            event_id=uuid4(),
            recorded_at=datetime.now(timezone.utc),
            error_code=None,
            error_message=None,
        )

        service = FinalDeliberationService(recorder=mock_recorder)

        # 40 yes, 30 no, 2 abstain
        deliberations = create_72_deliberations(40, 30, 2)

        await service.record_and_proceed(
            deliberation_id=uuid4(),
            started_at=datetime.now(timezone.utc),
            ended_at=datetime.now(timezone.utc),
            archon_deliberations=deliberations,
        )

        # Verify the payload was correct
        call_args = mock_recorder.record_deliberation.call_args
        payload: CessationDeliberationEventPayload = call_args[0][0]

        assert payload.vote_counts.yes_count == 40
        assert payload.vote_counts.no_count == 30
        assert payload.vote_counts.abstain_count == 2

    @pytest.mark.asyncio
    async def test_calculates_dissent_percentage(self) -> None:
        """Should calculate dissent percentage based on minority."""
        mock_recorder = AsyncMock()
        mock_recorder.record_deliberation.return_value = RecordDeliberationResult(
            success=True,
            event_id=uuid4(),
            recorded_at=datetime.now(timezone.utc),
            error_code=None,
            error_message=None,
        )

        service = FinalDeliberationService(recorder=mock_recorder)

        # 50 yes (majority), 20 no, 2 abstain
        # Dissent = non-yes votes / total = (20 + 2) / 72 = 30.56%
        deliberations = create_72_deliberations(50, 20, 2)

        await service.record_and_proceed(
            deliberation_id=uuid4(),
            started_at=datetime.now(timezone.utc),
            ended_at=datetime.now(timezone.utc),
            archon_deliberations=deliberations,
        )

        call_args = mock_recorder.record_deliberation.call_args
        payload: CessationDeliberationEventPayload = call_args[0][0]

        # (20 + 2) / 72 * 100 = 30.555...
        assert 30.5 <= payload.dissent_percentage <= 30.6

    @pytest.mark.asyncio
    async def test_calculates_duration_seconds(self) -> None:
        """Should calculate duration from started/ended timestamps."""
        mock_recorder = AsyncMock()
        mock_recorder.record_deliberation.return_value = RecordDeliberationResult(
            success=True,
            event_id=uuid4(),
            recorded_at=datetime.now(timezone.utc),
            error_code=None,
            error_message=None,
        )

        service = FinalDeliberationService(recorder=mock_recorder)

        started = datetime(2026, 1, 8, 10, 0, 0, tzinfo=timezone.utc)
        ended = datetime(2026, 1, 8, 12, 30, 0, tzinfo=timezone.utc)
        # 2.5 hours = 9000 seconds

        deliberations = create_72_deliberations(50, 20, 2)

        await service.record_and_proceed(
            deliberation_id=uuid4(),
            started_at=started,
            ended_at=ended,
            archon_deliberations=deliberations,
        )

        call_args = mock_recorder.record_deliberation.call_args
        payload: CessationDeliberationEventPayload = call_args[0][0]

        assert payload.duration_seconds == 9000

    @pytest.mark.asyncio
    async def test_rejects_fewer_than_72_deliberations(self) -> None:
        """Should reject deliberations with fewer than 72 Archons."""
        mock_recorder = AsyncMock()
        service = FinalDeliberationService(recorder=mock_recorder)

        # Only 71 deliberations
        timestamp = datetime.now(timezone.utc)
        deliberations = [
            ArchonDeliberation(
                archon_id=f"archon-{i + 1:03d}",
                position=ArchonPosition.SUPPORT_CESSATION,
                reasoning="Test",
                statement_timestamp=timestamp,
            )
            for i in range(71)
        ]

        with pytest.raises(ValueError, match="72"):
            await service.record_and_proceed(
                deliberation_id=uuid4(),
                started_at=datetime.now(timezone.utc),
                ended_at=datetime.now(timezone.utc),
                archon_deliberations=deliberations,
            )

    @pytest.mark.asyncio
    async def test_unanimous_support_zero_dissent(self) -> None:
        """Unanimous support should have 0% dissent."""
        mock_recorder = AsyncMock()
        mock_recorder.record_deliberation.return_value = RecordDeliberationResult(
            success=True,
            event_id=uuid4(),
            recorded_at=datetime.now(timezone.utc),
            error_code=None,
            error_message=None,
        )

        service = FinalDeliberationService(recorder=mock_recorder)

        # All 72 support
        deliberations = create_72_deliberations(72, 0, 0)

        await service.record_and_proceed(
            deliberation_id=uuid4(),
            started_at=datetime.now(timezone.utc),
            ended_at=datetime.now(timezone.utc),
            archon_deliberations=deliberations,
        )

        call_args = mock_recorder.record_deliberation.call_args
        payload: CessationDeliberationEventPayload = call_args[0][0]

        assert payload.dissent_percentage == 0.0

    @pytest.mark.asyncio
    async def test_failure_payload_includes_retry_info(self) -> None:
        """Failure event should include retry information."""
        mock_recorder = AsyncMock()

        # First call fails
        mock_recorder.record_deliberation.return_value = RecordDeliberationResult(
            success=False,
            event_id=None,
            recorded_at=None,
            error_code="DB_TIMEOUT",
            error_message="Database timeout",
        )
        # Failure recording succeeds
        mock_recorder.record_failure.return_value = RecordDeliberationResult(
            success=True,
            event_id=uuid4(),
            recorded_at=datetime.now(timezone.utc),
            error_code=None,
            error_message=None,
        )

        service = FinalDeliberationService(recorder=mock_recorder, max_retries=3)

        deliberations = create_72_deliberations(50, 20, 2)

        await service.record_and_proceed(
            deliberation_id=uuid4(),
            started_at=datetime.now(timezone.utc),
            ended_at=datetime.now(timezone.utc),
            archon_deliberations=deliberations,
        )

        # Verify failure payload was created with retry info
        call_args = mock_recorder.record_failure.call_args
        failure_payload = call_args[0][0]

        assert failure_payload.retry_count >= 0
        assert failure_payload.partial_archon_count == 72  # All deliberations collected


class TestDeliberationRecordingCompleteFailure:
    """Tests for DeliberationRecordingCompleteFailure exception."""

    def test_exception_includes_error_details(self) -> None:
        """Exception should include error code and message."""
        exc = DeliberationRecordingCompleteFailure(
            error_code="CATASTROPHIC_FAILURE",
            error_message="Everything is broken",
        )

        assert exc.error_code == "CATASTROPHIC_FAILURE"
        assert exc.error_message == "Everything is broken"
        assert "CATASTROPHIC_FAILURE" in str(exc)

    def test_exception_inherits_from_exception(self) -> None:
        """Exception should inherit from base Exception."""
        exc = DeliberationRecordingCompleteFailure(
            error_code="TEST",
            error_message="Test",
        )
        assert isinstance(exc, Exception)
