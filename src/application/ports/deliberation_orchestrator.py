"""Deliberation orchestrator protocols (Story 2A.4, FR-11.4).

This module defines the protocols for orchestrating the Three Fates
deliberation protocol. The orchestrator coordinates phase execution
while the executor handles actual agent interaction.

Constitutional Constraints:
- FR-11.4: Deliberation SHALL follow structured protocol
- FR-11.5: System SHALL require supermajority consensus (2-of-3)
- NFR-10.1: Deliberation end-to-end latency p95 < 5 minutes
- NFR-10.3: Consensus determinism - 100% reproducible
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from src.domain.models.deliberation_context_package import (
        DeliberationContextPackage,
    )
    from src.domain.models.deliberation_result import (
        DeliberationResult,
        PhaseResult,
    )
    from src.domain.models.deliberation_session import DeliberationSession


class PhaseExecutorProtocol(Protocol):
    """Protocol for executing individual deliberation phases (Story 2A.4).

    Implementations execute a single phase of the deliberation protocol,
    collecting responses from Archons and returning a PhaseResult.

    This protocol decouples the orchestrator from the actual execution
    mechanism, allowing for:
    - CrewAI adapter for production
    - Stub implementation for testing
    - Mock implementations for specific scenarios

    Constitutional Constraints:
    - NFR-10.2: Individual Archon response time p95 < 30 seconds
    - NFR-10.4: Witness completeness - transcript captured for each phase
    """

    def execute_assess(
        self,
        session: DeliberationSession,
        package: DeliberationContextPackage,
    ) -> PhaseResult:
        """Execute ASSESS phase - independent assessments.

        Phase 1 of the deliberation protocol. Each Archon receives the
        context package and produces an independent assessment of the
        petition without seeing other assessments.

        Args:
            session: The deliberation session with assigned archons.
            package: The context package for deliberation.

        Returns:
            PhaseResult with ASSESS phase transcript and hash.

        Raises:
            PhaseExecutionError: If phase execution fails.
        """
        ...

    def execute_position(
        self,
        session: DeliberationSession,
        package: DeliberationContextPackage,
        assess_result: PhaseResult,
    ) -> PhaseResult:
        """Execute POSITION phase - state preferred dispositions.

        Phase 2 of the deliberation protocol. Each Archon states their
        preferred disposition (ACKNOWLEDGE, REFER, or ESCALATE) with
        rationale. Positions are sequential, allowing each Archon to
        see previous positions.

        Args:
            session: The deliberation session with assigned archons.
            package: The context package for deliberation.
            assess_result: Result from the ASSESS phase.

        Returns:
            PhaseResult with POSITION phase transcript and hash.

        Raises:
            PhaseExecutionError: If phase execution fails.
        """
        ...

    def execute_cross_examine(
        self,
        session: DeliberationSession,
        package: DeliberationContextPackage,
        position_result: PhaseResult,
    ) -> PhaseResult:
        """Execute CROSS_EXAMINE phase - challenge positions.

        Phase 3 of the deliberation protocol. Archons may challenge
        each other's positions with a maximum of 3 rounds of exchange.
        Phase ends when no new challenges are raised or max rounds reached.

        Args:
            session: The deliberation session with assigned archons.
            package: The context package for deliberation.
            position_result: Result from the POSITION phase.

        Returns:
            PhaseResult with CROSS_EXAMINE phase transcript and hash.
            Phase metadata includes "challenges_raised" and "rounds_completed".

        Raises:
            PhaseExecutionError: If phase execution fails.
        """
        ...

    def execute_vote(
        self,
        session: DeliberationSession,
        package: DeliberationContextPackage,
        cross_examine_result: PhaseResult,
    ) -> PhaseResult:
        """Execute VOTE phase - cast final votes.

        Phase 4 of the deliberation protocol. Each Archon casts a final
        vote for ACKNOWLEDGE, REFER, or ESCALATE. Votes are simultaneous
        (no Archon can see others' votes before casting).

        The phase_metadata in the returned PhaseResult MUST include:
        - "votes": Dict[UUID, DeliberationOutcome] mapping archon_id to vote

        Args:
            session: The deliberation session with assigned archons.
            package: The context package for deliberation.
            cross_examine_result: Result from the CROSS_EXAMINE phase.

        Returns:
            PhaseResult with VOTE phase transcript, hash, and votes in metadata.

        Raises:
            PhaseExecutionError: If phase execution fails.
        """
        ...


class DeliberationOrchestratorProtocol(Protocol):
    """Protocol for orchestrating the deliberation protocol (Story 2A.4, FR-11.4).

    Implementations coordinate the 4-phase deliberation protocol,
    ensuring strict phase sequence and collecting results.

    The orchestrator:
    1. Executes phases in strict sequence (ASSESS -> POSITION -> CROSS_EXAMINE -> VOTE)
    2. Updates session state between phases
    3. Collects and records phase transcripts
    4. Resolves supermajority consensus from votes

    Constitutional Constraints:
    - FR-11.4: Structured protocol execution
    - FR-11.5: Supermajority consensus resolution
    - AT-6: Collective judgment via 2-of-3 agreement
    - NFR-10.1: Total deliberation p95 < 5 minutes
    """

    def orchestrate(
        self,
        session: DeliberationSession,
        package: DeliberationContextPackage,
    ) -> DeliberationResult:
        """Orchestrate the complete deliberation protocol.

        Executes the 4-phase protocol in strict sequence:
        ASSESS -> POSITION -> CROSS_EXAMINE -> VOTE

        Each phase:
        1. Executes via the PhaseExecutor
        2. Records transcript hash in session
        3. Transitions session to next phase

        After all phases, resolves votes to determine outcome
        and identifies any dissenting Archon.

        Args:
            session: The deliberation session with assigned archons.
                Must be in ASSESS phase with 3 assigned archons.
            package: The context package for deliberation.
                Must match session's petition_id.

        Returns:
            DeliberationResult with:
            - outcome: The resolved disposition (ACKNOWLEDGE, REFER, ESCALATE)
            - votes: All 3 archon votes
            - dissent_archon_id: UUID of dissenter in 2-1 vote (or None)
            - phase_results: All 4 phase results with transcripts

        Raises:
            DeliberationError: If orchestration fails.
            PetitionSessionMismatchError: If package.petition_id != session.petition_id.
            InvalidPhaseTransitionError: If phase sequence is violated.
            ConsensusNotReachedError: If votes don't reach 2-of-3 consensus.

        Example:
            >>> orchestrator = DeliberationOrchestratorService(executor)
            >>> result = orchestrator.orchestrate(session, package)
            >>> assert result.outcome in [ACKNOWLEDGE, REFER, ESCALATE]
            >>> assert len(result.phase_results) == 4
        """
        ...
