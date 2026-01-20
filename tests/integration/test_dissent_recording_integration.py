"""Integration tests for dissent recording (Story 2B.1, FR-11.8).

Tests the complete dissent recording flow from consensus resolution through
dissent recording, event emission, and retrieval.

Constitutional Constraints Verified:
- FR-11.8: System SHALL record dissent opinions in 2-1 votes
- CT-12: Witnessing creates accountability
- AT-6: Deliberation is collective judgment, minority voice preserved
- NFR-6.5: Audit trail completeness - complete reconstruction possible
- NFR-10.3: Consensus determinism - 100% reproducible
"""

from datetime import datetime, timezone
from uuid import uuid4

import blake3
import pytest
from uuid6 import uuid7

from src.application.services.consensus_resolver_service import ConsensusResolverService
from src.application.services.dissent_recorder_service import DissentRecorderService
from src.domain.events.dissent import DISSENT_RECORDED_EVENT_TYPE, DissentRecordedEvent
from src.domain.models.consensus_result import ConsensusResult, ConsensusStatus
from src.domain.models.deliberation_session import (
    DeliberationOutcome,
    DeliberationSession,
)
from src.domain.models.dissent_record import DissentRecord
from src.infrastructure.stubs.dissent_recorder_stub import (
    DissentRecorderOperation,
    DissentRecorderStub,
)


def _utc_now() -> datetime:
    """Return current UTC time with timezone info."""
    return datetime.now(timezone.utc)


def _compute_rationale_hash(rationale: str) -> bytes:
    """Compute Blake3 hash of rationale text."""
    return blake3.blake3(rationale.encode("utf-8")).digest()


