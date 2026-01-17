# Story consent-gov-7.2: Obligation Release

Status: ready-for-dev

---

## Story

As a **Cluster**,
I want **all obligations released on exit**,
So that **I leave with no lingering commitments**.

---

## Acceptance Criteria

1. **AC1:** All obligations released on exit (FR44)
2. **AC2:** Active tasks transitioned to appropriate states
3. **AC3:** Pending requests cancelled
4. **AC4:** No penalty applied for early exit
5. **AC5:** Event `custodial.obligations.released` emitted
6. **AC6:** Pre-consent tasks nullified
7. **AC7:** Post-consent tasks released with preservation
8. **AC8:** Unit tests for obligation release

---

## Tasks / Subtasks

- [ ] **Task 1: Create ObligationReleaseService** (AC: 1)
  - [ ] Create `src/application/services/governance/obligation_release_service.py`
  - [ ] Release all obligations for Cluster
  - [ ] Coordinate task state transitions
  - [ ] No penalty logic (structural absence)

- [ ] **Task 2: Implement task transition logic** (AC: 2, 6, 7)
  - [ ] Pre-consent tasks (AUTHORIZED, ACTIVATED, ROUTED) → NULLIFIED
  - [ ] Post-consent tasks (ACCEPTED, IN_PROGRESS) → RELEASED
  - [ ] REPORTED tasks → preserve work, mark RELEASED
  - [ ] COMPLETED tasks → no change

- [ ] **Task 3: Implement request cancellation** (AC: 3)
  - [ ] Cancel pending activation requests
  - [ ] Cancel pending routing requests
  - [ ] Cancel pending reminders
  - [ ] No future obligations

- [ ] **Task 4: Ensure no penalties** (AC: 4)
  - [ ] No reputation penalty tracking exists
  - [ ] No "early exit" flag exists
  - [ ] No standing reduction
  - [ ] Structurally impossible to penalize

- [ ] **Task 5: Implement release event** (AC: 5)
  - [ ] Emit `custodial.obligations.released`
  - [ ] Include count of released obligations
  - [ ] Include task state transitions
  - [ ] Knight observes release

- [ ] **Task 6: Handle pre-consent releases** (AC: 6)
  - [ ] AUTHORIZED → NULLIFIED_ON_EXIT
  - [ ] ACTIVATED → NULLIFIED_ON_EXIT
  - [ ] ROUTED → NULLIFIED_ON_EXIT
  - [ ] Cluster never consented, clean void

- [ ] **Task 7: Handle post-consent releases** (AC: 7)
  - [ ] ACCEPTED → RELEASED_ON_EXIT (work preserved)
  - [ ] IN_PROGRESS → RELEASED_ON_EXIT (work preserved)
  - [ ] REPORTED → RELEASED_ON_EXIT (results preserved)
  - [ ] Cluster's work remains attributed

- [ ] **Task 8: Write comprehensive unit tests** (AC: 8)
  - [ ] Test all pre-consent tasks nullified
  - [ ] Test all post-consent tasks released
  - [ ] Test pending requests cancelled
  - [ ] Test no penalties exist
  - [ ] Test release event emitted

---

## Documentation Checklist

- [ ] Architecture docs updated (release workflow)
- [ ] Task state transitions on exit documented
- [ ] Inline comments explaining no-penalty principle
- [ ] N/A - README (internal component)

---

## Dev Notes

### Key Architectural Decisions

**No Penalty Principle:**
```
Golden Rule: Refusal is penalty-free

On exit, Cluster faces:
  ✗ No reputation reduction
  ✗ No standing decrease
  ✗ No "early exit" mark
  ✗ No future restrictions

Structural enforcement:
  - No reputation field exists
  - No penalty tracking table
  - No standing calculation
  - Cannot add what doesn't exist

If penalty is needed later:
  - Requires constitutional amendment
  - Would be a violation of Golden Rule
  - Knight would observe attempt
```

**Release vs Nullify:**
```
Pre-consent (never agreed):
  → NULLIFIED_ON_EXIT
  - Task voided completely
  - As if it never happened
  - No work to preserve

Post-consent (agreed, worked):
  → RELEASED_ON_EXIT
  - Obligation released
  - Work preserved for attribution
  - Results available if useful

Distinction matters:
  - Preserves dignity (work acknowledged)
  - Enables audit (what was done)
  - Respects contribution (even incomplete)
```

### Domain Models

