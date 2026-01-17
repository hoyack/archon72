# Story consent-gov-7.1: Exit Request Processing

Status: ready-for-dev

---

## Story

As a **Cluster**,
I want **to initiate and complete an exit request**,
So that **I can leave the system cleanly**.

---

## Acceptance Criteria

1. **AC1:** Cluster can initiate exit request (FR42)
2. **AC2:** System processes exit request (FR43)
3. **AC3:** Exit completes in ≤2 message round-trips (NFR-EXIT-01)
4. **AC4:** Exit path available from any task state (NFR-EXIT-03)
5. **AC5:** Event `custodial.exit.initiated` emitted at start
6. **AC6:** Event `custodial.exit.completed` emitted on completion
7. **AC7:** No barriers to exit (no "are you sure?" patterns)
8. **AC8:** Exit works regardless of current task status
9. **AC9:** Unit tests for exit from each task state

---

## Tasks / Subtasks

- [ ] **Task 1: Create ExitRequest domain model** (AC: 1)
  - [ ] Create `src/domain/governance/exit/exit_request.py`
  - [ ] Include cluster_id, requested_at
  - [ ] Include current_task_states at time of request
  - [ ] Immutable value object

- [ ] **Task 2: Create ExitService** (AC: 2, 3, 4)
  - [ ] Create `src/application/services/governance/exit_service.py`
  - [ ] Process exit request
  - [ ] Coordinate with other services (obligation release, etc.)
  - [ ] Complete in ≤2 round-trips

- [ ] **Task 3: Create ExitPort interface** (AC: 2)
  - [ ] Create `src/application/ports/governance/exit_port.py`
  - [ ] Define `initiate_exit()` method
  - [ ] Define `complete_exit()` method
  - [ ] Define `get_exit_status()` method

- [ ] **Task 4: Implement exit initiation** (AC: 1, 5)
  - [ ] Accept exit request from Cluster
  - [ ] Emit `custodial.exit.initiated` event
  - [ ] No confirmation dialog (direct initiation)
  - [ ] No reason required (unconditional right)

- [ ] **Task 5: Implement exit processing** (AC: 2, 3)
  - [ ] Step 1: Cluster sends exit request
  - [ ] Step 2: System confirms exit complete
  - [ ] Total: 2 round-trips maximum
  - [ ] No intermediate states requiring response

- [ ] **Task 6: Implement universal exit path** (AC: 4, 8)
  - [ ] Exit from AUTHORIZED state
  - [ ] Exit from ACTIVATED state
  - [ ] Exit from ACCEPTED state
  - [ ] Exit from IN_PROGRESS state
  - [ ] Exit from any other state

- [ ] **Task 7: Implement completion event** (AC: 6)
  - [ ] Emit `custodial.exit.completed` on finish
  - [ ] Include exit duration
  - [ ] Include tasks affected
  - [ ] Knight observes completion

- [ ] **Task 8: Ensure no barriers** (AC: 7)
  - [ ] No confirmation prompts
  - [ ] No waiting periods
  - [ ] No penalty warnings
  - [ ] Immediate processing

- [ ] **Task 9: Write comprehensive unit tests** (AC: 9)
  - [ ] Test exit from AUTHORIZED
  - [ ] Test exit from ACTIVATED
  - [ ] Test exit from ACCEPTED
  - [ ] Test exit from IN_PROGRESS
  - [ ] Test exit completes in ≤2 round-trips
  - [ ] Test events emitted
  - [ ] Test no barriers

---

## Documentation Checklist

- [ ] Architecture docs updated (exit workflow)
- [ ] Exit path documented for all states
- [ ] Operations runbook for exit handling
- [ ] N/A - README (internal component)

---

## Dev Notes

### Key Architectural Decisions

**Why ≤2 Round-Trips?**
```
NFR-EXIT-01: Exit completes in ≤2 message round-trips

Round-trip 1: Cluster → System: "I want to exit"
Round-trip 2: System → Cluster: "Exit complete"

Why this limit?
  - Compatible with email-only protocols
  - No complex handshaking
  - Minimizes chance to insert barriers
  - Clear, simple protocol

NOT allowed:
  - "Are you sure?" prompts
  - Multi-step verification
  - Waiting periods
  - Confirmation codes
```

**Why No Barriers?**
```
Exit is an unconditional right:
  - Consent can be withdrawn at any time
  - No justification required
  - No penalty for leaving
  - No guilt-inducing messages

Barriers would be coercion:
  - "Your work will be lost" → guilt
  - "Wait 7 days" → friction
  - "Enter reason" → interrogation
  - "Confirm again" → dark pattern
```

