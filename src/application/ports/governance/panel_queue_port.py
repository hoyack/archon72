"""Panel queue port interface for Prince Panel operations.

Story: consent-gov-6-3: Witness Statement Routing

This module defines the port interface for panel queue operations.
The interface is intentionally designed to PREVENT suppression:
- No delete_statement() method exists
- No modify_statement() method exists
- Only append-only enqueue and status-change operations

Constitutional Truths Honored:
- CT-12: Witnessing creates accountability -> All items attributable
- NFR-CONST-07: Statements cannot be suppressed by any role

Suppression Prevention by Design:
---------------------------------
This port interface is the CONTRACT between the application layer and
any adapter implementation. By NOT defining delete or modify methods,
we ensure that NO adapter can implement suppression capabilities.

This is a "pit of success" design - the right behavior is the only
behavior possible.

References:
    - FR35: System can route witness statements to Prince Panel queue
    - AC2: Queue is append-only (no deletion)
    - AC7: Human Operator can view queue
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional, Protocol, runtime_checkable
from uuid import UUID

from src.domain.governance.queue.priority import QueuePriority
from src.domain.governance.queue.status import QueueItemStatus
from src.domain.governance.queue.queued_statement import QueuedStatement


@runtime_checkable
class PanelQueuePort(Protocol):
    """Port for Prince Panel queue operations.

    This interface defines the contract for panel queue persistence.
    It is intentionally designed to PREVENT suppression.

    Available operations (read + append + status change):
        - enqueue_statement: Add statement to queue (append-only)
        - get_pending_statements: Retrieve pending items
        - get_statements_by_status: Retrieve items by status
        - get_all_items: Retrieve all items (for audit)
        - acknowledge_statement: Status change to ACKNOWLEDGED
        - mark_in_review: Status change to IN_REVIEW
        - mark_resolved: Status change to RESOLVED

    Intentionally NOT defined (suppression prevention):
        - delete_statement: Suppression not allowed (NFR-CONST-07)
        - modify_statement: Immutability enforced
        - remove_statement: Suppression not allowed

    Any adapter implementing this port MUST NOT add these methods.
    The port interface is the enforcement mechanism.

    Example:
        >>> class PostgresPanelQueueAdapter:
        ...     async def enqueue_statement(self, item: QueuedStatement) -> None:
        ...         # Insert into append-only table
        ...         await self._db.execute(
        ...             "INSERT INTO panel_queue (...) VALUES (...)"
        ...         )
        ...
        ...     # Note: NO delete_statement method - not in the interface
    """

    async def enqueue_statement(
        self,
        item: QueuedStatement,
    ) -> None:
        """Add statement to the panel queue.

        Once enqueued, the statement cannot be deleted or modified.
        This is the ONLY write operation for new items.

        Args:
            item: The queued statement to add.

        Raises:
            Any persistence-related exceptions from the adapter.
        """
        ...

    async def get_pending_statements(
        self,
        priority: Optional[QueuePriority] = None,
    ) -> list[QueuedStatement]:
        """Get pending statements, optionally filtered by priority.

        Returns items with PENDING status, ordered by priority
        (CRITICAL first) and then by queued_at (oldest first).

        Args:
            priority: Optional priority filter. If None, all priorities.

        Returns:
            List of pending statements matching criteria.
        """
        ...

    async def get_statements_by_status(
        self,
        status: QueueItemStatus,
        since: Optional[datetime] = None,
    ) -> list[QueuedStatement]:
        """Get statements by status, optionally filtered by date.

        Args:
            status: The status to filter by.
            since: Optional timestamp to filter items after.

        Returns:
            List of statements matching the criteria.
        """
        ...

    async def get_all_items(
        self,
        since: Optional[datetime] = None,
    ) -> list[QueuedStatement]:
        """Get all queue items for audit purposes.

        Includes items in ALL statuses, including RESOLVED.
        Used for audit trail verification.

        Args:
            since: Optional timestamp to filter items after.

        Returns:
            List of all queue items.
        """
        ...

    async def get_item_by_id(
        self,
        queue_item_id: UUID,
    ) -> Optional[QueuedStatement]:
        """Get a specific queue item by ID.

        Args:
            queue_item_id: The queue item ID to retrieve.

        Returns:
            The queue item if found, None otherwise.
        """
        ...

    async def acknowledge_statement(
        self,
        queue_item_id: UUID,
        operator_id: UUID,
        acknowledged_at: datetime,
    ) -> QueuedStatement:
        """Mark statement as acknowledged by operator.

        Status change only - no deletion or modification of content.
        The operator_id is recorded for audit purposes.

        Args:
            queue_item_id: The queue item to acknowledge.
            operator_id: The Human Operator who acknowledged.
            acknowledged_at: Timestamp of acknowledgment.

        Returns:
            Updated queue item with ACKNOWLEDGED status.

        Raises:
            ValueError: If item not found or invalid state transition.
        """
        ...

    async def mark_in_review(
        self,
        queue_item_id: UUID,
        panel_id: UUID,
    ) -> QueuedStatement:
        """Mark statement as under panel review.

        Status change only - no deletion or modification of content.

        Args:
            queue_item_id: The queue item to mark.
            panel_id: The Prince Panel conducting review.

        Returns:
            Updated queue item with IN_REVIEW status.

        Raises:
            ValueError: If item not found or invalid state transition.
        """
        ...

    async def mark_resolved(
        self,
        queue_item_id: UUID,
        finding_id: UUID,
        resolved_at: datetime,
    ) -> QueuedStatement:
        """Mark statement as resolved with finding.

        Status change only - no deletion or modification of content.
        The item remains in the queue with RESOLVED status.

        Args:
            queue_item_id: The queue item to resolve.
            finding_id: The panel finding for this statement.
            resolved_at: Timestamp of resolution.

        Returns:
            Updated queue item with RESOLVED status.

        Raises:
            ValueError: If item not found or invalid state transition.
        """
        ...

    # =========================================================================
    # Explicitly NOT defined - these methods DO NOT EXIST:
    # =========================================================================
    #
    # - delete_statement(queue_item_id: UUID) -> None
    #   Suppression not allowed (NFR-CONST-07)
    #
    # - modify_statement(queue_item_id: UUID, ...) -> QueuedStatement
    #   Immutability enforced
    #
    # - remove_statement(queue_item_id: UUID) -> None
    #   Suppression not allowed
    #
    # Any adapter that adds these methods is VIOLATING the contract.
    # =========================================================================
