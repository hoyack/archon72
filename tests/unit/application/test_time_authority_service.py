"""Unit tests for TimeAuthorityService (Story 1.5, Task 1 + HARDENING-1).

Tests clock drift detection and TimeAuthorityProtocol implementation.
No infrastructure dependencies - pure unit tests.

Constitutional Constraints Tested:
- FR6: Events have dual timestamps
- FR7: Sequence is authoritative ordering
- CT-12: Witnessing creates accountability (drift logged for investigation)

HARDENING-1 Additions:
- AC4: TimeAuthorityService implements TimeAuthorityProtocol
- Protocol methods: now(), utcnow(), monotonic()
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from src.application.services.time_authority_service import (
    DEFAULT_DRIFT_THRESHOLD_SECONDS,
    TimeAuthorityService,
)
from src.domain.ports.time_authority import TimeAuthorityProtocol


class TestTimeAuthorityService:
    """Tests for TimeAuthorityService clock drift detection."""

    def test_init_with_default_threshold(self) -> None:
        """Service initializes with default 5 second threshold."""
        service = TimeAuthorityService()
        assert service._threshold == timedelta(seconds=DEFAULT_DRIFT_THRESHOLD_SECONDS)

    def test_init_with_custom_threshold(self) -> None:
        """Service accepts custom drift threshold."""
        service = TimeAuthorityService(drift_threshold_seconds=10.0)
        assert service._threshold == timedelta(seconds=10.0)

    def test_check_drift_no_warning_when_within_threshold(self) -> None:
        """No warning logged when drift is within threshold."""
        service = TimeAuthorityService(drift_threshold_seconds=5.0)
        now = datetime.now(timezone.utc)
        local_ts = now
        authority_ts = now + timedelta(seconds=3)  # 3 seconds drift, under 5

        with patch(
            "src.application.services.time_authority_service.logger"
        ) as mock_logger:
            mock_bound = MagicMock()
            mock_logger.bind.return_value = mock_bound

            service.check_drift(
                local_timestamp=local_ts,
                authority_timestamp=authority_ts,
                event_id="test-event-123",
            )

            # Logger.bind should not be called when no warning
            mock_logger.bind.assert_not_called()
            mock_bound.warning.assert_not_called()

    def test_check_drift_warning_when_exceeds_threshold(self) -> None:
        """Warning logged when drift exceeds threshold."""
        service = TimeAuthorityService(drift_threshold_seconds=5.0)
        now = datetime.now(timezone.utc)
        local_ts = now
        authority_ts = now + timedelta(seconds=10)  # 10 seconds drift, over 5

        with patch(
            "src.application.services.time_authority_service.logger"
        ) as mock_logger:
            mock_bound = MagicMock()
            mock_logger.bind.return_value = mock_bound

            service.check_drift(
                local_timestamp=local_ts,
                authority_timestamp=authority_ts,
                event_id="test-event-123",
            )

            # Logger should be bound with context and warning issued
            mock_logger.bind.assert_called_once()
            call_kwargs = mock_logger.bind.call_args.kwargs
            assert call_kwargs["event_id"] == "test-event-123"
            assert "drift_seconds" in call_kwargs
            assert call_kwargs["drift_seconds"] == 10.0

            mock_bound.warning.assert_called_once()
            warning_args = mock_bound.warning.call_args
            assert warning_args[0][0] == "clock_drift_detected"

    def test_check_drift_warning_with_negative_drift(self) -> None:
        """Warning logged when authority is behind local (negative drift)."""
        service = TimeAuthorityService(drift_threshold_seconds=5.0)
        now = datetime.now(timezone.utc)
        local_ts = now
        authority_ts = now - timedelta(seconds=10)  # Authority 10 seconds behind

        with patch(
            "src.application.services.time_authority_service.logger"
        ) as mock_logger:
            mock_bound = MagicMock()
            mock_logger.bind.return_value = mock_bound

            service.check_drift(
                local_timestamp=local_ts,
                authority_timestamp=authority_ts,
                event_id="test-event-456",
            )

            # Should still log warning (absolute value)
            mock_logger.bind.assert_called_once()
            call_kwargs = mock_logger.bind.call_args.kwargs
            assert call_kwargs["drift_seconds"] == 10.0  # Absolute value

    def test_check_drift_exact_threshold_no_warning(self) -> None:
        """No warning when drift equals threshold exactly."""
        service = TimeAuthorityService(drift_threshold_seconds=5.0)
        now = datetime.now(timezone.utc)
        local_ts = now
        authority_ts = now + timedelta(seconds=5)  # Exactly at threshold

        with patch(
            "src.application.services.time_authority_service.logger"
        ) as mock_logger:
            mock_bound = MagicMock()
            mock_logger.bind.return_value = mock_bound

            service.check_drift(
                local_timestamp=local_ts,
                authority_timestamp=authority_ts,
                event_id="test-event-789",
            )

            # At threshold, should NOT warn (only > threshold)
            mock_logger.bind.assert_not_called()

    def test_check_drift_just_over_threshold_warns(self) -> None:
        """Warning when drift just exceeds threshold."""
        service = TimeAuthorityService(drift_threshold_seconds=5.0)
        now = datetime.now(timezone.utc)
        local_ts = now
        authority_ts = now + timedelta(seconds=5.001)  # Just over threshold

        with patch(
            "src.application.services.time_authority_service.logger"
        ) as mock_logger:
            mock_bound = MagicMock()
            mock_logger.bind.return_value = mock_bound

            service.check_drift(
                local_timestamp=local_ts,
                authority_timestamp=authority_ts,
                event_id="test-event-edge",
            )

            # Just over threshold should warn
            mock_logger.bind.assert_called_once()
            mock_bound.warning.assert_called_once()

    def test_check_drift_logs_timestamps_as_iso_format(self) -> None:
        """Logged timestamps are in ISO format."""
        service = TimeAuthorityService(drift_threshold_seconds=5.0)
        now = datetime.now(timezone.utc)
        local_ts = now
        authority_ts = now + timedelta(seconds=10)

        with patch(
            "src.application.services.time_authority_service.logger"
        ) as mock_logger:
            mock_bound = MagicMock()
            mock_logger.bind.return_value = mock_bound

            service.check_drift(
                local_timestamp=local_ts,
                authority_timestamp=authority_ts,
                event_id="test-event-iso",
            )

            call_kwargs = mock_logger.bind.call_args.kwargs
            # Verify timestamps are ISO strings
            assert call_kwargs["local_timestamp"] == local_ts.isoformat()
            assert call_kwargs["authority_timestamp"] == authority_ts.isoformat()

    def test_check_drift_with_zero_drift(self) -> None:
        """No warning with zero drift."""
        service = TimeAuthorityService(drift_threshold_seconds=5.0)
        now = datetime.now(timezone.utc)

        with patch(
            "src.application.services.time_authority_service.logger"
        ) as mock_logger:
            mock_bound = MagicMock()
            mock_logger.bind.return_value = mock_bound

            service.check_drift(
                local_timestamp=now,
                authority_timestamp=now,  # Same timestamp
                event_id="test-event-zero",
            )

            mock_logger.bind.assert_not_called()

    def test_check_drift_returns_drift_value(self) -> None:
        """check_drift returns the drift value for caller inspection."""
        service = TimeAuthorityService(drift_threshold_seconds=5.0)
        now = datetime.now(timezone.utc)
        local_ts = now
        authority_ts = now + timedelta(seconds=3.5)

        with patch("src.application.services.time_authority_service.logger"):
            drift = service.check_drift(
                local_timestamp=local_ts,
                authority_timestamp=authority_ts,
                event_id="test-event-return",
            )

            assert drift == timedelta(seconds=3.5)

    def test_check_drift_returns_absolute_drift(self) -> None:
        """check_drift returns absolute drift value."""
        service = TimeAuthorityService(drift_threshold_seconds=5.0)
        now = datetime.now(timezone.utc)
        local_ts = now
        authority_ts = now - timedelta(seconds=3.5)  # Negative

        with patch("src.application.services.time_authority_service.logger"):
            drift = service.check_drift(
                local_timestamp=local_ts,
                authority_timestamp=authority_ts,
                event_id="test-event-abs",
            )

            # Should be positive (absolute)
            assert drift == timedelta(seconds=3.5)


class TestTimeAuthorityServiceEdgeCases:
    """Edge case tests for TimeAuthorityService."""

    def test_very_large_drift(self) -> None:
        """Handles very large drift values."""
        service = TimeAuthorityService(drift_threshold_seconds=5.0)
        now = datetime.now(timezone.utc)
        local_ts = now
        authority_ts = now + timedelta(days=1)  # 24 hours drift

        with patch(
            "src.application.services.time_authority_service.logger"
        ) as mock_logger:
            mock_bound = MagicMock()
            mock_logger.bind.return_value = mock_bound

            drift = service.check_drift(
                local_timestamp=local_ts,
                authority_timestamp=authority_ts,
                event_id="test-event-large",
            )

            mock_logger.bind.assert_called_once()
            assert drift == timedelta(days=1)

    def test_very_small_threshold(self) -> None:
        """Works with very small threshold."""
        service = TimeAuthorityService(drift_threshold_seconds=0.001)  # 1ms
        now = datetime.now(timezone.utc)
        local_ts = now
        authority_ts = now + timedelta(milliseconds=5)  # 5ms drift

        with patch(
            "src.application.services.time_authority_service.logger"
        ) as mock_logger:
            mock_bound = MagicMock()
            mock_logger.bind.return_value = mock_bound

            service.check_drift(
                local_timestamp=local_ts,
                authority_timestamp=authority_ts,
                event_id="test-event-small-threshold",
            )

            mock_logger.bind.assert_called_once()

    def test_different_timezone_timestamps(self) -> None:
        """Handles timestamps from different timezones correctly."""
        service = TimeAuthorityService(drift_threshold_seconds=5.0)

        # Create timestamps in different timezones
        utc_time = datetime.now(timezone.utc)
        # Same instant, but expressed in a different timezone representation
        # (The drift should still be calculated correctly based on absolute time)
        eastern = timezone(timedelta(hours=-5))
        eastern_time = utc_time.astimezone(eastern)

        with patch(
            "src.application.services.time_authority_service.logger"
        ) as mock_logger:
            mock_bound = MagicMock()
            mock_logger.bind.return_value = mock_bound

            drift = service.check_drift(
                local_timestamp=utc_time,
                authority_timestamp=eastern_time,
                event_id="test-event-tz",
            )

            # Same instant = zero drift
            assert drift == timedelta(seconds=0)
            mock_logger.bind.assert_not_called()


class TestTimeAuthorityProtocolImplementation:
    """Tests for TimeAuthorityProtocol implementation (HARDENING-1, AC4)."""

    def test_implements_time_authority_protocol(self) -> None:
        """TimeAuthorityService implements TimeAuthorityProtocol."""
        service = TimeAuthorityService()
        assert isinstance(service, TimeAuthorityProtocol)

    def test_now_returns_datetime(self) -> None:
        """now() returns a datetime object."""
        service = TimeAuthorityService()
        result = service.now()
        assert isinstance(result, datetime)

    def test_now_returns_timezone_aware_utc(self) -> None:
        """now() returns UTC timezone-aware datetime."""
        service = TimeAuthorityService()
        result = service.now()
        assert result.tzinfo is not None
        assert result.tzinfo == timezone.utc

    def test_now_returns_current_time(self) -> None:
        """now() returns approximately current time."""
        service = TimeAuthorityService()
        before = datetime.now(timezone.utc)
        result = service.now()
        after = datetime.now(timezone.utc)

        assert before <= result <= after

    def test_utcnow_returns_datetime(self) -> None:
        """utcnow() returns a datetime object."""
        service = TimeAuthorityService()
        result = service.utcnow()
        assert isinstance(result, datetime)

    def test_utcnow_returns_utc_timezone(self) -> None:
        """utcnow() returns UTC timezone-aware datetime."""
        service = TimeAuthorityService()
        result = service.utcnow()
        assert result.tzinfo is not None
        assert result.tzinfo == timezone.utc

    def test_now_and_utcnow_return_same_timezone(self) -> None:
        """now() and utcnow() both return UTC for consistency."""
        service = TimeAuthorityService()
        now_result = service.now()
        utcnow_result = service.utcnow()

        # Both should be in UTC
        assert now_result.tzinfo == timezone.utc
        assert utcnow_result.tzinfo == timezone.utc

    def test_monotonic_returns_float(self) -> None:
        """monotonic() returns a float."""
        service = TimeAuthorityService()
        result = service.monotonic()
        assert isinstance(result, float)

    def test_monotonic_is_monotonically_increasing(self) -> None:
        """monotonic() values never decrease."""
        service = TimeAuthorityService()
        values = [service.monotonic() for _ in range(100)]

        for i in range(1, len(values)):
            assert values[i] >= values[i - 1], "monotonic() must never decrease"

    def test_monotonic_increases_with_time(self) -> None:
        """monotonic() increases as time passes."""
        import time

        service = TimeAuthorityService()
        before = service.monotonic()
        time.sleep(0.01)  # Sleep 10ms
        after = service.monotonic()

        assert after > before
