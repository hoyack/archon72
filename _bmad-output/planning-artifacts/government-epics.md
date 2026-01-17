---
stepsCompleted: [1, 2, 3, 4]
inputDocuments:
  - _bmad-output/planning-artifacts/governance-prd.md
  - _bmad-output/planning-artifacts/governance-architecture.md
  - README.md
workflowType: 'create-epics-and-stories'
project_name: 'Archon 72 Governance System'
date: '2026-01-16'
---

# Archon 72 Governance System - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for the **Archon 72 Governance System**, implementing consent-based coordination with separation of powers, dignity preservation, and constitutional constraint enforcement.

**Source Documents:**
- `governance-prd.md` - 63 Functional Requirements, 34 Non-Functional Requirements
- `governance-architecture.md` - 18 Architectural Decisions
- `README.md` - Existing system context and integration points

**Project Type:** Brownfield Extension (building on existing hexagonal architecture)
**Tech Stack:** Python 3.11+, FastAPI, Supabase PostgreSQL, Redis
**Architecture Pattern:** Event-Sourced Constitutional State Machine

---

## Requirements Inventory

### Functional Requirements (63 Total)

#### Task Coordination (FR1-FR14)

| FR# | Requirement |
|-----|-------------|
| FR1 | Earl can create task activation requests for Clusters |
| FR2 | Cluster can view pending task activation requests |
| FR3 | Cluster can accept a task activation request |
| FR4 | Cluster can decline a task activation request without providing justification |
| FR5 | Cluster can halt an in-progress task without penalty |
| FR6 | Cluster can submit a task result report |
| FR7 | Cluster can submit a problem report for an in-progress task |
| FR8 | System can auto-decline task requests after TTL expiration (72h default) |
| FR9 | System can auto-transition accepted tasks to in_progress after inactivity (48h) |
| FR10 | System can auto-quarantine tasks that exceed reporting timeout (7d default) |
| FR11 | System can send neutral reminder at 50% and 90% of TTL |
| FR12 | Earl can view task state and history |
| FR13 | System can enforce task state machine transitions (no illegal transitions) |
| FR14 | System can enforce role-specific constraints within each rank |

#### Coercion Filter (FR15-FR21)

| FR# | Requirement |
|-----|-------------|
| FR15 | System can filter outbound content for coercive language |
| FR16 | Coercion Filter can accept content (with transformation) |
| FR17 | Coercion Filter can reject content (requiring rewrite) |
| FR18 | Coercion Filter can block content (hard violation, logged) |
| FR19 | Earl can view filter outcome before content is sent |
| FR20 | System can log all filter decisions with version and timestamp |
| FR21 | System can route all participant-facing messages through Coercion Filter |

#### Halt Circuit (FR22-FR27)

| FR# | Requirement |
|-----|-------------|
| FR22 | Human Operator can trigger system halt |
| FR23 | System can execute halt operation |
| FR24 | System can transition all pre-consent tasks to nullified on halt |
| FR25 | System can transition all post-consent tasks to quarantined on halt |
| FR26 | System can preserve completed tasks unchanged on halt |
| FR27 | System can ensure state transitions are atomic (no partial transitions) |

#### Legitimacy Management (FR28-FR32)

| FR# | Requirement |
|-----|-------------|
| FR28 | System can track current legitimacy band (Stable/Strained/Eroding/Compromised/Failed) |
| FR29 | System can auto-transition legitimacy downward based on violation events |
| FR30 | Human Operator can acknowledge and execute upward legitimacy transition |
| FR31 | System can record all legitimacy transitions in append-only ledger |
| FR32 | System can prevent upward transitions without explicit acknowledgment |

#### Violation Handling (FR33-FR41)

| FR# | Requirement |
|-----|-------------|
| FR33 | Knight can observe and record violations across all branches |
| FR34 | Knight can publish witness statements (observation only, no judgment) |
| FR35 | System can route witness statements to Prince Panel queue |
| FR36 | Human Operator (as Prince) can convene panel (≥3 members) |
| FR37 | Prince Panel can review witness artifacts |
| FR38 | Prince Panel can issue formal finding with remedy |
| FR39 | Prince Panel can record dissent in finding |
| FR40 | System can record all panel findings in append-only ledger |
| FR41 | Knight can observe Prince Panel conduct |

#### Exit & Dignified Departure (FR42-FR46)

| FR# | Requirement |
|-----|-------------|
| FR42 | Cluster can initiate exit request |
| FR43 | System can process exit request |
| FR44 | System can release Cluster from all obligations on exit |
| FR45 | System can preserve Cluster's contribution history on exit |
| FR46 | System can prohibit follow-up contact after exit |

#### Cessation & Reconstitution (FR47-FR55)

| FR# | Requirement |
|-----|-------------|
| FR47 | Human Operator can trigger system cessation |
| FR48 | System can create immutable Cessation Record on cessation |
| FR49 | System can block new motions on cessation |
| FR50 | System can halt execution on cessation |
| FR51 | System can preserve all records on cessation |
| FR52 | System can label in-progress work as `interrupted_by_cessation` |
| FR53 | System can validate Reconstitution Artifact before new instance |
| FR54 | System can reject reconstitution that claims continuity |
| FR55 | System can reject reconstitution that inherits legitimacy band |

#### Audit & Verification (FR56-FR60)

| FR# | Requirement |
|-----|-------------|
| FR56 | Any participant can export complete ledger |
| FR57 | System can provide cryptographic proof of ledger completeness |
| FR58 | Any participant can independently verify ledger integrity |
| FR59 | System can log all state transitions with timestamp and actor |
| FR60 | System can prevent ledger modification (append-only enforcement) |

#### System Capabilities (FR61-FR63)

| FR# | Requirement |
|-----|-------------|
| FR61 | System can coordinate tasks without storing participant-level performance metrics |
| FR62 | System can complete task workflows without calculating completion rates per participant |
| FR63 | System can operate without engagement or retention tracking |

### Non-Functional Requirements (34 Total)

#### Performance (NFR-PERF)

