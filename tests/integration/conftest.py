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

from __future__ import annotations

import os
from pathlib import Path
from collections.abc import AsyncGenerator, Generator

import pytest
import redis.asyncio as aioredis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from testcontainers.postgres import PostgresContainer
from testcontainers.redis import RedisContainer

REALMS_MIGRATION_FILE = (
    Path(__file__).parent.parent.parent / "migrations" / "015_create_realms_table.sql"
)


def _get_sql_echo() -> bool:
    """Get SQL echo setting from environment.

    Set SQLALCHEMY_ECHO=1 or SQLALCHEMY_ECHO=true to enable SQL logging.
    Defaults to False for cleaner test output.
    """
    return os.environ.get("SQLALCHEMY_ECHO", "").lower() in ("1", "true", "yes")


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

    Environment:
        SQLALCHEMY_ECHO: Set to "1" or "true" to enable SQL logging for debugging.
    """
    engine = create_async_engine(postgres_async_url, echo=_get_sql_echo())

    async_session_maker = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    session: AsyncSession | None = None
    try:
        session = async_session_maker()
        async with session.begin():
            yield session
            # Rollback after each test for isolation (AC2)
            await session.rollback()
    finally:
        # Ensure session is closed even if rollback fails
        if session is not None:
            await session.close()
        await engine.dispose()


@pytest.fixture(scope="session")
def redis_url(redis_container: RedisContainer) -> str:
    """Get Redis connection URL from container.

    Provides consistent URL-based connection pattern matching PostgreSQL.

    Returns:
        redis:// URL string
    """
    # Use get_connection_url() for consistency with postgres pattern
    # RedisContainer.get_connection_url() returns redis://host:port/db format
    url: str = redis_container.get_connection_url()
    return url


@pytest.fixture
async def redis_client(
    redis_url: str,
) -> AsyncGenerator[aioredis.Redis[bytes], None]:
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
    client: aioredis.Redis[bytes] = aioredis.from_url(redis_url)

    try:
        yield client
    finally:
        # Clean up after each test for isolation (AC4)
        # Use try/except to ensure aclose is called even if flushdb fails
        try:
            await client.flushdb()
        finally:
            await client.aclose()


class QueryResult:
    """Minimal result wrapper matching Supabase response shape."""

    def __init__(self, data: list[dict]) -> None:
        self.data = data


class TableQuery:
    """Lightweight query builder for integration tests."""

    def __init__(self, db_session: AsyncSession, table_name: str) -> None:
        self._db_session = db_session
        self._table_name = table_name
        self._columns = "*"
        self._filters: list[tuple[str, object]] = []
        self._limit: int | None = None
        self._insert_data: list[dict] | None = None

    def select(self, columns: str) -> "TableQuery":
        self._columns = columns
        return self

    def eq(self, column: str, value: object) -> "TableQuery":
        self._filters.append((column, value))
        return self

    def limit(self, count: int) -> "TableQuery":
        self._limit = count
        return self

    def insert(self, data: dict | list[dict]) -> "TableQuery":
        self._insert_data = data if isinstance(data, list) else [data]
        return self

    async def execute(self) -> QueryResult:
        if self._insert_data is not None:
            return await self._execute_insert()
        return await self._execute_select()

    async def _execute_select(self) -> QueryResult:
        sql = f"SELECT {self._columns} FROM {self._table_name}"
        params: dict[str, object] = {}

        if self._filters:
            clauses = []
            for idx, (column, value) in enumerate(self._filters):
                param_name = f"{column}_{idx}"
                clauses.append(f"{column} = :{param_name}")
                params[param_name] = value
            sql += " WHERE " + " AND ".join(clauses)

        if self._limit is not None:
            sql += " LIMIT :limit"
            params["limit"] = self._limit

        result = await self._db_session.execute(text(sql), params)
        rows = [dict(row) for row in result.mappings().all()]
        return QueryResult(rows)

    async def _execute_insert(self) -> QueryResult:
        if not self._insert_data:
            return QueryResult([])

        columns = list(self._insert_data[0].keys())
        column_list = ", ".join(columns)
        value_placeholders = ", ".join(f":{col}" for col in columns)

        sql = (
            f"INSERT INTO {self._table_name} ({column_list}) "
            f"VALUES ({value_placeholders}) RETURNING *"
        )

        rows: list[dict] = []
        for row in self._insert_data:
            result = await self._db_session.execute(text(sql), row)
            rows.extend(dict(r) for r in result.mappings().all())

        await self._db_session.flush()
        return QueryResult(rows)


class SupabaseClientStub:
    """Minimal supabase-like client for integration schema tests."""

    def __init__(self, db_session: AsyncSession) -> None:
        self._db_session = db_session

    def table(self, table_name: str) -> TableQuery:
        return TableQuery(self._db_session, table_name)


class IntegrationTestBase:
    """Base class for integration tests needing a supabase-style client."""

    client: SupabaseClientStub

    @pytest.fixture(autouse=True)
    async def _setup_realm_schema(self, db_session: AsyncSession) -> None:
        migration_sql = REALMS_MIGRATION_FILE.read_text()
        for statement in migration_sql.split(";"):
            cleaned = statement.strip()
            if cleaned and not cleaned.startswith("--"):
                await db_session.execute(text(cleaned))
        await db_session.flush()
        self.client = SupabaseClientStub(db_session)
