# Story 2A.6: Supermajority Consensus Resolution

## Story Information

| Field | Value |
|-------|-------|
| **Story ID** | petition-2a-6 |
| **Epic** | Epic 2A: Core Deliberation Protocol |
| **Priority** | P0-CRITICAL |
| **Status** | done |
| **Created** | 2026-01-19 |

## User Story

**As a** system,
**I want** to resolve deliberation outcome via supermajority consensus,
**So that** 2-of-3 Archon agreement determines petition disposition.

## Requirements Coverage

### Functional Requirements

| FR ID | Requirement | Priority |
|-------|-------------|----------|
| FR-11.5 | System SHALL require supermajority consensus (2-of-3 Archons) for disposition decision | P0 |
| FR-11.6 | Fate Archons SHALL vote for exactly one disposition: ACKNOWLEDGE, REFER, or ESCALATE | P0 |

### Non-Functional Requirements

| NFR ID | Requirement | Target |
|--------|-------------|--------|
| NFR-10.3 | Consensus determinism | 100% reproducible given same inputs |
| NFR-10.4 | Witness completeness | 100% utterances witnessed |

### Constitutional Truths

- **CT-14**: "Silence must be expensive. Every claim on attention terminates in a visible, witnessed fate."
- **AT-1**: Every petition terminates in exactly one of Three Fates
- **AT-6**: Deliberation is collective judgment, not unilateral decision

## Acceptance Criteria

### AC-1: Consensus Resolution Algorithm

**Given** a DeliberationSession with 3 recorded votes
**When** `resolve_consensus()` is invoked
**Then** the algorithm computes outcome:
- If 2+ votes for ACKNOWLEDGE → outcome = ACKNOWLEDGE
- If 2+ votes for REFER → outcome = REFER
- If 2+ votes for ESCALATE → outcome = ESCALATE
- If no 2+ agreement → `ConsensusNotReachedError` raised (handled in Epic 2B)
**And** the outcome is recorded in DeliberationSession
**And** the minority vote is preserved for audit

### AC-2: Consensus Service Protocol

**Given** the need for testability
**When** the ConsensusResolver is created
**Then** it defines a `ConsensusResolverProtocol` with:
- `resolve(session: DeliberationSession) -> ConsensusResult`
- `validate_votes(session: DeliberationSession) -> ValidationResult`
**And** a stub implementation is provided for testing

### AC-3: ConsensusResult Model

**Given** consensus is resolved
**When** the result is returned
**Then** `ConsensusResult` contains:
- `outcome`: The resolved disposition (ACKNOWLEDGE, REFER, or ESCALATE)
- `vote_counts`: Dict of outcome -> count
- `consensus_type`: "unanimous" (3-0) or "supermajority" (2-1)
- `dissent_archon_id`: UUID of dissenting archon (if 2-1)
- `dissent_vote`: The dissenting vote value
- `resolved_at`: Timestamp of resolution

### AC-4: Integration with Orchestrator

**Given** the orchestrator calls `session.with_outcome()` after VOTE phase
**When** consensus is resolved
**Then** the ConsensusResolverService:
- Receives the session with all 3 votes recorded
- Computes the supermajority outcome
- Identifies dissenting archon (if 2-1 vote)
- Returns `ConsensusResult` for witnessing
**And** the orchestrator updates the session state

### AC-5: Audit Trail Preservation

**Given** votes are resolved to an outcome
**When** the outcome is recorded
**Then** all vote information is preserved:
- Individual archon votes (archon_id -> vote)
- Vote timestamp (when each vote was cast)
- Consensus type (unanimous vs supermajority)
- Dissent information (archon_id, dissent_vote)
**And** this information is available for audit reconstruction (FR-11.12)

### AC-6: Vote Validation

**Given** a set of votes to resolve
**When** validation is performed
**Then** the validator ensures:
- Exactly 3 votes are present
- All voters are assigned archons for this session
- Each vote is a valid `DeliberationOutcome` value
- No archon has voted more than once
**And** validation errors include specific violation details

