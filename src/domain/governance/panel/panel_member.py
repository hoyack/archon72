"""Panel member domain model.

Story: consent-gov-6-4: Prince Panel Domain Model

Defines the PanelMember value object representing a member of a Prince Panel.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from src.domain.governance.panel.member_status import MemberStatus


@dataclass(frozen=True, eq=True)
class PanelMember:
    """Member of a Prince Panel.

    A panel member represents a Prince participating in judicial review.
    Members are equal (no rank/influence weight) and can recuse from
    cases where they have a conflict of interest.

    This is a frozen dataclass - once created, members cannot be modified.
    To change a member's status (e.g., recusal), create a new PanelMember.

    Attributes:
        member_id: Unique identifier for this panel member (Prince UUID)
        joined_at: When the member joined the panel
        status: Current participation status (ACTIVE or RECUSED)
        recusal_reason: Reason for recusal, if recused

    Note:
        No rank/influence weight field exists - all panel members are equal.
        This prevents power concentration in panels.

    Example:
        >>> member = PanelMember(
        ...     member_id=uuid4(),
        ...     joined_at=datetime.now(timezone.utc),
        ...     status=MemberStatus.ACTIVE,
        ...     recusal_reason=None,
        ... )
    """

    member_id: UUID
    """Unique identifier for this panel member (Prince UUID)."""

    joined_at: datetime
    """When the member joined the panel."""

    status: MemberStatus
    """Current participation status."""

    recusal_reason: str | None
    """Reason for recusal, if recused. None if active."""

    def __hash__(self) -> int:
        """Hash based on member_id (unique identifier)."""
        return hash(self.member_id)
