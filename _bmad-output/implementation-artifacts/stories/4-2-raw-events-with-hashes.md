# Story 4.2: Raw Events with Hashes (FR45)

## Story

**As an** external observer,
**I want** raw events returned with all hashes,
**So that** I can verify chain integrity myself.

## Status

Status: done

## Context

### Business Context
This story is the second in Epic 4 (Observer Verification Interface). It builds on Story 4.1 (Public Read Access) by ensuring that the event responses include ALL hash chain data necessary for independent verification.

The core principle: External observers must be able to independently recompute and verify the hash chain without trusting the system. This requires exposing:
1. **Raw payload**: Untransformed JSON exactly as stored
2. **All hash fields**: `content_hash`, `prev_hash`, `signature`
3. **Algorithm versioning**: `hash_alg_version`, `sig_alg_version`
4. **Complete verification data**: Everything needed to verify signatures and chain continuity

Key business drivers:
1. **Verification independence**: Observers can verify claims without trusting system calculations
2. **Algorithm transparency**: Hash and signature algorithm versions enable proper verification
3. **Chain continuity proof**: `prev_hash` enables walking the chain backwards for integrity checks

### Technical Context
- **FR45**: Query interface SHALL return raw events with hashes
- **FR62**: Observer interface SHALL provide raw event data sufficient for independent hash computation
- **FR63**: System SHALL publish exact hash algorithm, encoding, and field ordering as immutable specification
- **ADR-1**: DB-level hash enforcement uses SHA-256, hex-encoded

**Existing Implementation (Story 4.1):**
- `ObserverEventResponse` model already includes: `content_hash`, `prev_hash`, `signature`, `hash_algorithm_version`
- `EventToObserverAdapter` maps domain `Event` to API response
- Observer routes return events with hash data

**Gap Analysis:**
The current implementation has the foundation but needs enhancement:
1. **Raw payload verification**: Ensure payload is returned as-is, not transformed
2. **Algorithm version fields**: Add `sig_alg_version` to response
3. **Verification specification**: Document exact hash computation method
4. **Genesis anchor**: Document the genesis hash constant for chain root verification

### Dependencies
- **Story 4.1**: Public read access endpoints (DONE)
- **Story 1.2**: Hash chain implementation (content_hash, prev_hash)
- **Story 1.3**: Agent attribution and signing (signature, sig_alg_version)

### Constitutional Constraints
- **FR45**: Query interface SHALL return raw events with hashes
- **FR62**: Raw event data sufficient for independent hash computation
- **FR63**: Exact hash algorithm, encoding, field ordering as immutable specification
- **FR64**: Verification bundles in standard format for offline verification
- **CT-11**: Silent failure destroys legitimacy - verification must be possible
- **CT-12**: Witnessing creates accountability - hash chain creates verifiable history

### Architecture Decision
Per architecture.md (Hash Rules):
- Hash algorithm: SHA-256
- Chain construction: Event signature MUST cover `prev_hash` to prevent reordering
- Event record stores: `prev_hash`, `content_hash`, `signature`, `hash_alg_version`, `sig_alg_version`

From `src/domain/events/hash_utils.py`:
- `GENESIS_HASH = "0" * 64` - 64 zeros for sequence 1
- `HASH_ALG_VERSION = 1` - Version 1 = SHA-256
- `canonical_json()` - Deterministic JSON with sorted keys, no whitespace
- Hash excludes: `prev_hash`, `content_hash`, `sequence`, `authority_timestamp`
- Hash includes: `event_type`, `payload`, `signature`, `witness_id`, `witness_signature`, `local_timestamp`, `agent_id`

## Acceptance Criteria

### AC1: Event response includes all hash fields
**Given** I query an event
**When** the response is returned
**Then** it includes: `content_hash`, `prev_hash`, `signature`
**And** the raw payload is included (not transformed)

### AC2: Hash algorithm version is included
**Given** event response format
**When** I examine it
**Then** hash algorithm version is included
**And** all fields needed for verification are present

### AC3: Signature algorithm version is included (NEW)
**Given** event response format
**When** I examine it
**Then** signature algorithm version (`sig_alg_version`) is included
**And** matches the algorithm used for signing (1 = Ed25519)

### AC4: Genesis hash is documented (NEW)
**Given** the verification specification
**When** I verify the first event (sequence 1)
**Then** I can confirm `prev_hash` equals the documented genesis constant
**And** the genesis constant is "0" * 64 (64 zeros)

### AC5: Canonical JSON specification is documented (NEW)
**Given** the verification specification
**When** I want to recompute content_hash
**Then** I have documentation of:
  - Which fields are included in hash computation
  - Which fields are excluded (and why)
  - The exact JSON canonicalization rules
  - The hash algorithm and encoding

