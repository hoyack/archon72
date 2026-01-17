# Story consent-gov-4.3: Task State Transitions on Halt

Status: done

---

## Story

As a **governance system**,
I want **tasks to transition deterministically on halt**,
So that **all work is in a known state after halt with no ambiguity**.

---

## Acceptance Criteria

1. **AC1:** Pre-consent tasks transition to `nullified` (FR24)
2. **AC2:** Post-consent tasks transition to `quarantined` (FR25)
3. **AC3:** Completed tasks remain unchanged (FR26)
4. **AC4:** State transitions are atomic (FR27, NFR-ATOMIC-01)
5. **AC5:** In-flight tasks resolve deterministically (NFR-REL-03)
6. **AC6:** All transitions emit events with halt correlation
7. **AC7:** No partial transitions (all or nothing per task)
8. **AC8:** Transition audit trail preserved
9. **AC9:** Unit tests for each task state category

---

## Tasks / Subtasks

- [x] **Task 1: Define consent boundary** (AC: 1, 2)
  - [x] Pre-consent states: AUTHORIZED, ACTIVATED, ROUTED
  - [x] Post-consent states: ACCEPTED, IN_PROGRESS, REPORTED, AGGREGATED
  - [x] Terminal states: COMPLETED, DECLINED, QUARANTINED, NULLIFIED
  - [x] Document state categorization (TaskStateCategory enum)

- [x] **Task 2: Create HaltTaskTransitionPort interface** (AC: 4, 6)
  - [x] Create `src/application/ports/governance/halt_task_transition_port.py`
  - [x] Define `transition_all_tasks_on_halt()` method
  - [x] Include halt correlation ID
  - [x] Return transition results (HaltTransitionResult)

- [x] **Task 3: Implement HaltTaskTransitionService** (AC: 1, 2, 3, 4, 5)
  - [x] Create `src/application/services/governance/halt_task_transition_service.py`
  - [x] Categorize all active tasks by consent state
  - [x] Apply appropriate transitions
  - [x] Handle in-flight tasks deterministically

- [x] **Task 4: Implement pre-consent nullification** (AC: 1)
  - [x] Query tasks in AUTHORIZED, ACTIVATED, ROUTED states
  - [x] Transition to NULLIFIED
  - [x] Emit `executive.task.nullified_on_halt` event
  - [x] No penalty to Cluster (they never consented)

- [x] **Task 5: Implement post-consent quarantine** (AC: 2)
  - [x] Query tasks in ACCEPTED, IN_PROGRESS, REPORTED, AGGREGATED states
  - [x] Transition to QUARANTINED
  - [x] Emit `executive.task.quarantined_on_halt` event
  - [x] Preserve work state for review

- [x] **Task 6: Preserve completed tasks** (AC: 3)
  - [x] Tasks in COMPLETED state remain COMPLETED
  - [x] No transition needed
  - [x] Emit `executive.task.preserved_on_halt` event for audit

- [x] **Task 7: Implement atomic transitions** (AC: 4, 7)
  - [x] Each task transitions atomically
  - [x] No partial state changes
  - [x] Use optimistic locking via ConcurrentModificationError
  - [x] Graceful failure handling

- [x] **Task 8: Handle in-flight tasks** (AC: 5)
  - [x] Tasks mid-transition receive halt signal
  - [x] Resolve to deterministic end state
  - [x] Document resolution rules
  - [x] No undefined states

- [x] **Task 9: Implement event correlation** (AC: 6, 8)
  - [x] All halt transition events include halt_correlation_id
  - [x] Links task events to halt event
  - [x] Enables audit trail reconstruction
  - [x] Summary event emitted after all transitions

- [x] **Task 10: Write comprehensive unit tests** (AC: 9)
  - [x] Test pre-consent tasks → nullified (4 tests)
  - [x] Test post-consent tasks → quarantined (5 tests)
  - [x] Test completed tasks unchanged (5 tests)
  - [x] Test atomic transitions (2 tests)
  - [x] Test in-flight task resolution (1 test)
  - [x] Test event correlation (2 tests)
  - [x] 36 tests total, all passing

---

## Documentation Checklist

- [x] Architecture docs updated (halt task transitions)
- [x] State categorization documented (TaskStateCategory enum in port)
- [x] Inline comments explaining consent boundary
- [x] N/A - README (internal component)

---

## Dev Notes

### Key Architectural Decisions

