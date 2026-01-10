"""Collective output stub infrastructure adapter (Story 2.3, FR11).

This module provides an in-memory stub implementation of CollectiveOutputPort
for development and testing purposes.

RT-1/ADR-4: Dev Mode Watermark
- Stub includes DEV_MODE_WATERMARK for dev mode indication
- Real implementation will be in src/infrastructure/adapters/

Constitutional Constraints:
- FR11: Collective outputs attributed to Conclave, not individuals
- CT-12: Witnessing creates accountability
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from src.application.ports.collective_output import (
    CollectiveOutputPort,
    StoredCollectiveOutput,
)
from src.domain.events.collective_output import CollectiveOutputPayload

# RT-1/ADR-4: Dev mode watermark for stub identification
DEV_MODE_WATERMARK: str = "[DEV_STUB] CollectiveOutputStub - In-Memory Storage"


class CollectiveOutputStub(CollectiveOutputPort):
    """In-memory stub implementation of CollectiveOutputPort.

    Provides a simple dictionary-based storage for development and testing.
    This stub does NOT persist data between application restarts.

    RT-1/ADR-4 Compliance:
        - DEV_MODE_WATERMARK indicates dev mode
        - Use real adapter in production

    Usage:
        >>> stub = CollectiveOutputStub()
        >>> # Use for testing or local development
    """

    def __init__(self) -> None:
        """Initialize with empty in-memory storage."""
        self._storage: dict[UUID, CollectiveOutputPayload] = {}
        self._sequences: dict[UUID, int] = {}
        self._next_sequence: int = 1

    async def store_collective_output(
        self,
        payload: CollectiveOutputPayload,
        event_sequence: int,
    ) -> StoredCollectiveOutput:
        """Store a collective output in memory.

        Args:
            payload: The collective output payload to store.
            event_sequence: The event sequence number (ignored, auto-incremented).

        Returns:
            StoredCollectiveOutput with storage metadata.

        Note:
            The event_sequence parameter is ignored in this stub.
            The stub maintains its own auto-incrementing sequence for
            proper test isolation and realistic behavior.
        """
        # Use auto-incrementing sequence (ignore passed value for stub realism)
        actual_sequence = self._next_sequence
        self._next_sequence += 1

        self._storage[payload.output_id] = payload
        self._sequences[payload.output_id] = actual_sequence

        return StoredCollectiveOutput(
            output_id=payload.output_id,
            event_sequence=actual_sequence,
            content_hash=payload.content_hash,
            stored_at=datetime.now(timezone.utc),
        )

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
        return self._storage.get(output_id)

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
        payload = self._storage.get(output_id)
        if payload is None:
            return []
        return list(payload.linked_vote_event_ids)
