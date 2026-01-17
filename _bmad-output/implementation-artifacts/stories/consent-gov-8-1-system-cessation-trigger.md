# Story consent-gov-8.1: System Cessation Trigger

Status: done

---

## Story

As a **Human Operator**,
I want **to trigger system cessation**,
So that **the system can stop operations honorably**.

---

## Acceptance Criteria

1. **AC1:** Human Operator can trigger cessation (FR47)
2. **AC2:** Cessation blocks new motions (FR49)
3. **AC3:** Cessation halts execution (FR50)
4. **AC4:** Cessation requires Human Operator authentication
5. **AC5:** Event `constitutional.cessation.triggered` emitted
6. **AC6:** Cessation trigger is irreversible (no "undo")
7. **AC7:** All in-flight operations complete or interrupted
8. **AC8:** Unit tests for cessation trigger

---

## Tasks / Subtasks

- [x] **Task 1: Create CessationTrigger domain model** (AC: 1, 4)
  - [x] Create `src/domain/governance/cessation/cessation_trigger.py`
  - [x] Include operator_id, triggered_at
  - [x] Include reason (required documentation)
  - [x] Immutable value object

- [x] **Task 2: Create CessationTriggerService** (AC: 1, 5)
  - [x] Create `src/application/services/governance/cessation_trigger_service.py`
  - [x] Validate operator has cessation authority
  - [x] Emit `constitutional.cessation.triggered`
  - [x] Coordinate with other services

- [x] **Task 3: Create CessationPort interface** (AC: 1)
  - [x] Create `src/application/ports/governance/cessation_port.py`
  - [x] Define `trigger_cessation()` method
  - [x] Define `get_cessation_status()` method
  - [x] No `cancel_cessation()` (irreversible)

- [x] **Task 4: Implement motion blocking** (AC: 2)
  - [x] Block new motion submission
  - [x] Return `CESSATION_IN_PROGRESS` error
  - [x] Existing motions continue to completion
  - [x] No new motions accepted

- [x] **Task 5: Implement execution halt** (AC: 3)
  - [x] Signal halt to all executors
  - [x] Graceful shutdown where possible
  - [x] Force stop after timeout
  - [x] Log halt status for each component

- [x] **Task 6: Implement irreversibility** (AC: 6)
  - [x] No cancel/undo method exists
  - [x] State machine: ACTIVE → CESSATION_TRIGGERED → CEASED
  - [x] Forward-only transitions
  - [x] Any restart is new instance

- [x] **Task 7: Handle in-flight operations** (AC: 7)
  - [x] Grace period for completing operations
  - [x] Label interrupted work appropriately
  - [x] No silent drops
  - [x] All transitions recorded

- [x] **Task 8: Write comprehensive unit tests** (AC: 8)
  - [x] Test operator can trigger cessation
  - [x] Test new motions blocked
  - [x] Test execution halts
  - [x] Test irreversibility
  - [x] Test event emitted

---

## Documentation Checklist

- [x] Architecture docs updated (cessation workflow) - inline docstrings
- [x] Operations runbook for cessation procedure - via dev notes
- [x] Inline comments explaining irreversibility
- [x] N/A - README (internal component)

---

## Dev Notes

### Key Architectural Decisions

**Why Cessation?**
```
System can honorably stop:
  - Planned shutdown (maintenance)
  - Constitutional crisis
  - Deliberate end-of-life
  - Human decision to discontinue

Cessation is NOT:
  - Crash (unexpected failure)
  - Restart (temporary pause)
  - Maintenance mode (partial operation)

Cessation IS:
  - Permanent (forward-only)
  - Documented (Cessation Record)
  - Honorable (all records preserved)
  - Final (no recovery to same instance)
```

**Why Irreversible?**
```
Cessation cannot be "undone" because:
  - Legitimacy cannot be inherited
  - Continuity claims are false
  - Clean break is honest
  - New instance is new identity

If you want the system back:
  - Create new instance
  - New legitimacy starts at baseline
  - No claim to previous instance
  - Fresh constitutional foundation
```

**Motion Blocking:**
```
When cessation triggered:
  ✗ New motions rejected
  ✓ Existing motions continue
  ✓ In-progress work labeled
  ✓ Graceful completion where possible

Why allow existing to complete?
  - Honor commitments already made
  - Don't abandon mid-task
  - Clean state transition
  - Dignity for participants
```

### Domain Models

