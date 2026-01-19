# Story 2A.2: Archon Assignment Service

## Story Information

| Field | Value |
|-------|-------|
| **Story ID** | petition-2a-2 |
| **Epic** | Epic 2A: Core Deliberation Protocol |
| **Priority** | P0-CRITICAL |
| **Status** | ready |
| **Created** | 2026-01-19 |

## User Story

**As a** system,
**I want** to assign exactly 3 Marquis-rank Archons to deliberate each petition,
**So that** every petition receives collective judgment.

## Requirements Coverage

### Functional Requirements

| FR ID | Requirement | Priority |
|-------|-------------|----------|
| FR-11.1 | System SHALL assign exactly 3 Marquis-rank Archons from Three Fates pool to deliberate each petition | P0 |
| FR-11.2 | System SHALL initiate mini-Conclave deliberation session when petition enters RECEIVED state | P0 |

### Non-Functional Requirements

| NFR ID | Requirement | Target |
|--------|-------------|--------|
| NFR-10.3 | Consensus determinism | 100% reproducible given same inputs |
| NFR-10.5 | Concurrent deliberations | 100+ simultaneous sessions |
| NFR-10.6 | Archon substitution latency | < 10 seconds on failure |

### Hidden Prerequisites

| HP ID | Requirement | Status |
|-------|-------------|--------|
| HP-11 | Archon persona definitions for Three Fates pool | DONE (Story 0-7) |

### Constitutional Truths

- **AT-1**: Every petition terminates in exactly one of Three Fates
- **AT-6**: Deliberation is collective judgment, not unilateral decision
- **CT-14**: "Silence must be expensive. Every claim on attention terminates in a visible, witnessed fate."

## Acceptance Criteria

### AC-1: Archon Selection on Petition Received

**Given** a petition enters RECEIVED state
**When** the deliberation is initiated
**Then** the ArchonPool service selects exactly 3 Archons
**And** selection is deterministic given (petition_id + seed)
**And** selected Archons are from the configured Three Fates pool (7 Marquis-rank)
**And** the assignment is recorded in the DeliberationSession

### AC-2: Deterministic Selection

**Given** a petition_id and optional seed
**When** Archon selection is performed multiple times
**Then** the same 3 Archons are always selected in the same order
**And** different petition_ids produce different selections (distribution across pool)
**And** the selection algorithm uses SHA-256 for uniform distribution

### AC-3: Idempotent Assignment

**Given** a petition_id that has already been assigned Archons
**When** assignment is attempted again
**Then** the system returns the existing assignment (idempotent)
**And** no new DeliberationSession is created
**And** no error is raised

### AC-4: Session Creation

**Given** a petition without an existing DeliberationSession
**When** assignment is initiated
**Then** a new DeliberationSession is created with:
- `session_id` (new UUIDv7)
- `petition_id` (from petition)
- `assigned_archons` (3 selected archon IDs)
- `phase` = ASSESS (initial phase)
- `created_at` = current timestamp
**And** the petition state transitions from RECEIVED to DELIBERATING

### AC-5: Event Emission

**Given** a successful Archon assignment
**When** the assignment is complete
**Then** an `ArchonsAssignedEvent` is emitted with:
- `petition_id`
- `session_id`
- `assigned_archons` (array of 3 archon IDs)
- `assigned_at` timestamp
- `schema_version` (D2 compliance)
**And** the event is witnessed per CT-12

### AC-6: Concurrent Assignment Protection

**Given** two concurrent requests to assign Archons to the same petition
**When** both attempt to create a DeliberationSession
**Then** only one succeeds (unique constraint on petition_id)
**And** the other receives the existing assignment (idempotent)
**And** no race condition creates duplicate sessions

### AC-7: Assignment Service Protocol

**Given** the need for testability and dependency injection
**Then** an `ArchonAssignmentServiceProtocol` is defined with:
- `assign_archons(petition_id: UUID, seed: int | None = None) -> AssignmentResult`
- `get_assignment(petition_id: UUID) -> AssignmentResult | None`
**And** a stub implementation is provided for testing
**And** the protocol is registered in application ports

## Technical Design

### Service Protocol

