"""Integration tests for audit trail reconstruction (Story 2B.6).

These tests verify that the audit trail reconstruction system works
correctly with the stub implementation, simulating real-world scenarios.

Constitutional Constraints Tested:
- FR-11.12: Complete deliberation transcript preservation for audit
- NFR-6.5: Full state history reconstruction from event log
- CT-12: Verify unbroken chain of accountability
- CT-14: Every claim terminates in visible, witnessed fate
- NFR-10.4: 100% witness completeness
"""

from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from uuid6 import uuid7

from src.application.ports.audit_trail_reconstructor import SessionNotFoundError
from src.domain.models.audit_timeline import (
    BLAKE3_HASH_SIZE,
    TerminationReason,
    TimelineEvent,
    WitnessChainVerification,
)
from src.infrastructure.stubs.audit_trail_reconstructor_stub import (
    AuditTrailReconstructorStub,
)


def _utc_now() -> datetime:
    """Return current UTC time."""
    return datetime.now(timezone.utc)


def _make_witness_hash(seed: int = 1) -> bytes:
    """Create a valid 32-byte Blake3 hash for testing."""
    return bytes([seed % 256] * BLAKE3_HASH_SIZE)


def _make_timeline_event(
    event_type: str = "TestEvent",
    occurred_at: datetime | None = None,
    payload: dict[str, Any] | None = None,
    witness_hash: bytes | None = None,
) -> TimelineEvent:
    """Create a TimelineEvent for testing."""
    return TimelineEvent(
        event_id=uuid7(),
        event_type=event_type,
        occurred_at=occurred_at or _utc_now(),
        payload=payload or {},
        witness_hash=witness_hash,
    )


