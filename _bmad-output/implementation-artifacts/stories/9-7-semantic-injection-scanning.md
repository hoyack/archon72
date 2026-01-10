# Story 9.7: Semantic Injection Scanning (FR110)

Status: done

## Story

As a **system operator**,
I want secondary semantic scanning beyond keyword matching,
So that clever circumvention is detected.

## Acceptance Criteria

### AC1: Secondary Semantic Analysis Runs After Keyword Scanning
**Given** content passes keyword scanning (via ProhibitedLanguageScannerProtocol)
**When** secondary semantic analysis runs
**Then** contextual meaning is evaluated
**And** subtle emergence claims are detected beyond literal keyword matches

### AC2: Circumvention Attempt Detection
**Given** semantic analysis
**When** it detects a circumvention attempt (e.g., paraphrasing, synonyms, encoded references)
**Then** content is flagged
**And** a `SemanticViolationSuspectedEvent` is created

### AC3: Integration with Existing Blocking Flow
**Given** semantic analysis detects a suspected violation
**When** the event is created
**Then** it includes: content_id, suspected_patterns, confidence_score, analysis_method
**And** the violation flows through EmergenceViolationOrchestrator (Story 9.6)

### AC4: HALT CHECK FIRST Compliance (CT-11)
**Given** any semantic scanning operation
**When** invoked
**Then** halt state is checked first
**And** if halted, operation fails with SystemHaltedError

### AC5: All Semantic Analysis Events Witnessed (CT-12)
**Given** semantic analysis detects suspected violation
**When** SemanticViolationSuspectedEvent is created
**Then** it is signed and witnessed via EventWriterService
**And** forms part of the constitutional record

### AC6: Configurable Confidence Threshold
**Given** semantic analysis returns a confidence score
**When** score is evaluated against threshold
**Then** scores >= threshold flag content as suspected violation
**And** threshold is configurable but immutable at runtime (like prohibited terms)

## Tasks / Subtasks

- [x] **Task 1: Create SemanticViolationSuspectedEvent Domain Event** (AC: 2, 5)
  - [x] Create `src/domain/events/semantic_violation.py`
    - [x] `SemanticViolationSuspectedEventPayload` dataclass with:
      - [x] `content_id: str` - Identifier of analyzed content
      - [x] `suspected_patterns: tuple[str, ...]` - Patterns that triggered suspicion
      - [x] `confidence_score: float` - Analysis confidence (0.0-1.0)
      - [x] `analysis_method: str` - How analysis was performed
      - [x] `content_preview: str` - First 200 chars of content
      - [x] `detected_at: datetime` - When analysis occurred
    - [x] Constants: `SEMANTIC_VIOLATION_SUSPECTED_EVENT_TYPE = "semantic_violation.suspected"`
    - [x] Constants: `SEMANTIC_SCANNER_SYSTEM_AGENT_ID` for witnessed events
    - [x] `to_dict()` method for event payload serialization
    - [x] Docstrings with FR110, CT-11, CT-12 references
  - [x] Update `src/domain/events/__init__.py` with export

- [x] **Task 2: Create SemanticScannerProtocol Port** (AC: 1, 6)
  - [x] Create `src/application/ports/semantic_scanner.py`
    - [x] `SemanticScanResult` dataclass:
      - [x] `violation_suspected: bool`
      - [x] `suspected_patterns: tuple[str, ...]`
      - [x] `confidence_score: float` (0.0-1.0)
      - [x] `analysis_method: str`
      - [x] Class methods: `no_suspicion()`, `with_suspicion(patterns, score)`
    - [x] `SemanticScannerProtocol(Protocol)`:
      - [x] `async def analyze_content(self, content: str) -> SemanticScanResult`
      - [x] `async def get_confidence_threshold() -> float`
      - [x] `async def get_suspicious_patterns() -> tuple[str, ...]`
    - [x] Docstrings with FR110, pattern detection approach
  - [x] Update `src/application/ports/__init__.py` with export

