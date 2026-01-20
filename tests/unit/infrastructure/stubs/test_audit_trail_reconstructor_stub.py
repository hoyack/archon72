"""Unit tests for AuditTrailReconstructorStub (Story 2B.6).

Tests verify that the stub correctly:
- Stores and retrieves sessions and events
- Tracks method calls for test assertions
- Raises appropriate errors for missing sessions
- Supports injected verification results

Constitutional Constraints Tested:
- FR-11.12: Complete deliberation transcript preservation for audit
- NFR-6.5: Full state history reconstruction from event log
- CT-12: Verify unbroken chain of accountability
"""

from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from uuid6 import uuid7

from src.application.ports.audit_trail_reconstructor import SessionNotFoundError
from src.domain.models.audit_timeline import (
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


def _make_witness_hash() -> bytes:
    """Create a valid 32-byte Blake3 hash for testing."""
    return b"\x01" * 32


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


class TestAuditTrailReconstructorStubInit:
    """Tests for stub initialization."""

    def test_init_creates_empty_storage(self) -> None:
        """Stub initializes with empty storage."""
        stub = AuditTrailReconstructorStub()

        assert stub.get_session_count() == 0
        assert stub.get_reconstruct_call_count() == 0
        assert stub.get_verify_call_count() == 0
        assert stub.get_events_call_count() == 0


class TestInjectSession:
    """Tests for inject_session method."""

    def test_inject_session_stores_basic_data(self) -> None:
        """Injecting a session stores it in the stub."""
        stub = AuditTrailReconstructorStub()
        session_id = uuid7()
        petition_id = uuid7()
        archons = (uuid7(), uuid7(), uuid7())

        stub.inject_session(
            session_id=session_id,
            petition_id=petition_id,
            assigned_archons=archons,
        )

        assert stub.has_session(session_id)
        assert stub.get_session_count() == 1

    def test_inject_session_with_all_optional_fields(self) -> None:
        """Injecting a session with all optional fields."""
        stub = AuditTrailReconstructorStub()
        session_id = uuid7()
        petition_id = uuid7()
        archons = (uuid7(), uuid7(), uuid7())
        started = _utc_now()
        completed = started + timedelta(minutes=5)
        transcripts = {"ASSESS": "Assessment content", "VOTE": "Vote content"}
        dissent = {"dissenter_id": str(uuid7()), "reason": "Disagree"}
        substitutions = ({"original": str(uuid7()), "replacement": str(uuid7())},)

        stub.inject_session(
            session_id=session_id,
            petition_id=petition_id,
            assigned_archons=archons,
            started_at=started,
            completed_at=completed,
            outcome="REFER",
            termination_reason=TerminationReason.TIMEOUT,
            transcripts=transcripts,
            dissent_record=dissent,
            substitutions=substitutions,
            witness_chain_valid=False,
        )

        assert stub.has_session(session_id)

    def test_inject_multiple_sessions(self) -> None:
        """Can inject multiple distinct sessions."""
        stub = AuditTrailReconstructorStub()

        for _ in range(3):
            stub.inject_session(
                session_id=uuid7(),
                petition_id=uuid7(),
                assigned_archons=(uuid7(), uuid7(), uuid7()),
            )

        assert stub.get_session_count() == 3


class TestInjectEvent:
    """Tests for inject_event method."""

    def test_inject_event_adds_event_to_session(self) -> None:
        """Injecting an event adds it to the session's event list."""
        stub = AuditTrailReconstructorStub()
        session_id = uuid7()
        stub.inject_session(
            session_id=session_id,
            petition_id=uuid7(),
            assigned_archons=(uuid7(), uuid7(), uuid7()),
        )

        event = _make_timeline_event()
        stub.inject_event(session_id, event)

        assert stub.get_event_count(session_id) == 1

    def test_inject_multiple_events(self) -> None:
        """Can inject multiple events for a session."""
        stub = AuditTrailReconstructorStub()
        session_id = uuid7()
        stub.inject_session(
            session_id=session_id,
            petition_id=uuid7(),
            assigned_archons=(uuid7(), uuid7(), uuid7()),
        )

        for _ in range(5):
            stub.inject_event(session_id, _make_timeline_event())

        assert stub.get_event_count(session_id) == 5

    def test_inject_events_bulk(self) -> None:
        """Can inject multiple events at once using inject_events."""
        stub = AuditTrailReconstructorStub()
        session_id = uuid7()
        stub.inject_session(
            session_id=session_id,
            petition_id=uuid7(),
            assigned_archons=(uuid7(), uuid7(), uuid7()),
        )

        events = [_make_timeline_event() for _ in range(3)]
        stub.inject_events(session_id, events)

        assert stub.get_event_count(session_id) == 3

    def test_inject_event_for_nonexistent_session(self) -> None:
        """Injecting event for non-existent session creates event list."""
        stub = AuditTrailReconstructorStub()
        session_id = uuid7()

        # Note: inject_event doesn't require session to exist first
        event = _make_timeline_event()
        stub.inject_event(session_id, event)

        # Event is stored but session doesn't exist
        assert not stub.has_session(session_id)
        assert stub.get_event_count(session_id) == 1


class TestReconstructTimeline:
    """Tests for reconstruct_timeline method."""

    @pytest.mark.asyncio
    async def test_reconstruct_timeline_returns_timeline(self) -> None:
        """Reconstructing timeline returns AuditTimeline with session data."""
        stub = AuditTrailReconstructorStub()
        session_id = uuid7()
        petition_id = uuid7()
        archons = (uuid7(), uuid7(), uuid7())

        stub.inject_session(
            session_id=session_id,
            petition_id=petition_id,
            assigned_archons=archons,
            outcome="ACKNOWLEDGE",
        )

        timeline = await stub.reconstruct_timeline(session_id)

        assert timeline.session_id == session_id
        assert timeline.petition_id == petition_id
        assert timeline.assigned_archons == archons
        assert timeline.outcome == "ACKNOWLEDGE"

    @pytest.mark.asyncio
    async def test_reconstruct_timeline_includes_events_sorted(self) -> None:
        """Timeline includes events sorted by occurred_at."""
        stub = AuditTrailReconstructorStub()
        session_id = uuid7()
        stub.inject_session(
            session_id=session_id,
            petition_id=uuid7(),
            assigned_archons=(uuid7(), uuid7(), uuid7()),
        )

        # Inject events out of order
        now = _utc_now()
        event1 = _make_timeline_event(occurred_at=now + timedelta(minutes=2))
        event2 = _make_timeline_event(occurred_at=now)
        event3 = _make_timeline_event(occurred_at=now + timedelta(minutes=1))

        stub.inject_event(session_id, event1)
        stub.inject_event(session_id, event2)
        stub.inject_event(session_id, event3)

        timeline = await stub.reconstruct_timeline(session_id)

        # Should be sorted chronologically
        assert len(timeline.events) == 3
        assert timeline.events[0].occurred_at == event2.occurred_at
        assert timeline.events[1].occurred_at == event3.occurred_at
        assert timeline.events[2].occurred_at == event1.occurred_at

    @pytest.mark.asyncio
    async def test_reconstruct_timeline_tracks_call(self) -> None:
        """Reconstruct call is tracked for test assertions."""
        stub = AuditTrailReconstructorStub()
        session_id = uuid7()
        stub.inject_session(
            session_id=session_id,
            petition_id=uuid7(),
            assigned_archons=(uuid7(), uuid7(), uuid7()),
        )

        await stub.reconstruct_timeline(session_id)

        assert stub.get_reconstruct_call_count() == 1
        last_call = stub.get_last_reconstruct_call()
        assert last_call is not None
        assert last_call["session_id"] == session_id

    @pytest.mark.asyncio
    async def test_reconstruct_timeline_not_found_raises(self) -> None:
        """Reconstructing non-existent session raises SessionNotFoundError."""
        stub = AuditTrailReconstructorStub()
        session_id = uuid7()

        with pytest.raises(SessionNotFoundError) as exc_info:
            await stub.reconstruct_timeline(session_id)

        assert exc_info.value.session_id == session_id

    @pytest.mark.asyncio
    async def test_reconstruct_timeline_with_transcripts(self) -> None:
        """Timeline includes transcript content when injected."""
        stub = AuditTrailReconstructorStub()
        session_id = uuid7()
        transcripts = {
            "ASSESS": "Assessment phase content",
            "POSITION": "Position phase content",
        }

        stub.inject_session(
            session_id=session_id,
            petition_id=uuid7(),
            assigned_archons=(uuid7(), uuid7(), uuid7()),
            transcripts=transcripts,
        )

        timeline = await stub.reconstruct_timeline(session_id)

        assert timeline.transcripts == transcripts
        assert timeline.get_transcript("ASSESS") == "Assessment phase content"

    @pytest.mark.asyncio
    async def test_reconstruct_timeline_with_dissent(self) -> None:
        """Timeline includes dissent record when injected."""
        stub = AuditTrailReconstructorStub()
        session_id = uuid7()
        dissent = {"dissenter_id": str(uuid7()), "reason": "Constitutional concern"}

        stub.inject_session(
            session_id=session_id,
            petition_id=uuid7(),
            assigned_archons=(uuid7(), uuid7(), uuid7()),
            dissent_record=dissent,
        )

        timeline = await stub.reconstruct_timeline(session_id)

        assert timeline.dissent_record == dissent
        assert timeline.has_dissent is True

    @pytest.mark.asyncio
    async def test_reconstruct_timeline_with_substitutions(self) -> None:
        """Timeline includes substitution records when injected."""
        stub = AuditTrailReconstructorStub()
        session_id = uuid7()
        substitutions = (
            {"original": str(uuid7()), "replacement": str(uuid7())},
            {"original": str(uuid7()), "replacement": str(uuid7())},
        )

        stub.inject_session(
            session_id=session_id,
            petition_id=uuid7(),
            assigned_archons=(uuid7(), uuid7(), uuid7()),
            substitutions=substitutions,
        )

        timeline = await stub.reconstruct_timeline(session_id)

        assert timeline.substitutions == substitutions
        assert timeline.has_substitutions is True


class TestGetSessionEvents:
    """Tests for get_session_events method."""

    @pytest.mark.asyncio
    async def test_get_events_returns_events_sorted(self) -> None:
        """Getting events returns them sorted by occurred_at."""
        stub = AuditTrailReconstructorStub()
        session_id = uuid7()
        stub.inject_session(
            session_id=session_id,
            petition_id=uuid7(),
            assigned_archons=(uuid7(), uuid7(), uuid7()),
        )

        now = _utc_now()
        event1 = _make_timeline_event(occurred_at=now + timedelta(minutes=1))
        event2 = _make_timeline_event(occurred_at=now)

        stub.inject_event(session_id, event1)
        stub.inject_event(session_id, event2)

        events = await stub.get_session_events(session_id)

        assert len(events) == 2
        assert events[0].occurred_at == event2.occurred_at
        assert events[1].occurred_at == event1.occurred_at

    @pytest.mark.asyncio
    async def test_get_events_tracks_call(self) -> None:
        """Get events call is tracked for test assertions."""
        stub = AuditTrailReconstructorStub()
        session_id = uuid7()
        stub.inject_session(
            session_id=session_id,
            petition_id=uuid7(),
            assigned_archons=(uuid7(), uuid7(), uuid7()),
        )

        await stub.get_session_events(session_id)

        assert stub.get_events_call_count() == 1

    @pytest.mark.asyncio
    async def test_get_events_not_found_raises(self) -> None:
        """Getting events for non-existent session raises SessionNotFoundError."""
        stub = AuditTrailReconstructorStub()

        with pytest.raises(SessionNotFoundError):
            await stub.get_session_events(uuid7())

    @pytest.mark.asyncio
    async def test_get_events_empty_list_for_session_without_events(self) -> None:
        """Getting events for session with no events returns empty list."""
        stub = AuditTrailReconstructorStub()
        session_id = uuid7()
        stub.inject_session(
            session_id=session_id,
            petition_id=uuid7(),
            assigned_archons=(uuid7(), uuid7(), uuid7()),
        )

        events = await stub.get_session_events(session_id)

        assert events == []


class TestVerifyWitnessChain:
    """Tests for verify_witness_chain method."""

    @pytest.mark.asyncio
    async def test_verify_returns_default_valid(self) -> None:
        """Verification returns valid result by default."""
        stub = AuditTrailReconstructorStub()
        session_id = uuid7()
        stub.inject_session(
            session_id=session_id,
            petition_id=uuid7(),
            assigned_archons=(uuid7(), uuid7(), uuid7()),
        )

        # Add witnessed events
        stub.inject_event(
            session_id,
            _make_timeline_event(witness_hash=_make_witness_hash()),
        )

        verification = await stub.verify_witness_chain(session_id)

        assert verification.is_valid is True
        assert verification.broken_links == ()
        assert verification.missing_transcripts == ()
        assert verification.integrity_failures == ()
        assert verification.verified_events == 1
        assert verification.total_events == 1

    @pytest.mark.asyncio
    async def test_verify_tracks_call(self) -> None:
        """Verify call is tracked for test assertions."""
        stub = AuditTrailReconstructorStub()
        session_id = uuid7()
        stub.inject_session(
            session_id=session_id,
            petition_id=uuid7(),
            assigned_archons=(uuid7(), uuid7(), uuid7()),
        )

        await stub.verify_witness_chain(session_id)

        assert stub.get_verify_call_count() == 1
        last_call = stub.get_last_verify_call()
        assert last_call is not None
        assert last_call["session_id"] == session_id

    @pytest.mark.asyncio
    async def test_verify_not_found_raises(self) -> None:
        """Verifying non-existent session raises SessionNotFoundError."""
        stub = AuditTrailReconstructorStub()

        with pytest.raises(SessionNotFoundError):
            await stub.verify_witness_chain(uuid7())

    @pytest.mark.asyncio
    async def test_verify_uses_injected_result(self) -> None:
        """Verification uses injected result when present."""
        stub = AuditTrailReconstructorStub()
        session_id = uuid7()
        stub.inject_session(
            session_id=session_id,
            petition_id=uuid7(),
            assigned_archons=(uuid7(), uuid7(), uuid7()),
        )

        # Inject a failed verification result
        broken_verification = WitnessChainVerification(
            is_valid=False,
            broken_links=((uuid7(), uuid7()),),
            missing_transcripts=(_make_witness_hash(),),
            integrity_failures=(),
            verified_events=5,
            total_events=10,
        )
        stub.inject_verification_result(session_id, broken_verification)

        verification = await stub.verify_witness_chain(session_id)

        assert verification.is_valid is False
        assert len(verification.broken_links) == 1
        assert len(verification.missing_transcripts) == 1
        assert verification.verified_events == 5
        assert verification.total_events == 10

    def test_inject_verification_result_requires_session(self) -> None:
        """Injecting verification result requires session to exist."""
        stub = AuditTrailReconstructorStub()

        with pytest.raises(KeyError):
            stub.inject_verification_result(
                uuid7(),
                WitnessChainVerification(is_valid=True),
            )


class TestCallTracking:
    """Tests for call tracking and inspection."""

    @pytest.mark.asyncio
    async def test_multiple_calls_tracked(self) -> None:
        """Multiple calls to same method are all tracked."""
        stub = AuditTrailReconstructorStub()
        session_id = uuid7()
        stub.inject_session(
            session_id=session_id,
            petition_id=uuid7(),
            assigned_archons=(uuid7(), uuid7(), uuid7()),
        )

        await stub.reconstruct_timeline(session_id)
        await stub.reconstruct_timeline(session_id)
        await stub.reconstruct_timeline(session_id)

        assert stub.get_reconstruct_call_count() == 3

    @pytest.mark.asyncio
    async def test_last_call_returns_most_recent(self) -> None:
        """Get last call returns most recent call parameters."""
        stub = AuditTrailReconstructorStub()
        session1 = uuid7()
        session2 = uuid7()

        for sid in [session1, session2]:
            stub.inject_session(
                session_id=sid,
                petition_id=uuid7(),
                assigned_archons=(uuid7(), uuid7(), uuid7()),
            )

        await stub.reconstruct_timeline(session1)
        await stub.reconstruct_timeline(session2)

        last_call = stub.get_last_reconstruct_call()
        assert last_call is not None
        assert last_call["session_id"] == session2

    def test_last_call_returns_none_when_no_calls(self) -> None:
        """Get last call returns None when no calls made."""
        stub = AuditTrailReconstructorStub()

        assert stub.get_last_reconstruct_call() is None
        assert stub.get_last_verify_call() is None


class TestClear:
    """Tests for clear method."""

    @pytest.mark.asyncio
    async def test_clear_removes_all_data(self) -> None:
        """Clear removes all sessions, events, and call history."""
        stub = AuditTrailReconstructorStub()
        session_id = uuid7()
        stub.inject_session(
            session_id=session_id,
            petition_id=uuid7(),
            assigned_archons=(uuid7(), uuid7(), uuid7()),
        )
        stub.inject_event(session_id, _make_timeline_event())

        await stub.reconstruct_timeline(session_id)
        await stub.verify_witness_chain(session_id)
        await stub.get_session_events(session_id)

        stub.clear()

        assert stub.get_session_count() == 0
        assert stub.get_reconstruct_call_count() == 0
        assert stub.get_verify_call_count() == 0
        assert stub.get_events_call_count() == 0


class TestHelperMethods:
    """Tests for test helper methods."""

    def test_has_session_returns_false_for_missing(self) -> None:
        """has_session returns False for non-existent session."""
        stub = AuditTrailReconstructorStub()

        assert stub.has_session(uuid7()) is False

    def test_get_event_count_returns_zero_for_missing(self) -> None:
        """get_event_count returns 0 for non-existent session."""
        stub = AuditTrailReconstructorStub()

        assert stub.get_event_count(uuid7()) == 0
