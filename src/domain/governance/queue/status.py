"""Queue item status enum for Prince Panel queue.

Story: consent-gov-6-3: Witness Statement Routing

This module defines the lifecycle states for queued statements.

Queue Item Lifecycle:
--------------------
PENDING → ACKNOWLEDGED → IN_REVIEW → RESOLVED
         (Operator)      (Panel)     (Finding issued)

Note: Resolved items REMAIN in queue (historical record).
      Status change, not deletion, is how items progress.

Constitutional Truths Honored:
- CT-12: Witnessing creates accountability -> All status changes tracked
- NFR-CONST-07: Statements cannot be suppressed -> No deletion

References:
    - AC2: Queue is append-only (no deletion)
    - AC3: Status transitions tracked
"""

from __future__ import annotations

from enum import Enum


class QueueItemStatus(Enum):
    """Lifecycle status of a queued witness statement.

    Items progress through these states but are NEVER deleted.
    Resolved items remain in the queue for audit purposes.
    """

    PENDING = "pending"
    """Waiting for operator acknowledgment.

    Initial state when statement is first queued.
    Item is visible in the queue awaiting attention.
    """

    ACKNOWLEDGED = "acknowledged"
    """Operator has seen and acknowledged the item.

    The Human Operator has viewed the item and acknowledged receipt.
    This does NOT mean action has been taken, only that it was seen.
    """

    IN_REVIEW = "in_review"
    """Prince Panel is actively reviewing the statement.

    A Prince Panel has been convened to review this statement.
    Deliberation is in progress.
    """

    RESOLVED = "resolved"
    """Panel has issued a finding for this statement.

    The review process is complete. A finding has been issued
    and linked to this queue item. The item remains in the
    queue permanently for audit purposes.
    """
