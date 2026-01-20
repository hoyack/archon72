# Story 2A.4: Deliberation Protocol Orchestrator

## Story Information

| Field | Value |
|-------|-------|
| **Story ID** | petition-2a-4 |
| **Epic** | Epic 2A: Core Deliberation Protocol |
| **Priority** | P0-CRITICAL |
| **Status** | done |
| **Created** | 2026-01-19 |

## User Story

**As a** system,
**I want** to orchestrate the 4-phase deliberation protocol,
**So that** Archons proceed through Assess -> Position -> Cross-Examine -> Vote.

## Requirements Coverage

### Functional Requirements

| FR ID | Requirement | Priority |
|-------|-------------|----------|
| FR-11.4 | Deliberation SHALL follow structured protocol: Assess -> Position -> Cross-Examine -> Vote | P0 |
| FR-11.5 | System SHALL require supermajority consensus (2-of-3 Archons) for disposition decision | P0 |

### Non-Functional Requirements

| NFR ID | Requirement | Target |
|--------|-------------|--------|
| NFR-10.1 | Deliberation end-to-end latency | p95 < 5 minutes |
| NFR-10.2 | Individual Archon response time | p95 < 30 seconds |
| NFR-10.3 | Consensus determinism | 100% reproducible given same inputs |

### Constitutional Truths

- **CT-14**: "Silence must be expensive. Every claim on attention terminates in a visible, witnessed fate."
- **AT-1**: Every petition terminates in exactly one of Three Fates
- **AT-6**: Deliberation is collective judgment, not unilateral decision

## Acceptance Criteria

### AC-1: Phase Sequence Enforcement

**Given** a DeliberationSession with 3 assigned Archons
**When** deliberation begins
**Then** the orchestrator executes phases in strict sequence:
1. ASSESS
2. POSITION
3. CROSS_EXAMINE
4. VOTE
**And** no phase can be skipped
**And** phases cannot be executed out of order

### AC-2: Phase 1 - ASSESS Protocol

**Given** deliberation begins
**When** the ASSESS phase executes
**Then** each Archon receives the context package
**And** each Archon produces an independent assessment
**And** assessments are collected from all 3 Archons before proceeding
**And** the phase transcript is recorded with Blake3 hash

### AC-3: Phase 2 - POSITION Protocol

**Given** ASSESS phase is complete
**When** the POSITION phase executes
**Then** each Archon states their preferred disposition (ACKNOWLEDGE, REFER, or ESCALATE)
**And** positions are sequential (Archon 1 -> 2 -> 3)
**And** each Archon can see previous positions before stating their own
**And** each position includes rationale text
**And** the phase transcript is recorded with Blake3 hash

### AC-4: Phase 3 - CROSS_EXAMINE Protocol

**Given** POSITION phase is complete
**When** the CROSS_EXAMINE phase executes
**Then** Archons may challenge each other's positions
**And** challenges are sequential with responses
**And** maximum 3 rounds of exchange per cross-examine
**And** phase ends when no Archon raises a new challenge (or max rounds reached)
**And** the phase transcript is recorded with Blake3 hash

### AC-5: Phase 4 - VOTE Protocol