## Tasks

### Task 1: Add sig_alg_version to ObserverEventResponse
Enhance the response model to include signature algorithm version.

**Files:**
- `src/api/models/observer.py` (modify)
- `tests/unit/api/test_observer_models.py` (modify)

**Test Cases (RED):**
- `test_observer_event_response_includes_sig_alg_version`
- `test_sig_alg_version_defaults_to_ed25519`

**Implementation (GREEN):**
```python
# In ObserverEventResponse, add:
sig_alg_version: str = Field(default="Ed25519")
```

### Task 2: Update EventToObserverAdapter to map sig_alg_version
Map the domain Event's `sig_alg_version` to the response.

**Files:**
- `src/api/adapters/observer.py` (modify)
- `tests/unit/api/test_observer_adapter.py` (modify)

**Test Cases (RED):**
- `test_adapter_maps_sig_alg_version`
- `test_adapter_converts_sig_alg_version_to_string`

**Implementation (GREEN):**
```python
# In EventToObserverAdapter.to_response(), add:
sig_alg_version=_format_sig_alg_version(event.sig_alg_version),

def _format_sig_alg_version(version: int) -> str:
    """Convert numeric sig_alg_version to string name.

    Version mapping:
    - 1: Ed25519
    """
    if version == 1:
        return "Ed25519"
    return f"Unknown({version})"
```

### Task 3: Create HashVerificationSpec response model
Create a model that documents the verification specification.

**Files:**
- `src/api/models/observer.py` (modify)
- `tests/unit/api/test_observer_models.py` (modify)

**Test Cases (RED):**
- `test_hash_verification_spec_fields`
- `test_verification_spec_documents_genesis`
- `test_verification_spec_documents_excluded_fields`

**Implementation (GREEN):**
```python
class HashVerificationSpec(BaseModel):
    """Hash verification specification (FR62, FR63).

    Documents the exact hash computation method for independent verification.
    This is an immutable specification - changes require new version.
    """

    hash_algorithm: str = Field(default="SHA-256")
    hash_algorithm_version: int = Field(default=1)
    signature_algorithm: str = Field(default="Ed25519")
    signature_algorithm_version: int = Field(default=1)
    genesis_hash: str = Field(default="0" * 64)
    genesis_description: str = Field(
        default="64 zeros representing no previous event (sequence 1)"
    )

    # Fields included in content_hash computation
    hash_includes: list[str] = Field(default=[
        "event_type",
        "payload",
        "signature",
        "witness_id",
        "witness_signature",
        "local_timestamp",
        "agent_id (if present)",
    ])

    # Fields excluded from hash (with reasons)
    hash_excludes: list[str] = Field(default=[
        "prev_hash (would create circular dependency)",
        "content_hash (self-reference)",
        "sequence (assigned by database)",
        "authority_timestamp (set by database)",
        "hash_alg_version (metadata, not content)",
        "sig_alg_version (metadata, not content)",
    ])

    # JSON canonicalization rules
    json_canonicalization: str = Field(default=(
        "Keys sorted alphabetically (recursive), no whitespace between "
        "elements (separators=(',', ':')), ensure_ascii=False"
    ))

    # Hash encoding
    hash_encoding: str = Field(default="lowercase hexadecimal (64 characters)")
```

### Task 4: Create verification spec endpoint
Add endpoint that returns the verification specification.

**Files:**
- `src/api/routes/observer.py` (modify)
- `tests/unit/api/test_observer_routes.py` (modify)

**Test Cases (RED):**
- `test_get_verification_spec_no_auth_required`
- `test_verification_spec_returns_complete_spec`
- `test_verification_spec_genesis_hash_is_64_zeros`

**Implementation (GREEN):**
```python
@router.get("/verification-spec", response_model=HashVerificationSpec)
async def get_verification_spec(
    request: Request,
    rate_limiter: ObserverRateLimiter = Depends(get_rate_limiter),
) -> HashVerificationSpec:
    """Get hash verification specification.

    Returns the exact hash computation method for independent
    verification (FR62, FR63).

    No authentication required (FR44).
    """
    await rate_limiter.check_rate_limit(request)
    return HashVerificationSpec()
```

### Task 5: Add verify_hash helper function
Create a utility function that observers can reference for verification.

**Files:**
- `src/api/models/observer.py` (modify - add as staticmethod)
- `tests/unit/api/test_observer_models.py` (modify)

**Test Cases (RED):**
- `test_verify_content_hash_correct_hash`
- `test_verify_content_hash_wrong_hash`
- `test_verify_content_hash_matches_domain_computation`

