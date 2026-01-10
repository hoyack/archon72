"""Sequence gap detection service (FR18-FR19, Story 3.7).

This service coordinates sequence gap detection by periodically
checking the event store for missing sequences.

Constitutional Constraints:
- FR18: Gap detection within 1 minute
- FR19: Gap triggers investigation, not auto-fill
- CT-3: Time is unreliable - sequence is authoritative ordering
- CT-11: Silent failure destroys legitimacy

Detection SLA:
- 30-second detection interval ensures gaps are detected within 1 minute
- 2 cycles (60 seconds) = maximum detection latency

Note:
    This service coordinates gap detection but does NOT run the
    background loop. Use SequenceGapMonitor for background monitoring.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

import structlog

from src.application.ports.sequence_gap_detector import DETECTION_INTERVAL_SECONDS
from src.domain.events.constitutional_crisis import (
    ConstitutionalCrisisPayload,
    CrisisType,
)
from src.domain.events.sequence_gap_detected import SequenceGapDetectedPayload

if TYPE_CHECKING:
    from src.application.ports.event_store import EventStorePort
    from src.application.ports.halt_trigger import HaltTrigger


class SequenceGapDetectionService:
    """Sequence gap detection service (FR18-FR19).

    Periodically checks event store for sequence gaps.
    Gaps may indicate tampering, data loss, or system failure.

    Constitutional Constraints:
    - FR18: Detect gaps within 1 minute
    - FR19: Trigger investigation, no auto-fill
    - CT-11: Silent failure destroys legitimacy

    Attributes:
        detection_interval: The detection interval in seconds (30).
        service_id: The service identifier for logging.

    Example:
        >>> service = SequenceGapDetectionService(
        ...     event_store=event_store,
        ...     halt_trigger=halt_trigger,
        ...     halt_on_gap=True,
        ... )
        >>> gap = await service.check_sequence_continuity()
        >>> if gap:
        ...     await service.handle_gap_detected(gap)
    """

    def __init__(
        self,
        event_store: "EventStorePort",
        halt_trigger: "Optional[HaltTrigger]" = None,
        halt_on_gap: bool = False,
    ) -> None:
        """Initialize the sequence gap detection service.

        Args:
            event_store: The event store port for sequence verification.
            halt_trigger: Optional halt trigger for critical gaps.
            halt_on_gap: Whether to trigger halt on gap detection.
        """
        self._store = event_store
        self._halt = halt_trigger
        self._halt_on_gap = halt_on_gap
        self._last_checked_sequence: int = 0
        self._last_check_timestamp: Optional[datetime] = None
        self._service_id = "sequence_gap_detector"
        self._log = structlog.get_logger().bind(service=self._service_id)

    @property
    def detection_interval(self) -> int:
        """Get the detection interval in seconds."""
        return DETECTION_INTERVAL_SECONDS

    @property
    def service_id(self) -> str:
        """Get the service identifier."""
        return self._service_id

    async def check_sequence_continuity(
        self,
    ) -> Optional[SequenceGapDetectedPayload]:
        """Check for gaps in event sequence.

        Uses EventStorePort.verify_sequence_continuity() to detect gaps.
        Tracks last checked sequence to avoid redundant checks.

        Returns:
            SequenceGapDetectedPayload if gap found, None otherwise.

        Note:
            - Returns None if store is empty
            - Returns None if already checked up to max sequence
            - Updates last_checked_sequence after each check
        """
        current_max = await self._store.get_max_sequence()

        if current_max == 0:
            # Empty store - nothing to check
            return None

        # Check from last checked position to current max
        start = self._last_checked_sequence + 1 if self._last_checked_sequence > 0 else 1
        if start > current_max:
            # Already checked everything
            return None

        # Verify continuity using existing port method
        is_continuous, missing = await self._store.verify_sequence_continuity(
            start=start,
            end=current_max,
        )

        # Store previous timestamp for payload
        previous_check = self._last_check_timestamp or datetime.now(timezone.utc)
        self._last_check_timestamp = datetime.now(timezone.utc)
        self._last_checked_sequence = current_max

        if is_continuous:
            return None

        # Gap detected! Create payload
        return SequenceGapDetectedPayload(
            detection_timestamp=datetime.now(timezone.utc),
            expected_sequence=missing[0] if missing else start,
            actual_sequence=current_max,
            gap_size=len(missing),
            missing_sequences=tuple(missing),
            detection_service_id=self._service_id,
            previous_check_timestamp=previous_check,
        )

    async def handle_gap_detected(
        self,
        payload: SequenceGapDetectedPayload,
    ) -> None:
        """Handle detected sequence gap (FR19).

        Logs warning and optionally triggers halt.

        Args:
            payload: The gap detection details.

        Note:
            This method logs the gap but does NOT create a witnessed event.
            Event creation should be done by the caller if needed.
        """
        self._log.warning(
            "sequence_gap_detected",
            expected=payload.expected_sequence,
            actual=payload.actual_sequence,
            gap_size=payload.gap_size,
            missing=payload.missing_sequences,
        )

        # Optionally trigger halt (severity-based)
        if self._halt_on_gap and self._halt:
            crisis = ConstitutionalCrisisPayload(
                crisis_type=CrisisType.SEQUENCE_GAP_DETECTED,
                detection_timestamp=payload.detection_timestamp,
                detection_details=(
                    f"FR18-FR19: Sequence gap detected. "
                    f"Missing sequences: {payload.missing_sequences}"
                ),
                triggering_event_ids=(),
                detecting_service_id=self._service_id,
            )
            await self._halt.trigger_halt(crisis)

    async def run_detection_cycle(self) -> Optional[SequenceGapDetectedPayload]:
        """Run a single detection cycle.

        Checks for gaps and handles any detected gaps.

        Returns:
            SequenceGapDetectedPayload if gap found, None otherwise.

        Note:
            This method is designed to be called periodically by
            SequenceGapMonitor.
        """
        gap = await self.check_sequence_continuity()
        if gap:
            await self.handle_gap_detected(gap)
        return gap
