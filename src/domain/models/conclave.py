"""Conclave domain models for formal meeting proceedings.

The Archon 72 Conclave follows parliamentary procedure with:
- Formal agenda phases (Opening, Reports, Old/New Business, Closing)
- Motion system (propose, second, debate, vote)
- Multi-round debate with rank-ordered speaking
- Supermajority (2/3) voting threshold
- Persistent state for multi-day sessions

Constitutional Constraints:
- FR10: 72 agents can deliberate concurrently without degradation
- FR9: All outputs through witnessing pipeline
- CT-11: Silent failure destroys legitimacy -> report all failures
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

# =============================================================================
# Exceptions (Story 6.6, FR-5.7, NFR-6.2)
# =============================================================================


class MotionProvenanceImmutabilityError(Exception):
    """Raised when attempting to modify immutable Motion provenance field.

    Per Story 6.6, FR-5.7, NFR-6.2: Once a Motion is created with source_petition_ref,
    that field is immutable and cannot be changed. This enforces the constitutional
    requirement that the link between Motion and source petition cannot be altered.
    """

    def __init__(
        self, motion_id: UUID | str, field_name: str, message: str | None = None
    ):
        self.motion_id = str(motion_id)
        self.field_name = field_name
        self.message = (
            message
            or f"Cannot modify {field_name} on Motion {motion_id} - provenance is immutable"
        )
        super().__init__(self.message)


# =============================================================================
# Enums
# =============================================================================


class ConclavePhase(Enum):
    """Phases of a formal Conclave meeting."""

    NOT_STARTED = "not_started"
    CALL_TO_ORDER = "call_to_order"
    ROLL_CALL = "roll_call"
    APPROVAL_OF_MINUTES = "approval_of_minutes"
    EXECUTIVE_REPORTS = "executive_reports"
    COMMITTEE_REPORTS = "committee_reports"
    OLD_BUSINESS = "old_business"
    NEW_BUSINESS = "new_business"
    ANNOUNCEMENTS = "announcements"
    ADJOURNMENT = "adjournment"
    ADJOURNED = "adjourned"

    # Special states
    RECESS = "recess"
    SUSPENDED = "suspended"  # For checkpoint/resume


class MotionType(Enum):
    """Types of motions that can be proposed."""

    CONSTITUTIONAL = "constitutional"  # Changes to governance rules
    POLICY = "policy"  # Policy decisions and procedures
    PROCEDURAL = "procedural"  # Meeting procedures (adjourn, recess, etc.)
    OPEN = "open"  # Open-ended motions on any topic


class MotionStatus(Enum):
    """Status of a motion through its lifecycle."""

    PROPOSED = "proposed"  # Motion introduced, awaiting second
    SECONDED = "seconded"  # Motion seconded, ready for debate
    DEBATING = "debating"  # Active debate in progress
    CALLED = "called"  # Question called, debate ended
    VOTING = "voting"  # Vote in progress
    PASSED = "passed"  # Motion passed (2/3 supermajority)
    FAILED = "failed"  # Motion failed to pass
    WITHDRAWN = "withdrawn"  # Proposer withdrew motion
    TABLED = "tabled"  # Motion deferred to future session


class VoteChoice(Enum):
    """Vote choices for motion voting."""

    AYE = "aye"
    NAY = "nay"
    ABSTAIN = "abstain"
    PRESENT = "present"  # Present but not voting


@dataclass
class DebateEntry:
    """A single entry in the debate on a motion."""

    entry_id: UUID
    speaker_id: str
    speaker_name: str
    speaker_rank: str
    content: str
    round_number: int
    timestamp: datetime
    in_favor: bool | None  # True=for, False=against, None=neutral
    is_red_team: bool = False  # True if this is a red-team adversarial entry

    @classmethod
    def create(
        cls,
        speaker_id: str,
        speaker_name: str,
        speaker_rank: str,
        content: str,
        round_number: int,
        in_favor: bool | None = None,
        is_red_team: bool = False,
    ) -> DebateEntry:
        return cls(
            entry_id=uuid4(),
            speaker_id=speaker_id,
            speaker_name=speaker_name,
            speaker_rank=speaker_rank,
            content=content,
            round_number=round_number,
            timestamp=datetime.now(timezone.utc),
            in_favor=in_favor,
            is_red_team=is_red_team,
        )


@dataclass
class Vote:
    """A single vote cast on a motion."""

    voter_id: str
    voter_name: str
    voter_rank: str
    choice: VoteChoice
    timestamp: datetime
    reasoning: str | None = None


@dataclass
class Motion:
    """A motion proposed during the Conclave.

    Motions follow parliamentary procedure:
    1. Proposer introduces motion
    2. Another Archon seconds (or motion dies)
    3. Debate proceeds in rank order, multiple rounds
    4. Question is called (ends debate)
    5. Vote is taken (2/3 supermajority required)

    Provenance (Story 6.6, FR-5.7, NFR-6.2):
    - source_petition_ref: Immutable reference to source petition (if adopted)
    - This field CANNOT be modified after Motion creation
    - Enforced at application layer and database level
    """

    motion_id: UUID
    motion_type: MotionType
    title: str
    text: str
    proposer_id: str
    proposer_name: str
    proposed_at: datetime

    # Provenance (Story 6.6, FR-5.7, NFR-6.2)
    # Immutable reference to source petition if Motion was created via adoption
    source_petition_ref: UUID | None = None

    # Seconding
    seconder_id: str | None = None
    seconder_name: str | None = None
    seconded_at: datetime | None = None

    # Status tracking
    status: MotionStatus = MotionStatus.PROPOSED

    # Debate
    debate_entries: list[DebateEntry] = field(default_factory=list)
    current_debate_round: int = 0
    max_debate_rounds: int = 5  # Can be extended

    # Debate digests - LLM-generated summaries created periodically during debate
    # Each digest summarizes the debate up to that point (FOR/AGAINST/key arguments)
    debate_digests: list[str] = field(default_factory=list)
    last_digest_entry_count: int = 0  # Track when last digest was generated
    last_digest_attempt_count: int = 0  # Track failed attempts to prevent infinite retry

    # Voting
    votes: list[Vote] = field(default_factory=list)
    vote_started_at: datetime | None = None
    vote_ended_at: datetime | None = None

    # Results
    final_ayes: int = 0
    final_nays: int = 0
    final_abstentions: int = 0

    @classmethod
    def create(
        cls,
        motion_type: MotionType,
        title: str,
        text: str,
        proposer_id: str,
        proposer_name: str,
        max_debate_rounds: int = 5,
    ) -> Motion:
        return cls(
            motion_id=uuid4(),
            motion_type=motion_type,
            title=title,
            text=text,
            proposer_id=proposer_id,
            proposer_name=proposer_name,
            proposed_at=datetime.now(timezone.utc),
            max_debate_rounds=max_debate_rounds,
        )

    def second(self, seconder_id: str, seconder_name: str) -> None:
        """Record a second for this motion."""
        if self.status != MotionStatus.PROPOSED:
            raise ValueError(f"Cannot second motion in status {self.status}")
        if seconder_id == self.proposer_id:
            raise ValueError("Proposer cannot second their own motion")

        self.seconder_id = seconder_id
        self.seconder_name = seconder_name
        self.seconded_at = datetime.now(timezone.utc)
        self.status = MotionStatus.SECONDED

    def begin_debate(self) -> None:
        """Begin debate on this motion."""
        if self.status != MotionStatus.SECONDED:
            raise ValueError(f"Cannot begin debate on motion in status {self.status}")
        self.status = MotionStatus.DEBATING
        self.current_debate_round = 1

    def add_debate_entry(self, entry: DebateEntry) -> None:
        """Add a debate entry."""
        if self.status != MotionStatus.DEBATING:
            raise ValueError(f"Cannot add debate in status {self.status}")
        self.debate_entries.append(entry)

    def next_debate_round(self) -> bool:
        """Advance to next debate round. Returns False if max reached."""
        if self.current_debate_round >= self.max_debate_rounds:
            return False
        self.current_debate_round += 1
        return True

    def call_question(self) -> None:
        """End debate and prepare for voting."""
        if self.status != MotionStatus.DEBATING:
            raise ValueError(f"Cannot call question on motion in status {self.status}")
        self.status = MotionStatus.CALLED

    def begin_voting(self) -> None:
        """Begin voting on this motion."""
        if self.status != MotionStatus.CALLED:
            raise ValueError(f"Cannot begin voting on motion in status {self.status}")
        self.status = MotionStatus.VOTING
        self.vote_started_at = datetime.now(timezone.utc)

    def cast_vote(self, vote: Vote) -> None:
        """Record a vote."""
        if self.status != MotionStatus.VOTING:
            raise ValueError(f"Cannot vote on motion in status {self.status}")
        # Check for duplicate votes
        if any(v.voter_id == vote.voter_id for v in self.votes):
            raise ValueError(f"Voter {vote.voter_id} has already voted")
        self.votes.append(vote)

    def tally_votes(self, total_voters: int) -> None:
        """Tally votes and determine outcome. Requires 2/3 supermajority."""
        if self.status != MotionStatus.VOTING:
            raise ValueError(f"Cannot tally votes on motion in status {self.status}")

        self.final_ayes = sum(1 for v in self.votes if v.choice == VoteChoice.AYE)
        self.final_nays = sum(1 for v in self.votes if v.choice == VoteChoice.NAY)
        self.final_abstentions = sum(
            1
            for v in self.votes
            if v.choice in (VoteChoice.ABSTAIN, VoteChoice.PRESENT)
        )

        # 2/3 supermajority of votes cast (excluding abstentions)
        votes_cast = self.final_ayes + self.final_nays
        if votes_cast == 0:
            self.status = MotionStatus.FAILED
        elif self.final_ayes >= (votes_cast * 2 / 3):
            self.status = MotionStatus.PASSED
        else:
            self.status = MotionStatus.FAILED

        self.vote_ended_at = datetime.now(timezone.utc)

    @property
    def is_resolved(self) -> bool:
        """Check if motion has reached a final state."""
        return self.status in (
            MotionStatus.PASSED,
            MotionStatus.FAILED,
            MotionStatus.WITHDRAWN,
            MotionStatus.TABLED,
        )


@dataclass
class AgendaItem:
    """An item on the Conclave agenda."""

    item_id: UUID
    phase: ConclavePhase
    title: str
    description: str
    presenter_id: str | None = None
    presenter_name: str | None = None
    motion: Motion | None = None  # If this item involves a motion
    completed: bool = False
    completed_at: datetime | None = None
    notes: str = ""

    @classmethod
    def create(
        cls,
        phase: ConclavePhase,
        title: str,
        description: str,
        presenter_id: str | None = None,
        presenter_name: str | None = None,
    ) -> AgendaItem:
        return cls(
            item_id=uuid4(),
            phase=phase,
            title=title,
            description=description,
            presenter_id=presenter_id,
            presenter_name=presenter_name,
        )


@dataclass
class TranscriptEntry:
    """A single entry in the meeting transcript."""

    entry_id: UUID
    timestamp: datetime
    phase: ConclavePhase
    speaker_id: str | None
    speaker_name: str | None
    entry_type: str  # "speech", "motion", "vote", "procedural", "system"
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        phase: ConclavePhase,
        entry_type: str,
        content: str,
        speaker_id: str | None = None,
        speaker_name: str | None = None,
        metadata: dict[str, Any] | None = None,
        timestamp: datetime | None = None,
    ) -> TranscriptEntry:
        return cls(
            entry_id=uuid4(),
            timestamp=timestamp or datetime.now(timezone.utc),
            phase=phase,
            speaker_id=speaker_id,
            speaker_name=speaker_name,
            entry_type=entry_type,
            content=content,
            metadata=metadata or {},
        )


@dataclass
class ConclaveSession:
    """A complete Conclave meeting session.

    Sessions persist to disk and can be resumed across restarts.
    This enables multi-day deliberations that run continuously.
    """

    session_id: UUID
    session_name: str
    started_at: datetime

    # Current state
    current_phase: ConclavePhase = ConclavePhase.NOT_STARTED
    current_agenda_index: int = 0

    # Participants
    expected_participants: int = 72
    present_participants: list[str] = field(default_factory=list)

    # Agenda
    agenda: list[AgendaItem] = field(default_factory=list)

    # Motions
    motions: list[Motion] = field(default_factory=list)
    current_motion_index: int | None = None

    # Transcript
    transcript: list[TranscriptEntry] = field(default_factory=list)

    # Persistence
    checkpoint_file: str | None = None
    last_checkpoint: datetime | None = None

    # Timing
    ended_at: datetime | None = None
    total_debate_rounds: int = 0
    total_votes_cast: int = 0

    @classmethod
    def create(
        cls,
        session_name: str,
        expected_participants: int = 72,
    ) -> ConclaveSession:
        return cls(
            session_id=uuid4(),
            session_name=session_name,
            started_at=datetime.now(timezone.utc),
            expected_participants=expected_participants,
        )

    def add_transcript_entry(
        self,
        entry_type: str,
        content: str,
        speaker_id: str | None = None,
        speaker_name: str | None = None,
        metadata: dict[str, Any] | None = None,
        timestamp: datetime | None = None,
    ) -> TranscriptEntry:
        """Add an entry to the meeting transcript.

        Args:
            entry_type: Type of entry (speech, vote, procedural, etc.)
            content: The content of the entry
            speaker_id: Optional speaker ID
            speaker_name: Optional speaker name
            metadata: Optional metadata dict
            timestamp: Optional timestamp (defaults to now if not provided).
                       Use this to preserve original event timestamps, e.g.,
                       when recording votes that were collected in parallel.
        """
        entry = TranscriptEntry.create(
            phase=self.current_phase,
            entry_type=entry_type,
            content=content,
            speaker_id=speaker_id,
            speaker_name=speaker_name,
            metadata=metadata,
            timestamp=timestamp,
        )
        self.transcript.append(entry)
        return entry

    def advance_phase(self, new_phase: ConclavePhase) -> None:
        """Advance to a new meeting phase."""
        self.add_transcript_entry(
            entry_type="procedural",
            content=f"Phase advanced from {self.current_phase.value} to {new_phase.value}",
        )
        self.current_phase = new_phase

    def mark_present(self, archon_id: str) -> None:
        """Mark an archon as present during roll call."""
        if archon_id not in self.present_participants:
            self.present_participants.append(archon_id)

    def has_quorum(self) -> bool:
        """Check if quorum is present (majority of expected participants)."""
        return len(self.present_participants) > (self.expected_participants // 2)

    def add_motion(self, motion: Motion) -> None:
        """Add a new motion to the session."""
        self.motions.append(motion)
        self.add_transcript_entry(
            entry_type="motion",
            content=f"Motion introduced: {motion.title}",
            speaker_id=motion.proposer_id,
            speaker_name=motion.proposer_name,
            metadata={"motion_id": str(motion.motion_id)},
        )

    @property
    def current_motion(self) -> Motion | None:
        """Get the currently active motion."""
        if self.current_motion_index is None:
            return None
        if self.current_motion_index >= len(self.motions):
            return None
        return self.motions[self.current_motion_index]

    @property
    def passed_motions(self) -> list[Motion]:
        """Get all motions that passed."""
        return [m for m in self.motions if m.status == MotionStatus.PASSED]

    @property
    def failed_motions(self) -> list[Motion]:
        """Get all motions that failed."""
        return [m for m in self.motions if m.status == MotionStatus.FAILED]

    @property
    def duration(self) -> float:
        """Get session duration in seconds."""
        end = self.ended_at or datetime.now(timezone.utc)
        return (end - self.started_at).total_seconds()

    def to_dict(self) -> dict[str, Any]:
        """Serialize session to dictionary for persistence."""
        return {
            "session_id": str(self.session_id),
            "session_name": self.session_name,
            "started_at": self.started_at.isoformat(),
            "current_phase": self.current_phase.value,
            "current_agenda_index": self.current_agenda_index,
            "expected_participants": self.expected_participants,
            "present_participants": self.present_participants,
            "current_motion_index": self.current_motion_index,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "total_debate_rounds": self.total_debate_rounds,
            "total_votes_cast": self.total_votes_cast,
            "checkpoint_file": self.checkpoint_file,
            "last_checkpoint": self.last_checkpoint.isoformat()
            if self.last_checkpoint
            else None,
            # Note: agenda, motions, and transcript serialized separately for efficiency
        }


# Rank ordering for speaking order (highest to lowest)
RANK_ORDER = [
    "executive_director",  # Kings - speak first
    "senior_director",  # Dukes
    "director",  # Marquis
    "managing_director",  # Presidents
    "strategic_director",  # Prince/Earl/Knight - speak last
]


def get_rank_priority(rank: str) -> int:
    """Get speaking priority for a rank (lower = speaks first)."""
    try:
        return RANK_ORDER.index(rank)
    except ValueError:
        return len(RANK_ORDER)  # Unknown ranks speak last
