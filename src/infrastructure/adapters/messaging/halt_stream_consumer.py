"""Halt Stream Consumer adapter (Story 3.3, Task 4).

Provides Redis Streams consumer for checking halt state.
This is the Redis channel reader of the dual-channel halt transport.

ADR-3: Partition Behavior + Halt Durability
- Redis Streams for speed (~1ms latency)
- Consumer groups for reliable delivery
- Uses XREADGROUP with blocking read
- XACK for message acknowledgment

Constitutional Constraints:
- CT-11: Silent failure destroys legitimacy -> Consumer failures MUST be logged
- CT-13: Integrity outranks availability -> If halt detected, component halts

Message Fields (expected):
- reason: Human-readable halt reason
- crisis_event_id: UUID of triggering crisis event
- timestamp: ISO 8601 timestamp
- source_service: Service ID that triggered halt
"""

import asyncio
import contextlib
from typing import Any, Optional, Protocol, runtime_checkable

import structlog

from src.infrastructure.adapters.messaging.halt_stream_publisher import (
    DEFAULT_HALT_STREAM_NAME,
)

# Default consumer group name
DEFAULT_CONSUMER_GROUP: str = "halt:consumers"

log = structlog.get_logger(__name__)


@runtime_checkable
class RedisProtocol(Protocol):
    """Protocol for Redis client (allows mocking in tests)."""

    async def xlen(self, name: str) -> int:
        """Get stream length."""
        ...

    async def xgroup_create(
        self,
        name: str,
        groupname: str,
        id: str = "$",
        mkstream: bool = False,
    ) -> bool:
        """Create a consumer group."""
        ...

    async def xreadgroup(
        self,
        groupname: str,
        consumername: str,
        streams: dict[str, str],
        count: int | None = None,
        block: int | None = None,
    ) -> list[tuple[str, list[tuple[str, dict[str, str]]]]]:
        """Read from stream as consumer group member."""
        ...

    async def xack(
        self,
        name: str,
        groupname: str,
        *ids: str,
    ) -> int:
        """Acknowledge message processing."""
        ...


