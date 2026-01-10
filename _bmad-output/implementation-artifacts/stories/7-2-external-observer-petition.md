# Story 7.2: External Observer Petition

Status: dev-complete

## Story

As an **external observer**,
I want petition capability with 100+ co-signers to trigger agenda placement,
So that external parties can raise cessation concerns.

## Acceptance Criteria

### AC1: Petition Submission (FR39)
**Given** the petition system
**When** I submit a cessation petition
**Then** it is recorded with my signature
**And** a `PetitionCreatedEvent` is created with:
  - `petition_id`: Unique identifier
  - `submitter_public_key`: Observer's public key
  - `submitter_signature`: Signature over petition content
  - `petition_content`: Reason for cessation concern
  - `created_timestamp`: When submitted (UTC)
**And** petition status is "open"

### AC2: Co-signing Capability
**Given** an open petition
**When** another observer co-signs
**Then** their signature is added to the petition
**And** a `PetitionCoSignedEvent` is created with:
  - `petition_id`: Reference to petition
  - `cosigner_public_key`: Co-signer's public key
  - `cosigner_signature`: Signature over petition content
  - `cosigned_timestamp`: When co-signed (UTC)
  - `cosigner_sequence`: Order of this co-signer (1-based)
**And** duplicate co-signatures from same public key are rejected

### AC3: Threshold Trigger (FR39)
**Given** a petition reaches 100 co-signers
**When** the 100th co-signature is verified
**Then** cessation is placed on Conclave agenda
**And** a `PetitionThresholdMetEvent` is created with:
  - `petition_id`: Reference to petition
  - `threshold`: 100
  - `final_cosigner_count`: Actual count (>= 100)
  - `trigger_timestamp`: When threshold was met
  - `cosigner_public_keys`: All 100+ public keys
  - `agenda_placement_reason`: "FR39: External observer petition reached 100 co-signers"
**And** petition status changes to "threshold_met"
**And** `CessationAgendaPlacementEvent` is created (Story 7.1 integration)

### AC4: Signature Verification
**Given** a petition
**When** I examine it
**Then** all co-signers are visible via public read API
**And** signatures are cryptographically verifiable:
  - Ed25519 signature algorithm
  - Signature over canonical petition content bytes
  - Public key recovery from signature supported
**And** invalid signatures are rejected at submission time

### AC5: Idempotent Threshold
**Given** a petition has already met threshold
**When** additional co-signatures are added
**Then** no duplicate agenda placement is created
**And** co-signatures are still recorded for completeness

### AC6: Event Witnessing (CT-12)
**Given** any petition event (create, co-sign, threshold)
**When** the event is created
**Then** the event MUST be witnessed via EventWriterService
**And** `signable_content()` includes all petition/signature details

### AC7: Halt State Check (CT-11)
**Given** system is in halted state
**When** a petition submission or co-sign is attempted
**Then** `SystemHaltedError` is raised
**And** no petition event is created
**Note:** Reading petitions is allowed during halt (CT-13, per Story 3.5)

### AC8: Public Petition Visibility
**Given** any observer (no authentication per FR44)
**When** they query petitions
**Then** all open petitions are visible
**And** all co-signers are visible with their public keys
**And** signature verification data is included
**And** rate limits apply equally (FR48)

## Tasks / Subtasks

- [x] **Task 1: Create Petition domain events** (AC: 1,2,3,6)
  - [x] Create `src/domain/events/petition.py`
  - [x] Define `PetitionStatus` enum (open, threshold_met, closed)
  - [x] Implement `PetitionCreatedEventPayload` frozen dataclass
  - [x] Implement `PetitionCoSignedEventPayload` frozen dataclass
  - [x] Implement `PetitionThresholdMetEventPayload` frozen dataclass
  - [x] Implement `signable_content()` for all payloads (CT-12)
  - [x] Export from `src/domain/events/__init__.py`

- [x] **Task 2: Create Petition domain model** (AC: 1,2,4)
  - [x] Create `src/domain/models/petition.py`
  - [x] Define `Petition` frozen dataclass with:
    - `petition_id`: UUID
    - `submitter_public_key`: str (hex-encoded)
    - `submitter_signature`: str (hex-encoded)
    - `petition_content`: str
    - `created_timestamp`: datetime
    - `status`: PetitionStatus
    - `cosigners`: tuple of CoSigner dataclasses
    - `threshold_met_at`: Optional[datetime]
  - [x] Define `CoSigner` frozen dataclass with:
    - `public_key`: str (hex-encoded)
    - `signature`: str (hex-encoded)
    - `signed_at`: datetime
    - `sequence`: int
  - [x] Export from `src/domain/models/__init__.py`

