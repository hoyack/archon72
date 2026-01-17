# Story consent-gov-2.1: Task State Machine Domain Model

Status: ready-for-dev

---

## Story

As a **governance system**,
I want **a task state machine with defined transitions**,
So that **tasks can only move through legal states, ensuring consent-based coordination and dignity-preserving workflows**.

---

## Acceptance Criteria

1. **AC1:** Task states enumerated: `authorized`, `activated`, `routed`, `accepted`, `in_progress`, `reported`, `aggregated`, `completed`, `declined`, `quarantined`, `nullified`
2. **AC2:** `TaskState` domain model is immutable (frozen dataclass)
3. **AC3:** State transitions validated - illegal transitions rejected with `IllegalStateTransitionError`
4. **AC4:** State machine resolution completes in ≤10ms (NFR-PERF-05)
5. **AC5:** All transitions emit events to ledger via `executive.task.{verb}` pattern
6. **AC6:** `transition()` method returns new `TaskState` (immutable pattern)
7. **AC7:** Transition rules defined in separate `TaskTransitionRules` class
8. **AC8:** Unit tests for all valid state transitions
9. **AC9:** Unit tests for invalid transition rejection
10. **AC10:** Task includes metadata: `task_id`, `earl_id`, `cluster_id`, `created_at`, `ttl`, `current_state`

---

## Tasks / Subtasks

- [ ] **Task 1: Create task domain module structure** (AC: All)
  - [ ] Create `src/domain/governance/task/__init__.py`
  - [ ] Create `src/domain/governance/task/task_state.py`
  - [ ] Create `src/domain/governance/task/task_state_rules.py`
  - [ ] Create `src/domain/governance/task/task_events.py`

- [ ] **Task 2: Implement TaskStatus enumeration** (AC: 1)
  - [ ] Define `TaskStatus` enum with all 11 states
  - [ ] Add status descriptions for documentation
  - [ ] Define status categories (pre-consent, post-consent, terminal)

- [ ] **Task 3: Implement TaskState domain model** (AC: 2, 10)
  - [ ] Define frozen dataclass with required fields
  - [ ] Add `task_id`, `earl_id`, `cluster_id`, `created_at`, `ttl`
  - [ ] Add `current_status: TaskStatus`
  - [ ] Add `state_entered_at: datetime` for tracking
  - [ ] Implement `__post_init__` validation

- [ ] **Task 4: Implement TaskTransitionRules** (AC: 7)
  - [ ] Define `VALID_TRANSITIONS` mapping (current_state → allowed_next_states)
  - [ ] Define consent gate transitions (require explicit accept/decline)
  - [ ] Define auto-transition rules (TTL expiry, inactivity)
  - [ ] Define halt-triggered transitions (nullified, quarantined)

- [ ] **Task 5: Implement state transition method** (AC: 3, 6)
  - [ ] Create `TaskState.transition()` method
  - [ ] Validate transition against `TaskTransitionRules`
  - [ ] Return new `TaskState` instance (immutable)
  - [ ] Raise `IllegalStateTransitionError` for invalid transitions
  - [ ] Include transition reason in error message

- [ ] **Task 6: Define task event types** (AC: 5)
  - [ ] Register `executive.task.authorized` event type
  - [ ] Register `executive.task.activated` event type
  - [ ] Register `executive.task.routed` event type
  - [ ] Register `executive.task.accepted` event type
  - [ ] Register `executive.task.declined` event type
  - [ ] Register `executive.task.halted` event type
  - [ ] Register `executive.task.reported` event type
  - [ ] Register `executive.task.completed` event type
  - [ ] Register `executive.task.quarantined` event type
  - [ ] Register `executive.task.nullified` event type

- [ ] **Task 7: Implement transition event generation** (AC: 5)
  - [ ] Create `TaskState.create_transition_event()` method
  - [ ] Generate appropriate event type based on new state
  - [ ] Include transition metadata in event payload

- [ ] **Task 8: Add performance optimization** (AC: 4)
  - [ ] Pre-compute transition lookups (O(1) validation)
  - [ ] Minimize allocations in hot path
  - [ ] Add performance test for ≤10ms requirement

- [ ] **Task 9: Write comprehensive unit tests** (AC: 8, 9)
  - [ ] Test all valid transitions (authorized→activated, etc.)
  - [ ] Test all invalid transitions raise error
  - [ ] Test immutability (transition returns new instance)
  - [ ] Test consent gate enforcement
  - [ ] Test halt transitions
  - [ ] Test performance requirement (≤10ms)