| NFR# | Requirement | Test Conditions |
|------|-------------|-----------------|
| NFR-PERF-01 | Halt circuit completes in ≤100ms from trigger | Worst-case: max concurrent tasks, ledger append in progress |
| NFR-PERF-03 | Coercion Filter processes content in ≤200ms | Determinism is primary; speed is secondary |
| NFR-PERF-04 | Ledger append operations complete in ≤100ms | Normal operational load |
| NFR-PERF-05 | Task state machine resolves illegal transition detection in ≤10ms | Any state, any attempted transition |

#### Atomicity (NFR-ATOMIC)

| NFR# | Requirement | Severity |
|------|-------------|----------|
| NFR-ATOMIC-01 | State transition + ledger append SHALL succeed atomically or fail completely | Catastrophic |

#### Constitutional Integrity (NFR-CONST)

| NFR# | Requirement | Severity |
|------|-------------|----------|
| NFR-CONST-01 | Ledger is append-only; no delete or modify operations exist | Catastrophic |
| NFR-CONST-02 | All ledger entries include cryptographic hash linking to previous entry | Catastrophic |
| NFR-CONST-03 | Ledger export produces complete history; partial export is impossible | Catastrophic |
| NFR-CONST-04 | All state transitions are logged with timestamp, actor, and reason | High |
| NFR-CONST-05 | No API or administrative path exists to bypass Coercion Filter | High |
| NFR-CONST-06 | Prince Panel findings cannot be deleted or modified after submission | High |
| NFR-CONST-07 | Witness statements cannot be suppressed by any role | Catastrophic |
| NFR-CONST-08 | Anti-metrics are enforced at data layer; collection endpoints do not exist | High |
| NFR-CONST-09 | No mutation path except through authorized state machine and event append | Catastrophic |

#### Reliability (NFR-REL)

| NFR# | Requirement |
|------|-------------|
| NFR-REL-01 | Halt circuit has dedicated execution path with no shared dependencies |
| NFR-REL-02 | Ledger survives service restart without data loss |
| NFR-REL-03 | In-flight task state resolves deterministically on halt |
| NFR-REL-04 | System recovers to consistent state after unexpected shutdown |
| NFR-REL-05 | Cessation Record creation is atomic; partial cessation is impossible |

#### Auditability (NFR-AUDIT)

| NFR# | Requirement |
|------|-------------|
| NFR-AUDIT-01 | All branch actions logged with sufficient detail for Knight observation |
| NFR-AUDIT-02 | All filter decisions logged with input, output, and version |
| NFR-AUDIT-03 | All consent events logged with timestamp |
| NFR-AUDIT-04 | Legitimacy band transitions include triggering event reference |
| NFR-AUDIT-05 | Export format is machine-readable (JSON) and human-auditable |
| NFR-AUDIT-06 | Ledger export enables deterministic state derivation by replay |

#### Observability (NFR-OBS)

| NFR# | Requirement |
|------|-------------|
| NFR-OBS-01 | All branch actions emit events observable by Knight within ≤1 second |

#### Consent (NFR-CONSENT)

| NFR# | Requirement |
|------|-------------|
| NFR-CONSENT-01 | TTL expiration transitions task to `declined` with no failure attribution |

#### Exit Protocol (NFR-EXIT)

| NFR# | Requirement |
|------|-------------|
| NFR-EXIT-01 | Exit completes in ≤2 message round-trips |
| NFR-EXIT-02 | No follow-up contact mechanism may exist for exited participants |
| NFR-EXIT-03 | Exit path available from any task state |

#### UX Constraints (NFR-UX)

| NFR# | Requirement |
|------|-------------|
| NFR-UX-01 | All participant-facing communications free of engagement-optimization language |

#### Integration (NFR-INT)

| NFR# | Requirement |
|------|-------------|
| NFR-INT-01 | Async protocol (email) handles all Earl→Cluster communication |
| NFR-INT-02 | Ledger contains no PII; publicly readable by design |
| NFR-INT-03 | Core constitutional functions operate without external dependencies |

### Additional Requirements

#### From Architecture (18 Key Decisions)

1. **Event Sourcing as Canonical Model** - The ledger IS the state; everything else is projection
2. **Three-Channel Halt Circuit** - In-memory (primary) → Redis (propagation) → Ledger (recording)
3. **Two-Phase Event Emission** - `intent_emitted` → `commit_confirmed` OR `failure_recorded`
4. **Event Naming Convention** - `branch.noun.verb` (dot-separated, e.g., `executive.task.accepted`)
5. **Event Envelope Pattern** - `{ metadata: {...}, payload: {...} }` structure
6. **Hash Chain Implementation** - BLAKE3 preferred, SHA-256 required baseline
7. **Merkle Tree Proof-of-Inclusion** - Root per batch/epoch for verification
8. **Same-DB Projection Storage** - `ledger.*` vs `projections.*` schema isolation
9. **CQRS-Lite Query Pattern** - Single API, internal separation
10. **Hybrid Event Bus** - Redis notify (wake-up) + ledger replay (truth)
11. **Global Event Ordering** - Single monotonic `ledger.events.sequence`
12. **Write-Time Prevention** - Reject illegal transitions, hash breaks, unknown events
13. **Observer-Time Detection** - Knight detects legitimacy erosion patterns
14. **Coercion Filter Mandatory Path** - No API bypass exists; `FilteredContent` type required
15. **Branch Derivation at Write-Time** - `event_type.split('.')[0]`, no caller trust
16. **Passive Knight Observation** - Event bus subscription, ledger replay as backstop
17. **Schema Versioning** - Every event includes `schema_version` field
18. **Chaos Testing Constraint** - Read-path faults only; no live ledger mutation

#### From Architecture (Project Context)

- **No external starter template** - Build on existing codebase
- Existing hexagonal architecture in `src/`
- 60+ port definitions already exist
- PostgreSQL + Redis stack configured
- Full governance pipeline already implemented (Conclave → Secretary → Consolidator → Review Pipeline → Execution Planner)
- 72 Archon schema in `docs/archons-base.json`

#### New Directories Required

- `src/domain/governance/` - Governance domain models
- `src/domain/governance/events/` - Governance event definitions
- `src/domain/governance/task/` - Task lifecycle state machine
- `src/domain/governance/legitimacy/` - Legitimacy band state machine
- `src/domain/governance/filter/` - Coercion filter domain
- `src/domain/governance/witness/` - Knight-Witness domain
- `src/domain/governance/panel/` - Prince Panel domain
- `src/application/ports/governance/` - Governance port interfaces
- `src/infrastructure/adapters/governance/` - Governance adapters
- `tests/chaos/` - Chaos testing framework

