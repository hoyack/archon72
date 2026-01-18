"""Legitimacy state domain model.

This module defines the LegitimacyState value object that tracks the
current legitimacy band and related metadata.

Constitutional Compliance:
- FR28: Current band tracked and queryable
- AC3: Current band tracked and queryable
- AC7: Transitions recorded with timestamp
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from src.domain.governance.legitimacy.legitimacy_band import LegitimacyBand
from src.domain.governance.legitimacy.transition_type import TransitionType


@dataclass(frozen=True)
class LegitimacyState:
    """Current legitimacy state of the system.

    This is an immutable value object representing the current state
    of system legitimacy. All state changes create new instances.

    Attributes:
        current_band: The current legitimacy band.
        entered_at: When the system entered this band.
        violation_count: Running count of violations contributing to decay.
        last_triggering_event_id: ID of event that caused last transition.
        last_transition_type: Type of the last transition (automatic/acknowledged).
    """

    current_band: LegitimacyBand
    entered_at: datetime
    violation_count: int
    last_triggering_event_id: UUID | None
    last_transition_type: TransitionType

    def __post_init__(self) -> None:
        """Validate state consistency."""
        if self.violation_count < 0:
            raise ValueError("violation_count cannot be negative")

    @property
    def is_healthy(self) -> bool:
        """Check if current state indicates healthy operation.

        Returns:
            True if current band is STABLE or STRAINED.
        """
        return self.current_band.is_healthy

    @property
    def is_critical(self) -> bool:
        """Check if current state indicates critical issues.

        Returns:
            True if current band is COMPROMISED or FAILED.
        """
        return self.current_band.is_critical

    @property
    def is_terminal(self) -> bool:
        """Check if system has reached terminal state.

        Returns:
            True if current band is FAILED.
        """
        return self.current_band.is_terminal

    @property
    def severity(self) -> int:
        """Get current severity level.

        Returns:
            Integer 0-4 corresponding to current band.
        """
        return self.current_band.severity

    def with_new_band(
        self,
        new_band: LegitimacyBand,
        entered_at: datetime,
        triggering_event_id: UUID | None,
        transition_type: TransitionType,
        increment_violations: bool = False,
    ) -> "LegitimacyState":
        """Create new state with updated band.

        Args:
            new_band: The new legitimacy band.
            entered_at: When the transition occurred.
            triggering_event_id: ID of event causing transition.
            transition_type: Type of transition.
            increment_violations: Whether to increment violation count.

        Returns:
            New LegitimacyState with updated values.
        """
        new_violation_count = self.violation_count
        if increment_violations:
            new_violation_count += 1

        return LegitimacyState(
            current_band=new_band,
            entered_at=entered_at,
            violation_count=new_violation_count,
            last_triggering_event_id=triggering_event_id,
            last_transition_type=transition_type,
        )

    @classmethod
    def initial(cls, entered_at: datetime) -> "LegitimacyState":
        """Create initial state (STABLE with no violations).

        Args:
            entered_at: When the system started.

        Returns:
            Initial LegitimacyState at STABLE band.
        """
        return cls(
            current_band=LegitimacyBand.STABLE,
            entered_at=entered_at,
            violation_count=0,
            last_triggering_event_id=None,
            last_transition_type=TransitionType.AUTOMATIC,
        )
