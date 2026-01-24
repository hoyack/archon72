"""Port interface for vote publishing to Kafka.

Story 2.1: Implement VotePublisher Port and Adapter
Red Team: R1 (acks=all required), V2 (session_id headers)
Pre-mortems: P3 (Schema Registry health)

This port defines the interface for publishing votes to Kafka
for async validation. It abstracts the messaging infrastructure
from the application layer.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any
from uuid import UUID


class PublishResult(Enum):
    """Result of a publish operation."""

    SUCCESS = "success"  # Message durably written (acks=all)
    CIRCUIT_OPEN = "circuit_open"  # Circuit breaker is open, fallback to sync
    TIMEOUT = "timeout"  # Publish timed out
    SCHEMA_ERROR = "schema_error"  # Schema Registry unavailable (R2)
    BROKER_ERROR = "broker_error"  # Kafka broker error


@dataclass(frozen=True)
class PublishResponse:
    """Response from a publish operation.

    Attributes:
        result: The outcome of the publish attempt
        topic: Topic the message was published to (if successful)
        partition: Partition the message was written to (if successful)
        offset: Offset of the message (if successful)
        error_message: Error details (if failed)
    """

    result: PublishResult
    topic: str | None = None
    partition: int | None = None
    offset: int | None = None
    error_message: str | None = None

    @property
    def success(self) -> bool:
        """Check if publish was successful."""
        return self.result == PublishResult.SUCCESS

    @property
    def should_fallback_to_sync(self) -> bool:
        """Determine if we should fall back to sync validation.

        Returns True for any failure that indicates Kafka is unhealthy.
        """
        return self.result in {
            PublishResult.CIRCUIT_OPEN,
            PublishResult.TIMEOUT,
            PublishResult.SCHEMA_ERROR,
            PublishResult.BROKER_ERROR,
        }


@dataclass(frozen=True)
class PendingVote:
    """Vote pending async validation.

    Contains all information needed to validate a vote asynchronously.

    Attributes:
        vote_id: Unique vote identifier (partition key)
        session_id: Deliberation session ID (header for V2)
        motion_id: Motion being voted on
        archon_id: Archon casting the vote
        optimistic_choice: Initial choice (APPROVE/REJECT/ABSTAIN)
        raw_response: Full LLM response for validation
        timestamp_ms: When the vote was cast (epoch milliseconds)
    """

    vote_id: UUID
    session_id: UUID
    motion_id: UUID
    archon_id: str
    optimistic_choice: str
    raw_response: str
    timestamp_ms: int

    def to_avro_dict(self) -> dict[str, Any]:
        """Convert to dictionary for Avro serialization."""
        return {
            "vote_id": str(self.vote_id),
            "session_id": str(self.session_id),
            "motion_id": str(self.motion_id),
            "archon_id": self.archon_id,
            "optimistic_choice": self.optimistic_choice,
            "raw_response": self.raw_response,
            "timestamp_ms": self.timestamp_ms,
        }


class VotePublisherProtocol(ABC):
    """Abstract protocol for publishing votes to Kafka.

    Implementations must ensure:
    - R1: acks=all for durability (no silent message loss)
    - V2: session_id in headers for session-bounded replay
    - P3: Schema Registry health check before publish

    The publisher integrates with the circuit breaker to provide
    fast fallback to sync validation when Kafka is unhealthy.
    """

    @abstractmethod
    async def publish_pending_vote(self, vote: PendingVote) -> PublishResponse:
        """Publish a vote for async validation.

        Publishes to the 'pending-validation' topic with:
        - Key: vote_id (for partition affinity)
        - Headers: session_id (for V2 session-bounded replay)
        - Value: Avro-encoded PendingVote

        This method blocks until acks=all is received (R1) or
        times out. On failure, the circuit breaker is notified.

        Args:
            vote: The vote to publish

        Returns:
            PublishResponse with outcome details

        Note:
            This method does NOT raise exceptions for Kafka errors.
            Instead, it returns a PublishResponse indicating failure.
            The caller should check should_fallback_to_sync and
            proceed with sync validation if needed.
        """
        ...

    @abstractmethod
    async def publish_validation_result(
        self,
        vote_id: UUID,
        session_id: UUID,
        validator_id: str,
        validated_choice: str,
        confidence: float,
        attempt: int,
    ) -> PublishResponse:
        """Publish a validation result from a validator worker.

        Publishes to the 'validation-results' topic for aggregation.

        Args:
            vote_id: Vote being validated
            session_id: Session for header
            validator_id: Which validator produced this result
            validated_choice: APPROVE/REJECT/ABSTAIN/INVALID
            confidence: Confidence score 0.0-1.0
            attempt: Retry attempt number (1-based)

        Returns:
            PublishResponse with outcome details
        """
        ...

    @abstractmethod
    async def publish_to_dead_letter(
        self,
        vote_id: UUID,
        session_id: UUID,
        failure_reason: str,
        last_validator_responses: list[dict[str, Any]],
    ) -> PublishResponse:
        """Publish a vote to the dead letter queue.

        Used when validation fails after all retries (P1).

        Args:
            vote_id: Vote that failed validation
            session_id: Session for header
            failure_reason: Why validation failed
            last_validator_responses: Final validator responses

        Returns:
            PublishResponse with outcome details
        """
        ...

    @abstractmethod
    def get_circuit_state(self) -> str:
        """Get current circuit breaker state.

        Returns:
            'closed', 'open', or 'half_open'
        """
        ...

    @abstractmethod
    def get_publish_metrics(self) -> dict[str, Any]:
        """Get publisher metrics for monitoring.

        Returns:
            Dictionary with success/failure counts, latencies, etc.
        """
        ...
