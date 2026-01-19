# Story 2A.1: Deliberation Session Domain Model

## Story Information

| Field | Value |
|-------|-------|
| **Story ID** | petition-2a-1 |
| **Epic** | Epic 2A: Core Deliberation Protocol |
| **Priority** | P0-CRITICAL |
| **Status** | ready |
| **Created** | 2026-01-19 |

## User Story

**As a** developer,
**I want** a DeliberationSession aggregate that models the mini-Conclave,
**So that** deliberation state and transitions are properly encapsulated.

## Requirements Coverage

### Functional Requirements

| FR ID | Requirement | Priority |
|-------|-------------|----------|
| FR-11.1 | System SHALL assign exactly 3 Marquis-rank Archons from Three Fates pool to deliberate each petition | P0 |
| FR-11.4 | Deliberation SHALL follow structured protocol: Assess → Position → Cross-Examine → Vote | P0 |

### Non-Functional Requirements

| NFR ID | Requirement | Target |
|--------|-------------|--------|
| NFR-10.3 | Consensus determinism | 100% reproducible given same inputs |
| NFR-10.4 | Witness completeness | 100% utterances witnessed |
| NFR-10.5 | Concurrent deliberations | 100+ simultaneous sessions |

### Constitutional Truths

- **CT-14**: "Silence must be expensive. Every claim on attention terminates in a visible, witnessed fate."
- **AT-1**: Every petition terminates in exactly one of Three Fates
- **AT-6**: Deliberation is collective judgment, not unilateral decision

## Acceptance Criteria

### AC-1: DeliberationSession Aggregate Structure

**Given** no existing deliberation model
**When** I create the DeliberationSession aggregate
**Then** it contains:
- `session_id` (UUIDv7)
- `petition_id` (foreign key to petition_submissions)
- `assigned_archons` (array of exactly 3 archon_ids)
- `phase` (enum: ASSESS, POSITION, CROSS_EXAMINE, VOTE, COMPLETE)
- `phase_transcripts` (map of phase → transcript_hash)
- `votes` (map of archon_id → disposition)
- `outcome` (nullable: ACKNOWLEDGE, REFER, ESCALATE)
- `dissent_archon_id` (nullable: UUID of dissenting archon)
- `created_at` (timestamp)
- `completed_at` (nullable timestamp)
- `version` (optimistic locking)

### AC-2: Database Migration

**Given** the DeliberationSession domain model
**When** I create the database migration
**Then** it creates the `deliberation_sessions` table with:
- Primary key on `session_id`
- Foreign key to `petition_submissions(id)` with unique constraint (one session per petition)
- Array column for `assigned_archons` (UUID[3])
- JSONB for `phase_transcripts`
- JSONB for `votes`
- Enum for `phase` and `outcome`
- Index on `petition_id` for lookups
- Index on `phase` for in-progress session queries
- Index on `created_at` for timeout detection

### AC-3: Domain Invariants - Archon Count

**Given** a DeliberationSession
**When** `assigned_archons` is set
**Then** it MUST contain exactly 3 valid archon UUIDs
**And** attempting to set fewer or more than 3 raises `ValueError`
**And** attempting to set duplicate archon IDs raises `ValueError`
**And** attempting to set invalid archon IDs raises `ValueError`

### AC-4: Domain Invariants - Phase Progression

**Given** a DeliberationSession with current phase
**When** transitioning to next phase
**Then** phases progress in strict order: ASSESS → POSITION → CROSS_EXAMINE → VOTE → COMPLETE
**And** skipping phases raises `InvalidPhaseTransitionError`
**And** going backwards raises `InvalidPhaseTransitionError`
**And** only COMPLETE is a terminal phase

### AC-5: Domain Invariants - Outcome Requires Consensus

