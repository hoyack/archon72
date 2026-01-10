"""Halt Stream Publisher adapter (Story 3.3, Task 3).

Provides Redis Streams publisher for fast halt propagation.
This is the Redis channel of the dual-channel halt transport.

ADR-3: Partition Behavior + Halt Durability
- Redis Streams for speed (~1ms latency)
- Uses XADD to publish halt signals
- Stream name is configurable (default: 'halt:signals')

Constitutional Constraints:
- CT-11: Silent failure destroys legitimacy -> Publish failures MUST be logged
- CT-12: Witnessing creates accountability -> crisis_event_id links to trigger
- CT-13: Integrity outranks availability -> Redis channel complements DB

Message Fields (per story spec):
- reason: Human-readable halt reason
- crisis_event_id: UUID of triggering crisis event
- timestamp: ISO 8601 timestamp
- source_service: Service ID that triggered halt
"""

from datetime import datetime, timezone
from typing import Any, Protocol, runtime_checkable
from uuid import UUID

import structlog

# Default stream name for halt signals
DEFAULT_HALT_STREAM_NAME: str = "halt:signals"

log = structlog.get_logger(__name__)


@runtime_checkable
class RedisProtocol(Protocol):
    """Protocol for Redis client (allows mocking in tests)."""

    async def xadd(
        self,
        name: str,
        fields: dict[str, Any],
        id: str = "*",
        maxlen: int | None = None,
    ) -> str:
        """Add entry to a stream."""
        ...


class HaltStreamPublisher:
    """Redis Streams publisher for halt signals.

    Publishes halt signals to a Redis Stream for fast propagation
    across services. This is the "fast" channel of the dual-channel
    halt transport (ADR-3).

    Stream Schema (halt:signals):
    - reason: str - Human-readable halt reason
    - crisis_event_id: str - UUID of triggering crisis event
    - timestamp: str - ISO 8601 timestamp
    - source_service: str - Service ID that triggered halt

    Example:
        >>> publisher = HaltStreamPublisher(redis, stream_name="halt:signals")
        >>> message_id = await publisher.publish_halt(
        ...     reason="FR17: Fork detected",
        ...     crisis_event_id=crisis_uuid,
        ... )
    """

    def __init__(
        self,
        redis: RedisProtocol,
        stream_name: str = DEFAULT_HALT_STREAM_NAME,
        service_id: str = "archon72-api",
    ) -> None:
        """Initialize the halt stream publisher.

        Args:
            redis: Async Redis client (redis.asyncio.Redis compatible).
            stream_name: Name of the Redis Stream for halt signals.
            service_id: Identifier for this service instance.
        """
        self._redis = redis
        self._stream_name = stream_name
        self._service_id = service_id

    @property
    def stream_name(self) -> str:
        """Get the configured stream name."""
        return self._stream_name

    async def publish_halt(
        self,
        reason: str,
        crisis_event_id: UUID,
    ) -> str:
        """Publish halt signal to Redis Stream.

        Adds an entry to the halt signals stream with halt metadata.
        Returns the message ID assigned by Redis.

        Args:
            reason: Human-readable reason for halt (e.g., "FR17: Fork detected")
            crisis_event_id: UUID of the witnessed ConstitutionalCrisisEvent.

        Returns:
            The Redis message ID (e.g., "1704067200000-0").

        Raises:
            ConnectionError: If Redis is unavailable.
        """
        timestamp = datetime.now(timezone.utc).isoformat()

        message_fields = {
            "reason": reason,
            "crisis_event_id": str(crisis_event_id),
            "timestamp": timestamp,
            "source_service": self._service_id,
        }

        message_id = await self._redis.xadd(
            self._stream_name,
            message_fields,
        )

        log.info(
            "halt_signal_published",
            message_id=message_id,
            stream=self._stream_name,
            reason=reason,
            crisis_event_id=str(crisis_event_id),
        )

        return message_id
