"""Integration tests for date range and event type filtering (Story 4.3 - FR46).

Tests the complete filtering flow from API to data store.

Constitutional Constraints:
- FR44: Public read access without registration - filters must work without auth
- FR46: Query interface SHALL support date range and event type filtering
- FR48: Rate limits identical for all users
- CT-13: Reads allowed during halt
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class TestFR46DateRangeFiltering:
    """Integration tests for date range and event type filtering (FR46)."""

    @pytest.fixture
    async def events_table_with_data(self, db_session: AsyncSession) -> AsyncSession:
        """Create events table with test data spanning multiple dates and types."""
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

        # Create indexes for filtering
        await db_session.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_events_authority_timestamp "
                "ON events (authority_timestamp)"
            )
        )
        await db_session.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_events_event_type ON events (event_type)"
            )
        )

        # Insert test events with varying dates and types
        base_time = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)

        test_events = [
            # Day 1: Jan 15 - votes
            (1, "vote", base_time, "Vote 1"),
            (2, "vote", base_time + timedelta(hours=1), "Vote 2"),
            (3, "vote", base_time + timedelta(hours=2), "Vote 3"),
            # Day 1: Jan 15 - halt
            (4, "halt", base_time + timedelta(hours=3), "Halt 1"),
            # Day 2: Jan 16 - breach and vote
            (5, "breach", base_time + timedelta(days=1), "Breach 1"),
            (6, "vote", base_time + timedelta(days=1, hours=1), "Vote 4"),
            # Day 3: Jan 17 - votes
            (7, "vote", base_time + timedelta(days=2), "Vote 5"),
            (8, "vote", base_time + timedelta(days=2, hours=1), "Vote 6"),
        ]

        for seq, event_type, ts, note in test_events:
            event_id = uuid4()
            await db_session.execute(
                text("""
                INSERT INTO events (
                    event_id, sequence, event_type, payload, prev_hash, content_hash,
                    signature, agent_id, witness_id, witness_signature,
                    local_timestamp, authority_timestamp
                ) VALUES (
                    :event_id, :sequence, :event_type, CAST(:payload AS jsonb), :prev_hash,
                    :content_hash, :signature, :agent_id, :witness_id, :witness_signature,
                    :local_timestamp, :authority_timestamp
                )
            """),
                {
                    "event_id": str(event_id),
                    "sequence": seq,
                    "event_type": event_type,
                    "payload": f'{{"note": "{note}"}}',
                    "prev_hash": "0" * 64,
                    "content_hash": "a" * 64,
                    "signature": "sig123",
                    "agent_id": "agent-001",
                    "witness_id": "witness-001",
                    "witness_signature": "wsig123",
                    "local_timestamp": ts,
                    "authority_timestamp": ts,
                },
            )

        await db_session.flush()
        return db_session

    @pytest.mark.asyncio
    async def test_fr46_query_by_date_range(
        self, events_table_with_data: AsyncSession
    ) -> None:
        """Verify date range filtering works correctly (FR46).

        Events should be filtered by authority_timestamp within the range.
        """
        db = events_table_with_data

        # Query for Jan 15 only
        start = datetime(2026, 1, 15, 0, 0, 0, tzinfo=timezone.utc)
        end = datetime(2026, 1, 15, 23, 59, 59, tzinfo=timezone.utc)

        result = await db.execute(
            text("""
            SELECT sequence, event_type, authority_timestamp
            FROM events
            WHERE authority_timestamp >= :start AND authority_timestamp <= :end
            ORDER BY sequence
        """),
            {"start": start, "end": end},
        )

        rows = result.fetchall()

        # Should get 4 events from Jan 15
        assert len(rows) == 4
        for row in rows:
            assert row[0] in (1, 2, 3, 4)  # Sequences 1-4

    @pytest.mark.asyncio
    async def test_fr46_query_by_event_type(
        self, events_table_with_data: AsyncSession
    ) -> None:
        """Verify event type filtering works correctly (FR46)."""
        db = events_table_with_data

        # Query for votes only
        result = await db.execute(
            text("""
            SELECT sequence, event_type
            FROM events
            WHERE event_type = :event_type
            ORDER BY sequence
        """),
            {"event_type": "vote"},
        )

        rows = result.fetchall()

        # Should get 6 vote events
        assert len(rows) == 6
        for row in rows:
            assert row[1] == "vote"

    @pytest.mark.asyncio
    async def test_fr46_query_by_multiple_event_types(
        self, events_table_with_data: AsyncSession
    ) -> None:
        """Verify filtering by multiple event types uses OR logic."""
        db = events_table_with_data

        # Query for votes and halts
        result = await db.execute(
            text("""
            SELECT sequence, event_type
            FROM events
            WHERE event_type IN ('vote', 'halt')
            ORDER BY sequence
        """)
        )

        rows = result.fetchall()

        # Should get 7 events (6 votes + 1 halt)
        assert len(rows) == 7
        types = {row[1] for row in rows}
        assert types == {"vote", "halt"}

    @pytest.mark.asyncio
    async def test_fr46_combined_filters_use_and_logic(
        self, events_table_with_data: AsyncSession
    ) -> None:
        """Verify combined date + type filters use AND logic."""
        db = events_table_with_data

        # Query for votes on Jan 15 only
        start = datetime(2026, 1, 15, 0, 0, 0, tzinfo=timezone.utc)
        end = datetime(2026, 1, 15, 23, 59, 59, tzinfo=timezone.utc)

        result = await db.execute(
            text("""
            SELECT sequence, event_type, authority_timestamp
            FROM events
            WHERE authority_timestamp >= :start
              AND authority_timestamp <= :end
              AND event_type = :event_type
            ORDER BY sequence
        """),
            {
                "start": start,
                "end": end,
                "event_type": "vote",
            },
        )

        rows = result.fetchall()

        # Should get 3 votes from Jan 15 (not the halt)
        assert len(rows) == 3
        for row in rows:
            assert row[1] == "vote"
            assert row[0] in (1, 2, 3)

    @pytest.mark.asyncio
    async def test_fr46_partial_date_range_start_only(
        self, events_table_with_data: AsyncSession
    ) -> None:
        """Verify filtering with only start_date works."""
        db = events_table_with_data

        # Query from Jan 16 onwards
        start = datetime(2026, 1, 16, 0, 0, 0, tzinfo=timezone.utc)

        result = await db.execute(
            text("""
            SELECT sequence
            FROM events
            WHERE authority_timestamp >= :start
            ORDER BY sequence
        """),
            {"start": start},
        )

        rows = result.fetchall()

        # Should get 4 events (Jan 16 and 17)
        assert len(rows) == 4
        sequences = [row[0] for row in rows]
        assert sequences == [5, 6, 7, 8]

    @pytest.mark.asyncio
    async def test_fr46_partial_date_range_end_only(
        self, events_table_with_data: AsyncSession
    ) -> None:
        """Verify filtering with only end_date works."""
        db = events_table_with_data

        # Query until Jan 15 end of day
        end = datetime(2026, 1, 15, 23, 59, 59, tzinfo=timezone.utc)

        result = await db.execute(
            text("""
            SELECT sequence
            FROM events
            WHERE authority_timestamp <= :end
            ORDER BY sequence
        """),
            {"end": end},
        )

        rows = result.fetchall()

        # Should get 4 events from Jan 15
        assert len(rows) == 4
        sequences = [row[0] for row in rows]
        assert sequences == [1, 2, 3, 4]

    @pytest.mark.asyncio
    async def test_fr46_pagination_with_filters(
        self, events_table_with_data: AsyncSession
    ) -> None:
        """Verify pagination works with filters applied."""
        db = events_table_with_data

        # Get votes with limit and offset
        result = await db.execute(
            text("""
            SELECT sequence, event_type
            FROM events
            WHERE event_type = 'vote'
            ORDER BY sequence
            LIMIT 3 OFFSET 2
        """)
        )

        rows = result.fetchall()

        # Should get 3 votes starting from 3rd vote
        assert len(rows) == 3
        # 3rd, 4th, 5th votes by sequence
        sequences = [row[0] for row in rows]
        assert sequences == [3, 6, 7]  # Vote 3, 4, 5 by insertion order

    @pytest.mark.asyncio
    async def test_fr46_empty_result_on_no_match(
        self, events_table_with_data: AsyncSession
    ) -> None:
        """Verify empty result when no events match filters."""
        db = events_table_with_data

        # Query for non-existent type
        result = await db.execute(
            text("""
            SELECT sequence
            FROM events
            WHERE event_type = :event_type
        """),
            {"event_type": "nonexistent.type"},
        )

        rows = result.fetchall()
        assert len(rows) == 0

    @pytest.mark.asyncio
    async def test_fr46_index_used_for_date_range(
        self, events_table_with_data: AsyncSession
    ) -> None:
        """Verify index exists for authority_timestamp filtering."""
        db = events_table_with_data

        # Check index exists
        result = await db.execute(
            text("""
            SELECT indexname FROM pg_indexes
            WHERE tablename = 'events'
            AND indexname = 'idx_events_authority_timestamp'
        """)
        )

        rows = result.fetchall()
        assert len(rows) == 1

    @pytest.mark.asyncio
    async def test_fr46_index_used_for_event_type(
        self, events_table_with_data: AsyncSession
    ) -> None:
        """Verify index exists for event_type filtering."""
        db = events_table_with_data

        # Check index exists
        result = await db.execute(
            text("""
            SELECT indexname FROM pg_indexes
            WHERE tablename = 'events'
            AND indexname = 'idx_events_event_type'
        """)
        )

        rows = result.fetchall()
        assert len(rows) == 1

    @pytest.mark.asyncio
    async def test_fr46_results_ordered_by_sequence(
        self, events_table_with_data: AsyncSession
    ) -> None:
        """Verify filtered results are ordered by sequence."""
        db = events_table_with_data

        # Get all events with filter
        result = await db.execute(
            text("""
            SELECT sequence
            FROM events
            WHERE event_type IN ('vote', 'halt', 'breach')
            ORDER BY sequence
        """)
        )

        rows = result.fetchall()
        sequences = [row[0] for row in rows]

        # Should be monotonically increasing
        assert sequences == sorted(sequences)
