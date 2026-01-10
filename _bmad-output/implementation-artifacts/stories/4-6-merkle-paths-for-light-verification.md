# Story 4.6: Merkle Paths for Light Verification (FR136-FR138)

## Story

**As an** external observer,
**I want** Merkle paths included in responses,
**So that** I can perform light verification without full chain download.

## Status

Status: done

## Context

### Business Context
This is the sixth story in Epic 4 (Observer Verification Interface). It delivers **Merkle tree proofs** that enable lightweight verification without downloading the entire event chain.

Key business drivers:
1. **Scalability**: As the chain grows, observers need O(log n) proofs instead of O(n)
2. **Light clients**: Mobile and embedded verifiers can participate without full chain
3. **Bandwidth efficiency**: Proof size is logarithmic, not linear with chain length
4. **Checkpoint anchoring**: Weekly checkpoints provide trusted roots for verification

### Technical Context
- **FR136**: Merkle proof SHALL be included in event query responses when requested
- **FR137**: Observers SHALL be able to verify event inclusion without downloading full chain
- **FR138**: Weekly checkpoint anchors SHALL be published at consistent intervals
- **ADR-8**: Observer Consistency + Genesis Anchor - periodic checkpoints for faster anchoring
- **ADR-9**: Claim Verification Matrix - absence proof SLA: < 5 seconds for 1 year span

**Story 4.5 Delivered:**
- `HashChainProof` model with linear chain of entries
- `as_of_sequence` and `as_of_timestamp` parameters
- `include_proof=true` to get hash chain proof
- `verify-proof` command in toolkit

**Key Limitation of Story 4.5:**
- Hash chain proof grows linearly: O(n) entries for n events since queried point
- For large chains, this becomes bandwidth-prohibitive
- Merkle proofs are O(log n) - much more efficient

**Key Files from Previous Stories:**
- `src/api/models/observer.py` - HashChainProof, HashChainProofEntry, HistoricalQueryMetadata
- `src/api/routes/observer.py` - Observer API endpoints with include_proof parameter
- `src/application/services/observer_service.py` - ObserverService with _generate_hash_chain_proof
- `src/application/ports/event_store.py` - EventStorePort
- `tools/archon72-verify/` - Verification toolkit with verify-proof command

### Dependencies
- **Story 4.5**: Historical queries with hash chain proof (DONE) - foundation for Merkle proof
- **Story 4.2**: Raw events with hashes (DONE) - content_hash available
- **Story 4.4**: Open-source verification toolkit (DONE) - toolkit to extend

### Constitutional Constraints
- **FR136**: Merkle proof in responses when requested
- **FR137**: Verify without downloading full chain
- **FR138**: Weekly checkpoint anchors at consistent intervals
- **CT-7**: Observers must trust an anchor - checkpoints provide anchoring
- **CT-11**: Silent failure destroys legitimacy - proofs must be verifiable
- **ADR-8**: Genesis anchor + periodic checkpoints (RFC 3161 timestamping)

### Architecture Decision
Per ADR-8 (Observer Consistency + Genesis Anchor):
- Genesis anchor provides ultimate trust root (Bitcoin OP_RETURN)
- Periodic checkpoints via RFC 3161 timestamping service
- Observers can verify against either genesis or checkpoint

**Merkle Tree Design:**
1. **Checkpoint-based Merkle trees**: Build Merkle tree for each checkpoint interval
2. **Incremental proofs**: Proof connects event → checkpoint root → genesis
3. **Weekly schedule**: New checkpoint every Sunday at 00:00 UTC
4. **Checkpoint model**: Store Merkle root, sequence range, timestamp

## Acceptance Criteria

### AC1: Merkle proof included in event query
**Given** an event query with `include_merkle_proof=true`
**When** I receive the response
**Then** a Merkle proof is included connecting the event to the checkpoint root
**And** the proof contains sibling hashes for each tree level

### AC2: Verify event without full chain download
**Given** a Merkle proof from the response
**When** I verify it with the toolkit
**Then** I can confirm the event is in the canonical chain
**And** without downloading all events in the checkpoint interval

### AC3: Weekly checkpoint anchors
**Given** the checkpoint query endpoint
**When** I query checkpoints
**Then** I receive checkpoint hashes with timestamps
**And** checkpoints are published at consistent weekly intervals (Sunday 00:00 UTC)

### AC4: Checkpoint Merkle root verification
**Given** a checkpoint's Merkle root
**When** I have an event and its Merkle proof
**Then** I can recompute the Merkle root from the event
**And** verify it matches the checkpoint root

