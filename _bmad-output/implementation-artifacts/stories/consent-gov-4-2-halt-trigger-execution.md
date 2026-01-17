# Story consent-gov-4.2: Halt Trigger & Execution

Status: done

---

## Story

As a **Human Operator**,
I want **to trigger a system halt**,
So that **I can stop operations immediately when needed**.

---

## Acceptance Criteria

1. **AC1:** Human Operator can trigger halt (FR22)
2. **AC2:** System executes halt operation (FR23)
3. **AC3:** Halt propagates to all components via three channels
4. **AC4:** Event `constitutional.halt.triggered` emitted at start
5. **AC5:** Event `constitutional.halt.executed` emitted on completion
6. **AC6:** Operator must be authenticated and authorized
7. **AC7:** Halt reason and message are required
8. **AC8:** All in-flight operations receive halt signal
9. **AC9:** Unit tests for halt trigger and execution

---

## Tasks / Subtasks

- [x] **Task 1: Create HaltTriggerPort interface** (AC: 1, 2)
  - [x] Create `src/application/ports/governance/halt_trigger_port.py`
  - [x] Define `trigger_halt()` method
  - [x] Include operator_id, reason, message parameters
  - [x] Return halt execution result

- [x] **Task 2: Create HaltService** (AC: 2, 3, 4, 5)
  - [x] Create `src/application/services/governance/halt_service.py`
  - [x] Orchestrate halt trigger flow
  - [x] Emit trigger event
  - [x] Execute halt through circuit
  - [x] Emit execution complete event

- [x] **Task 3: Implement operator authentication** (AC: 6)
  - [x] Verify operator identity
  - [x] Check halt permission in rank matrix
  - [x] Only certain ranks can trigger halt
  - [x] Log unauthorized attempts

- [x] **Task 4: Implement halt trigger event** (AC: 4)
  - [x] Emit `constitutional.halt.triggered` at start
  - [x] Include operator_id, reason, timestamp
  - [x] Two-phase emission (intent first)
  - [x] Knight observes trigger attempt

- [x] **Task 5: Implement halt execution** (AC: 2, 3)
  - [x] Call HaltCircuitAdapter.trigger_halt()
  - [x] Wait for propagation (primary → secondary → tertiary)
  - [x] Verify halt is established
  - [x] Handle partial failures gracefully

- [x] **Task 6: Implement halt completion event** (AC: 5)
  - [x] Emit `constitutional.halt.executed` on completion
  - [x] Include execution time, channels reached
  - [x] Mark as final confirmation
  - [x] Knight observes completion

- [x] **Task 7: Implement in-flight operation handling** (AC: 8)
  - [x] Signal all running operations via halt flag (primary channel)
  - [x] Operations check halt flag and abort (delegated to HaltChecker)
  - [x] Graceful shutdown where possible (halt adapter logs)
  - [x] Log all interrupted operations

- [x] **Task 8: Create halt API endpoint** (AC: 1, 6)
  - [x] POST `/v1/governance/halt` endpoint
  - [x] Require authentication via X-Operator-Id header
  - [x] Require halt permission
  - [x] Return halt status

- [x] **Task 9: Write comprehensive unit tests** (AC: 9)
  - [x] Test authorized operator can halt (24 tests passing)
  - [x] Test unauthorized operator rejected
  - [x] Test trigger event emitted
  - [x] Test execution event emitted
  - [x] Test halt propagation
  - [x] Test in-flight operations interrupted

---

## Documentation Checklist

- [ ] Architecture docs updated (halt trigger flow)
- [ ] Operations runbook for triggering halt
- [ ] Inline comments explaining event sequence
- [ ] N/A - README (internal component)

---

## Dev Notes

### Key Architectural Decisions

**Two-Phase Halt Events:**
```
1. constitutional.halt.triggered
   - Intent to halt
   - Emitted BEFORE halt circuit activation
   - Knight observes attempt

2. constitutional.halt.executed
   - Confirmation of halt
   - Emitted AFTER halt established
   - Includes execution details
```

