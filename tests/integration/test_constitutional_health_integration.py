"""Integration tests for constitutional health (Story 8.10, ADR-10).

Tests the constitutional health endpoint through the full API stack.

Constitutional Constraints:
- ADR-10: Constitutional health is a blocking gate
- AC1: Constitutional metrics distinct from operational
- AC2: Routes to governance, not ops
- AC4: Ceremonies blocked when UNHEALTHY
- AC5: Constitutional health API endpoint

Integration Focus:
- Tests end-to-end API behavior
- Verifies response structure matches spec
- Confirms separation from operational health
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.routes.constitutional_health import router
from src.domain.errors import SystemHaltedError
from src.domain.models.constitutional_health import (
    ConstitutionalHealthSnapshot,
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
    return AsyncMock()


@pytest.fixture
def healthy_snapshot() -> ConstitutionalHealthSnapshot:
    """Create a healthy constitutional health snapshot.

    All metrics within normal ranges:
    - breach_count: 3 (< 8 warning threshold)
    - override_rate_daily: 1 (< 3 incident threshold)
    - dissent_health_percent: 15.0 (> 10% warning threshold)
    - witness_coverage: 72 (> 12 degraded threshold)
    """
    return ConstitutionalHealthSnapshot(
        breach_count=3,
        override_rate_daily=1,
        dissent_health_percent=15.0,
        witness_coverage=72,
        calculated_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def warning_snapshot() -> ConstitutionalHealthSnapshot:
    """Create a warning constitutional health snapshot.

    breach_count at warning threshold (8).
    """
    return ConstitutionalHealthSnapshot(
        breach_count=8,  # Warning threshold
        override_rate_daily=1,
        dissent_health_percent=15.0,
        witness_coverage=72,
        calculated_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def unhealthy_snapshot() -> ConstitutionalHealthSnapshot:
    """Create an unhealthy constitutional health snapshot.

    breach_count exceeds critical threshold (> 10).
    """
    return ConstitutionalHealthSnapshot(
        breach_count=12,  # Critical: > 10
        override_rate_daily=1,
        dissent_health_percent=15.0,
        witness_coverage=72,
        calculated_at=datetime.now(timezone.utc),
    )


class TestConstitutionalHealthEndpointIntegration:
    """Integration tests for /health/constitutional endpoint (AC5)."""

    def test_healthy_response_structure(
        self,
        client: TestClient,
        mock_service: AsyncMock,
        healthy_snapshot: ConstitutionalHealthSnapshot,
    ) -> None:
        """Healthy response has complete structure per AC5."""
        mock_service.get_constitutional_health.return_value = healthy_snapshot

        with patch(
            "src.api.routes.constitutional_health.get_constitutional_health_service",
            return_value=mock_service,
        ):
            response = client.get("/health/constitutional")

        assert response.status_code == 200
        data = response.json()

        # Verify required fields
        assert data["status"] == "healthy"
        assert data["ceremonies_blocked"] is False
        assert data["blocking_reasons"] == []
        assert "metrics" in data
        assert "checked_at" in data
        assert data["health_type"] == "constitutional"

    def test_warning_response_structure(
        self,
        client: TestClient,
        mock_service: AsyncMock,
        warning_snapshot: ConstitutionalHealthSnapshot,
    ) -> None:
        """Warning response maintains ceremonies but indicates degradation."""
        mock_service.get_constitutional_health.return_value = warning_snapshot

        with patch(
            "src.api.routes.constitutional_health.get_constitutional_health_service",
            return_value=mock_service,
        ):
            response = client.get("/health/constitutional")

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "warning"
        assert data["ceremonies_blocked"] is False  # Warning doesn't block

    def test_unhealthy_blocks_ceremonies(
        self,
        client: TestClient,
        mock_service: AsyncMock,
        unhealthy_snapshot: ConstitutionalHealthSnapshot,
    ) -> None:
        """Unhealthy status blocks ceremonies per AC4."""
        mock_service.get_constitutional_health.return_value = unhealthy_snapshot

        with patch(
            "src.api.routes.constitutional_health.get_constitutional_health_service",
            return_value=mock_service,
        ):
            response = client.get("/health/constitutional")

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "unhealthy"
        assert data["ceremonies_blocked"] is True  # Per AC4
        assert len(data["blocking_reasons"]) > 0

    def test_all_constitutional_metrics_present(
        self,
        client: TestClient,
        mock_service: AsyncMock,
        healthy_snapshot: ConstitutionalHealthSnapshot,
    ) -> None:
        """Response includes all four constitutional metrics per AC1."""
        mock_service.get_constitutional_health.return_value = healthy_snapshot

        with patch(
            "src.api.routes.constitutional_health.get_constitutional_health_service",
            return_value=mock_service,
        ):
            response = client.get("/health/constitutional")

        data = response.json()
        metrics = data["metrics"]

        # All four constitutional metrics must be present (AC1)
        required_metrics = [
            "breach_count",
            "override_rate",
            "dissent_health",
            "witness_coverage",
        ]
        for metric_name in required_metrics:
            assert metric_name in metrics, f"Missing metric: {metric_name}"
            metric = metrics[metric_name]
            assert "name" in metric
            assert "value" in metric
            assert "status" in metric
            assert "warning_threshold" in metric
            assert "critical_threshold" in metric
            assert "is_blocking" in metric

    def test_metric_values_match_snapshot(
        self,
        client: TestClient,
        mock_service: AsyncMock,
        healthy_snapshot: ConstitutionalHealthSnapshot,
    ) -> None:
        """Metric values in response match domain snapshot."""
        mock_service.get_constitutional_health.return_value = healthy_snapshot

        with patch(
            "src.api.routes.constitutional_health.get_constitutional_health_service",
            return_value=mock_service,
        ):
            response = client.get("/health/constitutional")

        data = response.json()
        metrics = data["metrics"]

        assert metrics["breach_count"]["value"] == 3
        assert metrics["override_rate"]["value"] == 1
        assert metrics["dissent_health"]["value"] == 15.0
        assert metrics["witness_coverage"]["value"] == 72

    def test_halted_system_returns_503(
        self,
        client: TestClient,
        mock_service: AsyncMock,
    ) -> None:
        """Halted system returns 503 per CT-11 (halt check first)."""
        mock_service.get_constitutional_health.side_effect = SystemHaltedError(
            "System halted"
        )

        with patch(
            "src.api.routes.constitutional_health.get_constitutional_health_service",
            return_value=mock_service,
        ):
            response = client.get("/health/constitutional")

        assert response.status_code == 503
        assert "halted" in response.json()["detail"].lower()


class TestCeremoniesAllowedEndpointIntegration:
    """Integration tests for /health/constitutional/ceremonies-allowed endpoint."""

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

    def test_returns_true_when_warning(
        self,
        client: TestClient,
        mock_service: AsyncMock,
        warning_snapshot: ConstitutionalHealthSnapshot,
    ) -> None:
        """Returns True when status is WARNING (ceremonies not blocked)."""
        mock_service.get_constitutional_health.return_value = warning_snapshot

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
        """Returns False when ceremonies are blocked (AC4)."""
        mock_service.get_constitutional_health.return_value = unhealthy_snapshot

        with patch(
            "src.api.routes.constitutional_health.get_constitutional_health_service",
            return_value=mock_service,
        ):
            response = client.get("/health/constitutional/ceremonies-allowed")

        assert response.status_code == 200
        assert response.json() is False

    def test_halted_system_returns_503(
        self,
        client: TestClient,
        mock_service: AsyncMock,
    ) -> None:
        """Halted system returns 503."""
        mock_service.get_constitutional_health.side_effect = SystemHaltedError(
            "System halted"
        )

        with patch(
            "src.api.routes.constitutional_health.get_constitutional_health_service",
            return_value=mock_service,
        ):
            response = client.get("/health/constitutional/ceremonies-allowed")

        assert response.status_code == 503


class TestConstitutionalVsOperationalSeparation:
    """Integration tests for constitutional vs operational health separation (AC1, AC3)."""

    def test_constitutional_health_endpoint_exists(
        self,
        client: TestClient,
        mock_service: AsyncMock,
        healthy_snapshot: ConstitutionalHealthSnapshot,
    ) -> None:
        """Constitutional health endpoint is distinct from operational."""
        mock_service.get_constitutional_health.return_value = healthy_snapshot

        with patch(
            "src.api.routes.constitutional_health.get_constitutional_health_service",
            return_value=mock_service,
        ):
            response = client.get("/health/constitutional")

        assert response.status_code == 200
        # Operational health is at /health, constitutional at /health/constitutional
        assert "constitutional" in response.request.url.path

    def test_response_indicates_constitutional_type(
        self,
        client: TestClient,
        mock_service: AsyncMock,
        healthy_snapshot: ConstitutionalHealthSnapshot,
    ) -> None:
        """Response clearly indicates this is constitutional (not operational) health."""
        mock_service.get_constitutional_health.return_value = healthy_snapshot

        with patch(
            "src.api.routes.constitutional_health.get_constitutional_health_service",
            return_value=mock_service,
        ):
            response = client.get("/health/constitutional")

        data = response.json()
        assert data["health_type"] == "constitutional"

    def test_constitutional_metrics_only(
        self,
        client: TestClient,
        mock_service: AsyncMock,
        healthy_snapshot: ConstitutionalHealthSnapshot,
    ) -> None:
        """Response only includes constitutional metrics, not operational."""
        mock_service.get_constitutional_health.return_value = healthy_snapshot

        with patch(
            "src.api.routes.constitutional_health.get_constitutional_health_service",
            return_value=mock_service,
        ):
            response = client.get("/health/constitutional")

        data = response.json()
        metrics = data["metrics"]

        # Constitutional metrics only
        constitutional_metrics = {
            "breach_count",
            "override_rate",
            "dissent_health",
            "witness_coverage",
        }

        # No operational metrics should be present
        operational_metrics = {
            "database_health",
            "redis_health",
            "api_latency",
            "memory_usage",
            "cpu_usage",
        }

        for metric_name in metrics:
            assert metric_name in constitutional_metrics, (
                f"Non-constitutional metric found: {metric_name}"
            )
            assert metric_name not in operational_metrics


class TestConservativeAggregation:
    """Integration tests for worst-component-health rule (ADR-10)."""

    def test_single_warning_makes_overall_warning(
        self,
        client: TestClient,
        mock_service: AsyncMock,
    ) -> None:
        """One warning metric makes overall status WARNING."""
        # breach_count at warning threshold
        snapshot = ConstitutionalHealthSnapshot(
            breach_count=8,  # Warning
            override_rate_daily=1,  # Healthy
            dissent_health_percent=20.0,  # Healthy
            witness_coverage=72,  # Healthy
            calculated_at=datetime.now(timezone.utc),
        )
        mock_service.get_constitutional_health.return_value = snapshot

        with patch(
            "src.api.routes.constitutional_health.get_constitutional_health_service",
            return_value=mock_service,
        ):
            response = client.get("/health/constitutional")

        data = response.json()
        assert data["status"] == "warning"
        assert data["ceremonies_blocked"] is False

    def test_single_critical_makes_overall_unhealthy(
        self,
        client: TestClient,
        mock_service: AsyncMock,
    ) -> None:
        """One critical metric makes overall status UNHEALTHY."""
        # breach_count at critical threshold
        snapshot = ConstitutionalHealthSnapshot(
            breach_count=12,  # Critical
            override_rate_daily=1,  # Healthy
            dissent_health_percent=20.0,  # Healthy
            witness_coverage=72,  # Healthy
            calculated_at=datetime.now(timezone.utc),
        )
        mock_service.get_constitutional_health.return_value = snapshot

        with patch(
            "src.api.routes.constitutional_health.get_constitutional_health_service",
            return_value=mock_service,
        ):
            response = client.get("/health/constitutional")

        data = response.json()
        assert data["status"] == "unhealthy"
        assert data["ceremonies_blocked"] is True

    def test_multiple_critical_still_unhealthy(
        self,
        client: TestClient,
        mock_service: AsyncMock,
    ) -> None:
        """Multiple critical metrics still results in UNHEALTHY (not worse)."""
        # Multiple metrics at critical
        snapshot = ConstitutionalHealthSnapshot(
            breach_count=15,  # Critical
            override_rate_daily=10,  # Critical
            dissent_health_percent=3.0,  # Critical
            witness_coverage=4,  # Critical
            calculated_at=datetime.now(timezone.utc),
        )
        mock_service.get_constitutional_health.return_value = snapshot

        with patch(
            "src.api.routes.constitutional_health.get_constitutional_health_service",
            return_value=mock_service,
        ):
            response = client.get("/health/constitutional")

        data = response.json()
        assert data["status"] == "unhealthy"
        assert data["ceremonies_blocked"] is True
        # Should list all blocking reasons
        assert len(data["blocking_reasons"]) >= 1


class TestBlockingReasons:
    """Integration tests for blocking reasons in response."""

    def test_blocking_reasons_identify_metrics(
        self,
        client: TestClient,
        mock_service: AsyncMock,
        unhealthy_snapshot: ConstitutionalHealthSnapshot,
    ) -> None:
        """Blocking reasons identify which metrics caused the block."""
        mock_service.get_constitutional_health.return_value = unhealthy_snapshot

        with patch(
            "src.api.routes.constitutional_health.get_constitutional_health_service",
            return_value=mock_service,
        ):
            response = client.get("/health/constitutional")

        data = response.json()
        assert len(data["blocking_reasons"]) > 0

        # At least one reason should mention breach (the critical metric)
        reasons_text = " ".join(data["blocking_reasons"]).lower()
        assert "breach" in reasons_text

    def test_healthy_has_no_blocking_reasons(
        self,
        client: TestClient,
        mock_service: AsyncMock,
        healthy_snapshot: ConstitutionalHealthSnapshot,
    ) -> None:
        """Healthy status has empty blocking reasons."""
        mock_service.get_constitutional_health.return_value = healthy_snapshot

        with patch(
            "src.api.routes.constitutional_health.get_constitutional_health_service",
            return_value=mock_service,
        ):
            response = client.get("/health/constitutional")

        data = response.json()
        assert data["blocking_reasons"] == []

    def test_warning_has_no_blocking_reasons(
        self,
        client: TestClient,
        mock_service: AsyncMock,
        warning_snapshot: ConstitutionalHealthSnapshot,
    ) -> None:
        """Warning status has empty blocking reasons (not blocking)."""
        mock_service.get_constitutional_health.return_value = warning_snapshot

        with patch(
            "src.api.routes.constitutional_health.get_constitutional_health_service",
            return_value=mock_service,
        ):
            response = client.get("/health/constitutional")

        data = response.json()
        assert data["blocking_reasons"] == []
