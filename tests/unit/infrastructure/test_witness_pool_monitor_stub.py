"""Unit tests for witness pool monitor stub (Story 6.6, FR117)."""

from datetime import datetime, timezone

import pytest

from src.application.ports.witness_pool_monitor import (
    MINIMUM_WITNESSES_HIGH_STAKES,
    MINIMUM_WITNESSES_STANDARD,
)
from src.infrastructure.stubs.witness_pool_monitor_stub import WitnessPoolMonitorStub


class TestWitnessPoolMonitorStubInit:
    """Tests for WitnessPoolMonitorStub initialization."""

    def test_initializes_with_default_pool_size(self) -> None:
        """Test stub initializes with 15 witnesses by default."""
        stub = WitnessPoolMonitorStub()

        assert len(stub._available_witnesses) == 15

    def test_initializes_with_custom_pool_size(self) -> None:
        """Test stub initializes with custom pool size."""
        stub = WitnessPoolMonitorStub(initial_pool_size=20)

        assert len(stub._available_witnesses) == 20

    def test_initializes_empty_excluded(self) -> None:
        """Test stub initializes with no excluded witnesses."""
        stub = WitnessPoolMonitorStub()

        assert stub._excluded_witnesses == []

    def test_initializes_not_degraded(self) -> None:
        """Test stub initializes as not degraded."""
        stub = WitnessPoolMonitorStub()

        assert stub._degraded_since is None
        assert stub._force_degraded is None


class TestGetPoolStatus:
    """Tests for get_pool_status method."""

    @pytest.mark.asyncio
    async def test_returns_healthy_status(self) -> None:
        """Test returns healthy status for adequate pool."""
        stub = WitnessPoolMonitorStub(initial_pool_size=15)

        status = await stub.get_pool_status()

        assert status.available_count == 15
        assert status.is_degraded is False
        assert status.degraded_since is None
        assert status.minimum_for_standard == MINIMUM_WITNESSES_STANDARD
        assert status.minimum_for_high_stakes == MINIMUM_WITNESSES_HIGH_STAKES

    @pytest.mark.asyncio
    async def test_returns_degraded_status(self) -> None:
        """Test returns degraded status for insufficient pool."""
        stub = WitnessPoolMonitorStub(initial_pool_size=8)

        status = await stub.get_pool_status()

        assert status.available_count == 8
        assert status.is_degraded is True
        assert status.degraded_since is not None

    @pytest.mark.asyncio
    async def test_includes_excluded_witnesses(self) -> None:
        """Test status includes excluded witnesses."""
        stub = WitnessPoolMonitorStub(initial_pool_size=15)
        stub.set_excluded_witnesses(["WITNESS:001", "WITNESS:002"])

        status = await stub.get_pool_status()

        assert status.excluded_witnesses == ("WITNESS:001", "WITNESS:002")
        assert status.effective_count == 13

    @pytest.mark.asyncio
    async def test_respects_force_degraded(self) -> None:
        """Test force_degraded overrides calculation."""
        stub = WitnessPoolMonitorStub(initial_pool_size=15)
        stub.set_degraded(True)

        status = await stub.get_pool_status()

        assert status.is_degraded is True
        assert status.available_count == 15  # Pool is healthy but forced degraded


class TestIsDegraded:
    """Tests for is_degraded method."""

    @pytest.mark.asyncio
    async def test_returns_false_for_healthy(self) -> None:
        """Test returns False for healthy pool."""
        stub = WitnessPoolMonitorStub(initial_pool_size=15)

        result = await stub.is_degraded()

        assert result is False

    @pytest.mark.asyncio
    async def test_returns_true_for_degraded(self) -> None:
        """Test returns True for degraded pool."""
        stub = WitnessPoolMonitorStub(initial_pool_size=8)

        result = await stub.is_degraded()

        assert result is True


