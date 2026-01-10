"""Unit tests for LoadSheddingService (Story 8.8, AC5, FR107).

Tests for load level evaluation and constitutional event protection.
"""

import pytest

from src.application.services.load_shedding_service import (
    DEFAULT_CAPACITY_THRESHOLD,
    LoadSheddingService,
)
from src.domain.errors.failure_prevention import (
    ConstitutionalEventSheddingError,
    LoadSheddingDecisionError,
)
from src.domain.models.load_status import (
    LoadLevel,
)


@pytest.fixture
def service() -> LoadSheddingService:
    """Create a LoadSheddingService instance."""
    return LoadSheddingService()


class TestSetBaselineLoad:
    """Tests for set_baseline_load method."""

    @pytest.mark.asyncio
    async def test_sets_baseline(self, service: LoadSheddingService) -> None:
        """Test that baseline load is set."""
        await service.set_baseline_load(50.0)

        assert service._baseline_load == 50.0

    @pytest.mark.asyncio
    async def test_accepts_zero_baseline(self, service: LoadSheddingService) -> None:
        """Test that zero baseline is accepted."""
        await service.set_baseline_load(0.0)

        assert service._baseline_load == 0.0

    @pytest.mark.asyncio
    async def test_rejects_negative_baseline(self, service: LoadSheddingService) -> None:
        """Test that negative baseline is rejected."""
        with pytest.raises(LoadSheddingDecisionError):
            await service.set_baseline_load(-10.0)


class TestUpdateLoad:
    """Tests for update_load method."""

    @pytest.mark.asyncio
    async def test_updates_current_load(self, service: LoadSheddingService) -> None:
        """Test that current load is updated."""
        status = await service.update_load(75.0)

        assert service._current_load == 75.0
        assert status.current_load == 75.0

    @pytest.mark.asyncio
    async def test_returns_load_status(self, service: LoadSheddingService) -> None:
        """Test that LoadStatus is returned."""
        status = await service.update_load(95.0)

        assert status is not None
        assert status.current_load == 95.0

    @pytest.mark.asyncio
    async def test_rejects_negative_load(self, service: LoadSheddingService) -> None:
        """Test that negative load is rejected."""
        with pytest.raises(LoadSheddingDecisionError):
            await service.update_load(-5.0)


class TestEvaluateLoad:
    """Tests for evaluate_load method."""

    @pytest.mark.asyncio
    async def test_returns_load_status(self, service: LoadSheddingService) -> None:
        """Test that LoadStatus is returned."""
        await service.update_load(50.0)
        status = await service.evaluate_load()

        assert status is not None
        assert status.current_load == 50.0


class TestShouldShedTelemetry:
    """Tests for should_shed_telemetry method."""

    @pytest.mark.asyncio
    async def test_no_shedding_at_low_load(self, service: LoadSheddingService) -> None:
        """Test that telemetry is not shed at low load."""
        await service.update_load(50.0)

        should_shed = await service.should_shed_telemetry()

        assert should_shed is False

    @pytest.mark.asyncio
    async def test_shedding_at_high_load(self, service: LoadSheddingService) -> None:
        """Test that telemetry is shed at high load."""
        await service.update_load(95.0)  # Above default 80% threshold

        should_shed = await service.should_shed_telemetry()

        assert should_shed is True


