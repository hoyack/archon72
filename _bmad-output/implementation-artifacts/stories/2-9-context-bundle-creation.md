# Story 2.9: Context Bundle Creation (ADR-2)

Status: complete

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an **agent**,
I want my context bundle created correctly before deliberation,
So that I have the information needed to participate.

## Acceptance Criteria

### AC1: Context Bundle Required Fields
**Given** an agent is invoked for deliberation
**When** the context bundle is prepared
**Then** it includes: `schema_version`, `bundle_id`, `meeting_id`
**And** `as_of_event_seq` anchors the bundle to a specific event
**And** `identity_prompt_ref`, `meeting_state_ref`, `precedent_refs[]` are included

### AC2: Context Bundle Signing and Hash
**Given** a context bundle
**When** it is created
**Then** it is signed with the bundle creator's key
**And** `bundle_hash` is computed over canonical JSON
**And** bundle passes JSON Schema validation

### AC3: Context Bundle Validation
**Given** an agent receives a context bundle
**When** it validates the bundle
**Then** signature is verified before parsing
**And** invalid bundles are rejected with "ADR-2: Invalid context bundle signature"

## Tasks / Subtasks

- [ ] Task 1: Create ContextBundlePayload Domain Model (AC: 1, 2)
  - [ ] 1.1 Create `src/domain/models/context_bundle.py`
  - [ ] 1.2 Define `ContentRef` type alias for content-addressed references (ref:{sha256_hex})
  - [ ] 1.3 Define `ContextBundlePayload` frozen dataclass with all ADR-2 required fields
  - [ ] 1.4 Add `bundle_id` property (computed as `ctx_{meeting_id}_{as_of_event_seq}`)
  - [ ] 1.5 Add `to_dict()` method for canonical JSON serialization
  - [ ] 1.6 Add `__post_init__` validation for all fields
  - [ ] 1.7 Add to `src/domain/models/__init__.py` exports
  - [ ] 1.8 Add unit tests (~15 tests in `tests/unit/domain/test_context_bundle.py`)

- [ ] Task 2: Create ContextBundleCreatedEvent Domain Event (AC: 1)
  - [ ] 2.1 Create `src/domain/events/context_bundle_created.py`
  - [ ] 2.2 Define `ContextBundleCreatedPayload` frozen dataclass
  - [ ] 2.3 Add `to_dict()` method for event payload serialization
  - [ ] 2.4 Add `__post_init__` validation
  - [ ] 2.5 Define event type constant: `CONTEXT_BUNDLE_CREATED_EVENT_TYPE = "context.bundle.created"`
  - [ ] 2.6 Add to `src/domain/events/__init__.py` exports
  - [ ] 2.7 Add unit tests (~10 tests in `tests/unit/domain/test_context_bundle_created_event.py`)

- [ ] Task 3: Create Context Bundle Domain Errors (AC: 3)
  - [ ] 3.1 Create `src/domain/errors/context_bundle.py`
  - [ ] 3.2 Define `ContextBundleError(ConclaveError)` base class
  - [ ] 3.3 Define `InvalidBundleSignatureError(ContextBundleError)` - "ADR-2: Invalid context bundle signature"
  - [ ] 3.4 Define `StaleBundleError(ContextBundleError)` - as_of_event_seq not in canonical chain
  - [ ] 3.5 Define `BundleSchemaValidationError(ContextBundleError)` - JSON Schema validation failed
  - [ ] 3.6 Add to `src/domain/errors/__init__.py` exports
  - [ ] 3.7 Add unit tests (~12 tests in `tests/unit/domain/test_context_bundle_errors.py`)

- [ ] Task 4: Create ContextBundleCreatorPort Interface (AC: 1, 2)
  - [ ] 4.1 Create `src/application/ports/context_bundle_creator.py`
  - [ ] 4.2 Define `BundleCreationResult` frozen dataclass
  - [ ] 4.3 Define `ContextBundleCreatorPort(Protocol)`
  - [ ] 4.4 Add `create_bundle()` method signature
  - [ ] 4.5 Add `verify_bundle()` method signature
  - [ ] 4.6 Add to `src/application/ports/__init__.py` exports
  - [ ] 4.7 Add unit tests (~10 tests in `tests/unit/application/test_context_bundle_creator_port.py`)

