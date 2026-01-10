"""Unit tests for InMemoryWitnessPool adapter (FR4, FR5).

Tests the in-memory witness pool implementation.

Constitutional Constraints Tested:
- FR5: No unwitnessed events can exist - raises NoWitnessAvailableError
- CT-12: Witnessing creates accountability
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from src.domain.errors.witness import NoWitnessAvailableError, WitnessNotFoundError
from src.domain.models.witness import Witness
from src.infrastructure.adapters.persistence.witness_pool import InMemoryWitnessPool


@pytest.fixture
def witness_pool() -> InMemoryWitnessPool:
    """Create a fresh witness pool for each test."""
    return InMemoryWitnessPool()


@pytest.fixture
def active_witness() -> Witness:
    """Create an active witness."""
    return Witness(
        witness_id=f"WITNESS:{uuid4()}",
        public_key=bytes(32),
        active_from=datetime.now(timezone.utc) - timedelta(hours=1),
    )


@pytest.fixture
def inactive_witness() -> Witness:
    """Create an inactive (expired) witness."""
    return Witness(
        witness_id=f"WITNESS:{uuid4()}",
        public_key=bytes(32),
        active_from=datetime.now(timezone.utc) - timedelta(hours=2),
        active_until=datetime.now(timezone.utc) - timedelta(hours=1),
    )


@pytest.fixture
def future_witness() -> Witness:
    """Create a witness that's not yet active."""
    return Witness(
        witness_id=f"WITNESS:{uuid4()}",
        public_key=bytes(32),
        active_from=datetime.now(timezone.utc) + timedelta(hours=1),
    )


class TestGetAvailableWitness:
    """Tests for get_available_witness() method."""

    @pytest.mark.asyncio
    async def test_returns_active_witness(
        self, witness_pool: InMemoryWitnessPool, active_witness: Witness
    ) -> None:
        """Test that get_available_witness returns an active witness."""
        await witness_pool.register_witness(active_witness)

        result = await witness_pool.get_available_witness()

        assert result == active_witness

    @pytest.mark.asyncio
    async def test_raises_when_no_witnesses(
        self, witness_pool: InMemoryWitnessPool
    ) -> None:
        """Test that NoWitnessAvailableError is raised when pool is empty."""
        with pytest.raises(NoWitnessAvailableError) as exc_info:
            await witness_pool.get_available_witness()

        assert "RT-1" in str(exc_info.value)
        assert "No witnesses available" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_raises_when_only_inactive_witnesses(
        self, witness_pool: InMemoryWitnessPool, inactive_witness: Witness
    ) -> None:
        """Test that NoWitnessAvailableError is raised when only inactive witnesses exist."""
        await witness_pool.register_witness(inactive_witness)

        with pytest.raises(NoWitnessAvailableError):
            await witness_pool.get_available_witness()

    @pytest.mark.asyncio
    async def test_raises_when_only_future_witnesses(
        self, witness_pool: InMemoryWitnessPool, future_witness: Witness
    ) -> None:
        """Test that NoWitnessAvailableError is raised when witnesses are not yet active."""
        await witness_pool.register_witness(future_witness)

        with pytest.raises(NoWitnessAvailableError):
            await witness_pool.get_available_witness()

    @pytest.mark.asyncio
    async def test_round_robin_selection(
        self, witness_pool: InMemoryWitnessPool
    ) -> None:
        """Test that witnesses are selected in round-robin order."""
        witnesses = [
            Witness(
                witness_id=f"WITNESS:{i}",
                public_key=bytes(32),
                active_from=datetime.now(timezone.utc) - timedelta(hours=1),
            )
            for i in range(3)
        ]

        for w in witnesses:
            await witness_pool.register_witness(w)

        # Get witnesses multiple times to verify round-robin
        selected = []
        for _ in range(6):
            w = await witness_pool.get_available_witness()
            selected.append(w.witness_id)

        # Should cycle through all witnesses
        assert "WITNESS:0" in selected
        assert "WITNESS:1" in selected
        assert "WITNESS:2" in selected


