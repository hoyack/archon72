# Story 2A.7: Phase-Level Witness Batching

## Story Information

| Field | Value |
|-------|-------|
| **Story ID** | petition-2a-7 |
| **Epic** | Epic 2A: Core Deliberation Protocol |
| **Priority** | P0-CRITICAL |
| **Status** | done |
| **Created** | 2026-01-19 |

## User Story

**As a** system,
**I want** to witness deliberation at phase boundaries (not per-utterance),
**So that** auditability is maintained without witness volume explosion.

## Requirements Coverage

### Functional Requirements

| FR ID | Requirement | Priority |
|-------|-------------|----------|
| FR-11.7 | System SHALL preserve ALL deliberation utterances (hash-referenced) with ledger witnessing at phase boundaries per CT-12 | P0 |

### Non-Functional Requirements

| NFR ID | Requirement | Target |
|--------|-------------|--------|
| NFR-10.4 | Witness completeness | 100% utterances witnessed |

### Constitutional Truths

- **CT-12**: "Every action that affects an Archon must be witnessed by another Archon, creating an unbroken chain of accountability."
- **CT-14**: "Silence must be expensive. Every claim on attention terminates in a visible, witnessed fate."

### Grand Architect Rulings

- **Ruling-1**: Phase-level witness batching - witness at phase boundaries, not per-utterance

## Acceptance Criteria

### AC-1: Phase Witness Event Structure

**Given** a deliberation phase completes
**When** the phase is witnessed
**Then** a single witness event is emitted containing:
  - `session_id`: UUID of the deliberation session
  - `phase`: The phase that completed (ASSESS, POSITION, CROSS_EXAMINE, VOTE)
  - `transcript_hash`: Blake3 hash of full phase transcript (32 bytes)
  - `participating_archons`: Array of 3 archon_ids
  - `start_timestamp`: When phase started (UTC)
  - `end_timestamp`: When phase completed (UTC)
  - `phase_metadata`: Dict with phase-specific data (e.g., "positions_converged", "challenges_raised")
**And** the raw transcript is stored as content-addressed artifact
**And** the artifact is referenced by hash in the witness event

### AC-2: Witness Batching Service Protocol

**Given** the need for testability
**When** the PhaseWitnessBatchingService is created
**Then** it defines a `PhaseWitnessBatchingProtocol` with:
  - `witness_phase(session: DeliberationSession, phase: DeliberationPhase, transcript: str, metadata: dict) -> PhaseWitnessEvent`
  - `get_phase_witness(session_id: UUID, phase: DeliberationPhase) -> PhaseWitnessEvent | None`
  - `get_all_witnesses(session_id: UUID) -> list[PhaseWitnessEvent]`
**And** a stub implementation is provided for testing

### AC-3: Four Witness Events Per Deliberation

**Given** a complete deliberation session
**When** the session completes normally
**Then** exactly 4 witness events are emitted:
  - 1 for ASSESS phase
  - 1 for POSITION phase
  - 1 for CROSS_EXAMINE phase
  - 1 for VOTE phase
**And** each event is chronologically ordered
**And** each event references the previous phase's witness hash (chain)

### AC-4: Content-Addressed Artifact Storage

**Given** a phase transcript needs witnessing
**When** `witness_phase()` is called
**Then** the raw transcript text is hashed using Blake3
**And** the hash is stored in `phase_transcripts` on the session
**And** the full transcript is stored as a content-addressed artifact
**And** the artifact can be retrieved by hash for audit

### AC-5: Integration with Orchestrator

**Given** the orchestrator completes a phase
**When** the phase result is recorded
**Then** the orchestrator calls `witness_phase()` with:
  - The current session state
  - The completed phase
  - The full phase transcript text
  - Phase-specific metadata from the result
**And** the session is updated with the transcript hash

### AC-6: Unit Tests

**Given** the PhaseWitnessBatchingService
**Then** unit tests verify:
  - PhaseWitnessEvent creation with all required fields
  - Transcript hash calculation (Blake3, 32 bytes)
  - Phase metadata validation
  - Chronological ordering
  - Hash chaining between phases
  - Error handling for invalid inputs

### AC-7: Integration Tests

