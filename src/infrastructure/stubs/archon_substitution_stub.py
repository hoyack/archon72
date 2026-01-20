"""Archon substitution stub implementation (Story 2B.4, AC-6).

This module provides an in-memory stub implementation of
ArchonSubstitutionProtocol for development and testing purposes.

Constitutional Constraints:
- FR-11.12: System SHALL detect individual Archon response timeout
- NFR-10.6: Archon substitution latency < 10 seconds on failure
- CT-11: Silent failure destroys legitimacy - failures must be handled
- AT-1: Every petition terminates in exactly one of Three Fates
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from uuid6 import uuid7

from src.application.ports.archon_substitution import (
    ArchonSubstitutionProtocol,
    ContextHandoff,
    SubstitutionResult,
)
from src.config.deliberation_config import (
    DEFAULT_DELIBERATION_CONFIG,
    DeliberationConfig,
)
from src.domain.events.archon_substitution import (
    ArchonSubstitutedEvent,
    DeliberationAbortedEvent,
)
from src.domain.models.deliberation_session import (
    MAX_SUBSTITUTIONS_PER_SESSION,
    ArchonSubstitution,
    DeliberationSession,
)


def _utc_now() -> datetime:
    """Return current UTC time with timezone info."""
    return datetime.now(timezone.utc)


# Maximum substitution latency in milliseconds (NFR-10.6)
MAX_SUBSTITUTION_LATENCY_MS = 10_000

# Valid failure reasons per AC-6
VALID_FAILURE_REASONS = (
    "RESPONSE_TIMEOUT",
    "API_ERROR",
    "INVALID_RESPONSE",
)

# Valid abort reasons per AC-7, AC-8
VALID_ABORT_REASONS = (
    "INSUFFICIENT_ARCHONS",
    "ARCHON_POOL_EXHAUSTED",
)


class ArchonSubstitutionStub(ArchonSubstitutionProtocol):
    """In-memory stub implementation of ArchonSubstitutionProtocol.

    This stub provides a simple implementation for development and testing
    that stores sessions, substitutions, and available substitutes in memory.

    NOT suitable for production use.

    Constitutional Compliance:
    - FR-11.12: Failure detection (simulated)
    - NFR-10.6: Substitution latency tracking (simulated)
    - CT-11: Failure handling (simulated)
    - AT-1: Session termination (simulated)

    Attributes:
        _sessions: Dictionary mapping session_id to DeliberationSession.
        _available_substitutes: List of available substitute archon IDs.
        _substitutions: List of (session_id, ArchonSubstitution) tuples.
        _aborts: Set of session IDs that were aborted.
        _config: Deliberation configuration.
        _events_emitted: List of emitted events.
        _simulated_latency_ms: Simulated latency for testing (default 100ms).
    """

    def __init__(
        self,
        config: DeliberationConfig | None = None,
        available_substitutes: list[UUID] | None = None,
        simulated_latency_ms: int = 100,
    ) -> None:
        """Initialize the stub with empty storage.

        Args:
            config: Deliberation configuration. Uses default if not provided.
            available_substitutes: List of substitute archon IDs to use.
            simulated_latency_ms: Simulated latency for testing.
        """
        self._sessions: dict[UUID, DeliberationSession] = {}
        self._available_substitutes = list(available_substitutes or [])
        self._substitutions: list[tuple[UUID, ArchonSubstitution]] = []
        self._aborts: set[UUID] = set()
        self._config = config or DEFAULT_DELIBERATION_CONFIG
        self._events_emitted: list[
            ArchonSubstitutedEvent | DeliberationAbortedEvent
        ] = []
        self._emitted_events = self._events_emitted
        self._simulated_latency_ms = simulated_latency_ms

    def register_session(self, session: DeliberationSession) -> None:
        """Register a session for substitution tracking (test helper).

        Args:
            session: The session to register.
        """
        self._sessions[session.session_id] = session

    def set_session(self, session: DeliberationSession) -> None:
        """Compatibility alias for register_session (test helper)."""
        self.register_session(session)

    def add_available_substitute(self, archon_id: UUID) -> None:
        """Add an available substitute archon ID (test helper).

        Args:
            archon_id: UUID of the archon to add.
        """
        if archon_id not in self._available_substitutes:
            self._available_substitutes.append(archon_id)

    def set_available_substitutes(self, archon_ids: list[UUID]) -> None:
        """Set the list of available substitutes (test helper).

        Args:
            archon_ids: List of archon UUIDs to set as available.
        """
        self._available_substitutes = list(archon_ids)

    async def detect_failure(
        self,
        session: DeliberationSession,
        archon_id: UUID,
        failure_reason: str,
    ) -> bool:
        """Detect and validate an Archon failure during deliberation (FR-11.12).

        Args:
            session: The deliberation session.
            archon_id: ID of the Archon that failed.
            failure_reason: Why failure occurred.

        Returns:
            True if failure is valid and can be handled, False otherwise.

        Raises:
            ValueError: If failure_reason is not a valid reason.
        """
        # Validate failure reason
        if failure_reason not in VALID_FAILURE_REASONS:
            raise ValueError(
                f"failure_reason must be one of {VALID_FAILURE_REASONS}, "
                f"got '{failure_reason}'"
            )

        # Check session is not complete
        if session.phase.is_terminal():
            return False

        # Check archon is currently active
        if archon_id not in session.current_active_archons:
            return False

        return True

    async def can_substitute(
        self,
        session: DeliberationSession,
    ) -> bool:
        """Check if substitution is allowed for this session (NFR-10.6: max 1).

        Args:
            session: The deliberation session.

        Returns:
            True if substitution_count < max_substitutions, False otherwise.
        """
        return session.can_substitute

    async def select_substitute(
        self,
        session: DeliberationSession,
        failed_archon_id: UUID,
    ) -> UUID | None:
        """Select a substitute Archon from the available substitutes list.

        Args:
            session: The deliberation session.
            failed_archon_id: ID of the Archon being replaced.

        Returns:
            UUID of selected substitute, or None if none available.
        """
        # Get current active archons (excludes failed, includes substitutes)
        active_archons = set(session.current_active_archons)

        # Also exclude the failed archon explicitly
        active_archons.add(failed_archon_id)

        # Also exclude any previously failed archons
        for sub in session.substitutions:
            active_archons.add(sub.failed_archon_id)

        # Find first available substitute not in session
        for archon_id in self._available_substitutes:
            if archon_id not in active_archons:
                return archon_id

        return None

    async def prepare_context_handoff(
        self,
        session: DeliberationSession,
        failed_archon_id: UUID,
    ) -> ContextHandoff:
        """Prepare context for substitute Archon (Story 2B.4, AC-3).

        Args:
            session: The deliberation session.
            failed_archon_id: ID of the failed Archon.

        Returns:
            ContextHandoff with transcript pages and session state.
        """
        # Collect transcript pages from completed phases
        transcript_pages = tuple(
            hash_bytes
            for phase, hash_bytes in sorted(
                session.phase_transcripts.items(),
                key=lambda x: x[0].value,
            )
        )

        # Convert votes to string outcome names
        previous_votes = {
            archon_id: vote.value for archon_id, vote in session.votes.items()
        }

        return ContextHandoff(
            session_id=session.session_id,
            petition_id=session.petition_id,
            current_phase=session.phase,
            transcript_pages=transcript_pages,
            previous_votes=previous_votes,
            round_count=session.round_count,
        )

    async def execute_substitution(
        self,
        session: DeliberationSession,
        failed_archon_id: UUID,
        failure_reason: str,
    ) -> SubstitutionResult:
        """Execute full substitution workflow (Story 2B.4).

        Args:
            session: The deliberation session.
            failed_archon_id: ID of the Archon that failed.
            failure_reason: Why failure occurred.

        Returns:
            SubstitutionResult with success status, updated session, and event.

        Raises:
            SessionAlreadyCompleteError: If session is already complete.
            ValueError: If archon_id is not active in session.
        """
        from src.domain.errors.deliberation import SessionAlreadyCompleteError

        # Validate session not complete
        if session.phase.is_terminal():
            raise SessionAlreadyCompleteError(
                session_id=str(session.session_id),
                message="Cannot substitute archon in completed session",
            )

        # Validate failure
        is_valid = await self.detect_failure(session, failed_archon_id, failure_reason)
        if not is_valid:
            raise ValueError(
                f"Archon {failed_archon_id} is not currently active in session"
            )

        # Check if substitution is allowed
        if not await self.can_substitute(session):
            # Max substitutions reached - must abort
            return await self._abort_insufficient_archons(
                session, failed_archon_id, failure_reason
            )

        # Select substitute
        substitute_id = await self.select_substitute(session, failed_archon_id)
        if substitute_id is None:
            # No substitute available - must abort
            return await self._abort_pool_exhausted(
                session, failed_archon_id, failure_reason
            )

        # Prepare context handoff
        context = await self.prepare_context_handoff(session, failed_archon_id)

        # Record substitution in session
        updated_session = session.with_substitution(
            failed_archon_id=failed_archon_id,
            substitute_archon_id=substitute_id,
            failure_reason=failure_reason,
        )

        # Create substitution event
        event = ArchonSubstitutedEvent(
            event_id=uuid7(),
            session_id=session.session_id,
            petition_id=session.petition_id,
            failed_archon_id=failed_archon_id,
            substitute_archon_id=substitute_id,
            phase_at_failure=session.phase,
            failure_reason=failure_reason,
            substitution_latency_ms=self._simulated_latency_ms,
            transcript_pages_provided=len(context.transcript_pages),
        )

        # Track substitution
        self._substitutions.append(
            (
                session.session_id,
                updated_session.substitutions[-1],
            )
        )
        self._events_emitted.append(event)

        # Store updated session
        self._sessions[session.session_id] = updated_session

        return SubstitutionResult(
            success=True,
            session=updated_session,
            event=event,
            substitute_archon_id=substitute_id,
            latency_ms=self._simulated_latency_ms,
            met_sla=self._simulated_latency_ms <= MAX_SUBSTITUTION_LATENCY_MS,
        )

    async def _abort_insufficient_archons(
        self,
        session: DeliberationSession,
        failed_archon_id: UUID,
        failure_reason: str,
    ) -> SubstitutionResult:
        """Abort due to too many failures (substitution limit exceeded)."""
        # Build failed archons list including previous failures
        failed_archons = [
            {
                "archon_id": str(sub.failed_archon_id),
                "failure_reason": sub.failure_reason,
                "phase": sub.phase_at_failure.value,
            }
            for sub in session.substitutions
        ]
        # Add current failure
        failed_archons.append(
            {
                "archon_id": str(failed_archon_id),
                "failure_reason": failure_reason,
                "phase": session.phase.value,
            }
        )

        updated_session, event = await self.abort_deliberation(
            session=session,
            reason="INSUFFICIENT_ARCHONS",
            failed_archons=failed_archons,
        )

        return SubstitutionResult(
            success=False,
            session=updated_session,
            event=event,
            substitute_archon_id=None,
            latency_ms=self._simulated_latency_ms,
            met_sla=self._simulated_latency_ms <= MAX_SUBSTITUTION_LATENCY_MS,
        )

    async def _abort_pool_exhausted(
        self,
        session: DeliberationSession,
        failed_archon_id: UUID,
        failure_reason: str,
    ) -> SubstitutionResult:
        """Abort due to archon pool exhausted."""
        failed_archons = [
            {
                "archon_id": str(failed_archon_id),
                "failure_reason": failure_reason,
                "phase": session.phase.value,
            }
        ]

        updated_session, event = await self.abort_deliberation(
            session=session,
            reason="ARCHON_POOL_EXHAUSTED",
            failed_archons=failed_archons,
        )

        return SubstitutionResult(
            success=False,
            session=updated_session,
            event=event,
            substitute_archon_id=None,
            latency_ms=self._simulated_latency_ms,
            met_sla=self._simulated_latency_ms <= MAX_SUBSTITUTION_LATENCY_MS,
        )

    async def abort_deliberation(
        self,
        session: DeliberationSession,
        reason: str,
        failed_archons: list[dict[str, str]],
    ) -> tuple[DeliberationSession, DeliberationAbortedEvent]:
        """Abort deliberation when substitution is not possible (Story 2B.4, AC-7, AC-8).

        Args:
            session: The deliberation session.
            reason: Why abort occurred.
            failed_archons: Details of Archons that failed.

        Returns:
            Tuple of (session with ESCALATE and is_aborted=True, event).

        Raises:
            SessionAlreadyCompleteError: If session is already complete.
            ValueError: If reason is not a valid abort reason.
        """
        from src.domain.errors.deliberation import SessionAlreadyCompleteError

        if session.phase.is_terminal():
            raise SessionAlreadyCompleteError(
                session_id=str(session.session_id),
                message="Cannot abort already completed session",
            )

        if reason not in VALID_ABORT_REASONS:
            raise ValueError(
                f"reason must be one of {VALID_ABORT_REASONS}, got '{reason}'"
            )

        # Apply abort outcome
        updated_session = session.with_abort(reason)

        # Find surviving archon (if any)
        current_active = session.current_active_archons
        failed_ids = {UUID(fa["archon_id"]) for fa in failed_archons}
        surviving = [a for a in current_active if a not in failed_ids]
        surviving_archon_id = surviving[0] if surviving else None

        # Create abort event
        event = DeliberationAbortedEvent(
            event_id=uuid7(),
            session_id=session.session_id,
            petition_id=session.petition_id,
            reason=reason,
            failed_archons=tuple(failed_archons),
            phase_at_abort=session.phase,
            surviving_archon_id=surviving_archon_id,
        )

        # Track abort
        self._aborts.add(session.session_id)
        self._events_emitted.append(event)

        # Store updated session
        self._sessions[session.session_id] = updated_session

        return updated_session, event

    async def get_substitution_status(
        self,
        session_id: UUID,
    ) -> tuple[bool, int, ArchonSubstitution | None]:
        """Get substitution tracking status for a session.

        Args:
            session_id: UUID of the deliberation session.

        Returns:
            Tuple of (has_substitution, substitution_count, latest_substitution).

        Raises:
            SessionNotFoundError: If session doesn't exist.
        """
        from src.domain.errors.deliberation import SessionNotFoundError

        session = self._sessions.get(session_id)
        if session is None:
            raise SessionNotFoundError(
                session_id=str(session_id),
                message=f"Session {session_id} not found for substitution status",
            )

        latest = session.substitutions[-1] if session.substitutions else None

        return (
            session.has_substitution,
            session.substitution_count,
            latest,
        )

    async def get_active_archons(
        self,
        session_id: UUID,
    ) -> tuple[UUID, ...]:
        """Get currently active Archon IDs for a session.

        Args:
            session_id: UUID of the deliberation session.

        Returns:
            Tuple of active Archon UUIDs.

        Raises:
            SessionNotFoundError: If session doesn't exist.
        """
        from src.domain.errors.deliberation import SessionNotFoundError

        session = self._sessions.get(session_id)
        if session is None:
            raise SessionNotFoundError(
                session_id=str(session_id),
                message=f"Session {session_id} not found for active archons",
            )

        return session.current_active_archons

    # Test helper methods

    def clear(self) -> None:
        """Clear all state (for testing)."""
        self._sessions.clear()
        self._available_substitutes.clear()
        self._substitutions.clear()
        self._aborts.clear()
        self._events_emitted.clear()

    def get_session(self, session_id: UUID) -> DeliberationSession | None:
        """Get a session by ID (for testing).

        Args:
            session_id: UUID of the session.

        Returns:
            DeliberationSession if found, None otherwise.
        """
        return self._sessions.get(session_id)

    def get_substitutions(self) -> list[tuple[UUID, ArchonSubstitution]]:
        """Get list of (session_id, substitution) tuples (for testing).

        Returns:
            List of tuples.
        """
        return self._substitutions.copy()

    def get_aborts(self) -> set[UUID]:
        """Get set of session IDs that were aborted (for testing).

        Returns:
            Set of session UUIDs.
        """
        return self._aborts.copy()

    def get_emitted_events(
        self,
    ) -> list[ArchonSubstitutedEvent | DeliberationAbortedEvent]:
        """Get list of emitted events (for testing).

        Returns:
            List of event instances.
        """
        return self._events_emitted.copy()

    @property
    def max_substitutions(self) -> int:
        """Get configured maximum substitutions per session.

        Returns:
            Maximum substitutions allowed (NFR-10.6: 1).
        """
        return MAX_SUBSTITUTIONS_PER_SESSION

    @property
    def max_latency_ms(self) -> int:
        """Get maximum substitution latency SLA (NFR-10.6).

        Returns:
            Maximum latency in milliseconds (10000).
        """
        return MAX_SUBSTITUTION_LATENCY_MS
