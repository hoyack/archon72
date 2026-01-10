# Story 4.10: Sequence Gap Detection for Observers (FR122-FR123)

## Story

**As an** external observer,
**I want** to detect sequence gaps in my local copy,
**So that** I know if I'm missing events.

## Status

Status: done

## Context

### Business Context
This is the **final story in Epic 4** (Observer Verification Interface). It extends the verification toolkit (Story 4.4) to support **local database gap detection** for observers who maintain their own synchronized copy of the Archon 72 event chain.

Key business drivers:
1. **Data completeness assurance**: Observers maintaining local copies need to verify they have all events
2. **Missing event identification**: When gaps are detected, observers need to know exactly which events to fetch
3. **Offline verification**: Gap detection must work on local databases without requiring API access
4. **Self-healing capability**: After detecting gaps, observers should be able to fill them and re-verify

**Story 4.4 Delivered** (verification toolkit baseline):
- CLI `check-gaps` command for API-based gap detection
- `ChainVerifier._find_sequence_gaps()` method for in-memory events
- Offline verification via `--file events.json`

**Story 4.10 Extends** to support:
- Local SQLite database storage for observers
- `--local-db ./events.db` flag for database-based gap detection
- Gap filling workflow with API fetch
- Re-verification after gap filling

### Technical Context
- **FR122**: Observer gap detection in local copy (detect missing sequence numbers)
- **FR123**: Gap range reporting (report exactly which sequences are missing)
- **ADR-8**: Observer Consistency + Genesis Anchor - observers catch up via checkpoints
- **ADR-9**: Claim Verification Matrix - verification capabilities

**Existing Toolkit Implementation** (`tools/archon72-verify/`):
- `archon72_verify/cli.py` - Typer CLI with `check-gaps` command
- `archon72_verify/verifier.py` - `ChainVerifier` class with `_find_sequence_gaps()`
- `archon72_verify/client.py` - `ObserverClient` for API access
- Gap detection for in-memory events and JSON files

**Key Files:**
- `tools/archon72-verify/archon72_verify/cli.py` - CLI entry point
- `tools/archon72-verify/archon72_verify/verifier.py` - Verification logic
- `tools/archon72-verify/archon72_verify/client.py` - Observer API client

### Dependencies
- **Story 4.4**: Open-source verification toolkit (DONE) - provides base toolkit
- **Story 4.9**: Observer API uptime SLA (DONE) - API availability for gap filling

### Constitutional Constraints
- **FR122**: Verification toolkit SHALL detect sequence gaps in observer's local copy
- **FR123**: Gap detection SHALL report gap ranges (start, end sequences)
- **CT-7**: Genesis anchoring - local database must include genesis event
- **CT-11**: Silent failure destroys legitimacy - gaps MUST be detected, not hidden
- **ADR-8**: Observers catch up via checkpoint anchors after detecting gaps

### Architecture Decisions
Per ADR-8 (Observer Consistency + Genesis Anchor):
- Observers may maintain local copies of the event chain
- Local copies require periodic synchronization with authoritative store
- Gap detection enables observers to identify synchronization issues
- Observer catch-up: verify all checkpoints since last healthy timestamp

Per Story 4.4 (verification toolkit design):
- SQLite chosen for local observer storage (portable, no server needed)
- Same hash verification spec as API-based verification
- Typer CLI pattern maintained for consistency

## Acceptance Criteria

### AC1: Local database gap detection via CLI
**Given** the verification toolkit
**When** I run `archon72-verify check-gaps --local-db ./events.db`
**Then** it detects any sequence gaps in my local copy
**And** reports gap ranges (start sequence, end sequence)

### AC2: Gap range reporting
**Given** a gap is detected (e.g., have 100, 101, 104, 105)
**When** the detector identifies it
**Then** it reports gap range: 102-103
**And** provides total count of missing events

### AC3: Gap filling via API
**Given** a gap is detected
**When** I query the API for missing events
**Then** I can fill the gap with `archon72-verify fill-gaps --local-db ./events.db`
**And** the toolkit re-verifies after filling

