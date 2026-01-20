# Story 2B.3: Deadlock Detection & Auto-Escalation

## Story Information

| Field | Value |
|-------|-------|
| **Story ID** | petition-2b-3 |
| **Epic** | Epic 2B: Deliberation Edge Cases & Guarantees |
| **Priority** | P0 |
| **Status** | done |
| **Created** | 2026-01-19 |

## User Story

**As a** system,
**I want** to detect deliberation deadlock after 3 rounds and auto-ESCALATE,
**So that** petitions with irreconcilable positions are elevated appropriately.

## Requirements Coverage

### Functional Requirements

| FR ID | Requirement | Priority |
|-------|-------------|----------|
| FR-11.10 | System SHALL auto-ESCALATE after 3 deliberation rounds without supermajority (deadlock) | P0 |

### Non-Functional Requirements

| NFR ID | Requirement | Target |
|--------|-------------|--------|
| NFR-10.3 | Consensus determinism | 100% reproducible given same inputs |
| NFR-10.4 | Witness completeness | 100% utterances witnessed |
| NFR-6.5 | Audit trail completeness | Complete reconstruction possible |

### Constitutional Truths

- **CT-11**: "Silent failure destroys legitimacy" - Deadlock MUST terminate
- **CT-14**: "Silence must be expensive" - Every petition terminates in witnessed fate
- **AT-1**: Every petition terminates in exactly one of Three Fates
- **AT-6**: Deliberation is collective judgment - deadlock is still collective conclusion

## Acceptance Criteria

### AC-1: Round Tracking in DeliberationSession

**Given** a deliberation enters the VOTE phase
**When** consensus is evaluated
**Then** if no supermajority exists (3-way split):
- `round_count` is incremented on the session
- A `CrossExamineRoundTriggered` event is emitted
- The session returns to CROSS_EXAMINE phase for another round
**And** if supermajority is achieved:
- `round_count` remains unchanged
- Consensus proceeds normally
**And** `round_count` starts at 1 for the first voting round

### AC-2: Deadlock Detection After 3 Rounds

**Given** a deliberation has reached `round_count` = 3
**When** consensus is evaluated and still no supermajority exists
**Then** the system detects deadlock:
- `is_deadlocked` flag is set to true on session
- No further CROSS_EXAMINE rounds are initiated
- Deliberation proceeds to auto-ESCALATE resolution

### AC-3: Auto-ESCALATE on Deadlock

**Given** a deadlock is detected (3 rounds without consensus)
**When** the deadlock handler processes the session
**Then** the deliberation terminates with outcome = ESCALATE
**And** the session transitions to `DeliberationPhase.COMPLETE`
**And** the petition state transitions: DELIBERATING -> ESCALATED
**And** a `DeadlockDetected` event is emitted with:
- `event_type`: "DeadlockDetected"
- `session_id`
- `petition_id`
- `round_count`: 3
- `final_vote_distribution` (showing the split)
- `reason`: "DEADLOCK_MAX_ROUNDS_EXCEEDED"
**And** the event is witnessed (hash-chain inclusion)

### AC-4: Vote Distribution Tracking

**Given** multiple voting rounds occur
**When** each round completes
**Then** the vote distribution for that round is recorded:
- `votes_by_round: list[dict[str, int]]` stores each round's distribution
- Each entry maps outcome to count (e.g., `{"ACKNOWLEDGE": 1, "REFER": 1, "ESCALATE": 1}`)
**And** the final `DeadlockDetected` event includes all round distributions

### AC-5: Persistent Deadlock (2-1 Repeating)

**Given** votes are consistently 2-1 with different archons dissenting each round
**When** 3 rounds complete with no supermajority (theoretically impossible with 3 archons and 2-1 always producing majority)
**Then** this scenario is recognized as:
- Actually a supermajority (2-of-3 = majority)
- NOT a deadlock
**And** this AC validates that 2-1 votes DO produce consensus
**And** deadlock only occurs with true 3-way split (1-1-1)

### AC-6: Three-Way Split Detection

**Given** 3 archons vote for 3 different outcomes (1-1-1 split)
**When** consensus is evaluated
**Then** `ConsensusNotReachedError` is raised
**And** this triggers the round-retry mechanism (AC-1)
**And** after 3 such rounds, deadlock is detected (AC-2)

