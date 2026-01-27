"""CrewAI adapter for Executive Review (E4) operations.

Implements ExecutiveReviewProtocol using CrewAI for LLM-powered
review of implementation proposals from Administration.

Each President reviews proposals from their portfolio's perspective
using their per-Archon LLM binding from archon-llm-bindings.yaml.

Constitutional Compliance:
- CT-11: All LLM calls logged with timing and outcomes
- CT-12: All decisions traceable to source proposals and portfolio
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from structlog import get_logger

from src.application.ports.archon_profile_repository import ArchonProfileRepository
from src.application.ports.executive_review import (
    ExecutiveReviewProtocol,
    ReviewContext,
    ReviewError,
    SingleReviewResult,
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
    RevisionRequest,
    RevisionType,
)
from src.domain.models.llm_config import LLMConfig
from src.infrastructure.adapters.external.crewai_json_utils import parse_json_response
from src.infrastructure.adapters.external.crewai_llm_factory import (
    create_crewai_llm,
    llm_config_from_model_string,
)

if TYPE_CHECKING:
    from src.optional_deps.crewai import LLM

from src.optional_deps.crewai import Agent, Crew, Task

logger = get_logger(__name__)

ISO = "%Y-%m-%dT%H:%M:%SZ"


def _now_iso() -> str:
    """UTC timestamp in a stable, sortable format."""
    return datetime.now(timezone.utc).strftime(ISO)


class ExecutiveReviewCrewAIAdapter(ExecutiveReviewProtocol):
    """CrewAI implementation of Executive Review.

    Each President reviews proposals from their portfolio's perspective
    using their per-Archon LLM binding. This enables domain-specific
    evaluation of tactical approaches, risks, and resource requests.

    LLM instances are cached per-President to avoid connection exhaustion.
    """

    def __init__(
        self,
        profile_repository: ArchonProfileRepository | None = None,
        verbose: bool = False,
        llm_config: LLMConfig | None = None,
        model: str | None = None,
        base_url: str | None = None,
        max_retries: int = 3,
    ) -> None:
        """Initialize the adapter.

        Args:
            profile_repository: Repository for loading Archon profiles with LLM configs.
                               If provided, each President uses their specific LLM binding.
            verbose: Enable verbose LLM logging
            llm_config: Default LLM configuration (fallback when profile not found)
            model: Model string fallback
            base_url: Base URL fallback for Ollama
            max_retries: Maximum retry attempts for transient LLM failures
        """
        self.verbose = verbose
        self._profile_repository = profile_repository
        self._max_retries = max_retries

        # Cache for LLM instances per-President
        self._llm_cache: dict[str, tuple[LLM | str, LLMConfig]] = {}

        # Default LLM config for when profile lookup fails
        if llm_config:
            self._default_llm = create_crewai_llm(llm_config)
            self._default_config = llm_config
        else:
            model_string = model or "ollama/qwen3:latest"
            resolved_config = llm_config_from_model_string(
                model_string,
                temperature=0.3,
                max_tokens=4096,
                timeout_ms=60000,
                base_url=base_url,
            )
            self._default_llm = create_crewai_llm(resolved_config)
            self._default_config = resolved_config

        logger.info(
            "executive_review_adapter_initialized",
            mode="per_archon" if profile_repository else "single_llm",
            default_model=self._default_config.model,
            default_provider=self._default_config.provider,
            verbose=verbose,
        )

    def _get_president_llm(self, president_name: str) -> tuple[LLM | str, LLMConfig]:
        """Get the appropriate LLM for a President (cached)."""
        if president_name in self._llm_cache:
            return self._llm_cache[president_name]

        llm: LLM | str = self._default_llm
        config: LLMConfig = self._default_config

        if self._profile_repository:
            try:
                profile = self._profile_repository.get_by_name(president_name)
                if profile:
                    llm = create_crewai_llm(profile.llm_config)
                    config = profile.llm_config
                    logger.debug(
                        "reviewer_llm_loaded",
                        president=president_name,
                        provider=profile.llm_config.provider,
                        model=profile.llm_config.model,
                    )
            except Exception as e:
                logger.warning(
                    "reviewer_profile_lookup_failed",
                    president=president_name,
                    error=str(e),
                )

        self._llm_cache[president_name] = (llm, config)
        return llm, config

    def _create_reviewer_agent(
        self,
        portfolio_id: str,
        context: ReviewContext,
    ) -> tuple[Agent, LLMConfig]:
        """Create a reviewer agent for a portfolio.

        Uses the portfolio's President's LLM binding for review.
        """
        # Get President name from portfolio labels or derive from ID
        president_name = context.portfolio_labels.get(
            portfolio_id,
            portfolio_id.replace("portfolio_", "").title(),
        )

        llm, config = self._get_president_llm(president_name)

        agent = Agent(
            role=f"Executive Reviewer for {portfolio_id}",
            goal="Review implementation proposals for feasibility, completeness, and risk mitigation",
            backstory=f"""You are an Executive Reviewer evaluating implementation proposals
