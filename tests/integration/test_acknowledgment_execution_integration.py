"""Integration tests for Acknowledgment Execution.

Story: 3.2 - Acknowledgment Execution Service
FR-3.1: Marquis SHALL be able to ACKNOWLEDGE petition with reason code
CT-12: Every action that affects an Archon must be witnessed
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.domain.models.acknowledgment_reason import AcknowledgmentReasonCode


class TestAcknowledgmentsTableIntegration:
    """Integration tests for acknowledgments table."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_table_exists(self, db_connection) -> None:
        """Verify acknowledgments table exists in database."""
        query = """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_name = 'acknowledgments'
            )
        """
        result = await db_connection.fetchval(query)
        assert result is True, "acknowledgments table should exist"

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_required_columns_exist(self, db_connection) -> None:
        """Verify all required columns exist."""
        query = """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'acknowledgments'
        """
        rows = await db_connection.fetch(query)
        columns = {row["column_name"] for row in rows}

        required_columns = {
            "id",
            "petition_id",
            "reason_code",
            "rationale",
            "reference_petition_id",
            "acknowledging_archon_ids",
            "acknowledged_at",
            "witness_hash",
            "created_at",
        }

        missing = required_columns - columns
        assert not missing, f"Missing columns: {missing}"

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_reason_code_uses_enum(self, db_connection) -> None:
        """Verify reason_code column uses acknowledgment_reason_enum type."""
        query = """
            SELECT data_type, udt_name
            FROM information_schema.columns
            WHERE table_name = 'acknowledgments'
            AND column_name = 'reason_code'
        """
        result = await db_connection.fetchrow(query)
        assert result is not None
        assert result["udt_name"] == "acknowledgment_reason_enum"


class TestConstraintsIntegration:
    """Integration tests for database constraints."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_minimum_archons_constraint(self, db_connection) -> None:
        """Verify ck_acknowledgments_min_archons constraint exists."""
        query = """
            SELECT constraint_name
            FROM information_schema.table_constraints
            WHERE table_name = 'acknowledgments'
            AND constraint_type = 'CHECK'
        """
        rows = await db_connection.fetch(query)
        constraint_names = {row["constraint_name"] for row in rows}

        assert "ck_acknowledgments_min_archons" in constraint_names

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_rationale_required_constraint(self, db_connection) -> None:
        """Verify ck_acknowledgments_rationale_required constraint exists."""
        query = """
            SELECT constraint_name
            FROM information_schema.table_constraints
            WHERE table_name = 'acknowledgments'
            AND constraint_type = 'CHECK'
        """
        rows = await db_connection.fetch(query)
        constraint_names = {row["constraint_name"] for row in rows}

        assert "ck_acknowledgments_rationale_required" in constraint_names

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_reference_required_constraint(self, db_connection) -> None:
        """Verify ck_acknowledgments_reference_required constraint exists."""
        query = """
            SELECT constraint_name
            FROM information_schema.table_constraints
            WHERE table_name = 'acknowledgments'
            AND constraint_type = 'CHECK'
        """
        rows = await db_connection.fetch(query)
        constraint_names = {row["constraint_name"] for row in rows}

        assert "ck_acknowledgments_reference_required" in constraint_names

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_unique_petition_constraint(self, db_connection) -> None:
        """Verify uq_acknowledgments_petition unique constraint exists."""
        query = """
            SELECT constraint_name
            FROM information_schema.table_constraints
            WHERE table_name = 'acknowledgments'
            AND constraint_type = 'UNIQUE'
        """
        rows = await db_connection.fetch(query)
        constraint_names = {row["constraint_name"] for row in rows}

        assert "uq_acknowledgments_petition" in constraint_names


class TestIndexesIntegration:
    """Integration tests for database indexes."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_reason_code_index_exists(self, db_connection) -> None:
        """Verify index on reason_code exists."""
        query = """
            SELECT indexname
            FROM pg_indexes
            WHERE tablename = 'acknowledgments'
            AND indexname = 'idx_acknowledgments_reason_code'
        """
        result = await db_connection.fetchrow(query)
        assert result is not None

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_acknowledged_at_index_exists(self, db_connection) -> None:
        """Verify index on acknowledged_at exists."""
        query = """
            SELECT indexname
            FROM pg_indexes
            WHERE tablename = 'acknowledgments'
            AND indexname = 'idx_acknowledgments_acknowledged_at'
        """
        result = await db_connection.fetchrow(query)
        assert result is not None


