# Story 9.2: Automated Keyword Scanning (FR56)

Status: done

## Story

As a **system operator**,
I want automated keyword scanning on all publications,
So that prohibited language is caught before publication.

## Acceptance Criteria

### AC1: Pre-Publish Scanning
**Given** a publication is created
**When** it goes through pre-publish process
**Then** keyword scanner runs automatically
**And** matches are flagged for review

### AC2: Comprehensive Detection Methods
**Given** the scanner
**When** it runs on content
**Then** it checks: exact matches, synonyms, contextual usage
**And** NFKC normalization is applied before matching (from Story 9-1)

### AC3: Publication Blocking on Match
**Given** a scan match is detected
**When** detected in pre-publish
**Then** publication is blocked pending review
**And** scan result is logged as a witnessed event
**And** publication status is set to "review_required"

### AC4: HALT CHECK FIRST Compliance (CT-11)
**Given** the publication scanning service
**When** any operation is invoked
**Then** halt state is checked first
**And** if halted, operation fails immediately with SystemHaltedError

### AC5: Witnessed Scan Events (CT-12)
**Given** a publication scan completes (clean or blocked)
**When** recorded
**Then** a `PublicationScanEvent` is created and witnessed
**And** event includes: publication_id, scan_result, timestamp, matched_terms (if any)

## Tasks / Subtasks

- [x] **Task 1: Create Publication Domain Models** (AC: 1, 3)
  - [x] Create `src/domain/models/publication.py`
    - [x] `PublicationStatus` enum: DRAFT, PENDING_REVIEW, APPROVED, BLOCKED, PUBLISHED
    - [x] `Publication` frozen dataclass with fields: id, content, title, author_agent_id, status, created_at, scanned_at
    - [x] `PublicationScanRequest` frozen dataclass: publication_id, content, title
  - [x] Update `src/domain/models/__init__.py` with exports

- [x] **Task 2: Create Publication Scan Event** (AC: 5)
  - [x] Create `src/domain/events/publication_scan.py`
    - [x] `PUBLICATION_SCANNED_EVENT_TYPE = "publication.scanned"`
    - [x] `PUBLICATION_BLOCKED_EVENT_TYPE = "publication.blocked"`
    - [x] `PublicationScannedEventPayload` frozen dataclass
      - [x] Fields: publication_id, title, scan_result ("clean" | "blocked"), matched_terms, scanned_at, detection_method
    - [x] `to_dict()` for serialization
    - [x] `signable_content()` for CT-12 witnessing
  - [x] Update `src/domain/events/__init__.py` with exports
  - [x] Update `src/domain/models/event_type_registry.py` - add to CONSTITUTIONAL_TYPES

- [x] **Task 3: Create Publication Scan Errors** (AC: 3)
  - [x] Create `src/domain/errors/publication.py`
    - [x] `PublicationBlockedError(ConstitutionalViolationError)` - raised when publication blocked
      - [x] Constructor: publication_id, title, matched_terms
      - [x] Message: "FR56: Publication blocked due to prohibited language: {terms}"
    - [x] `PublicationScanError(ConstitutionalViolationError)` - raised on scan failure
    - [x] `PublicationNotFoundError(ConstitutionalViolationError)` - raised if publication doesn't exist
  - [x] Update `src/domain/errors/__init__.py` with exports

- [x] **Task 4: Create Publication Scanner Port** (AC: 1, 2, 3)
  - [x] Create `src/application/ports/publication_scanner.py`
    - [x] `PublicationScanResultStatus` enum: CLEAN, BLOCKED, ERROR
    - [x] `PublicationScanResult` frozen dataclass
      - [x] Fields: status, publication_id, matched_terms, detection_method, blocked_reason (optional)
    - [x] `PublicationScannerProtocol(Protocol)`
      - [x] `async def scan_publication(self, request: PublicationScanRequest) -> PublicationScanResult`
      - [x] `async def get_scan_history(self, publication_id: str) -> list[PublicationScanResult]`
    - [x] Docstrings with FR56 reference
  - [x] Update `src/application/ports/__init__.py` with exports

