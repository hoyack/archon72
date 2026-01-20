"""Auto-escalation executor protocol (Story 5.6, FR-5.1, FR-5.3, CT-12, CT-14).

This module defines the protocol for executing auto-escalation when
co-signer thresholds are reached in the Three Fates petition system.

Constitutional Constraints:
- FR-5.1: System SHALL ESCALATE petition when co-signer threshold reached [P0]
- FR-5.3: System SHALL emit EscalationTriggered event with co-signer_count [P0]
- CT-12: All outputs through witnessing pipeline
- CT-14: Silence must be expensive - auto-escalation ensures collective
         petitions get King attention without deliberation delay

Developer Golden Rules:
1. HALT CHECK FIRST - Check halt state before any writes (CT-13)
2. ATOMIC TRANSITION - State change + event emission in same transaction
3. IDEMPOTENT - Multiple threshold triggers don't cause duplicate escalations
4. WITNESS EVERYTHING - All escalation events must be witnessed (CT-12)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True)
class AutoEscalationResult:
    """Result of an auto-escalation execution attempt.

    Attributes:
        escalation_id: Unique identifier for the escalation (if triggered).
        petition_id: The petition that was escalated.
        triggered: Whether escalation was triggered (False if already escalated).
        event_id: Event ID of the EscalationTriggered event (if emitted).
        timestamp: When the escalation was executed (UTC).
        already_escalated: True if petition was already in ESCALATED state.
        trigger_type: The trigger type (e.g., "CO_SIGNER_THRESHOLD").
        co_signer_count: The co-signer count at time of escalation.
        threshold: The threshold that was reached.
    """

    escalation_id: UUID | None
    petition_id: UUID
    triggered: bool
    event_id: UUID | None
    timestamp: datetime
    already_escalated: bool = False
    trigger_type: str = "CO_SIGNER_THRESHOLD"
    co_signer_count: int = 0
    threshold: int = 0


class AutoEscalationExecutorProtocol(Protocol):
    """Protocol for executing auto-escalation (Story 5.6, FR-5.1, FR-5.3).

    This protocol defines the contract for executing auto-escalation when
    co-signer thresholds are reached. Implementations must handle:

    1. Halt state check (CT-13: reject writes during halt)
    2. Idempotency (check if already escalated)
    3. Atomic state transition (RECEIVED → ESCALATED)
    4. EscalationTriggered event emission (FR-5.3)
    5. Witnessing of all events (CT-12)

    Constitutional Constraints:
    - FR-5.1: System SHALL ESCALATE petition when co-signer threshold reached
    - FR-5.3: System SHALL emit EscalationTriggered event with co_signer_count
    - CT-12: Witnessing creates accountability - all events witnessed
    - CT-13: Halt rejects writes, allows reads
    - CT-14: Silence must be expensive - ensures King attention

    Example:
        >>> executor = AutoEscalationExecutorService(
        ...     petition_repo=petition_repo,
        ...     event_writer=event_writer,
        ...     halt_checker=halt_checker,
        ... )
        >>> result = await executor.execute(
        ...     petition_id=petition_id,
        ...     trigger_type="CO_SIGNER_THRESHOLD",
        ...     co_signer_count=100,
        ...     threshold=100,
        ...     triggered_by=signer_id,
        ... )
        >>> result.triggered
        True
    """

    async def execute(
        self,
        petition_id: UUID,
        trigger_type: str,
        co_signer_count: int,
        threshold: int,
        triggered_by: UUID | None = None,
    ) -> AutoEscalationResult:
        """Execute auto-escalation for a petition.

        This method is called when a co-signer threshold is reached.
        It performs an atomic state transition from RECEIVED to ESCALATED
        and emits an EscalationTriggered event.

        Args:
            petition_id: The petition to escalate.
            trigger_type: The type of trigger (e.g., "CO_SIGNER_THRESHOLD").
            co_signer_count: The co-signer count at time of trigger.
            threshold: The threshold that was reached (e.g., 100 for CESSATION).
            triggered_by: UUID of the signer who triggered threshold (optional).

        Returns:
            AutoEscalationResult with escalation details:
            - triggered=True if escalation was executed
            - triggered=False if already escalated (idempotent)

        Raises:
            SystemHaltedError: System is in halt state (CT-13).
            PetitionNotFoundError: Petition doesn't exist.
            InvalidStateTransitionError: Petition not in valid state for escalation.
        """
        ...

    async def check_already_escalated(
        self,
        petition_id: UUID,
    ) -> bool:
        """Check if a petition has already been escalated.

        This method is used for idempotency - to check if a petition
        has already reached ESCALATED state before attempting escalation.

        Args:
            petition_id: The petition to check.

        Returns:
            True if petition is already in ESCALATED state, False otherwise.

        Raises:
            PetitionNotFoundError: Petition doesn't exist.
        """
        ...
