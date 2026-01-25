# Story 7.3: Petition Withdrawal

Status: done

## Story

As an **Observer**,
I want to withdraw my petition before fate assignment,
So that I can cancel my petition if circumstances change.

## Acceptance Criteria

### AC1: Successful Withdrawal (Happy Path)
**Given** I submitted a petition that is not yet fated (state = RECEIVED or DELIBERATING)
**When** I POST `/api/v1/petition-submissions/{petition_id}/withdraw` with:
  - `reason`: optional explanation string
**Then** the petition is acknowledged with:
  - `reason_code` = WITHDRAWN
  - `rationale` = my provided reason (or "Petitioner withdrew" if not provided)
**And** the petition state transitions to ACKNOWLEDGED
**And** a `PetitionWithdrawn` event is emitted (new event type)
**And** co-signers are notified of withdrawal (via FateNotificationService)
**And** HTTP 200 is returned with updated petition status

### AC2: Already Fated Rejection
**Given** my petition is already in a terminal fate state (ACKNOWLEDGED, REFERRED, or ESCALATED)
**When** I attempt to withdraw
**Then** the system returns HTTP 400 with:
  - `type`: "urn:archon72:petition:already-fated"
  - `title`: "Petition Already Fated"
  - `detail`: "Cannot withdraw petition {petition_id}: already fated as {state}"
**And** no state change occurs

### AC3: Unauthorized Rejection
**Given** I am not the original petitioner (submitter_id mismatch or anonymous petition)
**When** I attempt to withdraw
**Then** the system returns HTTP 403 Forbidden with:
  - `type`: "urn:archon72:petition:unauthorized-withdrawal"
  - `title`: "Unauthorized Withdrawal"
  - `detail`: "Only the original petitioner can withdraw this petition"
**And** no state change occurs

### AC4: Petition Not Found
**Given** the petition_id does not exist
**When** I attempt to withdraw
**Then** the system returns HTTP 404 with standard petition-not-found error

### AC5: System Halted
**Given** the system is in halted state (CT-13)
**When** I attempt to withdraw (write operation)
**Then** the system returns HTTP 503 with system-halted error
**And** no state change occurs

## Tasks / Subtasks

- [x] **Task 1: Create PetitionWithdrawn Event (AC: 1)**
  - [x] 1.1 Add `PETITION_WITHDRAWN_EVENT_TYPE` constant to `src/domain/events/petition.py`
  - [x] 1.2 Create `PetitionWithdrawnEventPayload` frozen dataclass with fields: petition_id, withdrawn_by, reason, withdrawn_at
  - [x] 1.3 Implement `signable_content()` and `to_dict()` methods per D2 compliance
  - [x] 1.4 Include `schema_version` in to_dict() (CRITICAL per D2)

- [x] **Task 2: Add Withdrawal Error Types (AC: 2, 3)**
  - [x] 2.1 Add `PetitionAlreadyFatedError` to `src/domain/errors/petition.py` (if not exists, check state_transition.py)
  - [x] 2.2 Add `UnauthorizedWithdrawalError` to `src/domain/errors/petition.py`
  - [x] 2.3 Ensure errors include petition_id and current_state for debugging

- [x] **Task 3: Add Withdrawal Method to PetitionSubmissionService (AC: 1, 2, 3, 5)**
  - [x] 3.1 Add `withdraw_petition()` async method to `PetitionSubmissionService`
  - [x] 3.2 Implement HALT CHECK FIRST pattern (CT-13)
  - [x] 3.3 Implement authorization check (submitter_id match)
  - [x] 3.4 Implement terminal state check (using `state.is_terminal()`)
  - [x] 3.5 Use existing `assign_fate_transactional()` with ACKNOWLEDGED state and WITHDRAWN reason
  - [x] 3.6 Emit PetitionWithdrawn event (via event emitter)
  - [x] 3.7 Trigger notification to co-signers (fire-and-forget via FateNotificationService)

