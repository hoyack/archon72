"""Queued statement domain model for Prince Panel queue.

Story: consent-gov-6-3: Witness Statement Routing

This module defines the immutable queued statement structure.
Represents a witness statement that has been routed to the Prince Panel
for review.

Design Principles:
-----------------
1. Frozen dataclass: Immutable once created
2. Links to original statement: statement_id reference
3. Contains statement copy: For review without dependency
4. Tracks lifecycle: status, timestamps, finding link

Constitutional Truths Honored:
- CT-12: Witnessing creates accountability
- NFR-CONST-07: Statements cannot be suppressed

References:
    - FR35: System can route witness statements to Prince Panel queue
    - AC1: Statements routed to Prince Panel queue
    - AC2: Queue is append-only (no deletion)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from src.domain.governance.queue.priority import QueuePriority
from src.domain.governance.queue.status import QueueItemStatus
from src.domain.governance.witness.witness_statement import WitnessStatement


@dataclass(frozen=True, eq=True)
class QueuedStatement:
    """Witness statement queued for Prince Panel review.

    Represents an immutable record of a witness statement that has
    been routed to the Prince Panel queue for review.

    Once created, this record cannot be modified. Status changes
    create new records linking to this one (or the adapter tracks
    status separately while preserving this immutable record).

    Attributes:
        queue_item_id: Unique identifier for this queue item.
        statement_id: Reference to the original witness statement.
        statement: Copy of the witness statement for review.
        priority: Queue priority (affects review order).
        status: Current lifecycle status.
        queued_at: When this statement was queued.
        acknowledged_at: When operator acknowledged (if any).
        resolved_at: When panel resolved (if any).
        finding_id: Link to panel finding (if resolved).

    Example:
        >>> queued = QueuedStatement(
        ...     queue_item_id=uuid4(),
        ...     statement_id=statement.statement_id,
        ...     statement=statement,
        ...     priority=QueuePriority.HIGH,
        ...     status=QueueItemStatus.PENDING,
        ...     queued_at=datetime.now(timezone.utc),
        ...     acknowledged_at=None,
        ...     resolved_at=None,
        ...     finding_id=None,
        ... )
    """

    queue_item_id: UUID
    """Unique identifier for this queue item.

    Different from statement_id to allow the same statement
    to be queued multiple times if needed (though unusual).
    """

    statement_id: UUID
    """Reference to the original witness statement.

    Links back to the statement in the witness ledger.
    """

    statement: WitnessStatement
    """Copy of the witness statement for panel review.

    Included directly so panel can review without additional
    lookups. This is a snapshot at queue time.
    """

    priority: QueuePriority
    """Queue priority for review ordering.

    Assigned by the routing service based on observation type
    and content analysis. CRITICAL items reviewed first.
    """

    status: QueueItemStatus
    """Current lifecycle status of this queue item.

    Progresses: PENDING -> ACKNOWLEDGED -> IN_REVIEW -> RESOLVED
    Items are NEVER deleted, only status changes.
    """

    queued_at: datetime
    """When this statement was added to the queue.

    UTC timestamp. Used for queue ordering within priority level.
    """

    acknowledged_at: datetime | None
    """When operator acknowledged this item.

    None if not yet acknowledged. UTC timestamp.
    """

    resolved_at: datetime | None
    """When panel resolved this item.

    None if not yet resolved. UTC timestamp.
    """

    finding_id: UUID | None
    """Link to the panel finding for this statement.

    None if not yet resolved. Links to the PanelFinding
    issued by the Prince Panel after review.
    """

    def __hash__(self) -> int:
        """Hash based on queue_item_id (unique identifier)."""
        return hash(self.queue_item_id)

    def with_status(
        self,
        new_status: QueueItemStatus,
        acknowledged_at: datetime | None = None,
        resolved_at: datetime | None = None,
        finding_id: UUID | None = None,
    ) -> QueuedStatement:
        """Create new instance with updated status.

        Since QueuedStatement is frozen, status changes create new
        instances. This method provides a convenient way to do that.

        Args:
            new_status: The new status for the queue item.
            acknowledged_at: Acknowledgment timestamp (for ACKNOWLEDGED+).
            resolved_at: Resolution timestamp (for RESOLVED).
            finding_id: Finding reference (for RESOLVED).

        Returns:
            New QueuedStatement with updated status fields.
        """
        return QueuedStatement(
            queue_item_id=self.queue_item_id,
            statement_id=self.statement_id,
            statement=self.statement,
            priority=self.priority,
            status=new_status,
            queued_at=self.queued_at,
            acknowledged_at=acknowledged_at or self.acknowledged_at,
            resolved_at=resolved_at or self.resolved_at,
            finding_id=finding_id or self.finding_id,
        )