class TestDissentRecordingIntegration:
    """Integration tests for complete dissent recording flow."""

    @pytest.mark.asyncio
    async def test_full_2_1_dissent_flow(self) -> None:
        """Test complete flow: session -> consensus -> dissent record (FR-11.8).

        This test validates the full dissent recording pipeline:
        1. Create deliberation session
        2. Cast votes resulting in 2-1 split
        3. Resolve consensus
        4. Record dissent
        5. Verify retrieval
        """
        # 1. Create session with 3 archons
        archon_ids = (uuid4(), uuid4(), uuid4())
        session = DeliberationSession.create(
            petition_id=uuid7(),
            assigned_archons=archon_ids,
        )

        # 2. Cast 2-1 votes: 2 ACKNOWLEDGE, 1 REFER
        votes = {
            archon_ids[0]: DeliberationOutcome.ACKNOWLEDGE,
            archon_ids[1]: DeliberationOutcome.ACKNOWLEDGE,
            archon_ids[2]: DeliberationOutcome.REFER,  # Dissenter
        }
        session_with_votes = session.with_votes(votes)
        session_complete = session_with_votes.with_outcome()

        # 3. Resolve consensus
        consensus_service = ConsensusResolverService()
        consensus_result = consensus_service.resolve_consensus(session, votes)

        # Verify consensus result
        assert consensus_result.status == ConsensusStatus.ACHIEVED
        assert consensus_result.has_dissent is True
        assert consensus_result.dissent_archon_id == archon_ids[2]
        assert consensus_result.winning_outcome == "ACKNOWLEDGE"

        # 4. Record dissent
        dissent_service = DissentRecorderService()
        dissent_rationale = (
            "The petition should be reviewed by a Knight for proper handling."
        )

        dissent = await dissent_service.record_dissent(
            session=session_complete,
            consensus_result=consensus_result,
            dissent_rationale=dissent_rationale,
        )

        # 5. Verify dissent was recorded
        assert dissent is not None
        assert dissent.session_id == session.session_id
        assert dissent.petition_id == session.petition_id
        assert dissent.dissent_archon_id == archon_ids[2]
        assert dissent.dissent_disposition == DeliberationOutcome.REFER
        assert dissent.majority_disposition == DeliberationOutcome.ACKNOWLEDGE
        assert dissent.dissent_rationale == dissent_rationale
        assert len(dissent.rationale_hash) == 32

        # Verify retrieval by petition
        retrieved = await dissent_service.get_dissent_by_petition(session.petition_id)
        assert retrieved is not None
        assert retrieved.dissent_id == dissent.dissent_id

    @pytest.mark.asyncio
    async def test_unanimous_vote_no_dissent(self) -> None:
        """Test that unanimous 3-0 votes produce no dissent record."""
        archon_ids = (uuid4(), uuid4(), uuid4())
        session = DeliberationSession.create(
            petition_id=uuid7(),
            assigned_archons=archon_ids,
        )

        # All 3 vote ACKNOWLEDGE
        votes = {
            archon_ids[0]: DeliberationOutcome.ACKNOWLEDGE,
            archon_ids[1]: DeliberationOutcome.ACKNOWLEDGE,
            archon_ids[2]: DeliberationOutcome.ACKNOWLEDGE,
        }
        session_with_votes = session.with_votes(votes)
        session_complete = session_with_votes.with_outcome()

        # Resolve consensus
        consensus_service = ConsensusResolverService()
        consensus_result = consensus_service.resolve_consensus(session, votes)

        # Verify unanimous
        assert consensus_result.status == ConsensusStatus.UNANIMOUS
        assert consensus_result.has_dissent is False
        assert consensus_result.dissent_archon_id is None

        # Record dissent (should return None)
        dissent_service = DissentRecorderService()
        dissent = await dissent_service.record_dissent(
            session=session_complete,
            consensus_result=consensus_result,
            dissent_rationale="This should not be stored.",
        )

        assert dissent is None
        assert dissent_service.get_total_dissent_count() == 0

    @pytest.mark.asyncio
    async def test_dissent_event_emission(self) -> None:
        """Test that DissentRecordedEvent is emitted for witnessing (CT-12)."""
        archon_ids = (uuid4(), uuid4(), uuid4())
        session = DeliberationSession.create(
            petition_id=uuid7(),
            assigned_archons=archon_ids,
        )

        votes = {
            archon_ids[0]: DeliberationOutcome.ESCALATE,
            archon_ids[1]: DeliberationOutcome.ESCALATE,
            archon_ids[2]: DeliberationOutcome.ACKNOWLEDGE,  # Dissenter
        }
        session_with_votes = session.with_votes(votes)
        session_complete = session_with_votes.with_outcome()

        # Use stub to capture events
        stub = DissentRecorderStub()
        rationale = "Petition does not warrant escalation to King."

        await stub.record_dissent(
            session=session_complete,
            consensus_result=ConsensusResult(
                session_id=session.session_id,
                petition_id=session.petition_id,
                status=ConsensusStatus.ACHIEVED,
                winning_outcome="ESCALATE",
                vote_distribution={"ESCALATE": 2, "ACKNOWLEDGE": 1},
                majority_archon_ids=(archon_ids[0], archon_ids[1]),
                dissent_archon_id=archon_ids[2],
            ),
            dissent_rationale=rationale,
        )

        # Verify event was emitted
        events = stub.get_emitted_events()
        assert len(events) == 1

        event = events[0]
        assert event.session_id == session.session_id
        assert event.petition_id == session.petition_id
        assert event.dissent_archon_id == archon_ids[2]
        assert event.dissent_disposition == "ACKNOWLEDGE"
        assert event.majority_disposition == "ESCALATE"
        assert event.event_type == DISSENT_RECORDED_EVENT_TYPE

    @pytest.mark.asyncio
    async def test_multiple_archon_dissent_tracking(self) -> None:
        """Test tracking multiple dissents for same archon (AC-6)."""
        # This archon dissents frequently
        frequent_dissenter = uuid4()
        dissent_service = DissentRecorderService()

        # Create 3 different sessions where this archon dissents
        for i in range(3):
            other_archons = (uuid4(), uuid4())
            archon_ids = (other_archons[0], other_archons[1], frequent_dissenter)

            session = DeliberationSession.create(
                petition_id=uuid7(),
                assigned_archons=archon_ids,
            )

            votes = {
                archon_ids[0]: DeliberationOutcome.ACKNOWLEDGE,
                archon_ids[1]: DeliberationOutcome.ACKNOWLEDGE,
                frequent_dissenter: DeliberationOutcome.REFER,  # Always dissents
            }
            session_with_votes = session.with_votes(votes)
            session_complete = session_with_votes.with_outcome()

            consensus_result = ConsensusResult(
                session_id=session.session_id,
                petition_id=session.petition_id,
                status=ConsensusStatus.ACHIEVED,
                winning_outcome="ACKNOWLEDGE",
                vote_distribution={"ACKNOWLEDGE": 2, "REFER": 1},
                majority_archon_ids=(other_archons[0], other_archons[1]),
                dissent_archon_id=frequent_dissenter,
            )

            await dissent_service.record_dissent(
                session=session_complete,
                consensus_result=consensus_result,
                dissent_rationale=f"Dissent rationale {i}",
            )

        # Verify archon has 3 dissents recorded
        dissents = await dissent_service.get_dissents_by_archon(frequent_dissenter)
        assert len(dissents) == 3

        # Verify count method
        count = dissent_service.get_dissent_count_by_archon(frequent_dissenter)
        assert count == 3

    @pytest.mark.asyncio
    async def test_dissent_hash_integrity(self) -> None:
        """Test Blake3 hash integrity for rationale (NFR-6.5)."""
        archon_ids = (uuid4(), uuid4(), uuid4())
        session = DeliberationSession.create(
            petition_id=uuid7(),
            assigned_archons=archon_ids,
        )

        votes = {
            archon_ids[0]: DeliberationOutcome.REFER,
            archon_ids[1]: DeliberationOutcome.REFER,
            archon_ids[2]: DeliberationOutcome.ESCALATE,
        }
        session_with_votes = session.with_votes(votes)
        session_complete = session_with_votes.with_outcome()

        rationale = "This petition warrants immediate King attention."
        expected_hash = _compute_rationale_hash(rationale)

        dissent_service = DissentRecorderService()
        dissent = await dissent_service.record_dissent(
            session=session_complete,
            consensus_result=ConsensusResult(
                session_id=session.session_id,
                petition_id=session.petition_id,
                status=ConsensusStatus.ACHIEVED,
                winning_outcome="REFER",
                vote_distribution={"REFER": 2, "ESCALATE": 1},
                majority_archon_ids=(archon_ids[0], archon_ids[1]),
                dissent_archon_id=archon_ids[2],
            ),
            dissent_rationale=rationale,
        )

        assert dissent is not None
        assert dissent.rationale_hash == expected_hash

        # Verify hash can be verified against stored rationale
        recomputed = _compute_rationale_hash(dissent.dissent_rationale)
        assert recomputed == dissent.rationale_hash


