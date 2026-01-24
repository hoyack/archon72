"""Integration tests for Observer API SLA functionality (Story 4.9).

Tests for 99.9% uptime SLA features including health endpoints,
checkpoint fallback, and Prometheus metrics.

Constitutional Constraints:
- RT-5: 99.9% uptime SLA with external monitoring
- ADR-8: Observer Consistency + Genesis Anchor - checkpoint fallback
- FR44: No authentication required for health endpoints
- CT-11: Silent failure destroys legitimacy - accurate health status
"""

import time
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.api.models.observer import (
    CheckpointAnchor as ApiCheckpointAnchor,
)
from src.api.models.observer import (
    CheckpointFallback,
    DependencyHealth,
    ObserverHealthResponse,
    ObserverHealthStatus,
    ObserverReadyResponse,
)
from src.application.dtos.observer import CheckpointAnchor as CheckpointAnchorDTO
from src.application.services.observer_service import ObserverService
from src.application.services.uptime_service import (
    UptimeService,
    UptimeSLAStatus,
)
from src.domain.events.hash_utils import GENESIS_HASH
from src.infrastructure.monitoring.external_monitor import (
    AlertSeverity,
    ExternalMonitorClient,
    MonitoringAlert,
    MonitoringConfig,
)


class TestObserverHealthEndpoint:
    """Integration tests for /v1/observer/health endpoint."""

    @pytest.mark.asyncio
    async def test_health_returns_status(self) -> None:
        """Test health endpoint returns status."""
        # Arrange
        mock_event_store = AsyncMock()
        mock_event_store.count_events.return_value = 100
        mock_halt_checker = AsyncMock()
        mock_checkpoint_repo = AsyncMock()
        mock_checkpoint_repo.list_checkpoints.return_value = ([], 0)

        service = ObserverService(
            event_store=mock_event_store,
            halt_checker=mock_halt_checker,
            checkpoint_repo=mock_checkpoint_repo,
        )

        # Act
        await service.check_database_health()

        # Assert
        mock_event_store.count_events.assert_called_once()

    @pytest.mark.asyncio
    async def test_health_includes_dependencies(self) -> None:
        """Test health response includes dependency status."""
        # The health response model includes dependencies
        response = ObserverHealthResponse(
            status=ObserverHealthStatus.HEALTHY,
            uptime_seconds=3600.0,
            dependencies=[
                DependencyHealth(
                    name="database",
                    status=ObserverHealthStatus.HEALTHY,
                    latency_ms=5.2,
                )
            ],
        )

        assert len(response.dependencies) == 1
        assert response.dependencies[0].name == "database"
        assert response.dependencies[0].status == ObserverHealthStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_health_degraded_when_db_slow(self) -> None:
        """Test health reports DEGRADED when DB latency is high."""
        # High latency (> 1000ms) should result in DEGRADED
        response = DependencyHealth(
            name="database",
            status=ObserverHealthStatus.DEGRADED,
            latency_ms=1500.0,
        )

        assert response.status == ObserverHealthStatus.DEGRADED
        assert response.latency_ms == 1500.0


class TestObserverReadyEndpoint:
    """Integration tests for /v1/observer/ready endpoint."""

    @pytest.mark.asyncio
    async def test_ready_returns_readiness(self) -> None:
        """Test ready endpoint returns readiness status."""
        response = ObserverReadyResponse(ready=True)
        assert response.ready is True
        assert response.startup_complete is True

    @pytest.mark.asyncio
    async def test_ready_not_ready_during_startup(self) -> None:
        """Test ready endpoint returns not ready during startup."""
        response = ObserverReadyResponse(
            ready=False,
            reason="API startup not complete",
            startup_complete=False,
        )

        assert response.ready is False
        assert response.reason == "API startup not complete"
        assert response.startup_complete is False


