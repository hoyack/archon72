"""Integration tests for hash chain verification (FR2, FR82-FR85).

These tests verify:
- DB trigger rejects events with invalid prev_hash (AC4)
- verify_chain() function correctly validates hash chains (AC5)
- Genesis events work correctly (AC2)
- Hash chain integrity is maintained through DB operations
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# Skip all tests if no database configured
pytestmark = pytest.mark.skipif(
    os.environ.get("DATABASE_URL") is None,
    reason="DATABASE_URL environment variable not set",
)


# Genesis hash constant matching domain layer
GENESIS_HASH = "0" * 64


@pytest.fixture(scope="module")
def database_url() -> str:
    """Get database URL from environment."""
    url = os.environ.get("DATABASE_URL", "")
    # Convert postgres:// to postgresql+asyncpg://
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


@pytest.fixture(scope="module")
async def engine(database_url: str):
    """Create async engine."""
    eng = create_async_engine(database_url, echo=False)
    yield eng
    await eng.dispose()


@pytest.fixture
async def db_session(engine) -> AsyncSession:
    """Create database session with cleanup."""
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        # Apply migrations
        migration_path = Path(__file__).parent.parent.parent / "migrations"

        # Apply migration 001 (events table)
        migration_001 = migration_path / "001_create_events_table.sql"
        if migration_001.exists():
            sql = migration_001.read_text()
            # Split by semicolons but handle plpgsql bodies
            await session.execute(text(sql))
            await session.commit()

        # Apply migration 002 (hash chain verification)
        migration_002 = migration_path / "002_hash_chain_verification.sql"
        if migration_002.exists():
            sql = migration_002.read_text()
            await session.execute(text(sql))
            await session.commit()

        yield session

        # Cleanup: Remove all events (need to disable trigger temporarily)
        await session.execute(
            text("DROP TRIGGER IF EXISTS prevent_event_delete ON events")
        )
        await session.execute(text("DELETE FROM events"))
        await session.execute(
            text("""
            CREATE TRIGGER prevent_event_delete
                BEFORE DELETE ON events
                FOR EACH ROW
                EXECUTE FUNCTION prevent_event_modification()
        """)
        )
        await session.commit()


def make_event_data(
    sequence: int,
    prev_hash: str,
    content_hash: str | None = None,
    event_type: str = "test.event",
) -> dict[str, Any]:
    """Create event data dictionary for insertion."""
    if content_hash is None:
        # Generate a unique content hash for testing
        content_hash = f"{uuid.uuid4().hex}{uuid.uuid4().hex}"[:64]

    return {
        "event_id": str(uuid.uuid4()),
        "sequence": sequence,
        "event_type": event_type,
        "payload": "{}",
        "prev_hash": prev_hash,
        "content_hash": content_hash,
        "signature": f"sig_{sequence}",
        "witness_id": "witness-001",
        "witness_signature": f"wsig_{sequence}",
        "local_timestamp": datetime.now(timezone.utc).isoformat(),
    }


class TestHashChainTrigger:
    """Tests for DB trigger that verifies hash chain on insert (AC4)."""

    @pytest.mark.asyncio
    async def test_genesis_event_accepted_with_genesis_hash(
        self, db_session: AsyncSession
    ) -> None:
        """First event (sequence 1) should be accepted with genesis prev_hash."""
        event = make_event_data(sequence=1, prev_hash=GENESIS_HASH)

        await db_session.execute(
            text("""
            INSERT INTO events (event_id, sequence, event_type, payload, prev_hash,
                content_hash, signature, witness_id, witness_signature, local_timestamp)
            VALUES (:event_id, :sequence, :event_type, :payload::jsonb, :prev_hash,
                :content_hash, :signature, :witness_id, :witness_signature,
                :local_timestamp::timestamptz)
        """),
            event,
        )
        await db_session.commit()

        # Verify event was inserted
        result = await db_session.execute(
            text("SELECT * FROM events WHERE sequence = 1")
        )
        row = result.fetchone()
        assert row is not None
        assert row.prev_hash == GENESIS_HASH

    @pytest.mark.asyncio
    async def test_genesis_event_rejected_with_wrong_prev_hash(
        self, db_session: AsyncSession
    ) -> None:
        """First event should be rejected if prev_hash is not genesis."""
        event = make_event_data(sequence=1, prev_hash="wrong_hash" + "0" * 54)

        with pytest.raises(Exception) as exc_info:
            await db_session.execute(
                text("""
                INSERT INTO events (event_id, sequence, event_type, payload, prev_hash,
                    content_hash, signature, witness_id, witness_signature, local_timestamp)
                VALUES (:event_id, :sequence, :event_type, :payload::jsonb, :prev_hash,
                    :content_hash, :signature, :witness_id, :witness_signature,
                    :local_timestamp::timestamptz)
            """),
                event,
            )
            await db_session.commit()

        error_msg = str(exc_info.value)
        assert "FR82" in error_msg
        assert "Hash chain continuity violation" in error_msg

    @pytest.mark.asyncio
    async def test_subsequent_event_accepted_with_correct_prev_hash(
        self, db_session: AsyncSession
    ) -> None:
        """Subsequent event should be accepted if prev_hash matches previous content_hash."""
        # Insert first event
        first_content_hash = "a" * 64
        first_event = make_event_data(
            sequence=1, prev_hash=GENESIS_HASH, content_hash=first_content_hash
        )
        await db_session.execute(
            text("""
            INSERT INTO events (event_id, sequence, event_type, payload, prev_hash,
                content_hash, signature, witness_id, witness_signature, local_timestamp)
            VALUES (:event_id, :sequence, :event_type, :payload::jsonb, :prev_hash,
                :content_hash, :signature, :witness_id, :witness_signature,
                :local_timestamp::timestamptz)
        """),
            first_event,
        )
        await db_session.commit()

        # Insert second event with correct prev_hash
        second_event = make_event_data(sequence=2, prev_hash=first_content_hash)
        await db_session.execute(
            text("""
            INSERT INTO events (event_id, sequence, event_type, payload, prev_hash,
                content_hash, signature, witness_id, witness_signature, local_timestamp)
            VALUES (:event_id, :sequence, :event_type, :payload::jsonb, :prev_hash,
                :content_hash, :signature, :witness_id, :witness_signature,
                :local_timestamp::timestamptz)
        """),
            second_event,
        )
        await db_session.commit()

        # Verify both events exist
        result = await db_session.execute(text("SELECT COUNT(*) FROM events"))
        count = result.scalar()
        assert count == 2

    @pytest.mark.asyncio
    async def test_subsequent_event_rejected_with_wrong_prev_hash(
        self, db_session: AsyncSession
    ) -> None:
        """Subsequent event should be rejected if prev_hash doesn't match."""
        # Insert first event
        first_content_hash = "b" * 64
        first_event = make_event_data(
            sequence=1, prev_hash=GENESIS_HASH, content_hash=first_content_hash
        )
        await db_session.execute(
            text("""
            INSERT INTO events (event_id, sequence, event_type, payload, prev_hash,
                content_hash, signature, witness_id, witness_signature, local_timestamp)
            VALUES (:event_id, :sequence, :event_type, :payload::jsonb, :prev_hash,
                :content_hash, :signature, :witness_id, :witness_signature,
                :local_timestamp::timestamptz)
        """),
            first_event,
        )
        await db_session.commit()

        # Try to insert second event with WRONG prev_hash
        wrong_prev_hash = "c" * 64  # Should be 'b' * 64
        second_event = make_event_data(sequence=2, prev_hash=wrong_prev_hash)

        with pytest.raises(Exception) as exc_info:
            await db_session.execute(
                text("""
                INSERT INTO events (event_id, sequence, event_type, payload, prev_hash,
                    content_hash, signature, witness_id, witness_signature, local_timestamp)
                VALUES (:event_id, :sequence, :event_type, :payload::jsonb, :prev_hash,
                    :content_hash, :signature, :witness_id, :witness_signature,
                    :local_timestamp::timestamptz)
            """),
                second_event,
            )
            await db_session.commit()

        error_msg = str(exc_info.value)
        assert "FR82" in error_msg
        assert "Hash chain continuity violation" in error_msg
        assert "prev_hash mismatch" in error_msg

    @pytest.mark.asyncio
    async def test_event_rejected_when_previous_sequence_missing(
        self, db_session: AsyncSession
    ) -> None:
        """Event should be rejected if previous sequence number doesn't exist."""
        # Try to insert sequence 5 without 1-4 existing
        event = make_event_data(sequence=5, prev_hash="x" * 64)

        with pytest.raises(Exception) as exc_info:
            await db_session.execute(
                text("""
                INSERT INTO events (event_id, sequence, event_type, payload, prev_hash,
                    content_hash, signature, witness_id, witness_signature, local_timestamp)
                VALUES (:event_id, :sequence, :event_type, :payload::jsonb, :prev_hash,
                    :content_hash, :signature, :witness_id, :witness_signature,
                    :local_timestamp::timestamptz)
            """),
                event,
            )
            await db_session.commit()

        error_msg = str(exc_info.value)
        assert "FR82" in error_msg
        assert "previous event" in error_msg.lower()
        assert "not found" in error_msg.lower()


