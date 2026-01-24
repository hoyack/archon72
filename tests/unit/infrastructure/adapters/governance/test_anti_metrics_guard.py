"""Tests for AntiMetricsGuard implementation.

Story: consent-gov-10.1: Anti-Metrics Data Layer Enforcement

These tests verify that:
1. Guard blocks metric table creation (AC: 1, 2, 3, 7)
2. Guard blocks metric column addition
3. Guard validates schema on startup
4. Guard emits violation events
5. Guard emits enforcement event on startup (AC: 6)
6. No metric storage paths exist (AC: 8)
"""

import contextlib
from datetime import datetime, timezone
from typing import Any

import pytest

from src.application.ports.governance.anti_metrics_port import (
    EventEmitterPort,
    SchemaValidatorPort,
)
from src.domain.governance.antimetrics import (
    AntiMetricsViolationError,
    ProhibitedPattern,
)
from src.domain.ports.time_authority import TimeAuthorityProtocol
from src.infrastructure.adapters.governance.anti_metrics_guard import (
    AntiMetricsGuard,
)


class FakeTimeAuthority(TimeAuthorityProtocol):
    """Fake time authority for testing."""

    def __init__(self, fixed_time: datetime | None = None) -> None:
        self._fixed_time = fixed_time or datetime.now(timezone.utc)
        self._monotonic_value = 0.0

    def now(self) -> datetime:
        return self._fixed_time

    def utcnow(self) -> datetime:
        return self._fixed_time

    def monotonic(self) -> float:
        return self._monotonic_value


class FakeSchemaValidator(SchemaValidatorPort):
    """Fake schema validator for testing."""

    def __init__(
        self,
        metric_tables: list[str] | None = None,
        metric_columns: list[tuple[str, str]] | None = None,
    ) -> None:
        self._metric_tables = metric_tables or []
        self._metric_columns = metric_columns or []

    async def check_for_metric_tables(self) -> list[str]:
        return self._metric_tables

    async def check_for_metric_columns(self) -> list[tuple[str, str]]:
        return self._metric_columns


class FakeEventEmitter(EventEmitterPort):
    """Fake event emitter for testing."""

    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    async def emit(
        self,
        event_type: str,
        actor: str,
        payload: dict,
    ) -> None:
        self.events.append(
            {
                "event_type": event_type,
                "actor": actor,
                "payload": payload,
            }
        )

    def get_events(self, event_type: str) -> list[dict[str, Any]]:
        return [e for e in self.events if e["event_type"] == event_type]


@pytest.fixture
def time_authority() -> FakeTimeAuthority:
    """Provide fake time authority."""
    return FakeTimeAuthority()


@pytest.fixture
def clean_schema_validator() -> FakeSchemaValidator:
    """Provide schema validator that reports no violations."""
    return FakeSchemaValidator()


@pytest.fixture
def event_emitter() -> FakeEventEmitter:
    """Provide fake event emitter."""
    return FakeEventEmitter()


@pytest.fixture
def anti_metrics_guard(
    clean_schema_validator: FakeSchemaValidator,
    event_emitter: FakeEventEmitter,
    time_authority: FakeTimeAuthority,
) -> AntiMetricsGuard:
    """Provide anti-metrics guard with clean schema."""
    return AntiMetricsGuard(
        schema_validator=clean_schema_validator,
        event_emitter=event_emitter,
        time_authority=time_authority,
    )


