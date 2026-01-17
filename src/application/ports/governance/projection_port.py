"""Governance Projection Port - Interface for derived state projections.

Story: consent-gov-1.5: Projection Infrastructure

This port defines the interface for managing derived state projections from
the governance event ledger. Projections enable efficient querying of current
state without replaying all events.

CQRS-Lite Pattern:
- Ledger is the single source of truth (write side)
- Projections are derived views for efficient reads (read side)
- Projections can be rebuilt from ledger replay at any time
- Single API with internal read/write separation

Constitutional Constraints (AD-1, AD-8, AD-9):
- Projections are DERIVED, never authoritative
- Projections CANNOT write to ledger schema
- Projections stored in isolated projections.* schema
- Idempotent event application via projection_applies table

Schema Separation:
| Schema         | Purpose                    | Write Access          |
|----------------|----------------------------|-----------------------|
| ledger.*       | Append-only event storage  | Event Store only      |
| projections.*  | Derived state views        | Projection services   |

References:
- [Source: _bmad-output/planning-artifacts/governance-architecture.md#Projection Architecture]
- [Source: _bmad-output/planning-artifacts/governance-architecture.md#Initial Projection Set (Locked)]
- [Source: _bmad-output/planning-artifacts/governance-architecture.md#Query API Pattern (Locked)]
"""

from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable
from uuid import UUID

from src.domain.governance.events.event_envelope import GovernanceEvent


@dataclass(frozen=True)
class ProjectionCheckpoint:
    """Checkpoint tracking for a projection.

    Tracks the last event processed by a projection to enable
    incremental updates and recovery after failures.

    Attributes:
        projection_name: Name of the projection (e.g., 'task_states').
        last_event_id: UUID of the last processed event.
        last_hash: Hash of the last processed event (integrity check).
        last_sequence: Sequence number of the last processed event.
        updated_at: When the checkpoint was last updated.
    """

    projection_name: str
    last_event_id: UUID
    last_hash: str
    last_sequence: int
    updated_at: datetime


@dataclass(frozen=True)
class ProjectionApplyRecord:
    """Record of an event application to a projection.

    Used for idempotency - prevents duplicate event processing.

    Attributes:
        projection_name: Name of the projection.
        event_id: UUID of the applied event.
        event_hash: Hash of the applied event (integrity check).
        sequence: Sequence number of the applied event.
        applied_at: When the event was applied.
    """

    projection_name: str
    event_id: UUID
    event_hash: str
    sequence: int
    applied_at: datetime


@runtime_checkable
class ProjectionPort(Protocol):
    """Projection storage for derived governance state.

    This interface defines the contract for managing derived state projections
    from the governance event ledger. All projections are stored in the
    projections.* schema, isolated from the ledger.* schema.

    ┌────────────────────────────────────────────────────────────────────┐
    │                    CQRS-LITE PATTERN                                │
    │                                                                      │
    │  📖 Projections are DERIVED from ledger, never authoritative        │
    │  🔄 Can be rebuilt from ledger replay at any time                   │
    │  ✅ Idempotent event application via projection_applies table        │
    │  🔒 CANNOT write to ledger schema (schema isolation)                │
    │                                                                      │
    │  Ref: AD-1, AD-8, AD-9, governance-architecture.md                  │
    └────────────────────────────────────────────────────────────────────┘

    Projection Tables:
    - projections.task_states: Task lifecycle state
    - projections.legitimacy_states: Entity legitimacy bands
    - projections.panel_registry: Prince panel tracking
    - projections.petition_index: Exit/dignity petitions
    - projections.actor_registry: Known actors

    Infrastructure Tables:
    - projections.projection_checkpoints: Last processed event per projection
    - projections.projection_applies: Event application log (idempotency)

    Implementation Notes:
    - PostgreSQL adapter uses projections.* schema
    - All operations are async for I/O efficiency
    - Idempotency check before every apply operation
    """

    @abstractmethod
    async def apply_event(
        self,
        projection_name: str,
        event: GovernanceEvent,
        sequence: int,
    ) -> bool:
        """Apply a governance event to update projection state.

        Idempotency: Checks projection_applies before applying. If the event
        was already applied to this projection, returns False without changes.

        Args:
            projection_name: Name of the projection to update.
            event: The governance event to apply.
            sequence: The ledger sequence number of the event.

        Returns:
            True if the event was applied, False if already processed.

        Raises:
            ValueError: If projection_name is unknown.
            ConstitutionalViolationError: If event processing fails.

        Note:
            This method is idempotent - calling it multiple times with
            the same event produces the same result.
        """
        ...

    @abstractmethod
    async def is_event_applied(
        self,
        projection_name: str,
        event_id: UUID,
    ) -> bool:
        """Check if an event was already applied to a projection.

        Used for idempotency verification before attempting to apply an event.

        Args:
            projection_name: Name of the projection.
            event_id: UUID of the event to check.

        Returns:
            True if the event was already applied, False otherwise.
        """
        ...

    @abstractmethod
    async def get_checkpoint(
        self,
        projection_name: str,
    ) -> ProjectionCheckpoint | None:
        """Get the checkpoint for a projection.

        The checkpoint tracks the last successfully processed event,
        enabling incremental updates and recovery.

        Args:
            projection_name: Name of the projection.

        Returns:
            The checkpoint, or None if projection has never processed events.
        """
        ...

    @abstractmethod
    async def save_checkpoint(
        self,
        projection_name: str,
        event_id: UUID,
        event_hash: str,
        sequence: int,
    ) -> ProjectionCheckpoint:
        """Save a checkpoint for a projection.

        Called after successfully processing an event (or batch of events)
        to record the new position.

        Args:
            projection_name: Name of the projection.
            event_id: UUID of the last processed event.
            event_hash: Hash of the last processed event.
            sequence: Sequence number of the last processed event.

        Returns:
            The saved checkpoint.
        """
        ...

    @abstractmethod
    async def get_apply_record(
        self,
        projection_name: str,
        event_id: UUID,
    ) -> ProjectionApplyRecord | None:
        """Get the apply record for a specific event.

        Args:
            projection_name: Name of the projection.
            event_id: UUID of the event.

        Returns:
            The apply record, or None if event was not applied.
        """
        ...

    @abstractmethod
    async def clear_projection(
        self,
        projection_name: str,
    ) -> int:
        """Clear all data for a projection (for rebuild).

        This removes all projection state and apply records, enabling
        a fresh rebuild from ledger events.

        Args:
            projection_name: Name of the projection to clear.

        Returns:
            Number of records deleted.

        Note:
            This is a destructive operation. Use only for rebuild scenarios.
        """
        ...

    @abstractmethod
    async def get_projection_names(self) -> list[str]:
        """Get all known projection names.

        Returns:
            List of projection names (e.g., ['task_states', 'legitimacy_states']).
        """
        ...


