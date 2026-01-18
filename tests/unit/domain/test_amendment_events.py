"""Unit tests for amendment visibility events (Story 6.7, FR126-FR128)."""

import json
from datetime import datetime, timedelta, timezone

import pytest

from src.domain.events.amendment import (
    AMENDMENT_PROPOSED_EVENT_TYPE,
    AMENDMENT_REJECTED_EVENT_TYPE,
    AMENDMENT_VOTE_BLOCKED_EVENT_TYPE,
    VISIBILITY_PERIOD_DAYS,
    AmendmentImpactAnalysis,
    AmendmentProposedEventPayload,
    AmendmentRejectedEventPayload,
    AmendmentStatus,
    AmendmentType,
    AmendmentVoteBlockedEventPayload,
)


class TestAmendmentType:
    """Tests for AmendmentType enum."""

    def test_tier_2_constitutional_value(self) -> None:
        """Test TIER_2_CONSTITUTIONAL enum value."""
        assert AmendmentType.TIER_2_CONSTITUTIONAL.value == "tier_2_constitutional"

    def test_tier_3_convention_value(self) -> None:
        """Test TIER_3_CONVENTION enum value."""
        assert AmendmentType.TIER_3_CONVENTION.value == "tier_3_convention"


class TestAmendmentStatus:
    """Tests for AmendmentStatus enum."""

    def test_proposed_value(self) -> None:
        """Test PROPOSED enum value."""
        assert AmendmentStatus.PROPOSED.value == "proposed"

    def test_visibility_period_value(self) -> None:
        """Test VISIBILITY_PERIOD enum value."""
        assert AmendmentStatus.VISIBILITY_PERIOD.value == "visibility_period"

    def test_votable_value(self) -> None:
        """Test VOTABLE enum value."""
        assert AmendmentStatus.VOTABLE.value == "votable"

    def test_voting_value(self) -> None:
        """Test VOTING enum value."""
        assert AmendmentStatus.VOTING.value == "voting"

    def test_approved_value(self) -> None:
        """Test APPROVED enum value."""
        assert AmendmentStatus.APPROVED.value == "approved"

    def test_rejected_value(self) -> None:
        """Test REJECTED enum value."""
        assert AmendmentStatus.REJECTED.value == "rejected"


class TestVisibilityPeriodDays:
    """Tests for visibility period constant (FR126)."""

    def test_visibility_period_is_14_days(self) -> None:
        """Test FR126: Visibility period is 14 days."""
        assert VISIBILITY_PERIOD_DAYS == 14


class TestAmendmentImpactAnalysis:
    """Tests for AmendmentImpactAnalysis (FR127)."""

    def test_create_with_all_fields(self) -> None:
        """Test creation with all FR127 required fields."""
        now = datetime.now(timezone.utc)
        analysis = AmendmentImpactAnalysis(
            reduces_visibility=True,
            raises_silence_probability=False,
            weakens_irreversibility=False,
            analysis_text="This amendment affects visibility by changing logging requirements. "
            * 2,
            analyzed_by="analyst-001",
            analyzed_at=now,
        )

        assert analysis.reduces_visibility is True
        assert analysis.raises_silence_probability is False
        assert analysis.weakens_irreversibility is False
        assert "visibility" in analysis.analysis_text
        assert analysis.analyzed_by == "analyst-001"
        assert analysis.analyzed_at == now

    def test_analysis_text_minimum_length(self) -> None:
        """Test FR127: Analysis text must be at least 50 characters."""
        now = datetime.now(timezone.utc)
        with pytest.raises(
            ValueError, match="analysis_text must be at least 50 characters"
        ):
            AmendmentImpactAnalysis(
                reduces_visibility=False,
                raises_silence_probability=False,
                weakens_irreversibility=False,
                analysis_text="Too short",
                analyzed_by="analyst-001",
                analyzed_at=now,
            )

    def test_analyzed_by_required(self) -> None:
        """Test FR127: analyzed_by attribution is required."""
        now = datetime.now(timezone.utc)
        with pytest.raises(ValueError, match="analyzed_by must be provided"):
            AmendmentImpactAnalysis(
                reduces_visibility=False,
                raises_silence_probability=False,
                weakens_irreversibility=False,
                analysis_text="This is a valid analysis text that is long enough to pass validation.",
                analyzed_by="",
                analyzed_at=now,
            )

    def test_to_dict(self) -> None:
        """Test serialization to dictionary."""
        now = datetime.now(timezone.utc)
        analysis = AmendmentImpactAnalysis(
            reduces_visibility=True,
            raises_silence_probability=True,
            weakens_irreversibility=False,
            analysis_text="This is a valid analysis text that is long enough to pass validation.",
            analyzed_by="analyst-001",
            analyzed_at=now,
        )

        result = analysis.to_dict()

        assert result["reduces_visibility"] is True
        assert result["raises_silence_probability"] is True
        assert result["weakens_irreversibility"] is False
        assert result["analyzed_by"] == "analyst-001"
        assert result["analyzed_at"] == now.isoformat()


