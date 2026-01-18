"""Integration tests for Keeper Attribution with Scope & Duration (Story 5.2).

Tests the complete flow of:
- AC1: Override events include enumerated reason (FR28)
- AC2: Automatic expiration after duration elapses (FR24)
- AC3: Duration validation (min 60s, max 7 days)
- AC4: expires_at property on OverrideEventPayload
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from src.domain.errors.override import DurationValidationError
from src.domain.events.override_event import (
    MAX_DURATION_SECONDS,
    ActionType,
    OverrideEventPayload,
    OverrideExpiredEventPayload,
)
from src.domain.models.override_reason import OverrideReason
from src.domain.services.duration_validator import (
    MIN_DURATION_SECONDS,
    validate_duration,
)
from src.infrastructure.stubs.override_registry_stub import OverrideRegistryStub


class TestAC1EnumeratedOverrideReasons:
    """AC1: Override events SHALL include enumerated reason attribute (FR28)."""

    def test_all_override_reasons_have_description(self) -> None:
        """Test that all OverrideReason values have descriptions."""
        for reason in OverrideReason:
            assert reason.description, f"{reason.name} has no description"
            assert len(reason.description) > 10

    def test_reason_serialization_roundtrip(self) -> None:
        """Test that reasons can be serialized and deserialized."""
        for reason in OverrideReason:
            serialized = reason.value
            deserialized = OverrideReason(serialized)
            assert deserialized == reason

    def test_override_event_includes_reason(self) -> None:
        """Test that override event payload includes reason."""
        now = datetime.now(timezone.utc)
        payload = OverrideEventPayload(
            keeper_id="keeper-001",
            scope="config.parameter",
            duration=3600,
            reason=OverrideReason.TECHNICAL_FAILURE.description,
            action_type=ActionType.CONFIG_CHANGE,
            initiated_at=now,
        )

        # Reason is in signable content
        content = payload.signable_content()
        assert (
            OverrideReason.TECHNICAL_FAILURE.description.split()[0].lower()
            in content.decode().lower()
        )


class TestAC2AutomaticExpiration:
    """AC2: Override automatically expires after duration elapses (FR24)."""

    @pytest.fixture
    def registry(self) -> OverrideRegistryStub:
        """Create a fresh registry for each test."""
        return OverrideRegistryStub()

    @pytest.mark.asyncio
    async def test_override_detected_as_expired_after_duration(
        self, registry: OverrideRegistryStub
    ) -> None:
        """Test that override is detected as expired after duration passes."""
        override_id = uuid4()
        # Already expired
        expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)

        await registry.register_active_override(
            override_id=override_id,
            keeper_id="keeper-001",
            scope="config.parameter",
            expires_at=expires_at,
        )

        expired = await registry.get_expired_overrides()
        assert len(expired) == 1
        assert expired[0].override_id == override_id

    @pytest.mark.asyncio
    async def test_expired_override_event_payload_created(
        self, registry: OverrideRegistryStub
    ) -> None:
        """Test that expired override info can create event payload."""
        override_id = uuid4()
        expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)

        await registry.register_active_override(
            override_id=override_id,
            keeper_id="keeper-001",
            scope="config.parameter",
            expires_at=expires_at,
        )

        expired_list = await registry.get_expired_overrides()
        info = expired_list[0]

        # Create expiration event payload
        payload = OverrideExpiredEventPayload(
            original_override_id=info.override_id,
            keeper_id=info.keeper_id,
            scope=info.scope,
            expired_at=datetime.now(timezone.utc),
            reversion_status="success",
        )

        assert payload.original_override_id == override_id
        assert payload.reversion_status == "success"


class TestAC3DurationValidation:
    """AC3: Duration validated to be within bounds (min 60s, max 7 days)."""

    def test_minimum_duration_is_60_seconds(self) -> None:
        """Test that minimum duration constant is 60 seconds."""
        assert MIN_DURATION_SECONDS == 60

    def test_maximum_duration_is_7_days(self) -> None:
        """Test that maximum duration is 7 days."""
        expected_7_days = 7 * 24 * 60 * 60
        assert expected_7_days == MAX_DURATION_SECONDS

    def test_duration_at_minimum_is_valid(self) -> None:
        """Test that exactly 60 seconds is valid."""
        validate_duration(60)  # Should not raise

    def test_duration_at_maximum_is_valid(self) -> None:
        """Test that exactly 7 days is valid."""
        validate_duration(MAX_DURATION_SECONDS)  # Should not raise

    def test_duration_below_minimum_fails(self) -> None:
        """Test that duration below 60 seconds raises error."""
        with pytest.raises(DurationValidationError, match="FR24"):
            validate_duration(59)

    def test_duration_above_maximum_fails(self) -> None:
        """Test that duration above 7 days raises error."""
        with pytest.raises(DurationValidationError, match="FR24"):
            validate_duration(MAX_DURATION_SECONDS + 1)

    def test_zero_duration_fails(self) -> None:
        """Test that zero duration raises error (indefinite prohibited)."""
        with pytest.raises(DurationValidationError, match="FR24"):
            validate_duration(0)

    def test_negative_duration_fails(self) -> None:
        """Test that negative duration raises error."""
        with pytest.raises(DurationValidationError, match="FR24"):
            validate_duration(-1)

    def test_override_payload_rejects_excessive_duration(self) -> None:
        """Test that OverrideEventPayload rejects duration > 7 days."""
        with pytest.raises(DurationValidationError, match="FR24"):
            OverrideEventPayload(
                keeper_id="keeper-001",
                scope="config.parameter",
                duration=MAX_DURATION_SECONDS + 1,
                reason="Test",
                action_type=ActionType.CONFIG_CHANGE,
                initiated_at=datetime.now(timezone.utc),
            )


class TestAC4ExpiresAtProperty:
    """AC4: Override payload has expires_at computed property."""

    def test_expires_at_calculated_correctly(self) -> None:
        """Test that expires_at = initiated_at + duration."""
        now = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        duration = 3600  # 1 hour

        payload = OverrideEventPayload(
            keeper_id="keeper-001",
            scope="config.parameter",
            duration=duration,
            reason="Test",
            action_type=ActionType.CONFIG_CHANGE,
            initiated_at=now,
        )

        expected = datetime(2025, 6, 15, 13, 0, 0, tzinfo=timezone.utc)
        assert payload.expires_at == expected

    def test_expires_at_with_max_duration(self) -> None:
        """Test expires_at with maximum 7-day duration."""
        now = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

        payload = OverrideEventPayload(
            keeper_id="keeper-001",
            scope="config.parameter",
            duration=MAX_DURATION_SECONDS,
            reason="Test",
            action_type=ActionType.CONFIG_CHANGE,
            initiated_at=now,
        )

        # 7 days later
        expected = datetime(2025, 1, 8, 0, 0, 0, tzinfo=timezone.utc)
        assert payload.expires_at == expected

    def test_expires_at_with_minimum_duration(self) -> None:
        """Test expires_at with minimum 60-second duration."""
        now = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)

        payload = OverrideEventPayload(
            keeper_id="keeper-001",
            scope="config.parameter",
            duration=MIN_DURATION_SECONDS,
            reason="Test",
            action_type=ActionType.CONFIG_CHANGE,
            initiated_at=now,
        )

        expected = datetime(2025, 6, 15, 12, 1, 0, tzinfo=timezone.utc)
        assert payload.expires_at == expected


class TestEndToEndKeeperAttribution:
    """End-to-end tests for keeper attribution flow."""

    @pytest.fixture
    def registry(self) -> OverrideRegistryStub:
        """Create a fresh registry for each test."""
        return OverrideRegistryStub()

    @pytest.mark.asyncio
    async def test_full_override_lifecycle(
        self, registry: OverrideRegistryStub
    ) -> None:
        """Test complete override lifecycle: register -> expire -> revert."""
        # 1. Create override payload with reason
        now = datetime.now(timezone.utc)
        override_id = uuid4()

        # 2. Simulate registering after event write
        expires_at = now - timedelta(seconds=1)  # Already expired for test

        await registry.register_active_override(
            override_id=override_id,
            keeper_id="keeper-001",
            scope="config.watchdog",
            expires_at=expires_at,
        )

        # 3. Check expiration
        expired = await registry.get_expired_overrides()
        assert len(expired) == 1
        assert expired[0].override_id == override_id
        assert expired[0].keeper_id == "keeper-001"
        assert expired[0].scope == "config.watchdog"

        # 4. Mark as reverted (would be done after writing expiration event)
        await registry.mark_override_reverted(override_id)

        # 5. Verify no longer shows as expired
        expired = await registry.get_expired_overrides()
        assert len(expired) == 0

        # 6. Verify no longer active
        assert not await registry.is_override_active(override_id)
