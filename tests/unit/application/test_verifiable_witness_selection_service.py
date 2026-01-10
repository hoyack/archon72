"""Unit tests for VerifiableWitnessSelectionService (FR59, FR60, FR61).

Tests the main service implementation.
"""

from datetime import datetime, timezone
from typing import Optional
from unittest.mock import AsyncMock, MagicMock

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
    WitnessSelectionVerificationError,
)
from src.domain.errors.writer import SystemHaltedError
from src.domain.models.witness_pair import WitnessPair
from src.domain.models.witness_selection import SELECTION_ALGORITHM_VERSION


@pytest.fixture
def mock_halt_checker() -> AsyncMock:
    """Create mock halt checker (not halted by default)."""
    checker = AsyncMock()
    checker.is_halted.return_value = False
    return checker


@pytest.fixture
def mock_witness_pool() -> AsyncMock:
    """Create mock witness pool with 10 witnesses."""
    pool = AsyncMock()
    witnesses = tuple(f"WITNESS:{i}" for i in range(10))
    pool.get_ordered_active_witnesses.return_value = witnesses
    pool.count_active_witnesses.return_value = len(witnesses)
    return pool


@pytest.fixture
def mock_entropy_source() -> AsyncMock:
    """Create mock entropy source."""
    source = AsyncMock()
    source.get_entropy.return_value = b"test_entropy_32_bytes_exactly!!"
    source.get_source_identifier.return_value = "test-source"
    return source


@pytest.fixture
def mock_event_store() -> AsyncMock:
    """Create mock event store with latest event."""
    store = AsyncMock()
    mock_event = MagicMock()
    mock_event.content_hash = "a" * 64
    store.get_latest_event.return_value = mock_event
    return store


@pytest.fixture
def mock_pair_history() -> AsyncMock:
    """Create mock pair history (no pairs blocked)."""
    history = AsyncMock()
    history.has_appeared_in_24h.return_value = False
    return history


@pytest.fixture
def service(
    mock_halt_checker: AsyncMock,
    mock_witness_pool: AsyncMock,
    mock_entropy_source: AsyncMock,
    mock_event_store: AsyncMock,
    mock_pair_history: AsyncMock,
) -> VerifiableWitnessSelectionService:
    """Create service with all mocked dependencies."""
    return VerifiableWitnessSelectionService(
        halt_checker=mock_halt_checker,
        witness_pool=mock_witness_pool,
        entropy_source=mock_entropy_source,
        event_store=mock_event_store,
        pair_history=mock_pair_history,
    )