class TestCanPerformOperation:
    """Tests for can_perform_operation method."""

    @pytest.mark.asyncio
    async def test_allows_high_stakes_with_healthy_pool(self) -> None:
        """Test allows high-stakes with healthy pool."""
        stub = WitnessPoolMonitorStub(initial_pool_size=15)

        result = await stub.can_perform_operation(high_stakes=True)

        assert result is True

    @pytest.mark.asyncio
    async def test_blocks_high_stakes_with_degraded_pool(self) -> None:
        """Test blocks high-stakes with degraded pool."""
        stub = WitnessPoolMonitorStub(initial_pool_size=8)

        result = await stub.can_perform_operation(high_stakes=True)

        assert result is False

    @pytest.mark.asyncio
    async def test_allows_standard_with_adequate_pool(self) -> None:
        """Test allows standard with adequate pool (>= 6)."""
        stub = WitnessPoolMonitorStub(initial_pool_size=8)

        result = await stub.can_perform_operation(high_stakes=False)

        assert result is True

    @pytest.mark.asyncio
    async def test_blocks_standard_with_insufficient_pool(self) -> None:
        """Test blocks standard with insufficient pool (< 6)."""
        stub = WitnessPoolMonitorStub(initial_pool_size=4)

        result = await stub.can_perform_operation(high_stakes=False)

        assert result is False


class TestGetDegradedSince:
    """Tests for get_degraded_since method."""

    @pytest.mark.asyncio
    async def test_returns_none_when_not_degraded(self) -> None:
        """Test returns None when pool is not degraded."""
        stub = WitnessPoolMonitorStub(initial_pool_size=15)

        result = await stub.get_degraded_since()

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_datetime_when_degraded(self) -> None:
        """Test returns datetime when pool is degraded."""
        stub = WitnessPoolMonitorStub(initial_pool_size=8)

        # Trigger degraded state by checking status
        await stub.get_pool_status()

        result = await stub.get_degraded_since()

        assert result is not None
        assert isinstance(result, datetime)


class TestGetAvailableWitnesses:
    """Tests for get_available_witnesses method."""

    @pytest.mark.asyncio
    async def test_returns_witness_ids(self) -> None:
        """Test returns tuple of witness IDs."""
        stub = WitnessPoolMonitorStub(initial_pool_size=3)

        result = await stub.get_available_witnesses()

        assert result == ("WITNESS:000", "WITNESS:001", "WITNESS:002")


class TestGetExcludedWitnesses:
    """Tests for get_excluded_witnesses method."""

    @pytest.mark.asyncio
    async def test_returns_empty_by_default(self) -> None:
        """Test returns empty tuple by default."""
        stub = WitnessPoolMonitorStub()

        result = await stub.get_excluded_witnesses()

        assert result == ()

    @pytest.mark.asyncio
    async def test_returns_excluded_witnesses(self) -> None:
        """Test returns excluded witness IDs."""
        stub = WitnessPoolMonitorStub()
        stub.set_excluded_witnesses(["WITNESS:001", "WITNESS:002"])

        result = await stub.get_excluded_witnesses()

        assert result == ("WITNESS:001", "WITNESS:002")


class TestSetPoolSize:
    """Tests for set_pool_size test helper."""

    @pytest.mark.asyncio
    async def test_sets_pool_size(self) -> None:
        """Test sets pool size."""
        stub = WitnessPoolMonitorStub()

        stub.set_pool_size(10)

        assert len(stub._available_witnesses) == 10

    @pytest.mark.asyncio
    async def test_clears_force_degraded(self) -> None:
        """Test clears force_degraded flag."""
        stub = WitnessPoolMonitorStub()
        stub.set_degraded(True)

        stub.set_pool_size(15)

        assert stub._force_degraded is None