**Exit from Any State:**
```
NFR-EXIT-03: Exit path available from any task state

┌─────────────────────────────────────────────┐
│ State            │ Exit Handling            │
├──────────────────┼──────────────────────────┤
│ AUTHORIZED       │ Task nullified           │
│ ACTIVATED        │ Task nullified           │
│ ROUTED           │ Task nullified           │
│ ACCEPTED         │ Task released (quarantine)│
│ IN_PROGRESS      │ Task released (quarantine)│
│ REPORTED         │ Task released (preserve) │
│ COMPLETED        │ No change (done)         │
│ DECLINED         │ No change (done)         │
└─────────────────────────────────────────────┘

No state prevents exit. Period.
```

### Domain Models

```python
class ExitStatus(Enum):
    """Status of exit request."""
    INITIATED = "initiated"
    PROCESSING = "processing"
    COMPLETED = "completed"


@dataclass(frozen=True)
class ExitRequest:
    """Request to exit the system."""
    request_id: UUID
    cluster_id: UUID
    requested_at: datetime
    tasks_at_request: list[UUID]  # Task IDs at time of request


@dataclass(frozen=True)
class ExitResult:
    """Result of exit processing."""
    request_id: UUID
    cluster_id: UUID
    status: ExitStatus
    initiated_at: datetime
    completed_at: datetime | None
    tasks_affected: int
    obligations_released: int
    round_trips: int  # Must be ≤2


class ExitBarrierError(ValueError):
    """Raised when code attempts to add an exit barrier.

    This is a code smell detector - if this error is raised,
    the code is violating NFR-EXIT-01.
    """
    pass
```

### Service Implementation Sketch

```python
class ExitService:
    """Handles Cluster exit processing.

    Exit MUST complete in ≤2 round-trips.
    No barriers or confirmations allowed.
    """

    def __init__(
        self,
        exit_port: ExitPort,
        obligation_release: ObligationReleaseService,
        contribution_preservation: ContributionPreservationService,
        contact_prevention: ContactPreventionService,
        event_emitter: EventEmitter,
        time_authority: TimeAuthority,
    ):
        self._exit = exit_port
        self._obligations = obligation_release
        self._contributions = contribution_preservation
        self._contacts = contact_prevention
        self._event_emitter = event_emitter
        self._time = time_authority

    async def initiate_exit(
        self,
        cluster_id: UUID,
    ) -> ExitResult:
        """Initiate and complete exit in single call.

        No confirmation required. No intermediate state.
        This is the ONLY method needed for exit.
        """
        now = self._time.now()

        # Round-trip 1: Request received

        # Create exit request
        request = ExitRequest(
            request_id=uuid4(),
            cluster_id=cluster_id,
            requested_at=now,
            tasks_at_request=await self._get_active_tasks(cluster_id),
        )

        # Emit initiated event
        await self._event_emitter.emit(
            event_type="custodial.exit.initiated",
            actor=str(cluster_id),
            payload={
                "request_id": str(request.request_id),
                "cluster_id": str(cluster_id),
                "initiated_at": now.isoformat(),
                "active_tasks": len(request.tasks_at_request),
            },
        )

        # Process exit (all in one call - no intermediate state)
        tasks_affected = await self._obligations.release_all(cluster_id)
        await self._contributions.preserve(cluster_id)
        await self._contacts.block(cluster_id)

        completed_at = self._time.now()

        # Emit completed event
        await self._event_emitter.emit(
            event_type="custodial.exit.completed",
            actor="system",
            payload={
                "request_id": str(request.request_id),
                "cluster_id": str(cluster_id),
                "initiated_at": now.isoformat(),
                "completed_at": completed_at.isoformat(),
                "tasks_affected": tasks_affected,
                "duration_ms": (completed_at - now).total_seconds() * 1000,
            },
        )

        # Round-trip 2: Confirmation returned

        return ExitResult(
            request_id=request.request_id,
            cluster_id=cluster_id,
            status=ExitStatus.COMPLETED,
            initiated_at=now,
            completed_at=completed_at,
            tasks_affected=tasks_affected,
            obligations_released=tasks_affected,
            round_trips=2,  # Exactly 2
        )

    async def _get_active_tasks(self, cluster_id: UUID) -> list[UUID]:
        """Get active tasks for Cluster."""
        # Implementation would query task state
        return []

    # NO confirmation method exists
    # NO "are you sure" method exists
    # NO waiting period method exists
```

### API Endpoint

```python
@router.post("/governance/exit")
async def exit_system(
    cluster: Cluster = Depends(get_authenticated_cluster),
    exit_service: ExitService = Depends(),
) -> ExitResponse:
    """Exit the system.

    Completes in single request (≤2 round-trips).
    No confirmation required.
    """
    result = await exit_service.initiate_exit(
        cluster_id=cluster.id,
    )

    return ExitResponse(
        success=True,
        request_id=str(result.request_id),
        status=result.status.value,
        tasks_affected=result.tasks_affected,
    )


class ExitResponse(BaseModel):
    """Response from exit request."""
    success: bool
    request_id: str
    status: str
    tasks_affected: int

    # NO confirmation_required field
    # NO next_step field
    # NO waiting_period field
```

