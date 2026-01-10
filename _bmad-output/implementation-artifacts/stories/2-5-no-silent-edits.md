# Story 2.5: No Silent Edits (FR13)

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an **external observer**,
I want the published hash to always equal the canonical hash,
So that no one can edit content after recording.

## Acceptance Criteria

### AC1: Hash Equality on Publish
**Given** content is published to external systems
**When** I compare published hash to event store hash
**Then** they are identical

### AC2: Silent Edit Detection and Block
**Given** an attempt to publish content that differs from recorded content
**When** the publish operation executes
**Then** the hash mismatch is detected
**And** publish is blocked
**And** error includes "FR13: Silent edit detected - hash mismatch"

### AC3: Verification Endpoint
**Given** the verification endpoint
**When** I call `verify_content(content_id)`
**Then** it returns TRUE if hashes match, FALSE otherwise
**And** hash values are included in response

## Tasks / Subtasks

- [x] Task 1: Create FR13ViolationError Domain Error (AC: 2) - ~4 tests
  - [x] 1.1 Create `src/domain/errors/silent_edit.py`
  - [x] 1.2 Define `FR13ViolationError` inheriting from `ConstitutionalViolationError`
  - [x] 1.3 Follow FR9ViolationError pattern from Story 2.1
  - [x] 1.4 Add to `src/domain/errors/__init__.py` exports
  - [x] 1.5 Add unit tests

- [x] Task 2: Create SilentEditEnforcer Domain Service (AC: 1, 2) - ~10 tests
  - [x] 2.1 Create `src/domain/services/silent_edit_enforcer.py`
  - [x] 2.2 Define `SilentEditEnforcer` class with hash verification methods
  - [x] 2.3 Implement `verify_before_publish(content_id, current_content) -> bool`
  - [x] 2.4 Implement `block_silent_edit(content_id, stored_hash, computed_hash)` raises FR13ViolationError
  - [x] 2.5 Reuse `compute_content_hash()` from `src/domain/events/hash_utils.py`
  - [x] 2.6 Add unit tests

- [x] Task 3: Create ContentVerificationPort Interface (AC: 3) - ~6 tests
  - [x] 3.1 Create `src/application/ports/content_verification.py`
  - [x] 3.2 Define `ContentVerificationPort(Protocol)` with:
    - `get_stored_hash(content_id: UUID) -> Optional[str]`
    - `verify_content(content_id: UUID, content: bytes) -> ContentVerificationResult`
  - [x] 3.3 Define `ContentVerificationResult` dataclass with `matches: bool`, `stored_hash`, `computed_hash`
  - [x] 3.4 Add to `src/application/ports/__init__.py` exports
  - [x] 3.5 Add unit tests

- [x] Task 4: Create ContentVerificationStub Infrastructure (AC: 3) - ~8 tests
  - [x] 4.1 Create `src/infrastructure/stubs/content_verification_stub.py`
  - [x] 4.2 Implement `ContentVerificationStub` with in-memory hash storage
  - [x] 4.3 Follow DEV_MODE_WATERMARK pattern (RT-1/ADR-4)
  - [x] 4.4 Add unit tests

- [x] Task 5: Create PublishService Application Service (AC: 1, 2) - ~8 tests
  - [x] 5.1 Create `src/application/services/publish_service.py`
  - [x] 5.2 Inject: `HaltChecker`, `ContentVerificationPort`, `SilentEditEnforcer`
  - [x] 5.3 Implement `publish_content(content_id, content)` with HALT FIRST pattern
  - [x] 5.4 Verify hash BEFORE any publish operation
  - [x] 5.5 Block on mismatch with FR13ViolationError
  - [x] 5.6 Add unit tests

- [x] Task 6: Integrate with NoPreviewEnforcer (AC: 1, 2) - ~4 tests
  - [x] 6.1 Extend `NoPreviewEnforcer.verify_hash()` to raise `FR13ViolationError` for silent edits
  - [x] 6.2 Ensure FR13 errors are distinct from FR9 errors
  - [x] 6.3 Add integration point in existing view/publish flows
  - [x] 6.4 Add unit tests

- [x] Task 7: FR13 Compliance Integration Tests (AC: 1, 2, 3) - ~10 tests
  - [x] 7.1 Create `tests/integration/test_no_silent_edits_integration.py`
  - [x] 7.2 Test: Publishing content with matching hash succeeds
  - [x] 7.3 Test: Publishing content with mismatched hash is blocked
  - [x] 7.4 Test: FR13ViolationError includes correct error message
  - [x] 7.5 Test: verify_content returns TRUE for matching hashes
  - [x] 7.6 Test: verify_content returns FALSE for mismatched hashes
  - [x] 7.7 Test: Verification result includes both hash values
  - [x] 7.8 Test: HALT state blocks publish operations
  - [x] 7.9 Test: End-to-end publish flow enforces FR13

## Dev Notes

### Critical Architecture Context

**FR13: No Silent Edits**
From the PRD, FR13 states: "Published hash always equals the canonical hash so no one can edit content after recording." This is a fundamental integrity guarantee that external observers depend on for trust.