class TestAntiMetricsGuardStartup:
    """Tests for enforce_on_startup method."""

    @pytest.mark.asyncio
    async def test_startup_enforcement_with_clean_schema(
        self,
        anti_metrics_guard: AntiMetricsGuard,
        event_emitter: FakeEventEmitter,
    ) -> None:
        """Anti-metrics enforced on startup with clean schema (AC: 6)."""
        await anti_metrics_guard.enforce_on_startup()

        # Enforcement event should be emitted
        events = event_emitter.get_events("constitutional.anti_metrics.enforced")
        assert len(events) == 1

        payload = events[0]["payload"]
        assert payload["schema_valid"] is True
        assert payload["violations_found"] == 0

    @pytest.mark.asyncio
    async def test_startup_blocks_metric_tables(
        self,
        event_emitter: FakeEventEmitter,
        time_authority: FakeTimeAuthority,
    ) -> None:
        """Startup fails if metric tables exist."""
        dirty_schema = FakeSchemaValidator(
            metric_tables=["cluster_metrics", "task_performance"]
        )
        guard = AntiMetricsGuard(
            schema_validator=dirty_schema,
            event_emitter=event_emitter,
            time_authority=time_authority,
        )

        with pytest.raises(AntiMetricsViolationError) as exc_info:
            await guard.enforce_on_startup()

        assert "cluster_metrics" in str(exc_info.value)
        assert "task_performance" in str(exc_info.value)

        # Violation events should be emitted
        violation_events = event_emitter.get_events(
            "constitutional.violation.anti_metrics"
        )
        assert len(violation_events) == 2

    @pytest.mark.asyncio
    async def test_startup_blocks_metric_columns(
        self,
        event_emitter: FakeEventEmitter,
        time_authority: FakeTimeAuthority,
    ) -> None:
        """Startup fails if metric columns exist."""
        dirty_schema = FakeSchemaValidator(
            metric_columns=[("users", "completion_rate"), ("tasks", "engagement_score")]
        )
        guard = AntiMetricsGuard(
            schema_validator=dirty_schema,
            event_emitter=event_emitter,
            time_authority=time_authority,
        )

        with pytest.raises(AntiMetricsViolationError) as exc_info:
            await guard.enforce_on_startup()

        assert "metric columns" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_enforcement_status_after_startup(
        self,
        anti_metrics_guard: AntiMetricsGuard,
    ) -> None:
        """Enforcement status is correct after startup."""
        await anti_metrics_guard.enforce_on_startup()

        status = await anti_metrics_guard.get_enforcement_status()
        assert status["enforced"] is True
        assert status["schema_valid"] is True
        assert status["violations_detected"] == 0
        assert status["last_check"] is not None