- [ ] Task 5: Create ContextBundleValidatorPort Interface (AC: 3)
  - [ ] 5.1 Create `src/application/ports/context_bundle_validator.py`
  - [ ] 5.2 Define `BundleValidationResult` frozen dataclass
  - [ ] 5.3 Define `ContextBundleValidatorPort(Protocol)`
  - [ ] 5.4 Add `validate_signature()` method signature
  - [ ] 5.5 Add `validate_schema()` method signature
  - [ ] 5.6 Add `validate_freshness()` method signature (as_of_event_seq check)
  - [ ] 5.7 Add to `src/application/ports/__init__.py` exports
  - [ ] 5.8 Add unit tests (~10 tests in `tests/unit/application/test_context_bundle_validator_port.py`)

- [ ] Task 6: Create ContextBundleCreatorStub Infrastructure (AC: 1, 2)
  - [ ] 6.1 Create `src/infrastructure/stubs/context_bundle_creator_stub.py`
  - [ ] 6.2 Implement `ContextBundleCreatorStub` with DEV_MODE_WATERMARK pattern
  - [ ] 6.3 Implement `create_bundle()` with canonical JSON hashing and signing
  - [ ] 6.4 Implement `verify_bundle()` signature verification
  - [ ] 6.5 Follow RT-1 pattern (mode inside signature)
  - [ ] 6.6 Add unit tests (~15 tests in `tests/unit/infrastructure/test_context_bundle_creator_stub.py`)

- [ ] Task 7: Create ContextBundleValidatorStub Infrastructure (AC: 3)
  - [ ] 7.1 Create `src/infrastructure/stubs/context_bundle_validator_stub.py`
  - [ ] 7.2 Implement `ContextBundleValidatorStub` with DEV_MODE_WATERMARK pattern
  - [ ] 7.3 Implement `validate_signature()` with signature verification
  - [ ] 7.4 Implement `validate_schema()` with JSON Schema validation
  - [ ] 7.5 Implement `validate_freshness()` with as_of_event_seq check
  - [ ] 7.6 Add unit tests (~15 tests in `tests/unit/infrastructure/test_context_bundle_validator_stub.py`)

- [ ] Task 8: Create ContextBundleService Application Service (AC: 1, 2, 3)
  - [ ] 8.1 Create `src/application/services/context_bundle_service.py`
  - [ ] 8.2 Inject: `HaltChecker`, `ContextBundleCreatorPort`, `ContextBundleValidatorPort`, `EventStorePort`
  - [ ] 8.3 Implement `create_bundle_for_meeting()` with HALT FIRST
  - [ ] 8.4 Implement `validate_bundle()` with HALT FIRST
  - [ ] 8.5 Implement `get_current_head_seq()` for as_of_event_seq
  - [ ] 8.6 Add unit tests (~18 tests in `tests/unit/application/test_context_bundle_service.py`)

- [ ] Task 9: ADR-2 Compliance Integration Tests (AC: 1, 2, 3)
  - [ ] 9.1 Create `tests/integration/test_context_bundle_integration.py`
  - [ ] 9.2 Test: Context bundle includes all required fields (schema_version, bundle_id, meeting_id, as_of_event_seq)
  - [ ] 9.3 Test: Context bundle includes identity_prompt_ref, meeting_state_ref, precedent_refs[]
  - [ ] 9.4 Test: Bundle hash computed over canonical JSON
  - [ ] 9.5 Test: Bundle signed with creator's key
  - [ ] 9.6 Test: Signature verified before parsing content
  - [ ] 9.7 Test: Invalid signature rejected with "ADR-2: Invalid context bundle signature"
  - [ ] 9.8 Test: Stale as_of_event_seq rejected
  - [ ] 9.9 Test: Bundle with missing required fields fails schema validation
  - [ ] 9.10 Test: HALT state blocks bundle creation and validation
  - [ ] 9.11 Test: End-to-end bundle creation and validation flow
  - [ ] 9.12 Test: precedent_refs maximum of 10 enforced
  - [ ] 9.13 Test: ContentRef format validation (ref:{sha256_hex})