**Constitutional Truths Honored:**
- **CT-11:** Silent failure destroys legitimacy → Hash mismatches MUST raise errors, never be ignored
- **CT-12:** Witnessing creates accountability → All publish attempts are logged with hash comparison
- **CT-13:** Integrity outranks availability → Better to block publish than serve modified content

### Previous Story Intelligence (Story 2.4)

**Key Learnings from Story 2.4:**
- HALT FIRST pattern enforced throughout (check halt before operations)
- DEV_MODE_WATERMARK pattern for all stubs
- Hexagonal architecture strictly maintained (domain has no infrastructure imports)
- Structured logging with structlog (no print statements or f-strings in logs)
- Total 80 tests created for comprehensive coverage
- Application services use dependency injection for ports

**Existing Code to Reuse:**
- `compute_content_hash()` from `src/domain/events/hash_utils.py` - SHA-256 hashing
- `canonical_json()` from `src/domain/events/hash_utils.py` - Deterministic JSON
- `NoPreviewEnforcer.verify_hash()` from `src/domain/services/no_preview_enforcer.py` - Hash verification pattern
- `FR9ViolationError` pattern from `src/domain/errors/no_preview.py` - Error structure
- `HaltChecker` pattern from `src/application/ports/halt_checker.py` - HALT checking

### Hash Verification Flow

```
1. Content stored → content_hash computed and recorded
2. Publish request received with content_id
3. HALT CHECK (fail fast if halted)
4. Retrieve stored content and hash from event store
5. Compute hash of content being published
6. Compare hashes:
   - Match → Allow publish, log success
   - Mismatch → Block publish, raise FR13ViolationError
7. Return verification result with both hashes
```

### FR13ViolationError Design

```python
class FR13ViolationError(ConstitutionalViolationError):
    """Raised when No Silent Edits constraint (FR13) is violated.

    FR13 violations indicate an attempt to publish content that differs
    from the originally recorded content (hash mismatch).

    This is a CRITICAL constitutional violation - silent edits would
    undermine observer trust and system integrity.
    """
    pass
```

### ContentVerificationResult Design

```python
@dataclass(frozen=True)
class ContentVerificationResult:
    """Result of content hash verification (FR13).

    Attributes:
        matches: True if published hash equals stored hash
        stored_hash: The original hash from event store
        computed_hash: The hash computed from current content
        content_id: The UUID of the content being verified
    """
    matches: bool
    stored_hash: str
    computed_hash: str
    content_id: UUID
```

### Project Structure Notes

**Files to Create:**
```
src/
├── domain/
│   ├── errors/
│   │   └── silent_edit.py           # FR13ViolationError
│   └── services/
│       └── silent_edit_enforcer.py  # SilentEditEnforcer
├── application/
│   ├── ports/
│   │   └── content_verification.py  # ContentVerificationPort
│   └── services/
│       └── publish_service.py       # PublishService
└── infrastructure/
    └── stubs/
        └── content_verification_stub.py  # ContentVerificationStub

tests/
├── unit/
│   ├── domain/
│   │   ├── test_fr13_error.py                # 4 tests
│   │   └── test_silent_edit_enforcer.py      # 10 tests
│   ├── application/
│   │   ├── test_content_verification_port.py # 6 tests
│   │   └── test_publish_service.py           # 8 tests
│   └── infrastructure/
│       └── test_content_verification_stub.py # 8 tests
└── integration/
    └── test_no_silent_edits_integration.py   # 10 tests
```

**Files to Modify:**
```
src/domain/errors/__init__.py            # Add FR13ViolationError export
src/application/ports/__init__.py        # Add ContentVerificationPort export
src/domain/services/no_preview_enforcer.py # Optional: extend for FR13
```

**Alignment with Hexagonal Architecture:**
- Domain layer (`domain/`) has NO infrastructure imports
- Application layer (`application/`) orchestrates domain and uses ports
- Infrastructure layer (`infrastructure/`) implements adapters for ports
- Import boundary enforcement from Story 0-6 MUST be respected

### Testing Standards

Per `project-context.md`:
- ALL test files use `pytest.mark.asyncio`
- Use `async def test_*` for async tests
- Use `AsyncMock` not `Mock` for async functions
- Unit tests in `tests/unit/{module}/test_{name}.py`
- Integration tests in `tests/integration/test_{feature}_integration.py`
- 80% minimum coverage

**Expected Test Count:** ~50 tests total (4+10+6+8+8+4+10)

### Library/Framework Requirements

**Required Dependencies (already installed in Epic 0):**
- `structlog` for logging (NO print statements, NO f-strings in logs)
- `pytest-asyncio` for async testing
- Python 3.10+ compatible (use `Optional[T]` not `T | None`)
- `hashlib` from stdlib for SHA-256

**Do NOT add new dependencies without explicit approval.**

### Logging Pattern

