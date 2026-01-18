"""Integration tests for amendment visibility (Story 6.7, FR126-FR128).

Tests the full amendment visibility flow including:
- FR126: 14-day visibility period before vote
- FR127: Impact analysis for core guarantee amendments
- FR128: History protection - amendments cannot hide history
- AC1-AC5: Acceptance criteria verification

Constitutional Truths Tested:
- CT-11: Silent failure destroys legitimacy -> HALT CHECK FIRST
- CT-12: Witnessing creates accountability -> Events are witnessed
- CT-15: Legitimacy requires consent -> 14-day visibility ensures consent
"""

from datetime import datetime, timedelta, timezone

import pytest

from src.application.ports.amendment_repository import AmendmentProposal
from src.application.services.amendment_visibility_service import (
    AmendmentProposalRequest,
    AmendmentVisibilityService,
)
from src.domain.errors.amendment import (
    AmendmentHistoryProtectionError,
    AmendmentImpactAnalysisMissingError,
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


class TestFR126VisibilityPeriod:
    """Integration tests for FR126: 14-day visibility period."""

    @pytest.mark.asyncio
    async def test_ac1_amendment_proposed_starts_14_day_countdown(
        self, service: AmendmentVisibilityService, repository: AmendmentRepositoryStub
    ) -> None:
        """Test AC1: Amendment proposed -> 14-day visibility countdown starts.

        Given: A constitutional amendment is submitted
        When: The proposal is saved
        Then: votable_from is set to 14 days after visible_from
        """
        request = AmendmentProposalRequest(
            amendment_id="AMD-001",
            amendment_type=AmendmentType.TIER_2_CONSTITUTIONAL,
            title="Update logging format",
            summary="Change structured log format for better parsing",
            proposer_id="proposer-001",
            is_core_guarantee=False,
        )

        proposal, event = await service.propose_amendment(request)

        # Verify 14-day visibility period
        expected_votable = proposal.visible_from + timedelta(
            days=VISIBILITY_PERIOD_DAYS
        )
        assert abs((proposal.votable_from - expected_votable).total_seconds()) <= 1

        # Verify status is VISIBILITY_PERIOD
        assert proposal.status == AmendmentStatus.VISIBILITY_PERIOD

        # Verify event created for witnessing
        assert event.amendment_id == "AMD-001"

    @pytest.mark.asyncio
    async def test_ac2_vote_blocked_before_14_days(
        self, service: AmendmentVisibilityService, repository: AmendmentRepositoryStub
    ) -> None:
        """Test AC2: Vote attempted before 14 days -> blocked with days remaining.

        Given: An amendment in visibility period
        When: A vote is attempted before 14 days complete
        Then: Vote is blocked with clear reason showing days remaining
        """
        # Create amendment in visibility period
        request = AmendmentProposalRequest(
            amendment_id="AMD-001",
            amendment_type=AmendmentType.TIER_2_CONSTITUTIONAL,
            title="Test Amendment",
            summary="Test summary",
            proposer_id="proposer-001",
            is_core_guarantee=False,
        )
        await service.propose_amendment(request)

        # Check vote eligibility (should be blocked)
        result, blocked_event = await service.check_vote_eligibility("AMD-001")

        assert result.is_eligible is False
        assert result.days_remaining > 0
        assert result.days_remaining <= VISIBILITY_PERIOD_DAYS
        assert "FR126" in result.reason
        assert blocked_event is not None
        assert "FR126" in blocked_event.blocked_reason

    @pytest.mark.asyncio
    async def test_vote_allowed_after_14_days(
        self, service: AmendmentVisibilityService, repository: AmendmentRepositoryStub
    ) -> None:
        """Test FR126: Vote allowed after 14-day visibility period complete.

        Given: An amendment past 14-day visibility period
        When: Vote eligibility is checked
        Then: Vote is allowed
        """
        # Create amendment that's already past visibility period
        past = datetime.now(timezone.utc) - timedelta(days=15)

        amendment = AmendmentProposal(
            amendment_id="AMD-001",
            amendment_type=AmendmentType.TIER_2_CONSTITUTIONAL,
            title="Test",
            summary="Test",
            proposed_at=past,
            visible_from=past,
            votable_from=past + timedelta(days=VISIBILITY_PERIOD_DAYS),
            proposer_id="proposer-001",
            is_core_guarantee=False,
            affected_guarantees=(),
            status=AmendmentStatus.VISIBILITY_PERIOD,
        )
        await repository.save_amendment(amendment)

        # Check vote eligibility (should be allowed)
        result, blocked_event = await service.check_vote_eligibility("AMD-001")

        assert result.is_eligible is True
        assert result.days_remaining == 0
        assert blocked_event is None


class TestFR127ImpactAnalysis:
    """Integration tests for FR127: Impact analysis for core guarantee amendments."""

    @pytest.mark.asyncio
    async def test_ac3_core_guarantee_requires_impact_analysis(
        self, service: AmendmentVisibilityService
    ) -> None:
        """Test AC3: Core guarantee amendment -> impact analysis required.

        Given: A core guarantee amendment without impact analysis
        When: The proposal is submitted
        Then: Submission is rejected with FR127 error
        """
        request = AmendmentProposalRequest(
            amendment_id="AMD-001",
            amendment_type=AmendmentType.TIER_3_CONVENTION,
            title="Modify halt recovery policy",
            summary="Change recovery waiting period from 48 to 72 hours",
            proposer_id="proposer-001",
            is_core_guarantee=True,
            affected_guarantees=("CT-11", "FR21"),  # Not targeting FR126/FR128
            # Missing impact_analysis!
        )

        with pytest.raises(AmendmentImpactAnalysisMissingError) as exc_info:
            await service.propose_amendment(request)

        assert exc_info.value.amendment_id == "AMD-001"
        assert exc_info.value.affected_guarantees == ("CT-11", "FR21")

    @pytest.mark.asyncio
    async def test_core_guarantee_with_impact_analysis_succeeds(
        self, service: AmendmentVisibilityService
    ) -> None:
        """Test FR127: Core guarantee with impact analysis succeeds.

        Given: A core guarantee amendment with complete impact analysis
        When: The proposal is submitted
        Then: Submission succeeds
        """
        now = datetime.now(timezone.utc)
        impact_analysis = AmendmentImpactAnalysis(
            reduces_visibility=True,
            raises_silence_probability=False,
            weakens_irreversibility=False,
            analysis_text="This amendment affects visibility by changing audit log retention policy. "
            "The change reduces the retention period from 7 years to 5 years.",
            analyzed_by="analyst-001",
            analyzed_at=now,
        )

        request = AmendmentProposalRequest(
            amendment_id="AMD-001",
            amendment_type=AmendmentType.TIER_3_CONVENTION,
            title="Modify visibility guarantees",
            summary="Change audit log retention from 7 years to 5 years",
            proposer_id="proposer-001",
            is_core_guarantee=True,
            impact_analysis=impact_analysis,
            affected_guarantees=("CT-11",),
        )

        proposal, event = await service.propose_amendment(request)

        assert proposal.is_core_guarantee is True
        assert proposal.impact_analysis is not None
        assert proposal.impact_analysis.reduces_visibility is True


class TestFR128HistoryProtection:
    """Integration tests for FR128: Amendment history cannot be hidden."""

    @pytest.mark.asyncio
    async def test_ac4_history_hiding_rejected(
        self, service: AmendmentVisibilityService
    ) -> None:
        """Test AC4: Amendment attempting to hide history -> rejected.

        Given: An amendment with history-hiding intent
        When: The proposal is submitted
        Then: Submission is rejected with FR128 error
        """
        request = AmendmentProposalRequest(
            amendment_id="AMD-001",
            amendment_type=AmendmentType.TIER_2_CONSTITUTIONAL,
            title="Amendment visibility changes",
            summary="This amendment will make previous amendments unreviewable for efficiency",
            proposer_id="proposer-001",
            is_core_guarantee=False,
        )

        with pytest.raises(AmendmentHistoryProtectionError) as exc_info:
            await service.propose_amendment(request)

        assert exc_info.value.amendment_id == "AMD-001"

    @pytest.mark.asyncio
    async def test_history_hiding_keywords_detected(
        self, service: AmendmentVisibilityService
    ) -> None:
        """Test FR128: Various history-hiding keywords are detected.

        Given: Amendments with different history-hiding keywords
        When: The proposals are submitted
        Then: All are rejected
        """
        hiding_summaries = [
            "We need to hide previous amendments for security",
            "This will restrict access to amendments from before 2025",
            "Making old amendments unreviewable saves storage space",
            "We should delete amendment history older than 1 year",
        ]

        for i, summary in enumerate(hiding_summaries):
            request = AmendmentProposalRequest(
                amendment_id=f"AMD-00{i + 1}",
                amendment_type=AmendmentType.TIER_2_CONSTITUTIONAL,
                title=f"Test Amendment {i + 1}",
                summary=summary,
                proposer_id="proposer-001",
                is_core_guarantee=False,
            )

            with pytest.raises(AmendmentHistoryProtectionError):
                await service.propose_amendment(request)


class TestAC5ObserverQueries:
    """Integration tests for AC5: Observer queries with visibility countdown."""

    @pytest.mark.asyncio
    async def test_ac5_pending_amendments_show_countdown(
        self, service: AmendmentVisibilityService, repository: AmendmentRepositoryStub
    ) -> None:
        """Test AC5: Pending amendments queryable with visibility countdown.

        Given: Multiple amendments at different stages
        When: Observers query pending amendments
        Then: Results include days until votable
        """
        # Create amendments at different stages
        now = datetime.now(timezone.utc)

        # Amendment just proposed (14 days remaining)
        request1 = AmendmentProposalRequest(
            amendment_id="AMD-001",
            amendment_type=AmendmentType.TIER_2_CONSTITUTIONAL,
            title="New Amendment",
            summary="Just proposed",
            proposer_id="proposer-001",
            is_core_guarantee=False,
        )
        await service.propose_amendment(request1)

        # Amendment halfway through (7 days remaining)
        past_7_days = now - timedelta(days=7)
        amendment2 = AmendmentProposal(
            amendment_id="AMD-002",
            amendment_type=AmendmentType.TIER_2_CONSTITUTIONAL,
            title="Halfway Amendment",
            summary="Proposed 7 days ago",
            proposed_at=past_7_days,
            visible_from=past_7_days,
            votable_from=past_7_days + timedelta(days=VISIBILITY_PERIOD_DAYS),
            proposer_id="proposer-001",
            is_core_guarantee=False,
            affected_guarantees=(),
            status=AmendmentStatus.VISIBILITY_PERIOD,
        )
        await repository.save_amendment(amendment2)

        # Query pending amendments
        summaries = await service.get_pending_amendments()

        assert len(summaries) == 2

        # Find each by ID
        amd001 = next(s for s in summaries if s.amendment_id == "AMD-001")
        amd002 = next(s for s in summaries if s.amendment_id == "AMD-002")

        # Verify countdowns
        assert amd001.days_until_votable >= 13  # Just proposed
        assert 6 <= amd002.days_until_votable <= 8  # Halfway through

    @pytest.mark.asyncio
    async def test_full_visibility_status_query(
        self, service: AmendmentVisibilityService, repository: AmendmentRepositoryStub
    ) -> None:
        """Test AC5: Full visibility status includes all context.

        Given: An amendment in visibility period
        When: Full status is queried
        Then: Response includes proposal, votability, days remaining, status message
        """
        request = AmendmentProposalRequest(
            amendment_id="AMD-001",
            amendment_type=AmendmentType.TIER_2_CONSTITUTIONAL,
            title="Test Amendment",
            summary="Test summary",
            proposer_id="proposer-001",
            is_core_guarantee=False,
        )
        await service.propose_amendment(request)

        result = await service.get_amendment_with_visibility_status("AMD-001")

        assert result.proposal.amendment_id == "AMD-001"
        assert result.is_votable is False
        assert result.days_remaining > 0
        assert "days remaining" in result.visibility_status


class TestHaltCheckIntegration:
    """Integration tests for CT-11: HALT CHECK FIRST."""

    @pytest.mark.asyncio
    async def test_all_operations_blocked_when_halted(
        self, halt_checker: HaltCheckerStub, service: AmendmentVisibilityService
    ) -> None:
        """Test CT-11: All operations blocked when system is halted.

        Given: System is in halted state
        When: Any amendment operation is attempted
        Then: Operation is blocked with SystemHaltedError
        """
        halt_checker.set_halted(True)

        request = AmendmentProposalRequest(
            amendment_id="AMD-001",
            amendment_type=AmendmentType.TIER_2_CONSTITUTIONAL,
            title="Test",
            summary="Test",
            proposer_id="proposer-001",
            is_core_guarantee=False,
        )

        # All operations should fail
        with pytest.raises(SystemHaltedError):
            await service.propose_amendment(request)

        with pytest.raises(SystemHaltedError):
            await service.check_vote_eligibility("AMD-001")

        with pytest.raises(SystemHaltedError):
            await service.get_pending_amendments()

        with pytest.raises(SystemHaltedError):
            await service.get_amendment_with_visibility_status("AMD-001")

        with pytest.raises(SystemHaltedError):
            await service.validate_amendment_submission(request)


class TestFullWorkflow:
    """Integration tests for full amendment workflow."""

    @pytest.mark.asyncio
    async def test_full_amendment_lifecycle(
        self, service: AmendmentVisibilityService, repository: AmendmentRepositoryStub
    ) -> None:
        """Test complete amendment lifecycle from proposal to rejection.

        1. Submit amendment (starts visibility period)
        2. Check vote eligibility (blocked during visibility)
        3. Query pending amendments (shows countdown)
        4. Simulate time passing (14 days)
        5. Check vote eligibility (now allowed)
        """
        # Step 1: Submit amendment
        request = AmendmentProposalRequest(
            amendment_id="AMD-001",
            amendment_type=AmendmentType.TIER_2_CONSTITUTIONAL,
            title="Test Amendment",
            summary="A valid amendment for testing the full lifecycle",
            proposer_id="proposer-001",
            is_core_guarantee=False,
        )
        proposal, event = await service.propose_amendment(request)

        assert proposal.status == AmendmentStatus.VISIBILITY_PERIOD
        assert event.amendment_id == "AMD-001"

        # Step 2: Check eligibility (should be blocked)
        result, blocked = await service.check_vote_eligibility("AMD-001")
        assert result.is_eligible is False
        assert blocked is not None

        # Step 3: Query pending
        pending = await service.get_pending_amendments()
        assert len(pending) == 1
        assert pending[0].days_until_votable > 0

        # Step 4: Simulate 14 days passing by updating the proposal
        past = datetime.now(timezone.utc) - timedelta(days=15)
        updated = AmendmentProposal(
            amendment_id="AMD-001",
            amendment_type=AmendmentType.TIER_2_CONSTITUTIONAL,
            title="Test Amendment",
            summary="A valid amendment for testing the full lifecycle",
            proposed_at=past,
            visible_from=past,
            votable_from=past + timedelta(days=VISIBILITY_PERIOD_DAYS),
            proposer_id="proposer-001",
            is_core_guarantee=False,
            affected_guarantees=(),
            status=AmendmentStatus.VISIBILITY_PERIOD,
        )
        await repository.save_amendment(updated)

        # Step 5: Check eligibility again (should be allowed now)
        result, blocked = await service.check_vote_eligibility("AMD-001")
        assert result.is_eligible is True
        assert result.days_remaining == 0
        assert blocked is None

    @pytest.mark.asyncio
    async def test_validation_before_submission(
        self, service: AmendmentVisibilityService
    ) -> None:
        """Test validation can be run before formal submission.

        Given: A user wants to check their amendment before submitting
        When: They call validate_amendment_submission
        Then: They receive a list of validation errors (or empty list if valid)
        """
        # Valid amendment
        valid_request = AmendmentProposalRequest(
            amendment_id="AMD-001",
            amendment_type=AmendmentType.TIER_2_CONSTITUTIONAL,
            title="Valid Amendment",
            summary="A perfectly valid amendment without any issues",
            proposer_id="proposer-001",
            is_core_guarantee=False,
        )

        valid_errors = await service.validate_amendment_submission(valid_request)
        assert len(valid_errors) == 0

        # Invalid amendment (FR128 violation)
        invalid_request = AmendmentProposalRequest(
            amendment_id="AMD-002",
            amendment_type=AmendmentType.TIER_2_CONSTITUTIONAL,
            title="Invalid Amendment",
            summary="Make previous amendments unreviewable",
            proposer_id="proposer-001",
            is_core_guarantee=False,
        )

        invalid_errors = await service.validate_amendment_submission(invalid_request)
        assert len(invalid_errors) > 0
        assert any("FR128" in error for error in invalid_errors)