---

### FR Coverage Map

| Epic | FRs Covered | NFRs Covered | User Value |
|------|-------------|--------------|------------|
| GOV-1: Constitutional Event Infrastructure | - | NFR-CONST-01 to 09, NFR-ATOMIC-01, NFR-PERF-04, NFR-PERF-05, NFR-REL-02, NFR-REL-04 | Foundation for all governance operations |
| GOV-2: Task Consent & Coordination | FR1-FR14 | NFR-CONSENT-01, NFR-PERF-05, NFR-INT-01 | Humans participate in tasks with dignity |
| GOV-3: Coercion-Free Communication | FR15-FR21 | NFR-CONST-05, NFR-PERF-03, NFR-UX-01 | All communications protect humans from manipulation |
| GOV-4: Emergency Safety Circuit | FR22-FR27 | NFR-PERF-01, NFR-ATOMIC-01, NFR-REL-01, NFR-REL-03 | System can halt immediately and safely |
| GOV-5: Legitimacy Visibility | FR28-FR32 | NFR-AUDIT-04, NFR-CONST-04 | System health is transparent and trackable |
| GOV-6: Violation Witness & Accountability | FR33-FR41 | NFR-CONST-06, NFR-CONST-07, NFR-OBS-01, NFR-AUDIT-01 | Violations observed, recorded, handled through panels |
| GOV-7: Dignified Exit | FR42-FR46 | NFR-EXIT-01 to 03 | Humans can leave at any time with dignity |
| GOV-8: System Lifecycle Management | FR47-FR55 | NFR-REL-05 | System can stop and restart with records preserved |
| GOV-9: Audit & Verification | FR56-FR60 | NFR-AUDIT-02 to 06, NFR-INT-02 | Anyone can verify system integrity independently |
| GOV-10: Anti-Metrics Foundation | FR61-FR63 | NFR-CONST-08 | System operates without surveillance |

---

## Epic List

### GOV-1: Constitutional Event Infrastructure
**User Value:** Foundation that makes all governance operations possible - the ledger IS the state.
**Priority:** P0 (Required First)
**Dependencies:** None (Foundation Epic)

### GOV-2: Task Consent & Coordination
**User Value:** Humans can participate in tasks with full consent, dignity, and penalty-free refusal.
**Priority:** P1
**Dependencies:** GOV-1 (event infrastructure)

### GOV-3: Coercion-Free Communication
**User Value:** All participant-facing communications are protected from manipulative language.
**Priority:** P1
**Dependencies:** GOV-1 (event infrastructure)

### GOV-4: Emergency Safety Circuit
**User Value:** System can halt immediately (<100ms), safely transitioning all tasks to known states.
**Priority:** P0 (Critical Safety)
**Dependencies:** GOV-1 (event infrastructure)

### GOV-5: Legitimacy Visibility
**User Value:** System health is visible through banded legitimacy states (Stable→Failed).
**Priority:** P2
**Dependencies:** GOV-1 (event infrastructure), GOV-6 (violations trigger transitions)

### GOV-6: Violation Witness & Accountability
**User Value:** Violations are observed by Knights, handled by Prince Panels, with findings preserved.
**Priority:** P1
**Dependencies:** GOV-1 (event infrastructure)

### GOV-7: Dignified Exit
**User Value:** Humans can leave at any time, from any state, with dignity preserved and no follow-up.
**Priority:** P1
**Dependencies:** GOV-1 (event infrastructure), GOV-2 (task states to release)

### GOV-8: System Lifecycle Management
**User Value:** System can stop honorably (cessation) and restart without claiming false continuity.
**Priority:** P2
**Dependencies:** GOV-1 (event infrastructure), GOV-4 (halt circuit)

### GOV-9: Audit & Verification
**User Value:** Anyone can independently verify the complete ledger and derive system state.
**Priority:** P2
**Dependencies:** GOV-1 (event infrastructure)

### GOV-10: Anti-Metrics Foundation
**User Value:** System operates without engagement tracking, retention metrics, or performance scoring.
**Priority:** P1
**Dependencies:** GOV-1 (event infrastructure)

---

## Epics and Stories

---

## GOV-1: Constitutional Event Infrastructure

**Epic Summary:** Build the foundational event-sourced ledger that enables all governance operations. The ledger IS the canonical state; everything else is projection.

**User Value:** All governance operations have an immutable, verifiable, append-only foundation that cannot be tampered with.

**Architectural Decisions Implemented:**
- AD-1: Event Sourcing as Canonical Model
- AD-4: Event Naming Convention (`branch.noun.verb`)
- AD-5: Event Envelope Pattern (`{ metadata, payload }`)
- AD-6: Hash Chain Implementation (BLAKE3/SHA-256)
- AD-7: Merkle Tree Proof-of-Inclusion
- AD-8: Same-DB Projection Storage
- AD-11: Global Event Ordering
- AD-12: Write-Time Prevention
- AD-17: Schema Versioning

**NFRs Addressed:**
- NFR-CONST-01: Ledger is append-only
- NFR-CONST-02: Cryptographic hash linking
- NFR-CONST-03: Complete export only
- NFR-CONST-09: No mutation except through state machine
- NFR-ATOMIC-01: Atomic state+ledger operations
- NFR-PERF-04: Ledger append ≤100ms
- NFR-PERF-05: State machine resolution ≤10ms
- NFR-REL-02: Ledger survives restart
- NFR-REL-04: Consistent state after shutdown

### Stories

#### GOV-1-1: Event Envelope Domain Model
**As a** governance system operator
**I want** a canonical event envelope structure
**So that** all events have consistent metadata and can be validated

**Acceptance Criteria:**
- [ ] `GovernanceEvent` domain model with `metadata` and `payload` fields
- [ ] Metadata includes: `event_id`, `event_type`, `timestamp`, `actor_id`, `schema_version`, `trace_id`
- [ ] Event type follows `branch.noun.verb` naming convention (validated)
- [ ] Branch is derived from event_type at write-time, not trusted from caller
- [ ] Schema version field present on all events
- [ ] Unit tests for event envelope validation

