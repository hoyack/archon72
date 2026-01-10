"""Deliberation Output port definition (Story 2.1, Task 4).

Defines the abstract interface for storing and retrieving deliberation
outputs. Infrastructure adapters must implement this protocol.

Constitutional Constraints:
- FR9: Agent outputs recorded before any human sees them
- AC1: Immediate Output Commitment
- AC2: Hash Verification on View
- CT-12: Witnessing creates accountability

Note: This port deliberately separates output storage from the event store.
The event store records the constitutional event (DeliberationOutputEvent),
while this port handles the actual output content storage for retrieval.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from src.domain.events.deliberation_output import DeliberationOutputPayload


@dataclass(frozen=True, eq=True)
class StoredOutput:
    """Represents a stored deliberation output reference.

    This is returned after successfully storing an output. It contains
    the reference information needed to verify and retrieve the output.

    Attributes:
        output_id: Unique identifier for the output (UUID).
        content_hash: SHA-256 hash of the output content (64 hex chars).
        event_sequence: Sequence number of the associated event.
        stored_at: Timestamp when the output was stored.
    """

    output_id: UUID
    content_hash: str
    event_sequence: int
    stored_at: datetime


class DeliberationOutputPort(ABC):
    """Abstract protocol for deliberation output storage operations.

    All output storage implementations must implement this interface.
    This enables dependency inversion and allows the application layer
    to remain independent of specific storage implementations.

    Constitutional Constraints:
    - FR9: Outputs must be stored before they can be viewed
    - AC1: Outputs are immediately committed with content hash
    - AC2: Hash verification enabled on retrieval
    - CT-12: Storage creates accountability through traceability

    Note:
        This port is for output content storage, separate from the event
        store which records the constitutional event (DeliberationOutputEvent).
        The output may be stored in a different location than events
        (e.g., blob storage) but must be indexed by output_id.
    """

    @abstractmethod
    async def store_output(
        self,
        payload: DeliberationOutputPayload,
        event_sequence: int,
    ) -> StoredOutput:
        """Store a deliberation output.

        This method stores the output content and creates a reference
        that can be used to retrieve and verify the output later.

        Args:
            payload: The DeliberationOutputPayload containing output data.
            event_sequence: The sequence number of the associated event.

        Returns:
            StoredOutput reference with storage metadata.

        Raises:
            EventStoreError: If storage fails.
        """
        ...

    @abstractmethod
    async def get_output(
        self,
        output_id: UUID,
    ) -> DeliberationOutputPayload | None:
        """Retrieve a stored deliberation output by ID.

        Args:
            output_id: The UUID of the output to retrieve.

        Returns:
            The DeliberationOutputPayload if found, None otherwise.

        Raises:
            EventStoreError: If retrieval fails due to storage error.
        """
        ...

    @abstractmethod
    async def verify_hash(
        self,
        output_id: UUID,
        expected_hash: str,
    ) -> bool:
        """Verify the content hash of a stored output.

        This method retrieves the stored output and computes its hash
        to verify against the expected hash. This is critical for FR9
        compliance - any hash mismatch indicates potential tampering.

        Args:
            output_id: The UUID of the output to verify.
            expected_hash: The expected SHA-256 content hash.

        Returns:
            True if hash matches, False if mismatch or output not found.

        Raises:
            EventStoreError: If verification fails due to storage error.
        """
        ...