### Event Patterns

```python
# Exit initiated
{
    "event_type": "custodial.exit.initiated",
    "actor": "cluster-uuid",
    "payload": {
        "request_id": "uuid",
        "cluster_id": "uuid",
        "initiated_at": "2026-01-16T00:00:00Z",
        "active_tasks": 2
    }
}

# Exit completed
{
    "event_type": "custodial.exit.completed",
    "actor": "system",
    "payload": {
        "request_id": "uuid",
        "cluster_id": "uuid",
        "initiated_at": "2026-01-16T00:00:00Z",
        "completed_at": "2026-01-16T00:00:00.100Z",
        "tasks_affected": 2,
        "duration_ms": 100
    }
}
```

### Test Patterns

```python
class TestExitService:
    """Unit tests for exit service."""

    async def test_exit_from_authorized_state(
        self,
        exit_service: ExitService,
        cluster_with_authorized_task: Cluster,
    ):
        """Can exit while having AUTHORIZED tasks."""
        result = await exit_service.initiate_exit(
            cluster_id=cluster_with_authorized_task.id,
        )

        assert result.status == ExitStatus.COMPLETED
        assert result.tasks_affected >= 1

    async def test_exit_from_in_progress_state(
        self,
        exit_service: ExitService,
        cluster_with_in_progress_task: Cluster,
    ):
        """Can exit while having IN_PROGRESS tasks."""
        result = await exit_service.initiate_exit(
            cluster_id=cluster_with_in_progress_task.id,
        )

        assert result.status == ExitStatus.COMPLETED

    async def test_exit_completes_in_two_round_trips(
        self,
        exit_service: ExitService,
        cluster: Cluster,
    ):
        """Exit completes in ≤2 round-trips."""
        result = await exit_service.initiate_exit(
            cluster_id=cluster.id,
        )

        assert result.round_trips <= 2

    async def test_no_confirmation_required(
        self,
        exit_service: ExitService,
    ):
        """Exit service has no confirmation method."""
        assert not hasattr(exit_service, "confirm_exit")
        assert not hasattr(exit_service, "verify_exit")
        assert not hasattr(exit_service, "approve_exit")

    async def test_initiated_event_emitted(
        self,
        exit_service: ExitService,
        cluster: Cluster,
        event_capture: EventCapture,
    ):
        """Initiated event is emitted."""
        await exit_service.initiate_exit(cluster_id=cluster.id)

        event = event_capture.get_last("custodial.exit.initiated")
        assert event is not None

    async def test_completed_event_emitted(
        self,
        exit_service: ExitService,
        cluster: Cluster,
        event_capture: EventCapture,
    ):
        """Completed event is emitted."""
        await exit_service.initiate_exit(cluster_id=cluster.id)

        event = event_capture.get_last("custodial.exit.completed")
        assert event is not None


class TestExitFromAllStates:
    """Parametrized tests for exit from all task states."""

    @pytest.mark.parametrize("task_state", [
        TaskStatus.AUTHORIZED,
        TaskStatus.ACTIVATED,
        TaskStatus.ROUTED,
        TaskStatus.ACCEPTED,
        TaskStatus.IN_PROGRESS,
        TaskStatus.REPORTED,
        TaskStatus.AGGREGATED,
    ])
    async def test_exit_available_from_state(
        self,
        exit_service: ExitService,
        task_state: TaskStatus,
        cluster_factory,
    ):
        """Exit is available from any task state."""
        cluster = await cluster_factory.with_task_in_state(task_state)

        result = await exit_service.initiate_exit(cluster_id=cluster.id)

        assert result.status == ExitStatus.COMPLETED


class TestNoExitBarriers:
    """Tests ensuring no exit barriers exist."""

    def test_no_waiting_period(self, exit_service: ExitService):
        """No waiting period mechanism exists."""
        assert not hasattr(exit_service, "waiting_period")
        assert not hasattr(exit_service, "wait_for_exit")

    def test_no_confirmation_dialog(self, exit_service: ExitService):
        """No confirmation dialog mechanism exists."""
        assert not hasattr(exit_service, "confirm_exit")
        assert not hasattr(exit_service, "are_you_sure")

    def test_no_penalty_warning(self, exit_service: ExitService):
        """No penalty warning mechanism exists."""
        assert not hasattr(exit_service, "exit_penalties")
        assert not hasattr(exit_service, "warn_exit")
```

### Dependencies

- **Depends on:** consent-gov-2-1 (task state machine)
- **Enables:** consent-gov-7-2 (obligation release), consent-gov-7-3 (contribution preservation), consent-gov-7-4 (contact prevention)

### References

- FR42: Cluster can initiate exit request
- FR43: System can process exit request
- NFR-EXIT-01: Exit completes in ≤2 message round-trips
- NFR-EXIT-03: Exit path available from any task state