class TestSetAvailableWitnesses:
    """Tests for set_available_witnesses test helper."""

    @pytest.mark.asyncio
    async def test_sets_specific_witnesses(self) -> None:
        """Test sets specific witness IDs."""
        stub = WitnessPoolMonitorStub()

        stub.set_available_witnesses(["ALICE", "BOB", "CHARLIE"])

        result = await stub.get_available_witnesses()
        assert result == ("ALICE", "BOB", "CHARLIE")


class TestSetExcludedWitnesses:
    """Tests for set_excluded_witnesses test helper."""

    @pytest.mark.asyncio
    async def test_sets_excluded_witnesses(self) -> None:
        """Test sets excluded witness IDs."""
        stub = WitnessPoolMonitorStub()

        stub.set_excluded_witnesses(["EXCLUDED:001", "EXCLUDED:002"])

        result = await stub.get_excluded_witnesses()
        assert result == ("EXCLUDED:001", "EXCLUDED:002")


class TestSetDegraded:
    """Tests for set_degraded test helper."""

    @pytest.mark.asyncio
    async def test_forces_degraded_true(self) -> None:
        """Test forces degraded state to True."""
        stub = WitnessPoolMonitorStub(initial_pool_size=15)

        stub.set_degraded(True)

        result = await stub.is_degraded()
        assert result is True

    @pytest.mark.asyncio
    async def test_forces_degraded_false(self) -> None:
        """Test forces degraded state to False."""
        stub = WitnessPoolMonitorStub(initial_pool_size=8)

        stub.set_degraded(False)

        result = await stub.is_degraded()
        assert result is False

    @pytest.mark.asyncio
    async def test_sets_degraded_since_when_true(self) -> None:
        """Test sets degraded_since when forcing True."""
        stub = WitnessPoolMonitorStub()

        stub.set_degraded(True)

        assert stub._degraded_since is not None

    @pytest.mark.asyncio
    async def test_clears_degraded_since_when_false(self) -> None:
        """Test clears degraded_since when forcing False."""
        stub = WitnessPoolMonitorStub(initial_pool_size=8)
        await stub.get_pool_status()  # Trigger degraded_since

        stub.set_degraded(False)

        assert stub._degraded_since is None


class TestClear:
    """Tests for clear test helper."""

    @pytest.mark.asyncio
    async def test_clears_all_state(self) -> None:
        """Test clears all state to defaults."""
        stub = WitnessPoolMonitorStub(initial_pool_size=5)
        stub.set_excluded_witnesses(["EXCLUDED:001"])
        stub.set_degraded(True)

        stub.clear()

        assert len(stub._available_witnesses) == 15
        assert stub._excluded_witnesses == []
        assert stub._degraded_since is None
        assert stub._force_degraded is None


class TestDegradedStateTracking:
    """Tests for degraded state tracking behavior."""

    @pytest.mark.asyncio
    async def test_tracks_degraded_start_time(self) -> None:
        """Test tracks when degraded mode started."""
        stub = WitnessPoolMonitorStub(initial_pool_size=8)

        before = datetime.now(timezone.utc)
        status = await stub.get_pool_status()
        after = datetime.now(timezone.utc)

        assert status.degraded_since is not None
        assert before <= status.degraded_since <= after

    @pytest.mark.asyncio
    async def test_preserves_degraded_since_across_calls(self) -> None:
        """Test preserves degraded_since time across multiple checks."""
        stub = WitnessPoolMonitorStub(initial_pool_size=8)

        status1 = await stub.get_pool_status()
        degraded_time = status1.degraded_since

        status2 = await stub.get_pool_status()

        assert status2.degraded_since == degraded_time

    @pytest.mark.asyncio
    async def test_clears_degraded_since_when_restored(self) -> None:
        """Test clears degraded_since when pool is restored."""
        stub = WitnessPoolMonitorStub(initial_pool_size=8)

        # Become degraded
        await stub.get_pool_status()
        assert stub._degraded_since is not None

        # Restore pool
        stub.set_pool_size(15)
        status = await stub.get_pool_status()

        assert status.is_degraded is False
        assert status.degraded_since is None
