"""Unit tests for SequenceGapDetectorPort (FR18-FR19, Story 3.7).

Tests the abstract port for sequence gap detection.

Constitutional Constraints:
- FR18: Gap detection within 1 minute
- FR19: Gap triggers investigation, not auto-fill
"""

from abc import ABC
from datetime import datetime
from typing import Optional

import pytest

from src.application.ports.sequence_gap_detector import (
    DETECTION_INTERVAL_SECONDS,
    SequenceGapDetectorPort,
)
from src.domain.events.sequence_gap_detected import SequenceGapDetectedPayload


class TestSequenceGapDetectorPortInterface:
    """Tests for SequenceGapDetectorPort interface definition."""

    def test_port_is_abstract(self) -> None:
        """Test port is an abstract base class."""
        assert issubclass(SequenceGapDetectorPort, ABC)

    def test_cannot_instantiate_directly(self) -> None:
        """Test port cannot be instantiated directly."""
        with pytest.raises(TypeError):
            SequenceGapDetectorPort()  # type: ignore

    def test_has_check_for_gaps_method(self) -> None:
        """Test port defines check_for_gaps method."""
        assert hasattr(SequenceGapDetectorPort, "check_for_gaps")
        # Verify it's async
        import inspect
        assert inspect.iscoroutinefunction(SequenceGapDetectorPort.check_for_gaps)

    def test_has_get_last_check_timestamp_method(self) -> None:
        """Test port defines get_last_check_timestamp method."""
        assert hasattr(SequenceGapDetectorPort, "get_last_check_timestamp")
        import inspect
        assert inspect.iscoroutinefunction(SequenceGapDetectorPort.get_last_check_timestamp)

    def test_has_get_detection_interval_seconds_method(self) -> None:
        """Test port defines get_detection_interval_seconds method."""
        assert hasattr(SequenceGapDetectorPort, "get_detection_interval_seconds")
        import inspect
        assert inspect.iscoroutinefunction(SequenceGapDetectorPort.get_detection_interval_seconds)

    def test_has_record_gap_detection_method(self) -> None:
        """Test port defines record_gap_detection method."""
        assert hasattr(SequenceGapDetectorPort, "record_gap_detection")
        import inspect
        assert inspect.iscoroutinefunction(SequenceGapDetectorPort.record_gap_detection)


class TestDetectionIntervalConstant:
    """Tests for detection interval constant."""

    def test_detection_interval_is_30_seconds(self) -> None:
        """Test detection interval is 30 seconds (FR18 - 1 minute SLA / 2 cycles)."""
        assert DETECTION_INTERVAL_SECONDS == 30

    def test_detection_interval_is_integer(self) -> None:
        """Test detection interval is an integer."""
        assert isinstance(DETECTION_INTERVAL_SECONDS, int)


class TestSequenceGapDetectorPortDocstrings:
    """Tests for port docstrings containing FR references."""

    def test_module_docstring_references_fr18(self) -> None:
        """Test module docstring references FR18."""
        import src.application.ports.sequence_gap_detector as module
        assert module.__doc__ is not None
        assert "FR18" in module.__doc__

    def test_module_docstring_references_fr19(self) -> None:
        """Test module docstring references FR19."""
        import src.application.ports.sequence_gap_detector as module
        assert module.__doc__ is not None
        assert "FR19" in module.__doc__

    def test_port_class_has_docstring(self) -> None:
        """Test port class has a docstring."""
        assert SequenceGapDetectorPort.__doc__ is not None
        assert len(SequenceGapDetectorPort.__doc__) > 50


class ConcreteGapDetector(SequenceGapDetectorPort):
    """Concrete implementation for testing."""

    async def check_for_gaps(self) -> Optional[SequenceGapDetectedPayload]:
        return None

    async def get_last_check_timestamp(self) -> Optional[datetime]:
        return None

    async def get_detection_interval_seconds(self) -> int:
        return DETECTION_INTERVAL_SECONDS

    async def record_gap_detection(self, payload: SequenceGapDetectedPayload) -> None:
        pass


class TestConcreteImplementation:
    """Tests for concrete implementation of port."""

    @pytest.mark.asyncio
    async def test_can_implement_port(self) -> None:
        """Test port can be properly implemented."""
        detector = ConcreteGapDetector()
        assert isinstance(detector, SequenceGapDetectorPort)

    @pytest.mark.asyncio
    async def test_check_for_gaps_can_return_none(self) -> None:
        """Test check_for_gaps can return None when no gap."""
        detector = ConcreteGapDetector()
        result = await detector.check_for_gaps()
        assert result is None

    @pytest.mark.asyncio
    async def test_get_detection_interval_returns_integer(self) -> None:
        """Test get_detection_interval_seconds returns integer."""
        detector = ConcreteGapDetector()
        result = await detector.get_detection_interval_seconds()
        assert isinstance(result, int)
        assert result == 30