**Technical Notes:**
- Location: `src/domain/governance/events/`
- Pattern: Value object with validation
- Reference: AD-4, AD-5, AD-15, AD-17

---

#### GOV-1-2: Append-Only Ledger Port & Adapter
**As a** governance system
**I want** an append-only ledger interface
**So that** events can be persisted without modification or deletion

**Acceptance Criteria:**
- [ ] `LedgerPort` interface with `append_event()` and `read_events()` methods
- [ ] No `update`, `delete`, or `modify` methods exist on the interface
- [ ] PostgreSQL adapter implements append with sequence number
- [ ] Global monotonic sequence via `ledger.events.sequence`
- [ ] Schema isolation: `ledger.*` tables separate from `projections.*`
- [ ] Ledger survives service restart without data loss
- [ ] Unit tests verify no mutation paths exist

**Technical Notes:**
- Port: `src/application/ports/governance/ledger_port.py`
- Adapter: `src/infrastructure/adapters/governance/postgres_ledger_adapter.py`
- Tables: `ledger.events`, `ledger.sequence`
- Reference: AD-8, AD-11, NFR-CONST-01, NFR-REL-02

---

#### GOV-1-3: Hash Chain Implementation
**As a** verifier
**I want** each event cryptographically linked to the previous
**So that** I can detect any tampering or gaps in the ledger

**Acceptance Criteria:**
- [ ] BLAKE3 as preferred hash algorithm
- [ ] SHA-256 as required baseline (configurable)
- [ ] Each event stores `previous_hash` field
- [ ] Genesis event has well-known null hash
- [ ] Hash chain validated on read
- [ ] Hash break detected and logged as `ledger.integrity.hash_break_detected`
- [ ] Unit tests for hash chain creation and verification

**Technical Notes:**
- Location: `src/domain/governance/events/hash_chain.py`
- Reference: AD-6, NFR-CONST-02

---

#### GOV-1-4: Write-Time Validation
**As a** governance system
**I want** invalid events rejected at write-time
**So that** the ledger never contains illegal transitions or invalid data

**Acceptance Criteria:**
- [ ] Illegal state transitions rejected before append
- [ ] Hash chain breaks rejected before append
- [ ] Unknown event types rejected before append
- [ ] Validation returns specific error (not generic failure)
- [ ] State machine resolution completes in ≤10ms
- [ ] Unit tests for each rejection case

**Technical Notes:**
- Location: `src/application/services/governance/ledger_validation_service.py`
- Reference: AD-12, NFR-PERF-05

---

#### GOV-1-5: Projection Infrastructure
**As a** governance system
**I want** queryable projections derived from the ledger
**So that** current state can be efficiently accessed without replaying all events

**Acceptance Criteria:**
- [ ] `ProjectionPort` interface for projection storage
- [ ] Projections stored in `projections.*` schema (separate from `ledger.*`)
- [ ] Projections can be rebuilt from ledger replay
- [ ] CQRS-Lite: Single API with internal read/write separation
- [ ] Deterministic state derivation from event replay
- [ ] Unit tests verify projection matches ledger state

**Technical Notes:**
- Port: `src/application/ports/governance/projection_port.py`
- Adapter: `src/infrastructure/adapters/governance/postgres_projection_adapter.py`
- Reference: AD-8, AD-9, NFR-AUDIT-06

---

#### GOV-1-6: Two-Phase Event Emission
**As a** governance system
**I want** events emitted in two phases (intent → commit/failure)
**So that** observers see both attempts and outcomes

**Acceptance Criteria:**
- [ ] `intent_emitted` event published before operation
- [ ] `commit_confirmed` event published on success
- [ ] `failure_recorded` event published on failure
- [ ] Intent and outcome linked by correlation ID
- [ ] No orphaned intents (always resolved to commit or failure)
- [ ] Unit tests for both success and failure paths

**Technical Notes:**
- Location: `src/application/services/governance/event_emission_service.py`
- Reference: AD-3

---

#### GOV-1-7: Merkle Tree Proof-of-Inclusion
**As a** verifier
**I want** Merkle tree proofs for event inclusion
**So that** I can verify specific events without downloading the entire ledger

**Acceptance Criteria:**
- [ ] Merkle root calculated per batch/epoch
- [ ] Proof-of-inclusion can be generated for any event
- [ ] Proof can be verified independently
- [ ] Root published to ledger at epoch boundaries
- [ ] Unit tests for proof generation and verification

**Technical Notes:**
- Location: `src/domain/governance/events/merkle_tree.py`
- Reference: AD-7

---

## GOV-2: Task Consent & Coordination

**Epic Summary:** Implement the task lifecycle with consent-based activation, penalty-free refusal, and dignity-preserving state transitions.

**User Value:** Humans can participate in tasks with full consent, clear state visibility, and the freedom to decline or halt without penalty.

**FRs Addressed:** FR1-FR14

**NFRs Addressed:**
- NFR-CONSENT-01: TTL expiration = declined (no failure attribution)
- NFR-PERF-05: State machine ≤10ms
- NFR-INT-01: Async protocol (email) for Earl→Cluster

### Stories

#### GOV-2-1: Task State Machine Domain Model
**As a** governance system
**I want** a task state machine with defined transitions
**So that** tasks can only move through legal states

**Acceptance Criteria:**
- [ ] Task states: `authorized`, `activated`, `routed`, `accepted`, `in_progress`, `reported`, `aggregated`, `completed`, `declined`, `quarantined`, `nullified`
- [ ] State transitions validated (illegal transitions rejected)
- [ ] State machine resolution ≤10ms
- [ ] All transitions emit events to ledger
- [ ] Unit tests for all valid transitions
- [ ] Unit tests for invalid transition rejection

**Technical Notes:**
- Location: `src/domain/governance/task/task_state_machine.py`
- Reference: FR13, NFR-PERF-05

---

#### GOV-2-2: Task Activation Request
**As an** Earl
**I want** to create task activation requests for Clusters
**So that** work can be offered to human participants

