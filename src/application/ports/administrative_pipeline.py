"""Port definition for Administrative Pipeline operations.

This port defines the interface for transforming Executive execution plans
into concrete implementation proposals through bottom-up resource discovery
and capacity analysis.

Operations:
1. Generate implementation proposals from execution handoffs
2. Discover and aggregate resource requirements
3. Produce capacity commitments based on reality

Principle: "Conclave is for intent. Administration is for reality."

Constitutional Compliance:
- CT-11: All planning operations must be logged, failures reported
- CT-12: All plans must be traceable to source motions
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from src.domain.models.administrative_pipeline import (
    CapacityCommitment,
    ImplementationProposal,
    ImplementationRisk,
    ResourceRequest,
    TacticProposal,
)
from src.domain.models.executive_planning import DiscoveryTaskStub, Epic


@dataclass
class ExecutionHandoffContext:
    """Context from Executive execution plan handoff."""

    cycle_id: str
    motion_id: str
    motion_title: str
    motion_text: str
    constraints_spotlight: list[str] = field(default_factory=list)
    epics: list[Epic] = field(default_factory=list)
    discovery_task_stubs: list[DiscoveryTaskStub] = field(default_factory=list)
    execution_plan_path: str = ""
    portfolio_labels: dict[str, str] = field(default_factory=dict)
    # Additional context for LLM processing
    ratified_motion: dict[str, Any] = field(default_factory=dict)
    review_artifacts: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProposalGenerationResult:
    """Result of generating an implementation proposal."""

    proposal: ImplementationProposal
    portfolio_id: str
    epic_id: str
    generated_by: str  # "llm" or "simulation"
    duration_ms: int = 0
    trace_metadata: Any | None = None


@dataclass
class BatchProposalResult:
    """Result of batch proposal generation."""

    proposals: list[ImplementationProposal] = field(default_factory=list)
    failed_epics: list[str] = field(default_factory=list)
    total_duration_ms: int = 0
    generation_mode: str = ""  # "llm", "simulation", "manual"


class AdministrativePipelineProtocol(ABC):
    """Port for Administrative Pipeline operations.

    This protocol defines the interface for LLM-powered or simulated
    implementation proposal generation. Implementations handle the actual
    CrewAI or LLM invocation details.

    The Administrative Pipeline transforms Executive plans (WHAT) into
    concrete implementation proposals (HOW) through bottom-up discovery.
    """

    @abstractmethod
    async def generate_proposal(
        self,
        epic: Epic,
        discovery_stubs: list[DiscoveryTaskStub],
        context: ExecutionHandoffContext,
    ) -> ProposalGenerationResult:
        """Generate an implementation proposal for a single epic.

        Analyzes the epic's intent and constraints, executes any discovery
        tasks, and produces a concrete implementation proposal with:
        - Tactical approaches
        - Resource requirements
        - Capacity commitments
        - Risk assessments

        Args:
            epic: The epic to generate a proposal for
            discovery_stubs: Discovery tasks from deferred blockers
            context: Execution handoff context

        Returns:
            ProposalGenerationResult with the generated proposal

        Raises:
            ProposalGenerationError: If proposal generation fails
        """
        ...

    @abstractmethod
    async def batch_generate_proposals(
        self,
        epics: list[Epic],
        discovery_stubs: list[DiscoveryTaskStub],
        context: ExecutionHandoffContext,
    ) -> BatchProposalResult:
        """Generate implementation proposals for multiple epics.

        Batch processing for efficiency when planning many epics.

        Args:
            epics: List of epics to generate proposals for
            discovery_stubs: Discovery tasks from deferred blockers
            context: Execution handoff context

        Returns:
            BatchProposalResult with generated proposals

        Raises:
            ProposalGenerationError: If any proposal generation fails
        """
        ...

    @abstractmethod
    async def discover_resources(
        self,
        epic: Epic,
        context: ExecutionHandoffContext,
    ) -> list[ResourceRequest]:
        """Discover resource requirements for an epic.

        Bottom-up resource discovery that identifies what's actually
        needed for implementation based on technical analysis.

        Args:
            epic: The epic to analyze
            context: Execution handoff context

        Returns:
            List of discovered resource requests

        Raises:
            ResourceDiscoveryError: If discovery fails
        """
        ...

    @abstractmethod
    async def assess_risks(
        self,
        epic: Epic,
        tactics: list[TacticProposal],
        context: ExecutionHandoffContext,
    ) -> list[ImplementationRisk]:
        """Assess implementation risks for an epic.

        Analyzes the proposed tactics and identifies potential risks
        that may affect delivery.

        Args:
            epic: The epic being implemented
            tactics: Proposed tactical approaches
            context: Execution handoff context

        Returns:
            List of identified implementation risks

        Raises:
            RiskAssessmentError: If assessment fails
        """
        ...

    @abstractmethod
    async def commit_capacity(
        self,
        epic: Epic,
        tactics: list[TacticProposal],
        resource_requests: list[ResourceRequest],
        context: ExecutionHandoffContext,
    ) -> CapacityCommitment:
        """Generate a capacity commitment for an epic.

        Produces a reality-based capacity commitment based on
        available resources and proposed tactics.

        Args:
            epic: The epic being committed to
            tactics: Approved tactical approaches
            resource_requests: Required resources
            context: Execution handoff context

        Returns:
            CapacityCommitment with confidence level

        Raises:
            CapacityCommitmentError: If commitment fails
        """
        ...


# -----------------------------------------------------------------------------
# Exceptions
# -----------------------------------------------------------------------------


class AdministrativePipelineError(Exception):
    """Base exception for Administrative Pipeline operations."""

    pass


class ProposalGenerationError(AdministrativePipelineError):
    """Error during proposal generation."""

    pass


class ResourceDiscoveryError(AdministrativePipelineError):
    """Error during resource discovery."""

    pass


class RiskAssessmentError(AdministrativePipelineError):
    """Error during risk assessment."""

    pass


class CapacityCommitmentError(AdministrativePipelineError):
    """Error during capacity commitment."""

    pass
