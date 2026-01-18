"""Motion Review Pipeline domain models.

Defines entities for the multi-phase motion review process that avoids
combinatorial Conclave explosion by using implicit support, risk tiers,
and targeted review assignments.

Constitutional Compliance:
- All review responses are attributed and witnessed
- No silent paths - abstention is explicitly recorded
- Ratification requires supermajority (48/72) for constitutional amendments
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

# uuid4 used in service layer for ID generation


class RiskTier(Enum):
    """Risk tier determining review depth.

    - LOW: >66% implicit support, 0 conflicts -> fast-track to ratification
    - MEDIUM: 33-66% support OR minor conflicts -> targeted async review
    - HIGH: <33% support OR major conflicts OR novel -> full deliberation panel
    """

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ReviewStance(Enum):
    """Archon stance on a mega-motion during review."""

    ENDORSE = "endorse"
    OPPOSE = "oppose"
    AMEND = "amend"
    ABSTAIN = "abstain"


class MotionStatus(Enum):
    """Motion status through the pipeline."""

    PENDING_TRIAGE = "pending_triage"
    FAST_TRACK = "fast_track"  # Low risk - direct to ratification
    UNDER_REVIEW = "under_review"  # Medium risk - targeted review
    CONTESTED = "contested"  # High risk - panel deliberation
    RATIFICATION_READY = "ratification_ready"
    RATIFIED = "ratified"
    REJECTED = "rejected"
    DEFERRED = "deferred"


class AmendmentType(Enum):
    """Type of amendment proposed by an Archon."""

    MINOR_WORDING = "minor_wording"
    MAJOR_REVISION = "major_revision"
    ADD_CLAUSE = "add_clause"
    REMOVE_CLAUSE = "remove_clause"


class PanelRecommendation(Enum):
    """Deliberation panel recommendation."""

    PASS = "pass"
    FAIL = "fail"
    AMEND = "amend"
    DEFER = "defer"


class RatificationOutcome(Enum):
    """Final ratification vote outcome."""

    RATIFIED = "ratified"
    REJECTED = "rejected"
    DEFERRED = "deferred"


@dataclass
class ImplicitSupport:
    """Calculated implicit support for a mega-motion.

    Implicit support = Archons whose recommendations/motions were
    incorporated into this mega-motion's source materials.
    """

    mega_motion_id: str
    mega_motion_title: str
    contributing_archons: list[str]  # Archon names who authored sources
    contribution_count: int  # Total source contributions
    implicit_support_ratio: float  # contributing / 72
    gap_archons: list[str]  # Archon names who need to review
    potential_conflicts: list[str]  # Archon names with opposing positions
    conflict_details: dict[str, str]  # archon_name -> conflict reason
    risk_tier: RiskTier
    is_novel_proposal: bool = False
    calculated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def support_count(self) -> int:
        """Number of Archons with implicit support."""
        return len(self.contributing_archons)

    @property
    def gap_count(self) -> int:
        """Number of Archons requiring explicit review."""
        return len(self.gap_archons)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "mega_motion_id": self.mega_motion_id,
            "mega_motion_title": self.mega_motion_title,
            "contributing_archons": self.contributing_archons,
            "contribution_count": self.contribution_count,
            "implicit_support_ratio": self.implicit_support_ratio,
            "gap_archons": self.gap_archons,
            "potential_conflicts": self.potential_conflicts,
            "conflict_details": self.conflict_details,
            "risk_tier": self.risk_tier.value,
            "is_novel_proposal": self.is_novel_proposal,
            "calculated_at": self.calculated_at.isoformat(),
        }


@dataclass
class ReviewAssignment:
    """Personalized review assignment for an Archon.

    Each Archon receives a packet containing only motions they
    need to explicitly review (didn't contribute to).
    """

    archon_id: str
    archon_name: str
    assigned_motions: list[str]  # Motion IDs to review
    conflict_flags: dict[str, str]  # motion_id -> conflict reason
    already_endorsed: list[str]  # Motion IDs with implicit support
    assignment_reasons: dict[str, str]  # motion_id -> "gap_archon"|"conflict"|"expert"
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def assignment_count(self) -> int:
        """Number of motions assigned for review."""
        return len(self.assigned_motions)

    @property
    def has_conflicts(self) -> bool:
        """Whether any assigned motions have conflict flags."""
        return len(self.conflict_flags) > 0

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for packet generation."""
        return {
            "archon_id": self.archon_id,
            "archon_name": self.archon_name,
            "assigned_motions": self.assigned_motions,
            "conflict_flags": self.conflict_flags,
            "already_endorsed": self.already_endorsed,
            "assignment_reasons": self.assignment_reasons,
            "generated_at": self.generated_at.isoformat(),
            "statistics": {
                "assignment_count": self.assignment_count,
                "implicit_endorsements": len(self.already_endorsed),
                "conflicts_flagged": len(self.conflict_flags),
            },
        }


@dataclass
class ReviewResponse:
    """An Archon's response to a motion review."""

    response_id: str
    archon_id: str
    archon_name: str
    mega_motion_id: str
    stance: ReviewStance
    amendment_type: AmendmentType | None = None  # If stance is AMEND
    amendment_text: str | None = None
    amendment_rationale: str | None = None
    opposition_reason: str | None = None  # If stance is OPPOSE
    reasoning: str = ""
    confidence: float = 0.8  # 0-1, self-reported
    review_duration_ms: int = 0  # Time taken for LLM review
    reviewed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def validate(self) -> list[str]:
        """Validate response completeness."""
        errors = []

        if self.stance == ReviewStance.OPPOSE:
            if not self.opposition_reason:
                errors.append("Opposition requires reasoning")
            elif len(self.opposition_reason) < 50:
                errors.append("Opposition reasoning must be substantive (50+ chars)")

        if self.stance == ReviewStance.AMEND:
            if not self.amendment_text:
                errors.append("Amendment requires proposed text")
            if not self.amendment_type:
                errors.append("Amendment requires type classification")
            if not self.amendment_rationale:
                errors.append("Amendment requires rationale")

        return errors

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "response_id": self.response_id,
            "archon_id": self.archon_id,
            "archon_name": self.archon_name,
            "mega_motion_id": self.mega_motion_id,
            "stance": self.stance.value,
            "amendment_type": self.amendment_type.value
            if self.amendment_type
            else None,
            "amendment_text": self.amendment_text,
            "amendment_rationale": self.amendment_rationale,
            "opposition_reason": self.opposition_reason,
            "reasoning": self.reasoning,
            "confidence": self.confidence,
            "reviewed_at": self.reviewed_at.isoformat(),
        }