### AC5: Toolkit Merkle verification command
**Given** a response with Merkle proof
**When** I run `archon72-verify verify-merkle --response response.json`
**Then** the toolkit validates the Merkle path
**And** confirms the event is in the canonical chain

## Tasks

### Task 1: Create Checkpoint and MerkleProof models

Create the domain models for checkpoints and Merkle proofs.

**Files:**
- `src/domain/models/checkpoint.py` (modify or create new Merkle-specific models)
- `src/api/models/observer.py` (add API response models)
- `tests/unit/api/test_observer_models.py` (add tests)
- `tests/unit/domain/test_checkpoint.py` (add tests)

**Test Cases (RED):**
- `test_merkle_proof_entry_model_valid`
- `test_merkle_proof_model_valid`
- `test_checkpoint_anchor_model_valid`
- `test_merkle_proof_serialization`

**Implementation (GREEN):**
```python
# In src/api/models/observer.py

class MerkleProofEntry(BaseModel):
    """Single sibling hash in Merkle proof path.

    Each entry represents one level of the Merkle tree,
    containing the sibling hash needed to compute the parent.

    Attributes:
        level: Tree level (0 = leaf level).
        position: Left (0) or right (1) sibling position.
        sibling_hash: Hash of the sibling node.
    """
    level: int = Field(ge=0, description="Tree level (0 = leaves)")
    position: Literal["left", "right"] = Field(
        description="Position of sibling relative to path"
    )
    sibling_hash: str = Field(
        description="SHA-256 hash of sibling node",
        pattern=r"^[a-f0-9]{64}$",
    )


class MerkleProof(BaseModel):
    """Merkle proof connecting event to checkpoint root (FR136).

    Contains the path of sibling hashes needed to recompute
    the Merkle root from the event's content_hash.

    Attributes:
        event_sequence: Sequence number of the proven event.
        event_hash: Content hash of the proven event.
        checkpoint_sequence: Sequence of checkpoint containing this event.
        checkpoint_root: Merkle root of the checkpoint.
        path: List of sibling hashes from leaf to root.
        tree_size: Total number of leaves in the Merkle tree.
        proof_type: Always "merkle" for this proof type.
    """
    event_sequence: int = Field(ge=1, description="Sequence of proven event")
    event_hash: str = Field(
        description="Content hash of proven event",
        pattern=r"^[a-f0-9]{64}$",
    )
    checkpoint_sequence: int = Field(
        ge=1,
        description="Sequence number of checkpoint containing this event"
    )
    checkpoint_root: str = Field(
        description="Merkle root of the checkpoint",
        pattern=r"^[a-f0-9]{64}$",
    )
    path: list[MerkleProofEntry] = Field(
        description="Sibling hashes from leaf to root"
    )
    tree_size: int = Field(ge=1, description="Number of leaves in tree")
    proof_type: str = Field(default="merkle", const=True)
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class CheckpointAnchor(BaseModel):
    """Checkpoint anchor with Merkle root (FR138).

    Represents a weekly checkpoint that anchors a range of events.

    Attributes:
        checkpoint_id: Unique identifier for checkpoint.
        sequence_start: First event sequence in checkpoint.
        sequence_end: Last event sequence in checkpoint.
        merkle_root: Root hash of Merkle tree for events in range.
        created_at: When checkpoint was created.
        anchor_type: Type of external anchor (genesis, rfc3161).
        anchor_reference: External anchor ID/txid.
    """
    checkpoint_id: UUID
    sequence_start: int = Field(ge=1)
    sequence_end: int = Field(ge=1)
    merkle_root: str = Field(pattern=r"^[a-f0-9]{64}$")
    created_at: datetime
    anchor_type: Literal["genesis", "rfc3161", "pending"] = Field(
        default="pending"
    )
    anchor_reference: Optional[str] = Field(
        default=None,
        description="External anchor reference (Bitcoin txid, TSA response)"
    )
    event_count: int = Field(ge=0)
```

### Task 2: Implement Merkle tree builder service

Create a service to build Merkle trees from event hashes.

**Files:**
- `src/application/services/merkle_tree_service.py` (new)
- `tests/unit/application/test_merkle_tree_service.py` (new)

