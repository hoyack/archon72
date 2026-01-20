# Story 6.1: King Escalation Queue

## Story

**ID:** petition-6-1-king-escalation-queue
**Epic:** Petition Epic 6: King Escalation & Adoption Bridge
**Priority:** P0
**Status:** ready-for-dev

As a **King**,
I want to access my escalation queue distinct from organic Motions,
So that I can review petitions that require my attention.

## Acceptance Criteria

### AC1: King Escalation Queue Endpoint
**Given** I am an authenticated King
**When** I GET `/api/v1/kings/{king_id}/escalations`
**Then** I receive a paginated list of escalated petitions assigned to my realm
**And** the list is distinct from my organic Motion queue
**And** each entry includes:
  - `petition_id`: UUID
  - `petition_type`: CESSATION, GRIEVANCE, GENERAL, COLLABORATION
  - `escalation_source`: DELIBERATION, CO_SIGNER_THRESHOLD, KNIGHT_RECOMMENDATION
  - `co_signer_count`: integer
  - `escalated_at`: timestamp (ISO 8601)
**And** pagination uses keyset cursors (D8 compliance)

### AC2: Empty Queue Handling
**Given** no escalations are pending for my realm
**When** I query the escalation queue
**Then** I receive an empty list (not an error)
**And** HTTP 200 with `items: []` and `next_cursor: null`

### AC3: Realm-Scoped Queue
**Given** I am a King with realm "governance"
**When** I query my escalation queue
**Then** I only see petitions escalated to the "governance" realm
**And** I do NOT see petitions from other realms

### AC4: Queue Ordering (Oldest First)
**Given** multiple petitions are escalated to my realm
**When** I query my escalation queue
**Then** petitions are ordered by `escalated_at` ascending (oldest first)
**And** this ensures fair processing order (FIFO)

### AC5: Halt Check First (CT-13)
**Given** the system is in HALTED state
**When** I attempt to query my escalation queue
**Then** the request is rejected with HTTP 503 Service Unavailable
**And** the response indicates "SYSTEM_HALTED"

### AC6: King Authorization
**Given** I am NOT a King-rank Archon
**When** I attempt to access `/api/v1/kings/{king_id}/escalations`
**Then** the system returns HTTP 403 Forbidden
**And** the attempt is logged

## References

- **FR-5.4:** King SHALL receive escalation queue distinct from organic Motions [P0]
- **NFR-1.3:** Endpoint latency < 200ms p95
- **CT-13:** Halt check first pattern
- **D8:** Keyset pagination compliance
- **RULING-3:** Realm-scoped data access

## Tasks/Subtasks

### Task 1: Create Escalation Queue Port
- [ ] Create `src/application/ports/escalation_queue.py`
  - [ ] `EscalationQueueItem` dataclass (petition_id, type, source, co_signer_count, escalated_at)
  - [ ] `EscalationSource` enum (DELIBERATION, CO_SIGNER_THRESHOLD, KNIGHT_RECOMMENDATION)
  - [ ] `EscalationQueueResult` dataclass (items, next_cursor, has_more)
  - [ ] `EscalationQueueProtocol` with `get_queue(king_id, realm_id, cursor, limit)` method
- [ ] Add exports to `src/application/ports/__init__.py`
- [ ] Document constitutional constraints (FR-5.4, CT-13)

### Task 2: Create Escalation Queue Service
- [ ] Create `src/application/services/escalation_queue_service.py`
  - [ ] Implement `EscalationQueueProtocol`
  - [ ] Inject: petition_repo, halt_circuit
  - [ ] HALT CHECK FIRST pattern (CT-13)
  - [ ] Filter by realm_id for King's realm
  - [ ] Order by escalated_at ascending (FIFO)
  - [ ] Keyset pagination using escalated_at + petition_id
  - [ ] Log with structlog (no f-strings)
- [ ] Add exports to `src/application/services/__init__.py`

### Task 3: Create Escalation Queue Stub (Testing)
- [ ] Create `src/infrastructure/stubs/escalation_queue_stub.py`
  - [ ] In-memory tracking of escalated petitions
  - [ ] Support for adding test escalations
  - [ ] Filtering by realm_id
  - [ ] Cursor-based pagination simulation
- [ ] Add exports to `src/infrastructure/stubs/__init__.py`