**Given** the PhaseWitnessBatchingService
**Then** integration tests verify:
  - Full deliberation produces 4 witness events
  - Content-addressed artifact retrieval
  - Audit trail reconstruction
  - Integration with DeliberationSession.with_transcript()

## Technical Design

### Domain Models

```python
# src/domain/events/phase_witness_event.py

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from src.domain.models.deliberation_session import DeliberationPhase


@dataclass(frozen=True, eq=True)
class PhaseWitnessEvent:
    """Witness event for a deliberation phase (Story 2A.7, FR-11.7).

    Emitted at phase boundaries to witness all utterances without
    per-utterance event explosion. The transcript is stored as a
    content-addressed artifact referenced by hash.

    Constitutional Constraints:
    - CT-12: Every action must be witnessed
    - CT-14: Every claim terminates in witnessed fate
    - FR-11.7: Hash-referenced ledger witnessing at phase boundaries
    - NFR-10.4: 100% witness completeness

    Attributes:
        event_id: UUIDv7 for this witness event.
        session_id: UUID of the deliberation session.
        phase: The phase being witnessed.
        transcript_hash: Blake3 hash of full transcript (32 bytes).
        participating_archons: Tuple of 3 archon UUIDs.
        start_timestamp: When phase started (UTC).
        end_timestamp: When phase completed (UTC).
        phase_metadata: Phase-specific metadata dict.
        previous_witness_hash: Hash of previous phase's witness (None for ASSESS).
        created_at: Event creation timestamp (UTC).
    """

    event_id: UUID
    session_id: UUID
    phase: DeliberationPhase
    transcript_hash: bytes
    participating_archons: tuple[UUID, UUID, UUID]
    start_timestamp: datetime
    end_timestamp: datetime
    phase_metadata: dict[str, Any] = field(default_factory=dict)
    previous_witness_hash: bytes | None = field(default=None)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        """Validate witness event invariants."""
        # Transcript hash must be 32 bytes (Blake3)
        if len(self.transcript_hash) != 32:
            raise ValueError("transcript_hash must be 32 bytes (Blake3)")

        # Must have exactly 3 archons
        if len(self.participating_archons) != 3:
            raise ValueError("participating_archons must contain exactly 3 UUIDs")

        # End must be after start
        if self.end_timestamp < self.start_timestamp:
            raise ValueError("end_timestamp must be >= start_timestamp")

        # ASSESS should not have previous hash; others should
        if self.phase == DeliberationPhase.ASSESS:
            if self.previous_witness_hash is not None:
                raise ValueError("ASSESS phase should not have previous_witness_hash")
        else:
            if self.previous_witness_hash is None:
                raise ValueError(f"{self.phase.value} phase must have previous_witness_hash")
            if len(self.previous_witness_hash) != 32:
                raise ValueError("previous_witness_hash must be 32 bytes (Blake3)")

    @property
    def transcript_hash_hex(self) -> str:
        """Return transcript hash as hex string."""
        return self.transcript_hash.hex()

    @property
    def event_hash(self) -> bytes:
        """Compute hash of this witness event for chaining.

        Used as previous_witness_hash for the next phase's event.
        """
        import blake3

        content = f"{self.event_id}:{self.session_id}:{self.phase.value}:{self.transcript_hash.hex()}:{self.end_timestamp.isoformat()}"
        return blake3.blake3(content.encode()).digest()
```

### Service Protocol

