"""TwoPhaseEventEmitter service implementation.

Story: consent-gov-1.6: Two-Phase Event Emission

This service implements the two-phase event emission pattern for
Knight observability of all governance operations.

The service:
1. Tracks pending intents in memory (for orphan detection)
2. Emits intent events to the ledger before operations
3. Emits commit/failure events to the ledger after operations
4. Links intent and outcome via correlation_id

Constitutional Guarantees:
- Intent is ALWAYS emitted before operation begins
- Outcome (commit/failure) is ALWAYS emitted after operation
- No orphaned intents - auto-resolved after timeout

References:
- AD-3: Two-phase event emission
- NFR-CONST-07: Witness statements cannot be suppressed
- NFR-OBS-01: Events observable within ≤1 second
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from src.application.ports.governance.ledger_port import GovernanceLedgerPort
from src.application.ports.governance.two_phase_emitter_port import (
    TwoPhaseEmitError,
    TwoPhaseEventEmitterPort,
)
from src.domain.ports.time_authority import TimeAuthorityProtocol
from src.domain.governance.events.event_envelope import GovernanceEvent
from src.domain.governance.events.schema_versions import CURRENT_SCHEMA_VERSION
from src.domain.governance.events.two_phase_events import (
    CommitConfirmedEvent,
    FailureRecordedEvent,
    IntentEmittedEvent,
)


@dataclass
class PendingIntent:
    """A pending intent awaiting outcome (commit or failure).

    Attributes:
        correlation_id: Links intent to outcome.
        intent_event_id: UUID of the intent event in the ledger.
        operation_type: Operation being attempted.
        actor_id: Actor who initiated the operation.
        target_entity_id: Target of the operation.
        intent_payload: Original intent data.
        emitted_at: When the intent was emitted.
    """

    correlation_id: UUID
    intent_event_id: UUID
    operation_type: str
    actor_id: str
    target_entity_id: str
    intent_payload: dict[str, Any]
    emitted_at: datetime


class TwoPhaseEventEmitter(TwoPhaseEventEmitterPort):
    """Service for two-phase event emission.

    This service emits governance events in two phases:
    1. Intent phase - before operation begins
    2. Outcome phase - after operation (commit or failure)

    It maintains a registry of pending intents for orphan detection.

    Example:
        emitter = TwoPhaseEventEmitter(ledger, time_authority)
        correlation_id = await emitter.emit_intent(
            operation_type="executive.task.accept",
            actor_id="archon-42",
            target_entity_id="task-001",
            intent_payload={"earl_id": "earl-1"},
        )
        try:
            result = await perform_task_acceptance()
            await emitter.emit_commit(correlation_id, {"new_state": "accepted"})
        except Exception as e:
            await emitter.emit_failure(correlation_id, str(e), {"traceback": "..."})
            raise
    """

    def __init__(
        self,
        ledger: GovernanceLedgerPort,
        time_authority: TimeAuthorityProtocol,
    ) -> None:
        """Initialize the TwoPhaseEventEmitter.

        Args:
            ledger: The governance ledger for event persistence.
            time_authority: Time authority for timestamps.
        """
        self._ledger = ledger
        self._time_authority = time_authority
        # Track pending intents by correlation_id
        self._pending_intents: dict[UUID, PendingIntent] = {}

    async def emit_intent(
        self,
        operation_type: str,
        actor_id: str,
        target_entity_id: str,
        intent_payload: dict[str, Any],
    ) -> UUID:
        """Emit intent event BEFORE operation begins.

        Creates an IntentEmittedEvent, persists it to the ledger,
        and tracks it as pending until an outcome is emitted.

        Args:
            operation_type: Operation being attempted.
            actor_id: Actor initiating the operation.
            target_entity_id: Target of the operation.
            intent_payload: Operation-specific data.

        Returns:
            The correlation_id linking intent to outcome.
        """
        correlation_id = uuid4()
        now = self._time_authority.now()

        # Create the intent domain event
        intent = IntentEmittedEvent(
            correlation_id=correlation_id,
            operation_type=operation_type,
            actor_id=actor_id,
            target_entity_id=target_entity_id,
            intent_payload=intent_payload,
        )

        # Create the governance event envelope
        event_id = uuid4()
        event = GovernanceEvent.create(
            event_id=event_id,
            event_type=intent.event_type,
            timestamp=now,
            actor_id=actor_id,
            trace_id=str(correlation_id),  # Use correlation_id as trace_id
            payload={
                "correlation_id": str(correlation_id),
                "operation_type": operation_type,
                "target_entity_id": target_entity_id,
                "intent_payload": intent_payload,
            },
            schema_version=CURRENT_SCHEMA_VERSION,
        )

        # Persist to ledger
        persisted = await self._ledger.append_event(event)

        # Track as pending
        self._pending_intents[correlation_id] = PendingIntent(
            correlation_id=correlation_id,
            intent_event_id=persisted.event_id,
            operation_type=operation_type,
            actor_id=actor_id,
            target_entity_id=target_entity_id,
            intent_payload=intent_payload,
            emitted_at=now,
        )

        return correlation_id

    async def emit_commit(
        self,
        correlation_id: UUID,
        result_payload: dict[str, Any],
    ) -> None:
        """Emit commit event on successful operation completion.

        Creates a CommitConfirmedEvent, persists it to the ledger,
        and removes the intent from pending tracking.

        Args:
            correlation_id: The correlation_id from emit_intent().
            result_payload: Operation result data.

        Raises:
            TwoPhaseEmitError: If correlation_id doesn't match a pending intent.
        """
        pending = self._pending_intents.get(correlation_id)
        if pending is None:
            raise TwoPhaseEmitError(
                f"No pending intent found for correlation_id {correlation_id}. "
                "Intent may have already been resolved or was never emitted."
            )

        now = self._time_authority.now()

        # Create the commit domain event
        commit = CommitConfirmedEvent(
            correlation_id=correlation_id,
            intent_event_id=pending.intent_event_id,
            operation_type=pending.operation_type,
            result_payload=result_payload,
        )

        # Create the governance event envelope
        event = GovernanceEvent.create(
            event_id=uuid4(),
            event_type=commit.event_type,
            timestamp=now,
            actor_id=pending.actor_id,
            trace_id=str(correlation_id),
            payload={
                "correlation_id": str(correlation_id),
                "intent_event_id": str(pending.intent_event_id),
                "operation_type": pending.operation_type,
                "result_payload": result_payload,
            },
            schema_version=CURRENT_SCHEMA_VERSION,
        )

        # Persist to ledger
        await self._ledger.append_event(event)

        # Remove from pending
        del self._pending_intents[correlation_id]

    async def emit_failure(
        self,
        correlation_id: UUID,
        failure_reason: str,
        failure_details: dict[str, Any],
    ) -> None:
        """Emit failure event when operation fails.

        Creates a FailureRecordedEvent, persists it to the ledger,
        and removes the intent from pending tracking.

        Args:
            correlation_id: The correlation_id from emit_intent().
            failure_reason: Short reason code.
            failure_details: Error details.

        Raises:
            TwoPhaseEmitError: If correlation_id doesn't match a pending intent.
        """
        pending = self._pending_intents.get(correlation_id)
        if pending is None:
            raise TwoPhaseEmitError(
                f"No pending intent found for correlation_id {correlation_id}. "
                "Intent may have already been resolved or was never emitted."
            )

        now = self._time_authority.now()

        # Check if this is an orphan resolution
        was_orphan = failure_reason == "ORPHAN_TIMEOUT"

        # Create the failure domain event
        failure = FailureRecordedEvent(
            correlation_id=correlation_id,
            intent_event_id=pending.intent_event_id,
            operation_type=pending.operation_type,
            failure_reason=failure_reason,
            failure_details=failure_details,
            was_orphan=was_orphan,
        )

        # Create the governance event envelope
        event = GovernanceEvent.create(
            event_id=uuid4(),
            event_type=failure.event_type,
            timestamp=now,
            actor_id=pending.actor_id,
            trace_id=str(correlation_id),
            payload={
                "correlation_id": str(correlation_id),
                "intent_event_id": str(pending.intent_event_id),
                "operation_type": pending.operation_type,
                "failure_reason": failure_reason,
                "failure_details": failure_details,
                "was_orphan": was_orphan,
            },
            schema_version=CURRENT_SCHEMA_VERSION,
        )

        # Persist to ledger
        await self._ledger.append_event(event)

        # Remove from pending
        del self._pending_intents[correlation_id]

    async def get_pending_intent(
        self,
        correlation_id: UUID,
    ) -> dict[str, Any] | None:
        """Get a pending intent by correlation_id.

        Used by the OrphanIntentDetector to retrieve intent details.

        Args:
            correlation_id: The correlation_id to look up.

        Returns:
            Dict with intent details if pending, None if resolved.
        """
        pending = self._pending_intents.get(correlation_id)
        if pending is None:
            return None

        return {
            "correlation_id": str(pending.correlation_id),
            "intent_event_id": str(pending.intent_event_id),
            "operation_type": pending.operation_type,
            "actor_id": pending.actor_id,
            "target_entity_id": pending.target_entity_id,
            "intent_payload": pending.intent_payload,
            "emitted_at": pending.emitted_at.isoformat(),
        }

    def get_pending_correlation_ids(self) -> list[UUID]:
        """Get all pending correlation IDs.

        Used by the OrphanIntentDetector to scan for orphans.

        Returns:
            List of correlation_ids for all pending intents.
        """
        return list(self._pending_intents.keys())

    def get_pending_intents_with_age(
        self,
    ) -> list[tuple[UUID, datetime]]:
        """Get all pending intents with their emission times.

        Used by OrphanIntentDetector to find intents exceeding timeout.

        Returns:
            List of (correlation_id, emitted_at) tuples.
        """
        return [
            (p.correlation_id, p.emitted_at) for p in self._pending_intents.values()
        ]
