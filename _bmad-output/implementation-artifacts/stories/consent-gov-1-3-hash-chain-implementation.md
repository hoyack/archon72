# Story consent-gov-1.3: Hash Chain Implementation

Status: done

---

## Story

As a **verifier**,
I want **each event cryptographically linked to the previous**,
so that **I can detect any tampering or gaps in the ledger, ensuring constitutional integrity**.

---

## Acceptance Criteria

1. **AC1:** BLAKE3 implemented as preferred hash algorithm for high-throughput operations
2. **AC2:** SHA-256 implemented as required baseline for portability
3. **AC3:** Algorithm-prefixed hash format used (e.g., `blake3:abc123...`, `sha256:789xyz...`)
4. **AC4:** `EventMetadata` extended with `prev_hash` and `hash` fields
5. **AC5:** Genesis event uses well-known null hash (`blake3:genesis` or configurable)
6. **AC6:** Hash computed from `canonical_json(metadata_without_hash) + canonical_json(payload)`
7. **AC7:** Hash chain validated on read (verification returns True/False)
8. **AC8:** Hash break detection emits `ledger.integrity.hash_break_detected` event
9. **AC9:** Unit tests for hash chain creation and verification (100% coverage)
10. **AC10:** Both algorithms supported for verification (reader extracts prefix, selects algorithm)

---

## Tasks / Subtasks

- [x] **Task 1: Create hash chain module structure** (AC: All)
  - [x] Create `src/domain/governance/events/hash_chain.py`
  - [x] Create `src/domain/governance/events/canonical_json.py`
  - [x] Create `src/domain/governance/events/hash_algorithms.py`

- [x] **Task 2: Implement hash algorithm abstraction** (AC: 1, 2, 3, 10)
  - [x] Define `HashAlgorithm` Protocol with `hash()` method
  - [x] Implement `Blake3Hasher` class
  - [x] Implement `Sha256Hasher` class
  - [x] Implement algorithm selection from prefix (`blake3:` or `sha256:`)
  - [x] Add `SUPPORTED_ALGORITHMS` registry

- [x] **Task 3: Implement canonical JSON serialization** (AC: 6)
  - [x] Create `canonical_json()` function with deterministic output
  - [x] Ensure sorted keys, no whitespace variation
  - [x] Handle datetime serialization (ISO-8601 UTC)
  - [x] Handle UUID serialization (string format)

- [x] **Task 4: Extend EventMetadata with hash fields** (AC: 4, 5)
  - [x] Add `prev_hash: str` field to `EventMetadata` (from story 1-1)
  - [x] Add `hash: str` field to `EventMetadata`
  - [x] Define `GENESIS_PREV_HASH = "blake3:0000..."`
  - [x] Add validation for hash format (algorithm prefix)

- [x] **Task 5: Implement hash chain computation** (AC: 1, 2, 6)
  - [x] Create `compute_event_hash()` function
  - [x] Implement metadata serialization (excluding `hash` field)
  - [x] Implement payload serialization
  - [x] Combine and hash with selected algorithm
  - [x] Return algorithm-prefixed hash string

- [x] **Task 6: Implement hash chain verification** (AC: 7, 10)
  - [x] Create `verify_event_hash()` function
  - [x] Extract algorithm from hash prefix
  - [x] Recompute hash and compare
  - [x] Create `verify_chain_link()` for prev_hash continuity
  - [x] Return verification result with details

- [x] **Task 7: Implement hash break detection** (AC: 8)
  - [x] Create `HashBreakDetector` class
  - [x] Define `ledger.integrity.hash_break_detected` event type
  - [x] Implement detection logic (hash mismatch, gap detection)
  - [x] Emit constitutional violation event on break

- [x] **Task 8: Create factory method for hash chain events** (AC: 4, 5, 6)
  - [x] Add `GovernanceEvent.create_with_hash()` factory method
  - [x] Accept `prev_event: GovernanceEvent | None` parameter
  - [x] Compute hash automatically
  - [x] Handle genesis case (None prev_event)

- [x] **Task 9: Write comprehensive unit tests** (AC: 9)
  - [x] Test BLAKE3 hashing correctness
  - [x] Test SHA-256 hashing correctness
  - [x] Test canonical JSON determinism
  - [x] Test hash chain computation
  - [x] Test hash verification (valid and invalid)
  - [x] Test genesis event handling
  - [x] Test hash break detection
  - [x] Test algorithm selection from prefix

---

## Documentation Checklist

- [x] Architecture docs updated (hash chain implementation details) - Module docstrings document architecture compliance
- [x] Inline comments added for cryptographic operations - All functions and classes documented
- [x] N/A - API docs (internal infrastructure)
- [x] N/A - README (internal component)

---

## Dev Notes

### Architecture Compliance (CRITICAL)

**From governance-architecture.md:**

