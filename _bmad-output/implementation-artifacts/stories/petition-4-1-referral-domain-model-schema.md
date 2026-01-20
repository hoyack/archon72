# Story 4.1: Referral Domain Model & Schema

## Story Status: Complete

| Attribute          | Value                                    |
| ------------------ | ---------------------------------------- |
| Epic               | Epic 4: Knight Referral Workflow         |
| Story ID           | petition-4-1                             |
| Story Points       | 5                                        |
| Priority           | P1                                       |
| Status             | Complete                                 |
| Created            | 2026-01-19                               |
| Updated            | 2026-01-19                               |
| Constitutional Ref | FR-4.1, FR-4.2, NFR-3.4, NFR-4.4         |

## Story Description

As a **developer**,
I want a Referral aggregate that models the Knight review workflow,
So that referral state and deadlines are properly tracked.

## Constitutional Context

- **FR-4.1**: Marquis SHALL be able to REFER petition to Knight with realm_id
- **FR-4.2**: System SHALL assign referral deadline (3 cycles default)
- **NFR-3.4**: Referral timeout reliability: 100% timeouts fire
- **NFR-4.4**: Referral deadline persistence: Survives scheduler restart
- **NFR-7.3**: Realm-based Knight capacity limits

## Acceptance Criteria

### AC-1: Referral Status Enum
**Given** the referral workflow states
**When** I define the `ReferralStatus` enum
**Then** it contains the following values:
  - `PENDING` - Referral created, awaiting Knight assignment
  - `ASSIGNED` - Knight has been assigned to review
  - `IN_REVIEW` - Knight is actively reviewing
  - `COMPLETED` - Knight submitted recommendation
  - `EXPIRED` - Referral deadline passed without recommendation

- [x] Create `ReferralStatus` enum in `src/domain/models/referral.py`
- [x] Use `str, Enum` pattern for Python 3.10 compatibility
- [x] Add status transition validation helper methods

### AC-2: Referral Domain Model
**Given** no existing referral model
**When** I create the Referral aggregate
**Then** it contains:
  - `referral_id` (UUIDv7)
  - `petition_id` (foreign key)
  - `realm_id` (routing target)
  - `assigned_knight_id` (nullable until assignment)
  - `status` (ReferralStatus enum)
  - `deadline` (timestamp, UTC timezone-aware)
  - `extensions_granted` (integer, max 2)
  - `recommendation` (nullable: ACKNOWLEDGE, ESCALATE)
  - `rationale` (text, nullable)
  - `created_at`, `completed_at` (UTC timestamps)

- [x] Create `Referral` frozen dataclass in `src/domain/models/referral.py`
- [x] Add field validation in `__post_init__`
- [x] Add `MAX_EXTENSIONS = 2` class constant
- [x] Add `DEFAULT_DEADLINE_CYCLES = 3` class constant

### AC-3: Recommendation Enum
**Given** Knights submit recommendations
**When** I define the recommendation options
**Then** a `ReferralRecommendation` enum contains:
  - `ACKNOWLEDGE` - Recommend acknowledging the petition
  - `ESCALATE` - Recommend escalating to King

- [x] Create `ReferralRecommendation` enum in `src/domain/models/referral.py`
- [x] Use `str, Enum` pattern for Python 3.10 compatibility

### AC-4: Domain Invariant Methods
**Given** the Referral aggregate
**When** I implement domain methods
**Then** it provides:
  - `can_extend() -> bool` - Check if extension possible
  - `can_submit_recommendation() -> bool` - Check if recommendation allowed
  - `is_expired() -> bool` - Check if deadline passed
  - `with_status(ReferralStatus) -> Referral` - Status transition (immutable)
  - `with_assignment(knight_id) -> Referral` - Knight assignment (immutable)
  - `with_extension(new_deadline) -> Referral` - Grant extension (immutable)
  - `with_recommendation(recommendation, rationale) -> Referral` - Complete referral (immutable)

- [x] Implement all domain methods following frozen dataclass pattern
- [x] Add validation for state transitions
- [x] Raise `ValueError` for invalid transitions

