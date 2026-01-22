"""Tests for orphan petition reprocessing service (Story 8.3, FR-8.5).

Constitutional Requirements:
- FR-8.5: Operators can manually trigger re-processing
- CT-12: All reprocessing actions must be witnessed
- CT-11: Manual interventions must be logged

Test Coverage:
- Manual reprocessing of valid orphans
- Event emission for reprocessing actions
- Validation of petition state (RECEIVED only)
- Error handling for missing petitions
- Deliberation initiation success/failure
"""

from datetime import datetime, timezone
from unittest.mock import Mock
from uuid import UUID, uuid4

import pytest

from src.application.services.orphan_petition_reprocessing_service import (
    OrphanPetitionReprocessingService,
)
from src.domain.events.orphan_petition import (
    ORPHAN_PETITION_REPROCESSING_TRIGGERED_EVENT_TYPE,
)
from src.domain.models.petition_submission import PetitionState, PetitionSubmission, PetitionType


class TestOrphanReprocessing:
    """Test orphan petition reprocessing logic."""

    def test_successful_reprocessing_of_valid_orphan(self):
        """Test successful reprocessing of petition in RECEIVED state (FR-8.5)."""
        # Setup
        petition_id = uuid4()
        petition = self._create_petition(
            petition_id=petition_id, state=PetitionState.RECEIVED
        )

        petition_repo = Mock()
        petition_repo.find_by_id.return_value = petition

        event_writer = Mock()
        deliberation_orchestrator = Mock()

        service = OrphanPetitionReprocessingService(
            petition_repository=petition_repo,
            event_writer=event_writer,
            deliberation_orchestrator=deliberation_orchestrator,
        )

        # Execute
        result = service.reprocess_orphans(
            petition_ids=[petition_id],
            triggered_by="operator-123",
            reason="Manual reprocessing after detection",
        )

        # Verify success
        assert petition_id in result["success"]
        assert len(result["failed"]) == 0

        # Verify event emitted (CT-12)
        event_writer.write_event.assert_called_once()
        call_args = event_writer.write_event.call_args
        assert (
            call_args[1]["event_type"]
            == ORPHAN_PETITION_REPROCESSING_TRIGGERED_EVENT_TYPE
        )

        # Verify deliberation initiated
        deliberation_orchestrator.initiate_deliberation.assert_called_once_with(
            petition_id
        )

    def test_multiple_orphans_reprocessing(self):
        """Test reprocessing multiple orphaned petitions (FR-8.5)."""
        # Setup: 3 petitions in RECEIVED state
        petition_ids = [uuid4() for _ in range(3)]
        petitions = [
            self._create_petition(petition_id=pid, state=PetitionState.RECEIVED)
            for pid in petition_ids
        ]

        petition_repo = Mock()
        petition_repo.find_by_id.side_effect = petitions

        event_writer = Mock()
        deliberation_orchestrator = Mock()

        service = OrphanPetitionReprocessingService(
            petition_repository=petition_repo,
            event_writer=event_writer,
            deliberation_orchestrator=deliberation_orchestrator,
        )

        # Execute
        result = service.reprocess_orphans(
            petition_ids=petition_ids,
            triggered_by="operator-123",
            reason="Batch reprocessing",
        )

        # Verify all succeeded
        assert len(result["success"]) == 3
        assert len(result["failed"]) == 0
        assert all(pid in result["success"] for pid in petition_ids)

        # Verify event emitted with all 3 IDs
        event_writer.write_event.assert_called_once()
        call_args = event_writer.write_event.call_args
        payload = call_args[1]["payload"]
        assert len(payload.petition_ids) == 3

        # Verify deliberation initiated for all 3
        assert deliberation_orchestrator.initiate_deliberation.call_count == 3

    def test_rejects_petition_not_in_received_state(self):
        """Test reprocessing rejected for non-RECEIVED petitions."""
        # Setup: Petition in DELIBERATING state
        petition_id = uuid4()
        petition = self._create_petition(
            petition_id=petition_id, state=PetitionState.DELIBERATING
        )

        petition_repo = Mock()
        petition_repo.find_by_id.return_value = petition

        event_writer = Mock()
        deliberation_orchestrator = Mock()

        service = OrphanPetitionReprocessingService(
            petition_repository=petition_repo,
            event_writer=event_writer,
            deliberation_orchestrator=deliberation_orchestrator,
        )

        # Execute
        result = service.reprocess_orphans(
            petition_ids=[petition_id],
            triggered_by="operator-123",
            reason="Test reprocessing",
        )

        # Verify rejected
        assert petition_id in result["failed"]
        assert len(result["success"]) == 0

        # Verify no event emitted (no valid petitions)
        event_writer.write_event.assert_not_called()

        # Verify no deliberation initiated
        deliberation_orchestrator.initiate_deliberation.assert_not_called()

    def test_handles_missing_petition(self):
        """Test reprocessing handles missing petitions gracefully."""
        # Setup: Petition does not exist
        petition_id = uuid4()

        petition_repo = Mock()
        petition_repo.find_by_id.return_value = None

        event_writer = Mock()
        deliberation_orchestrator = Mock()

        service = OrphanPetitionReprocessingService(
            petition_repository=petition_repo,
            event_writer=event_writer,
            deliberation_orchestrator=deliberation_orchestrator,
        )

        # Execute
        result = service.reprocess_orphans(
            petition_ids=[petition_id],
            triggered_by="operator-123",
            reason="Test reprocessing",
        )

        # Verify failed
        assert petition_id in result["failed"]
        assert len(result["success"]) == 0

        # Verify no event emitted
        event_writer.write_event.assert_not_called()

        # Verify no deliberation initiated
        deliberation_orchestrator.initiate_deliberation.assert_not_called()

    def test_handles_deliberation_initiation_failure(self):
        """Test reprocessing handles deliberation initiation failures."""
        # Setup: Valid petition but deliberation fails
        petition_id = uuid4()
        petition = self._create_petition(
            petition_id=petition_id, state=PetitionState.RECEIVED
        )

        petition_repo = Mock()
        petition_repo.find_by_id.return_value = petition

        event_writer = Mock()
        deliberation_orchestrator = Mock()
        deliberation_orchestrator.initiate_deliberation.side_effect = Exception(
            "Deliberation service unavailable"
        )

        service = OrphanPetitionReprocessingService(
            petition_repository=petition_repo,
            event_writer=event_writer,
            deliberation_orchestrator=deliberation_orchestrator,
        )

        # Execute
        result = service.reprocess_orphans(
            petition_ids=[petition_id],
            triggered_by="operator-123",
            reason="Test reprocessing",
        )

        # Verify failed
        assert petition_id in result["failed"]
        assert len(result["success"]) == 0

        # Verify event was emitted (CT-12) even though deliberation failed
        event_writer.write_event.assert_called_once()

    def test_partial_success_scenario(self):
        """Test reprocessing with mix of success and failure."""
        # Setup: 3 petitions, 1 RECEIVED, 1 DELIBERATING, 1 missing
        pid1, pid2, pid3 = uuid4(), uuid4(), uuid4()

        petition1 = self._create_petition(petition_id=pid1, state=PetitionState.RECEIVED)
        petition2 = self._create_petition(
            petition_id=pid2, state=PetitionState.DELIBERATING
        )

        petition_repo = Mock()
        petition_repo.find_by_id.side_effect = [petition1, petition2, None]

        event_writer = Mock()
        deliberation_orchestrator = Mock()

        service = OrphanPetitionReprocessingService(
            petition_repository=petition_repo,
            event_writer=event_writer,
            deliberation_orchestrator=deliberation_orchestrator,
        )

        # Execute
        result = service.reprocess_orphans(
            petition_ids=[pid1, pid2, pid3],
            triggered_by="operator-123",
            reason="Batch reprocessing",
        )

        # Verify: 1 success, 2 failed
        assert pid1 in result["success"]
        assert pid2 in result["failed"]
        assert pid3 in result["failed"]
        assert len(result["success"]) == 1
        assert len(result["failed"]) == 2

        # Verify event emitted only for valid petition
        event_writer.write_event.assert_called_once()
        call_args = event_writer.write_event.call_args
        payload = call_args[1]["payload"]
        assert len(payload.petition_ids) == 1
        assert payload.petition_ids[0] == pid1

    def test_empty_petition_list_raises_error(self):
        """Test reprocessing with empty petition list raises ValueError."""
        petition_repo = Mock()
        event_writer = Mock()
        deliberation_orchestrator = Mock()

        service = OrphanPetitionReprocessingService(
            petition_repository=petition_repo,
            event_writer=event_writer,
            deliberation_orchestrator=deliberation_orchestrator,
        )

        # Execute & Verify
        with pytest.raises(ValueError, match="petition_ids cannot be empty"):
            service.reprocess_orphans(
                petition_ids=[],
                triggered_by="operator-123",
                reason="Test reprocessing",
            )

    def test_event_payload_structure(self):
        """Test event payload contains all required fields (CT-12)."""
        # Setup
        petition_id = uuid4()
        petition = self._create_petition(
            petition_id=petition_id, state=PetitionState.RECEIVED
        )

        petition_repo = Mock()
        petition_repo.find_by_id.return_value = petition

        event_writer = Mock()
        deliberation_orchestrator = Mock()

        service = OrphanPetitionReprocessingService(
            petition_repository=petition_repo,
            event_writer=event_writer,
            deliberation_orchestrator=deliberation_orchestrator,
        )

        # Execute
        service.reprocess_orphans(
            petition_ids=[petition_id],
            triggered_by="operator-123",
            reason="Manual reprocessing after detection",
        )

        # Verify event payload structure
        call_args = event_writer.write_event.call_args
        payload = call_args[1]["payload"]

        assert payload.triggered_by == "operator-123"
        assert payload.reason == "Manual reprocessing after detection"
        assert len(payload.petition_ids) == 1
        assert payload.petition_ids[0] == petition_id
        assert isinstance(payload.triggered_at, datetime)

    def _create_petition(
        self, petition_id: UUID, state: PetitionState
    ) -> PetitionSubmission:
        """Helper to create petition for testing."""
        return PetitionSubmission(
            id=petition_id,
            type=PetitionType.GENERAL,
            text="Test petition content",
            state=state,
            realm="test-realm",
            co_signer_count=0,
        )
