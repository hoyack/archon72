"""Stub DeliberationOutputPort for Epic 2 development (Story 2.1).

This stub provides an in-memory implementation of DeliberationOutputPort
for development and testing. It stores outputs in memory and supports
hash verification.

WARNING: This stub is for development/testing only.
Production must use a real DeliberationOutput implementation with
persistent storage.

Future Implementation:
- Blob storage for large outputs
- Content-addressed storage
- Encryption at rest
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from uuid import UUID

# Python 3.11+ has datetime.UTC, earlier versions need timezone.utc
if sys.version_info >= (3, 11):  # noqa: UP036
    from datetime import timezone
else:
    UTC = timezone.utc  # noqa: UP017

import structlog

from src.application.ports.deliberation_output import (
    DeliberationOutputPort,
    StoredOutput,
)
from src.domain.events.deliberation_output import DeliberationOutputPayload

log = structlog.get_logger()


class DeliberationOutputStub(DeliberationOutputPort):
    """In-memory stub for deliberation output storage.

    This stub satisfies the DeliberationOutputPort interface so Epic 2 code
    can use output storage without depending on production infrastructure.

    Development Mode Behavior:
    - store_output(): Stores in memory, returns StoredOutput
    - get_output(): Returns stored payload or None
    - verify_hash(): Compares against stored hash

    Attributes:
        _storage: In-memory storage of outputs by output_id.
    """

    # Watermark for dev mode indication (following DevHSM pattern)
    DEV_MODE_WATERMARK = "[DEV MODE - IN-MEMORY STORAGE]"

    def __init__(self) -> None:
        """Initialize the stub with empty storage."""
        self._storage: dict[UUID, DeliberationOutputPayload] = {}
        self._sequences: dict[UUID, int] = {}
        self._stored_at: dict[UUID, datetime] = {}

        log.info(
            "deliberation_output_stub_initialized",
            watermark=self.DEV_MODE_WATERMARK,
        )

    async def store_output(
        self,
        payload: DeliberationOutputPayload,
        event_sequence: int,
    ) -> StoredOutput:
        """Store output in memory.

        Args:
            payload: The output payload to store.
            event_sequence: The event sequence number.

        Returns:
            StoredOutput reference.
        """
        now = datetime.now(timezone.utc)

        self._storage[payload.output_id] = payload
        self._sequences[payload.output_id] = event_sequence
        self._stored_at[payload.output_id] = now

        log.info(
            "output_stored",
            output_id=str(payload.output_id),
            agent_id=payload.agent_id,
            event_sequence=event_sequence,
            watermark=self.DEV_MODE_WATERMARK,
        )

        return StoredOutput(
            output_id=payload.output_id,
            content_hash=payload.content_hash,
            event_sequence=event_sequence,
            stored_at=now,
        )

    async def get_output(
        self,
        output_id: UUID,
    ) -> DeliberationOutputPayload | None:
        """Retrieve output from memory.

        Args:
            output_id: The output ID to retrieve.

        Returns:
            The stored payload or None if not found.
        """
        payload = self._storage.get(output_id)

        if payload is None:
            log.debug(
                "output_not_found",
                output_id=str(output_id),
                watermark=self.DEV_MODE_WATERMARK,
            )
        else:
            log.debug(
                "output_retrieved",
                output_id=str(output_id),
                watermark=self.DEV_MODE_WATERMARK,
            )

        return payload

    async def verify_hash(
        self,
        output_id: UUID,
        expected_hash: str,
    ) -> bool:
        """Verify content hash matches stored hash.

        Args:
            output_id: The output ID to verify.
            expected_hash: The expected content hash.

        Returns:
            True if hash matches, False otherwise.
        """
        payload = self._storage.get(output_id)

        if payload is None:
            log.warning(
                "hash_verify_not_found",
                output_id=str(output_id),
                watermark=self.DEV_MODE_WATERMARK,
            )
            return False

        matches = payload.content_hash == expected_hash

        if not matches:
            log.warning(
                "hash_mismatch",
                output_id=str(output_id),
                expected=expected_hash[:8] + "...",
                actual=payload.content_hash[:8] + "...",
                watermark=self.DEV_MODE_WATERMARK,
            )
        else:
            log.debug(
                "hash_verified",
                output_id=str(output_id),
                watermark=self.DEV_MODE_WATERMARK,
            )

        return matches
