"""Validator worker for async vote validation.

Story 3.1: Implement Validator Worker
ADR-004: 3-Archon Vote Validation Protocol
ADR-005: Error handling strategy
Pre-mortems: P5 (Witness writes cannot be caught)

3-Archon Protocol:
  DETERMINATION (2 Secretaries must agree):
    - SECRETARY_TEXT (Orias): Interprets vote using natural language analysis
    - SECRETARY_JSON (Orobas): Interprets vote using structured output analysis
  WITNESS (1 Knight-Witness observes):
    - WITNESS (Furcas): Reviews secretaries' determination
    - AGREES: Records acknowledgment on the record
    - DISSENTS: Records objection (CANNOT change outcome)

This worker consumes validation requests from Kafka and invokes its
assigned validator LLM to validate votes. Results are published to
the validation-results topic for aggregation.
"""

import asyncio
import json
import logging
import os
import signal
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Protocol
from uuid import uuid4

from src.application.ports.agent_orchestrator import ContextBundle
from src.application.ports.vote_publisher import PublishResponse, PublishResult
from src.infrastructure.adapters.kafka.avro_serializer import (
    AvroSerializer,
    SerializationError,
)
from src.infrastructure.adapters.kafka.circuit_breaker import CircuitBreaker
from src.workers.error_handler import (
    ErrorAction,
    ErrorHandler,
    WitnessWriteError,
)
from src.workers.validation_dispatcher import TOPIC_VALIDATION_REQUESTS

logger = logging.getLogger(__name__)

# Topics for validation flow
TOPIC_VALIDATION_RESULTS = "conclave.votes.validation-results"
TOPIC_WITNESS_REQUESTS = "conclave.votes.witness-requests"
TOPIC_WITNESS_EVENTS = "conclave.votes.witness.events"


def _get_env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        parsed = int(value)
        return parsed if parsed > 0 else default
    except ValueError:
        logger.warning("Invalid %s=%s, using default %d", name, value, default)
        return default


def _get_env_float(name: str, default: float) -> float:
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        parsed = float(value)
        return parsed if parsed > 0 else default
    except ValueError:
        logger.warning("Invalid %s=%s, using default %.2f", name, value, default)
        return default


OLLAMA_MAX_CONCURRENT = _get_env_int("OLLAMA_MAX_CONCURRENT", 5)
OLLAMA_SEMAPHORE = asyncio.Semaphore(OLLAMA_MAX_CONCURRENT)


class ValidatorRole(Enum):
    """Role in the 3-Archon Vote Validation Protocol."""

    SECRETARY_TEXT = "secretary_text"  # Orias - natural language analysis
    SECRETARY_JSON = "secretary_json"  # Orobas - structured output analysis
    WITNESS = "witness"  # Furcas - observes and records agreement/dissent


class WitnessVerdict(Enum):
    """Witness verdict on secretary determination."""

    AGREES = "agrees"  # Witness acknowledges the determination
    DISSENTS = "dissents"  # Witness objects (CANNOT change outcome)


class ValidatorProtocol(Protocol):
    """Protocol for validator implementations (legacy - use SecretaryProtocol).

    Validators are LLM-based vote validators (e.g., Furcas, Orias).
    """

    async def validate_vote(
        self,
        raw_response: str,
        optimistic_choice: str,
    ) -> tuple[str, float]:
        """Validate a vote and return the validated choice.

        Args:
            raw_response: Full LLM response text
            optimistic_choice: Initial regex-parsed choice

        Returns:
            Tuple of (validated_choice, confidence)
            validated_choice: APPROVE, REJECT, ABSTAIN, or INVALID
            confidence: 0.0 to 1.0
        """
        ...


class SecretaryProtocol(Protocol):
    """Protocol for Secretary implementations in 3-Archon Protocol.

    Secretaries determine the vote choice. Two secretaries must agree.
    - SECRETARY_TEXT (Orias): Natural language analysis
    - SECRETARY_JSON (Orobas): Structured output analysis
    """

    async def determine_vote(
        self,
        raw_response: str,
        archon_id: str,
        motion_text: str,
    ) -> tuple[str, float, str]:
        """Determine the vote from the archon's response.

        Args:
            raw_response: Full LLM response text from the voting archon
            archon_id: ID of the archon who cast the vote
            motion_text: The motion being voted on

        Returns:
            Tuple of (vote_choice, confidence, reasoning)
            vote_choice: AYE, NAY, or ABSTAIN
            confidence: 0.0 to 1.0
            reasoning: Explanation for the determination
        """
        ...


class WitnessObserverProtocol(Protocol):
    """Protocol for Witness implementations in 3-Archon Protocol.

    Witness observes the secretaries' determination and records
    agreement or dissent. Witness CANNOT change the outcome.
    """

    async def observe_determination(
        self,
        raw_response: str,
        archon_id: str,
        motion_text: str,
        secretary_text_choice: str,
        secretary_json_choice: str,
        consensus_choice: str,
    ) -> tuple[WitnessVerdict, str]:
        """Observe and record verdict on the secretaries' determination.

        Args:
            raw_response: Full LLM response text from the voting archon
            archon_id: ID of the archon who cast the vote
            motion_text: The motion being voted on
            secretary_text_choice: SECRETARY_TEXT's determination
            secretary_json_choice: SECRETARY_JSON's determination
            consensus_choice: The agreed choice (same as both secretaries)

        Returns:
            Tuple of (verdict, statement)
            verdict: AGREES or DISSENTS
            statement: Witness's statement for the record
        """
        ...


class WitnessProtocol(Protocol):
    """Protocol for witness logging (constitutional).

    Per P5: Witness writes MUST NOT be wrapped in try/except.
    Failures must propagate to halt the system.
    """

    async def witness_validation_failure(
        self,
        vote_id: str,
        session_id: str,
        validator_id: str,
        error: str,
    ) -> None:
        """Witness a validation failure (constitutional).

        This method MUST NOT be wrapped in try/except.
        If it fails, the error MUST propagate.
        """
        ...


@dataclass
class WorkerMetrics:
    """Metrics tracked by the validator worker."""

    messages_consumed: int = 0
    messages_processed: int = 0
    messages_skipped: int = 0  # Wrong validator_id
    validations_succeeded: int = 0
    validations_failed: int = 0
    retries: int = 0
    dlq_routes: int = 0
    errors_propagated: int = 0  # Constitutional errors (P5)
    total_processing_time_ms: float = 0.0
    last_message_time: float | None = None


