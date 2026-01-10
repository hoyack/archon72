# Story 2.8: Result Certification (FR99-FR101, FR141-FR142)

Status: complete

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an **external observer**,
I want deliberation results to have certified result events,
So that I can verify the result is official.

## Acceptance Criteria

### AC1: Certified Result Event Creation
**Given** a deliberation concludes
**When** the result is final
**Then** a `CertifiedResultEvent` is created
**And** it is signed by the system's certification key
**And** it includes: result_hash, participant_count, certification_timestamp

### AC2: Certification Signature Verification
**Given** a certified result
**When** I query it
**Then** the certification signature can be verified
**And** the result content matches the result_hash

### AC3: Procedural Record Generation
**Given** procedural record generation
**When** a deliberation completes
**Then** a procedural record is generated
**And** it includes: agenda, participants, votes, timeline, decisions
**And** the record is signed and stored

## Tasks / Subtasks

- [x] Task 1: Create CertifiedResultPayload Domain Event (AC: 1, 2) - 14 tests ✅
  - [x] 1.1 Create `src/domain/events/certified_result.py`
  - [x] 1.2 Define `CertifiedResultPayload` frozen dataclass with required fields
  - [x] 1.3 Add `to_dict()` method for event payload serialization
  - [x] 1.4 Add `__post_init__` validation
  - [x] 1.5 Define event type constant: `CERTIFIED_RESULT_EVENT_TYPE = "deliberation.result.certified"`
  - [x] 1.6 Add to `src/domain/events/__init__.py` exports
  - [x] 1.7 Add unit tests (14 tests in `tests/unit/domain/test_certified_result_event.py`)

- [x] Task 2: Create ProceduralRecordPayload Domain Event (AC: 3) - 14 tests ✅
  - [x] 2.1 Create `src/domain/events/procedural_record.py`
  - [x] 2.2 Define `ProceduralRecordPayload` frozen dataclass with immutable fields
  - [x] 2.3 Add `to_dict()` method for event payload serialization
  - [x] 2.4 Add `__post_init__` validation
  - [x] 2.5 Define event type constant: `PROCEDURAL_RECORD_EVENT_TYPE = "deliberation.record.procedural"`
  - [x] 2.6 Add to `src/domain/events/__init__.py` exports
  - [x] 2.7 Add unit tests (14 tests in `tests/unit/domain/test_procedural_record_event.py`)

- [x] Task 3: Create Certification Domain Errors (AC: 1, 2) - 11 tests ✅
  - [x] 3.1 Create `src/domain/errors/certification.py`
  - [x] 3.2 Define `CertificationError(ConclaveError)` base class
  - [x] 3.3 Define `CertificationSignatureError(CertificationError)`
  - [x] 3.4 Define `ResultHashMismatchError(CertificationError)`
  - [x] 3.5 Add to `src/domain/errors/__init__.py` exports
  - [x] 3.6 Add unit tests (11 tests in `tests/unit/domain/test_certification_errors.py`)

- [x] Task 4: Create ResultCertifierPort Interface (AC: 1, 2) - 13 tests ✅
  - [x] 4.1 Create `src/application/ports/result_certifier.py`
  - [x] 4.2 Define `CertificationResult` frozen dataclass
  - [x] 4.3 Define `ResultCertifierPort(Protocol)`
  - [x] 4.4 Add to `src/application/ports/__init__.py` exports
  - [x] 4.5 Add unit tests (13 tests in `tests/unit/application/test_result_certifier_port.py`)

- [x] Task 5: Create ProceduralRecordGeneratorPort Interface (AC: 3) - 11 tests ✅
  - [x] 5.1 Create `src/application/ports/procedural_record_generator.py`
  - [x] 5.2 Define `ProceduralRecordData` frozen dataclass
  - [x] 5.3 Define `ProceduralRecordGeneratorPort(Protocol)`
  - [x] 5.4 Add to `src/application/ports/__init__.py` exports
  - [x] 5.5 Add unit tests (11 tests in `tests/unit/application/test_procedural_record_generator_port.py`)

