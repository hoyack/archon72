"""Conclave Service - Orchestrates formal Archon 72 meetings.

Manages the complete lifecycle of a Conclave session including:
- Phase transitions following parliamentary procedure
- Motion proposal, seconding, debate, and voting
- Rank-ordered speaking (Kings first)
- Roll call and quorum verification
- Integration with CrewAI for agent deliberation
- Checkpoint/resume for multi-day sessions

Constitutional Constraints:
- FR10: 72 agents can deliberate concurrently without degradation
- FR9: All outputs through witnessing pipeline
- CT-11: Silent failure destroys legitimacy -> report all failures
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import random
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from src.application.ports.agent_orchestrator import (
    AgentOrchestratorProtocol,
    AgentOutput,
    ContextBundle,
)
from src.application.ports.knight_witness import (
    KnightWitnessProtocol,
    ObservationContext,
    ViolationRecord,
    WitnessStatement,
)
from src.application.ports.permission_enforcer import (
    GovernanceAction,
    PermissionContext,
    PermissionEnforcerProtocol,
    ViolationDetail,
    ViolationSeverity,
)
from src.application.services.async_vote_validator import (
    AsyncVoteValidator,
    ReconciliationTimeoutError,
    VoteValidationJob,
)
from src.domain.errors.agent import AgentInvocationError
from src.domain.errors.reconciliation import (
    ReconciliationIncompleteError,
    TallyInvariantError,
)
from src.domain.models.conclave import (
    AgendaItem,
    ConclavePhase,
    ConclaveSession,
    DebateEntry,
    Motion,
    MotionStatus,
    MotionType,
    TranscriptEntry,
    Vote,
    VoteChoice,
    get_rank_priority,
)

# Optional async validation imports (Story 4.3, 4.4)
# These are imported conditionally to avoid hard dependencies
try:
    from src.application.ports.vote_publisher import PendingVote
except ImportError:
    PendingVote = None  # type: ignore

try:
    from src.application.ports.reconciliation import ReconciliationProtocol
    from src.application.services.vote_override_service import (
        OverrideApplicationResult,
        VoteOverrideService,
    )
    from src.domain.models.reconciliation import ReconciliationConfig
except ImportError:
    ReconciliationProtocol = None  # type: ignore
    VoteOverrideService = None  # type: ignore
    OverrideApplicationResult = None  # type: ignore
    ReconciliationConfig = None  # type: ignore

try:
    from src.workers.validation_dispatcher import DispatchResult, ValidationDispatcher

    ASYNC_VALIDATION_AVAILABLE = True
except ImportError:
    ValidationDispatcher = None  # type: ignore
    DispatchResult = None  # type: ignore
    ASYNC_VALIDATION_AVAILABLE = PendingVote is not None

logger = logging.getLogger(__name__)

# Callback types for progress reporting
ConclaveProgressCallback = Callable[[str, str, dict[str, Any]], None]


@dataclass
class ArchonProfile:
    """Minimal archon profile for Conclave participation."""

    id: str
    name: str
    aegis_rank: str
    domain: str


@dataclass
class ConclaveConfig:
    """Configuration for Conclave operation."""

    # Session settings
    checkpoint_dir: Path = field(default_factory=lambda: Path("_bmad-output/conclave"))
    checkpoint_interval_minutes: int = 5

    # Deliberation settings
    max_debate_rounds: int = 5
    speaking_time_limit_seconds: int = 120  # Per turn

    # Quorum settings
    quorum_percentage: float = 0.5  # 50% needed for quorum

    # Voting
    supermajority_threshold: float = 2 / 3  # 2/3 for passage
    vote_validation_archon_ids: list[str] = field(default_factory=list)
    vote_validation_max_attempts: int = 3
    # Number of archons voting in parallel (1 = sequential, 0 = unlimited)
    voting_concurrency: int = 1

    # Three-tier async validation (spec v2)
    async_validation_enabled: bool = False
    secretary_text_archon_id: str | None = None
    secretary_json_archon_id: str | None = None
    witness_archon_id: str | None = None
    task_timeout_seconds: int = 60
    reconciliation_timeout: float = 300.0

    # Agent invocation
    agent_timeout_seconds: int = 180
    agent_timeout_max_attempts: int = 3
    agent_timeout_backoff_base_seconds: float = 2.0
    agent_timeout_backoff_max_seconds: float = 30.0

    # Output settings
    output_dir: Path = field(default_factory=lambda: Path("_bmad-output/conclave"))

    # Async validation (Story 4.3)
    # When enabled, votes are published to Kafka for async validation
    # Falls back to sync validation when circuit breaker is OPEN
    enable_async_validation: bool = False
    kafka_bootstrap_servers: str = "localhost:19092"
    schema_registry_url: str = "http://localhost:18081"
    kafka_enabled: bool = False
    kafka_topic_prefix: str = "conclave"


class ConclaveService:
    """Orchestrates formal Archon 72 Conclave meetings.

    The Conclave follows parliamentary procedure with:
    - Formal agenda phases (Opening, Reports, Old/New Business, Closing)
    - Motion system (propose, second, debate, vote)
    - Multi-round debate with rank-ordered speaking
    - Supermajority (2/3) voting threshold
    - Persistent state for multi-day sessions
    """

    def __init__(
        self,
        orchestrator: AgentOrchestratorProtocol,
        archon_profiles: list[ArchonProfile],
        config: ConclaveConfig | None = None,
        permission_enforcer: PermissionEnforcerProtocol | None = None,
        knight_witness: KnightWitnessProtocol | None = None,
        validation_dispatcher: Any | None = None,  # Story 4.3: ValidationDispatcher
        reconciliation_service: Any | None = None,  # Story 4.3: ReconciliationProtocol
        kafka_publisher: Any | None = None,
    ):
        """Initialize the Conclave service.

        Args:
            orchestrator: Agent orchestrator for LLM invocations
            archon_profiles: List of all Archon profiles
            config: Conclave configuration
            permission_enforcer: Optional permission enforcer for rank-based permissions
            knight_witness: Optional Knight-Witness service for governance observation
            validation_dispatcher: Optional ValidationDispatcher for async vote validation
            reconciliation_service: Optional ReconciliationService for vote tracking
        """
        self._orchestrator = orchestrator
        self._profiles = {p.id: p for p in archon_profiles}
        self._profiles_by_rank = self._sort_by_rank(archon_profiles)
        self._config = config or ConclaveConfig()
        self._permission_enforcer = permission_enforcer
        self._knight_witness = knight_witness

        # Story 4.3: Async validation components
        self._validation_dispatcher = validation_dispatcher
        self._reconciliation_service = reconciliation_service
        self._async_validation_active = False  # Set per-session
        self._async_validator: AsyncVoteValidator | None = None
        self._kafka_publisher = kafka_publisher
        self._pending_validation_payloads: list[dict[str, Any]] = []

        # Current session state
        self._session: ConclaveSession | None = None
        self._progress_callback: ConclaveProgressCallback | None = None

        # Ensure output directories exist
        self._config.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self._config.output_dir.mkdir(parents=True, exist_ok=True)

        # Validate async validation setup
        if self._config.async_validation_enabled:
            missing_ids = [
                name
                for name, value in {
                    "SECRETARY_TEXT_ARCHON_ID": self._config.secretary_text_archon_id,
                    "SECRETARY_JSON_ARCHON_ID": self._config.secretary_json_archon_id,
                    "WITNESS_ARCHON_ID": self._config.witness_archon_id,
                }.items()
                if not value
            ]
            if missing_ids:
                logger.warning(
                    "Async validation enabled but missing archon IDs: %s. "
                    "Will use sync validation.",
                    ", ".join(missing_ids),
                )

    def _sort_by_rank(self, profiles: list[ArchonProfile]) -> list[ArchonProfile]:
        """Sort profiles by rank priority (Kings speak first)."""
        return sorted(profiles, key=lambda p: get_rank_priority(p.aegis_rank))

    def set_progress_callback(self, callback: ConclaveProgressCallback | None) -> None:
        """Set callback for progress updates."""
        self._progress_callback = callback

    def _emit_progress(
        self, event: str, message: str, data: dict[str, Any] | None = None
    ) -> None:
        """Emit a progress event."""
        if self._progress_callback:
            self._progress_callback(event, message, data or {})

    def _emit_percent_complete(
        self,
        phase: str,
        current_index: int,
        total_items: int,
    ) -> None:
        """Emit a coarse percent-complete update to the progress callback."""
        if total_items <= 0:
            return
        percent = (current_index / total_items) * 100
        self._emit_progress(
            "session_progress",
            f"{percent:.1f}% complete",
            {
                "percent_complete": percent,
                "phase": phase,
                "current": current_index,
                "total": total_items,
            },
        )

    # =========================================================================
    # SESSION MANAGEMENT
    # =========================================================================

    def create_session(self, session_name: str) -> ConclaveSession:
        """Create a new Conclave session.

        Args:
            session_name: Human-readable name for the session

        Returns:
            New ConclaveSession
        """
        self._session = ConclaveSession.create(
            session_name=session_name,
            expected_participants=len(self._profiles),
        )
        self._emit_progress(
            "session_created",
            f"Conclave session '{session_name}' created",
            {"session_id": str(self._session.session_id)},
        )
        return self._session

    def load_session(self, checkpoint_file: Path) -> ConclaveSession:
        """Load a session from checkpoint.

        Args:
            checkpoint_file: Path to checkpoint JSON file

        Returns:
            Restored ConclaveSession
        """
        with open(checkpoint_file) as f:
            data = json.load(f)

        # Reconstruct session from checkpoint
        self._session = self._deserialize_session(data)
        self._session.checkpoint_file = str(checkpoint_file)

        self._emit_progress(
            "session_loaded",
            f"Session loaded from {checkpoint_file}",
            {
                "session_id": str(self._session.session_id),
                "phase": self._session.current_phase.value,
            },
        )
        return self._session

    async def resume_pending_validations(self) -> None:
        """Resume any pending async validations from checkpoint."""
        if not self._pending_validation_payloads:
            return

        if not (
            self._config.async_validation_enabled
            and self._config.secretary_text_archon_id
            and self._config.secretary_json_archon_id
            and self._config.witness_archon_id
        ):
            logger.warning(
                "Pending validations found but async validation is disabled; "
                "skipping resume."
            )
            return

        if not self._async_validator:
            self._async_validator = AsyncVoteValidator(
                voting_concurrency=self._config.voting_concurrency,
                secretary_text_id=self._config.secretary_text_archon_id,
                secretary_json_id=self._config.secretary_json_archon_id,
                witness_id=self._config.witness_archon_id,
                orchestrator=self._orchestrator,
                kafka_publisher=self._kafka_publisher,
                task_timeout_seconds=self._config.task_timeout_seconds,
                max_attempts=self._config.vote_validation_max_attempts,
                backoff_base_seconds=self._config.agent_timeout_backoff_base_seconds,
                backoff_max_seconds=self._config.agent_timeout_backoff_max_seconds,
            )

        for payload in self._pending_validation_payloads:
            optimistic_choice = VoteChoice(payload.get("optimistic_choice", "ABSTAIN"))
            await self._async_validator.submit_vote(
                vote_id=payload.get("vote_id", str(uuid4())),
                session_id=payload.get("session_id", ""),
                motion_id=payload.get("motion_id", ""),
                archon_id=payload.get("archon_id", ""),
                archon_name=payload.get("archon_name", ""),
                optimistic_choice=optimistic_choice,
                vote_payload=payload.get("vote_payload", payload),
            )

        self._pending_validation_payloads = []

    def save_checkpoint(self) -> Path:
        """Save current session state to checkpoint.

        Returns:
            Path to checkpoint file
        """
        if not self._session:
            raise ValueError("No active session")

        # Generate checkpoint filename
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        filename = f"checkpoint-{self._session.session_id}-{timestamp}.json"
        checkpoint_path = self._config.checkpoint_dir / filename

        # Serialize and save
        data = self._serialize_session(self._session)
        with open(checkpoint_path, "w") as f:
            json.dump(data, f, indent=2)

        self._session.checkpoint_file = str(checkpoint_path)
        self._session.last_checkpoint = datetime.now(timezone.utc)

        self._emit_progress(
            "checkpoint_saved",
            f"Checkpoint saved to {checkpoint_path}",
            {"checkpoint_file": str(checkpoint_path)},
        )
        return checkpoint_path

    # =========================================================================
    # PHASE MANAGEMENT
    # =========================================================================

    async def call_to_order(self) -> None:
        """Begin the Conclave with call to order."""
        if not self._session:
            raise ValueError("No active session")

        self._session.advance_phase(ConclavePhase.CALL_TO_ORDER)
        self._session.add_transcript_entry(
            entry_type="procedural",
            content="The Archon 72 Conclave is hereby called to order.",
        )
        self._emit_progress(
            "phase_change", "Conclave called to order", {"phase": "call_to_order"}
        )

    async def conduct_roll_call(self) -> dict[str, bool]:
        """Conduct roll call to establish quorum.

        Returns:
            Dict mapping archon_id to present status
        """
        if not self._session:
            raise ValueError("No active session")

        self._session.advance_phase(ConclavePhase.ROLL_CALL)
        self._emit_progress(
            "phase_change", "Roll call in progress", {"phase": "roll_call"}
        )

        attendance: dict[str, bool] = {}

        # For now, mark all archons as present
        # In production, this could involve actual agent invocation
        for archon_id in self._profiles:
            self._session.mark_present(archon_id)
            attendance[archon_id] = True

        # Check quorum
        present_count = len(self._session.present_participants)
        total_count = self._session.expected_participants
        has_quorum = self._session.has_quorum()

        self._session.add_transcript_entry(
            entry_type="procedural",
            content=f"Roll call complete. {present_count} of {total_count} Archons present. "
            f"Quorum {'achieved' if has_quorum else 'NOT achieved'}.",
        )

        self._emit_progress(
            "roll_call_complete",
            f"Roll call: {present_count}/{total_count} present",
            {"present": present_count, "total": total_count, "has_quorum": has_quorum},
        )

        return attendance

    async def advance_to_new_business(self) -> None:
        """Advance directly to new business phase."""
        if not self._session:
            raise ValueError("No active session")

        # Skip intermediate phases for expedited meetings
        self._session.advance_phase(ConclavePhase.NEW_BUSINESS)
        self._session.add_transcript_entry(
            entry_type="procedural",
            content="The Chair moves to New Business.",
        )
        self._emit_progress(
            "phase_change", "Moved to New Business", {"phase": "new_business"}
        )

    async def adjourn(self) -> None:
        """Adjourn the Conclave session."""
        if not self._session:
            raise ValueError("No active session")

        self._session.advance_phase(ConclavePhase.ADJOURNMENT)
        self._session.add_transcript_entry(
            entry_type="procedural",
            content="Motion to adjourn is in order.",
        )

        if self._async_validator:
            self._emit_progress(
                "reconciliation_started",
                "Waiting for validations to complete",
                {"pending": self._async_validator.get_stats()["pending"]},
            )
            try:
                validated_jobs = await self._async_validator.drain(
                    timeout_seconds=self._config.reconciliation_timeout
                )
            except ReconciliationTimeoutError as exc:
                motion_id = (
                    self._session.current_motion.motion_id
                    if self._session.current_motion
                    else UUID(int=0)
                )
                raise ReconciliationIncompleteError(
                    session_id=self._session.session_id,
                    motion_id=motion_id,
                    pending_count=exc.pending_count,
                    consumer_lag=0,
                    dlq_count=0,
                    timeout_seconds=exc.timeout_seconds,
                ) from exc

            override_count = await self._apply_validation_overrides(validated_jobs)
            self._emit_progress(
                "reconciliation_complete",
                "All validations complete",
                {
                    "total_votes": len(validated_jobs),
                    "overrides_applied": override_count,
                },
            )

        # Mark session as ended
        self._session.ended_at = datetime.now(timezone.utc)
        self._session.advance_phase(ConclavePhase.ADJOURNED)
        self._session.add_transcript_entry(
            entry_type="procedural",
            content="The Archon 72 Conclave is hereby adjourned.",
        )

        # Final checkpoint
        self.save_checkpoint()

        self._emit_progress(
            "session_adjourned",
            "Conclave adjourned",
            {
                "duration_minutes": self._session.duration / 60,
                "motions_passed": len(self._session.passed_motions),
                "motions_failed": len(self._session.failed_motions),
            },
        )

    # =========================================================================
    # MOTION HANDLING
    # =========================================================================

    async def propose_motion(
        self,
        proposer_id: str,
        motion_type: MotionType,
        title: str,
        text: str,
    ) -> Motion:
        """Propose a new motion.

        Per Government PRD FR-GOV-1: Kings introduce motions.
        Per Government PRD FR-GOV-6: Kings CANNOT define execution.

        Args:
            proposer_id: ID of the proposing Archon
            motion_type: Type of motion
            title: Short title for the motion
            text: Full motion text

        Returns:
            Created Motion

        Raises:
            RankViolationError: If the proposer lacks introduce_motion permission
        """
        if not self._session:
            raise ValueError("No active session")

        proposer = self._profiles.get(proposer_id)
        if not proposer:
            raise ValueError(f"Unknown proposer: {proposer_id}")

        # Check permission to introduce motion per Government PRD §10
        if self._permission_enforcer:
            context = PermissionContext(
                archon_id=UUID(proposer_id),
                archon_name=proposer.name,
                aegis_rank=proposer.aegis_rank,
                original_rank=self._get_original_rank(proposer.aegis_rank),
                branch="legislative",
                action=GovernanceAction.INTRODUCE_MOTION,
                target_id=None,
                target_type="motion",
            )
            self._permission_enforcer.enforce_permission(context)
            logger.info(
                "motion_propose_permission_granted",
                proposer_id=proposer_id,
                proposer_name=proposer.name,
                rank=proposer.aegis_rank,
            )

        motion = Motion.create(
            motion_type=motion_type,
            title=title,
            text=text,
            proposer_id=proposer_id,
            proposer_name=proposer.name,
            max_debate_rounds=self._config.max_debate_rounds,
        )

        self._session.add_motion(motion)
        self._session.current_motion_index = len(self._session.motions) - 1

        self._emit_progress(
            "motion_proposed",
            f"Motion proposed: {title}",
            {
                "motion_id": str(motion.motion_id),
                "proposer": proposer.name,
                "type": motion_type.value,
            },
        )

        return motion

    def add_external_motion(self, motion: Motion) -> None:
        """Add a pre-built motion to the session without permission checks.

        This supports agenda items sourced from the motion queue or execution
        planner blockers (external to the Conclave proposer workflow).
        """
        if not self._session:
            raise ValueError("No active session")

        self._session.add_motion(motion)
        self._session.current_motion_index = len(self._session.motions) - 1

    async def second_motion(self, seconder_id: str) -> bool:
        """Second the current motion.

        Args:
            seconder_id: ID of the seconding Archon

        Returns:
            True if motion was successfully seconded
        """
        if not self._session:
            raise ValueError("No active session")

        motion = self._session.current_motion
        if not motion:
            raise ValueError("No motion pending")

        seconder = self._profiles.get(seconder_id)
        if not seconder:
            raise ValueError(f"Unknown seconder: {seconder_id}")

        try:
            motion.second(seconder_id, seconder.name)
            self._session.add_transcript_entry(
                entry_type="motion",
                content=f"Motion seconded by {seconder.name}",
                speaker_id=seconder_id,
                speaker_name=seconder.name,
            )
            self._emit_progress(
                "motion_seconded",
                f"Motion seconded by {seconder.name}",
                {"motion_id": str(motion.motion_id), "seconder": seconder.name},
            )
            return True
        except ValueError as e:
            logger.warning(f"Failed to second motion: {e}")
            return False

    async def evaluate_motion_for_seconding(self, archon_id: str) -> tuple[bool, str]:
        """Ask an Archon to evaluate if they would second the current motion.

        This implements deliberative seconding - Archons evaluate motions
        before deciding to second them. Absurd or harmful motions may be
        refused, causing them to die without debate.

        Args:
            archon_id: ID of the Archon to ask

        Returns:
            Tuple of (would_second: bool, reasoning: str)
        """
        if not self._session:
            raise ValueError("No active session")

        motion = self._session.current_motion
        if not motion:
            raise ValueError("No motion pending")

        archon = self._profiles.get(archon_id)
        if not archon:
            raise ValueError(f"Unknown archon: {archon_id}")

        # Don't let the proposer second their own motion
        if archon_id == motion.proposer_id:
            return False, "Cannot second own motion"

        prompt = self._build_seconding_prompt(motion, archon)

        bundle = ContextBundle(
            bundle_id=uuid4(),
            topic_id=f"second-eval-{motion.motion_id}",
            topic_content=prompt,
            metadata={
                "motion_type": motion.motion_type.value,
                "motion_title": motion.title,
                "evaluation_type": "seconding",
            },
            created_at=datetime.now(timezone.utc),
        )

        try:
            result = await self._invoke_with_timeout(archon_id, bundle)
            content = result.content if result else ""
            would_second, reasoning = self._parse_seconding_decision(content)

            # Log the decision
            logger.info(
                "seconding_evaluation archon=%s motion=%s would_second=%s",
                archon.name,
                motion.title[:50],
                would_second,
            )

            return would_second, reasoning

        except Exception as e:
            logger.warning(
                "seconding_evaluation_failed archon=%s error=%s",
                archon.name,
                str(e),
            )
            # On error, decline to second (fail-safe)
            return False, f"Evaluation failed: {e}"

    def _build_seconding_prompt(self, motion: Motion, archon: ArchonProfile) -> str:
        """Build the prompt for evaluating whether to second a motion."""
        return f"""ARCHON 72 CONCLAVE - MOTION SECONDING EVALUATION

