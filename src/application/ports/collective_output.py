"""Collective output port interface (Story 2.3, FR11).

This module defines the abstract port interface for collective output storage.
Ports define the boundaries between the application layer and infrastructure.

Constitutional Constraints:
- FR11: Collective outputs attributed to Conclave, not individuals
- CT-12: Witnessing creates accountability

ADR-2: Context Bundles (Format + Integrity)
- Content hash enables verification of output integrity
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable
from uuid import UUID

from src.domain.events.collective_output import CollectiveOutputPayload


@dataclass(frozen=True, eq=True)
class StoredCollectiveOutput:
    """Result of storing a collective output.

    Returned after a collective output has been successfully stored.
    Contains the storage metadata needed for audit and retrieval.

    Attributes:
        output_id: UUID of the stored output.
        event_sequence: Sequence number in the event store.
        content_hash: SHA-256 hash of the stored content.
        stored_at: UTC timestamp when stored.
    """

    output_id: UUID
    event_sequence: int
    content_hash: str
    stored_at: datetime


@runtime_checkable
class CollectiveOutputPort(Protocol):
    """Abstract port interface for collective output storage.

    This port defines the contract that infrastructure adapters must
    implement to provide collective output persistence.

    Methods are async to support non-blocking I/O operations.

    Constitutional Constraints:
        - FR11: Stores collective outputs with proper attribution
        - CT-12: Enables audit trail via event store integration
    """

    async def store_collective_output(
        self,
        payload: CollectiveOutputPayload,
        event_sequence: int,
    ) -> StoredCollectiveOutput:
        """Store a collective output in the persistence layer.

        Args:
            payload: The collective output payload to store.
            event_sequence: The event sequence number for ordering.

        Returns:
            StoredCollectiveOutput with storage metadata.

        Raises:
            EventStoreError: If storage fails.
        """
        ...

    async def get_collective_output(
        self,
        output_id: UUID,
    ) -> CollectiveOutputPayload | None:
        """Retrieve a collective output by ID.

        Args:
            output_id: UUID of the output to retrieve.

        Returns:
            The CollectiveOutputPayload if found, None otherwise.
        """
        ...

    async def get_linked_vote_events(
        self,
        output_id: UUID,
    ) -> list[UUID]:
        """Get linked vote event IDs for a collective output.

        Args:
            output_id: UUID of the collective output.

        Returns:
            List of UUIDs for linked individual vote events.
            Empty list if output not found.
        """
        ...
