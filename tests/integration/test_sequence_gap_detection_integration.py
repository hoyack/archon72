"""Integration tests for sequence gap detection (FR18-FR19, Story 3.7).

Tests the complete sequence gap detection flow from detection through
event creation and optional halt triggering.

Constitutional Constraints:
- FR18: Gap detection within 1 minute
- FR19: Gap triggers investigation, not auto-fill
- CT-11: Silent failure destroys legitimacy
"""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from src.application.ports.event_store import EventStorePort
from src.application.ports.halt_trigger import HaltTrigger
from src.application.ports.sequence_gap_detector import DETECTION_INTERVAL_SECONDS
from src.application.services.sequence_gap_detection_service import (
    SequenceGapDetectionService,
)
from src.application.services.sequence_gap_monitor import SequenceGapMonitor
from src.domain.events.constitutional_crisis import (
    ConstitutionalCrisisPayload,
    CrisisType,
)
from src.domain.events.sequence_gap_detected import (
    SequenceGapDetectedPayload,
)
from src.infrastructure.stubs.sequence_gap_detector_stub import SequenceGapDetectorStub


class TestSequenceGapDetectionIntegration:
    """Integration tests for sequence gap detection flow."""

    @pytest.fixture
    def mock_event_store(self) -> AsyncMock:
        """Create mock event store."""
        store = AsyncMock(spec=EventStorePort)
        store.get_max_sequence.return_value = 0
        store.verify_sequence_continuity.return_value = (True, [])
        return store

    @pytest.fixture
    def mock_halt_trigger(self) -> AsyncMock:
        """Create mock halt trigger."""
        return AsyncMock(spec=HaltTrigger)

    @pytest.fixture
    def detection_service(
        self,
        mock_event_store: AsyncMock,
        mock_halt_trigger: AsyncMock,
    ) -> SequenceGapDetectionService:
        """Create detection service with mocks."""
        return SequenceGapDetectionService(
            event_store=mock_event_store,
            halt_trigger=mock_halt_trigger,
            halt_on_gap=False,
        )


class TestGapDetectionFlow:
    """Tests for the complete gap detection flow."""

    @pytest.mark.asyncio
    async def test_no_gap_produces_no_event(self) -> None:
        """Test continuous sequence produces no events."""
        event_store = AsyncMock(spec=EventStorePort)
        event_store.get_max_sequence.return_value = 10
        event_store.verify_sequence_continuity.return_value = (True, [])

        service = SequenceGapDetectionService(event_store=event_store)
        result = await service.check_sequence_continuity()

        assert result is None

    @pytest.mark.asyncio
    async def test_gap_creates_payload_with_correct_fields(self) -> None:
        """Test gap detection creates SequenceGapDetectedPayload with all fields."""
        event_store = AsyncMock(spec=EventStorePort)
        event_store.get_max_sequence.return_value = 10
        event_store.verify_sequence_continuity.return_value = (False, [5, 6, 7])

        service = SequenceGapDetectionService(event_store=event_store)
        result = await service.check_sequence_continuity()

        assert result is not None
        assert result.expected_sequence == 5
        assert result.actual_sequence == 10
        assert result.gap_size == 3
        assert result.missing_sequences == (5, 6, 7)
        assert result.detection_service_id == "sequence_gap_detector"
        assert isinstance(result.detection_timestamp, datetime)
        assert result.detection_timestamp.tzinfo == timezone.utc

    @pytest.mark.asyncio
    async def test_multiple_gaps_detected_in_single_check(self) -> None:
        """Test multiple gaps are all captured in single check."""
        event_store = AsyncMock(spec=EventStorePort)
        event_store.get_max_sequence.return_value = 20
        # Multiple non-contiguous gaps
        event_store.verify_sequence_continuity.return_value = (
            False,
            [5, 6, 10, 11, 12],
        )

        service = SequenceGapDetectionService(event_store=event_store)
        result = await service.check_sequence_continuity()

        assert result is not None
        assert result.gap_size == 5
        assert result.missing_sequences == (5, 6, 10, 11, 12)


class TestGapDetectionWithHaltTrigger:
    """Tests for gap detection with halt trigger integration."""

    @pytest.mark.asyncio
    async def test_gap_triggers_halt_when_configured(self) -> None:
        """Test gap detection can trigger ConstitutionalCrisisEvent."""
        event_store = AsyncMock(spec=EventStorePort)
        event_store.get_max_sequence.return_value = 10
        event_store.verify_sequence_continuity.return_value = (False, [5, 6, 7])

        halt_trigger = AsyncMock(spec=HaltTrigger)

        service = SequenceGapDetectionService(
            event_store=event_store,
            halt_trigger=halt_trigger,
            halt_on_gap=True,  # Enable halt on gap
        )

        result = await service.check_sequence_continuity()
        assert result is not None
        await service.handle_gap_detected(result)

        # Verify halt was triggered
        halt_trigger.trigger_halt.assert_called_once()
        call_args = halt_trigger.trigger_halt.call_args
        crisis = call_args.args[0]

        assert isinstance(crisis, ConstitutionalCrisisPayload)
        assert crisis.crisis_type == CrisisType.SEQUENCE_GAP_DETECTED
        assert "FR18-FR19" in crisis.detection_details
        assert "(5, 6, 7)" in crisis.detection_details

    @pytest.mark.asyncio
    async def test_gap_does_not_trigger_halt_by_default(self) -> None:
        """Test gap detection does NOT trigger halt when not configured."""
        event_store = AsyncMock(spec=EventStorePort)
        event_store.get_max_sequence.return_value = 10
        event_store.verify_sequence_continuity.return_value = (False, [5, 6, 7])

        halt_trigger = AsyncMock(spec=HaltTrigger)

        service = SequenceGapDetectionService(
            event_store=event_store,
            halt_trigger=halt_trigger,
            halt_on_gap=False,  # Disabled by default
        )

        result = await service.check_sequence_continuity()
        await service.handle_gap_detected(result)

        # Verify halt was NOT triggered
        halt_trigger.trigger_halt.assert_not_called()