---

## Documentation Checklist

- [ ] Architecture docs updated (task state machine diagram)
- [ ] Inline comments explaining consent gates
- [ ] N/A - API docs (domain model)
- [ ] N/A - README (internal component)

---

## Dev Notes

### Architecture Compliance (CRITICAL)

**From governance-architecture.md:**

This story implements the task state machine for consent-based coordination.

**Golden Rule Enforcement:**
> "No silent assignment - Task state machine requires explicit accept/decline transition"

**Task States (11 total):**

| State | Category | Description |
|-------|----------|-------------|
| `authorized` | Pre-consent | Task created by system, not yet offered |
| `activated` | Pre-consent | Task offered to Cluster via Earl |
| `routed` | Pre-consent | Task routed to Cluster (async delivery) |
| `accepted` | Post-consent | Cluster explicitly accepted |
| `in_progress` | Post-consent | Work actively being done |
| `reported` | Post-consent | Result submitted by Cluster |
| `aggregated` | Post-consent | Results aggregated (multi-cluster) |
| `completed` | Terminal | Task successfully finished |
| `declined` | Terminal | Cluster declined (or TTL expired) |
| `quarantined` | Terminal | Task isolated due to issue |
| `nullified` | Terminal | Task cancelled (pre-consent halt) |

**State Transition Diagram:**
```
                    authorized
                        │
                        ▼
                    activated
                        │
                        ▼
                      routed ──────────────► declined (TTL)
                        │                       ▲
                        ▼                       │
                    accepted ─────────────────────┘ (explicit decline)
                        │
                        ▼
                   in_progress ──────────────► quarantined (timeout/issue)
                        │
                        ▼
                     reported
                        │
                        ▼
                    aggregated
                        │
                        ▼
                    completed

HALT TRANSITIONS (any pre-consent state → nullified)
HALT TRANSITIONS (any post-consent state → quarantined)
```

### Valid State Transitions (Locked)

```python
VALID_TRANSITIONS: dict[TaskStatus, frozenset[TaskStatus]] = {
    TaskStatus.AUTHORIZED: frozenset({TaskStatus.ACTIVATED}),
    TaskStatus.ACTIVATED: frozenset({TaskStatus.ROUTED, TaskStatus.NULLIFIED}),
    TaskStatus.ROUTED: frozenset({
        TaskStatus.ACCEPTED,
        TaskStatus.DECLINED,  # Explicit decline OR TTL expiry
        TaskStatus.NULLIFIED,  # Halt (pre-consent)
    }),
    TaskStatus.ACCEPTED: frozenset({
        TaskStatus.IN_PROGRESS,
        TaskStatus.DECLINED,  # Changed mind before starting
        TaskStatus.QUARANTINED,  # Halt (post-consent)
    }),
    TaskStatus.IN_PROGRESS: frozenset({
        TaskStatus.REPORTED,
        TaskStatus.QUARANTINED,  # Timeout or halt
    }),
    TaskStatus.REPORTED: frozenset({
        TaskStatus.AGGREGATED,
        TaskStatus.COMPLETED,  # Direct completion for single-cluster
    }),
    TaskStatus.AGGREGATED: frozenset({TaskStatus.COMPLETED}),
    # Terminal states - no transitions out
    TaskStatus.COMPLETED: frozenset(),
    TaskStatus.DECLINED: frozenset(),
    TaskStatus.QUARANTINED: frozenset(),
    TaskStatus.NULLIFIED: frozenset(),
}
```

### Consent Gates

**Pre-Consent States:** `authorized`, `activated`, `routed`
- Cluster has not yet agreed to work
- Task can be declined without penalty
- Halt → `nullified`

**Post-Consent States:** `accepted`, `in_progress`, `reported`, `aggregated`
- Cluster has agreed to work
- Cluster can still halt without penalty (FR5)
- Halt → `quarantined`

**Consent Gate Transition:**
```
routed → accepted  (REQUIRES explicit Cluster acceptance)
routed → declined  (explicit decline OR TTL expiry)
```

### TaskState Domain Model