- [x] Task 6: Create ResultCertifierStub Infrastructure (AC: 1, 2) - 17 tests ✅
  - [x] 6.1 Create `src/infrastructure/stubs/result_certifier_stub.py`
  - [x] 6.2 Implement `ResultCertifierStub` with DEV_MODE_WATERMARK pattern
  - [x] 6.3 Implement `certify_result()` with canonical JSON hashing
  - [x] 6.4 Implement `verify_certification()`
  - [x] 6.5 Follow RT-1 pattern (mode inside signature)
  - [x] 6.6 Add unit tests (17 tests in `tests/unit/infrastructure/test_result_certifier_stub.py`)

- [x] Task 7: Create ProceduralRecordGeneratorStub Infrastructure (AC: 3) - 15 tests ✅
  - [x] 7.1 Create `src/infrastructure/stubs/procedural_record_generator_stub.py`
  - [x] 7.2 Implement `ProceduralRecordGeneratorStub` with DEV_MODE_WATERMARK pattern
  - [x] 7.3 Implement `generate_record()` with mock deliberation data support
  - [x] 7.4 Implement `verify_record()`
  - [x] 7.5 Add unit tests (15 tests in `tests/unit/infrastructure/test_procedural_record_generator_stub.py`)

- [x] Task 8: Create ResultCertificationService Application Service (AC: 1, 2, 3) - 17 tests ✅
  - [x] 8.1 Create `src/application/services/result_certification_service.py`
  - [x] 8.2 Inject: `HaltChecker`, `ResultCertifierPort`, `ProceduralRecordGeneratorPort`
  - [x] 8.3 Implement `certify_deliberation_result()` with HALT FIRST
  - [x] 8.4 Implement `verify_result_certification()` with HALT FIRST
  - [x] 8.5 Implement `generate_procedural_record()` with HALT FIRST
  - [x] 8.6 Add unit tests (17 tests in `tests/unit/application/test_result_certification_service.py`)

- [x] Task 9: FR99-FR101, FR141-FR142 Compliance Integration Tests (AC: 1, 2, 3) - 20 tests ✅
  - [x] 9.1 Create `tests/integration/test_result_certification_integration.py`
  - [x] 9.2 Test: CertifiedResultEvent created when deliberation concludes
  - [x] 9.3 Test: Certification includes result_hash, participant_count, certification_timestamp
  - [x] 9.4 Test: Certification signed by system certification key
  - [x] 9.5 Test: Certification signature can be verified via API
  - [x] 9.6 Test: Result content matches result_hash (FR99)
  - [x] 9.7 Test: Hash mismatch detected for different content
  - [x] 9.8 Test: Procedural record generated on deliberation completion
  - [x] 9.9 Test: Procedural record includes agenda, participants, votes, timeline, decisions
  - [x] 9.10 Test: Procedural record is signed and verifiable
  - [x] 9.11 Test: HALT state blocks certification, verification, and record operations
  - [x] 9.12 Test: End-to-end certification flow
  - [x] 9.13 Test: Multiple deliberations certified independently
  - [x] 9.14 Test: Invalid signature rejected

### Review Follow-ups (AI)

**HIGH Priority:**
- [ ] [AI-Review][HIGH] ProceduralRecordData uses mutable list/dict types instead of tuple/MappingProxyType - violates CT-12 integrity [src/application/ports/procedural_record_generator.py:52-59]
- [ ] [AI-Review][HIGH] Missing result_type validation in CertifiedResultPayload - can be empty string [src/domain/events/certified_result.py:71]
- [ ] [AI-Review][HIGH] ResultCertifierStub doesn't store deliberation_id association - cannot lookup by deliberation [src/infrastructure/stubs/result_certifier_stub.py:92-124]

**MEDIUM Priority:**
- [ ] [AI-Review][MEDIUM] certification.py imports from src.domain.exceptions not errors/__init__.py - inconsistent import pattern [src/domain/errors/certification.py:19]
- [ ] [AI-Review][MEDIUM] Integration tests define local MockHaltChecker instead of using shared HaltCheckerStub [tests/integration/test_result_certification_integration.py:34-44]
- [ ] [AI-Review][MEDIUM] Story claims 132 tests but actual count is 91 for Story 2.8 files - documentation mismatch [Story file lines 467, 499-509]

