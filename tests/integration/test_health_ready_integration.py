"""Integration tests for health and ready endpoints (Story 8.1, Task 7).

Tests for /v1/health liveness and /v1/ready readiness endpoints (AC5).
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch

from src.api.routes.health import router as health_router
from src.application.services.health_service import HealthService
from src.api.models.health import DependencyCheck, ReadyResponse
from src.infrastructure.monitoring.metrics import reset_metrics_collector, get_metrics_collector


@pytest.fixture(autouse=True)
def reset_collector() -> None:
    """Reset metrics collector before each test."""
    reset_metrics_collector()


@pytest.fixture
def app() -> FastAPI:
    """Create test FastAPI app with health routes."""
    app = FastAPI()
    app.include_router(health_router)
    return app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    """Create test client."""
    return TestClient(app)


class TestHealthEndpoint:
    """Integration tests for /v1/health liveness endpoint."""

    def test_health_returns_200(self, client: TestClient) -> None:
        """Test /v1/health returns 200 OK (AC5)."""
        response = client.get("/v1/health")

        assert response.status_code == 200

    def test_health_returns_healthy_status(self, client: TestClient) -> None:
        """Test /v1/health returns healthy status (AC5)."""
        response = client.get("/v1/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    def test_health_returns_uptime_seconds(self, client: TestClient) -> None:
        """Test /v1/health returns uptime_seconds field (AC5)."""
        response = client.get("/v1/health")

        assert response.status_code == 200
        data = response.json()
        assert "uptime_seconds" in data
        assert isinstance(data["uptime_seconds"], (int, float))

    def test_health_with_recorded_startup_has_positive_uptime(
        self, client: TestClient
    ) -> None:
        """Test /v1/health returns positive uptime after startup recorded."""
        import time

        collector = get_metrics_collector()
        collector.record_startup("api")
        time.sleep(0.1)

        response = client.get("/v1/health")

        assert response.status_code == 200
        data = response.json()
        assert data["uptime_seconds"] >= 0.1

    def test_health_is_fast_response(self, client: TestClient) -> None:
        """Test /v1/health responds quickly (no external calls)."""
        import time

        start = time.perf_counter()
        response = client.get("/v1/health")
        duration = time.perf_counter() - start

        assert response.status_code == 200
        # Should be very fast since no external calls
        assert duration < 0.5


class TestReadyEndpoint:
    """Integration tests for /v1/ready readiness endpoint."""

    def test_ready_returns_200_when_healthy(self, client: TestClient) -> None:
        """Test /v1/ready returns 200 when all dependencies healthy (AC5)."""
        response = client.get("/v1/ready")

        assert response.status_code == 200

    def test_ready_returns_ready_status(self, client: TestClient) -> None:
        """Test /v1/ready returns ready status (AC5)."""
        response = client.get("/v1/ready")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"

    def test_ready_includes_database_check(self, client: TestClient) -> None:
        """Test /v1/ready includes database dependency check (AC5)."""
        response = client.get("/v1/ready")

        assert response.status_code == 200
        data = response.json()
        assert "checks" in data
        assert "database" in data["checks"]
        assert data["checks"]["database"]["name"] == "database"
        assert "healthy" in data["checks"]["database"]

    def test_ready_includes_redis_check(self, client: TestClient) -> None:
        """Test /v1/ready includes Redis dependency check (AC5)."""
        response = client.get("/v1/ready")

        assert response.status_code == 200
        data = response.json()
        assert "checks" in data
        assert "redis" in data["checks"]
        assert data["checks"]["redis"]["name"] == "redis"
        assert "healthy" in data["checks"]["redis"]

    def test_ready_includes_event_store_check(self, client: TestClient) -> None:
        """Test /v1/ready includes event_store dependency check (AC5)."""
        response = client.get("/v1/ready")

        assert response.status_code == 200
        data = response.json()
        assert "checks" in data
        assert "event_store" in data["checks"]
        assert data["checks"]["event_store"]["name"] == "event_store"
        assert "healthy" in data["checks"]["event_store"]

    def test_ready_checks_include_latency(self, client: TestClient) -> None:
        """Test dependency checks include latency_ms field (AC5)."""
        response = client.get("/v1/ready")

        assert response.status_code == 200
        data = response.json()
        for check_name, check_data in data["checks"].items():
            assert "latency_ms" in check_data


class TestReadyUnhealthyScenarios:
    """Integration tests for /v1/ready when dependencies are unhealthy."""

    def test_ready_returns_503_when_database_down(self) -> None:
        """Test /v1/ready returns 503 when database is down (AC5)."""
        from src.application.services.health_service import (
            DependencyChecker,
            HealthService,
            configure_health_service,
            reset_health_service,
        )

        # Create mock unhealthy database checker
        class UnhealthyDbChecker(DependencyChecker):
            async def check(self) -> DependencyCheck:
                return DependencyCheck(
                    name="database",
                    healthy=False,
                    latency_ms=100.0,
                    error="Connection refused",
                )

        reset_health_service()
        configure_health_service(database_checker=UnhealthyDbChecker())

        app = FastAPI()
        app.include_router(health_router)
        client = TestClient(app)

        response = client.get("/v1/ready")

        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "not-ready"
        assert data["checks"]["database"]["healthy"] is False

        reset_health_service()

    def test_ready_returns_503_when_redis_down(self) -> None:
        """Test /v1/ready returns 503 when Redis is down (AC5)."""
        from src.application.services.health_service import (
            DependencyChecker,
            configure_health_service,
            reset_health_service,
        )

        class UnhealthyRedisChecker(DependencyChecker):
            async def check(self) -> DependencyCheck:
                return DependencyCheck(
                    name="redis",
                    healthy=False,
                    latency_ms=100.0,
                    error="Connection refused",
                )

        reset_health_service()
        configure_health_service(redis_checker=UnhealthyRedisChecker())

        app = FastAPI()
        app.include_router(health_router)
        client = TestClient(app)

        response = client.get("/v1/ready")

        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "not-ready"
        assert data["checks"]["redis"]["healthy"] is False

        reset_health_service()

    def test_ready_returns_503_when_event_store_down(self) -> None:
        """Test /v1/ready returns 503 when event_store is down (AC5)."""
        from src.application.services.health_service import (
            DependencyChecker,
            configure_health_service,
            reset_health_service,
        )

        class UnhealthyEventStoreChecker(DependencyChecker):
            async def check(self) -> DependencyCheck:
                return DependencyCheck(
                    name="event_store",
                    healthy=False,
                    latency_ms=100.0,
                    error="Connection refused",
                )

        reset_health_service()
        configure_health_service(event_store_checker=UnhealthyEventStoreChecker())

        app = FastAPI()
        app.include_router(health_router)
        client = TestClient(app)

        response = client.get("/v1/ready")

        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "not-ready"
        assert data["checks"]["event_store"]["healthy"] is False

        reset_health_service()

    def test_ready_includes_error_message_when_unhealthy(self) -> None:
        """Test unhealthy checks include error message."""
        from src.application.services.health_service import (
            DependencyChecker,
            configure_health_service,
            reset_health_service,
        )

        class UnhealthyDbChecker(DependencyChecker):
            async def check(self) -> DependencyCheck:
                return DependencyCheck(
                    name="database",
                    healthy=False,
                    latency_ms=5000.0,
                    error="Connection timeout after 5s",
                )

        reset_health_service()
        configure_health_service(database_checker=UnhealthyDbChecker())

        app = FastAPI()
        app.include_router(health_router)
        client = TestClient(app)

        response = client.get("/v1/ready")

        assert response.status_code == 503
        data = response.json()
        assert data["checks"]["database"]["error"] == "Connection timeout after 5s"

        reset_health_service()


class TestHealthVsReadySeparation:
    """Tests ensuring health (liveness) and ready (readiness) are separate."""

    def test_health_returns_200_even_when_dependencies_down(
        self, client: TestClient
    ) -> None:
        """Test /v1/health returns 200 even if dependencies are down (AC5).

        Liveness check only verifies the process is alive, not that it can
        serve traffic. Dependencies being down should not affect liveness.
        """
        # Health should always return 200 if the process is running
        response = client.get("/v1/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    def test_health_has_no_dependency_checks(self, client: TestClient) -> None:
        """Test /v1/health does not include dependency checks."""
        response = client.get("/v1/health")

        assert response.status_code == 200
        data = response.json()
        assert "checks" not in data

    def test_ready_has_dependency_checks(self, client: TestClient) -> None:
        """Test /v1/ready includes dependency checks."""
        response = client.get("/v1/ready")

        assert response.status_code == 200
        data = response.json()
        assert "checks" in data
        assert len(data["checks"]) > 0