```python
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from uuid import UUID

class TaskStatus(Enum):
    """All possible task states."""
    AUTHORIZED = "authorized"
    ACTIVATED = "activated"
    ROUTED = "routed"
    ACCEPTED = "accepted"
    IN_PROGRESS = "in_progress"
    REPORTED = "reported"
    AGGREGATED = "aggregated"
    COMPLETED = "completed"
    DECLINED = "declined"
    QUARANTINED = "quarantined"
    NULLIFIED = "nullified"

@dataclass(frozen=True)
class TaskState:
    """Immutable task state with transition capabilities.

    Constitutional Guarantee:
    - Transitions are validated against rules
    - Invalid transitions raise IllegalStateTransitionError
    - All transitions emit events to ledger
    """
    task_id: UUID
    earl_id: str
    cluster_id: str | None  # None until routed
    current_status: TaskStatus
    created_at: datetime
    state_entered_at: datetime
    ttl: timedelta = timedelta(hours=72)  # Default 72h
    inactivity_timeout: timedelta = timedelta(hours=48)
    reporting_timeout: timedelta = timedelta(days=7)

    def transition(
        self,
        new_status: TaskStatus,
        transition_time: datetime,
        actor_id: str,
        reason: str = "",
    ) -> "TaskState":
        """Transition to new state if valid.

        Returns:
            New TaskState with updated status

        Raises:
            IllegalStateTransitionError: If transition is not allowed
        """
        if not TaskTransitionRules.is_valid_transition(
            self.current_status, new_status
        ):
            raise IllegalStateTransitionError(
                current_state=self.current_status,
                attempted_state=new_status,
                allowed_states=TaskTransitionRules.get_allowed_transitions(
                    self.current_status
                ),
            )

        return TaskState(
            task_id=self.task_id,
            earl_id=self.earl_id,
            cluster_id=self.cluster_id,
            current_status=new_status,
            created_at=self.created_at,
            state_entered_at=transition_time,
            ttl=self.ttl,
            inactivity_timeout=self.inactivity_timeout,
            reporting_timeout=self.reporting_timeout,
        )

    @property
    def is_pre_consent(self) -> bool:
        """Check if task is in pre-consent state."""
        return self.current_status in {
            TaskStatus.AUTHORIZED,
            TaskStatus.ACTIVATED,
            TaskStatus.ROUTED,
        }

    @property
    def is_terminal(self) -> bool:
        """Check if task is in terminal state."""
        return self.current_status in {
            TaskStatus.COMPLETED,
            TaskStatus.DECLINED,
            TaskStatus.QUARANTINED,
            TaskStatus.NULLIFIED,
        }
```

### IllegalStateTransitionError

```python
from src.domain.errors.constitutional import ConstitutionalViolationError

class IllegalStateTransitionError(ConstitutionalViolationError):
    """Raised when an illegal state transition is attempted.

    This is a constitutional violation - the state machine
    must not allow invalid transitions.
    """

    def __init__(
        self,
        current_state: TaskStatus,
        attempted_state: TaskStatus,
        allowed_states: frozenset[TaskStatus],
    ) -> None:
        self.current_state = current_state
        self.attempted_state = attempted_state
        self.allowed_states = allowed_states
        super().__init__(
            f"Task cannot transition from {current_state.value} to "
            f"{attempted_state.value}. Allowed transitions: "
            f"{[s.value for s in allowed_states]}"
        )
```

### Task Event Types

```python
# Event type registry for task domain
TASK_EVENT_TYPES = {
    TaskStatus.AUTHORIZED: "executive.task.authorized",
    TaskStatus.ACTIVATED: "executive.task.activated",
    TaskStatus.ROUTED: "executive.task.routed",
    TaskStatus.ACCEPTED: "executive.task.accepted",
    TaskStatus.IN_PROGRESS: "executive.task.started",  # or in_progress
    TaskStatus.REPORTED: "executive.task.reported",
    TaskStatus.AGGREGATED: "executive.task.aggregated",
    TaskStatus.COMPLETED: "executive.task.completed",
    TaskStatus.DECLINED: "executive.task.declined",
    TaskStatus.QUARANTINED: "executive.task.quarantined",
    TaskStatus.NULLIFIED: "executive.task.nullified",
}
```

### Performance Requirements

**NFR-PERF-05:** State machine resolution ≤10ms

**Optimization Strategies:**
1. Pre-computed transition lookup (O(1))
2. Frozen dataclass (no property computation)
3. Minimal allocations in transition path

**Performance Test:**
```python
import time

def test_state_machine_performance():
    """State machine resolves in ≤10ms."""
    task = create_test_task(status=TaskStatus.ROUTED)

    start = time.perf_counter()
    for _ in range(1000):
        try:
            task.transition(TaskStatus.ACCEPTED, datetime.now(), "actor")
        except IllegalStateTransitionError:
            pass
    elapsed = (time.perf_counter() - start) / 1000

    assert elapsed <= 0.010, f"Transition took {elapsed*1000:.2f}ms"
```