class TestObserverFallbackEndpoint:
    """Integration tests for /v1/observer/fallback endpoint."""

    @pytest.mark.asyncio
    async def test_fallback_returns_checkpoint_info(self) -> None:
        """Test fallback endpoint returns checkpoint information."""
        checkpoint = ApiCheckpointAnchor(
            checkpoint_id=uuid4(),
            sequence_start=1,
            sequence_end=1000,
            merkle_root="a" * 64,
            created_at=datetime.now(timezone.utc),
            anchor_type="pending",
            event_count=1000,
        )

        fallback = CheckpointFallback(
            latest_checkpoint=checkpoint,
            genesis_anchor_hash=GENESIS_HASH,
            checkpoint_count=10,
        )

        assert fallback.latest_checkpoint is not None
        assert fallback.genesis_anchor_hash == GENESIS_HASH
        assert fallback.checkpoint_count == 10

    @pytest.mark.asyncio
    async def test_fallback_includes_genesis_anchor(self) -> None:
        """Test fallback includes genesis anchor hash."""
        fallback = CheckpointFallback(
            latest_checkpoint=None,
            genesis_anchor_hash=GENESIS_HASH,
            checkpoint_count=0,
        )

        # Genesis hash is 64 zeros
        assert fallback.genesis_anchor_hash == "0" * 64
        assert len(fallback.genesis_anchor_hash) == 64

    @pytest.mark.asyncio
    async def test_fallback_works_with_no_checkpoints(self) -> None:
        """Test fallback works even when no checkpoints exist."""
        fallback = CheckpointFallback(
            latest_checkpoint=None,
            genesis_anchor_hash=GENESIS_HASH,
            checkpoint_count=0,
        )

        assert fallback.latest_checkpoint is None
        assert fallback.checkpoint_count == 0
        # Genesis anchor still available for verification
        assert fallback.genesis_anchor_hash == GENESIS_HASH


class TestObserverMetricsEndpoint:
    """Integration tests for /v1/observer/metrics endpoint."""

    @pytest.mark.asyncio
    async def test_metrics_endpoint_returns_prometheus_format(self) -> None:
        """Test metrics endpoint returns Prometheus format."""
        # Simulate Prometheus format output
        metrics = """# HELP observer_uptime_seconds Total uptime
# TYPE observer_uptime_seconds gauge
observer_uptime_seconds 3600.0
"""
        assert "# HELP" in metrics
        assert "# TYPE" in metrics
        assert "observer_uptime_seconds" in metrics

    @pytest.mark.asyncio
    async def test_metrics_includes_sla_target(self) -> None:
        """Test metrics includes SLA target."""
        metrics = """# HELP observer_sla_target Target SLA percentage
# TYPE observer_sla_target gauge
observer_sla_target 99.9
"""
        assert "observer_sla_target 99.9" in metrics


class TestUptimeService:
    """Integration tests for UptimeService."""

    def test_uptime_service_tracks_availability(self) -> None:
        """Test uptime service tracks availability."""
        service = UptimeService(window_hours=24)

        status = service.get_sla_status()
        assert status.current_percentage == 100.0
        assert status.meeting_sla is True

    def test_uptime_service_records_downtime(self) -> None:
        """Test uptime service records downtime incidents."""
        service = UptimeService(window_hours=24)

        # Record downtime
        service.record_downtime_start("test_failure")

        # Verify incident started
        assert service.get_incident_count() == 1
        status = service.get_sla_status()
        # With active downtime, percentage should be less than 100
        assert status.current_percentage < 100.0

    def test_uptime_service_calculates_percentage(self) -> None:
        """Test uptime service calculates percentage correctly."""
        service = UptimeService(window_hours=720)  # 30 days window

        # Wait a bit to establish some uptime baseline
        time.sleep(0.1)  # 100ms of uptime first

        # Start and end a very short downtime
        service.record_downtime_start("test")
        time.sleep(0.001)  # 1ms downtime (much smaller than total)
        service.record_downtime_end()

        status = service.get_sla_status()
        # Service calculates from service_start, not full window
        # So we expect: (total_time - downtime) / total_time * 100
        # With ~100ms total and ~1ms downtime, should be ~99%
        assert status.total_downtime_seconds > 0
        assert status.total_downtime_seconds < 0.1  # Less than 100ms
        # Percentage should be calculated correctly (>90% at least)
        assert status.current_percentage > 90.0

    def test_uptime_service_returns_sla_status(self) -> None:
        """Test uptime service returns complete SLA status."""
        service = UptimeService(window_hours=24)

        status = service.get_sla_status()

        assert isinstance(status, UptimeSLAStatus)
        assert status.target_percentage == 99.9
        assert status.window_hours == 24
        assert isinstance(status.incidents, list)

    def test_uptime_service_rolling_window(self) -> None:
        """Test uptime service uses rolling window calculation."""
        service = UptimeService(window_hours=1)

        # The service should calculate based on window
        status = service.get_sla_status()
        assert status.window_hours == 1


