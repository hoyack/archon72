"""Unit tests for SequenceGapDetectionService (FR18-FR19, Story 3.7).

Tests the sequence gap detection service that coordinates gap checking.

Constitutional Constraints:
- FR18: Gap detection within 1 minute
- FR19: Gap triggers investigation, not auto-fill
- CT-11: Silent failure destroys legitimacy
"""

from datetime import datetime, timezone
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from src.application.ports.event_store import EventStorePort
from src.application.ports.halt_trigger import HaltTrigger
from src.application.ports.sequence_gap_detector import DETECTION_INTERVAL_SECONDS
from src.application.services.sequence_gap_detection_service import (
    SequenceGapDetectionService,
)
from src.domain.events.sequence_gap_detected import SequenceGapDetectedPayload


class TestSequenceGapDetectionServiceCreation:
    """Tests for SequenceGapDetectionService creation."""

    def test_service_creation(self) -> None:
        """Test service can be created with required dependencies."""
        event_store = AsyncMock(spec=EventStorePort)
        service = SequenceGapDetectionService(event_store=event_store)
        assert service is not None

    def test_service_with_halt_trigger(self) -> None:
        """Test service can be created with optional halt trigger."""
        event_store = AsyncMock(spec=EventStorePort)
        halt_trigger = AsyncMock(spec=HaltTrigger)
        service = SequenceGapDetectionService(
            event_store=event_store,
            halt_trigger=halt_trigger,
            halt_on_gap=True,
        )
        assert service is not None


class TestCheckSequenceContinuity:
    """Tests for check_sequence_continuity method."""

    @pytest.fixture
    def event_store(self) -> AsyncMock:
        """Create mock event store."""
        return AsyncMock(spec=EventStorePort)

    @pytest.fixture
    def service(self, event_store: AsyncMock) -> SequenceGapDetectionService:
        """Create service with mock event store."""
        return SequenceGapDetectionService(event_store=event_store)

    @pytest.mark.asyncio
    async def test_returns_none_when_store_empty(
        self,
        service: SequenceGapDetectionService,
        event_store: AsyncMock,
    ) -> None:
        """Test returns None when event store is empty."""
        event_store.get_max_sequence.return_value = 0
        result = await service.check_sequence_continuity()
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_no_gap(
        self,
        service: SequenceGapDetectionService,
        event_store: AsyncMock,
    ) -> None:
        """Test returns None when no gap detected."""
        event_store.get_max_sequence.return_value = 10
        event_store.verify_sequence_continuity.return_value = (True, [])
        result = await service.check_sequence_continuity()
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_payload_when_gap_detected(
        self,
        service: SequenceGapDetectionService,
        event_store: AsyncMock,
    ) -> None:
        """Test returns payload when gap detected."""
        event_store.get_max_sequence.return_value = 10
        event_store.verify_sequence_continuity.return_value = (False, [5, 6, 7])
        result = await service.check_sequence_continuity()
        assert result is not None
        assert isinstance(result, SequenceGapDetectedPayload)

    @pytest.mark.asyncio
    async def test_payload_contains_expected_sequence(
        self,
        service: SequenceGapDetectionService,
        event_store: AsyncMock,
    ) -> None:
        """Test payload contains expected sequence (first missing)."""
        event_store.get_max_sequence.return_value = 10
        event_store.verify_sequence_continuity.return_value = (False, [5, 6, 7])
        result = await service.check_sequence_continuity()
        assert result is not None
        assert result.expected_sequence == 5

    @pytest.mark.asyncio
    async def test_payload_contains_actual_sequence(
        self,
        service: SequenceGapDetectionService,
        event_store: AsyncMock,
    ) -> None:
        """Test payload contains actual sequence (max)."""
        event_store.get_max_sequence.return_value = 10
        event_store.verify_sequence_continuity.return_value = (False, [5, 6, 7])
        result = await service.check_sequence_continuity()
        assert result is not None
        assert result.actual_sequence == 10

    @pytest.mark.asyncio
    async def test_payload_contains_gap_size(
        self,
        service: SequenceGapDetectionService,
        event_store: AsyncMock,
    ) -> None:
        """Test payload contains gap size."""
        event_store.get_max_sequence.return_value = 10
        event_store.verify_sequence_continuity.return_value = (False, [5, 6, 7])
        result = await service.check_sequence_continuity()
        assert result is not None
        assert result.gap_size == 3

    @pytest.mark.asyncio
    async def test_payload_contains_missing_sequences(
        self,
        service: SequenceGapDetectionService,
        event_store: AsyncMock,
    ) -> None:
        """Test payload contains missing sequences."""
        event_store.get_max_sequence.return_value = 10
        event_store.verify_sequence_continuity.return_value = (False, [5, 6, 7])
        result = await service.check_sequence_continuity()
        assert result is not None
        assert result.missing_sequences == (5, 6, 7)

    @pytest.mark.asyncio
    async def test_updates_last_checked_sequence(
        self,
        service: SequenceGapDetectionService,
        event_store: AsyncMock,
    ) -> None:
        """Test service tracks last checked sequence."""
        event_store.get_max_sequence.return_value = 10
        event_store.verify_sequence_continuity.return_value = (True, [])
        await service.check_sequence_continuity()
        # Second call should check from 11
        event_store.get_max_sequence.return_value = 15
        await service.check_sequence_continuity()
        # Verify the range checked
        calls = event_store.verify_sequence_continuity.call_args_list
        assert len(calls) == 2
        # First call: 1 to 10
        assert calls[0].kwargs["start"] == 1
        assert calls[0].kwargs["end"] == 10
        # Second call: 11 to 15
        assert calls[1].kwargs["start"] == 11
        assert calls[1].kwargs["end"] == 15

    @pytest.mark.asyncio
    async def test_returns_none_when_already_checked(
        self,
        service: SequenceGapDetectionService,
        event_store: AsyncMock,
    ) -> None:
        """Test returns None when already checked up to max."""
        event_store.get_max_sequence.return_value = 10
        event_store.verify_sequence_continuity.return_value = (True, [])
        await service.check_sequence_continuity()
        # No new events - should return None without checking
        result = await service.check_sequence_continuity()
        assert result is None
        # verify_sequence_continuity should only be called once
        assert event_store.verify_sequence_continuity.call_count == 1


