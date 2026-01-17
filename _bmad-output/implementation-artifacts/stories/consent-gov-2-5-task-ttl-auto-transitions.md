# Story consent-gov-2.5: Task TTL & Auto-Transitions

Status: ready-for-dev

---

## Story

As a **governance system**,
I want **automatic task state transitions based on timeouts**,
So that **stale tasks don't block the system and silence is never allowed**.

---

## Acceptance Criteria

1. **AC1:** Auto-decline after TTL expiration (72h default) with no failure attribution (FR8)
2. **AC2:** Auto-transition accepted → in_progress after inactivity (48h default) (FR9)
3. **AC3:** Auto-quarantine tasks exceeding reporting timeout (7d default) (FR10)
4. **AC4:** TTL expiration results in `declined` state (NFR-CONSENT-01)
5. **AC5:** All auto-transitions emit events with `system` as actor (not blamed on Cluster)
6. **AC6:** Auto-decline does NOT reduce standing or trigger penalties
7. **AC7:** Timeout durations are configurable via configuration
8. **AC8:** Timeout processor runs on schedule without blocking other operations
9. **AC9:** Golden Rule enforced: "Failure is allowed; silence is not"
10. **AC10:** Unit tests for each timeout scenario

---

## Tasks / Subtasks

- [ ] **Task 1: Create TaskTimeoutPort interface** (AC: 1, 2, 3, 8)
  - [ ] Create `src/application/ports/governance/task_timeout_port.py`
  - [ ] Define `process_expired_tasks()` method
  - [ ] Define timeout configuration interface
  - [ ] Support async batch processing

- [ ] **Task 2: Create timeout configuration** (AC: 7)
  - [ ] Define `TaskTimeoutConfig` dataclass
  - [ ] Default activation TTL: 72 hours
  - [ ] Default acceptance inactivity: 48 hours
  - [ ] Default reporting timeout: 7 days
  - [ ] Load from YAML configuration

- [ ] **Task 3: Implement TaskTimeoutService** (AC: 1, 2, 3, 4, 5, 6)
  - [ ] Create `src/application/services/governance/task_timeout_service.py`
  - [ ] Implement `process_activation_timeouts()` - routed tasks past TTL
  - [ ] Implement `process_acceptance_timeouts()` - accepted but inactive
  - [ ] Implement `process_reporting_timeouts()` - in_progress past deadline
  - [ ] All transitions use `system` as actor

- [ ] **Task 4: Implement activation TTL auto-decline** (AC: 1, 4, 6)
  - [ ] Query tasks in ROUTED state past 72h TTL
  - [ ] Transition to DECLINED state
  - [ ] Emit `executive.task.auto_declined` event
  - [ ] Reason: "ttl_expired" (not "cluster_failure")
  - [ ] NO penalty attribution whatsoever

- [ ] **Task 5: Implement acceptance inactivity auto-start** (AC: 2)
  - [ ] Query tasks in ACCEPTED state inactive for 48h
  - [ ] Transition to IN_PROGRESS state
  - [ ] Emit `executive.task.auto_started` event
  - [ ] Rationale: Cluster accepted, assumed working

- [ ] **Task 6: Implement reporting timeout auto-quarantine** (AC: 3)
  - [ ] Query tasks in IN_PROGRESS state past 7d deadline
  - [ ] Transition to QUARANTINED state
  - [ ] Emit `executive.task.auto_quarantined` event
  - [ ] Reason: "reporting_timeout"
  - [ ] NO penalty attribution (silence isn't failure, it's unknown)

- [ ] **Task 7: Implement scheduled processor** (AC: 8)
  - [ ] Create background scheduler interface
  - [ ] Run timeout checks periodically (configurable interval, e.g., every 5 min)
  - [ ] Non-blocking execution
  - [ ] Log processing statistics

- [ ] **Task 8: Enforce "silence is not allowed"** (AC: 9)
  - [ ] All timeout events are explicit, never silent
  - [ ] Hash chain captures timeout events
  - [ ] No task can expire without recorded event
  - [ ] Architectural test: verify no silent expiry path

- [ ] **Task 9: Write comprehensive unit tests** (AC: 10)
  - [ ] Test auto-decline after 72h TTL
  - [ ] Test auto-start after 48h acceptance inactivity
  - [ ] Test auto-quarantine after 7d reporting timeout
  - [ ] Test events emitted with system as actor
  - [ ] Test no penalty attribution on any timeout
  - [ ] Test configurable timeout durations
  - [ ] Test batch processing of multiple expired tasks

---

## Documentation Checklist

- [ ] Architecture docs updated (timeout workflows)
- [ ] Inline comments explaining "silence is not allowed" rule
- [ ] Configuration docs for timeout values
- [ ] N/A - README (internal component)

