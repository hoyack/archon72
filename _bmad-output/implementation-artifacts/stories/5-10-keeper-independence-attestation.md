# Story 5.10: Keeper Independence Attestation (FR98, FR133)

Status: review

## Story

As an **external observer**,
I want annual Keeper independence attestation,
So that Keeper conflicts of interest are declared.

## Acceptance Criteria

### AC1: Annual Independence Attestation Event (FR133)
**Given** annual attestation requirement
**When** a Keeper attests independence
**Then** an `IndependenceAttestationEvent` is created
**And** it includes: `keeper_id`, `attested_at`, `attestation_year`, `conflict_declarations`, `affiliated_organizations`
**And** the attestation is cryptographically signed by the Keeper

### AC2: Missed Attestation Suspends Override Capability
**Given** a Keeper fails to attest within deadline
**When** the deadline passes
**Then** Keeper status is flagged as `independence_attestation_overdue`
**And** override capability is suspended until attestation
**And** a `KeeperIndependenceSuspendedEvent` is created
**And** the event includes: `keeper_id`, `deadline_missed`, `suspended_at`, `capabilities_suspended`

### AC3: Independence Attestation History Queryable
**Given** independence attestation history
**When** I query a Keeper's history
**Then** all attestations are visible
**And** changes in declarations are highlighted
**And** response includes: `attestation_list`, `declaration_changes`

### AC4: Declaration Change Tracking (FP-3 Integration)
**Given** a Keeper's independence declaration changes from previous year
**When** the new attestation is submitted
**Then** `DeclarationChangeDetectedEvent` is created
**And** changes are highlighted for review
**And** anomaly detection system is notified (ADR-7 integration)

## Tasks / Subtasks

