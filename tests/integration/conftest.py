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

import asyncio
import os
import re
from collections.abc import AsyncGenerator, Generator
from pathlib import Path

import asyncpg
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
PETITION_SUBMISSIONS_MIGRATION_FILE = (
    Path(__file__).parent.parent.parent
    / "migrations"
    / "012_create_petition_submissions.sql"
)
ACK_REASON_ENUM_MIGRATION_FILE = (
    Path(__file__).parent.parent.parent
    / "migrations"
    / "021_create_acknowledgment_reason_enum.sql"
)
ACK_TABLE_MIGRATION_FILE = (
    Path(__file__).parent.parent.parent
    / "migrations"
    / "022_create_acknowledgments_table.sql"
)
ACK_SCHEMA_NAME = "ack_test"


def _redis_connection_url(redis_container: RedisContainer) -> str:
    """Build Redis URL for testcontainers versions lacking get_connection_url."""
    host = redis_container.get_container_host_ip()
    port = redis_container.get_exposed_port(6379)
    return f"redis://{host}:{port}/0"


# Backfill missing method in older testcontainers versions.
if not hasattr(RedisContainer, "get_connection_url"):
    RedisContainer.get_connection_url = _redis_connection_url  # type: ignore[attr-defined]

_ACK_SCHEMA_READY = False
_ACK_SCHEMA_LOCK = asyncio.Lock()


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


@pytest.fixture
async def db_connection(
    postgres_container: PostgresContainer,
) -> AsyncGenerator[asyncpg.Connection, None]:
    """Asyncpg connection for tests expecting fetch/fetchval semantics."""
    dsn = postgres_container.get_connection_url().replace(
        "postgresql+psycopg2://", "postgresql://"
    )
    conn = await asyncpg.connect(dsn)
    try:
        await conn.execute(f"CREATE SCHEMA IF NOT EXISTS {ACK_SCHEMA_NAME}")
        await conn.execute(f"SET search_path TO {ACK_SCHEMA_NAME}")
        await _ensure_acknowledgment_schema(conn, ACK_SCHEMA_NAME)
        yield conn
    finally:
        await conn.close()