### AC-7: Unit Tests

**Given** the ConsensusResolverService
**Then** unit tests verify:
- 3-0 unanimous ACKNOWLEDGE
- 3-0 unanimous REFER
- 3-0 unanimous ESCALATE
- 2-1 supermajority with dissent tracking
- Invalid vote count (< 3 votes)
- Invalid archon voting
- All vote validation rules
- Deterministic results given same inputs (NFR-10.3)

## Technical Design

### Domain Models

```python
# src/domain/models/consensus_result.py

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from src.domain.models.deliberation_session import DeliberationOutcome


@dataclass(frozen=True, eq=True)
class ConsensusResult:
    """Result of supermajority consensus resolution (Story 2A.6, FR-11.5).

    Captures the outcome of 2-of-3 consensus resolution including
    dissent tracking for audit purposes.

    Attributes:
        outcome: The resolved disposition (ACKNOWLEDGE, REFER, ESCALATE).
        vote_counts: Count of votes for each outcome.
        consensus_type: "unanimous" (3-0) or "supermajority" (2-1).
        dissent_archon_id: UUID of dissenting archon (None if unanimous).
        dissent_vote: The vote cast by the dissenting archon (None if unanimous).
        resolved_at: Timestamp of resolution (UTC).
    """

    outcome: DeliberationOutcome
    vote_counts: dict[DeliberationOutcome, int]
    consensus_type: Literal["unanimous", "supermajority"]
    dissent_archon_id: UUID | None
    dissent_vote: DeliberationOutcome | None
    resolved_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def is_unanimous(self) -> bool:
        """Check if consensus was unanimous (3-0)."""
        return self.consensus_type == "unanimous"

    @property
    def is_supermajority(self) -> bool:
        """Check if consensus was supermajority (2-1)."""
        return self.consensus_type == "supermajority"


@dataclass(frozen=True, eq=True)
class VoteValidationResult:
    """Result of vote validation.

    Attributes:
        is_valid: Whether all votes are valid.
        errors: List of validation error messages.
        vote_count: Number of votes received.
        expected_count: Number of votes expected (3).
    """

    is_valid: bool
    errors: tuple[str, ...] = field(default_factory=tuple)
    vote_count: int = 0
    expected_count: int = 3
```

### Service Protocol

```python
# src/application/ports/consensus_resolver.py

from typing import Protocol
from src.domain.models.deliberation_session import DeliberationSession
from src.domain.models.consensus_result import ConsensusResult, VoteValidationResult


class ConsensusResolverProtocol(Protocol):
    """Protocol for resolving supermajority consensus (Story 2A.6, FR-11.5).

    Implementations compute 2-of-3 consensus from recorded votes
    and track dissent for audit purposes.
    """

    def resolve(self, session: DeliberationSession) -> ConsensusResult:
        """Resolve consensus from session votes.

        Args:
            session: Session with all 3 votes recorded.

        Returns:
            ConsensusResult with outcome and dissent tracking.

        Raises:
            ConsensusNotReachedError: If no 2-of-3 agreement (Epic 2B handles this).
            ValueError: If votes are invalid.
        """
        ...

    def validate_votes(self, session: DeliberationSession) -> VoteValidationResult:
        """Validate votes before resolution.

        Args:
            session: Session to validate.

        Returns:
            VoteValidationResult with validity and error details.
        """
        ...
```

### Service Implementation

