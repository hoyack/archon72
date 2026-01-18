"""Prometheus metrics infrastructure (Story 8.1, Task 1).

Operational metrics collection for system health monitoring.

Constitutional Constraints:
- FR52: ONLY operational metrics (uptime, latency, errors)
- NO constitutional metrics (breach_count, halt_state, etc.)
- Constitutional health belongs to Story 8.10, NOT here

NFR27 Requirements:
- Prometheus exposition format
- Labels: service, environment
- Latency histograms with standard buckets
"""

import os
import threading
import time

from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

# Content type for Prometheus metrics endpoint
METRICS_CONTENT_TYPE = "text/plain; version=0.0.4; charset=utf-8"

# Thread lock for singleton initialization (M2/M3 fix)
_collector_lock = threading.Lock()

# Histogram buckets for request duration (10ms to 10s)
# Per story specification: 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0
DEFAULT_HISTOGRAM_BUCKETS = (0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)


class MetricsCollector:
    """Collects and manages operational Prometheus metrics.

    This class manages ONLY operational metrics per FR52.
    Constitutional metrics (breach_count, halt_state, etc.) belong to Story 8.10.

    Attributes:
        uptime_seconds: Gauge tracking seconds since service start.
        service_starts_total: Counter tracking service restarts.
        http_request_duration_seconds: Histogram for request latency.
        http_requests_total: Counter for all HTTP requests.
        http_requests_failed_total: Counter for failed requests (4xx, 5xx).
        histogram_buckets: Configured histogram bucket boundaries.
        startup_times: Dict mapping service name to startup timestamp.
    """

    def __init__(self, registry: CollectorRegistry | None = None) -> None:
        """Initialize metrics collector with operational metrics.

        Args:
            registry: Optional custom registry for testing isolation.
        """
        self._registry = registry or CollectorRegistry()
        self.histogram_buckets = DEFAULT_HISTOGRAM_BUCKETS
        self.startup_times: dict[str, float] = {}

        # Get environment for labels
        self._environment = os.environ.get("ENVIRONMENT", "development")
        self._service_name = os.environ.get("SERVICE_NAME", "archon72-api")

        # Define operational metrics (FR52: ONLY operational, NO constitutional)

        # Uptime gauge per service (AC1, AC2)
        # Labels: service, environment per AC1
        self.uptime_seconds = Gauge(
            name="uptime_seconds",
            documentation="Seconds since service start",
            labelnames=["service", "environment"],
            registry=self._registry,
        )

        # Service starts counter (AC1, AC2)
        self.service_starts_total = Counter(
            name="service_starts_total",
            documentation="Total number of service starts/restarts",
            labelnames=["service", "environment"],
            registry=self._registry,
        )

        # Request duration histogram (AC1, AC3)
        # Labels include service/environment per AC1
        self.http_request_duration_seconds = Histogram(
            name="http_request_duration_seconds",
            documentation="HTTP request duration in seconds",
            labelnames=["service", "environment", "method", "endpoint"],
            buckets=self.histogram_buckets,
            registry=self._registry,
        )

        # Total requests counter (AC1, AC4)
        self.http_requests_total = Counter(
            name="http_requests_total",
            documentation="Total HTTP requests",
            labelnames=["service", "environment", "method", "endpoint", "status"],
            registry=self._registry,
        )

        # Failed requests counter (AC1, AC4)
        # Labels: endpoint, status_code, error_type per AC4
        self.http_requests_failed_total = Counter(
            name="http_requests_failed_total",
            documentation="Total failed HTTP requests (4xx, 5xx)",
            labelnames=[
                "service",
                "environment",
                "method",
                "endpoint",
                "status",
                "error_type",
            ],
            registry=self._registry,
        )

    def set_uptime(self, service: str, seconds: float) -> None:
        """Set uptime gauge for a service.

        Args:
            service: Service name (api, event-writer, observer, watchdog).
            seconds: Uptime in seconds.
        """
        self.uptime_seconds.labels(service=service, environment=self._environment).set(
            seconds
        )

    def increment_service_starts(self, service: str) -> None:
        """Increment service starts counter.

        Args:
            service: Service name.
        """
        self.service_starts_total.labels(
            service=service, environment=self._environment
        ).inc()

    def observe_request_duration(
        self, method: str, endpoint: str, duration: float
    ) -> None:
        """Record a request duration observation.

        Args:
            method: HTTP method (GET, POST, etc.).
            endpoint: Request endpoint path.
            duration: Request duration in seconds.
        """
        self.http_request_duration_seconds.labels(
            service=self._service_name,
            environment=self._environment,
            method=method,
            endpoint=endpoint,
        ).observe(duration)

    def increment_requests(self, method: str, endpoint: str, status: str) -> None:
        """Increment total requests counter.

        Args:
            method: HTTP method.
            endpoint: Request endpoint.
            status: HTTP status code as string.
        """
        self.http_requests_total.labels(
            service=self._service_name,
            environment=self._environment,
            method=method,
            endpoint=endpoint,
            status=status,
        ).inc()

    def increment_failed_requests(
        self, method: str, endpoint: str, status: str, error_type: str = "http_error"
    ) -> None:
        """Increment failed requests counter.

        Args:
            method: HTTP method.
            endpoint: Request endpoint.
            status: HTTP status code as string (4xx or 5xx).
            error_type: Type of error (client_error, server_error, timeout, etc.).
        """
        self.http_requests_failed_total.labels(
            service=self._service_name,
            environment=self._environment,
            method=method,
            endpoint=endpoint,
            status=status,
            error_type=error_type,
        ).inc()

    def record_startup(self, service: str) -> None:
        """Record service startup time.

        Args:
            service: Service name.
        """
        self.startup_times[service] = time.time()
        self.increment_service_starts(service)

    def get_uptime_seconds(self, service: str) -> float:
        """Get uptime in seconds for a service.

        Args:
            service: Service name.

        Returns:
            Uptime in seconds, or 0.0 if service not registered.
        """
        if service not in self.startup_times:
            return 0.0
        return time.time() - self.startup_times[service]

    def update_uptime_gauges(self) -> None:
        """Update uptime gauges for all registered services."""
        for service in self.startup_times:
            uptime = self.get_uptime_seconds(service)
            self.set_uptime(service, uptime)

    def get_registry(self) -> CollectorRegistry:
        """Get the collector registry.

        Returns:
            The Prometheus collector registry.
        """
        return self._registry


# Singleton instance
_metrics_collector: MetricsCollector | None = None


def get_metrics_collector() -> MetricsCollector:
    """Get the singleton MetricsCollector instance (thread-safe).

    Uses double-checked locking pattern for thread-safe lazy initialization.

    Returns:
        The global MetricsCollector instance.
    """
    global _metrics_collector
    if _metrics_collector is None:
        with _collector_lock:
            # Double-check inside lock
            if _metrics_collector is None:
                _metrics_collector = MetricsCollector()
    return _metrics_collector


def generate_metrics() -> bytes:
    """Generate Prometheus metrics in exposition format.

    Returns:
        Metrics in Prometheus text format as bytes.
    """
    collector = get_metrics_collector()
    # Update uptime gauges before generating output
    collector.update_uptime_gauges()
    return generate_latest(collector.get_registry())


def reset_metrics_collector() -> None:
    """Reset the singleton collector (for testing only).

    Thread-safe reset using the collector lock.
    """
    global _metrics_collector
    with _collector_lock:
        _metrics_collector = None