This story implements the hash chain cryptographic linking defined in the architecture document.

**Hash Chain Implementation (Locked):**

| Algorithm | Status | Use |
|-----------|--------|-----|
| BLAKE3 | Preferred | High-throughput ledger operations |
| SHA-256 | Required baseline | Portability, existing patterns (commit-reveal) |

**Hash Format (Locked):**
```
blake3:abc123def456...
sha256:789xyz012abc...
```

**Verification Rules:**
- Reader extracts prefix, selects algorithm
- Both algorithms MUST be supported for verification
- Writer may choose algorithm (BLAKE3 recommended)

**Hash Computation (Locked):**
```python
def compute_event_hash(event: GovernanceEvent, algorithm: str = "blake3") -> str:
    """Compute hash from metadata (excluding hash) + payload."""
    metadata_dict = asdict(event.metadata)
    del metadata_dict["hash"]  # Exclude hash from computation

    content = canonical_json(metadata_dict) + canonical_json(event.payload)

    if algorithm == "blake3":
        hash_bytes = blake3(content.encode()).digest()
    else:
        hash_bytes = hashlib.sha256(content.encode()).digest()

    return f"{algorithm}:{hash_bytes.hex()}"
```

**Event Envelope Pattern (Extended from Story 1-1):**
```json
{
  "metadata": {
    "event_id": "uuid",
    "event_type": "executive.task.accepted",
    "schema_version": "1.0.0",
    "timestamp": "2026-01-16T00:00:00Z",
    "actor_id": "archon-or-officer-id",
    "trace_id": "uuid",
    "prev_hash": "blake3:abc123...",
    "hash": "blake3:def456..."
  },
  "payload": {
    // Domain-specific event data
  }
}
```

### Existing Patterns to Follow

**Reference:** `src/domain/events/event.py`

The existing `Event` class has hash-related patterns:
- `create_with_hash()` factory method
- Hash field validation
- Immutability via frozen dataclass

**Key Pattern:** Hash computation MUST exclude the `hash` field itself (chicken-egg problem).

### Dependency on Story 1-1 and 1-2

This story depends on:
- `consent-gov-1-1-event-envelope-domain-model`: `GovernanceEvent`, `EventMetadata`
- `consent-gov-1-2-append-only-ledger-port-adapter`: `GovernanceLedgerPort.get_latest_event()`

**Import:**
```python
from src.domain.governance.events.event_envelope import GovernanceEvent, EventMetadata
from src.application.ports.governance.ledger_port import GovernanceLedgerPort
```

### Source Tree Components

**New Files:**
```
src/domain/governance/events/
├── hash_chain.py           # Hash chain computation and verification
├── canonical_json.py       # Deterministic JSON serialization
└── hash_algorithms.py      # Algorithm implementations (BLAKE3, SHA-256)
```

**Modified Files:**
```
src/domain/governance/events/event_envelope.py  # Add prev_hash, hash fields to EventMetadata
```

**Test Files:**
```
tests/unit/domain/governance/events/
├── test_hash_chain.py
├── test_canonical_json.py
└── test_hash_algorithms.py
```

### Technical Requirements

**Canonical JSON (CRITICAL):**
```python
import json
from datetime import datetime
from uuid import UUID

def canonical_json(obj: dict) -> str:
    """Produce deterministic JSON for hashing.

    Rules:
    - Keys sorted alphabetically
    - No extra whitespace
    - Datetime as ISO-8601 UTC string
    - UUID as lowercase string without dashes? (or with?)
    - Floats with consistent precision
    """
    def default_serializer(o):
        if isinstance(o, datetime):
            return o.isoformat()
        if isinstance(o, UUID):
            return str(o)
        raise TypeError(f"Object of type {type(o)} is not JSON serializable")

    return json.dumps(obj, sort_keys=True, separators=(',', ':'), default=default_serializer)
```

**Hash Algorithm Protocol:**
```python
from typing import Protocol

class HashAlgorithm(Protocol):
    """Protocol for hash algorithm implementations."""

    @property
    def name(self) -> str:
        """Algorithm name for prefix (e.g., 'blake3', 'sha256')."""
        ...

    def hash(self, data: bytes) -> bytes:
        """Compute hash of data."""
        ...

class Blake3Hasher:
    """BLAKE3 hash implementation (preferred)."""

    @property
    def name(self) -> str:
        return "blake3"

    def hash(self, data: bytes) -> bytes:
        import blake3
        return blake3.blake3(data).digest()

class Sha256Hasher:
    """SHA-256 hash implementation (baseline)."""

    @property
    def name(self) -> str:
        return "sha256"

    def hash(self, data: bytes) -> bytes:
        import hashlib
        return hashlib.sha256(data).digest()
```