@dataclass
class ValidationResult:
    """Result from validating a vote (legacy format for backwards compatibility)."""

    vote_id: str
    session_id: str
    validator_id: str
    validated_choice: str
    confidence: float
    attempt: int
    processing_time_ms: float
    timestamp_ms: int = field(default_factory=lambda: int(time.time() * 1000))

    def to_avro_dict(self) -> dict[str, Any]:
        """Convert to dictionary for Avro serialization."""
        return {
            "vote_id": self.vote_id,
            "session_id": self.session_id,
            "validator_id": self.validator_id,
            "validated_choice": self.validated_choice,
            "confidence": self.confidence,
            "attempt": self.attempt,
            "timestamp_ms": self.timestamp_ms,
        }


@dataclass
class SecretaryResult:
    """Result from a secretary determining a vote (3-Archon Protocol)."""

    vote_id: str
    session_id: str
    archon_id: str  # The archon who cast the vote
    secretary_id: str  # The secretary (Orias/Orobas) who determined
    role: ValidatorRole  # SECRETARY_TEXT or SECRETARY_JSON
    vote_choice: str  # AYE, NAY, ABSTAIN
    confidence: float
    reasoning: str
    attempt: int
    processing_time_ms: float
    timestamp_ms: int = field(default_factory=lambda: int(time.time() * 1000))

    def to_avro_dict(self) -> dict[str, Any]:
        """Convert to dictionary for Avro serialization."""
        return {
            "vote_id": self.vote_id,
            "session_id": self.session_id,
            "archon_id": self.archon_id,
            "secretary_id": self.secretary_id,
            "role": self.role.value,
            "vote_choice": self.vote_choice,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "attempt": self.attempt,
            "timestamp_ms": self.timestamp_ms,
        }


@dataclass
class WitnessResult:
    """Result from witness observing the determination (3-Archon Protocol)."""

    vote_id: str
    session_id: str
    archon_id: str  # The archon who cast the vote
    witness_id: str  # The witness (Furcas)
    consensus_choice: str  # The choice agreed by both secretaries
    verdict: WitnessVerdict  # AGREES or DISSENTS
    statement: str  # Witness statement for the record
    secretary_text_choice: str
    secretary_json_choice: str
    processing_time_ms: float
    timestamp_ms: int = field(default_factory=lambda: int(time.time() * 1000))

    def to_avro_dict(self) -> dict[str, Any]:
        """Convert to dictionary for Avro serialization."""
        return {
            "vote_id": self.vote_id,
            "session_id": self.session_id,
            "archon_id": self.archon_id,
            "witness_id": self.witness_id,
            "consensus_choice": self.consensus_choice,
            "verdict": self.verdict.value,
            "statement": self.statement,
            "secretary_text_choice": self.secretary_text_choice,
            "secretary_json_choice": self.secretary_json_choice,
            "timestamp_ms": self.timestamp_ms,
        }


