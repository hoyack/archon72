"""Petition Event Emitter Service (Story 1.2, FR-1.7, Story 1.7, FR-2.5).

This service emits petition lifecycle events to the governance ledger
using the two-phase emission pattern for observability.

Constitutional Constraints:
- FR-1.7: System SHALL emit PetitionReceived event on successful intake
- FR-2.5: System SHALL emit fate event in same transaction as state update
- CT-12: Witnessing creates accountability - events are witnessed via ledger
- CT-13: No writes during halt - emission blocked during system halt
- HC-1: Fate transition requires witness event - NO silent fate assignment
- NFR-3.3: Event witnessing: 100% fate events persisted [CRITICAL]
- AD-3: Two-phase event emission for Knight observability

Developer Golden Rules:
1. WITNESS EVERYTHING - All events must be persisted to ledger
2. FAIL GRACEFULLY - Event emission errors logged but don't fail operations (petition.received)
3. FAIL LOUD - Fate events MUST raise on failure (petition.acknowledged/referred/escalated)
4. HALT CHECK - Respect halt state for event emission (caller responsibility)

HARDENING-1: TimeAuthorityService Mandatory Injection
"""

from __future__ import annotations

import logging
from datetime import datetime
from uuid import UUID, uuid4

from src.application.ports.governance.ledger_port import GovernanceLedgerPort
from src.application.ports.petition_event_emitter import PetitionEventEmitterPort
from src.domain.ports.time_authority import TimeAuthorityProtocol
from src.domain.events.petition import (
    PETITION_ACKNOWLEDGED_EVENT_TYPE,
    PETITION_ESCALATED_EVENT_TYPE,
    PETITION_RECEIVED_EVENT_TYPE,
    PETITION_REFERRED_EVENT_TYPE,
    PETITION_SYSTEM_AGENT_ID,
    PETITION_WITHDRAWN_EVENT_TYPE,
    PetitionFateEventPayload,
    PetitionReceivedEventPayload,
    PetitionWithdrawnEventPayload,
)
from src.domain.governance.events.event_envelope import GovernanceEvent
from src.domain.governance.events.schema_versions import CURRENT_SCHEMA_VERSION

logger = logging.getLogger(__name__)