```python
# src/application/services/consensus_resolver_service.py

from datetime import datetime, timezone
from uuid import UUID

from src.domain.errors.deliberation import ConsensusNotReachedError
from src.domain.models.consensus_result import ConsensusResult, VoteValidationResult
from src.domain.models.deliberation_session import (
    CONSENSUS_THRESHOLD,
    REQUIRED_ARCHON_COUNT,
    DeliberationOutcome,
    DeliberationSession,
)


class ConsensusResolverService:
    """Service for resolving supermajority consensus (Story 2A.6, FR-11.5).

    Computes 2-of-3 consensus from recorded votes, identifying the
    majority outcome and tracking any dissent for audit purposes.

    Constitutional Constraints:
    - FR-11.5: 2-of-3 supermajority required
    - FR-11.6: Each archon votes exactly one disposition
    - NFR-10.3: Deterministic results given same inputs
    - AT-6: Collective judgment, not unilateral
    """

    def resolve(self, session: DeliberationSession) -> ConsensusResult:
        """Resolve consensus from session votes.

        Implements the supermajority algorithm:
        1. Count votes for each outcome
        2. Find outcome with >= 2 votes (threshold)
        3. Identify dissenting archon if 2-1 split
        4. Return ConsensusResult with full audit trail

        Args:
            session: Session with all 3 votes recorded.

        Returns:
            ConsensusResult with outcome and dissent tracking.

        Raises:
            ConsensusNotReachedError: If no 2-of-3 agreement.
            ValueError: If votes are invalid.
        """
        # Validate votes first
        validation = self.validate_votes(session)
        if not validation.is_valid:
            raise ValueError(f"Invalid votes: {', '.join(validation.errors)}")

        # Count votes by outcome
        vote_counts: dict[DeliberationOutcome, int] = {}
        votes_by_outcome: dict[DeliberationOutcome, list[UUID]] = {}

        for archon_id, vote in session.votes.items():
            vote_counts[vote] = vote_counts.get(vote, 0) + 1
            if vote not in votes_by_outcome:
                votes_by_outcome[vote] = []
            votes_by_outcome[vote].append(archon_id)

        # Find outcome with supermajority (>= 2 votes)
        resolved_outcome: DeliberationOutcome | None = None
        consensus_type: str = "unanimous"
        dissent_archon_id: UUID | None = None
        dissent_vote: DeliberationOutcome | None = None

        for outcome, count in vote_counts.items():
            if count >= CONSENSUS_THRESHOLD:
                resolved_outcome = outcome

                if count == REQUIRED_ARCHON_COUNT:
                    # Unanimous (3-0)
                    consensus_type = "unanimous"
                else:
                    # Supermajority (2-1)
                    consensus_type = "supermajority"

                    # Find the dissenting archon
                    for other_outcome, voters in votes_by_outcome.items():
                        if other_outcome != outcome and len(voters) == 1:
                            dissent_archon_id = voters[0]
                            dissent_vote = other_outcome
                            break
                break

        if resolved_outcome is None:
            # No 2-of-3 agreement - this is a deadlock (handled in Epic 2B)
            raise ConsensusNotReachedError(
                message="No outcome achieved 2-of-3 consensus",
                votes_received=len(session.votes),
                votes_required=CONSENSUS_THRESHOLD,
            )

        return ConsensusResult(
            outcome=resolved_outcome,
            vote_counts=vote_counts,
            consensus_type=consensus_type,
            dissent_archon_id=dissent_archon_id,
            dissent_vote=dissent_vote,
            resolved_at=datetime.now(timezone.utc),
        )

    def validate_votes(self, session: DeliberationSession) -> VoteValidationResult:
        """Validate votes before resolution.

        Checks:
        1. Exactly 3 votes present
        2. All voters are assigned archons
        3. Each vote is valid DeliberationOutcome
        4. No duplicate voters

        Args:
            session: Session to validate.

        Returns:
            VoteValidationResult with validity and error details.
        """
        errors: list[str] = []

        # Check vote count
        vote_count = len(session.votes)
        if vote_count != REQUIRED_ARCHON_COUNT:
            errors.append(
                f"Expected {REQUIRED_ARCHON_COUNT} votes, got {vote_count}"
            )

        # Check all voters are assigned
        assigned_set = set(session.assigned_archons)
        for archon_id in session.votes:
            if archon_id not in assigned_set:
                errors.append(
                    f"Archon {archon_id} is not assigned to this session"
                )

        # Check all assigned archons have voted
        for archon_id in session.assigned_archons:
            if archon_id not in session.votes:
                errors.append(
                    f"Assigned archon {archon_id} has not voted"
                )

        # Check vote values are valid
        valid_outcomes = {o for o in DeliberationOutcome}
        for archon_id, vote in session.votes.items():
            if vote not in valid_outcomes:
                errors.append(
                    f"Invalid vote value from {archon_id}: {vote}"
                )

        return VoteValidationResult(
            is_valid=len(errors) == 0,
            errors=tuple(errors),
            vote_count=vote_count,
            expected_count=REQUIRED_ARCHON_COUNT,
        )
```

