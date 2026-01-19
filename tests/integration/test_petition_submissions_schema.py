"""Integration tests for petition_submissions schema (Story 0.2, FR-2.2).

Tests:
- Table exists with correct columns (AC1)
- Enum values are queryable (AC2, AC3)
- CHECK constraint rejects oversized text (AC1)
- Indexes exist (AC1)
- updated_at trigger fires on update (AC1)

Requires Docker for testcontainers PostgreSQL.
"""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# Path to migration file
MIGRATION_FILE = Path(__file__).parent.parent.parent / "migrations" / "012_create_petition_submissions.sql"


@pytest.fixture
async def petition_schema(db_session: AsyncSession) -> AsyncSession:
    """Apply migration and return session with schema ready.

    This fixture reads the migration SQL and applies it to the test database.
    """
    migration_sql = MIGRATION_FILE.read_text()
    # Split by semicolons and execute each statement
    # (excluding empty statements)
    for statement in migration_sql.split(";"):
        cleaned = statement.strip()
        if cleaned and not cleaned.startswith("--"):
            await db_session.execute(text(cleaned))
    await db_session.flush()
    return db_session


@pytest.mark.integration
@pytest.mark.asyncio
class TestPetitionSubmissionsTable:
    """Test petition_submissions table structure."""

    async def test_table_exists(self, petition_schema: AsyncSession) -> None:
        """AC1: Verify petition_submissions table was created."""
        result = await petition_schema.execute(
            text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = 'petition_submissions'
                )
            """)
        )
        exists = result.scalar()
        assert exists is True

    async def test_table_columns(self, petition_schema: AsyncSession) -> None:
        """AC1: Verify all required columns exist with correct types."""
        result = await petition_schema.execute(
            text("""
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns
                WHERE table_name = 'petition_submissions'
                ORDER BY ordinal_position
            """)
        )
        columns = {row[0]: {"type": row[1], "nullable": row[2], "default": row[3]}
                   for row in result.fetchall()}

        # Verify expected columns
        assert "id" in columns
        assert columns["id"]["type"] == "uuid"
        assert columns["id"]["nullable"] == "NO"

        assert "type" in columns
        assert columns["type"]["type"] == "USER-DEFINED"  # enum
        assert columns["type"]["nullable"] == "NO"

        assert "text" in columns
        assert columns["text"]["type"] == "text"
        assert columns["text"]["nullable"] == "NO"

        assert "submitter_id" in columns
        assert columns["submitter_id"]["type"] == "uuid"
        assert columns["submitter_id"]["nullable"] == "YES"  # nullable

        assert "state" in columns
        assert columns["state"]["type"] == "USER-DEFINED"  # enum
        assert columns["state"]["nullable"] == "NO"

        assert "content_hash" in columns
        assert columns["content_hash"]["type"] == "bytea"
        assert columns["content_hash"]["nullable"] == "YES"

        assert "realm" in columns
        assert columns["realm"]["type"] == "text"
        assert columns["realm"]["nullable"] == "NO"

        assert "created_at" in columns
        assert "updated_at" in columns


@pytest.mark.integration
@pytest.mark.asyncio
class TestPetitionEnums:
    """Test petition enum types."""

    async def test_petition_type_enum_values(self, petition_schema: AsyncSession) -> None:
        """AC2: Verify petition_type_enum has all expected values."""
        result = await petition_schema.execute(
            text("""
                SELECT unnest(enum_range(NULL::petition_type_enum))::text
            """)
        )
        values = [row[0] for row in result.fetchall()]

        assert "GENERAL" in values
        assert "CESSATION" in values
        assert "GRIEVANCE" in values
        assert "COLLABORATION" in values
        assert len(values) == 4

    async def test_petition_state_enum_values(self, petition_schema: AsyncSession) -> None:
        """AC3: Verify petition_state_enum has all expected values."""
        result = await petition_schema.execute(
            text("""
                SELECT unnest(enum_range(NULL::petition_state_enum))::text
            """)
        )
        values = [row[0] for row in result.fetchall()]

        assert "RECEIVED" in values
        assert "DELIBERATING" in values
        assert "ACKNOWLEDGED" in values
        assert "REFERRED" in values
        assert "ESCALATED" in values
        assert len(values) == 5


@pytest.mark.integration
@pytest.mark.asyncio
class TestPetitionConstraints:
    """Test petition table constraints."""

    async def test_text_length_constraint_rejects_oversized(
        self, petition_schema: AsyncSession
    ) -> None:
        """AC1: CHECK constraint rejects text > 10,000 chars."""
        oversized_text = "x" * 10_001
        petition_id = str(uuid4())

        with pytest.raises(Exception) as exc_info:
            await petition_schema.execute(
                text("""
                    INSERT INTO petition_submissions (id, type, text, state)
                    VALUES (:id, 'GENERAL', :text, 'RECEIVED')
                """),
                {"id": petition_id, "text": oversized_text},
            )
            await petition_schema.flush()

        # Should fail with constraint violation
        assert "petition_text_length" in str(exc_info.value).lower() or "check" in str(exc_info.value).lower()

    async def test_text_length_constraint_accepts_max(
        self, petition_schema: AsyncSession
    ) -> None:
        """AC1: CHECK constraint accepts text exactly at 10,000 chars."""
        max_text = "x" * 10_000
        petition_id = str(uuid4())

        await petition_schema.execute(
            text("""
                INSERT INTO petition_submissions (id, type, text, state)
                VALUES (:id, 'GENERAL', :text, 'RECEIVED')
            """),
            {"id": petition_id, "text": max_text},
        )
        await petition_schema.flush()

        # Verify inserted
        result = await petition_schema.execute(
            text("SELECT id FROM petition_submissions WHERE id = :id"),
            {"id": petition_id},
        )
        assert result.fetchone() is not None


@pytest.mark.integration
@pytest.mark.asyncio
class TestPetitionIndexes:
    """Test petition table indexes."""

    async def test_indexes_exist(self, petition_schema: AsyncSession) -> None:
        """AC1: Verify all required indexes exist."""
        result = await petition_schema.execute(
            text("""
                SELECT indexname
                FROM pg_indexes
                WHERE tablename = 'petition_submissions'
            """)
        )
        indexes = [row[0] for row in result.fetchall()]

        assert "idx_petition_submissions_state" in indexes
        assert "idx_petition_submissions_type" in indexes
        assert "idx_petition_submissions_realm" in indexes
        assert "idx_petition_submissions_created_at" in indexes


@pytest.mark.integration
@pytest.mark.asyncio
class TestPetitionTrigger:
    """Test petition table triggers."""

    async def test_updated_at_trigger_fires(self, petition_schema: AsyncSession) -> None:
        """AC1: updated_at trigger fires on update."""
        petition_id = str(uuid4())

        # Insert
        await petition_schema.execute(
            text("""
                INSERT INTO petition_submissions (id, type, text, state, realm)
                VALUES (:id, 'GENERAL', 'Test content', 'RECEIVED', 'default')
            """),
            {"id": petition_id},
        )
        await petition_schema.flush()

        # Get initial updated_at
        result = await petition_schema.execute(
            text("SELECT updated_at FROM petition_submissions WHERE id = :id"),
            {"id": petition_id},
        )
        initial_updated = result.fetchone()[0]

        # Small delay to ensure timestamp difference
        import asyncio
        await asyncio.sleep(0.01)

        # Update
        await petition_schema.execute(
            text("""
                UPDATE petition_submissions
                SET state = 'DELIBERATING'
                WHERE id = :id
            """),
            {"id": petition_id},
        )
        await petition_schema.flush()

        # Get new updated_at
        result = await petition_schema.execute(
            text("SELECT updated_at FROM petition_submissions WHERE id = :id"),
            {"id": petition_id},
        )
        new_updated = result.fetchone()[0]

        assert new_updated > initial_updated


@pytest.mark.integration
@pytest.mark.asyncio
class TestPetitionCRUD:
    """Test basic CRUD operations on petition_submissions."""

    async def test_insert_and_select(self, petition_schema: AsyncSession) -> None:
        """Can insert and retrieve a petition."""
        petition_id = str(uuid4())
        submitter_id = str(uuid4())
        content_hash = bytes(32)  # 32 zero bytes

        await petition_schema.execute(
            text("""
                INSERT INTO petition_submissions
                    (id, type, text, submitter_id, state, content_hash, realm)
                VALUES
                    (:id, 'CESSATION', 'Test petition', :submitter_id,
                     'RECEIVED', :content_hash, 'test-realm')
            """),
            {
                "id": petition_id,
                "submitter_id": submitter_id,
                "content_hash": content_hash,
            },
        )
        await petition_schema.flush()

        result = await petition_schema.execute(
            text("""
                SELECT id, type, text, submitter_id, state, content_hash, realm
                FROM petition_submissions
                WHERE id = :id
            """),
            {"id": petition_id},
        )
        row = result.fetchone()

        assert row is not None
        assert str(row[0]) == petition_id
        assert row[1] == "CESSATION"
        assert row[2] == "Test petition"
        assert str(row[3]) == submitter_id
        assert row[4] == "RECEIVED"
        assert bytes(row[5]) == content_hash
        assert row[6] == "test-realm"

    async def test_state_update(self, petition_schema: AsyncSession) -> None:
        """Can update petition state."""
        petition_id = str(uuid4())

        await petition_schema.execute(
            text("""
                INSERT INTO petition_submissions (id, type, text, state)
                VALUES (:id, 'GENERAL', 'Test', 'RECEIVED')
            """),
            {"id": petition_id},
        )
        await petition_schema.flush()

        await petition_schema.execute(
            text("""
                UPDATE petition_submissions
                SET state = 'ESCALATED'
                WHERE id = :id
            """),
            {"id": petition_id},
        )
        await petition_schema.flush()

        result = await petition_schema.execute(
            text("SELECT state FROM petition_submissions WHERE id = :id"),
            {"id": petition_id},
        )
        state = result.fetchone()[0]

        assert state == "ESCALATED"

    async def test_default_values(self, petition_schema: AsyncSession) -> None:
        """Default values are applied correctly."""
        petition_id = str(uuid4())

        await petition_schema.execute(
            text("""
                INSERT INTO petition_submissions (id, type, text)
                VALUES (:id, 'GENERAL', 'Test')
            """),
            {"id": petition_id},
        )
        await petition_schema.flush()

        result = await petition_schema.execute(
            text("""
                SELECT state, realm, created_at, updated_at
                FROM petition_submissions
                WHERE id = :id
            """),
            {"id": petition_id},
        )
        row = result.fetchone()

        assert row[0] == "RECEIVED"  # default state
        assert row[1] == "default"  # default realm
        assert row[2] is not None  # created_at set
        assert row[3] is not None  # updated_at set
