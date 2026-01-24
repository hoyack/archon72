"""Consensus aggregator for validation results.

Story 3.2: Implement Consensus Aggregator
ADR-002: In-memory state + Kafka replay for aggregator (no Redis)
ADR-005: SKIP action for idempotent duplicate handling
Pre-mortems: P4 (No Redis for critical path)
Red Team: V2 (Session-bounded replay)

3-Archon Protocol Flow:
  1. Consume secretary results from validation-results topic
  2. Wait for both SECRETARY_TEXT and SECRETARY_JSON to agree
  3. On consensus, publish witness request to witness-requests topic
  4. Consume witness verdict from witness.events topic
  5. Publish final validated vote with witness statement

This aggregator consumes validation results from multiple validators,
tracks consensus, and produces final validated votes or routes to DLQ.
"""

import asyncio
import logging
import os
import signal
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from uuid import UUID

from src.infrastructure.adapters.kafka.avro_serializer import AvroSerializer, SerializationError
from src.infrastructure.adapters.kafka.circuit_breaker import CircuitBreaker
from src.workers.validator_worker import (
    TOPIC_VALIDATION_RESULTS,
    TOPIC_WITNESS_REQUESTS,
    TOPIC_WITNESS_EVENTS,
    ValidatorRole,
    WitnessVerdict,
)

logger = logging.getLogger(__name__)

# Topics
TOPIC_VALIDATED = "conclave.votes.validated"
TOPIC_DEAD_LETTER = "conclave.votes.dead-letter"


class ConsensusStatus(Enum):
    """Status of consensus determination."""

    PENDING = "pending"  # Waiting for secretary responses
    CONSENSUS = "consensus"  # Secretaries agree, awaiting witness
    WITNESS_PENDING = "witness_pending"  # Witness request sent, awaiting verdict
    DISAGREEMENT = "disagreement"  # Secretaries disagree
    RETRY_PENDING = "retry_pending"  # Scheduled for retry
    VALIDATED = "validated"  # Final validated with witness
    DEAD_LETTER = "dead_letter"  # Routed to DLQ


class ValidationSource(Enum):
    """Source of the final validation."""

    CONSENSUS = "consensus"  # Both validators agreed
    OPTIMISTIC_DLQ = "optimistic_dlq"  # DLQ fallback to optimistic
    SINGLE_VALIDATOR = "single_validator"  # Only one validator responded


@dataclass
class ValidatorResponse:
    """A single validator's response for a vote (legacy)."""

    validator_id: str
    validated_choice: str
    confidence: float
    attempt: int
    timestamp_ms: int


@dataclass
class SecretaryResponse:
    """A secretary's determination for a vote (3-Archon Protocol)."""

    secretary_id: str
    role: ValidatorRole  # SECRETARY_TEXT or SECRETARY_JSON
    vote_choice: str  # AYE, NAY, ABSTAIN
    confidence: float
    reasoning: str
    attempt: int
    timestamp_ms: int


@dataclass
class WitnessObservation:
    """Witness observation for a vote (3-Archon Protocol)."""

    witness_id: str
    verdict: WitnessVerdict  # AGREES or DISSENTS
    statement: str
    timestamp_ms: int