@pytest.mark.integration
class TestAuditTrailReconstructionIntegration:
    """Integration tests for complete audit trail reconstruction scenarios."""

    @pytest.mark.asyncio
    async def test_reconstruct_normal_deliberation_timeline(self) -> None:
        """Test FR-11.12: Reconstruct a normal deliberation with all phases.

        Scenario: A petition goes through all phases and reaches ACKNOWLEDGE.
        """
        stub = AuditTrailReconstructorStub()

        # Setup: Create a complete deliberation session
        session_id = uuid7()
        petition_id = uuid7()
        archons = (uuid7(), uuid7(), uuid7())
        started = _utc_now()
        completed = started + timedelta(minutes=10)

        stub.inject_session(
            session_id=session_id,
            petition_id=petition_id,
            assigned_archons=archons,
            started_at=started,
            completed_at=completed,
            outcome="ACKNOWLEDGE",
            termination_reason=TerminationReason.NORMAL,
            transcripts={
                "ASSESS": "All archons assessed the petition and found it compliant.",
                "POSITION": "Archon positions recorded.",
                "CROSS_EXAMINE": "Cross-examination completed.",
                "VOTE": "Final vote: 3-0 ACKNOWLEDGE.",
            },
            witness_chain_valid=True,
        )

        # Inject chronological events
        now = started
        events = [
            _make_timeline_event(
                event_type="SessionStarted",
                occurred_at=now,
                payload={"archons": [str(a) for a in archons]},
                witness_hash=_make_witness_hash(1),
            ),
            _make_timeline_event(
                event_type="PhaseWitnessed",
                occurred_at=now + timedelta(minutes=2),
                payload={"phase": "ASSESS"},
                witness_hash=_make_witness_hash(2),
            ),
            _make_timeline_event(
                event_type="PhaseWitnessed",
                occurred_at=now + timedelta(minutes=4),
                payload={"phase": "POSITION"},
                witness_hash=_make_witness_hash(3),
            ),
            _make_timeline_event(
                event_type="PhaseWitnessed",
                occurred_at=now + timedelta(minutes=6),
                payload={"phase": "CROSS_EXAMINE"},
                witness_hash=_make_witness_hash(4),
            ),
            _make_timeline_event(
                event_type="VoteRecorded",
                occurred_at=now + timedelta(minutes=8),
                payload={"votes": {"ACKNOWLEDGE": 3}},
                witness_hash=_make_witness_hash(5),
            ),
            _make_timeline_event(
                event_type="SessionCompleted",
                occurred_at=completed,
                payload={"outcome": "ACKNOWLEDGE"},
                witness_hash=_make_witness_hash(6),
            ),
        ]
        stub.inject_events(session_id, events)

        # Act: Reconstruct the timeline
        timeline = await stub.reconstruct_timeline(session_id)

        # Assert: FR-11.12 - Complete transcript preservation
        assert timeline.session_id == session_id
        assert timeline.petition_id == petition_id
        assert timeline.assigned_archons == archons
        assert timeline.outcome == "ACKNOWLEDGE"
        assert timeline.termination_reason == TerminationReason.NORMAL
        assert timeline.is_normal_completion is True
        assert timeline.was_forced_escalation is False

        # Verify all events are present and ordered
        assert timeline.event_count == 6
        event_types = [e.event_type for e in timeline.events]
        assert event_types == [
            "SessionStarted",
            "PhaseWitnessed",
            "PhaseWitnessed",
            "PhaseWitnessed",
            "VoteRecorded",
            "SessionCompleted",
        ]

        # Verify transcripts are preserved
        assert len(timeline.transcripts) == 4
        assert "ASSESS" in timeline.transcripts
        assert "VOTE" in timeline.transcripts

        # Verify timing
        assert timeline.duration_seconds is not None
        assert timeline.duration_seconds == 600.0  # 10 minutes

    @pytest.mark.asyncio
    async def test_reconstruct_deliberation_with_dissent(self) -> None:
        """Test FR-11.7: Reconstruct a 2-1 split decision with dissent recorded.

        Scenario: Deliberation ends with one archon dissenting.
        """
        stub = AuditTrailReconstructorStub()

        session_id = uuid7()
        dissenter_id = uuid7()
        archons = (uuid7(), uuid7(), dissenter_id)

        dissent_record = {
            "dissenter_id": str(dissenter_id),
            "dissent_reason": "Constitutional concern under CT-5",
            "original_vote": "REFER",
            "final_outcome": "ACKNOWLEDGE",
            "recorded_at": _utc_now().isoformat(),
        }

        stub.inject_session(
            session_id=session_id,
            petition_id=uuid7(),
            assigned_archons=archons,
            outcome="ACKNOWLEDGE",
            termination_reason=TerminationReason.NORMAL,
            dissent_record=dissent_record,
            witness_chain_valid=True,
        )

        # Act
        timeline = await stub.reconstruct_timeline(session_id)

        # Assert: Dissent is preserved in timeline
        assert timeline.has_dissent is True
        assert timeline.dissent_record is not None
        assert timeline.dissent_record["dissenter_id"] == str(dissenter_id)
        assert "CT-5" in timeline.dissent_record["dissent_reason"]

    @pytest.mark.asyncio
    async def test_reconstruct_timeout_forced_escalation(self) -> None:
        """Test FR-11.9/HC-7: Reconstruct deliberation that timed out.

        Scenario: Deliberation exceeds time limit and forces ESCALATE.
        """
        stub = AuditTrailReconstructorStub()

        session_id = uuid7()
        started = _utc_now()
        # Timed out after exceeding limit
        completed = started + timedelta(minutes=30)

        stub.inject_session(
            session_id=session_id,
            petition_id=uuid7(),
            assigned_archons=(uuid7(), uuid7(), uuid7()),
            started_at=started,
            completed_at=completed,
            outcome="ESCALATE",
            termination_reason=TerminationReason.TIMEOUT,
            witness_chain_valid=True,
        )

        # Add timeout event
        stub.inject_event(
            session_id,
            _make_timeline_event(
                event_type="DeliberationTimeout",
                occurred_at=completed,
                payload={"reason": "Exceeded maximum deliberation time"},
                witness_hash=_make_witness_hash(1),
            ),
        )

        # Act
        timeline = await stub.reconstruct_timeline(session_id)

        # Assert: Timeout is properly recorded
        assert timeline.outcome == "ESCALATE"
        assert timeline.termination_reason == TerminationReason.TIMEOUT
        assert timeline.was_forced_escalation is True
        assert timeline.is_normal_completion is False

        # Verify timeout event is present
        timeout_events = timeline.get_events_by_type("DeliberationTimeout")
        assert len(timeout_events) == 1
        assert "Exceeded maximum" in timeout_events[0].payload["reason"]

    @pytest.mark.asyncio
    async def test_reconstruct_deadlock_forced_escalation(self) -> None:
        """Test FR-11.10/CT-11: Reconstruct deliberation that deadlocked.

        Scenario: Deliberation reaches max rounds without consensus.
        """
        stub = AuditTrailReconstructorStub()

        session_id = uuid7()

        stub.inject_session(
            session_id=session_id,
            petition_id=uuid7(),
            assigned_archons=(uuid7(), uuid7(), uuid7()),
            outcome="ESCALATE",
            termination_reason=TerminationReason.DEADLOCK,
            witness_chain_valid=True,
        )

        # Add deadlock event
        stub.inject_event(
            session_id,
            _make_timeline_event(
                event_type="DeadlockDetected",
                payload={"rounds_attempted": 7, "max_rounds": 7},
                witness_hash=_make_witness_hash(1),
            ),
        )

        # Act
        timeline = await stub.reconstruct_timeline(session_id)

        # Assert: Deadlock is properly recorded
        assert timeline.outcome == "ESCALATE"
        assert timeline.termination_reason == TerminationReason.DEADLOCK
        assert timeline.was_forced_escalation is True

        deadlock_events = timeline.get_events_by_type("DeadlockDetected")
        assert len(deadlock_events) == 1
        assert deadlock_events[0].payload["rounds_attempted"] == 7

    @pytest.mark.asyncio
    async def test_reconstruct_with_archon_substitutions(self) -> None:
        """Test Story 2B.4: Reconstruct deliberation with archon substitutions.

        Scenario: An archon failed and was substituted mid-deliberation.
        """
        stub = AuditTrailReconstructorStub()

        session_id = uuid7()
        original_archon = uuid7()
        replacement_archon = uuid7()

        substitutions = (
            {
                "original_archon_id": str(original_archon),
                "replacement_archon_id": str(replacement_archon),
                "reason": "UNRESPONSIVE",
                "phase_at_substitution": "POSITION",
                "substituted_at": _utc_now().isoformat(),
            },
        )

        stub.inject_session(
            session_id=session_id,
            petition_id=uuid7(),
            assigned_archons=(uuid7(), uuid7(), replacement_archon),
            outcome="ACKNOWLEDGE",
            termination_reason=TerminationReason.NORMAL,
            substitutions=substitutions,
            witness_chain_valid=True,
        )

        # Add substitution event
        stub.inject_event(
            session_id,
            _make_timeline_event(
                event_type="ArchonSubstituted",
                payload={
                    "original": str(original_archon),
                    "replacement": str(replacement_archon),
                },
                witness_hash=_make_witness_hash(1),
            ),
        )

        # Act
        timeline = await stub.reconstruct_timeline(session_id)

        # Assert: Substitution is recorded
        assert timeline.has_substitutions is True
        assert len(timeline.substitutions) == 1
        assert timeline.substitutions[0]["original_archon_id"] == str(original_archon)
        assert timeline.substitutions[0]["replacement_archon_id"] == str(
            replacement_archon
        )

        sub_events = timeline.get_events_by_type("ArchonSubstituted")
        assert len(sub_events) == 1

    @pytest.mark.asyncio
    async def test_reconstruct_abort_due_to_multiple_failures(self) -> None:
        """Test Story 2B.4 AC-8: Reconstruct deliberation aborted due to failures.

        Scenario: More than one archon failed, triggering abort.
        """
        stub = AuditTrailReconstructorStub()

        session_id = uuid7()

        stub.inject_session(
            session_id=session_id,
            petition_id=uuid7(),
            assigned_archons=(uuid7(), uuid7(), uuid7()),
            outcome="ESCALATE",
            termination_reason=TerminationReason.ABORT,
            witness_chain_valid=True,
        )

        # Add abort event
        stub.inject_event(
            session_id,
            _make_timeline_event(
                event_type="DeliberationAborted",
                payload={
                    "reason": "Multiple archon failures",
                    "failed_archon_count": 2,
                },
                witness_hash=_make_witness_hash(1),
            ),
        )

        # Act
        timeline = await stub.reconstruct_timeline(session_id)

        # Assert: Abort is properly recorded
        assert timeline.outcome == "ESCALATE"
        assert timeline.termination_reason == TerminationReason.ABORT
        assert timeline.was_forced_escalation is True

        abort_events = timeline.get_events_by_type("DeliberationAborted")
        assert len(abort_events) == 1
        assert abort_events[0].payload["failed_archon_count"] == 2


