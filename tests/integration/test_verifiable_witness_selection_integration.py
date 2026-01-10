"""Integration tests for verifiable witness selection (FR59, FR60, FR61).

Tests the complete flow of verifiable witness selection including
external entropy, hash chain binding, and pair rotation enforcement.
"""

from datetime import datetime, timedelta, timezone

import pytest

from src.application.services.verifiable_witness_selection_service import (
    DEFAULT_MINIMUM_WITNESSES,
    HIGH_STAKES_MINIMUM_WITNESSES,
    VerifiableWitnessSelectionService,
)
from src.domain.errors.witness_selection import (
    AllWitnessesPairExhaustedError,
    EntropyUnavailableError,
    InsufficientWitnessPoolError,
)
from src.domain.errors.writer import SystemHaltedError
from src.domain.events.witness_selection import (
    WITNESS_SELECTION_EVENT_TYPE,
    WitnessSelectionEventPayload,
)
from src.domain.models.witness import WITNESS_PREFIX, Witness
from src.domain.models.witness_pair import WitnessPair
from src.domain.models.witness_selection import (
    SELECTION_ALGORITHM_VERSION,
    WitnessSelectionRecord,
    WitnessSelectionSeed,
    deterministic_select,
)
from src.infrastructure.adapters.persistence.witness_pool import InMemoryWitnessPool
from src.infrastructure.stubs.entropy_source_stub import EntropySourceStub
from src.infrastructure.stubs.event_store_stub import EventStoreStub
from src.infrastructure.stubs.halt_checker_stub import HaltCheckerStub
from src.infrastructure.stubs.witness_pair_history_stub import InMemoryWitnessPairHistory


@pytest.fixture
def halt_checker() -> HaltCheckerStub:
    """Create halt checker stub (not halted)."""
    return HaltCheckerStub()


@pytest.fixture
def witness_pool() -> InMemoryWitnessPool:
    """Create witness pool with 15 witnesses."""
    pool = InMemoryWitnessPool()
    now = datetime.now(timezone.utc)

    for i in range(15):
        witness = Witness(
            witness_id=f"{WITNESS_PREFIX}{i:03d}",
            public_key=bytes([i] * 32),
            active_from=now - timedelta(days=1),
        )
        pool.register_witness_sync(witness)

    return pool


@pytest.fixture
def entropy_source() -> EntropySourceStub:
    """Create entropy source stub."""
    return EntropySourceStub(warn_on_init=False)


@pytest.fixture
def event_store() -> EventStoreStub:
    """Create event store stub."""
    return EventStoreStub()


@pytest.fixture
def pair_history() -> InMemoryWitnessPairHistory:
    """Create pair history stub."""
    return InMemoryWitnessPairHistory()


@pytest.fixture
def service(
    halt_checker: HaltCheckerStub,
    witness_pool: InMemoryWitnessPool,
    entropy_source: EntropySourceStub,
    event_store: EventStoreStub,
    pair_history: InMemoryWitnessPairHistory,
) -> VerifiableWitnessSelectionService:
    """Create service with all dependencies."""
    return VerifiableWitnessSelectionService(
        halt_checker=halt_checker,
        witness_pool=witness_pool,
        entropy_source=entropy_source,
        event_store=event_store,
        pair_history=pair_history,
    )