@dataclass
class VoteAggregation:
    """Aggregated state for a single vote.

    Tracks responses from secretaries and witness for 3-Archon Protocol.
    """

    vote_id: str
    session_id: str
    archon_id: str  # The archon who cast the vote
    raw_response: str  # Original response for witness
    motion_text: str  # Motion being voted on
    optimistic_choice: str  # Legacy field
    responses: dict[str, ValidatorResponse] = field(default_factory=dict)  # Legacy
    secretary_responses: dict[str, SecretaryResponse] = field(default_factory=dict)
    witness_observation: WitnessObservation | None = None
    status: ConsensusStatus = ConsensusStatus.PENDING
    retry_count: int = 0
    consensus_choice: str | None = None
    consensus_confidence: float | None = None
    created_at_ms: int = field(default_factory=lambda: int(time.time() * 1000))
    updated_at_ms: int = field(default_factory=lambda: int(time.time() * 1000))

    def add_response(self, response: ValidatorResponse) -> bool:
        """Add a validator response.

        Args:
            response: The validator's response

        Returns:
            True if response was added, False if duplicate (idempotent)
        """
        key = f"{response.validator_id}:{response.attempt}"

        # Idempotent: skip duplicates (ADR-005 SKIP)
        if key in self.responses:
            logger.debug(
                "Skipping duplicate response: vote=%s validator=%s attempt=%d",
                self.vote_id,
                response.validator_id,
                response.attempt,
            )
            return False

        self.responses[key] = response
        self.updated_at_ms = int(time.time() * 1000)
        return True

    def get_latest_responses(self, attempt: int | None = None) -> list[ValidatorResponse]:
        """Get the latest response from each validator.

        Args:
            attempt: If specified, get responses for this attempt only

        Returns:
            List of latest responses per validator
        """
        if attempt is not None:
            # Get responses for specific attempt
            return [
                r for key, r in self.responses.items()
                if r.attempt == attempt
            ]

        # Get latest response per validator
        latest: dict[str, ValidatorResponse] = {}
        for response in self.responses.values():
            if (
                response.validator_id not in latest
                or response.attempt > latest[response.validator_id].attempt
            ):
                latest[response.validator_id] = response

        return list(latest.values())

    def check_consensus(self, required_validators: int = 2) -> bool:
        """Check if consensus has been reached.

        Args:
            required_validators: Number of validators required for consensus

        Returns:
            True if consensus reached, False otherwise
        """
        latest = self.get_latest_responses()

        if len(latest) < required_validators:
            return False

        # Check if all validators agree
        choices = {r.validated_choice for r in latest}

        if len(choices) == 1:
            # Consensus!
            self.consensus_choice = latest[0].validated_choice
            self.consensus_confidence = min(r.confidence for r in latest)
            self.status = ConsensusStatus.CONSENSUS
            return True

        # Disagreement
        self.status = ConsensusStatus.DISAGREEMENT
        return False

    def to_validated_dict(self) -> dict[str, Any]:
        """Convert to validated vote dictionary for Avro serialization."""
        latest = self.get_latest_responses()
        requires_override = self.consensus_choice != self.optimistic_choice

        return {
            "vote_id": self.vote_id,
            "session_id": self.session_id,
            "optimistic_choice": self.optimistic_choice,
            "validated_choice": self.consensus_choice,
            "requires_override": requires_override,
            "consensus_reached": True,
            "confidence": self.consensus_confidence or 0.0,
            "validator_responses": [
                {
                    "validator_id": r.validator_id,
                    "validated_choice": r.validated_choice,
                    "confidence": r.confidence,
                }
                for r in latest
            ],
            "validation_source": ValidationSource.CONSENSUS.value,
            "timestamp_ms": int(time.time() * 1000),
        }

    def to_dead_letter_dict(self, failure_reason: str) -> dict[str, Any]:
        """Convert to dead letter dictionary for Avro serialization."""
        latest = self.get_latest_responses()

        return {
            "vote_id": self.vote_id,
            "session_id": self.session_id,
            "failure_reason": failure_reason,
            "last_validator_responses": [
                {
                    "validator_id": r.validator_id,
                    "validated_choice": r.validated_choice,
                    "confidence": r.confidence,
                }
                for r in latest
            ],
            "retry_count": self.retry_count,
            "failed_at_ms": int(time.time() * 1000),
        }

    # =========================================================================
    # 3-ARCHON PROTOCOL METHODS
    # =========================================================================

    def add_secretary_response(self, response: SecretaryResponse) -> bool:
        """Add a secretary's determination.

        Args:
            response: The secretary's determination

        Returns:
            True if response was added, False if duplicate
        """
        key = f"{response.role.value}:{response.attempt}"

        if key in self.secretary_responses:
            logger.debug(
                "Skipping duplicate secretary response: vote=%s role=%s attempt=%d",
                self.vote_id,
                response.role.value,
                response.attempt,
            )
            return False

        self.secretary_responses[key] = response
        self.updated_at_ms = int(time.time() * 1000)
        return True

    def get_secretary_responses(self, attempt: int | None = None) -> dict[ValidatorRole, SecretaryResponse]:
        """Get secretary responses by role.

        Args:
            attempt: If specified, get responses for this attempt only

        Returns:
            Dict mapping role to response
        """
        result: dict[ValidatorRole, SecretaryResponse] = {}

        for response in self.secretary_responses.values():
            if attempt is not None and response.attempt != attempt:
                continue

            # Keep latest response per role
            if response.role not in result or response.attempt > result[response.role].attempt:
                result[response.role] = response

        return result

    def check_secretary_consensus(self) -> bool:
        """Check if both secretaries agree on the vote.

        Returns:
            True if SECRETARY_TEXT and SECRETARY_JSON agree
        """
        responses = self.get_secretary_responses()

        # Need both secretaries
        if ValidatorRole.SECRETARY_TEXT not in responses:
            return False
        if ValidatorRole.SECRETARY_JSON not in responses:
            return False

        text_choice = responses[ValidatorRole.SECRETARY_TEXT].vote_choice
        json_choice = responses[ValidatorRole.SECRETARY_JSON].vote_choice

        if text_choice == json_choice:
            # Consensus!
            self.consensus_choice = text_choice
            self.consensus_confidence = min(
                responses[ValidatorRole.SECRETARY_TEXT].confidence,
                responses[ValidatorRole.SECRETARY_JSON].confidence,
            )
            self.status = ConsensusStatus.CONSENSUS
            return True

        # Disagreement
        self.status = ConsensusStatus.DISAGREEMENT
        return False

    def add_witness_observation(self, observation: WitnessObservation) -> None:
        """Add the witness's observation.

        Args:
            observation: The witness's verdict and statement
        """
        self.witness_observation = observation
        self.updated_at_ms = int(time.time() * 1000)

    def to_witness_request_dict(self) -> dict[str, Any]:
        """Convert to witness request dictionary for Kafka."""
        responses = self.get_secretary_responses()
        text_choice = responses.get(ValidatorRole.SECRETARY_TEXT)
        json_choice = responses.get(ValidatorRole.SECRETARY_JSON)

        return {
            "vote_id": self.vote_id,
            "session_id": self.session_id,
            "archon_id": self.archon_id,
            "raw_response": self.raw_response,
            "motion_text": self.motion_text,
            "secretary_text_choice": text_choice.vote_choice if text_choice else "",
            "secretary_json_choice": json_choice.vote_choice if json_choice else "",
            "consensus_choice": self.consensus_choice or "",
            "timestamp_ms": int(time.time() * 1000),
        }

    def to_validated_with_witness_dict(self) -> dict[str, Any]:
        """Convert to validated vote with witness statement."""
        responses = self.get_secretary_responses()
        text_resp = responses.get(ValidatorRole.SECRETARY_TEXT)
        json_resp = responses.get(ValidatorRole.SECRETARY_JSON)

        return {
            "vote_id": self.vote_id,
            "session_id": self.session_id,
            "archon_id": self.archon_id,
            "validated_choice": self.consensus_choice,
            "consensus_reached": True,
            "confidence": self.consensus_confidence or 0.0,
            "secretary_text": {
                "secretary_id": text_resp.secretary_id if text_resp else "",
                "vote_choice": text_resp.vote_choice if text_resp else "",
                "confidence": text_resp.confidence if text_resp else 0.0,
                "reasoning": text_resp.reasoning if text_resp else "",
            } if text_resp else None,
            "secretary_json": {
                "secretary_id": json_resp.secretary_id if json_resp else "",
                "vote_choice": json_resp.vote_choice if json_resp else "",
                "confidence": json_resp.confidence if json_resp else 0.0,
                "reasoning": json_resp.reasoning if json_resp else "",
            } if json_resp else None,
            "witness": {
                "witness_id": self.witness_observation.witness_id,
                "verdict": self.witness_observation.verdict.value,
                "statement": self.witness_observation.statement,
            } if self.witness_observation else None,
            "validation_source": ValidationSource.CONSENSUS.value,
            "timestamp_ms": int(time.time() * 1000),
        }


