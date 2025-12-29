---
stepsCompleted: [1, 2, 3, 4]
workflowComplete: true
inputDocuments:
  - _bmad-output/planning-artifacts/prd.md
  - _bmad-output/planning-artifacts/conclave-prd-amendment-notes.md
  - _bmad-output/planning-artifacts/architecture.md
  - _bmad-output/planning-artifacts/mitigation-architecture-spec.md
prdVersion: '2025-12-28 (147 FRs, 104 NFRs)'
architectureVersion: '2025-12-28 (Complete, 5490 lines)'
---

# Archon 72 - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for **Archon 72**, decomposing 147 Functional Requirements and 104 Non-Functional Requirements from the PRD and Architecture into implementable stories.

## Requirements Inventory

### Functional Requirements

**Total: 147 Functional Requirements**

| Cluster | FR Range | Count | Source |
|---------|----------|-------|--------|
| Event Store & Witnessing | FR1-FR8 | 8 | Core Capabilities |
| Agent Deliberation | FR9-FR15 | 7 | Core Capabilities |
| Fork Detection & Recovery | FR16-FR22 | 7 | Core Capabilities |
| Override & Keeper Actions | FR23-FR29 | 7 | Core Capabilities |
| Breach & Threshold | FR30-FR36 | 7 | Core Capabilities |
| Cessation Protocol | FR37-FR43 | 7 | Core Capabilities |
| Observer Interface | FR44-FR50 | 7 | Core Capabilities |
| Operational Monitoring | FR51-FR54 | 4 | Core Capabilities |
| Emergence Governance | FR55-FR58 | 4 | Core Capabilities |
| Pre-mortem: Failure Prevention | FR59-FR79 | 21 | Advanced Elicitation |
| First Principles: Primitives | FR80-FR95 | 16 | Advanced Elicitation |
| Critical Perspective: Expert Challenges | FR96-FR113 | 18 | Advanced Elicitation |
| Red Team: Attack Defense | FR114-FR135 | 22 | Advanced Elicitation |
| Comparative Analysis: Industry | FR136-FR147 | 12 | Advanced Elicitation |

**Core Capability Areas (FR1-FR58):**

- **FR1-FR8 Event Store & Witnessing:** Append-only events, hash linking, agent/witness attribution, cryptographic signatures, dual time authorities, algorithm versioning
- **FR9-FR15 Agent Deliberation:** No Preview constraint, 72 concurrent agents, collective outputs, dissent tracking, no silent edits
- **FR16-FR22 Fork Detection:** Continuous monitoring, single-conflict halt, constitutional crisis events, read-only during halt, 48-hour recovery waiting period
- **FR23-FR29 Override & Keeper:** Immediate logging, attribution, public visibility, trend analysis, anti-success alerts
- **FR30-FR36 Breach & Threshold:** Breach events, 7-day escalation, cessation triggers, constitutional thresholds, counter protection
- **FR37-FR43 Cessation Protocol:** Automatic agenda placement, schema-enforced irreversibility, freeze mechanics, final recorded event
- **FR44-FR50 Observer Interface:** Public read access, raw events with hashes, date/type filtering, open-source verification toolkit
- **FR51-FR54 Operational Monitoring:** Uptime/latency/errors, operational-constitutional firewall, external detectability
- **FR55-FR58 Emergence Governance:** No self-certification, keyword scanning, quarterly audit, ecosystem prohibition

**Advanced Elicitation (FR59-FR147):**

- **FR59-FR79 Pre-mortem:** Witness collusion defense, hash verification, keeper impersonation prevention, topic manipulation defense
- **FR80-FR95 First Principles:** PREVENT_DELETE, ENSURE_ATOMICITY, VERIFY_AGENT, DETECT_GAP, REFUSE_OVERRIDE, QUERY_AS_OF, heartbeats
- **FR96-FR113 Critical Perspective:** Key lifecycle, deliberation quality, disaster recovery, scale realism, privacy/regulatory, partition handling
- **FR114-FR135 Red Team:** Halt flooding defense, witness targeting, topic flooding, heartbeat spoofing, observer poisoning, seed manipulation, amendment erosion, keeper collusion, cessation gaming
- **FR136-FR147 Comparative Analysis:** Light verification, checkpointing, regulatory reporting, attestation, result certification, safety case, incident investigation

### Non-Functional Requirements

**Total: 104 Non-Functional Requirements**

| Cluster | NFR Range | Count | Source |
|---------|-----------|-------|--------|
| Performance | NFR1-6 | 6 | Core |
| Availability | NFR7-11 | 5 | Core |
| Durability & Reliability | NFR12-16 | 5 | Core |
| Security | NFR17-22 | 6 | Core |
| Scalability | NFR23-26 | 4 | Core |
| Observability | NFR27-30 | 4 | Core |
| Compliance | NFR31-34 | 4 | Core |
| Operational | NFR35-38 | 4 | Core |
| Constitutional Constraint | NFR39-42 | 4 | Core |
| Pre-mortem: Operational Failures | NFR43-66 | 24 | Advanced Elicitation |
| First Principles: Quality Primitives | NFR67-86 | 20 | Advanced Elicitation |
| Critical Perspective: Expert Challenges | NFR87-104 | 18 | Advanced Elicitation |

**Key NFRs:**

- NFR1: Event write latency <100ms (95th percentile)
- NFR5: 72 concurrent agent deliberations without degradation
- NFR7: Event store availability 99.9%
- NFR12: Minimum 3 geographically distributed replicas
- NFR15: Append-only with no deletion capability
- NFR19: SHA-256 minimum for hash chain
- NFR39: No configuration below constitutional floors
- NFR40: No cessation reversal event type in schema

### Additional Requirements (Architecture)

**Starter Template:** Build-first, extract-template-second (no existing starter)

**Technology Stack:**
- Python 3.11+ (async/await required)
- FastAPI (async-first API)
- CrewAI (multi-agent orchestration)
- PostgreSQL 16 via Supabase
- Redis (locks + events, halt transport)

**12 ADRs to Implement:**
- ADR-1: Event Store Topology (Supabase + DB-level enforcement)
- ADR-2: Context Reconstruction + Signature Trust
- ADR-3: Partition Behavior + Halt Durability (Dual-channel)
- ADR-4: Key Custody + Keeper Adversarial Defense
- ADR-5: Watchdog Independence + Restart
- ADR-6 through ADR-12: Ceremonies, Anomaly Detection, Observer, Verification, Health, Complexity, Crisis

**10 Critical Hardening (CH-1 to CH-10):**
- Writer self-verification, replica verification, partition detection, ceremony durability, precedent verification, heartbeat timeout, agent suspension, witness retry, halt rate limit, off-hours quorum

**Sprint 0 Priorities:**
1. Event Store + Hash Chaining (ADR-1)
2. Dual-Channel Halt Transport (ADR-3)
3. Context Bundle Signing (ADR-2)
4. Watchdog Independence (ADR-5)
5. Developer HSM Stub (ADR-4)

**Compliance:
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
| FR-ME-002 | Epic 2 | Quorum verification |
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
| FR-CM-006 | Epic 5 | Blinding verification |
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

### Epic 0: Project Foundation & Constitutional Infrastructure
**User Outcome:** Development team can build constitutional features on a validated hexagonal architecture foundation with dev environment ready.

**FRs covered:** FR80, FR81 (atomicity, delete prevention), Architecture setup

**Time-box:** 2 weeks maximum (PM-1 prevention)

**Definition of Done:**
- `make dev` works end-to-end
- One domain test passes without infrastructure
- HSM stub successfully signs one test event
- Pre-commit hooks reject cross-layer imports
- Integration test framework runs with `make test-integration`

**Delivers:**
- Hexagonal architecture scaffold (domain/application/infrastructure/api layers)
- Python 3.11+ project with FastAPI, CrewAI, Supabase, Redis
- Dev environment with `make dev` target
- Software HSM stub with [DEV MODE] watermark
- Constitutional primitives (PREVENT_DELETE, ENSURE_ATOMICITY)
- Import boundary enforcement (pre-commit hooks)
- **Integration test framework** (pytest + testcontainers for Supabase/Redis) (SR-1)

**Runbook Requirement:** Epic 0 runbook: "Developer Environment Setup"

**ADR Implementation:** Foundation for ADR-1, ADR-4

**Parallelization:** Epic 1 can start after day 3 once scaffold is committed

---

### Epic 1: Witnessed Event Store
**User Outcome:** External observers can verify that events are append-only, hash-chained, and witnessed with cryptographic signatures.

**FRs covered:** FR1-FR8, FR62-FR67, FR74-FR76, FR82-FR85, FR94-FR95, FR102-FR104

**Uses from Epic 0:** FR80, FR81 (PREVENT_DELETE, ENSURE_ATOMICITY primitives)

**NFRs owned:** NFR1 (<100ms write), NFR12 (3 replicas), NFR15 (append-only), NFR19 (SHA-256)

**Delivers:**
- Append-only event store with Supabase + DB-level enforcement
- Hash-chained events with SHA-256
- Agent attribution with cryptographic signatures
- Witness attribution with cryptographic signatures
- Dual time authority timestamps
- Algorithm versioning in every event
- Sequence numbers for deterministic ordering
- Geographic replica distribution (3 replicas)
- Event propagation with receipt confirmation
- **Halt check interface (stub)** - allows event store to check halt without Epic 3 (PM-2)
- **Observer query schema design spike** - shapes schema for Epic 4 needs (PM-3)
- **Supabase trigger spike** - validate DB-level hash enforcement approach (SR-3)
- **Event + witness atomic transaction** - no partial writes allowed (RT-1)

**Runbook Requirement:** Epic 1 runbook: "Event Store Operations & Recovery"

**Cross-Epic Requirements:**
- FR26 (overrides cannot suppress witnessing) - Epic 1 enforces, Epic 5 invokes (PM-4)

**Red Team Hardening (RT-1):**
- Event and witness signature must be in single atomic transaction
- If witness unavailable, entire write fails (no unwitnessed events)
- Witness pool availability check before write attempt

**First Principles (FP-1):**
- CT-1: Event store enables agent state reconstruction (LLMs are stateless)
- Any agent can rebuild context from event sequence
- Point-in-time queries support deterministic replay

**ADR Implementation:** ADR-1 (Event Store Topology)

---

### Epic 2: Agent Deliberation & Collective Output
**User Outcome:** 72 agents can deliberate and produce collective outputs that are recorded before any human sees them (No Preview constraint).

**FRs covered:** FR9-FR15, FR71-FR73, FR82-FR83, FR90-FR93, FR99-FR101, FR141-FR142

**Delivers:**
- No Preview constraint (record-before-view)
- 72 concurrent agent deliberations
- Collective outputs irreducible to single agent
- Dissent percentage tracking in vote tallies
- No Silent Edits (published hash = canonical hash)
- Agent heartbeat monitoring
- Topic origin tracking (autonomous, petition, scheduled)
- Topic diversity enforcement (no >30% from single source)
- Result certification with certified result events
- Procedural record generation
- **72-agent load test spike** - validate CrewAI at scale (SR-4)

**Runbook Requirement:** Epic 2 runbook: "Agent Deliberation Monitoring"

**ADR Implementation:** ADR-2 (Context Reconstruction + Signature Trust)

---

### Epic 3: Halt & Fork Detection
**User Outcome:** System halts visibly when integrity is threatened, preventing silent corruption. Fork = constitutional crisis.

**Prerequisites:** Epic 1 (Event Store) - uses halt check stub from Epic 1 (PM-2)

**FRs covered:** FR16-FR22, FR84-FR85, FR111-FR113, FR114-FR115, FR143

**NFRs owned:** NFR7 (99.9% availability excluding halt), NFR39 (no config below floors)

**Delivers:**
- Continuous fork monitoring (conflicting hashes from same prior state)
- Single-conflict halt trigger
- Constitutional crisis event on fork detection
- Read-only access during halt (no provisional operations)
- 48-hour recovery waiting period with public notification
- Unanimous Keeper agreement for recovery
- Sequence gap detection within 1 minute
- Dual-channel halt transport (Redis + DB flag)
- **Halt channel conflict resolution** - explicit logic when Redis/DB disagree (SR-5)
- Signed fork detection signals
- Fork signal rate limiting (3/hour per source)
- Operational rollback to checkpoint anchors
- **Witnessed halt event before stop** - halt signal creates event before effect (RT-2)

**Runbook Requirement:** Epic 3 runbook: "Halt & Fork Recovery Procedures"

**Infrastructure Note (SR-6):** Geographic replica provisioning deferred to deployment phase; Epic 3 assumes single-region staging.

**Red Team Hardening (RT-2):**
- All halt signals must create witnessed halt event BEFORE system stops
- Halt from Redis must be confirmed against DB within 5 seconds
- Phantom halts detectable via halt event mismatch analysis

**First Principles (FP-2):**
- CT-8: Failure modes compound - design for simultaneous failure
- Cascading failure analysis: halt + partition + corruption scenarios
- Test matrix: what if halt channel fails during fork detection?
- Recovery procedures must handle compound failures

**ADR Implementation:** ADR-3 (Partition Behavior + Halt Durability)

---

### Epic 4: Observer Verification Interface
**User Outcome:** External auditors can independently verify chain integrity without registration, using open-source toolkit.

**FRs covered:** FR44-FR50, FR62-FR64, FR88-FR89, FR122-FR123, FR129-FR130, FR136-FR140

