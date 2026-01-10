"""Unit tests for constitutional health API route (Story 8.10, AC5).

Tests the /health/constitutional endpoint response structure and behavior.

Constitutional Constraints:
- ADR-10: Constitutional health is a blocking gate
- AC5: Constitutional health API endpoint
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.routes.constitutional_health import router
from src.domain.errors import SystemHaltedError
from src.domain.models.constitutional_health import (
    ConstitutionalHealthSnapshot,
    ConstitutionalHealthStatus,
    MetricName,
)


@pytest.fixture
def app() -> FastAPI:
    """Create a FastAPI app with constitutional health router."""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    """Create a test client."""
    return TestClient(app)


@pytest.fixture
def mock_service() -> AsyncMock:
    """Create a mock constitutional health service."""
    mock = AsyncMock()
    return mock


@pytest.fixture
def healthy_snapshot() -> ConstitutionalHealthSnapshot:
    """Create a healthy constitutional health snapshot."""
    return ConstitutionalHealthSnapshot(
        breach_count=3,
        override_rate_daily=1,
        dissent_health_percent=15.0,
        witness_coverage=72,
        calculated_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def unhealthy_snapshot() -> ConstitutionalHealthSnapshot:
    """Create an unhealthy constitutional health snapshot."""
    return ConstitutionalHealthSnapshot(
        breach_count=12,  # Critical: > 10
        override_rate_daily=1,
        dissent_health_percent=15.0,
        witness_coverage=72,
        calculated_at=datetime.now(timezone.utc),
    )


class TestConstitutionalHealthEndpoint:
    """Test /health/constitutional endpoint (AC5)."""

    def test_returns_200_when_healthy(
        self,
        client: TestClient,
        mock_service: AsyncMock,
        healthy_snapshot: ConstitutionalHealthSnapshot,
    ) -> None:
        """Endpoint returns 200 when constitutional health is healthy."""
        mock_service.get_constitutional_health.return_value = healthy_snapshot

        with patch(
            "src.api.routes.constitutional_health.get_constitutional_health_service",
            return_value=mock_service,
        ):
            response = client.get("/health/constitutional")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    def test_returns_200_when_unhealthy(
        self,
        client: TestClient,
        mock_service: AsyncMock,
        unhealthy_snapshot: ConstitutionalHealthSnapshot,
    ) -> None:
        """Endpoint returns 200 even when unhealthy (status in body)."""
        mock_service.get_constitutional_health.return_value = unhealthy_snapshot

        with patch(
            "src.api.routes.constitutional_health.get_constitutional_health_service",
            return_value=mock_service,
        ):
            response = client.get("/health/constitutional")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "unhealthy"

    def test_returns_503_when_halted(
        self,
        client: TestClient,
        mock_service: AsyncMock,
    ) -> None:
        """Endpoint returns 503 when system is halted."""
        mock_service.get_constitutional_health.side_effect = SystemHaltedError(
            "System halted"
        )

        with patch(
            "src.api.routes.constitutional_health.get_constitutional_health_service",
            return_value=mock_service,
        ):
            response = client.get("/health/constitutional")

        assert response.status_code == 503

    def test_response_includes_all_metrics(
        self,
        client: TestClient,
        mock_service: AsyncMock,
        healthy_snapshot: ConstitutionalHealthSnapshot,
    ) -> None:
        """Response includes all constitutional metrics."""
        mock_service.get_constitutional_health.return_value = healthy_snapshot

        with patch(
            "src.api.routes.constitutional_health.get_constitutional_health_service",
            return_value=mock_service,
        ):
            response = client.get("/health/constitutional")

        data = response.json()
        metrics = data["metrics"]

        assert "breach_count" in metrics
        assert "override_rate" in metrics
        assert "dissent_health" in metrics
        assert "witness_coverage" in metrics

    def test_response_metric_structure(
        self,
        client: TestClient,
        mock_service: AsyncMock,
        healthy_snapshot: ConstitutionalHealthSnapshot,
    ) -> None:
        """Each metric has name, value, status, thresholds, and blocking flag."""
        mock_service.get_constitutional_health.return_value = healthy_snapshot

        with patch(
            "src.api.routes.constitutional_health.get_constitutional_health_service",
            return_value=mock_service,
        ):
            response = client.get("/health/constitutional")

        data = response.json()
        breach_metric = data["metrics"]["breach_count"]

        assert "name" in breach_metric
        assert "value" in breach_metric
        assert "status" in breach_metric
        assert "warning_threshold" in breach_metric
        assert "critical_threshold" in breach_metric
        assert "is_blocking" in breach_metric

    def test_response_includes_ceremonies_blocked(
        self,
        client: TestClient,
        mock_service: AsyncMock,
        unhealthy_snapshot: ConstitutionalHealthSnapshot,
    ) -> None:
        """Response includes ceremonies_blocked flag."""
        mock_service.get_constitutional_health.return_value = unhealthy_snapshot

        with patch(
            "src.api.routes.constitutional_health.get_constitutional_health_service",
            return_value=mock_service,
        ):
            response = client.get("/health/constitutional")

        data = response.json()
        assert "ceremonies_blocked" in data
        assert data["ceremonies_blocked"] is True

    def test_response_includes_blocking_reasons(
        self,
        client: TestClient,
        mock_service: AsyncMock,
        unhealthy_snapshot: ConstitutionalHealthSnapshot,
    ) -> None:
        """Response includes blocking_reasons list."""
        mock_service.get_constitutional_health.return_value = unhealthy_snapshot

        with patch(
            "src.api.routes.constitutional_health.get_constitutional_health_service",
            return_value=mock_service,
        ):
            response = client.get("/health/constitutional")

        data = response.json()
        assert "blocking_reasons" in data
        assert isinstance(data["blocking_reasons"], list)

    def test_response_includes_checked_at(
        self,
        client: TestClient,
        mock_service: AsyncMock,
        healthy_snapshot: ConstitutionalHealthSnapshot,
    ) -> None:
        """Response includes checked_at timestamp."""
        mock_service.get_constitutional_health.return_value = healthy_snapshot

        with patch(
            "src.api.routes.constitutional_health.get_constitutional_health_service",
            return_value=mock_service,
        ):
            response = client.get("/health/constitutional")

        data = response.json()
        assert "checked_at" in data


class TestCeremoniesAllowedEndpoint:
    """Test /health/constitutional/ceremonies-allowed endpoint."""

    def test_returns_true_when_healthy(
        self,
        client: TestClient,
        mock_service: AsyncMock,
        healthy_snapshot: ConstitutionalHealthSnapshot,
    ) -> None:
        """Returns True when ceremonies are allowed."""
        mock_service.get_constitutional_health.return_value = healthy_snapshot

        with patch(
            "src.api.routes.constitutional_health.get_constitutional_health_service",
            return_value=mock_service,
        ):
            response = client.get("/health/constitutional/ceremonies-allowed")

        assert response.status_code == 200
        assert response.json() is True

    def test_returns_false_when_unhealthy(
        self,
        client: TestClient,
        mock_service: AsyncMock,
        unhealthy_snapshot: ConstitutionalHealthSnapshot,
    ) -> None:
        """Returns False when ceremonies are blocked."""
        mock_service.get_constitutional_health.return_value = unhealthy_snapshot

        with patch(
            "src.api.routes.constitutional_health.get_constitutional_health_service",
            return_value=mock_service,
        ):
            response = client.get("/health/constitutional/ceremonies-allowed")

        assert response.status_code == 200
        assert response.json() is False

    def test_returns_503_when_halted(
        self,
        client: TestClient,
        mock_service: AsyncMock,
    ) -> None:
        """Returns 503 when system is halted."""
        mock_service.get_constitutional_health.side_effect = SystemHaltedError(
            "System halted"
        )

        with patch(
            "src.api.routes.constitutional_health.get_constitutional_health_service",
            return_value=mock_service,
        ):
            response = client.get("/health/constitutional/ceremonies-allowed")

        assert response.status_code == 503