async def _ensure_acknowledgment_schema(
    conn: asyncpg.Connection, schema_name: str
) -> None:
    """Apply migrations needed for acknowledgment integration tests once."""
    global _ACK_SCHEMA_READY
    if _ACK_SCHEMA_READY:
        return
    async with _ACK_SCHEMA_LOCK:
        if _ACK_SCHEMA_READY:
            return

        petition_exists = await conn.fetchval(
            """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = $1
                AND table_name = 'petition_submissions'
            )
            """,
            schema_name,
        )
        if not petition_exists:
            await conn.execute(PETITION_SUBMISSIONS_MIGRATION_FILE.read_text())

        enum_exists = await conn.fetchval(
            """
            SELECT EXISTS (
                SELECT 1
                FROM pg_type
                JOIN pg_namespace ON pg_namespace.oid = pg_type.typnamespace
                WHERE pg_type.typname = 'acknowledgment_reason_enum'
                AND pg_namespace.nspname = $1
            )
            """,
            schema_name,
        )
        if not enum_exists:
            await conn.execute(ACK_REASON_ENUM_MIGRATION_FILE.read_text())
        else:
            value_exists = await conn.fetchval(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM pg_enum
                    JOIN pg_type ON pg_enum.enumtypid = pg_type.oid
                    JOIN pg_namespace ON pg_namespace.oid = pg_type.typnamespace
                    WHERE pg_type.typname = 'acknowledgment_reason_enum'
                    AND pg_enum.enumlabel = 'KNIGHT_REFERRAL'
                    AND pg_namespace.nspname = $1
                )
                """,
                schema_name,
            )
            if not value_exists:
                await conn.execute(
                    f"ALTER TYPE {schema_name}.acknowledgment_reason_enum "
                    "ADD VALUE IF NOT EXISTS 'KNIGHT_REFERRAL'"
                )

        ack_exists = await conn.fetchval(
            """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = $1
                AND table_name = 'acknowledgments'
            )
            """,
            schema_name,
        )
        if not ack_exists:
            await conn.execute(ACK_TABLE_MIGRATION_FILE.read_text())

        _ACK_SCHEMA_READY = True


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

    def select(self, columns: str) -> TableQuery:
        self._columns = columns
        return self

    def eq(self, column: str, value: object) -> TableQuery:
        self._filters.append((column, value))
        return self

    def limit(self, count: int) -> TableQuery:
        self._limit = count
        return self

    def insert(self, data: dict | list[dict]) -> TableQuery:
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

    @staticmethod
    def _split_sql_statements(sql: str) -> list[str]:
        """Split a SQL script into individual statements.

        We can't naively split on ';' because migrations may contain PL/pgSQL
        functions (dollar-quoted) with internal semicolons.
        """

        def scan_dollar_delimiter(source: str, start: int) -> str | None:
            if source[start] != "$":
                return None
            end = source.find("$", start + 1)
            if end == -1:
                return None
            tag = source[start + 1 : end]
            if tag and not all(ch.isalnum() or ch == "_" for ch in tag):
                return None
            return source[start : end + 1]

        statements: list[str] = []
        buf: list[str] = []

        in_single_quote = False
        in_double_quote = False
        in_line_comment = False
        in_block_comment = False
        dollar_delim: str | None = None

        i = 0
        while i < len(sql):
            ch = sql[i]
            nxt = sql[i + 1] if i + 1 < len(sql) else ""

            if in_line_comment:
                buf.append(ch)
                if ch == "\n":
                    in_line_comment = False
                i += 1
                continue

            if in_block_comment:
                buf.append(ch)
                if ch == "*" and nxt == "/":
                    buf.append(nxt)
                    i += 2
                    in_block_comment = False
                    continue
                i += 1
                continue

            if dollar_delim is not None:
                if sql.startswith(dollar_delim, i):
                    buf.append(dollar_delim)
                    i += len(dollar_delim)
                    dollar_delim = None
                    continue
                buf.append(ch)
                i += 1
                continue

            if in_single_quote:
                buf.append(ch)
                if ch == "'":
                    if nxt == "'":  # Escaped quote in standard SQL strings.
                        buf.append(nxt)
                        i += 2
                        continue
                    in_single_quote = False
                i += 1
                continue

            if in_double_quote:
                buf.append(ch)
                if ch == '"':
                    if nxt == '"':  # Escaped double quote in identifiers.
                        buf.append(nxt)
                        i += 2
                        continue
                    in_double_quote = False
                i += 1
                continue

            # Outside any quoted/comment context.
            if ch == "-" and nxt == "-":
                buf.append(ch)
                buf.append(nxt)
                i += 2
                in_line_comment = True
                continue

            if ch == "/" and nxt == "*":
                buf.append(ch)
                buf.append(nxt)
                i += 2
                in_block_comment = True
                continue

            if ch == "$":
                delim = scan_dollar_delimiter(sql, i)
                if delim is not None:
                    buf.append(delim)
                    i += len(delim)
                    dollar_delim = delim
                    continue

            if ch == "'":
                buf.append(ch)
                in_single_quote = True
                i += 1
                continue

            if ch == '"':
                buf.append(ch)
                in_double_quote = True
                i += 1
                continue

            if ch == ";":
                statement = "".join(buf).strip()
                if statement:
                    statements.append(statement)
                buf = []
                i += 1
                continue

            buf.append(ch)
            i += 1

        tail = "".join(buf).strip()
        if tail:
            statements.append(tail)

        return statements

    @pytest.fixture(autouse=True)
    async def _setup_realm_schema(self, db_session: AsyncSession) -> None:
        migration_sql = REALMS_MIGRATION_FILE.read_text()
        for statement in self._split_sql_statements(migration_sql):
            cleaned = statement.strip()
            if cleaned:
                await db_session.execute(text(cleaned))
        await db_session.flush()
        self.client = SupabaseClientStub(db_session)


_PLACEHOLDER_RE = re.compile(r"%s")


def _convert_placeholders(query: str) -> str:
    """Convert psycopg-style %s placeholders to asyncpg $1 format."""
    parts = _PLACEHOLDER_RE.split(query)
    if len(parts) == 1:
        return query
    rebuilt: list[str] = []
    for index, part in enumerate(parts[:-1], start=1):
        rebuilt.append(part)
        rebuilt.append(f"${index}")
    rebuilt.append(parts[-1])
    return "".join(rebuilt)


def _is_select_query(query: str) -> bool:
    stripped = query.lstrip().upper()
    return stripped.startswith("SELECT") or stripped.startswith("WITH")


class AsyncpgSyncCursor:
    """Sync cursor facade over asyncpg for legacy-style tests."""

    def __init__(self, connection: AsyncpgSyncConnection) -> None:
        self._connection = connection
        self._rows: list[tuple] = []

    def __enter__(self) -> AsyncpgSyncCursor:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self._rows = []

    def execute(self, query: str, params: tuple | list | None = None) -> None:
        sql = _convert_placeholders(query)
        values = tuple(params) if params is not None else ()
        if _is_select_query(sql):
            rows = self._connection._run(self._connection._conn.fetch(sql, *values))
            self._rows = [tuple(row) for row in rows]
        else:
            self._connection._run(self._connection._conn.execute(sql, *values))
            self._rows = []

    def fetchone(self) -> tuple | None:
        if not self._rows:
            return None
        return self._rows.pop(0)

    def fetchall(self) -> list[tuple]:
        rows = list(self._rows)
        self._rows = []
        return rows


class AsyncpgSyncConnection:
    """Minimal sync connection wrapper backed by asyncpg."""

    def __init__(self, dsn: str) -> None:
        self._loop = asyncio.new_event_loop()
        self._conn = self._loop.run_until_complete(asyncpg.connect(dsn))

    def _run(self, coro):
        return self._loop.run_until_complete(coro)

    def cursor(self) -> AsyncpgSyncCursor:
        return AsyncpgSyncCursor(self)

    def commit(self) -> None:
        # asyncpg autocommits outside explicit transactions
        return None

    def rollback(self) -> None:
        # No explicit transaction scope in this sync wrapper
        return None

    def close(self) -> None:
        self._loop.run_until_complete(self._conn.close())
        self._loop.close()


@pytest.fixture
def test_database_connection(
    postgres_container: PostgresContainer,
) -> Generator[AsyncpgSyncConnection, None, None]:
    """Sync-style database connection backed by asyncpg for legacy tests."""
    dsn = postgres_container.get_connection_url().replace(
        "postgresql+psycopg2://", "postgresql://"
    )
    conn = AsyncpgSyncConnection(dsn)
    try:
        yield conn
    finally:
        conn.close()