class ValidatorWorker:
    """Kafka consumer worker that validates votes.

    Each worker instance is dedicated to exactly one validator (Round 7).
    The worker filters messages by validator_id header and only processes
    requests targeted at its assigned validator.

    Constitutional Behavior (P5):
    - WitnessWriteError MUST propagate (ErrorAction.PROPAGATE)
    - Worker does NOT catch constitutional errors
    - System halts on witness write failure

    Usage:
        # Start with environment variable
        # VALIDATOR_ARCHON_ID=furcas_validator python -m src.workers.validator_worker

        worker = ValidatorWorker(
            bootstrap_servers="localhost:19092",
            schema_registry_url="http://localhost:18081",
            consumer_group="conclave-validators",
            validator_id="furcas_validator",
            validator=furcas_validator_instance,
        )

        await worker.run()
    """

    def __init__(
        self,
        bootstrap_servers: str,
        schema_registry_url: str,
        consumer_group: str,
        validator_id: str,
        validator: ValidatorProtocol,
        witness: WitnessProtocol | None = None,
        error_handler: ErrorHandler | None = None,
        max_poll_records: int = 10,
        poll_timeout_seconds: float = 1.0,
    ) -> None:
        """Initialize the validator worker.

        Args:
            bootstrap_servers: Kafka bootstrap servers
            schema_registry_url: Schema Registry URL
            consumer_group: Consumer group for coordination
            validator_id: This worker's assigned validator ID
            validator: Validator implementation to invoke
            witness: Optional witness for constitutional logging
            error_handler: Optional error handler (creates default if None)
            max_poll_records: Max records per poll
            poll_timeout_seconds: Poll timeout
        """
        self._bootstrap_servers = bootstrap_servers
        self._consumer_group = consumer_group
        self._validator_id = validator_id
        self._validator = validator
        self._witness = witness
        self._poll_timeout = poll_timeout_seconds
        self._max_poll_records = max_poll_records

        # Error handler per ADR-005
        retry_attempts = _get_env_int("OLLAMA_RETRY_MAX_ATTEMPTS", 5)
        base_delay = _get_env_float("OLLAMA_RETRY_BASE_DELAY", 1.0)
        max_delay = _get_env_float("OLLAMA_RETRY_MAX_DELAY", 60.0)
        self._error_handler = error_handler or ErrorHandler(
            max_attempts=retry_attempts,
            base_delay_seconds=base_delay,
            max_delay_seconds=max_delay,
        )

        # Serializer for Avro messages
        self._serializer = AvroSerializer(
            schema_registry_url=schema_registry_url,
            require_registry=True,
        )

        # Circuit breaker for publishing results
        self._circuit_breaker = CircuitBreaker(
            failure_threshold=3,
            reset_timeout=30.0,
        )

        # Consumer and producer (lazy-loaded)
        self._consumer: Any = None
        self._producer: Any = None

        # State
        self._running = False
        self._metrics = WorkerMetrics()

        logger.info(
            "ValidatorWorker initialized: validator_id=%s, group=%s",
            validator_id,
            consumer_group,
        )

    def _get_consumer(self) -> Any:
        """Get or create the Kafka consumer."""
        if self._consumer is None:
            try:
                from confluent_kafka import Consumer

                self._consumer = Consumer({
                    "bootstrap.servers": self._bootstrap_servers,
                    "group.id": self._consumer_group,
                    "auto.offset.reset": "earliest",
                    "enable.auto.commit": False,  # Manual commit for exactly-once
                    "max.poll.interval.ms": 300000,  # 5 minutes
                    "session.timeout.ms": 45000,
                })

                self._consumer.subscribe([TOPIC_VALIDATION_REQUESTS])
                logger.info(
                    "Consumer subscribed to %s",
                    TOPIC_VALIDATION_REQUESTS,
                )

            except ImportError:
                logger.error("confluent-kafka not installed")
                raise

        return self._consumer

    def _get_producer(self) -> Any:
        """Get or create the Kafka producer."""
        if self._producer is None:
            try:
                from confluent_kafka import Producer

                self._producer = Producer({
                    "bootstrap.servers": self._bootstrap_servers,
                    "acks": "all",
                    "enable.idempotence": True,
                    "message.timeout.ms": 10000,
                    "request.timeout.ms": 10000,
                    "retries": 3,
                    "compression.type": "snappy",
                })

            except ImportError:
                logger.error("confluent-kafka not installed")
                raise

        return self._producer

    def _extract_validator_id(self, message: Any) -> str | None:
        """Extract validator_id from message headers.

        Args:
            message: Kafka message

        Returns:
            validator_id or None if not found
        """
        headers = message.headers() or []
        for key, value in headers:
            if key == "validator_id" and value:
                return value.decode("utf-8")
        return None

    async def _publish_result(self, result: ValidationResult) -> PublishResponse:
        """Publish validation result to Kafka.

        Args:
            result: The validation result to publish

        Returns:
            PublishResponse with outcome
        """
        if not self._circuit_breaker.should_allow_request():
            return PublishResponse(
                result=PublishResult.CIRCUIT_OPEN,
                error_message="Circuit breaker is open",
            )

        try:
            value = self._serializer.serialize(
                "validation_result",
                result.to_avro_dict(),
            )
        except SerializationError as e:
            self._circuit_breaker.record_failure()
            return PublishResponse(
                result=PublishResult.SCHEMA_ERROR,
                error_message=str(e),
            )

        headers = [
            ("session_id", result.session_id.encode("utf-8")),
            ("validator_id", result.validator_id.encode("utf-8")),
            ("processed_at", str(result.timestamp_ms).encode("utf-8")),
        ]

        delivery_result: dict[str, Any] = {"error": None}

        def delivery_callback(err: Any, msg: Any) -> None:
            if err:
                delivery_result["error"] = str(err)

        try:
            producer = self._get_producer()

            producer.produce(
                topic=TOPIC_VALIDATION_RESULTS,
                key=result.vote_id.encode("utf-8"),
                value=value,
                headers=headers,
                callback=delivery_callback,
            )

            remaining = producer.flush(timeout=10.0)

            if remaining > 0 or delivery_result["error"]:
                self._circuit_breaker.record_failure()
                return PublishResponse(
                    result=PublishResult.BROKER_ERROR,
                    error_message=delivery_result["error"] or "Flush timeout",
                )

            self._circuit_breaker.record_success()
            return PublishResponse(result=PublishResult.SUCCESS)

        except Exception as e:
            self._circuit_breaker.record_failure()
            return PublishResponse(
                result=PublishResult.BROKER_ERROR,
                error_message=str(e),
            )

    async def _process_message(self, message: Any) -> None:
        """Process a single validation request message.

        Args:
            message: Kafka message to process
        """
        self._metrics.messages_consumed += 1
        start_time = time.monotonic()

        # Check if this message is for our validator
        msg_validator_id = self._extract_validator_id(message)

        if msg_validator_id != self._validator_id:
            # Skip messages for other validators
            self._metrics.messages_skipped += 1
            logger.debug(
                "Skipping message for validator %s (we are %s)",
                msg_validator_id,
                self._validator_id,
            )
            return

        # Deserialize request
        try:
            request_data = self._serializer.deserialize(
                "validation_request",
                message.value(),
            )
        except SerializationError as e:
            logger.error("Failed to deserialize message: %s", e)
            self._metrics.validations_failed += 1
            return

        vote_id = request_data["vote_id"]
        session_id = request_data["session_id"]
        attempt = request_data.get("attempt", 1)

        logger.debug(
            "Processing validation request: vote=%s validator=%s attempt=%d",
            vote_id,
            self._validator_id,
            attempt,
        )

        # Invoke validator with in-process retry/backoff
        try:
            while True:
                try:
                    async with OLLAMA_SEMAPHORE:
                        validated_choice, confidence = (
                            await self._validator.validate_vote(
                                raw_response=request_data["raw_response"],
                                optimistic_choice=request_data["optimistic_choice"],
                            )
                        )

                    processing_time = (time.monotonic() - start_time) * 1000

                    # Create result
                    result = ValidationResult(
                        vote_id=vote_id,
                        session_id=session_id,
                        validator_id=self._validator_id,
                        validated_choice=validated_choice,
                        confidence=confidence,
                        attempt=attempt,
                        processing_time_ms=processing_time,
                    )

                    # Publish result
                    response = await self._publish_result(result)

                    if response.success:
                        self._metrics.validations_succeeded += 1
                        self._metrics.messages_processed += 1
                        logger.info(
                            "Validation complete: vote=%s choice=%s confidence=%.2f",
                            vote_id,
                            validated_choice,
                            confidence,
                        )
                    else:
                        logger.error(
                            "Failed to publish validation result: vote=%s error=%s",
                            vote_id,
                            response.error_message,
                        )
                        self._metrics.validations_failed += 1

                    return

                except WitnessWriteError:
                    # P5: Constitutional error - MUST propagate
                    self._metrics.errors_propagated += 1
                    logger.critical(
                        "Constitutional error (WitnessWriteError) - propagating: vote=%s",
                        vote_id,
                    )
                    raise  # DO NOT catch - system must halt

                except Exception as e:
                    # Handle error per ADR-005
                    decision = self._error_handler.handle(e, attempt=attempt)
                    self._metrics.validations_failed += 1

                    if decision.action == ErrorAction.PROPAGATE:
                        # Constitutional - propagate
                        self._metrics.errors_propagated += 1
                        logger.critical(
                            "Error requires propagation: vote=%s error=%s",
                            vote_id,
                            e,
                        )
                        raise

                    if decision.action == ErrorAction.RETRY:
                        self._metrics.retries += 1
                        logger.warning(
                            "Validation error - retrying in %.1fs: vote=%s error=%s",
                            decision.retry_delay_seconds,
                            vote_id,
                            e,
                        )
                        await asyncio.sleep(decision.retry_delay_seconds)
                        attempt += 1
                        continue

                    if decision.action == ErrorAction.DEAD_LETTER:
                        self._metrics.dlq_routes += 1
                        logger.error(
                            "Validation failed - routing to DLQ: vote=%s error=%s",
                            vote_id,
                            e,
                        )
                        return

                    if decision.action == ErrorAction.SKIP:
                        self._metrics.messages_skipped += 1
                        logger.debug(
                            "Duplicate validation skipped: vote=%s",
                            vote_id,
                        )
                        return

        finally:
            processing_time = (time.monotonic() - start_time) * 1000
            self._metrics.total_processing_time_ms += processing_time
            self._metrics.last_message_time = time.monotonic()

    async def run(self) -> None:
        """Run the worker event loop.

        This method runs until stop() is called or a constitutional
        error occurs (P5).
        """
        self._running = True
        consumer = self._get_consumer()

        logger.info(
            "ValidatorWorker starting: validator_id=%s",
            self._validator_id,
        )

        try:
            while self._running:
                # Poll for messages
                message = consumer.poll(timeout=self._poll_timeout)

                if message is None:
                    continue

                if message.error():
                    logger.error("Consumer error: %s", message.error())
                    continue

                # Process the message
                await self._process_message(message)

                # Commit offset after successful processing
                consumer.commit(message=message, asynchronous=False)

        except KeyboardInterrupt:
            logger.info("Worker interrupted by user")

        except Exception as e:
            # Constitutional errors propagate here
            logger.critical("Worker fatal error: %s", e)
            raise

        finally:
            self._running = False
            self._cleanup()

    def stop(self) -> None:
        """Signal the worker to stop."""
        logger.info("Worker stop requested")
        self._running = False

    def _cleanup(self) -> None:
        """Clean up resources."""
        if self._consumer:
            self._consumer.close()
            logger.info("Consumer closed")

        if self._producer:
            self._producer.flush(timeout=5.0)
            logger.info("Producer flushed")

    def get_metrics(self) -> dict[str, Any]:
        """Get worker metrics for monitoring."""
        avg_processing_time = 0.0
        if self._metrics.messages_processed > 0:
            avg_processing_time = (
                self._metrics.total_processing_time_ms
                / self._metrics.messages_processed
            )

        return {
            "validator_id": self._validator_id,
            "messages_consumed": self._metrics.messages_consumed,
            "messages_processed": self._metrics.messages_processed,
            "messages_skipped": self._metrics.messages_skipped,
            "validations_succeeded": self._metrics.validations_succeeded,
            "validations_failed": self._metrics.validations_failed,
            "retries": self._metrics.retries,
            "dlq_routes": self._metrics.dlq_routes,
            "errors_propagated": self._metrics.errors_propagated,
            "avg_processing_time_ms": avg_processing_time,
            "circuit_state": self._circuit_breaker.state.value,
            "running": self._running,
        }


