"""Administrative Pipeline Service.

Orchestrates the transformation of Executive execution plans into
concrete implementation proposals through bottom-up resource discovery.

Pipeline Flow:
1. Load execution handoff from Executive Pipeline
2. Generate implementation proposals per epic
3. Aggregate resource requests
4. Save results for Executive Review

Principle: "Conclave is for intent. Administration is for reality."
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from structlog import get_logger

from src.application.ports.administrative_pipeline import (
    AdministrativePipelineProtocol,
    ExecutionHandoffContext,
)
from src.domain.models.administrative_pipeline import (
    ADMIN_SCHEMA_VERSION,
    AggregatedResourceSummary,
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
)
from src.domain.models.executive_planning import (
    DiscoveryTaskStub,
    Epic,
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


class AdministrativePipelineService:
    """Orchestrates Administrative Pipeline operations.

    This service coordinates:
    - Loading execution handoffs from Executive Pipeline
    - Generating implementation proposals (via LLM or simulation)
    - Aggregating resource requests
    - Saving results for Executive Review
    """

    def __init__(
        self,
        event_sink: Callable[[str, dict[str, Any]], None] | None = None,
        proposal_generator: AdministrativePipelineProtocol | None = None,
        verbose: bool = False,
    ) -> None:
        """Initialize the Administrative Pipeline Service.

        Args:
            event_sink: Optional callback for event emission
            proposal_generator: Optional LLM-powered proposal generator
            verbose: Enable verbose logging
        """
        self._event_sink = event_sink
        self._proposal_generator = proposal_generator
        self._verbose = verbose

        logger.info(
            "administrative_pipeline_initialized",
            llm_enabled=proposal_generator is not None,
            verbose=verbose,
        )

    # ------------------------------------------------------------------
    # Input Loading
    # ------------------------------------------------------------------

    def load_execution_handoff(
        self,
        executive_output_path: Path,
        motion_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Load execution plan handoffs from Executive Pipeline output.

        Args:
            executive_output_path: Path to Executive Pipeline output directory
            motion_id: Optional filter to single motion

        Returns:
            List of handoff dictionaries
        """
        executive_output_path = executive_output_path.resolve()
        handoffs: list[dict[str, Any]] = []

        # Look for motion directories
        motions_dir = executive_output_path / "motions"
        if not motions_dir.exists():
            logger.warning(
                "no_motions_directory",
                path=str(executive_output_path),
            )
            return handoffs

        for motion_dir in motions_dir.iterdir():
            if not motion_dir.is_dir():
                continue

            if motion_id and motion_dir.name != motion_id:
                continue

            handoff_path = motion_dir / "execution_plan_handoff.json"
            if handoff_path.exists():
                handoff = _load_json(handoff_path)

                # Enrich handoff with motion context from execution plan if missing
                exec_plan_path = motion_dir / "execution_plan.json"
                epic_count = 0
                if exec_plan_path.exists():
                    exec_plan = _load_json(exec_plan_path)
                    epic_count = len(exec_plan.get("epics", []))

                    # Load motion_title and motion_text from intent_provenance if not in handoff
                    if not handoff.get("motion_title") or not handoff.get("motion_text"):
                        provenance = exec_plan.get("intent_provenance", {})
                        ratification = provenance.get("ratification_record", {})
                        if not handoff.get("motion_title"):
                            handoff["motion_title"] = ratification.get(
                                "mega_motion_title", ""
                            )
                        if not handoff.get("motion_text"):
                            # Fall back to ratified motion text from review artifacts
                            review_artifacts = provenance.get("review_artifacts", {})
                            handoff["motion_text"] = review_artifacts.get(
                                "ratified_text", ""
                            )

                handoffs.append(handoff)

                self._emit(
                    "admin.handoff.loaded",
                    {
                        "motion_id": handoff.get("motion_id"),
                        "cycle_id": handoff.get("cycle_id"),
                        "epic_count": epic_count,
                        "ts": now_iso(),
                    },
                )

        logger.info(
            "execution_handoffs_loaded",
            count=len(handoffs),
            motion_id_filter=motion_id,
        )

        return handoffs

    def load_epics_from_handoff(
        self,
        handoff: dict[str, Any],
        executive_output_path: Path,
    ) -> list[Epic]:
        """Load epics from execution plan referenced in handoff.

        Args:
            handoff: Execution handoff dictionary
            executive_output_path: Base path for Executive output

        Returns:
            List of Epic objects
        """
        execution_plan_path = handoff.get("execution_plan_path")
        if not execution_plan_path:
            motion_id = handoff.get("motion_id", "unknown")
            execution_plan_path = str(
                executive_output_path / "motions" / motion_id / "execution_plan.json"
            )

        plan_path = Path(execution_plan_path)
        if not plan_path.exists():
            logger.warning(
                "execution_plan_not_found",
                path=str(plan_path),
            )
            return []

        plan = _load_json(plan_path)
        epics_data = plan.get("epics", [])

        return [Epic.from_dict(e) for e in epics_data]

    def load_discovery_stubs_from_handoff(
        self,
        handoff: dict[str, Any],
    ) -> list[DiscoveryTaskStub]:
        """Load discovery task stubs from handoff.

        Args:
            handoff: Execution handoff dictionary

        Returns:
            List of DiscoveryTaskStub objects
        """
        stubs_data = handoff.get("discovery_task_stubs", [])
        stubs: list[DiscoveryTaskStub] = []

        for stub_data in stubs_data:
            stub = DiscoveryTaskStub(
                task_id=stub_data["task_id"],
                origin_blocker_id=stub_data["origin_blocker_id"],
                question=stub_data["question"],
                deliverable=stub_data["deliverable"],
                max_effort=stub_data["max_effort"],
                stop_conditions=stub_data.get("stop_conditions", []),
                ttl=stub_data["ttl"],
                escalation_conditions=stub_data.get("escalation_conditions", []),
                suggested_tools=stub_data.get("suggested_tools", []),
            )
            stubs.append(stub)

        return stubs

    # ------------------------------------------------------------------
    # Proposal Generation
    # ------------------------------------------------------------------

    async def generate_proposals(
        self,
        handoff: dict[str, Any],
        executive_output_path: Path,
    ) -> list[ImplementationProposal]:
        """Generate implementation proposals using LLM.

        Args:
            handoff: Execution handoff dictionary
            executive_output_path: Base path for Executive output

        Returns:
            List of generated ImplementationProposal objects

        Raises:
            ValueError: If no proposal_generator is configured
        """
        if not self._proposal_generator:
            raise ValueError(
                "LLM proposal generation requires proposal_generator to be configured"
            )

        cycle_id = handoff.get("cycle_id", "")
        motion_id = handoff.get("motion_id", "")

        epics = self.load_epics_from_handoff(handoff, executive_output_path)
        discovery_stubs = self.load_discovery_stubs_from_handoff(handoff)

        # Build context
        context = ExecutionHandoffContext(
            cycle_id=cycle_id,
            motion_id=motion_id,
            motion_title=handoff.get("motion_title", ""),
            motion_text=handoff.get("motion_text", ""),
            constraints_spotlight=handoff.get("constraints_spotlight", []),
            epics=epics,
            discovery_task_stubs=discovery_stubs,
            execution_plan_path=handoff.get("execution_plan_path", ""),
        )

        self._emit(
            "admin.proposal_generation.started",
            {
                "cycle_id": cycle_id,
                "motion_id": motion_id,
                "epic_count": len(epics),
                "discovery_stub_count": len(discovery_stubs),
                "ts": now_iso(),
            },
        )

        result = await self._proposal_generator.batch_generate_proposals(
            epics=epics,
            discovery_stubs=discovery_stubs,
            context=context,
        )

        self._emit(
            "admin.proposal_generation.completed",
            {
                "cycle_id": cycle_id,
                "motion_id": motion_id,
                "proposals_generated": len(result.proposals),
                "failed_epics": result.failed_epics,
                "duration_ms": result.total_duration_ms,
                "ts": now_iso(),
            },
        )

        logger.info(
            "proposals_generated",
            cycle_id=cycle_id,
            motion_id=motion_id,
            count=len(result.proposals),
            mode="llm",
        )

        return result.proposals

    def generate_proposals_simulation(
        self,
        handoff: dict[str, Any],
        executive_output_path: Path,
    ) -> list[ImplementationProposal]:
        """Generate implementation proposals in simulation mode.

        Creates structured proposals without LLM for testing and
        manual workflow development.

        Args:
            handoff: Execution handoff dictionary
            executive_output_path: Base path for Executive output

        Returns:
            List of simulated ImplementationProposal objects
        """
        cycle_id = handoff.get("cycle_id", "")
        motion_id = handoff.get("motion_id", "")

        epics = self.load_epics_from_handoff(handoff, executive_output_path)
        discovery_stubs = self.load_discovery_stubs_from_handoff(handoff)

        # Map discovery stubs by epic
        stubs_by_epic: dict[str, list[DiscoveryTaskStub]] = {}
        for stub in discovery_stubs:
            # Match stubs to epics via discovery_required field
            for epic in epics:
                if stub.origin_blocker_id in epic.discovery_required:
                    stubs_by_epic.setdefault(epic.epic_id, []).append(stub)

        proposals: list[ImplementationProposal] = []
        for epic in epics:
            proposal = self._simulate_proposal(
                epic=epic,
                cycle_id=cycle_id,
                motion_id=motion_id,
                discovery_stubs=stubs_by_epic.get(epic.epic_id, []),
            )
            proposals.append(proposal)

        self._emit(
            "admin.proposal_generation.completed",
            {
                "cycle_id": cycle_id,
                "motion_id": motion_id,
                "proposals_generated": len(proposals),
                "failed_epics": [],
                "duration_ms": 0,
                "mode": "simulation",
                "ts": now_iso(),
            },
        )

        logger.info(
            "proposals_generated",
            cycle_id=cycle_id,
            motion_id=motion_id,
            count=len(proposals),
            mode="simulation",
        )

        return proposals

    def _simulate_proposal(
        self,
        epic: Epic,
        cycle_id: str,
        motion_id: str,
        discovery_stubs: list[DiscoveryTaskStub],
    ) -> ImplementationProposal:
        """Create a simulated proposal for an epic."""
        proposal_id = f"prop_{uuid.uuid4().hex[:12]}"
        portfolio_id = "portfolio_architecture_engineering_standards"  # Default

        # Generate tactics from epic intent
        tactics = [
            TacticProposal(
                tactic_id=f"tactic_{proposal_id}_001",
                description=f"Implement {epic.intent[:100]}",
                rationale="Primary implementation approach based on epic intent",
                prerequisites=[],
                dependencies=[],
                estimated_duration="P7D",
                owner_portfolio_id=portfolio_id,
            ),
        ]

        # Add discovery-related tactics
        for stub in discovery_stubs:
            tactics.append(
                TacticProposal(
                    tactic_id=f"tactic_{proposal_id}_{stub.task_id}",
                    description=f"Discovery: {stub.question[:100]}",
                    rationale=f"Resolve blocker {stub.origin_blocker_id}",
                    prerequisites=[],
                    dependencies=[],
                    estimated_duration=stub.max_effort,
                    owner_portfolio_id=portfolio_id,
                )
            )

        # Generate resource requests
        resource_requests = [
            ResourceRequest(
                request_id=f"req_{proposal_id}_001",
                resource_type=ResourceType.HUMAN_HOURS,
                description=f"Development capacity for {epic.epic_id}",
                justification=f"Required to implement: {epic.intent[:50]}",
                required_by=(datetime.now(timezone.utc).strftime("%Y-%m-%d")),
                priority=ResourcePriority.MEDIUM,
                quantity=40.0,
                unit="hours",
                owner_portfolio_id=portfolio_id,
                epic_id=epic.epic_id,
            ),
        ]

        # Generate risks
        risks = [
            ImplementationRisk(
                risk_id=f"risk_{proposal_id}_001",
                description="Implementation complexity may exceed estimates",
                likelihood=RiskLikelihood.POSSIBLE,
                impact=RiskImpact.MODERATE,
                mitigation_strategy="Regular progress reviews and early escalation",
                owner_portfolio_id=portfolio_id,
                affected_epics=[epic.epic_id],
            ),
        ]

        # Generate capacity commitment
        capacity_commitment = CapacityCommitment(
            portfolio_id=portfolio_id,
            committed_units=5.0,
            unit_label="story_points",
            confidence=ConfidenceLevel.MEDIUM,
            assumptions=epic.assumptions,
            caveats=["Dependent on resource availability"],
            epic_id=epic.epic_id,
        )

        return ImplementationProposal(
            proposal_id=proposal_id,
            cycle_id=cycle_id,
            motion_id=motion_id,
            epic_id=epic.epic_id,
            created_at=now_iso(),
            proposing_portfolio_id=portfolio_id,
            tactics=tactics,
            spec_references=[],
            risks=risks,
            resource_requests=resource_requests,
            capacity_commitment=capacity_commitment,
            discovery_findings=[
                f"Discovery task: {s.question}" for s in discovery_stubs
            ],
            assumptions_validated=[],
            assumptions_invalidated=[],
        )

    # ------------------------------------------------------------------
    # Resource Aggregation
    # ------------------------------------------------------------------

    def aggregate_resource_requests(
        self,
        proposals: list[ImplementationProposal],
        cycle_id: str,
        motion_id: str,
    ) -> AggregatedResourceSummary:
        """Aggregate resource requests across all proposals.

        Args:
            proposals: List of implementation proposals
            cycle_id: The executive cycle ID
            motion_id: The motion ID

        Returns:
            AggregatedResourceSummary with totals and breakdowns
        """
        summary = AggregatedResourceSummary.from_proposals(
            proposals=proposals,
            cycle_id=cycle_id,
            motion_id=motion_id,
            created_at=now_iso(),
        )

        self._emit(
            "admin.resources.aggregated",
            {
                "cycle_id": cycle_id,
                "motion_id": motion_id,
                "total_requests": summary.total_requests,
                "by_type": summary.requests_by_type,
                "by_priority": summary.requests_by_priority,
                "total_cost": summary.total_estimated_cost,
                "ts": now_iso(),
            },
        )

        logger.info(
            "resources_aggregated",
            cycle_id=cycle_id,
            motion_id=motion_id,
            total_requests=summary.total_requests,
        )

        return summary

    # ------------------------------------------------------------------
    # Output Saving
    # ------------------------------------------------------------------

    def save_results(
        self,
        proposals: list[ImplementationProposal],
        output_dir: Path,
        cycle_id: str,
        motion_id: str,
    ) -> Path:
        """Save Administrative Pipeline results.

        Creates output structure:
            output_dir/
                {motion_id}/
                    implementation_proposals/
                        proposal_{epic_id}.json
                    resource_requests.json
                    pipeline_summary.json

        Args:
            proposals: Generated implementation proposals
            output_dir: Base output directory
            cycle_id: The executive cycle ID
            motion_id: The motion ID

        Returns:
            Path to motion output directory
        """
        motion_dir = output_dir / motion_id
        proposals_dir = motion_dir / "implementation_proposals"
        proposals_dir.mkdir(parents=True, exist_ok=True)

        # Save individual proposals
        for proposal in proposals:
            proposal_path = proposals_dir / f"proposal_{proposal.epic_id}.json"
            _save_json(proposal_path, proposal.to_dict())

        # Save aggregated resources
        resource_summary = self.aggregate_resource_requests(
            proposals=proposals,
            cycle_id=cycle_id,
            motion_id=motion_id,
        )
        _save_json(motion_dir / "resource_requests.json", resource_summary.to_dict())

        # Save pipeline summary
        summary = {
            "schema_version": ADMIN_SCHEMA_VERSION,
            "cycle_id": cycle_id,
            "motion_id": motion_id,
            "created_at": now_iso(),
            "proposal_count": len(proposals),
            "proposal_ids": [p.proposal_id for p in proposals],
            "epic_ids": [p.epic_id for p in proposals],
            "total_tactics": sum(len(p.tactics) for p in proposals),
            "total_risks": sum(len(p.risks) for p in proposals),
            "total_resource_requests": resource_summary.total_requests,
            "resource_summary": {
                "by_type": resource_summary.requests_by_type,
                "by_priority": resource_summary.requests_by_priority,
                "total_cost": resource_summary.total_estimated_cost,
            },
        }
        _save_json(motion_dir / "pipeline_summary.json", summary)

        self._emit(
            "admin.results.saved",
            {
                "cycle_id": cycle_id,
                "motion_id": motion_id,
                "output_dir": str(motion_dir),
                "proposal_count": len(proposals),
                "ts": now_iso(),
            },
        )

        logger.info(
            "results_saved",
            cycle_id=cycle_id,
            motion_id=motion_id,
            output_dir=str(motion_dir),
            proposal_count=len(proposals),
        )

        return motion_dir

    # ------------------------------------------------------------------
    # Internal Helpers
    # ------------------------------------------------------------------

    def _emit(self, event_type: str, payload: dict[str, Any]) -> None:
        logger.info("admin_event", event_type=event_type, **payload)
        if self._event_sink:
            self._event_sink(event_type, payload)
