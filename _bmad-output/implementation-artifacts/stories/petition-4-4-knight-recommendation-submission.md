# Story 4.4: Knight Recommendation Submission

## Story Status: ready-for-dev

| Attribute          | Value                                    |
| ------------------ | ---------------------------------------- |
| Epic               | Epic 4: Knight Referral Workflow         |
| Story ID           | petition-4-4                             |
| Story Points       | 8                                        |
| Priority           | P0                                       |
| Status             | ready-for-dev                            |
| Created            | 2026-01-20                               |
| Updated            | 2026-01-20                               |
| Constitutional Ref | FR-4.6, CT-12, NFR-3.2, NFR-5.2          |

## Story

As a **Knight**,
I want to submit my recommendation with mandatory rationale,
So that the petition can proceed to its final disposition.

## Constitutional Context

- **FR-4.6**: Knight SHALL submit recommendation with mandatory rationale [P0]
- **CT-12**: Every action that affects an Archon must be witnessed
- **NFR-3.2**: Fate assignment atomicity: 100% single-fate [CRITICAL]
- **NFR-5.2**: Authorization: Only assigned Knight can submit recommendation

From PRD Section 8.3 - Recommendation:
- Knight's formal response: ACKNOWLEDGE or ESCALATE
- Mandatory rationale required for all recommendations
- Routes petition to next step based on recommendation

From PRD Section 15.4 - The Knight Journey:
```
Review petition + related context → Formulate recommendation
    → Submit recommendation with rationale → Petition proceeds to next fate
```

## Acceptance Criteria

### AC-1: Recommendation Submission
**Given** I am a Knight with an assigned referral in IN_REVIEW status
**When** I POST `/api/v1/referrals/{referral_id}/recommendation` with:
  - `recommendation`: ACKNOWLEDGE or ESCALATE
  - `rationale`: non-empty text explaining my decision
**Then** the recommendation is recorded on the referral
**And** the referral status transitions to COMPLETED
**And** a `ReferralCompletedEvent` is emitted with witness hash (CT-12)

- [ ] Create `RecommendationSubmissionProtocol` in `src/application/ports/recommendation_submission.py`
- [ ] Implement `RecommendationSubmissionService` in `src/application/services/recommendation_submission_service.py`
- [ ] Service validates Knight authorization (NFR-5.2)
- [ ] Service validates referral state (must be IN_REVIEW)
- [ ] Service updates referral with recommendation via `with_recommendation()`
- [ ] Service emits `ReferralCompletedEvent` with witness hash

### AC-2: Recommendation Validation
**Given** I submit a recommendation
**When** the request is validated
**Then** the system validates:
  - `recommendation` is valid enum value (ACKNOWLEDGE or ESCALATE)
  - `rationale` is non-empty string (minimum 10 characters)
  - Referral exists and is in IN_REVIEW status
  - Requester is the assigned Knight (NFR-5.2)

- [ ] Add input validation for recommendation enum
- [ ] Add input validation for rationale (non-empty, min 10 chars)
- [ ] Return HTTP 400 with specific validation errors
- [ ] Create `InvalidRecommendationError` domain error
- [ ] Create `RationaleRequiredError` domain error

### AC-3: Authorization Enforcement
**Given** a recommendation submission request
**When** the request includes a requester_id
**Then** the system validates:
  - The referral exists
  - The referral status is IN_REVIEW
  - The requester_id matches the assigned_knight_id (NFR-5.2)
**And** rejects unauthorized access with HTTP 403

- [ ] Add authorization check in service
- [ ] Return `UnauthorizedRecommendationError` if requester != assigned_knight_id
- [ ] Return HTTP 403 for authorization failures

### AC-4: Petition Routing Based on Recommendation
**Given** a valid recommendation is submitted
**When** the recommendation is ACKNOWLEDGE
**Then** the petition is routed to Acknowledgment execution (Epic 3)
**And** an acknowledgment is created with reason code KNIGHT_REFERRAL

**Given** a valid recommendation is submitted
**When** the recommendation is ESCALATE
**Then** the petition is routed to King escalation queue (Epic 6)
**And** an escalation is queued with Knight rationale

