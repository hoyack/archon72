"""Domain models for Executive Review (E4).

The Executive Review stage evaluates implementation proposals from Administration
and determines whether to:
- Accept the plan and proceed to Earl tasking
- Request revisions from Administration
- Escalate to Conclave for governance-level decisions

This completes the feedback loop:
- Implementation Loop (frequent): Executive -> Administrative -> Executive
- Intent Loop (rare): Executive -> Conclave (only for INTENT_AMBIGUITY)

Schema Versions:
- 2.0: Initial version aligned with Administrative Pipeline v2
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

# Schema version for Executive Review artifacts
REVIEW_SCHEMA_VERSION = "2.0"


class ReviewOutcome(str, Enum):
    """Outcome of Executive Review for a proposal."""

    ACCEPTED = "ACCEPTED"  # Proceed to Earl tasking
    REVISION_REQUESTED = "REVISION_REQUESTED"  # Back to Administration
    ESCALATE_TO_CONCLAVE = "ESCALATE_TO_CONCLAVE"  # Governance-level issue


class RevisionType(str, Enum):
    """Classification of revision request types."""

    CAPACITY_REBALANCE = "CAPACITY_REBALANCE"  # Adjust capacity commitments
    RISK_MITIGATION = "RISK_MITIGATION"  # Strengthen risk handling
    TACTICAL_CHANGE = "TACTICAL_CHANGE"  # Different tactical approach
    RESOURCE_CONSTRAINT = "RESOURCE_CONSTRAINT"  # Reduce resource requests
    SCOPE_CLARIFICATION = "SCOPE_CLARIFICATION"  # Clarify scope boundaries
    DEPENDENCY_RESOLUTION = "DEPENDENCY_RESOLUTION"  # Resolve dependencies
    TIMELINE_ADJUSTMENT = "TIMELINE_ADJUSTMENT"  # Adjust timeline


class EscalationUrgency(str, Enum):
    """Urgency level for Conclave escalations."""

    LOW = "LOW"  # Can wait for next scheduled session
    MEDIUM = "MEDIUM"  # Should be addressed soon
    HIGH = "HIGH"  # Requires prompt attention
    CRITICAL = "CRITICAL"  # Blocks all progress


# -----------------------------------------------------------------------------
# Plan Acceptance Model
# -----------------------------------------------------------------------------


@dataclass
class PlanAcceptance:
    """Approval to proceed to Earl tasking.

    Emitted when Executive Review accepts an implementation proposal,
    authorizing the Earl to begin work coordination.
    """

    acceptance_id: str
    epic_id: str
    proposal_id: str
    cycle_id: str
    motion_id: str
    accepted_at: str  # ISO8601 timestamp
    approved_tactics: list[str] = field(default_factory=list)  # tactic_ids
    approved_resources: list[str] = field(default_factory=list)  # request_ids
    acceptance_conditions: list[str] = field(default_factory=list)
    monitoring_requirements: list[str] = field(default_factory=list)
    proceed_to_earl_tasking: bool = True
    reviewer_portfolio_id: str = ""
    review_notes: str = ""
    schema_version: str = REVIEW_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "acceptance_id": self.acceptance_id,
            "epic_id": self.epic_id,
            "proposal_id": self.proposal_id,
            "cycle_id": self.cycle_id,
            "motion_id": self.motion_id,
            "accepted_at": self.accepted_at,
            "approved_tactics": self.approved_tactics,
            "approved_resources": self.approved_resources,
            "acceptance_conditions": self.acceptance_conditions,
            "monitoring_requirements": self.monitoring_requirements,
            "proceed_to_earl_tasking": self.proceed_to_earl_tasking,
            "reviewer_portfolio_id": self.reviewer_portfolio_id,
            "review_notes": self.review_notes,
        }

    def validate(self) -> list[str]:
        """Validate plan acceptance completeness."""
        errors: list[str] = []

        if not self.acceptance_id:
            errors.append("PlanAcceptance missing required field: acceptance_id")
        if not self.epic_id:
            errors.append("PlanAcceptance missing required field: epic_id")
        if not self.proposal_id:
            errors.append("PlanAcceptance missing required field: proposal_id")
        if not self.accepted_at:
            errors.append("PlanAcceptance missing required field: accepted_at")

        # Should have at least one approved tactic
        if not self.approved_tactics:
            errors.append(
                f"Acceptance {self.acceptance_id}: should approve at least one tactic"
            )

        return errors

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PlanAcceptance:
        """Create PlanAcceptance from dictionary representation."""
        return cls(
            acceptance_id=data["acceptance_id"],
            epic_id=data["epic_id"],
            proposal_id=data["proposal_id"],
            cycle_id=data.get("cycle_id", ""),
            motion_id=data.get("motion_id", ""),
            accepted_at=data["accepted_at"],
            approved_tactics=data.get("approved_tactics", []),
            approved_resources=data.get("approved_resources", []),
            acceptance_conditions=data.get("acceptance_conditions", []),
            monitoring_requirements=data.get("monitoring_requirements", []),
            proceed_to_earl_tasking=data.get("proceed_to_earl_tasking", True),
            reviewer_portfolio_id=data.get("reviewer_portfolio_id", ""),
            review_notes=data.get("review_notes", ""),
            schema_version=data.get("schema_version", REVIEW_SCHEMA_VERSION),
        )


# -----------------------------------------------------------------------------
# Revision Request Model
# -----------------------------------------------------------------------------


@dataclass
class RevisionRequest:
    """Request sent back to Administration for revisions.

    Specifies what needs to change and provides constraints for
    the revised proposal.
    """

    request_id: str
    epic_id: str
    proposal_id: str
    cycle_id: str
    motion_id: str
    revision_type: RevisionType
    revision_reason: str
    specific_concerns: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    questions: list[str] = field(default_factory=list)
    response_deadline: str = ""  # ISO8601 timestamp
    rejected_tactics: list[str] = field(default_factory=list)  # tactic_ids
    rejected_resources: list[str] = field(default_factory=list)  # request_ids
    suggested_alternatives: list[str] = field(default_factory=list)
    reviewer_portfolio_id: str = ""
    iteration_count: int = 1
    schema_version: str = REVIEW_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "request_id": self.request_id,
            "epic_id": self.epic_id,
            "proposal_id": self.proposal_id,
            "cycle_id": self.cycle_id,
            "motion_id": self.motion_id,
            "revision_type": self.revision_type.value,
            "revision_reason": self.revision_reason,
            "specific_concerns": self.specific_concerns,
            "constraints": self.constraints,
            "questions": self.questions,
            "response_deadline": self.response_deadline,
            "rejected_tactics": self.rejected_tactics,
            "rejected_resources": self.rejected_resources,
            "suggested_alternatives": self.suggested_alternatives,
            "reviewer_portfolio_id": self.reviewer_portfolio_id,
            "iteration_count": self.iteration_count,
        }

    def validate(self) -> list[str]:
        """Validate revision request completeness."""
        errors: list[str] = []

        if not self.request_id:
            errors.append("RevisionRequest missing required field: request_id")
        if not self.epic_id:
            errors.append("RevisionRequest missing required field: epic_id")
        if not self.proposal_id:
            errors.append("RevisionRequest missing required field: proposal_id")
        if not self.revision_reason:
            errors.append("RevisionRequest missing required field: revision_reason")

        # Should have specific concerns or questions
        if not self.specific_concerns and not self.questions:
            errors.append(
                f"Revision {self.request_id}: must specify concerns or questions"
            )

        return errors

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RevisionRequest:
        """Create RevisionRequest from dictionary representation."""
        return cls(
            request_id=data["request_id"],
            epic_id=data["epic_id"],
            proposal_id=data["proposal_id"],
            cycle_id=data.get("cycle_id", ""),
            motion_id=data.get("motion_id", ""),
            revision_type=RevisionType(data["revision_type"]),
            revision_reason=data["revision_reason"],
            specific_concerns=data.get("specific_concerns", []),
            constraints=data.get("constraints", []),
            questions=data.get("questions", []),
            response_deadline=data.get("response_deadline", ""),
            rejected_tactics=data.get("rejected_tactics", []),
            rejected_resources=data.get("rejected_resources", []),
            suggested_alternatives=data.get("suggested_alternatives", []),
            reviewer_portfolio_id=data.get("reviewer_portfolio_id", ""),
            iteration_count=data.get("iteration_count", 1),
            schema_version=data.get("schema_version", REVIEW_SCHEMA_VERSION),
        )


# -----------------------------------------------------------------------------
# Conclave Escalation Model
# -----------------------------------------------------------------------------


@dataclass
class ConclaveEscalation:
    """Escalation to Conclave for governance-level decisions.

    This is rare and should only occur when:
    - Intent ambiguity requires clarification from Conclave
    - Policy questions arise that Administration cannot resolve
    - Cross-portfolio conflicts cannot be resolved at Executive level
    """

    escalation_id: str
    cycle_id: str
    motion_id: str
    escalation_reason: str
    questions_for_conclave: list[str] = field(default_factory=list)
    proposed_options: list[str] = field(default_factory=list)
    source_proposal_ids: list[str] = field(default_factory=list)
    source_blocker_ids: list[str] = field(default_factory=list)
    affected_portfolios: list[str] = field(default_factory=list)
    urgency: EscalationUrgency = EscalationUrgency.MEDIUM
    context_summary: str = ""
    escalated_at: str = ""  # ISO8601 timestamp
    escalated_by_portfolio_id: str = ""
    schema_version: str = REVIEW_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "escalation_id": self.escalation_id,
            "cycle_id": self.cycle_id,
            "motion_id": self.motion_id,
            "escalation_reason": self.escalation_reason,
            "questions_for_conclave": self.questions_for_conclave,
            "proposed_options": self.proposed_options,
            "source_proposal_ids": self.source_proposal_ids,
            "source_blocker_ids": self.source_blocker_ids,
            "affected_portfolios": self.affected_portfolios,
            "urgency": self.urgency.value,
            "context_summary": self.context_summary,
            "escalated_at": self.escalated_at,
            "escalated_by_portfolio_id": self.escalated_by_portfolio_id,
        }

    def validate(self) -> list[str]:
        """Validate conclave escalation completeness."""
        errors: list[str] = []

        if not self.escalation_id:
            errors.append("ConclaveEscalation missing required field: escalation_id")
        if not self.cycle_id:
            errors.append("ConclaveEscalation missing required field: cycle_id")
        if not self.motion_id:
            errors.append("ConclaveEscalation missing required field: motion_id")
        if not self.escalation_reason:
            errors.append(
                "ConclaveEscalation missing required field: escalation_reason"
            )

        # Must have questions for Conclave
        if not self.questions_for_conclave:
            errors.append(
                f"Escalation {self.escalation_id}: must specify questions for Conclave"
            )

        # Should have proposed options
        if not self.proposed_options:
            errors.append(
                f"Escalation {self.escalation_id}: should propose resolution options"
            )

        return errors

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ConclaveEscalation:
        """Create ConclaveEscalation from dictionary representation."""
        return cls(
            escalation_id=data["escalation_id"],
            cycle_id=data["cycle_id"],
            motion_id=data["motion_id"],
            escalation_reason=data["escalation_reason"],
            questions_for_conclave=data.get("questions_for_conclave", []),
            proposed_options=data.get("proposed_options", []),
            source_proposal_ids=data.get("source_proposal_ids", []),
            source_blocker_ids=data.get("source_blocker_ids", []),
            affected_portfolios=data.get("affected_portfolios", []),
            urgency=EscalationUrgency(data.get("urgency", "MEDIUM")),
            context_summary=data.get("context_summary", ""),
            escalated_at=data.get("escalated_at", ""),
            escalated_by_portfolio_id=data.get("escalated_by_portfolio_id", ""),
            schema_version=data.get("schema_version", REVIEW_SCHEMA_VERSION),
        )


# -----------------------------------------------------------------------------
# Executive Review Result (aggregate)
# -----------------------------------------------------------------------------


@dataclass
class ProposalReviewResult:
    """Review result for a single proposal."""

    proposal_id: str
    epic_id: str
    outcome: ReviewOutcome
    acceptance: PlanAcceptance | None = None
    revision_request: RevisionRequest | None = None
    review_duration_ms: int = 0

    def to_dict(self) -> dict[str, Any]:
        result = {
            "proposal_id": self.proposal_id,
            "epic_id": self.epic_id,
            "outcome": self.outcome.value,
            "review_duration_ms": self.review_duration_ms,
        }
        if self.acceptance:
            result["acceptance"] = self.acceptance.to_dict()
        if self.revision_request:
            result["revision_request"] = self.revision_request.to_dict()
        return result


@dataclass
class ExecutiveReviewResult:
    """Aggregate result of E4 Executive Review.

    Contains the review outcomes for all proposals in a cycle,
    along with any Conclave escalations needed.
    """

    review_id: str
    cycle_id: str
    motion_id: str
    reviewed_at: str  # ISO8601 timestamp
    proposal_results: list[ProposalReviewResult] = field(default_factory=list)
    escalations: list[ConclaveEscalation] = field(default_factory=list)
    total_proposals: int = 0
    accepted_count: int = 0
    revision_count: int = 0
    escalation_count: int = 0
    iteration_number: int = 1
    max_iterations_reached: bool = False
    review_notes: str = ""
    resource_summary: dict[str, Any] = field(default_factory=dict)
    schema_version: str = REVIEW_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "review_id": self.review_id,
            "cycle_id": self.cycle_id,
            "motion_id": self.motion_id,
            "reviewed_at": self.reviewed_at,
            "proposal_results": [pr.to_dict() for pr in self.proposal_results],
            "escalations": [e.to_dict() for e in self.escalations],
            "total_proposals": self.total_proposals,
            "accepted_count": self.accepted_count,
            "revision_count": self.revision_count,
            "escalation_count": self.escalation_count,
            "iteration_number": self.iteration_number,
            "max_iterations_reached": self.max_iterations_reached,
            "review_notes": self.review_notes,
            "resource_summary": self.resource_summary,
        }

    def validate(self) -> list[str]:
        """Validate executive review result completeness."""
        errors: list[str] = []

        if not self.review_id:
            errors.append("ExecutiveReviewResult missing required field: review_id")
        if not self.cycle_id:
            errors.append("ExecutiveReviewResult missing required field: cycle_id")
        if not self.motion_id:
            errors.append("ExecutiveReviewResult missing required field: motion_id")
        if not self.reviewed_at:
            errors.append("ExecutiveReviewResult missing required field: reviewed_at")

        # Validate counts match
        expected_accepted = sum(
            1 for pr in self.proposal_results if pr.outcome == ReviewOutcome.ACCEPTED
        )
        expected_revision = sum(
            1
            for pr in self.proposal_results
            if pr.outcome == ReviewOutcome.REVISION_REQUESTED
        )

        if self.accepted_count != expected_accepted:
            errors.append(
                f"Review {self.review_id}: accepted_count mismatch "
                f"(got {self.accepted_count}, expected {expected_accepted})"
            )
        if self.revision_count != expected_revision:
            errors.append(
                f"Review {self.review_id}: revision_count mismatch "
                f"(got {self.revision_count}, expected {expected_revision})"
            )

        # Validate individual components
        for pr in self.proposal_results:
            if pr.outcome == ReviewOutcome.ACCEPTED and pr.acceptance:
                errors.extend(pr.acceptance.validate())
            elif pr.outcome == ReviewOutcome.REVISION_REQUESTED and pr.revision_request:
                errors.extend(pr.revision_request.validate())

        for e in self.escalations:
            errors.extend(e.validate())

        return errors

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExecutiveReviewResult:
        """Create ExecutiveReviewResult from dictionary representation."""
        proposal_results: list[ProposalReviewResult] = []
        for pr_data in data.get("proposal_results", []):
            acceptance = None
            revision_request = None
            if pr_data.get("acceptance"):
                acceptance = PlanAcceptance.from_dict(pr_data["acceptance"])
            if pr_data.get("revision_request"):
                revision_request = RevisionRequest.from_dict(
                    pr_data["revision_request"]
                )

            proposal_results.append(
                ProposalReviewResult(
                    proposal_id=pr_data["proposal_id"],
                    epic_id=pr_data["epic_id"],
                    outcome=ReviewOutcome(pr_data["outcome"]),
                    acceptance=acceptance,
                    revision_request=revision_request,
                    review_duration_ms=pr_data.get("review_duration_ms", 0),
                )
            )

        escalations = [
            ConclaveEscalation.from_dict(e) for e in data.get("escalations", [])
        ]

        return cls(
            review_id=data["review_id"],
            cycle_id=data["cycle_id"],
            motion_id=data["motion_id"],
            reviewed_at=data["reviewed_at"],
            proposal_results=proposal_results,
            escalations=escalations,
            total_proposals=data.get("total_proposals", len(proposal_results)),
            accepted_count=data.get("accepted_count", 0),
            revision_count=data.get("revision_count", 0),
            escalation_count=data.get("escalation_count", len(escalations)),
            iteration_number=data.get("iteration_number", 1),
            max_iterations_reached=data.get("max_iterations_reached", False),
            review_notes=data.get("review_notes", ""),
            resource_summary=data.get("resource_summary", {}),
            schema_version=data.get("schema_version", REVIEW_SCHEMA_VERSION),
        )

    def all_accepted(self) -> bool:
        """Check if all proposals were accepted."""
        return all(pr.outcome == ReviewOutcome.ACCEPTED for pr in self.proposal_results)

    def needs_iteration(self) -> bool:
        """Check if revision iteration is needed."""
        return any(
            pr.outcome == ReviewOutcome.REVISION_REQUESTED
            for pr in self.proposal_results
        )

    def get_accepted_proposals(self) -> list[str]:
        """Get list of accepted proposal IDs."""
        return [
            pr.proposal_id
            for pr in self.proposal_results
            if pr.outcome == ReviewOutcome.ACCEPTED
        ]

    def get_revision_requests(self) -> list[RevisionRequest]:
        """Get all revision requests for iteration."""
        return [
            pr.revision_request
            for pr in self.proposal_results
            if pr.revision_request is not None
        ]


# -----------------------------------------------------------------------------
# Handback Structures for Iteration
# -----------------------------------------------------------------------------


@dataclass
class RevisionHandback:
    """Handback package for Administration to revise proposals.

    Contains all revision requests and constraints for the next iteration.
    """

    handback_id: str
    cycle_id: str
    motion_id: str
    iteration_number: int
    revision_requests: list[RevisionRequest] = field(default_factory=list)
    global_constraints: list[str] = field(default_factory=list)
    response_deadline: str = ""
    created_at: str = ""
    schema_version: str = REVIEW_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "handback_id": self.handback_id,
            "cycle_id": self.cycle_id,
            "motion_id": self.motion_id,
            "iteration_number": self.iteration_number,
            "revision_requests": [rr.to_dict() for rr in self.revision_requests],
            "global_constraints": self.global_constraints,
            "response_deadline": self.response_deadline,
            "created_at": self.created_at,
        }

    @classmethod
    def from_review_result(
        cls,
        result: ExecutiveReviewResult,
        handback_id: str,
        response_deadline: str,
        created_at: str,
        global_constraints: list[str] | None = None,
    ) -> RevisionHandback:
        """Create handback from review result."""
        return cls(
            handback_id=handback_id,
            cycle_id=result.cycle_id,
            motion_id=result.motion_id,
            iteration_number=result.iteration_number + 1,
            revision_requests=result.get_revision_requests(),
            global_constraints=global_constraints or [],
            response_deadline=response_deadline,
            created_at=created_at,
        )