### AC-5: Database Migration
**Given** no existing referrals table
**When** I run migration 023
**Then** the `referrals` table is created with:
  - All fields from AC-2
  - Foreign key to `petition_submissions(id)`
  - Indexes for efficient queries:
    - `idx_referrals_status_deadline` on (status, deadline)
    - `idx_referrals_knight_id_status` on (assigned_knight_id, status)
    - `idx_referrals_realm_id_status` on (realm_id, status)
    - `idx_referrals_petition_id` on (petition_id)

- [ ] Create `migrations/023_create_referrals_table.sql`
- [ ] Add CHECK constraint for `extensions_granted BETWEEN 0 AND 2`
- [ ] Add CHECK constraint for `status` values
- [ ] Add COMMENT documentation for all columns

### AC-6: Unit Tests
**Given** the Referral domain model
**When** I run unit tests
**Then** tests verify:
  - All field validation in `__post_init__`
  - Status transition validation
  - `can_extend()` logic
  - `can_submit_recommendation()` logic
  - `is_expired()` logic
  - Immutable `with_*` methods

- [ ] Create `tests/unit/domain/models/test_referral.py`
- [ ] Test valid Referral creation
- [ ] Test invalid field validation
- [ ] Test all domain methods
- [ ] Test edge cases (max extensions, deadline boundaries)

### AC-7: Model Export
**Given** the new domain models
**When** I update exports
**Then** models are available from `src/domain/models/__init__.py`:
  - `Referral`
  - `ReferralStatus`
  - `ReferralRecommendation`

- [ ] Update `src/domain/models/__init__.py` with exports

## Tasks/Subtasks

### Task 1: Create ReferralStatus Enum
- [ ] Create `src/domain/models/referral.py`
- [ ] Define `ReferralStatus` enum with 5 states
- [ ] Add docstrings with Constitutional refs

### Task 2: Create ReferralRecommendation Enum
- [ ] Add `ReferralRecommendation` enum to same file
- [ ] Define ACKNOWLEDGE and ESCALATE values

### Task 3: Create Referral Domain Model
- [ ] Define `Referral` frozen dataclass
- [ ] Add all required fields with proper types
- [ ] Add class constants: `MAX_EXTENSIONS`, `DEFAULT_DEADLINE_CYCLES`
- [ ] Implement `__post_init__` validation:
  - `referral_id` must be valid UUID
  - `petition_id` must be valid UUID
  - `realm_id` must be valid UUID (from realm registry)
  - `deadline` must be timezone-aware UTC
  - `extensions_granted` must be 0-2
  - `recommendation` only valid with `rationale` and COMPLETED status

### Task 4: Implement Domain Methods
- [ ] Implement `can_extend() -> bool`
  - Returns True if `extensions_granted < MAX_EXTENSIONS` and status is ASSIGNED or IN_REVIEW
- [ ] Implement `can_submit_recommendation() -> bool`
  - Returns True if status is IN_REVIEW and `assigned_knight_id` is set
- [ ] Implement `is_expired() -> bool`
  - Returns True if status is EXPIRED or (deadline < now and status not COMPLETED)
- [ ] Implement `with_status(ReferralStatus) -> Referral`
  - Validate state transitions
- [ ] Implement `with_assignment(knight_id: UUID) -> Referral`
  - Must be PENDING status
  - Sets status to ASSIGNED
- [ ] Implement `with_extension(new_deadline: datetime) -> Referral`
  - Increments `extensions_granted`
  - Updates `deadline`
  - Validates `can_extend()`
- [ ] Implement `with_recommendation(recommendation, rationale) -> Referral`
  - Sets `recommendation`, `rationale`, `completed_at`
  - Sets status to COMPLETED
  - Validates `can_submit_recommendation()`

### Task 5: Create Database Migration
- [ ] Create `migrations/023_create_referrals_table.sql`
- [ ] Define table schema with all columns
- [ ] Add foreign key constraint to `petition_submissions(id)`
- [ ] Add CHECK constraints for `extensions_granted` and `status`
- [ ] Create performance indexes
- [ ] Add COMMENT documentation

### Task 6: Create Unit Tests
- [ ] Create `tests/unit/domain/models/test_referral.py`
- [ ] Test `ReferralStatus` enum values
- [ ] Test `ReferralRecommendation` enum values
- [ ] Test valid `Referral` creation
- [ ] Test field validation errors
- [ ] Test `can_extend()` method
- [ ] Test `can_submit_recommendation()` method
- [ ] Test `is_expired()` method
- [ ] Test `with_status()` transitions
- [ ] Test `with_assignment()` method
- [ ] Test `with_extension()` method
- [ ] Test `with_recommendation()` method
- [ ] Test immutability (all `with_*` return new instances)

