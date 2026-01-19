#!/usr/bin/env python3
"""CrewAI Three Fates Deliberation Spike Runner.

This script runs the spike experiment to validate CrewAI for petition deliberation.

Usage:
    # With real LLM (requires API key)
    python -m src.spikes.crewai_deliberation.run_spike

    # Mock mode (no API key required)
    python -m src.spikes.crewai_deliberation.run_spike --mock

    # Determinism test (runs 3 identical deliberations)
    python -m src.spikes.crewai_deliberation.run_spike --determinism

    # Performance test (runs 5 deliberations with timing)
    python -m src.spikes.crewai_deliberation.run_spike --performance
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from statistics import mean, stdev
from typing import Any

from structlog import get_logger

from .agents import (
    ATROPOS_PERSONA,
    CLOTHO_PERSONA,
    LACHESIS_PERSONA,
    Disposition,
    create_mock_three_fates,
)
from .crew import DeliberationCrew, DeliberationResult
from .tasks import MockDeliberationResult, execute_mock_deliberation

logger = get_logger()


# =============================================================================
# Sample Petitions for Testing
# =============================================================================

SAMPLE_PETITIONS = {
    "simple": """
I, citizen-47392, hereby petition the Conclave to consider my request.

The matter concerns the allocation of computational resources in Sector 7.
Current distribution appears suboptimal for the stated governance objectives.

I request a review of the allocation algorithm and its parameters.

Respectfully submitted.
""",
    "complex": """
To the Honored Three Fates and the Archon Conclave:

I write as a concerned participant in the Archon 72 governance system. After
careful observation over 47 cycles, I have identified a pattern that warrants
your attention.

**The Issue:**
The current implementation of vote-weight decay appears to violate Article 3,
Section 2 of the Covenant, which states: "No mechanism shall systematically
disadvantage participants based on temporal factors alone."

**Evidence:**
1. Decay rate: 0.1% per cycle compounds to 4.7% annually
2. Long-term participants face 23% weight reduction after 5 years
3. This creates de facto term limits not specified in the Covenant

**Request:**
I petition for an immediate review of the decay mechanism and, if warranted,
suspension pending Conclave deliberation.

This matter appears to require ESCALATION given its constitutional implications.

Signed,
Citizen-Advocate-29471
""",
    "urgent": """
URGENT: Safety Circuit Activation Request

Anomalous behavior detected in Archon-42. Requesting immediate review.

Observed: 3 consecutive votes contrary to stated alignment
Timestamp: 2026-01-19T11:47:32Z
Risk Level: MODERATE