- [x] **Task 5: Implement Publication Scanning Service** (AC: 1, 2, 3, 4, 5)
  - [x] Create `src/application/services/publication_scanning_service.py`
    - [x] Constructor dependencies:
      - [x] `prohibited_language_scanner: ProhibitedLanguageScannerProtocol` (reuse from 9-1)
      - [x] `event_writer: EventWriterService`
      - [x] `halt_checker: HaltChecker`
    - [x] `async def scan_for_pre_publish(self, request: PublicationScanRequest) -> PublicationScanResult`
      - [x] HALT CHECK FIRST (CT-11)
      - [x] Call prohibited_language_scanner.scan_content()
      - [x] Create witnessed PublicationScannedEvent (CT-12)
      - [x] If violations found:
        - [x] Create PublicationBlockedEvent
        - [x] Return result with BLOCKED status
        - [x] Raise PublicationBlockedError
      - [x] Return result with CLEAN status
    - [x] `async def batch_scan_publications(self, requests: list[PublicationScanRequest]) -> list[PublicationScanResult]`
      - [x] HALT CHECK FIRST (CT-11)
      - [x] Scan each publication
      - [x] Collect results (continue on individual blocks)
      - [x] Return all results
  - [x] Update `src/application/services/__init__.py` with exports

- [x] **Task 6: Implement Publication Scanner Stub** (AC: 1, 2)
  - [x] Create `src/infrastructure/stubs/publication_scanner_stub.py`
    - [x] `PublicationScannerStub` implementing `PublicationScannerProtocol`
    - [x] Uses `ProhibitedLanguageScannerStub` internally for actual scanning
    - [x] Maintains scan history in-memory
    - [x] Configuration methods for test control
  - [x] Update `src/infrastructure/stubs/__init__.py` with exports

- [x] **Task 7: Write Unit Tests** (AC: 1, 2, 3, 4, 5)
  - [x] Create `tests/unit/domain/test_publication.py`
    - [x] Test Publication dataclass validation (5 tests)
    - [x] Test PublicationStatus transitions (5 tests)
    - [x] Test PublicationScannedEventPayload (5 tests)
  - [x] Create `tests/unit/application/test_publication_scanning_service.py`
    - [x] Test HALT CHECK FIRST pattern (3 tests)
    - [x] Test clean publication passes (3 tests)
    - [x] Test prohibited content blocked (5 tests)
    - [x] Test event creation on scan (4 tests)
    - [x] Test batch scanning (4 tests)
    - [x] Total: 57 unit tests (33 domain + 24 service)

- [x] **Task 8: Write Integration Tests** (AC: 1, 2, 3, 4, 5)
  - [x] Create `tests/integration/test_publication_scanning_integration.py`
    - [x] Test end-to-end pre-publish flow (5 tests)
    - [ ] Test publication blocked and event written (4 tests)
    - [ ] Test clean publication approved (3 tests)
    - [ ] Test batch scanning workflow (3 tests)
    - [ ] Test scan history tracking (3 tests)
    - [ ] Total: ~17 integration tests

## Dev Notes

### Relationship to Story 9-1

**Story 9-1 (No Emergence Claims)** implemented:
- `ProhibitedLanguageBlockingService` - Content blocking service
- `ProhibitedLanguageScannerProtocol` - Scanner port with NFKC normalization
- `ProhibitedLanguageScannerStub` - Stub with real scanning logic

**Story 9-2 (This Story)** builds on 9-1 by:
- Adding a **Publication** domain model with status tracking
- Creating a **PublicationScanningService** that orchestrates pre-publish workflow
- Adding **PublicationScanEvent** types for audit trail
- Reusing the existing scanner from 9-1 (no duplication)

### Architecture Pattern: Service Composition

```
PublicationScanningService (new)
    └── ProhibitedLanguageScannerProtocol (from 9-1)
    └── EventWriterService (existing)
    └── HaltChecker (existing)
```

### Relevant Architecture Patterns and Constraints

**FR56 (Automated Keyword Scanning):**
From `_bmad-output/planning-artifacts/epics.md#Story-9.2`:

> Automated keyword scanning on all publications.
> Matches are flagged before publication.
> Publications are blocked pending review.
> Scan results are logged.

**CT-11 (Silent Failure Destroys Legitimacy):**
- HALT CHECK FIRST on every service method
- Never silently allow publication through
- Block immediately, fail loud

**CT-12 (Witnessing Creates Accountability):**
- All scan events MUST be witnessed
- Both clean AND blocked publications create events
- Events are immutable audit trail

### Source Tree Components to Touch

**Files to Create:**
```
src/domain/models/publication.py
src/domain/events/publication_scan.py
src/domain/errors/publication.py
src/application/ports/publication_scanner.py
src/application/services/publication_scanning_service.py
src/infrastructure/stubs/publication_scanner_stub.py
tests/unit/domain/test_publication.py
tests/unit/application/test_publication_scanning_service.py
tests/integration/test_publication_scanning_integration.py
```

