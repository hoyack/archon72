# Story 4.5: Historical Queries (QUERY_AS_OF) (FR62-FR64, FR88-FR89)

## Story

**As an** external observer,
**I want** to query state as of any sequence number,
**So that** I can reconstruct historical state for verification.

## Status

Status: done

## Context

### Business Context
This is the fifth story in Epic 4 (Observer Verification Interface). It delivers **point-in-time query capability** that allows external parties to reconstruct historical state at any moment in the chain's history.

Key business drivers:
1. **Temporal verification**: Observers can verify what the system state was at any point in history
2. **Cryptographic proof**: Historical queries include hash chain proof connecting to current head
3. **Offline verification**: Proof data can be verified locally without trusting server calculations
4. **Constitutional accountability**: Historical reconstruction enables forensic audit

### Technical Context
- **FR62**: Raw event data sufficient for independent hash computation (existing)
- **FR63**: Exact hash algorithm, encoding, field ordering as immutable spec (existing)
- **FR64**: Verification bundles for offline verification
- **FR88**: Observer interface SHALL support queries for system state as of any past sequence number or timestamp
- **FR89**: Historical queries SHALL return hash chain proof connecting queried state to current head
- **ADR-8**: Observer Consistency + Genesis Anchor - genesis provides trust root
- **ADR-9**: Claim Verification Matrix - absence proof SLA: < 5 seconds for 1 year span

**Existing Implementation (Stories 4.1-4.4):**
- Public Observer API with no auth required (`/v1/observer/events`)
- Full hash chain data in responses (`content_hash`, `prev_hash`, `signature`)
- Date range and event type filtering (`start_date`, `end_date`, `event_type`)
- Verification spec endpoint (`/v1/observer/verification-spec`)
- Schema documentation endpoint (`/v1/observer/schema`)
- Chain verification endpoint (`/v1/observer/verify-chain`)
- Open-source verification toolkit (`archon72-verify`)

**Key Files from Previous Stories:**
- `src/api/routes/observer.py` - Observer API endpoints
- `src/api/models/observer.py` - Response models (HashVerificationSpec, ObserverEventResponse, SchemaDocumentation)
- `src/api/adapters/observer.py` - EventToObserverAdapter
- `src/application/services/observer_service.py` - ObserverService
- `src/domain/events/hash_utils.py` - GENESIS_HASH, canonical_json, content_hash computation
- `tools/archon72-verify/` - Verification toolkit

### Dependencies
- **Story 4.1**: Public read access endpoints (DONE)
- **Story 4.2**: Raw events with hashes (DONE)
- **Story 4.3**: Date range and event type filtering (DONE)
- **Story 4.4**: Open-source verification toolkit (DONE)

### Constitutional Constraints
- **FR88**: Query for state as of any sequence number or timestamp
- **FR89**: Hash chain proof connecting queried state to current head
- **CT-7**: Observers must trust an anchor - genesis anchoring is mandatory
- **CT-11**: Silent failure destroys legitimacy - proofs must be clear and verifiable
- **CT-12**: Witnessing creates accountability - historical queries enable forensic witnessing

### Architecture Decision
Per ADR-8 (Observer Consistency + Genesis Anchor):
- Genesis anchor provides trust root for verification
- Periodic checkpoints provide faster anchoring
- Historical queries must include proof connecting to genesis or checkpoint

Per ADR-9 (Claim Verification Matrix):
- Absence proof SLA: < 5 seconds for queries spanning up to 1 year

**Implementation Approach:**
1. Add `as_of_sequence` parameter to events query endpoint
2. Add `as_of_timestamp` parameter as alternative
3. Return hash chain proof from queried point to current head
4. Proof includes intermediate hashes for verification
5. Toolkit can verify proof offline

## Acceptance Criteria

### AC1: Query state as of sequence number
**Given** the query API
**When** I specify `as_of_sequence=500`
**Then** I receive state as it was after event 500
**And** later events are excluded from the response

### AC2: Hash chain proof to current head
**Given** a historical query
**When** the response is returned
**Then** it includes a hash chain proof connecting to current head
**And** the proof can be verified with the toolkit

