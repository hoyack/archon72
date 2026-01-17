"""PostgreSQL Governance Ledger Adapter.

Story: consent-gov-1.2: Append-Only Ledger Port & Adapter

This adapter implements the GovernanceLedgerPort for PostgreSQL storage
using the ledger.governance_events table.

Constitutional Constraints (NFR-CONST-01, AD-1):
- Append is the ONLY write operation
- NO update operations - events are immutable
- NO delete operations - events are permanent
- Database triggers enforce append-only at DB level

Architectural Decisions:
- AD-8: Uses ledger.* schema (isolated from public.*)
- AD-11: Uses GENERATED ALWAYS AS IDENTITY for sequence
- AD-15: Branch derived by database trigger, not trusted from client

References:
- [Source: _bmad-output/planning-artifacts/governance-architecture.md#Storage Strategy (Locked)]
- [Source: migrations/009_create_ledger_schema.sql]
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import MappingProxyType
from typing import TYPE_CHECKING, Any
from uuid import UUID

from structlog import get_logger

from src.application.ports.governance.ledger_port import (
    GovernanceLedgerPort,
    LedgerReadOptions,
    PersistedGovernanceEvent,
)
from src.domain.errors.constitutional import ConstitutionalViolationError
from src.domain.governance.events.event_envelope import (
    EventMetadata,
    GovernanceEvent,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

logger = get_logger(__name__)


class PostgresGovernanceLedgerAdapter(GovernanceLedgerPort):
    """PostgreSQL implementation of GovernanceLedgerPort.

    Uses ledger.governance_events table with:
    - sequence: bigint GENERATED ALWAYS AS IDENTITY (global ordering)
    - branch: derived by database trigger from event_type
    - ACID guarantees for persistence
    - Triggers prevent UPDATE/DELETE (append-only enforcement)

    ┌────────────────────────────────────────────────────────────────────┐
    │                    CONSTITUTIONAL CONSTRAINTS                       │
    │                                                                      │
    │  This adapter has NO update() or delete() methods.                  │
    │  The absence is INTENTIONAL, not an oversight.                      │
    │                                                                      │
    │  The database layer enforces append-only via triggers.              │
    │  Attempting UPDATE/DELETE will raise PostgreSQL exceptions.         │
    │                                                                      │
    │  Ref: NFR-CONST-01, AD-1, migrations/009_create_ledger_schema.sql  │
    └────────────────────────────────────────────────────────────────────┘
    """

    def __init__(
        self,
        session_factory: "async_sessionmaker[AsyncSession]",
        verbose: bool = False,
    ) -> None:
        """Initialize the PostgreSQL ledger adapter.

        Args:
            session_factory: SQLAlchemy async session factory.
            verbose: Enable verbose logging for debugging.
        """
        self._session_factory = session_factory
        self._verbose = verbose

        if self._verbose:
            logger.debug("postgres_ledger_adapter_initialized")

    async def append_event(
        self,
        event: GovernanceEvent,
    ) -> PersistedGovernanceEvent:
        """Append a governance event to the ledger.

        This is the ONLY write operation. Events cannot be updated or
        deleted after being appended (NFR-CONST-01).

        Args:
            event: The GovernanceEvent to persist.

        Returns:
            PersistedGovernanceEvent with ledger-assigned sequence.

        Raises:
            TypeError: If event is not a GovernanceEvent instance.
            ConstitutionalViolationError: If event validation fails.
        """
        # Type enforcement per AC8
        if not isinstance(event, GovernanceEvent):
            raise TypeError(
                f"AC8: Only GovernanceEvent instances can be appended, "
                f"got {type(event).__name__}"
            )

        if self._verbose:
            logger.debug(
                "appending_governance_event",
                event_id=str(event.event_id),
                event_type=event.event_type,
                actor_id=event.actor_id,
            )

        async with self._session_factory() as session:
            from sqlalchemy import text

            # Insert event into ledger.governance_events
            # Branch is derived by database trigger (AD-15)
            # Sequence is assigned by IDENTITY column (AD-11)
            insert_sql = text("""
                INSERT INTO ledger.governance_events (
                    event_id,
                    event_type,
                    branch,  -- Will be overwritten by trigger, but required
                    schema_version,
                    timestamp,
                    actor_id,
                    trace_id,
                    payload
                ) VALUES (
                    :event_id,
                    :event_type,
                    :branch,
                    :schema_version,
                    :timestamp,
                    :actor_id,
                    :trace_id,
                    :payload
                )
                RETURNING sequence, branch
            """)

            # Convert MappingProxyType to dict for JSON serialization
            payload_dict = (
                dict(event.payload)
                if isinstance(event.payload, MappingProxyType)
                else event.payload
            )

            result = await session.execute(
                insert_sql,
                {
                    "event_id": event.event_id,
                    "event_type": event.event_type,
                    "branch": event.branch,  # Will be derived by trigger
                    "schema_version": event.schema_version,
                    "timestamp": event.timestamp,
                    "actor_id": event.actor_id,
                    "trace_id": event.trace_id,
                    "payload": payload_dict,
                },
            )

            row = result.fetchone()
            if row is None:
                raise ConstitutionalViolationError(
                    "AD-1: Event append failed - no sequence returned"
                )

            sequence = row[0]

            await session.commit()

            if self._verbose:
                logger.info(
                    "governance_event_appended",
                    event_id=str(event.event_id),
                    sequence=sequence,
                    event_type=event.event_type,
                    branch=event.branch,
                )

            return PersistedGovernanceEvent(
                event=event,
                sequence=sequence,
            )

    async def get_latest_event(self) -> PersistedGovernanceEvent | None:
        """Get the most recent event from the ledger.

        Returns:
            The event with the highest sequence number, or None if empty.
        """
        async with self._session_factory() as session:
            from sqlalchemy import text

            query = text("""
                SELECT
                    sequence,
                    event_id,
                    event_type,
                    branch,
                    schema_version,
                    timestamp,
                    actor_id,
                    trace_id,
                    payload
                FROM ledger.governance_events
                ORDER BY sequence DESC
                LIMIT 1
            """)

            result = await session.execute(query)
            row = result.fetchone()

            if row is None:
                return None

            return self._row_to_persisted_event(row)

    async def get_max_sequence(self) -> int:
        """Get the highest sequence number in the ledger.

        Returns:
            The maximum sequence number, or 0 if the ledger is empty.
        """
        async with self._session_factory() as session:
            from sqlalchemy import text

            query = text("""
                SELECT COALESCE(MAX(sequence), 0)
                FROM ledger.governance_events
            """)

            result = await session.execute(query)
            row = result.fetchone()

            return row[0] if row else 0

    async def read_events(
        self,
        options: LedgerReadOptions | None = None,
    ) -> list[PersistedGovernanceEvent]:
        """Read events from the ledger with optional filters.

        Args:
            options: Filter and pagination options.

        Returns:
            List of persisted events matching the criteria.
        """
        if options is None:
            options = LedgerReadOptions()

        async with self._session_factory() as session:
            from sqlalchemy import text

            # Build dynamic query with filters
            conditions: list[str] = []
            params: dict[str, Any] = {
                "limit": options.limit,
                "offset": options.offset,
            }

            if options.start_sequence is not None:
                conditions.append("sequence >= :start_sequence")
                params["start_sequence"] = options.start_sequence

            if options.end_sequence is not None:
                conditions.append("sequence <= :end_sequence")
                params["end_sequence"] = options.end_sequence

            if options.branch is not None:
                conditions.append("branch = :branch")
                params["branch"] = options.branch

            if options.event_type is not None:
                conditions.append("event_type = :event_type")
                params["event_type"] = options.event_type

            where_clause = ""
            if conditions:
                where_clause = "WHERE " + " AND ".join(conditions)

            query_str = f"""
                SELECT
                    sequence,
                    event_id,
                    event_type,
                    branch,
                    schema_version,
                    timestamp,
                    actor_id,
                    trace_id,
                    payload
                FROM ledger.governance_events
                {where_clause}
                ORDER BY sequence ASC
                LIMIT :limit OFFSET :offset
            """

            result = await session.execute(text(query_str), params)
            rows = result.fetchall()

            return [self._row_to_persisted_event(row) for row in rows]

    async def get_event_by_sequence(
        self,
        sequence: int,
    ) -> PersistedGovernanceEvent | None:
        """Get a single event by its sequence number.

        Args:
            sequence: The sequence number to look up.

        Returns:
            The event with the given sequence, or None if not found.
        """
        async with self._session_factory() as session:
            from sqlalchemy import text

            query = text("""
                SELECT
                    sequence,
                    event_id,
                    event_type,
                    branch,
                    schema_version,
                    timestamp,
                    actor_id,
                    trace_id,
                    payload
                FROM ledger.governance_events
                WHERE sequence = :sequence
            """)

            result = await session.execute(query, {"sequence": sequence})
            row = result.fetchone()

            if row is None:
                return None

            return self._row_to_persisted_event(row)

    async def get_event_by_id(
        self,
        event_id: UUID,
    ) -> PersistedGovernanceEvent | None:
        """Get a single event by its event ID.

        Args:
            event_id: The UUID of the event to look up.

        Returns:
            The event with the given ID, or None if not found.
        """
        async with self._session_factory() as session:
            from sqlalchemy import text

            query = text("""
                SELECT
                    sequence,
                    event_id,
                    event_type,
                    branch,
                    schema_version,
                    timestamp,
                    actor_id,
                    trace_id,
                    payload
                FROM ledger.governance_events
                WHERE event_id = :event_id
            """)

            result = await session.execute(query, {"event_id": event_id})
            row = result.fetchone()

            if row is None:
                return None

            return self._row_to_persisted_event(row)

    async def count_events(
        self,
        options: LedgerReadOptions | None = None,
    ) -> int:
        """Count events matching the given criteria.

        Args:
            options: Filter options (limit and offset are ignored).

        Returns:
            The number of events matching the criteria.
        """
        if options is None:
            options = LedgerReadOptions()

        async with self._session_factory() as session:
            from sqlalchemy import text

            # Build dynamic query with filters
            conditions: list[str] = []
            params: dict[str, Any] = {}

            if options.start_sequence is not None:
                conditions.append("sequence >= :start_sequence")
                params["start_sequence"] = options.start_sequence

            if options.end_sequence is not None:
                conditions.append("sequence <= :end_sequence")
                params["end_sequence"] = options.end_sequence

            if options.branch is not None:
                conditions.append("branch = :branch")
                params["branch"] = options.branch

            if options.event_type is not None:
                conditions.append("event_type = :event_type")
                params["event_type"] = options.event_type

            where_clause = ""
            if conditions:
                where_clause = "WHERE " + " AND ".join(conditions)

            query_str = f"""
                SELECT COUNT(*)
                FROM ledger.governance_events
                {where_clause}
            """

            result = await session.execute(text(query_str), params)
            row = result.fetchone()

            return row[0] if row else 0

    def _row_to_persisted_event(
        self,
        row: tuple[Any, ...],
    ) -> PersistedGovernanceEvent:
        """Convert a database row to a PersistedGovernanceEvent.

        Args:
            row: Database row tuple (sequence, event_id, event_type, branch,
                 schema_version, timestamp, actor_id, trace_id, payload)

        Returns:
            PersistedGovernanceEvent instance.
        """
        (
            sequence,
            event_id,
            event_type,
            branch,
            schema_version,
            timestamp,
            actor_id,
            trace_id,
            payload,
        ) = row

        # Ensure timestamp is timezone-aware
        if isinstance(timestamp, datetime) and timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)

        # Reconstruct the GovernanceEvent
        metadata = EventMetadata(
            event_id=event_id if isinstance(event_id, UUID) else UUID(str(event_id)),
            event_type=event_type,
            timestamp=timestamp,
            actor_id=actor_id,
            schema_version=schema_version,
            trace_id=trace_id,
        )

        event = GovernanceEvent(
            metadata=metadata,
            payload=payload if isinstance(payload, dict) else dict(payload),
        )

        return PersistedGovernanceEvent(
            event=event,
            sequence=sequence,
        )