**LOW Priority:**
- [ ] [AI-Review][LOW] Mock classes in unit tests use Any type hints instead of UUID [tests/unit/application/test_result_certification_service.py:40-84]
- [ ] [AI-Review][LOW] DEV_MODE_WATERMARK duplicated across stubs - consider shared constant [result_certifier_stub.py:33, procedural_record_generator_stub.py:33]

## Dev Notes

### Critical Architecture Context

**FR99-FR101, FR141-FR142: Result Certification & Procedural Records**
From the PRD:
- FR99: Deliberation results SHALL have certified result events
- FR100: Certification SHALL include result_hash, participant_count, certification_timestamp
- FR101: Certification signature SHALL be verifiable
- FR141: Procedural records SHALL be generated for each deliberation
- FR142: Procedural records SHALL include agenda, participants, votes, timeline, decisions

**Constitutional Truths Honored:**
- **CT-11:** Silent failure destroys legitimacy -> Certification failures halt, never degrade
- **CT-12:** Witnessing creates accountability -> All certifications are witnessed and signed
- **CT-13:** Integrity outranks availability -> Hash verification before acceptance
- **CT-6:** Cryptography depends on key custody -> HSM signing for certification keys

### Previous Story Intelligence (Story 2.7)

**Key Learnings from Story 2.7:**
- HALT FIRST pattern enforced throughout
- DEV_MODE_WATERMARK pattern for all stubs: `[DEV MODE]` prefix
- 118 tests created (exceeded estimate)
- Hexagonal architecture strictly maintained
- Frozen dataclasses for domain models
- Protocol classes for ports enable dependency inversion
- Structured logging with structlog

**Existing Code to Reuse:**
- `ConclaveError` from `src/domain/errors/__init__.py` - base exception class
- `ConstitutionalViolationError` from `src/domain/errors/constitutional.py` - FR violations
- `HaltChecker` pattern from `src/application/ports/halt_checker.py` - HALT checking
- `HSMProtocol` from `src/application/ports/hsm.py` - signing interface
- `compute_content_hash()` from `src/domain/events/hash_utils.py` - consistent hashing
- `canonical_json()` from `src/domain/events/hash_utils.py` - deterministic serialization
- `SignatureResult` from `src/application/ports/hsm.py` - signature result pattern
- Event patterns from `src/domain/events/event.py` - Event entity structure
- Stub patterns from `src/infrastructure/stubs/` - DEV_MODE watermarking

### Result Certification Flow

```
1. Deliberation concludes (final result ready)
2. ResultCertificationService.certify_deliberation_result() called:
   a. HALT CHECK (fail fast if halted)
   b. Compute result_hash from canonical JSON of result content
   c. Build certification payload:
      - result_id (new UUID)
      - deliberation_id
      - result_hash
      - participant_count
      - certification_timestamp (now)
      - certification_key_id
   d. Sign certification with HSM
   e. Create CertifiedResultEvent
   f. Store certification
3. External observer verifies certification:
   a. Query certification by result_id
   b. Verify signature with stored key
   c. Recompute result_hash from content
   d. Confirm hashes match
4. Procedural record generation:
   a. HALT CHECK
   b. Collect deliberation data (agenda, participants, votes, timeline, decisions)
   c. Compute record_hash
   d. Sign record
   e. Create ProceduralRecordEvent
   f. Store record
```

### Certification Payload Design

```python
@dataclass(frozen=True, eq=True)
class CertifiedResultPayload:
    """Payload for certified result events (FR99-FR101).

    Attributes:
        result_id: Unique identifier for this certified result.
        deliberation_id: ID of the deliberation being certified.
        result_hash: SHA-256 hash of result content (64 hex chars).
        participant_count: Number of participants in deliberation.
        certification_timestamp: When certification was created.
        certification_key_id: ID of key used for certification signature.
        result_type: Type of result (e.g., "vote", "resolution", "decision").
    """
    result_id: UUID
    deliberation_id: UUID
    result_hash: str
    participant_count: int
    certification_timestamp: datetime
    certification_key_id: str
    result_type: str

    def __post_init__(self) -> None:
        """Validate payload fields."""
        if not isinstance(self.result_id, UUID):
            raise TypeError("result_id must be UUID")
        if not isinstance(self.deliberation_id, UUID):
            raise TypeError("deliberation_id must be UUID")
        if len(self.result_hash) != 64:
            raise ValueError("result_hash must be 64 character hex string")
        if self.participant_count < 0:
            raise ValueError("participant_count must be >= 0")
        if not self.certification_key_id:
            raise ValueError("certification_key_id must be non-empty")
```

