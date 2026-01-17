"""Tests for TaskTimeoutService.

Story: consent-gov-2.5: Task TTL & Auto-Transitions

Tests the task timeout service:
- Auto-decline after 72h TTL expiration (FR8, NFR-CONSENT-01)
- Auto-start after 48h acceptance inactivity (FR9)
- Auto-quarantine after 7d reporting timeout (FR10)
- Events emitted with "system" as actor (AC5)
- No penalty attribution on any timeout (AC6)
- Configurable timeout durations (AC7)
- Batch processing of multiple expired tasks (AC8)
- Golden Rule: "Failure is allowed; silence is not" (AC9)

Constitutional Guarantees Tested:
- Every timeout MUST emit an explicit event (no silent expiry)
- Auto-transitions use "system" as actor (not Cluster)
- NO penalty attribution on any timeout
- penalty_incurred is ALWAYS false
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, call
from uuid import uuid4

import pytest

from src.application.ports.governance.task_timeout_port import (
    TaskTimeoutConfig,
    TimeoutProcessingResult,
)
from src.application.services.governance.task_timeout_service import (
    SYSTEM_ACTOR,
    TaskTimeoutScheduler,
    TaskTimeoutService,
)
from src.domain.governance.task.task_state import TaskState, TaskStatus
from tests.helpers.fake_time_authority import FakeTimeAuthority


# ==============================================================================
# Fixtures
# ==============================================================================


@pytest.fixture
def fake_time():
    """Create fake time authority for deterministic tests."""
    return FakeTimeAuthority(
        frozen_at=datetime(2026, 1, 16, 10, 0, 0, tzinfo=timezone.utc)
    )


@pytest.fixture
def mock_task_state_port():
    """Create mock task state port."""
    port = AsyncMock()
    port.get_tasks_by_status.return_value = []
    return port


@pytest.fixture
def mock_ledger_port():
    """Create mock ledger port."""
    port = AsyncMock()
    return port


@pytest.fixture
def timeout_config():
    """Create default timeout configuration."""
    return TaskTimeoutConfig(
        activation_ttl=timedelta(hours=72),
        acceptance_inactivity=timedelta(hours=48),
        reporting_timeout=timedelta(days=7),
        processor_interval=timedelta(minutes=5),
    )


@pytest.fixture
def timeout_service(
    mock_task_state_port,
    mock_ledger_port,
    fake_time,
    timeout_config,
):
    """Create TaskTimeoutService with mocked dependencies."""
    return TaskTimeoutService(
        task_state_port=mock_task_state_port,
        ledger_port=mock_ledger_port,
        time_authority=fake_time,
        config=timeout_config,
    )


def create_task(
    task_id=None,
    earl_id="earl-agares",
    cluster_id="cluster-alpha",
    status=TaskStatus.AUTHORIZED,
    created_at=None,
    state_entered_at=None,
    ttl=timedelta(hours=72),
    inactivity_timeout=timedelta(hours=48),
    reporting_timeout=timedelta(days=7),
):
    """Helper to create test tasks in various states."""
    if task_id is None:
        task_id = uuid4()
    if created_at is None:
        created_at = datetime(2026, 1, 14, 10, 0, 0, tzinfo=timezone.utc)
    if state_entered_at is None:
        state_entered_at = created_at

    return TaskState(
        task_id=task_id,
        earl_id=earl_id,
        cluster_id=cluster_id,
        current_status=status,
        created_at=created_at,
        state_entered_at=state_entered_at,
        ttl=ttl,
        inactivity_timeout=inactivity_timeout,
        reporting_timeout=reporting_timeout,
    )


# ==============================================================================
# Test: Activation TTL Auto-Decline (AC1, AC4, AC6, FR8, NFR-CONSENT-01)
# ==============================================================================


class TestActivationTTLAutoDeclne:
    """Tests for auto-decline after activation TTL expiration."""

    @pytest.mark.asyncio
    async def test_auto_decline_after_72h_ttl(
        self,
        timeout_service,
        mock_task_state_port,
        fake_time,
    ):
        """Routed task auto-declines after 72h TTL (AC1, FR8)."""
        # Task was routed 73 hours ago (past 72h TTL)
        task = create_task(
            status=TaskStatus.ROUTED,
            state_entered_at=datetime(2026, 1, 13, 9, 0, 0, tzinfo=timezone.utc),
            ttl=timedelta(hours=72),
        )
        mock_task_state_port.get_tasks_by_status.return_value = [task]

        result = await timeout_service.process_activation_timeouts()

        assert task.task_id in result
        mock_task_state_port.save_task.assert_called_once()
        saved_task = mock_task_state_port.save_task.call_args[0][0]
        assert saved_task.current_status == TaskStatus.DECLINED

    @pytest.mark.asyncio
    async def test_no_decline_before_ttl_expires(
        self,
        timeout_service,
        mock_task_state_port,
        fake_time,
    ):
        """Routed task NOT declined before TTL expires."""
        # Task was routed 24 hours ago (still within 72h TTL)
        task = create_task(
            status=TaskStatus.ROUTED,
            state_entered_at=datetime(2026, 1, 15, 10, 0, 0, tzinfo=timezone.utc),
            ttl=timedelta(hours=72),
        )
        mock_task_state_port.get_tasks_by_status.return_value = [task]

        result = await timeout_service.process_activation_timeouts()

        assert len(result) == 0
        mock_task_state_port.save_task.assert_not_called()

    @pytest.mark.asyncio
    async def test_auto_decline_uses_system_actor(
        self,
        timeout_service,
        mock_task_state_port,
        mock_ledger_port,
        fake_time,
    ):
        """Auto-decline events use 'system' as actor, not Cluster (AC5)."""
        task = create_task(
            status=TaskStatus.ROUTED,
            state_entered_at=datetime(2026, 1, 13, 9, 0, 0, tzinfo=timezone.utc),
        )
        mock_task_state_port.get_tasks_by_status.return_value = [task]

        await timeout_service.process_activation_timeouts()

        # Verify event was emitted with system as actor
        mock_ledger_port.append_event.assert_called_once()
        event = mock_ledger_port.append_event.call_args[0][0]
        assert event.actor_id == SYSTEM_ACTOR
        assert event.actor_id == "system"  # Explicit check

    @pytest.mark.asyncio
    async def test_auto_decline_event_has_correct_type(
        self,
        timeout_service,
        mock_task_state_port,
        mock_ledger_port,
    ):
        """Auto-decline emits executive.task.auto_declined event."""
        task = create_task(
            status=TaskStatus.ROUTED,
            state_entered_at=datetime(2026, 1, 13, 9, 0, 0, tzinfo=timezone.utc),
        )
        mock_task_state_port.get_tasks_by_status.return_value = [task]

        await timeout_service.process_activation_timeouts()

        event = mock_ledger_port.append_event.call_args[0][0]
        assert event.event_type == "executive.task.auto_declined"

    @pytest.mark.asyncio
    async def test_auto_decline_event_has_ttl_expired_reason(
        self,
        timeout_service,
        mock_task_state_port,
        mock_ledger_port,
    ):
        """Auto-decline event has reason='ttl_expired' (not 'failure')."""
        task = create_task(
            status=TaskStatus.ROUTED,
            state_entered_at=datetime(2026, 1, 13, 9, 0, 0, tzinfo=timezone.utc),
        )
        mock_task_state_port.get_tasks_by_status.return_value = [task]

        await timeout_service.process_activation_timeouts()

        event = mock_ledger_port.append_event.call_args[0][0]
        assert event.payload["reason"] == "ttl_expired"
        assert "failure" not in event.payload["reason"].lower()

    @pytest.mark.asyncio
    async def test_auto_decline_no_penalty(
        self,
        timeout_service,
        mock_task_state_port,
        mock_ledger_port,
    ):
        """Auto-decline does NOT incur penalty (AC6, FR8)."""
        task = create_task(
            status=TaskStatus.ROUTED,
            state_entered_at=datetime(2026, 1, 13, 9, 0, 0, tzinfo=timezone.utc),
        )
        mock_task_state_port.get_tasks_by_status.return_value = [task]

        await timeout_service.process_activation_timeouts()

        event = mock_ledger_port.append_event.call_args[0][0]
        assert event.payload["penalty_incurred"] is False

    @pytest.mark.asyncio
    async def test_auto_decline_transitions_to_declined_state(
        self,
        timeout_service,
        mock_task_state_port,
    ):
        """Auto-decline transitions task to DECLINED state (NFR-CONSENT-01)."""
        task = create_task(
            status=TaskStatus.ROUTED,
            state_entered_at=datetime(2026, 1, 13, 9, 0, 0, tzinfo=timezone.utc),
        )
        mock_task_state_port.get_tasks_by_status.return_value = [task]

        await timeout_service.process_activation_timeouts()

        saved_task = mock_task_state_port.save_task.call_args[0][0]
        assert saved_task.current_status == TaskStatus.DECLINED


# ==============================================================================
# Test: Acceptance Inactivity Auto-Start (AC2, FR9)
# ==============================================================================


class TestAcceptanceInactivityAutoStart:
    """Tests for auto-start after acceptance inactivity."""

    @pytest.mark.asyncio
    async def test_auto_start_after_48h_inactivity(
        self,
        timeout_service,
        mock_task_state_port,
        fake_time,
    ):
        """Accepted task auto-starts after 48h inactivity (AC2, FR9)."""
        # Task was accepted 49 hours ago (past 48h inactivity)
        task = create_task(
            status=TaskStatus.ACCEPTED,
            state_entered_at=datetime(2026, 1, 14, 9, 0, 0, tzinfo=timezone.utc),
        )
        mock_task_state_port.get_tasks_by_status.return_value = [task]

        result = await timeout_service.process_acceptance_timeouts()

        assert task.task_id in result
        saved_task = mock_task_state_port.save_task.call_args[0][0]
        assert saved_task.current_status == TaskStatus.IN_PROGRESS

    @pytest.mark.asyncio
    async def test_no_auto_start_before_inactivity_expires(
        self,
        timeout_service,
        mock_task_state_port,
        fake_time,
    ):
        """Accepted task NOT started before inactivity timeout."""
        # Task was accepted 24 hours ago (still within 48h)
        task = create_task(
            status=TaskStatus.ACCEPTED,
            state_entered_at=datetime(2026, 1, 15, 10, 0, 0, tzinfo=timezone.utc),
        )
        mock_task_state_port.get_tasks_by_status.return_value = [task]

        result = await timeout_service.process_acceptance_timeouts()

        assert len(result) == 0
        mock_task_state_port.save_task.assert_not_called()

    @pytest.mark.asyncio
    async def test_auto_start_uses_system_actor(
        self,
        timeout_service,
        mock_task_state_port,
        mock_ledger_port,
    ):
        """Auto-start events use 'system' as actor (AC5)."""
        task = create_task(
            status=TaskStatus.ACCEPTED,
            state_entered_at=datetime(2026, 1, 14, 9, 0, 0, tzinfo=timezone.utc),
        )
        mock_task_state_port.get_tasks_by_status.return_value = [task]

        await timeout_service.process_acceptance_timeouts()

        event = mock_ledger_port.append_event.call_args[0][0]
        assert event.actor_id == SYSTEM_ACTOR

    @pytest.mark.asyncio
    async def test_auto_start_event_has_correct_type(
        self,
        timeout_service,
        mock_task_state_port,
        mock_ledger_port,
    ):
        """Auto-start emits executive.task.auto_started event."""
        task = create_task(
            status=TaskStatus.ACCEPTED,
            state_entered_at=datetime(2026, 1, 14, 9, 0, 0, tzinfo=timezone.utc),
        )
        mock_task_state_port.get_tasks_by_status.return_value = [task]

        await timeout_service.process_acceptance_timeouts()

        event = mock_ledger_port.append_event.call_args[0][0]
        assert event.event_type == "executive.task.auto_started"

    @pytest.mark.asyncio
    async def test_auto_start_event_has_inactivity_reason(
        self,
        timeout_service,
        mock_task_state_port,
        mock_ledger_port,
    ):
        """Auto-start event has reason='acceptance_inactivity'."""
        task = create_task(
            status=TaskStatus.ACCEPTED,
            state_entered_at=datetime(2026, 1, 14, 9, 0, 0, tzinfo=timezone.utc),
        )
        mock_task_state_port.get_tasks_by_status.return_value = [task]

        await timeout_service.process_acceptance_timeouts()

        event = mock_ledger_port.append_event.call_args[0][0]
        assert event.payload["reason"] == "acceptance_inactivity"


# ==============================================================================
# Test: Reporting Timeout Auto-Quarantine (AC3, FR10)
# ==============================================================================


class TestReportingTimeoutAutoQuarantine:
    """Tests for auto-quarantine after reporting timeout."""

    @pytest.mark.asyncio
    async def test_auto_quarantine_after_7d_timeout(
        self,
        timeout_service,
        mock_task_state_port,
        fake_time,
    ):
        """In-progress task auto-quarantines after 7d (AC3, FR10)."""
        # Task was started 8 days ago (past 7d reporting timeout)
        task = create_task(
            status=TaskStatus.IN_PROGRESS,
            state_entered_at=datetime(2026, 1, 8, 9, 0, 0, tzinfo=timezone.utc),
        )
        mock_task_state_port.get_tasks_by_status.return_value = [task]

        result = await timeout_service.process_reporting_timeouts()

        assert task.task_id in result
        saved_task = mock_task_state_port.save_task.call_args[0][0]
        assert saved_task.current_status == TaskStatus.QUARANTINED

    @pytest.mark.asyncio
    async def test_no_quarantine_before_timeout_expires(
        self,
        timeout_service,
        mock_task_state_port,
        fake_time,
    ):
        """In-progress task NOT quarantined before timeout."""
        # Task was started 3 days ago (still within 7d)
        task = create_task(
            status=TaskStatus.IN_PROGRESS,
            state_entered_at=datetime(2026, 1, 13, 10, 0, 0, tzinfo=timezone.utc),
        )
        mock_task_state_port.get_tasks_by_status.return_value = [task]

        result = await timeout_service.process_reporting_timeouts()

        assert len(result) == 0
        mock_task_state_port.save_task.assert_not_called()

    @pytest.mark.asyncio
    async def test_auto_quarantine_uses_system_actor(
        self,
        timeout_service,
        mock_task_state_port,
        mock_ledger_port,
    ):
        """Auto-quarantine events use 'system' as actor (AC5)."""
        task = create_task(
            status=TaskStatus.IN_PROGRESS,
            state_entered_at=datetime(2026, 1, 8, 9, 0, 0, tzinfo=timezone.utc),
        )
        mock_task_state_port.get_tasks_by_status.return_value = [task]

        await timeout_service.process_reporting_timeouts()

        event = mock_ledger_port.append_event.call_args[0][0]
        assert event.actor_id == SYSTEM_ACTOR

    @pytest.mark.asyncio
    async def test_auto_quarantine_event_has_correct_type(
        self,
        timeout_service,
        mock_task_state_port,
        mock_ledger_port,
    ):
        """Auto-quarantine emits executive.task.auto_quarantined event."""
        task = create_task(
            status=TaskStatus.IN_PROGRESS,
            state_entered_at=datetime(2026, 1, 8, 9, 0, 0, tzinfo=timezone.utc),
        )
        mock_task_state_port.get_tasks_by_status.return_value = [task]

        await timeout_service.process_reporting_timeouts()

        event = mock_ledger_port.append_event.call_args[0][0]
        assert event.event_type == "executive.task.auto_quarantined"

    @pytest.mark.asyncio
    async def test_auto_quarantine_event_has_reporting_reason(
        self,
        timeout_service,
        mock_task_state_port,
        mock_ledger_port,
    ):
        """Auto-quarantine event has reason='reporting_timeout'."""
        task = create_task(
            status=TaskStatus.IN_PROGRESS,
            state_entered_at=datetime(2026, 1, 8, 9, 0, 0, tzinfo=timezone.utc),
        )
        mock_task_state_port.get_tasks_by_status.return_value = [task]

        await timeout_service.process_reporting_timeouts()

        event = mock_ledger_port.append_event.call_args[0][0]
        assert event.payload["reason"] == "reporting_timeout"
        assert "failure" not in event.payload["reason"].lower()

    @pytest.mark.asyncio
    async def test_auto_quarantine_no_penalty(
        self,
        timeout_service,
        mock_task_state_port,
        mock_ledger_port,
    ):
        """Auto-quarantine does NOT incur penalty (AC6)."""
        task = create_task(
            status=TaskStatus.IN_PROGRESS,
            state_entered_at=datetime(2026, 1, 8, 9, 0, 0, tzinfo=timezone.utc),
        )
        mock_task_state_port.get_tasks_by_status.return_value = [task]

        await timeout_service.process_reporting_timeouts()

        event = mock_ledger_port.append_event.call_args[0][0]
        assert event.payload["penalty_incurred"] is False


# ==============================================================================
# Test: Batch Processing (AC8)
# ==============================================================================


class TestBatchProcessing:
    """Tests for batch processing of multiple tasks."""

    @pytest.mark.asyncio
    async def test_processes_multiple_expired_tasks(
        self,
        timeout_service,
        mock_task_state_port,
        mock_ledger_port,
    ):
        """Processes multiple expired tasks in batch (AC8)."""
        # Create 3 expired routed tasks
        tasks = [
            create_task(
                task_id=uuid4(),
                status=TaskStatus.ROUTED,
                state_entered_at=datetime(2026, 1, 13, 9, 0, 0, tzinfo=timezone.utc),
            )
            for _ in range(3)
        ]
        mock_task_state_port.get_tasks_by_status.return_value = tasks

        result = await timeout_service.process_activation_timeouts()

        assert len(result) == 3
        assert mock_task_state_port.save_task.call_count == 3
        assert mock_ledger_port.append_event.call_count == 3

    @pytest.mark.asyncio
    async def test_process_all_timeouts_runs_all_scenarios(
        self,
        timeout_service,
        mock_task_state_port,
        mock_ledger_port,
    ):
        """process_all_timeouts runs all three timeout scenarios."""
        # Create expired tasks for each scenario
        routed_task = create_task(
            status=TaskStatus.ROUTED,
            state_entered_at=datetime(2026, 1, 13, 9, 0, 0, tzinfo=timezone.utc),
        )
        accepted_task = create_task(
            status=TaskStatus.ACCEPTED,
            state_entered_at=datetime(2026, 1, 14, 9, 0, 0, tzinfo=timezone.utc),
        )
        in_progress_task = create_task(
            status=TaskStatus.IN_PROGRESS,
            state_entered_at=datetime(2026, 1, 8, 9, 0, 0, tzinfo=timezone.utc),
        )

        # Mock different returns based on status
        def get_tasks_by_status(status):
            if status == TaskStatus.ROUTED:
                return [routed_task]
            elif status == TaskStatus.ACCEPTED:
                return [accepted_task]
            elif status == TaskStatus.IN_PROGRESS:
                return [in_progress_task]
            return []

        mock_task_state_port.get_tasks_by_status.side_effect = get_tasks_by_status

        result = await timeout_service.process_all_timeouts()

        assert routed_task.task_id in result.declined
        assert accepted_task.task_id in result.started
        assert in_progress_task.task_id in result.quarantined
        assert result.total_processed == 3

    @pytest.mark.asyncio
    async def test_process_all_returns_correct_counts(
        self,
        timeout_service,
        mock_task_state_port,
    ):
        """process_all_timeouts returns correct counts in result."""
        # Mock empty results
        mock_task_state_port.get_tasks_by_status.return_value = []

        result = await timeout_service.process_all_timeouts()

        assert isinstance(result, TimeoutProcessingResult)
        assert result.declined == []
        assert result.started == []
        assert result.quarantined == []
        assert result.total_processed == 0


# ==============================================================================
# Test: Configurable Timeouts (AC7)
# ==============================================================================


class TestConfigurableTimeouts:
    """Tests for configurable timeout durations."""

    @pytest.mark.asyncio
    async def test_custom_activation_ttl(
        self,
        mock_task_state_port,
        mock_ledger_port,
        fake_time,
    ):
        """Custom activation TTL is respected (AC7)."""
        # Custom 24h TTL
        config = TaskTimeoutConfig(activation_ttl=timedelta(hours=24))
        service = TaskTimeoutService(
            task_state_port=mock_task_state_port,
            ledger_port=mock_ledger_port,
            time_authority=fake_time,
            config=config,
        )

        # Task was routed 25 hours ago (past custom 24h TTL)
        task = create_task(
            status=TaskStatus.ROUTED,
            state_entered_at=datetime(2026, 1, 15, 9, 0, 0, tzinfo=timezone.utc),
            ttl=timedelta(hours=24),
        )
        mock_task_state_port.get_tasks_by_status.return_value = [task]

        result = await service.process_activation_timeouts()

        assert task.task_id in result

    @pytest.mark.asyncio
    async def test_custom_acceptance_inactivity(
        self,
        mock_task_state_port,
        mock_ledger_port,
        fake_time,
    ):
        """Custom acceptance inactivity timeout is respected (AC7)."""
        # Custom 12h inactivity timeout
        config = TaskTimeoutConfig(acceptance_inactivity=timedelta(hours=12))
        service = TaskTimeoutService(
            task_state_port=mock_task_state_port,
            ledger_port=mock_ledger_port,
            time_authority=fake_time,
            config=config,
        )

        # Task was accepted 13 hours ago (past custom 12h)
        task = create_task(
            status=TaskStatus.ACCEPTED,
            state_entered_at=datetime(2026, 1, 15, 21, 0, 0, tzinfo=timezone.utc),
        )
        mock_task_state_port.get_tasks_by_status.return_value = [task]

        result = await service.process_acceptance_timeouts()

        assert task.task_id in result

    @pytest.mark.asyncio
    async def test_custom_reporting_timeout(
        self,
        mock_task_state_port,
        mock_ledger_port,
        fake_time,
    ):
        """Custom reporting timeout is respected (AC7)."""
        # Custom 3-day reporting timeout
        config = TaskTimeoutConfig(reporting_timeout=timedelta(days=3))
        service = TaskTimeoutService(
            task_state_port=mock_task_state_port,
            ledger_port=mock_ledger_port,
            time_authority=fake_time,
            config=config,
        )

        # Task was started 4 days ago (past custom 3d)
        task = create_task(
            status=TaskStatus.IN_PROGRESS,
            state_entered_at=datetime(2026, 1, 12, 9, 0, 0, tzinfo=timezone.utc),
            reporting_timeout=timedelta(days=3),
        )
        mock_task_state_port.get_tasks_by_status.return_value = [task]

        result = await service.process_reporting_timeouts()

        assert task.task_id in result

    def test_get_config_returns_current_config(self, timeout_service, timeout_config):
        """get_config returns the current configuration."""
        config = timeout_service.get_config()

        assert config.activation_ttl == timeout_config.activation_ttl
        assert config.acceptance_inactivity == timeout_config.acceptance_inactivity
        assert config.reporting_timeout == timeout_config.reporting_timeout


# ==============================================================================
# Test: Golden Rule - "Failure is allowed; silence is not" (AC9)
# ==============================================================================


class TestGoldenRuleSilenceNotAllowed:
    """Tests for Golden Rule: 'Failure is allowed; silence is not' (AC9)."""

    @pytest.mark.asyncio
    async def test_every_auto_decline_emits_event(
        self,
        timeout_service,
        mock_task_state_port,
        mock_ledger_port,
    ):
        """Every auto-decline MUST emit an event - no silent expiry (AC9)."""
        task = create_task(
            status=TaskStatus.ROUTED,
            state_entered_at=datetime(2026, 1, 13, 9, 0, 0, tzinfo=timezone.utc),
        )
        mock_task_state_port.get_tasks_by_status.return_value = [task]

        await timeout_service.process_activation_timeouts()

        # Verify event was emitted
        mock_ledger_port.append_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_every_auto_start_emits_event(
        self,
        timeout_service,
        mock_task_state_port,
        mock_ledger_port,
    ):
        """Every auto-start MUST emit an event - no silent transition (AC9)."""
        task = create_task(
            status=TaskStatus.ACCEPTED,
            state_entered_at=datetime(2026, 1, 14, 9, 0, 0, tzinfo=timezone.utc),
        )
        mock_task_state_port.get_tasks_by_status.return_value = [task]

        await timeout_service.process_acceptance_timeouts()

        mock_ledger_port.append_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_every_auto_quarantine_emits_event(
        self,
        timeout_service,
        mock_task_state_port,
        mock_ledger_port,
    ):
        """Every auto-quarantine MUST emit an event - no silent quarantine (AC9)."""
        task = create_task(
            status=TaskStatus.IN_PROGRESS,
            state_entered_at=datetime(2026, 1, 8, 9, 0, 0, tzinfo=timezone.utc),
        )
        mock_task_state_port.get_tasks_by_status.return_value = [task]

        await timeout_service.process_reporting_timeouts()

        mock_ledger_port.append_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_event_contains_task_id_for_traceability(
        self,
        timeout_service,
        mock_task_state_port,
        mock_ledger_port,
    ):
        """Events contain task_id for traceability (AC9)."""
        task = create_task(
            status=TaskStatus.ROUTED,
            state_entered_at=datetime(2026, 1, 13, 9, 0, 0, tzinfo=timezone.utc),
        )
        mock_task_state_port.get_tasks_by_status.return_value = [task]

        await timeout_service.process_activation_timeouts()

        event = mock_ledger_port.append_event.call_args[0][0]
        assert event.payload["task_id"] == str(task.task_id)
        assert event.trace_id == str(task.task_id)

    @pytest.mark.asyncio
    async def test_event_contains_cluster_id_for_reference(
        self,
        timeout_service,
        mock_task_state_port,
        mock_ledger_port,
    ):
        """Events contain cluster_id for reference (not blame)."""
        task = create_task(
            status=TaskStatus.ROUTED,
            cluster_id="cluster-alpha",
            state_entered_at=datetime(2026, 1, 13, 9, 0, 0, tzinfo=timezone.utc),
        )
        mock_task_state_port.get_tasks_by_status.return_value = [task]

        await timeout_service.process_activation_timeouts()

        event = mock_ledger_port.append_event.call_args[0][0]
        assert event.payload["cluster_id"] == "cluster-alpha"


# ==============================================================================
# Test: Timeout Configuration Validation
# ==============================================================================


class TestTimeoutConfigValidation:
    """Tests for timeout configuration validation."""

    def test_config_with_defaults(self):
        """Config can be created with defaults."""
        config = TaskTimeoutConfig()

        assert config.activation_ttl == timedelta(hours=72)
        assert config.acceptance_inactivity == timedelta(hours=48)
        assert config.reporting_timeout == timedelta(days=7)
        assert config.processor_interval == timedelta(minutes=5)

    def test_config_with_custom_values(self):
        """Config accepts custom values."""
        config = TaskTimeoutConfig(
            activation_ttl=timedelta(hours=24),
            acceptance_inactivity=timedelta(hours=12),
            reporting_timeout=timedelta(days=3),
            processor_interval=timedelta(minutes=1),
        )

        assert config.activation_ttl == timedelta(hours=24)
        assert config.acceptance_inactivity == timedelta(hours=12)
        assert config.reporting_timeout == timedelta(days=3)
        assert config.processor_interval == timedelta(minutes=1)

    def test_config_rejects_zero_activation_ttl(self):
        """Config rejects zero activation TTL."""
        with pytest.raises(ValueError, match="activation_ttl must be positive"):
            TaskTimeoutConfig(activation_ttl=timedelta(0))

    def test_config_rejects_negative_activation_ttl(self):
        """Config rejects negative activation TTL."""
        with pytest.raises(ValueError, match="activation_ttl must be positive"):
            TaskTimeoutConfig(activation_ttl=timedelta(hours=-1))

    def test_config_rejects_zero_acceptance_inactivity(self):
        """Config rejects zero acceptance inactivity."""
        with pytest.raises(ValueError, match="acceptance_inactivity must be positive"):
            TaskTimeoutConfig(acceptance_inactivity=timedelta(0))

    def test_config_rejects_zero_reporting_timeout(self):
        """Config rejects zero reporting timeout."""
        with pytest.raises(ValueError, match="reporting_timeout must be positive"):
            TaskTimeoutConfig(reporting_timeout=timedelta(0))

    def test_config_rejects_zero_processor_interval(self):
        """Config rejects zero processor interval."""
        with pytest.raises(ValueError, match="processor_interval must be positive"):
            TaskTimeoutConfig(processor_interval=timedelta(0))


# ==============================================================================
# Test: TimeoutProcessingResult
# ==============================================================================


class TestTimeoutProcessingResult:
    """Tests for TimeoutProcessingResult dataclass."""

    def test_empty_result(self):
        """Empty result has zero totals."""
        result = TimeoutProcessingResult()

        assert result.declined == []
        assert result.started == []
        assert result.quarantined == []
        assert result.total_processed == 0
        assert result.has_errors is False

    def test_total_processed_calculation(self):
        """Total processed sums all categories."""
        result = TimeoutProcessingResult(
            declined=[uuid4(), uuid4()],
            started=[uuid4()],
            quarantined=[uuid4(), uuid4(), uuid4()],
        )

        assert result.total_processed == 6

    def test_has_errors_with_errors(self):
        """has_errors is True when errors exist."""
        result = TimeoutProcessingResult(
            errors=[(uuid4(), "Test error")]
        )

        assert result.has_errors is True

    def test_has_errors_without_errors(self):
        """has_errors is False when no errors."""
        result = TimeoutProcessingResult(
            declined=[uuid4()],
            errors=[],
        )

        assert result.has_errors is False


# ==============================================================================
# Test: TaskTimeoutScheduler
# ==============================================================================


class TestTaskTimeoutScheduler:
    """Tests for TaskTimeoutScheduler."""

    def _create_mock_service(self):
        """Create mock service with proper get_config behavior."""
        service = AsyncMock()
        # get_config is NOT async, so use MagicMock for it
        service.get_config = MagicMock(return_value=TaskTimeoutConfig())
        service.process_all_timeouts.return_value = TimeoutProcessingResult()
        return service

    def test_scheduler_not_running_initially(self):
        """Scheduler is not running when created."""
        service = self._create_mock_service()
        scheduler = TaskTimeoutScheduler(service)

        assert scheduler.is_running is False

    def test_last_run_result_none_initially(self):
        """last_run_result is None before first run."""
        service = self._create_mock_service()
        scheduler = TaskTimeoutScheduler(service)

        assert scheduler.last_run_result is None

    @pytest.mark.asyncio
    async def test_start_sets_running_true(self):
        """start() sets is_running to True."""
        service = self._create_mock_service()
        scheduler = TaskTimeoutScheduler(service)

        await scheduler.start()
        # Give the task a moment to start
        import asyncio
        await asyncio.sleep(0.01)

        assert scheduler.is_running is True

        await scheduler.stop()

    @pytest.mark.asyncio
    async def test_stop_sets_running_false(self):
        """stop() sets is_running to False."""
        service = self._create_mock_service()
        scheduler = TaskTimeoutScheduler(service)

        await scheduler.start()
        import asyncio
        await asyncio.sleep(0.01)
        await scheduler.stop()

        assert scheduler.is_running is False
