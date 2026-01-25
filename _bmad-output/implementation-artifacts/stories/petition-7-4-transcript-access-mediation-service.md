# Story 7.4: Transcript Access Mediation Service

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an **Observer**,
I want mediated access to deliberation artifacts,
So that I can understand how my petition was deliberated without ambient transcript access.

## Acceptance Criteria

### AC1: Successful Deliberation Summary (Happy Path)
**Given** my petition has completed deliberation (phase = COMPLETE, outcome set)
**When** I GET `/api/v1/petition-submissions/{petition_id}/deliberation-summary`
**Then** I receive a mediated summary containing:
  - `outcome`: Deliberation outcome (ACKNOWLEDGE, REFER, ESCALATE)
  - `vote_breakdown`: Vote breakdown string (e.g., "2-1" or "3-0")
  - `has_dissent`: Boolean indicating if there was a dissenting vote
  - `phase_summaries`: Array of high-level phase summaries (one per phase)
  - `duration_seconds`: Total deliberation duration in seconds
  - `completed_at`: ISO 8601 timestamp when deliberation completed
**And** I do NOT receive:
  - Raw transcript text
  - Individual Archon identities
  - Verbatim utterances
  - Archon UUIDs

### AC2: No Deliberation (Auto-Escalated)
**Given** my petition was auto-escalated (bypassed deliberation via co-signer threshold)
**When** I query deliberation summary
**Then** the response indicates:
  - `outcome`: "ESCALATED"
  - `escalation_trigger`: "AUTO_ESCALATED" (vs "DELIBERATION")
  - `escalation_reason`: Details about why (e.g., "Co-signer threshold reached: 100")
  - `phase_summaries`: Empty array (no deliberation phases occurred)
**And** no deliberation session data is returned (because none exists)

### AC3: Petition Not Yet Deliberated
**Given** my petition is still in RECEIVED state (not yet deliberated)
**When** I query deliberation summary
**Then** the system returns HTTP 400 with:
  - `type`: "urn:archon72:petition:deliberation-pending"
  - `title`: "Deliberation Pending"
  - `detail`: "Petition {petition_id} has not yet completed deliberation"

### AC4: Petition Not Found
**Given** the petition_id does not exist
**When** I query deliberation summary
**Then** the system returns HTTP 404 with standard petition-not-found error

### AC5: System Halted
**Given** the system is in halted state (CT-13)
**When** I query deliberation summary (read operation)
**Then** the system returns the summary normally
**Because** read operations are permitted during halt state (only writes blocked)

### AC6: Timeout-Triggered Escalation
**Given** my petition deliberation timed out (session.timed_out = True)
**When** I query deliberation summary
**Then** the response indicates:
  - `outcome`: "ESCALATED"
  - `escalation_trigger`: "TIMEOUT"
  - `phase_summaries`: Partial phase data (up to timeout point)
  - `timed_out`: true

### AC7: Deadlock-Triggered Escalation
**Given** my petition deliberation deadlocked (session.is_deadlocked = True)
**When** I query deliberation summary
**Then** the response indicates:
  - `outcome`: "ESCALATED"
  - `escalation_trigger`: "DEADLOCK"
  - `rounds_attempted`: Number of voting rounds attempted
  - `phase_summaries`: Full phase data (all rounds)

## Tasks / Subtasks

- [x] **Task 1: Create Deliberation Summary Domain Model (AC: 1, 2, 6, 7)**
  - [x] 1.1 Create `src/domain/models/deliberation_summary.py` with frozen dataclass
  - [x] 1.2 Define `DeliberationSummary` with mediated fields (no raw transcript exposure)
  - [x] 1.3 Define `PhaseSummaryItem` frozen dataclass for individual phase summaries
  - [x] 1.4 Define `EscalationTrigger` enum: DELIBERATION, AUTO_ESCALATED, TIMEOUT, DEADLOCK
  - [x] 1.5 Implement `to_dict()` method for API serialization

- [x] **Task 2: Create Deliberation Summary Port (AC: 1, 2)**
  - [x] 2.1 Create `src/application/ports/deliberation_summary.py` with protocol
  - [x] 2.2 Define `DeliberationSummaryRepositoryPort` protocol
  - [x] 2.3 Method: `get_session_by_petition_id(petition_id: UUID) -> Optional[DeliberationSession]`
  - [x] 2.4 Method: `get_phase_witnesses(session_id: UUID) -> list[PhaseWitnessEvent]`