### AC4: Database schema for local observer storage
**Given** an observer wants to maintain a local copy
**When** they initialize the database
**Then** `archon72-verify init-db ./events.db` creates the required schema
**And** schema matches event structure for verification

## Tasks

### Task 1: Add SQLite database support to toolkit

Add local database support for observer storage.

**Files:**
- `tools/archon72-verify/archon72_verify/database.py` (new)
- `tools/archon72-verify/tests/test_database.py` (new)

**Test Cases (RED):**
- `test_init_database_creates_schema`
- `test_insert_event_stores_all_fields`
- `test_get_sequences_returns_all`
- `test_find_gaps_in_database`
- `test_database_handles_large_ranges`

**Implementation (GREEN):**
```python
"""SQLite database support for local observer storage (FR122-FR123)."""

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
            import json
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
        self, start: int, end: int
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

        import json
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
```

### Task 2: Extend CLI with local database commands

Add `--local-db` flag to `check-gaps` and new commands.

**Files:**
- `tools/archon72-verify/archon72_verify/cli.py` (modify)
- `tools/archon72-verify/tests/test_cli.py` (modify)

**Test Cases (RED):**
- `test_cli_check_gaps_with_local_db`
- `test_cli_init_db_creates_database`
- `test_cli_fill_gaps_fetches_and_inserts`
- `test_cli_sync_command`

