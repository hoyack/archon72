"""Unit tests for HaltStreamConsumer (Story 3.3, Task 4).

Tests the Redis Streams halt consumer for checking halt state.
This is the Redis channel reader of the dual-channel halt transport.

ADR-3: Redis Streams for speed + DB halt flag for safety.
- Consumer groups for reliable delivery
- Uses XREADGROUP with blocking read
- XACK for message acknowledgment
"""

import asyncio
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from src.infrastructure.adapters.messaging.halt_stream_consumer import (
    DEFAULT_CONSUMER_GROUP,
    DEFAULT_HALT_STREAM_NAME,
    HaltStreamConsumer,
)


class TestHaltStreamConsumer:
    """Test the halt stream consumer."""

    @pytest.fixture
    def mock_redis(self) -> AsyncMock:
        """Create a mock Redis client."""
        redis = AsyncMock()
        # Default: no halt messages
        redis.xreadgroup.return_value = []
        # Consumer group may already exist
        redis.xgroup_create.return_value = True
        # XINFO returns stream info
        redis.xinfo_stream.return_value = {"length": 0}
        return redis

    @pytest.fixture
    def consumer(self, mock_redis: AsyncMock) -> HaltStreamConsumer:
        """Create a consumer with mock Redis."""
        return HaltStreamConsumer(
            redis=mock_redis,
            stream_name=DEFAULT_HALT_STREAM_NAME,
            consumer_group=DEFAULT_CONSUMER_GROUP,
            consumer_name="test-consumer-1",
        )

    @pytest.mark.asyncio
    async def test_check_redis_halt_no_messages(
        self, consumer: HaltStreamConsumer, mock_redis: AsyncMock
    ) -> None:
        """check_redis_halt should return False when no halt messages exist."""
        # Stream has no messages
        mock_redis.xlen.return_value = 0

        halted = await consumer.check_redis_halt()

        assert halted is False

    @pytest.mark.asyncio
    async def test_check_redis_halt_with_messages(
        self, consumer: HaltStreamConsumer, mock_redis: AsyncMock
    ) -> None:
        """check_redis_halt should return True when halt messages exist."""
        # Stream has messages
        mock_redis.xlen.return_value = 1

        halted = await consumer.check_redis_halt()

        assert halted is True

    @pytest.mark.asyncio
    async def test_has_halt_received_initial_false(
        self, consumer: HaltStreamConsumer
    ) -> None:
        """has_halt_received should be False initially."""
        assert consumer.has_halt_received is False

    @pytest.mark.asyncio
    async def test_has_halt_received_after_process(
        self, consumer: HaltStreamConsumer
    ) -> None:
        """has_halt_received should be True after processing a halt message."""
        crisis_id = uuid4()
        await consumer._process_halt_message({
            "reason": "FR17: Fork detected",
            "crisis_event_id": str(crisis_id),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source_service": "test-service",
        })

        assert consumer.has_halt_received is True

    @pytest.mark.asyncio
    async def test_get_halt_info_initial_none(
        self, consumer: HaltStreamConsumer
    ) -> None:
        """get_halt_info should return None initially."""
        info = consumer.get_halt_info()
        assert info is None

    @pytest.mark.asyncio
    async def test_get_halt_info_after_process(
        self, consumer: HaltStreamConsumer
    ) -> None:
        """get_halt_info should return halt details after processing."""
        crisis_id = uuid4()
        await consumer._process_halt_message({
            "reason": "FR17: Fork detected",
            "crisis_event_id": str(crisis_id),
            "timestamp": "2026-01-07T00:00:00+00:00",
            "source_service": "test-service",
        })

        info = consumer.get_halt_info()
        assert info is not None
        assert info["reason"] == "FR17: Fork detected"
        assert info["crisis_event_id"] == str(crisis_id)

    @pytest.mark.asyncio
    async def test_consumer_group_name_configured(
        self, consumer: HaltStreamConsumer
    ) -> None:
        """Consumer group name should be configurable."""
        assert consumer._consumer_group == DEFAULT_CONSUMER_GROUP

    @pytest.mark.asyncio
    async def test_consumer_name_configured(
        self, consumer: HaltStreamConsumer
    ) -> None:
        """Consumer name should be configurable."""
        assert consumer._consumer_name == "test-consumer-1"

    @pytest.mark.asyncio
    async def test_stop_listening_sets_running_false(
        self, consumer: HaltStreamConsumer
    ) -> None:
        """stop_listening should set _running to False."""
        consumer._running = True

        await consumer.stop_listening()

        assert consumer._running is False

    @pytest.mark.asyncio
    async def test_reset_halt_state(
        self, consumer: HaltStreamConsumer
    ) -> None:
        """reset_halt_state should clear received halt info."""
        # Set up halt state
        await consumer._process_halt_message({
            "reason": "Test",
            "crisis_event_id": str(uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source_service": "test",
        })

        assert consumer.has_halt_received is True

        # Reset
        consumer.reset_halt_state()

        assert consumer.has_halt_received is False
        assert consumer.get_halt_info() is None


class TestDefaultConstants:
    """Test the default constants."""

    def test_default_stream_name(self) -> None:
        """Default stream name should match publisher."""
        assert DEFAULT_HALT_STREAM_NAME == "halt:signals"

    def test_default_consumer_group(self) -> None:
        """Default consumer group should be 'halt:consumers'."""
        assert DEFAULT_CONSUMER_GROUP == "halt:consumers"
