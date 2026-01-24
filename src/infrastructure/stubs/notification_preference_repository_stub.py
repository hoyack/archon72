"""Notification preference repository stub (Story 7.2, FR-7.3).

In-memory stub implementation for notification preference storage.
This is a stub for development; production would use PostgreSQL.

Constitutional Constraints:
- FR-7.3: System SHALL notify Observer on fate assignment
- CT-13: Read operations allowed during halt

Developer Golden Rules:
1. In-memory storage - no persistence across restarts
2. Thread-safe operations with locks
3. Useful for testing and development
"""

from __future__ import annotations

import asyncio
import logging
from uuid import UUID

from src.application.ports.notification_preference_repository import (
    NotificationPreferenceAlreadyExistsError,
    NotificationPreferenceNotFoundError,
    NotificationPreferenceRepositoryProtocol,
)
from src.domain.models.notification_preference import NotificationPreference

logger = logging.getLogger(__name__)


class NotificationPreferenceRepositoryStub(NotificationPreferenceRepositoryProtocol):
    """In-memory stub implementation of notification preference repository.

    This stub provides thread-safe storage using asyncio Lock.

    Attributes:
        _preferences: Map of petition_id to NotificationPreference.
        _lock: Async lock for thread-safe operations.
    """

    def __init__(self) -> None:
        """Initialize the repository stub."""
        self._preferences: dict[UUID, NotificationPreference] = {}
        self._lock = asyncio.Lock()

    async def save(self, preference: NotificationPreference) -> None:
        """Save notification preferences for a petition.

        Args:
            preference: The notification preference to save.

        Raises:
            NotificationPreferenceAlreadyExistsError: If preference for petition already exists.
        """
        async with self._lock:
            if preference.petition_id in self._preferences:
                raise NotificationPreferenceAlreadyExistsError(preference.petition_id)

            self._preferences[preference.petition_id] = preference
            logger.debug(
                "Saved notification preference for petition %s: channel=%s",
                preference.petition_id,
                preference.channel.value,
            )

    async def get_by_petition_id(
        self, petition_id: UUID
    ) -> NotificationPreference | None:
        """Retrieve notification preferences for a petition.

        Args:
            petition_id: The petition ID to lookup preferences for.

        Returns:
            The notification preference if found, None otherwise.
        """
        async with self._lock:
            return self._preferences.get(petition_id)

    async def list_by_petition_ids(
        self, petition_ids: list[UUID]
    ) -> dict[UUID, NotificationPreference]:
        """Retrieve notification preferences for multiple petitions.

        Args:
            petition_ids: List of petition IDs to lookup preferences for.

        Returns:
            Dict mapping petition_id to NotificationPreference (excludes missing).
        """
        async with self._lock:
            result: dict[UUID, NotificationPreference] = {}
            for petition_id in petition_ids:
                pref = self._preferences.get(petition_id)
                if pref is not None:
                    result[petition_id] = pref
            return result

    async def delete(self, petition_id: UUID) -> bool:
        """Remove notification preferences for a petition.

        Args:
            petition_id: The petition ID to remove preferences for.

        Returns:
            True if deleted, False if not found.
        """
        async with self._lock:
            if petition_id in self._preferences:
                del self._preferences[petition_id]
                logger.debug(
                    "Deleted notification preference for petition %s", petition_id
                )
                return True
            return False

    async def update_enabled(self, petition_id: UUID, enabled: bool) -> None:
        """Update the enabled flag for a petition's notification preference.

        Args:
            petition_id: The petition ID to update preferences for.
            enabled: New enabled state.

        Raises:
            NotificationPreferenceNotFoundError: If preference doesn't exist.
        """
        async with self._lock:
            if petition_id not in self._preferences:
                raise NotificationPreferenceNotFoundError(petition_id)

            existing = self._preferences[petition_id]
            self._preferences[petition_id] = existing.with_enabled(enabled)
            logger.debug(
                "Updated notification preference for petition %s: enabled=%s",
                petition_id,
                enabled,
            )

    async def clear(self) -> None:
        """Clear all preferences (for testing)."""
        async with self._lock:
            self._preferences.clear()

    def count(self) -> int:
        """Get the number of stored preferences (for testing).

        Returns:
            Number of preferences stored.
        """
        return len(self._preferences)


# Singleton instance for the stub
_repository_instance: NotificationPreferenceRepositoryStub | None = None
_repository_lock: asyncio.Lock | None = None


def _get_repository_lock() -> asyncio.Lock:
    """Get or create the repository lock for the current event loop.

    This lazily creates the lock to avoid event loop binding issues
    when the module is imported before an event loop exists.

    Returns:
        The asyncio.Lock for repository access.
    """
    global _repository_lock
    if _repository_lock is None:
        _repository_lock = asyncio.Lock()
    return _repository_lock


async def get_notification_preference_repository() -> (
    NotificationPreferenceRepositoryStub
):
    """Get the singleton repository instance.

    Returns:
        The NotificationPreferenceRepositoryStub singleton.
    """
    global _repository_instance
    if _repository_instance is None:
        async with _get_repository_lock():
            if _repository_instance is None:
                _repository_instance = NotificationPreferenceRepositoryStub()
    return _repository_instance


def reset_notification_preference_repository() -> None:
    """Reset the singleton repository (for testing).

    Also resets the lock to ensure clean state across different
    event loops in test scenarios.
    """
    global _repository_instance, _repository_lock
    _repository_instance = None
    _repository_lock = None
