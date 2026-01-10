"""Sequence gap monitor background service (FR18-FR19, Story 3.7).

This service runs a background loop that periodically checks for
sequence gaps in the event store.

Constitutional Constraints:
- FR18: Gap detection within 1 minute
- FR19: Gap triggers investigation, not auto-fill

Detection SLA:
- 30-second detection interval ensures gaps are detected within 1 minute
- 2 cycles (60 seconds) = maximum detection latency

Note:
    This service should be started with the application lifecycle
    and stopped when the application shuts down.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

import structlog

from src.application.ports.sequence_gap_detector import DETECTION_INTERVAL_SECONDS

if TYPE_CHECKING:
    from src.application.services.sequence_gap_detection_service import (
        SequenceGapDetectionService,
    )
    from src.domain.events.sequence_gap_detected import SequenceGapDetectedPayload


class SequenceGapMonitor:
    """Background sequence gap monitoring service (FR18).

    Runs detection cycle every 30 seconds to meet 1-minute detection SLA.

    Constitutional Constraints:
    - FR18: Detect gaps within 1 minute
    - 30-second interval ensures 2 detection opportunities per minute

    Attributes:
        running: Whether the monitor is currently running.
        interval_seconds: The detection interval in seconds.

    Example:
        >>> monitor = SequenceGapMonitor(detection_service=detection_service)
        >>> await monitor.start()
        >>> # ... application runs ...
        >>> await monitor.stop()

    Note:
        This is a background service that should be started with
        the application lifecycle.
    """

    def __init__(
        self,
        detection_service: "SequenceGapDetectionService",
        interval_seconds: int = DETECTION_INTERVAL_SECONDS,
    ) -> None:
        """Initialize the sequence gap monitor.

        Args:
            detection_service: The detection service to use.
            interval_seconds: The detection interval in seconds.
        """
        self._detection = detection_service
        self._interval = interval_seconds
        self._running: bool = False
        self._task: Optional[asyncio.Task[None]] = None
        self._log = structlog.get_logger().bind(service="sequence_gap_monitor")

    @property
    def running(self) -> bool:
        """Check if the monitor is running."""
        return self._running

    @property
    def interval_seconds(self) -> int:
        """Get the detection interval in seconds."""
        return self._interval

    async def start(self) -> None:
        """Start the monitoring loop.

        Creates a background task that runs the detection cycle
        at the configured interval.

        Note:
            Calling start multiple times is safe (idempotent).
        """
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        self._log.info("sequence_gap_monitor_started", interval=self._interval)

    async def stop(self) -> None:
        """Stop the monitoring loop gracefully.

        Cancels the background task and waits for it to complete.

        Note:
            Calling stop when not running is safe.
        """
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        self._log.info("sequence_gap_monitor_stopped")

    async def _run_loop(self) -> None:
        """Internal monitoring loop.

        Runs the detection cycle at the configured interval.
        Handles exceptions gracefully to ensure the loop continues.
        """
        while self._running:
            try:
                start_time = datetime.now(timezone.utc)
                gap = await self._detection.check_sequence_continuity()

                if gap:
                    await self._detection.handle_gap_detected(gap)

                elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
                self._log.debug(
                    "detection_cycle_complete",
                    gap_found=gap is not None,
                    elapsed_seconds=elapsed,
                )

                # Sleep for remainder of interval
                sleep_time = max(0, self._interval - elapsed)
                await asyncio.sleep(sleep_time)

            except asyncio.CancelledError:
                raise
            except Exception as e:
                self._log.error("detection_cycle_failed", error=str(e))
                await asyncio.sleep(self._interval)

    async def run_once(self) -> "Optional[SequenceGapDetectedPayload]":
        """Run a single detection cycle (for testing).

        Checks for gaps and handles any detected gaps.

        Returns:
            SequenceGapDetectedPayload if gap found, None otherwise.

        Note:
            This method is primarily for testing purposes.
            In production, use start() and stop() instead.
        """
        gap = await self._detection.check_sequence_continuity()
        if gap:
            await self._detection.handle_gap_detected(gap)
        return gap
