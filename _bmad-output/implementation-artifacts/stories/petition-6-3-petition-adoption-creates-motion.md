# Story 6.3: Petition Adoption Creates Motion

## Story

**ID:** petition-6-3-petition-adoption-creates-motion
**Epic:** Petition Epic 6: King Escalation & Adoption Bridge
**Priority:** P0
**Status:** ready-for-dev

As a **King**,
I want to ADOPT an escalated petition and create a Motion,
So that the petition's concern enters the formal governance process.

## Acceptance Criteria

### AC1: Petition Adoption Endpoint
**Given** I am reviewing an escalated petition
**When** I POST `/api/v1/escalations/{petition_id}/adopt` with:
  - `motion_title`: title for the new Motion
  - `motion_body`: body text (may include petition text)
  - `adoption_rationale`: why I'm adopting this petition
**Then** a new Motion is created with:
  - `source_petition_ref` pointing to the original petition (FR-5.7)
  - `sponsor_id` = my King identity
  - Motion state = DRAFT (ready for formal introduction)
**And** the petition state remains ESCALATED (terminal)
**And** a `PetitionAdopted` event is emitted
**And** the event is witnessed via EventWriterService

### AC2: Adoption Budget Consumption (Story 6.4 Requirements)
**Given** a King has remaining promotion budget
**When** they adopt a petition
**Then** the budget is decremented atomically with Motion creation
**And** the budget consumption is durable (survives restart)
**And** if budget is insufficient, adoption fails with "INSUFFICIENT_BUDGET"

**Given** a King has zero remaining budget
**When** they attempt to adopt a petition
**Then** the system returns HTTP 400 with "INSUFFICIENT_BUDGET"
**And** the petition remains in escalation queue

**And** budget consumption uses existing PromotionBudgetStore
**And** consumption is atomic with Motion creation (same transaction)

### AC3: Realm Authorization
**Given** an escalated petition in realm "governance"
**When** a King from realm "knowledge" attempts to adopt
**Then** the system returns HTTP 403 Forbidden with realm mismatch error
**And** the petition remains in escalation queue

**Given** an escalated petition in my realm
**When** I am the King for that realm
**Then** adoption proceeds normally

### AC4: Petition Not Found
**Given** a petition_id that doesn't exist
**When** I attempt to adopt
**Then** the system returns HTTP 404 Not Found

### AC5: Petition Not Escalated
**Given** a petition in state RECEIVED, DELIBERATING, ACKNOWLEDGED, or REFERRED
**When** I attempt to adopt
**Then** the system returns HTTP 400 with "PETITION_NOT_ESCALATED"
**And** the petition state is unchanged

### AC6: Adoption Provenance Immutability (Story 6.6 Requirements)
**Given** a Motion created via adoption
**When** any update is attempted on `source_petition_ref`
**Then** the update is rejected with "IMMUTABLE_FIELD"
**And** the original reference remains intact

**Given** a Motion with `source_petition_ref`
**When** the source petition is queried
**Then** the petition shows `adopted_as_motion_id` back-reference
**And** provenance is visible in both directions

### AC7: Halt Check First (CT-13)
**Given** the system is in HALTED state
**When** I attempt to adopt a petition
**Then** the request is rejected with HTTP 503 Service Unavailable
**And** the response indicates "SYSTEM_HALTED"

### AC8: Rationale Validation
**Given** I attempt to adopt with empty or missing `adoption_rationale`
**When** the request is validated
**Then** the system returns HTTP 400 with validation error
**And** rationale is required (min 50 chars per good governance practice)

**Given** I attempt to adopt with whitespace-only rationale
**When** the request is validated
**Then** the system returns HTTP 400 with validation error

## References