@dataclass
class ReviewAggregation:
    """Aggregated review results for a mega-motion."""

    mega_motion_id: str
    mega_motion_title: str

    # Counts
    implicit_endorsements: int  # From source contributions
    explicit_endorsements: int  # From review responses
    total_endorsements: int  # implicit + explicit
    oppositions: int
    amendments_proposed: int
    abstentions: int
    no_response: int

    # Ratios (against engaged voters, not total 72)
    engaged_count: int  # 72 - no_response
    endorsement_ratio: float  # total_endorsements / engaged
    opposition_ratio: float

    # Derived status
    consensus_reached: bool  # endorsement_ratio >= 0.75
    contested: bool  # opposition_ratio >= 0.25
    needs_amendment_synthesis: bool  # amendments_proposed >= 3

    # Collections
    amendment_texts: list[str] = field(default_factory=list)
    opposition_reasons: list[str] = field(default_factory=list)
    endorsing_archons: list[str] = field(default_factory=list)
    opposing_archons: list[str] = field(default_factory=list)

    aggregated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def status(self) -> MotionStatus:
        """Determine motion status from aggregation."""
        if self.contested:
            return MotionStatus.CONTESTED
        if self.consensus_reached:
            return MotionStatus.RATIFICATION_READY
        return MotionStatus.UNDER_REVIEW

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "mega_motion_id": self.mega_motion_id,
            "mega_motion_title": self.mega_motion_title,
            "implicit_endorsements": self.implicit_endorsements,
            "explicit_endorsements": self.explicit_endorsements,
            "total_endorsements": self.total_endorsements,
            "oppositions": self.oppositions,
            "amendments_proposed": self.amendments_proposed,
            "abstentions": self.abstentions,
            "no_response": self.no_response,
            "engaged_count": self.engaged_count,
            "endorsement_ratio": self.endorsement_ratio,
            "opposition_ratio": self.opposition_ratio,
            "consensus_reached": self.consensus_reached,
            "contested": self.contested,
            "needs_amendment_synthesis": self.needs_amendment_synthesis,
            "status": self.status.value,
            "amendment_texts": self.amendment_texts,
            "opposition_reasons": self.opposition_reasons,
            "endorsing_archons": self.endorsing_archons,
            "opposing_archons": self.opposing_archons,
            "aggregated_at": self.aggregated_at.isoformat(),
        }


