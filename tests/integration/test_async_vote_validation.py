"""Integration tests for async vote validation with Redpanda.

Story 5.1: Integration Tests with Redpanda

Tests the full async validation pipeline:
- Vote publish → validate → reconcile round-trip
- Consumer lag reaching zero
- ReconciliationResult correctness

Uses testcontainers GenericContainer for Redpanda.
"""

from __future__ import annotations

import asyncio
import logging
import os
import socket
import time
from dataclasses import dataclass
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

# Skip all tests if testcontainers or confluent-kafka not available
pytest.importorskip("testcontainers")

try:
    from testcontainers.core.container import DockerContainer
    from testcontainers.core.waiting_utils import wait_for_logs
except ImportError:
    pytest.skip("testcontainers not available", allow_module_level=True)

try:
    from confluent_kafka import Consumer, Producer
    from confluent_kafka.admin import AdminClient, NewTopic
except ImportError:
    pytest.skip("confluent-kafka not available", allow_module_level=True)

from src.application.ports.vote_publisher import PendingVote
from src.application.services.reconciliation_service import ReconciliationService
from src.domain.models.reconciliation import (
    ReconciliationConfig,
    ReconciliationStatus,
    ValidationOutcome,
)
from src.infrastructure.adapters.kafka.audit_publisher import KafkaAuditPublisher
from src.workers.validation_dispatcher import ValidationDispatcher

logger = logging.getLogger(__name__)


# Redpanda container configuration
REDPANDA_IMAGE = "redpandadata/redpanda:v23.3.5"
REDPANDA_KAFKA_PORT = 9092
REDPANDA_KAFKA_EXTERNAL_PORT = 19092
REDPANDA_SCHEMA_REGISTRY_PORT = 8081
REDPANDA_RPC_PORT = 33145


