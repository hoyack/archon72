# Story consent-gov-9.2: Cryptographic Proof Generation

Status: done

---

## Story

As a **verifier**,
I want **cryptographic proofs of ledger completeness**,
So that **I can verify nothing is missing**.

---

## Acceptance Criteria

1. **AC1:** System provides cryptographic proof of completeness (FR57)
2. **AC2:** Proof uses hash chain verification
3. **AC3:** Proof uses Merkle tree proof-of-inclusion
4. **AC4:** Proof is independently verifiable
5. **AC5:** Event `audit.proof.generated` emitted
6. **AC6:** Proof includes root hash and witness path
7. **AC7:** Proof can be verified without trusted party
8. **AC8:** Unit tests for proof generation

---

## Tasks / Subtasks

- [x] **Task 1: Create CompletenessProof domain model** (AC: 1)
  - [x] Create `src/domain/governance/audit/completeness_proof.py`
  - [x] Include hash_chain_proof
  - [x] Include merkle_proof
  - [x] Include verification_instructions

- [x] **Task 2: Create LedgerProofService** (AC: 1, 5)
  - [x] Create `src/application/services/governance/ledger_proof_service.py`
  - [x] Generate completeness proofs
  - [x] Emit `audit.proof.generated` event
  - [x] Coordinate hash chain and Merkle proofs

- [x] **Task 3: Create ProofPort interface** (AC: 1)
  - [x] Create port for proof operations
  - [x] Define `generate_completeness_proof()` method
  - [x] Define `get_merkle_proof()` method
  - [x] Define `get_hash_chain_proof()` method

- [x] **Task 4: Implement hash chain proof** (AC: 2)
  - [x] Prove each event links to previous
  - [x] Verify chain from genesis to latest
  - [x] Detect any gaps or modifications
  - [x] Include first and last hashes

- [x] **Task 5: Implement Merkle tree proof** (AC: 3)
  - [x] Build Merkle tree from events
  - [x] Generate proof-of-inclusion for any event
  - [x] Root hash represents entire ledger
  - [x] Witness path for verification

- [x] **Task 6: Implement independent verification** (AC: 4, 7)
  - [x] Proof contains all needed info
  - [x] No external data required
  - [x] Verifier needs only proof and events
  - [x] Step-by-step verification possible

- [x] **Task 7: Implement root and witness path** (AC: 6)
  - [x] Merkle root hash
  - [x] Sibling hashes for path
  - [x] Position indicators (left/right)
  - [x] Compact representation

- [x] **Task 8: Write comprehensive unit tests** (AC: 8)
  - [x] Test proof generation succeeds
  - [x] Test hash chain verification works
  - [x] Test Merkle proof verification works
  - [x] Test tampered ledger detection
  - [x] Test missing event detection

---

## Documentation Checklist

- [ ] Architecture docs updated (proof structure)
- [ ] Verification guide for auditors
- [ ] Inline comments explaining cryptographic operations
- [ ] N/A - README (internal component)

---

## Dev Notes

### Key Architectural Decisions

**Why Cryptographic Proofs?**
```
Trust but verify:
  - System claims ledger is complete
  - Proof lets you verify that claim
  - Math, not trust

Two proof mechanisms:
  1. Hash Chain: Each event links to previous
  2. Merkle Tree: Efficient proof-of-inclusion

Combined, they prove:
  - All events are present
  - No events were modified
  - Sequence is unbroken
  - Nothing was inserted
```

**Hash Chain Proof:**
```
How it works:
  Event₁.hash = H(Event₁.payload)
  Event₂.hash = H(Event₂.payload || Event₁.hash)
  Event₃.hash = H(Event₃.payload || Event₂.hash)
  ...

Verification:
  - Recompute each hash
  - Verify it matches stored hash
  - Verify prev_hash links correctly
  - Chain must be unbroken

Detects:
  - Modified events (hash mismatch)
  - Missing events (prev_hash gap)
  - Reordered events (sequence break)
```

