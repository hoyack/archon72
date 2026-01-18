"""Archon Selector port definition (Story 10-4).

Defines the abstract interface for selecting archons for deliberation
based on topic characteristics. Enables matching archons to topics
using their domains, focus areas, capabilities, and suggested tools.

Constitutional Constraints:
- FR10: 72 agents can deliberate concurrently - selection must be efficient
- NFR5: No performance degradation - O(n) scoring for 72 archons
- CT-11: Silent failure destroys legitimacy - log all selection decisions
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from src.domain.models.archon_profile import ArchonProfile

__all__ = [
    "TopicContext",
    "SelectionMode",
    "ArchonSelectionMetadata",
    "ArchonSelection",
    "ArchonSelectorProtocol",
    "DEFAULT_MIN_ARCHONS",
    "DEFAULT_MAX_ARCHONS",
    "DEFAULT_RELEVANCE_THRESHOLD",
]

# Default selection parameters
DEFAULT_MIN_ARCHONS = 1
DEFAULT_MAX_ARCHONS = 72
DEFAULT_RELEVANCE_THRESHOLD = 0.1


class SelectionMode(Enum):
    """Mode for archon selection.

    ALL: All 72 archons participate (for general deliberations)
    RELEVANT: Only archons matching topic criteria participate
    WEIGHTED: All participate but matching archons have priority ordering
    """

    ALL = "all"
    RELEVANT = "relevant"
    WEIGHTED = "weighted"


@dataclass(frozen=True)
class TopicContext:
    """Context describing a deliberation topic for archon matching.

    Attributes:
        topic_id: Unique identifier for the topic
        content: The full topic text/content
        keywords: Extracted or provided keywords for matching
        required_tools: Tools that would be useful for this topic
        domain_hint: Optional domain classification hint
        required_capabilities: Capabilities needed for this topic
    """

    topic_id: str
    content: str
    keywords: list[str] = field(default_factory=list)
    required_tools: list[str] = field(default_factory=list)
    domain_hint: str | None = None
    required_capabilities: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ArchonSelectionMetadata:
    """Metadata explaining why an archon was selected.

    Provides an audit trail for the selection decision (AC6).

    Attributes:
        archon_id: UUID of the selected archon
        archon_name: Name of the archon for logging
        relevance_score: Computed relevance score (0.0 - 1.0)
        matched_tools: List of tools that matched the topic
        matched_domain: Whether domain matched
        matched_focus_keywords: Keywords that matched focus areas
        matched_capabilities: Capabilities that matched
    """

    archon_id: UUID
    archon_name: str
    relevance_score: float
    matched_tools: list[str] = field(default_factory=list)
    matched_domain: bool = False
    matched_focus_keywords: list[str] = field(default_factory=list)
    matched_capabilities: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ArchonSelection:
    """Result of archon selection including metadata.

    Attributes:
        archons: List of selected ArchonProfile objects
        metadata: List of ArchonSelectionMetadata (parallel to archons)
        mode: The selection mode used
        selected_at: When the selection was made
        total_candidates: Total number of archons considered
        min_requested: Minimum archons requested
        max_requested: Maximum archons requested
        include_executive: Whether executive inclusion was guaranteed
    """

    archons: list[ArchonProfile]
    metadata: list[ArchonSelectionMetadata]
    mode: SelectionMode
    selected_at: datetime
    total_candidates: int
    min_requested: int
    max_requested: int
    include_executive: bool = False


class ArchonSelectorProtocol(ABC):
    """Abstract interface for archon selection.

    Selects archons for deliberation based on topic characteristics.
    Implementations score archons against topic context and return
    selections based on the specified mode and constraints.

    Selection Modes:
    - ALL: Returns all archons (may still be ordered by relevance)
    - RELEVANT: Returns only archons with score > threshold
    - WEIGHTED: Returns all archons sorted by relevance score

    Constitutional Constraints:
    - FR10: Must support 72 archons efficiently
    - NFR5: O(n) scoring algorithm
    - CT-11: Log all selection decisions
    """

    @abstractmethod
    def select(
        self,
        topic: TopicContext,
        mode: SelectionMode = SelectionMode.ALL,
        min_archons: int = DEFAULT_MIN_ARCHONS,
        max_archons: int = DEFAULT_MAX_ARCHONS,
        include_executive: bool = False,
        relevance_threshold: float = DEFAULT_RELEVANCE_THRESHOLD,
    ) -> ArchonSelection:
        """Select archons for a deliberation topic.

        Args:
            topic: The topic context for matching
            mode: Selection mode (ALL, RELEVANT, WEIGHTED)
            min_archons: Minimum number of archons to select
            max_archons: Maximum number of archons to select
            include_executive: Guarantee at least one executive director
            relevance_threshold: Minimum score for RELEVANT mode

        Returns:
            ArchonSelection with selected archons and metadata

        Raises:
            ValueError: If min_archons > max_archons or invalid parameters
        """
        ...

    @abstractmethod
    def calculate_relevance(
        self,
        profile: ArchonProfile,
        topic: TopicContext,
    ) -> ArchonSelectionMetadata:
        """Calculate relevance score for an archon against a topic.

        Scores based on:
        - Tool matches (highest weight)
        - Domain match (medium weight)
        - Focus area matches (medium weight)
        - Capability matches (lower weight)

        Args:
            profile: The archon profile to score
            topic: The topic context to match against

        Returns:
            ArchonSelectionMetadata with score and match details
        """
        ...

    @abstractmethod
    def get_executives(self) -> list[ArchonProfile]:
        """Get all executive director (King-rank) archons.

        Used for executive inclusion guarantee (AC5).

        Returns:
            List of executive director ArchonProfiles
        """
        ...
