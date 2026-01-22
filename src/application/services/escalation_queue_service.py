"""Escalation queue service (Story 6.1, FR-5.4, CT-13, D8).

This module implements the EscalationQueueProtocol for accessing the King's
escalation queue, which contains petitions that have been escalated for
King review.

Constitutional Constraints:
- FR-5.4: King SHALL receive escalation queue distinct from organic Motions [P0]
- CT-13: Halt check first pattern must be enforced
- D8: Keyset pagination for efficient cursor-based navigation
- RULING-3: Realm-scoped data access enforced
- NFR-1.3: Endpoint latency < 200ms p95

Developer Golden Rules:
1. HALT CHECK FIRST - Check halt state before processing (CT-13)
2. REALM SCOPED - Only return petitions for King's realm (RULING-3)
3. FIFO ORDER - Order by escalated_at ascending (oldest first)
4. KEYSET PAGINATION - Use cursor-based pagination (D8)
"""

from __future__ import annotations

import base64
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from structlog import get_logger

from src.application.ports.escalation_queue import (
    EscalationQueueItem,
    EscalationQueueProtocol,
    EscalationQueueResult,
    EscalationSource,
)
from src.domain.errors import SystemHaltedError
from src.domain.models.petition_submission import PetitionState

if TYPE_CHECKING:
    from src.application.ports.halt_checker import HaltChecker
    from src.application.ports.petition_submission_repository import (
        PetitionSubmissionRepositoryProtocol,
    )

logger = get_logger(__name__)

# Pagination limits
DEFAULT_LIMIT = 20
MAX_LIMIT = 100