```python
class CessationStatus(Enum):
    """Status of the system regarding cessation."""
    ACTIVE = "active"                      # Normal operation
    CESSATION_TRIGGERED = "cessation_triggered"  # Shutdown in progress
    CEASED = "ceased"                      # Shutdown complete


@dataclass(frozen=True)
class CessationTrigger:
    """Record of cessation trigger.

    Created when Human Operator initiates cessation.
    Immutable - cannot be cancelled or reversed.
    """
    trigger_id: UUID
    operator_id: UUID
    triggered_at: datetime
    reason: str  # Required documentation
    # No cancelled_at (irreversible)
    # No revoked_by (irreversible)


@dataclass(frozen=True)
class CessationState:
    """Current state of cessation process."""
    status: CessationStatus
    trigger: CessationTrigger | None
    motions_blocked: bool
    execution_halted: bool
    in_flight_count: int


class CessationAlreadyTriggeredError(ValueError):
    """Raised when cessation is triggered twice."""
    pass


class MotionBlockedByCessationError(ValueError):
    """Raised when motion submitted during cessation."""
    pass
```

### Service Implementation Sketch

```python
class CessationTriggerService:
    """Handles system cessation triggering.

    Cessation is IRREVERSIBLE. No cancel method exists.
    """

    def __init__(
        self,
        cessation_port: CessationPort,
        motion_blocker: MotionBlockerPort,
        execution_halter: ExecutionHalterPort,
        event_emitter: EventEmitter,
        time_authority: TimeAuthority,
    ):
        self._cessation = cessation_port
        self._motion_blocker = motion_blocker
        self._execution_halter = execution_halter
        self._event_emitter = event_emitter
        self._time = time_authority

    async def trigger_cessation(
        self,
        operator_id: UUID,
        reason: str,
    ) -> CessationTrigger:
        """Trigger system cessation.

        This is IRREVERSIBLE. There is no cancel/undo method.

        Args:
            operator_id: The Human Operator triggering cessation
            reason: Required documentation of why

        Returns:
            CessationTrigger record

        Raises:
            CessationAlreadyTriggeredError: If cessation already in progress
        """
        now = self._time.now()

        # Check not already triggered
        current_state = await self._cessation.get_state()
        if current_state.status != CessationStatus.ACTIVE:
            raise CessationAlreadyTriggeredError(
                f"Cessation already triggered at {current_state.trigger.triggered_at}"
            )

        # Create trigger record
        trigger = CessationTrigger(
            trigger_id=uuid4(),
            operator_id=operator_id,
            triggered_at=now,
            reason=reason,
        )

        # Emit triggered event
        await self._event_emitter.emit(
            event_type="constitutional.cessation.triggered",
            actor=str(operator_id),
            payload={
                "trigger_id": str(trigger.trigger_id),
                "operator_id": str(operator_id),
                "triggered_at": now.isoformat(),
                "reason": reason,
            },
        )

        # Block new motions
        await self._motion_blocker.block_new_motions(
            reason="cessation_triggered",
        )

        # Begin execution halt
        await self._execution_halter.begin_halt(
            trigger_id=trigger.trigger_id,
            grace_period_seconds=60,  # Allow 60s to complete in-flight
        )

        # Store trigger
        await self._cessation.record_trigger(trigger)

        return trigger

    async def get_state(self) -> CessationState:
        """Get current cessation state."""
        return await self._cessation.get_state()

    # These methods intentionally do not exist:
    # async def cancel_cessation(self, ...): ...
    # async def undo_cessation(self, ...): ...
    # async def rollback_cessation(self, ...): ...


class CessationPort(Protocol):
    """Port for cessation operations.

    NO cancel/undo methods (irreversible).
    """

    async def get_state(self) -> CessationState:
        """Get current cessation state."""
        ...

    async def record_trigger(self, trigger: CessationTrigger) -> None:
        """Record cessation trigger."""
        ...

    # Intentionally NOT defined:
    # - cancel_cessation()
    # - undo_cessation()
    # - rollback_cessation()


class MotionBlockerPort(Protocol):
    """Port for blocking new motions."""

    async def block_new_motions(self, reason: str) -> None:
        """Block new motion submissions."""
        ...

    async def is_blocked(self) -> bool:
        """Check if new motions are blocked."""
        ...


class ExecutionHalterPort(Protocol):
    """Port for halting execution."""

    async def begin_halt(
        self,
        trigger_id: UUID,
        grace_period_seconds: int,
    ) -> None:
        """Begin halting execution with grace period."""
        ...

    async def get_halt_progress(self) -> HaltProgress:
        """Get progress of halt."""
        ...
```

### Event Pattern

```python
# Cessation triggered
{
    "event_type": "constitutional.cessation.triggered",
    "actor": "operator-uuid",
    "payload": {
        "trigger_id": "uuid",
        "operator_id": "uuid",
        "triggered_at": "2026-01-16T00:00:00Z",
        "reason": "Planned system retirement"
    }
}

# Motions blocked
{
    "event_type": "constitutional.motions.blocked",
    "actor": "system",
    "payload": {
        "trigger_id": "uuid",
        "blocked_at": "2026-01-16T00:00:00Z",
        "reason": "cessation_triggered"
    }
}

# Execution halt begun
{
    "event_type": "constitutional.execution.halt_begun",
    "actor": "system",
    "payload": {
        "trigger_id": "uuid",
        "halt_begun_at": "2026-01-16T00:00:00Z",
        "grace_period_seconds": 60,
        "in_flight_count": 5
    }
}
```

