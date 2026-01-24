"""Port interface for Kafka health checking.

Story 2.2: Implement Kafka Health Checker
Pre-mortems: P3 (Schema Registry health), P7 (Worker presence check)
Red Team: R2 (Schema Registry required), R3 (Zero lag before adjourn)

This port defines the interface for checking Kafka cluster health
to determine if async validation should proceed or fall back to sync.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class KafkaHealthStatus:
    """Status of Kafka cluster health.

    Per P3: Schema Registry health must be verified before publishing.
    Per P7: Health check must verify consumer group has active members.
    Per R3: Consumer lag must be tracked for reconciliation gate.

    Attributes:
        broker_reachable: Can connect to Kafka bootstrap servers
        schema_registry_reachable: Can GET /subjects from Schema Registry
        consumer_group_active: Consumer group has >0 members
        consumer_lag: Total lag across all partitions (0 = caught up)
        error_message: Optional error details if unhealthy
    """

    broker_reachable: bool
    schema_registry_reachable: bool
    consumer_group_active: bool
    consumer_lag: int
    error_message: str | None = None

    @property
    def healthy(self) -> bool:
        """Check if Kafka is healthy enough for async validation.

        All three conditions must be true:
        - Broker reachable
        - Schema Registry reachable (P3)
        - Consumer group has active members (P7)

        Note: Consumer lag is NOT part of healthy check - it's checked
        separately at reconciliation time (R3).
        """
        return (
            self.broker_reachable
            and self.schema_registry_reachable
            and self.consumer_group_active
        )

    @property
    def should_fallback_to_sync(self) -> bool:
        """Determine if async validation should fall back to sync.

        Returns True if any critical component is unhealthy.
        """
        return not self.healthy

    @property
    def ready_for_adjourn(self) -> bool:
        """Check if ready for session adjournment (R3).

        In addition to being healthy, consumer lag must be zero
        for all pending validations to have been processed.
        """
        return self.healthy and self.consumer_lag == 0


class KafkaHealthProtocol(ABC):
    """Abstract protocol for Kafka health checking.

    Implementations check all Kafka dependencies:
    - Broker connectivity (can we reach Kafka?)
    - Schema Registry (can we serialize messages?)
    - Consumer group members (are workers running?)
    - Consumer lag (how far behind are we?)

    This information is used to:
    1. Decide async vs sync validation path
    2. Gate session adjournment (must have zero lag)
    3. Trigger circuit breaker on repeated failures
    """

    @abstractmethod
    async def check_health(self) -> KafkaHealthStatus:
        """Perform comprehensive health check.

        Checks:
        1. Broker connectivity via metadata request
        2. Schema Registry via GET /subjects
        3. Consumer group via admin client
        4. Consumer lag via admin client

        Returns:
            KafkaHealthStatus with all health indicators

        Note: This should be fast (<5s timeout) and not block
        the main application thread.
        """
        ...

    @abstractmethod
    async def get_consumer_lag(self, topic: str) -> int:
        """Get consumer lag for a specific topic.

        Used by reconciliation gate (R3) to verify all messages
        have been processed before session adjournment.

        Args:
            topic: Kafka topic name

        Returns:
            Total lag across all partitions (0 = caught up)
        """
        ...

    @abstractmethod
    async def is_consumer_group_active(self) -> bool:
        """Check if consumer group has active members.

        Per P7: Workers must be running for async validation.

        Returns:
            True if consumer group has at least one member
        """
        ...
