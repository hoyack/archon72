"""Port interface for legitimacy band operations.

This module defines the LegitimacyPort protocol that specifies the
interface for legitimacy band persistence and retrieval.

Constitutional Compliance:
- AC3: Current band tracked and queryable
- AC4: Band state queryable by any participant
- NFR-AUDIT-04: State transitions are auditable
"""

from datetime import datetime
from typing import Protocol

from src.domain.governance.legitimacy.legitimacy_band import LegitimacyBand
from src.domain.governance.legitimacy.legitimacy_state import LegitimacyState
from src.domain.governance.legitimacy.legitimacy_transition import (
    LegitimacyTransition,
)


class LegitimacyPort(Protocol):
    """Port for legitimacy band operations.

    This protocol defines the interface for:
    - Querying current legitimacy state
    - Recording transitions
    - Retrieving transition history

    Implementations must ensure atomicity and consistency of state.
    """

    async def get_current_band(self) -> LegitimacyBand:
        """Get the current legitimacy band.

        This is the simplest query - just returns the current band
        without additional state information.

        Returns:
            The current LegitimacyBand.
        """
        ...

    async def get_legitimacy_state(self) -> LegitimacyState:
        """Get the full legitimacy state including metadata.

        Returns the complete state including when the current band
        was entered, violation count, and last transition details.

        Returns:
            The current LegitimacyState.
        """
        ...

    async def get_transition_history(
        self,
        since: datetime | None = None,
        limit: int | None = None,
    ) -> list[LegitimacyTransition]:
        """Get transition history.

        Returns a list of past transitions, optionally filtered by time.
        Results are ordered from oldest to newest.

        Args:
            since: Only return transitions after this time.
            limit: Maximum number of transitions to return.

        Returns:
            List of LegitimacyTransition records.
        """
        ...

    async def record_transition(
        self,
        transition: LegitimacyTransition,
    ) -> None:
        """Record a transition and update current state.

        This atomically:
        1. Appends the transition to history
        2. Updates the current state to reflect the transition

        Args:
            transition: The transition record to persist.

        Raises:
            InvalidTransitionError: If transition violates rules.
        """
        ...

    async def get_state_at(
        self,
        timestamp: datetime,
    ) -> LegitimacyState | None:
        """Get the legitimacy state at a specific point in time.

        Useful for historical queries and audit trails.

        Args:
            timestamp: The point in time to query.

        Returns:
            The LegitimacyState at that time, or None if before tracking started.
        """
        ...

    async def get_violation_count(self) -> int:
        """Get the current violation count.

        Returns:
            Number of violations that have contributed to decay.
        """
        ...

    async def initialize_state(
        self,
        initial_band: LegitimacyBand,
        timestamp: datetime,
    ) -> LegitimacyState:
        """Initialize the legitimacy state (first-time setup).

        Should only be called once when the system starts tracking
        legitimacy. Typically starts at STABLE.

        Args:
            initial_band: The starting band (usually STABLE).
            timestamp: When tracking begins.

        Returns:
            The initial LegitimacyState.

        Raises:
            RuntimeError: If state already exists.
        """
        ...


class LegitimacyQueryPort(Protocol):
    """Read-only port for legitimacy queries.

    This is a subset of LegitimacyPort that only allows read operations.
    Useful for participants who need to check state but cannot modify it.
    """

    async def get_current_band(self) -> LegitimacyBand:
        """Get the current legitimacy band.

        Returns:
            The current LegitimacyBand.
        """
        ...

    async def get_legitimacy_state(self) -> LegitimacyState:
        """Get the full legitimacy state.

        Returns:
            The current LegitimacyState.
        """
        ...

    async def get_transition_history(
        self,
        since: datetime | None = None,
        limit: int | None = None,
    ) -> list[LegitimacyTransition]:
        """Get transition history.

        Args:
            since: Only return transitions after this time.
            limit: Maximum number of transitions to return.

        Returns:
            List of LegitimacyTransition records.
        """
        ...
