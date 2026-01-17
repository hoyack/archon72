"""Unit tests for TaskState and TaskStatus domain models.

Story: consent-gov-2.1: Task State Machine Domain Model

Tests:
- AC1: Task states enumerated (all 11 states)
- AC2: TaskState is immutable (frozen dataclass)
- AC3: State transitions validated
- AC6: transition() returns new TaskState (immutable pattern)
- AC10: Task includes all required metadata
"""

import pytest
from datetime import datetime, timezone, timedelta
from uuid import uuid4

from src.domain.errors.constitutional import ConstitutionalViolationError
from src.domain.governance.task.task_state import (
    TaskStatus,
    TaskState,
    IllegalStateTransitionError,
    _PRE_CONSENT_STATES,
    _POST_CONSENT_STATES,
    _TERMINAL_STATES,
)


class TestTaskStatus:
    """Tests for TaskStatus enumeration (AC1)."""

    def test_all_11_states_defined(self):
        """AC1: All 11 task states are enumerated."""
        expected_states = {
            "authorized",
            "activated",
            "routed",
            "accepted",
            "in_progress",
            "reported",
            "aggregated",
            "completed",
            "declined",
            "quarantined",
            "nullified",
        }
        actual_states = {s.value for s in TaskStatus}
        assert actual_states == expected_states

    def test_pre_consent_states(self):
        """Pre-consent states correctly identified."""
        assert TaskStatus.AUTHORIZED.is_pre_consent
        assert TaskStatus.ACTIVATED.is_pre_consent
        assert TaskStatus.ROUTED.is_pre_consent
        assert not TaskStatus.ACCEPTED.is_pre_consent
        assert not TaskStatus.COMPLETED.is_pre_consent

    def test_post_consent_states(self):
        """Post-consent states correctly identified."""
        assert TaskStatus.ACCEPTED.is_post_consent
        assert TaskStatus.IN_PROGRESS.is_post_consent
        assert TaskStatus.REPORTED.is_post_consent
        assert TaskStatus.AGGREGATED.is_post_consent
        assert not TaskStatus.AUTHORIZED.is_post_consent
        assert not TaskStatus.COMPLETED.is_post_consent

    def test_terminal_states(self):
        """Terminal states correctly identified."""
        assert TaskStatus.COMPLETED.is_terminal
        assert TaskStatus.DECLINED.is_terminal
        assert TaskStatus.QUARANTINED.is_terminal
        assert TaskStatus.NULLIFIED.is_terminal
        assert not TaskStatus.AUTHORIZED.is_terminal
        assert not TaskStatus.IN_PROGRESS.is_terminal

    def test_state_categories_are_disjoint(self):
        """State categories don't overlap."""
        assert _PRE_CONSENT_STATES.isdisjoint(_POST_CONSENT_STATES)
        assert _PRE_CONSENT_STATES.isdisjoint(_TERMINAL_STATES)
        assert _POST_CONSENT_STATES.isdisjoint(_TERMINAL_STATES)

    def test_state_categories_cover_all_states(self):
        """All states belong to exactly one category."""
        all_categorized = _PRE_CONSENT_STATES | _POST_CONSENT_STATES | _TERMINAL_STATES
        all_states = set(TaskStatus)
        assert all_categorized == all_states


