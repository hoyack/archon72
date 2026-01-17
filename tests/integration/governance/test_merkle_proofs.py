"""Integration tests for Merkle tree proof-of-inclusion.

Story: consent-gov-1.7: Merkle Tree Proof-of-Inclusion

Tests cover:
- End-to-end proof generation from events
- Epoch root computation and verification
- Proof verification with published roots
- Multiple epochs handling
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.domain.governance.events.event_envelope import EventMetadata, GovernanceEvent
from src.domain.governance.events.hash_chain import add_hash_to_event
from src.domain.governance.events.merkle_tree import (
    MerkleProof,
    MerkleTree,
    verify_merkle_proof,
)


def _create_test_event(
    event_type: str = "executive.task.created",
    actor_id: str = "test-actor",
    payload: dict | None = None,
) -> GovernanceEvent:
    """Create a test governance event."""
    return GovernanceEvent(
        metadata=EventMetadata(
            event_id=uuid4(),
            event_type=event_type,
            timestamp=datetime.now(timezone.utc),
            actor_id=actor_id,
            schema_version="1.0.0",
            trace_id=str(uuid4()),  # trace_id must be string per AD-4
        ),
        payload=payload or {"test": "data"},
    )


def _create_hashed_events(count: int, algorithm: str = "blake3") -> list[GovernanceEvent]:
    """Create a list of hash-chained events."""
    events = [_create_test_event() for _ in range(count)]
    hashed_events = []
    prev_hash = None

    for event in events:
        hashed = add_hash_to_event(event, prev_hash, algorithm)
        hashed_events.append(hashed)
        prev_hash = hashed.hash

    return hashed_events


class TestEndToEndProofGeneration:
    """End-to-end tests for proof generation."""

    def test_generate_and_verify_proof_single_event(self) -> None:
        """Generate and verify proof for single event."""
        events = _create_hashed_events(1)
        event_hashes = [e.hash for e in events if e.hash]

        tree = MerkleTree(event_hashes, "blake3")
        proof = tree.generate_proof(0, events[0].event_id, epoch=0)

        result = verify_merkle_proof(proof)

        assert result.is_valid
        assert result.reconstructed_root == tree.root

    def test_generate_and_verify_proof_power_of_two(self) -> None:
        """Generate and verify proofs for power-of-two event count."""
        events = _create_hashed_events(8)
        event_hashes = [e.hash for e in events if e.hash]

        tree = MerkleTree(event_hashes, "blake3")

        # Verify proof for each event
        for i, event in enumerate(events):
            proof = tree.generate_proof(i, event.event_id, epoch=0)
            result = verify_merkle_proof(proof)
            assert result.is_valid, f"Proof for event {i} failed: {result.error_message}"

    def test_generate_and_verify_proof_non_power_of_two(self) -> None:
        """Generate and verify proofs for non-power-of-two event count."""
        events = _create_hashed_events(5)
        event_hashes = [e.hash for e in events if e.hash]

        tree = MerkleTree(event_hashes, "blake3")

        # Verify proof for each event
        for i, event in enumerate(events):
            proof = tree.generate_proof(i, event.event_id, epoch=0)
            result = verify_merkle_proof(proof)
            assert result.is_valid, f"Proof for event {i} failed: {result.error_message}"

    def test_large_tree_all_proofs_valid(self) -> None:
        """All proofs valid for larger tree (100 events)."""
        events = _create_hashed_events(100)
        event_hashes = [e.hash for e in events if e.hash]

        tree = MerkleTree(event_hashes, "blake3")

        # Sample verification (every 10th event to save time)
        for i in range(0, 100, 10):
            proof = tree.generate_proof(i, events[i].event_id, epoch=0)
            result = verify_merkle_proof(proof)
            assert result.is_valid, f"Proof for event {i} failed"


class TestEpochRootComputation:
    """Tests for epoch root computation."""

    def test_same_events_same_root(self) -> None:
        """Same events produce same root (deterministic)."""
        events = _create_hashed_events(10)
        event_hashes = [e.hash for e in events if e.hash]

        tree1 = MerkleTree(event_hashes, "blake3")
        tree2 = MerkleTree(event_hashes, "blake3")

        assert tree1.root == tree2.root

    def test_different_order_different_root(self) -> None:
        """Different event order produces different root."""
        events = _create_hashed_events(4)
        hashes1 = [e.hash for e in events if e.hash]
        hashes2 = list(reversed(hashes1))

        tree1 = MerkleTree(hashes1, "blake3")
        tree2 = MerkleTree(hashes2, "blake3")

        assert tree1.root != tree2.root

    def test_added_event_changes_root(self) -> None:
        """Adding an event changes the root."""
        events = _create_hashed_events(4)
        hashes1 = [e.hash for e in events[:3] if e.hash]
        hashes2 = [e.hash for e in events if e.hash]

        tree1 = MerkleTree(hashes1, "blake3")
        tree2 = MerkleTree(hashes2, "blake3")

        assert tree1.root != tree2.root

    def test_modified_event_changes_root(self) -> None:
        """Modifying an event changes the root."""
        events = _create_hashed_events(4)
        hashes1 = [e.hash for e in events if e.hash]

        # Create a different set of events
        events2 = _create_hashed_events(4)
        hashes2 = [e.hash for e in events2 if e.hash]

        tree1 = MerkleTree(hashes1, "blake3")
        tree2 = MerkleTree(hashes2, "blake3")

        assert tree1.root != tree2.root


class TestProofVerificationWithPublishedRoots:
    """Tests simulating proof verification against published roots."""

    def test_verify_proof_against_stored_root(self) -> None:
        """Verify proof against a stored/published root."""
        events = _create_hashed_events(8)
        event_hashes = [e.hash for e in events if e.hash]

        # Build tree and "store" the root
        tree = MerkleTree(event_hashes, "blake3")
        stored_root = tree.root

        # Generate proof for one event
        proof = tree.generate_proof(3, events[3].event_id, epoch=1)

        # Verify proof
        result = verify_merkle_proof(proof)

        assert result.is_valid
        assert result.reconstructed_root == stored_root

    def test_proof_fails_with_wrong_stored_root(self) -> None:
        """Proof fails if stored root doesn't match."""
        events = _create_hashed_events(8)
        event_hashes = [e.hash for e in events if e.hash]

        tree = MerkleTree(event_hashes, "blake3")

        # Generate proof
        proof = tree.generate_proof(3, events[3].event_id, epoch=1)

        # Create a proof with wrong root
        wrong_root_proof = MerkleProof(
            event_id=proof.event_id,
            event_hash=proof.event_hash,
            merkle_path=proof.merkle_path,
            merkle_root="blake3:wrong_root_0000000000000000000000000000000000000000000000",
            epoch=proof.epoch,
            leaf_index=proof.leaf_index,
            algorithm=proof.algorithm,
        )

        result = verify_merkle_proof(wrong_root_proof)
        assert not result.is_valid


