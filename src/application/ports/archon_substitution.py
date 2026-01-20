"""Archon substitution protocol (Story 2B.4, NFR-10.6).

This module defines the protocol for Archon failure detection and substitution
during deliberation. When an Archon fails mid-deliberation, a substitute can be
assigned to continue (within SLA limits).

Constitutional Constraints:
- FR-11.12: System SHALL detect individual Archon response timeout
- NFR-10.6: Archon substitution latency < 10 seconds on failure
- NFR-10.2: Individual Archon response time p95 < 30 seconds
- CT-11: Silent failure destroys legitimacy - failures must be handled
- AT-1: Every petition terminates in exactly one of Three Fates
- AT-6: Deliberation is collective judgment (need 3 active Archons)
- NFR-10.4: 100% witness completeness
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from src.domain.events.archon_substitution import (
    ArchonSubstitutedEvent,
    DeliberationAbortedEvent,
)
from src.domain.models.deliberation_session import (
    ArchonSubstitution,
    DeliberationPhase,
    DeliberationSession,
)


@dataclass(frozen=True)
class SubstitutionResult:
    """Result of an Archon substitution attempt (Story 2B.4, AC-4, AC-6).

    Attributes:
        success: Whether substitution succeeded.
        session: Updated session with substitution recorded (if successful).
        event: ArchonSubstitutedEvent or DeliberationAbortedEvent.
        substitute_archon_id: ID of substitute (if successful).
        latency_ms: Time taken for substitution (ms).
        met_sla: Whether latency was within NFR-10.6 limit (10 seconds).
    """

    success: bool
    session: DeliberationSession
    event: ArchonSubstitutedEvent | DeliberationAbortedEvent
    substitute_archon_id: UUID | None
    latency_ms: int
    met_sla: bool


@dataclass(frozen=True)
class ContextHandoff:
    """Context provided to substitute Archon (Story 2B.4, AC-3).

    Contains transcript pages and other context needed for the substitute
    to continue deliberation from where the failed Archon left off.

    Attributes:
        session_id: Deliberation session ID.
        petition_id: Petition being deliberated.
        current_phase: Phase when failure occurred.
        transcript_pages: Transcript content from completed phases.
        previous_votes: Votes recorded so far (if any).
        round_count: Current voting round.
    """

    session_id: UUID
    petition_id: UUID
    current_phase: DeliberationPhase
    transcript_pages: tuple[bytes, ...]
    previous_votes: dict[UUID, str]
    round_count: int


class ArchonSubstitutionProtocol(Protocol):
    """Protocol for Archon substitution during deliberation (Story 2B.4, NFR-10.6).

    Implementations handle detection of Archon failure and orchestrate
    substitution with a replacement Archon from the pool.

    Constitutional Constraints:
    - NFR-10.6: Substitution latency < 10 seconds
    - FR-11.12: Detect individual Archon response timeout
    - CT-11: Silent failure destroys legitimacy
    - AT-6: Need 3 active Archons for collective judgment
    """

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
        ...

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
        ...

    async def select_substitute(
        self,
        session: DeliberationSession,
        failed_archon_id: UUID,
    ) -> UUID | None:
        """Select a substitute Archon from the pool (Story 2B.4, AC-2).

        Selection criteria:
        1. Must be Marquis-rank
        2. Must not be currently assigned to this session
        3. Must be available (not in another deliberation)

        Args:
            session: The deliberation session.
            failed_archon_id: ID of the Archon being replaced.

        Returns:
            UUID of selected substitute, or None if pool exhausted.
        """
        ...

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
        ...

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
        ...

    async def abort_deliberation(
        self,
        session: DeliberationSession,
        reason: str,
        failed_archons: list[dict[str, str]],
    ) -> tuple[DeliberationSession, DeliberationAbortedEvent]:
        """Abort deliberation when substitution is not possible (Story 2B.4, AC-7, AC-8).

        Called when:
        - 2+ Archons have failed
        - Pool is exhausted (no available substitutes)

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
        ...

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
        ...

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
        ...
