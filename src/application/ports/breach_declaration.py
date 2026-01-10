"""Breach declaration port (Story 6.1, FR30).

This module defines the interface for declaring constitutional breaches.

Constitutional Constraints:
- FR30: Breach declarations SHALL create constitutional events with
        breach_type, violated_requirement, detection_timestamp
- CT-11: Silent failure destroys legitimacy -> HALT CHECK FIRST
- CT-12: Witnessing creates accountability -> All breaches must be witnessed
"""

from __future__ import annotations

from typing import Any, Optional, Protocol
from uuid import UUID

from src.domain.events.breach import BreachEventPayload, BreachSeverity, BreachType


class BreachDeclarationProtocol(Protocol):
    """Protocol for declaring constitutional breaches (FR30).

    This protocol defines the interface for creating breach declaration
    events. Implementations must ensure all breaches are witnessed (CT-12)
    and halt state is checked before declaration (CT-11).

    Constitutional Constraint (FR30):
    Breach declarations SHALL create constitutional events with
    breach_type, violated_requirement, detection_timestamp.
    """

    async def declare_breach(
        self,
        breach_type: BreachType,
        violated_requirement: str,
        severity: BreachSeverity,
        details: dict[str, Any],
        source_event_id: Optional[UUID] = None,
    ) -> BreachEventPayload:
        """Declare a constitutional breach (FR30).

        Constitutional Constraints:
        - CT-11: HALT CHECK FIRST - System halt is checked before declaration
        - CT-12: Breach is witnessed before being recorded

        Args:
            breach_type: Category of the constitutional violation.
            violated_requirement: The FR/CT/NFR violated (e.g., "FR30", "CT-11").
            severity: Alert severity level.
            details: Additional context about the breach.
            source_event_id: Optional ID of the event that triggered this breach.

        Returns:
            The created BreachEventPayload.

        Raises:
            SystemHaltedError: If system is halted (CT-11).
            BreachDeclarationError: If declaration fails.
        """
        ...

    async def get_breach_by_id(
        self,
        breach_id: UUID,
    ) -> Optional[BreachEventPayload]:
        """Retrieve a specific breach by ID.

        Constitutional Constraint (CT-11):
        HALT CHECK FIRST - System halt is checked before query.

        Args:
            breach_id: The unique identifier of the breach.

        Returns:
            The breach event payload if found, None otherwise.

        Raises:
            SystemHaltedError: If system is halted (CT-11).
            BreachQueryError: If query fails.
        """
        ...