```python
# src/application/ports/phase_witness_batching.py

from typing import Any, Protocol
from uuid import UUID

from src.domain.events.phase_witness_event import PhaseWitnessEvent
from src.domain.models.deliberation_session import DeliberationPhase, DeliberationSession


class PhaseWitnessBatchingProtocol(Protocol):
    """Protocol for phase-level witness batching (Story 2A.7, FR-11.7).

    Implementations batch utterances by phase and emit a single witness
    event per phase boundary, avoiding witness volume explosion while
    maintaining 100% auditability.

    Constitutional Constraints:
    - CT-12: Every action witnessed
    - FR-11.7: Phase boundary witnessing
    - NFR-10.4: 100% witness completeness
    """

    async def witness_phase(
        self,
        session: DeliberationSession,
        phase: DeliberationPhase,
        transcript: str,
        metadata: dict[str, Any],
        start_timestamp: datetime,
        end_timestamp: datetime,
    ) -> PhaseWitnessEvent:
        """Witness a completed phase with its full transcript.

        Args:
            session: The deliberation session.
            phase: The phase that completed.
            transcript: Full text transcript of the phase.
            metadata: Phase-specific metadata.
            start_timestamp: When phase started.
            end_timestamp: When phase completed.

        Returns:
            PhaseWitnessEvent with hash-referenced transcript.
        """
        ...

    async def get_phase_witness(
        self,
        session_id: UUID,
        phase: DeliberationPhase,
    ) -> PhaseWitnessEvent | None:
        """Retrieve witness event for a specific phase.

        Args:
            session_id: UUID of the deliberation session.
            phase: The phase to retrieve.

        Returns:
            PhaseWitnessEvent if found, None otherwise.
        """
        ...

    async def get_all_witnesses(
        self,
        session_id: UUID,
    ) -> list[PhaseWitnessEvent]:
        """Retrieve all witness events for a session.

        Args:
            session_id: UUID of the deliberation session.

        Returns:
            List of PhaseWitnessEvents in chronological order.
        """
        ...

    async def get_transcript_by_hash(
        self,
        transcript_hash: bytes,
    ) -> str | None:
        """Retrieve raw transcript by content hash.

        Args:
            transcript_hash: Blake3 hash of the transcript.

        Returns:
            Raw transcript text if found, None otherwise.
        """
        ...
```

### Service Implementation