**Genesis Hash Constant:**
```python
# Well-known null hash for genesis event
GENESIS_PREV_HASH = "blake3:0000000000000000000000000000000000000000000000000000000000000000"
```

**Hash Break Detection Event:**
```python
HASH_BREAK_EVENT_TYPE = "ledger.integrity.hash_break_detected"

@dataclass(frozen=True)
class HashBreakEvent:
    """Event emitted when hash chain integrity is violated."""
    event_id: UUID
    event_type: str = HASH_BREAK_EVENT_TYPE
    broken_at_sequence: int
    expected_prev_hash: str
    actual_prev_hash: str
    detected_at: datetime
    detector_id: str  # Which service detected the break
```

**Python Patterns (CRITICAL):**
- Use `blake3` library (pip install blake3)
- Use `hashlib` for SHA-256 (stdlib)
- ALL hash operations are synchronous (CPU-bound, no I/O)
- Type hints on ALL functions (mypy --strict must pass)
- Import from `src.domain.errors.constitutional import ConstitutionalViolationError`

### Testing Standards

**Test File Location:** `tests/unit/domain/governance/events/test_hash_chain.py`

**Test Patterns:**
```python
import pytest
from uuid import uuid4
from datetime import datetime, timezone

class TestHashChain:
    def test_blake3_hash_computation(self):
        """BLAKE3 produces correct algorithm-prefixed hash."""

    def test_sha256_hash_computation(self):
        """SHA-256 produces correct algorithm-prefixed hash."""

    def test_canonical_json_determinism(self):
        """Same dict produces identical JSON regardless of insertion order."""
        d1 = {"b": 1, "a": 2}
        d2 = {"a": 2, "b": 1}
        assert canonical_json(d1) == canonical_json(d2)

    def test_hash_verification_valid(self):
        """Valid event hash verifies successfully."""

    def test_hash_verification_invalid(self):
        """Tampered event fails hash verification."""

    def test_genesis_event_has_null_prev_hash(self):
        """First event in chain uses well-known genesis hash."""

    def test_chain_link_verification(self):
        """Event prev_hash matches previous event hash."""

    def test_hash_break_detection(self):
        """Hash break emits ledger.integrity.hash_break_detected."""

    def test_algorithm_selection_from_prefix(self):
        """Verification selects correct algorithm from hash prefix."""
```

**Coverage Requirement:** 100% for hash chain module

### Library/Framework Requirements

| Library | Version | Purpose |
|---------|---------|---------|
| Python | 3.11+ | Async/await, type hints |
| blake3 | latest | BLAKE3 hashing |
| hashlib | stdlib | SHA-256 hashing |
| pytest | latest | Unit testing |

**Installation:**
```bash
pip install blake3
```

### Project Structure Notes

**Alignment:** Creates new hash chain module in `src/domain/governance/events/` per architecture (Step 6).

**Import Rules (Hexagonal):**
- Domain layer imports NOTHING from other layers
- Hash chain module imports `GovernanceEvent` from same domain
- No infrastructure imports allowed

### References