**Merkle Tree Proof:**
```
How it works:
  - Leaves = event hashes
  - Nodes = H(left_child || right_child)
  - Root = single hash representing all

Proof-of-inclusion:
  - Sibling hashes along path
  - Position (left/right) at each level
  - Verifier reconstructs path to root
  - Matches root = event is included

Benefits:
  - Compact proof (O(log n))
  - Any event verifiable
  - Root hash = commitment to entire ledger
```

### Domain Models

```python
@dataclass(frozen=True)
class HashChainProof:
    """Proof that hash chain is complete and unbroken."""
    genesis_hash: str
    latest_hash: str
    total_events: int
    algorithm: str  # "BLAKE3" or "SHA256"
    chain_valid: bool


@dataclass(frozen=True)
class MerkleProof:
    """Merkle proof-of-inclusion for an event."""
    event_id: UUID
    event_hash: str
    merkle_root: str
    witness_path: list[tuple[str, str]]  # (sibling_hash, position)
    tree_height: int


@dataclass(frozen=True)
class CompletenessProof:
    """Complete proof of ledger integrity.

    Includes both hash chain and Merkle tree proofs.
    Can be verified independently.
    """
    proof_id: UUID
    generated_at: datetime
    hash_chain_proof: HashChainProof
    merkle_root: str
    total_events: int
    verification_instructions: str


class ProofGenerationError(ValueError):
    """Raised when proof generation fails."""
    pass


class InvalidProofError(ValueError):
    """Raised when proof verification fails."""
    pass
```

### Service Implementation Sketch

