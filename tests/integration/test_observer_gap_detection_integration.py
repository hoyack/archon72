"""Integration tests for Observer Gap Detection (Story 4.10 - FR122, FR123).

Tests the full workflow of local database gap detection for observers.

These tests use Python imports directly since archon72-verify CLI is not
installed system-wide. The CLI functionality is tested via typer.testing.
"""

import json
import sqlite3
import sys
import tempfile
from pathlib import Path

import pytest

# Add tools path to sys.path for imports
TOOLS_PATH = Path(__file__).parent.parent.parent / "tools" / "archon72-verify"
if str(TOOLS_PATH) not in sys.path:
    sys.path.insert(0, str(TOOLS_PATH))

from typer.testing import CliRunner

from archon72_verify.cli import app
from archon72_verify.database import ObserverDatabase


runner = CliRunner()


@pytest.fixture
def temp_db_path():
    """Create a temporary database path."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir) / "events.db"


def insert_test_events(db_path: Path, sequences: list[int]) -> None:
    """Insert test events into database."""
    conn = sqlite3.connect(str(db_path))
    for seq in sequences:
        conn.execute(
            """
            INSERT INTO events (
                event_id, sequence, event_type, payload, content_hash, prev_hash,
                signature, agent_id, witness_id, witness_signature,
                local_timestamp, authority_timestamp, hash_algorithm_version, sig_alg_version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"evt-{seq}",
                seq,
                "test",
                "{}",
                f"hash_{seq}",
                f"hash_{seq-1}" if seq > 1 else "0" * 64,
                "sig",
                None,
                "witness",
                "wsig",
                "2026-01-01T00:00:00Z",
                None,
                "1.0",
                "ed25519-v1",
            ),
        )
    conn.commit()
    conn.close()


class TestObserverLocalDatabaseInit:
    """Tests for AC4: init-db creates the required schema."""

    def test_observer_can_init_local_database(self, temp_db_path: Path):
        """AC4: archon72-verify init-db ./events.db creates the required schema."""
        result = runner.invoke(app, ["init-db", str(temp_db_path)])

        assert result.exit_code == 0
        assert "initialized" in result.stdout.lower()
        assert temp_db_path.exists()

        # Verify schema was created
        conn = sqlite3.connect(str(temp_db_path))
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        tables = {row[0] for row in cursor.fetchall()}
        conn.close()

        assert "events" in tables

    def test_init_db_creates_indexes(self, temp_db_path: Path):
        """Verify indexes are created for performance."""
        runner.invoke(app, ["init-db", str(temp_db_path)])

        conn = sqlite3.connect(str(temp_db_path))
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index'"
        )
        indexes = {row[0] for row in cursor.fetchall()}
        conn.close()

        assert "idx_events_sequence" in indexes


class TestObserverGapDetection:
    """Tests for AC1, AC2: Gap detection in local database."""

    def test_gap_detection_finds_missing_events(self, temp_db_path: Path):
        """AC1: check-gaps --local-db detects sequence gaps in local copy."""
        # Initialize database
        runner.invoke(app, ["init-db", str(temp_db_path)])

        # Insert events with gap (100, 101, 104, 105)
        insert_test_events(temp_db_path, [100, 101, 104, 105])

        # Run gap detection
        result = runner.invoke(
            app, ["check-gaps", "--local-db", str(temp_db_path)]
        )

        assert result.exit_code == 1  # Exit 1 = gaps found
        assert "102" in result.stdout
        assert "103" in result.stdout

    def test_gap_report_format_includes_ranges(self, temp_db_path: Path):
        """AC2: Gap detection reports gap ranges (start, end sequences)."""
        runner.invoke(app, ["init-db", str(temp_db_path)])

        # Insert events with gaps: 3-4, 7-9
        insert_test_events(temp_db_path, [1, 2, 5, 6, 10])

        # Run gap detection with JSON output
        result = runner.invoke(
            app,
            ["check-gaps", "--local-db", str(temp_db_path), "--format", "json"],
        )

        output = json.loads(result.stdout)
        assert "gaps" in output
        assert "total_gaps" in output
        assert "total_missing_events" in output
        assert output["total_gaps"] == 2
        # 3-4 = 2 events, 7-9 = 3 events = 5 total
        assert output["total_missing_events"] == 5

    def test_no_gaps_returns_success(self, temp_db_path: Path):
        """Verify no gaps returns success (exit code 0)."""
        runner.invoke(app, ["init-db", str(temp_db_path)])

        # Insert continuous events
        insert_test_events(temp_db_path, [1, 2, 3, 4, 5])

        result = runner.invoke(
            app, ["check-gaps", "--local-db", str(temp_db_path)]
        )

        assert result.exit_code == 0
        assert "No gaps" in result.stdout