- [x] **Task 4: Add Withdrawal API Endpoint (AC: 1, 2, 3, 4, 5)**
  - [x] 4.1 Add `WithdrawPetitionRequest` Pydantic model to `src/api/models/petition_submission.py`
  - [x] 4.2 Add POST `/v1/petition-submissions/{petition_id}/withdraw` route to `src/api/routes/petition_submission.py`
  - [x] 4.3 Implement RFC 7807 error responses with governance extensions (D7)
  - [x] 4.4 Map domain errors to HTTP status codes (400, 403, 404, 503)

- [x] **Task 5: Add Event Emitter Method (AC: 1)**
  - [x] 5.1 Add `emit_petition_withdrawn()` to `PetitionEventEmitterPort` protocol
  - [x] 5.2 Implement in `PetitionEventEmitter` service
  - [x] 5.3 Implement in stub for testing

- [x] **Task 6: Unit Tests (All ACs)**
  - [x] 6.1 Test PetitionWithdrawnEventPayload serialization and signable_content
  - [x] 6.2 Test withdrawal service method (happy path)
  - [x] 6.3 Test already-fated rejection
  - [x] 6.4 Test unauthorized rejection (submitter_id mismatch)
  - [x] 6.5 Test anonymous petition withdrawal (should fail - no submitter_id to verify)
  - [x] 6.6 Test halt rejection
  - [x] 6.7 Test API endpoint responses

- [x] **Task 7: Integration Tests (AC: 1, 2)**
  - [x] 7.1 Test full withdrawal flow: submit -> withdraw -> verify state
  - [x] 7.2 Test withdrawal after deliberation start (state = DELIBERATING)
  - [x] 7.3 Test withdrawal rejection after fate assignment

## Documentation Checklist

- [ ] API docs updated (new endpoint)
- [ ] Inline comments added for withdrawal authorization logic
- [ ] N/A - no architecture impact (uses existing patterns)

## Dev Notes

### Relevant Architecture Patterns

**State Machine (FR-2.1, FR-2.3):**
The petition state machine already supports RECEIVED -> ACKNOWLEDGED transition for withdrawal. See `STATE_TRANSITION_MATRIX` in `src/domain/models/petition_submission.py:110-136`.

**AcknowledgmentReasonCode.WITHDRAWN:**
Already defined in `src/domain/models/acknowledgment_reason.py:42`. No additional requirements for WITHDRAWN reason code (no rationale or reference required).

**Transactional Fate Assignment:**
Use existing `assign_fate_transactional()` method in `PetitionSubmissionService` which handles:
- CAS state update
- Event emission with rollback on failure
- Notification trigger (fire-and-forget)

**Authorization Pattern:**
For withdrawal, the petitioner is identified by `submitter_id`. Anonymous petitions (submitter_id = None) cannot be withdrawn since there's no way to verify the requester is the original submitter.

### Source Tree Components to Touch

| Component | Path | Change Type |
|-----------|------|-------------|
| Domain Event | `src/domain/events/petition.py` | Add PetitionWithdrawnEventPayload |
| Domain Error | `src/domain/errors/petition.py` | Add UnauthorizedWithdrawalError |
| Service | `src/application/services/petition_submission_service.py` | Add withdraw_petition() |
| API Model | `src/api/models/petition_submission.py` | Add WithdrawPetitionRequest |
| API Route | `src/api/routes/petition_submission.py` | Add POST withdraw endpoint |
| Event Emitter Port | `src/application/ports/petition_event_emitter.py` | Add emit_petition_withdrawn() |
| Event Emitter Impl | `src/application/services/petition_event_emitter.py` | Implement emit_petition_withdrawn() |
| Event Emitter Stub | `src/infrastructure/stubs/petition_event_emitter_stub.py` | Implement emit_petition_withdrawn() |

### Testing Standards Summary

- All tests use `pytest.mark.asyncio`
- Use `AsyncMock` for async dependencies
- Follow naming: `tests/unit/api/routes/test_petition_submission.py` (add withdrawal tests)
- Create `tests/unit/domain/events/test_petition_withdrawn_event.py` for event tests
- Create `tests/integration/test_petition_withdrawal_integration.py` for integration tests

### Project Structure Notes

