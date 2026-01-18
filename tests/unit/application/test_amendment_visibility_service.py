"""Unit tests for amendment visibility service (Story 6.7, FR126-FR128)."""

from datetime import datetime, timedelta, timezone

import pytest

from src.application.services.amendment_visibility_service import (
    AMENDMENT_VISIBILITY_SYSTEM_AGENT_ID,
    AmendmentProposalRequest,
    AmendmentVisibilityService,
)
from src.domain.errors.amendment import (
    AmendmentHistoryProtectionError,
    AmendmentImpactAnalysisMissingError,
    AmendmentNotFoundError,
)
from src.domain.errors.writer import SystemHaltedError
from src.domain.events.amendment import (
    VISIBILITY_PERIOD_DAYS,
    AmendmentImpactAnalysis,
    AmendmentStatus,
    AmendmentType,
)
from src.infrastructure.stubs.amendment_repository_stub import AmendmentRepositoryStub
from src.infrastructure.stubs.amendment_visibility_validator_stub import (
    AmendmentVisibilityValidatorStub,
)
from src.infrastructure.stubs.halt_checker_stub import HaltCheckerStub


@pytest.fixture
def halt_checker() -> HaltCheckerStub:
    """Provide a halt checker stub (not halted)."""
    return HaltCheckerStub(force_halted=False)


@pytest.fixture
def repository() -> AmendmentRepositoryStub:
    """Provide an amendment repository stub."""
    return AmendmentRepositoryStub()


@pytest.fixture
def validator(repository: AmendmentRepositoryStub) -> AmendmentVisibilityValidatorStub:
    """Provide an amendment visibility validator stub."""
    return AmendmentVisibilityValidatorStub(repository=repository)


@pytest.fixture
def service(
    halt_checker: HaltCheckerStub,
    repository: AmendmentRepositoryStub,
    validator: AmendmentVisibilityValidatorStub,
) -> AmendmentVisibilityService:
    """Provide an amendment visibility service."""
    return AmendmentVisibilityService(
        halt_checker=halt_checker,
        repository=repository,
        validator=validator,
    )


class TestSystemAgentId:
    """Tests for system agent ID."""

    def test_system_agent_id_format(self) -> None:
        """Test system agent ID has SYSTEM: prefix."""
        assert AMENDMENT_VISIBILITY_SYSTEM_AGENT_ID.startswith("SYSTEM:")
        assert "amendment_visibility" in AMENDMENT_VISIBILITY_SYSTEM_AGENT_ID