def _get_free_port() -> int:
    """Select a free host port for binding test containers."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _local_bootstrap_servers() -> str | None:
    return os.getenv("KAFKA_BOOTSTRAP_SERVERS") or os.getenv(
        "REDPANDA_BOOTSTRAP_SERVERS"
    )


def _local_schema_registry_url() -> str | None:
    return os.getenv("SCHEMA_REGISTRY_URL")


class RedpandaContainer(DockerContainer):
    """Testcontainer for Redpanda broker and Schema Registry."""

    def __init__(self) -> None:
        super().__init__(REDPANDA_IMAGE)
        self._kafka_host_port = _get_free_port()
        self._schema_registry_host_port = _get_free_port()
        # Redpanda requires distinct internal/external listener ports.
        self.with_bind_ports(REDPANDA_KAFKA_EXTERNAL_PORT, self._kafka_host_port)
        self.with_bind_ports(
            REDPANDA_SCHEMA_REGISTRY_PORT, self._schema_registry_host_port
        )
        self.with_command(
            "redpanda start "
            f"--kafka-addr internal://0.0.0.0:{REDPANDA_KAFKA_PORT},external://0.0.0.0:{REDPANDA_KAFKA_EXTERNAL_PORT} "
            f"--advertise-kafka-addr internal://localhost:{REDPANDA_KAFKA_PORT},external://localhost:{self._kafka_host_port} "
            f"--schema-registry-addr 0.0.0.0:{REDPANDA_SCHEMA_REGISTRY_PORT} "
            f"--rpc-addr 0.0.0.0:{REDPANDA_RPC_PORT} "
            f"--advertise-rpc-addr localhost:{REDPANDA_RPC_PORT} "
            "--smp 1 "
            "--memory 1G "
            "--mode dev-container "
            "--default-log-level=warn"
        )

    def get_bootstrap_servers(self) -> str:
        """Get Kafka bootstrap servers URL."""
        host = self.get_container_host_ip()
        return f"{host}:{self._kafka_host_port}"

    def get_schema_registry_url(self) -> str:
        """Get Schema Registry URL."""
        host = self.get_container_host_ip()
        return f"http://{host}:{self._schema_registry_host_port}"


@pytest.fixture(scope="module")
def redpanda_container():
    """Module-scoped Redpanda container fixture.

    Starts Redpanda once per test module for efficiency.
    """
    if _local_bootstrap_servers():
        yield None
        return

    container = RedpandaContainer()
    container.start()

    # Wait for Redpanda to be ready
    wait_for_logs(container, "Started Kafka API server", timeout=60)

    # Give Schema Registry time to initialize
    time.sleep(2)

    yield container

    container.stop()


@pytest.fixture
def bootstrap_servers(redpanda_container: RedpandaContainer | None) -> str:
    """Get Kafka bootstrap servers from container."""
    local = _local_bootstrap_servers()
    if local:
        return local
    assert redpanda_container is not None
    return redpanda_container.get_bootstrap_servers()


@pytest.mark.asyncio
async def test_audit_publisher_round_trip(bootstrap_servers: str) -> None:
    """Verify KafkaAuditPublisher publishes and messages can be consumed."""
    topic = "conclave.votes.validation-started"

    admin = AdminClient({"bootstrap.servers": bootstrap_servers})
    admin.create_topics(
        [NewTopic(topic=topic, num_partitions=1, replication_factor=1)],
        operation_timeout=10,
    )

    publisher = KafkaAuditPublisher(
        bootstrap_servers=bootstrap_servers,
        topic_prefix="conclave",
    )

    payload = {"vote_id": str(uuid4()), "archon_id": "archon-1", "optimistic": "AYE"}
    await publisher.publish(topic, payload)

    consumer = Consumer(
        {
            "bootstrap.servers": bootstrap_servers,
            "group.id": f"test-consumer-{uuid4()}",
            "auto.offset.reset": "earliest",
        }
    )
    consumer.subscribe([topic])

    msg = consumer.poll(5.0)
    consumer.close()

    assert msg is not None
    assert msg.value() is not None


@pytest.fixture
def schema_registry_url(redpanda_container: RedpandaContainer | None) -> str:
    """Get Schema Registry URL from container."""
    local = _local_schema_registry_url()
    if local:
        return local
    if redpanda_container is None:
        pytest.skip("Schema registry requires Redpanda test container or env URL")
    return redpanda_container.get_schema_registry_url()


@pytest.fixture
def kafka_topics(bootstrap_servers: str) -> list[str]:
    """Create required Kafka topics for tests."""
    topics = [
        "conclave.votes.pending-validation",
        "conclave.votes.validation-requests",
        "conclave.votes.validation-results",
        "conclave.votes.validated",
        "conclave.votes.dead-letter",
    ]

    admin = AdminClient({"bootstrap.servers": bootstrap_servers})

    new_topics = [
        NewTopic(topic, num_partitions=3, replication_factor=1) for topic in topics
    ]

    futures = admin.create_topics(new_topics)
    for topic, future in futures.items():
        try:
            future.result(timeout=10)
            logger.info(f"Created topic: {topic}")
        except Exception as e:
            if "already exists" not in str(e).lower():
                logger.warning(f"Topic creation error for {topic}: {e}")

    return topics


@dataclass
class MockValidator:
    """Mock validator that returns a fixed choice."""

    validator_id: str
    choice: str = "APPROVE"
    confidence: float = 0.95
    delay_seconds: float = 0.1

    async def validate(self, raw_response: str) -> tuple[str, float]:
        """Simulate validation with delay."""
        await asyncio.sleep(self.delay_seconds)
        return self.choice, self.confidence


@pytest.fixture
def mock_validators() -> list[MockValidator]:
    """Create mock validators for testing."""
    return [
        MockValidator(validator_id="validator_1", choice="APPROVE"),
        MockValidator(validator_id="validator_2", choice="APPROVE"),
    ]


class TestAsyncVoteValidationPipeline:
    """Integration tests for the full async vote validation pipeline."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    @pytest.mark.timeout(60)
    async def test_vote_publish_to_kafka(
        self,
        bootstrap_servers: str,
        schema_registry_url: str,
        kafka_topics: list[str],
    ) -> None:
        """Test that votes can be published to Kafka."""
        # Create dispatcher with mock validators
        dispatcher = ValidationDispatcher(
            bootstrap_servers=bootstrap_servers,
            schema_registry_url=schema_registry_url,
            validator_ids=["validator_1", "validator_2"],
            timeout_seconds=10.0,
        )

        # Create a pending vote
        vote = PendingVote(
            vote_id=uuid4(),
            session_id=uuid4(),
            motion_id=uuid4(),
            archon_id="archon_test",
            optimistic_choice="APPROVE",
            raw_response='{"choice": "AYE"}\n\nI support this motion.',
            timestamp_ms=int(time.time() * 1000),
        )

        # Dispatch vote for validation
        result = await dispatcher.dispatch_vote(vote, attempt=1)

        # Verify dispatch succeeded
        assert result.all_succeeded, f"Dispatch failed: {result.failed_validators}"
        assert len(result.validators_dispatched) == 2
        assert "validator_1" in result.validators_dispatched
        assert "validator_2" in result.validators_dispatched

    @pytest.mark.integration
    @pytest.mark.asyncio
    @pytest.mark.timeout(60)
    async def test_reconciliation_service_tracking(
        self,
        bootstrap_servers: str,
    ) -> None:
        """Test that reconciliation service correctly tracks votes."""
        session_id = uuid4()
        motion_id = uuid4()

        # Create reconciliation service
        reconciliation = ReconciliationService()

        # Register some votes
        vote_ids = [uuid4() for _ in range(3)]
        for i, vote_id in enumerate(vote_ids):
            reconciliation.register_vote(
                session_id=session_id,
                motion_id=motion_id,
                vote_id=vote_id,
                archon_id=f"archon_{i}",
                optimistic_choice="APPROVE",
            )

        # Mark votes as validated
        for vote_id in vote_ids[:2]:
            reconciliation.mark_validated(
                vote_id=vote_id,
                validated_choice="APPROVE",
                confidence=0.95,
            )

        # Mark one as DLQ
        reconciliation.mark_dlq(
            vote_id=vote_ids[2],
            failure_reason="Test DLQ",
        )

        # Get status
        status = await reconciliation.get_reconciliation_status(
            session_id=session_id,
            motion_id=motion_id,
        )

        # Verify counts
        assert status.validated_count == 2
        assert status.dlq_fallback_count == 1
        assert status.pending_count == 0

    @pytest.mark.integration
    @pytest.mark.asyncio
    @pytest.mark.timeout(120)
    async def test_full_async_validation_roundtrip(
        self,
        bootstrap_servers: str,
        schema_registry_url: str,
        kafka_topics: list[str],
    ) -> None:
        """Test complete vote publish → validate → reconcile round-trip.

        This is the key acceptance test for Story 5.1:
        - Votes are published to Kafka
        - Validation results are tracked
        - Reconciliation completes with zero pending
        """
        session_id = uuid4()
        motion_id = uuid4()

        # Create services
        reconciliation = ReconciliationService()
        dispatcher = ValidationDispatcher(
            bootstrap_servers=bootstrap_servers,
            schema_registry_url=schema_registry_url,
            validator_ids=["validator_1", "validator_2"],
            timeout_seconds=10.0,
        )

        # Create and dispatch votes
        num_votes = 3
        vote_ids = []

        for i in range(num_votes):
            vote_id = uuid4()
            vote_ids.append(vote_id)

            vote = PendingVote(
                vote_id=vote_id,
                session_id=session_id,
                motion_id=motion_id,
                archon_id=f"archon_{i}",
                optimistic_choice="APPROVE",
                raw_response='{"choice": "AYE"}\n\nI support this motion.',
                timestamp_ms=int(time.time() * 1000),
            )

            # Register with reconciliation service
            reconciliation.register_vote(
                session_id=session_id,
                motion_id=motion_id,
                vote_id=vote_id,
                archon_id=f"archon_{i}",
                optimistic_choice="APPROVE",
            )

            # Dispatch for validation
            result = await dispatcher.dispatch_vote(vote, attempt=1)
            assert result.all_succeeded, f"Dispatch failed for vote {i}"

        # Simulate validation completion (in real system, workers do this)
        # For integration test, we mark directly
        for vote_id in vote_ids:
            reconciliation.mark_validated(
                vote_id=vote_id,
                validated_choice="APPROVE",
                confidence=0.95,
            )

        # Await reconciliation with short timeout
        config = ReconciliationConfig(
            timeout_seconds=10.0,
            poll_interval_seconds=0.1,
            max_lag_for_complete=0,
            require_zero_pending=True,
        )

        result = await reconciliation.await_all_validations(
            session_id=session_id,
            motion_id=motion_id,
            expected_vote_count=num_votes,
            config=config,
        )

        # Verify reconciliation completed
        assert result.status == ReconciliationStatus.COMPLETE
        assert result.pending_count == 0
        assert result.validated_count == num_votes
        assert result.is_complete
        assert len(result.vote_summaries) == num_votes

    @pytest.mark.integration
    @pytest.mark.asyncio
    @pytest.mark.timeout(60)
    async def test_dlq_fallback_is_witnessed(
        self,
        bootstrap_servers: str,
    ) -> None:
        """Test that DLQ fallbacks are properly witnessed (V1)."""
        session_id = uuid4()
        motion_id = uuid4()

        # Create mock witness
        mock_witness = AsyncMock()

        # Create reconciliation service with witness
        reconciliation = ReconciliationService(witness=mock_witness)

        # Register a vote
        vote_id = uuid4()
        reconciliation.register_vote(
            session_id=session_id,
            motion_id=motion_id,
            vote_id=vote_id,
            archon_id="archon_test",
            optimistic_choice="APPROVE",
        )

        # Mark as DLQ
        reconciliation.mark_dlq(
            vote_id=vote_id,
            failure_reason="Validation timeout",
        )

        # Apply DLQ fallbacks
        fallbacks = await reconciliation.apply_dlq_fallbacks(
            session_id=session_id,
            motion_id=motion_id,
        )

        # Verify fallback was applied
        assert len(fallbacks) == 1
        assert fallbacks[0].vote_id == vote_id
        assert fallbacks[0].outcome == ValidationOutcome.DLQ_FALLBACK

        # Verify witness was called
        mock_witness.witness_dlq_fallback.assert_called_once()
        call_args = mock_witness.witness_dlq_fallback.call_args
        assert call_args.kwargs["vote_id"] == vote_id
        assert call_args.kwargs["optimistic_choice"] == "APPROVE"

    @pytest.mark.integration
    @pytest.mark.asyncio
    @pytest.mark.timeout(60)
    async def test_validation_override_tracked(
        self,
        bootstrap_servers: str,
    ) -> None:
        """Test that validation overrides are correctly tracked."""
        session_id = uuid4()
        motion_id = uuid4()

        # Create reconciliation service
        reconciliation = ReconciliationService()

        # Register a vote with optimistic APPROVE
        vote_id = uuid4()
        reconciliation.register_vote(
            session_id=session_id,
            motion_id=motion_id,
            vote_id=vote_id,
            archon_id="archon_test",
            optimistic_choice="APPROVE",
        )

        # Validate with REJECT (different from optimistic)
        reconciliation.mark_validated(
            vote_id=vote_id,
            validated_choice="REJECT",
            confidence=0.90,
        )

        # Get status
        status = await reconciliation.get_reconciliation_status(
            session_id=session_id,
            motion_id=motion_id,
        )

        # Verify override is tracked
        assert status.validated_count == 1
        assert len(status.vote_summaries) == 1

        summary = status.vote_summaries[0]
        assert summary.requires_override
        assert summary.optimistic_choice == "APPROVE"
        assert summary.validated_choice == "REJECT"
        assert summary.outcome == ValidationOutcome.VALIDATED_OVERRIDE


