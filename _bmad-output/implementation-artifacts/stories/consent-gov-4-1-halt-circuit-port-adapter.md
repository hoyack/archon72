# Story consent-gov-4.1: Halt Circuit Port & Adapter

Status: ready-for-dev

---

## Story

As a **governance system**,
I want **a three-channel halt circuit**,
So that **halts propagate reliably through all components even when infrastructure fails**.

---

## Acceptance Criteria

1. **AC1:** In-memory channel (primary, fastest) checked before ANY I/O
2. **AC2:** Redis channel (secondary) propagates halt to other instances
3. **AC3:** Ledger channel (tertiary) records halt permanently
4. **AC4:** Halt completes in ≤100ms (NFR-PERF-01)
5. **AC5:** Primary halt works even if Redis/DB unavailable (NFR-REL-01)
6. **AC6:** Halt flag checked before every I/O operation
7. **AC7:** HaltPort interface defines check and trigger operations
8. **AC8:** HaltCircuitAdapter implements three-channel design
9. **AC9:** Unit tests for halt circuit reliability

---

## Tasks / Subtasks

- [ ] **Task 1: Create HaltPort interface** (AC: 7)
  - [ ] Create `src/application/ports/governance/halt_port.py`
  - [ ] Define `is_halted()` method (fast, synchronous)
  - [ ] Define `trigger_halt()` method
  - [ ] Define `get_halt_status()` method

- [ ] **Task 2: Create HaltStatus domain model** (AC: 7)
  - [ ] Create `src/domain/governance/halt/halt_status.py`
  - [ ] Define `HaltStatus` with timestamp, reason, operator_id
  - [ ] Define `HaltReason` enum (OPERATOR, SYSTEM_FAULT, INTEGRITY_VIOLATION)
  - [ ] Immutable value object

- [ ] **Task 3: Implement in-memory primary channel** (AC: 1, 5, 6)
  - [ ] Process-local atomic flag
  - [ ] No external dependencies
  - [ ] Checked synchronously (no async)
  - [ ] Default state: not halted

- [ ] **Task 4: Implement Redis secondary channel** (AC: 2)
  - [ ] Pub/sub for halt propagation
  - [ ] Subscribe on startup
  - [ ] Publish on halt trigger
  - [ ] Graceful handling if Redis unavailable

- [ ] **Task 5: Implement ledger tertiary channel** (AC: 3)
  - [ ] Record `constitutional.halt.recorded` event
  - [ ] Best-effort, AFTER halt established
  - [ ] Failure to record does NOT block halt
  - [ ] Used for audit, not halt enforcement

- [ ] **Task 6: Implement HaltCircuitAdapter** (AC: 8)
  - [ ] Create `src/infrastructure/adapters/governance/halt_circuit_adapter.py`
  - [ ] Orchestrate three channels
  - [ ] Primary → Secondary → Tertiary order on trigger
  - [ ] Check primary channel only for `is_halted()` (fast path)

- [ ] **Task 7: Implement performance constraint** (AC: 4)
  - [ ] `is_halted()` completes in <1ms (in-memory only)
  - [ ] `trigger_halt()` completes in ≤100ms
  - [ ] Profile and verify performance

- [ ] **Task 8: Implement halt check integration** (AC: 6)
  - [ ] Create `HaltChecker` utility
  - [ ] Integrate into all I/O operations
  - [ ] Raise `HaltedException` if halted
  - [ ] Document where halt checks are required

- [ ] **Task 9: Write comprehensive unit tests** (AC: 9)
  - [ ] Test primary channel halt (in-memory)
  - [ ] Test Redis propagation
  - [ ] Test ledger recording
  - [ ] Test halt works without Redis
  - [ ] Test halt works without DB
  - [ ] Test ≤100ms completion
  - [ ] Test `is_halted()` <1ms

---

## Documentation Checklist

- [ ] Architecture docs updated (three-channel halt)
- [ ] Inline comments explaining priority order
- [ ] Operations runbook for halt scenarios
- [ ] N/A - README (internal component)

---

## Dev Notes

### Key Architectural Decisions

**Halt Priority: Correctness > Observability > Durability**
```
If everything is on fire, the system must still stop.

Primary (In-Memory):
  - Process-local atomic flag
  - No external dependencies
  - Checked synchronously before ANY I/O
  - This ALWAYS works

Secondary (Redis):
  - Propagates halt to other instances
  - Async broadcast
  - Failure is tolerated (primary still works)

Tertiary (Ledger):
  - Permanent record for audit
  - Best-effort, AFTER halt is established
  - Failure does NOT block halt
```

**Why Three Channels?**
```
Failure Mode Analysis:

| Failure | Primary | Secondary | Tertiary | Halt Works? |
|---------|---------|-----------|----------|-------------|
| Normal  | ✓       | ✓         | ✓        | ✓           |
| Redis down | ✓    | ✗         | ✓        | ✓           |
| DB down | ✓       | ✓         | ✗        | ✓           |
| Both down | ✓     | ✗         | ✗        | ✓           |

The system can ALWAYS halt because primary channel has no dependencies.
```

