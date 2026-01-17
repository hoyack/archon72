"""Recusal domain models.

Story: consent-gov-6-4: Prince Panel Domain Model

Defines models for panel member recusal (AC7).
A member can recuse from a specific case due to conflict of interest.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, eq=True)
class RecusalRequest:
    """Request for a panel member to recuse.

    Represents a member's declaration that they have a conflict of
    interest and should not participate in deliberation.

    Recusal rules:
    - Member can recuse from specific case
    - Recusal recorded with reason
    - Panel still valid if ≥3 active remain
    - Panel invalid if <3 active members after recusal

    Attributes:
        request_id: Unique identifier for this recusal request
        panel_id: UUID of the panel
        member_id: UUID of the member recusing
        reason: Explanation of the conflict of interest
        requested_at: When the recusal was requested

    Example:
        >>> recusal = RecusalRequest(
        ...     request_id=uuid4(),
        ...     panel_id=uuid4(),
        ...     member_id=uuid4(),
        ...     reason="I previously advised on this matter.",
        ...     requested_at=datetime.now(timezone.utc),
        ... )
    """

    request_id: UUID
    """Unique identifier for this recusal request."""

    panel_id: UUID
    """UUID of the panel."""

    member_id: UUID
    """UUID of the member recusing."""

    reason: str
    """Explanation of the conflict of interest."""

    requested_at: datetime
    """When the recusal was requested."""

    def __hash__(self) -> int:
        """Hash based on request_id (unique identifier)."""
        return hash(self.request_id)
