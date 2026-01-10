"""Unit tests for UptimeService (Story 4.9, Task 3).

Tests for uptime tracking and SLA compliance calculation.

Constitutional Constraints:
- RT-5: 99.9% uptime SLA with external monitoring
- CT-11: Silent failure destroys legitimacy - accurate health reporting
"""

import time
from datetime import datetime, timedelta, timezone

import pytest

from src.application.services.uptime_service import (
    DowntimeIncident,
    UptimeService,
    UptimeSLAStatus,
)


class TestDowntimeIncident:
    """Unit tests for DowntimeIncident dataclass."""

    def test_incident_duration_with_end_time(self) -> None:
        """Test duration calculation with end time."""
        start = datetime.now(timezone.utc)
        end = start + timedelta(minutes=5)

        incident = DowntimeIncident(
            start_time=start,
            end_time=end,
            reason="test",
        )

        assert incident.duration_seconds == 300.0  # 5 minutes

    def test_incident_duration_ongoing(self) -> None:
        """Test duration calculation for ongoing incident."""
        start = datetime.now(timezone.utc) - timedelta(seconds=10)

        incident = DowntimeIncident(
            start_time=start,
            reason="test",
        )

        # Duration should be at least 10 seconds
        assert incident.duration_seconds >= 10.0

    def test_incident_default_reason(self) -> None:
        """Test default reason is 'unknown'."""
        incident = DowntimeIncident(
            start_time=datetime.now(timezone.utc),
        )

        assert incident.reason == "unknown"


class TestUptimeSLAStatus:
    """Unit tests for UptimeSLAStatus dataclass."""

    def test_sla_status_defaults(self) -> None:
        """Test default values."""
        status = UptimeSLAStatus()

        assert status.target_percentage == 99.9
        assert status.current_percentage == 100.0
        assert status.meeting_sla is True
        assert status.window_hours == 720
        assert status.total_downtime_seconds == 0.0
        assert status.incidents == []

    def test_sla_status_meeting_sla(self) -> None:
        """Test meeting SLA calculation."""
        status = UptimeSLAStatus(
            current_percentage=99.95,
            meeting_sla=True,
        )

        assert status.meeting_sla is True

    def test_sla_status_not_meeting_sla(self) -> None:
        """Test not meeting SLA."""
        status = UptimeSLAStatus(
            current_percentage=99.5,
            meeting_sla=False,
        )

        assert status.meeting_sla is False


class TestUptimeService:
    """Unit tests for UptimeService."""

    def test_init_default_window(self) -> None:
        """Test default window is 30 days (720 hours)."""
        service = UptimeService()

        status = service.get_sla_status()
        assert status.window_hours == 720

    def test_init_custom_window(self) -> None:
        """Test custom window."""
        service = UptimeService(window_hours=24)

        status = service.get_sla_status()
        assert status.window_hours == 24

    def test_sla_target_constant(self) -> None:
        """Test SLA target is 99.9%."""
        assert UptimeService.SLA_TARGET == 99.9

    def test_initial_status_healthy(self) -> None:
        """Test initial status is 100% uptime."""
        service = UptimeService()

        status = service.get_sla_status()
        assert status.current_percentage == 100.0
        assert status.meeting_sla is True

    def test_record_downtime_start(self) -> None:
        """Test recording downtime start."""
        service = UptimeService()

        service.record_downtime_start("database_failure")

        assert service.get_incident_count() == 1

    def test_record_downtime_end(self) -> None:
        """Test recording downtime end."""
        service = UptimeService()

        service.record_downtime_start("test")
        incident = service.record_downtime_end()

        assert incident is not None
        assert incident.reason == "test"
        assert incident.end_time is not None

    def test_record_downtime_end_no_active(self) -> None:
        """Test recording end without active downtime."""
        service = UptimeService()

        incident = service.record_downtime_end()

        assert incident is None

    def test_double_start_ignored(self) -> None:
        """Test that double start is ignored."""
        service = UptimeService()

        service.record_downtime_start("first")
        service.record_downtime_start("second")  # Should be ignored

        # Only one incident
        assert service.get_incident_count() == 1

    def test_get_uptime_percentage(self) -> None:
        """Test get_uptime_percentage convenience method."""
        service = UptimeService()

        percentage = service.get_uptime_percentage()

        assert percentage == 100.0

    def test_is_meeting_sla(self) -> None:
        """Test is_meeting_sla convenience method."""
        service = UptimeService()

        assert service.is_meeting_sla() is True

    def test_get_incident_count_no_incidents(self) -> None:
        """Test incident count with no incidents."""
        service = UptimeService()

        assert service.get_incident_count() == 0

    def test_get_incident_count_with_active(self) -> None:
        """Test incident count includes active incident."""
        service = UptimeService()

        service.record_downtime_start("test")

        assert service.get_incident_count() == 1

    def test_get_incident_count_completed(self) -> None:
        """Test incident count with completed incidents."""
        service = UptimeService()

        service.record_downtime_start("test1")
        service.record_downtime_end()
        service.record_downtime_start("test2")
        service.record_downtime_end()

        assert service.get_incident_count() == 2

    def test_downtime_affects_percentage(self) -> None:
        """Test that downtime affects percentage."""
        service = UptimeService()

        # Wait a bit first
        time.sleep(0.05)

        # Record downtime
        service.record_downtime_start("test")
        time.sleep(0.01)
        service.record_downtime_end()

        status = service.get_sla_status()
        assert status.current_percentage < 100.0
        assert status.total_downtime_seconds > 0

    def test_active_downtime_in_percentage(self) -> None:
        """Test active downtime is included in percentage."""
        service = UptimeService()

        # Wait a bit first
        time.sleep(0.05)

        # Start downtime without ending
        service.record_downtime_start("test")
        time.sleep(0.01)

        status = service.get_sla_status()
        assert status.current_percentage < 100.0
        assert len(status.incidents) == 1

    def test_incidents_in_status(self) -> None:
        """Test incidents are included in SLA status."""
        service = UptimeService()

        service.record_downtime_start("test")
        service.record_downtime_end()

        status = service.get_sla_status()
        assert len(status.incidents) == 1
        assert status.incidents[0].reason == "test"