- [x] **Task 3: Create PetitionRepository port** (AC: 1,2,3,5,8)
  - [x] Create `src/application/ports/petition_repository.py`
  - [x] Define methods:
    - `save_petition(petition: Petition) -> None`
    - `get_petition(petition_id: UUID) -> Optional[Petition]`
    - `list_open_petitions(limit: int, offset: int) -> tuple[list[Petition], int]`
    - `add_cosigner(petition_id: UUID, cosigner: CoSigner) -> Petition`
    - `has_cosigned(petition_id: UUID, public_key: str) -> bool`
    - `update_status(petition_id: UUID, status: PetitionStatus) -> None`
  - [x] Export from `src/application/ports/__init__.py`

- [x] **Task 4: Create SignatureVerifier port** (AC: 4)
  - [x] Create `src/application/ports/signature_verifier.py`
  - [x] Define methods:
    - `verify_signature(public_key: str, signature: str, content: bytes) -> bool`
    - `get_algorithm() -> str`  # Returns "Ed25519"
  - [x] This enables observer self-verification of petition signatures
  - [x] Export from `src/application/ports/__init__.py`

- [x] **Task 5: Create PetitionService** (AC: 1,2,3,4,5,6,7)
  - [x] Create `src/application/services/petition_service.py`
  - [x] Inject dependencies: `PetitionRepository`, `SignatureVerifier`, `EventWriterService`, `HaltChecker`, `CessationAgendaRepository` (from Story 7.1)
  - [x] Implement `submit_petition()`:
    - HALT CHECK FIRST (CT-11)
    - Verify submitter signature
    - Create petition record
    - Write `PetitionCreatedEvent` via EventWriterService
    - Return petition_id
  - [x] Implement `cosign_petition()`:
    - HALT CHECK FIRST (CT-11)
    - Verify co-signer signature
    - Check for duplicate co-signature
    - Add co-signer to petition
    - Write `PetitionCoSignedEvent`
    - Check threshold (>= 100)
    - If threshold met: trigger agenda placement (idempotent)
  - [x] Implement `get_petition()` - reads allowed during halt (CT-13)
  - [x] Implement `list_open_petitions()` - reads allowed during halt (CT-13)
  - [x] Export from `src/application/services/__init__.py`

- [x] **Task 6: Create stub implementations** (AC: all)
  - [x] Create `src/infrastructure/stubs/petition_repository_stub.py`
  - [x] Create `src/infrastructure/stubs/signature_verifier_stub.py`
  - [x] Register stubs in `src/infrastructure/stubs/__init__.py`

- [x] **Task 7: Create API routes** (AC: 1,2,8)
  - [x] Create `src/api/routes/petition.py`
  - [x] Create `src/api/models/petition.py` (Pydantic models)
  - [x] Implement endpoints:
    - `POST /v1/petitions` - Submit new petition
    - `POST /v1/petitions/{petition_id}/cosign` - Co-sign petition
    - `GET /v1/petitions` - List open petitions (public, FR44)
    - `GET /v1/petitions/{petition_id}` - Get single petition with all co-signers
  - [x] No authentication (FR44)
  - [x] Register router in `src/api/routes/__init__.py`

- [x] **Task 8: Create domain errors** (AC: 2,4,7)
  - [x] Create `src/domain/errors/petition.py`
  - [x] Define:
    - `InvalidSignatureError(ConstitutionalViolationError)` - Signature verification failed
    - `DuplicateCosignatureError(ConstitutionalViolationError)` - Already co-signed
    - `PetitionNotFoundError(ConstitutionalViolationError)` - Petition doesn't exist
    - `PetitionClosedError(ConstitutionalViolationError)` - Petition not accepting co-signatures
    - `PetitionAlreadyExistsError(ConstitutionalViolationError)` - Duplicate petition ID
  - [x] Export from `src/domain/errors/__init__.py`

- [x] **Task 9: Write unit tests** (AC: all)
  - [x] Create `tests/unit/domain/test_petition.py` - Model tests (21 tests)
  - [x] Create `tests/unit/domain/test_petition_events.py` - Event payload tests (25 tests)
  - [x] Create `tests/unit/application/test_petition_service.py` (14 tests):
    - Test petition submission with valid signature
    - Test rejection of invalid signature
    - Test co-signing with threshold at 99, 100, 101
    - Test duplicate co-signature rejection
    - Test idempotent agenda placement
    - Test halt state rejection for writes
    - Test reads allowed during halt
    - Test signable_content() determinism
  - [x] Create `tests/unit/infrastructure/test_petition_repository_stub.py` (18 tests)

