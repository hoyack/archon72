# Story 1.1: Petition Submission REST Endpoint

**Epic:** Petition Epic 1: Petition Intake & State Machine
**Story ID:** petition-1-1-petition-submission-rest-endpoint
**Status:** done
**Priority:** P0
**Created:** 2026-01-19
**Completed:** 2026-01-19

---

## User Story

As an **Observer**,
I want to submit a petition via REST API,
So that I can formally request system attention for my concern.

---

## Business Context

This story implements the primary intake channel for the Petition System. It enables external parties (Observers) to submit formal petitions that will be processed by the Three Fates deliberation engine.

**Constitutional Alignment:**
- **CT-11:** "Speech is unlimited. Agenda is scarce." - This endpoint enables unlimited speech
- **CT-14 (Proposed):** "Silence must be expensive." - Every submission gets a petition_id and RECEIVED state

**Dependencies:**
- Story 0.2: Petition Domain Model (COMPLETE) - `PetitionSubmission`, `PetitionType`, `PetitionState`
- Story 0.5: Content Hashing Service (COMPLETE) - Blake3 hashing for duplicate detection
- Story 0.6: Realm Registry (COMPLETE) - Routing petitions to correct realm

---

## Acceptance Criteria

### AC1: Valid Petition Submission

**Given** I am an authenticated Observer
**When** I POST to `/api/v1/petition-submissions` with valid payload:
```json
{
  "type": "GENERAL" | "CESSATION" | "GRIEVANCE" | "COLLABORATION",
  "text": "petition content (1-10,000 chars)",
  "realm": "optional realm identifier"
}
```
**Then** the system returns HTTP 201 with:
```json
{
  "petition_id": "UUIDv7",
  "state": "RECEIVED",
  "type": "GENERAL",
  "content_hash": "base64-encoded-blake3-hash",
  "created_at": "ISO8601 timestamp"
}
```
**And** the petition is persisted to the database
**And** a Blake3 content hash is computed and stored
**And** response latency is < 200ms p99 (NFR-1.1)

### AC2: Schema Validation

**Given** I submit invalid payload:
- Missing `type` field
- Empty `text` field
- `text` > 10,000 characters
- Invalid `type` value

**When** the request is processed
**Then** the system returns HTTP 400 with RFC 7807 error response:
```json
{
  "type": "https://archon72.io/errors/invalid-petition",
  "title": "Invalid Petition Submission",
  "status": 400,
  "detail": "Specific validation error message",
  "instance": "/api/v1/petition-submissions"
}
```

### AC3: UUIDv7 Generation

**Given** a valid petition submission
**When** the petition is created
**Then** `petition_id` is a valid UUIDv7
**And** the ID is lexicographically sortable by creation time
**And** collision probability is negligible (FM-1.4 prevention)

### AC4: Content Hash Computation

**Given** a valid petition submission
**When** the petition is created
**Then** a Blake3 hash is computed from the petition text (canonical UTF-8 encoding)
**And** the 32-byte hash is stored with the petition
**And** the hash can be used for duplicate detection (HP-2)

### AC5: Initial State Assignment

**Given** a valid petition submission
**When** the petition is created
**Then** the state is set to `RECEIVED` (FR-1.6)
**And** the petition enters the processing queue
**And** the state is persisted atomically with the petition

### AC6: Realm Routing

**Given** a petition submission with optional `realm` field
**When** `realm` is provided and valid
**Then** the petition is assigned to the specified realm
**When** `realm` is not provided
**Then** the petition is assigned to the "default" realm via RealmRegistry

### AC7: Halt Behavior

**Given** the system is in HALT state
**When** I attempt to submit a petition
**Then** the system returns HTTP 503 Service Unavailable
**And** the response includes `Retry-After` header
**And** no petition data is persisted (write operation blocked per CT-13)

---

## Technical Specification

### API Endpoint

```
POST /api/v1/petition-submissions
Content-Type: application/json
Authorization: Bearer <token>

Request Body:
{
  "type": string (enum: GENERAL, CESSATION, GRIEVANCE, COLLABORATION),
  "text": string (1-10,000 chars, required),
  "realm": string (optional, validated against RealmRegistry)
}

Success Response (201 Created):
{
  "petition_id": string (UUIDv7),
  "state": "RECEIVED",
  "type": string,
  "content_hash": string (base64),
  "realm": string,
  "created_at": string (ISO8601)
}
```

### Error Responses

| Status | Condition | Error Type |
|--------|-----------|------------|
| 400 | Invalid payload | `invalid-petition` |
| 401 | Missing/invalid auth | `unauthorized` |
| 429 | Rate limit exceeded | `rate-limit-exceeded` |
| 503 | System halted | `system-halted` |
| 503 | Queue overflow | `queue-overflow` |

### Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `src/api/routes/petition_submission.py` | CREATE | New router for Three Fates petition submissions |
| `src/api/models/petition_submission.py` | CREATE | Pydantic request/response models |
| `src/application/services/petition_submission_service.py` | CREATE | Service orchestration layer |
| `src/api/dependencies/petition_submission.py` | CREATE | DI configuration |
| `src/api/routes/__init__.py` | MODIFY | Register new router |
| `tests/unit/api/routes/test_petition_submission.py` | CREATE | Unit tests |
| `tests/integration/test_petition_submission_api.py` | CREATE | Integration tests |

### Domain Model Integration

Uses existing models from Story 0.2:
- `PetitionSubmission` (frozen dataclass)
- `PetitionType` (enum: GENERAL, CESSATION, GRIEVANCE, COLLABORATION)
- `PetitionState` (enum: RECEIVED, DELIBERATING, ACKNOWLEDGED, REFERRED, ESCALATED)

### Service Dependencies

| Service | Port | Purpose |
|---------|------|---------|
| `PetitionSubmissionRepositoryProtocol` | `src/application/ports/petition_submission_repository.py` | Persistence |
| `ContentHashServiceProtocol` | `src/application/ports/content_hash_service.py` | Blake3 hashing |
| `RealmRegistryProtocol` | `src/application/ports/realm_registry.py` | Realm routing |
| `HaltService` | `src/application/services/halt_service.py` | Halt state check |

---

## Implementation Notes

### UUIDv7 Generation

```python
import uuid
from uuid import UUID

def generate_uuidv7() -> UUID:
    """Generate UUIDv7 with embedded timestamp for ordering."""
    return uuid.uuid7()  # Python 3.12+
    # Or use uuid7 library for earlier versions
```

### Content Hash Integration

```python
from src.application.ports.content_hash_service import ContentHashServiceProtocol

async def compute_hash(service: ContentHashServiceProtocol, text: str) -> bytes:
    """Compute Blake3 hash for duplicate detection."""
    return await service.hash_content(text.encode("utf-8"))
```

### Realm Validation

```python
from src.application.ports.realm_registry import RealmRegistryProtocol

async def validate_realm(registry: RealmRegistryProtocol, realm: str | None) -> str:
    """Validate and resolve realm, defaulting if not specified."""
    if realm is None:
        return registry.get_default_realm().id
    if not await registry.realm_exists(realm):
        raise InvalidRealmError(f"Unknown realm: {realm}")
    return realm
```

---

## Testing Requirements

### Unit Tests (>90% coverage)

1. **Request Validation**
   - Valid payload accepted
   - Missing type rejected
   - Empty text rejected
   - Text > 10k rejected
   - Invalid type rejected
   - Invalid realm rejected

2. **Response Structure**
   - 201 response has correct fields
   - UUIDv7 format validation
   - Content hash format validation
   - Timestamp format validation

3. **Error Responses**
   - 400 has RFC 7807 structure
   - 503 has Retry-After header
   - All error types documented

### Integration Tests

1. **Happy Path**
   - Submit GENERAL petition
   - Submit CESSATION petition
   - Submit with explicit realm
   - Submit without realm (default)

2. **Persistence Verification**
   - Petition retrievable after submit
   - State is RECEIVED
   - Content hash matches computation

3. **Performance**
   - p99 latency < 200ms (NFR-1.1)

---

## Definition of Done

- [x] API endpoint implemented at `/api/v1/petition-submissions`
- [x] All acceptance criteria have passing tests (21 unit + 12 integration)
- [x] Unit test coverage > 90%
- [x] Integration tests pass
- [x] RFC 7807 error responses implemented
- [x] Halt behavior verified
- [ ] p99 latency < 200ms verified (requires load testing)
- [ ] Code review approved
- [x] Documentation updated

---

## FR/NFR Traceability

| Requirement | Description | Implementation |
|-------------|-------------|----------------|
| FR-1.1 | Accept petition submissions via REST API | `/api/v1/petition-submissions` endpoint |
| FR-1.2 | Generate UUIDv7 petition_id | `uuid.uuid7()` |
| FR-1.3 | Validate petition schema | Pydantic models + validation |
| FR-1.6 | Set initial state to RECEIVED | `PetitionState.RECEIVED` default |
| FR-10.1 | Support GENERAL, CESSATION, GRIEVANCE, COLLABORATION types | `PetitionType` enum |
| NFR-1.1 | p99 < 200ms latency | Performance test validation |
| NFR-3.1 | No silent petition loss | Return 503 on failures, never drop |
| NFR-4.1 | Petition state durability | PostgreSQL persistence |

---

## Notes

- This endpoint is SEPARATE from the existing Story 7.2 petition API (`/v1/petitions`)
- Story 7.2 handles cessation co-signing; this handles Three Fates submission
- Event emission (FR-1.7) is covered by Story 1.2
- Queue overflow (FR-1.4) is covered by Story 1.3
- Rate limiting (FR-1.5) is covered by Story 1.4