### AC-7: Transcript Preservation on Deadlock

**Given** a deliberation deadlocks
**When** auto-ESCALATE is applied
**Then** all transcript content from all 3 rounds is preserved:
- Phase results for each round stored with round_number
- All utterances hash-referenced
- Transcript content available for audit
**And** the session's `phase_results` contains all rounds' data

### AC-8: Integration with Timeout Handler

**Given** a deliberation is in round 2 of CROSS_EXAMINE
**When** the timeout fires (from Story 2B.2)
**Then** the timeout takes precedence over deadlock detection
**And** the session terminates with reason "TIMEOUT_EXCEEDED" (not "DEADLOCK")
**And** `round_count` at timeout is recorded for audit

### AC-9: Unit Tests

**Given** the deadlock detection & auto-escalation components
**Then** unit tests verify:
- Round count increments on 3-way split (not on 2-1 majority)
- Deadlock detected at round 3
- Auto-ESCALATE triggers on deadlock
- Vote distribution tracked per round
- 2-1 votes produce consensus (not deadlock)
- 1-1-1 votes trigger round retry
- Transcript preservation for all rounds
- Event emission with correct payload
- Idempotent handling if already COMPLETE

### AC-10: Integration Tests

**Given** the full deadlock detection flow
**Then** integration tests verify:
- End-to-end 3-round deadlock scenario
- Database state transitions
- Event witnessing
- Round-by-round transcript preservation
- Interaction with timeout mechanism

## Technical Design

### Configuration

```python
# src/config/deliberation.py (addition to existing)

# Maximum deliberation rounds before deadlock (FR-11.10)
MAX_DELIBERATION_ROUNDS = 3

# Minimum rounds (floor - cannot be less than 1)
MIN_DELIBERATION_ROUNDS = 1
```

### Domain Events

```python
# src/domain/events/deadlock.py

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID


@dataclass(frozen=True, eq=True)
class CrossExamineRoundTriggeredEvent:
    """Event emitted when deliberation returns to CROSS_EXAMINE due to no consensus.

    This occurs when a 3-way split (1-1-1) happens in the VOTE phase.

    Attributes:
        event_type: Always "CrossExamineRoundTriggered".
        session_id: Deliberation session ID.
        petition_id: Petition ID.
        round_number: The new round being started (2 or 3).
        previous_vote_distribution: How votes were split in the previous round.
        emitted_at: Timestamp of event emission.
    """

    event_type: str = field(default="CrossExamineRoundTriggered", init=False)
    session_id: UUID
    petition_id: UUID
    round_number: int
    previous_vote_distribution: dict[str, int]
    emitted_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        """Serialize for event emission and witnessing."""
        return {
            "event_type": self.event_type,
            "session_id": str(self.session_id),
            "petition_id": str(self.petition_id),
            "round_number": self.round_number,
            "previous_vote_distribution": self.previous_vote_distribution,
            "emitted_at": self.emitted_at.isoformat(),
            "schema_version": 1,
        }


@dataclass(frozen=True, eq=True)
class DeadlockDetectedEvent:
    """Event emitted when deliberation deadlocks (FR-11.10).

    This event is witnessed in the hash chain. Deadlock triggers
    automatic ESCALATE disposition.

    Attributes:
        event_type: Always "DeadlockDetected".
        session_id: Deliberation session ID.
        petition_id: Petition ID.
        round_count: Total rounds attempted (always 3 on deadlock).
        votes_by_round: Vote distribution for each round.
        final_vote_distribution: The final round's vote split.
        reason: Always "DEADLOCK_MAX_ROUNDS_EXCEEDED".
        emitted_at: Timestamp of event emission.
    """

    event_type: str = field(default="DeadlockDetected", init=False)
    session_id: UUID
    petition_id: UUID
    round_count: int
    votes_by_round: list[dict[str, int]]
    final_vote_distribution: dict[str, int]
    reason: str = field(default="DEADLOCK_MAX_ROUNDS_EXCEEDED", init=False)
    emitted_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        """Serialize for event emission and witnessing."""
        return {
            "event_type": self.event_type,
            "session_id": str(self.session_id),
            "petition_id": str(self.petition_id),
            "round_count": self.round_count,
            "votes_by_round": self.votes_by_round,
            "final_vote_distribution": self.final_vote_distribution,
            "reason": self.reason,
            "emitted_at": self.emitted_at.isoformat(),
            "schema_version": 1,
        }
```

