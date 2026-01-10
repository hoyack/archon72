# Story 9.3: Quarterly Material Audit (FR57)

Status: done

## Story

As a **compliance officer**,
I want quarterly audits of all public materials,
So that prohibited language is caught even if it slipped through.

## Acceptance Criteria

### AC1: Quarterly Audit Schedule
**Given** quarterly audit schedule
**When** audit is due
**Then** all public materials are re-scanned
**And** audit results are logged as event

### AC2: Comprehensive Audit Results
**Given** an audit
**When** it completes
**Then** it includes: materials scanned, violations found, remediation status
**And** results are public

### AC3: Violation Flagging and Clock
**Given** a violation found during audit
**When** identified
**Then** material is flagged for remediation
**And** clock starts for Conclave response

### AC4: HALT CHECK FIRST Compliance (CT-11)
**Given** the quarterly audit service
**When** any operation is invoked
**Then** halt state is checked first
**And** if halted, operation fails immediately with SystemHaltedError

### AC5: Witnessed Audit Events (CT-12)
**Given** an audit completes (clean or with violations)
**When** recorded
**Then** an `AuditCompletedEvent` is created and witnessed
**And** event includes: audit_id, quarter, materials_scanned, violations_found, status

## Tasks / Subtasks

- [ ] **Task 1: Create Audit Domain Models** (AC: 1, 2, 3)
  - [ ] Create `src/domain/models/material_audit.py`
    - [ ] `AuditStatus` enum: SCHEDULED, IN_PROGRESS, COMPLETED, FAILED
    - [ ] `AuditQuarter` frozen dataclass: year (int), quarter (1-4)
    - [ ] `MaterialAudit` frozen dataclass with fields:
      - [ ] `audit_id: str` - Unique identifier (format: `audit-YYYY-Q#`)
      - [ ] `quarter: AuditQuarter` - Which quarter this audit covers
      - [ ] `status: AuditStatus` - Current audit status
      - [ ] `materials_scanned: int` - Count of materials scanned
      - [ ] `violations_found: int` - Count of violations detected
      - [ ] `violation_details: tuple[MaterialViolation, ...]` - Detailed violation records
      - [ ] `started_at: datetime` - When audit started
      - [ ] `completed_at: datetime | None` - When audit completed
      - [ ] `remediation_deadline: datetime | None` - Calculated from completion
    - [ ] `MaterialViolation` frozen dataclass:
      - [ ] `material_id: str` - ID of violating material
      - [ ] `material_type: str` - Type of material (publication, document, etc.)
      - [ ] `matched_terms: tuple[str, ...]` - Terms detected
      - [ ] `flagged_at: datetime` - When flagged
      - [ ] `remediation_status: RemediationStatus` - Current remediation state
    - [ ] `RemediationStatus` enum: PENDING, IN_PROGRESS, RESOLVED, WAIVED
  - [ ] Update `src/domain/models/__init__.py` with exports

- [ ] **Task 2: Create Audit Events** (AC: 5)
  - [ ] Create `src/domain/events/audit.py`
    - [ ] `AUDIT_STARTED_EVENT_TYPE = "audit.started"`
    - [ ] `AUDIT_COMPLETED_EVENT_TYPE = "audit.completed"`
    - [ ] `MATERIAL_VIOLATION_FLAGGED_EVENT_TYPE = "audit.violation.flagged"`
    - [ ] `AuditStartedEventPayload` frozen dataclass:
      - [ ] Fields: audit_id, quarter, scheduled_at, started_at
      - [ ] `to_dict()` for serialization
      - [ ] `signable_content()` for CT-12 witnessing
    - [ ] `AuditCompletedEventPayload` frozen dataclass:
      - [ ] Fields: audit_id, quarter, status, materials_scanned, violations_found, started_at, completed_at, remediation_deadline
      - [ ] `to_dict()` for serialization
      - [ ] `signable_content()` for CT-12 witnessing
    - [ ] `ViolationFlaggedEventPayload` frozen dataclass:
      - [ ] Fields: audit_id, material_id, material_type, matched_terms, flagged_at
      - [ ] `to_dict()` for serialization
      - [ ] `signable_content()` for CT-12 witnessing
  - [ ] Update `src/domain/events/__init__.py` with exports
  - [ ] Update `src/domain/models/event_type_registry.py` - add to CONSTITUTIONAL_TYPES