class TestAcknowledgmentPersistenceIntegration:
    """Integration tests for acknowledgment persistence."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_insert_valid_noted_acknowledgment(
        self, db_connection, test_petition_id
    ) -> None:
        """Successfully insert NOTED acknowledgment."""
        ack_id = uuid4()
        query = """
            INSERT INTO acknowledgments (
                id, petition_id, reason_code, acknowledging_archon_ids,
                acknowledged_at, witness_hash
            ) VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING id
        """
        result = await db_connection.fetchval(
            query,
            ack_id,
            test_petition_id,
            "NOTED",
            [15, 42],
            datetime.now(timezone.utc),
            "blake3:test123",
        )
        assert result == ack_id

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_insert_refused_without_rationale_fails(
        self, db_connection, test_petition_id
    ) -> None:
        """REFUSED without rationale fails constraint."""
        query = """
            INSERT INTO acknowledgments (
                id, petition_id, reason_code, acknowledging_archon_ids,
                acknowledged_at, witness_hash, rationale
            ) VALUES ($1, $2, $3, $4, $5, $6, NULL)
        """
        with pytest.raises(Exception) as exc_info:
            await db_connection.execute(
                query,
                uuid4(),
                test_petition_id,
                "REFUSED",
                [15, 42],
                datetime.now(timezone.utc),
                "blake3:test123",
            )
        assert "ck_acknowledgments_rationale_required" in str(exc_info.value)

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_insert_refused_with_rationale_succeeds(
        self, db_connection, test_petition_id
    ) -> None:
        """REFUSED with rationale succeeds."""
        ack_id = uuid4()
        query = """
            INSERT INTO acknowledgments (
                id, petition_id, reason_code, acknowledging_archon_ids,
                acknowledged_at, witness_hash, rationale
            ) VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING id
        """
        result = await db_connection.fetchval(
            query,
            ack_id,
            test_petition_id,
            "REFUSED",
            [15, 42],
            datetime.now(timezone.utc),
            "blake3:test123",
            "Violates community guidelines",
        )
        assert result == ack_id

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_insert_duplicate_without_reference_fails(
        self, db_connection, test_petition_id
    ) -> None:
        """DUPLICATE without reference_petition_id fails constraint."""
        query = """
            INSERT INTO acknowledgments (
                id, petition_id, reason_code, acknowledging_archon_ids,
                acknowledged_at, witness_hash, reference_petition_id
            ) VALUES ($1, $2, $3, $4, $5, $6, NULL)
        """
        with pytest.raises(Exception) as exc_info:
            await db_connection.execute(
                query,
                uuid4(),
                test_petition_id,
                "DUPLICATE",
                [15, 42],
                datetime.now(timezone.utc),
                "blake3:test123",
            )
        assert "ck_acknowledgments_reference_required" in str(exc_info.value)

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_insert_single_archon_fails(
        self, db_connection, test_petition_id
    ) -> None:
        """Single archon fails minimum archon constraint."""
        query = """
            INSERT INTO acknowledgments (
                id, petition_id, reason_code, acknowledging_archon_ids,
                acknowledged_at, witness_hash
            ) VALUES ($1, $2, $3, $4, $5, $6)
        """
        with pytest.raises(Exception) as exc_info:
            await db_connection.execute(
                query,
                uuid4(),
                test_petition_id,
                "NOTED",
                [15],  # Only 1 archon
                datetime.now(timezone.utc),
                "blake3:test123",
            )
        assert "ck_acknowledgments_min_archons" in str(exc_info.value)


class TestForeignKeyIntegration:
    """Integration tests for foreign key relationships."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_petition_foreign_key_exists(self, db_connection) -> None:
        """Verify foreign key to petition_submissions exists."""
        query = """
            SELECT constraint_name
            FROM information_schema.table_constraints
            WHERE table_name = 'acknowledgments'
            AND constraint_type = 'FOREIGN KEY'
        """
        rows = await db_connection.fetch(query)
        constraint_names = {row["constraint_name"] for row in rows}

        # Should have FK to petition_submissions for both petition_id and reference_petition_id
        assert len(constraint_names) >= 1


