"""Audit trail reconstructor stub for testing (Story 2B.6).

This module provides an in-memory stub implementation of
AuditTrailReconstructorProtocol for unit and integration testing.

Constitutional Constraints:
- FR-11.12: Complete deliberation transcript preservation for audit
- NFR-6.5: Full state history reconstruction from event log
- CT-12: Verify unbroken chain of accountability
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from src.application.ports.audit_trail_reconstructor import SessionNotFoundError
from src.domain.models.audit_timeline import (
    AuditTimeline,
    TerminationReason,
    TimelineEvent,
    WitnessChainVerification,
)


def _utc_now() -> datetime:
    """Return current UTC time with timezone info."""
    return datetime.now(timezone.utc)


class AuditTrailReconstructorStub:
    """Stub implementation of AuditTrailReconstructorProtocol for testing.

    Stores sessions and events in memory for fast unit tests.
    Supports injecting test data and tracking method calls.

    Attributes:
        _sessions: In-memory storage mapping session_id -> session data.
        _events: In-memory storage mapping session_id -> list of events.
        _reconstruct_calls: History of reconstruct_timeline calls.
        _verify_calls: History of verify_witness_chain calls.
        _get_events_calls: History of get_session_events calls.

    Example:
        ```python
        stub = AuditTrailReconstructorStub()

        # Inject test data
        stub.inject_session(
            session_id=uuid7(),
            petition_id=uuid7(),
            assigned_archons=(uuid7(), uuid7(), uuid7()),
            outcome="ACKNOWLEDGE",
        )

        # Use in tests
        timeline = await stub.reconstruct_timeline(session_id)
        assert timeline.outcome == "ACKNOWLEDGE"
        ```
    """

    def __init__(self) -> None:
        """Initialize empty in-memory store."""
        self._sessions: dict[UUID, dict[str, Any]] = {}
        self._events: dict[UUID, list[TimelineEvent]] = {}
        self._reconstruct_calls: list[dict[str, Any]] = []
        self._verify_calls: list[dict[str, Any]] = []
        self._get_events_calls: list[dict[str, Any]] = []

    async def reconstruct_timeline(
        self,
        session_id: UUID,
    ) -> AuditTimeline:
        """Reconstruct timeline from in-memory storage.

        Args:
            session_id: UUID of the deliberation session.

        Returns:
            AuditTimeline with all events, transcripts, and metadata.

        Raises:
            SessionNotFoundError: If session_id doesn't exist.
        """
        self._reconstruct_calls.append({"session_id": session_id})

        if session_id not in self._sessions:
            raise SessionNotFoundError(session_id)

        session_data = self._sessions[session_id]
        events = self._events.get(session_id, [])

        return AuditTimeline(
            session_id=session_id,
            petition_id=session_data["petition_id"],
            events=tuple(sorted(events, key=lambda e: e.occurred_at)),
            assigned_archons=session_data["assigned_archons"],
            outcome=session_data.get("outcome", "ESCALATE"),
            termination_reason=session_data.get(
                "termination_reason", TerminationReason.NORMAL
            ),
            started_at=session_data["started_at"],
            completed_at=session_data.get("completed_at"),
            witness_chain_valid=session_data.get("witness_chain_valid", True),
            transcripts=session_data.get("transcripts", {}),
            dissent_record=session_data.get("dissent_record"),
            substitutions=session_data.get("substitutions", ()),
        )

    async def get_session_events(
        self,
        session_id: UUID,
    ) -> list[TimelineEvent]:
        """Get events from in-memory storage.

        Args:
            session_id: UUID of the deliberation session.

        Returns:
            List of TimelineEvents ordered by occurred_at.

        Raises:
            SessionNotFoundError: If session_id doesn't exist.
        """
        self._get_events_calls.append({"session_id": session_id})

        if session_id not in self._sessions:
            raise SessionNotFoundError(session_id)

        events = self._events.get(session_id, [])
        return sorted(events, key=lambda e: e.occurred_at)

    async def verify_witness_chain(
        self,
        session_id: UUID,
    ) -> WitnessChainVerification:
        """Verify witness chain from in-memory storage.

        For the stub, returns pre-configured verification result
        or a default valid result if none configured.

        Args:
            session_id: UUID of the deliberation session.

        Returns:
            WitnessChainVerification with verification results.

        Raises:
            SessionNotFoundError: If session_id doesn't exist.
        """
        self._verify_calls.append({"session_id": session_id})

        if session_id not in self._sessions:
            raise SessionNotFoundError(session_id)

        session_data = self._sessions[session_id]
        events = self._events.get(session_id, [])

        # Return pre-configured verification result if present
        if "verification_result" in session_data:
            return session_data["verification_result"]

        # Default: return valid verification
        witnessed_events = [e for e in events if e.witness_hash is not None]
        return WitnessChainVerification(
            is_valid=True,
            broken_links=(),
            missing_transcripts=(),
            integrity_failures=(),
            verified_events=len(witnessed_events),
            total_events=len(witnessed_events),
        )

    # =========================================================================
    # Test Helpers
    # =========================================================================

    def inject_session(
        self,
        session_id: UUID,
        petition_id: UUID,
        assigned_archons: tuple[UUID, UUID, UUID],
        started_at: datetime | None = None,
        completed_at: datetime | None = None,
        outcome: str = "ACKNOWLEDGE",
        termination_reason: TerminationReason = TerminationReason.NORMAL,
        transcripts: dict[str, str | None] | None = None,
        dissent_record: dict[str, Any] | None = None,
        substitutions: tuple[dict[str, Any], ...] = (),
        witness_chain_valid: bool = True,
    ) -> None:
        """Inject a session for testing.

        Args:
            session_id: UUID of the deliberation session.
            petition_id: UUID of the petition.
            assigned_archons: Tuple of exactly 3 archon UUIDs.
            started_at: When deliberation started (defaults to now).
            completed_at: When deliberation completed (optional).
            outcome: Final outcome (ACKNOWLEDGE, REFER, ESCALATE).
            termination_reason: How deliberation terminated.
            transcripts: Dict mapping phase name to transcript content.
            dissent_record: Optional dissent record.
            substitutions: Tuple of substitution records.
            witness_chain_valid: Whether witness chain is valid.
        """
        self._sessions[session_id] = {
            "petition_id": petition_id,
            "assigned_archons": assigned_archons,
            "started_at": started_at or _utc_now(),
            "completed_at": completed_at,
            "outcome": outcome,
            "termination_reason": termination_reason,
            "transcripts": transcripts or {},
            "dissent_record": dissent_record,
            "substitutions": substitutions,
            "witness_chain_valid": witness_chain_valid,
        }

    def inject_event(
        self,
        session_id: UUID,
        event: TimelineEvent,
    ) -> None:
        """Inject an event for a session.

        Args:
            session_id: UUID of the deliberation session.
            event: TimelineEvent to add.
        """
        if session_id not in self._events:
            self._events[session_id] = []
        self._events[session_id].append(event)

    def inject_events(
        self,
        session_id: UUID,
        events: list[TimelineEvent],
    ) -> None:
        """Inject multiple events for a session.

        Args:
            session_id: UUID of the deliberation session.
            events: List of TimelineEvents to add.
        """
        for event in events:
            self.inject_event(session_id, event)

    def inject_verification_result(
        self,
        session_id: UUID,
        result: WitnessChainVerification,
    ) -> None:
        """Inject a verification result for testing failures.

        Args:
            session_id: UUID of the deliberation session.
            result: WitnessChainVerification to return.

        Raises:
            KeyError: If session doesn't exist.
        """
        if session_id not in self._sessions:
            raise KeyError(f"Session {session_id} not found. Inject session first.")
        self._sessions[session_id]["verification_result"] = result

    def get_reconstruct_call_count(self) -> int:
        """Get number of reconstruct_timeline calls.

        Returns:
            Count of calls.
        """
        return len(self._reconstruct_calls)

    def get_verify_call_count(self) -> int:
        """Get number of verify_witness_chain calls.

        Returns:
            Count of calls.
        """
        return len(self._verify_calls)

    def get_events_call_count(self) -> int:
        """Get number of get_session_events calls.

        Returns:
            Count of calls.
        """
        return len(self._get_events_calls)

    def get_last_reconstruct_call(self) -> dict[str, Any] | None:
        """Get the most recent reconstruct_timeline call.

        Returns:
            Dict with call parameters or None if no calls.
        """
        if not self._reconstruct_calls:
            return None
        return self._reconstruct_calls[-1]

    def get_last_verify_call(self) -> dict[str, Any] | None:
        """Get the most recent verify_witness_chain call.

        Returns:
            Dict with call parameters or None if no calls.
        """
        if not self._verify_calls:
            return None
        return self._verify_calls[-1]

    def clear(self) -> None:
        """Clear all stored sessions and call history."""
        self._sessions.clear()
        self._events.clear()
        self._reconstruct_calls.clear()
        self._verify_calls.clear()
        self._get_events_calls.clear()

    def has_session(self, session_id: UUID) -> bool:
        """Check if a session exists in the stub.

        Args:
            session_id: UUID to check.

        Returns:
            True if session exists.
        """
        return session_id in self._sessions

    def get_session_count(self) -> int:
        """Get number of sessions in the stub.

        Returns:
            Count of sessions.
        """
        return len(self._sessions)

    def get_event_count(self, session_id: UUID) -> int:
        """Get number of events for a session.

        Args:
            session_id: UUID of the session.

        Returns:
            Count of events (0 if session not found).
        """
        return len(self._events.get(session_id, []))