@dataclass
class DeliberationPanel:
    """Panel composition for contested motion deliberation."""

    panel_id: str
    mega_motion_id: str
    mega_motion_title: str

    # Panel composition (7-9 members)
    supporters: list[str]  # 3 Archon names
    critics: list[str]  # 3 Archon names
    neutrals: list[str]  # 1-3 Archon names (domain experts)

    # Session parameters
    time_limit_minutes: int = 45
    scheduled_at: datetime | None = None

    # Outcomes (populated after deliberation)
    recommendation: PanelRecommendation | None = None
    revised_motion_text: str | None = None
    revision_rationale: str | None = None
    dissenting_opinions: list[dict[str, str]] = field(
        default_factory=list
    )  # [{archon_name, opinion_text}]

    # Vote breakdown
    pass_votes: int = 0
    fail_votes: int = 0
    amend_votes: int = 0
    defer_votes: int = 0

    concluded_at: datetime | None = None
    deliberation_duration_minutes: int | None = None

    @property
    def panel_size(self) -> int:
        """Total panel members."""
        return len(self.supporters) + len(self.critics) + len(self.neutrals)

    @property
    def all_members(self) -> list[str]:
        """All panel member names."""
        return self.supporters + self.critics + self.neutrals

    @property
    def is_concluded(self) -> bool:
        """Whether deliberation has concluded."""
        return self.concluded_at is not None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "panel_id": self.panel_id,
            "mega_motion_id": self.mega_motion_id,
            "mega_motion_title": self.mega_motion_title,
            "supporters": self.supporters,
            "critics": self.critics,
            "neutrals": self.neutrals,
            "panel_size": self.panel_size,
            "time_limit_minutes": self.time_limit_minutes,
            "scheduled_at": self.scheduled_at.isoformat()
            if self.scheduled_at
            else None,
            "recommendation": self.recommendation.value
            if self.recommendation
            else None,
            "revised_motion_text": self.revised_motion_text,
            "revision_rationale": self.revision_rationale,
            "dissenting_opinions": self.dissenting_opinions,
            "vote_breakdown": {
                "pass": self.pass_votes,
                "fail": self.fail_votes,
                "amend": self.amend_votes,
                "defer": self.defer_votes,
            },
            "concluded_at": self.concluded_at.isoformat()
            if self.concluded_at
            else None,
            "deliberation_duration_minutes": self.deliberation_duration_minutes,
        }


@dataclass
class RatificationVote:
    """Final ratification vote record."""

    vote_id: str
    mega_motion_id: str
    mega_motion_title: str

    # Vote counts
    yeas: int
    nays: int
    abstentions: int

    # Thresholds
    threshold_type: str  # "simple_majority" | "supermajority"
    threshold_required: int  # 37 for simple, 48 for super
    threshold_met: bool

    # Attribution
    votes_by_archon: dict[str, str]  # archon_name -> "yea"|"nay"|"abstain"

    # Outcome
    outcome: RatificationOutcome
    ratified_at: datetime | None = None

    @property
    def total_votes(self) -> int:
        """Total votes cast."""
        return self.yeas + self.nays + self.abstentions

    @property
    def participation_rate(self) -> float:
        """Voting participation rate (out of 72)."""
        return self.total_votes / 72

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "vote_id": self.vote_id,
            "mega_motion_id": self.mega_motion_id,
            "mega_motion_title": self.mega_motion_title,
            "yeas": self.yeas,
            "nays": self.nays,
            "abstentions": self.abstentions,
            "total_votes": self.total_votes,
            "participation_rate": self.participation_rate,
            "threshold_type": self.threshold_type,
            "threshold_required": self.threshold_required,
            "threshold_met": self.threshold_met,
            "outcome": self.outcome.value,
            "ratified_at": self.ratified_at.isoformat() if self.ratified_at else None,
        }


