"""Unit tests for SequenceGapDetectorStub (FR18-FR19, Story 3.7).

Tests the stub implementation for sequence gap detection testing.
"""

from datetime import datetime, timezone

import pytest

from src.application.ports.sequence_gap_detector import (
    DETECTION_INTERVAL_SECONDS,
    SequenceGapDetectorPort,
)
from src.domain.events.sequence_gap_detected import SequenceGapDetectedPayload
from src.infrastructure.stubs.sequence_gap_detector_stub import SequenceGapDetectorStub


class TestSequenceGapDetectorStubInterface:
    """Tests for SequenceGapDetectorStub interface compliance."""

    def test_implements_port(self) -> None:
        """Test stub implements SequenceGapDetectorPort."""
        stub = SequenceGapDetectorStub()
        assert isinstance(stub, SequenceGapDetectorPort)


class TestSequenceGapDetectorStubCheckForGaps:
    """Tests for check_for_gaps method."""

    @pytest.mark.asyncio
    async def test_returns_none_by_default(self) -> None:
        """Test returns None when no gaps configured."""
        stub = SequenceGapDetectorStub()
        result = await stub.check_for_gaps()
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_configured_gap(self) -> None:
        """Test returns configured gap payload."""
        stub = SequenceGapDetectorStub()
        stub.simulate_gap(expected=5, actual=10, missing=(5, 6, 7, 8, 9))

        result = await stub.check_for_gaps()
        assert result is not None
        assert isinstance(result, SequenceGapDetectedPayload)
        assert result.expected_sequence == 5
        assert result.actual_sequence == 10
        assert result.missing_sequences == (5, 6, 7, 8, 9)

    @pytest.mark.asyncio
    async def test_gap_consumed_after_check(self) -> None:
        """Test gap is consumed after check (one-time use)."""
        stub = SequenceGapDetectorStub()
        stub.simulate_gap(expected=5, actual=10, missing=(5, 6, 7, 8, 9))

        result1 = await stub.check_for_gaps()
        assert result1 is not None

        result2 = await stub.check_for_gaps()
        assert result2 is None

    @pytest.mark.asyncio
    async def test_multiple_gaps_queued(self) -> None:
        """Test multiple gaps can be queued."""
        stub = SequenceGapDetectorStub()
        stub.simulate_gap(expected=5, actual=10, missing=(5, 6, 7, 8, 9))
        stub.simulate_gap(expected=15, actual=20, missing=(15, 16, 17, 18, 19))

        result1 = await stub.check_for_gaps()
        assert result1 is not None
        assert result1.expected_sequence == 5

        result2 = await stub.check_for_gaps()
        assert result2 is not None
        assert result2.expected_sequence == 15

        result3 = await stub.check_for_gaps()
        assert result3 is None


class TestSequenceGapDetectorStubTimestamps:
    """Tests for timestamp methods."""

    @pytest.mark.asyncio
    async def test_get_last_check_timestamp_none_initially(self) -> None:
        """Test returns None when never checked."""
        stub = SequenceGapDetectorStub()
        result = await stub.get_last_check_timestamp()
        assert result is None

    @pytest.mark.asyncio
    async def test_get_last_check_timestamp_after_check(self) -> None:
        """Test returns timestamp after check."""
        stub = SequenceGapDetectorStub()
        await stub.check_for_gaps()

        result = await stub.get_last_check_timestamp()
        assert result is not None
        assert isinstance(result, datetime)
        assert result.tzinfo == timezone.utc


class TestSequenceGapDetectorStubDetectionInterval:
    """Tests for detection interval."""

    @pytest.mark.asyncio
    async def test_default_interval(self) -> None:
        """Test default interval is 30 seconds."""
        stub = SequenceGapDetectorStub()
        result = await stub.get_detection_interval_seconds()
        assert result == DETECTION_INTERVAL_SECONDS
        assert result == 30

    @pytest.mark.asyncio
    async def test_custom_interval(self) -> None:
        """Test custom interval can be configured."""
        stub = SequenceGapDetectorStub(detection_interval=60)
        result = await stub.get_detection_interval_seconds()
        assert result == 60


class TestSequenceGapDetectorStubRecordGapDetection:
    """Tests for record_gap_detection method."""

    @pytest.mark.asyncio
    async def test_records_gap_detection(self) -> None:
        """Test gap detection is recorded."""
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

    @pytest.mark.asyncio
    async def test_records_multiple_detections(self) -> None:
        """Test multiple detections are recorded."""
        stub = SequenceGapDetectorStub()

        for i in range(3):
            payload = SequenceGapDetectedPayload(
                detection_timestamp=datetime.now(timezone.utc),
                expected_sequence=i * 5,
                actual_sequence=i * 5 + 5,
                gap_size=5,
                missing_sequences=tuple(range(i * 5, i * 5 + 5)),
                detection_service_id="test",
                previous_check_timestamp=datetime.now(timezone.utc),
            )
            await stub.record_gap_detection(payload)

        assert len(stub.recorded_gaps) == 3


class TestSequenceGapDetectorStubHelpers:
    """Tests for stub helper methods."""

    def test_clear_resets_state(self) -> None:
        """Test clear resets all state."""
        stub = SequenceGapDetectorStub()
        stub.simulate_gap(expected=5, actual=10, missing=(5, 6, 7, 8, 9))

        stub.clear()

        assert len(stub._simulated_gaps) == 0
        assert len(stub.recorded_gaps) == 0
        assert stub._last_check is None

    def test_has_pending_gaps(self) -> None:
        """Test has_pending_gaps property."""
        stub = SequenceGapDetectorStub()
        assert not stub.has_pending_gaps

        stub.simulate_gap(expected=5, actual=10, missing=(5, 6, 7, 8, 9))
        assert stub.has_pending_gaps
