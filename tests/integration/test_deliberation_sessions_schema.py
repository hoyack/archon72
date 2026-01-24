"""Integration tests for deliberation_sessions schema (Story 2A.1, FR-11.1, FR-11.4).

Tests:
- Migration 017 creates deliberation_sessions table with correct schema
- ENUM types created correctly (deliberation_phase, deliberation_outcome)
- Domain invariant constraints enforced at DB level (FR-11.1, AT-6)
- Indexes exist for query patterns (NFR-10.5)
- Foreign key to petition_submissions (one session per petition)

Requires Docker for testcontainers PostgreSQL.
"""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.integration.sql_helpers import execute_sql_file
# Path to migration files
PETITION_MIGRATION_FILE = (
    Path(__file__).parent.parent.parent
    / "migrations"
    / "012_create_petition_submissions.sql"
)
DELIBERATION_MIGRATION_FILE = (
    Path(__file__).parent.parent.parent
    / "migrations"
    / "017_create_deliberation_sessions.sql"
)


@pytest.fixture
async def deliberation_schema(db_session: AsyncSession) -> AsyncSession:
    """Apply migrations and return session with schema ready.

    Applies both petition_submissions and deliberation_sessions migrations
    since deliberation_sessions has a foreign key to petition_submissions.
    """
    # First apply petition_submissions migration (required for FK)
    await execute_sql_file(db_session, PETITION_MIGRATION_FILE)

    # Then apply deliberation_sessions migration
    await execute_sql_file(db_session, DELIBERATION_MIGRATION_FILE)

    await db_session.flush()
    return db_session


@pytest.fixture
def sample_petition_id(deliberation_schema: AsyncSession) -> str:
    """Return a petition ID string for use in tests."""
    return str(uuid4())


@pytest.fixture
async def inserted_petition(deliberation_schema: AsyncSession) -> str:
    """Insert a test petition and return its ID."""
    petition_id = str(uuid4())
    await deliberation_schema.execute(
        text("""
            INSERT INTO petition_submissions (id, type, text, state, realm)
            VALUES (:id, 'GENERAL', 'Test petition for deliberation', 'RECEIVED', 'default')
        """),
        {"id": petition_id},
    )
    await deliberation_schema.flush()
    return petition_id


