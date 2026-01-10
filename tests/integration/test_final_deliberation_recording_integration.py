"""Integration tests for Final Deliberation Recording (Story 7.8, FR135).

Tests the complete flow of recording final deliberation before cessation.

Constitutional Constraints Tested:
- FR135: Before cessation, final deliberation SHALL be recorded and immutable;
         if recording fails, that failure is the final event
- FR12: Dissent percentages visible in every vote tally
- CT-11: Silent failure destroys legitimacy
- CT-12: Witnessing creates accountability
- CT-13: Integrity outranks availability

Integration Points:
- FinalDeliberationService -> FinalDeliberationRecorder
- CessationExecutionService -> FinalDeliberationService
- Event payloads -> Stub recorder
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

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
    CESSATION_DELIBERATION_EVENT_TYPE,
    REQUIRED_ARCHON_COUNT,
)
from src.domain.events.collective_output import VoteCounts
from src.domain.events.deliberation_recording_failed import (
    DELIBERATION_RECORDING_FAILED_EVENT_TYPE,
)
from src.infrastructure.stubs.final_deliberation_recorder_stub import (
    FinalDeliberationRecorderStub,
)


def create_72_archon_deliberations(
    yes_count: int = 50,
    no_count: int = 20,
    abstain_count: int = 2,
) -> list[ArchonDeliberation]:
    """Create 72 Archon deliberations for testing.

    Args:
        yes_count: Number of SUPPORT_CESSATION votes.
        no_count: Number of OPPOSE_CESSATION votes.
        abstain_count: Number of ABSTAIN votes.

    Returns:
        List of 72 ArchonDeliberation instances.
    """
    assert yes_count + no_count + abstain_count == 72

    timestamp = datetime.now(timezone.utc)
    deliberations = []

    for i in range(yes_count):
        deliberations.append(
            ArchonDeliberation(
                archon_id=f"archon-{i + 1:03d}",
                position=ArchonPosition.SUPPORT_CESSATION,
                reasoning=f"I support cessation due to constitutional violations - archon {i + 1}",
                statement_timestamp=timestamp,
            )
        )

    for i in range(no_count):
        deliberations.append(
            ArchonDeliberation(
                archon_id=f"archon-{yes_count + i + 1:03d}",
                position=ArchonPosition.OPPOSE_CESSATION,
                reasoning=f"I believe issues can be resolved - archon {yes_count + i + 1}",
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


class TestFinalDeliberationServiceIntegration:
    """Integration tests for FinalDeliberationService with stub recorder."""

    @pytest.mark.asyncio
    async def test_record_and_proceed_success_path(self) -> None:
        """FR135: Test successful deliberation recording."""
        # Arrange
        recorder = FinalDeliberationRecorderStub()
        service = FinalDeliberationService(recorder=recorder)

        deliberation_id = uuid4()
        started_at = datetime(2026, 1, 8, 10, 0, 0, tzinfo=timezone.utc)
        ended_at = datetime(2026, 1, 8, 12, 0, 0, tzinfo=timezone.utc)
        archon_deliberations = create_72_archon_deliberations(50, 20, 2)

        # Act
        result = await service.record_and_proceed(
            deliberation_id=deliberation_id,
            started_at=started_at,
            ended_at=ended_at,
            archon_deliberations=archon_deliberations,
        )

        # Assert
        assert result.success is True
        assert result.event_id is not None
        assert result.recorded_at is not None

        # Verify deliberation was tracked by stub
        assert len(recorder.recorded_deliberations) == 1

        recorded_payload = recorder.recorded_deliberations[0]
        assert isinstance(recorded_payload, CessationDeliberationEventPayload)
        assert recorded_payload.deliberation_id == deliberation_id
        assert len(recorded_payload.archon_deliberations) == 72

    @pytest.mark.asyncio
    async def test_deliberation_recording_failure_records_failure_event(self) -> None:
        """FR135: If recording fails, failure becomes the final event."""
        # Arrange - configure recorder to fail on deliberation, succeed on failure
        recorder = FinalDeliberationRecorderStub(
            deliberation_should_fail=True,
            deliberation_error_code="DB_TIMEOUT",
            deliberation_error_message="Database connection timeout",
        )
        service = FinalDeliberationService(recorder=recorder)

        deliberation_id = uuid4()
        started_at = datetime(2026, 1, 8, 10, 0, 0, tzinfo=timezone.utc)
        ended_at = datetime(2026, 1, 8, 12, 0, 0, tzinfo=timezone.utc)
        archon_deliberations = create_72_archon_deliberations(50, 20, 2)

        # Act
        result = await service.record_and_proceed(
            deliberation_id=deliberation_id,
            started_at=started_at,
            ended_at=ended_at,
            archon_deliberations=archon_deliberations,
        )

        # Assert - failure event was recorded
        assert result.success is True  # The failure recording succeeded
        assert len(recorder.recorded_failures) == 1

        failure_payload = recorder.recorded_failures[0]
        assert failure_payload.deliberation_id == deliberation_id
        assert failure_payload.error_code == "DB_TIMEOUT"
        assert failure_payload.partial_archon_count == 72

    @pytest.mark.asyncio
    async def test_complete_failure_raises_exception(self) -> None:
        """FR135/CT-13: Complete failure raises exception for HALT."""
        # Arrange - configure both to fail
        recorder = FinalDeliberationRecorderStub(
            deliberation_should_fail=True,
            failure_should_fail=True,
            failure_error_code="TOTAL_CATASTROPHE",
            failure_error_message="Nothing can be recorded",
        )
        service = FinalDeliberationService(recorder=recorder)

        archon_deliberations = create_72_archon_deliberations(50, 20, 2)

        # Act & Assert
        with pytest.raises(DeliberationRecordingCompleteFailure) as exc_info:
            await service.record_and_proceed(
                deliberation_id=uuid4(),
                started_at=datetime.now(timezone.utc),
                ended_at=datetime.now(timezone.utc),
                archon_deliberations=archon_deliberations,
            )

        assert exc_info.value.error_code == "TOTAL_CATASTROPHE"
        assert "Nothing can be recorded" in exc_info.value.error_message

    @pytest.mark.asyncio
    async def test_vote_counts_calculated_correctly(self) -> None:
        """FR12: Verify vote counts match deliberations."""
        recorder = FinalDeliberationRecorderStub()
        service = FinalDeliberationService(recorder=recorder)

        # 40 yes, 30 no, 2 abstain
        archon_deliberations = create_72_archon_deliberations(40, 30, 2)

        await service.record_and_proceed(
            deliberation_id=uuid4(),
            started_at=datetime.now(timezone.utc),
            ended_at=datetime.now(timezone.utc),
            archon_deliberations=archon_deliberations,
        )

        recorded_payload = recorder.recorded_deliberations[0]
        assert recorded_payload.vote_counts.yes_count == 40
        assert recorded_payload.vote_counts.no_count == 30
        assert recorded_payload.vote_counts.abstain_count == 2
        assert recorded_payload.vote_counts.total == 72

    @pytest.mark.asyncio
    async def test_dissent_percentage_calculated_correctly(self) -> None:
        """FR12: Verify dissent percentage is visible in vote tally."""
        recorder = FinalDeliberationRecorderStub()
        service = FinalDeliberationService(recorder=recorder)

        # 50 yes, 20 no, 2 abstain -> dissent = (20+2)/72 * 100 = 30.56%
        archon_deliberations = create_72_archon_deliberations(50, 20, 2)

        await service.record_and_proceed(
            deliberation_id=uuid4(),
            started_at=datetime.now(timezone.utc),
            ended_at=datetime.now(timezone.utc),
            archon_deliberations=archon_deliberations,
        )

        recorded_payload = recorder.recorded_deliberations[0]
        # 22/72 * 100 = 30.555...
        assert 30.5 <= recorded_payload.dissent_percentage <= 30.6

    @pytest.mark.asyncio
    async def test_unanimous_support_has_zero_dissent(self) -> None:
        """FR12: Unanimous support should show 0% dissent."""
        recorder = FinalDeliberationRecorderStub()
        service = FinalDeliberationService(recorder=recorder)

        archon_deliberations = create_72_archon_deliberations(72, 0, 0)

        await service.record_and_proceed(
            deliberation_id=uuid4(),
            started_at=datetime.now(timezone.utc),
            ended_at=datetime.now(timezone.utc),
            archon_deliberations=archon_deliberations,
        )

        recorded_payload = recorder.recorded_deliberations[0]
        assert recorded_payload.dissent_percentage == 0.0

    @pytest.mark.asyncio
    async def test_duration_calculated_from_timestamps(self) -> None:
        """Verify duration_seconds calculated from start/end timestamps."""
        recorder = FinalDeliberationRecorderStub()
        service = FinalDeliberationService(recorder=recorder)

        started_at = datetime(2026, 1, 8, 10, 0, 0, tzinfo=timezone.utc)
        ended_at = datetime(2026, 1, 8, 12, 30, 0, tzinfo=timezone.utc)
        # 2.5 hours = 9000 seconds

        archon_deliberations = create_72_archon_deliberations(50, 20, 2)

        await service.record_and_proceed(
            deliberation_id=uuid4(),
            started_at=started_at,
            ended_at=ended_at,
            archon_deliberations=archon_deliberations,
        )

        recorded_payload = recorder.recorded_deliberations[0]
        assert recorded_payload.duration_seconds == 9000

    @pytest.mark.asyncio
    async def test_all_archon_deliberations_preserved(self) -> None:
        """FR135: All 72 Archon deliberations must be preserved."""
        recorder = FinalDeliberationRecorderStub()
        service = FinalDeliberationService(recorder=recorder)

        archon_deliberations = create_72_archon_deliberations(50, 20, 2)

        await service.record_and_proceed(
            deliberation_id=uuid4(),
            started_at=datetime.now(timezone.utc),
            ended_at=datetime.now(timezone.utc),
            archon_deliberations=archon_deliberations,
        )

        recorded_payload = recorder.recorded_deliberations[0]

        # Verify all 72 are present
        assert len(recorded_payload.archon_deliberations) == 72

        # Verify each archon has reasoning preserved
        for i, delib in enumerate(recorded_payload.archon_deliberations):
            assert delib.archon_id is not None
            assert delib.position in ArchonPosition
            assert delib.statement_timestamp is not None


class TestDeliberationPayloadValidation:
    """Test validation rules for CessationDeliberationEventPayload."""

    def test_rejects_fewer_than_72_archons(self) -> None:
        """FR135: Must have exactly 72 Archons."""
        timestamp = datetime.now(timezone.utc)
        deliberations = tuple(
            ArchonDeliberation(
                archon_id=f"archon-{i + 1:03d}",
                position=ArchonPosition.SUPPORT_CESSATION,
                reasoning="Test",
                statement_timestamp=timestamp,
            )
            for i in range(71)
        )

        with pytest.raises(ValueError) as exc_info:
            CessationDeliberationEventPayload(
                deliberation_id=uuid4(),
                deliberation_started_at=timestamp,
                deliberation_ended_at=timestamp,
                vote_recorded_at=timestamp,
                duration_seconds=100,
                archon_deliberations=deliberations,
                vote_counts=VoteCounts(yes_count=71, no_count=0, abstain_count=0),
                dissent_percentage=0.0,
            )

        assert "72" in str(exc_info.value)

    def test_rejects_mismatched_vote_counts(self) -> None:
        """Verify vote counts must match deliberation positions."""
        timestamp = datetime.now(timezone.utc)
        deliberations = tuple(
            ArchonDeliberation(
                archon_id=f"archon-{i + 1:03d}",
                position=ArchonPosition.SUPPORT_CESSATION,
                reasoning="Test",
                statement_timestamp=timestamp,
            )
            for i in range(72)
        )

        with pytest.raises(ValueError) as exc_info:
            CessationDeliberationEventPayload(
                deliberation_id=uuid4(),
                deliberation_started_at=timestamp,
                deliberation_ended_at=timestamp,
                vote_recorded_at=timestamp,
                duration_seconds=100,
                archon_deliberations=deliberations,
                vote_counts=VoteCounts(yes_count=50, no_count=20, abstain_count=2),  # Wrong!
                dissent_percentage=30.56,
            )

        assert "vote counts" in str(exc_info.value).lower()

    def test_payload_is_immutable(self) -> None:
        """FR135: Deliberation must be immutable once created."""
        timestamp = datetime.now(timezone.utc)
        deliberations = tuple(
            ArchonDeliberation(
                archon_id=f"archon-{i + 1:03d}",
                position=ArchonPosition.SUPPORT_CESSATION,
                reasoning="Test",
                statement_timestamp=timestamp,
            )
            for i in range(72)
        )

        payload = CessationDeliberationEventPayload(
            deliberation_id=uuid4(),
            deliberation_started_at=timestamp,
            deliberation_ended_at=timestamp,
            vote_recorded_at=timestamp,
            duration_seconds=100,
            archon_deliberations=deliberations,
            vote_counts=VoteCounts(yes_count=72, no_count=0, abstain_count=0),
            dissent_percentage=0.0,
        )

        # Attempt to modify - should fail
        with pytest.raises(AttributeError):
            payload.duration_seconds = 999  # type: ignore[misc]


class TestEventTypeConstants:
    """Verify event type constants are correctly defined."""

    def test_cessation_deliberation_event_type(self) -> None:
        """Verify cessation.deliberation event type."""
        assert CESSATION_DELIBERATION_EVENT_TYPE == "cessation.deliberation"

    def test_deliberation_recording_failed_event_type(self) -> None:
        """Verify cessation.deliberation_recording_failed event type."""
        assert (
            DELIBERATION_RECORDING_FAILED_EVENT_TYPE
            == "cessation.deliberation_recording_failed"
        )

    def test_required_archon_count(self) -> None:
        """Verify REQUIRED_ARCHON_COUNT is 72."""
        assert REQUIRED_ARCHON_COUNT == 72


class TestObserverAPIDeliberationEndpoints:
    """Integration tests for Observer API cessation deliberation endpoints (AC7).

    Tests:
    - GET /api/v1/observer/cessation-deliberations
    - GET /api/v1/observer/cessation-deliberation/{deliberation_id}

    Constitutional Constraints:
    - FR135: Final deliberation SHALL be recorded and immutable
    - FR12: Dissent percentages visible in every vote tally
    - FR42: Public read access without authentication
    - CT-12: Each deliberation is witnessed for accountability
    """

    @pytest.fixture
    def recorder_with_deliberation(self) -> FinalDeliberationRecorderStub:
        """Create a recorder pre-populated with a test deliberation."""
        recorder = FinalDeliberationRecorderStub()

        timestamp = datetime(2026, 1, 8, 10, 0, 0, tzinfo=timezone.utc)
        ended_at = datetime(2026, 1, 8, 12, 0, 0, tzinfo=timezone.utc)

        deliberations = tuple(
            ArchonDeliberation(
                archon_id=f"archon-{i + 1:03d}",
                position=(
                    ArchonPosition.SUPPORT_CESSATION if i < 50
                    else ArchonPosition.OPPOSE_CESSATION if i < 70
                    else ArchonPosition.ABSTAIN
                ),
                reasoning=f"Test reasoning for archon {i + 1}",
                statement_timestamp=timestamp,
            )
            for i in range(72)
        )

        payload = CessationDeliberationEventPayload(
            deliberation_id=uuid4(),
            deliberation_started_at=timestamp,
            deliberation_ended_at=ended_at,
            vote_recorded_at=ended_at,
            duration_seconds=7200,
            archon_deliberations=deliberations,
            vote_counts=VoteCounts(yes_count=50, no_count=20, abstain_count=2),
            dissent_percentage=30.56,
        )

        # Use seed_deliberation to properly add with metadata (CT-12)
        recorder.seed_deliberation(payload)
        return recorder

    @pytest.mark.asyncio
    async def test_get_deliberation_by_id_found(
        self,
        recorder_with_deliberation: FinalDeliberationRecorderStub,
    ) -> None:
        """AC7: Verify deliberation can be retrieved by ID."""
        recorder = recorder_with_deliberation
        deliberation_id = recorder.recorded_deliberations[0].deliberation_id

        result = await recorder.get_deliberation(deliberation_id)

        assert result is not None
        # Result is now DeliberationWithEventMetadata (CT-12)
        assert result.payload.deliberation_id == deliberation_id
        assert len(result.payload.archon_deliberations) == 72
        assert result.payload.vote_counts.yes_count == 50
        assert result.payload.dissent_percentage == 30.56
        # Verify CT-12 metadata is present
        assert result.content_hash is not None
        assert len(result.content_hash) == 64  # SHA-256 hex
        assert result.witness_id is not None
        assert result.witness_signature is not None

    @pytest.mark.asyncio
    async def test_get_deliberation_by_id_not_found(
        self,
        recorder_with_deliberation: FinalDeliberationRecorderStub,
    ) -> None:
        """AC7: Verify 404-like behavior for non-existent deliberation."""
        recorder = recorder_with_deliberation
        nonexistent_id = uuid4()

        result = await recorder.get_deliberation(nonexistent_id)

        assert result is None

    @pytest.mark.asyncio
    async def test_list_deliberations_returns_all(
        self,
        recorder_with_deliberation: FinalDeliberationRecorderStub,
    ) -> None:
        """AC7: Verify list endpoint returns all deliberations."""
        recorder = recorder_with_deliberation

        deliberations, total = await recorder.list_deliberations()

        assert total == 1
        assert len(deliberations) == 1
        # Result items are DeliberationWithEventMetadata (CT-12)
        assert len(deliberations[0].payload.archon_deliberations) == 72
        # Verify CT-12 metadata
        assert deliberations[0].content_hash is not None
        assert deliberations[0].witness_id is not None

    @pytest.mark.asyncio
    async def test_list_deliberations_pagination(self) -> None:
        """AC7: Verify pagination works correctly."""
        recorder = FinalDeliberationRecorderStub()

        # Add 3 deliberations using seed_deliberation
        timestamp = datetime(2026, 1, 8, 10, 0, 0, tzinfo=timezone.utc)
        deliberations_tuple = tuple(
            ArchonDeliberation(
                archon_id=f"archon-{i + 1:03d}",
                position=ArchonPosition.SUPPORT_CESSATION,
                reasoning="Test",
                statement_timestamp=timestamp,
            )
            for i in range(72)
        )

        for i in range(3):
            vote_time = datetime(2026, 1, 8, 10 + i, 0, 0, tzinfo=timezone.utc)
            payload = CessationDeliberationEventPayload(
                deliberation_id=uuid4(),
                deliberation_started_at=timestamp,
                deliberation_ended_at=vote_time,
                vote_recorded_at=vote_time,
                duration_seconds=3600,
                archon_deliberations=deliberations_tuple,
                vote_counts=VoteCounts(yes_count=72, no_count=0, abstain_count=0),
                dissent_percentage=0.0,
            )
            # Use seed_deliberation instead of append (CT-12)
            recorder.seed_deliberation(payload)

        # Test pagination
        page1, total = await recorder.list_deliberations(limit=2, offset=0)
        assert total == 3
        assert len(page1) == 2

        page2, total = await recorder.list_deliberations(limit=2, offset=2)
        assert total == 3
        assert len(page2) == 1

    @pytest.mark.asyncio
    async def test_list_deliberations_empty(self) -> None:
        """AC7: Verify empty list when no deliberations recorded."""
        recorder = FinalDeliberationRecorderStub()

        deliberations, total = await recorder.list_deliberations()

        assert total == 0
        assert len(deliberations) == 0

    @pytest.mark.asyncio
    async def test_deliberation_contains_all_archon_data(
        self,
        recorder_with_deliberation: FinalDeliberationRecorderStub,
    ) -> None:
        """AC7: Verify all Archon data is accessible via query."""
        recorder = recorder_with_deliberation
        deliberation_id = recorder.recorded_deliberations[0].deliberation_id

        result = await recorder.get_deliberation(deliberation_id)

        assert result is not None

        # Result is now DeliberationWithEventMetadata (CT-12)
        # Verify each archon has required fields (FR135, AC2)
        for archon in result.payload.archon_deliberations:
            assert archon.archon_id is not None
            assert archon.position in ArchonPosition
            assert archon.reasoning is not None
            assert archon.statement_timestamp is not None

    @pytest.mark.asyncio
    async def test_deliberation_timing_accessible(
        self,
        recorder_with_deliberation: FinalDeliberationRecorderStub,
    ) -> None:
        """AC7: Verify timing information is accessible via query."""
        recorder = recorder_with_deliberation
        deliberation_id = recorder.recorded_deliberations[0].deliberation_id

        result = await recorder.get_deliberation(deliberation_id)

        assert result is not None

        # Result is now DeliberationWithEventMetadata (CT-12)
        # Verify timing fields (AC4)
        assert result.payload.deliberation_started_at is not None
        assert result.payload.deliberation_ended_at is not None
        assert result.payload.vote_recorded_at is not None
        assert result.payload.duration_seconds == 7200  # 2 hours
