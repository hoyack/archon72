"""Tests for TaskTimeoutPort interface and configuration.

Story: consent-gov-2.5: Task TTL & Auto-Transitions

Tests the timeout port interface and configuration dataclasses.
"""

from datetime import timedelta

import pytest

from src.application.ports.governance.task_timeout_port import (
    TaskTimeoutConfig,
    TimeoutProcessingResult,
)


class TestTaskTimeoutConfig:
    """Tests for TaskTimeoutConfig dataclass."""

    def test_default_values(self):
        """Config has correct default values per story requirements."""
        config = TaskTimeoutConfig()

        # Per NFR-CONSENT-01: 72h activation TTL
        assert config.activation_ttl == timedelta(hours=72)
        # Per FR9: 48h acceptance inactivity
        assert config.acceptance_inactivity == timedelta(hours=48)
        # Per FR10: 7d reporting timeout
        assert config.reporting_timeout == timedelta(days=7)
        # Per AC8: 5 min processor interval
        assert config.processor_interval == timedelta(minutes=5)

    def test_custom_activation_ttl(self):
        """Config accepts custom activation TTL."""
        config = TaskTimeoutConfig(activation_ttl=timedelta(hours=24))
        assert config.activation_ttl == timedelta(hours=24)

    def test_custom_acceptance_inactivity(self):
        """Config accepts custom acceptance inactivity."""
        config = TaskTimeoutConfig(acceptance_inactivity=timedelta(hours=12))
        assert config.acceptance_inactivity == timedelta(hours=12)

    def test_custom_reporting_timeout(self):
        """Config accepts custom reporting timeout."""
        config = TaskTimeoutConfig(reporting_timeout=timedelta(days=14))
        assert config.reporting_timeout == timedelta(days=14)

    def test_custom_processor_interval(self):
        """Config accepts custom processor interval."""
        config = TaskTimeoutConfig(processor_interval=timedelta(seconds=30))
        assert config.processor_interval == timedelta(seconds=30)

    def test_all_custom_values(self):
        """Config accepts all custom values together."""
        config = TaskTimeoutConfig(
            activation_ttl=timedelta(hours=24),
            acceptance_inactivity=timedelta(hours=12),
            reporting_timeout=timedelta(days=3),
            processor_interval=timedelta(minutes=1),
        )
        assert config.activation_ttl == timedelta(hours=24)
        assert config.acceptance_inactivity == timedelta(hours=12)
        assert config.reporting_timeout == timedelta(days=3)
        assert config.processor_interval == timedelta(minutes=1)

    def test_frozen_dataclass(self):
        """Config is immutable (frozen)."""
        config = TaskTimeoutConfig()
        with pytest.raises(AttributeError):
            config.activation_ttl = timedelta(hours=24)  # type: ignore

    def test_validation_activation_ttl_positive(self):
        """Activation TTL must be positive."""
        with pytest.raises(ValueError, match="activation_ttl must be positive"):
            TaskTimeoutConfig(activation_ttl=timedelta(0))

        with pytest.raises(ValueError, match="activation_ttl must be positive"):
            TaskTimeoutConfig(activation_ttl=timedelta(seconds=-1))

    def test_validation_acceptance_inactivity_positive(self):
        """Acceptance inactivity must be positive."""
        with pytest.raises(ValueError, match="acceptance_inactivity must be positive"):
            TaskTimeoutConfig(acceptance_inactivity=timedelta(0))

    def test_validation_reporting_timeout_positive(self):
        """Reporting timeout must be positive."""
        with pytest.raises(ValueError, match="reporting_timeout must be positive"):
            TaskTimeoutConfig(reporting_timeout=timedelta(0))

    def test_validation_processor_interval_positive(self):
        """Processor interval must be positive."""
        with pytest.raises(ValueError, match="processor_interval must be positive"):
            TaskTimeoutConfig(processor_interval=timedelta(0))


class TestTimeoutProcessingResult:
    """Tests for TimeoutProcessingResult dataclass."""

    def test_empty_result(self):
        """Empty result has empty lists and zero count."""
        result = TimeoutProcessingResult()

        assert result.declined == []
        assert result.started == []
        assert result.quarantined == []
        assert result.errors == []
        assert result.total_processed == 0
        assert result.has_errors is False

    def test_with_declined_tasks(self):
        """Result with declined tasks."""
        from uuid import uuid4

        task_ids = [uuid4(), uuid4()]
        result = TimeoutProcessingResult(declined=task_ids)

        assert result.declined == task_ids
        assert result.total_processed == 2

    def test_with_started_tasks(self):
        """Result with started tasks."""
        from uuid import uuid4

        task_ids = [uuid4()]
        result = TimeoutProcessingResult(started=task_ids)

        assert result.started == task_ids
        assert result.total_processed == 1

    def test_with_quarantined_tasks(self):
        """Result with quarantined tasks."""
        from uuid import uuid4

        task_ids = [uuid4(), uuid4(), uuid4()]
        result = TimeoutProcessingResult(quarantined=task_ids)

        assert result.quarantined == task_ids
        assert result.total_processed == 3

    def test_total_processed_sums_all(self):
        """Total processed sums all categories."""
        from uuid import uuid4

        result = TimeoutProcessingResult(
            declined=[uuid4(), uuid4()],  # 2
            started=[uuid4()],  # 1
            quarantined=[uuid4(), uuid4(), uuid4()],  # 3
        )

        assert result.total_processed == 6

    def test_has_errors_true(self):
        """has_errors is True when errors list is non-empty."""
        from uuid import uuid4

        result = TimeoutProcessingResult(errors=[(uuid4(), "Error message")])

        assert result.has_errors is True

    def test_has_errors_false(self):
        """has_errors is False when errors list is empty."""
        from uuid import uuid4

        result = TimeoutProcessingResult(
            declined=[uuid4()],
            errors=[],
        )

        assert result.has_errors is False

    def test_frozen_dataclass(self):
        """Result is immutable (frozen)."""
        result = TimeoutProcessingResult()
        with pytest.raises(AttributeError):
            result.declined = []  # type: ignore
