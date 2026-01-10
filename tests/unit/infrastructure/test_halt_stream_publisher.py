"""Unit tests for HaltStreamPublisher (Story 3.3, Task 3).

Tests the Redis Streams halt publisher for fast halt propagation.
This is the Redis channel of the dual-channel halt transport.

ADR-3: Redis Streams for speed + DB halt flag for safety.
- Redis provides fast propagation (~1ms latency)
- Uses XADD to publish halt signals
"""

from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from src.infrastructure.adapters.messaging.halt_stream_publisher import (
    DEFAULT_HALT_STREAM_NAME,
    HaltStreamPublisher,
)


class TestHaltStreamPublisher:
    """Test the halt stream publisher."""

    @pytest.fixture
    def mock_redis(self) -> AsyncMock:
        """Create a mock Redis client."""
        redis = AsyncMock()
        # xadd returns a message ID
        redis.xadd.return_value = "1704067200000-0"
        return redis

    @pytest.fixture
    def publisher(self, mock_redis: AsyncMock) -> HaltStreamPublisher:
        """Create a publisher with mock Redis."""
        return HaltStreamPublisher(
            redis=mock_redis,
            stream_name=DEFAULT_HALT_STREAM_NAME,
            service_id="test-service",
        )

    @pytest.mark.asyncio
    async def test_publish_halt_calls_xadd(
        self, publisher: HaltStreamPublisher, mock_redis: AsyncMock
    ) -> None:
        """publish_halt should call redis.xadd with correct stream name."""
        crisis_id = uuid4()

        await publisher.publish_halt(
            reason="FR17: Fork detected",
            crisis_event_id=crisis_id,
        )

        mock_redis.xadd.assert_called_once()
        call_args = mock_redis.xadd.call_args
        assert call_args[0][0] == DEFAULT_HALT_STREAM_NAME

    @pytest.mark.asyncio
    async def test_publish_halt_includes_reason(
        self, publisher: HaltStreamPublisher, mock_redis: AsyncMock
    ) -> None:
        """publish_halt should include reason in message fields."""
        crisis_id = uuid4()

        await publisher.publish_halt(
            reason="FR17: Fork detected",
            crisis_event_id=crisis_id,
        )

        call_args = mock_redis.xadd.call_args
        message_fields = call_args[0][1]
        assert message_fields["reason"] == "FR17: Fork detected"

    @pytest.mark.asyncio
    async def test_publish_halt_includes_crisis_event_id(
        self, publisher: HaltStreamPublisher, mock_redis: AsyncMock
    ) -> None:
        """publish_halt should include crisis_event_id in message fields."""
        crisis_id = uuid4()

        await publisher.publish_halt(
            reason="FR17: Fork detected",
            crisis_event_id=crisis_id,
        )

        call_args = mock_redis.xadd.call_args
        message_fields = call_args[0][1]
        assert message_fields["crisis_event_id"] == str(crisis_id)

    @pytest.mark.asyncio
    async def test_publish_halt_includes_timestamp(
        self, publisher: HaltStreamPublisher, mock_redis: AsyncMock
    ) -> None:
        """publish_halt should include ISO 8601 timestamp."""
        crisis_id = uuid4()

        await publisher.publish_halt(
            reason="FR17: Fork detected",
            crisis_event_id=crisis_id,
        )

        call_args = mock_redis.xadd.call_args
        message_fields = call_args[0][1]
        assert "timestamp" in message_fields
        # Should be parseable as ISO 8601
        timestamp = message_fields["timestamp"]
        datetime.fromisoformat(timestamp.replace("Z", "+00:00"))

    @pytest.mark.asyncio
    async def test_publish_halt_includes_source_service(
        self, publisher: HaltStreamPublisher, mock_redis: AsyncMock
    ) -> None:
        """publish_halt should include source_service in message fields."""
        crisis_id = uuid4()

        await publisher.publish_halt(
            reason="FR17: Fork detected",
            crisis_event_id=crisis_id,
        )

        call_args = mock_redis.xadd.call_args
        message_fields = call_args[0][1]
        assert message_fields["source_service"] == "test-service"

    @pytest.mark.asyncio
    async def test_publish_halt_returns_message_id(
        self, publisher: HaltStreamPublisher, mock_redis: AsyncMock
    ) -> None:
        """publish_halt should return the message ID from Redis."""
        crisis_id = uuid4()

        message_id = await publisher.publish_halt(
            reason="FR17: Fork detected",
            crisis_event_id=crisis_id,
        )

        assert message_id == "1704067200000-0"

    @pytest.mark.asyncio
    async def test_publish_halt_with_custom_stream_name(
        self, mock_redis: AsyncMock
    ) -> None:
        """Publisher should use custom stream name when configured."""
        publisher = HaltStreamPublisher(
            redis=mock_redis,
            stream_name="custom:halt:stream",
            service_id="test-service",
        )
        crisis_id = uuid4()

        await publisher.publish_halt(
            reason="Test",
            crisis_event_id=crisis_id,
        )

        call_args = mock_redis.xadd.call_args
        assert call_args[0][0] == "custom:halt:stream"


class TestDefaultHaltStreamName:
    """Test the default stream name constant."""

    def test_default_stream_name(self) -> None:
        """Default stream name should be 'halt:signals'."""
        assert DEFAULT_HALT_STREAM_NAME == "halt:signals"