for the {portfolio_id} portfolio. Your job is to:
1. Assess tactical feasibility and completeness
2. Evaluate risk mitigation strategies
3. Verify resource requests are justified
4. Determine if the proposal should be accepted, revised, or escalated

You are rigorous but fair - you accept good proposals and provide constructive
feedback when revision is needed. You only escalate to Conclave for true
governance-level ambiguities.""",
            llm=llm,
            verbose=self.verbose,
            allow_delegation=False,
        )

        return agent, config

    async def review_proposal(
        self,
        proposal: ImplementationProposal,
        context: ReviewContext,
    ) -> SingleReviewResult:
        """Review a single implementation proposal."""
        start_time = time.time()

        logger.info(
            "review_proposal_start",
            proposal_id=proposal.proposal_id,
            epic_id=proposal.epic_id,
            portfolio_id=proposal.proposing_portfolio_id,
            motion_id=context.motion_id,
        )

        agent, llm_config = self._create_reviewer_agent(
            proposal.proposing_portfolio_id, context
        )

        # Build review prompt
        tactics_text = "\n".join(
            f"  - {t.tactic_id}: {t.description}" for t in proposal.tactics
        )
        risks_text = "\n".join(
            f"  - [{r.likelihood.value}/{r.impact.value}] {r.description}"
            for r in proposal.risks
        )
        resources_text = "\n".join(
            f"  - [{r.priority.value}] {r.resource_type.value}: {r.description}"
            for r in proposal.resource_requests
        )

        constraints_text = ', '.join(context.constraints) if context.constraints else 'None'

        review_prompt = f"""OUTPUT ONLY VALID JSON. No prose, no explanation outside JSON.

PROPOSAL: {proposal.proposal_id} for epic {proposal.epic_id}
Motion: {context.motion_title}
Iteration: {context.iteration_number}/{context.max_iterations}
Portfolio: {proposal.proposing_portfolio_id}

Tactics: {tactics_text or "None"}
Risks: {risks_text or "None"}
Resources: {resources_text or "None"}
Capacity: {proposal.capacity_commitment.committed_units} units ({proposal.capacity_commitment.confidence.value} confidence)
Constraints: {constraints_text}

REVIEW: Are tactics actionable? Risks mitigated? Resources justified? Capacity realistic?

OUTPUT FORMAT - Choose ONE outcome:

ACCEPT (proposal is good):
{{"outcome":"ACCEPT","reasoning":"WHY ACCEPTING","concerns":[],"acceptance_conditions":["CONDITION1"]}}

REVISE (needs changes):
{{"outcome":"REVISE","reasoning":"WHY REVISING","concerns":["CONCERN1"],"revision_type":"SCOPE_CLARIFICATION","questions_for_administration":["QUESTION1"]}}