**Acceptance Criteria:**
- [ ] Earl can create activation request with task details
- [ ] Request includes TTL (72h default)
- [ ] Request routed to Cluster via async protocol (email)
- [ ] Event `executive.task.activated` emitted to ledger
- [ ] Earl can view task state and history (FR12)
- [ ] Unit tests for activation request creation

**Technical Notes:**
- Location: `src/application/services/governance/task_activation_service.py`
- Reference: FR1, FR12, NFR-INT-01

---

#### GOV-2-3: Task Consent Operations
**As a** Cluster
**I want** to accept or decline task activation requests
**So that** I maintain control over my participation

**Acceptance Criteria:**
- [ ] Cluster can view pending requests (FR2)
- [ ] Cluster can accept request (FR3)
- [ ] Cluster can decline request without justification (FR4)
- [ ] Cluster can halt in-progress task without penalty (FR5)
- [ ] Declining does not reduce standing or trigger penalties
- [ ] Events emitted: `executive.task.accepted`, `executive.task.declined`, `executive.task.halted`
- [ ] Unit tests for accept, decline, and halt operations

**Technical Notes:**
- Location: `src/application/services/governance/task_consent_service.py`
- Reference: FR2-FR5

---

#### GOV-2-4: Task Result Submission
**As a** Cluster
**I want** to submit task results and problem reports
**So that** my work is recorded and issues are surfaced

**Acceptance Criteria:**
- [ ] Cluster can submit task result report (FR6)
- [ ] Cluster can submit problem report for in-progress task (FR7)
- [ ] Result transitions task from `in_progress` to `reported`
- [ ] Events emitted: `executive.task.reported`, `executive.task.problem_reported`
- [ ] Unit tests for result and problem submissions

**Technical Notes:**
- Location: `src/application/services/governance/task_result_service.py`
- Reference: FR6, FR7

---

#### GOV-2-5: Task TTL & Auto-Transitions
**As a** governance system
**I want** automatic task state transitions based on timeouts
**So that** stale tasks don't block the system

**Acceptance Criteria:**
- [ ] Auto-decline after TTL expiration (72h default) with no failure attribution (FR8)
- [ ] Auto-transition accepted→in_progress after inactivity (48h) (FR9)
- [ ] Auto-quarantine tasks exceeding reporting timeout (7d default) (FR10)
- [ ] TTL expiration → `declined` state (NFR-CONSENT-01)
- [ ] All auto-transitions emit events with system as actor
- [ ] Unit tests for each timeout scenario

**Technical Notes:**
- Location: `src/application/services/governance/task_timeout_service.py`
- Reference: FR8-FR10, NFR-CONSENT-01

---

#### GOV-2-6: Task Reminders
**As a** governance system
**I want** to send neutral reminders at TTL milestones
**So that** participants are informed without coercion

**Acceptance Criteria:**
- [ ] Reminder at 50% of TTL (FR11)
- [ ] Reminder at 90% of TTL (FR11)
- [ ] Reminders must pass through Coercion Filter (see GOV-3)
- [ ] Reminder is informational, not pressuring
- [ ] Event `executive.task.reminder_sent` emitted
- [ ] Unit tests for reminder timing

**Technical Notes:**
- Location: `src/application/services/governance/task_reminder_service.py`
- Reference: FR11

---

#### GOV-2-7: Role-Specific Task Constraints
**As a** governance system
**I want** role-specific constraints enforced within each rank
**So that** task operations respect branch authority

**Acceptance Criteria:**
- [ ] Earl can only activate (not compel or change scope)
- [ ] Cluster can only be activated (not commanded)
- [ ] Role constraints validated at operation time
- [ ] Constraint violations logged and rejected
- [ ] Unit tests for constraint enforcement

**Technical Notes:**
- Location: `src/application/services/governance/task_constraint_service.py`
- Reference: FR14

---

## GOV-3: Coercion-Free Communication

**Epic Summary:** Implement the Coercion Filter that protects all participant-facing communications from manipulative language.

**User Value:** All communications with human participants are free from coercive, manipulative, or engagement-optimized language.

**FRs Addressed:** FR15-FR21

**NFRs Addressed:**
- NFR-CONST-05: No API bypass of Coercion Filter
- NFR-PERF-03: Filter processes in ≤200ms
- NFR-UX-01: Communications free of engagement-optimization

### Stories

#### GOV-3-1: Coercion Filter Domain Model
**As a** governance system
**I want** a Coercion Filter domain model
**So that** content filtering has clear structure and outcomes

**Acceptance Criteria:**
- [ ] Filter outcomes: `accept` (with transformation), `reject` (require rewrite), `block` (hard violation)
- [ ] `FilteredContent` type required for all participant-facing output
- [ ] Unfiltered content cannot reach participants (type system enforced)
- [ ] Filter version tracked for auditability
- [ ] Unit tests for each outcome type

**Technical Notes:**
- Location: `src/domain/governance/filter/`
- Reference: AD-14, FR16-FR18

---

#### GOV-3-2: Coercion Filter Service
**As a** governance system
**I want** a filter service that processes content
**So that** coercive language is detected and handled

**Acceptance Criteria:**
- [ ] Filter processes content in ≤200ms (NFR-PERF-03)
- [ ] Determinism is primary; speed is secondary
- [ ] All participant-facing messages routed through filter (FR21)
- [ ] No API or administrative bypass path exists (NFR-CONST-05)
- [ ] Unit tests for filter processing

**Technical Notes:**
- Location: `src/application/services/governance/coercion_filter_service.py`
- Reference: FR15, FR21, NFR-CONST-05, NFR-PERF-03

---

#### GOV-3-3: Filter Decision Logging
**As an** auditor
**I want** all filter decisions logged
**So that** I can review what was filtered and why

**Acceptance Criteria:**
- [ ] All decisions logged with input, output, version, timestamp (FR20)
- [ ] Earl can view filter outcome before content is sent (FR19)
- [ ] Logs include transformation details for `accept` outcomes
- [ ] Logs include rejection reason for `reject` outcomes
- [ ] Logs include violation details for `block` outcomes
- [ ] Event `custodial.filter.decision_logged` emitted
- [ ] Unit tests for logging each outcome type

**Technical Notes:**
- Location: `src/application/services/governance/filter_logging_service.py`
- Reference: FR19, FR20, NFR-AUDIT-02

