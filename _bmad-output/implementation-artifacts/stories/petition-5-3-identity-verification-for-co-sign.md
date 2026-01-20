# Story 5.3: Identity Verification for Co-Sign

## Story

**ID:** petition-5-3-identity-verification-for-co-sign
**Epic:** Petition Epic 5: Co-signing & Auto-Escalation
**Priority:** P0

As a **system**,
I want to verify signer identity before accepting co-signs,
So that only legitimate identities can support petitions.

## Acceptance Criteria

### AC1: Valid Identity Verification
**Given** a co-sign request with valid authenticated identity
**When** the request is processed
**Then** the signer_id is verified against the identity store
**And** the co-sign is accepted with `identity_verified=true`
**And** the co-sign proceeds through normal flow

### AC2: Invalid Identity Rejection
**Given** a co-sign request with invalid identity (unknown signer_id)
**When** the request is processed
**Then** the system returns HTTP 403 Forbidden
**And** error code is "IDENTITY_NOT_FOUND"
**And** the co-sign is rejected
**And** no co-sign record is created

### AC3: Suspended Identity Rejection
**Given** a co-sign request with suspended identity
**When** the request is processed
**Then** the system returns HTTP 403 Forbidden
**And** error code is "IDENTITY_SUSPENDED"
**And** the co-sign is rejected
**And** no co-sign record is created

### AC4: Identity Verification Precedes Co-Sign Creation
**Given** a co-sign request
**When** the system processes it
**Then** identity verification happens BEFORE any database writes
**And** verification failure prevents any state changes

### AC5: Verification Status Recorded
**Given** a successful co-sign with verified identity
**When** the co-sign record is created
**Then** `identity_verified` field is set to `true`
**And** the CO_SIGN_RECORDED event includes `identity_verified=true`

### AC6: Graceful Degradation on Identity Service Unavailable
**Given** the identity service is temporarily unavailable
**When** a co-sign request is processed
**Then** the system returns HTTP 503 Service Unavailable
**And** error code is "IDENTITY_SERVICE_UNAVAILABLE"
**And** the response includes Retry-After header

## References

- **NFR-5.2:** Identity verification for co-sign: Required [LEGIT-1]
- **LEGIT-1:** Manufactured consent via bot co-signers -> Co-signer dedup + fraud detection patterns
- **CT-12:** Witnessing creates accountability
- **D7:** RFC 7807 error responses with governance extensions

## Tasks/Subtasks

### Task 1: Create Domain Errors for Identity Verification
- [x] Create `src/domain/errors/identity.py` with error classes
  - [x] `IdentityNotFoundError` - unknown signer_id (HTTP 403)
  - [x] `IdentitySuspendedError` - suspended identity (HTTP 403)
  - [x] `IdentityServiceUnavailableError` - service down (HTTP 503)
- [x] Add exports to `src/domain/errors/__init__.py`
- [x] Error classes use constitutional constraint references (NFR-5.2, LEGIT-1)

### Task 2: Create IdentityVerificationProtocol Port
- [x] Create `src/application/ports/identity_verification.py`
  - [x] `IdentityStatus` enum: VALID, NOT_FOUND, SUSPENDED, SERVICE_UNAVAILABLE
  - [x] `IdentityVerificationResult` dataclass with status, identity_id, is_valid, suspension_reason
  - [x] `IdentityStoreProtocol` with `verify(signer_id: UUID) -> IdentityVerificationResult`
- [x] Add exports to `src/application/ports/__init__.py`

### Task 3: Create IdentityVerificationService
- [x] Verification logic integrated directly into CoSignSubmissionService
  - [x] Handles verification with proper error mapping
  - [x] Returns appropriate errors based on IdentityStatus

### Task 4: Create IdentityStoreStub for Testing
- [x] Create `src/infrastructure/stubs/identity_store_stub.py`
  - [x] In-memory implementation of `IdentityStoreProtocol`
  - [x] `_valid_identities: set[UUID]` for known identities
  - [x] `_suspended_identities: dict[UUID, str | None]` for suspended identities with reasons
  - [x] Methods: `add_valid_identity()`, `remove_valid_identity()`, `suspend_identity()`, `unsuspend_identity()`
  - [x] `_available: bool` flag to simulate service unavailability
  - [x] `reset()` method to clear all data between tests
- [x] Add exports to `src/infrastructure/stubs/__init__.py`

### Task 5: Integrate Identity Verification into CoSignSubmissionService
- [x] Update `src/application/services/co_sign_submission_service.py`
  - [x] Add `IdentityStoreProtocol` dependency
  - [x] Call verification AFTER halt check, BEFORE duplicate check
  - [x] Set `identity_verified=True` on CoSign creation
  - [x] Raise appropriate errors on verification failure
- [x] Update `src/api/dependencies/co_sign.py` for new dependency
  - [x] Add `get_identity_store()` singleton function
  - [x] Update `get_co_sign_submission_service()` to include identity_store

