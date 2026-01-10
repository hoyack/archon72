"""Key Registry protocol definition (FR75, FR76).

Defines the abstract interface for agent key registry operations.
Infrastructure adapters must implement this protocol.

Constitutional Constraints:
- FR75: Key registry must track active keys
- FR76: Historical keys must be preserved (no deletion)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from src.domain.models.agent_key import AgentKey


class KeyRegistryProtocol(ABC):
    """Abstract protocol for key registry operations.

    All key registry implementations must implement this interface.
    This enables dependency inversion and allows the application layer
    to remain independent of specific storage implementations.

    Constitutional Requirements:
    - FR75: Must track active keys with temporal validity
    - FR76: Historical keys must never be deleted
    """

    @abstractmethod
    async def get_key_by_id(self, key_id: str) -> AgentKey | None:
        """Get a key by its key_id.

        Args:
            key_id: The HSM key identifier.

        Returns:
            AgentKey if found, None otherwise.
        """
        ...

    @abstractmethod
    async def get_active_key_for_agent(
        self,
        agent_id: str,
        at_time: datetime | None = None,
    ) -> AgentKey | None:
        """Get the active key for an agent at a specific time.

        Args:
            agent_id: The agent identifier.
            at_time: The time to check (default: current time).

        Returns:
            AgentKey if found and active, None otherwise.
        """
        ...

    @abstractmethod
    async def register_key(self, key: AgentKey) -> None:
        """Register a new agent key.

        Args:
            key: The AgentKey to register.

        Raises:
            KeyAlreadyExistsError: If key_id already exists.
        """
        ...

    @abstractmethod
    async def deactivate_key(
        self,
        key_id: str,
        deactivated_at: datetime,
    ) -> None:
        """Mark a key as deactivated (set active_until).

        Note: Keys are NEVER deleted (FR76). This only sets the
        active_until timestamp to prevent future use.

        Args:
            key_id: The key to deactivate.
            deactivated_at: When the key becomes inactive.

        Raises:
            KeyNotFoundError: If key_id doesn't exist.
        """
        ...

    @abstractmethod
    async def key_exists(self, key_id: str) -> bool:
        """Check if a key exists in the registry.

        Args:
            key_id: The key identifier to check.

        Returns:
            True if key exists, False otherwise.
        """
        ...
