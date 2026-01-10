# Story 9.6: Violations as Constitutional Breaches (FR109)

Status: done

## Story

As a **system operator**,
I want emergence violations treated as constitutional breaches,
So that they require Conclave response.

## Acceptance Criteria

### AC1: Emergence Violations Create Breach Events
**Given** an emergence violation is confirmed (via prohibited language blocking)
**When** it is recorded
**Then** a `BreachEvent` is created with `breach_type: EMERGENCE_VIOLATION`
**And** includes: violation_id, content_id, matched_terms, detection_method

### AC2: 7-Day Escalation Timer Starts
**Given** an emergence violation breach is created
**When** it is recorded
**Then** the 7-day escalation timer starts automatically (FR31)
**And** breach appears in pending escalations query

### AC3: Conclave Response Recording
**Given** the breach
**When** Conclave responds
**Then** response is recorded via breach acknowledgment (existing FR31 flow)
**And** remediation is tracked

### AC4: HALT CHECK FIRST Compliance (CT-11)
**Given** any violation-to-breach service operation
**When** invoked
**Then** halt state is checked first
**And** if halted, operation fails with SystemHaltedError

### AC5: All Breach Events Witnessed (CT-12)
**Given** emergence violation breach creation
**When** breach event is created
**Then** it is signed and witnessed via EventWriterService
**And** forms part of the constitutional record

### AC6: Integration with Existing Prohibited Language Blocking
**Given** the ProhibitedLanguageBlockingService detects a violation
**When** it blocks content and raises ProhibitedLanguageBlockedError
**Then** a constitutional breach MUST be created for the violation
**And** the breach references the original blocked event

## Tasks / Subtasks

- [x] **Task 1: Add EMERGENCE_VIOLATION to BreachType Enum** (AC: 1)
  - [x] Edit `src/domain/events/breach.py`
    - [x] Add `EMERGENCE_VIOLATION = "EMERGENCE_VIOLATION"` to BreachType enum
    - [x] Add docstring: "Emergence language violation detected (FR55, FR109)"
  - [x] No __init__.py changes needed (BreachType already exported)

- [x] **Task 2: Create Emergence Violation Breach Service** (AC: 1, 2, 4, 5)
  - [x] Create `src/application/services/emergence_violation_breach_service.py`
    - [x] `EmergenceViolationBreachService` class
    - [x] Constructor: `breach_service: BreachDeclarationService`, `halt_checker: HaltChecker`
    - [x] `async def create_breach_for_violation(self, violation_event_id: UUID, content_id: str, matched_terms: tuple[str, ...], detection_method: str) -> BreachEventPayload`
      - [x] HALT CHECK FIRST (CT-11)
      - [x] Call `breach_service.declare_breach()` with:
        - [x] `breach_type=BreachType.EMERGENCE_VIOLATION`
        - [x] `violated_requirement="FR55"` (No emergence claims)
        - [x] `severity=BreachSeverity.HIGH` (Page immediately)
        - [x] `details={content_id, matched_terms, detection_method, violation_event_id}`
        - [x] `source_event_id=violation_event_id`
      - [x] Return the created BreachEventPayload
    - [x] Docstrings with FR109 and CT-11/CT-12 references
  - [x] Update `src/application/services/__init__.py` with export

- [x] **Task 3: Create Emergence Violation Breach Orchestrator** (AC: 1, 2, 3, 6)
  - [x] Create `src/application/services/emergence_violation_orchestrator.py`
    - [x] `EmergenceViolationOrchestrator` class
    - [x] Constructor: `blocking_service: ProhibitedLanguageBlockingService`, `breach_service: EmergenceViolationBreachService`, `halt_checker: HaltChecker`
    - [x] `async def check_and_report_violation(self, content_id: str, content: str) -> ScanResult`
      - [x] HALT CHECK FIRST (CT-11)
      - [x] Try: call `blocking_service.check_content_for_prohibited_language()`
      - [x] Catch `ProhibitedLanguageBlockedError`:
        - [x] Generate deterministic violation_event_id from content_id
        - [x] Call `breach_service.create_breach_for_violation()` with event details
        - [x] Re-raise the original error (fail loud)
      - [x] Return ScanResult if no violation
    - [x] Docstrings with FR109, FR55, CT-11, CT-12 references
  - [x] Update `src/application/services/__init__.py` with export