class TestSelectWitness:
    """Tests for select_witness method."""

    @pytest.mark.asyncio
    async def test_select_witness_returns_valid_record(
        self,
        service: VerifiableWitnessSelectionService,
    ) -> None:
        """select_witness returns a WitnessSelectionRecord."""
        record = await service.select_witness()

        assert record is not None
        assert record.selected_witness_id.startswith("WITNESS:")
        assert record.algorithm_version == SELECTION_ALGORITHM_VERSION
        assert len(record.random_seed) == 32  # SHA-256 output
        assert len(record.pool_snapshot) == 10

    @pytest.mark.asyncio
    async def test_select_witness_uses_external_entropy(
        self,
        service: VerifiableWitnessSelectionService,
        mock_entropy_source: AsyncMock,
    ) -> None:
        """select_witness calls entropy source."""
        await service.select_witness()

        mock_entropy_source.get_entropy.assert_called_once()
        mock_entropy_source.get_source_identifier.assert_called_once()

    @pytest.mark.asyncio
    async def test_select_witness_uses_hash_chain(
        self,
        service: VerifiableWitnessSelectionService,
        mock_event_store: AsyncMock,
    ) -> None:
        """select_witness uses hash chain from event store."""
        record = await service.select_witness()

        mock_event_store.get_latest_event.assert_called_once()
        assert "chain:" in record.seed_source

    @pytest.mark.asyncio
    async def test_select_witness_halt_check_first(
        self,
        service: VerifiableWitnessSelectionService,
        mock_halt_checker: AsyncMock,
    ) -> None:
        """select_witness checks halt state first."""
        mock_halt_checker.is_halted.return_value = True

        with pytest.raises(SystemHaltedError):
            await service.select_witness()

        mock_halt_checker.is_halted.assert_called_once()

    @pytest.mark.asyncio
    async def test_select_witness_entropy_failure_raises_error(
        self,
        service: VerifiableWitnessSelectionService,
        mock_entropy_source: AsyncMock,
    ) -> None:
        """select_witness raises EntropyUnavailableError on entropy failure."""
        mock_entropy_source.get_entropy.side_effect = Exception("Network error")

        with pytest.raises(EntropyUnavailableError) as exc_info:
            await service.select_witness()

        assert "Network error" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_select_witness_insufficient_pool_raises_error(
        self,
        service: VerifiableWitnessSelectionService,
        mock_witness_pool: AsyncMock,
    ) -> None:
        """select_witness raises InsufficientWitnessPoolError for small pool."""
        # Only 3 witnesses
        mock_witness_pool.get_ordered_active_witnesses.return_value = (
            "WITNESS:0",
            "WITNESS:1",
            "WITNESS:2",
        )

        with pytest.raises(InsufficientWitnessPoolError):
            await service.select_witness()

    @pytest.mark.asyncio
    async def test_select_witness_high_stakes_requires_12(
        self,
        service: VerifiableWitnessSelectionService,
        mock_witness_pool: AsyncMock,
    ) -> None:
        """High-stakes selection requires 12 witnesses."""
        # 10 witnesses - enough for standard, not high-stakes
        mock_witness_pool.get_ordered_active_witnesses.return_value = tuple(
            f"WITNESS:{i}" for i in range(10)
        )

        with pytest.raises(InsufficientWitnessPoolError) as exc_info:
            await service.select_witness(high_stakes=True)

        assert exc_info.value.minimum_required == HIGH_STAKES_MINIMUM_WITNESSES
        assert "high-stakes" in exc_info.value.operation_type

    @pytest.mark.asyncio
    async def test_select_witness_enforces_pair_rotation(
        self,
        service: VerifiableWitnessSelectionService,
        mock_pair_history: AsyncMock,
    ) -> None:
        """select_witness checks pair rotation constraint."""
        # Set previous witness
        service.set_previous_witness("WITNESS:prev")

        await service.select_witness()

        # Should have checked pair history
        mock_pair_history.has_appeared_in_24h.assert_called()

    @pytest.mark.asyncio
    async def test_select_witness_retries_on_rotation_violation(
        self,
        service: VerifiableWitnessSelectionService,
        mock_pair_history: AsyncMock,
    ) -> None:
        """select_witness retries when pair rotation violated."""
        service.set_previous_witness("WITNESS:prev")

        # First check returns True (blocked), then False (allowed)
        mock_pair_history.has_appeared_in_24h.side_effect = [True, False]

        record = await service.select_witness()

        assert record.selected_witness_id is not None
        assert mock_pair_history.has_appeared_in_24h.call_count == 2

    @pytest.mark.asyncio
    async def test_select_witness_all_pairs_exhausted(
        self,
        mock_halt_checker: AsyncMock,
        mock_witness_pool: AsyncMock,
        mock_entropy_source: AsyncMock,
        mock_event_store: AsyncMock,
        mock_pair_history: AsyncMock,
    ) -> None:
        """select_witness raises when all pairs are blocked."""
        # Small pool
        mock_witness_pool.get_ordered_active_witnesses.return_value = (
            "WITNESS:0",
            "WITNESS:1",
            "WITNESS:2",
            "WITNESS:3",
            "WITNESS:4",
            "WITNESS:5",
        )

        # All pairs are blocked
        mock_pair_history.has_appeared_in_24h.return_value = True

        service = VerifiableWitnessSelectionService(
            halt_checker=mock_halt_checker,
            witness_pool=mock_witness_pool,
            entropy_source=mock_entropy_source,
            event_store=mock_event_store,
            pair_history=mock_pair_history,
            previous_witness_id="WITNESS:prev",
        )

        with pytest.raises(AllWitnessesPairExhaustedError):
            await service.select_witness()

    @pytest.mark.asyncio
    async def test_select_witness_records_pair_in_history(
        self,
        service: VerifiableWitnessSelectionService,
        mock_pair_history: AsyncMock,
    ) -> None:
        """select_witness records the selected pair."""
        service.set_previous_witness("WITNESS:prev")

        await service.select_witness()

        mock_pair_history.record_pair.assert_called_once()

    @pytest.mark.asyncio
    async def test_select_witness_genesis_chain_hash(
        self,
        service: VerifiableWitnessSelectionService,
        mock_event_store: AsyncMock,
    ) -> None:
        """select_witness uses 'genesis' when no events exist."""
        mock_event_store.get_latest_event.return_value = None

        record = await service.select_witness()

        assert "genesis" in record.seed_source