```python
# src/application/services/phase_witness_batching_service.py

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

import blake3

from src.application.ports.content_hash_service import ContentHashServiceProtocol
from src.domain.events.phase_witness_event import PhaseWitnessEvent
from src.domain.models.deliberation_session import DeliberationPhase, DeliberationSession


class PhaseWitnessBatchingService:
    """Service for phase-level witness batching (Story 2A.7, FR-11.7).

    Batches all utterances in a deliberation phase and emits a single
    witness event at the phase boundary. Maintains hash chain between
    phases for audit trail integrity.

    Constitutional Constraints:
    - CT-12: Every action witnessed
    - FR-11.7: Phase boundary witnessing
    - NFR-10.4: 100% witness completeness
    - Ruling-1: Phase-level batching

    Attributes:
        _content_hash_service: Service for Blake3 hashing.
        _witness_events: In-memory storage for witness events (by session).
        _transcripts: In-memory storage for raw transcripts (by hash).
    """

    def __init__(
        self,
        content_hash_service: ContentHashServiceProtocol | None = None,
    ) -> None:
        """Initialize the phase witness batching service.

        Args:
            content_hash_service: Optional content hash service.
                If not provided, uses Blake3 directly.
        """
        self._content_hash_service = content_hash_service
        # In-memory storage - replace with repository in production
        self._witness_events: dict[UUID, dict[DeliberationPhase, PhaseWitnessEvent]] = {}
        self._transcripts: dict[bytes, str] = {}

    def _compute_hash(self, content: str) -> bytes:
        """Compute Blake3 hash of content."""
        if self._content_hash_service:
            return self._content_hash_service.hash_text(content)
        return blake3.blake3(content.encode("utf-8")).digest()

    def _get_previous_witness_hash(
        self,
        session_id: UUID,
        phase: DeliberationPhase,
    ) -> bytes | None:
        """Get the witness hash from the previous phase.

        Args:
            session_id: The session ID.
            phase: The current phase (to find previous).

        Returns:
            Hash of previous phase's witness event, or None for ASSESS.
        """
        # Phase order
        phase_order = [
            DeliberationPhase.ASSESS,
            DeliberationPhase.POSITION,
            DeliberationPhase.CROSS_EXAMINE,
            DeliberationPhase.VOTE,
        ]

        current_idx = phase_order.index(phase)
        if current_idx == 0:
            return None  # ASSESS has no previous

        previous_phase = phase_order[current_idx - 1]
        session_events = self._witness_events.get(session_id, {})
        previous_event = session_events.get(previous_phase)

        if previous_event is None:
            raise ValueError(
                f"Cannot witness {phase.value} without prior {previous_phase.value} witness"
            )

        return previous_event.event_hash

    async def witness_phase(
        self,
        session: DeliberationSession,
        phase: DeliberationPhase,
        transcript: str,
        metadata: dict[str, Any],
        start_timestamp: datetime,
        end_timestamp: datetime,
    ) -> PhaseWitnessEvent:
        """Witness a completed phase with its full transcript.

        Creates a witness event with:
        - Blake3 hash of the full transcript
        - Content-addressed storage of raw transcript
        - Chain link to previous phase's witness

        Args:
            session: The deliberation session.
            phase: The phase that completed.
            transcript: Full text transcript of the phase.
            metadata: Phase-specific metadata.
            start_timestamp: When phase started.
            end_timestamp: When phase completed.

        Returns:
            PhaseWitnessEvent with hash-referenced transcript.

        Raises:
            ValueError: If witnessing out of order or invalid input.
        """
        # Compute transcript hash
        transcript_hash = self._compute_hash(transcript)

        # Store transcript as content-addressed artifact
        self._transcripts[transcript_hash] = transcript

        # Get previous witness hash for chaining
        previous_hash = self._get_previous_witness_hash(session.session_id, phase)

        # Create witness event
        event = PhaseWitnessEvent(
            event_id=uuid4(),  # Should be UUIDv7 in production
            session_id=session.session_id,
            phase=phase,
            transcript_hash=transcript_hash,
            participating_archons=session.assigned_archons,
            start_timestamp=start_timestamp,
            end_timestamp=end_timestamp,
            phase_metadata=metadata,
            previous_witness_hash=previous_hash,
        )

        # Store event
        if session.session_id not in self._witness_events:
            self._witness_events[session.session_id] = {}
        self._witness_events[session.session_id][phase] = event

        return event

    async def get_phase_witness(
        self,
        session_id: UUID,
        phase: DeliberationPhase,
    ) -> PhaseWitnessEvent | None:
        """Retrieve witness event for a specific phase."""
        session_events = self._witness_events.get(session_id, {})
        return session_events.get(phase)

    async def get_all_witnesses(
        self,
        session_id: UUID,
    ) -> list[PhaseWitnessEvent]:
        """Retrieve all witness events for a session in order."""
        session_events = self._witness_events.get(session_id, {})

        # Return in phase order
        phase_order = [
            DeliberationPhase.ASSESS,
            DeliberationPhase.POSITION,
            DeliberationPhase.CROSS_EXAMINE,
            DeliberationPhase.VOTE,
        ]

        return [
            session_events[phase]
            for phase in phase_order
            if phase in session_events
        ]

    async def get_transcript_by_hash(
        self,
        transcript_hash: bytes,
    ) -> str | None:
        """Retrieve raw transcript by content hash."""
        return self._transcripts.get(transcript_hash)
```

### Stub Implementation

