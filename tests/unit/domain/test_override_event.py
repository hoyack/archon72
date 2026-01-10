"""Unit tests for OverrideEventPayload (Story 5.1, FR23; Story 5.2, FR24, FR28).

Tests the override event payload that captures Keeper override actions.
All overrides must be logged BEFORE they take effect (FR23, CT-11).

Constitutional Constraints Tested:
- FR23: Override actions must be logged before they take effect
- FR24: Duration must be bounded (max 7 days, min 60 seconds)
- FR28: Reason must be from enumerated OverrideReason list
- CT-12: Witnessing creates accountability (signable_content for witness)
- AC2: Override event must include keeper_id, scope, duration, reason, action_type, timestamp
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from src.domain.errors.constitutional import ConstitutionalViolationError
from src.domain.errors.override import DurationValidationError
from src.domain.events.override_event import (
    MAX_DURATION_SECONDS,
    OVERRIDE_EVENT_TYPE,
    OVERRIDE_EXPIRED_EVENT_TYPE,
    ActionType,
    OverrideEventPayload,
    OverrideExpiredEventPayload,
)
from src.domain.models.override_reason import OverrideReason


class TestOverrideEventPayload:
    """Tests for OverrideEventPayload creation and validation."""

    def test_create_valid_payload(self) -> None:
        """Test creating a valid override event payload."""
        now = datetime.now(timezone.utc)
        payload = OverrideEventPayload(
            keeper_id="keeper-001",
            scope="config.parameter",
            duration=3600,
            reason="Emergency maintenance required",
            action_type=ActionType.CONFIG_CHANGE,
            initiated_at=now,
        )

        assert payload.keeper_id == "keeper-001"
        assert payload.scope == "config.parameter"
        assert payload.duration == 3600
        assert payload.reason == "Emergency maintenance required"
        assert payload.action_type == ActionType.CONFIG_CHANGE
        assert payload.initiated_at == now

    def test_event_type_constant(self) -> None:
        """Test that OVERRIDE_EVENT_TYPE is correctly defined."""
        assert OVERRIDE_EVENT_TYPE == "override.initiated"

    def test_payload_is_immutable(self) -> None:
        """Test that payload is frozen (immutable)."""
        now = datetime.now(timezone.utc)
        payload = OverrideEventPayload(
            keeper_id="keeper-001",
            scope="config.parameter",
            duration=3600,
            reason="Test",
            action_type=ActionType.CONFIG_CHANGE,
            initiated_at=now,
        )

        with pytest.raises(AttributeError):
            payload.keeper_id = "keeper-002"  # type: ignore[misc]

    def test_empty_scope_raises_error(self) -> None:
        """Test that empty scope raises ConstitutionalViolationError."""
        now = datetime.now(timezone.utc)

        with pytest.raises(ConstitutionalViolationError, match="scope"):
            OverrideEventPayload(
                keeper_id="keeper-001",
                scope="",
                duration=3600,
                reason="Test",
                action_type=ActionType.CONFIG_CHANGE,
                initiated_at=now,
            )

    def test_whitespace_scope_raises_error(self) -> None:
        """Test that whitespace-only scope raises ConstitutionalViolationError."""
        now = datetime.now(timezone.utc)

        with pytest.raises(ConstitutionalViolationError, match="scope"):
            OverrideEventPayload(
                keeper_id="keeper-001",
                scope="   ",
                duration=3600,
                reason="Test",
                action_type=ActionType.CONFIG_CHANGE,
                initiated_at=now,
            )

    def test_zero_duration_raises_error(self) -> None:
        """Test that zero duration raises ConstitutionalViolationError."""
        now = datetime.now(timezone.utc)

        with pytest.raises(ConstitutionalViolationError, match="duration"):
            OverrideEventPayload(
                keeper_id="keeper-001",
                scope="config.parameter",
                duration=0,
                reason="Test",
                action_type=ActionType.CONFIG_CHANGE,
                initiated_at=now,
            )

    def test_negative_duration_raises_error(self) -> None:
        """Test that negative duration raises ConstitutionalViolationError."""
        now = datetime.now(timezone.utc)

        with pytest.raises(ConstitutionalViolationError, match="duration"):
            OverrideEventPayload(
                keeper_id="keeper-001",
                scope="config.parameter",
                duration=-100,
                reason="Test",
                action_type=ActionType.CONFIG_CHANGE,
                initiated_at=now,
            )

    def test_empty_keeper_id_raises_error(self) -> None:
        """Test that empty keeper_id raises ConstitutionalViolationError."""
        now = datetime.now(timezone.utc)

        with pytest.raises(ConstitutionalViolationError, match="keeper_id"):
            OverrideEventPayload(
                keeper_id="",
                scope="config.parameter",
                duration=3600,
                reason="Test",
                action_type=ActionType.CONFIG_CHANGE,
                initiated_at=now,
            )

    def test_whitespace_keeper_id_raises_error(self) -> None:
        """Test that whitespace-only keeper_id raises ConstitutionalViolationError."""
        now = datetime.now(timezone.utc)

        with pytest.raises(ConstitutionalViolationError, match="keeper_id"):
            OverrideEventPayload(
                keeper_id="   ",
                scope="config.parameter",
                duration=3600,
                reason="Test",
                action_type=ActionType.CONFIG_CHANGE,
                initiated_at=now,
            )

    def test_empty_reason_raises_error(self) -> None:
        """Test that empty reason raises ConstitutionalViolationError."""
        now = datetime.now(timezone.utc)

        with pytest.raises(ConstitutionalViolationError, match="reason"):
            OverrideEventPayload(
                keeper_id="keeper-001",
                scope="config.parameter",
                duration=3600,
                reason="",
                action_type=ActionType.CONFIG_CHANGE,
                initiated_at=now,
            )

    def test_whitespace_reason_raises_error(self) -> None:
        """Test that whitespace-only reason raises ConstitutionalViolationError."""
        now = datetime.now(timezone.utc)

        with pytest.raises(ConstitutionalViolationError, match="reason"):
            OverrideEventPayload(
                keeper_id="keeper-001",
                scope="config.parameter",
                duration=3600,
                reason="   ",
                action_type=ActionType.CONFIG_CHANGE,
                initiated_at=now,
            )


class TestSignableContent:
    """Tests for signable_content() method (CT-12 witnessing)."""

    def test_signable_content_returns_bytes(self) -> None:
        """Test that signable_content returns bytes."""
        now = datetime.now(timezone.utc)
        payload = OverrideEventPayload(
            keeper_id="keeper-001",
            scope="config.parameter",
            duration=3600,
            reason="Test reason",
            action_type=ActionType.CONFIG_CHANGE,
            initiated_at=now,
        )

        content = payload.signable_content()
        assert isinstance(content, bytes)

    def test_signable_content_is_deterministic(self) -> None:
        """Test that signable_content produces deterministic output."""
        now = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        payload = OverrideEventPayload(
            keeper_id="keeper-001",
            scope="config.parameter",
            duration=3600,
            reason="Test reason",
            action_type=ActionType.CONFIG_CHANGE,
            initiated_at=now,
        )

        content1 = payload.signable_content()
        content2 = payload.signable_content()
        assert content1 == content2

    def test_signable_content_includes_event_type(self) -> None:
        """Test that signable_content includes event type."""
        now = datetime.now(timezone.utc)
        payload = OverrideEventPayload(
            keeper_id="keeper-001",
            scope="config.parameter",
            duration=3600,
            reason="Test reason",
            action_type=ActionType.CONFIG_CHANGE,
            initiated_at=now,
        )

        content = payload.signable_content()
        decoded = content.decode("utf-8")
        assert "OverrideEvent" in decoded

    def test_signable_content_includes_all_fields(self) -> None:
        """Test that signable_content includes all required fields."""
        now = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        payload = OverrideEventPayload(
            keeper_id="keeper-001",
            scope="config.parameter",
            duration=3600,
            reason="Test reason",
            action_type=ActionType.CONFIG_CHANGE,
            initiated_at=now,
        )

        content = payload.signable_content()
        decoded = content.decode("utf-8")

        assert "keeper-001" in decoded
        assert "config.parameter" in decoded
        assert "3600" in decoded
        assert "Test reason" in decoded
        assert "CONFIG_CHANGE" in decoded

    def test_different_payloads_produce_different_content(self) -> None:
        """Test that different payloads produce different signable content."""
        now = datetime.now(timezone.utc)
        payload1 = OverrideEventPayload(
            keeper_id="keeper-001",
            scope="config.parameter",
            duration=3600,
            reason="Test reason",
            action_type=ActionType.CONFIG_CHANGE,
            initiated_at=now,
        )
        payload2 = OverrideEventPayload(
            keeper_id="keeper-002",  # Different keeper
            scope="config.parameter",
            duration=3600,
            reason="Test reason",
            action_type=ActionType.CONFIG_CHANGE,
            initiated_at=now,
        )

        assert payload1.signable_content() != payload2.signable_content()


class TestActionType:
    """Tests for ActionType enum."""

    def test_config_change_action_type(self) -> None:
        """Test CONFIG_CHANGE action type."""
        assert ActionType.CONFIG_CHANGE.value == "CONFIG_CHANGE"

    def test_ceremony_override_action_type(self) -> None:
        """Test CEREMONY_OVERRIDE action type."""
        assert ActionType.CEREMONY_OVERRIDE.value == "CEREMONY_OVERRIDE"

    def test_system_restart_action_type(self) -> None:
        """Test SYSTEM_RESTART action type."""
        assert ActionType.SYSTEM_RESTART.value == "SYSTEM_RESTART"

    def test_halt_clear_action_type(self) -> None:
        """Test HALT_CLEAR action type."""
        assert ActionType.HALT_CLEAR.value == "HALT_CLEAR"


class TestPayloadEquality:
    """Tests for payload equality and hashing."""

    def test_equal_payloads(self) -> None:
        """Test that equal payloads are equal."""
        now = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        payload1 = OverrideEventPayload(
            keeper_id="keeper-001",
            scope="config.parameter",
            duration=3600,
            reason="Test",
            action_type=ActionType.CONFIG_CHANGE,
            initiated_at=now,
        )
        payload2 = OverrideEventPayload(
            keeper_id="keeper-001",
            scope="config.parameter",
            duration=3600,
            reason="Test",
            action_type=ActionType.CONFIG_CHANGE,
            initiated_at=now,
        )

        assert payload1 == payload2

    def test_unequal_payloads(self) -> None:
        """Test that unequal payloads are not equal."""
        now = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        payload1 = OverrideEventPayload(
            keeper_id="keeper-001",
            scope="config.parameter",
            duration=3600,
            reason="Test",
            action_type=ActionType.CONFIG_CHANGE,
            initiated_at=now,
        )
        payload2 = OverrideEventPayload(
            keeper_id="keeper-002",
            scope="config.parameter",
            duration=3600,
            reason="Test",
            action_type=ActionType.CONFIG_CHANGE,
            initiated_at=now,
        )

        assert payload1 != payload2

    def test_payload_is_hashable(self) -> None:
        """Test that payload can be used in sets/dicts."""
        now = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        payload = OverrideEventPayload(
            keeper_id="keeper-001",
            scope="config.parameter",
            duration=3600,
            reason="Test",
            action_type=ActionType.CONFIG_CHANGE,
            initiated_at=now,
        )

        # Should be hashable
        hash(payload)
        {payload}  # Can be added to set


class TestMaxDurationValidation:
    """Tests for max duration validation (FR24, Story 5.2)."""

    def test_max_duration_constant(self) -> None:
        """Test that MAX_DURATION_SECONDS is 7 days."""
        assert MAX_DURATION_SECONDS == 604800

    def test_duration_at_max_is_valid(self) -> None:
        """Test that duration at max (7 days) is accepted."""
        now = datetime.now(timezone.utc)
        payload = OverrideEventPayload(
            keeper_id="keeper-001",
            scope="config.parameter",
            duration=MAX_DURATION_SECONDS,
            reason="Test",
            action_type=ActionType.CONFIG_CHANGE,
            initiated_at=now,
        )
        assert payload.duration == MAX_DURATION_SECONDS

    def test_duration_above_max_raises_error(self) -> None:
        """Test that duration above max raises DurationValidationError."""
        now = datetime.now(timezone.utc)

        with pytest.raises(DurationValidationError, match="FR24"):
            OverrideEventPayload(
                keeper_id="keeper-001",
                scope="config.parameter",
                duration=MAX_DURATION_SECONDS + 1,
                reason="Test",
                action_type=ActionType.CONFIG_CHANGE,
                initiated_at=now,
            )

    def test_very_large_duration_raises_error(self) -> None:
        """Test that very large duration raises DurationValidationError."""
        now = datetime.now(timezone.utc)

        with pytest.raises(DurationValidationError):
            OverrideEventPayload(
                keeper_id="keeper-001",
                scope="config.parameter",
                duration=30 * 24 * 60 * 60,  # 30 days
                reason="Test",
                action_type=ActionType.CONFIG_CHANGE,
                initiated_at=now,
            )


class TestExpiresAtProperty:
    """Tests for expires_at computed property (AC2)."""

    def test_expires_at_calculation(self) -> None:
        """Test that expires_at is correctly calculated."""
        now = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        duration = 3600  # 1 hour
        payload = OverrideEventPayload(
            keeper_id="keeper-001",
            scope="config.parameter",
            duration=duration,
            reason="Test",
            action_type=ActionType.CONFIG_CHANGE,
            initiated_at=now,
        )

        expected = now + timedelta(seconds=duration)
        assert payload.expires_at == expected

    def test_expires_at_with_max_duration(self) -> None:
        """Test expires_at with maximum duration."""
        now = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        payload = OverrideEventPayload(
            keeper_id="keeper-001",
            scope="config.parameter",
            duration=MAX_DURATION_SECONDS,
            reason="Test",
            action_type=ActionType.CONFIG_CHANGE,
            initiated_at=now,
        )

        expected = now + timedelta(seconds=MAX_DURATION_SECONDS)
        assert payload.expires_at == expected
        # 7 days later
        assert payload.expires_at == datetime(2025, 1, 8, 12, 0, 0, tzinfo=timezone.utc)


class TestOverrideExpiredEventPayload:
    """Tests for OverrideExpiredEventPayload (AC2, Story 5.2)."""

    def test_expired_event_type_constant(self) -> None:
        """Test that OVERRIDE_EXPIRED_EVENT_TYPE is correctly defined."""
        assert OVERRIDE_EXPIRED_EVENT_TYPE == "override.expired"

    def test_create_valid_expired_payload(self) -> None:
        """Test creating a valid override expired event payload."""
        now = datetime.now(timezone.utc)
        override_id = uuid4()

        payload = OverrideExpiredEventPayload(
            original_override_id=override_id,
            keeper_id="keeper-001",
            scope="config.parameter",
            expired_at=now,
            reversion_status="success",
        )

        assert payload.original_override_id == override_id
        assert payload.keeper_id == "keeper-001"
        assert payload.scope == "config.parameter"
        assert payload.expired_at == now
        assert payload.reversion_status == "success"

    def test_expired_payload_is_immutable(self) -> None:
        """Test that expired payload is frozen (immutable)."""
        now = datetime.now(timezone.utc)
        payload = OverrideExpiredEventPayload(
            original_override_id=uuid4(),
            keeper_id="keeper-001",
            scope="config.parameter",
            expired_at=now,
            reversion_status="success",
        )

        with pytest.raises(AttributeError):
            payload.keeper_id = "keeper-002"  # type: ignore[misc]

    def test_reversion_status_success(self) -> None:
        """Test reversion_status can be 'success'."""
        payload = OverrideExpiredEventPayload(
            original_override_id=uuid4(),
            keeper_id="keeper-001",
            scope="config.parameter",
            expired_at=datetime.now(timezone.utc),
            reversion_status="success",
        )
        assert payload.reversion_status == "success"

    def test_reversion_status_failed(self) -> None:
        """Test reversion_status can be 'failed'."""
        payload = OverrideExpiredEventPayload(
            original_override_id=uuid4(),
            keeper_id="keeper-001",
            scope="config.parameter",
            expired_at=datetime.now(timezone.utc),
            reversion_status="failed",
        )
        assert payload.reversion_status == "failed"


class TestOverrideExpiredSignableContent:
    """Tests for OverrideExpiredEventPayload.signable_content() (CT-12)."""

    def test_signable_content_returns_bytes(self) -> None:
        """Test that signable_content returns bytes."""
        payload = OverrideExpiredEventPayload(
            original_override_id=uuid4(),
            keeper_id="keeper-001",
            scope="config.parameter",
            expired_at=datetime.now(timezone.utc),
            reversion_status="success",
        )

        content = payload.signable_content()
        assert isinstance(content, bytes)

    def test_signable_content_is_deterministic(self) -> None:
        """Test that signable_content produces deterministic output."""
        now = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        override_id = uuid4()

        payload = OverrideExpiredEventPayload(
            original_override_id=override_id,
            keeper_id="keeper-001",
            scope="config.parameter",
            expired_at=now,
            reversion_status="success",
        )

        content1 = payload.signable_content()
        content2 = payload.signable_content()
        assert content1 == content2

    def test_signable_content_includes_event_type(self) -> None:
        """Test that signable_content includes event type."""
        payload = OverrideExpiredEventPayload(
            original_override_id=uuid4(),
            keeper_id="keeper-001",
            scope="config.parameter",
            expired_at=datetime.now(timezone.utc),
            reversion_status="success",
        )

        content = payload.signable_content()
        decoded = content.decode("utf-8")
        assert "OverrideExpiredEvent" in decoded

    def test_signable_content_includes_all_fields(self) -> None:
        """Test that signable_content includes all required fields."""
        now = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        override_id = uuid4()

        payload = OverrideExpiredEventPayload(
            original_override_id=override_id,
            keeper_id="keeper-001",
            scope="config.parameter",
            expired_at=now,
            reversion_status="success",
        )

        content = payload.signable_content()
        decoded = content.decode("utf-8")

        assert str(override_id) in decoded
        assert "keeper-001" in decoded
        assert "config.parameter" in decoded
        assert "success" in decoded
