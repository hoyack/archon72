# Story 7.5: Phase Summary Generation

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **system**,
I want to generate phase summaries for Observer consumption,
So that deliberation transparency is maintained without raw transcript exposure.

## Acceptance Criteria

### AC1: Phase Summary Generation During Deliberation
**Given** a deliberation phase completes
**When** the phase summary is generated
**Then** it includes:
  - Phase name (ASSESS, POSITION, CROSS_EXAMINE, VOTE)
  - Phase duration (computed from timestamps)
  - Key themes identified (extracted keywords/topics from transcript)
  - Convergence indicator (did positions align?) - for POSITION and CROSS_EXAMINE phases
  - Challenge count (for CROSS_EXAMINE phase only)
**And** the summary is stored in `phase_metadata` of `PhaseWitnessEvent`
**And** the summary is derived from transcript but contains NO verbatim quotes

### AC2: Phase Summaries Assembled in Chronological Order
**Given** an Observer requests deliberation summary (via Story 7.4 endpoint)
**When** summaries are assembled
**Then** all 4 phase summaries are included in chronological order (ASSESS → POSITION → CROSS_EXAMINE → VOTE)

### AC3: ASSESS Phase Summary Content
**Given** the ASSESS phase completes
**When** summary is generated
**Then** it includes:
  - `themes`: List of 3-5 key topics/keywords identified from Archon assessments
  - No convergence indicator (first phase, no prior positions)
  - No challenge count (not applicable)

### AC4: POSITION Phase Summary Content
**Given** the POSITION phase completes
**When** summary is generated
**Then** it includes:
  - `themes`: List of 3-5 key topics/keywords from position statements
  - `convergence_reached`: Boolean indicating if all 3 Archons took similar positions
  - No challenge count (not applicable)

### AC5: CROSS_EXAMINE Phase Summary Content
**Given** the CROSS_EXAMINE phase completes
**When** summary is generated
**Then** it includes:
  - `themes`: List of 3-5 key debate topics
  - `convergence_reached`: Boolean indicating if positions aligned after debate
  - `challenge_count`: Integer count of challenges raised during cross-examination

### AC6: VOTE Phase Summary Content
**Given** the VOTE phase completes
**When** summary is generated
**Then** it includes:
  - `themes`: List of key factors cited in voting rationales
  - `convergence_reached`: Boolean (true if unanimous 3-0, false if 2-1)
  - No challenge count (not applicable)

### AC7: System Halted Behavior
**Given** the system is in halted state (CT-13)
**When** phase summary generation is triggered (write operation)
**Then** the deliberation should have already been halted before reaching summary generation
**Because** summary generation occurs within the deliberation flow which has halt checks

## Tasks / Subtasks

- [x] **Task 1: Create PhaseSummaryGenerationService (AC: 1, 3-6)**
  - [x] 1.1 Create `src/application/services/phase_summary_generation_service.py`
  - [x] 1.2 Implement `PhaseSummaryGenerationService` class with LoggingMixin
  - [x] 1.3 Implement `generate_phase_summary(phase: DeliberationPhase, transcript: str) -> dict[str, Any]`
  - [x] 1.4 Implement phase-specific extraction methods:
    - `_extract_themes(transcript: str) -> list[str]` - Extract 3-5 key topics
    - `_assess_convergence(transcript: str, phase: DeliberationPhase) -> bool | None` - Analyze position alignment
    - `_count_challenges(transcript: str) -> int` - Count challenges in CROSS_EXAMINE
  - [x] 1.5 Use simple keyword extraction (no LLM dependency for MVP)

- [x] **Task 2: Create PhaseSummaryGeneratorProtocol (AC: 1)**
  - [x] 2.1 Create `src/application/ports/phase_summary_generator.py`
  - [x] 2.2 Define `PhaseSummaryGeneratorProtocol` with `generate_phase_summary()` method
  - [x] 2.3 Include type hints and docstrings per project standards

- [x] **Task 3: Create PhaseSummaryGeneratorStub (AC: All)**
  - [x] 3.1 Create `src/infrastructure/stubs/phase_summary_generator_stub.py`
  - [x] 3.2 Implement stub returning predictable test data
  - [x] 3.3 Support configurable responses for different test scenarios

- [x] **Task 4: Integrate with PhaseWitnessBatchingService (AC: 1, 2)**
  - [x] 4.1 Update `PhaseWitnessBatchingService.witness_phase()` to optionally accept summary generator
  - [x] 4.2 OR create orchestration layer that generates summary before calling witness_phase
  - [x] 4.3 Ensure phase_metadata contains generated summary fields