- [Source: _bmad-output/planning-artifacts/governance-architecture.md#Hash Chain Implementation (Locked)]
- [Source: _bmad-output/planning-artifacts/governance-architecture.md#Event Envelope Pattern (Locked)]
- [Source: _bmad-output/planning-artifacts/governance-architecture.md#Constitutional Enforcement]
- [Source: _bmad-output/planning-artifacts/government-epics.md#GOV-1-3]
- [Source: src/domain/events/event.py] - Reference hash pattern
- [Source: _bmad-output/project-context.md#Critical Implementation Rules]
- [Source: consent-gov-1-1-event-envelope-domain-model.md] - Dependency
- [Source: consent-gov-1-2-append-only-ledger-port-adapter.md] - Dependency

### FR/NFR Traceability

| Requirement | Description | Implementation |
|-------------|-------------|----------------|
| AD-6 | BLAKE3/SHA-256 hash algorithms | Dual algorithm support |
| NFR-CONST-02 | Event integrity verification | Hash chain validation |
| NFR-AUDIT-06 | Deterministic replay | Canonical JSON ensures reproducibility |
| FR1 | Events must be hash-chained | prev_hash + hash fields |
| FR2 | Tampering detection | Hash verification on read |

### Story Dependencies

| Story | Dependency Type | What We Need |
|-------|-----------------|--------------|
| consent-gov-1-1 | Hard dependency | `GovernanceEvent`, `EventMetadata` types |
| consent-gov-1-2 | Soft dependency | `GovernanceLedgerPort.get_latest_event()` for prev_hash |

### Migration Notes

**EventMetadata Schema Change:**

Story 1-1 creates `EventMetadata` WITHOUT hash fields. This story adds:
- `prev_hash: str`
- `hash: str`

**Approach:** Modify story 1-1's `EventMetadata` dataclass OR create extended version.

**Recommended:** Story 1-1 should create `EventMetadata` with Optional hash fields, this story makes them required for persisted events.

```python
# In event_envelope.py (story 1-1, modified by story 1-3)
@dataclass(frozen=True)
class EventMetadata:
    event_id: UUID
    event_type: str
    schema_version: str
    timestamp: datetime
    actor_id: str
    trace_id: str
    prev_hash: str = ""  # Set by hash chain (empty until persisted)
    hash: str = ""       # Set by hash chain (empty until persisted)
```

**Alternative:** Create `HashedGovernanceEvent` wrapper that adds hash fields.

---

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

None - clean implementation with all 152 tests passing.

### Completion Notes List

- Created comprehensive hash algorithm module (`hash_algorithms.py`) with:
  - `HashAlgorithm` Protocol for type-safe abstraction
  - `Blake3Hasher` class (preferred, high-throughput)
  - `Sha256Hasher` class (required baseline)
  - `SUPPORTED_ALGORITHMS` registry (`frozenset({"blake3", "sha256"})`)
  - `GENESIS_PREV_HASH` constant (64 zeros)
  - Utility functions: `compute_hash()`, `verify_hash()`, `validate_hash_format()`, `extract_algorithm_from_hash()`, `is_genesis_hash()`, `make_genesis_hash()`
  - Added `blake3>=0.4.0` dependency to pyproject.toml

- Created canonical JSON serialization module (`canonical_json.py`) with:
  - `canonical_json()` function for deterministic JSON output
  - Sorted keys, minimal whitespace separators
  - Custom serializers for `datetime` (ISO-8601 UTC), `UUID` (lowercase string), `bytes` (base64)
  - Unicode NFKC normalization for consistent encoding
  - Explicit rejection of NaN/Infinity floats (non-deterministic)
  - `canonical_json_bytes()` convenience function for direct hashing

- Extended `EventMetadata` with hash fields:
  - Added `prev_hash: str = ""` field (empty until hashed)
  - Added `hash: str = ""` field (empty until hashed)
  - Added convenience accessors on `GovernanceEvent`: `prev_hash`, `hash`, `has_hash()`
  - Added `create_with_hash()` factory method for automatic hash computation

- Created hash chain module (`hash_chain.py`) with:
  - `compute_event_hash()` - computes hash from metadata (excluding hash) + payload
  - `compute_event_hash_with_prev()` - computes with specific prev_hash
  - `verify_event_hash()` - validates event's hash matches content
  - `verify_chain_link()` - validates prev_hash links to previous event
  - `verify_event_full()` - full verification (hash + chain link)
  - `add_hash_to_event()` - creates new event with hash fields populated
  - `chain_events()` - chains multiple events in sequence
  - `HashVerificationResult` frozen dataclass for verification results

- Created hash break detection module (`hash_break_detection.py`) with:
  - `HashBreakType` enum: HASH_MISMATCH, CHAIN_BREAK, SEQUENCE_GAP
  - `HashBreakInfo` frozen dataclass for break details
  - `HashBreakDetectionResult` frozen dataclass for check results
  - `HashBreakDetector` class with `check_event()`, `check_sequence()`, `create_break_event_payload()`
  - `HASH_BREAK_EVENT_TYPE = "ledger.integrity.hash_break_detected"` constant

- Updated `event_types.py` with ledger integrity event types:
  - `LEDGER_INTEGRITY_HASH_BREAK_DETECTED`
  - `LEDGER_INTEGRITY_GAP_DETECTED`
  - `LEDGER_INTEGRITY_VERIFICATION_PASSED`

- Updated `__init__.py` to export all new modules and classes

- **152 unit tests passing** across 4 test files:
  - `test_hash_algorithms.py` (39 tests)
  - `test_canonical_json.py` (27 tests)
  - `test_hash_chain.py` (57 tests)
  - `test_hash_break_detection.py` (20 tests)
  - Plus 9 existing tests from event_envelope, event_types, schema_versions

### File List

**Created:**
- `src/domain/governance/events/hash_algorithms.py`
- `src/domain/governance/events/canonical_json.py`
- `src/domain/governance/events/hash_chain.py`
- `src/domain/governance/events/hash_break_detection.py`
- `tests/unit/domain/governance/events/test_hash_algorithms.py`
- `tests/unit/domain/governance/events/test_canonical_json.py`
- `tests/unit/domain/governance/events/test_hash_chain.py`
- `tests/unit/domain/governance/events/test_hash_break_detection.py`

**Modified:**
- `pyproject.toml` (added blake3 dependency)
- `src/domain/governance/events/event_envelope.py` (added prev_hash, hash fields, create_with_hash method)
- `src/domain/governance/events/event_types.py` (added ledger integrity event types)
- `src/domain/governance/events/__init__.py` (exported new modules)

