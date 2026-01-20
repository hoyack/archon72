# Story 5.6: Auto-Escalation Execution

## Story

**ID:** petition-5-6-auto-escalation-execution
**Epic:** Petition Epic 5: Co-signing & Auto-Escalation
**Priority:** P0

As a **system**,
I want to execute auto-escalation when co-signer threshold is reached,
So that petitions with collective support bypass deliberation and reach King attention.

## Acceptance Criteria

### AC1: Auto-Escalation State Transition
**Given** a petition reaches its escalation threshold (detected by Story 5.5)
**When** auto-escalation executes
**Then** the petition state transitions: RECEIVED → ESCALATED (bypasses DELIBERATING)
**And** the state machine allows RECEIVED → ESCALATED transition
**And** the transition is atomic (all-or-nothing)

### AC2: EscalationTriggered Event Emission
**Given** auto-escalation is triggered
**When** the escalation completes
**Then** an `EscalationTriggered` event is emitted with:
  - `petition_id`: UUID of the escalated petition
  - `trigger_type`: "CO_SIGNER_THRESHOLD"
  - `co_signer_count`: Count at time of trigger
  - `threshold`: The threshold that was reached (100 or 50)
  - `schema_version`: 1 (D2 compliance)
**And** the event is witnessed via EventWriterService (CT-12)

### AC3: King Escalation Queue Routing
**Given** auto-escalation completes
**When** the petition reaches ESCALATED state
**Then** the petition is routed to King escalation queue
**And** escalation_source is set to "CO_SIGNER_THRESHOLD"
**And** the realm_id determines which King queue receives it

### AC4: Deliberation Cancellation (If Active)
**Given** auto-escalation is triggered
**When** the petition was in DELIBERATING state
**Then** the deliberation is cancelled gracefully
**And** a `DeliberationCancelled` event is emitted with reason "AUTO_ESCALATED"
**And** all Fate Archons in the session are notified
**And** the deliberation session transcript is preserved

### AC5: Idempotent Execution
**Given** a petition that has already been escalated
**When** additional co-signs trigger threshold again
**Then** no duplicate escalation occurs
**And** the response indicates escalation already triggered
**And** `escalation_triggered` field is true in co-sign response

### AC6: Integration with Co-Sign Flow
**Given** a co-sign that triggers threshold (Story 5.5 detection)
**When** the co-sign submission completes
**Then** auto-escalation executes synchronously (same request)
**And** `escalation_triggered` is true in response
**And** total response latency remains < 500ms p95 (NFR-1.4 extension)

### AC7: Witness Everything (CT-12)
**Given** auto-escalation execution
**When** the transition occurs
**Then** all events are witnessed in same transaction
**And** witness includes actor attribution (SYSTEM or triggering signer)
**And** audit trail can reconstruct escalation reason

## References