class TestProposeAmendment:
    """Tests for propose_amendment method (FR126-FR128)."""

    @pytest.mark.asyncio
    async def test_propose_non_core_guarantee(
        self, service: AmendmentVisibilityService, repository: AmendmentRepositoryStub
    ) -> None:
        """Test FR126: Propose non-core guarantee amendment sets 14-day visibility."""
        request = AmendmentProposalRequest(
            amendment_id="AMD-001",
            amendment_type=AmendmentType.TIER_2_CONSTITUTIONAL,
            title="Update logging format",
            summary="Change structured log format",
            proposer_id="proposer-001",
            is_core_guarantee=False,
        )

        proposal, event = await service.propose_amendment(request)

        # Verify proposal created
        assert proposal.amendment_id == "AMD-001"
        assert proposal.status == AmendmentStatus.VISIBILITY_PERIOD

        # Verify FR126: 14-day visibility period
        expected_votable = proposal.visible_from + timedelta(
            days=VISIBILITY_PERIOD_DAYS
        )
        assert abs((proposal.votable_from - expected_votable).total_seconds()) <= 1

        # Verify saved to repository
        saved = await repository.get_amendment("AMD-001")
        assert saved is not None
        assert saved.amendment_id == "AMD-001"

        # Verify event created
        assert event.amendment_id == "AMD-001"

    @pytest.mark.asyncio
    async def test_propose_core_guarantee_with_impact_analysis(
        self, service: AmendmentVisibilityService
    ) -> None:
        """Test FR127: Core guarantee with impact analysis succeeds."""
        now = datetime.now(timezone.utc)
        impact_analysis = AmendmentImpactAnalysis(
            reduces_visibility=True,
            raises_silence_probability=False,
            weakens_irreversibility=False,
            analysis_text="This amendment affects visibility by changing audit log retention policy.",
            analyzed_by="analyst-001",
            analyzed_at=now,
        )

        request = AmendmentProposalRequest(
            amendment_id="AMD-002",
            amendment_type=AmendmentType.TIER_3_CONVENTION,
            title="Modify visibility guarantees",
            summary="Change audit log retention",
            proposer_id="proposer-001",
            is_core_guarantee=True,
            impact_analysis=impact_analysis,
            affected_guarantees=("CT-11",),
        )

        proposal, event = await service.propose_amendment(request)

        assert proposal.is_core_guarantee is True
        assert proposal.impact_analysis is not None
        assert event.impact_analysis is not None

    @pytest.mark.asyncio
    async def test_propose_core_guarantee_without_impact_analysis_raises_fr127(
        self, service: AmendmentVisibilityService
    ) -> None:
        """Test FR127: Core guarantee without impact analysis raises error."""
        request = AmendmentProposalRequest(
            amendment_id="AMD-003",
            amendment_type=AmendmentType.TIER_3_CONVENTION,
            title="Modify visibility guarantees",
            summary="Change audit log retention",
            proposer_id="proposer-001",
            is_core_guarantee=True,
            # Missing impact_analysis!
        )

        with pytest.raises(AmendmentImpactAnalysisMissingError) as exc_info:
            await service.propose_amendment(request)

        assert exc_info.value.amendment_id == "AMD-003"

    @pytest.mark.asyncio
    async def test_propose_history_hiding_raises_fr128(
        self, service: AmendmentVisibilityService
    ) -> None:
        """Test FR128: Amendment with history-hiding intent is rejected."""
        request = AmendmentProposalRequest(
            amendment_id="AMD-004",
            amendment_type=AmendmentType.TIER_2_CONSTITUTIONAL,
            title="Amendment visibility changes",
            summary="This amendment will make previous amendments unreviewable",
            proposer_id="proposer-001",
            is_core_guarantee=False,
        )

        with pytest.raises(AmendmentHistoryProtectionError) as exc_info:
            await service.propose_amendment(request)

        assert exc_info.value.amendment_id == "AMD-004"

    @pytest.mark.asyncio
    async def test_propose_when_halted_raises_error(
        self, halt_checker: HaltCheckerStub, service: AmendmentVisibilityService
    ) -> None:
        """Test CT-11: Proposal blocked when system halted."""
        halt_checker.set_halted(True)

        request = AmendmentProposalRequest(
            amendment_id="AMD-005",
            amendment_type=AmendmentType.TIER_2_CONSTITUTIONAL,
            title="Test",
            summary="Test",
            proposer_id="proposer-001",
            is_core_guarantee=False,
        )

        with pytest.raises(SystemHaltedError):
            await service.propose_amendment(request)