class TestTableCreationBlocking:
    """Tests for check_table_creation method."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "table_name",
        [
            "cluster_metrics",
            "task_metrics",
            "user_metrics",
            "participant_metrics",
        ],
    )
    async def test_metrics_table_blocked(
        self,
        anti_metrics_guard: AntiMetricsGuard,
        table_name: str,
    ) -> None:
        """Tables ending in _metrics are blocked (AC: 1)."""
        with pytest.raises(AntiMetricsViolationError):
            await anti_metrics_guard.check_table_creation(table_name)

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "table_name",
        [
            "task_performance",
            "cluster_performance",
            "participant_performance",
        ],
    )
    async def test_performance_table_blocked(
        self,
        anti_metrics_guard: AntiMetricsGuard,
        table_name: str,
    ) -> None:
        """Tables ending in _performance are blocked (AC: 1)."""
        with pytest.raises(AntiMetricsViolationError):
            await anti_metrics_guard.check_table_creation(table_name)

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "table_name",
        [
            "user_engagement",
            "participant_engagement",
        ],
    )
    async def test_engagement_table_blocked(
        self,
        anti_metrics_guard: AntiMetricsGuard,
        table_name: str,
    ) -> None:
        """Tables ending in _engagement are blocked (AC: 3)."""
        with pytest.raises(AntiMetricsViolationError):
            await anti_metrics_guard.check_table_creation(table_name)

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "table_name",
        [
            "user_retention",
            "participant_retention",
        ],
    )
    async def test_retention_table_blocked(
        self,
        anti_metrics_guard: AntiMetricsGuard,
        table_name: str,
    ) -> None:
        """Tables ending in _retention are blocked (AC: 3)."""
        with pytest.raises(AntiMetricsViolationError):
            await anti_metrics_guard.check_table_creation(table_name)

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "table_name",
        [
            "user_analytics",
            "task_analytics",
            "cluster_analytics",
        ],
    )
    async def test_analytics_table_blocked(
        self,
        anti_metrics_guard: AntiMetricsGuard,
        table_name: str,
    ) -> None:
        """Tables ending in _analytics are blocked."""
        with pytest.raises(AntiMetricsViolationError):
            await anti_metrics_guard.check_table_creation(table_name)

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "table_name",
        [
            "participant_scores",
            "completion_rates",
            "session_tracking",
        ],
    )
    async def test_specific_tables_blocked(
        self,
        anti_metrics_guard: AntiMetricsGuard,
        table_name: str,
    ) -> None:
        """Specific prohibited tables are blocked (AC: 2)."""
        with pytest.raises(AntiMetricsViolationError):
            await anti_metrics_guard.check_table_creation(table_name)

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "table_name",
        [
            "tasks",
            "clusters",
            "participants",
            "events",
            "governance_events",
            "witness_statements",
            "panel_findings",
            "task_assignments",
            "consent_records",
            "coercion_filter_logs",
        ],
    )
    async def test_legitimate_tables_allowed(
        self,
        anti_metrics_guard: AntiMetricsGuard,
        table_name: str,
    ) -> None:
        """Legitimate governance tables are allowed."""
        # Should not raise
        await anti_metrics_guard.check_table_creation(table_name)

    @pytest.mark.asyncio
    async def test_violation_event_emitted_on_block(
        self,
        anti_metrics_guard: AntiMetricsGuard,
        event_emitter: FakeEventEmitter,
    ) -> None:
        """Violation event is emitted when table creation is blocked (AC: 7)."""
        with pytest.raises(AntiMetricsViolationError):
            await anti_metrics_guard.check_table_creation("cluster_metrics")

        violation_events = event_emitter.get_events(
            "constitutional.violation.anti_metrics"
        )
        assert len(violation_events) == 1

        payload = violation_events[0]["payload"]
        assert "cluster_metrics" in payload["description"]


class TestColumnAdditionBlocking:
    """Tests for check_column_addition method."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "column_name",
        [
            "completion_rate",
            "success_rate",
            "failure_rate",
        ],
    )
    async def test_rate_columns_blocked(
        self,
        anti_metrics_guard: AntiMetricsGuard,
        column_name: str,
    ) -> None:
        """Rate tracking columns are blocked (AC: 2)."""
        with pytest.raises(AntiMetricsViolationError):
            await anti_metrics_guard.check_column_addition("any_table", column_name)

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "column_name",
        [
            "performance_score",
            "engagement_score",
            "retention_score",
            "activity_score",
        ],
    )
    async def test_score_columns_blocked(
        self,
        anti_metrics_guard: AntiMetricsGuard,
        column_name: str,
    ) -> None:
        """Score tracking columns are blocked (AC: 1, 3)."""
        with pytest.raises(AntiMetricsViolationError):
            await anti_metrics_guard.check_column_addition("any_table", column_name)

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "column_name",
        [
            "session_count",
            "login_count",
            "task_completion_count",
        ],
    )
    async def test_count_columns_blocked(
        self,
        anti_metrics_guard: AntiMetricsGuard,
        column_name: str,
    ) -> None:
        """Count tracking columns are blocked (AC: 3)."""
        with pytest.raises(AntiMetricsViolationError):
            await anti_metrics_guard.check_column_addition("any_table", column_name)

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "column_name",
        [
            "id",
            "created_at",
            "updated_at",
            "cluster_id",
            "task_id",
            "participant_id",
            "status",
            "content",
            "description",
            "name",
        ],
    )
    async def test_legitimate_columns_allowed(
        self,
        anti_metrics_guard: AntiMetricsGuard,
        column_name: str,
    ) -> None:
        """Legitimate governance columns are allowed."""
        # Should not raise
        await anti_metrics_guard.check_column_addition("any_table", column_name)


