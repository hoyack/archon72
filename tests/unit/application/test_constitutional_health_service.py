"""Unit tests for ConstitutionalHealthService (Story 8.10, ADR-10).

Tests constitutional health metrics collection, threshold detection,
ceremony blocking logic, and HALT CHECK FIRST pattern.

Constitutional Constraints:
- ADR-10: Constitutional health is a blocking gate
- AC1: Constitutional metrics visibility
- AC2: Constitutional health degradation alerts
- AC4: Ceremonies blocked when UNHEALTHY
- CT-11: HALT CHECK FIRST pattern
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.application.services.constitutional_health_service import (
    ConstitutionalHealthService,
)
from src.domain.errors import SystemHaltedError
from src.domain.models.constitutional_health import (
    ConstitutionalHealthStatus,
    MetricName,
)


@pytest.fixture
def mock_halt_checker() -> AsyncMock:
    """Create a mock halt checker that returns not halted."""
    mock = AsyncMock()
    mock.is_halted = AsyncMock(return_value=False)
    return mock


@pytest.fixture
def mock_breach_repository() -> AsyncMock:
    """Create a mock breach repository."""
    mock = AsyncMock()
    # The service calls count_unacknowledged_in_window
    mock.count_unacknowledged_in_window = AsyncMock(return_value=3)
    return mock


@pytest.fixture
def mock_override_trend_repository() -> AsyncMock:
    """Create a mock override trend repository."""
    mock = AsyncMock()
    # The service calls get_trend_data().daily_count
    trend_data = MagicMock()
    trend_data.daily_count = 1
    mock.get_trend_data = AsyncMock(return_value=trend_data)
    return mock


@pytest.fixture
def mock_dissent_metrics() -> AsyncMock:
    """Create a mock dissent metrics port."""
    mock = AsyncMock()
    mock.get_rolling_average = AsyncMock(return_value=15.0)
    return mock


@pytest.fixture
def mock_witness_pool_monitor() -> AsyncMock:
    """Create a mock witness pool monitor."""
    mock = AsyncMock()
    # The service calls check_pool_health().effective_count
    pool_status = MagicMock()
    pool_status.effective_count = 72
    mock.check_pool_health = AsyncMock(return_value=pool_status)
    return mock


@pytest.fixture
def service(
    mock_halt_checker: AsyncMock,
    mock_breach_repository: AsyncMock,
    mock_override_trend_repository: AsyncMock,
    mock_dissent_metrics: AsyncMock,
    mock_witness_pool_monitor: AsyncMock,
) -> ConstitutionalHealthService:
    """Create a ConstitutionalHealthService with mocked dependencies."""
    return ConstitutionalHealthService(
        halt_checker=mock_halt_checker,
        breach_repository=mock_breach_repository,
        override_trend_repository=mock_override_trend_repository,
        dissent_metrics=mock_dissent_metrics,
        witness_pool_monitor=mock_witness_pool_monitor,
    )


class TestHaltCheckFirst:
    """Test HALT CHECK FIRST pattern (CT-11)."""

    @pytest.mark.asyncio
    async def test_get_constitutional_health_raises_when_halted(
        self,
        service: ConstitutionalHealthService,
        mock_halt_checker: AsyncMock,
    ) -> None:
        """HALT CHECK FIRST: get_constitutional_health raises when halted."""
        mock_halt_checker.is_halted.return_value = True

        with pytest.raises(SystemHaltedError):
            await service.get_constitutional_health()

        mock_halt_checker.is_halted.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_breach_count_raises_when_halted(
        self,
        service: ConstitutionalHealthService,
        mock_halt_checker: AsyncMock,
    ) -> None:
        """HALT CHECK FIRST: get_breach_count raises when halted."""
        mock_halt_checker.is_halted.return_value = True

        with pytest.raises(SystemHaltedError):
            await service.get_breach_count()

    @pytest.mark.asyncio
    async def test_get_override_rate_raises_when_halted(
        self,
        service: ConstitutionalHealthService,
        mock_halt_checker: AsyncMock,
    ) -> None:
        """HALT CHECK FIRST: get_override_rate raises when halted."""
        mock_halt_checker.is_halted.return_value = True

        with pytest.raises(SystemHaltedError):
            await service.get_override_rate()

    @pytest.mark.asyncio
    async def test_get_dissent_health_raises_when_halted(
        self,
        service: ConstitutionalHealthService,
        mock_halt_checker: AsyncMock,
    ) -> None:
        """HALT CHECK FIRST: get_dissent_health raises when halted."""
        mock_halt_checker.is_halted.return_value = True

        with pytest.raises(SystemHaltedError):
            await service.get_dissent_health()

    @pytest.mark.asyncio
    async def test_get_witness_coverage_raises_when_halted(
        self,
        service: ConstitutionalHealthService,
        mock_halt_checker: AsyncMock,
    ) -> None:
        """HALT CHECK FIRST: get_witness_coverage raises when halted."""
        mock_halt_checker.is_halted.return_value = True

        with pytest.raises(SystemHaltedError):
            await service.get_witness_coverage()


class TestMetricCalculation:
    """Test individual metric calculations (AC1)."""

    @pytest.mark.asyncio
    async def test_get_breach_count_returns_value(
        self,
        service: ConstitutionalHealthService,
        mock_breach_repository: AsyncMock,
    ) -> None:
        """get_breach_count returns breach count from repository."""
        mock_breach_repository.count_unacknowledged_in_window.return_value = 5

        result = await service.get_breach_count()

        assert result == 5
        mock_breach_repository.count_unacknowledged_in_window.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_override_rate_returns_value(
        self,
        service: ConstitutionalHealthService,
        mock_override_trend_repository: AsyncMock,
    ) -> None:
        """get_override_rate returns daily rate from repository."""
        trend_data = MagicMock()
        trend_data.daily_count = 5
        mock_override_trend_repository.get_trend_data.return_value = trend_data

        result = await service.get_override_rate()

        assert result == 5
        mock_override_trend_repository.get_trend_data.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_dissent_health_returns_value(
        self,
        service: ConstitutionalHealthService,
        mock_dissent_metrics: AsyncMock,
    ) -> None:
        """get_dissent_health returns rolling average from metrics port."""
        mock_dissent_metrics.get_rolling_average.return_value = 12.5

        result = await service.get_dissent_health()

        assert result == 12.5
        mock_dissent_metrics.get_rolling_average.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_witness_coverage_returns_value(
        self,
        service: ConstitutionalHealthService,
        mock_witness_pool_monitor: AsyncMock,
    ) -> None:
        """get_witness_coverage returns pool size from monitor."""
        pool_status = MagicMock()
        pool_status.effective_count = 24
        mock_witness_pool_monitor.check_pool_health.return_value = pool_status

        result = await service.get_witness_coverage()

        assert result == 24
        mock_witness_pool_monitor.check_pool_health.assert_awaited_once()


class TestOverallHealthCalculation:
    """Test overall health status calculation (ADR-10 gap resolution)."""

    @pytest.mark.asyncio
    async def test_all_healthy_returns_healthy(
        self,
        service: ConstitutionalHealthService,
        mock_breach_repository: AsyncMock,
        mock_override_trend_repository: AsyncMock,
        mock_dissent_metrics: AsyncMock,
        mock_witness_pool_monitor: AsyncMock,
    ) -> None:
        """Overall status is HEALTHY when all metrics healthy."""
        # All metrics within healthy thresholds
        mock_breach_repository.count_unacknowledged_in_window.return_value = 3

        trend_data = MagicMock()
        trend_data.daily_count = 1
        mock_override_trend_repository.get_trend_data.return_value = trend_data

        mock_dissent_metrics.get_rolling_average.return_value = 15.0

        pool_status = MagicMock()
        pool_status.effective_count = 72
        mock_witness_pool_monitor.check_pool_health.return_value = pool_status

        result = await service.get_constitutional_health()

        assert result.overall_status == ConstitutionalHealthStatus.HEALTHY
        assert not result.ceremonies_blocked

    @pytest.mark.asyncio
    async def test_one_warning_returns_warning(
        self,
        service: ConstitutionalHealthService,
        mock_breach_repository: AsyncMock,
        mock_override_trend_repository: AsyncMock,
        mock_dissent_metrics: AsyncMock,
        mock_witness_pool_monitor: AsyncMock,
    ) -> None:
        """Overall status is WARNING when one metric at warning."""
        # Breach count at warning threshold (>=8)
        mock_breach_repository.count_unacknowledged_in_window.return_value = 9

        trend_data = MagicMock()
        trend_data.daily_count = 1
        mock_override_trend_repository.get_trend_data.return_value = trend_data

        mock_dissent_metrics.get_rolling_average.return_value = 15.0

        pool_status = MagicMock()
        pool_status.effective_count = 72
        mock_witness_pool_monitor.check_pool_health.return_value = pool_status

        result = await service.get_constitutional_health()

        assert result.overall_status == ConstitutionalHealthStatus.WARNING
        assert not result.ceremonies_blocked

    @pytest.mark.asyncio
    async def test_one_critical_returns_unhealthy(
        self,
        service: ConstitutionalHealthService,
        mock_breach_repository: AsyncMock,
        mock_override_trend_repository: AsyncMock,
        mock_dissent_metrics: AsyncMock,
        mock_witness_pool_monitor: AsyncMock,
    ) -> None:
        """Overall status is UNHEALTHY when one metric critical."""
        # Breach count at critical threshold (>10)
        mock_breach_repository.count_unacknowledged_in_window.return_value = 12

        trend_data = MagicMock()
        trend_data.daily_count = 1
        mock_override_trend_repository.get_trend_data.return_value = trend_data

        mock_dissent_metrics.get_rolling_average.return_value = 15.0

        pool_status = MagicMock()
        pool_status.effective_count = 72
        mock_witness_pool_monitor.check_pool_health.return_value = pool_status

        result = await service.get_constitutional_health()

        assert result.overall_status == ConstitutionalHealthStatus.UNHEALTHY
        assert result.ceremonies_blocked

    @pytest.mark.asyncio
    async def test_worst_component_health_rule(
        self,
        service: ConstitutionalHealthService,
        mock_breach_repository: AsyncMock,
        mock_override_trend_repository: AsyncMock,
        mock_dissent_metrics: AsyncMock,
        mock_witness_pool_monitor: AsyncMock,
    ) -> None:
        """System health = worst component health (conservative)."""
        # Multiple warnings but one critical
        mock_breach_repository.count_unacknowledged_in_window.return_value = (
            9  # WARNING
        )

        trend_data = MagicMock()
        trend_data.daily_count = 7  # CRITICAL (>6)
        mock_override_trend_repository.get_trend_data.return_value = trend_data

        mock_dissent_metrics.get_rolling_average.return_value = 8.0  # WARNING (<10)

        pool_status = MagicMock()
        pool_status.effective_count = 72  # HEALTHY
        mock_witness_pool_monitor.check_pool_health.return_value = pool_status

        result = await service.get_constitutional_health()

        # UNHEALTHY because override rate is critical
        assert result.overall_status == ConstitutionalHealthStatus.UNHEALTHY


class TestCeremonyBlocking:
    """Test ceremony blocking logic (AC4)."""

    @pytest.mark.asyncio
    async def test_ceremonies_blocked_when_unhealthy(
        self,
        service: ConstitutionalHealthService,
        mock_breach_repository: AsyncMock,
        mock_override_trend_repository: AsyncMock,
        mock_dissent_metrics: AsyncMock,
        mock_witness_pool_monitor: AsyncMock,
    ) -> None:
        """Ceremonies blocked when constitutional health is UNHEALTHY."""
        mock_breach_repository.count_unacknowledged_in_window.return_value = 12

        trend_data = MagicMock()
        trend_data.daily_count = 1
        mock_override_trend_repository.get_trend_data.return_value = trend_data

        mock_dissent_metrics.get_rolling_average.return_value = 15.0

        pool_status = MagicMock()
        pool_status.effective_count = 72
        mock_witness_pool_monitor.check_pool_health.return_value = pool_status

        result = await service.get_constitutional_health()

        assert result.ceremonies_blocked
        assert len(result.blocking_reasons) > 0

    @pytest.mark.asyncio
    async def test_ceremonies_allowed_when_healthy(
        self,
        service: ConstitutionalHealthService,
    ) -> None:
        """Ceremonies allowed when constitutional health is HEALTHY."""
        result = await service.get_constitutional_health()

        assert not result.ceremonies_blocked
        assert len(result.blocking_reasons) == 0

    @pytest.mark.asyncio
    async def test_ceremonies_allowed_when_warning(
        self,
        service: ConstitutionalHealthService,
        mock_breach_repository: AsyncMock,
        mock_override_trend_repository: AsyncMock,
        mock_dissent_metrics: AsyncMock,
        mock_witness_pool_monitor: AsyncMock,
    ) -> None:
        """Ceremonies allowed when constitutional health is WARNING."""
        mock_breach_repository.count_unacknowledged_in_window.return_value = 9

        trend_data = MagicMock()
        trend_data.daily_count = 1
        mock_override_trend_repository.get_trend_data.return_value = trend_data

        mock_dissent_metrics.get_rolling_average.return_value = 15.0

        pool_status = MagicMock()
        pool_status.effective_count = 72
        mock_witness_pool_monitor.check_pool_health.return_value = pool_status

        result = await service.get_constitutional_health()

        assert result.overall_status == ConstitutionalHealthStatus.WARNING
        assert not result.ceremonies_blocked

    @pytest.mark.asyncio
    async def test_blocking_reasons_list_metrics(
        self,
        service: ConstitutionalHealthService,
        mock_breach_repository: AsyncMock,
        mock_override_trend_repository: AsyncMock,
        mock_dissent_metrics: AsyncMock,
        mock_witness_pool_monitor: AsyncMock,
    ) -> None:
        """Blocking reasons list all critical metrics."""
        mock_breach_repository.count_unacknowledged_in_window.return_value = (
            12  # CRITICAL
        )

        trend_data = MagicMock()
        trend_data.daily_count = 7  # CRITICAL
        mock_override_trend_repository.get_trend_data.return_value = trend_data

        mock_dissent_metrics.get_rolling_average.return_value = 15.0

        pool_status = MagicMock()
        pool_status.effective_count = 72
        mock_witness_pool_monitor.check_pool_health.return_value = pool_status

        result = await service.get_constitutional_health()

        assert result.ceremonies_blocked
        # Should have reasons for both critical metrics
        assert len(result.blocking_reasons) == 2


class TestThresholdDetection:
    """Test threshold crossing detection (AC2)."""

    @pytest.mark.asyncio
    async def test_breach_warning_threshold(
        self,
        service: ConstitutionalHealthService,
        mock_breach_repository: AsyncMock,
        mock_override_trend_repository: AsyncMock,
        mock_dissent_metrics: AsyncMock,
        mock_witness_pool_monitor: AsyncMock,
    ) -> None:
        """Breach count at 8 triggers WARNING."""
        mock_breach_repository.count_unacknowledged_in_window.return_value = 8

        trend_data = MagicMock()
        trend_data.daily_count = 1
        mock_override_trend_repository.get_trend_data.return_value = trend_data

        mock_dissent_metrics.get_rolling_average.return_value = 15.0

        pool_status = MagicMock()
        pool_status.effective_count = 72
        mock_witness_pool_monitor.check_pool_health.return_value = pool_status

        result = await service.get_constitutional_health()

        # Find breach_count metric
        metrics = result.get_all_metrics()
        breach_metric = next(m for m in metrics if m.name == MetricName.BREACH_COUNT)
        assert breach_metric.status == ConstitutionalHealthStatus.WARNING

    @pytest.mark.asyncio
    async def test_breach_critical_threshold(
        self,
        service: ConstitutionalHealthService,
        mock_breach_repository: AsyncMock,
        mock_override_trend_repository: AsyncMock,
        mock_dissent_metrics: AsyncMock,
        mock_witness_pool_monitor: AsyncMock,
    ) -> None:
        """Breach count at >10 triggers UNHEALTHY."""
        mock_breach_repository.count_unacknowledged_in_window.return_value = 11

        trend_data = MagicMock()
        trend_data.daily_count = 1
        mock_override_trend_repository.get_trend_data.return_value = trend_data

        mock_dissent_metrics.get_rolling_average.return_value = 15.0

        pool_status = MagicMock()
        pool_status.effective_count = 72
        mock_witness_pool_monitor.check_pool_health.return_value = pool_status

        result = await service.get_constitutional_health()

        metrics = result.get_all_metrics()
        breach_metric = next(m for m in metrics if m.name == MetricName.BREACH_COUNT)
        assert breach_metric.status == ConstitutionalHealthStatus.UNHEALTHY

    @pytest.mark.asyncio
    async def test_override_incident_threshold(
        self,
        service: ConstitutionalHealthService,
        mock_breach_repository: AsyncMock,
        mock_override_trend_repository: AsyncMock,
        mock_dissent_metrics: AsyncMock,
        mock_witness_pool_monitor: AsyncMock,
    ) -> None:
        """Override rate >=3/day triggers WARNING."""
        mock_breach_repository.count_unacknowledged_in_window.return_value = 3

        trend_data = MagicMock()
        trend_data.daily_count = 4  # >= 3 triggers WARNING
        mock_override_trend_repository.get_trend_data.return_value = trend_data

        mock_dissent_metrics.get_rolling_average.return_value = 15.0

        pool_status = MagicMock()
        pool_status.effective_count = 72
        mock_witness_pool_monitor.check_pool_health.return_value = pool_status

        result = await service.get_constitutional_health()

        metrics = result.get_all_metrics()
        override_metric = next(m for m in metrics if m.name == MetricName.OVERRIDE_RATE)
        assert override_metric.status == ConstitutionalHealthStatus.WARNING

    @pytest.mark.asyncio
    async def test_dissent_warning_threshold(
        self,
        service: ConstitutionalHealthService,
        mock_breach_repository: AsyncMock,
        mock_override_trend_repository: AsyncMock,
        mock_dissent_metrics: AsyncMock,
        mock_witness_pool_monitor: AsyncMock,
    ) -> None:
        """Dissent health <=10% triggers WARNING."""
        mock_breach_repository.count_unacknowledged_in_window.return_value = 3

        trend_data = MagicMock()
        trend_data.daily_count = 1
        mock_override_trend_repository.get_trend_data.return_value = trend_data

        mock_dissent_metrics.get_rolling_average.return_value = (
            8.0  # <= 10 triggers WARNING
        )

        pool_status = MagicMock()
        pool_status.effective_count = 72
        mock_witness_pool_monitor.check_pool_health.return_value = pool_status

        result = await service.get_constitutional_health()

        metrics = result.get_all_metrics()
        dissent_metric = next(m for m in metrics if m.name == MetricName.DISSENT_HEALTH)
        assert dissent_metric.status == ConstitutionalHealthStatus.WARNING

    @pytest.mark.asyncio
    async def test_witness_degraded_threshold(
        self,
        service: ConstitutionalHealthService,
        mock_breach_repository: AsyncMock,
        mock_override_trend_repository: AsyncMock,
        mock_dissent_metrics: AsyncMock,
        mock_witness_pool_monitor: AsyncMock,
    ) -> None:
        """Witness coverage <=12 triggers WARNING."""
        mock_breach_repository.count_unacknowledged_in_window.return_value = 3

        trend_data = MagicMock()
        trend_data.daily_count = 1
        mock_override_trend_repository.get_trend_data.return_value = trend_data

        mock_dissent_metrics.get_rolling_average.return_value = 15.0

        pool_status = MagicMock()
        pool_status.effective_count = 10  # <= 12 triggers WARNING
        mock_witness_pool_monitor.check_pool_health.return_value = pool_status

        result = await service.get_constitutional_health()

        metrics = result.get_all_metrics()
        witness_metric = next(
            m for m in metrics if m.name == MetricName.WITNESS_COVERAGE
        )
        assert witness_metric.status == ConstitutionalHealthStatus.WARNING


class TestSnapshot:
    """Test snapshot properties."""

    @pytest.mark.asyncio
    async def test_snapshot_has_timestamp(
        self,
        service: ConstitutionalHealthService,
    ) -> None:
        """Snapshot includes calculated_at timestamp."""
        result = await service.get_constitutional_health()

        assert result.calculated_at is not None
        assert isinstance(result.calculated_at, datetime)

    @pytest.mark.asyncio
    async def test_snapshot_has_all_metrics(
        self,
        service: ConstitutionalHealthService,
    ) -> None:
        """Snapshot includes all four metrics."""
        result = await service.get_constitutional_health()

        metrics = result.get_all_metrics()
        metric_names = [m.name for m in metrics]

        assert MetricName.BREACH_COUNT in metric_names
        assert MetricName.OVERRIDE_RATE in metric_names
        assert MetricName.DISSENT_HEALTH in metric_names
        assert MetricName.WITNESS_COVERAGE in metric_names
