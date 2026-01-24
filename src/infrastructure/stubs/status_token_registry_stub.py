"""Status Token Registry stub for state change tracking (Story 7.1, Task 5).

In-memory registry for tracking petition state versions and notifying
waiters when state changes occur. This is a stub implementation for
development; production would use a distributed mechanism.

Constitutional Constraints:
- FR-7.2: System SHALL return status_token for efficient long-poll
- NFR-1.2: Response latency < 100ms p99
- AC3: Efficient connection management (no busy-wait)

Developer Golden Rules:
1. Use asyncio.Event for efficient waiting (no busy-wait)
2. Thread-safe operations with locks
3. Clean up waiters on timeout or cancellation
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from uuid import UUID

from src.application.ports.status_token_registry import StatusTokenRegistryProtocol

logger = logging.getLogger(__name__)


@dataclass
class PetitionStateEntry:
    """Entry tracking a petition's current state version.

    Attributes:
        petition_id: UUID of the petition.
        version: Current state version.
        event: Async event set when state changes.
    """

    petition_id: UUID
    version: int
    event: asyncio.Event = field(default_factory=asyncio.Event)


class StatusTokenRegistryStub(StatusTokenRegistryProtocol):
    """In-memory stub implementation of status token registry.

    This stub provides state version tracking and change notification
    using asyncio.Event for efficient waiting (no busy-wait).

    Thread-safety: Uses asyncio Lock for concurrent access.

    Attributes:
        _entries: Map of petition_id to PetitionStateEntry.
        _lock: Async lock for thread-safe operations.
        _waiter_count: Number of active waiters.
    """

    def __init__(self) -> None:
        """Initialize the registry."""
        self._entries: dict[UUID, PetitionStateEntry] = {}
        self._lock = asyncio.Lock()
        self._waiter_count = 0

    async def get_current_version(self, petition_id: UUID) -> int | None:
        """Get the current state version for a petition.

        Args:
            petition_id: UUID of the petition.

        Returns:
            Current version, or None if not tracked.
        """
        async with self._lock:
            entry = self._entries.get(petition_id)
            return entry.version if entry else None

    async def register_petition(self, petition_id: UUID, version: int) -> None:
        """Register a petition for change tracking.

        Args:
            petition_id: UUID of the petition.
            version: Initial state version.
        """
        async with self._lock:
            if petition_id not in self._entries:
                self._entries[petition_id] = PetitionStateEntry(
                    petition_id=petition_id,
                    version=version,
                )
            else:
                self._entries[petition_id].version = version

    async def update_version(self, petition_id: UUID, new_version: int) -> None:
        """Update the state version for a petition and notify waiters.

        Args:
            petition_id: UUID of the petition.
            new_version: New state version.
        """
        async with self._lock:
            entry = self._entries.get(petition_id)
            if entry is None:
                # Auto-register if not tracked
                entry = PetitionStateEntry(
                    petition_id=petition_id,
                    version=new_version,
                )
                self._entries[petition_id] = entry
            else:
                if entry.version != new_version:
                    entry.version = new_version
                    # Set event to wake up all waiters
                    entry.event.set()
                    # Create new event for future waiters
                    entry.event = asyncio.Event()

            logger.debug("Updated petition %s to version %d", petition_id, new_version)

    async def wait_for_change(
        self, petition_id: UUID, current_version: int, timeout_seconds: float
    ) -> bool:
        """Wait for a state change or timeout.

        Args:
            petition_id: UUID of the petition to watch.
            current_version: Client's current version (from token).
            timeout_seconds: Maximum time to wait.

        Returns:
            True if state changed, False if timeout.
        """
        # Get or create entry
        async with self._lock:
            entry = self._entries.get(petition_id)
            if entry is None:
                # Auto-register with current version
                entry = PetitionStateEntry(
                    petition_id=petition_id,
                    version=current_version,
                )
                self._entries[petition_id] = entry

            # Check if already changed
            if entry.version != current_version:
                return True

            # Get event to wait on (must be grabbed while holding lock)
            event = entry.event

        # Wait for change outside of lock
        self._waiter_count += 1
        try:
            await asyncio.wait_for(event.wait(), timeout=timeout_seconds)
            # Event was set - state changed
            return True
        except TimeoutError:
            return False
        finally:
            self._waiter_count -= 1

    def get_active_waiter_count(self) -> int:
        """Get the number of active waiters.

        Returns:
            Count of active long-poll connections waiting.
        """
        return self._waiter_count

    async def cleanup_petition(self, petition_id: UUID) -> None:
        """Remove a petition from tracking (e.g., after terminal state).

        Args:
            petition_id: UUID of the petition to remove.
        """
        async with self._lock:
            self._entries.pop(petition_id, None)

    async def clear(self) -> None:
        """Clear all entries (for testing)."""
        async with self._lock:
            self._entries.clear()
            self._waiter_count = 0


# Singleton instance for the stub
_registry_instance: StatusTokenRegistryStub | None = None
_registry_lock: asyncio.Lock | None = None


def _get_registry_lock() -> asyncio.Lock:
    """Get or create the registry lock for the current event loop.

    This lazily creates the lock to avoid event loop binding issues
    when the module is imported before an event loop exists.

    Returns:
        The asyncio.Lock for registry access.
    """
    global _registry_lock
    if _registry_lock is None:
        _registry_lock = asyncio.Lock()
    return _registry_lock


async def get_status_token_registry() -> StatusTokenRegistryStub:
    """Get the singleton registry instance.

    Returns:
        The StatusTokenRegistryStub singleton.
    """
    global _registry_instance
    if _registry_instance is None:
        async with _get_registry_lock():
            if _registry_instance is None:
                _registry_instance = StatusTokenRegistryStub()
    return _registry_instance


def reset_status_token_registry() -> None:
    """Reset the singleton registry (for testing).

    Also resets the lock to ensure clean state across different
    event loops in test scenarios.
    """
    global _registry_instance, _registry_lock
    _registry_instance = None
    _registry_lock = None
