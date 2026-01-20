# Story 2B.5: Transcript Preservation & Hash-Referencing

## Story Information

| Field | Value |
|-------|-------|
| **Story ID** | petition-2b-5 |
| **Epic** | Epic 2B: Deliberation Edge Cases & Guarantees |
| **Priority** | P0 |
| **Status** | ready-for-dev |
| **Created** | 2026-01-19 |

## User Story

**As a** system,
**I want** all deliberation transcripts preserved with hash references in a persistent content-addressed store,
**So that** the complete deliberation record can be verified for integrity and reconstructed for audit.

## Requirements Coverage

### Functional Requirements

| FR ID | Requirement | Priority |
|-------|-------------|----------|
| FR-11.7 | System SHALL preserve ALL deliberation utterances (hash-referenced) with ledger witnessing at phase boundaries per CT-12 | P0 |
| FR-11.12 | System SHALL preserve complete deliberation transcript for audit reconstruction | P0 |

### Non-Functional Requirements

| NFR ID | Requirement | Target |
|--------|-------------|--------|
| NFR-10.4 | Witness completeness | 100% utterances witnessed |
| NFR-6.5 | State history reconstruction | Full replay from event log |
| NFR-4.2 | Event log durability | Append-only, no deletion |

### Constitutional Truths

- **CT-12**: "Every action that affects an Archon must be witnessed by another Archon, creating an unbroken chain of accountability."
- **CT-14**: "Silence must be expensive. Every claim on attention terminates in a visible, witnessed fate."

### Grand Architect Rulings

- **Ruling-1**: Phase-level witness batching - witness at phase boundaries, not per-utterance
- **Ruling-2**: Tiered transcript access - internal full access, observers get summaries

## Acceptance Criteria

### AC-1: Persistent Content-Addressed Storage Protocol

**Given** the need for persistent transcript storage beyond in-memory
**When** a transcript is stored
**Then** it uses a `TranscriptStoreProtocol` with methods:
- `store_transcript(content: str) -> TranscriptReference`
- `retrieve_transcript(hash: bytes) -> str | None`
- `verify_integrity(hash: bytes) -> bool`
- `exists(hash: bytes) -> bool`
**And** the protocol supports both PostgreSQL and stub implementations
**And** transcripts are immutable once stored (append-only)

### AC-2: TranscriptReference Value Object

**Given** a transcript is stored
**When** storage completes
**Then** a `TranscriptReference` value object is returned containing:
- `content_hash`: bytes (32-byte Blake3 hash)
- `content_size`: int (bytes)
- `stored_at`: datetime (UTC)
- `storage_path`: str | None (for filesystem-backed stores)
**And** the hash can be used to retrieve the original content
**And** the value object is frozen (immutable)

### AC-3: Database Migration for Transcript Storage

**Given** persistent transcript storage is needed
**When** the migration is applied
**Then** a `deliberation_transcripts` table is created with:
- `content_hash` BYTEA PRIMARY KEY (32 bytes, Blake3)
- `content` TEXT NOT NULL (the full transcript)
- `content_size` INTEGER NOT NULL
- `stored_at` TIMESTAMPTZ NOT NULL DEFAULT NOW()
- CHECK constraint: `content_hash = blake3(content)` (integrity)
**And** the table is append-only (no UPDATE/DELETE policies)
**And** indexes exist for efficient lookup by hash

### AC-4: Integration with PhaseWitnessBatchingService

**Given** the existing `PhaseWitnessBatchingService` uses in-memory storage
**When** the service is upgraded to use persistent storage
**Then** `_transcripts: dict[bytes, str]` is replaced with `TranscriptStoreProtocol`
**And** `witness_phase()` calls `store_transcript()` instead of dict assignment
**And** `get_transcript_by_hash()` delegates to `retrieve_transcript()`
**And** all existing unit tests continue to pass (with stub implementation)

### AC-5: Transcript Integrity Verification

**Given** a stored transcript
**When** `verify_integrity(hash)` is called
**Then** the content is retrieved and re-hashed
**And** the computed hash is compared to the stored hash
**And** True is returned if hashes match, False otherwise
**And** verification runs in < 10ms for typical transcripts (< 100KB)

### AC-6: Transcript Retrieval by Session

