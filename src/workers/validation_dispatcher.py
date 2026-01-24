"""Validation dispatcher for per-validator request routing.

Story 3.3: Implement Validation Dispatcher
Red Team Round 7: Split-brain mitigation via per-validator keying

This module dispatches validation requests to specific validators using
explicit keying to prevent split-brain scenarios where a single validator
might process the same vote twice with different results.

Key design (Round 7):
- Each vote generates N separate messages (one per validator)
- Key format: {vote_id}:{validator_id}
- Headers include validator_id for worker filtering
- This ensures each validator gets exactly one request per vote
"""

import logging
import time
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from src.application.ports.vote_publisher import (
    PendingVote,
    PublishResponse,
    PublishResult,
)
from src.infrastructure.adapters.kafka.avro_serializer import (
    AvroSerializer,
    SerializationError,
)
from src.infrastructure.adapters.kafka.circuit_breaker import CircuitBreaker

logger = logging.getLogger(__name__)

# Topic for per-validator requests
TOPIC_VALIDATION_REQUESTS = "conclave.votes.validation-requests"


@dataclass(frozen=True)
class ValidationRequest:
    """Request for a specific validator to validate a vote.

    Attributes:
        vote_id: Vote being validated
        session_id: Deliberation session
        motion_id: Motion being voted on
        archon_id: Archon who cast the vote
        validator_id: Specific validator to invoke
        optimistic_choice: Initial (regex-parsed) choice
        raw_response: Full LLM response for validation
        attempt: Retry attempt number (1-based)
        request_time_ms: When this request was created
    """

    vote_id: UUID
    session_id: UUID
    motion_id: UUID
    archon_id: str
    validator_id: str
    optimistic_choice: str
    raw_response: str
    attempt: int
    request_time_ms: int

    def to_avro_dict(self) -> dict[str, Any]:
        """Convert to dictionary for Avro serialization."""
        return {
            "vote_id": str(self.vote_id),
            "session_id": str(self.session_id),
            "motion_id": str(self.motion_id),
            "archon_id": self.archon_id,
            "validator_id": self.validator_id,
            "optimistic_choice": self.optimistic_choice,
            "raw_response": self.raw_response,
            "attempt": self.attempt,
            "request_time_ms": self.request_time_ms,
        }

    @property
    def message_key(self) -> str:
        """Get the Kafka message key (Round 7: per-validator keying).

        Format: {vote_id}:{validator_id}

        This ensures:
        - Same vote_id always routes to same partition (for ordering)
        - Different validators get separate messages
        - No split-brain where one validator processes twice
        """
        return f"{self.vote_id}:{self.validator_id}"


@dataclass(frozen=True)
class DispatchResult:
    """Result of dispatching validation requests.

    Attributes:
        vote_id: Vote that was dispatched
        session_id: Session for the vote
        validators_dispatched: List of validator IDs that received requests
        failed_validators: List of validator IDs that failed to receive requests
        all_succeeded: True if all dispatches succeeded
        responses: Individual PublishResponse per validator
    """

    vote_id: UUID
    session_id: UUID
    validators_dispatched: list[str]
    failed_validators: list[str]
    all_succeeded: bool
    responses: dict[str, PublishResponse]

    @property
    def should_fallback_to_sync(self) -> bool:
        """Check if we should fall back to sync validation.

        Returns True if ANY dispatch failed (partial dispatch is unsafe).
        """
        return not self.all_succeeded


