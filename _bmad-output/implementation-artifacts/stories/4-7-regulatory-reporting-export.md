# Story 4.7: Regulatory Reporting Export (FR139-FR140)

## Story

**As a** regulator,
**I want** structured audit format export,
**So that** I can import data into compliance systems.

## Status

Status: done

## Context

### Business Context
This is the seventh story in Epic 4 (Observer Verification Interface). It delivers **regulatory-compliant export formats** that allow compliance teams and regulators to import Archon 72 event data into their own audit and compliance systems.

Key business drivers:
1. **Regulatory compliance**: External regulators may require structured data for audits
2. **Compliance integration**: Data must be importable into standard compliance tools (SIEM, GRC platforms)
3. **Attestation support**: Third-party attestation services need standardized data formats
4. **Audit trail**: Complete event history in formats suitable for legal/regulatory review

### Technical Context
- **FR139**: Export SHALL support structured audit format (JSON Lines, CSV)
- **FR140**: Third-party attestation interface - data in attestation-compatible format
- **ADR-8**: Observer Consistency + Genesis Anchor - data export supports external attestation
- **ADR-9**: Claim Verification Matrix - exported data must be independently verifiable

**Story 4.6 Delivered:**
- `MerkleProof` model with Merkle path verification
- `CheckpointAnchor` model with weekly checkpoint support
- `/checkpoints` and `/checkpoints/{sequence}` endpoints
- `include_merkle_proof` query parameter
- `verify-merkle` command in verification toolkit

**Key Files from Previous Stories:**
- `src/api/models/observer.py` - Observer API models including MerkleProof, CheckpointAnchor
- `src/api/routes/observer.py` - Observer API endpoints with filtering and proof support
- `src/application/services/observer_service.py` - ObserverService with proof generation
- `tools/archon72-verify/` - Verification toolkit with chain and Merkle verification

### Dependencies
- **Story 4.1**: Public read access without registration (DONE) - export uses same auth model
- **Story 4.2**: Raw events with hashes (DONE) - export includes full hash data
- **Story 4.3**: Date range and event type filtering (DONE) - export uses same filtering
- **Story 4.6**: Merkle paths for light verification (DONE) - export can include proofs

### Constitutional Constraints
- **FR44**: No authentication required - export endpoints must be public
- **FR48**: Rate limits identical for all users
- **FR139**: Structured audit format export (JSON Lines, CSV)
- **FR140**: Third-party attestation interface with attestation metadata
- **CT-11**: Silent failure destroys legitimacy - export must include all verification data
- **CT-12**: Witnessing creates accountability - export must include witness attribution

### Architecture Decision
Per ADR-8 (Observer Consistency + Genesis Anchor):
- All exported data must be verifiable against the canonical chain
- Export formats must include hash chain data for independent verification
- Third-party attestation services receive complete event records

Per ADR-9 (Claim Verification Matrix):
- Exported data must support absence proof queries
- Format must allow reconstruction of chain state at any point

## Acceptance Criteria

### AC1: JSON Lines export format
**Given** the export API with `format=jsonl`
**When** I request event export
**Then** events are returned one JSON object per line
**And** each line is a complete, valid JSON document
**And** includes all hash chain fields (content_hash, prev_hash, signature)

### AC2: CSV export format
**Given** the export API with `format=csv`
**When** I request event export
**Then** events are returned in CSV format with header row
**And** columns include all verification fields
**And** format follows RFC 4180 specification

### AC3: Attestation metadata included
**Given** the export API with `include_attestation=true`
**When** I request regulatory export
**Then** response includes attestation metadata header/footer
**And** includes export timestamp, sequence range, and chain hash
**And** includes signature from export service

### AC4: Filter support in export
**Given** the export API
**When** I specify date range and event type filters
**Then** only matching events are exported
**And** metadata reflects the filter criteria used

### AC5: Large export pagination
**Given** a request for large export (>10000 events)
**When** I query the export endpoint
**Then** response uses streaming or chunked transfer
**And** memory usage remains bounded
**And** client receives data progressively

## Tasks

### Task 1: Create export format models

Create Pydantic models for regulatory export formats.

**Files:**
- `src/api/models/observer.py` (modify - add export models)
- `tests/unit/api/test_observer_models.py` (modify - add tests)

**Test Cases (RED):**
- `test_regulatory_export_jsonl_format_valid`
- `test_regulatory_export_csv_headers_complete`
- `test_attestation_metadata_model_valid`
- `test_export_request_params_model_valid`