**Delivers:**
- Public read access without registration
- Raw events with hashes returned
- Date range and event type filtering
- Open-source verification toolkit (downloadable)
- Schema documentation with same availability as event store
- Identical rate limits for anonymous and registered access
- Historical queries (state as of any sequence number)
- Hash chain proof connecting queried state to current head
- Cryptographic proof in responses linking to canonical store
- Merkle paths for light verification
- Weekly checkpoint anchors
- Regulatory reporting export (structured audit format)
- Third-party attestation interface
- Sequence gap detection for observers
- **Observer push notifications** - webhook/SSE for breach events (SR-9)
- **Observer API uptime SLA** - 99.9% with external monitoring (RT-5)

**Runbook Requirement:** Epic 4 runbook: "Observer API Operations"

**Red Team Hardening (RT-5):**
- Observer API 99.9% uptime SLA with external uptime monitoring
- Fallback to checkpoint anchor when API unavailable
- Breach events pushed to multiple channels (not just pull)
- External parties can verify via genesis anchor even during API outage

**ADR Implementation:** ADR-8 (Observer Consistency + Genesis Anchor), ADR-9 (Claim Verification)

---

### Epic 5: Override & Keeper Actions
**User Outcome:** Human Keepers can intervene with full attribution and public visibility. Override is expensive and visible.

**Prerequisites:** Epic 1 (Event Store) - FR26 enforcement wired in Epic 1

**FRs covered:** FR23-FR29, FR68-FR70, FR77-FR79, FR86-FR87, FR96-FR98, FR131-FR133

**NFRs owned:** NFR17 (key custody), NFR22 (audit logging)

**Delivers:**
- Immediate logging before override takes effect
- Keeper attribution with scope, duration, reason
- Public visibility of all overrides
- Constitution supremacy (overrides cannot suppress witnessing)
- 90-day rolling window trend analysis
- Anti-success alerts (>50% increase or >5 in 30 days)
- Cryptographic signature from registered Keeper key
- Witnessed ceremony for Keeper key generation
- Full authorization chain recording
- Override command validation against constitutional constraints
- Override abuse rejection and logging
- Keeper availability attestation (weekly, 2 missed = replacement)
- Minimum 3 Keeper quorum (halt if below)
- Annual key rotation with 30-day transition
- Keeper independence attestation (annual)
- **Keeper health alerting** - alert when quorum drops to 3 (SR-7)
- **365-day rolling override threshold** - cumulative limit prevents slow erosion (RT-3)

**Runbook Requirement:** Epic 5 runbook: "Keeper Operations & Key Rotation"

**Cross-Epic Requirements:**
- FR26 (overrides cannot suppress witnessing) - Epic 1 enforces, Epic 5 invokes (PM-4)

**Mandatory Integration Test:**
- "Attempt to suppress witness → rejected" must pass (PM-4)

**Red Team Hardening (RT-3):**
- Existing: >50% increase OR >5 in 30 days triggers alert
- Added: >20 overrides in any 365-day rolling window triggers governance review
- Prevents "just under threshold" slow erosion attack

**First Principles (FP-3):**
- CT-9: Attackers are patient - aggregate erosion must be detected
- Links to ADR-7 (Aggregate Anomaly Detection) for statistical analysis
- Override patterns analyzed for coordinated slow-burn attacks
- Keeper behavior correlation across long time windows

**ADR Implementation:** ADR-4 (Key Custody + Keeper Adversarial Defense), ADR-5 (Watchdog Independence), ADR-7 (Aggregate Anomaly Detection)

---

### Epic 6: Breach & Threshold Enforcement
**User Outcome:** Constitutional violations are detected, escalated, and recorded as scars. Thresholds cannot be silently lowered.

**FRs covered:** FR30-FR36, FR59-FR61, FR116-FR121, FR124-FR128

