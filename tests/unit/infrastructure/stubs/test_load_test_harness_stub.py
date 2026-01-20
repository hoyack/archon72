"""Unit tests for LoadTestHarnessStub (Story 2B.7, NFR-10.5).

Tests:
- Stub configuration and behavior
- Test petition generation
- Metrics collection
- Failure and timeout injection
- Test helpers
"""

from __future__ import annotations

import pytest

from src.domain.models.load_test_config import LoadTestConfig
from src.infrastructure.stubs.load_test_harness_stub import LoadTestHarnessStub


class TestLoadTestHarnessStubCreation:
    """Test stub initialization."""

    def test_default_creation(self) -> None:
        """Stub created with default latency."""
        stub = LoadTestHarnessStub()

        assert stub._base_latency_ms == 100.0
        assert stub._latency_variance_ms == 50.0

    def test_custom_latency(self) -> None:
        """Stub can be created with custom latency."""
        stub = LoadTestHarnessStub(base_latency_ms=500.0, latency_variance_ms=100.0)

        assert stub._base_latency_ms == 500.0
        assert stub._latency_variance_ms == 100.0


class TestRunLoadTest:
    """Test run_load_test execution."""

    @pytest.mark.asyncio
    async def test_run_load_test_returns_report(self) -> None:
        """run_load_test returns a complete report."""
        stub = LoadTestHarnessStub()
        config = LoadTestConfig(total_petitions=10, concurrent_sessions=5)

        report = await stub.run_load_test(config)

        assert report.total_petitions == 10
        assert report.test_id is not None

    @pytest.mark.asyncio
    async def test_run_load_test_no_injection_all_success(self) -> None:
        """Without injection, all petitions succeed."""
        stub = LoadTestHarnessStub()
        config = LoadTestConfig(
            total_petitions=50,
            failure_injection_rate=0.0,
            timeout_injection_rate=0.0,
        )

        report = await stub.run_load_test(config)

        assert report.successful_deliberations == 50
        assert report.failed_deliberations == 0
        assert report.timeout_deliberations == 0

    @pytest.mark.asyncio
    async def test_run_load_test_with_failure_injection(self) -> None:
        """Failure injection causes some failures."""
        stub = LoadTestHarnessStub()
        config = LoadTestConfig(
            total_petitions=100,
            failure_injection_rate=0.5,  # 50% failure
            timeout_injection_rate=0.0,
        )

        report = await stub.run_load_test(config)

        # With 50% rate, expect ~50 failures (allow variance)
        assert report.failed_deliberations >= 30
        assert report.failed_deliberations <= 70
        assert report.successful_deliberations == 100 - report.failed_deliberations

    @pytest.mark.asyncio
    async def test_run_load_test_with_timeout_injection(self) -> None:
        """Timeout injection causes some timeouts."""
        stub = LoadTestHarnessStub()
        config = LoadTestConfig(
            total_petitions=100,
            failure_injection_rate=0.0,
            timeout_injection_rate=0.2,  # 20% timeout
        )

        report = await stub.run_load_test(config)

        # With 20% rate, expect ~20 timeouts (allow variance)
        assert report.timeout_deliberations >= 10
        assert report.timeout_deliberations <= 35
        assert "TIMEOUT" in report.failure_breakdown

    @pytest.mark.asyncio
    async def test_run_load_test_tracks_call_history(self) -> None:
        """Stub tracks run_load_test calls."""
        stub = LoadTestHarnessStub()
        config1 = LoadTestConfig(total_petitions=10)
        config2 = LoadTestConfig(total_petitions=20)

        await stub.run_load_test(config1)
        await stub.run_load_test(config2)

        assert stub.get_run_call_count() == 2

    @pytest.mark.asyncio
    async def test_run_load_test_config_in_report(self) -> None:
        """Report contains the config used."""
        stub = LoadTestHarnessStub()
        config = LoadTestConfig(concurrent_sessions=75, total_petitions=100)

        report = await stub.run_load_test(config)

        assert report.config["concurrent_sessions"] == 75
        assert report.config["total_petitions"] == 100


