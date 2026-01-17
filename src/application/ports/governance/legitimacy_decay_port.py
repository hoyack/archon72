"""Port interface for automatic legitimacy decay operations.

This module defines the LegitimacyDecayPort protocol that specifies the
interface for processing violations and triggering automatic legitimacy decay.

Constitutional Compliance:
- FR29: System can auto-transition legitimacy downward based on violation events
- AC2: Transition includes triggering event reference
- AC5: System actor for automatic transitions
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Protocol
from uuid import UUID

from src.domain.governance.legitimacy.legitimacy_state import LegitimacyState
from src.domain.governance.legitimacy.legitimacy_transition import (
    LegitimacyTransition,
)
from src.domain.governance.legitimacy.violation_severity import ViolationSeverity


@dataclass(frozen=True)
class DecayResult:
    """Result of processing a violation for legitimacy decay.

    Attributes:
        transition_occurred: True if legitimacy band actually changed.
        new_state: The new legitimacy state (or current if no change).
        violation_event_id: ID of the violation event that triggered this.
        severity: The severity level determined for this violation.
        bands_dropped: Number of bands the legitimacy dropped (0 if no change).
    """

    transition_occurred: bool
    new_state: Optional[LegitimacyState]
    violation_event_id: UUID
    severity: ViolationSeverity
    bands_dropped: int


class LegitimacyDecayPort(Protocol):
    """Port for automatic legitimacy decay operations.

    This protocol defines the interface for:
    - Processing violation events and calculating decay
    - Recording decay transitions
    - Querying decay history

    Implementations must ensure automatic decay when violations occur,
    with proper event attribution and audit trails.
    """

    async def process_violation(
        self,
        violation_event_id: UUID,
        violation_type: str,
    ) -> DecayResult:
        """Process a violation event and decay legitimacy if needed.

        This method:
        1. Determines violation severity from violation_type
        2. Calculates target band based on severity
        3. Creates and records transition if band changes
        4. Emits band_decreased event

        Args:
            violation_event_id: Unique ID of the violation event.
            violation_type: Type string (e.g., "coercion.filter_blocked").

        Returns:
            DecayResult with transition details.

        Note:
            If the system is already in FAILED state, no transition
            occurs (FAILED is terminal).
        """
        ...

    async def get_decay_history(
        self,
        since: Optional[datetime] = None,
        limit: Optional[int] = None,
    ) -> list[LegitimacyTransition]:
        """Get history of automatic decay transitions.

        Returns only AUTOMATIC type transitions (decay events).

        Args:
            since: Only return transitions after this time.
            limit: Maximum number of transitions to return.

        Returns:
            List of LegitimacyTransition records for decay events.
        """
        ...

    async def get_decay_count(self) -> int:
        """Get total number of decay events that have occurred.

        Returns:
            Count of automatic decay transitions.
        """
        ...