- **FR-5.5:** King SHALL be able to ADOPT petition (creates Motion) [P0]
- **FR-5.6:** Adoption SHALL consume promotion budget (H1 compliance) [P0]
- **FR-5.7:** Adopted Motion SHALL include source_petition_ref (immutable) [P0]
- **FR-5.8:** King SHALL be able to ACKNOWLEDGE escalation (Story 6.5)
- **NFR-4.5:** Budget consumption durability (survives restart)
- **NFR-6.2:** Adoption provenance immutability
- **NFR-8.3:** Atomic budget consumption with Motion creation
- **CT-11:** Fail loud - never silently swallow errors
- **CT-12:** All events require witnessing
- **CT-13:** Halt check first pattern
- **ADR-P3:** King Adoption Prevents Budget Laundering (PRE-3 mitigation)
- **RULING-3:** Realm-scoped data access (Kings only adopt from their realm)
- **D8:** Keyset pagination compliance

## Tasks/Subtasks

### Task 1: Create Adoption Request/Response Models
- [ ] Create `src/api/models/adoption.py`
  - [ ] `PetitionAdoptionRequest` model (motion_title, motion_body, adoption_rationale)
  - [ ] `PetitionAdoptionResponse` model (motion_id, petition_id, sponsor_id, created_at)
  - [ ] Validation: motion_title (3-200 chars), motion_body (10-5000 chars), adoption_rationale (50-2000 chars)
  - [ ] Response includes Motion reference and provenance

### Task 2: Create Adoption Service Port
- [ ] Create `src/application/ports/petition_adoption.py`
  - [ ] `AdoptionRequest` dataclass (petition_id, king_id, realm_id, motion_title, motion_body, adoption_rationale)
  - [ ] `AdoptionResult` dataclass (success, motion_id, errors, budget_consumed)
  - [ ] `PetitionAdoptionProtocol` with `adopt_petition()` method
  - [ ] Custom errors: `PetitionNotEscalatedException`, `RealmMismatchException`, `InsufficientBudgetException`
- [ ] Add exports to `src/application/ports/__init__.py`

### Task 3: Create Petition Adoption Service
- [ ] Create `src/application/services/petition_adoption_service.py`
  - [ ] Implement `PetitionAdoptionProtocol`
  - [ ] Inject: petition_repo, budget_store, king_service, halt_circuit, knight_witness, event_writer
  - [ ] **HALT CHECK FIRST** (CT-13)
  - [ ] Validate petition exists and is ESCALATED
  - [ ] Validate realm authorization (RULING-3)
  - [ ] Check promotion budget (H1 compliance)
  - [ ] Create Motion via KingService.introduce_motion()
  - [ ] **Consume budget atomically** with Motion creation
  - [ ] Update petition with adopted_as_motion_id back-reference
  - [ ] Emit PetitionAdopted event (witnessed via EventWriterService)
  - [ ] Log with structlog (no f-strings)
  - [ ] Return AdoptionResult with motion_id
- [ ] Add exports to `src/application/services/__init__.py`

### Task 4: Create PetitionAdopted Event
- [ ] Update `src/domain/events/petition.py`
  - [ ] Add `PetitionAdopted` event class (inherits from PetitionEvent)
  - [ ] Fields: petition_id, motion_id, sponsor_king_id, adoption_rationale, adopted_at
  - [ ] Event category: PETITION_LIFECYCLE
  - [ ] Include complete provenance data for audit trail
- [ ] Add exports to `src/domain/events/__init__.py`

### Task 5: Update Petition Domain Model
- [ ] Update `src/domain/models/petition_submission.py`
  - [ ] Add `adopted_as_motion_id: str | None` field (back-reference)
  - [ ] Add `adopted_at: datetime | None` field
  - [ ] Add `adopted_by_king_id: str | None` field
  - [ ] Update `with_adoption()` method to populate adoption fields
  - [ ] Ensure immutability: adoption fields set once, never modified
- [ ] Create migration `migrations/027_add_petition_adoption_fields.sql`
  - [ ] Add `adopted_as_motion_id` column (text, nullable)
  - [ ] Add `adopted_at` column (timestamptz, nullable)
  - [ ] Add `adopted_by_king_id` column (text, nullable)
  - [ ] Add unique constraint on adopted_as_motion_id (one petition → one motion)
  - [ ] Add index for back-reference queries

