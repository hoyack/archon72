"""Executive Review Service (E4).

Orchestrates the review of implementation proposals from Administration
and determines the appropriate response:
- Accept and proceed to Earl tasking
- Request revisions from Administration
- Escalate to Conclave for governance-level decisions

Two Feedback Loops:
1. Implementation Loop (frequent): Executive -> Administrative -> Executive
2. Intent Loop (rare): Executive -> Conclave (only for INTENT_AMBIGUITY)

Pipeline Flow:
1. Load execution plan and implementation proposals
2. Review each proposal
3. Check for iteration or escalation needs
4. Save results
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from structlog import get_logger

from src.application.ports.executive_review import (
    ExecutiveReviewProtocol,
    ReviewContext,
)
from src.domain.models.administrative_pipeline import (
    AggregatedResourceSummary,
    ImplementationProposal,
)
from src.domain.models.executive_review import (
    ConclaveEscalation,
    EscalationUrgency,
    ExecutiveReviewResult,
    PlanAcceptance,
    ProposalReviewResult,
    ReviewOutcome,
    RevisionHandback,
    RevisionRequest,
    RevisionType,
)

logger = get_logger(__name__)

ISO = "%Y-%m-%dT%H:%M:%SZ"


def now_iso() -> str:
    """UTC timestamp in a stable, sortable format."""
    return datetime.now(timezone.utc).strftime(ISO)


def _load_json(path: Path) -> Any:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _save_json(path: Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2)


class ExecutiveReviewService:
    """Orchestrates Executive Review (E4) operations.

    This service coordinates:
    - Loading execution plans and implementation proposals
    - Reviewing proposals (via LLM or simulation)
    - Checking iteration and escalation needs
    - Saving results for downstream processing
    """

    def __init__(
        self,
        event_sink: Callable[[str, dict[str, Any]], None] | None = None,
        reviewer: ExecutiveReviewProtocol | None = None,
        max_iterations: int = 3,
        verbose: bool = False,
    ) -> None:
        """Initialize the Executive Review Service.

        Args:
            event_sink: Optional callback for event emission
            reviewer: Optional LLM-powered reviewer
            max_iterations: Maximum iterations before forced escalation
            verbose: Enable verbose logging
        """
        self._event_sink = event_sink
        self._reviewer = reviewer
        self._max_iterations = max_iterations
        self._verbose = verbose

        logger.info(
            "executive_review_initialized",
            llm_enabled=reviewer is not None,
            max_iterations=max_iterations,
            verbose=verbose,
        )

    # ------------------------------------------------------------------
    # Input Loading
    # ------------------------------------------------------------------

    def load_execution_plan(
        self,
        executive_output_path: Path,
        motion_id: str,
    ) -> dict[str, Any]:
        """Load execution plan from Executive Pipeline output.

        Args:
            executive_output_path: Path to Executive Pipeline output
            motion_id: The motion ID to load

        Returns:
            Execution plan dictionary
        """
        plan_path = (
            executive_output_path / "motions" / motion_id / "execution_plan.json"
        )

        if not plan_path.exists():
            raise FileNotFoundError(f"Execution plan not found: {plan_path}")

        plan = _load_json(plan_path)

        self._emit(
            "review.execution_plan.loaded",
            {
                "motion_id": motion_id,
                "cycle_id": plan.get("cycle_id"),
                "epic_count": len(plan.get("epics", [])),
                "ts": now_iso(),
            },
        )

        return plan

    def load_implementation_proposals(
        self,
        admin_output_path: Path,
        motion_id: str,
    ) -> list[ImplementationProposal]:
        """Load implementation proposals from Administrative Pipeline output.

        Args:
            admin_output_path: Path to Administrative Pipeline output
            motion_id: The motion ID to load

        Returns:
            List of ImplementationProposal objects
        """
        proposals_dir = admin_output_path / motion_id / "implementation_proposals"

        if not proposals_dir.exists():
            raise FileNotFoundError(f"Proposals directory not found: {proposals_dir}")

        proposals: list[ImplementationProposal] = []
        for proposal_path in proposals_dir.glob("proposal_*.json"):
            proposal_data = _load_json(proposal_path)
            proposal = ImplementationProposal.from_dict(proposal_data)
            proposals.append(proposal)

        self._emit(
            "review.proposals.loaded",
            {
                "motion_id": motion_id,
                "proposal_count": len(proposals),
                "ts": now_iso(),
            },
        )

        logger.info(
            "proposals_loaded",
            motion_id=motion_id,
            count=len(proposals),
        )

        return proposals

    def load_resource_summary(
        self,
        admin_output_path: Path,
        motion_id: str,
    ) -> AggregatedResourceSummary | None:
        """Load aggregated resource summary.

        Args:
            admin_output_path: Path to Administrative Pipeline output
            motion_id: The motion ID

        Returns:
            AggregatedResourceSummary or None if not found
        """
        summary_path = admin_output_path / motion_id / "resource_requests.json"

        if not summary_path.exists():
            return None

        data = _load_json(summary_path)

        # Reconstruct from dict
        return AggregatedResourceSummary(
            cycle_id=data["cycle_id"],
            motion_id=data["motion_id"],
            created_at=data["created_at"],
            total_requests=data["total_requests"],
            requests_by_type=data.get("requests_by_type", {}),
            requests_by_priority=data.get("requests_by_priority", {}),
            requests_by_portfolio=data.get("requests_by_portfolio", {}),
            all_requests=[],  # Don't reconstruct full request objects
            total_estimated_cost=data.get("total_estimated_cost", 0.0),
            cost_currency=data.get("cost_currency", "USD"),
        )

    # ------------------------------------------------------------------
    # Review Execution
    # ------------------------------------------------------------------

    async def run_review(
        self,
        plan: dict[str, Any],
        proposals: list[ImplementationProposal],
        resource_summary: AggregatedResourceSummary | None = None,
        iteration_number: int = 1,
    ) -> ExecutiveReviewResult:
        """Run Executive Review using LLM.

        Args:
            plan: Execution plan dictionary
            proposals: Implementation proposals to review
            resource_summary: Optional aggregated resource summary
            iteration_number: Current iteration number

        Returns:
            ExecutiveReviewResult with all outcomes

        Raises:
            ValueError: If no reviewer is configured
        """
        if not self._reviewer:
            raise ValueError("LLM review requires reviewer to be configured")

        cycle_id = plan.get("cycle_id", "")
        motion_id = plan.get("motion_id", "")

        context = ReviewContext(
            cycle_id=cycle_id,
            motion_id=motion_id,
            motion_title=plan.get("intent_provenance", {})
            .get("ratification_record", {})
            .get("mega_motion_title", ""),
            motion_text="",  # Would need to load from ratified intent
            iteration_number=iteration_number,
            max_iterations=self._max_iterations,
            resource_summary=resource_summary,
        )

        self._emit(
            "review.started",
            {
                "cycle_id": cycle_id,
                "motion_id": motion_id,
                "proposal_count": len(proposals),
                "iteration": iteration_number,
                "ts": now_iso(),
            },
        )

        result = await self._reviewer.batch_review_proposals(
            proposals=proposals,
            context=context,
        )

        self._emit(
            "review.completed",
            {
                "cycle_id": cycle_id,
                "motion_id": motion_id,
                "accepted": result.accepted_count,
                "revisions": result.revision_count,
                "escalations": result.escalation_count,
                "ts": now_iso(),
            },
        )

        logger.info(
            "review_completed",
            cycle_id=cycle_id,
            motion_id=motion_id,
            accepted=result.accepted_count,
            revisions=result.revision_count,
            escalations=result.escalation_count,
            mode="llm",
        )

        return result

    def run_review_simulation(
        self,
        plan: dict[str, Any],
        proposals: list[ImplementationProposal],
        resource_summary: AggregatedResourceSummary | None = None,
        iteration_number: int = 1,
    ) -> ExecutiveReviewResult:
        """Run Executive Review in simulation mode.

        Creates structured review results without LLM for testing
        and manual workflow development.

        Args:
            plan: Execution plan dictionary
            proposals: Implementation proposals to review
            resource_summary: Optional aggregated resource summary
            iteration_number: Current iteration number

        Returns:
            ExecutiveReviewResult with simulated outcomes
        """
        cycle_id = plan.get("cycle_id", "")
        motion_id = plan.get("motion_id", "")
        review_id = f"rev_{uuid.uuid4().hex[:12]}"

        proposal_results: list[ProposalReviewResult] = []
        escalations: list[ConclaveEscalation] = []

        for proposal in proposals:
            # Simulate review decision based on proposal content
            outcome, acceptance, revision = self._simulate_proposal_review(
                proposal=proposal,
                cycle_id=cycle_id,
                motion_id=motion_id,
                iteration_number=iteration_number,
            )

            proposal_results.append(
                ProposalReviewResult(
                    proposal_id=proposal.proposal_id,
                    epic_id=proposal.epic_id,
                    outcome=outcome,
                    acceptance=acceptance,
                    revision_request=revision,
                )
            )

        # Check for escalations (simulation assumes none needed unless max iterations)
        if iteration_number >= self._max_iterations:
            revisions_remaining = sum(
                1
                for pr in proposal_results
                if pr.outcome == ReviewOutcome.REVISION_REQUESTED
            )
            if revisions_remaining > 0:
                escalations.append(
                    ConclaveEscalation(
                        escalation_id=f"esc_{uuid.uuid4().hex[:12]}",
                        cycle_id=cycle_id,
                        motion_id=motion_id,
                        escalation_reason=(
                            f"Max iterations ({self._max_iterations}) reached with "
                            f"{revisions_remaining} unresolved revision(s)"
                        ),
                        questions_for_conclave=[
                            "Should implementation proceed with known issues?",
                            "Are additional resources needed?",
                            "Should scope be reduced?",
                        ],
                        proposed_options=[
                            "Proceed with acceptance conditions",
                            "Allocate additional resources",
                            "Reduce scope and proceed",
                            "Reject implementation",
                        ],
                        urgency=EscalationUrgency.HIGH,
                        escalated_at=now_iso(),
                    )
                )

        # Build result
        accepted_count = sum(
            1 for pr in proposal_results if pr.outcome == ReviewOutcome.ACCEPTED
        )
        revision_count = sum(
            1
            for pr in proposal_results
            if pr.outcome == ReviewOutcome.REVISION_REQUESTED
        )

        result = ExecutiveReviewResult(
            review_id=review_id,
            cycle_id=cycle_id,
            motion_id=motion_id,
            reviewed_at=now_iso(),
            proposal_results=proposal_results,
            escalations=escalations,
            total_proposals=len(proposals),
            accepted_count=accepted_count,
            revision_count=revision_count,
            escalation_count=len(escalations),
            iteration_number=iteration_number,
            max_iterations_reached=iteration_number >= self._max_iterations,
            resource_summary=(resource_summary.to_dict() if resource_summary else {}),
        )

        self._emit(
            "review.completed",
            {
                "cycle_id": cycle_id,
                "motion_id": motion_id,
                "accepted": accepted_count,
                "revisions": revision_count,
                "escalations": len(escalations),
                "mode": "simulation",
                "ts": now_iso(),
            },
        )

        logger.info(
            "review_completed",
            cycle_id=cycle_id,
            motion_id=motion_id,
            accepted=accepted_count,
            revisions=revision_count,
            escalations=len(escalations),
            mode="simulation",
        )

        return result

    def _simulate_proposal_review(
        self,
        proposal: ImplementationProposal,
        cycle_id: str,
        motion_id: str,
        iteration_number: int,
    ) -> tuple[ReviewOutcome, PlanAcceptance | None, RevisionRequest | None]:
        """Simulate review of a single proposal."""
        # Simulation logic: accept most proposals, request revision for some
        # Based on iteration number, more proposals are accepted in later iterations

        validation_errors = proposal.validate()
        has_high_risks = any(
            r.impact.value in ("MAJOR", "SEVERE")
            and r.likelihood.value in ("LIKELY", "ALMOST_CERTAIN")
            for r in proposal.risks
        )

        # Accept if valid and risks are manageable (or after first iteration)
        should_accept = len(validation_errors) == 0 and (
            not has_high_risks or iteration_number > 1
        )

        if should_accept:
            acceptance = PlanAcceptance(
                acceptance_id=f"acc_{uuid.uuid4().hex[:12]}",
                epic_id=proposal.epic_id,
                proposal_id=proposal.proposal_id,
                cycle_id=cycle_id,
                motion_id=motion_id,
                accepted_at=now_iso(),
                approved_tactics=[t.tactic_id for t in proposal.tactics],
                approved_resources=[r.request_id for r in proposal.resource_requests],
                acceptance_conditions=[
                    "Implementation must follow approved tactics",
                    "Resource usage must be tracked",
                ],
                monitoring_requirements=[
                    "Weekly progress reports",
                    "Risk register updates",
                ],
                proceed_to_earl_tasking=True,
            )
            return ReviewOutcome.ACCEPTED, acceptance, None
        else:
            concerns = []
            if validation_errors:
                concerns.extend(validation_errors)
            if has_high_risks:
                concerns.append("High-impact risks require additional mitigation")

            revision = RevisionRequest(
                request_id=f"rev_{uuid.uuid4().hex[:12]}",
                epic_id=proposal.epic_id,
                proposal_id=proposal.proposal_id,
                cycle_id=cycle_id,
                motion_id=motion_id,
                revision_type=(
                    RevisionType.RISK_MITIGATION
                    if has_high_risks
                    else RevisionType.SCOPE_CLARIFICATION
                ),
                revision_reason=("Proposal requires revision before acceptance"),
                specific_concerns=concerns,
                constraints=[
                    "Address all validation errors",
                    "Provide detailed risk mitigation plans",
                ],
                questions=[
                    "How will high-impact risks be mitigated?",
                    "What contingency plans are in place?",
                ],
                response_deadline=(
                    datetime.now(timezone.utc) + timedelta(hours=24)
                ).strftime(ISO),
                iteration_count=iteration_number,
            )
            return ReviewOutcome.REVISION_REQUESTED, None, revision

    # ------------------------------------------------------------------
    # Iteration Handling
    # ------------------------------------------------------------------

    def check_iteration_needed(self, result: ExecutiveReviewResult) -> bool:
        """Check if revision iteration is needed.

        Args:
            result: The review result to check

        Returns:
            True if iteration needed, False otherwise
        """
        return result.needs_iteration() and not result.max_iterations_reached

    def prepare_revision_handback(
        self,
        result: ExecutiveReviewResult,
        response_deadline_hours: int = 24,
    ) -> RevisionHandback:
        """Prepare revision handback for Administration.

        Args:
            result: The review result with revision requests
            response_deadline_hours: Hours until response deadline

        Returns:
            RevisionHandback package for Administration
        """
        deadline = (
            datetime.now(timezone.utc) + timedelta(hours=response_deadline_hours)
        ).strftime(ISO)

        handback = RevisionHandback.from_review_result(
            result=result,
            handback_id=f"hb_{uuid.uuid4().hex[:12]}",
            response_deadline=deadline,
            created_at=now_iso(),
            global_constraints=[
                f"Iteration {result.iteration_number + 1} of {self._max_iterations}",
                "Address all specific concerns listed",
                "Maintain traceability to original epic intent",
            ],
        )

        self._emit(
            "review.handback.prepared",
            {
                "cycle_id": result.cycle_id,
                "motion_id": result.motion_id,
                "handback_id": handback.handback_id,
                "revision_count": len(handback.revision_requests),
                "iteration": handback.iteration_number,
                "ts": now_iso(),
            },
        )

        return handback

    # ------------------------------------------------------------------
    # Output Saving
    # ------------------------------------------------------------------

    def save_results(
        self,
        result: ExecutiveReviewResult,
        output_dir: Path,
    ) -> Path:
        """Save Executive Review results.

        Creates output structure:
            output_dir/
                {motion_id}/
                    review_result.json
                    plan_acceptances/
                        acceptance_{epic_id}.json
                    revision_requests/
                        revision_{epic_id}.json
                    escalations/
                        escalation_{id}.json
                    revision_handback.json (if revisions needed)

        Args:
            result: The review result to save
            output_dir: Base output directory

        Returns:
            Path to motion output directory
        """
        motion_dir = output_dir / result.motion_id
        motion_dir.mkdir(parents=True, exist_ok=True)

        # Save main result
        _save_json(motion_dir / "review_result.json", result.to_dict())

        # Save individual acceptances
        acceptances_dir = motion_dir / "plan_acceptances"
        acceptances_dir.mkdir(exist_ok=True)
        for pr in result.proposal_results:
            if pr.acceptance:
                _save_json(
                    acceptances_dir / f"acceptance_{pr.epic_id}.json",
                    pr.acceptance.to_dict(),
                )

        # Save individual revision requests
        revisions_dir = motion_dir / "revision_requests"
        revisions_dir.mkdir(exist_ok=True)
        for pr in result.proposal_results:
            if pr.revision_request:
                _save_json(
                    revisions_dir / f"revision_{pr.epic_id}.json",
                    pr.revision_request.to_dict(),
                )

        # Save escalations
        if result.escalations:
            escalations_dir = motion_dir / "escalations"
            escalations_dir.mkdir(exist_ok=True)
            for esc in result.escalations:
                _save_json(
                    escalations_dir / f"escalation_{esc.escalation_id}.json",
                    esc.to_dict(),
                )

        # Save handback if revisions needed
        if result.needs_iteration() and not result.max_iterations_reached:
            handback = self.prepare_revision_handback(result)
            _save_json(motion_dir / "revision_handback.json", handback.to_dict())

        self._emit(
            "review.results.saved",
            {
                "cycle_id": result.cycle_id,
                "motion_id": result.motion_id,
                "output_dir": str(motion_dir),
                "accepted": result.accepted_count,
                "revisions": result.revision_count,
                "escalations": result.escalation_count,
                "ts": now_iso(),
            },
        )

        logger.info(
            "results_saved",
            cycle_id=result.cycle_id,
            motion_id=result.motion_id,
            output_dir=str(motion_dir),
        )

        return motion_dir

    # ------------------------------------------------------------------
    # Internal Helpers
    # ------------------------------------------------------------------

    def _emit(self, event_type: str, payload: dict[str, Any]) -> None:
        logger.info("review_event", event_type=event_type, **payload)
        if self._event_sink:
            self._event_sink(event_type, payload)
