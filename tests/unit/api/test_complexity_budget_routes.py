"""Unit tests for complexity budget API routes (Story 8.6, AC5).

Tests the API endpoints for complexity budget dashboard and metrics.

Constitutional Constraints Tested:
- CT-14: Complexity is a failure vector
- RT-6: Breach = constitutional event
- SC-3: Complexity budget dashboard required
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.api.models.complexity_budget import (
    ComplexityBreachListResponse,
    ComplexityDashboardResponse,
    ComplexityTrendResponse,
)
from src.api.routes.complexity_budget import (
    get_dashboard,
    get_metrics,
    get_trends,
    list_breaches,
)
from src.domain.events.complexity_budget import ComplexityBudgetBreachedPayload
from src.domain.models.complexity_budget import (
    ADR_LIMIT,
    CEREMONY_TYPE_LIMIT,
    CROSS_COMPONENT_DEP_LIMIT,
    ComplexityBudgetStatus,
    ComplexityDimension,
    ComplexitySnapshot,
)


@pytest.fixture
def mock_complexity_service():
    """Create a mock complexity budget service."""
    service = AsyncMock()
    return service


@pytest.fixture
def mock_escalation_service():
    """Create a mock escalation service."""
    service = AsyncMock()
    service.get_pending_escalations_count.return_value = 0
    service.get_all_escalations.return_value = []
    return service


@pytest.fixture
def sample_snapshot():
    """Create a sample complexity snapshot."""
    return ComplexitySnapshot.create(
        adr_count=10,
        ceremony_types=5,
        cross_component_deps=15,
        triggered_by="test",
    )


@pytest.fixture
def sample_dashboard_data():
    """Create sample dashboard data dict."""
    return {
        "adr_count": 10,
        "adr_limit": ADR_LIMIT,
        "adr_utilization": 66.67,
        "adr_status": "within_budget",
        "ceremony_types": 5,
        "ceremony_type_limit": CEREMONY_TYPE_LIMIT,
        "ceremony_type_utilization": 50.0,
        "ceremony_type_status": "within_budget",
        "cross_component_deps": 15,
        "cross_component_dep_limit": CROSS_COMPONENT_DEP_LIMIT,
        "cross_component_dep_utilization": 75.0,
        "cross_component_dep_status": "within_budget",
        "overall_status": "within_budget",
        "active_breaches": 0,
        "last_updated": datetime.now(timezone.utc).isoformat(),
    }


class TestGetMetricsEndpoint:
    """Tests for GET /v1/complexity/metrics endpoint."""

    @pytest.mark.asyncio
    async def test_returns_all_dimensions(
        self, mock_complexity_service, sample_snapshot
    ):
        """Test that get_metrics returns all three dimensions."""
        mock_complexity_service.check_all_budgets.return_value = sample_snapshot

        result = await get_metrics(service=mock_complexity_service)

        assert len(result) == 3
        dimensions = [r.dimension for r in result]
        assert ComplexityDimension.ADR_COUNT.value in dimensions
        assert ComplexityDimension.CEREMONY_TYPES.value in dimensions
        assert ComplexityDimension.CROSS_COMPONENT_DEPS.value in dimensions

    @pytest.mark.asyncio
    async def test_returns_correct_adr_metrics(
        self, mock_complexity_service, sample_snapshot
    ):
        """Test ADR metrics are correctly populated."""
        mock_complexity_service.check_all_budgets.return_value = sample_snapshot

        result = await get_metrics(service=mock_complexity_service)

        adr_metric = next(
            r for r in result if r.dimension == ComplexityDimension.ADR_COUNT.value
        )
        assert adr_metric.current_value == 10
        assert adr_metric.limit == ADR_LIMIT
        assert adr_metric.status == ComplexityBudgetStatus.WITHIN_BUDGET.value

    @pytest.mark.asyncio
    async def test_returns_correct_ceremony_metrics(
        self, mock_complexity_service, sample_snapshot
    ):
        """Test ceremony type metrics are correctly populated."""
        mock_complexity_service.check_all_budgets.return_value = sample_snapshot

        result = await get_metrics(service=mock_complexity_service)

        ceremony_metric = next(
            r for r in result if r.dimension == ComplexityDimension.CEREMONY_TYPES.value
        )
        assert ceremony_metric.current_value == 5
        assert ceremony_metric.limit == CEREMONY_TYPE_LIMIT
        assert ceremony_metric.status == ComplexityBudgetStatus.WITHIN_BUDGET.value

    @pytest.mark.asyncio
    async def test_returns_correct_deps_metrics(
        self, mock_complexity_service, sample_snapshot
    ):
        """Test cross-component dependency metrics are correctly populated."""
        mock_complexity_service.check_all_budgets.return_value = sample_snapshot

        result = await get_metrics(service=mock_complexity_service)

        deps_metric = next(
            r
            for r in result
            if r.dimension == ComplexityDimension.CROSS_COMPONENT_DEPS.value
        )
        assert deps_metric.current_value == 15
        assert deps_metric.limit == CROSS_COMPONENT_DEP_LIMIT
        assert deps_metric.status == ComplexityBudgetStatus.WITHIN_BUDGET.value

    @pytest.mark.asyncio
    async def test_calculates_utilization_correctly(self, mock_complexity_service):
        """Test utilization percentages are calculated correctly."""
        snapshot = ComplexitySnapshot.create(
            adr_count=12,  # 80% of 15 = warning level
            ceremony_types=10,  # 100% of 10 = breached
            cross_component_deps=16,  # 80% of 20 = warning level
        )
        mock_complexity_service.check_all_budgets.return_value = snapshot

        result = await get_metrics(service=mock_complexity_service)

        adr_metric = next(
            r for r in result if r.dimension == ComplexityDimension.ADR_COUNT.value
        )
        assert adr_metric.utilization == pytest.approx(80.0, abs=0.1)
        assert adr_metric.status == ComplexityBudgetStatus.WARNING.value

        ceremony_metric = next(
            r for r in result if r.dimension == ComplexityDimension.CEREMONY_TYPES.value
        )
        assert ceremony_metric.utilization == pytest.approx(100.0, abs=0.1)
        assert ceremony_metric.status == ComplexityBudgetStatus.BREACHED.value


class TestGetDashboardEndpoint:
    """Tests for GET /v1/complexity/dashboard endpoint."""

    @pytest.mark.asyncio
    async def test_returns_dashboard_data(
        self, mock_complexity_service, mock_escalation_service, sample_dashboard_data
    ):
        """Test that get_dashboard returns all expected fields."""
        mock_complexity_service.get_dashboard_data.return_value = sample_dashboard_data

        result = await get_dashboard(
            service=mock_complexity_service,
            escalation_service=mock_escalation_service,
        )

        assert isinstance(result, ComplexityDashboardResponse)
        assert result.adr_count == 10
        assert result.ceremony_types == 5
        assert result.cross_component_deps == 15
        assert result.overall_status == "within_budget"
        assert result.active_breaches == 0
        assert result.pending_escalations == 0

    @pytest.mark.asyncio
    async def test_includes_pending_escalations(
        self, mock_complexity_service, mock_escalation_service, sample_dashboard_data
    ):
        """Test that pending escalations count is included."""
        mock_complexity_service.get_dashboard_data.return_value = sample_dashboard_data
        mock_escalation_service.get_pending_escalations_count.return_value = 3

        result = await get_dashboard(
            service=mock_complexity_service,
            escalation_service=mock_escalation_service,
        )

        assert result.pending_escalations == 3


class TestListBreachesEndpoint:
    """Tests for GET /v1/complexity/breaches endpoint."""

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_breaches(self, mock_complexity_service):
        """Test empty breach list when no breaches exist."""
        mock_complexity_service.get_all_breaches.return_value = []
        mock_complexity_service.get_unresolved_breaches.return_value = []

        result = await list_breaches(resolved=None, service=mock_complexity_service)

        assert isinstance(result, ComplexityBreachListResponse)
        assert result.total_count == 0
        assert result.unresolved_count == 0
        assert len(result.breaches) == 0

    @pytest.mark.asyncio
    async def test_returns_all_breaches_when_no_filter(self, mock_complexity_service):
        """Test all breaches returned when resolved filter is None."""
        breach1 = ComplexityBudgetBreachedPayload(
            breach_id=uuid4(),
            dimension=ComplexityDimension.ADR_COUNT,
            limit=15,
            actual_value=16,
            breached_at=datetime.now(timezone.utc),
        )
        breach2 = ComplexityBudgetBreachedPayload(
            breach_id=uuid4(),
            dimension=ComplexityDimension.CEREMONY_TYPES,
            limit=10,
            actual_value=11,
            breached_at=datetime.now(timezone.utc),
        )
        mock_complexity_service.get_all_breaches.return_value = [breach1, breach2]
        mock_complexity_service.get_unresolved_breaches.return_value = [breach1]

        result = await list_breaches(resolved=None, service=mock_complexity_service)

        assert result.total_count == 2
        assert result.unresolved_count == 1
        assert len(result.breaches) == 2

    @pytest.mark.asyncio
    async def test_filters_resolved_breaches(self, mock_complexity_service):
        """Test resolved=True returns only resolved breaches."""
        breach1 = ComplexityBudgetBreachedPayload(
            breach_id=uuid4(),
            dimension=ComplexityDimension.ADR_COUNT,
            limit=15,
            actual_value=16,
            breached_at=datetime.now(timezone.utc),
        )
        breach2 = ComplexityBudgetBreachedPayload(
            breach_id=uuid4(),
            dimension=ComplexityDimension.CEREMONY_TYPES,
            limit=10,
            actual_value=11,
            breached_at=datetime.now(timezone.utc),
        )
        mock_complexity_service.get_all_breaches.return_value = [breach1, breach2]
        # Only breach1 is unresolved, breach2 is resolved
        mock_complexity_service.get_unresolved_breaches.return_value = [breach1]

        result = await list_breaches(resolved=True, service=mock_complexity_service)

        assert len(result.breaches) == 1
        assert result.breaches[0].breach_id == str(breach2.breach_id)

    @pytest.mark.asyncio
    async def test_filters_unresolved_breaches(self, mock_complexity_service):
        """Test resolved=False returns only unresolved breaches."""
        breach1 = ComplexityBudgetBreachedPayload(
            breach_id=uuid4(),
            dimension=ComplexityDimension.ADR_COUNT,
            limit=15,
            actual_value=16,
            breached_at=datetime.now(timezone.utc),
        )
        breach2 = ComplexityBudgetBreachedPayload(
            breach_id=uuid4(),
            dimension=ComplexityDimension.CEREMONY_TYPES,
            limit=10,
            actual_value=11,
            breached_at=datetime.now(timezone.utc),
        )
        mock_complexity_service.get_all_breaches.return_value = [breach1, breach2]
        mock_complexity_service.get_unresolved_breaches.return_value = [breach1]

        result = await list_breaches(resolved=False, service=mock_complexity_service)

        assert len(result.breaches) == 1
        assert result.breaches[0].breach_id == str(breach1.breach_id)


class TestGetTrendsEndpoint:
    """Tests for GET /v1/complexity/trends endpoint."""

    @pytest.mark.asyncio
    async def test_returns_trend_data(
        self, mock_complexity_service, mock_escalation_service
    ):
        """Test get_trends returns trend response."""
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        end = datetime(2026, 1, 8, tzinfo=timezone.utc)

        mock_complexity_service.get_snapshots_in_range.return_value = []
        mock_complexity_service.get_all_breaches.return_value = []
        mock_escalation_service.get_all_escalations.return_value = []

        result = await get_trends(
            start_date=start,
            end_date=end,
            service=mock_complexity_service,
            escalation_service=mock_escalation_service,
        )

        assert isinstance(result, ComplexityTrendResponse)
        assert result.start_date == start
        assert result.end_date == end
        assert result.total_breaches == 0
        assert result.total_escalations == 0

    @pytest.mark.asyncio
    async def test_counts_breaches_in_range(
        self, mock_complexity_service, mock_escalation_service
    ):
        """Test breaches within date range are counted."""
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        end = datetime(2026, 1, 8, tzinfo=timezone.utc)

        breach_in_range = ComplexityBudgetBreachedPayload(
            breach_id=uuid4(),
            dimension=ComplexityDimension.ADR_COUNT,
            limit=15,
            actual_value=16,
            breached_at=datetime(2026, 1, 5, tzinfo=timezone.utc),
        )
        breach_outside_range = ComplexityBudgetBreachedPayload(
            breach_id=uuid4(),
            dimension=ComplexityDimension.CEREMONY_TYPES,
            limit=10,
            actual_value=11,
            breached_at=datetime(2026, 1, 15, tzinfo=timezone.utc),
        )

        mock_complexity_service.get_snapshots_in_range.return_value = []
        mock_complexity_service.get_all_breaches.return_value = [
            breach_in_range,
            breach_outside_range,
        ]
        mock_escalation_service.get_all_escalations.return_value = []

        result = await get_trends(
            start_date=start,
            end_date=end,
            service=mock_complexity_service,
            escalation_service=mock_escalation_service,
        )

        assert result.total_breaches == 1  # Only breach_in_range counted
