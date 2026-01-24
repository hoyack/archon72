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

        # Petition queue capacity metrics (Story 1.3, FR-1.4, AC4)
        # These enable alerting on queue saturation before 503s occur

        # Current queue depth gauge (AC3: petition_queue_depth{state="RECEIVED"})
        self.petition_queue_depth = Gauge(
            name="petition_queue_depth",
            documentation="Current number of petitions in RECEIVED state",
            labelnames=["service", "environment", "state"],
            registry=self._registry,
        )

        # Queue threshold gauge (for calculating utilization percentage)
        self.petition_queue_threshold = Gauge(
            name="petition_queue_threshold",
            documentation="Configured petition queue threshold",
            labelnames=["service", "environment"],
            registry=self._registry,
        )

        # Rejection counter for 503 responses
        self.petition_queue_rejections_total = Counter(
            name="petition_queue_rejections_total",
            documentation="Total petition submissions rejected due to queue overflow",
            labelnames=["service", "environment"],
            registry=self._registry,
        )

        # Rate limit metrics (Story 1.4, FR-1.5, HC-4, AC4)
        # These enable alerting on rate limiting activity

        # Rate limit hits counter (429 responses due to rate limiting)
        self.petition_rate_limit_hits_total = Counter(
            name="petition_rate_limit_hits_total",
            documentation="Total petition submissions rejected due to rate limiting",
            labelnames=["service", "environment"],
            registry=self._registry,
        )

        # Rate limit remaining gauge (per submitter)
        # Note: This is an aggregate metric, not per-submitter (would be too many labels)
        self.petition_rate_limit_checks_total = Counter(
            name="petition_rate_limit_checks_total",
            documentation="Total rate limit checks performed",
            labelnames=["service", "environment", "result"],
            registry=self._registry,
        )

        # META petition metrics (Story 8.5, FR-10.4)
        # These track META petitions routed to High Archon queue

        # META petitions received counter (AC6: events witnessed)
        self.meta_petitions_received_total = Counter(
            name="meta_petitions_received_total",
            documentation="Total META petitions routed to High Archon queue",
            labelnames=["service", "environment"],
            registry=self._registry,
        )

        # META petitions resolved counter (AC6: events witnessed)
        self.meta_petitions_resolved_total = Counter(
            name="meta_petitions_resolved_total",
            documentation="Total META petitions resolved by High Archon",
            labelnames=["service", "environment", "disposition"],
            registry=self._registry,
        )

        # META petition queue depth gauge
        self.meta_petition_queue_depth = Gauge(
            name="meta_petition_queue_depth",
            documentation="Current number of pending META petitions",
            labelnames=["service", "environment"],
            registry=self._registry,
        )

        # Adoption ratio metrics (Story 8.6, PREVENT-7)
        # These track adoption ratio alerting per realm

        # Adoption ratio gauge per realm
        self.adoption_ratio = Gauge(
            name="adoption_ratio",
            documentation="Current adoption ratio per realm (0.0 to 1.0)",
            labelnames=["service", "environment", "realm_id", "cycle_id"],
            registry=self._registry,
        )

        # Adoption ratio alerts counter
        self.adoption_ratio_alerts_total = Counter(
            name="adoption_ratio_alerts_total",
            documentation="Total adoption ratio alerts triggered",
            labelnames=["service", "environment", "severity"],
            registry=self._registry,
        )

        # Adoption ratio alerts resolved counter
        self.adoption_ratio_alerts_resolved_total = Counter(
            name="adoption_ratio_alerts_resolved_total",
            documentation="Total adoption ratio alerts resolved",
            labelnames=["service", "environment", "severity"],
            registry=self._registry,
        )

        # Active adoption ratio alerts gauge
        self.adoption_ratio_alerts_active = Gauge(
            name="adoption_ratio_alerts_active",
            documentation="Current number of active adoption ratio alerts",
            labelnames=["service", "environment"],
            registry=self._registry,
        )

        # Realms exceeding threshold gauge
        self.adoption_ratio_realms_exceeding = Gauge(
            name="adoption_ratio_realms_exceeding",
            documentation="Number of realms exceeding adoption ratio threshold",
            labelnames=["service", "environment", "cycle_id"],
            registry=self._registry,
        )

        # Long-poll metrics (Story 7.1, FR-7.2, AC3)
        # These track long-poll connection efficiency and state change latency

        # Active long-poll connections gauge (Task 6.1)
        self.petition_status_longpoll_connections_active = Gauge(
            name="petition_status_longpoll_connections_active",
            documentation="Current number of active long-poll connections",
            labelnames=["service", "environment"],
            registry=self._registry,
        )

        # Long-poll timeout counter (Task 6.2)
        self.petition_status_longpoll_timeout_total = Counter(
            name="petition_status_longpoll_timeout_total",
            documentation="Total long-poll requests that timed out (HTTP 304)",
            labelnames=["service", "environment"],
            registry=self._registry,
        )

        # Long-poll state changed counter (Task 6.3)
        self.petition_status_longpoll_changed_total = Counter(
            name="petition_status_longpoll_changed_total",
            documentation="Total long-poll requests that detected state change",
            labelnames=["service", "environment"],
            registry=self._registry,
        )

        # Long-poll latency histogram (Task 6.4)
        # Measures time from request to response (should be < 100ms for changes)
        self.petition_status_longpoll_latency_seconds = Histogram(
            name="petition_status_longpoll_latency_seconds",
            documentation="Long-poll request duration in seconds",
            labelnames=["service", "environment", "result"],
            buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 5.0, 15.0, 30.0),
            registry=self._registry,
        )

        # Fate notification metrics (Story 7.2, FR-7.3)
        # These track notification delivery on fate assignment

        # Fate notification sent counter (Task 8.1)
        # Labels: fate, channel, status per story requirements
        self.petition_fate_notification_sent_total = Counter(
            name="petition_fate_notification_sent_total",
            documentation="Total fate notifications sent",
            labelnames=["service", "environment", "fate", "channel", "status"],
            registry=self._registry,
        )

        # Fate notification delivery latency histogram (Task 8.2)
        # Measures time from fate assignment to notification delivery
        self.petition_fate_notification_delivery_latency_seconds = Histogram(
            name="petition_fate_notification_delivery_latency_seconds",
            documentation="Fate notification delivery latency in seconds",
            labelnames=["service", "environment", "channel"],
            buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
            registry=self._registry,
        )

        # Fate notification retry counter (Task 8.3)
        self.petition_fate_notification_retry_total = Counter(
            name="petition_fate_notification_retry_total",
            documentation="Total fate notification retries scheduled",
            labelnames=["service", "environment", "channel"],
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

    def set_petition_queue_depth(self, depth: int, state: str = "RECEIVED") -> None:
        """Set the current petition queue depth gauge (Story 1.3, AC3).

        Args:
            depth: Current number of petitions in the specified state.
            state: Petition state being measured (default: "RECEIVED").
        """
        self.petition_queue_depth.labels(
            service=self._service_name,
            environment=self._environment,
            state=state,
        ).set(depth)

    def set_petition_queue_threshold(self, threshold: int) -> None:
        """Set the petition queue threshold gauge (Story 1.3, AC4).

        Args:
            threshold: Configured threshold before 503 rejections.
        """
        self.petition_queue_threshold.labels(
            service=self._service_name,
            environment=self._environment,
        ).set(threshold)

    def increment_petition_queue_rejections(self) -> None:
        """Increment the petition queue rejections counter (Story 1.3, AC4).

        Called when a 503 is returned due to queue overflow.
        """
        self.petition_queue_rejections_total.labels(
            service=self._service_name,
            environment=self._environment,
        ).inc()

    def increment_petition_rate_limit_hits(self) -> None:
        """Increment the petition rate limit hits counter (Story 1.4, AC4).

        Called when a 429 is returned due to rate limiting.
        """
        self.petition_rate_limit_hits_total.labels(
            service=self._service_name,
            environment=self._environment,
        ).inc()
        # Also record as a rate limit check with "blocked" result
        self.petition_rate_limit_checks_total.labels(
            service=self._service_name,
            environment=self._environment,
            result="blocked",
        ).inc()

    def increment_petition_rate_limit_allowed(self) -> None:
        """Increment the petition rate limit checks counter for allowed requests (Story 1.4, AC4).

        Called when a rate limit check passes (submitter is under limit).
        """
        self.petition_rate_limit_checks_total.labels(
            service=self._service_name,
            environment=self._environment,
            result="allowed",
        ).inc()

    def increment_meta_petitions_received(self) -> None:
        """Increment the META petitions received counter (Story 8.5, AC6).

        Called when a META petition is routed to High Archon queue.
        """
        self.meta_petitions_received_total.labels(
            service=self._service_name,
            environment=self._environment,
        ).inc()

    def increment_meta_petitions_resolved(self, disposition: str) -> None:
        """Increment the META petitions resolved counter (Story 8.5, AC6).

        Called when High Archon resolves a META petition.

        Args:
            disposition: Resolution disposition (ACKNOWLEDGE, CREATE_ACTION, FORWARD).
        """
        self.meta_petitions_resolved_total.labels(
            service=self._service_name,
            environment=self._environment,
            disposition=disposition,
        ).inc()

    def set_meta_petition_queue_depth(self, depth: int) -> None:
        """Set the META petition queue depth gauge (Story 8.5).

        Args:
            depth: Current number of pending META petitions.
        """
        self.meta_petition_queue_depth.labels(
            service=self._service_name,
            environment=self._environment,
        ).set(depth)

    def set_adoption_ratio(self, realm_id: str, cycle_id: str, ratio: float) -> None:
        """Set the adoption ratio gauge for a realm (Story 8.6, PREVENT-7).

        Args:
            realm_id: Realm identifier.
            cycle_id: Governance cycle identifier.
            ratio: Adoption ratio (0.0 to 1.0).
        """
        self.adoption_ratio.labels(
            service=self._service_name,
            environment=self._environment,
            realm_id=realm_id,
            cycle_id=cycle_id,
        ).set(ratio)

    def increment_adoption_ratio_alerts(self, severity: str) -> None:
        """Increment adoption ratio alerts counter (Story 8.6, PREVENT-7).

        Called when an adoption ratio alert is triggered.

        Args:
            severity: Alert severity (WARN or CRITICAL).
        """
        self.adoption_ratio_alerts_total.labels(
            service=self._service_name,
            environment=self._environment,
            severity=severity,
        ).inc()

    def increment_adoption_ratio_alerts_resolved(self, severity: str) -> None:
        """Increment adoption ratio alerts resolved counter (Story 8.6, PREVENT-7).

        Called when an adoption ratio alert is resolved.

        Args:
            severity: Alert severity that was resolved (WARN or CRITICAL).
        """
        self.adoption_ratio_alerts_resolved_total.labels(
            service=self._service_name,
            environment=self._environment,
            severity=severity,
        ).inc()

    def set_adoption_ratio_alerts_active(self, count: int) -> None:
        """Set the active adoption ratio alerts gauge (Story 8.6, PREVENT-7).

        Args:
            count: Current number of active adoption ratio alerts.
        """
        self.adoption_ratio_alerts_active.labels(
            service=self._service_name,
            environment=self._environment,
        ).set(count)

    def set_adoption_ratio_realms_exceeding(self, cycle_id: str, count: int) -> None:
        """Set the realms exceeding threshold gauge (Story 8.6, PREVENT-7).

        Args:
            cycle_id: Governance cycle identifier.
            count: Number of realms exceeding 50% adoption ratio threshold.
        """
        self.adoption_ratio_realms_exceeding.labels(
            service=self._service_name,
            environment=self._environment,
            cycle_id=cycle_id,
        ).set(count)

    def set_longpoll_connections_active(self, count: int) -> None:
        """Set the active long-poll connections gauge (Story 7.1, Task 6.1).

        Args:
            count: Current number of active long-poll connections.
        """
        self.petition_status_longpoll_connections_active.labels(
            service=self._service_name,
            environment=self._environment,
        ).set(count)

    def increment_longpoll_connections(self) -> None:
        """Increment active long-poll connections (Story 7.1, Task 6.1)."""
        self.petition_status_longpoll_connections_active.labels(
            service=self._service_name,
            environment=self._environment,
        ).inc()

    def decrement_longpoll_connections(self) -> None:
        """Decrement active long-poll connections (Story 7.1, Task 6.1)."""
        self.petition_status_longpoll_connections_active.labels(
            service=self._service_name,
            environment=self._environment,
        ).dec()

    def increment_longpoll_timeout(self) -> None:
        """Increment the long-poll timeout counter (Story 7.1, Task 6.2).

        Called when a long-poll request times out (HTTP 304).
        """
        self.petition_status_longpoll_timeout_total.labels(
            service=self._service_name,
            environment=self._environment,
        ).inc()

    def increment_longpoll_changed(self) -> None:
        """Increment the long-poll state changed counter (Story 7.1, Task 6.3).

        Called when a long-poll request detects a state change.
        """
        self.petition_status_longpoll_changed_total.labels(
            service=self._service_name,
            environment=self._environment,
        ).inc()

    def observe_longpoll_latency(self, duration: float, result: str) -> None:
        """Record a long-poll latency observation (Story 7.1, Task 6.4).

        Args:
            duration: Request duration in seconds.
            result: Result type ("changed", "timeout", "immediate").
        """
        self.petition_status_longpoll_latency_seconds.labels(
            service=self._service_name,
            environment=self._environment,
            result=result,
        ).observe(duration)

    def increment_fate_notification_sent(
        self, fate: str, channel: str, status: str
    ) -> None:
        """Increment the fate notification sent counter (Story 7.2, FR-7.3).

        Args:
            fate: Terminal fate (ACKNOWLEDGED, REFERRED, ESCALATED, DEFERRED, NO_RESPONSE).
            channel: Notification channel (WEBHOOK, IN_APP, LONG_POLL).
            status: Delivery status (DELIVERED, FAILED, PERMANENTLY_FAILED).
        """
        self.petition_fate_notification_sent_total.labels(
            service=self._service_name,
            environment=self._environment,
            fate=fate,
            channel=channel,
            status=status,
        ).inc()

    def observe_fate_notification_latency(self, duration: float, channel: str) -> None:
        """Record a fate notification delivery latency (Story 7.2, FR-7.3).

        Args:
            duration: Delivery latency in seconds.
            channel: Notification channel (WEBHOOK, IN_APP, LONG_POLL).
        """
        self.petition_fate_notification_delivery_latency_seconds.labels(
            service=self._service_name,
            environment=self._environment,
            channel=channel,
        ).observe(duration)

    def increment_fate_notification_retry(self, channel: str) -> None:
        """Increment the fate notification retry counter (Story 7.2, FR-7.3).

        Called when a notification delivery fails and is scheduled for retry.

        Args:
            channel: Notification channel (WEBHOOK, IN_APP).
        """
        self.petition_fate_notification_retry_total.labels(
            service=self._service_name,
            environment=self._environment,
            channel=channel,
        ).inc()

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