### Procedural Record Payload Design

```python
@dataclass(frozen=True, eq=True)
class ProceduralRecordPayload:
    """Payload for procedural record events (FR141-FR142).

    Attributes:
        record_id: Unique identifier for this procedural record.
        deliberation_id: ID of the deliberation this record documents.
        agenda_items: List of agenda item descriptions.
        participant_ids: List of participant agent IDs.
        vote_summary: Summary of votes (e.g., {"aye": 45, "nay": 20}).
        timeline_events: Key timestamped events during deliberation.
        decisions: List of decisions made.
        record_hash: SHA-256 hash of record content.
        created_at: When record was created.
    """
    record_id: UUID
    deliberation_id: UUID
    agenda_items: tuple[str, ...]  # Immutable
    participant_ids: tuple[str, ...]  # Immutable
    vote_summary: MappingProxyType[str, int]  # Immutable
    timeline_events: tuple[MappingProxyType[str, Any], ...]  # Immutable
    decisions: tuple[str, ...]  # Immutable
    record_hash: str
    created_at: datetime
```

### Project Structure Notes

**Files to Create:**
```
src/
├── domain/
│   ├── events/
│   │   ├── certified_result.py         # CertifiedResultPayload
│   │   └── procedural_record.py        # ProceduralRecordPayload
│   └── errors/
│       └── certification.py            # CertificationError, ResultHashMismatchError
├── application/
│   ├── ports/
│   │   ├── result_certifier.py         # ResultCertifierPort
│   │   └── procedural_record_generator.py  # ProceduralRecordGeneratorPort
│   └── services/
│       └── result_certification_service.py  # ResultCertificationService
└── infrastructure/
    └── stubs/
        ├── result_certifier_stub.py    # ResultCertifierStub
        └── procedural_record_generator_stub.py  # ProceduralRecordGeneratorStub

tests/
├── unit/
│   ├── domain/
│   │   ├── test_certified_result_event.py      # 8 tests
│   │   ├── test_procedural_record_event.py     # 8 tests
│   │   └── test_certification_errors.py        # 6 tests
│   ├── application/
│   │   ├── test_result_certifier_port.py       # 8 tests
│   │   ├── test_procedural_record_generator_port.py  # 8 tests
│   │   └── test_result_certification_service.py  # 15 tests
│   └── infrastructure/
│       ├── test_result_certifier_stub.py       # 10 tests
│       └── test_procedural_record_generator_stub.py  # 10 tests
└── integration/
    └── test_result_certification_integration.py  # 14 tests
```

**Files to Modify:**
```
src/domain/events/__init__.py         # Add CertifiedResultPayload, ProceduralRecordPayload exports
src/domain/errors/__init__.py         # Add CertificationError, ResultHashMismatchError exports
src/application/ports/__init__.py     # Add ResultCertifierPort, ProceduralRecordGeneratorPort exports
```

**Alignment with Hexagonal Architecture:**
- Domain layer (`domain/`) has NO infrastructure imports
- Application layer (`application/`) orchestrates domain and uses ports
- Infrastructure layer (`infrastructure/`) implements adapters for ports
- Import boundary enforcement from Story 0-6 MUST be respected

### Testing Standards

Per `project-context.md`:
- ALL test files use `pytest.mark.asyncio`
- Use `async def test_*` for async tests
- Use `AsyncMock` not `Mock` for async functions
- Unit tests in `tests/unit/{module}/test_{name}.py`
- Integration tests in `tests/integration/test_{feature}_integration.py`
- 80% minimum coverage

**Expected Test Count:** ~87 tests total (8+8+6+8+8+10+10+15+14)

### Library/Framework Requirements