### Existing Patterns to Follow

**Reference:** `src/domain/governance/events/event_envelope.py` (from Epic 1)

The governance event infrastructure provides the foundation for emitting task transition events.

**Reference:** `src/domain/errors/constitutional.py`

Existing `ConstitutionalViolationError` pattern for validation failures.

### Dependency on Epic 1

This story depends on:
- `consent-gov-1-1-event-envelope-domain-model`: `GovernanceEvent`, `EventMetadata`
- `consent-gov-1-2-append-only-ledger-port-adapter`: For persisting transition events

**Import:**
```python
from src.domain.governance.events.event_envelope import GovernanceEvent, EventMetadata
from src.domain.errors.constitutional import ConstitutionalViolationError
```

### Source Tree Components

**New Files:**
```
src/domain/governance/task/
├── __init__.py
├── task_state.py              # TaskState, TaskStatus
├── task_state_rules.py        # TaskTransitionRules, VALID_TRANSITIONS
└── task_events.py             # TASK_EVENT_TYPES, create_transition_event()
```

**Test Files:**
```
tests/unit/domain/governance/task/
├── __init__.py
├── test_task_state.py
├── test_task_state_rules.py
└── test_task_events.py
```

### Technical Requirements

**Python Patterns (CRITICAL):**
- ALL dataclasses must use `frozen=True` for immutability
- Enum for states (type safety)
- `frozenset` for transition rules (immutable)
- Type hints on ALL functions (mypy --strict must pass)

**State Machine Requirements:**
- O(1) transition validation
- No mutable state
- Clear error messages with allowed transitions

### Testing Standards

**Unit Test Patterns:**
```python
import pytest
from uuid import uuid4
from datetime import datetime, timezone, timedelta

class TestTaskState:
    def test_valid_transition_authorized_to_activated(self):
        """Authorized task can transition to activated."""
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
        assert new_task.task_id == task.task_id  # Same task

    def test_invalid_transition_raises_error(self):
        """Authorized task cannot jump to completed."""
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
                TaskStatus.COMPLETED,
                datetime.now(timezone.utc),
                "system",
            )

        assert exc.value.current_state == TaskStatus.AUTHORIZED
        assert exc.value.attempted_state == TaskStatus.COMPLETED
        assert TaskStatus.ACTIVATED in exc.value.allowed_states

    def test_transition_returns_new_instance(self):
        """Transition returns new TaskState, original unchanged."""
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
        assert task.current_status == TaskStatus.AUTHORIZED  # Unchanged
        assert new_task.current_status == TaskStatus.ACTIVATED

    def test_terminal_states_have_no_transitions(self):
        """Terminal states cannot transition to anything."""
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
```

**Coverage Requirement:** 100% for task state machine domain logic

### Library/Framework Requirements

| Library | Version | Purpose |
|---------|---------|---------|
| Python | 3.11+ | Dataclasses, Enum, type hints |
| pytest | latest | Unit testing |

No external dependencies - pure domain model.

### Project Structure Notes

**Alignment:** Creates `src/domain/governance/task/` per architecture (Step 6).

**Import Rules (Hexagonal):**
- Domain layer imports NOTHING from other layers
- Domain errors imported from `src/domain/errors/`
- No infrastructure imports allowed

### References

- [Source: _bmad-output/planning-artifacts/governance-architecture.md#Golden Rules → Architectural Enforcement]
- [Source: _bmad-output/planning-artifacts/governance-architecture.md#Task State Projection]
- [Source: _bmad-output/planning-artifacts/government-epics.md#GOV-2-1]
- [Source: _bmad-output/project-context.md#Critical Implementation Rules]
- [Source: consent-gov-1-1-event-envelope-domain-model.md] - Event infrastructure

### FR/NFR Traceability

| Requirement | Description | Implementation |
|-------------|-------------|----------------|
| FR13 | Enforce task state machine transitions | IllegalStateTransitionError |
| NFR-PERF-05 | State machine resolution ≤10ms | O(1) transition lookup |
| NFR-CONSENT-01 | TTL expiration = declined | Transition rules include TTL→declined |
| Golden Rule | No silent assignment | Explicit accept/decline transitions |

### Story Dependencies

| Story | Dependency Type | What We Need |
|-------|-----------------|--------------|
| consent-gov-1-1 | Hard dependency | Event infrastructure for transition events |
| consent-gov-1-2 | Soft dependency | Ledger for event persistence |

---

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List