class TestDetectionTimingSLA:
    """Tests for detection timing SLA (FR18 - 1 minute)."""

    def test_detection_interval_is_30_seconds(self) -> None:
        """Test detection interval is 30 seconds for 1-minute SLA."""
        assert DETECTION_INTERVAL_SECONDS == 30

    @pytest.mark.asyncio
    async def test_monitor_runs_at_configured_interval(self) -> None:
        """Test monitor runs detection at configured interval."""
        event_store = AsyncMock(spec=EventStorePort)
        event_store.get_max_sequence.return_value = 10
        event_store.verify_sequence_continuity.return_value = (True, [])

        service = SequenceGapDetectionService(event_store=event_store)
        monitor = SequenceGapMonitor(
            detection_service=service,
            interval_seconds=30,  # Use actual interval
        )

        # Verify configured interval
        assert monitor.interval_seconds == 30

    @pytest.mark.asyncio
    async def test_detection_latency_acceptable(self) -> None:
        """Test detection latency is acceptable for SLA."""
        event_store = AsyncMock(spec=EventStorePort)
        event_store.get_max_sequence.return_value = 10
        event_store.verify_sequence_continuity.return_value = (True, [])

        service = SequenceGapDetectionService(event_store=event_store)

        start = datetime.now(timezone.utc)
        await service.check_sequence_continuity()
        elapsed = (datetime.now(timezone.utc) - start).total_seconds()

        # Single check should be very fast (< 1 second)
        assert elapsed < 1.0


class TestManualResolutionRequired:
    """Tests for manual resolution requirement (FR19)."""

    @pytest.mark.asyncio
    async def test_gap_not_auto_filled(self) -> None:
        """Test gaps are NOT auto-filled (manual resolution required)."""
        event_store = AsyncMock(spec=EventStorePort)
        event_store.get_max_sequence.return_value = 10
        event_store.verify_sequence_continuity.return_value = (False, [5, 6, 7])

        service = SequenceGapDetectionService(event_store=event_store)

        # Check and handle gap
        result = await service.check_sequence_continuity()
        await service.handle_gap_detected(result)

        # Verify no events were inserted to fill the gap
        # (event_store.append should NOT have been called)
        assert not hasattr(event_store, "append") or not event_store.append.called

    @pytest.mark.asyncio
    async def test_gap_detection_creates_audit_trail(self) -> None:
        """Test gap detection creates audit trail (payload for event)."""
        event_store = AsyncMock(spec=EventStorePort)
        event_store.get_max_sequence.return_value = 10
        event_store.verify_sequence_continuity.return_value = (False, [5, 6, 7])

        service = SequenceGapDetectionService(event_store=event_store)
        result = await service.check_sequence_continuity()

        # Verify payload can create signable content for witnessing
        signable = result.signable_content()
        assert isinstance(signable, bytes)
        assert len(signable) > 0
        assert b"expected:5" in signable
        assert b"actual:10" in signable


class TestStubIntegration:
    """Tests using SequenceGapDetectorStub for controlled testing."""

    @pytest.mark.asyncio
    async def test_stub_simulates_gap(self) -> None:
        """Test stub can simulate gap detection."""
        stub = SequenceGapDetectorStub()
        stub.simulate_gap(expected=5, actual=10, missing=(5, 6, 7, 8, 9))

        result = await stub.check_for_gaps()

        assert result is not None
        assert result.expected_sequence == 5
        assert result.actual_sequence == 10
        assert result.gap_size == 5

    @pytest.mark.asyncio
    async def test_stub_records_detections(self) -> None:
        """Test stub records gap detections."""
        stub = SequenceGapDetectorStub()

        payload = SequenceGapDetectedPayload(
            detection_timestamp=datetime.now(timezone.utc),
            expected_sequence=5,
            actual_sequence=10,
            gap_size=5,
            missing_sequences=(5, 6, 7, 8, 9),
            detection_service_id="test",
            previous_check_timestamp=datetime.now(timezone.utc),
        )

        await stub.record_gap_detection(payload)

        assert len(stub.recorded_gaps) == 1
        assert stub.recorded_gaps[0] == payload


class TestMonitorIntegration:
    """Tests for SequenceGapMonitor integration."""

    @pytest.mark.asyncio
    async def test_monitor_full_cycle(self) -> None:
        """Test monitor runs full detection cycle."""
        event_store = AsyncMock(spec=EventStorePort)
        event_store.get_max_sequence.return_value = 10
        event_store.verify_sequence_continuity.return_value = (False, [5, 6, 7])

        service = SequenceGapDetectionService(event_store=event_store)
        monitor = SequenceGapMonitor(detection_service=service)

        # Run single cycle
        result = await monitor.run_once()

        assert result is not None
        assert result.gap_size == 3

    @pytest.mark.asyncio
    async def test_monitor_start_stop_cycle(self) -> None:
        """Test monitor can be started and stopped."""
        event_store = AsyncMock(spec=EventStorePort)
        event_store.get_max_sequence.return_value = 10
        event_store.verify_sequence_continuity.return_value = (True, [])

        service = SequenceGapDetectionService(event_store=event_store)
        monitor = SequenceGapMonitor(detection_service=service)

        # Override interval for fast testing
        monitor._interval = 0.01

        assert not monitor.running

        await monitor.start()
        assert monitor.running

        await asyncio.sleep(0.03)  # Let it run a few cycles

        await monitor.stop()
        assert not monitor.running
