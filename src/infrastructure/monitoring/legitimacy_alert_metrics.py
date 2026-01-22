"""Prometheus metrics for legitimacy alerting (Story 8.2, AC6).

Provides operational metrics for legitimacy decay alerting system.

Constitutional Constraints:
- FR-8.3: System SHALL alert on decay below 0.85 threshold
- NFR-7.2: Alert delivery within 1 minute of trigger
- AC6: Alert observability metrics

Metrics Exposed:
- legitimacy_alerts_triggered_total: Counter of alerts triggered by severity
- legitimacy_alerts_active: Gauge of active alerts (0 or 1)
- legitimacy_alert_duration_seconds: Histogram of alert duration
- legitimacy_alert_delivery_failures_total: Counter of delivery failures by channel
"""

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram

# Histogram buckets for alert duration (1min to 24h in seconds)
ALERT_DURATION_BUCKETS = (
    60,        # 1 minute
    300,       # 5 minutes
    600,       # 10 minutes
    1800,      # 30 minutes
    3600,      # 1 hour
    7200,      # 2 hours
    14400,     # 4 hours
    28800,     # 8 hours
    43200,     # 12 hours
    86400,     # 24 hours
)


class LegitimacyAlertMetrics:
    """Prometheus metrics collector for legitimacy alerting (Story 8.2, AC6).

    This class provides operational metrics for the legitimacy alerting system,
    enabling operators to monitor alert frequency, delivery success, and system health.

    Metrics:
        legitimacy_alerts_triggered_total: Counter labeled by severity (WARNING|CRITICAL)
        legitimacy_alerts_active: Gauge (0 or 1) indicating if an alert is active
        legitimacy_alert_duration_seconds: Histogram of alert durations
        legitimacy_alert_delivery_failures_total: Counter labeled by channel

    Constitutional Requirements:
        - AC6: Prometheus metrics updated when alerts trigger or recover
        - NFR-7.2: Metrics enable verification of < 1 minute delivery SLA
    """

    def __init__(self, registry: CollectorRegistry | None = None):
        """Initialize legitimacy alert metrics.

        Args:
            registry: Optional custom registry for testing isolation.
                     If None, uses default registry.
        """
        self._registry = registry or CollectorRegistry()

        # Counter: Total alerts triggered, labeled by severity
        self.alerts_triggered_total = Counter(
            name="legitimacy_alerts_triggered_total",
            documentation="Total legitimacy alerts triggered by severity",
            labelnames=["severity"],
            registry=self._registry,
        )

        # Gauge: Current number of active alerts (0 or 1)
        self.alerts_active = Gauge(
            name="legitimacy_alerts_active",
            documentation="Number of active legitimacy alerts (0 or 1)",
            registry=self._registry,
        )

        # Histogram: Alert duration from trigger to recovery
        self.alert_duration_seconds = Histogram(
            name="legitimacy_alert_duration_seconds",
            documentation="Duration of legitimacy alerts in seconds",
            labelnames=["severity"],
            buckets=ALERT_DURATION_BUCKETS,
            registry=self._registry,
        )

        # Counter: Alert delivery failures by channel
        self.alert_delivery_failures_total = Counter(
            name="legitimacy_alert_delivery_failures_total",
            documentation="Total alert delivery failures by channel",
            labelnames=["channel"],
            registry=self._registry,
        )

    def record_alert_triggered(self, severity: str) -> None:
        """Record an alert trigger event.

        Args:
            severity: Alert severity (WARNING or CRITICAL)
        """
        self.alerts_triggered_total.labels(severity=severity).inc()
        self.alerts_active.set(1)

    def record_alert_recovered(self, severity: str, duration_seconds: int) -> None:
        """Record an alert recovery event.

        Args:
            severity: Alert severity that recovered (WARNING or CRITICAL)
            duration_seconds: Duration the alert was active (seconds)
        """
        self.alert_duration_seconds.labels(severity=severity).observe(duration_seconds)
        self.alerts_active.set(0)

    def record_delivery_failure(self, channel: str) -> None:
        """Record an alert delivery failure.

        Args:
            channel: Delivery channel that failed (pagerduty|slack|email)
        """
        self.alert_delivery_failures_total.labels(channel=channel).inc()

    def get_metrics_text(self) -> str:
        """Get Prometheus metrics in text exposition format.

        Returns:
            Metrics in Prometheus text format for scraping.
        """
        from prometheus_client import generate_latest
        return generate_latest(self._registry).decode("utf-8")


# Singleton instance for application-wide use
_metrics_instance: LegitimacyAlertMetrics | None = None


def get_legitimacy_alert_metrics() -> LegitimacyAlertMetrics:
    """Get singleton instance of LegitimacyAlertMetrics.

    Returns:
        Singleton LegitimacyAlertMetrics instance.
    """
    global _metrics_instance
    if _metrics_instance is None:
        _metrics_instance = LegitimacyAlertMetrics()
    return _metrics_instance
