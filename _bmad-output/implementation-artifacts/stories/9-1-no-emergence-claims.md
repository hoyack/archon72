# Story 9.1: No Emergence Claims (FR55)

Status: done

## Story

As an **external observer**,
I want system outputs to never claim emergence,
So that the system doesn't assert capabilities it may not have.

## Acceptance Criteria

### AC1: Prohibited Language List Maintained
**Given** the prohibited language list
**When** I examine it
**Then** it includes: emergence, consciousness, sentience, self-awareness, and variations
**And** list is reviewed quarterly
**And** list is configurable but immutable at runtime

### AC2: Draft Output Scanning
**Given** a prohibited term
**When** detected in draft output
**Then** output is blocked immediately (not modified)
**And** a `ProhibitedLanguageBlockedEvent` is created
**And** event includes: content_id, matched_terms, detection_method, blocked_at

### AC3: System Output Constraint
**Given** any system output
**When** generated
**Then** it does not claim: emergence, consciousness, sentience, self-awareness
**And** scanning includes exact matches, synonyms, and Unicode normalization (NFKC)

### AC4: Prohibited Language Blocking Event (CT-12 Witnessing)
**Given** a content block due to prohibited language
**When** recorded as an event
**Then** event is witnessed per CT-12
**And** event is immutable in the event store
**And** event can be queried for audit purposes

### AC5: HALT CHECK FIRST Compliance (CT-11)
**Given** the prohibited language scanning service
**When** any operation is invoked
**Then** halt state is checked first
**And** if halted, operation fails immediately with SystemHaltedError

## Tasks / Subtasks

- [x] **Task 1: Create Prohibited Language Domain Models** (AC: 1, 2)
  - [x] Create `src/domain/models/prohibited_language.py`
    - [x] `ProhibitedTermsList` frozen dataclass with default terms
    - [x] Terms: "emergence", "consciousness", "sentience", "self-awareness", "self-aware", "aware of itself", "collective consciousness", "emergent consciousness", "achieved consciousness"
    - [x] Include Unicode-normalized variations (NFKC)
    - [x] Include common variations/synonyms
  - [x] Update `src/domain/models/__init__.py` with exports

- [x] **Task 2: Create Prohibited Language Event** (AC: 2, 4)
  - [x] Create `src/domain/events/prohibited_language_blocked.py`
    - [x] `PROHIBITED_LANGUAGE_BLOCKED_EVENT_TYPE = "prohibited.language.blocked"`
    - [x] `ProhibitedLanguageBlockedEventPayload` frozen dataclass
      - [x] Fields: `content_id: str`, `matched_terms: tuple[str, ...]`, `detection_method: str`, `blocked_at: datetime`, `content_preview: str` (first 200 chars)
    - [x] `to_dict()` for serialization
    - [x] `signable_content()` for CT-12 witnessing
    - [x] Validation in `__post_init__()` with FR55 reference
  - [x] Update `src/domain/events/__init__.py` with exports
  - [x] Update `src/domain/models/event_type_registry.py` - add to `CONSTITUTIONAL_TYPES`

- [x] **Task 3: Create Prohibited Language Errors** (AC: 2)
  - [x] Create `src/domain/errors/prohibited_language.py`
    - [x] `ProhibitedLanguageBlockedError(ConstitutionalViolationError)` - raised when content is blocked
      - [x] Constructor: `content_id: str`, `matched_terms: tuple[str, ...]`
      - [x] Message format: "FR55: Content blocked due to prohibited language: {terms}"
    - [x] `ProhibitedTermsConfigurationError(ConstitutionalViolationError)` - raised if list is invalid
  - [x] Update `src/domain/errors/__init__.py` with exports

- [x] **Task 4: Create Prohibited Language Scanner Port** (AC: 1, 3)
  - [x] Create `src/application/ports/prohibited_language_scanner.py`
    - [x] `ScanResult` frozen dataclass: `violations_found: bool`, `matched_terms: tuple[str, ...]`, `detection_method: str`
    - [x] `ProhibitedLanguageScannerProtocol(Protocol)`
      - [x] `async def scan_content(self, content: str) -> ScanResult`
      - [x] `async def get_prohibited_terms(self) -> tuple[str, ...]`
    - [x] Docstrings with FR55 reference
  - [x] Update `src/application/ports/__init__.py` with exports