**Test Cases (RED):**
- `test_build_merkle_tree_single_event`
- `test_build_merkle_tree_power_of_two`
- `test_build_merkle_tree_non_power_of_two_pads`
- `test_get_merkle_proof_for_index`
- `test_verify_merkle_proof_valid`
- `test_verify_merkle_proof_invalid_sibling`
- `test_compute_merkle_root_matches_tree`

**Implementation (GREEN):**
```python
# In src/application/services/merkle_tree_service.py

import hashlib
from typing import Optional

from src.api.models.observer import MerkleProof, MerkleProofEntry


def hash_pair(left: str, right: str) -> str:
    """Compute parent hash from two child hashes.

    Uses sorted concatenation to ensure deterministic ordering.
    """
    combined = "".join(sorted([left, right]))
    return hashlib.sha256(combined.encode()).hexdigest()


class MerkleTreeService:
    """Service for building and verifying Merkle trees (FR136, FR137)."""

    def build_tree(self, leaf_hashes: list[str]) -> tuple[str, list[list[str]]]:
        """Build Merkle tree from leaf hashes.

        Pads to next power of 2 if necessary (duplicating last hash).

        Args:
            leaf_hashes: List of content_hash values.

        Returns:
            Tuple of (root_hash, tree_levels).
            tree_levels[0] = leaves, tree_levels[-1] = [root].
        """
        if not leaf_hashes:
            raise ValueError("Cannot build tree from empty list")

        # Pad to power of 2
        leaves = list(leaf_hashes)
        while len(leaves) & (len(leaves) - 1):  # Not power of 2
            leaves.append(leaves[-1])  # Duplicate last

        levels = [leaves]
        current = leaves

        while len(current) > 1:
            next_level = []
            for i in range(0, len(current), 2):
                parent = hash_pair(current[i], current[i + 1])
                next_level.append(parent)
            levels.append(next_level)
            current = next_level

        return current[0], levels

    def get_proof(
        self,
        leaf_index: int,
        tree_levels: list[list[str]],
    ) -> list[MerkleProofEntry]:
        """Generate Merkle proof for a leaf at given index.

        Args:
            leaf_index: Index of leaf in tree (0-based).
            tree_levels: Tree levels from build_tree().

        Returns:
            List of MerkleProofEntry from leaf to root.
        """
        path = []
        idx = leaf_index

        for level in range(len(tree_levels) - 1):
            is_right = idx % 2 == 1
            sibling_idx = idx - 1 if is_right else idx + 1

            if sibling_idx < len(tree_levels[level]):
                sibling_hash = tree_levels[level][sibling_idx]
                path.append(MerkleProofEntry(
                    level=level,
                    position="left" if is_right else "right",
                    sibling_hash=sibling_hash,
                ))

            idx //= 2

        return path

    def verify_proof(
        self,
        leaf_hash: str,
        proof: list[MerkleProofEntry],
        expected_root: str,
    ) -> bool:
        """Verify a Merkle proof.

        Args:
            leaf_hash: Content hash of the event.
            proof: List of sibling hashes.
            expected_root: Expected Merkle root to match.

        Returns:
            True if proof is valid, False otherwise.
        """
        current = leaf_hash

        for entry in proof:
            if entry.position == "left":
                current = hash_pair(entry.sibling_hash, current)
            else:
                current = hash_pair(current, entry.sibling_hash)

        return current == expected_root
```

### Task 3: Create CheckpointPort and stub implementation

Define the port for checkpoint operations.

**Files:**
- `src/application/ports/checkpoint_repository.py` (modify)
- `src/infrastructure/stubs/checkpoint_repository_stub.py` (modify)
- `tests/unit/application/test_checkpoint_repository_port.py` (modify)
- `tests/unit/infrastructure/test_checkpoint_repository_stub.py` (modify)

**Test Cases (RED):**
- `test_port_get_checkpoint_for_sequence_signature`
- `test_port_get_latest_checkpoint_signature`
- `test_port_create_checkpoint_signature`
- `test_port_list_checkpoints_signature`
- `test_stub_get_checkpoint_for_sequence_returns_correct`
- `test_stub_create_checkpoint_stores_and_returns`