- [x] **Task 3: Create Transcript Access Mediation Service (AC: 1, 2, 6, 7)**
  - [x] 3.1 Create `src/application/services/transcript_access_mediation_service.py`
  - [x] 3.2 Implement `TranscriptAccessMediationService` class with LoggingMixin
  - [x] 3.3 Inject `DeliberationSummaryRepositoryPort` dependency
  - [x] 3.4 Implement `get_deliberation_summary(petition_id: UUID) -> DeliberationSummary`
  - [x] 3.5 Implement mediation logic: extract only permitted fields, hide Archon identities
  - [x] 3.6 Compute `vote_breakdown` string (e.g., "2-1") from votes without exposing who voted how
  - [x] 3.7 Compute `has_dissent` boolean from session.dissent_archon_id presence
  - [x] 3.8 Compute `duration_seconds` from session.created_at to session.completed_at
  - [x] 3.9 Handle auto-escalation case (no session exists)
  - [x] 3.10 Handle timeout and deadlock cases

- [x] **Task 4: Create Deliberation Summary Stub (AC: All)**
  - [x] 4.1 Create `src/infrastructure/stubs/deliberation_summary_repository_stub.py`
  - [x] 4.2 Implement `DeliberationSummaryRepositoryStub` class
  - [x] 4.3 Add in-memory storage for test sessions and witness events
  - [x] 4.4 Implement stub methods for testing

- [x] **Task 5: Create API Models (AC: 1, 2, 3)**
  - [x] 5.1 Add `DeliberationSummaryResponse` Pydantic model to `src/api/models/deliberation_summary.py`
  - [x] 5.2 Add `PhaseSummaryModel` Pydantic model for phase summaries
  - [x] 5.3 Add `DeliberationPendingError` response model

- [x] **Task 6: Create API Endpoint (AC: 1, 2, 3, 4, 5)**
  - [x] 6.1 Add GET `/v1/petition-submissions/{petition_id}/deliberation-summary` route
  - [x] 6.2 Implement dependency injection for TranscriptAccessMediationService
  - [x] 6.3 Implement RFC 7807 error responses with governance extensions (D7)
  - [x] 6.4 Map domain errors to HTTP status codes (400, 404)
  - [x] 6.5 NOTE: No halt check required for read operation (AC5)

- [x] **Task 7: Unit Tests (All ACs)**
  - [x] 7.1 Test DeliberationSummary model creation and serialization
  - [x] 7.2 Test service happy path (completed deliberation)
  - [x] 7.3 Test auto-escalation case (no deliberation session)
  - [x] 7.4 Test timeout case
  - [x] 7.5 Test deadlock case
  - [x] 7.6 Test mediation logic (Archon IDs not exposed)
  - [x] 7.7 Test vote breakdown computation
  - [x] 7.8 Test API endpoint responses
  - [x] 7.9 Test petition not found
  - [x] 7.10 Test deliberation pending

- [x] **Task 8: Integration Tests (AC: 1, 2, 3)**
  - [x] 8.1 Test full flow: submit -> deliberate -> query summary
  - [x] 8.2 Test auto-escalation flow: submit -> co-sign to threshold -> query summary
  - [x] 8.3 Test pending state rejection

## Documentation Checklist

- [ ] API docs updated (new endpoint)
- [ ] Inline comments added for mediation logic explaining Ruling-2 constraints
- [ ] N/A - no architecture impact (uses existing patterns)

## Dev Notes

### Relevant Architecture Patterns

**Ruling-2: Tiered Transcript Access (Section 13A.8):**
This story implements the Observer tier of transcript access. Per PRD Section 13A.8:
- **Internal system (Knight/Princes):** Full transcripts (Story 7.6)
- **Petitioner:** Phase summaries + final disposition rationale (THIS STORY)
- **Public observers:** No raw transcripts by default

**Key Constraint:** Observers receive:
- Phase-level witness records (metadata only, not content)
- Vote outcomes (2-1 or 3-0)
- Dissent presence indicator (boolean, not identity)
- Hash references (proving transcripts exist and are immutable)

Observers do NOT receive:
- Raw transcript text
- Individual Archon identities
- Verbatim utterances

**DeliberationSession Model (Story 2A.1):**
The `DeliberationSession` in `src/domain/models/deliberation_session.py` contains:
- `outcome: DeliberationOutcome | None` - ACKNOWLEDGE, REFER, ESCALATE
- `votes: dict[UUID, DeliberationOutcome]` - Who voted what (HIDE this from Observer)
- `dissent_archon_id: UUID | None` - Dissenting archon (HIDE this, expose boolean only)
- `timed_out: bool` - Timeout indicator
- `is_deadlocked: bool` - Deadlock indicator
- `round_count: int` - Voting rounds attempted

