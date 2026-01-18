"""Unit tests for GovernanceReviewRequiredPayload (Story 5.5, RT-3)."""

from datetime import datetime, timezone

import pytest

from src.domain.events.governance_review_required import (
    GOVERNANCE_REVIEW_REQUIRED_EVENT_TYPE,
    RT3_THRESHOLD,
    RT3_WINDOW_DAYS,
    GovernanceReviewRequiredPayload,
)


class TestGovernanceReviewRequiredPayload:
    """Tests for GovernanceReviewRequiredPayload dataclass."""

    def test_payload_creation_with_required_fields(self) -> None:
        """Test payload can be created with all required fields."""
        now = datetime.now(timezone.utc)
        payload = GovernanceReviewRequiredPayload(
            override_count=25,
            window_days=365,
            threshold=20,
            detected_at=now,
        )

        assert payload.override_count == 25
        assert payload.window_days == 365
        assert payload.threshold == 20
        assert payload.detected_at == now

    def test_payload_is_frozen(self) -> None:
        """Test payload is immutable (frozen dataclass)."""
        now = datetime.now(timezone.utc)
        payload = GovernanceReviewRequiredPayload(
            override_count=25,
            window_days=365,
            threshold=20,
            detected_at=now,
        )

        with pytest.raises(AttributeError):
            payload.override_count = 30  # type: ignore[misc]

    def test_signable_content_determinism(self) -> None:
        """Test signable_content() returns deterministic bytes."""
        fixed_time = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        payload = GovernanceReviewRequiredPayload(
            override_count=25,
            window_days=365,
            threshold=20,
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
        payload = GovernanceReviewRequiredPayload(
            override_count=25,
            window_days=365,
            threshold=20,
            detected_at=fixed_time,
        )

        content = payload.signable_content()
        content_str = content.decode("utf-8")

        # Verify key fields are present
        assert "GovernanceReviewRequired" in content_str
        assert '"override_count": 25' in content_str
        assert '"window_days": 365' in content_str
        assert '"threshold": 20' in content_str
        assert fixed_time.isoformat() in content_str

    def test_signable_content_different_for_different_payloads(self) -> None:
        """Test different payloads produce different signable content."""
        now = datetime.now(timezone.utc)
        payload1 = GovernanceReviewRequiredPayload(
            override_count=25,
            window_days=365,
            threshold=20,
            detected_at=now,
        )
        payload2 = GovernanceReviewRequiredPayload(
            override_count=30,
            window_days=365,
            threshold=20,
            detected_at=now,
        )

        assert payload1.signable_content() != payload2.signable_content()


class TestRT3Constants:
    """Tests for RT-3 threshold constants."""

    def test_rt3_threshold_value(self) -> None:
        """Test RT-3 threshold is 20 overrides."""
        assert RT3_THRESHOLD == 20

    def test_rt3_window_days_value(self) -> None:
        """Test RT-3 window is 365 days."""
        assert RT3_WINDOW_DAYS == 365


class TestEventTypeConstant:
    """Tests for event type constant."""

    def test_event_type_constant_value(self) -> None:
        """Test event type constant has correct value."""
        assert (
            GOVERNANCE_REVIEW_REQUIRED_EVENT_TYPE
            == "override.governance_review_required"
        )