class TestMakeSheddingDecision:
    """Tests for make_shedding_decision method."""

    @pytest.mark.asyncio
    async def test_allows_operational_at_low_load(
        self, service: LoadSheddingService
    ) -> None:
        """Test that operational events are allowed at low load."""
        await service.update_load(50.0)

        decision = await service.make_shedding_decision(
            item_type="operational_metric",
            is_constitutional=False,
        )

        assert decision.was_shed is False

    @pytest.mark.asyncio
    async def test_sheds_operational_at_high_load(
        self, service: LoadSheddingService
    ) -> None:
        """Test that operational events are shed at high load."""
        await service.update_load(95.0)

        decision = await service.make_shedding_decision(
            item_type="operational_metric",
            is_constitutional=False,
        )

        assert decision.was_shed is True

    @pytest.mark.asyncio
    async def test_never_sheds_constitutional_events(
        self, service: LoadSheddingService
    ) -> None:
        """Test that constitutional events are NEVER shed (FR107)."""
        await service.update_load(99.0)  # Critical load

        decision = await service.make_shedding_decision(
            item_type="breach_declaration",
            is_constitutional=True,
        )

        assert decision.was_shed is False
        assert "FR107" in decision.reason

    @pytest.mark.asyncio
    async def test_constitutional_protected_at_all_load_levels(
        self, service: LoadSheddingService
    ) -> None:
        """Test that constitutional events are protected at all load levels."""
        for load in [50.0, 70.0, 85.0, 95.0, 99.0]:
            await service.update_load(load)

            decision = await service.make_shedding_decision(
                item_type="constitutional_event",
                is_constitutional=True,
            )

            assert decision.was_shed is False


class TestRaiseIfSheddingConstitutional:
    """Tests for raise_if_shedding_constitutional method (FR107)."""

    @pytest.mark.asyncio
    async def test_raises_when_attempting_to_shed_constitutional(
        self, service: LoadSheddingService
    ) -> None:
        """Test that error is raised when attempting to shed constitutional event."""
        with pytest.raises(ConstitutionalEventSheddingError):
            await service.raise_if_shedding_constitutional(
                item_type="breach_declaration",
            )


class TestGetLoadStatus:
    """Tests for get_load_status method."""

    @pytest.mark.asyncio
    async def test_returns_current_status(self, service: LoadSheddingService) -> None:
        """Test that current load status is returned."""
        await service.update_load(75.0)
        status = await service.get_load_status()

        assert status["current_load"] == 75.0

    @pytest.mark.asyncio
    async def test_default_status(self, service: LoadSheddingService) -> None:
        """Test that default status is returned."""
        status = await service.get_load_status()

        assert status["current_load"] == 0.0


class TestGetSheddingStats:
    """Tests for get_shedding_stats method."""

    @pytest.mark.asyncio
    async def test_returns_initial_stats(self, service: LoadSheddingService) -> None:
        """Test that initial stats are returned."""
        stats = await service.get_shedding_stats()

        assert stats["total_decisions"] == 0
        assert stats["constitutional_protected"] == 0
        assert stats["telemetry_shed"] == 0

    @pytest.mark.asyncio
    async def test_tracks_shed_events(self, service: LoadSheddingService) -> None:
        """Test that shed events are tracked."""
        await service.update_load(95.0)

        # Make some shedding decisions
        await service.make_shedding_decision("metric", is_constitutional=False)
        await service.make_shedding_decision("another_metric", is_constitutional=False)

        stats = await service.get_shedding_stats()

        assert stats["total_decisions"] == 2
        assert stats["telemetry_shed"] == 2

    @pytest.mark.asyncio
    async def test_tracks_protected_constitutional_events(
        self, service: LoadSheddingService
    ) -> None:
        """Test that protected constitutional events are tracked."""
        await service.update_load(95.0)

        # Constitutional events should be protected
        await service.make_shedding_decision("constitutional_event", is_constitutional=True)

        stats = await service.get_shedding_stats()

        assert stats["constitutional_protected"] == 1


class TestGetRecentDecisions:
    """Tests for get_recent_decisions method."""

    @pytest.mark.asyncio
    async def test_returns_recent_decisions(self, service: LoadSheddingService) -> None:
        """Test that recent decisions are returned."""
        await service.update_load(50.0)
        await service.make_shedding_decision("test_item", is_constitutional=False)

        decisions = await service.get_recent_decisions()

        assert len(decisions) == 1
        assert decisions[0]["item_type"] == "test_item"


class TestCapacityThreshold:
    """Tests for capacity threshold configuration."""

    def test_default_capacity_threshold(self) -> None:
        """Test that default capacity threshold is 80%."""
        assert DEFAULT_CAPACITY_THRESHOLD == 80.0

    def test_custom_capacity_threshold(self) -> None:
        """Test that custom capacity threshold can be set."""
        service = LoadSheddingService(capacity_threshold=90.0)

        assert service._capacity_threshold == 90.0
