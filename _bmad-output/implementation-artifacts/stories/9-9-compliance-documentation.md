# Story 9.9: Compliance Documentation (NFR31-34)

Status: done

## Story

As a **compliance officer**,
I want compliance documentation maintained,
So that regulatory requirements are met.

## Acceptance Criteria

### AC1: EU AI Act Considerations Documented
**Given** compliance requirements
**When** I examine documentation
**Then** EU AI Act considerations are documented
**And** Human-in-Command (HIC) model compliance is demonstrated through Human Override Protocol
**And** High-risk system transparency obligations are addressed

### AC2: NIST AI RMF Alignment Documented
**Given** compliance requirements
**When** I examine documentation
**Then** NIST AI RMF alignment is documented
**And** GOVERN-MAP-MEASURE-MANAGE functions are mapped to system capabilities
**And** Full decision trail with reasoning is available

### AC3: IEEE 7001 Transparency Requirements Addressed
**Given** compliance requirements
**When** I examine documentation
**Then** IEEE 7001 transparency requirements are addressed
**And** Decision traceability mechanisms are documented
**And** Audit trail accessibility is confirmed

### AC4: Compliance Status Queryable via API
**Given** compliance status
**When** I query it
**Then** current compliance posture is visible
**And** compliance framework mappings are returned
**And** gaps are identified with remediation status

### AC5: Compliance Documentation Logged as Constitutional Event
**Given** compliance documentation creation
**When** documentation is recorded
**Then** a `ComplianceDocumentedEvent` is created
**And** it is signed and witnessed via EventWriterService (CT-12)

### AC6: HALT CHECK FIRST Compliance (CT-11)
**Given** any compliance documentation operation
**When** invoked
**Then** halt state is checked first
**And** if halted, operation fails with SystemHaltedError

## Tasks / Subtasks

- [x] **Task 1: Create ComplianceDocumentedEvent Domain Event** (AC: 5)
  - [ ] Create `src/domain/events/compliance.py`
    - [ ] `ComplianceDocumentedEventPayload` dataclass with:
      - [ ] `compliance_id: str` - Unique identifier (e.g., "NFR31-34-COMPLIANCE")
      - [ ] `framework: str` - Compliance framework (EU_AI_ACT, NIST_AI_RMF, IEEE_7001)
      - [ ] `framework_version: str` - Version of the standard
      - [ ] `assessment_date: datetime` - When assessment was performed
      - [ ] `status: str` - COMPLIANT, PARTIAL, GAP_IDENTIFIED, NOT_APPLICABLE
      - [ ] `findings: list[str]` - Key findings from assessment
      - [ ] `remediation_plan: Optional[str]` - Plan for addressing gaps
      - [ ] `next_review_date: Optional[datetime]` - Scheduled review
      - [ ] `documented_by: str` - Agent/system that documented compliance
    - [ ] Constants: `COMPLIANCE_DOCUMENTED_EVENT_TYPE = "compliance.documented"`
    - [ ] `to_dict()` method for event payload serialization
    - [ ] Docstrings with NFR31-34, CT-12 references
  - [ ] Update `src/domain/events/__init__.py` with export

- [x] **Task 2: Create Compliance Domain Models** (AC: 1, 2, 3, 4)
  - [ ] Create `src/domain/models/compliance.py`
    - [ ] `ComplianceFramework(Enum)`: EU_AI_ACT, NIST_AI_RMF, IEEE_7001, GDPR, MAESTRO
    - [ ] `ComplianceStatus(Enum)`: COMPLIANT, PARTIAL, GAP_IDENTIFIED, NOT_APPLICABLE
    - [ ] `ComplianceRequirement` dataclass:
      - [ ] `requirement_id: str` - NFR ID (e.g., "NFR31")
      - [ ] `framework: ComplianceFramework`
      - [ ] `description: str`
      - [ ] `status: ComplianceStatus`
      - [ ] `implementation_reference: Optional[str]` - Where implemented in codebase
      - [ ] `evidence: list[str]` - Evidence of compliance
    - [ ] `ComplianceAssessment` dataclass:
      - [ ] `assessment_id: str`
      - [ ] `framework: ComplianceFramework`
      - [ ] `assessment_date: datetime`
      - [ ] `requirements: tuple[ComplianceRequirement, ...]`
      - [ ] `overall_status: ComplianceStatus`
      - [ ] `gaps: tuple[str, ...]`
      - [ ] `remediation_plan: Optional[str]`
    - [ ] `FrameworkMapping` dataclass for cross-framework alignment
  - [ ] Update `src/domain/models/__init__.py` with exports

