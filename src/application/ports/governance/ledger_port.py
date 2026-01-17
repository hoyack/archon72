"""Governance Ledger Port - Append-only ledger interface for governance events.

Story: consent-gov-1.2: Append-Only Ledger Port & Adapter

This port defines the interface for persisting governance events to an
append-only ledger. The ledger enforces constitutional constraints by
design - there are NO update or delete methods.

Constitutional Constraints (NFR-CONST-01, AD-1):
- Append is the ONLY write operation
- NO update methods - events are immutable once written
- NO delete methods - events are permanent
- The absence of mutation methods is INTENTIONAL, not an oversight

Architectural Decisions:
- AD-1: Event sourcing as canonical model
- AD-8: Same DB, schema isolation (ledger.* schema)
- AD-11: Global monotonic sequence via IDENTITY column
- AD-15: Branch derived from event_type at write-time

References:
- [Source: _bmad-output/planning-artifacts/governance-architecture.md#Storage Strategy (Locked)]
- [Source: _bmad-output/planning-artifacts/governance-architecture.md#Ledger Table Schema (Locked)]
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable
from uuid import UUID

from src.domain.governance.events.event_envelope import GovernanceEvent


@dataclass(frozen=True)
class PersistedGovernanceEvent:
    """A governance event that has been persisted to the ledger.

    This wrapper adds the ledger-assigned sequence number to the
    immutable GovernanceEvent. The sequence is assigned by PostgreSQL's
    IDENTITY column and provides global ordering.

    Attributes:
        event: The original GovernanceEvent with metadata and payload.
        sequence: The globally monotonic sequence number assigned by the ledger.
    """

    event: GovernanceEvent
    sequence: int

    def __post_init__(self) -> None:
        """Validate sequence is positive."""
        if self.sequence <= 0:
            raise ValueError(
                f"Sequence must be positive, got {self.sequence}"
            )

    @property
    def event_id(self) -> UUID:
        """Convenience accessor for event.event_id."""
        return self.event.event_id

    @property
    def event_type(self) -> str:
        """Convenience accessor for event.event_type."""
        return self.event.event_type

    @property
    def branch(self) -> str:
        """Convenience accessor for derived branch."""
        return self.event.branch

    @property
    def timestamp(self) -> datetime:
        """Convenience accessor for event.timestamp."""
        return self.event.timestamp

    @property
    def actor_id(self) -> str:
        """Convenience accessor for event.actor_id."""
        return self.event.actor_id


@dataclass(frozen=True)
class LedgerReadOptions:
    """Options for reading events from the ledger.

    All filters combine with AND logic.

    Attributes:
        start_sequence: First sequence to include (inclusive). None = from start.
        end_sequence: Last sequence to include (inclusive). None = to end.
        branch: Filter by governance branch (e.g., 'executive', 'judicial').
        event_type: Filter by exact event type (e.g., 'executive.task.accepted').
        limit: Maximum number of events to return. Default 100.
        offset: Number of events to skip. Default 0.
    """

    start_sequence: int | None = None
    end_sequence: int | None = None
    branch: str | None = None
    event_type: str | None = None
    limit: int = 100
    offset: int = 0


@runtime_checkable
class GovernanceLedgerPort(Protocol):
    """Append-only ledger for governance events.

    This interface defines the contract for persisting governance events
    to a permanent, append-only store. The ledger is the canonical source
    of truth for all governance actions.

    ┌────────────────────────────────────────────────────────────────────┐
    │                    CONSTITUTIONAL CONSTRAINTS                       │
    │                                                                      │
    │  ⚠️  NO update methods - events are immutable once written          │
    │  ⚠️  NO delete methods - events are permanent and auditable         │
    │  ⚠️  Append is the ONLY write operation allowed                     │
    │                                                                      │
    │  This interface deliberately omits mutation methods.                 │
    │  The absence is INTENTIONAL, not an oversight.                      │
    │                                                                      │
    │  Ref: NFR-CONST-01, AD-1, governance-architecture.md               │
    └────────────────────────────────────────────────────────────────────┘

    Implementation Notes:
    - PostgreSQL adapter uses ledger.governance_events table
    - Sequence is assigned via GENERATED ALWAYS AS IDENTITY
    - Branch is derived from event_type.split('.')[0] at write-time
    - All operations are async for I/O efficiency
    """

    async def append_event(
        self,
        event: GovernanceEvent,
    ) -> PersistedGovernanceEvent:
        """Append a governance event to the ledger.

        This is the ONLY write operation. Events cannot be updated or
        deleted after being appended (NFR-CONST-01).

        The ledger assigns:
        - A globally monotonic sequence number (AD-11)
        - Branch derived from event_type (AD-15)

        Args:
            event: The GovernanceEvent to persist. Must be a valid
                   GovernanceEvent instance (type enforcement per AC8).

        Returns:
            PersistedGovernanceEvent with the ledger-assigned sequence.

        Raises:
            TypeError: If event is not a GovernanceEvent instance.
            ConstitutionalViolationError: If event validation fails.

        Constitutional Reference:
            - NFR-CONST-01: Append-only enforcement
            - AD-11: Global monotonic sequence
            - AD-15: Branch derived at write-time
        """
        ...

    async def get_latest_event(self) -> PersistedGovernanceEvent | None:
        """Get the most recent event from the ledger.

        Used for hash chaining in story consent-gov-1-3 where new events
        must reference the hash of the previous event.

        Returns:
            The event with the highest sequence number, or None if empty.
        """
        ...

    async def get_max_sequence(self) -> int:
        """Get the highest sequence number in the ledger.

        Used by external observers to verify sequence continuity
        and by the hash chain implementation.

        Returns:
            The maximum sequence number, or 0 if the ledger is empty.
        """
        ...

    async def read_events(
        self,
        options: LedgerReadOptions | None = None,
    ) -> list[PersistedGovernanceEvent]:
        """Read events from the ledger with optional filters.

        All filters combine with AND logic. Events are returned
        ordered by sequence (ascending).

        Args:
            options: Filter and pagination options. If None, returns
                     the first 100 events.

        Returns:
            List of persisted events matching the criteria.

        Note:
            This is a read-only operation. The ledger provides no
            mechanism to modify the returned events.
        """
        ...

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
        ...

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
        ...

    async def count_events(
        self,
        options: LedgerReadOptions | None = None,
    ) -> int:
        """Count events matching the given criteria.

        Args:
            options: Filter options (sequence range, branch, event_type).
                     Limit and offset are ignored for counting.

        Returns:
            The number of events matching the criteria.
        """
        ...