# Type aliases for projection-specific state accessors
# These are used by specialized projection ports


@runtime_checkable
class TaskStateProjectionPort(Protocol):
    """Specialized port for task state projection queries.

    Provides type-safe access to task state projection data.
    """

    @abstractmethod
    async def get_task_state(
        self,
        task_id: UUID,
    ) -> "TaskStateRecord | None":
        """Get the current state of a task.

        Args:
            task_id: UUID of the task.

        Returns:
            Task state record, or None if not found.
        """
        ...

    @abstractmethod
    async def get_tasks_by_state(
        self,
        state: str,
        limit: int = 100,
    ) -> list["TaskStateRecord"]:
        """Get all tasks in a given state.

        Args:
            state: The task state to filter by.
            limit: Maximum number of records to return.

        Returns:
            List of task state records.
        """
        ...

    @abstractmethod
    async def get_tasks_by_earl(
        self,
        earl_id: str,
        limit: int = 100,
    ) -> list["TaskStateRecord"]:
        """Get all tasks assigned to an Earl.

        Args:
            earl_id: ID of the Earl.
            limit: Maximum number of records to return.

        Returns:
            List of task state records.
        """
        ...


@runtime_checkable
class LegitimacyStateProjectionPort(Protocol):
    """Specialized port for legitimacy state projection queries.

    Provides type-safe access to legitimacy band data.
    """

    @abstractmethod
    async def get_legitimacy_state(
        self,
        entity_id: str,
    ) -> "LegitimacyStateRecord | None":
        """Get the current legitimacy state of an entity.

        Args:
            entity_id: ID of the entity.

        Returns:
            Legitimacy state record, or None if not found.
        """
        ...

    @abstractmethod
    async def get_entities_by_band(
        self,
        band: str,
        limit: int = 100,
    ) -> list["LegitimacyStateRecord"]:
        """Get all entities in a given legitimacy band.

        Args:
            band: The legitimacy band to filter by.
            limit: Maximum number of records to return.

        Returns:
            List of legitimacy state records.
        """
        ...


@runtime_checkable
class ActorRegistryProjectionPort(Protocol):
    """Specialized port for actor registry projection queries.

    Provides type-safe access to actor registry data.
    Used by write-time validation to verify actor existence.
    """

    @abstractmethod
    async def get_actor(
        self,
        actor_id: str,
    ) -> "ActorRegistryRecord | None":
        """Get an actor by ID.

        Args:
            actor_id: ID of the actor.

        Returns:
            Actor registry record, or None if not found.
        """
        ...

    @abstractmethod
    async def actor_exists(
        self,
        actor_id: str,
    ) -> bool:
        """Check if an actor exists and is active.

        Args:
            actor_id: ID of the actor.

        Returns:
            True if actor exists and is active, False otherwise.
        """
        ...

    @abstractmethod
    async def get_actors_by_branch(
        self,
        branch: str,
        limit: int = 100,
    ) -> list["ActorRegistryRecord"]:
        """Get all actors in a governance branch.

        Args:
            branch: The governance branch (e.g., 'executive', 'judicial').
            limit: Maximum number of records to return.

        Returns:
            List of actor registry records.
        """
        ...


# Forward references for record types (defined in domain layer)
TaskStateRecord = "TaskStateRecord"
LegitimacyStateRecord = "LegitimacyStateRecord"
ActorRegistryRecord = "ActorRegistryRecord"