```python
class LedgerProofService:
    """Generates cryptographic proofs of ledger integrity.

    Proofs are independently verifiable.
    No trusted party required.
    """

    def __init__(
        self,
        ledger_port: LedgerPort,
        merkle_tree: MerkleTreePort,
        hash_chain: HashChainPort,
        event_emitter: EventEmitter,
        time_authority: TimeAuthority,
    ):
        self._ledger = ledger_port
        self._merkle = merkle_tree
        self._chain = hash_chain
        self._event_emitter = event_emitter
        self._time = time_authority

    async def generate_completeness_proof(
        self,
        requester_id: UUID,
    ) -> CompletenessProof:
        """Generate proof that ledger is complete.

        The proof can be independently verified.

        Args:
            requester_id: Who is requesting the proof

        Returns:
            CompletenessProof with all verification data
        """
        now = self._time.now()
        proof_id = uuid4()

        # Get all events
        events = await self._ledger.get_all_events()

        # Generate hash chain proof
        chain_proof = await self._generate_hash_chain_proof(events)

        # Generate Merkle root
        merkle_root = await self._merkle.compute_root(events)

        # Create completeness proof
        proof = CompletenessProof(
            proof_id=proof_id,
            generated_at=now,
            hash_chain_proof=chain_proof,
            merkle_root=merkle_root,
            total_events=len(events),
            verification_instructions=self._get_verification_instructions(),
        )

        # Emit proof generated event
        await self._event_emitter.emit(
            event_type="audit.proof.generated",
            actor=str(requester_id),
            payload={
                "proof_id": str(proof_id),
                "requester_id": str(requester_id),
                "generated_at": now.isoformat(),
                "total_events": len(events),
                "merkle_root": merkle_root,
                "chain_valid": chain_proof.chain_valid,
            },
        )

        return proof

    async def generate_merkle_proof(
        self,
        event_id: UUID,
    ) -> MerkleProof:
        """Generate Merkle proof-of-inclusion for specific event.

        Proves that event is included in the ledger.

        Args:
            event_id: The event to prove inclusion for

        Returns:
            MerkleProof with witness path
        """
        # Get event
        event = await self._ledger.get_event(event_id)
        if event is None:
            raise ProofGenerationError(f"Event {event_id} not found")

        # Get all events for tree
        events = await self._ledger.get_all_events()

        # Build tree and get proof
        root, path = await self._merkle.generate_proof(
            events=events,
            target_event=event,
        )

        return MerkleProof(
            event_id=event_id,
            event_hash=event.event_hash,
            merkle_root=root,
            witness_path=path,
            tree_height=self._merkle.get_height(len(events)),
        )

    async def _generate_hash_chain_proof(
        self,
        events: list[EventEnvelope],
    ) -> HashChainProof:
        """Generate hash chain proof."""
        if not events:
            return HashChainProof(
                genesis_hash="",
                latest_hash="",
                total_events=0,
                algorithm="BLAKE3",
                chain_valid=True,
            )

        # Verify chain
        chain_valid = await self._chain.verify_chain(events)

        return HashChainProof(
            genesis_hash=events[0].event_hash,
            latest_hash=events[-1].event_hash,
            total_events=len(events),
            algorithm="BLAKE3",
            chain_valid=chain_valid,
        )

    def _get_verification_instructions(self) -> str:
        """Get human-readable verification instructions."""
        return """
VERIFICATION INSTRUCTIONS

1. Hash Chain Verification:
   - For each event, compute H(payload || prev_hash)
   - Verify computed hash matches event.event_hash
   - Verify event.prev_hash matches previous event.event_hash
   - Chain is valid if all links are correct

2. Merkle Tree Verification:
   - Start with target event hash
   - For each step in witness_path:
     - Combine with sibling hash (order by position)
     - Hash the combination
   - Final hash should equal merkle_root

3. Completeness Check:
   - Verify hash chain from genesis to latest
   - Verify Merkle root matches expected
   - No gaps in sequence numbers
   - All proofs pass = ledger is complete
"""


class MerkleTreePort(Protocol):
    """Port for Merkle tree operations."""

    async def compute_root(
        self,
        events: list[EventEnvelope],
    ) -> str:
        """Compute Merkle root for events."""
        ...

    async def generate_proof(
        self,
        events: list[EventEnvelope],
        target_event: EventEnvelope,
    ) -> tuple[str, list[tuple[str, str]]]:
        """Generate proof-of-inclusion for target event."""
        ...

    def get_height(self, num_leaves: int) -> int:
        """Get tree height for number of leaves."""
        ...


class HashChainPort(Protocol):
    """Port for hash chain operations."""

    async def verify_chain(
        self,
        events: list[EventEnvelope],
    ) -> bool:
        """Verify hash chain is valid."""
        ...

    async def compute_hash(
        self,
        event: EventEnvelope,
        prev_hash: str,
    ) -> str:
        """Compute hash for event."""
        ...
```

### Event Pattern

```python
# Proof generated
{
    "event_type": "audit.proof.generated",
    "actor": "requester-uuid",
    "payload": {
        "proof_id": "uuid",
        "requester_id": "uuid",
        "generated_at": "2026-01-16T00:00:00Z",
        "total_events": 12345,
        "merkle_root": "blake3:abc123...",
        "chain_valid": true
    }
}
```

### Test Patterns

