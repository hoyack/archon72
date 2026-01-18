"""Ledger Proof Service - Cryptographic proof generation for verification.

Story: consent-gov-9.2: Cryptographic Proof Generation

This service generates cryptographic proofs that the governance ledger
is complete and unmodified. Proofs can be verified independently
without trusted parties.

Constitutional Requirements:
- FR57: System can provide cryptographic proof of ledger completeness
- NFR-AUDIT-06: External verification possible

Proof Philosophy:
- Math, not trust
- Proofs are self-contained (all needed info included)
- Verification requires no database access
- External auditors can verify independently
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, Protocol
from uuid import UUID, uuid4

from src.domain.governance.audit.completeness_proof import (
    DEFAULT_VERIFICATION_INSTRUCTIONS,
    CompletenessProof,
    HashChainProof,
    ProofGenerationError,
)
from src.domain.governance.events.hash_algorithms import DEFAULT_ALGORITHM
from src.domain.governance.events.merkle_tree import (
    MerkleProof,
    MerkleTree,
    MerkleVerificationResult,
    compute_merkle_root,
    verify_merkle_proof,
)

if TYPE_CHECKING:
    from src.application.ports.governance.ledger_port import (
        GovernanceLedgerPort,
        PersistedGovernanceEvent,
    )
    from src.application.ports.governance.merkle_tree_port import MerkleTreePort

# Event type for audit logging
PROOF_GENERATED_EVENT = "audit.proof.generated"
PROOF_VERIFIED_EVENT = "audit.proof.verified"


class EventEmitterPort(Protocol):
    """Port for emitting events."""

    async def emit(
        self,
        event_type: str,
        actor: str,
        payload: dict[str, Any],
    ) -> None:
        """Emit an event."""
        ...


class TimeAuthorityPort(Protocol):
    """Port for getting authoritative time."""

    def now(self) -> datetime:
        """Get current time."""
        ...


class LedgerProofService:
    """Service for generating cryptographic proofs of ledger integrity.

    Proofs demonstrate:
    1. Hash chain is unbroken (integrity - no tampering)
    2. All events are accounted for (completeness - no omissions)
    3. Merkle root commits to exact ledger state

    All proofs can be verified independently without:
    - Database access
    - Trusted parties
    - Network connectivity

    The math proves completeness - you don't need to trust anyone.
    """

    def __init__(
        self,
        ledger_port: GovernanceLedgerPort,
        merkle_port: MerkleTreePort | None,
        event_emitter: EventEmitterPort,
        time_authority: TimeAuthorityPort,
    ) -> None:
        """Initialize the proof service.

        Args:
            ledger_port: Port for reading governance events.
            merkle_port: Port for Merkle tree operations (optional).
            event_emitter: Port for emitting audit events.
            time_authority: Port for getting authoritative time.
        """
        self._ledger = ledger_port
        self._merkle = merkle_port
        self._event_emitter = event_emitter
        self._time = time_authority

    async def generate_completeness_proof(
        self,
        requester_id: UUID,
    ) -> CompletenessProof:
        """Generate proof of ledger completeness.

        Creates a cryptographic proof demonstrating the ledger is complete
        and unmodified. The proof includes:
        1. Hash chain proof (each event links to previous)
        2. Merkle root (commits to all events)
        3. Verification instructions

        Args:
            requester_id: UUID of the requester (for audit logging).

        Returns:
            CompletenessProof with all verification data.

        Raises:
            ProofGenerationError: If proof generation fails.

        Constitutional Reference:
            - FR57: Cryptographic proof of completeness
        """
        now = self._time.now()
        proof_id = uuid4()

        # Get all events
        events = await self._get_all_events()

        # Generate hash chain proof
        hash_chain_proof = self._verify_hash_chain(events)

        # Check for chain breaks
        if not hash_chain_proof.chain_valid:
            raise ProofGenerationError(
                "Hash chain verification failed - ledger may be corrupted"
            )

        # Compute Merkle root
        merkle_root = self._compute_merkle_root(events)

        # Determine latest sequence
        latest_sequence = events[-1].sequence if events else 0

        proof = CompletenessProof(
            proof_id=proof_id,
            generated_at=now,
            hash_chain_proof=hash_chain_proof,
            merkle_root=merkle_root,
            total_events=len(events),
            latest_sequence=latest_sequence,
            algorithm=hash_chain_proof.algorithm,
            verification_instructions=DEFAULT_VERIFICATION_INSTRUCTIONS,
        )

        # Emit audit event
        await self._emit_proof_generated_event(
            proof_id=proof_id,
            requester_id=requester_id,
            generated_at=now,
            total_events=len(events),
            merkle_root=merkle_root,
            chain_valid=hash_chain_proof.chain_valid,
        )

        return proof

    async def generate_hash_chain_proof(self) -> HashChainProof:
        """Generate proof of hash chain integrity.

        Verifies that each event correctly links to the previous
        via cryptographic hash.

        Returns:
            HashChainProof with verification details.

        Raises:
            ProofGenerationError: If verification fails.
        """
        events = await self._get_all_events()
        return self._verify_hash_chain(events)

    async def generate_merkle_proof_for_event(
        self,
        event_id: UUID,
    ) -> MerkleProof:
        """Generate Merkle proof-of-inclusion for specific event.

        Creates a proof that the specified event is included in
        the ledger's Merkle tree.

        Args:
            event_id: UUID of the event to prove inclusion for.

        Returns:
            MerkleProof with witness path for verification.

        Raises:
            ProofGenerationError: If event not found.
        """
        # Get all events
        events = await self._get_all_events()

        if not events:
            raise ProofGenerationError("Cannot generate proof from empty ledger")

        # Find event index
        event_index = None
        target_event = None
        for i, event in enumerate(events):
            if event.event_id == event_id:
                event_index = i
                target_event = event
                break

        if event_index is None or target_event is None:
            raise ProofGenerationError(f"Event {event_id} not found in ledger")

        # Detect algorithm from events
        algorithm = self._detect_algorithm(events[0].event.hash)

        # Build Merkle tree and generate proof
        event_hashes = [e.event.hash for e in events]
        tree = MerkleTree(event_hashes, algorithm)

        return tree.generate_proof(
            leaf_index=event_index,
            event_id=event_id,
            epoch=0,  # Single epoch for simplicity
        )

    async def generate_merkle_proof_for_sequence(
        self,
        sequence: int,
    ) -> MerkleProof:
        """Generate Merkle proof-of-inclusion by sequence number.

        Args:
            sequence: Ledger sequence number of the event.

        Returns:
            MerkleProof with witness path for verification.

        Raises:
            ProofGenerationError: If sequence not found.
        """
        # Get all events
        events = await self._get_all_events()

        if not events:
            raise ProofGenerationError("Cannot generate proof from empty ledger")

        # Find event by sequence
        event_index = None
        target_event = None
        for i, event in enumerate(events):
            if event.sequence == sequence:
                event_index = i
                target_event = event
                break

        if event_index is None or target_event is None:
            raise ProofGenerationError(f"Sequence {sequence} not found in ledger")

        # Detect algorithm from events
        algorithm = self._detect_algorithm(events[0].event.hash)

        # Build Merkle tree and generate proof
        event_hashes = [e.event.hash for e in events]
        tree = MerkleTree(event_hashes, algorithm)

        return tree.generate_proof(
            leaf_index=event_index,
            event_id=target_event.event_id,
            epoch=0,  # Single epoch for simplicity
        )

    def verify_completeness_proof(
        self,
        proof: CompletenessProof,
        events: list[PersistedGovernanceEvent],
    ) -> bool:
        """Verify a completeness proof against event data.

        This method verifies that:
        1. Hash chain in proof matches computed chain
        2. Merkle root matches computed root from events
        3. Event counts match

        This is a sync method - no I/O required. Pure computation.

        Args:
            proof: The CompletenessProof to verify.
            events: List of PersistedGovernanceEvent to verify against.

        Returns:
            True if proof is valid, False otherwise.
        """
        # Verify event count
        if len(events) != proof.total_events:
            return False

        # Verify hash chain
        computed_chain_proof = self._verify_hash_chain(events)
        if not computed_chain_proof.chain_valid:
            return False

        # Verify chain proof matches
        if computed_chain_proof.genesis_hash != proof.hash_chain_proof.genesis_hash:
            return False
        if computed_chain_proof.latest_hash != proof.hash_chain_proof.latest_hash:
            return False

        # Verify Merkle root
        computed_root = self._compute_merkle_root(events)
        return computed_root == proof.merkle_root

    def verify_merkle_proof(
        self,
        proof: MerkleProof,
    ) -> MerkleVerificationResult:
        """Verify a Merkle proof.

        This is a sync method - no I/O required. Pure computation.
        Delegates to the standalone verify_merkle_proof function.

        Args:
            proof: The MerkleProof to verify.

        Returns:
            MerkleVerificationResult with verification details.
        """
        return verify_merkle_proof(proof)

    def verify_hash_chain(
        self,
        events: list[PersistedGovernanceEvent],
    ) -> HashChainProof:
        """Verify hash chain for a list of events.

        This is a sync method - no I/O required. Pure computation.

        Args:
            events: List of PersistedGovernanceEvent to verify.

        Returns:
            HashChainProof with verification results.
        """
        return self._verify_hash_chain(events)

    def _verify_hash_chain(
        self,
        events: list[PersistedGovernanceEvent],
    ) -> HashChainProof:
        """Verify hash chain and return proof.

        Args:
            events: Events to verify in sequence order.

        Returns:
            HashChainProof with verification results.
        """
        if not events:
            return HashChainProof(
                genesis_hash="",
                latest_hash="",
                total_events=0,
                algorithm=DEFAULT_ALGORITHM,
                chain_valid=True,
                first_sequence=0,
                last_sequence=0,
            )

        # Detect algorithm from first event
        algorithm = self._detect_algorithm(events[0].event.hash)

        # Verify genesis event
        genesis = events[0]
        if not self._is_valid_genesis_prev_hash(genesis.event.prev_hash):
            return HashChainProof(
                genesis_hash=genesis.event.hash,
                latest_hash=events[-1].event.hash,
                total_events=len(events),
                algorithm=algorithm,
                chain_valid=False,
                first_sequence=events[0].sequence,
                last_sequence=events[-1].sequence,
            )

        # Verify chain links
        chain_valid = True
        for i in range(1, len(events)):
            prev_event = events[i - 1]
            curr_event = events[i]

            # Verify prev_hash links correctly
            if curr_event.event.prev_hash != prev_event.event.hash:
                chain_valid = False
                break

            # Verify sequence is continuous
            if curr_event.sequence != prev_event.sequence + 1:
                chain_valid = False
                break

        return HashChainProof(
            genesis_hash=events[0].event.hash,
            latest_hash=events[-1].event.hash,
            total_events=len(events),
            algorithm=algorithm,
            chain_valid=chain_valid,
            first_sequence=events[0].sequence,
            last_sequence=events[-1].sequence,
        )

    def _compute_merkle_root(
        self,
        events: list[PersistedGovernanceEvent],
    ) -> str:
        """Compute Merkle root for events.

        Args:
            events: Events to include in tree.

        Returns:
            Algorithm-prefixed Merkle root hash.
        """
        if not events:
            return f"{DEFAULT_ALGORITHM}:empty"

        # Detect algorithm from events to maintain consistency
        algorithm = self._detect_algorithm(events[0].event.hash)

        event_hashes = [e.event.hash for e in events]
        return compute_merkle_root(event_hashes, algorithm)

    def _is_valid_genesis_prev_hash(self, prev_hash: str) -> bool:
        """Check if a prev_hash is valid for genesis event.

        Genesis event should have:
        - Empty string, or
        - All zeros hash (with or without algorithm prefix)

        Args:
            prev_hash: The prev_hash to check.

        Returns:
            True if valid for genesis, False otherwise.
        """
        if not prev_hash:
            return True

        # Check for all-zeros hash
        if prev_hash.startswith("0" * 64):
            return True

        # Check for prefixed all-zeros
        if ":" in prev_hash:
            _, hash_part = prev_hash.split(":", 1)
            if hash_part.startswith("0" * 64):
                return True

        return False

    def _detect_algorithm(self, hash_value: str) -> str:
        """Detect algorithm from hash format.

        Args:
            hash_value: Hash string (e.g., "blake3:abc123").

        Returns:
            Algorithm name.
        """
        if ":" in hash_value:
            prefix = hash_value.split(":", 1)[0]
            return prefix.lower()
        return DEFAULT_ALGORITHM

    async def _get_all_events(self) -> list[PersistedGovernanceEvent]:
        """Get all events from the ledger.

        Returns:
            List of all events in sequence order.
        """
        from src.application.ports.governance.ledger_port import LedgerReadOptions

        total = await self._ledger.count_events()

        if total == 0:
            return []

        all_events: list[PersistedGovernanceEvent] = []
        batch_size = 10000
        offset = 0

        while len(all_events) < total:
            options = LedgerReadOptions(
                limit=batch_size,
                offset=offset,
            )
            batch = await self._ledger.read_events(options)
            if not batch:
                break
            all_events.extend(batch)
            offset += batch_size

        return all_events

    async def _emit_proof_generated_event(
        self,
        proof_id: UUID,
        requester_id: UUID,
        generated_at: datetime,
        total_events: int,
        merkle_root: str,
        chain_valid: bool,
    ) -> None:
        """Emit audit event for proof generation.

        Args:
            proof_id: ID of the generated proof.
            requester_id: Who requested the proof.
            generated_at: When the proof was generated.
            total_events: Number of events in the ledger.
            merkle_root: Computed Merkle root.
            chain_valid: Whether hash chain is valid.
        """
        await self._event_emitter.emit(
            event_type=PROOF_GENERATED_EVENT,
            actor=str(requester_id),
            payload={
                "proof_id": str(proof_id),
                "requester_id": str(requester_id),
                "generated_at": generated_at.isoformat(),
                "total_events": total_events,
                "merkle_root": merkle_root,
                "chain_valid": chain_valid,
            },
        )