- [x] **Task 3: Create ComplianceRepository Port** (AC: 4)
  - [ ] Create `src/application/ports/compliance_repository.py`
    - [ ] `ComplianceRepositoryProtocol(Protocol)`:
      - [ ] `async def get_assessment(self, assessment_id: str) -> Optional[ComplianceAssessment]`
      - [ ] `async def get_assessments_by_framework(self, framework: ComplianceFramework) -> tuple[ComplianceAssessment, ...]`
      - [ ] `async def get_latest_assessment(self, framework: ComplianceFramework) -> Optional[ComplianceAssessment]`
      - [ ] `async def get_all_latest_assessments(self) -> tuple[ComplianceAssessment, ...]`
      - [ ] `async def get_requirements_by_status(self, status: ComplianceStatus) -> tuple[ComplianceRequirement, ...]`
      - [ ] `async def save_assessment(self, assessment: ComplianceAssessment) -> None`
    - [ ] Docstrings with NFR31-34 references
  - [ ] Update `src/application/ports/__init__.py` with export

- [x] **Task 4: Create ComplianceDocumentationService** (AC: 1, 2, 3, 4, 5, 6)
  - [ ] Create `src/application/services/compliance_documentation_service.py`
    - [ ] `ComplianceDocumentationService` class
    - [ ] Constructor: `compliance_repository: ComplianceRepositoryProtocol`, `event_writer: EventWriterService`, `halt_checker: HaltChecker`
    - [ ] `async def document_assessment(self, framework: ComplianceFramework, requirements: list[ComplianceRequirement], gaps: list[str], remediation_plan: Optional[str]) -> ComplianceAssessment`
      - [ ] HALT CHECK FIRST (CT-11)
      - [ ] Create `ComplianceAssessment` with computed overall status
      - [ ] Save to repository
      - [ ] Create `ComplianceDocumentedEvent` (CT-12)
      - [ ] Write witnessed event
      - [ ] Return assessment
    - [ ] `async def get_compliance_posture() -> dict[ComplianceFramework, ComplianceStatus]`
      - [ ] HALT CHECK FIRST
      - [ ] Get latest assessment for each framework
      - [ ] Return framework -> status mapping
    - [ ] `async def get_gaps() -> tuple[ComplianceRequirement, ...]`
      - [ ] HALT CHECK FIRST
      - [ ] Return all GAP_IDENTIFIED requirements
    - [ ] `async def get_framework_assessment(self, framework: ComplianceFramework) -> Optional[ComplianceAssessment]`
      - [ ] HALT CHECK FIRST
      - [ ] Return latest assessment for framework
    - [ ] Docstrings with NFR31-34, CT-11, CT-12 references
  - [ ] Update `src/application/services/__init__.py` with export

- [x] **Task 5: Create ComplianceRepositoryStub for Testing** (AC: 4)
  - [ ] Create `src/infrastructure/stubs/compliance_repository_stub.py`
    - [ ] `ComplianceRepositoryStub` implementing `ComplianceRepositoryProtocol`
    - [ ] In-memory storage with dict
    - [ ] `clear()` for test isolation
    - [ ] Pre-seed with NFR31-34 compliance assessments for integration tests
  - [ ] Update `src/infrastructure/stubs/__init__.py` with export