- [x] **Task 5: Integrate with DeliberationProtocolOrchestrator (AC: 1, 7)**
  - [x] 5.1 Inject PhaseSummaryGeneratorProtocol into orchestrator (or phase executors)
  - [x] 5.2 Call summary generation at end of each phase before witnessing
  - [x] 5.3 Pass generated metadata to witness_phase() call

- [x] **Task 6: Unit Tests (All ACs)**
  - [x] 6.1 Test PhaseSummaryGenerationService.generate_phase_summary() for each phase
  - [x] 6.2 Test theme extraction from sample transcripts
  - [x] 6.3 Test convergence detection logic
  - [x] 6.4 Test challenge count extraction for CROSS_EXAMINE
  - [x] 6.5 Test that no verbatim quotes appear in output
  - [x] 6.6 Test stub implementation

- [x] **Task 7: Integration Tests (AC: 1, 2)**
  - [x] 7.1 Test full deliberation flow produces phase summaries in metadata
  - [x] 7.2 Test Story 7.4 endpoint returns summaries with themes/convergence
  - [x] 7.3 Test summaries are in chronological order

## Documentation Checklist

- [x] Inline comments added for theme extraction logic
- [x] API docs NOT needed (internal service, no new endpoint)
- [x] N/A - no architecture impact (uses existing phase_metadata pattern)

## Dev Notes

### Relevant Architecture Patterns

**PhaseWitnessEvent.phase_metadata (Story 2A.7):**
The phase witness event already has a `phase_metadata: dict[str, Any]` field. Story 7.4's `TranscriptAccessMediationService._build_phase_summaries()` already reads from this field:
- `metadata.get("themes")` → `tuple[str, ...]`
- `metadata.get("convergence_reached")` → `bool | None`

This means the consumer is ready - we just need to **populate** the metadata during deliberation.

**DeliberationProtocolOrchestrator (Story 2A.4):**
The orchestrator manages the 4-phase deliberation flow. Each phase is executed by a `PhaseExecutorProtocol` implementation. At the end of each phase, `witness_phase()` is called with metadata.

**CrewAI Deliberation Adapter (Story 2A.5):**
The CrewAI adapter implements `PhaseExecutorProtocol` and produces transcript text. Summary generation should happen AFTER the adapter produces transcript but BEFORE witnessing.

### Design Decision: Where to Place Summary Generation

**Option A: Inside PhaseWitnessBatchingService** (NOT recommended)
- Mixes responsibilities (witnessing vs. summarization)
- Would require LLM/NLP dependency in witness service

**Option B: Separate PhaseSummaryGenerationService** (RECOMMENDED)
- Clean separation of concerns
- Orchestrator calls summary generation, passes result to witness_phase
- Easy to swap implementations (simple keyword extraction vs. LLM)

**Option C: Inside PhaseExecutor** (Alternative)
- Each phase executor generates its own summary
- Tight coupling to execution logic

**Recommendation:** Option B - Create `PhaseSummaryGenerationService` as a separate service.

### Theme Extraction Strategy (MVP)

For MVP, use simple keyword extraction (no LLM):
1. Tokenize transcript into words
2. Remove stopwords (common words)
3. Count word frequencies
4. Return top 3-5 most frequent meaningful terms
5. Normalize to lowercase

Future enhancement: Use LLM to extract semantic themes.

### Convergence Detection Strategy (MVP)

For MVP, use simple heuristics:
1. Look for agreement markers: "agree", "concur", "same", "aligned"
2. Look for disagreement markers: "disagree", "different", "oppose", "challenge"
3. If agreement markers > disagreement markers → convergence = True

Future enhancement: Use LLM to analyze semantic alignment.

### Challenge Count Strategy (CROSS_EXAMINE)

For MVP, count occurrences of challenge patterns:
1. "I challenge" / "challenge this"
2. "I question" / "questioning"
3. "disagree with" / "object to"
4. "how do you explain" / "why would"

### Source Tree Components to Touch

| Component | Path | Change Type |
|-----------|------|-------------|
| Service | `src/application/services/phase_summary_generation_service.py` | CREATE |
| Port | `src/application/ports/phase_summary_generator.py` | CREATE |
| Stub | `src/infrastructure/stubs/phase_summary_generator_stub.py` | CREATE |
| Orchestrator | `src/application/services/deliberation_orchestrator_service.py` | MODIFY (inject generator) |
| Tests | `tests/unit/application/services/test_phase_summary_generation_service.py` | CREATE |
| Tests | `tests/integration/test_phase_summary_integration.py` | CREATE |

### Testing Standards Summary

- All tests use `pytest.mark.asyncio`
- Use `AsyncMock` for async dependencies
- Follow naming: `tests/unit/application/services/test_phase_summary_generation_service.py`
- Test each phase type separately with representative transcripts
- Verify no verbatim quotes leak through

