"""Fork Monitor port interface for continuous fork detection (FR16, Story 3.1).

This module defines the ForkMonitor abstract base class for fork detection.
Implementations monitor for conflicting hashes from the same prior state.

Constitutional Constraints:
- FR16: System SHALL continuously monitor for conflicting hashes
- CT-11: Silent failure destroys legitimacy -> Fork detection MUST be logged
- CT-12: Witnessing creates accountability
- CT-13: Integrity outranks availability -> Fork triggers halt

Note: This story (3.1) handles DETECTION only. Halt logic is in Story 3.2.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.events.fork_detected import ForkDetectedPayload


class ForkMonitor(ABC):
    """Abstract interface for fork detection monitoring.

    Fork detection is a constitutional requirement (FR16). This interface
    defines the contract for continuous monitoring of hash chain integrity.

    A fork occurs when two events claim the same prev_hash but have
    different content_hashes. This is a constitutional crisis.

    Constitutional Constraints:
    - FR16: System SHALL continuously monitor for conflicting hashes
    - CT-11: Silent failure destroys legitimacy
    - CT-13: Integrity outranks availability

    Implementations should:
    1. Continuously check for forks at the configured interval
    2. Log detection latency for each check cycle
    3. Return ForkDetectedPayload immediately when fork is found
    4. Ensure graceful shutdown when stop_monitoring is called

    Note:
        Default monitoring interval is 10 seconds (configurable).
        Fork detection should trigger halt (handled by Story 3.2).
    """

    @property
    def monitoring_interval_seconds(self) -> int:
        """Get the monitoring interval in seconds.

        Default implementation returns 10 seconds per FR16 requirement:
        "fork checks run at least every 10 seconds"

        Override in concrete implementations if different interval needed.

        Returns:
            Monitoring interval in seconds (default: 10)
        """
        return 10

    @abstractmethod
    async def check_for_forks(self) -> ForkDetectedPayload | None:
        """Check for fork conditions in the event store.

        Scans events to detect if two events claim the same prev_hash
        but have different content_hashes.

        This method should:
        1. Query recent events (or all events if first check)
        2. Group events by prev_hash
        3. Detect conflicts (same prev_hash, different content_hash)
        4. Return ForkDetectedPayload if fork found

        Returns:
            ForkDetectedPayload if fork detected, None otherwise.

        Note:
            Detection latency should be logged by the caller.
        """
        ...

    @abstractmethod
    async def start_monitoring(self) -> None:
        """Start continuous fork monitoring.

        Starts a background task that calls check_for_forks at the
        configured interval. Continues until stop_monitoring is called.

        The monitoring loop should:
        1. Call check_for_forks at each interval
        2. Log detection latency for each cycle
        3. Handle errors gracefully (log and continue)
        4. Emit ForkDetectedEvent when fork is found
        """
        ...

    @abstractmethod
    async def stop_monitoring(self) -> None:
        """Stop continuous fork monitoring.

        Gracefully stops the monitoring background task.
        Should wait for current check to complete if one is in progress.
        """
        ...