```python
# src/application/ports/archon_assignment.py

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from src.domain.models.deliberation_session import DeliberationSession
from src.domain.models.fate_archon import FateArchon

@dataclass(frozen=True)
class AssignmentResult:
    """Result of Archon assignment operation."""
    session: DeliberationSession
    archons: tuple[FateArchon, FateArchon, FateArchon]
    was_existing: bool  # True if returned existing assignment

class ArchonAssignmentServiceProtocol(Protocol):
    """Protocol for assigning Archons to petitions (Story 2A.2, FR-11.1)."""

    async def assign_archons(
        self,
        petition_id: UUID,
        seed: int | None = None,
    ) -> AssignmentResult:
        """Assign 3 Archons to deliberate a petition.

        Selection is deterministic: given the same (petition_id, seed),
        the same 3 Archons will always be assigned.

        If assignment already exists, returns existing assignment (idempotent).

        Args:
            petition_id: UUID of the petition requiring deliberation.
            seed: Optional seed for deterministic selection.

        Returns:
            AssignmentResult with session, archons, and was_existing flag.

        Raises:
            PetitionNotFoundError: If petition doesn't exist.
            InvalidPetitionStateError: If petition is not in RECEIVED state.
        """
        ...

    async def get_assignment(
        self,
        petition_id: UUID,
    ) -> AssignmentResult | None:
        """Get existing Archon assignment for a petition.

        Args:
            petition_id: UUID of the petition.

        Returns:
            AssignmentResult if assignment exists, None otherwise.
        """
        ...
```

### Service Implementation

```python
# src/application/services/archon_assignment_service.py

from uuid import UUID, uuid7

from src.application.ports.archon_pool import ArchonPoolProtocol
from src.application.ports.petition_submission_repository import PetitionSubmissionRepositoryProtocol
from src.domain.models.deliberation_session import DeliberationSession, DeliberationPhase
from src.domain.models.petition_submission import PetitionState

class ArchonAssignmentService:
    """Service for assigning Archons to petitions (Story 2A.2)."""

    def __init__(
        self,
        archon_pool: ArchonPoolProtocol,
        petition_repo: PetitionSubmissionRepositoryProtocol,
        session_repo: DeliberationSessionRepositoryProtocol,
        event_emitter: PetitionEventEmitterProtocol,
    ) -> None:
        self._archon_pool = archon_pool
        self._petition_repo = petition_repo
        self._session_repo = session_repo
        self._event_emitter = event_emitter

    async def assign_archons(
        self,
        petition_id: UUID,
        seed: int | None = None,
    ) -> AssignmentResult:
        # Check for existing assignment (idempotent)
        existing = await self._session_repo.get_by_petition_id(petition_id)
        if existing:
            archons = self._archon_pool.select_archons(petition_id, seed)
            return AssignmentResult(
                session=existing,
                archons=archons,
                was_existing=True,
            )

        # Verify petition exists and is in correct state
        petition = await self._petition_repo.get_by_id(petition_id)
        if petition is None:
            raise PetitionNotFoundError(petition_id)
        if petition.state != PetitionState.RECEIVED:
            raise InvalidPetitionStateError(
                petition_id=petition_id,
                current_state=petition.state,
                required_state=PetitionState.RECEIVED,
            )

        # Select 3 Archons deterministically
        archons = self._archon_pool.select_archons(petition_id, seed)

        # Create deliberation session
        session = DeliberationSession.create(
            session_id=uuid7(),
            petition_id=petition_id,
            assigned_archons=(archons[0].id, archons[1].id, archons[2].id),
        )

        # Persist session (with unique constraint handling)
        try:
            await self._session_repo.save(session)
        except UniqueConstraintError:
            # Race condition: another request created session
            existing = await self._session_repo.get_by_petition_id(petition_id)
            return AssignmentResult(
                session=existing,
                archons=archons,
                was_existing=True,
            )

        # Transition petition to DELIBERATING
        updated_petition = petition.with_state(PetitionState.DELIBERATING)
        await self._petition_repo.save(updated_petition)

        # Emit event
        await self._event_emitter.emit_archons_assigned(
            petition_id=petition_id,
            session_id=session.session_id,
            assigned_archons=[a.id for a in archons],
        )

        return AssignmentResult(
            session=session,
            archons=archons,
            was_existing=False,
        )
```