- **FR-5.1:** System SHALL ESCALATE petition when co-signer threshold reached [P0]
- **FR-5.3:** System SHALL emit EscalationTriggered event with co-signer_count [P0]
- **FR-10.2:** CESSATION petitions SHALL auto-escalate at 100 co-signers [P0]
- **FR-10.3:** GRIEVANCE petitions SHALL auto-escalate at 50 co-signers [P1]
- **NFR-1.4:** Escalation trigger detection < 1 second
- **CT-12:** All outputs through witnessing pipeline
- **CT-14:** Silence must be expensive (escalation ensures petitions don't stall)

## Tasks/Subtasks

### Task 1: Update State Transition Matrix
- [x] Update `src/domain/models/petition_submission.py`
  - [x] Add RECEIVED → ESCALATED transition (bypass DELIBERATING for auto-escalation)
  - [x] Document constitutional justification for direct transition
  - [x] Ensure terminal state behavior unchanged
- [x] Add unit tests for new transition

### Task 2: Create Auto-Escalation Executor Port
- [x] Create `src/application/ports/auto_escalation_executor.py`
  - [x] `AutoEscalationResult` dataclass (escalation_id, petition_id, triggered, event_id, timestamp)
  - [x] `AutoEscalationExecutorProtocol` with `execute(petition_id, trigger_type, co_signer_count, threshold)` method
  - [x] `check_already_escalated(petition_id)` method for idempotency
- [x] Add exports to `src/application/ports/__init__.py`
- [x] Document constitutional constraints (FR-5.1, FR-5.3, CT-12)

### Task 3: Create EscalationTriggered Event
- [x] Create or update `src/domain/events/petition_escalation.py`
  - [x] `EscalationTriggeredEvent` dataclass
  - [x] Required fields: petition_id, trigger_type, co_signer_count, threshold, schema_version
  - [x] `signable_content()` method for CT-12 witnessing
  - [x] `to_dict()` method (NOT asdict - D2 compliance)
- [x] Add event type constant: `ESCALATION_TRIGGERED_EVENT_TYPE = "petition.escalation.triggered"`
- [x] Add exports to `src/domain/events/__init__.py`

### Task 4: Create DeliberationCancelled Event (Optional Path)
- [x] Create `src/domain/events/deliberation_cancelled.py` (if not exists)
  - [x] `DeliberationCancelledEvent` dataclass
  - [x] Required fields: session_id, petition_id, cancel_reason, cancelled_at, schema_version
  - [x] Cancel reason enum: AUTO_ESCALATED, TIMEOUT, MANUAL
- [x] Add exports to `src/domain/events/__init__.py`

### Task 5: Create Auto-Escalation Executor Service
- [x] Create `src/application/services/auto_escalation_executor_service.py`
  - [x] Implement `AutoEscalationExecutorProtocol`
  - [x] Inject: petition_repo, event_writer, deliberation_service (optional)
  - [x] HALT CHECK FIRST pattern (CT-13)
  - [x] Atomic state transition + event emission
  - [x] Cancel active deliberation if in DELIBERATING state
  - [x] Log with structlog (no f-strings)
- [x] Add exports to `src/application/services/__init__.py`

### Task 6: Create Auto-Escalation Executor Stub (Testing)
- [x] Create `src/infrastructure/stubs/auto_escalation_executor_stub.py`
  - [x] In-memory tracking of escalations
  - [x] Configurable success/failure for testing
  - [x] Track escalation history for assertions
- [x] Add exports to `src/infrastructure/stubs/__init__.py`

### Task 7: Integrate Executor into Co-Sign Submission Service
- [x] Update `src/application/services/co_sign_submission_service.py`
  - [x] Add `AutoEscalationExecutorProtocol` optional dependency
  - [x] Execute auto-escalation when `threshold_reached=True`
  - [x] Add `escalation_triggered` field to result
  - [x] Update service documentation
- [x] Update constructor signature

### Task 8: Update Co-Sign Submission Result
- [x] Update `src/application/ports/co_sign_submission.py`
  - [x] Add `escalation_triggered: bool` field (default False)
  - [x] Add `escalation_id: UUID | None` field (default None)
- [x] Update `src/api/models/co_sign.py` response model

### Task 9: Update API Dependencies
- [x] Update `src/api/dependencies/co_sign.py`
  - [x] Add `get_auto_escalation_executor()` singleton function
  - [x] Update `get_co_sign_submission_service()` to include executor
  - [x] Add `set_auto_escalation_executor()` for testing
  - [x] Update `reset_co_sign_dependencies()` to include executor

### Task 10: Write Unit Tests for Executor Service
- [x] Create `tests/unit/application/services/test_auto_escalation_executor_service.py`
  - [x] Test successful escalation from RECEIVED state
  - [x] Test HALT CHECK prevents execution
  - [x] Test idempotency (already escalated)
  - [x] Test event emission with correct fields
  - [x] Test deliberation cancellation path
  - [x] Test witness attribution

### Task 11: Write Unit Tests for Event Payloads
- [x] Create `tests/unit/domain/events/test_escalation_triggered_event.py`
  - [x] Test signable_content() produces deterministic bytes
  - [x] Test to_dict() serializes correctly (UUID, datetime)
  - [x] Test schema_version is included (D2)
- [x] Create `tests/unit/domain/events/test_deliberation_cancelled_event.py`
  - [x] Test all cancel reasons
  - [x] Test validation (escalation_id required for AUTO_ESCALATED)
  - [x] Test signable_content() and to_dict()

### Task 12: Write Integration Tests
- [x] Create `tests/integration/test_auto_escalation_execution_integration.py`
  - [x] Test co-sign triggers auto-escalation at threshold
  - [x] Test CESSATION escalates at 100 co-signers
  - [x] Test GRIEVANCE escalates at 50 co-signers
  - [x] Test response includes escalation_triggered=True
  - [x] Test idempotency (duplicate trigger)
  - [x] Test executor failure does not fail co-sign
  - [x] Test progression to threshold and escalation

### Task 13: Write Deliberation Cancellation Tests
- [x] Add tests to `tests/integration/test_deliberation_cancellation.py`
  - [x] Test escalation during active deliberation
  - [x] Test DeliberationCancelled event emitted
  - [x] Test transcript preserved

## Dev Notes

### Architecture Context
- **Extends Story 5.5:** Threshold detection returns `threshold_reached=True`; this story executes the escalation
- **State Machine Update:** RECEIVED → ESCALATED is a new valid transition (bypasses DELIBERATING)
- **Constitutional:** CT-14 "Silence must be expensive" - auto-escalation ensures collective petitions get King attention

### Existing Patterns to Follow
- `src/application/services/escalation_threshold_service.py` - Story 5.5 threshold detection
- `src/domain/events/escalation.py` - Existing escalation event patterns (breach escalation)
- `src/application/services/co_sign_submission_service.py` - Integration point

### Integration Order
The co-sign submission flow order (updated):
1. Halt check (CT-13)
2. Identity verification (NFR-5.2) - Story 5.3
3. Rate limit check (FR-6.6) - Story 5.4
4. Petition existence check
5. Terminal state check (FR-6.3)
6. Duplicate check (FR-6.2)
7. Persistence
8. Rate limit counter increment - Story 5.4
9. Threshold check (FR-6.5) - Story 5.5
10. **Auto-escalation execution (FR-5.1)** - THIS STORY
11. Event emission

### Key Design Decisions
1. **Synchronous execution:** Auto-escalation happens in same request as co-sign (no async job)
2. **Atomic transition:** State change + event emission in same transaction
3. **Deliberation awareness:** If petition in DELIBERATING, cancel gracefully
4. **Idempotent:** Multiple threshold triggers don't cause duplicate escalations

### State Transition Update
Current matrix allows:
- RECEIVED → DELIBERATING, ACKNOWLEDGED

Updated matrix for auto-escalation:
- RECEIVED → DELIBERATING, ACKNOWLEDGED, **ESCALATED**

This allows petitions to bypass deliberation when collective support (co-signer threshold) is reached.

### Event Schema (D2 Compliance)
```python
@dataclass(frozen=True)
class EscalationTriggeredEvent:
    escalation_id: UUID
    petition_id: UUID
    trigger_type: str  # "CO_SIGNER_THRESHOLD"
    co_signer_count: int
    threshold: int
    triggered_at: datetime
    triggered_by: UUID | None  # signer who triggered, or None for system
    schema_version: int = 1
```

### Success Response Update
```json
{
  "cosign_id": "...",
  "petition_id": "...",
  "signer_id": "...",
  "signed_at": "...",
  "identity_verified": true,
  "rate_limit_remaining": 45,
  "rate_limit_reset_at": "2026-01-20T15:00:00Z",
  "threshold_reached": true,
  "threshold_value": 100,
  "petition_type": "CESSATION",
  "escalation_triggered": true,
  "escalation_id": "uuid-of-escalation"
}
```

### Error Handling
- If escalation execution fails AFTER co-sign persists, log error but don't fail request
- Co-sign is successful even if escalation fails (can be retried by background job)
- Use structured logging for all outcomes

### Previous Story Learnings (5.5)
From Story 5.5 implementation:
- Pure calculation for threshold check worked well (no DB writes in check)
- Optional dependency pattern allows service to work without threshold checker
- Protocol compliance verification at module load catches issues early
- Integration order matters: threshold check AFTER persistence, BEFORE event

### Project Context Rules
- HALT CHECK FIRST pattern (CT-13) - check before any writes
- Use `to_dict()` not `asdict()` for events (D2)
- Include `schema_version` in all event payloads (D2)
- Structured logging with structlog (no f-strings)
- Absolute imports only
- Type hints on all functions

## File List

### Domain Layer
- `src/domain/models/petition_submission.py` - State transition matrix update
- `src/domain/events/petition_escalation.py` - EscalationTriggered event
- `src/domain/events/deliberation_cancelled.py` - DeliberationCancelled event

### Application Layer
- `src/application/ports/auto_escalation_executor.py` - Executor protocol
- `src/application/ports/co_sign_submission.py` - Result type update
- `src/application/services/auto_escalation_executor_service.py` - Executor service
- `src/application/services/co_sign_submission_service.py` - Integration

### Infrastructure Layer
- `src/infrastructure/stubs/auto_escalation_executor_stub.py` - Test stub

### API Layer
- `src/api/dependencies/co_sign.py` - Executor dependency injection
- `src/api/models/co_sign.py` - Response model update

### Tests
- `tests/unit/application/services/test_auto_escalation_executor_service.py`
- `tests/unit/domain/events/test_escalation_triggered_event.py`
- `tests/integration/test_auto_escalation_execution_integration.py`

## Documentation Checklist

- [ ] Architecture docs updated (state transition matrix change)
- [ ] API docs updated (new response fields)
- [ ] Inline comments added for state bypass logic
- [ ] N/A - no README impact

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2026-01-20 | Story created from Epic 5.6 | Create-Story Workflow |

## Status

**Status:** complete

## Dev Agent Record

### Agent Model Used
Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References
- All 104 tests passing for Story 5.6

### Completion Notes List
- Task 1: State transition matrix updated to support RECEIVED → ESCALATED and DELIBERATING → ESCALATED
- Task 2: Auto-escalation executor port created with protocol, result dataclass, and frozen constraints
- Task 3: EscalationTriggered event created with signable_content() and to_dict() for D2/CT-12 compliance
- Task 4: DeliberationCancelled event created with CancelReason enum and validation
- Task 5: Auto-escalation executor service implements halt check, idempotency, atomic transitions
- Task 6: Executor stub created with configurable success/failure and escalation history tracking
- Task 7: Co-sign submission service integrated with optional auto-escalation executor
- Task 8: Co-sign submission result updated with escalation_triggered and escalation_id fields
- Task 9: API dependencies updated with executor singleton and testing helpers
- Task 10: 22 unit tests for executor service covering all edge cases
- Task 11: 53 unit tests for event payloads (escalation triggered + deliberation cancelled)
- Task 12: 12 integration tests for full co-sign → escalation flow
- Task 13: 17 integration tests for deliberation cancellation scenarios

### File List
**Created:**
- `src/application/ports/auto_escalation_executor.py`
- `src/application/services/auto_escalation_executor_service.py`
- `src/domain/events/petition_escalation.py`
- `src/domain/events/deliberation_cancelled.py`
- `src/infrastructure/stubs/auto_escalation_executor_stub.py`
- `tests/unit/application/services/test_auto_escalation_executor_service.py`
- `tests/unit/domain/events/test_escalation_triggered_event.py`
- `tests/unit/domain/events/test_deliberation_cancelled_event.py`
- `tests/integration/test_auto_escalation_execution_integration.py`
- `tests/integration/test_deliberation_cancellation.py`

**Modified:**
- `src/domain/models/petition_submission.py` - State transition matrix
- `src/application/ports/co_sign_submission.py` - Result fields
- `src/application/services/co_sign_submission_service.py` - Executor integration
- `src/api/dependencies/co_sign.py` - Executor dependency injection
- `src/api/models/co_sign.py` - Response model fields
- `src/application/ports/__init__.py` - Exports
- `src/application/services/__init__.py` - Exports
- `src/domain/events/__init__.py` - Exports
- `src/infrastructure/stubs/__init__.py` - Exports