class TestTaskState:
    """Tests for TaskState domain model (AC2, AC10)."""

    def test_taskstate_is_frozen(self):
        """AC2: TaskState is immutable (frozen dataclass)."""
        task = TaskState(
            task_id=uuid4(),
            earl_id="earl-1",
            cluster_id=None,
            current_status=TaskStatus.AUTHORIZED,
            created_at=datetime.now(timezone.utc),
            state_entered_at=datetime.now(timezone.utc),
        )

        with pytest.raises(Exception):  # FrozenInstanceError
            task.task_id = uuid4()  # type: ignore

    def test_taskstate_required_fields(self):
        """AC10: Task includes required metadata fields."""
        task_id = uuid4()
        earl_id = "earl-1"
        cluster_id = "cluster-1"
        now = datetime.now(timezone.utc)
        ttl = timedelta(hours=48)

        task = TaskState(
            task_id=task_id,
            earl_id=earl_id,
            cluster_id=cluster_id,
            current_status=TaskStatus.AUTHORIZED,
            created_at=now,
            state_entered_at=now,
            ttl=ttl,
        )

        assert task.task_id == task_id
        assert task.earl_id == earl_id
        assert task.cluster_id == cluster_id
        assert task.current_status == TaskStatus.AUTHORIZED
        assert task.created_at == now
        assert task.state_entered_at == now
        assert task.ttl == ttl

    def test_taskstate_default_timeouts(self):
        """TaskState has sensible default timeouts."""
        task = TaskState(
            task_id=uuid4(),
            earl_id="earl-1",
            cluster_id=None,
            current_status=TaskStatus.AUTHORIZED,
            created_at=datetime.now(timezone.utc),
            state_entered_at=datetime.now(timezone.utc),
        )

        assert task.ttl == timedelta(hours=72)
        assert task.inactivity_timeout == timedelta(hours=48)
        assert task.reporting_timeout == timedelta(days=7)

    def test_taskstate_validation_invalid_task_id(self):
        """Invalid task_id raises ConstitutionalViolationError."""
        with pytest.raises(ConstitutionalViolationError, match="task_id must be UUID"):
            TaskState(
                task_id="not-a-uuid",  # type: ignore
                earl_id="earl-1",
                cluster_id=None,
                current_status=TaskStatus.AUTHORIZED,
                created_at=datetime.now(timezone.utc),
                state_entered_at=datetime.now(timezone.utc),
            )

    def test_taskstate_validation_empty_earl_id(self):
        """Empty earl_id raises ConstitutionalViolationError."""
        with pytest.raises(ConstitutionalViolationError, match="earl_id must be non-empty"):
            TaskState(
                task_id=uuid4(),
                earl_id="  ",
                cluster_id=None,
                current_status=TaskStatus.AUTHORIZED,
                created_at=datetime.now(timezone.utc),
                state_entered_at=datetime.now(timezone.utc),
            )

    def test_taskstate_validation_invalid_status(self):
        """Invalid current_status raises ConstitutionalViolationError."""
        with pytest.raises(ConstitutionalViolationError, match="current_status must be TaskStatus"):
            TaskState(
                task_id=uuid4(),
                earl_id="earl-1",
                cluster_id=None,
                current_status="authorized",  # type: ignore
                created_at=datetime.now(timezone.utc),
                state_entered_at=datetime.now(timezone.utc),
            )

    def test_taskstate_validation_invalid_timestamps(self):
        """Invalid timestamps raise ConstitutionalViolationError."""
        with pytest.raises(ConstitutionalViolationError, match="created_at must be datetime"):
            TaskState(
                task_id=uuid4(),
                earl_id="earl-1",
                cluster_id=None,
                current_status=TaskStatus.AUTHORIZED,
                created_at="2026-01-16",  # type: ignore
                state_entered_at=datetime.now(timezone.utc),
            )

    def test_taskstate_validation_invalid_ttl(self):
        """Invalid ttl raises ConstitutionalViolationError."""
        with pytest.raises(ConstitutionalViolationError, match="ttl must be positive"):
            TaskState(
                task_id=uuid4(),
                earl_id="earl-1",
                cluster_id=None,
                current_status=TaskStatus.AUTHORIZED,
                created_at=datetime.now(timezone.utc),
                state_entered_at=datetime.now(timezone.utc),
                ttl=timedelta(0),
            )

    def test_is_pre_consent_property(self):
        """is_pre_consent property works correctly."""
        for status in [TaskStatus.AUTHORIZED, TaskStatus.ACTIVATED, TaskStatus.ROUTED]:
            task = TaskState(
                task_id=uuid4(),
                earl_id="earl-1",
                cluster_id=None,
                current_status=status,
                created_at=datetime.now(timezone.utc),
                state_entered_at=datetime.now(timezone.utc),
            )
            assert task.is_pre_consent is True

    def test_is_post_consent_property(self):
        """is_post_consent property works correctly."""
        for status in [TaskStatus.ACCEPTED, TaskStatus.IN_PROGRESS]:
            task = TaskState(
                task_id=uuid4(),
                earl_id="earl-1",
                cluster_id="cluster-1",
                current_status=status,
                created_at=datetime.now(timezone.utc),
                state_entered_at=datetime.now(timezone.utc),
            )
            assert task.is_post_consent is True

    def test_is_terminal_property(self):
        """is_terminal property works correctly."""
        for status in [TaskStatus.COMPLETED, TaskStatus.DECLINED, TaskStatus.QUARANTINED, TaskStatus.NULLIFIED]:
            task = TaskState(
                task_id=uuid4(),
                earl_id="earl-1",
                cluster_id="cluster-1",
                current_status=status,
                created_at=datetime.now(timezone.utc),
                state_entered_at=datetime.now(timezone.utc),
            )
            assert task.is_terminal is True