async def run_validator_worker(
    bootstrap_servers: str,
    schema_registry_url: str,
    consumer_group: str,
    validator_id: str,
    validator: ValidatorProtocol,
    witness: WitnessProtocol | None = None,
) -> None:
    """Run a validator worker with graceful shutdown.

    Args:
        bootstrap_servers: Kafka bootstrap servers
        schema_registry_url: Schema Registry URL
        consumer_group: Consumer group
        validator_id: This worker's validator ID
        validator: Validator implementation
        witness: Optional witness for constitutional logging
    """
    worker = ValidatorWorker(
        bootstrap_servers=bootstrap_servers,
        schema_registry_url=schema_registry_url,
        consumer_group=consumer_group,
        validator_id=validator_id,
        validator=validator,
        witness=witness,
    )

    # Setup signal handlers for graceful shutdown
    loop = asyncio.get_event_loop()

    def signal_handler() -> None:
        worker.stop()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, signal_handler)

    await worker.run()


# =============================================================================
# 3-ARCHON PROTOCOL WORKERS
# =============================================================================


@dataclass
class SecretaryWorkerMetrics:
    """Metrics tracked by the secretary worker."""

    messages_consumed: int = 0
    messages_processed: int = 0
    messages_skipped: int = 0
    determinations_succeeded: int = 0
    determinations_failed: int = 0
    retries: int = 0
    dlq_routes: int = 0
    errors_propagated: int = 0
    total_processing_time_ms: float = 0.0
    last_message_time: float | None = None