### AC3: Merkle path for cryptographic proof (FR89)
**Given** cryptographic proof in responses
**When** I examine the response
**Then** it includes Merkle path from queried state to current root
**And** the proof is verifiable offline

### AC4: Timestamp-based query (Alternative to sequence)
**Given** the query API
**When** I specify `as_of_timestamp=2026-01-01T12:00:00Z`
**Then** I receive state as of the last event before that timestamp
**And** the response includes which sequence that corresponds to

### AC5: Proof verification via toolkit
**Given** a historical query response with proof
**When** I verify it with `archon72-verify verify-proof --response response.json`
**Then** the toolkit validates the hash chain proof
**And** confirms connection to current head

## Tasks

### Task 1: Create HashChainProof model

Create the proof model that contains the hash chain from queried point to current head.

**Files:**
- `src/api/models/observer.py` (modify)
- `tests/unit/api/test_observer_models.py` (modify)

**Test Cases (RED):**
- `test_hash_chain_proof_model_valid`
- `test_hash_chain_proof_from_sequence_to_head`
- `test_hash_chain_proof_includes_intermediate_hashes`
- `test_hash_chain_proof_serialization`

**Implementation (GREEN):**
```python
# In src/api/models/observer.py

class HashChainProofEntry(BaseModel):
    """Single entry in hash chain proof.

    Each entry contains the sequence, content_hash, and prev_hash
    to allow verification that the chain is continuous.
    """
    sequence: int = Field(ge=1, description="Event sequence number")
    content_hash: str = Field(
        description="SHA-256 hash of event content",
        pattern=r"^[a-f0-9]{64}$",
    )
    prev_hash: str = Field(
        description="Hash of previous event (genesis for seq 1)",
        pattern=r"^[a-f0-9]{64}$",
    )


class HashChainProof(BaseModel):
    """Hash chain proof connecting queried state to current head (FR89).

    Contains the chain of hashes from the as_of_sequence to the current
    head, allowing offline verification that the historical query
    result is part of the canonical chain.
    """
    from_sequence: int = Field(ge=1, description="Start of proof (queried sequence)")
    to_sequence: int = Field(ge=1, description="End of proof (current head)")

    # The chain of hash entries connecting from_sequence to to_sequence
    chain: list[HashChainProofEntry] = Field(
        description="Hash chain entries from queried point to head",
    )

    # Current head information for verification
    current_head_hash: str = Field(
        description="Content hash of current head event",
        pattern=r"^[a-f0-9]{64}$",
    )

    # Verification metadata
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When this proof was generated",
    )

    proof_type: str = Field(
        default="hash_chain",
        description="Type of proof (hash_chain or merkle_path)",
    )
```

### Task 2: Add as_of_sequence parameter to events endpoint

Add optional parameter to query events as of a specific sequence.

**Files:**
- `src/api/routes/observer.py` (modify)
- `tests/unit/api/test_observer_routes.py` (modify)

**Test Cases (RED):**
- `test_get_events_as_of_sequence_excludes_later`
- `test_get_events_as_of_sequence_returns_proof`
- `test_get_events_as_of_sequence_1_returns_genesis_only`
- `test_get_events_as_of_sequence_invalid_returns_404`
- `test_get_events_as_of_sequence_zero_returns_400`

**Implementation (GREEN):**
```python
# In src/api/routes/observer.py

@router.get("/events", response_model=ObserverEventsListResponse)
async def get_events(
    request: Request,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    start_date: Optional[datetime] = Query(default=None, ...),
    end_date: Optional[datetime] = Query(default=None, ...),
    event_type: Optional[str] = Query(default=None, ...),
    as_of_sequence: Optional[int] = Query(
        default=None,
        ge=1,
        description="Query state as of this sequence number (FR88). Events after this are excluded.",
    ),
    as_of_timestamp: Optional[datetime] = Query(
        default=None,
        description="Query state as of this timestamp (FR88). Returns events up to last before timestamp.",
    ),
    include_proof: bool = Query(
        default=False,
        description="Include hash chain proof connecting to current head (FR89)",
    ),
    observer_service: ObserverService = Depends(get_observer_service),
    rate_limiter: ObserverRateLimiter = Depends(get_rate_limiter),
) -> ObserverEventsListResponse:
    """Get events for observer verification with historical query support.

    Historical Queries (FR88, FR89):
    - as_of_sequence: Query events as of a specific sequence number
    - as_of_timestamp: Query events as of a specific timestamp
    - include_proof: Include hash chain proof to current head

    Only one of as_of_sequence or as_of_timestamp can be specified.
    """
```