**Implementation (GREEN):**
```python
# In src/api/models/observer.py

class ExportFormat(str, Enum):
    """Supported export formats (FR139)."""
    JSONL = "jsonl"
    CSV = "csv"


class AttestationMetadata(BaseModel):
    """Attestation metadata for regulatory export (FR140).

    Provides context and verification data for exported records.

    Attributes:
        export_id: Unique identifier for this export.
        exported_at: When export was generated (UTC).
        sequence_start: First event sequence in export.
        sequence_end: Last event sequence in export.
        event_count: Number of events exported.
        filter_criteria: Filters applied to export.
        chain_hash_at_export: Content hash of latest event at export time.
        export_signature: Signature of export metadata for verification.
        exporter_id: ID of service that generated export.
    """
    export_id: UUID = Field(default_factory=uuid4)
    exported_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    sequence_start: int = Field(ge=1)
    sequence_end: int = Field(ge=1)
    event_count: int = Field(ge=0)
    filter_criteria: Optional[dict[str, Any]] = None
    chain_hash_at_export: str = Field(pattern=r"^[a-f0-9]{64}$")
    export_signature: Optional[str] = None
    exporter_id: str = Field(default="archon72-observer-api")


class RegulatoryExportResponse(BaseModel):
    """Response wrapper for regulatory export (FR139).

    Attributes:
        format: Export format used.
        attestation: Attestation metadata if requested.
        data: Export data (format depends on format param).
    """
    format: ExportFormat
    attestation: Optional[AttestationMetadata] = None
    data_url: Optional[str] = None  # For large exports
    inline_data: Optional[str] = None  # For small exports
```

### Task 2: Create export service

Create service to handle export generation.

**Files:**
- `src/application/services/export_service.py` (new)
- `tests/unit/application/test_export_service.py` (new)

**Test Cases (RED):**
- `test_export_jsonl_generates_valid_output`
- `test_export_csv_generates_valid_output`
- `test_export_with_filters_applies_correctly`
- `test_export_attestation_metadata_populated`
- `test_export_large_dataset_streams_correctly`
- `test_export_signature_verification`

**Implementation (GREEN):**
```python
# In src/application/services/export_service.py

import csv
import io
import json
from datetime import datetime, timezone
from typing import AsyncIterator, Optional
from uuid import uuid4

from src.api.models.observer import (
    AttestationMetadata,
    ExportFormat,
    ObserverEventResponse,
)
from src.application.ports.event_store import EventStorePort
from src.application.ports.hsm import HSMPort


class ExportService:
    """Service for regulatory export generation (FR139, FR140)."""

    def __init__(
        self,
        event_store: EventStorePort,
        hsm: Optional[HSMPort] = None,
    ) -> None:
        self._event_store = event_store
        self._hsm = hsm

    async def export_jsonl(
        self,
        start_sequence: Optional[int] = None,
        end_sequence: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        event_types: Optional[list[str]] = None,
    ) -> AsyncIterator[str]:
        """Export events as JSON Lines format (FR139).

        Yields one JSON object per line for streaming support.

        Args:
            start_sequence: First sequence to export (optional).
            end_sequence: Last sequence to export (optional).
            start_date: Filter from date (optional).
            end_date: Filter until date (optional).
            event_types: Filter by event types (optional).

        Yields:
            JSON string for each event, newline terminated.
        """
        async for event in self._event_store.stream_events(
            start_sequence=start_sequence,
            end_sequence=end_sequence,
            start_date=start_date,
            end_date=end_date,
            event_types=event_types,
        ):
            yield json.dumps(event.to_dict(), default=str) + "\n"

    async def export_csv(
        self,
        start_sequence: Optional[int] = None,
        end_sequence: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        event_types: Optional[list[str]] = None,
    ) -> AsyncIterator[str]:
        """Export events as CSV format (FR139).

        First yield is header row, subsequent yields are data rows.

        Args:
            start_sequence: First sequence to export (optional).
            end_sequence: Last sequence to export (optional).
            start_date: Filter from date (optional).
            end_date: Filter until date (optional).
            event_types: Filter by event types (optional).

        Yields:
            CSV rows including header.
        """
        headers = [
            "event_id", "sequence", "event_type", "payload",
            "content_hash", "prev_hash", "signature",
            "agent_id", "witness_id", "witness_signature",
            "local_timestamp", "authority_timestamp",
            "hash_algorithm_version", "sig_alg_version",
        ]

        # Yield header row
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(headers)
        yield output.getvalue()

        # Yield data rows
        async for event in self._event_store.stream_events(
            start_sequence=start_sequence,
            end_sequence=end_sequence,
            start_date=start_date,
            end_date=end_date,
            event_types=event_types,
        ):
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow([
                str(event.event_id),
                event.sequence,
                event.event_type,
                json.dumps(event.payload),
                event.content_hash,
                event.prev_hash,
                event.signature,
                event.agent_id,
                event.witness_id,
                event.witness_signature,
                event.local_timestamp.isoformat(),
                event.authority_timestamp.isoformat() if event.authority_timestamp else "",
                event.hash_algorithm_version,
                event.sig_alg_version,
            ])
            yield output.getvalue()

    async def generate_attestation_metadata(
        self,
        sequence_start: int,
        sequence_end: int,
        event_count: int,
        filter_criteria: Optional[dict[str, Any]] = None,
    ) -> AttestationMetadata:
        """Generate attestation metadata for export (FR140).

        Args:
            sequence_start: First sequence in export.
            sequence_end: Last sequence in export.
            event_count: Number of events exported.
            filter_criteria: Filters applied to export.

        Returns:
            AttestationMetadata with export context.
        """
        # Get current chain hash
        head_event = await self._event_store.get_event_by_sequence(sequence_end)
        chain_hash = head_event.content_hash if head_event else "0" * 64

        metadata = AttestationMetadata(
            export_id=uuid4(),
            exported_at=datetime.now(timezone.utc),
            sequence_start=sequence_start,
            sequence_end=sequence_end,
            event_count=event_count,
            filter_criteria=filter_criteria,
            chain_hash_at_export=chain_hash,
        )

        # Sign metadata if HSM available
        if self._hsm:
            signature_data = json.dumps(
                metadata.model_dump(exclude={"export_signature"}),
                sort_keys=True,
                default=str,
            )
            metadata.export_signature = await self._hsm.sign(
                signature_data.encode()
            )

        return metadata
```

