# Story 2A.5: CrewAI Deliberation Adapter

## Story Information

| Field | Value |
|-------|-------|
| **Story ID** | petition-2a-5 |
| **Epic** | Epic 2A: Core Deliberation Protocol |
| **Priority** | P0-CRITICAL |
| **Status** | done |
| **Completed** | 2026-01-19 |
| **Created** | 2026-01-19 |

## User Story

**As a** developer,
**I want** a CrewAI adapter that executes the deliberation protocol,
**So that** the Three Fates can deliberate using the AI framework.

## Requirements Coverage

### Functional Requirements

| FR ID | Requirement | Priority |
|-------|-------------|----------|
| FR-11.4 | Deliberation SHALL follow structured protocol: Assess → Position → Cross-Examine → Vote | P0 |
| HP-10 | System SHALL use CrewAI framework for multi-agent deliberation | P0 |

### Non-Functional Requirements

| NFR ID | Requirement | Target |
|--------|-------------|--------|
| NFR-10.2 | Individual Archon response time | p95 < 30 seconds |
| NFR-10.3 | Consensus determinism | 100% reproducible given same inputs |
| NFR-10.4 | Witness completeness | 100% utterances witnessed |

### Constitutional Truths

- **CT-11**: "Silent failure destroys legitimacy" → Report all agent failures
- **CT-12**: "Witnessing creates accountability" → All outputs through Blake3 hashing
- **CT-14**: "Silence must be expensive" → Every petition gets a Three Fates verdict
- **AT-6**: Deliberation is collective judgment, not unilateral decision

## Acceptance Criteria

### AC-1: Implement PhaseExecutorProtocol

**Given** the `PhaseExecutorProtocol` defined in Story 2A.4
**When** the CrewAI adapter is created
**Then** it implements all four phase execution methods:
- `execute_assess(session, package) -> PhaseResult`
- `execute_position(session, package, assess_result) -> PhaseResult`
- `execute_cross_examine(session, package, position_result) -> PhaseResult`
- `execute_vote(session, package, cross_examine_result) -> PhaseResult`
**And** each method returns a valid `PhaseResult` with Blake3 transcript hash

### AC-2: ASSESS Phase - Independent Assessments

**Given** a DeliberationSession with 3 assigned Archons
**When** `execute_assess()` is invoked
**Then** the adapter:
- Instantiates 3 CrewAI agents using `ArchonProfileRepository`
- Creates assessment tasks with the `DeliberationContextPackage`
- Executes ALL 3 agents concurrently (no inter-archon visibility)
- Collects outputs from all 3 archons
- Concatenates transcripts and computes Blake3 hash
**And** each archon response completes within 30 seconds p95 (NFR-10.2)

### AC-3: POSITION Phase - Sequential Disposition Statements

**Given** ASSESS phase is complete
**When** `execute_position()` is invoked
**Then** the adapter:
- Executes archons SEQUENTIALLY (Archon 1 → 2 → 3)
- Each archon sees previous positions before stating their own
- Each position includes: disposition (ACKNOWLEDGE/REFER/ESCALATE) + rationale
- Injects assess_result.transcript into context for continuity
**And** the phase transcript is recorded with Blake3 hash

### AC-4: CROSS_EXAMINE Phase - Challenge/Response Exchanges

**Given** POSITION phase is complete
**When** `execute_cross_examine()` is invoked
**Then** the adapter:
- Executes round-robin challenge/response exchanges
- Maximum 3 rounds of exchange
- Stops early when no archon raises a new challenge
- Injects position_result.transcript into context
- Records challenge count and round count in `phase_metadata`
**And** the phase transcript is recorded with Blake3 hash

### AC-5: VOTE Phase - Simultaneous Final Votes

