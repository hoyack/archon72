"""Unit tests for LoadTestReport domain model (Story 2B.7, NFR-10.5).

Tests:
- Report creation with all fields
- Computed properties (duration, success_rate, NFR pass/fail)
- Summary generation
- Serialization to dict
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from src.domain.models.load_test_report import (
    NFR_10_1_THRESHOLD_MS,
    LoadTestReport,
)


def make_report(
    total_petitions: int = 100,
    successful: int = 90,
    failed: int = 7,
    timeouts: int = 3,
    latency_p95_ms: float = 5000.0,
    concurrent_sessions: int = 100,
    started_at: datetime | None = None,
    completed_at: datetime | None = None,
    witness_valid: int | None = None,
) -> LoadTestReport:
    """Create a test report with defaults."""
    now = datetime.now(timezone.utc)
    return LoadTestReport(
        test_id=uuid4(),
        config={"concurrent_sessions": concurrent_sessions, "total_petitions": total_petitions},
        started_at=started_at or now - timedelta(seconds=60),
        completed_at=completed_at or now,
        total_petitions=total_petitions,
        successful_deliberations=successful,
        failed_deliberations=failed,
        timeout_deliberations=timeouts,
        latency_p50_ms=2000.0,
        latency_p95_ms=latency_p95_ms,
        latency_p99_ms=8000.0,
        latency_max_ms=15000.0,
        throughput_per_second=1.5,
        resource_metrics={"memory_usage_mb": 256.0, "cpu_percent": 45.0},
        failure_breakdown={"ARCHON_ERROR": 5, "TIMEOUT": 3, "NETWORK_ERROR": 2},
        witness_chain_valid_count=witness_valid if witness_valid is not None else successful,
    )


class TestLoadTestReportCreation:
    """Test LoadTestReport creation."""

    def test_report_creation_with_all_fields(self) -> None:
        """Report can be created with all required fields."""
        report = make_report()

        assert report.total_petitions == 100
        assert report.successful_deliberations == 90
        assert report.failed_deliberations == 7
        assert report.timeout_deliberations == 3

    def test_report_has_test_id(self) -> None:
        """Report has unique test ID."""
        report1 = make_report()
        report2 = make_report()

        assert report1.test_id is not None
        assert report2.test_id is not None
        assert report1.test_id != report2.test_id


class TestLoadTestReportComputedProperties:
    """Test LoadTestReport computed properties."""

    def test_duration_seconds(self) -> None:
        """Duration calculated from start/end times."""
        now = datetime.now(timezone.utc)
        start = now - timedelta(seconds=120)

        report = make_report(started_at=start, completed_at=now)

        assert report.duration_seconds == pytest.approx(120.0, abs=1.0)

    def test_success_rate_percentage(self) -> None:
        """Success rate is percentage of successful deliberations."""
        report = make_report(total_petitions=100, successful=95)

        assert report.success_rate == 95.0

    def test_success_rate_zero_petitions(self) -> None:
        """Success rate is 0 when no petitions."""
        report = make_report(total_petitions=0, successful=0, failed=0, timeouts=0)

        assert report.success_rate == 0.0

    def test_all_witness_chains_valid_when_count_matches(self) -> None:
        """all_witness_chains_valid is True when counts match."""
        report = make_report(successful=90, witness_valid=90)

        assert report.all_witness_chains_valid is True

    def test_all_witness_chains_valid_false_when_mismatch(self) -> None:
        """all_witness_chains_valid is False when counts differ."""
        report = make_report(successful=90, witness_valid=85)

        assert report.all_witness_chains_valid is False


class TestNFRCompliance:
    """Test NFR compliance checking."""

    def test_nfr_10_1_pass_under_threshold(self) -> None:
        """NFR-10.1 passes when p95 < 5 minutes."""
        report = make_report(latency_p95_ms=299_000)  # Just under 5 min

        assert report.nfr_10_1_pass is True

    def test_nfr_10_1_fail_over_threshold(self) -> None:
        """NFR-10.1 fails when p95 >= 5 minutes."""
        report = make_report(latency_p95_ms=300_001)  # Just over 5 min

        assert report.nfr_10_1_pass is False

    def test_nfr_10_1_fail_at_threshold(self) -> None:
        """NFR-10.1 fails when p95 == 5 minutes."""
        report = make_report(latency_p95_ms=NFR_10_1_THRESHOLD_MS)

        assert report.nfr_10_1_pass is False

    def test_nfr_10_5_pass_with_100_sessions(self) -> None:
        """NFR-10.5 passes when 100+ concurrent sessions tested."""
        report = make_report(concurrent_sessions=100)

        assert report.nfr_10_5_pass is True

    def test_nfr_10_5_fail_under_100_sessions(self) -> None:
        """NFR-10.5 fails when < 100 concurrent sessions tested."""
        report = make_report(concurrent_sessions=50)

        assert report.nfr_10_5_pass is False


class TestLoadTestReportSummary:
    """Test LoadTestReport summary generation."""

    def test_summary_includes_key_metrics(self) -> None:
        """Summary includes all key metrics."""
        report = make_report(
            total_petitions=1000,
            successful=950,
            failed=30,
            timeouts=20,
            latency_p95_ms=5000,
        )

        summary = report.summary()

        assert "1000" in summary  # Total petitions
        assert "950" in summary  # Successful
        assert "30" in summary  # Failed
        assert "20" in summary  # Timeout
        assert "5000" in summary  # p95 latency
        assert "PASS" in summary  # NFR-10.1 status (p95 < 5 min)

    def test_summary_shows_fail_when_nfr_violated(self) -> None:
        """Summary shows FAIL when NFR-10.1 violated."""
        report = make_report(latency_p95_ms=400_000)  # > 5 min

        summary = report.summary()

        assert "FAIL" in summary

    def test_summary_includes_failure_breakdown(self) -> None:
        """Summary includes failure breakdown when present."""
        report = make_report()

        summary = report.summary()

        assert "ARCHON_ERROR" in summary
        assert "TIMEOUT" in summary


class TestLoadTestReportSerialization:
    """Test LoadTestReport serialization."""

    def test_to_dict_includes_all_fields(self) -> None:
        """to_dict includes all report fields."""
        report = make_report()

        result = report.to_dict()

        assert "test_id" in result
        assert "config" in result
        assert "started_at" in result
        assert "completed_at" in result
        assert "duration_seconds" in result
        assert "total_petitions" in result
        assert "successful_deliberations" in result
        assert "failed_deliberations" in result
        assert "timeout_deliberations" in result
        assert "success_rate" in result
        assert "latency_p50_ms" in result
        assert "latency_p95_ms" in result
        assert "latency_p99_ms" in result
        assert "latency_max_ms" in result
        assert "throughput_per_second" in result
        assert "resource_metrics" in result
        assert "failure_breakdown" in result
        assert "witness_chain_valid_count" in result
        assert "nfr_10_1_pass" in result
        assert "nfr_10_5_pass" in result
        assert "all_witness_chains_valid" in result
        assert result["schema_version"] == 1

    def test_to_dict_test_id_is_string(self) -> None:
        """Test ID is serialized as string."""
        report = make_report()

        result = report.to_dict()

        assert isinstance(result["test_id"], str)

    def test_to_dict_timestamps_are_iso_format(self) -> None:
        """Timestamps are serialized in ISO format."""
        report = make_report()

        result = report.to_dict()

        assert "T" in result["started_at"]  # ISO format includes T
        assert "T" in result["completed_at"]


class TestNFRThreshold:
    """Test NFR threshold constant."""

    def test_nfr_10_1_threshold_is_5_minutes(self) -> None:
        """NFR_10_1_THRESHOLD_MS is 5 minutes in milliseconds."""
        assert NFR_10_1_THRESHOLD_MS == 300_000  # 5 * 60 * 1000
