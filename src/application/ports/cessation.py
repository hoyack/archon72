"""Cessation consideration port (Story 6.3, FR32).

This module defines the protocol for cessation consideration operations.

Constitutional Constraints:
- FR32: >10 unacknowledged breaches in 90 days SHALL trigger cessation consideration
- CT-11: Silent failure destroys legitimacy -> HALT CHECK FIRST
- CT-12: Witnessing creates accountability -> All events MUST be witnessed
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Protocol, runtime_checkable
from uuid import UUID

if TYPE_CHECKING:
    from src.domain.events.cessation import (
        CessationConsiderationEventPayload,
        CessationDecision,
        CessationDecisionEventPayload,
    )
    from src.domain.models.breach_count_status import BreachCountStatus


@runtime_checkable
class CessationConsiderationProtocol(Protocol):
    """Protocol for cessation consideration operations (FR32).

    This protocol defines the interface for:
    - Triggering cessation consideration when thresholds are exceeded
    - Recording Conclave decisions on cessation considerations
    - Querying breach count status and trajectory

    Constitutional Constraints:
    - FR32: >10 unacknowledged breaches in 90 days SHALL trigger cessation
    - CT-11: HALT CHECK FIRST at every operation
    - CT-12: All cessation events MUST be witnessed
    """

    async def trigger_cessation_consideration(
        self,
    ) -> Optional[CessationConsiderationEventPayload]:
        """Check thresholds and trigger cessation consideration if exceeded.

        This method is idempotent and designed for periodic invocation:
        - If count > 10 AND no active consideration: creates consideration
        - If count <= 10 OR active consideration exists: returns None

        Constitutional Constraints:
        - FR32: Triggers at >10 unacknowledged breaches in 90 days
        - CT-11: HALT CHECK FIRST
        - CT-12: Creates witnessed event via EventWriterService

        Returns:
            CessationConsiderationEventPayload if consideration triggered,
            None if below threshold or consideration already active.

        Raises:
            SystemHaltedError: If system is halted (CT-11).
        """
        ...

    async def record_decision(
        self,
        consideration_id: UUID,
        decision: CessationDecision,
        decided_by: str,
        rationale: str,
    ) -> CessationDecisionEventPayload:
        """Record a Conclave decision on a cessation consideration.

        Constitutional Constraints:
        - FR32: Decision must be recorded for accountability
        - CT-11: HALT CHECK FIRST
        - CT-12: Creates witnessed event via EventWriterService

        Args:
            consideration_id: The ID of the consideration being decided.
            decision: The decision choice (PROCEED_TO_VOTE, DISMISS, DEFER).
            decided_by: Attribution of decision maker.
            rationale: Reason for the decision.

        Returns:
            CessationDecisionEventPayload for the recorded decision.

        Raises:
            SystemHaltedError: If system is halted (CT-11).
            CessationConsiderationNotFoundError: If consideration doesn't exist.
            InvalidCessationDecisionError: If decision already recorded.
        """
        ...

    async def get_current_breach_count(self) -> BreachCountStatus:
        """Get current unacknowledged breach count status.

        Constitutional Constraints:
        - FR32: Provides visibility into breach counts
        - CT-11: HALT CHECK FIRST

        Returns:
            BreachCountStatus with count, trajectory, and alert thresholds.

        Raises:
            SystemHaltedError: If system is halted (CT-11).
        """
        ...

    async def is_cessation_consideration_active(self) -> bool:
        """Check if a cessation consideration is currently active.

        A consideration is active if it exists and has not received
        a Conclave decision yet.

        Constitutional Constraints:
        - CT-11: HALT CHECK FIRST

        Returns:
            True if an active consideration exists, False otherwise.

        Raises:
            SystemHaltedError: If system is halted (CT-11).
        """
        ...
