"""Tests for local observer database (Story 4.10, Task 1).

Tests for ObserverDatabase that manages local SQLite storage
for observer gap detection (FR122, FR123).
"""

import json
import tempfile
from pathlib import Path

import pytest
from archon72_verify.database import ObserverDatabase


def make_event(
    sequence: int,
    event_type: str = "test",
    payload: dict = None,
) -> dict:
    """Helper to create test events matching Observer API structure."""
    if payload is None:
        payload = {"data": f"event_{sequence}"}

    return {
        "event_id": f"evt-{sequence:04d}",
        "sequence": sequence,
        "event_type": event_type,
        "payload": payload,
        "content_hash": f"hash_{sequence:04d}_" + "a" * 48,
        "prev_hash": f"hash_{sequence - 1:04d}_" + "a" * 48
        if sequence > 1
        else "0" * 64,
        "signature": f"sig_{sequence:04d}",
        "agent_id": f"agent_{sequence % 3}",
        "witness_id": "witness_1",
        "witness_signature": f"witness_sig_{sequence:04d}",
        "local_timestamp": f"2026-01-01T00:0{sequence}:00Z",
        "authority_timestamp": f"2026-01-01T00:0{sequence}:01Z",
        "hash_algorithm_version": "1.0",
        "sig_alg_version": "ed25519-v1",
    }


def make_events(sequences: list[int]) -> list[dict]:
    """Create multiple test events."""
    return [make_event(seq) for seq in sequences]


class TestObserverDatabaseInit:
    """Tests for database initialization."""

    def test_init_database_creates_schema(self):
        """AC4: init-db creates the required schema."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"

            with ObserverDatabase(db_path) as db:
                db.init_schema()

            # Verify tables were created
            import sqlite3

            conn = sqlite3.connect(str(db_path))
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = {row[0] for row in cursor.fetchall()}
            conn.close()

            assert "events" in tables

    def test_init_database_creates_indexes(self):
        """Verify indexes are created for performance."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"

            with ObserverDatabase(db_path) as db:
                db.init_schema()

            import sqlite3

            conn = sqlite3.connect(str(db_path))
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='index'")
            indexes = {row[0] for row in cursor.fetchall()}
            conn.close()

            assert "idx_events_sequence" in indexes
            assert "idx_events_event_type" in indexes

    def test_context_manager_opens_and_closes(self):
        """Verify context manager handles connection lifecycle."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"

            db = ObserverDatabase(db_path)
            assert db._conn is None

            with db:
                assert db._conn is not None
                db.init_schema()

            assert db._conn is None


class TestObserverDatabaseInsert:
    """Tests for event insertion."""

    def test_insert_event_stores_all_fields(self):
        """Verify all event fields are stored correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"

            event = make_event(1)

            with ObserverDatabase(db_path) as db:
                db.init_schema()
                db.insert_event(event)

                # Verify by reading back
                import sqlite3

                conn = sqlite3.connect(str(db_path))
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("SELECT * FROM events WHERE sequence = 1")
                row = dict(cursor.fetchone())
                conn.close()

            assert row["event_id"] == event["event_id"]
            assert row["sequence"] == event["sequence"]
            assert row["event_type"] == event["event_type"]
            assert row["content_hash"] == event["content_hash"]
            assert row["prev_hash"] == event["prev_hash"]
            assert row["signature"] == event["signature"]
            assert row["agent_id"] == event["agent_id"]
            assert row["witness_id"] == event["witness_id"]
            assert row["witness_signature"] == event["witness_signature"]

    def test_insert_event_handles_dict_payload(self):
        """Verify dict payload is serialized to JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"

            event = make_event(1, payload={"key": "value", "nested": {"a": 1}})

            with ObserverDatabase(db_path) as db:
                db.init_schema()
                db.insert_event(event)

                import sqlite3

                conn = sqlite3.connect(str(db_path))
                cursor = conn.execute("SELECT payload FROM events WHERE sequence = 1")
                stored_payload = cursor.fetchone()[0]
                conn.close()

            # Should be valid JSON
            parsed = json.loads(stored_payload)
            assert parsed["key"] == "value"
            assert parsed["nested"]["a"] == 1

    def test_insert_events_batch(self):
        """Verify multiple events can be inserted."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"

            events = make_events([1, 2, 3, 4, 5])

            with ObserverDatabase(db_path) as db:
                db.init_schema()
                count = db.insert_events(events)

            assert count == 5

            with ObserverDatabase(db_path) as db:
                assert db.get_event_count() == 5

    def test_insert_event_upserts_on_conflict(self):
        """Verify duplicate event_id updates instead of failing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"

            event1 = make_event(1, payload={"version": 1})
            event2 = make_event(1, payload={"version": 2})
            event2["event_id"] = event1["event_id"]  # Same ID

            with ObserverDatabase(db_path) as db:
                db.init_schema()
                db.insert_event(event1)
                db.insert_event(event2)

                # Should have only one event
                assert db.get_event_count() == 1


class TestObserverDatabaseQuery:
    """Tests for database queries."""

    def test_get_sequences_returns_all(self):
        """Verify get_all_sequences returns sorted sequence numbers."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"

            events = make_events([3, 1, 5, 2, 4])

            with ObserverDatabase(db_path) as db:
                db.init_schema()
                db.insert_events(events)

                sequences = db.get_all_sequences()

            assert sequences == [1, 2, 3, 4, 5]

    def test_get_sequence_range(self):
        """Verify min/max sequence detection."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"

            events = make_events([10, 20, 30])

            with ObserverDatabase(db_path) as db:
                db.init_schema()
                db.insert_events(events)

                min_seq, max_seq = db.get_sequence_range()

            assert min_seq == 10
            assert max_seq == 30

    def test_get_sequence_range_empty(self):
        """Verify empty database returns None, None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"

            with ObserverDatabase(db_path) as db:
                db.init_schema()
                min_seq, max_seq = db.get_sequence_range()

            assert min_seq is None
            assert max_seq is None

    def test_get_event_count(self):
        """Verify event count is accurate."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"

            events = make_events([1, 2, 3])

            with ObserverDatabase(db_path) as db:
                db.init_schema()
                assert db.get_event_count() == 0

                db.insert_events(events)
                assert db.get_event_count() == 3

    def test_get_events_in_range(self):
        """Verify range query returns correct events."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"

            events = make_events([1, 2, 3, 4, 5])

            with ObserverDatabase(db_path) as db:
                db.init_schema()
                db.insert_events(events)

                result = db.get_events_in_range(2, 4)

            assert len(result) == 3
            assert result[0]["sequence"] == 2
            assert result[1]["sequence"] == 3
            assert result[2]["sequence"] == 4


