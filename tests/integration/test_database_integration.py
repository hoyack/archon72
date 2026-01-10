"""Integration tests for database connectivity and operations.

These tests verify:
- AC1: Testcontainers setup with Docker
- AC2: Database session fixture provides real async connection
- AC3: Single test execution with container startup
- AC5: Test isolation (changes in one test don't affect another)
- Container startup performance (< 10s for both containers)
"""

from __future__ import annotations

import time

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from testcontainers.postgres import PostgresContainer
from testcontainers.redis import RedisContainer


class TestDatabaseConnectivity:
    """Tests for basic database connectivity using testcontainers."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_database_connection_works(
        self, db_session: AsyncSession
    ) -> None:
        """AC1, AC2: Verify database connection is established."""
        result = await db_session.execute(text("SELECT 1 as value"))
        row = result.fetchone()
        assert row is not None
        assert row[0] == 1

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_database_version_is_postgres_16(
        self, db_session: AsyncSession
    ) -> None:
        """AC1: Verify PostgreSQL 16 is running (Supabase-compatible)."""
        result = await db_session.execute(text("SELECT version()"))
        row = result.fetchone()
        assert row is not None
        version_string = str(row[0])
        assert "PostgreSQL 16" in version_string

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_async_operations_work(
        self, db_session: AsyncSession
    ) -> None:
        """AC2: Verify async database operations work correctly."""
        # Create a temporary table
        await db_session.execute(
            text("CREATE TEMPORARY TABLE test_async (id SERIAL PRIMARY KEY, name TEXT)")
        )

        # Insert data
        await db_session.execute(
            text("INSERT INTO test_async (name) VALUES ('test_value')")
        )

        # Query data
        result = await db_session.execute(text("SELECT name FROM test_async"))
        row = result.fetchone()
        assert row is not None
        assert row[0] == "test_value"


class TestDatabaseIsolation:
    """Tests for database isolation between test functions."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_isolation_01_first_insert_data(
        self, db_session: AsyncSession
    ) -> None:
        """AC5: First test creates data that should not affect second test."""
        # Create a table with a unique name to avoid conflicts
        await db_session.execute(
            text(
                "CREATE TABLE IF NOT EXISTS isolation_test "
                "(id SERIAL PRIMARY KEY, marker TEXT)"
            )
        )
        await db_session.execute(
            text("INSERT INTO isolation_test (marker) VALUES ('first_test')")
        )

        # Verify data exists in this test
        result = await db_session.execute(
            text("SELECT COUNT(*) FROM isolation_test WHERE marker = 'first_test'")
        )
        count = result.scalar()
        assert count == 1

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_isolation_02_second_no_data_from_first(
        self, db_session: AsyncSession
    ) -> None:
        """AC5: Second test should not see data from first test (rollback isolation)."""
        # Check if the table exists (it shouldn't due to rollback)
        result = await db_session.execute(
            text(
                "SELECT EXISTS ("
                "SELECT FROM information_schema.tables "
                "WHERE table_name = 'isolation_test'"
                ")"
            )
        )
        table_exists = result.scalar()

        # Table should not exist because first test was rolled back
        assert table_exists is False, "Table from previous test should not exist"


class TestDatabaseCRUD:
    """Tests for basic CRUD operations."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_create_and_read(
        self, db_session: AsyncSession
    ) -> None:
        """AC2: Test CREATE and READ operations."""
        # Create
        await db_session.execute(
            text("CREATE TEMPORARY TABLE crud_test (id SERIAL PRIMARY KEY, data TEXT)")
        )
        await db_session.execute(
            text("INSERT INTO crud_test (data) VALUES ('created')")
        )

        # Read
        result = await db_session.execute(text("SELECT data FROM crud_test"))
        row = result.fetchone()
        assert row is not None
        assert row[0] == "created"

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_update_operation(
        self, db_session: AsyncSession
    ) -> None:
        """AC2: Test UPDATE operation."""
        # Setup
        await db_session.execute(
            text("CREATE TEMPORARY TABLE update_test (id SERIAL PRIMARY KEY, data TEXT)")
        )
        await db_session.execute(
            text("INSERT INTO update_test (data) VALUES ('original')")
        )

        # Update
        await db_session.execute(
            text("UPDATE update_test SET data = 'updated' WHERE data = 'original'")
        )

        # Verify
        result = await db_session.execute(text("SELECT data FROM update_test"))
        row = result.fetchone()
        assert row is not None
        assert row[0] == "updated"

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_delete_operation(
        self, db_session: AsyncSession
    ) -> None:
        """AC2: Test DELETE operation."""
        # Setup
        await db_session.execute(
            text("CREATE TEMPORARY TABLE delete_test (id SERIAL PRIMARY KEY, data TEXT)")
        )
        await db_session.execute(
            text("INSERT INTO delete_test (data) VALUES ('to_delete')")
        )

        # Verify exists
        result = await db_session.execute(
            text("SELECT COUNT(*) FROM delete_test")
        )
        assert result.scalar() == 1

        # Delete
        await db_session.execute(
            text("DELETE FROM delete_test WHERE data = 'to_delete'")
        )

        # Verify deleted
        result = await db_session.execute(
            text("SELECT COUNT(*) FROM delete_test")
        )
        assert result.scalar() == 0


class TestContainerStartup:
    """Tests for container startup performance verification."""

    @pytest.mark.integration
    def test_postgres_container_startup_time(self) -> None:
        """Verify PostgreSQL container starts within acceptable time (<10s).

        This test measures actual container startup time to validate
        performance claims. The 10s threshold accounts for:
        - Docker image pull (if not cached)
        - Container creation
        - PostgreSQL startup and ready state
        """
        start = time.perf_counter()

        with PostgresContainer("postgres:16-alpine") as postgres:
            # Verify container is ready by getting connection URL
            url = postgres.get_connection_url()
            assert url is not None
            assert "postgresql" in url

        elapsed = time.perf_counter() - start

        # Threshold of 10s is generous; typical startup is 3-5s with cached image
        assert elapsed < 10.0, f"PostgreSQL container took {elapsed:.2f}s to start (expected <10s)"

    @pytest.mark.integration
    def test_redis_container_startup_time(self) -> None:
        """Verify Redis container starts within acceptable time (<10s).

        This test measures actual container startup time to validate
        performance claims. Redis typically starts faster than PostgreSQL.
        """
        start = time.perf_counter()

        with RedisContainer("redis:7-alpine") as redis_cont:
            # Verify container is ready by getting connection URL
            url = redis_cont.get_connection_url()
            assert url is not None
            assert "redis" in url

        elapsed = time.perf_counter() - start

        # Threshold of 10s is generous; typical startup is 2-3s with cached image
        assert elapsed < 10.0, f"Redis container took {elapsed:.2f}s to start (expected <10s)"
