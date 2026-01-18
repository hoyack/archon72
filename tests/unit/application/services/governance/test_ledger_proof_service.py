"""Unit tests for ledger proof service.

Story: consent-gov-9.2: Cryptographic Proof Generation

Tests:
- Completeness proof generation (AC1)
- Hash chain verification (AC2)
- Merkle tree proof-of-inclusion (AC3)
- Independent verification (AC4)
- Event emission (AC5)
- Root hash and witness path (AC6)
- Verification without trusted party (AC7)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any
from uuid import UUID, uuid4

import pytest

from src.application.services.governance.ledger_proof_service import (
    PROOF_GENERATED_EVENT,
    LedgerProofService,
)
from src.domain.governance.audit.completeness_proof import (
    CompletenessProof,
    HashChainProof,
    ProofGenerationError,
)
from src.domain.governance.events.merkle_tree import (
    MerkleProof,
    verify_merkle_proof,
)

# Use sha256 for testing since blake3 may not be available
TEST_ALGORITHM = "sha256"


@dataclass(frozen=True)
class FakeEventMetadata:
    """Fake event metadata for testing."""

    event_id: UUID
    event_type: str
    timestamp: datetime
    actor_id: str
    schema_version: str
    trace_id: str
    prev_hash: str
    hash: str


@dataclass(frozen=True)
class FakeGovernanceEvent:
    """Fake governance event for testing."""

    metadata: FakeEventMetadata
    payload: MappingProxyType[str, Any]

    @property
    def event_id(self) -> UUID:
        return self.metadata.event_id

    @property
    def event_type(self) -> str:
        return self.metadata.event_type

    @property
    def timestamp(self) -> datetime:
        return self.metadata.timestamp

    @property
    def actor_id(self) -> str:
        return self.metadata.actor_id

    @property
    def schema_version(self) -> str:
        return self.metadata.schema_version

    @property
    def trace_id(self) -> str:
        return self.metadata.trace_id

    @property
    def prev_hash(self) -> str:
        return self.metadata.prev_hash

    @property
    def hash(self) -> str:
        return self.metadata.hash


@dataclass(frozen=True)
class FakePersistedGovernanceEvent:
    """Fake persisted event for testing."""

    event: FakeGovernanceEvent
    sequence: int

    @property
    def event_id(self) -> UUID:
        return self.event.event_id

    @property
    def event_type(self) -> str:
        return self.event.event_type

    @property
    def branch(self) -> str:
        return self.event.event_type.split(".")[0]

    @property
    def timestamp(self) -> datetime:
        return self.event.timestamp

    @property
    def actor_id(self) -> str:
        return self.event.actor_id


def create_fake_event(
    sequence: int,
    actor_id: str | None = None,
    payload: dict[str, Any] | None = None,
    prev_hash: str | None = None,
    event_hash: str | None = None,
) -> FakePersistedGovernanceEvent:
    """Create a fake persisted event for testing."""
    event_id = uuid4()

    # For genesis event (sequence 1), use zeros as prev_hash
    if prev_hash is None:
        prev_hash = (
            f"{TEST_ALGORITHM}:{'0' * 64}"
            if sequence == 1
            else f"{TEST_ALGORITHM}:{'a' * 64}"
        )

    # Generate unique hash based on sequence for deterministic testing
    if event_hash is None:
        event_hash = f"{TEST_ALGORITHM}:{sequence:064x}"

    metadata = FakeEventMetadata(
        event_id=event_id,
        event_type="test.event.created",
        timestamp=datetime.now(timezone.utc),
        actor_id=actor_id or str(uuid4()),
        schema_version="1.0.0",
        trace_id=str(uuid4()),
        prev_hash=prev_hash,
        hash=event_hash,
    )
    event = FakeGovernanceEvent(
        metadata=metadata,
        payload=MappingProxyType(payload or {}),
    )
    return FakePersistedGovernanceEvent(event=event, sequence=sequence)


def create_linked_events(count: int) -> list[FakePersistedGovernanceEvent]:
    """Create events with properly linked hash chain."""
    events: list[FakePersistedGovernanceEvent] = []

    for i in range(1, count + 1):
        if i == 1:
            # Genesis event
            prev_hash = f"{TEST_ALGORITHM}:{'0' * 64}"
        else:
            # Link to previous event's hash
            prev_hash = events[i - 2].event.hash

        event_hash = f"{TEST_ALGORITHM}:{i:064x}"
        events.append(create_fake_event(i, prev_hash=prev_hash, event_hash=event_hash))

    return events


class FakeLedgerPort:
    """Fake ledger port for testing."""

    def __init__(
        self, events: list[FakePersistedGovernanceEvent] | None = None
    ) -> None:
        self.events = events or []

    async def count_events(self, options=None) -> int:
        return len(self.events)

    async def read_events(self, options=None) -> list[FakePersistedGovernanceEvent]:
        if options is None:
            return self.events
        offset = getattr(options, "offset", 0)
        limit = getattr(options, "limit", 100)
        return self.events[offset : offset + limit]


class FakeEventEmitter:
    """Fake event emitter for testing."""

    def __init__(self) -> None:
        self.emitted: list[dict[str, Any]] = []

    async def emit(
        self,
        event_type: str,
        actor: str,
        payload: dict[str, Any],
    ) -> None:
        self.emitted.append(
            {
                "event_type": event_type,
                "actor": actor,
                "payload": payload,
            }
        )


class FakeTimeAuthority:
    """Fake time authority for testing."""

    def __init__(self, fixed_time: datetime | None = None) -> None:
        self._time = fixed_time or datetime.now(timezone.utc)

    def now(self) -> datetime:
        return self._time


@pytest.fixture
def time_authority() -> FakeTimeAuthority:
    """Provide a fake time authority."""
    return FakeTimeAuthority()


@pytest.fixture
def event_emitter() -> FakeEventEmitter:
    """Provide a fake event emitter."""
    return FakeEventEmitter()


@pytest.fixture
def empty_ledger() -> FakeLedgerPort:
    """Provide an empty ledger."""
    return FakeLedgerPort([])


@pytest.fixture
def ledger_with_events() -> FakeLedgerPort:
    """Provide a ledger with properly linked events."""
    events = create_linked_events(10)
    return FakeLedgerPort(events)


@pytest.fixture
def ledger_with_broken_chain() -> FakeLedgerPort:
    """Provide a ledger with broken hash chain."""
    events = [
        create_fake_event(
            1,
            prev_hash=f"{TEST_ALGORITHM}:{'0' * 64}",
            event_hash=f"{TEST_ALGORITHM}:{'1' * 64}",
        ),
        create_fake_event(
            2,
            prev_hash=f"{TEST_ALGORITHM}:{'wrong' * 16}",  # Wrong prev_hash
            event_hash=f"{TEST_ALGORITHM}:{'2' * 64}",
        ),
    ]
    return FakeLedgerPort(events)


@pytest.fixture
def proof_service(
    empty_ledger: FakeLedgerPort,
    event_emitter: FakeEventEmitter,
    time_authority: FakeTimeAuthority,
) -> LedgerProofService:
    """Provide a proof service with empty ledger."""
    return LedgerProofService(
        ledger_port=empty_ledger,
        merkle_port=None,
        event_emitter=event_emitter,
        time_authority=time_authority,
    )


class TestCompletenessProofGeneration:
    """Tests for completeness proof generation (AC1)."""

    async def test_completeness_proof_generated(
        self,
        ledger_with_events: FakeLedgerPort,
        event_emitter: FakeEventEmitter,
        time_authority: FakeTimeAuthority,
    ) -> None:
        """Completeness proof is generated successfully."""
        service = LedgerProofService(
            ledger_port=ledger_with_events,
            merkle_port=None,
            event_emitter=event_emitter,
            time_authority=time_authority,
        )
        requester_id = uuid4()

        proof = await service.generate_completeness_proof(requester_id)

        assert proof is not None
        assert isinstance(proof, CompletenessProof)
        assert proof.proof_id is not None
        assert proof.total_events == 10

    async def test_completeness_proof_has_hash_chain_proof(
        self,
        ledger_with_events: FakeLedgerPort,
        event_emitter: FakeEventEmitter,
        time_authority: FakeTimeAuthority,
    ) -> None:
        """Completeness proof includes hash chain proof."""
        service = LedgerProofService(
            ledger_port=ledger_with_events,
            merkle_port=None,
            event_emitter=event_emitter,
            time_authority=time_authority,
        )
        requester_id = uuid4()

        proof = await service.generate_completeness_proof(requester_id)

        assert proof.hash_chain_proof is not None
        assert proof.hash_chain_proof.chain_valid is True

    async def test_completeness_proof_has_merkle_root(
        self,
        ledger_with_events: FakeLedgerPort,
        event_emitter: FakeEventEmitter,
        time_authority: FakeTimeAuthority,
    ) -> None:
        """Completeness proof includes Merkle root."""
        service = LedgerProofService(
            ledger_port=ledger_with_events,
            merkle_port=None,
            event_emitter=event_emitter,
            time_authority=time_authority,
        )
        requester_id = uuid4()

        proof = await service.generate_completeness_proof(requester_id)

        assert proof.merkle_root is not None
        assert proof.merkle_root.startswith(f"{TEST_ALGORITHM}:")

    async def test_empty_ledger_proof(
        self,
        proof_service: LedgerProofService,
    ) -> None:
        """Completeness proof works for empty ledger."""
        requester_id = uuid4()

        proof = await proof_service.generate_completeness_proof(requester_id)

        assert proof.total_events == 0
        assert proof.is_empty
        assert proof.hash_chain_proof.chain_valid is True

    async def test_completeness_proof_has_verification_instructions(
        self,
        ledger_with_events: FakeLedgerPort,
        event_emitter: FakeEventEmitter,
        time_authority: FakeTimeAuthority,
    ) -> None:
        """Completeness proof includes verification instructions."""
        service = LedgerProofService(
            ledger_port=ledger_with_events,
            merkle_port=None,
            event_emitter=event_emitter,
            time_authority=time_authority,
        )
        requester_id = uuid4()

        proof = await service.generate_completeness_proof(requester_id)

        assert proof.verification_instructions is not None
        assert len(proof.verification_instructions) > 0
        assert "HASH CHAIN" in proof.verification_instructions.upper()


class TestHashChainVerification:
    """Tests for hash chain verification (AC2)."""

    async def test_valid_chain_passes_verification(
        self,
        ledger_with_events: FakeLedgerPort,
        event_emitter: FakeEventEmitter,
        time_authority: FakeTimeAuthority,
    ) -> None:
        """Valid hash chain passes verification."""
        service = LedgerProofService(
            ledger_port=ledger_with_events,
            merkle_port=None,
            event_emitter=event_emitter,
            time_authority=time_authority,
        )

        chain_proof = await service.generate_hash_chain_proof()

        assert chain_proof.chain_valid is True

    async def test_chain_has_genesis_hash(
        self,
        ledger_with_events: FakeLedgerPort,
        event_emitter: FakeEventEmitter,
        time_authority: FakeTimeAuthority,
    ) -> None:
        """Chain proof includes genesis hash."""
        service = LedgerProofService(
            ledger_port=ledger_with_events,
            merkle_port=None,
            event_emitter=event_emitter,
            time_authority=time_authority,
        )

        chain_proof = await service.generate_hash_chain_proof()

        assert chain_proof.genesis_hash is not None
        assert chain_proof.genesis_hash.startswith(f"{TEST_ALGORITHM}:")

    async def test_chain_has_latest_hash(
        self,
        ledger_with_events: FakeLedgerPort,
        event_emitter: FakeEventEmitter,
        time_authority: FakeTimeAuthority,
    ) -> None:
        """Chain proof includes latest hash."""
        service = LedgerProofService(
            ledger_port=ledger_with_events,
            merkle_port=None,
            event_emitter=event_emitter,
            time_authority=time_authority,
        )

        chain_proof = await service.generate_hash_chain_proof()

        assert chain_proof.latest_hash is not None
        assert chain_proof.latest_hash.startswith(f"{TEST_ALGORITHM}:")

    async def test_broken_chain_fails_verification(
        self,
        ledger_with_broken_chain: FakeLedgerPort,
        event_emitter: FakeEventEmitter,
        time_authority: FakeTimeAuthority,
    ) -> None:
        """Broken hash chain fails verification."""
        service = LedgerProofService(
            ledger_port=ledger_with_broken_chain,
            merkle_port=None,
            event_emitter=event_emitter,
            time_authority=time_authority,
        )

        chain_proof = await service.generate_hash_chain_proof()

        assert chain_proof.chain_valid is False

    async def test_broken_chain_raises_on_completeness_proof(
        self,
        ledger_with_broken_chain: FakeLedgerPort,
        event_emitter: FakeEventEmitter,
        time_authority: FakeTimeAuthority,
    ) -> None:
        """Broken chain raises error when generating completeness proof."""
        service = LedgerProofService(
            ledger_port=ledger_with_broken_chain,
            merkle_port=None,
            event_emitter=event_emitter,
            time_authority=time_authority,
        )

        with pytest.raises(
            ProofGenerationError, match="Hash chain verification failed"
        ):
            await service.generate_completeness_proof(uuid4())


class TestMerkleProof:
    """Tests for Merkle tree proof-of-inclusion (AC3)."""

    async def test_merkle_proof_for_event(
        self,
        ledger_with_events: FakeLedgerPort,
        event_emitter: FakeEventEmitter,
        time_authority: FakeTimeAuthority,
    ) -> None:
        """Merkle proof is generated for specific event."""
        service = LedgerProofService(
            ledger_port=ledger_with_events,
            merkle_port=None,
            event_emitter=event_emitter,
            time_authority=time_authority,
        )
        target_event = ledger_with_events.events[5]

        proof = await service.generate_merkle_proof_for_event(target_event.event_id)

        assert proof is not None
        assert isinstance(proof, MerkleProof)
        assert proof.event_id == target_event.event_id

    async def test_merkle_proof_for_sequence(
        self,
        ledger_with_events: FakeLedgerPort,
        event_emitter: FakeEventEmitter,
        time_authority: FakeTimeAuthority,
    ) -> None:
        """Merkle proof is generated by sequence number."""
        service = LedgerProofService(
            ledger_port=ledger_with_events,
            merkle_port=None,
            event_emitter=event_emitter,
            time_authority=time_authority,
        )

        proof = await service.generate_merkle_proof_for_sequence(5)

        assert proof is not None
        assert isinstance(proof, MerkleProof)

    async def test_merkle_proof_has_witness_path(
        self,
        ledger_with_events: FakeLedgerPort,
        event_emitter: FakeEventEmitter,
        time_authority: FakeTimeAuthority,
    ) -> None:
        """Merkle proof includes witness path (AC6)."""
        service = LedgerProofService(
            ledger_port=ledger_with_events,
            merkle_port=None,
            event_emitter=event_emitter,
            time_authority=time_authority,
        )
        target_event = ledger_with_events.events[3]

        proof = await service.generate_merkle_proof_for_event(target_event.event_id)

        assert proof.merkle_path is not None
        assert len(proof.merkle_path) > 0

    async def test_merkle_proof_has_root(
        self,
        ledger_with_events: FakeLedgerPort,
        event_emitter: FakeEventEmitter,
        time_authority: FakeTimeAuthority,
    ) -> None:
        """Merkle proof includes root hash (AC6)."""
        service = LedgerProofService(
            ledger_port=ledger_with_events,
            merkle_port=None,
            event_emitter=event_emitter,
            time_authority=time_authority,
        )
        target_event = ledger_with_events.events[0]

        proof = await service.generate_merkle_proof_for_event(target_event.event_id)

        assert proof.merkle_root is not None
        assert proof.merkle_root.startswith(f"{TEST_ALGORITHM}:")

    async def test_merkle_proof_is_verifiable(
        self,
        ledger_with_events: FakeLedgerPort,
        event_emitter: FakeEventEmitter,
        time_authority: FakeTimeAuthority,
    ) -> None:
        """Generated Merkle proof can be verified."""
        service = LedgerProofService(
            ledger_port=ledger_with_events,
            merkle_port=None,
            event_emitter=event_emitter,
            time_authority=time_authority,
        )
        target_event = ledger_with_events.events[2]

        proof = await service.generate_merkle_proof_for_event(target_event.event_id)
        result = service.verify_merkle_proof(proof)

        assert result.is_valid is True

    async def test_nonexistent_event_raises(
        self,
        ledger_with_events: FakeLedgerPort,
        event_emitter: FakeEventEmitter,
        time_authority: FakeTimeAuthority,
    ) -> None:
        """Nonexistent event raises error."""
        service = LedgerProofService(
            ledger_port=ledger_with_events,
            merkle_port=None,
            event_emitter=event_emitter,
            time_authority=time_authority,
        )
        fake_event_id = uuid4()

        with pytest.raises(ProofGenerationError, match="not found"):
            await service.generate_merkle_proof_for_event(fake_event_id)

    async def test_nonexistent_sequence_raises(
        self,
        ledger_with_events: FakeLedgerPort,
        event_emitter: FakeEventEmitter,
        time_authority: FakeTimeAuthority,
    ) -> None:
        """Nonexistent sequence raises error."""
        service = LedgerProofService(
            ledger_port=ledger_with_events,
            merkle_port=None,
            event_emitter=event_emitter,
            time_authority=time_authority,
        )

        with pytest.raises(ProofGenerationError, match="not found"):
            await service.generate_merkle_proof_for_sequence(999)

    async def test_empty_ledger_raises(
        self,
        proof_service: LedgerProofService,
    ) -> None:
        """Empty ledger raises error for Merkle proof."""
        with pytest.raises(ProofGenerationError, match="empty"):
            await proof_service.generate_merkle_proof_for_sequence(1)


class TestIndependentVerification:
    """Tests for independent verification (AC4, AC7)."""

    async def test_proof_contains_all_needed_info(
        self,
        ledger_with_events: FakeLedgerPort,
        event_emitter: FakeEventEmitter,
        time_authority: FakeTimeAuthority,
    ) -> None:
        """Proof contains everything needed for verification."""
        service = LedgerProofService(
            ledger_port=ledger_with_events,
            merkle_port=None,
            event_emitter=event_emitter,
            time_authority=time_authority,
        )
        requester_id = uuid4()

        proof = await service.generate_completeness_proof(requester_id)

        # All needed fields present
        assert proof.hash_chain_proof is not None
        assert proof.merkle_root is not None
        assert proof.verification_instructions is not None
        assert proof.total_events >= 0
        assert proof.algorithm is not None

    async def test_completeness_proof_verifiable_with_events(
        self,
        ledger_with_events: FakeLedgerPort,
        event_emitter: FakeEventEmitter,
        time_authority: FakeTimeAuthority,
    ) -> None:
        """Completeness proof can be verified with exported events."""
        service = LedgerProofService(
            ledger_port=ledger_with_events,
            merkle_port=None,
            event_emitter=event_emitter,
            time_authority=time_authority,
        )
        requester_id = uuid4()

        proof = await service.generate_completeness_proof(requester_id)
        events = ledger_with_events.events

        # Verify using sync method (no database)
        is_valid = service.verify_completeness_proof(proof, events)

        assert is_valid is True

    async def test_verification_fails_with_tampered_events(
        self,
        ledger_with_events: FakeLedgerPort,
        event_emitter: FakeEventEmitter,
        time_authority: FakeTimeAuthority,
    ) -> None:
        """Verification fails if events are tampered."""
        service = LedgerProofService(
            ledger_port=ledger_with_events,
            merkle_port=None,
            event_emitter=event_emitter,
            time_authority=time_authority,
        )
        requester_id = uuid4()

        proof = await service.generate_completeness_proof(requester_id)

        # Tamper with events (remove one)
        tampered_events = ledger_with_events.events[:-1]

        is_valid = service.verify_completeness_proof(proof, tampered_events)

        assert is_valid is False

    async def test_verification_sync_no_io(
        self,
        ledger_with_events: FakeLedgerPort,
        event_emitter: FakeEventEmitter,
        time_authority: FakeTimeAuthority,
    ) -> None:
        """Verification is synchronous (no I/O)."""
        service = LedgerProofService(
            ledger_port=ledger_with_events,
            merkle_port=None,
            event_emitter=event_emitter,
            time_authority=time_authority,
        )
        requester_id = uuid4()

        proof = await service.generate_completeness_proof(requester_id)
        events = ledger_with_events.events

        # verify_completeness_proof is sync, not async

        # Should not need event loop for verification
        is_valid = service.verify_completeness_proof(proof, events)
        assert is_valid is True

        # Also test hash chain verification is sync
        chain_proof = service.verify_hash_chain(events)
        assert chain_proof.chain_valid is True


class TestEventEmission:
    """Tests for event emission (AC5)."""

    async def test_proof_generated_event_emitted(
        self,
        ledger_with_events: FakeLedgerPort,
        event_emitter: FakeEventEmitter,
        time_authority: FakeTimeAuthority,
    ) -> None:
        """Proof generation emits audit event."""
        service = LedgerProofService(
            ledger_port=ledger_with_events,
            merkle_port=None,
            event_emitter=event_emitter,
            time_authority=time_authority,
        )
        requester_id = uuid4()

        await service.generate_completeness_proof(requester_id)

        assert len(event_emitter.emitted) == 1
        event = event_emitter.emitted[0]
        assert event["event_type"] == PROOF_GENERATED_EVENT

    async def test_event_contains_proof_id(
        self,
        ledger_with_events: FakeLedgerPort,
        event_emitter: FakeEventEmitter,
        time_authority: FakeTimeAuthority,
    ) -> None:
        """Emitted event contains proof_id."""
        service = LedgerProofService(
            ledger_port=ledger_with_events,
            merkle_port=None,
            event_emitter=event_emitter,
            time_authority=time_authority,
        )
        requester_id = uuid4()

        await service.generate_completeness_proof(requester_id)

        event = event_emitter.emitted[0]
        assert "proof_id" in event["payload"]

    async def test_event_contains_requester_id(
        self,
        ledger_with_events: FakeLedgerPort,
        event_emitter: FakeEventEmitter,
        time_authority: FakeTimeAuthority,
    ) -> None:
        """Emitted event contains requester_id."""
        service = LedgerProofService(
            ledger_port=ledger_with_events,
            merkle_port=None,
            event_emitter=event_emitter,
            time_authority=time_authority,
        )
        requester_id = uuid4()

        await service.generate_completeness_proof(requester_id)

        event = event_emitter.emitted[0]
        assert event["payload"]["requester_id"] == str(requester_id)
        assert event["actor"] == str(requester_id)

    async def test_event_contains_merkle_root(
        self,
        ledger_with_events: FakeLedgerPort,
        event_emitter: FakeEventEmitter,
        time_authority: FakeTimeAuthority,
    ) -> None:
        """Emitted event contains merkle_root."""
        service = LedgerProofService(
            ledger_port=ledger_with_events,
            merkle_port=None,
            event_emitter=event_emitter,
            time_authority=time_authority,
        )
        requester_id = uuid4()

        await service.generate_completeness_proof(requester_id)

        event = event_emitter.emitted[0]
        assert "merkle_root" in event["payload"]
        assert event["payload"]["merkle_root"].startswith(f"{TEST_ALGORITHM}:")

    async def test_event_contains_chain_valid(
        self,
        ledger_with_events: FakeLedgerPort,
        event_emitter: FakeEventEmitter,
        time_authority: FakeTimeAuthority,
    ) -> None:
        """Emitted event contains chain_valid."""
        service = LedgerProofService(
            ledger_port=ledger_with_events,
            merkle_port=None,
            event_emitter=event_emitter,
            time_authority=time_authority,
        )
        requester_id = uuid4()

        await service.generate_completeness_proof(requester_id)

        event = event_emitter.emitted[0]
        assert event["payload"]["chain_valid"] is True


class TestHashChainProofModel:
    """Tests for HashChainProof domain model."""

    def test_hash_chain_proof_empty(self) -> None:
        """Empty chain proof is valid."""
        proof = HashChainProof(
            genesis_hash="",
            latest_hash="",
            total_events=0,
            algorithm="blake3",
            chain_valid=True,
            first_sequence=0,
            last_sequence=0,
        )

        assert proof.is_empty is True
        assert proof.chain_valid is True

    def test_hash_chain_proof_non_empty(self) -> None:
        """Non-empty chain proof has hashes and sequences."""
        proof = HashChainProof(
            genesis_hash="blake3:abc123",
            latest_hash="blake3:xyz789",
            total_events=10,
            algorithm="blake3",
            chain_valid=True,
            first_sequence=1,
            last_sequence=10,
        )

        assert proof.is_empty is False
        assert proof.genesis_hash == "blake3:abc123"
        assert proof.latest_hash == "blake3:xyz789"

    def test_hash_chain_proof_validates_total_events(self) -> None:
        """Negative total_events raises error."""
        with pytest.raises(ValueError, match="total_events"):
            HashChainProof(
                genesis_hash="",
                latest_hash="",
                total_events=-1,
                algorithm="blake3",
                chain_valid=True,
            )

    def test_hash_chain_proof_validates_empty_hashes(self) -> None:
        """Empty chain must have empty hashes."""
        with pytest.raises(ValueError, match="genesis_hash"):
            HashChainProof(
                genesis_hash="blake3:abc123",
                latest_hash="",
                total_events=0,
                algorithm="blake3",
                chain_valid=True,
            )

    def test_hash_chain_proof_validates_non_empty_hashes(self) -> None:
        """Non-empty chain must have hashes."""
        with pytest.raises(ValueError, match="genesis_hash.*required"):
            HashChainProof(
                genesis_hash="",
                latest_hash="",
                total_events=5,
                algorithm="blake3",
                chain_valid=True,
                first_sequence=1,
                last_sequence=5,
            )


class TestCompletenessProofModel:
    """Tests for CompletenessProof domain model."""

    def test_completeness_proof_to_dict(
        self,
        time_authority: FakeTimeAuthority,
    ) -> None:
        """Completeness proof serializes to dict."""
        chain_proof = HashChainProof(
            genesis_hash="blake3:abc",
            latest_hash="blake3:xyz",
            total_events=10,
            algorithm="blake3",
            chain_valid=True,
            first_sequence=1,
            last_sequence=10,
        )
        proof = CompletenessProof(
            proof_id=uuid4(),
            generated_at=time_authority.now(),
            hash_chain_proof=chain_proof,
            merkle_root="blake3:merkle123",
            total_events=10,
            latest_sequence=10,
            algorithm="blake3",
            verification_instructions="Test instructions",
        )

        d = proof.to_dict()

        assert "proof_id" in d
        assert "hash_chain_proof" in d
        assert "merkle_root" in d
        assert d["total_events"] == 10

    def test_completeness_proof_is_valid(
        self,
        time_authority: FakeTimeAuthority,
    ) -> None:
        """is_valid reflects chain validity."""
        valid_chain = HashChainProof(
            genesis_hash="blake3:abc",
            latest_hash="blake3:xyz",
            total_events=5,
            algorithm="blake3",
            chain_valid=True,
            first_sequence=1,
            last_sequence=5,
        )
        proof = CompletenessProof(
            proof_id=uuid4(),
            generated_at=time_authority.now(),
            hash_chain_proof=valid_chain,
            merkle_root="blake3:root",
            total_events=5,
            latest_sequence=5,
            algorithm="blake3",
        )

        assert proof.is_valid is True

    def test_completeness_proof_validates_event_count(
        self,
        time_authority: FakeTimeAuthority,
    ) -> None:
        """total_events must match hash_chain_proof."""
        chain_proof = HashChainProof(
            genesis_hash="blake3:abc",
            latest_hash="blake3:xyz",
            total_events=10,
            algorithm="blake3",
            chain_valid=True,
            first_sequence=1,
            last_sequence=10,
        )

        with pytest.raises(ValueError, match="total_events mismatch"):
            CompletenessProof(
                proof_id=uuid4(),
                generated_at=time_authority.now(),
                hash_chain_proof=chain_proof,
                merkle_root="blake3:root",
                total_events=5,  # Mismatch!
                latest_sequence=10,
                algorithm="blake3",
            )


class TestMerkleProofVerification:
    """Tests for standalone Merkle proof verification."""

    async def test_verify_merkle_proof_standalone(
        self,
        ledger_with_events: FakeLedgerPort,
        event_emitter: FakeEventEmitter,
        time_authority: FakeTimeAuthority,
    ) -> None:
        """Merkle proof can be verified with standalone function."""
        service = LedgerProofService(
            ledger_port=ledger_with_events,
            merkle_port=None,
            event_emitter=event_emitter,
            time_authority=time_authority,
        )
        target_event = ledger_with_events.events[4]

        proof = await service.generate_merkle_proof_for_event(target_event.event_id)

        # Use standalone verification function
        result = verify_merkle_proof(proof)

        assert result.is_valid is True
        assert result.reconstructed_root == proof.merkle_root

    async def test_tampered_proof_fails_verification(
        self,
        ledger_with_events: FakeLedgerPort,
        event_emitter: FakeEventEmitter,
        time_authority: FakeTimeAuthority,
    ) -> None:
        """Tampered Merkle proof fails verification."""
        service = LedgerProofService(
            ledger_port=ledger_with_events,
            merkle_port=None,
            event_emitter=event_emitter,
            time_authority=time_authority,
        )
        target_event = ledger_with_events.events[3]

        proof = await service.generate_merkle_proof_for_event(target_event.event_id)

        # Tamper with the proof by changing the event hash
        tampered_proof = MerkleProof(
            event_id=proof.event_id,
            event_hash="blake3:tampered_hash",  # Wrong hash!
            merkle_path=proof.merkle_path,
            merkle_root=proof.merkle_root,
            epoch=proof.epoch,
            leaf_index=proof.leaf_index,
            algorithm=proof.algorithm,
        )

        result = verify_merkle_proof(tampered_proof)

        assert result.is_valid is False