### Task 6: Create Adoption Endpoint
- [ ] Update `src/api/routes/escalation.py`
  - [ ] `POST /api/v1/escalations/{petition_id}/adopt` route
  - [ ] King authorization check using permission enforcer
  - [ ] Realm authorization check (RULING-3)
  - [ ] Halt check before processing (CT-13)
  - [ ] Call PetitionAdoptionService.adopt_petition()
  - [ ] Return PetitionAdoptionResponse with motion_id
  - [ ] Return RFC 7807 errors with governance extensions:
    - [ ] 400 for validation errors, not escalated, insufficient budget
    - [ ] 403 for realm mismatch
    - [ ] 404 for petition not found
    - [ ] 503 for system halt
- [ ] Update `src/api/dependencies/escalation.py`
  - [ ] `get_petition_adoption_service()` singleton
  - [ ] `set_petition_adoption_service()` for testing

### Task 7: Update PromotionService Integration
- [ ] Review `src/application/services/promotion_service.py`
  - [ ] Ensure budget consumption pattern matches adoption needs
  - [ ] Verify atomic budget consumption
  - [ ] Note: Adoption uses same budget as Seed promotion (per ADR-P4)

### Task 8: Write Unit Tests
- [ ] Create `tests/unit/application/services/test_petition_adoption_service.py`
  - [ ] Test successful adoption (happy path)
  - [ ] Test insufficient budget (budget exhausted)
  - [ ] Test petition not found
  - [ ] Test petition not escalated (wrong state)
  - [ ] Test realm mismatch (wrong King for realm)
  - [ ] Test halt check first (system halted)
  - [ ] Test rationale validation (too short, empty, whitespace)
  - [ ] Test atomic budget consumption
  - [ ] Test event emission (PetitionAdopted)
  - [ ] Test provenance back-reference

### Task 9: Write Integration Tests
- [ ] Create `tests/integration/test_petition_adoption_endpoint.py`
  - [ ] Test POST /escalations/{petition_id}/adopt returns 200 with motion_id
  - [ ] Test 400 for insufficient budget
  - [ ] Test 400 for petition not escalated
  - [ ] Test 403 for realm mismatch
  - [ ] Test 404 for petition not found
  - [ ] Test 503 during system halt
  - [ ] Test Motion created with source_petition_ref
  - [ ] Test petition updated with adopted_as_motion_id
  - [ ] Test budget decremented after adoption
  - [ ] Test event witnessed via EventWriterService
  - [ ] Test provenance immutability (back-reference)

### Task 10: Update Repository Protocol
- [ ] Update `src/application/ports/petition_submission_repository.py`
  - [ ] Add `mark_adopted(petition_id, motion_id, king_id, adopted_at)` method
  - [ ] Ensure method is idempotent (no-op if already adopted)
- [ ] Update `src/infrastructure/stubs/petition_submission_repository_stub.py`
  - [ ] Implement mark_adopted in stub for testing

## Documentation Checklist

- [ ] Architecture docs updated (adoption flow, budget integration)
- [ ] API docs updated (new endpoint documentation)
- [ ] README updated (if setup/usage changed)
- [ ] Inline comments added for atomic budget consumption logic
- [X] N/A - no documentation impact (explain why)

## Dev Notes

### Architecture Patterns

This story follows patterns established in:
- **Epic 5 (Co-signing & Auto-Escalation):** Event emission, state transitions
- **Epic 6 Stories 6.1-6.2:** Escalation queue, decision packages
- **Government Epics:** PromotionService budget consumption, KingService motion creation
- **Port → Service → API pattern** for clean protocol-first design
- **RFC 7807 errors** with governance extensions
- **HALT CHECK FIRST** per CT-13 in all entry points

### Existing Components to Leverage