---

## Dev Notes

### Key Architectural Decisions

**Golden Rule: Failure is allowed; silence is not**
```
This rule means:
- Every timeout MUST emit an explicit event
- No task can silently expire without recorded state change
- Even auto-transitions are witnessed in the ledger
- The hash chain proves no silent expirations occurred
```

**Actor Attribution on Timeouts:**
```
Auto-transitions use "system" as actor:
- "cluster_id" in payload identifies which Cluster's task
- "actor" field is "system" (not the Cluster)
- No negative attribution (standing, reputation, etc.)
- Rationale: Timeout is system behavior, not Cluster failure
```

### Timeout Scenarios

```
1. Activation TTL (72h):
   ROUTED → DECLINED (ttl_expired)
   - Cluster never responded
   - No penalty (they may be unavailable, busy, etc.)

2. Acceptance Inactivity (48h):
   ACCEPTED → IN_PROGRESS (auto_started)
   - Cluster accepted but no activity
   - Assumed they're working, just not reporting
   - Not punitive, just procedural

3. Reporting Timeout (7d):
   IN_PROGRESS → QUARANTINED (reporting_timeout)
   - Task started but no result/problem report
   - Quarantine for investigation
   - Still no penalty (may be stuck, not negligent)
```

### Configuration Schema

```yaml
# config/governance/task_timeouts.yaml
task_timeouts:
  activation_ttl_hours: 72       # ROUTED → auto-decline
  acceptance_inactivity_hours: 48  # ACCEPTED → auto-start
  reporting_timeout_days: 7      # IN_PROGRESS → auto-quarantine
  processor_interval_minutes: 5  # How often to check
```

### Event Patterns

```python
# Auto-decline event
{
    "event_type": "executive.task.auto_declined",
    "actor": "system",  # NOT the Cluster
    "payload": {
        "task_id": "uuid",
        "cluster_id": "uuid",  # For reference only
        "reason": "ttl_expired",
        "ttl_hours": 72,
        "expired_at": "timestamp"
    }
}

# Auto-start event
{
    "event_type": "executive.task.auto_started",
    "actor": "system",
    "payload": {
        "task_id": "uuid",
        "cluster_id": "uuid",
        "reason": "acceptance_inactivity",
        "inactivity_hours": 48,
        "started_at": "timestamp"
    }
}

# Auto-quarantine event
{
    "event_type": "executive.task.auto_quarantined",
    "actor": "system",
    "payload": {
        "task_id": "uuid",
        "cluster_id": "uuid",
        "reason": "reporting_timeout",
        "timeout_days": 7,
        "quarantined_at": "timestamp"
    }
}
```

### Service Implementation Sketch

```python
@dataclass(frozen=True)
class TaskTimeoutConfig:
    """Timeout configuration values."""
    activation_ttl: timedelta = timedelta(hours=72)
    acceptance_inactivity: timedelta = timedelta(hours=48)
    reporting_timeout: timedelta = timedelta(days=7)
    processor_interval: timedelta = timedelta(minutes=5)


class TaskTimeoutService:
    """Handles automatic task state transitions on timeout."""

    SYSTEM_ACTOR = "system"

    def __init__(
        self,
        task_state_port: TaskStatePort,
        event_emitter: EventEmitter,
        time_authority: TimeAuthority,
        config: TaskTimeoutConfig,
    ):
        self._task_state = task_state_port
        self._event_emitter = event_emitter
        self._time = time_authority
        self._config = config

    async def process_all_timeouts(self) -> TimeoutProcessingResult:
        """Process all timeout scenarios. Called periodically."""
        results = TimeoutProcessingResult()

        # Process each timeout type
        results.declined = await self._process_activation_timeouts()
        results.started = await self._process_acceptance_timeouts()
        results.quarantined = await self._process_reporting_timeouts()

        return results

    async def _process_activation_timeouts(self) -> list[UUID]:
        """Auto-decline tasks past activation TTL."""
        cutoff = self._time.now() - self._config.activation_ttl
        expired_tasks = await self._task_state.find_tasks(
            status=TaskStatus.ROUTED,
            created_before=cutoff,
        )

        declined_ids = []
        for task in expired_tasks:
            await self._auto_decline(task)
            declined_ids.append(task.id)

        return declined_ids

    async def _auto_decline(self, task: Task) -> None:
        """Decline task due to TTL expiration."""
        await self._event_emitter.emit(
            event_type="executive.task.auto_declined",
            actor=self.SYSTEM_ACTOR,
            payload={
                "task_id": str(task.id),
                "cluster_id": str(task.target_cluster_id),
                "reason": "ttl_expired",
                "ttl_hours": int(self._config.activation_ttl.total_seconds() / 3600),
            },
        )

        await self._task_state.transition(
            task_id=task.id,
            to_status=TaskStatus.DECLINED,
        )

    async def _process_acceptance_timeouts(self) -> list[UUID]:
        """Auto-start tasks inactive after acceptance."""
        cutoff = self._time.now() - self._config.acceptance_inactivity
        inactive_tasks = await self._task_state.find_tasks(
            status=TaskStatus.ACCEPTED,
            last_activity_before=cutoff,
        )

        started_ids = []
        for task in inactive_tasks:
            await self._auto_start(task)
            started_ids.append(task.id)

        return started_ids

    async def _process_reporting_timeouts(self) -> list[UUID]:
        """Auto-quarantine tasks past reporting deadline."""
        cutoff = self._time.now() - self._config.reporting_timeout
        stale_tasks = await self._task_state.find_tasks(
            status=TaskStatus.IN_PROGRESS,
            started_before=cutoff,
        )

        quarantined_ids = []
        for task in stale_tasks:
            await self._auto_quarantine(task)
            quarantined_ids.append(task.id)

        return quarantined_ids
```

