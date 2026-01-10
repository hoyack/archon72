# Story 3.7: Sequence Gap Detection (FR18-FR19)

Status: done

## Story

As a **system operator**,
I want sequence gaps detected within 1 minute,
so that missing events are caught quickly.

## Acceptance Criteria

1. **AC1: Periodic Gap Detection Service**
   - **Given** the gap detection service is running
   - **When** it checks the event store
   - **Then** it verifies sequence continuity every 30 seconds
   - **And** any gap triggers an alert

2. **AC2: Gap Detection Creates Event**
   - **Given** a sequence gap is detected (e.g., seq 100, then seq 102)
   - **When** the detector identifies it
   - **Then** a `SequenceGapDetectedEvent` is created
   - **And** the event includes: expected sequence, actual sequence, gap size

3. **AC3: Gap Requires Manual Resolution**
   - **Given** a gap detection occurs
   - **When** it is processed
   - **Then** further investigation is triggered
   - **And** the gap is NOT auto-filled (manual resolution required)

4. **AC4: Gap Detection Within 1 Minute (FR18-FR19)**
   - **Given** a gap appears in the sequence
   - **When** the detection interval elapses
   - **Then** the gap is detected within 1 minute (2 cycles of 30 seconds)
   - **And** detection latency is logged for operational monitoring

5. **AC5: Gap Detection Can Trigger Halt**
   - **Given** the gap detection service detects a gap
   - **When** the gap indicates possible integrity violation
   - **Then** a `ConstitutionalCrisisEvent` with type `SEQUENCE_GAP_DETECTED` can be created
   - **And** system halt can be triggered if configured (severity-based)

## Tasks / Subtasks

