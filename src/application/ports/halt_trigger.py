"""Halt Trigger port - interface for triggering system halt (Story 3.2).

This port defines the contract for triggering constitutional halt.
The HaltTrigger is invoked when a constitutional crisis is detected
(e.g., fork detection), and triggers immediate system-wide halt.

Constitutional Constraints:
- FR17: System SHALL halt immediately when fork detected
- CT-11: Silent failure destroys legitimacy -> Halt MUST be logged
- CT-13: Integrity outranks availability -> Availability sacrificed
- RT-2: Crisis event MUST be recorded BEFORE halt takes effect

ADR-3: Partition Behavior + Halt Durability
- Story 3.3 will implement dual-channel halt (Redis + DB)
- Story 3.4 will implement sticky halt semantics
- This story (3.2) provides the trigger mechanism

Developer Golden Rule: HALT FIRST
- Check halt state before every operation
- Never catch SystemHaltedError in business logic
"""

from abc import ABC, abstractmethod
from uuid import UUID


class HaltTrigger(ABC):
    """Abstract interface for triggering system halt.

    This port is used by the HaltTriggerService to set the halt state
    after a constitutional crisis is detected and recorded.

    Constitutional Constraints:
    - FR17: System SHALL halt immediately when crisis detected
    - CT-11: Silent failure destroys legitimacy
    - RT-2: Crisis event recorded BEFORE halt

    The crisis_event_id parameter links the halt to the witnessed
    ConstitutionalCrisisEvent that triggered it, providing audit trail.

    Example:
        >>> # Trigger halt after crisis event is witnessed
        >>> await halt_trigger.trigger_halt(
        ...     reason="FR17: Fork detected - 2 conflicting events",
        ...     crisis_event_id=crisis_event_uuid,
        ... )
    """

    @property
    @abstractmethod
    def halt_propagation_timeout_seconds(self) -> float:
        """Timeout for halt propagation across services.

        Per AC1: All write operations must be blocked within 1 second
        of fork detection. This property configures that timeout.

        Returns:
            Timeout in seconds. Default implementations should return 1.0.
        """
        ...

    @abstractmethod
    async def trigger_halt(
        self,
        reason: str,
        crisis_event_id: UUID | None = None,
    ) -> None:
        """Trigger system-wide halt due to constitutional crisis.

        This method is called AFTER the ConstitutionalCrisisEvent has
        been recorded and witnessed (RT-2 requirement). It sets the
        halt state and ensures all write operations are blocked.

        Constitutional Constraint (FR17):
        System SHALL halt immediately when crisis detected.
        No operations continue on corrupted state.

        Args:
            reason: Human-readable reason for halt (e.g., "FR17: Fork detected")
            crisis_event_id: UUID of the witnessed ConstitutionalCrisisEvent.
                           Provides audit trail linking halt to its trigger.

        Note:
            This method should complete within halt_propagation_timeout_seconds.
            If the halt cannot be propagated in time, the implementation
            should still ensure the halt state is set (even if propagation
            to all services takes longer).
        """
        ...

    @abstractmethod
    async def set_halt_state(
        self,
        halted: bool,
        reason: str | None = None,
    ) -> None:
        """Set the halt state directly.

        This method is primarily used for:
        - Testing (setting and clearing halt state)
        - Recovery scenarios (Story 3.4 sticky halt semantics)
        - Manual intervention by keepers (Story 5.x)

        Args:
            halted: True to halt system, False to clear halt
            reason: Reason for state change (required when halted=True)

        Note:
            In production, halts should be triggered via trigger_halt()
            which ensures proper crisis event creation. This method
            provides lower-level access for testing and recovery.
        """
        ...
