"""Notification preference repository port (Story 7.2, FR-7.3).

Protocol defining the interface for notification preference storage operations.

Constitutional Constraints:
- FR-7.3: System SHALL notify Observer on fate assignment
- CT-12: Witnessing creates accountability (service layer handles)
- D7: RFC 7807 error responses for invalid preferences

Developer Golden Rules:
1. Protocol-based DI - all implementations through ports
2. HALT CHECK FIRST - Service layer checks halt, not repository
3. WITNESS EVERYTHING - Repository stores, service witnesses
4. FAIL LOUD - Repository raises on errors
5. READS DURING HALT - Repository reads work during halt (CT-13)
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from src.domain.models.notification_preference import NotificationPreference


class NotificationPreferenceNotFoundError(Exception):
    """Raised when a notification preference is not found."""

    def __init__(self, petition_id: UUID) -> None:
        super().__init__(f"Notification preference not found for petition {petition_id}")
        self.petition_id = petition_id


class NotificationPreferenceAlreadyExistsError(Exception):
    """Raised when a notification preference already exists."""

    def __init__(self, petition_id: UUID) -> None:
        super().__init__(
            f"Notification preference already exists for petition {petition_id}"
        )
        self.petition_id = petition_id


class NotificationPreferenceRepositoryProtocol(Protocol):
    """Protocol for notification preference storage operations (Story 7.2).

    Defines the contract for notification preference persistence. Implementations
    may use PostgreSQL, in-memory storage, or other backends.

    Constitutional Constraints:
    - FR-7.3: System SHALL notify Observer on fate assignment
    - AC3: Support save, get_by_petition_id, delete operations

    Methods:
        save: Store notification preferences for a petition
        get_by_petition_id: Retrieve preferences for a petition
        list_by_petition_ids: Retrieve preferences for multiple petitions
        delete: Remove preferences for a petition
    """

    async def save(self, preference: NotificationPreference) -> None:
        """Save notification preferences for a petition.

        Args:
            preference: The notification preference to save.

        Raises:
            NotificationPreferenceAlreadyExistsError: If preference for petition already exists.
        """
        ...

    async def get_by_petition_id(
        self, petition_id: UUID
    ) -> NotificationPreference | None:
        """Retrieve notification preferences for a petition.

        Args:
            petition_id: The petition ID to lookup preferences for.

        Returns:
            The notification preference if found, None otherwise.
        """
        ...

    async def list_by_petition_ids(
        self, petition_ids: list[UUID]
    ) -> dict[UUID, NotificationPreference]:
        """Retrieve notification preferences for multiple petitions.

        Args:
            petition_ids: List of petition IDs to lookup preferences for.

        Returns:
            Dict mapping petition_id to NotificationPreference (excludes missing).
        """
        ...

    async def delete(self, petition_id: UUID) -> bool:
        """Remove notification preferences for a petition.

        Args:
            petition_id: The petition ID to remove preferences for.

        Returns:
            True if deleted, False if not found.
        """
        ...

    async def update_enabled(self, petition_id: UUID, enabled: bool) -> None:
        """Update the enabled flag for a petition's notification preference.

        Args:
            petition_id: The petition ID to update preferences for.
            enabled: New enabled state.

        Raises:
            NotificationPreferenceNotFoundError: If preference doesn't exist.
        """
        ...
