# Story 3.6: 48-Hour Recovery Waiting Period (FR21)

Status: done

## Story

As an **external observer**,
I want a 48-hour recovery waiting period with public notification,
so that stakeholders have time to verify before recovery.

## Acceptance Criteria

1. **AC1: Recovery Timer Starts on Initiation**
   - **Given** a fork is detected and system halted
   - **When** Keepers initiate recovery process
   - **Then** a 48-hour timer starts
   - **And** a `RecoveryWaitingPeriodStartedEvent` is created with end timestamp

2. **AC2: Public Visibility During Waiting Period**
   - **Given** the recovery waiting period is active
   - **When** it is queried
   - **Then** the end timestamp is publicly visible
   - **And** notifications are sent to registered observers

3. **AC3: Early Recovery Attempts Rejected**
   - **Given** the 48-hour period has not elapsed
   - **When** Keepers attempt to complete recovery
   - **Then** the attempt is rejected
   - **And** remaining time is displayed

4. **AC4: Recovery Allowed After Period Elapsed**
   - **Given** the 48-hour period has elapsed
   - **When** Keepers have unanimous agreement (FR22)
   - **Then** recovery can proceed
   - **And** a `RecoveryCompletedEvent` is created

## Tasks / Subtasks

- [x] Task 1: Create recovery waiting period domain errors (AC: #3)
  - [x] 1.1: Create `src/domain/errors/recovery.py`
  - [x] 1.2: Define `RecoveryWaitingPeriodNotElapsedError` with remaining time display
  - [x] 1.3: Define `RecoveryWaitingPeriodNotStartedError` for premature recovery attempts
  - [x] 1.4: Define `RecoveryAlreadyInProgressError` for duplicate initiation
  - [x] 1.5: Export from `src/domain/errors/__init__.py`
  - [x] 1.6: Write unit tests in `tests/unit/domain/test_recovery_errors.py`

- [x] Task 2: Create RecoveryWaitingPeriod domain model (AC: #1, #2, #3, #4)
  - [x] 2.1: Create `src/domain/models/recovery_waiting_period.py`
  - [x] 2.2: Define `RecoveryWaitingPeriod` dataclass with:
    - `started_at: datetime` - When recovery process initiated (UTC)
    - `ends_at: datetime` - When 48-hour period expires (UTC)
    - `crisis_event_id: UUID` - Reference to the triggering crisis event
    - `initiated_by: tuple[str, ...]` - Keeper IDs who initiated
  - [x] 2.3: Define `WAITING_PERIOD_HOURS: int = 48` constant
  - [x] 2.4: Implement `is_elapsed() -> bool` method checking current time vs ends_at
  - [x] 2.5: Implement `remaining_time() -> timedelta` method
  - [x] 2.6: Implement `check_elapsed() -> None` method raising RecoveryWaitingPeriodNotElapsedError if not elapsed
  - [x] 2.7: Factory method `start(crisis_event_id: UUID, initiated_by: tuple[str, ...]) -> RecoveryWaitingPeriod`
  - [x] 2.8: Export from `src/domain/models/__init__.py`
  - [x] 2.9: Write unit tests in `tests/unit/domain/test_recovery_waiting_period.py`

- [x] Task 3: Create RecoveryWaitingPeriodStartedEvent (AC: #1)
  - [x] 3.1: Create `src/domain/events/recovery_waiting_period_started.py`
  - [x] 3.2: Define `RECOVERY_WAITING_PERIOD_STARTED_EVENT_TYPE = "recovery_waiting_period_started"` constant
  - [x] 3.3: Define `RecoveryWaitingPeriodStartedPayload` dataclass with:
    - `crisis_event_id: UUID`
    - `started_at: datetime`
    - `ends_at: datetime`
    - `initiated_by_keepers: tuple[str, ...]`
    - `public_notification_sent: bool`
  - [x] 3.4: Export from `src/domain/events/__init__.py`
  - [x] 3.5: Write unit tests in `tests/unit/domain/test_recovery_waiting_period_started_event.py`

- [x] Task 4: Create RecoveryCompletedEvent (AC: #4)
  - [x] 4.1: Create `src/domain/events/recovery_completed.py`
  - [x] 4.2: Define `RECOVERY_COMPLETED_EVENT_TYPE = "recovery_completed"` constant
  - [x] 4.3: Define `RecoveryCompletedPayload` dataclass with:
    - `crisis_event_id: UUID`
    - `waiting_period_started_at: datetime`
    - `recovery_completed_at: datetime`
    - `keeper_ceremony_id: UUID` - Reference to unanimous Keeper ceremony
    - `approving_keepers: tuple[str, ...]`
  - [x] 4.4: Export from `src/domain/events/__init__.py`
  - [x] 4.5: Write unit tests in `tests/unit/domain/test_recovery_completed_event.py`

- [x] Task 5: Create RecoveryWaitingPeriodPort (AC: #1, #2, #3, #4)
  - [x] 5.1: Create `src/application/ports/recovery_waiting_period.py`
  - [x] 5.2: Define abstract `RecoveryWaitingPeriodPort` with:
    - `async def start_waiting_period(crisis_event_id: UUID, initiated_by: tuple[str, ...]) -> RecoveryWaitingPeriod`
    - `async def get_active_waiting_period() -> Optional[RecoveryWaitingPeriod]`
    - `async def is_waiting_period_elapsed() -> bool`
    - `async def get_remaining_time() -> Optional[timedelta]`
    - `async def complete_waiting_period(ceremony_evidence: CeremonyEvidence) -> RecoveryCompletedPayload`
  - [x] 5.3: Export from `src/application/ports/__init__.py`
  - [x] 5.4: Write unit tests in `tests/unit/application/test_recovery_waiting_period_port.py`

- [x] Task 6: Create RecoveryCoordinator application service (AC: #1, #2, #3, #4)
  - [x] 6.1: Create `src/application/services/recovery_coordinator.py`
  - [x] 6.2: Define `RecoveryCoordinator` class that:
    - Injects: `HaltChecker`, `RecoveryWaitingPeriodPort`
    - Uses halt verification before recovery operations
  - [x] 6.3: Implement `async def initiate_recovery(crisis_event_id: UUID, initiating_keepers: tuple[str, ...]) -> RecoveryWaitingPeriodStartedPayload`:
    - Verify system IS halted (can only recover from halt)
    - Start 48-hour waiting period
    - Return RecoveryWaitingPeriodStartedPayload
  - [x] 6.4: Implement `async def get_recovery_status() -> dict`:
    - Return current waiting period state
    - Include remaining time if active
    - Include whether recovery is possible
  - [x] 6.5: Implement `async def complete_recovery(ceremony_evidence: CeremonyEvidence) -> RecoveryCompletedPayload`:
    - Validate waiting period elapsed
    - Return completion payload
  - [x] 6.6: Export from `src/application/services/__init__.py`
  - [x] 6.7: Write unit tests in `tests/unit/application/test_recovery_coordinator_service.py`

- [x] Task 7: Create RecoveryWaitingPeriodStub for testing (AC: #1, #2, #3, #4)
  - [x] 7.1: Create `src/infrastructure/stubs/recovery_waiting_period_stub.py`
  - [x] 7.2: Implement stub with configurable:
    - `_active_period: Optional[RecoveryWaitingPeriod]`
    - `_force_elapsed: bool` for testing elapsed state
  - [x] 7.3: Methods to simulate waiting period start, time passage, completion
  - [x] 7.4: Export from `src/infrastructure/stubs/__init__.py`
  - [x] 7.5: Write unit tests in `tests/unit/infrastructure/test_recovery_waiting_period_stub.py`

- [x] Task 8: Integration tests (AC: #1, #2, #3, #4)
  - [x] 8.1: Create `tests/integration/test_recovery_waiting_period_integration.py`
  - [x] 8.2: Test: Initiate recovery creates event with 48-hour window
  - [x] 8.3: Test: Early recovery attempt rejected with remaining time
  - [x] 8.4: Test: Recovery succeeds after period elapsed with unanimous Keepers
  - [x] 8.5: Test: Waiting period state is queryable
  - [x] 8.6: Test: Cannot initiate recovery when not halted
  - [x] 8.7: Test: Cannot initiate second recovery while one is active
  - [x] 8.8: Test: can_complete_recovery helper correctly indicates readiness

### Review Follow-ups (AI Code Review 2026-01-07)

- [x] [AI-Review][HIGH] H1: Commit all Story 3.6 files to git - 16 files committed (cdeb269)
- [x] [AI-Review][MEDIUM] M1: Add halt state re-check in `complete_recovery()` before delegating to port [src/application/services/recovery_coordinator.py:180-190]
- [x] [AI-Review][MEDIUM] M2: Update Dev Notes code examples to use `RecoveryNotPermittedError` instead of `SystemNotHaltedError` (naming was changed per Debug Log)
- [x] [AI-Review][MEDIUM] M3: Add test coverage for port.py docstring example code [tests/unit/application/test_recovery_waiting_period_port.py:TestPortDocstringExample]
- [x] [AI-Review][LOW] L1: Verify event type naming convention (dot vs underscore) matches project standard - VERIFIED: recovery events use dot notation (recovery.completed, recovery.waiting_period_started) which is the majority pattern
- [x] [AI-Review][LOW] L2: Add per-file test counts to File List section for verification

## Dev Notes

### Constitutional Requirements

**FR21 (48-Hour Recovery Waiting Period):**
- Fork recovery SHALL include mandatory 48-hour waiting period
- Public notification SHALL be sent when waiting period starts
- Waiting period exists as "moral cost" preserving crisis gravity
- The 48 hours allows stakeholders to verify fork analysis before recovery

**FR22 (Unanimous Keeper Agreement):**
- Recovery requires unanimous Keeper agreement (integrated with ceremony from Story 3.4)
- This is checked in `complete_recovery()` via `CeremonyEvidence` validation
- Keepers must agree on which chain to designate as canonical

**NFR41 (Fork Recovery Cost):**
- Fork recovery waiting period SHALL be minimum 48 hours
- This is a constitutional floor - cannot be reduced by configuration

**Related FRs:**
- FR17: System SHALL halt immediately when fork detected (prerequisite)
- FR18: Fork detection SHALL create constitutional crisis event (prerequisite)
- FR19/FR20: Read-only access during halt (Story 3.5 - implemented)
- FR77: If unanimous Keeper agreement not achieved within 72 hours, cessation evaluation begins

**Constitutional Truths to Honor:**
- **CT-11 (Silent failure destroys legitimacy):** Recovery process MUST be publicly visible
- **CT-12 (Witnessing creates accountability):** All recovery actions are witnessed events
- **CT-13 (Integrity outranks availability):** 48-hour delay prioritizes integrity over speed

**Developer Golden Rules:**
1. **HALT VERIFIED** - Recovery only available during halt state
2. **TIME IS CONSTITUTIONAL** - 48 hours is a floor, not configurable
3. **WITNESS EVERYTHING** - Both start and completion are events
4. **FAIL LOUD** - Early recovery attempts fail with clear remaining time

### Architecture Compliance

**Hexagonal Architecture:**
- `src/domain/models/recovery_waiting_period.py` - Value object (pure domain, no I/O)
- `src/domain/events/recovery_*.py` - Event payloads (pure domain)
- `src/domain/errors/recovery.py` - Domain errors
- `src/application/ports/recovery_waiting_period.py` - Abstract port
- `src/application/services/recovery_coordinator.py` - Application service
- `src/infrastructure/stubs/recovery_waiting_period_stub.py` - Test stub

**Import Rules:**
- Domain layer: NO infrastructure imports (datetime, uuid, dataclass only)
- Application layer: Import from domain only
- Infrastructure: Implements application ports

**Layer Boundaries:**
- `RecoveryWaitingPeriod` is pure domain logic (no I/O)
- `RecoveryCoordinator` is application service (orchestrates ports)
- Time calculations use `datetime.now(timezone.utc)` in service, not domain

### Technical Implementation Notes

**RecoveryWaitingPeriod Pattern:**
```python
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

# Constitutional floor - cannot be reduced
WAITING_PERIOD_HOURS: int = 48


@dataclass(frozen=True)
class RecoveryWaitingPeriod:
    """48-hour recovery waiting period (FR21, NFR41).

    Represents an active recovery waiting period. The 48-hour duration
    is a constitutional floor that cannot be reduced.

    Constitutional Constraints:
    - FR21: Mandatory 48-hour waiting period with public notification
    - NFR41: Minimum 48 hours (constitutional floor)
    - CT-11: Process must be publicly visible
    """

    started_at: datetime
    ends_at: datetime
    crisis_event_id: UUID
    initiated_by: tuple[str, ...]

    @classmethod
    def start(
        cls,
        crisis_event_id: UUID,
        initiated_by: tuple[str, ...],
        started_at: Optional[datetime] = None,
    ) -> "RecoveryWaitingPeriod":
        """Factory to start a new 48-hour waiting period.

        Args:
            crisis_event_id: The fork/crisis that triggered recovery.
            initiated_by: Tuple of Keeper IDs who initiated recovery.
            started_at: Override start time (for testing). Defaults to now.

        Returns:
            New RecoveryWaitingPeriod with 48-hour window.
        """
        start = started_at or datetime.now(timezone.utc)
        end = start + timedelta(hours=WAITING_PERIOD_HOURS)
        return cls(
            started_at=start,
            ends_at=end,
            crisis_event_id=crisis_event_id,
            initiated_by=initiated_by,
        )

    def is_elapsed(self, current_time: Optional[datetime] = None) -> bool:
        """Check if the 48-hour period has elapsed.

        Args:
            current_time: Override current time (for testing).

        Returns:
            True if period has elapsed, False otherwise.
        """
        now = current_time or datetime.now(timezone.utc)
        return now >= self.ends_at

    def remaining_time(self, current_time: Optional[datetime] = None) -> timedelta:
        """Get remaining time in waiting period.

        Args:
            current_time: Override current time (for testing).

        Returns:
            Remaining time. Returns timedelta(0) if already elapsed.
        """
        now = current_time or datetime.now(timezone.utc)
        remaining = self.ends_at - now
        return max(remaining, timedelta(0))
```

**RecoveryCoordinator Pattern:**
```python
class RecoveryCoordinator:
    """Coordinates fork recovery process (FR21, FR22).

    Orchestrates the 48-hour recovery waiting period and
    unanimous Keeper ceremony for recovery completion.

    Constitutional Constraints:
    - FR21: 48-hour waiting period with public notification
    - FR22: Unanimous Keeper agreement required
    - FR77: 72-hour deadline before cessation evaluation
    """

    def __init__(
        self,
        halt_transport: DualChannelHaltTransport,
        event_writer: EventWriterService,
        waiting_period_repo: RecoveryWaitingPeriodPort,
        observer_notifier: Optional[ObserverNotifierPort] = None,
    ):
        self._halt = halt_transport
        self._events = event_writer
        self._periods = waiting_period_repo
        self._notifier = observer_notifier

    async def initiate_recovery(
        self,
        crisis_event_id: UUID,
        initiating_keepers: tuple[str, ...],
    ) -> RecoveryWaitingPeriod:
        """Initiate 48-hour recovery waiting period.

        Raises:
            RecoveryNotPermittedError: If system is not currently halted.
            RecoveryAlreadyInProgressError: If waiting period already active.
        """
        # Verify system IS halted
        if not await self._halt.is_halted():
            raise RecoveryNotPermittedError("Cannot initiate recovery - system not halted")

        # Check no active recovery
        existing = await self._periods.get_active_waiting_period()
        if existing is not None:
            raise RecoveryAlreadyInProgressError(
                f"Recovery already in progress, ends at {existing.ends_at}"
            )

        # Start waiting period
        period = await self._periods.start_waiting_period(
            crisis_event_id=crisis_event_id,
            initiated_by=initiating_keepers,
        )

        # Create witnessed event
        event_payload = RecoveryWaitingPeriodStartedPayload(
            crisis_event_id=crisis_event_id,
            started_at=period.started_at,
            ends_at=period.ends_at,
            initiated_by_keepers=initiating_keepers,
            public_notification_sent=self._notifier is not None,
        )
        await self._events.write_event(
            event_type=RECOVERY_WAITING_PERIOD_STARTED_EVENT_TYPE,
            payload=event_payload,
        )

        # Notify observers (if configured)
        if self._notifier:
            await self._notifier.notify_recovery_started(period)

        return period

    async def complete_recovery(
        self,
        ceremony_evidence: CeremonyEvidence,
    ) -> RecoveryCompletedPayload:
        """Complete recovery after 48 hours with unanimous Keepers.

        Raises:
            RecoveryNotPermittedError: If system is not halted.
            RecoveryWaitingPeriodNotStartedError: If no waiting period active.
            RecoveryWaitingPeriodNotElapsedError: If 48 hours not elapsed.
            InsufficientApproversError: If < unanimous Keepers.
        """
        # Verify still halted
        if not await self._halt.is_halted():
            raise RecoveryNotPermittedError("System not halted - recovery not needed")

        # Get and validate waiting period
        period = await self._periods.get_active_waiting_period()
        if period is None:
            raise RecoveryWaitingPeriodNotStartedError(
                "No recovery waiting period active"
            )

        if not period.is_elapsed():
            remaining = period.remaining_time()
            raise RecoveryWaitingPeriodNotElapsedError(
                f"FR21: 48-hour waiting period not elapsed. "
                f"Remaining: {remaining}"
            )

        # Validate ceremony (FR22 - unanimous Keepers)
        ceremony_evidence.validate()

        # Complete waiting period in repository
        await self._periods.complete_waiting_period(ceremony_evidence)

        # Clear halt via ceremony
        await self._halt.clear_halt(ceremony_evidence)

        # Create completed event
        payload = RecoveryCompletedPayload(
            crisis_event_id=period.crisis_event_id,
            waiting_period_started_at=period.started_at,
            recovery_completed_at=datetime.now(timezone.utc),
            keeper_ceremony_id=ceremony_evidence.ceremony_id,
            approving_keepers=ceremony_evidence.get_keeper_ids(),
        )
        await self._events.write_event(
            event_type=RECOVERY_COMPLETED_EVENT_TYPE,
            payload=payload,
        )

        return payload
```

**Error Patterns:**
```python
class RecoveryWaitingPeriodNotElapsedError(ConclaveError):
    """Raised when recovery attempted before 48 hours elapsed (FR21).

    The error message includes remaining time to help Keepers
    understand when recovery will be possible.
    """
    pass


class RecoveryWaitingPeriodNotStartedError(ConclaveError):
    """Raised when completing recovery without active waiting period.

    Recovery must go through the full process: initiate -> wait 48h -> complete.
    """
    pass


class RecoveryAlreadyInProgressError(ConclaveError):
    """Raised when initiating recovery while one is already active.

    Only one recovery process can be active at a time.
    """
    pass


class RecoveryNotPermittedError(ConclaveError):
    """Raised when attempting recovery operations on non-halted system.

    Recovery is only meaningful when system is in halted state.
    Named to avoid confusion with writer.py's SystemHaltedError.
    """
    pass
```

### Library/Framework Requirements

**Required Libraries (already in project):**
- `dataclasses` - Immutable data structures
- `datetime` with `timezone.utc` - Timestamps and time calculations
- `timedelta` - Duration calculations
- `uuid` - Crisis event references
- `structlog` - Structured logging
- `pytest-asyncio` - Async testing

**Patterns to Follow:**
- Use `@dataclass(frozen=True)` for domain objects
- Use `Optional[T]` not `T | None` (per project-context.md)
- Use `timezone.utc` not `datetime.UTC` (Python 3.10 compat)
- Log all recovery operations with structlog
- Include remaining time in rejection messages

### File Structure

```
src/
├── domain/
│   ├── errors/
│   │   ├── recovery.py          # NEW: FR21 recovery errors
│   │   └── __init__.py          # UPDATE: export new errors
│   ├── events/
│   │   ├── recovery_waiting_period_started.py  # NEW: Event
│   │   ├── recovery_completed.py               # NEW: Event
│   │   └── __init__.py          # UPDATE: export new events
│   └── models/
│       ├── recovery_waiting_period.py  # NEW: Value object
│       └── __init__.py          # UPDATE: export new model
├── application/
│   ├── ports/
│   │   ├── recovery_waiting_period.py  # NEW: Abstract port
│   │   └── __init__.py          # UPDATE: export new port
│   └── services/
│       ├── recovery_coordinator.py     # NEW: Application service
│       └── __init__.py          # UPDATE: export new service
└── infrastructure/
    └── stubs/
        ├── recovery_waiting_period_stub.py  # NEW: Test stub
        └── __init__.py          # UPDATE: export stub

tests/
├── unit/
│   ├── domain/
│   │   ├── test_recovery_errors.py                    # NEW
│   │   ├── test_recovery_waiting_period.py            # NEW
│   │   ├── test_recovery_waiting_period_started_event.py  # NEW
│   │   └── test_recovery_completed_event.py           # NEW
│   ├── application/
│   │   ├── test_recovery_waiting_period_port.py       # NEW
│   │   └── test_recovery_coordinator.py               # NEW
│   └── infrastructure/
│       └── test_recovery_waiting_period_stub.py       # NEW
└── integration/
    └── test_recovery_waiting_period_integration.py    # NEW
```

### Testing Standards

**Unit Tests:**
- Test `RecoveryWaitingPeriod.start()` creates 48-hour window from now
- Test `is_elapsed()` returns False before 48h, True after
- Test `remaining_time()` returns correct duration
- Test `remaining_time()` returns 0 when elapsed
- Test `RecoveryWaitingPeriodNotElapsedError` includes remaining time
- Test `RecoveryCoordinator.initiate_recovery()` requires halted state
- Test `RecoveryCoordinator.complete_recovery()` requires elapsed period
- Use `pytest.mark.asyncio` for async tests
- Use `AsyncMock` for async dependencies
- Use time mocking for elapsed state testing

**Integration Tests:**
- Test full recovery flow: initiate -> wait -> complete
- Test early completion rejection
- Test event creation and halt clearing
- Test observer notification (if configured)
- Use stub implementations with time control

**Coverage Target:** 100% for `RecoveryCoordinator` (security-critical path)

### Previous Story Learnings (Story 3.5)

**From Story 3.5 (Read-Only Access During Halt):**
- `HaltGuard` service exists for halt-aware operations
- `HaltStatusHeader` pattern for response headers
- `WriteBlockedDuringHaltError` pattern for rejection messages
- All operations check halt state first

**From Story 3.4 (Sticky Halt Semantics):**
- `CeremonyEvidence` value object exists for ceremony validation
- `DualChannelHaltTransport.clear_halt()` requires ceremony evidence
- ADR-6: Tier 1 ceremonies require 2 Keepers minimum
- `HaltClearedPayload` pattern for ceremony completion

**From Code Review:**
- Always export new types from `__init__.py` immediately
- Use consistent error message prefixes (e.g., "FR21: ...")
- Log structured events for all state changes
- Include context in error messages (remaining time, etc.)

**Patterns to Reuse:**
- `CeremonyEvidence` from domain/models
- `HaltClearedPayload` pattern for event payloads
- Stub pattern from `dual_channel_halt_stub.py`
- Error pattern from `read_only.py`

### Dependencies

**Story Dependencies:**
- **Story 3.2 (Single Conflict Halt):** Provides halt trigger
- **Story 3.3 (Dual-Channel Halt Transport):** Provides `DualChannelHaltTransport`
- **Story 3.4 (Sticky Halt Semantics):** Provides `clear_halt()` with ceremony
- **Story 3.5 (Read-Only Access During Halt):** Provides `HaltGuard`
- **Story 3.7 (Sequence Gap Detection):** May affect recovery criteria (future)

**Epic Dependencies:**
- **Epic 1 (Event Store):** `EventWriterService` for writing recovery events
- **Story 1.6 (Event Writer Service):** For creating witnessed events

**Forward Dependencies:**
- **Story 3.10 (Operational Rollback):** Uses recovery waiting period
- **Epic 7 (Cessation Protocol):** FR77 - 72-hour deadline triggers cessation evaluation

### Security Considerations

**Attack Vectors Mitigated:**
1. **Premature recovery bypass:** Time check is mandatory, cannot be skipped
2. **Unauthorized recovery initiation:** Requires Keeper signatures (future: verify signatures)
3. **Duplicate recovery processes:** Only one waiting period can be active
4. **Silent recovery:** All recovery actions create witnessed events

**Remaining Attack Surface:**
- System clock manipulation could affect time checks (use trusted time source)
- Keeper key compromise could allow unauthorized recovery initiation
- Network delays could affect observer notifications

**Constitutional Safeguards:**
- 48 hours is a floor, not a ceiling - more time allowed, less not
- Public notification ensures stakeholder awareness
- Witnessed events create permanent audit trail
- Unanimous Keeper requirement (FR22) prevents single-actor recovery

### Observer Notification Pattern (Optional)

For observer notifications when recovery starts:

```python
class ObserverNotifierPort(ABC):
    """Port for notifying external observers of constitutional events.

    Used for FR21: Public notification when recovery waiting period starts.
    """

    @abstractmethod
    async def notify_recovery_started(
        self,
        waiting_period: RecoveryWaitingPeriod,
    ) -> None:
        """Notify observers that recovery waiting period has started.

        Args:
            waiting_period: The active waiting period details.
        """
        ...

    @abstractmethod
    async def notify_recovery_completed(
        self,
        completion: RecoveryCompletedPayload,
    ) -> None:
        """Notify observers that recovery has completed.

        Args:
            completion: The recovery completion details.
        """
        ...
```

**Note:** Observer notification implementation is optional for this story.
Core functionality works without it. Can be deferred to Epic 4 (Observer Interface).

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story-3.6]
- [Source: _bmad-output/planning-artifacts/architecture.md#ADR-3]
- [Source: _bmad-output/planning-artifacts/prd.md#FR21]
- [Source: _bmad-output/planning-artifacts/prd.md#NFR41]
- [Source: _bmad-output/implementation-artifacts/stories/3-5-read-only-access-during-halt.md] - Previous story
- [Source: _bmad-output/implementation-artifacts/stories/3-4-sticky-halt-semantics.md] - Ceremony pattern
- [Source: src/application/ports/dual_channel_halt.py] - Clear halt interface
- [Source: src/domain/models/ceremony_evidence.py] - Ceremony validation
- [Source: _bmad-output/project-context.md#Constitutional-Implementation-Rules]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

- Initial naming conflict: `SystemNotHaltedError` conflicted with existing `SystemHaltedError` in `writer.py`, renamed to `RecoveryNotPermittedError`
- Integration test fix: `HaltCheckerStub` uses constructor params (`force_halted=True`) not `trigger_halt()` method

### Completion Notes List

- All 8 tasks completed with TDD (Red-Green-Refactor) approach
- 95 tests passing across unit and integration tests (updated after review)
- Constitutional constraints properly encoded (48-hour floor, FR21 references in errors)
- Signable content implemented for witnessing support
- Frozen dataclasses used for immutability throughout

### File List

**New Files Created:**
- `src/domain/errors/recovery.py` - Domain errors
- `src/domain/models/recovery_waiting_period.py` - Core 48-hour model
- `src/domain/events/recovery_waiting_period_started.py` - Event payload
- `src/domain/events/recovery_completed.py` - Event payload
- `src/application/ports/recovery_waiting_period.py` - Abstract port
- `src/application/services/recovery_coordinator.py` - Application service
- `src/infrastructure/stubs/recovery_waiting_period_stub.py` - Test stub
- `tests/unit/domain/test_recovery_errors.py` - 13 tests
- `tests/unit/domain/test_recovery_waiting_period.py` - 16 tests
- `tests/unit/domain/test_recovery_waiting_period_started_event.py` - 8 tests
- `tests/unit/domain/test_recovery_completed_event.py` - 10 tests
- `tests/unit/application/test_recovery_waiting_period_port.py` - 10 tests
- `tests/unit/application/test_recovery_coordinator_service.py` - 9 tests
- `tests/unit/infrastructure/test_recovery_waiting_period_stub.py` - 16 tests
- `tests/integration/test_recovery_waiting_period_integration.py` - 13 tests

**Modified Files:**
- `src/domain/errors/__init__.py` - Added recovery error exports
- `src/domain/models/__init__.py` - Added RecoveryWaitingPeriod, WAITING_PERIOD_HOURS exports
- `src/domain/events/__init__.py` - Added recovery event exports
- `src/application/ports/__init__.py` - Added RecoveryWaitingPeriodPort export
- `src/application/services/__init__.py` - Added RecoveryCoordinator export
- `src/infrastructure/stubs/__init__.py` - Added RecoveryWaitingPeriodStub export