**Implementation (GREEN):**
```python
class ObserverEventResponse(BaseModel):
    # ... existing fields ...

    def compute_expected_hash(self) -> str:
        """Compute expected content_hash from event fields.

        This method allows observers to independently verify
        the content_hash using the documented specification.

        Returns:
            The computed SHA-256 hash in lowercase hex.
        """
        import hashlib
        import json

        hashable: dict[str, Any] = {
            "event_type": self.event_type,
            "payload": self.payload,
            "signature": self.signature,
            "witness_id": self.witness_id,
            "witness_signature": self.witness_signature,
            "local_timestamp": self.local_timestamp.isoformat(),
        }

        if self.agent_id:
            hashable["agent_id"] = self.agent_id

        canonical = json.dumps(
            hashable,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
```

### Task 6: Ensure raw payload is not transformed
Verify and document that payload is returned exactly as stored.

**Files:**
- `tests/unit/api/test_observer_adapter.py` (modify)
- `tests/integration/test_raw_events_integration.py` (new)

**Test Cases (RED):**
- `test_payload_not_transformed_unicode`
- `test_payload_preserves_nested_structure`
- `test_payload_preserves_special_characters`
- `test_payload_preserves_numeric_precision`

**Implementation (GREEN):**
The adapter already converts `MappingProxyType` to `dict` without transformation.
Add documentation and tests to verify this behavior is preserved.

### Task 7: Create chain verification endpoint
Add endpoint to verify a range of events form a valid chain.

**Files:**
- `src/api/routes/observer.py` (modify)
- `src/api/models/observer.py` (modify)
- `src/application/services/observer_service.py` (modify)
- `tests/unit/application/test_observer_service.py` (modify)
- `tests/integration/test_raw_events_integration.py` (new)

**Test Cases (RED):**
- `test_verify_chain_valid_range`
- `test_verify_chain_invalid_hash`
- `test_verify_chain_genesis_anchor`

**Implementation (GREEN):**
```python
class ChainVerificationResult(BaseModel):
    """Result of chain verification request."""
    start_sequence: int
    end_sequence: int
    is_valid: bool
    first_invalid_sequence: Optional[int] = None
    error_message: Optional[str] = None
    verified_count: int

@router.get("/verify-chain", response_model=ChainVerificationResult)
async def verify_chain(
    request: Request,
    start: int = Query(ge=1),
    end: int = Query(ge=1),
    observer_service: ObserverService = Depends(get_observer_service),
    rate_limiter: ObserverRateLimiter = Depends(get_rate_limiter),
) -> ChainVerificationResult:
    """Verify hash chain integrity for a range of events.

    Returns verification result including first invalid event
    if chain is broken.
    """
    await rate_limiter.check_rate_limit(request)
    return await observer_service.verify_chain(start, end)
```

### Task 8: Integration tests for FR45 compliance
Comprehensive integration tests for raw events with hashes.

**Files:**
- `tests/integration/test_raw_events_integration.py` (new)

**Test Cases:**
- `test_fr45_content_hash_present`
- `test_fr45_prev_hash_present`
- `test_fr45_signature_present`
- `test_fr45_raw_payload_untransformed`
- `test_fr45_hash_alg_version_present`
- `test_fr45_sig_alg_version_present`
- `test_fr62_sufficient_for_hash_computation`
- `test_fr63_verification_spec_immutable`
- `test_genesis_prev_hash_is_64_zeros`
- `test_chain_continuity_verifiable`

## Technical Notes

### Implementation Order
1. Task 1: Add sig_alg_version to response model
2. Task 2: Update adapter to map sig_alg_version
3. Task 3: Create HashVerificationSpec model
4. Task 4: Create verification spec endpoint
5. Task 5: Add compute_expected_hash helper
6. Task 6: Verify raw payload preservation
7. Task 7: Create chain verification endpoint
8. Task 8: Integration tests

### Testing Strategy
- Unit tests for each model and adapter change
- Integration tests for API endpoints
- Verification tests that compare computed vs stored hashes
- All tests follow red-green-refactor TDD cycle

### Constitutional Compliance Matrix
| Requirement | Implementation |
|-------------|----------------|
| FR45 | Response includes content_hash, prev_hash, signature |
| FR62 | compute_expected_hash() enables independent verification |
| FR63 | HashVerificationSpec documents immutable specification |
| FR64 | verify-chain endpoint enables offline verification |
| CT-11 | Verification failure returns clear error message |
| CT-12 | Hash chain enables verifiable history |

### Key Design Decisions
1. **String algorithm versions**: Use human-readable names ("SHA256", "Ed25519") in API, numeric internally
2. **Verification spec endpoint**: Dedicated endpoint documents exact computation method
3. **compute_expected_hash**: Method on response model for easy verification
4. **Chain verification**: Server-side helper, observers can also verify client-side