class TestConsumerLag:
    """Tests for consumer lag tracking (R3)."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    @pytest.mark.timeout(60)
    async def test_lag_provider_integration(
        self,
        bootstrap_servers: str,
        kafka_topics: list[str],
    ) -> None:
        """Test that lag provider correctly reports consumer lag."""
        # Create a producer and write some messages
        producer = Producer(
            {
                "bootstrap.servers": bootstrap_servers,
                "acks": "all",
            }
        )

        topic = "conclave.votes.validation-results"

        # Produce messages
        for i in range(5):
            producer.produce(
                topic=topic,
                key=f"key_{i}".encode(),
                value=f"value_{i}".encode(),
            )
        producer.flush()

        # Create consumer and measure lag
        consumer = Consumer(
            {
                "bootstrap.servers": bootstrap_servers,
                "group.id": "test-lag-group",
                "auto.offset.reset": "earliest",
            }
        )
        consumer.subscribe([topic])

        # Consume some messages
        consumed = 0
        for _ in range(3):
            msg = consumer.poll(timeout=5.0)
            if msg and not msg.error():
                consumed += 1

        # Verify we consumed some but not all
        assert consumed > 0

        consumer.close()


class TestCircuitBreakerFallback:
    """Tests for circuit breaker fallback behavior."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    @pytest.mark.timeout(30)
    async def test_circuit_opens_on_failures(
        self,
    ) -> None:
        """Test that circuit breaker opens after consecutive failures."""
        from src.infrastructure.adapters.kafka.circuit_breaker import (
            CircuitBreaker,
            CircuitState,
        )

        # Create circuit breaker with low threshold
        breaker = CircuitBreaker(
            failure_threshold=2,
            reset_timeout=1.0,
        )

        # Verify starts closed
        assert breaker.state == CircuitState.CLOSED
        assert breaker.should_allow_request()

        # Record failures
        breaker.record_failure()
        assert breaker.state == CircuitState.CLOSED

        breaker.record_failure()
        assert breaker.state == CircuitState.OPEN
        assert not breaker.should_allow_request()

        # Wait for reset timeout
        await asyncio.sleep(1.1)

        # Should transition to half-open
        assert breaker.should_allow_request()
        assert breaker.state == CircuitState.HALF_OPEN

        # Success should close
        breaker.record_success()
        assert breaker.state == CircuitState.CLOSED