class TestObserverOfflineVerification:
    """Tests for offline gap detection without API access."""

    def test_offline_gap_detection_no_api_required(self, temp_db_path: Path):
        """Verify gap detection works without API access (offline mode)."""
        # Initialize database
        runner.invoke(app, ["init-db", str(temp_db_path)])

        # Insert events directly
        insert_test_events(temp_db_path, [1, 2, 3, 4, 5])

        # Run without any network (--api-url not specified)
        # This should work completely offline
        result = runner.invoke(
            app, ["check-gaps", "--local-db", str(temp_db_path)]
        )

        assert result.exit_code == 0
        assert "No gaps" in result.stdout


class TestObserverFillGapsCommand:
    """Tests for AC3: fill-gaps command."""

    def test_fill_gaps_command_exists(self):
        """Verify fill-gaps command exists."""
        result = runner.invoke(app, ["fill-gaps", "--help"])

        assert result.exit_code == 0
        assert "fill-gaps" in result.stdout
        assert "--local-db" in result.stdout

    def test_fill_gaps_with_no_gaps(self, temp_db_path: Path):
        """Verify fill-gaps with no gaps returns success."""
        runner.invoke(app, ["init-db", str(temp_db_path)])

        # Insert continuous events
        insert_test_events(temp_db_path, [1, 2, 3])

        result = runner.invoke(
            app,
            ["fill-gaps", "--local-db", str(temp_db_path), "--no-verify"],
        )

        assert result.exit_code == 0
        assert "No gaps to fill" in result.stdout


class TestObserverSyncCommand:
    """Tests for sync command."""

    def test_sync_command_exists(self):
        """Verify sync command exists."""
        result = runner.invoke(app, ["sync", "--help"])

        assert result.exit_code == 0
        assert "sync" in result.stdout
        assert "--local-db" in result.stdout
        assert "--batch-size" in result.stdout


class TestObserverDatabaseAPI:
    """Tests for ObserverDatabase API integration."""

    def test_full_workflow_init_insert_detect(self, temp_db_path: Path):
        """Test full workflow: init → insert → detect gaps."""
        # 1. Initialize database
        with ObserverDatabase(temp_db_path) as db:
            db.init_schema()

        # 2. Insert events with gap
        with ObserverDatabase(temp_db_path) as db:
            for seq in [1, 2, 5, 6]:
                db.insert_event({
                    "event_id": f"evt-{seq}",
                    "sequence": seq,
                    "event_type": "test",
                    "payload": {"data": seq},
                    "content_hash": f"hash_{seq}",
                    "prev_hash": f"hash_{seq-1}" if seq > 1 else "0" * 64,
                    "signature": "sig",
                    "agent_id": None,
                    "witness_id": "witness",
                    "witness_signature": "wsig",
                    "local_timestamp": "2026-01-01T00:00:00Z",
                    "authority_timestamp": None,
                    "hash_algorithm_version": "1.0",
                    "sig_alg_version": "ed25519-v1",
                })

        # 3. Detect gaps
        with ObserverDatabase(temp_db_path) as db:
            gaps = db.find_gaps()

        assert len(gaps) == 1
        assert gaps[0] == (3, 4)

    def test_event_count_tracking(self, temp_db_path: Path):
        """Verify event count is tracked correctly."""
        with ObserverDatabase(temp_db_path) as db:
            db.init_schema()
            assert db.get_event_count() == 0

            for seq in range(1, 101):
                db.insert_event({
                    "event_id": f"evt-{seq}",
                    "sequence": seq,
                    "event_type": "test",
                    "payload": {},
                    "content_hash": f"hash_{seq}",
                    "prev_hash": f"hash_{seq-1}" if seq > 1 else "0" * 64,
                    "signature": "sig",
                    "agent_id": None,
                    "witness_id": "witness",
                    "witness_signature": "wsig",
                    "local_timestamp": "2026-01-01T00:00:00Z",
                    "authority_timestamp": None,
                    "hash_algorithm_version": "1.0",
                    "sig_alg_version": "ed25519-v1",
                })

            assert db.get_event_count() == 100

    def test_sequence_range_query(self, temp_db_path: Path):
        """Verify sequence range queries work correctly."""
        with ObserverDatabase(temp_db_path) as db:
            db.init_schema()

            # Insert events 100-200
            for seq in range(100, 201):
                db.insert_event({
                    "event_id": f"evt-{seq}",
                    "sequence": seq,
                    "event_type": "test",
                    "payload": {},
                    "content_hash": f"hash_{seq}",
                    "prev_hash": f"hash_{seq-1}" if seq > 100 else "0" * 64,
                    "signature": "sig",
                    "agent_id": None,
                    "witness_id": "witness",
                    "witness_signature": "wsig",
                    "local_timestamp": "2026-01-01T00:00:00Z",
                    "authority_timestamp": None,
                    "hash_algorithm_version": "1.0",
                    "sig_alg_version": "ed25519-v1",
                })

            min_seq, max_seq = db.get_sequence_range()
            assert min_seq == 100
            assert max_seq == 200