You are {archon.name}, {archon.aegis_rank}.
Your domain: {archon.domain}

A motion has been proposed and requires a second before it can be debated.
You must decide whether this motion is worth the Conclave's time to debate.

MOTION TITLE: {motion.title}
MOTION TYPE: {motion.motion_type.value.upper()}
PROPOSER: {motion.proposer_name}

MOTION TEXT:
{motion.text}

EVALUATION CRITERIA:
1. Is this motion coherent and understandable?
2. Does it address a legitimate governance concern?
3. Is it feasible to implement if passed?
4. Does it align with the Conclave's purpose and values?
5. Is it a serious proposal worthy of formal debate?

INSTRUCTIONS:
Evaluate this motion based on your expertise and the criteria above.
A motion should be seconded if it merits formal debate, even if you might
ultimately vote against it. However, frivolous, absurd, or clearly harmful
motions should NOT be seconded.

Start your response with exactly one of:
DECISION: SECOND - if the motion merits debate
DECISION: DECLINE - if the motion should not proceed

Then provide a brief explanation (2-3 sentences) for your decision.
"""

    def _parse_seconding_decision(self, content: str) -> tuple[bool, str]:
        """Parse an Archon's seconding decision from their response.

        Args:
            content: The LLM response text

        Returns:
            Tuple of (would_second: bool, reasoning: str)
        """
        content_lower = content.lower()
        lines = content.strip().splitlines()

        would_second = False
        reasoning = content[:500] if content else "No response provided"

        # Look for explicit decision
        for line in lines:
            line_stripped = line.strip().lower()
            if line_stripped.startswith("decision:"):
                decision_part = line_stripped.split(":", 1)[1].strip()
                if decision_part.startswith("second"):
                    would_second = True
                elif decision_part.startswith("decline"):
                    would_second = False
                # Extract reasoning from remaining content
                idx = content.lower().find("decision:")
                if idx >= 0:
                    after_decision = content[idx:]
                    newline_idx = after_decision.find("\n")
                    if newline_idx >= 0:
                        reasoning = after_decision[newline_idx:].strip()[:500]
                break

        # Fallback: look for indicators if no explicit decision
        if "decision:" not in content_lower:
            second_indicators = [
                "i second",
                "i will second",
                "worthy of debate",
                "merits debate",
                "deserves consideration",
                "should be debated",
            ]
            decline_indicators = [
                "i decline",
                "i cannot second",
                "refuse to second",
                "not worthy",
                "frivolous",
                "absurd",
                "waste of time",
                "does not merit",
            ]

            for indicator in decline_indicators:
                if indicator in content_lower:
                    would_second = False
                    break

            for indicator in second_indicators:
                if indicator in content_lower:
                    would_second = True
                    break

        return would_second, reasoning

    async def seek_second(
        self,
        candidate_archon_ids: list[str],
        max_attempts: int | None = None,
    ) -> tuple[str | None, list[tuple[str, str]]]:
        """Seek a second for the current motion from candidate Archons.

        Tries each candidate in order until one agrees to second or all decline.
        This implements deliberative seconding where Archons evaluate motions
        before seconding them.

        Args:
            candidate_archon_ids: List of Archon IDs to try, in order
            max_attempts: Maximum number of Archons to ask (default: all)

        Returns:
            Tuple of:
                - seconder_id if someone seconded, None if all declined
                - List of (archon_name, reasoning) for all evaluations
        """
        if not self._session:
            raise ValueError("No active session")

        motion = self._session.current_motion
        if not motion:
            raise ValueError("No motion pending")

        evaluations: list[tuple[str, str]] = []
        attempts = 0
        limit = max_attempts or len(candidate_archon_ids)

        self._emit_progress(
            "seeking_second",
            f"Seeking a second for motion: {motion.title}",
            {
                "motion_id": str(motion.motion_id),
                "candidates": len(candidate_archon_ids),
            },
        )

        for archon_id in candidate_archon_ids:
            if attempts >= limit:
                break

            # Skip the proposer
            if archon_id == motion.proposer_id:
                continue

            archon = self._profiles.get(archon_id)
            if not archon:
                continue

            attempts += 1

            self._emit_progress(
                "seconding_evaluation",
                f"Asking {archon.name} to evaluate motion",
                {"archon": archon.name, "attempt": attempts, "max_attempts": limit},
            )

            would_second, reasoning = await self.evaluate_motion_for_seconding(
                archon_id
            )
            evaluations.append((archon.name, reasoning))

            if would_second:
                # This Archon agrees to second
                success = await self.second_motion(archon_id)
                if success:
                    return archon_id, evaluations
            else:
                # Record the decline in transcript
                self._session.add_transcript_entry(
                    entry_type="motion",
                    content=f"{archon.name} declines to second: {reasoning[:200]}",
                    speaker_id=archon_id,
                    speaker_name=archon.name,
                )
                self._emit_progress(
                    "second_declined",
                    f"{archon.name} declined to second",
                    {"archon": archon.name, "reasoning": reasoning[:200]},
                )

        # No one seconded - motion dies
        self._session.add_transcript_entry(
            entry_type="procedural",
            content=f"Motion '{motion.title}' died for lack of a second after {attempts} Archon(s) declined.",
        )
        self._emit_progress(
            "motion_died_no_second",
            "Motion died for lack of a second",
            {"motion_id": str(motion.motion_id), "attempts": attempts},
        )

        return None, evaluations

    async def conduct_debate(
        self,
        topic_prompt: str | None = None,
    ) -> list[DebateEntry]:
        """Conduct debate on the current motion.

        All Archons speak in rank order. Multiple rounds if configured.

        Args:
            topic_prompt: Optional additional context for the debate

        Returns:
            List of debate entries
        """
        if not self._session:
            raise ValueError("No active session")

        motion = self._session.current_motion
        if not motion:
            raise ValueError("No motion to debate")

        if motion.status == MotionStatus.SECONDED:
            motion.begin_debate()

        if motion.status != MotionStatus.DEBATING:
            raise ValueError(f"Cannot debate motion in status {motion.status}")

        all_entries: list[DebateEntry] = []

        # Conduct debate rounds
        while motion.current_debate_round <= motion.max_debate_rounds:
            round_num = motion.current_debate_round
            self._emit_progress(
                "debate_round_start",
                f"Debate round {round_num} of {motion.max_debate_rounds}",
                {"round": round_num, "max_rounds": motion.max_debate_rounds},
            )
            self._emit_percent_complete(
                phase="debate",
                current_index=round_num - 1,
                total_items=motion.max_debate_rounds + 1,  # keep <100% until done
            )

            # Each Archon speaks in rank order
            round_entries = await self._conduct_debate_round(
                motion, round_num, topic_prompt
            )
            all_entries.extend(round_entries)

            # Checkpoint after each round
            self.save_checkpoint()

            # Advance to next round
            if not motion.next_debate_round():
                break

        self._emit_progress(
            "debate_complete",
            f"Debate concluded after {motion.current_debate_round} rounds",
            {"total_entries": len(all_entries)},
        )
        self._emit_percent_complete(
            phase="debate",
            current_index=motion.max_debate_rounds,
            total_items=motion.max_debate_rounds,
        )

        return all_entries

    async def _conduct_debate_round(
        self,
        motion: Motion,
        round_num: int,
        topic_prompt: str | None,
    ) -> list[DebateEntry]:
        """Conduct a single debate round with all Archons speaking.

        Args:
            motion: The motion being debated
            round_num: Current debate round number
            topic_prompt: Additional context

        Returns:
            List of debate entries from this round
        """
        entries: list[DebateEntry] = []
        if self._session is None:
            raise RuntimeError("Conclave session not initialized")

        # Build context for debate
        debate_context = self._build_debate_context(motion, round_num, topic_prompt)

        # Create requests for all archons (in rank order)
        total_archons = len(self._profiles_by_rank)

        for idx, archon in enumerate(self._profiles_by_rank):
            current = idx + 1
            self._emit_progress(
                "archon_speaking",
                f"Round {round_num}: {archon.name} ({current}/{total_archons})",
                {
                    "round": round_num,
                    "archon": archon.name,
                    "rank": archon.aegis_rank,
                    "progress": f"{current}/{total_archons}",
                },
            )

            try:
                # Invoke the archon
                output = await self._invoke_archon_for_debate(
                    archon, debate_context, motion
                )

                # Validate speech for rank violations (per Government PRD FR-GOV-6)
                is_valid, violations = self._validate_speech_for_rank(
                    archon, output.content, motion
                )

                # Parse their position (for/against/neutral)
                position = self._parse_debate_position(output.content)

                entry = DebateEntry.create(
                    speaker_id=archon.id,
                    speaker_name=archon.name,
                    speaker_rank=archon.aegis_rank,
                    content=output.content,
                    round_number=round_num,
                    in_favor=position,
                )

                motion.add_debate_entry(entry)
                entries.append(entry)

                # Determine entry type based on violations
                entry_type = "speech" if is_valid else "violation_speech"
                metadata = {
                    "round": round_num,
                    "motion_id": str(motion.motion_id),
                    "position": "for"
                    if position is True
                    else "against"
                    if position is False
                    else "neutral",
                    "has_violations": not is_valid,
                    "violation_count": len(violations),
                }

                self._session.add_transcript_entry(
                    entry_type=entry_type,
                    content=output.content,
                    speaker_id=archon.id,
                    speaker_name=archon.name,
                    metadata=metadata,
                )

                # Flag violations if detected
                if violations:
                    self._flag_speech_violation(archon, violations, motion)

            except Exception as e:
                logger.error(f"Error during debate from {archon.name}: {e}")
                # Record failure but continue
                self._session.add_transcript_entry(
                    entry_type="system",
                    content=f"[Error: {archon.name} unable to contribute: {e}]",
                )

        return entries

    async def _invoke_archon_for_debate(
        self,
        archon: ArchonProfile,
        context: str,
        motion: Motion,
    ) -> AgentOutput:
        """Invoke a single archon for debate contribution.

        Args:
            archon: The archon profile
            context: Debate context
            motion: Motion being debated

        Returns:
            AgentOutput with the archon's contribution
        """
        bundle = ContextBundle(
            bundle_id=uuid4(),
            topic_id=f"motion-{motion.motion_id}",
            topic_content=context,
            metadata={
                "motion_type": motion.motion_type.value,
                "motion_title": motion.title,
                "debate_round": str(motion.current_debate_round),
            },
            created_at=datetime.now(timezone.utc),
        )

        return await self._invoke_with_timeout(archon.id, bundle)

    async def _invoke_with_timeout(
        self,
        agent_id: str,
        bundle: ContextBundle,
    ) -> AgentOutput:
        """Invoke an archon with a hard timeout from config.

        This prevents a single stalled LLM call from hanging the Conclave.
        Set agent_timeout_seconds <= 0 to disable the timeout.
        """
        timeout = self._config.agent_timeout_seconds
        if timeout <= 0:
            return await self._orchestrator.invoke(agent_id, bundle)

        max_attempts = max(1, self._config.agent_timeout_max_attempts)
        base_delay = max(0.0, self._config.agent_timeout_backoff_base_seconds)
        max_delay = max(base_delay, self._config.agent_timeout_backoff_max_seconds)

        attempt = 1
        while True:
            try:
                return await asyncio.wait_for(
                    self._orchestrator.invoke(agent_id, bundle),
                    timeout=timeout,
                )
            except TimeoutError as exc:
                if attempt >= max_attempts:
                    logger.warning(
                        "archon_invoke_timeout agent_id=%s timeout_seconds=%s attempts=%s",
                        agent_id,
                        timeout,
                        attempt,
                    )
                    raise AgentInvocationError(
                        f"Agent {agent_id} timed out after {timeout}s "
                        f"(attempts={attempt})"
                    ) from exc

                delay = self._calculate_timeout_backoff(
                    attempt=attempt,
                    base_delay=base_delay,
                    max_delay=max_delay,
                )
                logger.warning(
                    "archon_invoke_timeout_retry agent_id=%s timeout_seconds=%s "
                    "attempt=%s retry_delay_seconds=%s",
                    agent_id,
                    timeout,
                    attempt,
                    delay,
                )
                await asyncio.sleep(delay)
                attempt += 1

    @staticmethod
    def _calculate_timeout_backoff(
        attempt: int,
        base_delay: float,
        max_delay: float,
    ) -> float:
        """Decorrelated jitter backoff for timeout retries."""
        if attempt <= 1:
            return min(base_delay, max_delay)

        previous = base_delay * (2 ** (attempt - 2))
        delay = random.uniform(base_delay, previous * 3)
        return min(delay, max_delay)

    def _build_debate_context(
        self,
        motion: Motion,
        round_num: int,
        topic_prompt: str | None,
    ) -> str:
        """Build the context prompt for debate.

        Args:
            motion: The motion being debated
            round_num: Current round number
            topic_prompt: Additional context

        Returns:
            Complete debate prompt
        """
        # Include previous debate entries for context
        previous_debate = ""
        if motion.debate_entries:
            previous_debate = "\n\nPrevious contributions:\n"
            for entry in motion.debate_entries[-10:]:  # Last 10 entries
                position = (
                    "FOR"
                    if entry.in_favor is True
                    else "AGAINST"
                    if entry.in_favor is False
                    else "NEUTRAL"
                )
                previous_debate += f"\n[{entry.speaker_name} ({position})]:\n{entry.content[:500]}...\n"

        context = f"""ARCHON 72 CONCLAVE - FORMAL DEBATE