class TestAmendmentProposedEventPayload:
    """Tests for AmendmentProposedEventPayload (FR126, FR127)."""

    def test_create_non_core_guarantee(self) -> None:
        """Test creation for non-core guarantee amendment."""
        now = datetime.now(timezone.utc)
        votable_from = now + timedelta(days=VISIBILITY_PERIOD_DAYS)

        payload = AmendmentProposedEventPayload(
            amendment_id="AMD-001",
            amendment_type=AmendmentType.TIER_2_CONSTITUTIONAL,
            title="Update logging format",
            summary="Change structured log format for better parsing",
            proposed_at=now,
            visible_from=now,
            votable_from=votable_from,
            proposer_id="proposer-001",
            is_core_guarantee=False,
        )

        assert payload.amendment_id == "AMD-001"
        assert payload.amendment_type == AmendmentType.TIER_2_CONSTITUTIONAL
        assert payload.is_core_guarantee is False
        assert payload.impact_analysis is None

    def test_create_core_guarantee_with_analysis(self) -> None:
        """Test FR127: Core guarantee amendment requires impact analysis."""
        now = datetime.now(timezone.utc)
        votable_from = now + timedelta(days=VISIBILITY_PERIOD_DAYS)
        analysis = AmendmentImpactAnalysis(
            reduces_visibility=True,
            raises_silence_probability=False,
            weakens_irreversibility=False,
            analysis_text="This amendment affects visibility by changing audit log retention policy.",
            analyzed_by="analyst-001",
            analyzed_at=now,
        )

        payload = AmendmentProposedEventPayload(
            amendment_id="AMD-002",
            amendment_type=AmendmentType.TIER_3_CONVENTION,
            title="Modify visibility guarantees",
            summary="Change audit log retention from 7 years to 5 years",
            proposed_at=now,
            visible_from=now,
            votable_from=votable_from,
            proposer_id="proposer-001",
            is_core_guarantee=True,
            impact_analysis=analysis,
            affected_guarantees=("CT-11", "FR126"),
        )

        assert payload.is_core_guarantee is True
        assert payload.impact_analysis is not None
        assert payload.affected_guarantees == ("CT-11", "FR126")

    def test_core_guarantee_requires_impact_analysis(self) -> None:
        """Test FR127: Core guarantee without impact analysis raises ValueError."""
        now = datetime.now(timezone.utc)
        votable_from = now + timedelta(days=VISIBILITY_PERIOD_DAYS)

        with pytest.raises(ValueError, match="FR127"):
            AmendmentProposedEventPayload(
                amendment_id="AMD-003",
                amendment_type=AmendmentType.TIER_3_CONVENTION,
                title="Modify visibility guarantees",
                summary="Change audit log retention",
                proposed_at=now,
                visible_from=now,
                votable_from=votable_from,
                proposer_id="proposer-001",
                is_core_guarantee=True,
                # Missing impact_analysis!
            )

    def test_fr126_14_day_visibility_validation(self) -> None:
        """Test FR126: votable_from must be 14 days after visible_from."""
        now = datetime.now(timezone.utc)
        # Wrong votable_from - only 7 days
        wrong_votable_from = now + timedelta(days=7)

        with pytest.raises(ValueError, match="FR126"):
            AmendmentProposedEventPayload(
                amendment_id="AMD-004",
                amendment_type=AmendmentType.TIER_2_CONSTITUTIONAL,
                title="Test amendment",
                summary="Test summary",
                proposed_at=now,
                visible_from=now,
                votable_from=wrong_votable_from,
                proposer_id="proposer-001",
                is_core_guarantee=False,
            )

    def test_amendment_id_required(self) -> None:
        """Test amendment_id is required."""
        now = datetime.now(timezone.utc)
        votable_from = now + timedelta(days=VISIBILITY_PERIOD_DAYS)

        with pytest.raises(ValueError, match="amendment_id must be non-empty"):
            AmendmentProposedEventPayload(
                amendment_id="",
                amendment_type=AmendmentType.TIER_2_CONSTITUTIONAL,
                title="Test",
                summary="Test",
                proposed_at=now,
                visible_from=now,
                votable_from=votable_from,
                proposer_id="proposer-001",
                is_core_guarantee=False,
            )

    def test_signable_content(self) -> None:
        """Test CT-12: signable_content for witnessing."""
        now = datetime.now(timezone.utc)
        votable_from = now + timedelta(days=VISIBILITY_PERIOD_DAYS)

        payload = AmendmentProposedEventPayload(
            amendment_id="AMD-001",
            amendment_type=AmendmentType.TIER_2_CONSTITUTIONAL,
            title="Test amendment",
            summary="Test summary",
            proposed_at=now,
            visible_from=now,
            votable_from=votable_from,
            proposer_id="proposer-001",
            is_core_guarantee=False,
        )

        content = payload.signable_content()

        assert isinstance(content, bytes)
        # Verify it's valid JSON
        decoded = json.loads(content.decode("utf-8"))
        assert decoded["event_type"] == AMENDMENT_PROPOSED_EVENT_TYPE
        assert decoded["amendment_id"] == "AMD-001"

    def test_to_dict(self) -> None:
        """Test serialization to dictionary."""
        now = datetime.now(timezone.utc)
        votable_from = now + timedelta(days=VISIBILITY_PERIOD_DAYS)

        payload = AmendmentProposedEventPayload(
            amendment_id="AMD-001",
            amendment_type=AmendmentType.TIER_2_CONSTITUTIONAL,
            title="Test amendment",
            summary="Test summary",
            proposed_at=now,
            visible_from=now,
            votable_from=votable_from,
            proposer_id="proposer-001",
            is_core_guarantee=False,
        )

        result = payload.to_dict()

        assert result["amendment_id"] == "AMD-001"
        assert result["amendment_type"] == "tier_2_constitutional"
        assert result["proposed_at"] == now.isoformat()

    def test_days_until_votable(self) -> None:
        """Test days_until_votable calculation."""
        now = datetime.now(timezone.utc)
        votable_from = now + timedelta(days=VISIBILITY_PERIOD_DAYS)

        payload = AmendmentProposedEventPayload(
            amendment_id="AMD-001",
            amendment_type=AmendmentType.TIER_2_CONSTITUTIONAL,
            title="Test",
            summary="Test",
            proposed_at=now,
            visible_from=now,
            votable_from=votable_from,
            proposer_id="proposer-001",
            is_core_guarantee=False,
        )

        # Should return days remaining (14 or 15 depending on timing)
        days = payload.days_until_votable
        assert days >= 0
        assert days <= VISIBILITY_PERIOD_DAYS + 1


