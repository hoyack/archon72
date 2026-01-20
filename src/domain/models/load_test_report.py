"""Load test report domain model (Story 2B.7, NFR-10.5).

This module defines the report structure for completed load tests,
capturing comprehensive metrics including latency distribution,
throughput, and failure analysis.

Constitutional Constraints:
- NFR-10.1: Deliberation end-to-end latency p95 < 5 minutes
- NFR-10.5: Concurrent deliberations - 100+ simultaneous sessions
- CT-11: Silent failure destroys legitimacy - report all failures
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

# 5 minutes in milliseconds - NFR-10.1 threshold
NFR_10_1_THRESHOLD_MS = 300_000


@dataclass(frozen=True, eq=True)
class LoadTestReport:
    """Report from a completed load test (Story 2B.7, NFR-10.5).

    Captures comprehensive metrics from load test execution including
    latency distribution, throughput, and failure analysis.

    Attributes:
        test_id: Unique identifier for this test run.
        config: The LoadTestConfig used (as dict).
        started_at: When the test started (UTC).
        completed_at: When the test finished (UTC).
        total_petitions: Number of petitions processed.
        successful_deliberations: Count of successful completions.
        failed_deliberations: Count of failures.
        timeout_deliberations: Count of timeouts.
        latency_p50_ms: Median latency in milliseconds.
        latency_p95_ms: 95th percentile latency.
        latency_p99_ms: 99th percentile latency.
        latency_max_ms: Maximum latency observed.
        throughput_per_second: Petitions completed per second.
        resource_metrics: CPU, memory, connection usage dict.
        failure_breakdown: Mapping of failure reason to count.
        witness_chain_valid_count: Sessions with valid witness chains.

    Example:
        >>> report = LoadTestReport(
        ...     test_id=uuid4(),
        ...     config={"concurrent_sessions": 100},
        ...     started_at=datetime.now(timezone.utc),
        ...     completed_at=datetime.now(timezone.utc),
        ...     total_petitions=1000,
        ...     successful_deliberations=950,
        ...     failed_deliberations=30,
        ...     timeout_deliberations=20,
        ...     latency_p50_ms=1000,
        ...     latency_p95_ms=5000,
        ...     latency_p99_ms=10000,
        ...     latency_max_ms=15000,
        ...     throughput_per_second=10.5,
        ... )
        >>> assert report.success_rate == 95.0
        >>> assert report.nfr_10_1_pass is True
    """

    test_id: UUID
    config: dict[str, Any]
    started_at: datetime
    completed_at: datetime
    total_petitions: int
    successful_deliberations: int
    failed_deliberations: int
    timeout_deliberations: int
    latency_p50_ms: float
    latency_p95_ms: float
    latency_p99_ms: float
    latency_max_ms: float
    throughput_per_second: float
    resource_metrics: dict[str, float] = field(default_factory=dict)
    failure_breakdown: dict[str, int] = field(default_factory=dict)
    witness_chain_valid_count: int = field(default=0)

    @property
    def duration_seconds(self) -> float:
        """Get test duration in seconds."""
        return (self.completed_at - self.started_at).total_seconds()

    @property
    def success_rate(self) -> float:
        """Get success rate as percentage."""
        if self.total_petitions == 0:
            return 0.0
        return (self.successful_deliberations / self.total_petitions) * 100

    @property
    def nfr_10_1_pass(self) -> bool:
        """Check if NFR-10.1 (p95 < 5 minutes) is satisfied."""
        return self.latency_p95_ms < NFR_10_1_THRESHOLD_MS

    @property
    def nfr_10_5_pass(self) -> bool:
        """Check if NFR-10.5 (100+ concurrent) was tested."""
        return self.config.get("concurrent_sessions", 0) >= 100

    @property
    def all_witness_chains_valid(self) -> bool:
        """Check if all witness chains are valid."""
        return self.witness_chain_valid_count == self.successful_deliberations

    def summary(self) -> str:
        """Generate human-readable summary."""
        nfr_10_1_status = "PASS" if self.nfr_10_1_pass else "FAIL"
        nfr_10_5_status = "PASS" if self.nfr_10_5_pass else "N/A"

        lines = [
            f"Load Test Report ({self.test_id})",
            "=" * 50,
            f"Duration: {self.duration_seconds:.1f}s",
            f"Petitions: {self.total_petitions}",
            f"Success Rate: {self.success_rate:.1f}%",
            f"  - Successful: {self.successful_deliberations}",
            f"  - Failed: {self.failed_deliberations}",
            f"  - Timeout: {self.timeout_deliberations}",
            "Latency:",
            f"  - p50: {self.latency_p50_ms:.0f}ms",
            f"  - p95: {self.latency_p95_ms:.0f}ms",
            f"  - p99: {self.latency_p99_ms:.0f}ms",
            f"  - max: {self.latency_max_ms:.0f}ms",
            f"Throughput: {self.throughput_per_second:.2f}/s",
            f"NFR-10.1 (p95 < 5min): {nfr_10_1_status}",
            f"NFR-10.5 (100+ concurrent): {nfr_10_5_status}",
            f"Witness Chains Valid: {self.witness_chain_valid_count}/{self.successful_deliberations}",
        ]

        if self.failure_breakdown:
            lines.append("Failure Breakdown:")
            for reason, count in sorted(self.failure_breakdown.items()):
                lines.append(f"  - {reason}: {count}")

        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "test_id": str(self.test_id),
            "config": self.config,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat(),
            "duration_seconds": self.duration_seconds,
            "total_petitions": self.total_petitions,
            "successful_deliberations": self.successful_deliberations,
            "failed_deliberations": self.failed_deliberations,
            "timeout_deliberations": self.timeout_deliberations,
            "success_rate": self.success_rate,
            "latency_p50_ms": self.latency_p50_ms,
            "latency_p95_ms": self.latency_p95_ms,
            "latency_p99_ms": self.latency_p99_ms,
            "latency_max_ms": self.latency_max_ms,
            "throughput_per_second": self.throughput_per_second,
            "resource_metrics": self.resource_metrics,
            "failure_breakdown": self.failure_breakdown,
            "witness_chain_valid_count": self.witness_chain_valid_count,
            "nfr_10_1_pass": self.nfr_10_1_pass,
            "nfr_10_5_pass": self.nfr_10_5_pass,
            "all_witness_chains_valid": self.all_witness_chains_valid,
            "schema_version": 1,
        }