class SecretaryWorker:
    """Kafka consumer worker for Secretary role in 3-Archon Protocol.

    Secretaries determine the vote choice from archon responses.
    Two secretaries (SECRETARY_TEXT and SECRETARY_JSON) must agree
    before a vote is considered validated.

    Usage:
        worker = SecretaryWorker(
            bootstrap_servers="localhost:19092",
            schema_registry_url="http://localhost:18081",
            consumer_group="conclave-secretaries",
            secretary_id="orias_secretary",
            role=ValidatorRole.SECRETARY_TEXT,
            secretary=orias_secretary_instance,
        )

        await worker.run()
    """

    def __init__(
        self,
        bootstrap_servers: str,
        schema_registry_url: str,
        consumer_group: str,
        secretary_id: str,
        role: ValidatorRole,
        secretary: SecretaryProtocol,
        error_handler: ErrorHandler | None = None,
        poll_timeout_seconds: float = 1.0,
    ) -> None:
        """Initialize the secretary worker.

        Args:
            bootstrap_servers: Kafka bootstrap servers
            schema_registry_url: Schema Registry URL
            consumer_group: Consumer group for coordination
            secretary_id: This worker's secretary ID (e.g., Orias, Orobas)
            role: SECRETARY_TEXT or SECRETARY_JSON
            secretary: Secretary implementation to invoke
            error_handler: Optional error handler
            poll_timeout_seconds: Poll timeout
        """
        if role not in {ValidatorRole.SECRETARY_TEXT, ValidatorRole.SECRETARY_JSON}:
            raise ValueError(f"Invalid role for SecretaryWorker: {role}")

        self._bootstrap_servers = bootstrap_servers
        self._consumer_group = consumer_group
        self._secretary_id = secretary_id
        self._role = role
        self._secretary = secretary
        self._poll_timeout = poll_timeout_seconds

        # Error handler
        retry_attempts = _get_env_int("OLLAMA_RETRY_MAX_ATTEMPTS", 5)
        base_delay = _get_env_float("OLLAMA_RETRY_BASE_DELAY", 1.0)
        max_delay = _get_env_float("OLLAMA_RETRY_MAX_DELAY", 60.0)
        self._error_handler = error_handler or ErrorHandler(
            max_attempts=retry_attempts,
            base_delay_seconds=base_delay,
            max_delay_seconds=max_delay,
        )

        # Serializer
        self._serializer = AvroSerializer(
            schema_registry_url=schema_registry_url,
            require_registry=True,
        )

        # Circuit breaker
        self._circuit_breaker = CircuitBreaker(
            failure_threshold=3,
            reset_timeout=30.0,
        )

        # Consumer and producer (lazy-loaded)
        self._consumer: Any = None
        self._producer: Any = None

        # State
        self._running = False
        self._metrics = SecretaryWorkerMetrics()

        logger.info(
            "SecretaryWorker initialized: secretary_id=%s role=%s",
            secretary_id,
            role.value,
        )

    def _get_consumer(self) -> Any:
        """Get or create the Kafka consumer."""
        if self._consumer is None:
            from confluent_kafka import Consumer

            self._consumer = Consumer({
                "bootstrap.servers": self._bootstrap_servers,
                "group.id": self._consumer_group,
                "auto.offset.reset": "earliest",
                "enable.auto.commit": False,
                "max.poll.interval.ms": 300000,
                "session.timeout.ms": 45000,
            })

            self._consumer.subscribe([TOPIC_VALIDATION_REQUESTS])
            logger.info("Secretary subscribed to %s", TOPIC_VALIDATION_REQUESTS)

        return self._consumer

    def _get_producer(self) -> Any:
        """Get or create the Kafka producer."""
        if self._producer is None:
            from confluent_kafka import Producer

            self._producer = Producer({
                "bootstrap.servers": self._bootstrap_servers,
                "acks": "all",
                "enable.idempotence": True,
                "message.timeout.ms": 10000,
                "retries": 3,
                "compression.type": "snappy",
            })

        return self._producer

    def _extract_role_header(self, message: Any) -> str | None:
        """Extract target role from message headers."""
        headers = message.headers() or []
        for key, value in headers:
            if key == "target_role" and value:
                return value.decode("utf-8")
        return None

    async def _publish_result(self, result: SecretaryResult) -> PublishResponse:
        """Publish secretary determination result to Kafka."""
        if not self._circuit_breaker.should_allow_request():
            return PublishResponse(
                result=PublishResult.CIRCUIT_OPEN,
                error_message="Circuit breaker is open",
            )

        try:
            value = self._serializer.serialize(
                "secretary_result",
                result.to_avro_dict(),
            )
        except SerializationError as e:
            self._circuit_breaker.record_failure()
            return PublishResponse(
                result=PublishResult.SCHEMA_ERROR,
                error_message=str(e),
            )

        headers = [
            ("session_id", result.session_id.encode("utf-8")),
            ("secretary_id", result.secretary_id.encode("utf-8")),
            ("role", result.role.value.encode("utf-8")),
        ]

        delivery_result: dict[str, Any] = {"error": None}

        def delivery_callback(err: Any, msg: Any) -> None:
            if err:
                delivery_result["error"] = str(err)

        try:
            producer = self._get_producer()
            producer.produce(
                topic=TOPIC_VALIDATION_RESULTS,
                key=result.vote_id.encode("utf-8"),
                value=value,
                headers=headers,
                callback=delivery_callback,
            )
            remaining = producer.flush(timeout=10.0)

            if remaining > 0 or delivery_result["error"]:
                self._circuit_breaker.record_failure()
                return PublishResponse(
                    result=PublishResult.BROKER_ERROR,
                    error_message=delivery_result["error"] or "Flush timeout",
                )

            self._circuit_breaker.record_success()
            return PublishResponse(result=PublishResult.SUCCESS)

        except Exception as e:
            self._circuit_breaker.record_failure()
            return PublishResponse(
                result=PublishResult.BROKER_ERROR,
                error_message=str(e),
            )

    async def _process_message(self, message: Any) -> None:
        """Process a single validation request message."""
        self._metrics.messages_consumed += 1
        start_time = time.monotonic()

        # Check if this message is for our role
        target_role = self._extract_role_header(message)
        if target_role and target_role != self._role.value:
            self._metrics.messages_skipped += 1
            return

        # Deserialize request
        try:
            request_data = self._serializer.deserialize(
                "validation_request",
                message.value(),
            )
        except SerializationError as e:
            logger.error("Failed to deserialize message: %s", e)
            self._metrics.determinations_failed += 1
            return

        vote_id = request_data["vote_id"]
        session_id = request_data["session_id"]
        archon_id = request_data.get("archon_id", "unknown")
        raw_response = request_data["raw_response"]
        motion_text = request_data.get("motion_text", "")
        attempt = request_data.get("attempt", 1)

        logger.debug(
            "Processing determination: vote=%s secretary=%s role=%s",
            vote_id,
            self._secretary_id,
            self._role.value,
        )

        try:
            async with OLLAMA_SEMAPHORE:
                vote_choice, confidence, reasoning = await self._secretary.determine_vote(
                    raw_response=raw_response,
                    archon_id=archon_id,
                    motion_text=motion_text,
                )

            processing_time = (time.monotonic() - start_time) * 1000

            result = SecretaryResult(
                vote_id=vote_id,
                session_id=session_id,
                archon_id=archon_id,
                secretary_id=self._secretary_id,
                role=self._role,
                vote_choice=vote_choice,
                confidence=confidence,
                reasoning=reasoning,
                attempt=attempt,
                processing_time_ms=processing_time,
            )

            response = await self._publish_result(result)

            if response.success:
                self._metrics.determinations_succeeded += 1
                self._metrics.messages_processed += 1
                logger.info(
                    "Determination complete: vote=%s choice=%s confidence=%.2f",
                    vote_id,
                    vote_choice,
                    confidence,
                )
            else:
                logger.error(
                    "Failed to publish determination: vote=%s error=%s",
                    vote_id,
                    response.error_message,
                )
                self._metrics.determinations_failed += 1

        except WitnessWriteError:
            self._metrics.errors_propagated += 1
            raise

        except Exception as e:
            decision = self._error_handler.handle(e, attempt=attempt)
            self._metrics.determinations_failed += 1

            if decision.action == ErrorAction.PROPAGATE:
                self._metrics.errors_propagated += 1
                raise

            logger.error(
                "Secretary determination failed: vote=%s error=%s action=%s",
                vote_id,
                e,
                decision.action.value,
            )

        finally:
            processing_time = (time.monotonic() - start_time) * 1000
            self._metrics.total_processing_time_ms += processing_time
            self._metrics.last_message_time = time.monotonic()

    async def run(self) -> None:
        """Run the secretary worker event loop."""
        self._running = True
        consumer = self._get_consumer()

        logger.info(
            "SecretaryWorker starting: secretary_id=%s role=%s",
            self._secretary_id,
            self._role.value,
        )

        try:
            while self._running:
                message = consumer.poll(timeout=self._poll_timeout)

                if message is None:
                    continue

                if message.error():
                    logger.error("Consumer error: %s", message.error())
                    continue

                await self._process_message(message)
                consumer.commit(message=message, asynchronous=False)

        except KeyboardInterrupt:
            logger.info("Secretary worker interrupted by user")

        except Exception as e:
            logger.critical("Secretary worker fatal error: %s", e)
            raise

        finally:
            self._running = False
            self._cleanup()

    def stop(self) -> None:
        """Signal the worker to stop."""
        self._running = False

    def _cleanup(self) -> None:
        """Clean up resources."""
        if self._consumer:
            self._consumer.close()
        if self._producer:
            self._producer.flush(timeout=5.0)

    def get_metrics(self) -> dict[str, Any]:
        """Get worker metrics."""
        avg_time = 0.0
        if self._metrics.messages_processed > 0:
            avg_time = self._metrics.total_processing_time_ms / self._metrics.messages_processed

        return {
            "secretary_id": self._secretary_id,
            "role": self._role.value,
            "messages_consumed": self._metrics.messages_consumed,
            "messages_processed": self._metrics.messages_processed,
            "determinations_succeeded": self._metrics.determinations_succeeded,
            "determinations_failed": self._metrics.determinations_failed,
            "avg_processing_time_ms": avg_time,
            "circuit_state": self._circuit_breaker.state.value,
            "running": self._running,
        }


