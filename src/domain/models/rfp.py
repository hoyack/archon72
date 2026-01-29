"""Domain models for Executive Implementation Dossier generation.

The Executive dossier sits between Legislative (WHAT) and Administrative (WHO does HOW).
Executive branch translates mandates into requirements without prescribing implementation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4


class RequirementPriority(Enum):
    """MoSCoW prioritization for requirements."""

    MUST = "must"  # Non-negotiable, solution fails without this
    SHOULD = "should"  # Important, but workarounds exist
    COULD = "could"  # Desirable if resources allow
    WONT = "wont"  # Explicitly out of scope for this iteration


class RequirementCategory(Enum):
    """Categories for non-functional requirements."""

    PERFORMANCE = "performance"
    SECURITY = "security"
    RELIABILITY = "reliability"
    SCALABILITY = "scalability"
    USABILITY = "usability"
    COMPLIANCE = "compliance"
    MAINTAINABILITY = "maintainability"
    INTEROPERABILITY = "interoperability"


class ConstraintType(Enum):
    """Types of constraints."""

    TECHNICAL = "technical"
    RESOURCE = "resource"
    ORGANIZATIONAL = "organizational"
    TEMPORAL = "temporal"
    REGULATORY = "regulatory"


class ResourceType(Enum):
    """Types of resource constraints."""

    BUDGET = "budget"
    TIME = "time"
    CAPACITY = "capacity"
    SKILLS = "skills"
    INFRASTRUCTURE = "infrastructure"


class RFPStatus(Enum):
    """Status of the RFP document."""

    DRAFT = "draft"
    IN_DELIBERATION = "in_deliberation"
    BLOCKED = (
        "blocked"  # Cannot finalize - missing contributions or unresolved failures
    )
    FINAL = "final"
    ISSUED = "issued"
    CLOSED = "closed"


class ContributionStatus(Enum):
    """Status of a portfolio's contribution."""

    CONTRIBUTED = "contributed"  # Valid contribution received
    NO_ACTION = "no_action"  # Portfolio explicitly has nothing to contribute
    FAILED = "failed"  # LLM/parse failure - blocks finalization
    PENDING = "pending"  # Not yet received


@dataclass
class FunctionalRequirement:
    """A functional requirement - what the solution must DO."""

    req_id: str
    description: str
    priority: RequirementPriority
    source_portfolio_id: str
    acceptance_criteria: list[str] = field(default_factory=list)
    rationale: str = ""
    dependencies: list[str] = field(default_factory=list)  # Legacy req_id dependencies
    independence_requirements: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "req_id": self.req_id,
            "description": self.description,
            "priority": self.priority.value,
            "source_portfolio_id": self.source_portfolio_id,
            "acceptance_criteria": self.acceptance_criteria,
            "rationale": self.rationale,
            "independence_requirements": self.independence_requirements,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FunctionalRequirement:
        independence_requirements = data.get("independence_requirements", [])
        legacy_dependencies = data.get("dependencies", [])
        if not independence_requirements and legacy_dependencies:
            independence_requirements = legacy_dependencies
        return cls(
            req_id=data["req_id"],
            description=data["description"],
            priority=RequirementPriority(data["priority"]),
            source_portfolio_id=data["source_portfolio_id"],
            acceptance_criteria=data.get("acceptance_criteria", []),
            rationale=data.get("rationale", ""),
            dependencies=legacy_dependencies,
            independence_requirements=independence_requirements,
        )


