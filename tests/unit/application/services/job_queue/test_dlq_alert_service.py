"""Unit tests for DLQAlertService (Story 0.4, AC6, HC-6).

Tests the dead letter queue monitoring and alerting service.

Constitutional Constraints:
- CT-11: Silent failure destroys legitimacy → Failed jobs MUST be visible
- HC-6: Dead-letter alerting for failed jobs → Alert when DLQ depth > 0
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.application.services.job_queue.dlq_alert_service import (
    ALERT_SEVERITY_CRITICAL,
    ALERT_SEVERITY_WARNING,
    CRITICAL_DLQ_DEPTH_THRESHOLD,
    DEFAULT_DLQ_CHECK_INTERVAL_SECONDS,
    DLQAlertService,
    create_log_alert_callback,
)
from src.domain.models.scheduled_job import DeadLetterJob
from src.infrastructure.stubs.job_scheduler_stub import JobSchedulerStub


def _create_dlq_job(job_type: str = "test_job", failure_reason: str = "Test failure") -> DeadLetterJob:
    """Create a DeadLetterJob for testing."""
    return DeadLetterJob(
        id=uuid4(),
        original_job_id=uuid4(),
        job_type=job_type,
        payload={},
        failure_reason=failure_reason,
        failed_at=datetime.now(timezone.utc),
        attempts=3,
    )


class TestDLQAlertService:
    """Tests for DLQAlertService."""

    @pytest.fixture
    def scheduler(self) -> JobSchedulerStub:
        """Create a fresh scheduler stub."""
        return JobSchedulerStub()

    @pytest.fixture
    def alert_service(
        self,
        scheduler: JobSchedulerStub,
    ) -> DLQAlertService:
        """Create a DLQ alert service."""
        return DLQAlertService(
            scheduler=scheduler,
            check_interval=1,  # Fast for testing
        )

    def test_default_check_interval(self) -> None:
        """Test default check interval is 60 seconds."""
        assert DEFAULT_DLQ_CHECK_INTERVAL_SECONDS == 60

    def test_critical_threshold(self) -> None:
        """Test critical threshold is 10 jobs."""
        assert CRITICAL_DLQ_DEPTH_THRESHOLD == 10

    @pytest.mark.asyncio
    async def test_check_now_empty_dlq(
        self,
        alert_service: DLQAlertService,
    ) -> None:
        """Test check_now returns 0 for empty DLQ."""
        depth = await alert_service.check_now()
        assert depth == 0

    @pytest.mark.asyncio
    async def test_check_now_with_dlq_jobs(
        self,
        scheduler: JobSchedulerStub,
        alert_service: DLQAlertService,
    ) -> None:
        """Test check_now returns correct depth."""
        # Add jobs to DLQ via internal _dlq dict
        dlq_job = _create_dlq_job()
        scheduler.add_dlq_job(dlq_job)

        depth = await alert_service.check_now()
        assert depth == 1

    @pytest.mark.asyncio
    async def test_check_cycle_triggers_warning_alert(
        self,
        scheduler: JobSchedulerStub,
    ) -> None:
        """Test that check cycle triggers warning alert for DLQ depth > 0."""
        alerts_received: list[tuple[str, str, int]] = []

        def capture_alert(
            severity: str,
            message: str,
            depth: int,
            jobs: list[DeadLetterJob],
        ) -> None:
            alerts_received.append((severity, message, depth))

        alert_service = DLQAlertService(
            scheduler=scheduler,
            check_interval=1,
            alert_callback=capture_alert,
        )

        # Add job to DLQ
        dlq_job = _create_dlq_job(job_type="failing_job")
        scheduler.add_dlq_job(dlq_job)

        # Run check cycle
        await alert_service._check_cycle()

        assert len(alerts_received) == 1
        severity, message, depth = alerts_received[0]
        assert severity == ALERT_SEVERITY_WARNING
        assert depth == 1
        assert "WARNING" in message

    @pytest.mark.asyncio
    async def test_check_cycle_triggers_critical_alert(
        self,
        scheduler: JobSchedulerStub,
    ) -> None:
        """Test that check cycle triggers critical alert at threshold."""
        alerts_received: list[tuple[str, str, int]] = []

        def capture_alert(
            severity: str,
            message: str,
            depth: int,
            jobs: list[DeadLetterJob],
        ) -> None:
            alerts_received.append((severity, message, depth))

        alert_service = DLQAlertService(
            scheduler=scheduler,
            check_interval=1,
            alert_callback=capture_alert,
        )

        # Add 10+ jobs to DLQ (critical threshold)
        for i in range(CRITICAL_DLQ_DEPTH_THRESHOLD):
            dlq_job = _create_dlq_job(
                job_type="critical_job",
                failure_reason=f"Failure {i}",
            )
            scheduler.add_dlq_job(dlq_job)

        # Run check cycle
        await alert_service._check_cycle()

        assert len(alerts_received) == 1
        severity, message, depth = alerts_received[0]
        assert severity == ALERT_SEVERITY_CRITICAL
        assert depth == CRITICAL_DLQ_DEPTH_THRESHOLD
        assert "CRITICAL" in message

    @pytest.mark.asyncio
    async def test_alert_suppressed_on_same_depth(
        self,
        scheduler: JobSchedulerStub,
    ) -> None:
        """Test that repeated alerts are suppressed if depth unchanged."""
        alerts_received: list[tuple[str, str, int]] = []

        def capture_alert(
            severity: str,
            message: str,
            depth: int,
            jobs: list[DeadLetterJob],
        ) -> None:
            alerts_received.append((severity, message, depth))

        alert_service = DLQAlertService(
            scheduler=scheduler,
            check_interval=1,
            alert_callback=capture_alert,
        )

        # Add job to DLQ
        dlq_job = _create_dlq_job()
        scheduler.add_dlq_job(dlq_job)

        # Run check cycle twice
        await alert_service._check_cycle()
        await alert_service._check_cycle()

        # Only one alert should be received
        assert len(alerts_received) == 1

    @pytest.mark.asyncio
    async def test_new_alert_on_depth_increase(
        self,
        scheduler: JobSchedulerStub,
    ) -> None:
        """Test that new alert fires when depth increases."""
        alerts_received: list[tuple[str, str, int]] = []

        def capture_alert(
            severity: str,
            message: str,
            depth: int,
            jobs: list[DeadLetterJob],
        ) -> None:
            alerts_received.append((severity, message, depth))

        alert_service = DLQAlertService(
            scheduler=scheduler,
            check_interval=1,
            alert_callback=capture_alert,
        )

        # Add first job
        dlq_job1 = _create_dlq_job(failure_reason="Test failure 1")
        scheduler.add_dlq_job(dlq_job1)

        await alert_service._check_cycle()
        assert len(alerts_received) == 1
        assert alerts_received[0][2] == 1  # depth = 1

        # Add second job
        dlq_job2 = _create_dlq_job(failure_reason="Test failure 2")
        scheduler.add_dlq_job(dlq_job2)

        await alert_service._check_cycle()
        assert len(alerts_received) == 2
        assert alerts_received[1][2] == 2  # depth = 2

    @pytest.mark.asyncio
    async def test_last_check_timestamp(
        self,
        alert_service: DLQAlertService,
    ) -> None:
        """Test that last check timestamp is updated."""
        assert alert_service.get_last_check() is None

        await alert_service._check_cycle()

        last_check = alert_service.get_last_check()
        assert last_check is not None
        # Should be recent
        assert (datetime.now(timezone.utc) - last_check).total_seconds() < 5

    @pytest.mark.asyncio
    async def test_is_running_flag(
        self,
        alert_service: DLQAlertService,
    ) -> None:
        """Test is_running flag."""
        assert alert_service.is_running() is False

        alert_service._running = True
        assert alert_service.is_running() is True

    def test_create_log_alert_callback(self) -> None:
        """Test create_log_alert_callback returns callable."""
        callback = create_log_alert_callback()
        assert callable(callback)

        # Should not raise when called
        callback(
            ALERT_SEVERITY_WARNING,
            "Test message",
            1,
            [],
        )

    def test_build_alert_message_warning(
        self,
        scheduler: JobSchedulerStub,
    ) -> None:
        """Test warning alert message format."""
        alert_service = DLQAlertService(scheduler=scheduler)

        jobs = [_create_dlq_job(job_type="referral_timeout")]

        message = alert_service._build_alert_message(
            depth=1,
            severity=ALERT_SEVERITY_WARNING,
            jobs=jobs,
        )

        assert "WARNING" in message
        assert "1 job(s)" in message
        assert "referral_timeout" in message

    def test_build_alert_message_critical(
        self,
        scheduler: JobSchedulerStub,
    ) -> None:
        """Test critical alert message format."""
        alert_service = DLQAlertService(scheduler=scheduler)

        jobs = [_create_dlq_job(job_type="deliberation_timeout")]

        message = alert_service._build_alert_message(
            depth=10,
            severity=ALERT_SEVERITY_CRITICAL,
            jobs=jobs,
        )

        assert "CRITICAL" in message
        assert str(CRITICAL_DLQ_DEPTH_THRESHOLD) in message
        assert "deliberation_timeout" in message
        assert "Immediate investigation required" in message