**Given** a DeliberationSession
**When** setting the outcome
**Then** outcome requires 2+ matching votes (supermajority)
**And** attempting to set outcome without 2+ agreement raises `ConsensusNotReachedError`
**And** outcome can only be set when phase is VOTE or COMPLETE
**And** votes map must have exactly 3 entries (one per assigned archon)

### AC-6: Domain Invariants - Immutable Once Complete

**Given** a DeliberationSession with `phase == COMPLETE`
**When** any modification is attempted
**Then** `SessionAlreadyCompleteError` is raised
**And** all fields are effectively frozen

### AC-7: Unit Tests

**Given** the DeliberationSession domain model
**Then** unit tests verify:
- Happy path: session creation, phase progression, consensus, completion
- Archon count invariant (exactly 3)
- No duplicate archons
- Phase progression order (forward only)
- Consensus requirements (2-of-3)
- Terminal state immutability
- Vote integrity (only assigned archons can vote)
- Phase transcript storage and retrieval
- Dissent recording when vote is 2-1

## Technical Design

### Domain Model

```python
# src/domain/models/deliberation_session.py

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from uuid import UUID

class DeliberationPhase(Enum):
    """Phase in the deliberation protocol (FR-11.4)."""
    ASSESS = "ASSESS"           # Phase 1: Independent assessment
    POSITION = "POSITION"       # Phase 2: State preferred disposition
    CROSS_EXAMINE = "CROSS_EXAMINE"  # Phase 3: Challenge positions
    VOTE = "VOTE"               # Phase 4: Cast final votes
    COMPLETE = "COMPLETE"       # Terminal: Deliberation finished

class DeliberationOutcome(Enum):
    """Possible outcomes of deliberation (Three Fates)."""
    ACKNOWLEDGE = "ACKNOWLEDGE"
    REFER = "REFER"
    ESCALATE = "ESCALATE"

@dataclass(frozen=True, eq=True)
class DeliberationSession:
    """A mini-Conclave deliberation session (Story 2A.1, FR-11.1, FR-11.4)."""

    session_id: UUID
    petition_id: UUID
    assigned_archons: tuple[UUID, UUID, UUID]
    phase: DeliberationPhase
    phase_transcripts: dict[DeliberationPhase, bytes]  # phase -> Blake3 hash
    votes: dict[UUID, DeliberationOutcome]  # archon_id -> vote
    outcome: DeliberationOutcome | None
    dissent_archon_id: UUID | None
    created_at: datetime
    completed_at: datetime | None
    version: int  # Optimistic locking
```

### Phase Transition Matrix

```python
PHASE_TRANSITION_MATRIX: dict[DeliberationPhase, DeliberationPhase | None] = {
    DeliberationPhase.ASSESS: DeliberationPhase.POSITION,
    DeliberationPhase.POSITION: DeliberationPhase.CROSS_EXAMINE,
    DeliberationPhase.CROSS_EXAMINE: DeliberationPhase.VOTE,
    DeliberationPhase.VOTE: DeliberationPhase.COMPLETE,
    DeliberationPhase.COMPLETE: None,  # Terminal
}
```

### Database Migration