### Event Payload

```python
# src/domain/events/deliberation.py

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

@dataclass(frozen=True)
class ArchonsAssignedEventPayload:
    """Payload for archon assignment events (Story 2A.2, FR-11.1)."""
    petition_id: UUID
    session_id: UUID
    assigned_archons: tuple[UUID, UUID, UUID]
    assigned_at: datetime
    schema_version: str = "1.0.0"  # D2 compliance
```

### Stub Implementation

```python
# src/infrastructure/stubs/archon_assignment_stub.py

class ArchonAssignmentServiceStub:
    """In-memory stub for testing (Story 2A.2)."""

    def __init__(self, archon_pool: ArchonPoolProtocol) -> None:
        self._archon_pool = archon_pool
        self._assignments: dict[UUID, DeliberationSession] = {}
        self._emitted_events: list[ArchonsAssignedEventPayload] = []

    async def assign_archons(
        self,
        petition_id: UUID,
        seed: int | None = None,
    ) -> AssignmentResult:
        # Check existing
        if petition_id in self._assignments:
            session = self._assignments[petition_id]
            archons = self._archon_pool.select_archons(petition_id, seed)
            return AssignmentResult(
                session=session,
                archons=archons,
                was_existing=True,
            )

        # Create new
        archons = self._archon_pool.select_archons(petition_id, seed)
        session = DeliberationSession.create(
            session_id=uuid7(),
            petition_id=petition_id,
            assigned_archons=(archons[0].id, archons[1].id, archons[2].id),
        )
        self._assignments[petition_id] = session

        # Record event
        event = ArchonsAssignedEventPayload(
            petition_id=petition_id,
            session_id=session.session_id,
            assigned_archons=(archons[0].id, archons[1].id, archons[2].id),
            assigned_at=datetime.now(timezone.utc),
        )
        self._emitted_events.append(event)

        return AssignmentResult(
            session=session,
            archons=archons,
            was_existing=False,
        )
```

## Dependencies

### Upstream Dependencies (Required Before This Story)

| Story ID | Name | Status | Why Needed |
|----------|------|--------|------------|
| petition-2a-1 | Deliberation Session Domain Model | READY | DeliberationSession aggregate to record assignment |
| petition-0-7 | Archon Persona Definitions | DONE | ArchonPoolService with selection algorithm |
| petition-0-2 | Petition Domain Model | DONE | PetitionSubmission state transitions |
| petition-1-2 | Petition Received Event Emission | DONE | Event emission pattern |

### Downstream Dependencies (Blocked By This Story)

| Story ID | Name | Why Blocked |
|----------|------|-------------|
| petition-2a-3 | Deliberation Context Package Builder | Needs assigned archons |
| petition-2a-4 | Deliberation Protocol Orchestrator | Needs session with archons |
| petition-2a-5 | CrewAI Deliberation Adapter | Needs archon assignment |

## Implementation Tasks

### Task 1: Create Service Protocol
- [ ] Create `src/application/ports/archon_assignment.py`
- [ ] Define `AssignmentResult` dataclass
- [ ] Define `ArchonAssignmentServiceProtocol`
- [ ] Export from `src/application/ports/__init__.py`

### Task 2: Create Service Implementation
- [ ] Create `src/application/services/archon_assignment_service.py`
- [ ] Implement `assign_archons()` method
- [ ] Implement `get_assignment()` method
- [ ] Handle idempotency via unique constraint
- [ ] Handle race conditions gracefully
- [ ] Export from `src/application/services/__init__.py`

### Task 3: Create Event Payload
- [ ] Create `src/domain/events/deliberation.py`
- [ ] Define `ArchonsAssignedEventPayload`
- [ ] Include schema_version for D2 compliance
- [ ] Export from `src/domain/events/__init__.py`

### Task 4: Create Stub Implementation
- [ ] Create `src/infrastructure/stubs/archon_assignment_stub.py`
- [ ] Implement in-memory assignment storage
- [ ] Record emitted events for test assertions
- [ ] Export from `src/infrastructure/stubs/__init__.py`

