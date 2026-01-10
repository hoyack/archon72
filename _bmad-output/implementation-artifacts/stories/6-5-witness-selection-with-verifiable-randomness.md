# Story 6.5: Witness Selection with Verifiable Randomness (FR59-FR61)

Status: done

## Story

As an **external observer**,
I want witness selection to use verifiable randomness,
So that I can verify selection was fair.

## Acceptance Criteria

### AC1: External Entropy Source (FR61)
**Given** a witness is needed
**When** selection occurs
**Then** randomness source is external (FR61)
**And** selection algorithm is deterministic given the seed

### AC2: Verifiable Selection Record (FR59)
**Given** a witness selection event
**When** I examine it
**Then** it includes: `random_seed`, `seed_source`, `selected_witness_id`
**And** I can verify selection by re-running algorithm

### AC3: Witness Pair Rotation (FR60)
**Given** witness pair rotation (FR60)
**When** consecutive events need witnesses
**Then** no pair appears twice in 24 hours
**And** rotation is enforced

## Tasks / Subtasks

- [ ] Task 1: Create External Entropy Source Port (AC: #1)
  - [ ] 1.1 Create `src/application/ports/entropy_source.py`:
    - `EntropySourceProtocol` ABC with methods:
      - `async def get_entropy() -> bytes` - Returns external entropy
      - `async def get_source_identifier() -> str` - Returns source ID (e.g., "random.org", "cloudflare-drand")
    - Document FR61 requirement for external entropy
    - Document NFR22 (external entropy source requirement)
    - Document NFR57 (halt on entropy failure, not weak randomness)
  - [ ] 1.2 Export from `src/application/ports/__init__.py`

- [ ] Task 2: Create Verifiable Randomness Domain Models (AC: #1, #2)
  - [ ] 2.1 Create `src/domain/models/witness_selection.py`:
    - `WitnessSelectionRecord` frozen dataclass with:
      - `random_seed: bytes` - Combined entropy + hash chain seed
      - `seed_source: str` - Source identifier (e.g., "external:random.org+chain:abc123")
      - `selected_witness_id: str` - The selected witness ID
      - `pool_snapshot: tuple[str, ...]` - Ordered list of available witnesses at selection time
      - `algorithm_version: str` - Selection algorithm version for reproducibility
      - `selected_at: datetime` - UTC timestamp
    - `verify_selection()` method that re-runs algorithm and confirms match
    - `to_dict()` for serialization
    - `signable_content()` for witnessing (CT-12)
  - [ ] 2.2 Create `WitnessSelectionSeed` frozen dataclass:
    - `external_entropy: bytes` - From external source (FR61)
    - `chain_hash: str` - Latest hash chain value (FR59)
    - `combined_seed: bytes` - SHA-256(external_entropy || chain_hash)
    - Factory method `combine(external: bytes, chain_hash: str) -> WitnessSelectionSeed`
  - [ ] 2.3 Export from `src/domain/models/__init__.py`

- [ ] Task 3: Create Witness Pair Tracker Domain Model (AC: #3)
  - [ ] 3.1 Create `src/domain/models/witness_pair.py`:
    - `WitnessPair` frozen dataclass with:
      - `witness_a_id: str` - First witness ID
      - `witness_b_id: str` - Second witness ID (or same as A for single witness)
      - `paired_at: datetime` - When this pair was recorded
    - `canonical_key() -> str` - Returns sorted pair key for comparison
    - Pairs are symmetric: (A,B) == (B,A)
  - [ ] 3.2 Create `WitnessPairHistory` class:
    - `_recent_pairs: dict[str, datetime]` - Canonical key -> timestamp
    - `has_appeared_in_24h(pair: WitnessPair) -> bool` - FR60 check
    - `record_pair(pair: WitnessPair) -> None` - Record new pair
    - `prune_old_pairs() -> None` - Remove pairs older than 24 hours
  - [ ] 3.3 Export from `src/domain/models/__init__.py`

- [ ] Task 4: Create Witness Selection Errors (AC: #1, #2, #3)
  - [ ] 4.1 Create `src/domain/errors/witness_selection.py`:
    - `WitnessSelectionError(ConstitutionalViolationError)` - Base class
    - `EntropyUnavailableError(WitnessSelectionError)` - FR61/NFR57 violation
      - Message: "FR61: External entropy unavailable - witness selection halted"
      - CRITICAL: System must halt, not use weak randomness (NFR57)
    - `WitnessPairRotationViolationError(WitnessSelectionError)` - FR60 violation
      - Attributes: `pair_key: str`, `last_appearance: datetime`
      - Message: "FR60: Witness pair {pair_key} appeared within 24 hours"
    - `WitnessSelectionVerificationError(WitnessSelectionError)` - Verification failed
      - Attributes: `expected_witness: str`, `computed_witness: str`
      - Message: "FR59: Witness selection verification failed"
    - `InsufficientWitnessPoolError(WitnessSelectionError)` - Pool too small
      - Attributes: `available: int`, `minimum_required: int`
      - Message: "FR117: Witness pool below minimum ({available} < {minimum_required})"
  - [ ] 4.2 Export from `src/domain/errors/__init__.py`

- [ ] Task 5: Create Witness Selection Events (AC: #2)
  - [ ] 5.1 Create `src/domain/events/witness_selection.py`:
    - `WitnessSelectionEventPayload` frozen dataclass with:
      - `random_seed: str` - Base64 encoded combined seed
      - `seed_source: str` - Source identifier
      - `selected_witness_id: str` - The selected witness
      - `pool_size: int` - Number of available witnesses
      - `algorithm_version: str` - For reproducibility
      - `selected_at: datetime`
    - `to_dict()` for event writing
    - `signable_content()` for witnessing (CT-12)
    - Event type constant: `WITNESS_SELECTION_EVENT_TYPE = "witness.selection"`
  - [ ] 5.2 Create `WitnessPairRotationEventPayload` frozen dataclass:
    - `pair_key: str` - Canonical pair key
    - `last_pair_time: datetime | None` - When pair last appeared (None if first time)
    - `excluded_from_selection: bool` - True if pair was excluded due to FR60
    - `event_at: datetime`
  - [ ] 5.3 Export from `src/domain/events/__init__.py`

- [ ] Task 6: Create Verifiable Witness Selection Service (AC: #1, #2, #3)
  - [ ] 6.1 Create `src/application/services/verifiable_witness_selection_service.py`:
    - Inject: `HaltChecker`, `WitnessPoolProtocol`, `EntropySourceProtocol`, `EventStoreProtocol` (for chain hash), `EventWriterService` (optional)
    - HALT CHECK FIRST at every operation boundary (CT-11)
  - [ ] 6.2 Implement `async def select_witness() -> WitnessSelectionRecord`:
    - HALT CHECK FIRST (CT-11)
    - Get external entropy (FR61) - raise `EntropyUnavailableError` if fails
    - Get latest hash chain value (FR59)
    - Combine: `SHA-256(external_entropy || chain_hash)` for deterministic seed
    - Get pool snapshot (ordered list of active witnesses)
    - Check pool size >= WITNESS_POOL_MINIMUM (FR117, from Story 6.4)
    - Apply deterministic selection algorithm (modulo of seed % pool_size)
    - Check FR60 rotation constraint via `WitnessPairHistory`
    - If pair constraint violated, retry with next candidate (up to pool_size attempts)
    - Record selection event if EventWriter provided
    - Return `WitnessSelectionRecord` with full audit trail
  - [ ] 6.3 Implement `async def verify_selection(record: WitnessSelectionRecord) -> bool`:
    - Re-run deterministic selection algorithm with recorded seed
    - Compare computed witness with recorded witness
    - Return True if match, raise `WitnessSelectionVerificationError` if not
  - [ ] 6.4 Implement deterministic selection algorithm:
    - `_deterministic_select(seed: bytes, pool: tuple[str, ...]) -> str`
    - Convert seed to int: `int.from_bytes(seed[:8], 'big')`
    - Select: `pool[seed_int % len(pool)]`
    - Document algorithm version for reproducibility
  - [ ] 6.5 Export from `src/application/services/__init__.py`

- [ ] Task 7: Create Witness Pair History Port (AC: #3)
  - [ ] 7.1 Create `src/application/ports/witness_pair_history.py`:
    - `WitnessPairHistoryProtocol` with methods:
      - `async def has_appeared_in_24h(pair: WitnessPair) -> bool`
      - `async def record_pair(pair: WitnessPair) -> None`
      - `async def get_pair_last_appearance(pair_key: str) -> datetime | None`
  - [ ] 7.2 Export from `src/application/ports/__init__.py`

- [ ] Task 8: Create Infrastructure Stubs (AC: #1, #3)
  - [ ] 8.1 Create `src/infrastructure/stubs/entropy_source_stub.py`:
    - `EntropySourceStub` implementing `EntropySourceProtocol`
    - Returns deterministic entropy for testing (seeded from configurable value)
    - DEV MODE watermark warning on initialization
    - `set_entropy(entropy: bytes)` for test control
    - `set_failure(should_fail: bool)` to simulate entropy unavailability
  - [ ] 8.2 Create `src/infrastructure/stubs/witness_pair_history_stub.py`:
    - `InMemoryWitnessPairHistory` implementing `WitnessPairHistoryProtocol`
    - In-memory dict storage with automatic pruning
    - `clear()` for test cleanup
  - [ ] 8.3 Export from `src/infrastructure/stubs/__init__.py`

- [ ] Task 9: Extend Existing Witness Pool (AC: #2)
  - [ ] 9.1 Add to `WitnessPoolProtocol`:
    - `async def get_ordered_active_witnesses() -> tuple[str, ...]` - Returns deterministic ordered list
  - [ ] 9.2 Implement in `InMemoryWitnessPool`:
    - Sort by witness_id for deterministic ordering
    - Return tuple of witness IDs (not Witness objects)
  - [ ] 9.3 Update unit tests for new method

- [ ] Task 10: Write Unit Tests (AC: #1, #2, #3)
  - [ ] 10.1 Create `tests/unit/domain/test_witness_selection.py`:
    - Test `WitnessSelectionRecord` creation with all fields
    - Test `verify_selection()` returns True for valid record
    - Test `verify_selection()` returns False for tampered record
    - Test `to_dict()` returns expected structure
    - Test `signable_content()` determinism
    - Test record immutability (frozen dataclass)
  - [ ] 10.2 Create `tests/unit/domain/test_witness_selection_seed.py`:
    - Test `WitnessSelectionSeed.combine()` produces deterministic output
    - Test same inputs always produce same combined seed
    - Test different inputs produce different seeds
    - Test seed immutability
  - [ ] 10.3 Create `tests/unit/domain/test_witness_pair.py`:
    - Test `WitnessPair` canonical_key is symmetric: (A,B) == (B,A)
    - Test `WitnessPairHistory.has_appeared_in_24h()` returns False for new pair
    - Test `WitnessPairHistory.has_appeared_in_24h()` returns True after record
    - Test `WitnessPairHistory.prune_old_pairs()` removes old entries
    - Test pair history respects 24-hour boundary exactly
  - [ ] 10.4 Create `tests/unit/domain/test_witness_selection_errors.py`:
    - Test `EntropyUnavailableError` message includes FR61
    - Test `WitnessPairRotationViolationError` message includes FR60
    - Test `WitnessSelectionVerificationError` message includes FR59
    - Test `InsufficientWitnessPoolError` message includes FR117
    - Test error inheritance hierarchy
  - [ ] 10.5 Create `tests/unit/application/test_verifiable_witness_selection_service.py`:
    - Test `select_witness()` returns valid `WitnessSelectionRecord`
    - Test `select_witness()` uses external entropy (mock entropy source)
    - Test `select_witness()` combines entropy with hash chain
    - Test `select_witness()` raises `EntropyUnavailableError` on entropy failure
    - Test `select_witness()` raises `InsufficientWitnessPoolError` on small pool
    - Test `select_witness()` enforces FR60 rotation constraint
    - Test `select_witness()` retries on rotation violation
    - Test `verify_selection()` succeeds for valid record
    - Test `verify_selection()` raises for invalid record
    - Test deterministic algorithm produces consistent results
    - Test HALT CHECK on all operations
  - [ ] 10.6 Create `tests/unit/infrastructure/test_entropy_source_stub.py`:
    - Test stub returns configurable entropy
    - Test stub can simulate failures
    - Test stub DEV MODE warning
  - [ ] 10.7 Create `tests/unit/infrastructure/test_witness_pair_history_stub.py`:
    - Test in-memory storage works correctly
    - Test `clear()` method
    - Test automatic pruning

- [ ] Task 11: Write Integration Tests (AC: #1, #2, #3)
  - [ ] 11.1 Create `tests/integration/test_verifiable_witness_selection_integration.py`:
    - Test: `test_fr59_selection_uses_hash_chain_seed` (AC2)
    - Test: `test_fr59_selection_record_is_verifiable` (AC2)
    - Test: `test_fr61_selection_uses_external_entropy` (AC1)
    - Test: `test_fr61_entropy_failure_halts_selection` (AC1, NFR57)
    - Test: `test_fr60_pair_rotation_within_24h_blocked` (AC3)
    - Test: `test_fr60_pair_rotation_after_24h_allowed` (AC3)
    - Test: `test_selection_deterministic_given_seed` (AC1)
    - Test: `test_selection_includes_pool_snapshot` (AC2)
    - Test: `test_selection_includes_algorithm_version` (AC2)
    - Test: `test_halt_check_prevents_selection_during_halt`
    - Test: `test_selection_event_created_with_all_fields` (AC2)

## Dev Notes

### Constitutional Constraints (CRITICAL)

- **FR59**: System SHALL select witnesses using verifiable randomness seeded from previous hash chain state
- **FR60**: No witness pair SHALL appear consecutively more than once per 24-hour period
- **FR61**: System SHALL flag statistical anomalies in witness co-occurrence for Observer review (note: anomaly detection is Story 6.6)
- **NFR22**: Witness selection randomness SHALL include external entropy source
- **NFR57**: If all entropy fails, witness selection halts rather than using weak randomness
- **FR117**: If witness pool <12, continue only for low-stakes events; high-stakes events pause until restored
- **CT-11**: Silent failure destroys legitimacy -> HALT CHECK FIRST at every operation
- **CT-12**: Witnessing creates accountability -> Selection records must be verifiable

### Epic 6 Context - Story 6.5 Position

Story 6.5 implements verifiable witness selection building on the existing witness pool infrastructure from Story 1-4. Story 6.6 (next) will add anomaly detection on top of this selection mechanism.

```
┌─────────────────────────────────────────────────────────────────┐
│ Story 1-4: Witness Pool & Attestation (EXISTING)                │
│ - WitnessPoolProtocol, InMemoryWitnessPool                      │
│ - Round-robin selection (non-verifiable)                        │
│ - WitnessService for attestation                                │
└─────────────────────────────────────────────────────────────────┘
         │
         │ Enhanced by
         ▼
┌─────────────────────────────────────────────────────────────────┐
│ Story 6.5: Verifiable Witness Selection (THIS STORY)            │
│ - External entropy source (FR61, NFR22, NFR57)                  │
│ - Hash chain seeding (FR59)                                     │
│ - Deterministic, reproducible algorithm                         │
│ - Pair rotation enforcement (FR60)                              │
│ - Verifiable selection records                                  │
└─────────────────────────────────────────────────────────────────┘
         │
         │ Analyzed by
         ▼
┌─────────────────────────────────────────────────────────────────┐
│ Story 6.6: Witness Pool Anomaly Detection (NEXT)                │
│ - Statistical anomaly flagging (FR61, FR116-118)                │
│ - Co-occurrence analysis                                        │
│ - Degraded mode surfacing (FR117)                               │
└─────────────────────────────────────────────────────────────────┘
```

### Key Dependencies from Previous Stories

From existing codebase:
- `src/application/ports/witness_pool.py`: WitnessPoolProtocol (Story 1-4)
- `src/infrastructure/adapters/persistence/witness_pool.py`: InMemoryWitnessPool (Story 1-4)
- `src/application/services/witness_service.py`: WitnessService for attestation (Story 1-4)
- `src/domain/models/witness.py`: Witness domain model (Story 1-4)
- `src/application/ports/event_store.py`: EventStoreProtocol for hash chain (Story 1-1)
- `src/domain/primitives/constitutional_thresholds.py`: WITNESS_POOL_MINIMUM_THRESHOLD (Story 6.4)
- `src/application/ports/halt_checker.py`: HaltCheckerProtocol (Story 3-2)

### Verifiable Selection Algorithm Design

```python
# Deterministic selection algorithm - version 1.0.0
# MUST be versioned for reproducibility by external observers

SELECTION_ALGORITHM_VERSION = "1.0.0"

def deterministic_select(seed: bytes, pool: tuple[str, ...]) -> str:
    """Select witness deterministically from pool given seed.

    Algorithm (v1.0.0):
    1. Take first 8 bytes of seed
    2. Convert to unsigned big-endian integer
    3. Compute index = seed_int % len(pool)
    4. Return pool[index]

    This is verifiable: anyone with seed + pool can recompute selection.
    """
    if not pool:
        raise InsufficientWitnessPoolError(available=0, minimum_required=1)

    seed_int = int.from_bytes(seed[:8], 'big')
    index = seed_int % len(pool)
    return pool[index]
```

### Entropy Combination Design

```python
@dataclass(frozen=True)
class WitnessSelectionSeed:
    """Combined seed for verifiable witness selection (FR59, FR61).

    Constitutional Constraint (FR59):
    System SHALL select witnesses using verifiable randomness seeded
    from previous hash chain state.

    Constitutional Constraint (FR61):
    External entropy source required (NFR22).
    """
    external_entropy: bytes  # From external source (FR61)
    chain_hash: str  # Latest hash chain value (FR59)
    combined_seed: bytes  # SHA-256(external || chain_hash)

    @classmethod
    def combine(cls, external: bytes, chain_hash: str) -> "WitnessSelectionSeed":
        """Combine external entropy with hash chain for verifiable seed.

        Combination method:
        1. Concatenate: external_entropy || chain_hash.encode('utf-8')
        2. SHA-256 hash the concatenation
        3. Result is the combined seed
        """
        import hashlib

        data = external + chain_hash.encode('utf-8')
        combined = hashlib.sha256(data).digest()

        return cls(
            external_entropy=external,
            chain_hash=chain_hash,
            combined_seed=combined,
        )
```

### Pair Rotation Enforcement (FR60)

```python
@dataclass(frozen=True)
class WitnessPair:
    """Witness pair for rotation tracking (FR60).

    Constitutional Constraint (FR60):
    No witness pair SHALL appear consecutively more than once per 24-hour period.
    """
    witness_a_id: str
    witness_b_id: str
    paired_at: datetime

    def canonical_key(self) -> str:
        """Get canonical key for pair comparison.

        Pairs are symmetric: (A,B) == (B,A).
        Canonical form: sorted tuple as string.
        """
        ids = sorted([self.witness_a_id, self.witness_b_id])
        return f"{ids[0]}:{ids[1]}"


class WitnessPairHistory:
    """Track witness pairs for FR60 rotation enforcement."""

    ROTATION_WINDOW_HOURS: int = 24

    def __init__(self) -> None:
        self._recent_pairs: dict[str, datetime] = {}

    def has_appeared_in_24h(self, pair: WitnessPair) -> bool:
        """Check if pair has appeared in last 24 hours (FR60)."""
        key = pair.canonical_key()
        if key not in self._recent_pairs:
            return False

        last_time = self._recent_pairs[key]
        now = datetime.now(timezone.utc)
        window = timedelta(hours=self.ROTATION_WINDOW_HOURS)

        return (now - last_time) < window
```

### External Entropy Source Design

```python
class EntropySourceProtocol(ABC):
    """Protocol for external entropy source (FR61, NFR22, NFR57).

    Constitutional Constraints:
    - FR61: System SHALL use external entropy source
    - NFR22: Witness selection randomness SHALL include external entropy
    - NFR57: If all entropy fails, witness selection halts (not weak randomness)

    Production implementations may include:
    - CloudflareEntropySource: drand.cloudflare.com
    - RandomOrgEntropySource: api.random.org
    - HardwareEntropySource: Hardware RNG device
    """

    @abstractmethod
    async def get_entropy(self) -> bytes:
        """Get external entropy bytes.

        Returns:
            At least 32 bytes of external entropy.

        Raises:
            EntropyUnavailableError: If entropy cannot be obtained.
                CRITICAL: Caller MUST halt, not use weak randomness (NFR57).
        """
        ...

    @abstractmethod
    async def get_source_identifier(self) -> str:
        """Get identifier for entropy source.

        Returns:
            Human-readable source identifier for audit trail.
            E.g., "drand.cloudflare.com", "random.org/v2"
        """
        ...
```

### Import Rules (Hexagonal Architecture)

- `domain/models/witness_selection.py` imports from `domain/`, `typing`, `dataclasses`, `hashlib`
- `domain/models/witness_pair.py` imports from `domain/`, `typing`, `dataclasses`, `datetime`
- `domain/errors/witness_selection.py` inherits from `ConstitutionalViolationError`
- `application/ports/entropy_source.py` imports from `abc`, `typing`
- `application/services/verifiable_witness_selection_service.py` imports from `application/ports/`, `domain/`
- NEVER import from `infrastructure/` in `domain/` or `application/`

### Testing Standards

- ALL tests use `pytest.mark.asyncio`
- Use `AsyncMock` for async dependencies
- Unit tests mock the protocol interfaces
- Integration tests use stub implementations
- FR59 tests MUST verify:
  - Selection uses hash chain state
  - Selection record can be verified by re-running algorithm
- FR60 tests MUST verify:
  - Same pair cannot appear twice in 24 hours
  - Pair can appear after 24 hours
  - Pair rotation is symmetric (A,B == B,A)
- FR61 tests MUST verify:
  - External entropy is used in seed
  - Entropy failure causes halt, not weak randomness (NFR57)
- NFR22 tests MUST verify:
  - External entropy source is always used

### Files to Create

```
src/domain/models/witness_selection.py                    # Selection record model
src/domain/models/witness_pair.py                         # Pair tracking model
src/domain/errors/witness_selection.py                    # Selection errors
src/domain/events/witness_selection.py                    # Selection events
src/application/ports/entropy_source.py                   # Entropy port
src/application/ports/witness_pair_history.py             # Pair history port
src/application/services/verifiable_witness_selection_service.py  # Main service
src/infrastructure/stubs/entropy_source_stub.py           # Entropy stub
src/infrastructure/stubs/witness_pair_history_stub.py     # Pair history stub
tests/unit/domain/test_witness_selection.py               # Selection model tests
tests/unit/domain/test_witness_selection_seed.py          # Seed tests
tests/unit/domain/test_witness_pair.py                    # Pair tests
tests/unit/domain/test_witness_selection_errors.py        # Error tests
tests/unit/application/test_verifiable_witness_selection_service.py  # Service tests
tests/unit/infrastructure/test_entropy_source_stub.py     # Stub tests
tests/unit/infrastructure/test_witness_pair_history_stub.py  # Stub tests
tests/integration/test_verifiable_witness_selection_integration.py  # Integration tests
```

### Files to Modify

```
src/application/ports/witness_pool.py                     # Add get_ordered_active_witnesses()
src/infrastructure/adapters/persistence/witness_pool.py   # Implement new method
src/domain/models/__init__.py                             # Export new models
src/domain/errors/__init__.py                             # Export new errors
src/domain/events/__init__.py                             # Export new events
src/application/ports/__init__.py                         # Export new ports
src/application/services/__init__.py                      # Export new service
src/infrastructure/stubs/__init__.py                      # Export new stubs
tests/unit/infrastructure/test_witness_pool.py            # Add tests for new method
```

### Project Structure Notes

- Selection service follows existing service patterns from Stories 6.1-6.4
- Entropy source port follows ADR-4 pattern (prod adapter vs dev stub)
- Pair history follows in-memory stub pattern from existing stubs
- Selection algorithm version MUST be recorded for reproducibility
- External observers MUST be able to verify selection with recorded data

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story-6.5] - Story definition
- [Source: _bmad-output/planning-artifacts/prd.md#FR59] - Verifiable randomness from hash chain
- [Source: _bmad-output/planning-artifacts/prd.md#FR60] - Witness pair rotation
- [Source: _bmad-output/planning-artifacts/prd.md#FR61] - External entropy source
- [Source: _bmad-output/planning-artifacts/prd.md#NFR22] - External entropy requirement
- [Source: _bmad-output/planning-artifacts/prd.md#NFR57] - Halt on entropy failure
- [Source: _bmad-output/planning-artifacts/prd.md#FR117] - Witness pool minimum
- [Source: _bmad-output/planning-artifacts/prd.md#FR124-125] - Randomness gaming defense
- [Source: src/application/ports/witness_pool.py] - Existing witness pool protocol
- [Source: src/infrastructure/adapters/persistence/witness_pool.py] - Existing pool implementation
- [Source: src/application/services/witness_service.py] - Existing witness service
- [Source: src/domain/primitives/constitutional_thresholds.py] - WITNESS_POOL_MINIMUM_THRESHOLD
- [Source: _bmad-output/project-context.md] - Project implementation rules
- [Source: _bmad-output/implementation-artifacts/stories/6-4-constitutional-threshold-definitions.md] - Previous story context

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### Change Log

| Date | Change | Author |
|------|--------|--------|
| 2026-01-08 | Story created with comprehensive FR59/FR60/FR61 context, verifiable selection algorithm, pair rotation design | Create-Story Workflow (Opus 4.5) |

### File List