```python
# src/infrastructure/stubs/phase_witness_batching_stub.py

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

import blake3

from src.domain.events.phase_witness_event import PhaseWitnessEvent
from src.domain.models.deliberation_session import DeliberationPhase, DeliberationSession


class PhaseWitnessBatchingStub:
    """Stub implementation of PhaseWitnessBatchingProtocol for testing.

    Provides configurable witness event generation for unit tests
    without requiring full service dependencies.
    """

    def __init__(self) -> None:
        """Initialize the stub."""
        self.witness_phase_calls: list[tuple[DeliberationSession, DeliberationPhase, str, dict]] = []
        self._events: dict[UUID, dict[DeliberationPhase, PhaseWitnessEvent]] = {}
        self._transcripts: dict[bytes, str] = {}
        self._force_error: bool = False

    def set_force_error(self, force: bool) -> None:
        """Force errors for testing error paths."""
        self._force_error = force

    async def witness_phase(
        self,
        session: DeliberationSession,
        phase: DeliberationPhase,
        transcript: str,
        metadata: dict[str, Any],
        start_timestamp: datetime,
        end_timestamp: datetime,
    ) -> PhaseWitnessEvent:
        """Record call and return stub event."""
        self.witness_phase_calls.append((session, phase, transcript, metadata))

        if self._force_error:
            raise RuntimeError("Forced error for testing")

        transcript_hash = blake3.blake3(transcript.encode()).digest()
        self._transcripts[transcript_hash] = transcript

        # Get previous hash
        previous_hash = None
        if phase != DeliberationPhase.ASSESS:
            session_events = self._events.get(session.session_id, {})
            phase_order = [
                DeliberationPhase.ASSESS,
                DeliberationPhase.POSITION,
                DeliberationPhase.CROSS_EXAMINE,
                DeliberationPhase.VOTE,
            ]
            current_idx = phase_order.index(phase)
            previous_phase = phase_order[current_idx - 1]
            if previous_phase in session_events:
                previous_hash = session_events[previous_phase].event_hash

        event = PhaseWitnessEvent(
            event_id=uuid4(),
            session_id=session.session_id,
            phase=phase,
            transcript_hash=transcript_hash,
            participating_archons=session.assigned_archons,
            start_timestamp=start_timestamp,
            end_timestamp=end_timestamp,
            phase_metadata=metadata,
            previous_witness_hash=previous_hash,
        )

        if session.session_id not in self._events:
            self._events[session.session_id] = {}
        self._events[session.session_id][phase] = event

        return event

    async def get_phase_witness(
        self,
        session_id: UUID,
        phase: DeliberationPhase,
    ) -> PhaseWitnessEvent | None:
        """Get recorded event."""
        return self._events.get(session_id, {}).get(phase)

    async def get_all_witnesses(
        self,
        session_id: UUID,
    ) -> list[PhaseWitnessEvent]:
        """Get all events for session."""
        session_events = self._events.get(session_id, {})
        phase_order = [
            DeliberationPhase.ASSESS,
            DeliberationPhase.POSITION,
            DeliberationPhase.CROSS_EXAMINE,
            DeliberationPhase.VOTE,
        ]
        return [session_events[p] for p in phase_order if p in session_events]

    async def get_transcript_by_hash(
        self,
        transcript_hash: bytes,
    ) -> str | None:
        """Get transcript by hash."""
        return self._transcripts.get(transcript_hash)
```

## Dependencies

### Upstream Dependencies (Required Before This Story)

| Story ID | Name | Status | Why Needed |
|----------|------|--------|------------|
| petition-2a-1 | Deliberation Session Domain Model | DONE | DeliberationSession with phase_transcripts |
| petition-2a-4 | Deliberation Protocol Orchestrator | DONE | Calls witness_phase() after each phase |
| petition-0-5 | Content Hashing Service | DONE | Blake3 hashing service |

### Downstream Dependencies (Blocked By This Story)

| Story ID | Name | Why Blocked |
|----------|------|-------------|
| petition-2a-8 | Disposition Emission & Pipeline Routing | Needs phase witnesses complete |
| petition-2b-5 | Transcript Preservation & Hash Referencing | Uses witness events for audit |
| petition-2b-6 | Audit Trail Reconstruction | Uses witness chain for reconstruction |

## Implementation Tasks

### Task 1: Create PhaseWitnessEvent Model (AC: 1)
- [x] Create `src/domain/events/phase_witness.py`
- [x] Define `PhaseWitnessEvent` frozen dataclass
- [x] Implement validation for all fields
- [x] Implement `event_hash` property for chaining
- [x] Export from `src/domain/events/__init__.py`

### Task 2: Create Service Protocol (AC: 2)
- [x] Create `src/application/ports/phase_witness_batching.py`
- [x] Define `PhaseWitnessBatchingProtocol`
- [x] Export from `src/application/ports/__init__.py`

### Task 3: Implement Service (AC: 3, 4, 5)
- [x] Create `src/application/services/phase_witness_batching_service.py`
- [x] Implement `witness_phase()` with hash chaining
- [x] Implement content-addressed transcript storage
- [x] Implement retrieval methods
- [x] Export from `src/application/services/__init__.py`

### Task 4: Create Stub (AC: 2)
- [x] Create `src/infrastructure/stubs/phase_witness_batching_stub.py`
- [x] Implement stub with call tracking
- [x] Export from `src/infrastructure/stubs/__init__.py`

