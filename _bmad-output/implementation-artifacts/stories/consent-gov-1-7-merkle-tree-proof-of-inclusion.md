# Story consent-gov-1.7: Merkle Tree Proof-of-Inclusion

Status: done

---

## Story

As a **verifier**,
I want **Merkle tree proofs for event inclusion**,
So that **I can verify specific events are in the ledger without downloading the entire history, enabling light verification and independent audit**.

---

## Acceptance Criteria

1. **AC1:** Merkle tree structure implemented with configurable batch/epoch size
2. **AC2:** Merkle root calculated per batch/epoch of events
3. **AC3:** Proof-of-inclusion can be generated for any event in the ledger
4. **AC4:** Merkle proof format includes: `event_id`, `event_hash`, `merkle_path`, `merkle_root`, `epoch`
5. **AC5:** Proof can be verified independently without accessing the full ledger
6. **AC6:** Merkle root published to ledger as `ledger.merkle.root_published` event at epoch boundaries
7. **AC7:** Both BLAKE3 and SHA-256 supported for Merkle tree hashing (consistent with hash chain)
8. **AC8:** `MerkleTreePort` interface for proof generation and verification
9. **AC9:** PostgreSQL adapter stores epoch roots and enables proof queries
10. **AC10:** Unit tests for proof generation, verification, and edge cases (single event, power-of-two, non-power-of-two)

---

## Tasks / Subtasks

- [ ] **Task 1: Create Merkle tree domain module** (AC: 1, 7)
  - [ ] Create `src/domain/governance/events/merkle_tree.py`
  - [ ] Implement `MerkleTree` class with configurable hash algorithm
  - [ ] Implement leaf node creation from event hashes
  - [ ] Implement internal node computation (hash of children)
  - [ ] Support both BLAKE3 and SHA-256 algorithms

- [ ] **Task 2: Implement Merkle proof generation** (AC: 3, 4)
  - [ ] Create `MerkleProof` dataclass with required fields
  - [ ] Implement `generate_proof()` method for specific event
  - [ ] Generate merkle_path (sibling hashes from leaf to root)
  - [ ] Include epoch identifier in proof

- [ ] **Task 3: Implement Merkle proof verification** (AC: 5)
  - [ ] Create `verify_proof()` function (standalone, no ledger access)
  - [ ] Reconstruct root from event_hash + merkle_path
  - [ ] Compare reconstructed root with provided merkle_root
  - [ ] Return verification result with details

- [ ] **Task 4: Create MerkleTreePort interface** (AC: 8)
  - [ ] Create `src/application/ports/governance/merkle_tree_port.py`
  - [ ] Define `build_tree_for_epoch()` method
  - [ ] Define `generate_proof()` method
  - [ ] Define `get_epoch_root()` method
  - [ ] Define `verify_proof()` method

- [ ] **Task 5: Implement epoch management** (AC: 2, 6)
  - [ ] Define epoch boundaries (configurable, e.g., every 1000 events or time-based)
  - [ ] Create `EpochManager` class for epoch tracking
  - [ ] Implement `ledger.merkle.root_published` event type
  - [ ] Publish root to ledger at epoch boundaries

- [ ] **Task 6: Create database schema for Merkle roots** (AC: 9)
  - [ ] Create Alembic migration for `ledger.merkle_epochs` table
  - [ ] Store: `epoch_id`, `root_hash`, `start_sequence`, `end_sequence`, `event_count`, `created_at`
  - [ ] Create index for epoch lookups

- [ ] **Task 7: Implement PostgresMerkleTreeAdapter** (AC: 9)
  - [ ] Create `src/infrastructure/adapters/governance/merkle_tree_adapter.py`
  - [ ] Implement epoch root persistence
  - [ ] Implement proof generation from stored data
  - [ ] Use async SQLAlchemy 2.0 patterns

- [ ] **Task 8: Write comprehensive unit tests** (AC: 10)
  - [ ] Test Merkle tree construction (1, 2, 4, 8 leaves)
  - [ ] Test non-power-of-two leaf counts (3, 5, 7 leaves)
  - [ ] Test proof generation for all leaf positions
  - [ ] Test proof verification (valid proofs)
  - [ ] Test proof verification (tampered proofs)
  - [ ] Test both BLAKE3 and SHA-256 algorithms
  - [ ] Test epoch boundary handling

