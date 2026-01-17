"""Legitimacy transition domain model.

This module defines the LegitimacyTransition record that captures
all transition events between legitimacy bands.

Constitutional Compliance:
- AC7: All transitions recorded with timestamp
- NFR-CONST-04: Transitions include actor attribution
- NFR-AUDIT-04: State transitions are auditable
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from uuid import UUID

from src.domain.governance.legitimacy.legitimacy_band import LegitimacyBand
from src.domain.governance.legitimacy.transition_type import TransitionType


@dataclass(frozen=True)
class LegitimacyTransition:
    """Record of a legitimacy band transition.

    This is an immutable record capturing the details of a transition
    between legitimacy bands. Used for audit trails and state reconstruction.

    Attributes:
        transition_id: Unique identifier for this transition.
        from_band: The band before the transition.
        to_band: The band after the transition.
        transition_type: Whether automatic or acknowledged.
        actor: Identifier of who/what caused transition ("system" or operator UUID).
        triggering_event_id: ID of event that triggered this transition (for automatic).
        acknowledgment_id: ID of acknowledgment record (for acknowledged).
        timestamp: When the transition occurred.
        reason: Human-readable explanation of why transition occurred.
    """

    transition_id: UUID
    from_band: LegitimacyBand
    to_band: LegitimacyBand
    transition_type: TransitionType
    actor: str
    triggering_event_id: Optional[UUID]
    acknowledgment_id: Optional[UUID]
    timestamp: datetime
    reason: str

    def __post_init__(self) -> None:
        """Validate transition record consistency."""
        # Must have triggering event for automatic transitions
        if (
            self.transition_type == TransitionType.AUTOMATIC
            and self.triggering_event_id is None
        ):
            raise ValueError(
                "Automatic transitions must have triggering_event_id"
            )

        # Must have acknowledgment for acknowledged transitions
        if (
            self.transition_type == TransitionType.ACKNOWLEDGED
            and self.acknowledgment_id is None
        ):
            raise ValueError(
                "Acknowledged transitions must have acknowledgment_id"
            )

        # Must have a reason
        if not self.reason or not self.reason.strip():
            raise ValueError("Transition must have a reason")

        # From and to must be different
        if self.from_band == self.to_band:
            raise ValueError("Transition must change bands")

    @property
    def is_decay(self) -> bool:
        """Check if this is a downward (decay) transition.

        Returns:
            True if moving to higher severity band.
        """
        return self.to_band.severity > self.from_band.severity

    @property
    def is_restoration(self) -> bool:
        """Check if this is an upward (restoration) transition.

        Returns:
            True if moving to lower severity band.
        """
        return self.to_band.severity < self.from_band.severity

    @property
    def severity_change(self) -> int:
        """Get the change in severity.

        Returns:
            Positive for decay, negative for restoration.
        """
        return self.to_band.severity - self.from_band.severity

    @property
    def crossed_critical_threshold(self) -> bool:
        """Check if transition crossed into or out of critical state.

        Returns:
            True if transition crossed ERODING/COMPROMISED boundary.
        """
        from_critical = self.from_band.is_critical
        to_critical = self.to_band.is_critical
        return from_critical != to_critical

    @property
    def resulted_in_failure(self) -> bool:
        """Check if this transition resulted in FAILED state.

        Returns:
            True if to_band is FAILED.
        """
        return self.to_band == LegitimacyBand.FAILED