```sql
-- migrations/017_create_deliberation_sessions.sql

-- Enum types
CREATE TYPE deliberation_phase AS ENUM (
    'ASSESS', 'POSITION', 'CROSS_EXAMINE', 'VOTE', 'COMPLETE'
);

CREATE TYPE deliberation_outcome AS ENUM (
    'ACKNOWLEDGE', 'REFER', 'ESCALATE'
);

-- Deliberation sessions table
CREATE TABLE deliberation_sessions (
    session_id UUID PRIMARY KEY,
    petition_id UUID NOT NULL UNIQUE REFERENCES petition_submissions(id),
    assigned_archons UUID[3] NOT NULL,
    phase deliberation_phase NOT NULL DEFAULT 'ASSESS',
    phase_transcripts JSONB NOT NULL DEFAULT '{}',
    votes JSONB NOT NULL DEFAULT '{}',
    outcome deliberation_outcome,
    dissent_archon_id UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    version INTEGER NOT NULL DEFAULT 1,

    -- Constraints
    CONSTRAINT check_exactly_3_archons CHECK (
        array_length(assigned_archons, 1) = 3
    ),
    CONSTRAINT check_unique_archons CHECK (
        assigned_archons[1] != assigned_archons[2] AND
        assigned_archons[2] != assigned_archons[3] AND
        assigned_archons[1] != assigned_archons[3]
    ),
    CONSTRAINT check_completed_has_outcome CHECK (
        (phase = 'COMPLETE' AND outcome IS NOT NULL) OR
        (phase != 'COMPLETE')
    ),
    CONSTRAINT check_dissent_when_not_unanimous CHECK (
        dissent_archon_id IS NULL OR
        dissent_archon_id = ANY(assigned_archons)
    )
);

-- Indexes
CREATE INDEX idx_deliberation_sessions_petition_id ON deliberation_sessions(petition_id);
CREATE INDEX idx_deliberation_sessions_phase ON deliberation_sessions(phase) WHERE phase != 'COMPLETE';
CREATE INDEX idx_deliberation_sessions_created_at ON deliberation_sessions(created_at);
CREATE INDEX idx_deliberation_sessions_incomplete ON deliberation_sessions(created_at)
    WHERE phase != 'COMPLETE';
```

### Error Types

```python
# src/domain/errors/deliberation.py

class InvalidPhaseTransitionError(DomainError):
    """Raised when attempting invalid phase transition."""
    pass

class ConsensusNotReachedError(DomainError):
    """Raised when setting outcome without 2-of-3 consensus."""
    pass

class SessionAlreadyCompleteError(DomainError):
    """Raised when modifying a completed session."""
    pass

class InvalidArchonAssignmentError(DomainError):
    """Raised when archon assignment violates invariants."""
    pass
```

## Dependencies

### Upstream Dependencies (Required Before This Story)

| Story ID | Name | Status |
|----------|------|--------|
| petition-0-2 | Petition Domain Model & Base Schema | DONE |
| petition-0-7 | Archon Persona Definitions (Three Fates) | DONE |

### Downstream Dependencies (Blocked By This Story)

| Story ID | Name | Why Blocked |
|----------|------|-------------|
| petition-2a-2 | Archon Assignment Service | Needs DeliberationSession to record assignment |
| petition-2a-3 | Deliberation Context Package Builder | Needs session_id for context |
| petition-2a-4 | Deliberation Protocol Orchestrator | Needs phase transitions |
| petition-2a-5 | CrewAI Deliberation Adapter | Needs session model |
| petition-2a-6 | Supermajority Consensus Resolution | Needs votes map |
| petition-2a-7 | Phase-Level Witness Batching | Needs phase_transcripts |
| petition-2a-8 | Disposition Emission & Pipeline Routing | Needs outcome |

## Implementation Tasks

### Task 1: Create Domain Model
- [ ] Create `src/domain/models/deliberation_session.py`
- [ ] Define `DeliberationPhase` enum
- [ ] Define `DeliberationOutcome` enum
- [ ] Create frozen `DeliberationSession` dataclass
- [ ] Implement `__post_init__` validation for invariants
- [ ] Add method `with_phase()` for phase transitions
- [ ] Add method `with_votes()` for recording votes
- [ ] Add method `with_outcome()` for setting final outcome
- [ ] Add method `with_transcript()` for recording phase transcripts
- [ ] Export from `src/domain/models/__init__.py`

### Task 2: Create Error Types
- [ ] Create `src/domain/errors/deliberation.py`
- [ ] Define `InvalidPhaseTransitionError`
- [ ] Define `ConsensusNotReachedError`
- [ ] Define `SessionAlreadyCompleteError`
- [ ] Define `InvalidArchonAssignmentError`
- [ ] Export from `src/domain/errors/__init__.py`