- [ ] **Task 3: Create Audit Errors** (AC: 3)
  - [ ] Create `src/domain/errors/audit.py`
    - [ ] `AuditError(ConstitutionalViolationError)` - Base audit error
    - [ ] `AuditNotDueError(AuditError)` - Raised when audit not yet due
    - [ ] `AuditInProgressError(AuditError)` - Raised when audit already running
    - [ ] `MaterialViolationError(AuditError)` - Raised when violations found
      - [ ] Constructor: audit_id, violations_count, violation_details
      - [ ] Message: "FR57: Quarterly audit found {count} violations"
  - [ ] Update `src/domain/errors/__init__.py` with exports

- [ ] **Task 4: Create Material Repository Port** (AC: 1, 2)
  - [ ] Create `src/application/ports/material_repository.py`
    - [ ] `Material` frozen dataclass (if not exists):
      - [ ] Fields: material_id, material_type, content, title, published_at
    - [ ] `MaterialRepositoryProtocol(Protocol)`
      - [ ] `async def get_all_public_materials(self) -> list[Material]`
      - [ ] `async def get_materials_by_type(self, material_type: str) -> list[Material]`
      - [ ] `async def get_material_count(self) -> int`
    - [ ] Docstrings with FR57 reference
  - [ ] Update `src/application/ports/__init__.py` with exports

- [ ] **Task 5: Create Audit Repository Port** (AC: 1, 2)
  - [ ] Create `src/application/ports/audit_repository.py`
    - [ ] `AuditRepositoryProtocol(Protocol)`
      - [ ] `async def save_audit(self, audit: MaterialAudit) -> None`
      - [ ] `async def get_audit(self, audit_id: str) -> MaterialAudit | None`
      - [ ] `async def get_latest_audit(self) -> MaterialAudit | None`
      - [ ] `async def get_audit_by_quarter(self, quarter: AuditQuarter) -> MaterialAudit | None`
      - [ ] `async def get_audit_history(self, limit: int = 10) -> list[MaterialAudit]`
      - [ ] `async def is_audit_due(self) -> bool`
    - [ ] Docstrings with FR57 reference
  - [ ] Update `src/application/ports/__init__.py` with exports

- [ ] **Task 6: Implement Quarterly Audit Service** (AC: 1, 2, 3, 4, 5)
  - [ ] Create `src/application/services/quarterly_audit_service.py`
    - [ ] Constructor dependencies:
      - [ ] `material_repository: MaterialRepositoryProtocol`
      - [ ] `audit_repository: AuditRepositoryProtocol`
      - [ ] `publication_scanner: PublicationScannerProtocol` (reuse from 9-2)
      - [ ] `event_writer: EventWriterService`
      - [ ] `halt_checker: HaltChecker`
    - [ ] `async def run_quarterly_audit(self) -> MaterialAudit`
      - [ ] HALT CHECK FIRST (CT-11)
      - [ ] Check if audit is due (error if not)
      - [ ] Create audit record with status IN_PROGRESS
      - [ ] Write AuditStartedEvent (CT-12)
      - [ ] Fetch all public materials
      - [ ] Scan each material using publication_scanner
      - [ ] Collect violations
      - [ ] For each violation: write ViolationFlaggedEvent (CT-12)
      - [ ] Update audit record with results
      - [ ] Write AuditCompletedEvent (CT-12)
      - [ ] Return completed audit
    - [ ] `async def check_audit_due(self) -> bool`
      - [ ] HALT CHECK FIRST (CT-11)
      - [ ] Get latest audit from repository
      - [ ] Calculate if 3 months have passed
      - [ ] Return True if audit is due
    - [ ] `async def get_audit_status(self, audit_id: str) -> MaterialAudit | None`
      - [ ] HALT CHECK FIRST (CT-11)
      - [ ] Retrieve audit from repository
    - [ ] `async def get_audit_history(self, limit: int = 10) -> list[MaterialAudit]`
      - [ ] HALT CHECK FIRST (CT-11)
      - [ ] Retrieve audit history
  - [ ] Update `src/application/services/__init__.py` with exports

