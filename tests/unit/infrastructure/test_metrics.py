"""Unit tests for Prometheus metrics infrastructure (Story 8.1, Task 1).

Tests for MetricsCollector class that manages operational metrics.

Constitutional Constraints:
- FR52: ONLY operational metrics (uptime, latency, errors)
- NO constitutional metrics (breach_count, halt_state, etc.)
"""

import time

import pytest

from src.infrastructure.monitoring.metrics import (
    MetricsCollector,
    get_metrics_collector,
)


class TestMetricsCollector:
    """Tests for MetricsCollector class."""

    def test_metrics_collector_initialization(self) -> None:
        """Test MetricsCollector initializes with all required metrics."""
        collector = MetricsCollector()

        # Verify all operational metrics are defined
        assert collector.uptime_seconds is not None
        assert collector.service_starts_total is not None
        assert collector.http_request_duration_seconds is not None
        assert collector.http_requests_total is not None
        assert collector.http_requests_failed_total is not None

    def test_uptime_gauge_updates(self) -> None:
        """Test uptime gauge can be set for different services."""
        from prometheus_client import generate_latest

        collector = MetricsCollector()

        # Set uptime for api service
        collector.set_uptime("api", 120.5)

        # Verify gauge was updated by checking generated metrics
        output = generate_latest(collector.get_registry()).decode("utf-8")
        assert 'uptime_seconds{environment="development",service="api"}' in output
        assert "120.5" in output

    def test_service_starts_counter_increments(self) -> None:
        """Test service starts counter can be incremented."""
        from prometheus_client import generate_latest

        collector = MetricsCollector()

        # Increment starts counter for api service
        collector.increment_service_starts("api")
        collector.increment_service_starts("api")
        collector.increment_service_starts("observer")

        # Verify counter was incremented by checking generated metrics
        output = generate_latest(collector.get_registry()).decode("utf-8")
        assert 'service_starts_total{environment="development",service="api"}' in output
        assert 'service_starts_total{environment="development",service="observer"}' in output

    def test_histogram_recording(self) -> None:
        """Test request duration histogram records values."""
        from prometheus_client import generate_latest

        collector = MetricsCollector()

        # Record various request durations
        collector.observe_request_duration(
            method="GET", endpoint="/v1/health", duration=0.015
        )
        collector.observe_request_duration(
            method="POST", endpoint="/v1/events", duration=0.250
        )
        collector.observe_request_duration(
            method="GET", endpoint="/v1/observer/events", duration=1.5
        )

        # Verify histogram recorded values by checking generated metrics
        output = generate_latest(collector.get_registry()).decode("utf-8")
        assert "http_request_duration_seconds" in output
        # Check that sum was recorded (should be approximately 0.015 + 0.25 + 1.5 = 1.765)
        assert "http_request_duration_seconds_sum" in output

    def test_histogram_buckets_configured(self) -> None:
        """Test histogram has appropriate bucket configuration."""
        collector = MetricsCollector()

        # Expected buckets per story spec: 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0
        expected_buckets = (0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)

        # Verify the buckets match expected configuration
        assert collector.histogram_buckets == expected_buckets

    def test_request_counter_increments(self) -> None:
        """Test http_requests_total counter increments with labels."""
        from prometheus_client import generate_latest

        collector = MetricsCollector()

        # Increment request counter with various labels
        collector.increment_requests("GET", "/v1/health", "200")
        collector.increment_requests("POST", "/v1/events", "201")
        collector.increment_requests("GET", "/v1/observer/events", "200")

        # Verify counter was incremented by checking generated metrics
        output = generate_latest(collector.get_registry()).decode("utf-8")
        assert "http_requests_total" in output
        assert 'method="GET"' in output
        assert 'endpoint="/v1/health"' in output
        assert 'status="200"' in output

    def test_failed_request_counter_increments(self) -> None:
        """Test http_requests_failed_total counter increments for 4xx/5xx."""
        from prometheus_client import generate_latest

        collector = MetricsCollector()

        # Increment failed request counter with error_type
        collector.increment_failed_requests("GET", "/v1/events/123", "404", "not_found")
        collector.increment_failed_requests("POST", "/v1/events", "500", "internal_error")
        collector.increment_failed_requests("GET", "/v1/observer", "503", "service_unavailable")

        # Verify counter was incremented by checking generated metrics
        output = generate_latest(collector.get_registry()).decode("utf-8")
        assert "http_requests_failed_total" in output
        assert 'error_type="not_found"' in output
        assert 'error_type="internal_error"' in output
        assert 'error_type="service_unavailable"' in output

    def test_no_constitutional_metrics_exposed(self) -> None:
        """Test that NO constitutional metrics are exposed (FR52).

        Constitutional metrics belong to Story 8.10, not this story.
        This test ensures we don't accidentally add them here.
        """
        collector = MetricsCollector()

        # Verify these constitutional metrics do NOT exist
        assert not hasattr(collector, "breach_count")
        assert not hasattr(collector, "halt_state")
        assert not hasattr(collector, "dissent_health")
        assert not hasattr(collector, "witness_coverage")
        assert not hasattr(collector, "override_frequency")

    def test_record_startup_time(self) -> None:
        """Test startup time recording for uptime calculation."""
        collector = MetricsCollector()

        # Record startup
        collector.record_startup("api")

        # Verify startup was recorded
        assert "api" in collector.startup_times

    def test_get_uptime_seconds(self) -> None:
        """Test calculating uptime from startup time."""
        collector = MetricsCollector()

        # Record startup
        collector.record_startup("api")

        # Small delay
        time.sleep(0.1)

        # Get uptime
        uptime = collector.get_uptime_seconds("api")

        # Uptime should be at least 0.1 seconds
        assert uptime >= 0.1

    def test_get_uptime_seconds_unknown_service(self) -> None:
        """Test getting uptime for unknown service returns 0."""
        collector = MetricsCollector()

        uptime = collector.get_uptime_seconds("unknown-service")
        assert uptime == 0.0

    def test_service_and_environment_labels(self) -> None:
        """Test that metrics have service and environment labels (AC1)."""
        collector = MetricsCollector()

        # Verify label names are configured for all metrics (AC1 requirement)
        assert "service" in collector.uptime_seconds._labelnames
        assert "environment" in collector.uptime_seconds._labelnames
        assert "service" in collector.service_starts_total._labelnames
        assert "environment" in collector.service_starts_total._labelnames
        # HTTP metrics also have service and environment labels
        assert "service" in collector.http_request_duration_seconds._labelnames
        assert "environment" in collector.http_request_duration_seconds._labelnames
        assert "service" in collector.http_requests_total._labelnames
        assert "environment" in collector.http_requests_total._labelnames
        assert "service" in collector.http_requests_failed_total._labelnames
        assert "environment" in collector.http_requests_failed_total._labelnames
        # AC4: error_type label on failed requests
        assert "error_type" in collector.http_requests_failed_total._labelnames

    def test_singleton_pattern(self) -> None:
        """Test get_metrics_collector returns same instance."""
        collector1 = get_metrics_collector()
        collector2 = get_metrics_collector()

        # Should be the same instance
        assert collector1 is collector2


class TestMetricsExposition:
    """Tests for Prometheus metrics exposition."""

    def test_generate_metrics_output(self) -> None:
        """Test metrics can be generated in Prometheus format."""
        from src.infrastructure.monitoring.metrics import generate_metrics

        collector = get_metrics_collector()

        # Record some metrics
        collector.increment_requests("GET", "/test", "200")

        # Generate metrics output
        output = generate_metrics()

        # Should be bytes in Prometheus format
        assert isinstance(output, bytes)
        assert b"http_requests_total" in output

    def test_metrics_content_type(self) -> None:
        """Test metrics content type is correct Prometheus format."""
        from src.infrastructure.monitoring.metrics import METRICS_CONTENT_TYPE

        expected = "text/plain; version=0.0.4; charset=utf-8"
        assert METRICS_CONTENT_TYPE == expected