**Authorization:**
```
Who can trigger halt?
  - Human Operator (designated role)
  - System (automatic fault detection)
  - Knight (integrity violation detection)

Who CANNOT trigger halt?
  - Regular participants (Clusters)
  - Automated scripts without proper auth
```

### Event Patterns

```python
# Halt triggered event (intent)
{
    "event_type": "constitutional.halt.triggered",
    "actor": "operator-uuid",
    "payload": {
        "reason": "operator",
        "message": "Manual halt for maintenance",
        "triggered_at": "2026-01-16T00:00:00Z"
    }
}

# Halt executed event (confirmation)
{
    "event_type": "constitutional.halt.executed",
    "actor": "system",
    "payload": {
        "operator_id": "uuid",
        "reason": "operator",
        "message": "Manual halt for maintenance",
        "triggered_at": "2026-01-16T00:00:00Z",
        "executed_at": "2026-01-16T00:00:00.050Z",
        "execution_ms": 50,
        "channels_reached": ["primary", "secondary", "tertiary"]
    }
}
```

### Service Implementation Sketch

```python
class HaltService:
    """Orchestrates halt trigger and execution."""

    def __init__(
        self,
        halt_circuit: HaltPort,
        event_emitter: TwoPhaseEventEmitter,
        permission_matrix: PermissionMatrixPort,
        time_authority: TimeAuthority,
    ):
        self._halt_circuit = halt_circuit
        self._event_emitter = event_emitter
        self._permissions = permission_matrix
        self._time = time_authority

    async def trigger_halt(
        self,
        operator_id: UUID,
        reason: HaltReason,
        message: str,
    ) -> HaltExecutionResult:
        """Trigger system halt.

        Must be called by authorized operator.
        """
        # 1. Verify authorization
        await self._verify_halt_permission(operator_id)

        triggered_at = self._time.now()

        # 2. Emit trigger event (intent)
        async with self._event_emitter.two_phase(
            event_type="constitutional.halt.triggered",
            payload={
                "reason": reason.value,
                "message": message,
                "triggered_at": triggered_at.isoformat(),
            },
            actor=str(operator_id),
        ) as trigger_context:

            # 3. Execute halt through circuit
            status = await self._halt_circuit.trigger_halt(
                reason=reason,
                operator_id=operator_id,
                message=message,
            )

            executed_at = self._time.now()
            execution_ms = (executed_at - triggered_at).total_seconds() * 1000

        # 4. Emit execution complete event
        await self._event_emitter.emit(
            event_type="constitutional.halt.executed",
            actor="system",
            payload={
                "operator_id": str(operator_id),
                "reason": reason.value,
                "message": message,
                "triggered_at": triggered_at.isoformat(),
                "executed_at": executed_at.isoformat(),
                "execution_ms": execution_ms,
                "channels_reached": self._get_channels_reached(status),
            },
        )

        return HaltExecutionResult(
            success=status.is_halted,
            status=status,
            execution_ms=execution_ms,
        )

    async def _verify_halt_permission(self, operator_id: UUID) -> None:
        """Verify operator has halt permission."""
        permissions = await self._permissions.get_permissions_for_actor(operator_id)

        if "halt_system" not in permissions.allowed_actions:
            # Log unauthorized attempt
            await self._event_emitter.emit(
                event_type="security.unauthorized_halt_attempt",
                actor=str(operator_id),
                payload={"attempted_action": "halt_system"},
            )
            raise UnauthorizedError("Operator not authorized to trigger halt")

    def _get_channels_reached(self, status: HaltStatus) -> list[str]:
        """Determine which channels were successfully reached."""
        # Implementation would check each channel's status
        channels = ["primary"]  # Primary always works
        # Check secondary and tertiary...
        return channels


@dataclass(frozen=True)
class HaltExecutionResult:
    """Result of halt execution."""
    success: bool
    status: HaltStatus
    execution_ms: float
```

