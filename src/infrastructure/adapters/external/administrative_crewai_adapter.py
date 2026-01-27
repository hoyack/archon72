"""CrewAI adapter for Administrative Pipeline proposal generation.

Implements AdministrativePipelineProtocol using CrewAI for LLM-powered
generation of implementation proposals from Executive execution plans.

Each portfolio's President uses their per-Archon LLM binding from
archon-llm-bindings.yaml for domain-specific proposal generation.

Constitutional Compliance:
- CT-11: All LLM calls logged with timing and outcomes
- CT-12: All proposals traceable to source motions and epics
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from typing import TYPE_CHECKING

from structlog import get_logger

from src.application.ports.administrative_pipeline import (
    AdministrativePipelineProtocol,
    BatchProposalResult,
    ExecutionHandoffContext,
    ProposalGenerationError,
    ProposalGenerationResult,
)
from src.application.ports.archon_profile_repository import ArchonProfileRepository
from src.domain.models.administrative_pipeline import (
    CapacityCommitment,
    ConfidenceLevel,
    ImplementationProposal,
    ImplementationRisk,
    ResourcePriority,
    ResourceRequest,
    ResourceType,
    RiskImpact,
    RiskLikelihood,
    TacticProposal,
    TechnicalSpecReference,
)
from src.domain.models.executive_planning import DiscoveryTaskStub, Epic
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


def _now_iso() -> str:
    """UTC timestamp in a stable, sortable format."""
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class AdministrativeCrewAIAdapter(AdministrativePipelineProtocol):
    """CrewAI implementation of Administrative Pipeline proposal generation.

    Each portfolio's President generates proposals using their per-Archon
    LLM binding, enabling domain-specific tactical planning and resource
    discovery.

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
            "administrative_adapter_initialized",
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
                        "admin_llm_loaded",
                        president=president_name,
                        provider=profile.llm_config.provider,
                        model=profile.llm_config.model,
                    )
            except Exception as e:
                logger.warning(
                    "admin_profile_lookup_failed",
                    president=president_name,
                    error=str(e),
                )

        self._llm_cache[president_name] = (llm, config)
        return llm, config

    def _create_proposal_agent(
        self,
        portfolio_id: str,
        context: ExecutionHandoffContext,
    ) -> tuple[Agent, LLMConfig]:
        """Create a proposal generator agent for a portfolio.

        Uses the portfolio's President's LLM binding for proposal generation.
        """
        # Get President name from portfolio labels or derive from ID
        president_name = context.portfolio_labels.get(
            portfolio_id,
            portfolio_id.replace("portfolio_", "").title(),
        )

        llm, config = self._get_president_llm(president_name)

        agent = Agent(
            role=f"Implementation Planner for {portfolio_id}",
            goal="Transform executive epics into concrete implementation proposals",
            backstory=f"""You are an Implementation Planner for the {portfolio_id} portfolio.
Your job is to transform high-level epic descriptions into concrete implementation
proposals with:
1. Specific tactical approaches (HOW to achieve the epic)
2. Resource requirements (WHAT is needed)
3. Risk assessments (WHAT could go wrong)
4. Capacity commitments (WHEN and HOW MUCH)

You are realistic about capacity and thorough about risks.
You propose actionable tactics, not vague descriptions.""",
            llm=llm,
            verbose=self.verbose,
            allow_delegation=False,
        )

        return agent, config

    async def generate_proposal(
        self,
        epic: Epic,
        discovery_stubs: list[DiscoveryTaskStub],
        context: ExecutionHandoffContext,
    ) -> ProposalGenerationResult:
        """Generate an implementation proposal for a single epic."""
        start_time = time.time()

        # Get the portfolio ID from the epic
        portfolio_id = epic.owner_portfolio_id or f"portfolio_{epic.epic_id.split('_')[1]}"

        logger.info(
            "generate_proposal_start",
            epic_id=epic.epic_id,
            portfolio_id=portfolio_id,
            motion_id=context.motion_id,
        )

        agent, llm_config = self._create_proposal_agent(portfolio_id, context)

        # Build discovery context
        discovery_text = ""
        if discovery_stubs:
            relevant_stubs = [
                s for s in discovery_stubs
                if s.origin_blocker_id and epic.epic_id in s.task_id
            ]
            if relevant_stubs:
                discovery_text = "\n".join(
                    f"  - {s.question}: {s.deliverable}" for s in relevant_stubs
                )

        # Build work packages context
        work_packages_text = ""
        if epic.work_packages:
            work_packages_text = "\n".join(
                f"  - {wp.package_id}: {wp.scope_description}"
                for wp in epic.work_packages
            )

        constraints_text = ', '.join(context.constraints_spotlight) if context.constraints_spotlight else 'None'

        proposal_prompt = f"""OUTPUT ONLY VALID JSON. No prose, no explanation outside JSON.

EPIC: {epic.epic_id} - {epic.title}
{epic.description[:1500]}

Portfolio: {portfolio_id}
Motion: {context.motion_title}
Work packages: {work_packages_text or "Derive from epic"}
Discovery tasks: {discovery_text or "None"}
Constraints: {constraints_text}

Create implementation proposal with tactics, resources, risks, capacity.

OUTPUT FORMAT (single JSON object):
{{"tactics":[{{"tactic_id":"tactic_001","description":"HOW TO DO IT","rationale":"WHY","prerequisites":[],"estimated_duration":"P5D"}}],"resources":[{{"resource_type":"TOOL","description":"WHAT NEEDED","justification":"WHY","priority":"MEDIUM","alternatives":[]}}],"risks":[{{"description":"WHAT COULD FAIL","likelihood":"MEDIUM","impact":"MODERATE","mitigation_strategy":"HOW TO PREVENT"}}],"capacity":{{"units":15,"confidence":"MEDIUM","assumptions":[],"caveats":[]}},"spec_references":[]}}

Valid resource_type: TOOL, SERVICE, DATA, INFRASTRUCTURE, HUMAN_EXPERTISE, THIRD_PARTY, BUDGET
Valid priority: CRITICAL, HIGH, MEDIUM, LOW
Valid likelihood: VERY_LOW, LOW, MEDIUM, HIGH, VERY_HIGH
Valid impact: NEGLIGIBLE, MINOR, MODERATE, MAJOR, CATASTROPHIC
Valid confidence: HIGH, MEDIUM, LOW, VERY_LOW

CRITICAL: Output ONLY the JSON object. No markdown, no ```json, no explanation."""

        task = Task(
            description=proposal_prompt,
            expected_output='A single JSON object with "tactics", "resources", "risks", and "capacity" keys. No prose.',
            agent=agent,
        )

        crew = Crew(agents=[agent], tasks=[task], verbose=self.verbose)

        # Retry loop
        for attempt in range(self._max_retries):
            try:
                result = await asyncio.to_thread(crew.kickoff)
                raw_output = str(result.raw) if hasattr(result, "raw") else str(result)

                if not raw_output or raw_output.strip() in ("None", "null", ""):
                    raise ValueError("Empty response from LLM")

                parsed = parse_json_response(raw_output, aggressive=True)
                duration_ms = int((time.time() - start_time) * 1000)

                # Build tactics
                tactics: list[TacticProposal] = []
                for idx, t in enumerate(parsed.get("tactics", [])):
                    tactics.append(
                        TacticProposal(
                            tactic_id=t.get("tactic_id", f"tactic_{idx + 1:03d}"),
                            description=t.get("description", ""),
                            rationale=t.get("rationale", ""),
                            prerequisites=t.get("prerequisites", []),
                            estimated_duration=t.get("estimated_duration", "P7D"),
                        )
                    )

                # Build resources
                resources: list[ResourceRequest] = []
                for idx, r in enumerate(parsed.get("resources", [])):
                    resource_type_str = r.get("resource_type", "TOOL")
                    try:
                        resource_type = ResourceType(resource_type_str)
                    except ValueError:
                        resource_type = ResourceType.TOOL

                    priority_str = r.get("priority", "MEDIUM")
                    try:
                        priority = ResourcePriority(priority_str)
                    except ValueError:
                        priority = ResourcePriority.MEDIUM

                    resources.append(
                        ResourceRequest(
                            request_id=f"req_{epic.epic_id}_{idx + 1:03d}",
                            resource_type=resource_type,
                            description=r.get("description", ""),
                            justification=r.get("justification", ""),
                            required_by="",
                            alternatives=r.get("alternatives", []),
                            priority=priority,
                        )
                    )

                # Build risks
                risks: list[ImplementationRisk] = []
                for idx, rk in enumerate(parsed.get("risks", [])):
                    likelihood_str = rk.get("likelihood", "MEDIUM")
                    try:
                        likelihood = RiskLikelihood(likelihood_str)
                    except ValueError:
                        likelihood = RiskLikelihood.MEDIUM

                    impact_str = rk.get("impact", "MODERATE")
                    try:
                        impact = RiskImpact(impact_str)
                    except ValueError:
                        impact = RiskImpact.MODERATE

                    risks.append(
                        ImplementationRisk(
                            risk_id=f"risk_{epic.epic_id}_{idx + 1:03d}",
                            description=rk.get("description", ""),
                            likelihood=likelihood,
                            impact=impact,
                            mitigation_strategy=rk.get("mitigation_strategy", ""),
                            owner_portfolio_id=portfolio_id,
                        )
                    )

                # Build capacity
                cap = parsed.get("capacity", {})
                confidence_str = cap.get("confidence", "MEDIUM")
                try:
                    confidence = ConfidenceLevel(confidence_str)
                except ValueError:
                    confidence = ConfidenceLevel.MEDIUM

                capacity = CapacityCommitment(
                    portfolio_id=portfolio_id,
                    committed_units=cap.get("units", 10),
                    unit_label="capacity_units",
                    confidence=confidence,
                    assumptions=cap.get("assumptions", []),
                    caveats=cap.get("caveats", []),
                )

                # Build spec references
                specs: list[TechnicalSpecReference] = []
                for idx, s in enumerate(parsed.get("spec_references", [])):
                    from src.domain.models.administrative_pipeline import SpecType
                    spec_type_str = s.get("spec_type", "TECHNICAL_DESIGN")
                    try:
                        spec_type = SpecType(spec_type_str)
                    except ValueError:
                        spec_type = SpecType.TECHNICAL_DESIGN

                    specs.append(
                        TechnicalSpecReference(
                            spec_id=f"spec_{epic.epic_id}_{idx + 1:03d}",
                            spec_type=spec_type,
                            location=s.get("location", ""),
                            summary=s.get("summary", ""),
                        )
                    )

                # Build proposal
                proposal = ImplementationProposal(
                    proposal_id=f"prop_{uuid.uuid4().hex[:12]}",
                    cycle_id=context.cycle_id,
                    motion_id=context.motion_id,
                    epic_id=epic.epic_id,
                    created_at=_now_iso(),
                    tactics=tactics,
                    spec_references=specs,
                    risks=risks,
                    resource_requests=resources,
                    capacity_commitment=capacity,
                    proposing_portfolio_id=portfolio_id,
                )

                logger.info(
                    "generate_proposal_complete",
                    epic_id=epic.epic_id,
                    tactic_count=len(tactics),
                    resource_count=len(resources),
                    risk_count=len(risks),
                    capacity_units=capacity.committed_units,
                    duration_ms=duration_ms,
                    model=llm_config.model,
                )

                return ProposalGenerationResult(
                    proposal=proposal,
                    portfolio_id=portfolio_id,
                    epic_id=epic.epic_id,
                    generated_by="llm",
                    duration_ms=duration_ms,
                )

            except json.JSONDecodeError as e:
                logger.warning(
                    "generate_proposal_json_failed",
                    epic_id=epic.epic_id,
                    error=str(e),
                    attempt=attempt + 1,
                )
            except Exception as e:
                logger.warning(
                    "generate_proposal_retry",
                    epic_id=epic.epic_id,
                    error=str(e),
                    attempt=attempt + 1,
                )

            if attempt < self._max_retries - 1:
                await asyncio.sleep(2 ** (attempt + 1))

        # All retries exhausted
        raise ProposalGenerationError(
            f"Proposal generation failed after {self._max_retries} attempts"
        )

    async def batch_generate_proposals(
        self,
        epics: list[Epic],
        discovery_stubs: list[DiscoveryTaskStub],
        context: ExecutionHandoffContext,
    ) -> BatchProposalResult:
        """Generate implementation proposals for multiple epics."""
        logger.info(
            "batch_generate_start",
            motion_id=context.motion_id,
            epic_count=len(epics),
        )

        proposals: list[ImplementationProposal] = []
        failed_epics: list[str] = []
        total_duration_ms = 0

        for epic in epics:
            try:
                result = await self.generate_proposal(epic, discovery_stubs, context)
                proposals.append(result.proposal)
                total_duration_ms += result.duration_ms
            except ProposalGenerationError as e:
                logger.error(
                    "batch_generate_epic_failed",
                    epic_id=epic.epic_id,
                    error=str(e),
                )
                failed_epics.append(epic.epic_id)

            # Small delay between proposals
            await asyncio.sleep(0.5)

        logger.info(
            "batch_generate_complete",
            motion_id=context.motion_id,
            proposals_generated=len(proposals),
            failed_epics=len(failed_epics),
            total_duration_ms=total_duration_ms,
        )

        return BatchProposalResult(
            proposals=proposals,
            failed_epics=failed_epics,
            total_duration_ms=total_duration_ms,
            generation_mode="llm",
        )

    async def discover_resources(
        self,
        epic: Epic,
        context: ExecutionHandoffContext,
    ) -> list[ResourceRequest]:
        """Discover resource requirements for an epic."""
        # Generate a proposal and extract just the resources
        discovery_result = await self.generate_proposal(epic, [], context)
        return discovery_result.proposal.resource_requests

    async def assess_risks(
        self,
        epic: Epic,
        tactics: list[TacticProposal],
        context: ExecutionHandoffContext,
    ) -> list[ImplementationRisk]:
        """Assess implementation risks for an epic."""
        # Generate a proposal and extract just the risks
        discovery_result = await self.generate_proposal(epic, [], context)
        return discovery_result.proposal.risks

    async def commit_capacity(
        self,
        epic: Epic,
        tactics: list[TacticProposal],
        resource_requests: list[ResourceRequest],
        context: ExecutionHandoffContext,
    ) -> CapacityCommitment:
        """Generate a capacity commitment for an epic."""
        # Generate a proposal and extract just the capacity
        discovery_result = await self.generate_proposal(epic, [], context)
        return discovery_result.proposal.capacity_commitment


def create_administrative_proposal_generator(
    profile_repository: ArchonProfileRepository | None = None,
    verbose: bool = False,
    llm_config: LLMConfig | None = None,
    model: str | None = None,
    base_url: str | None = None,
) -> AdministrativePipelineProtocol:
    """Factory function to create an Administrative Pipeline adapter.

    Args:
        profile_repository: Optional repository for loading per-Archon LLM configs.
        verbose: Enable verbose LLM logging
        llm_config: Default LLM configuration
        model: Model string fallback
        base_url: Base URL fallback

    Returns:
        AdministrativePipelineProtocol implementation
    """
    return AdministrativeCrewAIAdapter(
        profile_repository=profile_repository,
        verbose=verbose,
        llm_config=llm_config,
        model=model,
        base_url=base_url,
    )
