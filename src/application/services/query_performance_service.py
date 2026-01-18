"""Query Performance Service (Story 8.8, FR106).

This service monitors query performance and enforces the 30-second SLA
for historical queries under 10,000 events.

Constitutional Constraints:
- FR106: Historical queries SHALL complete within 30 seconds for ranges
         up to 10,000 events; larger ranges batched with progress indication.

Developer Golden Rules:
1. HALT CHECK FIRST - Check halt state before write operations
2. LOG EVERYTHING - All SLA violations must be logged
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from src.application.services.base import LoggingMixin
from src.domain.errors.failure_prevention import QueryPerformanceViolationError
from src.domain.models.batch_progress import BatchProgress

# FR106 SLA thresholds
QUERY_SLA_THRESHOLD_EVENTS: int = 10_000
QUERY_SLA_TIMEOUT_SECONDS: float = 30.0


class QueryPerformanceService(LoggingMixin):
    """Monitors query performance and enforces FR106 SLA.

    This service provides:
    1. Query tracking with timing (AC4)
    2. SLA compliance checking (AC4)
    3. Batch progress tracking for large queries (AC4)
    4. Query timeout logging as operational events (AC4)

    Constitutional Constraint (FR106):
    Historical queries SHALL complete within 30 seconds for ranges
    up to 10,000 events; larger ranges batched with progress indication.
    """

    def __init__(self) -> None:
        """Initialize the Query Performance Service."""
        self._init_logger(component="operational")
        self._active_queries: dict[str, dict[str, Any]] = {}
        self._completed_queries: list[dict[str, Any]] = []
        self._batch_progress: dict[str, BatchProgress] = {}

    async def start_query(
        self,
        query_id: str | None = None,
        event_count: int = 0,
    ) -> str:
        """Start tracking a query.

        Args:
            query_id: Optional query identifier. Generated if not provided.
            event_count: Expected number of events in the query.

        Returns:
            The query ID for tracking.
        """
        if query_id is None:
            query_id = f"q-{uuid4().hex[:8]}"

        log = self._log_operation(
            "start_query",
            query_id=query_id,
            event_count=event_count,
        )

        self._active_queries[query_id] = {
            "query_id": query_id,
            "event_count": event_count,
            "started_at": datetime.now(timezone.utc),
            "ended_at": None,
            "duration_seconds": None,
            "compliant": None,
            "batched": event_count > QUERY_SLA_THRESHOLD_EVENTS,
        }

        # Initialize batch progress for large queries
        if event_count > QUERY_SLA_THRESHOLD_EVENTS:
            self._batch_progress[query_id] = BatchProgress.create(
                query_id=query_id,
                total_events=event_count,
            )
            log.info(
                "large_query_started",
                batched=True,
                total_batches=self._batch_progress[query_id].total_batches,
            )
        else:
            log.info("query_started", batched=False)

        return query_id

    async def track_query(
        self,
        query_id: str,
        event_count: int,
        duration_ms: float,
    ) -> bool:
        """Track a completed query and check SLA compliance.

        Args:
            query_id: The query identifier.
            event_count: Number of events returned.
            duration_ms: Query duration in milliseconds.

        Returns:
            True if query was SLA compliant, False otherwise.
        """
        log = self._log_operation(
            "track_query",
            query_id=query_id,
            event_count=event_count,
            duration_ms=duration_ms,
        )

        duration_seconds = duration_ms / 1000.0
        ended_at = datetime.now(timezone.utc)

        # Check SLA compliance
        compliant = self.check_compliance(event_count, duration_seconds)

        # Record completion
        query_record = {
            "query_id": query_id,
            "event_count": event_count,
            "started_at": self._active_queries.get(query_id, {}).get("started_at"),
            "ended_at": ended_at,
            "duration_seconds": duration_seconds,
            "duration_ms": duration_ms,
            "compliant": compliant,
            "batched": event_count > QUERY_SLA_THRESHOLD_EVENTS,
        }

        # Move from active to completed
        self._active_queries.pop(query_id, None)
        self._completed_queries.append(query_record)
        self._batch_progress.pop(query_id, None)

        # Keep only last 1000 completed queries
        if len(self._completed_queries) > 1000:
            self._completed_queries = self._completed_queries[-1000:]

        if compliant:
            log.info(
                "query_completed_compliant",
                duration_seconds=duration_seconds,
                sla_seconds=QUERY_SLA_TIMEOUT_SECONDS,
            )
        else:
            log.warning(
                "query_sla_violation",
                duration_seconds=duration_seconds,
                sla_seconds=QUERY_SLA_TIMEOUT_SECONDS,
                overage_seconds=duration_seconds - QUERY_SLA_TIMEOUT_SECONDS,
            )

        return compliant

    def check_compliance(
        self,
        event_count: int,
        duration_seconds: float,
    ) -> bool:
        """Check if a query meets FR106 SLA requirements.

        Constitutional Constraint (FR106):
        Historical queries SHALL complete within 30 seconds for ranges
        up to 10,000 events.

        Args:
            event_count: Number of events in the query.
            duration_seconds: Query duration in seconds.

        Returns:
            True if compliant with SLA requirements.
        """
        # FR106: 30 second SLA applies to queries under 10k events
        if event_count <= QUERY_SLA_THRESHOLD_EVENTS:
            return duration_seconds <= QUERY_SLA_TIMEOUT_SECONDS

        # Larger queries have extended SLA (no strict timeout)
        return True

    async def raise_if_non_compliant(
        self,
        query_id: str,
        event_count: int,
        duration_seconds: float,
    ) -> None:
        """Raise error if query violates FR106 SLA.

        Args:
            query_id: The query identifier.
            event_count: Number of events in the query.
            duration_seconds: Query duration in seconds.

        Raises:
            QueryPerformanceViolationError: If SLA violated.
        """
        if not self.check_compliance(event_count, duration_seconds):
            raise QueryPerformanceViolationError(
                query_id=query_id,
                event_count=event_count,
                duration_seconds=duration_seconds,
                sla_seconds=QUERY_SLA_TIMEOUT_SECONDS,
            )

    async def update_batch_progress(
        self,
        query_id: str,
        processed_events: int,
    ) -> BatchProgress | None:
        """Update progress for a batched query.

        Args:
            query_id: The query identifier.
            processed_events: Additional events processed.

        Returns:
            Updated BatchProgress if query is batched, None otherwise.
        """
        if query_id not in self._batch_progress:
            return None

        log = self._log_operation(
            "update_batch_progress",
            query_id=query_id,
            additional_events=processed_events,
        )

        progress = self._batch_progress[query_id].with_progress(processed_events)
        self._batch_progress[query_id] = progress

        log.info(
            "batch_progress_updated",
            progress_percent=progress.progress_percent,
            current_batch=progress.current_batch,
            total_batches=progress.total_batches,
        )

        return progress

    async def get_batch_progress(self, query_id: str) -> BatchProgress | None:
        """Get current batch progress for a query.

        Args:
            query_id: The query identifier.

        Returns:
            BatchProgress if query is batched, None otherwise.
        """
        return self._batch_progress.get(query_id)

    async def get_active_queries(self) -> list[dict[str, Any]]:
        """Get all currently active queries.

        Returns:
            List of active query records.
        """
        return list(self._active_queries.values())

    async def get_recent_violations(self, limit: int = 100) -> list[dict[str, Any]]:
        """Get recent SLA violations.

        Args:
            limit: Maximum number of violations to return.

        Returns:
            List of non-compliant query records.
        """
        violations = [
            q for q in self._completed_queries if not q.get("compliant", True)
        ]
        return violations[-limit:]

    async def get_compliance_stats(self) -> dict[str, Any]:
        """Get query compliance statistics.

        Returns:
            Dictionary with compliance statistics including:
            - Total queries tracked
            - Compliant count
            - Non-compliant count
            - Compliance rate
            - Average duration
        """
        log = self._log_operation("get_compliance_stats")

        total = len(self._completed_queries)
        if total == 0:
            return {
                "total_queries": 0,
                "compliant_count": 0,
                "non_compliant_count": 0,
                "compliance_rate": 100.0,
                "average_duration_seconds": 0.0,
                "active_queries": len(self._active_queries),
            }

        compliant = sum(1 for q in self._completed_queries if q.get("compliant", True))
        non_compliant = total - compliant

        durations = [q.get("duration_seconds", 0) for q in self._completed_queries]
        avg_duration = sum(durations) / len(durations) if durations else 0.0

        stats = {
            "total_queries": total,
            "compliant_count": compliant,
            "non_compliant_count": non_compliant,
            "compliance_rate": (compliant / total) * 100.0,
            "average_duration_seconds": avg_duration,
            "active_queries": len(self._active_queries),
            "sla_threshold_events": QUERY_SLA_THRESHOLD_EVENTS,
            "sla_timeout_seconds": QUERY_SLA_TIMEOUT_SECONDS,
        }

        log.info(
            "compliance_stats_retrieved",
            compliance_rate=stats["compliance_rate"],
            total_queries=total,
        )

        return stats
