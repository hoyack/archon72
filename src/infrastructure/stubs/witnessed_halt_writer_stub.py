"""WitnessedHaltWriterStub (Story 3.9, Task 5).

Stub implementation of WitnessedHaltWriter for testing.
Allows configuration of success/failure and tracks written events.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from src.application.ports.witnessed_halt_writer import WitnessedHaltWriter
from src.domain.events.constitutional_crisis import (
    CONSTITUTIONAL_CRISIS_EVENT_TYPE,
    ConstitutionalCrisisPayload,
)
from src.domain.events.event import Event


class WitnessedHaltWriterStub(WitnessedHaltWriter):
    """Test stub for WitnessedHaltWriter.

    Simulates witnessed halt event writing with configurable
    success/failure. Tracks written events for test assertions.
    """

    def __init__(self) -> None:
        """Initialize with empty state."""
        self._fail_next: bool = False
        self._written_events: list[Event] = []
        self._sequence_counter: int = 1
        self._last_content_hash: str | None = None

    def set_fail_next(self) -> None:
        """Configure next write to fail.

        The next call to write_halt_event will return None.
        After that failure, subsequent calls succeed again.
        """
        self._fail_next = True

    def get_written_events(self) -> list[Event]:
        """Get list of successfully written events.

        Returns:
            List of Event objects in write order.
        """
        return list(self._written_events)

    def reset(self) -> None:
        """Reset all state.

        Clears written events and failure configuration.
        """
        self._fail_next = False
        self._written_events.clear()
        self._sequence_counter = 1
        self._last_content_hash = None

    async def write_halt_event(
        self,
        crisis_payload: ConstitutionalCrisisPayload,
    ) -> Event | None:
        """Write a witnessed halt event.

        Args:
            crisis_payload: The crisis details to record.

        Returns:
            Event if successful, None if configured to fail.
        """
        if self._fail_next:
            self._fail_next = False
            return None

        # Create mock event with all required fields
        event = Event.create_with_hash(
            sequence=self._sequence_counter,
            event_type=CONSTITUTIONAL_CRISIS_EVENT_TYPE,
            payload={
                "crisis_type": crisis_payload.crisis_type.value,
                "detection_timestamp": crisis_payload.detection_timestamp.isoformat(),
                "detection_details": crisis_payload.detection_details,
                "triggering_event_ids": [
                    str(uid) for uid in crisis_payload.triggering_event_ids
                ],
                "detecting_service_id": crisis_payload.detecting_service_id,
            },
            signature="stub_signature_" + str(uuid4())[:8],
            witness_id="stub-witness-001",
            witness_signature="stub_witness_sig_" + str(uuid4())[:8],
            local_timestamp=datetime.now(timezone.utc),
            agent_id=crisis_payload.detecting_service_id,
            previous_content_hash=self._last_content_hash,
        )

        self._sequence_counter += 1
        self._last_content_hash = event.content_hash
        self._written_events.append(event)

        return event
