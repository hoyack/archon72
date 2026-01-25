# Story 7.6: Governance Transcript Access (Elevated)

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **High Archon or auditor**,
I want full transcript access for governance review,
So that I can perform quality oversight of deliberations.

## Acceptance Criteria

### AC1: Elevated Access for HIGH_ARCHON Role
**Given** I have HIGH_ARCHON role (via X-Archon-Role header)
**When** I GET `/api/v1/deliberations/{session_id}/transcript`
**Then** I receive the complete transcript including:
  - All utterances with Archon attribution (archon_id for each utterance)
  - Timestamps for each utterance (ISO 8601 UTC)
  - Phase boundaries (ASSESS, POSITION, CROSS_EXAMINE, VOTE)
  - Raw dissent text (if present)
**And** my access is logged for audit purposes (CT-12)

### AC2: Elevated Access for AUDITOR Role
**Given** I have AUDITOR role (via X-Archon-Role header)
**When** I GET `/api/v1/deliberations/{session_id}/transcript`
**Then** I receive the same complete transcript as HIGH_ARCHON
**And** my access is logged for audit purposes

### AC3: Denied Access for OBSERVER Role
**Given** I have OBSERVER role
**When** I attempt to GET `/api/v1/deliberations/{session_id}/transcript`
**Then** the system returns HTTP 403 Forbidden
**And** the response body includes:
  - Error message: "Elevated role required for full transcript access"
  - Redirect hint to mediated summary endpoint (`/api/v1/petitions/{petition_id}/deliberation-summary`)

### AC4: Denied Access for SEEKER Role
**Given** I have SEEKER role
**When** I attempt to GET `/api/v1/deliberations/{session_id}/transcript`
**Then** the system returns HTTP 403 Forbidden
**And** I am directed to the mediated summary endpoint

### AC5: Session Not Found Error
**Given** the session_id does not exist
**When** I attempt to GET `/api/v1/deliberations/{session_id}/transcript`
**Then** the system returns HTTP 404 Not Found
**And** the error follows RFC 7807 + governance extensions

### AC6: Read Operations Permitted During Halt
**Given** the system is in halted state (CT-13)
**When** I query the full transcript endpoint
**Then** the request succeeds (read operations allowed during halt)
**Because** transcript access is a read operation that maintains visibility (CT-13: integrity over availability, but reads preserve visibility)

### AC7: Audit Log Content
**Given** a successful transcript access request
**When** the access is logged
**Then** the audit log entry contains:
  - accessor_archon_id
  - accessor_role (HIGH_ARCHON or AUDITOR)
  - session_id accessed
  - timestamp of access (UTC)
  - request_ip (if available)

## Tasks / Subtasks

- [x] **Task 1: Create GovernanceTranscriptAccessService (AC: 1, 2, 5, 6)**
  - [x] 1.1 Create `src/application/services/governance_transcript_access_service.py`
  - [x] 1.2 Implement service class with LoggingMixin pattern
  - [x] 1.3 Implement `get_full_transcript(session_id: UUID) -> FullTranscriptResponse`
  - [x] 1.4 Use existing `DeliberationSummaryRepositoryProtocol` for session lookup
  - [x] 1.5 Load raw transcript content from TranscriptStoreProtocol
  - [x] 1.6 Include Archon attributions (NOT mediated)

- [x] **Task 2: Create GovernanceTranscriptAccessProtocol (AC: 1, 2)**
  - [x] 2.1 Create `src/application/ports/governance_transcript_access.py`
  - [x] 2.2 Define `GovernanceTranscriptAccessProtocol` with method signatures
  - [x] 2.3 Include type hints for response models

- [x] **Task 3: Create Response Models (AC: 1, 2, 5)**
  - [x] 3.1 Create `src/api/models/governance_transcript.py`
  - [x] 3.2 Define `FullTranscriptResponse` Pydantic model
  - [x] 3.3 Define `PhaseTranscriptDetail` model
  - [x] 3.4 Define `TranscriptUtterance` model

- [x] **Task 4: Create Elevated Auth Dependency (AC: 1-4)**
  - [x] 4.1 Create `src/api/auth/elevated_auth.py`
  - [x] 4.2 Implement `get_elevated_actor()` that accepts HIGH_ARCHON or AUDITOR roles
  - [x] 4.3 Return 403 Forbidden with redirect hint for OBSERVER/SEEKER roles
  - [x] 4.4 Log all access attempts for audit (CT-12)

- [x] **Task 5: Create REST Endpoint (AC: All)**
  - [x] 5.1 Create `src/api/routes/governance_transcript.py`
  - [x] 5.2 Implement `GET /deliberations/{session_id}/transcript`
  - [x] 5.3 Use elevated auth dependency
  - [x] 5.4 Return FullTranscriptResponse on success
  - [x] 5.5 Return RFC 7807 error with governance extensions on failure

