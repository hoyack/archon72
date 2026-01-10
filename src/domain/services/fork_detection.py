"""Fork detection domain service (FR16, Story 3.1, Task 3).

This module provides the fork detection logic as a pure domain service.
A fork is detected when two events claim the same prev_hash but have
different content_hashes.

Constitutional Constraints:
- FR16: System SHALL continuously monitor for conflicting hashes
- CT-11: Silent failure destroys legitimacy
- CT-12: Witnessing creates accountability

Note: This is pure domain logic with no infrastructure dependencies.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from src.domain.events.fork_detected import ForkDetectedPayload

if TYPE_CHECKING:
    from src.domain.events.event import Event


class ForkDetectionService:
    """Domain service for detecting fork conditions.

    A fork occurs when two events claim the same prev_hash but have
    different content_hashes. This is a constitutional crisis.

    This service implements pure domain logic for fork detection.
    It does not have any infrastructure dependencies.

    Constitutional Constraints:
    - FR16: System SHALL continuously monitor for conflicting hashes
    - CT-11: Silent failure destroys legitimacy

    Attributes:
        service_id: Identifier for the detecting service (for attribution)

    Example:
        >>> service = ForkDetectionService(service_id="detector-001")
        >>> result = service.detect_fork(events)
        >>> if result:
        ...     print(f"Fork detected: {result.prev_hash}")
    """

    def __init__(self, service_id: str) -> None:
        """Initialize the fork detection service.

        Args:
            service_id: Identifier for this service (used in ForkDetectedPayload)
        """
        self._service_id = service_id

    @property
    def service_id(self) -> str:
        """Get the service ID."""
        return self._service_id

    def detect_fork(self, events: list[Event]) -> ForkDetectedPayload | None:
        """Detect fork conditions in a list of events.

        Scans the provided events to detect if two events claim the same
        prev_hash but have different content_hashes.

        Args:
            events: List of events to check for fork conditions.

        Returns:
            ForkDetectedPayload if fork detected, None otherwise.

        Note:
            Returns immediately upon finding the first fork.
            Only two conflicting events are included in the payload,
            even if more events share the same prev_hash.
        """
        if len(events) < 2:
            return None

        # Group events by prev_hash
        events_by_prev_hash: dict[str, list[Event]] = {}

        for event in events:
            prev_hash = event.prev_hash

            if prev_hash in events_by_prev_hash:
                # Check for conflicts with existing events at this prev_hash
                for existing in events_by_prev_hash[prev_hash]:
                    if existing.content_hash != event.content_hash:
                        # Fork detected!
                        return ForkDetectedPayload(
                            conflicting_event_ids=(
                                existing.event_id,
                                event.event_id,
                            ),
                            prev_hash=prev_hash,
                            content_hashes=(
                                existing.content_hash,
                                event.content_hash,
                            ),
                            detection_timestamp=datetime.now(timezone.utc),
                            detecting_service_id=self._service_id,
                        )
                # No conflict with existing events, add to list
                events_by_prev_hash[prev_hash].append(event)
            else:
                events_by_prev_hash[prev_hash] = [event]

        return None
