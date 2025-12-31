"""
Integration test configuration with testcontainers.

This module provides session-scoped container fixtures for integration testing:
- PostgreSQL 16 container (Supabase-compatible)
- Redis 7 container

Container Reuse Pattern (AC5):
- Containers are started once per test session (scope="session")
- Database/Redis state is reset between tests (function-scoped fixtures)
- Containers are automatically cleaned up after all tests complete

Usage:
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_example(db_session: AsyncSession, redis_client: Redis) -> None:
        # db_session provides isolated async database connection
        # redis_client provides isolated Redis connection
        ...

Note: Docker must be running for these fixtures to work.
"""

from collections.abc import AsyncGenerator, Generator
from typing import Any

import pytest
import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from testcontainers.postgres import PostgresContainer
from testcontainers.redis import RedisContainer


# Session-scoped container fixtures (started once per test session)
@pytest.fixture(scope="session")
def postgres_container() -> Generator[PostgresContainer, None, None]:
    """Session-scoped PostgreSQL 16 container matching Supabase.

    The container is started once and reused across all integration tests.
    This significantly improves test performance (AC5: session-scoped containers).

    Example:
        def test_uses_postgres(postgres_container: PostgresContainer) -> None:
            url = postgres_container.get_connection_url()
            # Use URL to connect to database
    """
    with PostgresContainer("postgres:16-alpine") as postgres:
        yield postgres


@pytest.fixture(scope="session")
def redis_container() -> Generator[RedisContainer, None, None]:
    """Session-scoped Redis 7 container.

    The container is started once and reused across all integration tests.
    This significantly improves test performance (AC5: session-scoped containers).

    Example:
        def test_uses_redis(redis_container: RedisContainer) -> None:
            url = redis_container.get_connection_url()
            # Use URL to connect to Redis
    """
    with RedisContainer("redis:7-alpine") as redis_cont:
        yield redis_cont


@pytest.fixture(scope="session")
def postgres_async_url(postgres_container: PostgresContainer) -> str:
    """Get async-compatible PostgreSQL connection URL.

    Converts the sync URL to async URL for use with asyncpg.
    testcontainers returns psycopg2 URL by default, we convert to asyncpg.

    Returns:
        postgresql+asyncpg:// URL string
    """
    sync_url = postgres_container.get_connection_url()
    # testcontainers returns psycopg2 URL, convert to asyncpg
    # Replace both possible prefixes
    async_url: str = sync_url.replace(
        "postgresql+psycopg2://", "postgresql+asyncpg://"
    ).replace("postgresql://", "postgresql+asyncpg://")
    return async_url


# Function-scoped fixtures for test isolation
@pytest.fixture
async def db_session(
    postgres_async_url: str,
) -> AsyncGenerator[AsyncSession, None]:
    """Per-test async database session with rollback isolation (AC2).

    Provides a fresh database session for each test with automatic
    transaction rollback to ensure test isolation.

    The session is wrapped in a transaction that is rolled back after
    each test, ensuring changes don't persist between tests.

    Example:
        @pytest.mark.asyncio
        async def test_database_operation(db_session: AsyncSession) -> None:
            # Perform database operations
            result = await db_session.execute(text("SELECT 1"))
            # Session is automatically rolled back after test
    """
    engine = create_async_engine(postgres_async_url, echo=False)

    async_session_maker = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session_maker() as session, session.begin():
        yield session
        # Rollback after each test for isolation (AC2)
        await session.rollback()

    await engine.dispose()


@pytest.fixture
async def redis_client(
    redis_container: RedisContainer,
) -> AsyncGenerator[aioredis.Redis, None]:  # type: ignore[type-arg]
    """Per-test Redis client with FLUSHDB isolation (AC4).

    Provides a fresh Redis connection for each test with automatic
    database flush after each test to ensure isolation.

    Example:
        @pytest.mark.asyncio
        async def test_redis_operation(redis_client: Redis) -> None:
            await redis_client.set("key", "value")
            result = await redis_client.get("key")
            # Redis is automatically flushed after test
    """
    # Get connection details from container
    host = redis_container.get_container_host_ip()
    port = redis_container.get_exposed_port(6379)

    client: aioredis.Redis[Any] = aioredis.Redis(host=host, port=int(port))

    yield client

    # Clean up after each test for isolation (AC4)
    await client.flushdb()
    await client.aclose()