- [x] **Task 6: Create GovernanceTranscriptAccessStub (AC: All)**
  - [x] 6.1 Create `src/infrastructure/stubs/governance_transcript_access_stub.py`
  - [x] 6.2 Implement stub with configurable responses
  - [x] 6.3 Support error simulation (session not found)

- [x] **Task 7: Unit Tests (All ACs)**
  - [x] 7.1 Test service returns full transcript for valid session
  - [x] 7.2 Test session not found raises correct error
  - [x] 7.3 Test auth accepts HIGH_ARCHON role
  - [x] 7.4 Test auth accepts AUDITOR role
  - [x] 7.5 Test auth rejects OBSERVER role with 403
  - [x] 7.6 Test auth rejects SEEKER role with 403
  - [x] 7.7 Test audit logging captures required fields

- [x] **Task 8: Integration Tests (AC: 1-5)**
  - [x] 8.1 Test full flow: authenticated HIGH_ARCHON gets transcript
  - [x] 8.2 Test full flow: authenticated AUDITOR gets transcript
  - [x] 8.3 Test full flow: OBSERVER gets 403 with redirect hint
  - [x] 8.4 Test full flow: missing session returns 404

## Documentation Checklist

- [ ] Inline comments for elevated access logic
- [ ] API docs updated (new endpoint `/api/v1/deliberations/{session_id}/transcript`)
- [ ] N/A - no architecture impact (uses existing tiered access pattern from Ruling-2)

## Dev Notes

### Relevant Architecture Patterns

**Ruling-2 Tiered Access Model (PRD Section 13A.8):**
This story completes the Ruling-2 trilogy:
- Story 7.4: Mediated access for OBSERVER/SEEKER (phase summaries, no raw transcripts)
- Story 7.5: Phase summary generation (themes, convergence, no verbatim quotes)
- **Story 7.6**: Elevated access for HIGH_ARCHON/AUDITOR (full transcripts)

The access tiers per PRD:
| Audience | Access Level |
|----------|--------------|
| Internal system (Knight/Princes) | Full transcripts |
| **HIGH_ARCHON/AUDITOR** | Full transcripts (this story) |
| Petitioner (OBSERVER) | Phase summaries + final disposition (Story 7.4) |
| Public observers | No raw transcripts by default |

**Existing Auth Pattern (src/api/auth/high_archon_auth.py):**
The existing `get_high_archon_id()` function validates:
1. X-Archon-Id header (UUID format)
2. X-Archon-Role header (must equal "HIGH_ARCHON")

For this story, extend or create a new function that accepts EITHER "HIGH_ARCHON" OR "AUDITOR" role.

**TranscriptAccessMediationService (Story 7.4):**
The existing service at `src/application/services/transcript_access_mediation_service.py`:
- Filters out raw Archon identities
- Provides anonymous vote breakdown ("2-1" not "Archon A voted X")
- Returns phase summaries with metadata, not transcript content

This story provides the OPPOSITE - full details for governance actors.

### Design Decision: Where to Get Transcript Content

**Option A: From PhaseWitnessEvents (RECOMMENDED)**
- PhaseWitnessEvents contain `transcript_hash_hex` proving integrity
- Need to also store/retrieve actual transcript content
- `phase_metadata` may contain summary but NOT raw content

**Option B: From DeliberationSession.phase_transcripts**
- Session stores `phase_transcripts: dict[DeliberationPhase, bytes]` (Blake3 hashes)
- Hashes only - need separate storage for actual content

**Option C: New TranscriptStorage Repository**
- Create dedicated storage for raw transcripts
- Reference by hash for integrity verification
- May need to update deliberation flow to persist transcripts

**Recommendation:** Check if CrewAI adapter already persists transcripts. If not, this story may need to add transcript persistence alongside the access endpoint.

**CRITICAL INVESTIGATION NEEDED:** Before implementation, verify where raw transcript text is currently stored. The hash references exist but the actual content storage location needs to be confirmed.

### Source Tree Components to Touch

| Component | Path | Change Type |
|-----------|------|-------------|
| Service | `src/application/services/governance_transcript_access_service.py` | CREATE |
| Port | `src/application/ports/governance_transcript_access.py` | CREATE |
| Auth | `src/api/auth/elevated_auth.py` | CREATE |
| Models | `src/api/models/governance_transcript.py` | CREATE |
| Routes | `src/api/routes/governance_transcript.py` | CREATE |
| Stub | `src/infrastructure/stubs/governance_transcript_access_stub.py` | CREATE |
| Tests | `tests/unit/application/services/test_governance_transcript_access_service.py` | CREATE |
| Tests | `tests/unit/api/routes/test_governance_transcript_routes.py` | CREATE |
| Tests | `tests/integration/test_governance_transcript_access_integration.py` | CREATE |

### Testing Standards Summary

- All tests use `pytest.mark.asyncio`
- Use `AsyncMock` for async dependencies
- Follow naming: `tests/unit/application/services/test_governance_transcript_access_service.py`
- Test each role type separately (HIGH_ARCHON, AUDITOR, OBSERVER, SEEKER)
- Verify audit logging captures required fields

