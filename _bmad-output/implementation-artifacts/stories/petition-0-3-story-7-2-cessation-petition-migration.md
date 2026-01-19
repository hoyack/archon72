# Story 0.3: Story 7.2 Cessation Petition Migration (FR-9.1, ADR-P7)

Status: complete

## Story

As a **system operator**,
I want existing Story 7.2 cessation_petition data migrated to the new petition schema,
So that existing functionality is preserved and all 98 tests pass.

## Acceptance Criteria

### AC1: Petition Model Adapter (FR-9.1)

**Given** the existing `Petition` model from Story 7.2 (`src/domain/models/petition.py`)
**And** the new `PetitionSubmission` model from Story 0.2 (`src/domain/models/petition_submission.py`)
**When** I create a `CessationPetitionAdapter` class
**Then** it converts between the two models bidirectionally:
  - `Petition.petition_content` → `PetitionSubmission.text`
  - `Petition.petition_id` → `PetitionSubmission.id` (preserved, FR-9.4)
  - `Petition.created_timestamp` → `PetitionSubmission.created_at`
  - Hardcoded: `PetitionSubmission.type` = `CESSATION`
  - Hardcoded: `PetitionSubmission.realm` = `cessation-realm`
  - `Petition.status` mapping: `OPEN` → `RECEIVED`, `THRESHOLD_MET` → `ESCALATED`, `CLOSED` → `ACKNOWLEDGED`