class TestVerifyChainFunction:
    """Tests for verify_chain() SQL function (AC5)."""

    @pytest.mark.asyncio
    async def test_verify_chain_returns_true_for_valid_chain(
        self, db_session: AsyncSession
    ) -> None:
        """verify_chain() should return is_valid=TRUE for correctly chained events."""
        # Build a valid chain of 3 events
        hash1 = "1" * 64
        hash2 = "2" * 64
        hash3 = "3" * 64

        events = [
            make_event_data(sequence=1, prev_hash=GENESIS_HASH, content_hash=hash1),
            make_event_data(sequence=2, prev_hash=hash1, content_hash=hash2),
            make_event_data(sequence=3, prev_hash=hash2, content_hash=hash3),
        ]

        for event in events:
            await db_session.execute(
                text("""
                INSERT INTO events (event_id, sequence, event_type, payload, prev_hash,
                    content_hash, signature, witness_id, witness_signature, local_timestamp)
                VALUES (:event_id, :sequence, :event_type, :payload::jsonb, :prev_hash,
                    :content_hash, :signature, :witness_id, :witness_signature,
                    :local_timestamp::timestamptz)
            """),
                event,
            )
        await db_session.commit()

        # Verify the chain
        result = await db_session.execute(text("SELECT * FROM verify_chain(1, 3)"))
        row = result.fetchone()

        assert row is not None
        assert row.is_valid is True
        assert row.broken_at_sequence is None

    @pytest.mark.asyncio
    async def test_verify_chain_returns_false_for_broken_chain(
        self, db_session: AsyncSession
    ) -> None:
        """verify_chain() should return is_valid=FALSE with details for broken chain."""
        # We need to bypass the trigger to insert a broken chain
        # First, drop the verification trigger temporarily
        await db_session.execute(
            text("DROP TRIGGER IF EXISTS verify_hash_chain_on_insert ON events")
        )
        await db_session.commit()

        try:
            # Insert events with a broken chain (event 2 has wrong prev_hash)
            hash1 = "d" * 64
            hash2 = "e" * 64
            wrong_hash = "f" * 64  # Wrong - should be hash1

            events = [
                make_event_data(sequence=1, prev_hash=GENESIS_HASH, content_hash=hash1),
                make_event_data(
                    sequence=2, prev_hash=wrong_hash, content_hash=hash2
                ),  # BROKEN
            ]

            for event in events:
                await db_session.execute(
                    text("""
                    INSERT INTO events (event_id, sequence, event_type, payload, prev_hash,
                        content_hash, signature, witness_id, witness_signature, local_timestamp)
                    VALUES (:event_id, :sequence, :event_type, :payload::jsonb, :prev_hash,
                        :content_hash, :signature, :witness_id, :witness_signature,
                        :local_timestamp::timestamptz)
                """),
                    event,
                )
            await db_session.commit()

            # Verify the broken chain
            result = await db_session.execute(text("SELECT * FROM verify_chain(1, 2)"))
            row = result.fetchone()

            assert row is not None
            assert row.is_valid is False
            assert row.broken_at_sequence == 2
            assert row.expected_hash == hash1
            assert row.actual_hash == wrong_hash

        finally:
            # Restore the trigger
            await db_session.execute(
                text("""
                CREATE TRIGGER verify_hash_chain_on_insert
                    BEFORE INSERT ON events
                    FOR EACH ROW
                    EXECUTE FUNCTION verify_hash_chain_on_insert()
            """)
            )
            await db_session.commit()

    @pytest.mark.asyncio
    async def test_verify_chain_detects_wrong_genesis_hash(
        self, db_session: AsyncSession
    ) -> None:
        """verify_chain() should detect if first event has wrong prev_hash."""
        # Bypass trigger to insert invalid genesis
        await db_session.execute(
            text("DROP TRIGGER IF EXISTS verify_hash_chain_on_insert ON events")
        )
        await db_session.commit()

        try:
            wrong_genesis = "x" * 64
            event = make_event_data(
                sequence=1, prev_hash=wrong_genesis, content_hash="y" * 64
            )

            await db_session.execute(
                text("""
                INSERT INTO events (event_id, sequence, event_type, payload, prev_hash,
                    content_hash, signature, witness_id, witness_signature, local_timestamp)
                VALUES (:event_id, :sequence, :event_type, :payload::jsonb, :prev_hash,
                    :content_hash, :signature, :witness_id, :witness_signature,
                    :local_timestamp::timestamptz)
            """),
                event,
            )
            await db_session.commit()

            result = await db_session.execute(text("SELECT * FROM verify_chain(1, 1)"))
            row = result.fetchone()

            assert row is not None
            assert row.is_valid is False
            assert row.broken_at_sequence == 1
            assert row.expected_hash == GENESIS_HASH
            assert row.actual_hash == wrong_genesis

        finally:
            await db_session.execute(
                text("""
                CREATE TRIGGER verify_hash_chain_on_insert
                    BEFORE INSERT ON events
                    FOR EACH ROW
                    EXECUTE FUNCTION verify_hash_chain_on_insert()
            """)
            )
            await db_session.commit()

    @pytest.mark.asyncio
    async def test_verify_chain_handles_empty_range(
        self, db_session: AsyncSession
    ) -> None:
        """verify_chain() should handle empty range (no events in range)."""
        result = await db_session.execute(
            text("SELECT * FROM verify_chain(1000, 2000)")
        )
        row = result.fetchone()

        # Empty range should return is_valid=TRUE (nothing to invalidate)
        assert row is not None
        assert row.is_valid is True


