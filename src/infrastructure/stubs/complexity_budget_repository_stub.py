"""Complexity budget repository stub implementation (Story 8.6, CT-14, RT-6, SC-3).

This module provides an in-memory stub implementation of ComplexityBudgetRepositoryPort
for testing and development purposes.

Constitutional Constraints:
- CT-14: Complexity is a failure vector. Complexity must be budgeted.
- RT-6: Red Team hardening - breach = constitutional event, not just alert.
- SC-3: Self-consistency finding - complexity budget dashboard required.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from src.application.ports.complexity_budget_repository import (
    ComplexityBudgetRepositoryPort,
)
from src.domain.events.complexity_budget import (
    ComplexityBudgetBreachedPayload,
    ComplexityBudgetEscalatedPayload,
)
from src.domain.models.complexity_budget import ComplexitySnapshot


class ComplexityBudgetRepositoryStub(ComplexityBudgetRepositoryPort):
    """In-memory stub for complexity budget storage (testing only).

    This stub provides an in-memory implementation of ComplexityBudgetRepositoryPort
    suitable for unit and integration tests.

    The stub stores snapshots in a list ordered by timestamp, breaches in a
    dictionary keyed by breach_id, and escalations similarly.
    """

    def __init__(self) -> None:
        """Initialize the stub with empty storage."""
        self._snapshots: list[ComplexitySnapshot] = []
        self._breaches: dict[UUID, ComplexityBudgetBreachedPayload] = {}
        self._escalations: dict[UUID, ComplexityBudgetEscalatedPayload] = {}
        self._resolved_breaches: set[UUID] = set()

    def clear(self) -> None:
        """Clear all stored data (for test cleanup)."""
        self._snapshots.clear()
        self._breaches.clear()
        self._escalations.clear()
        self._resolved_breaches.clear()

    async def save_snapshot(self, snapshot: ComplexitySnapshot) -> None:
        """Save a complexity snapshot to storage.

        Snapshots are stored in chronological order.

        Args:
            snapshot: The complexity snapshot to save.
        """
        self._snapshots.append(snapshot)
        # Keep snapshots sorted by timestamp
        self._snapshots.sort(key=lambda s: s.timestamp)

    async def get_latest_snapshot(self) -> ComplexitySnapshot | None:
        """Retrieve the most recent complexity snapshot.

        Returns:
            The most recent snapshot if any exist, None otherwise.
        """
        if not self._snapshots:
            return None
        return self._snapshots[-1]

    async def get_snapshots_in_range(
        self,
        start: datetime,
        end: datetime,
    ) -> list[ComplexitySnapshot]:
        """Retrieve complexity snapshots within a date range.

        Args:
            start: Start of the date range (inclusive).
            end: End of the date range (inclusive).

        Returns:
            List of snapshots within the date range, ordered by timestamp.
        """
        return [s for s in self._snapshots if start <= s.timestamp <= end]

    async def save_breach(self, breach: ComplexityBudgetBreachedPayload) -> None:
        """Save a complexity breach event (CT-14, RT-6).

        Breach events are constitutional events per RT-6 and must be persisted.

        Args:
            breach: The breach event payload to save.
        """
        self._breaches[breach.breach_id] = breach

    async def get_breach(
        self,
        breach_id: UUID,
    ) -> ComplexityBudgetBreachedPayload | None:
        """Retrieve a specific breach event by ID.

        Args:
            breach_id: The unique identifier of the breach event.

        Returns:
            The breach event payload if found, None otherwise.
        """
        return self._breaches.get(breach_id)

    # Alias for compatibility
    async def get_breach_by_id(
        self,
        breach_id: UUID,
    ) -> ComplexityBudgetBreachedPayload | None:
        """Alias for get_breach (for backwards compatibility)."""
        return await self.get_breach(breach_id)

    async def get_all_breaches(self) -> list[ComplexityBudgetBreachedPayload]:
        """Retrieve all breach events.

        Returns:
            List of all stored breach events, ordered by breached_at timestamp.
        """
        breaches = list(self._breaches.values())
        return sorted(breaches, key=lambda b: b.breached_at)

    async def get_unresolved_breaches(self) -> list[ComplexityBudgetBreachedPayload]:
        """Retrieve all unresolved breach events (RT-6).

        Unresolved breaches are those that haven't been approved via
        governance ceremony.

        Returns:
            List of unresolved breach events, ordered by breached_at timestamp.
        """
        unresolved = [
            b
            for b in self._breaches.values()
            if b.breach_id not in self._resolved_breaches
        ]
        return sorted(unresolved, key=lambda b: b.breached_at)

    async def resolve_breach(
        self,
        breach_id: UUID,
        governance_approval_id: UUID | None = None,
    ) -> bool:
        """Mark a breach as resolved via governance ceremony (RT-6).

        Args:
            breach_id: The breach ID to mark as resolved.
            governance_approval_id: Optional governance ceremony approval ID.

        Returns:
            True if breach was found and marked, False otherwise.
        """
        if breach_id not in self._breaches:
            return False
        self._resolved_breaches.add(breach_id)
        return True

    # Alias for compatibility
    async def mark_breach_resolved(self, breach_id: UUID) -> bool:
        """Alias for resolve_breach (for backwards compatibility)."""
        return await self.resolve_breach(breach_id)

    async def is_breach_resolved(self, breach_id: UUID) -> bool:
        """Check if a breach has been resolved.

        Args:
            breach_id: The breach ID to check.

        Returns:
            True if breach is resolved, False otherwise.
        """
        return breach_id in self._resolved_breaches

    async def save_escalation(
        self,
        escalation: ComplexityBudgetEscalatedPayload,
    ) -> None:
        """Save a complexity escalation event (RT-6).

        Escalation events are created when breaches remain unresolved
        beyond the escalation period.

        Args:
            escalation: The escalation event payload to save.
        """
        self._escalations[escalation.escalation_id] = escalation

    async def get_escalation_by_id(
        self,
        escalation_id: UUID,
    ) -> ComplexityBudgetEscalatedPayload | None:
        """Retrieve a specific escalation event by ID.

        Args:
            escalation_id: The unique identifier of the escalation event.

        Returns:
            The escalation event payload if found, None otherwise.
        """
        return self._escalations.get(escalation_id)

    async def get_escalations_for_breach(
        self,
        breach_id: UUID,
    ) -> list[ComplexityBudgetEscalatedPayload]:
        """Retrieve all escalations for a specific breach.

        Args:
            breach_id: The breach ID to find escalations for.

        Returns:
            List of escalation events for the breach, ordered by escalated_at.
        """
        escalations = [
            e for e in self._escalations.values() if e.breach_id == breach_id
        ]
        return sorted(escalations, key=lambda e: e.escalated_at)

    async def get_all_escalations(self) -> list[ComplexityBudgetEscalatedPayload]:
        """Retrieve all escalation events.

        Returns:
            List of all stored escalation events, ordered by escalated_at.
        """
        escalations = list(self._escalations.values())
        return sorted(escalations, key=lambda e: e.escalated_at)

    # Test helper methods (not part of protocol)

    def get_snapshot_count(self) -> int:
        """Get total number of stored snapshots."""
        return len(self._snapshots)

    def get_breach_count(self) -> int:
        """Get total number of stored breaches."""
        return len(self._breaches)

    def get_resolved_count(self) -> int:
        """Get number of resolved breaches."""
        return len(self._resolved_breaches)

    def get_escalation_count(self) -> int:
        """Get total number of stored escalations."""
        return len(self._escalations)

    def add_snapshot(self, snapshot: ComplexitySnapshot) -> None:
        """Synchronously add a snapshot (for test setup)."""
        self._snapshots.append(snapshot)
        self._snapshots.sort(key=lambda s: s.timestamp)

    def add_breach(self, breach: ComplexityBudgetBreachedPayload) -> None:
        """Synchronously add a breach (for test setup)."""
        self._breaches[breach.breach_id] = breach

    def add_escalation(self, escalation: ComplexityBudgetEscalatedPayload) -> None:
        """Synchronously add an escalation (for test setup)."""
        self._escalations[escalation.escalation_id] = escalation