### Session Model Extension

```python
# Addition to src/domain/models/deliberation_session.py

# Maximum rounds before deadlock (FR-11.10)
MAX_ROUNDS = 3


@dataclass(frozen=True, eq=True)
class DeliberationSession:
    # ... existing fields ...

    round_count: int = field(default=1)  # Starts at round 1
    votes_by_round: tuple[dict[str, int], ...] = field(default_factory=tuple)
    is_deadlocked: bool = field(default=False)
    deadlock_reason: str | None = field(default=None)

    def can_retry_cross_examine(self) -> bool:
        """Check if another CROSS_EXAMINE round is allowed.

        Returns:
            True if round_count < MAX_ROUNDS, False otherwise.
        """
        return self.round_count < MAX_ROUNDS

    def with_new_round(
        self,
        previous_vote_distribution: dict[str, int],
    ) -> DeliberationSession:
        """Return session with incremented round and phase reset to CROSS_EXAMINE.

        Called when VOTE phase results in 3-way split (no consensus).

        Args:
            previous_vote_distribution: Vote distribution from failed consensus.

        Returns:
            Session in CROSS_EXAMINE phase with incremented round_count.

        Raises:
            ValueError: If already at MAX_ROUNDS.
        """
        if not self.can_retry_cross_examine():
            raise ValueError(
                f"Cannot start new round: already at MAX_ROUNDS ({MAX_ROUNDS})"
            )

        new_votes_by_round = self.votes_by_round + (previous_vote_distribution,)

        return DeliberationSession(
            session_id=self.session_id,
            petition_id=self.petition_id,
            assigned_archons=self.assigned_archons,
            current_phase=DeliberationPhase.CROSS_EXAMINE,
            round_count=self.round_count + 1,
            votes_by_round=new_votes_by_round,
            # ... copy other fields ...
        )

    def with_deadlock_outcome(
        self,
        final_vote_distribution: dict[str, int],
    ) -> DeliberationSession:
        """Return session terminated due to deadlock (FR-11.10).

        Args:
            final_vote_distribution: Vote distribution from final failed round.

        Returns:
            Session in COMPLETE phase with ESCALATE outcome and deadlock metadata.
        """
        new_votes_by_round = self.votes_by_round + (final_vote_distribution,)

        return DeliberationSession(
            session_id=self.session_id,
            petition_id=self.petition_id,
            assigned_archons=self.assigned_archons,
            current_phase=DeliberationPhase.COMPLETE,
            outcome=DeliberationOutcome.ESCALATE,
            round_count=self.round_count,
            votes_by_round=new_votes_by_round,
            is_deadlocked=True,
            deadlock_reason="DEADLOCK_MAX_ROUNDS_EXCEEDED",
            # ... copy other fields ...
        )
```

### Deadlock Handler Protocol

```python
# src/application/ports/deadlock_handler.py

from typing import Protocol
from uuid import UUID

from src.domain.events.deadlock import DeadlockDetectedEvent
from src.domain.models.deliberation_session import DeliberationSession


class DeadlockHandlerProtocol(Protocol):
    """Protocol for handling deliberation deadlock (FR-11.10).

    Implementations detect deadlock conditions (3 rounds without consensus)
    and trigger auto-ESCALATE.
    """

    def check_deadlock(
        self,
        session: DeliberationSession,
        vote_distribution: dict[str, int],
    ) -> bool:
        """Check if session is deadlocked after a voting round.

        Deadlock occurs when:
        1. No supermajority in current round (3-way split)
        2. round_count >= MAX_ROUNDS after this round

        Args:
            session: The deliberation session.
            vote_distribution: Vote distribution from current round.

        Returns:
            True if deadlocked, False if can retry or consensus reached.
        """
        ...

    async def handle_no_consensus(
        self,
        session: DeliberationSession,
        vote_distribution: dict[str, int],
    ) -> DeliberationSession:
        """Handle a voting round with no consensus.

        Either initiates a new CROSS_EXAMINE round or triggers deadlock.

        Args:
            session: The deliberation session.
            vote_distribution: Vote distribution from current round.

        Returns:
            Updated session (either in CROSS_EXAMINE for retry or COMPLETE if deadlocked).
        """
        ...

    async def process_deadlock(
        self,
        session: DeliberationSession,
        final_vote_distribution: dict[str, int],
    ) -> DeadlockDetectedEvent:
        """Process a deadlocked deliberation.

        Terminates the session with ESCALATE outcome and emits DeadlockDetectedEvent.

        Args:
            session: The deadlocked session.
            final_vote_distribution: Final round's vote distribution.

        Returns:
            The DeadlockDetectedEvent that was emitted.
        """
        ...
```

