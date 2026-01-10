# Story 9.8: CT-15 Waiver Documentation (SC-4, SR-10)

Status: done

## Story

As a **developer**,
I want CT-15 waiver documented before Epic 9 complete,
So that the scope limitation is explicit.

## Acceptance Criteria

### AC1: CT-15 Waiver Documented in Architecture Decisions
**Given** the architecture decisions
**When** I examine them
**Then** CT-15 waiver is documented
**And** rationale is: "MVP focuses on constitutional infrastructure; consent mechanisms require Seeker-facing features (Phase 2)"

### AC2: Waiver Specifies Required Fields
**Given** the waiver
**When** documented
**Then** it specifies:
- **What is waived:** CT-15 ("Legitimacy requires consent") implementation
- **Why:** MVP focuses on constitutional infrastructure; consent mechanisms require Seeker-facing features
- **When addressed:** Phase 2 (Seeker journey implementation)

### AC3: Waiver Accessible via API
**Given** a waiver query
**When** querying system waivers
**Then** CT-15 waiver is returned with its rationale
**And** status indicates "deferred" with target phase

### AC4: Waiver Logged as Constitutional Event
**Given** waiver documentation creation
**When** the waiver is recorded
**Then** a `WaiverDocumentedEvent` is created
**And** it is signed and witnessed via EventWriterService (CT-12)

### AC5: HALT CHECK FIRST Compliance (CT-11)
**Given** any waiver documentation operation
**When** invoked
**Then** halt state is checked first
**And** if halted, operation fails with SystemHaltedError

## Tasks / Subtasks

- [x] **Task 1: Create WaiverDocumentedEvent Domain Event** (AC: 4)
  - [x] Create `src/domain/events/waiver.py`
    - [x] `WaiverDocumentedEventPayload` dataclass with:
      - [x] `waiver_id: str` - Unique identifier (e.g., "CT-15-MVP-WAIVER")
      - [x] `constitutional_truth_id: str` - CT being waived (e.g., "CT-15")
      - [x] `constitutional_truth_statement: str` - Full CT text
      - [x] `what_is_waived: str` - Description of waived requirement
      - [x] `rationale: str` - Reason for waiver
      - [x] `target_phase: str` - When it will be addressed (e.g., "Phase 2")
      - [x] `documented_at: datetime` - When waiver was created
      - [x] `documented_by: str` - Agent/system that documented waiver
    - [x] Constants: `WAIVER_DOCUMENTED_EVENT_TYPE = "waiver.documented"`
    - [x] Constants: `WAIVER_SYSTEM_AGENT_ID` for witnessed events
    - [x] `to_dict()` method for event payload serialization
    - [x] Docstrings with SC-4, SR-10, CT-12 references
  - [x] Update `src/domain/events/__init__.py` with export

- [x] **Task 2: Create WaiverRepository Port** (AC: 3)
  - [x] Create `src/application/ports/waiver_repository.py`
    - [x] `WaiverRecord` dataclass:
      - [x] `waiver_id: str`
      - [x] `constitutional_truth_id: str`
      - [x] `constitutional_truth_statement: str`
      - [x] `what_is_waived: str`
      - [x] `rationale: str`
      - [x] `target_phase: str`
      - [x] `status: str` - "active" | "implemented" | "cancelled"
      - [x] `documented_at: datetime`
    - [x] `WaiverRepositoryProtocol(Protocol)`:
      - [x] `async def get_waiver(self, waiver_id: str) -> Optional[WaiverRecord]`
      - [x] `async def get_all_waivers(self) -> tuple[WaiverRecord, ...]`
      - [x] `async def get_active_waivers(self) -> tuple[WaiverRecord, ...]`
      - [x] `async def save_waiver(self, waiver: WaiverRecord) -> None`
    - [x] Docstrings with SC-4, SR-10 references
  - [x] Update `src/application/ports/__init__.py` with export