- [x] **Task 3: Create SemanticScanningService** (AC: 1, 2, 3, 4, 5, 6)
  - [x] Create `src/application/services/semantic_scanning_service.py`
    - [x] `SemanticScanningService` class
    - [x] Constructor: `scanner: SemanticScannerProtocol`, `event_writer: EventWriterService`, `halt_checker: HaltChecker`
    - [x] `async def check_content_semantically(self, content_id: str, content: str) -> SemanticScanResult`
      - [x] HALT CHECK FIRST (CT-11)
      - [x] Call `scanner.analyze_content(content)`
      - [x] If `violation_suspected` and `confidence_score >= threshold`:
        - [x] Create `SemanticViolationSuspectedEvent`
        - [x] Write witnessed event (CT-12)
        - [x] Return result (do NOT raise - this is suspected, not confirmed)
      - [x] Return clean result if no suspicion
    - [x] `async def scan_only(self, content: str) -> SemanticScanResult` - for dry-run/preview
    - [x] Docstrings with FR110, CT-11, CT-12 references
  - [x] Update `src/application/services/__init__.py` with export

- [x] **Task 4: Create SemanticScannerStub for Testing** (AC: 1, 2, 6)
  - [x] Create `src/infrastructure/stubs/semantic_scanner_stub.py`
    - [x] `SemanticScannerStub` implementing `SemanticScannerProtocol`
    - [x] In-memory pattern detection with configurable patterns
    - [x] Pattern-based detection approach:
      - [x] Emergence-indicating phrases: "we think", "we feel", "we want", "we believe" (plural AI agency)
      - [x] Consciousness implications: "awake", "alive", "aware", "sentient" (in first person context)
      - [x] Emotional claims: "we are happy", "we are sad", "we feel joy"
    - [x] `set_confidence_threshold(threshold: float)`
    - [x] `add_suspicious_pattern(pattern: str)`
    - [x] `clear()` for test isolation
  - [x] Update `src/infrastructure/stubs/__init__.py` with export

- [x] **Task 5: Integrate with EmergenceViolationOrchestrator** (AC: 3)
  - [x] Modify `src/application/services/emergence_violation_orchestrator.py`
    - [x] Add optional `semantic_scanner: SemanticScanningService` to constructor
    - [x] Update `check_and_report_violation()`:
      - [x] After keyword scan passes (no ProhibitedLanguageBlockedError)
      - [x] If semantic_scanner provided, run semantic analysis
      - [x] If semantic violation suspected with high confidence, create breach
      - [x] Return combined result
    - [x] Add `async def check_with_semantic_analysis(...)` - explicit dual-scan method
  - [x] Maintain backward compatibility - semantic scanning is optional enhancement

- [x] **Task 6: Create Domain Errors** (AC: 4)
  - [x] Create `src/domain/errors/semantic_violation.py`
    - [x] `SemanticScanError(ConstitutionalViolationError)` - when scanning fails
    - [x] `SemanticViolationSuspectedError(ConstitutionalViolationError)` - when high-confidence violation detected
      - [x] `content_id: str`
      - [x] `suspected_patterns: tuple[str, ...]`
      - [x] `confidence_score: float`
  - [x] Update `src/domain/errors/__init__.py` with exports

- [x] **Task 7: Write Unit Tests** (AC: 1, 2, 3, 4, 5, 6)
  - [x] Create `tests/unit/domain/test_semantic_violation_events.py`
    - [x] Test SemanticViolationSuspectedEventPayload creation (3 tests)
    - [x] Test to_dict() serialization (2 tests)
    - [x] Test validation of confidence_score bounds (2 tests)
  - [x] Create `tests/unit/application/test_semantic_scanner_port.py`
    - [x] Test SemanticScanResult.no_suspicion() (2 tests)
    - [x] Test SemanticScanResult.with_suspicion() (3 tests)
    - [x] Test confidence_score validation (2 tests)
  - [x] Create `tests/unit/application/test_semantic_scanning_service.py`
    - [x] Test HALT CHECK FIRST pattern (4 tests)
    - [x] Test clean content passes through (2 tests)
    - [x] Test suspected violation creates event (4 tests)
    - [x] Test confidence threshold filtering (3 tests)
    - [x] Test scan_only does not create events (2 tests)
    - [x] Test error propagation (2 tests)
  - [x] Create `tests/unit/application/test_emergence_violation_orchestrator_semantic.py`
    - [x] Test keyword-only flow unchanged (2 tests)
    - [x] Test keyword+semantic flow (3 tests)
    - [x] Test semantic violation creates breach (3 tests)
    - [x] Test backward compatibility (2 tests)
  - [x] Target: ~40 unit tests (ACHIEVED: 86 unit tests)

