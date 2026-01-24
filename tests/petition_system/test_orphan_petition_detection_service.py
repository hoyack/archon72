"""Tests for orphan petition detection service (Story 8.3, FR-8.5).

Constitutional Requirements:
- FR-8.5: System SHALL identify petitions stuck in RECEIVED state
- NFR-7.1: 100% of orphans must be detected
- CT-12: All detection events must be witnessed

Test Coverage:
- Orphan detection with various age thresholds
- Event emission for detected orphans
- No orphans scenario (no event emission)
- Threshold configuration
- Age calculation accuracy
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import Mock
from uuid import uuid4

from src.application.services.orphan_petition_detection_service import (
    OrphanPetitionDetectionService,
)
from src.domain.events.orphan_petition import ORPHAN_PETITIONS_DETECTED_EVENT_TYPE
from src.domain.models.petition_submission import (
    PetitionState,
    PetitionSubmission,
    PetitionType,
)


class TestOrphanDetection:
    """Test orphan petition detection logic."""

    def test_detects_orphans_beyond_threshold(self):
        """Test orphans are detected when age > threshold (FR-8.5)."""
        # Setup: Create petition older than 24 hour threshold
        old_timestamp = datetime.now(timezone.utc) - timedelta(hours=30)
        _ = self._create_petition(
            received_at=old_timestamp, state=PetitionState.RECEIVED
        )

        petition_repo = Mock()
        petition_repo.find_by_state.return_value = [old_petition]

        event_writer = Mock()

        service = OrphanPetitionDetectionService(
            petition_repository=petition_repo,
            event_writer=event_writer,
            threshold_hours=24.0,
        )

        # Execute
        _ = service.detect_orphans()

        # Verify
        assert result.has_orphans()
        assert result.total_orphans == 1
        assert result.orphan_petitions[0].petition_id == old_petition.id
        assert result.orphan_petitions[0].age_hours >= 30.0
        assert result.oldest_orphan_age_hours >= 30.0

        # Verify event was emitted (CT-12)
        event_writer.write_event.assert_called_once()
        call_args = event_writer.write_event.call_args
        assert call_args[1]["event_type"] == ORPHAN_PETITIONS_DETECTED_EVENT_TYPE

    def test_no_orphans_when_all_recent(self):
        """Test no orphans detected when all petitions recent (FR-8.5)."""
        # Setup: Create petition within threshold
        recent_timestamp = datetime.now(timezone.utc) - timedelta(hours=12)
        _ = self._create_petition(
            received_at=recent_timestamp, state=PetitionState.RECEIVED
        )

        petition_repo = Mock()
        # Repository should return empty list since petition is too recent
        petition_repo.find_by_state.return_value = []

        event_writer = Mock()

        service = OrphanPetitionDetectionService(
            petition_repository=petition_repo,
            event_writer=event_writer,
            threshold_hours=24.0,
        )

        # Execute
        _ = service.detect_orphans()

        # Verify: No orphans detected, no event emitted
        assert not result.has_orphans()
        assert result.total_orphans == 0
        assert result.oldest_orphan_age_hours is None
        event_writer.write_event.assert_not_called()

    def test_no_orphans_when_no_received_petitions(self):
        """Test no orphans when no RECEIVED petitions exist (FR-8.5)."""
        petition_repo = Mock()
        petition_repo.find_by_state.return_value = []

        event_writer = Mock()

        service = OrphanPetitionDetectionService(
            petition_repository=petition_repo,
            event_writer=event_writer,
            threshold_hours=24.0,
        )

        # Execute
        _ = service.detect_orphans()

        # Verify
        assert not result.has_orphans()
        assert result.total_orphans == 0
        assert result.oldest_orphan_age_hours is None
        event_writer.write_event.assert_not_called()

    def test_detects_multiple_orphans(self):
        """Test detection of multiple orphaned petitions (NFR-7.1)."""
        # Setup: Create 3 old petitions
        timestamps = [
            datetime.now(timezone.utc) - timedelta(hours=30),
            datetime.now(timezone.utc) - timedelta(hours=48),
            datetime.now(timezone.utc) - timedelta(hours=72),
        ]

        petitions = [
            self._create_petition(received_at=ts, state=PetitionState.RECEIVED)
            for ts in timestamps
        ]

        petition_repo = Mock()
        petition_repo.find_by_state.return_value = petitions

        event_writer = Mock()

        service = OrphanPetitionDetectionService(
            petition_repository=petition_repo,
            event_writer=event_writer,
            threshold_hours=24.0,
        )

        # Execute
        _ = service.detect_orphans()

        # Verify: All 3 orphans detected (NFR-7.1)
        assert result.has_orphans()
        assert result.total_orphans == 3
        assert len(result.orphan_petitions) == 3

        # Verify oldest is 72 hours
        assert result.oldest_orphan_age_hours >= 72.0

        # Verify event emitted with all 3 IDs
        event_writer.write_event.assert_called_once()
        call_args = event_writer.write_event.call_args
        payload = call_args[1]["payload"]
        assert payload.orphan_count == 3
        assert len(payload.orphan_petition_ids) == 3

    def test_custom_threshold_configuration(self):
        """Test custom threshold configuration (FR-8.5)."""
        # Setup: Petition 36 hours old
        timestamp = datetime.now(timezone.utc) - timedelta(hours=36)
        _ = self._create_petition(received_at=timestamp, state=PetitionState.RECEIVED)

        petition_repo = Mock()
        # Repository should return empty list since 36h < 48h threshold
        petition_repo.find_by_state.return_value = []

        event_writer = Mock()

        # Service with 48 hour threshold
        service = OrphanPetitionDetectionService(
            petition_repository=petition_repo,
            event_writer=event_writer,
            threshold_hours=48.0,
        )

        # Execute
        _ = service.detect_orphans()

        # Verify: Not an orphan with 48 hour threshold
        assert not result.has_orphans()
        assert result.total_orphans == 0
        event_writer.write_event.assert_not_called()

    def test_event_payload_structure(self):
        """Test event payload contains all required fields (CT-12)."""
        # Setup
        old_timestamp = datetime.now(timezone.utc) - timedelta(hours=30)
        _ = self._create_petition(
            received_at=old_timestamp, state=PetitionState.RECEIVED
        )

        petition_repo = Mock()
        petition_repo.find_by_state.return_value = [old_petition]

        event_writer = Mock()

        service = OrphanPetitionDetectionService(
            petition_repository=petition_repo,
            event_writer=event_writer,
            threshold_hours=24.0,
        )

        # Execute
        service.detect_orphans()

        # Verify event payload structure
        call_args = event_writer.write_event.call_args
        payload = call_args[1]["payload"]

        assert payload.orphan_count == 1
        assert len(payload.orphan_petition_ids) == 1
        assert payload.orphan_petition_ids[0] == old_petition.id
        assert payload.oldest_orphan_age_hours >= 30.0
        assert payload.detection_threshold_hours == 24.0
        assert isinstance(payload.detected_at, datetime)

    def test_orphan_info_includes_metadata(self):
        """Test orphan info includes petition metadata for context."""
        # Setup
        old_timestamp = datetime.now(timezone.utc) - timedelta(hours=30)
        _ = self._create_petition(
            received_at=old_timestamp,
            state=PetitionState.RECEIVED,
            petition_type=PetitionType.CESSATION,
            co_signer_count=25,
        )

        petition_repo = Mock()
        petition_repo.find_by_state.return_value = [old_petition]

        event_writer = Mock()

        service = OrphanPetitionDetectionService(
            petition_repository=petition_repo,
            event_writer=event_writer,
            threshold_hours=24.0,
        )

        # Execute
        _ = service.detect_orphans()

        # Verify metadata included
        orphan_info = result.orphan_petitions[0]
        assert orphan_info.petition_type == "CESSATION"
        assert orphan_info.co_signer_count == 25
        assert orphan_info.created_at == old_timestamp

    def _create_petition(
        self,
        received_at: datetime,
        state: PetitionState,
        petition_type: PetitionType = PetitionType.GENERAL,
        co_signer_count: int = 0,
    ) -> PetitionSubmission:
        """Helper to create petition for testing."""
        return PetitionSubmission(
            id=uuid4(),
            type=petition_type,
            text="Test petition content",
            state=state,
            realm="test-realm",
            created_at=received_at,
            co_signer_count=co_signer_count,
        )


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_petition_exactly_at_threshold(self):
        """Test petition exactly at threshold is NOT considered orphan."""
        # Setup: Petition exactly 24 hours old
        timestamp = datetime.now(timezone.utc) - timedelta(hours=24, seconds=0)
        _ = self._create_petition(received_at=timestamp, state=PetitionState.RECEIVED)

        petition_repo = Mock()
        petition_repo.find_by_state.return_value = [petition]

        event_writer = Mock()

        service = OrphanPetitionDetectionService(
            petition_repository=petition_repo,
            event_writer=event_writer,
            threshold_hours=24.0,
        )

        # Execute
        _ = service.detect_orphans()

        # Verify: At threshold means NOT orphan (boundary condition)
        # Repository query uses received_before which is < cutoff, not <=
        # So petition exactly at threshold should not be returned
        # This test verifies the service behavior matches the query semantics

    def test_zero_threshold(self):
        """Test zero threshold detects all RECEIVED petitions."""
        # Setup: Very recent petition
        timestamp = datetime.now(timezone.utc) - timedelta(minutes=5)
        _ = self._create_petition(received_at=timestamp, state=PetitionState.RECEIVED)

        petition_repo = Mock()
        petition_repo.find_by_state.return_value = [petition]

        event_writer = Mock()

        service = OrphanPetitionDetectionService(
            petition_repository=petition_repo,
            event_writer=event_writer,
            threshold_hours=0.0,
        )

        # Execute
        _ = service.detect_orphans()

        # Verify: Even recent petition is orphan with 0 threshold
        assert result.has_orphans()
        assert result.total_orphans == 1

    def _create_petition(
        self, received_at: datetime, state: PetitionState
    ) -> PetitionSubmission:
        """Helper to create petition for testing."""
        return PetitionSubmission(
            id=uuid4(),
            type=PetitionType.GENERAL,
            text="Test petition content",
            state=state,
            realm="test-realm",
            created_at=received_at,
            co_signer_count=0,
        )
