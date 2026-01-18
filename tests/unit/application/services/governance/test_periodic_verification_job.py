"""Tests for PeriodicVerificationJob.

Story: consent-gov-10.2: Anti-Metrics Verification

These tests verify that:
1. Job runs on schedule (AC: 3)
2. Job logs results (AC: 3)
3. Job alerts on violations (AC: 3)
4. Job configuration works correctly
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from src.application.ports.governance.anti_metrics_verification_port import (
    RouteInfo,
    RouteInspectorPort,
    SchemaInspectorPort,
)
from src.application.ports.time_authority import TimeAuthorityProtocol
from src.application.services.governance.anti_metrics_verification_service import (
    AntiMetricsVerificationService,
)
from src.application.services.governance.periodic_verification_job import (
    JobRunResult,
    PeriodicVerificationJob,
    VerificationJobConfig,
)
from src.domain.governance.antimetrics.verification import (
    VerificationReport,
    VerificationStatus,
)


class FakeTimeAuthority(TimeAuthorityProtocol):
    """Fake time authority for testing."""

    def __init__(self) -> None:
        self._time = datetime.now(timezone.utc)
        self._advance_ms = 0.0

    def now(self) -> datetime:
        return self._time

    def utcnow(self) -> datetime:
        result = self._time
        if self._advance_ms > 0:
            from datetime import timedelta

            self._time = self._time + timedelta(milliseconds=self._advance_ms)
        return result

    def monotonic(self) -> float:
        return 0.0

    def advance(self, seconds: float) -> None:
        """Advance time by given seconds."""
        from datetime import timedelta

        self._time = self._time + timedelta(seconds=seconds)


class FakeSchemaInspector(SchemaInspectorPort):
    """Fake schema inspector for testing."""

    async def get_all_tables(self) -> list[str]:
        return ["tasks", "clusters"]

    async def get_all_columns(self) -> list[tuple[str, str]]:
        return [("tasks", "id"), ("tasks", "status")]


class FakeRouteInspector(RouteInspectorPort):
    """Fake route inspector for testing."""

    async def get_all_routes(self) -> list[RouteInfo]:
        return [RouteInfo(method="GET", path="/v1/health")]


@pytest.fixture
def time_authority() -> FakeTimeAuthority:
    """Provide fake time authority."""
    return FakeTimeAuthority()


@pytest.fixture
def verification_service(
    time_authority: FakeTimeAuthority,
) -> AntiMetricsVerificationService:
    """Provide verification service."""
    return AntiMetricsVerificationService(
        schema_inspector=FakeSchemaInspector(),
        route_inspector=FakeRouteInspector(),
        event_emitter=None,  # Independent mode
        time_authority=time_authority,
    )


@pytest.fixture
def job_config() -> VerificationJobConfig:
    """Provide default job configuration."""
    return VerificationJobConfig(
        interval_seconds=60,  # 1 minute for testing
        run_on_start=False,
    )


@pytest.fixture
def verification_job(
    verification_service: AntiMetricsVerificationService,
    time_authority: FakeTimeAuthority,
    job_config: VerificationJobConfig,
) -> PeriodicVerificationJob:
    """Provide periodic verification job."""
    return PeriodicVerificationJob(
        verification_service=verification_service,
        time_authority=time_authority,
        config=job_config,
    )


class TestVerificationJobConfig:
    """Tests for VerificationJobConfig."""

    def test_default_config(self) -> None:
        """Default configuration uses 24 hours."""
        config = VerificationJobConfig()

        assert config.interval_seconds == 86400
        assert config.alert_on_violations is True
        assert config.run_on_start is True

    def test_custom_config(self) -> None:
        """Custom configuration works."""
        config = VerificationJobConfig(
            interval_seconds=3600,
            alert_on_violations=False,
            run_on_start=False,
        )

        assert config.interval_seconds == 3600
        assert config.alert_on_violations is False
        assert config.run_on_start is False

    def test_minimum_interval_validation(self) -> None:
        """Interval must be at least 60 seconds."""
        with pytest.raises(ValueError, match="at least 60"):
            VerificationJobConfig(interval_seconds=30)


class TestJobRunResult:
    """Tests for JobRunResult."""

    def test_success_property(self) -> None:
        """success property reflects report presence."""
        result_success = JobRunResult(
            run_id=uuid4(),
            started_at=datetime.now(timezone.utc),
            report=MagicMock(spec=VerificationReport),
        )
        assert result_success.success is True

        result_failure = JobRunResult(
            run_id=uuid4(),
            started_at=datetime.now(timezone.utc),
            error="Something went wrong",
        )
        assert result_failure.success is False

    def test_passed_property(self) -> None:
        """passed property reflects verification status."""
        mock_report_pass = MagicMock(spec=VerificationReport)
        mock_report_pass.overall_status = VerificationStatus.PASS
        result_pass = JobRunResult(
            run_id=uuid4(),
            started_at=datetime.now(timezone.utc),
            report=mock_report_pass,
        )
        assert result_pass.passed is True

        mock_report_fail = MagicMock(spec=VerificationReport)
        mock_report_fail.overall_status = VerificationStatus.FAIL
        result_fail = JobRunResult(
            run_id=uuid4(),
            started_at=datetime.now(timezone.utc),
            report=mock_report_fail,
        )
        assert result_fail.passed is False


class TestPeriodicVerificationJob:
    """Tests for PeriodicVerificationJob."""

    @pytest.mark.asyncio
    async def test_run_once_executes_verification(
        self,
        verification_job: PeriodicVerificationJob,
    ) -> None:
        """run_once executes a single verification."""
        result = await verification_job.run_once()

        assert result.success is True
        assert result.report is not None
        assert result.error is None
        assert verification_job.run_count == 1

    @pytest.mark.asyncio
    async def test_run_once_updates_last_run(
        self,
        verification_job: PeriodicVerificationJob,
    ) -> None:
        """run_once updates last_run property."""
        assert verification_job.last_run is None

        result = await verification_job.run_once()

        assert verification_job.last_run is result

    @pytest.mark.asyncio
    async def test_run_once_updates_history(
        self,
        verification_job: PeriodicVerificationJob,
    ) -> None:
        """run_once adds to history."""
        await verification_job.run_once()
        await verification_job.run_once()
        await verification_job.run_once()

        assert len(verification_job.history) == 3
        assert verification_job.run_count == 3

    @pytest.mark.asyncio
    async def test_start_stop_lifecycle(
        self,
        verification_job: PeriodicVerificationJob,
    ) -> None:
        """Job can be started and stopped."""
        assert verification_job.is_running is False

        await verification_job.start()
        assert verification_job.is_running is True

        await verification_job.stop()
        assert verification_job.is_running is False

    @pytest.mark.asyncio
    async def test_start_with_run_on_start(
        self,
        verification_service: AntiMetricsVerificationService,
        time_authority: FakeTimeAuthority,
    ) -> None:
        """Start runs immediately when run_on_start is True."""
        config = VerificationJobConfig(
            interval_seconds=3600,
            run_on_start=True,
        )
        job = PeriodicVerificationJob(
            verification_service=verification_service,
            time_authority=time_authority,
            config=config,
        )

        await job.start()

        # Should have run once
        assert job.run_count == 1

        await job.stop()

    @pytest.mark.asyncio
    async def test_cannot_start_twice(
        self,
        verification_job: PeriodicVerificationJob,
    ) -> None:
        """Cannot start an already running job."""
        await verification_job.start()

        with pytest.raises(RuntimeError, match="already running"):
            await verification_job.start()

        await verification_job.stop()

    @pytest.mark.asyncio
    async def test_stop_idempotent(
        self,
        verification_job: PeriodicVerificationJob,
    ) -> None:
        """Stop is idempotent."""
        # Stop without start - should not raise
        await verification_job.stop()

        # Start and stop multiple times
        await verification_job.start()
        await verification_job.stop()
        await verification_job.stop()  # Second stop - should not raise

    @pytest.mark.asyncio
    async def test_alert_callback_invoked_on_violations(
        self,
        time_authority: FakeTimeAuthority,
    ) -> None:
        """Alert callback is invoked when violations are found."""

        # Create service with violations
        class DirtySchemaInspector(SchemaInspectorPort):
            async def get_all_tables(self) -> list[str]:
                return ["cluster_metrics"]  # Prohibited!

            async def get_all_columns(self) -> list[tuple[str, str]]:
                return []

        service = AntiMetricsVerificationService(
            schema_inspector=DirtySchemaInspector(),
            route_inspector=FakeRouteInspector(),
            event_emitter=None,
            time_authority=time_authority,
        )

        config = VerificationJobConfig(
            interval_seconds=60,
            run_on_start=False,
            alert_on_violations=True,
        )

        job = PeriodicVerificationJob(
            verification_service=service,
            time_authority=time_authority,
            config=config,
        )

        # Set up alert callback
        alert_reports: list[VerificationReport] = []
        job.set_alert_callback(lambda r: alert_reports.append(r))

        # Run verification
        await job.run_once()

        # Alert should have been triggered
        assert len(alert_reports) == 1
        assert alert_reports[0].overall_status == VerificationStatus.FAIL

    @pytest.mark.asyncio
    async def test_alert_callback_not_invoked_on_pass(
        self,
        verification_job: PeriodicVerificationJob,
    ) -> None:
        """Alert callback is not invoked when verification passes."""
        alert_called = False

        def alert_callback(report: VerificationReport) -> None:
            nonlocal alert_called
            alert_called = True

        verification_job.set_alert_callback(alert_callback)

        await verification_job.run_once()

        assert alert_called is False

    @pytest.mark.asyncio
    async def test_get_stats(
        self,
        verification_job: PeriodicVerificationJob,
    ) -> None:
        """get_stats returns correct statistics."""
        # Run a few times
        await verification_job.run_once()
        await verification_job.run_once()

        stats = verification_job.get_stats()

        assert stats["running"] is False
        assert stats["total_runs"] == 2
        assert stats["successful_runs"] == 2
        assert stats["passed_runs"] == 2
        assert stats["failed_runs"] == 0
        assert stats["last_run_at"] is not None
        assert stats["last_run_passed"] is True
        assert stats["interval_seconds"] == 60

    @pytest.mark.asyncio
    async def test_history_limited_to_100(
        self,
        verification_job: PeriodicVerificationJob,
    ) -> None:
        """History is limited to last 100 runs."""
        # Run 105 times
        for _ in range(105):
            await verification_job.run_once()

        assert verification_job.run_count == 105
        assert len(verification_job.history) == 100

    @pytest.mark.asyncio
    async def test_run_once_handles_errors(
        self,
        time_authority: FakeTimeAuthority,
    ) -> None:
        """run_once handles errors gracefully."""

        # Create service that throws
        class FailingSchemaInspector(SchemaInspectorPort):
            async def get_all_tables(self) -> list[str]:
                raise RuntimeError("Database connection failed")

            async def get_all_columns(self) -> list[tuple[str, str]]:
                return []

        service = AntiMetricsVerificationService(
            schema_inspector=FailingSchemaInspector(),
            route_inspector=FakeRouteInspector(),
            event_emitter=None,
            time_authority=time_authority,
        )

        job = PeriodicVerificationJob(
            verification_service=service,
            time_authority=time_authority,
            config=VerificationJobConfig(interval_seconds=60, run_on_start=False),
        )

        result = await job.run_once()

        assert result.success is False
        assert result.error is not None
        assert "Database connection failed" in result.error
        assert job.run_count == 1

    @pytest.mark.asyncio
    async def test_set_alert_callback_none_disables(
        self,
        time_authority: FakeTimeAuthority,
    ) -> None:
        """Setting alert callback to None disables alerts."""

        # Create service with violations
        class DirtySchemaInspector(SchemaInspectorPort):
            async def get_all_tables(self) -> list[str]:
                return ["cluster_metrics"]

            async def get_all_columns(self) -> list[tuple[str, str]]:
                return []

        service = AntiMetricsVerificationService(
            schema_inspector=DirtySchemaInspector(),
            route_inspector=FakeRouteInspector(),
            event_emitter=None,
            time_authority=time_authority,
        )

        job = PeriodicVerificationJob(
            verification_service=service,
            time_authority=time_authority,
            config=VerificationJobConfig(
                interval_seconds=60,
                run_on_start=False,
                alert_on_violations=True,
            ),
        )

        alert_called = False

        def callback(r: VerificationReport) -> None:
            nonlocal alert_called
            alert_called = True

        job.set_alert_callback(callback)
        job.set_alert_callback(None)  # Disable

        await job.run_once()

        assert alert_called is False