@dataclass
class WitnessWorkerMetrics:
    """Metrics tracked by the witness worker."""

    messages_consumed: int = 0
    messages_processed: int = 0
    verdicts_agrees: int = 0
    verdicts_dissents: int = 0
    errors_propagated: int = 0
    total_processing_time_ms: float = 0.0


class WitnessWorker:
    """Kafka consumer worker for Witness role in 3-Archon Protocol.

    The Witness observes the secretaries' determination and records
    agreement or dissent. The Witness CANNOT change the outcome.

    Usage:
        worker = WitnessWorker(
            bootstrap_servers="localhost:19092",
            schema_registry_url="http://localhost:18081",
            consumer_group="conclave-witness",
            witness_id="furcas_witness",
            witness=furcas_witness_instance,
        )

        await worker.run()
    """

    def __init__(
        self,
        bootstrap_servers: str,
        schema_registry_url: str,
        consumer_group: str,
        witness_id: str,
        witness: WitnessObserverProtocol,
        poll_timeout_seconds: float = 1.0,
    ) -> None:
        """Initialize the witness worker."""
        self._bootstrap_servers = bootstrap_servers
        self._consumer_group = consumer_group
        self._witness_id = witness_id
        self._witness = witness
        self._poll_timeout = poll_timeout_seconds

        self._serializer = AvroSerializer(
            schema_registry_url=schema_registry_url,
            require_registry=True,
        )

        self._circuit_breaker = CircuitBreaker(
            failure_threshold=3,
            reset_timeout=30.0,
        )

        self._consumer: Any = None
        self._producer: Any = None
        self._running = False
        self._metrics = WitnessWorkerMetrics()

        logger.info("WitnessWorker initialized: witness_id=%s", witness_id)

    def _get_consumer(self) -> Any:
        """Get or create the Kafka consumer."""
        if self._consumer is None:
            from confluent_kafka import Consumer

            self._consumer = Consumer({
                "bootstrap.servers": self._bootstrap_servers,
                "group.id": self._consumer_group,
                "auto.offset.reset": "earliest",
                "enable.auto.commit": False,
                "max.poll.interval.ms": 300000,
                "session.timeout.ms": 45000,
            })

            self._consumer.subscribe([TOPIC_WITNESS_REQUESTS])
            logger.info("Witness subscribed to %s", TOPIC_WITNESS_REQUESTS)

        return self._consumer

    def _get_producer(self) -> Any:
        """Get or create the Kafka producer."""
        if self._producer is None:
            from confluent_kafka import Producer

            self._producer = Producer({
                "bootstrap.servers": self._bootstrap_servers,
                "acks": "all",
                "enable.idempotence": True,
                "message.timeout.ms": 10000,
                "retries": 3,
                "compression.type": "snappy",
            })

        return self._producer

    async def _publish_result(self, result: WitnessResult) -> PublishResponse:
        """Publish witness verdict to Kafka."""
        if not self._circuit_breaker.should_allow_request():
            return PublishResponse(
                result=PublishResult.CIRCUIT_OPEN,
                error_message="Circuit breaker is open",
            )

        try:
            value = self._serializer.serialize(
                "witness_result",
                result.to_avro_dict(),
            )
        except SerializationError as e:
            self._circuit_breaker.record_failure()
            return PublishResponse(
                result=PublishResult.SCHEMA_ERROR,
                error_message=str(e),
            )

        headers = [
            ("session_id", result.session_id.encode("utf-8")),
            ("witness_id", result.witness_id.encode("utf-8")),
            ("verdict", result.verdict.value.encode("utf-8")),
        ]

        delivery_result: dict[str, Any] = {"error": None}

        def delivery_callback(err: Any, msg: Any) -> None:
            if err:
                delivery_result["error"] = str(err)

        try:
            producer = self._get_producer()
            producer.produce(
                topic=TOPIC_WITNESS_EVENTS,
                key=result.vote_id.encode("utf-8"),
                value=value,
                headers=headers,
                callback=delivery_callback,
            )
            remaining = producer.flush(timeout=10.0)

            if remaining > 0 or delivery_result["error"]:
                self._circuit_breaker.record_failure()
                return PublishResponse(
                    result=PublishResult.BROKER_ERROR,
                    error_message=delivery_result["error"] or "Flush timeout",
                )

            self._circuit_breaker.record_success()
            return PublishResponse(result=PublishResult.SUCCESS)

        except Exception as e:
            self._circuit_breaker.record_failure()
            return PublishResponse(
                result=PublishResult.BROKER_ERROR,
                error_message=str(e),
            )

    async def _process_message(self, message: Any) -> None:
        """Process a single witness request message."""
        self._metrics.messages_consumed += 1
        start_time = time.monotonic()

        # Deserialize request
        try:
            request_data = self._serializer.deserialize(
                "witness_request",
                message.value(),
            )
        except SerializationError as e:
            logger.error("Failed to deserialize witness request: %s", e)
            return

        vote_id = request_data["vote_id"]
        session_id = request_data["session_id"]
        archon_id = request_data.get("archon_id", "unknown")
        raw_response = request_data["raw_response"]
        motion_text = request_data.get("motion_text", "")
        secretary_text_choice = request_data["secretary_text_choice"]
        secretary_json_choice = request_data["secretary_json_choice"]
        consensus_choice = request_data["consensus_choice"]

        logger.debug(
            "Processing witness request: vote=%s consensus=%s",
            vote_id,
            consensus_choice,
        )

        try:
            async with OLLAMA_SEMAPHORE:
                verdict, statement = await self._witness.observe_determination(
                    raw_response=raw_response,
                    archon_id=archon_id,
                    motion_text=motion_text,
                    secretary_text_choice=secretary_text_choice,
                    secretary_json_choice=secretary_json_choice,
                    consensus_choice=consensus_choice,
                )

            processing_time = (time.monotonic() - start_time) * 1000

            result = WitnessResult(
                vote_id=vote_id,
                session_id=session_id,
                archon_id=archon_id,
                witness_id=self._witness_id,
                consensus_choice=consensus_choice,
                verdict=verdict,
                statement=statement,
                secretary_text_choice=secretary_text_choice,
                secretary_json_choice=secretary_json_choice,
                processing_time_ms=processing_time,
            )

            response = await self._publish_result(result)

            if response.success:
                self._metrics.messages_processed += 1
                if verdict == WitnessVerdict.AGREES:
                    self._metrics.verdicts_agrees += 1
                else:
                    self._metrics.verdicts_dissents += 1

                logger.info(
                    "Witness observation complete: vote=%s verdict=%s",
                    vote_id,
                    verdict.value,
                )
            else:
                logger.error(
                    "Failed to publish witness result: vote=%s error=%s",
                    vote_id,
                    response.error_message,
                )

        except WitnessWriteError:
            # P5: Constitutional - MUST propagate
            self._metrics.errors_propagated += 1
            raise

        except Exception as e:
            logger.error("Witness observation failed: vote=%s error=%s", vote_id, e)

        finally:
            self._metrics.total_processing_time_ms += (time.monotonic() - start_time) * 1000

    async def run(self) -> None:
        """Run the witness worker event loop."""
        self._running = True
        consumer = self._get_consumer()

        logger.info("WitnessWorker starting: witness_id=%s", self._witness_id)

        try:
            while self._running:
                message = consumer.poll(timeout=self._poll_timeout)

                if message is None:
                    continue

                if message.error():
                    logger.error("Consumer error: %s", message.error())
                    continue

                await self._process_message(message)
                consumer.commit(message=message, asynchronous=False)

        except KeyboardInterrupt:
            logger.info("Witness worker interrupted by user")

        except Exception as e:
            logger.critical("Witness worker fatal error: %s", e)
            raise

        finally:
            self._running = False
            self._cleanup()

    def stop(self) -> None:
        """Signal the worker to stop."""
        self._running = False

    def _cleanup(self) -> None:
        """Clean up resources."""
        if self._consumer:
            self._consumer.close()
        if self._producer:
            self._producer.flush(timeout=5.0)

    def get_metrics(self) -> dict[str, Any]:
        """Get worker metrics."""
        avg_time = 0.0
        if self._metrics.messages_processed > 0:
            avg_time = self._metrics.total_processing_time_ms / self._metrics.messages_processed

        return {
            "witness_id": self._witness_id,
            "messages_consumed": self._metrics.messages_consumed,
            "messages_processed": self._metrics.messages_processed,
            "verdicts_agrees": self._metrics.verdicts_agrees,
            "verdicts_dissents": self._metrics.verdicts_dissents,
            "avg_processing_time_ms": avg_time,
            "circuit_state": self._circuit_breaker.state.value,
            "running": self._running,
        }