- [ ] Implement routing logic based on recommendation
- [ ] For ACKNOWLEDGE: Call `AcknowledgmentExecutionService` with reason KNIGHT_REFERRAL
- [ ] For ESCALATE: Queue petition for King escalation (stub until Epic 6)
- [ ] Emit appropriate routing events

### AC-5: Deadline Job Cancellation
**Given** a recommendation is submitted successfully
**When** the referral is marked COMPLETED
**Then** the pending deadline timeout job is cancelled
**And** NFR-3.4 compliance is maintained (no orphaned jobs)

- [ ] Cancel deadline job via `JobSchedulerProtocol.cancel()`
- [ ] Handle case where job already executed (idempotent)

### AC-6: REST API Endpoint
**Given** an assigned Knight in review
**When** they call `POST /api/v1/referrals/{referral_id}/recommendation`
**Then** the recommendation is submitted
**And** the endpoint returns:
  - 200: Recommendation accepted, petition routed
  - 400: Validation error (invalid recommendation, missing rationale)
  - 401: Unauthorized (no auth)
  - 403: Forbidden (not assigned Knight or wrong referral state)
  - 404: Referral not found

- [ ] Create API endpoint in `src/api/routes/referral_routes.py` (stub for now)
- [ ] Add Pydantic request model `RecommendationRequest`
- [ ] Add Pydantic response model `RecommendationResponse`
- [ ] Return appropriate HTTP status codes

### AC-7: Unit Tests
**Given** the RecommendationSubmissionService
**When** unit tests run
**Then** tests verify:
  - Successful recommendation submission (ACKNOWLEDGE)
  - Successful recommendation submission (ESCALATE)
  - Authorization enforcement (wrong knight)
  - Referral state validation (not IN_REVIEW)
  - Rationale validation (empty, too short)
  - Recommendation enum validation
  - Event emission with witness hash
  - Routing logic for both recommendations

- [ ] Create `tests/unit/application/services/test_recommendation_submission_service.py`
- [ ] Test successful ACKNOWLEDGE submission
- [ ] Test successful ESCALATE submission
- [ ] Test authorization failure (wrong knight)
- [ ] Test referral state validation
- [ ] Test rationale validation
- [ ] Test witness hash generation
- [ ] Test routing logic

### AC-8: Integration Tests
**Given** the recommendation submission flow
**When** integration tests run
**Then** tests verify:
  - End-to-end submission with stubs
  - Event emission verification
  - Routing to acknowledgment/escalation
  - Job cancellation

- [ ] Create `tests/integration/test_recommendation_submission_integration.py`
- [ ] Test full ACKNOWLEDGE flow with AcknowledgmentExecutionService
- [ ] Test ESCALATE flow with stub escalation handler
- [ ] Verify event contents and witness hash

## Tasks / Subtasks

### Task 1: Create Domain Errors
- [ ] Create/update `src/domain/errors/recommendation.py`
  - [ ] Define `InvalidRecommendationError`
  - [ ] Define `RationaleRequiredError` (min 10 chars)
  - [ ] Define `UnauthorizedRecommendationError`
  - [ ] Define `ReferralNotInReviewError`
  - [ ] Define `RecommendationAlreadySubmittedError`
- [ ] Export in `src/domain/errors/__init__.py`

### Task 2: Create Protocol Port
- [ ] Create `src/application/ports/recommendation_submission.py`
  - [ ] Define `RecommendationSubmissionProtocol`
  - [ ] Method: `submit(referral_id, requester_id, recommendation, rationale) -> Referral`
  - [ ] Document Constitutional refs in docstrings
- [ ] Export in `src/application/ports/__init__.py`

### Task 3: Implement Recommendation Submission Service
- [ ] Create `src/application/services/recommendation_submission_service.py`
  - [ ] Inject dependencies: referral_repo, petition_repo, event_writer, job_scheduler, hash_service, acknowledgment_service
  - [ ] Implement `submit()` method with:
    - [ ] Authorization check (requester == assigned_knight_id)
    - [ ] Referral state validation (must be IN_REVIEW)
    - [ ] Rationale validation (non-empty, min 10 chars)
    - [ ] Call `referral.with_recommendation()` to update state
    - [ ] Save updated referral
    - [ ] Generate witness hash (CT-12)
    - [ ] Emit `ReferralCompletedEvent`
    - [ ] Cancel deadline job
    - [ ] Route petition based on recommendation
