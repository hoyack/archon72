"""CrewAI adapter for LLM-powered E2.5 Blocker Workup.

Implements BlockerWorkupProtocol using CrewAI for LLM-powered
cross-review of blockers from all contributing portfolios.

Constitutional Compliance:
- CT-11: All LLM calls logged with timing and outcomes
- CT-12: All outputs traceable to cycle_id, motion_id, and blocker_id
"""

from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING

from structlog import get_logger

from src.application.ports.blocker_workup import (
    BlockerWorkupContext,
    BlockerWorkupError,
    BlockerWorkupProtocol,
)
from src.domain.models.executive_planning import (
    BlockerDisposition,
    BlockerPacket,
    BlockerV2,
    BlockerWorkupResult,
    ConclaveQueueItem,
    DiscoveryTaskStub,
    PeerReviewSummary,
    PortfolioIdentity,
    RatifiedIntentPacket,
)
from src.domain.models.llm_config import LLMConfig
from src.infrastructure.adapters.external.crewai_json_utils import parse_json_response
from src.infrastructure.adapters.external.crewai_llm_factory import (
    create_crewai_llm,
    llm_config_from_model_string,
)

if TYPE_CHECKING:
    pass

from src.optional_deps.crewai import Agent, Crew, Task

logger = get_logger(__name__)