class TestHandleGapDetected:
    """Tests for handle_gap_detected method."""

    @pytest.fixture
    def sample_payload(self) -> SequenceGapDetectedPayload:
        """Create sample gap payload."""
        return SequenceGapDetectedPayload(
            detection_timestamp=datetime.now(timezone.utc),
            expected_sequence=5,
            actual_sequence=10,
            gap_size=5,
            missing_sequences=(5, 6, 7, 8, 9),
            detection_service_id="sequence_gap_detector",
            previous_check_timestamp=datetime.now(timezone.utc),
        )

    @pytest.mark.asyncio
    async def test_logs_warning_on_gap(
        self,
        sample_payload: SequenceGapDetectedPayload,
    ) -> None:
        """Test logs warning when gap detected."""
        event_store = AsyncMock(spec=EventStorePort)
        service = SequenceGapDetectionService(event_store=event_store)
        with patch.object(service, "_log") as mock_log:
            await service.handle_gap_detected(sample_payload)
            mock_log.warning.assert_called_once()
            call_args = mock_log.warning.call_args
            assert call_args.args[0] == "sequence_gap_detected"

    @pytest.mark.asyncio
    async def test_does_not_halt_by_default(
        self,
        sample_payload: SequenceGapDetectedPayload,
    ) -> None:
        """Test does not trigger halt when halt_on_gap=False (default)."""
        event_store = AsyncMock(spec=EventStorePort)
        halt_trigger = AsyncMock(spec=HaltTrigger)
        service = SequenceGapDetectionService(
            event_store=event_store,
            halt_trigger=halt_trigger,
            halt_on_gap=False,
        )
        await service.handle_gap_detected(sample_payload)
        halt_trigger.trigger_halt.assert_not_called()

    @pytest.mark.asyncio
    async def test_triggers_halt_when_configured(
        self,
        sample_payload: SequenceGapDetectedPayload,
    ) -> None:
        """Test triggers halt when halt_on_gap=True."""
        event_store = AsyncMock(spec=EventStorePort)
        halt_trigger = AsyncMock(spec=HaltTrigger)
        service = SequenceGapDetectionService(
            event_store=event_store,
            halt_trigger=halt_trigger,
            halt_on_gap=True,
        )
        await service.handle_gap_detected(sample_payload)
        halt_trigger.trigger_halt.assert_called_once()


class TestRunDetectionCycle:
    """Tests for run_detection_cycle method."""

    @pytest.mark.asyncio
    async def test_runs_check_and_handles_gap(self) -> None:
        """Test run_detection_cycle checks and handles gap."""
        event_store = AsyncMock(spec=EventStorePort)
        event_store.get_max_sequence.return_value = 10
        event_store.verify_sequence_continuity.return_value = (False, [5, 6, 7])

        service = SequenceGapDetectionService(event_store=event_store)

        with patch.object(service, "handle_gap_detected", new_callable=AsyncMock) as mock_handle:
            await service.run_detection_cycle()
            mock_handle.assert_called_once()
            # Verify payload was passed
            call_args = mock_handle.call_args
            payload = call_args.args[0]
            assert isinstance(payload, SequenceGapDetectedPayload)
            assert payload.gap_size == 3

    @pytest.mark.asyncio
    async def test_runs_check_without_gap(self) -> None:
        """Test run_detection_cycle works when no gap."""
        event_store = AsyncMock(spec=EventStorePort)
        event_store.get_max_sequence.return_value = 10
        event_store.verify_sequence_continuity.return_value = (True, [])

        service = SequenceGapDetectionService(event_store=event_store)

        with patch.object(service, "handle_gap_detected", new_callable=AsyncMock) as mock_handle:
            await service.run_detection_cycle()
            mock_handle.assert_not_called()


class TestServiceAttributes:
    """Tests for service attributes."""

    def test_detection_interval_constant(self) -> None:
        """Test detection interval is 30 seconds."""
        event_store = AsyncMock(spec=EventStorePort)
        service = SequenceGapDetectionService(event_store=event_store)
        assert service.detection_interval == DETECTION_INTERVAL_SECONDS
        assert service.detection_interval == 30

    def test_service_id(self) -> None:
        """Test service has correct ID."""
        event_store = AsyncMock(spec=EventStorePort)
        service = SequenceGapDetectionService(event_store=event_store)
        assert service.service_id == "sequence_gap_detector"
