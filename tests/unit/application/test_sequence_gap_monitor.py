"""Unit tests for SequenceGapMonitor (FR18-FR19, Story 3.7).

Tests the background monitoring service for sequence gap detection.

Constitutional Constraints:
- FR18: Gap detection within 1 minute (30-second intervals)
- FR19: Gap triggers investigation, not auto-fill
"""

import asyncio
from datetime import datetime, timezone
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.application.ports.sequence_gap_detector import DETECTION_INTERVAL_SECONDS
from src.application.services.sequence_gap_detection_service import (
    SequenceGapDetectionService,
)
from src.application.services.sequence_gap_monitor import SequenceGapMonitor
from src.domain.events.sequence_gap_detected import SequenceGapDetectedPayload


class TestSequenceGapMonitorCreation:
    """Tests for SequenceGapMonitor creation."""

    def test_monitor_creation(self) -> None:
        """Test monitor can be created with detection service."""
        detection_service = MagicMock(spec=SequenceGapDetectionService)
        monitor = SequenceGapMonitor(detection_service=detection_service)
        assert monitor is not None

    def test_monitor_with_custom_interval(self) -> None:
        """Test monitor can be created with custom interval."""
        detection_service = MagicMock(spec=SequenceGapDetectionService)
        monitor = SequenceGapMonitor(
            detection_service=detection_service,
            interval_seconds=60,
        )
        assert monitor.interval_seconds == 60


class TestSequenceGapMonitorAttributes:
    """Tests for SequenceGapMonitor attributes."""

    def test_default_interval(self) -> None:
        """Test default interval is 30 seconds."""
        detection_service = MagicMock(spec=SequenceGapDetectionService)
        monitor = SequenceGapMonitor(detection_service=detection_service)
        assert monitor.interval_seconds == DETECTION_INTERVAL_SECONDS
        assert monitor.interval_seconds == 30

    def test_running_is_false_initially(self) -> None:
        """Test running is False initially."""
        detection_service = MagicMock(spec=SequenceGapDetectionService)
        monitor = SequenceGapMonitor(detection_service=detection_service)
        assert not monitor.running


class TestSequenceGapMonitorStartStop:
    """Tests for start and stop methods."""

    @pytest.mark.asyncio
    async def test_start_sets_running(self) -> None:
        """Test start sets running to True."""
        detection_service = MagicMock(spec=SequenceGapDetectionService)
        detection_service.check_sequence_continuity = AsyncMock(return_value=None)

        monitor = SequenceGapMonitor(detection_service=detection_service)

        # Start with very short interval for testing
        monitor._interval = 0.01  # 10ms for testing

        await monitor.start()
        assert monitor.running

        # Let it run briefly
        await asyncio.sleep(0.02)

        await monitor.stop()
        assert not monitor.running

    @pytest.mark.asyncio
    async def test_stop_cancels_task(self) -> None:
        """Test stop cancels the background task."""
        detection_service = MagicMock(spec=SequenceGapDetectionService)
        detection_service.check_sequence_continuity = AsyncMock(return_value=None)

        monitor = SequenceGapMonitor(detection_service=detection_service)
        monitor._interval = 0.01

        await monitor.start()
        await asyncio.sleep(0.02)
        await monitor.stop()

        # Task should be cancelled
        assert monitor._task is None or monitor._task.cancelled() or monitor._task.done()

    @pytest.mark.asyncio
    async def test_start_is_idempotent(self) -> None:
        """Test calling start twice is safe."""
        detection_service = MagicMock(spec=SequenceGapDetectionService)
        detection_service.check_sequence_continuity = AsyncMock(return_value=None)

        monitor = SequenceGapMonitor(detection_service=detection_service)
        monitor._interval = 0.01

        await monitor.start()
        await monitor.start()  # Should be safe
        assert monitor.running

        await monitor.stop()


