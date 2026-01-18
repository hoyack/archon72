"""Performance tests for task state machine.

Story: consent-gov-2.1: Task State Machine Domain Model

Tests:
- AC4: State machine resolution completes in ≤10ms (NFR-PERF-05)

Note: These tests are timing-sensitive and may fail on slower CI runners.
They are marked with @pytest.mark.performance and skipped in CI.
"""

import contextlib
import time

import pytest

# Mark all tests in this module as performance tests (skipped in CI)
pytestmark = pytest.mark.performance
from datetime import datetime, timezone
from uuid import uuid4

from src.domain.governance.task.task_state import (
    IllegalStateTransitionError,
    TaskState,
    TaskStatus,
)
from src.domain.governance.task.task_state_rules import TaskTransitionRules


class TestStateTransitionPerformance:
    """AC4: State machine resolution ≤10ms (NFR-PERF-05)."""

    def test_single_transition_under_10ms(self):
        """Single state transition completes in under 10ms."""
        task = TaskState.create(
            task_id=uuid4(),
            earl_id="earl-1",
            created_at=datetime.now(timezone.utc),
        )

        start = time.perf_counter()
        new_task = task.transition(
            TaskStatus.ACTIVATED,
            datetime.now(timezone.utc),
            "actor",
        )
        elapsed = time.perf_counter() - start

        assert elapsed < 0.010, f"Transition took {elapsed * 1000:.2f}ms (limit: 10ms)"
        assert new_task.current_status == TaskStatus.ACTIVATED

    def test_1000_transitions_average_under_10ms(self):
        """Average of 1000 transitions completes in under 10ms each."""
        task = TaskState(
            task_id=uuid4(),
            earl_id="earl-1",
            cluster_id=None,
            current_status=TaskStatus.ROUTED,
            created_at=datetime.now(timezone.utc),
            state_entered_at=datetime.now(timezone.utc),
        )

        start = time.perf_counter()
        for _ in range(1000):
            with contextlib.suppress(IllegalStateTransitionError):
                task.transition(
                    TaskStatus.ACCEPTED,
                    datetime.now(timezone.utc),
                    "actor",
                )
        elapsed = (time.perf_counter() - start) / 1000

        assert elapsed <= 0.010, (
            f"Average transition took {elapsed * 1000:.2f}ms (limit: 10ms)"
        )

    def test_transition_validation_o1(self):
        """Transition validation is O(1) - constant time lookup."""
        # Test with various states to confirm O(1) behavior
        times = []

        for status in TaskStatus:
            start = time.perf_counter()
            for _ in range(10000):
                TaskTransitionRules.is_valid_transition(status, TaskStatus.COMPLETED)
            elapsed = time.perf_counter() - start
            times.append(elapsed)

        # All times should be similar (within 2x of each other for O(1))
        max_time = max(times)
        min_time = min(times)
        assert max_time / min_time < 3.0, (
            f"Transition validation not O(1): min={min_time * 1000:.2f}ms, "
            f"max={max_time * 1000:.2f}ms"
        )


class TestTransitionRulesPerformance:
    """Performance tests for TaskTransitionRules."""

    def test_is_valid_transition_lookup_performance(self):
        """is_valid_transition lookup is fast (O(1))."""
        start = time.perf_counter()
        for _ in range(100000):
            TaskTransitionRules.is_valid_transition(
                TaskStatus.ROUTED, TaskStatus.ACCEPTED
            )
        elapsed = time.perf_counter() - start

        # 100k lookups should complete in under 100ms
        assert elapsed < 0.100, f"100k lookups took {elapsed * 1000:.2f}ms"

    def test_get_allowed_transitions_lookup_performance(self):
        """get_allowed_transitions lookup is fast."""
        start = time.perf_counter()
        for _ in range(100000):
            TaskTransitionRules.get_allowed_transitions(TaskStatus.ROUTED)
        elapsed = time.perf_counter() - start

        # 100k lookups should complete in under 100ms
        assert elapsed < 0.100, f"100k lookups took {elapsed * 1000:.2f}ms"

    def test_get_halt_target_lookup_performance(self):
        """get_halt_target lookup is fast."""
        start = time.perf_counter()
        for _ in range(100000):
            TaskTransitionRules.get_halt_target(TaskStatus.IN_PROGRESS)
        elapsed = time.perf_counter() - start

        # 100k lookups should complete in under 100ms
        assert elapsed < 0.100, f"100k lookups took {elapsed * 1000:.2f}ms"


class TestTaskStateCreationPerformance:
    """Performance tests for TaskState creation."""

    def test_taskstate_creation_fast(self):
        """TaskState creation is fast."""
        now = datetime.now(timezone.utc)

        start = time.perf_counter()
        for _ in range(1000):
            TaskState.create(
                task_id=uuid4(),
                earl_id="earl-1",
                created_at=now,
            )
        elapsed = (time.perf_counter() - start) / 1000

        # Each creation should take under 1ms
        assert elapsed < 0.001, f"TaskState.create took {elapsed * 1000:.2f}ms avg"

    def test_taskstate_with_cluster_fast(self):
        """with_cluster() method is fast."""
        task = TaskState.create(
            task_id=uuid4(),
            earl_id="earl-1",
            created_at=datetime.now(timezone.utc),
        )

        start = time.perf_counter()
        for _ in range(10000):
            task.with_cluster("cluster-1")
        elapsed = (time.perf_counter() - start) / 10000

        # Each call should take under 0.1ms
        assert elapsed < 0.0001, f"with_cluster took {elapsed * 1000000:.2f}μs avg"


class TestImmutabilityPerformance:
    """Performance tests ensuring immutability doesn't hurt performance."""

    def test_frozen_dataclass_attribute_access_fast(self):
        """Attribute access on frozen dataclass is fast."""
        task = TaskState.create(
            task_id=uuid4(),
            earl_id="earl-1",
            created_at=datetime.now(timezone.utc),
        )

        start = time.perf_counter()
        for _ in range(100000):
            _ = task.task_id
            _ = task.current_status
            _ = task.is_pre_consent
        elapsed = time.perf_counter() - start

        # 100k attribute accesses should be very fast
        assert elapsed < 0.050, f"100k attribute accesses took {elapsed * 1000:.2f}ms"