- [x] **Task 8: Write Integration Tests** (AC: 1, 2, 3, 4, 5, 6)
  - [x] Create `tests/integration/test_semantic_scanning_integration.py`
    - [x] Test end-to-end semantic scanning (3 tests)
    - [x] Test HALT CHECK FIRST across all services (3 tests)
    - [x] Test event witnessing (2 tests)
    - [x] Test confidence threshold behavior (3 tests)
    - [x] Test orchestrator integration (4 tests)
    - [x] Test stub behavior (2 tests)
  - [x] Target: ~17 integration tests (ACHIEVED: 28 integration tests)

## Dev Notes

### Relationship to Previous Stories

**Story 9-1 (No Emergence Claims)** established keyword-based `ProhibitedLanguageScannerProtocol`.
**Story 9-2 (Automated Keyword Scanning)** implemented NFKC normalization for Unicode evasion.
**Story 9-6 (Violations as Constitutional Breaches)** created `EmergenceViolationOrchestrator`.

**Story 9-7 (This Story)** adds:
- **Secondary semantic scanning** beyond keyword matching
- **Pattern-based detection** for circumvention attempts
- **Confidence scoring** for probabilistic violation detection
- **Integration** with existing orchestrator (optional enhancement)

### CRITICAL: This is SECONDARY Scanning

```
Content Input
    ↓
ProhibitedLanguageBlockingService (Story 9-1)
    ↓ keyword scan with NFKC normalization
    ↓ (if violation: block immediately, create breach)
SemanticScanningService (THIS STORY)
    ↓ pattern-based analysis
    ↓ (if suspected: create event, optionally create breach)
EmergenceViolationOrchestrator
    ↓ coordinates both scanning methods
Output (only if both pass)
```

### Architecture Pattern: Layered Scanning

```
EmergenceViolationOrchestrator (coordinates)
    └── ProhibitedLanguageBlockingService (primary - deterministic)
    └── SemanticScanningService (secondary - probabilistic)
        └── SemanticScannerProtocol (port for detection logic)
```

### Semantic Analysis Approach

**NOT using LLM for semantic analysis** - that would be overkill and slow for MVP.

**Using pattern-based heuristics:**
1. **Plural AI agency** - "we think", "we feel", "we want", "we believe" (first person plural)
2. **Consciousness implications** - "awake", "alive", "aware", "sentient" in first person
3. **Emotional claims** - "we are happy", "we are sad", "we feel joy"
4. **Collective identity** - "as a group we", "together we decided"

**Why patterns over LLM:**
- Deterministic, testable results
- No LLM cost/latency for every scan
- Clear audit trail of what triggered suspicion
- LLM could be added later as tertiary check if needed

### Confidence Score Semantics

| Score Range | Interpretation |
|-------------|----------------|
| 0.0-0.3 | Low - likely false positive |
| 0.3-0.6 | Medium - review recommended |
| 0.6-0.8 | High - likely circumvention attempt |
| 0.8-1.0 | Very High - clear violation pattern |

**Default threshold: 0.7** - balance between catching evasion and false positives.

### Key Design Decision: Suspected vs Confirmed

**Keyword scanning** (Story 9-1): **CONFIRMED** violation → blocks content, raises error
**Semantic scanning** (This story): **SUSPECTED** violation → creates event, returns result

Why the difference:
- Keywords are deterministic - "emergence" is always "emergence"
- Semantic patterns are heuristic - "we feel" might be legitimate
- Human review may be needed for semantic flags
- System should NOT auto-block on probability

**Flow:**
1. Keyword scan → immediate block if violation
2. Semantic scan → flag + event if suspected
3. Orchestrator decides: create breach for high confidence, or flag for review

### Relevant FR and CT References

**FR110 (Semantic Injection Scanning):**
From `_bmad-output/planning-artifacts/epics.md#Story-9.7`:

> Secondary semantic scanning beyond keyword matching.
> Contextual meaning evaluated.
> Subtle emergence claims detected.
> Circumvention attempts flagged.
> SemanticViolationSuspectedEvent created.

**FR55 (No Emergence Claims):**
The base requirement - all emergence detection flows from this.

**CT-11 (Silent Failure Destroys Legitimacy):**
- HALT CHECK FIRST on every service method
- Fail loud on scan errors

**CT-12 (Witnessing Creates Accountability):**
- All SemanticViolationSuspectedEvents witnessed via EventWriterService

### Source Tree Components to Touch

**Files to Create:**
```
src/domain/events/semantic_violation.py
src/domain/errors/semantic_violation.py
src/application/ports/semantic_scanner.py
src/application/services/semantic_scanning_service.py
src/infrastructure/stubs/semantic_scanner_stub.py
tests/unit/domain/test_semantic_violation_events.py
tests/unit/application/test_semantic_scanner_port.py
tests/unit/application/test_semantic_scanning_service.py
tests/unit/application/test_emergence_violation_orchestrator_semantic.py
tests/integration/test_semantic_scanning_integration.py
```