class TestGenerateTestPetitions:
    """Test petition generation."""

    def test_generate_correct_count(self) -> None:
        """Generates requested number of petitions."""
        stub = LoadTestHarnessStub()

        petitions = stub.generate_test_petitions(100)

        assert len(petitions) == 100

    def test_generate_unique_ids(self) -> None:
        """All generated petitions have unique IDs."""
        stub = LoadTestHarnessStub()

        petitions = stub.generate_test_petitions(100)

        ids = [p.petition_id for p in petitions]
        assert len(set(ids)) == 100

    def test_generate_varied_realms(self) -> None:
        """Petitions have varied realms."""
        stub = LoadTestHarnessStub()

        petitions = stub.generate_test_petitions(100)

        realms = {p.realm for p in petitions}
        # Should have multiple realms
        assert len(realms) >= 3

    def test_generate_has_content(self) -> None:
        """All petitions have content."""
        stub = LoadTestHarnessStub()

        petitions = stub.generate_test_petitions(10)

        for petition in petitions:
            assert petition.content
            assert len(petition.content) > 0


class TestCollectMetrics:
    """Test metrics collection."""

    def test_collect_metrics_returns_current_state(self) -> None:
        """collect_metrics returns current metrics."""
        stub = LoadTestHarnessStub()

        metrics = stub.collect_metrics()

        assert metrics.active_sessions == 0
        assert metrics.completed_sessions == 0

    @pytest.mark.asyncio
    async def test_collect_metrics_during_test(self) -> None:
        """Metrics updated during test execution."""
        stub = LoadTestHarnessStub()
        config = LoadTestConfig(total_petitions=100)

        # Run test
        await stub.run_load_test(config)

        # After test, metrics should reflect completion
        metrics = stub.collect_metrics()
        assert metrics.completed_sessions + metrics.failed_sessions == 100


class TestForcedLatencies:
    """Test forced latency behavior."""

    @pytest.mark.asyncio
    async def test_forced_latencies_used_in_order(self) -> None:
        """Forced latencies are consumed in order."""
        stub = LoadTestHarnessStub()
        forced = [100.0, 200.0, 300.0]
        stub.set_forced_latencies(forced)

        config = LoadTestConfig(total_petitions=3)
        report = await stub.run_load_test(config)

        # With forced latencies, p50 should be deterministic
        assert report.latency_p50_ms == 200.0

    @pytest.mark.asyncio
    async def test_forced_latencies_exhausted_falls_back(self) -> None:
        """After exhausting forced latencies, uses random."""
        stub = LoadTestHarnessStub(base_latency_ms=1000.0, latency_variance_ms=0.0)
        stub.set_forced_latencies([100.0, 200.0])  # Only 2 forced

        config = LoadTestConfig(total_petitions=5)
        report = await stub.run_load_test(config)

        # Should have mix of forced (100, 200) and base (1000)
        assert report.latency_max_ms >= 900  # At least some ~1000ms latencies


class TestSetBaseLatency:
    """Test base latency configuration."""

    @pytest.mark.asyncio
    async def test_set_base_latency(self) -> None:
        """set_base_latency updates latency generation."""
        stub = LoadTestHarnessStub()
        stub.set_base_latency(500.0, variance_ms=0.0)  # No variance for determinism

        config = LoadTestConfig(total_petitions=10)
        report = await stub.run_load_test(config)

        # All latencies should be ~500ms
        assert report.latency_p50_ms == 500.0


class TestGetLastRunConfig:
    """Test getting last run config."""

    def test_get_last_run_config_none_initially(self) -> None:
        """No config before any runs."""
        stub = LoadTestHarnessStub()

        assert stub.get_last_run_config() is None

    @pytest.mark.asyncio
    async def test_get_last_run_config_after_run(self) -> None:
        """Returns config from last run."""
        stub = LoadTestHarnessStub()
        config = LoadTestConfig(total_petitions=50, concurrent_sessions=25)

        await stub.run_load_test(config)

        last_config = stub.get_last_run_config()
        assert last_config is not None
        assert last_config["total_petitions"] == 50
        assert last_config["concurrent_sessions"] == 25


class TestIsRunning:
    """Test running state tracking."""

    def test_not_running_initially(self) -> None:
        """Not running before any test."""
        stub = LoadTestHarnessStub()

        assert stub.is_running is False

    @pytest.mark.asyncio
    async def test_not_running_after_completion(self) -> None:
        """Not running after test completes."""
        stub = LoadTestHarnessStub()
        config = LoadTestConfig(total_petitions=10)

        await stub.run_load_test(config)

        assert stub.is_running is False


class TestClear:
    """Test clearing stub state."""

    @pytest.mark.asyncio
    async def test_clear_resets_all_state(self) -> None:
        """clear() resets all tracked state."""
        stub = LoadTestHarnessStub()
        config = LoadTestConfig(total_petitions=10)

        await stub.run_load_test(config)
        stub.set_forced_latencies([100])

        stub.clear()

        assert stub.get_run_call_count() == 0
        assert stub.get_last_run_config() is None
        assert stub._forced_latencies is None