# =============================================================================
# 3-ARCHON PROTOCOL: CrewAI-backed implementations
# =============================================================================


def _ensure_crewai_env() -> None:
    """Disable CrewAI telemetry and set writable storage defaults."""
    os.environ.setdefault("CREWAI_DISABLE_TELEMETRY", "true")
    os.environ.setdefault("CREWAI_DISABLE_TRACKING", "true")
    os.environ.setdefault("OTEL_SDK_DISABLED", "true")
    os.environ.setdefault("CREWAI_TRACING_ENABLED", "false")
    os.environ.setdefault("CREWAI_TESTING", "true")
    os.environ.setdefault("CREWAI_STORAGE_DIR", "archon72")
    os.environ.setdefault("XDG_DATA_HOME", "/tmp/crewai-data")
    Path(os.environ["XDG_DATA_HOME"]).mkdir(parents=True, exist_ok=True)


def _extract_json_payload(content: str) -> dict[str, Any] | None:
    """Extract the first JSON object from a response."""
    start = content.find("{")
    end = content.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        return json.loads(content[start : end + 1])
    except json.JSONDecodeError:
        return None


def _normalize_vote_choice(value: str) -> str | None:
    """Normalize vote choice to AYE/NAY/ABSTAIN."""
    raw = value.strip().lower()
    mapping = {
        "aye": "AYE",
        "yes": "AYE",
        "for": "AYE",
        "approve": "AYE",
        "nay": "NAY",
        "no": "NAY",
        "against": "NAY",
        "reject": "NAY",
        "abstain": "ABSTAIN",
        "abstention": "ABSTAIN",
        "neutral": "ABSTAIN",
    }
    return mapping.get(raw)


class CrewAISecretary(SecretaryProtocol):
    """SecretaryProtocol implementation backed by CrewAI."""

    def __init__(self, orchestrator: Any, secretary_id: str, role_label: str) -> None:
        self._orchestrator = orchestrator
        self._secretary_id = secretary_id
        self._role_label = role_label

    async def determine_vote(
        self,
        raw_response: str,
        archon_id: str,
        motion_text: str,
    ) -> tuple[str, float, str]:
        prompt = f"""ARCHON 72 CONCLAVE - VOTE VALIDATION

You are {self._role_label}, a secretary responsible for determining the vote.

TARGET ARCHON: {archon_id}
MOTION:
{motion_text}

RAW VOTE RESPONSE:
<<<
{raw_response[:2000]}
>>>

Return JSON only (no prose):
{{\"choice\":\"AYE\"}} or {{\"choice\":\"NAY\"}} or {{\"choice\":\"ABSTAIN\"}}
If unclear, choose ABSTAIN.
"""

        bundle = ContextBundle(
            bundle_id=uuid4(),
            topic_id=f"vote-validate-{archon_id}-{self._secretary_id}",
            topic_content=prompt,
            metadata={
                "validation": "vote",
                "secretary_role": self._role_label,
            },
            created_at=datetime.now(timezone.utc),
        )

        output = await self._orchestrator.invoke(self._secretary_id, bundle)
        payload = _extract_json_payload(output.content)
        if not payload:
            return "ABSTAIN", 0.0, "unparseable_response"

        choice_value = _normalize_vote_choice(str(payload.get("choice", "")))
        if not choice_value:
            return "ABSTAIN", 0.0, "invalid_choice"

        return choice_value, 0.75, ""