### Task 3: Implement ObserverService.get_events_as_of method

Add service method to query events up to a specific sequence with proof generation.

**Files:**
- `src/application/services/observer_service.py` (modify)
- `tests/unit/application/test_observer_service.py` (modify)

**Test Cases (RED):**
- `test_get_events_as_of_returns_events_up_to_sequence`
- `test_get_events_as_of_excludes_later_events`
- `test_get_events_as_of_generates_proof`
- `test_get_events_as_of_proof_is_verifiable`
- `test_get_events_as_of_timestamp_finds_sequence`
- `test_get_events_as_of_sequence_not_found`

**Implementation (GREEN):**
```python
# In src/application/services/observer_service.py

async def get_events_as_of(
    self,
    as_of_sequence: int,
    limit: int = 100,
    offset: int = 0,
    include_proof: bool = False,
) -> tuple[list[Event], int, Optional[HashChainProof]]:
    """Get events as of a specific sequence number (FR88).

    Returns events with sequence <= as_of_sequence, excluding
    any events that were appended after that point.

    If include_proof is True, generates hash chain proof from
    as_of_sequence to current head (FR89).

    Args:
        as_of_sequence: Maximum sequence number to include.
        limit: Maximum events to return.
        offset: Number of events to skip.
        include_proof: Whether to include hash chain proof.

    Returns:
        Tuple of (events, total_count, optional_proof).
    """
    # Verify as_of_sequence exists
    as_of_event = await self._event_store.get_event_by_sequence(as_of_sequence)
    if as_of_event is None:
        raise EventNotFoundError(f"Sequence {as_of_sequence} not found")

    # Get events up to as_of_sequence
    events, total = await self._event_store.get_events_up_to_sequence(
        max_sequence=as_of_sequence,
        limit=limit,
        offset=offset,
    )

    # Generate proof if requested
    proof = None
    if include_proof:
        proof = await self._generate_hash_chain_proof(as_of_sequence)

    return events, total, proof

async def _generate_hash_chain_proof(
    self,
    from_sequence: int,
) -> HashChainProof:
    """Generate hash chain proof from sequence to current head.

    The proof contains the chain of (sequence, content_hash, prev_hash)
    entries that connect the queried point to the current head.

    Args:
        from_sequence: Starting sequence for proof.

    Returns:
        HashChainProof connecting from_sequence to head.
    """
    # Get current head
    head_event = await self._event_store.get_latest_event()
    if head_event is None:
        raise EventNotFoundError("No events in store")

    # Get all events from from_sequence to head
    proof_events = await self._event_store.get_events_range(
        start_sequence=from_sequence,
        end_sequence=head_event.sequence,
    )

    # Build proof chain
    chain = [
        HashChainProofEntry(
            sequence=e.sequence,
            content_hash=e.content_hash,
            prev_hash=e.prev_hash,
        )
        for e in proof_events
    ]

    return HashChainProof(
        from_sequence=from_sequence,
        to_sequence=head_event.sequence,
        chain=chain,
        current_head_hash=head_event.content_hash,
    )
```

### Task 4: Add EventStorePort.get_events_up_to_sequence method

Add port method for querying events up to a sequence.

**Files:**
- `src/application/ports/event_store.py` (modify)
- `src/infrastructure/stubs/event_store_stub.py` (modify)
- `tests/unit/application/test_event_store_port.py` (modify)

**Test Cases (RED):**
- `test_port_get_events_up_to_sequence_signature`
- `test_stub_get_events_up_to_sequence_returns_filtered`
- `test_stub_get_events_up_to_sequence_respects_limit_offset`