# =============================================================================
# Table Structure Tests
# =============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
class TestDeliberationSessionsTable:
    """Test deliberation_sessions table structure."""

    async def test_table_exists(self, deliberation_schema: AsyncSession) -> None:
        """AC1: Verify deliberation_sessions table was created."""
        result = await deliberation_schema.execute(
            text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = 'deliberation_sessions'
                )
            """)
        )
        exists = result.scalar()
        assert exists is True

    async def test_table_columns(self, deliberation_schema: AsyncSession) -> None:
        """AC1: Verify all required columns exist with correct types."""
        result = await deliberation_schema.execute(
            text("""
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns
                WHERE table_name = 'deliberation_sessions'
                ORDER BY ordinal_position
            """)
        )
        columns = {
            row[0]: {"type": row[1], "nullable": row[2], "default": row[3]}
            for row in result.fetchall()
        }

        # Verify expected columns
        assert "session_id" in columns
        assert columns["session_id"]["type"] == "uuid"
        assert columns["session_id"]["nullable"] == "NO"

        assert "petition_id" in columns
        assert columns["petition_id"]["type"] == "uuid"
        assert columns["petition_id"]["nullable"] == "NO"

        assert "assigned_archons" in columns
        assert "ARRAY" in columns["assigned_archons"]["type"]
        assert columns["assigned_archons"]["nullable"] == "NO"

        assert "phase" in columns
        assert columns["phase"]["type"] == "USER-DEFINED"  # enum
        assert columns["phase"]["nullable"] == "NO"

        assert "phase_transcripts" in columns
        assert columns["phase_transcripts"]["type"] == "jsonb"

        assert "votes" in columns
        assert columns["votes"]["type"] == "jsonb"

        assert "outcome" in columns
        assert columns["outcome"]["type"] == "USER-DEFINED"  # enum
        assert columns["outcome"]["nullable"] == "YES"  # null until resolved

        assert "dissent_archon_id" in columns
        assert columns["dissent_archon_id"]["type"] == "uuid"
        assert columns["dissent_archon_id"]["nullable"] == "YES"

        assert "created_at" in columns
        assert columns["created_at"]["nullable"] == "NO"

        assert "completed_at" in columns
        assert columns["completed_at"]["nullable"] == "YES"

        assert "version" in columns
        assert columns["version"]["type"] == "integer"
        assert columns["version"]["nullable"] == "NO"


# =============================================================================
# Enum Tests
# =============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
class TestDeliberationEnums:
    """Test deliberation enum types."""

    async def test_deliberation_phase_enum_values(
        self, deliberation_schema: AsyncSession
    ) -> None:
        """FR-11.4: Verify deliberation_phase enum has all expected values."""
        result = await deliberation_schema.execute(
            text("""
                SELECT unnest(enum_range(NULL::deliberation_phase))::text
            """)
        )
        values = [row[0] for row in result.fetchall()]

        assert "ASSESS" in values
        assert "POSITION" in values
        assert "CROSS_EXAMINE" in values
        assert "VOTE" in values
        assert "COMPLETE" in values
        assert len(values) == 5

    async def test_deliberation_outcome_enum_values(
        self, deliberation_schema: AsyncSession
    ) -> None:
        """AT-1: Verify deliberation_outcome enum has expected values."""
        result = await deliberation_schema.execute(
            text("""
                SELECT unnest(enum_range(NULL::deliberation_outcome))::text
            """)
        )
        values = [row[0] for row in result.fetchall()]

        assert "ACKNOWLEDGE" in values
        assert "REFER" in values
        assert "ESCALATE" in values
        assert "DEFER" in values
        assert "NO_RESPONSE" in values
        assert len(values) == 5


# =============================================================================
# Constraint Tests (FR-11.1, AT-6)
# =============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
class TestDeliberationConstraints:
    """Test deliberation table constraints (domain invariants)."""

    async def test_exactly_3_archons_constraint_rejects_2(
        self, deliberation_schema: AsyncSession, inserted_petition: str
    ) -> None:
        """FR-11.1: CHECK constraint rejects fewer than 3 archons."""
        session_id = str(uuid4())
        archon1 = str(uuid4())
        archon2 = str(uuid4())

        with pytest.raises(Exception) as exc_info:
            await deliberation_schema.execute(
                text("""
                    INSERT INTO deliberation_sessions
                        (session_id, petition_id, assigned_archons)
                    VALUES
                        (:session_id, :petition_id, ARRAY[:a1, :a2]::uuid[])
                """),
                {
                    "session_id": session_id,
                    "petition_id": inserted_petition,
                    "a1": archon1,
                    "a2": archon2,
                },
            )
            await deliberation_schema.flush()

        # Should fail with constraint violation
        assert (
            "check_exactly_3_archons" in str(exc_info.value).lower()
            or "check" in str(exc_info.value).lower()
        )

    async def test_exactly_3_archons_constraint_rejects_4(
        self, deliberation_schema: AsyncSession, inserted_petition: str
    ) -> None:
        """FR-11.1: CHECK constraint rejects more than 3 archons."""
        session_id = str(uuid4())
        archons = [str(uuid4()) for _ in range(4)]

        with pytest.raises(Exception) as exc_info:
            await deliberation_schema.execute(
                text("""
                    INSERT INTO deliberation_sessions
                        (session_id, petition_id, assigned_archons)
                    VALUES
                        (:session_id, :petition_id, ARRAY[:a1, :a2, :a3, :a4]::uuid[])
                """),
                {
                    "session_id": session_id,
                    "petition_id": inserted_petition,
                    "a1": archons[0],
                    "a2": archons[1],
                    "a3": archons[2],
                    "a4": archons[3],
                },
            )
            await deliberation_schema.flush()

        # Should fail with constraint violation
        assert "check" in str(exc_info.value).lower()

    async def test_unique_archons_constraint_rejects_duplicates(
        self, deliberation_schema: AsyncSession, inserted_petition: str
    ) -> None:
        """FR-11.1: CHECK constraint rejects duplicate archon IDs."""
        session_id = str(uuid4())
        archon1 = str(uuid4())
        archon2 = str(uuid4())

        with pytest.raises(Exception) as exc_info:
            await deliberation_schema.execute(
                text("""
                    INSERT INTO deliberation_sessions
                        (session_id, petition_id, assigned_archons)
                    VALUES
                        (:session_id, :petition_id, ARRAY[:a1, :a2, :a1]::uuid[])
                """),
                {
                    "session_id": session_id,
                    "petition_id": inserted_petition,
                    "a1": archon1,  # Duplicate
                    "a2": archon2,
                },
            )
            await deliberation_schema.flush()

        # Should fail with constraint violation
        assert (
            "check_unique_archons" in str(exc_info.value).lower()
            or "check" in str(exc_info.value).lower()
        )

    async def test_completed_has_outcome_constraint(
        self, deliberation_schema: AsyncSession, inserted_petition: str
    ) -> None:
        """FR-11.4: Completed sessions must have outcome."""
        session_id = str(uuid4())
        archons = [str(uuid4()) for _ in range(3)]

        with pytest.raises(Exception) as exc_info:
            await deliberation_schema.execute(
                text("""
                    INSERT INTO deliberation_sessions
                        (session_id, petition_id, assigned_archons, phase, outcome)
                    VALUES
                        (:session_id, :petition_id, ARRAY[:a1, :a2, :a3]::uuid[], 'COMPLETE', NULL)
                """),
                {
                    "session_id": session_id,
                    "petition_id": inserted_petition,
                    "a1": archons[0],
                    "a2": archons[1],
                    "a3": archons[2],
                },
            )
            await deliberation_schema.flush()

        # Should fail with constraint violation
        assert (
            "check_completed_has_outcome" in str(exc_info.value).lower()
            or "check" in str(exc_info.value).lower()
        )

    async def test_completed_has_timestamp_constraint(
        self, deliberation_schema: AsyncSession, inserted_petition: str
    ) -> None:
        """FR-11.4: Completed sessions must have completed_at timestamp."""
        session_id = str(uuid4())
        archons = [str(uuid4()) for _ in range(3)]

        with pytest.raises(Exception) as exc_info:
            await deliberation_schema.execute(
                text("""
                    INSERT INTO deliberation_sessions
                        (session_id, petition_id, assigned_archons, phase, outcome, completed_at)
                    VALUES
                        (:session_id, :petition_id, ARRAY[:a1, :a2, :a3]::uuid[],
                         'COMPLETE', 'ACKNOWLEDGE', NULL)
                """),
                {
                    "session_id": session_id,
                    "petition_id": inserted_petition,
                    "a1": archons[0],
                    "a2": archons[1],
                    "a3": archons[2],
                },
            )
            await deliberation_schema.flush()

        # Should fail with constraint violation
        assert "check" in str(exc_info.value).lower()

    async def test_version_positive_constraint(
        self, deliberation_schema: AsyncSession, inserted_petition: str
    ) -> None:
        """NFR-3.2: Version must be positive."""
        session_id = str(uuid4())
        archons = [str(uuid4()) for _ in range(3)]

        with pytest.raises(Exception) as exc_info:
            await deliberation_schema.execute(
                text("""
                    INSERT INTO deliberation_sessions
                        (session_id, petition_id, assigned_archons, version)
                    VALUES
                        (:session_id, :petition_id, ARRAY[:a1, :a2, :a3]::uuid[], 0)
                """),
                {
                    "session_id": session_id,
                    "petition_id": inserted_petition,
                    "a1": archons[0],
                    "a2": archons[1],
                    "a3": archons[2],
                },
            )
            await deliberation_schema.flush()

        # Should fail with constraint violation
        assert (
            "check_version_positive" in str(exc_info.value).lower()
            or "check" in str(exc_info.value).lower()
        )

    async def test_one_session_per_petition_constraint(
        self, deliberation_schema: AsyncSession, inserted_petition: str
    ) -> None:
        """FR-11.1: Only one deliberation session per petition."""
        session1_id = str(uuid4())
        session2_id = str(uuid4())
        archons = [str(uuid4()) for _ in range(3)]

        # Insert first session
        await deliberation_schema.execute(
            text("""
                INSERT INTO deliberation_sessions
                    (session_id, petition_id, assigned_archons)
                VALUES
                    (:session_id, :petition_id, ARRAY[:a1, :a2, :a3]::uuid[])
            """),
            {
                "session_id": session1_id,
                "petition_id": inserted_petition,
                "a1": archons[0],
                "a2": archons[1],
                "a3": archons[2],
            },
        )
        await deliberation_schema.flush()

        # Try to insert second session for same petition
        with pytest.raises(Exception) as exc_info:
            await deliberation_schema.execute(
                text("""
                    INSERT INTO deliberation_sessions
                        (session_id, petition_id, assigned_archons)
                    VALUES
                        (:session_id, :petition_id, ARRAY[:a1, :a2, :a3]::uuid[])
                """),
                {
                    "session_id": session2_id,
                    "petition_id": inserted_petition,
                    "a1": archons[0],
                    "a2": archons[1],
                    "a3": archons[2],
                },
            )
            await deliberation_schema.flush()

        # Should fail with unique constraint violation
        assert (
            "unique" in str(exc_info.value).lower()
            or "duplicate" in str(exc_info.value).lower()
        )


# =============================================================================
# Index Tests (NFR-10.5)
# =============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
class TestDeliberationIndexes:
    """Test deliberation table indexes (NFR-10.5: 100+ concurrent sessions)."""

    async def test_indexes_exist(self, deliberation_schema: AsyncSession) -> None:
        """NFR-10.5: Verify all required indexes exist."""
        result = await deliberation_schema.execute(
            text("""
                SELECT indexname
                FROM pg_indexes
                WHERE tablename = 'deliberation_sessions'
            """)
        )
        indexes = [row[0] for row in result.fetchall()]

        # Primary key index (auto-created)
        assert "deliberation_sessions_pkey" in indexes

        # Active sessions by phase index
        assert "idx_deliberation_sessions_phase_active" in indexes

        # Created at index (for timeout detection)
        assert "idx_deliberation_sessions_created_at" in indexes

        # Incomplete sessions by created_at (for timeout queries)
        assert "idx_deliberation_sessions_incomplete_created" in indexes

        # Archon lookup indexes
        assert "idx_deliberation_sessions_archon1" in indexes
        assert "idx_deliberation_sessions_archon2" in indexes
        assert "idx_deliberation_sessions_archon3" in indexes


# =============================================================================
# Foreign Key Tests
# =============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
class TestDeliberationForeignKey:
    """Test foreign key to petition_submissions."""

    async def test_fk_rejects_invalid_petition(
        self, deliberation_schema: AsyncSession
    ) -> None:
        """FK constraint rejects non-existent petition_id."""
        session_id = str(uuid4())
        fake_petition_id = str(uuid4())  # Does not exist
        archons = [str(uuid4()) for _ in range(3)]

        with pytest.raises(Exception) as exc_info:
            await deliberation_schema.execute(
                text("""
                    INSERT INTO deliberation_sessions
                        (session_id, petition_id, assigned_archons)
                    VALUES
                        (:session_id, :petition_id, ARRAY[:a1, :a2, :a3]::uuid[])
                """),
                {
                    "session_id": session_id,
                    "petition_id": fake_petition_id,
                    "a1": archons[0],
                    "a2": archons[1],
                    "a3": archons[2],
                },
            )
            await deliberation_schema.flush()

        # Should fail with FK violation
        assert (
            "foreign key" in str(exc_info.value).lower()
            or "fk" in str(exc_info.value).lower()
            or "reference" in str(exc_info.value).lower()
        )


# =============================================================================
# CRUD Tests
# =============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
class TestDeliberationCRUD:
    """Test basic CRUD operations on deliberation_sessions."""

    async def test_insert_and_select_session(
        self, deliberation_schema: AsyncSession, inserted_petition: str
    ) -> None:
        """Can insert and retrieve a deliberation session."""
        session_id = str(uuid4())
        archons = [str(uuid4()) for _ in range(3)]

        await deliberation_schema.execute(
            text("""
                INSERT INTO deliberation_sessions
                    (session_id, petition_id, assigned_archons)
                VALUES
                    (:session_id, :petition_id, ARRAY[:a1, :a2, :a3]::uuid[])
            """),
            {
                "session_id": session_id,
                "petition_id": inserted_petition,
                "a1": archons[0],
                "a2": archons[1],
                "a3": archons[2],
            },
        )
        await deliberation_schema.flush()

        result = await deliberation_schema.execute(
            text("""
                SELECT session_id, petition_id, assigned_archons, phase, version
                FROM deliberation_sessions
                WHERE session_id = :session_id
            """),
            {"session_id": session_id},
        )
        row = result.fetchone()

        assert row is not None
        assert str(row[0]) == session_id
        assert str(row[1]) == inserted_petition
        assert len(row[2]) == 3  # 3 archons
        assert row[3] == "ASSESS"  # default phase
        assert row[4] == 1  # default version

    async def test_phase_update(
        self, deliberation_schema: AsyncSession, inserted_petition: str
    ) -> None:
        """Can update session phase."""
        session_id = str(uuid4())
        archons = [str(uuid4()) for _ in range(3)]

        await deliberation_schema.execute(
            text("""
                INSERT INTO deliberation_sessions
                    (session_id, petition_id, assigned_archons)
                VALUES
                    (:session_id, :petition_id, ARRAY[:a1, :a2, :a3]::uuid[])
            """),
            {
                "session_id": session_id,
                "petition_id": inserted_petition,
                "a1": archons[0],
                "a2": archons[1],
                "a3": archons[2],
            },
        )
        await deliberation_schema.flush()

        await deliberation_schema.execute(
            text("""
                UPDATE deliberation_sessions
                SET phase = 'POSITION', version = version + 1
                WHERE session_id = :session_id
            """),
            {"session_id": session_id},
        )
        await deliberation_schema.flush()

        result = await deliberation_schema.execute(
            text(
                "SELECT phase, version FROM deliberation_sessions WHERE session_id = :session_id"
            ),
            {"session_id": session_id},
        )
        row = result.fetchone()

        assert row[0] == "POSITION"
        assert row[1] == 2

    async def test_complete_session_with_outcome(
        self, deliberation_schema: AsyncSession, inserted_petition: str
    ) -> None:
        """Can complete a session with outcome, votes, and completed_at."""
        session_id = str(uuid4())
        archons = [str(uuid4()) for _ in range(3)]
        votes_json = {
            archons[0]: "ACKNOWLEDGE",
            archons[1]: "ACKNOWLEDGE",
            archons[2]: "REFER",
        }

        await deliberation_schema.execute(
            text("""
                INSERT INTO deliberation_sessions
                    (session_id, petition_id, assigned_archons, phase, votes, outcome,
                     dissent_archon_id, completed_at)
                VALUES
                    (:session_id, :petition_id, ARRAY[:a1, :a2, :a3]::uuid[],
                     'COMPLETE', :votes, 'ACKNOWLEDGE', :dissent_id, NOW())
            """),
            {
                "session_id": session_id,
                "petition_id": inserted_petition,
                "a1": archons[0],
                "a2": archons[1],
                "a3": archons[2],
                "votes": str(votes_json).replace("'", '"'),  # JSON format
                "dissent_id": archons[2],
            },
        )
        await deliberation_schema.flush()

        result = await deliberation_schema.execute(
            text("""
                SELECT phase, outcome, dissent_archon_id, completed_at
                FROM deliberation_sessions
                WHERE session_id = :session_id
            """),
            {"session_id": session_id},
        )
        row = result.fetchone()

        assert row[0] == "COMPLETE"
        assert row[1] == "ACKNOWLEDGE"
        assert str(row[2]) == archons[2]  # Dissenter
        assert row[3] is not None  # completed_at set

    async def test_default_values(
        self, deliberation_schema: AsyncSession, inserted_petition: str
    ) -> None:
        """Default values are applied correctly."""
        session_id = str(uuid4())
        archons = [str(uuid4()) for _ in range(3)]

        await deliberation_schema.execute(
            text("""
                INSERT INTO deliberation_sessions
                    (session_id, petition_id, assigned_archons)
                VALUES
                    (:session_id, :petition_id, ARRAY[:a1, :a2, :a3]::uuid[])
            """),
            {
                "session_id": session_id,
                "petition_id": inserted_petition,
                "a1": archons[0],
                "a2": archons[1],
                "a3": archons[2],
            },
        )
        await deliberation_schema.flush()

        result = await deliberation_schema.execute(
            text("""
                SELECT phase, phase_transcripts, votes, outcome,
                       dissent_archon_id, created_at, completed_at, version
                FROM deliberation_sessions
                WHERE session_id = :session_id
            """),
            {"session_id": session_id},
        )
        row = result.fetchone()

        assert row[0] == "ASSESS"  # default phase
        assert row[1] == {}  # default empty JSONB
        assert row[2] == {}  # default empty JSONB
        assert row[3] is None  # outcome null until resolved
        assert row[4] is None  # no dissenter
        assert row[5] is not None  # created_at set
        assert row[6] is None  # completed_at null
        assert row[7] == 1  # default version