- [ ] **Task 9: Create integration tests** (AC: 6)
  - [ ] Test end-to-end proof generation from ledger
  - [ ] Test epoch root publication
  - [ ] Test proof verification with published roots

---

## Documentation Checklist

- [ ] Architecture docs updated (Merkle tree implementation details)
- [ ] Inline comments explaining Merkle tree algorithm
- [ ] N/A - API docs (internal infrastructure, API added in GOV-9)
- [ ] N/A - README (internal component)

---

## Dev Notes

### Architecture Compliance (CRITICAL)

**From governance-architecture.md:**

This story implements AD-7: Merkle Tree Proof-of-Inclusion.

**Proof-of-Inclusion (Locked):**

**Mechanism:** Merkle tree with root per batch/epoch

**Structure:**
```
                    [Merkle Root]
                    /           \
             [Branch A]      [Branch B]
              /     \          /     \
         [Leaf1]  [Leaf2]  [Leaf3]  [Leaf4]
```

**Proof Format (Locked):**
```json
{
  "event_id": "uuid",
  "event_hash": "blake3:...",
  "merkle_path": ["hash1", "hash2", "hash3"],
  "merkle_root": "blake3:...",
  "epoch": 42
}
```

**NFR Satisfied:** NFR-CONST-02 (proof-of-inclusion for any entry)

**API Endpoint (Future Story):**
- `/governance/ledger/proof/{event_id}` — Merkle proof retrieval

### Merkle Tree Implementation

**Leaf Node:**
```python
def leaf_hash(event_hash: str, algorithm: str = "blake3") -> str:
    """Compute leaf node hash from event hash.

    Prefix with 0x00 to distinguish from internal nodes.
    """
    hasher = get_hasher(algorithm)
    return f"{algorithm}:{hasher.hash(b'\x00' + event_hash.encode()).hex()}"
```

**Internal Node:**
```python
def internal_hash(left: str, right: str, algorithm: str = "blake3") -> str:
    """Compute internal node hash from children.

    Prefix with 0x01 to distinguish from leaf nodes.
    Sort children to ensure consistent ordering.
    """
    hasher = get_hasher(algorithm)
    sorted_children = sorted([left, right])
    content = b'\x01' + sorted_children[0].encode() + sorted_children[1].encode()
    return f"{algorithm}:{hasher.hash(content).hex()}"
```

**Why Prefix Bytes:**
- Prevents second-preimage attacks
- 0x00 = leaf node, 0x01 = internal node
- Standard Merkle tree security practice

### MerkleTree Class

```python
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

@dataclass(frozen=True)
class MerkleProof:
    """Proof that an event is included in a Merkle tree."""
    event_id: UUID
    event_hash: str
    merkle_path: list[str]  # Sibling hashes from leaf to root
    merkle_root: str
    epoch: int
    leaf_index: int  # Position in tree (for verification)
    algorithm: str = "blake3"

class MerkleTree:
    """Merkle tree for event inclusion proofs.

    Constitutional Guarantee:
    - Proofs are verifiable without full ledger access
    - Tampered events produce different root
    - External observers can verify independently
    """

    def __init__(self, event_hashes: list[str], algorithm: str = "blake3") -> None:
        self._algorithm = algorithm
        self._leaves = [leaf_hash(h, algorithm) for h in event_hashes]
        self._tree = self._build_tree()

    def _build_tree(self) -> list[list[str]]:
        """Build complete Merkle tree from leaves."""
        if not self._leaves:
            return [[]]

        # Pad to power of two if needed
        leaves = self._pad_to_power_of_two(self._leaves)

        tree = [leaves]
        current_level = leaves

        while len(current_level) > 1:
            next_level = []
            for i in range(0, len(current_level), 2):
                left = current_level[i]
                right = current_level[i + 1]
                parent = internal_hash(left, right, self._algorithm)
                next_level.append(parent)
            tree.append(next_level)
            current_level = next_level

        return tree

    def _pad_to_power_of_two(self, leaves: list[str]) -> list[str]:
        """Pad leaves to next power of two by duplicating last leaf."""
        n = len(leaves)
        if n == 0:
            return []
        target = 1
        while target < n:
            target *= 2
        return leaves + [leaves[-1]] * (target - n)

    @property
    def root(self) -> str:
        """Get Merkle root hash."""
        if not self._tree or not self._tree[-1]:
            return f"{self._algorithm}:empty"
        return self._tree[-1][0]

    def generate_proof(self, leaf_index: int, event_id: UUID, event_hash: str) -> MerkleProof:
        """Generate inclusion proof for event at given index."""
        path = []
        index = leaf_index

        for level in self._tree[:-1]:  # All levels except root
            sibling_index = index ^ 1  # XOR to get sibling
            if sibling_index < len(level):
                path.append(level[sibling_index])
            index //= 2

        return MerkleProof(
            event_id=event_id,
            event_hash=event_hash,
            merkle_path=path,
            merkle_root=self.root,
            epoch=0,  # Set by caller
            leaf_index=leaf_index,
            algorithm=self._algorithm,
        )
```