**Given** a deliberation session with phase witness events
**When** I query for all transcripts by session_id
**Then** all 4 phase transcripts are retrieved (ASSESS, POSITION, CROSS_EXAMINE, VOTE)
**And** each transcript is keyed by its phase
**And** retrieval uses the hashes from PhaseWitnessEvents
**And** missing transcripts are indicated (not silently skipped)

### AC-7: Stub Implementation for Testing

**Given** the need for fast unit tests
**When** tests run
**Then** `TranscriptStoreStub` provides in-memory implementation
**And** the stub implements full `TranscriptStoreProtocol`
**And** the stub tracks call history for verification
**And** the stub supports pre-loading test data

### AC-8: PostgreSQL Adapter Implementation

**Given** production deployment requirements
**When** the PostgreSQL adapter is used
**Then** `PostgresTranscriptStore` implements `TranscriptStoreProtocol`
**And** storage uses INSERT with ON CONFLICT DO NOTHING (idempotent)
**And** retrieval uses direct SELECT by primary key hash
**And** connection pooling is used efficiently

### AC-9: Unit Tests

**Given** the TranscriptStoreProtocol and implementations
**Then** unit tests verify:
- TranscriptReference creation with valid hash
- TranscriptReference immutability
- Blake3 hash computation matches expected
- Store/retrieve round-trip integrity
- Verify integrity returns True for valid content
- Verify integrity returns False for tampered content
- Exists returns True for stored, False for missing
- Stub tracks store/retrieve calls

### AC-10: Integration Tests

**Given** the PostgreSQL adapter
**Then** integration tests verify:
- Migration applies cleanly
- Transcript insertion persists
- Transcript retrieval by hash works
- Duplicate insertion is idempotent (no error)
- Integrity verification uses database content
- Large transcripts (> 64KB) work correctly
- Concurrent inserts don't conflict

## Technical Design

### Domain Model

```python
# src/domain/models/transcript_reference.py

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID


def _utc_now() -> datetime:
    """Return current UTC time with timezone info."""
    return datetime.now(timezone.utc)


@dataclass(frozen=True, eq=True)
class TranscriptReference:
    """Reference to a content-addressed transcript (Story 2B.5, FR-11.7).

    Provides a compact reference to a transcript stored in the content-
    addressed store. The hash can be used to retrieve and verify the
    original content.

    Constitutional Constraints:
    - CT-12: Enables witness verification
    - NFR-6.5: Supports audit trail reconstruction
    - NFR-4.2: Hash guarantees immutability

    Attributes:
        content_hash: 32-byte Blake3 hash of transcript content.
        content_size: Size of content in bytes.
        stored_at: When the transcript was stored (UTC).
        storage_path: Optional path for filesystem-backed stores.
    """

    content_hash: bytes
    content_size: int
    stored_at: datetime = field(default_factory=_utc_now)
    storage_path: str | None = field(default=None)

    def __post_init__(self) -> None:
        """Validate transcript reference invariants."""
        if len(self.content_hash) != 32:
            raise ValueError(
                f"content_hash must be 32 bytes (Blake3), got {len(self.content_hash)}"
            )
        if self.content_size < 0:
            raise ValueError(f"content_size must be >= 0, got {self.content_size}")

    @property
    def content_hash_hex(self) -> str:
        """Return content hash as hex string."""
        return self.content_hash.hex()

    def to_dict(self) -> dict:
        """Serialize for storage/transmission."""
        return {
            "content_hash": self.content_hash_hex,
            "content_size": self.content_size,
            "stored_at": self.stored_at.isoformat(),
            "storage_path": self.storage_path,
        }
```

### Protocol Definition