### Deadlock Handler Service

```python
# src/application/services/deadlock_handler_service.py

from uuid import UUID

import structlog

from src.application.ports.deadlock_handler import DeadlockHandlerProtocol
from src.config.deliberation import MAX_DELIBERATION_ROUNDS
from src.domain.events.deadlock import (
    CrossExamineRoundTriggeredEvent,
    DeadlockDetectedEvent,
)
from src.domain.models.deliberation_session import (
    DeliberationOutcome,
    DeliberationSession,
)

logger = structlog.get_logger(__name__)


def has_supermajority(vote_distribution: dict[str, int], threshold: int = 2) -> bool:
    """Check if any outcome has supermajority votes.

    Args:
        vote_distribution: Map of outcome to vote count.
        threshold: Minimum votes for majority (default 2 for 2-of-3).

    Returns:
        True if any outcome has >= threshold votes.
    """
    return any(count >= threshold for count in vote_distribution.values())


class DeadlockHandlerService(DeadlockHandlerProtocol):
    """Service for handling deliberation deadlock (FR-11.10).

    Detects 3-way splits, manages round retries, and triggers
    auto-ESCALATE when deadlock occurs.

    Constitutional Constraints:
    - CT-11: Silent failure destroys legitimacy - deadlock MUST terminate
    - CT-14: Silence is expensive - petition terminates in witnessed fate
    - AT-1: Every petition terminates in exactly one of Three Fates
    """

    def __init__(
        self,
        session_repository: SessionRepositoryProtocol,
        petition_repository: PetitionRepositoryProtocol,
        event_emitter: EventEmitterProtocol,
        max_rounds: int = MAX_DELIBERATION_ROUNDS,
    ) -> None:
        """Initialize the deadlock handler service."""
        self._session_repository = session_repository
        self._petition_repository = petition_repository
        self._event_emitter = event_emitter
        self._max_rounds = max_rounds
        self._log = logger.bind(component="deadlock_handler")

    def check_deadlock(
        self,
        session: DeliberationSession,
        vote_distribution: dict[str, int],
    ) -> bool:
        """Check if session is deadlocked (AC-2, AC-5, AC-6).

        A session is deadlocked when:
        1. No supermajority in vote_distribution (3-way split)
        2. This is round MAX_ROUNDS (no more retries allowed)

        Note: 2-1 votes always produce supermajority, so deadlock
        only occurs with true 1-1-1 splits across 3 rounds.

        Args:
            session: The deliberation session.
            vote_distribution: Vote distribution from current round.

        Returns:
            True if deadlocked, False otherwise.
        """
        # If there's a supermajority, no deadlock possible
        if has_supermajority(vote_distribution):
            return False

        # No supermajority = 3-way split (1-1-1)
        # Deadlock if this is the final allowed round
        return session.round_count >= self._max_rounds

    async def handle_no_consensus(
        self,
        session: DeliberationSession,
        vote_distribution: dict[str, int],
    ) -> DeliberationSession:
        """Handle a voting round with no supermajority (AC-1, AC-2, AC-3).

        Either:
        1. Starts a new CROSS_EXAMINE round (if rounds remaining)
        2. Processes deadlock (if at max rounds)

        Args:
            session: The deliberation session.
            vote_distribution: Vote distribution from current round.

        Returns:
            Updated session.
        """
        log = self._log.bind(
            session_id=str(session.session_id),
            petition_id=str(session.petition_id),
            round_count=session.round_count,
            vote_distribution=vote_distribution,
        )

        if self.check_deadlock(session, vote_distribution):
            log.info("deadlock_detected")
            await self.process_deadlock(session, vote_distribution)
            return session.with_deadlock_outcome(vote_distribution)

        # Not deadlocked - start new round
        log.info("starting_new_cross_examine_round")

        updated_session = session.with_new_round(vote_distribution)
        await self._session_repository.update(updated_session)

        # Emit round triggered event
        round_event = CrossExamineRoundTriggeredEvent(
            session_id=session.session_id,
            petition_id=session.petition_id,
            round_number=updated_session.round_count,
            previous_vote_distribution=vote_distribution,
        )
        await self._event_emitter.emit(round_event)

        log.info(
            "cross_examine_round_triggered",
            new_round=updated_session.round_count,
        )

        return updated_session

    async def process_deadlock(
        self,
        session: DeliberationSession,
        final_vote_distribution: dict[str, int],
    ) -> DeadlockDetectedEvent:
        """Process a deadlocked deliberation (AC-3, AC-4).

        Terminates the session with ESCALATE outcome per FR-11.10.

        Args:
            session: The deadlocked session.
            final_vote_distribution: Final round's vote distribution.

        Returns:
            The DeadlockDetectedEvent that was emitted.
        """
        log = self._log.bind(
            session_id=str(session.session_id),
            petition_id=str(session.petition_id),
            round_count=session.round_count,
        )

        # Build complete votes history including final round
        all_votes = list(session.votes_by_round) + [final_vote_distribution]

        # Update session with deadlock outcome
        updated_session = session.with_deadlock_outcome(final_vote_distribution)
        await self._session_repository.update(updated_session)

        # Update petition state: DELIBERATING -> ESCALATED
        await self._petition_repository.transition_to_escalated(
            session.petition_id,
            reason="DELIBERATION_DEADLOCK",
        )

        # Emit deadlock event
        event = DeadlockDetectedEvent(
            session_id=session.session_id,
            petition_id=session.petition_id,
            round_count=session.round_count,
            votes_by_round=all_votes,
            final_vote_distribution=final_vote_distribution,
        )
        await self._event_emitter.emit(event)

        log.info(
            "deadlock_processed",
            outcome="ESCALATE",
            total_rounds=session.round_count,
        )

        return event
```

