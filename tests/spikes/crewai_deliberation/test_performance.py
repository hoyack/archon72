"""Performance tests for CrewAI Three Fates Deliberation Spike.

Tests timing and resource usage without requiring real LLM calls.
"""

from __future__ import annotations

import gc
import time
import tracemalloc
from statistics import mean

import pytest

from src.spikes.crewai_deliberation.agents import create_mock_three_fates
from src.spikes.crewai_deliberation.tasks import execute_mock_deliberation


# =============================================================================
# Constants (from Story 0.1 Acceptance Criteria)
# =============================================================================

ACCEPTABLE_EXECUTION_TIME_MS = 300_000  # 5 minutes in ms
ACCEPTABLE_MEMORY_MB = 100  # Should be minimal for mock
BENCHMARK_RUNS = 5


class TestPerformanceBenchmarks:
    """Performance benchmarks for deliberation."""

    def test_mock_deliberation_under_5_minutes(self) -> None:
        """AC3: Verify deliberation completes within 5 minutes.

        Mock deliberation should be nearly instant; this validates the framework.
        """
        clotho, lachesis, atropos = create_mock_three_fates()
        petition = """
        This is a sample petition with enough content to simulate
        a realistic deliberation scenario. It contains multiple
        paragraphs and sufficient context for the Three Fates to
        perform their assessment, evaluation, and decision phases.
        """

        start = time.perf_counter()
        result = execute_mock_deliberation(clotho, lachesis, atropos, petition)
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert elapsed_ms < ACCEPTABLE_EXECUTION_TIME_MS, (
            f"Execution took {elapsed_ms:.1f}ms, exceeds {ACCEPTABLE_EXECUTION_TIME_MS}ms"
        )

    def test_multiple_deliberations_consistent_timing(self) -> None:
        """Verify timing consistency across multiple runs."""
        clotho, lachesis, atropos = create_mock_three_fates()
        petition = "Test petition for timing consistency"

        times_ms: list[float] = []

        for _ in range(BENCHMARK_RUNS):
            start = time.perf_counter()
            execute_mock_deliberation(clotho, lachesis, atropos, petition)
            elapsed_ms = (time.perf_counter() - start) * 1000
            times_ms.append(elapsed_ms)

        mean_time = mean(times_ms)
        max_time = max(times_ms)

        # All runs should be fast
        assert max_time < 1000, f"Slowest run: {max_time:.1f}ms"

        # No run should be more than 10x the mean (would indicate issue)
        for t in times_ms:
            assert t < mean_time * 10, f"Outlier timing: {t:.1f}ms vs mean {mean_time:.1f}ms"

    @pytest.mark.slow
    def test_deliberation_memory_usage(self) -> None:
        """Verify memory usage is acceptable."""
        gc.collect()
        tracemalloc.start()
        memory_before = tracemalloc.get_traced_memory()[0] / (1024 * 1024)

        # Run multiple deliberations
        for _ in range(10):
            clotho, lachesis, atropos = create_mock_three_fates()
            execute_mock_deliberation(clotho, lachesis, atropos, "Test")

        gc.collect()
        memory_after = tracemalloc.get_traced_memory()[0] / (1024 * 1024)
        peak_memory = tracemalloc.get_traced_memory()[1] / (1024 * 1024)
        tracemalloc.stop()

        memory_used = memory_after - memory_before

        assert peak_memory < ACCEPTABLE_MEMORY_MB, (
            f"Peak memory {peak_memory:.1f}MB exceeds {ACCEPTABLE_MEMORY_MB}MB"
        )

    def test_sequential_deliberations_no_memory_leak(self) -> None:
        """Verify no memory leak across sequential deliberations."""
        gc.collect()
        tracemalloc.start()
        memory_start = tracemalloc.get_traced_memory()[0]

        # Run many deliberations
        for i in range(20):
            clotho, lachesis, atropos = create_mock_three_fates()
            execute_mock_deliberation(clotho, lachesis, atropos, f"Petition {i}")

        gc.collect()
        memory_end = tracemalloc.get_traced_memory()[0]
        tracemalloc.stop()

        # Memory growth should be minimal
        memory_growth_mb = (memory_end - memory_start) / (1024 * 1024)
        acceptable_growth_mb = 5.0

        assert memory_growth_mb < acceptable_growth_mb, (
            f"Memory grew by {memory_growth_mb:.2f}MB over 20 deliberations"
        )


class TestTimingMetrics:
    """Tests for timing metric collection."""

    def test_result_includes_execution_time(self) -> None:
        """Verify result includes execution timing."""
        clotho, lachesis, atropos = create_mock_three_fates()

        result = execute_mock_deliberation(clotho, lachesis, atropos, "Test")

        assert hasattr(result, "execution_time_ms")
        assert result.execution_time_ms >= 0

    def test_execution_time_accuracy(self) -> None:
        """Verify execution time measurement is reasonable."""
        clotho, lachesis, atropos = create_mock_three_fates()

        # Time the execution ourselves
        start = time.perf_counter()
        result = execute_mock_deliberation(clotho, lachesis, atropos, "Test")
        our_time_ms = (time.perf_counter() - start) * 1000

        # Result's time should be close to our measurement
        # Allow some overhead for result object creation
        assert result.execution_time_ms <= our_time_ms + 10, (
            f"Reported {result.execution_time_ms}ms but measured {our_time_ms}ms"
        )


class TestScalability:
    """Tests for scalability indicators."""

    @pytest.mark.slow
    def test_concurrent_deliberation_scalability(self) -> None:
        """Test behavior under concurrent load (mock)."""
        import asyncio

        async def mock_async_deliberation(petition: str) -> float:
            """Run mock deliberation asynchronously."""
            clotho, lachesis, atropos = create_mock_three_fates()
            start = time.perf_counter()
            execute_mock_deliberation(clotho, lachesis, atropos, petition)
            return (time.perf_counter() - start) * 1000

        async def run_concurrent() -> list[float]:
            """Run multiple deliberations concurrently."""
            tasks = [
                mock_async_deliberation(f"Petition {i}")
                for i in range(10)
            ]
            return await asyncio.gather(*tasks)

        times = asyncio.run(run_concurrent())

        # All should complete quickly
        max_time = max(times)
        assert max_time < 1000, f"Slowest concurrent run: {max_time:.1f}ms"

        # Total time should be roughly the same as sequential
        # (since mock is CPU-bound, not I/O-bound)
        total_time = sum(times)
        avg_time = mean(times)

        # No single run should be dramatically slower
        for t in times:
            assert t < avg_time * 5, f"Outlier: {t:.1f}ms vs avg {avg_time:.1f}ms"
