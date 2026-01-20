"""Unit tests for LoadTestMetrics domain model (Story 2B.7, NFR-10.5).

Tests:
- Metrics initialization
- Session tracking (start, completion)
- Latency percentile calculation
- Progress summary generation
- Serialization
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.domain.models.load_test_metrics import LoadTestMetrics


class TestLoadTestMetricsCreation:
    """Test LoadTestMetrics creation."""

    def test_default_creation(self) -> None:
        """Metrics created with default values."""
        metrics = LoadTestMetrics()

        assert metrics.active_sessions == 0
        assert metrics.completed_sessions == 0
        assert metrics.failed_sessions == 0
        assert metrics.timeout_sessions == 0
        assert metrics.pending_petitions == 0
        assert metrics.current_throughput == 0.0
        assert metrics.memory_usage_mb == 0.0
        assert metrics.db_connection_count == 0
        assert metrics.event_queue_depth == 0
        assert len(metrics.latencies_ms) == 0

    def test_creation_with_pending_petitions(self) -> None:
        """Metrics can be created with initial pending count."""
        metrics = LoadTestMetrics(pending_petitions=100)

        assert metrics.pending_petitions == 100

    def test_timestamp_is_set(self) -> None:
        """Timestamp is set on creation."""
        before = datetime.now(timezone.utc)
        metrics = LoadTestMetrics()
        after = datetime.now(timezone.utc)

        assert before <= metrics.timestamp <= after


class TestSessionTracking:
    """Test session start and completion tracking."""

    def test_start_session_increments_active(self) -> None:
        """Starting a session increments active count."""
        metrics = LoadTestMetrics(pending_petitions=10)

        metrics.start_session()

        assert metrics.active_sessions == 1

    def test_start_session_decrements_pending(self) -> None:
        """Starting a session decrements pending count."""
        metrics = LoadTestMetrics(pending_petitions=10)

        metrics.start_session()

        assert metrics.pending_petitions == 9

    def test_start_session_pending_floor_at_zero(self) -> None:
        """Pending count does not go below zero."""
        metrics = LoadTestMetrics(pending_petitions=0)

        metrics.start_session()

        assert metrics.pending_petitions == 0

    def test_record_completion_success(self) -> None:
        """Successful completion updates correct counters."""
        metrics = LoadTestMetrics()
        metrics.active_sessions = 1

        metrics.record_completion(150.0, success=True)

        assert metrics.completed_sessions == 1
        assert metrics.failed_sessions == 0
        assert metrics.active_sessions == 0
        assert 150.0 in metrics.latencies_ms

    def test_record_completion_failure(self) -> None:
        """Failed completion updates correct counters."""
        metrics = LoadTestMetrics()
        metrics.active_sessions = 1

        metrics.record_completion(200.0, success=False)

        assert metrics.completed_sessions == 0
        assert metrics.failed_sessions == 1
        assert metrics.active_sessions == 0
        assert 200.0 in metrics.latencies_ms

    def test_record_completion_timeout(self) -> None:
        """Timeout completion updates both failed and timeout counters."""
        metrics = LoadTestMetrics()
        metrics.active_sessions = 1

        metrics.record_completion(300_000.0, success=False, is_timeout=True)

        assert metrics.completed_sessions == 0
        assert metrics.failed_sessions == 1
        assert metrics.timeout_sessions == 1
        assert metrics.active_sessions == 0

    def test_record_completion_does_not_go_below_zero(self) -> None:
        """Active count does not go below zero."""
        metrics = LoadTestMetrics()
        metrics.active_sessions = 0

        metrics.record_completion(100.0, success=True)

        assert metrics.active_sessions == 0

    def test_multiple_completions(self) -> None:
        """Multiple completions accumulate correctly."""
        metrics = LoadTestMetrics()
        metrics.active_sessions = 5

        metrics.record_completion(100.0, success=True)
        metrics.record_completion(200.0, success=True)
        metrics.record_completion(300.0, success=False)

        assert metrics.completed_sessions == 2
        assert metrics.failed_sessions == 1
        assert metrics.active_sessions == 2
        assert len(metrics.latencies_ms) == 3


class TestPercentileCalculation:
    """Test latency percentile calculation."""

    def test_percentile_empty_list(self) -> None:
        """Percentile is 0 for empty latencies."""
        metrics = LoadTestMetrics()

        assert metrics.calculate_percentile(50) == 0.0
        assert metrics.calculate_percentile(95) == 0.0

    def test_percentile_single_value(self) -> None:
        """Percentile of single value is that value."""
        metrics = LoadTestMetrics()
        metrics.latencies_ms = [100.0]

        assert metrics.calculate_percentile(50) == 100.0
        assert metrics.calculate_percentile(95) == 100.0

    def test_percentile_median(self) -> None:
        """50th percentile is median."""
        metrics = LoadTestMetrics()
        metrics.latencies_ms = [100, 200, 300, 400, 500]

        assert metrics.calculate_percentile(50) == 300.0

    def test_percentile_95th(self) -> None:
        """95th percentile calculation."""
        metrics = LoadTestMetrics()
        metrics.latencies_ms = list(range(1, 101))  # 1 to 100

        p95 = metrics.calculate_percentile(95)
        assert p95 >= 95  # Should be around 95th element

    def test_percentile_invalid_range(self) -> None:
        """Percentile must be 0-100."""
        metrics = LoadTestMetrics()
        metrics.latencies_ms = [100]

        with pytest.raises(ValueError, match="percentile must be 0-100"):
            metrics.calculate_percentile(-1)

        with pytest.raises(ValueError, match="percentile must be 0-100"):
            metrics.calculate_percentile(101)

    def test_latency_property_shortcuts(self) -> None:
        """Latency properties use calculate_percentile."""
        metrics = LoadTestMetrics()
        metrics.latencies_ms = [100, 200, 300, 400, 500]

        assert metrics.latency_p50_ms == metrics.calculate_percentile(50)
        assert metrics.latency_p95_ms == metrics.calculate_percentile(95)
        assert metrics.latency_p99_ms == metrics.calculate_percentile(99)

    def test_latency_max_ms(self) -> None:
        """latency_max_ms returns maximum latency."""
        metrics = LoadTestMetrics()
        metrics.latencies_ms = [100, 200, 300, 400, 500]

        assert metrics.latency_max_ms == 500.0

    def test_latency_max_empty(self) -> None:
        """latency_max_ms returns 0 for empty list."""
        metrics = LoadTestMetrics()

        assert metrics.latency_max_ms == 0.0


class TestTotalProcessed:
    """Test total_processed property."""

    def test_total_processed(self) -> None:
        """total_processed is sum of completed and failed."""
        metrics = LoadTestMetrics()
        metrics.completed_sessions = 80
        metrics.failed_sessions = 20

        assert metrics.total_processed == 100


class TestProgressSummary:
    """Test progress summary generation."""

    def test_progress_summary_format(self) -> None:
        """Progress summary includes key metrics."""
        metrics = LoadTestMetrics()
        metrics.completed_sessions = 50
        metrics.failed_sessions = 5
        metrics.active_sessions = 10
        metrics.current_throughput = 2.5

        summary = metrics.progress_summary(total_petitions=100)

        assert "55/100" in summary  # Progress
        assert "55.0%" in summary  # Percentage
        assert "Active: 10" in summary
        assert "2.5/s" in summary  # Throughput
        assert "Failed: 5" in summary

    def test_progress_summary_zero_total(self) -> None:
        """Progress summary handles zero total."""
        metrics = LoadTestMetrics()

        summary = metrics.progress_summary(total_petitions=0)

        assert "0.0%" in summary


class TestReset:
    """Test metrics reset."""

    def test_reset_clears_all_counters(self) -> None:
        """Reset clears all tracked state."""
        metrics = LoadTestMetrics()
        metrics.active_sessions = 10
        metrics.completed_sessions = 50
        metrics.failed_sessions = 5
        metrics.timeout_sessions = 2
        metrics.pending_petitions = 30
        metrics.current_throughput = 2.5
        metrics.latencies_ms = [100, 200, 300]

        metrics.reset(pending_petitions=200)

        assert metrics.active_sessions == 0
        assert metrics.completed_sessions == 0
        assert metrics.failed_sessions == 0
        assert metrics.timeout_sessions == 0
        assert metrics.pending_petitions == 200
        assert metrics.current_throughput == 0.0
        assert len(metrics.latencies_ms) == 0


class TestSerialization:
    """Test metrics serialization."""

    def test_to_dict_includes_all_fields(self) -> None:
        """to_dict includes all metrics fields."""
        metrics = LoadTestMetrics(pending_petitions=100)
        metrics.active_sessions = 10
        metrics.completed_sessions = 50
        metrics.latencies_ms = [100, 200, 300]

        result = metrics.to_dict()

        assert "timestamp" in result
        assert result["active_sessions"] == 10
        assert result["completed_sessions"] == 50
        assert result["failed_sessions"] == 0
        assert result["timeout_sessions"] == 0
        assert result["pending_petitions"] == 100
        assert result["total_processed"] == 50
        assert result["latency_count"] == 3
        assert "latency_p50_ms" in result
        assert "latency_p95_ms" in result
        assert "latency_p99_ms" in result
        assert "latency_max_ms" in result
        assert result["schema_version"] == 1
