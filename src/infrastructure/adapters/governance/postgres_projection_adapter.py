"""PostgreSQL Projection Adapter - Implementation of ProjectionPort.

Story: consent-gov-1.5: Projection Infrastructure

This adapter implements the ProjectionPort interface using PostgreSQL
for persistent storage of derived governance state projections.

CQRS-Lite Pattern (AD-9):
- Projections stored in isolated projections.* schema
- Idempotent event application via projection_applies table
- Can be rebuilt from ledger replay at any time

Schema Separation (AD-8):
- This adapter ONLY writes to projections.* schema
- It CANNOT modify ledger.* schema (Constitutional Constraint)

References:
- [Source: _bmad-output/planning-artifacts/governance-architecture.md#Projection Architecture]
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.application.ports.governance.projection_port import (
    ProjectionApplyRecord,
    ProjectionCheckpoint,
    ProjectionPort,
)
from src.domain.governance.events.event_envelope import GovernanceEvent
from src.domain.governance.projections import (
    ActorRegistryRecord,
    LegitimacyStateRecord,
    PanelRegistryRecord,
    PetitionIndexRecord,
    TaskStateRecord,
)

if TYPE_CHECKING:
    from src.application.ports.time_authority import TimeAuthority


# Known projection names
KNOWN_PROJECTIONS = frozenset({
    "task_states",
    "legitimacy_states",
    "panel_registry",
    "petition_index",
    "actor_registry",
})


class PostgresProjectionAdapter(ProjectionPort):
    """PostgreSQL implementation of ProjectionPort.

    Uses projections.* schema with:
    - Idempotent event application via projection_applies table
    - Checkpoint tracking via projection_checkpoints table
    - Five initial projection tables per architecture spec

    ┌────────────────────────────────────────────────────────────────────┐
    │                    SCHEMA ISOLATION                                 │
    │                                                                      │
    │  🔒 This adapter ONLY writes to projections.* schema                │
    │  🔒 It CANNOT modify ledger.* schema                                │
    │  🔒 Enforced by database role permissions in production             │
    │                                                                      │
    │  Ref: AD-8, governance-architecture.md                              │
    └────────────────────────────────────────────────────────────────────┘
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        time_authority: "TimeAuthority",
    ) -> None:
        """Initialize the adapter.

        Args:
            session_factory: SQLAlchemy async session factory.
            time_authority: Time authority for consistent timestamps.
        """
        self._session_factory = session_factory
        self._time_authority = time_authority

    async def apply_event(
        self,
        projection_name: str,
        event: GovernanceEvent,
        sequence: int,
    ) -> bool:
        """Apply a governance event to update projection state.

        Idempotency: Checks projection_applies before applying.
        """
        if projection_name not in KNOWN_PROJECTIONS:
            raise ValueError(
                f"Unknown projection '{projection_name}'. "
                f"Known projections: {sorted(KNOWN_PROJECTIONS)}"
            )

        async with self._session_factory() as session:
            # Check idempotency - has this event already been applied?
            if await self._is_event_applied_internal(session, projection_name, event.event_id):
                return False

            # Apply the event based on projection type
            # (Event handlers would dispatch to appropriate projection update)
            # For now, we just record the apply
            await self._record_apply(
                session,
                projection_name,
                event.event_id,
                event.hash or "",
                sequence,
            )

            await session.commit()
            return True

    async def is_event_applied(
        self,
        projection_name: str,
        event_id: UUID,
    ) -> bool:
        """Check if an event was already applied to a projection."""
        async with self._session_factory() as session:
            return await self._is_event_applied_internal(session, projection_name, event_id)

    async def _is_event_applied_internal(
        self,
        session: AsyncSession,
        projection_name: str,
        event_id: UUID,
    ) -> bool:
        """Internal method to check if event was applied (within transaction)."""
        result = await session.execute(
            text("""
                SELECT 1 FROM projections.projection_applies
                WHERE projection_name = :projection_name AND event_id = :event_id
            """),
            {"projection_name": projection_name, "event_id": event_id},
        )
        return result.scalar() is not None

    async def _record_apply(
        self,
        session: AsyncSession,
        projection_name: str,
        event_id: UUID,
        event_hash: str,
        sequence: int,
    ) -> None:
        """Record an event application for idempotency."""
        now = self._time_authority.now()
        await session.execute(
            text("""
                INSERT INTO projections.projection_applies
                (projection_name, event_id, event_hash, sequence, applied_at)
                VALUES (:projection_name, :event_id, :event_hash, :sequence, :applied_at)
            """),
            {
                "projection_name": projection_name,
                "event_id": event_id,
                "event_hash": event_hash,
                "sequence": sequence,
                "applied_at": now,
            },
        )

    async def get_checkpoint(
        self,
        projection_name: str,
    ) -> ProjectionCheckpoint | None:
        """Get the checkpoint for a projection."""
        async with self._session_factory() as session:
            result = await session.execute(
                text("""
                    SELECT projection_name, last_event_id, last_hash, last_sequence, updated_at
                    FROM projections.projection_checkpoints
                    WHERE projection_name = :projection_name
                """),
                {"projection_name": projection_name},
            )
            row = result.mappings().first()
            if row is None:
                return None

            return ProjectionCheckpoint(
                projection_name=row["projection_name"],
                last_event_id=row["last_event_id"],
                last_hash=row["last_hash"],
                last_sequence=row["last_sequence"],
                updated_at=row["updated_at"],
            )

    async def save_checkpoint(
        self,
        projection_name: str,
        event_id: UUID,
        event_hash: str,
        sequence: int,
    ) -> ProjectionCheckpoint:
        """Save a checkpoint for a projection."""
        now = self._time_authority.now()

        async with self._session_factory() as session:
            await session.execute(
                text("""
                    INSERT INTO projections.projection_checkpoints
                    (projection_name, last_event_id, last_hash, last_sequence, updated_at)
                    VALUES (:projection_name, :event_id, :event_hash, :sequence, :updated_at)
                    ON CONFLICT (projection_name) DO UPDATE SET
                        last_event_id = EXCLUDED.last_event_id,
                        last_hash = EXCLUDED.last_hash,
                        last_sequence = EXCLUDED.last_sequence,
                        updated_at = EXCLUDED.updated_at
                """),
                {
                    "projection_name": projection_name,
                    "event_id": event_id,
                    "event_hash": event_hash,
                    "sequence": sequence,
                    "updated_at": now,
                },
            )
            await session.commit()

        return ProjectionCheckpoint(
            projection_name=projection_name,
            last_event_id=event_id,
            last_hash=event_hash,
            last_sequence=sequence,
            updated_at=now,
        )

    async def get_apply_record(
        self,
        projection_name: str,
        event_id: UUID,
    ) -> ProjectionApplyRecord | None:
        """Get the apply record for a specific event."""
        async with self._session_factory() as session:
            result = await session.execute(
                text("""
                    SELECT projection_name, event_id, event_hash, sequence, applied_at
                    FROM projections.projection_applies
                    WHERE projection_name = :projection_name AND event_id = :event_id
                """),
                {"projection_name": projection_name, "event_id": event_id},
            )
            row = result.mappings().first()
            if row is None:
                return None

            return ProjectionApplyRecord(
                projection_name=row["projection_name"],
                event_id=row["event_id"],
                event_hash=row["event_hash"],
                sequence=row["sequence"],
                applied_at=row["applied_at"],
            )

    async def clear_projection(
        self,
        projection_name: str,
    ) -> int:
        """Clear all data for a projection (for rebuild)."""
        if projection_name not in KNOWN_PROJECTIONS:
            raise ValueError(
                f"Unknown projection '{projection_name}'. "
                f"Known projections: {sorted(KNOWN_PROJECTIONS)}"
            )

        async with self._session_factory() as session:
            # Clear the projection table
            result = await session.execute(
                text(f"DELETE FROM projections.{projection_name}"),
            )
            deleted_count = result.rowcount

            # Clear apply records for this projection
            await session.execute(
                text("""
                    DELETE FROM projections.projection_applies
                    WHERE projection_name = :projection_name
                """),
                {"projection_name": projection_name},
            )

            # Clear checkpoint for this projection
            await session.execute(
                text("""
                    DELETE FROM projections.projection_checkpoints
                    WHERE projection_name = :projection_name
                """),
                {"projection_name": projection_name},
            )

            await session.commit()
            return deleted_count

    async def get_projection_names(self) -> list[str]:
        """Get all known projection names."""
        return sorted(KNOWN_PROJECTIONS)

    # =========================================================================
    # Task State Projection Methods
    # =========================================================================

    async def get_task_state(self, task_id: UUID) -> TaskStateRecord | None:
        """Get the current state of a task."""
        async with self._session_factory() as session:
            result = await session.execute(
                text("""
                    SELECT task_id, current_state, earl_id, cluster_id, task_type,
                           created_at, state_entered_at, last_event_sequence,
                           last_event_hash, updated_at
                    FROM projections.task_states
                    WHERE task_id = :task_id
                """),
                {"task_id": task_id},
            )
            row = result.mappings().first()
            if row is None:
                return None

            return TaskStateRecord(
                task_id=row["task_id"],
                current_state=row["current_state"],
                earl_id=row["earl_id"],
                cluster_id=row["cluster_id"],
                task_type=row["task_type"],
                created_at=row["created_at"],
                state_entered_at=row["state_entered_at"],
                last_event_sequence=row["last_event_sequence"],
                last_event_hash=row["last_event_hash"],
                updated_at=row["updated_at"],
            )

    async def upsert_task_state(self, record: TaskStateRecord) -> None:
        """Insert or update a task state record."""
        async with self._session_factory() as session:
            await session.execute(
                text("""
                    INSERT INTO projections.task_states
                    (task_id, current_state, earl_id, cluster_id, task_type,
                     created_at, state_entered_at, last_event_sequence,
                     last_event_hash, updated_at)
                    VALUES (:task_id, :current_state, :earl_id, :cluster_id, :task_type,
                            :created_at, :state_entered_at, :last_event_sequence,
                            :last_event_hash, :updated_at)
                    ON CONFLICT (task_id) DO UPDATE SET
                        current_state = EXCLUDED.current_state,
                        earl_id = EXCLUDED.earl_id,
                        cluster_id = EXCLUDED.cluster_id,
                        task_type = EXCLUDED.task_type,
                        state_entered_at = EXCLUDED.state_entered_at,
                        last_event_sequence = EXCLUDED.last_event_sequence,
                        last_event_hash = EXCLUDED.last_event_hash,
                        updated_at = EXCLUDED.updated_at
                """),
                {
                    "task_id": record.task_id,
                    "current_state": record.current_state,
                    "earl_id": record.earl_id,
                    "cluster_id": record.cluster_id,
                    "task_type": record.task_type,
                    "created_at": record.created_at,
                    "state_entered_at": record.state_entered_at,
                    "last_event_sequence": record.last_event_sequence,
                    "last_event_hash": record.last_event_hash,
                    "updated_at": record.updated_at,
                },
            )
            await session.commit()

    async def get_tasks_by_state(
        self,
        state: str,
        limit: int = 100,
    ) -> list[TaskStateRecord]:
        """Get all tasks in a given state."""
        async with self._session_factory() as session:
            result = await session.execute(
                text("""
                    SELECT task_id, current_state, earl_id, cluster_id, task_type,
                           created_at, state_entered_at, last_event_sequence,
                           last_event_hash, updated_at
                    FROM projections.task_states
                    WHERE current_state = :state
                    ORDER BY updated_at DESC
                    LIMIT :limit
                """),
                {"state": state, "limit": limit},
            )
            return [
                TaskStateRecord(
                    task_id=row["task_id"],
                    current_state=row["current_state"],
                    earl_id=row["earl_id"],
                    cluster_id=row["cluster_id"],
                    task_type=row["task_type"],
                    created_at=row["created_at"],
                    state_entered_at=row["state_entered_at"],
                    last_event_sequence=row["last_event_sequence"],
                    last_event_hash=row["last_event_hash"],
                    updated_at=row["updated_at"],
                )
                for row in result.mappings()
            ]

    # =========================================================================
    # Legitimacy State Projection Methods
    # =========================================================================

    async def get_legitimacy_state(self, entity_id: str) -> LegitimacyStateRecord | None:
        """Get the current legitimacy state of an entity."""
        async with self._session_factory() as session:
            result = await session.execute(
                text("""
                    SELECT entity_id, entity_type, current_band, band_entered_at,
                           violation_count, last_violation_at, last_restoration_at,
                           last_event_sequence, updated_at
                    FROM projections.legitimacy_states
                    WHERE entity_id = :entity_id
                """),
                {"entity_id": entity_id},
            )
            row = result.mappings().first()
            if row is None:
                return None

            return LegitimacyStateRecord(
                entity_id=row["entity_id"],
                entity_type=row["entity_type"],
                current_band=row["current_band"],
                band_entered_at=row["band_entered_at"],
                violation_count=row["violation_count"],
                last_violation_at=row["last_violation_at"],
                last_restoration_at=row["last_restoration_at"],
                last_event_sequence=row["last_event_sequence"],
                updated_at=row["updated_at"],
            )

    async def upsert_legitimacy_state(self, record: LegitimacyStateRecord) -> None:
        """Insert or update a legitimacy state record."""
        async with self._session_factory() as session:
            await session.execute(
                text("""
                    INSERT INTO projections.legitimacy_states
                    (entity_id, entity_type, current_band, band_entered_at,
                     violation_count, last_violation_at, last_restoration_at,
                     last_event_sequence, updated_at)
                    VALUES (:entity_id, :entity_type, :current_band, :band_entered_at,
                            :violation_count, :last_violation_at, :last_restoration_at,
                            :last_event_sequence, :updated_at)
                    ON CONFLICT (entity_id) DO UPDATE SET
                        entity_type = EXCLUDED.entity_type,
                        current_band = EXCLUDED.current_band,
                        band_entered_at = EXCLUDED.band_entered_at,
                        violation_count = EXCLUDED.violation_count,
                        last_violation_at = EXCLUDED.last_violation_at,
                        last_restoration_at = EXCLUDED.last_restoration_at,
                        last_event_sequence = EXCLUDED.last_event_sequence,
                        updated_at = EXCLUDED.updated_at
                """),
                {
                    "entity_id": record.entity_id,
                    "entity_type": record.entity_type,
                    "current_band": record.current_band,
                    "band_entered_at": record.band_entered_at,
                    "violation_count": record.violation_count,
                    "last_violation_at": record.last_violation_at,
                    "last_restoration_at": record.last_restoration_at,
                    "last_event_sequence": record.last_event_sequence,
                    "updated_at": record.updated_at,
                },
            )
            await session.commit()

    # =========================================================================
    # Actor Registry Projection Methods
    # =========================================================================

    async def get_actor(self, actor_id: str) -> ActorRegistryRecord | None:
        """Get an actor by ID."""
        async with self._session_factory() as session:
            result = await session.execute(
                text("""
                    SELECT actor_id, actor_type, branch, rank, display_name,
                           active, created_at, deactivated_at,
                           last_event_sequence, updated_at
                    FROM projections.actor_registry
                    WHERE actor_id = :actor_id
                """),
                {"actor_id": actor_id},
            )
            row = result.mappings().first()
            if row is None:
                return None

            return ActorRegistryRecord(
                actor_id=row["actor_id"],
                actor_type=row["actor_type"],
                branch=row["branch"],
                rank=row["rank"],
                display_name=row["display_name"],
                active=row["active"],
                created_at=row["created_at"],
                deactivated_at=row["deactivated_at"],
                last_event_sequence=row["last_event_sequence"],
                updated_at=row["updated_at"],
            )

    async def actor_exists(self, actor_id: str) -> bool:
        """Check if an actor exists and is active."""
        async with self._session_factory() as session:
            result = await session.execute(
                text("""
                    SELECT 1 FROM projections.actor_registry
                    WHERE actor_id = :actor_id AND active = true
                """),
                {"actor_id": actor_id},
            )
            return result.scalar() is not None

    async def upsert_actor(self, record: ActorRegistryRecord) -> None:
        """Insert or update an actor registry record."""
        async with self._session_factory() as session:
            await session.execute(
                text("""
                    INSERT INTO projections.actor_registry
                    (actor_id, actor_type, branch, rank, display_name,
                     active, created_at, deactivated_at,
                     last_event_sequence, updated_at)
                    VALUES (:actor_id, :actor_type, :branch, :rank, :display_name,
                            :active, :created_at, :deactivated_at,
                            :last_event_sequence, :updated_at)
                    ON CONFLICT (actor_id) DO UPDATE SET
                        actor_type = EXCLUDED.actor_type,
                        branch = EXCLUDED.branch,
                        rank = EXCLUDED.rank,
                        display_name = EXCLUDED.display_name,
                        active = EXCLUDED.active,
                        deactivated_at = EXCLUDED.deactivated_at,
                        last_event_sequence = EXCLUDED.last_event_sequence,
                        updated_at = EXCLUDED.updated_at
                """),
                {
                    "actor_id": record.actor_id,
                    "actor_type": record.actor_type,
                    "branch": record.branch,
                    "rank": record.rank,
                    "display_name": record.display_name,
                    "active": record.active,
                    "created_at": record.created_at,
                    "deactivated_at": record.deactivated_at,
                    "last_event_sequence": record.last_event_sequence,
                    "updated_at": record.updated_at,
                },
            )
            await session.commit()

    async def get_actors_by_branch(
        self,
        branch: str,
        limit: int = 100,
    ) -> list[ActorRegistryRecord]:
        """Get all actors in a governance branch."""
        async with self._session_factory() as session:
            result = await session.execute(
                text("""
                    SELECT actor_id, actor_type, branch, rank, display_name,
                           active, created_at, deactivated_at,
                           last_event_sequence, updated_at
                    FROM projections.actor_registry
                    WHERE branch = :branch AND active = true
                    ORDER BY created_at DESC
                    LIMIT :limit
                """),
                {"branch": branch, "limit": limit},
            )
            return [
                ActorRegistryRecord(
                    actor_id=row["actor_id"],
                    actor_type=row["actor_type"],
                    branch=row["branch"],
                    rank=row["rank"],
                    display_name=row["display_name"],
                    active=row["active"],
                    created_at=row["created_at"],
                    deactivated_at=row["deactivated_at"],
                    last_event_sequence=row["last_event_sequence"],
                    updated_at=row["updated_at"],
                )
                for row in result.mappings()
            ]
