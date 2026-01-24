"""Petition Event Emitter Port (Story 1.2, FR-1.7, Story 1.7, FR-2.5, Story 7.3, FR-7.5).

This module defines the protocol for emitting petition lifecycle events
to the governance ledger.

Constitutional Constraints:
- FR-1.7: System SHALL emit PetitionReceived event on successful intake
- FR-2.5: System SHALL emit fate event in same transaction as state update
- FR-7.5: System SHALL emit PetitionWithdrawn event when petitioner withdraws (Story 7.3)
- CT-12: Witnessing creates accountability - events are witnessed via ledger
- CT-13: No writes during halt - emission blocked during system halt
- HC-1: Fate transition requires witness event - NO silent fate assignment
- NFR-3.3: Event witnessing: 100% fate events persisted [CRITICAL]

Developer Golden Rules:
1. WITNESS EVERYTHING - All events must be persisted to ledger
2. FAIL GRACEFULLY - Event emission errors logged but don't fail operations (petition.received)
3. FAIL LOUD - Fate events MUST raise on failure (petition.acknowledged/referred/escalated)
4. HALT CHECK - Respect halt state for event emission
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID


class PetitionEventEmitterPort(Protocol):
    """Protocol for petition event emission.

    This port defines the interface for emitting petition lifecycle events
    to observers via the governance ledger.

    Constitutional Guarantees:
    - Events are witnessed via GovernanceLedger (CT-12)
    - Two-phase emission pattern ensures no silent failures
    - Halt state is respected (CT-13)

    Example:
        emitter = PetitionEventEmitterService(ledger, time_authority)
        await emitter.emit_petition_received(
            petition_id=petition_id,
            petition_type="GENERAL",
            realm="default",
            content_hash="base64hash==",
            submitter_id=None,
        )
    """

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

        Constitutional Constraints:
        - FR-1.7: Event SHALL be emitted on successful intake
        - CT-12: Event is witnessed via GovernanceLedger
        - CT-13: Emission blocked during halt

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
        ...

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

        CRITICAL DIFFERENCE from emit_petition_received:
        - This method MUST raise on failure - no graceful degradation
        - If event cannot be witnessed, the caller MUST rollback state change
        - This ensures HC-1: Fate transition requires witness event

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
        ...

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

        Constitutional Constraints:
        - FR-7.5: Event SHALL be emitted when petitioner withdraws
        - CT-12: Event is witnessed via GovernanceLedger
        - CT-13: Emission blocked during halt

        Args:
            petition_id: The withdrawn petition identifier.
            withdrawn_by: UUID of the petitioner who withdrew.
            reason: Optional explanation for withdrawal.

        Returns:
            True if event was emitted successfully, False otherwise.
            False does NOT indicate withdrawal failure - just event emission.
        """
        ...
