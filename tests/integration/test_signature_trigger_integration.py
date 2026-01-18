"""Integration tests for signature validation DB trigger (FR74, Story 1.3 AC4).

Tests the database-level enforcement of signature validation using PostgreSQL triggers.

AC4: Given an event is submitted without a valid signature,
     When the DB trigger evaluates,
     Then the insert is rejected
     And error message includes "FR74: Invalid agent signature"

Constitutional Constraints:
- FR74: Invalid agent signatures must be rejected
- FR75: Key registry must track active keys
- CT-11: Silent failure destroys legitimacy → HALT OVER DEGRADE
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession


class TestSignatureValidationTrigger:
    """Tests for signature format validation trigger (AC4)."""

    @pytest.fixture
    async def schema_with_trigger(self, db_session: AsyncSession) -> AsyncSession:
        """Create events table, agent_keys table, and signature validation trigger."""
        # Create agent_keys table first (required for FK reference)
        await db_session.execute(
            text("""
            CREATE TABLE IF NOT EXISTS agent_keys (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                agent_id TEXT NOT NULL,
                key_id TEXT NOT NULL UNIQUE,
                public_key BYTEA NOT NULL,
                active_from TIMESTAMPTZ NOT NULL DEFAULT now(),
                active_until TIMESTAMPTZ,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                CONSTRAINT agent_keys_active_check CHECK (
                    active_until IS NULL OR active_until > active_from
                )
            )
        """)
        )

        # Create events table with signing_key_id column
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
                signing_key_id TEXT NOT NULL DEFAULT '',
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

        # Create signature validation trigger function
        await db_session.execute(
            text("""
            CREATE OR REPLACE FUNCTION validate_signature_format()
            RETURNS TRIGGER AS $func$
            BEGIN
                -- Validate signature is present and non-empty
                IF NEW.signature IS NULL OR NEW.signature = '' THEN
                    RAISE EXCEPTION 'FR74: Invalid agent signature - signature is required';
                END IF;

                -- Validate signature length is consistent with Ed25519
                -- Ed25519 signatures are 64 bytes = 88 base64 chars (with padding)
                IF length(NEW.signature) < 80 OR length(NEW.signature) > 100 THEN
                    RAISE EXCEPTION 'FR74: Invalid agent signature - unexpected signature length';
                END IF;

                -- Validate signing_key_id references a valid key
                IF NEW.signing_key_id IS NULL OR NEW.signing_key_id = '' THEN
                    RAISE EXCEPTION 'FR74: Invalid agent signature - signing_key_id is required';
                END IF;

                IF NOT EXISTS (
                    SELECT 1 FROM agent_keys
                    WHERE key_id = NEW.signing_key_id
                ) THEN
                    RAISE EXCEPTION 'FR74: Invalid agent signature - unknown signing key: %', NEW.signing_key_id;
                END IF;

                RETURN NEW;
            END;
            $func$ LANGUAGE plpgsql
        """)
        )

        # Create trigger
        await db_session.execute(
            text("DROP TRIGGER IF EXISTS validate_signature_format_on_insert ON events")
        )
        await db_session.execute(
            text("""
            CREATE TRIGGER validate_signature_format_on_insert
            BEFORE INSERT ON events
            FOR EACH ROW
            EXECUTE FUNCTION validate_signature_format()
        """)
        )

        return db_session

    @pytest.fixture
    async def schema_with_valid_key(
        self, schema_with_trigger: AsyncSession
    ) -> tuple[AsyncSession, str]:
        """Create schema with a valid agent key registered."""
        key_id = f"dev-{uuid4().hex[:8]}"

        # Insert a valid agent key
        await schema_with_trigger.execute(
            text("""
                INSERT INTO agent_keys (agent_id, key_id, public_key)
                VALUES (:agent_id, :key_id, :public_key)
            """),
            {
                "agent_id": "agent-001",
                "key_id": key_id,
                "public_key": b"x" * 32,  # Ed25519 public key
            },
        )

        return schema_with_trigger, key_id

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_insert_rejected_without_signature(
        self, schema_with_trigger: AsyncSession
    ) -> None:
        """AC4: Insert without signature is rejected with FR74 error."""
        with pytest.raises((ProgrammingError, DBAPIError)) as exc_info:
            await schema_with_trigger.execute(
                text("""
                    INSERT INTO events (
                        event_id, event_type, payload, prev_hash, content_hash,
                        signature, signing_key_id, witness_id, witness_signature,
                        local_timestamp
                    ) VALUES (
                        :event_id, 'test.event', '{"test": true}'::jsonb,
                        '0000000000000000000000000000000000000000000000000000000000000000',
                        'abc123', '', 'dev-test', 'witness-001', 'wsig123',
                        :local_timestamp
                    )
                """),
                {
                    "event_id": str(uuid4()),
                    "local_timestamp": datetime.now(timezone.utc),
                },
            )

        error_message = str(exc_info.value)
        assert "FR74" in error_message, f"Error should mention FR74: {error_message}"
        assert "signature" in error_message.lower()

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_insert_rejected_with_wrong_signature_length(
        self, schema_with_valid_key: tuple[AsyncSession, str]
    ) -> None:
        """AC4: Insert with wrong-length signature is rejected."""
        session, key_id = schema_with_valid_key

        with pytest.raises((ProgrammingError, DBAPIError)) as exc_info:
            await session.execute(
                text("""
                    INSERT INTO events (
                        event_id, event_type, payload, prev_hash, content_hash,
                        signature, signing_key_id, witness_id, witness_signature,
                        local_timestamp
                    ) VALUES (
                        :event_id, 'test.event', '{"test": true}'::jsonb,
                        '0000000000000000000000000000000000000000000000000000000000000000',
                        'abc123', 'tooshort', :key_id, 'witness-001', 'wsig123',
                        :local_timestamp
                    )
                """),
                {
                    "event_id": str(uuid4()),
                    "key_id": key_id,
                    "local_timestamp": datetime.now(timezone.utc),
                },
            )

        error_message = str(exc_info.value)
        assert "FR74" in error_message, f"Error should mention FR74: {error_message}"
        assert "length" in error_message.lower()

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_insert_rejected_without_signing_key_id(
        self, schema_with_trigger: AsyncSession
    ) -> None:
        """AC4: Insert without signing_key_id is rejected."""
        # Valid Ed25519 signature length (~88 chars base64)
        valid_length_sig = "x" * 88

        with pytest.raises((ProgrammingError, DBAPIError)) as exc_info:
            await schema_with_trigger.execute(
                text("""
                    INSERT INTO events (
                        event_id, event_type, payload, prev_hash, content_hash,
                        signature, signing_key_id, witness_id, witness_signature,
                        local_timestamp
                    ) VALUES (
                        :event_id, 'test.event', '{"test": true}'::jsonb,
                        '0000000000000000000000000000000000000000000000000000000000000000',
                        'abc123', :signature, '', 'witness-001', 'wsig123',
                        :local_timestamp
                    )
                """),
                {
                    "event_id": str(uuid4()),
                    "signature": valid_length_sig,
                    "local_timestamp": datetime.now(timezone.utc),
                },
            )

        error_message = str(exc_info.value)
        assert "FR74" in error_message, f"Error should mention FR74: {error_message}"
        assert "signing_key_id" in error_message.lower()

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_insert_rejected_with_unknown_signing_key(
        self, schema_with_trigger: AsyncSession
    ) -> None:
        """AC4: Insert with unknown signing_key_id is rejected."""
        # Valid Ed25519 signature length (~88 chars base64)
        valid_length_sig = "x" * 88

        with pytest.raises((ProgrammingError, DBAPIError)) as exc_info:
            await schema_with_trigger.execute(
                text("""
                    INSERT INTO events (
                        event_id, event_type, payload, prev_hash, content_hash,
                        signature, signing_key_id, witness_id, witness_signature,
                        local_timestamp
                    ) VALUES (
                        :event_id, 'test.event', '{"test": true}'::jsonb,
                        '0000000000000000000000000000000000000000000000000000000000000000',
                        'abc123', :signature, 'nonexistent-key', 'witness-001', 'wsig123',
                        :local_timestamp
                    )
                """),
                {
                    "event_id": str(uuid4()),
                    "signature": valid_length_sig,
                    "local_timestamp": datetime.now(timezone.utc),
                },
            )

        error_message = str(exc_info.value)
        assert "FR74" in error_message, f"Error should mention FR74: {error_message}"
        assert "unknown signing key" in error_message.lower()

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_insert_succeeds_with_valid_signature_and_key(
        self, schema_with_valid_key: tuple[AsyncSession, str]
    ) -> None:
        """Insert with valid signature format and registered key succeeds."""
        session, key_id = schema_with_valid_key

        # Valid Ed25519 signature length (~88 chars base64)
        valid_length_sig = "x" * 88

        # Should not raise
        await session.execute(
            text("""
                INSERT INTO events (
                    event_id, event_type, payload, prev_hash, content_hash,
                    signature, signing_key_id, witness_id, witness_signature,
                    local_timestamp
                ) VALUES (
                    :event_id, 'test.event', '{"test": true}'::jsonb,
                    '0000000000000000000000000000000000000000000000000000000000000000',
                    'abc123', :signature, :key_id, 'witness-001', 'wsig123',
                    :local_timestamp
                )
            """),
            {
                "event_id": str(uuid4()),
                "signature": valid_length_sig,
                "key_id": key_id,
                "local_timestamp": datetime.now(timezone.utc),
            },
        )

        # Verify insert succeeded
        result = await session.execute(text("SELECT COUNT(*) FROM events"))
        count = result.scalar()
        assert count == 1


class TestKeyRegistryDeletePrevention:
    """Tests for key registry delete prevention trigger (FR76)."""

    @pytest.fixture
    async def key_registry_schema(self, db_session: AsyncSession) -> AsyncSession:
        """Create agent_keys table with delete prevention trigger."""
        # Create agent_keys table
        await db_session.execute(
            text("""
            CREATE TABLE IF NOT EXISTS agent_keys (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                agent_id TEXT NOT NULL,
                key_id TEXT NOT NULL UNIQUE,
                public_key BYTEA NOT NULL,
                active_from TIMESTAMPTZ NOT NULL DEFAULT now(),
                active_until TIMESTAMPTZ,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                CONSTRAINT agent_keys_active_check CHECK (
                    active_until IS NULL OR active_until > active_from
                )
            )
        """)
        )

        # Create delete prevention trigger
        await db_session.execute(
            text("""
            CREATE OR REPLACE FUNCTION prevent_key_deletion()
            RETURNS TRIGGER AS $func$
            BEGIN
                RAISE EXCEPTION 'FR76: Key deletion prohibited - historical keys must be preserved';
            END;
            $func$ LANGUAGE plpgsql
        """)
        )

        await db_session.execute(
            text("DROP TRIGGER IF EXISTS prevent_agent_key_deletion ON agent_keys")
        )
        await db_session.execute(
            text("""
            CREATE TRIGGER prevent_agent_key_deletion
            BEFORE DELETE ON agent_keys
            FOR EACH ROW
            EXECUTE FUNCTION prevent_key_deletion()
        """)
        )

        return db_session

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_key_deletion_is_prevented_with_fr76_error(
        self, key_registry_schema: AsyncSession
    ) -> None:
        """FR76: Key deletion is prevented with FR76 error message."""
        # Insert a key
        await key_registry_schema.execute(
            text("""
                INSERT INTO agent_keys (agent_id, key_id, public_key)
                VALUES ('agent-001', 'dev-test123', :public_key)
            """),
            {"public_key": b"x" * 32},
        )

        # Attempt to delete - should fail
        with pytest.raises((ProgrammingError, DBAPIError)) as exc_info:
            await key_registry_schema.execute(
                text("DELETE FROM agent_keys WHERE key_id = 'dev-test123'")
            )

        error_message = str(exc_info.value)
        assert "FR76" in error_message, f"Error should mention FR76: {error_message}"
        assert "deletion prohibited" in error_message.lower()

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_key_update_is_allowed(
        self, key_registry_schema: AsyncSession
    ) -> None:
        """Keys can be updated (e.g., setting active_until for rotation)."""
        # Insert a key with active_from in the past
        await key_registry_schema.execute(
            text("""
                INSERT INTO agent_keys (agent_id, key_id, public_key, active_from)
                VALUES ('agent-001', 'dev-test123', :public_key, now() - interval '1 hour')
            """),
            {"public_key": b"x" * 32},
        )

        # Update should succeed (setting active_until for key rotation)
        # active_until must be > active_from per check constraint
        await key_registry_schema.execute(
            text("""
                UPDATE agent_keys
                SET active_until = now()
                WHERE key_id = 'dev-test123'
            """)
        )

        # Verify update worked
        result = await key_registry_schema.execute(
            text("SELECT active_until FROM agent_keys WHERE key_id = 'dev-test123'")
        )
        row = result.fetchone()
        assert row is not None
        assert row[0] is not None  # active_until was set