### Integration with Consensus Resolver

```python
# Addition to src/application/services/consensus_resolver_service.py

# In resolve_consensus method, the ConsensusNotReachedError is raised
# when there's no supermajority. The orchestrator catches this and
# invokes the deadlock handler:

# In DeliberationOrchestratorService.process_vote_phase():
try:
    consensus_result = self._consensus_resolver.resolve_consensus(session, votes)
    # Consensus reached - proceed to completion
    ...
except ConsensusNotReachedError:
    # No consensus - delegate to deadlock handler
    updated_session = await self._deadlock_handler.handle_no_consensus(
        session,
        vote_distribution,
    )
    if updated_session.is_deadlocked:
        # Deadlock - session already in COMPLETE state with ESCALATE
        return updated_session
    else:
        # New round started - continue deliberation from CROSS_EXAMINE
        return updated_session
```

### Database Migration

```sql
-- migrations/019_add_round_tracking.sql

-- Add round tracking columns to deliberation_sessions (FR-11.10)
ALTER TABLE deliberation_sessions
ADD COLUMN round_count INTEGER NOT NULL DEFAULT 1,
ADD COLUMN votes_by_round JSONB NOT NULL DEFAULT '[]'::jsonb,
ADD COLUMN is_deadlocked BOOLEAN NOT NULL DEFAULT false,
ADD COLUMN deadlock_reason VARCHAR(100);

-- Constraint: round_count must be >= 1 and <= MAX_ROUNDS
ALTER TABLE deliberation_sessions
ADD CONSTRAINT check_round_count_bounds CHECK (
    round_count >= 1 AND round_count <= 3
);

-- Index for querying deadlocked sessions
CREATE INDEX idx_deliberation_sessions_deadlocked
ON deliberation_sessions(is_deadlocked)
WHERE is_deadlocked = true;
```