```python
class ReleaseType(Enum):
    """Type of obligation release."""
    NULLIFIED_ON_EXIT = "nullified_on_exit"  # Pre-consent
    RELEASED_ON_EXIT = "released_on_exit"    # Post-consent


@dataclass(frozen=True)
class ObligationRelease:
    """Record of obligation release."""
    release_id: UUID
    cluster_id: UUID
    task_id: UUID
    previous_state: TaskStatus
    release_type: ReleaseType
    released_at: datetime
    work_preserved: bool


@dataclass(frozen=True)
class ReleaseResult:
    """Result of releasing all obligations."""
    cluster_id: UUID
    nullified_count: int
    released_count: int
    pending_cancelled: int
    total_obligations: int

    # Structurally impossible fields (do not add):
    # - penalty_applied: bool
    # - reputation_impact: int
    # - standing_reduction: float


# Task state categorization for release
RELEASE_CATEGORIES: dict[TaskStatus, ReleaseType] = {
    # Pre-consent (nullify)
    TaskStatus.AUTHORIZED: ReleaseType.NULLIFIED_ON_EXIT,
    TaskStatus.ACTIVATED: ReleaseType.NULLIFIED_ON_EXIT,
    TaskStatus.ROUTED: ReleaseType.NULLIFIED_ON_EXIT,

    # Post-consent (release with preservation)
    TaskStatus.ACCEPTED: ReleaseType.RELEASED_ON_EXIT,
    TaskStatus.IN_PROGRESS: ReleaseType.RELEASED_ON_EXIT,
    TaskStatus.REPORTED: ReleaseType.RELEASED_ON_EXIT,
    TaskStatus.AGGREGATED: ReleaseType.RELEASED_ON_EXIT,
}
```

### Service Implementation Sketch

```python
class ObligationReleaseService:
    """Handles obligation release on exit.

    No penalty logic exists here or anywhere.
    """

    def __init__(
        self,
        task_state_port: TaskStatePort,
        event_emitter: EventEmitter,
        time_authority: TimeAuthority,
    ):
        self._tasks = task_state_port
        self._event_emitter = event_emitter
        self._time = time_authority

    async def release_all(
        self,
        cluster_id: UUID,
    ) -> int:
        """Release all obligations for Cluster.

        Returns count of obligations released.
        """
        now = self._time.now()
        releases = []

        # Get all tasks for Cluster
        tasks = await self._tasks.get_tasks_for_cluster(cluster_id)

        nullified = 0
        released = 0

        for task in tasks:
            # Skip terminal states
            if task.status in [TaskStatus.COMPLETED, TaskStatus.DECLINED,
                               TaskStatus.NULLIFIED, TaskStatus.QUARANTINED]:
                continue

            release_type = RELEASE_CATEGORIES.get(task.status)
            if not release_type:
                continue

            if release_type == ReleaseType.NULLIFIED_ON_EXIT:
                await self._nullify_task(task, cluster_id, now)
                nullified += 1
            else:
                await self._release_task(task, cluster_id, now)
                released += 1

            releases.append(ObligationRelease(
                release_id=uuid4(),
                cluster_id=cluster_id,
                task_id=task.id,
                previous_state=task.status,
                release_type=release_type,
                released_at=now,
                work_preserved=(release_type == ReleaseType.RELEASED_ON_EXIT),
            ))

        # Cancel pending requests
        pending_cancelled = await self._cancel_pending_requests(cluster_id)

        # Emit release event
        await self._event_emitter.emit(
            event_type="custodial.obligations.released",
            actor="system",
            payload={
                "cluster_id": str(cluster_id),
                "nullified_count": nullified,
                "released_count": released,
                "pending_cancelled": pending_cancelled,
                "total_obligations": len(releases),
                "released_at": now.isoformat(),
            },
        )

        return len(releases)

    async def _nullify_task(
        self,
        task: Task,
        cluster_id: UUID,
        now: datetime,
    ) -> None:
        """Nullify pre-consent task."""
        await self._tasks.transition(
            task_id=task.id,
            to_status=TaskStatus.NULLIFIED,
            reason="cluster_exit",
        )

        await self._event_emitter.emit(
            event_type="executive.task.nullified_on_exit",
            actor="system",
            payload={
                "task_id": str(task.id),
                "cluster_id": str(cluster_id),
                "previous_state": task.status.value,
                "reason": "cluster_exit_pre_consent",
            },
        )

    async def _release_task(
        self,
        task: Task,
        cluster_id: UUID,
        now: datetime,
    ) -> None:
        """Release post-consent task with work preservation."""
        # Custom state for exit release (preserves work)
        await self._tasks.transition(
            task_id=task.id,
            to_status=TaskStatus.RELEASED,  # New terminal state
            reason="cluster_exit",
            preserve_work=True,
        )

        await self._event_emitter.emit(
            event_type="executive.task.released_on_exit",
            actor="system",
            payload={
                "task_id": str(task.id),
                "cluster_id": str(cluster_id),
                "previous_state": task.status.value,
                "work_preserved": True,
                "reason": "cluster_exit_post_consent",
            },
        )

    async def _cancel_pending_requests(
        self,
        cluster_id: UUID,
    ) -> int:
        """Cancel all pending requests for Cluster."""
        # Implementation would cancel:
        # - Pending activation requests
        # - Pending reminders
        # - Scheduled tasks
        return 0  # Placeholder

    # These methods intentionally do not exist:
    # async def apply_penalty(self, ...): ...
    # async def reduce_standing(self, ...): ...
    # async def mark_early_exit(self, ...): ...
```