```python
# src/application/ports/transcript_store.py

from typing import Protocol
from uuid import UUID

from src.domain.models.transcript_reference import TranscriptReference


class TranscriptStoreProtocol(Protocol):
    """Protocol for content-addressed transcript storage (Story 2B.5, FR-11.7).

    Implementations store deliberation transcripts in a content-addressed
    manner, using Blake3 hashes as keys. This ensures immutability and
    enables integrity verification.

    Constitutional Constraints:
    - CT-12: Supports witness verification
    - FR-11.7: Hash-referenced storage
    - NFR-6.5: Audit trail reconstruction
    - NFR-4.2: Append-only durability
    """

    async def store_transcript(self, content: str) -> TranscriptReference:
        """Store transcript and return its reference.

        If transcript with same content already exists, returns existing
        reference (idempotent operation).

        Args:
            content: Full transcript text.

        Returns:
            TranscriptReference with Blake3 hash.
        """
        ...

    async def retrieve_transcript(self, content_hash: bytes) -> str | None:
        """Retrieve transcript by content hash.

        Args:
            content_hash: 32-byte Blake3 hash.

        Returns:
            Transcript content if found, None otherwise.
        """
        ...

    async def verify_integrity(self, content_hash: bytes) -> bool:
        """Verify stored content matches its hash.

        Re-computes hash of stored content and compares.

        Args:
            content_hash: Expected 32-byte Blake3 hash.

        Returns:
            True if content verifies, False if tampered or missing.
        """
        ...

    async def exists(self, content_hash: bytes) -> bool:
        """Check if transcript exists by hash.

        Args:
            content_hash: 32-byte Blake3 hash.

        Returns:
            True if exists, False otherwise.
        """
        ...

    async def get_transcripts_for_session(
        self,
        witness_events: list,  # list[PhaseWitnessEvent]
    ) -> dict[str, str | None]:
        """Retrieve all transcripts for a session's witness events.

        Args:
            witness_events: List of PhaseWitnessEvents containing transcript hashes.

        Returns:
            Dict mapping phase name to transcript content (None if missing).
        """
        ...
```

### Database Migration

```sql
-- migrations/019_create_deliberation_transcripts.sql

-- Content-addressed transcript storage (Story 2B.5, FR-11.7)
-- Stores deliberation phase transcripts with Blake3 hash as primary key.
-- This table is APPEND-ONLY - no updates or deletes permitted.

CREATE TABLE deliberation_transcripts (
    -- Primary key is the Blake3 hash of content (32 bytes)
    content_hash BYTEA PRIMARY KEY,

    -- Full transcript content
    content TEXT NOT NULL,

    -- Content size in bytes (for quick lookup without loading content)
    content_size INTEGER NOT NULL GENERATED ALWAYS AS (length(content)) STORED,

    -- When transcript was stored
    stored_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Constraints
    CONSTRAINT check_content_hash_length CHECK (
        length(content_hash) = 32
    ),
    CONSTRAINT check_content_not_empty CHECK (
        length(content) > 0
    )
);

-- No additional indexes needed - primary key on content_hash is sufficient
-- for all query patterns (direct lookup by hash)

-- Comment for documentation
COMMENT ON TABLE deliberation_transcripts IS
    'Content-addressed storage for deliberation phase transcripts (Story 2B.5, FR-11.7). Append-only.';

COMMENT ON COLUMN deliberation_transcripts.content_hash IS
    'Blake3 hash of content (32 bytes). Primary key for content-addressed retrieval.';

-- RLS policy: Read-only access for authenticated users
-- (Transcripts are created by system, not users)
ALTER TABLE deliberation_transcripts ENABLE ROW LEVEL SECURITY;

-- System can insert (via service role)
CREATE POLICY "System can insert transcripts"
ON deliberation_transcripts FOR INSERT
TO service_role
WITH CHECK (true);

-- Authenticated users can read
CREATE POLICY "Authenticated users can read transcripts"
ON deliberation_transcripts FOR SELECT
TO authenticated
USING (true);

-- No UPDATE or DELETE policies - table is append-only
```

### Stub Implementation