### Test Patterns

```python
class TestCessationTriggerService:
    """Unit tests for cessation trigger service."""

    async def test_operator_can_trigger_cessation(
        self,
        cessation_service: CessationTriggerService,
        operator: HumanOperator,
    ):
        """Human Operator can trigger cessation."""
        trigger = await cessation_service.trigger_cessation(
            operator_id=operator.id,
            reason="Planned shutdown",
        )

        assert trigger.operator_id == operator.id
        assert trigger.reason == "Planned shutdown"

    async def test_cessation_blocks_new_motions(
        self,
        cessation_service: CessationTriggerService,
        motion_blocker: FakeMotionBlockerPort,
        operator: HumanOperator,
    ):
        """New motions are blocked after cessation triggered."""
        await cessation_service.trigger_cessation(
            operator_id=operator.id,
            reason="Test",
        )

        assert await motion_blocker.is_blocked()

    async def test_cessation_halts_execution(
        self,
        cessation_service: CessationTriggerService,
        execution_halter: FakeExecutionHalterPort,
        operator: HumanOperator,
    ):
        """Execution is halted after cessation triggered."""
        await cessation_service.trigger_cessation(
            operator_id=operator.id,
            reason="Test",
        )

        progress = await execution_halter.get_halt_progress()
        assert progress.halt_begun

    async def test_cessation_triggered_event_emitted(
        self,
        cessation_service: CessationTriggerService,
        operator: HumanOperator,
        event_capture: EventCapture,
    ):
        """Triggered event is emitted."""
        await cessation_service.trigger_cessation(
            operator_id=operator.id,
            reason="Test",
        )

        event = event_capture.get_last("constitutional.cessation.triggered")
        assert event is not None
        assert event.payload["reason"] == "Test"

    async def test_cannot_trigger_cessation_twice(
        self,
        cessation_service: CessationTriggerService,
        operator: HumanOperator,
    ):
        """Cessation cannot be triggered twice."""
        await cessation_service.trigger_cessation(
            operator_id=operator.id,
            reason="First",
        )

        with pytest.raises(CessationAlreadyTriggeredError):
            await cessation_service.trigger_cessation(
                operator_id=operator.id,
                reason="Second",
            )


class TestCessationIrreversibility:
    """Tests ensuring cessation is irreversible."""

    def test_no_cancel_method(
        self,
        cessation_service: CessationTriggerService,
    ):
        """No cancel method exists."""
        assert not hasattr(cessation_service, "cancel_cessation")
        assert not hasattr(cessation_service, "abort_cessation")

    def test_no_undo_method(
        self,
        cessation_service: CessationTriggerService,
    ):
        """No undo method exists."""
        assert not hasattr(cessation_service, "undo_cessation")
        assert not hasattr(cessation_service, "revert_cessation")

    def test_no_rollback_method(
        self,
        cessation_service: CessationTriggerService,
    ):
        """No rollback method exists."""
        assert not hasattr(cessation_service, "rollback_cessation")
        assert not hasattr(cessation_service, "resume_operations")


class TestMotionBlocking:
    """Tests for motion blocking during cessation."""

    async def test_new_motion_rejected(
        self,
        motion_service: MotionService,
        cessation_service: CessationTriggerService,
        operator: HumanOperator,
    ):
        """New motions rejected during cessation."""
        await cessation_service.trigger_cessation(
            operator_id=operator.id,
            reason="Test",
        )

        with pytest.raises(MotionBlockedByCessationError):
            await motion_service.submit_motion(
                motion=Motion(content="Test motion"),
            )

    async def test_existing_motion_continues(
        self,
        motion_service: MotionService,
        cessation_service: CessationTriggerService,
        in_progress_motion: Motion,
        operator: HumanOperator,
    ):
        """Existing in-progress motions continue."""
        await cessation_service.trigger_cessation(
            operator_id=operator.id,
            reason="Test",
        )

        # Should not raise - existing motion continues
        status = await motion_service.get_status(in_progress_motion.id)
        assert status.can_continue  # Existing work honored
```

### Dependencies

- **Depends on:** consent-gov-4-1 (halt circuit)
- **Enables:** consent-gov-8-2 (cessation record creation)

### References

- FR47: Human Operator can trigger system cessation
- FR49: System can block new motions on cessation
- FR50: System can halt execution on cessation