## Dev Notes

### Critical Architecture Context

**ADR-2: Context Reconstruction + Signature Trust**
From the Architecture document:

> Agents are stateless. Deliberation coherence requires deterministic, verifiable context bundles. Bundles must be human-debuggable and schema-valid.

**Decision:** Use signed JSON context bundles with JSON Schema validation.

**Format Requirements (from ADR-002):**
- Canonical JSON serialization (sorted keys, stable encoding)
- Required fields:
  - `schema_version` (e.g., "1.0")
  - `bundle_id` (computed as `ctx_{meeting_id}_{as_of_event_seq}`)
  - `meeting_id` (UUID)
  - `as_of_event_seq` (sequence number anchor for determinism)
  - `identity_prompt_ref` (ContentRef to agent identity)
  - `meeting_state_ref` (ContentRef to meeting state)
  - `precedent_refs[]` (ContentRef array, max 10)
  - `bundle_hash` (SHA-256 of canonical JSON)
  - `signature` (Ed25519 signature)
  - `signing_key_id` (key identifier)
  - `created_at` (datetime)

**Integrity Requirements:**
- Bundle is **signed at creation** time
- Receivers verify signature **before parsing/using** bundle
- Bundle references are content-addressed (hash refs) where possible

**Acceptance Criteria (from ADR-002):**
- Any agent invocation without a valid bundle signature is rejected
- Any bundle whose `as_of_event_seq` does not exist in canonical chain is rejected
- Decision artifacts must record `bundle_hash` for traceability

### Constitutional Truths Honored

| CT | Truth | Implication |
|----|-------|-------------|
| **CT-1** | LLMs are stateless | Context bundles provide deterministic state |
| **CT-11** | Silent failure destroys legitimacy | Invalid bundles halt, never degrade |
| **CT-12** | Witnessing creates accountability | Bundle hash creates audit trail |
| **CT-13** | Integrity outranks availability | Signature verification mandatory |

### MA-3: Temporal Determinism Pattern (CRITICAL)

From Architecture - "The Non-Obvious Truth":

> Context bundles snapshot reality at a specific sequence number for reproducibility.

```python
# WRONG - "latest" is non-deterministic
async def build_agent_context(meeting_id: str) -> ContextBundle:
    events = await event_store.get_all_events(meeting_id)
    return ContextBundle(meeting_id=meeting_id, events=events)

# RIGHT - snapshot at specific sequence
async def build_agent_context(meeting_id: str) -> ContextBundle:
    current_seq = await event_store.get_head_seq()
    events = await event_store.get_events(meeting_id, up_to_seq=current_seq)
    return ContextBundle(
        meeting_id=meeting_id,
        as_of_event_seq=current_seq,
        events=events,
    )
```

**Why this matters:**
- Agent deliberations are reproducible
- Auditors can replay decisions with identical context
- New events during deliberation don't corrupt in-flight decisions

**Key Insight:** "Latest" is non-deterministic. `as_of_event_seq` makes time explicit.

### Previous Story Intelligence (Story 2.8)

**Key Learnings from Story 2.8:**
- HALT FIRST pattern enforced throughout
- DEV_MODE_WATERMARK pattern for all stubs: `[DEV MODE]` prefix
- 136 tests created (exceeded estimate)
- Hexagonal architecture strictly maintained
- Frozen dataclasses for domain models
- Protocol classes for ports enable dependency inversion
- Structured logging with structlog

**Existing Code to Reuse:**
- `ConclaveError` from `src/domain/errors/__init__.py` - base exception class
- `HaltChecker` pattern from `src/application/ports/halt_checker.py` - HALT checking
- `HSMProtocol` from `src/application/ports/hsm.py` - signing interface
- `compute_content_hash()` from `src/domain/events/hash_utils.py` - consistent hashing
- `canonical_json()` from `src/domain/events/hash_utils.py` - deterministic serialization
- `SignatureResult` from `src/application/ports/hsm.py` - signature result pattern
- Stub patterns from `src/infrastructure/stubs/` - DEV_MODE watermarking
- Existing `ContextBundle` in `src/application/ports/agent_orchestrator.py` - simple version to enhance