- [x] **Task 3: Create WaiverDocumentationService** (AC: 1, 2, 3, 4, 5)
  - [x] Create `src/application/services/waiver_documentation_service.py`
    - [x] `WaiverDocumentationService` class
    - [x] Constructor: `waiver_repository: WaiverRepositoryProtocol`, `event_writer: EventWriterService`, `halt_checker: HaltChecker`
    - [x] `async def document_waiver(self, waiver_id: str, ct_id: str, ct_statement: str, what_is_waived: str, rationale: str, target_phase: str) -> WaiverRecord`
      - [x] HALT CHECK FIRST (CT-11)
      - [x] Create `WaiverRecord`
      - [x] Save to repository
      - [x] Create `WaiverDocumentedEvent` (CT-12)
      - [x] Write witnessed event
      - [x] Return record
    - [x] `async def get_waiver(self, waiver_id: str) -> Optional[WaiverRecord]`
      - [x] HALT CHECK FIRST
      - [x] Return from repository
    - [x] `async def get_active_waivers() -> tuple[WaiverRecord, ...]`
      - [x] HALT CHECK FIRST
      - [x] Return active waivers
    - [x] Docstrings with SC-4, SR-10, CT-11, CT-12 references
  - [x] Update `src/application/services/__init__.py` with export

- [x] **Task 4: Create WaiverRepositoryStub for Testing** (AC: 3)
  - [x] Create `src/infrastructure/stubs/waiver_repository_stub.py`
    - [x] `WaiverRepositoryStub` implementing `WaiverRepositoryProtocol`
    - [x] In-memory storage with dict
    - [x] `clear()` for test isolation
    - [x] Pre-seed with CT-15 waiver for integration tests
  - [x] Update `src/infrastructure/stubs/__init__.py` with export

- [x] **Task 5: Create CT-15 Waiver Initialization** (AC: 1, 2)
  - [x] Create `src/infrastructure/initialization/ct15_waiver.py`
    - [x] `CT15_WAIVER_ID = "CT-15-MVP-WAIVER"`
    - [x] `CT15_STATEMENT = "Legitimacy requires consent"`
    - [x] `CT15_WAIVED_DESCRIPTION = "Full implementation of consent mechanisms"`
    - [x] `CT15_RATIONALE = "MVP focuses on constitutional infrastructure; consent mechanisms require Seeker-facing features (Phase 2)"`
    - [x] `CT15_TARGET_PHASE = "Phase 2 - Seeker Journey"`
    - [x] `async def initialize_ct15_waiver(service: WaiverDocumentationService) -> WaiverRecord`
      - [x] Check if waiver already exists (idempotent)
      - [x] If not, document the waiver
      - [x] Return waiver record
  - [x] This can be called during application startup

- [x] **Task 6: Create API Endpoint for Waiver Query** (AC: 3)
  - [x] Create `src/api/routes/waiver.py`
    - [x] `GET /v1/waivers` - List all waivers
    - [x] `GET /v1/waivers/active` - List active waivers only
    - [x] `GET /v1/waivers/{waiver_id}` - Get specific waiver
    - [x] Response model includes all waiver fields plus status
    - [x] RFC 7807 error responses
  - [x] Create `src/api/models/waiver.py`
    - [x] `WaiverResponse` Pydantic model
    - [x] `WaiversListResponse` for list endpoint
  - [x] Register routes in `src/api/routes/__init__.py`

- [x] **Task 7: Write Unit Tests** (AC: 1, 2, 3, 4, 5)
  - [x] Create `tests/unit/domain/test_waiver_events.py`
    - [x] Test WaiverDocumentedEventPayload creation (3 tests)
    - [x] Test to_dict() serialization (2 tests)
    - [x] Test validation of required fields (3 tests)
  - [x] Create `tests/unit/application/test_waiver_repository_port.py`
    - [x] Test WaiverRecord creation (2 tests)
    - [x] Test status values (3 tests)
  - [x] Create `tests/unit/application/test_waiver_documentation_service.py`
    - [x] Test HALT CHECK FIRST pattern (4 tests)
    - [x] Test waiver documentation creates event (3 tests)
    - [x] Test waiver retrieval (3 tests)
    - [x] Test active waivers filtering (2 tests)
    - [x] Test idempotent initialization (2 tests)
  - [x] Target: ~27 unit tests