**Implementation (GREEN):**
```python
# Add to cli.py

from archon72_verify.database import ObserverDatabase


@app.command()
def init_db(
    db_path: Path = typer.Argument(
        ...,
        help="Path to SQLite database file to create",
    ),
) -> None:
    """Initialize local observer database.

    Creates SQLite database with schema for storing events.

    Example:
        archon72-verify init-db ./events.db
    """
    if db_path.exists():
        console.print(f"[yellow]Warning: {db_path} already exists[/yellow]")
        if not typer.confirm("Reinitialize schema?"):
            raise typer.Exit(1)

    with ObserverDatabase(db_path) as db:
        db.init_schema()

    console.print(f"[green]Database initialized: {db_path}[/green]")


@app.command()
def check_gaps(
    from_seq: int = typer.Option(
        1,
        "--from",
        "-f",
        help="First sequence number",
    ),
    to_seq: Optional[int] = typer.Option(
        None,
        "--to",
        "-t",
        help="Last sequence number (default: max in local db or required for API)",
    ),
    api_url: Optional[str] = typer.Option(
        None,
        "--api-url",
        "-u",
        help="API base URL",
    ),
    local_db: Optional[Path] = typer.Option(
        None,
        "--local-db",
        "-d",
        help="Local SQLite database file (FR122)",
    ),
    file: Optional[Path] = typer.Option(
        None,
        "--file",
        "-F",
        help="Local events file (JSON)",
    ),
    output_format: str = typer.Option(
        "text",
        "--format",
        "-o",
        help="Output format: text or json",
    ),
) -> None:
    """Detect sequence gaps in events (FR122-FR123).

    Checks for missing sequence numbers in:
    - Local SQLite database (--local-db)
    - Local JSON file (--file)
    - Observer API (default)

    Examples:
        archon72-verify check-gaps --local-db ./events.db
        archon72-verify check-gaps --from 1 --to 1000
        archon72-verify check-gaps --file events.json --from 1 --to 100
    """
    # Validate: exactly one source
    sources = [local_db, file, (api_url or not local_db and not file)]

    if local_db:
        # Local database mode (FR122)
        result = _check_gaps_local_db(local_db, from_seq, to_seq)
    elif file:
        # File mode
        result = asyncio.run(_check_gaps_async(from_seq, to_seq, api_url, file))
    else:
        # API mode
        if to_seq is None:
            console.print("[red]--to is required for API mode[/red]")
            raise typer.Exit(1)
        result = asyncio.run(_check_gaps_async(from_seq, to_seq, api_url, None))

    _output_gaps(result, output_format, local_db)


def _check_gaps_local_db(
    db_path: Path,
    from_seq: int,
    to_seq: Optional[int],
) -> list[tuple[int, int]]:
    """Check gaps in local database.

    Per FR122: Detect sequence gaps in local copy.
    """
    if not db_path.exists():
        console.print(f"[red]Database not found: {db_path}[/red]")
        console.print("Run 'archon72-verify init-db' first")
        raise typer.Exit(1)

    with ObserverDatabase(db_path) as db:
        min_seq, max_seq = db.get_sequence_range()

        if min_seq is None:
            console.print("[yellow]Database is empty[/yellow]")
            return []

        console.print(f"Database range: {min_seq} - {max_seq}", style="dim")
        console.print(f"Events in database: {db.get_event_count()}", style="dim")

        # Use max_seq as default end if not specified
        if to_seq is None:
            to_seq = max_seq

        return db.find_gaps(from_seq, to_seq)


def _output_gaps(
    gaps: list[tuple[int, int]],
    format: str,
    db_path: Optional[Path] = None,
) -> None:
    """Output gap detection results (FR123)."""
    # Calculate total missing events
    total_missing = sum(end - start + 1 for start, end in gaps)

    if format == "json":
        output = {
            "gaps": [{"start": s, "end": e, "count": e - s + 1} for s, e in gaps],
            "total_gaps": len(gaps),
            "total_missing_events": total_missing,
        }
        if db_path:
            output["database"] = str(db_path)
        console.print_json(json.dumps(output))
    else:
        if not gaps:
            console.print("[green]No gaps found - sequence is complete[/green]")
        else:
            console.print(f"[yellow]Found {len(gaps)} gap(s) ({total_missing} missing events):[/yellow]")

            table = Table()
            table.add_column("Gap #", style="dim")
            table.add_column("Start", justify="right")
            table.add_column("End", justify="right")
            table.add_column("Missing", justify="right")

            for i, (start, end) in enumerate(gaps, 1):
                table.add_row(
                    str(i),
                    str(start),
                    str(end),
                    str(end - start + 1),
                )

            console.print(table)

            if db_path:
                console.print(
                    f"\nTo fill gaps: archon72-verify fill-gaps --local-db {db_path}",
                    style="dim",
                )

            sys.exit(1)


@app.command()
def fill_gaps(
    local_db: Path = typer.Option(
        ...,
        "--local-db",
        "-d",
        help="Local SQLite database file",
    ),
    api_url: Optional[str] = typer.Option(
        None,
        "--api-url",
        "-u",
        help="API base URL",
    ),
    verify_after: bool = typer.Option(
        True,
        "--verify/--no-verify",
        help="Verify chain after filling gaps",
    ),
) -> None:
    """Fill gaps in local database by fetching from API.

    Detects gaps, fetches missing events from Observer API,
    inserts them into local database, and re-verifies.

    Example:
        archon72-verify fill-gaps --local-db ./events.db
    """
    asyncio.run(_fill_gaps_async(local_db, api_url, verify_after))


async def _fill_gaps_async(
    db_path: Path,
    api_url: Optional[str],
    verify_after: bool,
) -> None:
    """Async implementation of gap filling."""
    if not db_path.exists():
        console.print(f"[red]Database not found: {db_path}[/red]")
        raise typer.Exit(1)

    # Find gaps
    with ObserverDatabase(db_path) as db:
        gaps = db.find_gaps()

    if not gaps:
        console.print("[green]No gaps to fill[/green]")
        return

    total_missing = sum(end - start + 1 for start, end in gaps)
    console.print(f"Found {len(gaps)} gap(s) with {total_missing} missing events")

    # Fetch missing events from API
    client = ObserverClient(base_url=api_url)
    try:
        with ObserverDatabase(db_path) as db:
            filled = 0
            for start, end in gaps:
                console.print(f"Fetching events {start}-{end}...", style="dim")
                events = await client.get_events(start, end)

                if events:
                    db.insert_events(events)
                    filled += len(events)
                    console.print(f"  Inserted {len(events)} events")
                else:
                    console.print(f"  [yellow]No events returned for {start}-{end}[/yellow]")
    finally:
        await client.close()

    console.print(f"[green]Filled {filled} events[/green]")

    # Re-verify if requested
    if verify_after:
        console.print("\nVerifying chain after fill...", style="dim")

        with ObserverDatabase(db_path) as db:
            remaining_gaps = db.find_gaps()

        if remaining_gaps:
            console.print(f"[yellow]Warning: {len(remaining_gaps)} gaps remain[/yellow]")
            sys.exit(1)
        else:
            console.print("[green]Chain complete - no gaps[/green]")


@app.command()
def sync(
    local_db: Path = typer.Option(
        ...,
        "--local-db",
        "-d",
        help="Local SQLite database file",
    ),
    api_url: Optional[str] = typer.Option(
        None,
        "--api-url",
        "-u",
        help="API base URL",
    ),
    batch_size: int = typer.Option(
        1000,
        "--batch-size",
        "-b",
        help="Events per API request",
    ),
) -> None:
    """Synchronize local database with Observer API.

    Fetches all new events since the last sequence in local database.

    Example:
        archon72-verify sync --local-db ./events.db
    """
    asyncio.run(_sync_async(local_db, api_url, batch_size))


async def _sync_async(
    db_path: Path,
    api_url: Optional[str],
    batch_size: int,
) -> None:
    """Async implementation of database sync."""
    if not db_path.exists():
        console.print(f"[red]Database not found: {db_path}[/red]")
        console.print("Run 'archon72-verify init-db' first")
        raise typer.Exit(1)

    with ObserverDatabase(db_path) as db:
        _, max_seq = db.get_sequence_range()

    start_seq = (max_seq or 0) + 1
    console.print(f"Syncing from sequence {start_seq}...", style="dim")

    client = ObserverClient(base_url=api_url)
    try:
        total_synced = 0

        while True:
            events = await client.get_events(
                start_seq,
                start_seq + batch_size - 1,
                page_size=batch_size,
            )

            if not events:
                break

            with ObserverDatabase(db_path) as db:
                db.insert_events(events)

            total_synced += len(events)
            max_fetched = max(e["sequence"] for e in events)
            console.print(f"  Synced up to sequence {max_fetched}")

            start_seq = max_fetched + 1
    finally:
        await client.close()

    console.print(f"[green]Synced {total_synced} new events[/green]")
```