class TestVerifySelection:
    """Tests for verify_selection method."""

    @pytest.mark.asyncio
    async def test_verify_selection_valid_record(
        self,
        service: VerifiableWitnessSelectionService,
    ) -> None:
        """verify_selection returns True for valid record."""
        # First select a witness
        record = await service.select_witness()

        # Then verify it
        result = await service.verify_selection(record)

        assert result is True

    @pytest.mark.asyncio
    async def test_verify_selection_halt_check(
        self,
        service: VerifiableWitnessSelectionService,
        mock_halt_checker: AsyncMock,
    ) -> None:
        """verify_selection checks halt state."""
        # Select while not halted
        record = await service.select_witness()

        # Then halt the system
        mock_halt_checker.is_halted.return_value = True

        with pytest.raises(SystemHaltedError):
            await service.verify_selection(record)

    @pytest.mark.asyncio
    async def test_verify_selection_invalid_record(
        self,
        service: VerifiableWitnessSelectionService,
    ) -> None:
        """verify_selection raises for tampered record."""
        # Get a valid record
        record = await service.select_witness()

        # Tamper with it by creating a new record with wrong witness
        from src.domain.models.witness_selection import WitnessSelectionRecord

        tampered = WitnessSelectionRecord(
            random_seed=record.random_seed,
            seed_source=record.seed_source,
            selected_witness_id="WITNESS:tampered",  # Wrong witness
            pool_snapshot=record.pool_snapshot,
            algorithm_version=record.algorithm_version,
            selected_at=record.selected_at,
        )

        with pytest.raises(WitnessSelectionVerificationError):
            await service.verify_selection(tampered)


class TestCreateSelectionEventPayload:
    """Tests for create_selection_event_payload method."""

    @pytest.mark.asyncio
    async def test_creates_payload_from_record(
        self,
        service: VerifiableWitnessSelectionService,
    ) -> None:
        """create_selection_event_payload creates valid payload."""
        record = await service.select_witness()

        payload = await service.create_selection_event_payload(record)

        assert payload.selected_witness_id == record.selected_witness_id
        assert payload.seed_source == record.seed_source
        assert payload.pool_size == len(record.pool_snapshot)
        assert payload.algorithm_version == record.algorithm_version


class TestSetPreviousWitness:
    """Tests for set_previous_witness method."""

    @pytest.mark.asyncio
    async def test_set_previous_witness_affects_selection(
        self,
        service: VerifiableWitnessSelectionService,
        mock_pair_history: AsyncMock,
    ) -> None:
        """set_previous_witness establishes context for rotation."""
        service.set_previous_witness("WITNESS:previous")

        await service.select_witness()

        # Check that pair history was called with the previous witness
        call_args = mock_pair_history.has_appeared_in_24h.call_args
        pair: WitnessPair = call_args[0][0]
        assert pair.witness_a_id == "WITNESS:previous"


class TestDeterministicAlgorithm:
    """Tests for deterministic selection algorithm."""

    @pytest.mark.asyncio
    async def test_algorithm_is_deterministic(
        self,
        mock_halt_checker: AsyncMock,
        mock_witness_pool: AsyncMock,
        mock_entropy_source: AsyncMock,
        mock_event_store: AsyncMock,
        mock_pair_history: AsyncMock,
    ) -> None:
        """Same inputs produce same selection."""
        # Use deterministic entropy
        mock_entropy_source.get_entropy.return_value = b"deterministic_entropy_here!!!!!"

        service1 = VerifiableWitnessSelectionService(
            halt_checker=mock_halt_checker,
            witness_pool=mock_witness_pool,
            entropy_source=mock_entropy_source,
            event_store=mock_event_store,
            pair_history=mock_pair_history,
        )

        service2 = VerifiableWitnessSelectionService(
            halt_checker=mock_halt_checker,
            witness_pool=mock_witness_pool,
            entropy_source=mock_entropy_source,
            event_store=mock_event_store,
            pair_history=mock_pair_history,
        )

        record1 = await service1.select_witness()
        record2 = await service2.select_witness()

        # Same entropy + same chain hash -> same selection
        assert record1.selected_witness_id == record2.selected_witness_id


class TestConstants:
    """Tests for service constants."""

    def test_default_minimum_witnesses(self) -> None:
        """DEFAULT_MINIMUM_WITNESSES is 6."""
        assert DEFAULT_MINIMUM_WITNESSES == 6

    def test_high_stakes_minimum_witnesses(self) -> None:
        """HIGH_STAKES_MINIMUM_WITNESSES is 12."""
        assert HIGH_STAKES_MINIMUM_WITNESSES == 12