1. **KingServiceProtocol** (`src/application/ports/king_service.py`)
   - Use `introduce_motion()` to create Motion
   - Validates intent-only content (FR-GOV-6)
   - Returns Motion with INTRODUCED status (changed from DRAFT per gov system)
   - Note: Will need to adapt for DRAFT status if adoption differs from normal introduction

2. **PromotionService** (`src/application/services/promotion_service.py`)
   - **PRIMARY REFERENCE for budget consumption pattern**
   - Shows H1 budget check → consume → create → witness pattern
   - Atomic budget consumption with entity creation
   - Returns PromotionResult with success/failure
   - Budget store interface: PromotionBudgetStore

3. **PromotionBudgetStore** (`src/application/ports/promotion_budget_store.py`)
   - Interface: `can_promote(king_id, cycle_id, count)` → bool
   - Interface: `consume(king_id, cycle_id, count)` → new_used
   - Interface: `get_usage(king_id, cycle_id)` → KingBudgetUsage
   - Implementations: InMemoryBudgetStore, FileBudgetStore, RedisBudgetStore

4. **PetitionSubmission model** (`src/domain/models/petition_submission.py`)
   - Already has ESCALATED state (terminal)
   - Need to add: adopted_as_motion_id, adopted_at, adopted_by_king_id
   - Immutability: adoption fields set once, never modified

5. **EscalationQueueService** (`src/application/services/escalation_queue_service.py`)
   - Pattern for realm-scoped filtering
   - HALT CHECK FIRST pattern
   - Keyset pagination

6. **EventWriterService** (`src/application/services/event_writer_service.py`)
   - Existing witnessing pattern for all events
   - Use for PetitionAdopted event emission
   - Ensures CT-12 compliance (all events witnessed)

7. **HaltCircuitProtocol** (`src/application/ports/halt_circuit.py`)
   - Use `is_halted()` before processing (CT-13)
   - Writes blocked during halt, reads allowed

8. **PermissionEnforcerProtocol** (`src/application/ports/permission_enforcer.py`)
   - Use to verify King rank and realm authorization
   - Check permissions before allowing adoption

### Motion Creation from Adoption

**Key Difference from Seed Promotion:**

| Aspect | Seed Promotion (PromotionService) | Petition Adoption (This Story) |
|--------|----------------------------------|--------------------------------|
| **Source** | MotionSeeds (internal ideas) | Petition (external concerns) |
| **Input** | List of seeds, title, intent, constraints, success criteria | Petition ID, motion title/body, rationale |
| **Budget** | H1 promotion budget (same pool) | H1 promotion budget (same pool) |
| **Motion State** | INTRODUCED (per KingService) | DRAFT (ready for introduction) |
| **Provenance** | source_seed_refs list | source_petition_ref (single, immutable) |
| **Back-reference** | Seeds marked PROMOTED | Petition marked with adopted_as_motion_id |

**Critical Implementation Note:**
- PromotionService creates `MotionFromPromotion` (application layer construct)
- KingService creates `Motion` (domain model)
- This story needs to coordinate both:
  1. Use KingService.introduce_motion() to create Motion domain object
  2. Add source_petition_ref to Motion (may need Motion model extension)
  3. Alternatively: Create MotionFromAdoption similar to MotionFromPromotion

**Motion Structure for Adoption:**
```python
# Option 1: Extend Motion model with source_petition_ref
@dataclass(frozen=True)
class Motion:
    motion_id: UUID
    introduced_by: str  # King ID
    title: str
    intent: str  # motion_body becomes the intent
    rationale: str  # adoption_rationale
    status: MotionStatus  # DRAFT
    introduced_at: datetime
    source_petition_ref: UUID | None = None  # NEW: for adoption provenance
    session_ref: UUID | None = None
    amended_intent: str | None = None

# Option 2: Create MotionFromAdoption (parallel to MotionFromPromotion)
@dataclass
class MotionFromAdoption:
    motion_id: str
    title: str
    intent: str  # Derived from motion_body
    rationale: str  # adoption_rationale
    sponsor_id: str  # King ID
    created_at: datetime
    source_petition_ref: str  # Petition ID (immutable)
    realm_assignment: RealmAssignment  # King's realm
```