class TestAmendmentVoteBlockedEventPayload:
    """Tests for AmendmentVoteBlockedEventPayload (FR126)."""

    def test_create_vote_blocked(self) -> None:
        """Test creation of vote blocked event."""
        now = datetime.now(timezone.utc)
        votable_from = now + timedelta(days=10)

        payload = AmendmentVoteBlockedEventPayload(
            amendment_id="AMD-001",
            blocked_reason="FR126: Amendment visibility period incomplete - 10 days remaining",
            days_remaining=10,
            votable_from=votable_from,
            blocked_at=now,
        )

        assert payload.amendment_id == "AMD-001"
        assert "FR126" in payload.blocked_reason
        assert payload.days_remaining == 10
        assert payload.votable_from == votable_from

    def test_amendment_id_required(self) -> None:
        """Test amendment_id is required."""
        now = datetime.now(timezone.utc)
        with pytest.raises(ValueError, match="amendment_id must be non-empty"):
            AmendmentVoteBlockedEventPayload(
                amendment_id="",
                blocked_reason="FR126: Blocked",
                days_remaining=5,
                votable_from=now + timedelta(days=5),
                blocked_at=now,
            )

    def test_days_remaining_non_negative(self) -> None:
        """Test days_remaining must be non-negative."""
        now = datetime.now(timezone.utc)
        with pytest.raises(ValueError, match="days_remaining must be non-negative"):
            AmendmentVoteBlockedEventPayload(
                amendment_id="AMD-001",
                blocked_reason="FR126: Blocked",
                days_remaining=-1,
                votable_from=now,
                blocked_at=now,
            )

    def test_signable_content(self) -> None:
        """Test CT-12: signable_content for witnessing."""
        now = datetime.now(timezone.utc)
        votable_from = now + timedelta(days=5)

        payload = AmendmentVoteBlockedEventPayload(
            amendment_id="AMD-001",
            blocked_reason="FR126: Blocked",
            days_remaining=5,
            votable_from=votable_from,
            blocked_at=now,
        )

        content = payload.signable_content()

        assert isinstance(content, bytes)
        decoded = json.loads(content.decode("utf-8"))
        assert decoded["event_type"] == AMENDMENT_VOTE_BLOCKED_EVENT_TYPE
        assert decoded["amendment_id"] == "AMD-001"