### Event Patterns

```python
# Obligations released
{
    "event_type": "custodial.obligations.released",
    "actor": "system",
    "payload": {
        "cluster_id": "uuid",
        "nullified_count": 1,
        "released_count": 2,
        "pending_cancelled": 0,
        "total_obligations": 3,
        "released_at": "2026-01-16T00:00:00Z"
    }
}

# Task nullified on exit (pre-consent)
{
    "event_type": "executive.task.nullified_on_exit",
    "actor": "system",
    "payload": {
        "task_id": "uuid",
        "cluster_id": "uuid",
        "previous_state": "routed",
        "reason": "cluster_exit_pre_consent"
    }
}

# Task released on exit (post-consent)
{
    "event_type": "executive.task.released_on_exit",
    "actor": "system",
    "payload": {
        "task_id": "uuid",
        "cluster_id": "uuid",
        "previous_state": "in_progress",
        "work_preserved": true,
        "reason": "cluster_exit_post_consent"
    }
}
```

### Test Patterns

```python
class TestObligationReleaseService:
    """Unit tests for obligation release."""

    async def test_pre_consent_tasks_nullified(
        self,
        release_service: ObligationReleaseService,
        cluster_with_routed_task: Cluster,
        task_state_port: FakeTaskStatePort,
    ):
        """Pre-consent tasks are nullified."""
        await release_service.release_all(cluster_with_routed_task.id)

        tasks = await task_state_port.get_tasks_for_cluster(
            cluster_with_routed_task.id
        )
        routed_task = next(t for t in tasks if t.previous_status == TaskStatus.ROUTED)
        assert routed_task.status == TaskStatus.NULLIFIED

    async def test_post_consent_tasks_released(
        self,
        release_service: ObligationReleaseService,
        cluster_with_in_progress_task: Cluster,
        task_state_port: FakeTaskStatePort,
    ):
        """Post-consent tasks are released with work preserved."""
        await release_service.release_all(cluster_with_in_progress_task.id)

        tasks = await task_state_port.get_tasks_for_cluster(
            cluster_with_in_progress_task.id
        )
        in_progress_task = next(
            t for t in tasks
            if t.previous_status == TaskStatus.IN_PROGRESS
        )
        assert in_progress_task.status == TaskStatus.RELEASED

    async def test_release_event_emitted(
        self,
        release_service: ObligationReleaseService,
        cluster: Cluster,
        event_capture: EventCapture,
    ):
        """Release event is emitted."""
        await release_service.release_all(cluster.id)

        event = event_capture.get_last("custodial.obligations.released")
        assert event is not None


class TestNoPenalties:
    """Tests ensuring no penalty mechanisms exist."""

    def test_no_penalty_method(self, release_service: ObligationReleaseService):
        """No penalty method exists."""
        assert not hasattr(release_service, "apply_penalty")
        assert not hasattr(release_service, "penalize")

    def test_no_standing_reduction(self, release_service: ObligationReleaseService):
        """No standing reduction method exists."""
        assert not hasattr(release_service, "reduce_standing")
        assert not hasattr(release_service, "decrease_reputation")

    def test_no_early_exit_mark(self, release_service: ObligationReleaseService):
        """No early exit marking method exists."""
        assert not hasattr(release_service, "mark_early_exit")
        assert not hasattr(release_service, "record_abandonment")

    def test_release_result_has_no_penalty_field(self):
        """ReleaseResult has no penalty-related fields."""
        fields = ReleaseResult.__dataclass_fields__
        assert "penalty_applied" not in fields
        assert "reputation_impact" not in fields
        assert "standing_reduction" not in fields
```

### Dependencies

- **Depends on:** consent-gov-7-1 (exit processing), consent-gov-2-1 (task state machine)
- **Enables:** consent-gov-7-3 (contribution preservation)

### References

- FR44: System can release Cluster from all obligations on exit
- Golden Rule: Refusal is penalty-free