**Recommendation:** Option 2 (MotionFromAdoption) is cleaner because:
- Doesn't modify core Motion domain model
- Parallel structure to existing MotionFromPromotion
- Clear separation between adoption flow and normal motion introduction
- Application layer construct, not domain primitive

### Budget Consumption Pattern (CRITICAL)

**From PromotionService (reference implementation):**

```python
# Step 1: Validate inputs
if not petition.state == PetitionState.ESCALATED:
    return AdoptionResult(success=False, errors=["PETITION_NOT_ESCALATED"])

# Step 2: Check budget BEFORE any side effects
if not self.budget_store.can_promote(king_id, cycle_id, count=1):
    return AdoptionResult(success=False, errors=["INSUFFICIENT_BUDGET"])

# Step 3: Consume budget ATOMICALLY
new_used = self.budget_store.consume(king_id, cycle_id, count=1)

# Step 4: Create Motion (after budget consumed)
motion = self._create_motion_from_adoption(...)

# Step 5: Update petition with back-reference (non-destructive)
petition_repo.mark_adopted(petition_id, motion.motion_id, king_id, utc_now())

# Step 6: Emit event (witnessed)
event = PetitionAdopted(
    petition_id=petition_id,
    motion_id=motion.motion_id,
    sponsor_king_id=king_id,
    adoption_rationale=adoption_rationale,
    adopted_at=utc_now()
)
self.event_writer.write_event(event)

# Step 7: Return success
return AdoptionResult(success=True, motion_id=motion.motion_id, budget_consumed=1)
```

**Atomicity Guarantee:**
- Budget consumption happens BEFORE Motion creation
- If Motion creation fails → budget is lost (by design per ADR-P4)
- This prevents budget laundering (PRE-3 prevention)
- Budget store implementations (File, Redis) ensure durability (NFR-4.5)

### Realm Authorization Pattern

**From EscalationDecisionPackageService (Story 6.2):**

```python
# Get petition
petition = self.petition_repo.get_by_id(petition_id)
if not petition:
    raise EscalationNotFoundError(petition_id)

# Check realm match (RULING-3)
if petition.escalated_to_realm != king_realm_id:
    raise RealmMismatchError(
        king_realm=king_realm_id,
        petition_realm=petition.escalated_to_realm
    )
```

**Kings and Their Realms (from KING_REALM_MAP):**
1. Bael → realm_privacy_discretion_services
2. Paimon → realm_knowledge_skill_development
3. Beleth → realm_data_management_lifecycle
4. Asmoday → realm_commerce_financial_operations
5. Vine → realm_ethics_complaints_accountability
6. Balam → realm_infrastructure_platform_services
7. Barbatos → realm_api_interface_gateway_services
8. Zagan → realm_information_search_retrieval
9. Agares → realm_identity_access_authorization

### Database Schema

```sql
-- Migration 027: Add petition adoption fields
ALTER TABLE petition_submissions
ADD COLUMN adopted_as_motion_id TEXT,
ADD COLUMN adopted_at TIMESTAMPTZ,
ADD COLUMN adopted_by_king_id TEXT;

-- Unique constraint: one petition → one motion
ALTER TABLE petition_submissions
ADD CONSTRAINT unique_petition_adoption
UNIQUE (adopted_as_motion_id)
WHERE adopted_as_motion_id IS NOT NULL;

-- Index for back-reference queries
CREATE INDEX idx_petition_adoption_back_ref
ON petition_submissions (adopted_as_motion_id)
WHERE adopted_as_motion_id IS NOT NULL;

-- Index for King adoption history
CREATE INDEX idx_petition_adopted_by_king
ON petition_submissions (adopted_by_king_id, adopted_at)
WHERE adopted_by_king_id IS NOT NULL;
```

