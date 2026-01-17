"""FilterDecisionLogPort - Interface for filter decision logging.

Story: consent-gov-3.3: Filter Decision Logging

This port defines the contract for logging filter decisions to the
append-only ledger for audit and compliance.

Key Design:
- All decisions logged with input, output, version, timestamp (FR20)
- Content stored as hashes for privacy
- Append-only semantics - logged decisions are immutable (AC8)

References:
- FR19: Earl can view filter outcome before content is sent
- FR20: System can log all filter decisions with version and timestamp
- NFR-AUDIT-02: Complete audit trail
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable
from uuid import UUID

from src.application.ports.governance.coercion_filter_port import MessageType
from src.domain.governance.filter import (
    FilterDecisionLog,
    FilterResult,
)


@runtime_checkable
class FilterDecisionLogPort(Protocol):
    """Port for filter decision logging operations.

    This interface defines the contract for logging filter decisions
    to the governance ledger. All logged decisions are immutable and
    become part of the permanent audit trail.

    Constitutional Guarantee:
    - All filter_content() calls are logged (not preview_filter())
    - Logs are append-only - no updates or deletes
    - Events are visible to Knight for observation

    Event Type:
    - custodial.filter.decision_logged

    Usage:
        log_entry = await log_port.log_decision(
            result=filter_result,
            input_content="Raw content",
            message_type=MessageType.TASK_ACTIVATION,
            earl_id=earl_uuid,
        )
    """

    async def log_decision(
        self,
        result: FilterResult,
        input_content: str,
        message_type: MessageType,
        earl_id: UUID,
    ) -> FilterDecisionLog:
        """Log a filter decision to the ledger.

        Creates an immutable log entry and emits the
        'custodial.filter.decision_logged' event.

        Args:
            result: The FilterResult from the filter service.
            input_content: Raw input content (will be hashed, not stored).
            message_type: Type of message that was filtered.
            earl_id: Earl who submitted the content.

        Returns:
            FilterDecisionLog capturing the logged decision.

        Side Effects:
            - Emits 'custodial.filter.decision_logged' event to ledger
            - Event becomes part of hash chain
            - Knight can observe via event stream
        """
        ...

    async def get_decision_history(
        self,
        earl_id: UUID | None = None,
        decision_type: str | None = None,
        since: datetime | None = None,
        limit: int = 100,
    ) -> list[FilterDecisionLog]:
        """Query decision history for audit.

        Retrieves historical filter decisions with optional filters.

        Args:
            earl_id: Filter by Earl who submitted content.
            decision_type: Filter by decision type ('accepted', 'rejected', 'blocked').
            since: Only return decisions after this timestamp.
            limit: Maximum number of results (default 100).

        Returns:
            List of FilterDecisionLog entries matching criteria.
        """
        ...

    async def get_decision_by_id(
        self,
        decision_id: UUID,
    ) -> FilterDecisionLog | None:
        """Get a specific decision by its ID.

        Args:
            decision_id: The UUID of the decision to retrieve.

        Returns:
            FilterDecisionLog if found, None otherwise.
        """
        ...

    async def count_decisions(
        self,
        earl_id: UUID | None = None,
        decision_type: str | None = None,
        since: datetime | None = None,
    ) -> int:
        """Count decisions matching criteria.

        Useful for rejection pattern detection and analytics.

        Args:
            earl_id: Filter by Earl who submitted content.
            decision_type: Filter by decision type.
            since: Only count decisions after this timestamp.

        Returns:
            Count of decisions matching criteria.
        """
        ...