### Task 3: Add export endpoints to Observer API

Add export endpoints with streaming support.

**Files:**
- `src/api/routes/observer.py` (modify)
- `src/api/dependencies/export.py` (new)
- `tests/unit/api/test_observer_routes.py` (modify)

**Test Cases (RED):**
- `test_export_endpoint_jsonl_returns_stream`
- `test_export_endpoint_csv_returns_stream`
- `test_export_with_attestation_includes_metadata`
- `test_export_with_filters_applies_correctly`
- `test_export_large_response_streams`
- `test_export_rate_limited`

**Implementation (GREEN):**
```python
# In src/api/routes/observer.py (additions)

from fastapi.responses import StreamingResponse


@router.get("/export")
async def export_events(
    request: Request,
    format: ExportFormat = Query(
        default=ExportFormat.JSONL,
        description="Export format: jsonl or csv (FR139)",
    ),
    include_attestation: bool = Query(
        default=False,
        description="Include attestation metadata header/footer (FR140)",
    ),
    start_sequence: Optional[int] = Query(
        default=None,
        ge=1,
        description="First sequence to export",
    ),
    end_sequence: Optional[int] = Query(
        default=None,
        ge=1,
        description="Last sequence to export",
    ),
    start_date: Optional[datetime] = Query(
        default=None,
        description="Filter from date (ISO 8601)",
    ),
    end_date: Optional[datetime] = Query(
        default=None,
        description="Filter until date (ISO 8601)",
    ),
    event_type: Optional[str] = Query(
        default=None,
        description="Filter by event type(s), comma-separated",
    ),
    export_service: ExportService = Depends(get_export_service),
    rate_limiter: ObserverRateLimiter = Depends(get_rate_limiter),
) -> StreamingResponse:
    """Export events in regulatory format (FR139, FR140).

    No authentication required (FR44).
    Rate limits identical for all users (FR48).

    Per FR139: Structured audit format export (JSON Lines or CSV).
    Per FR140: Third-party attestation interface with metadata.

    Supports streaming for large exports to maintain bounded memory.

    Args:
        request: The FastAPI request object.
        format: Export format (jsonl or csv).
        include_attestation: Include attestation metadata.
        start_sequence: First sequence to export.
        end_sequence: Last sequence to export.
        start_date: Filter from date.
        end_date: Filter until date.
        event_type: Filter by event type(s).
        export_service: Injected export service.
        rate_limiter: Injected rate limiter.

    Returns:
        StreamingResponse with exported data.
    """
    await rate_limiter.check_rate_limit(request)

    # Parse event types
    event_types = None
    if event_type:
        event_types = [t.strip() for t in event_type.split(",") if t.strip()]

    # Build filter criteria for attestation
    filter_criteria = {
        "start_sequence": start_sequence,
        "end_sequence": end_sequence,
        "start_date": start_date.isoformat() if start_date else None,
        "end_date": end_date.isoformat() if end_date else None,
        "event_types": event_types,
    }

    # Determine content type and generator
    if format == ExportFormat.JSONL:
        content_type = "application/x-ndjson"
        generator = export_service.export_jsonl(
            start_sequence=start_sequence,
            end_sequence=end_sequence,
            start_date=start_date,
            end_date=end_date,
            event_types=event_types,
        )
    else:
        content_type = "text/csv"
        generator = export_service.export_csv(
            start_sequence=start_sequence,
            end_sequence=end_sequence,
            start_date=start_date,
            end_date=end_date,
            event_types=event_types,
        )

    async def stream_with_attestation():
        """Wrap generator with attestation header/footer if requested."""
        event_count = 0
        first_seq = None
        last_seq = None

        if include_attestation and format == ExportFormat.JSONL:
            # Attestation header will be added at end
            pass

        async for chunk in generator:
            event_count += 1
            # Track sequence range for attestation
            if first_seq is None and format == ExportFormat.JSONL:
                try:
                    data = json.loads(chunk)
                    first_seq = data.get("sequence", 1)
                except json.JSONDecodeError:
                    pass
            yield chunk
            if format == ExportFormat.JSONL:
                try:
                    data = json.loads(chunk)
                    last_seq = data.get("sequence", last_seq)
                except json.JSONDecodeError:
                    pass

        if include_attestation:
            # Generate attestation metadata
            metadata = await export_service.generate_attestation_metadata(
                sequence_start=first_seq or start_sequence or 1,
                sequence_end=last_seq or end_sequence or 0,
                event_count=event_count,
                filter_criteria=filter_criteria,
            )

            if format == ExportFormat.JSONL:
                yield "\n# ATTESTATION METADATA\n"
                yield json.dumps(
                    {"attestation": metadata.model_dump(mode="json")},
                    default=str,
                ) + "\n"

    return StreamingResponse(
        stream_with_attestation(),
        media_type=content_type,
        headers={
            "Content-Disposition": f"attachment; filename=archon72-export.{format.value}",
        },
    )


@router.get("/export/attestation")
async def get_attestation_for_range(
    request: Request,
    start_sequence: int = Query(ge=1, description="First sequence"),
    end_sequence: int = Query(ge=1, description="Last sequence"),
    export_service: ExportService = Depends(get_export_service),
    rate_limiter: ObserverRateLimiter = Depends(get_rate_limiter),
) -> AttestationMetadata:
    """Get attestation metadata for a sequence range (FR140).

    No authentication required (FR44).
    Rate limits identical for all users (FR48).

    Allows third-party attestation services to request metadata
    for a specific range without downloading the full export.

    Args:
        request: The FastAPI request object.
        start_sequence: First sequence in range.
        end_sequence: Last sequence in range.
        export_service: Injected export service.
        rate_limiter: Injected rate limiter.

    Returns:
        AttestationMetadata for the specified range.
    """
    await rate_limiter.check_rate_limit(request)

    # Count events in range
    event_count = await export_service._event_store.count_events_in_range(
        start_sequence, end_sequence
    )

    return await export_service.generate_attestation_metadata(
        sequence_start=start_sequence,
        sequence_end=end_sequence,
        event_count=event_count,
    )
```

