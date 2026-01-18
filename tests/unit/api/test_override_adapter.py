"""Unit tests for EventToOverrideAdapter (Story 5.3, FR25).

Tests for adapter that transforms domain Event to Override API response.

Constitutional Constraints:
- FR25: All overrides SHALL be publicly visible
- FR44: No authentication required
- CT-12: Witnessing creates accountability

CRITICAL: Keeper identity is NOT anonymized per FR25.
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from src.api.adapters.override import EventToOverrideAdapter
from src.api.models.override import OverrideEventResponse
from src.domain.events import Event


class TestEventToOverrideAdapter:
    """Tests for EventToOverrideAdapter class."""

    def _create_override_event(
        self,
        *,
        event_id=None,
        sequence: int = 1,
        keeper_id: str = "keeper-alpha-001",
        scope: str = "agent_pool_size",
        duration: int = 3600,
        reason: str = "EMERGENCY_RESPONSE",
        action_type: str = "CONFIG_CHANGE",
        initiated_at: datetime = None,
        witness_id: str = "witness-001",
    ) -> Event:
        """Create a sample override Event for testing."""
        if initiated_at is None:
            initiated_at = datetime.now(timezone.utc)

        return Event(
            event_id=event_id or uuid4(),
            sequence=sequence,
            event_type="override.initiated",
            payload={
                "keeper_id": keeper_id,
                "scope": scope,
                "duration": duration,
                "reason": reason,
                "action_type": action_type,
                "initiated_at": initiated_at.isoformat(),
            },
            prev_hash="0" * 64,
            content_hash="a" * 64,
            signature="sig123",
            hash_alg_version=1,
            sig_alg_version=1,
            signing_key_id="key-001",
            agent_id=None,  # Override events don't have agent_id
            witness_id=witness_id,
            witness_signature="wsig123",
            local_timestamp=initiated_at,
        )

    def test_adapter_exists(self) -> None:
        """Test that EventToOverrideAdapter exists."""
        assert EventToOverrideAdapter is not None

    def test_adapt_event_to_response(self) -> None:
        """Test converting domain Event to OverrideEventResponse."""
        event = self._create_override_event()

        response = EventToOverrideAdapter.to_response(event)

        assert isinstance(response, OverrideEventResponse)
        assert response.override_id == event.event_id
        assert response.sequence == event.sequence
        assert response.event_hash == event.content_hash

    def test_keeper_id_is_visible_not_anonymized(self) -> None:
        """Test that Keeper ID is visible and NOT anonymized (FR25).

        CRITICAL: Per FR25, all overrides SHALL be publicly visible.
        Keeper identity MUST be visible for public accountability.
        """
        keeper_id = "keeper-alpha-001"
        event = self._create_override_event(keeper_id=keeper_id)

        response = EventToOverrideAdapter.to_response(event)

        # FR25: Keeper identity MUST be visible (NOT anonymized)
        assert response.keeper_id == keeper_id
        assert response.keeper_id != "[REDACTED]"
        assert response.keeper_id != "***"
        assert "anonymous" not in response.keeper_id.lower()

    def test_full_scope_is_visible(self) -> None:
        """Test that full override scope is visible (FR25, AC2)."""
        scope = "agent_pool_size"
        event = self._create_override_event(scope=scope)

        response = EventToOverrideAdapter.to_response(event)

        assert response.scope == scope

    def test_full_reason_is_visible(self) -> None:
        """Test that full override reason is visible (FR25, AC2)."""
        reason = "EMERGENCY_RESPONSE"
        event = self._create_override_event(reason=reason)

        response = EventToOverrideAdapter.to_response(event)

        assert response.reason == reason

    def test_duration_is_visible(self) -> None:
        """Test that duration is visible (FR25, AC2)."""
        duration = 3600
        event = self._create_override_event(duration=duration)

        response = EventToOverrideAdapter.to_response(event)

        assert response.duration == duration

    def test_expires_at_calculation(self) -> None:
        """Test that expires_at is calculated correctly from initiated_at + duration."""
        initiated_at = datetime(2026, 1, 7, 10, 0, 0, tzinfo=timezone.utc)
        duration = 3600  # 1 hour

        event = self._create_override_event(
            initiated_at=initiated_at,
            duration=duration,
        )

        response = EventToOverrideAdapter.to_response(event)

        expected_expires_at = initiated_at + timedelta(seconds=duration)
        assert response.expires_at == expected_expires_at

    def test_action_type_is_visible(self) -> None:
        """Test that action_type is visible (AC2)."""
        action_type = "CONFIG_CHANGE"
        event = self._create_override_event(action_type=action_type)

        response = EventToOverrideAdapter.to_response(event)

        assert response.action_type == action_type

    def test_witness_id_is_visible(self) -> None:
        """Test that witness_id is visible for CT-12 compliance."""
        witness_id = "witness-001"
        event = self._create_override_event(witness_id=witness_id)

        response = EventToOverrideAdapter.to_response(event)

        assert response.witness_id == witness_id

    def test_adapt_list_of_events(self) -> None:
        """Test converting a list of Events to responses."""
        events = [self._create_override_event(sequence=i) for i in range(1, 4)]

        responses = EventToOverrideAdapter.to_response_list(events)

        assert len(responses) == 3
        assert all(isinstance(r, OverrideEventResponse) for r in responses)
        assert [r.sequence for r in responses] == [1, 2, 3]

    def test_adapt_empty_list(self) -> None:
        """Test converting empty list returns empty list."""
        responses = EventToOverrideAdapter.to_response_list([])

        assert responses == []

    def test_initiated_at_is_preserved(self) -> None:
        """Test that initiated_at timestamp is preserved."""
        initiated_at = datetime(2026, 1, 7, 10, 30, 0, tzinfo=timezone.utc)
        event = self._create_override_event(initiated_at=initiated_at)

        response = EventToOverrideAdapter.to_response(event)

        assert response.initiated_at == initiated_at

    def test_different_keepers_are_distinguishable(self) -> None:
        """Test that different Keeper IDs remain distinguishable (FR25)."""
        events = [
            self._create_override_event(keeper_id="keeper-alpha", sequence=1),
            self._create_override_event(keeper_id="keeper-beta", sequence=2),
            self._create_override_event(keeper_id="keeper-gamma", sequence=3),
        ]

        responses = EventToOverrideAdapter.to_response_list(events)

        keeper_ids = [r.keeper_id for r in responses]
        assert len(set(keeper_ids)) == 3  # All unique
        assert "keeper-alpha" in keeper_ids
        assert "keeper-beta" in keeper_ids
        assert "keeper-gamma" in keeper_ids

    def test_all_fields_for_public_visibility(self) -> None:
        """Test that all required fields are visible for full public transparency (FR25).

        Per FR25: All override data must be publicly visible.
        This test ensures no fields are hidden or omitted.
        """
        event = self._create_override_event(
            keeper_id="keeper-test",
            scope="test_scope",
            duration=7200,
            reason="PLANNED_MAINTENANCE",
            action_type="SYSTEM_RESTART",
            witness_id="witness-test",
        )

        response = EventToOverrideAdapter.to_response(event)

        # All fields must be present and non-None
        assert response.override_id is not None
        assert response.keeper_id is not None
        assert response.scope is not None
        assert response.duration is not None
        assert response.reason is not None
        assert response.action_type is not None
        assert response.initiated_at is not None
        assert response.expires_at is not None
        assert response.event_hash is not None
        assert response.sequence is not None
        # witness_id is optional but should be present when provided
        assert response.witness_id is not None