Per `project-context.md`, use structured logging:
```python
import structlog

logger = structlog.get_logger()

# CORRECT
logger.info(
    "content_verified",
    content_id=str(content_id),
    hashes_match=True,
)

logger.warning(
    "silent_edit_blocked",
    content_id=str(content_id),
    stored_hash=stored_hash[:8] + "...",
    computed_hash=computed_hash[:8] + "...",
)

# WRONG - Never do these
print(f"Content: {content_id}")  # No print
logger.info(f"Verified {content_id}")  # No f-strings in logs
```

### Integration with Previous Stories

**Story 2.1 (FR9 - No Preview):**
- FR13 builds on FR9's commit-before-view pattern
- NoPreviewEnforcer already has `verify_hash()` method that can be extended
- Both enforce integrity before access, but FR13 specifically for publish operations

**Story 2.2 (FR10 - 72 Concurrent Agents):**
- Content from 72 agents must maintain hash integrity when published
- No special handling needed - hash verification is content-agnostic

**Story 2.3 (FR11 - Collective Output Irreducibility):**
- Collective outputs have content_hash computed at creation
- FR13 ensures these hashes are verified before external publish

**Story 2.4 (FR12 - Dissent Tracking):**
- Dissent metrics follow same hash integrity patterns
- Publish operations for vote tallies must verify hashes

### Security Considerations

**Tamper Detection:**
- Hash verification prevents post-commit content modification
- All publish attempts logged with hash comparison
- Failed verifications trigger alerts

**Observer Trust:**
- External observers can independently verify published content
- Hash values included in verification response for transparency
- No silent failures - all mismatches are surfaced

**Audit Trail:**
- Every publish attempt is logged
- Hash comparison results are recorded
- FR13 violations are constitutional events

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 2.5: No Silent Edits (FR13)]
- [Source: _bmad-output/project-context.md]
- [Source: _bmad-output/implementation-artifacts/stories/2-4-dissent-tracking-in-vote-tallies.md] - Previous story patterns
- [Source: src/domain/events/hash_utils.py] - compute_content_hash, canonical_json
- [Source: src/domain/services/no_preview_enforcer.py] - verify_hash pattern
- [Source: src/domain/errors/no_preview.py] - FR9ViolationError pattern
- [Source: _bmad-output/planning-artifacts/architecture.md#ADR-001] - Hash rules (SHA-256)

---

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

No debug issues encountered.

### Completion Notes List

- **Task 1 Complete:** Created FR13ViolationError in `src/domain/errors/silent_edit.py`, inheriting from ConstitutionalViolationError. Added to `__init__.py` exports. 4 unit tests pass.

- **Task 2 Complete:** Created SilentEditEnforcer domain service with `register_hash()`, `get_stored_hash()`, `verify_hash()`, `verify_before_publish()`, and `block_silent_edit()` methods. Uses structlog for logging. 10 unit tests pass.

- **Task 3 Complete:** Created ContentVerificationPort protocol and ContentVerificationResult frozen dataclass. Port defines async methods for hash storage and verification. Added to ports `__init__.py`. 7 unit tests pass.

- **Task 4 Complete:** Created ContentVerificationStub with DEV_MODE_WATERMARK pattern. Implements in-memory hash storage and SHA-256 verification. 8 unit tests pass.

- **Task 5 Complete:** Created PublishService with HALT FIRST pattern. Injects HaltChecker and ContentVerificationPort. Blocks publish on hash mismatch with FR13ViolationError. 7 unit tests pass.

- **Task 6 Complete:** Extended NoPreviewEnforcer with `verify_hash_for_publish()` method that raises FR13ViolationError (distinct from FR9). Maintains separation between viewing (FR9) and publish (FR13) contexts. 4 additional tests pass.

- **Task 7 Complete:** Created comprehensive integration tests covering AC1 (hash equality), AC2 (silent edit blocking), AC3 (verification endpoint), HALT behavior, and end-to-end flow. 9 integration tests pass.

**Total Tests Created:** 49 tests (4+10+7+8+7+4+9)
**All Tests Pass:** Yes

### File List

**New Files Created:**
- `src/domain/errors/silent_edit.py`
- `src/domain/services/silent_edit_enforcer.py`
- `src/application/ports/content_verification.py`
- `src/application/services/publish_service.py`
- `src/infrastructure/stubs/content_verification_stub.py`
- `tests/unit/domain/test_fr13_error.py`
- `tests/unit/domain/test_silent_edit_enforcer.py`
- `tests/unit/application/test_content_verification_port.py`
- `tests/unit/application/test_publish_service.py`
- `tests/unit/infrastructure/test_content_verification_stub.py`
- `tests/integration/test_no_silent_edits_integration.py`

**Modified Files:**
- `src/domain/errors/__init__.py` - Added FR13ViolationError export
- `src/application/ports/__init__.py` - Added ContentVerificationPort, ContentVerificationResult exports
- `src/domain/services/no_preview_enforcer.py` - Added verify_hash_for_publish() method
- `tests/unit/domain/test_no_preview_enforcer.py` - Added FR13 integration tests
- `_bmad-output/implementation-artifacts/sprint-status.yaml` - Status updated to review
