"""Unit tests for ExternalMonitorClient (Story 4.9, Task 6).

Tests for external monitoring configuration and alerting.

Constitutional Constraints:
- RT-5: 99.9% uptime SLA with external monitoring
- CT-11: Silent failure destroys legitimacy - alert on downtime
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from src.infrastructure.monitoring.external_monitor import (
    AlertSeverity,
    ExternalMonitorClient,
    MonitoringAlert,
    MonitoringConfig,
)


class TestAlertSeverity:
    """Unit tests for AlertSeverity enum."""

    def test_severity_values(self) -> None:
        """Test all severity levels exist."""
        assert AlertSeverity.CRITICAL.value == "critical"
        assert AlertSeverity.HIGH.value == "high"
        assert AlertSeverity.MEDIUM.value == "medium"
        assert AlertSeverity.LOW.value == "low"
        assert AlertSeverity.INFO.value == "info"


class TestMonitoringConfig:
    """Unit tests for MonitoringConfig dataclass."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        config = MonitoringConfig()

        assert config.health_endpoint == "http://localhost:8000/v1/observer/health"
        assert config.check_interval_seconds == 30
        assert config.alert_webhook_url is None
        assert config.sla_target == 99.9
        assert config.alert_after_failures == 3

    def test_custom_values(self) -> None:
        """Test custom configuration values."""
        config = MonitoringConfig(
            health_endpoint="http://example.com/health",
            check_interval_seconds=60,
            alert_webhook_url="https://alerts.example.com/webhook",
            sla_target=99.95,
            alert_after_failures=5,
        )

        assert config.health_endpoint == "http://example.com/health"
        assert config.check_interval_seconds == 60
        assert config.alert_webhook_url == "https://alerts.example.com/webhook"
        assert config.sla_target == 99.95
        assert config.alert_after_failures == 5


class TestMonitoringAlert:
    """Unit tests for MonitoringAlert dataclass."""

    def test_alert_creation(self) -> None:
        """Test alert creation."""
        alert = MonitoringAlert(
            severity=AlertSeverity.HIGH,
            title="Test Alert",
            message="Test message",
            timestamp=datetime.now(timezone.utc),
        )

        assert alert.severity == AlertSeverity.HIGH
        assert alert.title == "Test Alert"
        assert alert.message == "Test message"
        assert alert.service == "observer-api"  # Default
        assert alert.incident_id is None  # Default

    def test_alert_with_incident_id(self) -> None:
        """Test alert with incident ID."""
        alert = MonitoringAlert(
            severity=AlertSeverity.CRITICAL,
            title="Test",
            message="Test",
            timestamp=datetime.now(timezone.utc),
            incident_id="incident-123",
        )

        assert alert.incident_id == "incident-123"


class TestExternalMonitorClient:
    """Unit tests for ExternalMonitorClient."""

    def test_init(self) -> None:
        """Test client initialization."""
        config = MonitoringConfig()
        client = ExternalMonitorClient(config)

        assert client.get_consecutive_failures() == 0
        assert not client.is_in_incident()
        assert client.get_current_incident_id() is None

    @pytest.mark.asyncio
    async def test_record_check_failure_increments_count(self) -> None:
        """Test failure recording increments count."""
        config = MonitoringConfig(alert_after_failures=5)
        client = ExternalMonitorClient(config)

        await client.record_check_failure("test")

        assert client.get_consecutive_failures() == 1
        assert not client.is_in_incident()  # Below threshold

    @pytest.mark.asyncio
    async def test_record_check_failure_creates_incident(self) -> None:
        """Test incident creation after threshold failures."""
        config = MonitoringConfig(alert_after_failures=2)
        client = ExternalMonitorClient(config)

        await client.record_check_failure("test")
        await client.record_check_failure("test")

        assert client.get_consecutive_failures() == 2
        assert client.is_in_incident()
        assert client.get_current_incident_id() is not None

    @pytest.mark.asyncio
    async def test_record_check_success_clears_count(self) -> None:
        """Test success clears failure count."""
        config = MonitoringConfig(alert_after_failures=5)
        client = ExternalMonitorClient(config)

        await client.record_check_failure("test")
        await client.record_check_failure("test")
        await client.record_check_success()

        assert client.get_consecutive_failures() == 0

    @pytest.mark.asyncio
    async def test_record_check_success_clears_incident(self) -> None:
        """Test success clears incident."""
        config = MonitoringConfig(alert_after_failures=2)
        client = ExternalMonitorClient(config)

        # Create incident
        await client.record_check_failure("test")
        await client.record_check_failure("test")
        assert client.is_in_incident()

        # Recover
        await client.record_check_success()

        assert not client.is_in_incident()
        assert client.get_current_incident_id() is None

    @pytest.mark.asyncio
    async def test_send_alert_no_webhook(self) -> None:
        """Test alert sending without webhook configured."""
        config = MonitoringConfig(alert_webhook_url=None)
        client = ExternalMonitorClient(config)

        alert = MonitoringAlert(
            severity=AlertSeverity.HIGH,
            title="Test",
            message="Test",
            timestamp=datetime.now(timezone.utc),
        )

        result = await client.send_alert(alert)

        assert result is False

    @pytest.mark.asyncio
    async def test_send_alert_with_webhook(self) -> None:
        """Test alert sending with webhook configured."""
        config = MonitoringConfig(
            alert_webhook_url="https://alerts.example.com/webhook"
        )
        client = ExternalMonitorClient(config)

        alert = MonitoringAlert(
            severity=AlertSeverity.HIGH,
            title="Test",
            message="Test",
            timestamp=datetime.now(timezone.utc),
        )

        # Mock httpx.AsyncClient
        with patch(
            "src.infrastructure.monitoring.external_monitor.httpx.AsyncClient"
        ) as mock_client:
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            result = await client.send_alert(alert)

            assert result is True

    @pytest.mark.asyncio
    async def test_send_alert_failure(self) -> None:
        """Test alert sending failure handling."""
        config = MonitoringConfig(
            alert_webhook_url="https://alerts.example.com/webhook"
        )
        client = ExternalMonitorClient(config)

        alert = MonitoringAlert(
            severity=AlertSeverity.HIGH,
            title="Test",
            message="Test",
            timestamp=datetime.now(timezone.utc),
        )

        # Mock httpx.AsyncClient to raise exception
        with patch(
            "src.infrastructure.monitoring.external_monitor.httpx.AsyncClient"
        ) as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                side_effect=Exception("Connection refused")
            )

            result = await client.send_alert(alert)

            assert result is False

    @pytest.mark.asyncio
    async def test_incident_id_format(self) -> None:
        """Test incident ID format."""
        config = MonitoringConfig(alert_after_failures=1)
        client = ExternalMonitorClient(config)

        await client.record_check_failure("test")

        incident_id = client.get_current_incident_id()
        assert incident_id is not None
        assert incident_id.startswith("observer-")