## Dependencies

### Upstream Dependencies (Required Before This Story)

| Story ID | Name | Status | Why Needed |
|----------|------|--------|------------|
| petition-2a-1 | Deliberation Session Domain Model | DONE | Session model to extend |
| petition-2a-6 | Supermajority Consensus Resolution | DONE | ConsensusResolverService, ConsensusNotReachedError |
| petition-2b-2 | Deliberation Timeout Enforcement | ready-for-dev | Must integrate with timeout handling |

### Downstream Dependencies (Blocked By This Story)

| Story ID | Name | Why Blocked |
|----------|------|-------------|
| petition-2b-6 | Audit Trail Reconstruction | Needs deadlock events and round history |

## Implementation Tasks

### Task 1: Add Configuration Constants (AC: 5)
- [ ] Add `MAX_DELIBERATION_ROUNDS` to `src/config/deliberation.py`
- [ ] Add constant to existing `DeliberationConfig` or create new constant

### Task 2: Create Domain Events (AC: 1, 3, 4)
- [ ] Create `src/domain/events/deadlock.py`
- [ ] Define `CrossExamineRoundTriggeredEvent`
- [ ] Define `DeadlockDetectedEvent`
- [ ] Export from `src/domain/events/__init__.py`

### Task 3: Extend DeliberationSession Model (AC: 1, 4, 7)
- [ ] Add `round_count: int = 1` field
- [ ] Add `votes_by_round: tuple[dict[str, int], ...]` field
- [ ] Add `is_deadlocked: bool` field
- [ ] Add `deadlock_reason: str | None` field
- [ ] Implement `can_retry_cross_examine()` method
- [ ] Implement `with_new_round()` method
- [ ] Implement `with_deadlock_outcome()` method

### Task 4: Create Deadlock Handler Protocol (AC: 2, 3, 6)
- [ ] Create `src/application/ports/deadlock_handler.py`
- [ ] Define `DeadlockHandlerProtocol`
- [ ] Export from `src/application/ports/__init__.py`

### Task 5: Implement Deadlock Handler Service (AC: 1, 2, 3, 4, 6)
- [ ] Create `src/application/services/deadlock_handler_service.py`
- [ ] Implement `has_supermajority()` helper function
- [ ] Implement `check_deadlock()` method
- [ ] Implement `handle_no_consensus()` method
- [ ] Implement `process_deadlock()` method
- [ ] Add structured logging

### Task 6: Create Stub Implementation
- [ ] Create `src/infrastructure/stubs/deadlock_handler_stub.py`
- [ ] Implement `DeadlockHandlerStub`
- [ ] Export from `src/infrastructure/stubs/__init__.py`

### Task 7: Create Database Migration (AC: 1, 4)
- [ ] Create `migrations/019_add_round_tracking.sql`
- [ ] Add round_count, votes_by_round columns
- [ ] Add is_deadlocked, deadlock_reason columns
- [ ] Add constraints and indexes

### Task 8: Integrate with Orchestrator (AC: 1, 2, 8)
- [ ] Update orchestrator to catch `ConsensusNotReachedError`
- [ ] Call `deadlock_handler.handle_no_consensus()` on no consensus
- [ ] Ensure timeout takes precedence over deadlock (AC-8)

### Task 9: Write Unit Tests (AC: 9)
- [ ] Create `tests/unit/domain/events/test_deadlock_events.py`
- [ ] Create `tests/unit/application/services/test_deadlock_handler_service.py`
- [ ] Test round increment on 3-way split
- [ ] Test deadlock detection at round 3
- [ ] Test auto-ESCALATE on deadlock
- [ ] Test 2-1 votes produce consensus (NOT deadlock)
- [ ] Test 1-1-1 votes trigger round retry
- [ ] Test event emission
- [ ] Test session model extensions

### Task 10: Write Integration Tests (AC: 10)
- [ ] Create `tests/integration/test_deadlock_detection_integration.py`
- [ ] Test end-to-end 3-round deadlock scenario
- [ ] Test database state transitions
- [ ] Test event witnessing
- [ ] Test interaction with timeout mechanism (AC-8)