- [x] **Task 10: Write integration tests** (AC: all)
  - [x] Create `tests/integration/test_external_observer_petition_integration.py` (20 tests):
    - Test end-to-end petition submission → co-sign → threshold → agenda
    - Test 100 co-signature boundary (99 vs 100)
    - Test signature verification with stub verifier
    - Test public API access patterns
    - Test halt state behavior

## Dev Notes

### Relevant Architecture Patterns and Constraints

**Constitutional Truths to Honor:**
- **CT-11**: Silent failure destroys legitimacy → HALT CHECK FIRST, raise `SystemHaltedError`
- **CT-12**: Witnessing creates accountability → All events MUST be witnessed via EventWriterService
- **CT-13**: Integrity outranks availability → Reads allowed during halt (per Story 3.5)

**Developer Golden Rules:**
1. **HALT FIRST** - Check halt state before every write operation
2. **WITNESS EVERYTHING** - All petition events require attribution
3. **FAIL LOUD** - Never silently swallow signature errors
4. **READS DURING HALT** - Petition queries work during halt (CT-13)

### Source Tree Components to Touch

**New Files:**
```
src/domain/events/petition.py                    # PetitionCreatedEventPayload, PetitionCoSignedEventPayload, PetitionThresholdMetEventPayload
src/domain/models/petition.py                    # Petition, CoSigner domain models
src/domain/errors/petition.py                    # Petition-related errors
src/application/ports/petition_repository.py     # PetitionRepository port
src/application/ports/signature_verifier.py      # SignatureVerifier port
src/application/services/petition_service.py     # PetitionService
src/infrastructure/stubs/petition_repository_stub.py
src/infrastructure/stubs/signature_verifier_stub.py
src/api/routes/petition.py                       # FastAPI router
src/api/models/petition.py                       # Pydantic API models
src/api/dependencies/petition.py                 # Dependency injection
tests/unit/domain/test_petition.py
tests/unit/domain/test_petition_events.py
tests/unit/application/test_petition_service.py
tests/integration/test_external_observer_petition_integration.py
```

**Files to Update:**
```
src/domain/events/__init__.py                    # Export new events
src/domain/models/__init__.py                    # Export new models
src/domain/errors/__init__.py                    # Export new errors
src/application/ports/__init__.py                # Export new ports
src/application/services/__init__.py             # Export PetitionService
src/infrastructure/stubs/__init__.py             # Register stubs
src/api/routes/__init__.py                       # Register petition router
src/api/main.py                                  # Include petition routes
```

### Related Existing Code

**Story 7.1 Integration (CessationAgendaPlacementEvent):**
- `src/domain/events/cessation_agenda.py` - `CessationAgendaPlacementEventPayload`, `AgendaTriggerType`
- `src/application/ports/cessation_agenda_repository.py` - Reuse for idempotent agenda placement
- `src/application/services/automatic_agenda_placement_service.py` - Pattern reference

**Observer API Patterns (Epic 4):**
- `src/api/routes/observer.py` - Public read access pattern (FR44)
- `src/application/services/observer_service.py` - Service pattern for reads
- `src/api/middleware/rate_limiter.py` - Rate limiting (FR48)

**Halt Check Pattern:**
```python
# From automatic_agenda_placement_service.py - FOLLOW THIS PATTERN
if await self._halt_checker.is_halted():
    reason = await self._halt_checker.get_halt_reason()
    log.critical("operation_rejected_system_halted", halt_reason=reason)
    raise SystemHaltedError(f"CT-11: System is halted: {reason}")
```

**Event Writing Pattern:**
```python
# From automatic_agenda_placement_service.py - FOLLOW THIS PATTERN
await self._event_writer.write_event(
    event_type=PETITION_CREATED_EVENT_TYPE,
    payload=payload.to_dict(),
    agent_id=PETITION_SYSTEM_AGENT_ID,
    local_timestamp=created_timestamp,
)
```

**Signature Verification Reference:**
- Ed25519 is used throughout the system for agent signatures
- `src/infrastructure/adapters/security/hsm_dev.py` - Software HSM stub with Ed25519
- Petitions use observer-provided keys (not system HSM)

### API Design Notes

**Petition Submission Request:**
```json
{
  "petition_content": "Concern about integrity failures...",
  "submitter_public_key": "abc123...",  // hex-encoded Ed25519 public key
  "signature": "def456..."               // hex-encoded signature
}
```

**Co-sign Request:**
```json
{
  "cosigner_public_key": "789abc...",
  "signature": "fed321..."
}
```

**Petition Response:**
```json
{
  "petition_id": "uuid",
  "submitter_public_key": "abc123...",
  "petition_content": "...",
  "status": "open",
  "created_at": "2026-01-08T...",
  "cosigner_count": 47,
  "cosigners": [
    {
      "public_key": "...",
      "signed_at": "...",
      "sequence": 1
    }
  ],
  "threshold": 100,
  "threshold_met_at": null
}
```

