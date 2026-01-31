"""Domain models for the Duke Proposal Selection Pipeline.

After Administrative Dukes generate implementation proposals for a finalized RFP,
the 11 Executive Presidents review, score, rank, and deliberate to select a
winning proposal.

Pipeline Position:
    Legislative (Motion) -> Executive (RFP) -> Administrative (Duke Proposals)
      -> Executive (Proposal Selection) <- THIS
      -> Administrative (Execution)

Schema Versions:
    1.0: Initial version for competitive proposal selection
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

PROPOSAL_SELECTION_SCHEMA_VERSION = "1.0"


class SelectionStatus(str, Enum):
    """Status of the proposal selection pipeline."""

    SCORING = "SCORING"
    NOVELTY_ANALYSIS = "NOVELTY_ANALYSIS"
    AGGREGATION = "AGGREGATION"
    DELIBERATION = "DELIBERATION"
    DECIDED = "DECIDED"
    REVISION_REQUESTED = "REVISION_REQUESTED"
    ESCALATED = "ESCALATED"


class SelectionOutcome(str, Enum):
    """Outcome of the proposal selection pipeline."""

    WINNER_SELECTED = "WINNER_SELECTED"
    REVISION_NEEDED = "REVISION_NEEDED"
    NO_VIABLE_PROPOSAL = "NO_VIABLE_PROPOSAL"
    ESCALATE_TO_CONCLAVE = "ESCALATE_TO_CONCLAVE"


class ProposalTier(str, Enum):
    """Tier classification for ranked proposals."""

    FINALIST = "FINALIST"
    CONTENDER = "CONTENDER"
    BELOW_THRESHOLD = "BELOW_THRESHOLD"


# ------------------------------------------------------------------
# Scoring
# ------------------------------------------------------------------


@dataclass
class ProposalScore:
    """One President's score of one Duke proposal.

    Each President evaluates proposals across 6 dimensions on a 0-10 scale.
    """

    president_name: str
    proposal_id: str

    # 6 scoring dimensions (0-10 each)
    feasibility: float = 0.0
    completeness: float = 0.0
    risk_mitigation: float = 0.0
    resource_efficiency: float = 0.0
    innovation: float = 0.0
    alignment: float = 0.0

    # Aggregate
    overall_score: float = 0.0
    confidence: float = 0.5

    # Qualitative
    reasoning: str = ""
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)

    schema_version: str = PROPOSAL_SELECTION_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "artifact_type": "proposal_score",
            "president_name": self.president_name,
            "proposal_id": self.proposal_id,
            "dimensions": {
                "feasibility": self.feasibility,
                "completeness": self.completeness,
                "risk_mitigation": self.risk_mitigation,
                "resource_efficiency": self.resource_efficiency,
                "innovation": self.innovation,
                "alignment": self.alignment,
            },
            "overall_score": self.overall_score,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "strengths": self.strengths,
            "weaknesses": self.weaknesses,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProposalScore:
        dims = data.get("dimensions", {})
        return cls(
            president_name=data.get("president_name", ""),
            proposal_id=data.get("proposal_id", ""),
            feasibility=dims.get("feasibility", data.get("feasibility", 0.0)),
            completeness=dims.get("completeness", data.get("completeness", 0.0)),
            risk_mitigation=dims.get(
                "risk_mitigation", data.get("risk_mitigation", 0.0)
            ),
            resource_efficiency=dims.get(
                "resource_efficiency", data.get("resource_efficiency", 0.0)
            ),
            innovation=dims.get("innovation", data.get("innovation", 0.0)),
            alignment=dims.get("alignment", data.get("alignment", 0.0)),
            overall_score=data.get("overall_score", 0.0),
            confidence=data.get("confidence", 0.5),
            reasoning=data.get("reasoning", ""),
            strengths=data.get("strengths", []),
            weaknesses=data.get("weaknesses", []),
            schema_version=data.get(
                "schema_version", PROPOSAL_SELECTION_SCHEMA_VERSION
            ),
        )

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.president_name:
            errors.append("ProposalScore missing required field: president_name")
        if not self.proposal_id:
            errors.append("ProposalScore missing required field: proposal_id")
        for dim_name in (
            "feasibility",
            "completeness",
            "risk_mitigation",
            "resource_efficiency",
            "innovation",
            "alignment",
        ):
            val = getattr(self, dim_name)
            if not (0.0 <= val <= 10.0):
                errors.append(f"ProposalScore {dim_name} must be 0-10, got {val}")
        if not (0.0 <= self.confidence <= 1.0):
            errors.append(
                f"ProposalScore confidence must be 0-1, got {self.confidence}"
            )
        return errors


# ------------------------------------------------------------------
# Novelty
# ------------------------------------------------------------------


@dataclass
class ProposalNovelty:
    """Novelty annotation for a proposal."""

    proposal_id: str
    novelty_score: float = 0.0  # 0-1
    category: str = ""  # unconventional|cross-domain|minority-insight|creative
    novelty_reason: str = ""
    novel_elements: list[str] = field(default_factory=list)

    schema_version: str = PROPOSAL_SELECTION_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "artifact_type": "proposal_novelty",
            "proposal_id": self.proposal_id,
            "novelty_score": self.novelty_score,
            "category": self.category,
            "novelty_reason": self.novelty_reason,
            "novel_elements": self.novel_elements,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProposalNovelty:
        return cls(
            proposal_id=data.get("proposal_id", ""),
            novelty_score=data.get("novelty_score", 0.0),
            category=data.get("category", ""),
            novelty_reason=data.get("novelty_reason", ""),
            novel_elements=data.get("novel_elements", []),
            schema_version=data.get(
                "schema_version", PROPOSAL_SELECTION_SCHEMA_VERSION
            ),
        )

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.proposal_id:
            errors.append("ProposalNovelty missing required field: proposal_id")
        if not (0.0 <= self.novelty_score <= 1.0):
            errors.append(
                f"ProposalNovelty novelty_score must be 0-1, got {self.novelty_score}"
            )
        valid_categories = {
            "",
            "unconventional",
            "cross-domain",
            "minority-insight",
            "creative",
        }
        if self.category not in valid_categories:
            errors.append(f"ProposalNovelty invalid category: {self.category}")
        return errors


# ------------------------------------------------------------------
# Rankings
# ------------------------------------------------------------------


@dataclass
class ProposalRanking:
    """Aggregated ranking for one proposal across all Presidents."""

    proposal_id: str
    rank: int = 0

    # Statistical aggregates of overall_score
    mean_score: float = 0.0
    median_score: float = 0.0
    min_score: float = 0.0
    max_score: float = 0.0
    stddev_score: float = 0.0

    # Per-dimension means
    mean_feasibility: float = 0.0
    mean_completeness: float = 0.0
    mean_risk_mitigation: float = 0.0
    mean_resource_efficiency: float = 0.0
    mean_innovation: float = 0.0
    mean_alignment: float = 0.0

    # Novelty
    novelty_bonus: float = 0.0

    # Classification
    tier: ProposalTier = ProposalTier.BELOW_THRESHOLD

    # Supporters and critics
    supporters: list[str] = field(default_factory=list)
    critics: list[str] = field(default_factory=list)

    schema_version: str = PROPOSAL_SELECTION_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "artifact_type": "proposal_ranking",
            "proposal_id": self.proposal_id,
            "rank": self.rank,
            "statistics": {
                "mean": self.mean_score,
                "median": self.median_score,
                "min": self.min_score,
                "max": self.max_score,
                "stddev": self.stddev_score,
            },
            "dimension_means": {
                "feasibility": self.mean_feasibility,
                "completeness": self.mean_completeness,
                "risk_mitigation": self.mean_risk_mitigation,
                "resource_efficiency": self.mean_resource_efficiency,
                "innovation": self.mean_innovation,
                "alignment": self.mean_alignment,
            },
            "novelty_bonus": self.novelty_bonus,
            "tier": self.tier.value,
            "supporters": self.supporters,
            "critics": self.critics,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProposalRanking:
        stats = data.get("statistics", {})
        dims = data.get("dimension_means", {})
        return cls(
            proposal_id=data.get("proposal_id", ""),
            rank=data.get("rank", 0),
            mean_score=stats.get("mean", data.get("mean_score", 0.0)),
            median_score=stats.get("median", data.get("median_score", 0.0)),
            min_score=stats.get("min", data.get("min_score", 0.0)),
            max_score=stats.get("max", data.get("max_score", 0.0)),
            stddev_score=stats.get("stddev", data.get("stddev_score", 0.0)),
            mean_feasibility=dims.get("feasibility", data.get("mean_feasibility", 0.0)),
            mean_completeness=dims.get(
                "completeness", data.get("mean_completeness", 0.0)
            ),
            mean_risk_mitigation=dims.get(
                "risk_mitigation", data.get("mean_risk_mitigation", 0.0)
            ),
            mean_resource_efficiency=dims.get(
                "resource_efficiency", data.get("mean_resource_efficiency", 0.0)
            ),
            mean_innovation=dims.get("innovation", data.get("mean_innovation", 0.0)),
            mean_alignment=dims.get("alignment", data.get("mean_alignment", 0.0)),
            novelty_bonus=data.get("novelty_bonus", 0.0),
            tier=ProposalTier(data.get("tier", "BELOW_THRESHOLD")),
            supporters=data.get("supporters", []),
            critics=data.get("critics", []),
            schema_version=data.get(
                "schema_version", PROPOSAL_SELECTION_SCHEMA_VERSION
            ),
        )

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.proposal_id:
            errors.append("ProposalRanking missing required field: proposal_id")
        if self.rank < 0:
            errors.append(f"ProposalRanking rank must be >= 0, got {self.rank}")
        return errors


# ------------------------------------------------------------------
# Deliberation
# ------------------------------------------------------------------


@dataclass
class SelectionDeliberation:
    """Panel deliberation on finalist proposals."""

    finalist_proposal_ids: list[str] = field(default_factory=list)
    recommended_winner_id: str = ""
    recommendation_rationale: str = ""
    arguments_for: dict[str, list[str]] = field(default_factory=dict)
    arguments_against: dict[str, list[str]] = field(default_factory=dict)
    dissenting_opinions: list[str] = field(default_factory=list)
    votes: dict[str, str] = field(default_factory=dict)

    schema_version: str = PROPOSAL_SELECTION_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "artifact_type": "selection_deliberation",
            "finalist_proposal_ids": self.finalist_proposal_ids,
            "recommended_winner_id": self.recommended_winner_id,
            "recommendation_rationale": self.recommendation_rationale,
            "arguments_for": self.arguments_for,
            "arguments_against": self.arguments_against,
            "dissenting_opinions": self.dissenting_opinions,
            "votes": self.votes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SelectionDeliberation:
        return cls(
            finalist_proposal_ids=data.get("finalist_proposal_ids", []),
            recommended_winner_id=data.get("recommended_winner_id", ""),
            recommendation_rationale=data.get("recommendation_rationale", ""),
            arguments_for=data.get("arguments_for", {}),
            arguments_against=data.get("arguments_against", {}),
            dissenting_opinions=data.get("dissenting_opinions", []),
            votes=data.get("votes", {}),
            schema_version=data.get(
                "schema_version", PROPOSAL_SELECTION_SCHEMA_VERSION
            ),
        )

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.finalist_proposal_ids:
            errors.append(
                "SelectionDeliberation missing required field: finalist_proposal_ids"
            )
        return errors


# ------------------------------------------------------------------
# Revision guidance
# ------------------------------------------------------------------


@dataclass
class DukeRevisionGuidance:
    """Feedback for a Duke whose proposal needs revision."""

    proposal_id: str
    duke_name: str
    critical_weaknesses: list[str] = field(default_factory=list)
    improvement_areas: list[str] = field(default_factory=list)
    required_changes: list[str] = field(default_factory=list)
    revision_constraints: list[str] = field(default_factory=list)

    schema_version: str = PROPOSAL_SELECTION_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "artifact_type": "duke_revision_guidance",
            "proposal_id": self.proposal_id,
            "duke_name": self.duke_name,
            "critical_weaknesses": self.critical_weaknesses,
            "improvement_areas": self.improvement_areas,
            "required_changes": self.required_changes,
            "revision_constraints": self.revision_constraints,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DukeRevisionGuidance:
        return cls(
            proposal_id=data.get("proposal_id", ""),
            duke_name=data.get("duke_name", ""),
            critical_weaknesses=data.get("critical_weaknesses", []),
            improvement_areas=data.get("improvement_areas", []),
            required_changes=data.get("required_changes", []),
            revision_constraints=data.get("revision_constraints", []),
            schema_version=data.get(
                "schema_version", PROPOSAL_SELECTION_SCHEMA_VERSION
            ),
        )

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.proposal_id:
            errors.append("DukeRevisionGuidance missing required field: proposal_id")
        if not self.duke_name:
            errors.append("DukeRevisionGuidance missing required field: duke_name")
        return errors


# ------------------------------------------------------------------
# Selection handback (for revision loop)
# ------------------------------------------------------------------


@dataclass
class SelectionHandback:
    """Handback package for the Duke revision loop."""

    revision_guidance: list[DukeRevisionGuidance] = field(default_factory=list)
    global_constraints: list[str] = field(default_factory=list)
    focus_areas: list[str] = field(default_factory=list)
    winning_score_threshold: float = 7.0

    schema_version: str = PROPOSAL_SELECTION_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "artifact_type": "selection_handback",
            "revision_guidance": [g.to_dict() for g in self.revision_guidance],
            "global_constraints": self.global_constraints,
            "focus_areas": self.focus_areas,
            "winning_score_threshold": self.winning_score_threshold,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SelectionHandback:
        return cls(
            revision_guidance=[
                DukeRevisionGuidance.from_dict(g)
                for g in data.get("revision_guidance", [])
            ],
            global_constraints=data.get("global_constraints", []),
            focus_areas=data.get("focus_areas", []),
            winning_score_threshold=data.get("winning_score_threshold", 7.0),
            schema_version=data.get(
                "schema_version", PROPOSAL_SELECTION_SCHEMA_VERSION
            ),
        )

    def validate(self) -> list[str]:
        errors: list[str] = []
        for g in self.revision_guidance:
            errors.extend(g.validate())
        return errors


# ------------------------------------------------------------------
# Aggregate root
# ------------------------------------------------------------------


@dataclass
class ProposalSelectionResult:
    """Aggregate root for the entire proposal selection process."""

    selection_id: str
    status: SelectionStatus = SelectionStatus.SCORING
    outcome: SelectionOutcome | None = None
    winning_proposal_id: str = ""

    # Collected artifacts
    rankings: list[ProposalRanking] = field(default_factory=list)
    president_scores: list[ProposalScore] = field(default_factory=list)
    novelty_assessments: list[ProposalNovelty] = field(default_factory=list)
    deliberation: SelectionDeliberation | None = None
    revision_guidance: list[DukeRevisionGuidance] = field(default_factory=list)

    # Iteration tracking
    iteration_number: int = 1
    max_iterations: int = 3

    # Metadata
    rfp_id: str = ""
    mandate_id: str = ""
    created_at: str = ""

    schema_version: str = PROPOSAL_SELECTION_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "artifact_type": "proposal_selection_result",
            "selection_id": self.selection_id,
            "status": self.status.value,
            "outcome": self.outcome.value if self.outcome else None,
            "winning_proposal_id": self.winning_proposal_id,
            "rankings": [r.to_dict() for r in self.rankings],
            "president_scores": [s.to_dict() for s in self.president_scores],
            "novelty_assessments": [n.to_dict() for n in self.novelty_assessments],
            "deliberation": self.deliberation.to_dict() if self.deliberation else None,
            "revision_guidance": [g.to_dict() for g in self.revision_guidance],
            "iteration_number": self.iteration_number,
            "max_iterations": self.max_iterations,
            "rfp_id": self.rfp_id,
            "mandate_id": self.mandate_id,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProposalSelectionResult:
        delib_data = data.get("deliberation")
        return cls(
            selection_id=data.get("selection_id", ""),
            status=SelectionStatus(data.get("status", "SCORING")),
            outcome=SelectionOutcome(data["outcome"]) if data.get("outcome") else None,
            winning_proposal_id=data.get("winning_proposal_id", ""),
            rankings=[ProposalRanking.from_dict(r) for r in data.get("rankings", [])],
            president_scores=[
                ProposalScore.from_dict(s) for s in data.get("president_scores", [])
            ],
            novelty_assessments=[
                ProposalNovelty.from_dict(n)
                for n in data.get("novelty_assessments", [])
            ],
            deliberation=SelectionDeliberation.from_dict(delib_data)
            if delib_data
            else None,
            revision_guidance=[
                DukeRevisionGuidance.from_dict(g)
                for g in data.get("revision_guidance", [])
            ],
            iteration_number=data.get("iteration_number", 1),
            max_iterations=data.get("max_iterations", 3),
            rfp_id=data.get("rfp_id", ""),
            mandate_id=data.get("mandate_id", ""),
            created_at=data.get("created_at", ""),
            schema_version=data.get(
                "schema_version", PROPOSAL_SELECTION_SCHEMA_VERSION
            ),
        )

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.selection_id:
            errors.append(
                "ProposalSelectionResult missing required field: selection_id"
            )
        if not self.rfp_id:
            errors.append("ProposalSelectionResult missing required field: rfp_id")
        if not self.created_at:
            errors.append("ProposalSelectionResult missing required field: created_at")
        if self.outcome == SelectionOutcome.WINNER_SELECTED:
            if not self.winning_proposal_id:
                errors.append(
                    "ProposalSelectionResult: WINNER_SELECTED requires winning_proposal_id"
                )
        for score in self.president_scores:
            errors.extend(score.validate())
        for novelty in self.novelty_assessments:
            errors.extend(novelty.validate())
        for ranking in self.rankings:
            errors.extend(ranking.validate())
        if self.deliberation:
            errors.extend(self.deliberation.validate())
        for guidance in self.revision_guidance:
            errors.extend(guidance.validate())
        return errors
