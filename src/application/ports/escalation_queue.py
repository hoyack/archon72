"""Escalation queue port (Story 6.1, FR-5.4, CT-13).

This module defines the protocol for accessing the King's escalation queue,
which contains petitions that have been escalated for King review.

Constitutional Constraints:
- FR-5.4: King SHALL receive escalation queue distinct from organic Motions [P0]
- CT-13: Halt check first pattern must be enforced
- D8: Keyset pagination for efficient cursor-based navigation
- RULING-3: Realm-scoped data access enforced

Escalation Sources:
- DELIBERATION: Three Fates decided to escalate
- CO_SIGNER_THRESHOLD: Auto-escalation from co-signer count
- KNIGHT_RECOMMENDATION: Knight recommended escalation

State Machine:
    Petition enters queue when state = ESCALATED and escalated_to_realm is set.
    Queue is read-only; petitions cannot transition out once escalated.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Protocol
from uuid import UUID

from src.domain.models.petition_submission import PetitionType


class EscalationSource(Enum):
    """Source that triggered the escalation (FR-5.4).

    Values:
        DELIBERATION: Three Fates deliberation decided ESCALATE
        CO_SIGNER_THRESHOLD: Auto-escalation from co-signer count
        KNIGHT_RECOMMENDATION: Knight recommended escalation
    """

    DELIBERATION = "DELIBERATION"
    CO_SIGNER_THRESHOLD = "CO_SIGNER_THRESHOLD"
    KNIGHT_RECOMMENDATION = "KNIGHT_RECOMMENDATION"


@dataclass(frozen=True)
class EscalationQueueItem:
    """A single item in the King's escalation queue (FR-5.4).

    Attributes:
        petition_id: UUID of the escalated petition
        petition_type: Type of petition (CESSATION, GRIEVANCE, etc.)
        escalation_source: What triggered the escalation
        co_signer_count: Number of co-signers (for visibility)
        escalated_at: When the petition was escalated (UTC)
    """

    petition_id: UUID
    petition_type: PetitionType
    escalation_source: EscalationSource
    co_signer_count: int
    escalated_at: datetime


@dataclass(frozen=True)
class EscalationQueueResult:
    """Result of querying the escalation queue (FR-5.4, D8).

    Uses keyset pagination for efficient cursor-based navigation.

    Attributes:
        items: List of escalated petitions in FIFO order
        next_cursor: Cursor for next page (None if no more items)
        has_more: Whether there are more items after this page
    """

    items: list[EscalationQueueItem]
    next_cursor: str | None
    has_more: bool


class EscalationQueueProtocol(Protocol):
    """Protocol for accessing the King's escalation queue (FR-5.4).

    The escalation queue contains petitions that have been escalated
    for King review. It is distinct from the organic Motion queue.

    Implementation Requirements:
    - CT-13: HALT CHECK FIRST before processing
    - RULING-3: Filter by realm_id for King's realm
    - D8: Use keyset pagination (not offset-based)
    - Order by escalated_at ascending (FIFO)
    """

    async def get_queue(
        self,
        king_id: UUID,
        realm_id: str,
        cursor: str | None = None,
        limit: int = 20,
    ) -> EscalationQueueResult:
        """Get the escalation queue for a King's realm (FR-5.4).

        Args:
            king_id: UUID of the King requesting the queue
            realm_id: Realm ID for the King's domain (e.g., "governance")
            cursor: Optional cursor for pagination (keyset-based)
            limit: Maximum number of items to return (default 20, max 100)

        Returns:
            EscalationQueueResult with items, next_cursor, and has_more flag

        Raises:
            HaltedError: If system is halted (CT-13)
            ValueError: If limit is invalid
        """
        ...


__all__ = [
    "EscalationSource",
    "EscalationQueueItem",
    "EscalationQueueProtocol",
    "EscalationQueueResult",
]