## Definition of Done

- [ ] Configuration constants added
- [ ] `CrossExamineRoundTriggeredEvent` and `DeadlockDetectedEvent` defined
- [ ] `DeliberationSession` extended with round tracking fields
- [ ] `DeadlockHandlerProtocol` defined
- [ ] `DeadlockHandlerService` implements all methods
- [ ] Stub implementation for testing
- [ ] Migration 019 created and tested
- [ ] Orchestrator integration complete
- [ ] Unit tests pass (>90% coverage)
- [ ] Integration tests verify end-to-end flow
- [ ] FR-11.10 satisfied: 3 rounds without consensus triggers auto-ESCALATE
- [ ] 2-1 votes correctly produce consensus (no false deadlock)
- [ ] Round history preserved for audit (AC-4, AC-7)

## Test Scenarios

### Scenario 1: Three-Way Split Triggers New Round
```python
# Setup: First vote round with 1-1-1 split
session = create_session_in_vote_phase(round_count=1)
vote_distribution = {"ACKNOWLEDGE": 1, "REFER": 1, "ESCALATE": 1}

# Handle no consensus
updated_session = await deadlock_handler.handle_no_consensus(
    session,
    vote_distribution,
)

# Verify new round started
assert updated_session.round_count == 2
assert updated_session.current_phase == DeliberationPhase.CROSS_EXAMINE
assert vote_distribution in updated_session.votes_by_round
```

### Scenario 2: Deadlock After 3 Rounds
```python
# Setup: Third vote round with 1-1-1 split
session = create_session_in_vote_phase(
    round_count=3,
    votes_by_round=[
        {"ACKNOWLEDGE": 1, "REFER": 1, "ESCALATE": 1},
        {"ACKNOWLEDGE": 1, "REFER": 1, "ESCALATE": 1},
    ],
)
vote_distribution = {"ACKNOWLEDGE": 1, "REFER": 1, "ESCALATE": 1}

# Handle no consensus -> deadlock
updated_session = await deadlock_handler.handle_no_consensus(
    session,
    vote_distribution,
)

# Verify deadlock processed
assert updated_session.is_deadlocked is True
assert updated_session.current_phase == DeliberationPhase.COMPLETE
assert updated_session.outcome == DeliberationOutcome.ESCALATE
assert len(updated_session.votes_by_round) == 3

# Verify petition escalated
petition = await petition_repo.get(session.petition_id)
assert petition.state == PetitionState.ESCALATED
```

### Scenario 3: 2-1 Vote Produces Consensus (Not Deadlock)
```python
# Setup: Vote round with 2-1 split (this IS consensus)
session = create_session_in_vote_phase(round_count=1)
vote_distribution = {"ACKNOWLEDGE": 2, "REFER": 1}

# Check if deadlock
is_deadlocked = deadlock_handler.check_deadlock(session, vote_distribution)

# 2-1 is NOT deadlock (it's supermajority)
assert is_deadlocked is False

# The consensus resolver handles this case normally
consensus = consensus_resolver.resolve_consensus(session, votes)
assert consensus.winning_outcome == "ACKNOWLEDGE"
```

### Scenario 4: DeadlockDetected Event Payload
```python
# Setup: Deadlock scenario
session = create_session_for_deadlock()
final_distribution = {"ACKNOWLEDGE": 1, "REFER": 1, "ESCALATE": 1}

# Process deadlock
event = await deadlock_handler.process_deadlock(session, final_distribution)

# Verify event payload
assert event.event_type == "DeadlockDetected"
assert event.round_count == 3
assert event.reason == "DEADLOCK_MAX_ROUNDS_EXCEEDED"
assert len(event.votes_by_round) == 3
assert event.final_vote_distribution == final_distribution
```

### Scenario 5: Timeout Precedence Over Deadlock
```python
# Setup: Session in round 2, timeout fires
session = create_session_with_timeout_job(round_count=2)

# Timeout handler processes (from Story 2B.2)
timeout_event = await timeout_handler.handle_timeout(
    session.session_id,
    session.petition_id,
)

# Verify timeout took precedence
assert timeout_event.reason == "TIMEOUT_EXCEEDED"
updated_session = await session_repo.get(session.session_id)
assert not updated_session.is_deadlocked  # Timeout, not deadlock
```