class TestDissentRecordingStubbingPatterns:
    """Integration tests for stub usage patterns in testing."""

    @pytest.mark.asyncio
    async def test_inject_dissent_for_test_setup(self) -> None:
        """Test injecting pre-made dissent records for test setup."""
        stub = DissentRecorderStub()

        # Inject dissent for test scenario
        dissent = DissentRecord(
            dissent_id=uuid7(),
            session_id=uuid7(),
            petition_id=uuid7(),
            dissent_archon_id=uuid4(),
            dissent_disposition=DeliberationOutcome.ESCALATE,
            dissent_rationale="Pre-injected test rationale.",
            rationale_hash=_compute_rationale_hash("Pre-injected test rationale."),
            majority_disposition=DeliberationOutcome.ACKNOWLEDGE,
        )
        stub.inject_dissent(dissent)

        # Test code can now verify behavior with pre-existing dissent
        assert await stub.has_dissent(dissent.session_id) is True
        retrieved = await stub.get_dissent_by_session(dissent.session_id)
        assert retrieved is not None
        assert retrieved.dissent_disposition == DeliberationOutcome.ESCALATE

    @pytest.mark.asyncio
    async def test_operation_tracking_for_verification(self) -> None:
        """Test operation tracking for test verification."""
        stub = DissentRecorderStub()
        petition_id = uuid7()
        archon_id = uuid4()

        # Perform operations
        await stub.get_dissent_by_petition(petition_id)
        await stub.get_dissents_by_archon(archon_id)

        # Verify operations were tracked
        operations = stub.get_operations()
        assert len(operations) == 2

        assert operations[0][0] == DissentRecorderOperation.GET_BY_PETITION
        assert operations[0][1]["petition_id"] == petition_id

        assert operations[1][0] == DissentRecorderOperation.GET_BY_ARCHON
        assert operations[1][1]["archon_id"] == archon_id

    def test_clear_resets_all_state(self) -> None:
        """Test that clear() resets stub for test isolation."""
        stub = DissentRecorderStub()

        # Add some state
        dissent = DissentRecord(
            dissent_id=uuid7(),
            session_id=uuid7(),
            petition_id=uuid7(),
            dissent_archon_id=uuid4(),
            dissent_disposition=DeliberationOutcome.REFER,
            dissent_rationale="Test.",
            rationale_hash=_compute_rationale_hash("Test."),
            majority_disposition=DeliberationOutcome.ACKNOWLEDGE,
        )
        stub.inject_dissent(dissent)

        assert stub.get_dissent_count() == 1

        # Clear for next test
        stub.clear()

        assert stub.get_dissent_count() == 0
        assert stub.get_operations() == []
        assert stub.get_emitted_events() == []


