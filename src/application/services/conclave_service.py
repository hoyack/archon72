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

import json
import logging
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

    # Agent invocation
    agent_timeout_seconds: int = 180

    # Output settings
    output_dir: Path = field(default_factory=lambda: Path("_bmad-output/conclave"))


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
    ):
        """Initialize the Conclave service.

        Args:
            orchestrator: Agent orchestrator for LLM invocations
            archon_profiles: List of all Archon profiles
            config: Conclave configuration
            permission_enforcer: Optional permission enforcer for rank-based permissions
            knight_witness: Optional Knight-Witness service for governance observation
        """
        self._orchestrator = orchestrator
        self._profiles = {p.id: p for p in archon_profiles}
        self._profiles_by_rank = self._sort_by_rank(archon_profiles)
        self._config = config or ConclaveConfig()
        self._permission_enforcer = permission_enforcer
        self._knight_witness = knight_witness

        # Current session state
        self._session: ConclaveSession | None = None
        self._progress_callback: ConclaveProgressCallback | None = None

        # Ensure output directories exist
        self._config.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self._config.output_dir.mkdir(parents=True, exist_ok=True)

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

        return await self._orchestrator.invoke(archon.id, bundle)

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
State clearly whether you are FOR, AGAINST, or NEUTRAL on the motion.
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

        All present Archons vote in rank order.

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

        self._emit_progress(
            "voting_start",
            "Voting has begun",
            {"motion_id": str(motion.motion_id), "title": motion.title},
        )

        # Collect votes from all present archons
        total_voters = len(self._session.present_participants)

        for idx, archon_id in enumerate(self._session.present_participants):
            archon = self._profiles.get(archon_id)
            if not archon:
                continue

            current = idx + 1
            self._emit_progress(
                "archon_voting",
                f"Voting: {archon.name} ({current}/{total_voters})",
                {"archon": archon.name, "progress": f"{current}/{total_voters}"},
            )

            try:
                vote = await self._get_archon_vote(archon, motion)
                motion.cast_vote(vote)

                self._session.add_transcript_entry(
                    entry_type="vote",
                    content=f"Vote: {vote.choice.value.upper()}",
                    speaker_id=archon_id,
                    speaker_name=archon.name,
                    metadata={
                        "motion_id": str(motion.motion_id),
                        "choice": vote.choice.value,
                    },
                )

            except Exception as e:
                logger.error(f"Error getting vote from {archon.name}: {e}")
                # Record abstention on error
                vote = Vote(
                    voter_id=archon_id,
                    voter_name=archon.name,
                    voter_rank=archon.aegis_rank,
                    choice=VoteChoice.ABSTAIN,
                    timestamp=datetime.now(timezone.utc),
                    reasoning=f"Vote error: {e}",
                )
                motion.cast_vote(vote)

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

    async def _get_archon_vote(self, archon: ArchonProfile, motion: Motion) -> Vote:
        """Get a vote from an archon.

        Args:
            archon: The archon voting
            motion: The motion being voted on

        Returns:
            Vote object
        """
        # Build voting context
        vote_context = f"""ARCHON 72 CONCLAVE - FORMAL VOTE

MOTION: {motion.title}
TYPE: {motion.motion_type.value.upper()}

MOTION TEXT:
{motion.text}

You must now cast your vote on this motion.
Based on the debate and your own judgment, vote:
- AYE (support the motion)
- NAY (oppose the motion)
- ABSTAIN (decline to vote)

State your vote clearly as "I VOTE AYE", "I VOTE NAY", or "I ABSTAIN".
You may briefly explain your reasoning.
"""

        bundle = ContextBundle(
            bundle_id=uuid4(),
            topic_id=f"vote-{motion.motion_id}",
            topic_content=vote_context,
            metadata={"motion_id": str(motion.motion_id), "voting": "true"},
            created_at=datetime.now(timezone.utc),
        )

        output = await self._orchestrator.invoke(archon.id, bundle)

        # Parse the vote
        choice = self._parse_vote(output.content)

        return Vote(
            voter_id=archon.id,
            voter_name=archon.name,
            voter_rank=archon.aegis_rank,
            choice=choice,
            timestamp=datetime.now(timezone.utc),
            reasoning=output.content[:500],  # Truncate reasoning
        )

    def _parse_vote(self, content: str) -> VoteChoice:
        """Parse a vote from archon response.

        Args:
            content: The response text

        Returns:
            VoteChoice
        """
        content_lower = content.lower()

        if "vote aye" in content_lower or "i vote aye" in content_lower:
            return VoteChoice.AYE
        elif "vote nay" in content_lower or "i vote nay" in content_lower:
            return VoteChoice.NAY
        elif "abstain" in content_lower or "i abstain" in content_lower:
            return VoteChoice.ABSTAIN
        else:
            # Default to abstain if unclear
            return VoteChoice.ABSTAIN

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
                    "king_defined_execution_violation",
                    archon_id=archon.id,
                    archon_name=archon.name,
                    violations=execution_details,
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
