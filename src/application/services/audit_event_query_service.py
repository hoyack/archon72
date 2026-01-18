"""Audit event query service (Story 9.5, FR108).

Service for querying and analyzing audit events from the constitutional
record. Enables external observers to view audit history and trends.

Architecture Pattern:
- Story 9-3: QuarterlyAuditService WRITES audit events
- Story 9-5: AuditEventQueryService READS audit events (this story)

Constitutional Constraints:
- FR108: Audit results logged as events, audit history queryable
- CT-11: HALT CHECK FIRST on all operations
- CT-12: Events are witnessed when written (read concern only here)
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Final

from src.application.ports.event_query import EventQueryProtocol

logger = logging.getLogger(__name__)

from src.application.ports.halt_checker import HaltChecker
from src.domain.errors.audit_event import (
    AuditTrendCalculationError,
    InsufficientAuditDataError,
)
from src.domain.errors.writer import SystemHaltedError
from src.domain.models.audit_event import (
    AUDIT_EVENT_TYPE_PREFIX,
    AuditCompletionStatus,
    AuditEvent,
    AuditEventType,
    AuditTrend,
    QuarterStats,
)

# System agent ID for audit event query operations
AUDIT_EVENT_QUERY_SYSTEM_AGENT_ID: Final[str] = "system:audit_event_query"


class AuditEventQueryService:
    """Service for querying audit events from the constitutional record (FR108).

    This service provides read access to audit events stored by
    QuarterlyAuditService. It supports filtering, trend analysis,
    and historical queries for external observers.

    Constitutional Constraints:
    - CT-11: HALT CHECK FIRST on every public method
    - FR108: Audit history is queryable with trend analysis

    Usage:
        service = AuditEventQueryService(
            event_query=event_query_port,
            halt_checker=halt_checker,
        )
        events = await service.get_audit_events(limit=50)
        trend = await service.get_audit_trend(quarters=4)
    """

    def __init__(
        self,
        event_query: EventQueryProtocol,
        halt_checker: HaltChecker,
    ) -> None:
        """Initialize audit event query service.

        Args:
            event_query: Port for querying events from the store.
            halt_checker: Port for checking halt state (CT-11).
        """
        self._event_query = event_query
        self._halt_checker = halt_checker

    async def _check_halt(self) -> None:
        """Check halt state and raise if halted (CT-11).

        Raises:
            SystemHaltedError: If system is halted.
        """
        if await self._halt_checker.is_halted():
            raise SystemHaltedError("FR108: System halted - audit event query blocked")

    def _to_audit_event(self, raw_event: dict[str, object]) -> AuditEvent:
        """Transform raw event data to AuditEvent domain model.

        Args:
            raw_event: Raw event dictionary from event store.

        Returns:
            AuditEvent domain model.
        """
        payload = raw_event.get("payload", {})
        if not isinstance(payload, dict):
            payload = {}

        # Parse timestamp
        timestamp_str = str(raw_event.get("timestamp", ""))
        try:
            timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        except ValueError:
            logger.warning(
                "FR108: Malformed timestamp in audit event, using current time: %s",
                timestamp_str,
            )
            timestamp = datetime.now()

        # Extract event_id with warning for malformed events
        event_id = str(raw_event.get("event_id", ""))
        if not event_id:
            logger.warning(
                "FR108: Missing event_id in audit event, using 'unknown' fallback"
            )
            event_id = "unknown"

        # Extract event_type with warning for malformed events
        event_type = str(raw_event.get("event_type", ""))
        if not event_type:
            logger.warning(
                "FR108: Missing event_type in audit event %s, using 'unknown' fallback",
                event_id,
            )
            event_type = "unknown"

        # Extract audit_id with fallback for malformed events
        audit_id = str(payload.get("audit_id", ""))
        if not audit_id:
            logger.warning(
                "FR108: Missing audit_id in audit event %s payload, using event_id as fallback",
                event_id,
            )
            audit_id = event_id

        return AuditEvent(
            event_id=event_id,
            event_type=event_type,
            audit_id=audit_id,
            quarter=payload.get("quarter") if "quarter" in payload else None,
            timestamp=timestamp,
            payload=payload,
        )

    async def get_audit_events(self, limit: int = 100) -> list[AuditEvent]:
        """Query all audit events (FR108).

        HALT CHECK FIRST (CT-11).

        Args:
            limit: Maximum events to return.

        Returns:
            List of AuditEvent objects, ordered chronologically (oldest first).

        Raises:
            SystemHaltedError: If system is halted.
        """
        # HALT CHECK FIRST (Golden Rule #1, CT-11)
        await self._check_halt()

        # Query events with audit prefix
        raw_events = await self._event_query.query_events_by_type_prefix(
            type_prefix=AUDIT_EVENT_TYPE_PREFIX,
            limit=limit,
        )

        # Transform to domain objects
        return [self._to_audit_event(event) for event in raw_events]

    async def get_audit_events_by_type(
        self,
        event_type: str,
        limit: int = 100,
    ) -> list[AuditEvent]:
        """Query audit events by specific type (FR108).

        HALT CHECK FIRST (CT-11).

        Args:
            event_type: Exact event type to match (e.g., "audit.completed").
            limit: Maximum events to return.

        Returns:
            List of AuditEvent objects matching the type.

        Raises:
            SystemHaltedError: If system is halted.
        """
        # HALT CHECK FIRST (Golden Rule #1, CT-11)
        await self._check_halt()

        raw_events = await self._event_query.query_events_by_type(
            event_type=event_type,
            limit=limit,
        )

        return [self._to_audit_event(event) for event in raw_events]

    async def get_audit_events_by_quarter(
        self,
        quarter: str,
        limit: int = 100,
    ) -> list[AuditEvent]:
        """Query audit events for a specific quarter (FR108).

        HALT CHECK FIRST (CT-11).

        Args:
            quarter: Quarter identifier (e.g., "2026-Q1").
            limit: Maximum events to return.

        Returns:
            List of AuditEvent objects for the quarter.

        Raises:
            SystemHaltedError: If system is halted.
        """
        # HALT CHECK FIRST (Golden Rule #1, CT-11)
        await self._check_halt()

        # Query completed events filtered by quarter
        raw_events = await self._event_query.query_events_with_payload_filter(
            event_type=AuditEventType.COMPLETED.value,
            payload_filter={"quarter": quarter},
            limit=limit,
        )

        return [self._to_audit_event(event) for event in raw_events]

    async def get_audit_trend(self, quarters: int = 4) -> AuditTrend:
        """Calculate audit trend over quarters (FR108).

        HALT CHECK FIRST (CT-11).

        Analyzes completed audit events to provide trend data for
        external observers. Returns aggregated statistics by quarter.

        Args:
            quarters: Number of recent quarters to analyze.

        Returns:
            AuditTrend with aggregated statistics.

        Raises:
            SystemHaltedError: If system is halted.
            InsufficientAuditDataError: If no audit data available.
            AuditTrendCalculationError: If trend calculation fails.
        """
        # HALT CHECK FIRST (Golden Rule #1, CT-11)
        await self._check_halt()

        # Get completed audit events
        raw_events = await self._event_query.query_events_by_type(
            event_type=AuditEventType.COMPLETED.value,
            limit=quarters * 10,  # Buffer for multiple audits per quarter
        )

        if not raw_events:
            raise InsufficientAuditDataError(
                message="No completed audit events found for trend analysis",
                requested_quarters=quarters,
                available_quarters=0,
            )

        # Aggregate by quarter
        quarter_data: dict[str, dict[str, int | str]] = {}
        total_violations = 0

        for raw_event in raw_events:
            payload = raw_event.get("payload", {})
            if not isinstance(payload, dict):
                continue

            quarter = str(payload.get("quarter", "unknown"))
            status = str(payload.get("status", "unknown"))
            violations = payload.get("violations_found", 0)
            if not isinstance(violations, int):
                violations = 0

            if quarter not in quarter_data:
                quarter_data[quarter] = {
                    "audits": 0,
                    "violations": 0,
                    "clean": 0,
                    "violations_found": 0,
                    "failed": 0,
                }

            quarter_data[quarter]["audits"] = int(quarter_data[quarter]["audits"]) + 1
            quarter_data[quarter]["violations"] = (
                int(quarter_data[quarter]["violations"]) + violations
            )
            total_violations += violations

            # Track status counts
            if status == "clean":
                quarter_data[quarter]["clean"] = int(quarter_data[quarter]["clean"]) + 1
            elif status == "violations_found":
                quarter_data[quarter]["violations_found"] = (
                    int(quarter_data[quarter]["violations_found"]) + 1
                )
            elif status == "failed":
                quarter_data[quarter]["failed"] = (
                    int(quarter_data[quarter]["failed"]) + 1
                )

        # Build quarter stats
        quarter_stats: list[QuarterStats] = []
        total_audits = 0
        clean_audits = 0
        violation_audits = 0
        failed_audits = 0

        # Sort quarters chronologically and take requested number
        sorted_quarters = sorted(quarter_data.keys())[-quarters:]

        def safe_int(value: int | str, default: int = 0) -> int:
            """Safely convert value to int with fallback."""
            if isinstance(value, int):
                return value
            try:
                return int(value)
            except (ValueError, TypeError):
                logger.warning(
                    "FR108: Invalid integer value in quarter data: %s, using default %d",
                    value,
                    default,
                )
                return default

        for quarter in sorted_quarters:
            data = quarter_data[quarter]
            audits = safe_int(data["audits"])
            violations = safe_int(data["violations"])
            clean = safe_int(data["clean"])
            violations_count = safe_int(data["violations_found"])
            failed = safe_int(data["failed"])

            # Determine overall quarter status
            if failed > 0:
                status: AuditCompletionStatus = "failed"
            elif violations_count > 0:
                status = "violations_found"
            elif clean > 0:
                status = "clean"
            else:
                status = "not_run"

            quarter_stats.append(
                QuarterStats(
                    quarter=quarter,
                    audits=audits,
                    violations=violations,
                    status=status,
                )
            )

            total_audits += audits
            clean_audits += clean
            violation_audits += violations_count
            failed_audits += failed

        # Calculate average
        try:
            average = total_violations / total_audits if total_audits > 0 else 0.0
        except ZeroDivisionError:
            average = 0.0
        except Exception as e:
            raise AuditTrendCalculationError(str(e)) from e

        return AuditTrend(
            quarters=tuple(sorted_quarters),
            total_audits=total_audits,
            total_violations=total_violations,
            clean_audits=clean_audits,
            violation_audits=violation_audits,
            failed_audits=failed_audits,
            average_violations_per_audit=average,
            quarter_breakdown=tuple(quarter_stats),
        )

    async def get_available_quarters(self) -> list[str]:
        """Get list of quarters with audit data (FR108).

        HALT CHECK FIRST (CT-11).

        Returns:
            List of quarter strings (e.g., ["2026-Q1", "2026-Q2"]).

        Raises:
            SystemHaltedError: If system is halted.
        """
        # HALT CHECK FIRST (Golden Rule #1, CT-11)
        await self._check_halt()

        quarters = await self._event_query.get_distinct_payload_values(
            event_type=AuditEventType.COMPLETED.value,
            payload_field="quarter",
        )

        # Filter and sort
        return sorted(str(q) for q in quarters if q is not None and isinstance(q, str))

    async def get_audit_count(self) -> int:
        """Get total count of completed audits (FR108).

        HALT CHECK FIRST (CT-11).

        Returns:
            Total number of completed audits.

        Raises:
            SystemHaltedError: If system is halted.
        """
        # HALT CHECK FIRST (Golden Rule #1, CT-11)
        await self._check_halt()

        return await self._event_query.count_events_by_type(
            event_type=AuditEventType.COMPLETED.value,
        )

    async def get_violation_events(
        self,
        audit_id: str | None = None,
        limit: int = 100,
    ) -> list[AuditEvent]:
        """Get violation flagged events (FR108).

        HALT CHECK FIRST (CT-11).

        Args:
            audit_id: Optional audit ID to filter by.
            limit: Maximum events to return.

        Returns:
            List of violation flagged events.

        Raises:
            SystemHaltedError: If system is halted.
        """
        # HALT CHECK FIRST (Golden Rule #1, CT-11)
        await self._check_halt()

        if audit_id:
            raw_events = await self._event_query.query_events_with_payload_filter(
                event_type=AuditEventType.VIOLATION_FLAGGED.value,
                payload_filter={"audit_id": audit_id},
                limit=limit,
            )
        else:
            raw_events = await self._event_query.query_events_by_type(
                event_type=AuditEventType.VIOLATION_FLAGGED.value,
                limit=limit,
            )

        return [self._to_audit_event(event) for event in raw_events]
