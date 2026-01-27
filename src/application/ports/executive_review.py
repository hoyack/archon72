"""Port definition for Executive Review (E4) operations.

This port defines the interface for reviewing implementation proposals
from Administration and determining the appropriate response:
- Accept and proceed to Earl tasking
- Request revisions from Administration
- Escalate to Conclave for governance-level decisions

Two Feedback Loops:
1. Implementation Loop (frequent): Executive -> Administrative -> Executive
2. Intent Loop (rare): Executive -> Conclave (only for INTENT_AMBIGUITY)

Constitutional Compliance:
- CT-11: All review operations must be logged
- CT-12: All decisions must be traceable to source proposals
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from src.domain.models.administrative_pipeline import (
    AggregatedResourceSummary,
    ImplementationProposal,
)
from src.domain.models.executive_review import (
    ConclaveEscalation,
    ExecutiveReviewResult,
    PlanAcceptance,
    ReviewOutcome,
    RevisionRequest,
)


@dataclass
class ReviewContext:
    """Context for Executive Review operations."""

    cycle_id: str
    motion_id: str
    motion_title: str
    motion_text: str
    execution_plan_path: str = ""
    iteration_number: int = 1
    max_iterations: int = 3
    portfolio_labels: dict[str, str] = field(default_factory=dict)
    constraints: list[str] = field(default_factory=list)
    # Additional context
    ratified_motion: dict[str, Any] = field(default_factory=dict)
    resource_summary: AggregatedResourceSummary | None = None


@dataclass
class SingleReviewResult:
    """Result of reviewing a single proposal."""

    proposal_id: str
    epic_id: str
    outcome: ReviewOutcome
    acceptance: PlanAcceptance | None = None
    revision_request: RevisionRequest | None = None
    escalation: ConclaveEscalation | None = None
    review_duration_ms: int = 0
    review_notes: str = ""
    trace_metadata: Any | None = None


class ExecutiveReviewProtocol(ABC):
    """Port for Executive Review (E4) operations.

    This protocol defines the interface for LLM-powered or simulated
    review of implementation proposals. Implementations handle the actual
    CrewAI or LLM invocation details.

    The Executive Review evaluates proposals from Administration and
    determines whether to proceed, iterate, or escalate.
    """

    @abstractmethod
    async def review_proposal(
        self,
        proposal: ImplementationProposal,
        context: ReviewContext,
    ) -> SingleReviewResult:
        """Review a single implementation proposal.

        Evaluates the proposal against Executive expectations and
        returns one of:
        - ACCEPTED: Proceed to Earl tasking
        - REVISION_REQUESTED: Back to Administration
        - ESCALATE_TO_CONCLAVE: Governance-level issue

        Args:
            proposal: The implementation proposal to review
            context: Review context with motion and iteration info

        Returns:
            SingleReviewResult with outcome and details

        Raises:
            ReviewError: If review fails
        """
        ...

    @abstractmethod
    async def batch_review_proposals(
        self,
        proposals: list[ImplementationProposal],
        context: ReviewContext,
    ) -> ExecutiveReviewResult:
        """Review multiple implementation proposals.

        Batch processing for reviewing all proposals in a cycle.

        Args:
            proposals: List of proposals to review
            context: Review context with motion and iteration info

        Returns:
            ExecutiveReviewResult with all outcomes

        Raises:
            ReviewError: If any review fails
        """
        ...

    @abstractmethod
    async def evaluate_resource_requests(
        self,
        resource_summary: AggregatedResourceSummary,
        context: ReviewContext,
    ) -> dict[str, bool]:
        """Evaluate aggregated resource requests.

        Reviews the total resource impact across all proposals
        and identifies which requests should be approved.

        Args:
            resource_summary: Aggregated resource requests
            context: Review context

        Returns:
            Dict mapping request_id to approval status

        Raises:
            ReviewError: If evaluation fails
        """
        ...

    @abstractmethod
    async def check_escalation_needed(
        self,
        proposals: list[ImplementationProposal],
        context: ReviewContext,
    ) -> list[ConclaveEscalation]:
        """Check if any proposals require Conclave escalation.

        Identifies governance-level issues that cannot be resolved
        at Executive level. This should be rare.

        Args:
            proposals: Proposals to check
            context: Review context

        Returns:
            List of escalations needed (empty if none)

        Raises:
            ReviewError: If check fails
        """
        ...

    @abstractmethod
    async def generate_revision_guidance(
        self,
        proposal: ImplementationProposal,
        concerns: list[str],
        context: ReviewContext,
    ) -> RevisionRequest:
        """Generate detailed revision guidance for Administration.

        Creates a structured revision request with specific
        guidance for improving the proposal.

        Args:
            proposal: The proposal needing revision
            concerns: Identified concerns
            context: Review context

        Returns:
            RevisionRequest with detailed guidance

        Raises:
            ReviewError: If guidance generation fails
        """
        ...


# -----------------------------------------------------------------------------
# Exceptions
# -----------------------------------------------------------------------------


class ExecutiveReviewError(Exception):
    """Base exception for Executive Review operations."""

    pass


class ReviewError(ExecutiveReviewError):
    """Error during proposal review."""

    pass


class EscalationCheckError(ExecutiveReviewError):
    """Error during escalation check."""

    pass


class GuidanceGenerationError(ExecutiveReviewError):
    """Error during revision guidance generation."""

    pass