class TestTaskStateTransition:
    """Tests for TaskState.transition() method (AC3, AC6)."""

    def test_valid_transition_authorized_to_activated(self):
        """AC3: Valid transition succeeds."""
        task = TaskState(
            task_id=uuid4(),
            earl_id="earl-1",
            cluster_id=None,
            current_status=TaskStatus.AUTHORIZED,
            created_at=datetime.now(timezone.utc),
            state_entered_at=datetime.now(timezone.utc),
        )

        new_task = task.transition(
            TaskStatus.ACTIVATED,
            datetime.now(timezone.utc),
            "system",
        )

        assert new_task.current_status == TaskStatus.ACTIVATED
        assert new_task.task_id == task.task_id

    def test_transition_returns_new_instance(self):
        """AC6: transition() returns new TaskState, original unchanged."""
        task = TaskState(
            task_id=uuid4(),
            earl_id="earl-1",
            cluster_id=None,
            current_status=TaskStatus.AUTHORIZED,
            created_at=datetime.now(timezone.utc),
            state_entered_at=datetime.now(timezone.utc),
        )

        new_task = task.transition(
            TaskStatus.ACTIVATED,
            datetime.now(timezone.utc),
            "system",
        )

        assert new_task is not task
        assert task.current_status == TaskStatus.AUTHORIZED  # Original unchanged
        assert new_task.current_status == TaskStatus.ACTIVATED

    def test_transition_updates_state_entered_at(self):
        """transition() updates state_entered_at."""
        created = datetime.now(timezone.utc)
        transitioned = created + timedelta(minutes=5)

        task = TaskState(
            task_id=uuid4(),
            earl_id="earl-1",
            cluster_id=None,
            current_status=TaskStatus.AUTHORIZED,
            created_at=created,
            state_entered_at=created,
        )

        new_task = task.transition(
            TaskStatus.ACTIVATED,
            transitioned,
            "system",
        )

        assert new_task.state_entered_at == transitioned
        assert new_task.created_at == created  # Created unchanged

    def test_invalid_transition_raises_error(self):
        """AC3: Invalid transition raises IllegalStateTransitionError."""
        task = TaskState(
            task_id=uuid4(),
            earl_id="earl-1",
            cluster_id=None,
            current_status=TaskStatus.AUTHORIZED,
            created_at=datetime.now(timezone.utc),
            state_entered_at=datetime.now(timezone.utc),
        )

        with pytest.raises(IllegalStateTransitionError) as exc:
            task.transition(
                TaskStatus.COMPLETED,  # Cannot jump to completed
                datetime.now(timezone.utc),
                "system",
            )

        assert exc.value.current_state == TaskStatus.AUTHORIZED
        assert exc.value.attempted_state == TaskStatus.COMPLETED
        assert TaskStatus.ACTIVATED in exc.value.allowed_states

    def test_terminal_states_have_no_transitions(self):
        """AC9: Terminal states cannot transition to anything."""
        for terminal_status in [
            TaskStatus.COMPLETED,
            TaskStatus.DECLINED,
            TaskStatus.QUARANTINED,
            TaskStatus.NULLIFIED,
        ]:
            task = TaskState(
                task_id=uuid4(),
                earl_id="earl-1",
                cluster_id="cluster-1",
                current_status=terminal_status,
                created_at=datetime.now(timezone.utc),
                state_entered_at=datetime.now(timezone.utc),
            )

            # Any transition should fail
            with pytest.raises(IllegalStateTransitionError):
                task.transition(
                    TaskStatus.AUTHORIZED,
                    datetime.now(timezone.utc),
                    "system",
                )

    def test_routed_to_accepted_valid(self):
        """Consent gate: routed → accepted is valid."""
        task = TaskState(
            task_id=uuid4(),
            earl_id="earl-1",
            cluster_id="cluster-1",
            current_status=TaskStatus.ROUTED,
            created_at=datetime.now(timezone.utc),
            state_entered_at=datetime.now(timezone.utc),
        )

        new_task = task.transition(
            TaskStatus.ACCEPTED,
            datetime.now(timezone.utc),
            "cluster-1",
        )

        assert new_task.current_status == TaskStatus.ACCEPTED

    def test_routed_to_declined_valid(self):
        """Consent gate: routed → declined is valid (explicit decline or TTL)."""
        task = TaskState(
            task_id=uuid4(),
            earl_id="earl-1",
            cluster_id="cluster-1",
            current_status=TaskStatus.ROUTED,
            created_at=datetime.now(timezone.utc),
            state_entered_at=datetime.now(timezone.utc),
        )

        new_task = task.transition(
            TaskStatus.DECLINED,
            datetime.now(timezone.utc),
            "cluster-1",
            reason="No capacity",
        )

        assert new_task.current_status == TaskStatus.DECLINED

    def test_accepted_to_declined_valid(self):
        """Accepted can transition to declined (changed mind)."""
        task = TaskState(
            task_id=uuid4(),
            earl_id="earl-1",
            cluster_id="cluster-1",
            current_status=TaskStatus.ACCEPTED,
            created_at=datetime.now(timezone.utc),
            state_entered_at=datetime.now(timezone.utc),
        )

        new_task = task.transition(
            TaskStatus.DECLINED,
            datetime.now(timezone.utc),
            "cluster-1",
        )

        assert new_task.current_status == TaskStatus.DECLINED