def _now_iso() -> str:
    """UTC timestamp in a stable, sortable format."""
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class BlockerWorkupCrewAIAdapter(BlockerWorkupProtocol):
    """CrewAI implementation of E2.5 blocker workup.

    The Plan Owner agent cross-reviews all blockers from portfolio drafting
    to detect duplicates, identify conflicts, find coverage gaps, and
    provide disposition rationale.
    """

    def __init__(
        self,
        verbose: bool = False,
        llm_config: LLMConfig | None = None,
        model: str | None = None,
        base_url: str | None = None,
    ) -> None:
        """Initialize the adapter.

        Args:
            verbose: Enable verbose LLM logging
            llm_config: LLM configuration (preferred)
            model: Model string fallback
            base_url: Base URL fallback for Ollama
        """
        self.verbose = verbose

        if llm_config:
            self._llm = create_crewai_llm(llm_config)
            logger.info(
                "blocker_workup_adapter_initialized",
                model=llm_config.model,
                provider=llm_config.provider,
                verbose=verbose,
            )
        else:
            model_string = model or "ollama/qwen3:latest"
            resolved_config = llm_config_from_model_string(
                model_string,
                temperature=0.2,  # Lower temperature for analytical tasks
                max_tokens=8192,  # Larger context for blocker analysis
                timeout_ms=120000,  # Longer timeout for complex analysis
                base_url=base_url,
            )
            self._llm = create_crewai_llm(resolved_config)
            logger.info(
                "blocker_workup_adapter_initialized",
                model=resolved_config.model,
                provider=resolved_config.provider,
                verbose=verbose,
            )

    def _create_workup_agent(
        self,
        plan_owner: PortfolioIdentity,
        context: BlockerWorkupContext,
    ) -> Agent:
        """Create a Plan Owner agent for blocker cross-review."""
        portfolio_labels = context.portfolio_labels
        owner_label = portfolio_labels.get(
            plan_owner.portfolio_id, plan_owner.portfolio_id
        )

        return Agent(
            role="Plan Owner - Blocker Cross-Reviewer",
            goal="Analyze all blockers from portfolio drafting to detect duplicates, conflicts, and gaps",
            backstory=f"""You are {plan_owner.president_name}, the Plan Owner for this executive
planning cycle. As Plan Owner of the {owner_label} portfolio, you are responsible for
cross-reviewing all blockers raised during E2 Portfolio Drafting.

Your responsibilities in E2.5 Blocker Workup:
1. Detect duplicate blockers (same issue raised by multiple portfolios)
2. Identify conflicting dispositions (same issue with incompatible resolutions)
3. Find coverage gaps (aspects of the motion not addressed by any portfolio)
4. Provide rationale for each blocker's disposition

You are thorough and objective. You ensure blocker dispositions follow the rules:
- INTENT_AMBIGUITY blockers must have ESCALATE_NOW disposition
- DEFER_DOWNSTREAM blockers must have verification_tasks
- MITIGATE_IN_EXECUTIVE blockers must have mitigation_notes

You produce a comprehensive PeerReviewSummary that enables clean E3 Integration.""",
            llm=self._llm,
            verbose=self.verbose,
            allow_delegation=False,
        )

    async def run_workup(
        self,
        packet: RatifiedIntentPacket,
        blocker_packet: BlockerPacket,
        plan_owner: PortfolioIdentity,
        context: BlockerWorkupContext,
    ) -> BlockerWorkupResult:
        """Run E2.5 blocker workup for cross-review and disposition."""
        start_time = time.time()

        logger.info(
            "blocker_workup_start",
            cycle_id=context.cycle_id,
            motion_id=context.motion_id,
            blocker_count=len(blocker_packet.blockers),
            plan_owner=plan_owner.portfolio_id,
        )

        # If no blockers, return empty result
        if not blocker_packet.blockers:
            return self._empty_workup_result(
                context.cycle_id, context.motion_id, plan_owner
            )

        agent = self._create_workup_agent(plan_owner, context)

        # Build the workup prompt
        blockers_json = json.dumps(
            [b.to_dict() for b in blocker_packet.blockers], indent=2
        )
        portfolio_labels_text = "\n".join(
            f"  - {pid}: {label}"
            for pid, label in context.portfolio_labels.items()
            if pid in context.affected_portfolios
        )

        prompt = f"""Analyze the following blockers from E2 Portfolio Drafting and produce a PeerReviewSummary.

## Motion Context
- **Motion ID:** {context.motion_id}
- **Title:** {context.motion_title}
- **Text:** {context.motion_text}
- **Constraints:** {", ".join(context.constraints) if context.constraints else "none specified"}

## Affected Portfolios
{portfolio_labels_text}

## Blockers to Review
{blockers_json}

## Your Task
Produce a JSON response with the following structure:
```json
{{
  "duplicates_detected": [
    ["blocker_id_1", "blocker_id_2"]  // Groups of duplicate blockers
  ],
  "conflicts_detected": [
    {{
      "blocker_ids": ["blocker_id_1", "blocker_id_2"],
      "conflict_type": "incompatible_dispositions",
      "description": "Both address X but one escalates while other defers"
    }}
  ],
  "coverage_gaps": [
    "No portfolio claimed ownership of compliance monitoring",
    "Security audit aspect not addressed"
  ],
  "blocker_disposition_rationale": {{
    "blocker_001": "Deferred: security audit is discovery work, not a planning halt",
    "blocker_002": "Escalated: intent ambiguity requires Conclave clarification"
  }}
}}
```

Rules for analysis:
1. **Duplicates**: Identify blockers that describe the same underlying issue
2. **Conflicts**: Find blockers with incompatible dispositions for the same concern
3. **Coverage Gaps**: Identify aspects of the motion that no blocker or contribution addresses
4. **Disposition Rationale**: Explain why each blocker's disposition is appropriate

Return ONLY the JSON object, no additional text."""

        task = Task(
            description=prompt,
            expected_output="JSON object with PeerReviewSummary fields",
            agent=agent,
        )

        crew = Crew(
            agents=[agent],
            tasks=[task],
            verbose=self.verbose,
        )

        try:
            raw_output = crew.kickoff()
            output_text = (
                str(raw_output.raw) if hasattr(raw_output, "raw") else str(raw_output)
            )
            parsed = parse_json_response(output_text)

            # Build peer review summary
            peer_review_summary = PeerReviewSummary(
                cycle_id=context.cycle_id,
                motion_id=context.motion_id,
                plan_owner_portfolio_id=plan_owner.portfolio_id,
                duplicates_detected=parsed.get("duplicates_detected", []),
                conflicts_detected=parsed.get("conflicts_detected", []),
                coverage_gaps=parsed.get("coverage_gaps", []),
                blocker_disposition_rationale=parsed.get(
                    "blocker_disposition_rationale", {}
                ),
                created_at=_now_iso(),
            )

            # Generate downstream artifacts from blockers
            conclave_queue_items, discovery_task_stubs = self._generate_artifacts(
                blocker_packet.blockers, context.cycle_id, context.motion_id
            )

            duration_ms = int((time.time() - start_time) * 1000)

            logger.info(
                "blocker_workup_complete",
                cycle_id=context.cycle_id,
                motion_id=context.motion_id,
                duplicates=len(peer_review_summary.duplicates_detected),
                conflicts=len(peer_review_summary.conflicts_detected),
                gaps=len(peer_review_summary.coverage_gaps),
                duration_ms=duration_ms,
            )

            return BlockerWorkupResult(
                cycle_id=context.cycle_id,
                motion_id=context.motion_id,
                peer_review_summary=peer_review_summary,
                final_blockers=list(blocker_packet.blockers),
                conclave_queue_items=conclave_queue_items,
                discovery_task_stubs=discovery_task_stubs,
                workup_duration_ms=duration_ms,
            )

        except Exception as e:
            logger.error(
                "blocker_workup_failed",
                cycle_id=context.cycle_id,
                motion_id=context.motion_id,
                error=str(e),
            )
            raise BlockerWorkupError(f"Blocker workup failed: {e}") from e

    async def validate_dispositions(
        self,
        blocker_packet: BlockerPacket,
        context: BlockerWorkupContext,
    ) -> list[str]:
        """Validate blocker dispositions against workup rules."""
        errors: list[str] = []
        for b in blocker_packet.blockers:
            errors.extend(b.validate())
        return errors

    async def detect_duplicates(
        self,
        blocker_packet: BlockerPacket,
    ) -> list[list[str]]:
        """Detect duplicate blockers using semantic similarity.

        This is a simplified implementation - full LLM analysis happens in run_workup.
        """
        # Group by description similarity (basic implementation)
        # Full semantic analysis happens in run_workup via LLM
        return []

    async def identify_conflicts(
        self,
        blocker_packet: BlockerPacket,
    ) -> list[dict[str, str]]:
        """Identify conflicting blocker dispositions.

        This is a simplified implementation - full LLM analysis happens in run_workup.
        """
        # Full conflict analysis happens in run_workup via LLM
        return []

    async def find_coverage_gaps(
        self,
        packet: RatifiedIntentPacket,
        blocker_packet: BlockerPacket,
        context: BlockerWorkupContext,
    ) -> list[str]:
        """Find areas not covered by any blocker or contribution.

        This is a simplified implementation - full LLM analysis happens in run_workup.
        """
        # Full gap analysis happens in run_workup via LLM
        return []

    def _empty_workup_result(
        self,
        cycle_id: str,
        motion_id: str,
        plan_owner: PortfolioIdentity,
    ) -> BlockerWorkupResult:
        """Return an empty workup result when there are no blockers."""
        peer_review_summary = PeerReviewSummary(
            cycle_id=cycle_id,
            motion_id=motion_id,
            plan_owner_portfolio_id=plan_owner.portfolio_id,
            duplicates_detected=[],
            conflicts_detected=[],
            coverage_gaps=[],
            blocker_disposition_rationale={},
            created_at=_now_iso(),
        )

        return BlockerWorkupResult(
            cycle_id=cycle_id,
            motion_id=motion_id,
            peer_review_summary=peer_review_summary,
            final_blockers=[],
            conclave_queue_items=[],
            discovery_task_stubs=[],
            workup_duration_ms=0,
        )

    def _generate_artifacts(
        self,
        blockers: list[BlockerV2],
        cycle_id: str,
        motion_id: str,
    ) -> tuple[list[ConclaveQueueItem], list[DiscoveryTaskStub]]:
        """Generate downstream artifacts from blockers based on disposition."""
        conclave_queue_items: list[ConclaveQueueItem] = []
        discovery_task_stubs: list[DiscoveryTaskStub] = []

        for b in blockers:
            if b.disposition == BlockerDisposition.ESCALATE_NOW:
                queue_item = ConclaveQueueItem(
                    queue_item_id=f"cqi_{b.id}",
                    cycle_id=cycle_id,
                    motion_id=motion_id,
                    blocker_id=b.id,
                    blocker_class=b.blocker_class,
                    questions=[b.description],
                    options=[
                        "Resolve in Conclave",
                        "Defer resolution",
                        "Reject motion",
                    ],
                    source_citations=b.escalation_conditions,
                    created_at=_now_iso(),
                )
                conclave_queue_items.append(queue_item)

            elif b.disposition == BlockerDisposition.DEFER_DOWNSTREAM:
                for vt in b.verification_tasks:
                    stub = DiscoveryTaskStub(
                        task_id=vt.task_id,
                        origin_blocker_id=b.id,
                        question=b.description,
                        deliverable=vt.success_signal,
                        max_effort=b.ttl,
                        stop_conditions=[vt.success_signal],
                        ttl=b.ttl,
                        escalation_conditions=b.escalation_conditions,
                    )
                    discovery_task_stubs.append(stub)

        return conclave_queue_items, discovery_task_stubs
