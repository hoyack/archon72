"""CrewAI adapter for LLM-powered President deliberation.

Implements PresidentDeliberationProtocol using CrewAI for LLM-powered
portfolio analysis and contribution/attestation generation.

Constitutional Compliance:
- CT-11: All LLM calls logged with timing and outcomes
- CT-12: All outputs traceable to motion_id and portfolio_id

LLM Configuration:
- Each President can use their per-Archon LLM binding from archon-llm-bindings.yaml
- Falls back to rank-based defaults, then global default
- Local models use Ollama via OLLAMA_HOST environment variable
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import TYPE_CHECKING

from structlog import get_logger

from src.application.ports.archon_profile_repository import ArchonProfileRepository
from src.application.ports.president_deliberation import (
    DeliberationContext,
    DeliberationResult,
    GeneratedBy,
    PresidentDeliberationError,
    PresidentDeliberationProtocol,
    TraceMetadata,
)
from src.domain.models.executive_planning import (
    SCHEMA_VERSION,
    SCHEMA_VERSION_V1,
    Blocker,
    BlockerClass,
    BlockerDisposition,
    BlockerSeverity,
    BlockerV2,
    CapacityClaim,
    NoActionAttestation,
    NoActionReason,
    PortfolioContribution,
    PortfolioIdentity,
    RatifiedIntentPacket,
    VerificationTask,
    WorkPackage,
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


def _now_iso() -> str:
    """UTC timestamp in a stable, sortable format."""
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class PresidentCrewAIAdapter(PresidentDeliberationProtocol):
    """CrewAI implementation of President deliberation.

    Each President is instantiated as a CrewAI agent with their portfolio
    context, enabling domain-specific analysis of ratified motions.

    Each President can use their per-Archon LLM binding from archon-llm-bindings.yaml,
    with rank-based defaults and global fallback for local Ollama models.

    LLM instances are cached per-President to avoid connection exhaustion with
    rate-limited endpoints like Ollama Cloud.
    """

    def __init__(
        self,
        profile_repository: ArchonProfileRepository | None = None,
        verbose: bool = False,
        llm_config: LLMConfig | None = None,
        model: str | None = None,
        base_url: str | None = None,
    ) -> None:
        """Initialize the adapter.

        Args:
            profile_repository: Repository for loading Archon profiles with LLM configs.
                               If provided, each President uses their specific LLM binding.
                               If None, falls back to the provided llm_config or default.
            verbose: Enable verbose LLM logging
            llm_config: Default LLM configuration (used when profile_repository not provided)
            model: Model string fallback
            base_url: Base URL fallback for Ollama
        """
        self.verbose = verbose
        self._profile_repository = profile_repository

        # Cache for LLM instances per-President to avoid connection exhaustion
        # Key: president_name, Value: (LLM instance, LLMConfig)
        self._llm_cache: dict[str, tuple[LLM | str, LLMConfig]] = {}

        # Default LLM config for when profile lookup fails
        if llm_config:
            self._default_llm = create_crewai_llm(llm_config)
            self._default_config = llm_config
            logger.info(
                "president_adapter_initialized",
                mode="per_archon" if profile_repository else "single_llm",
                default_model=llm_config.model,
                default_provider=llm_config.provider,
                verbose=verbose,
            )
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
                "president_adapter_initialized",
                mode="per_archon" if profile_repository else "single_llm",
                default_model=resolved_config.model,
                default_provider=resolved_config.provider,
                verbose=verbose,
            )

        if profile_repository:
            logger.info(
                "president_adapter_using_profiles",
                message="Each President will use their per-Archon LLM binding",
            )
        else:
            logger.info(
                "president_adapter_no_profiles",
                message="All Presidents will use default LLM configuration",
            )

    def _get_president_llm(self, president_name: str) -> tuple[LLM | str, LLMConfig]:
        """Get the appropriate LLM for a President (cached).

        Looks up the President's profile to get their per-Archon LLM binding.
        Falls back to default if profile not found.

        LLM instances are cached per-President to avoid creating new connections
        for each deliberation, which can exhaust rate-limited endpoints.

        Args:
            president_name: Name of the President

        Returns:
            Tuple of (CrewAI LLM instance, LLMConfig) configured for this President
        """
        # Check cache first
        if president_name in self._llm_cache:
            logger.debug(
                "president_llm_cache_hit",
                president=president_name,
            )
            return self._llm_cache[president_name]

        # Create new LLM instance
        llm: LLM | str = self._default_llm
        config: LLMConfig = self._default_config

        if self._profile_repository:
            try:
                profile = self._profile_repository.get_by_name(president_name)
                if profile:
                    llm = create_crewai_llm(profile.llm_config)
                    config = profile.llm_config
                    logger.debug(
                        "president_llm_loaded",
                        president=president_name,
                        provider=profile.llm_config.provider,
                        model=profile.llm_config.model,
                    )
            except Exception as e:
                logger.warning(
                    "president_profile_lookup_failed",
                    president=president_name,
                    error=str(e),
                )

        if llm is self._default_llm:
            logger.debug(
                "president_using_default_llm",
                president=president_name,
            )

        # Cache the LLM instance
        self._llm_cache[president_name] = (llm, config)
        return llm, config

    def _create_president_agent(
        self,
        portfolio: PortfolioIdentity,
        portfolio_scope: list[str],
    ) -> tuple[Agent, LLMConfig]:
        """Create a President agent with portfolio-specific context and LLM.

        Uses the President's per-Archon LLM binding from their profile.

        Args:
            portfolio: The President's portfolio identity
            portfolio_scope: List of domain scope keywords

        Returns:
            Tuple of (CrewAI Agent, LLMConfig used)
        """
        scope_text = (
            ", ".join(portfolio_scope) if portfolio_scope else "general governance"
        )
        llm, config = self._get_president_llm(portfolio.president_name)

        agent = Agent(
            role=f"President of {portfolio.portfolio_id}",
            goal=f"Analyze motions and determine appropriate contributions for the {portfolio.portfolio_id} portfolio",
            backstory=f"""You are {portfolio.president_name}, President of the {portfolio.portfolio_id}
