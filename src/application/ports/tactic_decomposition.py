"""Ports for the Earl Decomposition Bridge.

Defines:
- TacticDecomposerProtocol: decomposes a tactic into activation-ready TaskDrafts
- ClusterRegistryPort: discovers eligible Aegis Clusters for capability matching
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class TacticContext:
    """Context for a single tactic to be decomposed.

    Extracted from the winning Duke proposal's Markdown.
    """

    tactic_id: str
    title: str
    description: str
    deliverable_id: str = ""
    prerequisites: str = ""
    dependencies: str = ""
    duration: str = ""
    owner: str = ""
    rationale: str = ""


@dataclass(frozen=True)
class DecompositionContext:
    """Full context passed to the decomposer adapter.

    Includes the tactic plus RFP-level references needed to produce
    well-grounded TaskDrafts.
    """

    tactic: TacticContext
    rfp_id: str
    mandate_id: str
    proposal_id: str
    deliverable_name: str = ""
    deliverable_acceptance_criteria: list[str] = field(default_factory=list)
    related_fr_ids: list[str] = field(default_factory=list)
    related_nfr_ids: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    duke_capacity_hours: float = 0.0


class TacticDecomposerProtocol(ABC):
    """Protocol for decomposing a tactic into activation-ready TaskDrafts.

    Implementations:
    - TacticDecomposerCrewAIAdapter (LLM-assisted)
    - TacticDecomposerSimulationAdapter (deterministic, for testing)
    """

    @abstractmethod
    async def decompose_tactic(
        self,
        context: DecompositionContext,
    ) -> list[dict[str, Any]]:
        """Decompose a tactic into task draft dictionaries.

        Returns a list of dicts that can be converted to TaskDraft via
        TaskDraft.from_dict(). The adapter produces raw dicts; the service
        handles validation and lint.

        Args:
            context: Full decomposition context for one tactic.

        Returns:
            List of task draft dictionaries. Empty list means the tactic
            could not be decomposed (triggers ambiguous_tactic).
        """
        ...


# ------------------------------------------------------------------
# Cluster registry port
# ------------------------------------------------------------------


@dataclass(frozen=True)
class ClusterCandidate:
    """A Cluster that is eligible for a task activation."""

    cluster_id: str
    cluster_name: str
    steward_id: str
    capability_tags: list[str] = field(default_factory=list)
    availability_status: str = "available"
    max_concurrent_tasks: int = 3
    auth_level: str = "standard"
    contact_channel: str = ""
    contact_address: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "cluster_id": self.cluster_id,
            "cluster_name": self.cluster_name,
            "steward_id": self.steward_id,
            "capability_tags": list(self.capability_tags),
            "availability_status": self.availability_status,
            "max_concurrent_tasks": self.max_concurrent_tasks,
            "auth_level": self.auth_level,
            "contact_channel": self.contact_channel,
            "contact_address": self.contact_address,
        }


class ClusterRegistryPort(ABC):
    """Port for discovering eligible Aegis Clusters.

    The MVP adapter reads cluster JSON files from a directory.
    Future adapters may query a database or remote registry.
    """

    @abstractmethod
    async def find_eligible_clusters(
        self,
        required_tags: list[str],
        sensitivity_level: str = "standard",
    ) -> list[ClusterCandidate]:
        """Find clusters whose capabilities match the required tags.

        Filtering rules (hard):
        1. cluster.status == "active"
        2. cluster.capacity.availability_status != "unavailable"
        3. required_tags is a subset of cluster.capabilities.tags
        4. cluster.steward.auth_level meets sensitivity gate

        Args:
            required_tags: Capability tags the task requires.
            sensitivity_level: Task sensitivity (standard/sensitive/restricted).

        Returns:
            List of eligible ClusterCandidates, sorted by cluster_id
            for deterministic ordering.
        """
        ...

    @abstractmethod
    async def get_all_clusters(self) -> list[ClusterCandidate]:
        """Return all registered clusters (for summary/audit purposes)."""
        ...