### Task 7: Update Model Exports
- [ ] Update `src/domain/models/__init__.py`
- [ ] Export `Referral`, `ReferralStatus`, `ReferralRecommendation`

## Technical Implementation

### Files to Create

1. **`src/domain/models/referral.py`**
   - `ReferralStatus` enum
   - `ReferralRecommendation` enum
   - `Referral` frozen dataclass

2. **`migrations/023_create_referrals_table.sql`**
   - `referrals` table DDL
   - Indexes and constraints

3. **`tests/unit/domain/models/test_referral.py`**
   - Comprehensive unit tests

### Files to Modify

1. **`src/domain/models/__init__.py`**
   - Add exports for new models

### State Transition Matrix

| From Status | Allowed Transitions |
|-------------|---------------------|
| PENDING | ASSIGNED, EXPIRED |
| ASSIGNED | IN_REVIEW, EXPIRED |
| IN_REVIEW | COMPLETED, EXPIRED |
| COMPLETED | (terminal) |
| EXPIRED | (terminal) |

### Deadline Calculation

```python
# Default: 3 cycles = 3 weeks (Conclave convenes weekly)
DEFAULT_DEADLINE_CYCLES = 3
DEFAULT_CYCLE_DURATION = timedelta(weeks=1)

# Default deadline = now + (3 * 1 week)
default_deadline = datetime.now(timezone.utc) + (DEFAULT_DEADLINE_CYCLES * DEFAULT_CYCLE_DURATION)
```

### Extension Logic

```python
# Max 2 extensions
MAX_EXTENSIONS = 2

# Each extension adds 1 cycle (1 week)
def with_extension(self, new_deadline: datetime) -> Referral:
    if not self.can_extend():
        raise ValueError("Cannot extend: max extensions reached or invalid status")
    return Referral(
        ...
        extensions_granted=self.extensions_granted + 1,
        deadline=new_deadline,
        ...
    )
```

## Dependencies

- `src/domain/models/petition_submission.py` - Petition FK reference
- `src/domain/models/realm.py` - Realm FK reference (for validation)
- `src/application/ports/job_scheduler.py` - For deadline job scheduling (Story 4.2)

## Definition of Done

- [ ] All acceptance criteria met
- [ ] `Referral` domain model complete with all methods
- [ ] `ReferralStatus` and `ReferralRecommendation` enums defined
- [ ] Migration 023 creates `referrals` table
- [ ] Unit tests written and passing
- [ ] Code follows existing patterns (frozen dataclass, `with_*` methods)
- [ ] Models exported from `__init__.py`
- [ ] No security vulnerabilities introduced
- [ ] Code passes lint and type checks

## Notes

- This story creates the domain model only - persistence and service layer are in Story 4.2
- Deadline jobs are scheduled in Story 4.2 via JobSchedulerProtocol
- Knight assignment logic is in Story 4.2 (ReferralExecutionService)
- Extension requests are handled in Story 4.5

## References

- [Source: _bmad-output/planning-artifacts/petition-system-epics.md#Story 4.1]
- [Source: _bmad-output/planning-artifacts/petition-system-prd.md#FR-4.1, FR-4.2]
- [Source: src/domain/models/petition.py] - Domain model pattern
- [Source: src/domain/models/realm.py] - Realm model reference
- [Source: src/domain/models/scheduled_job.py] - Job model pattern

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
- `src/domain/models/referral.py`
- `migrations/023_create_referrals_table.sql`
- `tests/unit/domain/models/test_referral.py`

**To Modify:**
- `src/domain/models/__init__.py`

### Change Log

| Date | Change | Author |
|------|--------|--------|
| 2026-01-19 | Story file created | Claude Opus 4.5 |

---

## Senior Developer Review (AI)

**Review Date:** Pending
**Reviewer:** Pending

### Checklist

- [ ] Domain model follows frozen dataclass pattern
- [ ] State transition validation implemented
- [ ] Migration follows existing conventions
- [ ] All domain invariants enforced
- [ ] Unit tests cover all methods and edge cases
- [ ] Models properly exported

### Notes

*To be filled during review*
