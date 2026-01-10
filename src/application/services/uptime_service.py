"""Uptime tracking service (Story 4.9, Task 3).

Tracks Observer API uptime for 99.9% SLA compliance.

Constitutional Constraints:
- RT-5: 99.9% uptime SLA with external monitoring
- CT-11: Silent failure destroys legitimacy - accurate health reporting
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

import structlog

log = structlog.get_logger()


@dataclass
class DowntimeIncident:
    """Record of a downtime incident.

    Attributes:
        start_time: When downtime started.
        end_time: When downtime ended (None if ongoing).
        reason: Reason for downtime.
    """

    start_time: datetime
    end_time: Optional[datetime] = None
    reason: str = "unknown"

    @property
    def duration_seconds(self) -> float:
        """Calculate duration in seconds.

        Returns:
            Duration in seconds (uses current time if ongoing).
        """
        end = self.end_time or datetime.now(timezone.utc)
        return (end - self.start_time).total_seconds()


@dataclass
class UptimeSLAStatus:
    """Uptime SLA status for reporting.

    Per RT-5: 99.9% uptime target.
    Per CT-11: Accurate reporting, not optimistic.

    Attributes:
        target_percentage: SLA target (99.9%).
        current_percentage: Current uptime percentage.
        meeting_sla: Whether currently meeting SLA.
        window_hours: Calculation window in hours.
        total_downtime_seconds: Total downtime in window.
        incidents: List of downtime incidents in window.
    """

    target_percentage: float = 99.9
    current_percentage: float = 100.0
    meeting_sla: bool = True
    window_hours: int = 720  # 30 days default
    total_downtime_seconds: float = 0.0
    incidents: list[DowntimeIncident] = field(default_factory=list)


class UptimeService:
    """Service for tracking Observer API uptime (RT-5).

    Per RT-5: 99.9% uptime SLA with external monitoring.
    Per CT-11: Accurate reporting, no optimistic status.

    Tracks:
    - Availability windows
    - Downtime incidents
    - SLA compliance

    Usage:
        service = UptimeService()

        # Record downtime start
        service.record_downtime_start("database_unavailable")

        # Record recovery
        service.record_downtime_end()

        # Check SLA status
        status = service.get_sla_status()
        if not status.meeting_sla:
            log.error("sla_violation", percentage=status.current_percentage)
    """

    SLA_TARGET = 99.9  # 99.9% uptime target

    def __init__(
        self,
        window_hours: int = 720,  # 30 days rolling window
    ) -> None:
        """Initialize uptime service.

        Args:
            window_hours: Rolling window for SLA calculation (default 30 days).
        """
        self._window_hours = window_hours
        self._incidents: list[DowntimeIncident] = []
        self._current_incident: Optional[DowntimeIncident] = None
        self._service_start: datetime = datetime.now(timezone.utc)

    def record_downtime_start(self, reason: str = "unknown") -> None:
        """Record start of downtime incident.

        Per CT-11: All downtime events are logged for accountability.

        Args:
            reason: Reason for the downtime.
        """
        if self._current_incident is not None:
            log.warning(
                "downtime_already_active",
                existing_reason=self._current_incident.reason,
                new_reason=reason,
            )
            return

        self._current_incident = DowntimeIncident(
            start_time=datetime.now(timezone.utc),
            reason=reason,
        )

        log.error(
            "downtime_started",
            reason=reason,
            start_time=self._current_incident.start_time.isoformat(),
        )

    def record_downtime_end(self) -> Optional[DowntimeIncident]:
        """Record end of current downtime incident.

        Per CT-11: Recovery events are logged for accountability.

        Returns:
            The completed incident, or None if no active incident.
        """
        if self._current_incident is None:
            log.warning("no_active_downtime")
            return None

        self._current_incident.end_time = datetime.now(timezone.utc)
        incident = self._current_incident
        self._incidents.append(incident)
        self._current_incident = None

        log.info(
            "downtime_ended",
            duration_seconds=incident.duration_seconds,
            reason=incident.reason,
        )

        return incident

    def get_sla_status(self) -> UptimeSLAStatus:
        """Get current SLA status.

        Per RT-5: Accurate SLA calculation over rolling window.
        Per CT-11: No optimistic reporting.

        Returns:
            UptimeSLAStatus with current uptime metrics.
        """
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(hours=self._window_hours)

        # Calculate total seconds in window (or since service start)
        service_start = max(self._service_start, window_start)
        total_seconds = (now - service_start).total_seconds()

        if total_seconds <= 0:
            return UptimeSLAStatus(
                target_percentage=self.SLA_TARGET,
                current_percentage=100.0,
                meeting_sla=True,
                window_hours=self._window_hours,
            )

        # Calculate downtime in window
        downtime_seconds = 0.0
        window_incidents: list[DowntimeIncident] = []

        for incident in self._incidents:
            if incident.end_time and incident.end_time >= window_start:
                # Incident overlaps with window
                incident_start = max(incident.start_time, window_start)
                incident_end = min(incident.end_time, now)
                downtime_seconds += (incident_end - incident_start).total_seconds()
                window_incidents.append(incident)

        # Include current incident if active
        if self._current_incident is not None:
            incident_start = max(self._current_incident.start_time, window_start)
            downtime_seconds += (now - incident_start).total_seconds()
            window_incidents.append(self._current_incident)

        # Calculate uptime percentage
        uptime_seconds = total_seconds - downtime_seconds
        uptime_percentage = (uptime_seconds / total_seconds) * 100.0

        return UptimeSLAStatus(
            target_percentage=self.SLA_TARGET,
            current_percentage=round(uptime_percentage, 4),
            meeting_sla=uptime_percentage >= self.SLA_TARGET,
            window_hours=self._window_hours,
            total_downtime_seconds=downtime_seconds,
            incidents=window_incidents,
        )

    def get_uptime_percentage(self) -> float:
        """Get current uptime percentage.

        Convenience method for metrics endpoint.

        Returns:
            Uptime percentage (0-100).
        """
        return self.get_sla_status().current_percentage

    def is_meeting_sla(self) -> bool:
        """Check if currently meeting SLA.

        Returns:
            True if meeting 99.9% SLA.
        """
        return self.get_sla_status().meeting_sla

    def get_incident_count(self) -> int:
        """Get total number of recorded incidents.

        Returns:
            Number of downtime incidents recorded.
        """
        count = len(self._incidents)
        if self._current_incident is not None:
            count += 1
        return count
