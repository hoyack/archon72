"""Panel queue domain models for witness statement routing.

Story: consent-gov-6-3: Witness Statement Routing

This module defines the domain models for the Prince Panel queue.
The queue is append-only by design - no deletion or modification allowed.

Queue Design Principles:
-----------------------
1. Append-only: Evidence preservation, no suppression possible
2. Priority-based: Critical issues reviewed first
3. Status tracking: Lifecycle from pending to resolved
4. Immutable items: Once queued, cannot be modified (only status changes)

Why Append-Only?
----------------
- Evidence must be preserved for audit
- Deletion could suppress violations
- Audit trail must be complete
- Resolution is a status change, not deletion

Constitutional Truths Honored:
- CT-12: Witnessing creates accountability
- NFR-CONST-07: Statements cannot be suppressed by any role

References:
    - FR35: System can route witness statements to Prince Panel queue
    - AC2: Queue is append-only (no deletion)
"""

from src.domain.governance.queue.priority import QueuePriority
from src.domain.governance.queue.queued_statement import QueuedStatement
from src.domain.governance.queue.status import QueueItemStatus

__all__ = [
    "QueuePriority",
    "QueueItemStatus",
    "QueuedStatement",
]