---

#### GOV-3-4: Coercion Pattern Detection
**As a** governance system
**I want** detection of coercive language patterns
**So that** manipulative content is identified

**Acceptance Criteria:**
- [ ] Detection of urgency pressure ("act now", "limited time")
- [ ] Detection of guilt induction ("you owe", "disappointing")
- [ ] Detection of false scarcity
- [ ] Detection of engagement-optimization language
- [ ] Pattern library versioned and auditable
- [ ] Unit tests for each pattern category

**Technical Notes:**
- Location: `src/domain/governance/filter/coercion_patterns.py`
- Reference: NFR-UX-01

---

## GOV-4: Emergency Safety Circuit

**Epic Summary:** Implement the halt circuit that can stop the system immediately and safely.

**User Value:** The system can be stopped instantly (<100ms) by a human operator, safely transitioning all tasks to known states.

**FRs Addressed:** FR22-FR27

**NFRs Addressed:**
- NFR-PERF-01: Halt completes in ≤100ms
- NFR-ATOMIC-01: Atomic transitions
- NFR-REL-01: Dedicated execution path
- NFR-REL-03: In-flight tasks resolve deterministically

### Stories

#### GOV-4-1: Halt Circuit Port & Adapter
**As a** governance system
**I want** a three-channel halt circuit
**So that** halts propagate reliably through all components

**Acceptance Criteria:**
- [ ] In-memory channel (primary, fastest)
- [ ] Redis channel (propagation to other instances)
- [ ] Ledger channel (permanent recording)
- [ ] Dedicated execution path with no shared dependencies (NFR-REL-01)
- [ ] Halt completes in ≤100ms under worst-case load (NFR-PERF-01)
- [ ] Unit tests for each channel

**Technical Notes:**
- Port: `src/application/ports/governance/halt_circuit_port.py`
- Adapter: `src/infrastructure/adapters/governance/halt_circuit_adapter.py`
- Reference: AD-2, NFR-PERF-01, NFR-REL-01

---

#### GOV-4-2: Halt Trigger & Execution
**As a** Human Operator
**I want** to trigger a system halt
**So that** I can stop operations immediately when needed

**Acceptance Criteria:**
- [ ] Human Operator can trigger halt (FR22)
- [ ] System executes halt operation (FR23)
- [ ] Halt propagates to all components
- [ ] Event `constitutional.halt.triggered` emitted
- [ ] Event `constitutional.halt.executed` emitted on completion
- [ ] Unit tests for halt trigger and execution

**Technical Notes:**
- Location: `src/application/services/governance/halt_service.py`
- Reference: FR22, FR23

---

#### GOV-4-3: Task State Transitions on Halt
**As a** governance system
**I want** tasks to transition deterministically on halt
**So that** all work is in a known state after halt

**Acceptance Criteria:**
- [ ] Pre-consent tasks → `nullified` (FR24)
- [ ] Post-consent tasks → `quarantined` (FR25)
- [ ] Completed tasks unchanged (FR26)
- [ ] State transitions are atomic (FR27, NFR-ATOMIC-01)
- [ ] In-flight tasks resolve deterministically (NFR-REL-03)
- [ ] All transitions emit events
- [ ] Unit tests for each task state category

**Technical Notes:**
- Location: `src/application/services/governance/halt_task_transition_service.py`
- Reference: FR24-FR27, NFR-ATOMIC-01, NFR-REL-03

---

## GOV-5: Legitimacy Visibility

**Epic Summary:** Implement the legitimacy band system that makes system health visible.

**User Value:** System health is transparently visible through banded legitimacy states, with clear transitions and no hidden decay.

**FRs Addressed:** FR28-FR32

**NFRs Addressed:**
- NFR-AUDIT-04: Transitions include triggering event reference
- NFR-CONST-04: All transitions logged with timestamp and actor

### Stories

#### GOV-5-1: Legitimacy Band Domain Model
**As a** governance system
**I want** a legitimacy band state machine
**So that** system health has clear states and transitions

**Acceptance Criteria:**
- [ ] Bands: `Stable`, `Strained`, `Eroding`, `Compromised`, `Failed`
- [ ] State machine enforces valid transitions only
- [ ] Current band tracked (FR28)
- [ ] Band state queryable by any participant
- [ ] Unit tests for band transitions

**Technical Notes:**
- Location: `src/domain/governance/legitimacy/`
- Reference: FR28

---

#### GOV-5-2: Automatic Downward Transitions
**As a** governance system
**I want** automatic legitimacy decay based on violations
**So that** system health degrades visibly when problems occur

**Acceptance Criteria:**
- [ ] Auto-transition downward based on violation events (FR29)
- [ ] Transition includes triggering event reference (NFR-AUDIT-04)
- [ ] All transitions logged with timestamp, actor, reason (NFR-CONST-04)
- [ ] Event `constitutional.legitimacy.band_decreased` emitted
- [ ] Unit tests for auto-decay scenarios

**Technical Notes:**
- Location: `src/application/services/governance/legitimacy_decay_service.py`
- Reference: FR29, NFR-AUDIT-04, NFR-CONST-04

---

#### GOV-5-3: Explicit Upward Transitions
**As a** Human Operator
**I want** to acknowledge and execute upward legitimacy transitions
**So that** restoration requires explicit human decision

**Acceptance Criteria:**
- [ ] Upward transition requires explicit acknowledgment (FR30)
- [ ] No automatic upward transitions (FR32)
- [ ] Acknowledgment logged in append-only ledger (FR31)
- [ ] Event `constitutional.legitimacy.band_increased` emitted
- [ ] Unit tests for acknowledgment requirement

**Technical Notes:**
- Location: `src/application/services/governance/legitimacy_restoration_service.py`
- Reference: FR30-FR32

---

## GOV-6: Violation Witness & Accountability

**Epic Summary:** Implement the Knight witness system and Prince Panel for violation handling.

**User Value:** Violations are observed by neutral witnesses, recorded without judgment, and handled through multi-member panels with preserved dissent.

**FRs Addressed:** FR33-FR41

**NFRs Addressed:**
- NFR-CONST-06: Panel findings cannot be modified
- NFR-CONST-07: Witness statements cannot be suppressed
- NFR-OBS-01: Events observable within ≤1 second
- NFR-AUDIT-01: All branch actions logged for Knight