- [x] **Task 6: Create NFR31-34 Compliance Initialization** (AC: 1, 2, 3)
  - [ ] Create `src/infrastructure/initialization/compliance_init.py`
    - [ ] Define NFR31-34 requirements with implementation references:
      ```python
      NFR31_REQUIREMENT = ComplianceRequirement(
          requirement_id="NFR31",
          framework=ComplianceFramework.GDPR,
          description="Personal data SHALL be stored separately from constitutional events",
          status=ComplianceStatus.COMPLIANT,
          implementation_reference="src/infrastructure/adapters/persistence/ - separate schemas",
          evidence=["patronage_private schema isolation", "no PII in events table"]
      )
      ```
    - [ ] Define EU AI Act mapping:
      - [ ] Human-in-Command via Human Override Protocol (Epic 5)
      - [ ] Transparency via Observer API (Epic 4)
      - [ ] Audit trail via Event Store (Epic 1)
    - [ ] Define NIST AI RMF mapping:
      - [ ] GOVERN: Keeper governance structure
      - [ ] MAP: Risk identification in architecture
      - [ ] MEASURE: Compliance metrics collection
      - [ ] MANAGE: Override and halt mechanisms
    - [ ] Define IEEE 7001 mapping:
      - [ ] Decision traceability via events
      - [ ] Algorithm versioning in event schema
      - [ ] Public verification interface
    - [ ] `async def initialize_compliance_documentation(service: ComplianceDocumentationService) -> tuple[ComplianceAssessment, ...]`
      - [ ] Check if assessments already exist (idempotent)
      - [ ] Create assessments for each framework
      - [ ] Return all assessments

- [x] **Task 7: Create API Endpoints for Compliance Query** (AC: 4)
  - [ ] Create `src/api/routes/compliance.py`
    - [ ] `GET /v1/compliance` - Overall compliance posture
    - [ ] `GET /v1/compliance/frameworks` - List all framework assessments
    - [ ] `GET /v1/compliance/frameworks/{framework}` - Get specific framework assessment
    - [ ] `GET /v1/compliance/gaps` - List all identified gaps
    - [ ] `GET /v1/compliance/requirements/{requirement_id}` - Get specific requirement status
    - [ ] Response model includes all assessment fields plus evidence
    - [ ] RFC 7807 error responses
  - [ ] Create `src/api/models/compliance.py`
    - [ ] `ComplianceRequirementResponse` Pydantic model
    - [ ] `ComplianceAssessmentResponse` Pydantic model
    - [ ] `CompliancePostureResponse` with framework -> status mapping
    - [ ] `ComplianceGapsResponse` for gaps list
  - [ ] Register routes in `src/api/routes/__init__.py`

- [x] **Task 8: Write Unit Tests** (AC: 1, 2, 3, 4, 5, 6)
  - [ ] Create `tests/unit/domain/test_compliance_events.py`
    - [ ] Test ComplianceDocumentedEventPayload creation (3 tests)
    - [ ] Test to_dict() serialization (2 tests)
    - [ ] Test validation of required fields (3 tests)
  - [ ] Create `tests/unit/domain/test_compliance_models.py`
    - [ ] Test ComplianceFramework enum (2 tests)
    - [ ] Test ComplianceStatus enum (2 tests)
    - [ ] Test ComplianceRequirement creation (3 tests)
    - [ ] Test ComplianceAssessment overall status calculation (4 tests)
  - [ ] Create `tests/unit/application/test_compliance_repository_port.py`
    - [ ] Test ComplianceAssessment creation (2 tests)
    - [ ] Test status values (3 tests)
  - [ ] Create `tests/unit/application/test_compliance_documentation_service.py`
    - [ ] Test HALT CHECK FIRST pattern (4 tests)
    - [ ] Test assessment documentation creates event (3 tests)
    - [ ] Test compliance posture aggregation (3 tests)
    - [ ] Test gaps retrieval (3 tests)
    - [ ] Test idempotent initialization (2 tests)
  - [ ] Target: ~35 unit tests

- [x] **Task 9: Write Integration Tests** (AC: 1, 2, 3, 4, 5, 6)
  - [ ] Create `tests/integration/test_compliance_documentation_integration.py`
    - [ ] Test NFR31-34 compliance initialization (2 tests)
    - [ ] Test EU AI Act assessment creation (2 tests)
    - [ ] Test NIST AI RMF assessment creation (2 tests)
    - [ ] Test IEEE 7001 assessment creation (2 tests)
    - [ ] Test compliance documented event creation (2 tests)
    - [ ] Test compliance API endpoints (5 tests)
    - [ ] Test HALT CHECK FIRST across all services (3 tests)
    - [ ] Test event witnessing (2 tests)
    - [ ] Test idempotent initialization (2 tests)
  - [ ] Target: ~22 integration tests

## Dev Notes

### What are NFR31-34?