- [ ] **Task 7: Implement Audit Repository Stub** (AC: 1, 2)
  - [ ] Create `src/infrastructure/stubs/audit_repository_stub.py`
    - [ ] `AuditRepositoryStub` implementing `AuditRepositoryProtocol`
    - [ ] In-memory storage for audits
    - [ ] Configuration methods for test control:
      - [ ] `set_audit_due(is_due: bool)` - Override due check
      - [ ] `add_audit(audit: MaterialAudit)` - Add test audit
      - [ ] `clear()` - Clear all data
  - [ ] Update `src/infrastructure/stubs/__init__.py` with exports

- [ ] **Task 8: Implement Material Repository Stub** (AC: 1, 2)
  - [ ] Create `src/infrastructure/stubs/material_repository_stub.py`
    - [ ] `MaterialRepositoryStub` implementing `MaterialRepositoryProtocol`
    - [ ] In-memory storage for materials
    - [ ] Configuration methods for test control:
      - [ ] `add_material(material: Material)` - Add test material
      - [ ] `clear()` - Clear all data
  - [ ] Update `src/infrastructure/stubs/__init__.py` with exports

- [ ] **Task 9: Write Unit Tests** (AC: 1, 2, 3, 4, 5)
  - [ ] Create `tests/unit/domain/test_material_audit.py`
    - [ ] Test MaterialAudit dataclass validation (5 tests)
    - [ ] Test AuditQuarter validation (3 tests)
    - [ ] Test AuditStatus transitions (3 tests)
    - [ ] Test MaterialViolation dataclass (3 tests)
    - [ ] Test RemediationStatus enum (2 tests)
  - [ ] Create `tests/unit/domain/test_audit_events.py`
    - [ ] Test AuditStartedEventPayload (5 tests)
    - [ ] Test AuditCompletedEventPayload (5 tests)
    - [ ] Test ViolationFlaggedEventPayload (5 tests)
    - [ ] Test signable_content determinism (3 tests)
  - [ ] Create `tests/unit/application/test_quarterly_audit_service.py`
    - [ ] Test HALT CHECK FIRST pattern (4 tests)
    - [ ] Test audit due check logic (4 tests)
    - [ ] Test clean audit with no violations (3 tests)
    - [ ] Test audit with violations found (5 tests)
    - [ ] Test event creation for all scenarios (5 tests)
    - [ ] Test remediation deadline calculation (3 tests)
  - [ ] Total: ~50 unit tests

- [ ] **Task 10: Write Integration Tests** (AC: 1, 2, 3, 4, 5)
  - [ ] Create `tests/integration/test_quarterly_audit_integration.py`
    - [ ] Test end-to-end quarterly audit workflow (5 tests)
    - [ ] Test audit with violations triggers events (4 tests)
    - [ ] Test audit history tracking (3 tests)
    - [ ] Test remediation deadline is set correctly (3 tests)
    - [ ] Test concurrent audit prevention (2 tests)
    - [ ] Test audit due check across quarters (3 tests)
  - [ ] Total: ~20 integration tests

## Dev Notes

### Relationship to Previous Stories

**Story 9-1 (No Emergence Claims)** implemented:
- `ProhibitedLanguageBlockingService` - Content blocking service
- `ProhibitedLanguageScannerProtocol` - Scanner port with NFKC normalization
- `ProhibitedLanguageScannerStub` - Stub with real scanning logic

**Story 9-2 (Automated Keyword Scanning)** implemented:
- `PublicationScanningService` - Pre-publish scanning workflow
- `PublicationScannerProtocol` - Orchestrates scanning for publications
- `PublicationScannedEventPayload` - Scan event types