- [x] Task 1: Create sequence gap domain errors (AC: #2, #3)
  - [x] 1.1: Create `src/domain/errors/sequence_gap.py`
  - [x] 1.2: Define `SequenceGapDetectedError` with gap details
  - [x] 1.3: Define `SequenceGapResolutionRequiredError` for manual resolution marker
  - [x] 1.4: Export from `src/domain/errors/__init__.py`
  - [x] 1.5: Write unit tests in `tests/unit/domain/test_sequence_gap_errors.py`

- [x] Task 2: Add SEQUENCE_GAP_DETECTED to CrisisType enum (AC: #5)
  - [x] 2.1: Uncomment `SEQUENCE_GAP_DETECTED` in `src/domain/events/constitutional_crisis.py`
  - [x] 2.2: Update any switch/match statements if needed
  - [x] 2.3: Write unit test verifying enum value exists

- [x] Task 3: Create SequenceGapDetectedEvent payload (AC: #2)
  - [x] 3.1: Create `src/domain/events/sequence_gap_detected.py`
  - [x] 3.2: Define `SEQUENCE_GAP_DETECTED_EVENT_TYPE = "sequence.gap_detected"` constant
  - [x] 3.3: Define `SequenceGapDetectedPayload` dataclass with:
    - `detection_timestamp: datetime` - When gap was detected
    - `expected_sequence: int` - The sequence number that was expected
    - `actual_sequence: int` - The sequence number that was found
    - `gap_size: int` - Number of missing sequences
    - `missing_sequences: tuple[int, ...]` - The actual missing sequence numbers
    - `detection_service_id: str` - ID of the detecting service
    - `previous_check_timestamp: datetime` - When last successful check occurred
  - [x] 3.4: Implement `signable_content() -> bytes` for witnessing
  - [x] 3.5: Export from `src/domain/events/__init__.py`
  - [x] 3.6: Write unit tests in `tests/unit/domain/test_sequence_gap_detected_event.py`

- [x] Task 4: Create SequenceGapDetectorPort (AC: #1, #2, #4)
  - [x] 4.1: Create `src/application/ports/sequence_gap_detector.py`
  - [x] 4.2: Define abstract `SequenceGapDetectorPort` with:
    - `async def check_for_gaps() -> Optional[SequenceGapDetectedPayload]`
    - `async def get_last_check_timestamp() -> Optional[datetime]`
    - `async def get_detection_interval_seconds() -> int`
    - `async def record_gap_detection(payload: SequenceGapDetectedPayload) -> None`
  - [x] 4.3: Add docstring with FR18-FR19 references
  - [x] 4.4: Export from `src/application/ports/__init__.py`
  - [x] 4.5: Write unit tests in `tests/unit/application/test_sequence_gap_detector_port.py`

- [x] Task 5: Create SequenceGapDetectionService (AC: #1, #2, #3, #4, #5)
  - [x] 5.1: Create `src/application/services/sequence_gap_detection_service.py`
  - [x] 5.2: Define `SequenceGapDetectionService` class that:
    - Injects: `EventStorePort`, `HaltTriggerPort`, `EventWriterService`
    - Uses `validate_sequence_continuity()` helper from event_store.py
  - [x] 5.3: Implement `async def check_sequence_continuity() -> Optional[SequenceGapDetectedPayload]`:
    - Get max_sequence from event store
    - Get events in last check range
    - Use validate_sequence_continuity() to detect gaps
    - Create SequenceGapDetectedPayload if gap found
    - Log detection latency
  - [x] 5.4: Implement `async def handle_gap_detected(payload: SequenceGapDetectedPayload) -> None`:
    - Create witnessed SequenceGapDetectedEvent
    - Log alert with gap details
    - If configured, trigger halt via ConstitutionalCrisisEvent
  - [x] 5.5: Implement `async def run_detection_cycle() -> None`:
    - Check for gaps
    - Handle any detected gaps
    - Update last check timestamp
  - [x] 5.6: Add detection interval constant (30 seconds)
  - [x] 5.7: Export from `src/application/services/__init__.py`
  - [x] 5.8: Write unit tests in `tests/unit/application/test_sequence_gap_detection_service.py`

- [x] Task 6: Create SequenceGapDetectorStub (AC: #1, #2, #3, #4)
  - [x] 6.1: Create `src/infrastructure/stubs/sequence_gap_detector_stub.py`
  - [x] 6.2: Implement stub with configurable:
    - `_simulated_gaps: list[tuple[int, int]]` - (expected, actual) pairs
    - `_detection_interval: int` - configurable interval
    - `_last_check: Optional[datetime]`
  - [x] 6.3: Methods to simulate gap detection scenarios
  - [x] 6.4: Export from `src/infrastructure/stubs/__init__.py`
  - [x] 6.5: Write unit tests in `tests/unit/infrastructure/test_sequence_gap_detector_stub.py`

- [x] Task 7: Create SequenceGapMonitor background service (AC: #1, #4)
  - [x] 7.1: Create `src/application/services/sequence_gap_monitor.py`
  - [x] 7.2: Define `SequenceGapMonitor` class that:
    - Runs detection cycle every 30 seconds
    - Can be started/stopped
    - Logs all detection cycles with timing
  - [x] 7.3: Implement `async def start() -> None` - Begin monitoring loop
  - [x] 7.4: Implement `async def stop() -> None` - Stop monitoring gracefully
  - [x] 7.5: Implement `async def run_once() -> Optional[SequenceGapDetectedPayload]` - Single check
  - [x] 7.6: Export from `src/application/services/__init__.py`
  - [x] 7.7: Write unit tests in `tests/unit/application/test_sequence_gap_monitor.py`

- [x] Task 8: Integration tests (AC: #1, #2, #3, #4, #5)
  - [x] 8.1: Create `tests/integration/test_sequence_gap_detection_integration.py`
  - [x] 8.2: Test: Gap detection service runs every 30 seconds
  - [x] 8.3: Test: Gap creates SequenceGapDetectedEvent with correct fields
  - [x] 8.4: Test: Multiple gaps detected in single check
  - [x] 8.5: Test: No gap produces no event
  - [x] 8.6: Test: Detection latency is logged
  - [x] 8.7: Test: Gap detection can trigger ConstitutionalCrisisEvent
  - [x] 8.8: Test: Manual resolution required (no auto-fill)

## Dev Notes

### Constitutional Requirements

**FR18 (Sequence Gap Detection):**
- System SHALL detect sequence gaps within 1 minute
- Gap detection is a constitutional integrity check
- Sequence is the authoritative ordering mechanism (CT-3: Time is unreliable)

**FR19 (Gap Investigation):**
- Gap detection SHALL trigger further investigation
- Gaps are NOT auto-filled - manual resolution required
- Gap may indicate tampering, data loss, or system failure

**Architecture Gap Resolution (from ADR-2):**
- "Sequence gap handling: Gap in sequence = integrity violation = halt"
- Gaps are treated as potential constitutional violations
- Severity determines whether halt is triggered

**Constitutional Truths to Honor:**
- **CT-3 (Time is unreliable):** Ordering via sequence numbers only
- **CT-11 (Silent failure destroys legitimacy):** Gap detection MUST alert, not ignore
- **CT-12 (Witnessing creates accountability):** Gap detection events are witnessed
- **CT-8 (Failure modes compound):** Gap may indicate multiple failures

**Developer Golden Rules:**
1. **HALT OVER DEGRADE** - Gap is potential crisis, not silent failure
2. **SEQUENCE IS TRUTH** - Timestamps are informational, sequence is authoritative
3. **WITNESS EVERYTHING** - Gap detection creates witnessed event
4. **NO AUTO-FIX** - Manual resolution required, no auto-fill

### Architecture Compliance

**Hexagonal Architecture:**
- `src/domain/errors/sequence_gap.py` - Domain errors
- `src/domain/events/sequence_gap_detected.py` - Event payload (pure domain)
- `src/application/ports/sequence_gap_detector.py` - Abstract port
- `src/application/services/sequence_gap_detection_service.py` - Detection logic
- `src/application/services/sequence_gap_monitor.py` - Background monitor
- `src/infrastructure/stubs/sequence_gap_detector_stub.py` - Test stub

**Import Rules:**
- Domain layer: NO infrastructure imports
- Application layer: Import from domain only
- Infrastructure: Implements application ports

**Existing Infrastructure to Use:**
- `EventStorePort.verify_sequence_continuity()` - Already exists
- `validate_sequence_continuity()` helper function - Already in event_store.py
- `EventStorePort.get_max_sequence()` - For checking range
- `HaltTriggerPort` - For triggering halt if needed (Story 3.2)
- `EventWriterService` - For creating witnessed events (Story 1.6)
- `CrisisType.SEQUENCE_GAP_DETECTED` - Already defined (commented out)

### Technical Implementation Notes

**Detection Interval Pattern:**
```python
from datetime import datetime, timezone
from typing import Optional

# FR18-FR19: Detection interval for 1-minute SLA
DETECTION_INTERVAL_SECONDS: int = 30  # 2 cycles = 1 minute max detection time


@dataclass(frozen=True)
class SequenceGapDetectedPayload:
    """Payload for sequence gap detection events (FR18-FR19).

    A sequence gap indicates potential integrity violation.
    This event is witnessed and triggers investigation.

    Constitutional Constraints:
    - FR18: Gap detection within 1 minute
    - FR19: Gap triggers investigation, not auto-fill
    - CT-3: Sequence is authoritative ordering
    """

    detection_timestamp: datetime
    expected_sequence: int
    actual_sequence: int
    gap_size: int
    missing_sequences: tuple[int, ...]
    detection_service_id: str
    previous_check_timestamp: datetime

    def signable_content(self) -> bytes:
        """Return canonical bytes for signing (witnessing support)."""
        content = (
            f"gap_detected:{self.detection_timestamp.isoformat()}"
            f":expected:{self.expected_sequence}"
            f":actual:{self.actual_sequence}"
            f":gap_size:{self.gap_size}"
            f":missing:{','.join(str(s) for s in self.missing_sequences)}"
            f":service:{self.detection_service_id}"
        )
        return content.encode("utf-8")
```

**Detection Service Pattern:**
```python
class SequenceGapDetectionService:
    """Sequence gap detection service (FR18-FR19).

    Periodically checks event store for sequence gaps.
    Gaps may indicate tampering, data loss, or system failure.

    Constitutional Constraints:
    - FR18: Detect gaps within 1 minute
    - FR19: Trigger investigation, no auto-fill
    - CT-11: Silent failure destroys legitimacy
    """

    def __init__(
        self,
        event_store: EventStorePort,
        event_writer: EventWriterService,
        halt_trigger: Optional[HaltTriggerPort] = None,
        halt_on_gap: bool = False,  # Configurable severity
    ):
        self._store = event_store
        self._writer = event_writer
        self._halt = halt_trigger
        self._halt_on_gap = halt_on_gap
        self._last_checked_sequence: int = 0
        self._last_check_timestamp: Optional[datetime] = None
        self._service_id = "sequence_gap_detector"
        self._log = structlog.get_logger().bind(service=self._service_id)

    async def check_sequence_continuity(self) -> Optional[SequenceGapDetectedPayload]:
        """Check for gaps in event sequence.

        Uses existing validate_sequence_continuity() helper.

        Returns:
            SequenceGapDetectedPayload if gap found, None otherwise.
        """
        current_max = await self._store.get_max_sequence()

        if current_max == 0:
            # Empty store - nothing to check
            return None

        # Check from last checked position to current max
        start = self._last_checked_sequence + 1 if self._last_checked_sequence > 0 else 1
        if start > current_max:
            # Already checked everything
            return None

        # Verify continuity
        is_continuous, missing = await self._store.verify_sequence_continuity(
            start=start,
            end=current_max,
        )

        previous_check = self._last_check_timestamp or datetime.now(timezone.utc)
        self._last_check_timestamp = datetime.now(timezone.utc)
        self._last_checked_sequence = current_max

        if is_continuous:
            return None

        # Gap detected!
        return SequenceGapDetectedPayload(
            detection_timestamp=datetime.now(timezone.utc),
            expected_sequence=missing[0] if missing else start,
            actual_sequence=current_max,
            gap_size=len(missing),
            missing_sequences=tuple(missing),
            detection_service_id=self._service_id,
            previous_check_timestamp=previous_check,
        )

    async def handle_gap_detected(
        self,
        payload: SequenceGapDetectedPayload,
    ) -> None:
        """Handle detected sequence gap (FR19).

        Creates witnessed event and optionally triggers halt.

        Args:
            payload: The gap detection details.
        """
        self._log.warning(
            "sequence_gap_detected",
            expected=payload.expected_sequence,
            actual=payload.actual_sequence,
            gap_size=payload.gap_size,
            missing=payload.missing_sequences,
        )

        # Create witnessed gap detection event
        await self._writer.write_event(
            event_type=SEQUENCE_GAP_DETECTED_EVENT_TYPE,
            payload=payload,
        )

        # Optionally trigger halt (severity-based)
        if self._halt_on_gap and self._halt:
            crisis = ConstitutionalCrisisPayload(
                crisis_type=CrisisType.SEQUENCE_GAP_DETECTED,
                detection_timestamp=payload.detection_timestamp,
                detection_details=(
                    f"FR18-FR19: Sequence gap detected. "
                    f"Missing sequences: {payload.missing_sequences}"
                ),
                triggering_event_ids=(),
                detecting_service_id=self._service_id,
            )
            await self._halt.trigger_halt(crisis)
```

**Background Monitor Pattern:**
```python
class SequenceGapMonitor:
    """Background sequence gap monitoring service (FR18).

    Runs detection cycle every 30 seconds to meet
    1-minute detection SLA.

    Note:
        This is a background service that should be started
        with the application lifecycle.
    """

    def __init__(
        self,
        detection_service: SequenceGapDetectionService,
        interval_seconds: int = DETECTION_INTERVAL_SECONDS,
    ):
        self._detection = detection_service
        self._interval = interval_seconds
        self._running: bool = False
        self._task: Optional[asyncio.Task] = None
        self._log = structlog.get_logger().bind(service="sequence_gap_monitor")

    async def start(self) -> None:
        """Start the monitoring loop."""
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        self._log.info("sequence_gap_monitor_started", interval=self._interval)

    async def stop(self) -> None:
        """Stop the monitoring loop gracefully."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._log.info("sequence_gap_monitor_stopped")

    async def _run_loop(self) -> None:
        """Internal monitoring loop."""
        while self._running:
            try:
                start_time = datetime.now(timezone.utc)
                gap = await self._detection.check_sequence_continuity()

                if gap:
                    await self._detection.handle_gap_detected(gap)

                elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
                self._log.debug(
                    "detection_cycle_complete",
                    gap_found=gap is not None,
                    elapsed_seconds=elapsed,
                )

                # Sleep for remainder of interval
                sleep_time = max(0, self._interval - elapsed)
                await asyncio.sleep(sleep_time)

            except asyncio.CancelledError:
                raise
            except Exception as e:
                self._log.error("detection_cycle_failed", error=str(e))
                await asyncio.sleep(self._interval)

    async def run_once(self) -> Optional[SequenceGapDetectedPayload]:
        """Run a single detection cycle (for testing)."""
        gap = await self._detection.check_sequence_continuity()
        if gap:
            await self._detection.handle_gap_detected(gap)
        return gap
```

**Error Patterns:**
```python
class SequenceGapDetectedError(ConclaveError):
    """Raised when sequence gap is detected (FR18-FR19).

    The error message includes gap details for investigation.
    """

    def __init__(
        self,
        expected: int,
        actual: int,
        missing: tuple[int, ...],
    ) -> None:
        self.expected = expected
        self.actual = actual
        self.missing = missing
        super().__init__(
            f"FR18: Sequence gap detected. "
            f"Expected {expected}, found {actual}. "
            f"Missing: {missing}"
        )


class SequenceGapResolutionRequiredError(ConclaveError):
    """Raised when attempting to auto-fill sequence gaps (FR19).

    Sequence gaps require manual investigation and resolution.
    Auto-fill is constitutionally prohibited.
    """
    pass
```

### Library/Framework Requirements

**Required Libraries (already in project):**
- `asyncio` - Background monitoring loop
- `dataclasses` - Immutable data structures
- `datetime` with `timezone.utc` - Timestamps
- `structlog` - Structured logging
- `pytest-asyncio` - Async testing

**Patterns to Follow:**
- Use `@dataclass(frozen=True)` for event payloads
- Use `Optional[T]` not `T | None` (per project-context.md)
- Use `timezone.utc` for all timestamps
- Log all detection cycles with structlog
- Include detection latency in logs for SLA monitoring

### File Structure

```
src/
├── domain/
│   ├── errors/
│   │   ├── sequence_gap.py          # NEW: FR18-FR19 gap errors
│   │   └── __init__.py              # UPDATE: export new errors
│   └── events/
│       ├── constitutional_crisis.py # UPDATE: uncomment SEQUENCE_GAP_DETECTED
│       ├── sequence_gap_detected.py # NEW: Event payload
│       └── __init__.py              # UPDATE: export new event
├── application/
│   ├── ports/
│   │   ├── sequence_gap_detector.py # NEW: Abstract port
│   │   └── __init__.py              # UPDATE: export new port
│   └── services/
│       ├── sequence_gap_detection_service.py  # NEW: Detection logic
│       ├── sequence_gap_monitor.py            # NEW: Background monitor
│       └── __init__.py              # UPDATE: export new services
└── infrastructure/
    └── stubs/
        ├── sequence_gap_detector_stub.py  # NEW: Test stub
        └── __init__.py              # UPDATE: export stub

tests/
├── unit/
│   ├── domain/
│   │   ├── test_sequence_gap_errors.py           # NEW
│   │   └── test_sequence_gap_detected_event.py   # NEW
│   ├── application/
│   │   ├── test_sequence_gap_detector_port.py    # NEW
│   │   ├── test_sequence_gap_detection_service.py # NEW
│   │   └── test_sequence_gap_monitor.py          # NEW
│   └── infrastructure/
│       └── test_sequence_gap_detector_stub.py    # NEW
└── integration/
    └── test_sequence_gap_detection_integration.py # NEW
```

### Testing Standards

**Unit Tests:**
- Test `SequenceGapDetectedPayload` has all required fields
- Test `signable_content()` returns deterministic bytes
- Test `SequenceGapDetectionService.check_sequence_continuity()`:
  - Returns None when no gap
  - Returns payload with correct gap details when gap found
  - Updates last_checked_sequence correctly
- Test `SequenceGapMonitor`:
  - Starts and stops cleanly
  - Runs detection at configured interval
  - Handles exceptions gracefully
- Use `pytest.mark.asyncio` for async tests
- Use `AsyncMock` for async dependencies
- Mock time for interval testing

**Integration Tests:**
- Test full detection flow: gap → event → (optional) halt
- Test multiple gaps detected in one cycle
- Test continuous sequence produces no events
- Test detection timing meets 1-minute SLA
- Use stub implementations for controlled testing

**Coverage Target:** 100% for `SequenceGapDetectionService` (integrity-critical path)

### Previous Story Learnings (Story 3.6)

**From Story 3.6 (48-Hour Recovery Waiting Period):**
- `RecoveryCoordinator` pattern for coordinating state + events
- `CeremonyEvidence` value object for ceremony validation
- Integration with `DualChannelHaltTransport` for halt operations
- Frozen dataclasses for immutability throughout
- Error naming to avoid conflicts (e.g., `RecoveryNotPermittedError`)

**From Story 3.1-3.5:**
- `HaltTriggerPort` exists for triggering halt (Story 3.2)
- `ConstitutionalCrisisPayload` and `CrisisType` exist
- `EventWriterService` for creating witnessed events
- Dual-channel halt (Redis + DB) for halt propagation

**Code Review Learnings:**
- Always export new types from `__init__.py` immediately
- Use consistent error message prefixes (e.g., "FR18: ...")
- Log structured events for all state changes
- Include context in error messages
- Verify event type naming follows project convention (dot notation)

### Dependencies

**Story Dependencies:**
- **Story 1.1 (Event Store Schema):** Provides `EventStorePort`
- **Story 1.5 (Dual Time Authority):** Provides `validate_sequence_continuity()`
- **Story 1.6 (Event Writer Service):** Provides `EventWriterService`
- **Story 3.2 (Single Conflict Halt):** Provides `HaltTriggerPort`

**Epic Dependencies:**
- **Epic 1 (Event Store):** Core event store infrastructure

**Forward Dependencies:**
- **Story 3.8 (Signed Fork Detection):** May use similar detection patterns
- **Epic 4 (Observer Interface):** Observers will use gap detection for verification

### Security Considerations

**Attack Vectors Mitigated:**
1. **Event suppression:** Gap detection catches missing events
2. **Silent corruption:** Gaps are never ignored
3. **Time-based attacks:** Sequence (not time) is authoritative
4. **Replay attacks:** Sequence gaps prevent replay insertion

**Remaining Attack Surface:**
- Attacker with event store access could insert false gap events
- Clock manipulation could affect detection timestamps (not critical)
- DoS by triggering many false gap detections (rate limiting needed?)

**Constitutional Safeguards:**
- 30-second interval ensures 1-minute max detection time
- Witnessed events create permanent audit trail
- Manual resolution prevents auto-fill vulnerabilities
- Optional halt trigger for severe integrity violations

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story-3.7]
- [Source: _bmad-output/planning-artifacts/architecture.md#ADR-2] - Sequence gap handling
- [Source: _bmad-output/planning-artifacts/architecture.md#ADR-3] - Partition + Halt
- [Source: src/application/ports/event_store.py#validate_sequence_continuity] - Existing helper
- [Source: src/domain/events/constitutional_crisis.py#CrisisType] - SEQUENCE_GAP_DETECTED enum
- [Source: _bmad-output/implementation-artifacts/stories/3-6-48-hour-recovery-waiting-period.md] - Previous story
- [Source: _bmad-output/project-context.md#Constitutional-Implementation-Rules]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

None required - all tests passing.

### Completion Notes List

- All 8 tasks completed successfully
- 118 tests passing (including all Story 3.7 tests)
- FR18-FR19 requirements fully implemented
- Detection interval set to 30 seconds for 1-minute SLA
- `CrisisType.SEQUENCE_GAP_DETECTED` enum added
- Gap detection can optionally trigger halt via `halt_on_gap` flag
- Manual resolution required (no auto-fill) - FR19 compliant
- Hexagonal architecture maintained (domain, application, infrastructure layers)

### File List

**Domain Layer (src/domain/):**
- `src/domain/errors/sequence_gap.py` - SequenceGapDetectedError, SequenceGapResolutionRequiredError
- `src/domain/errors/__init__.py` - Updated exports
- `src/domain/events/sequence_gap_detected.py` - SequenceGapDetectedPayload, SEQUENCE_GAP_DETECTED_EVENT_TYPE
- `src/domain/events/constitutional_crisis.py` - Added CrisisType.SEQUENCE_GAP_DETECTED
- `src/domain/events/__init__.py` - Updated exports

**Application Layer (src/application/):**
- `src/application/ports/sequence_gap_detector.py` - SequenceGapDetectorPort, DETECTION_INTERVAL_SECONDS
- `src/application/ports/__init__.py` - Updated exports
- `src/application/services/sequence_gap_detection_service.py` - SequenceGapDetectionService
- `src/application/services/sequence_gap_monitor.py` - SequenceGapMonitor
- `src/application/services/__init__.py` - Updated exports

**Infrastructure Layer (src/infrastructure/):**
- `src/infrastructure/stubs/sequence_gap_detector_stub.py` - SequenceGapDetectorStub
- `src/infrastructure/stubs/__init__.py` - Updated exports

**Tests:**
- `tests/unit/domain/test_sequence_gap_errors.py` - 11 tests
- `tests/unit/domain/test_sequence_gap_detected_event.py` - 19 tests
- `tests/unit/application/test_sequence_gap_detector_port.py` - 14 tests
- `tests/unit/application/test_sequence_gap_detection_service.py` - 18 tests
- `tests/unit/application/test_sequence_gap_monitor.py` - 12 tests
- `tests/unit/infrastructure/test_sequence_gap_detector_stub.py` - 13 tests
- `tests/integration/test_sequence_gap_detection_integration.py` - 14 tests
- `tests/unit/domain/test_constitutional_crisis_event.py` - Updated with SEQUENCE_GAP_DETECTED tests