### Task 3: Add verification for local database

Extend `ChainVerifier` to verify events from local database.

**Files:**
- `tools/archon72-verify/archon72_verify/verifier.py` (modify)
- `tools/archon72-verify/tests/test_verifier.py` (modify)

**Test Cases (RED):**
- `test_verify_chain_from_database`
- `test_verify_detects_corruption_in_database`
- `test_verify_database_with_gaps`

**Implementation (GREEN):**
```python
# Add to verifier.py

from archon72_verify.database import ObserverDatabase


def verify_database(
    self,
    db_path: str | Path,
    start: Optional[int] = None,
    end: Optional[int] = None,
) -> VerificationResult:
    """Verify hash chain in local database.

    Per FR122: Verify local copy integrity.

    Args:
        db_path: Path to SQLite database.
        start: First sequence to verify (default: min in db).
        end: Last sequence to verify (default: max in db).

    Returns:
        VerificationResult with validation status.
    """
    with ObserverDatabase(db_path) as db:
        min_seq, max_seq = db.get_sequence_range()

        if min_seq is None:
            return VerificationResult(
                is_valid=True,
                events_verified=0,
                error_message="Database is empty",
            )

        # Apply range defaults
        start = start or min_seq
        end = end or max_seq

        # Get events from database
        events = db.get_events_in_range(start, end)

        # Find gaps first
        gaps = db.find_gaps(start, end)

        # Verify chain
        result = self.verify_chain(events)

        # Merge gap information
        if gaps and result.is_valid:
            result.is_valid = False
            result.gaps_found = gaps
            result.error_type = "sequence_gaps"
            result.error_message = f"Found {len(gaps)} sequence gap(s)"
        elif gaps:
            result.gaps_found = gaps

        return result
```

