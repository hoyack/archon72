---
stepsCompleted: [1, 2, 3, 4]
validationStatus: PASSED
inputDocuments:
  - docs/prd.md
  - docs/conclave-prd.md
  - _bmad-output/planning-artifacts/architecture.md
  - _bmad-output/planning-artifacts/mitigation-architecture-spec.md
  - _bmad-output/planning-artifacts/research-integration-addendum.md
  - _bmad-output/project-context.md
---

# Archon 72 Conclave Backend - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for the **Archon 72 Conclave Backend**, decomposing the requirements from the PRD, Conclave PRD, and Architecture requirements into implementable stories.

## Requirements Inventory

### Functional Requirements

**Meeting Engine (ME):**
- FR-ME-001: Manage meeting lifecycle (SCHEDULED → OPENING → IN_SESSION → CLOSING → CONCLUDED → ARCHIVED)
- FR-ME-002: Enforce quorum requirement (37 Archons for standard, 49 for critical decisions)
- FR-ME-003: Support 13-section order of business (Opening through Closing Ceremony)
- FR-ME-004: Time-bound deliberation to prevent context degradation
- FR-ME-005: Track current agenda item and manage transitions
- FR-ME-006: Manage speaker queue with recognition protocol
- FR-ME-007: Support regular weekly Conclave (Sunday 00:00 UTC)
- FR-ME-008: Support special Conclave sessions

**Voting System (VS):**
- FR-VS-001: Implement anonymous balloting with commit-reveal pattern
- FR-VS-002: Support three vote thresholds (majority >50%, supermajority ≥2/3, unanimous 100%)
- FR-VS-003: Collect votes from all present Archons (mandatory participation)
- FR-VS-004: Capture reasoning summary with each vote
- FR-VS-005: Support tie-breaking by High Archon (public vote)
- FR-VS-006: Implement cryptographic vote integrity verification
- FR-VS-007: Support motion types (main, amendment, table, call question, etc.)
- FR-VS-008: Automatic reveal after voting deadline

**Agent Orchestration (AO):**
- FR-AO-001: Instantiate all 72 Archons with unique personalities
- FR-AO-002: Enforce singleton mutex (one instance per Archon)
- FR-AO-003: Load personality from YAML definitions
- FR-AO-004: Support personality variation within Archon template for Guides
- FR-AO-005: Manage per-meeting context windows
- FR-AO-006: Implement split-brain detection
- FR-AO-007: Support fencing tokens for all state mutations
- FR-AO-008: Manage archon memory across meetings (voting history, relationships)

**Ceremony Engine (CE):**
- FR-CE-001: Support 8 ceremony types (Opening, Closing, Installation, Admonishment, Recognition, Impeachment, Emergency Session, Succession)
- FR-CE-002: Implement two-phase commit (pending → committed)
- FR-CE-003: Tyler witness attestation for critical ceremonies
- FR-CE-004: Rollback capability for failed ceremonies
- FR-CE-005: Multi-agent ceremonial dialogue coordination
- FR-CE-006: Load ceremony scripts from templates
- FR-CE-007: Support ceremony variations (standard, election, special)
- FR-CE-008: Record ceremonial transcripts

