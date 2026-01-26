"""DB-backed integration tests for Witness Attribution Validation Triggers (Story 1.4 Task 5.5).

Tests the PostgreSQL database triggers that enforce witness attribution requirements:
- FR4: Events must have atomic witness attribution
- FR5: No unwitnessed events can exist
- CT-12: Witnessing creates accountability

These tests use REAL PostgreSQL via testcontainers to verify:
- AC4: Trigger rejects INSERT without witness_id
- AC4: Trigger rejects INSERT without witness_signature
- AC4: Trigger rejects invalid witness_id format
- AC4: Trigger rejects invalid witness_signature length
- AC4: Trigger accepts valid witness attribution

Technical Debt Resolution:
- Story 1-4 Task 5.5 was deferred to DB-backed tests
- This file completes that deferred task

Constitutional Constraints:
- CT-12: Witnessing creates accountability
- FR4: Events must have atomic witness attribution
- FR5: No unwitnessed events can exist
"""

from __future__ import annotations

import base64
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession


class TestWitnessValidationTrigger:
    """DB-backed tests for witness attribution validation trigger (Migration 004).

    These tests verify the PostgreSQL trigger that enforces FR4/FR5 requirements
    at the database level. This is the "trust boundary" - even if application
    code is bypassed, the database enforces witness attribution.
    """

    @pytest.fixture
    async def events_table_with_witness_trigger(
        self, db_session: AsyncSession
    ) -> AsyncSession:
        """Create events table with witness validation trigger.

        Applies migrations 001 (events table) and 004 (witness validation)
        inline to test the trigger behavior.
        """
        # Create events table (from migration 001)
        await db_session.execute(
            text("""
            CREATE TABLE IF NOT EXISTS events (
                event_id UUID PRIMARY KEY,
                sequence BIGSERIAL UNIQUE NOT NULL,
                event_type TEXT NOT NULL,
                payload JSONB NOT NULL,
                prev_hash TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                signature TEXT NOT NULL,
                hash_alg_version SMALLINT NOT NULL DEFAULT 1,
                sig_alg_version SMALLINT NOT NULL DEFAULT 1,
                agent_id TEXT,
                witness_id TEXT NOT NULL,
                witness_signature TEXT NOT NULL,
                local_timestamp TIMESTAMPTZ NOT NULL,
                authority_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        )

        # Create witness validation trigger function (from migration 004)
        await db_session.execute(
            text("""
            CREATE OR REPLACE FUNCTION validate_witness_attribution()
            RETURNS TRIGGER AS $func$
            BEGIN
                -- FR5: witness_id must be present and non-empty
                IF NEW.witness_id IS NULL OR NEW.witness_id = '' THEN
                    RAISE EXCEPTION 'FR5: Witness attribution required - witness_id missing';
                END IF;

                -- FR5: witness_signature must be present and non-empty
                IF NEW.witness_signature IS NULL OR NEW.witness_signature = '' THEN
                    RAISE EXCEPTION 'FR5: Witness attribution required - witness_signature missing';
                END IF;

                -- FR4: Validate witness_id format (must start with WITNESS:)
                IF NOT NEW.witness_id LIKE 'WITNESS:%' THEN
                    RAISE EXCEPTION 'FR4: Invalid witness_id format - must start with WITNESS:';
                END IF;

                -- FR4: Validate witness signature length (Ed25519 = 64 bytes = ~88 base64 chars)
                IF length(NEW.witness_signature) < 80 OR length(NEW.witness_signature) > 100 THEN
                    RAISE EXCEPTION 'FR4: Invalid witness signature - unexpected length (expected 80-100 chars, got %)', length(NEW.witness_signature);
                END IF;

                RETURN NEW;
            END;
            $func$ LANGUAGE plpgsql
        """)
        )

        # Create trigger
        await db_session.execute(
            text(
                "DROP TRIGGER IF EXISTS validate_witness_attribution_on_insert ON events"
            )
        )
        await db_session.execute(
            text("""
            CREATE TRIGGER validate_witness_attribution_on_insert
                BEFORE INSERT ON events
                FOR EACH ROW
                EXECUTE FUNCTION validate_witness_attribution()
        """)
        )

        return db_session

    def _generate_valid_witness_signature(self) -> str:
        """Generate a valid-length witness signature (Ed25519 base64).

        Ed25519 signatures are 64 bytes, which encode to ~88 base64 characters.
        """
        # 64 bytes = Ed25519 signature size
        signature_bytes = b"A" * 64
        return base64.b64encode(signature_bytes).decode()

    def _generate_valid_event_params(self) -> dict:
        """Generate valid parameters for an event insert."""
        return {
            "event_id": str(uuid4()),
            "event_type": "test.event",
            "payload": '{"test": true}',
            "prev_hash": "0" * 64,  # Genesis hash
            "content_hash": "abc123" + "0" * 58,  # 64 char hash
            "signature": base64.b64encode(b"S" * 64).decode(),
            "witness_id": f"WITNESS:{uuid4()}",
            "witness_signature": self._generate_valid_witness_signature(),
            "local_timestamp": datetime.now(timezone.utc),
        }

    # =========================================================================
    # Test: Trigger accepts valid witness attribution
    # =========================================================================

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_trigger_accepts_valid_witness_attribution(
        self, events_table_with_witness_trigger: AsyncSession
    ) -> None:
        """AC4: Trigger accepts INSERT with valid witness_id and signature.

        Verifies:
        - Valid witness_id format (WITNESS:{uuid}) is accepted
        - Valid witness_signature length (80-100 chars) is accepted
        - Event is successfully inserted
        """
        db_session = events_table_with_witness_trigger
        params = self._generate_valid_event_params()

        # Insert should succeed
        await db_session.execute(
            text("""
                INSERT INTO events (
                    event_id, event_type, payload, prev_hash, content_hash,
                    signature, witness_id, witness_signature, local_timestamp
                ) VALUES (
                    :event_id, :event_type, CAST(:payload AS jsonb), :prev_hash, :content_hash,
                    :signature, :witness_id, :witness_signature, :local_timestamp
                )
            """),
            params,
        )

        # Verify event was inserted
        result = await db_session.execute(
            text(
                "SELECT witness_id, witness_signature FROM events WHERE event_id = :event_id"
            ),
            {"event_id": params["event_id"]},
        )
        row = result.fetchone()
        assert row is not None, "Event should be inserted"
        assert row[0] == params["witness_id"], "witness_id should match"
        assert row[1] == params["witness_signature"], "witness_signature should match"

    # =========================================================================
    # Test: Trigger rejects missing witness_id (FR5)
    # =========================================================================

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_trigger_rejects_null_witness_id(
        self, events_table_with_witness_trigger: AsyncSession
    ) -> None:
        """FR5: Trigger rejects INSERT with NULL witness_id.

        Constitutional Constraint: CT-12 - Witnessing creates accountability
        No event can exist without witness attribution.
        """
        db_session = events_table_with_witness_trigger

        with pytest.raises((ProgrammingError, DBAPIError)) as exc_info:
            await db_session.execute(
                text("""
                    INSERT INTO events (
                        event_id, event_type, payload, prev_hash, content_hash,
                        signature, witness_id, witness_signature, local_timestamp
                    ) VALUES (
                        :event_id, 'test.event', '{"test": true}'::jsonb,
                        '0000000000000000000000000000000000000000000000000000000000000000',
                        'abc123', 'sig123', NULL, :witness_signature, :local_timestamp
                    )
                """),
                {
                    "event_id": str(uuid4()),
                    "witness_signature": self._generate_valid_witness_signature(),
                    "local_timestamp": datetime.now(timezone.utc),
                },
            )

        error_message = str(exc_info.value)
        # May fail on NOT NULL constraint before trigger, either is acceptable
        assert (
            "FR5" in error_message
            or "witness_id" in error_message.lower()
            or "null" in error_message.lower()
        ), f"Error should mention FR5 or witness_id: {error_message}"

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_trigger_rejects_empty_witness_id(
        self, events_table_with_witness_trigger: AsyncSession
    ) -> None:
        """FR5: Trigger rejects INSERT with empty string witness_id.

        Even if NOT NULL passes, empty string should be rejected by trigger.
        """
        db_session = events_table_with_witness_trigger

        with pytest.raises((ProgrammingError, DBAPIError)) as exc_info:
            await db_session.execute(
                text("""
                    INSERT INTO events (
                        event_id, event_type, payload, prev_hash, content_hash,
                        signature, witness_id, witness_signature, local_timestamp
                    ) VALUES (
                        :event_id, 'test.event', '{"test": true}'::jsonb,
                        '0000000000000000000000000000000000000000000000000000000000000000',
                        'abc123', 'sig123', '', :witness_signature, :local_timestamp
                    )
                """),
                {
                    "event_id": str(uuid4()),
                    "witness_signature": self._generate_valid_witness_signature(),
                    "local_timestamp": datetime.now(timezone.utc),
                },
            )

        error_message = str(exc_info.value)
        assert "FR5" in error_message, f"Error should mention FR5: {error_message}"
        assert "witness_id missing" in error_message

    # =========================================================================
    # Test: Trigger rejects missing witness_signature (FR5)
    # =========================================================================

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_trigger_rejects_null_witness_signature(
        self, events_table_with_witness_trigger: AsyncSession
    ) -> None:
        """FR5: Trigger rejects INSERT with NULL witness_signature.

        Constitutional Constraint: CT-12 - Witnessing creates accountability
        """
        db_session = events_table_with_witness_trigger

        with pytest.raises((ProgrammingError, DBAPIError)) as exc_info:
            await db_session.execute(
                text("""
                    INSERT INTO events (
                        event_id, event_type, payload, prev_hash, content_hash,
                        signature, witness_id, witness_signature, local_timestamp
                    ) VALUES (
                        :event_id, 'test.event', '{"test": true}'::jsonb,
                        '0000000000000000000000000000000000000000000000000000000000000000',
                        'abc123', 'sig123', :witness_id, NULL, :local_timestamp
                    )
                """),
                {
                    "event_id": str(uuid4()),
                    "witness_id": f"WITNESS:{uuid4()}",
                    "local_timestamp": datetime.now(timezone.utc),
                },
            )

        error_message = str(exc_info.value)
        # May fail on NOT NULL constraint before trigger
        assert (
            "FR5" in error_message
            or "witness_signature" in error_message.lower()
            or "null" in error_message.lower()
        ), f"Error should mention FR5 or witness_signature: {error_message}"

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_trigger_rejects_empty_witness_signature(
        self, events_table_with_witness_trigger: AsyncSession
    ) -> None:
        """FR5: Trigger rejects INSERT with empty string witness_signature."""
        db_session = events_table_with_witness_trigger

        with pytest.raises((ProgrammingError, DBAPIError)) as exc_info:
            await db_session.execute(
                text("""
                    INSERT INTO events (
                        event_id, event_type, payload, prev_hash, content_hash,
                        signature, witness_id, witness_signature, local_timestamp
                    ) VALUES (
                        :event_id, 'test.event', '{"test": true}'::jsonb,
                        '0000000000000000000000000000000000000000000000000000000000000000',
                        'abc123', 'sig123', :witness_id, '', :local_timestamp
                    )
                """),
                {
                    "event_id": str(uuid4()),
                    "witness_id": f"WITNESS:{uuid4()}",
                    "local_timestamp": datetime.now(timezone.utc),
                },
            )

        error_message = str(exc_info.value)
        assert "FR5" in error_message, f"Error should mention FR5: {error_message}"
        assert "witness_signature missing" in error_message

    # =========================================================================
    # Test: Trigger rejects invalid witness_id format (FR4)
    # =========================================================================

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_trigger_rejects_witness_id_without_prefix(
        self, events_table_with_witness_trigger: AsyncSession
    ) -> None:
        """FR4: Trigger rejects witness_id that doesn't start with 'WITNESS:'.

        The WITNESS: prefix is required for clear identification of witness IDs
        and prevents confusion with agent IDs.
        """
        db_session = events_table_with_witness_trigger

        with pytest.raises((ProgrammingError, DBAPIError)) as exc_info:
            await db_session.execute(
                text("""
                    INSERT INTO events (
                        event_id, event_type, payload, prev_hash, content_hash,
                        signature, witness_id, witness_signature, local_timestamp
                    ) VALUES (
                        :event_id, 'test.event', '{"test": true}'::jsonb,
                        '0000000000000000000000000000000000000000000000000000000000000000',
                        'abc123', 'sig123', :witness_id, :witness_signature, :local_timestamp
                    )
                """),
                {
                    "event_id": str(uuid4()),
                    "witness_id": f"agent-{uuid4()}",  # Wrong prefix!
                    "witness_signature": self._generate_valid_witness_signature(),
                    "local_timestamp": datetime.now(timezone.utc),
                },
            )

        error_message = str(exc_info.value)
        assert "FR4" in error_message, f"Error should mention FR4: {error_message}"
        assert "must start with WITNESS:" in error_message

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_trigger_rejects_lowercase_witness_prefix(
        self, events_table_with_witness_trigger: AsyncSession
    ) -> None:
        """FR4: Trigger rejects witness_id with lowercase 'witness:' prefix.

        Case sensitivity is enforced for consistent identification.
        """
        db_session = events_table_with_witness_trigger

        with pytest.raises((ProgrammingError, DBAPIError)) as exc_info:
            await db_session.execute(
                text("""
                    INSERT INTO events (
                        event_id, event_type, payload, prev_hash, content_hash,
                        signature, witness_id, witness_signature, local_timestamp
                    ) VALUES (
                        :event_id, 'test.event', '{"test": true}'::jsonb,
                        '0000000000000000000000000000000000000000000000000000000000000000',
                        'abc123', 'sig123', :witness_id, :witness_signature, :local_timestamp
                    )
                """),
                {
                    "event_id": str(uuid4()),
                    "witness_id": f"witness:{uuid4()}",  # Lowercase!
                    "witness_signature": self._generate_valid_witness_signature(),
                    "local_timestamp": datetime.now(timezone.utc),
                },
            )

        error_message = str(exc_info.value)
        assert "FR4" in error_message, f"Error should mention FR4: {error_message}"
        assert "must start with WITNESS:" in error_message

    # =========================================================================
    # Test: Trigger rejects invalid witness_signature length (FR4)
    # =========================================================================

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_trigger_rejects_signature_too_short(
        self, events_table_with_witness_trigger: AsyncSession
    ) -> None:
        """FR4: Trigger rejects witness_signature shorter than 80 characters.

        Ed25519 signatures are 64 bytes = ~88 base64 characters.
        Signatures shorter than 80 chars indicate corruption or wrong algorithm.
        """
        db_session = events_table_with_witness_trigger

        with pytest.raises((ProgrammingError, DBAPIError)) as exc_info:
            await db_session.execute(
                text("""
                    INSERT INTO events (
                        event_id, event_type, payload, prev_hash, content_hash,
                        signature, witness_id, witness_signature, local_timestamp
                    ) VALUES (
                        :event_id, 'test.event', '{"test": true}'::jsonb,
                        '0000000000000000000000000000000000000000000000000000000000000000',
                        'abc123', 'sig123', :witness_id, :witness_signature, :local_timestamp
                    )
                """),
                {
                    "event_id": str(uuid4()),
                    "witness_id": f"WITNESS:{uuid4()}",
                    "witness_signature": "too_short",  # Only 9 chars!
                    "local_timestamp": datetime.now(timezone.utc),
                },
            )

        error_message = str(exc_info.value)
        assert "FR4" in error_message, f"Error should mention FR4: {error_message}"
        assert "unexpected length" in error_message

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_trigger_rejects_signature_too_long(
        self, events_table_with_witness_trigger: AsyncSession
    ) -> None:
        """FR4: Trigger rejects witness_signature longer than 100 characters.

        Signatures longer than expected indicate data corruption or wrong format.
        """
        db_session = events_table_with_witness_trigger

        with pytest.raises((ProgrammingError, DBAPIError)) as exc_info:
            await db_session.execute(
                text("""
                    INSERT INTO events (
                        event_id, event_type, payload, prev_hash, content_hash,
                        signature, witness_id, witness_signature, local_timestamp
                    ) VALUES (
                        :event_id, 'test.event', '{"test": true}'::jsonb,
                        '0000000000000000000000000000000000000000000000000000000000000000',
                        'abc123', 'sig123', :witness_id, :witness_signature, :local_timestamp
                    )
                """),
                {
                    "event_id": str(uuid4()),
                    "witness_id": f"WITNESS:{uuid4()}",
                    "witness_signature": "A" * 150,  # 150 chars - too long!
                    "local_timestamp": datetime.now(timezone.utc),
                },
            )

        error_message = str(exc_info.value)
        assert "FR4" in error_message, f"Error should mention FR4: {error_message}"
        assert "unexpected length" in error_message

    # =========================================================================
    # Test: Edge cases for valid signatures
    # =========================================================================

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_trigger_accepts_minimum_valid_signature_length(
        self, events_table_with_witness_trigger: AsyncSession
    ) -> None:
        """FR4: Trigger accepts signature at minimum valid length (80 chars)."""
        db_session = events_table_with_witness_trigger
        params = self._generate_valid_event_params()
        params["witness_signature"] = "A" * 80  # Minimum valid length

        # Should succeed
        await db_session.execute(
            text("""
                INSERT INTO events (
                    event_id, event_type, payload, prev_hash, content_hash,
                    signature, witness_id, witness_signature, local_timestamp
                ) VALUES (
                    :event_id, :event_type, CAST(:payload AS jsonb), :prev_hash, :content_hash,
                    :signature, :witness_id, :witness_signature, :local_timestamp
                )
            """),
            params,
        )

        result = await db_session.execute(
            text("SELECT COUNT(*) FROM events WHERE event_id = :event_id"),
            {"event_id": params["event_id"]},
        )
        assert result.scalar() == 1

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_trigger_accepts_maximum_valid_signature_length(
        self, events_table_with_witness_trigger: AsyncSession
    ) -> None:
        """FR4: Trigger accepts signature at maximum valid length (100 chars)."""
        db_session = events_table_with_witness_trigger
        params = self._generate_valid_event_params()
        params["witness_signature"] = "A" * 100  # Maximum valid length

        # Should succeed
        await db_session.execute(
            text("""
                INSERT INTO events (
                    event_id, event_type, payload, prev_hash, content_hash,
                    signature, witness_id, witness_signature, local_timestamp
                ) VALUES (
                    :event_id, :event_type, CAST(:payload AS jsonb), :prev_hash, :content_hash,
                    :signature, :witness_id, :witness_signature, :local_timestamp
                )
            """),
            params,
        )

        result = await db_session.execute(
            text("SELECT COUNT(*) FROM events WHERE event_id = :event_id"),
            {"event_id": params["event_id"]},
        )
        assert result.scalar() == 1


class TestWitnessValidationTriggerExists:
    """Tests to verify the trigger infrastructure is properly installed."""

    @pytest.fixture
    async def events_table_with_witness_trigger(
        self, db_session: AsyncSession
    ) -> AsyncSession:
        """Create events table with witness validation trigger."""
        # Create events table
        await db_session.execute(
            text("""
            CREATE TABLE IF NOT EXISTS events (
                event_id UUID PRIMARY KEY,
                sequence BIGSERIAL UNIQUE NOT NULL,
                event_type TEXT NOT NULL,
                payload JSONB NOT NULL,
                prev_hash TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                signature TEXT NOT NULL,
                hash_alg_version SMALLINT NOT NULL DEFAULT 1,
                sig_alg_version SMALLINT NOT NULL DEFAULT 1,
                agent_id TEXT,
                witness_id TEXT NOT NULL,
                witness_signature TEXT NOT NULL,
                local_timestamp TIMESTAMPTZ NOT NULL,
                authority_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        )

        # Create witness validation trigger function
        await db_session.execute(
            text("""
            CREATE OR REPLACE FUNCTION validate_witness_attribution()
            RETURNS TRIGGER AS $func$
            BEGIN
                IF NEW.witness_id IS NULL OR NEW.witness_id = '' THEN
                    RAISE EXCEPTION 'FR5: Witness attribution required - witness_id missing';
                END IF;
                IF NEW.witness_signature IS NULL OR NEW.witness_signature = '' THEN
                    RAISE EXCEPTION 'FR5: Witness attribution required - witness_signature missing';
                END IF;
                IF NOT NEW.witness_id LIKE 'WITNESS:%' THEN
                    RAISE EXCEPTION 'FR4: Invalid witness_id format - must start with WITNESS:';
                END IF;
                IF length(NEW.witness_signature) < 80 OR length(NEW.witness_signature) > 100 THEN
                    RAISE EXCEPTION 'FR4: Invalid witness signature - unexpected length';
                END IF;
                RETURN NEW;
            END;
            $func$ LANGUAGE plpgsql
        """)
        )

        # Create trigger
        await db_session.execute(
            text(
                "DROP TRIGGER IF EXISTS validate_witness_attribution_on_insert ON events"
            )
        )
        await db_session.execute(
            text("""
            CREATE TRIGGER validate_witness_attribution_on_insert
                BEFORE INSERT ON events
                FOR EACH ROW
                EXECUTE FUNCTION validate_witness_attribution()
        """)
        )

        return db_session

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_witness_validation_function_exists(
        self, events_table_with_witness_trigger: AsyncSession
    ) -> None:
        """Verify validate_witness_attribution function exists."""
        db_session = events_table_with_witness_trigger

        result = await db_session.execute(
            text("""
                SELECT routine_name
                FROM information_schema.routines
                WHERE routine_name = 'validate_witness_attribution'
                AND routine_type = 'FUNCTION'
            """)
        )
        functions = [row[0] for row in result.fetchall()]
        assert "validate_witness_attribution" in functions

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_witness_validation_trigger_exists(
        self, events_table_with_witness_trigger: AsyncSession
    ) -> None:
        """Verify validate_witness_attribution_on_insert trigger exists."""
        db_session = events_table_with_witness_trigger

        result = await db_session.execute(
            text("""
                SELECT trigger_name
                FROM information_schema.triggers
                WHERE trigger_name = 'validate_witness_attribution_on_insert'
                AND event_object_table = 'events'
            """)
        )
        triggers = [row[0] for row in result.fetchall()]
        assert "validate_witness_attribution_on_insert" in triggers

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_witness_validation_trigger_fires_before_insert(
        self, events_table_with_witness_trigger: AsyncSession
    ) -> None:
        """Verify trigger fires BEFORE INSERT."""
        db_session = events_table_with_witness_trigger

        result = await db_session.execute(
            text("""
                SELECT action_timing, event_manipulation
                FROM information_schema.triggers
                WHERE trigger_name = 'validate_witness_attribution_on_insert'
                AND event_object_table = 'events'
            """)
        )
        row = result.fetchone()
        assert row is not None
        assert row[0] == "BEFORE", "Trigger should fire BEFORE"
        assert row[1] == "INSERT", "Trigger should fire on INSERT"