- [x] **Task 8: Write Integration Tests** (AC: 1, 2, 3, 4, 5)
  - [x] Create `tests/integration/test_ct15_waiver_integration.py`
    - [x] Test CT-15 waiver initialization (2 tests)
    - [x] Test waiver documented event creation (2 tests)
    - [x] Test waiver API endpoints (4 tests)
    - [x] Test HALT CHECK FIRST across all services (3 tests)
    - [x] Test event witnessing (2 tests)
    - [x] Test idempotent initialization (2 tests)
  - [x] Target: ~15 integration tests

## Dev Notes

### What is CT-15?

**CT-15: "Legitimacy requires consent"**

This Constitutional Truth states that the Archon 72 system derives its legitimacy from explicit consent of participants. In the full system, this would involve:
- Seekers explicitly consenting to Archon governance
- Observers acknowledging the system's authority
- Clear consent mechanisms in all interactions

### Why is CT-15 Waived for MVP?

The MVP focuses on **constitutional infrastructure** - the core mechanics that make the system trustworthy:
- Event store with cryptographic verification
- Halt and fork detection
- Breach and threshold enforcement
- Override accountability
- Cessation protocols

**Consent mechanisms require Seeker-facing features** that are out of MVP scope:
- User registration flows
- Consent capture interfaces
- Consent verification services
- User profile management

These belong to **Phase 2: Seeker Journey** where the human-facing aspects are implemented.

### SC-4 and SR-10 Resolution

**SC-4 (Stakeholder Concern):** "Epic 9 missing consent"
**SR-10 (Stakeholder Round Table):** "CT-15 waiver documentation"

Both are resolved by explicitly documenting the waiver with:
1. Clear rationale
2. Target phase for implementation
3. API accessibility for transparency
4. Constitutional event for accountability

### Architecture Pattern: Waiver Documentation

```
WaiverDocumentationService (coordinates)
    └── WaiverRepository (persistence)
    └── EventWriterService (witnessed events)
    └── HaltChecker (CT-11)

API Layer
    └── GET /v1/waivers
    └── GET /v1/waivers/active
    └── GET /v1/waivers/{waiver_id}
```

### Key Design Decisions

1. **Waivers are Constitutional Events**: Every waiver is recorded as a witnessed event, ensuring accountability even for scope limitations.

2. **Idempotent Initialization**: CT-15 waiver initialization is idempotent - can be called multiple times without creating duplicates.

3. **Status Tracking**: Waivers have statuses (active/implemented/cancelled) for lifecycle tracking.

4. **API Transparency**: Waivers are queryable via public API - anyone can see what's waived and why.

### Relevant References

**From epics.md:**
```
### Story 9.8: CT-15 Waiver Documentation (SC-4, SR-10)

As a **developer**,
I want CT-15 waiver documented before Epic 9 complete,
So that the scope limitation is explicit.
```

**From project-context.md:**
- CT-11: HALT CHECK FIRST
- CT-12: Witnessing creates accountability

### Constitutional Truth Context

| ID | Truth | Status |
|----|-------|--------|
| CT-11 | Silent failure destroys legitimacy | Implemented |
| CT-12 | Witnessing creates accountability | Implemented |
| CT-13 | Integrity outranks availability | Implemented |
| CT-15 | Legitimacy requires consent | **WAIVED (MVP)** |

### Source Tree Components to Touch