### Stories

#### GOV-6-1: Knight Witness Domain Model
**As a** governance system
**I want** a Knight witness capability
**So that** violations can be observed and recorded neutrally

**Acceptance Criteria:**
- [ ] Knight can observe all branch actions (FR33)
- [ ] Knight observes but does not judge or enforce
- [ ] Witness statements are observation only, no judgment (FR34)
- [ ] Statements cannot be suppressed by any role (NFR-CONST-07)
- [ ] Unit tests for witness statement creation

**Technical Notes:**
- Location: `src/domain/governance/witness/`
- Reference: FR33, FR34, NFR-CONST-07

---

#### GOV-6-2: Passive Knight Observation
**As a** Knight
**I want** passive observation via event subscription
**So that** I see all branch actions without active intervention

**Acceptance Criteria:**
- [ ] Event bus subscription for real-time observation
- [ ] Ledger replay as verification backstop
- [ ] Events observable within ≤1 second (NFR-OBS-01)
- [ ] All branch actions logged with sufficient detail (NFR-AUDIT-01)
- [ ] Knight can observe Prince Panel conduct (FR41)
- [ ] Unit tests for observation mechanics

**Technical Notes:**
- Location: `src/application/services/governance/knight_observation_service.py`
- Reference: AD-16, FR41, NFR-OBS-01, NFR-AUDIT-01

---

#### GOV-6-3: Witness Statement Routing
**As a** governance system
**I want** witness statements routed to Prince Panel queue
**So that** violations are queued for review

**Acceptance Criteria:**
- [ ] Statements routed to Prince Panel queue (FR35)
- [ ] Queue is append-only (no deletion)
- [ ] Event `judicial.witness.statement_queued` emitted
- [ ] Unit tests for routing mechanics

**Technical Notes:**
- Location: `src/application/services/governance/witness_routing_service.py`
- Reference: FR35

---

#### GOV-6-4: Prince Panel Domain Model
**As a** governance system
**I want** a Prince Panel domain model
**So that** panels can review and issue findings

**Acceptance Criteria:**
- [ ] Panel requires ≥3 members (FR36)
- [ ] Human Operator convenes panel
- [ ] Panel can review witness artifacts (FR37)
- [ ] Panel can issue formal finding with remedy (FR38)
- [ ] Panel can record dissent in finding (FR39)
- [ ] Unit tests for panel mechanics

**Technical Notes:**
- Location: `src/domain/governance/panel/`
- Reference: FR36-FR39

---

#### GOV-6-5: Panel Finding Preservation
**As an** auditor
**I want** panel findings preserved immutably
**So that** judicial outcomes cannot be altered

**Acceptance Criteria:**
- [ ] Findings recorded in append-only ledger (FR40)
- [ ] Findings cannot be deleted or modified (NFR-CONST-06)
- [ ] Dissent preserved alongside majority finding
- [ ] Event `judicial.panel.finding_issued` emitted
- [ ] Unit tests for immutability

**Technical Notes:**
- Location: `src/application/services/governance/panel_finding_service.py`
- Reference: FR40, NFR-CONST-06

---

## GOV-7: Dignified Exit

**Epic Summary:** Implement the exit protocol that allows humans to leave with dignity.

**User Value:** Humans can leave the system at any time, from any state, with their dignity preserved and no follow-up contact.

**FRs Addressed:** FR42-FR46

**NFRs Addressed:**
- NFR-EXIT-01: Exit completes in ≤2 message round-trips
- NFR-EXIT-02: No follow-up contact mechanism exists
- NFR-EXIT-03: Exit path available from any task state

### Stories

#### GOV-7-1: Exit Request Processing
**As a** Cluster
**I want** to initiate and complete an exit request
**So that** I can leave the system cleanly

**Acceptance Criteria:**
- [ ] Cluster can initiate exit request (FR42)
- [ ] System processes exit request (FR43)
- [ ] Exit completes in ≤2 message round-trips (NFR-EXIT-01)
- [ ] Exit path available from any task state (NFR-EXIT-03)
- [ ] Event `custodial.exit.initiated` and `custodial.exit.completed` emitted
- [ ] Unit tests for exit from each task state

**Technical Notes:**
- Location: `src/application/services/governance/exit_service.py`
- Reference: FR42, FR43, NFR-EXIT-01, NFR-EXIT-03

---

#### GOV-7-2: Obligation Release
**As a** Cluster
**I want** all obligations released on exit
**So that** I leave with no lingering commitments

**Acceptance Criteria:**
- [ ] All obligations released on exit (FR44)
- [ ] Active tasks transitioned to appropriate states
- [ ] Pending requests cancelled
- [ ] No penalty applied for early exit
- [ ] Unit tests for obligation release

**Technical Notes:**
- Location: `src/application/services/governance/obligation_release_service.py`
- Reference: FR44

---

#### GOV-7-3: Contribution Preservation
**As a** Cluster
**I want** my contribution history preserved on exit
**So that** my work remains attributed even after I leave

**Acceptance Criteria:**
- [ ] Contribution history preserved (FR45)
- [ ] History remains in ledger (immutable)
- [ ] Attribution maintained without PII
- [ ] Unit tests for preservation

**Technical Notes:**
- Location: `src/application/services/governance/contribution_preservation_service.py`
- Reference: FR45

---

#### GOV-7-4: Follow-Up Contact Prevention
**As a** Cluster
**I want** no follow-up contact after exit
**So that** my departure is truly final

**Acceptance Criteria:**
- [ ] No follow-up contact mechanism exists (FR46, NFR-EXIT-02)
- [ ] Contact endpoint removed/blocked on exit
- [ ] Re-engagement requires explicit new initiation
- [ ] Unit tests verify no contact path exists

**Technical Notes:**
- Location: `src/application/services/governance/contact_prevention_service.py`
- Reference: FR46, NFR-EXIT-02

---

## GOV-8: System Lifecycle Management

**Epic Summary:** Implement cessation and reconstitution that allows the system to stop and restart properly.

**User Value:** The system can stop honorably with complete records, and any restart cannot falsely claim continuity with the previous instance.

