"""Sequence gap detector port definition (FR18-FR19, Story 3.7).

Defines the abstract interface for sequence gap detection operations.
Infrastructure adapters must implement this protocol.

Constitutional Constraints:
- FR18: Gap detection within 1 minute
- FR19: Gap triggers investigation, not auto-fill
- CT-3: Time is unreliable - sequence is authoritative ordering
- CT-11: Silent failure destroys legitimacy

Detection SLA:
- 30-second detection interval ensures gaps are detected within 1 minute
- 2 cycles (60 seconds) = maximum detection latency

Note:
    Sequence gaps may indicate:
    - Event suppression by attacker
    - Data loss or corruption
    - Replication failure
    - System failure during write

    Gaps are NEVER auto-filled. Manual investigation required.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.domain.events.sequence_gap_detected import SequenceGapDetectedPayload


# FR18-FR19: Detection interval for 1-minute SLA
# 2 cycles of 30 seconds = 1 minute maximum detection time
DETECTION_INTERVAL_SECONDS: int = 30


class SequenceGapDetectorPort(ABC):
    """Abstract protocol for sequence gap detection operations.

    All sequence gap detector implementations must implement this interface.
    This enables dependency inversion and allows the application layer
    to remain independent of specific detection implementations.

    Constitutional Constraints:
    - FR18: Gap detection within 1 minute (30-second interval)
    - FR19: Gap triggers investigation, not auto-fill
    - CT-3: Sequence is authoritative ordering
    - CT-11: Silent failure destroys legitimacy - gaps MUST be reported

    Note:
        This port defines the contract for gap detection.
        The actual detection logic uses EventStorePort.verify_sequence_continuity().
        This port handles the scheduling and state tracking of detection cycles.

    Example:
        >>> class MyGapDetector(SequenceGapDetectorPort):
        ...     async def check_for_gaps(self) -> Optional[SequenceGapDetectedPayload]:
        ...         # Check event store for gaps
        ...         return None  # No gap found
        ...
        ...     async def get_last_check_timestamp(self) -> Optional[datetime]:
        ...         return self._last_check
        ...
        ...     async def get_detection_interval_seconds(self) -> int:
        ...         return DETECTION_INTERVAL_SECONDS
        ...
        ...     async def record_gap_detection(self, payload: SequenceGapDetectedPayload) -> None:
        ...         # Record the gap for investigation
        ...         pass
    """

    @abstractmethod
    async def check_for_gaps(self) -> "SequenceGapDetectedPayload | None":
        """Check for gaps in the event sequence.

        This method checks the event store for sequence continuity
        and returns a payload if a gap is detected.

        Returns:
            SequenceGapDetectedPayload if gap found, None otherwise.

        Note:
            Detection should use EventStorePort.verify_sequence_continuity()
            which is already implemented.
        """
        ...

    @abstractmethod
    async def get_last_check_timestamp(self) -> "datetime | None":
        """Get the timestamp of the last successful gap check.

        Used for operational monitoring and SLA verification.

        Returns:
            Datetime of last check, or None if never checked.
        """
        ...

    @abstractmethod
    async def get_detection_interval_seconds(self) -> int:
        """Get the detection interval in seconds.

        Returns:
            The configured detection interval (default: 30 seconds).

        Note:
            30 seconds ensures gaps are detected within 1 minute (2 cycles).
        """
        ...

    @abstractmethod
    async def record_gap_detection(
        self,
        payload: "SequenceGapDetectedPayload",
    ) -> None:
        """Record a gap detection for tracking.

        This method records the gap detection details for
        operational tracking and investigation.

        Args:
            payload: The gap detection details.

        Note:
            This is separate from creating the witnessed event.
            The EventWriterService handles event creation.
        """
        ...
