"""Integration tests for structured logging (Story 8.7, AC1, AC2, AC3).

Tests end-to-end correlation ID propagation and logging through the API.
"""

import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.infrastructure.observability import configure_structlog


class TestLoggingMiddlewareIntegration:
    """Integration tests for LoggingMiddleware."""

    @pytest.fixture
    def client(self) -> TestClient:
        """Create test client with configured logging."""
        configure_structlog(environment="production")
        return TestClient(app)

    def test_correlation_id_generated_when_not_provided(
        self, client: TestClient
    ) -> None:
        """Test that correlation ID is generated if not in request (AC2)."""
        response = client.get("/health")

        # Response should contain X-Correlation-ID header
        assert "X-Correlation-ID" in response.headers
        correlation_id = response.headers["X-Correlation-ID"]

        # Should be a valid UUID format
        assert len(correlation_id) == 36
        assert correlation_id.count("-") == 4

    def test_correlation_id_propagated_from_request(
        self, client: TestClient
    ) -> None:
        """Test that correlation ID from request header is propagated (AC2)."""
        test_correlation_id = "test-correlation-id-12345"

        response = client.get(
            "/health",
            headers={"X-Correlation-ID": test_correlation_id},
        )

        # Response should contain the same correlation ID
        assert response.headers.get("X-Correlation-ID") == test_correlation_id

    def test_correlation_id_consistent_across_request(
        self, client: TestClient
    ) -> None:
        """Test correlation ID remains consistent throughout request (AC2)."""
        test_correlation_id = "consistent-correlation-id"

        # Make multiple requests with same correlation ID
        response1 = client.get(
            "/health",
            headers={"X-Correlation-ID": test_correlation_id},
        )
        response2 = client.get(
            "/health",
            headers={"X-Correlation-ID": test_correlation_id},
        )

        # Both responses should have the same correlation ID
        assert response1.headers.get("X-Correlation-ID") == test_correlation_id
        assert response2.headers.get("X-Correlation-ID") == test_correlation_id


class TestStructuredLogOutput:
    """Integration tests for structured log output."""

    @pytest.fixture
    def client(self) -> TestClient:
        """Create test client with production logging."""
        configure_structlog(environment="production")
        return TestClient(app)

    def test_request_logs_include_required_fields(
        self, client: TestClient, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test that request logs contain all required fields (AC1)."""
        test_correlation_id = "log-test-correlation-id"

        # Make a request - status code doesn't matter for log testing
        # The endpoint may not exist in test context (startup not run)
        response = client.get(
            "/health",
            headers={"X-Correlation-ID": test_correlation_id},
        )

        # Response should have correlation ID regardless of status
        assert response.headers.get("X-Correlation-ID") == test_correlation_id

        # Check captured logs (may need to check stderr too)
        captured = capsys.readouterr()
        output = captured.out + captured.err

        # Log lines should be parseable as JSON
        # Note: Multiple log lines may be present
        log_lines = [line for line in output.strip().split("\n") if line.strip()]

        # Should have at least request_started and request_completed logs
        request_logs = []
        for line in log_lines:
            try:
                log_entry = json.loads(line)
                # If this is a request log, verify fields
                if "request" in log_entry.get("event", ""):
                    assert "timestamp" in log_entry, "Log entry missing timestamp"
                    assert "level" in log_entry, "Log entry missing level"
                    assert "event" in log_entry, "Log entry missing event"
                    assert "correlation_id" in log_entry, "Log entry missing correlation_id"
                    assert log_entry["correlation_id"] == test_correlation_id
                    request_logs.append(log_entry)
            except json.JSONDecodeError:
                # Skip non-JSON lines (may be from other loggers)
                pass

        # Should have captured at least one request log
        assert len(request_logs) >= 1, "No request logs captured"


class TestEnvironmentConfiguration:
    """Integration tests for environment-based configuration."""

    def test_production_environment_uses_json(self) -> None:
        """Test that production environment outputs JSON (AC3)."""
        configure_structlog(environment="production")

        # Get config and verify JSON renderer
        import structlog

        config = structlog.get_config()
        processors = config.get("processors", [])

        json_found = any(
            "JSONRenderer" in str(type(p))
            for p in processors
        )
        assert json_found

    def test_development_environment_uses_console(self) -> None:
        """Test that development environment uses console renderer (AC3)."""
        configure_structlog(environment="development")

        import structlog

        config = structlog.get_config()
        processors = config.get("processors", [])

        console_found = any(
            "ConsoleRenderer" in str(type(p))
            for p in processors
        )
        assert console_found


class TestCorrelationIdPropagation:
    """Integration tests for correlation ID propagation across services."""

    @pytest.fixture
    def client(self) -> TestClient:
        """Create test client."""
        configure_structlog(environment="production")
        return TestClient(app)

    def test_correlation_id_in_error_responses(
        self, client: TestClient
    ) -> None:
        """Test that correlation ID is in response even on errors (AC2)."""
        test_correlation_id = "error-correlation-id"

        # Request a non-existent endpoint to get 404
        response = client.get(
            "/non-existent-endpoint",
            headers={"X-Correlation-ID": test_correlation_id},
        )

        # Should still have correlation ID in response
        assert response.headers.get("X-Correlation-ID") == test_correlation_id

    def test_each_request_gets_unique_correlation_id(
        self, client: TestClient
    ) -> None:
        """Test that separate requests get unique correlation IDs (AC2)."""
        response1 = client.get("/health")
        response2 = client.get("/health")

        correlation_id1 = response1.headers.get("X-Correlation-ID")
        correlation_id2 = response2.headers.get("X-Correlation-ID")

        # Each request should get a unique correlation ID when not provided
        assert correlation_id1 != correlation_id2


class TestBaseServiceLoggingMixin:
    """Integration tests for the LoggingMixin pattern."""

    def test_logging_mixin_integration(self) -> None:
        """Test that LoggingMixin works correctly in services (AC4)."""
        configure_structlog(environment="production")

        from src.application.services.base import LoggingMixin
        from src.infrastructure.observability.correlation import set_correlation_id

        # Create a test service using the mixin
        class TestService(LoggingMixin):
            def __init__(self) -> None:
                self._init_logger()

            def do_operation(self) -> None:
                log = self._log_operation("test_operation", test_key="test_value")
                log.info("operation_executed")

        # Set correlation ID in context
        set_correlation_id("mixin-test-correlation")

        # Create service and call operation
        service = TestService()
        service.do_operation()

        # Verify logger is properly bound
        assert hasattr(service, "_log")

        # Clean up
        set_correlation_id("")