- [x] **Task 4: Create Service Error Types** (AC: 4)
  - [x] Verified existing error types sufficient (BreachDeclarationError, ProhibitedLanguageBlockedError, SystemHaltedError)
  - [x] No new error types needed

- [x] **Task 5: Create Service Stubs for Testing** (AC: 1, 2, 4, 5)
  - [x] Create `src/infrastructure/stubs/emergence_violation_breach_service_stub.py`
    - [x] `EmergenceViolationBreachServiceStub` with:
      - [x] In-memory breach storage
      - [x] `set_halt_state(halted: bool)` for testing
      - [x] `get_created_breaches() -> list[BreachEventPayload]`
      - [x] `clear()` for test isolation
  - [x] Update `src/infrastructure/stubs/__init__.py` with export

- [x] **Task 6: Write Unit Tests** (AC: 1, 2, 3, 4, 5, 6)
  - [x] Create `tests/unit/application/test_emergence_violation_breach_service.py`
    - [x] Test HALT CHECK FIRST pattern (4 tests)
    - [x] Test breach creation with correct type (4 tests)
    - [x] Test breach includes all required details (4 tests)
    - [x] Test severity is HIGH (2 tests)
    - [x] Test violated_requirement is FR55 (2 tests)
    - [x] Test error propagation (2 tests)
  - [x] Create `tests/unit/application/test_emergence_violation_orchestrator.py`
    - [x] Test HALT CHECK FIRST pattern (4 tests)
    - [x] Test clean content passes through (2 tests)
    - [x] Test violation creates breach (4 tests)
    - [x] Test original error re-raised (2 tests)
    - [x] Test scan error propagation (1 test)
    - [x] Test breach service error handling (1 test)
  - [x] Total: 30 unit tests passing

- [x] **Task 7: Write Integration Tests** (AC: 1, 2, 3, 4, 5, 6)
  - [x] Create `tests/integration/test_violations_as_breaches_integration.py`
    - [x] Test end-to-end violation detection to breach creation (4 tests)
    - [x] Test HALT CHECK FIRST across all services (4 tests)
    - [x] Test breach event witnessing (2 tests)
    - [x] Test breach type is EMERGENCE_VIOLATION (2 tests)
    - [x] Test escalation timer prerequisites (2 tests)
    - [x] Test service stub (3 tests)
  - [x] Total: 17 integration tests passing

## Dev Notes

### Relationship to Previous Stories

**Story 9-1 (No Emergence Claims)** established the prohibited language scanner.
**Story 9-2 (Automated Keyword Scanning)** implemented ProhibitedLanguageScannerProtocol.
**Story 9-5 (Audit Results as Events)** established AuditEventQueryService pattern.

**Story 9-6 (This Story)** adds:
- **Constitutional breach creation** when emergence violations are detected
- **Integration** with existing BreachDeclarationService (Story 6.1)
- **Automatic escalation timer** via EscalationService (Story 6.2)

### CRITICAL: Integration Points

```
ProhibitedLanguageBlockingService (Story 9-1)
    ↓ detects violation, creates event, raises error
EmergenceViolationOrchestrator (NEW)
    ↓ catches error, queries event, creates breach
EmergenceViolationBreachService (NEW)
    ↓ calls existing breach infrastructure
BreachDeclarationService (Story 6.1)
    ↓ creates witnessed breach event
EscalationService (Story 6.2)
    ↓ 7-day timer starts automatically
```

### Architecture Pattern: Orchestrator + Domain Service