### Task 6: Update API Route Error Handling
- [x] Update `src/api/routes/co_sign.py`
  - [x] Add error handlers for identity verification errors
  - [x] Return HTTP 403 for identity errors (not 401 - already authenticated)
  - [x] Return HTTP 503 for service unavailable with Retry-After header
  - [x] RFC 7807 error format with governance extensions (nfr_reference, hardening_control)

### Task 7: Write Unit Tests
- [x] Create `tests/unit/infrastructure/stubs/test_identity_store_stub.py`
  - [x] Test add/remove valid identities (21 tests)
  - [x] Test suspend/unsuspend identities
  - [x] Test availability toggle
  - [x] Test IdentityVerificationResult properties

### Task 8: Write Integration Tests
- [x] Create `tests/integration/test_identity_verification_integration.py`
  - [x] Test co-sign with valid identity succeeds (201)
  - [x] Test co-sign with unknown identity rejected (403)
  - [x] Test co-sign with suspended identity rejected (403)
  - [x] Test identity_verified field is true on success (18 tests)
  - [x] Test service unavailable returns 503 with Retry-After
  - [x] Test error responses are RFC 7807 compliant with governance extensions

## Dev Notes

### Architecture Context
- Follow hexagonal architecture: Port -> Service -> Adapter pattern
- Identity verification is a new domain concern, separate from co-sign logic
- The CoSign model already has `identity_verified` field (from Story 5.1)

### Dependencies
- Story 5.1 (DONE): CoSign domain model with `identity_verified` field
- Story 5.2 (DONE): CoSignSubmissionService
- HaltCheckProtocol for halt state verification
- EventWriterService for event emission

### Key Design Decisions
1. **403 vs 401:** Use 403 (Forbidden) not 401 (Unauthorized) - the request is authenticated but the identity is invalid/suspended
2. **Verification Order:** Halt check -> Identity verification -> Duplicate check -> State check -> Create
3. **Graceful Degradation:** Service unavailable returns 503 with Retry-After, not auto-fail
4. **No Auto-Create:** Unknown identities are rejected, not auto-created (security)

### Error Response Format (RFC 7807)
```json
{
  "type": "urn:archon72:identity:not-found",
  "title": "Identity Not Found",
  "status": 403,
  "detail": "Signer identity not found in identity store",
  "instance": "/api/v1/petitions/{id}/co-sign",
  "nfr_reference": "NFR-5.2",
  "hardening_control": "LEGIT-1"
}
```

### Future Extension Points
- Integration with actual identity provider (OAuth, SSO)
- Identity verification caching for performance
- Fraud pattern detection (LEGIT-1 phase 2)

## File List

### Domain Layer
- `src/domain/errors/identity.py` - Identity verification errors

### Application Layer
- `src/application/ports/identity_verification.py` - Protocol and result types
- `src/application/services/identity_verification_service.py` - Verification service

### Infrastructure Layer
- `src/infrastructure/stubs/identity_store_stub.py` - In-memory stub

### API Layer
- Updates to `src/api/routes/co_sign.py` - Error handling
- Updates to `src/api/dependencies/co_sign.py` - New dependency

### Tests
- `tests/unit/application/services/test_identity_verification_service.py`
- `tests/unit/infrastructure/stubs/test_identity_store_stub.py`
- `tests/integration/test_identity_verification_integration.py`

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2026-01-20 | Story created from Epic 5.3 | Dev Agent |

## Status

**Status:** done

## Implementation Summary

**Completed:** 2026-01-20

### Files Created
- `src/domain/errors/identity.py` - Identity verification errors (IdentityNotFoundError, IdentitySuspendedError, IdentityServiceUnavailableError)
- `src/application/ports/identity_verification.py` - Protocol and result types (IdentityStatus, IdentityVerificationResult, IdentityStoreProtocol)
- `src/infrastructure/stubs/identity_store_stub.py` - In-memory identity store stub
- `tests/unit/infrastructure/stubs/test_identity_store_stub.py` - 21 unit tests
- `tests/integration/test_identity_verification_integration.py` - 18 integration tests

### Files Modified
- `src/domain/errors/__init__.py` - Added identity error exports
- `src/application/ports/__init__.py` - Added identity verification exports
- `src/application/ports/co_sign_submission.py` - Added identity_verified field to CoSignSubmissionResult and protocol
- `src/application/services/co_sign_submission_service.py` - Integrated identity verification
- `src/domain/events/co_sign.py` - Added identity_verified field
- `src/infrastructure/stubs/co_sign_repository_stub.py` - Added identity_verified parameter
- `src/infrastructure/stubs/__init__.py` - Added IdentityStoreStub export
- `src/api/models/co_sign.py` - Added identity_verified to response, governance extensions to errors
- `src/api/dependencies/co_sign.py` - Added identity store dependency
- `src/api/routes/co_sign.py` - Added identity error handlers

### Test Coverage
- 39 total tests passing (21 unit + 18 integration)
- All acceptance criteria verified
- RFC 7807 compliance with governance extensions confirmed