portfolio in the Archon72 governance system. Your domain expertise covers: {scope_text}.

Your role is to:
1. Analyze ratified motions from the Conclave
2. Determine if your portfolio should contribute tasks to the execution plan
3. If contributing, define specific tasks with realistic capacity estimates
4. If not contributing, provide a clear attestation with reason

You are thorough but efficient - you only claim work that genuinely falls within your domain.
You respect other portfolios' boundaries and delegate appropriately.""",
            llm=llm,
            verbose=self.verbose,
            allow_delegation=False,
        )

        return agent, config

    async def deliberate(
        self,
        packet: RatifiedIntentPacket,
        portfolio: PortfolioIdentity,
        portfolio_scope: list[str],
        context: DeliberationContext,
    ) -> DeliberationResult:
        """Deliberate on a motion from a portfolio perspective."""
        start_time = time.time()
        start_timestamp = _now_iso()

        logger.info(
            "president_deliberation_start",
            cycle_id=context.cycle_id,
            motion_id=context.motion_id,
            portfolio_id=portfolio.portfolio_id,
            president_name=portfolio.president_name,
        )

        agent, llm_config = self._create_president_agent(portfolio, portfolio_scope)

        # Build the deliberation prompt
        scope_text = (
            ", ".join(portfolio_scope) if portfolio_scope else "general governance"
        )
        constraints_text = (
            ", ".join(context.constraints) if context.constraints else "none specified"
        )
        other_portfolios = [
            p for p in context.affected_portfolios if p != portfolio.portfolio_id
        ]
        other_text = ", ".join(other_portfolios) if other_portfolios else "none"

        is_plan_owner = context.plan_owner_portfolio_id == portfolio.portfolio_id

        # Simplified portfolio ID for cleaner IDs
        short_id = portfolio.portfolio_id.replace("portfolio_", "")

        deliberation_prompt = f"""OUTPUT ONLY VALID JSON. No prose, no explanation outside JSON.

You are {portfolio.president_name}, President of {portfolio.portfolio_id}.
Domain: {scope_text}
Role: {"PLAN OWNER" if is_plan_owner else "Contributor"}

MOTION: {context.motion_title}
{context.motion_text[:2000]}

Constraints: {constraints_text}
Other portfolios: {other_text}

DECISION: Does this motion need work from your domain ({scope_text})?

OUTPUT FORMAT - Choose ONE:

OPTION A - If contributing (action=CONTRIBUTE):
{{"action":"CONTRIBUTE","schema_version":"2.0","epic_id":"epic_{short_id}_001","work_packages":[{{"package_id":"wp_{short_id}_001","epic_id":"epic_{short_id}_001","scope_description":"YOUR SCOPE HERE","portfolio_id":"{portfolio.portfolio_id}","dependencies":[],"constraints_respected":[]}}],"capacity_claim":{{"claim_type":"COARSE_ESTIMATE","units":5,"unit_label":"capacity_units"}},"blockers":[],"reasoning":"WHY CONTRIBUTING"}}

OPTION B - If not contributing (action=NO_ACTION):
{{"action":"NO_ACTION","reason_code":"OUTSIDE_PORTFOLIO_SCOPE","explanation":"WHY NOT CONTRIBUTING","capacity_claim":{{"claim_type":"NONE","units":null,"unit_label":null}}}}

Valid reason_codes: OUTSIDE_PORTFOLIO_SCOPE, MOTION_DOES_NOT_REQUIRE_MY_DOMAIN, NO_CAPACITY_AVAILABLE, DELEGATED_TO_OTHER_PORTFOLIO

Optional blockers format (only if risks exist):
{{"id":"blocker_{short_id}_001","blocker_class":"EXECUTION_UNCERTAINTY","severity":"MEDIUM","description":"RISK","owner_portfolio_id":"{portfolio.portfolio_id}","disposition":"DEFER_DOWNSTREAM","ttl":"P7D","escalation_conditions":["IF UNRESOLVED"],"verification_tasks":[{{"task_id":"verify_001","description":"TASK","success_signal":"DONE"}}]}}

CRITICAL: Output ONLY the JSON object. No markdown, no ```json, no explanation."""

        task = Task(
            description=deliberation_prompt,
            expected_output='A single JSON object with "action" key set to either "CONTRIBUTE" or "NO_ACTION". No prose.',
            agent=agent,
        )

        crew = Crew(agents=[agent], tasks=[task], verbose=self.verbose)

        try:
            result = await asyncio.to_thread(crew.kickoff)
            raw_output = str(result.raw) if hasattr(result, "raw") else str(result)

            parsed = parse_json_response(raw_output, aggressive=True)
            duration_ms = int((time.time() - start_time) * 1000)

            action = parsed.get("action", "NO_ACTION")

            if action == "CONTRIBUTE":
                return self._build_contribution_result(
                    parsed, portfolio, context, duration_ms, start_timestamp, llm_config
                )
            else:
                return self._build_attestation_result(
                    parsed, portfolio, context, duration_ms, start_timestamp, llm_config
                )

        except json.JSONDecodeError as e:
            logger.error(
                "president_deliberation_json_failed",
                portfolio_id=portfolio.portfolio_id,
                motion_id=context.motion_id,
                error=str(e),
                raw_output=raw_output[:500] if "raw_output" in dir() else "N/A",
            )
            raise PresidentDeliberationError(f"Failed to parse response: {e}") from e
        except Exception as e:
            logger.error(
                "president_deliberation_failed",
                portfolio_id=portfolio.portfolio_id,
                motion_id=context.motion_id,
                error=str(e),
            )
            raise PresidentDeliberationError(f"Deliberation failed: {e}") from e

    def _build_contribution_result(
        self,
        parsed: dict,
        portfolio: PortfolioIdentity,
        context: DeliberationContext,
        duration_ms: int,
        start_timestamp: str,
        llm_config: LLMConfig,
    ) -> DeliberationResult:
        """Build a contribution result from parsed JSON."""
        tasks = parsed.get("tasks", [])
        work_packages_data = parsed.get("work_packages", [])
        cc = parsed.get("capacity_claim", {})
        blockers_data = parsed.get("blockers", [])
        schema_version = parsed.get("schema_version", SCHEMA_VERSION_V1)

        def _coerce_enum(enum_cls, value, default):
            try:
                return enum_cls(value)
            except Exception:
                return default

        is_v2 = (
            schema_version == SCHEMA_VERSION
            or bool(work_packages_data)
            or any(
                isinstance(b, dict)
                and (
                    b.get("schema_version") == SCHEMA_VERSION
                    or "blocker_class" in b
                    or "disposition" in b
                )
                for b in blockers_data
            )
        )

        # If v2 is requested but only tasks were provided, lift tasks into work packages.
        if is_v2 and not work_packages_data and tasks:
            lifted_packages = []
            for idx, task in enumerate(tasks):
                if not isinstance(task, dict):
                    continue
                lifted_packages.append(
                    {
                        "package_id": task.get("task_id")
                        or f"wp_{portfolio.portfolio_id}_{idx + 1:03d}",
                        "epic_id": parsed.get("epic_id")
                        or f"epic_{portfolio.portfolio_id}_001",
                        "scope_description": task.get("description")
                        or task.get("title")
                        or "Work package",
                        "portfolio_id": portfolio.portfolio_id,
                        "dependencies": task.get("dependencies", []),
                        "constraints_respected": task.get("constraints_respected", []),
                    }
                )
            work_packages_data = lifted_packages

        work_packages: list[WorkPackage] = []
        if is_v2:
            for idx, wp_data in enumerate(work_packages_data):
                if not isinstance(wp_data, dict):
                    continue
                wp = WorkPackage(
                    package_id=wp_data.get("package_id")
                    or wp_data.get("task_id")
                    or f"wp_{portfolio.portfolio_id}_{idx + 1:03d}",
                    epic_id=wp_data.get("epic_id")
                    or parsed.get("epic_id")
                    or f"epic_{portfolio.portfolio_id}_001",
                    scope_description=wp_data.get("scope_description")
                    or wp_data.get("description")
                    or wp_data.get("title")
                    or "Work package",
                    portfolio_id=wp_data.get("portfolio_id") or portfolio.portfolio_id,
                    dependencies=wp_data.get("dependencies", []),
                    constraints_respected=wp_data.get("constraints_respected", []),
                    schema_version=SCHEMA_VERSION,
                )
                work_packages.append(wp)

        blockers: list[Blocker] = []
        for idx, b in enumerate(blockers_data):
            if isinstance(b, BlockerV2):
                blockers.append(b)  # type: ignore[list-item]
                continue
            if not isinstance(b, dict):
                continue

            looks_like_v2 = (
                is_v2
                or b.get("schema_version") == SCHEMA_VERSION
                or "blocker_class" in b
                or "disposition" in b
            )

            if looks_like_v2:
                blocker_id = (
                    b.get("id") or f"blocker_{portfolio.portfolio_id}_{idx + 1:03d}"
                )
                blocker_class = _coerce_enum(
                    BlockerClass,
                    b.get("blocker_class", BlockerClass.EXECUTION_UNCERTAINTY.value),
                    BlockerClass.EXECUTION_UNCERTAINTY,
                )
                severity = _coerce_enum(
                    BlockerSeverity,
                    b.get("severity", BlockerSeverity.MEDIUM.value),
                    BlockerSeverity.MEDIUM,
                )
                disposition = _coerce_enum(
                    BlockerDisposition,
                    b.get("disposition", BlockerDisposition.DEFER_DOWNSTREAM.value),
                    BlockerDisposition.DEFER_DOWNSTREAM,
                )

                # Auto-correct common LLM errors:
                # 1. INTENT_AMBIGUITY must have disposition ESCALATE_NOW
                if (
                    blocker_class == BlockerClass.INTENT_AMBIGUITY
                    and disposition != BlockerDisposition.ESCALATE_NOW
                ):
                    logger.warning(
                        "blocker_disposition_auto_corrected",
                        blocker_id=blocker_id,
                        blocker_class=blocker_class.value,
                        old_disposition=disposition.value,
                        new_disposition=BlockerDisposition.ESCALATE_NOW.value,
                    )
                    disposition = BlockerDisposition.ESCALATE_NOW

                # 2. MITIGATE_IN_EXECUTIVE requires mitigation_notes
                mitigation_notes = b.get("mitigation_notes")
                if (
                    disposition == BlockerDisposition.MITIGATE_IN_EXECUTIVE
                    and not mitigation_notes
                ):
                    mitigation_notes = (
                        f"Auto-generated: Blocker {blocker_id} will be mitigated "
                        f"through executive coordination. Original description: {b.get('description', 'N/A')[:200]}"
                    )
                    logger.warning(
                        "blocker_mitigation_notes_auto_generated",
                        blocker_id=blocker_id,
                        disposition=disposition.value,
                    )

                ttl = b.get("ttl", "P7D")
                escalation_conditions = b.get("escalation_conditions") or [
                    "Escalate if unresolved within TTL",
                ]

                verification_tasks_data = b.get("verification_tasks", [])
                verification_tasks: list[VerificationTask] = []
                for vt_idx, vt in enumerate(verification_tasks_data):
                    if not isinstance(vt, dict):
                        continue
                    verification_tasks.append(
                        VerificationTask(
                            task_id=vt.get("task_id")
                            or f"verify_{blocker_id}_{vt_idx + 1:02d}",
                            description=vt.get("description")
                            or vt.get("task")
                            or "Discovery task",
                            success_signal=vt.get("success_signal")
                            or "Evidence gathered",
                        )
                    )

                blockers.append(  # type: ignore[list-item]
                    BlockerV2(
                        id=blocker_id,
                        blocker_class=blocker_class,
                        severity=severity,
                        description=b.get("description", ""),
                        owner_portfolio_id=b.get("owner_portfolio_id")
                        or portfolio.portfolio_id,
                        disposition=disposition,
                        ttl=ttl,
                        escalation_conditions=escalation_conditions,
                        verification_tasks=verification_tasks,
                        mitigation_notes=mitigation_notes,  # May be auto-generated
                        schema_version=SCHEMA_VERSION,
                    )
                )
            else:
                blockers.append(
                    Blocker(
                        severity=b.get("severity", "MEDIUM"),
                        description=b.get("description", ""),
                        requires_escalation=b.get("requires_escalation", False),
                    )
                )

        unit_label = cc.get("unit_label")
        if is_v2 and unit_label == "story_points":
            unit_label = "capacity_units"

        capacity = CapacityClaim(
            claim_type=cc.get("claim_type", "COARSE_ESTIMATE"),
            units=cc.get("units"),
            unit_label=unit_label,
        )

        contribution = PortfolioContribution(
            cycle_id=context.cycle_id,
            motion_id=context.motion_id,
            portfolio=portfolio,
            tasks=tasks,
            capacity_claim=capacity,
            blockers=blockers,
            work_packages=work_packages,
            schema_version=SCHEMA_VERSION if is_v2 else SCHEMA_VERSION_V1,
        )

        # Create trace metadata for provenance tracking
        trace_metadata = TraceMetadata(
            timestamp=start_timestamp,
            model=llm_config.model,
            provider=llm_config.provider,
            duration_ms=duration_ms,
            temperature=llm_config.temperature,
        )

        logger.info(
            "president_deliberation_contributed",
            portfolio_id=portfolio.portfolio_id,
            motion_id=context.motion_id,
            task_count=len(tasks),
            work_package_count=len(work_packages),
            capacity_units=capacity.units,
            blocker_count=len(blockers),
            duration_ms=duration_ms,
            model=llm_config.model,
            provider=llm_config.provider,
        )

        return DeliberationResult(
            portfolio_id=portfolio.portfolio_id,
            president_name=portfolio.president_name,
            contributed=True,
            contribution=contribution,
            deliberation_notes=parsed.get("reasoning", ""),
            duration_ms=duration_ms,
            generated_by=GeneratedBy.LLM,
            trace_metadata=trace_metadata,
        )

    def _build_attestation_result(
        self,
        parsed: dict,
        portfolio: PortfolioIdentity,
        context: DeliberationContext,
        duration_ms: int,
        start_timestamp: str,
        llm_config: LLMConfig,
    ) -> DeliberationResult:
        """Build an attestation result from parsed JSON."""
        reason_code_str = parsed.get("reason_code", "OUTSIDE_PORTFOLIO_SCOPE")
        try:
            reason_code = NoActionReason(reason_code_str)
        except ValueError:
            reason_code = NoActionReason.OUTSIDE_PORTFOLIO_SCOPE

        cc = parsed.get("capacity_claim", {})
        capacity = CapacityClaim(
            claim_type=cc.get("claim_type", "NONE"),
            units=cc.get("units"),
            unit_label=cc.get("unit_label"),
        )

        attestation = NoActionAttestation(
            cycle_id=context.cycle_id,
            motion_id=context.motion_id,
            portfolio=portfolio,
            reason_code=reason_code,
            explanation=parsed.get("explanation", ""),
            capacity_claim=capacity,
        )

        # Create trace metadata for provenance tracking
        trace_metadata = TraceMetadata(
            timestamp=start_timestamp,
            model=llm_config.model,
            provider=llm_config.provider,
            duration_ms=duration_ms,
            temperature=llm_config.temperature,
        )

        logger.info(
            "president_deliberation_no_action",
            portfolio_id=portfolio.portfolio_id,
            motion_id=context.motion_id,
            reason_code=reason_code.value,
            duration_ms=duration_ms,
            model=llm_config.model,
            provider=llm_config.provider,
        )

        return DeliberationResult(
            portfolio_id=portfolio.portfolio_id,
            president_name=portfolio.president_name,
            contributed=False,
            attestation=attestation,
            deliberation_notes=parsed.get("explanation", ""),
            duration_ms=duration_ms,
            generated_by=GeneratedBy.LLM,
            trace_metadata=trace_metadata,
        )

    async def batch_deliberate(
        self,
        packet: RatifiedIntentPacket,
        portfolios: list[tuple[PortfolioIdentity, list[str]]],
        context: DeliberationContext,
    ) -> list[DeliberationResult]:
        """Run deliberation for multiple portfolios sequentially."""
        logger.info(
            "president_batch_deliberation_start",
            motion_id=context.motion_id,
            portfolio_count=len(portfolios),
        )

        results: list[DeliberationResult] = []

        for portfolio, scope in portfolios:
            try:
                result = await self.deliberate(packet, portfolio, scope, context)
                results.append(result)
            except PresidentDeliberationError as e:
                logger.error(
                    "president_batch_deliberation_failed",
                    portfolio_id=portfolio.portfolio_id,
                    error=str(e),
                )
                # Continue with other portfolios

        logger.info(
            "president_batch_deliberation_complete",
            motion_id=context.motion_id,
            deliberated=len(results),
            failed=len(portfolios) - len(results),
        )

        return results


def create_president_deliberator(
    profile_repository: ArchonProfileRepository | None = None,
    verbose: bool = False,
    llm_config: LLMConfig | None = None,
    model: str | None = None,
    base_url: str | None = None,
) -> PresidentDeliberationProtocol:
    """Factory function to create a President deliberation adapter.

    Args:
        profile_repository: Optional repository for loading per-Archon LLM configs.
                           If provided, each President uses their specific LLM binding.
                           If None, falls back to the provided llm_config or default.
        verbose: Enable verbose LLM logging
        llm_config: Default LLM configuration (used when profile lookup fails)
        model: Model string fallback
        base_url: Base URL fallback

    Returns:
        PresidentDeliberationProtocol implementation
    """
    return PresidentCrewAIAdapter(
        profile_repository=profile_repository,
        verbose=verbose,
        llm_config=llm_config,
        model=model,
        base_url=base_url,
    )
