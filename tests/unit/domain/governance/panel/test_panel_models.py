"""Unit tests for Prince Panel domain models.

Story: consent-gov-6-4: Prince Panel Domain Model

Tests cover:
- PanelStatus enum
- MemberStatus enum
- PanelMember model
- RemedyType enum (corrective, not punitive)
- Determination enum
- Dissent model
- PanelFinding model
- PrincePanel model with composition validation

Constitutional Truths:
- CT-12: Witnessing creates accountability
- No punitive remedies (dignity preservation)
- Dissent preserved alongside findings (FR39)

References:
    - FR36: Human Operator can convene panel (≥3 members)
    - FR37: Prince Panel can review witness artifacts
    - FR38: Prince Panel can issue formal finding with remedy
    - FR39: Prince Panel can record dissent in finding
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.domain.governance.panel import (
    PanelStatus,
    MemberStatus,
    PanelMember,
    RemedyType,
    Determination,
    Dissent,
    PanelFinding,
    PrincePanel,
    InvalidPanelComposition,
)


class TestPanelStatus:
    """Tests for PanelStatus enum."""

    def test_convened_status_exists(self) -> None:
        """Panel can be in convened status."""
        assert PanelStatus.CONVENED.value == "convened"

    def test_reviewing_status_exists(self) -> None:
        """Panel can be reviewing artifacts."""
        assert PanelStatus.REVIEWING.value == "reviewing"

    def test_deliberating_status_exists(self) -> None:
        """Panel can be deliberating."""
        assert PanelStatus.DELIBERATING.value == "deliberating"

    def test_finding_issued_status_exists(self) -> None:
        """Panel can have issued finding."""
        assert PanelStatus.FINDING_ISSUED.value == "finding_issued"

    def test_disbanded_status_exists(self) -> None:
        """Panel can be disbanded."""
        assert PanelStatus.DISBANDED.value == "disbanded"


class TestMemberStatus:
    """Tests for MemberStatus enum."""

    def test_active_status_exists(self) -> None:
        """Member can be active."""
        assert MemberStatus.ACTIVE.value == "active"

    def test_recused_status_exists(self) -> None:
        """Member can be recused."""
        assert MemberStatus.RECUSED.value == "recused"


class TestPanelMember:
    """Tests for PanelMember model."""

    def test_create_active_member(self) -> None:
        """Can create an active panel member."""
        member_id = uuid4()
        joined_at = datetime.now(timezone.utc)

        member = PanelMember(
            member_id=member_id,
            joined_at=joined_at,
            status=MemberStatus.ACTIVE,
            recusal_reason=None,
        )

        assert member.member_id == member_id
        assert member.joined_at == joined_at
        assert member.status == MemberStatus.ACTIVE
        assert member.recusal_reason is None

    def test_create_recused_member(self) -> None:
        """Can create a recused member with reason."""
        member = PanelMember(
            member_id=uuid4(),
            joined_at=datetime.now(timezone.utc),
            status=MemberStatus.RECUSED,
            recusal_reason="Conflict of interest",
        )

        assert member.status == MemberStatus.RECUSED
        assert member.recusal_reason == "Conflict of interest"

    def test_member_is_immutable(self) -> None:
        """PanelMember is frozen dataclass."""
        member = PanelMember(
            member_id=uuid4(),
            joined_at=datetime.now(timezone.utc),
            status=MemberStatus.ACTIVE,
            recusal_reason=None,
        )

        with pytest.raises(AttributeError):
            member.status = MemberStatus.RECUSED  # type: ignore

    def test_members_with_same_id_are_equal(self) -> None:
        """Members with same ID are equal."""
        member_id = uuid4()
        joined_at = datetime.now(timezone.utc)

        member1 = PanelMember(
            member_id=member_id,
            joined_at=joined_at,
            status=MemberStatus.ACTIVE,
            recusal_reason=None,
        )
        member2 = PanelMember(
            member_id=member_id,
            joined_at=joined_at,
            status=MemberStatus.ACTIVE,
            recusal_reason=None,
        )

        assert member1 == member2


class TestRemedyType:
    """Tests for RemedyType enum.

    Remedies are CORRECTIVE, not PUNITIVE per dignity preservation.
    """

    def test_warning_remedy_exists(self) -> None:
        """WARNING: Formal notice."""
        assert RemedyType.WARNING.value == "warning"

    def test_correction_remedy_exists(self) -> None:
        """CORRECTION: Require action change."""
        assert RemedyType.CORRECTION.value == "correction"

    def test_escalation_remedy_exists(self) -> None:
        """ESCALATION: Route to higher authority."""
        assert RemedyType.ESCALATION.value == "escalation"

    def test_halt_recommendation_remedy_exists(self) -> None:
        """HALT_RECOMMENDATION: Recommend system halt."""
        assert RemedyType.HALT_RECOMMENDATION.value == "halt_recommendation"

    def test_no_punitive_remedies(self) -> None:
        """No punitive remedy types exist (dignity preservation).

        Explicitly verify that punitive remedies are NOT available:
        - REPUTATION_PENALTY
        - ACCESS_RESTRICTION
        - PUNITIVE_FINE
        """
        remedy_values = [r.value for r in RemedyType]

        # These MUST NOT exist
        assert "reputation_penalty" not in remedy_values
        assert "access_restriction" not in remedy_values
        assert "punitive_fine" not in remedy_values
        assert "punishment" not in remedy_values
        assert "penalty" not in remedy_values

    def test_exactly_four_remedy_types(self) -> None:
        """Only 4 corrective remedy types exist."""
        assert len(RemedyType) == 4


class TestDetermination:
    """Tests for Determination enum."""

    def test_violation_found(self) -> None:
        """Determination can be violation found."""
        assert Determination.VIOLATION_FOUND.value == "violation_found"

    def test_no_violation(self) -> None:
        """Determination can be no violation."""
        assert Determination.NO_VIOLATION.value == "no_violation"

    def test_insufficient_evidence(self) -> None:
        """Determination can be insufficient evidence."""
        assert Determination.INSUFFICIENT_EVIDENCE.value == "insufficient_evidence"


class TestDissent:
    """Tests for Dissent model."""

    def test_create_dissent(self) -> None:
        """Can create a dissent with members and rationale."""
        member_id = uuid4()
        dissent = Dissent(
            dissenting_member_ids=[member_id],
            rationale="I disagree because the evidence was inconclusive.",
        )

        assert member_id in dissent.dissenting_member_ids
        assert "disagree" in dissent.rationale

    def test_dissent_multiple_members(self) -> None:
        """Multiple members can dissent."""
        member1 = uuid4()
        member2 = uuid4()
        dissent = Dissent(
            dissenting_member_ids=[member1, member2],
            rationale="We both disagree for the same reason.",
        )

        assert len(dissent.dissenting_member_ids) == 2

    def test_dissent_is_immutable(self) -> None:
        """Dissent is frozen dataclass."""
        dissent = Dissent(
            dissenting_member_ids=[uuid4()],
            rationale="Disagreement recorded.",
        )

        with pytest.raises(AttributeError):
            dissent.rationale = "Changed rationale"  # type: ignore


class TestPanelFinding:
    """Tests for PanelFinding model."""

    def test_create_finding_with_violation(self) -> None:
        """Can create finding with violation and remedy."""
        finding = PanelFinding(
            finding_id=uuid4(),
            panel_id=uuid4(),
            statement_id=uuid4(),
            determination=Determination.VIOLATION_FOUND,
            remedy=RemedyType.CORRECTION,
            majority_rationale="Evidence clearly shows violation occurred.",
            dissent=None,
            issued_at=datetime.now(timezone.utc),
            voting_record={uuid4(): "violation", uuid4(): "violation", uuid4(): "no_violation"},
        )

        assert finding.determination == Determination.VIOLATION_FOUND
        assert finding.remedy == RemedyType.CORRECTION
        assert finding.dissent is None

    def test_create_finding_no_violation(self) -> None:
        """Can create finding with no violation."""
        finding = PanelFinding(
            finding_id=uuid4(),
            panel_id=uuid4(),
            statement_id=uuid4(),
            determination=Determination.NO_VIOLATION,
            remedy=None,
            majority_rationale="No violation found.",
            dissent=None,
            issued_at=datetime.now(timezone.utc),
            voting_record={uuid4(): "no_violation"},
        )

        assert finding.determination == Determination.NO_VIOLATION
        assert finding.remedy is None

    def test_finding_with_dissent(self) -> None:
        """Can create finding with dissent (FR39)."""
        dissenting_member = uuid4()
        dissent = Dissent(
            dissenting_member_ids=[dissenting_member],
            rationale="I disagree because...",
        )

        finding = PanelFinding(
            finding_id=uuid4(),
            panel_id=uuid4(),
            statement_id=uuid4(),
            determination=Determination.VIOLATION_FOUND,
            remedy=RemedyType.WARNING,
            majority_rationale="Majority believes violation occurred.",
            dissent=dissent,
            issued_at=datetime.now(timezone.utc),
            voting_record={
                uuid4(): "violation",
                uuid4(): "violation",
                dissenting_member: "no_violation",
            },
        )

        assert finding.dissent is not None
        assert len(finding.dissent.dissenting_member_ids) == 1

    def test_finding_is_immutable(self) -> None:
        """PanelFinding is frozen dataclass."""
        finding = PanelFinding(
            finding_id=uuid4(),
            panel_id=uuid4(),
            statement_id=uuid4(),
            determination=Determination.NO_VIOLATION,
            remedy=None,
            majority_rationale="No violation.",
            dissent=None,
            issued_at=datetime.now(timezone.utc),
            voting_record={},
        )

        with pytest.raises(AttributeError):
            finding.determination = Determination.VIOLATION_FOUND  # type: ignore

    def test_finding_voting_record_captures_all_votes(self) -> None:
        """Voting record captures member votes for audit."""
        m1, m2, m3 = uuid4(), uuid4(), uuid4()
        voting_record = {
            m1: "violation",
            m2: "violation",
            m3: "no_violation",
        }

        finding = PanelFinding(
            finding_id=uuid4(),
            panel_id=uuid4(),
            statement_id=uuid4(),
            determination=Determination.VIOLATION_FOUND,
            remedy=RemedyType.CORRECTION,
            majority_rationale="2-1 majority.",
            dissent=Dissent(dissenting_member_ids=[m3], rationale="Disagree."),
            issued_at=datetime.now(timezone.utc),
            voting_record=voting_record,
        )

        assert finding.voting_record[m1] == "violation"
        assert finding.voting_record[m3] == "no_violation"


class TestPrincePanel:
    """Tests for PrincePanel model."""

    def _create_active_member(self) -> PanelMember:
        """Helper to create an active panel member."""
        return PanelMember(
            member_id=uuid4(),
            joined_at=datetime.now(timezone.utc),
            status=MemberStatus.ACTIVE,
            recusal_reason=None,
        )

    def _create_recused_member(self, reason: str = "Conflict") -> PanelMember:
        """Helper to create a recused panel member."""
        return PanelMember(
            member_id=uuid4(),
            joined_at=datetime.now(timezone.utc),
            status=MemberStatus.RECUSED,
            recusal_reason=reason,
        )

    def test_panel_requires_minimum_three_members(self) -> None:
        """Panel must have ≥3 active members (FR36/AC1)."""
        with pytest.raises(InvalidPanelComposition) as exc_info:
            PrincePanel(
                panel_id=uuid4(),
                convened_by=uuid4(),
                members=(self._create_active_member(), self._create_active_member()),
                statement_under_review=uuid4(),
                status=PanelStatus.CONVENED,
                convened_at=datetime.now(timezone.utc),
                finding=None,
            )

        assert "3" in str(exc_info.value)
        assert "2" in str(exc_info.value)

    def test_panel_allows_three_members(self) -> None:
        """Panel accepts exactly 3 active members."""
        panel = PrincePanel(
            panel_id=uuid4(),
            convened_by=uuid4(),
            members=(
                self._create_active_member(),
                self._create_active_member(),
                self._create_active_member(),
            ),
            statement_under_review=uuid4(),
            status=PanelStatus.CONVENED,
            convened_at=datetime.now(timezone.utc),
            finding=None,
        )

        assert len(panel.members) == 3

    def test_panel_allows_more_than_three_members(self) -> None:
        """Panel accepts more than 3 active members."""
        panel = PrincePanel(
            panel_id=uuid4(),
            convened_by=uuid4(),
            members=tuple(self._create_active_member() for _ in range(5)),
            statement_under_review=uuid4(),
            status=PanelStatus.CONVENED,
            convened_at=datetime.now(timezone.utc),
            finding=None,
        )

        assert len(panel.members) == 5

    def test_panel_rejects_single_member(self) -> None:
        """Panel rejects single member."""
        with pytest.raises(InvalidPanelComposition):
            PrincePanel(
                panel_id=uuid4(),
                convened_by=uuid4(),
                members=(self._create_active_member(),),
                statement_under_review=uuid4(),
                status=PanelStatus.CONVENED,
                convened_at=datetime.now(timezone.utc),
                finding=None,
            )

    def test_panel_rejects_zero_members(self) -> None:
        """Panel rejects zero members."""
        with pytest.raises(InvalidPanelComposition):
            PrincePanel(
                panel_id=uuid4(),
                convened_by=uuid4(),
                members=(),
                statement_under_review=uuid4(),
                status=PanelStatus.CONVENED,
                convened_at=datetime.now(timezone.utc),
                finding=None,
            )

    def test_active_members_property(self) -> None:
        """active_members property returns only non-recused members."""
        active1 = self._create_active_member()
        active2 = self._create_active_member()
        active3 = self._create_active_member()
        recused = self._create_recused_member()

        panel = PrincePanel(
            panel_id=uuid4(),
            convened_by=uuid4(),
            members=(active1, active2, active3, recused),
            statement_under_review=uuid4(),
            status=PanelStatus.CONVENED,
            convened_at=datetime.now(timezone.utc),
            finding=None,
        )

        active_members = panel.active_members
        assert len(active_members) == 3
        assert recused not in active_members

    def test_quorum_is_majority_of_active(self) -> None:
        """Quorum is majority of active members."""
        # 5 active members -> quorum is 3
        panel = PrincePanel(
            panel_id=uuid4(),
            convened_by=uuid4(),
            members=tuple(self._create_active_member() for _ in range(5)),
            statement_under_review=uuid4(),
            status=PanelStatus.CONVENED,
            convened_at=datetime.now(timezone.utc),
            finding=None,
        )

        assert panel.quorum == 3  # (5 // 2) + 1

    def test_quorum_for_three_members(self) -> None:
        """Quorum for 3 members is 2."""
        panel = PrincePanel(
            panel_id=uuid4(),
            convened_by=uuid4(),
            members=tuple(self._create_active_member() for _ in range(3)),
            statement_under_review=uuid4(),
            status=PanelStatus.CONVENED,
            convened_at=datetime.now(timezone.utc),
            finding=None,
        )

        assert panel.quorum == 2  # (3 // 2) + 1

    def test_can_issue_finding_when_reviewing(self) -> None:
        """Panel can issue finding when in REVIEWING status."""
        panel = PrincePanel(
            panel_id=uuid4(),
            convened_by=uuid4(),
            members=tuple(self._create_active_member() for _ in range(3)),
            statement_under_review=uuid4(),
            status=PanelStatus.REVIEWING,
            convened_at=datetime.now(timezone.utc),
            finding=None,
        )

        assert panel.can_issue_finding() is True

    def test_can_issue_finding_when_deliberating(self) -> None:
        """Panel can issue finding when in DELIBERATING status."""
        panel = PrincePanel(
            panel_id=uuid4(),
            convened_by=uuid4(),
            members=tuple(self._create_active_member() for _ in range(3)),
            statement_under_review=uuid4(),
            status=PanelStatus.DELIBERATING,
            convened_at=datetime.now(timezone.utc),
            finding=None,
        )

        assert panel.can_issue_finding() is True

    def test_cannot_issue_finding_when_convened(self) -> None:
        """Panel cannot issue finding when just convened."""
        panel = PrincePanel(
            panel_id=uuid4(),
            convened_by=uuid4(),
            members=tuple(self._create_active_member() for _ in range(3)),
            statement_under_review=uuid4(),
            status=PanelStatus.CONVENED,
            convened_at=datetime.now(timezone.utc),
            finding=None,
        )

        assert panel.can_issue_finding() is False

    def test_cannot_issue_finding_when_disbanded(self) -> None:
        """Panel cannot issue finding when disbanded."""
        panel = PrincePanel(
            panel_id=uuid4(),
            convened_by=uuid4(),
            members=tuple(self._create_active_member() for _ in range(3)),
            statement_under_review=uuid4(),
            status=PanelStatus.DISBANDED,
            convened_at=datetime.now(timezone.utc),
            finding=None,
        )

        assert panel.can_issue_finding() is False

    def test_panel_is_immutable(self) -> None:
        """PrincePanel is frozen dataclass."""
        panel = PrincePanel(
            panel_id=uuid4(),
            convened_by=uuid4(),
            members=tuple(self._create_active_member() for _ in range(3)),
            statement_under_review=uuid4(),
            status=PanelStatus.CONVENED,
            convened_at=datetime.now(timezone.utc),
            finding=None,
        )

        with pytest.raises(AttributeError):
            panel.status = PanelStatus.REVIEWING  # type: ignore

    def test_recused_members_dont_count_toward_minimum(self) -> None:
        """Recused members don't count toward minimum 3 active (AC6)."""
        with pytest.raises(InvalidPanelComposition):
            PrincePanel(
                panel_id=uuid4(),
                convened_by=uuid4(),
                members=(
                    self._create_active_member(),
                    self._create_active_member(),
                    self._create_recused_member(),
                    self._create_recused_member(),
                ),
                statement_under_review=uuid4(),
                status=PanelStatus.CONVENED,
                convened_at=datetime.now(timezone.utc),
                finding=None,
            )

    def test_panel_with_finding(self) -> None:
        """Panel can have an attached finding."""
        panel_id = uuid4()
        finding = PanelFinding(
            finding_id=uuid4(),
            panel_id=panel_id,
            statement_id=uuid4(),
            determination=Determination.VIOLATION_FOUND,
            remedy=RemedyType.WARNING,
            majority_rationale="Test rationale.",
            dissent=None,
            issued_at=datetime.now(timezone.utc),
            voting_record={},
        )

        panel = PrincePanel(
            panel_id=panel_id,
            convened_by=uuid4(),
            members=tuple(self._create_active_member() for _ in range(3)),
            statement_under_review=uuid4(),
            status=PanelStatus.FINDING_ISSUED,
            convened_at=datetime.now(timezone.utc),
            finding=finding,
        )

        assert panel.finding is not None
        assert panel.finding.determination == Determination.VIOLATION_FOUND

    def test_human_operator_convenes_panel(self) -> None:
        """Panel records who convened it (Human Operator per AC2)."""
        convener_id = uuid4()

        panel = PrincePanel(
            panel_id=uuid4(),
            convened_by=convener_id,
            members=tuple(self._create_active_member() for _ in range(3)),
            statement_under_review=uuid4(),
            status=PanelStatus.CONVENED,
            convened_at=datetime.now(timezone.utc),
            finding=None,
        )

        assert panel.convened_by == convener_id


class TestInvalidPanelComposition:
    """Tests for InvalidPanelComposition exception."""

    def test_exception_inherits_from_value_error(self) -> None:
        """InvalidPanelComposition is a ValueError."""
        exc = InvalidPanelComposition("test message")
        assert isinstance(exc, ValueError)

    def test_exception_contains_message(self) -> None:
        """Exception contains descriptive message."""
        exc = InvalidPanelComposition("Panel requires ≥3 members")
        assert "3" in str(exc)