**Implementation (GREEN):**
```python
# In src/application/ports/checkpoint_repository.py

from typing import Optional, Protocol
from uuid import UUID

from src.api.models.observer import CheckpointAnchor


class CheckpointRepositoryPort(Protocol):
    """Port for checkpoint storage and retrieval (FR138)."""

    async def get_checkpoint_for_sequence(
        self,
        sequence: int,
    ) -> Optional[CheckpointAnchor]:
        """Get checkpoint containing the given sequence.

        Args:
            sequence: Event sequence number.

        Returns:
            Checkpoint if found, None if sequence is in pending interval.
        """
        ...

    async def get_latest_checkpoint(self) -> Optional[CheckpointAnchor]:
        """Get the most recent checkpoint.

        Returns:
            Latest checkpoint, or None if no checkpoints exist.
        """
        ...

    async def create_checkpoint(
        self,
        sequence_start: int,
        sequence_end: int,
        merkle_root: str,
    ) -> CheckpointAnchor:
        """Create a new checkpoint.

        Args:
            sequence_start: First sequence in checkpoint range.
            sequence_end: Last sequence in checkpoint range.
            merkle_root: Computed Merkle root for the range.

        Returns:
            The created checkpoint.
        """
        ...

    async def list_checkpoints(
        self,
        limit: int = 10,
        offset: int = 0,
    ) -> tuple[list[CheckpointAnchor], int]:
        """List checkpoints with pagination.

        Returns:
            Tuple of (checkpoints, total_count).
        """
        ...

    async def update_anchor_reference(
        self,
        checkpoint_id: UUID,
        anchor_type: str,
        anchor_reference: str,
    ) -> None:
        """Update checkpoint with external anchor reference.

        Called after RFC 3161 timestamping or Bitcoin anchoring.
        """
        ...
```

### Task 4: Implement ObserverService Merkle proof generation

Extend ObserverService to generate Merkle proofs.

**Files:**
- `src/application/services/observer_service.py` (modify)
- `tests/unit/application/test_observer_service.py` (modify)

**Test Cases (RED):**
- `test_generate_merkle_proof_returns_valid_proof`
- `test_generate_merkle_proof_for_event_in_checkpoint`
- `test_generate_merkle_proof_for_pending_event_uses_hash_chain`
- `test_get_events_with_merkle_proof_includes_proof`

**Implementation (GREEN):**
```python
# In src/application/services/observer_service.py (additions)

async def _generate_merkle_proof(
    self,
    event_sequence: int,
) -> Optional[MerkleProof]:
    """Generate Merkle proof for an event (FR136).

    If the event is in a completed checkpoint, generates Merkle proof.
    If the event is in the pending interval (after latest checkpoint),
    returns None and caller should use hash chain proof instead.

    Args:
        event_sequence: Sequence number of event to prove.

    Returns:
        MerkleProof if event is in a checkpoint, None if pending.
    """
    # Get checkpoint containing this event
    checkpoint = await self._checkpoint_repo.get_checkpoint_for_sequence(
        event_sequence
    )

    if checkpoint is None:
        # Event is in pending interval - no Merkle proof available
        return None

    # Get all events in the checkpoint range
    events = await self._event_store.get_events_range(
        start_sequence=checkpoint.sequence_start,
        end_sequence=checkpoint.sequence_end,
    )

    # Build Merkle tree
    leaf_hashes = [e.content_hash for e in events]
    root, levels = self._merkle_service.build_tree(leaf_hashes)

    # Find index of our event
    event_index = event_sequence - checkpoint.sequence_start

    # Generate proof
    path = self._merkle_service.get_proof(event_index, levels)

    # Get the event's hash
    event = await self._event_store.get_event_by_sequence(event_sequence)

    return MerkleProof(
        event_sequence=event_sequence,
        event_hash=event.content_hash,
        checkpoint_sequence=checkpoint.sequence_end,
        checkpoint_root=checkpoint.merkle_root,
        path=path,
        tree_size=len(events),
    )


async def get_events_with_merkle_proof(
    self,
    as_of_sequence: int,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[Event], int, Optional[MerkleProof], Optional[HashChainProof]]:
    """Get events with appropriate proof type (FR136, FR137).

    Returns Merkle proof if events are in completed checkpoints.
    Returns hash chain proof for events in pending interval.

    Args:
        as_of_sequence: Query up to this sequence.
        limit: Maximum events to return.
        offset: Number to skip.

    Returns:
        Tuple of (events, total, merkle_proof, hash_chain_proof).
        Only one proof type will be non-None.
    """
    events, total = await self._event_store.get_events_up_to_sequence(
        max_sequence=as_of_sequence,
        limit=limit,
        offset=offset,
    )

    # Try Merkle proof first
    merkle_proof = await self._generate_merkle_proof(as_of_sequence)

    if merkle_proof is not None:
        return events, total, merkle_proof, None

    # Fall back to hash chain proof for pending events
    hash_proof = await self._generate_hash_chain_proof(as_of_sequence)
    return events, total, None, hash_proof
```