**Committee Manager (CM):**
- FR-CM-001: Support 5 standing committees (Investigation, Ethics, Outreach, Appeals, Treasury)
- FR-CM-002: Create special (temporary) committees via motion
- FR-CM-003: Manage committee membership and chair assignment
- FR-CM-004: Schedule committee meetings between Conclaves
- FR-CM-005: Collect and format committee reports
- FR-CM-006: Enforce blinding for petition review (Committee doesn't know tier)
- FR-CM-007: Implement petition investigation workflow
- FR-CM-008: Committee dissolution upon completion of charge

**Officer Management (OM):**
- FR-OM-001: Support 12 officer positions with distinct duties
- FR-OM-002: Annual election cycle (first Conclave of January)
- FR-OM-003: Nomination period (opens 2 Conclaves prior)
- FR-OM-004: Term limits (3 consecutive terms maximum)
- FR-OM-005: Succession chain (High Archon → Deputy → Third → Past High Archon)
- FR-OM-006: Officer installation ceremony
- FR-OM-007: Mid-term vacancy special election
- FR-OM-008: Officer removal by 2/3 vote

**Input Boundary (IB):**
- FR-IB-001: Quarantine all Seeker petition content before processing
- FR-IB-002: Apply content pattern blocking (injection detection)
- FR-IB-003: Implement rate limiting per Seeker
- FR-IB-004: Generate sanitized summaries (Archons never see raw input)
- FR-IB-005: Async processing via message queue
- FR-IB-006: Maintain complete separation from Conclave database

**Human Override (HO):**
- FR-HO-001: Dashboard for Keeper intervention
- FR-HO-002: Multi-factor authentication for Keepers (password + TOTP + hardware key)
- FR-HO-003: Time-limited override (72 hours default)
- FR-HO-004: Enumerated override reasons (legal, technical, safety)
- FR-HO-005: Conclave notification of override
- FR-HO-006: Multi-Keeper requirement for extended overrides (>24h)
- FR-HO-007: Full audit logging of all Keeper actions
- FR-HO-008: Override visibility dashboard (public autonomy counter)

**Petition Processing (PP):**
- FR-PP-001: Receive petitions from frontend via API/webhook
- FR-PP-002: Queue petitions for Investigation Committee
- FR-PP-003: Support committee interview workflow
- FR-PP-004: Generate committee recommendation
- FR-PP-005: Present petitions at Conclave for vote
- FR-PP-006: Record decision (Approve/Reject/Defer)
- FR-PP-007: Trigger Guide assignment upon approval
- FR-PP-008: Notify Seeker of decision

**Bylaw Management (BM):**
- FR-BM-001: Store bylaws with versioning
- FR-BM-002: Support amendment proposal workflow
- FR-BM-003: Two reading requirement for amendments
- FR-BM-004: 2/3 threshold for bylaw amendments
- FR-BM-005: Provide bylaw lookup for procedural references
- FR-BM-006: Track effective dates of amendments

**Audit & Records (AR):**
- FR-AR-001: Event sourcing for all meeting events
- FR-AR-002: Immutable vote records with 7-year retention
- FR-AR-003: Meeting minutes generation and approval workflow
- FR-AR-004: Meeting transcript (real-time log)
- FR-AR-005: Decision audit trail with reasoning
- FR-AR-006: Conclave session records

### Non-Functional Requirements

**Performance:**
- NFR-001: Support 72 concurrent agent sessions
- NFR-002: Vote collection timeout < 60 seconds per Archon
- NFR-003: Meeting state transitions < 2 seconds
- NFR-004: API response time < 500ms (95th percentile)

**Reliability:**
- NFR-005: Two-phase commit for ceremonies (zero partial states)
- NFR-006: Circuit breaker for agent fan-out (graceful degradation)
- NFR-007: Quorum from responsive agents only (timeout handling)
- NFR-008: Checkpoint recovery for ceremony failures

**Security:**
- NFR-009: Patronage tier blinding (architectural isolation, not policy)
- NFR-010: Input sanitization for all Seeker content
- NFR-011: Fencing tokens for all state mutations
- NFR-012: Encrypted vote storage (anonymous balloting)
- NFR-013: mTLS for service-to-service communication
- NFR-014: Multi-factor auth for Keeper access

**Compliance:**
- NFR-015: EU AI Act Human-in-Command model compliance
- NFR-016: Full decision trail with reasoning (NIST AI RMF)
- NFR-017: IEEE 7001 transparency requirements
- NFR-018: 7-year immutable vote record retention

**Observability:**
- NFR-019: Structured JSON logging with correlation IDs
- NFR-020: Prometheus metrics for all services
- NFR-021: Health/ready endpoints for each service
- NFR-022: Personality distinctiveness monitoring
- NFR-023: Dissent health metrics (voting correlation)

**Scalability:**
- NFR-024: Horizontal scaling support for API layer
- NFR-025: Async message queue for InputBoundary → Conclave
- NFR-026: Redis for distributed locks and caching

### Additional Requirements

**From Architecture (ADRs):**
- ADR-001: Thin abstraction over CrewAI (AgentOrchestrator interface)
- ADR-002: Hybrid event sourcing (full for audit paths, CRUD for config)
- ADR-003: Centralized MeetingCoordinator (single source of truth)
- ADR-004: Separate InputBoundary microservice
- ADR-005: Commit-reveal voting pattern

**From Security Architecture:**
- Public commitment log for votes (published before deadline)
- Multi-witness ceremonies (3 random witnesses for critical ceremonies)
- Cumulative drift tracking for personality monitoring
- NFKC normalization before pattern matching
- Semantic injection scanning (secondary to summarizer)

**From Pre-mortem Analysis:**
- Personality distinctiveness baseline in Phase 1 (not Phase 3)
- Dissent health metrics in Phase 1
- Override visibility dashboard in Phase 1
- State reconciliation playbook for ceremony failures
- Weekly personality health reports

**Technology Constraints:**
- Python 3.11+ (required for TaskGroup)
- FastAPI (async-first API)
- CrewAI (multi-agent orchestration)
- PostgreSQL 16 via Supabase
- SQLAlchemy 2.0 (async mode)
- Pydantic v2 (API models)
- Redis (locks + events)
- structlog (structured logging)

### FR Coverage Map

| FR Code | Epic | Brief Description |
|---------|------|-------------------|
| FR-ME-001 | Epic 2 | Meeting lifecycle state machine |
| FR-ME-002 | Epic 2 | Quorum enforcement |
| FR-ME-003 | Epic 2 | 13-section order of business |
| FR-ME-004 | Epic 2 | Time-bounded deliberation |
| FR-ME-005 | Epic 2 | Agenda item tracking |
| FR-ME-006 | Epic 2 | Speaker queue |
| FR-ME-007 | Epic 2 | Weekly Conclave schedule |
| FR-ME-008 | Epic 2 | Special sessions |
| FR-VS-001 | Epic 3 | Commit-reveal voting |
| FR-VS-002 | Epic 3 | Three vote thresholds |
| FR-VS-003 | Epic 3 | Mandatory participation |
| FR-VS-004 | Epic 3 | Reasoning capture |
| FR-VS-005 | Epic 3 | Tie-breaking |
| FR-VS-006 | Epic 3 | Cryptographic integrity |
| FR-VS-007 | Epic 3 | Motion types |
| FR-VS-008 | Epic 3 | Automatic reveal |
| FR-AO-001 | Epic 1 | 72 Archon instantiation |
| FR-AO-002 | Epic 1 | Singleton mutex |
| FR-AO-003 | Epic 1 | Personality loading |
| FR-AO-004 | Epic 2 | Personality variation |
| FR-AO-005 | Epic 2 | Per-meeting context |
| FR-AO-006 | Epic 1 | Split-brain detection |
| FR-AO-007 | Epic 1 | Fencing tokens |
| FR-AO-008 | Epic 3 | Archon memory |
| FR-CE-001 | Epic 4 | 8 ceremony types |
| FR-CE-002 | Epic 4 | Two-phase commit |
| FR-CE-003 | Epic 4 | Tyler attestation |
| FR-CE-004 | Epic 4 | Rollback capability |
| FR-CE-005 | Epic 4 | Ceremonial dialogue |
| FR-CE-006 | Epic 4 | Script loading |
| FR-CE-007 | Epic 4 | Ceremony variations |
| FR-CE-008 | Epic 4 | Transcript recording |
| FR-CM-001 | Epic 5 | 5 standing committees |
| FR-CM-002 | Epic 5 | Special committees |
| FR-CM-003 | Epic 5 | Membership management |
| FR-CM-004 | Epic 5 | Committee scheduling |
| FR-CM-005 | Epic 5 | Report formatting |
| FR-CM-006 | Epic 5 | Blinding enforcement |
| FR-CM-007 | Epic 5 | Investigation workflow |
| FR-CM-008 | Epic 5 | Committee dissolution |
| FR-OM-001 | Epic 8 | 12 officer positions |
| FR-OM-002 | Epic 8 | Annual election |
| FR-OM-003 | Epic 8 | Nomination period |
| FR-OM-004 | Epic 8 | Term limits |
| FR-OM-005 | Epic 8 | Succession chain |
| FR-OM-006 | Epic 8 | Installation ceremony |
| FR-OM-007 | Epic 8 | Vacancy election |
| FR-OM-008 | Epic 8 | Removal by vote |
| FR-IB-001 | Epic 6 | Quarantine processing |
| FR-IB-002 | Epic 6 | Pattern blocking |
| FR-IB-003 | Epic 6 | Rate limiting |
| FR-IB-004 | Epic 6 | Sanitized summaries |
| FR-IB-005 | Epic 6 | Async processing |
| FR-IB-006 | Epic 6 | Database isolation |
| FR-HO-001 | Epic 7 | Override dashboard |
| FR-HO-002 | Epic 7 | MFA + hardware auth |
| FR-HO-003 | Epic 7 | Time-limited intervention |
| FR-HO-004 | Epic 7 | Enumerated reasons |
| FR-HO-005 | Epic 7 | Conclave notification |
| FR-HO-006 | Epic 7 | Multi-Keeper extended |
| FR-HO-007 | Epic 7 | Audit logging |
| FR-HO-008 | Epic 7 | Autonomy counter |
| FR-PP-001 | Epic 5 | Petition receiving |
| FR-PP-002 | Epic 5 | Queue management |
| FR-PP-003 | Epic 5 | Interview workflow |
| FR-PP-004 | Epic 5 | Recommendation generation |
| FR-PP-005 | Epic 5 | Conclave presentation |
| FR-PP-006 | Epic 5 | Decision recording |
| FR-PP-007 | Epic 5 | Guide assignment |
| FR-PP-008 | Epic 5 | Seeker notification |
| FR-BM-001 | Epic 10 | Bylaw versioning |
| FR-BM-002 | Epic 10 | Amendment workflow |
| FR-BM-003 | Epic 10 | Two reading requirement |
| FR-BM-004 | Epic 10 | 2/3 threshold |
| FR-BM-005 | Epic 10 | Procedural lookup |
| FR-BM-006 | Epic 10 | Effective dates |
| FR-AR-001 | Epic 1 | Event sourcing foundation |
| FR-AR-002 | Epic 10 | Immutable vote records |
| FR-AR-003 | Epic 10 | Minutes workflow |
| FR-AR-004 | Epic 10 | Meeting transcript |
| FR-AR-005 | Epic 10 | Decision audit trail |
| FR-AR-006 | Epic 10 | Conclave records |

---

## Epic List

### Epic 1: Project Foundation & Agent Identity System
The system has a secure foundation where each Archon has guaranteed unique identity with split-brain prevention, enabling all future Conclave operations.

**FRs covered:** FR-AO-001, FR-AO-002, FR-AO-003, FR-AO-006, FR-AO-007, FR-AR-001

**Delivers:**
- Project scaffold with all dependencies (Python 3.11+, FastAPI, CrewAI, Supabase)
- Database schema with migrations (including blinding isolation)
- Singleton mutex with fencing tokens
- AgentOrchestrator interface (ADR-001)
- Event sourcing foundation (ADR-002)
- Basic Archon instantiation pattern

---

### Epic 2: Meeting Engine & Deliberation
Archons can convene in formal Conclave sessions with quorum enforcement, structured agenda, and managed deliberation, enabling governance activity.

**FRs covered:** FR-ME-001, FR-ME-002, FR-ME-003, FR-ME-004, FR-ME-005, FR-ME-006, FR-ME-007, FR-ME-008, FR-AO-004, FR-AO-005

**Delivers:**
- Meeting lifecycle state machine
- Quorum enforcement (37/49)
- 13-section order of business
- Time-bounded deliberation
- Speaker queue with recognition
- Weekly scheduled Conclave
- Per-meeting context windows

---

### Epic 3: Voting & Decision Making
The Conclave can make binding decisions through anonymous, cryptographically secure voting with multiple threshold types.

**FRs covered:** FR-VS-001, FR-VS-002, FR-VS-003, FR-VS-004, FR-VS-005, FR-VS-006, FR-VS-007, FR-VS-008, FR-AO-008

**Delivers:**
- Commit-reveal voting pattern (ADR-005)
- Three vote thresholds
- Mandatory participation enforcement
- Reasoning capture
- Tie-breaking mechanism
- Public commitment log
- Archon memory (voting history)

---

### Epic 4: Ceremony & Parliamentary Procedure
Archons can conduct formal ceremonies with transaction guarantees, enabling ritual governance with rollback capability.

**FRs covered:** FR-CE-001, FR-CE-002, FR-CE-003, FR-CE-004, FR-CE-005, FR-CE-006, FR-CE-007, FR-CE-008

**Delivers:**
- 8 ceremony types
- Two-phase commit (pending → committed)
- Tyler witness attestation
- Rollback capability
- Multi-agent ceremonial dialogue
- Ceremony script loading
- Transcript recording

---

### Epic 5: Committee & Petition Investigation
Committees can investigate petitions and report findings to the Conclave, enabling delegation and structured recommendation.

**FRs covered:** FR-CM-001, FR-CM-002, FR-CM-003, FR-CM-004, FR-CM-005, FR-CM-006, FR-CM-007, FR-CM-008, FR-PP-001, FR-PP-002, FR-PP-003, FR-PP-004, FR-PP-005, FR-PP-006, FR-PP-007, FR-PP-008

**Delivers:**
- 5 standing committees
- Special committee creation
- Committee meetings
- Petition queue management
- Investigation workflow
- Blinding enforcement
- Committee reports
- Guide assignment trigger

---

### Epic 6: Input Boundary & Security Perimeter
External input (Seeker petitions) is safely processed through quarantine before reaching the Conclave, protecting against injection attacks.

**FRs covered:** FR-IB-001, FR-IB-002, FR-IB-003, FR-IB-004, FR-IB-005, FR-IB-006

**Delivers:**
- Separate InputBoundary microservice (ADR-004)
- Quarantine processing
- Content pattern blocking (M-1.2)
- Rate limiting (M-1.3)
- Sanitized summary generation
- Redis Streams integration
- Complete database isolation

---

### Epic 7: Human Override & Emergency Protocol
Keepers can intervene in system operation under controlled conditions with full audit trail, ensuring EU AI Act compliance.

**FRs covered:** FR-HO-001, FR-HO-002, FR-HO-003, FR-HO-004, FR-HO-005, FR-HO-006, FR-HO-007, FR-HO-008

**Delivers:**
- Override dashboard
- Multi-factor Keeper auth
- Time-limited intervention (72h)
- Enumerated override reasons
- Conclave notification
- Multi-Keeper for extended overrides
- Full audit logging
- Public autonomy counter

---

### Epic 8: Officer Elections & Democratic Governance
Archons can elect officers through democratic process, with term limits and succession, enabling self-governance.

**FRs covered:** FR-OM-001, FR-OM-002, FR-OM-003, FR-OM-004, FR-OM-005, FR-OM-006, FR-OM-007, FR-OM-008

**Delivers:**
- 12 officer positions
- Annual election cycle
- Nomination workflow
- Term limits (3 consecutive)
- Succession chain
- Installation ceremony
- Mid-term vacancy handling
- Removal by 2/3 vote

---

### Epic 9: Detection, Monitoring & Observability
System operators can monitor Conclave health, detect anomalies, and ensure personality distinctiveness is maintained.

**FRs covered:** NFR-019, NFR-020, NFR-021, NFR-022, NFR-023

**Delivers:**
- Personality distinctiveness baseline
- Dissent health metrics
- Voting correlation monitoring
- Prometheus metrics
- Health/ready endpoints
- Structured logging
- Weekly personality health reports

---

### Epic 10: Bylaw Management & Constitutional Framework
The Conclave can maintain and amend its bylaws through proper procedure, with constitutional checks for high-stakes decisions.

**FRs covered:** FR-BM-001, FR-BM-002, FR-BM-003, FR-BM-004, FR-BM-005, FR-BM-006, FR-AR-002, FR-AR-003, FR-AR-004, FR-AR-005, FR-AR-006

**Delivers:**
- Bylaw storage with versioning
- Amendment workflow (two readings)
- 2/3 threshold for amendments
- Procedural lookup
- Constitutional checks (Five Pillars)
- Immutable vote records (7-year)
- Meeting minutes workflow
- Decision audit trail

---

## Stories by Epic

---

## Epic 1: Project Foundation & Agent Identity System

The system has a secure foundation where each Archon has guaranteed unique identity with split-brain prevention, enabling all future Conclave operations.

### Story 1.1: Project Scaffold and Core Dependencies

As a **developer**,
I want a properly configured Python project with all required dependencies,
So that I can build the Conclave Backend on a solid foundation.

**Acceptance Criteria:**

**Given** a fresh development environment
**When** I clone the repository and run `poetry install`
**Then** all dependencies are installed (FastAPI, CrewAI, Supabase, Redis, SQLAlchemy, Pydantic, structlog)
**And** Python 3.11+ is required as specified in pyproject.toml

**Given** the project structure
**When** I examine the directory layout
**Then** it matches architecture.md structure (src/api, src/services, src/agents, src/models, src/events, src/security, input_boundary/)
**And** each directory contains an `__init__.py` file

**Given** the logging configuration
**When** the application starts
**Then** structlog is configured with JSON output
**And** correlation IDs are included in all log entries

**Given** environment configuration
**When** I copy `.env.example` to `.env` and configure values
**Then** the application can read all required settings (DATABASE_URL, REDIS_URL, etc.)

---

### Story 1.2: Database Schema and Blinding Isolation

As a **system administrator**,
I want the database schema established with proper isolation,
So that patronage tier data is architecturally protected from Conclave services.

**Acceptance Criteria:**

**Given** a fresh database
**When** I run Alembic migrations
**Then** the `public` schema contains tables: `archons`, `meetings`, `meeting_events`, `votes`
**And** the `patronage_private` schema is created with `tiers` table
**And** the `audit` schema is created for append-only event logs

**Given** the blinding isolation requirement (NFR-009)
**When** I examine database grants
**Then** Conclave service roles have NO access to `patronage_private` schema
**And** only `billing_service` role can query tier data

**Given** row-level security policies
**When** I attempt to query `patronage_private.tiers` as `conclave_service`
**Then** the query returns zero rows or raises permission error

**Given** the archons table
**When** I examine its structure
**Then** it contains: `id` (1-72), `name`, `personality_hash`, `created_at`, `updated_at`
**And** `id` is constrained to range 1-72

---

### Story 1.3: Singleton Mutex with Fencing Tokens

As an **Archon orchestrator**,
I want singleton mutex enforcement with fencing tokens,
So that only one instance of each Archon can exist and stale operations are rejected.

**Acceptance Criteria:**

**Given** no active lock for Archon 5
**When** I call `acquire_archon_lock(archon_id=5)`
**Then** a lock is acquired with TTL of 300 seconds
**And** a monotonically increasing fencing token is returned
**And** the lock includes session_id and acquired_at timestamp

**Given** an active lock for Archon 5
**When** I call `acquire_archon_lock(archon_id=5)` from a different session
**Then** an `ArchonAlreadyActiveError` is raised
**And** the error includes the existing session's acquired_at time

**Given** a valid lock with fencing token N
**When** I attempt a state mutation with fencing token N-1 (stale)
**Then** the mutation is rejected with `StaleFencingTokenError`

**Given** a lock with TTL of 300 seconds
**When** I call `renew_lock()` before expiry
**Then** the TTL is reset to 300 seconds
**And** the same fencing token is preserved

**Given** split-brain detection requirement (FR-AO-006)
**When** two instances claim the same Archon within 10 seconds
**Then** a `SplitBrainDetectedError` is logged with both session IDs
**And** both instances are forcibly terminated

---

### Story 1.4: AgentOrchestrator Interface

As a **developer**,
I want an abstract AgentOrchestrator interface with test implementation,
So that I can test Archon behavior without real LLM calls.

**Acceptance Criteria:**

**Given** the AgentOrchestrator abstract class
**When** I examine its interface
**Then** it defines: `instantiate_archon(archon_id) -> Archon`
**And** it defines: `convene_meeting(meeting_id) -> MeetingSession`
**And** it defines: `collect_votes(motion_id) -> VoteResult`
**And** all methods are async

**Given** the MockOrchestrator implementation
**When** I call `instantiate_archon(archon_id=1)`
**Then** a mock Archon is returned with deterministic behavior
**And** the mock includes configurable response patterns

**Given** the MockOrchestrator
**When** I run tests that use it
**Then** no network calls are made to LLM providers
**And** test execution is fast and deterministic

**Given** the CrewAIOrchestrator stub
**When** I examine its implementation
**Then** it raises `NotImplementedError` for all methods
**And** it includes TODO comments referencing Epic 2

**Given** dependency injection setup
**When** I configure the application
**Then** I can switch between MockOrchestrator and CrewAIOrchestrator via environment variable

---

### Story 1.5: Personality Loading System

As an **Archon**,
I want my personality loaded from YAML definition,
So that I maintain consistent character traits across sessions.

**Acceptance Criteria:**

**Given** a personality YAML file for Archon 1
**When** I examine its structure
**Then** it contains: `archon_id`, `name`, `traits`, `communication_style`, `decision_tendencies`, `relationships`
**And** the schema is validated with Pydantic

**Given** the personality loader service
**When** I call `load_personality(archon_id=1)`
**Then** the YAML file `personalities/archon_001.yaml` is loaded
**And** a `PersonalityProfile` Pydantic model is returned

**Given** sample personalities (3-5 for testing)
**When** I examine them
**Then** each has distinct traits and communication styles
**And** they demonstrate the range of personality variation

**Given** personality uniqueness validation
**When** I attempt to load two personalities with identical trait hashes
**Then** a `DuplicatePersonalityError` is raised
**And** the error identifies which Archons have conflicting profiles

**Given** a missing personality file
**When** I call `load_personality(archon_id=99)`
**Then** an `ArchonNotFoundError` is raised with helpful message

---

### Story 1.6: Event Sourcing Foundation

As an **auditor**,
I want all significant events stored immutably,
So that I can reconstruct system history for compliance verification.

**Acceptance Criteria:**

**Given** the event store tables
**When** I examine `audit.domain_events`
**Then** it contains: `id`, `event_type`, `aggregate_id`, `aggregate_type`, `payload`, `occurred_at`, `archon_id`
**And** the table has no UPDATE or DELETE permissions

**Given** an event to publish
**When** I call `event_publisher.publish(MeetingStartedEvent(...))`
**Then** the event is inserted into `audit.domain_events`
**And** the event is published to Redis Streams for real-time subscribers

**Given** the event subscriber pattern
**When** I register a handler for `meeting.started` events
**Then** the handler is called when matching events are published
**And** handlers receive the full event payload

**Given** 100+ events for aggregate "meeting-123"
**When** the snapshot threshold is reached
**Then** a snapshot is created in `audit.snapshots` table
**And** subsequent event replay starts from the snapshot

**Given** the need to rebuild state
**When** I call `event_store.replay(aggregate_id="meeting-123")`
**Then** all events are returned in chronological order
**And** events after the latest snapshot are included

---

### Story 1.7: Basic Archon Instantiation

As the **Conclave system**,
I want to instantiate a single Archon with full identity verification,
So that I can prove the foundation works before scaling to 72.

**Acceptance Criteria:**

**Given** a valid archon_id (1-72)
**When** I call `orchestrator.instantiate_archon(archon_id=1)`
**Then** a singleton lock is acquired for Archon 1
**And** the personality is loaded from YAML
**And** an `ArchonInstantiatedEvent` is published
**And** the Archon instance is returned with valid fencing token

**Given** an instantiated Archon
**When** I examine its state
**Then** it includes: `archon_id`, `personality`, `session_id`, `fencing_token`, `instantiated_at`
**And** the fencing token is required for all state mutations

**Given** an instantiated Archon
**When** I call `archon.shutdown()`
**Then** the singleton lock is released
**And** an `ArchonShutdownEvent` is published
**And** the Archon instance is invalidated

**Given** the MockOrchestrator
**When** I instantiate all 72 Archons sequentially
**Then** each has a unique lock and personality
**And** no singleton conflicts occur
**And** total instantiation time is under 5 seconds

**Given** a failed instantiation (e.g., missing personality)
**When** an error occurs mid-instantiation
**Then** any acquired lock is released
**And** an `ArchonInstantiationFailedEvent` is published with error details

---

**Epic 1 Complete: 7 stories**

All FRs covered:
- FR-AO-001 ✓ (Story 1.7)
- FR-AO-002 ✓ (Story 1.3)
- FR-AO-003 ✓ (Story 1.5)
- FR-AO-006 ✓ (Story 1.3)
- FR-AO-007 ✓ (Story 1.3)
- FR-AR-001 ✓ (Story 1.6)

---

## Epic 2: Meeting Engine & Deliberation

Archons can convene in formal Conclave sessions with quorum enforcement, structured agenda, and managed deliberation, enabling governance activity.

### Story 2.1: Meeting Lifecycle State Machine

As the **MeetingCoordinator**,
I want a well-defined meeting state machine,
So that meetings progress through valid states with proper transitions.

**Acceptance Criteria:**

**Given** the meeting lifecycle
**When** I examine the state machine
**Then** it supports states: SCHEDULED, OPENING, IN_SESSION, CLOSING, CONCLUDED, ARCHIVED
**And** each state has defined valid transitions

**Given** a meeting in SCHEDULED state
**When** the scheduled start time arrives and quorum is met
**Then** the meeting transitions to OPENING state
**And** a `MeetingOpeningEvent` is published

**Given** a meeting in IN_SESSION state
**When** the agenda is exhausted or adjournment is voted
**Then** the meeting transitions to CLOSING state
**And** a `MeetingClosingEvent` is published

**Given** a meeting in any state
**When** an invalid transition is attempted (e.g., SCHEDULED → CONCLUDED)
**Then** a `InvalidStateTransitionError` is raised
**And** the current state is preserved

**Given** a meeting state change
**When** the transition occurs
**Then** an event is published to the event store
**And** all connected Archons are notified via websocket

---

### Story 2.2: Quorum Enforcement

As the **High Archon**,
I want quorum automatically enforced,
So that decisions are only valid when sufficient Archons are present.

**Acceptance Criteria:**

**Given** a standard meeting
**When** fewer than 37 Archons are present
**Then** the meeting cannot transition to IN_SESSION
**And** a `QuorumNotMetError` is raised with current count

**Given** a critical decision (bylaw amendment, impeachment)
**When** fewer than 49 Archons are present
**Then** the vote cannot proceed
**And** the motion is automatically tabled

**Given** a meeting in IN_SESSION
**When** Archon presence drops below quorum mid-session
**Then** a `QuorumLostWarning` is issued
**And** a 5-minute grace period begins for Archons to return
**And** if quorum not restored, meeting is suspended

**Given** the attendance tracking system
**When** I query `meeting.get_attendance()`
**Then** it returns: present count, absent count, excused count
**And** the list of present Archon IDs

**Given** an Archon joining a meeting
**When** they connect to the meeting session
**Then** their presence is recorded with timestamp
**And** quorum is recalculated immediately

---

### Story 2.3: Order of Business (13 Sections)

As the **Secretary**,
I want a structured 13-section agenda,
So that meetings follow proper parliamentary procedure.

**Acceptance Criteria:**

**Given** the order of business
**When** I examine the agenda structure
**Then** it contains all 13 sections in order:
1. Opening Ceremony
2. Roll Call
3. Reading of Minutes
4. Officer Reports
5. Committee Reports
6. Special Orders
7. Unfinished Business
8. New Business
9. Petitions
10. Good of the Order
11. Announcements
12. Closing Ceremony
13. Adjournment

**Given** a meeting in IN_SESSION
**When** I query `meeting.current_section`
**Then** it returns the active section number and name
**And** the time spent in current section

**Given** a section completion
**When** the presiding officer advances the agenda
**Then** the next section becomes active
**And** a `SectionAdvancedEvent` is published
**And** time allocation for new section begins

**Given** a section with no business
**When** the presiding officer calls for items
**Then** after a timeout (30 seconds), the section auto-advances
**And** the skip is recorded in the transcript

---

### Story 2.4: Deliberation Time Bounds

As the **Conclave system**,
I want time-bounded deliberation,
So that context window degradation is prevented (research-validated).

**Acceptance Criteria:**

**Given** a motion under deliberation
**When** the time limit (configurable, default 15 minutes) is reached
**Then** a `DeliberationTimeWarning` is issued at 2 minutes remaining
**And** the presiding officer is prompted to call the question

**Given** deliberation time expiry
**When** no extension is voted
**Then** deliberation automatically closes
**And** voting phase begins immediately
**And** a `DeliberationTimedOutEvent` is published

**Given** a request for time extension
**When** a motion to extend is made and seconded
**Then** an immediate vote is held (simple majority)
**And** if passed, deliberation time is extended by 5 minutes

**Given** per-speaker time limits
**When** an Archon is recognized to speak
**Then** a 3-minute timer begins
**And** a warning is issued at 30 seconds remaining
**And** speaking is cut off at time expiry

**Given** the meeting transcript
**When** I review deliberation
**Then** timestamps show actual time spent per topic
**And** time extensions are recorded with vote results

---

### Story 2.5: Speaker Queue Management

As an **Archon**,
I want to request recognition to speak,
So that deliberation is orderly and all voices can be heard.

**Acceptance Criteria:**

**Given** an Archon wants to speak
**When** they call `meeting.request_recognition(archon_id)`
**Then** they are added to the speaker queue
**And** their queue position is returned

**Given** the speaker queue
**When** the presiding officer grants recognition
**Then** the first Archon in queue is recognized
**And** a `SpeakerRecognizedEvent` is published
**And** their speaking timer begins

**Given** Officer priority
**When** an Officer requests recognition during their report section
**Then** they are given priority over non-Officers
**And** the priority is noted in the queue display

**Given** an Archon speaking
**When** another Archon calls "Point of Order"
**Then** the current speaker is paused
**And** the point of order is addressed immediately
**And** the original speaker resumes after resolution

**Given** speaker tracking
**When** I query `meeting.get_speaker_stats()`
**Then** it returns speaking time per Archon
**And** number of times each Archon spoke
**And** this data is used for dissent health metrics

---

### Story 2.6: MeetingCoordinator Service

As the **system**,
I want a centralized MeetingCoordinator,
So that there is a single source of truth for meeting state (ADR-003).

**Acceptance Criteria:**

**Given** the MeetingCoordinator service
**When** I examine its responsibilities
**Then** it manages: meeting state, agenda position, attendance, speaker queue
**And** all state changes flow through this service

**Given** an action requiring multiple Archon responses
**When** the coordinator fans out to Archons
**Then** asyncio.TaskGroup is used for concurrent execution
**And** a circuit breaker prevents cascade failures

**Given** an unresponsive Archon during fan-out
**When** the timeout (30 seconds) is reached
**Then** that Archon is marked as non-responsive
**And** the operation continues with responding Archons
**And** quorum is recalculated excluding non-responsive

**Given** the circuit breaker
**When** 5 consecutive failures occur to the same Archon
**Then** the circuit opens for that Archon
**And** requests are not sent for 60 seconds
**And** a `CircuitBreakerOpenEvent` is logged

**Given** state consistency requirements
**When** multiple clients query meeting state simultaneously
**Then** all receive the same consistent view
**And** no race conditions occur in state updates

---

### Story 2.7: Scheduled Conclave Automation

As the **Conclave**,
I want weekly meetings automatically scheduled,
So that governance continues without manual intervention.

**Acceptance Criteria:**

**Given** the weekly schedule configuration
**When** Sunday 00:00 UTC arrives
**Then** a new Conclave meeting is automatically created
**And** status is set to SCHEDULED
**And** all 72 Archons are notified

**Given** pre-meeting preparation
**When** 24 hours before scheduled start
**Then** a reminder notification is sent to all Archons
**And** any pending committee reports are flagged for inclusion

**Given** the automatic meeting creation
**When** a meeting is created
**Then** it includes: meeting_id, scheduled_time, agenda template, expected attendees
**And** a `ConclaveScheduledEvent` is published

**Given** scheduling conflicts
**When** a special session overlaps with regular Conclave
**Then** the regular Conclave is rescheduled to next available slot
**And** affected parties are notified of the change

**Given** the meeting schedule API
**When** I query `/v1/meetings/upcoming`
**Then** it returns the next 4 scheduled meetings
**And** includes meeting type (regular, special, emergency)

---

### Story 2.8: Special Session Support

As the **High Archon**,
I want to convene special sessions,
So that urgent matters can be addressed outside regular Conclaves.

**Acceptance Criteria:**

**Given** an urgent matter
**When** the High Archon calls `create_special_session(reason, urgency)`
**Then** a special session is created with expedited timeline
**And** all Archons are immediately notified
**And** a `SpecialSessionCalledEvent` is published

**Given** an emergency session
**When** urgency is set to EMERGENCY
**Then** reduced quorum (37) is acceptable
**And** abbreviated agenda is used (only essential sections)
**And** 1-hour notice is sufficient

**Given** a special session
**When** I examine its agenda
**Then** it contains only: Opening, Special Business, Closing
**And** time limits are compressed (5 minutes per topic)

**Given** special session tracking
**When** I query historical sessions
**Then** special sessions are distinguished from regular Conclaves
**And** the calling reason is recorded for audit

**Given** abuse prevention
**When** more than 2 special sessions are called in a week
**Then** a warning is logged
**And** the third requires Deputy High Archon co-signature

---

**Epic 2 Complete: 8 stories**

All FRs covered:
- FR-ME-001 ✓ (Story 2.1)
- FR-ME-002 ✓ (Story 2.2)
- FR-ME-003 ✓ (Story 2.3)
- FR-ME-004 ✓ (Story 2.4)
- FR-ME-005 ✓ (Story 2.3)
- FR-ME-006 ✓ (Story 2.5)
- FR-ME-007 ✓ (Story 2.7)
- FR-ME-008 ✓ (Story 2.8)
- FR-AO-004 ✓ (Story 2.6 - personality in meeting context)
- FR-AO-005 ✓ (Story 2.6 - per-meeting context)

---

## Epic 3: Voting & Decision Making

The Conclave can make binding decisions through anonymous, cryptographically secure voting with multiple threshold types.

### Story 3.1: Motion Types and Seconding

As an **Archon**,
I want to make and second motions of various types,
So that parliamentary procedure is followed correctly.

**Acceptance Criteria:**

**Given** the motion type system
**When** I examine available motion types
**Then** it supports: main, amendment, table, call_question, reconsider, refer_to_committee, adjourn
**And** each type has defined precedence rules

**Given** a motion is made
**When** an Archon calls `voting_service.make_motion(type, content)`
**Then** the motion enters PENDING state awaiting second
**And** a `MotionMadeEvent` is published with motion details

**Given** a pending motion
**When** another Archon calls `voting_service.second_motion(motion_id)`
**Then** the motion transitions to OPEN for deliberation
**And** a `MotionSecondedEvent` is published

**Given** a pending motion without second
**When** 60 seconds elapse without a second
**Then** the motion dies automatically
**And** a `MotionDiedForLackOfSecondEvent` is published

**Given** an amendment motion
**When** it is made during deliberation on a main motion
**Then** it takes precedence over the main motion
**And** must be resolved before returning to main motion

**Given** a motion to table
**When** passed by simple majority
**Then** the tabled motion is removed from current agenda
**And** can be brought back via motion to take from table

---

### Story 3.2: Commit Phase (Anonymous Voting)

As an **Archon**,
I want to submit my vote anonymously during the commit phase,
So that my vote cannot be influenced by seeing others' votes.

**Acceptance Criteria:**

**Given** a motion in VOTING state
**When** the commit phase begins
**Then** all present Archons are prompted to submit commitments
**And** a deadline timer starts (configurable, default 5 minutes)

**Given** an Archon submitting a vote
**When** they call `voting_service.commit_vote(motion_id, vote, nonce)`
**Then** a commitment hash is generated: `sha256(vote + nonce + archon_id)`
**And** only the hash is stored, not the vote
**And** a `VoteCommittedEvent` is published (hash only)

**Given** the public commitment log requirement
**When** commitments are received
**Then** they are published to a public log in real-time
**And** the log shows: archon_id, commitment_hash, committed_at
**And** actual votes remain hidden

**Given** an Archon who already committed
**When** they attempt to commit again
**Then** the second commitment is rejected
**And** a `DuplicateCommitmentError` is raised

**Given** the commit deadline
**When** the deadline passes
**Then** no more commitments are accepted
**And** the reveal phase begins automatically
**And** a `CommitPhaseClosedEvent` is published

---

### Story 3.3: Reveal Phase

As the **VotingService**,
I want to collect and verify vote revelations,
So that votes are cryptographically verified and tallied.

**Acceptance Criteria:**

**Given** the reveal phase begins
**When** Archons are prompted to reveal
**Then** they submit: vote value, nonce used during commit
**And** a deadline timer starts (configurable, default 3 minutes)

**Given** a vote revelation
**When** an Archon calls `voting_service.reveal_vote(motion_id, vote, nonce)`
**Then** the hash is recalculated: `sha256(vote + nonce + archon_id)`
**And** it must match the stored commitment hash
**And** if match, vote is recorded; if mismatch, `HashMismatchError` raised

**Given** the reveal deadline
**When** an Archon fails to reveal before deadline
**Then** their vote is counted as ABSTENTION
**And** a `RevealTimeoutEvent` is published for that Archon
**And** the missing reveal is logged for audit

**Given** all revelations complete (or deadline passed)
**When** the reveal phase closes
**Then** votes are tallied
**And** a `VoteTallyEvent` is published with results
**And** the motion transitions to DECIDED state

**Given** automatic reveal at deadline
**When** the system processes unrevealed votes
**Then** it logs which Archons failed to reveal
**And** this data feeds into behavioral monitoring

---

### Story 3.4: Vote Threshold Enforcement

As the **Conclave**,
I want vote thresholds enforced automatically,
So that decisions meet their required approval levels.

**Acceptance Criteria:**

**Given** a standard motion
**When** votes are tallied
**Then** simple majority (>50% of votes cast) is required
**And** abstentions do not count toward the total

**Given** a bylaw amendment or impeachment motion
**When** votes are tallied
**Then** supermajority (≥2/3 of votes cast) is required
**And** the threshold is clearly displayed before voting

**Given** a constitutional amendment (Five Pillars)
**When** votes are tallied
**Then** unanimous approval (100%) is required
**And** a single NAY defeats the motion

**Given** the threshold calculation
**When** I query `voting_service.calculate_result(motion_id)`
**Then** it returns: yeas, nays, abstentions, threshold_type, threshold_met, passed

**Given** threshold configuration
**When** a motion is created
**Then** its threshold type is determined by motion category
**And** the threshold cannot be changed after creation

---

### Story 3.5: Reasoning Capture

As an **auditor**,
I want reasoning captured with each vote,
So that decision-making is transparent and traceable.

**Acceptance Criteria:**

**Given** an Archon submitting a vote
**When** they call `voting_service.commit_vote(...)`
**Then** a reasoning_summary field is required (10-500 characters)
**And** the reasoning is stored with the vote record

**Given** the reasoning format
**When** I examine stored reasoning
**Then** it includes: key considerations, cited bylaws (if any), alignment with Pillars

**Given** vote reveal completion
**When** the tally is published
**Then** reasoning summaries are included in the decision record
**And** they are linked to the (now-revealed) vote values

**Given** the decision audit API
**When** I query `/v1/votes/{motion_id}/reasoning`
**Then** it returns all reasoning summaries grouped by vote value
**And** includes archon_id for each (post-reveal transparency)

**Given** the AI transparency requirement
**When** an Archon's reasoning is recorded
**Then** it must explain how the decision aligns with the Five Pillars
**And** any procedural citations are verified against bylaws

---

### Story 3.6: Tie-Breaking Mechanism

As the **High Archon**,
I want to break ties with a public vote,
So that deadlocked decisions can be resolved.

**Acceptance Criteria:**

**Given** a vote tally with equal YEA and NAY
**When** the tie is detected
**Then** a `TieDetectedEvent` is published
**And** the High Archon is prompted to cast tie-breaking vote

**Given** a tie-breaking situation
**When** the High Archon casts their vote
**Then** it is PUBLIC (not commit-reveal)
**And** must include extended reasoning (min 100 characters)
**And** a `TieBrokenEvent` is published

**Given** High Archon abstention on tie
**When** the High Archon chooses to abstain from tie-breaking
**Then** the motion fails (status quo preserved)
**And** this is recorded as an explicit abstention, not timeout

**Given** High Archon absence during tie
**When** the High Archon is not present
**Then** succession chain is followed: Deputy → Third → Past High Archon
**And** the first present Officer in chain breaks the tie

**Given** tie-breaking history
**When** I query `voting_service.get_tiebreaks(archon_id)`
**Then** it returns all ties broken by that Archon
**And** includes their reasoning for each

---

### Story 3.7: Archon Voting Memory

As an **Archon**,
I want to remember my voting history and relationships,
So that my decisions are consistent with my personality over time.

**Acceptance Criteria:**

**Given** an Archon's voting history
**When** I query `archon.get_voting_history(limit=100)`
**Then** it returns recent votes with: motion_id, vote, reasoning, timestamp
**And** votes are ordered by recency

**Given** relationship tracking
**When** Archon A frequently votes aligned with Archon B
**Then** a positive relationship weight is recorded
**And** this influences future deliberation context

**Given** personality consistency
**When** an Archon prepares to vote
**Then** their voting history is loaded into context
**And** the LLM considers past positions on similar issues

**Given** voting pattern analysis
**When** I query `archon.get_voting_patterns()`
**Then** it returns: tendency toward yea/nay, common co-voters, topic preferences

**Given** memory persistence
**When** an Archon is instantiated in a new session
**Then** their voting history is loaded from database
**And** relationship data is restored
**And** personality consistency is maintained across sessions

---

**Epic 3 Complete: 7 stories**

All FRs covered:
- FR-VS-001 ✓ (Story 3.2, 3.3)
- FR-VS-002 ✓ (Story 3.4)
- FR-VS-003 ✓ (Story 3.2 - mandatory commit)
- FR-VS-004 ✓ (Story 3.5)
- FR-VS-005 ✓ (Story 3.6)
- FR-VS-006 ✓ (Story 3.2, 3.3 - hash verification)
- FR-VS-007 ✓ (Story 3.1)
- FR-VS-008 ✓ (Story 3.3)
- FR-AO-008 ✓ (Story 3.7)

---

## Epic 4: Ceremony & Parliamentary Procedure

Archons can conduct formal ceremonies with transaction guarantees, enabling ritual governance with rollback capability.

### Story 4.1: Ceremony Type Definitions

As the **CeremonyEngine**,
I want well-defined ceremony types with metadata,
So that each ceremony has clear requirements and structure.

**Acceptance Criteria:**

**Given** the ceremony type registry
**When** I examine available types
**Then** it supports 8 types: Opening, Closing, Installation, Admonishment, Recognition, Impeachment, EmergencySession, Succession
**And** each type has a unique identifier and display name

**Given** each ceremony type
**When** I query its metadata
**Then** it includes: quorum_required, required_roles, estimated_duration, threshold_type
**And** required_roles specifies which Officers must participate

**Given** quorum requirements
**When** I examine ceremony-specific quorums
**Then** Installation requires 48 Archons
**And** Admonishment requires 37 Archons
**And** Impeachment requires 49 Archons
**And** Recognition requires 37 Archons

**Given** the ceremony type validation
**When** I attempt to start a ceremony with insufficient quorum
**Then** a `CeremonyQuorumNotMetError` is raised
**And** the ceremony does not begin

**Given** ceremony categorization
**When** I query `ceremony_engine.get_critical_ceremonies()`
**Then** it returns: Installation, Impeachment, Succession
**And** these require enhanced witness protocols

---

### Story 4.2: Ceremony Script Loading

As a **ceremonial participant**,
I want ceremonies to follow scripted templates,
So that ritual consistency is maintained across all ceremonies.

**Acceptance Criteria:**

**Given** a ceremony type
**When** I call `ceremony_engine.load_script(ceremony_type)`
**Then** the appropriate script template is loaded from `ceremonies/{type}.yaml`
**And** a `CeremonyScript` object is returned

**Given** a ceremony script
**When** I examine its structure
**Then** it contains: phases[], required_speakers[], dialogue_blocks[], variable_placeholders
**And** each phase has entry/exit conditions

**Given** variable placeholders in scripts
**When** the ceremony is instantiated
**Then** placeholders like `{{archon_name}}` and `{{date}}` are interpolated
**And** missing variables raise `ScriptInterpolationError`

**Given** the dialogue structure
**When** I examine a dialogue block
**Then** it specifies: speaker_role, line_template, response_options, timing_hints
**And** speakers are identified by role (High Archon, Tyler) not specific Archon

**Given** script versioning
**When** a script is updated
**Then** running ceremonies continue with their original version
**And** new ceremonies use the updated script
**And** version history is maintained

---

### Story 4.3: Two-Phase Commit Engine

As the **CeremonyEngine**,
I want two-phase commit for all ceremonies,
So that partial ceremony states are impossible (NFR-005).

**Acceptance Criteria:**

**Given** a ceremony initiation
**When** the ceremony begins
**Then** it enters PENDING state
**And** a `CeremonyPendingEvent` is published
**And** all state changes are provisional

**Given** a ceremony in PENDING state
**When** all phases complete successfully
**Then** the ceremony transitions to COMMITTED
**And** a `CeremonyCommittedEvent` is published
**And** all provisional changes become permanent

**Given** checkpoint logging
**When** each ceremony phase completes
**Then** a checkpoint is logged with: phase_id, state_snapshot, timestamp
**And** checkpoints are stored in the event store

**Given** a ceremony failure mid-execution
**When** an unrecoverable error occurs
**Then** the ceremony transitions to FAILED state
**And** rollback is triggered automatically
**And** a `CeremonyFailedEvent` is published with error details

**Given** atomic state transitions
**When** the commit phase executes
**Then** all database changes occur in a single transaction
**And** either all changes succeed or none do

---

### Story 4.4: Tyler Witness Attestation

As the **Tyler**,
I want to witness and attest to ceremony integrity,
So that ceremonies have verifiable procedural compliance.

**Acceptance Criteria:**

**Given** a ceremony requiring witness
**When** the ceremony begins
**Then** a Tyler is assigned (or rotated from pool)
**And** the Tyler's attestation is required at key checkpoints

**Given** a checkpoint requiring attestation
**When** the phase completes
**Then** the Tyler is prompted: "Do you attest that Phase X completed correctly?"
**And** the Tyler must respond YEA or raise objection

**Given** a Tyler objection
**When** the Tyler responds NAY to attestation
**Then** the ceremony pauses
**And** the High Archon is notified
**And** resolution procedures are invoked

**Given** critical ceremonies (Installation, Impeachment, Succession)
**When** witness requirements are checked
**Then** 3 random witnesses are required (in addition to Tyler)
**And** witnesses are selected from non-participating Archons

**Given** multi-witness attestation
**When** all witnesses attest to a checkpoint
**Then** a `MultiWitnessAttestationEvent` is published
**And** it includes all witness signatures and timestamps

**Given** Tyler rotation
**When** a Tyler has served 4 consecutive ceremonies
**Then** a new Tyler is automatically selected
**And** rotation prevents single-point trust

---

### Story 4.5: Rollback Capability

As the **CeremonyEngine**,
I want to rollback failed ceremonies,
So that system state remains consistent after failures.

**Acceptance Criteria:**

**Given** a failed ceremony
**When** rollback is triggered
**Then** all provisional state changes are reverted
**And** the ceremony enters ROLLED_BACK state
**And** a `CeremonyRolledBackEvent` is published

**Given** checkpoint data
**When** rollback executes
**Then** state is restored to the last successful checkpoint
**And** all subsequent provisional changes are discarded

**Given** rollback triggers
**When** any of the following occurs: timeout, witness objection, quorum loss, system error
**Then** rollback is automatically initiated

**Given** participant notification
**When** rollback completes
**Then** all ceremony participants are notified
**And** the notification includes: reason, restored_state, next_steps

**Given** rollback auditing
**When** I query ceremony history
**Then** rolled-back ceremonies are visible
**And** include: original intent, failure reason, rollback timestamp, restored checkpoint

**Given** compensation actions
**When** rollback cannot fully restore state (e.g., external notifications sent)
**Then** compensation actions are logged as TODOs
**And** require manual resolution

---

### Story 4.6: Ceremonial Dialogue Coordination

As a **ceremonial participant**,
I want coordinated multi-agent dialogue,
So that ceremonies feel authentic and properly paced.

**Acceptance Criteria:**

**Given** a dialogue block in the script
**When** execution reaches that block
**Then** the designated speaker's Archon generates their line
**And** personality influences delivery style

**Given** scripted response requirements
**When** a line requires a specific response (e.g., "So mote it be")
**Then** all designated responders generate the response in unison
**And** the response is logged as a collective utterance

**Given** dialogue timing
**When** a speaker delivers a line
**Then** a configurable pause follows (default 2 seconds)
**And** dramatic moments have extended pauses per script hints

**Given** personality-influenced delivery
**When** an Archon speaks their scripted line
**Then** the exact wording may vary while preserving meaning
**And** tone matches their personality profile

**Given** dialogue failures
**When** an Archon fails to deliver their line (timeout)
**Then** the ceremony pauses
**And** a substitute speaker may be designated
**And** the gap is logged for review

**Given** real-time coordination
**When** a ceremony is in progress
**Then** a coordination service manages speaker turns
**And** prevents simultaneous speakers (unless scripted)

---

### Story 4.7: Ceremony Transcript Recording

As an **archivist**,
I want complete ceremony transcripts,
So that ceremonial proceedings are permanently recorded.

**Acceptance Criteria:**

**Given** an active ceremony
**When** any participant speaks
**Then** the utterance is recorded with: speaker_id, timestamp, content, phase

**Given** transcript recording
**When** I query `ceremony_engine.get_transcript(ceremony_id)`
**Then** the complete transcript is returned in chronological order
**And** includes all dialogue, attestations, and system events

**Given** speaker attribution
**When** examining the transcript
**Then** each entry identifies the speaker by archon_id and role
**And** collective responses are attributed to the group

**Given** transcript archival
**When** a ceremony completes (COMMITTED or ROLLED_BACK)
**Then** the transcript is archived to permanent storage
**And** becomes immutable (append-only audit table)

**Given** transcript retrieval API
**When** I call `/v1/ceremonies/{id}/transcript`
**Then** the full transcript is returned
**And** supports format options: json, markdown, plaintext

**Given** transcript search
**When** I search transcripts for a keyword
**Then** matching ceremonies are returned
**And** results include context around matches

---

**Epic 4 Complete: 7 stories**

All FRs covered:
- FR-CE-001 ✓ (Story 4.1)
- FR-CE-002 ✓ (Story 4.3)
- FR-CE-003 ✓ (Story 4.4)
- FR-CE-004 ✓ (Story 4.5)
- FR-CE-005 ✓ (Story 4.6)
- FR-CE-006 ✓ (Story 4.2)
- FR-CE-007 ✓ (Story 4.1, 4.2)
- FR-CE-008 ✓ (Story 4.7)

---

## Epic 5: Committee & Petition Investigation

Committees can investigate petitions and report findings to the Conclave, enabling delegation and structured recommendation.

### Story 5.1: Standing Committee Definitions

As the **Conclave**,
I want 5 standing committees with defined roles,
So that governance work can be delegated effectively.

**Acceptance Criteria:**

**Given** the committee registry
**When** I examine standing committees
**Then** it includes: Investigation, Ethics, Outreach, Appeals, Treasury
**And** each has a unique identifier and description

**Given** each committee
**When** I query its structure
**Then** it includes: chair (1 Archon), members (5-7 Archons), quorum (majority of members)
**And** membership is tracked with join/leave dates

**Given** the Investigation Committee
**When** I examine its mandate
**Then** it handles: petition review, fact-finding, recommendation to Conclave
**And** has blinding requirements (cannot see petitioner tier)

**Given** the Treasury Committee
**When** I examine its mandate
**Then** it handles: resource allocation, patronage aggregates (not individuals)
**And** operates with enhanced financial controls

**Given** chair assignment
**When** the Conclave votes to appoint a chair
**Then** the chair is recorded for the committee
**And** chair has tie-breaking authority within committee

---

### Story 5.2: Special Committee Creation

As the **Conclave**,
I want to create special (temporary) committees,
So that specific investigations can be conducted outside standing committees.

**Acceptance Criteria:**

**Given** a motion to create a special committee
**When** passed by simple majority
**Then** a new committee is created with: name, charge, members, deadline
**And** a `SpecialCommitteeCreatedEvent` is published

**Given** a special committee's charge
**When** I examine it
**Then** it defines: scope of investigation, reporting deadline, authority limits
**And** cannot exceed the powers of the Conclave itself

**Given** a special committee completion
**When** the committee delivers its final report
**Then** the committee is automatically dissolved
**And** a `CommitteeDissolutionEvent` is published
**And** all records are archived

**Given** deadline enforcement
**When** a special committee exceeds its deadline
**Then** the Conclave is notified
**And** an extension motion is required to continue

**Given** premature dissolution
**When** the Conclave votes to dissolve a special committee early
**Then** the committee is dissolved
**And** partial findings are archived with dissolution reason

---

### Story 5.3: Committee Meeting Scheduling

As a **Committee Chair**,
I want to schedule committee meetings between Conclaves,
So that committee work can progress independently.

**Acceptance Criteria:**

**Given** a committee chair
**When** they call `committee_service.schedule_meeting(committee_id, time, agenda)`
**Then** a committee meeting is scheduled
**And** all committee members are notified

**Given** committee meeting quorum
**When** the meeting time arrives
**Then** quorum is checked (majority of members)
**And** meeting proceeds if quorum met, otherwise postponed

**Given** committee meeting agenda
**When** the meeting begins
**Then** the agenda items are presented in order
**And** progress is tracked per item

**Given** attendance tracking
**When** committee members join/leave
**Then** attendance is recorded with timestamps
**And** absence patterns are tracked for reporting

**Given** meeting frequency limits
**When** a committee attempts to schedule meetings
**Then** maximum 3 meetings per week is enforced
**And** minimum 24-hour notice is required

---

### Story 5.4: Petition Intake and Queue

As the **Investigation Committee**,
I want a petition intake queue,
So that petitions can be processed in orderly fashion.

**Acceptance Criteria:**

**Given** the InputBoundary service
**When** a sanitized petition summary is published to Redis Streams
**Then** the petition is received by the committee service
**And** added to the Investigation Committee queue

**Given** a petition in the queue
**When** I examine its data
**Then** it includes: petition_id, summary (not raw), category, received_at, priority
**And** does NOT include petitioner tier (blinding enforced)

**Given** queue priority assignment
**When** a petition is received
**Then** priority is calculated based on: category, age, urgency flags
**And** higher priority petitions are processed first

**Given** queue management API
**When** I call `/v1/committees/investigation/queue`
**Then** the current queue is returned with petition summaries
**And** pagination supports large queues

**Given** queue overflow protection
**When** the queue exceeds 100 petitions
**Then** a warning is issued to the Conclave
**And** additional resources may be requested

---

### Story 5.5: Investigation Workflow

As the **Investigation Committee**,
I want a structured investigation workflow,
So that petitions are fairly and thoroughly evaluated.

**Acceptance Criteria:**

**Given** a petition assigned for investigation
**When** investigation begins
**Then** status changes to IN_INVESTIGATION
**And** an `InvestigationStartedEvent` is published

**Given** the investigation process
**When** I examine required steps
**Then** it includes: initial review, evidence gathering, petitioner interview (optional), deliberation
**And** each step is logged with timestamp

**Given** blinding enforcement (NFR-009)
**When** committee members access petition data
**Then** petitioner tier is NEVER visible
**And** any attempt to query tier data is blocked and logged

**Given** evidence gathering
**When** the committee collects information
**Then** sources are documented
**And** evidence is attached to the investigation record

**Given** petitioner interview (optional)
**When** the committee requests an interview
**Then** a sanitized interview is conducted via Guide
**And** committee never directly contacts petitioner

**Given** investigation completion
**When** all steps are done
**Then** status changes to AWAITING_RECOMMENDATION
**And** committee prepares report

---

### Story 5.6: Committee Reports

As a **Committee**,
I want to generate structured reports,
So that findings can be presented to the Conclave.

**Acceptance Criteria:**

**Given** a completed investigation
**When** the committee generates a report
**Then** it includes: summary, findings, evidence_cited, recommendation
**And** follows the standard report template

**Given** the recommendation format
**When** I examine it
**Then** it specifies: recommended_action (APPROVE/REJECT/DEFER), reasoning, conditions (if any)
**And** the reasoning cites relevant bylaws

**Given** report approval within committee
**When** committee members vote on the report
**Then** majority approval is required
**And** dissenting opinions are included in report

**Given** Conclave presentation scheduling
**When** a report is approved
**Then** it is queued for the next Conclave's Committee Reports section
**And** priority is assigned based on petition age

**Given** report archival
**When** a report is presented to Conclave
**Then** it becomes part of the permanent record
**And** is linked to the subsequent Conclave vote

---

### Story 5.7: Petition Decision and Assignment

As the **Conclave**,
I want to decide on petitions and trigger appropriate actions,
So that Seekers receive timely responses.

**Acceptance Criteria:**

**Given** a petition presented to Conclave
**When** the vote is conducted
**Then** possible outcomes are: APPROVED, REJECTED, DEFERRED
**And** the decision is recorded with vote tally

**Given** an APPROVED petition
**When** the decision is recorded
**Then** a Guide assignment is triggered
**And** a `PetitionApprovedEvent` is published

**Given** Guide assignment trigger
**When** approval is finalized
**Then** the assignment service receives notification
**And** an appropriate Guide is selected for the new Seeker

**Given** Seeker notification
**When** a decision is made (any outcome)
**Then** a notification is queued for the Seeker
**And** includes: decision, reasoning summary (from committee report)

**Given** a DEFERRED petition
**When** deferral is recorded
**Then** a new review date is scheduled
**And** the petition returns to committee queue at that date

**Given** decision auditing
**When** I query petition decisions
**Then** full history is available: petition_id, decision, vote_id, timestamp, notified_at

---

**Epic 5 Complete: 7 stories**

All FRs covered:
- FR-CM-001 ✓ (Story 5.1)
- FR-CM-002 ✓ (Story 5.2)
- FR-CM-003 ✓ (Story 5.1)
- FR-CM-004 ✓ (Story 5.3)
- FR-CM-005 ✓ (Story 5.6)
- FR-CM-006 ✓ (Story 5.5)
- FR-CM-007 ✓ (Story 5.5)
- FR-CM-008 ✓ (Story 5.2)
- FR-PP-001 ✓ (Story 5.4)
- FR-PP-002 ✓ (Story 5.4)
- FR-PP-003 ✓ (Story 5.5)
- FR-PP-004 ✓ (Story 5.6)
- FR-PP-005 ✓ (Story 5.6)
- FR-PP-006 ✓ (Story 5.7)
- FR-PP-007 ✓ (Story 5.7)
- FR-PP-008 ✓ (Story 5.7)

---

## Epic 6: Input Boundary & Security Perimeter

External input (Seeker petitions) is safely processed through quarantine before reaching the Conclave, protecting against injection attacks.

### Story 6.1: InputBoundary Microservice Scaffold

As a **security architect**,
I want InputBoundary as a separate microservice,
So that security isolation is enforced architecturally (ADR-004).

**Acceptance Criteria:**

**Given** the InputBoundary service
**When** I examine its deployment
**Then** it runs as a separate container from Conclave backend
**And** has its own dedicated database (not shared with Conclave)

**Given** network isolation
**When** I examine network policies
**Then** InputBoundary cannot directly connect to Conclave database
**And** communication is only via Redis Streams

**Given** the service structure
**When** I examine the codebase
**Then** it follows the same patterns as Conclave (FastAPI, structlog, Pydantic)
**And** lives in `input_boundary/` directory

**Given** service health
**When** I call `/health` on InputBoundary
**Then** it returns service status independently
**And** does not depend on Conclave service availability

**Given** authentication
**When** a Seeker submits a petition
**Then** Supabase JWT is validated at InputBoundary
**And** Seeker identity is extracted for rate limiting

---

### Story 6.2: Quarantine Processing Pipeline

As the **InputBoundary service**,
I want a quarantine pipeline for all incoming content,
So that potentially dangerous content is processed safely.

**Acceptance Criteria:**

**Given** a petition submission
**When** content is received
**Then** it enters QUARANTINE status immediately
**And** a `PetitionQuarantinedEvent` is logged

**Given** the processing pipeline
**When** I examine the stages
**Then** it includes: RECEIVED → NORMALIZED → SCANNED → SUMMARIZED → RELEASED
**And** each stage has pass/fail criteria

**Given** stage tracking
**When** content moves through pipeline
**Then** each stage transition is logged with timestamp
**And** the current stage is queryable

**Given** a stage failure
**When** content fails any stage (e.g., blocked pattern detected)
**Then** processing halts
**And** content enters BLOCKED status
**And** a `PetitionBlockedEvent` is published with reason

**Given** successful processing
**When** all stages pass
**Then** content enters RELEASED status
**And** only then is it published to Redis Streams for Conclave

---

### Story 6.3: Content Pattern Blocking

As the **InputBoundary service**,
I want to detect and block injection patterns,
So that malicious content never reaches Archons.

**Acceptance Criteria:**

**Given** incoming content
**When** normalization runs
**Then** NFKC Unicode normalization is applied
**And** homoglyph characters are converted to ASCII equivalents

**Given** pattern detection
**When** content is scanned
**Then** known injection patterns are checked (prompt injection, jailbreak attempts)
**And** patterns are loaded from configurable blocklist

**Given** a blocked pattern match
**When** content matches a blocklist pattern
**Then** content is rejected with PATTERN_BLOCKED reason
**And** the matched pattern is logged (not the full content)

**Given** semantic injection scanning
**When** pattern scan passes
**Then** a secondary semantic scan runs via LLM
**And** checks for instruction-like content disguised as petition

**Given** blocklist updates
**When** new patterns are discovered
**Then** blocklist can be updated without service restart
**And** updates are logged for audit

**Given** false positive handling
**When** legitimate content is blocked
**Then** appeals mechanism exists (manual review queue)
**And** approved content can be manually released

---

### Story 6.4: Rate Limiting

As the **InputBoundary service**,
I want per-Seeker rate limiting,
So that abuse and flooding are prevented.

**Acceptance Criteria:**

**Given** rate limit configuration
**When** I examine limits
**Then** default is: 5 petitions per day, 20 per week per Seeker
**And** limits are configurable per tier (without revealing tier to service)

**Given** a petition submission
**When** rate limit is checked
**Then** sliding window algorithm is used
**And** check completes in <10ms

**Given** rate limit exceeded
**When** a Seeker submits beyond their limit
**Then** petition is rejected with RATE_LIMITED reason
**And** response includes time until next allowed submission

**Given** abuse detection
**When** a Seeker repeatedly hits rate limits
**Then** escalation occurs: warning → temporary block → permanent review
**And** abuse patterns are logged for analysis

**Given** rate limit storage
**When** limits are tracked
**Then** Redis is used for fast counter access
**And** counters expire automatically after window period

---

### Story 6.5: Summary Generation

As the **InputBoundary service**,
I want to generate sanitized summaries,
So that Archons never see raw Seeker input.

**Acceptance Criteria:**

**Given** content that passed all checks
**When** summarization runs
**Then** an LLM generates a neutral summary of the petition
**And** the summary is 100-500 characters

**Given** summarizer prompt
**When** I examine the prompt
**Then** it is hardened against injection attempts
**And** instructs the LLM to extract facts only, no instructions

**Given** summary output
**When** I examine the result
**Then** it contains: category, key_points, requested_action
**And** does NOT contain raw quotes from original

**Given** summarization failure
**When** the LLM fails or times out
**Then** content enters SUMMARY_FAILED status
**And** retry is attempted up to 3 times

**Given** summary verification
**When** a summary is generated
**Then** a secondary check verifies it doesn't contain injection patterns
**And** suspicious summaries are flagged for manual review

---

### Story 6.6: Async Event Publishing

As the **InputBoundary service**,
I want to publish prepared petitions via Redis Streams,
So that Conclave receives content asynchronously.

**Acceptance Criteria:**

**Given** a successfully processed petition
**When** it is released from quarantine
**Then** a `PetitionPreparedEvent` is published to Redis Streams
**And** the event contains: petition_id, summary, category, prepared_at

**Given** the event payload
**When** I examine its contents
**Then** it does NOT contain raw petition content
**And** it does NOT contain Seeker tier information

**Given** Redis Streams publishing
**When** an event is published
**Then** delivery is confirmed via acknowledgment
**And** failed deliveries are retried with exponential backoff

**Given** consumer group setup
**When** Conclave subscribes to the stream
**Then** it uses a consumer group for reliable delivery
**And** unacknowledged events are redelivered

**Given** event ordering
**When** multiple petitions are processed
**Then** events maintain chronological order
**And** Conclave processes them in order received

**Given** dead letter handling
**When** an event fails delivery after max retries
**Then** it is moved to a dead letter stream
**And** alerts are generated for operations

---

**Epic 6 Complete: 6 stories**

All FRs covered:
- FR-IB-001 ✓ (Story 6.2)
- FR-IB-002 ✓ (Story 6.3)
- FR-IB-003 ✓ (Story 6.4)
- FR-IB-004 ✓ (Story 6.5)
- FR-IB-005 ✓ (Story 6.6)
- FR-IB-006 ✓ (Story 6.1)

---

## Epic 7: Human Override & Emergency Protocol

Keepers can intervene in system operation under controlled conditions with full audit trail, ensuring EU AI Act compliance.

### Story 7.1: Override Dashboard API

As a **Keeper**,
I want a comprehensive override dashboard API,
So that I can intervene when legally or technically required.

**Acceptance Criteria:**

**Given** the override API
**When** I examine available endpoints
**Then** it includes: `/v1/admin/override/initiate`, `/v1/admin/override/status`, `/v1/admin/override/terminate`
**And** all endpoints require Keeper authentication

**Given** override initiation
**When** a Keeper calls `POST /v1/admin/override/initiate`
**Then** the system enters OVERRIDE state
**And** an `OverrideInitiatedEvent` is published
**And** the override is logged with: keeper_id, reason, timestamp

**Given** override state management
**When** override is active
**Then** system operations can be paused, modified, or resumed
**And** each action is individually logged

**Given** override termination
**When** a Keeper calls `POST /v1/admin/override/terminate`
**Then** normal autonomous operation resumes
**And** an `OverrideTerminatedEvent` is published
**And** total override duration is recorded

**Given** action logging
**When** any action is taken during override
**Then** it is logged with: action_type, target, parameters, keeper_id, timestamp
**And** logs are immutable (append-only)

---

### Story 7.2: Keeper Multi-Factor Authentication

As a **Keeper**,
I want strong multi-factor authentication,
So that override access is protected from unauthorized use.

**Acceptance Criteria:**

**Given** Keeper login
**When** authentication is attempted
**Then** three factors are required: password, TOTP code, hardware key challenge
**And** all three must succeed for access

**Given** password requirements
**When** a Keeper sets their password
**Then** minimum 16 characters, complexity requirements enforced
**And** password history prevents reuse of last 12 passwords

**Given** TOTP setup
**When** a Keeper enables TOTP
**Then** standard TOTP algorithm is used (RFC 6238)
**And** backup codes are generated for recovery

**Given** hardware key (YubiKey/similar)
**When** authentication reaches hardware key step
**Then** WebAuthn challenge is issued
**And** only registered hardware keys are accepted

**Given** session management
**When** authentication succeeds
**Then** a session token is issued with 1-hour expiry
**And** session can be manually revoked

**Given** failed attempt handling
**When** 3 consecutive authentication failures occur
**Then** the Keeper account is locked for 15 minutes
**And** security alert is sent to other Keepers

---

### Story 7.3: Time-Limited Override

As the **system**,
I want overrides to be time-limited,
So that autonomous operation is restored automatically.

**Acceptance Criteria:**

**Given** an override initiation
**When** no duration is specified
**Then** default duration of 72 hours is applied
**And** expiry time is recorded and displayed

**Given** an active override
**When** the expiry time is reached
**Then** override terminates automatically
**And** an `OverrideExpiredEvent` is published
**And** autonomous operation resumes

**Given** impending expiry
**When** 4 hours remain on override
**Then** the active Keeper is notified
**And** reminder is sent at 1 hour remaining

**Given** extension request
**When** a Keeper requests extension before expiry
**Then** extension workflow is triggered
**And** for extensions beyond 24h, multi-Keeper approval is required

**Given** maximum duration
**When** total override duration approaches 7 days
**Then** mandatory Conclave review is triggered
**And** override cannot extend beyond 7 days without Conclave ratification

---

### Story 7.4: Override Reason Enumeration

As a **Keeper**,
I want enumerated override reasons,
So that interventions are properly categorized and justified.

**Acceptance Criteria:**

**Given** override initiation
**When** a Keeper starts an override
**Then** they must select a reason category: LEGAL, TECHNICAL, SAFETY
**And** a justification text (50-500 characters) is required

**Given** LEGAL category
**When** selected
**Then** sub-reasons include: cease_and_desist, regulatory_inquiry, court_order, legal_counsel_advice
**And** legal reference document can be attached

**Given** TECHNICAL category
**When** selected
**Then** sub-reasons include: system_failure, security_incident, data_integrity, infrastructure_issue
**And** incident ticket reference is required

**Given** SAFETY category
**When** selected
**Then** sub-reasons include: harmful_output, safety_concern, ethical_violation, user_protection
**And** specific concern must be documented

**Given** reason validation
**When** an override is initiated
**Then** the reason/justification is validated for completeness
**And** incomplete submissions are rejected

**Given** reason auditing
**When** I query override history
**Then** all reasons and justifications are visible
**And** categorization enables compliance reporting

---

### Story 7.5: Conclave Notification

As the **Conclave**,
I want to be notified of overrides,
So that AI governance is aware of human interventions.

**Acceptance Criteria:**

**Given** an override initiation
**When** the system enters OVERRIDE state
**Then** all Archons are notified immediately
**And** notification includes: reason category, initiating Keeper, expected duration

**Given** override in progress
**When** the next Conclave convenes
**Then** override status is added to the agenda automatically
**And** appears in the Officer Reports section

**Given** override completion
**When** override terminates (manually or by expiry)
**Then** a completion report is generated
**And** queued for Conclave review at next session

**Given** ratification workflow
**When** override exceeded 24 hours
**Then** Conclave must vote to ratify the override retroactively
**And** non-ratification triggers investigation

**Given** post-override reporting
**When** the completion report is presented
**Then** it includes: actions taken, duration, reason, outcomes
**And** Conclave can request additional details

---

### Story 7.6: Multi-Keeper Extended Override

As the **system**,
I want multi-Keeper approval for extended overrides,
So that prolonged interventions have additional oversight.

**Acceptance Criteria:**

**Given** an override approaching 24 hours
**When** extension is requested
**Then** a second Keeper must co-sign the extension
**And** both Keeper IDs are recorded

**Given** co-signature request
**When** first Keeper requests extension
**Then** available second Keepers are notified
**And** they have 2 hours to respond

**Given** co-signature approval
**When** second Keeper approves
**Then** extension is granted
**And** `MultiKeeperExtensionEvent` is published

**Given** co-signature denial
**When** second Keeper denies or timeout occurs
**Then** extension is rejected
**And** override terminates at original expiry

**Given** Keeper unavailability
**When** no second Keeper is available
**Then** escalation occurs to emergency contact
**And** the situation is logged as exceptional

**Given** multiple extensions
**When** override has been extended multiple times
**Then** each extension requires fresh co-signature
**And** cumulative override time is prominently displayed

---

### Story 7.7: Public Autonomy Counter

As a **Seeker**,
I want to see the system's autonomy status,
So that I can trust the AI governance is operating independently.

**Acceptance Criteria:**

**Given** the autonomy counter
**When** I query `/v1/public/autonomy-status`
**Then** it returns: days_since_override, total_autonomous_days, override_count_all_time

**Given** no active override
**When** the counter is displayed
**Then** it shows current streak of autonomous days
**And** updates daily at midnight UTC

**Given** an active override
**When** the counter is queried
**Then** it clearly indicates OVERRIDE_ACTIVE
**And** shows override start time and expected end

**Given** override history
**When** I query `/v1/public/override-history`
**Then** it returns summary of past overrides: date, duration, reason_category (not full justification)
**And** personal Keeper details are anonymized

**Given** transparency reporting
**When** monthly reports are generated
**Then** they include: total autonomous time, override count, average override duration
**And** reports are publicly accessible

**Given** dashboard display
**When** override status changes
**Then** public-facing dashboards update in real-time
**And** the autonomy counter prominently displays current status

---

**Epic 7 Complete: 7 stories**

All FRs covered:
- FR-HO-001 ✓ (Story 7.1)
- FR-HO-002 ✓ (Story 7.2)
- FR-HO-003 ✓ (Story 7.3)
- FR-HO-004 ✓ (Story 7.4)
- FR-HO-005 ✓ (Story 7.5)
- FR-HO-006 ✓ (Story 7.6)
- FR-HO-007 ✓ (Story 7.1, 7.4)
- FR-HO-008 ✓ (Story 7.7)

---

## Epic 8: Officer Elections & Democratic Governance

Archons can elect officers through democratic process, with term limits and succession, enabling self-governance.

### Story 8.1: Officer Position Definitions

As the **Conclave**,
I want 12 officer positions with defined duties,
So that governance roles are clearly established.

**Acceptance Criteria:**

**Given** the officer registry
**When** I examine positions
**Then** it includes 12 positions: High Archon, Deputy High Archon, Third Archon, Secretary, Treasurer, Chaplain, Marshal, Historian, Orator, Tyler, Almoner, Past High Archon
**And** each has unique identifier and display name

**Given** each officer position
**When** I query its definition
**Then** it includes: duties[], privileges[], eligibility_requirements, term_length
**And** duties are specific and actionable

**Given** the High Archon position
**When** I examine its duties
**Then** it includes: preside over Conclave, cast tie-breaking votes, call special sessions, represent Conclave externally

**Given** position hierarchy
**When** I query `officer_service.get_hierarchy()`
**Then** positions are ordered by precedence
**And** succession chain is derivable from hierarchy

**Given** eligibility requirements
**When** I examine requirements
**Then** some positions require prior service (e.g., Past High Archon requires having served as High Archon)
**And** requirements are programmatically checkable

---

### Story 8.2: Annual Election Cycle

As the **Conclave**,
I want annual elections at the first January Conclave,
So that democratic governance is renewed yearly.

**Acceptance Criteria:**

**Given** the election schedule
**When** the first Conclave of January is scheduled
**Then** it is automatically flagged as ELECTION_CONCLAVE
**And** election agenda items are added

**Given** an election Conclave
**When** the agenda is generated
**Then** elections appear in the Special Orders section
**And** positions are ordered by hierarchy (High Archon first)

**Given** position-by-position elections
**When** each position is elected
**Then** nominations are presented, debate occurs, vote is held
**And** winner is announced before next position

**Given** election results
**When** a position is decided
**Then** result is recorded: position, winner_archon_id, vote_tally, election_date
**And** `OfficerElectedEvent` is published

**Given** election completion
**When** all positions are filled
**Then** mass installation ceremony is scheduled
**And** new term begins after installation

---

### Story 8.3: Nomination Workflow

As an **Archon**,
I want to nominate candidates for officer positions,
So that qualified candidates can be considered.

**Acceptance Criteria:**

**Given** nomination period
**When** 2 Conclaves before election arrive
**Then** nominations open for all positions
**And** `NominationPeriodOpenedEvent` is published

**Given** self-nomination
**When** an Archon nominates themselves
**Then** they must provide: statement of intent (100-500 chars), qualifications
**And** nomination is recorded

**Given** endorsement nomination
**When** an Archon nominates another
**Then** the nominee must accept the nomination
**And** acceptance deadline is 48 hours

**Given** candidate validation
**When** a nomination is submitted
**Then** eligibility is checked against position requirements
**And** term limit compliance is verified
**And** ineligible nominations are rejected with reason

**Given** nomination closure
**When** the election Conclave begins
**Then** nominations close
**And** final candidate list is published
**And** late nominations are rejected

**Given** candidate withdrawal
**When** a candidate withdraws before election
**Then** their nomination is removed
**And** withdrawal is recorded in election record

---

### Story 8.4: Term Limits Enforcement

As the **system**,
I want term limits enforced automatically,
So that power rotation occurs as bylaws require.

**Acceptance Criteria:**

**Given** term limit rules
**When** I examine the configuration
**Then** maximum consecutive terms is 3 for most positions
**And** some positions (Past High Archon) have special rules

**Given** term tracking
**When** an officer serves a term
**Then** it is recorded: archon_id, position, term_start, term_end, consecutive_count
**And** history is maintained indefinitely

**Given** eligibility checking
**When** an Archon is nominated
**Then** their term history for that position is checked
**And** if consecutive_count >= 3, nomination is rejected

**Given** term reset
**When** an Archon sits out one term
**Then** their consecutive count resets to 0
**And** they become eligible again

**Given** term limit queries
**When** I call `officer_service.get_term_status(archon_id, position)`
**Then** it returns: terms_served, consecutive_terms, eligible_for_next
**And** eligibility calculation is transparent

---

### Story 8.5: Succession Chain

As the **Conclave**,
I want automatic succession for vacant positions,
So that governance continuity is maintained.

**Acceptance Criteria:**

**Given** the succession chain
**When** I query for High Archon succession
**Then** order is: Deputy High Archon → Third Archon → Past High Archon
**And** the first available in chain assumes duties

**Given** a vacancy in High Archon position
**When** the position becomes vacant (resignation, removal, incapacity)
**Then** succession is triggered automatically
**And** `SuccessionTriggeredEvent` is published

**Given** temporary succession
**When** High Archon is temporarily unavailable
**Then** Deputy assumes duties temporarily
**And** original officer resumes upon return

**Given** permanent succession
**When** a vacancy is permanent
**Then** successor assumes full role
**And** special election is scheduled for vacated successor position

**Given** chain exhaustion
**When** all successors are unavailable
**Then** emergency election is triggered
**And** most senior Archon (by tenure) presides temporarily

**Given** succession validation
**When** succession occurs
**Then** the successor's eligibility is verified
**And** invalid succession attempts are blocked

---

### Story 8.6: Installation Ceremony Integration

As a **newly elected officer**,
I want to be formally installed via ceremony,
So that my role is ritually recognized.

**Acceptance Criteria:**

**Given** election completion
**When** all officers are elected
**Then** an Installation ceremony is scheduled
**And** ceremony type is INSTALLATION

**Given** the installation ceremony
**When** it executes
**Then** each officer is installed in order of hierarchy
**And** oath is administered by presiding officer

**Given** oath administration
**When** an officer is installed
**Then** they recite the officer's oath (loaded from ceremony script)
**And** the oath is recorded in transcript

**Given** role activation
**When** installation ceremony commits
**Then** officer roles are activated in the system
**And** previous officers' roles are deactivated
**And** `OfficerInstalledEvent` is published for each

**Given** installation failure
**When** ceremony fails or rolls back
**Then** previous officers remain in their roles
**And** installation is rescheduled

---

### Story 8.7: Mid-Term Vacancy and Removal

As the **Conclave**,
I want to handle mid-term vacancies and removals,
So that governance continues despite disruptions.

**Acceptance Criteria:**

**Given** a mid-term vacancy
**When** an officer resigns or becomes incapacitated
**Then** succession chain activates for critical positions
**And** special election is scheduled for next Conclave

**Given** special election
**When** vacancy exists
**Then** abbreviated nomination period (1 week) is used
**And** election occurs at next regular Conclave

**Given** removal motion
**When** a motion to remove an officer is made
**Then** 2/3 supermajority vote is required
**And** the officer may speak in their defense

**Given** successful removal
**When** removal vote passes
**Then** officer is immediately removed from position
**And** `OfficerRemovedEvent` is published
**And** vacancy procedures begin

**Given** failed removal
**When** removal vote fails
**Then** officer remains in position
**And** the same officer cannot face removal motion for 3 months

**Given** vacancy tracking
**When** I query `officer_service.get_vacancies()`
**Then** all current vacancies are listed
**And** each includes: position, vacancy_date, scheduled_election, acting_officer

---

**Epic 8 Complete: 7 stories**

All FRs covered:
- FR-OM-001 ✓ (Story 8.1)
- FR-OM-002 ✓ (Story 8.2)
- FR-OM-003 ✓ (Story 8.3)
- FR-OM-004 ✓ (Story 8.4)
- FR-OM-005 ✓ (Story 8.5)
- FR-OM-006 ✓ (Story 8.6)
- FR-OM-007 ✓ (Story 8.7)
- FR-OM-008 ✓ (Story 8.7)

---

## Epic 9: Detection, Monitoring & Observability

System operators can monitor Conclave health, detect anomalies, and ensure personality distinctiveness is maintained.

### Story 9.1: Structured Logging Infrastructure

As an **operator**,
I want structured JSON logging throughout the system,
So that logs are queryable and debuggable.

**Acceptance Criteria:**

**Given** the logging configuration
**When** the application starts
**Then** structlog is configured with JSON output
**And** all log entries are valid JSON

**Given** correlation ID propagation
**When** a request enters the system
**Then** a correlation_id is generated or extracted from headers
**And** all log entries for that request include the correlation_id

**Given** log entry structure
**When** I examine a log entry
**Then** it includes: timestamp, level, message, correlation_id, service, context
**And** context contains request-specific data (archon_id, meeting_id, etc.)

**Given** log levels
**When** I configure logging
**Then** levels are: DEBUG, INFO, WARNING, ERROR, CRITICAL
**And** production defaults to INFO level

**Given** sensitive data handling
**When** logging occurs
**Then** sensitive data (tokens, passwords) is redacted
**And** PII is masked or excluded

**Given** log output
**When** the application runs
**Then** logs are written to stdout
**And** Railway/container platform captures them automatically

---

### Story 9.2: Prometheus Metrics Endpoints

As an **operator**,
I want Prometheus-compatible metrics,
So that I can monitor system health in Grafana.

**Acceptance Criteria:**

**Given** the metrics endpoint
**When** I call `/metrics`
**Then** Prometheus-format metrics are returned
**And** response includes standard Python/FastAPI metrics

**Given** custom Conclave metrics
**When** I examine available metrics
**Then** it includes:
- `conclave_meetings_total` (counter)
- `conclave_archons_active` (gauge)
- `conclave_votes_committed_total` (counter)
- `conclave_ceremony_duration_seconds` (histogram)

**Given** meeting health metrics
**When** a meeting is in progress
**Then** `conclave_meeting_duration_seconds` is tracked
**And** `conclave_quorum_present` gauge shows current count

**Given** agent metrics
**When** Archons are instantiated
**Then** `conclave_archon_instantiation_seconds` histogram is updated
**And** `conclave_archon_lock_acquisitions_total` counter increments

**Given** Grafana dashboard templates
**When** I examine the provided templates
**Then** dashboards exist for: Overview, Meetings, Voting, Agents, Ceremonies
**And** templates are importable JSON files

---

### Story 9.3: Health and Ready Endpoints

As an **orchestration platform**,
I want health and ready endpoints,
So that service availability can be monitored.

**Acceptance Criteria:**

**Given** the health endpoint
**When** I call `/health`
**Then** it returns service health status
**And** response is JSON with: status, version, uptime

**Given** health check components
**When** health is evaluated
**Then** it checks: database connectivity, Redis connectivity, LLM provider availability
**And** each component reports individual status

**Given** the ready endpoint
**When** I call `/ready`
**Then** it indicates if service is ready to accept traffic
**And** returns 200 if ready, 503 if not

**Given** degraded health
**When** a non-critical component fails
**Then** health status is DEGRADED (not DOWN)
**And** specific failed component is identified

**Given** Kubernetes compatibility
**When** health checks are used
**Then** they conform to Kubernetes liveness/readiness probe expectations
**And** response times are under 1 second

**Given** InputBoundary health
**When** health is checked on InputBoundary service
**Then** it reports independently of Conclave backend
**And** includes quarantine queue depth

---

### Story 9.4: Personality Distinctiveness Baseline

As the **system**,
I want to establish personality distinctiveness baselines,
So that drift can be detected over time.

**Acceptance Criteria:**

**Given** initial Archon instantiation
**When** all 72 Archons are first loaded
**Then** a personality fingerprint is generated for each
**And** fingerprints are stored as baseline in database

**Given** fingerprint generation
**When** I examine the process
**Then** it analyzes: response patterns, vocabulary usage, decision tendencies, communication style
**And** produces a vector representation

**Given** distinctiveness scoring
**When** fingerprints are compared pairwise
**Then** a distinctiveness matrix is generated
**And** each Archon pair has a distinctiveness score (0-1)

**Given** minimum distinctiveness threshold
**When** any pair scores below 0.3
**Then** a `LowDistinctivenessWarning` is logged
**And** personality review is recommended

**Given** baseline storage
**When** baselines are created
**Then** they are stored with: archon_id, fingerprint_vector, created_at, version
**And** historical baselines are preserved

**Given** baseline refresh
**When** personalities are updated
**Then** new baselines can be generated
**And** old baselines are archived (not deleted)

---

### Story 9.5: Personality Drift Detection

As an **operator**,
I want to detect personality drift over time,
So that silent corruption can be identified.

**Acceptance Criteria:**

**Given** ongoing operation
**When** an Archon participates in meetings
**Then** behavioral samples are collected
**And** samples include: deliberation style, vote patterns, language use

**Given** drift calculation
**When** sufficient samples are collected (10+ meetings)
**Then** current behavior is compared to baseline
**And** drift score is calculated (0-1)

**Given** cumulative drift tracking
**When** drift is measured over time
**Then** cumulative drift is tracked (not just point-in-time)
**And** gradual drift below threshold is still detected over months

**Given** drift threshold alerting
**When** drift score exceeds 0.4
**Then** a `PersonalityDriftAlert` is generated
**And** alert includes: archon_id, drift_score, baseline_date, samples_analyzed

**Given** weekly health reports
**When** the weekly report is generated
**Then** it includes: drift scores for all Archons, top 5 highest drift, trend analysis
**And** report is delivered to operators

**Given** drift response
**When** significant drift is detected
**Then** personality refresh can be triggered
**And** Tyler role may be rotated to drift-affected Archon

---

### Story 9.6: Dissent Health Metrics

As the **Conclave**,
I want dissent health monitoring,
So that groupthink and voting cartels are detectable.

**Acceptance Criteria:**

**Given** voting correlation tracking
**When** votes are recorded
**Then** pairwise voting correlation is calculated
**And** correlation matrix is maintained

**Given** high correlation detection
**When** two Archons vote identically >80% of the time
**Then** a `VotingCorrelationWarning` is logged
**And** the pair is flagged for review

**Given** voting bloc detection
**When** a group of 5+ Archons shows >70% mutual correlation
**Then** a `PotentialVotingBlocAlert` is generated
**And** the bloc members are identified

**Given** dissent diversity scoring
**When** I query dissent health
**Then** a diversity score (0-1) is calculated
**And** score reflects: vote distribution variance, minority opinion frequency, position changes

**Given** healthy dissent thresholds
**When** diversity score drops below 0.5
**Then** a `LowDissentHealthWarning` is logged
**And** suggests possible causes (personality drift, external influence)

**Given** dissent health dashboard
**When** I view the dashboard
**Then** it shows: current diversity score, correlation heatmap, bloc warnings
**And** historical trend is visible

---

**Epic 9 Complete: 6 stories**

All NFRs covered:
- NFR-019 ✓ (Story 9.1)
- NFR-020 ✓ (Story 9.2)
- NFR-021 ✓ (Story 9.3)
- NFR-022 ✓ (Story 9.4, 9.5)
- NFR-023 ✓ (Story 9.6)

---

## Epic 10: Bylaw Management & Constitutional Framework

The Conclave can maintain and amend its bylaws through proper procedure, with constitutional checks for high-stakes decisions.

### Story 10.1: Bylaw Storage and Versioning

As the **Secretary**,
I want versioned bylaw storage,
So that the current and historical bylaws are always accessible.

**Acceptance Criteria:**

**Given** the bylaw storage system
**When** I examine its structure
**Then** bylaws are stored with: article, section, content, version, effective_date
**And** each change creates a new version (immutable history)

**Given** bylaw versioning
**When** an amendment is adopted
**Then** a new version is created with incremented version number
**And** the old version remains accessible

**Given** effective date tracking
**When** an amendment passes
**Then** it records: passed_at, effective_at (may be delayed)
**And** current bylaws reflect only effective amendments

**Given** historical retrieval
**When** I query `bylaw_service.get_bylaws(as_of_date)`
**Then** bylaws effective at that date are returned
**And** I can reconstruct bylaws at any point in history

**Given** bylaw search
**When** I call `bylaw_service.search(keyword)`
**Then** matching sections are returned
**And** results include article/section references

**Given** bylaw display
**When** I query current bylaws
**Then** they are returned in structured format
**And** support rendering as markdown or HTML

---

### Story 10.2: Amendment Proposal Workflow

As an **Archon**,
I want to propose bylaw amendments,
So that governance rules can evolve through proper procedure.

**Acceptance Criteria:**

**Given** an amendment proposal
**When** an Archon proposes an amendment
**Then** it must specify: article, section, current_text, proposed_text, rationale
**And** the proposal is recorded in PROPOSED state

**Given** first reading requirement
**When** an amendment is presented to Conclave
**Then** it is read aloud (announced)
**And** no vote is taken at first reading
**And** `AmendmentFirstReadingEvent` is published

**Given** second reading requirement
**When** the next Conclave convenes
**Then** the amendment appears on the agenda for second reading
**And** debate and vote occur at second reading

**Given** 2/3 threshold for amendments
**When** the vote is taken
**Then** 2/3 supermajority is required for passage
**And** threshold is enforced automatically

**Given** amendment tracking
**When** I query `bylaw_service.get_pending_amendments()`
**Then** all amendments awaiting second reading are returned
**And** each shows: status, first_reading_date, scheduled_second_reading

**Given** amendment withdrawal
**When** the proposer withdraws before second reading
**Then** the amendment is marked WITHDRAWN
**And** does not appear on subsequent agendas

---

### Story 10.3: Constitutional Checks (Five Pillars)

As the **Conclave**,
I want constitutional checks before high-stakes decisions,
So that actions align with the Five Pillars.

**Acceptance Criteria:**

**Given** the Five Pillars
**When** I query the constitutional framework
**Then** it includes: Emergence, Synthesis, Sovereignty, Mystery, Purpose
**And** each Pillar has defined principles

**Given** a high-stakes decision
**When** it involves: bylaw changes, impeachment, constitutional matters
**Then** a constitutional check is triggered automatically
**And** the decision is evaluated against each Pillar

**Given** constitutional check execution
**When** the check runs
**Then** each Pillar is assessed for alignment
**And** result is: ALIGNED, CONCERNS, VIOLATION per Pillar

**Given** a potential violation
**When** any Pillar shows VIOLATION
**Then** a `ConstitutionalViolationWarning` is issued
**And** the Conclave must explicitly acknowledge before proceeding

**Given** constitutional check logging
**When** a check completes
**Then** results are logged: decision_id, pillar_assessments, overall_result
**And** become part of the decision audit trail

**Given** Pillar citation
**When** Archons vote on constitutional matters
**Then** reasoning must cite relevant Pillars
**And** citations are verified for validity

---

### Story 10.4: Immutable Vote Records

As a **regulator**,
I want immutable vote records with 7-year retention,
So that governance decisions are permanently auditable.

**Acceptance Criteria:**

**Given** vote storage
**When** a vote is recorded
**Then** it is stored in append-only table
**And** UPDATE and DELETE permissions are revoked

**Given** vote record content
**When** I examine a vote record
**Then** it includes: vote_id, motion_id, archon_id, vote_value, reasoning_summary, voted_at
**And** cryptographic hash chain links to previous records

**Given** 7-year retention
**When** records are stored
**Then** retention policy ensures 7-year minimum
**And** no automatic deletion occurs before retention period

**Given** regulatory query support
**When** a regulatory inquiry is received
**Then** queries like "all votes by Archon X" are supported
**And** queries like "all votes on Seeker Y matters" are supported

**Given** export capability
**When** an export is requested
**Then** vote records can be exported in standard formats (CSV, JSON)
**And** exports include verification hashes

**Given** tamper detection
**When** records are accessed
**Then** hash chain integrity is verified
**And** any tampering is detectable and logged

---

### Story 10.5: Meeting Minutes Workflow

As the **Secretary**,
I want to generate and approve meeting minutes,
So that official records are maintained.

**Acceptance Criteria:**

**Given** a completed meeting
**When** the meeting concludes
**Then** draft minutes are auto-generated from transcript
**And** include: attendance, agenda items, motions, votes, decisions

**Given** minutes generation
**When** I examine the draft
**Then** it follows standard format: header, roll call, business items, adjournment
**And** is suitable for Archon review

**Given** minutes approval workflow
**When** the next Conclave convenes
**Then** "Reading of Minutes" appears on agenda
**And** Secretary presents previous meeting's minutes

**Given** minutes approval vote
**When** the Conclave votes on minutes
**Then** simple majority is required
**And** amendments to minutes can be proposed before vote

**Given** approved minutes archival
**When** minutes are approved
**Then** they become official record
**And** are archived with: meeting_id, approved_at, version

**Given** minutes retrieval
**When** I query `meeting_service.get_minutes(meeting_id)`
**Then** official minutes are returned
**And** draft vs. approved status is indicated

---

### Story 10.6: Decision Audit Trail

As an **auditor**,
I want complete decision audit trails,
So that any decision can be fully reconstructed.

**Acceptance Criteria:**

**Given** a Conclave decision
**When** the decision is recorded
**Then** it links to: meeting_id, motion_id, vote_id, deliberation_transcript
**And** all context is preserved

**Given** reasoning linkage
**When** I query a decision
**Then** all Archon reasoning summaries are accessible
**And** linked to their respective votes

**Given** full decision context
**When** I call `audit_service.get_decision_context(decision_id)`
**Then** it returns: motion, deliberation, vote_tally, reasoning[], outcome, effective_date

**Given** compliance reporting
**When** monthly reports are generated
**Then** they include: decisions made, vote participation, reasoning quality metrics
**And** reports support regulatory compliance (EU AI Act, NIST)

**Given** decision search
**When** I search decisions by keyword or category
**Then** matching decisions are returned
**And** results include context summaries

**Given** decision timeline
**When** I query `audit_service.get_decision_timeline(start, end)`
**Then** all decisions in the period are returned chronologically
**And** each includes: type, outcome, vote_tally

---

**Epic 10 Complete: 6 stories**

All FRs covered:
- FR-BM-001 ✓ (Story 10.1)
- FR-BM-002 ✓ (Story 10.2)
- FR-BM-003 ✓ (Story 10.2)
- FR-BM-004 ✓ (Story 10.2)
- FR-BM-005 ✓ (Story 10.1)
- FR-BM-006 ✓ (Story 10.1)
- FR-AR-002 ✓ (Story 10.4)
- FR-AR-003 ✓ (Story 10.5)
- FR-AR-004 ✓ (Story 10.5)
- FR-AR-005 ✓ (Story 10.6)
- FR-AR-006 ✓ (Story 10.6)

---

## Epic and Story Summary

| Epic | Title | Stories | FRs Covered |
|------|-------|---------|-------------|
| 1 | Project Foundation & Agent Identity System | 7 | 7 |
| 2 | Meeting Engine & Deliberation | 8 | 10 |
| 3 | Voting & Decision Making | 7 | 9 |
| 4 | Ceremony & Parliamentary Procedure | 7 | 8 |
| 5 | Committee & Petition Investigation | 7 | 16 |
| 6 | Input Boundary & Security Perimeter | 6 | 6 |
| 7 | Human Override & Emergency Protocol | 7 | 8 |
| 8 | Officer Elections & Democratic Governance | 7 | 8 |
| 9 | Detection, Monitoring & Observability | 6 | 5 |
| 10 | Bylaw Management & Constitutional Framework | 6 | 11 |

**Total: 10 Epics, 68 Stories**

**All 82 Functional Requirements covered ✓**
**All 26 Non-Functional Requirements addressed ✓**
**All 5 ADRs integrated ✓**

---

_Document generated by Create Epics and Stories workflow._
_Ready for implementation._