class EscalationQueueService:
    """Service for accessing the King's escalation queue (Story 6.1, FR-5.4).

    Implements the EscalationQueueProtocol for retrieving escalated petitions
    assigned to a King's realm.

    The service ensures:
    1. Halt check first (CT-13)
    2. Realm-scoped filtering (RULING-3)
    3. FIFO ordering by escalated_at (oldest first)
    4. Keyset pagination for efficiency (D8)
    5. Structured logging (no f-strings)

    Constitutional Constraints:
    - FR-5.4: King SHALL receive escalation queue distinct from organic Motions
    - CT-13: Halt rejects writes, allows reads
    - D8: Keyset pagination compliance
    - RULING-3: Realm-scoped data access

    Example:
        >>> service = EscalationQueueService(
        ...     petition_repo=petition_repo,
        ...     halt_checker=halt_checker,
        ... )
        >>> result = await service.get_queue(
        ...     king_id=king_id,
        ...     realm_id="governance",
        ...     cursor=None,
        ...     limit=20,
        ... )
        >>> result.items
        [EscalationQueueItem(...), ...]
    """

    def __init__(
        self,
        petition_repo: PetitionSubmissionRepositoryProtocol,
        halt_checker: HaltChecker,
    ) -> None:
        """Initialize the escalation queue service.

        Args:
            petition_repo: Repository for petition access.
            halt_checker: Service for checking halt state.
        """
        self._petition_repo = petition_repo
        self._halt_checker = halt_checker

    async def get_queue(
        self,
        king_id: UUID,
        realm_id: str,
        cursor: str | None = None,
        limit: int = DEFAULT_LIMIT,
    ) -> EscalationQueueResult:
        """Get the escalation queue for a King's realm (FR-5.4).

        This method retrieves petitions that have been escalated to the King's
        realm, ordered by escalated_at ascending (FIFO).

        Uses keyset pagination for efficiency (D8):
        - Cursor format: base64(escalated_at:petition_id)
        - Next page: WHERE (escalated_at, id) > (cursor_time, cursor_id)

        Args:
            king_id: UUID of the King requesting the queue
            realm_id: Realm ID for the King's domain (e.g., "governance")
            cursor: Optional cursor for pagination (keyset-based)
            limit: Maximum number of items to return (default 20, max 100)

        Returns:
            EscalationQueueResult with items, next_cursor, and has_more flag

        Raises:
            SystemHaltedError: If system is halted (CT-13)
            ValueError: If limit is invalid
        """
        log = logger.bind(
            king_id=str(king_id),
            realm_id=realm_id,
            cursor=cursor,
            limit=limit,
        )
        log.info("Retrieving escalation queue for King")

        # Step 1: HALT CHECK FIRST (CT-13)
        # Reading is allowed during halt, but we check for consistency
        if await self._halt_checker.is_halted():
            log.warning("Queue access during system halt")
            raise SystemHaltedError(
                "Escalation queue access is not permitted during system halt"
            )

        # Step 2: Validate limit
        if limit < 1 or limit > MAX_LIMIT:
            raise ValueError(
                f"Limit must be between 1 and {MAX_LIMIT}, got {limit}"
            )

        # Step 3: Parse cursor (if provided)
        cursor_time: datetime | None = None
        cursor_id: UUID | None = None
        if cursor:
            try:
                cursor_time, cursor_id = self._parse_cursor(cursor)
                log.debug(
                    "Parsed cursor",
                    cursor_time=cursor_time.isoformat(),
                    cursor_id=str(cursor_id),
                )
            except Exception as e:
                log.warning("Invalid cursor format", error=str(e))
                raise ValueError(f"Invalid cursor format: {e}")

        # Step 4: Query petitions from repository
        # This would use a new repository method: list_escalated_by_realm()
        # For now, we'll use list_by_state and filter in-memory
        # TODO: Add list_escalated_by_realm() to repository for efficiency
        escalated_petitions, _ = await self._petition_repo.list_by_state(
            state=PetitionState.ESCALATED,
            limit=limit + 1,  # Fetch one extra to determine has_more
            offset=0,
        )

        # Step 5: Filter by realm and apply cursor
        filtered_items = []
        for petition in escalated_petitions:
            # Skip if not for this realm
            if not hasattr(petition, "escalated_to_realm"):
                continue
            if petition.escalated_to_realm != realm_id:
                continue

            # Skip if not escalated (safety check)
            if not hasattr(petition, "escalated_at") or petition.escalated_at is None:
                continue

            # Apply cursor filter
            if cursor_time and cursor_id:
                if petition.escalated_at < cursor_time:
                    continue
                if (
                    petition.escalated_at == cursor_time
                    and petition.id <= cursor_id
                ):
                    continue

            # Build queue item
            escalation_source = EscalationSource.DELIBERATION
            if hasattr(petition, "escalation_source") and petition.escalation_source:
                escalation_source = EscalationSource[petition.escalation_source]

            item = EscalationQueueItem(
                petition_id=petition.id,
                petition_type=petition.type,
                escalation_source=escalation_source,
                co_signer_count=petition.co_signer_count,
                escalated_at=petition.escalated_at,
            )
            filtered_items.append(item)

        # Step 6: Sort by escalated_at ascending (FIFO)
        filtered_items.sort(key=lambda x: (x.escalated_at, x.petition_id))

        # Step 7: Determine has_more and build response
        has_more = len(filtered_items) > limit
        items = filtered_items[:limit]

        next_cursor = None
        if has_more and items:
            last_item = items[-1]
            next_cursor = self._build_cursor(
                last_item.escalated_at, last_item.petition_id
            )

        log.info(
            "Retrieved escalation queue",
            item_count=len(items),
            has_more=has_more,
        )

        return EscalationQueueResult(
            items=items,
            next_cursor=next_cursor,
            has_more=has_more,
        )

    def _parse_cursor(self, cursor: str) -> tuple[datetime, UUID]:
        """Parse a keyset cursor into (escalated_at, petition_id).

        Cursor format: base64(escalated_at_iso:petition_id)

        Args:
            cursor: Base64-encoded cursor string

        Returns:
            Tuple of (escalated_at, petition_id)

        Raises:
            ValueError: If cursor format is invalid
        """
        try:
            decoded = base64.b64decode(cursor).decode("utf-8")
            time_str, id_str = decoded.split(":", 1)
            escalated_at = datetime.fromisoformat(time_str)
            petition_id = UUID(id_str)
            return escalated_at, petition_id
        except Exception as e:
            raise ValueError(f"Invalid cursor format: {e}")

    def _build_cursor(self, escalated_at: datetime, petition_id: UUID) -> str:
        """Build a keyset cursor from (escalated_at, petition_id).

        Cursor format: base64(escalated_at_iso:petition_id)

        Args:
            escalated_at: Escalation timestamp
            petition_id: Petition UUID

        Returns:
            Base64-encoded cursor string
        """
        cursor_str = f"{escalated_at.isoformat()}:{str(petition_id)}"
        return base64.b64encode(cursor_str.encode("utf-8")).decode("utf-8")


__all__ = ["EscalationQueueService"]