```
EmergenceViolationOrchestrator (new - coordinates flow)
    └── ProhibitedLanguageBlockingService (existing - detection)
    └── EmergenceViolationBreachService (new - breach creation)
        └── BreachDeclarationService (existing - breach infrastructure)
```

### Relevant FR and CT References

**FR109 (Violations as Constitutional Breaches):**
From `_bmad-output/planning-artifacts/epics.md#Story-9.6`:

> Emergence violations treated as constitutional breaches.
> Requires Conclave response.
> BreachEvent created with breach_type: EMERGENCE_VIOLATION.
> 7-day escalation timer starts.

**FR55 (No Emergence Claims):**
The violated requirement for all emergence violations.

**FR31 (7-Day Escalation):**
Unacknowledged breaches after 7 days escalate to Conclave agenda.

**CT-11 (Silent Failure Destroys Legitimacy):**
- HALT CHECK FIRST on every service method
- Never silently allow violations to pass

**CT-12 (Witnessing Creates Accountability):**
- All breach events witnessed via EventWriterService
- Breach creation uses existing witnessed infrastructure

### BreachType Enum Addition

Add to `src/domain/events/breach.py`:

```python
class BreachType(Enum):
    # ... existing types ...

    EMERGENCE_VIOLATION = "EMERGENCE_VIOLATION"
    """Emergence language violation detected (FR55, FR109)."""
```

### Service Implementation Pattern

```python
class EmergenceViolationBreachService:
    """Creates constitutional breaches for emergence violations (FR109).

    Constitutional Constraints:
    - FR109: Emergence violations create constitutional breaches
    - FR55: The violated requirement (no emergence claims)
    - CT-11: HALT CHECK FIRST
    - CT-12: All breaches witnessed via BreachDeclarationService

    Developer Golden Rules:
    1. HALT CHECK FIRST - Every operation checks halt state
    2. WITNESS EVERYTHING - Delegated to BreachDeclarationService
    3. FAIL LOUD - Raise errors for all failures
    """

    def __init__(
        self,
        breach_service: BreachDeclarationService,
        halt_checker: HaltChecker,
    ) -> None:
        self._breach_service = breach_service
        self._halt_checker = halt_checker

    async def create_breach_for_violation(
        self,
        violation_event_id: UUID,
        content_id: str,
        matched_terms: tuple[str, ...],
        detection_method: str,
    ) -> BreachEventPayload:
        """Create constitutional breach for emergence violation (FR109).

        HALT CHECK FIRST (CT-11).

        Args:
            violation_event_id: UUID of the ProhibitedLanguageBlockedEvent.
            content_id: Identifier of the blocked content.
            matched_terms: Terms that triggered the violation.
            detection_method: How violation was detected.

        Returns:
            The created BreachEventPayload.

        Raises:
            SystemHaltedError: If system is halted (CT-11).
            BreachDeclarationError: If breach creation fails.
        """
        # HALT CHECK FIRST (Golden Rule #1)
        if await self._halt_checker.is_halted():
            raise SystemHaltedError("System halted")

        # Create breach via existing infrastructure (CT-12 compliance delegated)
        return await self._breach_service.declare_breach(
            breach_type=BreachType.EMERGENCE_VIOLATION,
            violated_requirement="FR55",
            severity=BreachSeverity.HIGH,  # Page immediately
            details={
                "content_id": content_id,
                "matched_terms": list(matched_terms),
                "detection_method": detection_method,
                "violation_event_id": str(violation_event_id),
            },
            source_event_id=violation_event_id,
        )
```

### Orchestrator Pattern