- [ ] Export in `src/application/services/__init__.py`

### Task 4: Implement ACKNOWLEDGE Routing
- [ ] In service, implement ACKNOWLEDGE routing:
  - [ ] Call `AcknowledgmentExecutionService.execute()` with:
    - [ ] petition_id
    - [ ] reason_code = KNIGHT_REFERRAL
    - [ ] rationale from Knight's recommendation
    - [ ] reference to referral_id
  - [ ] Add new `AcknowledgmentReasonCode.KNIGHT_REFERRAL` if not exists

### Task 5: Implement ESCALATE Routing (Stub)
- [ ] In service, implement ESCALATE routing stub:
  - [ ] Create escalation queue entry (stub until Epic 6)
  - [ ] Emit `PetitionEscalatedEvent` (stub event)
  - [ ] Log escalation with rationale

### Task 6: Create Stub Implementation
- [ ] Create `src/infrastructure/stubs/recommendation_submission_stub.py`
  - [ ] Implement in-memory stub for testing
- [ ] Export in `src/infrastructure/stubs/__init__.py`

### Task 7: Create Unit Tests
- [ ] Create `tests/unit/application/services/test_recommendation_submission_service.py`
  - [ ] Test successful ACKNOWLEDGE submission
  - [ ] Test successful ESCALATE submission
  - [ ] Test authorization failure (wrong knight)
  - [ ] Test referral not found
  - [ ] Test referral wrong state (not IN_REVIEW)
  - [ ] Test empty rationale
  - [ ] Test rationale too short (<10 chars)
  - [ ] Test invalid recommendation enum
  - [ ] Test event emission with witness hash
  - [ ] Test job cancellation
  - [ ] Test ACKNOWLEDGE routing to acknowledgment service
  - [ ] Test ESCALATE routing to escalation stub

### Task 8: Create Integration Tests
- [ ] Create `tests/integration/test_recommendation_submission_integration.py`
  - [ ] Test end-to-end ACKNOWLEDGE flow
  - [ ] Test end-to-end ESCALATE flow
  - [ ] Verify event emission and witness hash
  - [ ] Verify referral state changes
  - [ ] Verify job cancellation

### Task 9: Update Exports
- [ ] Update `src/domain/errors/__init__.py`
- [ ] Update `src/application/ports/__init__.py`
- [ ] Update `src/application/services/__init__.py`
- [ ] Update `src/infrastructure/stubs/__init__.py`

## Documentation Checklist

- [ ] Architecture docs updated (if patterns/structure changed)
- [ ] API docs updated (if endpoints/contracts changed)
- [ ] README updated (if setup/usage changed)
- [ ] Inline comments added for complex logic
- [ ] N/A - no documentation impact (service layer implementation follows existing patterns)

## Dev Notes

### Architecture Patterns to Follow

1. **Hexagonal Architecture**: Use protocol ports with service implementations
2. **Frozen Dataclasses**: All domain models are frozen for immutability (CT-12)
3. **Dependency Injection**: Service receives all dependencies in constructor
4. **Constitutional Comments**: Document FR/NFR refs in docstrings
5. **Witness Chain**: All state-changing operations require witness hash (CT-12)

### Previous Story Learnings (Story 4.3)

- Pattern reference: `DecisionPackageBuilderService` shows proper authorization pattern
- Authorization must be explicit: check `requester_id == assigned_knight_id`
- Use `structlog` for structured logging with bound context
- Referral domain model has `with_recommendation()` method already implemented
- `ReferralCompletedEvent` already exists in `src/domain/events/referral.py`

### Technical Constraints

1. **Authorization (NFR-5.2)**: Only assigned Knight can submit
2. **Referral State**: Must be IN_REVIEW to accept recommendation
3. **Rationale Required (FR-4.6)**: Minimum 10 characters
4. **Atomic State Change (NFR-3.2)**: Recommendation + state change atomic
5. **CT-12 Witnessing**: All changes witnessed with BLAKE3 hash

### Dependencies

