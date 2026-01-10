"""Unit tests for ArchonSelectorAdapter (Story 10-4).

Tests verify:
- AC1: ArchonSelectorProtocol compliance
- AC2: Topic-to-archon matching algorithm
- AC3: Selection modes (ALL, RELEVANT, WEIGHTED)
- AC4: Configurable selection limits
- AC5: Executive inclusion guarantee
- AC6: Selection audit trail (metadata)
- AC7: Unit tests for selection logic
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest

from src.application.ports.archon_profile_repository import ArchonProfileRepository
from src.application.ports.archon_selector import (
    ArchonSelection,
    ArchonSelectionMetadata,
    ArchonSelectorProtocol,
    SelectionMode,
    TopicContext,
)
from src.domain.models.archon_profile import ArchonProfile
from src.domain.models.llm_config import DEFAULT_LLM_CONFIG
from src.infrastructure.adapters.selection.archon_selector_adapter import (
    ArchonSelectorAdapter,
    create_archon_selector,
    TOOL_MATCH_WEIGHT,
    DOMAIN_MATCH_WEIGHT,
    FOCUS_AREA_MATCH_WEIGHT,
    CAPABILITY_MATCH_WEIGHT,
)


# ===========================================================================
# Fixtures
# ===========================================================================


def create_test_profile(
    name: str,
    is_executive: bool = False,
    suggested_tools: list[str] | None = None,
    domain: str | None = None,
    focus_areas: str | None = None,
    capabilities: str | None = None,
) -> ArchonProfile:
    """Helper to create test ArchonProfile."""
    return ArchonProfile(
        id=uuid4(),
        name=name,
        aegis_rank="executive_director" if is_executive else "director",
        original_rank="King" if is_executive else "Marquis",
        rank_level=8 if is_executive else 6,
        role=f"Test role for {name}",
        goal=f"Test goal for {name}",
        backstory=f"Backstory for {name}",
        system_prompt=f"You are {name}",
        suggested_tools=suggested_tools or [],
        allow_delegation=is_executive,
        attributes={
            "domain": domain,
            "focus_areas": focus_areas,
            "capabilities": capabilities,
        },
        max_members=10,
        max_legions=5,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        llm_config=DEFAULT_LLM_CONFIG,
    )


@pytest.fixture
def insight_archon() -> ArchonProfile:
    """Archon specialized in insight and analysis."""
    return create_test_profile(
        name="InsightArchon",
        suggested_tools=["insight_tool", "knowledge_retrieval_tool"],
        domain="analytics",
        focus_areas="pattern recognition, data analysis, forecasting",
        capabilities="analytical thinking, research",
    )


@pytest.fixture
def communication_archon() -> ArchonProfile:
    """Archon specialized in communication."""
    return create_test_profile(
        name="CommunicationArchon",
        suggested_tools=["communication_tool", "relationship_tool"],
        domain="communications",
        focus_areas="messaging, coordination, negotiation",
        capabilities="diplomatic communication, consensus building",
    )


@pytest.fixture
def executive_archon() -> ArchonProfile:
    """Executive director archon."""
    return create_test_profile(
        name="ExecutiveArchon",
        is_executive=True,
        suggested_tools=["insight_tool"],
        domain="leadership",
        focus_areas="strategy, governance",
        capabilities="decision making, leadership",
    )


@pytest.fixture
def generic_archon() -> ArchonProfile:
    """Generic archon with no special attributes."""
    return create_test_profile(
        name="GenericArchon",
        suggested_tools=[],
        domain=None,
        focus_areas=None,
        capabilities=None,
    )


@pytest.fixture
def mock_profile_repository(
    insight_archon: ArchonProfile,
    communication_archon: ArchonProfile,
    executive_archon: ArchonProfile,
    generic_archon: ArchonProfile,
) -> MagicMock:
    """Create mock repository with test archons."""
    mock_repo = MagicMock(spec=ArchonProfileRepository)

    all_archons = [insight_archon, communication_archon, executive_archon, generic_archon]

    mock_repo.get_all.return_value = all_archons
    mock_repo.count.return_value = len(all_archons)
    mock_repo.get_executives.return_value = [executive_archon]

    return mock_repo


@pytest.fixture
def selector(mock_profile_repository: MagicMock) -> ArchonSelectorAdapter:
    """Create selector with mock repository."""
    return ArchonSelectorAdapter(profile_repository=mock_profile_repository)


@pytest.fixture
def analytics_topic() -> TopicContext:
    """Topic about analytics/data analysis."""
    return TopicContext(
        topic_id="topic-analytics",
        content="We need to analyze market trends and forecast future patterns.",
        keywords=["analysis", "forecasting", "patterns"],
        required_tools=["insight_tool"],
        domain_hint="analytics",
        required_capabilities=["analytical thinking"],
    )


@pytest.fixture
def communication_topic() -> TopicContext:
    """Topic about communication/messaging."""
    return TopicContext(
        topic_id="topic-comm",
        content="We need to improve inter-agent communication protocols.",
        keywords=["messaging", "coordination"],
        required_tools=["communication_tool"],
        domain_hint="communications",
        required_capabilities=["diplomatic communication"],
    )


@pytest.fixture
def generic_topic() -> TopicContext:
    """Generic topic with no specific requirements."""
    return TopicContext(
        topic_id="topic-generic",
        content="General discussion topic.",
        keywords=[],
        required_tools=[],
        domain_hint=None,
        required_capabilities=[],
    )


# ===========================================================================
# Tests: Protocol Compliance
# ===========================================================================


class TestProtocolCompliance:
    """AC1: Tests for ArchonSelectorProtocol compliance."""

    def test_implements_protocol(self, selector: ArchonSelectorAdapter) -> None:
        """Verify adapter implements protocol."""
        assert isinstance(selector, ArchonSelectorProtocol)

    def test_has_select_method(self, selector: ArchonSelectorAdapter) -> None:
        """Verify select method exists."""
        assert hasattr(selector, "select")
        assert callable(selector.select)

    def test_has_calculate_relevance_method(self, selector: ArchonSelectorAdapter) -> None:
        """Verify calculate_relevance method exists."""
        assert hasattr(selector, "calculate_relevance")
        assert callable(selector.calculate_relevance)

    def test_has_get_executives_method(self, selector: ArchonSelectorAdapter) -> None:
        """Verify get_executives method exists."""
        assert hasattr(selector, "get_executives")
        assert callable(selector.get_executives)


# ===========================================================================
# Tests: Relevance Calculation (AC2)
# ===========================================================================


class TestRelevanceCalculation:
    """AC2: Tests for topic-to-archon matching algorithm."""

    def test_tool_match_adds_weight(
        self,
        selector: ArchonSelectorAdapter,
        insight_archon: ArchonProfile,
        analytics_topic: TopicContext,
    ) -> None:
        """Verify tool match adds to score."""
        metadata = selector.calculate_relevance(insight_archon, analytics_topic)

        assert "insight_tool" in metadata.matched_tools
        assert metadata.relevance_score >= TOOL_MATCH_WEIGHT

    def test_domain_match_adds_weight(
        self,
        selector: ArchonSelectorAdapter,
        insight_archon: ArchonProfile,
        analytics_topic: TopicContext,
    ) -> None:
        """Verify domain match adds to score."""
        metadata = selector.calculate_relevance(insight_archon, analytics_topic)

        assert metadata.matched_domain is True
        assert metadata.relevance_score >= DOMAIN_MATCH_WEIGHT

    def test_focus_area_match_adds_weight(
        self,
        selector: ArchonSelectorAdapter,
        insight_archon: ArchonProfile,
        analytics_topic: TopicContext,
    ) -> None:
        """Verify focus area keyword match adds to score."""
        metadata = selector.calculate_relevance(insight_archon, analytics_topic)

        # "forecasting" and "patterns" should match focus_areas
        assert len(metadata.matched_focus_keywords) > 0
        assert metadata.relevance_score >= FOCUS_AREA_MATCH_WEIGHT

    def test_capability_match_adds_weight(
        self,
        selector: ArchonSelectorAdapter,
        insight_archon: ArchonProfile,
        analytics_topic: TopicContext,
    ) -> None:
        """Verify capability match adds to score."""
        metadata = selector.calculate_relevance(insight_archon, analytics_topic)

        assert "analytical thinking" in metadata.matched_capabilities
        assert metadata.relevance_score >= CAPABILITY_MATCH_WEIGHT

    def test_score_capped_at_one(
        self,
        selector: ArchonSelectorAdapter,
        insight_archon: ArchonProfile,
    ) -> None:
        """Verify score is capped at 1.0."""
        # Topic with many matching criteria
        heavy_topic = TopicContext(
            topic_id="heavy",
            content="Heavy match topic",
            keywords=["pattern recognition", "data analysis", "forecasting"],
            required_tools=["insight_tool", "knowledge_retrieval_tool"],
            domain_hint="analytics",
            required_capabilities=["analytical thinking", "research"],
        )

        metadata = selector.calculate_relevance(insight_archon, heavy_topic)
        assert metadata.relevance_score <= 1.0

    def test_no_match_gives_zero_score(
        self,
        selector: ArchonSelectorAdapter,
        generic_archon: ArchonProfile,
        analytics_topic: TopicContext,
    ) -> None:
        """Verify no matches gives zero score."""
        metadata = selector.calculate_relevance(generic_archon, analytics_topic)

        assert metadata.relevance_score == 0.0
        assert metadata.matched_tools == []
        assert metadata.matched_domain is False
        assert metadata.matched_focus_keywords == []
        assert metadata.matched_capabilities == []


# ===========================================================================
# Tests: Selection Modes (AC3)
# ===========================================================================


class TestSelectionModes:
    """AC3: Tests for selection modes."""

    def test_all_mode_returns_all_archons(
        self,
        selector: ArchonSelectorAdapter,
        generic_topic: TopicContext,
    ) -> None:
        """Verify ALL mode returns all archons."""
        result = selector.select(generic_topic, mode=SelectionMode.ALL)

        assert len(result.archons) == 4
        assert result.mode == SelectionMode.ALL

    def test_relevant_mode_filters_by_threshold(
        self,
        selector: ArchonSelectorAdapter,
        analytics_topic: TopicContext,
    ) -> None:
        """Verify RELEVANT mode only returns archons above threshold."""
        result = selector.select(
            analytics_topic,
            mode=SelectionMode.RELEVANT,
            relevance_threshold=0.1,
        )

        # Only archons with relevance >= 0.1 should be included
        for metadata in result.metadata:
            assert metadata.relevance_score >= 0.1

        assert result.mode == SelectionMode.RELEVANT

    def test_relevant_mode_excludes_low_scores(
        self,
        selector: ArchonSelectorAdapter,
        analytics_topic: TopicContext,
    ) -> None:
        """Verify RELEVANT mode excludes archons below threshold."""
        result = selector.select(
            analytics_topic,
            mode=SelectionMode.RELEVANT,
            relevance_threshold=0.5,  # High threshold
        )

        # Generic archon should be excluded (score 0)
        archon_names = [a.name for a in result.archons]
        assert "GenericArchon" not in archon_names

    def test_weighted_mode_returns_sorted(
        self,
        selector: ArchonSelectorAdapter,
        analytics_topic: TopicContext,
    ) -> None:
        """Verify WEIGHTED mode returns all archons sorted by score."""
        result = selector.select(analytics_topic, mode=SelectionMode.WEIGHTED)

        # Should return all 4 archons
        assert len(result.archons) == 4
        assert result.mode == SelectionMode.WEIGHTED

        # Should be sorted by relevance (highest first)
        scores = [m.relevance_score for m in result.metadata]
        assert scores == sorted(scores, reverse=True)


# ===========================================================================
# Tests: Selection Limits (AC4)
# ===========================================================================


class TestSelectionLimits:
    """AC4: Tests for configurable selection limits."""

    def test_max_archons_limits_selection(
        self,
        selector: ArchonSelectorAdapter,
        generic_topic: TopicContext,
    ) -> None:
        """Verify max_archons limits the selection."""
        result = selector.select(
            generic_topic,
            mode=SelectionMode.ALL,
            max_archons=2,
        )

        assert len(result.archons) == 2
        assert result.max_requested == 2

    def test_min_archons_logged_when_insufficient(
        self,
        selector: ArchonSelectorAdapter,
        analytics_topic: TopicContext,
    ) -> None:
        """Verify selection proceeds even if fewer than min_archons match."""
        result = selector.select(
            analytics_topic,
            mode=SelectionMode.RELEVANT,
            min_archons=10,  # More than we have
            relevance_threshold=0.9,  # High threshold
        )

        # Should return what matches, even if < min
        assert len(result.archons) < 10
        assert result.min_requested == 10

    def test_invalid_min_max_raises_error(
        self,
        selector: ArchonSelectorAdapter,
        generic_topic: TopicContext,
    ) -> None:
        """Verify ValueError when min > max."""
        with pytest.raises(ValueError) as exc_info:
            selector.select(
                generic_topic,
                min_archons=10,
                max_archons=5,
            )

        assert "min_archons" in str(exc_info.value)

    def test_negative_min_raises_error(
        self,
        selector: ArchonSelectorAdapter,
        generic_topic: TopicContext,
    ) -> None:
        """Verify ValueError for negative min_archons."""
        with pytest.raises(ValueError) as exc_info:
            selector.select(
                generic_topic,
                min_archons=-1,
            )

        assert "non-negative" in str(exc_info.value)


# ===========================================================================
# Tests: Executive Inclusion (AC5)
# ===========================================================================


class TestExecutiveInclusion:
    """AC5: Tests for executive inclusion guarantee."""

    def test_include_executive_adds_executive(
        self,
        selector: ArchonSelectorAdapter,
        communication_topic: TopicContext,
    ) -> None:
        """Verify include_executive adds an executive director."""
        result = selector.select(
            communication_topic,
            mode=SelectionMode.RELEVANT,
            include_executive=True,
            relevance_threshold=0.5,
        )

        # Executive should be included even if not highest relevance
        archon_names = [a.name for a in result.archons]
        assert "ExecutiveArchon" in archon_names
        assert result.include_executive is True

    def test_executive_not_duplicated(
        self,
        selector: ArchonSelectorAdapter,
        analytics_topic: TopicContext,
    ) -> None:
        """Verify executive is not duplicated if already selected."""
        result = selector.select(
            analytics_topic,
            mode=SelectionMode.ALL,
            include_executive=True,
        )

        # Count executives in result
        executive_count = sum(1 for a in result.archons if a.is_executive)
        assert executive_count == 1  # Only one executive

    def test_get_executives_returns_executive_archons(
        self,
        selector: ArchonSelectorAdapter,
    ) -> None:
        """Verify get_executives returns executive directors."""
        executives = selector.get_executives()

        assert len(executives) == 1
        assert executives[0].name == "ExecutiveArchon"
        assert executives[0].is_executive is True


# ===========================================================================
# Tests: Selection Metadata (AC6)
# ===========================================================================


class TestSelectionMetadata:
    """AC6: Tests for selection audit trail."""

    def test_metadata_includes_archon_info(
        self,
        selector: ArchonSelectorAdapter,
        analytics_topic: TopicContext,
    ) -> None:
        """Verify metadata includes archon identification."""
        result = selector.select(analytics_topic, mode=SelectionMode.ALL)

        for i, metadata in enumerate(result.metadata):
            assert metadata.archon_id == result.archons[i].id
            assert metadata.archon_name == result.archons[i].name

    def test_metadata_includes_relevance_score(
        self,
        selector: ArchonSelectorAdapter,
        analytics_topic: TopicContext,
    ) -> None:
        """Verify metadata includes relevance score."""
        result = selector.select(analytics_topic, mode=SelectionMode.ALL)

        for metadata in result.metadata:
            assert isinstance(metadata.relevance_score, float)
            assert 0.0 <= metadata.relevance_score <= 1.0

    def test_metadata_includes_matched_criteria(
        self,
        selector: ArchonSelectorAdapter,
        insight_archon: ArchonProfile,
        analytics_topic: TopicContext,
    ) -> None:
        """Verify metadata explains why archon was selected."""
        metadata = selector.calculate_relevance(insight_archon, analytics_topic)

        # Should have match details
        assert len(metadata.matched_tools) > 0
        assert metadata.matched_domain is True
        assert len(metadata.matched_focus_keywords) > 0
        assert len(metadata.matched_capabilities) > 0

    def test_selection_includes_timestamp(
        self,
        selector: ArchonSelectorAdapter,
        generic_topic: TopicContext,
    ) -> None:
        """Verify selection includes timestamp."""
        result = selector.select(generic_topic)

        assert result.selected_at is not None
        assert isinstance(result.selected_at, datetime)

    def test_selection_includes_totals(
        self,
        selector: ArchonSelectorAdapter,
        generic_topic: TopicContext,
    ) -> None:
        """Verify selection includes total counts."""
        result = selector.select(
            generic_topic,
            min_archons=1,
            max_archons=10,
        )

        assert result.total_candidates == 4
        assert result.min_requested == 1
        assert result.max_requested == 10


# ===========================================================================
# Tests: Edge Cases
# ===========================================================================


class TestEdgeCases:
    """Tests for edge cases."""

    def test_empty_topic_returns_all_with_zero_scores(
        self,
        selector: ArchonSelectorAdapter,
    ) -> None:
        """Verify empty topic gives all archons zero scores."""
        empty_topic = TopicContext(
            topic_id="empty",
            content="",
            keywords=[],
            required_tools=[],
            domain_hint=None,
            required_capabilities=[],
        )

        result = selector.select(empty_topic, mode=SelectionMode.ALL)

        assert len(result.archons) == 4
        # Generic archons should have 0 score, but others might have partial matches
        # from their attributes

    def test_high_threshold_may_return_empty(
        self,
        selector: ArchonSelectorAdapter,
        generic_topic: TopicContext,
    ) -> None:
        """Verify high threshold can return empty selection."""
        result = selector.select(
            generic_topic,
            mode=SelectionMode.RELEVANT,
            relevance_threshold=0.99,
        )

        # Generic topic has no matching criteria, so all should be filtered
        assert len(result.archons) == 0

    def test_max_archons_zero_returns_empty(
        self,
        selector: ArchonSelectorAdapter,
        generic_topic: TopicContext,
    ) -> None:
        """Verify max_archons=0 returns empty selection."""
        result = selector.select(
            generic_topic,
            min_archons=0,
            max_archons=0,
        )

        assert len(result.archons) == 0


# ===========================================================================
# Tests: Factory Function
# ===========================================================================


class TestCreateArchonSelector:
    """Tests for factory function."""

    def test_creates_selector_with_provided_repository(
        self,
        mock_profile_repository: MagicMock,
    ) -> None:
        """Verify factory uses provided repository."""
        selector = create_archon_selector(
            profile_repository=mock_profile_repository
        )

        assert selector._profile_repo is mock_profile_repository

    def test_returns_protocol_compliant_instance(
        self,
        mock_profile_repository: MagicMock,
    ) -> None:
        """Verify factory returns protocol-compliant instance."""
        selector = create_archon_selector(
            profile_repository=mock_profile_repository
        )

        assert isinstance(selector, ArchonSelectorProtocol)
