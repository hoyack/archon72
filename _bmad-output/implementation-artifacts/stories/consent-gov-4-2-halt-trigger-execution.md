# Story consent-gov-4.2: Halt Trigger & Execution

Status: ready-for-dev

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

- [ ] **Task 1: Create HaltTriggerPort interface** (AC: 1, 2)
  - [ ] Create `src/application/ports/governance/halt_trigger_port.py`
  - [ ] Define `trigger_halt()` method
  - [ ] Include operator_id, reason, message parameters
  - [ ] Return halt execution result

- [ ] **Task 2: Create HaltService** (AC: 2, 3, 4, 5)
  - [ ] Create `src/application/services/governance/halt_service.py`
  - [ ] Orchestrate halt trigger flow
  - [ ] Emit trigger event
  - [ ] Execute halt through circuit
  - [ ] Emit execution complete event

- [ ] **Task 3: Implement operator authentication** (AC: 6)
  - [ ] Verify operator identity
  - [ ] Check halt permission in rank matrix
  - [ ] Only certain ranks can trigger halt
  - [ ] Log unauthorized attempts

- [ ] **Task 4: Implement halt trigger event** (AC: 4)
  - [ ] Emit `constitutional.halt.triggered` at start
  - [ ] Include operator_id, reason, timestamp
  - [ ] Two-phase emission (intent first)
  - [ ] Knight observes trigger attempt

- [ ] **Task 5: Implement halt execution** (AC: 2, 3)
  - [ ] Call HaltCircuitAdapter.trigger_halt()
  - [ ] Wait for propagation (primary → secondary → tertiary)
  - [ ] Verify halt is established
  - [ ] Handle partial failures gracefully

- [ ] **Task 6: Implement halt completion event** (AC: 5)
  - [ ] Emit `constitutional.halt.executed` on completion
  - [ ] Include execution time, channels reached
  - [ ] Mark as final confirmation
  - [ ] Knight observes completion

- [ ] **Task 7: Implement in-flight operation handling** (AC: 8)
  - [ ] Signal all running operations
  - [ ] Operations check halt flag and abort
  - [ ] Graceful shutdown where possible
  - [ ] Log all interrupted operations

- [ ] **Task 8: Create halt API endpoint** (AC: 1, 6)
  - [ ] POST `/governance/halt` endpoint
  - [ ] Require authentication
  - [ ] Require halt permission
  - [ ] Return halt status

- [ ] **Task 9: Write comprehensive unit tests** (AC: 9)
  - [ ] Test authorized operator can halt
  - [ ] Test unauthorized operator rejected
  - [ ] Test trigger event emitted
  - [ ] Test execution event emitted
  - [ ] Test halt propagation
  - [ ] Test in-flight operations interrupted

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