**Consent Boundary:**
```
The consent boundary determines how tasks are handled on halt:

PRE-CONSENT (Cluster never agreed):
  - AUTHORIZED: Task created but not activated
  - ACTIVATED: Earl sent activation request
  - ROUTED: Request delivered to Cluster
  → NULLIFIED (voided, never happened)

POST-CONSENT (Cluster agreed to work):
  - ACCEPTED: Cluster accepted task
  - IN_PROGRESS: Work started
  - REPORTED: Result submitted
  - AGGREGATED: Results being collected
  → QUARANTINED (preserved for review)

TERMINAL (already done):
  - COMPLETED: Work finished and accepted
  - DECLINED: Cluster declined
  - QUARANTINED: Already quarantined
  - NULLIFIED: Already nullified
  → UNCHANGED (preserve final state)
```

**Why Different Treatment?**
```
Pre-consent tasks:
  - Cluster never agreed to do them
  - No obligation exists
  - Safe to void completely

Post-consent tasks:
  - Cluster invested effort
  - Work may have value
  - Must preserve for review after halt resolves
```

### State Transition Diagram on Halt

```
AUTHORIZED ─────┐
ACTIVATED ──────┼──→ NULLIFIED
ROUTED ─────────┘

ACCEPTED ───────┐
IN_PROGRESS ────┼──→ QUARANTINED
REPORTED ───────┤
AGGREGATED ─────┘

COMPLETED ──────────→ COMPLETED (unchanged)
DECLINED ───────────→ DECLINED (unchanged)
QUARANTINED ────────→ QUARANTINED (unchanged)
NULLIFIED ──────────→ NULLIFIED (unchanged)
```

### Event Patterns

```python
# Pre-consent task nullified
{
    "event_type": "executive.task.nullified_on_halt",
    "actor": "system",
    "payload": {
        "task_id": "uuid",
        "previous_state": "routed",
        "new_state": "nullified",
        "halt_correlation_id": "uuid",
        "reason": "system_halt_pre_consent",
        "transitioned_at": "timestamp"
    }
}

# Post-consent task quarantined
{
    "event_type": "executive.task.quarantined_on_halt",
    "actor": "system",
    "payload": {
        "task_id": "uuid",
        "previous_state": "in_progress",
        "new_state": "quarantined",
        "halt_correlation_id": "uuid",
        "reason": "system_halt_post_consent",
        "work_preserved": true,
        "transitioned_at": "timestamp"
    }
}

# Completed task preserved (audit record)
{
    "event_type": "executive.task.preserved_on_halt",
    "actor": "system",
    "payload": {
        "task_id": "uuid",
        "state": "completed",
        "halt_correlation_id": "uuid",
        "reason": "terminal_state_unchanged",
        "recorded_at": "timestamp"
    }
}
```

### Service Implementation Sketch