### Task 5: Create Error Types
- [ ] Add `PetitionNotFoundError` if not exists
- [ ] Add `InvalidPetitionStateError` if not exists
- [ ] Export from `src/domain/errors/__init__.py`

### Task 6: Write Unit Tests
- [ ] Create `tests/unit/application/services/test_archon_assignment_service.py`
- [ ] Test happy path assignment
- [ ] Test deterministic selection (same petition_id = same archons)
- [ ] Test idempotency (second call returns existing)
- [ ] Test petition not found error
- [ ] Test invalid state error (not RECEIVED)
- [ ] Test event emission
- [ ] Test race condition handling

### Task 7: Write Integration Tests
- [ ] Create `tests/integration/test_archon_assignment.py`
- [ ] Test with real ArchonPoolService
- [ ] Test concurrent assignment (unique constraint)
- [ ] Test petition state transition to DELIBERATING
- [ ] Test event witnessed in ledger

## Definition of Done

- [ ] ArchonAssignmentServiceProtocol defined
- [ ] Service implementation complete with idempotency
- [ ] Event payload includes schema_version (D2 compliance)
- [ ] Stub implementation for testing
- [ ] Unit tests pass (>90% coverage)
- [ ] Integration tests verify concurrent safety
- [ ] Code review completed
- [ ] FR-11.1 satisfied: Exactly 3 Marquis-rank Archons assigned
- [ ] FR-11.2 satisfied: Deliberation initiated on RECEIVED state
- [ ] NFR-10.3 satisfied: Deterministic selection

## Test Scenarios

### Scenario 1: Happy Path - New Assignment
```python
# Setup
petition = create_petition(state=PetitionState.RECEIVED)
service = ArchonAssignmentService(...)

# Execute
result = await service.assign_archons(petition.id)

# Verify
assert not result.was_existing
assert len(result.archons) == 3
assert result.session.petition_id == petition.id
assert result.session.phase == DeliberationPhase.ASSESS
assert all(archon.id in FATE_ARCHON_IDS for archon in result.archons)
```

### Scenario 2: Idempotent - Second Assignment Returns Existing
```python
# First assignment
result1 = await service.assign_archons(petition.id)

# Second assignment
result2 = await service.assign_archons(petition.id)

# Verify idempotency
assert result2.was_existing
assert result2.session.session_id == result1.session.session_id
assert result2.archons == result1.archons
```

### Scenario 3: Deterministic Selection
```python
# Multiple calls with same petition_id
archons1 = archon_pool.select_archons(petition_id, seed=42)
archons2 = archon_pool.select_archons(petition_id, seed=42)
archons3 = archon_pool.select_archons(petition_id, seed=42)

# Same selection every time
assert archons1 == archons2 == archons3
```

### Scenario 4: Invalid State - Not RECEIVED
```python
petition = create_petition(state=PetitionState.DELIBERATING)

with pytest.raises(InvalidPetitionStateError) as exc:
    await service.assign_archons(petition.id)

assert exc.value.current_state == PetitionState.DELIBERATING
assert exc.value.required_state == PetitionState.RECEIVED
```

### Scenario 5: Concurrent Assignment - Race Condition
```python
petition = create_petition(state=PetitionState.RECEIVED)

# Simulate concurrent requests
results = await asyncio.gather(
    service.assign_archons(petition.id),
    service.assign_archons(petition.id),
    return_exceptions=True,
)

# Both should succeed with same session
successful = [r for r in results if not isinstance(r, Exception)]
assert len(successful) == 2
assert successful[0].session.session_id == successful[1].session.session_id
# One was_existing=False, one was_existing=True
```

## Notes

- Builds on ArchonPoolService from Story 0-7 (already implements deterministic selection)
- DeliberationSession creation requires Story 2A.1 to be implemented first
- The unique constraint on `petition_id` in `deliberation_sessions` table provides concurrency safety
- Event emission follows pattern established in Story 1-2
- The service coordinates multiple repositories but keeps business logic in domain

## Revision History

| Date | Author | Changes |
|------|--------|---------|
| 2026-01-19 | Claude | Initial story creation |