### Stub Implementation

```python
# src/infrastructure/stubs/consensus_resolver_stub.py

from datetime import datetime, timezone
from uuid import UUID

from src.domain.models.consensus_result import ConsensusResult, VoteValidationResult
from src.domain.models.deliberation_session import (
    CONSENSUS_THRESHOLD,
    REQUIRED_ARCHON_COUNT,
    DeliberationOutcome,
    DeliberationSession,
)


class ConsensusResolverStub:
    """Stub implementation of ConsensusResolverProtocol for testing.

    Provides configurable consensus resolution for unit testing
    without real vote processing.
    """

    def __init__(
        self,
        default_outcome: DeliberationOutcome = DeliberationOutcome.ACKNOWLEDGE,
        force_unanimous: bool = True,
    ) -> None:
        """Initialize stub with configurable defaults.

        Args:
            default_outcome: Outcome to return by default.
            force_unanimous: If True, always return unanimous (3-0).
        """
        self._default_outcome = default_outcome
        self._force_unanimous = force_unanimous
        self.resolve_calls: list[DeliberationSession] = []
        self.validate_calls: list[DeliberationSession] = []

    def resolve(self, session: DeliberationSession) -> ConsensusResult:
        """Resolve consensus using stub logic."""
        self.resolve_calls.append(session)

        # If session has votes, use them; otherwise use defaults
        if session.votes:
            vote_counts: dict[DeliberationOutcome, int] = {}
            for vote in session.votes.values():
                vote_counts[vote] = vote_counts.get(vote, 0) + 1

            # Find majority
            for outcome, count in vote_counts.items():
                if count >= CONSENSUS_THRESHOLD:
                    is_unanimous = count == REQUIRED_ARCHON_COUNT
                    dissent_archon_id = None
                    dissent_vote = None

                    if not is_unanimous:
                        for aid, v in session.votes.items():
                            if v != outcome:
                                dissent_archon_id = aid
                                dissent_vote = v
                                break

                    return ConsensusResult(
                        outcome=outcome,
                        vote_counts=vote_counts,
                        consensus_type="unanimous" if is_unanimous else "supermajority",
                        dissent_archon_id=dissent_archon_id,
                        dissent_vote=dissent_vote,
                        resolved_at=datetime.now(timezone.utc),
                    )

        # Default response
        return ConsensusResult(
            outcome=self._default_outcome,
            vote_counts={self._default_outcome: 3},
            consensus_type="unanimous" if self._force_unanimous else "supermajority",
            dissent_archon_id=None,
            dissent_vote=None,
            resolved_at=datetime.now(timezone.utc),
        )

    def validate_votes(self, session: DeliberationSession) -> VoteValidationResult:
        """Validate votes - stub always returns valid."""
        self.validate_calls.append(session)
        return VoteValidationResult(
            is_valid=True,
            errors=(),
            vote_count=len(session.votes),
            expected_count=REQUIRED_ARCHON_COUNT,
        )
```

## Dependencies

### Upstream Dependencies (Required Before This Story)

| Story ID | Name | Status | Why Needed |
|----------|------|--------|------------|
| petition-2a-1 | Deliberation Session Domain Model | DONE | DeliberationSession with votes map |
| petition-2a-4 | Deliberation Protocol Orchestrator | DONE | Calls with_outcome() needing consensus |
| petition-2a-5 | CrewAI Deliberation Adapter | DONE | Produces votes in VOTE phase |

### Downstream Dependencies (Blocked By This Story)