### Proof Verification (Standalone)

```python
def verify_merkle_proof(proof: MerkleProof) -> bool:
    """Verify Merkle proof without accessing ledger.

    This function can be used by external verifiers.
    No database access required.
    """
    current = leaf_hash(proof.event_hash, proof.algorithm)
    index = proof.leaf_index

    for sibling in proof.merkle_path:
        if index % 2 == 0:
            # Current is left child
            current = internal_hash(current, sibling, proof.algorithm)
        else:
            # Current is right child
            current = internal_hash(sibling, current, proof.algorithm)
        index //= 2

    return current == proof.merkle_root
```

### Epoch Management

**Epoch Configuration:**
```python
@dataclass
class EpochConfig:
    """Configuration for Merkle tree epochs."""
    events_per_epoch: int = 1000  # Build tree every N events
    time_based: bool = False  # Alternative: time-based epochs
    epoch_duration_seconds: int = 3600  # If time-based
```

**Epoch Root Event:**
```python
# Event type: ledger.merkle.root_published
{
    "metadata": {
        "event_id": "uuid",
        "event_type": "ledger.merkle.root_published",
        "schema_version": "1.0.0",
        "timestamp": "2026-01-16T00:00:00Z",
        "actor_id": "system",
        "trace_id": "uuid"
    },
    "payload": {
        "epoch": 42,
        "merkle_root": "blake3:abc123...",
        "start_sequence": 41001,
        "end_sequence": 42000,
        "event_count": 1000,
        "algorithm": "blake3"
    }
}
```

### Database Schema

**Merkle Epochs Table:**
```sql
CREATE TABLE ledger.merkle_epochs (
    epoch_id bigint PRIMARY KEY,
    root_hash text NOT NULL,
    algorithm text NOT NULL DEFAULT 'blake3',
    start_sequence bigint NOT NULL,
    end_sequence bigint NOT NULL,
    event_count int NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    root_event_id uuid NOT NULL REFERENCES ledger.governance_events(event_id)
);

CREATE INDEX idx_merkle_epochs_sequence ON ledger.merkle_epochs (start_sequence, end_sequence);
```

**Note:** Stored in `ledger` schema (not `projections`) because Merkle roots are part of the cryptographic integrity infrastructure.

### MerkleTreePort Interface

```python
from typing import Protocol
from uuid import UUID

class MerkleTreePort(Protocol):
    """Port for Merkle tree proof operations.

    Constitutional Guarantee:
    - Any event can have proof generated
    - Proofs are independently verifiable
    - Epoch roots are published to ledger
    """

    async def build_epoch(self, epoch_id: int, event_hashes: list[str]) -> str:
        """Build Merkle tree for epoch and return root."""
        ...

    async def generate_proof(self, event_id: UUID) -> MerkleProof:
        """Generate inclusion proof for specific event."""
        ...

    async def get_epoch_root(self, epoch_id: int) -> str | None:
        """Get published root for epoch."""
        ...

    async def get_epoch_for_sequence(self, sequence: int) -> int:
        """Determine which epoch contains a given sequence number."""
        ...

    def verify_proof(self, proof: MerkleProof) -> bool:
        """Verify proof (no async - pure computation)."""
        ...
```

### Existing Patterns to Follow

**Reference:** `src/domain/governance/events/hash_chain.py` (from story 1-3)

The hash chain implementation provides:
- Algorithm abstraction (BLAKE3/SHA-256)
- Algorithm-prefixed hash format
- Verification patterns