@dataclass
class TriageResult:
    """Result of Phase 1 triage."""

    session_id: str
    triaged_at: datetime
    total_motions: int
    novel_proposals_count: int

    # Risk tier counts
    low_risk_count: int
    medium_risk_count: int
    high_risk_count: int

    # Detailed results
    implicit_supports: list[ImplicitSupport]

    # Summary statistics
    average_implicit_support: float
    total_conflicts_detected: int

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "session_id": self.session_id,
            "triaged_at": self.triaged_at.isoformat(),
            "summary": {
                "total_motions": self.total_motions,
                "novel_proposals": self.novel_proposals_count,
                "low_risk": self.low_risk_count,
                "medium_risk": self.medium_risk_count,
                "high_risk": self.high_risk_count,
                "average_implicit_support": self.average_implicit_support,
                "total_conflicts": self.total_conflicts_detected,
            },
            "motions": [s.to_dict() for s in self.implicit_supports],
        }


@dataclass
class MotionReviewPipelineResult:
    """Complete result of the motion review pipeline."""

    # Session info
    session_id: str
    session_name: str
    started_at: datetime
    completed_at: datetime | None = None

    # Input counts
    mega_motions_input: int = 0
    novel_proposals_input: int = 0

    # Phase 1: Triage
    triage_result: TriageResult | None = None

    # Phase 2: Assignments
    review_assignments: list[ReviewAssignment] = field(default_factory=list)
    total_assignments: int = 0
    average_assignments_per_archon: float = 0.0

    # Phase 3-4: Review & Aggregation
    review_responses: list[ReviewResponse] = field(default_factory=list)
    response_rate: float = 0.0  # responses / assignments
    aggregations: list[ReviewAggregation] = field(default_factory=list)

    # Phase 5: Deliberation
    panels_convened: int = 0
    panel_results: list[DeliberationPanel] = field(default_factory=list)

    # Phase 6: Ratification
    ratification_votes: list[RatificationVote] = field(default_factory=list)
    motions_ratified: int = 0
    motions_rejected: int = 0
    motions_deferred: int = 0

    # Traceability
    audit_trail: list[dict[str, Any]] = field(default_factory=list)

    def add_audit_event(
        self,
        event_type: str,
        details: dict[str, Any],
        attributed_to: list[str] | None = None,
    ) -> None:
        """Add an event to the audit trail."""
        self.audit_trail.append(
            {
                "event_type": event_type,
                "occurred_at": datetime.now(timezone.utc).isoformat(),
                "session_id": self.session_id,
                "attributed_to": attributed_to or [],
                "details": details,
            }
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "session_id": self.session_id,
            "session_name": self.session_name,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat()
            if self.completed_at
            else None,
            "input": {
                "mega_motions": self.mega_motions_input,
                "novel_proposals": self.novel_proposals_input,
            },
            "triage": self.triage_result.to_dict() if self.triage_result else None,
            "assignments": {
                "total": self.total_assignments,
                "average_per_archon": self.average_assignments_per_archon,
                "details": [a.to_dict() for a in self.review_assignments],
            },
            "reviews": {
                "response_count": len(self.review_responses),
                "response_rate": self.response_rate,
                "aggregations": [a.to_dict() for a in self.aggregations],
            },
            "deliberation": {
                "panels_convened": self.panels_convened,
                "panels": [p.to_dict() for p in self.panel_results],
            },
            "ratification": {
                "votes": [v.to_dict() for v in self.ratification_votes],
                "ratified": self.motions_ratified,
                "rejected": self.motions_rejected,
                "deferred": self.motions_deferred,
            },
            "audit_trail": self.audit_trail,
        }