class TestGetWitnessById:
    """Tests for get_witness_by_id() method."""

    @pytest.mark.asyncio
    async def test_returns_witness_when_exists(
        self, witness_pool: InMemoryWitnessPool, active_witness: Witness
    ) -> None:
        """Test that get_witness_by_id returns witness when it exists."""
        await witness_pool.register_witness(active_witness)

        result = await witness_pool.get_witness_by_id(active_witness.witness_id)

        assert result == active_witness

    @pytest.mark.asyncio
    async def test_returns_none_when_not_exists(
        self, witness_pool: InMemoryWitnessPool
    ) -> None:
        """Test that get_witness_by_id returns None for non-existent witness."""
        result = await witness_pool.get_witness_by_id("WITNESS:nonexistent")

        assert result is None


class TestRegisterWitness:
    """Tests for register_witness() method."""

    @pytest.mark.asyncio
    async def test_registers_new_witness(
        self, witness_pool: InMemoryWitnessPool, active_witness: Witness
    ) -> None:
        """Test that register_witness adds witness to pool."""
        await witness_pool.register_witness(active_witness)

        result = await witness_pool.get_witness_by_id(active_witness.witness_id)
        assert result == active_witness

    @pytest.mark.asyncio
    async def test_replaces_existing_witness(
        self, witness_pool: InMemoryWitnessPool
    ) -> None:
        """Test that registering same witness_id replaces existing."""
        witness_id = f"WITNESS:{uuid4()}"

        witness1 = Witness(
            witness_id=witness_id,
            public_key=b"A" * 32,
            active_from=datetime.now(timezone.utc),
        )
        witness2 = Witness(
            witness_id=witness_id,
            public_key=b"B" * 32,
            active_from=datetime.now(timezone.utc),
        )

        await witness_pool.register_witness(witness1)
        await witness_pool.register_witness(witness2)

        result = await witness_pool.get_witness_by_id(witness_id)
        assert result.public_key == b"B" * 32


class TestDeactivateWitness:
    """Tests for deactivate_witness() method."""

    @pytest.mark.asyncio
    async def test_deactivates_witness(
        self, witness_pool: InMemoryWitnessPool, active_witness: Witness
    ) -> None:
        """Test that deactivate_witness prevents future attestations."""
        await witness_pool.register_witness(active_witness)

        await witness_pool.deactivate_witness(active_witness.witness_id)

        # Should no longer be available
        with pytest.raises(NoWitnessAvailableError):
            await witness_pool.get_available_witness()

    @pytest.mark.asyncio
    async def test_raises_when_not_found(
        self, witness_pool: InMemoryWitnessPool
    ) -> None:
        """Test that deactivate_witness raises for non-existent witness."""
        with pytest.raises(WitnessNotFoundError) as exc_info:
            await witness_pool.deactivate_witness("WITNESS:nonexistent")

        assert "FR4" in str(exc_info.value)


class TestCountActiveWitnesses:
    """Tests for count_active_witnesses() method."""

    @pytest.mark.asyncio
    async def test_returns_zero_when_empty(
        self, witness_pool: InMemoryWitnessPool
    ) -> None:
        """Test that count is zero for empty pool."""
        count = await witness_pool.count_active_witnesses()
        assert count == 0

    @pytest.mark.asyncio
    async def test_counts_only_active(
        self,
        witness_pool: InMemoryWitnessPool,
        active_witness: Witness,
        inactive_witness: Witness,
    ) -> None:
        """Test that count only includes active witnesses."""
        await witness_pool.register_witness(active_witness)
        await witness_pool.register_witness(inactive_witness)

        count = await witness_pool.count_active_witnesses()
        assert count == 1


class TestClear:
    """Tests for clear() method."""

    def test_clears_all_witnesses(
        self, witness_pool: InMemoryWitnessPool, active_witness: Witness
    ) -> None:
        """Test that clear removes all witnesses."""
        witness_pool.register_witness_sync(active_witness)

        witness_pool.clear()

        assert witness_pool._witnesses == {}
        assert witness_pool._selection_index == 0