| Story ID | Name | Why Blocked |
|----------|------|-------------|
| petition-2a-7 | Phase-Level Witness Batching | Needs consensus result for witness event |
| petition-2a-8 | Disposition Emission & Pipeline Routing | Needs resolved outcome for routing |
| petition-2b-1 | Dissent Recording Service | Uses dissent tracking from consensus |
| petition-2b-3 | Deadlock Detection | Handles ConsensusNotReachedError |

## Implementation Tasks

### Task 1: Create Domain Model (AC: 3)
- [ ] Create `src/domain/models/consensus_result.py`
- [ ] Define `ConsensusResult` frozen dataclass
- [ ] Define `VoteValidationResult` frozen dataclass
- [ ] Export from `src/domain/models/__init__.py`

### Task 2: Create Service Protocol (AC: 2)
- [ ] Create `src/application/ports/consensus_resolver.py`
- [ ] Define `ConsensusResolverProtocol`
- [ ] Export from `src/application/ports/__init__.py`

### Task 3: Implement Service (AC: 1, 4)
- [ ] Create `src/application/services/consensus_resolver_service.py`
- [ ] Implement `resolve()` method with supermajority algorithm
- [ ] Implement `validate_votes()` method
- [ ] Export from `src/application/services/__init__.py`

### Task 4: Create Stub (AC: 2)
- [ ] Create `src/infrastructure/stubs/consensus_resolver_stub.py`
- [ ] Implement `ConsensusResolverStub` class
- [ ] Export from `src/infrastructure/stubs/__init__.py`

### Task 5: Write Unit Tests (AC: 7)
- [ ] Create `tests/unit/domain/models/test_consensus_result.py`
- [ ] Create `tests/unit/application/services/test_consensus_resolver_service.py`
- [ ] Test unanimous 3-0 for all outcomes
- [ ] Test supermajority 2-1 with dissent tracking
- [ ] Test validation error cases
- [ ] Test determinism (same input → same output)

### Task 6: Write Integration Tests (AC: 4, 5)
- [ ] Create `tests/integration/test_consensus_resolver_integration.py`
- [ ] Test integration with DeliberationSession
- [ ] Test integration with orchestrator flow
- [ ] Verify audit trail preservation

## Definition of Done

- [ ] `ConsensusResult` domain model created
- [ ] `VoteValidationResult` domain model created
- [ ] `ConsensusResolverProtocol` defined
- [ ] `ConsensusResolverService` implements supermajority algorithm
- [ ] `ConsensusResolverStub` for testing
- [ ] Unit tests pass (>90% coverage)
- [ ] Integration tests verify orchestrator integration
- [ ] FR-11.5 satisfied: 2-of-3 supermajority required
- [ ] FR-11.6 satisfied: Valid disposition votes
- [ ] NFR-10.3 satisfied: Deterministic consensus
- [ ] Dissent tracking for audit (FR-11.8 partial)

## Test Scenarios

### Scenario 1: Unanimous ACKNOWLEDGE (3-0)
```python
session = create_session_with_votes({
    archon1: DeliberationOutcome.ACKNOWLEDGE,
    archon2: DeliberationOutcome.ACKNOWLEDGE,
    archon3: DeliberationOutcome.ACKNOWLEDGE,
})

resolver = ConsensusResolverService()
result = resolver.resolve(session)

assert result.outcome == DeliberationOutcome.ACKNOWLEDGE
assert result.is_unanimous is True
assert result.dissent_archon_id is None
assert result.vote_counts[DeliberationOutcome.ACKNOWLEDGE] == 3
```

### Scenario 2: Supermajority REFER (2-1)
```python
session = create_session_with_votes({
    archon1: DeliberationOutcome.REFER,
    archon2: DeliberationOutcome.REFER,
    archon3: DeliberationOutcome.ESCALATE,
})

result = resolver.resolve(session)

assert result.outcome == DeliberationOutcome.REFER
assert result.is_supermajority is True
assert result.dissent_archon_id == archon3
assert result.dissent_vote == DeliberationOutcome.ESCALATE
```