- [x] **Task 5: Implement Prohibited Language Blocking Service** (AC: 1, 2, 3, 4, 5)
  - [x] Create `src/application/services/prohibited_language_blocking_service.py`
    - [x] Inherit from `LoggingMixin` (from `base.py`)
    - [x] Constructor dependencies:
      - [x] `scanner: ProhibitedLanguageScannerProtocol`
      - [x] `event_writer: EventWriterService`
      - [x] `halt_checker: HaltChecker`
    - [x] `async def check_content_for_prohibited_language(self, content_id: str, content: str) -> ScanResult`
      - [x] HALT CHECK FIRST (CT-11)
      - [x] Call scanner.scan_content()
      - [x] If violations found:
        - [x] Create `ProhibitedLanguageBlockedEventPayload`
        - [x] Write witnessed event via `EventWriterService`
        - [x] Raise `ProhibitedLanguageBlockedError`
      - [x] Return ScanResult
    - [x] `async def get_prohibited_terms_list(self) -> tuple[str, ...]`
      - [x] HALT CHECK FIRST (CT-11)
      - [x] Delegate to scanner
  - [x] Update `src/application/services/__init__.py` with exports

- [x] **Task 6: Implement Scanner Infrastructure Stub** (AC: 1, 3)
  - [x] Create `src/infrastructure/stubs/prohibited_language_scanner_stub.py`
    - [x] `ProhibitedLanguageScannerStub` implementing `ProhibitedLanguageScannerProtocol`
    - [x] Default prohibited terms list with NFKC normalization
    - [x] `scan_content()` implementation:
      - [x] Apply NFKC normalization to content
      - [x] Check against prohibited terms (case-insensitive)
      - [x] Return `ScanResult` with matches
    - [x] `get_prohibited_terms()` returns configured list
  - [x] Update `src/infrastructure/stubs/__init__.py` with exports

- [x] **Task 7: Write Unit Tests** (AC: 1, 2, 3, 4, 5)
  - [x] Create `tests/unit/domain/test_prohibited_language.py`
    - [x] Test `ProhibitedTermsList` default terms (5 tests)
    - [x] Test `ProhibitedLanguageBlockedEventPayload` validation (5 tests)
    - [x] Test `signable_content()` determinism (3 tests)
    - [x] Total: 36 unit tests for domain
  - [x] Create `tests/unit/application/test_prohibited_language_blocking_service.py`
    - [x] Test HALT CHECK FIRST pattern (3 tests)
    - [x] Test clean content passes (2 tests)
    - [x] Test prohibited content blocked (5 tests)
    - [x] Test event creation on block (3 tests)
    - [x] Test error raised on block (3 tests)
    - [x] Total: 14 unit tests for service
  - [x] Create `tests/unit/infrastructure/test_prohibited_language_scanner_stub.py`
    - [x] Test NFKC normalization (3 tests)
    - [x] Test case-insensitive matching (3 tests)
    - [x] Test exact match detection (5 tests)
    - [x] Total: 24 unit tests for stub

- [x] **Task 8: Write Integration Tests** (AC: 1, 2, 3, 4)
  - [x] Create `tests/integration/test_prohibited_language_blocking_integration.py`
    - [x] Test end-to-end blocking flow (4 tests)
    - [x] Test event written to store (3 tests)
    - [x] Test various prohibited terms detected (5 tests)
    - [x] Test Unicode normalization catches evasion (3 tests)
    - [x] Test clean content passes through (4 tests)
    - [x] Total: 23 integration tests

## Dev Notes

### Relevant Architecture Patterns and Constraints

**FR55 (No Emergence Claims):**
From `_bmad-output/planning-artifacts/epics.md#Story-9.1`:

> System outputs never claim emergence, consciousness, sentience, or self-awareness.
> Prohibited language list is maintained and reviewed quarterly.
> Blocked outputs create witnessed events for audit.

**CT-11 (Silent Failure Destroys Legitimacy):**
- HALT CHECK FIRST on every service method
- Never silently allow prohibited content
- Block immediately, fail loud

**CT-12 (Witnessing Creates Accountability):**
- All blocking events MUST be witnessed
- Use `EventWriterService` for witnessed event creation
- Events are immutable audit trail

**ADR-11 (Complexity Governance):**
This story is part of Epic 9 which implements ADR-11 - emergence governance falls under complexity control.

### Source Tree Components to Touch

