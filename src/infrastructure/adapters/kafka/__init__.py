"""Kafka infrastructure adapters for async vote validation.

ADR-001: Message Infrastructure (Kafka/Redpanda)
ADR-002: Aggregator State Storage (In-memory + Kafka replay)
ADR-003: Topic Design & Partitioning (Stage-per-topic)
"""

from src.infrastructure.adapters.kafka.avro_serializer import (
    AvroSerializer,
    SchemaRegistryError,
    SchemaRegistryUnavailableError,
    SerializationError,
)
from src.infrastructure.adapters.kafka.circuit_breaker import (
    CircuitBreaker,
    CircuitMetrics,
    CircuitState,
)
from src.infrastructure.adapters.kafka.kafka_health_checker import KafkaHealthChecker
from src.infrastructure.adapters.kafka.vote_publisher import (
    KafkaVotePublisher,
    TOPIC_DEAD_LETTER,
    TOPIC_PENDING_VALIDATION,
    TOPIC_VALIDATED,
    TOPIC_VALIDATION_RESULTS,
)
from src.infrastructure.adapters.kafka.startup_health_gate import (
    StartupHealthGate,
    StartupHealthReport,
    StartupHealthResult,
    create_startup_health_gate,
)

__all__ = [
    # Serialization
    "AvroSerializer",
    "SchemaRegistryError",
    "SchemaRegistryUnavailableError",
    "SerializationError",
    # Circuit Breaker
    "CircuitBreaker",
    "CircuitMetrics",
    "CircuitState",
    # Health Checking
    "KafkaHealthChecker",
    # Vote Publisher
    "KafkaVotePublisher",
    "TOPIC_DEAD_LETTER",
    "TOPIC_PENDING_VALIDATION",
    "TOPIC_VALIDATED",
    "TOPIC_VALIDATION_RESULTS",
    # Startup Health Gate
    "StartupHealthGate",
    "StartupHealthReport",
    "StartupHealthResult",
    "create_startup_health_gate",
]
