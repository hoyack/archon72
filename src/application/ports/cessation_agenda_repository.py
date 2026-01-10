"""Cessation agenda repository port (Story 7.1, FR37-FR38, RT-4).

This module defines the repository interface for storing and querying
cessation agenda placement events.

Constitutional Constraints:
- FR37: 3 consecutive integrity failures triggers agenda placement
- FR38: Anti-success alert sustained 90 days triggers agenda placement
- RT-4: 5 failures in 90-day window triggers agenda placement
- CT-11: Silent failure destroys legitimacy -> Query failures must not be silent
- CT-12: Witnessing creates accountability -> All placements were witnessed
"""

from __future__ import annotations

from typing import Optional, Protocol
from uuid import UUID

from src.domain.events.cessation_agenda import (
    AgendaTriggerType,
    CessationAgendaPlacementEventPayload,
)


class CessationAgendaRepositoryProtocol(Protocol):
    """Protocol for cessation agenda placement storage (FR37-FR38, RT-4).

    This protocol defines the interface for storing agenda placement
    events and supporting idempotent trigger checks.

    Constitutional Constraint (CT-11):
    Query failures must not be silent - raise specific errors.

    Constitutional Constraint (CT-12):
    All stored placements are assumed to have been witnessed
    via the EventWriterService before being saved here.
    """

    async def save_agenda_placement(
        self,
        placement: CessationAgendaPlacementEventPayload,
    ) -> None:
        """Save an agenda placement event to storage.

        Constitutional Constraint:
        The placement event is assumed to have already been witnessed
        via the EventWriterService before being saved here.

        Args:
            placement: The agenda placement payload to save.

        Raises:
            CessationAgendaRepositoryError: If save fails.
        """
        ...

    async def get_by_id(
        self,
        placement_id: UUID,
    ) -> Optional[CessationAgendaPlacementEventPayload]:
        """Retrieve a specific agenda placement by ID.

        Args:
            placement_id: The unique identifier of the placement.

        Returns:
            The placement payload if found, None otherwise.

        Raises:
            CessationAgendaRepositoryError: If query fails.
        """
        ...

    async def get_active_placement(
        self,
    ) -> Optional[CessationAgendaPlacementEventPayload]:
        """Get the currently active agenda placement, if any.

        An agenda placement is "active" if it hasn't been resolved
        by a Conclave decision yet.

        Returns:
            The active placement or None if no active placement.

        Raises:
            CessationAgendaRepositoryError: If query fails.
        """
        ...

    async def get_placement_by_trigger(
        self,
        trigger_type: AgendaTriggerType,
    ) -> Optional[CessationAgendaPlacementEventPayload]:
        """Get the most recent placement for a specific trigger type.

        This supports idempotent checks - if a placement already exists
        for this trigger type, we don't create a duplicate.

        Args:
            trigger_type: The type of trigger to search for.

        Returns:
            The placement for this trigger type, or None if none exists.

        Raises:
            CessationAgendaRepositoryError: If query fails.
        """
        ...

    async def has_active_placement_for_trigger(
        self,
        trigger_type: AgendaTriggerType,
    ) -> bool:
        """Check if an active placement exists for a trigger type (AC4).

        This supports idempotent trigger evaluation - prevents
        duplicate agenda placements.

        Args:
            trigger_type: The type of trigger to check.

        Returns:
            True if an active placement exists for this trigger, False otherwise.

        Raises:
            CessationAgendaRepositoryError: If query fails.
        """
        ...

    async def list_all_placements(
        self,
    ) -> list[CessationAgendaPlacementEventPayload]:
        """List all agenda placements.

        Returns:
            List of all placements, ordered by trigger_timestamp.

        Raises:
            CessationAgendaRepositoryError: If query fails.
        """
        ...

    async def mark_placement_resolved(
        self,
        placement_id: UUID,
        resolution_event_id: UUID,
    ) -> None:
        """Mark a placement as resolved by a Conclave decision.

        Args:
            placement_id: The placement to mark as resolved.
            resolution_event_id: Reference to the resolution event.

        Raises:
            CessationAgendaRepositoryError: If update fails.
        """
        ...