class TestCheckVoteEligibility:
    """Tests for check_vote_eligibility method (FR126)."""

    @pytest.mark.asyncio
    async def test_check_eligible_after_14_days(
        self, service: AmendmentVisibilityService, repository: AmendmentRepositoryStub
    ) -> None:
        """Test FR126: Amendment is eligible after 14-day visibility period."""
        # Create amendment that's already past visibility period
        from src.application.ports.amendment_repository import AmendmentProposal

        past = datetime.now(timezone.utc) - timedelta(days=15)
        votable_from = past + timedelta(days=VISIBILITY_PERIOD_DAYS)

        amendment = AmendmentProposal(
            amendment_id="AMD-001",
            amendment_type=AmendmentType.TIER_2_CONSTITUTIONAL,
            title="Test",
            summary="Test",
            proposed_at=past,
            visible_from=past,
            votable_from=votable_from,
            proposer_id="proposer-001",
            is_core_guarantee=False,
            affected_guarantees=(),
            status=AmendmentStatus.VISIBILITY_PERIOD,
        )
        await repository.save_amendment(amendment)

        result, blocked_event = await service.check_vote_eligibility("AMD-001")

        assert result.is_eligible is True
        assert result.days_remaining == 0
        assert blocked_event is None

    @pytest.mark.asyncio
    async def test_check_not_eligible_before_14_days(
        self, service: AmendmentVisibilityService, repository: AmendmentRepositoryStub
    ) -> None:
        """Test FR126: Amendment not eligible before 14-day visibility period."""
        from src.application.ports.amendment_repository import AmendmentProposal

        now = datetime.now(timezone.utc)
        votable_from = now + timedelta(days=VISIBILITY_PERIOD_DAYS)

        amendment = AmendmentProposal(
            amendment_id="AMD-001",
            amendment_type=AmendmentType.TIER_2_CONSTITUTIONAL,
            title="Test",
            summary="Test",
            proposed_at=now,
            visible_from=now,
            votable_from=votable_from,
            proposer_id="proposer-001",
            is_core_guarantee=False,
            affected_guarantees=(),
            status=AmendmentStatus.VISIBILITY_PERIOD,
        )
        await repository.save_amendment(amendment)

        result, blocked_event = await service.check_vote_eligibility("AMD-001")

        assert result.is_eligible is False
        assert result.days_remaining > 0
        assert blocked_event is not None
        assert "FR126" in blocked_event.blocked_reason

    @pytest.mark.asyncio
    async def test_check_not_found_raises_error(
        self, service: AmendmentVisibilityService
    ) -> None:
        """Test error raised for non-existent amendment."""
        with pytest.raises(AmendmentNotFoundError) as exc_info:
            await service.check_vote_eligibility("AMD-NONEXISTENT")

        assert exc_info.value.amendment_id == "AMD-NONEXISTENT"

    @pytest.mark.asyncio
    async def test_check_when_halted_raises_error(
        self, halt_checker: HaltCheckerStub, service: AmendmentVisibilityService
    ) -> None:
        """Test CT-11: Check blocked when system halted."""
        halt_checker.set_halted(True)

        with pytest.raises(SystemHaltedError):
            await service.check_vote_eligibility("AMD-001")


class TestValidateAmendmentSubmission:
    """Tests for validate_amendment_submission method (FR127, FR128)."""

    @pytest.mark.asyncio
    async def test_validate_valid_non_core_amendment(
        self, service: AmendmentVisibilityService
    ) -> None:
        """Test validation passes for valid non-core amendment."""
        request = AmendmentProposalRequest(
            amendment_id="AMD-001",
            amendment_type=AmendmentType.TIER_2_CONSTITUTIONAL,
            title="Test",
            summary="Valid summary without history-hiding intent",
            proposer_id="proposer-001",
            is_core_guarantee=False,
        )

        errors = await service.validate_amendment_submission(request)

        assert len(errors) == 0

    @pytest.mark.asyncio
    async def test_validate_detects_fr128_violation(
        self, service: AmendmentVisibilityService
    ) -> None:
        """Test FR128: Validation detects history-hiding intent."""
        request = AmendmentProposalRequest(
            amendment_id="AMD-001",
            amendment_type=AmendmentType.TIER_2_CONSTITUTIONAL,
            title="Test",
            summary="Make previous amendments unreviewable",
            proposer_id="proposer-001",
            is_core_guarantee=False,
        )

        errors = await service.validate_amendment_submission(request)

        assert len(errors) > 0
        assert any("FR128" in error for error in errors)

    @pytest.mark.asyncio
    async def test_validate_detects_fr127_violation(
        self, service: AmendmentVisibilityService
    ) -> None:
        """Test FR127: Validation detects missing impact analysis."""
        request = AmendmentProposalRequest(
            amendment_id="AMD-001",
            amendment_type=AmendmentType.TIER_3_CONVENTION,
            title="Test",
            summary="Valid summary",
            proposer_id="proposer-001",
            is_core_guarantee=True,
            # Missing impact_analysis!
        )

        errors = await service.validate_amendment_submission(request)

        assert len(errors) > 0
        assert any("FR127" in error for error in errors)