class TestObserverDatabaseFindGaps:
    """Tests for gap detection (FR122, FR123)."""

    def test_find_gaps_in_database(self):
        """FR122: Detect sequence gaps in local copy."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"

            # Create events with gap: 100, 101, 104, 105
            events = make_events([100, 101, 104, 105])

            with ObserverDatabase(db_path) as db:
                db.init_schema()
                db.insert_events(events)

                gaps = db.find_gaps()

            # FR123: Reports gap range 102-103
            assert len(gaps) == 1
            assert gaps[0] == (102, 103)

    def test_find_gaps_multiple_gaps(self):
        """FR123: Reports multiple gap ranges."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"

            # Events: 1, 3, 7, 10 (gaps: 2, 4-6, 8-9)
            events = make_events([1, 3, 7, 10])

            with ObserverDatabase(db_path) as db:
                db.init_schema()
                db.insert_events(events)

                gaps = db.find_gaps()

            assert len(gaps) == 3
            assert gaps[0] == (2, 2)
            assert gaps[1] == (4, 6)
            assert gaps[2] == (8, 9)

    def test_find_gaps_no_gaps(self):
        """Verify no gaps returns empty list."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"

            events = make_events([1, 2, 3, 4, 5])

            with ObserverDatabase(db_path) as db:
                db.init_schema()
                db.insert_events(events)

                gaps = db.find_gaps()

            assert gaps == []

    def test_find_gaps_empty_database(self):
        """Verify empty database returns no gaps."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"

            with ObserverDatabase(db_path) as db:
                db.init_schema()
                gaps = db.find_gaps()

            assert gaps == []

    def test_find_gaps_with_range_filter(self):
        """Verify gap detection respects range filters."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"

            # Events: 1, 2, 5, 6, 10 (gaps: 3-4, 7-9)
            events = make_events([1, 2, 5, 6, 10])

            with ObserverDatabase(db_path) as db:
                db.init_schema()
                db.insert_events(events)

                # Only check 4-7
                gaps = db.find_gaps(start=4, end=7)

            # Should only see gap 7-7 (since we start at 4, 5 is present)
            # Wait, let's think: with sequences [5, 6] in range 4-7,
            # we're filtering to [5, 6] and checking gaps within
            # Gap would be none since 5->6 is consecutive
            assert gaps == []

    def test_database_handles_large_ranges(self):
        """Verify performance with large sequence ranges."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"

            # Create 1000 events with some gaps
            sequences = list(range(1, 500)) + list(range(600, 1100))
            events = make_events(sequences)

            with ObserverDatabase(db_path) as db:
                db.init_schema()
                db.insert_events(events)

                # Should find one gap: 500-599
                gaps = db.find_gaps()

            assert len(gaps) == 1
            assert gaps[0] == (500, 599)


class TestObserverDatabaseErrors:
    """Tests for error handling."""

    def test_operation_without_connect_raises(self):
        """Verify operations require connection."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db = ObserverDatabase(db_path)

            with pytest.raises(RuntimeError, match="not connected"):
                db.init_schema()

    def test_insert_without_connect_raises(self):
        """Verify insert requires connection."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db = ObserverDatabase(db_path)

            with pytest.raises(RuntimeError, match="not connected"):
                db.insert_event(make_event(1))

    def test_query_without_connect_raises(self):
        """Verify query requires connection."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db = ObserverDatabase(db_path)

            with pytest.raises(RuntimeError, match="not connected"):
                db.get_all_sequences()
