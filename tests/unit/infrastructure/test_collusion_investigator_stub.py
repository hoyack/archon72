"""Unit tests for CollusionInvestigatorStub (Story 6.8, FR124).

Tests the in-memory stub implementation of CollusionInvestigatorProtocol.
"""

from __future__ import annotations

import pytest

from src.application.ports.collusion_investigator import InvestigationStatus
from src.domain.errors.collusion import (
    InvestigationAlreadyResolvedError,
    InvestigationNotFoundError,
)
from src.domain.events.collusion import InvestigationResolution
from src.infrastructure.stubs.collusion_investigator_stub import CollusionInvestigatorStub


@pytest.fixture
def stub() -> CollusionInvestigatorStub:
    """Create a fresh stub for each test."""
    return CollusionInvestigatorStub()


class TestTriggerInvestigation:
    """Tests for trigger_investigation method."""

    @pytest.mark.asyncio
    async def test_creates_investigation(self, stub: CollusionInvestigatorStub) -> None:
        """Test that triggering creates an investigation."""
        investigation_id = await stub.trigger_investigation(
            pair_key="witness_a:witness_b",
            anomaly_ids=("anomaly-1",),
            breach_ids=("breach-1", "breach-2"),
        )

        assert investigation_id
        investigation = await stub.get_investigation(investigation_id)
        assert investigation is not None
        assert investigation.pair_key == "witness_a:witness_b"
        assert investigation.status == InvestigationStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_suspends_pair(self, stub: CollusionInvestigatorStub) -> None:
        """Test that triggering suspends the pair."""
        await stub.trigger_investigation(
            pair_key="witness_a:witness_b",
            anomaly_ids=("anomaly-1",),
            breach_ids=("breach-1",),
        )

        assert await stub.is_pair_under_investigation("witness_a:witness_b")
        suspended = await stub.get_suspended_pairs()
        assert "witness_a:witness_b" in suspended

    @pytest.mark.asyncio
    async def test_calculates_correlation(self, stub: CollusionInvestigatorStub) -> None:
        """Test that correlation is calculated based on breach count."""
        investigation_id = await stub.trigger_investigation(
            pair_key="witness_a:witness_b",
            anomaly_ids=("anomaly-1",),
            breach_ids=tuple(f"breach-{i}" for i in range(5)),
        )

        investigation = await stub.get_investigation(investigation_id)
        assert investigation is not None
        assert investigation.correlation_score == 0.5  # 5/10


class TestResolveInvestigation:
    """Tests for resolve_investigation method."""

    @pytest.mark.asyncio
    async def test_resolve_cleared(self, stub: CollusionInvestigatorStub) -> None:
        """Test resolving as CLEARED."""
        investigation_id = await stub.trigger_investigation(
            pair_key="witness_a:witness_b",
            anomaly_ids=("anomaly-1",),
            breach_ids=("breach-1",),
        )

        await stub.resolve_investigation(
            investigation_id=investigation_id,
            resolution=InvestigationResolution.CLEARED,
            reason="No evidence found",
            resolved_by="reviewer_1",
        )

        investigation = await stub.get_investigation(investigation_id)
        assert investigation is not None
        assert investigation.status == InvestigationStatus.CLEARED
        assert investigation.resolved_by == "reviewer_1"

        # Pair should no longer be under investigation
        assert not await stub.is_pair_under_investigation("witness_a:witness_b")

    @pytest.mark.asyncio
    async def test_resolve_confirmed(self, stub: CollusionInvestigatorStub) -> None:
        """Test resolving as CONFIRMED_COLLUSION."""
        investigation_id = await stub.trigger_investigation(
            pair_key="witness_a:witness_b",
            anomaly_ids=("anomaly-1",),
            breach_ids=("breach-1",),
        )

        await stub.resolve_investigation(
            investigation_id=investigation_id,
            resolution=InvestigationResolution.CONFIRMED_COLLUSION,
            reason="Evidence confirmed",
            resolved_by="reviewer_1",
        )

        investigation = await stub.get_investigation(investigation_id)
        assert investigation is not None
        assert investigation.status == InvestigationStatus.CONFIRMED

        # Pair should be permanently banned
        banned = await stub.get_permanently_banned_pairs()
        assert "witness_a:witness_b" in banned

    @pytest.mark.asyncio
    async def test_resolve_not_found(self, stub: CollusionInvestigatorStub) -> None:
        """Test resolving non-existent investigation raises error."""
        with pytest.raises(InvestigationNotFoundError):
            await stub.resolve_investigation(
                investigation_id="non-existent",
                resolution=InvestigationResolution.CLEARED,
                reason="No evidence",
                resolved_by="reviewer_1",
            )

    @pytest.mark.asyncio
    async def test_resolve_already_resolved(self, stub: CollusionInvestigatorStub) -> None:
        """Test resolving already-resolved investigation raises error."""
        investigation_id = await stub.trigger_investigation(
            pair_key="witness_a:witness_b",
            anomaly_ids=("anomaly-1",),
            breach_ids=("breach-1",),
        )

        await stub.resolve_investigation(
            investigation_id=investigation_id,
            resolution=InvestigationResolution.CLEARED,
            reason="No evidence",
            resolved_by="reviewer_1",
        )

        with pytest.raises(InvestigationAlreadyResolvedError):
            await stub.resolve_investigation(
                investigation_id=investigation_id,
                resolution=InvestigationResolution.CONFIRMED_COLLUSION,
                reason="Changed mind",
                resolved_by="reviewer_2",
            )