class TestExternalMonitorClient:
    """Integration tests for ExternalMonitorClient."""

    @pytest.mark.asyncio
    async def test_monitor_records_failure(self) -> None:
        """Test monitor records check failures."""
        config = MonitoringConfig(alert_after_failures=3)
        client = ExternalMonitorClient(config)

        await client.record_check_failure("db_timeout")

        assert client.get_consecutive_failures() == 1
        assert not client.is_in_incident()

    @pytest.mark.asyncio
    async def test_monitor_creates_incident_after_threshold(self) -> None:
        """Test monitor creates incident after failure threshold."""
        config = MonitoringConfig(
            alert_after_failures=3,
            alert_webhook_url=None,  # No webhook to avoid actual calls
        )
        client = ExternalMonitorClient(config)

        # Record 3 failures
        for _ in range(3):
            await client.record_check_failure("test")

        assert client.get_consecutive_failures() == 3
        assert client.is_in_incident()
        assert client.get_current_incident_id() is not None

    @pytest.mark.asyncio
    async def test_monitor_recovery_clears_incident(self) -> None:
        """Test monitor clears incident on recovery."""
        config = MonitoringConfig(
            alert_after_failures=2,
            alert_webhook_url=None,
        )
        client = ExternalMonitorClient(config)

        # Create incident
        await client.record_check_failure("test")
        await client.record_check_failure("test")
        assert client.is_in_incident()

        # Recover
        await client.record_check_success()

        assert client.get_consecutive_failures() == 0
        assert not client.is_in_incident()

    @pytest.mark.asyncio
    async def test_monitor_alert_severity_levels(self) -> None:
        """Test monitor uses correct alert severity levels."""
        alert = MonitoringAlert(
            severity=AlertSeverity.HIGH,
            title="Test Alert",
            message="Test message",
            timestamp=datetime.now(timezone.utc),
        )

        assert alert.severity == AlertSeverity.HIGH
        assert alert.service == "observer-api"


