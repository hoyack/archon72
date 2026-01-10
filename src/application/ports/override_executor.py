"""Override executor port interface (Story 5.1, FR23).

Defines the protocol for executing override actions after they are logged.
The OverrideService calls this port ONLY after successfully logging
the override event (FR23 requirement).

Constitutional Constraints:
- FR23: Override must be logged BEFORE execution
- CT-11: Silent failure destroys legitimacy
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from src.domain.events.override_event import OverrideEventPayload


@dataclass(frozen=True)
class OverrideResult:
    """Result of an override execution.

    Attributes:
        success: Whether the override executed successfully.
        event_id: UUID of the logged override event.
        error_message: Error message if execution failed, None otherwise.
    """

    success: bool
    event_id: UUID
    error_message: str | None = None


class OverrideExecutorPort(Protocol):
    """Protocol for executing override actions.

    This port is called by OverrideService ONLY after the override
    event has been successfully logged to the event store.

    Constitutional Constraint:
    This port MUST NOT be called if the override event fails to write.
    The OverrideService is responsible for enforcing this invariant.

    Implementers should:
    - Execute the override action based on the payload
    - Return success/failure status
    - NOT worry about logging (already done by OverrideService)
    """

    async def execute_override(
        self,
        override_payload: OverrideEventPayload,
        event_id: UUID,
    ) -> OverrideResult:
        """Execute an override action after it has been logged.

        This method is called ONLY after the override event has been
        successfully written to the event store.

        Args:
            override_payload: The validated override payload.
            event_id: UUID of the logged override event (for correlation).

        Returns:
            OverrideResult indicating success or failure.

        Note:
            The override event is already logged at this point.
            Failures here are execution failures, not logging failures.
        """
        ...
