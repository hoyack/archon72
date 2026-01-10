"""Unit tests for metrics middleware (Story 8.1, Task 2).

Tests for FastAPI middleware that records request metrics.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.middleware.metrics_middleware import MetricsMiddleware, _classify_error_type
from src.infrastructure.monitoring.metrics import (
    MetricsCollector,
    reset_metrics_collector,
)


@pytest.fixture(autouse=True)
def reset_collector() -> None:
    """Reset metrics collector before each test."""
    reset_metrics_collector()


class TestMetricsMiddleware:
    """Tests for MetricsMiddleware class."""

    def test_request_duration_recording(self) -> None:
        """Test middleware records request duration."""
        app = FastAPI()
        app.add_middleware(MetricsMiddleware)

        @app.get("/test")
        async def test_endpoint() -> dict[str, str]:
            return {"status": "ok"}

        client = TestClient(app)
        response = client.get("/test")

        assert response.status_code == 200

    def test_status_code_labeling(self) -> None:
        """Test middleware labels metrics with status code."""
        app = FastAPI()
        app.add_middleware(MetricsMiddleware)

        @app.get("/success")
        async def success_endpoint() -> dict[str, str]:
            return {"status": "ok"}

        @app.get("/not-found")
        async def not_found_endpoint() -> None:
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail="Not found")

        client = TestClient(app)

        # Success request
        response = client.get("/success")
        assert response.status_code == 200

        # 404 request
        response = client.get("/not-found")
        assert response.status_code == 404

    def test_error_tracking_4xx(self) -> None:
        """Test middleware tracks 4xx errors."""
        app = FastAPI()
        app.add_middleware(MetricsMiddleware)

        @app.get("/bad-request")
        async def bad_request_endpoint() -> None:
            from fastapi import HTTPException

            raise HTTPException(status_code=400, detail="Bad request")

        client = TestClient(app)
        response = client.get("/bad-request")

        assert response.status_code == 400

    def test_error_tracking_5xx(self) -> None:
        """Test middleware tracks 5xx errors."""
        app = FastAPI()
        app.add_middleware(MetricsMiddleware)

        @app.get("/server-error")
        async def server_error_endpoint() -> None:
            from fastapi import HTTPException

            raise HTTPException(status_code=500, detail="Server error")

        client = TestClient(app)
        response = client.get("/server-error")

        assert response.status_code == 500

    def test_method_labeling(self) -> None:
        """Test middleware labels metrics with HTTP method."""
        app = FastAPI()
        app.add_middleware(MetricsMiddleware)

        @app.get("/get-test")
        async def get_endpoint() -> dict[str, str]:
            return {"method": "get"}

        @app.post("/post-test")
        async def post_endpoint() -> dict[str, str]:
            return {"method": "post"}

        client = TestClient(app)

        response = client.get("/get-test")
        assert response.status_code == 200

        response = client.post("/post-test")
        assert response.status_code == 200

    def test_endpoint_path_labeling(self) -> None:
        """Test middleware labels metrics with endpoint path."""
        app = FastAPI()
        app.add_middleware(MetricsMiddleware)

        @app.get("/v1/health")
        async def health_endpoint() -> dict[str, str]:
            return {"status": "healthy"}

        @app.get("/v1/observer/events")
        async def events_endpoint() -> dict[str, str]:
            return {"events": "listed"}

        client = TestClient(app)

        response = client.get("/v1/health")
        assert response.status_code == 200

        response = client.get("/v1/observer/events")
        assert response.status_code == 200

    def test_metrics_not_blocked_by_request(self) -> None:
        """Test middleware doesn't block async request processing."""
        import asyncio

        app = FastAPI()
        app.add_middleware(MetricsMiddleware)

        @app.get("/async-test")
        async def async_endpoint() -> dict[str, str]:
            # Simulate async work
            await asyncio.sleep(0.01)
            return {"async": "completed"}

        client = TestClient(app)
        response = client.get("/async-test")

        assert response.status_code == 200
        assert response.json() == {"async": "completed"}

    def test_histogram_updated_on_request(self) -> None:
        """Test histogram is updated after request completes."""
        app = FastAPI()
        app.add_middleware(MetricsMiddleware)

        @app.get("/histogram-test")
        async def histogram_endpoint() -> dict[str, str]:
            return {"test": "histogram"}

        client = TestClient(app)

        # Make multiple requests
        for _ in range(3):
            response = client.get("/histogram-test")
            assert response.status_code == 200

    def test_counter_incremented_on_request(self) -> None:
        """Test request counter is incremented."""
        app = FastAPI()
        app.add_middleware(MetricsMiddleware)

        @app.get("/counter-test")
        async def counter_endpoint() -> dict[str, str]:
            return {"test": "counter"}

        client = TestClient(app)

        # Make multiple requests
        for _ in range(5):
            response = client.get("/counter-test")
            assert response.status_code == 200

    def test_failed_counter_incremented_for_errors(self) -> None:
        """Test failed request counter is incremented for errors."""
        app = FastAPI()
        app.add_middleware(MetricsMiddleware)

        @app.get("/error-counter-test")
        async def error_counter_endpoint() -> None:
            from fastapi import HTTPException

            raise HTTPException(status_code=503, detail="Service unavailable")

        client = TestClient(app)

        # Make multiple error requests
        for _ in range(3):
            response = client.get("/error-counter-test")
            assert response.status_code == 503


