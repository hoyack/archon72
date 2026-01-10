"""Unit tests for AntiSuccessAlertPayload (Story 5.5, FR27)."""

from datetime import datetime, timezone

import pytest

from src.domain.events.anti_success_alert import (
    ANTI_SUCCESS_ALERT_EVENT_TYPE,
    AlertType,
    AntiSuccessAlertPayload,
)


class TestAntiSuccessAlertPayload:
    """Tests for AntiSuccessAlertPayload dataclass."""

    def test_payload_creation_with_required_fields(self) -> None:
        """Test payload can be created with all required fields."""
        now = datetime.now(timezone.utc)
        payload = AntiSuccessAlertPayload(
            alert_type=AlertType.PERCENTAGE_INCREASE,
            before_count=5,
            after_count=10,
            percentage_change=100.0,
            window_days=30,
            detected_at=now,
        )

        assert payload.alert_type == AlertType.PERCENTAGE_INCREASE
        assert payload.before_count == 5
        assert payload.after_count == 10
        assert payload.percentage_change == 100.0
        assert payload.window_days == 30
        assert payload.detected_at == now

    def test_payload_is_frozen(self) -> None:
        """Test payload is immutable (frozen dataclass)."""
        now = datetime.now(timezone.utc)
        payload = AntiSuccessAlertPayload(
            alert_type=AlertType.PERCENTAGE_INCREASE,
            before_count=5,
            after_count=10,
            percentage_change=100.0,
            window_days=30,
            detected_at=now,
        )

        with pytest.raises(AttributeError):
            payload.before_count = 20  # type: ignore[misc]

    def test_signable_content_determinism(self) -> None:
        """Test signable_content() returns deterministic bytes."""
        fixed_time = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        payload = AntiSuccessAlertPayload(
            alert_type=AlertType.PERCENTAGE_INCREASE,
            before_count=5,
            after_count=10,
            percentage_change=100.0,
            window_days=30,
            detected_at=fixed_time,
        )

        # Call twice to verify determinism
        content1 = payload.signable_content()
        content2 = payload.signable_content()

        assert content1 == content2
        assert isinstance(content1, bytes)

    def test_signable_content_includes_all_fields(self) -> None:
        """Test signable_content() includes all relevant fields."""
        fixed_time = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        payload = AntiSuccessAlertPayload(
            alert_type=AlertType.THRESHOLD_30_DAY,
            before_count=5,
            after_count=8,
            percentage_change=60.0,
            window_days=30,
            detected_at=fixed_time,
        )

        content = payload.signable_content()
        content_str = content.decode("utf-8")

        # Verify key fields are present
        assert "AntiSuccessAlert" in content_str
        assert "THRESHOLD_30_DAY" in content_str
        assert '"before_count": 5' in content_str
        assert '"after_count": 8' in content_str
        assert '"percentage_change": 60.0' in content_str
        assert '"window_days": 30' in content_str
        assert fixed_time.isoformat() in content_str

    def test_signable_content_different_for_different_payloads(self) -> None:
        """Test different payloads produce different signable content."""
        now = datetime.now(timezone.utc)
        payload1 = AntiSuccessAlertPayload(
            alert_type=AlertType.PERCENTAGE_INCREASE,
            before_count=5,
            after_count=10,
            percentage_change=100.0,
            window_days=30,
            detected_at=now,
        )
        payload2 = AntiSuccessAlertPayload(
            alert_type=AlertType.THRESHOLD_30_DAY,
            before_count=5,
            after_count=10,
            percentage_change=100.0,
            window_days=30,
            detected_at=now,
        )

        assert payload1.signable_content() != payload2.signable_content()


class TestAlertType:
    """Tests for AlertType enum."""

    def test_percentage_increase_type(self) -> None:
        """Test PERCENTAGE_INCREASE alert type."""
        assert AlertType.PERCENTAGE_INCREASE.value == "PERCENTAGE_INCREASE"

    def test_threshold_30_day_type(self) -> None:
        """Test THRESHOLD_30_DAY alert type."""
        assert AlertType.THRESHOLD_30_DAY.value == "THRESHOLD_30_DAY"


class TestEventTypeConstant:
    """Tests for event type constant."""

    def test_event_type_constant_value(self) -> None:
        """Test event type constant has correct value."""
        assert ANTI_SUCCESS_ALERT_EVENT_TYPE == "override.anti_success_alert"
