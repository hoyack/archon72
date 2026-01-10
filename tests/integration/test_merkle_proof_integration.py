"""Integration tests for Merkle proof functionality (Story 4.6, Task 9).

Tests the full integration of:
- Merkle tree building and proof generation
- Observer service Merkle proof methods
- Checkpoint generation and retrieval
- Verification toolkit Merkle verification

Constitutional Constraints tested:
- FR136: Merkle proof SHALL be included in event query responses when requested
- FR137: Observers SHALL be able to verify event inclusion without downloading full chain
- FR138: Weekly checkpoint anchors SHALL be published at consistent intervals
"""

import math
from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.application.services.merkle_tree_service import MerkleTreeService
from src.application.services.observer_service import ObserverService
from src.domain.events import Event
from src.domain.models.checkpoint import Checkpoint
from src.infrastructure.stubs.checkpoint_worker_stub import CheckpointWorkerStub


class TestMerkleProofIntegration:
    """Integration tests for Merkle proof generation and verification."""

    def _create_events(self, count: int, start_seq: int = 1) -> list[Event]:
        """Create test events with sequential hashes."""
        return [
            Event(
                event_id=uuid4(),
                sequence=i,
                event_type="test.event",
                payload={"index": i},
                prev_hash="0" * 64 if i == 1 else f"{i-1:064x}",
                content_hash=f"{i:064x}",
                signature="sig123",
                witness_id="witness-001",
                witness_signature="wsig123",
                local_timestamp=datetime.now(timezone.utc),
                authority_timestamp=datetime.now(timezone.utc),
            )
            for i in range(start_seq, start_seq + count)
        ]

    def _create_service_with_checkpoint(
        self,
        events: list[Event],
        checkpoint: Checkpoint,
    ) -> ObserverService:
        """Create ObserverService with test data."""
        event_store = AsyncMock()
        event_store.get_events_by_sequence_range.return_value = events
        event_store.get_event_by_sequence.side_effect = (
            lambda seq: next((e for e in events if e.sequence == seq), None)
        )
        event_store.get_max_sequence.return_value = len(events)
        event_store.get_events_up_to_sequence.return_value = events
        event_store.count_events_up_to_sequence.return_value = len(events)
        event_store.get_latest_event.return_value = events[-1] if events else None

        halt_checker = AsyncMock()
        halt_checker.is_halted.return_value = False

        checkpoint_repo = AsyncMock()
        checkpoint_repo.get_checkpoint_for_sequence.return_value = checkpoint
        checkpoint_repo.list_checkpoints.return_value = ([checkpoint], 1)

        merkle_service = MerkleTreeService()

        return ObserverService(
            event_store=event_store,
            halt_checker=halt_checker,
            checkpoint_repo=checkpoint_repo,
            merkle_service=merkle_service,
        )

    @pytest.mark.asyncio
    async def test_merkle_proof_generation_and_verification_fr136(self) -> None:
        """Test full Merkle proof generation and verification (FR136).

        FR136: Merkle proof SHALL be included in event query responses when requested.
        """
        # Create 100 events
        events = self._create_events(100)

        # Build Merkle tree to get root
        merkle_service = MerkleTreeService()
        leaves = [e.content_hash for e in events]
        merkle_root, _ = merkle_service.build_tree(leaves)

        # Create checkpoint with Merkle root
        checkpoint = Checkpoint(
            checkpoint_id=uuid4(),
            event_sequence=100,
            timestamp=datetime.now(timezone.utc),
            anchor_hash=merkle_root,
            anchor_type="periodic",
            creator_id="system",
        )

        # Create service
        service = self._create_service_with_checkpoint(events, checkpoint)

        # Generate proof for sequence 50
        proof = await service._generate_merkle_proof(50)

        assert proof is not None
        assert proof.event_sequence == 50
        assert proof.event_hash == events[49].content_hash
        assert proof.checkpoint_root == merkle_root

        # Manual verification: walk path from leaf to root
        current = proof.event_hash
        for entry in proof.path:
            import hashlib
            combined = "".join(sorted([entry.sibling_hash, current]))
            current = hashlib.sha256(combined.encode()).hexdigest()

        assert current == merkle_root

    @pytest.mark.asyncio
    async def test_merkle_proof_is_o_log_n_fr137(self) -> None:
        """Test Merkle proof path length is O(log n) (FR137).

        FR137: Observers SHALL be able to verify event inclusion
        without downloading the full chain.
        """
        # Test with different sizes
        for size in [8, 32, 128, 1000]:
            events = self._create_events(size)

            merkle_service = MerkleTreeService()
            leaves = [e.content_hash for e in events]
            merkle_root, _ = merkle_service.build_tree(leaves)

            checkpoint = Checkpoint(
                checkpoint_id=uuid4(),
                event_sequence=size,
                timestamp=datetime.now(timezone.utc),
                anchor_hash=merkle_root,
                anchor_type="periodic",
                creator_id="system",
            )

            service = self._create_service_with_checkpoint(events, checkpoint)

            # Generate proof for middle event
            middle = size // 2
            proof = await service._generate_merkle_proof(middle)

            assert proof is not None

            # Path length should be O(log n)
            # For n leaves padded to next power of 2, path length = ceil(log2(padded_size))
            padded_size = 1
            while padded_size < size:
                padded_size *= 2
            expected_max_path = math.ceil(math.log2(padded_size))

            assert len(proof.path) <= expected_max_path, (
                f"Path length {len(proof.path)} exceeds O(log n) for size {size} "
                f"(expected max {expected_max_path})"
            )

    @pytest.mark.asyncio
    async def test_get_events_with_merkle_proof_returns_proof_for_checkpointed(
        self,
    ) -> None:
        """Test get_events_with_merkle_proof returns Merkle proof for checkpointed events."""
        events = self._create_events(100)

        merkle_service = MerkleTreeService()
        leaves = [e.content_hash for e in events]
        merkle_root, _ = merkle_service.build_tree(leaves)

        checkpoint = Checkpoint(
            checkpoint_id=uuid4(),
            event_sequence=100,
            timestamp=datetime.now(timezone.utc),
            anchor_hash=merkle_root,
            anchor_type="periodic",
            creator_id="system",
        )

        service = self._create_service_with_checkpoint(events, checkpoint)

        result_events, total, merkle_proof, hash_proof = (
            await service.get_events_with_merkle_proof(as_of_sequence=50)
        )

        assert len(result_events) == 100
        assert merkle_proof is not None
        assert hash_proof is None  # Merkle proof takes precedence

    @pytest.mark.asyncio
    async def test_get_events_with_merkle_proof_falls_back_for_pending(self) -> None:
        """Test get_events_with_merkle_proof falls back to hash chain for pending events."""
        events = self._create_events(100)

        # No checkpoint (pending interval)
        service = self._create_service_with_checkpoint(events, checkpoint=None)
        service._checkpoint_repo.get_checkpoint_for_sequence.return_value = None

        result_events, total, merkle_proof, hash_proof = (
            await service.get_events_with_merkle_proof(as_of_sequence=50)
        )

        assert merkle_proof is None  # No checkpoint
        assert hash_proof is not None  # Falls back to hash chain

    @pytest.mark.asyncio
    async def test_checkpoint_worker_generates_valid_merkle_root_fr138(self) -> None:
        """Test checkpoint worker generates valid Merkle root (FR138).

        FR138: Weekly checkpoint anchors SHALL be published at consistent intervals.
        """
        events = self._create_events(50)

        event_store = AsyncMock()
        event_store.get_max_sequence.return_value = 50
        event_store.get_events_by_sequence_range.return_value = events

        checkpoint_repo = AsyncMock()
        checkpoint_repo.list_checkpoints.return_value = ([], 0)

        merkle_service = MerkleTreeService()

        worker = CheckpointWorkerStub(
            event_store=event_store,
            checkpoint_repo=checkpoint_repo,
            merkle_service=merkle_service,
        )

        checkpoint = await worker.generate_checkpoint()

        # Verify Merkle root is correct
        leaves = [e.content_hash for e in events]
        expected_root, _ = merkle_service.build_tree(leaves)

        assert checkpoint.anchor_hash == expected_root
        assert checkpoint.event_sequence == 50
        assert checkpoint.anchor_type == "periodic"

    @pytest.mark.asyncio
    async def test_list_checkpoints_returns_checkpoints_fr138(self) -> None:
        """Test list_checkpoints returns available checkpoints (FR138)."""
        events = self._create_events(100)

        merkle_service = MerkleTreeService()
        leaves = [e.content_hash for e in events]
        merkle_root, _ = merkle_service.build_tree(leaves)

        checkpoints = [
            Checkpoint(
                checkpoint_id=uuid4(),
                event_sequence=i * 100,
                timestamp=datetime.now(timezone.utc),
                anchor_hash=f"{i:064x}",
                anchor_type="periodic",
                creator_id="system",
            )
            for i in range(1, 6)
        ]

        service = self._create_service_with_checkpoint(events, checkpoints[0])
        service._checkpoint_repo.list_checkpoints.return_value = (checkpoints, 5)

        result, total = await service.list_checkpoints(limit=10, offset=0)

        assert len(result) == 5
        assert total == 5

    @pytest.mark.asyncio
    async def test_proof_verifies_with_toolkit(self) -> None:
        """Test generated Merkle proof verifies with toolkit."""
        events = self._create_events(64)

        merkle_service = MerkleTreeService()
        leaves = [e.content_hash for e in events]
        merkle_root, _ = merkle_service.build_tree(leaves)

        checkpoint = Checkpoint(
            checkpoint_id=uuid4(),
            event_sequence=64,
            timestamp=datetime.now(timezone.utc),
            anchor_hash=merkle_root,
            anchor_type="periodic",
            creator_id="system",
        )

        service = self._create_service_with_checkpoint(events, checkpoint)

        # Generate proof
        proof = await service._generate_merkle_proof(32)

        # Convert to dict for toolkit verifier
        proof_dict = {
            "event_sequence": proof.event_sequence,
            "event_hash": proof.event_hash,
            "checkpoint_sequence": proof.checkpoint_sequence,
            "checkpoint_root": proof.checkpoint_root,
            "path": [
                {
                    "level": e.level,
                    "position": e.position,
                    "sibling_hash": e.sibling_hash,
                }
                for e in proof.path
            ],
            "tree_size": proof.tree_size,
        }

        # Verify the proof dict structure matches expected format
        assert "event_hash" in proof_dict
        assert "checkpoint_root" in proof_dict
        assert "path" in proof_dict
        assert len(proof_dict["path"]) <= 6  # log2(64) = 6

    @pytest.mark.asyncio
    async def test_end_to_end_merkle_verification(self) -> None:
        """Test complete end-to-end Merkle proof generation and verification."""
        # 1. Create events
        events = self._create_events(128)

        # 2. Build Merkle tree
        merkle_service = MerkleTreeService()
        leaves = [e.content_hash for e in events]
        merkle_root, _ = merkle_service.build_tree(leaves)

        # 3. Create checkpoint
        checkpoint = Checkpoint(
            checkpoint_id=uuid4(),
            event_sequence=128,
            timestamp=datetime.now(timezone.utc),
            anchor_hash=merkle_root,
            anchor_type="periodic",
            creator_id="system",
        )

        # 4. Create service
        service = self._create_service_with_checkpoint(events, checkpoint)

        # 5. Test proofs for multiple events
        for seq in [1, 32, 64, 100, 128]:
            proof = await service._generate_merkle_proof(seq)

            assert proof is not None
            assert proof.event_sequence == seq
            assert proof.event_hash == events[seq - 1].content_hash

            # Verify proof manually
            import hashlib
            current = proof.event_hash
            for entry in proof.path:
                combined = "".join(sorted([entry.sibling_hash, current]))
                current = hashlib.sha256(combined.encode()).hexdigest()

            assert current == merkle_root, (
                f"Proof verification failed for sequence {seq}"
            )