class TestListActiveInvestigations:
    """Tests for list_active_investigations method."""

    @pytest.mark.asyncio
    async def test_lists_active_only(self, stub: CollusionInvestigatorStub) -> None:
        """Test that only active investigations are listed."""
        # Create two investigations
        id1 = await stub.trigger_investigation(
            pair_key="pair_a:pair_b",
            anomaly_ids=("anomaly-1",),
            breach_ids=("breach-1",),
        )
        await stub.trigger_investigation(
            pair_key="pair_c:pair_d",
            anomaly_ids=("anomaly-2",),
            breach_ids=("breach-2",),
        )

        # Resolve one
        await stub.resolve_investigation(
            investigation_id=id1,
            resolution=InvestigationResolution.CLEARED,
            reason="Cleared",
            resolved_by="reviewer",
        )

        active = await stub.list_active_investigations()
        assert len(active) == 1
        assert active[0].pair_key == "pair_c:pair_d"


class TestCalculateCorrelation:
    """Tests for calculate_correlation method."""

    @pytest.mark.asyncio
    async def test_empty_breaches(self, stub: CollusionInvestigatorStub) -> None:
        """Test correlation with no breaches is 0."""
        correlation = await stub.calculate_correlation(
            pair_key="witness_a:witness_b",
            breach_ids=(),
        )
        assert correlation == 0.0

    @pytest.mark.asyncio
    async def test_max_correlation(self, stub: CollusionInvestigatorStub) -> None:
        """Test correlation is capped at 1.0."""
        correlation = await stub.calculate_correlation(
            pair_key="witness_a:witness_b",
            breach_ids=tuple(f"breach-{i}" for i in range(20)),
        )
        assert correlation == 1.0


class TestGetInvestigationsForPair:
    """Tests for get_investigations_for_pair method."""

    @pytest.mark.asyncio
    async def test_returns_all_investigations(self, stub: CollusionInvestigatorStub) -> None:
        """Test that all investigations for a pair are returned."""
        # Create and resolve first investigation
        id1 = await stub.trigger_investigation(
            pair_key="witness_a:witness_b",
            anomaly_ids=("anomaly-1",),
            breach_ids=("breach-1",),
        )
        await stub.resolve_investigation(
            investigation_id=id1,
            resolution=InvestigationResolution.CLEARED,
            reason="Cleared first time",
            resolved_by="reviewer",
        )

        # Create second investigation
        await stub.trigger_investigation(
            pair_key="witness_a:witness_b",
            anomaly_ids=("anomaly-2",),
            breach_ids=("breach-2",),
        )

        investigations = await stub.get_investigations_for_pair("witness_a:witness_b")
        assert len(investigations) == 2


class TestClear:
    """Tests for clear method."""

    @pytest.mark.asyncio
    async def test_clears_all_data(self, stub: CollusionInvestigatorStub) -> None:
        """Test that clear removes all data."""
        await stub.trigger_investigation(
            pair_key="witness_a:witness_b",
            anomaly_ids=("anomaly-1",),
            breach_ids=("breach-1",),
        )

        stub.clear()

        assert await stub.list_active_investigations() == []
        assert await stub.get_suspended_pairs() == set()
        assert await stub.get_permanently_banned_pairs() == set()