Request emergency deliberation protocol.
""",
}


# =============================================================================
# Spike Metrics
# =============================================================================


@dataclass
class SpikeMetrics:
    """Metrics collected during spike execution."""

    # Timing
    execution_times_ms: list[float] = field(default_factory=list)
    mean_time_ms: float = 0.0
    min_time_ms: float = 0.0
    max_time_ms: float = 0.0
    p95_time_ms: float = 0.0
    stddev_time_ms: float = 0.0

    # Outcomes
    dispositions: list[str] = field(default_factory=list)
    disposition_counts: dict[str, int] = field(default_factory=dict)

    # Determinism
    outputs: list[str] = field(default_factory=list)
    is_deterministic: bool = False
    variance_notes: str = ""

    # Success/Failure
    success_count: int = 0
    failure_count: int = 0
    errors: list[str] = field(default_factory=list)

    def calculate_stats(self) -> None:
        """Calculate timing statistics."""
        if not self.execution_times_ms:
            return

        sorted_times = sorted(self.execution_times_ms)
        n = len(sorted_times)

        self.mean_time_ms = mean(sorted_times)
        self.min_time_ms = min(sorted_times)
        self.max_time_ms = max(sorted_times)
        self.p95_time_ms = sorted_times[min(int(n * 0.95), n - 1)]

        if n > 1:
            self.stddev_time_ms = stdev(sorted_times)

        # Count dispositions
        self.disposition_counts = {}
        for d in self.dispositions:
            self.disposition_counts[d] = self.disposition_counts.get(d, 0) + 1


# =============================================================================
# Spike Execution Functions
# =============================================================================


def run_mock_deliberation(petition_content: str) -> MockDeliberationResult:
    """Run a mock deliberation without LLM calls.

    Args:
        petition_content: The petition text.

    Returns:
        MockDeliberationResult.
    """
    clotho, lachesis, atropos = create_mock_three_fates()
    return execute_mock_deliberation(clotho, lachesis, atropos, petition_content)


def run_real_deliberation(petition_content: str, verbose: bool = True) -> DeliberationResult:
    """Run a real deliberation with LLM calls.

    Args:
        petition_content: The petition text.
        verbose: Whether to enable verbose output.

    Returns:
        DeliberationResult.
    """
    crew = DeliberationCrew(verbose=verbose, temperature=0.0)
    return crew.deliberate(petition_content=petition_content)


async def run_real_deliberation_async(
    petition_content: str, verbose: bool = True
) -> DeliberationResult:
    """Run a real deliberation asynchronously.

    Args:
        petition_content: The petition text.
        verbose: Whether to enable verbose output.

    Returns:
        DeliberationResult.
    """
    crew = DeliberationCrew(verbose=verbose, temperature=0.0)
    return await crew.deliberate_async(petition_content=petition_content)


# =============================================================================
# Test Functions
# =============================================================================


def test_basic_deliberation(mock: bool = True) -> tuple[bool, str]:
    """Test basic deliberation flow.

    Args:
        mock: Whether to use mock mode.

    Returns:
        Tuple of (success, message).
    """
    logger.info("test_basic_deliberation_start", mock=mock)

    petition = SAMPLE_PETITIONS["simple"]

    try:
        if mock:
            result = run_mock_deliberation(petition)
            disposition = result.final_disposition
            time_ms = result.execution_time_ms
        else:
            result = run_real_deliberation(petition, verbose=False)
            disposition = result.disposition
            time_ms = result.total_execution_time_ms

        valid_dispositions = [Disposition.ACKNOWLEDGE, Disposition.REFER, Disposition.ESCALATE]

        if disposition in valid_dispositions:
            logger.info(
                "test_basic_deliberation_pass",
                disposition=disposition,
                time_ms=round(time_ms, 2),
            )
            return True, f"Disposition: {disposition} in {time_ms:.1f}ms"
        else:
            return False, f"Invalid disposition: {disposition}"

    except Exception as e:
        logger.error("test_basic_deliberation_fail", error=str(e))
        return False, f"Error: {e}"


def test_determinism(mock: bool = True, runs: int = 3) -> tuple[bool, SpikeMetrics]:
    """Test determinism of deliberation output.

    Args:
        mock: Whether to use mock mode.
        runs: Number of runs to compare.

    Returns:
        Tuple of (is_deterministic, metrics).
    """
    logger.info("test_determinism_start", mock=mock, runs=runs)

    petition = SAMPLE_PETITIONS["simple"]
    metrics = SpikeMetrics()

    for i in range(runs):
        try:
            if mock:
                result = run_mock_deliberation(petition)
                metrics.outputs.append(result.final_disposition)
                metrics.dispositions.append(result.final_disposition)
                metrics.execution_times_ms.append(result.execution_time_ms)
            else:
                result = run_real_deliberation(petition, verbose=False)
                metrics.outputs.append(result.crew_output_raw)
                metrics.dispositions.append(result.disposition)
                metrics.execution_times_ms.append(result.total_execution_time_ms)

            metrics.success_count += 1
            logger.info(
                "test_determinism_run",
                run=i + 1,
                disposition=metrics.dispositions[-1],
            )

        except Exception as e:
            metrics.failure_count += 1
            metrics.errors.append(str(e))

    # Check determinism
    metrics.calculate_stats()

    if len(set(metrics.dispositions)) == 1:
        metrics.is_deterministic = True
        metrics.variance_notes = "All runs produced identical dispositions"
    else:
        metrics.is_deterministic = False
        metrics.variance_notes = f"Dispositions varied: {metrics.disposition_counts}"

    logger.info(
        "test_determinism_result",
        is_deterministic=metrics.is_deterministic,
        dispositions=metrics.disposition_counts,
    )

    return metrics.is_deterministic, metrics


def test_performance(mock: bool = True, runs: int = 5) -> SpikeMetrics:
    """Test performance with multiple deliberations.

    Args:
        mock: Whether to use mock mode.
        runs: Number of runs for timing.

    Returns:
        SpikeMetrics with timing data.
    """
    logger.info("test_performance_start", mock=mock, runs=runs)

    petition = SAMPLE_PETITIONS["complex"]  # Use complex petition
    metrics = SpikeMetrics()

    for i in range(runs):
        try:
            if mock:
                result = run_mock_deliberation(petition)
                metrics.execution_times_ms.append(result.execution_time_ms)
                metrics.dispositions.append(result.final_disposition)
            else:
                result = run_real_deliberation(petition, verbose=False)
                metrics.execution_times_ms.append(result.total_execution_time_ms)
                metrics.dispositions.append(result.disposition)

            metrics.success_count += 1
            logger.info(
                "test_performance_run",
                run=i + 1,
                time_ms=round(metrics.execution_times_ms[-1], 2),
            )

        except Exception as e:
            metrics.failure_count += 1
            metrics.errors.append(str(e))

    metrics.calculate_stats()

    logger.info(
        "test_performance_result",
        mean_ms=round(metrics.mean_time_ms, 2),
        p95_ms=round(metrics.p95_time_ms, 2),
        max_ms=round(metrics.max_time_ms, 2),
        success_rate=f"{metrics.success_count}/{runs}",
    )

    return metrics


# =============================================================================
# Main Spike Runner
# =============================================================================


def run_full_spike(mock: bool = True) -> dict[str, Any]:
    """Run the complete spike test suite.

    Args:
        mock: Whether to use mock mode.

    Returns:
        Dictionary with all test results.
    """
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "mode": "mock" if mock else "real",
        "tests": {},
    }

    print("\n" + "=" * 60)
    print("CrewAI Three Fates Deliberation Spike")
    print("=" * 60)
    print(f"Mode: {'MOCK (no LLM)' if mock else 'REAL (LLM required)'}")
    print(f"Started: {results['timestamp']}")
    print("=" * 60 + "\n")

    # Test 1: Basic Deliberation
    print("Test 1: Basic Deliberation Flow")
    print("-" * 40)
    success, message = test_basic_deliberation(mock=mock)
    results["tests"]["basic"] = {"success": success, "message": message}
    print(f"Result: {'PASS' if success else 'FAIL'} - {message}\n")

    # Test 2: Determinism
    print("Test 2: Determinism (3 identical runs)")
    print("-" * 40)
    is_deterministic, det_metrics = test_determinism(mock=mock, runs=3)
    results["tests"]["determinism"] = {
        "is_deterministic": is_deterministic,
        "variance_notes": det_metrics.variance_notes,
        "dispositions": det_metrics.disposition_counts,
    }
    print(f"Result: {'PASS' if is_deterministic else 'WARN'} - {det_metrics.variance_notes}\n")

    # Test 3: Performance
    print("Test 3: Performance (5 runs)")
    print("-" * 40)
    perf_metrics = test_performance(mock=mock, runs=5)
    within_threshold = perf_metrics.p95_time_ms < 300000  # 5 minutes in ms

    results["tests"]["performance"] = {
        "mean_ms": round(perf_metrics.mean_time_ms, 2),
        "p95_ms": round(perf_metrics.p95_time_ms, 2),
        "max_ms": round(perf_metrics.max_time_ms, 2),
        "within_5min_threshold": within_threshold,
        "success_count": perf_metrics.success_count,
        "failure_count": perf_metrics.failure_count,
    }
    print(f"Mean: {perf_metrics.mean_time_ms:.2f}ms")
    print(f"P95: {perf_metrics.p95_time_ms:.2f}ms")
    print(f"Max: {perf_metrics.max_time_ms:.2f}ms")
    print(f"Result: {'PASS' if within_threshold else 'FAIL'} - P95 {'<' if within_threshold else '>'} 5 minutes\n")

    # Summary
    print("=" * 60)
    print("SPIKE SUMMARY")
    print("=" * 60)

    all_pass = (
        results["tests"]["basic"]["success"]
        and results["tests"]["performance"]["within_5min_threshold"]
    )
    determinism_ok = results["tests"]["determinism"]["is_deterministic"]

    results["recommendation"] = "GO" if all_pass else "NO-GO"
    results["determinism_status"] = "PASS" if determinism_ok else "ACCEPTABLE (variance noted)"

    print(f"Basic Flow: {'PASS' if results['tests']['basic']['success'] else 'FAIL'}")
    print(f"Determinism: {results['determinism_status']}")
    print(f"Performance: {'PASS' if within_threshold else 'FAIL'}")
    print("-" * 40)
    print(f"RECOMMENDATION: {results['recommendation']}")

    if mock:
        print("\nNote: Tests ran in MOCK mode. Run with --no-mock for real LLM testing.")

    return results


# =============================================================================
# CLI Entry Point
# =============================================================================


def main() -> int:
    """Main entry point for the spike runner."""
    parser = argparse.ArgumentParser(
        description="CrewAI Three Fates Deliberation Spike",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Run in mock mode (no API key required)
    python -m src.spikes.crewai_deliberation.run_spike

    # Run with real LLM
    python -m src.spikes.crewai_deliberation.run_spike --no-mock

    # Test determinism only
    python -m src.spikes.crewai_deliberation.run_spike --determinism

    # Test performance only
    python -m src.spikes.crewai_deliberation.run_spike --performance
        """,
    )

    parser.add_argument(
        "--mock",
        action="store_true",
        default=True,
        help="Run in mock mode (no LLM calls, default)",
    )
    parser.add_argument(
        "--no-mock",
        action="store_true",
        help="Run with real LLM (requires API key)",
    )
    parser.add_argument(
        "--determinism",
        action="store_true",
        help="Run determinism test only",
    )
    parser.add_argument(
        "--performance",
        action="store_true",
        help="Run performance test only",
    )
    parser.add_argument(
        "--basic",
        action="store_true",
        help="Run basic deliberation test only",
    )

    args = parser.parse_args()

    mock = not args.no_mock

    # Check for API key if not mock
    if not mock and not os.environ.get("OPENAI_API_KEY"):
        print("ERROR: OPENAI_API_KEY not set. Use --mock or set the environment variable.")
        return 1

    # Run specific tests or full spike
    if args.determinism:
        is_det, metrics = test_determinism(mock=mock)
        print(f"\nDeterminism: {'PASS' if is_det else 'FAIL'}")
        print(f"Notes: {metrics.variance_notes}")
        return 0 if is_det else 1

    if args.performance:
        metrics = test_performance(mock=mock)
        within = metrics.p95_time_ms < 300000
        print(f"\nPerformance: {'PASS' if within else 'FAIL'}")
        print(f"P95: {metrics.p95_time_ms:.2f}ms")
        return 0 if within else 1

    if args.basic:
        success, msg = test_basic_deliberation(mock=mock)
        print(f"\nBasic: {'PASS' if success else 'FAIL'} - {msg}")
        return 0 if success else 1

    # Run full spike
    results = run_full_spike(mock=mock)
    return 0 if results["recommendation"] == "GO" else 1


if __name__ == "__main__":
    sys.exit(main())
