"""Deliberation orchestrator service implementation (Story 2A.4, FR-11.4).

This module implements the DeliberationOrchestratorProtocol for coordinating
the Three Fates deliberation protocol: ASSESS -> POSITION -> CROSS_EXAMINE -> VOTE.

Constitutional Constraints:
- FR-11.4: Deliberation SHALL follow structured protocol
- FR-11.5: System SHALL require supermajority consensus (2-of-3)
- AT-6: Deliberation is collective judgment, not unilateral decision
- NFR-10.1: Deliberation end-to-end latency p95 < 5 minutes
- NFR-10.3: Consensus determinism - 100% reproducible
"""

from __future__ import annotations

from datetime import datetime, timezone

from src.application.ports.deliberation_orchestrator import PhaseExecutorProtocol
from src.domain.errors.deliberation import PetitionSessionMismatchError
from src.domain.models.deliberation_context_package import DeliberationContextPackage
from src.domain.models.deliberation_result import DeliberationResult, PhaseResult
from src.domain.models.deliberation_session import (
    DeliberationPhase,
    DeliberationSession,
)


class DeliberationOrchestratorService:
    """Service for orchestrating the 4-phase deliberation protocol (Story 2A.4).

    Coordinates the execution of ASSESS -> POSITION -> CROSS_EXAMINE -> VOTE
    phases in strict sequence, collecting results and resolving consensus.

    The orchestrator is decoupled from actual phase execution via the
    PhaseExecutorProtocol, allowing for different implementations:
    - CrewAI adapter for production
    - Stub implementation for testing
    - Mock implementations for specific test scenarios

    Key Guarantees:
    - Strict phase sequence (no skipping, no out-of-order)
    - Session state updated between phases
    - Transcript hashes recorded for each phase
    - Supermajority consensus resolution

    Example:
        >>> executor = CrewAIDeliberationAdapter()
        >>> orchestrator = DeliberationOrchestratorService(executor)
        >>> result = orchestrator.orchestrate(session, package)
        >>> assert result.outcome in [ACKNOWLEDGE, REFER, ESCALATE]

    Constitutional Constraints:
    - FR-11.4: Structured protocol execution
    - FR-11.5: 2-of-3 supermajority for disposition
    - AT-6: Collective judgment via consensus
    """

    def __init__(self, executor: PhaseExecutorProtocol) -> None:
        """Initialize orchestrator with a phase executor.

        Args:
            executor: Protocol implementation for executing phases.
                In production, this will be the CrewAI adapter.
                In tests, this will be a stub or mock.
        """
        self._executor = executor

    def orchestrate(
        self,
        session: DeliberationSession,
        package: DeliberationContextPackage,
    ) -> DeliberationResult:
        """Orchestrate the complete deliberation protocol.

        Executes the 4-phase protocol in strict sequence, updates session
        state through each phase, and returns the complete result with
        outcome and transcripts.

        The session is updated (immutably) between phases:
        1. After ASSESS: Record transcript hash, transition to POSITION
        2. After POSITION: Record transcript hash, transition to CROSS_EXAMINE
        3. After CROSS_EXAMINE: Record transcript hash, transition to VOTE
        4. After VOTE: Record transcript hash, record votes, resolve outcome

        Args:
            session: The deliberation session with assigned archons.
            package: The context package for deliberation.

        Returns:
            DeliberationResult with outcome and all phase results.

        Raises:
            PetitionSessionMismatchError: If package doesn't match session.
            InvalidPhaseTransitionError: If phase sequence is violated.
            ConsensusNotReachedError: If votes don't reach 2-of-3 consensus.
        """
        # Validate session-package relationship
        if session.petition_id != package.petition_id:
            raise PetitionSessionMismatchError(
                petition_id=package.petition_id,
                session_petition_id=session.petition_id,
            )

        started_at = datetime.now(timezone.utc)
        phase_results: list[PhaseResult] = []

        # Phase 1: ASSESS
        assess_result = self._executor.execute_assess(session, package)
        phase_results.append(assess_result)
        session = session.with_transcript(
            DeliberationPhase.ASSESS, assess_result.transcript_hash
        )
        session = session.with_phase(DeliberationPhase.POSITION)

        # Phase 2: POSITION
        position_result = self._executor.execute_position(
            session, package, assess_result
        )
        phase_results.append(position_result)
        session = session.with_transcript(
            DeliberationPhase.POSITION, position_result.transcript_hash
        )
        session = session.with_phase(DeliberationPhase.CROSS_EXAMINE)

        # Phase 3: CROSS_EXAMINE
        cross_examine_result = self._executor.execute_cross_examine(
            session, package, position_result
        )
        phase_results.append(cross_examine_result)
        session = session.with_transcript(
            DeliberationPhase.CROSS_EXAMINE, cross_examine_result.transcript_hash
        )
        session = session.with_phase(DeliberationPhase.VOTE)

        # Phase 4: VOTE
        vote_result = self._executor.execute_vote(
            session, package, cross_examine_result
        )
        phase_results.append(vote_result)
        session = session.with_transcript(
            DeliberationPhase.VOTE, vote_result.transcript_hash
        )

        # Extract votes from vote result metadata
        votes = vote_result.phase_metadata.get("votes", {})
        session = session.with_votes(votes)

        # Resolve outcome from votes (determines dissent if 2-1)
        session = session.with_outcome()

        completed_at = datetime.now(timezone.utc)

        return DeliberationResult(
            session_id=session.session_id,
            petition_id=session.petition_id,
            outcome=session.outcome,  # type: ignore[arg-type]  # with_outcome guarantees non-None
            votes=dict(session.votes),
            dissent_archon_id=session.dissent_archon_id,
            phase_results=tuple(phase_results),
            started_at=started_at,
            completed_at=completed_at,
        )