class TestDissentEventSerialization:
    """Tests for dissent event serialization (CT-12 witness compatibility)."""

    def test_event_to_dict_contains_all_witness_fields(self) -> None:
        """Test that event serialization contains all fields for witnessing."""
        event = DissentRecordedEvent(
            event_id=uuid7(),
            session_id=uuid7(),
            petition_id=uuid7(),
            dissent_archon_id=uuid4(),
            dissent_disposition="REFER",
            rationale_hash="a" * 64,  # Valid hex
            majority_disposition="ACKNOWLEDGE",
            recorded_at=_utc_now(),
        )

        data = event.to_dict()

        # Required fields for witness record (CT-12)
        assert "event_type" in data
        assert "event_id" in data
        assert "session_id" in data
        assert "petition_id" in data
        assert "dissent_archon_id" in data
        assert "dissent_disposition" in data
        assert "rationale_hash" in data
        assert "majority_disposition" in data
        assert "recorded_at" in data
        assert "schema_version" in data

        # Verify types
        assert data["event_type"] == DISSENT_RECORDED_EVENT_TYPE
        assert isinstance(data["event_id"], str)
        assert isinstance(data["schema_version"], int)

    def test_event_to_dict_timestamps_are_iso_format(self) -> None:
        """Test that timestamps serialize to ISO format for portability."""
        recorded_at = _utc_now()
        event = DissentRecordedEvent(
            event_id=uuid7(),
            session_id=uuid7(),
            petition_id=uuid7(),
            dissent_archon_id=uuid4(),
            dissent_disposition="ESCALATE",
            rationale_hash="b" * 64,
            majority_disposition="REFER",
            recorded_at=recorded_at,
        )

        data = event.to_dict()

        # Should be ISO format string
        assert data["recorded_at"] == recorded_at.isoformat()
        assert "T" in data["recorded_at"]  # ISO format includes T separator


class TestDissentRecordDomainIntegration:
    """Tests for DissentRecord domain model integration."""

    def test_dissent_record_immutability(self) -> None:
        """Test that DissentRecord is immutable (frozen dataclass)."""
        dissent = DissentRecord(
            dissent_id=uuid7(),
            session_id=uuid7(),
            petition_id=uuid7(),
            dissent_archon_id=uuid4(),
            dissent_disposition=DeliberationOutcome.REFER,
            dissent_rationale="Test rationale.",
            rationale_hash=_compute_rationale_hash("Test rationale."),
            majority_disposition=DeliberationOutcome.ACKNOWLEDGE,
        )

        with pytest.raises(AttributeError):
            dissent.dissent_rationale = "Modified"  # type: ignore[misc]

    def test_dissent_record_to_dict_serialization(self) -> None:
        """Test DissentRecord serializes to dictionary correctly."""
        dissent_id = uuid7()
        session_id = uuid7()
        petition_id = uuid7()
        archon_id = uuid4()
        rationale = "Test rationale for serialization."
        rationale_hash = _compute_rationale_hash(rationale)

        dissent = DissentRecord(
            dissent_id=dissent_id,
            session_id=session_id,
            petition_id=petition_id,
            dissent_archon_id=archon_id,
            dissent_disposition=DeliberationOutcome.ESCALATE,
            dissent_rationale=rationale,
            rationale_hash=rationale_hash,
            majority_disposition=DeliberationOutcome.REFER,
        )

        data = dissent.to_dict()

        assert data["dissent_id"] == str(dissent_id)
        assert data["session_id"] == str(session_id)
        assert data["petition_id"] == str(petition_id)
        assert data["dissent_archon_id"] == str(archon_id)
        assert data["dissent_disposition"] == "ESCALATE"
        assert data["majority_disposition"] == "REFER"
        assert data["rationale_hash"] == rationale_hash.hex()
        assert "recorded_at" in data