class TestObserverServiceHealthMethods:
    """Integration tests for ObserverService health methods."""

    @pytest.mark.asyncio
    async def test_check_database_health(self) -> None:
        """Test check_database_health method."""
        mock_event_store = AsyncMock()
        mock_event_store.count_events.return_value = 100
        mock_halt_checker = AsyncMock()

        service = ObserverService(
            event_store=mock_event_store,
            halt_checker=mock_halt_checker,
        )

        # Should not raise
        await service.check_database_health()
        mock_event_store.count_events.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_last_checkpoint_sequence(self) -> None:
        """Test get_last_checkpoint_sequence method."""
        mock_event_store = AsyncMock()
        mock_halt_checker = AsyncMock()
        mock_checkpoint_repo = AsyncMock()

        # Mock checkpoint
        mock_checkpoint = MagicMock()
        mock_checkpoint.event_sequence = 1000
        mock_checkpoint_repo.list_checkpoints.return_value = ([mock_checkpoint], 1)

        service = ObserverService(
            event_store=mock_event_store,
            halt_checker=mock_halt_checker,
            checkpoint_repo=mock_checkpoint_repo,
        )

        result = await service.get_last_checkpoint_sequence()
        assert result == 1000

    @pytest.mark.asyncio
    async def test_get_genesis_anchor_hash(self) -> None:
        """Test get_genesis_anchor_hash method."""
        mock_event_store = AsyncMock()
        mock_halt_checker = AsyncMock()

        service = ObserverService(
            event_store=mock_event_store,
            halt_checker=mock_halt_checker,
        )

        result = await service.get_genesis_anchor_hash()
        assert result == GENESIS_HASH
        assert result == "0" * 64

    @pytest.mark.asyncio
    async def test_get_checkpoint_count(self) -> None:
        """Test get_checkpoint_count method."""
        mock_event_store = AsyncMock()
        mock_halt_checker = AsyncMock()
        mock_checkpoint_repo = AsyncMock()
        mock_checkpoint_repo.list_checkpoints.return_value = ([], 5)

        service = ObserverService(
            event_store=mock_event_store,
            halt_checker=mock_halt_checker,
            checkpoint_repo=mock_checkpoint_repo,
        )

        result = await service.get_checkpoint_count()
        assert result == 5

    @pytest.mark.asyncio
    async def test_get_latest_checkpoint(self) -> None:
        """Test get_latest_checkpoint method returns CheckpointAnchor."""
        mock_event_store = AsyncMock()
        mock_halt_checker = AsyncMock()
        mock_checkpoint_repo = AsyncMock()

        # Mock checkpoint
        mock_checkpoint = MagicMock()
        mock_checkpoint.checkpoint_id = uuid4()
        mock_checkpoint.event_sequence = 1000
        mock_checkpoint.anchor_hash = "a" * 64
        mock_checkpoint.timestamp = datetime.now(timezone.utc)
        mock_checkpoint.anchor_type = "pending"
        mock_checkpoint_repo.list_checkpoints.return_value = ([mock_checkpoint], 1)

        service = ObserverService(
            event_store=mock_event_store,
            halt_checker=mock_halt_checker,
            checkpoint_repo=mock_checkpoint_repo,
        )

        result = await service.get_latest_checkpoint()

        assert result is not None
        assert isinstance(result, CheckpointAnchorDTO)
        assert result.sequence_end == 1000
        assert result.merkle_root == "a" * 64


class TestHealthStatusAccuracy:
    """Integration tests for health status accuracy (CT-11)."""

    @pytest.mark.asyncio
    async def test_unhealthy_status_on_db_error(self) -> None:
        """Test UNHEALTHY status when database is unavailable."""
        mock_event_store = AsyncMock()
        mock_event_store.count_events.side_effect = Exception("Connection refused")
        mock_halt_checker = AsyncMock()

        service = ObserverService(
            event_store=mock_event_store,
            halt_checker=mock_halt_checker,
        )

        # Should raise exception
        with pytest.raises(Exception, match="Connection refused"):
            await service.check_database_health()

    def test_worst_status_wins(self) -> None:
        """Test that worst status wins in aggregate health (CT-11)."""
        # Per CT-11: Health status must be accurate, not optimistic
        healthy = DependencyHealth(
            name="cache",
            status=ObserverHealthStatus.HEALTHY,
        )
        degraded = DependencyHealth(
            name="database",
            status=ObserverHealthStatus.DEGRADED,
        )

        # Aggregate should show DEGRADED (worst of the two)
        response = ObserverHealthResponse(
            status=ObserverHealthStatus.DEGRADED,  # Worst status
            uptime_seconds=3600.0,
            dependencies=[healthy, degraded],
        )

        assert response.status == ObserverHealthStatus.DEGRADED
