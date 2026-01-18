"""Archon Selector adapter implementation (Story 10-4).

This adapter implements ArchonSelectorProtocol to select archons
for deliberation based on topic characteristics.

Constitutional Constraints:
- FR10: 72 agents can deliberate concurrently - O(n) selection
- NFR5: No performance degradation - efficient scoring
- CT-11: Silent failure destroys legitimacy - log all decisions
"""

from __future__ import annotations

from datetime import datetime, timezone

from structlog import get_logger

from src.application.ports.archon_profile_repository import ArchonProfileRepository
from src.application.ports.archon_selector import (
    DEFAULT_MAX_ARCHONS,
    DEFAULT_MIN_ARCHONS,
    DEFAULT_RELEVANCE_THRESHOLD,
    ArchonSelection,
    ArchonSelectionMetadata,
    ArchonSelectorProtocol,
    SelectionMode,
    TopicContext,
)
from src.domain.models.archon_profile import ArchonProfile

logger = get_logger(__name__)

# Scoring weights for relevance calculation
TOOL_MATCH_WEIGHT = 0.4  # Highest weight - explicit capability
DOMAIN_MATCH_WEIGHT = 0.25  # Medium weight
FOCUS_AREA_MATCH_WEIGHT = 0.15  # Medium weight (per keyword)
CAPABILITY_MATCH_WEIGHT = 0.1  # Lower weight (per capability)