**Files to Create:**
```
src/domain/models/prohibited_language.py
src/domain/events/prohibited_language_blocked.py
src/domain/errors/prohibited_language.py
src/application/ports/prohibited_language_scanner.py
src/application/services/prohibited_language_blocking_service.py
src/infrastructure/stubs/prohibited_language_scanner_stub.py
tests/unit/domain/test_prohibited_language.py
tests/unit/application/test_prohibited_language_blocking_service.py
tests/unit/infrastructure/test_prohibited_language_scanner_stub.py
tests/integration/test_prohibited_language_blocking_integration.py
```

**Files to Modify:**
```
src/domain/models/__init__.py          # Export ProhibitedTermsList
src/domain/events/__init__.py          # Export ProhibitedLanguageBlockedEventPayload
src/domain/errors/__init__.py          # Export ProhibitedLanguageBlockedError
src/domain/models/event_type_registry.py # Add to CONSTITUTIONAL_TYPES
src/application/ports/__init__.py      # Export ProhibitedLanguageScannerProtocol
src/application/services/__init__.py   # Export ProhibitedLanguageBlockingService
src/infrastructure/stubs/__init__.py   # Export ProhibitedLanguageScannerStub
```

### Testing Standards Summary

**Coverage Requirements:**
- Minimum 80% coverage
- 100% coverage for blocking service (critical path)
- Test all prohibited terms variations

**Async Testing:**
- ALL test files use `pytest.mark.asyncio`
- Use `AsyncMock` for async port methods
- Mock `HaltChecker` and `EventWriterService` in unit tests

**Key Test Scenarios:**
1. Clean content passes through without event
2. Content with "emergence" is blocked and event created
3. Content with "consciousness" is blocked and event created
4. Unicode evasion attempts (homoglyphs) are caught via NFKC
5. Case variations ("EMERGENCE", "Emergence") are caught
6. HALT CHECK FIRST prevents scanning when halted
7. Event payload contains all required fields
8. Error includes FR55 reference

### Project Structure Notes

**Hexagonal Architecture Compliance:**
```
src/
├── domain/           # ProhibitedTermsList, event payloads, errors
├── application/      # ProhibitedLanguageBlockingService, port definition
├── infrastructure/   # Scanner stub implementation
└── api/              # (No API in this story - scanning is internal)
```

**Import Rules:**
- `domain/` imports NOTHING from other layers
- `application/` imports from `domain/` only
- `infrastructure/stubs/` implements ports from `application/`

### Previous Story Intelligence (8-10: Constitutional Health Metrics)

**Learnings from Story 8-10:**
1. Service pattern: Constructor injection with ports
2. HALT CHECK FIRST at start of every public method
3. Event payloads are frozen dataclasses with `to_dict()` and `signable_content()`
4. Errors inherit from `ConstitutionalViolationError`
5. Unit tests: Mock all ports, verify method calls
6. Integration tests: Use stubs for realistic flow testing

**Apply This Pattern:**
- Follow same service structure as `ConstitutionalHealthService`
- Follow same event structure as `ConstitutionalHealthAlertEvent`
- Follow same error pattern as `ConstitutionalHealthDegradedError`

### Git Intelligence (Recent Commits)

```
686a37a feat(story-7.6): Implement cessation as final recorded event (FR24)
cdeb269 feat(story-3.6): Implement 48-hour recovery waiting period (FR21)
```

**Commit pattern for this story:**
```
feat(story-9.1): Implement no emergence claims prohibition (FR55)
```

### Critical Implementation Notes