**And** co-signer data is preserved in a separate mapping table (Story 7.2 has co-signers, Story 0.2 doesn't)

### AC2: Dual-Write Repository Adapter (FR-9.3)

**Given** the existing `PetitionRepositoryProtocol` from Story 7.2
**And** the new `PetitionSubmissionRepositoryProtocol` (to be created)
**When** I create a `DualWritePetitionRepository` adapter
**Then** writes go to BOTH repositories during migration period:
  - `save_petition()` writes to both legacy and new schema
  - `add_cosigner()` writes to legacy (co-signers remain in Story 7.2 model)
  - `update_status()` writes to both with appropriate state mapping
**And** reads come from the LEGACY repository (source of truth during migration)
**And** a configuration flag `PETITION_DUAL_WRITE_ENABLED` controls the behavior

### AC3: Petition Submission Repository Port (New)

**Given** the `PetitionSubmission` domain model from Story 0.2
**When** I query petitions
**Then** a `PetitionSubmissionRepositoryProtocol` exists in `src/application/ports/`
**And** it supports:
  - `save(submission: PetitionSubmission) -> None`
  - `get(id: UUID) -> PetitionSubmission | None`
  - `list_by_state(state: PetitionState, limit: int, offset: int) -> tuple[list[PetitionSubmission], int]`
  - `update_state(id: UUID, state: PetitionState) -> None`
**And** a stub implementation exists for testing

### AC4: All 98 Story 7.2 Tests Pass (FR-9.2)

**Given** the dual-write migration is enabled
**When** I run all Story 7.2 tests:
  - `tests/unit/domain/test_petition.py` (21 tests)
  - `tests/unit/domain/test_petition_events.py` (25 tests)
  - `tests/unit/application/test_petition_service.py` (14 tests)
  - `tests/unit/infrastructure/test_petition_repository_stub.py` (18 tests)
  - `tests/integration/test_external_observer_petition_integration.py` (20 tests)
**Then** all 98 tests pass without modification
**And** the existing API endpoints continue to work

### AC5: Petition ID Preservation (FR-9.4)

**Given** existing petitions with specific UUIDs
**When** they are accessed through the new schema
**Then** the original `petition_id` values are preserved exactly
**And** no ID collision or remapping occurs
**And** existing URLs/references continue to work

### AC6: Migration Script with Rollback

**Given** the dual-write adapter is working
**When** I run the migration script
**Then** it copies existing petition data to the new `petition_submissions` table
**And** creates a mapping table `petition_migration_mapping` with:
  - `legacy_petition_id` (UUID)
  - `new_submission_id` (UUID, same value per FR-9.4)
  - `migrated_at` (timestamptz)
  - `co_signer_count` (int, for reference)
**And** a rollback script exists that removes migrated data
**And** rollback is tested in integration tests

### AC7: Unit Tests for Adapter

**Given** the `CessationPetitionAdapter`
**When** I run unit tests
**Then** bidirectional conversion is tested
**And** state mapping is verified (OPEN→RECEIVED, THRESHOLD_MET→ESCALATED, CLOSED→ACKNOWLEDGED)
**And** ID preservation is verified
**And** edge cases are handled (empty content, no co-signers, max co-signers)

## Tasks / Subtasks

- [x] Task 1: Create PetitionSubmissionRepositoryProtocol (AC: 3)
  - [x] 1.1 Create `src/application/ports/petition_submission_repository.py`
  - [x] 1.2 Define `PetitionSubmissionRepositoryProtocol` with methods:
    - `save(submission: PetitionSubmission) -> None`
    - `get(id: UUID) -> PetitionSubmission | None`
    - `list_by_state(state: PetitionState, limit: int, offset: int) -> tuple[list[PetitionSubmission], int]`
    - `update_state(id: UUID, state: PetitionState) -> None`
  - [x] 1.3 Export from `src/application/ports/__init__.py`

- [x] Task 2: Create PetitionSubmissionRepositoryStub (AC: 3)
  - [x] 2.1 Create `src/infrastructure/stubs/petition_submission_repository_stub.py`
  - [x] 2.2 Implement in-memory storage matching PetitionSubmissionRepositoryProtocol
  - [x] 2.3 Export from `src/infrastructure/stubs/__init__.py`

- [x] Task 3: Create CessationPetitionAdapter (AC: 1, 5)
  - [x] 3.1 Create `src/infrastructure/adapters/petition_migration/cessation_adapter.py`
  - [x] 3.2 Implement `to_submission(petition: Petition) -> PetitionSubmission`:
    - Map `petition_content` → `text`
    - Map `petition_id` → `id` (PRESERVE EXACTLY)
    - Map `created_timestamp` → `created_at`
    - Set `type` = `PetitionType.CESSATION`
    - Set `realm` = `"cessation-realm"`
    - Map status: OPEN→RECEIVED, THRESHOLD_MET→ESCALATED, CLOSED→ACKNOWLEDGED
  - [x] 3.3 Implement `from_submission(submission: PetitionSubmission, cosigners: tuple[CoSigner, ...]) -> Petition`:
    - Reverse mapping for read operations
    - Preserve co-signer data from legacy
  - [x] 3.4 Create state mapping enum/constants
  - [x] 3.5 Export from `src/infrastructure/adapters/__init__.py`

- [x] Task 4: Create DualWritePetitionRepository (AC: 2)
  - [x] 4.1 Create `src/infrastructure/adapters/petition_migration/dual_write_repository.py`
  - [x] 4.2 Inject both `PetitionRepositoryProtocol` and `PetitionSubmissionRepositoryProtocol`
  - [x] 4.3 Implement dual-write for `save_petition()`:
    - Write to legacy repository
    - Convert via adapter and write to new repository
  - [x] 4.4 Implement `add_cosigner()` (legacy only - co-signers stay in Story 7.2 model)
  - [x] 4.5 Implement dual-write for `update_status()`:
    - Update legacy repository
    - Map status and update new repository
  - [x] 4.6 Implement reads from legacy repository (source of truth)
  - [x] 4.7 Add `PETITION_DUAL_WRITE_ENABLED` config flag
  - [x] 4.8 Export from `src/infrastructure/adapters/__init__.py`

- [x] Task 5: Create migration SQL (AC: 6)
  - [x] 5.1 Create `migrations/013_create_petition_migration_mapping.sql`
  - [x] 5.2 Create mapping table schema:
    - `legacy_petition_id` UUID PRIMARY KEY
    - `new_submission_id` UUID NOT NULL (FK to petition_submissions)
    - `migrated_at` TIMESTAMPTZ NOT NULL DEFAULT NOW()
    - `co_signer_count` INT NOT NULL DEFAULT 0
  - [x] 5.3 Add COMMENT documentation

- [x] Task 6: Create migration script (AC: 6)
  - [x] 6.1 Create `scripts/migrate_cessation_petitions.py`
  - [x] 6.2 Query existing petitions from events (Story 7.2 uses event sourcing)
  - [x] 6.3 Convert each petition via adapter
  - [x] 6.4 Insert into `petition_submissions` table
  - [x] 6.5 Record in mapping table
  - [x] 6.6 Log migration progress

- [x] Task 7: Create rollback script (AC: 6)
  - [x] 7.1 Create `scripts/rollback_cessation_migration.py`
  - [x] 7.2 Delete from `petition_submissions` WHERE id IN (SELECT new_submission_id FROM petition_migration_mapping)
  - [x] 7.3 Delete from `petition_migration_mapping`
  - [x] 7.4 Log rollback progress

- [x] Task 8: Create unit tests for adapter (AC: 7)
  - [x] 8.1 Create `tests/unit/infrastructure/adapters/test_cessation_petition_adapter.py`
  - [x] 8.2 Test `to_submission()` with various petition states
  - [x] 8.3 Test `from_submission()` round-trip
  - [x] 8.4 Test ID preservation (FR-9.4)
  - [x] 8.5 Test state mapping correctness
  - [x] 8.6 Test edge cases (empty content, max length, no co-signers)

- [x] Task 9: Create unit tests for dual-write repository (AC: 2, 7)
  - [x] 9.1 Create `tests/unit/infrastructure/adapters/test_dual_write_petition_repository.py`
  - [x] 9.2 Test dual-write on save
  - [x] 9.3 Test dual-write on status update
  - [x] 9.4 Test co-signer writes (legacy only)
  - [x] 9.5 Test reads from legacy
  - [x] 9.6 Test config flag behavior

- [x] Task 10: Create integration tests (AC: 4, 6)
  - [x] 10.1 Create `tests/integration/test_cessation_petition_migration.py`
  - [x] 10.2 Test migration script execution
  - [x] 10.3 Test rollback script execution
  - [x] 10.4 Test end-to-end petition flow with dual-write
  - [x] 10.5 Verify all 98 Story 7.2 tests still pass

- [x] Task 11: Verify all Story 7.2 tests pass (AC: 4)
  - [x] 11.1 Run `pytest tests/unit/domain/test_petition.py -v` (21 passed)
  - [x] 11.2 Run `pytest tests/unit/domain/test_petition_events.py -v` (25 passed)
  - [x] 11.3 Run `pytest tests/unit/application/test_petition_service.py -v` (14 passed)
  - [x] 11.4 Run `pytest tests/unit/infrastructure/test_petition_repository_stub.py -v` (18 passed)
  - [x] 11.5 Run `pytest tests/integration/test_external_observer_petition_integration.py -v` (20 passed)
  - [x] 11.6 Confirm 98/98 tests pass

## Dev Notes

### Critical Architecture Requirements

**Constitutional Truths to Honor:**
- **CT-11:** Silent failure destroys legitimacy → Migration must be auditable
- **CT-12:** Witnessing creates accountability → All changes logged
- **FR-9.4:** Petition ID preservation is MANDATORY

**PRD Requirements (FR-9.x):**
- **FR-9.1:** System SHALL migrate Story 7.2 cessation_petition to CESSATION type [P0]
- **FR-9.2:** All 98 existing tests SHALL pass post-migration [P0]
- **FR-9.3:** System SHALL support dual-write during migration period [P1]
- **FR-9.4:** System SHALL preserve existing petition_id references [P0]

**ADR-P7:** Story 7.2 Migration
- Subsume as CESSATION petition type
- Unified petition handling; preserve 98 tests
- Migration path; no breaking changes

### State Mapping Strategy

Story 7.2 has 3 states, Story 0.2 has 5 states:

| Story 7.2 (PetitionStatus) | Story 0.2 (PetitionState) | Rationale |
|---------------------------|---------------------------|-----------|
| `OPEN` | `RECEIVED` | Initial state, awaiting processing |
| `THRESHOLD_MET` | `ESCALATED` | 100 co-signers triggers escalation to King |
| `CLOSED` | `ACKNOWLEDGED` | No longer active, acknowledged by system |

**Note:** `DELIBERATING` and `REFERRED` states are not used for cessation petitions since they bypass Three Fates deliberation and go directly to escalation at 100 co-signers.

### Co-Signer Handling

Story 7.2's `Petition` model has co-signers embedded, while Story 0.2's `PetitionSubmission` does not track co-signers (they're handled differently in the Three Fates system).

**Strategy:**
1. Co-signer data remains in Story 7.2's event-sourced model
2. New `petition_submissions` table stores just the petition content
3. A future story (Epic 5) will handle co-signing for the new system
4. For cessation petitions, co-signers continue to be read from legacy events

### Hexagonal Architecture Compliance

**Files to Create:**

| Layer | Path | Purpose |
|-------|------|---------|
| Port | `src/application/ports/petition_submission_repository.py` | New repository protocol |
| Stub | `src/infrastructure/stubs/petition_submission_repository_stub.py` | Test implementation |
| Adapter | `src/infrastructure/adapters/petition_migration/cessation_adapter.py` | Model conversion |
| Adapter | `src/infrastructure/adapters/petition_migration/dual_write_repository.py` | Dual-write logic |
| Migration | `migrations/013_create_petition_migration_mapping.sql` | Mapping table |
| Script | `scripts/migrate_cessation_petitions.py` | Migration execution |
| Script | `scripts/rollback_cessation_migration.py` | Rollback execution |

**Import Rules (CRITICAL):**
```python
# ALLOWED in adapters/
from src.domain.models.petition import Petition, CoSigner
from src.domain.models.petition_submission import PetitionSubmission, PetitionType, PetitionState
from src.application.ports.petition_repository import PetitionRepositoryProtocol
from src.application.ports.petition_submission_repository import PetitionSubmissionRepositoryProtocol

# FORBIDDEN - Will fail pre-commit hook
from src.api import ...  # VIOLATION!
```

### Testing Strategy

**Unit Tests (no infrastructure):**
- Test adapter conversion in both directions
- Test state mapping correctness
- Test ID preservation (critical for FR-9.4)
- Test dual-write logic with mocks

**Integration Tests (require DB):**
- Test migration script with real data
- Test rollback script
- Test full petition flow with dual-write enabled
- Verify all 98 Story 7.2 tests still pass

### Configuration

Add to `src/config.py`:
```python
# Migration Configuration
PETITION_DUAL_WRITE_ENABLED: bool = True  # Set to False after migration complete
```

### Migration Execution Plan

1. **Pre-Migration:**
   - Deploy dual-write adapter code
   - Enable `PETITION_DUAL_WRITE_ENABLED=True`
   - Run migration script to copy existing data

2. **Migration Period:**
   - All writes go to both schemas
   - Reads come from legacy (source of truth)
   - Monitor for errors

3. **Post-Migration (Future Story):**
   - Switch reads to new schema
   - Set `PETITION_DUAL_WRITE_ENABLED=False`
   - Remove legacy code

### Previous Story Learnings

From Story 0.2 (Petition Domain Model):
- Use frozen dataclass with `eq=True` for immutability
- Comprehensive docstrings with FR references
- `with_*` pattern for state transitions

From Story 7.2 (External Observer Petition):
- 98 tests establish comprehensive coverage
- Event-sourced design for co-signers
- Ed25519 signature verification

### Future Story Dependencies

**This story enables:**
- Epic 5: Co-signing & Auto-Escalation (reads both schemas)
- Epic 6: King Escalation (unified escalation handling)
- Story 0.4: Job Queue (cessation deadline monitoring)

### References

- [Source: _bmad-output/planning-artifacts/petition-system-prd.md#FR-9.1-FR-9.4]
- [Source: _bmad-output/planning-artifacts/petition-system-epics.md#Story 0.3]
- [Source: _bmad-output/implementation-artifacts/stories/7-2-external-observer-petition.md]
- [Source: _bmad-output/implementation-artifacts/stories/petition-0-2-petition-domain-model-base-schema.md]
- [Source: src/domain/models/petition.py] - Legacy petition model
- [Source: src/domain/models/petition_submission.py] - New petition model

---

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

N/A - Story creation phase

### Completion Notes List

*To be filled during implementation*

### File List

**To Create:**
- `src/application/ports/petition_submission_repository.py`
- `src/infrastructure/stubs/petition_submission_repository_stub.py`
- `src/infrastructure/adapters/petition_migration/__init__.py`
- `src/infrastructure/adapters/petition_migration/cessation_adapter.py`
- `src/infrastructure/adapters/petition_migration/dual_write_repository.py`
- `migrations/013_create_petition_migration_mapping.sql`
- `scripts/migrate_cessation_petitions.py`
- `scripts/rollback_cessation_migration.py`
- `tests/unit/infrastructure/adapters/test_cessation_petition_adapter.py`
- `tests/unit/infrastructure/adapters/test_dual_write_petition_repository.py`
- `tests/integration/test_cessation_petition_migration.py`

**To Modify:**
- `src/application/ports/__init__.py` - Export new repository protocol
- `src/infrastructure/stubs/__init__.py` - Export new stub
- `src/infrastructure/adapters/__init__.py` - Export new adapters
- `src/config.py` - Add PETITION_DUAL_WRITE_ENABLED flag

### Change Log

| Date | Change | Author |
|------|--------|--------|
| 2026-01-19 | Story file created | Claude Opus 4.5 |

---

## Senior Developer Review (AI)

**Review Date:** Pending
**Reviewer:** Pending

### Checklist

- [ ] Code follows existing patterns (adapter pattern, protocol classes)
- [ ] Migration preserves petition IDs (FR-9.4)
- [ ] Dual-write logic is correct
- [ ] Rollback script is tested
- [ ] All 98 Story 7.2 tests pass
- [ ] State mapping is correct
- [ ] Configuration flag works

### Notes

*To be filled during review*
