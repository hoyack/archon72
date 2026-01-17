"""Contact block status enum for dignified exit.

Story: consent-gov-7.4: Follow-Up Contact Prevention

Defines the status of contact blocking for exited Clusters.
Contact blocks are PERMANENT - there is no unblocked status.

NFR-EXIT-02: No follow-up contact mechanism may exist.
"""

from enum import Enum


class ContactBlockStatus(Enum):
    """Status of contact blocking.

    Note: There is intentionally NO unblocked status.
    Once blocked, always blocked. This is structural.

    Why only PERMANENTLY_BLOCKED?
    - Exit is final
    - Contact prohibition is permanent
    - No "temporary" blocks that could be lifted
    - Structural enforcement, not policy
    """

    PERMANENTLY_BLOCKED = "permanently_blocked"
    """Contact is permanently blocked due to exit.

    This is the only status. It cannot transition to any other state.
    There is no UNBLOCKED, ACTIVE, or TEMPORARY status by design.
    """