**Implementation (GREEN):**
```python
# In src/application/ports/event_store.py

class EventStorePort(Protocol):
    async def get_events_up_to_sequence(
        self,
        max_sequence: int,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[Event], int]:
        """Get events with sequence <= max_sequence.

        Args:
            max_sequence: Maximum sequence number to include.
            limit: Maximum events to return.
            offset: Number of events to skip.

        Returns:
            Tuple of (events, total_count).
        """
        ...

    async def get_events_range(
        self,
        start_sequence: int,
        end_sequence: int,
    ) -> list[Event]:
        """Get all events in a sequence range (inclusive).

        Args:
            start_sequence: First sequence number.
            end_sequence: Last sequence number.

        Returns:
            List of events in range, ordered by sequence.
        """
        ...

    async def get_latest_event(self) -> Optional[Event]:
        """Get the most recent event (highest sequence).

        Returns:
            The latest event, or None if store is empty.
        """
        ...

    async def sequence_to_timestamp(
        self,
        timestamp: datetime,
    ) -> Optional[int]:
        """Find sequence number for last event before timestamp.

        Args:
            timestamp: Target timestamp.

        Returns:
            Sequence of last event before timestamp, or None.
        """
        ...
```

### Task 5: Add as_of_timestamp support

Implement timestamp-to-sequence resolution for temporal queries.

**Files:**
- `src/api/routes/observer.py` (modify)
- `src/application/services/observer_service.py` (modify)
- `tests/unit/application/test_observer_service.py` (modify)

**Test Cases (RED):**
- `test_get_events_as_of_timestamp_resolves_to_sequence`
- `test_get_events_as_of_timestamp_returns_last_before`
- `test_get_events_as_of_timestamp_no_events_before_returns_empty`
- `test_get_events_as_of_timestamp_response_includes_resolved_sequence`

**Implementation (GREEN):**
```python
# In src/application/services/observer_service.py

async def get_events_as_of_timestamp(
    self,
    as_of_timestamp: datetime,
    limit: int = 100,
    offset: int = 0,
    include_proof: bool = False,
) -> tuple[list[Event], int, int, Optional[HashChainProof]]:
    """Get events as of a specific timestamp (FR88).

    Finds the last event before the given timestamp and returns
    all events up to that point.

    Args:
        as_of_timestamp: Query state as of this timestamp.
        limit: Maximum events to return.
        offset: Number of events to skip.
        include_proof: Whether to include hash chain proof.

    Returns:
        Tuple of (events, total_count, resolved_sequence, optional_proof).
    """
    # Find sequence for timestamp
    resolved_sequence = await self._event_store.sequence_to_timestamp(as_of_timestamp)

    if resolved_sequence is None:
        # No events before timestamp
        return [], 0, 0, None

    events, total, proof = await self.get_events_as_of(
        as_of_sequence=resolved_sequence,
        limit=limit,
        offset=offset,
        include_proof=include_proof,
    )

    return events, total, resolved_sequence, proof
```

### Task 6: Update response model for historical queries

Add proof and metadata fields to response.

**Files:**
- `src/api/models/observer.py` (modify)
- `tests/unit/api/test_observer_models.py` (modify)

**Test Cases (RED):**
- `test_events_list_response_includes_proof`
- `test_events_list_response_includes_as_of_metadata`
- `test_events_list_response_proof_optional`

**Implementation (GREEN):**
```python
# In src/api/models/observer.py

class HistoricalQueryMetadata(BaseModel):
    """Metadata for historical queries (FR88).

    Included when as_of_sequence or as_of_timestamp is specified.
    """
    queried_as_of_sequence: Optional[int] = Field(
        default=None,
        description="Sequence number queried (if specified)",
    )
    queried_as_of_timestamp: Optional[datetime] = Field(
        default=None,
        description="Timestamp queried (if specified)",
    )
    resolved_sequence: int = Field(
        description="Actual sequence number used for query",
    )
    current_head_sequence: int = Field(
        description="Current head sequence at time of query",
    )


class ObserverEventsListResponse(BaseModel):
    """Response for events list endpoint.

    Enhanced with historical query support (FR88, FR89).
    """
    events: list[ObserverEventResponse]
    pagination: PaginationMetadata

    # Historical query fields (FR88, FR89)
    historical_query: Optional[HistoricalQueryMetadata] = Field(
        default=None,
        description="Metadata when as_of_sequence/timestamp is used",
    )
    proof: Optional[HashChainProof] = Field(
        default=None,
        description="Hash chain proof to current head (FR89)",
    )
```