```python
class EmergenceViolationOrchestrator:
    """Orchestrates violation detection and breach creation (FR109).

    This orchestrator coordinates between:
    - ProhibitedLanguageBlockingService (detection)
    - EmergenceViolationBreachService (breach creation)

    Constitutional Constraints:
    - FR109: Violations become breaches
    - FR55: No emergence claims
    - CT-11: HALT CHECK FIRST
    - CT-12: All events witnessed (delegated)
    """

    async def check_and_report_violation(
        self,
        content_id: str,
        content: str,
    ) -> ScanResult:
        """Check content and create breach if violation detected (FR109).

        Flow:
        1. HALT CHECK FIRST (CT-11)
        2. Call blocking service to check content
        3. If violation detected:
           a. Query event store for blocked event
           b. Create constitutional breach
           c. Re-raise original error (fail loud)
        4. Return clean result if no violation

        Args:
            content_id: Unique identifier for content.
            content: Text content to check.

        Returns:
            ScanResult if content is clean.

        Raises:
            SystemHaltedError: If system is halted.
            ProhibitedLanguageBlockedError: If violation detected (after breach created).
        """
        # HALT CHECK FIRST
        if await self._halt_checker.is_halted():
            raise SystemHaltedError("System halted")

        try:
            return await self._blocking_service.check_content_for_prohibited_language(
                content_id=content_id,
                content=content,
            )
        except ProhibitedLanguageBlockedError as e:
            # Violation detected - create breach before re-raising
            # Query for the blocked event to get its UUID
            blocked_events = await self._event_query.query_events_with_payload_filter(
                event_type="prohibited_language.blocked",
                payload_filter={"content_id": content_id},
                limit=1,
            )

            if blocked_events:
                event_id = UUID(blocked_events[0]["event_id"])
                matched_terms = tuple(e.matched_terms)

                await self._breach_service.create_breach_for_violation(
                    violation_event_id=event_id,
                    content_id=content_id,
                    matched_terms=matched_terms,
                    detection_method="keyword_scan",
                )

            # Re-raise original error (fail loud)
            raise
```

### Source Tree Components to Touch

**Files to Create:**
```
src/application/services/emergence_violation_breach_service.py
src/application/services/emergence_violation_orchestrator.py
src/domain/errors/emergence_violation.py (if needed)
src/infrastructure/stubs/emergence_violation_breach_service_stub.py
tests/unit/application/test_emergence_violation_breach_service.py
tests/unit/application/test_emergence_violation_orchestrator.py
tests/integration/test_violations_as_breaches_integration.py
```

**Files to Modify:**
```
src/domain/events/breach.py                    # Add EMERGENCE_VIOLATION to BreachType
src/application/services/__init__.py           # Export new services
src/domain/errors/__init__.py                  # Export new errors (if created)
src/infrastructure/stubs/__init__.py           # Export new stub
```

### Testing Standards Summary

**Coverage Requirements:**
- Minimum 80% coverage
- 100% coverage for breach creation path
- All HALT CHECK FIRST patterns tested

**Async Testing:**
- ALL test files use `pytest.mark.asyncio`
- Use `AsyncMock` for async port methods
- Mock `HaltChecker`, `BreachDeclarationService`, `ProhibitedLanguageBlockingService` in unit tests

**Key Test Scenarios:**
1. Violation creates breach with correct type (EMERGENCE_VIOLATION)
2. Breach has violated_requirement="FR55"
3. Breach has severity=HIGH
4. Breach details include all violation context
5. source_event_id links to blocked event
6. HALT CHECK FIRST prevents all operations when halted
7. 7-day escalation timer starts (via existing infrastructure)
8. Clean content does not create breach
9. Original ProhibitedLanguageBlockedError re-raised after breach creation

### Previous Story Intelligence (Story 9-5)

**Learnings from Story 9-5:**
1. Service pattern: Constructor injection with ports
2. HALT CHECK FIRST at start of every public method
3. Event payloads reference FR numbers in docstrings
4. Errors inherit from `ConstitutionalViolationError`
5. Query services transform raw events to domain objects

**Existing Infrastructure to Reuse:**
- `BreachDeclarationService` (Story 6.1) - breach creation
- `BreachType` enum (Story 6.1) - add new type
- `EscalationService` (Story 6.2) - 7-day timer automatic
- `ProhibitedLanguageBlockingService` (Story 9.1) - violation detection
- `EventQueryProtocol` (Story 9.5) - query blocked events