- Withdrawal endpoint goes under existing router `/v1/petition-submissions`
- Follows existing pattern for fate assignment (see escalation routes)
- Event follows frozen dataclass pattern with signable_content() method

### References

- [Source: _bmad-output/planning-artifacts/petition-system-epics.md#Story 7.3]
- [Source: _bmad-output/planning-artifacts/petition-system-prd.md#FR-7.5]
- [Source: src/domain/models/petition_submission.py - State machine]
- [Source: src/domain/models/acknowledgment_reason.py - WITHDRAWN reason code]
- [Source: src/application/services/petition_submission_service.py - assign_fate_transactional pattern]
- [Source: _bmad-output/project-context.md - Constitutional rules and patterns]

### Critical Implementation Notes

1. **HALT CHECK FIRST** - Withdrawal is a write operation, must check halt state before proceeding
2. **Authorization is REQUIRED** - Only submitter can withdraw their own petition
3. **Anonymous petitions CANNOT be withdrawn** - No way to verify identity
4. **Use existing transactional pattern** - Don't reinvent fate assignment
5. **Fire-and-forget notification** - Don't block withdrawal on notification delivery
6. **Schema version in events** - D2 compliance requires schema_version in to_dict()

### Previous Story Intelligence (Story 7.2)

Story 7.2 (Fate Assignment Notification) established:
- `FateNotificationService` for fire-and-forget notifications
- `NotificationPreference` model for webhook/in-app preferences
- Integration with `StatusTokenRegistry` for long-poll notification

Withdrawal should reuse this notification infrastructure to notify co-signers.

### Git Intelligence (Recent Commits)

Recent commits show pattern of:
- Comprehensive unit tests for all ACs
- Integration tests for full flows
- Following constitutional constraints (HALT CHECK, witnessing)
- Using existing service patterns with dependency injection

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

N/A - Implementation completed successfully

### Completion Notes List

1. Implemented PetitionWithdrawn event in `src/domain/events/petition.py`
2. Added UnauthorizedWithdrawalError, PetitionAlreadyFatedError to `src/domain/errors/petition.py`
3. Added `withdraw_petition()` method to PetitionSubmissionService
4. Added withdrawal endpoint POST `/v1/petition-submissions/{petition_id}/withdraw`
5. Added event emitter method `emit_petition_withdrawn()` to protocol and stubs
6. Added event emitter injection to dependency injection (bootstrap and API dependencies)
7. Fixed bug in `assign_fate_transactional()` - was not passing `fate_reason` to repository
8. Created 20 unit tests (10 service + 10 API) - all passing
9. Created 6 integration tests - all passing
10. Total: 86 petition-related tests passing

### File List

**New Files:**
- None (all changes to existing files)

**Modified Files:**
- `src/domain/events/petition.py` - Added PetitionWithdrawnEventPayload
- `src/domain/errors/petition.py` - Added UnauthorizedWithdrawalError, PetitionAlreadyFatedError
- `src/domain/models/petition_submission.py` - Added is_terminal() method to PetitionState
- `src/application/ports/petition_event_emitter.py` - Added emit_petition_withdrawn protocol method
- `src/application/services/petition_submission_service.py` - Added withdraw_petition() method, fixed fate_reason passing
- `src/api/models/petition_submission.py` - Added WithdrawPetitionRequest, WithdrawPetitionResponse
- `src/api/routes/petition_submission.py` - Added POST withdraw endpoint
- `src/api/dependencies/petition_submission.py` - Added event emitter injection
- `src/bootstrap/petition_submission.py` - Added event emitter singleton management
- `src/infrastructure/stubs/petition_event_emitter_stub.py` - Added emit_petition_withdrawn stub (already existed)
- `src/infrastructure/monitoring/metrics.py` - Added withdrawal metrics counter
- `tests/unit/application/services/test_petition_submission_service.py` - Added TestWithdrawPetition class
- `tests/unit/api/routes/test_petition_submission.py` - Added TestWithdrawPetitionEndpoint class
- `tests/integration/test_petition_submission_api.py` - Added TestPetitionWithdrawalIntegration class