### Domain Models

```python
class HaltReason(Enum):
    """Reason for system halt."""
    OPERATOR = "operator"              # Human triggered
    SYSTEM_FAULT = "system_fault"      # Detected fault
    INTEGRITY_VIOLATION = "integrity_violation"  # Hash chain break, etc.


@dataclass(frozen=True)
class HaltStatus:
    """Current halt status."""
    is_halted: bool
    halted_at: datetime | None
    reason: HaltReason | None
    operator_id: UUID | None
    message: str | None

    @classmethod
    def not_halted(cls) -> "HaltStatus":
        return cls(
            is_halted=False,
            halted_at=None,
            reason=None,
            operator_id=None,
            message=None,
        )

    @classmethod
    def halted(
        cls,
        reason: HaltReason,
        operator_id: UUID | None,
        message: str,
        halted_at: datetime,
    ) -> "HaltStatus":
        return cls(
            is_halted=True,
            halted_at=halted_at,
            reason=reason,
            operator_id=operator_id,
            message=message,
        )
```

### Port Interface

```python
class HaltPort(Protocol):
    """Port for halt circuit operations."""

    def is_halted(self) -> bool:
        """Check if system is halted.

        MUST be fast (<1ms) and synchronous.
        Checked before EVERY I/O operation.
        """
        ...

    async def trigger_halt(
        self,
        reason: HaltReason,
        operator_id: UUID | None,
        message: str,
    ) -> HaltStatus:
        """Trigger system halt.

        MUST complete in ≤100ms.
        Propagates through all three channels.
        """
        ...

    def get_halt_status(self) -> HaltStatus:
        """Get current halt status with details."""
        ...


class HaltedException(Exception):
    """Raised when operation attempted during halt."""

    def __init__(self, status: HaltStatus):
        self.status = status
        super().__init__(f"System halted: {status.reason.value}")
```

### Adapter Implementation Sketch

```python
import threading
from typing import Callable


class HaltCircuitAdapter:
    """Three-channel halt circuit implementation."""

    def __init__(
        self,
        redis_client: Redis | None,
        event_emitter: EventEmitter | None,
        time_authority: TimeAuthority,
    ):
        # Primary channel: process-local atomic flag
        self._halted = threading.Event()
        self._status: HaltStatus = HaltStatus.not_halted()
        self._lock = threading.Lock()

        # Secondary/tertiary channels (optional)
        self._redis = redis_client
        self._event_emitter = event_emitter
        self._time = time_authority

        # Subscribe to Redis halt channel if available
        if self._redis:
            self._subscribe_to_halt_channel()

    def is_halted(self) -> bool:
        """Fast, synchronous halt check (primary channel only)."""
        return self._halted.is_set()

    async def trigger_halt(
        self,
        reason: HaltReason,
        operator_id: UUID | None,
        message: str,
    ) -> HaltStatus:
        """Trigger halt through all three channels."""
        start = self._time.now()

        # 1. PRIMARY: Set in-memory flag (instant)
        with self._lock:
            if self._halted.is_set():
                return self._status  # Already halted

            self._status = HaltStatus.halted(
                reason=reason,
                operator_id=operator_id,
                message=message,
                halted_at=start,
            )
            self._halted.set()

        # 2. SECONDARY: Propagate via Redis (best-effort)
        try:
            if self._redis:
                await self._publish_halt_to_redis()
        except Exception as e:
            # Log but don't fail - primary halt is established
            logger.warning(f"Redis halt propagation failed: {e}")

        # 3. TERTIARY: Record to ledger (best-effort)
        try:
            if self._event_emitter:
                await self._record_halt_to_ledger()
        except Exception as e:
            # Log but don't fail - halt is established
            logger.warning(f"Ledger halt recording failed: {e}")

        # Verify we met performance target
        elapsed_ms = (self._time.now() - start).total_seconds() * 1000
        if elapsed_ms > 100:
            logger.error(f"Halt took {elapsed_ms}ms, exceeded 100ms target")

        return self._status

    def get_halt_status(self) -> HaltStatus:
        """Get current halt status with details."""
        return self._status

    async def _publish_halt_to_redis(self) -> None:
        """Publish halt to Redis channel for other instances."""
        await self._redis.publish(
            "governance:halt",
            json.dumps({
                "halted_at": self._status.halted_at.isoformat(),
                "reason": self._status.reason.value,
                "message": self._status.message,
            }),
        )

    async def _record_halt_to_ledger(self) -> None:
        """Record halt event to ledger for audit."""
        await self._event_emitter.emit(
            event_type="constitutional.halt.recorded",
            actor=str(self._status.operator_id) if self._status.operator_id else "system",
            payload={
                "halted_at": self._status.halted_at.isoformat(),
                "reason": self._status.reason.value,
                "message": self._status.message,
            },
        )

    def _subscribe_to_halt_channel(self) -> None:
        """Subscribe to Redis halt channel."""
        async def handler(message: dict) -> None:
            # Set local halt flag when receiving broadcast
            with self._lock:
                if not self._halted.is_set():
                    self._status = HaltStatus.halted(
                        reason=HaltReason(message["reason"]),
                        operator_id=None,  # Remote trigger
                        message=message["message"],
                        halted_at=datetime.fromisoformat(message["halted_at"]),
                    )
                    self._halted.set()

        self._redis.subscribe("governance:halt", handler)
```