**FRs Addressed:** FR47-FR55

**NFRs Addressed:**
- NFR-REL-05: Cessation Record creation is atomic

### Stories

#### GOV-8-1: System Cessation Trigger
**As a** Human Operator
**I want** to trigger system cessation
**So that** the system can stop operations honorably

**Acceptance Criteria:**
- [ ] Human Operator can trigger cessation (FR47)
- [ ] Cessation blocks new motions (FR49)
- [ ] Cessation halts execution (FR50)
- [ ] Event `constitutional.cessation.triggered` emitted
- [ ] Unit tests for cessation trigger

**Technical Notes:**
- Location: `src/application/services/governance/cessation_trigger_service.py`
- Reference: FR47, FR49, FR50

---

#### GOV-8-2: Cessation Record Creation
**As a** governance system
**I want** an immutable Cessation Record created on cessation
**So that** the shutdown is formally documented

**Acceptance Criteria:**
- [ ] Immutable Cessation Record created (FR48)
- [ ] Creation is atomic (NFR-REL-05)
- [ ] All records preserved (FR51)
- [ ] In-progress work labeled `interrupted_by_cessation` (FR52)
- [ ] Event `constitutional.cessation.record_created` emitted
- [ ] Unit tests for record creation

**Technical Notes:**
- Location: `src/application/services/governance/cessation_record_service.py`
- Reference: FR48, FR51, FR52, NFR-REL-05

---

#### GOV-8-3: Reconstitution Validation
**As a** governance system
**I want** reconstitution artifacts validated before new instance
**So that** new instances don't falsely inherit legitimacy

**Acceptance Criteria:**
- [ ] Reconstitution Artifact validated (FR53)
- [ ] Reject reconstitution claiming continuity (FR54)
- [ ] Reject reconstitution inheriting legitimacy band (FR55)
- [ ] New instance starts at baseline legitimacy
- [ ] Unit tests for validation rules

**Technical Notes:**
- Location: `src/application/services/governance/reconstitution_validation_service.py`
- Reference: FR53-FR55

---

## GOV-9: Audit & Verification

**Epic Summary:** Implement audit and verification capabilities for independent ledger verification.

**User Value:** Anyone can export the complete ledger, verify its integrity independently, and derive system state through replay.

**FRs Addressed:** FR56-FR60

**NFRs Addressed:**
- NFR-AUDIT-02 to 06
- NFR-INT-02: Ledger contains no PII

### Stories

#### GOV-9-1: Ledger Export
**As a** participant
**I want** to export the complete ledger
**So that** I can independently verify system history

**Acceptance Criteria:**
- [ ] Any participant can export complete ledger (FR56)
- [ ] Partial export is impossible (NFR-CONST-03)
- [ ] Export format is JSON (machine-readable) and human-auditable (NFR-AUDIT-05)
- [ ] Ledger contains no PII (NFR-INT-02)
- [ ] Unit tests for export completeness

**Technical Notes:**
- Location: `src/application/services/governance/ledger_export_service.py`
- Reference: FR56, NFR-CONST-03, NFR-AUDIT-05, NFR-INT-02

---

#### GOV-9-2: Cryptographic Proof Generation
**As a** verifier
**I want** cryptographic proofs of ledger completeness
**So that** I can verify nothing is missing

**Acceptance Criteria:**
- [ ] System provides cryptographic proof of completeness (FR57)
- [ ] Proof uses hash chain and Merkle tree
- [ ] Proof independently verifiable
- [ ] Unit tests for proof generation

**Technical Notes:**
- Location: `src/application/services/governance/ledger_proof_service.py`
- Reference: FR57

---

#### GOV-9-3: Independent Verification
**As a** verifier
**I want** to independently verify ledger integrity
**So that** I don't have to trust the system

**Acceptance Criteria:**
- [ ] Independent hash chain verification (FR58)
- [ ] Independent Merkle proof verification
- [ ] State derivable through event replay (NFR-AUDIT-06)
- [ ] Verification possible offline with exported ledger
- [ ] Unit tests for verification

**Technical Notes:**
- Location: `src/domain/governance/verification/`
- Reference: FR58, NFR-AUDIT-06

---

#### GOV-9-4: State Transition Logging
**As an** auditor
**I want** all state transitions logged with full context
**So that** I can trace what happened and why

**Acceptance Criteria:**
- [ ] All transitions logged with timestamp and actor (FR59)
- [ ] Reason/trigger included in log
- [ ] No modification of logs (append-only) (FR60)
- [ ] Unit tests for log completeness

**Technical Notes:**
- Location: `src/application/services/governance/transition_logging_service.py`
- Reference: FR59, FR60

---

## GOV-10: Anti-Metrics Foundation

**Epic Summary:** Implement the anti-metrics constraints that prevent surveillance.

**User Value:** The system operates without engagement tracking, retention metrics, or performance scoring - no surveillance of participants.

**FRs Addressed:** FR61-FR63

**NFRs Addressed:**
- NFR-CONST-08: Anti-metrics enforced at data layer

### Stories

#### GOV-10-1: Anti-Metrics Data Layer Enforcement
**As a** governance system
**I want** anti-metrics enforced at the data layer
**So that** no collection endpoints exist

**Acceptance Criteria:**
- [ ] No participant-level performance metrics stored (FR61)
- [ ] No completion rates per participant calculated (FR62)
- [ ] No engagement or retention tracking (FR63)
- [ ] Collection endpoints do not exist (NFR-CONST-08)
- [ ] Schema validation prevents metric tables
- [ ] Unit tests verify no metric collection paths

**Technical Notes:**
- Location: `src/infrastructure/adapters/governance/anti_metrics_guard.py`
- Reference: FR61-FR63, NFR-CONST-08

---

#### GOV-10-2: Anti-Metrics Verification
**As an** auditor
**I want** to verify no metrics are collected
**So that** I can confirm the anti-surveillance guarantee

**Acceptance Criteria:**
- [ ] Audit query confirms no metric tables
- [ ] Audit confirms no metric API endpoints
- [ ] Periodic verification job
- [ ] Unit tests for verification

**Technical Notes:**
- Location: `src/application/services/governance/anti_metrics_verification_service.py`
- Reference: NFR-CONST-08