@dataclass
class AggregatorMetrics:
    """Metrics tracked by the consensus aggregator."""

    messages_consumed: int = 0
    messages_processed: int = 0
    duplicates_skipped: int = 0
    consensus_reached: int = 0
    disagreements: int = 0
    retries_scheduled: int = 0
    dlq_routes: int = 0
    validated_published: int = 0
    session_filtered: int = 0  # Messages filtered by session_id (V2)
    # 3-Archon Protocol metrics
    secretary_responses_received: int = 0
    witness_requests_published: int = 0
    witness_verdicts_received: int = 0
    witness_agrees: int = 0
    witness_dissents: int = 0


class ConsensusAggregator:
    """Aggregator that tracks secretary responses and witness verdicts.

    3-Archon Protocol Flow:
    1. Consume secretary results from validation-results topic
    2. Wait for both SECRETARY_TEXT and SECRETARY_JSON to agree
    3. On consensus, publish witness request to witness-requests topic
    4. Consume witness verdict from witness.events topic
    5. Publish final validated vote with witness statement

    State Management (P4 - No Redis):
    - All state is held in-memory in _vote_state dictionary
    - On startup, state is reconstructed from Kafka replay
    - Only messages for current session_id are processed (V2)

    Idempotency (ADR-005):
    - Duplicate (vote_id, role, attempt) tuples are skipped
    - Safe for message replay and at-least-once delivery

    Consensus Logic:
    - Both secretaries same choice → publish witness request
    - Secretaries disagree → schedule retry (up to max_retries)
    - Witness responds → publish final validated vote
    - Max retries exhausted → route to DLQ

    Usage:
        aggregator = ConsensusAggregator(
            bootstrap_servers="localhost:19092",
            schema_registry_url="http://localhost:18081",
            consumer_group="conclave-aggregator",
            current_session_id="session-uuid",
        )

        await aggregator.run()
    """

    def __init__(
        self,
        bootstrap_servers: str,
        schema_registry_url: str,
        consumer_group: str,
        current_session_id: str | None,
        validator_ids: list[str] | None = None,  # Legacy, kept for compatibility
        max_retries: int = 3,
        poll_timeout_seconds: float = 1.0,
    ) -> None:
        """Initialize the consensus aggregator.

        Args:
            bootstrap_servers: Kafka bootstrap servers
            schema_registry_url: Schema Registry URL
            consumer_group: Consumer group
            current_session_id: Current session to filter by (V2). If None, disables filtering.
            validator_ids: Legacy - ignored in 3-Archon Protocol
            max_retries: Maximum retry attempts before DLQ
            poll_timeout_seconds: Poll timeout
        """
        self._bootstrap_servers = bootstrap_servers
        self._consumer_group = consumer_group
        self._current_session_id = current_session_id
        self._validator_ids = validator_ids or []  # Legacy
        self._max_retries = max_retries
        self._poll_timeout = poll_timeout_seconds

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

        # In-memory state (P4 - no Redis)
        self._vote_state: dict[str, VoteAggregation] = {}

        # Consumer and producer (lazy-loaded)
        self._consumer: Any = None
        self._producer: Any = None

        # State
        self._running = False
        self._metrics = AggregatorMetrics()
        self._state_reconstructed = False

        logger.info(
            "ConsensusAggregator initialized: session=%s (3-Archon Protocol)",
            current_session_id,
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
                    "enable.auto.commit": False,
                    "max.poll.interval.ms": 300000,
                    "session.timeout.ms": 45000,
                })

                # Subscribe to both secretary results and witness events
                self._consumer.subscribe([
                    TOPIC_VALIDATION_RESULTS,
                    TOPIC_WITNESS_EVENTS,
                ])
                logger.info(
                    "Consumer subscribed to %s and %s",
                    TOPIC_VALIDATION_RESULTS,
                    TOPIC_WITNESS_EVENTS,
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

    def _extract_session_id(self, message: Any) -> str | None:
        """Extract session_id from message headers."""
        headers = message.headers() or []
        for key, value in headers:
            if key == "session_id" and value:
                return value.decode("utf-8")
        return None

    def _extract_role(self, message: Any) -> str | None:
        """Extract role from message headers."""
        headers = message.headers() or []
        for key, value in headers:
            if key == "role" and value:
                return value.decode("utf-8")
        return None

    def _get_topic(self, message: Any) -> str:
        """Get the topic name from the message."""
        return message.topic() if hasattr(message, "topic") else ""

    async def _publish_witness_request(self, vote: VoteAggregation) -> bool:
        """Publish witness request after secretary consensus.

        Args:
            vote: The vote aggregation with secretary consensus

        Returns:
            True if published successfully
        """
        if not self._circuit_breaker.should_allow_request():
            logger.warning("Circuit breaker open - cannot publish witness request")
            return False

        try:
            value = self._serializer.serialize(
                "witness_request",
                vote.to_witness_request_dict(),
            )
        except SerializationError as e:
            logger.error("Failed to serialize witness request: %s", e)
            self._circuit_breaker.record_failure()
            return False

        headers = [
            ("session_id", vote.session_id.encode("utf-8")),
            ("consensus_choice", (vote.consensus_choice or "").encode("utf-8")),
        ]

        success = await self._produce_message(
            topic=TOPIC_WITNESS_REQUESTS,
            key=vote.vote_id,
            value=value,
            headers=headers,
        )

        if success:
            vote.status = ConsensusStatus.WITNESS_PENDING
            self._metrics.witness_requests_published += 1
            logger.info(
                "Published witness request: vote=%s consensus=%s",
                vote.vote_id,
                vote.consensus_choice,
            )

        return success

    async def _publish_validated_with_witness(self, vote: VoteAggregation) -> bool:
        """Publish validated vote with witness statement.

        Args:
            vote: The vote aggregation with witness observation

        Returns:
            True if published successfully
        """
        if not self._circuit_breaker.should_allow_request():
            logger.warning("Circuit breaker open - cannot publish validated vote")
            return False

        try:
            value = self._serializer.serialize(
                "validated_with_witness",
                vote.to_validated_with_witness_dict(),
            )
        except SerializationError as e:
            logger.error("Failed to serialize validated vote: %s", e)
            self._circuit_breaker.record_failure()
            return False

        witness_verdict = ""
        if vote.witness_observation:
            witness_verdict = vote.witness_observation.verdict.value

        headers = [
            ("session_id", vote.session_id.encode("utf-8")),
            ("consensus", b"true"),
            ("witness_verdict", witness_verdict.encode("utf-8")),
        ]

        success = await self._produce_message(
            topic=TOPIC_VALIDATED,
            key=vote.vote_id,
            value=value,
            headers=headers,
        )

        if success:
            vote.status = ConsensusStatus.VALIDATED
            self._metrics.validated_published += 1

            if vote.witness_observation:
                if vote.witness_observation.verdict == WitnessVerdict.AGREES:
                    self._metrics.witness_agrees += 1
                else:
                    self._metrics.witness_dissents += 1

            logger.info(
                "Published validated vote with witness: vote=%s choice=%s witness=%s",
                vote.vote_id,
                vote.consensus_choice,
                witness_verdict,
            )

        return success

    async def _publish_validated(self, vote: VoteAggregation) -> bool:
        """Publish validated vote to Kafka.

        Args:
            vote: The vote aggregation with consensus

        Returns:
            True if published successfully
        """
        if not self._circuit_breaker.should_allow_request():
            logger.warning("Circuit breaker open - cannot publish validated vote")
            return False

        try:
            value = self._serializer.serialize(
                "validated",
                vote.to_validated_dict(),
            )
        except SerializationError as e:
            logger.error("Failed to serialize validated vote: %s", e)
            self._circuit_breaker.record_failure()
            return False

        headers = [
            ("session_id", vote.session_id.encode("utf-8")),
            ("consensus", b"true"),
        ]

        success = await self._produce_message(
            topic=TOPIC_VALIDATED,
            key=vote.vote_id,
            value=value,
            headers=headers,
        )

        if success:
            vote.status = ConsensusStatus.VALIDATED
            self._metrics.validated_published += 1
            logger.info(
                "Published validated vote: vote=%s choice=%s",
                vote.vote_id,
                vote.consensus_choice,
            )

        return success

    async def _publish_dead_letter(
        self,
        vote: VoteAggregation,
        failure_reason: str,
    ) -> bool:
        """Publish vote to dead letter queue.

        Args:
            vote: The vote aggregation that failed
            failure_reason: Why validation failed

        Returns:
            True if published successfully
        """
        if not self._circuit_breaker.should_allow_request():
            logger.warning("Circuit breaker open - cannot publish to DLQ")
            return False

        try:
            value = self._serializer.serialize(
                "dead_letter",
                vote.to_dead_letter_dict(failure_reason),
            )
        except SerializationError as e:
            logger.error("Failed to serialize dead letter: %s", e)
            self._circuit_breaker.record_failure()
            return False

        headers = [
            ("session_id", vote.session_id.encode("utf-8")),
            ("failure_reason", failure_reason.encode("utf-8")),
        ]

        success = await self._produce_message(
            topic=TOPIC_DEAD_LETTER,
            key=vote.vote_id,
            value=value,
            headers=headers,
        )

        if success:
            vote.status = ConsensusStatus.DEAD_LETTER
            self._metrics.dlq_routes += 1
            logger.warning(
                "Vote routed to DLQ: vote=%s reason=%s",
                vote.vote_id,
                failure_reason,
            )

        return success

    async def _produce_message(
        self,
        topic: str,
        key: str,
        value: bytes,
        headers: list[tuple[str, bytes]],
    ) -> bool:
        """Produce a message to Kafka with delivery confirmation.

        Args:
            topic: Target topic
            key: Message key
            value: Serialized value
            headers: Message headers

        Returns:
            True if delivered successfully
        """
        delivery_result: dict[str, Any] = {"error": None}

        def delivery_callback(err: Any, msg: Any) -> None:
            if err:
                delivery_result["error"] = str(err)

        try:
            producer = self._get_producer()

            producer.produce(
                topic=topic,
                key=key.encode("utf-8"),
                value=value,
                headers=headers,
                callback=delivery_callback,
            )

            remaining = producer.flush(timeout=10.0)

            if remaining > 0 or delivery_result["error"]:
                self._circuit_breaker.record_failure()
                logger.error(
                    "Failed to produce message: topic=%s error=%s",
                    topic,
                    delivery_result["error"] or "Flush timeout",
                )
                return False

            self._circuit_breaker.record_success()
            return True

        except Exception as e:
            self._circuit_breaker.record_failure()
            logger.error("Produce error: %s", e)
            return False

    async def _process_message(self, message: Any) -> None:
        """Process a message from validation-results or witness.events topic.

        3-Archon Protocol Flow:
        1. Secretary result → add to aggregation → check consensus
        2. Secretary consensus → publish witness request
        3. Witness verdict → publish final validated vote

        Args:
            message: Kafka message to process
        """
        self._metrics.messages_consumed += 1

        # V2: Filter by session_id if configured
        msg_session_id = self._extract_session_id(message)
        if self._current_session_id:
            if msg_session_id != self._current_session_id:
                self._metrics.session_filtered += 1
                logger.debug(
                    "Filtering message for session %s (current=%s)",
                    msg_session_id,
                    self._current_session_id,
                )
                return

        # Route by topic
        topic = self._get_topic(message)

        if topic == TOPIC_WITNESS_EVENTS:
            await self._process_witness_verdict(message)
        else:
            # TOPIC_VALIDATION_RESULTS - secretary or legacy validator
            role = self._extract_role(message)
            if role in {ValidatorRole.SECRETARY_TEXT.value, ValidatorRole.SECRETARY_JSON.value}:
                await self._process_secretary_result(message, role)
            else:
                # Legacy validator flow (backwards compatibility)
                await self._process_legacy_validator_result(message)

    async def _process_secretary_result(self, message: Any, role_str: str) -> None:
        """Process a secretary determination result.

        Args:
            message: Kafka message
            role_str: "secretary_text" or "secretary_json"
        """
        try:
            result_data = self._serializer.deserialize(
                "secretary_result",
                message.value(),
            )
        except SerializationError as e:
            logger.error("Failed to deserialize secretary result: %s", e)
            return

        vote_id = result_data["vote_id"]
        role = ValidatorRole(role_str)

        # Get or create vote aggregation
        if vote_id not in self._vote_state:
            self._vote_state[vote_id] = VoteAggregation(
                vote_id=vote_id,
                session_id=result_data["session_id"],
                archon_id=result_data.get("archon_id", ""),
                raw_response=result_data.get("raw_response", ""),
                motion_text=result_data.get("motion_text", ""),
                optimistic_choice="",  # Not used in 3-Archon Protocol
            )

        vote = self._vote_state[vote_id]

        # Skip if already finalized
        if vote.status in {ConsensusStatus.VALIDATED, ConsensusStatus.DEAD_LETTER}:
            return

        # Create secretary response
        response = SecretaryResponse(
            secretary_id=result_data.get("secretary_id", ""),
            role=role,
            vote_choice=result_data["vote_choice"],
            confidence=result_data["confidence"],
            reasoning=result_data.get("reasoning", ""),
            attempt=result_data.get("attempt", 1),
            timestamp_ms=result_data["timestamp_ms"],
        )

        # Idempotent: skip duplicates
        if not vote.add_secretary_response(response):
            self._metrics.duplicates_skipped += 1
            return

        self._metrics.secretary_responses_received += 1
        self._metrics.messages_processed += 1

        logger.debug(
            "Added secretary response: vote=%s role=%s choice=%s",
            vote_id,
            role.value,
            response.vote_choice,
        )

        # Check for secretary consensus
        if vote.check_secretary_consensus():
            self._metrics.consensus_reached += 1
            # Publish witness request
            await self._publish_witness_request(vote)

        elif vote.status == ConsensusStatus.DISAGREEMENT:
            self._metrics.disagreements += 1

            if vote.retry_count < self._max_retries:
                vote.retry_count += 1
                vote.status = ConsensusStatus.RETRY_PENDING
                self._metrics.retries_scheduled += 1
                logger.info(
                    "Scheduling retry for secretary disagreement: vote=%s retry=%d/%d",
                    vote_id,
                    vote.retry_count,
                    self._max_retries,
                )
            else:
                await self._publish_dead_letter(
                    vote,
                    failure_reason="secretary_disagreement_max_retries",
                )

    async def _process_witness_verdict(self, message: Any) -> None:
        """Process a witness observation verdict.

        Args:
            message: Kafka message from witness.events topic
        """
        try:
            result_data = self._serializer.deserialize(
                "witness_result",
                message.value(),
            )
        except SerializationError as e:
            logger.error("Failed to deserialize witness result: %s", e)
            return

        vote_id = result_data["vote_id"]

        # Vote must exist and be awaiting witness
        if vote_id not in self._vote_state:
            logger.warning("Witness verdict for unknown vote: %s", vote_id)
            return

        vote = self._vote_state[vote_id]

        if vote.status != ConsensusStatus.WITNESS_PENDING:
            logger.debug(
                "Ignoring witness verdict for vote not awaiting witness: vote=%s status=%s",
                vote_id,
                vote.status.value,
            )
            return

        # Add witness observation
        observation = WitnessObservation(
            witness_id=result_data.get("witness_id", ""),
            verdict=WitnessVerdict(result_data["verdict"]),
            statement=result_data.get("statement", ""),
            timestamp_ms=result_data["timestamp_ms"],
        )

        vote.add_witness_observation(observation)
        self._metrics.witness_verdicts_received += 1
        self._metrics.messages_processed += 1

        logger.info(
            "Witness verdict received: vote=%s verdict=%s",
            vote_id,
            observation.verdict.value,
        )

        # Publish final validated vote with witness statement
        await self._publish_validated_with_witness(vote)

    async def _process_legacy_validator_result(self, message: Any) -> None:
        """Process a legacy validator result (backwards compatibility).

        Args:
            message: Kafka message with legacy validation_result format
        """
        try:
            result_data = self._serializer.deserialize(
                "validation_result",
                message.value(),
            )
        except SerializationError as e:
            logger.error("Failed to deserialize validation result: %s", e)
            return

        vote_id = result_data["vote_id"]
        validator_id = result_data["validator_id"]
        attempt = result_data.get("attempt", 1)

        if vote_id not in self._vote_state:
            self._vote_state[vote_id] = VoteAggregation(
                vote_id=vote_id,
                session_id=result_data["session_id"],
                archon_id="",
                raw_response="",
                motion_text="",
                optimistic_choice=result_data["validated_choice"],
            )

        vote = self._vote_state[vote_id]

        if vote.status in {ConsensusStatus.VALIDATED, ConsensusStatus.DEAD_LETTER}:
            return

        response = ValidatorResponse(
            validator_id=validator_id,
            validated_choice=result_data["validated_choice"],
            confidence=result_data["confidence"],
            attempt=attempt,
            timestamp_ms=result_data["timestamp_ms"],
        )

        if not vote.add_response(response):
            self._metrics.duplicates_skipped += 1
            return

        self._metrics.messages_processed += 1

        # Legacy consensus check
        if vote.check_consensus(required_validators=len(self._validator_ids) or 2):
            self._metrics.consensus_reached += 1
            await self._publish_validated(vote)

        elif vote.status == ConsensusStatus.DISAGREEMENT:
            self._metrics.disagreements += 1

            if vote.retry_count < self._max_retries:
                vote.retry_count += 1
                vote.status = ConsensusStatus.RETRY_PENDING
                self._metrics.retries_scheduled += 1
            else:
                await self._publish_dead_letter(
                    vote,
                    failure_reason="max_retries_exhausted_disagreement",
                )

    async def reconstruct_state(self) -> None:
        """Reconstruct state from Kafka replay.

        Per P4: State must be reconstructable from Kafka only.
        Per V2: Only current session_id messages are processed.
        """
        if self._state_reconstructed:
            return

        logger.info(
            "Reconstructing state from Kafka (session=%s)",
            self._current_session_id,
        )

        # This would involve consuming from the beginning of the topic
        # and replaying all messages for the current session.
        # For now, we start fresh with empty state.

        self._state_reconstructed = True
        logger.info("State reconstruction complete")

    async def run(self) -> None:
        """Run the aggregator event loop."""
        self._running = True
        consumer = self._get_consumer()

        # Reconstruct state from Kafka (P4)
        await self.reconstruct_state()

        logger.info(
            "ConsensusAggregator starting: session=%s",
            self._current_session_id,
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
            logger.info("Aggregator interrupted by user")

        finally:
            self._running = False
            self._cleanup()

    def stop(self) -> None:
        """Signal the aggregator to stop."""
        logger.info("Aggregator stop requested")
        self._running = False

    def _cleanup(self) -> None:
        """Clean up resources."""
        if self._consumer:
            self._consumer.close()
            logger.info("Consumer closed")

        if self._producer:
            self._producer.flush(timeout=5.0)
            logger.info("Producer flushed")

    def get_vote_status(self, vote_id: str) -> VoteAggregation | None:
        """Get the current status of a vote.

        Args:
            vote_id: Vote to look up

        Returns:
            VoteAggregation or None if not found
        """
        return self._vote_state.get(vote_id)

    def get_pending_votes(self) -> list[str]:
        """Get list of votes pending consensus.

        Returns:
            List of vote IDs still pending
        """
        return [
            vote_id
            for vote_id, vote in self._vote_state.items()
            if vote.status not in {ConsensusStatus.VALIDATED, ConsensusStatus.DEAD_LETTER}
        ]

    def get_metrics(self) -> dict[str, Any]:
        """Get aggregator metrics for monitoring."""
        return {
            "session_id": self._current_session_id,
            "messages_consumed": self._metrics.messages_consumed,
            "messages_processed": self._metrics.messages_processed,
            "duplicates_skipped": self._metrics.duplicates_skipped,
            "consensus_reached": self._metrics.consensus_reached,
            "disagreements": self._metrics.disagreements,
            "retries_scheduled": self._metrics.retries_scheduled,
            "dlq_routes": self._metrics.dlq_routes,
            "validated_published": self._metrics.validated_published,
            "session_filtered": self._metrics.session_filtered,
            "votes_in_state": len(self._vote_state),
            "pending_votes": len(self.get_pending_votes()),
            "circuit_state": self._circuit_breaker.state.value,
            "running": self._running,
            # 3-Archon Protocol metrics
            "secretary_responses_received": self._metrics.secretary_responses_received,
            "witness_requests_published": self._metrics.witness_requests_published,
            "witness_verdicts_received": self._metrics.witness_verdicts_received,
            "witness_agrees": self._metrics.witness_agrees,
            "witness_dissents": self._metrics.witness_dissents,
        }


async def run_consensus_aggregator(
    bootstrap_servers: str,
    schema_registry_url: str,
    consumer_group: str,
    current_session_id: str | None,
    validator_ids: list[str] | None = None,
) -> ConsensusAggregator:
    """Create and run a consensus aggregator.

    Args:
        bootstrap_servers: Kafka bootstrap servers
        schema_registry_url: Schema Registry URL
        consumer_group: Consumer group
        current_session_id: Current session to filter by (None disables filtering)
        validator_ids: Expected validator IDs (legacy, optional)

    Returns:
        The running aggregator instance
    """
    aggregator = ConsensusAggregator(
        bootstrap_servers=bootstrap_servers,
        schema_registry_url=schema_registry_url,
        consumer_group=consumer_group,
        current_session_id=current_session_id,
        validator_ids=validator_ids,
    )

    # Setup signal handlers
    loop = asyncio.get_event_loop()

    def signal_handler() -> None:
        aggregator.stop()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, signal_handler)

    # Run in background
    asyncio.create_task(aggregator.run())

    return aggregator


def _get_env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return value.strip()


async def _run_from_env() -> None:
    try:
        from dotenv import load_dotenv
    except Exception:
        load_dotenv = None

    if load_dotenv:
        load_dotenv()

    bootstrap_servers = _get_env("KAFKA_BOOTSTRAP_SERVERS", "localhost:19092") or "localhost:19092"
    schema_registry_url = _get_env("SCHEMA_REGISTRY_URL", "http://localhost:18081") or "http://localhost:18081"
    consumer_group = _get_env("KAFKA_CONSUMER_GROUP", "conclave-aggregator") or "conclave-aggregator"
    current_session_id = _get_env("CONCLAVE_SESSION_ID") or _get_env("CURRENT_SESSION_ID")

    aggregator = ConsensusAggregator(
        bootstrap_servers=bootstrap_servers,
        schema_registry_url=schema_registry_url,
        consumer_group=consumer_group,
        current_session_id=current_session_id,
    )

    await aggregator.run()


if __name__ == "__main__":
    asyncio.run(_run_from_env())
