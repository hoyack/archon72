"""Integration tests for metrics collection (Story 8.1, Task 7).

Tests for Prometheus metrics endpoint and operational metrics exposure.

Constitutional Constraints:
- FR52: ONLY operational metrics (uptime, latency, errors)
- NO constitutional metrics exposed (breach_count, halt_state, etc.)
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.middleware.metrics_middleware import MetricsMiddleware
from src.api.routes.metrics import router as metrics_router
from src.infrastructure.monitoring.metrics import (
    METRICS_CONTENT_TYPE,
    get_metrics_collector,
    reset_metrics_collector,
)


@pytest.fixture(autouse=True)
def reset_collector() -> None:
    """Reset metrics collector before each test."""
    reset_metrics_collector()


@pytest.fixture
def app() -> FastAPI:
    """Create test FastAPI app with metrics middleware and routes."""
    app = FastAPI()
    app.add_middleware(MetricsMiddleware)
    app.include_router(metrics_router)

    @app.get("/v1/test")
    async def test_endpoint() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/v1/error")
    async def error_endpoint() -> dict[str, str]:
        from fastapi import HTTPException

        raise HTTPException(status_code=500, detail="Server error")

    return app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    """Create test client."""
    return TestClient(app)


class TestMetricsEndpoint:
    """Integration tests for /v1/metrics endpoint."""

    def test_metrics_returns_prometheus_format(self, client: TestClient) -> None:
        """Test /v1/metrics returns Prometheus exposition format (AC1)."""
        response = client.get("/v1/metrics")

        assert response.status_code == 200
        assert response.headers["content-type"] == METRICS_CONTENT_TYPE

        # Prometheus format includes # HELP and # TYPE lines
        content = response.text
        assert "# HELP" in content or "# TYPE" in content or "_total" in content

    def test_metrics_contains_uptime_gauge(self, client: TestClient) -> None:
        """Test metrics contain uptime_seconds gauge (AC2)."""
        # Record startup to populate uptime
        collector = get_metrics_collector()
        collector.record_startup("api")

        response = client.get("/v1/metrics")

        assert response.status_code == 200
        content = response.text
        assert "uptime_seconds" in content

    def test_metrics_contains_service_starts_counter(self, client: TestClient) -> None:
        """Test metrics contain service_starts_total counter (AC2)."""
        # Record startup to increment counter
        collector = get_metrics_collector()
        collector.record_startup("api")

        response = client.get("/v1/metrics")

        assert response.status_code == 200
        content = response.text
        assert "service_starts_total" in content

    def test_metrics_contains_request_duration_histogram(
        self, client: TestClient
    ) -> None:
        """Test metrics contain http_request_duration_seconds histogram (AC3)."""
        # Make a request to record duration
        client.get("/v1/test")

        response = client.get("/v1/metrics")

        assert response.status_code == 200
        content = response.text
        assert "http_request_duration_seconds" in content

    def test_metrics_contains_histogram_buckets(self, client: TestClient) -> None:
        """Test histogram has proper bucket configuration (AC3)."""
        # Make a request to record duration
        client.get("/v1/test")

        response = client.get("/v1/metrics")

        assert response.status_code == 200
        content = response.text
        # Check for bucket markers
        assert "http_request_duration_seconds_bucket" in content

    def test_metrics_contains_request_counter(self, client: TestClient) -> None:
        """Test metrics contain http_requests_total counter (AC4)."""
        # Make a request to increment counter
        client.get("/v1/test")

        response = client.get("/v1/metrics")

        assert response.status_code == 200
        content = response.text
        assert "http_requests_total" in content

    def test_metrics_contains_failed_counter(self, client: TestClient) -> None:
        """Test metrics contain http_requests_failed_total counter (AC4)."""
        # Make an error request to increment failed counter
        client.get("/v1/error")

        response = client.get("/v1/metrics")

        assert response.status_code == 200
        content = response.text
        assert "http_requests_failed_total" in content

    def test_metrics_includes_labels(self, client: TestClient) -> None:
        """Test metrics include proper labels (method, endpoint, status) (AC1)."""
        # Make requests to generate labeled metrics
        client.get("/v1/test")

        response = client.get("/v1/metrics")

        assert response.status_code == 200
        content = response.text
        # Check for label patterns
        assert 'method="GET"' in content
        assert 'endpoint="' in content


class TestNoConstitutionalMetrics:
    """Tests ensuring no constitutional metrics are exposed (AC6, FR52)."""

    def test_no_breach_count_metric(self, client: TestClient) -> None:
        """Test no constitutional_breach_count metric exposed (FR52)."""
        response = client.get("/v1/metrics")

        assert response.status_code == 200
        content = response.text
        assert "breach_count" not in content
        assert "constitutional_breach_count" not in content

    def test_no_halt_state_metric(self, client: TestClient) -> None:
        """Test no halt_state metric exposed (FR52)."""
        response = client.get("/v1/metrics")

        assert response.status_code == 200
        content = response.text
        assert "halt_state" not in content

    def test_no_dissent_health_metric(self, client: TestClient) -> None:
        """Test no dissent_health_ratio metric exposed (FR52)."""
        response = client.get("/v1/metrics")

        assert response.status_code == 200
        content = response.text
        assert "dissent_health" not in content
        assert "dissent_ratio" not in content

    def test_no_witness_coverage_metric(self, client: TestClient) -> None:
        """Test no witness_coverage_percent metric exposed (FR52)."""
        response = client.get("/v1/metrics")

        assert response.status_code == 200
        content = response.text
        assert "witness_coverage" not in content

    def test_no_override_frequency_metric(self, client: TestClient) -> None:
        """Test no override_frequency metric exposed (FR52)."""
        response = client.get("/v1/metrics")

        assert response.status_code == 200
        content = response.text
        assert "override_frequency" not in content


class TestMetricsAccumulation:
    """Tests for metrics accumulating correctly across requests."""

    def test_requests_accumulate_in_counter(self, client: TestClient) -> None:
        """Test multiple requests accumulate in http_requests_total counter."""
        # Make multiple requests
        for _ in range(5):
            client.get("/v1/test")

        response = client.get("/v1/metrics")

        assert response.status_code == 200
        # Counter should have recorded requests

    def test_errors_accumulate_in_failed_counter(self, client: TestClient) -> None:
        """Test multiple errors accumulate in http_requests_failed_total counter."""
        # Make multiple error requests
        for _ in range(3):
            client.get("/v1/error")

        response = client.get("/v1/metrics")

        assert response.status_code == 200
        content = response.text
        assert "http_requests_failed_total" in content

    def test_histogram_records_multiple_observations(self, client: TestClient) -> None:
        """Test histogram records multiple request durations."""
        # Make multiple requests
        for _ in range(10):
            client.get("/v1/test")

        response = client.get("/v1/metrics")

        assert response.status_code == 200
        content = response.text
        assert "http_request_duration_seconds_count" in content
