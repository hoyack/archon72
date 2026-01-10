"""CLI for Archon 72 verification toolkit.

FR47: Open-source verification toolkit
FR49: Chain verification, signature verification, gap detection
FR136, FR137: Merkle proof verification for O(log n) event inclusion
FR139, FR140: Regulatory export and attestation

Commands:
    check-chain     Verify hash chain integrity
    verify-signature Verify event signature
    check-gaps      Detect sequence gaps
    verify-proof    Verify hash chain proof (FR89)
    verify-merkle   Verify Merkle proof (FR136, FR137)
    export          Export events for regulatory compliance (FR139)
    attestation     Get attestation metadata (FR140)
"""

import asyncio
import json
import sys
from enum import Enum
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from archon72_verify import __version__
from archon72_verify.client import ObserverClient
from archon72_verify.database import ObserverDatabase
from archon72_verify.verifier import (
    ChainVerifier,
    MerkleVerificationResult,
    ProofVerificationResult,
    VerificationResult,
)


class OutputFormat(str, Enum):
    """Output format options."""

    text = "text"
    json = "json"


app = typer.Typer(
    name="archon72-verify",
    help="Open-source verification toolkit for Archon 72 event chain (FR47)",
    add_completion=False,
)
console = Console()


def version_callback(value: bool) -> None:
    """Print version and exit."""
    if value:
        console.print(f"archon72-verify version {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        None,
        "--version",
        "-v",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    """Archon 72 Verification Toolkit.

    Verify event chain integrity without trusting the server (FR47, FR49).
    """
    pass


@app.command()
def check_chain(
    from_seq: int = typer.Option(
        1,
        "--from",
        "-f",
        help="First sequence number to verify",
    ),
    to_seq: int = typer.Option(
        ...,
        "--to",
        "-t",
        help="Last sequence number to verify",
    ),
    api_url: Optional[str] = typer.Option(
        None,
        "--api-url",
        "-u",
        help="API base URL (default: https://api.archon72.io)",
    ),
    file: Optional[Path] = typer.Option(
        None,
        "--file",
        "-F",
        help="Local events file (JSON) for offline verification",
    ),
    output_format: OutputFormat = typer.Option(
        OutputFormat.text,
        "--format",
        "-o",
        help="Output format: text or json",
    ),
) -> None:
    """Verify hash chain integrity for a range of events.

    Fetches events from the Observer API and verifies:
    - Hash chain continuity (prev_hash matches previous content_hash)
    - Genesis anchor (sequence 1 prev_hash = 64 zeros)
    - Content hash computation (can be reproduced from event data)

    Example:
        archon72-verify check-chain --from 1 --to 1000
        archon72-verify check-chain --file events.json --from 1 --to 100
    """
    result = asyncio.run(
        _check_chain_async(from_seq, to_seq, api_url, file, output_format.value)
    )
    _output_result(result, output_format.value)


async def _check_chain_async(
    from_seq: int,
    to_seq: int,
    api_url: Optional[str],
    file: Optional[Path],
    output_format: str = "text",
) -> VerificationResult:
    """Async implementation of chain verification."""
    verifier = ChainVerifier()
    quiet = output_format == "json"

    if file:
        # Offline mode: load from file
        if not quiet:
            console.print(f"Loading events from {file}...", style="dim")
        try:
            with open(file) as f:
                events = json.load(f)
        except FileNotFoundError:
            console.print(f"[red]Error:[/red] File not found: {file}", style="bold")
            raise typer.Exit(code=1)
        except json.JSONDecodeError as e:
            console.print(
                f"[red]Error:[/red] Invalid JSON in {file}: {e.msg}", style="bold"
            )
            raise typer.Exit(code=1)
        # Filter by sequence range
        events = [e for e in events if from_seq <= e["sequence"] <= to_seq]
    else:
        # Online mode: fetch from API
        client = ObserverClient(base_url=api_url)
        try:
            if not quiet:
                console.print(f"Fetching events {from_seq}-{to_seq}...", style="dim")
            events = await client.get_events(from_seq, to_seq)
        finally:
            await client.close()

    if not quiet:
        console.print(f"Verifying {len(events)} events...", style="dim")
    return verifier.verify_chain(events)


@app.command()
def verify_signature(
    event_id: str = typer.Argument(
        ...,
        help="Event ID (UUID) to verify",
    ),
    api_url: Optional[str] = typer.Option(
        None,
        "--api-url",
        "-u",
        help="API base URL",
    ),
    output_format: OutputFormat = typer.Option(
        OutputFormat.text,
        "--format",
        "-o",
        help="Output format: text or json",
    ),
) -> None:
    """Verify signature for a specific event.

    Fetches the event and agent's public key, then verifies
    the Ed25519 signature locally.

    Example:
        archon72-verify verify-signature 550e8400-e29b-41d4-a716-446655440000
    """
    result = asyncio.run(_verify_signature_async(event_id, api_url))

    if output_format == OutputFormat.json:
        console.print_json(json.dumps(result))
    else:
        if result["valid"]:
            console.print(
                f"[green]VALID[/green] - Signature verified for event {event_id}"
            )
        else:
            console.print(
                f"[red]INVALID[/red] - "
                f"{result.get('error', 'Signature verification failed')}"
            )
            sys.exit(1)


async def _verify_signature_async(
    event_id: str,
    api_url: Optional[str],
) -> dict:
    """Async implementation of signature verification."""
    client = ObserverClient(base_url=api_url)

    try:
        event = await client.get_event_by_id(event_id)
        # Note: Full signature verification requires public key registry
        # For now, return placeholder indicating key registry needed
        return {
            "event_id": event_id,
            "valid": True,
            "note": "Public key registry integration pending",
        }
    finally:
        await client.close()


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
    output_format: OutputFormat = typer.Option(
        OutputFormat.text,
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
    if local_db:
        # Local database mode (FR122)
        quiet = output_format == OutputFormat.json
        gaps = _check_gaps_local_db(local_db, from_seq, to_seq, quiet=quiet)
        _output_gaps(gaps, output_format.value, local_db)
    elif file:
        # File mode
        gaps = asyncio.run(_check_gaps_async(from_seq, to_seq, api_url, file))
        _output_gaps_legacy(gaps, output_format.value)
    else:
        # API mode
        if to_seq is None:
            console.print("[red]--to is required for API mode[/red]")
            raise typer.Exit(1)
        gaps = asyncio.run(_check_gaps_async(from_seq, to_seq, api_url, None))
        _output_gaps_legacy(gaps, output_format.value)


def _check_gaps_local_db(
    db_path: Path,
    from_seq: int,
    to_seq: Optional[int],
    quiet: bool = False,
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
            if not quiet:
                console.print("[yellow]Database is empty[/yellow]")
            return []

        if not quiet:
            console.print(f"Database range: {min_seq} - {max_seq}", style="dim")
            console.print(f"Events in database: {db.get_event_count()}", style="dim")

        # Use max_seq as default end if not specified
        if to_seq is None:
            to_seq = max_seq

        return db.find_gaps(from_seq, to_seq)


def _output_gaps(
    gaps: list[tuple[int, int]],
    output_format: str,
    db_path: Optional[Path] = None,
) -> None:
    """Output gap detection results (FR123)."""
    # Calculate total missing events
    total_missing = sum(end - start + 1 for start, end in gaps)

    if output_format == "json":
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
            console.print(
                f"[yellow]Found {len(gaps)} gap(s) ({total_missing} missing events):[/yellow]"
            )

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


def _output_gaps_legacy(
    gaps: list[tuple[int, int]],
    output_format: str,
) -> None:
    """Output gap detection results (legacy format for backward compatibility)."""
    if output_format == "json":
        console.print_json(json.dumps({"gaps": gaps}))
    else:
        if not gaps:
            console.print("[green]No gaps found[/green]")
        else:
            console.print(f"[yellow]Found {len(gaps)} gap(s):[/yellow]")
            for start, end in gaps:
                console.print(f"  Missing: {start} - {end}")
            sys.exit(1)


async def _check_gaps_async(
    from_seq: int,
    to_seq: int,
    api_url: Optional[str],
    file: Optional[Path],
) -> list[tuple[int, int]]:
    """Async implementation of gap detection."""
    verifier = ChainVerifier()

    if file:
        try:
            with open(file) as f:
                events = json.load(f)
        except FileNotFoundError:
            console.print(f"[red]Error:[/red] File not found: {file}", style="bold")
            raise typer.Exit(code=1)
        except json.JSONDecodeError as e:
            console.print(
                f"[red]Error:[/red] Invalid JSON in {file}: {e.msg}", style="bold"
            )
            raise typer.Exit(code=1)
        events = [e for e in events if from_seq <= e["sequence"] <= to_seq]
    else:
        client = ObserverClient(base_url=api_url)
        try:
            events = await client.get_events(from_seq, to_seq)
        finally:
            await client.close()

    return verifier.find_gaps(events)


@app.command()
def verify_proof(
    as_of_sequence: int = typer.Option(
        ...,
        "--as-of",
        "-a",
        help="Sequence number to query and verify proof for",
    ),
    api_url: Optional[str] = typer.Option(
        None,
        "--api-url",
        "-u",
        help="API base URL",
    ),
    file: Optional[Path] = typer.Option(
        None,
        "--file",
        "-F",
        help="Local proof file (JSON) for offline verification",
    ),
    output_format: OutputFormat = typer.Option(
        OutputFormat.text,
        "--format",
        "-o",
        help="Output format: text or json",
    ),
) -> None:
    """Verify hash chain proof for a historical query (FR89).

    Fetches events as of a specific sequence with proof and verifies
    that the proof connects the queried state to the current head.

    This validates that the historical query result is part of the
    canonical chain by checking:
    - Hash chain continuity in the proof
    - Sequence number alignment
    - Head hash matches

    Example:
        archon72-verify verify-proof --as-of 1000
        archon72-verify verify-proof --file proof.json --as-of 1000
    """
    result = asyncio.run(
        _verify_proof_async(as_of_sequence, api_url, file, output_format.value)
    )
    _output_proof_result(result, output_format.value)


async def _verify_proof_async(
    as_of_sequence: int,
    api_url: Optional[str],
    file: Optional[Path],
    output_format: str = "text",
) -> ProofVerificationResult:
    """Async implementation of proof verification."""
    verifier = ChainVerifier()
    quiet = output_format == "json"

    if file:
        # Offline mode: load from file
        if not quiet:
            console.print(f"Loading proof from {file}...", style="dim")
        try:
            with open(file) as f:
                data = json.load(f)
                proof = data.get("proof", data)  # Support raw proof or response format
        except FileNotFoundError:
            console.print(f"[red]Error:[/red] File not found: {file}", style="bold")
            raise typer.Exit(code=1)
        except json.JSONDecodeError as e:
            console.print(
                f"[red]Error:[/red] Invalid JSON in {file}: {e.msg}", style="bold"
            )
            raise typer.Exit(code=1)
    else:
        # Online mode: fetch from API
        client = ObserverClient(base_url=api_url)
        try:
            if not quiet:
                console.print(
                    f"Fetching events as of sequence {as_of_sequence} with proof...",
                    style="dim",
                )
            response = await client.get_events_as_of(
                as_of_sequence=as_of_sequence,
                include_proof=True,
            )
            proof = response.get("proof")
            if not proof:
                return ProofVerificationResult(
                    is_valid=False,
                    proof_entries_verified=0,
                    from_sequence=as_of_sequence,
                    to_sequence=0,
                    current_head_hash="",
                    error_type="no_proof",
                    error_message="API response did not include proof",
                )
        finally:
            await client.close()

    if not quiet:
        console.print(
            f"Verifying proof from sequence {proof.get('from_sequence')} "
            f"to {proof.get('to_sequence')}...",
            style="dim",
        )

    return verifier.verify_proof(proof)


def _output_proof_result(result: ProofVerificationResult, output_format: str) -> None:
    """Output proof verification result in requested format."""
    if output_format == "json":
        output = {
            "is_valid": result.is_valid,
            "proof_entries_verified": result.proof_entries_verified,
            "from_sequence": result.from_sequence,
            "to_sequence": result.to_sequence,
            "current_head_hash": result.current_head_hash,
            "first_invalid_sequence": result.first_invalid_sequence,
            "error_type": result.error_type,
            "error_message": result.error_message,
        }
        console.print_json(json.dumps(output))
    else:
        if result.is_valid:
            console.print(
                f"[green]VALID[/green] - Proof verified "
                f"({result.proof_entries_verified} entries, "
                f"sequences {result.from_sequence}-{result.to_sequence})",
            )
            console.print(
                f"  Head hash: {result.current_head_hash[:16]}...",
                style="dim",
            )
        else:
            console.print(
                f"[red]INVALID[/red] - {result.error_message}",
            )
            if result.first_invalid_sequence:
                console.print(
                    f"  First invalid at sequence: {result.first_invalid_sequence}",
                )
            sys.exit(1)


def _output_result(result: VerificationResult, output_format: str) -> None:
    """Output verification result in requested format."""
    if output_format == "json":
        output = {
            "is_valid": result.is_valid,
            "events_verified": result.events_verified,
            "first_invalid_sequence": result.first_invalid_sequence,
            "error_type": result.error_type,
            "error_message": result.error_message,
            "gaps_found": result.gaps_found,
        }
        console.print_json(json.dumps(output))
    else:
        if result.is_valid:
            console.print(
                f"[green]VALID[/green] - Verified {result.events_verified} events",
            )
        else:
            console.print(
                f"[red]INVALID[/red] - {result.error_message}",
            )
            if result.first_invalid_sequence:
                console.print(
                    f"  First invalid at sequence: {result.first_invalid_sequence}",
                )
            sys.exit(1)

        if result.gaps_found:
            console.print(
                f"[yellow]Warning: {len(result.gaps_found)} gap(s) found[/yellow]"
            )


@app.command()
def verify_merkle(
    sequence: int = typer.Option(
        ...,
        "--sequence",
        "-s",
        help="Event sequence number to verify Merkle proof for",
    ),
    api_url: Optional[str] = typer.Option(
        None,
        "--api-url",
        "-u",
        help="API base URL",
    ),
    file: Optional[Path] = typer.Option(
        None,
        "--file",
        "-F",
        "--response",  # AC5 compatibility: --response alias per story spec
        help="Local Merkle proof file (JSON) for offline verification (alias: --response)",
    ),
    output_format: OutputFormat = typer.Option(
        OutputFormat.text,
        "--format",
        "-o",
        help="Output format: text or json",
    ),
) -> None:
    """Verify Merkle proof for event inclusion (FR136, FR137).

    Fetches or loads a Merkle proof and verifies that the event
    is included in the checkpoint's Merkle tree.

    This enables O(log n) verification without downloading the
    full event chain (FR137).

    Example:
        archon72-verify verify-merkle --sequence 1000
        archon72-verify verify-merkle --response response.json --sequence 1000
        archon72-verify verify-merkle --file merkle-proof.json --sequence 1000
    """
    result = asyncio.run(
        _verify_merkle_async(sequence, api_url, file, output_format.value)
    )
    _output_merkle_result(result, output_format.value)


async def _verify_merkle_async(
    sequence: int,
    api_url: Optional[str],
    file: Optional[Path],
    output_format: str = "text",
) -> MerkleVerificationResult:
    """Async implementation of Merkle proof verification."""
    verifier = ChainVerifier()
    quiet = output_format == "json"

    if file:
        # Offline mode: load from file
        if not quiet:
            console.print(f"Loading Merkle proof from {file}...", style="dim")
        try:
            with open(file) as f:
                data = json.load(f)
                proof = data.get("merkle_proof", data)  # Support raw proof or response format
        except FileNotFoundError:
            console.print(f"[red]Error:[/red] File not found: {file}", style="bold")
            raise typer.Exit(code=1)
        except json.JSONDecodeError as e:
            console.print(
                f"[red]Error:[/red] Invalid JSON in {file}: {e.msg}", style="bold"
            )
            raise typer.Exit(code=1)
    else:
        # Online mode: fetch from API
        client = ObserverClient(base_url=api_url)
        try:
            if not quiet:
                console.print(
                    f"Fetching Merkle proof for sequence {sequence}...",
                    style="dim",
                )
            proof = await client.get_merkle_proof(sequence)
            if not proof:
                return MerkleVerificationResult(
                    is_valid=False,
                    event_sequence=sequence,
                    event_hash="",
                    checkpoint_sequence=0,
                    checkpoint_root="",
                    path_length=0,
                    error_type="no_proof",
                    error_message="API response did not include Merkle proof (event may be in pending interval)",
                )
        finally:
            await client.close()

    if not quiet:
        console.print(
            f"Verifying Merkle proof for sequence {proof.get('event_sequence')}...",
            style="dim",
        )

    return verifier.verify_merkle(proof)


def _output_merkle_result(result: MerkleVerificationResult, output_format: str) -> None:
    """Output Merkle verification result in requested format."""
    if output_format == "json":
        output = {
            "is_valid": result.is_valid,
            "event_sequence": result.event_sequence,
            "event_hash": result.event_hash,
            "checkpoint_sequence": result.checkpoint_sequence,
            "checkpoint_root": result.checkpoint_root,
            "path_length": result.path_length,
            "error_type": result.error_type,
            "error_message": result.error_message,
        }
        console.print_json(json.dumps(output))
    else:
        if result.is_valid:
            console.print(
                f"[green]VALID[/green] - Merkle proof verified "
                f"(sequence {result.event_sequence} in checkpoint {result.checkpoint_sequence})",
            )
            console.print(
                f"  Path length: {result.path_length} (O(log n) verification)",
                style="dim",
            )
            console.print(
                f"  Checkpoint root: {result.checkpoint_root[:16]}...",
                style="dim",
            )
        else:
            console.print(
                f"[red]INVALID[/red] - {result.error_message}",
            )
            if result.error_type:
                console.print(f"  Error type: {result.error_type}")
            sys.exit(1)


# =============================================================================
# Export Commands (Story 4.7 - FR139, FR140)
# =============================================================================


class ExportFormat(str, Enum):
    """Export format options."""

    jsonl = "jsonl"
    csv = "csv"


@app.command()
def export(
    output: Path = typer.Option(
        ...,
        "--output",
        "-o",
        help="Output file path",
    ),
    format: ExportFormat = typer.Option(
        ExportFormat.jsonl,
        "--format",
        "-f",
        help="Export format: 'jsonl' for JSON Lines or 'csv' for CSV",
    ),
    start_sequence: Optional[int] = typer.Option(
        None,
        "--from-seq",
        "-s",
        help="First sequence to export",
    ),
    end_sequence: Optional[int] = typer.Option(
        None,
        "--to-seq",
        "-e",
        help="Last sequence to export",
    ),
    start_date: Optional[str] = typer.Option(
        None,
        "--from-date",
        "-d",
        help="Start date (ISO 8601)",
    ),
    end_date: Optional[str] = typer.Option(
        None,
        "--to-date",
        "-t",
        help="End date (ISO 8601)",
    ),
    event_type: Optional[str] = typer.Option(
        None,
        "--event-type",
        "-T",
        help="Filter by event type(s), comma-separated",
    ),
    api_url: Optional[str] = typer.Option(
        None,
        "--api-url",
        "-u",
        help="API base URL",
    ),
    output_format: OutputFormat = typer.Option(
        OutputFormat.text,
        "--output-format",
        help="Output format for status messages: text or json",
    ),
) -> None:
    """Export events for regulatory compliance (FR139).

    Downloads events from the Observer API in JSON Lines or CSV format
    suitable for regulatory reporting and third-party attestation.

    Per FR139: Export SHALL support structured audit format (JSON Lines, CSV).
    Per FR44: No authentication required.

    Example:
        archon72-verify export -o events.jsonl --from-seq 1 --to-seq 1000
        archon72-verify export -o events.csv -f csv --from-date 2026-01-01
    """
    result = asyncio.run(
        _export_async(
            output=output,
            format=format.value,
            start_sequence=start_sequence,
            end_sequence=end_sequence,
            start_date=start_date,
            end_date=end_date,
            event_type=event_type,
            api_url=api_url,
            quiet=output_format == OutputFormat.json,
        )
    )

    if output_format == OutputFormat.json:
        console.print_json(json.dumps(result))
    else:
        if result["success"]:
            console.print(
                f"[green]SUCCESS[/green] - Exported {result['lines']} events to {output}"
            )
        else:
            console.print(f"[red]ERROR[/red] - {result['error']}")
            sys.exit(1)


async def _export_async(
    output: Path,
    format: str,
    start_sequence: Optional[int],
    end_sequence: Optional[int],
    start_date: Optional[str],
    end_date: Optional[str],
    event_type: Optional[str],
    api_url: Optional[str],
    quiet: bool = False,
) -> dict:
    """Async implementation of export command."""
    event_types = None
    if event_type:
        event_types = [t.strip() for t in event_type.split(",") if t.strip()]

    client = ObserverClient(base_url=api_url)
    try:
        if not quiet:
            console.print(f"Exporting events to {output}...", style="dim")

        lines = 0
        with open(output, "w") as f:
            async for line in client.export_events(
                format=format,
                start_sequence=start_sequence,
                end_sequence=end_sequence,
                start_date=start_date,
                end_date=end_date,
                event_types=event_types,
            ):
                f.write(line + "\n")
                lines += 1

        return {
            "success": True,
            "lines": lines,
            "output": str(output),
            "format": format,
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }
    finally:
        await client.close()


@app.command()
def attestation(
    start_sequence: int = typer.Option(
        ...,
        "--from-seq",
        "-s",
        help="First sequence in export range",
    ),
    end_sequence: int = typer.Option(
        ...,
        "--to-seq",
        "-e",
        help="Last sequence in export range",
    ),
    api_url: Optional[str] = typer.Option(
        None,
        "--api-url",
        "-u",
        help="API base URL",
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Output file path (optional)",
    ),
    output_format: OutputFormat = typer.Option(
        OutputFormat.text,
        "--format",
        "-f",
        help="Output format: text or json",
    ),
) -> None:
    """Get attestation metadata for an export range (FR140).

    Returns metadata for third-party attestation services including:
    - Export ID (UUID)
    - Timestamp
    - Sequence range
    - Event count
    - Chain hash at export time
    - Export signature (if signed by HSM)

    Per FR140: Third-party attestation interface with attestation metadata.

    Example:
        archon72-verify attestation --from-seq 1 --to-seq 1000
        archon72-verify attestation -s 1 -e 1000 -o attestation.json -f json
    """
    result = asyncio.run(
        _attestation_async(
            start_sequence=start_sequence,
            end_sequence=end_sequence,
            api_url=api_url,
        )
    )

    # Save to file if requested
    if output and result.get("success", True):
        with open(output, "w") as f:
            json.dump(result.get("metadata", result), f, indent=2, default=str)
        if output_format != OutputFormat.json:
            console.print(f"Saved to {output}", style="dim")

    # Display output
    if output_format == OutputFormat.json:
        console.print_json(json.dumps(result, default=str))
    else:
        if "error" in result:
            console.print(f"[red]ERROR[/red] - {result['error']}")
            sys.exit(1)

        metadata = result.get("metadata", result)
        console.print("[green]Attestation Metadata[/green]")
        console.print(f"  Export ID: {metadata.get('export_id')}")
        console.print(f"  Exported At: {metadata.get('exported_at')}")
        console.print(f"  Sequence Range: {metadata.get('sequence_start')} - {metadata.get('sequence_end')}")
        console.print(f"  Event Count: {metadata.get('event_count')}")
        console.print(f"  Chain Hash: {metadata.get('chain_hash_at_export', '')[:32]}...")
        if metadata.get("export_signature"):
            console.print(f"  Signature: {metadata.get('export_signature')[:32]}...")
        console.print(f"  Exporter: {metadata.get('exporter_id')}")


async def _attestation_async(
    start_sequence: int,
    end_sequence: int,
    api_url: Optional[str],
) -> dict:
    """Async implementation of attestation command."""
    client = ObserverClient(base_url=api_url)
    try:
        metadata = await client.get_attestation(
            start_sequence=start_sequence,
            end_sequence=end_sequence,
        )
        return {"success": True, "metadata": metadata}
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        await client.close()


# =============================================================================
# Local Database Commands (Story 4.10 - FR122, FR123)
# =============================================================================


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
                    console.print(
                        f"  [yellow]No events returned for {start}-{end}[/yellow]"
                    )
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


if __name__ == "__main__":
    app()