MOTION: {motion.title}
TYPE: {motion.motion_type.value.upper()}
PROPOSER: {motion.proposer_name}
SECONDER: {motion.seconder_name}

MOTION TEXT:
{motion.text}

DEBATE ROUND: {round_num} of {motion.max_debate_rounds}
{previous_debate}

{topic_prompt or ""}

INSTRUCTIONS:
You are participating in a formal deliberation of the Archon 72 Conclave.
Provide your perspective on this motion based on your domain expertise and role.
Start with one line: STANCE: FOR or STANCE: AGAINST or STANCE: NEUTRAL
Be concise but substantive. Your contribution will be recorded in the official transcript.
"""
        return context

    def _parse_debate_position(self, content: str) -> bool | None:
        """Parse an archon's position from their debate contribution.

        Args:
            content: The debate contribution text

        Returns:
            True (for), False (against), or None (neutral)
        """
        content_lower = content.lower()

        if "stance:" in content_lower:
            for line in content_lower.splitlines():
                line = line.strip()
                if not line.startswith("stance:"):
                    continue
                value = line.split(":", 1)[1].strip()
                if value.startswith("for"):
                    return True
                if value.startswith("against"):
                    return False
                if value.startswith("neutral"):
                    return None

        # Look for explicit position statements
        for_indicators = [
            "i support",
            "i am for",
            "in favor",
            "vote aye",
            "support this motion",
        ]
        against_indicators = [
            "i oppose",
            "i am against",
            "vote nay",
            "against this motion",
            "cannot support",
        ]

        for indicator in for_indicators:
            if indicator in content_lower:
                return True

        for indicator in against_indicators:
            if indicator in content_lower:
                return False

        return None

    async def call_question(self) -> None:
        """Call the question, ending debate.

        Must have motion seconding to proceed.
        """
        if not self._session:
            raise ValueError("No active session")

        motion = self._session.current_motion
        if not motion:
            raise ValueError("No motion pending")

        motion.call_question()

        self._session.add_transcript_entry(
            entry_type="procedural",
            content="The question has been called. Debate is closed.",
        )

        self._emit_progress(
            "question_called",
            "Question called - debate ended",
            {"motion_id": str(motion.motion_id)},
        )

    # =========================================================================
    # VOTING
    # =========================================================================

    async def conduct_vote(self) -> dict[str, Any]:
        """Conduct voting on the current motion.

        Voting proceeds in two phases (batch architecture):
          Phase 1 - Vote Collection: Collect all votes from archons with bounded
                    concurrency. No validation LLM calls during this phase.
          Phase 2 - Batch Validation: After all votes collected, submit all to
                    the async validator. Validation runs independently.

        This separation eliminates resource contention between vote collection
        and validation LLM calls.

        Use --voting-concurrency N to control parallel vote collection
        (0 = unlimited).

        Returns:
            Dict with vote results
        """
        if not self._session:
            raise ValueError("No active session")

        motion = self._session.current_motion
        if not motion:
            raise ValueError("No motion to vote on")

        if motion.status == MotionStatus.CALLED:
            motion.begin_voting()
        elif motion.status != MotionStatus.VOTING:
            raise ValueError(f"Cannot vote on motion in status {motion.status}")

        # Collect votes from all present archons
        total_voters = len(self._session.present_participants)

        configured_concurrency = self._config.voting_concurrency
        if configured_concurrency <= 0:
            configured_concurrency = max(1, total_voters)

        self._emit_progress(
            "voting_start",
            "Voting has begun (Phase 1: Collection)",
            {
                "motion_id": str(motion.motion_id),
                "title": motion.title,
                "concurrency": configured_concurrency,
            },
        )
        completed_count = 0
        completed_lock = asyncio.Lock()

        # Create semaphore for concurrency control during vote collection
        voting_semaphore = asyncio.Semaphore(configured_concurrency)

        use_async_validator = (
            self._config.async_validation_enabled
            and self._config.secretary_text_archon_id
            and self._config.secretary_json_archon_id
            and self._config.witness_archon_id
        )

        if use_async_validator and not self._async_validator:
            self._async_validator = AsyncVoteValidator(
                voting_concurrency=self._config.voting_concurrency,
                secretary_text_id=self._config.secretary_text_archon_id,
                secretary_json_id=self._config.secretary_json_archon_id,
                witness_id=self._config.witness_archon_id,
                orchestrator=self._orchestrator,
                kafka_publisher=self._kafka_publisher,
                task_timeout_seconds=self._config.task_timeout_seconds,
                max_attempts=self._config.vote_validation_max_attempts,
                backoff_base_seconds=self._config.agent_timeout_backoff_base_seconds,
                backoff_max_seconds=self._config.agent_timeout_backoff_max_seconds,
            )

        # Storage for validation payloads (Phase 2 batch submission)
        validation_payloads: list[dict[str, Any]] = []
        validation_payloads_lock = asyncio.Lock()

        async def collect_single_vote(
            archon_id: str,
        ) -> Vote | None:
            """Collect a single vote with semaphore-controlled concurrency.

            Phase 1 only: Collects vote payload from LLM, parses optimistic choice,
            stores payload for batch validation submission. Does NOT submit to
            validator here - that happens in Phase 2.
            """
            nonlocal completed_count

            archon = self._profiles.get(archon_id)
            if not archon:
                return None

            async with voting_semaphore:
                try:
                    if use_async_validator:
                        # Phase 1: Collect vote payload, defer validation submission
                        payload = await self._collect_vote_payload(archon, motion)
                        raw_response = payload["raw_content"]
                        optimistic_choice = self._parse_vote(raw_response)
                        vote_id = str(uuid4())

                        payload.update(
                            {
                                "vote_id": vote_id,
                                "session_id": str(
                                    self._session.session_id if self._session else ""
                                ),
                                "motion_id": str(motion.motion_id),
                                "archon_id": archon.id,
                                "archon_name": archon.name,
                                "optimistic_choice": optimistic_choice.value,
                            }
                        )

                        if self._kafka_publisher:
                            await self._kafka_publisher.publish(
                                "conclave.votes.cast",
                                payload,
                            )

                        # Store payload for Phase 2 batch submission
                        async with validation_payloads_lock:
                            validation_payloads.append(payload)

                        vote = Vote(
                            voter_id=archon.id,
                            voter_name=archon.name,
                            voter_rank=archon.aegis_rank,
                            choice=optimistic_choice,
                            timestamp=datetime.now(timezone.utc),
                            reasoning=raw_response[:500],
                        )
                    else:
                        vote, _is_valid = await self._get_archon_vote(archon, motion)

                    # Update progress atomically
                    async with completed_lock:
                        completed_count += 1
                        current = completed_count

                    self._emit_percent_complete(
                        phase="vote_collection",
                        current_index=current,
                        total_items=total_voters,
                    )
                    self._emit_progress(
                        "archon_voting",
                        f"Collected: {archon.name} ({current}/{total_voters})",
                        {
                            "archon": archon.name,
                            "progress": f"{current}/{total_voters}",
                        },
                    )

                    return vote

                except AgentInvocationError as e:
                    logger.error(f"Error getting vote from {archon.name}: {e}")

                    # Update progress atomically
                    async with completed_lock:
                        completed_count += 1

                    # Do not silently skip failed LLM invocations.
                    raise
                except Exception as e:
                    logger.error(f"Error getting vote from {archon.name}: {e}")

                    # Update progress atomically
                    async with completed_lock:
                        completed_count += 1

                    # Record abstention on unexpected errors
                    return Vote(
                        voter_id=archon_id,
                        voter_name=archon.name,
                        voter_rank=archon.aegis_rank,
                        choice=VoteChoice.ABSTAIN,
                        timestamp=datetime.now(timezone.utc),
                        reasoning=f"Vote error: {e}",
                    )

        # =====================================================================
        # PHASE 1: Vote Collection (bounded concurrency, no validation yet)
        # =====================================================================
        if configured_concurrency == 1:
            # Sequential mode (original behavior)
            for archon_id in self._session.present_participants:
                vote = await collect_single_vote(archon_id)
                if vote:
                    motion.cast_vote(vote)
                    if self._session:
                        self._session.add_transcript_entry(
                            entry_type="vote",
                            content=f"Vote: {vote.choice.value.upper()}",
                            speaker_id=vote.voter_id,
                            speaker_name=vote.voter_name,
                            metadata={
                                "motion_id": str(motion.motion_id),
                                "choice": vote.choice.value,
                            },
                        )
        else:
            # Concurrent mode
            tasks = [
                collect_single_vote(archon_id)
                for archon_id in self._session.present_participants
            ]
            votes = await asyncio.gather(*tasks)

            # Cast all votes and record in transcript
            for vote in votes:
                if vote:
                    motion.cast_vote(vote)
                    if self._session:
                        self._session.add_transcript_entry(
                            entry_type="vote",
                            content=f"Vote: {vote.choice.value.upper()}",
                            speaker_id=vote.voter_id,
                            speaker_name=vote.voter_name,
                            metadata={
                                "motion_id": str(motion.motion_id),
                                "choice": vote.choice.value,
                            },
                        )

        # =====================================================================
        # PHASE 2: Batch Validation Submission (after all votes collected)
        # =====================================================================
        if use_async_validator and self._async_validator and validation_payloads:
            self._emit_progress(
                "validation_batch_start",
                f"Phase 2: Submitting {len(validation_payloads)} votes for validation",
                {
                    "motion_id": str(motion.motion_id),
                    "vote_count": len(validation_payloads),
                },
            )

            for payload in validation_payloads:
                await self._async_validator.submit_vote(
                    vote_id=payload["vote_id"],
                    session_id=payload["session_id"],
                    motion_id=payload["motion_id"],
                    archon_id=payload["archon_id"],
                    archon_name=payload["archon_name"],
                    optimistic_choice=VoteChoice(payload["optimistic_choice"]),
                    vote_payload=payload,
                )

            self._emit_progress(
                "validation_batch_complete",
                f"Phase 2: All {len(validation_payloads)} votes submitted for async validation",
                {
                    "motion_id": str(motion.motion_id),
                    "vote_count": len(validation_payloads),
                    "pending_validations": self._async_validator.get_stats()["pending"],
                },
            )

        # Story 4.4: Reconciliation gate for async validation (legacy Kafka path)
        # P2: ReconciliationIncompleteError MUST propagate - do NOT catch
        if not use_async_validator and await self._should_use_async_validation():
            override_result = await self._await_reconciliation_gate(
                motion=motion,
                total_voters=total_voters,
            )
            if override_result and override_result.overrides_applied > 0:
                logger.info(
                    "Applied %d vote overrides after reconciliation",
                    override_result.overrides_applied,
                )

        # Tally and determine result
        motion.tally_votes(total_voters)
        self._session.total_votes_cast += len(motion.votes)

        result = {
            "motion_id": str(motion.motion_id),
            "title": motion.title,
            "ayes": motion.final_ayes,
            "nays": motion.final_nays,
            "abstentions": motion.final_abstentions,
            "passed": motion.status == MotionStatus.PASSED,
            "threshold": f"{self._config.supermajority_threshold:.1%}",
        }

        self._session.add_transcript_entry(
            entry_type="procedural",
            content=f"Vote tally: {motion.final_ayes} AYE, {motion.final_nays} NAY, "
            f"{motion.final_abstentions} ABSTAIN. "
            f"Motion {'PASSED' if result['passed'] else 'FAILED'}.",
        )

        self._emit_progress(
            "vote_complete",
            f"Motion {'PASSED' if result['passed'] else 'FAILED'}: "
            f"{motion.final_ayes}-{motion.final_nays}-{motion.final_abstentions}",
            result,
        )

        # Checkpoint after vote
        self.save_checkpoint()

        return result

    async def _collect_vote_payload(
        self, archon: ArchonProfile, motion: Motion
    ) -> dict[str, Any]:
        """Collect raw vote response for async validation."""
        vote_context = f"""ARCHON 72 CONCLAVE - FORMAL VOTE

