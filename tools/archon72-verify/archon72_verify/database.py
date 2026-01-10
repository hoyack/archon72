"""SQLite database support for local observer storage (FR122-FR123).

Provides local storage for observers to maintain their own copy of the
event chain for offline verification and gap detection.

FR122: Verification toolkit SHALL detect sequence gaps in observer's local copy
FR123: Gap detection SHALL report gap ranges (start, end sequences)
"""

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class LocalEvent:
    """Event stored in local database.

    Matches ObserverEventResponse structure for verification.
    """

    event_id: str
    sequence: int
    event_type: str
    payload: str  # JSON string
    content_hash: str
    prev_hash: str
    signature: str
    agent_id: Optional[str]
    witness_id: str
    witness_signature: str
    local_timestamp: str
    authority_timestamp: Optional[str]
    hash_algorithm_version: str
    sig_alg_version: str


class ObserverDatabase:
    """SQLite database for local observer event storage.

    Per FR122: Detect sequence gaps in local copy.
    Per FR123: Report gap ranges.

    Attributes:
        path: Path to SQLite database file.

    Example:
        with ObserverDatabase("./events.db") as db:
            db.init_schema()
            db.insert_events(events)
            gaps = db.find_gaps()
    """

    SCHEMA = """
    CREATE TABLE IF NOT EXISTS events (
        event_id TEXT PRIMARY KEY,
        sequence INTEGER UNIQUE NOT NULL,
        event_type TEXT NOT NULL,
        payload TEXT NOT NULL,
        content_hash TEXT NOT NULL,
        prev_hash TEXT NOT NULL,
        signature TEXT NOT NULL,
        agent_id TEXT,
        witness_id TEXT NOT NULL,
        witness_signature TEXT NOT NULL,
        local_timestamp TEXT NOT NULL,
        authority_timestamp TEXT,
        hash_algorithm_version TEXT NOT NULL,
        sig_alg_version TEXT NOT NULL
    );

    CREATE INDEX IF NOT EXISTS idx_events_sequence ON events(sequence);
    CREATE INDEX IF NOT EXISTS idx_events_event_type ON events(event_type);
    """

    def __init__(self, path: str | Path) -> None:
        """Initialize database connection.

        Args:
            path: Path to SQLite database file.
        """
        self.path = Path(path)
        self._conn: Optional[sqlite3.Connection] = None

    def connect(self) -> None:
        """Open database connection."""
        self._conn = sqlite3.connect(str(self.path))
        self._conn.row_factory = sqlite3.Row

    def close(self) -> None:
        """Close database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

    def init_schema(self) -> None:
        """Initialize database schema.

        Creates events table if not exists.
        """
        if not self._conn:
            raise RuntimeError("Database not connected")
        self._conn.executescript(self.SCHEMA)
        self._conn.commit()

    def insert_event(self, event: dict) -> None:
        """Insert event into local database.

        Args:
            event: Event dictionary from Observer API.
        """
        if not self._conn:
            raise RuntimeError("Database not connected")

        # Convert payload to JSON string if dict
        payload = event["payload"]
        if isinstance(payload, dict):
            payload = json.dumps(payload, sort_keys=True, separators=(",", ":"))

        self._conn.execute(
            """
            INSERT OR REPLACE INTO events (
                event_id, sequence, event_type, payload, content_hash, prev_hash,
                signature, agent_id, witness_id, witness_signature,
                local_timestamp, authority_timestamp, hash_algorithm_version, sig_alg_version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event["event_id"],
                event["sequence"],
                event["event_type"],
                payload,
                event["content_hash"],
                event["prev_hash"],
                event["signature"],
                event.get("agent_id"),
                event["witness_id"],
                event["witness_signature"],
                event["local_timestamp"],
                event.get("authority_timestamp"),
                event["hash_algorithm_version"],
                event["sig_alg_version"],
            ),
        )
        self._conn.commit()

    def insert_events(self, events: list[dict]) -> int:
        """Insert multiple events.

        Args:
            events: List of event dictionaries.

        Returns:
            Number of events inserted.
        """
        for event in events:
            self.insert_event(event)
        return len(events)

    def get_all_sequences(self) -> list[int]:
        """Get all sequence numbers in database.

        Returns:
            Sorted list of sequence numbers.
        """
        if not self._conn:
            raise RuntimeError("Database not connected")

        cursor = self._conn.execute("SELECT sequence FROM events ORDER BY sequence")
        return [row[0] for row in cursor.fetchall()]

    def get_sequence_range(self) -> tuple[Optional[int], Optional[int]]:
        """Get min and max sequence numbers.

        Returns:
            Tuple of (min_sequence, max_sequence) or (None, None) if empty.
        """
        if not self._conn:
            raise RuntimeError("Database not connected")

        cursor = self._conn.execute(
            "SELECT MIN(sequence), MAX(sequence) FROM events"
        )
        row = cursor.fetchone()
        return (row[0], row[1])

    def get_event_count(self) -> int:
        """Get total number of events in database.

        Returns:
            Event count.
        """
        if not self._conn:
            raise RuntimeError("Database not connected")

        cursor = self._conn.execute("SELECT COUNT(*) FROM events")
        return cursor.fetchone()[0]

    def get_events_in_range(
        self,
        start: int,
        end: int,
    ) -> list[dict]:
        """Get events in sequence range.

        Args:
            start: First sequence number.
            end: Last sequence number.

        Returns:
            List of event dictionaries.
        """
        if not self._conn:
            raise RuntimeError("Database not connected")

        cursor = self._conn.execute(
            """
            SELECT * FROM events
            WHERE sequence >= ? AND sequence <= ?
            ORDER BY sequence
            """,
            (start, end),
        )

        events = []
        for row in cursor.fetchall():
            event = dict(row)
            # Parse payload back to dict
            if event["payload"]:
                try:
                    event["payload"] = json.loads(event["payload"])
                except json.JSONDecodeError:
                    pass
            events.append(event)

        return events

    def find_gaps(
        self,
        start: Optional[int] = None,
        end: Optional[int] = None,
    ) -> list[tuple[int, int]]:
        """Find sequence gaps in local database.

        Per FR122: Detect sequence gaps in local copy.
        Per FR123: Report gap ranges.

        Args:
            start: Start of range to check (default: min sequence).
            end: End of range to check (default: max sequence).

        Returns:
            List of (gap_start, gap_end) tuples.
        """
        if not self._conn:
            raise RuntimeError("Database not connected")

        sequences = self.get_all_sequences()

        if not sequences:
            return []

        # Apply range filters
        if start is not None:
            sequences = [s for s in sequences if s >= start]
        if end is not None:
            sequences = [s for s in sequences if s <= end]

        if not sequences:
            return []

        # Find gaps
        gaps: list[tuple[int, int]] = []

        for i in range(1, len(sequences)):
            prev_seq = sequences[i - 1]
            curr_seq = sequences[i]

            if curr_seq != prev_seq + 1:
                # Gap detected: missing sequences from prev_seq+1 to curr_seq-1
                gaps.append((prev_seq + 1, curr_seq - 1))

        return gaps

    def __enter__(self) -> "ObserverDatabase":
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.close()