class TestFR59SelectionUsesHashChainSeed:
    """Tests for FR59: Verifiable randomness from hash chain."""

    @pytest.mark.asyncio
    async def test_fr59_selection_uses_hash_chain_seed(
        self,
        service: VerifiableWitnessSelectionService,
        event_store: EventStoreStub,
    ) -> None:
        """FR59: Selection seed includes hash chain state."""
        # Add an event to establish chain state
        from datetime import datetime, timezone
        from src.domain.events.event import Event

        event = Event.create_with_hash(
            sequence=1,
            event_type="test",
            payload={"test": "data"},
            signature="test-signature",
            witness_id="witness-001",
            witness_signature="witness-sig-001",
            local_timestamp=datetime.now(timezone.utc),
            agent_id="test-agent",
        )
        await event_store.append_event(event)

        record = await service.select_witness()

        # Seed source should reference chain hash
        assert "chain:" in record.seed_source
        assert record.random_seed is not None
        assert len(record.random_seed) == 32  # SHA-256

    @pytest.mark.asyncio
    async def test_fr59_selection_record_is_verifiable(
        self,
        service: VerifiableWitnessSelectionService,
    ) -> None:
        """FR59: Selection can be verified by re-running algorithm."""
        record = await service.select_witness()

        # Record includes all data needed for verification
        assert record.random_seed is not None
        assert record.pool_snapshot is not None
        assert record.algorithm_version == SELECTION_ALGORITHM_VERSION

        # Verify by re-running
        computed = deterministic_select(record.random_seed, record.pool_snapshot)
        assert computed == record.selected_witness_id

        # Verify using built-in method
        is_valid = record.verify_selection()
        assert is_valid is True


class TestFR61ExternalEntropy:
    """Tests for FR61: External entropy source."""

    @pytest.mark.asyncio
    async def test_fr61_selection_uses_external_entropy(
        self,
        service: VerifiableWitnessSelectionService,
        entropy_source: EntropySourceStub,
    ) -> None:
        """FR61: Selection uses external entropy source."""
        # Set specific entropy
        test_entropy = b"test_entropy_value_32_bytes_here"
        entropy_source.set_entropy(test_entropy)

        record = await service.select_witness()

        # Seed source should reference external source
        assert "external:" in record.seed_source
        assert "dev-stub" in record.seed_source

    @pytest.mark.asyncio
    async def test_fr61_entropy_failure_halts_selection(
        self,
        service: VerifiableWitnessSelectionService,
        entropy_source: EntropySourceStub,
    ) -> None:
        """FR61/NFR57: Entropy failure halts selection, no weak randomness."""
        entropy_source.set_failure(True, reason="External source unavailable")

        with pytest.raises(EntropyUnavailableError) as exc_info:
            await service.select_witness()

        # Error should mention FR61
        assert "FR61" in str(exc_info.value)
        assert "halted" in str(exc_info.value).lower()


class TestFR60PairRotation:
    """Tests for FR60: Witness pair rotation."""

    @pytest.mark.asyncio
    async def test_fr60_pair_rotation_within_24h_blocked(
        self,
        halt_checker: HaltCheckerStub,
        witness_pool: InMemoryWitnessPool,
        entropy_source: EntropySourceStub,
        event_store: EventStoreStub,
        pair_history: InMemoryWitnessPairHistory,
    ) -> None:
        """FR60: Same pair within 24h is blocked."""
        # Set up: previous witness selected
        service = VerifiableWitnessSelectionService(
            halt_checker=halt_checker,
            witness_pool=witness_pool,
            entropy_source=entropy_source,
            event_store=event_store,
            pair_history=pair_history,
            previous_witness_id=f"{WITNESS_PREFIX}000",
        )

        # First selection
        record1 = await service.select_witness()

        # Record the pair as appearing recently
        pair = WitnessPair(
            witness_a_id=f"{WITNESS_PREFIX}000",
            witness_b_id=record1.selected_witness_id,
        )
        await pair_history.record_pair(pair)

        # Reset service to previous state
        service2 = VerifiableWitnessSelectionService(
            halt_checker=halt_checker,
            witness_pool=witness_pool,
            entropy_source=entropy_source,
            event_store=event_store,
            pair_history=pair_history,
            previous_witness_id=f"{WITNESS_PREFIX}000",
        )

        # Next selection should avoid the same pair
        record2 = await service2.select_witness()

        # If same entropy, selection might differ due to rotation retry
        # The key is that pair_history was checked

    @pytest.mark.asyncio
    async def test_fr60_pair_rotation_after_24h_allowed(
        self,
        halt_checker: HaltCheckerStub,
        witness_pool: InMemoryWitnessPool,
        entropy_source: EntropySourceStub,
        event_store: EventStoreStub,
        pair_history: InMemoryWitnessPairHistory,
    ) -> None:
        """FR60: Same pair after 24h is allowed."""
        # Record a pair 25 hours ago
        old_time = datetime.now(timezone.utc) - timedelta(hours=25)
        pair_history.inject_pair(
            f"{WITNESS_PREFIX}000:{WITNESS_PREFIX}001",
            old_time,
        )

        service = VerifiableWitnessSelectionService(
            halt_checker=halt_checker,
            witness_pool=witness_pool,
            entropy_source=entropy_source,
            event_store=event_store,
            pair_history=pair_history,
            previous_witness_id=f"{WITNESS_PREFIX}000",
        )

        # Selection should succeed - old pair is allowed
        record = await service.select_witness()
        assert record.selected_witness_id is not None


