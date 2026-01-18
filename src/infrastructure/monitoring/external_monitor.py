"""External monitoring client (Story 4.9, Task 6).

Configuration and client for external uptime monitoring services.

Constitutional Constraints:
- RT-5: 99.9% uptime SLA with external monitoring
- CT-11: Silent failure destroys legitimacy - alert on downtime
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

import httpx
import structlog

log = structlog.get_logger()


class AlertSeverity(str, Enum):
    """Alert severity levels per project context.

    Aligns with project's alert severity classification.

    Values:
        CRITICAL: Page immediately, halt system.
        HIGH: Page immediately.
        MEDIUM: Alert on-call, 15 min response.
        LOW: Next business day.
        INFO: No alert, log only.
    """

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


@dataclass
class MonitoringConfig:
    """External monitoring configuration (RT-5).

    Configuration for external uptime monitoring service integration.

    Attributes:
        health_endpoint: URL to monitor.
        check_interval_seconds: How often to check.
        alert_webhook_url: Where to send alerts.
        sla_target: Target uptime percentage.
        alert_after_failures: Alert after N consecutive failures.
    """

    health_endpoint: str = "http://localhost:8000/v1/observer/health"
    check_interval_seconds: int = 30
    alert_webhook_url: str | None = None
    sla_target: float = 99.9
    alert_after_failures: int = 3


@dataclass
class MonitoringAlert:
    """Alert for monitoring events.

    Per CT-11: All monitoring events have full context for accountability.

    Attributes:
        severity: Alert severity level.
        title: Short alert title.
        message: Detailed alert message.
        timestamp: When alert was generated.
        service: Service that generated alert.
        incident_id: Optional incident tracking ID.
    """

    severity: AlertSeverity
    title: str
    message: str
    timestamp: datetime
    service: str = "observer-api"
    incident_id: str | None = None


class ExternalMonitorClient:
    """Client for sending alerts to external monitoring services.

    Per RT-5: External uptime monitoring with alerts.
    Per CT-11: All monitoring events are logged.

    Usage:
        config = MonitoringConfig(
            health_endpoint="http://localhost:8000/v1/observer/health",
            alert_webhook_url="https://alerts.example.com/webhook",
        )
        client = ExternalMonitorClient(config)

        # Record failures
        await client.record_check_failure("database_timeout")

        # Record recovery
        await client.record_check_success()
    """

    def __init__(self, config: MonitoringConfig) -> None:
        """Initialize external monitor client.

        Args:
            config: Monitoring configuration.
        """
        self._config = config
        self._consecutive_failures = 0
        self._current_incident_id: str | None = None

    async def send_alert(self, alert: MonitoringAlert) -> bool:
        """Send alert to external monitoring service.

        Per CT-11: Alert delivery is logged for accountability.

        Args:
            alert: The alert to send.

        Returns:
            True if alert was sent successfully.
        """
        if not self._config.alert_webhook_url:
            log.warning("no_alert_webhook_configured")
            return False

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    self._config.alert_webhook_url,
                    json={
                        "severity": alert.severity.value,
                        "title": alert.title,
                        "message": alert.message,
                        "timestamp": alert.timestamp.isoformat(),
                        "service": alert.service,
                        "incident_id": alert.incident_id,
                    },
                    timeout=10.0,
                )

                if response.status_code < 300:
                    log.info(
                        "alert_sent",
                        severity=alert.severity.value,
                        title=alert.title,
                        incident_id=alert.incident_id,
                    )
                    return True

                log.error(
                    "alert_send_failed",
                    status_code=response.status_code,
                    title=alert.title,
                )
                return False

            except Exception as e:
                log.error("alert_send_error", error=str(e), title=alert.title)
                return False

    async def record_check_failure(self, reason: str) -> None:
        """Record a health check failure.

        Per RT-5: Alert after consecutive failures.
        Per CT-11: All failures are logged.

        Args:
            reason: Reason for failure.
        """
        self._consecutive_failures += 1

        log.warning(
            "health_check_failed",
            consecutive_failures=self._consecutive_failures,
            reason=reason,
        )

        if self._consecutive_failures >= self._config.alert_after_failures:
            if self._current_incident_id is None:
                # Start new incident
                self._current_incident_id = (
                    f"observer-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
                )

                await self.send_alert(
                    MonitoringAlert(
                        severity=AlertSeverity.HIGH,
                        title="Observer API Down",
                        message=(
                            f"Observer API health check failed "
                            f"{self._consecutive_failures} times. Reason: {reason}"
                        ),
                        timestamp=datetime.now(timezone.utc),
                        incident_id=self._current_incident_id,
                    )
                )

    async def record_check_success(self) -> None:
        """Record a successful health check.

        Per CT-11: Recovery events are logged.
        """
        if self._consecutive_failures > 0:
            if self._current_incident_id is not None:
                # Recovery alert
                await self.send_alert(
                    MonitoringAlert(
                        severity=AlertSeverity.INFO,
                        title="Observer API Recovered",
                        message=(
                            f"Observer API recovered after "
                            f"{self._consecutive_failures} failed checks."
                        ),
                        timestamp=datetime.now(timezone.utc),
                        incident_id=self._current_incident_id,
                    )
                )
                self._current_incident_id = None

            log.info(
                "health_check_recovered",
                previous_failures=self._consecutive_failures,
            )

        self._consecutive_failures = 0

    def get_consecutive_failures(self) -> int:
        """Get current consecutive failure count.

        Returns:
            Number of consecutive failures.
        """
        return self._consecutive_failures

    def is_in_incident(self) -> bool:
        """Check if currently in an incident.

        Returns:
            True if an incident is active.
        """
        return self._current_incident_id is not None

    def get_current_incident_id(self) -> str | None:
        """Get current incident ID.

        Returns:
            Current incident ID, or None if no active incident.
        """
        return self._current_incident_id
