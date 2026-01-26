"""Load test harness stub implementation (Story 2B.7, NFR-10.5).

This module provides an in-memory stub implementation of the
LoadTestHarnessProtocol for fast unit and integration testing.

Constitutional Constraints:
- NFR-10.1: Verify p95 latency < 5 minutes
- NFR-10.5: Support 100+ concurrent sessions
- CT-11: Report all failures (no silent drops)
"""

from __future__ import annotations

import asyncio
import random
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from src.application.ports.load_test_harness import TestPetition
from src.domain.models.load_test_config import LoadTestConfig
from src.domain.models.load_test_metrics import LoadTestMetrics
from src.domain.models.load_test_report import LoadTestReport


class LoadTestHarnessStub:
    """Stub implementation of LoadTestHarnessProtocol for testing.

    Simulates load test execution with configurable behavior
    for fast unit and integration tests. Does not require
    actual deliberation infrastructure.

    Attributes:
        _run_calls: History of run_load_test calls.
        _metrics: Current metrics state.
        _base_latency_ms: Base latency for simulated deliberations.
        _latency_variance_ms: Variance in latency for realism.
        _forced_latencies: Optional fixed latencies for deterministic testing.

    Example:
        >>> stub = LoadTestHarnessStub(base_latency_ms=100)
        >>> config = LoadTestConfig(total_petitions=100)
        >>> report = await stub.run_load_test(config)
        >>> assert report.total_petitions == 100
    """

    # Standard realms for petition routing
    REALMS = [
        "INFRASTRUCTURE",
        "ECONOMY",
        "CULTURE",
        "DIPLOMACY",
        "DEFENSE",
        "KNOWLEDGE",
        "JUSTICE",
        "HEALTH",
        "ENVIRONMENT",
    ]

    # Possible failure reasons for injection
    FAILURE_REASONS = [
        "ARCHON_ERROR",
        "CONSENSUS_FAILED",
        "NETWORK_ERROR",
        "CONTEXT_BUILD_FAILED",
        "PHASE_EXECUTION_ERROR",
    ]

    def __init__(
        self,
        base_latency_ms: float = 100.0,
        latency_variance_ms: float = 50.0,
    ) -> None:
        """Initialize stub with configurable latency.

        Args:
            base_latency_ms: Base latency for simulated deliberations.
            latency_variance_ms: +/- variance for latency realism.
        """
        self._run_calls: list[dict[str, Any]] = []
        self._metrics = LoadTestMetrics()
        self._base_latency_ms = base_latency_ms
        self._latency_variance_ms = latency_variance_ms
        self._forced_latencies: list[float] | None = None
        self._is_running = False

    async def run_load_test(
        self,
        config: LoadTestConfig,
    ) -> LoadTestReport:
        """Simulate load test execution.

        Processes all petitions according to configuration,
        simulating deliberation latency and injecting failures
        as configured.

        Args:
            config: Load test configuration.

        Returns:
            LoadTestReport with simulated results.
        """
        self._run_calls.append(
            {
                "config": config.to_dict(),
                "timestamp": datetime.now(timezone.utc),
            }
        )

        self._is_running = True
        started_at = datetime.now(timezone.utc)

        # Reset metrics for this run
        self._metrics.reset(pending_petitions=config.total_petitions)

        # Track results
        latencies: list[float] = []
        successful = 0
        failed = 0
        timeouts = 0
        failure_breakdown: dict[str, int] = {}
        rng = random.Random(0)

        # Process all petitions
        for i in range(config.total_petitions):
            # Simulate starting a session
            self._metrics.start_session()

            # Determine outcome based on injection rates
            roll = rng.random()

            if roll < config.failure_injection_rate:
                # Injected failure
                latency = self._generate_latency()
                latencies.append(latency)
                failed += 1
                reason = rng.choice(self.FAILURE_REASONS)
                failure_breakdown[reason] = failure_breakdown.get(reason, 0) + 1
                self._metrics.record_completion(latency, success=False)

            elif roll < config.failure_injection_rate + config.timeout_injection_rate:
                # Injected timeout - latency exceeds 5 minutes
                latency = 300_001.0  # Just over NFR-10.1 threshold
                latencies.append(latency)
                failed += 1
                timeouts += 1
                failure_breakdown["TIMEOUT"] = failure_breakdown.get("TIMEOUT", 0) + 1
                self._metrics.record_completion(latency, success=False, is_timeout=True)

            else:
                # Successful deliberation
                latency = self._generate_latency()
                latencies.append(latency)
                successful += 1
                self._metrics.record_completion(latency, success=True)

            # Update throughput (simple sliding approximation)
            elapsed = (datetime.now(timezone.utc) - started_at).total_seconds()
            if elapsed > 0:
                self._metrics.current_throughput = (
                    self._metrics.total_processed / elapsed
                )

            # Yield periodically to allow concurrent behavior
            if i % 10 == 0:
                await asyncio.sleep(0)

        completed_at = datetime.now(timezone.utc)
        self._is_running = False

        # Calculate final metrics
        duration_s = max(0.001, (completed_at - started_at).total_seconds())
        throughput = config.total_petitions / duration_s

        # Calculate percentiles
        p50 = self._calculate_percentile(latencies, 50)
        p95 = self._calculate_percentile(latencies, 95)
        p99 = self._calculate_percentile(latencies, 99)
        max_lat = max(latencies) if latencies else 0

        return LoadTestReport(
            test_id=uuid4(),
            config=config.to_dict(),
            started_at=started_at,
            completed_at=completed_at,
            total_petitions=config.total_petitions,
            successful_deliberations=successful,
            failed_deliberations=failed,
            timeout_deliberations=timeouts,
            latency_p50_ms=p50,
            latency_p95_ms=p95,
            latency_p99_ms=p99,
            latency_max_ms=max_lat,
            throughput_per_second=throughput,
            resource_metrics={
                "memory_usage_mb": 256.0,
                "cpu_percent": 45.0,
                "db_connections": 10,
            },
            failure_breakdown=failure_breakdown,
            witness_chain_valid_count=successful,  # Assume all successful have valid chains
        )

    def generate_test_petitions(
        self,
        count: int,
    ) -> list[TestPetition]:
        """Generate synthetic test petitions.

        Creates petitions with varied realms and content
        for realistic load testing.

        Args:
            count: Number of petitions to generate.

        Returns:
            List of TestPetition objects.
        """
        petitions = []
        for i in range(count):
            petitions.append(
                TestPetition(
                    petition_id=uuid4(),
                    content=f"Test petition {i}: Request for review of matter #{i} "
                    f"regarding {random.choice(['policy', 'procedure', 'allocation', 'decision'])} "
                    f"in the {random.choice(self.REALMS).lower()} domain.",
                    realm=random.choice(self.REALMS),
                    submitter_id=uuid4(),
                )
            )
        return petitions

    def collect_metrics(self) -> LoadTestMetrics:
        """Return current metrics snapshot.

        Updates timestamp before returning.

        Returns:
            Current LoadTestMetrics state.
        """
        self._metrics.timestamp = datetime.now(timezone.utc)
        return self._metrics

    def _generate_latency(self) -> float:
        """Generate a realistic latency value.

        Uses forced latencies if set, otherwise generates
        random latency around base with configured variance.

        Returns:
            Latency value in milliseconds.
        """
        if self._forced_latencies:
            if self._forced_latencies:
                return self._forced_latencies.pop(0)
        base = self._base_latency_ms
        variance = random.uniform(-self._latency_variance_ms, self._latency_variance_ms)
        return max(1.0, base + variance)

    def _calculate_percentile(self, latencies: list[float], percentile: float) -> float:
        """Calculate percentile from latency list.

        Args:
            latencies: List of latency values.
            percentile: Percentile to calculate (0-100).

        Returns:
            Value at the given percentile.
        """
        if not latencies:
            return 0.0
        sorted_latencies = sorted(latencies)
        index = int(len(sorted_latencies) * (percentile / 100))
        index = min(index, len(sorted_latencies) - 1)
        return sorted_latencies[index]

    # ========================================
    # Test Helpers
    # ========================================

    def set_forced_latencies(self, latencies: list[float]) -> None:
        """Set fixed latencies for deterministic testing.

        Latencies will be consumed in order. Once exhausted,
        random latencies will be generated.

        Args:
            latencies: List of latency values to use.
        """
        self._forced_latencies = latencies.copy()

    def set_base_latency(self, base_ms: float, variance_ms: float = 0.0) -> None:
        """Set base latency parameters.

        Args:
            base_ms: Base latency in milliseconds.
            variance_ms: Variance (+/-) in milliseconds.
        """
        self._base_latency_ms = base_ms
        self._latency_variance_ms = variance_ms

    def get_run_call_count(self) -> int:
        """Get number of run_load_test calls."""
        return len(self._run_calls)

    def get_last_run_config(self) -> dict[str, Any] | None:
        """Get the config from the last run."""
        if not self._run_calls:
            return None
        return self._run_calls[-1]["config"]

    @property
    def is_running(self) -> bool:
        """Check if a load test is currently running."""
        return self._is_running

    def clear(self) -> None:
        """Clear all state for clean testing."""
        self._run_calls.clear()
        self._metrics.reset()
        self._forced_latencies = None
        self._is_running = False
