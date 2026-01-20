"""Load test configuration domain model (Story 2B.7, NFR-10.5).

This module defines the configuration parameters for deliberation load testing,
enabling verification of system performance under concurrent load.

Constitutional Constraints:
- NFR-9.4: Load test harness simulates 10k petition flood
- NFR-10.1: Deliberation end-to-end latency p95 < 5 minutes
- NFR-10.5: Concurrent deliberations - 100+ simultaneous sessions
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, eq=True)
class LoadTestConfig:
    """Configuration for deliberation load testing (Story 2B.7, NFR-10.5).

    Defines the parameters for load test execution including concurrency,
    fault injection, and reporting intervals.

    Attributes:
        concurrent_sessions: Max simultaneous deliberations (default: 100).
        total_petitions: Total petitions to process (default: 1000).
        petition_batch_size: Petitions submitted per batch (default: 100).
        archon_response_latency_ms: Simulated archon delay (default: 100).
        failure_injection_rate: Fraction to fail (0.0-1.0, default: 0.0).
        timeout_injection_rate: Fraction to timeout (0.0-1.0, default: 0.0).
        report_interval_seconds: Progress report frequency (default: 5).

    Example:
        >>> config = LoadTestConfig(
        ...     concurrent_sessions=100,
        ...     total_petitions=1000,
        ...     failure_injection_rate=0.05,
        ... )
        >>> assert config.concurrent_sessions == 100
        >>> assert config.failure_injection_rate == 0.05

    Raises:
        ValueError: If any configuration parameter is invalid.
    """

    concurrent_sessions: int = field(default=100)
    total_petitions: int = field(default=1000)
    petition_batch_size: int = field(default=100)
    archon_response_latency_ms: int = field(default=100)
    failure_injection_rate: float = field(default=0.0)
    timeout_injection_rate: float = field(default=0.0)
    report_interval_seconds: int = field(default=5)

    def __post_init__(self) -> None:
        """Validate configuration invariants."""
        if self.concurrent_sessions < 1:
            raise ValueError(
                f"concurrent_sessions must be >= 1, got {self.concurrent_sessions}"
            )
        if self.concurrent_sessions > 500:
            raise ValueError(
                f"concurrent_sessions must be <= 500, got {self.concurrent_sessions}"
            )
        if self.total_petitions < 1:
            raise ValueError(
                f"total_petitions must be >= 1, got {self.total_petitions}"
            )
        if self.petition_batch_size < 1:
            raise ValueError(
                f"petition_batch_size must be >= 1, got {self.petition_batch_size}"
            )
        if self.archon_response_latency_ms < 0:
            raise ValueError(
                f"archon_response_latency_ms must be >= 0, "
                f"got {self.archon_response_latency_ms}"
            )
        if not 0.0 <= self.failure_injection_rate <= 1.0:
            raise ValueError(
                f"failure_injection_rate must be 0.0-1.0, "
                f"got {self.failure_injection_rate}"
            )
        if not 0.0 <= self.timeout_injection_rate <= 1.0:
            raise ValueError(
                f"timeout_injection_rate must be 0.0-1.0, "
                f"got {self.timeout_injection_rate}"
            )
        if self.report_interval_seconds < 1:
            raise ValueError(
                f"report_interval_seconds must be >= 1, "
                f"got {self.report_interval_seconds}"
            )
        # Combined injection rate cannot exceed 100%
        combined_rate = self.failure_injection_rate + self.timeout_injection_rate
        if combined_rate > 1.0:
            raise ValueError(
                f"Combined injection rates must be <= 1.0, "
                f"got {combined_rate} (failure={self.failure_injection_rate}, "
                f"timeout={self.timeout_injection_rate})"
            )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "concurrent_sessions": self.concurrent_sessions,
            "total_petitions": self.total_petitions,
            "petition_batch_size": self.petition_batch_size,
            "archon_response_latency_ms": self.archon_response_latency_ms,
            "failure_injection_rate": self.failure_injection_rate,
            "timeout_injection_rate": self.timeout_injection_rate,
            "report_interval_seconds": self.report_interval_seconds,
            "schema_version": 1,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LoadTestConfig:
        """Create from dictionary."""
        return cls(
            concurrent_sessions=data.get("concurrent_sessions", 100),
            total_petitions=data.get("total_petitions", 1000),
            petition_batch_size=data.get("petition_batch_size", 100),
            archon_response_latency_ms=data.get("archon_response_latency_ms", 100),
            failure_injection_rate=data.get("failure_injection_rate", 0.0),
            timeout_injection_rate=data.get("timeout_injection_rate", 0.0),
            report_interval_seconds=data.get("report_interval_seconds", 5),
        )
