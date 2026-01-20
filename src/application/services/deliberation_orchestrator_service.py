"""Deliberation orchestrator service implementation (Story 2A.4, FR-11.4).

This module implements the DeliberationOrchestratorProtocol for coordinating
the Three Fates deliberation protocol: ASSESS -> POSITION -> CROSS_EXAMINE -> VOTE.

Constitutional Constraints:
- FR-11.4: Deliberation SHALL follow structured protocol
- FR-11.5: System SHALL require supermajority consensus (2-of-3)
- FR-11.9: Timeout enforcement with auto-ESCALATE on expiry (Story 2B.2)
- FR-11.10: Auto-ESCALATE after 3 rounds without supermajority (Story 2B.3)
- AT-6: Deliberation is collective judgment, not unilateral decision
- HC-7: Deliberation timeout auto-ESCALATE - Prevent stuck petitions
- CT-11: Silent failure destroys legitimacy - deadlock MUST terminate
- NFR-10.1: Deliberation end-to-end latency p95 < 5 minutes
- NFR-10.3: Consensus determinism - 100% reproducible
- NFR-3.4: Timeout reliability - 100% timeouts fire
"""

from __future__ import annotations

import asyncio
import threading
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from src.application.ports.deliberation_orchestrator import PhaseExecutorProtocol
from src.config.deliberation_config import (
    DEFAULT_DELIBERATION_CONFIG,
    DeliberationConfig,
)
from src.domain.errors.deliberation import (
    ConsensusNotReachedError,
    PetitionSessionMismatchError,
)
from src.domain.events.deadlock import DeadlockDetectedEvent
from src.domain.models.deliberation_context_package import DeliberationContextPackage
from src.domain.models.deliberation_result import DeliberationResult, PhaseResult
from src.domain.models.deliberation_session import (
    DeliberationPhase,
    DeliberationSession,
)