### Task 5: Write Unit Tests (AC: 6)
- [x] Create `tests/unit/domain/events/test_phase_witness_event.py`
- [x] Create `tests/unit/application/services/test_phase_witness_batching_service.py`
- [x] Test all validation rules
- [x] Test hash chaining logic
- [x] Test metadata handling

### Task 6: Write Integration Tests (AC: 7)
- [x] Create `tests/integration/test_phase_witness_batching_integration.py`
- [x] Test full 4-phase witnessing flow
- [x] Test content-addressed retrieval
- [x] Test integration with DeliberationSession

## Definition of Done

- [x] `PhaseWitnessEvent` domain event created
- [x] `PhaseWitnessBatchingProtocol` defined
- [x] `PhaseWitnessBatchingService` implements phase witnessing
- [x] `PhaseWitnessBatchingStub` for testing
- [x] Unit tests pass (>90% coverage)
- [x] Integration tests verify 4 events per deliberation
- [x] FR-11.7 satisfied: Hash-referenced witnessing at phase boundaries
- [x] NFR-10.4 satisfied: 100% witness completeness
- [x] Ruling-1 satisfied: Phase-level batching (not per-utterance)
- [x] Hash chain integrity verified

## Test Scenarios

### Scenario 1: Single Phase Witnessing
```python
service = PhaseWitnessBatchingService()
session = create_session_with_archons(archon1, archon2, archon3)

event = await service.witness_phase(
    session=session,
    phase=DeliberationPhase.ASSESS,
    transcript="Archon 1: This petition concerns...\nArchon 2: I observe...",
    metadata={"assessments_recorded": 3},
    start_timestamp=datetime(2026, 1, 19, 10, 0, 0),
    end_timestamp=datetime(2026, 1, 19, 10, 5, 0),
)

assert event.phase == DeliberationPhase.ASSESS
assert len(event.transcript_hash) == 32
assert event.previous_witness_hash is None  # First phase
```

### Scenario 2: Full 4-Phase Witnessing
```python
service = PhaseWitnessBatchingService()
session = create_session_with_archons(archon1, archon2, archon3)

# Witness all 4 phases
phases = [
    (DeliberationPhase.ASSESS, "ASSESS transcript..."),
    (DeliberationPhase.POSITION, "POSITION transcript..."),
    (DeliberationPhase.CROSS_EXAMINE, "CROSS_EXAMINE transcript..."),
    (DeliberationPhase.VOTE, "VOTE transcript..."),
]

events = []
for phase, transcript in phases:
    event = await service.witness_phase(
        session=session,
        phase=phase,
        transcript=transcript,
        metadata={},
        start_timestamp=datetime.now(timezone.utc),
        end_timestamp=datetime.now(timezone.utc),
    )
    events.append(event)

assert len(events) == 4

# Verify chain
assert events[0].previous_witness_hash is None
assert events[1].previous_witness_hash == events[0].event_hash
assert events[2].previous_witness_hash == events[1].event_hash
assert events[3].previous_witness_hash == events[2].event_hash
```

### Scenario 3: Content-Addressed Retrieval
```python
service = PhaseWitnessBatchingService()
transcript = "Original transcript content for audit"

event = await service.witness_phase(
    session=session,
    phase=DeliberationPhase.ASSESS,
    transcript=transcript,
    metadata={},
    start_timestamp=start,
    end_timestamp=end,
)

# Retrieve by hash
retrieved = await service.get_transcript_by_hash(event.transcript_hash)
assert retrieved == transcript

# Verify hash integrity
recomputed = blake3.blake3(transcript.encode()).digest()
assert event.transcript_hash == recomputed
```

### Scenario 4: Out-of-Order Witnessing Error
```python
service = PhaseWitnessBatchingService()
session = create_session()

# Try to witness POSITION without ASSESS
with pytest.raises(ValueError, match="Cannot witness POSITION without prior ASSESS"):
    await service.witness_phase(
        session=session,
        phase=DeliberationPhase.POSITION,
        transcript="...",
        metadata={},
        start_timestamp=start,
        end_timestamp=end,
    )
```

## Dev Notes

### Relevant Architecture Patterns

1. **Existing witness infrastructure**:
   - `WitnessService` in `src/application/services/witness_service.py`
   - Uses HSM for attestation signing
   - This story focuses on batching, not attestation signing

