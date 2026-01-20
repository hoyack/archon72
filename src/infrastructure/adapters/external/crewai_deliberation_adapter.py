"""CrewAI deliberation adapter for Three Fates protocol (Story 2A.5, FR-11.4).

This adapter implements PhaseExecutorProtocol using CrewAI to execute
deliberation phases with Marquis-rank Archons. Each phase invokes the
assigned archons with phase-specific prompts and collects their responses.

Constitutional Constraints:
- FR-11.4: Deliberation SHALL follow structured protocol
- NFR-10.2: Individual Archon response time p95 < 30 seconds
- NFR-10.4: Witness completeness - transcript captured for each phase
- CT-12: Witnessing creates accountability - Blake3 transcript hashes
"""

from __future__ import annotations

import asyncio
import threading
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any
from uuid import UUID

import blake3
from structlog import get_logger

from src.application.ports.archon_profile_repository import ArchonProfileRepository
from src.application.ports.deliberation_orchestrator import PhaseExecutorProtocol
from src.domain.errors.deliberation import PhaseExecutionError
from src.domain.models.deliberation_result import PhaseResult
from src.domain.models.deliberation_session import (
    DeliberationOutcome,
    DeliberationPhase,
)
from src.infrastructure.adapters.config.archon_profile_adapter import (
    create_archon_profile_repository,
)
from src.infrastructure.adapters.external.crewai_llm_factory import create_crewai_llm

if TYPE_CHECKING:
    from src.domain.models.archon_profile import ArchonProfile
    from src.domain.models.deliberation_context_package import (
        DeliberationContextPackage,
    )
    from src.domain.models.deliberation_session import DeliberationSession

logger = get_logger(__name__)

# NFR-10.2: Individual Archon response time p95 < 30 seconds
DEFAULT_ARCHON_TIMEOUT_SECONDS = 30

# Maximum cross-examination rounds (Story 2A.5 AC-4)
MAX_CROSS_EXAMINE_ROUNDS = 3


def _utc_now() -> datetime:
    """Return current UTC time with timezone info."""
    return datetime.now(timezone.utc)


def _compute_blake3_hash(content: str) -> bytes:
    """Compute Blake3 hash of content (NFR-10.4).

    Args:
        content: Text content to hash.

    Returns:
        32-byte Blake3 hash.
    """
    return blake3.blake3(content.encode("utf-8")).digest()


