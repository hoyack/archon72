"""Contact block domain model for dignified exit.

Story: consent-gov-7.4: Follow-Up Contact Prevention

Records when contact has been blocked for an exited Cluster.
Contact blocks are PERMANENT and cannot be removed.

NFR-EXIT-02: No follow-up contact mechanism may exist.
FR46: System can prohibit follow-up contact after exit.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from src.domain.governance.exit.contact_block_status import ContactBlockStatus


@dataclass(frozen=True)
class ContactBlock:
    """Record of blocked contact for an exited Cluster.

    This is an immutable record. Once created, a contact block
    cannot be modified or removed. This is structural enforcement
    of NFR-EXIT-02.

    Key Properties:
    - Immutable (frozen dataclass)
    - No unblock field (cannot be unblocked)
    - Permanent by design
    - Structural prohibition

    Example:
        block = ContactBlock(
            block_id=uuid4(),
            cluster_id=cluster.id,
            blocked_at=time_authority.now(),
            reason="exit",
            status=ContactBlockStatus.PERMANENTLY_BLOCKED,
        )

        # No way to unblock - intentional
    """

    block_id: UUID
    """Unique identifier for this block record."""

    cluster_id: UUID
    """The Cluster whose contact is blocked."""

    blocked_at: datetime
    """When the block was applied."""

    reason: str
    """Why contact was blocked. Always 'exit' for dignified exit."""

    status: ContactBlockStatus
    """Block status. Always PERMANENTLY_BLOCKED."""

    # Intentionally NO fields for:
    # - unblocked_at: Cannot be unblocked
    # - unblock_reason: No unblocking possible
    # - temporary_until: Blocks are permanent
    # - override_by: No override mechanism

    def __post_init__(self) -> None:
        """Validate block is permanent.

        Raises:
            ValueError: If status is not PERMANENTLY_BLOCKED.
        """
        if self.status != ContactBlockStatus.PERMANENTLY_BLOCKED:
            raise ValueError(
                f"ContactBlock status must be PERMANENTLY_BLOCKED, "
                f"got {self.status}"
            )