### Git Intelligence (Recent Commits)

```
686a37a feat(story-7.6): Implement cessation as final recorded event (FR24)
cdeb269 feat(story-3.6): Implement 48-hour recovery waiting period (FR21)
```

**Commit pattern for this story:**
```
feat(story-9.6): Implement violations as constitutional breaches (FR109)
```

### Critical Implementation Notes

**Severity Choice: HIGH**

Emergence violations are constitutional breaches requiring immediate attention:
- Pages on-call immediately
- Does NOT halt system (CRITICAL would halt)
- Aligns with breach severity levels from architecture

**Why Not CRITICAL:**
- CRITICAL = halt system
- Emergence violation is serious but doesn't threaten system integrity
- HIGH = page immediately, investigate promptly

**7-Day Timer Automatic:**

The 7-day escalation timer (FR31) starts automatically when any breach is created via `BreachDeclarationService`. No additional code needed - the existing `EscalationService.check_and_escalate_breaches()` will find unacknowledged breaches.

### Dependencies

**Required Ports (inject via constructor):**
- `BreachDeclarationService` - For breach creation (existing)
- `ProhibitedLanguageBlockingService` - For violation detection (existing)
- `EventQueryProtocol` - For querying blocked events (existing from 9-5)
- `HaltChecker` - For CT-11 halt check (existing)

**Existing Infrastructure to Reuse:**
- `BreachType`, `BreachSeverity` from Story 6.1
- `BreachDeclarationService` from Story 6.1
- `EscalationService` from Story 6.2 (automatic escalation)
- `ProhibitedLanguageBlockingService` from Story 9.1
- `EventQueryProtocol` from Story 9.5

### Project Structure Notes

- Alignment with unified project structure (paths, modules, naming)
- New files follow existing patterns in `src/application/services/`
- No conflicts detected
- Breach integration leverages existing Story 6.1/6.2 infrastructure

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story-9.6] - Story definition
- [Source: _bmad-output/implementation-artifacts/stories/9-5-audit-results-as-events.md] - Previous story patterns
- [Source: src/application/services/breach_declaration_service.py] - Breach infrastructure
- [Source: src/application/services/escalation_service.py] - 7-day escalation
- [Source: src/application/services/prohibited_language_blocking_service.py] - Violation detection
- [Source: src/domain/events/breach.py] - BreachType enum to extend
- [Source: _bmad-output/project-context.md] - Project conventions

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

None - all tests passed first run.

### Completion Notes List

1. Added `EMERGENCE_VIOLATION` to `BreachType` enum with FR55/FR109 docstring
2. Created `EmergenceViolationBreachService` wrapping `BreachDeclarationService`
3. Created `EmergenceViolationOrchestrator` coordinating blocking + breach services
4. Created `EmergenceViolationBreachServiceStub` for test isolation
5. Wrote 30 unit tests covering HALT CHECK FIRST, breach creation, error propagation
6. Wrote 17 integration tests covering end-to-end flow, all services
7. All 47 tests passing
8. Existing error types sufficient - no new errors needed
9. Orchestrator uses deterministic UUID5 for violation_event_id based on content_id

### File List

**Created:**
- `src/application/services/emergence_violation_breach_service.py`
- `src/application/services/emergence_violation_orchestrator.py`
- `src/infrastructure/stubs/emergence_violation_breach_service_stub.py`
- `tests/unit/application/test_emergence_violation_breach_service.py`
- `tests/unit/application/test_emergence_violation_orchestrator.py`
- `tests/integration/test_violations_as_breaches_integration.py`

**Modified:**
- `src/domain/events/breach.py` - Added EMERGENCE_VIOLATION to BreachType enum
- `src/application/services/__init__.py` - Exported new services and constants
- `src/infrastructure/stubs/__init__.py` - Exported new stub