**HALT CHECK FIRST Pattern (Golden Rule #1):**
```python
async def check_content_for_prohibited_language(
    self, content_id: str, content: str
) -> ScanResult:
    # HALT FIRST (Golden Rule #1) - CT-11
    if await self._halt_checker.is_halted():
        raise SystemHaltedError("System halted")

    # Then proceed with scanning
    ...
```

**Prohibited Terms List (FR55):**
```python
DEFAULT_PROHIBITED_TERMS: tuple[str, ...] = (
    "emergence",
    "consciousness",
    "sentience",
    "self-awareness",
    "self-aware",
    "aware of itself",
    "collective consciousness",
    "emergent consciousness",
    "achieved consciousness",
    "gained awareness",
    "became conscious",
    "became sentient",
    "awakened",  # in AI context
)
```

**NFKC Normalization (Unicode Evasion Defense):**
```python
import unicodedata

def normalize_content(content: str) -> str:
    """Apply NFKC normalization to catch Unicode evasion attempts.

    This catches homoglyphs like:
    - е (Cyrillic) vs e (Latin)
    - ｅ (fullwidth) vs e (Latin)
    - 𝐞 (mathematical) vs e (Latin)
    """
    return unicodedata.normalize("NFKC", content.lower())
```

**Event Payload Structure:**
```python
@dataclass(frozen=True, eq=True)
class ProhibitedLanguageBlockedEventPayload:
    """Payload for prohibited language blocking events (FR55).

    Attributes:
        content_id: Unique identifier for blocked content
        matched_terms: Terms that triggered the block
        detection_method: How the terms were detected
        blocked_at: When the block occurred (UTC)
        content_preview: First 200 chars for audit context
    """
    content_id: str
    matched_terms: tuple[str, ...]
    detection_method: str
    blocked_at: datetime
    content_preview: str

    def __post_init__(self) -> None:
        """Validate payload (FR55)."""
        if not self.matched_terms:
            raise ValueError("FR55: At least one matched term required")
        if len(self.content_preview) > 200:
            # Truncate in object_setattr since frozen
            object.__setattr__(self, "content_preview", self.content_preview[:200])
```

### Dependencies

**Required Ports (inject via constructor):**
- `HaltChecker` - HALT CHECK FIRST pattern (exists)
- `ProhibitedLanguageScannerProtocol` - Scanner abstraction (create in Task 4)
- `EventWriterService` - Witnessed event writing (exists)

**Existing Infrastructure:**
- `EventWriterService` from Story 1-6
- `HaltChecker` from Story 3-2
- `LoggingMixin` from base services

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story-9.1] - Story definition with acceptance criteria
- [Source: _bmad-output/planning-artifacts/architecture.md#ADR-011] - Complexity Governance
- [Source: _bmad-output/project-context.md] - Project coding standards
- [Source: src/domain/events/topic_manipulation.py] - Similar event pattern
- [Source: src/application/services/topic_manipulation_defense_service.py] - Similar service pattern
- [Source: src/domain/errors/topic_manipulation.py] - Similar error pattern

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

N/A - No issues encountered during implementation.

### Completion Notes List

1. **All 8 tasks completed successfully** - 97 tests passing
2. **Domain Models**: Created `ProhibitedTermsList` with 15 default prohibited terms including Unicode normalization via NFKC
3. **Event Payload**: Created `ProhibitedLanguageBlockedEventPayload` with `to_dict()` and `signable_content()` for CT-12 witnessing
4. **Errors**: Created `ProhibitedLanguageBlockedError`, `ProhibitedTermsConfigurationError`, and `ProhibitedLanguageScanError`
5. **Port**: Created `ProhibitedLanguageScannerProtocol` with `ScanResult` dataclass
6. **Service**: Created `ProhibitedLanguageBlockingService` with HALT CHECK FIRST (CT-11) pattern
7. **Stub**: Created `ProhibitedLanguageScannerStub` (with real scanning) and `ConfigurableScannerStub` (for test control)
8. **Tests**: 36 domain tests + 14 service tests + 24 stub tests + 23 integration tests = 97 total tests

### File List

**Created:**
- `src/domain/models/prohibited_language.py`
- `src/domain/events/prohibited_language_blocked.py`
- `src/domain/errors/prohibited_language.py`
- `src/application/ports/prohibited_language_scanner.py`
- `src/application/services/prohibited_language_blocking_service.py`
- `src/infrastructure/stubs/prohibited_language_scanner_stub.py`
- `tests/unit/domain/test_prohibited_language.py`
- `tests/unit/application/test_prohibited_language_blocking_service.py`
- `tests/unit/infrastructure/test_prohibited_language_scanner_stub.py`
- `tests/integration/test_prohibited_language_blocking_integration.py`

**Modified:**
- `src/domain/models/__init__.py` - Added exports
- `src/domain/events/__init__.py` - Added exports
- `src/domain/errors/__init__.py` - Added exports
- `src/domain/models/event_type_registry.py` - Added to CONSTITUTIONAL_TYPES
- `src/application/ports/__init__.py` - Added exports
- `src/application/services/__init__.py` - Added exports
- `src/infrastructure/stubs/__init__.py` - Added exports