class CrewAIDeliberationAdapter(PhaseExecutorProtocol):
    """CrewAI implementation of deliberation phase execution (Story 2A.5).

    This adapter executes the 4-phase deliberation protocol using CrewAI
    to invoke Archon agents. Each phase has specific execution patterns:

    - ASSESS: Concurrent execution (archons work independently)
    - POSITION: Sequential execution (each archon sees previous positions)
    - CROSS_EXAMINE: Turn-based with max 3 rounds
    - VOTE: Concurrent execution (simultaneous voting)

    AC1: Implements PhaseExecutorProtocol
    AC2: Executes ASSESS phase with concurrent archon invocations
    AC3: Executes POSITION phase with sequential archon invocations
    AC4: Executes CROSS_EXAMINE phase with up to 3 rounds
    AC5: Executes VOTE phase with simultaneous vote collection
    AC6: Blake3 transcript hashing for integrity

    Attributes:
        _profile_repo: Repository for looking up Archon profiles.
        _timeout_seconds: Timeout for individual archon responses.
        _verbose: Whether to enable verbose CrewAI logging.
    """

    def __init__(
        self,
        profile_repository: ArchonProfileRepository,
        timeout_seconds: int = DEFAULT_ARCHON_TIMEOUT_SECONDS,
        verbose: bool = False,
    ) -> None:
        """Initialize CrewAIDeliberationAdapter.

        Args:
            profile_repository: Repository for Archon profile lookup.
            timeout_seconds: Timeout per archon (NFR-10.2 default: 30s).
            verbose: Enable verbose CrewAI logging.
        """
        self._profile_repo = profile_repository
        self._timeout_seconds = timeout_seconds
        self._verbose = verbose

        logger.info(
            "crewai_deliberation_adapter_initialized",
            timeout_seconds=timeout_seconds,
            verbose=verbose,
        )

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

    def _get_archon_profile(self, archon_id: UUID) -> ArchonProfile:
        """Get archon profile by ID.

        Args:
            archon_id: UUID of the archon.

        Returns:
            ArchonProfile for the archon.

        Raises:
            PhaseExecutionError: If archon not found.
        """
        profile = self._profile_repo.get_by_id(archon_id)
        if profile is None:
            raise PhaseExecutionError(
                phase=DeliberationPhase.ASSESS,
                reason=f"Archon {archon_id} not found in profile repository",
                archon_id=archon_id,
            )
        return profile

    async def _invoke_archon(
        self,
        archon_id: UUID,
        prompt: str,
        phase: DeliberationPhase,
    ) -> str:
        """Invoke a single archon with a prompt.

        Uses CrewAI to invoke the archon's LLM with the given prompt.
        Respects NFR-10.2 timeout constraint.

        Args:
            archon_id: UUID of the archon to invoke.
            prompt: The prompt to send to the archon.
            phase: Current phase (for error context).

        Returns:
            Archon's response text.

        Raises:
            PhaseExecutionError: If invocation fails or times out.
        """
        profile = self._get_archon_profile(archon_id)

        try:

            def _run_crew() -> str:
                from crewai import Agent, Crew, Task

                llm = create_crewai_llm(profile.llm_config)

                # Create agent with archon's personality
                agent = Agent(
                    role=profile.role,
                    goal=profile.goal,
                    backstory=profile.backstory,
                    verbose=self._verbose,
                    allow_delegation=False,  # No delegation in deliberation
                    llm=llm,
                )

                # Create task
                task = Task(
                    description=prompt,
                    expected_output="A structured response to the deliberation prompt",
                    agent=agent,
                )

                # Create single-agent crew
                crew = Crew(
                    agents=[agent],
                    tasks=[task],
                    verbose=self._verbose,
                )

                return str(crew.kickoff())

            # Execute with timeout (NFR-10.2: 30s)
            result = await asyncio.wait_for(
                asyncio.to_thread(_run_crew),
                timeout=self._timeout_seconds,
            )
            response = str(result)

            logger.debug(
                "archon_invocation_complete",
                archon_id=str(archon_id),
                archon_name=profile.name,
                phase=phase.value,
                response_length=len(response),
            )

            return response

        except TimeoutError:
            logger.error(
                "archon_invocation_timeout",
                archon_id=str(archon_id),
                phase=phase.value,
                timeout_seconds=self._timeout_seconds,
            )
            raise PhaseExecutionError(
                phase=phase,
                reason=f"Archon response timed out after {self._timeout_seconds}s",
                archon_id=archon_id,
            ) from None

        except Exception as e:
            logger.error(
                "archon_invocation_failed",
                archon_id=str(archon_id),
                phase=phase.value,
                error=str(e),
            )
            raise PhaseExecutionError(
                phase=phase,
                reason=f"Archon invocation failed: {e}",
                archon_id=archon_id,
            ) from e

    def _build_assess_prompt(
        self,
        archon_id: UUID,
        package: DeliberationContextPackage,
    ) -> str:
        """Build ASSESS phase prompt for an archon.

        Args:
            archon_id: UUID of the archon.
            package: Context package with petition data.

        Returns:
            Prompt string for ASSESS phase.
        """
        profile = self._get_archon_profile(archon_id)
        return f"""You are {profile.name}, a Marquis-rank Archon participating in a Three Fates deliberation.

PHASE: ASSESS (Independent Assessment)

Your task is to independently assess this petition. Do NOT consider what other Archons might think - provide your own analysis.

PETITION DETAILS:
- Petition ID: {package.petition_id}
- Type: {package.petition_type}
- Realm: {package.realm}
- Co-signers: {package.co_signer_count}
- Submitted: {package.submitted_at.isoformat()}

PETITION TEXT:
{package.petition_text}

Provide your independent assessment covering:
1. Nature and legitimacy of the petition
2. Potential impacts and considerations
3. Relevant constitutional or procedural factors
4. Initial disposition tendency (ACKNOWLEDGE, REFER, or ESCALATE)

Be thorough but concise. Your assessment will inform subsequent deliberation phases."""

    def _build_position_prompt(
        self,
        archon_id: UUID,
        package: DeliberationContextPackage,
        previous_positions: list[tuple[UUID, str]],
    ) -> str:
        """Build POSITION phase prompt for an archon.

        Args:
            archon_id: UUID of the archon.
            package: Context package with petition data.
            previous_positions: List of (archon_id, position_text) from previous archons.

        Returns:
            Prompt string for POSITION phase.
        """
        profile = self._get_archon_profile(archon_id)

        previous_section = ""
        if previous_positions:
            positions_text = "\n\n".join(
                f"--- Position from Archon {self._get_archon_profile(aid).name} ---\n{pos}"
                for aid, pos in previous_positions
            )
            previous_section = f"""
PREVIOUS POSITIONS (you may consider but are not bound by these):
{positions_text}

"""

        return f"""You are {profile.name}, a Marquis-rank Archon participating in a Three Fates deliberation.

PHASE: POSITION (State Your Preferred Disposition)

Based on your assessment of the petition, you must now state your preferred disposition.
{previous_section}
PETITION SUMMARY:
- Petition ID: {package.petition_id}
- Type: {package.petition_type}
- Co-signers: {package.co_signer_count}

State your preferred disposition choosing from:
- ACKNOWLEDGE: Note the petition, no further action required
- REFER: Route to the relevant Knight for domain-specific review
- ESCALATE: Elevate to the King for adoption consideration

Provide:
1. Your chosen disposition: [ACKNOWLEDGE | REFER | ESCALATE]
2. Clear rationale for your choice
3. Any conditions or caveats"""

    def _build_cross_examine_prompt(
        self,
        archon_id: UUID,
        package: DeliberationContextPackage,
        all_positions: list[tuple[UUID, str]],
        exchange_history: list[str],
    ) -> str:
        """Build CROSS_EXAMINE phase prompt for an archon.

        Args:
            archon_id: UUID of the archon.
            package: Context package with petition data.
            all_positions: All archon positions from POSITION phase.
            exchange_history: Previous exchanges in this round.

        Returns:
            Prompt string for CROSS_EXAMINE phase.
        """
        profile = self._get_archon_profile(archon_id)

        positions_text = "\n\n".join(
            f"--- Position from {self._get_archon_profile(aid).name} ---\n{pos}"
            for aid, pos in all_positions
        )

        history_section = ""
        if exchange_history:
            history_section = f"""
PREVIOUS EXCHANGES THIS ROUND:
{chr(10).join(exchange_history)}

"""

        return f"""You are {profile.name}, a Marquis-rank Archon participating in a Three Fates deliberation.

PHASE: CROSS_EXAMINE (Challenge Positions)

Review the positions stated and determine if you have any challenges or questions.

POSITIONS:
{positions_text}
{history_section}
PETITION: {package.petition_id} ({package.petition_type})

You may:
1. Challenge another Archon's position with a specific question
2. Defend your position if challenged
3. State "NO CHALLENGE" if you accept the current state

Keep responses focused and constructive. We seek consensus through examination."""

    def _build_vote_prompt(
        self,
        archon_id: UUID,
        package: DeliberationContextPackage,
        cross_examine_summary: str,
    ) -> str:
        """Build VOTE phase prompt for an archon.

        Args:
            archon_id: UUID of the archon.
            package: Context package with petition data.
            cross_examine_summary: Summary from CROSS_EXAMINE phase.

        Returns:
            Prompt string for VOTE phase.
        """
        profile = self._get_archon_profile(archon_id)

        return f"""You are {profile.name}, a Marquis-rank Archon participating in a Three Fates deliberation.

PHASE: VOTE (Cast Final Vote)

After assessment, positioning, and cross-examination, you must now cast your final vote.

PETITION: {package.petition_id} ({package.petition_type})

CROSS-EXAMINATION SUMMARY:
{cross_examine_summary}

Cast your FINAL vote. This vote is binding and cannot be changed.

Your response MUST start with one of these exact strings:
- "VOTE: ACKNOWLEDGE" - Note the petition, no further action
- "VOTE: REFER" - Route to Knight for review
- "VOTE: ESCALATE" - Elevate to King for consideration

Then briefly explain your final reasoning."""

    def execute_assess(
        self,
        session: DeliberationSession,
        package: DeliberationContextPackage,
    ) -> PhaseResult:
        """Execute ASSESS phase - independent assessments (AC-2).

        Archons assess the petition concurrently without seeing each other's
        assessments. Uses asyncio.gather for parallel execution.

        Args:
            session: The deliberation session.
            package: The context package.

        Returns:
            PhaseResult for ASSESS phase.

        Raises:
            PhaseExecutionError: If phase execution fails.
        """
        logger.info(
            "assess_phase_starting",
            session_id=str(session.session_id),
            petition_id=str(package.petition_id),
            archon_count=len(session.assigned_archons),
        )

        started_at = _utc_now()

        async def execute_concurrent() -> list[tuple[UUID, str]]:
            """Execute all archon invocations concurrently."""
            tasks = [
                self._invoke_archon(
                    archon_id,
                    self._build_assess_prompt(archon_id, package),
                    DeliberationPhase.ASSESS,
                )
                for archon_id in session.assigned_archons
            ]
            results = await asyncio.gather(*tasks)
            return list(zip(session.assigned_archons, results, strict=True))

        # Run concurrent execution
        assessments = self._run_async(execute_concurrent())

        # Build transcript
        transcript_parts = [
            "=== ASSESS PHASE ===",
            f"Petition ID: {package.petition_id}",
            f"Petition Type: {package.petition_type}",
            f"Session ID: {session.session_id}",
            "",
        ]

        for archon_id, assessment in assessments:
            profile = self._get_archon_profile(archon_id)
            transcript_parts.extend(
                [
                    f"--- Assessment from {profile.name} ({archon_id}) ---",
                    assessment,
                    "",
                ]
            )

        transcript = "\n".join(transcript_parts)
        transcript_hash = _compute_blake3_hash(transcript)
        completed_at = _utc_now()

        logger.info(
            "assess_phase_complete",
            session_id=str(session.session_id),
            duration_ms=int((completed_at - started_at).total_seconds() * 1000),
            transcript_length=len(transcript),
        )

        return PhaseResult(
            phase=DeliberationPhase.ASSESS,
            transcript=transcript,
            transcript_hash=transcript_hash,
            participants=session.assigned_archons,
            started_at=started_at,
            completed_at=completed_at,
            phase_metadata={
                "assessments_completed": len(assessments),
                "petition_type": package.petition_type,
            },
        )

    def execute_position(
        self,
        session: DeliberationSession,
        package: DeliberationContextPackage,
        assess_result: PhaseResult,
    ) -> PhaseResult:
        """Execute POSITION phase - state preferred dispositions (AC-3).

        Archons state positions sequentially, each seeing previous positions.
        This allows for informed positioning while maintaining independent judgment.

        Args:
            session: The deliberation session.
            package: The context package.
            assess_result: Result from ASSESS phase.

        Returns:
            PhaseResult for POSITION phase.

        Raises:
            PhaseExecutionError: If phase execution fails.
        """
        logger.info(
            "position_phase_starting",
            session_id=str(session.session_id),
            petition_id=str(package.petition_id),
        )

        started_at = _utc_now()

        async def execute_sequential() -> list[tuple[UUID, str]]:
            """Execute archon invocations sequentially."""
            positions: list[tuple[UUID, str]] = []
            for archon_id in session.assigned_archons:
                prompt = self._build_position_prompt(archon_id, package, positions)
                response = await self._invoke_archon(
                    archon_id, prompt, DeliberationPhase.POSITION
                )
                positions.append((archon_id, response))
            return positions

        positions = self._run_async(execute_sequential())

        # Build transcript
        transcript_parts = [
            "=== POSITION PHASE ===",
            f"Session ID: {session.session_id}",
            "Archons stating dispositions sequentially.",
            "",
        ]

        for archon_id, position in positions:
            profile = self._get_archon_profile(archon_id)
            transcript_parts.extend(
                [
                    f"--- Position from {profile.name} ({archon_id}) ---",
                    position,
                    "",
                ]
            )

        transcript = "\n".join(transcript_parts)
        transcript_hash = _compute_blake3_hash(transcript)
        completed_at = _utc_now()

        logger.info(
            "position_phase_complete",
            session_id=str(session.session_id),
            duration_ms=int((completed_at - started_at).total_seconds() * 1000),
        )

        return PhaseResult(
            phase=DeliberationPhase.POSITION,
            transcript=transcript,
            transcript_hash=transcript_hash,
            participants=session.assigned_archons,
            started_at=started_at,
            completed_at=completed_at,
            phase_metadata={
                "positions_stated": len(positions),
                "positions": positions,  # Store for CROSS_EXAMINE
            },
        )

    def execute_cross_examine(
        self,
        session: DeliberationSession,
        package: DeliberationContextPackage,
        position_result: PhaseResult,
    ) -> PhaseResult:
        """Execute CROSS_EXAMINE phase - challenge positions (AC-4).

        Archons may challenge each other with up to MAX_CROSS_EXAMINE_ROUNDS
        rounds of exchange. Phase ends when no new challenges are raised.

        Args:
            session: The deliberation session.
            package: The context package.
            position_result: Result from POSITION phase.

        Returns:
            PhaseResult for CROSS_EXAMINE phase.

        Raises:
            PhaseExecutionError: If phase execution fails.
        """
        logger.info(
            "cross_examine_phase_starting",
            session_id=str(session.session_id),
            max_rounds=MAX_CROSS_EXAMINE_ROUNDS,
        )

        started_at = _utc_now()
        all_positions = position_result.get_metadata("positions", [])
        exchange_history: list[str] = []
        rounds_completed = 0
        challenges_raised = 0

        async def execute_round() -> bool:
            """Execute one round of cross-examination. Returns True if challenges raised."""
            nonlocal challenges_raised
            round_had_challenges = False

            for archon_id in session.assigned_archons:
                prompt = self._build_cross_examine_prompt(
                    archon_id, package, all_positions, exchange_history
                )
                response = await self._invoke_archon(
                    archon_id, prompt, DeliberationPhase.CROSS_EXAMINE
                )

                profile = self._get_archon_profile(archon_id)
                exchange_history.append(f"{profile.name}: {response}")

                # Check if this was a challenge (not "NO CHALLENGE")
                if "NO CHALLENGE" not in response.upper():
                    round_had_challenges = True
                    challenges_raised += 1

            return round_had_challenges

        async def run_rounds() -> int:
            """Run cross-examination rounds until done or max reached."""
            nonlocal rounds_completed
            for round_num in range(MAX_CROSS_EXAMINE_ROUNDS):
                rounds_completed = round_num + 1
                exchange_history.append(f"\n--- Round {rounds_completed} ---")
                had_challenges = await execute_round()
                if not had_challenges:
                    break
            return rounds_completed

        self._run_async(run_rounds())

        # Build transcript
        transcript_parts = [
            "=== CROSS_EXAMINE PHASE ===",
            f"Session ID: {session.session_id}",
            f"Maximum rounds: {MAX_CROSS_EXAMINE_ROUNDS}",
            "",
        ]
        transcript_parts.extend(exchange_history)
        transcript_parts.append("\n=== CROSS_EXAMINATION COMPLETE ===")

        transcript = "\n".join(transcript_parts)
        transcript_hash = _compute_blake3_hash(transcript)
        completed_at = _utc_now()

        logger.info(
            "cross_examine_phase_complete",
            session_id=str(session.session_id),
            rounds_completed=rounds_completed,
            challenges_raised=challenges_raised,
            duration_ms=int((completed_at - started_at).total_seconds() * 1000),
        )

        return PhaseResult(
            phase=DeliberationPhase.CROSS_EXAMINE,
            transcript=transcript,
            transcript_hash=transcript_hash,
            participants=session.assigned_archons,
            started_at=started_at,
            completed_at=completed_at,
            phase_metadata={
                "challenges_raised": challenges_raised,
                "rounds_completed": rounds_completed,
                "max_rounds": MAX_CROSS_EXAMINE_ROUNDS,
            },
        )

    def execute_vote(
        self,
        session: DeliberationSession,
        package: DeliberationContextPackage,
        cross_examine_result: PhaseResult,
    ) -> PhaseResult:
        """Execute VOTE phase - cast final votes (AC-5).

        Archons cast votes concurrently (simultaneously). Votes are parsed
        from response text looking for "VOTE: {OUTCOME}" pattern.

        Args:
            session: The deliberation session.
            package: The context package.
            cross_examine_result: Result from CROSS_EXAMINE phase.

        Returns:
            PhaseResult for VOTE phase with votes in metadata.

        Raises:
            PhaseExecutionError: If phase execution fails.
        """
        logger.info(
            "vote_phase_starting",
            session_id=str(session.session_id),
        )

        started_at = _utc_now()
        cross_examine_summary = cross_examine_result.transcript[
            :2000
        ]  # Truncate for prompt

        async def execute_concurrent() -> list[tuple[UUID, str]]:
            """Execute all archon votes concurrently."""
            tasks = [
                self._invoke_archon(
                    archon_id,
                    self._build_vote_prompt(archon_id, package, cross_examine_summary),
                    DeliberationPhase.VOTE,
                )
                for archon_id in session.assigned_archons
            ]
            results = await asyncio.gather(*tasks)
            return list(zip(session.assigned_archons, results, strict=True))

        vote_responses = self._run_async(execute_concurrent())

        # Parse votes from responses
        votes: dict[UUID, DeliberationOutcome] = {}
        for archon_id, response in vote_responses:
            vote = self._parse_vote(response)
            if vote is None:
                # Default to ACKNOWLEDGE if parse fails
                logger.warning(
                    "vote_parse_failed",
                    archon_id=str(archon_id),
                    response_start=response[:100],
                )
                vote = DeliberationOutcome.ACKNOWLEDGE
            votes[archon_id] = vote

        # Build transcript
        transcript_parts = [
            "=== VOTE PHASE ===",
            f"Session ID: {session.session_id}",
            "All Archons casting simultaneous votes.",
            "",
        ]

        for archon_id, response in vote_responses:
            profile = self._get_archon_profile(archon_id)
            transcript_parts.extend(
                [
                    f"--- Vote from {profile.name} ({archon_id}) ---",
                    response,
                    "",
                ]
            )

        # Add vote summary
        vote_counts: dict[DeliberationOutcome, int] = {}
        for vote in votes.values():
            vote_counts[vote] = vote_counts.get(vote, 0) + 1

        transcript_parts.append("=== VOTE SUMMARY ===")
        for outcome, count in vote_counts.items():
            transcript_parts.append(f"{outcome.value}: {count} vote(s)")

        transcript = "\n".join(transcript_parts)
        transcript_hash = _compute_blake3_hash(transcript)
        completed_at = _utc_now()

        logger.info(
            "vote_phase_complete",
            session_id=str(session.session_id),
            vote_counts={k.value: v for k, v in vote_counts.items()},
            duration_ms=int((completed_at - started_at).total_seconds() * 1000),
        )

        return PhaseResult(
            phase=DeliberationPhase.VOTE,
            transcript=transcript,
            transcript_hash=transcript_hash,
            participants=session.assigned_archons,
            started_at=started_at,
            completed_at=completed_at,
            phase_metadata={
                "votes": votes,
                "vote_counts": {k.value: v for k, v in vote_counts.items()},
            },
        )

    def _parse_vote(self, response: str) -> DeliberationOutcome | None:
        """Parse vote from archon response.

        Looks for "VOTE: {OUTCOME}" pattern in response text.

        Args:
            response: Archon's vote response.

        Returns:
            Parsed DeliberationOutcome, or None if parsing fails.
        """
        response_upper = response.upper()

        if "VOTE: ESCALATE" in response_upper or "VOTE:ESCALATE" in response_upper:
            return DeliberationOutcome.ESCALATE
        if "VOTE: REFER" in response_upper or "VOTE:REFER" in response_upper:
            return DeliberationOutcome.REFER
        if (
            "VOTE: ACKNOWLEDGE" in response_upper
            or "VOTE:ACKNOWLEDGE" in response_upper
        ):
            return DeliberationOutcome.ACKNOWLEDGE

        # Try to find the outcome in a more flexible way
        if "ESCALATE" in response_upper and "VOTE" in response_upper:
            return DeliberationOutcome.ESCALATE
        if "REFER" in response_upper and "VOTE" in response_upper:
            return DeliberationOutcome.REFER
        if "ACKNOWLEDGE" in response_upper and "VOTE" in response_upper:
            return DeliberationOutcome.ACKNOWLEDGE

        return None


def create_crewai_deliberation_adapter(
    profile_repository: ArchonProfileRepository | None = None,
    timeout_seconds: int = DEFAULT_ARCHON_TIMEOUT_SECONDS,
    verbose: bool = False,
) -> CrewAIDeliberationAdapter:
    """Factory function to create CrewAIDeliberationAdapter.

    Args:
        profile_repository: Optional profile repository.
            If not provided, creates one with default paths.
        timeout_seconds: Timeout per archon (NFR-10.2 default: 30s).
        verbose: Enable verbose CrewAI logging.

    Returns:
        Configured CrewAIDeliberationAdapter instance.
    """
    if profile_repository is None:
        profile_repository = create_archon_profile_repository()

    return CrewAIDeliberationAdapter(
        profile_repository=profile_repository,
        timeout_seconds=timeout_seconds,
        verbose=verbose,
    )
