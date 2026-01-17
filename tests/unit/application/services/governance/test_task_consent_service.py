"""Tests for TaskConsentService.

Story: consent-gov-2.3: Task Consent Operations

Tests the task consent service:
- Viewing pending task activation requests
- Accepting task activation requests
- Declining task activation requests (no justification required)
- Halting in-progress tasks (no penalty)
- Constitutional guarantees: penalty-free refusal

Constitutional Guarantees Tested:
- AC5: Declining does NOT reduce standing/reputation
- AC6: No standing/reputation tracking schema exists
- FR4: Cluster can decline without justification
- FR5: Cluster can halt without penalty
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.application.ports.governance.task_consent_port import (
    InvalidTaskStateError,
    PendingTaskView,
    TaskConsentResult,
    UnauthorizedConsentError,
)
from src.application.services.governance.task_consent_service import (
    TaskConsentService,
)
from src.domain.governance.task.task_state import TaskState, TaskStatus
from tests.helpers.fake_time_authority import FakeTimeAuthority


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
    return port


@pytest.fixture
def mock_ledger_port():
    """Create mock ledger port."""
    port = AsyncMock()
    port.read_events.return_value = []
    return port


@pytest.fixture
def mock_two_phase_emitter():
    """Create mock two-phase emitter."""
    emitter = AsyncMock()
    emitter.emit_intent.return_value = uuid4()
    return emitter


@pytest.fixture
def task_consent_service(
    mock_task_state_port,
    mock_ledger_port,
    mock_two_phase_emitter,
    fake_time,
):
    """Create TaskConsentService with mocked dependencies."""
    return TaskConsentService(
        task_state_port=mock_task_state_port,
        ledger_port=mock_ledger_port,
        two_phase_emitter=mock_two_phase_emitter,
        time_authority=fake_time,
    )


def create_task(
    task_id=None,
    earl_id="earl-agares",
    cluster_id="cluster-alpha",
    status=TaskStatus.AUTHORIZED,
    created_at=None,
    state_entered_at=None,
    ttl=timedelta(hours=72),
):
    """Helper to create test tasks in various states."""
    if task_id is None:
        task_id = uuid4()
    if created_at is None:
        created_at = datetime(2026, 1, 16, 10, 0, 0, tzinfo=timezone.utc)
    if state_entered_at is None:
        state_entered_at = created_at

    task = TaskState(
        task_id=task_id,
        earl_id=earl_id,
        cluster_id=cluster_id,
        current_status=status,
        created_at=created_at,
        state_entered_at=state_entered_at,
        ttl=ttl,
    )
    return task


class TestGetPendingRequests:
    """Tests for get_pending_requests method (AC1, FR2)."""

    @pytest.mark.asyncio
    async def test_returns_routed_tasks_for_cluster(
        self,
        task_consent_service,
        mock_task_state_port,
        mock_ledger_port,
    ):
        """Returns tasks in ROUTED state for the Cluster (AC1)."""
        task_id = uuid4()
        task = create_task(
            task_id=task_id,
            cluster_id="cluster-alpha",
            status=TaskStatus.ROUTED,
        )
        mock_task_state_port.get_tasks_by_state_and_cluster.return_value = [task]

        # Mock ledger for description preview
        mock_event = MagicMock()
        mock_event.payload = {"description": "Test task description"}
        mock_ledger_port.read_events.return_value = [mock_event]

        result = await task_consent_service.get_pending_requests(
            cluster_id="cluster-alpha",
            limit=100,
        )

        assert len(result) == 1
        assert result[0].task_id == task_id
        assert result[0].earl_id == "earl-agares"
        mock_task_state_port.get_tasks_by_state_and_cluster.assert_called_once_with(
            status=TaskStatus.ROUTED,
            cluster_id="cluster-alpha",
            limit=100,
        )

    @pytest.mark.asyncio
    async def test_filters_out_expired_requests(
        self,
        task_consent_service,
        mock_task_state_port,
        fake_time,
    ):
        """Expired requests are not returned (AC1)."""
        # Create a task with expired TTL
        expired_task = create_task(
            cluster_id="cluster-alpha",
            status=TaskStatus.ROUTED,
            state_entered_at=datetime(2026, 1, 13, 10, 0, 0, tzinfo=timezone.utc),  # 3 days ago
            ttl=timedelta(hours=72),  # 72h TTL = expired
        )
        mock_task_state_port.get_tasks_by_state_and_cluster.return_value = [expired_task]

        result = await task_consent_service.get_pending_requests(
            cluster_id="cluster-alpha",
        )

        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_includes_ttl_remaining(
        self,
        task_consent_service,
        mock_task_state_port,
        mock_ledger_port,
        fake_time,
    ):
        """Includes TTL remaining in response (AC1)."""
        # Task routed 1 hour ago with 72h TTL
        task = create_task(
            cluster_id="cluster-alpha",
            status=TaskStatus.ROUTED,
            state_entered_at=datetime(2026, 1, 16, 9, 0, 0, tzinfo=timezone.utc),
            ttl=timedelta(hours=72),
        )
        mock_task_state_port.get_tasks_by_state_and_cluster.return_value = [task]
        mock_ledger_port.read_events.return_value = []

        result = await task_consent_service.get_pending_requests(
            cluster_id="cluster-alpha",
        )

        assert len(result) == 1
        # TTL remaining should be ~71 hours
        assert result[0].ttl_remaining > timedelta(hours=70)
        assert result[0].ttl_remaining < timedelta(hours=72)

    @pytest.mark.asyncio
    async def test_respects_limit_parameter(
        self,
        task_consent_service,
        mock_task_state_port,
    ):
        """Respects limit parameter for pagination (AC1)."""
        await task_consent_service.get_pending_requests(
            cluster_id="cluster-alpha",
            limit=50,
        )

        mock_task_state_port.get_tasks_by_state_and_cluster.assert_called_once_with(
            status=TaskStatus.ROUTED,
            cluster_id="cluster-alpha",
            limit=50,
        )


class TestAcceptTask:
    """Tests for accept_task method (AC2, AC7, FR3)."""

    @pytest.mark.asyncio
    async def test_accept_transitions_to_accepted(
        self,
        task_consent_service,
        mock_task_state_port,
        mock_ledger_port,
    ):
        """Accepting a routed task transitions to ACCEPTED (AC2)."""
        task = create_task(
            cluster_id="cluster-alpha",
            status=TaskStatus.ROUTED,
        )
        mock_task_state_port.get_task.return_value = task
        mock_task_state_port.save_task.return_value = None

        result = await task_consent_service.accept_task(
            task_id=task.task_id,
            cluster_id="cluster-alpha",
        )

        assert result.success is True
        assert result.operation == "accepted"
        assert result.task_state.current_status == TaskStatus.ACCEPTED

    @pytest.mark.asyncio
    async def test_accept_emits_event(
        self,
        task_consent_service,
        mock_task_state_port,
        mock_ledger_port,
    ):
        """Accepting emits executive.task.accepted event (AC7)."""
        task = create_task(
            cluster_id="cluster-alpha",
            status=TaskStatus.ROUTED,
        )
        mock_task_state_port.get_task.return_value = task
        mock_task_state_port.save_task.return_value = None

        await task_consent_service.accept_task(
            task_id=task.task_id,
            cluster_id="cluster-alpha",
        )

        # Verify event was appended to ledger
        mock_ledger_port.append_event.assert_called_once()
        event = mock_ledger_port.append_event.call_args[0][0]
        assert event.event_type == "executive.task.accepted"
        assert event.payload["cluster_id"] == "cluster-alpha"

    @pytest.mark.asyncio
    async def test_accept_unauthorized_cluster_rejected(
        self,
        task_consent_service,
        mock_task_state_port,
    ):
        """Cluster cannot accept task addressed to another (AC2)."""
        task = create_task(
            cluster_id="cluster-other",  # Different cluster
            status=TaskStatus.ROUTED,
        )
        mock_task_state_port.get_task.return_value = task

        with pytest.raises(UnauthorizedConsentError) as exc_info:
            await task_consent_service.accept_task(
                task_id=task.task_id,
                cluster_id="cluster-alpha",  # Wrong cluster
            )

        assert "cluster-alpha" in str(exc_info.value)
        assert "not the recipient" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_accept_invalid_state_rejected(
        self,
        task_consent_service,
        mock_task_state_port,
    ):
        """Cannot accept task not in ROUTED state (AC2)."""
        task = create_task(
            cluster_id="cluster-alpha",
            status=TaskStatus.IN_PROGRESS,  # Wrong state
        )
        mock_task_state_port.get_task.return_value = task

        with pytest.raises(InvalidTaskStateError) as exc_info:
            await task_consent_service.accept_task(
                task_id=task.task_id,
                cluster_id="cluster-alpha",
            )

        assert "in_progress" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_accept_uses_two_phase_emission(
        self,
        task_consent_service,
        mock_task_state_port,
        mock_two_phase_emitter,
    ):
        """Accept uses two-phase event emission pattern."""
        task = create_task(
            cluster_id="cluster-alpha",
            status=TaskStatus.ROUTED,
        )
        mock_task_state_port.get_task.return_value = task
        mock_task_state_port.save_task.return_value = None

        await task_consent_service.accept_task(
            task_id=task.task_id,
            cluster_id="cluster-alpha",
        )

        # Verify intent was emitted
        mock_two_phase_emitter.emit_intent.assert_called_once()
        call_kwargs = mock_two_phase_emitter.emit_intent.call_args.kwargs
        assert call_kwargs["operation_type"] == "task.accept"
        assert call_kwargs["actor_id"] == "cluster-alpha"

        # Verify commit was emitted
        mock_two_phase_emitter.emit_commit.assert_called_once()


class TestDeclineTask:
    """Tests for decline_task method (AC3, AC5, AC8, FR4)."""

    @pytest.mark.asyncio
    async def test_decline_requires_no_justification(
        self,
        task_consent_service,
        mock_task_state_port,
        mock_ledger_port,
    ):
        """Declining does NOT require justification (FR4, AC3)."""
        task = create_task(
            cluster_id="cluster-alpha",
            status=TaskStatus.ROUTED,
        )
        mock_task_state_port.get_task.return_value = task
        mock_task_state_port.save_task.return_value = None

        # NOTE: No justification parameter - this is intentional (FR4)
        result = await task_consent_service.decline_task(
            task_id=task.task_id,
            cluster_id="cluster-alpha",
        )

        assert result.success is True
        assert result.operation == "declined"
        assert result.task_state.current_status == TaskStatus.DECLINED

    @pytest.mark.asyncio
    async def test_decline_incurs_no_penalty(
        self,
        task_consent_service,
        mock_task_state_port,
        mock_ledger_port,
    ):
        """Declining MUST NOT incur any penalty (AC5)."""
        task = create_task(
            cluster_id="cluster-alpha",
            status=TaskStatus.ROUTED,
        )
        mock_task_state_port.get_task.return_value = task
        mock_task_state_port.save_task.return_value = None

        await task_consent_service.decline_task(
            task_id=task.task_id,
            cluster_id="cluster-alpha",
        )

        # Verify event payload has penalty_incurred: false
        mock_ledger_port.append_event.assert_called_once()
        event = mock_ledger_port.append_event.call_args[0][0]
        assert event.payload["penalty_incurred"] is False

    @pytest.mark.asyncio
    async def test_decline_emits_event_with_explicit_decline_reason(
        self,
        task_consent_service,
        mock_task_state_port,
        mock_ledger_port,
    ):
        """Decline emits event with reason 'explicit_decline' (AC8)."""
        task = create_task(
            cluster_id="cluster-alpha",
            status=TaskStatus.ROUTED,
        )
        mock_task_state_port.get_task.return_value = task
        mock_task_state_port.save_task.return_value = None

        await task_consent_service.decline_task(
            task_id=task.task_id,
            cluster_id="cluster-alpha",
        )

        mock_ledger_port.append_event.assert_called_once()
        event = mock_ledger_port.append_event.call_args[0][0]
        assert event.event_type == "executive.task.declined"
        assert event.payload["reason"] == "explicit_decline"
        # NOT "failure" or "penalty"
        assert event.payload["reason"] != "failure"
        assert event.payload["reason"] != "penalty"

    @pytest.mark.asyncio
    async def test_decline_from_accepted_state(
        self,
        task_consent_service,
        mock_task_state_port,
        mock_ledger_port,
    ):
        """Can decline from ACCEPTED state (changed mind before starting)."""
        task = create_task(
            cluster_id="cluster-alpha",
            status=TaskStatus.ACCEPTED,
        )
        mock_task_state_port.get_task.return_value = task
        mock_task_state_port.save_task.return_value = None

        result = await task_consent_service.decline_task(
            task_id=task.task_id,
            cluster_id="cluster-alpha",
        )

        assert result.success is True
        assert result.task_state.current_status == TaskStatus.DECLINED

    @pytest.mark.asyncio
    async def test_decline_unauthorized_cluster_rejected(
        self,
        task_consent_service,
        mock_task_state_port,
    ):
        """Cluster cannot decline task addressed to another."""
        task = create_task(
            cluster_id="cluster-other",
            status=TaskStatus.ROUTED,
        )
        mock_task_state_port.get_task.return_value = task

        with pytest.raises(UnauthorizedConsentError):
            await task_consent_service.decline_task(
                task_id=task.task_id,
                cluster_id="cluster-alpha",
            )

    @pytest.mark.asyncio
    async def test_decline_invalid_state_rejected(
        self,
        task_consent_service,
        mock_task_state_port,
    ):
        """Cannot decline task in IN_PROGRESS state."""
        task = create_task(
            cluster_id="cluster-alpha",
            status=TaskStatus.IN_PROGRESS,
        )
        mock_task_state_port.get_task.return_value = task

        with pytest.raises(InvalidTaskStateError) as exc_info:
            await task_consent_service.decline_task(
                task_id=task.task_id,
                cluster_id="cluster-alpha",
            )

        assert "in_progress" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_decline_uses_two_phase_emission(
        self,
        task_consent_service,
        mock_task_state_port,
        mock_two_phase_emitter,
    ):
        """Decline uses two-phase event emission pattern."""
        task = create_task(
            cluster_id="cluster-alpha",
            status=TaskStatus.ROUTED,
        )
        mock_task_state_port.get_task.return_value = task
        mock_task_state_port.save_task.return_value = None

        await task_consent_service.decline_task(
            task_id=task.task_id,
            cluster_id="cluster-alpha",
        )

        mock_two_phase_emitter.emit_intent.assert_called_once()
        call_kwargs = mock_two_phase_emitter.emit_intent.call_args.kwargs
        assert call_kwargs["operation_type"] == "task.decline"


class TestHaltTask:
    """Tests for halt_task method (AC4, AC9, FR5)."""

    @pytest.mark.asyncio
    async def test_halt_in_progress_no_penalty(
        self,
        task_consent_service,
        mock_task_state_port,
        mock_ledger_port,
    ):
        """Halting in-progress task incurs NO penalty (FR5, AC4)."""
        task = create_task(
            cluster_id="cluster-alpha",
            status=TaskStatus.IN_PROGRESS,
        )
        mock_task_state_port.get_task.return_value = task
        mock_task_state_port.save_task.return_value = None

        result = await task_consent_service.halt_task(
            task_id=task.task_id,
            cluster_id="cluster-alpha",
        )

        assert result.success is True
        assert result.operation == "halted"

        # Verify event has penalty_incurred: false
        mock_ledger_port.append_event.assert_called_once()
        event = mock_ledger_port.append_event.call_args[0][0]
        assert event.payload["penalty_incurred"] is False

    @pytest.mark.asyncio
    async def test_halt_transitions_to_quarantined(
        self,
        task_consent_service,
        mock_task_state_port,
        mock_ledger_port,
    ):
        """Halting transitions to QUARANTINED (not 'failed') (AC4)."""
        task = create_task(
            cluster_id="cluster-alpha",
            status=TaskStatus.IN_PROGRESS,
        )
        mock_task_state_port.get_task.return_value = task
        mock_task_state_port.save_task.return_value = None

        result = await task_consent_service.halt_task(
            task_id=task.task_id,
            cluster_id="cluster-alpha",
        )

        assert result.task_state.current_status == TaskStatus.QUARANTINED
        # Not "failed" - important constitutional distinction

    @pytest.mark.asyncio
    async def test_halt_emits_event(
        self,
        task_consent_service,
        mock_task_state_port,
        mock_ledger_port,
    ):
        """Halt emits executive.task.halted event (AC9)."""
        task = create_task(
            cluster_id="cluster-alpha",
            status=TaskStatus.IN_PROGRESS,
        )
        mock_task_state_port.get_task.return_value = task
        mock_task_state_port.save_task.return_value = None

        await task_consent_service.halt_task(
            task_id=task.task_id,
            cluster_id="cluster-alpha",
        )

        mock_ledger_port.append_event.assert_called_once()
        event = mock_ledger_port.append_event.call_args[0][0]
        assert event.event_type == "executive.task.halted"
        assert event.payload["reason"] == "cluster_initiated_halt"
        assert event.payload["penalty_incurred"] is False

    @pytest.mark.asyncio
    async def test_halt_unauthorized_cluster_rejected(
        self,
        task_consent_service,
        mock_task_state_port,
    ):
        """Cluster cannot halt task worked by another."""
        task = create_task(
            cluster_id="cluster-other",
            status=TaskStatus.IN_PROGRESS,
        )
        mock_task_state_port.get_task.return_value = task

        with pytest.raises(UnauthorizedConsentError) as exc_info:
            await task_consent_service.halt_task(
                task_id=task.task_id,
                cluster_id="cluster-alpha",
            )

        assert "not working on" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_halt_invalid_state_rejected(
        self,
        task_consent_service,
        mock_task_state_port,
    ):
        """Cannot halt task not in IN_PROGRESS state."""
        task = create_task(
            cluster_id="cluster-alpha",
            status=TaskStatus.ROUTED,  # Not IN_PROGRESS
        )
        mock_task_state_port.get_task.return_value = task

        with pytest.raises(InvalidTaskStateError) as exc_info:
            await task_consent_service.halt_task(
                task_id=task.task_id,
                cluster_id="cluster-alpha",
            )

        assert "routed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_halt_uses_two_phase_emission(
        self,
        task_consent_service,
        mock_task_state_port,
        mock_two_phase_emitter,
    ):
        """Halt uses two-phase event emission pattern."""
        task = create_task(
            cluster_id="cluster-alpha",
            status=TaskStatus.IN_PROGRESS,
        )
        mock_task_state_port.get_task.return_value = task
        mock_task_state_port.save_task.return_value = None

        await task_consent_service.halt_task(
            task_id=task.task_id,
            cluster_id="cluster-alpha",
        )

        mock_two_phase_emitter.emit_intent.assert_called_once()
        call_kwargs = mock_two_phase_emitter.emit_intent.call_args.kwargs
        assert call_kwargs["operation_type"] == "task.halt"


class TestConstitutionalGuarantees:
    """Tests for constitutional guarantees (AC5, AC6).

    These tests verify that the system CANNOT track penalties,
    standing, or reputation. This is an architectural constraint.
    """

    @pytest.mark.asyncio
    async def test_decline_event_never_has_penalty_true(
        self,
        task_consent_service,
        mock_task_state_port,
        mock_ledger_port,
    ):
        """Decline event MUST have penalty_incurred: false (AC5)."""
        task = create_task(
            cluster_id="cluster-alpha",
            status=TaskStatus.ROUTED,
        )
        mock_task_state_port.get_task.return_value = task
        mock_task_state_port.save_task.return_value = None

        await task_consent_service.decline_task(
            task_id=task.task_id,
            cluster_id="cluster-alpha",
        )

        event = mock_ledger_port.append_event.call_args[0][0]

        # CONSTITUTIONAL GUARANTEE: penalty_incurred must be False
        assert event.payload.get("penalty_incurred") is False

        # Verify no standing/reputation fields exist
        assert "standing" not in event.payload
        assert "reputation" not in event.payload
        assert "score" not in event.payload
        assert "decline_count" not in event.payload

    @pytest.mark.asyncio
    async def test_halt_event_never_has_penalty_true(
        self,
        task_consent_service,
        mock_task_state_port,
        mock_ledger_port,
    ):
        """Halt event MUST have penalty_incurred: false (FR5)."""
        task = create_task(
            cluster_id="cluster-alpha",
            status=TaskStatus.IN_PROGRESS,
        )
        mock_task_state_port.get_task.return_value = task
        mock_task_state_port.save_task.return_value = None

        await task_consent_service.halt_task(
            task_id=task.task_id,
            cluster_id="cluster-alpha",
        )

        event = mock_ledger_port.append_event.call_args[0][0]

        # CONSTITUTIONAL GUARANTEE: penalty_incurred must be False
        assert event.payload.get("penalty_incurred") is False

        # Verify no standing/reputation fields exist
        assert "standing" not in event.payload
        assert "reputation" not in event.payload
        assert "score" not in event.payload

    @pytest.mark.asyncio
    async def test_decline_reason_never_failure_or_penalty(
        self,
        task_consent_service,
        mock_task_state_port,
        mock_ledger_port,
    ):
        """Decline reason MUST be 'explicit_decline', never 'failure'."""
        task = create_task(
            cluster_id="cluster-alpha",
            status=TaskStatus.ROUTED,
        )
        mock_task_state_port.get_task.return_value = task
        mock_task_state_port.save_task.return_value = None

        await task_consent_service.decline_task(
            task_id=task.task_id,
            cluster_id="cluster-alpha",
        )

        event = mock_ledger_port.append_event.call_args[0][0]

        # Reason should be "explicit_decline", not negative language
        assert event.payload["reason"] == "explicit_decline"
        assert "failure" not in event.payload["reason"].lower()
        assert "penalty" not in event.payload["reason"].lower()


class TestErrorHandling:
    """Tests for error handling and edge cases."""

    @pytest.mark.asyncio
    async def test_accept_saves_task_state(
        self,
        task_consent_service,
        mock_task_state_port,
        mock_ledger_port,
    ):
        """Accept persists the new task state."""
        task = create_task(
            cluster_id="cluster-alpha",
            status=TaskStatus.ROUTED,
        )
        mock_task_state_port.get_task.return_value = task
        mock_task_state_port.save_task.return_value = None

        await task_consent_service.accept_task(
            task_id=task.task_id,
            cluster_id="cluster-alpha",
        )

        mock_task_state_port.save_task.assert_called_once()
        saved_task = mock_task_state_port.save_task.call_args[0][0]
        assert saved_task.current_status == TaskStatus.ACCEPTED

    @pytest.mark.asyncio
    async def test_decline_saves_task_state(
        self,
        task_consent_service,
        mock_task_state_port,
        mock_ledger_port,
    ):
        """Decline persists the new task state."""
        task = create_task(
            cluster_id="cluster-alpha",
            status=TaskStatus.ROUTED,
        )
        mock_task_state_port.get_task.return_value = task
        mock_task_state_port.save_task.return_value = None

        await task_consent_service.decline_task(
            task_id=task.task_id,
            cluster_id="cluster-alpha",
        )

        mock_task_state_port.save_task.assert_called_once()
        saved_task = mock_task_state_port.save_task.call_args[0][0]
        assert saved_task.current_status == TaskStatus.DECLINED

    @pytest.mark.asyncio
    async def test_halt_saves_task_state(
        self,
        task_consent_service,
        mock_task_state_port,
        mock_ledger_port,
    ):
        """Halt persists the new task state."""
        task = create_task(
            cluster_id="cluster-alpha",
            status=TaskStatus.IN_PROGRESS,
        )
        mock_task_state_port.get_task.return_value = task
        mock_task_state_port.save_task.return_value = None

        await task_consent_service.halt_task(
            task_id=task.task_id,
            cluster_id="cluster-alpha",
        )

        mock_task_state_port.save_task.assert_called_once()
        saved_task = mock_task_state_port.save_task.call_args[0][0]
        assert saved_task.current_status == TaskStatus.QUARANTINED
