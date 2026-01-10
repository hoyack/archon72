"""Final deliberation recorder stub (Story 7.8, FR135).

Stub implementation of FinalDeliberationRecorder for development and testing.

This stub provides:
- Configurable success/failure modes
- Event tracking for test assertions
- Default pass-through behavior
- Real hash computation for CT-12 compliance
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

from src.application.ports.final_deliberation_recorder import (
    DeliberationWithEventMetadata,
    FinalDeliberationRecorder,
    RecordDeliberationResult,
)
from src.domain.events.cessation_deliberation import CessationDeliberationEventPayload
from src.domain.events.deliberation_recording_failed import (
    DeliberationRecordingFailedEventPayload,
)


class FinalDeliberationRecorderStub(FinalDeliberationRecorder):
    """Stub implementation of FinalDeliberationRecorder for development.

    This stub allows configuration of success/failure modes for testing
    different scenarios. By default, all operations succeed.

    Per CT-12: Computes real content_hash and witness signatures for
    accountability verification.

    Attributes:
        recorded_deliberations: List of deliberation records with metadata.
        recorded_failures: List of failure payloads recorded.
        deliberation_should_fail: If True, record_deliberation returns failure.
        failure_should_fail: If True, record_failure returns failure.
        deliberation_error_code: Error code when deliberation fails.
        deliberation_error_message: Error message when deliberation fails.
        failure_error_code: Error code when failure recording fails.
        failure_error_message: Error message when failure recording fails.
        witness_id: Configurable witness ID for stub attestations.
    """

    def __init__(
        self,
        deliberation_should_fail: bool = False,
        failure_should_fail: bool = False,
        deliberation_error_code: str = "STUB_DELIBERATION_ERROR",
        deliberation_error_message: str = "Stub deliberation error",
        failure_error_code: str = "STUB_FAILURE_ERROR",
        failure_error_message: str = "Stub failure error",
        witness_id: str = "stub-witness-dev",
    ) -> None:
        """Initialize the stub.

        Args:
            deliberation_should_fail: Whether record_deliberation should fail.
            failure_should_fail: Whether record_failure should fail.
            deliberation_error_code: Error code for deliberation failure.
            deliberation_error_message: Error message for deliberation failure.
            failure_error_code: Error code for failure recording failure.
            failure_error_message: Error message for failure recording failure.
            witness_id: Witness ID used for attestations.
        """
        self._recorded_deliberations: list[DeliberationWithEventMetadata] = []
        self.recorded_failures: list[DeliberationRecordingFailedEventPayload] = []
        self.deliberation_should_fail = deliberation_should_fail
        self.failure_should_fail = failure_should_fail
        self.deliberation_error_code = deliberation_error_code
        self.deliberation_error_message = deliberation_error_message
        self.failure_error_code = failure_error_code
        self.failure_error_message = failure_error_message
        self._witness_id = witness_id

    def _compute_content_hash(self, payload: CessationDeliberationEventPayload) -> str:
        """Compute SHA-256 content hash from payload (CT-12).

        Args:
            payload: The deliberation payload.

        Returns:
            SHA-256 hash in lowercase hex (64 chars).
        """
        signable_content = payload.signable_content()
        return hashlib.sha256(signable_content).hexdigest()

    def _compute_witness_signature(self, content_hash: str) -> str:
        """Compute stub witness signature (CT-12).

        In production, this would use the witness's private key.
        For the stub, we create a deterministic signature based on content.

        Args:
            content_hash: The content hash to sign.

        Returns:
            Stub signature string.
        """
        # Stub: deterministic signature from content hash + witness ID
        sig_input = f"{self._witness_id}:{content_hash}".encode("utf-8")
        return f"stub-sig-{hashlib.sha256(sig_input).hexdigest()[:32]}"

    @property
    def recorded_deliberations(self) -> list[CessationDeliberationEventPayload]:
        """Get raw payloads for backward compatibility with tests.

        Returns:
            List of payload objects.
        """
        return [d.payload for d in self._recorded_deliberations]

    def seed_deliberation(
        self,
        payload: CessationDeliberationEventPayload,
    ) -> DeliberationWithEventMetadata:
        """Seed a deliberation for testing without async.

        This helper method allows tests to pre-populate the recorder
        with deliberation data. It computes real content_hash and
        witness_signature like record_deliberation().

        Args:
            payload: The deliberation payload to seed.

        Returns:
            The created DeliberationWithEventMetadata record.
        """
        event_id = uuid4()
        content_hash = self._compute_content_hash(payload)
        witness_signature = self._compute_witness_signature(content_hash)

        record = DeliberationWithEventMetadata(
            payload=payload,
            event_id=event_id,
            content_hash=content_hash,
            witness_id=self._witness_id,
            witness_signature=witness_signature,
        )
        self._recorded_deliberations.append(record)
        return record

    async def record_deliberation(
        self,
        payload: CessationDeliberationEventPayload,
    ) -> RecordDeliberationResult:
        """Record deliberation (stub implementation).

        Computes real content_hash and witness_signature for CT-12 compliance.

        Args:
            payload: The deliberation payload to record.

        Returns:
            RecordDeliberationResult indicating success or configured failure.
        """
        if self.deliberation_should_fail:
            return RecordDeliberationResult(
                success=False,
                event_id=None,
                recorded_at=None,
                error_code=self.deliberation_error_code,
                error_message=self.deliberation_error_message,
            )

        # Generate event metadata (CT-12)
        event_id = uuid4()
        content_hash = self._compute_content_hash(payload)
        witness_signature = self._compute_witness_signature(content_hash)

        # Store with metadata
        record = DeliberationWithEventMetadata(
            payload=payload,
            event_id=event_id,
            content_hash=content_hash,
            witness_id=self._witness_id,
            witness_signature=witness_signature,
        )
        self._recorded_deliberations.append(record)

        return RecordDeliberationResult(
            success=True,
            event_id=event_id,
            recorded_at=datetime.now(timezone.utc),
            error_code=None,
            error_message=None,
        )

    async def record_failure(
        self,
        payload: DeliberationRecordingFailedEventPayload,
    ) -> RecordDeliberationResult:
        """Record failure (stub implementation).

        Args:
            payload: The failure payload to record.

        Returns:
            RecordDeliberationResult indicating success or configured failure.
        """
        self.recorded_failures.append(payload)

        if self.failure_should_fail:
            return RecordDeliberationResult(
                success=False,
                event_id=None,
                recorded_at=None,
                error_code=self.failure_error_code,
                error_message=self.failure_error_message,
            )

        return RecordDeliberationResult(
            success=True,
            event_id=uuid4(),
            recorded_at=datetime.now(timezone.utc),
            error_code=None,
            error_message=None,
        )

    def reset(self) -> None:
        """Reset recorded events and failures."""
        self._recorded_deliberations.clear()
        self.recorded_failures.clear()

    async def get_deliberation(
        self,
        deliberation_id: UUID,
    ) -> DeliberationWithEventMetadata | None:
        """Get a recorded deliberation by ID (FR135, AC7).

        Per AC7: Observer query access - vote counts, dissent, and reasoning
        are available via Observer API.

        Per CT-12: Returns event metadata (content_hash, witness_id,
        witness_signature) for accountability verification.

        Args:
            deliberation_id: The UUID of the deliberation to retrieve.

        Returns:
            DeliberationWithEventMetadata if found, None otherwise.
        """
        for record in self._recorded_deliberations:
            if record.payload.deliberation_id == deliberation_id:
                return record
        return None

    async def list_deliberations(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[DeliberationWithEventMetadata], int]:
        """List recorded deliberations with pagination (FR135, AC7).

        Per AC7: Observer query access - all deliberations accessible
        via Observer API without authentication (FR42).

        Per CT-12: Returns event metadata for accountability verification.

        Args:
            limit: Maximum number of deliberations to return.
            offset: Number of deliberations to skip.

        Returns:
            Tuple of (deliberations with metadata list, total count).
        """
        total = len(self._recorded_deliberations)
        # Return in reverse chronological order (newest first)
        sorted_records = sorted(
            self._recorded_deliberations,
            key=lambda r: r.payload.vote_recorded_at,
            reverse=True,
        )
        page = sorted_records[offset : offset + limit]
        return page, total
