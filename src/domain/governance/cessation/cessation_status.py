"""Cessation status enumeration for system lifecycle management.

Story: consent-gov-8.1: System Cessation Trigger

This module defines the CessationStatus enumeration for tracking cessation state.
Cessation is a forward-only state machine - there is no going back.

State Transitions:
    ACTIVE → CESSATION_TRIGGERED → CEASED

There is no:
- CANCELLED: Cannot be cancelled once triggered
- PAUSED: Cannot be paused
- RESUMED: Cannot be resumed
- ROLLED_BACK: Cannot be rolled back

Design Principles:
- Irreversibility is structural, not policy
- No methods exist to reverse cessation
- New instance is only path forward
"""

from enum import Enum


class CessationStatus(str, Enum):
    """Status of the system regarding cessation.

    This is a forward-only state machine:
        ACTIVE → CESSATION_TRIGGERED → CEASED

    There are intentionally NO reverse transitions.
    """

    ACTIVE = "active"
    """Normal system operation.

    System is fully operational. New Motion Seeds accepted.
    Execution continues normally.
    """

    CESSATION_TRIGGERED = "cessation_triggered"
    """Cessation in progress - shutdown initiated.

    When triggered:
    - New Motion Seeds are blocked
    - Existing motions continue to completion
    - In-progress work labeled
    - Graceful shutdown proceeds

    This is a transient state - system will reach CEASED.
    """

    CEASED = "ceased"
    """System has ceased operation.

    Final state. No operations possible.
    All records preserved for audit.
    Only read access remains.
    """

    @property
    def is_active(self) -> bool:
        """Check if system is in normal active operation."""
        return self == CessationStatus.ACTIVE

    @property
    def is_ceasing(self) -> bool:
        """Check if cessation is in progress."""
        return self == CessationStatus.CESSATION_TRIGGERED

    @property
    def is_ceased(self) -> bool:
        """Check if system has ceased."""
        return self == CessationStatus.CEASED

    @property
    def is_terminal(self) -> bool:
        """Check if this is a terminal state.

        Only CEASED is terminal.
        """
        return self == CessationStatus.CEASED

    @property
    def allows_new_motions(self) -> bool:
        """Check if new Motion Seeds are allowed.

        Only ACTIVE allows new Motion Seeds.
        """
        return self == CessationStatus.ACTIVE

    @property
    def allows_execution(self) -> bool:
        """Check if execution is allowed.

        ACTIVE: Full execution
        CESSATION_TRIGGERED: Existing only, no new
        CEASED: No execution
        """
        return self in (CessationStatus.ACTIVE, CessationStatus.CESSATION_TRIGGERED)

    def can_transition_to(self, target: "CessationStatus") -> bool:
        """Check if transition to target status is valid.

        Valid transitions (forward-only):
            ACTIVE → CESSATION_TRIGGERED
            CESSATION_TRIGGERED → CEASED

        Args:
            target: Target cessation status.

        Returns:
            True if transition is valid, False otherwise.
        """
        valid_transitions = {
            CessationStatus.ACTIVE: {CessationStatus.CESSATION_TRIGGERED},
            CessationStatus.CESSATION_TRIGGERED: {CessationStatus.CEASED},
            CessationStatus.CEASED: set(),  # No transitions from CEASED
        }
        return target in valid_transitions.get(self, set())
