# Story 6.3: Automatic Cessation Consideration (FR32)

Status: done

## Story

As a **system operator**,
I want automatic cessation consideration at >10 unacknowledged breaches in 90 days,
So that persistent violations trigger existential review.

## Acceptance Criteria

### AC1: Cessation Consideration Trigger (FR32)
**Given** breach count tracking
**When** >10 unacknowledged breaches occur in 90 days
**Then** cessation is automatically placed on agenda
**And** a `CessationConsiderationEvent` is created

### AC2: Breach Count Query with Trajectory (FR32)
**Given** the 90-day rolling window
**When** I query breach counts
**Then** I see current count and trajectory
**And** alert fires at 8+ breaches (warning threshold)

### AC3: Cessation Review Recording (FR32)
**Given** cessation is on the agenda
**When** the Conclave reviews
**Then** decision is recorded as event
**And** outcome (proceed/dismiss) is logged

## Tasks / Subtasks

- [x] Task 1: Create Cessation Consideration Domain Events (AC: #1, #3)
  - [x] 1.1 Create `src/domain/events/cessation.py`:
    - `CessationConsiderationEventPayload` dataclass with: `consideration_id`, `trigger_timestamp`, `breach_count`, `window_days` (90), `unacknowledged_breach_ids`, `agenda_placement_reason`
    - `CessationDecisionEventPayload` dataclass with: `decision_id`, `consideration_id`, `decision` (CessationDecision enum), `decision_timestamp`, `decided_by`, `rationale`
    - `CessationDecision` enum: `PROCEED_TO_VOTE`, `DISMISS_CONSIDERATION`, `DEFER_REVIEW`
    - Event type constants: `CESSATION_CONSIDERATION_EVENT_TYPE = "cessation.consideration"`, `CESSATION_DECISION_EVENT_TYPE = "cessation.decision"`
    - `to_dict()` methods for event writing (pattern from escalation.py)
    - `signable_content()` methods for witnessing (CT-12)
  - [x] 1.2 Export from `src/domain/events/__init__.py`

- [x] Task 2: Create Cessation Domain Errors (AC: #1, #2, #3)
  - [x] 2.1 Create `src/domain/errors/cessation.py`:
    - `CessationError(ConstitutionalViolationError)` - base for cessation errors
    - `CessationAlreadyTriggeredError(CessationError)` - cessation already on agenda for this period
    - `CessationConsiderationNotFoundError(CessationError)` - consideration does not exist
    - `InvalidCessationDecisionError(CessationError)` - invalid decision attempt
    - `BelowThresholdError(CessationError)` - breach count below trigger threshold
  - [x] 2.2 Export from `src/domain/errors/__init__.py`

- [x] Task 3: Create Cessation Ports (AC: #1, #2, #3)
  - [x] 3.1 Create `src/application/ports/cessation.py`:
    - `CessationConsiderationProtocol` with methods:
      - `async def trigger_cessation_consideration() -> CessationConsiderationEventPayload`
      - `async def record_decision(consideration_id: UUID, decision: CessationDecision, decided_by: str, rationale: str) -> CessationDecisionEventPayload`
      - `async def get_current_breach_count() -> BreachCountStatus`
      - `async def is_cessation_consideration_active() -> bool`
  - [x] 3.2 Create `BreachCountStatus` dataclass in `src/domain/models/breach_count_status.py`:
    - `current_count`, `window_days`, `threshold`, `warning_threshold` (8)
    - `days_remaining_in_window`, `breach_ids`, `trajectory` (INCREASING, STABLE, DECREASING)
    - `is_above_threshold`, `is_at_warning`, `urgency_level` properties
    - `from_breaches()` factory method for calculation
  - [x] 3.3 Create `src/application/ports/cessation_repository.py`:
    - `CessationRepositoryProtocol` with methods:
      - `async def save_consideration(consideration: CessationConsiderationEventPayload) -> None`
      - `async def save_decision(decision: CessationDecisionEventPayload) -> None`
      - `async def get_active_consideration() -> Optional[CessationConsiderationEventPayload]`
      - `async def get_consideration_by_id(consideration_id: UUID) -> Optional[CessationConsiderationEventPayload]`
      - `async def get_decision_for_consideration(consideration_id: UUID) -> Optional[CessationDecisionEventPayload]`
      - `async def list_considerations() -> list[CessationConsiderationEventPayload]`
  - [x] 3.4 Export from `src/application/ports/__init__.py` and `src/domain/models/__init__.py`

- [x] Task 4: Create Cessation Consideration Service (AC: #1, #2, #3)
  - [x] 4.1 Create `src/application/services/cessation_consideration_service.py`
  - [x] 4.2 Implement `CessationConsiderationService`:
    - Inject: `BreachRepositoryProtocol`, `EscalationRepositoryProtocol`, `CessationRepositoryProtocol`, `EventWriterService`, `HaltChecker`
    - HALT CHECK FIRST at every operation boundary (CT-11)
    - Constants: `CESSATION_THRESHOLD = 10`, `CESSATION_WINDOW_DAYS = 90`, `WARNING_THRESHOLD = 8`
  - [x] 4.3 Implement `check_and_trigger_cessation() -> Optional[CessationConsiderationEventPayload]`:
    - HALT CHECK FIRST (CT-11)
    - Query `BreachRepositoryProtocol.count_unacknowledged_in_window(90)`
    - If count > 10 AND no active consideration exists:
      - Get all unacknowledged breach IDs for inclusion
      - Create `CessationConsiderationEventPayload`
      - Write `CessationConsiderationEvent` via EventWriterService (CT-12)
      - Save to cessation repository
      - Log with FR32 reference
      - Return payload
    - If count <= 10 OR active consideration exists:
      - Return None (no action needed)
  - [x] 4.4 Implement `record_cessation_decision(consideration_id: UUID, decision: CessationDecision, decided_by: str, rationale: str) -> CessationDecisionEventPayload`:
    - HALT CHECK FIRST (CT-11)
    - Validate consideration exists via repository
    - Check no decision already recorded
    - Create `CessationDecisionEventPayload`
    - Write `CessationDecisionEvent` via EventWriterService (CT-12)
    - Save to cessation repository
    - Log decision
    - Return payload
  - [x] 4.5 Implement `get_breach_count_status() -> BreachCountStatus`:
    - HALT CHECK FIRST (CT-11)
    - Query all unacknowledged breaches in 90-day window
    - Calculate trajectory (compare last 30 days to previous 30 days)
    - Return `BreachCountStatus` with all metrics
  - [x] 4.6 Implement `get_breach_alert_status() -> Optional[BreachAlertEvent]`:
    - HALT CHECK FIRST (CT-11)
    - If count >= 8: Return warning alert
    - If count > 10: Return critical alert
    - Else: Return None
  - [x] 4.7 Export from `src/application/services/__init__.py`

- [x] Task 5: Create Cessation Repository Stub (AC: #3)
  - [x] 5.1 Create `src/infrastructure/stubs/cessation_repository_stub.py`
  - [x] 5.2 Implement `CessationRepositoryStub`:
    - In-memory storage with `dict[UUID, CessationConsiderationEventPayload]` and `dict[UUID, CessationDecisionEventPayload]`
    - Track active consideration (only one can be active at a time without decision)
    - Implement all protocol methods
    - `clear()` for test cleanup
  - [x] 5.3 Export from `src/infrastructure/stubs/__init__.py`

- [x] Task 6: Write Unit Tests (AC: #1, #2, #3)
  - [x] 6.1 Create `tests/unit/domain/test_cessation_events.py`:
    - Test `CessationConsiderationEventPayload` creation with required fields
    - Test `CessationDecisionEventPayload` creation
    - Test `CessationDecision` enum values
    - Test `to_dict()` returns dict (not bytes)
    - Test `signable_content()` determinism
    - Test payload immutability (frozen dataclass)
  - [x] 6.2 Create `tests/unit/domain/test_cessation_errors.py`:
    - Test all cessation error types
    - Test error inheritance hierarchy
    - Test error messages include FR32 reference
  - [x] 6.3 Create `tests/unit/domain/test_breach_count_status.py`:
    - Test `BreachCountStatus` dataclass
    - Test threshold calculations (10 = trigger, 8 = warning)
    - Test trajectory calculation (INCREASING, STABLE, DECREASING)
    - Test `from_breaches()` factory method
    - Test `is_above_threshold`, `is_at_warning`, `urgency_level` properties
  - [x] 6.4 Create `tests/unit/application/test_cessation_consideration_service.py`:
    - Test `check_and_trigger_cessation()` triggers at >10 breaches
    - Test `check_and_trigger_cessation()` does NOT trigger at exactly 10
    - Test `check_and_trigger_cessation()` skips if active consideration exists
    - Test `record_cessation_decision()` creates witnessed event (CT-12)
    - Test `record_cessation_decision()` fails for nonexistent consideration
    - Test `record_cessation_decision()` fails if decision already recorded
    - Test `get_breach_count_status()` returns correct trajectory
    - Test `get_breach_alert_status()` fires warning at 8+
    - Test HALT CHECK on all operations
  - [x] 6.5 Create `tests/unit/infrastructure/test_cessation_repository_stub.py`:
    - Test all repository methods
    - Test active consideration tracking
    - Test consideration-to-decision lookup

- [x] Task 7: Write Integration Tests (AC: #1, #2, #3)
  - [x] 7.1 Create `tests/integration/test_cessation_consideration_integration.py`:
    - Test: `test_fr32_cessation_triggers_at_11_breaches` (AC1)
    - Test: `test_cessation_event_is_witnessed` (AC1, CT-12)
    - Test: `test_cessation_event_includes_breach_references` (AC1)
    - Test: `test_cessation_not_triggered_at_10_breaches` (AC1 boundary)
    - Test: `test_breach_count_query_returns_status` (AC2)
    - Test: `test_warning_alert_at_8_breaches` (AC2)
    - Test: `test_trajectory_calculation` (AC2)
    - Test: `test_decision_recording_proceed` (AC3)
    - Test: `test_decision_recording_dismiss` (AC3)
    - Test: `test_decision_recording_defer` (AC3)
    - Test: `test_decision_event_is_witnessed` (AC3, CT-12)
    - Test: `test_halt_check_prevents_cessation_trigger_during_halt`
    - Test: `test_halt_check_prevents_decision_during_halt`
    - Test: `test_no_duplicate_consideration_while_active`

## Dev Notes

### Constitutional Constraints (CRITICAL)

- **FR32**: >10 unacknowledged breaches in 90 days SHALL trigger cessation consideration
- **CT-11**: Silent failure destroys legitimacy -> HALT CHECK FIRST at every operation
- **CT-12**: Witnessing creates accountability -> All events MUST be witnessed
- **CT-13**: Integrity outranks availability -> Availability may be sacrificed

### Epic 6 Context - Story 6.3 Position

Story 6.3 builds on Stories 6.1 (Breach Declaration) and 6.2 (7-Day Escalation) to implement the cessation consideration trigger. The escalation chain:

```
Breach Declared (Story 6.1)
     |
     v
+---------------------------------------------+
| EscalationService (Story 6.2)               |
| - 7-day escalation if unacknowledged        |
+---------------------------------------------+
     |
     v (if still unacknowledged after escalation)
+---------------------------------------------+
| CessationConsiderationService (Story 6.3)   | <- THIS STORY
| - check_and_trigger_cessation() [periodic]  |
| - record_cessation_decision()               |
| - get_breach_count_status()                 |
+---------------------------------------------+
     |
     v
+---------------------------------------------+
| EventWriterService                          |
| - Write CessationConsideration/Decision     |
| - Events are witnessed (CT-12)              |
+---------------------------------------------+
```

### Key Dependencies from Stories 6.1 and 6.2

From Story 6.1:
- `BreachEventPayload` from `src/domain/events/breach.py`
- `BreachRepositoryProtocol` from `src/application/ports/breach_repository.py`
- `BreachRepositoryProtocol.count_unacknowledged_in_window(window_days: int)` - Returns count of unacknowledged breaches

From Story 6.2:
- `EscalationRepositoryProtocol` from `src/application/ports/escalation_repository.py`
- Understanding that breaches may be acknowledged, which removes them from the cessation count

### Threshold Constants

```python
# Cessation trigger threshold (FR32)
CESSATION_THRESHOLD = 10  # > 10 means 11+ triggers cessation

# Warning threshold for early alerting
WARNING_THRESHOLD = 8  # Alert when reaching 8 unacknowledged breaches

# Rolling window for breach counting
CESSATION_WINDOW_DAYS = 90  # 90-day rolling window per FR32
```

### CessationDecision Enum Design

```python
class CessationDecision(str, Enum):
    """Decision choices for cessation consideration review (FR32).

    After the Conclave reviews a cessation consideration, one of these
    decisions must be recorded.
    """
    PROCEED_TO_VOTE = "proceed_to_vote"  # Move to formal cessation vote
    DISMISS_CONSIDERATION = "dismiss"     # Dismiss - situation addressed
    DEFER_REVIEW = "defer"               # Defer to next session
```

### CessationConsiderationEventPayload Design

```python
@dataclass(frozen=True)
class CessationConsiderationEventPayload:
    """Payload for cessation consideration trigger (FR32).

    Created when >10 unacknowledged breaches occur in 90 days.
    """
    consideration_id: UUID
    trigger_timestamp: datetime
    breach_count: int  # The count that triggered consideration
    window_days: int  # Always 90 per FR32
    unacknowledged_breach_ids: tuple[UUID, ...]  # References to specific breaches
    agenda_placement_reason: str  # "FR32: >10 unacknowledged breaches in 90 days"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for event writing."""
        return {
            "consideration_id": str(self.consideration_id),
            "trigger_timestamp": self.trigger_timestamp.isoformat(),
            "breach_count": self.breach_count,
            "window_days": self.window_days,
            "unacknowledged_breach_ids": [str(bid) for bid in self.unacknowledged_breach_ids],
            "agenda_placement_reason": self.agenda_placement_reason,
        }

    def signable_content(self) -> bytes:
        """Return deterministic bytes for signing (CT-12)."""
        content = self.to_dict()
        return json.dumps(content, sort_keys=True).encode("utf-8")
```

### BreachCountStatus Design

```python
class BreachTrajectory(str, Enum):
    """Trajectory of breach count over time."""
    INCREASING = "increasing"  # More breaches in recent period
    STABLE = "stable"          # Similar count across periods
    DECREASING = "decreasing"  # Fewer breaches in recent period

@dataclass(frozen=True)
class BreachCountStatus:
    """Status of unacknowledged breach count in 90-day window (FR32)."""
    current_count: int
    window_days: int  # 90
    threshold: int  # 10
    warning_threshold: int  # 8
    breach_ids: tuple[UUID, ...]
    trajectory: BreachTrajectory
    calculated_at: datetime

    @property
    def is_above_threshold(self) -> bool:
        """True if count > threshold (triggers cessation)."""
        return self.current_count > self.threshold

    @property
    def is_at_warning(self) -> bool:
        """True if count >= warning_threshold."""
        return self.current_count >= self.warning_threshold

    @property
    def urgency_level(self) -> str:
        """CRITICAL, WARNING, or NORMAL based on count."""
        if self.is_above_threshold:
            return "CRITICAL"
        if self.is_at_warning:
            return "WARNING"
        return "NORMAL"

    @classmethod
    def from_breaches(
        cls,
        breaches: list[BreachEventPayload],
        window_days: int = 90,
    ) -> "BreachCountStatus":
        """Create status from list of unacknowledged breaches."""
        # Calculate trajectory by comparing recent vs older breaches
        now = datetime.now(timezone.utc)
        midpoint = now - timedelta(days=window_days // 2)

        recent = sum(1 for b in breaches if b.detection_timestamp > midpoint)
        older = len(breaches) - recent

        if recent > older + 2:
            trajectory = BreachTrajectory.INCREASING
        elif recent < older - 2:
            trajectory = BreachTrajectory.DECREASING
        else:
            trajectory = BreachTrajectory.STABLE

        return cls(
            current_count=len(breaches),
            window_days=window_days,
            threshold=CESSATION_THRESHOLD,
            warning_threshold=WARNING_THRESHOLD,
            breach_ids=tuple(b.breach_id for b in breaches),
            trajectory=trajectory,
            calculated_at=now,
        )
```

### Periodic Check Integration

The `check_and_trigger_cessation()` method is designed to be called periodically (e.g., daily). It is idempotent:
- If no consideration is active and count > 10: creates new consideration
- If consideration already active: returns None (no duplicate)
- If count <= 10: returns None (below threshold)

**Integration Point**: A background worker or scheduled task should call this method. For MVP, manual invocation is acceptable with documentation for future automation.

### Alert Severity for Cessation

Per architecture alert levels:
- Cessation consideration created: **CRITICAL** - Page immediately, this is existential
- Warning threshold reached (8+): **HIGH** - Page immediately
- Decision recorded: **MEDIUM** - Alert on-call, 15 min response

### Import Rules (Hexagonal Architecture)

- `domain/events/cessation.py` imports from `domain/events/breach.py` (for reference), `typing`, `json`
- `domain/errors/cessation.py` inherits from `ConstitutionalViolationError`
- `application/ports/cessation*.py` imports from `domain/events/`, `domain/errors/`, `typing`
- `application/services/cessation_consideration_service.py` imports from `application/ports/`, `domain/`
- NEVER import from `infrastructure/` in `domain/` or `application/`

### Testing Standards

- ALL tests use `pytest.mark.asyncio`
- Use `AsyncMock` for async dependencies
- Unit tests mock the protocol interfaces
- Integration tests use stub implementations
- FR32 tests MUST verify:
  - Cessation triggers at >10 breaches (exactly 11, NOT 10)
  - Warning alert fires at 8+ breaches
  - Decisions are recorded with all required fields
  - All events are witnessed (CT-12)
  - HALT CHECK prevents operations during halt (CT-11)

### Learnings from Story 6.2

- Use `to_dict()` method for event payload serialization (not `signable_content()`)
- Add explicit `local_timestamp` parameter to `write_event()` calls
- Use `Optional[dict[str, Any]]` for return type annotations (not bare `dict`)
- Pattern: `payload.to_dict()` for writing, `payload.signable_content()` for signing
- HALT CHECK pattern should check state at start of every public method

### Files to Create

```
src/domain/events/cessation.py                             # Cessation event payloads
src/domain/errors/cessation.py                             # Cessation errors
src/domain/models/breach_count_status.py                   # BreachCountStatus model
src/application/ports/cessation.py                         # Cessation protocol
src/application/ports/cessation_repository.py              # Repository protocol
src/application/services/cessation_consideration_service.py # Main service
src/infrastructure/stubs/cessation_repository_stub.py      # Repository stub
tests/unit/domain/test_cessation_events.py                 # Event tests
tests/unit/domain/test_cessation_errors.py                 # Error tests
tests/unit/domain/test_breach_count_status.py              # Model tests
tests/unit/application/test_cessation_consideration_service.py # Service tests
tests/unit/infrastructure/test_cessation_repository_stub.py # Stub tests
tests/integration/test_cessation_consideration_integration.py # Integration tests
```

### Files to Modify

```
src/domain/events/__init__.py                              # Export new events
src/domain/errors/__init__.py                              # Export new errors
src/domain/models/__init__.py                              # Export new model
src/application/ports/__init__.py                          # Export new ports
src/application/services/__init__.py                       # Export new service
src/infrastructure/stubs/__init__.py                       # Export new stub
```

### Project Structure Notes

- Events follow existing payload patterns from Stories 6.1 and 6.2
- Errors inherit from `ConstitutionalViolationError` with FR32 reference
- Service follows HALT CHECK FIRST pattern throughout
- Repository stub follows in-memory dict pattern from `EscalationRepositoryStub`

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story-6.3] - Story definition
- [Source: _bmad-output/planning-artifacts/prd.md#FR32] - Cessation consideration requirement
- [Source: _bmad-output/planning-artifacts/architecture.md#CT-11] - Halt over degrade
- [Source: _bmad-output/planning-artifacts/architecture.md#CT-12] - Witnessing accountability
- [Source: _bmad-output/implementation-artifacts/stories/6-1-breach-declaration-events.md] - Breach event patterns
- [Source: _bmad-output/implementation-artifacts/stories/6-2-7-day-escalation-to-agenda.md] - Escalation patterns
- [Source: src/domain/events/escalation.py] - Event payload pattern with to_dict()
- [Source: src/application/services/escalation_service.py] - Service pattern with HALT CHECK
- [Source: _bmad-output/project-context.md] - Project implementation rules

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### Change Log

| Date | Change | Author |
|------|--------|--------|
| 2026-01-08 | Story created with comprehensive FR32 context, builds on Stories 6.1 and 6.2 foundation | Create-Story Workflow (Opus 4.5) |

### File List

