"""Unit tests for PublicOverrideService (Story 5.3, FR25).

Tests for service that queries override events with public visibility.

Constitutional Constraints:
- FR25: All overrides SHALL be publicly visible
- FR44: No authentication required
- FR46: Query interface supports date range and event type filtering
- CT-12: Witnessing creates accountability
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.application.services.public_override_service import PublicOverrideService
from src.domain.events import Event
from src.domain.events.override_event import OVERRIDE_EVENT_TYPE


class TestPublicOverrideService:
    """Tests for PublicOverrideService class."""

    def _create_mock_event_store(self) -> MagicMock:
        """Create a mock event store."""
        mock = MagicMock()
        mock.get_events_filtered = AsyncMock(return_value=[])
        mock.count_events_filtered = AsyncMock(return_value=0)
        mock.get_event_by_id = AsyncMock(return_value=None)
        return mock

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
    ) -> Event:
        """Create a sample override Event for testing."""
        initiated_at = datetime.now(timezone.utc)

        return Event(
            event_id=event_id or uuid4(),
            sequence=sequence,
            event_type=OVERRIDE_EVENT_TYPE,
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
            witness_id="witness-001",
            witness_signature="wsig123",
            local_timestamp=initiated_at,
        )

    def test_service_exists(self) -> None:
        """Test that PublicOverrideService exists."""
        assert PublicOverrideService is not None

    def test_service_initialization(self) -> None:
        """Test service initializes with event store."""
        mock_event_store = self._create_mock_event_store()

        service = PublicOverrideService(event_store=mock_event_store)

        assert service._event_store is mock_event_store

    @pytest.mark.asyncio
    async def test_get_overrides_calls_event_store(self) -> None:
        """Test that get_overrides calls event store with correct parameters."""
        mock_event_store = self._create_mock_event_store()
        service = PublicOverrideService(event_store=mock_event_store)

        await service.get_overrides(limit=50, offset=10)

        # Verify event store was called with override event type filter
        mock_event_store.get_events_filtered.assert_called_once()
        call_kwargs = mock_event_store.get_events_filtered.call_args[1]
        assert call_kwargs["limit"] == 50
        assert call_kwargs["offset"] == 10
        assert call_kwargs["event_types"] == [OVERRIDE_EVENT_TYPE]

    @pytest.mark.asyncio
    async def test_get_overrides_filters_by_override_event_type(self) -> None:
        """Test that get_overrides filters by override.initiated event type."""
        mock_event_store = self._create_mock_event_store()
        service = PublicOverrideService(event_store=mock_event_store)

        await service.get_overrides()

        call_kwargs = mock_event_store.get_events_filtered.call_args[1]
        assert call_kwargs["event_types"] == [OVERRIDE_EVENT_TYPE]

    @pytest.mark.asyncio
    async def test_get_overrides_with_date_range(self) -> None:
        """Test that get_overrides passes date range filters."""
        mock_event_store = self._create_mock_event_store()
        service = PublicOverrideService(event_store=mock_event_store)

        start_date = datetime(2026, 1, 1, tzinfo=timezone.utc)
        end_date = datetime(2026, 1, 31, tzinfo=timezone.utc)

        await service.get_overrides(start_date=start_date, end_date=end_date)

        call_kwargs = mock_event_store.get_events_filtered.call_args[1]
        assert call_kwargs["start_date"] == start_date
        assert call_kwargs["end_date"] == end_date

    @pytest.mark.asyncio
    async def test_get_overrides_returns_events_and_count(self) -> None:
        """Test that get_overrides returns tuple of (events, total_count)."""
        mock_event_store = self._create_mock_event_store()
        override_events = [self._create_override_event(sequence=i) for i in range(1, 4)]
        mock_event_store.get_events_filtered = AsyncMock(return_value=override_events)
        mock_event_store.count_events_filtered = AsyncMock(return_value=100)

        service = PublicOverrideService(event_store=mock_event_store)

        events, total = await service.get_overrides()

        assert len(events) == 3
        assert total == 100

    @pytest.mark.asyncio
    async def test_get_override_by_id_returns_event(self) -> None:
        """Test that get_override_by_id returns event when found."""
        mock_event_store = self._create_mock_event_store()
        override_event = self._create_override_event()
        mock_event_store.get_event_by_id = AsyncMock(return_value=override_event)

        service = PublicOverrideService(event_store=mock_event_store)

        result = await service.get_override_by_id(str(override_event.event_id))

        assert result == override_event

    @pytest.mark.asyncio
    async def test_get_override_by_id_returns_none_when_not_found(self) -> None:
        """Test that get_override_by_id returns None when not found."""
        mock_event_store = self._create_mock_event_store()
        mock_event_store.get_event_by_id = AsyncMock(return_value=None)

        service = PublicOverrideService(event_store=mock_event_store)

        result = await service.get_override_by_id(str(uuid4()))

        assert result is None

    @pytest.mark.asyncio
    async def test_get_override_by_id_returns_none_for_non_override_event(self) -> None:
        """Test that get_override_by_id returns None for non-override events."""
        mock_event_store = self._create_mock_event_store()
        # Create a non-override event
        non_override_event = Event(
            event_id=uuid4(),
            sequence=1,
            event_type="vote.cast",  # NOT an override event
            payload={"vote": "aye"},
            prev_hash="0" * 64,
            content_hash="a" * 64,
            signature="sig123",
            witness_id="witness-001",
            witness_signature="wsig123",
            local_timestamp=datetime.now(timezone.utc),
        )
        mock_event_store.get_event_by_id = AsyncMock(return_value=non_override_event)

        service = PublicOverrideService(event_store=mock_event_store)

        result = await service.get_override_by_id(str(non_override_event.event_id))

        # Should return None because it's not an override event
        assert result is None

    @pytest.mark.asyncio
    async def test_get_override_by_id_handles_invalid_uuid(self) -> None:
        """Test that get_override_by_id handles invalid UUID gracefully."""
        mock_event_store = self._create_mock_event_store()
        service = PublicOverrideService(event_store=mock_event_store)

        result = await service.get_override_by_id("invalid-uuid")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_overrides_default_pagination(self) -> None:
        """Test that get_overrides uses default pagination values."""
        mock_event_store = self._create_mock_event_store()
        service = PublicOverrideService(event_store=mock_event_store)

        await service.get_overrides()

        call_kwargs = mock_event_store.get_events_filtered.call_args[1]
        assert call_kwargs["limit"] == 100  # Default limit
        assert call_kwargs["offset"] == 0  # Default offset

    @pytest.mark.asyncio
    async def test_get_overrides_count_matches_filter(self) -> None:
        """Test that count uses same filters as get_events."""
        mock_event_store = self._create_mock_event_store()
        service = PublicOverrideService(event_store=mock_event_store)

        start_date = datetime(2026, 1, 1, tzinfo=timezone.utc)
        end_date = datetime(2026, 1, 31, tzinfo=timezone.utc)

        await service.get_overrides(start_date=start_date, end_date=end_date)

        # Count should use same date filters
        count_kwargs = mock_event_store.count_events_filtered.call_args[1]
        assert count_kwargs["start_date"] == start_date
        assert count_kwargs["end_date"] == end_date
        assert count_kwargs["event_types"] == [OVERRIDE_EVENT_TYPE]