class ValidationDispatcher:
    """Dispatcher that routes validation requests to specific validators.

    Round 7 Split-Brain Mitigation:
    - Each validator worker is assigned a single validator_id at startup
    - The dispatcher sends separate messages for each validator
    - Messages are keyed by {vote_id}:{validator_id}
    - Workers filter by validator_id header, only processing their own

    This prevents scenarios where:
    - A worker processes the same vote for multiple validators
    - Network issues cause duplicate processing
    - Rebalancing leads to inconsistent state

    Usage:
        dispatcher = ValidationDispatcher(
            bootstrap_servers="localhost:19092",
            schema_registry_url="http://localhost:18081",
            validator_ids=["furcas_validator", "orias_validator"],
        )

        result = await dispatcher.dispatch_vote(pending_vote)
        if result.should_fallback_to_sync:
            # Fall back to synchronous validation
            await sync_validate(pending_vote)
    """

    def __init__(
        self,
        bootstrap_servers: str,
        schema_registry_url: str,
        validator_ids: list[str],
        circuit_breaker: CircuitBreaker | None = None,
        timeout_seconds: float = 10.0,
    ) -> None:
        """Initialize the validation dispatcher.

        Args:
            bootstrap_servers: Kafka bootstrap servers
            schema_registry_url: Schema Registry URL
            validator_ids: List of validator IDs to dispatch to
            circuit_breaker: Optional circuit breaker (creates default if None)
            timeout_seconds: Timeout for publish operations
        """
        self._bootstrap_servers = bootstrap_servers
        self._timeout = timeout_seconds
        self._validator_ids = validator_ids

        # Circuit breaker for fast fallback
        self._circuit_breaker = circuit_breaker or CircuitBreaker(
            failure_threshold=3,
            reset_timeout=30.0,
        )

        # Avro serializer
        self._serializer = AvroSerializer(
            schema_registry_url=schema_registry_url,
            require_registry=True,
        )

        # Lazy-loaded producer
        self._producer: Any = None

        # Metrics
        self._total_dispatches = 0
        self._successful_dispatches = 0
        self._failed_dispatches = 0

        logger.info(
            "ValidationDispatcher initialized with %d validators: %s",
            len(validator_ids),
            validator_ids,
        )

    def _get_producer(self) -> Any:
        """Get or create the Kafka producer."""
        if self._producer is None:
            try:
                from confluent_kafka import Producer

                self._producer = Producer(
                    {
                        "bootstrap.servers": self._bootstrap_servers,
                        "acks": "all",  # R1: Durability
                        "enable.idempotence": True,
                        "message.timeout.ms": int(self._timeout * 1000),
                        "request.timeout.ms": int(self._timeout * 1000),
                        "retries": 3,
                        "retry.backoff.ms": 100,
                        "compression.type": "snappy",
                    }
                )
            except ImportError:
                logger.error("confluent-kafka not installed")
                raise

        return self._producer

    def _create_headers(
        self,
        session_id: UUID,
        validator_id: str,
    ) -> list[tuple[str, bytes]]:
        """Create Kafka headers for a validation request.

        Args:
            session_id: Deliberation session ID (V2)
            validator_id: Target validator (Round 7)

        Returns:
            List of header tuples
        """
        return [
            ("session_id", str(session_id).encode("utf-8")),
            ("validator_id", validator_id.encode("utf-8")),
            ("dispatched_at", str(int(time.time() * 1000)).encode("utf-8")),
        ]

    async def _publish_request(
        self,
        request: ValidationRequest,
    ) -> PublishResponse:
        """Publish a single validation request.

        Args:
            request: The validation request to publish

        Returns:
            PublishResponse with outcome
        """
        # Check circuit breaker
        if not self._circuit_breaker.should_allow_request():
            return PublishResponse(
                result=PublishResult.CIRCUIT_OPEN,
                error_message="Circuit breaker is open",
            )

        try:
            # Serialize to Avro
            value = self._serializer.serialize(
                "validation_request",
                request.to_avro_dict(),
            )
        except SerializationError as e:
            self._circuit_breaker.record_failure()
            return PublishResponse(
                result=PublishResult.SCHEMA_ERROR,
                error_message=str(e),
            )

        # Create headers
        headers = self._create_headers(request.session_id, request.validator_id)

        # Track delivery
        delivery_result: dict[str, Any] = {
            "error": None,
            "partition": None,
            "offset": None,
        }

        def delivery_callback(err: Any, msg: Any) -> None:
            if err:
                delivery_result["error"] = str(err)
            else:
                delivery_result["partition"] = msg.partition()
                delivery_result["offset"] = msg.offset()

        try:
            producer = self._get_producer()

            # Produce with per-validator key (Round 7)
            producer.produce(
                topic=TOPIC_VALIDATION_REQUESTS,
                key=request.message_key.encode("utf-8"),
                value=value,
                headers=headers,
                callback=delivery_callback,
            )

            # Flush to wait for acks=all
            remaining = producer.flush(timeout=self._timeout)

            if remaining > 0:
                self._circuit_breaker.record_failure()
                return PublishResponse(
                    result=PublishResult.TIMEOUT,
                    error_message=f"Publish timeout - {remaining} messages pending",
                )

            if delivery_result["error"]:
                self._circuit_breaker.record_failure()
                return PublishResponse(
                    result=PublishResult.BROKER_ERROR,
                    error_message=delivery_result["error"],
                )

            self._circuit_breaker.record_success()
            return PublishResponse(
                result=PublishResult.SUCCESS,
                topic=TOPIC_VALIDATION_REQUESTS,
                partition=delivery_result["partition"],
                offset=delivery_result["offset"],
            )

        except Exception as e:
            self._circuit_breaker.record_failure()
            return PublishResponse(
                result=PublishResult.BROKER_ERROR,
                error_message=str(e),
            )

    async def dispatch_vote(
        self,
        vote: PendingVote,
        attempt: int = 1,
    ) -> DispatchResult:
        """Dispatch a vote to all validators.

        Creates separate validation requests for each validator and
        publishes them to Kafka with per-validator keying.

        Args:
            vote: The pending vote to validate
            attempt: Retry attempt number (1-based)

        Returns:
            DispatchResult with outcomes per validator
        """
        self._total_dispatches += 1

        validators_dispatched: list[str] = []
        failed_validators: list[str] = []
        responses: dict[str, PublishResponse] = {}

        request_time = int(time.time() * 1000)

        for validator_id in self._validator_ids:
            # Create per-validator request
            request = ValidationRequest(
                vote_id=vote.vote_id,
                session_id=vote.session_id,
                motion_id=vote.motion_id,
                archon_id=vote.archon_id,
                validator_id=validator_id,
                optimistic_choice=vote.optimistic_choice,
                raw_response=vote.raw_response,
                attempt=attempt,
                request_time_ms=request_time,
            )

            # Publish request
            response = await self._publish_request(request)
            responses[validator_id] = response

            if response.success:
                validators_dispatched.append(validator_id)
                logger.debug(
                    "Dispatched validation request: vote=%s validator=%s partition=%s",
                    vote.vote_id,
                    validator_id,
                    response.partition,
                )
            else:
                failed_validators.append(validator_id)
                logger.warning(
                    "Failed to dispatch validation request: vote=%s validator=%s error=%s",
                    vote.vote_id,
                    validator_id,
                    response.error_message,
                )

        all_succeeded = len(failed_validators) == 0

        if all_succeeded:
            self._successful_dispatches += 1
            logger.info(
                "Vote dispatched to all %d validators: vote=%s session=%s",
                len(self._validator_ids),
                vote.vote_id,
                vote.session_id,
            )
        else:
            self._failed_dispatches += 1
            logger.error(
                "Vote dispatch partially failed: vote=%s succeeded=%d failed=%d",
                vote.vote_id,
                len(validators_dispatched),
                len(failed_validators),
            )

        return DispatchResult(
            vote_id=vote.vote_id,
            session_id=vote.session_id,
            validators_dispatched=validators_dispatched,
            failed_validators=failed_validators,
            all_succeeded=all_succeeded,
            responses=responses,
        )

    def get_metrics(self) -> dict[str, Any]:
        """Get dispatcher metrics for monitoring."""
        return {
            "total_dispatches": self._total_dispatches,
            "successful_dispatches": self._successful_dispatches,
            "failed_dispatches": self._failed_dispatches,
            "validator_count": len(self._validator_ids),
            "circuit_state": self._circuit_breaker.state.value,
        }

    def close(self) -> None:
        """Close the producer and release resources."""
        if self._producer is not None:
            self._producer.flush(timeout=5.0)
            logger.info("Validation dispatcher producer closed")
            self._producer = None