class TestTaskStateHaltTransitions:
    """Tests for halt-triggered transitions."""

    def test_pre_consent_halt_to_nullified(self):
        """Pre-consent halt transitions to nullified."""
        for status in [TaskStatus.ACTIVATED, TaskStatus.ROUTED]:
            task = TaskState(
                task_id=uuid4(),
                earl_id="earl-1",
                cluster_id="cluster-1" if status != TaskStatus.AUTHORIZED else None,
                current_status=status,
                created_at=datetime.now(timezone.utc),
                state_entered_at=datetime.now(timezone.utc),
            )

            new_task = task.transition(
                TaskStatus.NULLIFIED,
                datetime.now(timezone.utc),
                "system",
            )

            assert new_task.current_status == TaskStatus.NULLIFIED

    def test_post_consent_halt_to_quarantined(self):
        """Post-consent halt transitions to quarantined."""
        for status in [TaskStatus.ACCEPTED, TaskStatus.IN_PROGRESS]:
            task = TaskState(
                task_id=uuid4(),
                earl_id="earl-1",
                cluster_id="cluster-1",
                current_status=status,
                created_at=datetime.now(timezone.utc),
                state_entered_at=datetime.now(timezone.utc),
            )

            new_task = task.transition(
                TaskStatus.QUARANTINED,
                datetime.now(timezone.utc),
                "system",
            )

            assert new_task.current_status == TaskStatus.QUARANTINED


class TestTaskStateCreate:
    """Tests for TaskState.create() factory method."""

    def test_create_returns_authorized_state(self):
        """create() returns task in AUTHORIZED state."""
        task_id = uuid4()
        now = datetime.now(timezone.utc)

        task = TaskState.create(
            task_id=task_id,
            earl_id="earl-1",
            created_at=now,
        )

        assert task.task_id == task_id
        assert task.earl_id == "earl-1"
        assert task.cluster_id is None
        assert task.current_status == TaskStatus.AUTHORIZED
        assert task.created_at == now
        assert task.state_entered_at == now

    def test_create_with_custom_timeouts(self):
        """create() accepts custom timeout values."""
        ttl = timedelta(hours=24)
        inactivity = timedelta(hours=12)
        reporting = timedelta(days=3)

        task = TaskState.create(
            task_id=uuid4(),
            earl_id="earl-1",
            created_at=datetime.now(timezone.utc),
            ttl=ttl,
            inactivity_timeout=inactivity,
            reporting_timeout=reporting,
        )

        assert task.ttl == ttl
        assert task.inactivity_timeout == inactivity
        assert task.reporting_timeout == reporting