```python
class TaskStateCategory(Enum):
    """Categories for halt handling."""
    PRE_CONSENT = "pre_consent"
    POST_CONSENT = "post_consent"
    TERMINAL = "terminal"


# State to category mapping
STATE_CATEGORIES: dict[TaskStatus, TaskStateCategory] = {
    # Pre-consent (Cluster never agreed)
    TaskStatus.AUTHORIZED: TaskStateCategory.PRE_CONSENT,
    TaskStatus.ACTIVATED: TaskStateCategory.PRE_CONSENT,
    TaskStatus.ROUTED: TaskStateCategory.PRE_CONSENT,

    # Post-consent (Cluster agreed)
    TaskStatus.ACCEPTED: TaskStateCategory.POST_CONSENT,
    TaskStatus.IN_PROGRESS: TaskStateCategory.POST_CONSENT,
    TaskStatus.REPORTED: TaskStateCategory.POST_CONSENT,
    TaskStatus.AGGREGATED: TaskStateCategory.POST_CONSENT,

    # Terminal (already done)
    TaskStatus.COMPLETED: TaskStateCategory.TERMINAL,
    TaskStatus.DECLINED: TaskStateCategory.TERMINAL,
    TaskStatus.QUARANTINED: TaskStateCategory.TERMINAL,
    TaskStatus.NULLIFIED: TaskStateCategory.TERMINAL,
}


@dataclass(frozen=True)
class HaltTransitionResult:
    """Result of halt task transitions."""
    halt_correlation_id: UUID
    nullified_count: int
    quarantined_count: int
    preserved_count: int
    failed_count: int
    failed_task_ids: list[UUID]


class HaltTaskTransitionService:
    """Handles task state transitions when system halts."""

    def __init__(
        self,
        task_state_port: TaskStatePort,
        event_emitter: EventEmitter,
        time_authority: TimeAuthority,
    ):
        self._task_state = task_state_port
        self._event_emitter = event_emitter
        self._time = time_authority

    async def transition_all_tasks_on_halt(
        self,
        halt_correlation_id: UUID,
    ) -> HaltTransitionResult:
        """Transition all active tasks to halt states."""
        nullified = 0
        quarantined = 0
        preserved = 0
        failed = []

        # Get all non-terminal tasks
        active_tasks = await self._task_state.get_active_tasks()

        for task in active_tasks:
            category = STATE_CATEGORIES.get(task.status)

            try:
                if category == TaskStateCategory.PRE_CONSENT:
                    await self._nullify_task(task, halt_correlation_id)
                    nullified += 1

                elif category == TaskStateCategory.POST_CONSENT:
                    await self._quarantine_task(task, halt_correlation_id)
                    quarantined += 1

                elif category == TaskStateCategory.TERMINAL:
                    await self._preserve_task(task, halt_correlation_id)
                    preserved += 1

            except Exception as e:
                logger.error(f"Failed to transition task {task.id}: {e}")
                failed.append(task.id)

        return HaltTransitionResult(
            halt_correlation_id=halt_correlation_id,
            nullified_count=nullified,
            quarantined_count=quarantined,
            preserved_count=preserved,
            failed_count=len(failed),
            failed_task_ids=failed,
        )

    async def _nullify_task(
        self,
        task: Task,
        halt_correlation_id: UUID,
    ) -> None:
        """Nullify pre-consent task."""
        now = self._time.now()

        # Atomic transition
        await self._task_state.atomic_transition(
            task_id=task.id,
            from_status=task.status,
            to_status=TaskStatus.NULLIFIED,
        )

        # Emit event
        await self._event_emitter.emit(
            event_type="executive.task.nullified_on_halt",
            actor="system",
            payload={
                "task_id": str(task.id),
                "previous_state": task.status.value,
                "new_state": "nullified",
                "halt_correlation_id": str(halt_correlation_id),
                "reason": "system_halt_pre_consent",
                "transitioned_at": now.isoformat(),
            },
        )

    async def _quarantine_task(
        self,
        task: Task,
        halt_correlation_id: UUID,
    ) -> None:
        """Quarantine post-consent task."""
        now = self._time.now()

        # Atomic transition
        await self._task_state.atomic_transition(
            task_id=task.id,
            from_status=task.status,
            to_status=TaskStatus.QUARANTINED,
        )

        # Emit event
        await self._event_emitter.emit(
            event_type="executive.task.quarantined_on_halt",
            actor="system",
            payload={
                "task_id": str(task.id),
                "previous_state": task.status.value,
                "new_state": "quarantined",
                "halt_correlation_id": str(halt_correlation_id),
                "reason": "system_halt_post_consent",
                "work_preserved": True,
                "transitioned_at": now.isoformat(),
            },
        )

    async def _preserve_task(
        self,
        task: Task,
        halt_correlation_id: UUID,
    ) -> None:
        """Record preservation of terminal task (no state change)."""
        now = self._time.now()

        # No transition needed, just record for audit
        await self._event_emitter.emit(
            event_type="executive.task.preserved_on_halt",
            actor="system",
            payload={
                "task_id": str(task.id),
                "state": task.status.value,
                "halt_correlation_id": str(halt_correlation_id),
                "reason": "terminal_state_unchanged",
                "recorded_at": now.isoformat(),
            },
        )
```

### Atomic Transition Implementation

```python
class TaskStatePort(Protocol):
    """Port for task state operations."""

    async def atomic_transition(
        self,
        task_id: UUID,
        from_status: TaskStatus,
        to_status: TaskStatus,
    ) -> None:
        """Atomically transition task state.

        Uses optimistic locking:
        - Check current state matches from_status
        - Update to to_status
        - If state changed mid-transition, raise ConcurrentModificationError

        This ensures no partial transitions.
        """
        ...


# Database-level implementation
async def atomic_transition(
    self,
    task_id: UUID,
    from_status: TaskStatus,
    to_status: TaskStatus,
) -> None:
    """Atomic transition with optimistic locking."""
    result = await self._db.execute(
        """
        UPDATE tasks
        SET status = :to_status, updated_at = :now
        WHERE id = :task_id AND status = :from_status
        RETURNING id
        """,
        {
            "task_id": task_id,
            "from_status": from_status.value,
            "to_status": to_status.value,
            "now": self._time.now(),
        },
    )

    if result.rowcount == 0:
        # State changed between read and write
        current = await self.get_task(task_id)
        raise ConcurrentModificationError(
            f"Task {task_id} state changed: expected {from_status}, got {current.status}"
        )
```