@dataclass
class NonFunctionalRequirement:
    """A non-functional requirement - quality attributes."""

    req_id: str
    category: RequirementCategory
    description: str
    source_portfolio_id: str
    target_metric: str = ""  # e.g., "response time < 200ms"
    threshold: str = ""  # e.g., "99.9% of requests"
    measurement_method: str = ""
    priority: RequirementPriority = RequirementPriority.SHOULD

    def to_dict(self) -> dict[str, Any]:
        return {
            "req_id": self.req_id,
            "category": self.category.value,
            "description": self.description,
            "source_portfolio_id": self.source_portfolio_id,
            "target_metric": self.target_metric,
            "threshold": self.threshold,
            "measurement_method": self.measurement_method,
            "priority": self.priority.value,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> NonFunctionalRequirement:
        return cls(
            req_id=data["req_id"],
            category=RequirementCategory(data["category"]),
            description=data["description"],
            source_portfolio_id=data["source_portfolio_id"],
            target_metric=data.get("target_metric", ""),
            threshold=data.get("threshold", ""),
            measurement_method=data.get("measurement_method", ""),
            priority=RequirementPriority(data.get("priority", "should")),
        )


@dataclass
class Constraint:
    """A constraint on the solution."""

    constraint_id: str
    constraint_type: ConstraintType
    description: str
    source_portfolio_id: str
    rationale: str = ""
    negotiable: bool = False
    # For resource constraints
    resource_type: ResourceType | None = None
    limit_value: str = ""  # e.g., "$50,000", "3 months", "2 FTE"

    def to_dict(self) -> dict[str, Any]:
        result = {
            "constraint_id": self.constraint_id,
            "constraint_type": self.constraint_type.value,
            "description": self.description,
            "source_portfolio_id": self.source_portfolio_id,
            "rationale": self.rationale,
            "negotiable": self.negotiable,
        }
        if self.resource_type:
            result["resource_type"] = self.resource_type.value
            result["limit_value"] = self.limit_value
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Constraint:
        resource_type = None
        if data.get("resource_type"):
            resource_type = ResourceType(data["resource_type"])
        return cls(
            constraint_id=data["constraint_id"],
            constraint_type=ConstraintType(data["constraint_type"]),
            description=data["description"],
            source_portfolio_id=data["source_portfolio_id"],
            rationale=data.get("rationale", ""),
            negotiable=data.get("negotiable", False),
            resource_type=resource_type,
            limit_value=data.get("limit_value", ""),
        )


@dataclass
class EvaluationCriterion:
    """A criterion for evaluating proposals."""

    criterion_id: str
    name: str
    description: str
    scoring_method: str  # How to score (e.g., "1-5 scale", "pass/fail", "percentage")
    minimum_threshold: str = ""  # Minimum acceptable score
    priority_band: str = "medium"  # high|medium|low (output-facing)

    def to_dict(self) -> dict[str, Any]:
        return {
            "criterion_id": self.criterion_id,
            "name": self.name,
            "description": self.description,
            "priority_band": self.priority_band,
            "scoring_method": self.scoring_method,
            "minimum_threshold": self.minimum_threshold,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EvaluationCriterion:
        return cls(
            criterion_id=data["criterion_id"],
            name=data["name"],
            description=data["description"],
            scoring_method=data.get("scoring_method", "1-5 scale"),
            minimum_threshold=data.get("minimum_threshold", ""),
            priority_band=data.get("priority_band", "medium"),
        )


@dataclass
class Deliverable:
    """A required deliverable from the solution."""

    deliverable_id: str
    name: str
    description: str
    acceptance_criteria: list[str] = field(default_factory=list)
    verification_method: str = ""  # How to verify delivery
    dependencies: list[str] = field(default_factory=list)  # Other deliverable_ids

    def to_dict(self) -> dict[str, Any]:
        return {
            "deliverable_id": self.deliverable_id,
            "name": self.name,
            "description": self.description,
            "acceptance_criteria": self.acceptance_criteria,
            "verification_method": self.verification_method,
            "dependencies": self.dependencies,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Deliverable:
        return cls(
            deliverable_id=data["deliverable_id"],
            name=data["name"],
            description=data["description"],
            acceptance_criteria=data.get("acceptance_criteria", []),
            verification_method=data.get("verification_method", ""),
            dependencies=data.get("dependencies", []),
        )


@dataclass
class PortfolioContribution:
    """A President's contribution to the RFP.

    Includes full traceability back to the contributing Archon via president_id (UUID).
    """

    portfolio_id: str
    president_name: str
    contribution_summary: str
    president_id: str = ""  # UUID for full traceability
    portfolio_label: str = ""
    status: ContributionStatus = ContributionStatus.CONTRIBUTED
    functional_requirements: list[FunctionalRequirement] = field(default_factory=list)
    non_functional_requirements: list[NonFunctionalRequirement] = field(
        default_factory=list
    )
    constraints: list[Constraint] = field(default_factory=list)
    deliverables: list[Deliverable] = field(default_factory=list)
    evaluation_criteria: list[EvaluationCriterion] = field(default_factory=list)
    risks_identified: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    deliberation_notes: str = ""
    failure_reason: str = ""  # If status=FAILED, why
    # Trace metadata for debugging and audit
    llm_model: str = ""
    llm_provider: str = ""
    generated_at: str = ""

    def is_blocking_failure(self) -> bool:
        """Return True if this contribution represents a failure that blocks finalization."""
        return self.status == ContributionStatus.FAILED

    def is_no_action(self) -> bool:
        """Return True if this is a valid 'no action required' response."""
        if self.status == ContributionStatus.NO_ACTION:
            return True
        # Also detect via summary text
        no_action_phrases = [
            "no action required",
            "nothing to contribute",
            "not applicable",
            "no requirements",
        ]
        summary_lower = self.contribution_summary.lower()
        return any(phrase in summary_lower for phrase in no_action_phrases)

    def to_dict(self) -> dict[str, Any]:
        return {
            "portfolio": {
                "portfolio_id": self.portfolio_id,
                "president_id": self.president_id,
                "president_name": self.president_name,
                "portfolio_label": self.portfolio_label,
            },
            "status": self.status.value,
            "contribution_summary": self.contribution_summary,
            "failure_reason": self.failure_reason,
            "functional_requirements": [
                r.to_dict() for r in self.functional_requirements
            ],
            "non_functional_requirements": [
                r.to_dict() for r in self.non_functional_requirements
            ],
            "constraints": [c.to_dict() for c in self.constraints],
            "deliverables": [d.to_dict() for d in self.deliverables],
            "evaluation_criteria": [e.to_dict() for e in self.evaluation_criteria],
            "risks_identified": self.risks_identified,
            "assumptions": self.assumptions,
            "deliberation_notes": self.deliberation_notes,
            "trace": {
                "llm_model": self.llm_model,
                "llm_provider": self.llm_provider,
                "generated_at": self.generated_at,
            },
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PortfolioContribution:
        # Handle both old flat format and new nested portfolio format
        if "portfolio" in data:
            portfolio = data["portfolio"]
            portfolio_id = portfolio.get("portfolio_id", "")
            president_id = portfolio.get("president_id", "")
            president_name = portfolio.get("president_name", "")
            portfolio_label = portfolio.get("portfolio_label", "")
        else:
            # Legacy format
            portfolio_id = data.get("portfolio_id", "")
            president_id = data.get("president_id", "")
            president_name = data.get("president_name", "")
            portfolio_label = data.get("portfolio_label", "")

        trace = data.get("trace", {})

        # Parse status
        status_str = data.get("status", "contributed")
        try:
            status = ContributionStatus(status_str)
        except ValueError:
            status = ContributionStatus.CONTRIBUTED

        return cls(
            portfolio_id=portfolio_id,
            president_id=president_id,
            president_name=president_name,
            portfolio_label=portfolio_label,
            status=status,
            contribution_summary=data.get("contribution_summary", ""),
            failure_reason=data.get("failure_reason", ""),
            functional_requirements=[
                FunctionalRequirement.from_dict(r)
                for r in data.get("functional_requirements", [])
            ],
            non_functional_requirements=[
                NonFunctionalRequirement.from_dict(r)
                for r in data.get("non_functional_requirements", [])
            ],
            constraints=[Constraint.from_dict(c) for c in data.get("constraints", [])],
            deliverables=[
                Deliverable.from_dict(d) for d in data.get("deliverables", [])
            ],
            evaluation_criteria=[
                EvaluationCriterion.from_dict(e)
                for e in data.get("evaluation_criteria", [])
            ],
            risks_identified=data.get("risks_identified", []),
            assumptions=data.get("assumptions", []),
            deliberation_notes=data.get("deliberation_notes", ""),
            llm_model=trace.get("llm_model", ""),
            llm_provider=trace.get("llm_provider", ""),
            generated_at=trace.get("generated_at", ""),
        )


@dataclass
class UnresolvedConflict:
    """A conflict between portfolio contributions that needs resolution."""

    conflict_id: str
    description: str
    conflicting_portfolios: list[str]
    conflicting_items: list[str]  # req_ids or constraint_ids
    proposed_resolution: str = ""
    escalate_to_conclave: bool = False
    resolution_notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "conflict_id": self.conflict_id,
            "description": self.description,
            "conflicting_portfolios": self.conflicting_portfolios,
            "conflicting_items": self.conflicting_items,
            "proposed_resolution": self.proposed_resolution,
            "escalate_to_conclave": self.escalate_to_conclave,
            "resolution_notes": self.resolution_notes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> UnresolvedConflict:
        return cls(
            conflict_id=data["conflict_id"],
            description=data["description"],
            conflicting_portfolios=data["conflicting_portfolios"],
            conflicting_items=data["conflicting_items"],
            proposed_resolution=data.get("proposed_resolution", ""),
            escalate_to_conclave=data.get("escalate_to_conclave", False),
            resolution_notes=data.get("resolution_notes", ""),
        )


@dataclass
class RFPDocument:
    """The complete Executive Implementation Dossier document.

    This is the output of the Executive branch, translating a Legislative
    mandate into detailed requirements for the Administrative branch.
    """

    implementation_dossier_id: str
    mandate_id: str
    status: RFPStatus
    created_at: str
    schema_version: str = "1.0"

    # Background from the mandate
    motion_title: str = ""
    motion_text: str = ""
    business_justification: str = ""
    strategic_alignment: list[str] = field(default_factory=list)

    # Scope of Work
    objectives: list[str] = field(default_factory=list)
    in_scope: list[str] = field(default_factory=list)
    out_of_scope: list[str] = field(default_factory=list)
    success_criteria: list[str] = field(default_factory=list)

    # Requirements (merged from all portfolio contributions)
    functional_requirements: list[FunctionalRequirement] = field(default_factory=list)
    non_functional_requirements: list[NonFunctionalRequirement] = field(
        default_factory=list
    )

    # Constraints (merged from all portfolio contributions)
    constraints: list[Constraint] = field(default_factory=list)

    # Evaluation criteria (merged)
    evaluation_criteria: list[EvaluationCriterion] = field(default_factory=list)

    # Deliverables (merged)
    deliverables: list[Deliverable] = field(default_factory=list)

    # Terms and governance
    governance_requirements: list[str] = field(default_factory=list)
    reporting_expectations: list[str] = field(default_factory=list)
    escalation_paths: list[str] = field(default_factory=list)
    change_management_process: str = ""

    # Contribution tracking
    portfolio_contributions: list[PortfolioContribution] = field(default_factory=list)

    # Unresolved issues
    unresolved_conflicts: list[UnresolvedConflict] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)

    # Metadata
    deliberation_rounds: int = 0
    finalized_at: str | None = None
    executive_scope_disclaimer: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        mandate_id: str,
        motion_title: str,
        motion_text: str,
    ) -> RFPDocument:
        """Create a new RFP document from a mandate."""
        return cls(
            implementation_dossier_id=f"eid-{uuid4()}",
            mandate_id=mandate_id,
            status=RFPStatus.DRAFT,
            created_at=datetime.now(timezone.utc).isoformat(),
            motion_title=motion_title,
            motion_text=motion_text,
            executive_scope_disclaimer={
                "statement": (
                    "This dossier articulates required capabilities and constraints "
                    "derived from the ratified motion. It does not prescribe "
                    "implementation mechanisms, select proposals, authorize execution, "
                    "or expand authority."
                ),
                "acknowledged_at": datetime.now(timezone.utc).isoformat(),
            },
        )

    def add_contribution(self, contribution: PortfolioContribution) -> None:
        """Add a portfolio contribution to the RFP."""
        self.portfolio_contributions.append(contribution)
        # Merge requirements, constraints, etc. into main lists
        self.functional_requirements.extend(contribution.functional_requirements)
        self.non_functional_requirements.extend(
            contribution.non_functional_requirements
        )
        self.constraints.extend(contribution.constraints)
        self.deliverables.extend(contribution.deliverables)
        self.evaluation_criteria.extend(contribution.evaluation_criteria)

    def check_completeness(
        self, expected_portfolios: list[str] | None = None
    ) -> tuple[bool, list[str]]:
        """Check if the RFP has complete contributions from all expected portfolios.

        Args:
            expected_portfolios: List of expected portfolio_ids (if None, uses contributions)

        Returns:
            Tuple of (is_complete, list_of_blocking_issues)
        """
        issues: list[str] = []

        # Check for blocking failures
        for contrib in self.portfolio_contributions:
            if contrib.is_blocking_failure():
                issues.append(
                    f"FAILED: {contrib.president_name} ({contrib.portfolio_id}) - {contrib.failure_reason or 'Unknown error'}"
                )

        # Check for missing portfolios if expected list provided
        if expected_portfolios:
            contributed_ids = {c.portfolio_id for c in self.portfolio_contributions}
            missing = set(expected_portfolios) - contributed_ids
            for pid in missing:
                issues.append(f"MISSING: No contribution from {pid}")

        return len(issues) == 0, issues

    def finalize(
        self,
        force: bool = False,
        expected_portfolios: list[str] | None = None,
    ) -> bool:
        """Mark the RFP as final if completeness checks pass.

        Args:
            force: If True, finalize even with blocking failures (marks as BLOCKED instead)
            expected_portfolios: List of expected portfolio_ids for completeness check

        Returns:
            True if finalized successfully, False if blocked
        """
        is_complete, issues = self.check_completeness(expected_portfolios)

        if not is_complete and not force:
            self.status = RFPStatus.BLOCKED
            self.open_questions.extend(issues)
            return False

        if not is_complete and force:
            # Force finalization but record the issues
            self.status = RFPStatus.BLOCKED
            self.open_questions.extend([f"[FORCED] {issue}" for issue in issues])
            self.finalized_at = datetime.now(timezone.utc).isoformat()
            return False

        self.status = RFPStatus.FINAL
        self.finalized_at = datetime.now(timezone.utc).isoformat()
        return True

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "artifact_type": "executive_implementation_dossier",
            "implementation_dossier_id": self.implementation_dossier_id,
            "mandate_id": self.mandate_id,
            "status": self.status.value,
            "created_at": self.created_at,
            "finalized_at": self.finalized_at,
            "executive_scope_disclaimer": self.executive_scope_disclaimer,
            "background": {
                "motion_title": self.motion_title,
                "motion_text": self.motion_text,
                "business_justification": self.business_justification,
                "strategic_alignment": self.strategic_alignment,
            },
            "scope_of_work": {
                "objectives": self.objectives,
                "in_scope": self.in_scope,
                "out_of_scope": self.out_of_scope,
                "success_criteria": self.success_criteria,
            },
            "requirements": {
                "functional": [r.to_dict() for r in self.functional_requirements],
                "non_functional": [
                    r.to_dict() for r in self.non_functional_requirements
                ],
            },
            "constraints": [c.to_dict() for c in self.constraints],
            "evaluation_criteria": [e.to_dict() for e in self.evaluation_criteria],
            "deliverables": [d.to_dict() for d in self.deliverables],
            "terms": {
                "governance_requirements": self.governance_requirements,
                "reporting_expectations": self.reporting_expectations,
                "escalation_paths": self.escalation_paths,
                "change_management_process": self.change_management_process,
            },
            "portfolio_contributions": [
                c.to_dict() for c in self.portfolio_contributions
            ],
            "unresolved_conflicts": [c.to_dict() for c in self.unresolved_conflicts],
            "open_questions": self.open_questions,
            "deliberation_rounds": self.deliberation_rounds,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RFPDocument:
        background = data.get("background", {})
        scope = data.get("scope_of_work", {})
        requirements = data.get("requirements", {})
        terms = data.get("terms", {})
        disclaimer = data.get("executive_scope_disclaimer", {})

        return cls(
            schema_version=data.get("schema_version", "1.0"),
            implementation_dossier_id=data.get("implementation_dossier_id")
            or data.get("rfp_id", ""),
            mandate_id=data["mandate_id"],
            status=RFPStatus(data["status"]),
            created_at=data["created_at"],
            finalized_at=data.get("finalized_at"),
            executive_scope_disclaimer=disclaimer,
            motion_title=background.get("motion_title", ""),
            motion_text=background.get("motion_text", ""),
            business_justification=background.get("business_justification", ""),
            strategic_alignment=background.get("strategic_alignment", []),
            objectives=scope.get("objectives", []),
            in_scope=scope.get("in_scope", []),
            out_of_scope=scope.get("out_of_scope", []),
            success_criteria=scope.get("success_criteria", []),
            functional_requirements=[
                FunctionalRequirement.from_dict(r)
                for r in requirements.get("functional", [])
            ],
            non_functional_requirements=[
                NonFunctionalRequirement.from_dict(r)
                for r in requirements.get("non_functional", [])
            ],
            constraints=[Constraint.from_dict(c) for c in data.get("constraints", [])],
            evaluation_criteria=[
                EvaluationCriterion.from_dict(e)
                for e in data.get("evaluation_criteria", [])
            ],
            deliverables=[
                Deliverable.from_dict(d) for d in data.get("deliverables", [])
            ],
            governance_requirements=terms.get("governance_requirements", []),
            reporting_expectations=terms.get("reporting_expectations", []),
            escalation_paths=terms.get("escalation_paths", []),
            change_management_process=terms.get("change_management_process", ""),
            portfolio_contributions=[
                PortfolioContribution.from_dict(c)
                for c in data.get("portfolio_contributions", [])
            ],
            unresolved_conflicts=[
                UnresolvedConflict.from_dict(c)
                for c in data.get("unresolved_conflicts", [])
            ],
            open_questions=data.get("open_questions", []),
            deliberation_rounds=data.get("deliberation_rounds", 0),
        )