class TestSequenceGapMonitorRunOnce:
    """Tests for run_once method."""

    @pytest.mark.asyncio
    async def test_run_once_returns_none_when_no_gap(self) -> None:
        """Test run_once returns None when no gap."""
        detection_service = MagicMock(spec=SequenceGapDetectionService)
        detection_service.check_sequence_continuity = AsyncMock(return_value=None)
        detection_service.handle_gap_detected = AsyncMock()

        monitor = SequenceGapMonitor(detection_service=detection_service)
        result = await monitor.run_once()

        assert result is None
        detection_service.check_sequence_continuity.assert_called_once()
        detection_service.handle_gap_detected.assert_not_called()

    @pytest.mark.asyncio
    async def test_run_once_returns_payload_when_gap(self) -> None:
        """Test run_once returns payload when gap detected."""
        detection_service = MagicMock(spec=SequenceGapDetectionService)
        gap_payload = SequenceGapDetectedPayload(
            detection_timestamp=datetime.now(timezone.utc),
            expected_sequence=5,
            actual_sequence=10,
            gap_size=5,
            missing_sequences=(5, 6, 7, 8, 9),
            detection_service_id="test",
            previous_check_timestamp=datetime.now(timezone.utc),
        )
        detection_service.check_sequence_continuity = AsyncMock(return_value=gap_payload)
        detection_service.handle_gap_detected = AsyncMock()

        monitor = SequenceGapMonitor(detection_service=detection_service)
        result = await monitor.run_once()

        assert result is not None
        assert result == gap_payload
        detection_service.check_sequence_continuity.assert_called_once()
        detection_service.handle_gap_detected.assert_called_once_with(gap_payload)


class TestSequenceGapMonitorLoop:
    """Tests for internal monitoring loop."""

    @pytest.mark.asyncio
    async def test_loop_calls_check_periodically(self) -> None:
        """Test loop calls check_sequence_continuity periodically."""
        detection_service = MagicMock(spec=SequenceGapDetectionService)
        detection_service.check_sequence_continuity = AsyncMock(return_value=None)
        detection_service.handle_gap_detected = AsyncMock()

        monitor = SequenceGapMonitor(detection_service=detection_service)
        monitor._interval = 0.01  # 10ms for testing

        await monitor.start()
        await asyncio.sleep(0.05)  # Let it run a few cycles
        await monitor.stop()

        # Should have been called multiple times
        assert detection_service.check_sequence_continuity.call_count >= 2

    @pytest.mark.asyncio
    async def test_loop_handles_gap(self) -> None:
        """Test loop handles detected gaps."""
        detection_service = MagicMock(spec=SequenceGapDetectionService)
        gap_payload = SequenceGapDetectedPayload(
            detection_timestamp=datetime.now(timezone.utc),
            expected_sequence=5,
            actual_sequence=10,
            gap_size=5,
            missing_sequences=(5, 6, 7, 8, 9),
            detection_service_id="test",
            previous_check_timestamp=datetime.now(timezone.utc),
        )
        # Return gap once, then None
        detection_service.check_sequence_continuity = AsyncMock(
            side_effect=[gap_payload, None, None, None]
        )
        detection_service.handle_gap_detected = AsyncMock()

        monitor = SequenceGapMonitor(detection_service=detection_service)
        monitor._interval = 0.01

        await monitor.start()
        await asyncio.sleep(0.05)
        await monitor.stop()

        # Should have handled the gap
        detection_service.handle_gap_detected.assert_called_once()

    @pytest.mark.asyncio
    async def test_loop_continues_after_exception(self) -> None:
        """Test loop continues after exception."""
        detection_service = MagicMock(spec=SequenceGapDetectionService)
        detection_service.check_sequence_continuity = AsyncMock(
            side_effect=[Exception("Test error"), None, None]
        )
        detection_service.handle_gap_detected = AsyncMock()

        monitor = SequenceGapMonitor(detection_service=detection_service)
        monitor._interval = 0.01

        await monitor.start()
        await asyncio.sleep(0.05)
        await monitor.stop()

        # Should have continued after exception
        assert detection_service.check_sequence_continuity.call_count >= 2