### API Endpoint

```python
@router.post("/governance/halt")
async def trigger_halt(
    request: HaltRequest,
    operator: Operator = Depends(get_authenticated_operator),
    halt_service: HaltService = Depends(),
) -> HaltResponse:
    """Trigger system halt.

    Requires:
    - Authentication
    - halt_system permission
    """
    result = await halt_service.trigger_halt(
        operator_id=operator.id,
        reason=HaltReason(request.reason),
        message=request.message,
    )

    return HaltResponse(
        success=result.success,
        halted_at=result.status.halted_at,
        execution_ms=result.execution_ms,
    )


class HaltRequest(BaseModel):
    """Request to trigger halt."""
    reason: str  # HaltReason value
    message: str

    @validator("message")
    def message_required(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Halt message is required")
        return v


class HaltResponse(BaseModel):
    """Response from halt trigger."""
    success: bool
    halted_at: datetime
    execution_ms: float
```

### Test Patterns

```python
class TestHaltService:
    """Unit tests for halt service."""

    async def test_authorized_operator_can_halt(
        self,
        halt_service: HaltService,
        authorized_operator: Operator,
    ):
        """Authorized operator can trigger halt."""
        result = await halt_service.trigger_halt(
            operator_id=authorized_operator.id,
            reason=HaltReason.OPERATOR,
            message="Test halt",
        )

        assert result.success
        assert result.status.is_halted

    async def test_unauthorized_operator_rejected(
        self,
        halt_service: HaltService,
        regular_user: Operator,
    ):
        """Unauthorized operator cannot trigger halt."""
        with pytest.raises(UnauthorizedError):
            await halt_service.trigger_halt(
                operator_id=regular_user.id,
                reason=HaltReason.OPERATOR,
                message="Attempted halt",
            )

    async def test_trigger_event_emitted(
        self,
        halt_service: HaltService,
        authorized_operator: Operator,
        event_capture: EventCapture,
    ):
        """Trigger event emitted at start."""
        await halt_service.trigger_halt(
            operator_id=authorized_operator.id,
            reason=HaltReason.OPERATOR,
            message="Event test",
        )

        event = event_capture.get("constitutional.halt.triggered")
        assert event is not None
        assert event.payload["reason"] == "operator"

    async def test_execution_event_emitted(
        self,
        halt_service: HaltService,
        authorized_operator: Operator,
        event_capture: EventCapture,
    ):
        """Execution complete event emitted."""
        await halt_service.trigger_halt(
            operator_id=authorized_operator.id,
            reason=HaltReason.OPERATOR,
            message="Execution test",
        )

        event = event_capture.get("constitutional.halt.executed")
        assert event is not None
        assert event.payload["execution_ms"] <= 100

    async def test_halt_propagates_to_all_channels(
        self,
        halt_service: HaltService,
        authorized_operator: Operator,
        event_capture: EventCapture,
    ):
        """Halt propagates through all three channels."""
        result = await halt_service.trigger_halt(
            operator_id=authorized_operator.id,
            reason=HaltReason.OPERATOR,
            message="Propagation test",
        )

        event = event_capture.get("constitutional.halt.executed")
        assert "primary" in event.payload["channels_reached"]

    async def test_message_required(
        self,
        halt_service: HaltService,
        authorized_operator: Operator,
    ):
        """Halt requires a message."""
        with pytest.raises(ValueError):
            await halt_service.trigger_halt(
                operator_id=authorized_operator.id,
                reason=HaltReason.OPERATOR,
                message="",  # Empty message
            )
```

### Dependencies

- **Depends on:** consent-gov-4-1 (halt circuit)
- **Enables:** consent-gov-4-3 (task transitions on halt)

### References

- FR22: Human Operator can trigger system halt
- FR23: System can execute halt operation
- NFR-PERF-01: Halt completes in ≤100ms
- NFR-REL-01: Dedicated execution path
