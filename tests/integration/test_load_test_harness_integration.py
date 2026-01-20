"""Integration tests for Load Test Harness (Story 2B.7, NFR-10.5).

Tests:
- 100+ concurrent deliberations (NFR-10.5)
- p95 latency verification (NFR-10.1)
- Failure injection and recovery
- Timeout injection with auto-ESCALATE behavior
- No petition lost or duplicated under load
- Witness chain validity under load
- Report accuracy and completeness

Constitutional Constraints:
- NFR-9.4: Load test harness simulates 10k petition flood
- NFR-10.1: Deliberation end-to-end latency p95 < 5 minutes
- NFR-10.5: Concurrent deliberations - 100+ simultaneous sessions
- CT-11: Silent failure destroys legitimacy - report all failures
- CT-14: Every petition terminates in visible, witnessed fate
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.domain.models.load_test_config import LoadTestConfig
from src.domain.models.load_test_report import NFR_10_1_THRESHOLD_MS
from src.infrastructure.stubs.load_test_harness_stub import LoadTestHarnessStub


class TestNFR105ConcurrentSessions:
    """Test 100+ concurrent deliberations (NFR-10.5)."""

    @pytest.mark.asyncio
    async def test_100_concurrent_sessions_complete(self) -> None:
        """100 concurrent sessions all complete successfully (NFR-10.5).

        AC-4: 100 deliberations execute simultaneously and all complete.
        """
        harness = LoadTestHarnessStub(base_latency_ms=50.0, latency_variance_ms=10.0)
        config = LoadTestConfig(
            concurrent_sessions=100,
            total_petitions=100,
            failure_injection_rate=0.0,
            timeout_injection_rate=0.0,
        )

        report = await harness.run_load_test(config)

        assert report.total_petitions == 100
        assert report.successful_deliberations == 100
        assert report.failed_deliberations == 0
        assert report.nfr_10_5_pass is True

    @pytest.mark.asyncio
    async def test_200_concurrent_sessions_complete(self) -> None:
        """200 concurrent sessions demonstrates scalability beyond minimum.

        Tests that the system can handle significantly more than the
        required 100 concurrent sessions.
        """
        harness = LoadTestHarnessStub(base_latency_ms=10.0, latency_variance_ms=5.0)
        config = LoadTestConfig(
            concurrent_sessions=200,
            total_petitions=200,
            failure_injection_rate=0.0,
            timeout_injection_rate=0.0,
        )

        report = await harness.run_load_test(config)

        assert report.successful_deliberations == 200
        assert report.nfr_10_5_pass is True

    @pytest.mark.asyncio
    async def test_concurrent_sessions_config_in_report(self) -> None:
        """Report accurately reflects concurrent session count tested."""
        harness = LoadTestHarnessStub()
        config = LoadTestConfig(concurrent_sessions=150, total_petitions=150)

        report = await harness.run_load_test(config)

        assert report.config["concurrent_sessions"] == 150


class TestNFR101LatencySLA:
    """Test p95 latency < 5 minutes (NFR-10.1)."""

    @pytest.mark.asyncio
    async def test_p95_latency_under_threshold_passes(self) -> None:
        """p95 latency under 5 minutes passes NFR-10.1.

        AC-5: Report indicates PASS when p95 < 5 minutes.
        """
        harness = LoadTestHarnessStub(base_latency_ms=1000.0, latency_variance_ms=500.0)
        config = LoadTestConfig(
            concurrent_sessions=100,
            total_petitions=1000,
            failure_injection_rate=0.0,
        )

        report = await harness.run_load_test(config)

        assert report.latency_p95_ms < NFR_10_1_THRESHOLD_MS
        assert report.nfr_10_1_pass is True

    @pytest.mark.asyncio
    async def test_latency_distribution_captured(self) -> None:
        """Report captures full latency distribution.

        AC-5: Latency distribution captured (p50, p95, p99, max).
        """
        harness = LoadTestHarnessStub()
        # Set forced latencies for deterministic testing
        latencies = [100 * i for i in range(1, 101)]  # 100 to 10000
        harness.set_forced_latencies(latencies)

        config = LoadTestConfig(
            concurrent_sessions=10,
            total_petitions=100,
        )

        report = await harness.run_load_test(config)

        # Verify distribution is captured
        assert report.latency_p50_ms > 0
        assert report.latency_p95_ms > report.latency_p50_ms
        assert report.latency_p99_ms >= report.latency_p95_ms
        assert report.latency_max_ms >= report.latency_p99_ms


class TestFailureInjection:
    """Test failure injection for resilience testing (AC-6)."""

    @pytest.mark.asyncio
    async def test_failure_injection_creates_failures(self) -> None:
        """Failure injection creates approximately expected failure rate.

        AC-6: With failure_injection_rate=0.05, ~5% deliberations fail.
        """
        harness = LoadTestHarnessStub()
        config = LoadTestConfig(
            concurrent_sessions=50,
            total_petitions=1000,  # Large sample for statistical accuracy
            failure_injection_rate=0.1,  # 10% failure
            timeout_injection_rate=0.0,
        )

        report = await harness.run_load_test(config)

        # Allow +/- 5% variance
        expected = 100  # 10% of 1000
        assert report.failed_deliberations >= expected - 50
        assert report.failed_deliberations <= expected + 50

    @pytest.mark.asyncio
    async def test_failure_reasons_recorded(self) -> None:
        """Failed sessions have reasons recorded in breakdown.

        AC-6: Failed session IDs and reasons are recorded.
        """
        harness = LoadTestHarnessStub()
        config = LoadTestConfig(
            concurrent_sessions=50,
            total_petitions=100,
            failure_injection_rate=0.2,  # 20% to ensure some failures
        )

        report = await harness.run_load_test(config)

        # Should have some failures
        assert report.failed_deliberations > 0
        # Should have reasons
        assert len(report.failure_breakdown) > 0
        # Total in breakdown should match failed count
        breakdown_total = sum(report.failure_breakdown.values())
        assert breakdown_total == report.failed_deliberations

    @pytest.mark.asyncio
    async def test_unfailed_deliberations_succeed(self) -> None:
        """Non-injected deliberations complete successfully.

        AC-6: Unfailed deliberations complete successfully.
        """
        harness = LoadTestHarnessStub()
        config = LoadTestConfig(
            concurrent_sessions=50,
            total_petitions=100,
            failure_injection_rate=0.1,
        )

        report = await harness.run_load_test(config)

        # Successful + failed should equal total
        total = report.successful_deliberations + report.failed_deliberations
        assert total == 100


class TestTimeoutInjection:
    """Test timeout injection (AC-7)."""

    @pytest.mark.asyncio
    async def test_timeout_injection_creates_timeouts(self) -> None:
        """Timeout injection creates approximately expected timeout rate.

        AC-7: With timeout_injection_rate=0.02, ~2% deliberations timeout.
        """
        harness = LoadTestHarnessStub()
        config = LoadTestConfig(
            concurrent_sessions=50,
            total_petitions=500,
            failure_injection_rate=0.0,
            timeout_injection_rate=0.1,  # 10% timeout
        )

        report = await harness.run_load_test(config)

        # Allow variance
        expected = 50  # 10% of 500
        assert report.timeout_deliberations >= expected - 25
        assert report.timeout_deliberations <= expected + 25

    @pytest.mark.asyncio
    async def test_timeout_recorded_in_failure_breakdown(self) -> None:
        """Timeouts recorded as TIMEOUT in failure breakdown.

        AC-7: Timeout session IDs are recorded.
        """
        harness = LoadTestHarnessStub()
        config = LoadTestConfig(
            concurrent_sessions=50,
            total_petitions=100,
            timeout_injection_rate=0.2,
        )

        report = await harness.run_load_test(config)

        assert "TIMEOUT" in report.failure_breakdown
        assert report.failure_breakdown["TIMEOUT"] == report.timeout_deliberations


class TestNoPetitionLoss:
    """Test no petition lost or duplicated (CT-14)."""

    @pytest.mark.asyncio
    async def test_no_petition_lost(self) -> None:
        """All petitions accounted for (success + failure = total).

        AC-4: No petition is lost or double-fated.
        """
        harness = LoadTestHarnessStub()
        config = LoadTestConfig(
            concurrent_sessions=100,
            total_petitions=500,
            failure_injection_rate=0.1,
            timeout_injection_rate=0.05,
        )

        report = await harness.run_load_test(config)

        # Every petition must be accounted for
        accounted = report.successful_deliberations + report.failed_deliberations
        assert accounted == 500

    @pytest.mark.asyncio
    async def test_no_duplicate_processing(self) -> None:
        """No petition processed more than once.

        The total processed should exactly equal total_petitions.
        """
        harness = LoadTestHarnessStub()
        config = LoadTestConfig(
            concurrent_sessions=100,
            total_petitions=1000,
        )

        report = await harness.run_load_test(config)

        # Total processed must exactly match
        assert report.total_petitions == 1000


class TestWitnessChainValidity:
    """Test witness chain validity under load."""

    @pytest.mark.asyncio
    async def test_witness_chains_valid_for_successful(self) -> None:
        """All successful deliberations have valid witness chains.

        AC-12: Witness chains remain valid under load.
        """
        harness = LoadTestHarnessStub()
        config = LoadTestConfig(
            concurrent_sessions=100,
            total_petitions=200,
            failure_injection_rate=0.0,
        )

        report = await harness.run_load_test(config)

        # All successful should have valid witness chains
        assert report.witness_chain_valid_count == report.successful_deliberations
        assert report.all_witness_chains_valid is True


class TestMetricsCollection:
    """Test metrics collection during load test (AC-8)."""

    @pytest.mark.asyncio
    async def test_metrics_collection_during_test(self) -> None:
        """Metrics can be collected during test execution.

        AC-8: Metrics can be polled during test execution.
        """
        harness = LoadTestHarnessStub()
        config = LoadTestConfig(
            concurrent_sessions=50,
            total_petitions=100,
        )

        # Collect metrics before
        before_metrics = harness.collect_metrics()
        assert before_metrics.total_processed == 0

        # Run test
        await harness.run_load_test(config)

        # Collect metrics after
        after_metrics = harness.collect_metrics()
        assert after_metrics.total_processed == 100


class TestReportAccuracy:
    """Test report accuracy and completeness (AC-3)."""

    @pytest.mark.asyncio
    async def test_report_has_all_required_fields(self) -> None:
        """Report contains all required fields.

        AC-3: LoadTestReport contains all specified fields.
        """
        harness = LoadTestHarnessStub()
        config = LoadTestConfig(total_petitions=50)

        report = await harness.run_load_test(config)

        # Required fields from AC-3
        assert report.test_id is not None
        assert report.config is not None
        assert report.started_at is not None
        assert report.completed_at is not None
        assert report.total_petitions == 50
        assert report.successful_deliberations >= 0
        assert report.failed_deliberations >= 0
        assert report.timeout_deliberations >= 0
        assert report.latency_p50_ms >= 0
        assert report.latency_p95_ms >= 0
        assert report.latency_p99_ms >= 0
        assert report.latency_max_ms >= 0
        assert report.throughput_per_second >= 0
        assert report.resource_metrics is not None
        assert report.failure_breakdown is not None
        assert report.witness_chain_valid_count >= 0

    @pytest.mark.asyncio
    async def test_report_timestamps_accurate(self) -> None:
        """Report timestamps reflect actual test timing."""
        before = datetime.now(timezone.utc)

        harness = LoadTestHarnessStub()
        config = LoadTestConfig(total_petitions=50)
        report = await harness.run_load_test(config)

        after = datetime.now(timezone.utc)

        assert before <= report.started_at <= after
        assert before <= report.completed_at <= after
        assert report.started_at <= report.completed_at

    @pytest.mark.asyncio
    async def test_report_summary_generation(self) -> None:
        """Report can generate human-readable summary.

        AC-3: Report can generate a summary string.
        """
        harness = LoadTestHarnessStub()
        config = LoadTestConfig(total_petitions=100)

        report = await harness.run_load_test(config)
        summary = report.summary()

        assert len(summary) > 0
        assert "100" in summary  # Total petitions
        assert "NFR-10.1" in summary  # NFR reference

    @pytest.mark.asyncio
    async def test_report_serialization(self) -> None:
        """Report can be serialized to dict.

        AC-3: Report can export to JSON/dict.
        """
        harness = LoadTestHarnessStub()
        config = LoadTestConfig(total_petitions=100)

        report = await harness.run_load_test(config)
        data = report.to_dict()

        assert isinstance(data, dict)
        assert "test_id" in data
        assert "config" in data
        assert "total_petitions" in data
        assert data["total_petitions"] == 100


class TestPetitionGeneration:
    """Test petition generation functionality."""

    def test_generate_petitions_for_load_test(self) -> None:
        """Harness can generate test petitions.

        AC-1: generate_test_petitions returns list of TestPetition.
        """
        harness = LoadTestHarnessStub()

        petitions = harness.generate_test_petitions(100)

        assert len(petitions) == 100
        for petition in petitions:
            assert petition.petition_id is not None
            assert petition.content is not None
            assert petition.realm is not None


class TestLargeScaleLoad:
    """Test large-scale load scenarios approaching NFR-9.4."""

    @pytest.mark.asyncio
    async def test_1000_petitions_complete(self) -> None:
        """1000 petitions complete successfully.

        Progress toward NFR-9.4 (10k petition flood).
        """
        harness = LoadTestHarnessStub(base_latency_ms=10.0, latency_variance_ms=5.0)
        config = LoadTestConfig(
            concurrent_sessions=100,
            total_petitions=1000,
            failure_injection_rate=0.02,  # 2% failures for realism
        )

        report = await harness.run_load_test(config)

        # Most should succeed
        assert report.successful_deliberations >= 950
        # Total accounted for
        total = report.successful_deliberations + report.failed_deliberations
        assert total == 1000
        # p95 should still be reasonable
        assert report.latency_p95_ms < 100  # 100ms for fast stub


class TestThroughputMeasurement:
    """Test throughput measurement."""

    @pytest.mark.asyncio
    async def test_throughput_calculated(self) -> None:
        """Report includes throughput measurement."""
        harness = LoadTestHarnessStub()
        config = LoadTestConfig(total_petitions=100)

        report = await harness.run_load_test(config)

        # Throughput should be positive
        assert report.throughput_per_second > 0

    @pytest.mark.asyncio
    async def test_throughput_reflects_test_speed(self) -> None:
        """Throughput reflects actual test completion speed."""
        harness = LoadTestHarnessStub(base_latency_ms=1.0, latency_variance_ms=0.0)
        config = LoadTestConfig(total_petitions=100)

        report = await harness.run_load_test(config)

        # With very fast latency, throughput should be high
        # Exact value depends on stub implementation
        assert report.throughput_per_second > 1.0
