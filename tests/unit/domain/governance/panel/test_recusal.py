"""Unit tests for panel recusal mechanism.

Story: consent-gov-6-4: Prince Panel Domain Model

Tests for the recusal mechanism (AC7):
- Member can recuse from specific case
- Recusal recorded with reason
- Panel still valid if ≥3 active remain
- Panel invalid if <3 active members

References:
    - AC7: Recusal mechanism for conflict of interest
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.domain.governance.panel import (
    PanelMember,
    MemberStatus,
    PrincePanel,
    PanelStatus,
    InvalidPanelComposition,
)
from src.domain.governance.panel.recusal import RecusalRequest


class TestRecusalRequest:
    """Tests for RecusalRequest model."""

    def test_create_recusal_request(self) -> None:
        """Can create a recusal request."""
        request = RecusalRequest(
            request_id=uuid4(),
            panel_id=uuid4(),
            member_id=uuid4(),
            reason="I previously advised on this matter.",
            requested_at=datetime.now(timezone.utc),
        )

        assert request.reason == "I previously advised on this matter."

    def test_recusal_request_is_immutable(self) -> None:
        """RecusalRequest is frozen dataclass."""
        request = RecusalRequest(
            request_id=uuid4(),
            panel_id=uuid4(),
            member_id=uuid4(),
            reason="Conflict of interest.",
            requested_at=datetime.now(timezone.utc),
        )

        with pytest.raises(AttributeError):
            request.reason = "Changed reason"  # type: ignore

    def test_recusal_request_captures_member_id(self) -> None:
        """Recusal request captures which member is recusing."""
        member_id = uuid4()
        request = RecusalRequest(
            request_id=uuid4(),
            panel_id=uuid4(),
            member_id=member_id,
            reason="Conflict.",
            requested_at=datetime.now(timezone.utc),
        )

        assert request.member_id == member_id

    def test_recusal_request_captures_panel_id(self) -> None:
        """Recusal request captures which panel."""
        panel_id = uuid4()
        request = RecusalRequest(
            request_id=uuid4(),
            panel_id=panel_id,
            member_id=uuid4(),
            reason="Conflict.",
            requested_at=datetime.now(timezone.utc),
        )

        assert request.panel_id == panel_id


class TestRecusalMechanics:
    """Tests for recusal mechanics in PrincePanel."""

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

    def test_panel_valid_with_three_active_one_recused(self) -> None:
        """Panel is valid with 3 active + 1 recused (≥3 active)."""
        panel = PrincePanel(
            panel_id=uuid4(),
            convened_by=uuid4(),
            members=(
                self._create_active_member(),
                self._create_active_member(),
                self._create_active_member(),
                self._create_recused_member("Prior involvement"),
            ),
            statement_under_review=uuid4(),
            status=PanelStatus.CONVENED,
            convened_at=datetime.now(timezone.utc),
            finding=None,
        )

        assert len(panel.active_members) == 3
        assert len(panel.members) == 4

    def test_panel_invalid_with_two_active_two_recused(self) -> None:
        """Panel is invalid with 2 active + 2 recused (<3 active)."""
        with pytest.raises(InvalidPanelComposition) as exc_info:
            PrincePanel(
                panel_id=uuid4(),
                convened_by=uuid4(),
                members=(
                    self._create_active_member(),
                    self._create_active_member(),
                    self._create_recused_member("Prior involvement"),
                    self._create_recused_member("Financial interest"),
                ),
                statement_under_review=uuid4(),
                status=PanelStatus.CONVENED,
                convened_at=datetime.now(timezone.utc),
                finding=None,
            )

        assert "2" in str(exc_info.value)

    def test_recused_member_has_reason(self) -> None:
        """Recused member records the reason."""
        reason = "I advised the complainant previously"
        member = PanelMember(
            member_id=uuid4(),
            joined_at=datetime.now(timezone.utc),
            status=MemberStatus.RECUSED,
            recusal_reason=reason,
        )

        assert member.recusal_reason == reason

    def test_active_member_has_no_recusal_reason(self) -> None:
        """Active member has no recusal reason."""
        member = self._create_active_member()
        assert member.recusal_reason is None

    def test_can_issue_finding_respects_recusal(self) -> None:
        """can_issue_finding() only counts active members."""
        # 4 members, 1 recused -> 3 active -> can issue
        panel = PrincePanel(
            panel_id=uuid4(),
            convened_by=uuid4(),
            members=(
                self._create_active_member(),
                self._create_active_member(),
                self._create_active_member(),
                self._create_recused_member(),
            ),
            statement_under_review=uuid4(),
            status=PanelStatus.REVIEWING,
            convened_at=datetime.now(timezone.utc),
            finding=None,
        )

        assert panel.can_issue_finding() is True

    def test_quorum_calculation_excludes_recused(self) -> None:
        """Quorum is calculated from active members only."""
        # 5 members, 2 recused -> 3 active -> quorum is 2
        panel = PrincePanel(
            panel_id=uuid4(),
            convened_by=uuid4(),
            members=(
                self._create_active_member(),
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

        assert panel.quorum == 2  # (3 // 2) + 1


class TestRecusalScenarios:
    """Integration-style tests for recusal scenarios."""

    def _create_active_member(self) -> PanelMember:
        """Helper to create an active panel member."""
        return PanelMember(
            member_id=uuid4(),
            joined_at=datetime.now(timezone.utc),
            status=MemberStatus.ACTIVE,
            recusal_reason=None,
        )

    def test_simulate_recusal_transition(self) -> None:
        """Simulate recusal by creating new panel with updated member.

        Since domain models are immutable, recusal creates a new panel.
        """
        # Original panel with 4 active members
        member1 = self._create_active_member()
        member2 = self._create_active_member()
        member3 = self._create_active_member()
        member4 = self._create_active_member()

        original_panel = PrincePanel(
            panel_id=uuid4(),
            convened_by=uuid4(),
            members=(member1, member2, member3, member4),
            statement_under_review=uuid4(),
            status=PanelStatus.REVIEWING,
            convened_at=datetime.now(timezone.utc),
            finding=None,
        )

        assert len(original_panel.active_members) == 4

        # Member 4 recuses - create new member object
        recused_member4 = PanelMember(
            member_id=member4.member_id,
            joined_at=member4.joined_at,
            status=MemberStatus.RECUSED,
            recusal_reason="I advised the subject of review",
        )

        # Create new panel with recused member
        updated_panel = PrincePanel(
            panel_id=original_panel.panel_id,
            convened_by=original_panel.convened_by,
            members=(member1, member2, member3, recused_member4),
            statement_under_review=original_panel.statement_under_review,
            status=original_panel.status,
            convened_at=original_panel.convened_at,
            finding=None,
        )

        assert len(updated_panel.active_members) == 3
        assert updated_panel.can_issue_finding() is True

    def test_cannot_recuse_below_minimum(self) -> None:
        """Cannot create panel where recusal leaves <3 active."""
        member1 = self._create_active_member()
        member2 = self._create_active_member()
        member3 = self._create_active_member()

        # Try to create panel where one is recused (only 2 active)
        recused_member3 = PanelMember(
            member_id=member3.member_id,
            joined_at=member3.joined_at,
            status=MemberStatus.RECUSED,
            recusal_reason="Conflict",
        )

        with pytest.raises(InvalidPanelComposition):
            PrincePanel(
                panel_id=uuid4(),
                convened_by=uuid4(),
                members=(member1, member2, recused_member3),
                statement_under_review=uuid4(),
                status=PanelStatus.REVIEWING,
                convened_at=datetime.now(timezone.utc),
                finding=None,
            )