## Dev Notes

### Relevant Architecture Patterns

1. **Consensus resolution flow**:
   - `ConsensusResolverService.resolve_consensus()` raises `ConsensusNotReachedError` for 3-way splits
   - Orchestrator catches this and delegates to `DeadlockHandlerService`
   - Pattern: Exception-based flow control for edge cases

2. **Session mutation pattern**:
   - Follow immutable pattern: `with_*()` methods return new session instances
   - Existing: `with_outcome()`, `with_timeout_outcome()`
   - New: `with_new_round()`, `with_deadlock_outcome()`

3. **Event emission pattern**:
   - Follow `DeliberationTimeoutEvent`, `DissentRecordedEvent` patterns
   - Events witnessed in hash chain
   - Frozen dataclass with `to_dict()`

4. **Idempotent handling**:
   - Check session state before processing
   - If already COMPLETE, no-op

### Key Files to Reference

| File | Why |
|------|-----|
| `src/domain/models/deliberation_session.py` | Session model to extend |
| `src/application/services/consensus_resolver_service.py` | ConsensusNotReachedError integration |
| `src/domain/errors/deliberation.py` | ConsensusNotReachedError definition |
| `src/application/services/deliberation_timeout_handler_service.py` | Similar pattern (Story 2B.2) |
| `_bmad-output/implementation-artifacts/stories/petition-2b-2-*.md` | Reference story pattern |

### Integration Points

1. **Orchestrator integration** (VOTE phase):
   ```python
   # In DeliberationOrchestratorService.process_vote_phase()
   try:
       consensus_result = self._consensus_resolver.resolve_consensus(session, votes)
       # Proceed to complete deliberation with consensus
       ...
   except ConsensusNotReachedError:
       # Delegate to deadlock handler
       updated_session = await self._deadlock_handler.handle_no_consensus(
           session,
           vote_distribution,
       )
       if updated_session.is_deadlocked:
           # Deadlock - already ESCALATED, emit completion event
           ...
       else:
           # New round started - return to CROSS_EXAMINE
           ...
   ```

2. **Timeout interaction** (AC-8):
   - Timeout job scheduled on session start (Story 2B.2)
   - If timeout fires during round 2/3, timeout takes precedence
   - `handle_timeout()` checks session state first - if COMPLETE (from deadlock), no-op

### Mathematical Note on Deadlock

With 3 archons and 3 possible outcomes:
- **2-1 split**: Always produces consensus (2 >= SUPERMAJORITY_THRESHOLD of 2)
- **3-way split (1-1-1)**: No consensus possible

True deadlock (requiring 3 rounds) only occurs if archons vote 1-1-1 three times in a row. This is rare but must be handled per FR-11.10.

### Project Structure Notes

- **Location**: Follow existing patterns:
  - Events: `src/domain/events/deadlock.py`
  - Protocol: `src/application/ports/deadlock_handler.py`
  - Service: `src/application/services/deadlock_handler_service.py`
  - Stub: `src/infrastructure/stubs/deadlock_handler_stub.py`
- **Naming**: `deadlock_*` prefix for deadlock-specific, `round_*` for round tracking
- **Imports**: Absolute imports from `src.`

### References

- [Source: `_bmad-output/planning-artifacts/petition-system-prd.md#FR-11.10`] - Deadlock requirement
- [Source: `_bmad-output/planning-artifacts/petition-system-prd.md#Section-13A.5`] - Timeout & deadlock handling
- [Source: `_bmad-output/planning-artifacts/petition-system-epics.md#Story-2B.3`] - Original story definition
- [Source: `src/application/services/consensus_resolver_service.py`] - ConsensusNotReachedError integration
- [Source: `src/domain/errors/deliberation.py`] - Error class definition

## Documentation Checklist

- [ ] Architecture docs updated (if patterns/structure changed)
- [ ] API docs updated (if endpoints/contracts changed)
- [ ] README updated (if setup/usage changed)
- [ ] Inline comments added for complex logic
- [x] N/A - Internal service, extends existing deliberation infrastructure

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List