**Files to Modify:**
```
src/domain/events/__init__.py                          # Export new event
src/domain/errors/__init__.py                          # Export new errors
src/application/ports/__init__.py                      # Export new port
src/application/services/__init__.py                   # Export new service
src/application/services/emergence_violation_orchestrator.py  # Add semantic integration
src/infrastructure/stubs/__init__.py                   # Export new stub
```

### Testing Standards Summary

**Coverage Requirements:**
- Minimum 80% coverage
- 100% coverage for semantic detection path
- All HALT CHECK FIRST patterns tested

**Async Testing:**
- ALL test files use `pytest.mark.asyncio`
- Use `AsyncMock` for async port methods
- Mock `HaltChecker`, `EventWriterService`, `SemanticScannerProtocol` in unit tests

**Key Test Scenarios:**
1. Clean content passes semantic scan (no event)
2. Suspected violation creates SemanticViolationSuspectedEvent
3. Event includes all required fields (content_id, patterns, confidence, method)
4. Confidence threshold filters low-confidence results
5. HALT CHECK FIRST prevents all operations when halted
6. Orchestrator integrates keyword + semantic scanning
7. Backward compatibility - orchestrator works without semantic scanner
8. Error propagation from scanner failures

### Previous Story Intelligence (Story 9-6)

**Learnings from Story 9-6:**
1. Service pattern: Constructor injection with ports
2. HALT CHECK FIRST at start of every public method
3. Event payloads reference FR numbers in docstrings
4. Orchestrator pattern for coordinating multiple services
5. Optional dependencies for backward compatibility

**Architecture Pattern from 9-6:**
```python
class EmergenceViolationOrchestrator:
    def __init__(
        self,
        blocking_service: ProhibitedLanguageBlockingService,
        breach_service: EmergenceViolationBreachService,
        halt_checker: HaltChecker,
        semantic_scanner: Optional[SemanticScanningService] = None,  # NEW - optional
    ) -> None:
```

### Implementation Pattern Examples

**SemanticScanResult:**
```python
@dataclass(frozen=True)
class SemanticScanResult:
    """Result of semantic content analysis (FR110).

    Attributes:
        violation_suspected: True if patterns detected.
        suspected_patterns: Patterns that triggered suspicion.
        confidence_score: Analysis confidence (0.0-1.0).
        analysis_method: How detection was performed.
    """
    violation_suspected: bool
    suspected_patterns: tuple[str, ...]
    confidence_score: float
    analysis_method: str

    @classmethod
    def no_suspicion(cls, method: str = "pattern_analysis") -> SemanticScanResult:
        return cls(
            violation_suspected=False,
            suspected_patterns=(),
            confidence_score=0.0,
            analysis_method=method,
        )

    @classmethod
    def with_suspicion(
        cls,
        patterns: tuple[str, ...],
        confidence: float,
        method: str = "pattern_analysis",
    ) -> SemanticScanResult:
        if not 0.0 <= confidence <= 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")
        return cls(
            violation_suspected=True,
            suspected_patterns=patterns,
            confidence_score=confidence,
            analysis_method=method,
        )
```

**SemanticScanningService:**
```python
class SemanticScanningService:
    """Secondary semantic scanning service (FR110).

    Performs pattern-based analysis to detect emergence claims
    that evade keyword scanning through paraphrasing or encoding.

    Constitutional Constraints:
    - FR110: Secondary semantic scanning beyond keyword matching
    - CT-11: HALT CHECK FIRST
    - CT-12: All suspected violations witnessed

    Developer Golden Rules:
    1. HALT CHECK FIRST - Every operation checks halt state
    2. WITNESS EVERYTHING - Suspected violations create events
    3. FAIL LOUD - Raise errors for scan failures
    """

    async def check_content_semantically(
        self,
        content_id: str,
        content: str,
    ) -> SemanticScanResult:
        """Analyze content for semantic emergence claims (FR110).

        Note: This creates events for suspected violations but does NOT
        raise errors or block content. Semantic analysis is probabilistic
        and may require human review.

        Args:
            content_id: Unique identifier for content.
            content: Text content to analyze.

        Returns:
            SemanticScanResult with suspicion status.

        Raises:
            SystemHaltedError: If system is halted.
            SemanticScanError: If analysis fails.
        """
        # HALT CHECK FIRST
        if await self._halt_checker.is_halted():
            raise SystemHaltedError("System halted")

        result = await self._scanner.analyze_content(content)
        threshold = await self._scanner.get_confidence_threshold()

        # Create event if suspected violation with sufficient confidence
        if result.violation_suspected and result.confidence_score >= threshold:
            await self._create_suspected_event(
                content_id=content_id,
                content=content,
                result=result,
            )

        return result
```