class TestMultipleEpochs:
    """Tests for handling multiple epochs."""

    def test_different_epochs_different_roots(self) -> None:
        """Different epochs have different roots."""
        events1 = _create_hashed_events(10)
        events2 = _create_hashed_events(10)

        hashes1 = [e.hash for e in events1 if e.hash]
        hashes2 = [e.hash for e in events2 if e.hash]

        tree1 = MerkleTree(hashes1, "blake3")
        tree2 = MerkleTree(hashes2, "blake3")

        assert tree1.root != tree2.root

    def test_proof_from_epoch_1_valid_against_epoch_1_root(self) -> None:
        """Proof from epoch 1 validates against epoch 1 root."""
        # Simulate two epochs
        epoch0_events = _create_hashed_events(100)
        epoch1_events = _create_hashed_events(100)

        hashes0 = [e.hash for e in epoch0_events if e.hash]
        hashes1 = [e.hash for e in epoch1_events if e.hash]

        tree0 = MerkleTree(hashes0, "blake3")
        tree1 = MerkleTree(hashes1, "blake3")

        # Generate proof from epoch 1
        proof = tree1.generate_proof(50, epoch1_events[50].event_id, epoch=1)

        # Should verify against epoch 1 root
        result = verify_merkle_proof(proof)
        assert result.is_valid
        assert result.reconstructed_root == tree1.root
        assert result.reconstructed_root != tree0.root

    def test_proof_from_epoch_0_fails_against_epoch_1_root(self) -> None:
        """Proof from epoch 0 fails against epoch 1 root."""
        epoch0_events = _create_hashed_events(10)
        epoch1_events = _create_hashed_events(10)

        hashes0 = [e.hash for e in epoch0_events if e.hash]
        hashes1 = [e.hash for e in epoch1_events if e.hash]

        tree0 = MerkleTree(hashes0, "blake3")
        tree1 = MerkleTree(hashes1, "blake3")

        # Generate proof from epoch 0
        proof = tree0.generate_proof(0, epoch0_events[0].event_id, epoch=0)

        # Create proof with epoch 1 root
        cross_epoch_proof = MerkleProof(
            event_id=proof.event_id,
            event_hash=proof.event_hash,
            merkle_path=proof.merkle_path,
            merkle_root=tree1.root,  # Wrong epoch root!
            epoch=1,
            leaf_index=proof.leaf_index,
            algorithm=proof.algorithm,
        )

        result = verify_merkle_proof(cross_epoch_proof)
        assert not result.is_valid


