"""Sequence gap detector stub for testing (FR18-FR19, Story 3.7).

This stub implementation of SequenceGapDetectorPort allows controlled
testing of gap detection scenarios.

Usage:
    >>> stub = SequenceGapDetectorStub()
    >>> stub.simulate_gap(expected=5, actual=10, missing=(5, 6, 7, 8, 9))
    >>> result = await stub.check_for_gaps()
    >>> assert result.gap_size == 5
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from src.application.ports.sequence_gap_detector import (
    DETECTION_INTERVAL_SECONDS,
    SequenceGapDetectorPort,
)
from src.domain.events.sequence_gap_detected import SequenceGapDetectedPayload

if TYPE_CHECKING:
    pass


class SequenceGapDetectorStub(SequenceGapDetectorPort):
    """Stub implementation for sequence gap detection testing.

    This stub allows controlled simulation of gap detection scenarios
    for testing purposes.

    Attributes:
        recorded_gaps: List of gap detections that were recorded.
        has_pending_gaps: Whether there are pending simulated gaps.

    Example:
        >>> stub = SequenceGapDetectorStub()
        >>> stub.simulate_gap(expected=5, actual=10, missing=(5, 6, 7, 8, 9))
        >>> result = await stub.check_for_gaps()
        >>> assert result.expected_sequence == 5
    """

    def __init__(
        self,
        detection_interval: int = DETECTION_INTERVAL_SECONDS,
    ) -> None:
        """Initialize the stub.

        Args:
            detection_interval: The detection interval in seconds.
        """
        self._detection_interval = detection_interval
        self._simulated_gaps: list[tuple[int, int, tuple[int, ...]]] = []
        self._last_check: Optional[datetime] = None
        self.recorded_gaps: list[SequenceGapDetectedPayload] = []

    async def check_for_gaps(self) -> Optional[SequenceGapDetectedPayload]:
        """Check for gaps and return next simulated gap if any.

        Returns:
            SequenceGapDetectedPayload if simulated gap available, None otherwise.

        Note:
            Each simulated gap is consumed after being returned (one-time use).
        """
        previous_check = self._last_check or datetime.now(timezone.utc)
        self._last_check = datetime.now(timezone.utc)

        if not self._simulated_gaps:
            return None

        expected, actual, missing = self._simulated_gaps.pop(0)
        return SequenceGapDetectedPayload(
            detection_timestamp=datetime.now(timezone.utc),
            expected_sequence=expected,
            actual_sequence=actual,
            gap_size=len(missing),
            missing_sequences=missing,
            detection_service_id="sequence_gap_detector_stub",
            previous_check_timestamp=previous_check,
        )

    async def get_last_check_timestamp(self) -> Optional[datetime]:
        """Get the timestamp of the last check.

        Returns:
            Datetime of last check, or None if never checked.
        """
        return self._last_check

    async def get_detection_interval_seconds(self) -> int:
        """Get the detection interval in seconds.

        Returns:
            The configured detection interval.
        """
        return self._detection_interval

    async def record_gap_detection(
        self,
        payload: SequenceGapDetectedPayload,
    ) -> None:
        """Record a gap detection.

        Args:
            payload: The gap detection details.
        """
        self.recorded_gaps.append(payload)

    def simulate_gap(
        self,
        expected: int,
        actual: int,
        missing: tuple[int, ...],
    ) -> None:
        """Simulate a gap for the next check.

        Args:
            expected: The expected sequence number.
            actual: The actual sequence number found.
            missing: Tuple of missing sequence numbers.

        Note:
            Multiple gaps can be queued by calling this multiple times.
        """
        self._simulated_gaps.append((expected, actual, missing))

    def clear(self) -> None:
        """Clear all state (simulated gaps, recorded gaps, timestamp)."""
        self._simulated_gaps.clear()
        self.recorded_gaps.clear()
        self._last_check = None

    @property
    def has_pending_gaps(self) -> bool:
        """Check if there are pending simulated gaps.

        Returns:
            True if there are gaps queued for check_for_gaps().
        """
        return len(self._simulated_gaps) > 0