```python
# src/infrastructure/stubs/transcript_store_stub.py

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import blake3

from src.domain.events.phase_witness import PhaseWitnessEvent
from src.domain.models.transcript_reference import TranscriptReference


class TranscriptStoreStub:
    """Stub implementation of TranscriptStoreProtocol for testing (Story 2B.5).

    Stores transcripts in memory for fast unit tests.

    Attributes:
        _transcripts: In-memory storage mapping hash -> content.
        _store_calls: History of store_transcript calls for verification.
        _retrieve_calls: History of retrieve_transcript calls.
    """

    def __init__(self) -> None:
        """Initialize empty in-memory store."""
        self._transcripts: dict[bytes, str] = {}
        self._store_calls: list[dict[str, Any]] = []
        self._retrieve_calls: list[dict[str, Any]] = []

    def _compute_hash(self, content: str) -> bytes:
        """Compute Blake3 hash of content."""
        return blake3.blake3(content.encode("utf-8")).digest()

    async def store_transcript(self, content: str) -> TranscriptReference:
        """Store transcript in memory."""
        content_hash = self._compute_hash(content)
        content_size = len(content.encode("utf-8"))

        # Track call
        self._store_calls.append({
            "content_hash": content_hash,
            "content_size": content_size,
            "already_existed": content_hash in self._transcripts,
        })

        # Store (idempotent)
        if content_hash not in self._transcripts:
            self._transcripts[content_hash] = content

        return TranscriptReference(
            content_hash=content_hash,
            content_size=content_size,
            stored_at=datetime.now(timezone.utc),
        )

    async def retrieve_transcript(self, content_hash: bytes) -> str | None:
        """Retrieve transcript by hash."""
        self._retrieve_calls.append({"content_hash": content_hash})
        return self._transcripts.get(content_hash)

    async def verify_integrity(self, content_hash: bytes) -> bool:
        """Verify stored content matches hash."""
        content = self._transcripts.get(content_hash)
        if content is None:
            return False

        recomputed = self._compute_hash(content)
        return recomputed == content_hash

    async def exists(self, content_hash: bytes) -> bool:
        """Check if transcript exists."""
        return content_hash in self._transcripts

    async def get_transcripts_for_session(
        self,
        witness_events: list[PhaseWitnessEvent],
    ) -> dict[str, str | None]:
        """Retrieve all transcripts for session's witness events."""
        result: dict[str, str | None] = {}

        for event in witness_events:
            phase_name = event.phase.value
            content = await self.retrieve_transcript(event.transcript_hash)
            result[phase_name] = content

        return result

    # Test helpers

    def preload_transcript(self, content: str) -> bytes:
        """Preload a transcript for testing. Returns hash."""
        content_hash = self._compute_hash(content)
        self._transcripts[content_hash] = content
        return content_hash

    def get_store_call_count(self) -> int:
        """Get number of store calls."""
        return len(self._store_calls)

    def get_retrieve_call_count(self) -> int:
        """Get number of retrieve calls."""
        return len(self._retrieve_calls)

    def clear(self) -> None:
        """Clear all stored transcripts and call history."""
        self._transcripts.clear()
        self._store_calls.clear()
        self._retrieve_calls.clear()
```

## Dependencies

### Upstream Dependencies (Required Before This Story)

| Story ID | Name | Status | Why Needed |
|----------|------|--------|------------|
| petition-2a-7 | Phase-Level Witness Batching | DONE | Defines PhaseWitnessEvent structure, existing service |
| petition-0-5 | Content Hashing Service (Blake3) | DONE | Blake3 library and patterns |

### Downstream Dependencies (Blocked By This Story)

| Story ID | Name | Why Blocked |
|----------|------|-------------|
| petition-2b-6 | Audit Trail Reconstruction | Needs persistent transcript storage for reconstruction |
| petition-7-4 | Transcript Access Mediation Service | Needs TranscriptStoreProtocol for access control |

## Implementation Tasks

### Task 1: Create TranscriptReference Domain Model (AC: 2)
- [ ] Create `src/domain/models/transcript_reference.py`
- [ ] Define frozen `TranscriptReference` dataclass
- [ ] Implement `__post_init__` validation (32-byte hash, non-negative size)
- [ ] Add `content_hash_hex` property
- [ ] Add `to_dict()` method
- [ ] Export from `src/domain/models/__init__.py`

### Task 2: Create TranscriptStoreProtocol (AC: 1)
- [ ] Create `src/application/ports/transcript_store.py`
- [ ] Define `TranscriptStoreProtocol` with all methods
- [ ] Add comprehensive docstrings with constitutional constraints
- [ ] Export from `src/application/ports/__init__.py`

### Task 3: Create TranscriptStoreStub (AC: 7)
- [ ] Create `src/infrastructure/stubs/transcript_store_stub.py`
- [ ] Implement all protocol methods with in-memory storage
- [ ] Add call tracking for test verification
- [ ] Add `preload_transcript()` helper
- [ ] Add `clear()` method
- [ ] Export from `src/infrastructure/stubs/__init__.py`