2. **Content hashing**:
   - `Blake3ContentHashService` in `src/application/services/content_hash_service.py`
   - Already provides BLAKE3 hashing (Story 0.5)
   - Reuse for transcript hashing

3. **DeliberationSession integration**:
   - `with_transcript()` method already exists
   - Stores transcript hash in `phase_transcripts` dict
   - This story adds the witness event layer

### Key Files to Reference

| File | Why |
|------|-----|
| `src/domain/models/deliberation_session.py` | `with_transcript()` method |
| `src/application/services/content_hash_service.py` | Blake3 hashing |
| `src/application/services/witness_service.py` | Witness attestation pattern |
| `src/domain/events/` | Event structure patterns |

### Integration Point

The orchestrator service (Story 2A.4) should call `witness_phase()` after each phase completes:

```python
# In orchestrator, after each phase
result = await executor.execute_phase(session, package)

# Witness the phase
witness_event = await witness_batching.witness_phase(
    session=session,
    phase=current_phase,
    transcript=result.transcript,
    metadata=result.phase_metadata,
    start_timestamp=phase_start,
    end_timestamp=phase_end,
)

# Update session with transcript hash
session = session.with_transcript(current_phase, witness_event.transcript_hash)
```

### Phase Metadata Examples

| Phase | Metadata Keys |
|-------|---------------|
| ASSESS | `assessments_recorded`, `risk_flags`, `initial_sentiment` |
| POSITION | `positions_converged`, `disposition_alignment`, `key_points` |
| CROSS_EXAMINE | `challenges_raised`, `positions_modified`, `clarifications` |
| VOTE | `vote_breakdown`, `consensus_type`, `dissent_present` |

## Documentation Checklist

- [ ] Architecture docs updated (if patterns/structure changed)
- [ ] API docs updated (if endpoints/contracts changed)
- [ ] README updated (if setup/usage changed)
- [ ] Inline comments added for complex logic
- [x] N/A - Internal service, no external API impact

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

N/A

### Completion Notes List

1. Implemented `PhaseWitnessEvent` domain event with:
   - Frozen dataclass for immutability
   - Blake3 hash validation (32 bytes)
   - Hash chaining between phases
   - Comprehensive field validation
   - `event_hash` property for witness chain

2. Created `PhaseWitnessBatchingProtocol` with methods:
   - `witness_phase()` - Witness a phase with transcript
   - `get_phase_witness()` - Retrieve specific phase witness
   - `get_all_witnesses()` - Get all witnesses in order
   - `get_transcript_by_hash()` - Content-addressed retrieval
   - `verify_witness_chain()` - Validate hash chain
   - `verify_transcript_integrity()` - Validate transcripts

3. Implemented `PhaseWitnessBatchingService` with:
   - In-memory witness event storage per session
   - Content-addressed transcript storage
   - Phase ordering enforcement
   - Hash chain integrity verification
   - Helper methods (`get_witness_count`, `has_complete_witnessing`)

4. Created `PhaseWitnessBatchingStub` with:
   - Call tracking for test verification
   - Configurable error forcing
   - Configurable chain validity forcing

5. Comprehensive test coverage:
   - Unit tests for PhaseWitnessEvent
   - Unit tests for PhaseWitnessBatchingService
   - Integration tests for full deliberation flow

### File List

**Created Files:**
- `src/domain/events/phase_witness.py` - PhaseWitnessEvent domain event
- `src/application/ports/phase_witness_batching.py` - Protocol definition
- `src/application/services/phase_witness_batching_service.py` - Service implementation
- `src/infrastructure/stubs/phase_witness_batching_stub.py` - Test stub
- `tests/unit/domain/events/test_phase_witness_event.py` - Event unit tests
- `tests/unit/application/services/test_phase_witness_batching_service.py` - Service unit tests
- `tests/integration/test_phase_witness_batching_integration.py` - Integration tests

**Modified Files:**
- `src/domain/events/__init__.py` - Added exports
- `src/application/ports/__init__.py` - Added exports
- `src/application/services/__init__.py` - Added exports
- `src/infrastructure/stubs/__init__.py` - Added exports
