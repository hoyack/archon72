"""Unit tests for task event generation.

Story: consent-gov-2.1: Task State Machine Domain Model

Tests:
- AC5: All transitions emit events to ledger via executive.task.{verb} pattern
- Event generation for all task status types
- Halt and TTL expiry event generation
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from src.domain.governance.events.event_envelope import GovernanceEvent
from src.domain.governance.task.task_events import (
    TASK_EVENT_TYPES,
    create_halt_transition_event,
    create_task_created_event,
    create_transition_event,
    create_ttl_expiry_event,
    get_event_type_for_status,
)
from src.domain.governance.task.task_state import TaskState, TaskStatus


class TestTaskEventTypes:
    """Tests for TASK_EVENT_TYPES registry (AC5)."""

    def test_all_statuses_have_event_types(self):
        """AC5: All task statuses have corresponding event types."""
        for status in TaskStatus:
            assert status in TASK_EVENT_TYPES, f"Missing event type for {status}"

    def test_event_types_follow_pattern(self):
        """AC5: Event types follow executive.task.{verb} pattern."""
        for status, event_type in TASK_EVENT_TYPES.items():
            assert event_type.startswith("executive.task."), (
                f"Event type for {status} should start with 'executive.task.', "
                f"got '{event_type}'"
            )

    def test_event_types_are_unique(self):
        """All event types are unique."""
        event_types = list(TASK_EVENT_TYPES.values())
        assert len(event_types) == len(set(event_types))

    def test_specific_event_types(self):
        """Specific event types are correct."""
        assert TASK_EVENT_TYPES[TaskStatus.AUTHORIZED] == "executive.task.authorized"
        assert TASK_EVENT_TYPES[TaskStatus.ACTIVATED] == "executive.task.activated"
        assert TASK_EVENT_TYPES[TaskStatus.ROUTED] == "executive.task.routed"
        assert TASK_EVENT_TYPES[TaskStatus.ACCEPTED] == "executive.task.accepted"
        assert TASK_EVENT_TYPES[TaskStatus.IN_PROGRESS] == "executive.task.started"
        assert TASK_EVENT_TYPES[TaskStatus.REPORTED] == "executive.task.reported"
        assert TASK_EVENT_TYPES[TaskStatus.AGGREGATED] == "executive.task.aggregated"
        assert TASK_EVENT_TYPES[TaskStatus.COMPLETED] == "executive.task.completed"
        assert TASK_EVENT_TYPES[TaskStatus.DECLINED] == "executive.task.declined"
        assert TASK_EVENT_TYPES[TaskStatus.QUARANTINED] == "executive.task.quarantined"
        assert TASK_EVENT_TYPES[TaskStatus.NULLIFIED] == "executive.task.nullified"


class TestGetEventTypeForStatus:
    """Tests for get_event_type_for_status() function."""

    def test_returns_correct_event_type(self):
        """Returns correct event type for status."""
        assert (
            get_event_type_for_status(TaskStatus.ACCEPTED) == "executive.task.accepted"
        )

    def test_raises_for_invalid_status(self):
        """Raises KeyError for non-TaskStatus values."""
        with pytest.raises(KeyError):
            get_event_type_for_status("invalid")  # type: ignore


class TestCreateTransitionEvent:
    """Tests for create_transition_event() function."""

    def test_creates_governance_event(self):
        """create_transition_event returns GovernanceEvent."""
        task = TaskState.create(
            task_id=uuid4(),
            earl_id="earl-1",
            created_at=datetime.now(timezone.utc),
        )

        event = create_transition_event(
            task_state=task,
            new_status=TaskStatus.ACTIVATED,
            transition_time=datetime.now(timezone.utc),
            actor_id="system",
            trace_id="trace-123",
        )

        assert isinstance(event, GovernanceEvent)

    def test_event_type_matches_new_status(self):
        """Event type matches the new status."""
        task = TaskState.create(
            task_id=uuid4(),
            earl_id="earl-1",
            created_at=datetime.now(timezone.utc),
        )

        event = create_transition_event(
            task_state=task,
            new_status=TaskStatus.ACTIVATED,
            transition_time=datetime.now(timezone.utc),
            actor_id="system",
            trace_id="trace-123",
        )

        assert event.event_type == "executive.task.activated"

    def test_payload_contains_task_id(self):
        """Event payload contains task_id."""
        task_id = uuid4()
        task = TaskState.create(
            task_id=task_id,
            earl_id="earl-1",
            created_at=datetime.now(timezone.utc),
        )

        event = create_transition_event(
            task_state=task,
            new_status=TaskStatus.ACTIVATED,
            transition_time=datetime.now(timezone.utc),
            actor_id="system",
            trace_id="trace-123",
        )

        assert event.payload["task_id"] == str(task_id)

    def test_payload_contains_transition_info(self):
        """Event payload contains from/to status."""
        task = TaskState.create(
            task_id=uuid4(),
            earl_id="earl-1",
            created_at=datetime.now(timezone.utc),
        )

        event = create_transition_event(
            task_state=task,
            new_status=TaskStatus.ACTIVATED,
            transition_time=datetime.now(timezone.utc),
            actor_id="system",
            trace_id="trace-123",
        )

        assert event.payload["from_status"] == "authorized"
        assert event.payload["to_status"] == "activated"

    def test_payload_contains_earl_id(self):
        """Event payload contains earl_id."""
        task = TaskState.create(
            task_id=uuid4(),
            earl_id="earl-42",
            created_at=datetime.now(timezone.utc),
        )

        event = create_transition_event(
            task_state=task,
            new_status=TaskStatus.ACTIVATED,
            transition_time=datetime.now(timezone.utc),
            actor_id="system",
            trace_id="trace-123",
        )

        assert event.payload["earl_id"] == "earl-42"

    def test_payload_includes_cluster_id_when_present(self):
        """Event payload includes cluster_id when set."""
        task = TaskState(
            task_id=uuid4(),
            earl_id="earl-1",
            cluster_id="cluster-99",
            current_status=TaskStatus.ROUTED,
            created_at=datetime.now(timezone.utc),
            state_entered_at=datetime.now(timezone.utc),
        )

        event = create_transition_event(
            task_state=task,
            new_status=TaskStatus.ACCEPTED,
            transition_time=datetime.now(timezone.utc),
            actor_id="cluster-99",
            trace_id="trace-123",
        )

        assert event.payload["cluster_id"] == "cluster-99"

    def test_payload_includes_reason_when_provided(self):
        """Event payload includes reason when provided."""
        task = TaskState(
            task_id=uuid4(),
            earl_id="earl-1",
            cluster_id="cluster-1",
            current_status=TaskStatus.ROUTED,
            created_at=datetime.now(timezone.utc),
            state_entered_at=datetime.now(timezone.utc),
        )

        event = create_transition_event(
            task_state=task,
            new_status=TaskStatus.DECLINED,
            transition_time=datetime.now(timezone.utc),
            actor_id="cluster-1",
            trace_id="trace-123",
            reason="No capacity available",
        )

        assert event.payload["reason"] == "No capacity available"

    def test_additional_payload_merged(self):
        """Additional payload is merged into event."""
        task = TaskState.create(
            task_id=uuid4(),
            earl_id="earl-1",
            created_at=datetime.now(timezone.utc),
        )

        event = create_transition_event(
            task_state=task,
            new_status=TaskStatus.ACTIVATED,
            transition_time=datetime.now(timezone.utc),
            actor_id="system",
            trace_id="trace-123",
            additional_payload={"priority": "high", "tags": ["urgent"]},
        )

        assert event.payload["priority"] == "high"
        assert event.payload["tags"] == ["urgent"]

    def test_event_metadata_correct(self):
        """Event metadata is correctly set."""
        now = datetime.now(timezone.utc)
        task = TaskState.create(
            task_id=uuid4(),
            earl_id="earl-1",
            created_at=now,
        )

        event = create_transition_event(
            task_state=task,
            new_status=TaskStatus.ACTIVATED,
            transition_time=now,
            actor_id="actor-42",
            trace_id="trace-xyz",
        )

        assert event.actor_id == "actor-42"
        assert event.trace_id == "trace-xyz"
        assert event.timestamp == now


class TestCreateTaskCreatedEvent:
    """Tests for create_task_created_event() function."""

    def test_creates_authorized_event(self):
        """Creates event with authorized event type."""
        task = TaskState.create(
            task_id=uuid4(),
            earl_id="earl-1",
            created_at=datetime.now(timezone.utc),
        )

        event = create_task_created_event(
            task_state=task,
            created_time=datetime.now(timezone.utc),
            actor_id="system",
            trace_id="trace-123",
        )

        assert event.event_type == "executive.task.authorized"

    def test_payload_contains_timeout_info(self):
        """Event payload contains timeout configuration."""
        task = TaskState.create(
            task_id=uuid4(),
            earl_id="earl-1",
            created_at=datetime.now(timezone.utc),
            ttl=timedelta(hours=24),
            inactivity_timeout=timedelta(hours=12),
            reporting_timeout=timedelta(days=3),
        )

        event = create_task_created_event(
            task_state=task,
            created_time=datetime.now(timezone.utc),
            actor_id="system",
            trace_id="trace-123",
        )

        assert event.payload["ttl_seconds"] == 24 * 3600
        assert event.payload["inactivity_timeout_seconds"] == 12 * 3600
        assert event.payload["reporting_timeout_seconds"] == 3 * 24 * 3600


class TestCreateHaltTransitionEvent:
    """Tests for create_halt_transition_event() function."""

    def test_pre_consent_halt_creates_nullified_event(self):
        """Pre-consent halt creates nullified event."""
        task = TaskState(
            task_id=uuid4(),
            earl_id="earl-1",
            cluster_id="cluster-1",
            current_status=TaskStatus.ROUTED,
            created_at=datetime.now(timezone.utc),
            state_entered_at=datetime.now(timezone.utc),
        )

        event = create_halt_transition_event(
            task_state=task,
            halt_reason="System halt triggered",
            halt_time=datetime.now(timezone.utc),
            actor_id="system",
            trace_id="trace-123",
        )

        assert event is not None
        assert event.event_type == "executive.task.nullified"
        assert event.payload["halt_triggered"] is True

    def test_post_consent_halt_creates_quarantined_event(self):
        """Post-consent halt creates quarantined event."""
        task = TaskState(
            task_id=uuid4(),
            earl_id="earl-1",
            cluster_id="cluster-1",
            current_status=TaskStatus.IN_PROGRESS,
            created_at=datetime.now(timezone.utc),
            state_entered_at=datetime.now(timezone.utc),
        )

        event = create_halt_transition_event(
            task_state=task,
            halt_reason="Emergency halt",
            halt_time=datetime.now(timezone.utc),
            actor_id="system",
            trace_id="trace-123",
        )

        assert event is not None
        assert event.event_type == "executive.task.quarantined"

    def test_terminal_state_returns_none(self):
        """Terminal state halt returns None (no transition needed)."""
        task = TaskState(
            task_id=uuid4(),
            earl_id="earl-1",
            cluster_id="cluster-1",
            current_status=TaskStatus.COMPLETED,
            created_at=datetime.now(timezone.utc),
            state_entered_at=datetime.now(timezone.utc),
        )

        event = create_halt_transition_event(
            task_state=task,
            halt_reason="System halt",
            halt_time=datetime.now(timezone.utc),
            actor_id="system",
            trace_id="trace-123",
        )

        assert event is None

    def test_halt_context_included(self):
        """Halt context is included in payload."""
        task = TaskState(
            task_id=uuid4(),
            earl_id="earl-1",
            cluster_id="cluster-1",
            current_status=TaskStatus.ACTIVATED,
            created_at=datetime.now(timezone.utc),
            state_entered_at=datetime.now(timezone.utc),
        )

        event = create_halt_transition_event(
            task_state=task,
            halt_reason="Fork detected",
            halt_time=datetime.now(timezone.utc),
            actor_id="system",
            trace_id="trace-123",
            halt_context={"fork_id": "fork-001", "severity": "critical"},
        )

        assert event is not None
        assert event.payload["halt_context"]["fork_id"] == "fork-001"
        assert event.payload["halt_context"]["severity"] == "critical"


class TestCreateTtlExpiryEvent:
    """Tests for create_ttl_expiry_event() function."""

    def test_creates_declined_event(self):
        """TTL expiry creates declined event."""
        task = TaskState(
            task_id=uuid4(),
            earl_id="earl-1",
            cluster_id="cluster-1",
            current_status=TaskStatus.ROUTED,
            created_at=datetime.now(timezone.utc),
            state_entered_at=datetime.now(timezone.utc),
            ttl=timedelta(hours=24),
        )

        event = create_ttl_expiry_event(
            task_state=task,
            expiry_time=datetime.now(timezone.utc),
            actor_id="timer-service",
            trace_id="trace-123",
        )

        assert event.event_type == "executive.task.declined"
        assert event.payload["ttl_expired"] is True

    def test_payload_contains_ttl_info(self):
        """Event payload contains TTL information."""
        task = TaskState(
            task_id=uuid4(),
            earl_id="earl-1",
            cluster_id="cluster-1",
            current_status=TaskStatus.ROUTED,
            created_at=datetime.now(timezone.utc),
            state_entered_at=datetime.now(timezone.utc),
            ttl=timedelta(hours=48),
        )

        event = create_ttl_expiry_event(
            task_state=task,
            expiry_time=datetime.now(timezone.utc),
            actor_id="timer-service",
            trace_id="trace-123",
        )

        assert event.payload["ttl_seconds"] == 48 * 3600
        assert event.payload["reason"] == "TTL expired without acceptance"


class TestEventBranchDerivation:
    """Tests for event branch derivation."""

    def test_all_task_events_have_executive_branch(self):
        """All task events derive to executive branch."""
        task = TaskState.create(
            task_id=uuid4(),
            earl_id="earl-1",
            created_at=datetime.now(timezone.utc),
        )

        event = create_transition_event(
            task_state=task,
            new_status=TaskStatus.ACTIVATED,
            transition_time=datetime.now(timezone.utc),
            actor_id="system",
            trace_id="trace-123",
        )

        assert event.branch == "executive"