class CrewAIWitness(WitnessObserverProtocol):
    """WitnessObserverProtocol implementation backed by CrewAI."""

    def __init__(self, orchestrator: Any, witness_id: str) -> None:
        self._orchestrator = orchestrator
        self._witness_id = witness_id

    async def observe_determination(
        self,
        raw_response: str,
        archon_id: str,
        motion_text: str,
        secretary_text_choice: str,
        secretary_json_choice: str,
        consensus_choice: str,
    ) -> tuple[WitnessVerdict, str]:
        prompt = f"""ARCHON 72 CONCLAVE - WITNESS OBSERVATION

You are the WITNESS. Review the secretaries' determination and record agreement or dissent.

TARGET ARCHON: {archon_id}
MOTION:
{motion_text}

RAW VOTE RESPONSE:
<<<
{raw_response[:2000]}
>>>

SECRETARY_TEXT CHOICE: {secretary_text_choice}
SECRETARY_JSON CHOICE: {secretary_json_choice}
CONSENSUS CHOICE: {consensus_choice}

Return JSON only:
{{\"verdict\":\"AGREES\",\"statement\":\"...\"}} or {{\"verdict\":\"DISSENTS\",\"statement\":\"...\"}}
"""

        bundle = ContextBundle(
            bundle_id=uuid4(),
            topic_id=f"witness-{archon_id}-{self._witness_id}",
            topic_content=prompt,
            metadata={
                "validation": "witness",
            },
            created_at=datetime.now(timezone.utc),
        )

        output = await self._orchestrator.invoke(self._witness_id, bundle)
        payload = _extract_json_payload(output.content)
        if not payload:
            return WitnessVerdict.DISSENTS, "unparseable_response"

        verdict_raw = str(payload.get("verdict", "")).strip().upper()
        statement = str(payload.get("statement", "")).strip()

        verdict = WitnessVerdict.DISSENTS
        if verdict_raw == WitnessVerdict.AGREES.value:
            verdict = WitnessVerdict.AGREES
        elif verdict_raw == WitnessVerdict.DISSENTS.value:
            verdict = WitnessVerdict.DISSENTS

        if not statement:
            statement = "witness_verdict_recorded"

        return verdict, statement


def _get_env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return value.strip()


def _resolve_archon_id(role: str) -> str | None:
    archon_id = _get_env("VALIDATOR_ARCHON_ID")
    if archon_id:
        return archon_id
    if role == "secretary_text":
        return _get_env("SECRETARY_TEXT_ARCHON_ID")
    if role == "secretary_json":
        return _get_env("SECRETARY_JSON_ARCHON_ID")
    if role == "witness":
        return _get_env("WITNESS_ARCHON_ID")
    return None


async def _run_from_env() -> None:
    try:
        from dotenv import load_dotenv
    except Exception:
        load_dotenv = None

    if load_dotenv:
        load_dotenv()

    _ensure_crewai_env()

    role = (_get_env("VALIDATOR_ROLE") or "").lower()
    if not role:
        print("ERROR: VALIDATOR_ROLE must be set (secretary_text, secretary_json, witness)")
        sys.exit(1)

    archon_id = _resolve_archon_id(role)
    if not archon_id:
        print("ERROR: VALIDATOR_ARCHON_ID (or role-specific override) is required")
        sys.exit(1)

    bootstrap_servers = _get_env("KAFKA_BOOTSTRAP_SERVERS", "localhost:19092") or "localhost:19092"
    schema_registry_url = _get_env("SCHEMA_REGISTRY_URL", "http://localhost:18081") or "http://localhost:18081"

    if role in {"secretary_text", "secretary_json"}:
        consumer_group = _get_env("KAFKA_CONSUMER_GROUP", "conclave-secretaries") or "conclave-secretaries"
    elif role == "witness":
        consumer_group = _get_env("KAFKA_CONSUMER_GROUP", "conclave-witness") or "conclave-witness"
    else:
        consumer_group = _get_env("KAFKA_CONSUMER_GROUP", "conclave-validators") or "conclave-validators"

    from src.infrastructure.adapters.config.archon_profile_adapter import (
        create_archon_profile_repository,
    )
    from src.infrastructure.adapters.external import create_crewai_adapter

    profile_repo = create_archon_profile_repository()
    orchestrator = create_crewai_adapter(
        profile_repository=profile_repo,
        verbose=False,
        include_default_tools=False,
    )

    if role == "secretary_text":
        secretary = CrewAISecretary(orchestrator, archon_id, "SECRETARY_TEXT")
        worker = SecretaryWorker(
            bootstrap_servers=bootstrap_servers,
            schema_registry_url=schema_registry_url,
            consumer_group=consumer_group,
            secretary_id=archon_id,
            role=ValidatorRole.SECRETARY_TEXT,
            secretary=secretary,
        )
        await worker.run()
        return

    if role == "secretary_json":
        secretary = CrewAISecretary(orchestrator, archon_id, "SECRETARY_JSON")
        worker = SecretaryWorker(
            bootstrap_servers=bootstrap_servers,
            schema_registry_url=schema_registry_url,
            consumer_group=consumer_group,
            secretary_id=archon_id,
            role=ValidatorRole.SECRETARY_JSON,
            secretary=secretary,
        )
        await worker.run()
        return

    if role == "witness":
        witness = CrewAIWitness(orchestrator, archon_id)
        worker = WitnessWorker(
            bootstrap_servers=bootstrap_servers,
            schema_registry_url=schema_registry_url,
            consumer_group=consumer_group,
            witness_id=archon_id,
            witness=witness,
        )
        await worker.run()
        return

    print(f"ERROR: Unknown VALIDATOR_ROLE '{role}'")
    sys.exit(1)


if __name__ == "__main__":
    asyncio.run(_run_from_env())