### In-Flight Task Resolution

```python
# In-flight task resolution rules:

# Scenario: Task is mid-transition when halt occurs
# Example: Task transitioning from ROUTED → ACCEPTED

# Rule: Resolve to the state that was committed to ledger
# If event for new state was emitted: use new state
# If event not yet emitted: use previous state

# Implementation: HaltTaskTransitionService reads from ledger,
# so it always sees the committed state.

# Determinism guarantee:
# - Ledger is source of truth
# - Halt reads current committed state
# - Applies appropriate transition based on that state
# - No race condition because ledger operations are atomic
```

### Test Patterns

```python
class TestHaltTaskTransitionService:
    """Unit tests for halt task transitions."""

    async def test_pre_consent_tasks_nullified(
        self,
        transition_service: HaltTaskTransitionService,
        routed_task: Task,
    ):
        """Pre-consent tasks (ROUTED) become NULLIFIED."""
        result = await transition_service.transition_all_tasks_on_halt(
            halt_correlation_id=uuid4(),
        )

        assert result.nullified_count >= 1
        task = await transition_service._task_state.get_task(routed_task.id)
        assert task.status == TaskStatus.NULLIFIED

    async def test_post_consent_tasks_quarantined(
        self,
        transition_service: HaltTaskTransitionService,
        in_progress_task: Task,
    ):
        """Post-consent tasks (IN_PROGRESS) become QUARANTINED."""
        result = await transition_service.transition_all_tasks_on_halt(
            halt_correlation_id=uuid4(),
        )

        assert result.quarantined_count >= 1
        task = await transition_service._task_state.get_task(in_progress_task.id)
        assert task.status == TaskStatus.QUARANTINED

    async def test_completed_tasks_unchanged(
        self,
        transition_service: HaltTaskTransitionService,
        completed_task: Task,
    ):
        """Completed tasks remain COMPLETED."""
        result = await transition_service.transition_all_tasks_on_halt(
            halt_correlation_id=uuid4(),
        )

        assert result.preserved_count >= 1
        task = await transition_service._task_state.get_task(completed_task.id)
        assert task.status == TaskStatus.COMPLETED

    async def test_atomic_transitions(
        self,
        transition_service: HaltTaskTransitionService,
        routed_task: Task,
    ):
        """Transitions are atomic (no partial states)."""
        # Simulate concurrent modification
        async def modify_task_during_transition():
            await asyncio.sleep(0.001)  # Small delay
            await transition_service._task_state.atomic_transition(
                task_id=routed_task.id,
                from_status=TaskStatus.ROUTED,
                to_status=TaskStatus.ACCEPTED,
            )

        # This should either:
        # 1. Complete before modification → task is NULLIFIED
        # 2. Fail with ConcurrentModificationError
        # Never a partial state

    async def test_event_correlation(
        self,
        transition_service: HaltTaskTransitionService,
        routed_task: Task,
        event_capture: EventCapture,
    ):
        """Events include halt correlation ID."""
        halt_id = uuid4()

        await transition_service.transition_all_tasks_on_halt(
            halt_correlation_id=halt_id,
        )

        events = event_capture.get_all()
        halt_events = [e for e in events if "on_halt" in e.event_type]

        for event in halt_events:
            assert event.payload["halt_correlation_id"] == str(halt_id)

    async def test_all_states_categorized(self):
        """All TaskStatus values are categorized."""
        for status in TaskStatus:
            assert status in STATE_CATEGORIES, f"{status} not categorized"
```

### Dependencies

- **Depends on:** consent-gov-2-1 (TaskStatus), consent-gov-4-1 (halt circuit), consent-gov-4-2 (halt trigger)
- **Enables:** System can safely halt with all tasks in known states

### References

- FR24: System can transition all pre-consent tasks to nullified on halt
- FR25: System can transition all post-consent tasks to quarantined on halt
- FR26: System can preserve completed tasks unchanged on halt
- FR27: System can ensure state transitions are atomic (no partial transitions)
- NFR-ATOMIC-01: Atomic transitions
- NFR-REL-03: In-flight tasks resolve deterministically