### Task 4: Create Database Migration (AC: 3)
- [ ] Create `migrations/019_create_deliberation_transcripts.sql`
- [ ] Define table with content_hash primary key
- [ ] Add CHECK constraints for hash length and content
- [ ] Configure RLS policies (append-only)
- [ ] Add table/column comments

### Task 5: Create PostgreSQL Adapter (AC: 8)
- [ ] Create `src/infrastructure/adapters/persistence/transcript_store.py`
- [ ] Implement `PostgresTranscriptStore` class
- [ ] Use INSERT ON CONFLICT DO NOTHING for idempotency
- [ ] Handle connection pooling properly
- [ ] Add error handling for database errors

### Task 6: Upgrade PhaseWitnessBatchingService (AC: 4)
- [ ] Add `TranscriptStoreProtocol` dependency to constructor
- [ ] Replace `_transcripts` dict with protocol calls
- [ ] Update `witness_phase()` to use `store_transcript()`
- [ ] Update `get_transcript_by_hash()` to use `retrieve_transcript()`
- [ ] Ensure backward compatibility with existing tests

### Task 7: Write Unit Tests (AC: 9)
- [ ] Create `tests/unit/domain/models/test_transcript_reference.py`
- [ ] Create `tests/unit/infrastructure/stubs/test_transcript_store_stub.py`
- [ ] Create `tests/unit/application/services/test_phase_witness_with_persistence.py`
- [ ] Test TranscriptReference creation and validation
- [ ] Test stub store/retrieve/verify round-trip
- [ ] Test call tracking
- [ ] Test hash computation consistency

### Task 8: Write Integration Tests (AC: 10)
- [ ] Create `tests/integration/test_deliberation_transcripts_schema.py`
- [ ] Test migration applies cleanly
- [ ] Test INSERT and SELECT operations
- [ ] Test idempotent insert behavior
- [ ] Test integrity verification with database
- [ ] Test large transcript handling (> 64KB)
- [ ] Test concurrent insert behavior

## Definition of Done

- [ ] `TranscriptReference` domain model implemented with invariants
- [ ] `TranscriptStoreProtocol` defined with full interface
- [ ] `TranscriptStoreStub` provides test implementation
- [ ] Migration 019 created and tested
- [ ] `PostgresTranscriptStore` implements persistent storage
- [ ] `PhaseWitnessBatchingService` upgraded to use protocol
- [ ] Unit tests pass (>90% coverage for new code)
- [ ] Integration tests verify database operations
- [ ] All existing Phase Witness tests continue to pass
- [ ] FR-11.7 satisfied: All transcripts hash-referenced
- [ ] FR-11.12 satisfied: Complete transcripts preserved for audit

## Test Scenarios

### Scenario 1: Store and Retrieve Transcript

```python
# Setup
store = TranscriptStoreStub()
transcript = """
[ASSESS Phase]
Archon-1: The petition requests...
Archon-2: I observe that...
Archon-3: My initial assessment...
"""

# Store
ref = await store.store_transcript(transcript)

assert ref.content_hash is not None
assert len(ref.content_hash) == 32
assert ref.content_size == len(transcript.encode("utf-8"))

# Retrieve
retrieved = await store.retrieve_transcript(ref.content_hash)

assert retrieved == transcript
```

### Scenario 2: Verify Integrity

```python
import blake3

# Store transcript
transcript = "Phase content..."
ref = await store.store_transcript(transcript)

# Verify integrity
is_valid = await store.verify_integrity(ref.content_hash)
assert is_valid is True

# Verify hash computation
expected_hash = blake3.blake3(transcript.encode("utf-8")).digest()
assert ref.content_hash == expected_hash
```

### Scenario 3: Idempotent Storage

```python
# Store same content twice
transcript = "Identical content"
ref1 = await store.store_transcript(transcript)
ref2 = await store.store_transcript(transcript)

# Same hash returned
assert ref1.content_hash == ref2.content_hash

# Only one entry in store
assert store.get_store_call_count() == 2  # Called twice
# But second call was idempotent (already_existed=True)
```

