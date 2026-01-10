"""Unit tests for DissentHealthService (Story 2.4, FR12).

Tests the DissentHealthService for tracking and alerting on
dissent health metrics.

Test categories:
- DissentHealthStatus dataclass
- DissentAlert dataclass
- Service initialization
- record_dissent method
- get_health_status method
- check_alert_condition method
- HALT FIRST pattern compliance
"""

from datetime import datetime
from uuid import UUID, uuid4

import pytest

from src.application.ports.dissent_metrics import DissentRecord
from src.application.services.dissent_health_service import (
    DissentAlert,
    DissentHealthService,
    DissentHealthStatus,
)


class MockHaltChecker:
    """Mock HaltChecker for testing."""

    def __init__(self, is_halted: bool = False) -> None:
        self._is_halted = is_halted

    async def is_halted(self) -> bool:
        """Return whether the system is halted."""
        return self._is_halted

    async def get_halt_reason(self) -> str | None:
        """Return the halt reason if halted."""
        return "System is halted" if self._is_halted else None

    async def check_halted(self) -> None:
        if self._is_halted:
            from src.domain.errors.writer import SystemHaltedError
            raise SystemHaltedError("System is halted")


class MockDissentMetricsPort:
    """Mock DissentMetricsPort for testing."""

    def __init__(self) -> None:
        self.records: list[DissentRecord] = []
        self._rolling_average: float = 0.0
        self._is_below_threshold: bool = False

    async def record_vote_dissent(
        self,
        output_id: UUID,
        dissent_percentage: float,
        recorded_at: datetime,
    ) -> None:
        record = DissentRecord(
            output_id=output_id,
            dissent_percentage=dissent_percentage,
            recorded_at=recorded_at,
        )
        self.records.append(record)

    async def get_rolling_average(self, days: int = 30) -> float:
        return self._rolling_average

    async def get_dissent_history(self, days: int = 30) -> list[DissentRecord]:
        return self.records

    async def is_below_threshold(
        self,
        threshold: float = 10.0,
        days: int = 30,
    ) -> bool:
        return self._is_below_threshold


class TestDissentHealthStatus:
    """Tests for DissentHealthStatus dataclass."""

    def test_valid_healthy_status(self) -> None:
        """Valid healthy status is created successfully."""
        status = DissentHealthStatus(
            rolling_average=15.5,
            period_days=30,
            record_count=10,
            is_healthy=True,
        )

        assert status.rolling_average == 15.5
        assert status.period_days == 30
        assert status.record_count == 10
        assert status.is_healthy is True

    def test_valid_unhealthy_status(self) -> None:
        """Valid unhealthy status is created successfully."""
        status = DissentHealthStatus(
            rolling_average=5.0,
            period_days=30,
            record_count=10,
            is_healthy=False,
        )

        assert status.rolling_average == 5.0
        assert status.is_healthy is False


class TestDissentAlert:
    """Tests for DissentAlert dataclass."""

    def test_valid_alert(self) -> None:
        """Valid alert is created successfully."""
        alert = DissentAlert(
            threshold=10.0,
            actual_average=5.5,
            period_days=30,
            alert_type="DISSENT_BELOW_THRESHOLD",
        )

        assert alert.threshold == 10.0
        assert alert.actual_average == 5.5
        assert alert.period_days == 30
        assert alert.alert_type == "DISSENT_BELOW_THRESHOLD"


class TestDissentHealthService:
    """Tests for DissentHealthService."""

    @pytest.fixture
    def halt_checker(self) -> MockHaltChecker:
        return MockHaltChecker(is_halted=False)

    @pytest.fixture
    def metrics_port(self) -> MockDissentMetricsPort:
        return MockDissentMetricsPort()

    @pytest.fixture
    def service(
        self,
        halt_checker: MockHaltChecker,
        metrics_port: MockDissentMetricsPort,
    ) -> DissentHealthService:
        return DissentHealthService(
            halt_checker=halt_checker,  # type: ignore[arg-type]
            metrics_port=metrics_port,  # type: ignore[arg-type]
        )

    @pytest.mark.asyncio
    async def test_record_dissent_success(
        self,
        service: DissentHealthService,
        metrics_port: MockDissentMetricsPort,
    ) -> None:
        """record_dissent successfully records dissent metric."""
        output_id = uuid4()

        await service.record_dissent(output_id, 15.5)

        assert len(metrics_port.records) == 1
        assert metrics_port.records[0].output_id == output_id
        assert metrics_port.records[0].dissent_percentage == 15.5

    @pytest.mark.asyncio
    async def test_record_dissent_halt_first(
        self,
        metrics_port: MockDissentMetricsPort,
    ) -> None:
        """record_dissent checks halt state first (Golden Rule #1)."""
        halted_checker = MockHaltChecker(is_halted=True)
        service = DissentHealthService(
            halt_checker=halted_checker,  # type: ignore[arg-type]
            metrics_port=metrics_port,  # type: ignore[arg-type]
        )

        from src.domain.errors.writer import SystemHaltedError
        with pytest.raises(SystemHaltedError):
            await service.record_dissent(uuid4(), 15.5)

        # Verify metric was NOT recorded
        assert len(metrics_port.records) == 0

    @pytest.mark.asyncio
    async def test_get_health_status_healthy(
        self,
        service: DissentHealthService,
        metrics_port: MockDissentMetricsPort,
    ) -> None:
        """get_health_status returns healthy status when dissent > 10%."""
        metrics_port._rolling_average = 15.0
        metrics_port._is_below_threshold = False

        status = await service.get_health_status()

        assert status.rolling_average == 15.0
        assert status.is_healthy is True

    @pytest.mark.asyncio
    async def test_get_health_status_unhealthy(
        self,
        service: DissentHealthService,
        metrics_port: MockDissentMetricsPort,
    ) -> None:
        """get_health_status returns unhealthy status when dissent < 10%."""
        metrics_port._rolling_average = 5.0
        metrics_port._is_below_threshold = True

        status = await service.get_health_status()

        assert status.rolling_average == 5.0
        assert status.is_healthy is False

    @pytest.mark.asyncio
    async def test_check_alert_condition_no_alert(
        self,
        service: DissentHealthService,
        metrics_port: MockDissentMetricsPort,
    ) -> None:
        """check_alert_condition returns None when dissent is healthy."""
        metrics_port._rolling_average = 15.0
        metrics_port._is_below_threshold = False

        alert = await service.check_alert_condition()

        assert alert is None

    @pytest.mark.asyncio
    async def test_check_alert_condition_alert_triggered(
        self,
        service: DissentHealthService,
        metrics_port: MockDissentMetricsPort,
    ) -> None:
        """check_alert_condition returns alert when dissent is below threshold."""
        metrics_port._rolling_average = 5.0
        metrics_port._is_below_threshold = True

        alert = await service.check_alert_condition()

        assert alert is not None
        assert alert.threshold == 10.0
        assert alert.actual_average == 5.0
        assert alert.period_days == 30
        assert alert.alert_type == "DISSENT_BELOW_THRESHOLD"
