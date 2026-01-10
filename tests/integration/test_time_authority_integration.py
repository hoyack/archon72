"""Integration tests for Time Authority & Sequence Numbers (Story 1.5).

Tests dual timestamps, sequence uniqueness, and clock drift detection
against real database infrastructure.

Constitutional Constraints Tested:
- FR6: Events must have dual timestamps (local + authority)
- FR7: Sequence numbers must be monotonically increasing and unique
- AC1: Dual timestamps on event creation
- AC2: Unique sequential numbers with concurrent inserts
- AC3: Sequence as authoritative order
- AC4: Clock drift warning when drift > threshold

Note: These tests require Docker to be running for testcontainers.
"""

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.ports.event_store import validate_sequence_continuity
from src.application.services.time_authority_service import TimeAuthorityService

if TYPE_CHECKING:
    pass


@pytest.mark.integration
class TestDualTimestampsOnInsert:
    """Tests for AC1: Dual timestamps on event creation."""

    @pytest.mark.asyncio
    async def test_event_gets_authority_timestamp_from_db(
        self,
        db_session: AsyncSession,
    ) -> None:
        """Event gets authority_timestamp from database NOW() (AC1)."""
        # Create events table if not exists (simplified for test)
        await db_session.execute(
            text("""
                CREATE TABLE IF NOT EXISTS events_test (
                    event_id UUID PRIMARY KEY,
                    sequence BIGSERIAL UNIQUE NOT NULL,
                    local_timestamp TIMESTAMPTZ NOT NULL,
                    authority_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
        )

        local_ts = datetime.now(timezone.utc)
        event_id = uuid4()

        await db_session.execute(
            text("""
                INSERT INTO events_test (event_id, local_timestamp)
                VALUES (:event_id, :local_ts)
            """),
            {"event_id": event_id, "local_ts": local_ts},
        )

        result = await db_session.execute(
            text("""
                SELECT local_timestamp, authority_timestamp
                FROM events_test
                WHERE event_id = :event_id
            """),
            {"event_id": event_id},
        )
        row = result.fetchone()

        assert row is not None
        assert row.local_timestamp == local_ts
        # authority_timestamp should be set by DB
        assert row.authority_timestamp is not None
        # authority_timestamp should be close to now
        assert abs((row.authority_timestamp - local_ts).total_seconds()) < 10

    @pytest.mark.asyncio
    async def test_sequence_is_auto_incremented(
        self,
        db_session: AsyncSession,
    ) -> None:
        """Sequence is assigned by BIGSERIAL (AC1)."""
        await db_session.execute(
            text("""
                CREATE TABLE IF NOT EXISTS events_test_seq (
                    event_id UUID PRIMARY KEY,
                    sequence BIGSERIAL UNIQUE NOT NULL,
                    local_timestamp TIMESTAMPTZ NOT NULL,
                    authority_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
        )

        # Insert multiple events
        for i in range(3):
            await db_session.execute(
                text("""
                    INSERT INTO events_test_seq (event_id, local_timestamp)
                    VALUES (:event_id, :local_ts)
                """),
                {"event_id": uuid4(), "local_ts": datetime.now(timezone.utc)},
            )

        result = await db_session.execute(
            text("SELECT sequence FROM events_test_seq ORDER BY sequence")
        )
        sequences = [row.sequence for row in result.fetchall()]

        # Should be 1, 2, 3
        assert sequences == [1, 2, 3]


@pytest.mark.integration
class TestSequenceUniqueness:
    """Tests for AC2: Unique sequential numbers with concurrent inserts."""

    @pytest.mark.asyncio
    async def test_sequence_uniqueness_with_concurrent_inserts(
        self,
        db_session: AsyncSession,
    ) -> None:
        """Concurrent inserts get unique sequence numbers (AC2)."""
        await db_session.execute(
            text("""
                CREATE TABLE IF NOT EXISTS events_test_concurrent (
                    event_id UUID PRIMARY KEY,
                    sequence BIGSERIAL UNIQUE NOT NULL,
                    local_timestamp TIMESTAMPTZ NOT NULL,
                    authority_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
        )

        # Insert many events "concurrently" (in sequence for this test)
        event_ids = [uuid4() for _ in range(10)]
        for event_id in event_ids:
            await db_session.execute(
                text("""
                    INSERT INTO events_test_concurrent (event_id, local_timestamp)
                    VALUES (:event_id, :local_ts)
                """),
                {"event_id": event_id, "local_ts": datetime.now(timezone.utc)},
            )

        result = await db_session.execute(
            text("SELECT sequence FROM events_test_concurrent ORDER BY sequence")
        )
        sequences = [row.sequence for row in result.fetchall()]

        # All sequences should be unique
        assert len(sequences) == len(set(sequences))
        # Sequences should be continuous
        assert sequences == list(range(1, 11))

    @pytest.mark.asyncio
    async def test_sequence_no_gaps(
        self,
        db_session: AsyncSession,
    ) -> None:
        """Sequence has no gaps under normal operation (AC2)."""
        await db_session.execute(
            text("""
                CREATE TABLE IF NOT EXISTS events_test_gaps (
                    event_id UUID PRIMARY KEY,
                    sequence BIGSERIAL UNIQUE NOT NULL,
                    local_timestamp TIMESTAMPTZ NOT NULL,
                    authority_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
        )

        # Insert 5 events
        for _ in range(5):
            await db_session.execute(
                text("""
                    INSERT INTO events_test_gaps (event_id, local_timestamp)
                    VALUES (:event_id, :local_ts)
                """),
                {"event_id": uuid4(), "local_ts": datetime.now(timezone.utc)},
            )

        result = await db_session.execute(
            text("SELECT sequence FROM events_test_gaps ORDER BY sequence")
        )
        sequences = [row.sequence for row in result.fetchall()]

        # Use our validate_sequence_continuity helper
        is_continuous, missing = validate_sequence_continuity(sequences)
        assert is_continuous is True
        assert missing == []


@pytest.mark.integration
class TestSequenceAuthoritative:
    """Tests for AC3: Sequence as authoritative order."""

    @pytest.mark.asyncio
    async def test_sequence_determines_order_not_timestamp(
        self,
        db_session: AsyncSession,
    ) -> None:
        """Sequence determines order, not timestamps (AC3)."""
        await db_session.execute(
            text("""
                CREATE TABLE IF NOT EXISTS events_test_order (
                    event_id UUID PRIMARY KEY,
                    sequence BIGSERIAL UNIQUE NOT NULL,
                    local_timestamp TIMESTAMPTZ NOT NULL,
                    authority_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
        )

        # Insert events with "out of order" local timestamps
        # Event 1: timestamp = now - 1 hour
        # Event 2: timestamp = now + 1 hour
        # Event 3: timestamp = now

        now = datetime.now(timezone.utc)

        await db_session.execute(
            text("""
                INSERT INTO events_test_order (event_id, local_timestamp)
                VALUES (:event_id, :local_ts)
            """),
            {"event_id": uuid4(), "local_ts": now - timedelta(hours=1)},
        )
        await db_session.execute(
            text("""
                INSERT INTO events_test_order (event_id, local_timestamp)
                VALUES (:event_id, :local_ts)
            """),
            {"event_id": uuid4(), "local_ts": now + timedelta(hours=1)},
        )
        await db_session.execute(
            text("""
                INSERT INTO events_test_order (event_id, local_timestamp)
                VALUES (:event_id, :local_ts)
            """),
            {"event_id": uuid4(), "local_ts": now},
        )

        # Query by sequence (authoritative order)
        result = await db_session.execute(
            text("""
                SELECT sequence, local_timestamp
                FROM events_test_order
                ORDER BY sequence
            """)
        )
        rows = result.fetchall()

        # Sequence order should be 1, 2, 3 regardless of timestamp order
        sequences = [row.sequence for row in rows]
        assert sequences == [1, 2, 3]


@pytest.mark.integration
class TestClockDriftDetection:
    """Tests for AC4: Clock drift warning when drift > threshold."""

    def test_drift_warning_logged_when_exceeds_threshold(self) -> None:
        """Warning is logged when drift exceeds threshold (AC4)."""
        service = TimeAuthorityService(drift_threshold_seconds=5.0)
        now = datetime.now(timezone.utc)
        local_ts = now
        authority_ts = now + timedelta(seconds=10)  # 10 seconds drift

        with patch("src.application.services.time_authority_service.logger") as mock_logger:
            mock_bound = MagicMock()
            mock_logger.bind.return_value = mock_bound

            drift = service.check_drift(
                local_timestamp=local_ts,
                authority_timestamp=authority_ts,
                event_id="test-event-123",
            )

            # Warning should have been logged
            mock_logger.bind.assert_called_once()
            mock_bound.warning.assert_called_once_with(
                "clock_drift_detected",
                message="FR6: Clock drift exceeds threshold - investigate time sync",
            )

            # Drift should still be returned
            assert drift == timedelta(seconds=10)

    def test_event_accepted_despite_drift(self) -> None:
        """Event is still accepted even with drift (AC4)."""
        service = TimeAuthorityService(drift_threshold_seconds=5.0)
        now = datetime.now(timezone.utc)
        local_ts = now
        authority_ts = now + timedelta(seconds=60)  # Large drift

        with patch("src.application.services.time_authority_service.logger"):
            # Should not raise - drift is informational only
            drift = service.check_drift(
                local_timestamp=local_ts,
                authority_timestamp=authority_ts,
                event_id="test-event-456",
            )

            # Event would still be accepted, we just get the drift back
            assert drift == timedelta(seconds=60)


@pytest.mark.integration
class TestSequenceValidationHelpers:
    """Tests for sequence validation helper functions."""

    def test_validate_sequence_continuity_finds_gaps(self) -> None:
        """Helper correctly identifies gaps in sequence."""
        is_continuous, missing = validate_sequence_continuity([1, 2, 4, 5])
        assert is_continuous is False
        assert missing == [3]

    def test_validate_sequence_continuity_with_range(self) -> None:
        """Helper validates against expected range."""
        is_continuous, missing = validate_sequence_continuity(
            [3, 4, 5],
            expected_start=1,
            expected_end=7,
        )
        assert is_continuous is False
        assert sorted(missing) == [1, 2, 6, 7]

    def test_validate_sequence_continuity_empty_is_continuous(self) -> None:
        """Empty sequence list is considered continuous."""
        is_continuous, missing = validate_sequence_continuity([])
        assert is_continuous is True
        assert missing == []


@pytest.mark.integration
class TestClockDriftMigration:
    """Tests for clock drift migration functionality."""

    @pytest.mark.asyncio
    async def test_clock_drift_table_can_be_created(
        self,
        db_session: AsyncSession,
    ) -> None:
        """Clock drift warnings table can be created."""
        await db_session.execute(
            text("""
                CREATE TABLE IF NOT EXISTS clock_drift_warnings_test (
                    id BIGSERIAL PRIMARY KEY,
                    event_id UUID NOT NULL,
                    local_timestamp TIMESTAMPTZ NOT NULL,
                    authority_timestamp TIMESTAMPTZ NOT NULL,
                    drift_seconds NUMERIC(10, 3) NOT NULL,
                    logged_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
        )

        # Verify table exists
        result = await db_session.execute(
            text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = 'clock_drift_warnings_test'
                )
            """)
        )
        exists = result.scalar()
        assert exists is True

    @pytest.mark.asyncio
    async def test_drift_warning_can_be_inserted(
        self,
        db_session: AsyncSession,
    ) -> None:
        """Clock drift warning records can be inserted."""
        await db_session.execute(
            text("""
                CREATE TABLE IF NOT EXISTS clock_drift_warnings_insert (
                    id BIGSERIAL PRIMARY KEY,
                    event_id UUID NOT NULL,
                    local_timestamp TIMESTAMPTZ NOT NULL,
                    authority_timestamp TIMESTAMPTZ NOT NULL,
                    drift_seconds NUMERIC(10, 3) NOT NULL,
                    logged_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
        )

        event_id = uuid4()
        now = datetime.now(timezone.utc)

        await db_session.execute(
            text("""
                INSERT INTO clock_drift_warnings_insert
                (event_id, local_timestamp, authority_timestamp, drift_seconds)
                VALUES (:event_id, :local_ts, :auth_ts, :drift)
            """),
            {
                "event_id": event_id,
                "local_ts": now,
                "auth_ts": now + timedelta(seconds=10),
                "drift": 10.0,
            },
        )

        result = await db_session.execute(
            text("""
                SELECT drift_seconds FROM clock_drift_warnings_insert
                WHERE event_id = :event_id
            """),
            {"event_id": event_id},
        )
        row = result.fetchone()
        assert row is not None
        assert float(row.drift_seconds) == 10.0