if TYPE_CHECKING:
    from src.application.ports.deadlock_handler import DeadlockHandlerProtocol
    from src.application.ports.deliberation_timeout import DeliberationTimeoutProtocol


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
    - Timeout scheduled at start, cancelled on normal completion (Story 2B.2)
    - Deadlock detection after 3 rounds without consensus (Story 2B.3)

    Example:
        >>> executor = CrewAIDeliberationAdapter()
        >>> timeout_handler = DeliberationTimeoutService(scheduler)
        >>> deadlock_handler = DeadlockHandlerService(session_repo)
        >>> orchestrator = DeliberationOrchestratorService(
        ...     executor, timeout_handler, deadlock_handler
        ... )
        >>> result = await orchestrator.orchestrate(session, package)
        >>> assert result.outcome in [ACKNOWLEDGE, REFER, ESCALATE]

    Constitutional Constraints:
    - FR-11.4: Structured protocol execution
    - FR-11.5: 2-of-3 supermajority for disposition
    - FR-11.9: Timeout enforcement (5 min default)
    - FR-11.10: Auto-ESCALATE after 3 rounds without supermajority (deadlock)
    - AT-6: Collective judgment via consensus
    - HC-7: Auto-ESCALATE on timeout
    - CT-11: Deadlock MUST terminate (no silent failures)
    - NFR-3.4: Timeout reliability
    """

    def __init__(
        self,
        executor: PhaseExecutorProtocol,
        timeout_handler: DeliberationTimeoutProtocol | None = None,
        deadlock_handler: DeadlockHandlerProtocol | None = None,
        config: DeliberationConfig | None = None,
    ) -> None:
        """Initialize orchestrator with a phase executor.

        Args:
            executor: Protocol implementation for executing phases.
                In production, this will be the CrewAI adapter.
                In tests, this will be a stub or mock.
            timeout_handler: Optional protocol for timeout management.
                If provided, timeouts will be scheduled at start and
                cancelled on normal completion (Story 2B.2, FR-11.9).
            deadlock_handler: Optional protocol for deadlock detection.
                If provided, handles 1-1-1 vote splits and triggers
                retry rounds or auto-ESCALATE (Story 2B.3, FR-11.10).
            config: Deliberation configuration (timeout, max_rounds).
                If not provided, uses DEFAULT_DELIBERATION_CONFIG.
        """
        self._executor = executor
        self._timeout_handler = timeout_handler
        self._deadlock_handler = deadlock_handler
        self._config = config or DEFAULT_DELIBERATION_CONFIG

    def orchestrate(
        self,
        session: DeliberationSession,
        package: DeliberationContextPackage,
    ) -> DeliberationResult:
        """Orchestrate the complete deliberation protocol.

        Executes the 4-phase protocol in strict sequence, updates session
        state through each phase, and returns the complete result with
        outcome and transcripts.

        Timeout Handling (Story 2B.2, FR-11.9):
        - Timeout is scheduled at start (if timeout_handler provided)
        - Timeout is cancelled on normal completion
        - If timeout fires before completion, session is auto-ESCALATED (HC-7)

        Deadlock Handling (Story 2B.3, FR-11.10):
        - When a 1-1-1 vote split occurs and deadlock_handler is provided:
          - If round_count < max_rounds: return to CROSS_EXAMINE for retry
          - If round_count >= max_rounds: auto-ESCALATE (deadlock)
        - Without deadlock_handler, ConsensusNotReachedError is raised

        The session is updated (immutably) between phases:
        1. After ASSESS: Record transcript hash, transition to POSITION
        2. After POSITION: Record transcript hash, transition to CROSS_EXAMINE
        3. After CROSS_EXAMINE: Record transcript hash, transition to VOTE
        4. After VOTE: Record transcript hash, record votes, resolve outcome
           - On 1-1-1 split: may loop back to step 3 (if not deadlocked)

        Args:
            session: The deliberation session with assigned archons.
            package: The context package for deliberation.

        Returns:
            DeliberationResult with outcome and all phase results.

        Raises:
            PetitionSessionMismatchError: If package doesn't match session.
            InvalidPhaseTransitionError: If phase sequence is violated.
            ConsensusNotReachedError: If votes don't reach consensus and
                no deadlock_handler is configured.
        """
        # Validate session-package relationship
        if session.petition_id != package.petition_id:
            raise PetitionSessionMismatchError(
                petition_id=package.petition_id,
                session_petition_id=session.petition_id,
            )

        started_at = datetime.now(timezone.utc)
        phase_results: list[PhaseResult] = []

        # FR-11.9: Schedule timeout at start of deliberation
        if self._timeout_handler is not None:
            session = self._run_async(self._timeout_handler.schedule_timeout(session))

        try:
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

            # Phases 3-4: CROSS_EXAMINE -> VOTE loop (supports retry on 1-1-1 split)
            # FR-11.10: Loop may repeat up to max_rounds times before deadlock
            session = self._execute_cross_examine_vote_loop(
                session, package, position_result, phase_results
            )

            # FR-11.9: Cancel timeout on normal completion
            if self._timeout_handler is not None:
                session = self._run_async(self._timeout_handler.cancel_timeout(session))

        except Exception:
            # Note: On exception, timeout remains scheduled and will fire
            # per HC-7 if deliberation doesn't complete. The job worker
            # will handle the timeout and auto-ESCALATE.
            raise

        completed_at = datetime.now(timezone.utc)

        return DeliberationResult(
            session_id=session.session_id,
            petition_id=session.petition_id,
            outcome=session.outcome,
            votes=dict(session.votes),
            dissent_archon_id=session.dissent_archon_id,
            phase_results=tuple(phase_results),
            started_at=started_at,
            completed_at=completed_at,
        )

    def _execute_cross_examine_vote_loop(
        self,
        session: DeliberationSession,
        package: DeliberationContextPackage,
        position_result: PhaseResult,
        phase_results: list[PhaseResult],
    ) -> DeliberationSession:
        """Execute CROSS_EXAMINE -> VOTE with retry support (FR-11.10).

        This method handles the loop for deadlock detection. On a 1-1-1 split:
        - If round_count < max_rounds: return to CROSS_EXAMINE for retry
        - If round_count >= max_rounds: auto-ESCALATE (deadlock)

        Args:
            session: Current session in CROSS_EXAMINE phase.
            package: Deliberation context package.
            position_result: Result from POSITION phase (needed for first CROSS_EXAMINE).
            phase_results: List to append phase results to (mutated in place).

        Returns:
            Session with outcome resolved (either consensus or deadlock ESCALATE).

        Raises:
            ConsensusNotReachedError: If no consensus and no deadlock_handler.
        """
        # Track the previous result for CROSS_EXAMINE input
        # First round uses position_result, subsequent rounds use previous cross_examine
        previous_result = position_result

        while True:
            # Phase 3: CROSS_EXAMINE
            cross_examine_result = self._executor.execute_cross_examine(
                session, package, previous_result
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

            # Try to resolve outcome from votes
            try:
                session = session.with_outcome()
                # Consensus reached (2-1 or 3-0), we're done
                return session

            except ConsensusNotReachedError:
                # 1-1-1 split - handle deadlock logic
                if self._deadlock_handler is None:
                    # No handler configured, propagate error
                    raise

                # FR-11.10: Use deadlock handler to decide next action
                vote_distribution: dict[str, int] = {}
                for vote in votes.values():
                    vote_key = vote.value if hasattr(vote, "value") else str(vote)
                    vote_distribution[vote_key] = vote_distribution.get(vote_key, 0) + 1

                session, event = self._run_async(
                    self._deadlock_handler.handle_no_consensus(
                        session=session,
                        vote_distribution=vote_distribution,
                        max_rounds=self._config.max_rounds,
                    )
                )

                if isinstance(event, DeadlockDetectedEvent):
                    # Deadlock detected, session has ESCALATE outcome
                    # Session is already in COMPLETE phase with outcome set
                    return session

                # CrossExamineRoundTriggeredEvent - retry with new round
                # Session is back in CROSS_EXAMINE phase with incremented round
                # Update previous_result for next iteration
                previous_result = cross_examine_result
                # Continue the loop for another CROSS_EXAMINE -> VOTE cycle

    @staticmethod
    def _run_async(coro: Any) -> Any:
        """Run a coroutine in sync context, even if an event loop is running."""
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coro)

        result: Any = None
        error: BaseException | None = None

        def _runner() -> None:
            nonlocal result, error
            try:
                result = asyncio.run(coro)
            except BaseException as exc:  # pragma: no cover - passthrough
                error = exc

        thread = threading.Thread(target=_runner, daemon=True)
        thread.start()
        thread.join()

        if error is not None:
            raise error
        return result