class PetitionEventEmitter(PetitionEventEmitterPort):
    """Service for emitting petition lifecycle events.

    This service emits petition events to the governance ledger,
    providing observability for the petition lifecycle.

    Constitutional Guarantees:
    - Events are witnessed via GovernanceLedger (CT-12)
    - Event emission errors are logged but don't fail operations
    - Halt state must be checked by caller (CT-13)

    Example:
        emitter = PetitionEventEmitter(ledger, time_authority)
        success = await emitter.emit_petition_received(
            petition_id=petition_id,
            petition_type="GENERAL",
            realm="default",
            content_hash="base64hash==",
            submitter_id=None,
        )
    """

    def __init__(
        self,
        ledger: GovernanceLedgerPort,
        time_authority: TimeAuthorityProtocol,
    ) -> None:
        """Initialize the PetitionEventEmitter.

        Args:
            ledger: The governance ledger for event persistence.
            time_authority: Time authority for timestamps (HARDENING-1).
        """
        self._ledger = ledger
        self._time_authority = time_authority

    async def emit_petition_received(
        self,
        petition_id: UUID,
        petition_type: str,
        realm: str,
        content_hash: str,
        submitter_id: UUID | None,
    ) -> bool:
        """Emit petition.received event after successful intake.

        This method emits a petition.received event to notify observers
        that a new petition has been received and persisted.

        The event is emitted to the governance ledger and witnessed
        per CT-12. Emission errors are logged but do NOT fail the
        calling operation (eventual consistency).

        Constitutional Constraints:
        - FR-1.7: Event SHALL be emitted on successful intake
        - CT-12: Event is witnessed via GovernanceLedger
        - CT-13: Halt check is caller responsibility

        Args:
            petition_id: The unique petition identifier.
            petition_type: Type of petition (GENERAL, CESSATION, etc.)
            realm: The realm assigned for routing.
            content_hash: Base64-encoded Blake3 hash of petition text.
            submitter_id: Optional submitter identity.

        Returns:
            True if event was emitted successfully, False otherwise.
            False does NOT indicate submission failure - just event emission.
        """
        try:
            # Get timestamp from time authority (HARDENING-1)
            now: datetime = self._time_authority.utcnow()

            # Create event payload (FR-1.7)
            payload = PetitionReceivedEventPayload(
                petition_id=petition_id,
                petition_type=petition_type,
                realm=realm,
                content_hash=content_hash,
                submitter_id=submitter_id,
                received_timestamp=now,
            )

            # Create governance event envelope
            event_id = uuid4()
            event = GovernanceEvent.create(
                event_id=event_id,
                event_type=PETITION_RECEIVED_EVENT_TYPE,
                timestamp=now,
                actor_id=PETITION_SYSTEM_AGENT_ID,
                trace_id=str(petition_id),  # Use petition_id for tracing
                payload=payload.to_dict(),
                schema_version=CURRENT_SCHEMA_VERSION,
            )

            # Persist to ledger (CT-12: witnessing)
            await self._ledger.append_event(event)

            logger.info(
                "petition.received event emitted",
                extra={
                    "petition_id": str(petition_id),
                    "event_id": str(event_id),
                    "petition_type": petition_type,
                    "realm": realm,
                },
            )

            return True

        except Exception as e:
            # Log error but don't fail the operation (eventual consistency)
            # The petition is already persisted; event can be reconstructed
            logger.error(
                "Failed to emit petition.received event",
                extra={
                    "petition_id": str(petition_id),
                    "petition_type": petition_type,
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
                exc_info=True,
            )
            return False

    async def emit_fate_event(
        self,
        petition_id: UUID,
        previous_state: str,
        new_state: str,
        actor_id: str,
        reason: str | None = None,
    ) -> None:
        """Emit fate event when petition reaches terminal state (FR-2.5, HC-1).

        This method emits a fate event (petition.acknowledged, petition.referred,
        or petition.escalated) when a petition transitions to a terminal fate state.

        CRITICAL: This method MUST raise on failure - no graceful degradation.
        If event cannot be witnessed, the caller MUST rollback state change.
        This ensures HC-1: Fate transition requires witness event.

        Constitutional Constraints:
        - FR-2.5: Event SHALL be emitted in same transaction as state update
        - HC-1: Fate transition requires witness event - NO silent failures
        - NFR-3.3: 100% fate events persisted [CRITICAL]
        - CT-12: Event is witnessed via GovernanceLedger

        Args:
            petition_id: The petition reaching terminal state.
            previous_state: State before fate assignment (RECEIVED or DELIBERATING).
            new_state: Terminal fate state (ACKNOWLEDGED, REFERRED, or ESCALATED).
            actor_id: Agent or system identifier that assigned the fate.
            reason: Optional reason code or rationale.

        Returns:
            None on success.

        Raises:
            Exception: If event emission fails - caller MUST handle rollback.
        """
        # Get timestamp from time authority (HARDENING-1)
        now: datetime = self._time_authority.utcnow()

        # Map fate state to event type (AC: 1, 2, 3)
        event_type = self._get_fate_event_type(new_state)

        # Create fate event payload (Story 1.7, AC: 5)
        payload = PetitionFateEventPayload(
            petition_id=petition_id,
            previous_state=previous_state,
            new_state=new_state,
            actor_id=actor_id,
            timestamp=now,
            reason=reason,
        )

        # Create governance event envelope
        event_id = uuid4()
        event = GovernanceEvent.create(
            event_id=event_id,
            event_type=event_type,
            timestamp=now,
            actor_id=actor_id,  # Use actor who assigned fate, not system
            trace_id=str(petition_id),  # Use petition_id for tracing
            payload=payload.to_dict(),
            schema_version=CURRENT_SCHEMA_VERSION,
        )

        # Persist to ledger (CT-12: witnessing)
        # CRITICAL: NO try/except - exception MUST propagate to caller (HC-1)
        await self._ledger.append_event(event)

        # Log success (only reached if append_event succeeds)
        logger.info(
            f"{event_type} event emitted",
            extra={
                "petition_id": str(petition_id),
                "event_id": str(event_id),
                "previous_state": previous_state,
                "new_state": new_state,
                "actor_id": actor_id,
            },
        )

    @staticmethod
    def _get_fate_event_type(new_state: str) -> str:
        """Map fate state to event type constant.

        Args:
            new_state: Terminal fate state.

        Returns:
            Event type constant for the fate.

        Raises:
            ValueError: If new_state is not a valid fate state.
        """
        event_type_map = {
            "ACKNOWLEDGED": PETITION_ACKNOWLEDGED_EVENT_TYPE,
            "REFERRED": PETITION_REFERRED_EVENT_TYPE,
            "ESCALATED": PETITION_ESCALATED_EVENT_TYPE,
        }
        if new_state not in event_type_map:
            raise ValueError(
                f"Invalid fate state: {new_state}. "
                f"Must be one of: {list(event_type_map.keys())}"
            )
        return event_type_map[new_state]

    async def emit_petition_withdrawn(
        self,
        petition_id: UUID,
        withdrawn_by: UUID,
        reason: str | None = None,
    ) -> bool:
        """Emit petition.withdrawn event when petitioner withdraws (Story 7.3, FR-7.5).

        This method emits a petition.withdrawn event to notify observers
        that a petition has been withdrawn by the original petitioner.

        Note: This is a secondary event - the primary fate event (petition.acknowledged)
        is emitted via emit_fate_event with WITHDRAWN reason code. This event provides
        additional context specifically for withdrawals.

        The event is emitted to the governance ledger and witnessed
        per CT-12. Emission errors are logged but do NOT fail the
        calling operation (eventual consistency).

        Constitutional Constraints:
        - FR-7.5: Event SHALL be emitted when petitioner withdraws
        - CT-12: Event is witnessed via GovernanceLedger
        - CT-13: Halt check is caller responsibility

        Args:
            petition_id: The withdrawn petition identifier.
            withdrawn_by: UUID of the petitioner who withdrew.
            reason: Optional explanation for withdrawal.

        Returns:
            True if event was emitted successfully, False otherwise.
            False does NOT indicate withdrawal failure - just event emission.
        """
        try:
            # Get timestamp from time authority (HARDENING-1)
            now: datetime = self._time_authority.utcnow()

            # Create event payload (FR-7.5)
            payload = PetitionWithdrawnEventPayload(
                petition_id=petition_id,
                withdrawn_by=withdrawn_by,
                reason=reason,
                withdrawn_at=now,
            )

            # Create governance event envelope
            event_id = uuid4()
            event = GovernanceEvent.create(
                event_id=event_id,
                event_type=PETITION_WITHDRAWN_EVENT_TYPE,
                timestamp=now,
                actor_id=f"submitter:{withdrawn_by}",
                trace_id=str(petition_id),  # Use petition_id for tracing
                payload=payload.to_dict(),
                schema_version=CURRENT_SCHEMA_VERSION,
            )

            # Persist to ledger (CT-12: witnessing)
            await self._ledger.append_event(event)

            logger.info(
                "petition.withdrawn event emitted",
                extra={
                    "petition_id": str(petition_id),
                    "event_id": str(event_id),
                    "withdrawn_by": str(withdrawn_by),
                },
            )

            return True

        except Exception as e:
            # Log error but don't fail the operation (eventual consistency)
            # The withdrawal fate event is already emitted; this is secondary
            logger.error(
                "Failed to emit petition.withdrawn event",
                extra={
                    "petition_id": str(petition_id),
                    "withdrawn_by": str(withdrawn_by),
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
                exc_info=True,
            )
            return False