### Testing Standards Summary

- **Async Testing**: ALL tests use `pytest.mark.asyncio` and `async def test_*`
- **Mocking**: Use `AsyncMock` for async dependencies
- **Coverage**: 80% minimum required
- **Boundary Tests**: Test exact threshold (99 vs 100)
- **Signature Tests**: Test both valid and invalid Ed25519 signatures
- **Unit Test Location**: `tests/unit/domain/` and `tests/unit/application/`
- **Integration Test Location**: `tests/integration/`

### Project Structure Notes

**Hexagonal Architecture Compliance:**
- Domain events: Pure dataclasses, no infrastructure imports
- Ports: Protocol classes in `application/ports/`
- Stubs: Implementation stubs in `infrastructure/stubs/`
- Service: Business logic in `application/services/`
- API: FastAPI routes in `api/routes/`

**Import Rules:**
- `domain/` imports NOTHING from other layers
- `application/` imports from `domain/` only
- `infrastructure/` implements ports from `application/`
- `api/` depends on `application/` services

### Key Differences from Story 7.1

| Aspect | Story 7.1 | Story 7.2 |
|--------|-----------|-----------|
| Trigger Source | System integrity metrics | External observer action |
| Authentication | N/A (internal) | None required (FR44) |
| Threshold | 3 failures / 5 in window / 90 days | 100 co-signers |
| Signature | System HSM | Observer-provided Ed25519 keys |
| Public Visibility | Events only | Full petition + co-signer list |

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story-7.2]
- [Source: _bmad-output/planning-artifacts/architecture.md#ADR-012]
- [Source: src/domain/events/cessation_agenda.py] - Event payload pattern
- [Source: src/application/services/automatic_agenda_placement_service.py] - Service pattern
- [Source: src/api/routes/observer.py] - Public API pattern (FR44)
- [Source: src/infrastructure/adapters/security/hsm_dev.py] - Ed25519 pattern
- [Source: _bmad-output/project-context.md] - Coding standards
- [Source: _bmad-output/implementation-artifacts/stories/7-1-automatic-agenda-placement.md] - Previous story learnings

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

N/A - All tests passing

### Completion Notes List

- **98 tests passing**: 25 (domain events) + 21 (domain model) + 14 (service) + 18 (repository stub) + 20 (integration)
- All acceptance criteria verified through comprehensive test coverage
- Constitutional constraints honored: CT-11 (HALT CHECK FIRST), CT-12 (event witnessing), CT-13 (reads during halt)
- Hexagonal architecture compliance verified: domain has no external dependencies
- API routes registered and follow FR44 (public access) pattern
- Automatic agenda placement at 100 co-signers integrates with Story 7.1

### File List

**Created Files:**
- `src/domain/events/petition.py` - Event payloads (PetitionCreated, PetitionCoSigned, PetitionThresholdMet)
- `src/domain/models/petition.py` - Petition and CoSigner domain models
- `src/domain/errors/petition.py` - Petition-specific errors
- `src/application/ports/petition_repository.py` - PetitionRepositoryProtocol
- `src/application/ports/signature_verifier.py` - SignatureVerifierProtocol
- `src/application/services/petition_service.py` - PetitionService with submit, cosign, list methods
- `src/infrastructure/stubs/petition_repository_stub.py` - In-memory petition repository
- `src/infrastructure/stubs/signature_verifier_stub.py` - Configurable signature verifier stub
- `src/api/routes/petition.py` - FastAPI router with 4 endpoints
- `src/api/models/petition.py` - Pydantic request/response models
- `tests/unit/domain/test_petition.py` - 21 unit tests for domain model
- `tests/unit/domain/test_petition_events.py` - 25 unit tests for event payloads
- `tests/unit/application/test_petition_service.py` - 14 unit tests for service
- `tests/unit/infrastructure/test_petition_repository_stub.py` - 18 unit tests for repository stub
- `tests/integration/test_external_observer_petition_integration.py` - 20 integration tests

**Updated Files:**
- `src/domain/events/__init__.py` - Export petition events
- `src/domain/models/__init__.py` - Export Petition, CoSigner
- `src/domain/errors/__init__.py` - Export petition errors
- `src/application/ports/__init__.py` - Export petition ports
- `src/application/services/__init__.py` - Export PetitionService
- `src/infrastructure/stubs/__init__.py` - Export petition stubs
- `src/api/routes/__init__.py` - Export petition_router
- `src/api/models/__init__.py` - Export petition API models

## Change Log

- 2026-01-08: Story created - External observer petition with 100 co-signer threshold (FR39)
- 2026-01-08: Implementation complete - All 10 tasks finished, 98 tests passing