### Task 5: Add checkpoint endpoint to Observer API

Add endpoint to query checkpoints.

**Files:**
- `src/api/routes/observer.py` (modify)
- `tests/unit/api/test_observer_routes.py` (modify)

**Test Cases (RED):**
- `test_get_checkpoints_returns_list`
- `test_get_checkpoints_pagination_works`
- `test_get_checkpoint_by_sequence_returns_correct`
- `test_get_checkpoint_by_sequence_not_found_returns_404`

**Implementation (GREEN):**
```python
# In src/api/routes/observer.py (additions)

@router.get("/checkpoints", response_model=CheckpointListResponse)
async def get_checkpoints(
    request: Request,
    limit: int = Query(default=10, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    observer_service: ObserverService = Depends(get_observer_service),
    rate_limiter: ObserverRateLimiter = Depends(get_rate_limiter),
) -> CheckpointListResponse:
    """Get list of checkpoint anchors (FR138).

    No authentication required (FR44).
    Checkpoints are published at consistent weekly intervals.

    Returns:
        List of checkpoints with Merkle roots and anchor references.
    """
    await rate_limiter.check_rate_limit(request)

    checkpoints, total = await observer_service.list_checkpoints(
        limit=limit,
        offset=offset,
    )

    return CheckpointListResponse(
        checkpoints=checkpoints,
        pagination=PaginationMetadata(
            total_count=total,
            offset=offset,
            limit=limit,
            has_more=(offset + len(checkpoints)) < total,
        ),
    )


@router.get("/checkpoints/sequence/{sequence}", response_model=CheckpointAnchor)
async def get_checkpoint_for_sequence(
    request: Request,
    sequence: int,
    observer_service: ObserverService = Depends(get_observer_service),
    rate_limiter: ObserverRateLimiter = Depends(get_rate_limiter),
) -> CheckpointAnchor:
    """Get checkpoint containing a specific sequence.

    No authentication required (FR44).

    Returns:
        Checkpoint anchor if found.

    Raises:
        HTTPException: 404 if sequence is in pending interval.
    """
    await rate_limiter.check_rate_limit(request)

    checkpoint = await observer_service.get_checkpoint_for_sequence(sequence)

    if checkpoint is None:
        raise HTTPException(
            status_code=404,
            detail=f"Sequence {sequence} is in pending interval (no checkpoint yet)",
        )

    return checkpoint
```

### Task 6: Add include_merkle_proof parameter to events endpoint

Extend GET /events to support Merkle proof requests.

**Files:**
- `src/api/routes/observer.py` (modify)
- `src/api/models/observer.py` (modify)
- `tests/unit/api/test_observer_routes.py` (modify)

**Test Cases (RED):**
- `test_get_events_include_merkle_proof_returns_merkle`
- `test_get_events_include_merkle_proof_pending_returns_hash_chain`
- `test_get_events_proof_mutual_exclusivity`

**Implementation (GREEN):**
```python
# Modify GET /events to add:
include_merkle_proof: bool = Query(
    default=False,
    description="Include Merkle proof if event is in checkpoint (FR136). Falls back to hash chain for pending events.",
),

# Add to ObserverEventsListResponse:
merkle_proof: Optional[MerkleProof] = Field(
    default=None,
    description="Merkle proof to checkpoint root (FR136)",
)
```

### Task 7: Add verify-merkle command to toolkit

Extend the verification toolkit to verify Merkle proofs.

**Files:**
- `tools/archon72-verify/archon72_verify/verifier.py` (modify)
- `tools/archon72-verify/archon72_verify/cli.py` (modify)
- `tools/archon72-verify/tests/test_verifier.py` (modify)
- `tools/archon72-verify/tests/test_cli.py` (modify)

**Test Cases (RED):**
- `test_verify_merkle_proof_valid`
- `test_verify_merkle_proof_invalid_sibling`
- `test_verify_merkle_proof_invalid_root`
- `test_verify_merkle_cli_command`
- `test_verify_merkle_from_file`