### Hash Computation Reference
From `src/domain/events/hash_utils.py`:

```python
# Genesis hash for sequence 1
GENESIS_HASH = "0" * 64

# Content hash computation
hashable = {
    "event_type": event_data["event_type"],
    "payload": event_data["payload"],
    "signature": event_data["signature"],
    "witness_id": event_data["witness_id"],
    "witness_signature": event_data["witness_signature"],
    "local_timestamp": local_ts.isoformat(),
}
if agent_id is not None:
    hashable["agent_id"] = agent_id

canonical = json.dumps(hashable, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
content_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
```

### Previous Story Intelligence (Story 4.1)
From Story 4.1 completion:
- Response model already includes most hash fields
- Adapter already handles MappingProxyType → dict conversion
- Rate limiter applies to all observer endpoints
- No auth middleware pattern established
- 60 tests passing (36 unit + 11 service + 13 integration)

Files created in 4.1 that will be modified:
- `src/api/models/observer.py` - Add sig_alg_version, HashVerificationSpec
- `src/api/adapters/observer.py` - Map sig_alg_version
- `src/api/routes/observer.py` - Add verification-spec and verify-chain endpoints
- `src/application/services/observer_service.py` - Add verify_chain method

### Patterns from Previous Stories to Follow
- Router prefix: `/v1/observer`
- Tags: `tags=["observer"]`
- No auth dependency (FR44)
- Rate limiter on all endpoints (FR48)
- Async handlers: `async def handler() -> Response`
- Dependencies via `Depends()`

## Dev Notes

### Project Structure Notes
- Response models: `src/api/models/observer.py`
- Adapter: `src/api/adapters/observer.py`
- Routes: `src/api/routes/observer.py`
- Service: `src/application/services/observer_service.py`
- Hash utils: `src/domain/events/hash_utils.py` (reference only, don't modify)

### References
- [Source: _bmad-output/planning-artifacts/epics.md#Story-4.2]
- [Source: _bmad-output/planning-artifacts/architecture.md#Hash-rules]
- [Source: _bmad-output/planning-artifacts/prd.md#FR45]
- [Source: _bmad-output/planning-artifacts/prd.md#FR62-FR63]
- [Source: src/domain/events/hash_utils.py - Hash computation reference]
- [Source: src/api/models/observer.py - Existing response model]
- [Source: src/api/adapters/observer.py - Existing adapter]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

None

### Completion Notes List

All 8 tasks completed successfully following TDD (Red-Green-Refactor cycle):

1. **Task 1**: Added `sig_alg_version: str = Field(default="Ed25519")` to ObserverEventResponse
2. **Task 2**: Updated EventToObserverAdapter with `_format_sig_alg_version()` helper to convert numeric version to string name
3. **Task 3**: Created HashVerificationSpec model with complete documentation of hash computation method (FR62, FR63)
4. **Task 4**: Created `/v1/observer/verification-spec` endpoint returning immutable hash specification
5. **Task 5**: Added `compute_expected_hash()` method to ObserverEventResponse for independent verification
6. **Task 6**: Verified raw payload preservation with unicode, nested structures, special characters, and numeric precision tests
7. **Task 7**: Created `/v1/observer/verify-chain` endpoint with ChainVerificationResult model and verify_chain service method
8. **Task 8**: Created 13 integration tests covering FR45, FR62, FR63, FR64 compliance

**Test Results**: 62 tests passing (22 model + 15 adapter + 12 route + 13 integration)

**Constitutional Compliance Verified**:
- FR45: Raw events with all hashes (content_hash, prev_hash, signature)
- FR62: compute_expected_hash() enables independent verification
- FR63: HashVerificationSpec documents immutable specification
- FR64: verify-chain endpoint provides verification bundles

### File List

**Modified Files:**
- `src/api/models/observer.py` - Added sig_alg_version, HashVerificationSpec, ChainVerificationResult, compute_expected_hash
- `src/api/adapters/observer.py` - Added _format_sig_alg_version, updated to_response mapping
- `src/api/routes/observer.py` - Added verification-spec and verify-chain endpoints
- `src/application/services/observer_service.py` - Added ChainVerificationResultDTO, verify_chain method
- `tests/unit/api/test_observer_models.py` - Added tests for new models and methods
- `tests/unit/api/test_observer_adapter.py` - Added sig_alg_version and payload preservation tests
- `tests/unit/api/test_observer_routes.py` - Added endpoint existence and spec tests

**New Files:**
- `tests/integration/test_raw_events_integration.py` - 13 FR45 compliance integration tests