**Story 9-3 (This Story)** builds on 9-1 and 9-2 by:
- Adding **MaterialAudit** domain model for tracking quarterly audits
- Creating **QuarterlyAuditService** that uses existing scanner infrastructure
- Adding **AuditCompletedEvent** types for audit audit trail
- Implementing **remediation tracking** with deadlines and status

### Architecture Pattern: Service Composition

```
QuarterlyAuditService (new)
    └── MaterialRepositoryProtocol (new - lists all materials)
    └── AuditRepositoryProtocol (new - tracks audit history)
    └── PublicationScannerProtocol (from 9-2 - reuse scanning)
    └── EventWriterService (existing)
    └── HaltChecker (existing)
```

### Relevant Architecture Patterns and Constraints

**FR57 (Quarterly Material Audit):**
From `_bmad-output/planning-artifacts/epics.md#Story-9.3`:

> Quarterly audits of all public materials.
> All materials are re-scanned.
> Audit results are logged as event.
> Violations flagged for remediation.
> Clock starts for Conclave response.

**CT-11 (Silent Failure Destroys Legitimacy):**
- HALT CHECK FIRST on every service method
- Never silently skip materials
- All errors must be surfaced

**CT-12 (Witnessing Creates Accountability):**
- All audit events MUST be witnessed
- AuditStarted, AuditCompleted, ViolationFlagged events
- Events are immutable audit trail

### Audit Scheduling Logic

**Quarter Calculation:**
- Q1: January 1 - March 31
- Q2: April 1 - June 30
- Q3: July 1 - September 30
- Q4: October 1 - December 31

**Audit Due Check:**
```python
def is_audit_due(last_audit: MaterialAudit | None, now: datetime) -> bool:
    if last_audit is None:
        return True  # First audit is always due

    # Get current quarter
    current_quarter = AuditQuarter(
        year=now.year,
        quarter=(now.month - 1) // 3 + 1
    )

    # Audit is due if:
    # 1. No audit for current quarter
    # 2. Last audit was in previous quarter
    return last_audit.quarter != current_quarter
```

**Remediation Deadline:**
- From FR57: "clock starts for Conclave response"
- Default: 7 days from violation flagging (consistent with breach escalation)

### Source Tree Components to Touch

**Files to Create:**
```
src/domain/models/material_audit.py
src/domain/events/audit.py
src/domain/errors/audit.py
src/application/ports/material_repository.py
src/application/ports/audit_repository.py
src/application/services/quarterly_audit_service.py
src/infrastructure/stubs/audit_repository_stub.py
src/infrastructure/stubs/material_repository_stub.py
tests/unit/domain/test_material_audit.py
tests/unit/domain/test_audit_events.py
tests/unit/application/test_quarterly_audit_service.py
tests/integration/test_quarterly_audit_integration.py
```

**Files to Modify:**
```
src/domain/models/__init__.py          # Export MaterialAudit, AuditQuarter, etc.
src/domain/events/__init__.py          # Export audit event payloads
src/domain/errors/__init__.py          # Export AuditError and subclasses
src/domain/models/event_type_registry.py # Add audit event types
src/application/ports/__init__.py      # Export repository protocols
src/application/services/__init__.py   # Export QuarterlyAuditService
src/infrastructure/stubs/__init__.py   # Export stubs
```

### Testing Standards Summary

**Coverage Requirements:**
- Minimum 80% coverage
- 100% coverage for audit service (critical compliance path)
- Test all quarters and edge cases

**Async Testing:**
- ALL test files use `pytest.mark.asyncio`
- Use `AsyncMock` for async port methods
- Mock `HaltChecker` and `EventWriterService` in unit tests

**Key Test Scenarios:**
1. Quarterly audit runs when due
2. Audit not due returns error
3. Audit with no violations completes cleanly
4. Audit with violations flags each material
5. HALT CHECK FIRST prevents audit when halted
6. All events are written with correct payloads
7. Remediation deadline is calculated correctly
8. Concurrent audit prevention works
9. Audit history is maintained

### Previous Story Intelligence (Story 9-2)

