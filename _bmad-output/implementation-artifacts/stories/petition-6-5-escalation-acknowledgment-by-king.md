# Story 6.5: Escalation Acknowledgment by King

## Story

**ID:** petition-6-5-escalation-acknowledgment-by-king
**Epic:** Petition Epic 6: King Escalation & Adoption Bridge
**Priority:** P0
**Status:** ready-for-dev

As a **King**,
I want to ACKNOWLEDGE an escalation with rationale,
So that I can formally decline adoption while respecting the petitioners.

## Acceptance Criteria

### AC1: King Acknowledgment Endpoint
**Given** I am reviewing an escalated petition
**When** I POST `/api/v1/kings/escalations/{petition_id}/acknowledge` with:
  - `reason_code`: from acknowledgment enum (ADDRESSED, NOTED, OUT_OF_SCOPE, etc.)
  - `rationale`: mandatory explanation (min 100 chars)
**Then** the petition is acknowledged (uses Epic 3 acknowledgment service)
**And** the acknowledgment records `acknowledged_by_king_id`
**And** a `KingAcknowledgedEscalation` event is emitted
**And** the rationale is preserved for petitioner visibility

### AC2: Rationale Validation
**Given** I acknowledge without sufficient rationale
**When** the request is validated
**Then** the system returns HTTP 400 with validation error
**And** minimum rationale length is 100 characters

### AC3: Petition Must Be Escalated
**Given** a petition not in ESCALATED state
**When** I attempt to acknowledge
**Then** the system returns HTTP 400 with "PETITION_NOT_ESCALATED"
**And** the petition state is unchanged

### AC4: Realm Authorization
**Given** an escalated petition in realm "governance"
**When** a King from realm "knowledge" attempts to acknowledge
**Then** the system returns HTTP 403 Forbidden with realm mismatch error

### AC5: Halt Check First (CT-13)
**Given** the system is in HALTED state
**When** I attempt to acknowledge
**Then** the request is rejected with HTTP 503 Service Unavailable
**And** the response indicates "SYSTEM_HALTED"

### AC6: King ID Recorded
**Given** a successful King acknowledgment
**When** the acknowledgment is created
**Then** it includes `acknowledged_by_king_id` field
**And** this field is separate from `acknowledging_archon_ids` (which will be empty for King acknowledgments)

### AC7: Event Emission
**Given** a successful King acknowledgment
**When** the acknowledgment completes
**Then** a `KingAcknowledgedEscalation` event is emitted
**And** the event includes petition_id, king_id, reason_code, and rationale
**And** the event is witnessed via EventWriterService (CT-12)

## References

- **FR-5.8:** King SHALL be able to ACKNOWLEDGE escalation (with rationale) [P0]
- **FR-3.1:** Marquis SHALL be able to ACKNOWLEDGE petition with reason code [P0]
- **FR-3.2:** System SHALL require reason_code from enumerated list [P0]
- **FR-3.3:** System SHALL require rationale text for certain reason codes [P0]
- **CT-12:** All events require witnessing
- **CT-13:** Halt check first pattern
- **RULING-3:** Realm-scoped data access

## Implementation Plan

### Components to Implement

1. **King Acknowledgment Method**
   - Add `execute_king_acknowledge()` to `AcknowledgmentExecutionService`
   - Similar to `execute_system_acknowledge()` but:
     - Records King ID separately
     - Validates petition is in ESCALATED state (not DELIBERATING)
     - Emits KingAcknowledgedEscalation event (not PetitionAcknowledged)
     - Enforces rationale minimum length (100 chars)

2. **King Acknowledgment Endpoint**
   - POST `/api/v1/kings/escalations/{petition_id}/acknowledge`
   - Request: `{"reason_code": "NOTED", "rationale": "..."}`
   - Query params: `king_id` and `realm_id`
   - Response: Acknowledgment details with king_id

3. **KingAcknowledgedEscalation Event**
   - Create event payload in `src/domain/events/petition.py`
   - Include: petition_id, king_id, reason_code, rationale, acknowledged_at

4. **Database Schema**
   - Add `acknowledged_by_king_id` column to acknowledgments table
   - Migration to add nullable UUID column

### Reuse from Epic 3

- **AcknowledgmentReasonCode** enum (already exists)
- **validate_acknowledgment_requirements()** (already exists)
- **AcknowledgmentRepositoryProtocol** (already exists)
- **Acknowledgment domain model** (already exists)

### Design Decisions

1. **King vs Marquis Acknowledgment**
   - King acknowledgments bypass dwell time enforcement
   - King acknowledgments work on ESCALATED state (not DELIBERATING)
   - King acknowledgments recorded with `acknowledged_by_king_id`
   - Separate event type for King acknowledgments

2. **Rationale Minimum Length**
   - 100 characters minimum for King acknowledgments (vs 0-50 for Marquis)
   - Higher bar for Kings given constitutional significance

3. **Event Type**
   - New event: `petition.escalation.acknowledged_by_king`
   - Distinct from `petition.acknowledged` (Marquis/system acknowledgments)

## Tasks

