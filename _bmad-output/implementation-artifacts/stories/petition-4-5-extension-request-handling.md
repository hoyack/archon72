# Story 4.5: Extension Request Handling

**Epic:** 4 - Knight Referral Workflow
**Priority:** P1
**Status:** complete

---

## User Story

As a **Knight**,
I want to request deadline extensions (max 2),
So that I can properly review complex petitions.

---

## Acceptance Criteria

### AC-1: Extension Request Success
**Given** I have an assigned referral with extensions_granted < 2
**When** I POST `/api/v1/referrals/{referral_id}/extend` with:
  - `reason`: text explaining need for extension
**Then** the deadline is extended by 1 cycle
**And** `extensions_granted` is incremented
**And** a `ReferralExtended` event is emitted
**And** the deadline job is rescheduled

### AC-2: Max Extensions Enforcement
**Given** I have already used 2 extensions
**When** I request another extension
**Then** the system returns HTTP 400 with "MAX_EXTENSIONS_REACHED"

### AC-3: Authorization Check
**Given** I am not the assigned Knight for this referral
**When** I request an extension
**Then** the system returns HTTP 403 with "NOT_ASSIGNED_KNIGHT"

### AC-4: Invalid State Check
**Given** the referral is not in IN_REVIEW status
**When** I request an extension
**Then** the system returns HTTP 400 with "INVALID_REFERRAL_STATE"

### AC-5: Reason Validation
**Given** I request an extension with empty or missing reason
**When** the request is validated
**Then** the system returns HTTP 400 with "REASON_REQUIRED"

---

## References

- **FR-4.4:** Knight SHALL be able to request extension (max 2)
- **NFR-4.4:** Referral deadline persistence: Survives scheduler restart

---

## Technical Notes

### Domain Model Updates
- `Referral.extensions_granted: int` - Track number of extensions (0-2)
- `Referral.original_deadline: datetime` - Preserve original deadline for audit
- `Referral.can_extend() -> bool` - Check if extensions available

### Events
- `ReferralExtendedEvent`:
  - `referral_id: UUID`
  - `petition_id: UUID`
  - `knight_id: UUID`
  - `extension_number: int` (1 or 2)
  - `reason: str`
  - `old_deadline: datetime`
  - `new_deadline: datetime`
  - `witness_hash: str`

### Errors
- `MaxExtensionsReachedError` - Already used 2 extensions
- `NotAssignedKnightError` - Already exists from Story 4.4
- `InvalidReferralStateError` - Already exists from Story 4.2
- `ExtensionReasonRequiredError` - Reason text is required

### Configuration
- `EXTENSION_DURATION_CYCLES: int = 1` - Cycles added per extension
- `MAX_EXTENSIONS: int = 2` - Maximum extensions allowed

### Integration Points
- Deadline job scheduler (from Story 0.4) for rescheduling
- Referral repository for updating deadline and extensions_granted
- Event bus for ReferralExtended emission

---

## Tasks

- [x] Update Referral model with `extensions_granted` field (pre-existing)
- [x] Create `ReferralExtendedEvent` domain event (pre-existing)
- [x] Create extension-specific domain errors
- [x] Create `ExtensionRequestProtocol` port
- [x] Implement `ExtensionRequestService`
- [x] Create stub implementation
- [x] Write unit tests (22 tests)
- [x] Write integration tests (23 tests)

---

## Definition of Done

- [x] All acceptance criteria verified with tests
- [x] Unit tests passing (22 - exceeds 15+ requirement)
- [x] Integration tests passing (23 - exceeds 10+ requirement)
- [x] FR-4.4 covered
- [x] No regressions in existing tests

## Implementation Notes

### Files Created
- `src/application/ports/extension_request.py` - Protocol and data classes
- `src/application/services/extension_request_service.py` - Service implementation
- `src/infrastructure/stubs/extension_request_stub.py` - In-memory test stub
- `tests/unit/application/services/test_extension_request_service.py` - Unit tests
- `tests/integration/test_extension_request_integration.py` - Integration tests

### Files Modified
- `src/domain/errors/referral.py` - Added extension-specific errors
- `src/domain/errors/__init__.py` - Exported new errors
- `src/application/ports/__init__.py` - Exported protocol and data classes
- `src/application/services/__init__.py` - Exported service and constants
- `src/infrastructure/stubs/__init__.py` - Exported stub

### Test Coverage
- **Unit Tests (22):** Service logic, error handling, authorization, state validation
- **Integration Tests (23):** Full flow with stubs, witness hashing, event emission

### Known Limitations
- JobSchedulerStub interface differs from service expectations; service handles gracefully per NFR-4.4
- Service max_extensions config cannot exceed model MAX_EXTENSIONS (2) due to model validation
