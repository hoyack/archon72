"""Archon profile model for the 72 deliberative agents.

This module defines the complete profile structure for each Archon,
combining identity data (from CSV) with operational configuration
(LLM bindings from YAML). Based on the Ars Goetia mythological
framework, each Archon embodies distinct archetypal traits.
"""

from dataclasses import dataclass
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


@dataclass(frozen=True, eq=True)
class ArchonProfile:
    """Complete Archon identity and operational configuration.

    Each of the 72 Archons has a unique profile combining:
    - Identity: Name, rank, role, backstory (from CSV)
    - Behavior: System prompt, tools, attributes (from CSV)
    - Operations: LLM provider/model binding (from YAML)

    The profile is immutable once loaded, ensuring consistency
    across deliberations.

    Attributes:
        id: Unique identifier (UUID)
        name: Archon name (e.g., "Paimon", "Belial", "Astaroth")
        aegis_rank: Hierarchy position in the Aegis Network
        original_rank: Traditional Goetic rank (King, Duke, etc.)
        rank_level: Numeric rank (8=highest, 4=lowest)
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

    # Identity fields (from CSV)
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