### Task 4: Add Escalation Tracking Fields to Petition
- [ ] Update `src/domain/models/petition_submission.py`
  - [ ] Add `escalation_source: EscalationSource | None` field
  - [ ] Add `escalated_at: datetime | None` field
  - [ ] Add `escalated_to_realm: str | None` field (target King's realm)
  - [ ] Update `with_state()` to populate escalation fields when transitioning to ESCALATED
- [ ] Create migration `migrations/026_add_escalation_tracking_fields.sql`
  - [ ] Add `escalation_source` column (text, nullable)
  - [ ] Add `escalated_at` column (timestamptz, nullable)
  - [ ] Add `escalated_to_realm` column (text, nullable)
  - [ ] Add index on (escalated_to_realm, escalated_at) for queue queries

### Task 5: Create API Endpoint
- [ ] Create `src/api/routes/escalation.py`
  - [ ] `GET /api/v1/kings/{king_id}/escalations` route
  - [ ] Query params: `cursor`, `limit` (default 20, max 100)
  - [ ] King authorization check using permission enforcer
  - [ ] Halt check before processing
  - [ ] Return RFC 7807 errors with governance extensions
- [ ] Create `src/api/models/escalation.py`
  - [ ] `EscalationQueueItemResponse` model
  - [ ] `EscalationQueueResponse` model (items, next_cursor, has_more)
- [ ] Create `src/api/dependencies/escalation.py`
  - [ ] `get_escalation_queue_service()` singleton
  - [ ] `set_escalation_queue_service()` for testing

### Task 6: Register Route
- [ ] Update `src/api/routes/__init__.py` to include escalation router
- [ ] Update `src/api/main.py` to register escalation routes

### Task 7: Write Unit Tests
- [ ] Create `tests/unit/application/services/test_escalation_queue_service.py`
  - [ ] Test empty queue returns empty list
  - [ ] Test realm filtering
  - [ ] Test FIFO ordering
  - [ ] Test keyset pagination
  - [ ] Test halt check first
  - [ ] Test with multiple escalation sources

### Task 8: Write Integration Tests
- [ ] Create `tests/integration/test_escalation_queue_endpoint.py`
  - [ ] Test endpoint returns 200 with escalated petitions
  - [ ] Test empty queue returns 200 with empty list
  - [ ] Test realm isolation
  - [ ] Test pagination cursor navigation
  - [ ] Test 403 for non-King access
  - [ ] Test 503 during system halt

### Task 9: Update Auto-Escalation to Populate Fields
- [ ] Update `src/application/services/auto_escalation_executor_service.py`
  - [ ] Populate `escalation_source = CO_SIGNER_THRESHOLD`
  - [ ] Populate `escalated_at = utc_now()`
  - [ ] Populate `escalated_to_realm` based on petition realm
- [ ] Update `src/application/services/disposition_emission_service.py` (if deliberation ESCALATE)
  - [ ] Populate `escalation_source = DELIBERATION`
  - [ ] Populate escalation fields when routing ESCALATE disposition

## Documentation Checklist

- [ ] Architecture docs updated (if patterns/structure changed)
- [ ] API docs updated (if endpoints/contracts changed)
- [ ] README updated (if setup/usage changed)
- [ ] Inline comments added for complex logic
- [ ] N/A - no documentation impact (explain why)

## Dev Notes

### Architecture Patterns

This story follows established patterns from Epic 5:
- **Port → Service → Stub pattern** for clean protocol-first design
- **Keyset pagination** per D8 compliance (not offset-based)
- **HALT CHECK FIRST** per CT-13 in all entry points
- **RFC 7807 errors** with governance extensions

### Existing Components to Leverage

1. **PetitionSubmission model** (`src/domain/models/petition_submission.py`)
   - Already has ESCALATED state
   - Need to add escalation_source, escalated_at, escalated_to_realm fields

2. **EscalationTriggeredEvent** (`src/domain/events/petition_escalation.py`)
   - Already emits escalation events
   - Contains trigger_type which maps to escalation_source

3. **AutoEscalationExecutorService** (`src/application/services/auto_escalation_executor_service.py`)
   - Already handles CO_SIGNER_THRESHOLD escalations
   - Need to populate new escalation tracking fields

4. **HaltCircuitProtocol** (`src/application/ports/halt_circuit.py`)
   - Existing halt check pattern
   - Use `halt_circuit.is_halted()` before processing

5. **PermissionEnforcerProtocol** (`src/application/ports/permission_enforcer.py`)
   - Existing authorization pattern
   - Use to verify King rank

### Escalation Source Mapping

| Source | Description | Populated By |
|--------|-------------|--------------|
| `CO_SIGNER_THRESHOLD` | Auto-escalation from co-signer count | AutoEscalationExecutorService |
| `DELIBERATION` | Three Fates deliberation decided ESCALATE | DispositionEmissionService |
| `KNIGHT_RECOMMENDATION` | Knight recommended escalation | ReferralExecutionService |

### Database Schema

```sql
-- Migration 026: Add escalation tracking fields
ALTER TABLE petition_submissions
ADD COLUMN escalation_source TEXT,
ADD COLUMN escalated_at TIMESTAMPTZ,
ADD COLUMN escalated_to_realm TEXT;

-- Index for efficient queue queries
CREATE INDEX idx_petition_escalation_queue
ON petition_submissions (escalated_to_realm, escalated_at)
WHERE state = 'ESCALATED' AND escalated_to_realm IS NOT NULL;
```

### API Response Format

```json
{
  "items": [
    {
      "petition_id": "uuid",
      "petition_type": "CESSATION",
      "escalation_source": "CO_SIGNER_THRESHOLD",
      "co_signer_count": 150,
      "escalated_at": "2026-01-20T12:00:00Z"
    }
  ],
  "next_cursor": "base64_encoded_cursor",
  "has_more": true
}
```

### Project Structure Notes

- Follow hexagonal architecture: ports in `application/ports/`, services in `application/services/`
- Stubs in `infrastructure/stubs/` for testing without DB
- API routes in `api/routes/`, models in `api/models/`, dependencies in `api/dependencies/`
- Migrations in `migrations/` with sequential numbering

### Testing Standards

- Unit tests in `tests/unit/` mirroring source structure
- Integration tests in `tests/integration/` for API flows
- Use pytest-asyncio for async tests
- Use FastAPI TestClient for endpoint tests
- Minimum 80% coverage for new code

### References

- [Source: _bmad-output/planning-artifacts/petition-system-epics.md#Epic 6]
- [Source: src/application/ports/king_service.py] - Motion structure and King patterns
- [Source: src/application/services/auto_escalation_executor_service.py] - Escalation patterns
- [Source: src/domain/models/petition_submission.py] - Petition state machine

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List
