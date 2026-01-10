"""Integration tests for breach collusion defense (Story 6.8, FR124).

Tests BreachCollusionDefenseService with infrastructure stubs.

Constitutional Constraints:
- FR124: Witness selection randomness SHALL combine hash chain state +
         external entropy source meeting independence criteria (Randomness Gaming defense)
- CT-11: Silent failure destroys legitimacy -> HALT CHECK FIRST
- CT-12: Witnessing creates accountability
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.application.ports.collusion_investigator import InvestigationStatus
from src.application.services.breach_collusion_defense_service import (
    BreachCollusionDefenseService,
)
from src.domain.errors.collusion import (
    InvestigationAlreadyResolvedError,
    InvestigationNotFoundError,
)
from src.domain.errors.writer import SystemHaltedError
from src.domain.events.collusion import InvestigationResolution
from src.infrastructure.stubs.breach_repository_stub import BreachRepositoryStub
from src.infrastructure.stubs.collusion_investigator_stub import CollusionInvestigatorStub
from src.infrastructure.stubs.halt_checker_stub import HaltCheckerStub
from src.infrastructure.stubs.witness_anomaly_detector_stub import (
    WitnessAnomalyDetectorStub,
)


@pytest.fixture
def halt_checker() -> HaltCheckerStub:
    """Create halt checker stub."""
    return HaltCheckerStub()


@pytest.fixture
def investigator() -> CollusionInvestigatorStub:
    """Create collusion investigator stub."""
    return CollusionInvestigatorStub()


@pytest.fixture
def anomaly_detector() -> WitnessAnomalyDetectorStub:
    """Create anomaly detector stub."""
    return WitnessAnomalyDetectorStub()


@pytest.fixture
def breach_repository() -> BreachRepositoryStub:
    """Create breach repository stub."""
    return BreachRepositoryStub()


@pytest.fixture
def service(
    halt_checker: HaltCheckerStub,
    investigator: CollusionInvestigatorStub,
    anomaly_detector: WitnessAnomalyDetectorStub,
    breach_repository: BreachRepositoryStub,
) -> BreachCollusionDefenseService:
    """Create breach collusion defense service with stubs."""
    return BreachCollusionDefenseService(
        halt_checker=halt_checker,
        investigator=investigator,
        anomaly_detector=anomaly_detector,
        breach_repository=breach_repository,
        correlation_threshold=0.8,
    )


class TestHaltCheckFirst:
    """Tests for HALT CHECK FIRST pattern (CT-11)."""

    @pytest.mark.asyncio
    async def test_check_for_collusion_halted(
        self,
        service: BreachCollusionDefenseService,
        halt_checker: HaltCheckerStub,
    ) -> None:
        """Test that check_for_collusion_trigger raises when halted."""
        halt_checker.set_halted(True)

        with pytest.raises(SystemHaltedError):
            await service.check_for_collusion_trigger("witness_a:witness_b")

    @pytest.mark.asyncio
    async def test_trigger_investigation_halted(
        self,
        service: BreachCollusionDefenseService,
        halt_checker: HaltCheckerStub,
    ) -> None:
        """Test that trigger_investigation raises when halted."""
        halt_checker.set_halted(True)

        with pytest.raises(SystemHaltedError):
            await service.trigger_investigation(
                pair_key="witness_a:witness_b",
                anomaly_ids=("anomaly-1",),
                breach_ids=("breach-1",),
            )

    @pytest.mark.asyncio
    async def test_resolve_investigation_halted(
        self,
        service: BreachCollusionDefenseService,
        halt_checker: HaltCheckerStub,
        investigator: CollusionInvestigatorStub,
    ) -> None:
        """Test that resolve_investigation raises when halted."""
        # Create investigation first
        investigation_id = await investigator.trigger_investigation(
            pair_key="witness_a:witness_b",
            anomaly_ids=("anomaly-1",),
            breach_ids=("breach-1",),
        )

        halt_checker.set_halted(True)

        with pytest.raises(SystemHaltedError):
            await service.resolve_investigation(
                investigation_id=investigation_id,
                resolution=InvestigationResolution.CLEARED,
                reason="No evidence",
                resolved_by="reviewer",
            )


class TestTriggerInvestigation:
    """Tests for triggering collusion investigations."""

    @pytest.mark.asyncio
    async def test_creates_investigation(
        self,
        service: BreachCollusionDefenseService,
        investigator: CollusionInvestigatorStub,
    ) -> None:
        """Test that investigation is created correctly."""
        investigation_id = await service.trigger_investigation(
            pair_key="witness_a:witness_b",
            anomaly_ids=("anomaly-1", "anomaly-2"),
            breach_ids=("breach-1", "breach-2"),
        )

        assert investigation_id is not None
        investigation = await investigator.get_investigation(investigation_id)
        assert investigation is not None
        assert investigation.status == InvestigationStatus.ACTIVE
        assert investigation.pair_key == "witness_a:witness_b"

    @pytest.mark.asyncio
    async def test_suspends_pair(
        self,
        service: BreachCollusionDefenseService,
        investigator: CollusionInvestigatorStub,
    ) -> None:
        """Test that pair is suspended after investigation trigger."""
        await service.trigger_investigation(
            pair_key="witness_a:witness_b",
            anomaly_ids=("anomaly-1",),
            breach_ids=("breach-1",),
        )

        assert await service.is_pair_under_investigation("witness_a:witness_b")
        suspended = await service.get_suspended_pairs()
        assert "witness_a:witness_b" in suspended


class TestResolveInvestigation:
    """Tests for resolving collusion investigations."""

    @pytest.mark.asyncio
    async def test_resolve_cleared_reinstates_pair(
        self,
        service: BreachCollusionDefenseService,
    ) -> None:
        """Test that CLEARED resolution reinstates pair."""
        investigation_id = await service.trigger_investigation(
            pair_key="witness_a:witness_b",
            anomaly_ids=("anomaly-1",),
            breach_ids=("breach-1",),
        )

        await service.resolve_investigation(
            investigation_id=investigation_id,
            resolution=InvestigationResolution.CLEARED,
            reason="No evidence of collusion",
            resolved_by="human_reviewer_1",
        )

        # Pair should no longer be suspended
        assert not await service.is_pair_under_investigation("witness_a:witness_b")

    @pytest.mark.asyncio
    async def test_resolve_confirmed_bans_pair(
        self,
        service: BreachCollusionDefenseService,
    ) -> None:
        """Test that CONFIRMED_COLLUSION permanently bans pair."""
        investigation_id = await service.trigger_investigation(
            pair_key="witness_a:witness_b",
            anomaly_ids=("anomaly-1",),
            breach_ids=("breach-1",),
        )

        await service.resolve_investigation(
            investigation_id=investigation_id,
            resolution=InvestigationResolution.CONFIRMED_COLLUSION,
            reason="Evidence confirmed coordinated behavior",
            resolved_by="human_reviewer_1",
        )

        banned = await service.get_permanently_banned_pairs()
        assert "witness_a:witness_b" in banned

    @pytest.mark.asyncio
    async def test_resolve_not_found(
        self,
        service: BreachCollusionDefenseService,
    ) -> None:
        """Test that resolving non-existent investigation raises error."""
        with pytest.raises(InvestigationNotFoundError):
            await service.resolve_investigation(
                investigation_id="non-existent",
                resolution=InvestigationResolution.CLEARED,
                reason="No evidence",
                resolved_by="reviewer",
            )

    @pytest.mark.asyncio
    async def test_resolve_already_resolved(
        self,
        service: BreachCollusionDefenseService,
    ) -> None:
        """Test that resolving already-resolved investigation raises error."""
        investigation_id = await service.trigger_investigation(
            pair_key="witness_a:witness_b",
            anomaly_ids=("anomaly-1",),
            breach_ids=("breach-1",),
        )

        await service.resolve_investigation(
            investigation_id=investigation_id,
            resolution=InvestigationResolution.CLEARED,
            reason="First resolution",
            resolved_by="reviewer",
        )

        with pytest.raises(InvestigationAlreadyResolvedError):
            await service.resolve_investigation(
                investigation_id=investigation_id,
                resolution=InvestigationResolution.CONFIRMED_COLLUSION,
                reason="Second resolution",
                resolved_by="reviewer",
            )


class TestCheckForCollusionTrigger:
    """Tests for automatic collusion trigger detection."""

    @pytest.mark.asyncio
    async def test_no_breaches_no_investigation(
        self,
        service: BreachCollusionDefenseService,
    ) -> None:
        """Test that no breaches means no investigation trigger."""
        result = await service.check_for_collusion_trigger("witness_a:witness_b")

        assert not result.requires_investigation
        assert result.correlation_score == 0.0
        assert result.breach_count == 0

    @pytest.mark.asyncio
    async def test_already_under_investigation(
        self,
        service: BreachCollusionDefenseService,
        investigator: CollusionInvestigatorStub,
    ) -> None:
        """Test that already-investigated pairs don't trigger new investigation."""
        # Create existing investigation
        investigation_id = await investigator.trigger_investigation(
            pair_key="witness_a:witness_b",
            anomaly_ids=("anomaly-1",),
            breach_ids=("breach-1",),
        )

        result = await service.check_for_collusion_trigger("witness_a:witness_b")

        assert not result.requires_investigation
        assert result.investigation_id == investigation_id