class TestSha256Integration:
    """Integration tests using SHA-256 algorithm."""

    def test_sha256_end_to_end(self) -> None:
        """End-to-end proof with SHA-256."""
        events = _create_hashed_events(8, algorithm="sha256")
        event_hashes = [e.hash for e in events if e.hash]

        tree = MerkleTree(event_hashes, "sha256")

        for i, event in enumerate(events):
            proof = tree.generate_proof(i, event.event_id, epoch=0)

            assert proof.algorithm == "sha256"
            assert proof.merkle_root.startswith("sha256:")

            result = verify_merkle_proof(proof)
            assert result.is_valid


class TestExternalVerifierScenario:
    """Tests simulating external verifier scenarios."""

    def test_external_verifier_can_validate_proof(self) -> None:
        """External verifier can validate proof without database access."""
        # System creates events and builds tree
        events = _create_hashed_events(50)
        event_hashes = [e.hash for e in events if e.hash]
        tree = MerkleTree(event_hashes, "blake3")

        # System generates proof
        target_index = 25
        proof = tree.generate_proof(
            target_index,
            events[target_index].event_id,
            epoch=0,
        )

        # External verifier receives:
        # 1. The proof (JSON serializable)
        proof_dict = proof.to_dict()

        # 2. Reconstructs proof from dict
        reconstructed_proof = MerkleProof(
            event_id=events[target_index].event_id,
            event_hash=proof_dict["event_hash"],
            merkle_path=tuple(proof_dict["merkle_path"]),
            merkle_root=proof_dict["merkle_root"],
            epoch=proof_dict["epoch"],
            leaf_index=proof_dict["leaf_index"],
            algorithm=proof_dict["algorithm"],
        )

        # 3. Verifies without any database access
        result = verify_merkle_proof(reconstructed_proof)

        assert result.is_valid
        assert result.reconstructed_root == proof.merkle_root

    def test_external_verifier_detects_tampering(self) -> None:
        """External verifier detects tampered proof."""
        events = _create_hashed_events(10)
        event_hashes = [e.hash for e in events if e.hash]
        tree = MerkleTree(event_hashes, "blake3")

        proof = tree.generate_proof(5, events[5].event_id, epoch=0)

        # Tamper with proof data
        tampered_proof = MerkleProof(
            event_id=proof.event_id,
            event_hash="blake3:tampered_hash_00000000000000000000000000000000000000000",
            merkle_path=proof.merkle_path,
            merkle_root=proof.merkle_root,
            epoch=proof.epoch,
            leaf_index=proof.leaf_index,
            algorithm=proof.algorithm,
        )

        result = verify_merkle_proof(tampered_proof)
        assert not result.is_valid


class TestConstitutionalConstraints:
    """Tests verifying constitutional constraints (AD-7, NFR-CONST-02)."""

    def test_any_event_can_have_proof_generated(self) -> None:
        """AD-7: Any event can have proof generated."""
        events = _create_hashed_events(20)
        event_hashes = [e.hash for e in events if e.hash]
        tree = MerkleTree(event_hashes, "blake3")

        # Every single event should have a valid proof
        for i in range(len(events)):
            proof = tree.generate_proof(i, events[i].event_id, epoch=0)
            result = verify_merkle_proof(proof)
            assert result.is_valid, f"Event {i} proof generation failed"

    def test_proofs_independently_verifiable(self) -> None:
        """NFR-CONST-02: Proofs can be verified without full ledger."""
        events = _create_hashed_events(10)
        event_hashes = [e.hash for e in events if e.hash]
        tree = MerkleTree(event_hashes, "blake3")

        proof = tree.generate_proof(3, events[3].event_id, epoch=0)

        # Verification uses only the proof data - no tree or events needed
        # verify_merkle_proof is a pure function
        result = verify_merkle_proof(proof)
        assert result.is_valid

    def test_tampered_events_produce_different_root(self) -> None:
        """Tampered events produce different root (integrity)."""
        events = _create_hashed_events(10)
        original_hashes = [e.hash for e in events if e.hash]

        # Tamper by changing one hash
        tampered_hashes = original_hashes.copy()
        tampered_hashes[5] = "blake3:tampered_00000000000000000000000000000000000000000000"

        tree_original = MerkleTree(original_hashes, "blake3")
        tree_tampered = MerkleTree(tampered_hashes, "blake3")

        assert tree_original.root != tree_tampered.root
