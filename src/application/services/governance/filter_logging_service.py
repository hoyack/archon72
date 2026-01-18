"""FilterLoggingService - Logs all filter decisions to the ledger.

Story: consent-gov-3.3: Filter Decision Logging

This service implements filter decision logging per FR20:
- All filter_content() calls are logged
- preview_filter() calls are NOT logged
- Content is hashed for privacy
- Events emitted to ledger for Knight observability

Event Type:
- custodial.filter.decision_logged

References:
- FR19: Earl can view filter outcome before content is sent
- FR20: System can log all filter decisions with version and timestamp
- NFR-AUDIT-02: Complete audit trail
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from uuid import UUID, uuid4

from src.application.ports.governance.coercion_filter_port import MessageType
from src.application.ports.governance.filter_decision_log_port import (
    FilterDecisionLogPort,
)
from src.application.ports.governance.ledger_port import GovernanceLedgerPort
from src.application.ports.time_authority import TimeAuthorityProtocol
from src.domain.governance.events.event_envelope import GovernanceEvent
from src.domain.governance.events.schema_versions import CURRENT_SCHEMA_VERSION
from src.domain.governance.filter import (
    FilterDecision,
    FilterDecisionLog,
    FilterResult,
    TransformationLog,
)

# Event type for filter decision logging
FILTER_DECISION_LOGGED_EVENT = "custodial.filter.decision_logged"


class FilterLoggingService(FilterDecisionLogPort):
    """Service for logging filter decisions to the governance ledger.

    This service implements the FilterDecisionLogPort interface,
    providing:
    - Logging of all filter decisions with content hashes
    - Event emission to ledger for Knight observability
    - Decision history queries for audit

    Content Privacy:
    All content is hashed using BLAKE3 before logging.
    Raw content is NEVER stored in logs.

    Usage:
        service = FilterLoggingService(ledger, time_authority)

        # Log a decision
        log_entry = await service.log_decision(
            result=filter_result,
            input_content="Please review...",
            message_type=MessageType.TASK_ACTIVATION,
            earl_id=earl_uuid,
        )

        # Query history
        history = await service.get_decision_history(
            earl_id=earl_uuid,
            decision_type="rejected",
            since=datetime(2026, 1, 1),
        )
    """

    def __init__(
        self,
        ledger: GovernanceLedgerPort,
        time_authority: TimeAuthorityProtocol,
    ) -> None:
        """Initialize the FilterLoggingService.

        Args:
            ledger: The governance ledger for event persistence.
            time_authority: Time authority for timestamps.
        """
        self._ledger = ledger
        self._time_authority = time_authority
        # In-memory storage for decision history (projection)
        # In production, this would be backed by a projection table
        self._decisions: dict[UUID, FilterDecisionLog] = {}

    async def log_decision(
        self,
        result: FilterResult,
        input_content: str,
        message_type: MessageType,
        earl_id: UUID,
    ) -> FilterDecisionLog:
        """Log a filter decision to the ledger.

        Creates a FilterDecisionLog entry with:
        - Content hashes (not raw content)
        - Filter version for auditability
        - Transformation/rejection/violation details

        Emits 'custodial.filter.decision_logged' event to ledger.

        Args:
            result: The FilterResult from the filter service.
            input_content: Raw input content (will be hashed, not stored).
            message_type: Type of message that was filtered.
            earl_id: Earl who submitted the content.

        Returns:
            FilterDecisionLog capturing the logged decision.
        """
        decision_id = uuid4()
        now = self._time_authority.now()

        # Hash content for privacy
        input_hash = self._hash_content(input_content)
        output_hash = None
        if result.content is not None:
            output_hash = self._hash_content(result.content.content)

        # Create the log entry based on decision type
        if result.decision == FilterDecision.ACCEPTED:
            log_entry = self._create_accepted_log(
                decision_id=decision_id,
                input_hash=input_hash,
                output_hash=output_hash,
                result=result,
                message_type=message_type,
                earl_id=earl_id,
                timestamp=now,
            )
        elif result.decision == FilterDecision.REJECTED:
            log_entry = self._create_rejected_log(
                decision_id=decision_id,
                input_hash=input_hash,
                result=result,
                message_type=message_type,
                earl_id=earl_id,
                timestamp=now,
            )
        else:  # BLOCKED
            log_entry = self._create_blocked_log(
                decision_id=decision_id,
                input_hash=input_hash,
                result=result,
                message_type=message_type,
                earl_id=earl_id,
                timestamp=now,
            )

        # Emit event to ledger
        await self._emit_decision_event(log_entry, earl_id)

        # Store in projection
        self._decisions[decision_id] = log_entry

        return log_entry

    async def get_decision_history(
        self,
        earl_id: UUID | None = None,
        decision_type: str | None = None,
        since: datetime | None = None,
        limit: int = 100,
    ) -> list[FilterDecisionLog]:
        """Query decision history for audit.

        Args:
            earl_id: Filter by Earl who submitted content.
            decision_type: Filter by decision type ('accepted', 'rejected', 'blocked').
            since: Only return decisions after this timestamp.
            limit: Maximum number of results (default 100).

        Returns:
            List of FilterDecisionLog entries matching criteria.
        """
        results = []

        for decision in self._decisions.values():
            # Apply filters
            if earl_id is not None and decision.earl_id != earl_id:
                continue

            if decision_type is not None:
                if decision.decision.value.lower() != decision_type.lower():
                    continue

            if since is not None and decision.timestamp < since:
                continue

            results.append(decision)

            if len(results) >= limit:
                break

        # Sort by timestamp descending (most recent first)
        results.sort(key=lambda d: d.timestamp, reverse=True)

        return results[:limit]

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
        return self._decisions.get(decision_id)

    async def count_decisions(
        self,
        earl_id: UUID | None = None,
        decision_type: str | None = None,
        since: datetime | None = None,
    ) -> int:
        """Count decisions matching criteria.

        Args:
            earl_id: Filter by Earl who submitted content.
            decision_type: Filter by decision type.
            since: Only count decisions after this timestamp.

        Returns:
            Count of decisions matching criteria.
        """
        count = 0

        for decision in self._decisions.values():
            if earl_id is not None and decision.earl_id != earl_id:
                continue

            if decision_type is not None:
                if decision.decision.value.lower() != decision_type.lower():
                    continue

            if since is not None and decision.timestamp < since:
                continue

            count += 1

        return count

    def _hash_content(self, content: str) -> str:
        """Hash content using BLAKE2b (BLAKE3-compatible for this context).

        We use BLAKE2b with 32-byte digest as BLAKE3 is not in stdlib.
        The hash is prefixed with the algorithm name.

        Args:
            content: Content to hash.

        Returns:
            Hash string in format "blake3:hexdigest".
        """
        # Using blake2b as BLAKE3 stand-in (32-byte digest = 256-bit)
        digest = hashlib.blake2b(content.encode(), digest_size=32).hexdigest()
        return f"blake3:{digest}"

    def _create_accepted_log(
        self,
        decision_id: UUID,
        input_hash: str,
        output_hash: str | None,
        result: FilterResult,
        message_type: MessageType,
        earl_id: UUID,
        timestamp: datetime,
    ) -> FilterDecisionLog:
        """Create log entry for ACCEPTED decision."""
        # Convert transformations to log format
        transformation_logs = tuple(
            TransformationLog(
                rule_id=t.rule_id,
                pattern=t.pattern_matched,
                original_hash=self._hash_content(t.original_text),
                replacement_hash=self._hash_content(t.replacement_text),
            )
            for t in result.transformations
        )

        return FilterDecisionLog.for_accepted(
            decision_id=decision_id,
            input_hash=input_hash,
            output_hash=output_hash or input_hash,  # Same if no transformation
            filter_version=result.version,
            message_type=message_type,
            earl_id=earl_id,
            timestamp=timestamp,
            transformations=transformation_logs,
        )

    def _create_rejected_log(
        self,
        decision_id: UUID,
        input_hash: str,
        result: FilterResult,
        message_type: MessageType,
        earl_id: UUID,
        timestamp: datetime,
    ) -> FilterDecisionLog:
        """Create log entry for REJECTED decision."""
        return FilterDecisionLog.for_rejected(
            decision_id=decision_id,
            input_hash=input_hash,
            filter_version=result.version,
            message_type=message_type,
            earl_id=earl_id,
            timestamp=timestamp,
            rejection_reason=result.rejection_reason,
            rejection_guidance=result.rejection_guidance,
        )

    def _create_blocked_log(
        self,
        decision_id: UUID,
        input_hash: str,
        result: FilterResult,
        message_type: MessageType,
        earl_id: UUID,
        timestamp: datetime,
    ) -> FilterDecisionLog:
        """Create log entry for BLOCKED decision."""
        return FilterDecisionLog.for_blocked(
            decision_id=decision_id,
            input_hash=input_hash,
            filter_version=result.version,
            message_type=message_type,
            earl_id=earl_id,
            timestamp=timestamp,
            violation_type=result.violation_type,
            violation_details=result.violation_details,
        )

    async def _emit_decision_event(
        self,
        log_entry: FilterDecisionLog,
        earl_id: UUID,
    ) -> None:
        """Emit filter decision event to the ledger.

        Creates and persists a GovernanceEvent for the filter decision.
        This makes the decision observable to Knight.

        Args:
            log_entry: The FilterDecisionLog to emit.
            earl_id: The Earl who submitted the content.
        """
        event = GovernanceEvent.create(
            event_id=uuid4(),
            event_type=FILTER_DECISION_LOGGED_EVENT,
            timestamp=log_entry.timestamp,
            actor_id="system",  # Filter is system actor
            trace_id=str(log_entry.decision_id),
            payload=log_entry.to_event_payload(),
            schema_version=CURRENT_SCHEMA_VERSION,
        )

        await self._ledger.append_event(event)
