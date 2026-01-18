"""Complexity Budget Repository port definition (Story 8.6, SC-3, RT-6).

Defines the abstract interface for storing and querying complexity snapshots
and breach events. Infrastructure adapters must implement this protocol.

Constitutional Constraints:
- CT-14: Complexity is a failure vector. Complexity must be budgeted.
- RT-6: Breach = constitutional event, not just alert.

Usage:
    from src.application.ports.complexity_budget_repository import (
        ComplexityBudgetRepositoryPort
    )

    class MyComplexityRepository(ComplexityBudgetRepositoryPort):
        async def save_snapshot(self, snapshot: ComplexitySnapshot) -> None:
            # Implementation...
            pass
"""

from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from src.domain.events.complexity_budget import (
    ComplexityBudgetBreachedPayload,
    ComplexityBudgetEscalatedPayload,
)
from src.domain.models.complexity_budget import ComplexitySnapshot


class ComplexityBudgetRepositoryPort(ABC):
    """Abstract protocol for complexity budget persistence.

    All complexity budget repository implementations must implement this
    interface. This enables dependency inversion and allows the application
    layer to remain independent of specific storage implementations.

    Constitutional Constraint (CT-14):
    Complexity metrics must be tracked historically to detect trends
    and support the complexity budget dashboard.

    Red Team Hardening (RT-6):
    Breach events must be persisted for governance tracking and
    automatic escalation.

    Methods:
        save_snapshot: Store a complexity snapshot
        get_latest_snapshot: Get most recent snapshot
        get_snapshots_in_range: Get snapshots within a date range
        save_breach: Store a breach event
        get_breach: Get a specific breach by ID
        get_unresolved_breaches: Get all unresolved breaches
        resolve_breach: Mark a breach as resolved
        save_escalation: Store an escalation event
        get_escalations_for_breach: Get escalations for a breach
    """

    # Snapshot operations

    @abstractmethod
    async def save_snapshot(self, snapshot: ComplexitySnapshot) -> None:
        """Store a complexity snapshot.

        Args:
            snapshot: The complexity snapshot to store.

        Raises:
            RuntimeError: If storage operation fails.
        """
        ...

    @abstractmethod
    async def get_latest_snapshot(self) -> ComplexitySnapshot | None:
        """Get the most recent complexity snapshot.

        Returns:
            The most recent ComplexitySnapshot, or None if no snapshots exist.

        Raises:
            RuntimeError: If retrieval operation fails.
        """
        ...

    @abstractmethod
    async def get_snapshots_in_range(
        self,
        start: datetime,
        end: datetime,
    ) -> list[ComplexitySnapshot]:
        """Get all snapshots within a date range.

        Used for historical trend analysis on the complexity dashboard.

        Args:
            start: Start of the date range (inclusive).
            end: End of the date range (inclusive).

        Returns:
            List of ComplexitySnapshots within the range, ordered by timestamp.

        Raises:
            RuntimeError: If retrieval operation fails.
        """
        ...

    # Breach operations

    @abstractmethod
    async def save_breach(self, breach: ComplexityBudgetBreachedPayload) -> None:
        """Store a breach event.

        Red Team Hardening (RT-6):
        Breaches are constitutional events that must be tracked for
        governance and escalation.

        Args:
            breach: The breach payload to store.

        Raises:
            RuntimeError: If storage operation fails.
        """
        ...

    @abstractmethod
    async def get_breach(
        self, breach_id: UUID
    ) -> ComplexityBudgetBreachedPayload | None:
        """Get a specific breach by ID.

        Args:
            breach_id: The breach event ID.

        Returns:
            The breach payload, or None if not found.

        Raises:
            RuntimeError: If retrieval operation fails.
        """
        ...

    @abstractmethod
    async def get_unresolved_breaches(self) -> list[ComplexityBudgetBreachedPayload]:
        """Get all unresolved breaches.

        Red Team Hardening (RT-6):
        Used to track breaches that require governance ceremony approval
        and to check for escalation eligibility.

        Returns:
            List of unresolved breach payloads.

        Raises:
            RuntimeError: If retrieval operation fails.
        """
        ...

    @abstractmethod
    async def resolve_breach(
        self,
        breach_id: UUID,
        governance_approval_id: UUID | None = None,
    ) -> bool:
        """Mark a breach as resolved.

        Red Team Hardening (RT-6):
        Resolution should include a governance approval ID if the breach
        was resolved through a governance ceremony.

        Args:
            breach_id: The breach to resolve.
            governance_approval_id: Optional governance ceremony approval ID.

        Returns:
            True if the breach was found and resolved, False if not found.

        Raises:
            RuntimeError: If update operation fails.
        """
        ...

    # Escalation operations

    @abstractmethod
    async def save_escalation(
        self, escalation: ComplexityBudgetEscalatedPayload
    ) -> None:
        """Store an escalation event.

        Red Team Hardening (RT-6):
        Escalations occur when breaches are not resolved within the
        escalation period.

        Args:
            escalation: The escalation payload to store.

        Raises:
            RuntimeError: If storage operation fails.
        """
        ...

    @abstractmethod
    async def get_escalations_for_breach(
        self,
        breach_id: UUID,
    ) -> list[ComplexityBudgetEscalatedPayload]:
        """Get all escalations for a specific breach.

        Args:
            breach_id: The breach to get escalations for.

        Returns:
            List of escalation payloads for the breach, ordered by escalation time.

        Raises:
            RuntimeError: If retrieval operation fails.
        """
        ...