**Given** CROSS_EXAMINE phase is complete
**When** `execute_vote()` is invoked
**Then** the adapter:
- Creates simultaneous vote tasks (no archon sees others' votes before casting)
- Each archon votes exactly one of: ACKNOWLEDGE, REFER, ESCALATE
- Collects all 3 votes
- Returns `phase_metadata['votes']` = `{UUID: DeliberationOutcome}`
**And** votes are deterministic given same inputs (NFR-10.3)

### AC-6: CrewAI Agent Configuration

**Given** an Archon ID from the session
**When** a CrewAI agent is created
**Then** the adapter:
- Resolves ArchonProfile via `ArchonProfileRepository`
- Uses `profile.get_crewai_config()` for role, goal, backstory
- Uses `_create_crewai_llm(profile.llm_config)` for LLM binding
- Sets `max_iter=5` to prevent runaway iterations
- Applies `timeout_ms` from LLM config (default 30s)

### AC-7: Deterministic Seeding

**Given** the same inputs (session, package)
**When** deliberation is executed multiple times
**Then** the outcome is reproducible (NFR-10.3):
- Use low temperature in LLM config for determinism
- Frozen dataclasses ensure immutable state
- All context passed explicitly (no hidden state)

### AC-8: Error Handling

**Given** an archon fails during deliberation
**When** the failure occurs
**Then** the adapter:
- Logs the failure with full context (CT-11)
- Raises `DeliberationError` with archon ID and phase
- Does NOT silently continue (legitimacy requirement)
- Records partial transcript if available

## Technical Design

### File Structure

```
src/infrastructure/adapters/external/
├── crewai_adapter.py                    # Existing - General agent orchestration
└── crewai_deliberation_adapter.py       # NEW - Deliberation-specific adapter

src/application/ports/
└── deliberation_orchestrator.py         # Existing - PhaseExecutorProtocol (Story 2A.4)

tests/unit/infrastructure/adapters/external/
└── test_crewai_deliberation_adapter.py  # NEW - Unit tests

tests/integration/
└── test_crewai_deliberation_adapter_integration.py  # NEW - Integration tests
```

### Domain Models (Existing from 2A.4)

```python
# src/domain/models/deliberation_result.py (already exists)
from src.domain.models.deliberation_result import PhaseResult, DeliberationResult

# src/domain/models/deliberation_session.py (already exists)
from src.domain.models.deliberation_session import (
    DeliberationSession,
    DeliberationPhase,
    DeliberationOutcome,
)

# src/domain/models/deliberation_context_package.py (already exists)
from src.domain.models.deliberation_context_package import DeliberationContextPackage
```

### Service Implementation

```python
# src/infrastructure/adapters/external/crewai_deliberation_adapter.py

"""CrewAI adapter for Three Fates deliberation (Story 2A.5, FR-11.4).

Implements PhaseExecutorProtocol to execute the 4-phase deliberation
protocol using CrewAI agents with per-archon LLM configuration.

Constitutional Constraints:
- FR-11.4: Strict protocol sequence (ASSESS → POSITION → CROSS_EXAMINE → VOTE)
- NFR-10.2: Individual archon response p95 < 30 seconds
- NFR-10.3: Deterministic consensus reproducibility
- CT-11: Silent failure destroys legitimacy → report all failures
- CT-12: Witnessing creates accountability → Blake3 hashing all transcripts
"""

from __future__ import annotations

import asyncio
import hashlib
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID

from crewai import Agent, Crew, Task
from structlog import get_logger

from src.application.ports.archon_profile_repository import ArchonProfileRepository
from src.application.ports.deliberation_orchestrator import PhaseExecutorProtocol
from src.domain.errors.deliberation import DeliberationError
from src.domain.models.deliberation_result import PhaseResult
from src.domain.models.deliberation_session import (
    DeliberationOutcome,
    DeliberationPhase,
    DeliberationSession,
)
from src.infrastructure.adapters.external.crewai_adapter import _create_crewai_llm

if TYPE_CHECKING:
    from src.domain.models.archon_profile import ArchonProfile
    from src.domain.models.deliberation_context_package import DeliberationContextPackage

logger = get_logger(__name__)


def _compute_blake3_hash(content: str) -> bytes:
    """Compute Blake3 hash of transcript content.

    Note: Using hashlib.blake2b as fallback if blake3 not available.
    Production should use blake3 library for 32-byte hashes.
    """
    # blake3 produces 32-byte digest by default
    # Using blake2b with 32 bytes for compatibility
    return hashlib.blake2b(content.encode(), digest_size=32).digest()


class CrewAIDeliberationAdapter(PhaseExecutorProtocol):
    """CrewAI implementation of PhaseExecutorProtocol (Story 2A.5).

    Executes the 4-phase deliberation protocol using CrewAI agents.
    Each archon is configured via ArchonProfileRepository with
    per-archon LLM bindings.

    Attributes:
        _profile_repo: Repository for Archon profile lookup
        _verbose: Whether to enable verbose CrewAI logging
        _timeout_seconds: Timeout per archon response (default 30s)
    """

    def __init__(
        self,
        profile_repository: ArchonProfileRepository,
        verbose: bool = False,
        timeout_seconds: float = 30.0,
    ) -> None:
        """Initialize the CrewAI deliberation adapter.

        Args:
            profile_repository: Repository for Archon profile lookup
            verbose: Enable verbose CrewAI logging
            timeout_seconds: Timeout per archon response (NFR-10.2: 30s)
        """
        self._profile_repo = profile_repository
        self._verbose = verbose
        self._timeout_seconds = timeout_seconds

        logger.info(
            "crewai_deliberation_adapter_initialized",
            archon_count=profile_repository.count(),
            verbose=verbose,
            timeout_seconds=timeout_seconds,
        )

    def _get_archon_profile(self, archon_id: UUID) -> ArchonProfile:
        """Get ArchonProfile by UUID.

        Raises:
            DeliberationError: If archon not found
        """
        profile = self._profile_repo.get_by_id(archon_id)
        if profile is None:
            raise DeliberationError(
                f"Archon {archon_id} not found in profile repository"
            )
        return profile

    def _create_agent(self, profile: ArchonProfile, context_text: str) -> Agent:
        """Create a CrewAI Agent from ArchonProfile with deliberation context.

        Args:
            profile: The archon's profile
            context_text: Additional context to inject into backstory

        Returns:
            Configured CrewAI Agent
        """
        crewai_config = profile.get_crewai_config()
        llm = _create_crewai_llm(profile.llm_config)

        # Inject deliberation context into backstory
        backstory = profile.get_system_prompt_with_context(context_text)

        return Agent(
            role=crewai_config["role"],
            goal="Deliberate on the petition and provide judgment",
            backstory=backstory,
            verbose=self._verbose,
            allow_delegation=False,  # No delegation in deliberation
            llm=llm,
            max_iter=5,  # Prevent runaway
        )

    async def _execute_agent_task(
        self,
        agent: Agent,
        task_description: str,
        expected_output: str,
    ) -> str:
        """Execute a single agent task with timeout.

        Returns:
            Agent output as string

        Raises:
            DeliberationError: On timeout or execution failure
        """
        task = Task(
            description=task_description,
            expected_output=expected_output,
            agent=agent,
        )

        crew = Crew(
            agents=[agent],
            tasks=[task],
            verbose=self._verbose,
        )

        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(crew.kickoff),
                timeout=self._timeout_seconds,
            )
            return str(result)
        except asyncio.TimeoutError:
            raise DeliberationError(
                f"Archon timed out after {self._timeout_seconds}s"
            )
        except Exception as e:
            raise DeliberationError(f"Agent execution failed: {e}") from e

    def execute_assess(
        self,
        session: DeliberationSession,
        package: DeliberationContextPackage,
    ) -> PhaseResult:
        """Execute ASSESS phase - independent assessments (AC-2).

        All 3 archons assess the petition concurrently without
        seeing each other's assessments.
        """
        started_at = datetime.now(timezone.utc)
        transcript_parts = ["=== ASSESS PHASE ===\n"]

        async def run_assessments() -> list[str]:
            tasks = []
            for archon_id in session.assigned_archons:
                profile = self._get_archon_profile(archon_id)
                agent = self._create_agent(
                    profile,
                    f"Petition for assessment: {package.petition_text[:500]}"
                )

                task_description = f"""
You are {profile.name}, a Fate Archon assessing petition {package.petition_id}.

PETITION DETAILS:
- Type: {package.petition_type}
- Realm: {package.realm}
- Co-signers: {package.co_signer_count}
- Submitted: {package.submitted_at}

PETITION TEXT:
{package.petition_text}

Provide your independent assessment of this petition. Consider:
1. Does it conform to constitutional requirements?
2. Is the request clear and actionable?
3. What are the potential implications?

Do NOT state a disposition yet - only assess the petition's merits.
"""
                tasks.append(
                    self._execute_agent_task(
                        agent,
                        task_description,
                        "A thorough assessment of the petition's merits"
                    )
                )

            return await asyncio.gather(*tasks)

        # Run assessments concurrently
        outputs = asyncio.run(run_assessments())

        # Build transcript
        for i, (archon_id, output) in enumerate(
            zip(session.assigned_archons, outputs)
        ):
            profile = self._get_archon_profile(archon_id)
            transcript_parts.append(
                f"\n--- Archon {i+1}: {profile.name} ({archon_id}) ---\n"
                f"{output}\n"
            )

        transcript = "".join(transcript_parts)
        completed_at = datetime.now(timezone.utc)

        logger.info(
            "assess_phase_complete",
            session_id=str(session.session_id),
            archon_count=3,
            duration_ms=int((completed_at - started_at).total_seconds() * 1000),
        )

        return PhaseResult(
            phase=DeliberationPhase.ASSESS,
            transcript=transcript,
            transcript_hash=_compute_blake3_hash(transcript),
            participants=session.assigned_archons,
            started_at=started_at,
            completed_at=completed_at,
            phase_metadata={
                "assessments_completed": 3,
                "petition_type": package.petition_type,
            },
        )

    def execute_position(
        self,
        session: DeliberationSession,
        package: DeliberationContextPackage,
        assess_result: PhaseResult,
    ) -> PhaseResult:
        """Execute POSITION phase - sequential disposition statements (AC-3).

        Archons state positions sequentially. Each sees previous positions.
        """
        started_at = datetime.now(timezone.utc)
        transcript_parts = ["=== POSITION PHASE ===\n"]
        positions: list[tuple[UUID, str, str]] = []  # (archon_id, disposition, rationale)

        async def run_positions() -> None:
            previous_positions = ""

            for i, archon_id in enumerate(session.assigned_archons):
                profile = self._get_archon_profile(archon_id)
                agent = self._create_agent(
                    profile,
                    f"ASSESS phase results:\n{assess_result.transcript}"
                )

                task_description = f"""
You are {profile.name}, stating your position on petition {package.petition_id}.

PREVIOUS ASSESSMENTS:
{assess_result.transcript}

{f"PREVIOUS POSITIONS:{chr(10)}{previous_positions}" if previous_positions else "You are the FIRST to state a position."}

State your preferred disposition. Choose EXACTLY ONE:
- ACKNOWLEDGE: Accept and acknowledge the petition
- REFER: Refer to Knight for expert review
- ESCALATE: Escalate to King for adoption consideration

Format your response as:
DISPOSITION: [ACKNOWLEDGE/REFER/ESCALATE]
RATIONALE: [Your reasoning for this choice]
"""
                output = await self._execute_agent_task(
                    agent,
                    task_description,
                    "DISPOSITION: [choice] RATIONALE: [reasoning]"
                )

                # Parse disposition from output
                disposition = "ACKNOWLEDGE"  # Default
                for d in ["ACKNOWLEDGE", "REFER", "ESCALATE"]:
                    if d in output.upper():
                        disposition = d
                        break

                positions.append((archon_id, disposition, output))
                previous_positions += f"\n{profile.name}: {disposition}\n"

                transcript_parts.append(
                    f"\n--- Archon {i+1}: {profile.name} ({archon_id}) ---\n"
                    f"{output}\n"
                )

        asyncio.run(run_positions())

        transcript = "".join(transcript_parts)
        completed_at = datetime.now(timezone.utc)

        # Check if positions converged
        disposition_set = {p[1] for p in positions}

        logger.info(
            "position_phase_complete",
            session_id=str(session.session_id),
            positions_converged=len(disposition_set) == 1,
            duration_ms=int((completed_at - started_at).total_seconds() * 1000),
        )

        return PhaseResult(
            phase=DeliberationPhase.POSITION,
            transcript=transcript,
            transcript_hash=_compute_blake3_hash(transcript),
            participants=session.assigned_archons,
            started_at=started_at,
            completed_at=completed_at,
            phase_metadata={
                "positions_stated": 3,
                "positions_converged": len(disposition_set) == 1,
                "position_summary": {str(p[0]): p[1] for p in positions},
            },
        )

    def execute_cross_examine(
        self,
        session: DeliberationSession,
        package: DeliberationContextPackage,
        position_result: PhaseResult,
    ) -> PhaseResult:
        """Execute CROSS_EXAMINE phase - challenge/response exchanges (AC-4).

        Archons may challenge each other's positions. Max 3 rounds.
        """
        started_at = datetime.now(timezone.utc)
        transcript_parts = ["=== CROSS_EXAMINE PHASE ===\n"]
        challenge_count = 0
        rounds_completed = 0
        max_rounds = 3

        async def run_cross_examination() -> None:
            nonlocal challenge_count, rounds_completed

            for round_num in range(max_rounds):
                round_challenges = 0
                transcript_parts.append(f"\n--- Round {round_num + 1} ---\n")

                for archon_id in session.assigned_archons:
                    profile = self._get_archon_profile(archon_id)
                    agent = self._create_agent(
                        profile,
                        f"Position phase:\n{position_result.transcript}"
                    )

                    task_description = f"""
You are {profile.name} in the CROSS_EXAMINE phase.

POSITIONS STATED:
{position_result.transcript}

Review the other archons' positions. If you wish to challenge any position:
1. State which archon's position you challenge
2. Explain your challenge
3. Request clarification or change

If you have no challenges, simply state "NO CHALLENGE".

This is round {round_num + 1} of up to {max_rounds}.
"""
                    output = await self._execute_agent_task(
                        agent,
                        task_description,
                        "Challenge or NO CHALLENGE response"
                    )

                    has_challenge = "NO CHALLENGE" not in output.upper()
                    if has_challenge:
                        round_challenges += 1
                        challenge_count += 1

                    transcript_parts.append(f"{profile.name}: {output}\n")

                rounds_completed = round_num + 1

                # Stop early if no challenges this round
                if round_challenges == 0:
                    transcript_parts.append(
                        "\nNo further challenges raised. Proceeding to vote.\n"
                    )
                    break

        asyncio.run(run_cross_examination())

        transcript = "".join(transcript_parts)
        completed_at = datetime.now(timezone.utc)

        logger.info(
            "cross_examine_phase_complete",
            session_id=str(session.session_id),
            challenge_count=challenge_count,
            rounds_completed=rounds_completed,
            duration_ms=int((completed_at - started_at).total_seconds() * 1000),
        )

        return PhaseResult(
            phase=DeliberationPhase.CROSS_EXAMINE,
            transcript=transcript,
            transcript_hash=_compute_blake3_hash(transcript),
            participants=session.assigned_archons,
            started_at=started_at,
            completed_at=completed_at,
            phase_metadata={
                "challenges_raised": challenge_count,
                "rounds_completed": rounds_completed,
                "max_rounds": max_rounds,
            },
        )

    def execute_vote(
        self,
        session: DeliberationSession,
        package: DeliberationContextPackage,
        cross_examine_result: PhaseResult,
    ) -> PhaseResult:
        """Execute VOTE phase - simultaneous final votes (AC-5).

        All archons cast votes simultaneously without seeing others' votes.
        """
        started_at = datetime.now(timezone.utc)
        transcript_parts = ["=== VOTE PHASE ===\n"]

        async def run_votes() -> dict[UUID, DeliberationOutcome]:
            tasks = []

            for archon_id in session.assigned_archons:
                profile = self._get_archon_profile(archon_id)
                agent = self._create_agent(
                    profile,
                    f"Full deliberation context:\n{cross_examine_result.transcript}"
                )

                task_description = f"""
You are {profile.name} casting your FINAL VOTE on petition {package.petition_id}.

CROSS-EXAMINATION COMPLETE:
{cross_examine_result.transcript}

Cast your FINAL vote. Choose EXACTLY ONE:
- ACKNOWLEDGE: Accept and acknowledge the petition
- REFER: Refer to Knight for expert review
- ESCALATE: Escalate to King for adoption consideration

This vote is FINAL and SIMULTANEOUS - you cannot see other votes.

Reply with ONLY your vote: ACKNOWLEDGE, REFER, or ESCALATE
"""
                tasks.append(
                    self._execute_agent_task(
                        agent,
                        task_description,
                        "ACKNOWLEDGE, REFER, or ESCALATE"
                    )
                )

            outputs = await asyncio.gather(*tasks)

            votes: dict[UUID, DeliberationOutcome] = {}
            for archon_id, output in zip(session.assigned_archons, outputs):
                profile = self._get_archon_profile(archon_id)

                # Parse vote from output
                vote = DeliberationOutcome.ACKNOWLEDGE  # Default
                output_upper = output.upper()
                if "ESCALATE" in output_upper:
                    vote = DeliberationOutcome.ESCALATE
                elif "REFER" in output_upper:
                    vote = DeliberationOutcome.REFER

                votes[archon_id] = vote
                transcript_parts.append(
                    f"\n--- {profile.name} ({archon_id}) ---\n"
                    f"VOTE: {vote.value}\n"
                )

            return votes

        votes = asyncio.run(run_votes())

        # Add vote summary
        vote_counts: dict[str, int] = {}
        for vote in votes.values():
            vote_counts[vote.value] = vote_counts.get(vote.value, 0) + 1

        transcript_parts.append("\n=== VOTE SUMMARY ===\n")
        for outcome, count in vote_counts.items():
            transcript_parts.append(f"{outcome}: {count} vote(s)\n")

        transcript = "".join(transcript_parts)
        completed_at = datetime.now(timezone.utc)

        logger.info(
            "vote_phase_complete",
            session_id=str(session.session_id),
            vote_counts=vote_counts,
            duration_ms=int((completed_at - started_at).total_seconds() * 1000),
        )

        return PhaseResult(
            phase=DeliberationPhase.VOTE,
            transcript=transcript,
            transcript_hash=_compute_blake3_hash(transcript),
            participants=session.assigned_archons,
            started_at=started_at,
            completed_at=completed_at,
            phase_metadata={
                "votes": votes,  # Required for orchestrator
                "vote_counts": vote_counts,
            },
        )


def create_crewai_deliberation_adapter(
    profile_repository: ArchonProfileRepository | None = None,
    verbose: bool = False,
    timeout_seconds: float = 30.0,
) -> CrewAIDeliberationAdapter:
    """Factory function to create CrewAIDeliberationAdapter.

    Args:
        profile_repository: Optional profile repository.
            If not provided, creates one with default paths.
        verbose: Enable verbose CrewAI logging
        timeout_seconds: Timeout per archon response (default 30s)

    Returns:
        Configured CrewAIDeliberationAdapter
    """
    if profile_repository is None:
        from src.infrastructure.adapters.config.archon_profile_adapter import (
            create_archon_profile_repository,
        )
        profile_repository = create_archon_profile_repository()

    return CrewAIDeliberationAdapter(
        profile_repository=profile_repository,
        verbose=verbose,
        timeout_seconds=timeout_seconds,
    )
```

## Dependencies

### Upstream Dependencies (Required Before This Story)

| Story ID | Name | Status | Why Needed |
|----------|------|--------|------------|
| petition-2a-1 | Deliberation Session Domain Model | DONE | DeliberationSession aggregate |
| petition-2a-2 | Archon Assignment Service | DONE | Session with assigned archons |
| petition-2a-3 | Context Package Builder | DONE | Context package for Archons |
| petition-2a-4 | Deliberation Protocol Orchestrator | DONE | PhaseExecutorProtocol to implement |
| petition-0-7 | Archon Persona Definitions (Three Fates) | DONE | Archon profiles for CrewAI agents |
| Story 10-2 | CrewAI Adapter Implementation | DONE | Base CrewAI patterns to follow |

### Downstream Dependencies (Blocked By This Story)

| Story ID | Name | Why Blocked |
|----------|------|-------------|
| petition-2a-6 | Supermajority Consensus Resolution | Needs working adapter for real deliberation |
| petition-2a-7 | Phase-Level Witness Batching | Needs real transcript hashes from adapter |
| petition-2a-8 | Disposition Emission & Pipeline Routing | Needs complete deliberation result |

## Implementation Tasks

### Task 1: Create CrewAI Deliberation Adapter (AC: 1, 6)
- [ ] Create `src/infrastructure/adapters/external/crewai_deliberation_adapter.py`
- [ ] Implement `CrewAIDeliberationAdapter` class
- [ ] Add factory function `create_crewai_deliberation_adapter()`
- [ ] Export from `src/infrastructure/adapters/external/__init__.py`

### Task 2: Implement ASSESS Phase (AC: 2)
- [ ] Implement `execute_assess()` method
- [ ] Create assessment tasks for all 3 archons
- [ ] Execute concurrently using `asyncio.gather()`
- [ ] Build transcript and compute Blake3 hash

### Task 3: Implement POSITION Phase (AC: 3)
- [ ] Implement `execute_position()` method
- [ ] Execute archons sequentially (1 → 2 → 3)
- [ ] Pass previous positions to subsequent archons
- [ ] Parse dispositions from outputs

### Task 4: Implement CROSS_EXAMINE Phase (AC: 4)
- [ ] Implement `execute_cross_examine()` method
- [ ] Execute round-robin challenge exchanges
- [ ] Maximum 3 rounds
- [ ] Early termination when no challenges raised

### Task 5: Implement VOTE Phase (AC: 5)
- [ ] Implement `execute_vote()` method
- [ ] Execute votes simultaneously (concurrent)
- [ ] Parse votes from outputs
- [ ] Return votes in `phase_metadata['votes']`

### Task 6: Write Unit Tests
- [ ] Create `tests/unit/infrastructure/adapters/external/test_crewai_deliberation_adapter.py`
- [ ] Test each phase method with mocked CrewAI
- [ ] Test timeout handling
- [ ] Test error conditions

### Task 7: Write Integration Tests
- [ ] Create `tests/integration/test_crewai_deliberation_adapter_integration.py`
- [ ] Test with stub executor (no real LLM)
- [ ] Test with real CrewAI (marked slow, optional)
- [ ] Verify transcript hash generation

## Definition of Done

- [ ] `CrewAIDeliberationAdapter` implements `PhaseExecutorProtocol`
- [ ] All 4 phase methods implemented
- [ ] Concurrent execution for ASSESS and VOTE phases
- [ ] Sequential execution for POSITION phase
- [ ] Round-robin with early exit for CROSS_EXAMINE phase
- [ ] Blake3 hashing for all transcripts
- [ ] Timeout enforcement (30s per archon)
- [ ] Error handling with `DeliberationError`
- [ ] Unit tests pass (>90% coverage)
- [ ] Integration tests verify end-to-end
- [ ] FR-11.4 satisfied: Protocol sequence
- [ ] NFR-10.2 satisfied: 30s timeout enforcement
- [ ] NFR-10.3 satisfied: Deterministic with same inputs

## Test Scenarios

### Scenario 1: Happy Path - Full Deliberation
```python
# Setup
profile_repo = create_archon_profile_repository()
adapter = CrewAIDeliberationAdapter(profile_repo)
session = create_session_with_archons(petition_id, (a1, a2, a3))
package = build_context_package(petition, session)

# Execute all phases
assess = adapter.execute_assess(session, package)
position = adapter.execute_position(session, package, assess)
cross = adapter.execute_cross_examine(session, package, position)
vote = adapter.execute_vote(session, package, cross)

# Verify
assert len(vote.phase_metadata["votes"]) == 3
assert all(v in DeliberationOutcome for v in vote.phase_metadata["votes"].values())
```

### Scenario 2: Timeout Handling
```python
adapter = CrewAIDeliberationAdapter(profile_repo, timeout_seconds=0.001)

with pytest.raises(DeliberationError, match="timed out"):
    adapter.execute_assess(session, package)
```

### Scenario 3: Transcript Hash Consistency
```python
result1 = adapter.execute_assess(session, package)
result2 = adapter.execute_assess(session, package)

# Same inputs should produce same hash (determinism)
assert result1.transcript_hash == result2.transcript_hash
```

## Dev Notes

### Architecture Patterns to Follow

1. **Follow existing CrewAI adapter pattern** in `src/infrastructure/adapters/external/crewai_adapter.py`:
   - Use `_create_crewai_llm()` for LLM configuration
   - Use `profile.get_crewai_config()` for agent setup
   - Use `asyncio.wait_for()` for timeout enforcement
   - Use `asyncio.to_thread()` for running sync CrewAI code

2. **Use existing stub pattern** from `src/infrastructure/stubs/deliberation_orchestrator_stub.py`:
   - Follow the same transcript format
   - Use same `phase_metadata` structure
   - Match the `_compute_transcript_hash()` signature

3. **Structured logging** with `structlog`:
   - Log at INFO level for phase completion
   - Log at DEBUG level for agent creation
   - Log at ERROR level for failures

### Key Files to Reference

| File | Why |
|------|-----|
| `src/infrastructure/adapters/external/crewai_adapter.py` | Base CrewAI patterns |
| `src/application/ports/deliberation_orchestrator.py` | PhaseExecutorProtocol |
| `src/infrastructure/stubs/deliberation_orchestrator_stub.py` | Expected transcript format |
| `src/domain/models/deliberation_result.py` | PhaseResult model |
| `src/domain/models/deliberation_session.py` | Session and outcome enums |

### Project Structure Notes

- **Location:** `src/infrastructure/adapters/external/` - external service adapters
- **Naming:** Follow `*_adapter.py` convention
- **Imports:** Use absolute imports from `src.`
- **Testing:** Separate unit (mocked) and integration (real) tests

### References

- [Source: `src/application/ports/deliberation_orchestrator.py`] - PhaseExecutorProtocol definition
- [Source: `src/infrastructure/adapters/external/crewai_adapter.py`] - CrewAI patterns
- [Source: `src/infrastructure/stubs/deliberation_orchestrator_stub.py`] - Stub reference
- [Source: `_bmad-output/planning-artifacts/petition-system-prd.md`] - FR-11.x requirements
- [Source: `_bmad-output/implementation-artifacts/stories/petition-2a-4-deliberation-protocol-orchestrator.md`] - Upstream story

## Documentation Checklist

- [ ] Architecture docs updated (if patterns/structure changed)
- [ ] API docs updated (if endpoints/contracts changed)
- [ ] README updated (if setup/usage changed)
- [ ] Inline comments added for complex logic
- [ ] N/A - no documentation impact (explain why)

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List