**Implementation (GREEN):**
```python
# In tools/archon72-verify/archon72_verify/verifier.py

@dataclass
class MerkleVerificationResult:
    """Result of Merkle proof verification."""
    is_valid: bool
    event_sequence: int
    checkpoint_sequence: int
    computed_root: str
    expected_root: str
    error_message: Optional[str] = None


class ChainVerifier:
    # ... existing methods ...

    def verify_merkle_proof(self, proof: dict) -> MerkleVerificationResult:
        """Verify a Merkle proof from historical query (FR136, FR137).

        Validates that the event hash combined with sibling hashes
        produces the expected checkpoint Merkle root.

        Args:
            proof: Merkle proof dictionary from API response.

        Returns:
            MerkleVerificationResult with validation status.
        """
        event_hash = proof["event_hash"]
        expected_root = proof["checkpoint_root"]
        path = proof["path"]

        current = event_hash

        for entry in path:
            sibling = entry["sibling_hash"]
            if entry["position"] == "left":
                combined = "".join(sorted([sibling, current]))
            else:
                combined = "".join(sorted([current, sibling]))
            current = hashlib.sha256(combined.encode()).hexdigest()

        return MerkleVerificationResult(
            is_valid=(current == expected_root),
            event_sequence=proof["event_sequence"],
            checkpoint_sequence=proof["checkpoint_sequence"],
            computed_root=current,
            expected_root=expected_root,
            error_message=None if current == expected_root else "Root mismatch",
        )


# In tools/archon72-verify/archon72_verify/cli.py

@app.command()
def verify_merkle(
    file: Path = typer.Argument(
        ...,
        help="Path to JSON file containing Merkle proof from query",
    ),
    output_format: str = typer.Option(
        "text",
        "--format",
        "-o",
        help="Output format: text or json",
    ),
) -> None:
    """Verify Merkle proof from event query (FR136, FR137).

    Validates that the event's content hash combined with
    sibling hashes produces the checkpoint's Merkle root.

    Example:
        archon72-verify verify-merkle response.json
    """
    verifier = ChainVerifier()

    with open(file) as f:
        data = json.load(f)

    # Extract merkle_proof from response
    proof = data.get("merkle_proof")
    if proof is None:
        console.print("[red]ERROR[/red] - No merkle_proof found in response")
        sys.exit(1)

    result = verifier.verify_merkle_proof(proof)

    if output_format == "json":
        console.print_json(json.dumps({
            "is_valid": result.is_valid,
            "event_sequence": result.event_sequence,
            "checkpoint_sequence": result.checkpoint_sequence,
            "computed_root": result.computed_root,
            "expected_root": result.expected_root,
            "error_message": result.error_message,
        }))
    else:
        if result.is_valid:
            console.print(
                f"[green]VALID[/green] - Event {result.event_sequence} "
                f"verified in checkpoint {result.checkpoint_sequence}"
            )
        else:
            console.print(f"[red]INVALID[/red] - {result.error_message}")
            sys.exit(1)
```

### Task 8: Create checkpoint generation worker (stub)

Create a background worker stub for checkpoint generation.

**Files:**
- `src/application/services/checkpoint_service.py` (new)
- `tests/unit/application/test_checkpoint_service.py` (new)

**Test Cases (RED):**
- `test_create_checkpoint_for_week_builds_merkle_tree`
- `test_create_checkpoint_stores_in_repository`
- `test_get_pending_checkpoint_range_returns_correct`
- `test_should_create_checkpoint_returns_true_on_sunday`

**Implementation (GREEN):**
```python
# In src/application/services/checkpoint_service.py

from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from src.api.models.observer import CheckpointAnchor
from src.application.ports.checkpoint_repository import CheckpointRepositoryPort
from src.application.ports.event_store import EventStorePort
from src.application.services.merkle_tree_service import MerkleTreeService


class CheckpointService:
    """Service for creating and managing checkpoints (FR138)."""

    def __init__(
        self,
        event_store: EventStorePort,
        checkpoint_repo: CheckpointRepositoryPort,
        merkle_service: MerkleTreeService,
    ) -> None:
        self._event_store = event_store
        self._checkpoint_repo = checkpoint_repo
        self._merkle_service = merkle_service

    async def create_checkpoint(self) -> Optional[CheckpointAnchor]:
        """Create checkpoint for events since last checkpoint.

        Gets events from (last_checkpoint.sequence_end + 1) to current head,
        builds Merkle tree, and stores checkpoint.

        Returns:
            Created checkpoint, or None if no new events.
        """
        # Get last checkpoint
        last_checkpoint = await self._checkpoint_repo.get_latest_checkpoint()

        if last_checkpoint:
            start_sequence = last_checkpoint.sequence_end + 1
        else:
            start_sequence = 1

        # Get current head
        head_sequence = await self._event_store.get_max_sequence()

        if head_sequence < start_sequence:
            # No new events since last checkpoint
            return None

        # Get events in range
        events = await self._event_store.get_events_range(
            start_sequence=start_sequence,
            end_sequence=head_sequence,
        )

        if not events:
            return None

        # Build Merkle tree
        leaf_hashes = [e.content_hash for e in events]
        merkle_root, _ = self._merkle_service.build_tree(leaf_hashes)

        # Create checkpoint
        checkpoint = await self._checkpoint_repo.create_checkpoint(
            sequence_start=start_sequence,
            sequence_end=head_sequence,
            merkle_root=merkle_root,
        )

        return checkpoint

    def should_create_checkpoint(self) -> bool:
        """Check if it's time to create a checkpoint (FR138).

        Per FR138: Weekly checkpoints on Sunday at 00:00 UTC.

        Returns:
            True if current time is checkpoint time.
        """
        now = datetime.now(timezone.utc)
        # Sunday = 6 in weekday(), hour 0
        return now.weekday() == 6 and now.hour == 0
```