**PhaseWitnessEvent Model (Story 2A.7):**
The `PhaseWitnessEvent` in `src/domain/events/phase_witness.py` contains:
- `phase: DeliberationPhase` - ASSESS, POSITION, CROSS_EXAMINE, VOTE
- `transcript_hash: bytes` - Blake3 hash of transcript (reveal hash, not content)
- `participating_archons: tuple[UUID, UUID, UUID]` - HIDE these from Observer
- `start_timestamp` / `end_timestamp` - Phase duration (can expose)
- `phase_metadata: dict[str, Any]` - May contain themes, convergence (can expose)

### Source Tree Components to Touch

| Component | Path | Change Type |
|-----------|------|-------------|
| Domain Model | `src/domain/models/deliberation_summary.py` | CREATE |
| Port | `src/application/ports/deliberation_summary.py` | CREATE |
| Service | `src/application/services/transcript_access_mediation_service.py` | CREATE |
| Stub | `src/infrastructure/stubs/deliberation_summary_repository_stub.py` | CREATE |
| API Model | `src/api/models/deliberation_summary.py` | CREATE |
| API Route | `src/api/routes/deliberation_summary.py` OR `src/api/routes/petition_submission.py` | CREATE/MODIFY |
| Domain Error | `src/domain/errors/deliberation.py` | MODIFY (add DeliberationPendingError) |

### Testing Standards Summary

- All tests use `pytest.mark.asyncio`
- Use `AsyncMock` for async dependencies
- Follow naming: `tests/unit/domain/models/test_deliberation_summary.py`
- Create `tests/unit/application/services/test_transcript_access_mediation_service.py`
- Create `tests/unit/api/routes/test_deliberation_summary_routes.py`
- Create `tests/integration/test_deliberation_summary_integration.py`

### Project Structure Notes

- New endpoint under existing router `/v1/petition-submissions/{petition_id}/deliberation-summary`
- Follows existing pattern for petition-related endpoints
- Service uses constructor injection with LoggingMixin pattern
- Domain model uses frozen dataclass pattern

### References

- [Source: _bmad-output/planning-artifacts/petition-system-epics.md#Story 7.4]
- [Source: _bmad-output/planning-artifacts/petition-system-prd.md#Section 13A.8]
- [Source: _bmad-output/planning-artifacts/petition-system-prd.md#Ruling-2]
- [Source: src/domain/models/deliberation_session.py - Session model with outcome, votes, dissent]
- [Source: src/domain/events/phase_witness.py - Phase witness event model]
- [Source: _bmad-output/project-context.md - Constitutional rules and patterns]

### Critical Implementation Notes

1. **MEDIATION IS CRITICAL** - Never expose raw Archon identities to Observers
2. **Vote breakdown format** - Use "2-1" or "3-0" string, not individual votes
3. **Dissent is boolean only** - `has_dissent: true/false`, not `dissenting_archon: UUID`
4. **Phase summaries** - Expose metadata (duration, themes), not transcript content
5. **Hash transparency** - Expose transcript hashes (proves immutability) without content
6. **No HALT check for reads** - This is a read operation, permitted during halt
7. **Handle missing session** - Auto-escalated petitions have no deliberation session
8. **Schema version in events** - D2 compliance requires schema_version in to_dict()

### Previous Story Intelligence (Story 7.3)

Story 7.3 (Petition Withdrawal) established:
- RFC 7807 error response pattern with governance extensions
- `urn:archon72:petition:*` error type URNs
- Endpoint naming under `/v1/petition-submissions/{petition_id}/...`
- Service dependency injection via `Depends()` in routes
- Unit test pattern with comprehensive AC coverage

### Git Intelligence (Recent Commits)

Recent commits show pattern of:
- Comprehensive unit tests for all ACs
- Integration tests for full flows
- Following constitutional constraints (HALT CHECK only for writes)
- Using existing service patterns with dependency injection
- RFC 7807 error responses with governance extensions

### Existing Deliberation Infrastructure

From Epic 2A/2B implementation:
- `DeliberationSession` aggregate in `src/domain/models/deliberation_session.py`
- `PhaseWitnessEvent` in `src/domain/events/phase_witness.py`
- `PhaseWitnessBatchingService` in `src/application/services/phase_witness_batching_service.py`
- `ConsensusResolverService` in `src/application/services/consensus_resolver_service.py`
- Deliberation timeout and deadlock handling already in place

This story builds on top of this infrastructure by providing a mediated read-only view.

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List

