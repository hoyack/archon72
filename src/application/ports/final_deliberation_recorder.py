"""Final deliberation recorder port (Story 7.8, FR135).

Defines the protocol for recording the final deliberation before cessation.

Constitutional Constraints:
- FR135: Before cessation, final deliberation SHALL be recorded and immutable;
         if recording fails, that failure is the final event
- CT-12: Witnessing creates accountability - deliberation must be witnessed

Developer Golden Rules:
1. DELIBERATION FIRST - Record deliberation BEFORE cessation event
2. FAIL LOUD - Recording failure becomes final event
3. WITNESS EVERYTHING - Both success and failure must be witnessed
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Optional, Protocol, runtime_checkable
from uuid import UUID

if TYPE_CHECKING:
    from src.domain.events.cessation_deliberation import (
        CessationDeliberationEventPayload,
    )
    from src.domain.events.deliberation_recording_failed import (
        DeliberationRecordingFailedEventPayload,
    )


@dataclass(frozen=True)
class DeliberationWithEventMetadata:
    """Wrapper for deliberation payload with event metadata (CT-12).

    This wrapper includes the event store metadata required for
    Observer API compliance with CT-12 (witnessing accountability).

    Attributes:
        payload: The CessationDeliberationEventPayload.
        event_id: UUID of the event in the event store.
        content_hash: SHA-256 hash of the event content.
        witness_id: ID of the witness who attested this event.
        witness_signature: Signature of the witness.
    """

    payload: "CessationDeliberationEventPayload"
    event_id: UUID
    content_hash: str
    witness_id: str
    witness_signature: str


@dataclass(frozen=True)
class RecordDeliberationResult:
    """Result of recording a deliberation event (FR135).

    This result indicates whether the deliberation was successfully
    recorded to the event store.

    Attributes:
        success: True if recording succeeded.
        event_id: UUID of the created event (if success).
        recorded_at: When the event was recorded (if success).
        error_code: Machine-readable error code (if failure).
        error_message: Human-readable error description (if failure).
    """

    success: bool
    event_id: Optional[UUID]
    recorded_at: Optional[datetime]
    error_code: Optional[str]
    error_message: Optional[str]


@runtime_checkable
class FinalDeliberationRecorder(Protocol):
    """Protocol for recording final deliberation before cessation (FR135).

    Implementations are responsible for:
    1. Recording the complete cessation deliberation with all 72 Archon votes
    2. Ensuring the event is witnessed (CT-12)
    3. Recording failure events if recording fails

    Constitutional Constraints:
    - FR135: Final deliberation SHALL be recorded and immutable
    - CT-11: Silent failure destroys legitimacy -> Failure must be logged
    - CT-12: Witnessing creates accountability -> Must be witnessed

    Developer Golden Rules:
    1. DELIBERATION FIRST - Deliberation event before cessation
    2. FAIL LOUD - Recording failure becomes the final event
    3. WITNESS EVERYTHING - Both success and failure witnessed
    """

    async def record_deliberation(
        self,
        payload: "CessationDeliberationEventPayload",
    ) -> RecordDeliberationResult:
        """Record the final cessation deliberation (FR135).

        Records the complete deliberation including all 72 Archon votes,
        reasoning, and timing information.

        Constitutional Constraints:
        - FR135: Deliberation SHALL be recorded and immutable
        - CT-12: Event MUST be witnessed

        Args:
            payload: The complete cessation deliberation payload.

        Returns:
            RecordDeliberationResult indicating success or failure.

        Note:
            If this fails, caller MUST call record_failure() to record
            the failure as the final event per FR135.
        """
        ...

    async def record_failure(
        self,
        payload: "DeliberationRecordingFailedEventPayload",
    ) -> RecordDeliberationResult:
        """Record deliberation recording failure as final event (FR135).

        Per FR135: If recording fails, that failure IS the final event.
        This ensures the system cannot silently fail to record.

        Constitutional Constraints:
        - FR135: Failure SHALL be the final event
        - CT-11: Silent failure destroys legitimacy -> MUST be logged
        - CT-12: Failure MUST be witnessed

        Args:
            payload: The failure details including error code and message.

        Returns:
            RecordDeliberationResult indicating success or failure.

        Note:
            If even this fails, the system must HALT as there is no
            way to record what happened (per CT-13: integrity > availability).
        """
        ...

    async def get_deliberation(
        self,
        deliberation_id: UUID,
    ) -> Optional[DeliberationWithEventMetadata]:
        """Get a recorded deliberation by ID (FR135, AC7).

        Per AC7: Observer query access - vote counts, dissent, and reasoning
        are available via Observer API.

        Per CT-12: Returns event metadata (content_hash, witness_id,
        witness_signature) for accountability verification.

        Args:
            deliberation_id: The UUID of the deliberation to retrieve.

        Returns:
            DeliberationWithEventMetadata if found, None otherwise.
            Includes both payload and event store metadata.
        """
        ...

    async def list_deliberations(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[DeliberationWithEventMetadata], int]:
        """List recorded deliberations with pagination (FR135, AC7).

        Per AC7: Observer query access - all deliberations accessible
        via Observer API without authentication (FR42).

        Per CT-12: Returns event metadata (content_hash, witness_id,
        witness_signature) for accountability verification.

        Args:
            limit: Maximum number of deliberations to return.
            offset: Number of deliberations to skip.

        Returns:
            Tuple of (deliberations with metadata list, total count).
        """
        ...