**Reference:** `src/application/ports/governance/ledger_port.py` (from story 1-2)

The ledger port provides:
- Event retrieval for tree building
- Event append for root publication

### Dependency on Story 1-1, 1-2, 1-3

This story depends on:
- `consent-gov-1-1-event-envelope-domain-model`: `GovernanceEvent`, `EventMetadata`
- `consent-gov-1-2-append-only-ledger-port-adapter`: `GovernanceLedgerPort.read_events()`, `append_event()`
- `consent-gov-1-3-hash-chain-implementation`: Hash algorithms, `compute_event_hash()`

**Import:**
```python
from src.domain.governance.events.event_envelope import GovernanceEvent, EventMetadata
from src.application.ports.governance.ledger_port import GovernanceLedgerPort
from src.domain.governance.events.hash_algorithms import Blake3Hasher, Sha256Hasher
```

### Source Tree Components

**New Files:**
```
src/domain/governance/events/
└── merkle_tree.py                        # MerkleTree, MerkleProof, verify_merkle_proof

src/application/ports/governance/
└── merkle_tree_port.py                   # MerkleTreePort protocol

src/application/services/governance/
└── epoch_manager.py                      # EpochManager service

src/infrastructure/adapters/governance/
└── merkle_tree_adapter.py                # PostgresMerkleTreeAdapter

alembic/versions/
└── YYYYMMDD_HHMMSS_create_merkle_epochs_table.py
```

**Test Files:**
```
tests/unit/domain/governance/events/
└── test_merkle_tree.py

tests/unit/application/ports/governance/
└── test_merkle_tree_port.py

tests/integration/governance/
└── test_merkle_proofs.py
```

### Technical Requirements

**Python Patterns (CRITICAL):**
- Pure domain logic in `merkle_tree.py` (no I/O)
- Frozen dataclasses for `MerkleProof`
- Type hints on ALL functions (mypy --strict must pass)
- Use existing hash algorithm abstractions from story 1-3

**Merkle Tree Requirements:**
- Support arbitrary number of leaves (pad to power of two)
- Use prefix bytes to prevent second-preimage attacks
- Sort children before hashing for consistent ordering
- Support both BLAKE3 and SHA-256

**Verification Requirements:**
- `verify_merkle_proof()` must be standalone (no database)
- External verifiers can use this function directly
- Returns boolean with no side effects

### Testing Standards

**Unit Test Patterns:**
```python
import pytest
from uuid import uuid4

class TestMerkleTree:
    def test_single_event_tree(self):
        """Tree with one event has that event's hash as root."""
        hashes = ["blake3:abc123"]
        tree = MerkleTree(hashes)
        assert tree.root is not None

    def test_power_of_two_events(self):
        """Tree with 4 events builds correctly."""
        hashes = [f"blake3:hash{i}" for i in range(4)]
        tree = MerkleTree(hashes)
        assert tree.root is not None
        # Verify all proofs
        for i in range(4):
            proof = tree.generate_proof(i, uuid4(), hashes[i])
            assert verify_merkle_proof(proof)

    def test_non_power_of_two_events(self):
        """Tree with 5 events pads correctly."""
        hashes = [f"blake3:hash{i}" for i in range(5)]
        tree = MerkleTree(hashes)
        assert tree.root is not None
        # Verify all real proofs
        for i in range(5):
            proof = tree.generate_proof(i, uuid4(), hashes[i])
            assert verify_merkle_proof(proof)

    def test_tampered_proof_fails(self):
        """Modified hash in proof fails verification."""
        hashes = [f"blake3:hash{i}" for i in range(4)]
        tree = MerkleTree(hashes)
        proof = tree.generate_proof(0, uuid4(), hashes[0])

        # Tamper with event hash
        tampered = MerkleProof(
            event_id=proof.event_id,
            event_hash="blake3:tampered",  # Changed!
            merkle_path=proof.merkle_path,
            merkle_root=proof.merkle_root,
            epoch=proof.epoch,
            leaf_index=proof.leaf_index,
        )
        assert not verify_merkle_proof(tampered)

    def test_sha256_algorithm(self):
        """Tree works with SHA-256 algorithm."""
        hashes = [f"sha256:hash{i}" for i in range(4)]
        tree = MerkleTree(hashes, algorithm="sha256")
        assert tree.root.startswith("sha256:")
```