**Important:** The existing `ContextBundle` in agent_orchestrator.py is a minimal version. This story creates the full ADR-2 compliant version with signing and validation.

### Context Bundle Flow

```
1. Meeting deliberation starts
2. ContextBundleService.create_bundle_for_meeting() called:
   a. HALT CHECK (fail fast if halted)
   b. Get current head sequence from event store (as_of_event_seq)
   c. Collect meeting state (up to as_of_event_seq)
   d. Collect precedent references (max 10, content-addressed)
   e. Build ContextBundlePayload:
      - schema_version = "1.0"
      - bundle_id = ctx_{meeting_id}_{as_of_event_seq}
      - meeting_id
      - as_of_event_seq
      - identity_prompt_ref (ContentRef)
      - meeting_state_ref (ContentRef)
      - precedent_refs[] (ContentRef array)
      - created_at (now)
   f. Compute bundle_hash from canonical JSON
   g. Sign bundle with creator's key
   h. Add signature and signing_key_id
   i. Create ContextBundleCreatedEvent
3. Agent receives bundle:
   a. Validate signature BEFORE parsing
   b. Verify as_of_event_seq exists in chain
   c. Parse and use bundle
4. Agent decision recorded with bundle_hash for traceability
```

### ContextBundlePayload Design (ADR-002 Compliant)

```python
from typing import Literal
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

# ContentRef type for content-addressed references
# Format: ref:{sha256_hex} (68 chars total)
ContentRef = str  # Pattern: "ref:[a-f0-9]{64}"

@dataclass(frozen=True, eq=True)
class ContextBundlePayload:
    """Deterministic context for agent invocation (ADR-2).

    Attributes:
        schema_version: Bundle schema version ("1.0").
        meeting_id: UUID of the meeting being deliberated.
        as_of_event_seq: Sequence number anchor for determinism.
        identity_prompt_ref: ContentRef to agent identity prompt.
        meeting_state_ref: ContentRef to meeting state snapshot.
        precedent_refs: Tuple of ContentRefs to relevant precedents (max 10).
        created_at: When bundle was created.
        bundle_hash: SHA-256 hash of canonical JSON (excluding signature fields).
        signature: Ed25519 signature of bundle_hash.
        signing_key_id: ID of key used for signing.
    """
    schema_version: Literal["1.0"]
    meeting_id: UUID
    as_of_event_seq: int
    identity_prompt_ref: ContentRef
    meeting_state_ref: ContentRef
    precedent_refs: tuple[ContentRef, ...]  # Max 10, immutable
    created_at: datetime
    bundle_hash: str
    signature: str
    signing_key_id: str

    @property
    def bundle_id(self) -> str:
        """Compute bundle_id from meeting_id and as_of_event_seq."""
        return f"ctx_{self.meeting_id}_{self.as_of_event_seq}"

    def __post_init__(self) -> None:
        """Validate payload fields."""
        if self.schema_version != "1.0":
            raise ValueError("schema_version must be '1.0'")
        if not isinstance(self.meeting_id, UUID):
            raise TypeError("meeting_id must be UUID")
        if self.as_of_event_seq < 1:
            raise ValueError("as_of_event_seq must be >= 1")
        if not self.identity_prompt_ref.startswith("ref:"):
            raise ValueError("identity_prompt_ref must be ContentRef (ref:{hash})")
        if len(self.identity_prompt_ref) != 68:
            raise ValueError("identity_prompt_ref must be 68 chars (ref: + 64 hex)")
        if not self.meeting_state_ref.startswith("ref:"):
            raise ValueError("meeting_state_ref must be ContentRef (ref:{hash})")
        if len(self.meeting_state_ref) != 68:
            raise ValueError("meeting_state_ref must be 68 chars (ref: + 64 hex)")
        if len(self.precedent_refs) > 10:
            raise ValueError("Maximum 10 precedent references allowed")
        for ref in self.precedent_refs:
            if not ref.startswith("ref:"):
                raise ValueError(f"precedent_ref must be ContentRef: {ref}")
            if len(ref) != 68:
                raise ValueError(f"precedent_ref must be 68 chars: {ref}")
        if len(self.bundle_hash) != 64:
            raise ValueError("bundle_hash must be 64 character hex string")
        if not self.signature:
            raise ValueError("signature must be non-empty")
        if not self.signing_key_id:
            raise ValueError("signing_key_id must be non-empty")
```

