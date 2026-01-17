"""Actor validator for governance events.

Story: consent-gov-1.4: Write-Time Validation

Validates that actors are registered in the actor registry before
allowing events to be appended to the ledger.

Performance Target: ≤3ms (cached projection lookup)

References:
    - CT-12: Witnessing creates accountability
    - All actors must be attributable
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from src.domain.governance.errors.validation_errors import UnknownActorError
from src.domain.governance.events.event_envelope import GovernanceEvent


@runtime_checkable
class ActorRegistryPort(Protocol):
    """Port for querying the actor registry.

    The actor registry tracks all known actors (archons, officers)
    that are allowed to emit governance events.
    """

    async def actor_exists(self, actor_id: str) -> bool:
        """Check if an actor is registered.

        Args:
            actor_id: The ID of the actor to check.

        Returns:
            True if the actor is registered, False otherwise.
        """
        ...

    async def get_all_actor_ids(self) -> frozenset[str]:
        """Get all registered actor IDs.

        Returns:
            Frozen set of all registered actor IDs.
        """
        ...


class InMemoryActorRegistry:
    """In-memory implementation of ActorRegistryPort.

    Used for testing and as a cache layer for the database-backed registry.
    """

    def __init__(self, actors: frozenset[str] | None = None) -> None:
        """Initialize with a set of actor IDs.

        Args:
            actors: Initial set of registered actors. Defaults to empty set.
        """
        self._actors: frozenset[str] = actors or frozenset()

    async def actor_exists(self, actor_id: str) -> bool:
        """Check if an actor is registered."""
        return actor_id in self._actors

    async def get_all_actor_ids(self) -> frozenset[str]:
        """Get all registered actor IDs."""
        return self._actors

    def add_actor(self, actor_id: str) -> None:
        """Add an actor to the registry (for testing)."""
        self._actors = self._actors | {actor_id}

    def remove_actor(self, actor_id: str) -> None:
        """Remove an actor from the registry (for testing)."""
        self._actors = self._actors - {actor_id}


class ActorValidator:
    """Validates that actors are registered in the governance system.

    Uses a cached projection for O(1) lookup performance after cache warm.

    Constitutional Constraint:
        Per CT-12, all actors must be attributable. Events from unknown
        actors are rejected to maintain accountability integrity.

    Performance:
        - Actor lookup: ≤3ms (cached projection)
        - Cache refresh: configurable TTL

    Attributes:
        skip_validation: If True, all actors are considered valid.
                         Used only for replay scenarios (admin only).
    """

    def __init__(
        self,
        actor_registry: ActorRegistryPort,
        *,
        skip_validation: bool = False,
    ) -> None:
        """Initialize the actor validator.

        Args:
            actor_registry: The actor registry port for lookups.
            skip_validation: If True, skip validation (admin replay only).
        """
        self._registry = actor_registry
        self._skip_validation = skip_validation

    @property
    def registry(self) -> ActorRegistryPort:
        """Get the actor registry."""
        return self._registry

    async def validate(self, event: GovernanceEvent) -> None:
        """Validate that the actor is registered.

        Args:
            event: The GovernanceEvent to validate.

        Raises:
            UnknownActorError: If actor is not registered and validation is enabled.
        """
        if self._skip_validation:
            return

        actor_id = event.actor_id

        if await self._registry.actor_exists(actor_id):
            return  # Valid actor

        # Actor not recognized - reject with error
        raise UnknownActorError(
            event_id=event.event_id,
            actor_id=actor_id,
        )

    async def is_valid_actor(self, actor_id: str) -> bool:
        """Check if an actor is valid without raising.

        Args:
            actor_id: The actor ID to check.

        Returns:
            True if the actor is registered, False otherwise.
        """
        if self._skip_validation:
            return True
        return await self._registry.actor_exists(actor_id)