### Task 4: Add stream_events to EventStorePort

Extend EventStorePort with streaming capability.

**Files:**
- `src/application/ports/event_store.py` (modify)
- `src/infrastructure/stubs/event_store_stub.py` (modify)
- `tests/unit/application/test_event_store_port.py` (modify)
- `tests/unit/infrastructure/test_event_store_stub.py` (modify)

**Test Cases (RED):**
- `test_port_stream_events_signature`
- `test_port_count_events_in_range_signature`
- `test_stub_stream_events_yields_events`
- `test_stub_stream_events_with_filters`
- `test_stub_count_events_in_range`

**Implementation (GREEN):**
```python
# In src/application/ports/event_store.py (additions)

async def stream_events(
    self,
    start_sequence: Optional[int] = None,
    end_sequence: Optional[int] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    event_types: Optional[list[str]] = None,
    batch_size: int = 100,
) -> AsyncIterator[Event]:
    """Stream events matching criteria (FR139).

    Yields events in batches for memory efficiency.

    Args:
        start_sequence: First sequence to include.
        end_sequence: Last sequence to include.
        start_date: Filter from date.
        end_date: Filter until date.
        event_types: Filter by event types.
        batch_size: Number of events per DB query.

    Yields:
        Events matching criteria.
    """
    ...

async def count_events_in_range(
    self,
    start_sequence: int,
    end_sequence: int,
) -> int:
    """Count events in sequence range.

    Args:
        start_sequence: First sequence.
        end_sequence: Last sequence.

    Returns:
        Number of events in range.
    """
    ...
```