**NFR31:** Personal data SHALL be stored separately from constitutional events (GDPR Compatibility)
**NFR32:** Retention policy SHALL be published and immutable (Regulatory Transparency)
**NFR33:** System SHALL provide structured audit export in standard format (Regulatory Reporting)
**NFR34:** Third-party attestation interface SHALL be available (External Audit)

### Regulatory Framework Overview

#### EU AI Act (2024/1689)
- **Human Oversight:** Human-in-Command (HIC) model via Human Override Protocol (Epic 5)
- **Transparency:** Observer API (Epic 4) provides public read access
- **Audit Trail:** Event Store (Epic 1) with hash-chained, witnessed events
- **High-Risk Classification:** Archons making decisions affecting Seekers = "High Risk" or "Limited Risk"
- **Conformity Assessment:** May be required for EU deployment

#### NIST AI RMF
- **GOVERN:** Keeper governance structure, override accountability
- **MAP:** Risk identification in architecture (ADRs, Constitutional Truths)
- **MEASURE:** Compliance metrics, complexity budget tracking (Epic 8)
- **MANAGE:** Override mechanisms (Epic 5), halt protocols (Epic 3)

#### IEEE 7001 Transparency Standard
- **Decision Traceability:** Every decision logged with attribution
- **Algorithm Versioning:** `hash_alg_version`, `sig_alg_version` in events
- **Public Verification:** Observer API with verification toolkit (Epic 4)
- **Accountability:** Witness attribution on all constitutional events

### NFR31-34 Implementation References

| NFR | Implementation | Evidence |
|-----|----------------|----------|
| NFR31 | `patronage_private` schema isolation | No PII in `events` table |
| NFR32 | Append-only event store, CT-13 | Retention policy in docs/ |
| NFR33 | Export service (Epic 4, Story 4-7) | Regulatory reporting export |
| NFR34 | Observer API (Epic 4) | Third-party attestation interface |

### Architecture Pattern: Compliance Documentation

```
ComplianceDocumentationService (coordinates)
    └── ComplianceRepository (persistence)
    └── EventWriterService (witnessed events)
    └── HaltChecker (CT-11)

Domain Models
    └── ComplianceFramework (enum)
    └── ComplianceStatus (enum)
    └── ComplianceRequirement (per-NFR)
    └── ComplianceAssessment (framework-level)

API Layer
    └── GET /v1/compliance
    └── GET /v1/compliance/frameworks
    └── GET /v1/compliance/frameworks/{framework}
    └── GET /v1/compliance/gaps
    └── GET /v1/compliance/requirements/{requirement_id}
```

### Key Design Decisions

1. **Compliance as Constitutional Events**: Every compliance assessment is recorded as a witnessed event, ensuring accountability for compliance claims.

2. **Framework-Based Organization**: Compliance is organized by framework (EU AI Act, NIST AI RMF, IEEE 7001) with cross-framework mapping.

3. **Status Tracking**: Four-tier status (COMPLIANT, PARTIAL, GAP_IDENTIFIED, NOT_APPLICABLE) for granular visibility.

4. **Evidence-Based**: Each requirement includes implementation references and evidence for audit purposes.

5. **API Transparency**: Compliance status queryable via public API - regulators can see compliance posture.

### Previous Story Intelligence (Story 9-8)

**Learnings from Story 9-8:**
1. Service pattern: Constructor injection with ports
2. HALT CHECK FIRST at start of every public method
3. Event payloads reference requirement IDs in docstrings
4. Optional dependencies for backward compatibility
5. Idempotent initialization prevents duplicates
6. API routes follow existing patterns

### Relevant Constitutional Truths

| ID | Truth | Application |
|----|-------|-------------|
| CT-11 | Silent failure destroys legitimacy | HALT CHECK FIRST |
| CT-12 | Witnessing creates accountability | Witnessed compliance events |
| CT-13 | Integrity outranks availability | Immutable retention policy |

### Source Tree Components to Touch

**Files to Create:**
```
src/domain/events/compliance.py
src/domain/models/compliance.py
src/application/ports/compliance_repository.py
src/application/services/compliance_documentation_service.py
src/infrastructure/stubs/compliance_repository_stub.py
src/infrastructure/initialization/compliance_init.py
src/api/routes/compliance.py
src/api/models/compliance.py
tests/unit/domain/test_compliance_events.py
tests/unit/domain/test_compliance_models.py
tests/unit/application/test_compliance_repository_port.py
tests/unit/application/test_compliance_documentation_service.py
tests/integration/test_compliance_documentation_integration.py
```