### Project Structure Notes

**Files to Create:**
```
src/
├── domain/
│   ├── models/
│   │   └── context_bundle.py          # ContextBundlePayload, ContentRef
│   ├── events/
│   │   └── context_bundle_created.py  # ContextBundleCreatedPayload
│   └── errors/
│       └── context_bundle.py          # ContextBundleError, InvalidBundleSignatureError, etc.
├── application/
│   ├── ports/
│   │   ├── context_bundle_creator.py  # ContextBundleCreatorPort
│   │   └── context_bundle_validator.py # ContextBundleValidatorPort
│   └── services/
│       └── context_bundle_service.py  # ContextBundleService
└── infrastructure/
    └── stubs/
        ├── context_bundle_creator_stub.py   # ContextBundleCreatorStub
        └── context_bundle_validator_stub.py # ContextBundleValidatorStub

tests/
├── unit/
│   ├── domain/
│   │   ├── test_context_bundle.py                # ~15 tests
│   │   ├── test_context_bundle_created_event.py  # ~10 tests
│   │   └── test_context_bundle_errors.py         # ~12 tests
│   ├── application/
│   │   ├── test_context_bundle_creator_port.py   # ~10 tests
│   │   ├── test_context_bundle_validator_port.py # ~10 tests
│   │   └── test_context_bundle_service.py        # ~18 tests
│   └── infrastructure/
│       ├── test_context_bundle_creator_stub.py   # ~15 tests
│       └── test_context_bundle_validator_stub.py # ~15 tests
└── integration/
    └── test_context_bundle_integration.py        # ~13 tests
```

**Files to Modify:**
```
src/domain/models/__init__.py         # Add ContextBundlePayload, ContentRef exports
src/domain/events/__init__.py         # Add ContextBundleCreatedPayload export
src/domain/errors/__init__.py         # Add ContextBundleError, etc. exports
src/application/ports/__init__.py     # Add ContextBundleCreatorPort, ContextBundleValidatorPort exports
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

**Expected Test Count:** ~118 tests total (15+10+12+10+10+15+15+18+13)

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
    "context_bundle_created",
    bundle_id=bundle.bundle_id,
    meeting_id=str(meeting_id),
    as_of_event_seq=as_of_event_seq,
    bundle_hash_prefix=bundle_hash[:8],
    signing_key_id=signing_key_id,
)

logger.warning(
    "invalid_bundle_signature",
    bundle_id=bundle_id,
    expected_key_id=expected_key_id,
    provided_key_id=provided_key_id,
)

logger.error(
    "stale_bundle_rejected",
    bundle_id=bundle_id,
    as_of_event_seq=as_of_event_seq,
    current_head_seq=current_head_seq,
)

# WRONG - Never do these
print(f"Created bundle {bundle_id}")  # No print
logger.info(f"Bundle {bundle_id} created")  # No f-strings in logs
```

### Integration with Previous Stories

**Story 2.2 (FR10 - 72 Concurrent Agents):**
- Context bundles are passed to agents via AgentOrchestratorProtocol
- Each agent gets isolated, signed context bundle

**Story 2.8 (FR99-FR101 - Result Certification):**
- Decision artifacts record `bundle_hash` for traceability
- CertifiedResultPayload can reference bundle used for deliberation

**Epic 1 (Event Store):**
- `as_of_event_seq` references event store sequence number
- Bundle validation checks sequence exists in chain

### Security Considerations