### Project Structure Notes

- Service follows LoggingMixin pattern per project-context.md
- Port uses Protocol class for dependency injection
- Auth follows existing pattern in `src/api/auth/high_archon_auth.py`
- Response models use Pydantic v2 per project standards
- Error responses use RFC 7807 + governance extensions

### References

- [Source: _bmad-output/planning-artifacts/petition-system-epics.md#Story 7.6]
- [Source: _bmad-output/planning-artifacts/petition-system-prd.md#Ruling-2]
- [Source: _bmad-output/planning-artifacts/petition-system-prd.md#Section 13A.8]
- [Source: src/api/auth/high_archon_auth.py - Existing HIGH_ARCHON auth pattern]
- [Source: src/application/services/transcript_access_mediation_service.py - Mediated access for contrast]
- [Source: src/domain/models/deliberation_session.py - Session with phase_transcripts]
- [Source: _bmad-output/project-context.md - Constitutional rules and patterns]

### Critical Implementation Notes

1. **FULL TRANSCRIPTS** - This endpoint exposes raw content, not mediated summaries
2. **ARCHON ATTRIBUTION** - Unlike Story 7.4, include actual Archon IDs
3. **AUDIT LOGGING** - Every access MUST be logged (CT-12)
4. **ROLE CHECK** - Only HIGH_ARCHON and AUDITOR, NOT OBSERVER/SEEKER
5. **403 WITH REDIRECT** - Denied users should be told about the mediated endpoint
6. **TRANSCRIPT STORAGE** - Investigate where raw transcripts are persisted before implementing

### Previous Story Intelligence (Story 7.5)

Story 7.5 (Phase Summary Generation) established:
- PhaseSummaryGenerationService generates themes/convergence/challenge_count
- Output stored in `phase_metadata` of PhaseWitnessEvent
- NO VERBATIM QUOTES in summary output (Ruling-2 compliance)

This story is the elevated tier where verbatim content IS permitted.

### Git Intelligence (Recent Commits)

Recent commits show:
- Story 8.4 added `src/api/auth/high_archon_auth.py` pattern (use this!)
- Story 8.3 added orphan detection job pattern
- Story 8.2 added alerting pattern
- Story 8.1 added metrics computation pattern

The auth pattern from 8.4 is directly reusable for this story's elevated access.

### Sample Response Format

```json
{
  "session_id": "01234567-89ab-cdef-0123-456789abcdef",
  "petition_id": "fedcba98-7654-3210-fedc-ba9876543210",
  "phases": [
    {
      "phase": "ASSESS",
      "start_timestamp": "2026-01-22T10:00:00Z",
      "end_timestamp": "2026-01-22T10:05:00Z",
      "utterances": [
        {
          "archon_id": "aaaa1111-2222-3333-4444-555566667777",
          "timestamp": "2026-01-22T10:01:00Z",
          "content": "Upon review of this petition, I see themes of resource allocation...",
          "sequence": 1
        }
      ],
      "transcript_hash_hex": "abc123..."
    }
  ],
  "outcome": "ACKNOWLEDGE",
  "has_dissent": true,
  "dissent_text": "I disagree with the majority because...",
  "completed_at": "2026-01-22T10:30:00Z"
}
```

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

N/A

### Completion Notes List

- All 8 tasks completed successfully
- 18 unit tests passing in `tests/unit/application/services/test_governance_transcript_access_service.py`
- 12 integration tests passing in `tests/integration/test_governance_transcript_integration.py`
- Transcript content is stored in `transcript_contents` table via `TranscriptStoreProtocol`
- Extended `DeliberationSummaryRepositoryProtocol` with `get_session_by_session_id()` method
- Ruling-2 Trilogy completed (Story 7.4 mediated, Story 7.5 summaries, Story 7.6 elevated)
- This completes Epic 7: Petition System - Observer Engagement

### File List

**Created:**
- `src/application/ports/governance_transcript_access.py` - Protocol definition
- `src/api/models/governance_transcript.py` - Response models (FullTranscriptResponse, PhaseTranscriptDetail, TranscriptUtterance, TranscriptAccessError)
- `src/application/services/governance_transcript_access_service.py` - Main service
- `src/api/auth/elevated_auth.py` - Elevated auth dependency (HIGH_ARCHON/AUDITOR)
- `src/api/routes/governance_transcript.py` - REST endpoint
- `src/infrastructure/stubs/governance_transcript_access_stub.py` - Stub for testing
- `tests/unit/application/services/test_governance_transcript_access_service.py` - Unit tests (18 tests)
- `tests/integration/test_governance_transcript_integration.py` - Integration tests (12 tests)

**Modified:**
- `src/application/ports/deliberation_summary.py` - Added `get_session_by_session_id()` method
- `src/infrastructure/stubs/deliberation_summary_repository_stub.py` - Implemented session lookup by ID