**Coverage Requirement:** 100% for Merkle tree domain logic

### Library/Framework Requirements

| Library | Version | Purpose |
|---------|---------|---------|
| Python | 3.11+ | Type hints, dataclasses |
| blake3 | latest | BLAKE3 hashing (from story 1-3) |
| hashlib | stdlib | SHA-256 hashing |
| pytest | latest | Unit testing |

### Project Structure Notes

**Alignment:** Creates Merkle tree infrastructure in `src/domain/governance/events/` per architecture (Step 6).

**Import Rules (Hexagonal):**
- Domain Merkle tree imports nothing from infrastructure
- `verify_merkle_proof()` is pure function (no I/O)
- Adapter imports domain types and port interface
- Service imports port for dependency injection

### References

- [Source: _bmad-output/planning-artifacts/governance-architecture.md#Proof-of-Inclusion (Locked)]
- [Source: _bmad-output/planning-artifacts/governance-architecture.md#Hash Chain Implementation (Locked)]
- [Source: _bmad-output/planning-artifacts/government-epics.md#GOV-1-7]
- [Source: _bmad-output/project-context.md#Critical Implementation Rules]
- [Source: consent-gov-1-1-event-envelope-domain-model.md] - Dependency
- [Source: consent-gov-1-2-append-only-ledger-port-adapter.md] - Dependency
- [Source: consent-gov-1-3-hash-chain-implementation.md] - Dependency

### FR/NFR Traceability

| Requirement | Description | Implementation |
|-------------|-------------|----------------|
| AD-7 | Merkle tree proof-of-inclusion | Root per epoch, proof generation |
| NFR-CONST-02 | Proof-of-inclusion for any entry | MerkleProof with verification |
| NFR-AUDIT-06 | External verification possible | Standalone verify_merkle_proof() |
| FR57 | Cryptographic proof of completeness | Merkle root + hash chain |

### Story Dependencies

| Story | Dependency Type | What We Need |
|-------|-----------------|--------------|
| consent-gov-1-1 | Hard dependency | `GovernanceEvent`, `EventMetadata` types |
| consent-gov-1-2 | Hard dependency | `GovernanceLedgerPort.read_events()` for tree building |
| consent-gov-1-3 | Hard dependency | Hash algorithms (BLAKE3, SHA-256) |

---

## Dev Agent Record

### Agent Model Used

claude-opus-4-5-20251101

### Debug Log References

None - all tests pass

### Completion Notes List

- **All 90 tests passing**: 44 unit tests + 27 epoch manager tests + 19 integration tests
- **Fixed security issue**: Removed sorted children in `_compute_internal_hash()` - order must matter for proof security (wrong leaf_index must fail verification)
- **Raw docstring**: Used `r"""` prefix to avoid escape sequence warnings in tree diagram
- **trace_id type**: Fixed integration tests to use `str(uuid4())` instead of raw `UUID` per AD-4 validation
- **Single-event tree**: Correctly produces empty merkle_path since single leaf IS the root (no padding when `_next_power_of_two(1)` = 1)
- **Empty tree validation order**: Check for empty tree BEFORE index bounds to raise proper `ValueError`
- **Constitutional compliance**: AD-7 (Merkle tree proof-of-inclusion), NFR-CONST-02, NFR-AUDIT-06, FR57

### File List

**Domain Layer:**
- `src/domain/governance/events/merkle_tree.py` - MerkleTree, MerkleProof, verify_merkle_proof, MerkleVerificationResult

**Application Layer:**
- `src/application/ports/governance/merkle_tree_port.py` - MerkleTreePort, EpochManagerPort protocols, EpochInfo, EpochConfig
- `src/application/services/governance/epoch_manager.py` - EpochManagerService for epoch lifecycle

**Infrastructure Layer:**
- `src/infrastructure/adapters/governance/merkle_tree_adapter.py` - PostgresMerkleTreeAdapter
- `migrations/011_create_merkle_epochs_table.sql` - Database schema for ledger.merkle_epochs

**Tests:**
- `tests/unit/domain/governance/events/test_merkle_tree.py` - 44 unit tests
- `tests/unit/application/services/governance/test_epoch_manager.py` - 27 unit tests
- `tests/integration/governance/test_merkle_proofs.py` - 19 integration tests