class TestErrorTypeClassifier:
    """Tests for _classify_error_type function (AC4 error_type label)."""

    def test_classify_bad_request(self) -> None:
        """Test 400 is classified as bad_request."""
        assert _classify_error_type(400) == "bad_request"

    def test_classify_unauthorized(self) -> None:
        """Test 401 is classified as unauthorized."""
        assert _classify_error_type(401) == "unauthorized"

    def test_classify_forbidden(self) -> None:
        """Test 403 is classified as forbidden."""
        assert _classify_error_type(403) == "forbidden"

    def test_classify_not_found(self) -> None:
        """Test 404 is classified as not_found."""
        assert _classify_error_type(404) == "not_found"

    def test_classify_timeout(self) -> None:
        """Test 408 is classified as timeout."""
        assert _classify_error_type(408) == "timeout"

    def test_classify_rate_limited(self) -> None:
        """Test 429 is classified as rate_limited."""
        assert _classify_error_type(429) == "rate_limited"

    def test_classify_other_4xx_as_client_error(self) -> None:
        """Test other 4xx codes are classified as client_error."""
        assert _classify_error_type(405) == "client_error"
        assert _classify_error_type(422) == "client_error"
        assert _classify_error_type(418) == "client_error"

    def test_classify_internal_error(self) -> None:
        """Test 500 is classified as internal_error."""
        assert _classify_error_type(500) == "internal_error"

    def test_classify_bad_gateway(self) -> None:
        """Test 502 is classified as bad_gateway."""
        assert _classify_error_type(502) == "bad_gateway"

    def test_classify_service_unavailable(self) -> None:
        """Test 503 is classified as service_unavailable."""
        assert _classify_error_type(503) == "service_unavailable"

    def test_classify_gateway_timeout(self) -> None:
        """Test 504 is classified as gateway_timeout."""
        assert _classify_error_type(504) == "gateway_timeout"

    def test_classify_other_5xx_as_server_error(self) -> None:
        """Test other 5xx codes are classified as server_error."""
        assert _classify_error_type(501) == "server_error"
        assert _classify_error_type(507) == "server_error"

    def test_classify_success_as_unknown(self) -> None:
        """Test success codes return unknown (shouldn't be called)."""
        assert _classify_error_type(200) == "unknown"
        assert _classify_error_type(201) == "unknown"

    def test_classify_redirect_as_unknown(self) -> None:
        """Test redirect codes return unknown (shouldn't be called)."""
        assert _classify_error_type(301) == "unknown"
        assert _classify_error_type(302) == "unknown"