### Task 5: Add export command to verification toolkit

Add export download and verification to CLI.

**Files:**
- `tools/archon72-verify/archon72_verify/cli.py` (modify)
- `tools/archon72-verify/archon72_verify/client.py` (modify)
- `tools/archon72-verify/tests/test_cli.py` (modify)

**Test Cases (RED):**
- `test_export_command_downloads_jsonl`
- `test_export_command_downloads_csv`
- `test_export_verify_attestation`
- `test_export_with_date_filter`

**Implementation (GREEN):**
```python
# In tools/archon72-verify/archon72_verify/cli.py (additions)

@app.command()
def export(
    output: Path = typer.Argument(
        ...,
        help="Output file path for exported data",
    ),
    format: str = typer.Option(
        "jsonl",
        "--format",
        "-f",
        help="Export format: jsonl or csv",
    ),
    start_date: Optional[str] = typer.Option(
        None,
        "--start-date",
        "-s",
        help="Filter from date (ISO 8601)",
    ),
    end_date: Optional[str] = typer.Option(
        None,
        "--end-date",
        "-e",
        help="Filter until date (ISO 8601)",
    ),
    event_types: Optional[str] = typer.Option(
        None,
        "--types",
        "-t",
        help="Filter by event type(s), comma-separated",
    ),
    include_attestation: bool = typer.Option(
        False,
        "--attestation",
        "-a",
        help="Include attestation metadata",
    ),
    api_url: str = typer.Option(
        "http://localhost:8000",
        "--api-url",
        "-u",
        help="API base URL",
    ),
) -> None:
    """Export events to file for regulatory/compliance use (FR139).

    Downloads events in the specified format with optional filtering.

    Examples:
        archon72-verify export events.jsonl
        archon72-verify export audit.csv -f csv --attestation
        archon72-verify export events.jsonl -s 2026-01-01 -e 2026-01-31
    """
    client = ObserverClient(api_url)

    console.print(f"[bold]Exporting events to {output}...[/bold]")

    params = {
        "format": format,
        "include_attestation": include_attestation,
    }
    if start_date:
        params["start_date"] = start_date
    if end_date:
        params["end_date"] = end_date
    if event_types:
        params["event_type"] = event_types

    # Stream response to file
    with open(output, "w") as f:
        for chunk in client.export_events_stream(**params):
            f.write(chunk)

    console.print(f"[green]Export complete: {output}[/green]")

    if include_attestation:
        console.print("[dim]Attestation metadata included at end of file[/dim]")


@app.command()
def verify_attestation(
    file: Path = typer.Argument(
        ...,
        help="Path to exported file with attestation",
    ),
    api_url: str = typer.Option(
        "http://localhost:8000",
        "--api-url",
        "-u",
        help="API base URL",
    ),
) -> None:
    """Verify attestation metadata in exported file (FR140).

    Checks that the attestation signature is valid and
    the chain hash matches the current chain state.

    Example:
        archon72-verify verify-attestation audit.jsonl
    """
    # Read file and find attestation metadata
    with open(file) as f:
        lines = f.readlines()

    attestation_line = None
    for line in reversed(lines):
        if line.strip().startswith('{"attestation":'):
            attestation_line = line
            break

    if not attestation_line:
        console.print("[red]ERROR[/red] - No attestation metadata found in file")
        sys.exit(1)

    attestation = json.loads(attestation_line)["attestation"]

    # Verify against current chain
    client = ObserverClient(api_url)
    current_event = client.get_event_by_sequence(attestation["sequence_end"])

    if current_event["content_hash"] == attestation["chain_hash_at_export"]:
        console.print("[green]VALID[/green] - Chain hash matches attestation")
        console.print(f"  Export ID: {attestation['export_id']}")
        console.print(f"  Exported at: {attestation['exported_at']}")
        console.print(f"  Event count: {attestation['event_count']}")
    else:
        console.print("[yellow]WARNING[/yellow] - Chain has changed since export")
        console.print(f"  Export hash: {attestation['chain_hash_at_export']}")
        console.print(f"  Current hash: {current_event['content_hash']}")
```