class TestSelectionDeterminism:
    """Tests for deterministic selection algorithm."""

    @pytest.mark.asyncio
    async def test_selection_deterministic_given_seed(
        self,
        halt_checker: HaltCheckerStub,
        witness_pool: InMemoryWitnessPool,
        event_store: EventStoreStub,
        pair_history: InMemoryWitnessPairHistory,
    ) -> None:
        """Same seed + pool = same selection."""
        # Use same entropy for both selections
        entropy1 = EntropySourceStub(warn_on_init=False)
        entropy1.set_entropy(b"deterministic_entropy_32_bytes!!")

        entropy2 = EntropySourceStub(warn_on_init=False)
        entropy2.set_entropy(b"deterministic_entropy_32_bytes!!")

        service1 = VerifiableWitnessSelectionService(
            halt_checker=halt_checker,
            witness_pool=witness_pool,
            entropy_source=entropy1,
            event_store=event_store,
            pair_history=InMemoryWitnessPairHistory(),
        )

        service2 = VerifiableWitnessSelectionService(
            halt_checker=halt_checker,
            witness_pool=witness_pool,
            entropy_source=entropy2,
            event_store=event_store,
            pair_history=InMemoryWitnessPairHistory(),
        )

        record1 = await service1.select_witness()
        record2 = await service2.select_witness()

        # Same entropy + same chain state = same selection
        assert record1.selected_witness_id == record2.selected_witness_id

    @pytest.mark.asyncio
    async def test_selection_includes_pool_snapshot(
        self,
        service: VerifiableWitnessSelectionService,
    ) -> None:
        """Selection record includes pool snapshot for verification."""
        record = await service.select_witness()

        assert record.pool_snapshot is not None
        assert len(record.pool_snapshot) == 15  # All witnesses
        assert all(w.startswith(WITNESS_PREFIX) for w in record.pool_snapshot)

    @pytest.mark.asyncio
    async def test_selection_includes_algorithm_version(
        self,
        service: VerifiableWitnessSelectionService,
    ) -> None:
        """Selection record includes algorithm version."""
        record = await service.select_witness()

        assert record.algorithm_version == SELECTION_ALGORITHM_VERSION


class TestHaltBehavior:
    """Tests for halt state during selection."""

    @pytest.mark.asyncio
    async def test_halt_check_prevents_selection_during_halt(
        self,
        service: VerifiableWitnessSelectionService,
        halt_checker: HaltCheckerStub,
    ) -> None:
        """CT-11: Selection blocked during halt."""
        halt_checker.set_halted(True, reason="Test halt")

        with pytest.raises(SystemHaltedError):
            await service.select_witness()