### Task 3: Create Database Migration
- [ ] Create `migrations/017_create_deliberation_sessions.sql`
- [ ] Define enum types for phase and outcome
- [ ] Create table with all columns
- [ ] Add CHECK constraints for invariants
- [ ] Add indexes for query patterns
- [ ] Test migration applies cleanly

### Task 4: Write Unit Tests
- [ ] Create `tests/unit/domain/models/test_deliberation_session.py`
- [ ] Test session creation with valid archons
- [ ] Test exactly-3-archons invariant
- [ ] Test no-duplicate-archons invariant
- [ ] Test valid archon ID requirement
- [ ] Test phase progression (forward only)
- [ ] Test invalid phase transitions
- [ ] Test vote recording (only assigned archons)
- [ ] Test consensus calculation (2-of-3)
- [ ] Test outcome setting requirements
- [ ] Test immutability when complete
- [ ] Test dissent recording
- [ ] Test phase transcript storage

### Task 5: Write Integration Tests
- [ ] Create `tests/integration/test_deliberation_sessions_schema.py`
- [ ] Test migration applies
- [ ] Test CHECK constraints work
- [ ] Test unique petition_id constraint
- [ ] Test foreign key constraint
- [ ] Test indexes exist

## Definition of Done

- [ ] DeliberationSession domain model implemented with all invariants
- [ ] All error types defined and exported
- [ ] Migration 017 created and tested
- [ ] Unit tests pass (>90% coverage on domain model)
- [ ] Integration tests verify schema constraints
- [ ] Code review completed
- [ ] D2 compliance: Frozen dataclass for immutability
- [ ] D7 compliance: All errors include constitutional references

## Test Scenarios

### Scenario 1: Happy Path - Full Deliberation Lifecycle
```python
# Create session with 3 archons
session = DeliberationSession.create(
    petition_id=petition.id,
    assigned_archons=(archon1.id, archon2.id, archon3.id),
)
assert session.phase == DeliberationPhase.ASSESS

# Progress through phases
session = session.with_phase(DeliberationPhase.POSITION)
session = session.with_phase(DeliberationPhase.CROSS_EXAMINE)
session = session.with_phase(DeliberationPhase.VOTE)

# Record votes (2-1 for ACKNOWLEDGE)
session = session.with_votes({
    archon1.id: DeliberationOutcome.ACKNOWLEDGE,
    archon2.id: DeliberationOutcome.ACKNOWLEDGE,
    archon3.id: DeliberationOutcome.REFER,
})

# Resolve consensus
session = session.with_outcome()
assert session.outcome == DeliberationOutcome.ACKNOWLEDGE
assert session.dissent_archon_id == archon3.id
assert session.phase == DeliberationPhase.COMPLETE
```

### Scenario 2: Invalid Archon Count
```python
with pytest.raises(InvalidArchonAssignmentError):
    DeliberationSession.create(
        petition_id=petition.id,
        assigned_archons=(archon1.id, archon2.id),  # Only 2
    )
```

### Scenario 3: Invalid Phase Transition
```python
session = DeliberationSession.create(...)  # Phase = ASSESS
with pytest.raises(InvalidPhaseTransitionError):
    session.with_phase(DeliberationPhase.VOTE)  # Can't skip
```

### Scenario 4: Modification After Complete
```python
completed_session = ...  # phase = COMPLETE
with pytest.raises(SessionAlreadyCompleteError):
    completed_session.with_votes({...})
```

## Notes

- DeliberationSession follows the same frozen dataclass pattern as PetitionSubmission
- The `assigned_archons` tuple is ordered - position may matter for tie-breaking
- Phase transcripts store Blake3 hashes; actual transcripts are content-addressed artifacts
- The `version` field enables optimistic locking for concurrent access (NFR-3.2)
- Dissent recording is automatic when consensus is 2-1 (FR-11.8)

## Revision History

| Date | Author | Changes |
|------|--------|---------|
| 2026-01-19 | Claude | Initial story creation |