### API Request/Response Format

**Request:**
```json
POST /api/v1/escalations/{petition_id}/adopt

{
  "motion_title": "Address Data Retention Policy Concerns",
  "motion_body": "The petitioners have raised valid concerns about data retention policies. This motion directs the system to review and update retention policies to balance privacy and operational needs.",
  "adoption_rationale": "The 150+ co-signers demonstrate strong community concern. The petition text aligns with governance priorities for data privacy and discretion."
}
```

**Response (200 OK):**
```json
{
  "motion_id": "uuid-of-created-motion",
  "petition_id": "uuid-of-source-petition",
  "sponsor_id": "king-archon-id",
  "created_at": "2026-01-22T14:30:00Z",
  "provenance": {
    "source_petition_ref": "uuid-of-source-petition",
    "adoption_rationale": "The 150+ co-signers demonstrate...",
    "budget_consumed": 1
  }
}
```

**Error Response (400 - Insufficient Budget):**
```json
{
  "type": "https://conclave.archon72.ai/errors/insufficient-budget",
  "title": "Insufficient Promotion Budget",
  "status": 400,
  "detail": "King has exhausted promotion budget for current cycle",
  "king_id": "king-archon-id",
  "cycle_id": "2026-Q1",
  "budget": 3,
  "used": 3,
  "remaining": 0
}
```

**Error Response (403 - Realm Mismatch):**
```json
{
  "type": "https://conclave.archon72.ai/errors/realm-mismatch",
  "title": "Realm Authorization Failed",
  "status": 403,
  "detail": "Petition is assigned to a different realm",
  "king_realm": "realm_knowledge_skill_development",
  "petition_realm": "realm_privacy_discretion_services"
}
```

### Project Structure Notes

- Follow hexagonal architecture: ports in `application/ports/`, services in `application/services/`
- API routes in `api/routes/`, models in `api/models/`, dependencies in `api/dependencies/`
- Events in `domain/events/`
- Migrations in `migrations/` with sequential numbering (027)
- Tests mirror source structure

### Testing Standards

- Unit tests in `tests/unit/` mirroring source structure
- Integration tests in `tests/integration/` for API flows
- Use pytest-asyncio for async tests
- Use FastAPI TestClient for endpoint tests
- Minimum 80% coverage for new code
- Test all error paths: budget exhausted, realm mismatch, not escalated, not found, system halt

### Constitutional Constraints Summary

| Constraint | Description | Implementation |
|------------|-------------|----------------|
| **FR-5.5** | King ADOPT creates Motion | POST /api/v1/escalations/{petition_id}/adopt |
| **FR-5.6** | Adoption consumes budget | PromotionBudgetStore.consume() atomic |
| **FR-5.7** | source_petition_ref immutable | Motion field, database constraint |
| **NFR-4.5** | Budget consumption durable | FileBudgetStore, RedisBudgetStore |
| **NFR-6.2** | Provenance immutability | adopted_as_motion_id unique constraint |
| **NFR-8.3** | Atomic budget + creation | Budget consumed before Motion created |
| **CT-11** | Fail loud | Never silently swallow errors |
| **CT-12** | Witness everything | PetitionAdopted event via EventWriterService |
| **CT-13** | Halt check first | is_halted() before processing |
| **ADR-P4** | Prevent budget laundering | source_petition_ref mandatory + attribution |
| **RULING-3** | Realm-scoped access | King can only adopt from their realm |
| **D8** | Keyset pagination | For co-signer lists in decision package |
| **PRE-3** | Budget laundering prevention | Atomic consumption, immutable provenance |

### Previous Story Intelligence (Story 6.1 & 6.2)