**Given** CROSS_EXAMINE phase is complete
**When** the VOTE phase executes
**Then** each Archon casts a final vote: ACKNOWLEDGE, REFER, or ESCALATE
**And** votes are simultaneous (no seeing others' votes before casting)
**And** all 3 votes are collected
**And** the phase transcript is recorded with Blake3 hash

### AC-6: Orchestrator Protocol Interface

**Given** the need for testability and CrewAI adapter integration
**Then** a `DeliberationOrchestratorProtocol` is defined with:
- `orchestrate(session: DeliberationSession, package: DeliberationContextPackage) -> DeliberationResult`
**And** the protocol accepts a `DeliberationExecutorProtocol` for phase execution
**And** a stub implementation is provided for testing

### AC-7: Phase Result Model

**Given** each phase execution
**When** the phase completes
**Then** a `PhaseResult` is returned containing:
- `phase`: The phase that was executed
- `transcript`: Full text transcript of phase
- `transcript_hash`: Blake3 hash of transcript
- `participants`: List of participating archon IDs
- `started_at`: Phase start timestamp
- `completed_at`: Phase completion timestamp
- `phase_metadata`: Dict with phase-specific metadata

### AC-8: Deliberation Result Model

**Given** deliberation completes
**When** all phases have executed
**Then** a `DeliberationResult` is returned containing:
- `session_id`: UUID of the session
- `petition_id`: UUID of the petition
- `outcome`: The resolved outcome (ACKNOWLEDGE, REFER, ESCALATE)
- `votes`: Dict of archon_id -> vote
- `dissent_archon_id`: UUID of dissenting archon (if 2-1 vote)
- `phase_results`: List of all PhaseResult objects
- `started_at`: Deliberation start timestamp
- `completed_at`: Deliberation completion timestamp
- `total_duration_ms`: Total deliberation time in milliseconds

## Technical Design

### Domain Models

```python
# src/domain/models/deliberation_result.py

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

from src.domain.models.deliberation_session import (
    DeliberationOutcome,
    DeliberationPhase,
)


@dataclass(frozen=True, eq=True)
class PhaseResult:
    """Result of a single deliberation phase execution.

    Captures the transcript and metadata for each phase of the
    deliberation protocol (ASSESS, POSITION, CROSS_EXAMINE, VOTE).

    Attributes:
        phase: The phase that was executed.
        transcript: Full text transcript of the phase.
        transcript_hash: Blake3 hash of transcript (32 bytes).
        participants: Ordered list of participating archon IDs.
        started_at: Phase start timestamp (UTC).
        completed_at: Phase completion timestamp (UTC).
        phase_metadata: Phase-specific metadata (e.g., "positions_converged").
    """

    phase: DeliberationPhase
    transcript: str
    transcript_hash: bytes
    participants: tuple[UUID, ...]
    started_at: datetime
    completed_at: datetime
    phase_metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def duration_ms(self) -> int:
        """Get phase duration in milliseconds."""
        delta = self.completed_at - self.started_at
        return int(delta.total_seconds() * 1000)


@dataclass(frozen=True, eq=True)
class DeliberationResult:
    """Complete result of a deliberation session.

    Captures the outcome and all phase results for a completed
    Three Fates deliberation.

    Attributes:
        session_id: UUID of the deliberation session.
        petition_id: UUID of the petition deliberated.
        outcome: The resolved outcome (ACKNOWLEDGE, REFER, ESCALATE).
        votes: Map of archon_id to their final vote.
        dissent_archon_id: UUID of dissenting archon (if 2-1 vote).
        phase_results: Ordered list of all phase results.
        started_at: Deliberation start timestamp (UTC).
        completed_at: Deliberation completion timestamp (UTC).
    """

    session_id: UUID
    petition_id: UUID
    outcome: DeliberationOutcome
    votes: dict[UUID, DeliberationOutcome]
    dissent_archon_id: UUID | None
    phase_results: tuple[PhaseResult, ...]
    started_at: datetime
    completed_at: datetime

    @property
    def total_duration_ms(self) -> int:
        """Get total deliberation duration in milliseconds."""
        delta = self.completed_at - self.started_at
        return int(delta.total_seconds() * 1000)

    @property
    def is_unanimous(self) -> bool:
        """Check if deliberation was unanimous (3-0 vote)."""
        return self.dissent_archon_id is None
```

### Service Protocols

```python
# src/application/ports/deliberation_orchestrator.py

from typing import Protocol
from src.domain.models.deliberation_session import DeliberationSession
from src.domain.models.deliberation_context_package import DeliberationContextPackage
from src.domain.models.deliberation_result import DeliberationResult, PhaseResult


class PhaseExecutorProtocol(Protocol):
    """Protocol for executing individual deliberation phases.

    Implementations execute a single phase of the deliberation protocol,
    collecting responses from Archons and returning a PhaseResult.

    This allows the orchestrator to be decoupled from the actual
    execution mechanism (CrewAI, mock, etc.).
    """

    def execute_assess(
        self,
        session: DeliberationSession,
        package: DeliberationContextPackage,
    ) -> PhaseResult:
        """Execute ASSESS phase - independent assessments."""
        ...

    def execute_position(
        self,
        session: DeliberationSession,
        package: DeliberationContextPackage,
        assess_result: PhaseResult,
    ) -> PhaseResult:
        """Execute POSITION phase - state preferred dispositions."""
        ...

    def execute_cross_examine(
        self,
        session: DeliberationSession,
        package: DeliberationContextPackage,
        position_result: PhaseResult,
    ) -> PhaseResult:
        """Execute CROSS_EXAMINE phase - challenge positions."""
        ...

    def execute_vote(
        self,
        session: DeliberationSession,
        package: DeliberationContextPackage,
        cross_examine_result: PhaseResult,
    ) -> PhaseResult:
        """Execute VOTE phase - cast final votes."""
        ...


class DeliberationOrchestratorProtocol(Protocol):
    """Protocol for orchestrating the deliberation protocol.

    Implementations coordinate the 4-phase deliberation protocol,
    ensuring strict phase sequence and collecting results.
    """

    def orchestrate(
        self,
        session: DeliberationSession,
        package: DeliberationContextPackage,
    ) -> DeliberationResult:
        """Orchestrate the complete deliberation protocol.

        Executes the 4-phase protocol in sequence:
        ASSESS -> POSITION -> CROSS_EXAMINE -> VOTE

        Args:
            session: The deliberation session with assigned archons.
            package: The context package for deliberation.

        Returns:
            DeliberationResult with outcome and phase transcripts.

        Raises:
            DeliberationError: If orchestration fails.
        """
        ...
```

### Service Implementation

```python
# src/application/services/deliberation_orchestrator_service.py

from datetime import datetime, timezone

from src.domain.models.deliberation_session import (
    DeliberationSession,
    DeliberationPhase,
    CONSENSUS_THRESHOLD,
)
from src.domain.models.deliberation_context_package import DeliberationContextPackage
from src.domain.models.deliberation_result import (
    DeliberationResult,
    PhaseResult,
)
from src.application.ports.deliberation_orchestrator import PhaseExecutorProtocol


class DeliberationOrchestratorService:
    """Service for orchestrating the 4-phase deliberation protocol (Story 2A.4, FR-11.4).

    Coordinates the execution of ASSESS -> POSITION -> CROSS_EXAMINE -> VOTE
    phases in strict sequence, collecting results and resolving consensus.
    """

    def __init__(self, executor: PhaseExecutorProtocol) -> None:
        """Initialize orchestrator with a phase executor.

        Args:
            executor: Protocol implementation for executing phases.
        """
        self._executor = executor

    def orchestrate(
        self,
        session: DeliberationSession,
        package: DeliberationContextPackage,
    ) -> DeliberationResult:
        """Orchestrate the complete deliberation protocol.

        Executes the 4-phase protocol in sequence, updates session state,
        and returns the complete result with outcome and transcripts.
        """
        started_at = datetime.now(timezone.utc)
        phase_results: list[PhaseResult] = []

        # Phase 1: ASSESS
        assess_result = self._executor.execute_assess(session, package)
        phase_results.append(assess_result)
        session = session.with_transcript(DeliberationPhase.ASSESS, assess_result.transcript_hash)
        session = session.with_phase(DeliberationPhase.POSITION)

        # Phase 2: POSITION
        position_result = self._executor.execute_position(session, package, assess_result)
        phase_results.append(position_result)
        session = session.with_transcript(DeliberationPhase.POSITION, position_result.transcript_hash)
        session = session.with_phase(DeliberationPhase.CROSS_EXAMINE)

        # Phase 3: CROSS_EXAMINE
        cross_examine_result = self._executor.execute_cross_examine(
            session, package, position_result
        )
        phase_results.append(cross_examine_result)
        session = session.with_transcript(
            DeliberationPhase.CROSS_EXAMINE, cross_examine_result.transcript_hash
        )
        session = session.with_phase(DeliberationPhase.VOTE)

        # Phase 4: VOTE
        vote_result = self._executor.execute_vote(
            session, package, cross_examine_result
        )
        phase_results.append(vote_result)
        session = session.with_transcript(DeliberationPhase.VOTE, vote_result.transcript_hash)

        # Extract votes from vote result metadata
        votes = vote_result.phase_metadata.get("votes", {})
        session = session.with_votes(votes)
        session = session.with_outcome()

        completed_at = datetime.now(timezone.utc)

        return DeliberationResult(
            session_id=session.session_id,
            petition_id=session.petition_id,
            outcome=session.outcome,
            votes=dict(session.votes),
            dissent_archon_id=session.dissent_archon_id,
            phase_results=tuple(phase_results),
            started_at=started_at,
            completed_at=completed_at,
        )
```

## Dependencies

### Upstream Dependencies (Required Before This Story)

| Story ID | Name | Status | Why Needed |
|----------|------|--------|------------|
| petition-2a-1 | Deliberation Session Domain Model | DONE | DeliberationSession aggregate |
| petition-2a-2 | Archon Assignment Service | DONE | Session with assigned archons |
| petition-2a-3 | Context Package Builder | DONE | Context package for Archons |

### Downstream Dependencies (Blocked By This Story)

| Story ID | Name | Why Blocked |
|----------|------|-------------|
| petition-2a-5 | CrewAI Deliberation Adapter | Needs orchestrator to implement executor protocol |
| petition-2a-6 | Supermajority Consensus Resolution | Orchestrator resolves consensus via session.with_outcome() |
| petition-2a-7 | Phase-Level Witness Batching | Needs phase results with transcript hashes |

## Implementation Tasks

### Task 1: Create Domain Models
- [x] Create `src/domain/models/deliberation_result.py`
- [x] Define `PhaseResult` frozen dataclass
- [x] Define `DeliberationResult` frozen dataclass
- [x] Export from `src/domain/models/__init__.py`

### Task 2: Create Service Protocols
- [x] Create `src/application/ports/deliberation_orchestrator.py`
- [x] Define `PhaseExecutorProtocol`
- [x] Define `DeliberationOrchestratorProtocol`
- [x] Export from `src/application/ports/__init__.py`

### Task 3: Create Service Implementation
- [x] Create `src/application/services/deliberation_orchestrator_service.py`
- [x] Implement `orchestrate()` method with strict phase sequence
- [x] Handle session state updates through phases
- [x] Export from `src/application/services/__init__.py`

### Task 4: Create Stub Implementations
- [x] Create `src/infrastructure/stubs/deliberation_orchestrator_stub.py`
- [x] Implement `PhaseExecutorStub` for testing
- [x] Implement `DeliberationOrchestratorStub` for testing
- [x] Export from `src/infrastructure/stubs/__init__.py`

### Task 5: Write Unit Tests
- [x] Create `tests/unit/domain/models/test_deliberation_result.py`
- [x] Test PhaseResult frozen behavior
- [x] Test DeliberationResult frozen behavior
- [x] Test duration calculations

### Task 6: Write Service Tests
- [x] Create `tests/unit/application/services/test_deliberation_orchestrator_service.py`
- [x] Test strict phase sequence
- [x] Test session state progression
- [x] Test consensus resolution integration

### Task 7: Write Integration Tests
- [x] Create `tests/integration/test_deliberation_orchestrator_integration.py`
- [x] Test full orchestration with stub executor
- [x] Test transcript hash recording
- [x] Test vote collection and outcome resolution

## Definition of Done

- [x] PhaseResult domain model created
- [x] DeliberationResult domain model created
- [x] PhaseExecutorProtocol defined
- [x] DeliberationOrchestratorProtocol defined
- [x] Service implementation complete
- [x] Stub implementations for testing
- [x] Unit tests pass (>90% coverage)
- [x] Integration tests verify phase sequence
- [x] Code review completed
- [x] FR-11.4 satisfied: Structured protocol execution
- [x] NFR-10.3 satisfied: Deterministic phase sequence

## Test Scenarios

### Scenario 1: Happy Path - Full Orchestration
```python
# Setup
session = create_session(petition_id=petition.id, archons=(a1, a2, a3))
package = builder.build_package(petition, session)
executor = PhaseExecutorStub()
orchestrator = DeliberationOrchestratorService(executor)

# Execute
result = orchestrator.orchestrate(session, package)

# Verify
assert len(result.phase_results) == 4
assert result.phase_results[0].phase == DeliberationPhase.ASSESS
assert result.phase_results[1].phase == DeliberationPhase.POSITION
assert result.phase_results[2].phase == DeliberationPhase.CROSS_EXAMINE
assert result.phase_results[3].phase == DeliberationPhase.VOTE
assert result.outcome in [DeliberationOutcome.ACKNOWLEDGE, DeliberationOutcome.REFER, DeliberationOutcome.ESCALATE]
```

### Scenario 2: Unanimous Vote (3-0)
```python
# Setup with all archons voting ACKNOWLEDGE
executor = PhaseExecutorStub(unanimous_vote=DeliberationOutcome.ACKNOWLEDGE)
orchestrator = DeliberationOrchestratorService(executor)

# Execute
result = orchestrator.orchestrate(session, package)

# Verify
assert result.outcome == DeliberationOutcome.ACKNOWLEDGE
assert result.is_unanimous is True
assert result.dissent_archon_id is None
```

### Scenario 3: 2-1 Vote with Dissent
```python
# Setup with 2 ACKNOWLEDGE, 1 REFER
executor = PhaseExecutorStub(votes={a1: ACKNOWLEDGE, a2: ACKNOWLEDGE, a3: REFER})
orchestrator = DeliberationOrchestratorService(executor)

# Execute
result = orchestrator.orchestrate(session, package)

# Verify
assert result.outcome == DeliberationOutcome.ACKNOWLEDGE
assert result.is_unanimous is False
assert result.dissent_archon_id == a3
```

### Scenario 4: Transcript Hash Recording
```python
result = orchestrator.orchestrate(session, package)

# All phases have transcript hashes
for phase_result in result.phase_results:
    assert len(phase_result.transcript_hash) == 32  # Blake3
    assert phase_result.transcript != ""  # Has content
```

## Notes

- Orchestrator is decoupled from actual execution via PhaseExecutorProtocol
- CrewAI adapter (Story 2A.5) will implement PhaseExecutorProtocol
- Timeout handling and deadlock detection are in Epic 2B
- Phase results include metadata for witness batching (Story 2A.7)

## Revision History

| Date | Author | Changes |
|------|--------|---------|
| 2026-01-19 | Claude | Initial story creation |