- [x] Task 1: Create Independence Attestation Domain Models (AC: #1)
  - [x] 1.1 Create `src/domain/models/independence_attestation.py`:
    - `IndependenceAttestation` frozen dataclass with: `id`, `keeper_id`, `attested_at`, `attestation_year`, `conflict_declarations: list[ConflictDeclaration]`, `affiliated_organizations: list[str]`, `signature`
    - `ConflictDeclaration` frozen dataclass with: `declaration_type`, `description`, `related_party`, `disclosed_at`
    - `DeclarationType` enum: `FINANCIAL`, `ORGANIZATIONAL`, `PERSONAL`, `NONE_DECLARED`
    - `ATTESTATION_DEADLINE_DAYS = 365` (annual requirement)
    - `DEADLINE_GRACE_PERIOD_DAYS = 30` (30-day grace after anniversary)
    - `is_valid_for_year(year: int)` method
    - Use `DeletePreventionMixin` for audit trail preservation (FR76)
  - [x] 1.2 Export from `src/domain/models/__init__.py`

- [x] Task 2: Create Independence Attestation Events (AC: #1, #2, #4)
  - [x] 2.1 Create `src/domain/events/independence_attestation.py`:
    - `IndependenceAttestationPayload` - annual attestation submitted
      - Fields: `keeper_id`, `attestation_year`, `conflict_count`, `organization_count`, `attested_at`
      - `signable_content()` method for witnessing (CT-12)
    - `KeeperIndependenceSuspendedPayload` - override capability suspended
      - Fields: `keeper_id`, `deadline_missed`, `suspended_at`, `capabilities_suspended: list[str]`
      - `signable_content()` method
    - `DeclarationChangeDetectedPayload` - declaration changed from previous year
      - Fields: `keeper_id`, `attestation_year`, `previous_conflicts`, `current_conflicts`, `change_summary`, `detected_at`
      - `signable_content()` method
    - Event type constants: `INDEPENDENCE_ATTESTATION_EVENT_TYPE`, `KEEPER_INDEPENDENCE_SUSPENDED_EVENT_TYPE`, `DECLARATION_CHANGE_DETECTED_EVENT_TYPE`
  - [x] 2.2 Export from `src/domain/events/__init__.py`

- [x] Task 3: Create Independence Attestation Errors (AC: #2)
  - [x] 3.1 Create `src/domain/errors/independence_attestation.py`:
    - `IndependenceAttestationError(ConclaveError)` - base class
    - `AttestationDeadlineMissedError(IndependenceAttestationError)` - deadline passed, capabilities suspended
    - `DuplicateIndependenceAttestationError(IndependenceAttestationError)` - already attested for year
    - `InvalidIndependenceSignatureError(IndependenceAttestationError)` - signature verification failed
    - `CapabilitySuspendedError(IndependenceAttestationError)` - override attempted while suspended
    - All errors include FR133 reference in message
  - [x] 3.2 Export from `src/domain/errors/__init__.py`

- [x] Task 4: Create Independence Attestation Port (AC: #1, #2, #3)
  - [x] 4.1 Create `src/application/ports/independence_attestation.py`:
    - `IndependenceAttestationProtocol` with methods:
      - `async def get_attestation(keeper_id: str, year: int) -> IndependenceAttestation | None`
      - `async def record_attestation(attestation: IndependenceAttestation) -> None`
      - `async def get_attestation_history(keeper_id: str) -> list[IndependenceAttestation]`
      - `async def get_latest_attestation(keeper_id: str) -> IndependenceAttestation | None`
      - `async def get_keepers_overdue_attestation() -> list[str]`
      - `async def mark_keeper_suspended(keeper_id: str, reason: str) -> None`
      - `async def is_keeper_suspended(keeper_id: str) -> bool`
      - `async def clear_suspension(keeper_id: str) -> None`
  - [x] 4.2 Export from `src/application/ports/__init__.py`

- [x] Task 5: Create Independence Attestation Service (AC: #1, #2, #3, #4)
  - [x] 5.1 Create `src/application/services/independence_attestation_service.py`
  - [x] 5.2 Implement `IndependenceAttestationService`:
    - Inject: `IndependenceAttestationProtocol`, `KeeperSignatureService`, `EventWriterService`, `HaltChecker`, `AnomalyDetectorProtocol`
    - Constants:
      - `ATTESTATION_DEADLINE_DAYS = 365`
      - `GRACE_PERIOD_DAYS = 30`
      - `SUSPENDED_CAPABILITIES = ["override"]`
  - [x] 5.3 Implement `submit_independence_attestation(keeper_id: str, conflicts: list[ConflictDeclaration], organizations: list[str], signature: bytes) -> IndependenceAttestation`:
    - HALT CHECK FIRST (CT-11)
    - Verify Keeper signature using KeeperSignatureService
    - Calculate current attestation year
    - Check for duplicate attestation for year
    - Get previous year's attestation for comparison
    - Record attestation
    - Write `IndependenceAttestationEvent` to event store
    - If declarations changed from previous year:
      - Write `DeclarationChangeDetectedEvent`
      - Notify anomaly detection system
    - If Keeper was suspended, clear suspension
    - Return attestation record
  - [x] 5.4 Implement `check_attestation_deadlines() -> list[str]` - background task:
    - HALT CHECK FIRST
    - Calculate deadline for each Keeper based on first attestation date or system start
    - Find all Keepers past deadline + grace period
    - For each overdue Keeper:
      - Mark as suspended
      - Write `KeeperIndependenceSuspendedEvent`
    - Return list of newly suspended Keepers
  - [x] 5.5 Implement `get_keeper_independence_history(keeper_id: str) -> IndependenceHistoryResponse`:
    - Get all attestations for Keeper
    - Calculate declaration changes between consecutive years
    - Return: attestations, change_summary, current_status
  - [x] 5.6 Implement `validate_keeper_can_override(keeper_id: str) -> bool`:
    - Check if Keeper has valid current year attestation OR within grace period
    - If suspended, raise `CapabilitySuspendedError`
    - Return True if can override
  - [x] 5.7 Implement `get_declaration_diff(prev: IndependenceAttestation, curr: IndependenceAttestation) -> DeclarationDiff`:
    - Compare conflict declarations
    - Compare affiliated organizations
    - Return: added_conflicts, removed_conflicts, added_orgs, removed_orgs
  - [x] 5.8 Export from `src/application/services/__init__.py`

- [x] Task 6: Create Independence Attestation Stub (AC: #1, #2, #3)
  - [x] 6.1 Create `src/infrastructure/stubs/independence_attestation_stub.py`
  - [x] 6.2 Implement `IndependenceAttestationStub`:
    - In-memory attestation storage (dict by keeper_id -> list[attestation])
    - Suspended Keepers tracking (set)
    - `clear()` for test cleanup
    - `add_attestation(attestation: IndependenceAttestation)` for test setup
    - `suspend_keeper(keeper_id: str)` for suspension testing
  - [x] 6.3 Export from `src/infrastructure/stubs/__init__.py`

- [x] Task 7: Write Unit Tests (AC: #1, #2, #3, #4)
  - [x] 7.1 Create `tests/unit/domain/test_independence_attestation.py` (23 tests):
    - Test `IndependenceAttestation` creation with required fields
    - Test `ConflictDeclaration` creation
    - Test `DeclarationType` enum values
    - Test `is_valid_for_year()` temporal checks
    - Test annual period calculation
    - Test delete prevention (FR76)
    - Test signature requirement
  - [x] 7.2 Create `tests/unit/domain/test_independence_attestation_events.py` (18 tests):
    - Test `IndependenceAttestationPayload` creation
    - Test `KeeperIndependenceSuspendedPayload` creation
    - Test `DeclarationChangeDetectedPayload` creation
    - Test `signable_content()` determinism for all payloads
    - Test event type constants
    - Test serialization/deserialization
  - [x] 7.3 Create `tests/unit/domain/test_independence_attestation_errors.py` (20 tests):
    - Test `AttestationDeadlineMissedError` with FR133 reference
    - Test `DuplicateIndependenceAttestationError` creation
    - Test `InvalidIndependenceSignatureError` creation
    - Test `CapabilitySuspendedError` creation and message
  - [x] 7.4 Create `tests/unit/application/test_independence_attestation_service.py` (25 tests):
    - Test `submit_independence_attestation()` with valid signature (AC1)
    - Test `submit_independence_attestation()` rejects invalid signature
    - Test `submit_independence_attestation()` rejects duplicate for year
    - Test `submit_independence_attestation()` with HALT CHECK
    - Test `submit_independence_attestation()` detects declaration changes (AC4)
    - Test `submit_independence_attestation()` clears suspension
    - Test `check_attestation_deadlines()` detects overdue Keepers (AC2)
    - Test `check_attestation_deadlines()` suspends override capability (AC2)
    - Test `check_attestation_deadlines()` writes events correctly
    - Test `get_keeper_independence_history()` returns all attestations (AC3)
    - Test `get_keeper_independence_history()` highlights changes (AC3)
    - Test `validate_keeper_can_override()` with valid attestation
    - Test `validate_keeper_can_override()` raises when suspended
    - Test `get_declaration_diff()` calculates changes correctly
    - Test HALT CHECK at every operation boundary
  - [x] 7.5 Create `tests/unit/infrastructure/test_independence_attestation_stub.py` (24 tests):
    - Test stub implementation of all protocol methods
    - Test suspension tracking
    - Test attestation history retrieval
    - Test clear and setup methods

- [x] Task 8: Write Integration Tests (AC: #1, #2, #3, #4)
  - [x] 8.1 Create `tests/integration/test_keeper_independence_attestation_integration.py` (14 tests):
    - Test: `test_fr133_submit_valid_independence_attestation` (AC1)
    - Test: `test_attestation_includes_all_required_fields` (AC1)
    - Test: `test_attestation_is_witnessed` (CT-12)
    - Test: `test_deadline_missed_suspends_override_capability` (AC2)
    - Test: `test_suspension_event_includes_required_fields` (AC2)
    - Test: `test_suspended_keeper_cannot_override` (AC2)
    - Test: `test_attestation_clears_suspension` (AC2)
    - Test: `test_history_query_returns_all_attestations` (AC3)
    - Test: `test_history_highlights_declaration_changes` (AC3)
    - Test: `test_declaration_change_detected_event` (AC4)
    - Test: `test_declaration_change_notifies_anomaly_detector` (AC4)
    - Test: `test_signature_verification_required`
    - Test: `test_duplicate_attestation_rejected`
    - Test: `test_halt_check_prevents_attestation_during_halt`

## Code Review Action Items

> **Review Date:** 2026-01-07 | **Reviewer:** Claude Opus 4.5 (Code Review Workflow)
> **Tests:** 124 PASSED (110 unit + 14 integration)
> **Verdict:** CONDITIONAL PASS - Implementation correct, documentation incomplete

### 🔴 HIGH Priority (Must Fix Before Done)

- [ ] **AI-1: Populate File List section** - The implementation created 12 new files and modified 6 `__init__.py` files but none are documented. Add complete file inventory to Dev Agent Record → File List.

### 🟡 MEDIUM Priority (Should Fix)

- [ ] **AI-2: Complete Dev Agent Record** - Fill in Agent Model Used (remove placeholder), add Completion Notes summarizing implementation approach, update Change Log with completion entry.

- [ ] **AI-3: Document actual test count** - Story specified target of 95 tests but implementation has 124 tests (29 extra). Add note explaining the coverage expansion.

- [ ] **AI-4: Add `get_first_attestation_date()` to port** - Protocol lacks dedicated method to get first attestation date for deadline calculation. Currently uses `get_latest_attestation().attested_at` which is semantically incorrect for first-time deadline calculation.

### 🟢 LOW Priority (Nice to Have)

- [ ] **AI-5: Add `completed:` field to story front matter** - Other completed stories have this timestamp.

- [ ] **AI-6: Remove or use `ATTESTATION_DEADLINE_DAYS` constant** - Constant defined in domain model but not directly used in service logic.

---

## Dev Notes

### Constitutional Constraints (CRITICAL)

- **FR98**: Anomalous signature patterns (impossible timing, geographic impossibility) SHALL be flagged for manual review
- **FR133**: Keepers SHALL annually attest independence from each other and system operators; attestation recorded (exposes, doesn't prevent)
- **CT-11**: Silent failure destroys legitimacy -> HALT CHECK FIRST at every operation
- **CT-12**: Witnessing creates accountability -> All attestation events MUST be witnessed
- **NFR22**: All Keeper actions SHALL be cryptographically signed

### FR133 Implementation Context

From the PRD (Keeper Collusion Defense):
- Annual independence attestation is about EXPOSURE, not prevention
- Attestation declares conflicts of interest and affiliations
- Changes in declarations are highlighted to make patterns visible
- This creates accountability trail, not enforcement mechanism

### FP-3 and ADR-7 Integration

From Story 5.9 (Override Abuse Detection), the anomaly detection system should be notified when:
- A Keeper's declarations change significantly from previous year
- Multiple Keepers declare similar new affiliations (potential coordination)
- Declaration patterns suggest undisclosed relationships

The `AnomalyDetectorProtocol` from Story 5.9 can be extended to track independence attestation anomalies.

### Architecture Pattern: Independence Attestation Flow

```
1. submit_independence_attestation()
   |
   v
+---------------------------------------------+
| IndependenceAttestationService              |
| - HALT CHECK FIRST                          |
| - Verify Keeper signature                   |
| - Calculate attestation year                |
| - Check for duplicate                       |
| - Get previous attestation                  |
| - Compare declarations                      |
| - Record attestation                        |
| - Write IndependenceAttestationEvent        |
+---------------------------------------------+
   |
   | (if declarations changed)
   v
+---------------------------------------------+
| - Write DeclarationChangeDetectedEvent      |
| - Notify AnomalyDetectorProtocol            |
+---------------------------------------------+
   |
   | (if was suspended)
   v
+---------------------------------------------+
| - Clear suspension                          |
| - Resume override capability                |
+---------------------------------------------+

2. check_attestation_deadlines() [Background Task]
   |
   v
+---------------------------------------------+
| - HALT CHECK FIRST                          |
| - Get all active Keepers                    |
| - Calculate deadline for each               |
| - Find overdue Keepers (past grace period)  |
| - For each overdue:                         |
|   - Mark suspended                          |
|   - Write KeeperIndependenceSuspendedEvent  |
+---------------------------------------------+

3. validate_keeper_can_override()
   |
   v
+---------------------------------------------+
| Called by OverrideService before override   |
| - Check current year attestation            |
| - Check grace period                        |
| - Raise CapabilitySuspendedError if invalid |
+---------------------------------------------+
```

### Integration with Override System

**From Story 5.4 (Constitution Supremacy) - OverrideService integration:**

Before executing an override, `OverrideService.initiate_override()` should call:
```python
await independence_attestation_service.validate_keeper_can_override(keeper_id)
```

If the Keeper's independence attestation is overdue (past grace period), the override is blocked with `CapabilitySuspendedError`.

### Attestation Year Calculation

```python
def get_current_attestation_year() -> int:
    """Return the current attestation year.

    Attestation year aligns with calendar year.
    """
    return datetime.now(timezone.utc).year

def calculate_deadline(first_attestation_date: datetime) -> datetime:
    """Calculate when next attestation is due.

    Due on anniversary of first attestation + grace period.
    If no previous attestation, due immediately.
    """
    if first_attestation_date is None:
        return datetime.now(timezone.utc)  # Due immediately

    # Anniversary of first attestation in current year
    current_year = datetime.now(timezone.utc).year
    anniversary = first_attestation_date.replace(year=current_year)

    # Add grace period
    deadline = anniversary + timedelta(days=GRACE_PERIOD_DAYS)
    return deadline
```

### Declaration Diff Algorithm

```python
@dataclass(frozen=True)
class DeclarationDiff:
    added_conflicts: list[ConflictDeclaration]
    removed_conflicts: list[ConflictDeclaration]
    added_organizations: list[str]
    removed_organizations: list[str]
    has_changes: bool

def get_declaration_diff(
    prev: IndependenceAttestation | None,
    curr: IndependenceAttestation
) -> DeclarationDiff:
    """Compare declarations between consecutive attestations."""
    if prev is None:
        return DeclarationDiff(
            added_conflicts=curr.conflict_declarations,
            removed_conflicts=[],
            added_organizations=curr.affiliated_organizations,
            removed_organizations=[],
            has_changes=len(curr.conflict_declarations) > 0 or len(curr.affiliated_organizations) > 0
        )

    prev_conflicts = set(prev.conflict_declarations)
    curr_conflicts = set(curr.conflict_declarations)
    prev_orgs = set(prev.affiliated_organizations)
    curr_orgs = set(curr.affiliated_organizations)

    added_conflicts = list(curr_conflicts - prev_conflicts)
    removed_conflicts = list(prev_conflicts - curr_conflicts)
    added_orgs = list(curr_orgs - prev_orgs)
    removed_orgs = list(prev_orgs - curr_orgs)

    has_changes = bool(added_conflicts or removed_conflicts or added_orgs or removed_orgs)

    return DeclarationDiff(
        added_conflicts=added_conflicts,
        removed_conflicts=removed_conflicts,
        added_organizations=added_orgs,
        removed_organizations=removed_orgs,
        has_changes=has_changes
    )
```

### Previous Story Learnings (from 5.8 and 5.9)

**From Story 5.8 (Keeper Availability Attestation):**
- Attestation domain model pattern with temporal validity
- Suspension tracking and capability restriction
- Background task for deadline checking (idempotent)
- Integration with KeeperSignatureService
- 80 tests pattern - maintain similar rigor

**From Story 5.9 (Override Abuse Detection):**
- AnomalyDetectorProtocol integration pattern
- Event payload with `signable_content()` for witnessing
- Violation type enums
- HALT CHECK FIRST at every operation boundary

### Files to Create

```
src/domain/models/independence_attestation.py                    # Domain model
src/domain/events/independence_attestation.py                    # Event payloads
src/domain/errors/independence_attestation.py                    # Error classes
src/application/ports/independence_attestation.py                # Repository protocol
src/application/services/independence_attestation_service.py     # Main service
src/infrastructure/stubs/independence_attestation_stub.py        # Test stub
tests/unit/domain/test_independence_attestation.py               # Model tests
tests/unit/domain/test_independence_attestation_events.py        # Event tests
tests/unit/domain/test_independence_attestation_errors.py        # Error tests
tests/unit/application/test_independence_attestation_service.py  # Service tests
tests/unit/infrastructure/test_independence_attestation_stub.py  # Stub tests
tests/integration/test_keeper_independence_attestation_integration.py  # Integration tests
```

### Files to Modify

```
src/domain/models/__init__.py              # Export IndependenceAttestation, ConflictDeclaration, DeclarationType
src/domain/events/__init__.py              # Export event payloads and constants
src/domain/errors/__init__.py              # Export error classes
src/application/ports/__init__.py          # Export IndependenceAttestationProtocol
src/application/services/__init__.py       # Export service and response dataclasses
src/infrastructure/stubs/__init__.py       # Export IndependenceAttestationStub
```

### Import Rules (Hexagonal Architecture)

- `domain/models/` imports from `domain/errors/`, `domain/primitives/`, `typing`, `datetime`, `dataclasses`, `uuid`, `enum`
- `domain/events/` imports from `domain/models/`, `typing`, `datetime`, `json`
- `domain/errors/` inherits from base `ConclaveError`
- `application/ports/` imports from `domain/models/`, `typing` (Protocol)
- `application/services/` imports from `application/ports/`, `domain/`
- NEVER import from `infrastructure/` in `domain/` or `application/`

### Testing Standards

- ALL tests use `pytest.mark.asyncio`
- Use `AsyncMock` for async dependencies
- Unit tests mock the protocol interfaces
- Integration tests use stub implementations
- FR133 tests MUST verify attestation recording and exposure (not enforcement)
- Test declaration change detection thoroughly (boundary conditions)
- Test suspension and capability restriction
- Test HALT CHECK at every operation boundary
- Target: 95 tests (similar rigor to 5.8 and 5.9)

### Critical Implementation Notes

1. **Exposure, Not Enforcement**: FR133 is about making conflicts visible, not preventing them. The system records and exposes, it does not judge.
2. **Signature Verification**: Every attestation MUST be cryptographically signed (use KeeperSignatureService)
3. **Declaration Comparison**: Diff algorithm must handle first-time attestations (no previous to compare)
4. **Grace Period**: 30-day grace period after annual anniversary before suspension
5. **Anomaly Integration**: Declaration changes should notify anomaly detection for pattern analysis
6. **Background Task**: `check_attestation_deadlines()` should be idempotent (safe to run multiple times)

### Project Structure Notes

- Follows Story 5.8 attestation patterns closely
- Events follow existing payload patterns with `signable_content()`
- Errors inherit from `ConclaveError` with FR references
- Service follows HALT CHECK FIRST pattern throughout
- Integrates with anomaly detection from Story 5.9

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story-5.10] - Story definition
- [Source: _bmad-output/planning-artifacts/prd.md#FR133] - Keeper Collusion Defense requirements
- [Source: _bmad-output/planning-artifacts/prd.md#FR98] - Key Lifecycle Management
- [Source: _bmad-output/planning-artifacts/architecture.md#ADR-007] - Aggregate Anomaly Detection
- [Source: _bmad-output/planning-artifacts/architecture.md#ADR-004] - Key Custody patterns
- [Source: _bmad-output/planning-artifacts/architecture.md#ADR-005] - Watchdog Independence
- [Source: src/domain/models/keeper_attestation.py] - Attestation model patterns (Story 5.8)
- [Source: src/application/services/keeper_availability_service.py] - Attestation service patterns
- [Source: src/application/ports/anomaly_detector.py] - Anomaly detection integration
- [Source: src/application/services/override_abuse_detection_service.py] - Anomaly notification patterns
- [Source: _bmad-output/implementation-artifacts/stories/5-8-keeper-availability-attestation.md] - Previous story patterns
- [Source: _bmad-output/implementation-artifacts/stories/5-9-override-abuse-detection.md] - Anomaly integration patterns

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### Change Log

| Date | Change | Author |
|------|--------|--------|
| 2026-01-07 | Story created with comprehensive FR98/FR133 context | Create-Story Workflow (Opus 4.5) |

### File List

