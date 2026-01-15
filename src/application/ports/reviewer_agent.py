"""Port definition for Reviewer agent operations.

This port defines the interface for LLM-powered motion review by Archons.
The Reviewer agent enables each Archon to analyze mega-motions and provide
structured feedback including endorsements, oppositions, and amendments.

Operations:
1. Review a mega-motion and provide stance
2. Detect conflicts between Archon's positions and motion content
3. Participate in panel deliberations
4. Synthesize amendments from multiple proposals

Constitutional Compliance:
- CT-11: All review operations must be logged, failures reported
- CT-12: All responses must be attributed to the reviewing Archon
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class MotionReviewContext:
    """Context for reviewing a single mega-motion."""

    mega_motion_id: str
    mega_motion_title: str
    mega_motion_text: str
    theme: str
    source_motion_count: int
    supporting_archon_count: int
    supporting_archons: list[str]
    conflict_flag: str | None = None  # If Archon has known conflict
    assignment_reason: str = "gap_archon"  # Why Archon is reviewing


@dataclass
class ArchonReviewerContext:
    """Context about the reviewing Archon."""

    archon_id: str
    archon_name: str
    archon_role: str
    archon_backstory: str
    domain: str | None = None
    previous_positions: list[str] = field(default_factory=list)


@dataclass
class ReviewDecision:
    """An Archon's decision on a mega-motion."""

    stance: str  # "endorse" | "oppose" | "amend" | "abstain"
    reasoning: str
    confidence: float  # 0-1

    # For opposition
    opposition_concerns: list[str] = field(default_factory=list)

    # For amendment
    amendment_type: str | None = None  # "minor_wording" | "major_revision" | "add_clause" | "remove_clause"
    amendment_text: str | None = None
    amendment_rationale: str | None = None

    # Metadata
    review_duration_ms: int = 0


@dataclass
class ConflictAnalysis:
    """Analysis of conflicts between an Archon's positions and a motion."""

    has_conflict: bool
    conflict_severity: str  # "none" | "minor" | "moderate" | "major"
    conflict_description: str | None = None
    archon_position: str | None = None
    motion_position: str | None = None
    reconciliation_possible: bool = True
    suggested_resolution: str | None = None


@dataclass
class PanelDeliberationContext:
    """Context for panel deliberation on a contested motion."""

    panel_id: str
    mega_motion_id: str
    mega_motion_title: str
    mega_motion_text: str

    # Panel composition
    supporters: list[ArchonReviewerContext]
    critics: list[ArchonReviewerContext]
    neutrals: list[ArchonReviewerContext]

    # Arguments collected
    supporter_arguments: list[str] = field(default_factory=list)
    critic_arguments: list[str] = field(default_factory=list)

    # Proposed amendments
    proposed_amendments: list[str] = field(default_factory=list)

    time_limit_minutes: int = 45


@dataclass
class PanelDeliberationResult:
    """Result of a panel deliberation."""

    panel_id: str
    mega_motion_id: str

    # Recommendation
    recommendation: str  # "pass" | "fail" | "amend" | "defer"
    recommendation_rationale: str

    # Vote breakdown
    votes: dict[str, str]  # archon_name -> vote

    # If amended
    revised_motion_text: str | None = None
    revision_summary: str | None = None

    # Dissenting opinions
    dissenting_opinions: list[dict[str, str]] = field(default_factory=list)

    # Summary
    key_points_discussed: list[str] = field(default_factory=list)
    consensus_areas: list[str] = field(default_factory=list)
    unresolved_concerns: list[str] = field(default_factory=list)

    deliberation_duration_ms: int = 0


@dataclass
class AmendmentSynthesis:
    """Synthesized amendment from multiple proposals."""

    original_motion_text: str
    synthesized_amendment: str
    incorporated_proposals: list[str]  # Which amendment proposals were included
    excluded_proposals: list[str]  # Which were not compatible
    synthesis_rationale: str
    archons_satisfied: list[str]  # Archons whose concerns were addressed


class ReviewerAgentProtocol(ABC):
    """Port for Reviewer agent operations using LLM enhancement.

    This protocol defines the interface for LLM-powered motion review.
    Implementations handle the actual CrewAI or LLM invocation details.

    The Reviewer agent operates in the context of a specific Archon,
    maintaining their personality, expertise, and prior positions.
    """

    @abstractmethod
    async def review_motion(
        self,
        archon: ArchonReviewerContext,
        motion: MotionReviewContext,
    ) -> ReviewDecision:
        """Have an Archon review a mega-motion and provide stance.

        The Archon analyzes the motion through their unique perspective,
        considering their domain expertise, prior positions, and the
        motion's alignment with their principles.

        Args:
            archon: Context about the reviewing Archon
            motion: The motion to review

        Returns:
            ReviewDecision with stance, reasoning, and any amendments

        Raises:
            ReviewerAgentError: If review fails
        """
        ...

    @abstractmethod
    async def detect_conflict(
        self,
        archon: ArchonReviewerContext,
        motion: MotionReviewContext,
        archon_prior_statements: list[str],
    ) -> ConflictAnalysis:
        """Detect conflicts between an Archon's positions and a motion.

        Analyzes whether the motion contradicts or conflicts with
        positions the Archon has previously taken.

        Args:
            archon: Context about the Archon
            motion: The motion to check against
            archon_prior_statements: Previous statements/positions by this Archon

        Returns:
            ConflictAnalysis with conflict details and resolution suggestions

        Raises:
            ReviewerAgentError: If conflict detection fails
        """
        ...

    @abstractmethod
    async def run_panel_deliberation(
        self,
        context: PanelDeliberationContext,
    ) -> PanelDeliberationResult:
        """Run a panel deliberation for a contested motion.

        Orchestrates a structured discussion between supporters,
        critics, and neutral domain experts to reach a panel
        recommendation.

        Args:
            context: Full panel deliberation context

        Returns:
            PanelDeliberationResult with recommendation and details

        Raises:
            ReviewerAgentError: If deliberation fails
        """
        ...

    @abstractmethod
    async def synthesize_amendments(
        self,
        motion_text: str,
        proposed_amendments: list[tuple[str, str]],  # (archon_name, amendment_text)
    ) -> AmendmentSynthesis:
        """Synthesize multiple amendment proposals into a coherent revision.

        When multiple Archons propose amendments, this synthesizes
        compatible changes into a single revised motion text.

        Args:
            motion_text: Original motion text
            proposed_amendments: List of (archon_name, amendment_text) tuples

        Returns:
            AmendmentSynthesis with synthesized text and rationale

        Raises:
            ReviewerAgentError: If synthesis fails
        """
        ...

    @abstractmethod
    async def batch_review_motions(
        self,
        archon: ArchonReviewerContext,
        motions: list[MotionReviewContext],
    ) -> list[ReviewDecision]:
        """Have an Archon review multiple motions efficiently.

        Batch processing for efficiency when an Archon has many
        motions to review.

        Args:
            archon: Context about the reviewing Archon
            motions: List of motions to review

        Returns:
            List of ReviewDecision, one per motion

        Raises:
            ReviewerAgentError: If any review fails
        """
        ...


class ReviewerAgentError(Exception):
    """Base exception for Reviewer agent operations."""

    pass


class ReviewError(ReviewerAgentError):
    """Error during motion review."""

    pass


class ConflictDetectionError(ReviewerAgentError):
    """Error during conflict detection."""

    pass


class DeliberationError(ReviewerAgentError):
    """Error during panel deliberation."""

    pass


class AmendmentSynthesisError(ReviewerAgentError):
    """Error during amendment synthesis."""

    pass