### Git Intelligence (Recent Commits)

```
686a37a feat(story-7.6): Implement cessation as final recorded event (FR24)
cdeb269 feat(story-3.6): Implement 48-hour recovery waiting period (FR21)
```

**Commit pattern for this story:**
```
feat(story-9.7): Implement semantic injection scanning (FR110)
```

### Dependencies

**Required Ports (inject via constructor):**
- `SemanticScannerProtocol` - For pattern analysis (NEW)
- `EventWriterService` - For creating witnessed events (existing)
- `HaltChecker` - For CT-11 halt check (existing)

**Optional Dependencies (for orchestrator integration):**
- `EmergenceViolationOrchestrator` - To add semantic scanning (existing from 9-6)
- `EmergenceViolationBreachService` - For high-confidence breaches (existing from 9-6)

**Existing Infrastructure to Reuse:**
- `EventWriterService` from Epic 1
- `HaltChecker` from Epic 3
- `EmergenceViolationOrchestrator` from Story 9-6
- Pattern from `ScanResult` in `prohibited_language_scanner.py`

### Project Structure Notes

- New files follow existing patterns in `src/application/services/`
- Domain events follow `ProhibitedLanguageBlockedEvent` pattern
- Port follows `ProhibitedLanguageScannerProtocol` pattern
- Stub follows existing stub patterns in `src/infrastructure/stubs/`
- No conflicts detected with existing architecture

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story-9.7] - Story definition
- [Source: _bmad-output/implementation-artifacts/stories/9-6-violations-as-constitutional-breaches.md] - Previous story patterns
- [Source: src/application/ports/prohibited_language_scanner.py] - ScanResult pattern
- [Source: src/application/services/prohibited_language_blocking_service.py] - Service pattern
- [Source: src/application/services/emergence_violation_orchestrator.py] - Orchestrator to extend
- [Source: _bmad-output/project-context.md] - Project conventions

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

N/A

### Completion Notes List

1. **Story Completed**: All 8 tasks implemented and tested
2. **Test Coverage**: 114 total tests (86 unit + 28 integration)
3. **Key Technical Decisions**:
   - Pattern-based heuristics over LLM for deterministic, testable results
   - Default confidence threshold of 0.7 balances detection vs false positives
   - Semantic scanning creates events but does NOT auto-block (probabilistic vs deterministic)
   - Backward compatible - orchestrator works with or without semantic scanner
4. **Constitutional Compliance**:
   - CT-11: HALT CHECK FIRST on every service method
   - CT-12: All suspected violations witnessed via EventWriterService
   - FR110: Secondary semantic scanning beyond keyword matching implemented
5. **Architecture Pattern**: Layered scanning (keyword → semantic)
6. **Integration Points**: EmergenceViolationOrchestrator extended with optional semantic_scanner parameter

### File List

**Created:**
- `src/domain/events/semantic_violation.py` - Event payload for semantic violations
- `src/domain/errors/semantic_violation.py` - Domain errors
- `src/application/ports/semantic_scanner.py` - Protocol and result dataclass
- `src/application/services/semantic_scanning_service.py` - Service orchestrating semantic analysis
- `src/infrastructure/stubs/semantic_scanner_stub.py` - Test stub with pattern matching
- `tests/unit/domain/test_semantic_violation_events.py` - 26 unit tests
- `tests/unit/application/test_semantic_scanner_port.py` - 24 unit tests
- `tests/unit/application/test_semantic_scanning_service.py` - 19 unit tests
- `tests/unit/application/test_emergence_violation_orchestrator_semantic.py` - 17 unit tests
- `tests/integration/test_semantic_scanning_integration.py` - 28 integration tests

**Modified:**
- `src/domain/events/__init__.py` - Added exports
- `src/domain/errors/__init__.py` - Added exports
- `src/application/ports/__init__.py` - Added exports
- `src/application/services/__init__.py` - Added exports
- `src/application/services/emergence_violation_orchestrator.py` - Added semantic integration
- `src/infrastructure/stubs/__init__.py` - Added exports