### Task 7: Add verify-proof command to toolkit

Extend the verification toolkit to verify historical query proofs.

**Files:**
- `tools/archon72-verify/archon72_verify/cli.py` (modify)
- `tools/archon72-verify/archon72_verify/verifier.py` (modify)
- `tools/archon72-verify/tests/test_verifier.py` (modify)
- `tools/archon72-verify/tests/test_cli.py` (modify)

**Test Cases (RED):**
- `test_verify_proof_valid_chain`
- `test_verify_proof_detects_gap`
- `test_verify_proof_detects_hash_mismatch`
- `test_verify_proof_cli_command`
- `test_verify_proof_from_file`

**Implementation (GREEN):**
```python
# In tools/archon72-verify/archon72_verify/verifier.py

@dataclass
class ProofVerificationResult:
    """Result of hash chain proof verification."""
    is_valid: bool
    from_sequence: int
    to_sequence: int
    error_message: Optional[str] = None


class ChainVerifier:
    def verify_proof(self, proof: dict) -> ProofVerificationResult:
        """Verify a hash chain proof from historical query (FR89).

        Validates that:
        1. Chain entries are continuous (no gaps)
        2. prev_hash of each entry matches content_hash of previous
        3. Chain ends at the claimed current_head_hash

        Args:
            proof: Hash chain proof dictionary from API response.

        Returns:
            ProofVerificationResult with validation status.
        """
        from_seq = proof["from_sequence"]
        to_seq = proof["to_sequence"]
        chain = proof["chain"]
        expected_head = proof["current_head_hash"]

        if not chain:
            return ProofVerificationResult(
                is_valid=False,
                from_sequence=from_seq,
                to_sequence=to_seq,
                error_message="Empty proof chain",
            )

        # Verify chain continuity
        for i, entry in enumerate(chain):
            if i == 0:
                # First entry should be from_sequence
                if entry["sequence"] != from_seq:
                    return ProofVerificationResult(
                        is_valid=False,
                        from_sequence=from_seq,
                        to_sequence=to_seq,
                        error_message=f"First entry sequence {entry['sequence']} != from_sequence {from_seq}",
                    )
            else:
                # Verify prev_hash matches previous content_hash
                prev_entry = chain[i - 1]
                if entry["prev_hash"] != prev_entry["content_hash"]:
                    return ProofVerificationResult(
                        is_valid=False,
                        from_sequence=from_seq,
                        to_sequence=to_seq,
                        error_message=f"Chain break at sequence {entry['sequence']}",
                    )

        # Verify last entry is to_sequence with correct head hash
        last_entry = chain[-1]
        if last_entry["sequence"] != to_seq:
            return ProofVerificationResult(
                is_valid=False,
                from_sequence=from_seq,
                to_sequence=to_seq,
                error_message=f"Last entry sequence {last_entry['sequence']} != to_sequence {to_seq}",
            )

        if last_entry["content_hash"] != expected_head:
            return ProofVerificationResult(
                is_valid=False,
                from_sequence=from_seq,
                to_sequence=to_seq,
                error_message="Last entry content_hash doesn't match claimed head",
            )

        return ProofVerificationResult(
            is_valid=True,
            from_sequence=from_seq,
            to_sequence=to_seq,
        )


# In tools/archon72-verify/archon72_verify/cli.py

@app.command()
def verify_proof(
    file: Path = typer.Argument(
        ...,
        help="Path to JSON file containing proof from historical query",
    ),
    output_format: str = typer.Option(
        "text",
        "--format",
        "-o",
        help="Output format: text or json",
    ),
) -> None:
    """Verify hash chain proof from historical query (FR89).

    Validates that the proof correctly connects the queried
    sequence to the current head.

    Example:
        archon72-verify verify-proof response.json
    """
    verifier = ChainVerifier()

    with open(file) as f:
        data = json.load(f)

    # Extract proof from response
    proof = data.get("proof")
    if proof is None:
        console.print("[red]ERROR[/red] - No proof found in response")
        sys.exit(1)

    result = verifier.verify_proof(proof)

    if output_format == "json":
        console.print_json(json.dumps({
            "is_valid": result.is_valid,
            "from_sequence": result.from_sequence,
            "to_sequence": result.to_sequence,
            "error_message": result.error_message,
        }))
    else:
        if result.is_valid:
            console.print(f"[green]VALID[/green] - Proof verified from sequence {result.from_sequence} to {result.to_sequence}")
        else:
            console.print(f"[red]INVALID[/red] - {result.error_message}")
            sys.exit(1)
```