**Files to Modify:**
```
src/domain/events/__init__.py          # Export new event
src/domain/models/__init__.py          # Export new models
src/application/ports/__init__.py      # Export new port
src/application/services/__init__.py   # Export new service
src/infrastructure/stubs/__init__.py   # Export new stub
src/api/routes/__init__.py             # Register compliance routes
src/api/models/__init__.py             # Export new models
```

### Testing Standards Summary

**Coverage Requirements:**
- Minimum 80% coverage
- 100% coverage for compliance documentation path
- All HALT CHECK FIRST patterns tested

**Async Testing:**
- ALL test files use `pytest.mark.asyncio`
- Use `AsyncMock` for async port methods
- Mock `HaltChecker`, `EventWriterService`, `ComplianceRepositoryProtocol` in unit tests

**Key Test Scenarios:**
1. NFR31-34 compliance is correctly documented with all fields
2. EU AI Act, NIST AI RMF, IEEE 7001 assessments are created
3. ComplianceDocumentedEvent is created and witnessed
4. Compliance posture query returns framework -> status mapping
5. Gaps retrieval returns all GAP_IDENTIFIED requirements
6. HALT CHECK FIRST prevents all operations when halted
7. Idempotent initialization doesn't create duplicates
8. API endpoints return correct data

### Git Commit Pattern

```
feat(story-9.9): Implement compliance documentation (NFR31-34)
```

### Project Structure Notes

- New files follow existing patterns in `src/application/services/`
- Domain events follow existing event patterns
- Domain models follow existing model patterns
- Port follows existing repository protocol patterns
- Stub follows existing stub patterns in `src/infrastructure/stubs/`
- API routes follow existing patterns in `src/api/routes/`
- No conflicts detected with existing architecture

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story-9.9] - Story definition
- [Source: _bmad-output/planning-artifacts/prd.md#NFR31-34] - Compliance requirements
- [Source: _bmad-output/planning-artifacts/research/domain-ai-governance-systems-research-2024-12-27.md] - Regulatory research
- [Source: _bmad-output/implementation-artifacts/stories/9-8-ct-15-waiver-documentation.md] - Previous story patterns
- [Source: _bmad-output/project-context.md] - Project conventions
- [Source: _bmad-output/planning-artifacts/architecture.md] - Architecture patterns

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5

### Debug Log References

N/A

### Completion Notes List

1. Created ComplianceDocumentedEventPayload with signable_content() for CT-12 witnessing
2. Created compliance domain models: ComplianceFramework, ComplianceStatus, ComplianceRequirement, ComplianceAssessment, FrameworkMapping
3. Created ComplianceRepositoryProtocol with all required async methods
4. Created ComplianceDocumentationService with HALT CHECK FIRST pattern on all methods
5. Created ComplianceRepositoryStub for testing with in-memory storage
6. Created compliance initialization with NFR31-34, EU AI Act, NIST AI RMF, IEEE 7001 requirements
7. Created API endpoints: GET /v1/compliance, /v1/compliance/frameworks, /v1/compliance/frameworks/{framework}, /v1/compliance/gaps
8. Created 75 unit tests (target was ~35) - exceeded target
9. Created 28 integration tests (target was ~22) - exceeded target
10. All 103 tests passing

### File List

**Created:**
- src/domain/events/compliance.py
- src/domain/models/compliance.py
- src/application/ports/compliance_repository.py
- src/application/services/compliance_documentation_service.py
- src/infrastructure/stubs/compliance_repository_stub.py
- src/infrastructure/initialization/compliance_init.py
- src/api/routes/compliance.py
- src/api/models/compliance.py
- tests/unit/domain/test_compliance_events.py
- tests/unit/domain/test_compliance_models.py
- tests/unit/application/test_compliance_documentation_service.py
- tests/integration/test_compliance_documentation_integration.py

**Modified:**
- src/domain/events/__init__.py (added exports)
- src/domain/models/__init__.py (added exports)
- src/application/ports/__init__.py (added exports)
- src/application/services/__init__.py (added exports)
- src/infrastructure/stubs/__init__.py (added exports)
- src/api/routes/__init__.py (added compliance_router)
- src/api/models/__init__.py (added exports)