- `src/domain/models/referral.py` - Referral model with `with_recommendation()` (Story 4.1) ✓
- `src/domain/events/referral.py` - `ReferralCompletedEvent` (Story 4.2) ✓
- `src/application/ports/referral_execution.py` - `ReferralRepositoryProtocol` (Story 4.2) ✓
- `src/application/services/acknowledgment_execution_service.py` - For ACKNOWLEDGE routing (Story 3.2) ✓
- `src/application/ports/job_scheduler.py` - For deadline job cancellation ✓
- `src/application/ports/content_hash.py` - For witness hash generation ✓

### Existing Code to Leverage

1. **`Referral.with_recommendation()`** - Domain method already implemented:
   ```python
   def with_recommendation(
       self,
       recommendation: ReferralRecommendation,
       rationale: str,
       completed_at: Optional[datetime] = None,
   ) -> Referral:
       """Create a new referral with Knight's recommendation."""
   ```

2. **`ReferralCompletedEvent`** - Event already defined:
   ```python
   @dataclass(frozen=True)
   class ReferralCompletedEvent:
       event_id: UUID
       referral_id: UUID
       petition_id: UUID
       knight_id: UUID
       recommendation: str
       rationale: str
       completed_at: datetime
       witness_hash: str
   ```

3. **`ReferralRecommendation`** - Enum already defined:
   ```python
   class ReferralRecommendation(str, Enum):
       ACKNOWLEDGE = "acknowledge"
       ESCALATE = "escalate"
   ```

### API Endpoint Design

```
POST /api/v1/referrals/{referral_id}/recommendation

Authorization: Bearer <knight_token>

Request Body:
{
  "recommendation": "acknowledge" | "escalate",
  "rationale": "string (min 10 chars)"
}

Response 200:
{
  "referral_id": "uuid",
  "petition_id": "uuid",
  "recommendation": "acknowledge",
  "rationale": "Knight's rationale text",
  "completed_at": "2026-01-20T12:00:00Z",
  "routing": {
    "destination": "acknowledgment",
    "reason_code": "KNIGHT_REFERRAL"
  }
}

Response 400:
{
  "error": "validation_error",
  "message": "Rationale must be at least 10 characters",
  "field": "rationale"
}

Response 403:
{
  "error": "unauthorized_recommendation",
  "message": "Only the assigned Knight can submit recommendations"
}

Response 404:
{
  "error": "referral_not_found",
  "message": "Referral not found"
}
```

### Service Dependencies Diagram

```
RecommendationSubmissionService
    ├── ReferralRepositoryProtocol (get/save referral)
    ├── PetitionSubmissionRepositoryProtocol (update petition state)
    ├── EventWriterProtocol (emit ReferralCompletedEvent)
    ├── JobSchedulerProtocol (cancel deadline job)
    ├── ContentHashProtocol (witness hash generation)
    ├── AcknowledgmentExecutionService (ACKNOWLEDGE routing)
    └── EscalationQueueService (ESCALATE routing - stub)
```

### Project Structure Notes

Files to create:
- `src/domain/errors/recommendation.py` - New file
- `src/application/ports/recommendation_submission.py` - New file
- `src/application/services/recommendation_submission_service.py` - New file
- `src/infrastructure/stubs/recommendation_submission_stub.py` - New file
- `tests/unit/application/services/test_recommendation_submission_service.py` - New file
- `tests/integration/test_recommendation_submission_integration.py` - New file

May need to update:
- `src/domain/models/acknowledgment_reason.py` - Add KNIGHT_REFERRAL reason code if not exists

### References

- [Source: _bmad-output/planning-artifacts/petition-system-prd.md#FR-4.6]
- [Source: _bmad-output/planning-artifacts/petition-system-prd.md#Section 8.3 Recommendation]
- [Source: _bmad-output/planning-artifacts/petition-system-prd.md#Section 15.4 The Knight]
- [Source: _bmad-output/planning-artifacts/petition-system-epics.md#Story 4.4]
- [Source: src/domain/models/referral.py#with_recommendation] - Domain method
- [Source: src/domain/events/referral.py#ReferralCompletedEvent] - Event class
- [Source: src/application/services/decision_package_service.py] - Authorization pattern reference
- [Source: src/application/services/acknowledgment_execution_service.py] - ACKNOWLEDGE routing reference

---

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List

### Change Log

| Date | Change | Author |
|------|--------|--------|
| 2026-01-20 | Story file created with comprehensive context | Claude Opus 4.5 |