### Task 4: Integration tests for local database gap detection

End-to-end tests for FR122-FR123.

**Files:**
- `tests/integration/test_observer_gap_detection_integration.py` (new)

**Test Cases:**
- `test_observer_can_init_local_database`
- `test_observer_can_sync_events_to_local_db`
- `test_gap_detection_finds_missing_events`
- `test_gap_filling_retrieves_missing_events`
- `test_full_workflow_sync_detect_fill_verify`
- `test_gap_report_format_includes_ranges`
- `test_offline_gap_detection_no_api_required`

### Task 5: Update toolkit README with local database documentation

Document local database usage for observers.

**Files:**
- `tools/archon72-verify/README.md` (modify)

**Add Section:**
```markdown
## Local Observer Database

Observers can maintain a local copy of events for offline verification.

### Initialize Database

```bash
archon72-verify init-db ./events.db
```

### Sync with API

```bash
# Initial sync or catch up
archon72-verify sync --local-db ./events.db

# Sync with custom API URL
archon72-verify sync --local-db ./events.db --api-url https://staging.archon72.io
```

### Detect Gaps in Local Copy (FR122)

```bash
# Check entire database
archon72-verify check-gaps --local-db ./events.db

# Check specific range
archon72-verify check-gaps --local-db ./events.db --from 1 --to 1000
```

### Fill Gaps (FR123)

```bash
# Automatically fetch and insert missing events
archon72-verify fill-gaps --local-db ./events.db

# Fill without re-verification
archon72-verify fill-gaps --local-db ./events.db --no-verify
```

### Verify Local Database Chain

```bash
# Full chain verification on local copy
archon72-verify check-chain --local-db ./events.db
```
```

## Technical Notes

### Implementation Order
1. Task 1: SQLite database support (`database.py`)
2. Task 2: CLI extensions for local database commands
3. Task 3: Verifier extension for database verification
4. Task 4: Integration tests
5. Task 5: Documentation update

### Testing Strategy
- Unit tests for database operations (connect, insert, query, find_gaps)
- Unit tests for CLI commands with mock database
- Integration tests with real SQLite database
- End-to-end test: init → sync → detect gaps → fill → verify

### Constitutional Compliance Matrix
| Requirement | Implementation |
|-------------|----------------|
| FR122 | `check-gaps --local-db` command, `ObserverDatabase.find_gaps()` |
| FR123 | Gap range reporting in CLI output (start, end, count) |
| CT-7 | Genesis event must be in local database for verification |
| CT-11 | Gaps are clearly reported, not hidden |
| ADR-8 | Observer catch-up via `sync` and `fill-gaps` commands |

### Key Design Decisions
1. **SQLite**: Portable, serverless, works offline - ideal for observer local storage
2. **Same schema**: Local database mirrors API response structure for consistent verification
3. **Incremental sync**: Only fetch new events to minimize API load
4. **Gap filling workflow**: Detect → fetch → insert → re-verify

### Performance Considerations
- **Batch sync**: 1000 events per API request by default
- **Indexed queries**: Sequence number indexed for fast gap detection
- **Streaming insert**: Events inserted as received, not buffered

### Previous Story Intelligence (Story 4.4)
From Story 4.4 (verification toolkit - 68 tests):
- `ChainVerifier._find_sequence_gaps()` already implemented
- CLI uses Typer with Rich console output
- JSON output format supported for programmatic use
- Offline verification via `--file` already works

Key patterns to follow:
- Typer CLI with type hints
- Rich console for colored output
- Async/await for API calls
- Context manager pattern for database

### Previous Story Intelligence (Story 4.9)
From Story 4.9 (Observer API uptime SLA - 62 tests):
- `/health`, `/ready` endpoints for checking API availability
- Checkpoint fallback for verification during outages
- UptimeService tracks API availability

### Git Intelligence
Recent commits:
- `cdeb269` - Story 3.6: 48-hour recovery waiting period (FR21)
- Full event store and observer API implementation complete
- Observer API has all endpoints needed for gap filling

## Dev Notes