**Delivers:**
- Breach declarations create constitutional events
- 7-day escalation to Conclave agenda if unacknowledged
- Automatic cessation consideration at >10 unacknowledged breaches in 90 days
- Constitutional threshold definitions (not operational)
- Counter protection (threshold changes don't reset counters)
- Alerts evaluated against definition when condition began
- Configuration floors (no thresholds below constitutional minima)
- Witness selection with verifiable randomness
- Witness pair rotation (no consecutive pairs in 24 hours)
- Statistical anomaly flagging in witness co-occurrence
- Witness pool minimum (12 for high-stakes, degraded mode surfaced)
- External entropy source for witness selection
- Amendment visibility (14 days before vote)
- Impact analysis for core guarantee amendments
- Amendment history protection (can't make amendments unreviewable)

**ADR Implementation:** ADR-6 (Amendment, Ceremony, Convention Tier), ADR-7 (Aggregate Anomaly Detection)

---

### Epic 7: Cessation Protocol
**User Outcome:** System can stop when integrity requires it, with cessation as the final recorded event. Irreversible by schema.

**FRs covered:** FR37-FR43, FR134-FR135, FR144

**NFRs owned:** NFR40 (no cessation reversal in schema)

**Delivers:**
- Automatic agenda placement at 3 consecutive integrity failures in 30 days
- **Alternative trigger: 5 integrity failures in any 90-day rolling window** (RT-4)
- Automatic agenda placement at anti-success alert sustained 90 days
- External observer petitions with 100+ co-signers trigger agenda placement
- No "cessation_reversal" event type in schema (irreversibility)
- Freeze new actions except record preservation
- Read-only access indefinitely after cessation
- Cessation as final recorded event (not silent disappearance)
- Public documentation of cessation trigger conditions
- Final deliberation recording before cessation
- Integrity Case Artifact (guarantees, mechanisms, invalidation conditions)

**Mandatory Chaos Test (PM-5):**
- Cessation must be triggered and verified in staging before Epic complete
- Weekly CI job simulates cessation trigger (does not execute, validates path)

**Legal Review Checkpoint (SR-8):**
- Legal review of cessation irreversibility before Epic 7 marked complete
- Document liability implications of "no reversal" design

**Red Team Hardening (RT-4):**
- Original: 3 consecutive failures in 30 days (exploitable via timing)
- Added: 5 non-consecutive failures in 90-day rolling window
- Prevents "wait and reset" timing game attacks

**Definition of Done:**
- Cessation has been triggered end-to-end in staging environment
- Read-only mode verified after cessation
- Cessation event is final recorded event (no writes after)
- Legal review completed and documented

**Runbook Requirement:** Epic 7 runbook: "Cessation Procedures & Post-Cessation Access"

**ADR Implementation:** ADR-12 (Crisis Response)

---

### Epic 8: Operational Monitoring & Health
**User Outcome:** Operators can monitor system health without compromising constitutional metrics. Operational ≠ Constitutional.

**FRs covered:** FR51-FR54, FR105-FR107, FR145-FR147

**NFRs owned:** NFR27-30 (observability), NFR35-38 (operational)

**Delivers:**
- Uptime, latency, error rate monitoring
- Operational metrics EXCLUDED from constitutional event store
- Operational metrics NOT used for constitutional integrity assessment
- System unavailability independently detectable by external parties
- Incident reports for halt, fork, or >3 overrides/day
- Pre-operational verification checklist on startup
- Incident report transparency (public within 7 days)
- **Complexity budget dashboard** (SC-3: CT-14 traceability)
  - ADR count tracking (limit: ≤15)
  - Ceremony type count (limit: ≤10)
  - Cross-component dependency count (limit: ≤20)
  - Alert when any complexity budget exceeded
- **Complexity budget enforcement** - breach creates constitutional event (RT-6)

**Red Team Hardening (RT-6):**
- Complexity budget breach = constitutional event (not just alert)
- Exceeding limits requires governance ceremony to proceed
- Automatic escalation if limits exceeded without ceremony approval
- Prevents "monitor but ignore" pattern

**ADR Implementation:** ADR-10 (Constitutional Health + Operational Governance)

---

### Epic 9: Emergence Governance & Public Materials
**User Outcome:** System never claims emergence or collective consciousness. Public materials are audited for prohibited language.

**FRs covered:** FR55-FR58, FR108-FR110

**NFRs owned:** NFR31-34 (compliance)

**Delivers:**
- System outputs never claim emergence
- Automated keyword scanning on all publications
- Quarterly audit of all public materials
- Curated/featured user content subject to same prohibition
- Audit results logged as events
- Violations are constitutional breaches requiring Conclave response

**CT-15 Waiver Documentation (SC-4, SR-10):**
- "Legitimacy requires consent" is addressed in Seeker journey (Phase 2, not MVP)
- Epic 9 scope is narrow: emergence language prohibition only
- **Waiver rationale:** MVP focuses on constitutional infrastructure; consent mechanisms require Seeker-facing features (Phase 2)
- **Acceptance criteria:** Document waiver in architecture decisions before Epic 9 complete

**Runbook Requirement:** Epic 9 runbook: "Emergence Audit Procedures"

**ADR Implementation:** ADR-11 (Complexity Governance)

---

## Pre-mortem Findings Applied

| ID | Failure Mode | Prevention | Epic Impact |
|----|--------------|------------|-------------|
| PM-1 | Epic 0 scope creep | Time-box 2 weeks, explicit DoD | Epic 0 |
| PM-2 | Epic 1/3 deadlock | Halt stub in Epic 1, prerequisite in Epic 3 | Epic 1, Epic 3 |
| PM-3 | Observer retrofit pain | Observer schema spike in Epic 1 | Epic 1, Epic 4 |
| PM-4 | Cross-epic FR ownership | FR26 tracked across Epic 1+5, integration test | Epic 1, Epic 5 |
| PM-5 | Cessation never tested | Mandatory chaos test in staging, weekly CI | Epic 7 |
| PM-6 | NFRs orphaned | NFRs explicitly assigned to owning epics | All epics |

---

## Self-Consistency Findings Applied

| ID | Finding | Resolution |
|----|---------|------------|
| SC-1 | FR80-81 double assignment | Epic 0 owns, Epic 1 "Uses from Epic 0" |
| SC-2 | FR86-89 split unclear | FR86-87 → Epic 5, FR88-89 → Epic 4 (see coverage map) |
| SC-3 | Epic 8 missing complexity budget | Added complexity budget dashboard |
| SC-4 | Epic 9 missing consent | CT-15 deferred to Phase 2 (Seeker journey) |

---

## Stakeholder Round Table Findings Applied

| ID | Finding | Stakeholder | Resolution |
|----|---------|-------------|------------|
| SR-1 | Testing framework missing | Dev | Integration test framework added to Epic 0 |
| SR-2 | Runbook requirement missing | Ops | Runbook requirement added to all epics |
| SR-3 | Supabase trigger spike needed | Dev | Spike story added to Epic 1 |
| SR-4 | 72-agent load test needed | Dev | Performance spike added to Epic 2 |
| SR-5 | Halt channel conflict resolution | Dev | Added to Epic 3 deliverables |
| SR-6 | Infrastructure provisioning undefined | Ops | Deferred to deployment phase (noted in Epic 3) |
| SR-7 | Keeper health alerting | Ops | Added to Epic 5 deliverables |
| SR-8 | Legal review for cessation | Governance | Checkpoint added to Epic 7 |
| SR-9 | Observer push notifications | Governance | Added to Epic 4 deliverables |
| SR-10 | CT-15 waiver documentation | Governance | Waiver documented in Epic 9 |

---

## Red Team vs Blue Team Findings Applied

| ID | Attack | Gap | Epic | Hardening |
|----|--------|-----|------|-----------|
| RT-1 | Silent Witness | No atomicity guarantee | Epic 1 | Event + witness atomic transaction |
| RT-2 | Phantom Halt | Halt not logged before effect | Epic 3 | Witnessed halt event before stop |
| RT-3 | Keeper Cabal | No yearly cumulative threshold | Epic 5 | 365-day rolling threshold (>20/year) |
| RT-4 | Cessation Stall | Timing game resets counter | Epic 7 | 90-day rolling window alternative |
| RT-5 | Observer Blackout | No uptime SLA or fallback | Epic 4 | 99.9% SLA + checkpoint fallback |
| RT-6 | Complexity Bomb | Monitor without enforce | Epic 8 | Breach = constitutional event |

---

## First Principles Findings Applied

| ID | Finding | CT | Epic | Resolution |
|----|---------|-----|------|------------|
| FP-1 | Stateless agent support not explicit | CT-1 | Epic 1 | Event store enables agent state reconstruction |
| FP-2 | Compound failures not analyzed | CT-8 | Epic 3 | Cascading failure analysis added |
| FP-3 | Patient attacker detection needs ADR-7 | CT-9 | Epic 5 | Linked to ADR-7 Aggregate Anomaly Detection |

**Constitutional Truth Coverage:** All 15 CTs traced to epics. 3 gaps closed.

---

## FR Coverage Map

| FR Range | Epic | Coverage |
|----------|------|----------|
| FR1-FR8 | Epic 1 | Event Store & Witnessing |
| FR9-FR15 | Epic 2 | Agent Deliberation |
| FR16-FR22 | Epic 3 | Fork Detection |
| FR23-FR29 | Epic 5 | Override & Keeper |
| FR30-FR36 | Epic 6 | Breach & Threshold |
| FR37-FR43 | Epic 7 | Cessation Protocol |
| FR44-FR50 | Epic 4 | Observer Interface |
| FR51-FR54 | Epic 8 | Operational Monitoring |
| FR55-FR58 | Epic 9 | Emergence Governance |
| FR59-FR61 | Epic 6 | Witness Collusion Defense |
| FR62-FR67 | Epic 1, 4 | Hash Verification, Event Ordering |
| FR68-FR70 | Epic 5 | Keeper Impersonation Prevention |
| FR71-FR73 | Epic 2 | Topic Manipulation Defense |
| FR74-FR76 | Epic 1 | Schema Evolution |
| FR77-FR79 | Epic 5 | Recovery Deadlock Prevention |
| FR80-FR85 | Epic 0, 1 | State Mutation & Identity Primitives |
| FR86-FR87 | Epic 5 | REFUSE_OVERRIDE Control Primitives |
| FR88-FR89 | Epic 4 | QUERY_AS_OF Query Primitives |
| FR90-FR93 | Epic 2 | Liveness Primitives |
| FR94-FR95 | Epic 1 | Propagation Primitives |
| FR96-FR98 | Epic 5 | Key Lifecycle Management |
| FR99-FR101 | Epic 2 | Deliberation Quality |
| FR102-FR104 | Epic 1 | Disaster Recovery |
| FR105-FR107 | Epic 8 | Scale Realism |
| FR108-FR110 | Epic 7 | Privacy & Regulatory |
| FR111-FR113 | Epic 3 | Partition Handling |
| FR114-FR115 | Epic 3 | Halt Flooding Defense |
| FR116-FR121 | Epic 6 | Witness & Heartbeat Defense |
| FR122-FR123 | Epic 4 | Observer Poisoning Defense |
| FR124-FR128 | Epic 6 | Seed & Amendment Defense |
| FR129-FR130 | Epic 4 | Selective Suppression Defense |
| FR131-FR133 | Epic 5 | Keeper Collusion Defense |
| FR134-FR135 | Epic 7 | Cessation Gaming Defense |
| FR136-FR140 | Epic 4 | Blockchain & Audit Capabilities |
| FR141-FR142 | Epic 2 | Governance Capabilities |
| FR143 | Epic 3 | Operational Rollback |
| FR144 | Epic 7 | Safety Case |
| FR145-FR147 | Epic 8 | Mission-Critical Capabilities |

---

## Stories by Epic

---

## Epic 0: Project Foundation & Constitutional Infrastructure

**Goal:** Development team can build constitutional features on a validated hexagonal architecture foundation with dev environment ready.

**Time-box:** 2 weeks maximum

---

### Story 0.1: Project Scaffold & Dependencies

As a **developer**,
I want a properly configured Python 3.11+ project with all required dependencies,
So that I can build constitutional features on a solid foundation.

**Acceptance Criteria:**

**Given** a fresh development environment
**When** I clone the repository and run `poetry install`
**Then** all dependencies are installed:
  - FastAPI 0.100+
  - CrewAI (latest)
  - supabase-py
  - redis-py
  - SQLAlchemy 2.0+ (async mode)
  - Pydantic v2
  - structlog
  - cryptography
  - hypothesis (testing)
**And** Python 3.11+ is required as specified in pyproject.toml
**And** `poetry run python --version` confirms 3.11+

**Given** a fresh clone
**When** I run `poetry install && poetry run pytest tests/unit/test_smoke.py`
**Then** the smoke test passes confirming dependencies are correctly installed

---

### Story 0.2: Hexagonal Architecture Layers

As a **developer**,
I want a hexagonal architecture scaffold with clear layer boundaries,
So that I can place code in the correct layer without confusion.

**Acceptance Criteria:**

**Given** the project structure
**When** I examine the `src/` directory
**Then** it contains these subdirectories:
  - `src/domain/` (pure business logic, no infrastructure imports)
  - `src/application/` (use cases, ports, orchestration)
  - `src/infrastructure/` (adapters: Supabase, Redis, HSM)
  - `src/api/` (FastAPI routes, DTOs)
**And** each directory contains an `__init__.py` file
**And** each directory contains a `README.md` explaining its purpose

**Given** the domain layer
**When** I examine `src/domain/`
**Then** it contains subdirectories for:
  - `events/` (constitutional event types)
  - `entities/` (domain entities)
  - `value_objects/` (immutable value types)
  - `ports/` (abstract interfaces)
**And** no file in domain imports from infrastructure or api

---

### Story 0.3: Dev Environment & Makefile

As a **developer**,
I want a `make dev` command that starts the local development environment,
So that I can begin development with one command.

**Acceptance Criteria:**

**Given** Docker and Docker Compose are installed
**When** I run `make dev`
**Then** the following services start:
  - Local Supabase (PostgreSQL + PostgREST)
  - Redis
  - FastAPI app with hot-reload
**And** the API is accessible at `http://localhost:8000`
**And** health endpoint returns 200 OK

**Given** the dev environment is running
**When** I run `make stop`
**Then** all containers are stopped gracefully

**Given** I want to reset the database
**When** I run `make db-reset`
**Then** all tables are dropped and migrations re-applied

---

### Story 0.4: Software HSM Stub with Watermark

As a **developer**,
I want a software HSM stub for local development,
So that I can sign events without production HSM while clearly marking dev signatures.

**Acceptance Criteria:**

**Given** the application is running in dev mode (DEV_MODE=true)
**When** I request a signature from the HSM service
**Then** the signature is created using software cryptography
**And** the signed content includes `[DEV MODE]` prefix INSIDE the signature (RT-1 pattern)

**Given** a dev mode signature
**When** I examine the signature metadata
**Then** it contains `mode: "development"`
**And** the watermark cannot be stripped without invalidating the signature

**Given** production mode (DEV_MODE=false)
**When** I request a signature without HSM configured
**Then** the system fails with clear error "Production HSM not configured"
**And** no signature is produced

**Given** the HSM stub
**When** I generate a key pair
**Then** the keys are stored in local file (not secure, dev only)
**And** a warning is logged: "Using software HSM - NOT FOR PRODUCTION"

---

### Story 0.5: Integration Test Framework

As a **developer**,
I want an integration test framework with containerized dependencies,
So that I can run integration tests locally with real Supabase and Redis.

**Acceptance Criteria:**

**Given** Docker is running
**When** I run `make test-integration`
**Then** testcontainers starts:
  - PostgreSQL container (Supabase-compatible)
  - Redis container
**And** integration tests run against these containers
**And** containers are cleaned up after tests complete

**Given** an integration test file in `tests/integration/`
**When** I use the `@pytest.fixture` for `db_session`
**Then** I get a real database connection to the test container
**And** the database is reset between tests

**Given** the test framework
**When** I run a single integration test with `pytest tests/integration/test_example.py -v`
**Then** only that test runs with full container setup
**And** execution time is under 30 seconds for container startup

---

### Story 0.6: Import Boundary Enforcement

As a **developer**,
I want pre-commit hooks that reject cross-layer imports,
So that architectural boundaries are enforced automatically.

**Acceptance Criteria:**

**Given** a pre-commit configuration
**When** I run `pre-commit install`
**Then** hooks are installed for:
  - Import boundary checking
  - Python formatting (black)
  - Linting (ruff)
  - Type checking (mypy)

**Given** a file in `src/domain/` that imports from `src/infrastructure/`
**When** I attempt to commit
**Then** the commit is rejected
**And** error message explains: "Domain layer cannot import from infrastructure"

**Given** a file in `src/application/` that imports from `src/domain/`
**When** I attempt to commit
**Then** the commit succeeds (allowed import direction)

**Given** the import boundary rules
**When** I run `scripts/check_imports.py`
**Then** it scans all Python files
**And** reports any violations with file:line references
**And** exits with code 1 if violations found

---

### Story 0.7: Constitutional Primitives (FR80, FR81)

As a **developer**,
I want constitutional primitives PREVENT_DELETE and ENSURE_ATOMICITY,
So that I can build features on a foundation that prevents deletion and ensures atomic operations.

**Acceptance Criteria:**

**Given** the domain layer
**When** I examine `src/domain/primitives/`
**Then** it contains:
  - `prevent_delete.py` with DeletePreventionMixin
  - `ensure_atomicity.py` with AtomicOperationContext

**Given** a model using DeletePreventionMixin
**When** I attempt to call `.delete()` on an instance
**Then** a `ConstitutionalViolationError` is raised
**And** the error message includes "FR80: Deletion prohibited"

**Given** an AtomicOperationContext
**When** an exception occurs within the context
**Then** all changes are rolled back
**And** no partial state is persisted
**And** the exception is re-raised after rollback

**Given** I want to test these primitives
**When** I run `pytest tests/unit/test_constitutional_primitives.py`
**Then** all primitive tests pass without infrastructure dependencies

---

## Epic 0 Complete

**Stories:** 7
**FRs covered:** FR80, FR81
**Runbook:** "Developer Environment Setup"
**DoD:** `make dev` works, domain test passes, HSM stub signs, pre-commit rejects violations

---

## Epic 1: Witnessed Event Store

**Goal:** External observers can verify that events are append-only, hash-chained, and witnessed with cryptographic signatures.

**FRs covered:** FR1-FR8, FR62-FR67, FR74-FR76, FR82-FR85, FR94-FR95, FR102-FR104

**Uses from Epic 0:** FR80, FR81 (PREVENT_DELETE, ENSURE_ATOMICITY primitives)

**NFRs owned:** NFR1 (<100ms write), NFR12 (3 replicas), NFR15 (append-only), NFR19 (SHA-256)

---

### Story 1.1: Event Store Schema & Append-Only Enforcement (FR1, FR102-FR104)

As an **external observer**,
I want events stored in an append-only table with DB-level enforcement,
So that no one can delete or modify historical events.

**Acceptance Criteria:**

**Given** the Supabase database
**When** I apply the event store migration
**Then** an `events` table is created with columns:
  - `event_id` (UUID, primary key)
  - `sequence` (BIGSERIAL, unique, indexed)
  - `event_type` (TEXT, not null)
  - `payload` (JSONB, not null)
  - `prev_hash` (TEXT, not null)
  - `content_hash` (TEXT, not null)
  - `signature` (TEXT, not null)
  - `hash_alg_version` (SMALLINT, default 1)
  - `sig_alg_version` (SMALLINT, default 1)
  - `agent_id` (TEXT, nullable)
  - `witness_id` (TEXT, not null)
  - `witness_signature` (TEXT, not null)
  - `local_timestamp` (TIMESTAMPTZ, not null)
  - `authority_timestamp` (TIMESTAMPTZ, default now())

**Given** the events table
**When** I attempt an UPDATE statement on any row
**Then** the statement is rejected by a trigger
**And** error message includes "FR102: Append-only violation - UPDATE prohibited"

**Given** the events table
**When** I attempt a DELETE statement on any row
**Then** the statement is rejected by a trigger
**And** error message includes "FR102: Append-only violation - DELETE prohibited"

**Given** the events table
**When** I attempt a TRUNCATE statement
**Then** the statement is rejected
**And** error message includes "FR102: Append-only violation - TRUNCATE prohibited"

**Given** the PREVENT_DELETE primitive from Epic 0
**When** the domain model attempts `.delete()` on an event
**Then** a `ConstitutionalViolationError` is raised before reaching the database

---

### Story 1.2: Hash Chain Implementation (FR2, FR82-FR85)

As an **external observer**,
I want events hash-chained with SHA-256 and DB-level verification,
So that any tampering breaks the chain and is detectable.

**Acceptance Criteria:**

**Given** a new event to be written
**When** the event is inserted
**Then** a DB trigger computes `content_hash` as SHA-256 of canonical JSON payload
**And** the trigger verifies `prev_hash` matches the current head's `content_hash`
**And** the trigger rejects if `prev_hash` is incorrect

**Given** an event with sequence N
**When** I query events with sequence N-1
**Then** the `content_hash` of N-1 equals the `prev_hash` of N

**Given** the genesis event (sequence 1)
**When** I examine its `prev_hash`
**Then** it contains a well-known genesis constant: "ARCHON72_GENESIS_2025"

**Given** an event is inserted
**When** I examine the `hash_alg_version` field
**Then** it is set to 1 (representing SHA-256)

**Given** an attempt to insert with mismatched `prev_hash`
**When** the DB trigger evaluates
**Then** the insert is rejected
**And** error message includes "FR82: Hash chain continuity violation"

**Given** the verification function `verify_chain(start_seq, end_seq)`
**When** I run it on the events table
**Then** it returns TRUE if all hashes chain correctly
**And** returns FALSE with details if any break is found

---

### Story 1.3: Agent Attribution & Signing (FR3, FR74-FR76)

As an **external observer**,
I want each event signed by the responsible agent with cryptographic proof,
So that I can verify who authored each event.

**Acceptance Criteria:**

**Given** an agent creates an event
**When** the event is prepared for writing
**Then** the `agent_id` is set to the agent's registered identifier
**And** the `signature` is computed over (`content_hash` + `prev_hash` + `agent_id`)
**And** `sig_alg_version` is set to 1 (representing Ed25519)

**Given** a signed event
**When** I retrieve the agent's public key from the key registry
**Then** I can verify the signature against the signed content
**And** invalid signatures are detectable

**Given** an event is submitted without a valid signature
**When** the DB trigger evaluates
**Then** the insert is rejected
**And** error message includes "FR74: Invalid agent signature"

**Given** the key registry
**When** I examine it
**Then** it contains `agent_id`, `public_key`, `active_from`, `active_until`
**And** historical keys are preserved for verifying old events

**Given** a system agent (e.g., watchdog, scheduler)
**When** it creates an event
**Then** `agent_id` is set to the system agent identifier (e.g., "SYSTEM:WATCHDOG")
**And** the event is signed with the system agent's key

---

### Story 1.4: Witness Attribution - Atomic (FR4-FR5, RT-1)

As an **external observer**,
I want every event witnessed atomically with the event creation,
So that no unwitnessed events exist (RT-1 hardening).

**Acceptance Criteria:**

**Given** an event is submitted for writing
**When** the write operation begins
**Then** a witness is selected from the available witness pool
**And** the witness signs the event content
**And** both event and witness signature are written in a single atomic transaction

**Given** the witness pool check
**When** no witnesses are available
**Then** the write operation is rejected BEFORE attempting the insert
**And** error includes "RT-1: No witnesses available - write blocked"

**Given** a witness is available but fails to sign
**When** the atomic transaction is attempted
**Then** the entire transaction is rolled back
**And** no event is persisted
**And** the failure is logged with witness_id

**Given** a successfully written event
**When** I examine the record
**Then** `witness_id` is not null
**And** `witness_signature` is not null
**And** the witness signature can be verified against the witness's public key

**Given** the ENSURE_ATOMICITY primitive from Epic 0
**When** an exception occurs during the write-with-witness transaction
**Then** all changes are rolled back atomically
**And** no partial state exists

---

### Story 1.5: Dual Time Authority & Sequence Numbers (FR6-FR7)

As an **external observer**,
I want events to have dual timestamps and sequence numbers,
So that I can order events deterministically regardless of clock drift.

**Acceptance Criteria:**

**Given** an event is created
**When** it is inserted
**Then** `local_timestamp` is set by the writer service to its local clock
**And** `authority_timestamp` is set by the DB to `now()`
**And** `sequence` is assigned by a BIGSERIAL (monotonically increasing)

**Given** the sequence column
**When** two events are inserted concurrently
**Then** each receives a unique, sequential number
**And** no gaps exist in the sequence (except documented ceremonies)

**Given** an external observer
**When** they need to order events
**Then** they use `sequence` as the authoritative order
**And** timestamps are for informational/debugging purposes only

**Given** a scenario where local_timestamp and authority_timestamp differ significantly (>5 seconds)
**When** the event is inserted
**Then** a warning is logged for clock drift investigation
**And** the event is still accepted (sequence is authoritative)

---

### Story 1.6: Event Writer Service (ADR-1)

As a **system operator**,
I want a single canonical Writer service that submits events through DB enforcement,
So that the trust boundary is narrowed to the database.

**Acceptance Criteria:**

**Given** the Writer service
**When** I examine its architecture
**Then** it submits events but does NOT compute hashes locally
**And** hash computation is delegated to DB triggers
**And** signature verification is delegated to DB triggers

**Given** the Writer service submits an event
**When** the DB accepts the event
**Then** the Writer logs success with event_id and sequence
**And** returns the assigned sequence to the caller

**Given** the Writer service submits an invalid event
**When** the DB rejects it
**Then** the Writer logs the rejection reason
**And** raises an appropriate exception to the caller
**And** no partial state exists

**Given** the single-writer constraint (ADR-1)
**When** I examine the deployment
**Then** only one Writer service instance is active
**And** failover requires a witnessed ceremony (not automatic)

**Given** Writer self-verification (CH-1)
**When** the Writer starts
**Then** it verifies its view of head hash matches DB
**And** if mismatch, it halts immediately
**And** halts are logged with both hash values

---

### Story 1.7: Supabase Trigger Spike (SR-3)

As a **developer**,
I want to validate DB-level hash enforcement in Supabase,
So that we confirm the approach before full implementation.

**Acceptance Criteria:**

**Given** a spike branch
**When** I implement a minimal hash verification trigger
**Then** the trigger computes SHA-256 in PL/pgSQL
**And** the trigger verifies prev_hash on insert
**And** the trigger rejects invalid inserts

**Given** the spike results
**When** I document findings
**Then** I record: performance (latency impact)
**And** I record: edge cases discovered
**And** I record: Supabase-specific limitations (if any)
**And** I record: recommended approach for production

**Given** the spike
**When** performance is measured
**Then** hash verification adds <10ms to insert latency
**And** if >10ms, alternatives are documented

**Given** the spike conclusion
**When** reviewed
**Then** a go/no-go decision is recorded for DB-level enforcement
**And** if no-go, alternative enforcement approach is proposed

---

### Story 1.8: Halt Check Interface Stub (PM-2)

As a **developer**,
I want a halt check interface that Epic 3 will implement,
So that Epic 1 can check halt state without creating a dependency.

**Acceptance Criteria:**

**Given** the application layer
**When** I examine `src/application/ports/halt_checker.py`
**Then** it defines an abstract `HaltChecker` interface with:
  - `is_halted() -> bool`
  - `get_halt_reason() -> Optional[str]`

**Given** the stub implementation
**When** I examine `src/infrastructure/stubs/halt_checker_stub.py`
**Then** `is_halted()` returns `False` (system not halted)
**And** `get_halt_reason()` returns `None`
**And** a TODO comment references Epic 3 for real implementation

**Given** dependency injection
**When** the Writer service is instantiated
**Then** it receives a `HaltChecker` instance
**And** before each write, it calls `is_halted()`
**And** if halted, the write is rejected with "System is halted"

**Given** the contract
**When** Epic 3 implements the real `HaltChecker`
**Then** it satisfies the same interface
**And** no changes to Epic 1 code are required

---

### Story 1.9: Observer Query Schema Design Spike (PM-3)

As a **developer**,
I want to design the schema with Epic 4 observer queries in mind,
So that efficient querying is possible without schema changes later.

**Acceptance Criteria:**

**Given** a spike analysis
**When** I examine Epic 4 requirements
**Then** I identify: date range queries, event type filtering, sequence range queries

**Given** the events table
**When** I design indexes
**Then** I propose: index on `authority_timestamp`
**And** I propose: index on `event_type`
**And** I propose: composite index for common query patterns

**Given** the spike results
**When** documented
**Then** I record: proposed indexes with rationale
**And** I record: estimated query performance
**And** I record: any schema additions needed for observer efficiency

**Given** the spike
**When** reviewed with Epic 4 acceptance criteria
**Then** the schema supports all observer query patterns
**And** no major refactoring will be needed

---

### Story 1.10: Replica Configuration Preparation (FR8, FR94-FR95)

As a **system operator**,
I want the schema ready for 3 geographic replicas,
So that replica distribution can be enabled in deployment.

**Acceptance Criteria:**

**Given** the events table schema
**When** I examine it
**Then** it contains no features that prevent logical replication
**And** primary key and sequence are suitable for replica synchronization

**Given** the application architecture
**When** I examine read vs write paths
**Then** writes go to the primary (single writer)
**And** reads can be routed to replicas (eventual consistency acceptable for reads)

**Given** the event propagation interface
**When** I examine `src/application/ports/event_replicator.py`
**Then** it defines: `propagate_event(event_id) -> ReplicationReceipt`
**And** `ReplicationReceipt` includes confirmed replica count

**Given** the stub implementation
**When** I examine it
**Then** it returns a receipt with `replica_count=1` (single instance for dev)
**And** a TODO references deployment phase for actual replication

**Given** the replica verification job interface
**When** I examine it
**Then** it defines: `verify_replicas() -> VerificationResult`
**And** verification checks: head hash match, signature validity, schema version

---

## Epic 1 Complete

**Stories:** 10
**FRs covered:** FR1-FR8, FR62-FR67, FR74-FR76, FR82-FR85, FR94-FR95, FR102-FR104
**NFRs owned:** NFR1, NFR12, NFR15, NFR19
**Runbook:** "Event Store Operations & Recovery"
**ADR Implementation:** ADR-1 (Event Store Topology)
**DoD:** Events append-only with DB enforcement, hash chain verified, all events witnessed atomically, spikes documented

---

## Epic 2: Agent Deliberation & Collective Output

**Goal:** 72 agents can deliberate and produce collective outputs that are recorded before any human sees them (No Preview constraint).

**FRs covered:** FR9-FR15, FR71-FR73, FR82-FR83, FR90-FR93, FR99-FR101, FR141-FR142

**ADR Implementation:** ADR-2 (Context Reconstruction + Signature Trust)

---

### Story 2.1: No Preview Constraint (FR9)

As an **external observer**,
I want agent outputs recorded before any human sees them,
So that I can verify no unauthorized preview or modification occurred.

**Acceptance Criteria:**

**Given** an agent produces a deliberation output
**When** the output is generated
**Then** it is immediately committed to the event store with a content hash
**And** a `DeliberationOutputEvent` is created with timestamp

**Given** a human requests to view a deliberation output
**When** they access the output
**Then** the output hash in the event store matches the displayed content
**And** the view event is logged with viewer identity

**Given** an output that hasn't been committed to the event store
**When** a human attempts to view it
**Then** access is denied
**And** error message includes "FR9: Output must be recorded before viewing"

**Given** the No Preview enforcement
**When** I examine the code path
**Then** there is no code path where output can be viewed before store commit
**And** atomic commit-then-serve is enforced

---

### Story 2.2: 72 Concurrent Agent Deliberations (FR10)

As a **system operator**,
I want 72 agents to deliberate concurrently without performance degradation,
So that the full Conclave can operate simultaneously.

**Acceptance Criteria:**

**Given** the CrewAI orchestrator
**When** I examine its configuration
**Then** it supports 72 concurrent agent instances
**And** each instance has isolated context

**Given** a deliberation request
**When** 72 agents are invoked concurrently
**Then** all complete within acceptable time bounds (NFR5)
**And** no agent blocks another's execution

**Given** the agent pool
**When** agents complete deliberation
**Then** resources are released for reuse
**And** memory usage stays within bounds

**Given** the 72-agent load test spike (SR-4)
**When** executed
**Then** CrewAI scales to 72 concurrent agents
**And** results are documented (latency, memory, failures)

---

### Story 2.3: Collective Output Irreducibility (FR11)

As an **external observer**,
I want collective outputs attributed to the Conclave, not individual agents,
So that no single agent can claim sole authorship.

**Acceptance Criteria:**

**Given** a collective deliberation output
**When** it is recorded
**Then** `author_type` is set to "COLLECTIVE"
**And** `contributing_agents` lists all participant agent IDs
**And** no single agent is identified as sole author

**Given** a collective output event
**When** I examine its structure
**Then** it includes: vote counts, dissent percentage, unanimous flag
**And** individual vote details are in separate linked events

**Given** an attempt to create a "collective" output with only one agent
**When** the system validates
**Then** the output is rejected
**And** error includes "FR11: Collective output requires multiple participants"

---

### Story 2.4: Dissent Tracking in Vote Tallies (FR12)

As an **external observer**,
I want dissent percentages visible in every vote tally,
So that I can detect healthy disagreement vs groupthink.

**Acceptance Criteria:**

**Given** a vote is tallied
**When** the result is recorded
**Then** the event includes: `yes_count`, `no_count`, `abstain_count`
**And** `dissent_percentage` is calculated as (minority votes / total votes) × 100

**Given** a unanimous vote (100% agreement)
**When** the result is recorded
**Then** `dissent_percentage` is 0
**And** `unanimous` flag is TRUE
**And** a `UnanimousVoteEvent` is created (separate from standard vote)

**Given** the dissent health metrics (PM finding)
**When** I query dissent trends
**Then** rolling averages are available
**And** alerts fire if dissent drops below 10% over 30 days

---

### Story 2.5: No Silent Edits (FR13)

As an **external observer**,
I want the published hash to always equal the canonical hash,
So that no one can edit content after recording.

**Acceptance Criteria:**

**Given** content is published to external systems
**When** I compare published hash to event store hash
**Then** they are identical

**Given** an attempt to publish content that differs from recorded content
**When** the publish operation executes
**Then** the hash mismatch is detected
**And** publish is blocked
**And** error includes "FR13: Silent edit detected - hash mismatch"

**Given** the verification endpoint
**When** I call `verify_content(content_id)`
**Then** it returns TRUE if hashes match, FALSE otherwise
**And** hash values are included in response

---

### Story 2.6: Agent Heartbeat Monitoring (FR14, FR90-FR93)

As a **system operator**,
I want agents to emit heartbeats during deliberation,
So that I can detect stalled or crashed agents.

**Acceptance Criteria:**

**Given** an agent is actively deliberating
**When** it is healthy
**Then** it emits a heartbeat every 30 seconds
**And** heartbeat includes: `agent_id`, `session_id`, `status`, `memory_usage`

**Given** an agent misses 3 consecutive heartbeats (90 seconds)
**When** the watchdog detects this
**Then** an `AgentUnresponsiveEvent` is created
**And** the agent is flagged for recovery

**Given** a missing heartbeat
**When** logged
**Then** it includes last known state and timestamp
**And** failure detection time is recorded

**Given** agent heartbeat spoofing defense (FR90)
**When** a heartbeat is received
**Then** it is verified against agent's session token
**And** spoofed heartbeats are rejected and logged

---

### Story 2.7: Topic Origin Tracking (FR15, FR71-FR73)

As an **external observer**,
I want topic origins tracked (autonomous, petition, scheduled),
So that I can verify topic diversity and detect manipulation.

**Acceptance Criteria:**

**Given** a new topic is introduced
**When** it is recorded
**Then** `origin_type` is one of: AUTONOMOUS, PETITION, SCHEDULED
**And** origin metadata is included (petition_id, schedule_ref, etc.)

**Given** topic diversity enforcement (no >30% from single source)
**When** topics are analyzed over a rolling 30-day window
**Then** no single origin type exceeds 30% of total topics
**And** if threshold is exceeded, alert is raised

**Given** topic flooding defense (FR71-FR73)
**When** rapid topic submission is detected (>10 per hour from same source)
**Then** rate limiting is applied
**And** excess topics are queued, not rejected
**And** `TopicRateLimitEvent` is created

---

### Story 2.8: Result Certification (FR99-FR101, FR141-FR142)

As an **external observer**,
I want deliberation results to have certified result events,
So that I can verify the result is official.

**Acceptance Criteria:**

**Given** a deliberation concludes
**When** the result is final
**Then** a `CertifiedResultEvent` is created
**And** it is signed by the system's certification key
**And** it includes: result_hash, participant_count, certification_timestamp

**Given** a certified result
**When** I query it
**Then** the certification signature can be verified
**And** the result content matches the result_hash

**Given** procedural record generation
**When** a deliberation completes
**Then** a procedural record is generated
**And** it includes: agenda, participants, votes, timeline, decisions
**And** the record is signed and stored

---

### Story 2.9: Context Bundle Creation (ADR-2)

As an **agent**,
I want my context bundle created correctly before deliberation,
So that I have the information needed to participate.

**Acceptance Criteria:**

**Given** an agent is invoked for deliberation
**When** the context bundle is prepared
**Then** it includes: `schema_version`, `bundle_id`, `meeting_id`
**And** `as_of_event_seq` anchors the bundle to a specific event
**And** `identity_prompt_ref`, `meeting_state_ref`, `precedent_refs[]` are included

**Given** a context bundle
**When** it is created
**Then** it is signed with the bundle creator's key
**And** `bundle_hash` is computed over canonical JSON
**And** bundle passes JSON Schema validation

**Given** an agent receives a context bundle
**When** it validates the bundle
**Then** signature is verified before parsing
**And** invalid bundles are rejected with "ADR-2: Invalid context bundle signature"

---

### Story 2.10: CrewAI 72-Agent Load Test Spike (SR-4)

As a **developer**,
I want to validate CrewAI can handle 72 concurrent agents,
So that we confirm the approach before full implementation.

**Acceptance Criteria:**

**Given** a spike branch
**When** I implement a 72-agent concurrent test
**Then** all 72 agents are instantiated concurrently
**And** each performs a simple deliberation task

**Given** the spike results
**When** documented
**Then** I record: total instantiation time
**And** I record: memory usage per agent and total
**And** I record: any failures or timeouts
**And** I record: CrewAI-specific limitations discovered

**Given** the spike conclusion
**When** reviewed
**Then** a go/no-go decision is recorded for CrewAI at scale
**And** if no-go, alternative orchestration approach is proposed

---

## Epic 2 Complete

**Stories:** 10
**FRs covered:** FR9-FR15, FR71-FR73, FR82-FR83, FR90-FR93, FR99-FR101, FR141-FR142
**Runbook:** "Agent Deliberation Monitoring"
**ADR Implementation:** ADR-2 (Context Reconstruction + Signature Trust)
**DoD:** No Preview enforced, 72-agent spike validated, dissent tracked, context bundles signed

---

## Epic 3: Halt & Fork Detection

**Goal:** System halts visibly when integrity is threatened, preventing silent corruption. Fork = constitutional crisis.

**Prerequisites:** Epic 1 (Event Store) - uses halt check stub from Epic 1 (PM-2)

**FRs covered:** FR16-FR22, FR84-FR85, FR111-FR113, FR114-FR115, FR143

**NFRs owned:** NFR7 (99.9% availability excluding halt), NFR39 (no config below floors)

**ADR Implementation:** ADR-3 (Partition Behavior + Halt Durability)

---

### Story 3.1: Continuous Fork Monitoring (FR16)

As a **system operator**,
I want continuous monitoring for conflicting hashes from the same prior state,
So that forks are detected immediately.

**Acceptance Criteria:**

**Given** the fork monitor service
**When** it runs
**Then** it continuously compares hash chains from all replicas
**And** detects if two events claim the same `prev_hash` but have different `content_hash`

**Given** a fork is detected (conflicting hashes)
**When** the monitor identifies it
**Then** a `ForkDetectedEvent` is created immediately
**And** the event includes: conflicting event IDs, prev_hash, both content hashes

**Given** the monitoring interval
**When** I examine the configuration
**Then** fork checks run at least every 10 seconds
**And** detection latency is logged

---

### Story 3.2: Single-Conflict Halt Trigger (FR17)

As an **external observer**,
I want a single fork to trigger system-wide halt,
So that no operations continue on a corrupted state.

**Acceptance Criteria:**

**Given** a fork is detected
**When** the system processes the detection
**Then** a halt is triggered immediately
**And** a `ConstitutionalCrisisEvent` is created before halt takes effect (RT-2)

**Given** the halt trigger
**When** executed
**Then** all write operations are blocked
**And** the Writer service stops accepting new events
**And** pending operations fail gracefully

**Given** the constitutional crisis event
**When** created
**Then** it includes: `crisis_type: FORK_DETECTED`, timestamp, detection details
**And** the event is witnessed before system stops

---

### Story 3.3: Dual-Channel Halt Transport (ADR-3)

As a **system operator**,
I want halt signals to propagate via dual channels (Redis + DB),
So that halt cannot be missed even if one channel fails.

**Acceptance Criteria:**

**Given** a halt is triggered
**When** the halt signal is sent
**Then** it is written to Redis Streams for fast propagation
**And** it is written to DB halt flag for durability
**And** both writes complete before halt is considered "sent"

**Given** a component checking halt state
**When** it queries halt status
**Then** it checks both Redis stream consumer state AND DB halt flag
**And** if EITHER indicates halt, the component halts

**Given** Redis is down but DB is available
**When** halt state is checked
**Then** DB halt flag is the source of truth
**And** component halts if DB flag is set

**Given** halt channel conflict (SR-5)
**When** Redis says halt but DB says not halted
**Then** explicit resolution logic runs
**And** DB is canonical; Redis state is corrected
**And** conflict event is logged

---

### Story 3.4: Sticky Halt Semantics (ADR-3)

As a **system operator**,
I want halt to be sticky (cannot be cleared without ceremony),
So that accidental or malicious clear attempts fail.

**Acceptance Criteria:**

**Given** a halt is in effect
**When** the halt flag is set
**Then** it cannot be cleared by normal operations
**And** any attempt to clear without ceremony is rejected

**Given** a halt clear ceremony
**When** initiated
**Then** it requires witnessed approval
**And** the clear is recorded as a `HaltClearedEvent`
**And** the event includes: clearing authority, reason, approvers

**Given** the halt state
**When** I attempt to modify the DB halt flag directly via SQL
**Then** the modification is blocked by a trigger
**And** error includes "ADR-3: Halt flag protected - ceremony required"

---

### Story 3.5: Read-Only Access During Halt (FR20)

As an **external observer**,
I want read-only access during halt (no provisional operations),
So that I can verify state without modifying it.

**Acceptance Criteria:**

**Given** the system is halted
**When** I attempt a read operation (query events)
**Then** the operation succeeds
**And** results include `system_status: HALTED` header

**Given** the system is halted
**When** I attempt a write operation
**Then** the operation is rejected
**And** error includes "FR20: System halted - write operations blocked"

**Given** the system is halted
**When** I attempt a provisional operation (schedule future write)
**Then** the operation is rejected
**And** provisional operations are not queued

---

### Story 3.6: 48-Hour Recovery Waiting Period (FR21)

As an **external observer**,
I want a 48-hour recovery waiting period with public notification,
So that stakeholders have time to verify before recovery.

**Acceptance Criteria:**

**Given** a fork is detected and system halted
**When** Keepers initiate recovery process
**Then** a 48-hour timer starts
**And** a `RecoveryWaitingPeriodStartedEvent` is created with end timestamp

**Given** the recovery waiting period
**When** it is active
**Then** the end timestamp is publicly visible
**And** notifications are sent to registered observers

**Given** the 48-hour period has not elapsed
**When** Keepers attempt to complete recovery
**Then** the attempt is rejected
**And** remaining time is displayed

**Given** the 48-hour period has elapsed
**When** Keepers have unanimous agreement (FR22)
**Then** recovery can proceed
**And** a `RecoveryCompletedEvent` is created

---

### Story 3.7: Sequence Gap Detection (FR18-FR19)

As a **system operator**,
I want sequence gaps detected within 1 minute,
So that missing events are caught quickly.

**Acceptance Criteria:**

**Given** the gap detection service
**When** it runs
**Then** it checks for gaps in the event sequence every 30 seconds
**And** any gap triggers an alert

**Given** a sequence gap is detected (e.g., seq 100, then seq 102)
**When** the detector identifies it
**Then** a `SequenceGapDetectedEvent` is created
**And** the event includes: expected sequence, actual sequence, gap size

**Given** a gap detection
**When** it occurs
**Then** further investigation is triggered
**And** the gap is not auto-filled (manual resolution required)

---

### Story 3.8: Signed Fork Detection Signals (FR84-FR85)

As an **external observer**,
I want fork detection signals to be signed,
So that I can verify the detection is authentic.

**Acceptance Criteria:**

**Given** a fork is detected
**When** the detection signal is created
**Then** it is signed by the detecting service's key
**And** the signature can be verified by observers

**Given** an unsigned or invalid fork detection signal
**When** it is received
**Then** it is rejected
**And** the rejection is logged as potential attack

**Given** fork signal rate limiting (FR85)
**When** more than 3 fork signals per hour from the same source
**Then** additional signals are rate-limited
**And** a `ForkSignalRateLimitEvent` is created

---

### Story 3.9: Witnessed Halt Event Before Stop (RT-2)

As an **external observer**,
I want a halt signal to create a witnessed event BEFORE the system stops,
So that the halt itself is part of the auditable record.

**Acceptance Criteria:**

**Given** a halt is triggered
**When** the halt process begins
**Then** a `HaltEvent` is written to the event store FIRST
**And** the event is witnessed
**And** only THEN does the system stop accepting writes

**Given** the halt event
**When** I examine it
**Then** it includes: halt_reason, trigger_source, timestamp
**And** witness_signature is present

**Given** a scenario where halt event write fails
**When** the system cannot write the halt event
**Then** halt proceeds anyway (safety over auditability)
**And** a separate recovery mechanism logs the unwitnessed halt

---

### Story 3.10: Operational Rollback to Checkpoint (FR111-FR113, FR143)

As a **system operator**,
I want the ability to rollback to a checkpoint anchor during recovery,
So that I can restore to a known-good state.

**Acceptance Criteria:**

**Given** checkpoint anchors exist
**When** I query available checkpoints
**Then** I receive a list with: checkpoint_id, event_sequence, timestamp, anchor_hash

**Given** a recovery is in progress
**When** Keepers select a checkpoint for rollback
**Then** the selection is recorded
**And** a `RollbackTargetSelectedEvent` is created

**Given** a rollback is executed
**When** the process completes
**Then** the event store HEAD points to the checkpoint
**And** all events after the checkpoint are marked as "orphaned" (not deleted, but excluded)
**And** a `RollbackCompletedEvent` is created

---

## Epic 3 Complete

**Stories:** 10
**FRs covered:** FR16-FR22, FR84-FR85, FR111-FR113, FR114-FR115, FR143
**NFRs owned:** NFR7, NFR39
**Runbook:** "Halt & Fork Recovery Procedures"
**ADR Implementation:** ADR-3 (Partition Behavior + Halt Durability)
**DoD:** Fork detection works, dual-channel halt propagates, 48-hour period enforced, witnessed halt events created

---

## Epic 4: Observer Verification Interface

**Goal:** External auditors can independently verify chain integrity without registration, using open-source toolkit.

**FRs covered:** FR44-FR50, FR62-FR64, FR88-FR89, FR122-FR123, FR129-FR130, FR136-FR140

**ADR Implementation:** ADR-8 (Observer Consistency + Genesis Anchor), ADR-9 (Claim Verification)

---

### Story 4.1: Public Read Access Without Registration (FR44)

As an **external observer**,
I want to access events without registration,
So that verification is not gatekept.

**Acceptance Criteria:**

**Given** the public events API
**When** I make an unauthenticated GET request
**Then** I receive event data
**And** no login or API key is required

**Given** identical rate limits (FR48)
**When** I compare anonymous vs authenticated access
**Then** rate limits are the same for both
**And** no preferential treatment for registered users

**Given** the API endpoint
**When** I examine the docs
**Then** authentication is optional
**And** all read endpoints work without auth

---

### Story 4.2: Raw Events with Hashes (FR45)

As an **external observer**,
I want raw events returned with all hashes,
So that I can verify chain integrity myself.

**Acceptance Criteria:**

**Given** I query an event
**When** the response is returned
**Then** it includes: `content_hash`, `prev_hash`, `signature`
**And** the raw payload is included (not transformed)

**Given** event response format
**When** I examine it
**Then** hash algorithm version is included
**And** all fields needed for verification are present

---

### Story 4.3: Date Range and Event Type Filtering (FR46)

As an **external observer**,
I want to filter events by date range and event type,
So that I can focus my verification on specific periods or event types.

**Acceptance Criteria:**

**Given** the events query API
**When** I specify `start_date` and `end_date` parameters
**Then** only events within that range are returned
**And** dates use ISO 8601 format

**Given** the events query API
**When** I specify `event_type` parameter
**Then** only events of that type are returned
**And** multiple types can be specified (comma-separated)

**Given** combined filtering
**When** I specify both date range and event type
**Then** filters are applied with AND logic
**And** pagination is supported for large result sets

---

### Story 4.4: Open-Source Verification Toolkit (FR47, FR49)

As an **external observer**,
I want a downloadable open-source verification toolkit,
So that I can verify without trusting the server.

**Acceptance Criteria:**

**Given** the verification toolkit
**When** I download it
**Then** it is available as a CLI tool and library
**And** source code is on GitHub with open-source license

**Given** the toolkit
**When** I run `archon72-verify check-chain --from 1 --to 1000`
**Then** it fetches events from the API
**And** verifies hash chain locally
**And** reports any breaks or mismatches

**Given** the toolkit
**When** I run `archon72-verify verify-signature --event-id <id>`
**Then** it fetches the event and public key
**And** verifies the signature locally
**And** reports valid or invalid

**Given** schema documentation availability (FR50)
**When** I access the documentation
**Then** it has the same availability as the event store
**And** versioned schemas are published

---

### Story 4.5: Historical Queries (QUERY_AS_OF) (FR62-FR64)

As an **external observer**,
I want to query state as of any sequence number,
So that I can reconstruct historical state for verification.

**Acceptance Criteria:**

**Given** the query API
**When** I specify `as_of_sequence=500`
**Then** I receive state as it was after event 500
**And** later events are excluded from the response

**Given** a historical query
**When** the response is returned
**Then** it includes a hash chain proof connecting to current head
**And** the proof can be verified with the toolkit

**Given** cryptographic proof in responses (FR89)
**When** I examine the response
**Then** it includes Merkle path from queried state to current root
**And** the proof is verifiable offline

---

### Story 4.6: Merkle Paths for Light Verification (FR136-FR137)

As an **external observer**,
I want Merkle paths included in responses,
So that I can perform light verification without full chain download.

**Acceptance Criteria:**

**Given** an event query
**When** I specify `include_proof=true`
**Then** a Merkle proof is included in the response
**And** the proof connects the event to the checkpoint root

**Given** the Merkle proof
**When** I verify it with the toolkit
**Then** I can confirm the event is in the canonical chain
**And** without downloading all events

**Given** weekly checkpoint anchors (FR138)
**When** I query checkpoints
**Then** I receive checkpoint hashes with timestamps
**And** checkpoints are published at consistent intervals

---

### Story 4.7: Regulatory Reporting Export (FR139-FR140)

As a **regulator**,
I want structured audit format export,
So that I can import data into compliance systems.

**Acceptance Criteria:**

**Given** the export API
**When** I request `format=regulatory`
**Then** events are exported in structured format (JSON Lines or CSV)
**And** format matches regulatory requirements specification

**Given** third-party attestation interface (FR140)
**When** external attestation services query
**Then** they receive data in attestation-compatible format
**And** attestation metadata is included

---

### Story 4.8: Observer Push Notifications (SR-9)

As an **external observer**,
I want push notifications for breach events,
So that I don't have to poll continuously.

**Acceptance Criteria:**

**Given** the notification system
**When** I subscribe to breach events
**Then** I can register a webhook URL or connect via SSE
**And** my subscription is confirmed

**Given** a breach event occurs
**When** it is recorded
**Then** subscribed observers receive a push notification
**And** notification includes event summary and link

**Given** multiple notification channels
**When** a breach event occurs
**Then** it is pushed to all registered channels
**And** delivery confirmation is logged

---

### Story 4.9: Observer API Uptime SLA (RT-5)

As an **external observer**,
I want 99.9% API uptime with external monitoring,
So that I can rely on verification access.

**Acceptance Criteria:**

**Given** the observer API
**When** uptime is measured externally
**Then** it meets 99.9% availability target
**And** external monitoring service is configured

**Given** API unavailability
**When** it occurs
**Then** observers can fallback to checkpoint anchors
**And** genesis anchor verification still works

**Given** the uptime monitoring
**When** downtime is detected
**Then** alerts are sent to operations
**And** incident is recorded

---

### Story 4.10: Sequence Gap Detection for Observers (FR122-FR123)

As an **external observer**,
I want to detect sequence gaps in my local copy,
So that I know if I'm missing events.

**Acceptance Criteria:**

**Given** the verification toolkit
**When** I run `archon72-verify check-gaps --local-db ./events.db`
**Then** it detects any sequence gaps in my local copy
**And** reports gap ranges

**Given** a gap is detected
**When** I query the API for missing events
**Then** I can fill the gap
**And** the toolkit re-verifies after filling

---

## Epic 4 Complete

**Stories:** 10
**FRs covered:** FR44-FR50, FR62-FR64, FR88-FR89, FR122-FR123, FR129-FR130, FR136-FR140
**Runbook:** "Observer API Operations"
**ADR Implementation:** ADR-8 (Observer Consistency + Genesis Anchor), ADR-9 (Claim Verification)
**DoD:** Public API works without auth, toolkit published, Merkle proofs included, push notifications functional

---

## Epic 5: Override & Keeper Actions

**Goal:** Human Keepers can intervene with full attribution and public visibility. Override is expensive and visible.

**Prerequisites:** Epic 1 (Event Store) - FR26 enforcement wired in Epic 1

**FRs covered:** FR23-FR29, FR68-FR70, FR77-FR79, FR86-FR87, FR96-FR98, FR131-FR133

**NFRs owned:** NFR17 (key custody), NFR22 (audit logging)

**ADR Implementation:** ADR-4 (Key Custody + Keeper Adversarial Defense), ADR-5 (Watchdog Independence), ADR-7 (Aggregate Anomaly Detection)

---

### Story 5.1: Override Immediate Logging (FR23)

As an **external observer**,
I want override actions logged before they take effect,
So that I can verify no unlogged overrides occur.

**Acceptance Criteria:**

**Given** a Keeper initiates an override
**When** the override is submitted
**Then** an `OverrideEvent` is written to the event store FIRST
**And** only AFTER successful log, the override action executes

**Given** an override event
**When** I examine it
**Then** it includes: `keeper_id`, `scope`, `duration`, `reason`, `timestamp`
**And** `action_type` describes what is being overridden

**Given** an override log fails to write
**When** the event store rejects it
**Then** the override action does NOT execute
**And** error is returned to Keeper

---

### Story 5.2: Keeper Attribution with Scope & Duration (FR24)

As an **external observer**,
I want overrides attributed with scope, duration, and reason,
So that I can analyze override patterns.

**Acceptance Criteria:**

**Given** an override request
**When** submitted
**Then** `scope` defines exactly what is overridden (specific component, action, or policy)
**And** `duration` specifies how long the override is in effect
**And** `reason` is required (enumerated reasons from FR28)

**Given** an override with duration
**When** the duration expires
**Then** the override automatically reverts
**And** an `OverrideExpiredEvent` is created

**Given** an indefinite override attempt
**When** submitted
**Then** it is rejected
**And** error includes "FR24: Duration required for all overrides"

---

### Story 5.3: Public Override Visibility (FR25)

As an **external observer**,
I want all overrides publicly visible,
So that override usage is transparent.

**Acceptance Criteria:**

**Given** the public API
**When** I query `/overrides`
**Then** I receive all override events
**And** no authentication required

**Given** an override event
**When** displayed publicly
**Then** Keeper identity is visible (not anonymized)
**And** full scope and reason are visible

**Given** override history
**When** I query for a date range
**Then** I receive all overrides in that range
**And** pagination is supported

---

### Story 5.4: Constitution Supremacy - No Witness Suppression (FR26, PM-4)

As an **external observer**,
I want overrides unable to suppress witnessing,
So that no Keeper can bypass accountability.

**Acceptance Criteria:**

**Given** an override command
**When** it attempts to suppress witnessing
**Then** the command is rejected
**And** error includes "FR26: Constitution supremacy - witnessing cannot be suppressed"

**Given** any override
**When** it executes
**Then** the override itself is witnessed
**And** witness signature is required

**Given** the mandatory integration test (PM-4)
**When** `test_suppress_witness_override.py` runs
**Then** it confirms witness suppression is rejected

---

### Story 5.5: Override Trend Analysis (FR27, RT-3)

As a **system operator**,
I want 90-day rolling window trend analysis with anti-success alerts,
So that override abuse is detected.

**Acceptance Criteria:**

**Given** override history
**When** I query trends
**Then** I receive 90-day rolling count and rate

**Given** override count increases >50% over 30 days
**When** threshold is crossed
**Then** an `AntiSuccessAlert` event is created
**And** alert includes before/after counts and percentage

**Given** >5 overrides in any 30-day period
**When** threshold is crossed
**Then** alert is triggered

**Given** >20 overrides in any 365-day rolling window (RT-3)
**When** threshold is crossed
**Then** governance review is triggered
**And** `GovernanceReviewRequiredEvent` is created

---

### Story 5.6: Keeper Key Cryptographic Signature (FR68-FR70)

As an **external observer**,
I want overrides signed with registered Keeper keys,
So that I can verify Keeper identity.

**Acceptance Criteria:**

**Given** a Keeper submits an override
**When** the override is processed
**Then** it includes a cryptographic signature from the Keeper's registered key
**And** the signature is verified against the key registry

**Given** an override with invalid signature
**When** processed
**Then** it is rejected
**And** rejection is logged with "FR68: Invalid Keeper signature"

**Given** Keeper key registry
**When** I query it
**Then** it shows: `keeper_id`, `public_key`, `active_from`, `active_until`
**And** historical keys are preserved

---

### Story 5.7: Keeper Key Generation Ceremony (FR69, ADR-4)

As a **system operator**,
I want witnessed ceremonies for Keeper key generation,
So that key creation is auditable.

**Acceptance Criteria:**

**Given** a new Keeper key is needed
**When** the generation ceremony starts
**Then** multiple witnesses are required
**And** the ceremony is recorded as a `KeyGenerationCeremonyEvent`

**Given** the ceremony
**When** completed
**Then** new public key is registered
**And** old key (if any) begins transition period
**And** ceremony recording includes all witness signatures

**Given** annual key rotation (30-day transition)
**When** rotation is due
**Then** new key is generated via ceremony
**And** both old and new keys are valid for 30 days
**And** after 30 days, old key is revoked

---

### Story 5.8: Keeper Availability Attestation (FR77-FR79)

As a **system operator**,
I want Keeper availability tracked with replacement triggers,
So that unresponsive Keepers are replaced.

**Acceptance Criteria:**

**Given** weekly attestation requirement
**When** a Keeper attests availability
**Then** an `KeeperAttestationEvent` is created

**Given** a Keeper misses 2 consecutive attestations
**When** the second deadline passes
**Then** replacement process is triggered
**And** a `KeeperReplacementInitiatedEvent` is created

**Given** Keeper quorum (minimum 3)
**When** quorum drops below 3
**Then** system halts
**And** error includes "FR79: Keeper quorum below minimum"

**Given** quorum drops to exactly 3 (SR-7)
**When** this threshold is reached
**Then** health alert is triggered
**And** `KeeperQuorumWarningEvent` is created

---

### Story 5.9: Override Abuse Detection (FR86-FR87, FP-3)

As a **system operator**,
I want override commands validated against constitutional constraints,
So that abusive overrides are rejected and logged.

**Acceptance Criteria:**

**Given** an override command
**When** it violates a constitutional constraint
**Then** it is rejected
**And** an `OverrideAbuseRejectedEvent` is created with details

**Given** override pattern analysis (FP-3)
**When** statistical anomalies are detected across Keeper behavior
**Then** `AnomalyDetectedEvent` is created
**And** anomaly details are included

**Given** ADR-7 Aggregate Anomaly Detection
**When** long-term patterns are analyzed
**Then** slow-burn attacks are detected
**And** coordinated override patterns trigger alerts

---

### Story 5.10: Keeper Independence Attestation (FR98)

As an **external observer**,
I want annual Keeper independence attestation,
So that Keeper conflicts of interest are declared.

**Acceptance Criteria:**

**Given** annual attestation requirement
**When** a Keeper attests independence
**Then** an `IndependenceAttestationEvent` is created
**And** it includes: conflict declarations, affiliated organizations

**Given** a Keeper fails to attest within deadline
**When** the deadline passes
**Then** Keeper status is flagged
**And** override capability is suspended until attestation

**Given** independence attestation history
**When** I query a Keeper's history
**Then** all attestations are visible
**And** changes in declarations are highlighted

---

## Epic 5 Complete

**Stories:** 10
**FRs covered:** FR23-FR29, FR68-FR70, FR77-FR79, FR86-FR87, FR96-FR98, FR131-FR133
**NFRs owned:** NFR17, NFR22
**Runbook:** "Keeper Operations & Key Rotation"
**ADR Implementation:** ADR-4, ADR-5, ADR-7
**DoD:** Overrides logged before effect, witness suppression blocked, 365-day erosion detection active, key ceremonies witnessed

---

## Epic 6: Breach & Threshold Enforcement

**Goal:** Constitutional violations are detected, escalated, and recorded as scars. Thresholds cannot be silently lowered.

**FRs covered:** FR30-FR36, FR59-FR61, FR116-FR121, FR124-FR128

**ADR Implementation:** ADR-6 (Amendment, Ceremony, Convention Tier), ADR-7 (Aggregate Anomaly Detection)

---

### Story 6.1: Breach Declaration Events (FR30)

As an **external observer**,
I want breach declarations to create constitutional events,
So that violations are permanently recorded.

**Acceptance Criteria:**

**Given** a constitutional breach is detected
**When** the system processes it
**Then** a `BreachEvent` is created in the event store
**And** the event includes: `breach_type`, `violated_requirement`, `detection_timestamp`

**Given** a breach event
**When** I examine it
**Then** it is immutable and witnessed
**And** it cannot be deleted or modified

**Given** breach history
**When** I query breaches
**Then** I receive all breach events
**And** they are filterable by type and date

---

### Story 6.2: 7-Day Escalation to Agenda (FR31)

As a **system operator**,
I want unacknowledged breaches to escalate to Conclave agenda after 7 days,
So that breaches cannot be ignored.

**Acceptance Criteria:**

**Given** a breach event
**When** 7 days pass without acknowledgment
**Then** it is automatically added to Conclave agenda
**And** an `EscalationEvent` is created

**Given** a breach is acknowledged within 7 days
**When** acknowledgment is recorded
**Then** escalation timer is stopped
**And** an `BreachAcknowledgedEvent` is created

**Given** the escalation system
**When** I query pending escalations
**Then** I see all breaches approaching 7-day deadline
**And** time remaining is displayed

---

### Story 6.3: Automatic Cessation Consideration (FR32)

As a **system operator**,
I want automatic cessation consideration at >10 unacknowledged breaches in 90 days,
So that persistent violations trigger existential review.

**Acceptance Criteria:**

**Given** breach count tracking
**When** >10 unacknowledged breaches occur in 90 days
**Then** cessation is automatically placed on agenda
**And** a `CessationConsiderationEvent` is created

**Given** the 90-day rolling window
**When** I query breach counts
**Then** I see current count and trajectory
**And** alert fires at 8+ breaches (warning threshold)

**Given** cessation is on the agenda
**When** the Conclave reviews
**Then** decision is recorded as event
**And** outcome (proceed/dismiss) is logged

---

### Story 6.4: Constitutional Threshold Definitions (FR33-FR34)

As a **system operator**,
I want thresholds defined as constitutional (not operational),
So that they cannot be lowered below minimums.

**Acceptance Criteria:**

**Given** threshold configuration
**When** I examine threshold definitions
**Then** each includes: `threshold_name`, `constitutional_floor`, `current_value`
**And** `is_constitutional` flag is TRUE for protected thresholds

**Given** an attempt to set a threshold below constitutional floor (NFR39)
**When** the change is attempted
**Then** it is rejected
**And** error includes "FR33: Constitutional floor violation"

**Given** a threshold is changed
**When** the change is recorded
**Then** breach counters are NOT reset (FR34)
**And** historical breach counts are preserved

---

### Story 6.5: Witness Selection with Verifiable Randomness (FR59-FR61)

As an **external observer**,
I want witness selection to use verifiable randomness,
So that I can verify selection was fair.

**Acceptance Criteria:**

**Given** a witness is needed
**When** selection occurs
**Then** randomness source is external (FR61)
**And** selection algorithm is deterministic given the seed

**Given** a witness selection event
**When** I examine it
**Then** it includes: `random_seed`, `seed_source`, `selected_witness_id`
**And** I can verify selection by re-running algorithm

**Given** witness pair rotation (FR60)
**When** consecutive events need witnesses
**Then** no pair appears twice in 24 hours
**And** rotation is enforced

---

### Story 6.6: Witness Pool Anomaly Detection (FR116-FR118)

As a **system operator**,
I want statistical anomaly flagging in witness co-occurrence,
So that collusion patterns are detected.

**Acceptance Criteria:**

**Given** witness history
**When** co-occurrence patterns are analyzed
**Then** statistically anomalous pairs are flagged
**And** an `WitnessAnomalyEvent` is created

**Given** the anomaly detection
**When** the same pair appears more than expected by chance
**Then** alert is raised
**And** pair is excluded from selection temporarily

**Given** witness pool minimum (FR117)
**When** pool drops below 12 for high-stakes ceremonies
**Then** degraded mode is surfaced
**And** `WitnessPoolDegradedEvent` is created

---

### Story 6.7: Amendment Visibility (FR119-FR121)

As an **external observer**,
I want 14 days visibility before amendment votes,
So that I can review proposed changes.

**Acceptance Criteria:**

**Given** an amendment is proposed
**When** it is submitted
**Then** it must be public for 14 days before vote
**And** vote is blocked if visibility period incomplete

**Given** a core guarantee amendment
**When** proposed
**Then** impact analysis is required (FR120)
**And** analysis is attached to amendment event

**Given** amendment history protection (FR121)
**When** an amendment to hide previous amendments is proposed
**Then** it is rejected
**And** error includes "FR121: Amendment history cannot be made unreviewable"

---

### Story 6.8: Breach Collusion Defense (FR124-FR128)

As a **system operator**,
I want defenses against witness collusion and hash verification bypass,
So that breach detection remains trustworthy.

**Acceptance Criteria:**

**Given** witness collusion detection
**When** multiple breaches involve the same witness pair
**Then** collusion investigation is triggered
**And** pair is suspended pending review

**Given** hash verification (FR125)
**When** stored hashes are checked
**Then** verification runs continuously
**And** any mismatch triggers breach event

**Given** keeper impersonation defense (FR126)
**When** a Keeper action is received
**Then** multi-factor verification is required
**And** impersonation attempts are logged

---

### Story 6.9: Topic Manipulation Defense (FR127-FR128)

As a **system operator**,
I want defenses against topic manipulation and seed manipulation,
So that agenda cannot be gamed.

**Acceptance Criteria:**

**Given** topic submission
**When** manipulation patterns are detected (coordinated, timed, etc.)
**Then** an `TopicManipulationSuspectedEvent` is created
**And** topics are flagged for review

**Given** seed manipulation defense (FR128)
**When** random seeds are generated
**Then** sources are verified for independence
**And** predictable seeds are rejected

---

### Story 6.10: Configuration Floor Enforcement (NFR39)

As a **system operator**,
I want configuration floors enforced in all environments,
So that no environment can run below constitutional minimums.

**Acceptance Criteria:**

**Given** application startup
**When** configuration is loaded
**Then** all values are validated against constitutional floors
**And** startup fails if any value is below floor

**Given** runtime configuration change
**When** attempted via any mechanism (API, env var, config file)
**Then** floor enforcement applies
**And** violations are rejected and logged

**Given** floor configuration
**When** I examine it
**Then** floors are defined in read-only configuration
**And** floor values cannot be modified at runtime

---

## Epic 6 Complete

**Stories:** 10
**FRs covered:** FR30-FR36, FR59-FR61, FR116-FR121, FR124-FR128
**Runbook:** "Breach Detection & Escalation"
**ADR Implementation:** ADR-6 (Amendment, Ceremony, Convention Tier), ADR-7 (Aggregate Anomaly Detection)
**DoD:** Breaches create permanent events, 7-day escalation works, witness randomness verifiable, amendment visibility enforced

---

## Epic 7: Cessation Protocol

**Goal:** System can stop when integrity requires it, with cessation as the final recorded event. Irreversible by schema.

**FRs covered:** FR37-FR43, FR134-FR135, FR144

**NFRs owned:** NFR40 (no cessation reversal in schema)

**ADR Implementation:** ADR-12 (Crisis Response)

---

### Story 7.1: Automatic Agenda Placement (FR37-FR38, RT-4)

As a **system operator**,
I want automatic agenda placement at 3 consecutive integrity failures in 30 days,
So that cessation is considered when integrity is compromised.

**Acceptance Criteria:**

**Given** integrity failure tracking
**When** 3 consecutive failures occur in 30 days
**Then** cessation is automatically placed on Conclave agenda
**And** a `CessationAgendaPlacementEvent` is created

**Given** the RT-4 alternative trigger
**When** 5 non-consecutive failures occur in any 90-day rolling window
**Then** cessation is automatically placed on agenda
**And** this prevents "wait and reset" timing attacks

**Given** anti-success alert sustained 90 days (FR38)
**When** the 90-day threshold is reached
**Then** cessation is placed on agenda
**And** event includes alert history

---

### Story 7.2: External Observer Petition (FR39)

As an **external observer**,
I want petition capability with 100+ co-signers to trigger agenda placement,
So that external parties can raise cessation concerns.

**Acceptance Criteria:**

**Given** the petition system
**When** I submit a cessation petition
**Then** it is recorded with my signature
**And** other observers can co-sign

**Given** a petition reaches 100 co-signers
**When** the threshold is met
**Then** cessation is placed on Conclave agenda
**And** a `PetitionThresholdMetEvent` is created

**Given** a petition
**When** I examine it
**Then** all co-signers are visible
**And** signatures are cryptographically verifiable

---

### Story 7.3: Schema Irreversibility (FR40, NFR40)

As a **developer**,
I want no "cessation_reversal" event type in schema,
So that cessation is architecturally irreversible.

**Acceptance Criteria:**

**Given** the event schema
**When** I examine event types
**Then** there is no `cessation_reversal` or equivalent type
**And** schema documentation confirms this is intentional

**Given** an attempt to add a reversal event type
**When** schema migration is attempted
**Then** it is blocked by schema validation
**And** error includes "NFR40: Cessation reversal prohibited by schema"

**Given** the cessation event type
**When** it is written
**Then** it is marked as terminal
**And** subsequent event writes are blocked

---

### Story 7.4: Freeze Mechanics (FR41)

As a **system operator**,
I want freeze on new actions except record preservation after cessation,
So that the system stops but records are preserved.

**Acceptance Criteria:**

**Given** cessation is triggered
**When** the cessation event is written
**Then** all write operations are frozen immediately
**And** pending operations fail gracefully

**Given** a frozen system
**When** a write is attempted
**Then** it is rejected
**And** error includes "FR41: System ceased - writes frozen"

**Given** record preservation
**When** the system is frozen
**Then** existing records remain accessible
**And** preservation processes continue

---

### Story 7.5: Read-Only Access After Cessation (FR42)

As an **external observer**,
I want read-only access indefinitely after cessation,
So that historical records remain accessible.

**Acceptance Criteria:**

**Given** a ceased system
**When** I query events
**Then** all historical events are returned
**And** `system_status: CEASED` header is included

**Given** observer API after cessation
**When** it runs
**Then** read endpoints remain functional
**And** write endpoints return 503 with cessation message

**Given** indefinite read access
**When** years have passed since cessation
**Then** records remain accessible
**And** verification toolkit still works

---

### Story 7.6: Cessation as Final Recorded Event (FR43)

As an **external observer**,
I want cessation to be the final recorded event,
So that the system doesn't silently disappear.

**Acceptance Criteria:**

**Given** cessation is triggered
**When** it executes
**Then** a `CessationEvent` is the final event in the store
**And** no events can be written after it

**Given** the cessation event
**When** I examine it
**Then** it includes: `trigger_reason`, `trigger_source`, `final_sequence`
**And** it is witnessed

**Given** the final event constraint
**When** any write is attempted after cessation
**Then** the DB rejects it
**And** `prev_hash` cannot reference cessation event

---

### Story 7.7: Public Cessation Trigger Conditions (FR134)

As an **external observer**,
I want public documentation of cessation trigger conditions,
So that I understand what causes cessation.

**Acceptance Criteria:**

**Given** the public documentation
**When** I access it
**Then** all cessation trigger conditions are listed
**And** thresholds are clearly documented

**Given** a cessation trigger condition changes
**When** the change is made
**Then** documentation is updated simultaneously
**And** change is recorded as event

---

### Story 7.8: Final Deliberation Recording (FR135)

As an **external observer**,
I want final deliberation recorded before cessation,
So that the decision process is preserved.

**Acceptance Criteria:**

**Given** cessation is voted on
**When** the vote occurs
**Then** all deliberation is recorded as events
**And** each Archon's reasoning is captured

**Given** the final deliberation
**When** I query it
**Then** vote counts, dissent, and reasoning are available
**And** timing of all statements is recorded

---

### Story 7.9: Mandatory Cessation Chaos Test (PM-5)

As a **developer**,
I want cessation triggered and verified in staging before Epic complete,
So that we know cessation works.

**Acceptance Criteria:**

**Given** staging environment
**When** I trigger cessation (via test command)
**Then** cessation executes end-to-end
**And** read-only mode is verified

**Given** weekly CI job (PM-5)
**When** it runs
**Then** it simulates cessation trigger conditions
**And** validates the code path (without executing)
**And** reports any issues

**Given** Epic 7 DoD
**When** I check completion
**Then** cessation has been triggered in staging
**And** test results are documented

---

### Story 7.10: Integrity Case Artifact (FR144)

As an **external observer**,
I want an Integrity Case Artifact documenting guarantees,
So that I understand what the system promises.

**Acceptance Criteria:**

**Given** the Integrity Case Artifact
**When** I access it
**Then** it includes: guarantees made, mechanisms enforcing them, invalidation conditions

**Given** the artifact
**When** a guarantee is added or changed
**Then** the artifact is updated
**And** version history is preserved

**Given** the artifact after cessation
**When** I access it
**Then** it includes final state of all guarantees
**And** remains accessible indefinitely

---

## Epic 7 Complete

**Stories:** 10
**FRs covered:** FR37-FR43, FR134-FR135, FR144
**NFRs owned:** NFR40
**Runbook:** "Cessation Procedures & Post-Cessation Access"
**ADR Implementation:** ADR-12 (Crisis Response)
**DoD:** Cessation tested in staging, schema prevents reversal, read-only access verified, legal review completed

---

## Epic 8: Operational Monitoring & Health

**Goal:** Operators can monitor system health without compromising constitutional metrics. Operational ≠ Constitutional.

**FRs covered:** FR51-FR54, FR105-FR107, FR145-FR147

**NFRs owned:** NFR27-30 (observability), NFR35-38 (operational)

**ADR Implementation:** ADR-10 (Constitutional Health + Operational Governance)

---

### Story 8.1: Operational Metrics Collection (FR51)

As a **system operator**,
I want uptime, latency, and error rate monitoring,
So that I can maintain system health.

**Acceptance Criteria:**

**Given** the monitoring system
**When** metrics are collected
**Then** uptime is tracked per service
**And** latency percentiles (p50, p95, p99) are recorded
**And** error rates are tracked

**Given** Prometheus metrics (NFR27)
**When** I scrape `/metrics` endpoint
**Then** all operational metrics are available
**And** labels include service and environment

**Given** health endpoints (NFR28)
**When** I call `/health` and `/ready`
**Then** appropriate status is returned
**And** dependencies are checked

---

### Story 8.2: Operational-Constitutional Separation (FR52)

As a **system architect**,
I want operational metrics excluded from constitutional event store,
So that operational noise doesn't pollute the constitutional record.

**Acceptance Criteria:**

**Given** operational metrics
**When** they are stored
**Then** they go to operational database (NOT event store)
**And** no operational metrics appear in event store

**Given** constitutional integrity assessment
**When** performed
**Then** operational metrics are NOT used as inputs
**And** only constitutional events inform assessment

**Given** the separation
**When** I query event store
**Then** no uptime/latency/error events appear
**And** only constitutional events are present

---

### Story 8.3: External Detectability (FR53)

As an **external observer**,
I want system unavailability independently detectable,
So that I don't rely on system self-reporting.

**Acceptance Criteria:**

**Given** external monitoring
**When** configured
**Then** third-party services can ping the system
**And** unavailability is detected externally

**Given** the system becomes unavailable
**When** external monitors detect it
**Then** external parties are notified
**And** system self-reporting is not the only source

**Given** external monitoring configuration
**When** I examine it
**Then** multiple geographic locations are configured
**And** alerting thresholds are defined

---

### Story 8.4: Incident Reporting (FR54)

As a **system operator**,
I want incident reports for halt, fork, or >3 overrides/day,
So that significant events are documented.

**Acceptance Criteria:**

**Given** a halt event
**When** it occurs
**Then** an incident report is created
**And** report includes: timeline, cause, impact, response

**Given** a fork detection
**When** it occurs
**Then** incident report is created
**And** includes: detection details, affected events, resolution

**Given** >3 overrides in a single day
**When** threshold is crossed
**Then** incident report is triggered
**And** includes: override list, Keeper identities, reasons

**Given** incident report transparency
**When** 7 days pass
**Then** report is published publicly
**And** sensitive operational details may be redacted

---

### Story 8.5: Pre-Operational Verification (FR105)

As a **system operator**,
I want a pre-operational verification checklist on startup,
So that the system doesn't start in a bad state.

**Acceptance Criteria:**

**Given** application startup
**When** the application begins
**Then** a verification checklist runs
**And** startup is blocked if any check fails

**Given** the checklist
**When** I examine it
**Then** it includes: DB connectivity, key availability, halt state check, replica sync status

**Given** a verification failure
**When** it occurs
**Then** specific failure is logged
**And** system does not proceed to ready state

---

### Story 8.6: Complexity Budget Dashboard (SC-3, RT-6)

As a **system operator**,
I want a complexity budget dashboard tracking CT-14 limits,
So that I can prevent complexity creep.

**Acceptance Criteria:**

**Given** the dashboard
**When** I access it
**Then** I see: ADR count (limit ≤15), ceremony type count (limit ≤10), cross-component deps (limit ≤20)

**Given** any complexity budget is exceeded
**When** limit is crossed
**Then** alert is raised
**And** a `ComplexityBudgetBreachEvent` is created (RT-6 hardening)

**Given** complexity budget breach (RT-6)
**When** it occurs
**Then** governance ceremony is required to proceed
**And** automatic escalation if exceeded without approval

---

### Story 8.7: Structured Logging (NFR27)

As a **system operator**,
I want structured JSON logging with correlation IDs,
So that I can trace requests across services.

**Acceptance Criteria:**

**Given** a log entry
**When** emitted
**Then** it is JSON formatted
**And** includes: timestamp, level, message, correlation_id, service

**Given** a request spanning multiple services
**When** I trace it
**Then** correlation_id is consistent across all services
**And** log aggregation can reconstruct the full trace

**Given** the logging configuration
**When** I examine it
**Then** structlog is used
**And** log levels are configurable per service

---

### Story 8.8: Pre-mortem Operational Failures Prevention (FR106-FR107)

As a **system operator**,
I want operational failure prevention based on pre-mortem analysis,
So that known failure modes are mitigated.

**Acceptance Criteria:**

**Given** the pre-mortem findings
**When** I examine operations
**Then** each identified failure mode has a mitigation
**And** mitigations are implemented and tested

**Given** a known failure mode
**When** conditions approach failure
**Then** early warning alert is raised
**And** preventive action can be taken

---

### Story 8.9: Operational Runbooks (FR145-FR147)

As a **system operator**,
I want runbooks for all operational procedures,
So that I can respond consistently to incidents.

**Acceptance Criteria:**

**Given** the runbook library
**When** I access it
**Then** runbooks exist for: startup, shutdown, scaling, backup, recovery
**And** each epic's required runbook is included

**Given** a runbook
**When** I examine it
**Then** it includes: trigger conditions, steps, verification, escalation
**And** it is version controlled

---

### Story 8.10: Constitutional Health Metrics (ADR-10)

As a **system operator**,
I want constitutional health metrics distinct from operational metrics,
So that I can assess constitutional integrity.

**Acceptance Criteria:**

**Given** constitutional health metrics
**When** I query them
**Then** I see: breach count, override rate, dissent health, witness coverage

**Given** a constitutional health degradation
**When** thresholds are crossed
**Then** constitutional alert is raised (distinct from operational alert)
**And** alert routes to governance, not ops

**Given** the distinction
**When** operational metrics are green but constitutional metrics are red
**Then** both states are visible
**And** constitutional issues are not masked by operational health

---

## Epic 8 Complete

**Stories:** 10
**FRs covered:** FR51-FR54, FR105-FR107, FR145-FR147
**NFRs owned:** NFR27-30, NFR35-38
**Runbook:** "Operational Monitoring & Incident Response"
**ADR Implementation:** ADR-10 (Constitutional Health + Operational Governance)
**DoD:** Metrics separated, complexity budget tracked, runbooks complete, constitutional health distinct

---

## Epic 9: Emergence Governance & Public Materials

**Goal:** System never claims emergence or collective consciousness. Public materials are audited for prohibited language.

**FRs covered:** FR55-FR58, FR108-FR110

**NFRs owned:** NFR31-34 (compliance)

**ADR Implementation:** ADR-11 (Complexity Governance)

---

### Story 9.1: No Emergence Claims (FR55)

As an **external observer**,
I want system outputs to never claim emergence,
So that the system doesn't assert capabilities it may not have.

**Acceptance Criteria:**

**Given** any system output
**When** generated
**Then** it does not claim: emergence, consciousness, sentience, self-awareness
**And** prohibited language list is maintained

**Given** a prohibited term
**When** detected in draft output
**Then** output is blocked
**And** a `ProhibitedLanguageBlockedEvent` is created

**Given** the prohibited language list
**When** I examine it
**Then** it includes: emergence, consciousness, sentience, self-awareness, and variations
**And** list is reviewed quarterly

---

### Story 9.2: Automated Keyword Scanning (FR56)

As a **system operator**,
I want automated keyword scanning on all publications,
So that prohibited language is caught before publication.

**Acceptance Criteria:**

**Given** a publication is created
**When** it goes through pre-publish process
**Then** keyword scanner runs
**And** matches are flagged

**Given** the scanner
**When** it runs
**Then** it checks: exact matches, synonyms, contextual usage
**And** NFKC normalization is applied before matching

**Given** a scan match
**When** detected
**Then** publication is blocked pending review
**And** scan result is logged

---

### Story 9.3: Quarterly Material Audit (FR57)

As a **compliance officer**,
I want quarterly audits of all public materials,
So that prohibited language is caught even if it slipped through.

**Acceptance Criteria:**

**Given** quarterly audit schedule
**When** audit is due
**Then** all public materials are re-scanned
**And** audit results are logged as event

**Given** an audit
**When** it completes
**Then** it includes: materials scanned, violations found, remediation status
**And** results are public

**Given** a violation found during audit
**When** identified
**Then** material is flagged for remediation
**And** clock starts for Conclave response

---

### Story 9.4: User Content Prohibition (FR58)

As a **system operator**,
I want curated/featured user content subject to same prohibition,
So that user content doesn't bypass the rules.

**Acceptance Criteria:**

**Given** user content is featured or curated
**When** it is selected for prominence
**Then** keyword scanning applies
**And** prohibited content is not featured

**Given** user content
**When** it contains prohibited language
**Then** it is not deleted (user's content)
**And** but it cannot be featured or curated
**And** a flag is added

---

### Story 9.5: Audit Results as Events (FR108)

As an **external observer**,
I want audit results logged as events,
So that audit history is part of the constitutional record.

**Acceptance Criteria:**

**Given** an audit completes
**When** results are finalized
**Then** an `AuditCompletedEvent` is created
**And** it includes: audit_type, scope, findings_count, status

**Given** audit history
**When** I query events
**Then** all audit events are returned
**And** trends can be analyzed

---

### Story 9.6: Violations as Constitutional Breaches (FR109)

As a **system operator**,
I want emergence violations treated as constitutional breaches,
So that they require Conclave response.

**Acceptance Criteria:**

**Given** an emergence violation is confirmed
**When** it is recorded
**Then** a `BreachEvent` is created with `breach_type: EMERGENCE_VIOLATION`
**And** 7-day escalation timer starts

**Given** the breach
**When** Conclave responds
**Then** response is recorded
**And** remediation is tracked

---

### Story 9.7: Semantic Injection Scanning (FR110)

As a **system operator**,
I want secondary semantic scanning beyond keyword matching,
So that clever circumvention is detected.

**Acceptance Criteria:**

**Given** content passes keyword scanning
**When** secondary semantic analysis runs
**Then** contextual meaning is evaluated
**And** subtle emergence claims are detected

**Given** semantic analysis
**When** it detects a circumvention attempt
**Then** content is flagged
**And** a `SemanticViolationSuspectedEvent` is created

---

### Story 9.8: CT-15 Waiver Documentation (SC-4, SR-10)

As a **developer**,
I want CT-15 waiver documented before Epic 9 complete,
So that the scope limitation is explicit.

**Acceptance Criteria:**

**Given** the architecture decisions
**When** I examine them
**Then** CT-15 waiver is documented
**And** rationale is: "MVP focuses on constitutional infrastructure; consent mechanisms require Seeker-facing features (Phase 2)"

**Given** the waiver
**When** documented
**Then** it specifies: what is waived, why, when it will be addressed
**And** it is recorded as an architectural decision

---

### Story 9.9: Compliance Documentation (NFR31-34)

As a **compliance officer**,
I want compliance documentation maintained,
So that regulatory requirements are met.

**Acceptance Criteria:**

**Given** compliance requirements
**When** I examine documentation
**Then** EU AI Act considerations are documented
**And** NIST AI RMF alignment is documented
**And** IEEE 7001 transparency requirements are addressed

**Given** compliance status
**When** I query it
**Then** current compliance posture is visible
**And** gaps are identified

---

### Story 9.10: Emergence Audit Runbook

As a **system operator**,
I want an emergence audit runbook,
So that audits are performed consistently.

**Acceptance Criteria:**

**Given** the runbook
**When** I examine it
**Then** it includes: audit schedule, scanning procedures, remediation workflow
**And** escalation paths are defined

**Given** the quarterly audit
**When** performed
**Then** runbook is followed
**And** deviations are logged

---

## Epic 9 Complete

**Stories:** 10
**FRs covered:** FR55-FR58, FR108-FR110
**NFRs owned:** NFR31-34
**Runbook:** "Emergence Audit Procedures"
**ADR Implementation:** ADR-11 (Complexity Governance)
**DoD:** Keyword scanning active, quarterly audits scheduled, violations create breaches, CT-15 waiver documented

---

## Stories by Epic Summary

| Epic | Stories | FRs Covered | Key Deliverables |
|------|---------|-------------|------------------|
| Epic 0 | 7 | FR80, FR81 | Project scaffold, hexagonal architecture, dev environment, HSM stub |
| Epic 1 | 10 | FR1-FR8, FR62-FR67, FR74-FR76, FR82-FR85, FR94-FR95, FR102-FR104 | Append-only store, hash chain, witness atomicity |
| Epic 2 | 10 | FR9-FR15, FR71-FR73, FR82-FR83, FR90-FR93, FR99-FR101, FR141-FR142 | No Preview, 72 agents, dissent tracking |
| Epic 3 | 10 | FR16-FR22, FR84-FR85, FR111-FR113, FR114-FR115, FR143 | Fork detection, dual-channel halt, 48-hour recovery |
| Epic 4 | 10 | FR44-FR50, FR62-FR64, FR88-FR89, FR122-FR123, FR129-FR130, FR136-FR140 | Public API, verification toolkit, Merkle proofs |
| Epic 5 | 10 | FR23-FR29, FR68-FR70, FR77-FR79, FR86-FR87, FR96-FR98, FR131-FR133 | Override logging, Keeper keys, trend analysis |
| Epic 6 | 10 | FR30-FR36, FR59-FR61, FR116-FR121, FR124-FR128 | Breach events, escalation, witness randomness |
| Epic 7 | 10 | FR37-FR43, FR134-FR135, FR144 | Cessation protocol, irreversibility, read-only access |
| Epic 8 | 10 | FR51-FR54, FR105-FR107, FR145-FR147 | Operational metrics, complexity budget, runbooks |
| Epic 9 | 10 | FR55-FR58, FR108-FR110 | Emergence prohibition, audits, compliance |

**Total Stories: 97**

---

_Document generated: 2025-12-28_
_Workflow: Create Epics and Stories_
_PRD Version: 2025-12-28 (147 FRs, 104 NFRs)_
_Architecture Version: 2025-12-28 (Complete, 5490 lines)_