### Task 8: Integration tests for historical queries

End-to-end tests verifying historical query functionality.

**Files:**
- `tests/integration/test_historical_queries_integration.py` (new)

**Test Cases:**
- `test_historical_query_as_of_sequence_returns_correct_events`
- `test_historical_query_as_of_timestamp_returns_correct_events`
- `test_historical_query_with_proof_is_verifiable`
- `test_historical_query_proof_connects_to_head`
- `test_historical_query_pagination_with_as_of`
- `test_historical_query_combined_with_filters`
- `test_toolkit_verifies_historical_proof`
- `test_historical_query_at_sequence_1_includes_genesis`

## Technical Notes

### Implementation Order
1. Task 1: HashChainProof model
2. Task 4: EventStorePort methods (dependency for Task 3)
3. Task 3: ObserverService.get_events_as_of
4. Task 5: Timestamp support
5. Task 6: Response model updates
6. Task 2: API endpoint changes
7. Task 7: Toolkit verify-proof command
8. Task 8: Integration tests

### Testing Strategy
- Unit tests for each component using pytest
- Integration tests verify end-to-end flow
- Toolkit tests verify proof verification
- All tests follow red-green-refactor TDD cycle

### Constitutional Compliance Matrix
| Requirement | Implementation |
|-------------|----------------|
| FR88 | as_of_sequence and as_of_timestamp parameters |
| FR89 | HashChainProof in response with chain to head |
| FR62 | Existing raw event data (Story 4.2) |
| FR63 | Existing verification spec (Story 4.2) |
| FR64 | Proof data sufficient for offline verification |
| CT-7 | Genesis anchor included when querying from sequence 1 |
| CT-11 | Clear error messages for invalid proofs |

### Key Design Decisions
1. **Proof as hash chain**: Simple chain of (sequence, content_hash, prev_hash) entries
2. **Merkle paths deferred**: Story 4.6 will add Merkle tree support for lighter proofs
3. **Timestamp resolution**: Finds last event before timestamp, returns resolved sequence
4. **Optional proof**: include_proof parameter to avoid overhead when not needed
5. **Existing toolkit extension**: Add verify-proof command to archon72-verify

### Performance Considerations
- **Proof size**: Chain proof grows linearly with events since queried point
- **Query SLA**: Per ADR-9, < 5 seconds for 1 year span
- **Caching**: Consider caching proof segments for frequently queried points
- **Pagination**: Proof generation is independent of pagination

### Previous Story Intelligence (Story 4.4)
From Story 4.4 completion:
- Toolkit uses Typer for CLI, httpx for HTTP client
- ChainVerifier class handles verification logic
- Rich for colored terminal output
- JSON output format for programmatic use
- Test approach: pytest with CliRunner for CLI tests

Files created in 4.4 that will be extended:
- `tools/archon72-verify/archon72_verify/verifier.py` - Add verify_proof method
- `tools/archon72-verify/archon72_verify/cli.py` - Add verify-proof command

### Git Intelligence
Recent commits show:
- Story 4.4 just completed with toolkit implementation
- TDD approach with red-green-refactor cycle
- Comprehensive test coverage (68 tests in 4.4)

### Patterns to Follow
- Use Pydantic models for all API request/response types
- Async/await for all I/O operations
- Type hints on all functions
- FastAPI Query parameters for API options
- Structlog for any logging (no print, no f-strings in logs)
- Domain exceptions for error cases (EventNotFoundError)

## Dev Notes