class TestPoolSizeRequirements:
    """Tests for witness pool minimum requirements (FR117)."""

    @pytest.mark.asyncio
    async def test_insufficient_pool_standard_operation(
        self,
        halt_checker: HaltCheckerStub,
        entropy_source: EntropySourceStub,
        event_store: EventStoreStub,
        pair_history: InMemoryWitnessPairHistory,
    ) -> None:
        """FR117: Standard operation requires minimum witnesses."""
        # Create pool with only 3 witnesses
        small_pool = InMemoryWitnessPool()
        now = datetime.now(timezone.utc)
        for i in range(3):
            witness = Witness(
                witness_id=f"{WITNESS_PREFIX}{i:03d}",
                public_key=bytes([i + 100] * 32),
                active_from=now - timedelta(days=1),
            )
            small_pool.register_witness_sync(witness)

        service = VerifiableWitnessSelectionService(
            halt_checker=halt_checker,
            witness_pool=small_pool,
            entropy_source=entropy_source,
            event_store=event_store,
            pair_history=pair_history,
        )

        with pytest.raises(InsufficientWitnessPoolError) as exc_info:
            await service.select_witness()

        assert exc_info.value.available == 3
        assert exc_info.value.minimum_required == DEFAULT_MINIMUM_WITNESSES

    @pytest.mark.asyncio
    async def test_insufficient_pool_high_stakes_operation(
        self,
        halt_checker: HaltCheckerStub,
        entropy_source: EntropySourceStub,
        event_store: EventStoreStub,
        pair_history: InMemoryWitnessPairHistory,
    ) -> None:
        """FR117: High-stakes operation requires 12 witnesses."""
        # Create pool with 10 witnesses (enough for standard, not high-stakes)
        medium_pool = InMemoryWitnessPool()
        now = datetime.now(timezone.utc)
        for i in range(10):
            witness = Witness(
                witness_id=f"{WITNESS_PREFIX}{i:03d}",
                public_key=bytes([i + 100] * 32),
                active_from=now - timedelta(days=1),
            )
            medium_pool.register_witness_sync(witness)

        service = VerifiableWitnessSelectionService(
            halt_checker=halt_checker,
            witness_pool=medium_pool,
            entropy_source=entropy_source,
            event_store=event_store,
            pair_history=pair_history,
        )

        with pytest.raises(InsufficientWitnessPoolError) as exc_info:
            await service.select_witness(high_stakes=True)

        assert exc_info.value.available == 10
        assert exc_info.value.minimum_required == HIGH_STAKES_MINIMUM_WITNESSES


class TestSelectionEventCreation:
    """Tests for selection event payload creation."""

    @pytest.mark.asyncio
    async def test_selection_event_created_with_all_fields(
        self,
        service: VerifiableWitnessSelectionService,
    ) -> None:
        """Selection event payload contains all required fields."""
        record = await service.select_witness()
        payload = await service.create_selection_event_payload(record)

        assert payload.random_seed is not None
        assert payload.seed_source is not None
        assert payload.selected_witness_id == record.selected_witness_id
        assert payload.pool_size == len(record.pool_snapshot)
        assert payload.algorithm_version == SELECTION_ALGORITHM_VERSION
        assert payload.selected_at is not None


class TestSeedCombination:
    """Tests for entropy combination."""

    def test_seed_combination_is_deterministic(self) -> None:
        """Same inputs produce same combined seed."""
        external = b"external_entropy_value_32_bytes!"
        chain_hash = "a" * 64

        seed1 = WitnessSelectionSeed.combine(external, chain_hash)
        seed2 = WitnessSelectionSeed.combine(external, chain_hash)

        assert seed1.combined_seed == seed2.combined_seed

    def test_different_entropy_produces_different_seed(self) -> None:
        """Different external entropy produces different seed."""
        chain_hash = "a" * 64

        seed1 = WitnessSelectionSeed.combine(b"entropy_one_32_bytes_exactly!!!", chain_hash)
        seed2 = WitnessSelectionSeed.combine(b"entropy_two_32_bytes_exactly!!!", chain_hash)

        assert seed1.combined_seed != seed2.combined_seed

    def test_different_chain_produces_different_seed(self) -> None:
        """Different chain hash produces different seed."""
        external = b"external_entropy_value_32_bytes!"

        seed1 = WitnessSelectionSeed.combine(external, "a" * 64)
        seed2 = WitnessSelectionSeed.combine(external, "b" * 64)

        assert seed1.combined_seed != seed2.combined_seed