### Project Structure Notes
- Toolkit location: `tools/archon72-verify/`
- New database module: `tools/archon72-verify/archon72_verify/database.py`
- CLI modifications: `tools/archon72-verify/archon72_verify/cli.py`
- Tests: `tools/archon72-verify/tests/`

### References
- [Source: _bmad-output/planning-artifacts/epics.md#Story-4.10]
- [Source: _bmad-output/planning-artifacts/architecture.md#ADR-8]
- [Source: tools/archon72-verify/archon72_verify/cli.py - Existing CLI]
- [Source: tools/archon72-verify/archon72_verify/verifier.py - ChainVerifier]
- [Source: tools/archon72-verify/archon72_verify/client.py - ObserverClient]
- [Source: _bmad-output/implementation-artifacts/stories/4-4-open-source-verification-toolkit.md]
- [Source: _bmad-output/implementation-artifacts/stories/4-9-observer-api-uptime-sla.md]

### Patterns to Follow
- Typer CLI with type hints (per Story 4.4)
- Rich console for colored output
- Context manager for database connections
- Async/await for API calls
- JSON output format option for scripting
- Pydantic for data models

### Files to Create
- `tools/archon72-verify/archon72_verify/database.py` (new)
- `tools/archon72-verify/tests/test_database.py` (new)
- `tests/integration/test_observer_gap_detection_integration.py` (new)

### Files to Modify
- `tools/archon72-verify/archon72_verify/cli.py` (add commands)
- `tools/archon72-verify/archon72_verify/verifier.py` (add verify_database)
- `tools/archon72-verify/README.md` (add documentation)
- `tools/archon72-verify/pyproject.toml` (no changes needed - sqlite3 is stdlib)

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

N/A

### Completion Notes List

**Task 1**: Added SQLite database support - Created `tools/archon72-verify/archon72_verify/database.py` with `ObserverDatabase` class implementing context manager pattern, schema creation, event insertion, gap detection (FR122), and sequence range queries. Added 21 unit tests in `test_database.py`.

**Task 2**: Extended CLI with local database commands - Modified `cli.py` to add:
- `--local-db` flag to `check-gaps` command for local database gap detection
- `init-db` command for database initialization
- `fill-gaps` command for fetching missing events from API
- `sync` command for incremental database synchronization
- Added `quiet` parameter to `_check_gaps_local_db()` for clean JSON output
- Added 12 new CLI tests in `test_cli.py`

**Task 3**: Added verification for local database - Added `verify_database()` method to `ChainVerifier` class that reads events from SQLite, detects gaps, and performs chain verification. Added 4 unit tests in `test_verifier.py`.

**Task 4**: Integration tests - Created `tests/integration/test_observer_gap_detection_integration.py` with 12 tests covering:
- Database initialization (AC4)
- Gap detection with ranges (AC1, AC2)
- Offline verification
- fill-gaps and sync commands (AC3)
- Full workflow API tests

**Task 5**: Updated README documentation - Added sections for:
- Local database CLI commands
- Python API usage with `ObserverDatabase`
- FR122/FR123 in verification specification

### File List

**Created:**
- `tools/archon72-verify/archon72_verify/database.py` - SQLite database support
- `tools/archon72-verify/tests/test_database.py` - 21 database unit tests
- `tests/integration/test_observer_gap_detection_integration.py` - 12 integration tests

**Modified:**
- `tools/archon72-verify/archon72_verify/__init__.py` - Export `ObserverDatabase`
- `tools/archon72-verify/archon72_verify/cli.py` - Added local-db commands
- `tools/archon72-verify/archon72_verify/verifier.py` - Added `verify_database()`
- `tools/archon72-verify/tests/test_cli.py` - 12 new CLI tests
- `tools/archon72-verify/tests/test_verifier.py` - 4 database verification tests
- `tools/archon72-verify/README.md` - Documentation for local database features

### Test Summary

- **Toolkit tests**: 102 passed
- **Integration tests**: 12 passed
- **Total for story**: 37 new tests added (21 database + 12 CLI + 4 verifier)
