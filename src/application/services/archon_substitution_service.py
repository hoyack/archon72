"""Archon substitution service (Story 2B.4, NFR-10.6).

This module implements the ArchonSubstitutionProtocol for detecting Archon
failure and orchestrating substitution with a replacement Archon.

Constitutional Constraints:
- FR-11.12: System SHALL detect individual Archon response timeout
- NFR-10.6: Archon substitution latency < 10 seconds on failure
- NFR-10.2: Individual Archon response time p95 < 30 seconds
- CT-11: Silent failure destroys legitimacy - failures must be handled
- AT-1: Every petition terminates in exactly one of Three Fates
- AT-6: Deliberation is collective judgment (need 3 active Archons)
- NFR-10.4: 100% witness completeness

Usage:
    from src.application.services.archon_substitution_service import (
        ArchonSubstitutionService,
    )
    from src.config.deliberation_config import DEFAULT_DELIBERATION_CONFIG

    service = ArchonSubstitutionService(
        archon_pool=pool,
        event_emitter=emitter,
        config=DEFAULT_DELIBERATION_CONFIG,
    )

    # Execute substitution when archon fails
    result = await service.execute_substitution(
        session, failed_archon_id, "RESPONSE_TIMEOUT"
    )
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID

from uuid6 import uuid7

from src.application.ports.archon_substitution import (
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

if TYPE_CHECKING:
    from src.application.ports.archon_pool import ArchonPoolProtocol
    from src.application.ports.event_store import EventStorePort


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


class ArchonSubstitutionService:
    """Service for Archon failure detection and substitution (Story 2B.4, NFR-10.6).

    Handles detection of Archon failure during deliberation and orchestrates
    substitution with a replacement Archon from the pool.

    Substitution Logic:
    1. Detect failure (timeout, API error, invalid response)
    2. Check if substitution is allowed (max 1 per session)
    3. Select substitute from pool (not in current session)
    4. Prepare context handoff (transcript, votes, state)
    5. Record substitution in session
    6. Emit ArchonSubstitutedEvent

    Abort Conditions:
    - 2+ Archons fail (INSUFFICIENT_ARCHONS)
    - Pool exhausted (ARCHON_POOL_EXHAUSTED)

    Constitutional Constraints:
    - NFR-10.6: Substitution latency < 10 seconds
    - FR-11.12: Detect individual Archon response timeout
    - CT-11: Silent failure destroys legitimacy
    - AT-6: Need 3 active Archons for collective judgment

    Attributes:
        _archon_pool: Protocol for archon selection.
        _event_emitter: Protocol for emitting events (optional).
        _config: Deliberation configuration.
        _sessions: In-memory session storage (for stub/testing).
    """

    def __init__(
        self,
        archon_pool: ArchonPoolProtocol | None = None,
        event_emitter: EventStorePort | None = None,
        config: DeliberationConfig | None = None,
    ) -> None:
        """Initialize the archon substitution service.

        Args:
            archon_pool: Protocol for archon selection.
            event_emitter: Protocol for emitting substitution events (optional).
            config: Deliberation configuration. Uses default if not provided.
        """
        self._archon_pool = archon_pool
        self._event_emitter = event_emitter
        self._config = config or DEFAULT_DELIBERATION_CONFIG
        # In-memory session storage for development/testing
        # Production would use a repository
        self._sessions: dict[UUID, DeliberationSession] = {}

    def _utc_now(self) -> datetime:
        """Return current UTC time with timezone info."""
        return datetime.now(timezone.utc)

    def _time_ms(self) -> int:
        """Return current time in milliseconds for latency tracking."""
        return int(time.time() * 1000)

    def register_session(self, session: DeliberationSession) -> None:
        """Register a session for substitution tracking (development helper).

        In production, sessions would be stored in a repository.

        Args:
            session: The session to register.
        """
        self._sessions[session.session_id] = session

    def get_session(self, session_id: UUID) -> DeliberationSession | None:
        """Get a session by ID (development helper).

        Args:
            session_id: UUID of the session.

        Returns:
            DeliberationSession if found, None otherwise.
        """
        return self._sessions.get(session_id)

    async def detect_failure(
        self,
        session: DeliberationSession,
        archon_id: UUID,
        failure_reason: str,
    ) -> bool:
        """Detect and validate an Archon failure during deliberation (FR-11.12).

        Validates that:
        1. The archon is currently active in the session
        2. The session is not already complete
        3. The failure reason is valid

        Args:
            session: The deliberation session.
            archon_id: ID of the Archon that failed.
            failure_reason: Why failure occurred (RESPONSE_TIMEOUT, API_ERROR, INVALID_RESPONSE).

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
        """Select a substitute Archon from the pool (Story 2B.4, AC-2).

        Selection criteria:
        1. Must be Marquis-rank (pool only contains Marquis)
        2. Must not be currently assigned to this session
        3. Must be available (pool archons are always available)

        Args:
            session: The deliberation session.
            failed_archon_id: ID of the Archon being replaced.

        Returns:
            UUID of selected substitute, or None if pool exhausted.
        """
        if self._archon_pool is None:
            # No pool available - cannot select substitute
            return None

        # Get all archons from pool
        all_archons = self._archon_pool.list_all_archons()

        # Get current active archons (excludes failed, includes substitutes)
        active_archons = set(session.current_active_archons)

        # Also exclude the failed archon explicitly
        active_archons.add(failed_archon_id)

        # Also exclude any previously failed archons
        for sub in session.substitutions:
            active_archons.add(sub.failed_archon_id)

        # Find first available archon not in session
        for archon in all_archons:
            if archon.id not in active_archons:
                return archon.id

        # No substitute available (pool exhausted)
        return None

    async def prepare_context_handoff(
        self,
        session: DeliberationSession,
        failed_archon_id: UUID,
    ) -> ContextHandoff:
        """Prepare context for substitute Archon (Story 2B.4, AC-3).

        Gathers all relevant context from the session so the substitute
        can continue deliberation seamlessly.

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

        # Convert votes to string outcome names for serialization
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
        """Execute full substitution workflow (Story 2B.4, AC-1 through AC-9).

        This is the main entry point for handling Archon failure:

        1. Validate failure can be handled
        2. Check if substitution is allowed (max 1 per session)
        3. Select substitute from pool
        4. Prepare context handoff
        5. Record substitution in session
        6. Emit ArchonSubstitutedEvent

        If substitution cannot proceed (pool exhausted, limit exceeded):
        - Abort session with ESCALATE outcome
        - Emit DeliberationAbortedEvent

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

        start_time_ms = self._time_ms()

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
            latency_ms = self._time_ms() - start_time_ms
            return await self._abort_insufficient_archons(
                session, failed_archon_id, failure_reason, latency_ms
            )

        # Select substitute from pool
        substitute_id = await self.select_substitute(session, failed_archon_id)
        if substitute_id is None:
            # Pool exhausted - must abort
            latency_ms = self._time_ms() - start_time_ms
            return await self._abort_pool_exhausted(
                session, failed_archon_id, failure_reason, latency_ms
            )

        # Prepare context handoff
        context = await self.prepare_context_handoff(session, failed_archon_id)

        # Calculate latency before session update
        latency_ms = self._time_ms() - start_time_ms

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
            substitution_latency_ms=latency_ms,
            transcript_pages_provided=len(context.transcript_pages),
        )

        # Emit event if event emitter available
        if self._event_emitter is not None:
            if hasattr(self._event_emitter, "append_event"):
                await self._event_emitter.append_event(event)
            elif hasattr(self._event_emitter, "emit"):
                await self._event_emitter.emit(event)

        # Store updated session
        self._sessions[session.session_id] = updated_session

        return SubstitutionResult(
            success=True,
            session=updated_session,
            event=event,
            substitute_archon_id=substitute_id,
            latency_ms=latency_ms,
            met_sla=latency_ms <= MAX_SUBSTITUTION_LATENCY_MS,
        )

    async def _abort_insufficient_archons(
        self,
        session: DeliberationSession,
        failed_archon_id: UUID,
        failure_reason: str,
        latency_ms: int,
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
            latency_ms=latency_ms,
            met_sla=latency_ms <= MAX_SUBSTITUTION_LATENCY_MS,
        )

    async def _abort_pool_exhausted(
        self,
        session: DeliberationSession,
        failed_archon_id: UUID,
        failure_reason: str,
        latency_ms: int,
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
            latency_ms=latency_ms,
            met_sla=latency_ms <= MAX_SUBSTITUTION_LATENCY_MS,
        )

    async def abort_deliberation(
        self,
        session: DeliberationSession,
        reason: str,
        failed_archons: list[dict[str, str]],
    ) -> tuple[DeliberationSession, DeliberationAbortedEvent]:
        """Abort deliberation when substitution is not possible (Story 2B.4, AC-7, AC-8).

        Called when:
        - 2+ Archons have failed (INSUFFICIENT_ARCHONS)
        - Pool is exhausted (ARCHON_POOL_EXHAUSTED)

        Terminates session with ESCALATE outcome per CT-11.

        Args:
            session: The deliberation session.
            reason: Why abort occurred (INSUFFICIENT_ARCHONS or ARCHON_POOL_EXHAUSTED).
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

        # Emit event if event emitter available
        if self._event_emitter is not None:
            if hasattr(self._event_emitter, "append_event"):
                await self._event_emitter.append_event(event)
            elif hasattr(self._event_emitter, "emit"):
                await self._event_emitter.emit(event)

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

        Returns the current panel, accounting for any substitutions.

        Args:
            session_id: UUID of the deliberation session.

        Returns:
            Tuple of active Archon UUIDs (should always be 3 if session active).

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