@pytest.fixture
async def test_petition_id(db_connection):
    """Create a test petition and return its ID."""
    # Check if petition_submissions table exists
    table_exists = await db_connection.fetchval("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_name = 'petition_submissions'
        )
    """)

    if not table_exists:
        pytest.skip("petition_submissions table not available")

    # Create a test petition
    petition_id = uuid4()
    try:
        await db_connection.execute(
            """
            INSERT INTO petition_submissions (
                id, petition_type_id, submitter_id, content_hash,
                realm_id, state, submitted_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7)
            """,
            petition_id,
            "STANDARD",
            uuid4(),
            "blake3:test",
            "TECH",
            "DELIBERATING",
            datetime.now(timezone.utc),
        )
    except Exception:
        pytest.skip("Could not create test petition")

    yield petition_id

    # Cleanup
    try:
        await db_connection.execute(
            "DELETE FROM acknowledgments WHERE petition_id = $1", petition_id
        )
        await db_connection.execute(
            "DELETE FROM petition_submissions WHERE id = $1", petition_id
        )
    except Exception:
        pass


class TestDwellTimeIntegration:
    """Integration tests for minimum dwell time enforcement (FR-3.5, Story 3.5).

    FR-3.5: System SHALL enforce minimum dwell time before ACKNOWLEDGE
    to ensure petitions receive adequate deliberation time.
    """

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_dwell_time_error_attributes(self) -> None:
        """DwellTimeNotElapsedError includes all required context."""
        from datetime import timedelta

        from src.domain.errors.acknowledgment import DwellTimeNotElapsedError

        petition_id = uuid4()
        started_at = datetime.now(timezone.utc) - timedelta(seconds=10)

        error = DwellTimeNotElapsedError(
            petition_id=petition_id,
            deliberation_started_at=started_at,
            min_dwell_seconds=30,
            elapsed_seconds=10.5,
        )

        assert error.petition_id == petition_id
        assert error.deliberation_started_at == started_at
        assert error.min_dwell_seconds == 30
        assert error.elapsed_seconds == 10.5
        assert error.remaining_seconds == pytest.approx(19.5, rel=0.1)
        assert error.remaining_timedelta.total_seconds() == pytest.approx(19.5, rel=0.1)

        # Verify message includes FR-3.5 reference
        assert "FR-3.5" in str(error)

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_session_not_found_error_attributes(self) -> None:
        """DeliberationSessionNotFoundError includes petition context."""
        from src.domain.errors.acknowledgment import DeliberationSessionNotFoundError

        petition_id = uuid4()

        error = DeliberationSessionNotFoundError(petition_id=petition_id)

        assert error.petition_id == petition_id
        assert "DELIBERATING" in str(error)
        assert "inconsistent state" in str(error).lower()

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_dwell_config_environment_override(self) -> None:
        """DeliberationConfig reads dwell time from environment."""
        import os

        from src.config.deliberation_config import DeliberationConfig

        # Set environment variable
        original = os.environ.get("MIN_DWELL_TIME_SECONDS")
        try:
            os.environ["MIN_DWELL_TIME_SECONDS"] = "60"
            config = DeliberationConfig.from_environment()
            assert config.min_dwell_seconds == 60
        finally:
            if original is not None:
                os.environ["MIN_DWELL_TIME_SECONDS"] = original
            else:
                os.environ.pop("MIN_DWELL_TIME_SECONDS", None)

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_dwell_config_clamps_to_valid_range(self) -> None:
        """DeliberationConfig clamps out-of-range dwell time values."""
        import os

        from src.config.deliberation_config import (
            MAX_DWELL_TIME_SECONDS,
            MIN_DWELL_TIME_FLOOR_SECONDS,
            DeliberationConfig,
        )

        original = os.environ.get("MIN_DWELL_TIME_SECONDS")
        try:
            # Test below floor
            os.environ["MIN_DWELL_TIME_SECONDS"] = "-10"
            config = DeliberationConfig.from_environment()
            assert config.min_dwell_seconds == MIN_DWELL_TIME_FLOOR_SECONDS

            # Test above ceiling
            os.environ["MIN_DWELL_TIME_SECONDS"] = "9999"
            config = DeliberationConfig.from_environment()
            assert config.min_dwell_seconds == MAX_DWELL_TIME_SECONDS
        finally:
            if original is not None:
                os.environ["MIN_DWELL_TIME_SECONDS"] = original
            else:
                os.environ.pop("MIN_DWELL_TIME_SECONDS", None)

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_dwell_timedelta_property(self) -> None:
        """dwell_timedelta property returns correct timedelta."""
        from datetime import timedelta

        from src.config.deliberation_config import DeliberationConfig

        config = DeliberationConfig(
            min_dwell_seconds=45,
            timeout_seconds=300,
            max_rounds=3,
        )

        assert config.dwell_timedelta == timedelta(seconds=45)

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_predefined_configs(self) -> None:
        """Verify predefined config constants are set correctly."""
        from src.config.deliberation_config import (
            DEFAULT_DELIBERATION_CONFIG,
            DEFAULT_MIN_DWELL_TIME_SECONDS,
            NO_DWELL_CONFIG,
            TEST_DELIBERATION_CONFIG,
        )

        # Default config has standard dwell time
        assert DEFAULT_DELIBERATION_CONFIG.min_dwell_seconds == DEFAULT_MIN_DWELL_TIME_SECONDS

        # Test config has zero dwell time
        assert TEST_DELIBERATION_CONFIG.min_dwell_seconds == 0

        # No dwell config explicitly has zero dwell time
        assert NO_DWELL_CONFIG.min_dwell_seconds == 0

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_stub_dwell_time_enforcement(self) -> None:
        """Integration test for stub with dwell time enforcement."""
        from datetime import timedelta

        from src.config.deliberation_config import DeliberationConfig
        from src.domain.errors.acknowledgment import DwellTimeNotElapsedError
        from src.domain.models.acknowledgment_reason import AcknowledgmentReasonCode
        from src.domain.models.deliberation_session import DeliberationSession
        from src.domain.models.petition_submission import PetitionState, PetitionSubmission
        from src.infrastructure.stubs.acknowledgment_execution_stub import (
            AcknowledgmentExecutionStub,
        )

        config = DeliberationConfig(
            min_dwell_seconds=60,  # 60 second dwell time
            timeout_seconds=300,
            max_rounds=3,
        )

        stub = AcknowledgmentExecutionStub(config=config, enforce_dwell_time=True)

        # Create petition with recent session (dwell time not elapsed)
        petition = PetitionSubmission(
            id=uuid4(),
            petition_type_id="STANDARD",
            submitter_id=uuid4(),
            content_hash="blake3:integration_test",
            realm_id="TECH",
            state=PetitionState.DELIBERATING,
            submitted_at=datetime.now(timezone.utc),
        )

        session = DeliberationSession(
            id=uuid4(),
            petition_id=petition.id,
            archon_ids=(15, 42, 67),
            created_at=datetime.now(timezone.utc) - timedelta(seconds=10),  # Only 10 seconds ago
        )

        stub.add_petition(petition, session)

        # Should fail - dwell time not elapsed
        with pytest.raises(DwellTimeNotElapsedError) as exc_info:
            await stub.execute(
                petition_id=petition.id,
                reason_code=AcknowledgmentReasonCode.NOTED,
                acknowledging_archon_ids=(15, 42),
            )

        assert exc_info.value.remaining_seconds > 0

        # Now add old session
        old_session = DeliberationSession(
            id=uuid4(),
            petition_id=petition.id,
            archon_ids=(15, 42, 67),
            created_at=datetime.now(timezone.utc) - timedelta(seconds=120),  # 2 minutes ago
        )
        stub.add_session(petition.id, old_session)

        # Now should succeed
        ack = await stub.execute(
            petition_id=petition.id,
            reason_code=AcknowledgmentReasonCode.NOTED,
            acknowledging_archon_ids=(15, 42),
        )

        assert ack.petition_id == petition.id
        assert stub.was_executed(petition.id)