class TestHashChainIntegrity:
    """End-to-end tests for hash chain integrity (AC1-AC6)."""

    @pytest.mark.asyncio
    async def test_full_chain_creation_and_verification(
        self, db_session: AsyncSession
    ) -> None:
        """Test creating a full chain and verifying it."""
        from src.domain.events.hash_utils import (
            GENESIS_HASH,
            compute_content_hash,
            get_prev_hash,
        )

        # Build events with proper hashes
        events_data = []
        prev_hash = GENESIS_HASH

        for i in range(1, 6):  # Create 5 events
            event_fields = {
                "event_type": f"test.event.{i}",
                "payload": {"iteration": i, "data": f"test data {i}"},
                "signature": f"sig_{i}",
                "witness_id": "witness-001",
                "witness_signature": f"wsig_{i}",
                "local_timestamp": datetime.now(timezone.utc),
            }

            content_hash = compute_content_hash(event_fields)
            current_prev_hash = get_prev_hash(
                sequence=i,
                previous_content_hash=prev_hash if i > 1 else None,
            )

            event = {
                "event_id": str(uuid.uuid4()),
                "sequence": i,
                "event_type": event_fields["event_type"],
                "payload": f'{{"iteration":{i},"data":"test data {i}"}}',
                "prev_hash": current_prev_hash,
                "content_hash": content_hash,
                "signature": event_fields["signature"],
                "witness_id": event_fields["witness_id"],
                "witness_signature": event_fields["witness_signature"],
                "local_timestamp": event_fields["local_timestamp"].isoformat(),
            }

            events_data.append(event)
            prev_hash = content_hash

        # Insert all events
        for event in events_data:
            await db_session.execute(
                text("""
                INSERT INTO events (event_id, sequence, event_type, payload, prev_hash,
                    content_hash, signature, witness_id, witness_signature, local_timestamp)
                VALUES (:event_id, :sequence, :event_type, :payload::jsonb, :prev_hash,
                    :content_hash, :signature, :witness_id, :witness_signature,
                    :local_timestamp::timestamptz)
            """),
                event,
            )
        await db_session.commit()

        # Verify the chain is valid
        result = await db_session.execute(text("SELECT * FROM verify_chain(1, 5)"))
        row = result.fetchone()

        assert row is not None
        assert row.is_valid is True
        assert row.broken_at_sequence is None