### Project Structure Notes

- Service follows LoggingMixin pattern per project-context.md
- Port uses Protocol class for dependency injection
- Stub enables testing without LLM/NLP dependencies
- Integration should verify Story 7.4 endpoint shows populated summaries

### References

- [Source: _bmad-output/planning-artifacts/petition-system-epics.md#Story 7.5]
- [Source: _bmad-output/planning-artifacts/petition-system-prd.md#Ruling-2]
- [Source: _bmad-output/planning-artifacts/petition-system-prd.md#Section 13A.8]
- [Source: src/domain/events/phase_witness.py - PhaseWitnessEvent with phase_metadata]
- [Source: src/application/services/phase_witness_batching_service.py - witness_phase() accepts metadata]
- [Source: src/application/services/transcript_access_mediation_service.py - _build_phase_summaries() reads themes/convergence]
- [Source: _bmad-output/project-context.md - Constitutional rules and patterns]

### Critical Implementation Notes

1. **NO VERBATIM QUOTES** - Summary must be derived, not excerpted (Ruling-2)
2. **Theme extraction is SUMMARIZATION** - Extract topics, not sentences
3. **Convergence is BOOLEAN** - Not a score, not a detailed analysis
4. **Challenge count is INTEGER** - Simple count, not detailed breakdown
5. **MVP uses heuristics** - No LLM dependency for initial implementation
6. **Integration point is witness_phase()** - Pass summary in metadata parameter

### Previous Story Intelligence (Story 7.4)

Story 7.4 (Transcript Access Mediation Service) established:
- `TranscriptAccessMediationService._build_phase_summaries()` reads from `phase_metadata`
- Expected keys: `themes`, `convergence_reached`
- Returns `PhaseSummaryItem` with these fields populated
- If metadata is empty/missing, fields are empty but no error

This means the consumer is already built - we just need to populate the data.

### Git Intelligence (Recent Commits)

Recent commits show pattern of:
- Comprehensive unit tests for all ACs
- Integration tests for full flows
- Following constitutional constraints (CT-12 witnessing)
- Using existing service patterns with dependency injection
- LoggingMixin for all services

### Sample Transcripts for Testing

**ASSESS Phase Sample:**
```
Archon Alpha: Upon review of this petition, I see themes of resource allocation
and community governance. The petitioner raises valid concerns about distribution.

Archon Beta: I concur with the resource focus. Additionally, I note transparency
requirements mentioned multiple times.

Archon Gamma: My assessment highlights governance structure and accountability
mechanisms. The petition seems well-formed.
```
Expected themes: ["resource", "governance", "transparency", "accountability", "distribution"]

**CROSS_EXAMINE Phase Sample:**
```
Archon Alpha: I challenge the assumption that current distribution is unfair.
Archon Beta: I question whether the proposed solution addresses root causes.
Archon Gamma: How do you explain the discrepancy in the petitioner's claims?
Archon Alpha: I disagree with Beta's analysis of the timeline.
```
Expected challenge_count: 4

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

- All 50 unit tests passed
- All 6 integration tests passed
- Fixed witness chain issue in integration test (POSITION requires previous witness hash)

### Completion Notes List

1. Implemented PhaseSummaryGenerationService with LoggingMixin pattern
2. Created PhaseSummaryGeneratorProtocol for dependency injection
3. Created PhaseSummaryGeneratorStub with configurable responses and call tracking
4. Used simple keyword extraction with stopwords filtering (no LLM dependency)
5. Implemented heuristic-based convergence detection (agreement vs disagreement markers)
6. Implemented pattern-based challenge counting for CROSS_EXAMINE phase
7. Added augment_phase_metadata() convenience method for metadata merging
8. Integration tests verify summary flows to PhaseWitnessEvent.phase_metadata
9. NO VERBATIM QUOTES in output - compliant with Ruling-2

### File List

| File | Type | Description |
|------|------|-------------|
| `src/application/ports/phase_summary_generator.py` | CREATE | Protocol definition for phase summary generation |
| `src/application/services/phase_summary_generation_service.py` | CREATE | Main service with theme extraction, convergence detection |
| `src/infrastructure/stubs/phase_summary_generator_stub.py` | CREATE | Test stub with configurable responses |
| `tests/unit/application/services/test_phase_summary_generation_service.py` | CREATE | 27 unit tests for service |
| `tests/unit/infrastructure/stubs/test_phase_summary_generator_stub.py` | CREATE | 23 unit tests for stub |
| `tests/integration/test_phase_summary_generation_integration.py` | CREATE | 6 integration tests for summary-to-witness flow |