### Task 9: Integration tests for Merkle proofs

End-to-end tests verifying Merkle proof functionality.

**Files:**
- `tests/integration/test_merkle_proof_integration.py` (new)

**Test Cases:**
- `test_create_checkpoint_and_query_merkle_proof`
- `test_merkle_proof_verifiable_with_toolkit`
- `test_checkpoint_endpoint_returns_list`
- `test_pending_event_returns_hash_chain_not_merkle`
- `test_merkle_proof_path_has_log_n_entries`
- `test_verify_merkle_recomputes_root_correctly`

## Technical Notes

### Implementation Order
1. Task 1: Models (foundation)
2. Task 2: Merkle tree service (core algorithm)
3. Task 3: Checkpoint port and stub
4. Task 8: Checkpoint service
5. Task 4: ObserverService Merkle proof generation
6. Task 5: Checkpoint endpoint
7. Task 6: Events endpoint Merkle support
8. Task 7: Toolkit verify-merkle command
9. Task 9: Integration tests

### Testing Strategy
- Unit tests for each component using pytest
- Integration tests verify end-to-end flow
- Toolkit tests verify Merkle verification
- All tests follow red-green-refactor TDD cycle

### Constitutional Compliance Matrix
| Requirement | Implementation |
|-------------|----------------|
| FR136 | MerkleProof in response when include_merkle_proof=true |
| FR137 | verify_merkle_proof allows offline verification |
| FR138 | CheckpointService creates weekly checkpoints |
| FR44 | No auth required for checkpoint endpoints |
| CT-7 | Checkpoints provide anchoring for verification |

### Key Design Decisions
1. **Checkpoint-based Merkle trees**: Each checkpoint has its own Merkle tree over contained events
2. **Padding for non-power-of-2**: Duplicate last leaf to pad to power of 2
3. **Sorted hash pairs**: Use sorted concatenation for deterministic parent hashes
4. **Fallback to hash chain**: Events in pending interval (after last checkpoint) use hash chain proof
5. **Weekly schedule**: Checkpoints created Sunday 00:00 UTC per FR138
6. **Anchor types**: Support genesis (Bitcoin), rfc3161 (TSA), and pending

### Performance Considerations
- **Proof size**: O(log n) sibling hashes vs O(n) for full chain
- **Tree build**: O(n) to build, O(log n) to generate proof
- **Query SLA**: Per ADR-9, < 5 seconds for 1 year span
- **Checkpoint size**: Weekly = ~604,800 seconds, depends on event rate

### Previous Story Intelligence (Story 4.5)
From Story 4.5 completion:
- HashChainProof model exists with chain of entries
- include_proof parameter already on GET /events
- ObserverService._generate_hash_chain_proof exists
- verify-proof command in toolkit uses ChainVerifier class
- ProofVerificationResult dataclass pattern established

Files that will be extended:
- `src/api/models/observer.py` - Add MerkleProof, MerkleProofEntry, CheckpointAnchor
- `src/api/routes/observer.py` - Add checkpoints endpoint, include_merkle_proof param
- `src/application/services/observer_service.py` - Add _generate_merkle_proof
- `tools/archon72-verify/archon72_verify/verifier.py` - Add verify_merkle_proof
- `tools/archon72-verify/archon72_verify/cli.py` - Add verify-merkle command

