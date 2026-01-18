"""Prince Panel domain model.

Story: consent-gov-6-4: Prince Panel Domain Model

Defines the PrincePanel aggregate root for judicial review.
Panels require ≥3 active members to issue findings (FR36).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from src.domain.governance.panel.errors import InvalidPanelComposition
from src.domain.governance.panel.member_status import MemberStatus
from src.domain.governance.panel.panel_finding import PanelFinding
from src.domain.governance.panel.panel_member import PanelMember
from src.domain.governance.panel.panel_status import PanelStatus


@dataclass(frozen=True, eq=True)
class PrincePanel:
    """Prince Panel for judicial review.

    A panel of Princes that reviews witness statements and issues
    formal findings. Requires ≥3 active members (FR36).

    Why ≥3 Members?
    ---------------
    Single person decisions:
      - No check on individual bias
      - No deliberation required
      - No dissent possible

    Two person panels:
      - Deadlock possible
      - Still limited perspective

    Three or more:
      - Deliberation required
      - Majority can decide
      - Dissent can be recorded

    Attributes:
        panel_id: Unique identifier for this panel
        convened_by: UUID of Human Operator who convened the panel
        members: Tuple of panel members (immutable)
        statement_under_review: UUID of witness statement being reviewed
        status: Current panel status
        convened_at: When the panel was convened
        finding: Panel finding if issued, None otherwise

    Raises:
        InvalidPanelComposition: If fewer than 3 active members

    Example:
        >>> panel = PrincePanel(
        ...     panel_id=uuid4(),
        ...     convened_by=uuid4(),  # Human Operator
        ...     members=(member1, member2, member3),
        ...     statement_under_review=uuid4(),
        ...     status=PanelStatus.CONVENED,
        ...     convened_at=datetime.now(timezone.utc),
        ...     finding=None,
        ... )
    """

    panel_id: UUID
    """Unique identifier for this panel."""

    convened_by: UUID
    """UUID of Human Operator who convened the panel (AC2)."""

    members: tuple[PanelMember, ...]
    """Tuple of panel members (immutable)."""

    statement_under_review: UUID
    """UUID of witness statement being reviewed."""

    status: PanelStatus
    """Current panel status."""

    convened_at: datetime
    """When the panel was convened."""

    finding: PanelFinding | None
    """Panel finding if issued, None otherwise."""

    def __post_init__(self) -> None:
        """Validate panel composition.

        Raises:
            InvalidPanelComposition: If fewer than 3 active members
        """
        active_count = sum(1 for m in self.members if m.status == MemberStatus.ACTIVE)
        if active_count < 3:
            raise InvalidPanelComposition(
                f"Panel requires ≥3 active members, has {active_count}"
            )

    @property
    def active_members(self) -> list[PanelMember]:
        """Get active (non-recused) members.

        Returns:
            List of members with ACTIVE status
        """
        return [m for m in self.members if m.status == MemberStatus.ACTIVE]

    @property
    def quorum(self) -> int:
        """Calculate quorum (majority of active members).

        Returns:
            Number of votes needed for quorum
        """
        return (len(self.active_members) // 2) + 1

    def can_issue_finding(self) -> bool:
        """Check if panel can issue a finding.

        Panel can issue finding only when:
        - Status is REVIEWING or DELIBERATING
        - Has ≥3 active members

        Returns:
            True if panel can issue finding, False otherwise
        """
        return len(self.active_members) >= 3 and self.status in [
            PanelStatus.REVIEWING,
            PanelStatus.DELIBERATING,
        ]

    def __hash__(self) -> int:
        """Hash based on panel_id (unique identifier)."""
        return hash(self.panel_id)