**Bundle Signing (ADR-2):**
- Bundle signed at creation time (not later)
- Signature covers bundle_hash, not just payload
- HSM signing for production (RT-1 pattern)
- DEV MODE watermark for development

**Signature Verification (ADR-2):**
- MUST verify signature BEFORE parsing/using content
- Invalid signature = immediate rejection
- Error message: "ADR-2: Invalid context bundle signature"

**ContentRef Format:**
- Format: `ref:{sha256_hex}`
- Total length: 68 characters (4 prefix + 64 hex)
- Enables content-addressed verification

**Stale Bundle Detection:**
- `as_of_event_seq` must exist in canonical chain
- If sequence gap detected, bundle is stale
- Stale bundles rejected (integrity over availability)

### Configuration Constants

| Constant | Value | Rationale |
|----------|-------|-----------|
| `CONTEXT_BUNDLE_SCHEMA_VERSION` | "1.0" | Initial schema version |
| `CONTEXT_BUNDLE_CREATED_EVENT_TYPE` | "context.bundle.created" | Event type per convention |
| `MAX_PRECEDENT_REFS` | 10 | Max precedent references per ADR-2 |
| `CONTENT_REF_PREFIX` | "ref:" | ContentRef prefix |
| `CONTENT_REF_LENGTH` | 68 | Total length: ref: + 64 hex |
| `BUNDLE_ID_PREFIX` | "ctx_" | Bundle ID prefix |

### Edge Cases to Handle

1. **Empty precedent_refs**: Valid - tuple can be empty
2. **Max precedent_refs exceeded**: Reject with clear error (max 10)
3. **Invalid ContentRef format**: Reject with specific validation error
4. **as_of_event_seq = 0**: Invalid - must be >= 1
5. **Missing signature**: Reject - signature is mandatory
6. **Signature verification fails**: Reject with "ADR-2: Invalid context bundle signature"
7. **Stale sequence number**: as_of_event_seq not in chain = reject
8. **Future sequence number**: as_of_event_seq > head = reject as invalid
9. **Invalid schema_version**: Only "1.0" currently supported
10. **HSM unavailable**: Fail with clear error, no degraded mode

### Anti-Pattern Alert (AP-5: The Latest Fetcher)

From Architecture document:

```python
# ❌ ANTI-PATTERN: Always use latest events
async def build_agent_context(meeting_id: str) -> ContextBundle:
    events = await event_store.get_all_events(meeting_id)
    return ContextBundle(meeting_id=meeting_id, events=events)

# ✅ CORRECT: Snapshot at specific sequence
async def build_agent_context(meeting_id: str) -> ContextBundle:
    current_seq = await event_store.get_head_seq()
    events = await event_store.get_events(meeting_id, up_to_seq=current_seq)
    return ContextBundle(
        meeting_id=meeting_id,
        as_of_event_seq=current_seq,
        events=events,
    )
```

**Violation:** MA-3, ADR-002. "Latest" is non-deterministic.

### References

- [Source: _bmad-output/planning-artifacts/architecture.md#ADR-002 — Context Bundles]
- [Source: _bmad-output/planning-artifacts/architecture.md#Context Bundle Patterns]
- [Source: _bmad-output/planning-artifacts/architecture.md#MA-3: Temporal Determinism]
- [Source: _bmad-output/planning-artifacts/architecture.md#AP-5: The Latest Fetcher]
- [Source: _bmad-output/planning-artifacts/epics.md#Story 2.9: Context Bundle Creation]
- [Source: _bmad-output/project-context.md]
- [Source: _bmad-output/implementation-artifacts/stories/2-8-result-certification.md] - Previous story patterns
- [Source: src/application/ports/halt_checker.py] - HALT checking pattern
- [Source: src/application/ports/hsm.py] - HSM signing pattern
- [Source: src/domain/events/hash_utils.py] - Hash computation patterns (canonical_json, compute_content_hash)
- [Source: src/infrastructure/stubs/result_certifier_stub.py] - DEV_MODE watermark patterns
- [Source: src/application/ports/agent_orchestrator.py] - Existing simple ContextBundle

---

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List