@pytest.mark.integration
class TestWitnessChainVerificationIntegration:
    """Integration tests for witness chain verification per CT-12."""

    @pytest.mark.asyncio
    async def test_verify_valid_witness_chain(self) -> None:
        """Test CT-12: Valid witness chain passes verification.

        Scenario: All events have valid witness hashes and chain links.
        """
        stub = AuditTrailReconstructorStub()

        session_id = uuid7()
        stub.inject_session(
            session_id=session_id,
            petition_id=uuid7(),
            assigned_archons=(uuid7(), uuid7(), uuid7()),
            witness_chain_valid=True,
        )

        # Add witnessed events
        now = _utc_now()
        for i in range(5):
            stub.inject_event(
                session_id,
                _make_timeline_event(
                    event_type=f"Event{i}",
                    occurred_at=now + timedelta(minutes=i),
                    witness_hash=_make_witness_hash(i + 1),
                ),
            )

        # Act
        verification = await stub.verify_witness_chain(session_id)

        # Assert: Chain is valid
        assert verification.is_valid is True
        assert verification.broken_links == ()
        assert verification.missing_transcripts == ()
        assert verification.integrity_failures == ()
        assert verification.verified_events == 5
        assert verification.total_events == 5
        assert verification.verification_coverage == 1.0

    @pytest.mark.asyncio
    async def test_verify_broken_witness_chain(self) -> None:
        """Test CT-12: Broken witness chain fails verification.

        Scenario: Chain has a broken link between events.
        """
        stub = AuditTrailReconstructorStub()

        session_id = uuid7()
        stub.inject_session(
            session_id=session_id,
            petition_id=uuid7(),
            assigned_archons=(uuid7(), uuid7(), uuid7()),
        )

        # Inject a failing verification result
        event1_id = uuid7()
        event2_id = uuid7()
        broken_verification = WitnessChainVerification(
            is_valid=False,
            broken_links=((event1_id, event2_id),),
            missing_transcripts=(),
            integrity_failures=(),
            verified_events=4,
            total_events=5,
        )
        stub.inject_verification_result(session_id, broken_verification)

        # Act
        verification = await stub.verify_witness_chain(session_id)

        # Assert: Chain verification fails
        assert verification.is_valid is False
        assert verification.has_broken_links is True
        assert len(verification.broken_links) == 1
        assert verification.verified_events == 4
        assert verification.total_events == 5
        assert verification.verification_coverage == 0.8

    @pytest.mark.asyncio
    async def test_verify_missing_transcripts(self) -> None:
        """Test NFR-10.4: Detect missing transcripts in verification.

        Scenario: Some transcript hashes don't exist in store.
        """
        stub = AuditTrailReconstructorStub()

        session_id = uuid7()
        stub.inject_session(
            session_id=session_id,
            petition_id=uuid7(),
            assigned_archons=(uuid7(), uuid7(), uuid7()),
        )

        # Inject verification with missing transcripts
        missing_hash = _make_witness_hash(99)
        verification_result = WitnessChainVerification(
            is_valid=False,
            broken_links=(),
            missing_transcripts=(missing_hash,),
            integrity_failures=(),
            verified_events=3,
            total_events=4,
        )
        stub.inject_verification_result(session_id, verification_result)

        # Act
        verification = await stub.verify_witness_chain(session_id)

        # Assert: Missing transcript detected
        assert verification.is_valid is False
        assert verification.has_missing_transcripts is True
        assert len(verification.missing_transcripts) == 1
        assert verification.missing_transcripts[0] == missing_hash

    @pytest.mark.asyncio
    async def test_verify_transcript_integrity_failure(self) -> None:
        """Test NFR-10.4: Detect transcript integrity failures.

        Scenario: Transcript content doesn't match stored hash.
        """
        stub = AuditTrailReconstructorStub()

        session_id = uuid7()
        stub.inject_session(
            session_id=session_id,
            petition_id=uuid7(),
            assigned_archons=(uuid7(), uuid7(), uuid7()),
        )

        # Inject verification with integrity failure
        corrupted_hash = _make_witness_hash(42)
        verification_result = WitnessChainVerification(
            is_valid=False,
            broken_links=(),
            missing_transcripts=(),
            integrity_failures=(corrupted_hash,),
            verified_events=2,
            total_events=3,
        )
        stub.inject_verification_result(session_id, verification_result)

        # Act
        verification = await stub.verify_witness_chain(session_id)

        # Assert: Integrity failure detected
        assert verification.is_valid is False
        assert verification.has_integrity_failures is True
        assert len(verification.integrity_failures) == 1


