"""Archon profile model for the 72 deliberative agents.

This module defines the complete profile structure for each Archon,
combining identity data (from JSON) with operational configuration
(LLM bindings from YAML). Based on the Ars Goetia mythological
framework, each Archon embodies distinct archetypal traits.

Aligned with Government PRD (docs/new-requirements.md):
- Separation of powers via branch assignment
- Rank-based jurisdiction with governance permissions
- Knight-Witness role (Furcas) as special 73rd agent
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

from src.domain.models.llm_config import LLMConfig, DEFAULT_LLM_CONFIG


# Aegis Network rank hierarchy (highest to lowest)
AEGIS_RANKS = [
    "executive_director",  # King (rank_level 8)
    "senior_director",     # Duke (rank_level 7)
    "director",            # Marquis (rank_level 6)
    "managing_director",   # President (rank_level 5)
    "strategic_director",  # Prince/Earl/Knight (rank_level 4)
]

# Governance branches per Government PRD §4
# Administrative branch split into senior (Dukes) and strategic (Earls) per schema v2.2.0
GOVERNANCE_BRANCHES = [
    "legislative",            # Kings - introduce motions, define WHAT
    "executive",              # Presidents - translate WHAT to HOW
    "administrative",         # Generic administrative (legacy compatibility)
    "administrative_senior",  # Dukes - own domains, allocate resources
    "administrative_strategic",  # Earls - execute tasks, coordinate agents
    "judicial",               # Princes - evaluate compliance
    "advisory",               # Marquis - expert testimony
    "witness",                # Knight (Furcas only) - observe and record
]

# Base branch mapping for permission/constraint lookup
# Maps granular branches to their base branch for shared permissions
BASE_BRANCH = {
    "administrative_senior": "administrative",
    "administrative_strategic": "administrative",
}

# Rank to branch mapping per Government PRD
# Dukes and Earls now have distinct administrative sub-branches per schema v2.2.0
RANK_TO_BRANCH = {
    "King": "legislative",
    "President": "executive",
    "Duke": "administrative_senior",
    "Earl": "administrative_strategic",
    "Prince": "judicial",
    "Marquis": "advisory",
    "Knight": "witness",
}

# Governance permissions per branch (Government PRD §4)
# Administrative sub-branches have distinct permissions per schema v2.2.0
BRANCH_PERMISSIONS = {
    "legislative": ["introduce_motion", "define_what"],
    "executive": ["translate_what_to_how", "decompose_tasks", "identify_dependencies", "escalate_blockers"],
    "administrative": ["own_domain", "allocate_resources", "track_progress", "report_status", "execute_task", "coordinate_agents"],
    "administrative_senior": ["own_domain", "allocate_resources", "track_progress", "report_status", "delegate_task"],
    "administrative_strategic": ["execute_task", "coordinate_agents", "optimize_execution", "report_status"],
    "judicial": ["evaluate_compliance", "issue_finding", "invalidate_execution", "trigger_conclave_review"],
    "advisory": ["provide_testimony", "issue_advisory", "analyze_risk"],
    "witness": ["observe_all", "record_violations", "publish_witness_statement", "trigger_acknowledgment"],
}

# Governance constraints per branch (Government PRD §4)
# Administrative sub-branches share core constraints with role-specific additions
BRANCH_CONSTRAINTS = {
    "legislative": ["no_define_how", "no_supervise_execution", "no_judge_outcomes"],
    "executive": ["no_redefine_intent", "no_self_ratify", "must_escalate_ambiguity"],
    "administrative": ["no_reinterpret_intent", "no_suppress_failure"],
    "administrative_senior": ["no_reinterpret_intent", "no_suppress_failure", "no_direct_execution"],
    "administrative_strategic": ["no_reinterpret_intent", "no_suppress_failure", "no_resource_allocation"],
    "judicial": ["no_introduce_motion", "no_define_execution"],
    "advisory": ["advisories_non_binding", "no_judge_advised_domain"],
    "witness": ["no_propose", "no_debate", "no_define_execution", "no_judge", "no_enforce"],
}


@dataclass(frozen=True, eq=True)
class ArchonProfile:
    """Complete Archon identity and operational configuration.

    Each of the 72 Archons has a unique profile combining:
    - Identity: Name, rank, role, backstory (from JSON)
    - Governance: Branch, permissions, constraints (from Government PRD)
    - Behavior: System prompt, tools, attributes (from JSON)
    - Operations: LLM provider/model binding (from YAML)

    The profile is immutable once loaded, ensuring consistency
    across deliberations.

    Attributes:
        id: Unique identifier (UUID)
        name: Archon name (e.g., "Paimon", "Belial", "Astaroth")
        aegis_rank: Hierarchy position in the Aegis Network
        original_rank: Traditional Goetic rank (King, Duke, etc.)
        rank_level: Numeric rank (8=highest, 4=lowest)
        branch: Governance branch (legislative, executive, etc.)
        role: Functional role description
        goal: Agent's primary objective
        backstory: Rich narrative background for personality
        system_prompt: Complete CrewAI-compatible system prompt
        suggested_tools: List of tool identifiers for this archon
        allow_delegation: Whether archon can delegate to others
        attributes: Extended attributes (brand_color, energy_type, etc.)
        max_members: Maximum member capacity
        max_legions: Number of legions commanded
        llm_config: Per-archon LLM binding configuration
        created_at: Profile creation timestamp
        updated_at: Last modification timestamp
    """

    # Identity fields (from JSON)
    id: UUID
    name: str
    aegis_rank: str
    original_rank: str
    rank_level: int
    role: str
    goal: str
    backstory: str
    system_prompt: str
    suggested_tools: list[str]
    allow_delegation: bool
    attributes: dict[str, Any]
    max_members: int
    max_legions: int
    created_at: datetime
    updated_at: datetime

    # Governance field (from Government PRD)
    branch: str = field(default="")

    # Operational configuration (from YAML, with default)
    llm_config: LLMConfig = DEFAULT_LLM_CONFIG

    def __post_init__(self) -> None:
        """Validate profile integrity."""
        if self.aegis_rank not in AEGIS_RANKS:
            raise ValueError(
                f"Invalid aegis_rank '{self.aegis_rank}', "
                f"must be one of {AEGIS_RANKS}"
            )
        if not 4 <= self.rank_level <= 8:
            raise ValueError(
                f"rank_level must be between 4 and 8, got {self.rank_level}"
            )
        # Validate branch if provided
        if self.branch and self.branch not in GOVERNANCE_BRANCHES:
            raise ValueError(
                f"Invalid branch '{self.branch}', "
                f"must be one of {GOVERNANCE_BRANCHES}"
            )

    @property
    def personality(self) -> str | None:
        """Extract personality traits from attributes."""
        return self.attributes.get("personality")

    @property
    def brand_color(self) -> str | None:
        """Extract brand color from attributes."""
        return self.attributes.get("brand_color")

    @property
    def energy_type(self) -> str | None:
        """Extract energy type from attributes."""
        return self.attributes.get("energy_type")

    @property
    def domain(self) -> str | None:
        """Extract domain from attributes."""
        return self.attributes.get("domain")

    @property
    def focus_areas(self) -> str | None:
        """Extract focus areas from attributes."""
        return self.attributes.get("focus_areas")

    @property
    def capabilities(self) -> str | None:
        """Extract capabilities from attributes."""
        return self.attributes.get("capabilities")

    @property
    def is_executive(self) -> bool:
        """Check if this archon is an executive director (King)."""
        return self.aegis_rank == "executive_director"

    @property
    def is_senior(self) -> bool:
        """Check if this archon is a senior director (Duke)."""
        return self.aegis_rank == "senior_director"

    @property
    def can_delegate(self) -> bool:
        """Check if this archon can delegate to lower ranks."""
        return self.allow_delegation and self.rank_level >= 5

    @property
    def governance_branch(self) -> str:
        """Get the governance branch, deriving from rank if not set."""
        if self.branch:
            return self.branch
        return RANK_TO_BRANCH.get(self.original_rank, "")

    @property
    def governance_permissions(self) -> list[str]:
        """Get the governance permissions for this archon's branch."""
        branch = self.governance_branch
        return BRANCH_PERMISSIONS.get(branch, [])

    @property
    def governance_constraints(self) -> list[str]:
        """Get the governance constraints for this archon's branch."""
        branch = self.governance_branch
        return BRANCH_CONSTRAINTS.get(branch, [])

    @property
    def is_witness(self) -> bool:
        """Check if this archon is the Knight-Witness (Furcas)."""
        return self.governance_branch == "witness"

    @property
    def is_legislative(self) -> bool:
        """Check if this archon is in the legislative branch (King)."""
        return self.governance_branch == "legislative"

    @property
    def is_judicial(self) -> bool:
        """Check if this archon is in the judicial branch (Prince)."""
        return self.governance_branch == "judicial"

    @property
    def is_advisory(self) -> bool:
        """Check if this archon is in the advisory branch (Marquis)."""
        return self.governance_branch == "advisory"

    @property
    def is_administrative(self) -> bool:
        """Check if this archon is in the administrative branch (Duke or Earl).

        This includes both administrative_senior (Dukes) and
        administrative_strategic (Earls) sub-branches.
        """
        return self.governance_branch in (
            "administrative",
            "administrative_senior",
            "administrative_strategic",
        )

    @property
    def is_administrative_senior(self) -> bool:
        """Check if this archon is in the senior administrative branch (Duke)."""
        return self.governance_branch == "administrative_senior"

    @property
    def is_administrative_strategic(self) -> bool:
        """Check if this archon is in the strategic administrative branch (Earl)."""
        return self.governance_branch == "administrative_strategic"

    @property
    def base_governance_branch(self) -> str:
        """Get the base governance branch, mapping sub-branches to their parent.

        This is useful when you need the general branch category rather than
        the specific sub-branch. For example, both administrative_senior and
        administrative_strategic map to 'administrative'.
        """
        branch = self.governance_branch
        return BASE_BRANCH.get(branch, branch)

    def has_permission(self, permission: str) -> bool:
        """Check if this archon has a specific governance permission.

        Args:
            permission: The permission to check (e.g., "introduce_motion")

        Returns:
            True if the archon has the permission, False otherwise
        """
        return permission in self.governance_permissions

    def has_constraint(self, constraint: str) -> bool:
        """Check if this archon has a specific governance constraint.

        Args:
            constraint: The constraint to check (e.g., "no_define_how")

        Returns:
            True if the archon has the constraint, False otherwise
        """
        return constraint in self.governance_constraints

    def get_crewai_config(self) -> dict[str, Any]:
        """Generate CrewAI Agent configuration dictionary.

        Returns a dictionary suitable for initializing a CrewAI Agent
        with this archon's personality and configuration.
        """
        return {
            "role": self.role,
            "goal": self.goal,
            "backstory": self.backstory,
            "verbose": True,
            "allow_delegation": self.allow_delegation,
            # Tools will be mapped separately by the adapter
        }

    def get_system_prompt_with_context(self, context: str | None = None) -> str:
        """Generate complete system prompt with optional context injection.

        Args:
            context: Optional additional context to append

        Returns:
            Complete system prompt for LLM invocation
        """
        prompt = self.system_prompt
        if context:
            prompt = f"{prompt}\n\nCURRENT CONTEXT:\n{context}"
        return prompt
