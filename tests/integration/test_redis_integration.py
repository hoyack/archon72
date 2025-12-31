"""Integration tests for Redis connectivity and operations.

These tests verify:
- AC1: Testcontainers setup with Docker (Redis container)
- AC4: Redis client fixture provides real async connection
- AC5: Test isolation (Redis is flushed between tests)
"""

from typing import TYPE_CHECKING, Any

import pytest
import redis.asyncio as aioredis

if TYPE_CHECKING:
    from redis.asyncio import Redis


class TestRedisConnectivity:
    """Tests for basic Redis connectivity using testcontainers."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_redis_connection_works(
        self, redis_client: "Redis[Any]"
    ) -> None:
        """AC1, AC4: Verify Redis connection is established."""
        # PING should return True
        result = await redis_client.ping()
        assert result is True

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_redis_server_info(
        self, redis_client: "Redis[Any]"
    ) -> None:
        """AC1: Verify Redis server info is accessible."""
        info = await redis_client.info()
        assert "redis_version" in info
        # Should be Redis 7.x
        version = str(info["redis_version"])
        assert version.startswith("7"), f"Expected Redis 7.x, got {version}"


class TestRedisOperations:
    """Tests for basic Redis operations."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_set_and_get(
        self, redis_client: "Redis[Any]"
    ) -> None:
        """AC4: Test SET and GET operations."""
        await redis_client.set("test_key", "test_value")
        result = await redis_client.get("test_key")
        assert result == b"test_value"

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_delete_operation(
        self, redis_client: "Redis[Any]"
    ) -> None:
        """AC4: Test DELETE operation."""
        await redis_client.set("delete_key", "value")
        assert await redis_client.exists("delete_key") == 1

        await redis_client.delete("delete_key")
        assert await redis_client.exists("delete_key") == 0

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_hash_operations(
        self, redis_client: "Redis[Any]"
    ) -> None:
        """AC4: Test hash operations (useful for caching)."""
        await redis_client.hset("hash_key", "field1", "value1")
        await redis_client.hset("hash_key", "field2", "value2")

        result = await redis_client.hget("hash_key", "field1")
        assert result == b"value1"

        all_fields = await redis_client.hgetall("hash_key")
        assert all_fields == {b"field1": b"value1", b"field2": b"value2"}

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_list_operations(
        self, redis_client: "Redis[Any]"
    ) -> None:
        """AC4: Test list operations (useful for queues)."""
        await redis_client.rpush("list_key", "item1", "item2", "item3")

        length = await redis_client.llen("list_key")
        assert length == 3

        item = await redis_client.lpop("list_key")
        assert item == b"item1"

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_expiration(
        self, redis_client: "Redis[Any]"
    ) -> None:
        """AC4: Test key expiration (useful for locks)."""
        await redis_client.setex("expiring_key", 60, "value")

        ttl = await redis_client.ttl("expiring_key")
        assert 0 < ttl <= 60


class TestRedisIsolation:
    """Tests for Redis isolation between test functions."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_isolation_first_set_data(
        self, redis_client: "Redis[Any]"
    ) -> None:
        """AC5: First test sets data that should not affect second test."""
        await redis_client.set("isolation_marker", "first_test_data")

        # Verify data exists in this test
        result = await redis_client.get("isolation_marker")
        assert result == b"first_test_data"

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_isolation_second_no_data_from_first(
        self, redis_client: "Redis[Any]"
    ) -> None:
        """AC5: Second test should not see data from first test (FLUSHDB isolation)."""
        # Key from first test should not exist due to FLUSHDB
        result = await redis_client.get("isolation_marker")
        assert result is None, "Data from previous test should not exist"

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_isolation_database_is_empty(
        self, redis_client: "Redis[Any]"
    ) -> None:
        """AC5: Verify database starts empty for each test."""
        # Get all keys - should be empty at start of test
        keys = await redis_client.keys("*")
        assert len(keys) == 0, "Database should be empty at start of test"