### Halt Checker Utility

```python
class HaltChecker:
    """Utility for checking halt status before operations."""

    def __init__(self, halt_port: HaltPort):
        self._halt = halt_port

    def check_or_raise(self) -> None:
        """Check if halted, raise if so."""
        if self._halt.is_halted():
            raise HaltedException(self._halt.get_halt_status())

    def wrap_operation(self, operation: Callable[..., T]) -> Callable[..., T]:
        """Decorator to check halt before operation."""
        def wrapper(*args, **kwargs) -> T:
            self.check_or_raise()
            return operation(*args, **kwargs)
        return wrapper


# Usage in services:
class TaskActivationService:
    def __init__(self, halt_checker: HaltChecker, ...):
        self._halt = halt_checker

    async def create_activation(self, ...):
        self._halt.check_or_raise()  # Check before ANY operation
        # ... proceed with activation
```

### Test Patterns

```python
class TestHaltCircuitAdapter:
    """Unit tests for three-channel halt circuit."""

    def test_primary_channel_halt(self, halt_circuit: HaltCircuitAdapter):
        """In-memory halt works without any external services."""
        assert not halt_circuit.is_halted()

        await halt_circuit.trigger_halt(
            reason=HaltReason.OPERATOR,
            operator_id=uuid4(),
            message="Test halt",
        )

        assert halt_circuit.is_halted()

    def test_halt_works_without_redis(self, time_authority: TimeAuthority):
        """Halt works even when Redis is unavailable."""
        circuit = HaltCircuitAdapter(
            redis_client=None,  # No Redis!
            event_emitter=None,
            time_authority=time_authority,
        )

        await circuit.trigger_halt(
            reason=HaltReason.SYSTEM_FAULT,
            operator_id=None,
            message="Fault detected",
        )

        assert circuit.is_halted()

    def test_halt_works_without_db(
        self,
        redis_client: Redis,
        time_authority: TimeAuthority,
    ):
        """Halt works even when DB is unavailable."""
        circuit = HaltCircuitAdapter(
            redis_client=redis_client,
            event_emitter=None,  # No DB/event emitter!
            time_authority=time_authority,
        )

        await circuit.trigger_halt(
            reason=HaltReason.INTEGRITY_VIOLATION,
            operator_id=None,
            message="Hash chain break",
        )

        assert circuit.is_halted()

    def test_halt_completes_within_100ms(self, halt_circuit: HaltCircuitAdapter):
        """Halt must complete in ≤100ms."""
        start = time.time()

        await halt_circuit.trigger_halt(
            reason=HaltReason.OPERATOR,
            operator_id=uuid4(),
            message="Performance test",
        )

        elapsed_ms = (time.time() - start) * 1000
        assert elapsed_ms <= 100

    def test_is_halted_under_1ms(self, halt_circuit: HaltCircuitAdapter):
        """is_halted() must complete in <1ms."""
        # Warm up
        for _ in range(100):
            halt_circuit.is_halted()

        # Measure
        start = time.time()
        for _ in range(10000):
            halt_circuit.is_halted()
        elapsed_ms = (time.time() - start) * 1000

        avg_ms = elapsed_ms / 10000
        assert avg_ms < 1  # <1ms per call

    def test_redis_propagation(
        self,
        halt_circuit_a: HaltCircuitAdapter,
        halt_circuit_b: HaltCircuitAdapter,
    ):
        """Halt propagates to other instances via Redis."""
        # Instance A triggers halt
        await halt_circuit_a.trigger_halt(
            reason=HaltReason.OPERATOR,
            operator_id=uuid4(),
            message="Propagation test",
        )

        # Wait for propagation
        await asyncio.sleep(0.1)

        # Instance B should be halted too
        assert halt_circuit_b.is_halted()

    def test_ledger_recording(
        self,
        halt_circuit: HaltCircuitAdapter,
        event_capture: EventCapture,
    ):
        """Halt is recorded to ledger for audit."""
        await halt_circuit.trigger_halt(
            reason=HaltReason.OPERATOR,
            operator_id=uuid4(),
            message="Recording test",
        )

        event = event_capture.get_last("constitutional.halt.recorded")
        assert event is not None
        assert event.payload["reason"] == "operator"
```

### Dependencies

- **Depends on:** Existing Redis and event infrastructure
- **Enables:** consent-gov-4-2 (halt trigger), consent-gov-4-3 (task transitions)

### References

- AD-2: Three-channel halt circuit design
- NFR-PERF-01: Halt completes in ≤100ms
- NFR-REL-01: Dedicated execution path (no external dependencies for primary)
- Foundation 2: Halt correctness > observability > durability