class HaltStreamConsumer:
    """Redis Streams consumer for halt signals.

    Consumes halt signals from a Redis Stream to detect system halts.
    This is the "fast" channel reader of the dual-channel halt transport.

    Uses consumer groups for reliable delivery:
    - Consumer group: halt:consumers (default)
    - Each service instance has unique consumer name
    - Messages are acknowledged after processing
    - Unacknowledged messages can be claimed by other consumers

    Example:
        >>> consumer = HaltStreamConsumer(redis, consumer_name="api-1")
        >>> if await consumer.check_redis_halt():
        ...     raise SystemHaltedError("System halted via Redis")
    """

    def __init__(
        self,
        redis: RedisProtocol,
        stream_name: str = DEFAULT_HALT_STREAM_NAME,
        consumer_group: str = DEFAULT_CONSUMER_GROUP,
        consumer_name: str = "archon72-consumer",
    ) -> None:
        """Initialize the halt stream consumer.

        Args:
            redis: Async Redis client (redis.asyncio.Redis compatible).
            stream_name: Name of the Redis Stream for halt signals.
            consumer_group: Name of the consumer group.
            consumer_name: Unique name for this consumer instance.
        """
        self._redis = redis
        self._stream_name = stream_name
        self._consumer_group = consumer_group
        self._consumer_name = consumer_name
        self._running = False
        self._halt_received = False
        self._halt_info: Optional[dict[str, str]] = None

    @property
    def stream_name(self) -> str:
        """Get the configured stream name."""
        return self._stream_name

    @property
    def has_halt_received(self) -> bool:
        """Check if a halt message has been received."""
        return self._halt_received

    def get_halt_info(self) -> Optional[dict[str, str]]:
        """Get information about the received halt signal.

        Returns:
            Dict with halt info if received, None otherwise.
        """
        return self._halt_info

    def reset_halt_state(self) -> None:
        """Reset the halt state (for testing/recovery only).

        WARNING: This should only be used in tests or during
        witnessed ceremony recovery (Story 3.4).
        """
        self._halt_received = False
        self._halt_info = None

    async def clear_halt_state(self) -> None:
        """Clear halt state as part of ceremony-authorized recovery (Story 3.4).

        This method should only be called after a valid ceremony has been
        completed and the HaltClearedEvent has been witnessed.

        Constitutional Constraint (ADR-3):
        - This is called by DualChannelHaltTransport.clear_halt()
        - The transport validates ceremony evidence before calling this

        Note:
            This clears the in-memory halt state but does NOT delete
            the stream messages (they remain for audit trail).
        """
        self._halt_received = False
        self._halt_info = None
        log.info(
            "halt_state_cleared_via_ceremony",
            consumer=self._consumer_name,
            stream=self._stream_name,
        )

    async def check_redis_halt(self) -> bool:
        """Check if halt messages exist in the stream.

        Simple check that returns True if any halt messages
        have been published to the stream.

        Returns:
            True if halt messages exist, False otherwise.
        """
        try:
            length = await self._redis.xlen(self._stream_name)
            return length > 0
        except Exception as e:
            log.warning(
                "redis_halt_check_failed",
                error=str(e),
                stream=self._stream_name,
            )
            # On Redis failure, return False (defer to DB check)
            return False

    async def start_listening(self) -> None:
        """Start listening for halt signals (background loop).

        Creates consumer group if not exists, then continuously
        reads from the stream. Call stop_listening() to stop.

        Note: This runs as a background task. Use asyncio.create_task()
        to start it non-blocking.
        """
        self._running = True

        # Create consumer group if not exists
        try:
            await self._redis.xgroup_create(
                self._stream_name,
                self._consumer_group,
                id="0",
                mkstream=True,
            )
            log.info(
                "consumer_group_created",
                stream=self._stream_name,
                group=self._consumer_group,
            )
        except Exception as e:
            # BUSYGROUP means group already exists - that's OK
            if "BUSYGROUP" not in str(e):
                log.error(
                    "consumer_group_creation_failed",
                    error=str(e),
                    stream=self._stream_name,
                )
                raise

        log.info(
            "halt_consumer_started",
            stream=self._stream_name,
            consumer=self._consumer_name,
        )

        while self._running:
            try:
                # Block for 1 second waiting for messages
                messages = await self._redis.xreadgroup(
                    self._consumer_group,
                    self._consumer_name,
                    {self._stream_name: ">"},  # Only new messages
                    count=1,
                    block=1000,  # 1 second block
                )

                for stream_name, stream_messages in messages:
                    for message_id, fields in stream_messages:
                        await self._process_halt_message(fields)
                        await self._redis.xack(
                            self._stream_name,
                            self._consumer_group,
                            message_id,
                        )

            except asyncio.CancelledError:
                log.info("halt_consumer_cancelled")
                break
            except Exception as e:
                log.warning(
                    "halt_consumer_error",
                    error=str(e),
                    stream=self._stream_name,
                )
                # Brief pause before retry
                with contextlib.suppress(asyncio.CancelledError):
                    await asyncio.sleep(0.1)

        log.info(
            "halt_consumer_stopped",
            stream=self._stream_name,
            consumer=self._consumer_name,
        )

    async def stop_listening(self) -> None:
        """Stop the background listening loop.

        Sets _running to False, causing the start_listening loop to exit
        on its next iteration.
        """
        self._running = False
        log.info("halt_consumer_stop_requested", consumer=self._consumer_name)

    async def _process_halt_message(self, fields: dict[str, Any]) -> None:
        """Process a halt message from the stream.

        Args:
            fields: Message fields from Redis Stream.
        """
        self._halt_received = True
        self._halt_info = {
            "reason": str(fields.get("reason", "Unknown")),
            "crisis_event_id": str(fields.get("crisis_event_id", "")),
            "timestamp": str(fields.get("timestamp", "")),
            "source_service": str(fields.get("source_service", "")),
        }

        log.warning(
            "halt_signal_received",
            reason=self._halt_info["reason"],
            crisis_event_id=self._halt_info["crisis_event_id"],
            source_service=self._halt_info["source_service"],
        )
