"""Cessation agenda repository stub implementation (Story 7.1, FR37-FR38, RT-4).

This module provides an in-memory stub implementation of CessationAgendaRepositoryProtocol
for testing and development purposes.

Constitutional Constraints:
- FR37: 3 consecutive integrity failures triggers agenda placement
- FR38: Anti-success alert sustained 90 days triggers agenda placement
- RT-4: 5 failures in 90-day window triggers agenda placement
"""

from __future__ import annotations

from uuid import UUID

from src.application.ports.cessation_agenda_repository import (
    CessationAgendaRepositoryProtocol,
)
from src.domain.events.cessation_agenda import (
    AgendaTriggerType,
    CessationAgendaPlacementEventPayload,
)


class CessationAgendaRepositoryStub(CessationAgendaRepositoryProtocol):
    """In-memory stub for cessation agenda placement storage (testing only).

    This stub provides an in-memory implementation of CessationAgendaRepositoryProtocol
    suitable for unit and integration tests.

    The stub stores placements in dictionaries for efficient lookup by ID and trigger type.
    """

    def __init__(self) -> None:
        """Initialize the stub with empty storage."""
        self._placements: dict[UUID, CessationAgendaPlacementEventPayload] = {}
        self._by_trigger: dict[
            AgendaTriggerType, CessationAgendaPlacementEventPayload
        ] = {}
        self._resolved: set[UUID] = set()

    def clear(self) -> None:
        """Clear all stored placements (for test cleanup)."""
        self._placements.clear()
        self._by_trigger.clear()
        self._resolved.clear()

    async def save_agenda_placement(
        self,
        placement: CessationAgendaPlacementEventPayload,
    ) -> None:
        """Save an agenda placement event to storage.

        Args:
            placement: The agenda placement payload to save.
        """
        self._placements[placement.placement_id] = placement
        self._by_trigger[placement.trigger_type] = placement

    async def get_by_id(
        self,
        placement_id: UUID,
    ) -> CessationAgendaPlacementEventPayload | None:
        """Retrieve a specific agenda placement by ID.

        Args:
            placement_id: The unique identifier of the placement.

        Returns:
            The placement payload if found, None otherwise.
        """
        return self._placements.get(placement_id)

    async def get_active_placement(
        self,
    ) -> CessationAgendaPlacementEventPayload | None:
        """Get the currently active agenda placement, if any.

        An agenda placement is "active" if it hasn't been resolved
        by a Conclave decision yet.

        Returns:
            The active placement or None if no active placement.
        """
        # Return the first non-resolved placement
        for placement_id, placement in self._placements.items():
            if placement_id not in self._resolved:
                return placement
        return None

    async def get_placement_by_trigger(
        self,
        trigger_type: AgendaTriggerType,
    ) -> CessationAgendaPlacementEventPayload | None:
        """Get the most recent placement for a specific trigger type.

        Args:
            trigger_type: The type of trigger to search for.

        Returns:
            The placement for this trigger type, or None if none exists.
        """
        return self._by_trigger.get(trigger_type)

    async def has_active_placement_for_trigger(
        self,
        trigger_type: AgendaTriggerType,
    ) -> bool:
        """Check if an active placement exists for a trigger type (AC4).

        Args:
            trigger_type: The type of trigger to check.

        Returns:
            True if an active placement exists for this trigger, False otherwise.
        """
        placement = self._by_trigger.get(trigger_type)
        if placement is None:
            return False
        return placement.placement_id not in self._resolved

    async def list_all_placements(
        self,
    ) -> list[CessationAgendaPlacementEventPayload]:
        """List all agenda placements.

        Returns:
            List of all placements, ordered by trigger_timestamp.
        """
        placements = list(self._placements.values())
        return sorted(placements, key=lambda p: p.trigger_timestamp)

    async def mark_placement_resolved(
        self,
        placement_id: UUID,
        resolution_event_id: UUID,
    ) -> None:
        """Mark a placement as resolved by a Conclave decision.

        Args:
            placement_id: The placement to mark as resolved.
            resolution_event_id: Reference to the resolution event.
        """
        self._resolved.add(placement_id)

    # Test helper methods (not part of protocol)

    def add_placement(
        self,
        placement: CessationAgendaPlacementEventPayload,
        resolved: bool = False,
    ) -> None:
        """Add a placement directly (for testing).

        Args:
            placement: The placement to add.
            resolved: Whether to mark it as resolved.
        """
        self._placements[placement.placement_id] = placement
        self._by_trigger[placement.trigger_type] = placement
        if resolved:
            self._resolved.add(placement.placement_id)

    def get_placement_count(self) -> int:
        """Get total number of stored placements."""
        return len(self._placements)

    def get_resolved_count(self) -> int:
        """Get number of resolved placements."""
        return len(self._resolved)

    def is_resolved(self, placement_id: UUID) -> bool:
        """Check if a specific placement is resolved."""
        return placement_id in self._resolved