### Test Patterns

```python
class TestTaskTimeoutService:
    """Unit tests for task timeout processing."""

    async def test_auto_decline_after_72h_ttl(
        self,
        timeout_service: TaskTimeoutService,
        routed_task_72h_old: Task,
        fake_time: FakeTimeAuthority,
    ):
        """Routed task auto-declines after 72h."""
        # Advance time past TTL
        fake_time.advance(hours=73)

        result = await timeout_service.process_all_timeouts()

        assert routed_task_72h_old.id in result.declined
        task = await timeout_service._task_state.get_task(routed_task_72h_old.id)
        assert task.status == TaskStatus.DECLINED

    async def test_auto_decline_uses_system_actor(
        self,
        timeout_service: TaskTimeoutService,
        routed_task_72h_old: Task,
        event_capture: EventCapture,
    ):
        """Auto-decline events use 'system' as actor, not Cluster."""
        await timeout_service.process_all_timeouts()

        event = event_capture.get_last("executive.task.auto_declined")
        assert event.actor == "system"
        assert event.payload["cluster_id"] == str(routed_task_72h_old.target_cluster_id)
        assert event.payload["reason"] == "ttl_expired"

    async def test_no_penalty_on_timeout(
        self,
        timeout_service: TaskTimeoutService,
        routed_task_72h_old: Task,
    ):
        """Timeout does NOT trigger any penalty tracking."""
        await timeout_service.process_all_timeouts()

        # Verify no penalty-related events or data
        # (This is really an architectural test - no penalty schema exists)
        # See consent-gov-2-3 for the standing/reputation schema test

    async def test_auto_start_after_48h_inactivity(
        self,
        timeout_service: TaskTimeoutService,
        accepted_task_48h_inactive: Task,
    ):
        """Accepted but inactive task auto-starts after 48h."""
        result = await timeout_service.process_all_timeouts()

        assert accepted_task_48h_inactive.id in result.started
        task = await timeout_service._task_state.get_task(accepted_task_48h_inactive.id)
        assert task.status == TaskStatus.IN_PROGRESS

    async def test_auto_quarantine_after_7d_reporting(
        self,
        timeout_service: TaskTimeoutService,
        in_progress_task_7d_old: Task,
    ):
        """In-progress task auto-quarantines after 7d reporting timeout."""
        result = await timeout_service.process_all_timeouts()

        assert in_progress_task_7d_old.id in result.quarantined
        task = await timeout_service._task_state.get_task(in_progress_task_7d_old.id)
        assert task.status == TaskStatus.QUARANTINED

    async def test_no_silent_expiry(
        self,
        timeout_service: TaskTimeoutService,
        routed_task_72h_old: Task,
        event_capture: EventCapture,
    ):
        """Every timeout produces an explicit event - no silent expiry."""
        await timeout_service.process_all_timeouts()

        events = event_capture.get_all()
        timeout_events = [e for e in events if "auto_" in e.event_type]
        assert len(timeout_events) >= 1  # Must have explicit event
```

### Dependencies

- **Depends on:** consent-gov-2-1 (TaskStatus enum), hardening-1 (TimeAuthority injection)
- **Enables:** consent-gov-2-6 (reminders use TTL milestones)

### References

- FR8: Auto-decline after TTL expiration with no failure attribution
- FR9: Auto-transition accepted → in_progress after inactivity
- FR10: Auto-quarantine tasks exceeding reporting timeout
- NFR-CONSENT-01: TTL expiration → declined state
- Golden Rule: Failure is allowed; silence is not