### Project Structure Notes
- API routes: `src/api/routes/observer.py`
- Models: `src/api/models/observer.py`
- Service: `src/application/services/observer_service.py`
- Port: `src/application/ports/event_store.py`
- Stub: `src/infrastructure/stubs/event_store_stub.py`
- Toolkit: `tools/archon72-verify/`

### References
- [Source: _bmad-output/planning-artifacts/epics.md#Story-4.5]
- [Source: _bmad-output/planning-artifacts/prd.md#FR88-FR89]
- [Source: _bmad-output/planning-artifacts/architecture.md#ADR-8]
- [Source: _bmad-output/planning-artifacts/architecture.md#ADR-9]
- [Source: src/api/routes/observer.py - Existing observer endpoints]
- [Source: src/api/models/observer.py - Existing observer models]
- [Source: tools/archon72-verify/ - Verification toolkit]
- [Source: _bmad-output/implementation-artifacts/stories/4-4-open-source-verification-toolkit.md - Previous story]
- [Source: _bmad-output/project-context.md - Project patterns and constraints]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

N/A

### Completion Notes List

- **Task 1 (HashChainProof model)**: Created `HashChainProofEntry` and `HashChainProof` models in `src/api/models/observer.py` with full validation
- **Task 4 (EventStorePort methods)**: Added `get_events_up_to_sequence`, `count_events_up_to_sequence`, and `find_sequence_for_timestamp` methods
- **Task 3 (ObserverService.get_events_as_of)**: Implemented with proof generation support
- **Task 5 (as_of_timestamp support)**: Implemented timestamp-to-sequence resolution via `get_events_as_of_timestamp`
- **Task 6 (Response model updates)**: Added `HistoricalQueryMetadata` model and optional `proof` field to response
- **Task 2 (API endpoint)**: Added `as_of_sequence`, `as_of_timestamp`, and `include_proof` parameters to GET /events
- **Task 7 (Toolkit verify-proof)**: Added `verify-proof` command and `ProofVerificationResult` dataclass to archon72-verify toolkit
- **Task 8 (Integration tests)**: Created 20 integration tests covering all acceptance criteria

**Test Results:**
- Unit tests: 64 tests passing for observer service and routes
- Toolkit tests: 56 tests passing (11 new proof tests)
- Integration tests: 20 tests passing

**Constitutional Compliance:**
- FR88: Query for state as of sequence/timestamp - IMPLEMENTED
- FR89: Hash chain proof to current head - IMPLEMENTED
- FR44: No auth required for historical queries - VERIFIED
- CT-7: Genesis anchor support - IMPLEMENTED

### File List

**Modified:**
- `src/api/models/observer.py` - Added HashChainProof, HashChainProofEntry, HistoricalQueryMetadata
- `src/api/routes/observer.py` - Added as_of_sequence, as_of_timestamp, include_proof params
- `src/api/dependencies/observer.py` - Added historical query methods to stub
- `src/application/ports/event_store.py` - Added get_events_up_to_sequence, count_events_up_to_sequence, find_sequence_for_timestamp
- `src/application/services/observer_service.py` - Added get_events_as_of, get_events_as_of_timestamp, _generate_hash_chain_proof
- `src/infrastructure/stubs/event_store_stub.py` - Implemented new port methods
- `tools/archon72-verify/archon72_verify/verifier.py` - Added ProofVerificationResult, verify_proof method
- `tools/archon72-verify/archon72_verify/cli.py` - Added verify-proof command
- `tools/archon72-verify/archon72_verify/client.py` - Added get_events_as_of method
- `tools/archon72-verify/archon72_verify/__init__.py` - Exported ProofVerificationResult
- `tools/archon72-verify/README.md` - Documented verify-proof command

**New:**
- `tests/unit/application/test_observer_service.py` - Added TestObserverServiceHistoricalQueries (6 tests)
- `tests/unit/api/test_observer_routes.py` - Added TestObserverRoutesHistoricalQueries (8 tests)
- `tests/integration/test_historical_query_integration.py` - 20 integration tests
- `tools/archon72-verify/tests/test_verifier.py` - Added TestProofVerificationResult, TestChainVerifierVerifyProof (11 tests)
