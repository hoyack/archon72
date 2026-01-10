"""Key Registry adapter implementations (FR75, FR76).

Provides infrastructure adapters for the key registry protocol.

Available adapters:
- InMemoryKeyRegistry: In-memory storage for testing/development

Constitutional Constraints:
- FR75: Key registry must track active keys
- FR76: Historical keys must be preserved (no deletion)
"""

from __future__ import annotations

from datetime import datetime, timezone

from src.application.ports.key_registry import KeyRegistryProtocol
from src.domain.errors.constitutional import ConstitutionalViolationError
from src.domain.models.agent_key import AgentKey


class KeyAlreadyExistsError(ConstitutionalViolationError):
    """Raised when attempting to register a key that already exists."""

    def __init__(self, key_id: str) -> None:
        super().__init__(f"FR75: Key already exists: {key_id}")


class KeyNotFoundError(ConstitutionalViolationError):
    """Raised when a key is not found in the registry."""

    def __init__(self, key_id: str) -> None:
        super().__init__(f"FR75: Key not found: {key_id}")


class InMemoryKeyRegistry(KeyRegistryProtocol):
    """In-memory key registry for testing and development.

    NOT FOR PRODUCTION USE. Keys are stored in memory and will be
    lost when the process exits.

    Constitutional Constraints:
    - FR75: Key registry must track active keys
    - FR76: Historical keys are preserved (no deletion method)
    """

    def __init__(self) -> None:
        """Initialize the in-memory registry."""
        self._keys: dict[str, AgentKey] = {}  # key_id -> AgentKey

    async def get_key_by_id(self, key_id: str) -> AgentKey | None:
        """Get a key by its key_id.

        Args:
            key_id: The HSM key identifier.

        Returns:
            AgentKey if found, None otherwise.
        """
        return self._keys.get(key_id)

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
        check_time = at_time or datetime.now(timezone.utc)

        for key in self._keys.values():
            if key.agent_id == agent_id and key.is_active_at(check_time):
                return key

        return None

    async def register_key(self, key: AgentKey) -> None:
        """Register a new agent key.

        Args:
            key: The AgentKey to register.

        Raises:
            KeyAlreadyExistsError: If key_id already exists.
        """
        if key.key_id in self._keys:
            raise KeyAlreadyExistsError(key.key_id)

        self._keys[key.key_id] = key

    async def deactivate_key(
        self,
        key_id: str,
        deactivated_at: datetime,
    ) -> None:
        """Mark a key as deactivated (set active_until).

        Note: Keys are NEVER deleted (FR76). This creates a new
        AgentKey instance with active_until set.

        Args:
            key_id: The key to deactivate.
            deactivated_at: When the key becomes inactive.

        Raises:
            KeyNotFoundError: If key_id doesn't exist.
        """
        if key_id not in self._keys:
            raise KeyNotFoundError(key_id)

        old_key = self._keys[key_id]

        # Create new key with active_until set
        # We need to use object.__setattr__ since dataclass is frozen
        # Actually, we create a new instance entirely
        new_key = AgentKey(
            id=old_key.id,
            agent_id=old_key.agent_id,
            key_id=old_key.key_id,
            public_key=old_key.public_key,
            active_from=old_key.active_from,
            active_until=deactivated_at,
            created_at=old_key.created_at,
        )

        self._keys[key_id] = new_key

    async def key_exists(self, key_id: str) -> bool:
        """Check if a key exists in the registry.

        Args:
            key_id: The key identifier to check.

        Returns:
            True if key exists, False otherwise.
        """
        return key_id in self._keys

    def clear(self) -> None:
        """Clear all keys (for testing only).

        WARNING: This bypasses FR76 and should only be used
        in test fixtures.
        """
        self._keys.clear()
