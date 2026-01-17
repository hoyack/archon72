"""Panel member status enumeration.

Story: consent-gov-6-4: Prince Panel Domain Model

Defines the participation status of a panel member.
"""

from enum import Enum


class MemberStatus(Enum):
    """Status of a panel member.

    Attributes:
        ACTIVE: Member is participating in the panel
        RECUSED: Member has recused from this case
    """

    ACTIVE = "active"
    """Member is participating in the panel."""

    RECUSED = "recused"
    """Member has recused due to conflict of interest."""