**From Story 6.1 (King Escalation Queue):**
- Created EscalationSource enum (DELIBERATION, CO_SIGNER_THRESHOLD, KNIGHT_RECOMMENDATION)
- Added escalation tracking fields to petition_submissions (escalation_source, escalated_at, escalated_to_realm)
- Created GET /api/v1/escalations/queue endpoint with keyset pagination
- Established realm-scoped filtering pattern (RULING-3)
- HALT CHECK FIRST pattern in all entry points

**From Story 6.2 (Escalation Decision Package):**
- Created comprehensive decision package endpoint
- Established realm authorization pattern (RealmMismatchError)
- Submitter anonymization via SHA-256 hashing
- Context-dependent escalation history (deliberation vs Knight vs co-signer)
- Mediated deliberation summaries (RULING-2 compliance)
- 7 Pydantic response models for structured data

**Key Learnings:**
1. **Realm Authorization is Critical:** Check petition.escalated_to_realm matches King's realm
2. **Budget Pattern Exists:** PromotionService shows atomic consumption pattern
3. **Event Witnessing Pattern:** All state transitions emit witnessed events
4. **Error Responses:** RFC 7807 with governance extensions
5. **Keyset Pagination:** Use for any list endpoints (D8 compliance)

### Git Intelligence Summary

**Recent Commits (last 5):**
1. `ea436e5` - Implement Escalation Decision Package (Story 6.2)
   - 2,132 lines added across 7 files
   - Comprehensive decision package endpoint
   - Realm authorization enforcement
   - Mediated deliberation summaries

2. `27f9127` - Implement King Escalation Queue (Story 6.1)
   - 1,761 lines added across 11 files
   - Migration 026 for escalation tracking fields
   - Escalation queue endpoint with keyset pagination
   - FIFO ordering and realm filtering

3. `c898136` - Updates to tests
4. `b3cda8b` - Optimized Pipeline
5. `d22422a` - Format realm registry

**Implementation Patterns Observed:**
- **Large changesets:** 1,700-2,100 lines per story (comprehensive implementation)
- **Migration-first:** Database schema changes before service layer
- **Test-heavy:** ~50% of code is tests (unit + integration)
- **RFC 7807 errors:** Consistent error response format
- **Constitutional compliance:** Every commit references FRs, NFRs, CTs, Rulings

### Latest Technical Information

**Python Version:** 3.11+ (per test files using `async with` patterns)

**FastAPI Patterns:**
- Dependency injection via `Depends()`
- RFC 7807 error responses via custom exception handlers
- Pydantic v2 for request/response models
- TestClient for integration tests

**Database:**
- PostgreSQL with migrations
- Partial B-tree indexes for performance
- Unique constraints for immutability enforcement
- Timestamptz for all timestamps (UTC)

**Testing:**
- pytest-asyncio for async tests
- FastAPI TestClient for endpoint tests
- Stubs for protocol implementations (no mocks)
- Comprehensive coverage: happy path + all error paths

**Logging:**
- structlog for structured logging
- No f-strings in logs (use structlog.bind())
- Correlative IDs for request tracing

**Key Libraries:**
- FastAPI (async web framework)
- Pydantic v2 (validation)
- SQLAlchemy (if using ORM - TBD)
- structlog (structured logging)
- pytest + pytest-asyncio (testing)

### References

- [Source: _bmad-output/planning-artifacts/petition-system-epics.md#Epic 6, Story 6.3]
- [Source: _bmad-output/planning-artifacts/petition-system-prd.md#ADR-P4, PRE-3]
- [Source: src/application/services/promotion_service.py] - Budget consumption pattern (REFERENCE IMPLEMENTATION)
- [Source: src/application/ports/king_service.py] - Motion creation protocol
- [Source: src/application/services/escalation_decision_package_service.py] - Realm authorization pattern (Story 6.2)
- [Source: src/api/routes/escalation.py] - Escalation endpoint patterns (Stories 6.1, 6.2)
- [Source: src/domain/models/petition_submission.py] - Petition state machine
- [Source: src/application/ports/promotion_budget_store.py] - Budget store interface

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List