class TestTaskStateWithCluster:
    """Tests for TaskState.with_cluster() method."""

    def test_with_cluster_returns_new_instance(self):
        """with_cluster() returns new instance with cluster set."""
        task = TaskState(
            task_id=uuid4(),
            earl_id="earl-1",
            cluster_id=None,
            current_status=TaskStatus.ACTIVATED,
            created_at=datetime.now(timezone.utc),
            state_entered_at=datetime.now(timezone.utc),
        )

        new_task = task.with_cluster("cluster-42")

        assert new_task.cluster_id == "cluster-42"
        assert task.cluster_id is None  # Original unchanged

    def test_with_cluster_invalid_raises_error(self):
        """with_cluster() raises error for invalid cluster_id."""
        task = TaskState(
            task_id=uuid4(),
            earl_id="earl-1",
            cluster_id=None,
            current_status=TaskStatus.ACTIVATED,
            created_at=datetime.now(timezone.utc),
            state_entered_at=datetime.now(timezone.utc),
        )

        with pytest.raises(ConstitutionalViolationError, match="cluster_id must be non-empty"):
            task.with_cluster("  ")


class TestTaskStateTimeoutChecks:
    """Tests for timeout checking methods."""

    def test_is_ttl_expired_pre_consent(self):
        """is_ttl_expired works for pre-consent states."""
        created = datetime.now(timezone.utc)
        task = TaskState(
            task_id=uuid4(),
            earl_id="earl-1",
            cluster_id=None,
            current_status=TaskStatus.ROUTED,
            created_at=created,
            state_entered_at=created,
            ttl=timedelta(hours=24),
        )

        # Not expired yet
        assert task.is_ttl_expired(created + timedelta(hours=12)) is False

        # Expired
        assert task.is_ttl_expired(created + timedelta(hours=25)) is True

    def test_is_ttl_expired_post_consent_always_false(self):
        """is_ttl_expired returns False for post-consent states."""
        created = datetime.now(timezone.utc)
        task = TaskState(
            task_id=uuid4(),
            earl_id="earl-1",
            cluster_id="cluster-1",
            current_status=TaskStatus.ACCEPTED,
            created_at=created,
            state_entered_at=created,
            ttl=timedelta(hours=24),
        )

        # Even after TTL would expire, returns False for post-consent
        assert task.is_ttl_expired(created + timedelta(hours=100)) is False

    def test_is_inactive_in_progress(self):
        """is_inactive works for in_progress state."""
        created = datetime.now(timezone.utc)
        task = TaskState(
            task_id=uuid4(),
            earl_id="earl-1",
            cluster_id="cluster-1",
            current_status=TaskStatus.IN_PROGRESS,
            created_at=created,
            state_entered_at=created,
            inactivity_timeout=timedelta(hours=48),
        )

        # Not inactive yet
        assert task.is_inactive(created + timedelta(hours=24)) is False

        # Inactive
        assert task.is_inactive(created + timedelta(hours=49)) is True

    def test_is_inactive_other_states_always_false(self):
        """is_inactive returns False for non-in_progress states."""
        created = datetime.now(timezone.utc)
        task = TaskState(
            task_id=uuid4(),
            earl_id="earl-1",
            cluster_id="cluster-1",
            current_status=TaskStatus.ACCEPTED,
            created_at=created,
            state_entered_at=created,
        )

        assert task.is_inactive(created + timedelta(days=100)) is False


class TestIllegalStateTransitionError:
    """Tests for IllegalStateTransitionError exception."""

    def test_error_contains_state_info(self):
        """Error contains current, attempted, and allowed states."""
        error = IllegalStateTransitionError(
            current_state=TaskStatus.AUTHORIZED,
            attempted_state=TaskStatus.COMPLETED,
            allowed_states=frozenset({TaskStatus.ACTIVATED}),
        )

        assert error.current_state == TaskStatus.AUTHORIZED
        assert error.attempted_state == TaskStatus.COMPLETED
        assert error.allowed_states == frozenset({TaskStatus.ACTIVATED})

    def test_error_message_format(self):
        """Error message includes relevant state information."""
        error = IllegalStateTransitionError(
            current_state=TaskStatus.AUTHORIZED,
            attempted_state=TaskStatus.COMPLETED,
            allowed_states=frozenset({TaskStatus.ACTIVATED}),
        )

        message = str(error)
        assert "authorized" in message
        assert "completed" in message
        assert "activated" in message

    def test_error_inherits_from_constitutional(self):
        """IllegalStateTransitionError is a ConstitutionalViolationError."""
        error = IllegalStateTransitionError(
            current_state=TaskStatus.AUTHORIZED,
            attempted_state=TaskStatus.COMPLETED,
            allowed_states=frozenset({TaskStatus.ACTIVATED}),
        )

        assert isinstance(error, ConstitutionalViolationError)