class ArchonSelectorAdapter(ArchonSelectorProtocol):
    """Archon selection based on topic relevance.

    Implements scoring and selection logic for matching archons to topics.
    Uses ArchonProfileRepository to access archon data.

    Scoring Algorithm:
    - Tool matches: 0.4 per matching tool
    - Domain match: 0.25 if domain matches
    - Focus area matches: 0.15 per matching keyword
    - Capability matches: 0.1 per matching capability
    - Score capped at 1.0

    Attributes:
        _profile_repo: Repository for accessing archon profiles
    """

    def __init__(self, profile_repository: ArchonProfileRepository) -> None:
        """Initialize the selector with a profile repository.

        Args:
            profile_repository: Repository for archon profile lookup
        """
        self._profile_repo = profile_repository
        logger.info(
            "archon_selector_initialized",
            archon_count=profile_repository.count(),
        )

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
            ValueError: If min_archons > max_archons
        """
        if min_archons > max_archons:
            raise ValueError(
                f"min_archons ({min_archons}) cannot exceed max_archons ({max_archons})"
            )

        if min_archons < 0:
            raise ValueError(f"min_archons must be non-negative, got {min_archons}")

        # Get all archons and score them
        all_archons = self._profile_repo.get_all()
        total_candidates = len(all_archons)

        # Calculate relevance for each archon
        scored: list[tuple[ArchonProfile, ArchonSelectionMetadata]] = []
        for profile in all_archons:
            metadata = self.calculate_relevance(profile, topic)
            scored.append((profile, metadata))

        # Sort by relevance score (highest first)
        scored.sort(key=lambda x: x[1].relevance_score, reverse=True)

        # Apply selection mode
        if mode == SelectionMode.ALL:
            selected = scored
        elif mode == SelectionMode.RELEVANT:
            selected = [
                (p, m) for p, m in scored if m.relevance_score >= relevance_threshold
            ]
        elif mode == SelectionMode.WEIGHTED:
            # All archons but sorted by relevance
            selected = scored
        else:
            raise ValueError(f"Unknown selection mode: {mode}")

        # Ensure executive inclusion if requested
        executives_included = False
        if include_executive:
            # Check if any executive is already in selection
            for profile, _ in selected:
                if profile.is_executive:
                    executives_included = True
                    break

            if not executives_included:
                # Add highest-scoring executive
                executives = self.get_executives()
                if executives:
                    # Score executives and pick the best one
                    exec_scored = [
                        (e, self.calculate_relevance(e, topic)) for e in executives
                    ]
                    exec_scored.sort(key=lambda x: x[1].relevance_score, reverse=True)
                    best_exec = exec_scored[0]

                    # Insert at appropriate position based on score
                    inserted = False
                    for i, (_, m) in enumerate(selected):
                        if best_exec[1].relevance_score >= m.relevance_score:
                            selected.insert(i, best_exec)
                            inserted = True
                            break
                    if not inserted:
                        selected.append(best_exec)

                    executives_included = True

        # Apply min/max constraints
        if len(selected) < min_archons:
            # Not enough archons - this is okay, return what we have
            logger.warning(
                "insufficient_archons_selected",
                selected_count=len(selected),
                min_requested=min_archons,
                mode=mode.value,
                topic_id=topic.topic_id,
            )

        if len(selected) > max_archons:
            selected = selected[:max_archons]

        # Extract parallel lists
        archons = [p for p, _ in selected]
        metadata = [m for _, m in selected]

        logger.info(
            "archon_selection_complete",
            topic_id=topic.topic_id,
            mode=mode.value,
            selected_count=len(archons),
            total_candidates=total_candidates,
            min_requested=min_archons,
            max_requested=max_archons,
            include_executive=include_executive,
            executives_included=executives_included,
        )

        return ArchonSelection(
            archons=archons,
            metadata=metadata,
            mode=mode,
            selected_at=datetime.now(timezone.utc),
            total_candidates=total_candidates,
            min_requested=min_archons,
            max_requested=max_archons,
            include_executive=include_executive,
        )

    def calculate_relevance(
        self,
        profile: ArchonProfile,
        topic: TopicContext,
    ) -> ArchonSelectionMetadata:
        """Calculate relevance score for an archon against a topic.

        Scores based on:
        - Tool matches (highest weight: 0.4 per tool)
        - Domain match (medium weight: 0.25)
        - Focus area matches (medium weight: 0.15 per keyword)
        - Capability matches (lower weight: 0.1 per capability)

        Args:
            profile: The archon profile to score
            topic: The topic context to match against

        Returns:
            ArchonSelectionMetadata with score and match details
        """
        score = 0.0
        matched_tools: list[str] = []
        matched_domain = False
        matched_focus_keywords: list[str] = []
        matched_capabilities: list[str] = []

        # Tool match (highest weight - explicit capability)
        for tool in topic.required_tools:
            if tool in profile.suggested_tools:
                score += TOOL_MATCH_WEIGHT
                matched_tools.append(tool)

        # Domain match (medium weight)
        if profile.domain and topic.domain_hint:
            profile_domain = profile.domain.lower()
            topic_domain = topic.domain_hint.lower()
            if profile_domain in topic_domain or topic_domain in profile_domain:
                score += DOMAIN_MATCH_WEIGHT
                matched_domain = True

        # Focus area match (medium weight per keyword)
        if profile.focus_areas and topic.keywords:
            profile_focus = profile.focus_areas.lower()
            for keyword in topic.keywords:
                if keyword.lower() in profile_focus:
                    score += FOCUS_AREA_MATCH_WEIGHT
                    matched_focus_keywords.append(keyword)

        # Capability match (lower weight per capability)
        if profile.capabilities and topic.required_capabilities:
            profile_caps = profile.capabilities.lower()
            for cap in topic.required_capabilities:
                if cap.lower() in profile_caps:
                    score += CAPABILITY_MATCH_WEIGHT
                    matched_capabilities.append(cap)

        # Cap score at 1.0
        score = min(score, 1.0)

        return ArchonSelectionMetadata(
            archon_id=profile.id,
            archon_name=profile.name,
            relevance_score=score,
            matched_tools=matched_tools,
            matched_domain=matched_domain,
            matched_focus_keywords=matched_focus_keywords,
            matched_capabilities=matched_capabilities,
        )

    def get_executives(self) -> list[ArchonProfile]:
        """Get all executive director (King-rank) archons.

        Returns:
            List of executive director ArchonProfiles
        """
        return self._profile_repo.get_executives()


def create_archon_selector(
    profile_repository: ArchonProfileRepository | None = None,
) -> ArchonSelectorAdapter:
    """Factory function to create an ArchonSelectorAdapter.

    Args:
        profile_repository: Optional profile repository.
            If not provided, creates one with default paths.

    Returns:
        Configured ArchonSelectorAdapter instance
    """
    if profile_repository is None:
        from src.infrastructure.adapters.config.archon_profile_adapter import (
            create_archon_profile_repository,
        )

        profile_repository = create_archon_profile_repository()

    return ArchonSelectorAdapter(profile_repository=profile_repository)