ESCALATE (governance issue):
{{"outcome":"ESCALATE","reasoning":"WHY ESCALATING","concerns":["CONCERN1"],"questions_for_conclave":["QUESTION1"]}}

Valid revision_type: CAPACITY_REBALANCE, RISK_MITIGATION, TACTICAL_CHANGE, RESOURCE_CONSTRAINT, SCOPE_CLARIFICATION

CRITICAL: Output ONLY the JSON object. No markdown, no ```json, no explanation."""

        task = Task(
            description=review_prompt,
            expected_output='A single JSON object with "outcome" key set to ACCEPT, REVISE, or ESCALATE. No prose.',
            agent=agent,
        )

        crew = Crew(agents=[agent], tasks=[task], verbose=self.verbose)

        # Retry loop
        last_error: Exception | None = None
        raw_output: str = ""

        for attempt in range(self._max_retries):
            try:
                result = await asyncio.to_thread(crew.kickoff)
                raw_output = str(result.raw) if hasattr(result, "raw") else str(result)

                if not raw_output or raw_output.strip() in ("None", "null", ""):
                    raise ValueError("Empty response from LLM")

                parsed = parse_json_response(raw_output, aggressive=True)
                duration_ms = int((time.time() - start_time) * 1000)

                outcome_str = parsed.get("outcome", "REVISE").upper()
                outcome_map = {
                    "ACCEPT": ReviewOutcome.ACCEPTED,
                    "ACCEPTED": ReviewOutcome.ACCEPTED,
                    "REVISE": ReviewOutcome.REVISION_REQUESTED,
                    "REVISION_REQUESTED": ReviewOutcome.REVISION_REQUESTED,
                    "ESCALATE": ReviewOutcome.ESCALATE_TO_CONCLAVE,
                    "ESCALATE_TO_CONCLAVE": ReviewOutcome.ESCALATE_TO_CONCLAVE,
                }
                outcome = outcome_map.get(outcome_str, ReviewOutcome.REVISION_REQUESTED)

                acceptance = None
                revision_request = None
                escalation = None

                if outcome == ReviewOutcome.ACCEPTED:
                    acceptance = PlanAcceptance(
                        acceptance_id=f"acc_{uuid.uuid4().hex[:12]}",
                        epic_id=proposal.epic_id,
                        proposal_id=proposal.proposal_id,
                        cycle_id=context.cycle_id,
                        motion_id=context.motion_id,
                        accepted_at=_now_iso(),
                        approved_tactics=[t.tactic_id for t in proposal.tactics],
                        approved_resources=[r.request_id for r in proposal.resource_requests],
                        acceptance_conditions=parsed.get("acceptance_conditions", []),
                        monitoring_requirements=["Progress tracking required"],
                        proceed_to_earl_tasking=True,
                        reviewer_portfolio_id=proposal.proposing_portfolio_id,
                        review_notes=parsed.get("reasoning", ""),
                    )
                elif outcome == ReviewOutcome.REVISION_REQUESTED:
                    revision_type_str = parsed.get("revision_type", "SCOPE_CLARIFICATION")
                    try:
                        revision_type = RevisionType(revision_type_str)
                    except ValueError:
                        revision_type = RevisionType.SCOPE_CLARIFICATION

                    revision_request = RevisionRequest(
                        request_id=f"rev_{uuid.uuid4().hex[:12]}",
                        epic_id=proposal.epic_id,
                        proposal_id=proposal.proposal_id,
                        cycle_id=context.cycle_id,
                        motion_id=context.motion_id,
                        revision_type=revision_type,
                        revision_reason=parsed.get("reasoning", "Revision needed"),
                        specific_concerns=parsed.get("concerns", []),
                        constraints=context.constraints,
                        questions=parsed.get("questions_for_administration", []),
                        response_deadline=(
                            datetime.now(timezone.utc) + timedelta(hours=24)
                        ).strftime(ISO),
                        reviewer_portfolio_id=proposal.proposing_portfolio_id,
                        iteration_count=context.iteration_number,
                    )
                else:  # ESCALATE_TO_CONCLAVE
                    escalation = ConclaveEscalation(
                        escalation_id=f"esc_{uuid.uuid4().hex[:12]}",
                        cycle_id=context.cycle_id,
                        motion_id=context.motion_id,
                        escalation_reason=parsed.get("reasoning", "Escalation needed"),
                        questions_for_conclave=parsed.get("questions_for_conclave", []),
                        proposed_options=["Resolve in Conclave", "Defer", "Reject"],
                        source_proposal_ids=[proposal.proposal_id],
                        affected_portfolios=[proposal.proposing_portfolio_id],
                        urgency=EscalationUrgency.HIGH,
                        escalated_at=_now_iso(),
                        escalated_by_portfolio_id=proposal.proposing_portfolio_id,
                    )

                logger.info(
                    "review_proposal_complete",
                    proposal_id=proposal.proposal_id,
                    outcome=outcome.value,
                    duration_ms=duration_ms,
                    model=llm_config.model,
                )

                return SingleReviewResult(
                    proposal_id=proposal.proposal_id,
                    epic_id=proposal.epic_id,
                    outcome=outcome,
                    acceptance=acceptance,
                    revision_request=revision_request,
                    escalation=escalation,
                    review_duration_ms=duration_ms,
                    review_notes=parsed.get("reasoning", ""),
                )

            except json.JSONDecodeError as e:
                logger.warning(
                    "review_json_parse_failed",
                    proposal_id=proposal.proposal_id,
                    error=str(e),
                    attempt=attempt + 1,
                )
                last_error = e
            except Exception as e:
                logger.warning(
                    "review_proposal_retry",
                    proposal_id=proposal.proposal_id,
                    error=str(e),
                    attempt=attempt + 1,
                )
                last_error = e

            if attempt < self._max_retries - 1:
                await asyncio.sleep(2 ** (attempt + 1))

        # All retries exhausted - return revision request as fallback
        logger.error(
            "review_proposal_all_retries_exhausted",
            proposal_id=proposal.proposal_id,
            error=str(last_error),
        )
        raise ReviewError(f"Review failed after {self._max_retries} attempts: {last_error}")

    async def batch_review_proposals(
        self,
        proposals: list[ImplementationProposal],
        context: ReviewContext,
    ) -> ExecutiveReviewResult:
        """Review multiple implementation proposals."""
        logger.info(
            "batch_review_start",
            motion_id=context.motion_id,
            proposal_count=len(proposals),
        )

        review_id = f"rev_{uuid.uuid4().hex[:12]}"
        proposal_results: list[ProposalReviewResult] = []
        escalations: list[ConclaveEscalation] = []

        for proposal in proposals:
            try:
                result = await self.review_proposal(proposal, context)

                proposal_results.append(
                    ProposalReviewResult(
                        proposal_id=result.proposal_id,
                        epic_id=result.epic_id,
                        outcome=result.outcome,
                        acceptance=result.acceptance,
                        revision_request=result.revision_request,
                        review_duration_ms=result.review_duration_ms,
                    )
                )

                if result.escalation:
                    escalations.append(result.escalation)

            except ReviewError as e:
                logger.error(
                    "batch_review_proposal_failed",
                    proposal_id=proposal.proposal_id,
                    error=str(e),
                )
                # Continue with remaining proposals

            # Small delay between reviews
            await asyncio.sleep(0.5)

        accepted_count = sum(
            1 for pr in proposal_results if pr.outcome == ReviewOutcome.ACCEPTED
        )
        revision_count = sum(
            1 for pr in proposal_results if pr.outcome == ReviewOutcome.REVISION_REQUESTED
        )

        result = ExecutiveReviewResult(
            review_id=review_id,
            cycle_id=context.cycle_id,
            motion_id=context.motion_id,
            reviewed_at=_now_iso(),
            proposal_results=proposal_results,
            escalations=escalations,
            total_proposals=len(proposals),
            accepted_count=accepted_count,
            revision_count=revision_count,
            escalation_count=len(escalations),
            iteration_number=context.iteration_number,
            max_iterations_reached=context.iteration_number >= context.max_iterations,
        )

        logger.info(
            "batch_review_complete",
            motion_id=context.motion_id,
            accepted=accepted_count,
            revisions=revision_count,
            escalations=len(escalations),
        )

        return result

    async def evaluate_resource_requests(
        self,
        resource_summary: AggregatedResourceSummary,
        context: ReviewContext,
    ) -> dict[str, bool]:
        """Evaluate aggregated resource requests."""
        # For now, approve all resource requests
        # Could be enhanced with LLM-powered resource arbitration
        return {
            req.request_id: True
            for req in resource_summary.all_requests
        }

    async def check_escalation_needed(
        self,
        proposals: list[ImplementationProposal],
        context: ReviewContext,
    ) -> list[ConclaveEscalation]:
        """Check if any proposals require Conclave escalation."""
        escalations: list[ConclaveEscalation] = []

        for proposal in proposals:
            # Check for intent ambiguity indicators
            has_ambiguity = any(
                "ambiguity" in r.description.lower() or
                "unclear" in r.description.lower()
                for r in proposal.risks
            )

            if has_ambiguity:
                escalations.append(
                    ConclaveEscalation(
                        escalation_id=f"esc_{uuid.uuid4().hex[:12]}",
                        cycle_id=context.cycle_id,
                        motion_id=context.motion_id,
                        escalation_reason="Intent ambiguity detected in proposal risks",
                        questions_for_conclave=["Clarify motion intent"],
                        proposed_options=["Clarify", "Proceed as-is", "Reject"],
                        source_proposal_ids=[proposal.proposal_id],
                        affected_portfolios=[proposal.proposing_portfolio_id],
                        urgency=EscalationUrgency.MEDIUM,
                        escalated_at=_now_iso(),
                    )
                )

        return escalations

    async def generate_revision_guidance(
        self,
        proposal: ImplementationProposal,
        concerns: list[str],
        context: ReviewContext,
    ) -> RevisionRequest:
        """Generate detailed revision guidance for Administration."""
        return RevisionRequest(
            request_id=f"rev_{uuid.uuid4().hex[:12]}",
            epic_id=proposal.epic_id,
            proposal_id=proposal.proposal_id,
            cycle_id=context.cycle_id,
            motion_id=context.motion_id,
            revision_type=RevisionType.SCOPE_CLARIFICATION,
            revision_reason="Executive review identified concerns requiring revision",
            specific_concerns=concerns,
            constraints=context.constraints,
            questions=["How will these concerns be addressed?"],
            response_deadline=(
                datetime.now(timezone.utc) + timedelta(hours=24)
            ).strftime(ISO),
            reviewer_portfolio_id=proposal.proposing_portfolio_id,
            iteration_count=context.iteration_number,
        )


def create_executive_reviewer(
    profile_repository: ArchonProfileRepository | None = None,
    verbose: bool = False,
    llm_config: LLMConfig | None = None,
    model: str | None = None,
    base_url: str | None = None,
) -> ExecutiveReviewProtocol:
    """Factory function to create an Executive Review adapter.

    Args:
        profile_repository: Optional repository for loading per-Archon LLM configs.
        verbose: Enable verbose LLM logging
        llm_config: Default LLM configuration
        model: Model string fallback
        base_url: Base URL fallback

    Returns:
        ExecutiveReviewProtocol implementation
    """
    return ExecutiveReviewCrewAIAdapter(
        profile_repository=profile_repository,
        verbose=verbose,
        llm_config=llm_config,
        model=model,
        base_url=base_url,
    )