### Task 6: Integration tests for regulatory export

End-to-end tests for export functionality.

**Files:**
- `tests/integration/test_regulatory_export_integration.py` (new)

**Test Cases:**
- `test_export_jsonl_full_chain`
- `test_export_csv_full_chain`
- `test_export_with_attestation_metadata`
- `test_export_with_date_filter`
- `test_export_with_event_type_filter`
- `test_export_attestation_endpoint`
- `test_export_large_dataset_streams`
- `test_export_verify_chain_integrity`

## Technical Notes

### Implementation Order
1. Task 1: Export models (foundation)
2. Task 4: EventStorePort streaming (required for service)
3. Task 2: Export service
4. Task 3: API endpoints
5. Task 5: Toolkit commands
6. Task 6: Integration tests

### Testing Strategy
- Unit tests for each component using pytest
- Integration tests verify end-to-end export flow
- Toolkit tests verify CLI commands work correctly
- All tests follow red-green-refactor TDD cycle

### Constitutional Compliance Matrix
| Requirement | Implementation |
|-------------|----------------|
| FR139 | export_jsonl and export_csv methods |
| FR140 | AttestationMetadata model and endpoint |
| FR44 | No auth on export endpoints |
| FR48 | Same rate limits for all users |
| CT-11 | Full hash data in exports |
| CT-12 | Witness attribution in exports |

### Key Design Decisions
1. **Streaming exports**: Use AsyncIterator for memory-bounded exports
2. **JSON Lines format**: One JSON object per line for streaming and tool compatibility
3. **RFC 4180 CSV**: Standard CSV format for compliance tool import
4. **Attestation metadata**: Separate from data, signed for verification
5. **Filter support**: Reuse existing filtering from /events endpoint

### Performance Considerations
- **Streaming**: Exports use chunked transfer encoding for large datasets
- **Batch queries**: EventStore streams in batches (default 100) to limit memory
- **Rate limiting**: Export endpoints subject to same rate limits as other endpoints
- **File size**: No explicit limit, but rate limits naturally constrain throughput

### Previous Story Intelligence (Story 4.6)
From Story 4.6 completion:
- Observer API patterns established
- Rate limiting applies to all endpoints
- Streaming responses work with FastAPI
- Toolkit CLI patterns established with typer

Files that will be extended:
- `src/api/models/observer.py` - Add export-related models
- `src/api/routes/observer.py` - Add export endpoint
- `src/application/ports/event_store.py` - Add streaming method
- `tools/archon72-verify/` - Add export command

### Patterns to Follow
- Use Pydantic models for all API request/response types
- Async/await for all I/O operations
- Type hints on all functions
- FastAPI Query parameters for API options
- Structlog for any logging (no print, no f-strings in logs)
- Domain exceptions for error cases
- Protocol classes for ports (dependency inversion)
- StreamingResponse for large data exports

## Dev Notes

### Project Structure Notes
- API routes: `src/api/routes/observer.py`
- Models: `src/api/models/observer.py`
- New service: `src/application/services/export_service.py`
- Port extension: `src/application/ports/event_store.py`
- Toolkit: `tools/archon72-verify/`

### References
- [Source: _bmad-output/planning-artifacts/epics.md#Story-4.7]
- [Source: _bmad-output/planning-artifacts/architecture.md#ADR-8]
- [Source: _bmad-output/planning-artifacts/architecture.md#ADR-9]
- [Source: src/api/routes/observer.py - Existing observer endpoints]
- [Source: src/api/models/observer.py - Existing observer models]
- [Source: tools/archon72-verify/ - Verification toolkit]
- [Source: _bmad-output/implementation-artifacts/stories/4-6-merkle-paths-for-light-verification.md - Previous story]
- [Source: _bmad-output/project-context.md - Project patterns and constraints]

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List