MOTION: {motion.title}
TYPE: {motion.motion_type.value.upper()}

MOTION TEXT:
{motion.text}

You must now cast your vote on this motion.
Based on the debate and your own judgment, choose one:
- AYE (support the motion)
- NAY (oppose the motion)
- ABSTAIN (decline to vote)

Output format:
- First line MUST be JSON only: {{"choice":"AYE"}} or {{"choice":"NAY"}} or {{"choice":"ABSTAIN"}}
- Then (optional) up to 2 short paragraphs of public rationale.
"""

        bundle = ContextBundle(
            bundle_id=uuid4(),
            topic_id=f"vote-{motion.motion_id}",
            topic_content=vote_context,
            metadata={"motion_id": str(motion.motion_id), "voting": "true"},
            created_at=datetime.now(timezone.utc),
        )

        output = await self._invoke_with_timeout(archon.id, bundle)
        return {
            "raw_content": output.content,
            "motion_title": motion.title,
            "motion_text": motion.text,
            "archon_id": archon.id,
            "archon_name": archon.name,
        }

    async def _get_archon_vote(
        self, archon: ArchonProfile, motion: Motion
    ) -> tuple[Vote, bool]:
        """Get a vote from an archon.

        Story 4.3: Supports async validation via Kafka when enabled.
        - When async enabled and circuit breaker allows: publish for async validation
        - When circuit breaker OPEN or async disabled: use sync validation

        Args:
            archon: The archon voting
            motion: The motion being voted on

        Returns:
            tuple of (Vote object, is_validated flag)
        """
        # Build voting context
        vote_context = f"""ARCHON 72 CONCLAVE - FORMAL VOTE