@pytest.mark.integration
class TestSessionEventsIntegration:
    """Integration tests for session event retrieval."""

    @pytest.mark.asyncio
    async def test_get_events_for_complete_deliberation(self) -> None:
        """Test NFR-6.5: Get all events for state reconstruction.

        Scenario: Retrieve all events from a complete deliberation.
        """
        stub = AuditTrailReconstructorStub()

        session_id = uuid7()
        stub.inject_session(
            session_id=session_id,
            petition_id=uuid7(),
            assigned_archons=(uuid7(), uuid7(), uuid7()),
        )

        # Add various event types
        now = _utc_now()
        event_types = [
            "SessionStarted",
            "PhaseWitnessed",
            "PhaseWitnessed",
            "DissentRecorded",
            "VoteRecorded",
            "SessionCompleted",
        ]

        for i, event_type in enumerate(event_types):
            stub.inject_event(
                session_id,
                _make_timeline_event(
                    event_type=event_type,
                    occurred_at=now + timedelta(minutes=i),
                    witness_hash=_make_witness_hash(i),
                ),
            )

        # Act
        events = await stub.get_session_events(session_id)

        # Assert: All events returned in order
        assert len(events) == 6
        returned_types = [e.event_type for e in events]
        assert returned_types == event_types

    @pytest.mark.asyncio
    async def test_get_events_not_found_raises(self) -> None:
        """Test: Getting events for non-existent session raises error."""
        stub = AuditTrailReconstructorStub()

        with pytest.raises(SessionNotFoundError) as exc_info:
            await stub.get_session_events(uuid7())

        assert exc_info.value.session_id is not None


