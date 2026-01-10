# Story 9.4: User Content Prohibition (FR58)

Status: done

## Story

As a **system operator**,
I want curated/featured user content subject to same prohibition,
So that user content doesn't bypass the rules.

## Acceptance Criteria

### AC1: Featured Content Scanning
**Given** user content is featured or curated
**When** it is selected for prominence
**Then** keyword scanning applies
**And** prohibited content is not featured

### AC2: Prohibited Content Flagging (Not Deletion)
**Given** user content
**When** it contains prohibited language
**Then** it is NOT deleted (user's content remains theirs)
**And** but it cannot be featured or curated
**And** a prohibition flag is added to the content

### AC3: HALT CHECK FIRST Compliance (CT-11)
**Given** the user content prohibition service
**When** any operation is invoked
**Then** halt state is checked first
**And** if halted, operation fails immediately with SystemHaltedError

### AC4: Witnessed Prohibition Events (CT-12)
**Given** a user content is evaluated for featuring
**When** it contains prohibited language
**Then** a `UserContentProhibitionEvent` is created and witnessed
**And** event includes: content_id, owner_id, matched_terms, action_taken (flag_not_feature)
**And** a clean content check creates a `UserContentClearedEvent`

### AC5: Content Status Tracking
**Given** user content with prohibition flag
**When** querying content status
**Then** the prohibition status is returned
**And** the flag includes: flagged_at, matched_terms, can_be_featured (false)

## Tasks / Subtasks

- [x] **Task 1: Create User Content Domain Models** (AC: 1, 2, 5)
  - [ ] Create `src/domain/models/user_content.py`
    - [ ] `UserContentStatus` enum: ACTIVE, FLAGGED, REMOVED
    - [ ] `FeaturedStatus` enum: NOT_FEATURED, PENDING_REVIEW, FEATURED, PROHIBITED
    - [ ] `UserContentProhibitionFlag` frozen dataclass:
      - [ ] `flagged_at: datetime` - When content was flagged
      - [ ] `matched_terms: tuple[str, ...]` - Terms detected
      - [ ] `can_be_featured: bool` - Always False when flagged
      - [ ] `reviewed_by: str | None` - Agent/system that flagged
    - [ ] `UserContent` frozen dataclass:
      - [ ] `content_id: str` - Unique identifier
      - [ ] `owner_id: str` - User who owns the content
      - [ ] `content: str` - The actual content text
      - [ ] `title: str` - Content title
      - [ ] `status: UserContentStatus` - Current status
      - [ ] `featured_status: FeaturedStatus` - Featured eligibility
      - [ ] `prohibition_flag: UserContentProhibitionFlag | None` - Flag if prohibited
      - [ ] `created_at: datetime` - When content was created
    - [ ] `FeatureRequest` frozen dataclass:
      - [ ] `content_id: str`, `owner_id: str`, `content: str`, `title: str`
  - [ ] Update `src/domain/models/__init__.py` with exports

- [x] **Task 2: Create User Content Prohibition Events** (AC: 4)
  - [ ] Create `src/domain/events/user_content_prohibition.py`
    - [ ] `USER_CONTENT_PROHIBITED_EVENT_TYPE = "user_content.prohibited"`
    - [ ] `USER_CONTENT_CLEARED_EVENT_TYPE = "user_content.cleared"`
    - [ ] `USER_CONTENT_SCANNER_SYSTEM_AGENT_ID = "system:user_content_scanner"`
    - [ ] `UserContentProhibitionEventPayload` frozen dataclass:
      - [ ] Fields: content_id, owner_id, title, matched_terms, action_taken, flagged_at
      - [ ] `to_dict()` for serialization
      - [ ] `signable_content()` for CT-12 witnessing
    - [ ] `UserContentClearedEventPayload` frozen dataclass:
      - [ ] Fields: content_id, owner_id, title, scanned_at, detection_method
      - [ ] `to_dict()` for serialization
      - [ ] `signable_content()` for CT-12 witnessing
  - [ ] Update `src/domain/events/__init__.py` with exports
  - [ ] Update `src/domain/models/event_type_registry.py` - add to CONSTITUTIONAL_TYPES

- [x] **Task 3: Create User Content Prohibition Errors** (AC: 2)
  - [ ] Create `src/domain/errors/user_content.py`
    - [ ] `UserContentProhibitionError(ConstitutionalViolationError)` - Base error
    - [ ] `UserContentCannotBeFeaturedException(UserContentProhibitionError)`
      - [ ] Constructor: content_id, owner_id, matched_terms
      - [ ] Message: "FR58: User content cannot be featured due to prohibited language: {terms}"
    - [ ] `UserContentNotFoundError(UserContentProhibitionError)` - Content doesn't exist
  - [ ] Update `src/domain/errors/__init__.py` with exports

- [x] **Task 4: Create User Content Repository Port** (AC: 1, 2, 5)
  - [ ] Create `src/application/ports/user_content_repository.py`
    - [ ] `UserContentRepositoryProtocol(Protocol)`
      - [ ] `async def get_content(self, content_id: str) -> UserContent | None`
      - [ ] `async def save_content(self, content: UserContent) -> None`
      - [ ] `async def update_prohibition_flag(self, content_id: str, flag: UserContentProhibitionFlag) -> None`
      - [ ] `async def update_featured_status(self, content_id: str, status: FeaturedStatus) -> None`
      - [ ] `async def get_featured_candidates(self) -> list[UserContent]`
      - [ ] `async def get_prohibited_content(self) -> list[UserContent]`
    - [ ] Docstrings with FR58 reference
  - [ ] Update `src/application/ports/__init__.py` with exports

- [x] **Task 5: Implement User Content Prohibition Service** (AC: 1, 2, 3, 4, 5)
  - [ ] Create `src/application/services/user_content_prohibition_service.py`
    - [ ] Constructor dependencies:
      - [ ] `content_repository: UserContentRepositoryProtocol`
      - [ ] `prohibited_language_scanner: ProhibitedLanguageScannerProtocol` (reuse from 9-1)
      - [ ] `event_writer: EventWriterService`
      - [ ] `halt_checker: HaltChecker`
    - [ ] `async def evaluate_for_featuring(self, request: FeatureRequest) -> UserContent`
      - [ ] HALT CHECK FIRST (CT-11)
      - [ ] Scan content using prohibited_language_scanner
      - [ ] If clean:
        - [ ] Write UserContentClearedEvent (CT-12)
        - [ ] Return content with featured_status = PENDING_REVIEW
      - [ ] If violations found:
        - [ ] Create prohibition flag (DO NOT DELETE content)
        - [ ] Update content with flag
        - [ ] Write UserContentProhibitionEvent (CT-12)
        - [ ] Return content with featured_status = PROHIBITED
        - [ ] Raise UserContentCannotBeFeaturedException
    - [ ] `async def batch_evaluate_for_featuring(self, requests: list[FeatureRequest]) -> list[UserContent]`
      - [ ] HALT CHECK FIRST (CT-11)
      - [ ] Evaluate each request
      - [ ] Collect results (continue on individual prohibitions)
      - [ ] Return all results
    - [ ] `async def get_content_prohibition_status(self, content_id: str) -> UserContentProhibitionFlag | None`
      - [ ] HALT CHECK FIRST (CT-11)
      - [ ] Get content from repository
      - [ ] Return prohibition flag if exists
    - [ ] `async def clear_prohibition_flag(self, content_id: str, reason: str) -> UserContent`
      - [ ] HALT CHECK FIRST (CT-11)
      - [ ] Only for admin/manual review override
      - [ ] Must be witnessed (CT-12)
  - [ ] Update `src/application/services/__init__.py` with exports

- [x] **Task 6: Implement User Content Repository Stub** (AC: 1, 2, 5)
  - [ ] Create `src/infrastructure/stubs/user_content_repository_stub.py`
    - [ ] `UserContentRepositoryStub` implementing `UserContentRepositoryProtocol`
    - [ ] In-memory storage for content
    - [ ] Configuration methods for test control:
      - [ ] `add_content(content: UserContent)` - Add test content
      - [ ] `clear()` - Clear all data
      - [ ] `set_content_prohibited(content_id: str, flag: UserContentProhibitionFlag)` - Set flag
  - [ ] Update `src/infrastructure/stubs/__init__.py` with exports

- [x] **Task 7: Write Unit Tests** (AC: 1, 2, 3, 4, 5)
  - [ ] Create `tests/unit/domain/test_user_content.py`
    - [ ] Test UserContent dataclass validation (5 tests)
    - [ ] Test UserContentStatus enum (3 tests)
    - [ ] Test FeaturedStatus enum (3 tests)
    - [ ] Test UserContentProhibitionFlag (5 tests)
  - [ ] Create `tests/unit/domain/test_user_content_prohibition_events.py`
    - [ ] Test UserContentProhibitionEventPayload (5 tests)
    - [ ] Test UserContentClearedEventPayload (5 tests)
    - [ ] Test signable_content determinism (3 tests)
  - [ ] Create `tests/unit/application/test_user_content_prohibition_service.py`
    - [ ] Test HALT CHECK FIRST pattern (4 tests)
    - [ ] Test clean content can be featured (3 tests)
    - [ ] Test prohibited content flagged not deleted (5 tests)
    - [ ] Test prohibition flag prevents featuring (3 tests)
    - [ ] Test event creation for all scenarios (5 tests)
    - [ ] Test batch evaluation (4 tests)
    - [ ] Test prohibition status query (3 tests)
  - [ ] Total: ~48 unit tests

- [x] **Task 8: Write Integration Tests** (AC: 1, 2, 3, 4, 5)
  - [ ] Create `tests/integration/test_user_content_prohibition_integration.py`
    - [ ] Test end-to-end featuring workflow (5 tests)
    - [ ] Test prohibited content flagged and event written (4 tests)
    - [ ] Test clean content cleared for featuring (3 tests)
    - [ ] Test batch evaluation workflow (3 tests)
    - [ ] Test prohibition flag persists on content (3 tests)
    - [ ] Test content NOT deleted when prohibited (2 tests)
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

**Story 9-3 (Quarterly Material Audit)** implemented:
- `QuarterlyAuditService` - Quarterly audit workflow
- `MaterialRepositoryProtocol` - Material listing
- `AuditRepositoryProtocol` - Audit history

**Story 9-4 (This Story)** is DIFFERENT because:
- User content is NOT deleted when prohibited (user's content belongs to them)
- Only FEATURING/CURATION is blocked, not the content itself
- Creates a prohibition FLAG instead of blocking content
- Uses same scanner infrastructure from 9-1, but different action on violation

### CRITICAL DISTINCTION: Flag Not Delete

```
Publications (9-2):  BLOCK content -> don't publish
User Content (9-4):  FLAG content -> allow to exist, prevent featuring
```

The key difference is ownership:
- Publications = system content = can be blocked
- User Content = user's property = flag only, never delete

### Architecture Pattern: Service Composition

```
UserContentProhibitionService (new)
    └── UserContentRepositoryProtocol (new - stores user content)
    └── ProhibitedLanguageScannerProtocol (from 9-1 - reuse scanning)
    └── EventWriterService (existing)
    └── HaltChecker (existing)
```

### Relevant Architecture Patterns and Constraints

**FR58 (User Content Prohibition):**
From `_bmad-output/planning-artifacts/epics.md#Story-9.4`:

> Curated/featured user content subject to same prohibition.
> Keyword scanning applies to featured content.
> Prohibited content is NOT deleted (user's content).
> Cannot be featured or curated.
> A flag is added.

**CT-11 (Silent Failure Destroys Legitimacy):**
- HALT CHECK FIRST on every service method
- Never silently allow prohibited content to be featured
- Flag immediately, fail loud

**CT-12 (Witnessing Creates Accountability):**
- All prohibition events MUST be witnessed
- Both clean AND prohibited content evaluations create events
- Events are immutable audit trail

### Source Tree Components to Touch

**Files to Create:**
```
src/domain/models/user_content.py
src/domain/events/user_content_prohibition.py
src/domain/errors/user_content.py
src/application/ports/user_content_repository.py
src/application/services/user_content_prohibition_service.py
src/infrastructure/stubs/user_content_repository_stub.py
tests/unit/domain/test_user_content.py
tests/unit/domain/test_user_content_prohibition_events.py
tests/unit/application/test_user_content_prohibition_service.py
tests/integration/test_user_content_prohibition_integration.py
```

**Files to Modify:**
```
src/domain/models/__init__.py          # Export UserContent, UserContentStatus, etc.
src/domain/events/__init__.py          # Export user content event payloads
src/domain/errors/__init__.py          # Export UserContentProhibitionError and subclasses
src/domain/models/event_type_registry.py # Add user content event types
src/application/ports/__init__.py      # Export UserContentRepositoryProtocol
src/application/services/__init__.py   # Export UserContentProhibitionService
src/infrastructure/stubs/__init__.py   # Export UserContentRepositoryStub
```

### Testing Standards Summary

**Coverage Requirements:**
- Minimum 80% coverage
- 100% coverage for prohibition service (critical compliance path)
- Test flag not delete behavior explicitly

**Async Testing:**
- ALL test files use `pytest.mark.asyncio`
- Use `AsyncMock` for async port methods
- Mock `HaltChecker` and `EventWriterService` in unit tests

**Key Test Scenarios:**
1. Clean content can be featured (PENDING_REVIEW status)
2. Prohibited content is FLAGGED (not deleted)
3. Flagged content cannot be featured (PROHIBITED status)
4. HALT CHECK FIRST prevents operations when halted
5. All events are written with correct payloads
6. Prohibition flag contains all required fields
7. Batch evaluation handles mixed results
8. Content ownership is preserved (never deleted)

### Previous Story Intelligence (Story 9-3)

**Learnings from Story 9-3:**
1. Service pattern: Constructor injection with ports
2. HALT CHECK FIRST at start of every public method
3. Event payloads are frozen dataclasses with `to_dict()` and `signable_content()`
4. Errors inherit from `ConstitutionalViolationError`
5. Stubs provide test control methods (configuration for test scenarios)
6. Batch operations collect all results, don't fail on first error

**Reuse from Story 9-1:**
- `ProhibitedLanguageScannerProtocol` - for scanning content
- Same scanning logic, different action on match

### Git Intelligence (Recent Commits)

```
686a37a feat(story-7.6): Implement cessation as final recorded event (FR24)
cdeb269 feat(story-3.6): Implement 48-hour recovery waiting period (FR21)
```

**Commit pattern for this story:**
```
feat(story-9.4): Implement user content prohibition (FR58)
```

### Critical Implementation Notes

**User Content Model:**
```python
from enum import Enum
from dataclasses import dataclass
from datetime import datetime

class UserContentStatus(str, Enum):
    """Status of user content."""
    ACTIVE = "active"
    FLAGGED = "flagged"  # Has prohibition flag
    REMOVED = "removed"  # User deleted their own content

class FeaturedStatus(str, Enum):
    """Featured eligibility status."""
    NOT_FEATURED = "not_featured"
    PENDING_REVIEW = "pending_review"  # Passed scan, awaiting curation
    FEATURED = "featured"
    PROHIBITED = "prohibited"  # Cannot be featured

@dataclass(frozen=True)
class UserContentProhibitionFlag:
    """Flag indicating content cannot be featured (FR58)."""
    flagged_at: datetime
    matched_terms: tuple[str, ...]
    can_be_featured: bool = False  # Always False
    reviewed_by: str | None = None
```

**Service Pattern:**
```python
async def evaluate_for_featuring(self, request: FeatureRequest) -> UserContent:
    """Evaluate user content for featuring per FR58."""
    # HALT CHECK FIRST (Golden Rule #1)
    await self._check_halt()

    # Scan content using existing scanner (reuse from 9-1)
    scan_result = await self._scanner.scan_content(request.content)

    if scan_result.violations_found:
        # FLAG - do NOT delete
        flag = UserContentProhibitionFlag(
            flagged_at=datetime.now(timezone.utc),
            matched_terms=scan_result.matched_terms,
            can_be_featured=False,
            reviewed_by=USER_CONTENT_SCANNER_SYSTEM_AGENT_ID,
        )

        # Update content with flag
        content = UserContent(
            content_id=request.content_id,
            owner_id=request.owner_id,
            content=request.content,
            title=request.title,
            status=UserContentStatus.FLAGGED,
            featured_status=FeaturedStatus.PROHIBITED,
            prohibition_flag=flag,
            created_at=datetime.now(timezone.utc),
        )

        # Write witnessed event (CT-12)
        await self._write_prohibition_event(content, scan_result)

        # Save flagged content (NOT deleted!)
        await self._content_repository.save_content(content)

        # Raise error - content cannot be featured
        raise UserContentCannotBeFeaturedException(
            content_id=request.content_id,
            owner_id=request.owner_id,
            matched_terms=scan_result.matched_terms,
        )

    # Clean - can be featured
    content = UserContent(
        content_id=request.content_id,
        owner_id=request.owner_id,
        content=request.content,
        title=request.title,
        status=UserContentStatus.ACTIVE,
        featured_status=FeaturedStatus.PENDING_REVIEW,
        prohibition_flag=None,
        created_at=datetime.now(timezone.utc),
    )

    # Write cleared event (CT-12)
    await self._write_cleared_event(content)

    await self._content_repository.save_content(content)
    return content
```

### Dependencies

**Required Ports (inject via constructor):**
- `UserContentRepositoryProtocol` - New for this story
- `ProhibitedLanguageScannerProtocol` - From Story 9-1 (existing)
- `EventWriterService` - For witnessed event writing (existing)
- `HaltChecker` - For CT-11 halt check (existing)

**Existing Infrastructure to Reuse:**
- `ProhibitedLanguageScannerProtocol` from Story 9-1
- `ProhibitedLanguageScannerStub` from Story 9-1
- `EventWriterService` from Story 1-6
- `HaltChecker` from Story 3-2

### Project Structure Notes

- Alignment with unified project structure (paths, modules, naming)
- New files follow existing patterns in `src/domain/models/`, `src/application/services/`, etc.
- No conflicts detected
- Reuses scanner infrastructure from 9-1 for consistency

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story-9.4] - Story definition
- [Source: _bmad-output/implementation-artifacts/stories/9-1-no-emergence-claims.md] - Scanner infrastructure
- [Source: _bmad-output/implementation-artifacts/stories/9-2-automated-keyword-scanning.md] - Publication scanning pattern
- [Source: _bmad-output/implementation-artifacts/stories/9-3-quarterly-material-audit.md] - Previous story
- [Source: src/application/services/publication_scanning_service.py] - Service pattern to follow
- [Source: src/domain/events/publication_scan.py] - Event pattern to follow

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

None.

### Completion Notes List

- **Implementation Complete**: All 8 tasks completed successfully
- **Test Coverage**: 116 tests passing (92 unit + 24 integration)
- **Critical FR58 Distinction**: User content is FLAGGED not DELETED when prohibited
- **Constitutional Compliance**: CT-11 (HALT CHECK FIRST) and CT-12 (event witnessing) implemented
- **Service Composition**: Reuses ProhibitedLanguageScannerProtocol from Story 9-1
- **Immutable Domain Models**: All dataclasses use `frozen=True`

### File List

**Created Files:**
- `src/domain/models/user_content.py` - Domain models (UserContent, UserContentStatus, FeaturedStatus, UserContentProhibitionFlag, FeatureRequest)
- `src/domain/events/user_content_prohibition.py` - Event payloads (UserContentProhibitionEventPayload, UserContentClearedEventPayload)
- `src/domain/errors/user_content.py` - Error classes (UserContentCannotBeFeaturedException, UserContentNotFoundError, UserContentFlagClearError)
- `src/application/ports/user_content_repository.py` - Repository protocol
- `src/application/services/user_content_prohibition_service.py` - Main service
- `src/infrastructure/stubs/user_content_repository_stub.py` - Test stub
- `tests/unit/domain/test_user_content.py` - Domain model unit tests (31 tests)
- `tests/unit/domain/test_user_content_prohibition_events.py` - Event unit tests (30 tests)
- `tests/unit/application/test_user_content_prohibition_service.py` - Service unit tests (31 tests)
- `tests/integration/test_user_content_prohibition_integration.py` - Integration tests (24 tests)

**Modified Files:**
- `src/domain/models/__init__.py` - Added exports
- `src/domain/events/__init__.py` - Added exports
- `src/domain/errors/__init__.py` - Added exports
- `src/domain/models/event_type_registry.py` - Added constitutional event types
- `src/application/ports/__init__.py` - Added exports
- `src/application/services/__init__.py` - Added exports
- `src/infrastructure/stubs/__init__.py` - Added exports