MOTION: {motion.title}
TYPE: {motion.motion_type.value.upper()}

MOTION TEXT:
{motion.text}

You must now cast your vote on this motion.
Based on the debate and your own judgment, choose one:
- AYE (support the motion)
- NAY (oppose the motion)
- ABSTAIN (decline to vote)

Output format:
- First line MUST be JSON only: {{"choice":"AYE"}} or {{"choice":"NAY"}} or {{"choice":"ABSTAIN"}}
- Then (optional) up to 2 short paragraphs of public rationale.
"""

        bundle = ContextBundle(
            bundle_id=uuid4(),
            topic_id=f"vote-{motion.motion_id}",
            topic_content=vote_context,
            metadata={"motion_id": str(motion.motion_id), "voting": "true"},
            created_at=datetime.now(timezone.utc),
        )

        output = await self._invoke_with_timeout(archon.id, bundle)

        # 3-Archon Vote Validation Protocol:
        # Votes are determined ONLY by secretary consensus, not by parsing.
        # Secretaries analyze the raw response and determine: AYE, NAY, or ABSTAIN.
        # Witness observes and records agreement/dissent (cannot change outcome).

        # Story 4.3: Check if async validation should be used
        use_async = await self._should_use_async_validation()

        if use_async:
            # Async path: publish for validation
            # Vote choice will be determined by secretary consensus via Kafka
            vote, is_validated = await self._handle_async_vote(
                archon=archon,
                motion=motion,
                optimistic_choice=VoteChoice.ABSTAIN,  # Placeholder until validated
                raw_response=output.content,
            )
            return vote, is_validated

        # Sync path: use 3-archon validation (secretary consensus)
        validated_choice = await self._validate_vote_consensus(
            archon=archon,
            motion=motion,
            raw_vote=output.content,
        )
        is_validated = validated_choice is not None

        if is_validated:
            choice = validated_choice
        else:
            # No secretary consensus reached - abstain is the constitutional default
            choice = VoteChoice.ABSTAIN
            if self._config.vote_validation_archon_ids:
                self._record_vote_validation_failure(archon, motion)

        vote = Vote(
            voter_id=archon.id,
            voter_name=archon.name,
            voter_rank=archon.aegis_rank,
            choice=choice,
            timestamp=datetime.now(timezone.utc),
            reasoning=(
                output.content[:500]
                if is_validated or not self._config.vote_validation_archon_ids
                else "Vote validation failed: no consensus"
            ),
        )
        return vote, (is_validated or not self._config.vote_validation_archon_ids)

    async def _should_use_async_validation(self) -> bool:
        """Check if async validation should be used.

        Story 4.3: Async validation is used when:
        1. enable_async_validation config is True
        2. Async validation module is available
        3. ValidationDispatcher is configured
        4. Circuit breaker allows requests (CLOSED or HALF_OPEN)

        Returns:
            True if async validation should be used, False for sync fallback
        """
        if not self._config.enable_async_validation:
            return False

        if not ASYNC_VALIDATION_AVAILABLE and not self._validation_dispatcher:
            return False

        if not self._validation_dispatcher:
            return False

        # Check circuit breaker state
        breaker = getattr(self._validation_dispatcher, "_circuit_breaker", None)
        if breaker is not None and hasattr(breaker, "should_allow_request"):
            allowed = breaker.should_allow_request()
            if asyncio.iscoroutine(allowed):
                allowed = await allowed
            if not allowed:
                logger.info("Circuit breaker OPEN, falling back to sync validation")
                return False

        return True

    async def _handle_async_vote(
        self,
        archon: ArchonProfile,
        motion: Motion,
        optimistic_choice: VoteChoice,
        raw_response: str,
    ) -> tuple[Vote, bool]:
        """Handle a vote using async validation via Kafka.

        3-Archon Vote Validation Protocol:
        Vote choice is determined ONLY by secretary consensus (SECRETARY_TEXT
        and SECRETARY_JSON must agree). Publishes vote for async validation
        and returns a pending vote. Final choice will be determined by the
        consensus aggregator when validation completes.

        Args:
            archon: The archon voting
            motion: The motion being voted on
            optimistic_choice: Placeholder (ABSTAIN) - not used for determination
            raw_response: Full LLM response for validation by secretaries

        Returns:
            tuple of (Vote with pending status, validation_pending=False)
        """
        vote_id = uuid4()
        session_id = self._session.session_id if self._session else uuid4()

        # Create pending vote for dispatcher
        # Note: optimistic_choice is ABSTAIN (placeholder) - actual choice
        # will be determined by 3-Archon Protocol secretary consensus
        pending_vote = PendingVote(
            vote_id=vote_id,
            session_id=session_id,
            motion_id=motion.motion_id,
            archon_id=archon.id,
            raw_response=raw_response,
            optimistic_choice="ABSTAIN",  # Placeholder - secretaries determine actual vote
            timestamp_ms=int(datetime.now(timezone.utc).timestamp() * 1000),
        )

        # Attempt async dispatch
        dispatch_result = await self._validation_dispatcher.dispatch_vote(
            vote=pending_vote,
            attempt=1,
        )

        if dispatch_result.should_fallback_to_sync:
            # Dispatch failed, fall back to sync validation (secretary consensus)
            logger.warning(
                "Async dispatch failed for vote %s, falling back to sync",
                vote_id,
            )
            validated_choice = await self._validate_vote_consensus(
                archon=archon,
                motion=motion,
                raw_vote=raw_response,
            )

            # Use secretary consensus or ABSTAIN if no consensus
            choice = validated_choice if validated_choice else VoteChoice.ABSTAIN
            is_validated = validated_choice is not None

            vote = Vote(
                voter_id=archon.id,
                voter_name=archon.name,
                voter_rank=archon.aegis_rank,
                choice=choice,
                timestamp=datetime.now(timezone.utc),
                reasoning=raw_response[:500]
                if is_validated
                else "Awaiting secretary consensus",
            )
            return vote, is_validated

        # Dispatch succeeded - register with reconciliation service
        if self._reconciliation_service:
            self._reconciliation_service.register_vote(
                session_id=session_id,
                motion_id=motion.motion_id,
                vote_id=vote_id,
                archon_id=archon.id,
                optimistic_choice="ABSTAIN",  # Placeholder until secretaries determine
            )

        logger.info(
            "Vote dispatched for 3-Archon validation: vote_id=%s archon=%s (awaiting secretary consensus)",
            vote_id,
            archon.id,
        )

        # Return vote with ABSTAIN placeholder - actual choice determined by
        # 3-Archon Protocol (secretary consensus + witness observation)
        # is_validated=False indicates async validation pending
        vote = Vote(
            voter_id=archon.id,
            voter_name=archon.name,
            voter_rank=archon.aegis_rank,
            choice=VoteChoice.ABSTAIN,  # Placeholder until validation completes
            timestamp=datetime.now(timezone.utc),
            reasoning="Awaiting 3-Archon validation (secretary consensus + witness)",
        )
        return vote, False  # False = validation pending (async)

    async def _await_reconciliation_gate(
        self,
        motion: Motion,
        total_voters: int,
    ) -> OverrideApplicationResult | None:
        """Await async validation reconciliation before tallying.

        Story 4.4: Implements the hard reconciliation gate (P2).
        - Waits for all async validations to complete
        - Applies vote overrides where validated != optimistic
        - P6: Enforces tally invariant (ayes + nays + abstains == total)
        - P2: ReconciliationIncompleteError MUST propagate

        Args:
            motion: The motion being voted on
            total_voters: Expected total number of votes

        Returns:
            OverrideApplicationResult if overrides applied, None if no async validation

        Raises:
            ReconciliationIncompleteError: If reconciliation times out (P2)
            TallyInvariantError: If P6 invariant violated
        """
        if not self._reconciliation_service:
            logger.warning(
                "Async validation active but no reconciliation service configured"
            )
            return None

        if not self._session:
            return None

        session_id = self._session.session_id
        motion_id = motion.motion_id

        # P2: This call raises ReconciliationIncompleteError on timeout
        # We MUST NOT catch it - it propagates to halt the session
        self._emit_progress(
            "reconciliation_start",
            "Waiting for vote validations to complete...",
            {"motion_id": str(motion_id), "total_votes": total_voters},
        )

        timeout_seconds = 300.0
        timeout_env = os.getenv("RECONCILIATION_TIMEOUT_SECONDS", "").strip()
        if not timeout_env:
            timeout_env = os.getenv("VOTE_VALIDATION_TIMEOUT", "").strip()
        if timeout_env:
            try:
                timeout_seconds = max(30.0, float(timeout_env))
            except ValueError:
                logger.warning(
                    "Invalid RECONCILIATION_TIMEOUT_SECONDS=%s; using default %.1fs",
                    timeout_env,
                    timeout_seconds,
                )

        reconciliation_config = (
            ReconciliationConfig(
                timeout_seconds=timeout_seconds,
                poll_interval_seconds=1.0,
                max_lag_for_complete=0,  # R3: Must be zero
                require_zero_pending=True,  # P1: Must have zero pending
            )
            if ReconciliationConfig
            else None
        )

        reconciliation_result = (
            await self._reconciliation_service.await_all_validations(
                session_id=session_id,
                motion_id=motion_id,
                expected_vote_count=total_voters,
                config=reconciliation_config,
            )
        )

        self._emit_progress(
            "reconciliation_complete",
            f"Vote validations complete: {reconciliation_result.validated_count} validated, "
            f"{reconciliation_result.dlq_fallback_count} DLQ fallback",
            {
                "validated": reconciliation_result.validated_count,
                "dlq_fallback": reconciliation_result.dlq_fallback_count,
                "has_overrides": reconciliation_result.has_overrides,
            },
        )

        # If no overrides needed, we're done
        if not reconciliation_result.has_overrides:
            logger.info("No vote overrides required after reconciliation")
            return None

        # Apply overrides via VoteOverrideService
        logger.info(
            "Applying %d vote overrides from reconciliation",
            reconciliation_result.override_count,
        )

        if not VoteOverrideService:
            logger.error("VoteOverrideService not available but overrides needed")
            return None

        override_service = VoteOverrideService(
            witness=self._knight_witness if hasattr(self, "_knight_witness") else None,
            strict_invariant=True,  # P6: Raise on invariant violation
        )

        # Create helper functions for the override service
        def get_vote_choice(archon_id: str) -> str:
            """Get current vote choice for an archon."""
            for vote in motion.votes:
                if vote.voter_id == archon_id:
                    return vote.choice.value
            raise KeyError(f"No vote found for archon {archon_id}")

        def update_vote_choice(archon_id: str, new_choice: str) -> None:
            """Update a vote's choice (mutates motion.votes)."""
            for vote in motion.votes:
                if vote.voter_id == archon_id:
                    # Convert string to VoteChoice enum
                    choice_map = {
                        "APPROVE": VoteChoice.AYE,
                        "REJECT": VoteChoice.NAY,
                        "ABSTAIN": VoteChoice.ABSTAIN,
                        "AYE": VoteChoice.AYE,
                        "NAY": VoteChoice.NAY,
                    }
                    vote.choice = choice_map.get(new_choice.upper(), VoteChoice.ABSTAIN)
                    return
            raise KeyError(f"No vote found for archon {archon_id}")

        def get_current_tallies() -> tuple[int, int, int]:
            """Get current vote tallies from motion."""
            ayes = sum(1 for v in motion.votes if v.choice == VoteChoice.AYE)
            nays = sum(1 for v in motion.votes if v.choice == VoteChoice.NAY)
            abstains = sum(1 for v in motion.votes if v.choice == VoteChoice.ABSTAIN)
            return ayes, nays, abstains

        override_result = await override_service.apply_overrides(
            session_id=session_id,
            motion_id=motion_id,
            reconciliation_result=reconciliation_result,
            get_vote_fn=get_vote_choice,
            update_vote_fn=update_vote_choice,
            get_tallies_fn=get_current_tallies,
            total_votes=total_voters,
        )

        if override_result.outcome_changed:
            logger.warning(
                "Motion outcome may have changed after reconciliation! "
                "Tallies before: %s, after: %s",
                override_result.tally_before.to_dict(),
                override_result.tally_after.to_dict(),
            )
            self._emit_progress(
                "reconciliation_outcome_changed",
                "Vote overrides changed motion outcome",
                {
                    "tally_before": override_result.tally_before.to_dict(),
                    "tally_after": override_result.tally_after.to_dict(),
                },
            )

        return override_result

    async def _apply_validation_overrides(
        self,
        validated_jobs: list[VoteValidationJob],
    ) -> int:
        """Apply validated vote corrections and recompute tallies."""
        if not self._session:
            return 0

        override_count = 0
        affected_motion_ids: set[str] = set()

        for job in validated_jobs:
            if not job.override_required or not job.adjudication_result:
                continue

            motion = next(
                (m for m in self._session.motions if str(m.motion_id) == job.motion_id),
                None,
            )
            if not motion:
                continue

            vote = next(
                (v for v in motion.votes if v.voter_id == job.archon_id),
                None,
            )
            if not vote:
                continue

            original_choice = vote.choice
            vote.choice = job.adjudication_result.final_vote
            vote.reasoning = (vote.reasoning or "") + (
                f"\n\n[Validated: {job.adjudication_result.final_vote.value}]"
            )

            self._session.add_transcript_entry(
                entry_type="procedural",
                content=(
                    f"Vote correction: {job.archon_name}'s vote on "
                    f"'{motion.title}' validated as "
                    f"{job.adjudication_result.final_vote.value} "
                    f"(originally {original_choice.value}). "
                    f"Witness ruling: {job.adjudication_result.ruling.value}"
                ),
                speaker_id="system",
                speaker_name="Validation System",
                metadata={
                    "event": "vote_override",
                    "vote_id": job.vote_id,
                    "motion_id": job.motion_id,
                    "archon_id": job.archon_id,
                    "original": original_choice.value,
                    "validated": job.adjudication_result.final_vote.value,
                    "witness_statement": job.adjudication_result.witness_statement,
                },
            )

            if self._kafka_publisher:
                await self._kafka_publisher.publish(
                    "conclave.votes.overrides",
                    {
                        "vote_id": job.vote_id,
                        "session_id": job.session_id,
                        "motion_id": job.motion_id,
                        "archon_id": job.archon_id,
                        "original": original_choice.value,
                        "validated": job.adjudication_result.final_vote.value,
                        "witness_ruling": job.adjudication_result.ruling.value,
                    },
                )

            override_count += 1
            affected_motion_ids.add(job.motion_id)

        for motion_id in affected_motion_ids:
            motion = next(
                (m for m in self._session.motions if str(m.motion_id) == motion_id),
                None,
            )
            if not motion:
                continue
            outcome_changed = self._recompute_motion_result(motion)
            if outcome_changed:
                self._session.add_transcript_entry(
                    entry_type="procedural",
                    content=(
                        f"Motion '{motion.title}' result changed after vote validation: "
                        f"{'PASSED' if motion.status == MotionStatus.PASSED else 'FAILED'}"
                    ),
                    speaker_id="system",
                    speaker_name="Validation System",
                )

        return override_count

    def _recompute_motion_result(self, motion: Motion) -> bool:
        """Recompute motion pass/fail after vote overrides."""
        original_status = motion.status

        ayes = sum(1 for v in motion.votes if v.choice == VoteChoice.AYE)
        nays = sum(1 for v in motion.votes if v.choice == VoteChoice.NAY)
        abstentions = sum(
            1
            for v in motion.votes
            if v.choice in (VoteChoice.ABSTAIN, VoteChoice.PRESENT)
        )

        total_votes = len(motion.votes)
        if ayes + nays + abstentions != total_votes:
            raise TallyInvariantError(
                session_id=self._session.session_id,
                motion_id=motion.motion_id,
                ayes=ayes,
                nays=nays,
                abstains=abstentions,
                total_votes=total_votes,
            )

        motion.final_ayes = ayes
        motion.final_nays = nays
        motion.final_abstentions = abstentions

        votes_cast = ayes + nays
        if votes_cast == 0:
            motion.status = MotionStatus.FAILED
        elif (ayes / votes_cast) >= self._config.supermajority_threshold:
            motion.status = MotionStatus.PASSED
        else:
            motion.status = MotionStatus.FAILED

        motion.vote_ended_at = datetime.now(timezone.utc)
        return motion.status != original_status

    def _parse_vote(self, content: str) -> VoteChoice:
        """Parse a vote from archon response (DEPRECATED - for debugging only).

        DEPRECATED: The 3-Archon Vote Validation Protocol should be used instead.
        Votes are now determined ONLY by secretary consensus (SECRETARY_TEXT and
        SECRETARY_JSON must agree), then witnessed by WITNESS. This method is kept
        only for debugging, logging, or fallback scenarios.

        Args:
            content: The response text

        Returns:
            VoteChoice
        """
        json_choice = self._parse_validation_json(content)
        if json_choice is not None:
            return json_choice

        # DEPRECATED: Deterministic string parsing for fallback/debugging only.
        # Votes should be determined by 3-Archon Protocol secretaries.
        #
        # Upstream formats:
        # - Conclave vote prompt: "I VOTE AYE|NAY|I ABSTAIN"
        # - King system prompts: "Vote: FOR|NAY|ABSTAIN"
        token_to_choice: dict[str, VoteChoice] = {
            "aye": VoteChoice.AYE,
            "for": VoteChoice.AYE,
            "yes": VoteChoice.AYE,
            "nay": VoteChoice.NAY,
            "against": VoteChoice.NAY,
            "no": VoteChoice.NAY,
            "abstain": VoteChoice.ABSTAIN,
        }
        token_strip_chars = " .!?,;:\"'"

        for raw_line in content.splitlines():
            line = raw_line.strip()
            if not line:
                continue

            # Strip common markdown/bullet prefixes that often appear in LLM output.
            line = line.lstrip(">*-_` ").strip()
            line = line.strip("*_` ").strip()
            if not line:
                continue

            lower = line.lower()

            if lower.startswith("i abstain"):
                return VoteChoice.ABSTAIN

            if lower.startswith("vote"):
                rest = lower[4:].lstrip(" :-")
                if rest.startswith("i abstain"):
                    return VoteChoice.ABSTAIN
                if rest.startswith("i vote "):
                    rest = rest[7:].lstrip()
                token = rest.split()[0] if rest else ""
                token = token.strip(token_strip_chars)
                parsed = token_to_choice.get(token)
                if parsed:
                    return parsed

            if lower.startswith("i vote "):
                rest = lower[7:].lstrip()
                token = rest.split()[0] if rest else ""
                token = token.strip(token_strip_chars)
                parsed = token_to_choice.get(token)
                if parsed:
                    return parsed

            stripped = lower.strip(" .!?,;:")
            if stripped in token_to_choice:
                return token_to_choice[stripped]

        # Fallback: if nothing matches, default to abstain (conservative).
        return VoteChoice.ABSTAIN

    async def _validate_vote_consensus(
        self,
        archon: ArchonProfile,
        motion: Motion,
        raw_vote: str,
    ) -> VoteChoice | None:
        """Validate a vote via 3-Archon Protocol secretary consensus.

        In the 3-Archon Protocol:
        - SECRETARY_TEXT (Orias): Analyzes via natural language
        - SECRETARY_JSON (Orobas): Analyzes via structured output
        Both must agree for consensus. WITNESS observes but cannot change outcome.

        Returns:
            VoteChoice if secretaries agree, otherwise None.
        """
        validator_ids = [vid for vid in self._config.vote_validation_archon_ids if vid]
        if len(validator_ids) < 2:
            return None

        max_attempts = max(1, self._config.vote_validation_max_attempts)
        for attempt in range(1, max_attempts + 1):
            choices: list[VoteChoice | None] = []
            for validator_id in validator_ids:
                choice = await self._request_vote_validation(
                    validator_id=validator_id,
                    archon=archon,
                    motion=motion,
                    raw_vote=raw_vote,
                    attempt=attempt,
                )
                choices.append(choice)

            if all(choice is not None for choice in choices):
                if len(set(choices)) == 1:
                    return choices[0]

        return None

    async def _request_vote_validation(
        self,
        validator_id: str,
        archon: ArchonProfile,
        motion: Motion,
        raw_vote: str,
        attempt: int,
    ) -> VoteChoice | None:
        """Ask a validator Archon to normalize a vote into AYE/NAY/ABSTAIN."""
        validator = self._profiles.get(validator_id)
        validator_name = validator.name if validator else validator_id

        prompt = f"""ARCHON 72 CONCLAVE - VOTE VALIDATION

You are validating a vote cast by another Archon.

TARGET ARCHON: {archon.name} ({archon.aegis_rank})
MOTION: {motion.title}

RAW VOTE RESPONSE:
<<<
{raw_vote[:2000]}
>>>

Return JSON only (no prose):
{{\"choice\": \"AYE\"}} or {{\"choice\": \"NAY\"}} or {{\"choice\": \"ABSTAIN\"}}
If unclear, choose ABSTAIN.
"""

        bundle = ContextBundle(
            bundle_id=uuid4(),
            topic_id=f"vote-validate-{motion.motion_id}-{archon.id}-{validator_id}-{attempt}",
            topic_content=prompt,
            metadata={
                "motion_id": str(motion.motion_id),
                "target_archon_id": archon.id,
                "validator_archon_id": validator_id,
                "validation_attempt": attempt,
                "validation": "vote",
            },
            created_at=datetime.now(timezone.utc),
        )

        try:
            output = await self._invoke_with_timeout(validator_id, bundle)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning(
                "vote_validation_error validator_id=%s validator_name=%s "
                "target_archon_id=%s error=%s",
                validator_id,
                validator_name,
                archon.id,
                exc,
            )
            return None

        return self._parse_validation_json(output.content)

    def _parse_validation_json(self, content: str) -> VoteChoice | None:
        """Parse validator JSON without regex (strict JSON)."""
        start = content.find("{")
        end = content.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None

        try:
            payload = json.loads(content[start : end + 1])
        except json.JSONDecodeError:
            return None

        raw_choice = str(payload.get("choice", "")).strip().lower()
        mapping = {
            "aye": VoteChoice.AYE,
            "for": VoteChoice.AYE,
            "yes": VoteChoice.AYE,
            "nay": VoteChoice.NAY,
            "against": VoteChoice.NAY,
            "no": VoteChoice.NAY,
            "abstain": VoteChoice.ABSTAIN,
        }
        return mapping.get(raw_choice)

    def _record_vote_validation_failure(
        self, archon: ArchonProfile, motion: Motion
    ) -> None:
        """Record a witnessed event when validators cannot reach consensus."""
        if not self._session:
            return

        description = (
            f"Vote validation failed for {archon.name} on motion "
            f"'{motion.title}'. Validators could not reach consensus."
        )

        self._session.add_transcript_entry(
            entry_type="procedural",
            content=description,
            speaker_id=archon.id,
            speaker_name=archon.name,
            metadata={
                "motion_id": str(motion.motion_id),
                "event": "vote_validation_non_consensus",
            },
        )

        validator_names = []
        for vid in self._config.vote_validation_archon_ids:
            profile = self._profiles.get(vid)
            validator_names.append(profile.name if profile else vid)

        self._observe_event(
            event_type="vote_validation_non_consensus",
            description=description,
            participants=[archon.name, *validator_names],
            target_id=str(motion.motion_id),
            target_type="motion",
            metadata={
                "archon_id": archon.id,
                "validator_ids": list(self._config.vote_validation_archon_ids),
            },
        )

    # =========================================================================
    # PERMISSION HELPERS (Government PRD)
    # =========================================================================

    def _get_original_rank(self, aegis_rank: str) -> str:
        """Map Aegis rank to original Ars Goetia rank.

        Args:
            aegis_rank: The Aegis rank (corporate terminology)

        Returns:
            Original Ars Goetia rank
        """
        rank_map = {
            "executive_director": "King",
            "senior_director": "President",
            "director": "Duke",
            "senior_manager": "Earl",
            "manager": "Prince",
            "senior_associate": "Marquis",
            "associate_director": "Prelate",
            "observer": "Knight",
        }
        return rank_map.get(aegis_rank, aegis_rank.replace("_", " ").title())

    def _detect_execution_details(self, content: str) -> list[str]:
        """Detect if content defines execution details (HOW) rather than intent (WHAT).

        Per Government PRD FR-GOV-6: Kings CANNOT define execution.
        This method identifies execution-defining content such as:
        - Task lists with specific steps
        - Timelines and schedules
        - Tool specifications
        - Resource allocations

        Args:
            content: The speech or motion text to analyze

        Returns:
            List of detected execution detail indicators
        """
        execution_indicators = []
        content_lower = content.lower()

        # Task list indicators
        task_patterns = [
            "step 1",
            "step 2",
            "first, ",
            "second, ",
            "third, ",
            "1. ",
            "2. ",
            "3. ",
            "- task:",
            "task list:",
            "action items:",
            "deliverables:",
        ]
        for pattern in task_patterns:
            if pattern in content_lower:
                execution_indicators.append(f"Task list detected: '{pattern}'")
                break

        # Timeline indicators
        timeline_patterns = [
            "by tomorrow",
            "within ",
            " days",
            " weeks",
            " hours",
            "deadline:",
            "schedule:",
            "timeline:",
            "due date:",
            "sprint",
            "milestone",
        ]
        for pattern in timeline_patterns:
            if pattern in content_lower:
                execution_indicators.append(f"Timeline specification: '{pattern}'")
                break

        # Tool/technology specifications
        tool_patterns = [
            "using python",
            "using javascript",
            "using ",
            "with api",
            "implement with",
            "tool:",
            "technology:",
            "framework:",
            "database:",
            "server:",
            "endpoint:",
        ]
        for pattern in tool_patterns:
            if pattern in content_lower:
                execution_indicators.append(f"Tool specification: '{pattern}'")
                break

        # Resource allocation
        resource_patterns = [
            "allocate ",
            "budget:",
            "resources:",
            "team:",
            "assign ",
            "delegate to",
            "responsible:",
        ]
        for pattern in resource_patterns:
            if pattern in content_lower:
                execution_indicators.append(f"Resource allocation: '{pattern}'")
                break

        return execution_indicators

    def _validate_speech_for_rank(
        self,
        archon: ArchonProfile,
        content: str,
        motion: Motion | None = None,
    ) -> tuple[bool, list[ViolationDetail]]:
        """Validate that a speech doesn't violate rank constraints.

        Per Government PRD FR-GOV-6: Kings define WHAT, not HOW.
        This checks if King-rank Archons are improperly defining execution details.

        Args:
            archon: The archon who gave the speech
            content: The speech content
            motion: Optional motion context

        Returns:
            Tuple of (is_valid, violation_details)
        """
        violations: list[ViolationDetail] = []

        # Check if this is a King-rank Archon
        is_king = archon.aegis_rank == "executive_director"

        if is_king:
            # Detect execution details in King's speech
            execution_details = self._detect_execution_details(content)

            if execution_details:
                for detail in execution_details:
                    violations.append(
                        ViolationDetail(
                            violated_constraint=f"VIOLATION: King defined HOW - {detail}",
                            severity=ViolationSeverity.MAJOR,
                            prd_reference="FR-GOV-6",
                            requires_witnessing=True,
                            requires_conclave_review=True,
                        )
                    )

                logger.warning(
                    "king_defined_execution_violation archon_id=%s archon_name=%s violations=%s",
                    archon.id,
                    archon.name,
                    execution_details,
                )

        return len(violations) == 0, violations

    def _flag_speech_violation(
        self,
        archon: ArchonProfile,
        violations: list[ViolationDetail],
        motion: Motion | None,
    ) -> None:
        """Record a speech violation in the transcript and witness log.

        Per Government PRD NFR-GOV-1: Violations must be visible.
        Per Government PRD FR-GOV-20: Knight records procedural violations.

        Args:
            archon: The archon who violated
            violations: List of violation details
            motion: Optional motion context
        """
        if not self._session:
            return

        for violation in violations:
            self._session.add_transcript_entry(
                entry_type="violation",
                content=violation.violated_constraint,
                speaker_id=archon.id,
                speaker_name=archon.name,
                metadata={
                    "severity": violation.severity.value,
                    "prd_reference": violation.prd_reference,
                    "requires_witnessing": violation.requires_witnessing,
                    "requires_conclave_review": violation.requires_conclave_review,
                    "motion_id": str(motion.motion_id) if motion else None,
                },
            )

            # Record violation via Knight-Witness (per FR-GOV-20)
            if self._knight_witness:
                violation_record = ViolationRecord(
                    violation_type="role_violation",
                    violator_id=UUID(archon.id),
                    violator_name=archon.name,
                    violator_rank=archon.aegis_rank,
                    description=violation.violated_constraint,
                    target_id=str(motion.motion_id) if motion else None,
                    target_type="motion" if motion else None,
                    prd_reference=violation.prd_reference,
                    requires_acknowledgment=violation.requires_conclave_review,
                    metadata={"severity": violation.severity.value},
                )
                self._knight_witness.record_violation(violation_record)

        self._emit_progress(
            "speech_violation_detected",
            f"{archon.name} speech flagged: {len(violations)} violation(s)",
            {
                "archon_name": archon.name,
                "archon_rank": archon.aegis_rank,
                "violations": [v.violated_constraint for v in violations],
            },
        )

    def _check_pending_acknowledgments(self) -> list[WitnessStatement]:
        """Check for pending acknowledgments that must be addressed.

        Per FR-GOV-22: Statements must be acknowledged before session proceeds.

        Returns:
            List of WitnessStatements requiring acknowledgment
        """
        if not self._knight_witness:
            return []

        pending = self._knight_witness.get_pending_acknowledgments()
        return [req.statement for req in pending]

    def _observe_event(
        self,
        event_type: str,
        description: str,
        participants: list[str],
        target_id: str | None = None,
        target_type: str | None = None,
        metadata: dict | None = None,
    ) -> WitnessStatement | None:
        """Observe a governance event via Knight-Witness.

        Per FR-GOV-20: Knight may observe all proceedings.

        Args:
            event_type: Type of event being observed
            description: Human-readable description
            participants: Archons involved
            target_id: Optional target ID
            target_type: Optional target type
            metadata: Additional data

        Returns:
            WitnessStatement if Knight-Witness is available, else None
        """
        if not self._knight_witness:
            return None

        context = ObservationContext(
            event_type=event_type,
            event_id=uuid4(),
            description=description,
            participants=participants,
            target_id=target_id,
            target_type=target_type,
            metadata=metadata or {},
        )
        return self._knight_witness.observe(context)

    # =========================================================================
    # SERIALIZATION
    # =========================================================================

    def _serialize_session(self, session: ConclaveSession) -> dict[str, Any]:
        """Serialize session to JSON-compatible dict."""
        pending_validations: list[dict[str, Any]] = []
        if self._async_validator:
            for job in self._async_validator.pending_jobs.values():
                pending_validations.append(
                    {
                        "vote_id": job.vote_id,
                        "session_id": job.session_id,
                        "motion_id": job.motion_id,
                        "archon_id": job.archon_id,
                        "archon_name": job.archon_name,
                        "optimistic_choice": job.optimistic_choice.value,
                        "vote_payload": job.vote_payload,
                    }
                )
        elif self._pending_validation_payloads:
            pending_validations = list(self._pending_validation_payloads)

        return {
            "session_id": str(session.session_id),
            "session_name": session.session_name,
            "started_at": session.started_at.isoformat(),
            "current_phase": session.current_phase.value,
            "current_agenda_index": session.current_agenda_index,
            "expected_participants": session.expected_participants,
            "present_participants": session.present_participants,
            "current_motion_index": session.current_motion_index,
            "ended_at": session.ended_at.isoformat() if session.ended_at else None,
            "total_debate_rounds": session.total_debate_rounds,
            "total_votes_cast": session.total_votes_cast,
            "motions": [self._serialize_motion(m) for m in session.motions],
            "transcript": [
                self._serialize_transcript_entry(t) for t in session.transcript
            ],
            "agenda": [self._serialize_agenda_item(a) for a in session.agenda],
            "pending_validations": pending_validations,
        }

    def _serialize_motion(self, motion: Motion) -> dict[str, Any]:
        """Serialize a motion to dict."""
        return {
            "motion_id": str(motion.motion_id),
            "motion_type": motion.motion_type.value,
            "title": motion.title,
            "text": motion.text,
            "proposer_id": motion.proposer_id,
            "proposer_name": motion.proposer_name,
            "proposed_at": motion.proposed_at.isoformat(),
            "seconder_id": motion.seconder_id,
            "seconder_name": motion.seconder_name,
            "seconded_at": motion.seconded_at.isoformat()
            if motion.seconded_at
            else None,
            "status": motion.status.value,
            "current_debate_round": motion.current_debate_round,
            "max_debate_rounds": motion.max_debate_rounds,
            "final_ayes": motion.final_ayes,
            "final_nays": motion.final_nays,
            "final_abstentions": motion.final_abstentions,
            "debate_entries": [
                {
                    "entry_id": str(e.entry_id),
                    "speaker_id": e.speaker_id,
                    "speaker_name": e.speaker_name,
                    "speaker_rank": e.speaker_rank,
                    "content": e.content,
                    "round_number": e.round_number,
                    "timestamp": e.timestamp.isoformat(),
                    "in_favor": e.in_favor,
                }
                for e in motion.debate_entries
            ],
            "votes": [
                {
                    "voter_id": v.voter_id,
                    "voter_name": v.voter_name,
                    "voter_rank": v.voter_rank,
                    "choice": v.choice.value,
                    "timestamp": v.timestamp.isoformat(),
                    "reasoning": v.reasoning,
                }
                for v in motion.votes
            ],
        }

    def _serialize_transcript_entry(self, entry: TranscriptEntry) -> dict[str, Any]:
        """Serialize a transcript entry to dict."""
        return {
            "entry_id": str(entry.entry_id),
            "timestamp": entry.timestamp.isoformat(),
            "phase": entry.phase.value,
            "speaker_id": entry.speaker_id,
            "speaker_name": entry.speaker_name,
            "entry_type": entry.entry_type,
            "content": entry.content,
            "metadata": entry.metadata,
        }

    def _serialize_agenda_item(self, item: AgendaItem) -> dict[str, Any]:
        """Serialize an agenda item to dict."""
        return {
            "item_id": str(item.item_id),
            "phase": item.phase.value,
            "title": item.title,
            "description": item.description,
            "presenter_id": item.presenter_id,
            "presenter_name": item.presenter_name,
            "completed": item.completed,
            "completed_at": item.completed_at.isoformat()
            if item.completed_at
            else None,
            "notes": item.notes,
        }

    def _deserialize_session(self, data: dict[str, Any]) -> ConclaveSession:
        """Deserialize session from dict."""
        session = ConclaveSession(
            session_id=UUID(data["session_id"]),
            session_name=data["session_name"],
            started_at=datetime.fromisoformat(data["started_at"]),
            current_phase=ConclavePhase(data["current_phase"]),
            current_agenda_index=data["current_agenda_index"],
            expected_participants=data["expected_participants"],
            present_participants=data["present_participants"],
            current_motion_index=data["current_motion_index"],
            ended_at=datetime.fromisoformat(data["ended_at"])
            if data["ended_at"]
            else None,
            total_debate_rounds=data["total_debate_rounds"],
            total_votes_cast=data["total_votes_cast"],
        )

        # Deserialize motions
        for m_data in data.get("motions", []):
            session.motions.append(self._deserialize_motion(m_data))

        # Deserialize transcript
        for t_data in data.get("transcript", []):
            session.transcript.append(self._deserialize_transcript_entry(t_data))

        # Deserialize agenda
        for a_data in data.get("agenda", []):
            session.agenda.append(self._deserialize_agenda_item(a_data))

        self._pending_validation_payloads = data.get("pending_validations", []) or []

        return session

    def _deserialize_motion(self, data: dict[str, Any]) -> Motion:
        """Deserialize a motion from dict."""
        motion = Motion(
            motion_id=UUID(data["motion_id"]),
            motion_type=MotionType(data["motion_type"]),
            title=data["title"],
            text=data["text"],
            proposer_id=data["proposer_id"],
            proposer_name=data["proposer_name"],
            proposed_at=datetime.fromisoformat(data["proposed_at"]),
            seconder_id=data.get("seconder_id"),
            seconder_name=data.get("seconder_name"),
            seconded_at=datetime.fromisoformat(data["seconded_at"])
            if data.get("seconded_at")
            else None,
            status=MotionStatus(data["status"]),
            current_debate_round=data["current_debate_round"],
            max_debate_rounds=data["max_debate_rounds"],
            final_ayes=data["final_ayes"],
            final_nays=data["final_nays"],
            final_abstentions=data["final_abstentions"],
        )

        # Deserialize debate entries
        for e_data in data.get("debate_entries", []):
            motion.debate_entries.append(
                DebateEntry(
                    entry_id=UUID(e_data["entry_id"]),
                    speaker_id=e_data["speaker_id"],
                    speaker_name=e_data["speaker_name"],
                    speaker_rank=e_data["speaker_rank"],
                    content=e_data["content"],
                    round_number=e_data["round_number"],
                    timestamp=datetime.fromisoformat(e_data["timestamp"]),
                    in_favor=e_data["in_favor"],
                )
            )

        # Deserialize votes
        for v_data in data.get("votes", []):
            motion.votes.append(
                Vote(
                    voter_id=v_data["voter_id"],
                    voter_name=v_data["voter_name"],
                    voter_rank=v_data["voter_rank"],
                    choice=VoteChoice(v_data["choice"]),
                    timestamp=datetime.fromisoformat(v_data["timestamp"]),
                    reasoning=v_data.get("reasoning"),
                )
            )

        return motion

    def _deserialize_transcript_entry(self, data: dict[str, Any]) -> TranscriptEntry:
        """Deserialize a transcript entry from dict."""
        return TranscriptEntry(
            entry_id=UUID(data["entry_id"]),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            phase=ConclavePhase(data["phase"]),
            speaker_id=data.get("speaker_id"),
            speaker_name=data.get("speaker_name"),
            entry_type=data["entry_type"],
            content=data["content"],
            metadata=data.get("metadata", {}),
        )

    def _deserialize_agenda_item(self, data: dict[str, Any]) -> AgendaItem:
        """Deserialize an agenda item from dict."""
        return AgendaItem(
            item_id=UUID(data["item_id"]),
            phase=ConclavePhase(data["phase"]),
            title=data["title"],
            description=data["description"],
            presenter_id=data.get("presenter_id"),
            presenter_name=data.get("presenter_name"),
            completed=data["completed"],
            completed_at=datetime.fromisoformat(data["completed_at"])
            if data.get("completed_at")
            else None,
            notes=data.get("notes", ""),
        )

    # =========================================================================
    # SESSION OUTPUT
    # =========================================================================

    def save_transcript(self, filename: str | None = None) -> Path:
        """Save the full session transcript to file.

        Args:
            filename: Optional custom filename

        Returns:
            Path to saved transcript
        """
        if not self._session:
            raise ValueError("No active session")

        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            filename = f"transcript-{self._session.session_id}-{timestamp}.md"

        output_path = self._config.output_dir / filename

        with open(output_path, "w") as f:
            f.write("# Archon 72 Conclave Transcript\n\n")
            f.write(f"**Session:** {self._session.session_name}\n")
            f.write(f"**Started:** {self._session.started_at.isoformat()}\n")
            if self._session.ended_at:
                f.write(f"**Ended:** {self._session.ended_at.isoformat()}\n")
            f.write(f"**Duration:** {self._session.duration / 60:.1f} minutes\n\n")
            f.write("---\n\n")

            current_phase = None
            for entry in self._session.transcript:
                if entry.phase != current_phase:
                    current_phase = entry.phase
                    f.write(f"\n## {current_phase.value.replace('_', ' ').title()}\n\n")

                timestamp = entry.timestamp.strftime("%H:%M:%S")
                if entry.speaker_name:
                    f.write(f"**[{timestamp}] {entry.speaker_name}:**\n")
                else:
                    f.write(f"**[{timestamp}] [{entry.entry_type.upper()}]:**\n")
                f.write(f"{entry.content}\n\n")

            # Summary
            f.write("\n---\n\n")
            f.write("## Summary\n\n")
            f.write(f"- Total motions: {len(self._session.motions)}\n")
            f.write(f"- Passed: {len(self._session.passed_motions)}\n")
            f.write(f"- Failed: {len(self._session.failed_motions)}\n")
            f.write(f"- Total votes cast: {self._session.total_votes_cast}\n")

        return output_path

    def get_session_summary(self) -> dict[str, Any]:
        """Get summary of the current session.

        Returns:
            Dict with session summary
        """
        if not self._session:
            raise ValueError("No active session")

        return {
            "session_id": str(self._session.session_id),
            "session_name": self._session.session_name,
            "phase": self._session.current_phase.value,
            "duration_minutes": self._session.duration / 60,
            "present_archons": len(self._session.present_participants),
            "total_archons": self._session.expected_participants,
            "has_quorum": self._session.has_quorum(),
            "motions_count": len(self._session.motions),
            "passed_motions": len(self._session.passed_motions),
            "failed_motions": len(self._session.failed_motions),
            "total_debate_rounds": self._session.total_debate_rounds,
            "total_votes_cast": self._session.total_votes_cast,
            "transcript_entries": len(self._session.transcript),
        }