class TestAmendmentRejectedEventPayload:
    """Tests for AmendmentRejectedEventPayload (FR128)."""

    def test_create_rejection(self) -> None:
        """Test creation of rejection event."""
        now = datetime.now(timezone.utc)

        payload = AmendmentRejectedEventPayload(
            amendment_id="AMD-001",
            rejection_reason="FR128: Amendment history cannot be made unreviewable",
            rejected_at=now,
        )

        assert payload.amendment_id == "AMD-001"
        assert "FR128" in payload.rejection_reason
        assert payload.rejected_at == now

    def test_amendment_id_required(self) -> None:
        """Test amendment_id is required."""
        now = datetime.now(timezone.utc)
        with pytest.raises(ValueError, match="amendment_id must be non-empty"):
            AmendmentRejectedEventPayload(
                amendment_id="",
                rejection_reason="FR128: Rejected",
                rejected_at=now,
            )

    def test_rejection_reason_required(self) -> None:
        """Test rejection_reason is required."""
        now = datetime.now(timezone.utc)
        with pytest.raises(ValueError, match="rejection_reason must be non-empty"):
            AmendmentRejectedEventPayload(
                amendment_id="AMD-001",
                rejection_reason="",
                rejected_at=now,
            )

    def test_signable_content(self) -> None:
        """Test CT-12: signable_content for witnessing."""
        now = datetime.now(timezone.utc)

        payload = AmendmentRejectedEventPayload(
            amendment_id="AMD-001",
            rejection_reason="FR128: Amendment history cannot be made unreviewable",
            rejected_at=now,
        )

        content = payload.signable_content()

        assert isinstance(content, bytes)
        decoded = json.loads(content.decode("utf-8"))
        assert decoded["event_type"] == AMENDMENT_REJECTED_EVENT_TYPE
        assert decoded["amendment_id"] == "AMD-001"

    def test_to_dict(self) -> None:
        """Test serialization to dictionary."""
        now = datetime.now(timezone.utc)

        payload = AmendmentRejectedEventPayload(
            amendment_id="AMD-001",
            rejection_reason="FR128: Rejected",
            rejected_at=now,
        )

        result = payload.to_dict()

        assert result["amendment_id"] == "AMD-001"
        assert result["rejection_reason"] == "FR128: Rejected"
        assert result["rejected_at"] == now.isoformat()