```python
class TestLedgerProofService:
    """Unit tests for ledger proof service."""

    async def test_completeness_proof_generated(
        self,
        proof_service: LedgerProofService,
        ledger_with_events: FakeLedgerPort,
        verifier: Verifier,
    ):
        """Completeness proof is generated."""
        proof = await proof_service.generate_completeness_proof(
            requester_id=verifier.id,
        )

        assert proof.proof_id is not None
        assert proof.hash_chain_proof.chain_valid

    async def test_hash_chain_verification(
        self,
        proof_service: LedgerProofService,
        ledger_with_events: FakeLedgerPort,
        verifier: Verifier,
    ):
        """Hash chain proof is verifiable."""
        proof = await proof_service.generate_completeness_proof(
            requester_id=verifier.id,
        )

        assert proof.hash_chain_proof.chain_valid
        assert proof.hash_chain_proof.genesis_hash != ""
        assert proof.hash_chain_proof.latest_hash != ""

    async def test_merkle_proof_verification(
        self,
        proof_service: LedgerProofService,
        ledger_with_events: FakeLedgerPort,
        event_in_ledger: EventEnvelope,
    ):
        """Merkle proof-of-inclusion is verifiable."""
        proof = await proof_service.generate_merkle_proof(
            event_id=event_in_ledger.event_id,
        )

        assert proof.merkle_root is not None
        assert len(proof.witness_path) > 0

    async def test_proof_event_emitted(
        self,
        proof_service: LedgerProofService,
        verifier: Verifier,
        event_capture: EventCapture,
    ):
        """Proof generation event is emitted."""
        await proof_service.generate_completeness_proof(
            requester_id=verifier.id,
        )

        event = event_capture.get_last("audit.proof.generated")
        assert event is not None


class TestHashChainVerification:
    """Tests for hash chain verification."""

    async def test_valid_chain_passes(
        self,
        hash_chain_port: FakeHashChainPort,
        valid_events: list[EventEnvelope],
    ):
        """Valid hash chain passes verification."""
        result = await hash_chain_port.verify_chain(valid_events)
        assert result is True

    async def test_modified_event_detected(
        self,
        hash_chain_port: FakeHashChainPort,
        events_with_modified: list[EventEnvelope],
    ):
        """Modified event is detected."""
        result = await hash_chain_port.verify_chain(events_with_modified)
        assert result is False

    async def test_missing_event_detected(
        self,
        hash_chain_port: FakeHashChainPort,
        events_with_gap: list[EventEnvelope],
    ):
        """Missing event (gap) is detected."""
        result = await hash_chain_port.verify_chain(events_with_gap)
        assert result is False


class TestMerkleProofVerification:
    """Tests for Merkle proof verification."""

    async def test_valid_proof_verifies(
        self,
        merkle_tree_port: FakeMerkleTreePort,
        events: list[EventEnvelope],
        target_event: EventEnvelope,
    ):
        """Valid Merkle proof verifies."""
        root, path = await merkle_tree_port.generate_proof(
            events=events,
            target_event=target_event,
        )

        # Verify by reconstructing path
        verified = verify_merkle_proof(
            event_hash=target_event.event_hash,
            witness_path=path,
            expected_root=root,
        )

        assert verified is True

    async def test_tampered_proof_fails(
        self,
        merkle_tree_port: FakeMerkleTreePort,
        events: list[EventEnvelope],
        target_event: EventEnvelope,
    ):
        """Tampered Merkle proof fails verification."""
        root, path = await merkle_tree_port.generate_proof(
            events=events,
            target_event=target_event,
        )

        # Tamper with path
        tampered_path = [(h + "X", p) for h, p in path]

        verified = verify_merkle_proof(
            event_hash=target_event.event_hash,
            witness_path=tampered_path,
            expected_root=root,
        )

        assert verified is False


class TestIndependentVerification:
    """Tests ensuring proof can be verified independently."""

    async def test_proof_contains_all_needed_info(
        self,
        proof_service: LedgerProofService,
        verifier: Verifier,
    ):
        """Proof contains everything needed for verification."""
        proof = await proof_service.generate_completeness_proof(
            requester_id=verifier.id,
        )

        # All needed fields present
        assert proof.hash_chain_proof is not None
        assert proof.merkle_root is not None
        assert proof.verification_instructions is not None
        assert proof.total_events >= 0

    async def test_verification_needs_no_external_data(
        self,
        proof_service: LedgerProofService,
        export_service: LedgerExportService,
        verifier: Verifier,
    ):
        """Verification possible with just proof and export."""
        proof = await proof_service.generate_completeness_proof(
            requester_id=verifier.id,
        )
        export = await export_service.export_complete(
            requester_id=verifier.id,
        )

        # Can verify with just these two
        verified = verify_independently(proof, export)
        assert verified is True
```

### Dependencies

- **Depends on:** consent-gov-1-3 (hash chain), consent-gov-1-7 (Merkle tree)
- **Enables:** consent-gov-9-3 (independent verification)

### References

- FR57: System can provide cryptographic proof of ledger completeness