class TestListActiveInvestigations:
    """Tests for listing active investigations."""

    @pytest.mark.asyncio
    async def test_lists_active(
        self,
        service: BreachCollusionDefenseService,
    ) -> None:
        """Test that active investigations are listed."""
        await service.trigger_investigation(
            pair_key="pair_a:pair_b",
            anomaly_ids=("anomaly-1",),
            breach_ids=("breach-1",),
        )
        await service.trigger_investigation(
            pair_key="pair_c:pair_d",
            anomaly_ids=("anomaly-2",),
            breach_ids=("breach-2",),
        )

        active = await service.list_active_investigations()
        assert len(active) == 2

    @pytest.mark.asyncio
    async def test_excludes_resolved(
        self,
        service: BreachCollusionDefenseService,
    ) -> None:
        """Test that resolved investigations are excluded."""
        id1 = await service.trigger_investigation(
            pair_key="pair_a:pair_b",
            anomaly_ids=("anomaly-1",),
            breach_ids=("breach-1",),
        )
        await service.trigger_investigation(
            pair_key="pair_c:pair_d",
            anomaly_ids=("anomaly-2",),
            breach_ids=("breach-2",),
        )

        await service.resolve_investigation(
            investigation_id=id1,
            resolution=InvestigationResolution.CLEARED,
            reason="Cleared",
            resolved_by="reviewer",
        )

        active = await service.list_active_investigations()
        assert len(active) == 1
        assert active[0].pair_key == "pair_c:pair_d"
