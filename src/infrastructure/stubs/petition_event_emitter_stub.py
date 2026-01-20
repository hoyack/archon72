"""Stub implementation of PetitionEventEmitterPort for testing.

This stub captures emitted events for test assertions without
requiring a real governance ledger.

Usage in tests:
    stub = PetitionEventEmitterStub()
    service = PetitionSubmissionService(..., event_emitter=stub)

    await service.submit_petition(...)

    assert len(stub.emitted_events) == 1
    assert stub.emitted_events[0]["petition_type"] == "GENERAL"

    # Test fate event emission (Story 1.7)
    stub.reset()
    await stub.emit_fate_event(
        petition_id=petition_id,
        previous_state="RECEIVED",
        new_state="ACKNOWLEDGED",
        actor_id="clotho-agent",
        reason="Acknowledged per protocol",
    )
    assert len(stub.emitted_fate_events) == 1
    assert stub.emitted_fate_events[0].new_state == "ACKNOWLEDGED"
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from src.application.ports.petition_event_emitter import PetitionEventEmitterPort


@dataclass
class EmittedEvent:
    """Record of an emitted petition.received event for test assertions.

    Attributes:
        petition_id: The petition identifier.
        petition_type: Type of petition.
        realm: The assigned realm.
        content_hash: Base64-encoded content hash.
        submitter_id: Optional submitter identity.
        emitted_at: When the event was emitted.
    """

    petition_id: UUID
    petition_type: str
    realm: str
    content_hash: str
    submitter_id: UUID | None
    emitted_at: datetime


@dataclass
class EmittedFateEvent:
    """Record of an emitted fate event for test assertions (Story 1.7).

    Attributes:
        petition_id: The petition identifier.
        previous_state: State before fate assignment.
        new_state: Terminal fate state (ACKNOWLEDGED/REFERRED/ESCALATED).
        actor_id: Agent or system that assigned fate.
        reason: Optional rationale for fate decision.
        emitted_at: When the event was emitted.
    """

    petition_id: UUID
    previous_state: str
    new_state: str
    actor_id: str
    reason: str | None
    emitted_at: datetime


class PetitionEventEmitterStub(PetitionEventEmitterPort):
    """Stub implementation for testing petition event emission.

    This stub captures all emitted events in a list for test assertions.
    It can be configured to simulate failures for error path testing.

    Attributes:
        emitted_events: List of all emitted petition.received events.
        emitted_fate_events: List of all emitted fate events (Story 1.7).
        should_fail: If True, emit_petition_received returns False.
        fail_exception: If set, emit_petition_received raises this exception.
        fate_should_fail: If True, emit_fate_event raises an exception (HC-1).
        fate_fail_exception: If set, emit_fate_event raises this exception.

    Example:
        stub = PetitionEventEmitterStub()
        service = SomeService(event_emitter=stub)

        await service.do_something()

        assert len(stub.emitted_events) == 1
        assert stub.emitted_events[0].petition_type == "GENERAL"

        # Test failure path for petition.received (graceful)
        stub.should_fail = True
        result = await stub.emit_petition_received(...)
        assert result is False

        # Test failure path for fate events (MUST raise - HC-1)
        stub.fate_should_fail = True
        with pytest.raises(RuntimeError):
            await stub.emit_fate_event(...)
    """

    def __init__(self) -> None:
        """Initialize the stub with empty state."""
        self.emitted_events: list[EmittedEvent] = []
        self.emitted_fate_events: list[EmittedFateEvent] = []
        self.should_fail: bool = False
        self.fail_exception: Exception | None = None
        self.fate_should_fail: bool = False
        self.fate_fail_exception: Exception | None = None

    async def emit_petition_received(
        self,
        petition_id: UUID,
        petition_type: str,
        realm: str,
        content_hash: str,
        submitter_id: UUID | None,
    ) -> bool:
        """Capture petition.received event for test assertions.

        Args:
            petition_id: The petition identifier.
            petition_type: Type of petition.
            realm: The assigned realm.
            content_hash: Base64-encoded content hash.
            submitter_id: Optional submitter identity.

        Returns:
            True if not configured to fail, False if should_fail is True.

        Raises:
            Exception: If fail_exception is set.
        """
        if self.fail_exception is not None:
            raise self.fail_exception

        if self.should_fail:
            return False

        event = EmittedEvent(
            petition_id=petition_id,
            petition_type=petition_type,
            realm=realm,
            content_hash=content_hash,
            submitter_id=submitter_id,
            emitted_at=datetime.now(timezone.utc),
        )
        self.emitted_events.append(event)
        return True

    async def emit_fate_event(
        self,
        petition_id: UUID,
        previous_state: str,
        new_state: str,
        actor_id: str,
        reason: str | None = None,
    ) -> None:
        """Capture fate event for test assertions (Story 1.7).

        CRITICAL: Unlike emit_petition_received, this method MUST raise
        on failure (HC-1: Fate transition requires witness event).

        Args:
            petition_id: The petition reaching terminal state.
            previous_state: State before fate assignment.
            new_state: Terminal fate state (ACKNOWLEDGED/REFERRED/ESCALATED).
            actor_id: Agent or system that assigned fate.
            reason: Optional rationale for fate decision.

        Returns:
            None on success.

        Raises:
            Exception: If fate_fail_exception is set or fate_should_fail is True.
        """
        if self.fate_fail_exception is not None:
            raise self.fate_fail_exception

        if self.fate_should_fail:
            raise RuntimeError("Simulated fate event emission failure (HC-1 test)")

        fate_event = EmittedFateEvent(
            petition_id=petition_id,
            previous_state=previous_state,
            new_state=new_state,
            actor_id=actor_id,
            reason=reason,
            emitted_at=datetime.now(timezone.utc),
        )
        self.emitted_fate_events.append(fate_event)

    def reset(self) -> None:
        """Reset stub state for reuse between tests."""
        self.emitted_events.clear()
        self.emitted_fate_events.clear()
        self.should_fail = False
        self.fail_exception = None
        self.fate_should_fail = False
        self.fate_fail_exception = None

    def get_event_by_petition_id(self, petition_id: UUID) -> EmittedEvent | None:
        """Find an emitted event by petition ID.

        Args:
            petition_id: The petition ID to search for.

        Returns:
            The matching EmittedEvent or None if not found.
        """
        for event in self.emitted_events:
            if event.petition_id == petition_id:
                return event
        return None

    def to_dict_list(self) -> list[dict[str, Any]]:
        """Convert emitted petition.received events to list of dicts for assertions.

        Returns:
            List of event dicts with all fields.
        """
        return [
            {
                "petition_id": str(event.petition_id),
                "petition_type": event.petition_type,
                "realm": event.realm,
                "content_hash": event.content_hash,
                "submitter_id": str(event.submitter_id) if event.submitter_id else None,
                "emitted_at": event.emitted_at.isoformat(),
            }
            for event in self.emitted_events
        ]

    def get_fate_event_by_petition_id(
        self, petition_id: UUID
    ) -> EmittedFateEvent | None:
        """Find an emitted fate event by petition ID (Story 1.7).

        Args:
            petition_id: The petition ID to search for.

        Returns:
            The matching EmittedFateEvent or None if not found.
        """
        for event in self.emitted_fate_events:
            if event.petition_id == petition_id:
                return event
        return None

    def fate_events_to_dict_list(self) -> list[dict[str, Any]]:
        """Convert emitted fate events to list of dicts for assertions (Story 1.7).

        Returns:
            List of fate event dicts with all fields.
        """
        return [
            {
                "petition_id": str(event.petition_id),
                "previous_state": event.previous_state,
                "new_state": event.new_state,
                "actor_id": event.actor_id,
                "reason": event.reason,
                "emitted_at": event.emitted_at.isoformat(),
            }
            for event in self.emitted_fate_events
        ]