### Task 1: Add King Acknowledgment Column
- [ ] Create migration `028_add_king_acknowledgment_field.sql`
  - [ ] Add `acknowledged_by_king_id UUID NULL` to acknowledgments table
  - [ ] Add index on `acknowledged_by_king_id` for queries
  - [ ] Add CHECK constraint: only one of (acknowledging_archon_ids, acknowledged_by_king_id) can be set

### Task 2: Update Acknowledgment Domain Model
- [ ] Update `src/domain/models/acknowledgment.py`
  - [ ] Add `acknowledged_by_king_id: UUID | None` field
  - [ ] Update validation to allow empty `acknowledging_archon_ids` if `acknowledged_by_king_id` is set

### Task 3: Create KingAcknowledgedEscalation Event
- [ ] Update `src/domain/events/petition.py`
  - [ ] Add `KingAcknowledgedEscalationEventPayload` dataclass
  - [ ] Fields: petition_id, king_id, reason_code, rationale, acknowledged_at, realm_id

### Task 4: Implement King Acknowledgment Service Method
- [ ] Update `src/application/services/acknowledgment_execution_service.py`
  - [ ] Add `execute_king_acknowledge()` method
  - [ ] Validate petition is in ESCALATED state
  - [ ] Validate rationale >= 100 chars
  - [ ] Create acknowledgment with `acknowledged_by_king_id`
  - [ ] Emit KingAcknowledgedEscalation event

### Task 5: Create King Acknowledgment Endpoint
- [ ] Update `src/api/routes/escalation.py`
  - [ ] Add POST `/escalations/{petition_id}/acknowledge` endpoint
  - [ ] Request model: `EscalationAcknowledgmentRequest`
  - [ ] Response model: `EscalationAcknowledgmentResponse`
  - [ ] Query params: king_id, realm_id
  - [ ] Error handling: 400 (validation, not escalated), 403 (realm), 404 (not found), 503 (halt)

### Task 6: Create Request/Response Models
- [ ] Update `src/api/models/escalation.py`
  - [ ] Add `EscalationAcknowledgmentRequest` (reason_code, rationale)
  - [ ] Add `EscalationAcknowledgmentResponse` (acknowledgment_id, petition_id, king_id, reason_code, acknowledged_at)

### Task 7: Write Unit Tests
- [ ] Create `tests/unit/application/services/test_king_acknowledgment.py`
  - [ ] Test successful King acknowledgment
  - [ ] Test rationale too short (< 100 chars)
  - [ ] Test petition not escalated
  - [ ] Test realm mismatch
  - [ ] Test halt check
  - [ ] Test King ID recorded correctly
  - [ ] Test event emission

### Task 8: Write Integration Tests
- [ ] Create `tests/integration/test_king_acknowledgment_endpoint.py`
  - [ ] Test POST endpoint success (200)
  - [ ] Test 400 for short rationale
  - [ ] Test 400 for petition not escalated
  - [ ] Test 403 for realm mismatch
  - [ ] Test 404 for petition not found
  - [ ] Test 503 during halt
  - [ ] Test acknowledgment persisted with king_id
  - [ ] Test event witnessed

### Task 9: Update Repository
- [ ] Update `src/application/ports/acknowledgment_execution.py`
  - [ ] Add `acknowledged_by_king_id` parameter to repository protocol if needed
- [ ] Update stub implementation
  - [ ] Handle `acknowledged_by_king_id` in acknowledgment creation

## Documentation Checklist

- [ ] Inline comments for King-specific acknowledgment logic
- [ ] API documentation for new endpoint
- [ ] Event documentation for KingAcknowledgedEscalation

## Dev Notes

### Pattern Consistency

This story follows the same pattern as:
- **Story 6.3:** King adoption endpoint (realm auth, halt check, error handling)
- **Story 3.2:** Acknowledgment execution service (reason code validation, event emission)
- **Story 4.6:** System acknowledgment (bypassing certain validations)

### Key Differences from Marquis Acknowledgment

1. **State Validation:** ESCALATED (not DELIBERATING)
2. **Rationale Length:** 100 chars minimum (vs flexible for Marquis)
3. **Archon IDs:** Empty (King acts alone, not via deliberation)
4. **Event Type:** KingAcknowledgedEscalation (distinct from PetitionAcknowledged)
5. **Realm Authorization:** Must match petition's realm (RULING-3)

### Constitutional Significance

King acknowledgments are constitutionally significant because:
- They resolve escalations that reached the highest level
- They provide formal response to petitioners who gathered significant co-signers
- They demonstrate accountability in the governance hierarchy
- They preserve the dignity of petitioners (FR-5.8 rationale requirement)

## References

- [Source: _bmad-output/planning-artifacts/petition-system-epics.md#Story 6.5]
- [Source: src/application/services/acknowledgment_execution_service.py] - Acknowledgment pattern
- [Source: src/application/services/petition_adoption_service.py] - King action pattern (Story 6.3)
- [Source: src/api/routes/escalation.py] - King escalation endpoints (Stories 6.1-6.3)
- [Source: src/domain/models/acknowledgment_reason.py] - Reason code enum