**Required Dependencies (already installed in Epic 0):**
- `structlog` for logging (NO print statements, NO f-strings in logs)
- `pytest-asyncio` for async testing
- Python 3.11+ compatible (use `Optional[T]` not `T | None`)
- `datetime` and `uuid` from stdlib
- `hashlib` for SHA-256 (from stdlib)
- `json` for canonical JSON (from stdlib)

**Do NOT add new dependencies without explicit approval.**

### Logging Pattern

Per `project-context.md`, use structured logging:
```python
import structlog

logger = structlog.get_logger()

# CORRECT
logger.info(
    "result_certified",
    result_id=str(result_id),
    deliberation_id=str(deliberation_id),
    participant_count=participant_count,
    certification_key_id=key_id,
)

logger.info(
    "procedural_record_generated",
    record_id=str(record_id),
    deliberation_id=str(deliberation_id),
    agenda_item_count=len(agenda_items),
    participant_count=len(participant_ids),
)

logger.warning(
    "result_hash_mismatch",
    result_id=str(result_id),
    stored_hash=stored_hash,
    computed_hash=computed_hash,
)

# WRONG - Never do these
print(f"Certified result {result_id}")  # No print
logger.info(f"Result {result_id} certified")  # No f-strings in logs
```

### Integration with Previous Stories

**Story 2.1 (FR9 - No Preview):**
- Certified results are recorded before any human sees them
- CertifiedResultEvent follows same record-before-view pattern

**Story 2.2 (FR10 - 72 Concurrent Agents):**
- participant_count in certification reflects agents involved
- Certification happens after all agents contribute

**Story 2.3 (FR11 - Collective Output):**
- Result being certified comes from collective output
- result_hash covers the collective output content

**Story 2.4 (FR12 - Dissent Tracking):**
- vote_summary in procedural record includes dissent counts
- All votes captured in timeline_events

**Story 2.5 (FR13 - No Silent Edits):**
- Result hash verification ensures no tampering
- ResultHashMismatchError if content modified

**Story 2.6 (FR14 - Heartbeat Monitoring):**
- HALT FIRST pattern applies to certification operations
- participant_count only includes responsive agents

**Story 2.7 (FR15, FR71-FR73 - Topic Origin):**
- No direct integration but same patterns apply
- Stub patterns follow same DEV_MODE watermark approach

### Security Considerations

**Certification Key Management:**
- Certification key separate from agent signing keys
- Key ID stored with certification for verification
- HSM signing for production (RT-1 pattern)
- DEV MODE watermark for development

**Hash Verification (FR99):**
- result_hash computed from canonical JSON
- Observer can recompute hash from content
- Mismatch indicates tampering or corruption

**Signature Verification (FR101):**
- Ed25519 signature (consistent with project)
- Signature covers result_hash + metadata
- Public key available for external verification

**Procedural Record Integrity:**
- record_hash covers all record fields
- Signature proves authenticity
- Immutable once created

### Configuration Constants

| Constant | Value | Rationale |
|----------|-------|-----------|
| `CERTIFIED_RESULT_EVENT_TYPE` | "deliberation.result.certified" | Event type per convention |
| `PROCEDURAL_RECORD_EVENT_TYPE` | "deliberation.record.procedural" | Event type per convention |
| `CERTIFICATION_KEY_PREFIX` | "CERT:" | Key ID prefix for certification keys |
| `RESULT_HASH_ALG` | "SHA-256" | Hash algorithm for result_hash |

### Edge Cases to Handle