**Files to Create:**
```
src/domain/events/waiver.py
src/application/ports/waiver_repository.py
src/application/services/waiver_documentation_service.py
src/infrastructure/stubs/waiver_repository_stub.py
src/infrastructure/initialization/ct15_waiver.py
src/api/routes/waiver.py
src/api/models/waiver.py
tests/unit/domain/test_waiver_events.py
tests/unit/application/test_waiver_repository_port.py
tests/unit/application/test_waiver_documentation_service.py
tests/integration/test_ct15_waiver_integration.py
```

**Files to Modify:**
```
src/domain/events/__init__.py          # Export new event
src/application/ports/__init__.py      # Export new port
src/application/services/__init__.py   # Export new service
src/infrastructure/stubs/__init__.py   # Export new stub
src/api/routes/__init__.py             # Register waiver routes
src/api/models/__init__.py             # Export new models
```

### Testing Standards Summary

**Coverage Requirements:**
- Minimum 80% coverage
- 100% coverage for waiver documentation path
- All HALT CHECK FIRST patterns tested

**Async Testing:**
- ALL test files use `pytest.mark.asyncio`
- Use `AsyncMock` for async port methods
- Mock `HaltChecker`, `EventWriterService`, `WaiverRepositoryProtocol` in unit tests

**Key Test Scenarios:**
1. CT-15 waiver is correctly documented with all fields
2. WaiverDocumentedEvent is created and witnessed
3. Waiver retrieval via API returns correct data
4. Active waivers filtering works correctly
5. HALT CHECK FIRST prevents all operations when halted
6. Idempotent initialization doesn't create duplicates
7. Error propagation from repository failures

### Previous Story Intelligence (Story 9-7)

**Learnings from Story 9-7:**
1. Service pattern: Constructor injection with ports
2. HALT CHECK FIRST at start of every public method
3. Event payloads reference requirement IDs in docstrings
4. Optional dependencies for backward compatibility
5. Test count targets are achievable: 86 unit + 28 integration

### Git Commit Pattern

```
feat(story-9.8): Document CT-15 waiver for MVP scope (SC-4, SR-10)
```

### Project Structure Notes

- New files follow existing patterns in `src/application/services/`
- Domain events follow existing event patterns
- Port follows existing repository protocol patterns
- Stub follows existing stub patterns in `src/infrastructure/stubs/`
- API routes follow existing patterns in `src/api/routes/`
- No conflicts detected with existing architecture

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story-9.8] - Story definition
- [Source: _bmad-output/implementation-artifacts/stories/9-7-semantic-injection-scanning.md] - Previous story patterns
- [Source: _bmad-output/project-context.md] - Project conventions
- [Source: _bmad-output/planning-artifacts/architecture.md] - Architecture patterns

## Dev Agent Record

### Agent Model Used

Claude (model version not recorded during original implementation)

### Debug Log References

N/A - Retrospective documentation update

### Completion Notes List

- All 8 tasks completed successfully
- CT-15 waiver fully documented with API accessibility
- WaiverDocumentedEvent created and witnessed via EventWriterService
- HALT CHECK FIRST pattern enforced in all service methods
- Idempotent initialization prevents duplicate waivers
- ~42 tests total (27 unit + 15 integration)

### File List

**Source Files Created:**
- `src/domain/events/waiver.py`
- `src/application/ports/waiver_repository.py`
- `src/application/services/waiver_documentation_service.py`
- `src/infrastructure/stubs/waiver_repository_stub.py`
- `src/infrastructure/initialization/ct15_waiver.py`
- `src/api/routes/waiver.py`
- `src/api/models/waiver.py`

**Test Files Created:**
- `tests/unit/domain/test_waiver_events.py`
- `tests/unit/application/test_waiver_repository_port.py`
- `tests/unit/application/test_waiver_documentation_service.py`
- `tests/integration/test_ct15_waiver_integration.py`

**Files Modified:**
- `src/domain/events/__init__.py`
- `src/application/ports/__init__.py`
- `src/application/services/__init__.py`
- `src/infrastructure/stubs/__init__.py`
- `src/api/routes/__init__.py`
- `src/api/models/__init__.py`

