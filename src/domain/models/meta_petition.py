"""META petition domain models (Story 8.5, FR-10.4).

This module defines the domain models for META petition routing and resolution:
- MetaDisposition: High Archon disposition options
- MetaPetitionStatus: Queue item status
- MetaPetitionQueueItem: Item in the High Archon queue

Constitutional Constraints:
- FR-10.4: META petitions route to High Archon [P2]
- META-1: Prevents deadlock from system-about-system petitions
- CT-12: Witnessing creates accountability - frozen dataclasses
- CT-13: Explicit consent - High Archon explicitly handles META petitions

Developer Golden Rules:
1. HALT CHECK FIRST - Check halt state before creating queue items (writes)
2. WITNESS EVERYTHING - All META petition actions require attribution
3. FAIL LOUD - Never silently swallow errors
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from uuid import UUID


class MetaDisposition(str, Enum):
    """High Archon disposition options for META petitions (Story 8.5, AC4).

    When a High Archon reviews a META petition, they must select one
    of these dispositions to resolve it.

    Values:
        ACKNOWLEDGE: Acknowledge the concern with rationale.
                     No further action required, concern is noted.
        CREATE_ACTION: Create a governance action item.
                       Triggers creation of follow-up task.
        FORWARD: Forward to specific governance body for review.
                 Requires forward_target to be specified.

    Constitutional Constraint (CT-13):
    Each disposition is an explicit consent action by the High Archon,
    ensuring no META petition is silently dismissed.
    """

    ACKNOWLEDGE = "ACKNOWLEDGE"
    CREATE_ACTION = "CREATE_ACTION"
    FORWARD = "FORWARD"


class MetaPetitionStatus(str, Enum):
    """Status of META petition in High Archon queue (Story 8.5, AC3).

    Values:
        PENDING: Awaiting High Archon review.
        RESOLVED: High Archon has assigned a disposition.

    State Transitions:
        PENDING -> RESOLVED: When High Archon resolves via API.

    Constitutional Constraint (CT-12):
    Each status transition must be witnessed and logged with attribution.
    """

    PENDING = "PENDING"
    RESOLVED = "RESOLVED"


@dataclass(frozen=True, eq=True)
class MetaPetitionQueueItem:
    """Item in High Archon's META petition queue (Story 8.5, AC3).

    This model represents a META petition waiting for or processed by
    the High Archon. Queue items are immutable for audit trail integrity.

    Constitutional Constraints:
    - CT-12: Frozen dataclass ensures immutability
    - FR-10.4: META petitions route directly to High Archon queue
    - AC3: Queue returns sorted by received_at (FIFO)

    Attributes:
        petition_id: UUID of the META petition.
        submitter_id: UUID of the petition submitter.
        petition_text: Full petition text content.
        received_at: When the petition was received (UTC).
        status: Current queue status (PENDING or RESOLVED).

    Usage:
        item = MetaPetitionQueueItem(
            petition_id=uuid4(),
            submitter_id=uuid4(),
            petition_text="Petition about improving the petition system",
            received_at=datetime.now(timezone.utc),
            status=MetaPetitionStatus.PENDING,
        )
    """

    petition_id: UUID
    submitter_id: UUID
    petition_text: str
    received_at: datetime
    status: MetaPetitionStatus
