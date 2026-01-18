"""Unit tests for health service (Story 8.1, Task 6).

Tests for liveness and readiness checks.
"""

import pytest

from src.api.models.health import DependencyCheck, HealthResponse, ReadyResponse
from src.application.dtos.health import (
    DependencyCheckDTO,
    HealthResponseDTO,
    ReadyResponseDTO,
)
from src.application.services.health_service import HealthService
from src.infrastructure.monitoring.metrics import reset_metrics_collector


@pytest.fixture(autouse=True)
def reset_collector() -> None:
    """Reset metrics collector before each test."""
    reset_metrics_collector()


class TestHealthService:
    """Tests for HealthService class."""

    @pytest.mark.asyncio
    async def test_check_liveness_returns_healthy(self) -> None:
        """Test liveness check returns healthy status."""
        service = HealthService()
        result = await service.check_liveness()

        assert isinstance(result, HealthResponseDTO)
        assert result.status == "healthy"

    @pytest.mark.asyncio
    async def test_check_liveness_returns_uptime(self) -> None:
        """Test liveness check returns uptime seconds."""
        service = HealthService()
        result = await service.check_liveness()

        assert isinstance(result.uptime_seconds, float)
        # Uptime should be 0 if service not registered
        assert result.uptime_seconds >= 0.0

    @pytest.mark.asyncio
    async def test_check_liveness_with_recorded_startup(self) -> None:
        """Test liveness check returns positive uptime after startup recorded."""
        import time

        from src.infrastructure.monitoring.metrics import get_metrics_collector

        collector = get_metrics_collector()
        collector.record_startup("api")
        time.sleep(0.1)

        # Must inject the metrics_collector for uptime tracking to work
        service = HealthService(metrics_collector=collector)
        result = await service.check_liveness()

        assert result.uptime_seconds >= 0.1

    @pytest.mark.asyncio
    async def test_check_readiness_returns_ready(self) -> None:
        """Test readiness check returns ready status with healthy deps."""
        service = HealthService()
        result = await service.check_readiness()

        assert isinstance(result, ReadyResponseDTO)
        assert result.status == "ready"

    @pytest.mark.asyncio
    async def test_check_readiness_includes_all_dependencies(self) -> None:
        """Test readiness check includes database, redis, event_store."""
        service = HealthService()
        result = await service.check_readiness()

        assert "database" in result.checks
        assert "redis" in result.checks
        assert "event_store" in result.checks

    @pytest.mark.asyncio
    async def test_check_readiness_dependency_checks_healthy(self) -> None:
        """Test all dependency checks return healthy."""
        service = HealthService()
        result = await service.check_readiness()

        for name, check in result.checks.items():
            assert isinstance(check, DependencyCheckDTO)
            assert check.name == name
            assert check.healthy is True
            assert check.latency_ms is not None
            assert check.error is None

    @pytest.mark.asyncio
    async def test_check_database_returns_dependency_check(self) -> None:
        """Test database check returns valid DependencyCheck."""
        service = HealthService()
        result = await service._check_database()

        assert isinstance(result, DependencyCheckDTO)
        assert result.name == "database"
        assert result.healthy is True

    @pytest.mark.asyncio
    async def test_check_redis_returns_dependency_check(self) -> None:
        """Test redis check returns valid DependencyCheck."""
        service = HealthService()
        result = await service._check_redis()

        assert isinstance(result, DependencyCheckDTO)
        assert result.name == "redis"
        assert result.healthy is True

    @pytest.mark.asyncio
    async def test_check_event_store_returns_dependency_check(self) -> None:
        """Test event store check returns valid DependencyCheck."""
        service = HealthService()
        result = await service._check_event_store()

        assert isinstance(result, DependencyCheckDTO)
        assert result.name == "event_store"
        assert result.healthy is True

    @pytest.mark.asyncio
    async def test_dependency_check_includes_latency(self) -> None:
        """Test dependency checks include latency measurement."""
        service = HealthService()
        result = await service._check_database()

        assert result.latency_ms is not None
        assert result.latency_ms >= 0.0

    def test_health_service_custom_service_name(self) -> None:
        """Test HealthService can be created with custom service name."""
        service = HealthService(service_name="custom-service")
        assert service._service_name == "custom-service"


class TestDependencyCheck:
    """Tests for DependencyCheck model."""

    def test_dependency_check_healthy(self) -> None:
        """Test creating healthy DependencyCheck."""
        check = DependencyCheck(
            name="test-dep",
            healthy=True,
            latency_ms=5.0,
        )

        assert check.name == "test-dep"
        assert check.healthy is True
        assert check.latency_ms == 5.0
        assert check.error is None

    def test_dependency_check_unhealthy(self) -> None:
        """Test creating unhealthy DependencyCheck with error."""
        check = DependencyCheck(
            name="test-dep",
            healthy=False,
            latency_ms=100.0,
            error="Connection refused",
        )

        assert check.name == "test-dep"
        assert check.healthy is False
        assert check.error == "Connection refused"


class TestReadyResponse:
    """Tests for ReadyResponse model."""

    def test_ready_response_ready(self) -> None:
        """Test creating ready response."""
        response = ReadyResponse(
            status="ready",
            checks={
                "database": DependencyCheck(name="database", healthy=True),
            },
        )

        assert response.status == "ready"
        assert "database" in response.checks

    def test_ready_response_not_ready(self) -> None:
        """Test creating not-ready response."""
        response = ReadyResponse(
            status="not-ready",
            checks={
                "database": DependencyCheck(
                    name="database", healthy=False, error="Timeout"
                ),
            },
        )

        assert response.status == "not-ready"
        assert response.checks["database"].healthy is False


class TestHealthResponse:
    """Tests for HealthResponse model."""

    def test_health_response_healthy(self) -> None:
        """Test creating healthy response."""
        response = HealthResponse(status="healthy", uptime_seconds=120.5)

        assert response.status == "healthy"
        assert response.uptime_seconds == 120.5

    def test_health_response_default_uptime(self) -> None:
        """Test HealthResponse defaults uptime to 0."""
        response = HealthResponse(status="healthy")

        assert response.uptime_seconds == 0.0