### Scenario 3: No Consensus (1-1-1) - Deadlock
```python
session = create_session_with_votes({
    archon1: DeliberationOutcome.ACKNOWLEDGE,
    archon2: DeliberationOutcome.REFER,
    archon3: DeliberationOutcome.ESCALATE,
})

with pytest.raises(ConsensusNotReachedError):
    resolver.resolve(session)
```

### Scenario 4: Invalid Vote Count
```python
session_with_2_votes = create_session_with_votes({
    archon1: DeliberationOutcome.ACKNOWLEDGE,
    archon2: DeliberationOutcome.ACKNOWLEDGE,
})  # Missing archon3

validation = resolver.validate_votes(session_with_2_votes)
assert validation.is_valid is False
assert "Expected 3 votes" in validation.errors[0]
```

### Scenario 5: Determinism Test (NFR-10.3)
```python
session = create_session_with_votes(votes)

result1 = resolver.resolve(session)
result2 = resolver.resolve(session)

# Same inputs must produce same outcome
assert result1.outcome == result2.outcome
assert result1.consensus_type == result2.consensus_type
assert result1.dissent_archon_id == result2.dissent_archon_id
```

## Dev Notes

### Relevant Architecture Patterns

1. **Existing consensus logic in DeliberationSession.with_outcome()**:
   - The `with_outcome()` method already computes consensus
   - This story extracts that logic into a dedicated service for:
     - Better testability
     - Richer result model
     - Separation of concerns
   - See `src/domain/models/deliberation_session.py:386-459`

2. **Frozen dataclass pattern**:
   - All domain models are frozen for immutability
   - Follow existing pattern in `DeliberationSession`, `PhaseResult`

3. **Service + Protocol + Stub pattern**:
   - Protocol in `src/application/ports/`
   - Service in `src/application/services/`
   - Stub in `src/infrastructure/stubs/`
   - Follow pattern from Stories 2A.2, 2A.3, 2A.4

### Key Files to Reference

| File | Why |
|------|-----|
| `src/domain/models/deliberation_session.py` | `with_outcome()` has existing consensus logic |
| `src/domain/errors/deliberation.py` | `ConsensusNotReachedError` already defined |
| `src/application/services/deliberation_orchestrator_service.py` | Where consensus is invoked |
| `src/infrastructure/stubs/deliberation_orchestrator_stub.py` | Stub pattern reference |

### Integration Point

The orchestrator service (Story 2A.4) calls `session.with_outcome()` which internally resolves consensus. This story provides:

1. **Explicit consensus service** for richer result tracking
2. **Validation** before resolution
3. **Dissent tracking** with audit details
4. **ConsensusResult** model for witnessing (Story 2A.7)

The integration flow:
```python
# In orchestrator (existing)
vote_result = executor.execute_vote(session, package, cross_examine_result)
votes = vote_result.phase_metadata["votes"]
session = session.with_votes(votes)

# NEW: Use consensus resolver for rich result
consensus_resolver = ConsensusResolverService()
consensus_result = consensus_resolver.resolve(session)

session = session.with_outcome()  # Still updates session state
# consensus_result now available for witnessing
```

### Project Structure Notes

- **Location:** `src/application/services/` for service, `src/domain/models/` for result model
- **Naming:** Follow `*_service.py` and `*_result.py` conventions
- **Imports:** Use absolute imports from `src.`
- **Constants:** Use existing `CONSENSUS_THRESHOLD`, `REQUIRED_ARCHON_COUNT` from `deliberation_session.py`

### References

- [Source: `src/domain/models/deliberation_session.py:386-459`] - Existing `with_outcome()` logic
- [Source: `src/domain/errors/deliberation.py`] - `ConsensusNotReachedError` definition
- [Source: `_bmad-output/planning-artifacts/petition-system-prd.md#FR-11.5`] - Supermajority requirement
- [Source: `_bmad-output/planning-artifacts/petition-system-epics.md#Story-2A.6`] - Original story definition

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