class TestNoMetricStoragePaths:
    """Tests ensuring no metric storage paths exist (AC: 8).

    These tests verify STRUCTURAL ABSENCE - the methods that would
    store metrics simply don't exist on the guard.
    """

    def test_no_store_participant_performance_method(
        self,
        anti_metrics_guard: AntiMetricsGuard,
    ) -> None:
        """No store_participant_performance method exists."""
        assert not hasattr(anti_metrics_guard, "store_participant_performance")
        assert not hasattr(anti_metrics_guard, "save_performance")
        assert not hasattr(anti_metrics_guard, "record_performance")

    def test_no_calculate_completion_rate_method(
        self,
        anti_metrics_guard: AntiMetricsGuard,
    ) -> None:
        """No calculate_completion_rate method exists."""
        assert not hasattr(anti_metrics_guard, "calculate_completion_rate")
        assert not hasattr(anti_metrics_guard, "compute_success_rate")
        assert not hasattr(anti_metrics_guard, "compute_failure_rate")

    def test_no_track_engagement_method(
        self,
        anti_metrics_guard: AntiMetricsGuard,
    ) -> None:
        """No track_engagement method exists."""
        assert not hasattr(anti_metrics_guard, "track_engagement")
        assert not hasattr(anti_metrics_guard, "record_engagement")
        assert not hasattr(anti_metrics_guard, "update_engagement_score")

    def test_no_track_retention_method(
        self,
        anti_metrics_guard: AntiMetricsGuard,
    ) -> None:
        """No track_retention method exists."""
        assert not hasattr(anti_metrics_guard, "track_retention")
        assert not hasattr(anti_metrics_guard, "record_retention")
        assert not hasattr(anti_metrics_guard, "update_retention_score")

    def test_no_session_tracking_method(
        self,
        anti_metrics_guard: AntiMetricsGuard,
    ) -> None:
        """No session tracking method exists."""
        assert not hasattr(anti_metrics_guard, "record_session")
        assert not hasattr(anti_metrics_guard, "track_session")
        assert not hasattr(anti_metrics_guard, "log_login")

    def test_no_save_metrics_method(
        self,
        anti_metrics_guard: AntiMetricsGuard,
    ) -> None:
        """No generic save metrics method exists."""
        assert not hasattr(anti_metrics_guard, "save_metrics")
        assert not hasattr(anti_metrics_guard, "store_metrics")
        assert not hasattr(anti_metrics_guard, "write_metrics")

    def test_no_get_performance_history_method(
        self,
        anti_metrics_guard: AntiMetricsGuard,
    ) -> None:
        """No get performance history method exists."""
        assert not hasattr(anti_metrics_guard, "get_performance_history")
        assert not hasattr(anti_metrics_guard, "get_metrics_history")
        assert not hasattr(anti_metrics_guard, "get_analytics")


class TestPatternClassification:
    """Tests for pattern classification."""

    @pytest.mark.asyncio
    async def test_get_prohibited_patterns(
        self,
        anti_metrics_guard: AntiMetricsGuard,
    ) -> None:
        """Can get list of all prohibited patterns."""
        patterns = await anti_metrics_guard.get_prohibited_patterns()

        assert ProhibitedPattern.PARTICIPANT_PERFORMANCE in patterns
        assert ProhibitedPattern.COMPLETION_RATE in patterns
        assert ProhibitedPattern.ENGAGEMENT_TRACKING in patterns
        assert ProhibitedPattern.RETENTION_METRICS in patterns
        assert ProhibitedPattern.SESSION_TRACKING in patterns
        assert len(patterns) == 6


class TestEnforcementStatus:
    """Tests for enforcement status tracking."""

    @pytest.mark.asyncio
    async def test_initial_status(
        self,
        anti_metrics_guard: AntiMetricsGuard,
    ) -> None:
        """Initial status before enforcement."""
        status = await anti_metrics_guard.get_enforcement_status()

        assert status["enforced"] is False
        assert status["last_check"] is None
        assert status["violations_detected"] == 0
        assert status["schema_valid"] is False

    @pytest.mark.asyncio
    async def test_status_after_successful_enforcement(
        self,
        anti_metrics_guard: AntiMetricsGuard,
    ) -> None:
        """Status after successful enforcement."""
        await anti_metrics_guard.enforce_on_startup()

        status = await anti_metrics_guard.get_enforcement_status()

        assert status["enforced"] is True
        assert status["last_check"] is not None
        assert status["violations_detected"] == 0
        assert status["schema_valid"] is True

    @pytest.mark.asyncio
    async def test_violation_count_increases(
        self,
        anti_metrics_guard: AntiMetricsGuard,
    ) -> None:
        """Violation count increases with each blocked attempt."""
        # Initial count
        status = await anti_metrics_guard.get_enforcement_status()
        initial_count = status["violations_detected"]

        # Trigger some violations
        for table in ["cluster_metrics", "task_performance", "user_engagement"]:
            with contextlib.suppress(AntiMetricsViolationError):
                await anti_metrics_guard.check_table_creation(table)

        status = await anti_metrics_guard.get_enforcement_status()
        assert status["violations_detected"] == initial_count + 3