### Patterns to Follow
- Use Pydantic models for all API request/response types
- Async/await for all I/O operations
- Type hints on all functions
- FastAPI Query parameters for API options
- Structlog for any logging (no print, no f-strings in logs)
- Domain exceptions for error cases
- Protocol classes for ports (dependency inversion)

## Dev Notes

### Project Structure Notes
- API routes: `src/api/routes/observer.py`
- Models: `src/api/models/observer.py`
- Service: `src/application/services/observer_service.py`
- New service: `src/application/services/merkle_tree_service.py`
- New service: `src/application/services/checkpoint_service.py`
- Port: `src/application/ports/checkpoint_repository.py`
- Stub: `src/infrastructure/stubs/checkpoint_repository_stub.py`
- Toolkit: `tools/archon72-verify/`

### References
- [Source: _bmad-output/planning-artifacts/epics.md#Story-4.6]
- [Source: _bmad-output/planning-artifacts/architecture.md#ADR-8]
- [Source: _bmad-output/planning-artifacts/architecture.md#ADR-9]
- [Source: src/api/routes/observer.py - Existing observer endpoints]
- [Source: src/api/models/observer.py - Existing observer models including HashChainProof]
- [Source: src/application/services/observer_service.py - Existing service with _generate_hash_chain_proof]
- [Source: tools/archon72-verify/ - Verification toolkit with verify-proof]
- [Source: _bmad-output/implementation-artifacts/stories/4-5-historical-queries-query-as-of.md - Previous story]
- [Source: _bmad-output/project-context.md - Project patterns and constraints]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

N/A - All tests passing

### Completion Notes List

**Session 1 (Tasks 1-3):**
- Created `Checkpoint` and `MerkleProof` API models in `src/api/models/observer.py`
- Implemented `MerkleTreeService` in `src/application/services/merkle_tree_service.py`
- Updated `CheckpointRepositoryPort` with Merkle-specific methods
- Created/updated `CheckpointRepositoryStub` implementation
- Added 61 unit tests covering all new components

**Session 2 (Tasks 4-9):**
- Task 4: Added Merkle proof generation to `ObserverService` with fallback to hash chain for pending intervals
- Task 5: Added `/checkpoints` and `/checkpoints/{sequence}` endpoints to Observer API
- Task 6: Added `include_merkle_proof` query parameter to `/events` endpoint
- Task 7: Added `verify-merkle` command to toolkit CLI with `MerkleVerificationResult`
- Task 8: Created `CheckpointWorkerStub` for periodic checkpoint generation
- Task 9: Created integration tests in `test_merkle_proof_integration.py`

**All Acceptance Criteria Met:**
- AC1: Merkle proof included with `include_merkle_proof=true` ✓
- AC2: O(log n) proof verification without full chain download ✓
- AC3: Weekly checkpoint anchors via `/checkpoints` endpoint ✓
- AC4: Checkpoint Merkle root verification implemented ✓
- AC5: `archon72-verify verify-merkle` command available ✓

**Test Results:**
- 103 tests passing for Story 4-6 components
- 8 integration tests covering end-to-end Merkle proof flow
- FR136, FR137, FR138 constitutional constraints verified

### File List

**Created:**
- `src/application/services/merkle_tree_service.py` - Merkle tree builder service
- `src/infrastructure/stubs/checkpoint_worker_stub.py` - Checkpoint generation worker stub
- `tests/unit/application/test_merkle_tree_service.py` - MerkleTreeService unit tests
- `tests/unit/infrastructure/test_checkpoint_worker_stub.py` - Worker stub tests (10 tests)
- `tests/integration/test_merkle_proof_integration.py` - Integration tests (8 tests)

**Modified:**
- `src/api/models/observer.py` - Added MerkleProof, MerkleProofEntry, Checkpoint models
- `src/api/routes/observer.py` - Added checkpoint endpoints, include_merkle_proof parameter
- `src/application/services/observer_service.py` - Added Merkle proof generation methods
- `src/application/ports/checkpoint_repository.py` - Extended port interface
- `src/infrastructure/stubs/checkpoint_repository_stub.py` - Extended stub
- `tools/archon72-verify/archon72_verify/verifier.py` - Added MerkleVerificationResult, verify_merkle method
- `tools/archon72-verify/archon72_verify/cli.py` - Added verify-merkle command
- `tools/archon72-verify/archon72_verify/client.py` - Added get_merkle_proof, list_checkpoints methods
- `tests/unit/application/test_observer_service.py` - Added 8 Merkle proof tests
- `tests/unit/api/test_observer_routes.py` - Updated for new endpoints
