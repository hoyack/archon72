"""Kafka vote publisher adapter.

Story 2.1: Implement VotePublisher Port and Adapter
Red Team: R1 (acks=all required), V2 (session_id headers)
Pre-mortems: P3 (Schema Registry health)

This adapter publishes votes to Kafka for async validation using
confluent-kafka with strong durability guarantees.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from src.application.ports.vote_publisher import (
    PendingVote,
    PublishResponse,
    PublishResult,
    VotePublisherProtocol,
)
from src.infrastructure.adapters.kafka.avro_serializer import (
    AvroSerializer,
    SchemaRegistryUnavailableError,
    SerializationError,
)
from src.infrastructure.adapters.kafka.circuit_breaker import CircuitBreaker, CircuitState

logger = logging.getLogger(__name__)

# Topic names per ADR-003
TOPIC_PENDING_VALIDATION = "conclave.votes.pending-validation"
TOPIC_VALIDATION_RESULTS = "conclave.votes.validation-results"
TOPIC_VALIDATED = "conclave.votes.validated"
TOPIC_DEAD_LETTER = "conclave.votes.dead-letter"


@dataclass
class PublishMetrics:
    """Metrics tracked by the publisher."""

    total_publishes: int = 0
    successful_publishes: int = 0
    failed_publishes: int = 0
    circuit_open_rejections: int = 0
    schema_errors: int = 0
    broker_errors: int = 0
    timeouts: int = 0
    total_latency_ms: float = 0.0
    last_publish_time: float | None = None


class KafkaVotePublisher(VotePublisherProtocol):
    """Kafka implementation of VotePublisherProtocol.

    Features:
    - acks=all for durability (R1)
    - session_id headers for session-bounded replay (V2)
    - Circuit breaker integration for fast fallback
    - Avro serialization with Schema Registry

    Usage:
        publisher = KafkaVotePublisher(
            bootstrap_servers="localhost:19092",
            schema_registry_url="http://localhost:18081",
        )

        response = await publisher.publish_pending_vote(vote)
        if response.should_fallback_to_sync:
            # Use sync validation instead
            await sync_validate(vote)
    """

    def __init__(
        self,
        bootstrap_servers: str,
        schema_registry_url: str,
        circuit_breaker: CircuitBreaker | None = None,
        timeout_seconds: float = 10.0,
        require_schema_registry: bool = True,
    ) -> None:
        """Initialize the Kafka publisher.

        Args:
            bootstrap_servers: Kafka bootstrap servers
            schema_registry_url: Schema Registry URL
            circuit_breaker: Optional circuit breaker (creates default if None)
            timeout_seconds: Timeout for publish operations
            require_schema_registry: If True, fails when registry unavailable (R2)
        """
        self._bootstrap_servers = bootstrap_servers
        self._schema_registry_url = schema_registry_url
        self._timeout = timeout_seconds

        # Circuit breaker for fast fallback
        self._circuit_breaker = circuit_breaker or CircuitBreaker(
            failure_threshold=3,
            reset_timeout=30.0,
            on_state_change=self._on_circuit_state_change,
        )

        # Avro serializer with Schema Registry
        self._serializer = AvroSerializer(
            schema_registry_url=schema_registry_url,
            require_registry=require_schema_registry,
        )

        # Lazy-loaded producer
        self._producer: Any = None

        # Metrics
        self._metrics = PublishMetrics()

    def _on_circuit_state_change(
        self, old_state: CircuitState, new_state: CircuitState
    ) -> None:
        """Handle circuit breaker state changes."""
        logger.info(
            "Publisher circuit breaker: %s -> %s",
            old_state.value,
            new_state.value,
        )

    def _get_producer(self) -> Any:
        """Get or create the Kafka producer.

        Configured with acks=all per R1 for strong durability.
        """
        if self._producer is None:
            try:
                from confluent_kafka import Producer

                self._producer = Producer({
                    "bootstrap.servers": self._bootstrap_servers,
                    # R1: acks=all ensures all replicas acknowledge
                    "acks": "all",
                    # Enable idempotence for exactly-once semantics
                    "enable.idempotence": True,
                    # Timeout settings
                    "message.timeout.ms": int(self._timeout * 1000),
                    "request.timeout.ms": int(self._timeout * 1000),
                    # Retries for transient failures
                    "retries": 3,
                    "retry.backoff.ms": 100,
                    # Compression for efficiency
                    "compression.type": "snappy",
                })
                logger.info(
                    "Created Kafka producer with acks=all (bootstrap=%s)",
                    self._bootstrap_servers,
                )
            except ImportError:
                logger.error("confluent-kafka not installed")
                raise

        return self._producer

    def _create_headers(self, session_id: UUID) -> list[tuple[str, bytes]]:
        """Create Kafka headers with session_id (V2).

        Per V2: session_id in headers enables session-bounded replay
        for disaster recovery without mixing sessions.

        Args:
            session_id: Deliberation session ID

        Returns:
            List of header tuples for Kafka
        """
        return [
            ("session_id", str(session_id).encode("utf-8")),
            ("published_at", str(int(time.time() * 1000)).encode("utf-8")),
        ]

    async def _publish_message(
        self,
        topic: str,
        key: str,
        value: bytes,
        headers: list[tuple[str, bytes]],
    ) -> PublishResponse:
        """Publish a message to Kafka with acks=all.

        This is the core publish method that:
        1. Checks circuit breaker
        2. Calls producer.produce()
        3. Calls producer.flush() to wait for acks=all (R1)
        4. Updates circuit breaker and metrics

        Args:
            topic: Kafka topic
            key: Message key (for partitioning)
            value: Serialized message value
            headers: Message headers

        Returns:
            PublishResponse with outcome
        """
        start_time = time.monotonic()
        self._metrics.total_publishes += 1

        # Check circuit breaker first
        if not self._circuit_breaker.should_allow_request():
            self._metrics.circuit_open_rejections += 1
            self._metrics.failed_publishes += 1
            logger.warning(
                "Publish rejected - circuit breaker OPEN (topic=%s, key=%s)",
                topic,
                key,
            )
            return PublishResponse(
                result=PublishResult.CIRCUIT_OPEN,
                error_message="Circuit breaker is open - Kafka unhealthy",
            )

        # Track delivery result
        delivery_result: dict[str, Any] = {"error": None, "partition": None, "offset": None}

        def delivery_callback(err: Any, msg: Any) -> None:
            """Callback for async delivery confirmation."""
            if err:
                delivery_result["error"] = str(err)
            else:
                delivery_result["partition"] = msg.partition()
                delivery_result["offset"] = msg.offset()

        try:
            producer = self._get_producer()

            # Produce message (async)
            producer.produce(
                topic=topic,
                key=key.encode("utf-8"),
                value=value,
                headers=headers,
                callback=delivery_callback,
            )

            # Flush to wait for acks=all (R1: send_and_wait behavior)
            # This blocks until the message is durably written
            remaining = producer.flush(timeout=self._timeout)

            if remaining > 0:
                # Messages still in queue - timeout
                self._circuit_breaker.record_failure()
                self._metrics.timeouts += 1
                self._metrics.failed_publishes += 1
                logger.error(
                    "Publish timeout - %d messages still pending (topic=%s, key=%s)",
                    remaining,
                    topic,
                    key,
                )
                return PublishResponse(
                    result=PublishResult.TIMEOUT,
                    error_message=f"Publish timeout - {remaining} messages pending",
                )

            # Check delivery result
            if delivery_result["error"]:
                self._circuit_breaker.record_failure()
                self._metrics.broker_errors += 1
                self._metrics.failed_publishes += 1
                logger.error(
                    "Publish failed - broker error: %s (topic=%s, key=%s)",
                    delivery_result["error"],
                    topic,
                    key,
                )
                return PublishResponse(
                    result=PublishResult.BROKER_ERROR,
                    error_message=delivery_result["error"],
                )

            # Success!
            self._circuit_breaker.record_success()
            self._metrics.successful_publishes += 1

            elapsed_ms = (time.monotonic() - start_time) * 1000
            self._metrics.total_latency_ms += elapsed_ms
            self._metrics.last_publish_time = time.monotonic()

            logger.debug(
                "Published message (topic=%s, partition=%s, offset=%s, latency=%.1fms)",
                topic,
                delivery_result["partition"],
                delivery_result["offset"],
                elapsed_ms,
            )

            return PublishResponse(
                result=PublishResult.SUCCESS,
                topic=topic,
                partition=delivery_result["partition"],
                offset=delivery_result["offset"],
            )

        except SchemaRegistryUnavailableError as e:
            self._circuit_breaker.record_failure()
            self._metrics.schema_errors += 1
            self._metrics.failed_publishes += 1
            logger.error("Schema Registry unavailable: %s", e)
            return PublishResponse(
                result=PublishResult.SCHEMA_ERROR,
                error_message=str(e),
            )

        except Exception as e:
            self._circuit_breaker.record_failure()
            self._metrics.broker_errors += 1
            self._metrics.failed_publishes += 1
            logger.error("Unexpected publish error: %s", e)
            return PublishResponse(
                result=PublishResult.BROKER_ERROR,
                error_message=str(e),
            )

    async def publish_pending_vote(self, vote: PendingVote) -> PublishResponse:
        """Publish a vote for async validation.

        Publishes to 'pending-validation' topic with vote_id as key
        for partition affinity.

        Args:
            vote: The vote to publish

        Returns:
            PublishResponse with outcome
        """
        try:
            # Serialize to Avro
            value = self._serializer.serialize(
                "pending_validation",
                vote.to_avro_dict(),
            )
        except SerializationError as e:
            self._metrics.schema_errors += 1
            self._metrics.failed_publishes += 1
            return PublishResponse(
                result=PublishResult.SCHEMA_ERROR,
                error_message=str(e),
            )

        headers = self._create_headers(vote.session_id)

        return await self._publish_message(
            topic=TOPIC_PENDING_VALIDATION,
            key=str(vote.vote_id),
            value=value,
            headers=headers,
        )

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

        Args:
            vote_id: Vote being validated
            session_id: Session for header
            validator_id: Which validator produced this result
            validated_choice: APPROVE/REJECT/ABSTAIN/INVALID
            confidence: Confidence score 0.0-1.0
            attempt: Retry attempt number

        Returns:
            PublishResponse with outcome
        """
        try:
            value = self._serializer.serialize(
                "validation_result",
                {
                    "vote_id": str(vote_id),
                    "session_id": str(session_id),
                    "validator_id": validator_id,
                    "validated_choice": validated_choice,
                    "confidence": confidence,
                    "attempt": attempt,
                    "timestamp_ms": int(time.time() * 1000),
                },
            )
        except SerializationError as e:
            self._metrics.schema_errors += 1
            self._metrics.failed_publishes += 1
            return PublishResponse(
                result=PublishResult.SCHEMA_ERROR,
                error_message=str(e),
            )

        headers = self._create_headers(session_id)

        return await self._publish_message(
            topic=TOPIC_VALIDATION_RESULTS,
            key=str(vote_id),
            value=value,
            headers=headers,
        )

    async def publish_to_dead_letter(
        self,
        vote_id: UUID,
        session_id: UUID,
        failure_reason: str,
        last_validator_responses: list[dict[str, Any]],
    ) -> PublishResponse:
        """Publish a vote to the dead letter queue.

        Args:
            vote_id: Vote that failed validation
            session_id: Session for header
            failure_reason: Why validation failed
            last_validator_responses: Final validator responses

        Returns:
            PublishResponse with outcome
        """
        try:
            value = self._serializer.serialize(
                "dead_letter",
                {
                    "vote_id": str(vote_id),
                    "session_id": str(session_id),
                    "failure_reason": failure_reason,
                    "last_validator_responses": last_validator_responses,
                    "failed_at_ms": int(time.time() * 1000),
                },
            )
        except SerializationError as e:
            self._metrics.schema_errors += 1
            self._metrics.failed_publishes += 1
            return PublishResponse(
                result=PublishResult.SCHEMA_ERROR,
                error_message=str(e),
            )

        headers = self._create_headers(session_id)

        return await self._publish_message(
            topic=TOPIC_DEAD_LETTER,
            key=str(vote_id),
            value=value,
            headers=headers,
        )

    def get_circuit_state(self) -> str:
        """Get current circuit breaker state."""
        return self._circuit_breaker.state.value

    def get_publish_metrics(self) -> dict[str, Any]:
        """Get publisher metrics for monitoring."""
        avg_latency = 0.0
        if self._metrics.successful_publishes > 0:
            avg_latency = (
                self._metrics.total_latency_ms / self._metrics.successful_publishes
            )

        return {
            "total_publishes": self._metrics.total_publishes,
            "successful_publishes": self._metrics.successful_publishes,
            "failed_publishes": self._metrics.failed_publishes,
            "circuit_open_rejections": self._metrics.circuit_open_rejections,
            "schema_errors": self._metrics.schema_errors,
            "broker_errors": self._metrics.broker_errors,
            "timeouts": self._metrics.timeouts,
            "avg_latency_ms": avg_latency,
            "circuit_state": self.get_circuit_state(),
            "circuit_breaker": self._circuit_breaker.get_status(),
        }

    def force_circuit_open(self) -> None:
        """Force the circuit breaker open.

        Used by startup health gate (Story 2.2.2) when Kafka is unhealthy.
        """
        self._circuit_breaker.force_open()

    def close(self) -> None:
        """Close the producer and release resources."""
        if self._producer is not None:
            self._producer.flush(timeout=5.0)
            logger.info("Kafka producer closed")
            self._producer = None
