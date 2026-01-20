"""Load test metrics domain model (Story 2B.7, NFR-10.5).

This module defines the real-time metrics structure for monitoring
load test execution, enabling progress tracking and resource monitoring.

Constitutional Constraints:
- NFR-10.1: Deliberation end-to-end latency p95 < 5 minutes
- NFR-10.5: Concurrent deliberations - 100+ simultaneous sessions
- CT-11: Silent failure destroys legitimacy - track all failures
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(eq=True)
class LoadTestMetrics:
    """Real-time metrics during load test execution (Story 2B.7).

    Captures point-in-time metrics for monitoring load test progress.
    Unlike LoadTestReport, this is mutable for incremental updates.

    Attributes:
        timestamp: When these metrics were captured (UTC).
        active_sessions: Current concurrent deliberations.
        completed_sessions: Total completed so far.
        failed_sessions: Total failed so far.
        timeout_sessions: Total timed out so far.
        pending_petitions: Petitions waiting to start.
        current_throughput: Recent petitions/second (sliding window).
        memory_usage_mb: Current memory consumption.
        db_connection_count: Active database connections.
        event_queue_depth: Pending events to write.
        latencies_ms: List of completed latencies for percentile calc.

    Example:
        >>> metrics = LoadTestMetrics(pending_petitions=100)
        >>> metrics.start_session()
        >>> assert metrics.active_sessions == 1
        >>> assert metrics.pending_petitions == 99
        >>> metrics.record_completion(150.0, success=True)
        >>> assert metrics.completed_sessions == 1
        >>> assert metrics.active_sessions == 0
    """

    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    active_sessions: int = field(default=0)
    completed_sessions: int = field(default=0)
    failed_sessions: int = field(default=0)
    timeout_sessions: int = field(default=0)
    pending_petitions: int = field(default=0)
    current_throughput: float = field(default=0.0)
    memory_usage_mb: float = field(default=0.0)
    db_connection_count: int = field(default=0)
    event_queue_depth: int = field(default=0)
    latencies_ms: list[float] = field(default_factory=list)

    def record_completion(
        self,
        latency_ms: float,
        success: bool = True,
        is_timeout: bool = False,
    ) -> None:
        """Record a completed deliberation.

        Args:
            latency_ms: Time taken for deliberation in milliseconds.
            success: True if deliberation succeeded, False otherwise.
            is_timeout: True if failure was due to timeout.
        """
        self.latencies_ms.append(latency_ms)
        if success:
            self.completed_sessions += 1
        elif is_timeout:
            self.timeout_sessions += 1
            self.failed_sessions += 1
        else:
            self.failed_sessions += 1
        if self.active_sessions > 0:
            self.active_sessions -= 1

    def start_session(self) -> None:
        """Record a session starting."""
        self.active_sessions += 1
        if self.pending_petitions > 0:
            self.pending_petitions -= 1

    def calculate_percentile(self, percentile: float) -> float:
        """Calculate latency percentile from recorded latencies.

        Args:
            percentile: Percentile to calculate (0-100).

        Returns:
            Latency value at the given percentile, or 0.0 if no data.

        Example:
            >>> metrics = LoadTestMetrics()
            >>> metrics.latencies_ms = [100, 200, 300, 400, 500]
            >>> metrics.calculate_percentile(50)  # Median
            300.0
            >>> metrics.calculate_percentile(90)
            500.0
        """
        if not self.latencies_ms:
            return 0.0
        if not 0 <= percentile <= 100:
            raise ValueError(f"percentile must be 0-100, got {percentile}")

        sorted_latencies = sorted(self.latencies_ms)
        index = int(len(sorted_latencies) * (percentile / 100))
        index = min(index, len(sorted_latencies) - 1)
        return sorted_latencies[index]

    @property
    def total_processed(self) -> int:
        """Get total petitions processed (success + failure)."""
        return self.completed_sessions + self.failed_sessions

    @property
    def latency_p50_ms(self) -> float:
        """Get median latency."""
        return self.calculate_percentile(50)

    @property
    def latency_p95_ms(self) -> float:
        """Get 95th percentile latency."""
        return self.calculate_percentile(95)

    @property
    def latency_p99_ms(self) -> float:
        """Get 99th percentile latency."""
        return self.calculate_percentile(99)

    @property
    def latency_max_ms(self) -> float:
        """Get maximum latency."""
        if not self.latencies_ms:
            return 0.0
        return max(self.latencies_ms)

    def reset(self, pending_petitions: int = 0) -> None:
        """Reset all metrics for a new test run.

        Args:
            pending_petitions: Number of petitions to process.
        """
        self.timestamp = datetime.now(timezone.utc)
        self.active_sessions = 0
        self.completed_sessions = 0
        self.failed_sessions = 0
        self.timeout_sessions = 0
        self.pending_petitions = pending_petitions
        self.current_throughput = 0.0
        self.memory_usage_mb = 0.0
        self.db_connection_count = 0
        self.event_queue_depth = 0
        self.latencies_ms.clear()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "active_sessions": self.active_sessions,
            "completed_sessions": self.completed_sessions,
            "failed_sessions": self.failed_sessions,
            "timeout_sessions": self.timeout_sessions,
            "pending_petitions": self.pending_petitions,
            "total_processed": self.total_processed,
            "current_throughput": self.current_throughput,
            "memory_usage_mb": self.memory_usage_mb,
            "db_connection_count": self.db_connection_count,
            "event_queue_depth": self.event_queue_depth,
            "latency_count": len(self.latencies_ms),
            "latency_p50_ms": self.latency_p50_ms,
            "latency_p95_ms": self.latency_p95_ms,
            "latency_p99_ms": self.latency_p99_ms,
            "latency_max_ms": self.latency_max_ms,
            "schema_version": 1,
        }

    def progress_summary(self, total_petitions: int) -> str:
        """Generate a progress summary string.

        Args:
            total_petitions: Total petitions in the test.

        Returns:
            Human-readable progress string.
        """
        pct = (self.total_processed / total_petitions * 100) if total_petitions > 0 else 0
        return (
            f"Progress: {self.total_processed}/{total_petitions} ({pct:.1f}%) | "
            f"Active: {self.active_sessions} | "
            f"Throughput: {self.current_throughput:.1f}/s | "
            f"Failed: {self.failed_sessions}"
        )