### Scenario 4: Get Transcripts for Session

```python
from src.domain.events.phase_witness import PhaseWitnessEvent
from src.domain.models.deliberation_session import DeliberationPhase

# Setup witness events with hashes
witness_events = [
    PhaseWitnessEvent(..., phase=DeliberationPhase.ASSESS, transcript_hash=hash1),
    PhaseWitnessEvent(..., phase=DeliberationPhase.POSITION, transcript_hash=hash2),
    PhaseWitnessEvent(..., phase=DeliberationPhase.CROSS_EXAMINE, transcript_hash=hash3),
    PhaseWitnessEvent(..., phase=DeliberationPhase.VOTE, transcript_hash=hash4),
]

# Preload transcripts
for event in witness_events:
    store.preload_transcript(f"Content for {event.phase.value}")

# Get all transcripts
transcripts = await store.get_transcripts_for_session(witness_events)

assert len(transcripts) == 4
assert "ASSESS" in transcripts
assert "POSITION" in transcripts
assert "CROSS_EXAMINE" in transcripts
assert "VOTE" in transcripts
assert all(t is not None for t in transcripts.values())
```

## Dev Notes

### Relevant Architecture Patterns

1. **Content-Addressed Storage**:
   - Hash = key, content = value
   - Immutability guaranteed by hash
   - Deduplication automatic (same content = same hash)
   - Pattern used in Git, IPFS, CAS systems

2. **Protocol + Stub + Adapter Pattern**:
   - Protocol in `src/application/ports/`
   - Stub in `src/infrastructure/stubs/`
   - Adapter in `src/infrastructure/adapters/persistence/`
   - Allows dependency injection for testing

3. **Existing Blake3 Pattern**:
   - `blake3.blake3(content.encode("utf-8")).digest()` → 32 bytes
   - Hex encoding: `.hex()` for display
   - Compare bytes directly for verification

### Key Files to Reference

| File | Why |
|------|-----|
| `src/application/services/phase_witness_batching_service.py` | Service to upgrade |
| `src/domain/events/phase_witness.py` | PhaseWitnessEvent structure |
| `src/application/ports/phase_witness_batching.py` | Protocol pattern reference |
| `src/infrastructure/stubs/phase_witness_batching_stub.py` | Stub pattern reference |

### Integration Points

1. **PhaseWitnessBatchingService Upgrade**:
   - Constructor gains `transcript_store: TranscriptStoreProtocol` parameter
   - Default to stub in tests, inject PostgreSQL adapter in production
   - Backward compatible: existing tests pass unchanged

2. **Audit Trail Service** (Story 2B.6):
   - Will use `get_transcripts_for_session()` to reconstruct deliberations
   - Relies on all 4 phase transcripts being available

### Project Structure Notes

- **Location**: Follow existing patterns:
  - Model: `src/domain/models/transcript_reference.py`
  - Protocol: `src/application/ports/transcript_store.py`
  - Stub: `src/infrastructure/stubs/transcript_store_stub.py`
  - Adapter: `src/infrastructure/adapters/persistence/transcript_store.py`
  - Migration: `migrations/019_create_deliberation_transcripts.sql`

### Performance Considerations

- **Storage**: Typical phase transcript ~10-50KB, max ~100KB
- **Retrieval**: Direct hash lookup = O(1) with B-tree index
- **Integrity Check**: Blake3 is fast (~1GB/s), verification < 10ms
- **Connection Pooling**: Use async pool, don't hold connections

### References

- [Source: `_bmad-output/planning-artifacts/petition-system-prd.md#FR-11.7`] - Hash-referenced preservation
- [Source: `_bmad-output/planning-artifacts/petition-system-prd.md#FR-11.12`] - Complete transcript preservation
- [Source: `_bmad-output/planning-artifacts/petition-system-prd.md#Ruling-1`] - Phase-level witness batching
- [Source: `src/application/services/phase_witness_batching_service.py`] - Existing in-memory implementation

## Documentation Checklist

- [ ] Architecture docs updated (if patterns/structure changed)
- [ ] API docs updated (if endpoints/contracts changed)
- [ ] README updated (if setup/usage changed)
- [ ] Inline comments added for complex logic
- [x] N/A - Internal service, no external API impact

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List