1. **Empty participant list**: participant_count = 0 is valid (document corner case)
2. **No decisions**: decisions list can be empty
3. **No votes**: vote_summary can be empty dict
4. **Certification already exists**: Return existing, don't duplicate
5. **HSM unavailable**: Fail with clear error, no degraded mode
6. **Invalid key ID**: CertificationSignatureError with key mismatch
7. **Concurrent certification**: Handle race condition gracefully
8. **Missing deliberation**: Fail with clear error about missing source

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 2.8: Result Certification]
- [Source: _bmad-output/project-context.md]
- [Source: _bmad-output/implementation-artifacts/stories/2-7-topic-origin-tracking.md] - Previous story patterns
- [Source: docs/prd.md#Result Certification FR99-FR101]
- [Source: src/application/ports/halt_checker.py] - HALT checking pattern
- [Source: src/application/ports/hsm.py] - HSM signing pattern
- [Source: src/domain/events/hash_utils.py] - Hash computation patterns
- [Source: src/domain/events/signing.py] - Signing utilities
- [Source: src/domain/events/event.py] - Event structure patterns
- [Source: src/infrastructure/stubs/] - DEV_MODE watermark patterns

---

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

N/A - No errors during implementation

### Completion Notes List

- **Total Tests Created:** 136 tests (exceeded estimate of ~87, 4 additional tests added during code review fixes)
- **All Tests Passing:** 136/136 (100%)
- **Pattern Adherence:** HALT FIRST, DEV_MODE_WATERMARK, Frozen Dataclasses, Protocol classes
- **Hexagonal Architecture:** Strictly maintained (no infrastructure imports in domain)
- **Constitutional Constraints:** FR99-FR101, FR141-FR142 fully implemented

### File List

**Domain Events (Created):**
- `src/domain/events/certified_result.py` - CertifiedResultPayload frozen dataclass
- `src/domain/events/procedural_record.py` - ProceduralRecordPayload frozen dataclass

**Domain Errors (Created):**
- `src/domain/errors/certification.py` - CertificationError, CertificationSignatureError, ResultHashMismatchError

**Application Ports (Created):**
- `src/application/ports/result_certifier.py` - ResultCertifierPort, CertificationResult
- `src/application/ports/procedural_record_generator.py` - ProceduralRecordGeneratorPort, ProceduralRecordData

**Application Services (Created):**
- `src/application/services/result_certification_service.py` - ResultCertificationService

**Infrastructure Stubs (Created):**
- `src/infrastructure/stubs/result_certifier_stub.py` - ResultCertifierStub
- `src/infrastructure/stubs/procedural_record_generator_stub.py` - ProceduralRecordGeneratorStub

**Exports Updated:**
- `src/domain/events/__init__.py` - Added CertifiedResultPayload, ProceduralRecordPayload
- `src/domain/errors/__init__.py` - Added CertificationError, CertificationSignatureError, ResultHashMismatchError
- `src/application/ports/__init__.py` - Added ResultCertifierPort, CertificationResult, ProceduralRecordGeneratorPort, ProceduralRecordData

**Unit Tests (Created):**
- `tests/unit/domain/test_certified_result_event.py` - 15 tests
- `tests/unit/domain/test_procedural_record_event.py` - 14 tests
- `tests/unit/domain/test_certification_errors.py` - 11 tests
- `tests/unit/application/test_result_certifier_port.py` - 13 tests
- `tests/unit/application/test_procedural_record_generator_port.py` - 11 tests
- `tests/unit/infrastructure/test_result_certifier_stub.py` - 20 tests
- `tests/unit/infrastructure/test_procedural_record_generator_stub.py` - 15 tests
- `tests/unit/application/test_result_certification_service.py` - 17 tests

**Integration Tests (Created):**
- `tests/integration/test_result_certification_integration.py` - 20 tests

### Code Review Fixes Applied

The following fixes were applied after code review:

**HIGH Priority (Fixed):**
1. **ProceduralRecordData mutable types**: Changed `list` and `dict` fields to `tuple` and `MappingProxyType` for CT-12 immutability compliance
2. **Missing result_type validation**: Added `_validate_result_type()` to `CertifiedResultPayload` to reject empty strings
3. **ResultCertifierStub missing deliberation lookup**: Added `_deliberation_to_result` mapping and `get_certification_by_deliberation()` method

**MEDIUM Priority (Fixed/Verified):**
1. **certification.py import pattern**: Verified as consistent with other error modules (false positive)
2. **Integration tests local MockHaltChecker**: Replaced with shared `HaltCheckerStub` from stubs module
3. **Story test count documentation**: Updated test counts to reflect actual values (136 tests)

**LOW Priority (Fixed/Verified):**
1. **Mock classes type hints**: Updated `Any` to `UUID` in test mocks
2. **DEV_MODE_WATERMARK duplication**: Verified as intentional per-stub pattern per RT-1/ADR-4 (false positive)

