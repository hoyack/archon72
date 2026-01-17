"""Transition Logging Service - Logs all state transitions for audit.

Story: consent-gov-9.4: State Transition Logging

This service logs all state transitions in the governance system.
Logs are append-only and cannot be modified or deleted.

Constitutional Requirements:
- FR59: System can log all state transitions with timestamp and actor
- FR60: System can prevent ledger modification (append-only enforcement)
- NFR-AUDIT-04: Transitions include triggering event reference

Design Decisions:
- Uses TimeAuthority for consistent timestamps
- Emits audit.transition.logged event for each transition
- No modification or deletion methods exist
- All entity types use same logging mechanism
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional, Protocol
from uuid import UUID, uuid4

from src.domain.governance.audit.transition_log import (
    EntityType,
    TransitionLog,
    TransitionQuery,
)

if TYPE_CHECKING:
    from src.application.ports.governance.transition_log_port import (
        TransitionLogPort,
    )


# Event type for audit logging
TRANSITION_LOGGED_EVENT = "audit.transition.logged"


class EventEmitterPort(Protocol):
    """Port for emitting events."""

    async def emit(
        self,
        event_type: str,
        actor: str,
        payload: dict[str, Any],
    ) -> None:
        """Emit an event."""
        ...


class TimeAuthorityPort(Protocol):
    """Port for getting authoritative time."""

    def now(self) -> datetime:
        """Get current time with millisecond precision."""
        ...


class TransitionLoggingService:
    """Service for logging all state transitions.

    Logs are append-only. NO modification methods exist.
    This is a design decision per FR60 - audit trail must be immutable.

    This service:
    1. Creates immutable TransitionLog entries
    2. Appends to the log store (only write operation)
    3. Emits audit.transition.logged event
    4. Provides query methods for reading logs

    ┌────────────────────────────────────────────────────────────────┐
    │  Intentionally NOT implemented (FR60 compliance):              │
    │  - update_log() - no modification of logs                      │
    │  - delete_log() - no deletion of logs                          │
    │  - modify_log() - no modification of logs                      │
    │  - remove_log() - no removal of logs                           │
    └────────────────────────────────────────────────────────────────┘
    """

    def __init__(
        self,
        log_port: "TransitionLogPort",
        event_emitter: EventEmitterPort,
        time_authority: TimeAuthorityPort,
    ) -> None:
        """Initialize the transition logging service.

        Args:
            log_port: Port for storing transition logs (append-only).
            event_emitter: Port for emitting audit events.
            time_authority: Port for getting authoritative time.
        """
        self._logs = log_port
        self._event_emitter = event_emitter
        self._time = time_authority

    async def log_transition(
        self,
        entity_type: EntityType,
        entity_id: UUID,
        from_state: str,
        to_state: str,
        actor: str,
        reason: str,
        triggering_event_id: Optional[UUID] = None,
    ) -> TransitionLog:
        """Log a state transition.

        This is the ONLY way to add to the log.
        There is no way to modify or delete logs.

        Args:
            entity_type: Type of entity transitioning.
            entity_id: ID of the entity.
            from_state: State before transition.
            to_state: State after transition.
            actor: Who/what caused the transition (UUID or "system").
            reason: Human-readable reason for the transition.
            triggering_event_id: Optional reference to triggering event.

        Returns:
            TransitionLog (immutable record).
        """
        now = self._time.now()
        log_id = uuid4()

        log = TransitionLog(
            log_id=log_id,
            entity_type=entity_type,
            entity_id=entity_id,
            from_state=from_state,
            to_state=to_state,
            timestamp=now,
            actor=actor,
            reason=reason,
            triggering_event_id=triggering_event_id,
        )

        # Append to log (only append operation)
        await self._logs.append(log)

        # Emit logged event
        await self._emit_logged_event(log)

        return log

    async def get_transitions(
        self,
        query: TransitionQuery,
    ) -> list[TransitionLog]:
        """Get transitions matching query.

        Read-only operation.

        Args:
            query: Query parameters.

        Returns:
            List of matching transition logs.
        """
        return await self._logs.query(query)

    async def get_entity_history(
        self,
        entity_type: EntityType,
        entity_id: UUID,
    ) -> list[TransitionLog]:
        """Get complete transition history for entity.

        Convenience method for getting all transitions of a
        specific entity in chronological order.

        Args:
            entity_type: Type of entity.
            entity_id: ID of entity.

        Returns:
            All transitions for entity, in order.
        """
        return await self._logs.get_entity_history(entity_type, entity_id)

    async def get_by_id(self, log_id: UUID) -> Optional[TransitionLog]:
        """Get a specific transition log by ID.

        Args:
            log_id: The log ID to retrieve.

        Returns:
            The transition log if found, None otherwise.
        """
        return await self._logs.get_by_id(log_id)

    async def count(self, query: Optional[TransitionQuery] = None) -> int:
        """Count transition logs matching query.

        Args:
            query: Optional query parameters.

        Returns:
            Number of matching logs.
        """
        return await self._logs.count(query)

    async def _emit_logged_event(self, log: TransitionLog) -> None:
        """Emit audit event for logged transition.

        Args:
            log: The transition log that was recorded.
        """
        await self._event_emitter.emit(
            event_type=TRANSITION_LOGGED_EVENT,
            actor=log.actor,
            payload={
                "log_id": str(log.log_id),
                "entity_type": log.entity_type.value,
                "entity_id": str(log.entity_id),
                "from_state": log.from_state,
                "to_state": log.to_state,
                "timestamp": log.timestamp.isoformat(),
                "actor": log.actor,
                "reason": log.reason,
                "triggering_event_id": (
                    str(log.triggering_event_id) if log.triggering_event_id else None
                ),
            },
        )

    # These methods intentionally do not exist (FR60 compliance):
    #
    # async def update_log(self, log_id: UUID, ...) -> TransitionLog:
    #     """Update would violate FR60 - logs are immutable."""
    #     ...
    #
    # async def delete_log(self, log_id: UUID) -> None:
    #     """Delete would violate FR60 - logs are permanent."""
    #     ...
    #
    # async def modify_log(self, log_id: UUID, changes: dict) -> TransitionLog:
    #     """Modify would violate FR60 - logs cannot be changed."""
    #     ...
    #
    # async def remove_log(self, log_id: UUID) -> bool:
    #     """Remove would violate FR60 - logs cannot be removed."""
    #     ...