**Learnings from Story 9-2:**
1. Service pattern: Constructor injection with ports
2. HALT CHECK FIRST at start of every public method
3. Event payloads are frozen dataclasses with `to_dict()` and `signable_content()`
4. Errors inherit from `ConstitutionalViolationError`
5. Stubs provide test control methods (configuration for test scenarios)
6. Batch operations collect all results, don't fail on first error

**Reuse from Story 9-2:**
- `PublicationScannerProtocol` - for scanning materials
- `PublicationScanningService` - for actual scanning logic
- `PublicationScanResult` - result structure pattern

### Git Intelligence (Recent Commits)

```
686a37a feat(story-7.6): Implement cessation as final recorded event (FR24)
cdeb269 feat(story-3.6): Implement 48-hour recovery waiting period (FR21)
```

**Commit pattern for this story:**
```
feat(story-9.3): Implement quarterly material audit (FR57)
```

### Critical Implementation Notes

**Audit Model:**
```python
from enum import Enum
from dataclasses import dataclass
from datetime import datetime

class AuditStatus(str, Enum):
    """Status of a quarterly material audit."""
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True)
class AuditQuarter:
    """Quarter identifier for audit scheduling."""
    year: int
    quarter: int  # 1-4

    def __post_init__(self) -> None:
        if not 1 <= self.quarter <= 4:
            raise ValueError("FR57: quarter must be 1-4")

    def __str__(self) -> str:
        return f"{self.year}-Q{self.quarter}"


@dataclass(frozen=True)
class MaterialAudit:
    """A quarterly material audit per FR57."""
    audit_id: str
    quarter: AuditQuarter
    status: AuditStatus
    materials_scanned: int
    violations_found: int
    violation_details: tuple["MaterialViolation", ...]
    started_at: datetime
    completed_at: datetime | None = None
    remediation_deadline: datetime | None = None
```

**Service Pattern:**
```python
async def run_quarterly_audit(self) -> MaterialAudit:
    """Run quarterly audit per FR57."""
    # HALT CHECK FIRST (Golden Rule #1)
    await self._check_halt()

    # Check if audit is due
    if not await self._audit_repository.is_audit_due():
        raise AuditNotDueError("Audit not yet due")

    # Create audit record
    audit = MaterialAudit(
        audit_id=self._generate_audit_id(),
        quarter=self._get_current_quarter(),
        status=AuditStatus.IN_PROGRESS,
        ...
    )

    # Write AuditStartedEvent (CT-12)
    ...

    # Scan all materials
    materials = await self._material_repository.get_all_public_materials()
    violations = []

    for material in materials:
        try:
            await self._scanner.scan_publication(...)
        except PublicationBlockedError as e:
            violations.append(...)
            # Write ViolationFlaggedEvent (CT-12)
            ...

    # Complete audit
    completed_audit = ...

    # Write AuditCompletedEvent (CT-12)
    ...

    return completed_audit
```

### Dependencies

**Required Ports (inject via constructor):**
- `MaterialRepositoryProtocol` - New for this story
- `AuditRepositoryProtocol` - New for this story
- `PublicationScannerProtocol` - From Story 9-2 (existing)
- `EventWriterService` - For witnessed event writing (existing)
- `HaltChecker` - For CT-11 halt check (existing)

**Existing Infrastructure to Reuse:**
- `PublicationScanningService` from Story 9-2
- `EventWriterService` from Story 1-6
- `HaltChecker` from Story 3-2
- `ProhibitedLanguageScannerStub` from Story 9-1

### Project Structure Notes

- Alignment with unified project structure (paths, modules, naming)
- New files follow existing patterns in `src/domain/models/`, `src/application/services/`, etc.
- No conflicts detected

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story-9.3] - Story definition
- [Source: _bmad-output/implementation-artifacts/stories/9-2-automated-keyword-scanning.md] - Previous story
- [Source: src/application/services/publication_scanning_service.py] - Scanner service to reuse
- [Source: src/domain/events/publication_scan.py] - Event pattern to follow
- [Source: _bmad-output/project-context.md] - Project context and rules

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List

