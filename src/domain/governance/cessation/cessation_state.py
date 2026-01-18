"""Cessation state domain model for system lifecycle management.

Story: consent-gov-8.1: System Cessation Trigger

This module defines CessationState - the current state of the cessation
process including status, trigger details, and operational flags.

Key Design:
- Immutable (frozen dataclass)
- Combines status with operational state
- Tracks motion blocking and execution halt
- Tracks in-flight operation count
"""

from dataclasses import dataclass

from src.domain.governance.cessation.cessation_status import CessationStatus
from src.domain.governance.cessation.cessation_trigger import CessationTrigger


@dataclass(frozen=True)
class CessationState:
    """Current state of the cessation process.

    This value object captures the full cessation state including:
    - Current status (ACTIVE, CESSATION_TRIGGERED, CEASED)
    - Trigger details (if cessation has been triggered)
    - Operational flags (motions blocked, execution halted)
    - In-flight operation tracking

    Attributes:
        status: Current cessation status.
        trigger: CessationTrigger if cessation has been triggered, None otherwise.
        motions_blocked: Whether new motions are blocked.
        execution_halted: Whether execution has been halted.
        in_flight_count: Number of in-flight operations being gracefully completed.

    Example:
        >>> state = CessationState.active()
        >>> assert state.status.is_active
        >>> assert not state.motions_blocked
    """

    status: CessationStatus
    """Current cessation status."""

    trigger: CessationTrigger | None
    """CessationTrigger if triggered, None if still active."""

    motions_blocked: bool
    """Whether new motions are blocked.

    True when cessation is triggered or complete.
    False only when system is active.
    """

    execution_halted: bool
    """Whether execution has been halted.

    True when cessation is complete.
    During CESSATION_TRIGGERED, existing operations may continue.
    """

    in_flight_count: int
    """Number of in-flight operations being gracefully completed.

    Starts at some positive value when cessation is triggered.
    Decreases as operations complete.
    Reaches 0 when system reaches CEASED status.
    """

    @classmethod
    def active(cls) -> "CessationState":
        """Create state representing normal active operation.

        Returns:
            CessationState with ACTIVE status and all flags clear.
        """
        return cls(
            status=CessationStatus.ACTIVE,
            trigger=None,
            motions_blocked=False,
            execution_halted=False,
            in_flight_count=0,
        )

    @classmethod
    def triggered(
        cls,
        trigger: CessationTrigger,
        in_flight_count: int = 0,
    ) -> "CessationState":
        """Create state representing cessation in progress.

        Args:
            trigger: The cessation trigger record.
            in_flight_count: Number of operations being completed.

        Returns:
            CessationState with CESSATION_TRIGGERED status.
        """
        return cls(
            status=CessationStatus.CESSATION_TRIGGERED,
            trigger=trigger,
            motions_blocked=True,
            execution_halted=False,  # Existing operations continue
            in_flight_count=in_flight_count,
        )

    @classmethod
    def ceased(cls, trigger: CessationTrigger) -> "CessationState":
        """Create state representing completed cessation.

        Args:
            trigger: The cessation trigger record.

        Returns:
            CessationState with CEASED status.
        """
        return cls(
            status=CessationStatus.CEASED,
            trigger=trigger,
            motions_blocked=True,
            execution_halted=True,
            in_flight_count=0,
        )

    @property
    def is_active(self) -> bool:
        """Check if system is in normal active operation."""
        return self.status.is_active

    @property
    def is_ceasing(self) -> bool:
        """Check if cessation is in progress."""
        return self.status.is_ceasing

    @property
    def is_ceased(self) -> bool:
        """Check if system has ceased."""
        return self.status.is_ceased

    def with_in_flight_count(self, count: int) -> "CessationState":
        """Return new state with updated in-flight count.

        Args:
            count: New in-flight operation count.

        Returns:
            New CessationState with updated count.
        """
        return CessationState(
            status=self.status,
            trigger=self.trigger,
            motions_blocked=self.motions_blocked,
            execution_halted=self.execution_halted,
            in_flight_count=count,
        )

    def to_dict(self) -> dict:
        """Serialize to dictionary.

        Returns:
            Dictionary representation suitable for JSON serialization.
        """
        return {
            "status": self.status.value,
            "trigger": self.trigger.to_dict() if self.trigger else None,
            "motions_blocked": self.motions_blocked,
            "execution_halted": self.execution_halted,
            "in_flight_count": self.in_flight_count,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CessationState":
        """Deserialize from dictionary.

        Args:
            data: Dictionary from to_dict().

        Returns:
            Reconstructed CessationState.
        """
        return cls(
            status=CessationStatus(data["status"]),
            trigger=CessationTrigger.from_dict(data["trigger"])
            if data.get("trigger")
            else None,
            motions_blocked=data["motions_blocked"],
            execution_halted=data["execution_halted"],
            in_flight_count=data["in_flight_count"],
        )