class TestGetPendingAmendments:
    """Tests for get_pending_amendments method (AC5)."""

    @pytest.mark.asyncio
    async def test_get_pending_returns_summaries(
        self, service: AmendmentVisibilityService, repository: AmendmentRepositoryStub
    ) -> None:
        """Test AC5: Pending amendments returned with visibility countdown."""
        from src.application.ports.amendment_repository import AmendmentProposal

        now = datetime.now(timezone.utc)
        votable_from = now + timedelta(days=VISIBILITY_PERIOD_DAYS)

        amendment = AmendmentProposal(
            amendment_id="AMD-001",
            amendment_type=AmendmentType.TIER_2_CONSTITUTIONAL,
            title="Test Amendment",
            summary="Test",
            proposed_at=now,
            visible_from=now,
            votable_from=votable_from,
            proposer_id="proposer-001",
            is_core_guarantee=False,
            affected_guarantees=(),
            status=AmendmentStatus.VISIBILITY_PERIOD,
        )
        await repository.save_amendment(amendment)

        summaries = await service.get_pending_amendments()

        assert len(summaries) == 1
        assert summaries[0].amendment_id == "AMD-001"
        assert summaries[0].days_until_votable > 0

    @pytest.mark.asyncio
    async def test_get_pending_when_halted_raises_error(
        self, halt_checker: HaltCheckerStub, service: AmendmentVisibilityService
    ) -> None:
        """Test CT-11: Query blocked when system halted."""
        halt_checker.set_halted(True)

        with pytest.raises(SystemHaltedError):
            await service.get_pending_amendments()


class TestGetAmendmentWithVisibilityStatus:
    """Tests for get_amendment_with_visibility_status method (AC5)."""

    @pytest.mark.asyncio
    async def test_get_with_full_status(
        self, service: AmendmentVisibilityService, repository: AmendmentRepositoryStub
    ) -> None:
        """Test AC5: Get amendment with full visibility context."""
        from src.application.ports.amendment_repository import AmendmentProposal

        now = datetime.now(timezone.utc)
        votable_from = now + timedelta(days=VISIBILITY_PERIOD_DAYS)

        amendment = AmendmentProposal(
            amendment_id="AMD-001",
            amendment_type=AmendmentType.TIER_2_CONSTITUTIONAL,
            title="Test",
            summary="Test",
            proposed_at=now,
            visible_from=now,
            votable_from=votable_from,
            proposer_id="proposer-001",
            is_core_guarantee=False,
            affected_guarantees=(),
            status=AmendmentStatus.VISIBILITY_PERIOD,
        )
        await repository.save_amendment(amendment)

        result = await service.get_amendment_with_visibility_status("AMD-001")

        assert result.proposal.amendment_id == "AMD-001"
        assert result.is_votable is False
        assert result.days_remaining > 0
        assert "days remaining" in result.visibility_status

    @pytest.mark.asyncio
    async def test_get_not_found_raises_error(
        self, service: AmendmentVisibilityService
    ) -> None:
        """Test error raised for non-existent amendment."""
        with pytest.raises(AmendmentNotFoundError):
            await service.get_amendment_with_visibility_status("AMD-NONEXISTENT")


class TestRejectAmendment:
    """Tests for reject_amendment method (FR128)."""

    @pytest.mark.asyncio
    async def test_reject_creates_event(
        self, service: AmendmentVisibilityService, repository: AmendmentRepositoryStub
    ) -> None:
        """Test rejection creates witnessed event."""
        from src.application.ports.amendment_repository import AmendmentProposal

        now = datetime.now(timezone.utc)
        votable_from = now + timedelta(days=VISIBILITY_PERIOD_DAYS)

        amendment = AmendmentProposal(
            amendment_id="AMD-001",
            amendment_type=AmendmentType.TIER_2_CONSTITUTIONAL,
            title="Test",
            summary="Test",
            proposed_at=now,
            visible_from=now,
            votable_from=votable_from,
            proposer_id="proposer-001",
            is_core_guarantee=False,
            affected_guarantees=(),
            status=AmendmentStatus.VISIBILITY_PERIOD,
        )
        await repository.save_amendment(amendment)

        event = await service.reject_amendment(
            "AMD-001", "FR128: Amendment history cannot be made unreviewable"
        )

        assert event.amendment_id == "AMD-001"
        assert "FR128" in event.rejection_reason

        # Verify status updated
        saved = await repository.get_amendment("AMD-001")
        assert saved is not None
        assert saved.status == AmendmentStatus.REJECTED

    @pytest.mark.asyncio
    async def test_reject_not_found_raises_error(
        self, service: AmendmentVisibilityService
    ) -> None:
        """Test error raised for non-existent amendment."""
        with pytest.raises(AmendmentNotFoundError):
            await service.reject_amendment("AMD-NONEXISTENT", "Test reason")