@pytest.mark.integration
class TestAuditTrailEdgeCases:
    """Integration tests for edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_reconstruct_session_with_no_events(self) -> None:
        """Edge case: Session exists but has no events yet."""
        stub = AuditTrailReconstructorStub()

        session_id = uuid7()
        stub.inject_session(
            session_id=session_id,
            petition_id=uuid7(),
            assigned_archons=(uuid7(), uuid7(), uuid7()),
        )

        # Act: Reconstruct with no events
        timeline = await stub.reconstruct_timeline(session_id)

        # Assert: Empty events tuple
        assert timeline.event_count == 0
        assert timeline.events == ()

    @pytest.mark.asyncio
    async def test_reconstruct_session_still_in_progress(self) -> None:
        """Edge case: Session still in progress (no completed_at)."""
        stub = AuditTrailReconstructorStub()

        session_id = uuid7()
        started = _utc_now()

        stub.inject_session(
            session_id=session_id,
            petition_id=uuid7(),
            assigned_archons=(uuid7(), uuid7(), uuid7()),
            started_at=started,
            completed_at=None,  # Still in progress
            outcome="ESCALATE",  # Default outcome
        )

        # Act
        timeline = await stub.reconstruct_timeline(session_id)

        # Assert: Timeline valid but incomplete
        assert timeline.completed_at is None
        assert timeline.duration_seconds is None

    @pytest.mark.asyncio
    async def test_multiple_sessions_independent(self) -> None:
        """Edge case: Multiple sessions don't interfere with each other."""
        stub = AuditTrailReconstructorStub()

        # Create two independent sessions
        session1 = uuid7()
        session2 = uuid7()

        stub.inject_session(
            session_id=session1,
            petition_id=uuid7(),
            assigned_archons=(uuid7(), uuid7(), uuid7()),
            outcome="ACKNOWLEDGE",
        )
        stub.inject_session(
            session_id=session2,
            petition_id=uuid7(),
            assigned_archons=(uuid7(), uuid7(), uuid7()),
            outcome="REFER",
        )

        # Add events to each
        stub.inject_event(session1, _make_timeline_event(event_type="Event1"))
        stub.inject_event(session1, _make_timeline_event(event_type="Event2"))
        stub.inject_event(session2, _make_timeline_event(event_type="EventA"))

        # Act
        timeline1 = await stub.reconstruct_timeline(session1)
        timeline2 = await stub.reconstruct_timeline(session2)

        # Assert: Sessions are independent
        assert timeline1.outcome == "ACKNOWLEDGE"
        assert timeline2.outcome == "REFER"
        assert timeline1.event_count == 2
        assert timeline2.event_count == 1

    @pytest.mark.asyncio
    async def test_clear_and_reuse_stub(self) -> None:
        """Edge case: Stub can be cleared and reused."""
        stub = AuditTrailReconstructorStub()

        # Use the stub
        session_id = uuid7()
        stub.inject_session(
            session_id=session_id,
            petition_id=uuid7(),
            assigned_archons=(uuid7(), uuid7(), uuid7()),
        )
        await stub.reconstruct_timeline(session_id)

        # Clear
        stub.clear()

        # Assert: Everything is reset
        assert stub.get_session_count() == 0
        assert stub.get_reconstruct_call_count() == 0

        # Can reuse
        new_session_id = uuid7()
        stub.inject_session(
            session_id=new_session_id,
            petition_id=uuid7(),
            assigned_archons=(uuid7(), uuid7(), uuid7()),
        )
        timeline = await stub.reconstruct_timeline(new_session_id)
        assert timeline.session_id == new_session_id