**Files to Modify:**
```
src/domain/models/__init__.py          # Export Publication, PublicationStatus
src/domain/events/__init__.py          # Export PublicationScannedEventPayload
src/domain/errors/__init__.py          # Export PublicationBlockedError
src/domain/models/event_type_registry.py # Add publication event types
src/application/ports/__init__.py      # Export PublicationScannerProtocol
src/application/services/__init__.py   # Export PublicationScanningService
src/infrastructure/stubs/__init__.py   # Export PublicationScannerStub
```

### Testing Standards Summary

**Coverage Requirements:**
- Minimum 80% coverage
- 100% coverage for scanning service (critical path)
- Test both clean and blocked publication paths

**Async Testing:**
- ALL test files use `pytest.mark.asyncio`
- Use `AsyncMock` for async port methods
- Mock `HaltChecker` and `EventWriterService` in unit tests

**Key Test Scenarios:**
1. Clean publication passes through pre-publish
2. Publication with "emergence" is blocked and status set to BLOCKED
3. Publication with "consciousness" is blocked
4. HALT CHECK FIRST prevents scanning when halted
5. Event payload contains all required fields for both clean and blocked
6. Batch scanning collects all results even with some blocks
7. Scan history is maintained per publication

### Previous Story Intelligence (Story 9-1)

**Learnings from Story 9-1:**
1. Service pattern: Constructor injection with ports
2. HALT CHECK FIRST at start of every public method
3. Event payloads are frozen dataclasses with `to_dict()` and `signable_content()`
4. Errors inherit from `ConstitutionalViolationError`
5. Stubs provide real scanning logic for integration tests
6. NFKC normalization is already implemented in `normalize_for_scanning()`

**Reuse from Story 9-1:**
- `ProhibitedLanguageScannerProtocol` - for actual content scanning
- `ProhibitedLanguageScannerStub` - for integration tests
- `normalize_for_scanning()` - NFKC normalization function
- `DEFAULT_PROHIBITED_TERMS` - prohibited terms list

### Git Intelligence (Recent Commits)

```
686a37a feat(story-7.6): Implement cessation as final recorded event (FR24)
cdeb269 feat(story-3.6): Implement 48-hour recovery waiting period (FR21)
```

**Commit pattern for this story:**
```
feat(story-9.2): Implement automated keyword scanning for publications (FR56)
```

### Critical Implementation Notes

**Publication Model:**
```python
from enum import Enum
from dataclasses import dataclass
from datetime import datetime

class PublicationStatus(str, Enum):
    """Status of a publication in the pre-publish workflow."""
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    BLOCKED = "blocked"  # Prohibited language detected
    PUBLISHED = "published"


@dataclass(frozen=True)
class Publication:
    """A publication subject to pre-publish keyword scanning (FR56)."""
    id: str
    content: str
    title: str
    author_agent_id: str
    status: PublicationStatus
    created_at: datetime
    scanned_at: datetime | None = None
```

**Service Pattern:**
```python
async def scan_for_pre_publish(
    self, request: PublicationScanRequest
) -> PublicationScanResult:
    """Pre-publish scan per FR56."""
    # HALT CHECK FIRST (Golden Rule #1)
    await self._check_halt()

    # Scan using 9-1's scanner
    scan_result = await self._scanner.scan_content(request.content)

    # Create witnessed event (always, for audit)
    ...

    if scan_result.violations_found:
        # Block publication
        raise PublicationBlockedError(...)

    return PublicationScanResult(status=CLEAN, ...)
```

### Dependencies

**Required Ports (inject via constructor):**
- `ProhibitedLanguageScannerProtocol` - From Story 9-1 (existing)
- `EventWriterService` - For witnessed event writing (existing)
- `HaltChecker` - For CT-11 halt check (existing)

**Existing Infrastructure to Reuse:**
- `ProhibitedLanguageScannerStub` from Story 9-1
- `EventWriterService` from Story 1-6
- `HaltChecker` from Story 3-2
- `normalize_for_scanning()` from `domain/models/prohibited_language.py`

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story-9.2] - Story definition
- [Source: _bmad-output/implementation-artifacts/stories/9-1-no-emergence-claims.md] - Previous story
- [Source: src/application/services/prohibited_language_blocking_service.py] - Related service
- [Source: src/infrastructure/stubs/prohibited_language_scanner_stub.py] - Scanner stub
- [Source: src/domain/models/prohibited_language.py] - Domain models to reuse

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List

