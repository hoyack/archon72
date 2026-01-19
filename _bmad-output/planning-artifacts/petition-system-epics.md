---
stepsCompleted: [1, 2, 3, 4]
inputDocuments:
  - _bmad-output/planning-artifacts/petition-system-prd.md
  - _bmad-output/planning-artifacts/petition-system-architecture.md
prdVersion: '2026-01-19 (70 FRs, 53 NFRs) - Amendment 13A'
architectureVersion: '2026-01-19 (Complete, 12 Decisions)'
storiesVersion: '2026-01-19 (71 stories across 10 epics)'
validationStatus: 'COMPLETE - All FRs covered, Grand Architect rulings applied'
---

# Petition System - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for the **Petition System**, decomposing 70 Functional Requirements and 53 Non-Functional Requirements from the PRD and Architecture into implementable stories.

**Constitutional Core:** The **Three Fates** are Marquis-rank Archon AI agents that deliberate on every petition using supermajority consensus, determining its terminal disposition: ACKNOWLEDGED, REFERRED, or ESCALATED.

## Requirements Inventory

### Functional Requirements

**Total: 70 Functional Requirements (49 P0, 20 P1, 1 P2)**

| Group | FR Range | Count | P0 | P1 | P2 |
|-------|----------|-------|----|----|-----|
| Petition Intake | FR-1.1 to FR-1.7 | 7 | 6 | 1 | 0 |
| State Machine | FR-2.1 to FR-2.6 | 6 | 6 | 0 | 0 |
| Acknowledgment | FR-3.1 to FR-3.6 | 6 | 3 | 3 | 0 |
| Referral | FR-4.1 to FR-4.7 | 7 | 4 | 3 | 0 |
| Escalation | FR-5.1 to FR-5.8 | 8 | 7 | 1 | 0 |
| Co-signer | FR-6.1 to FR-6.6 | 6 | 4 | 2 | 0 |
| Status/Visibility | FR-7.1 to FR-7.5 | 5 | 2 | 3 | 0 |
| Legitimacy Decay | FR-8.1 to FR-8.5 | 5 | 0 | 5 | 0 |
| Migration | FR-9.1 to FR-9.4 | 4 | 3 | 1 | 0 |
| Petition Types | FR-10.1 to FR-10.4 | 4 | 2 | 1 | 1 |
| **Deliberation** | **FR-11.1 to FR-11.12** | **12** | **12** | **0** | **0** |

**Petition Intake (7 FRs):**
- FR-1.1: System SHALL accept petition submissions via REST API [P0]
- FR-1.2: System SHALL generate UUIDv7 petition_id on submission [P0]
- FR-1.3: System SHALL validate petition schema (type, text, submitter_id) [P0]
- FR-1.4: System SHALL return HTTP 503 on queue overflow (no silent drop) [P0]
- FR-1.5: System SHALL enforce rate limits per submitter_id [P1]
- FR-1.6: System SHALL set initial state to RECEIVED [P0]
- FR-1.7: System SHALL emit PetitionReceived event on successful intake [P0]

**Petition State Machine (6 FRs):**
- FR-2.1: System SHALL enforce valid state transitions only [P0]
- FR-2.2: System SHALL support states: RECEIVED, DELIBERATING, ACKNOWLEDGED, REFERRED, ESCALATED [P0]
- FR-2.3: System SHALL reject transitions not in transition matrix [P0]
- FR-2.4: System SHALL use atomic CAS for fate assignment (no double-fate) [P0]
- FR-2.5: System SHALL emit fate event in same transaction as state update [P0]
- FR-2.6: System SHALL mark petition as terminal when fate assigned [P0]

**Acknowledgment Handling (6 FRs):**
- FR-3.1: Marquis SHALL be able to ACKNOWLEDGE petition with reason code [P0]
- FR-3.2: System SHALL require reason_code from enumerated list [P0]
- FR-3.3: System SHALL require rationale text for REFUSED and NO_ACTION_WARRANTED [P0]
- FR-3.4: System SHALL require reference_petition_id for DUPLICATE [P1]
- FR-3.5: System SHALL enforce minimum dwell time before ACKNOWLEDGE [P1]
- FR-3.6: System SHALL track acknowledgment rate metrics per Marquis [P1]

**Referral Handling (7 FRs):**
- FR-4.1: Marquis SHALL be able to REFER petition to Knight with realm_id [P0]
- FR-4.2: System SHALL assign referral deadline (3 cycles default) [P0]
- FR-4.3: Knight SHALL receive decision package (petition + context) [P0]
- FR-4.4: Knight SHALL be able to request extension (max 2) [P1]
- FR-4.5: System SHALL auto-ACKNOWLEDGE on referral timeout (reason: EXPIRED) [P0]
- FR-4.6: Knight SHALL submit recommendation with mandatory rationale [P0]
- FR-4.7: System SHALL enforce max concurrent referrals per Knight [P1]

**Escalation Handling (8 FRs):**
- FR-5.1: System SHALL ESCALATE petition when co-signer threshold reached [P0]
- FR-5.2: Escalation thresholds: CESSATION=100, GRIEVANCE=50 [P0]
- FR-5.3: System SHALL emit EscalationTriggered event with co-signer_count [P0]
- FR-5.4: King SHALL receive escalation queue distinct from organic Motions [P0]
- FR-5.5: King SHALL be able to ADOPT petition (creates Motion) [P0]
- FR-5.6: Adoption SHALL consume promotion budget (H1 compliance) [P0]
- FR-5.7: Adopted Motion SHALL include source_petition_ref [P0]
- FR-5.8: King SHALL be able to ACKNOWLEDGE escalation (with rationale) [P0]

**Co-signer Management (6 FRs):**
- FR-6.1: Seeker SHALL be able to co-sign active petition [P0]
- FR-6.2: System SHALL enforce unique constraint (petition_id, signer_id) [P0]
- FR-6.3: System SHALL reject co-sign after fate assignment [P1]
- FR-6.4: System SHALL increment co-signer count atomically [P0]
- FR-6.5: System SHALL check escalation threshold on each co-sign [P0]
- FR-6.6: System SHALL apply SYBIL-1 rate limiting per signer [P1]

**Status & Visibility (5 FRs):**
- FR-7.1: Observer SHALL be able to query petition status by petition_id [P0]
- FR-7.2: System SHALL return status_token for efficient long-poll [P1]
- FR-7.3: System SHALL notify Observer on fate assignment [P1]
- FR-7.4: System SHALL expose co-signer count in status response [P0]
- FR-7.5: Observer SHALL be able to WITHDRAW petition (before fate) [P1]

**Legitimacy Decay (5 FRs):**
- FR-8.1: System SHALL compute legitimacy decay metric per cycle [P1]
- FR-8.2: Decay formula: (fated_petitions / total_petitions) within SLA [P1]
- FR-8.3: System SHALL alert on decay below 0.85 threshold [P1]
- FR-8.4: High Archon SHALL access legitimacy dashboard [P1]
- FR-8.5: System SHALL identify petitions stuck in RECEIVED [P1]

**Migration & Compatibility (4 FRs):**
- FR-9.1: System SHALL migrate Story 7.2 cessation_petition to CESSATION type [P0]
- FR-9.2: All 98 existing tests SHALL pass post-migration [P0]
- FR-9.3: System SHALL support dual-write during migration period [P1]
- FR-9.4: System SHALL preserve existing petition_id references [P0]

**Petition Types (4 FRs):**
- FR-10.1: System SHALL support petition types: GENERAL, CESSATION, GRIEVANCE, COLLABORATION [P0]
- FR-10.2: CESSATION petitions SHALL auto-escalate at 100 co-signers [P0]
- FR-10.3: GRIEVANCE petitions SHALL auto-escalate at 50 co-signers [P1]
- FR-10.4: META petitions (about petition system) SHALL route to High Archon [P2]

**Three Fates Deliberation (12 FRs):**
- FR-11.1: System SHALL assign exactly 3 Marquis-rank Archons from Three Fates pool to deliberate each petition [P0]
- FR-11.2: System SHALL initiate mini-Conclave deliberation session when petition enters RECEIVED state [P0]
- FR-11.3: System SHALL provide deliberation context package (petition, type, co-signer count, similar petitions) to each Fate Archon [P0]
- FR-11.4: Deliberation SHALL follow structured protocol: Assess -> Position -> Cross-Examine -> Vote [P0]
- FR-11.5: System SHALL require supermajority consensus (2-of-3 Archons) for disposition decision [P0]
- FR-11.6: Fate Archons SHALL vote for exactly one disposition: ACKNOWLEDGE, REFER, or ESCALATE [P0]
- FR-11.7: System SHALL preserve ALL deliberation utterances (hash-referenced) with ledger witnessing at phase boundaries per CT-12 [P0]
- FR-11.8: System SHALL record dissenting opinion when vote is not unanimous [P0]
- FR-11.9: System SHALL enforce deliberation timeout (5 minutes default) with auto-ESCALATE on expiry [P0]
- FR-11.10: System SHALL auto-ESCALATE after 3 deliberation rounds without supermajority (deadlock) [P0]
- FR-11.11: System SHALL route petition to appropriate pipeline based on deliberation outcome [P0]
- FR-11.12: System SHALL preserve complete deliberation transcript for audit reconstruction [P0]

### Non-Functional Requirements

**Total: 53 Non-Functional Requirements (15 Critical)**

| Group | NFR Range | Count | Critical |
|-------|-----------|-------|----------|
| Performance | NFR-1.1 to NFR-1.5 | 5 | NFR-1.4 |
| Scalability | NFR-2.1 to NFR-2.5 | 5 | NFR-2.2 |
| Reliability | NFR-3.1 to NFR-3.6 | 6 | NFR-3.1, NFR-3.2, NFR-3.3 |
| Durability | NFR-4.1 to NFR-4.5 | 5 | NFR-4.1, NFR-4.2 |
| Security | NFR-5.1 to NFR-5.6 | 6 | NFR-5.1, NFR-5.2 |
| Auditability | NFR-6.1 to NFR-6.5 | 5 | NFR-6.1 |
| Operability | NFR-7.1 to NFR-7.5 | 5 | NFR-7.1 |
| Compatibility | NFR-8.1 to NFR-8.5 | 5 | NFR-8.1 |
| Testability | NFR-9.1 to NFR-9.5 | 5 | NFR-9.3 |
| **Deliberation** | **NFR-10.1 to NFR-10.6** | **6** | **NFR-10.1, NFR-10.3, NFR-10.4** |

**Performance (5 NFRs):**
- NFR-1.1: Petition intake latency p99 < 200ms
- NFR-1.2: Status query latency p99 < 100ms
- NFR-1.3: Co-sign processing p99 < 150ms
- NFR-1.4: Escalation trigger detection < 1 second from threshold [CRITICAL]
- NFR-1.5: Legitimacy metric computation < 60 seconds per cycle

**Scalability (5 NFRs):**
- NFR-2.1: Concurrent petitions in RECEIVED: 10,000+
- NFR-2.2: Co-signers per petition: 100,000+ [CRITICAL]
- NFR-2.3: Petitions per cycle: 1,000+
- NFR-2.4: Horizontal scaling: Stateless API nodes
- NFR-2.5: Database connection pooling: 100 connections per node

**Reliability (6 NFRs):**
- NFR-3.1: No silent petition loss: 0 lost petitions [CRITICAL]
- NFR-3.2: Fate assignment atomicity: 100% single-fate [CRITICAL]
- NFR-3.3: Event witnessing: 100% fate events persisted [CRITICAL]
- NFR-3.4: Referral timeout reliability: 100% timeouts fire
- NFR-3.5: Co-signer deduplication: 0 duplicate signatures
- NFR-3.6: System availability: 99.9% uptime

**Durability (5 NFRs):**
- NFR-4.1: Petition state durability: Survives process restart [CRITICAL]
- NFR-4.2: Event log durability: Append-only, no deletion [CRITICAL]
- NFR-4.3: Co-signer list durability: No truncation before archive
- NFR-4.4: Referral deadline persistence: Survives scheduler restart
- NFR-4.5: Budget consumption durability: Atomic with promotion

**Security (6 NFRs):**
- NFR-5.1: Rate limiting per identity: Configurable per type [CRITICAL]
- NFR-5.2: Identity verification for co-sign: Required [CRITICAL]
- NFR-5.3: Input sanitization: All petition text sanitized
- NFR-5.4: Role-based access control: Actor-appropriate endpoints
- NFR-5.5: Audit log immutability: Hash chain integrity
- NFR-5.6: Legitimacy metrics visibility: Internal-only by default

**Auditability (5 NFRs):**
- NFR-6.1: All fate transitions witnessed: Event with actor, timestamp, reason [CRITICAL]
- NFR-6.2: Adoption provenance: source_petition_ref immutable
- NFR-6.3: Rationale preservation: REFUSED/NO_ACTION rationale stored
- NFR-6.4: Co-signer attribution: Full signer list queryable
- NFR-6.5: State history reconstruction: Full replay from event log

**Operability (5 NFRs):**
- NFR-7.1: Orphan petition detection: Daily sweep identifies stuck petitions [CRITICAL]
- NFR-7.2: Legitimacy decay alerting: Alert at < 0.85 threshold
- NFR-7.3: Referral load balancing: Max concurrent per Knight configurable
- NFR-7.4: Queue depth monitoring: Backpressure before overflow
- NFR-7.5: Timeout job monitoring: Heartbeat on scheduler

**Compatibility (5 NFRs):**
- NFR-8.1: Story 7.2 test compatibility: 98/98 tests pass [CRITICAL]
- NFR-8.2: Existing petition_id preservation: No ID changes
- NFR-8.3: Motion Gates integration: Uses existing promotion budget
- NFR-8.4: EventWriterService integration: Same witness pipeline
- NFR-8.5: API versioning: /v1/ prefix for new endpoints

**Testability (5 NFRs):**
- NFR-9.1: Unit test coverage > 90% for domain logic
- NFR-9.2: Integration test coverage: All state transitions
- NFR-9.3: FMEA scenario coverage: All 10 critical failure modes [CRITICAL]
- NFR-9.4: Load test harness: Simulates 10k petition flood
- NFR-9.5: Chaos testing: Scheduler crash recovery

**Deliberation Performance (6 NFRs):**
- NFR-10.1: Deliberation end-to-end latency p95 < 5 minutes [CRITICAL]
- NFR-10.2: Individual Archon response time p95 < 30 seconds
- NFR-10.3: Consensus determinism: 100% reproducible given same inputs [CRITICAL]
- NFR-10.4: Witness completeness: 100% utterances witnessed [CRITICAL]
- NFR-10.5: Concurrent deliberations: 100+ simultaneous sessions
- NFR-10.6: Archon substitution latency: < 10 seconds on failure

### Additional Requirements

**From Architecture Decisions (D1-D12):**

| ID | Decision | Implementation Impact |
|----|----------|----------------------|
| D1 | Supabase Migrations | All schema via migration files |
| D2 | Schema Versioning | All events include `schema_version` |
| D3 | Read Models | Application projections, rebuildable |
| D4 | Rate Limiting | PostgreSQL time-bucket counters |
| D5 | MFA | Keeper/Operator scopes only |
| D6 | Authentication | Supabase JWTs M1-M2 |
| D7 | Errors | RFC 7807 + governance extensions |
| D8 | Pagination | Keyset with base64 cursors |
| D9 | API Versioning | URL path (/api/v1/) |
| D10 | Observability | OTel + Prometheus/Grafana |
| D11 | Feature Flags | Config-based, constitutional excluded |
| D12 | Retry Policy | Non-authoritative calls only |

**Module Structure (Hexagonal):**
```
src/
├── domain/models/
│   ├── petition.py              # Petition aggregate
│   ├── co_sign_request.py       # CoSignRequest aggregate
│   ├── deliberation_session.py  # DeliberationSession aggregate
│   ├── fate_archon.py           # FateArchon value object
│   └── realm_health.py          # RealmHealth aggregate
├── application/
│   ├── ports/
│   │   ├── petition_store.py    # Repository protocol
│   │   ├── deliberation_store.py # Deliberation repository
│   │   ├── archon_pool.py       # Archon selection protocol
│   │   └── fraud_detector.py    # Fraud detection protocol
│   └── services/
│       ├── petition_service.py       # Core lifecycle
│       ├── deliberation_service.py   # Three Fates orchestration
│       ├── escalation_service.py     # Escalation handling
│       └── adoption_service.py       # Bridge to Motion Gates
├── infrastructure/adapters/
│   ├── persistence/
│   │   ├── petition_store.py         # PostgreSQL implementation
│   │   ├── deliberation_store.py     # Deliberation persistence
│   │   └── realm_health_store.py
│   └── ai/
│       └── crewai_deliberation.py    # CrewAI multi-agent adapter
└── api/routes/
    └── petitions.py                  # FastAPI endpoints
```

**Hidden Prerequisites (M1):**
- HP-1: Job queue for deadline monitoring
- HP-2: Content hashing service (Blake3)
- HP-3: Realm registry (valid routing targets)
- HP-4: Sentinel-to-realm mapping
- HP-7: Read model projections
- HP-8: Notification templates
- HP-9: Fraud rule engine
- HP-10: CrewAI multi-agent framework integration
- HP-11: Archon persona definitions (Three Fates pool)

**Hidden Prerequisites (M2 - Deferred per Ruling-3):**
- HP-12: Petition Similarity Index (P1 enhancement, not M1 blocker)

**Integration Points:**
- EventWriterService (existing witnessing pipeline)
- PromotionBudgetStore (H1 budget for King adoption)
- Supabase Auth (JWT validation)
- Motion Gates (adoption bridge)
- CrewAI (multi-agent deliberation)

**Constitutional Truths:**
- AT-1: Every petition terminates in exactly one of Three Fates (determined by deliberating Archons)
- AT-2: Silence has measurable cost (CT-14)
- AT-3: Claims are witnessed before processing (CT-12)
- AT-4: Agenda is scarce (CT-11)
- AT-5: Petitions are external; Motions are internal
- AT-6: Deliberation is collective judgment, not unilateral decision

**Hardening Controls (8 P0):**
- HC-1: Fate transition requires witness event
- HC-2: Co-sign timeout (24h) with auto-reject
- HC-3: Escalation consumes H1 budget atomically
- HC-4: Rate limit: 10 petitions/user/hour
- HC-5: Duplicate detection via content hash
- HC-6: Job queue dead-letter with alerting
- HC-7: Deliberation timeout auto-ESCALATE
- PREVENT-7: Adoption ratio alert > 50% per realm

## FR Coverage Map

| Epic | FR Coverage | Count |
|------|-------------|-------|
| Epic 0: Foundation & Migration | FR-9.1, FR-9.2, FR-9.3, FR-9.4 + HPs + CrewAI Spike | 4 + HP |
| Epic 1: Petition Intake & State Machine | FR-1.1-1.7, FR-2.1-2.6, FR-7.1, FR-7.4, FR-10.1 | 15 |
| **Epic 2A: Core Deliberation Protocol** | FR-11.1-11.6, FR-11.11 | 7 |
| **Epic 2B: Edge Cases & Guarantees** | FR-11.7-11.10, FR-11.12 | 5 |
| Epic 3: Acknowledgment Execution | FR-3.1-3.6 | 6 |
| Epic 4: Knight Referral Workflow | FR-4.1-4.7 | 7 |
| Epic 5: Co-signing & Auto-Escalation | FR-5.1-5.3, FR-6.1-6.6, FR-10.2, FR-10.3 | 11 |
| Epic 6: King Escalation & Adoption Bridge | FR-5.4-5.8 | 5 |
| Epic 7: Observer Engagement | FR-7.2, FR-7.3, FR-7.5, + Transcript Access Mediation | 3 + 1 |
| Epic 8: Legitimacy Metrics & Governance | FR-8.1-8.5, FR-10.4 | 6 |
| **Total** | **70 FRs** | **70** |

## Epic List

### Epic 0: Foundation & Migration (Pre-requisite)
**Value:** Enable all subsequent epics by migrating Story 7.2 and establishing infrastructure
**FRs:** FR-9.1, FR-9.2, FR-9.3, FR-9.4
**Hidden Prerequisites:** HP-1, HP-2, HP-3, HP-4, HP-7, HP-8, HP-9, HP-10, HP-11
**Special Stories:**
- CrewAI Feasibility Spike: Validate multi-agent deliberation works at all
- DELIBERATING State Migration: Add intermediate state to schema
**Dependencies:** None (foundation)
**Critical Path:** Yes - blocks all other epics

### Epic 1: Petition Intake & State Machine
**Value:** Observers can submit petitions and track their status through the system
**FRs:** FR-1.1-1.7, FR-2.1-2.6, FR-7.1, FR-7.4, FR-10.1
**NFRs:** NFR-1.1, NFR-1.2, NFR-2.1, NFR-3.1, NFR-4.1
**Dependencies:** Epic 0
**Critical Path:** Yes - enables deliberation

### Epic 2A: Core Deliberation Protocol (CRITICAL PATH)
**Value:** Petitions receive collective deliberative judgment from Marquis-rank Archons (happy path)
**FRs:** FR-11.1-11.6, FR-11.11
**NFRs:** NFR-10.1, NFR-10.2, NFR-10.5
**Scope:**
- Archon assignment and session initiation
- Basic context package (no similarity search - per Ruling-3)
- Assess → Position → Cross-Examine → Vote protocol
- Supermajority consensus and disposition emission
- Phase-level witness batching (per Ruling-1)
- Deterministic seeding for CrewAI
**Dependencies:** Epic 0 (spike), Epic 1
**Critical Path:** Yes - proves collective judgment works

### Epic 2B: Deliberation Edge Cases & Guarantees
**Value:** Deliberation holds under stress with full auditability
**FRs:** FR-11.7-11.10, FR-11.12
**NFRs:** NFR-10.3, NFR-10.4, NFR-10.6
**Scope:**
- Phase-boundary witnessing with hash-referenced transcripts
- Dissent recording
- Timeout handling (5 min) with auto-ESCALATE
- Deadlock handling (3 rounds) with auto-ESCALATE
- Archon substitution on failure
- Audit trail and replay capability
- Load and chaos testing
**Dependencies:** Epic 2A
**Critical Path:** Yes - guarantees earned rigor

### Epic 3: Acknowledgment Execution
**Value:** System can formally acknowledge petitions with appropriate reason codes
**FRs:** FR-3.1-3.6
**NFRs:** NFR-6.1, NFR-6.3
**Dependencies:** Epic 2A (deliberation decides ACKNOWLEDGE)
**Critical Path:** Yes - first fate implementation

### Epic 4: Knight Referral Workflow
**Value:** Domain experts can review and recommend on referred petitions
**FRs:** FR-4.1-4.7
**NFRs:** NFR-3.4, NFR-4.4, NFR-7.3
**Dependencies:** Epic 2A (deliberation decides REFER)
**Critical Path:** Yes - second fate implementation

### Epic 5: Co-signing & Auto-Escalation
**Value:** Seekers can collectively support petitions, triggering auto-escalation at thresholds
**FRs:** FR-5.1-5.3, FR-6.1-6.6, FR-10.2, FR-10.3
**NFRs:** NFR-1.3, NFR-1.4, NFR-2.2, NFR-3.5, NFR-5.2
**Dependencies:** Epic 1
**Critical Path:** No - can parallelize with Epic 2A

### Epic 6: King Escalation & Adoption Bridge
**Value:** Kings can adopt petitions as Motions, bridging external voice to internal governance
**FRs:** FR-5.4-5.8
**NFRs:** NFR-4.5, NFR-8.3
**Dependencies:** Epic 2A (deliberation decides ESCALATE), Epic 5 (auto-escalation)
**Critical Path:** Yes - third fate implementation

### Epic 7: Observer Engagement
**Value:** Observers receive notifications, can withdraw petitions, and access mediated deliberation artifacts
**FRs:** FR-7.2, FR-7.3, FR-7.5
**NFRs:** NFR-1.2
**Special Stories (per Ruling-2):**
- Transcript Access Mediation: Observer access to deliberation artifacts is mediated, not ambient
- Phase Summary Generation: Observers receive phase summaries, vote outcomes, dissent indicators
**Dependencies:** Epic 1, Epic 2B (for transcript access)
**Critical Path:** No - enhancement

### Epic 8: Legitimacy Metrics & Governance
**Value:** High Archon can monitor system health and petition responsiveness
**FRs:** FR-8.1-8.5, FR-10.4
**NFRs:** NFR-1.5, NFR-7.1, NFR-7.2, NFR-5.6
**Dependencies:** Epics 2A-6 (needs fate data)
**Critical Path:** No - governance oversight

## Dependency Graph

```
                    ┌────────────────┐
                    │   Epic 0:      │
                    │   Foundation   │
                    │   + CrewAI     │
                    │     Spike      │
                    └───────┬────────┘
                            │
                    ┌───────▼────────┐
                    │   Epic 1:      │
                    │   Intake &     │
                    │   State Machine│
                    └───────┬────────┘
                            │
           ┌────────────────┼────────────────┐
           │                │                │
   ┌───────▼────────┐      │        ┌───────▼────────┐
   │   Epic 5:      │      │        │   Epic 7:      │
   │   Co-signing   │      │        │   Observer     │
   │   & Auto-Esc   │      │        │   (partial)    │
   └───────┬────────┘      │        └───────┬────────┘
           │               │                │
           │       ┌───────▼────────┐       │
           │       │   Epic 2A:     │ ◄─── CRITICAL PATH
           │       │   Core Delib   │       │
           │       │   (happy path) │       │
           │       └───────┬────────┘       │
           │               │                │
           │    ┌──────────┼──────────┐     │
           │    │          │          │     │
           │ ┌──▼──┐   ┌───▼───┐  ┌───▼───┐ │
           │ │ E3: │   │  E4:  │  │  E6:  │ │
           │ │ACK  │   │ REFER │  │ESCALATE│ │
           │ └─────┘   └───────┘  └───┬───┘ │
           │                          │     │
           └──────────────────────────┘     │
                            │               │
                    ┌───────▼────────┐      │
                    │   Epic 2B:     │      │
                    │   Edge Cases   │      │
                    │   & Guarantees │      │
                    └───────┬────────┘      │
                            │               │
                            └───────┬───────┘
                                    │
                            ┌───────▼────────┐
                            │   Epic 7:      │
                            │   (transcript  │
                            │    access)     │
                            └───────┬────────┘
                                    │
                            ┌───────▼────────┐
                            │   Epic 8:      │
                            │   Legitimacy   │
                            │   Metrics      │
                            └────────────────┘
```

## Sprint Allocation (Revised per Ruling-4)

| Sprint | Epics | Focus | Risk |
|--------|-------|-------|------|
| M1-S1 | Epic 0 | Foundation, Migration, **CrewAI Spike** | 🟢 Low |
| M1-S2 | Epic 1 | Intake & State Machine | 🟢 Low |
| M2-S1 | **Epic 2A** | Core Deliberation Protocol (happy path) | 🟡 Medium |
| M2-S2 | Epic 3, Epic 4 | ACK & REFER execution | 🟢 Low |
| M3-S1 | Epic 5, Epic 6, **Epic 2B** | Co-signing, Escalation, Edge Cases | 🟡 Medium |
| M3-S2 | Epic 7, Epic 8 | Engagement, Transcript Access, Metrics | 🟢 Low |

**Key De-risk Points:**
- CrewAI Spike in M1-S1 validates multi-agent feasibility before commitment
- Epic 2A proves collective judgment works before edge case investment
- Epic 2B can absorb scope if M2-S1 runs long
- Epic 7 transcript access depends on Epic 2B (not blocking M2)

## Grand Architect Rulings (Recorded)

| Ruling | Decision | Impact |
|--------|----------|--------|
| **Ruling-1** | Phase-level witness batching | FR-11.7 amended, Section 13A.7 added |
| **Ruling-2** | Tiered transcript access | Section 13A.8 added, Epic 7 stories added |
| **Ruling-3** | Similar petitions deferred to M2 | HP-12 created as P1, not blocking Epic 2A |
| **Ruling-4** | Epic 2 split into 2A/2B | De-risks M2, proves core before edge cases |

---

## Epic 0: Foundation & Migration

**Goal:** Enable all subsequent epics by migrating Story 7.2 and establishing infrastructure

**FRs Covered:** FR-9.1, FR-9.2, FR-9.3, FR-9.4
**Hidden Prerequisites:** HP-1, HP-2, HP-3, HP-4, HP-7, HP-8, HP-9, HP-10, HP-11

---

### Story 0.1: CrewAI Multi-Agent Feasibility Spike

As a **system architect**,
I want to validate that CrewAI can orchestrate 3 AI agents in a deliberation pattern,
So that we can commit to the Three Fates architecture with confidence.

**Acceptance Criteria:**

**Given** a test harness with CrewAI framework installed
**When** I configure 3 agents with distinct personas and a deliberation task
**Then** the agents produce sequential outputs (assess → position → vote)
**And** the output is deterministic given the same random seed
**And** total execution completes within 5 minutes
**And** a spike report documents findings and recommendations

**Technical Notes:**
- Timeboxed spike (2 days max)
- Creates no production tables
- Output: Go/No-Go decision for Epic 2A
- References: HP-10, HP-11, NFR-10.1, NFR-10.3

---

### Story 0.2: Petition Domain Model & Base Schema

As a **developer**,
I want the core petition domain model and database schema established,
So that subsequent stories can persist and query petitions.

**Acceptance Criteria:**

**Given** no existing petition tables in the database
**When** I run the migration
**Then** a `petitions` table is created with columns:
  - `id` (UUIDv7, primary key)
  - `type` (enum: GENERAL, CESSATION, GRIEVANCE, COLLABORATION)
  - `text` (text, max 10k chars)
  - `submitter_id` (UUID, foreign key to identities)
  - `state` (enum: RECEIVED, DELIBERATING, ACKNOWLEDGED, REFERRED, ESCALATED)
  - `content_hash` (bytea, Blake3 hash)
  - `created_at`, `updated_at` (timestamps)
**And** a `petition_state_enum` type exists
**And** the Petition domain model class exists in `src/domain/models/petition.py`
**And** unit tests verify model invariants

**References:** FR-2.2, HP-2

---

### Story 0.3: Story 7.2 Cessation Petition Migration

As a **system operator**,
I want existing Story 7.2 cessation_petition data migrated to the new petition schema,
So that existing functionality is preserved and all 98 tests pass.

**Acceptance Criteria:**

**Given** existing cessation_petition records in the legacy schema
**When** I run the migration script
**Then** all records are copied to the new `petitions` table with type=CESSATION
**And** existing `petition_id` values are preserved (FR-9.4)
**And** a dual-write adapter is enabled for the migration period (FR-9.3)
**And** all 98 existing Story 7.2 tests pass (FR-9.2)
**And** rollback script exists and is tested

**References:** FR-9.1, FR-9.2, FR-9.3, FR-9.4, NFR-8.1

---

### Story 0.4: Job Queue Infrastructure (Deadline Monitoring)

As a **developer**,
I want a job queue infrastructure for scheduling deadline monitoring jobs,
So that referral timeouts and deliberation timeouts can fire reliably.

**Acceptance Criteria:**

**Given** no existing job queue tables
**When** I run the migration
**Then** job queue tables are created (`scheduled_jobs`, `dead_letter_queue`)
**And** a job scheduler service exists that:
  - Polls for due jobs every 10 seconds
  - Processes jobs with at-least-once delivery
  - Moves failed jobs to dead-letter queue after 3 retries
  - Emits heartbeat metrics
**And** alerting is configured for dead-letter queue depth > 0
**And** integration tests verify job execution

**References:** HP-1, HC-6, NFR-7.5

---

### Story 0.5: Content Hashing Service (Blake3)

As a **developer**,
I want a content hashing service using Blake3,
So that petition text can be hashed for duplicate detection and witness integrity.

**Acceptance Criteria:**

**Given** petition text content
**When** I call the content hashing service
**Then** it returns a 32-byte Blake3 hash
**And** the same content always produces the same hash
**And** different content produces different hashes (collision resistance)
**And** the service is available as `ContentHashService` in application services
**And** unit tests verify hash consistency

**References:** HP-2, HC-5

---

### Story 0.6: Realm Registry & Routing

As a **developer**,
I want a realm registry with valid routing targets,
So that petitions can be referred to appropriate Knights by realm.

**Acceptance Criteria:**

**Given** no existing realm registry
**When** I run the migration
**Then** a `realms` table is created with:
  - `id` (UUID, primary key)
  - `name` (text, unique)
  - `knight_capacity` (integer, max concurrent referrals)
  - `is_active` (boolean)
**And** seed data includes at least 3 test realms
**And** a `RealmRegistry` service exists for querying valid realms
**And** sentinel-to-realm mapping is configurable (HP-4)

**References:** HP-3, HP-4, NFR-7.3

---

### Story 0.7: Archon Persona Definitions (Three Fates Pool)

As a **developer**,
I want Archon persona definitions for the Three Fates pool,
So that deliberation sessions can assign appropriate Marquis-rank Archons.

**Acceptance Criteria:**

**Given** the CrewAI spike was successful (Story 0.1)
**When** I create the Archon persona configuration
**Then** at least 5 Fate Archon personas are defined with:
  - Unique identifier
  - Persona name and title
  - Deliberation style (e.g., "constitutional purist", "pragmatic moderator")
  - System prompt template
**And** personas are stored in configuration (not database)
**And** an `ArchonPool` service can select 3 Archons for a deliberation
**And** selection is deterministic given the same seed

**References:** HP-11, FR-11.1

---

---

## Epic 1: Petition Intake & State Machine

**Goal:** Observers can submit petitions and track their status through the system

**FRs Covered:** FR-1.1-1.7, FR-2.1-2.6, FR-7.1, FR-7.4, FR-10.1
**NFRs:** NFR-1.1, NFR-1.2, NFR-2.1, NFR-3.1, NFR-4.1

---

### Story 1.1: Petition Submission REST Endpoint

As an **Observer**,
I want to submit a petition via REST API,
So that I can formally request system attention for my concern.

**Acceptance Criteria:**

**Given** I am an authenticated Observer
**When** I POST to `/api/v1/petitions` with valid payload:
  - `type`: one of GENERAL, CESSATION, GRIEVANCE, COLLABORATION
  - `text`: petition content (1-10,000 chars)
**Then** the system returns HTTP 201 with:
  - `petition_id` (UUIDv7)
  - `state`: RECEIVED
  - `created_at` timestamp
**And** the petition is persisted to the database
**And** a content hash is computed and stored (Blake3)
**And** response latency is < 200ms p99 (NFR-1.1)

**Given** I submit invalid payload (missing type, empty text, text > 10k)
**When** the request is processed
**Then** the system returns HTTP 400 with RFC 7807 error response

**References:** FR-1.1, FR-1.2, FR-1.3, FR-1.6, FR-10.1, NFR-1.1, D7, D9

---

### Story 1.2: Petition Received Event Emission

As a **system**,
I want to emit a PetitionReceived event when a petition is successfully submitted,
So that downstream systems can react to new petitions.

**Acceptance Criteria:**

**Given** a petition is successfully created (Story 1.1)
**When** the transaction commits
**Then** a `PetitionReceived` event is emitted containing:
  - `petition_id`
  - `type`
  - `submitter_id`
  - `content_hash`
  - `timestamp`
  - `schema_version` (D2)
**And** the event is persisted via EventWriterService
**And** the event is witnessed per CT-12

**References:** FR-1.7, D2, CT-12

---

### Story 1.3: Queue Overflow Protection (503 Response)

As a **system operator**,
I want the system to return HTTP 503 when the petition queue is overwhelmed,
So that no petitions are silently dropped.

**Acceptance Criteria:**

**Given** the system is under high load
**When** the pending petition count exceeds the configured threshold (default: 10,000)
**Then** new petition submissions return HTTP 503 Service Unavailable
**And** the response includes `Retry-After` header
**And** no petition data is lost (NFR-3.1)
**And** queue depth is exposed as a Prometheus metric

**Given** the queue depth drops below threshold
**When** new submissions arrive
**Then** normal processing resumes (HTTP 201)

**References:** FR-1.4, NFR-2.1, NFR-3.1, NFR-7.4

---

### Story 1.4: Submitter Rate Limiting

As a **system**,
I want to enforce rate limits per submitter,
So that no single identity can flood the petition queue.

**Acceptance Criteria:**

**Given** a submitter_id has submitted petitions
**When** they exceed the rate limit (10 petitions/hour, configurable)
**Then** subsequent submissions return HTTP 429 Too Many Requests
**And** the response includes:
  - `Retry-After` header
  - RFC 7807 error with `rate_limit_remaining` extension
**And** rate limit state is stored in PostgreSQL time-bucket counters (D4)

**Given** the rate limit window expires
**When** the submitter submits again
**Then** the submission is accepted normally

**References:** FR-1.5, HC-4, D4, NFR-5.1

---

### Story 1.5: State Machine Domain Model

As a **developer**,
I want a petition state machine that enforces valid transitions,
So that petitions can only move through legitimate states.

**Acceptance Criteria:**

**Given** a petition in state RECEIVED
**When** a transition is attempted
**Then** only these transitions are valid:
  - RECEIVED → DELIBERATING
  - RECEIVED → ACKNOWLEDGED (withdrawn)
**And** invalid transitions raise `InvalidStateTransition` exception

**Given** a petition in state DELIBERATING
**When** a transition is attempted
**Then** only these transitions are valid:
  - DELIBERATING → ACKNOWLEDGED
  - DELIBERATING → REFERRED
  - DELIBERATING → ESCALATED
**And** invalid transitions raise `InvalidStateTransition` exception

**Given** a petition in terminal state (ACKNOWLEDGED, REFERRED, ESCALATED)
**When** any transition is attempted
**Then** the system rejects with `PetitionAlreadyFated` exception

**And** all transition rules are documented in the state machine model
**And** unit tests cover all valid and invalid transition combinations

**References:** FR-2.1, FR-2.2, FR-2.3, FR-2.6

---

### Story 1.6: Atomic Fate Assignment (CAS)

As a **system**,
I want fate assignment to use atomic compare-and-swap,
So that no petition can ever have double-fate assignment.

**Acceptance Criteria:**

**Given** a petition in DELIBERATING state
**When** two concurrent fate assignments are attempted
**Then** exactly one succeeds
**And** the other fails with `ConcurrentModificationException`
**And** the successful assignment is persisted atomically
**And** no petition ever has more than one fate (NFR-3.2)

**Implementation:**
- Use PostgreSQL `UPDATE ... WHERE state = expected_state RETURNING *`
- Verify row count = 1 for success

**References:** FR-2.4, NFR-3.2

---

### Story 1.7: Fate Event Emission (Transactional)

As a **system**,
I want fate events emitted in the same transaction as state updates,
So that fate assignment and witnessing are atomic.

**Acceptance Criteria:**

**Given** a petition fate is being assigned
**When** the state transition succeeds
**Then** a fate event is emitted in the same database transaction:
  - `PetitionAcknowledged`, `PetitionReferred`, or `PetitionEscalated`
  - Contains: petition_id, previous_state, new_state, actor_id, timestamp, reason
**And** if the event emission fails, the state change is rolled back
**And** fate events are persisted via EventWriterService
**And** 100% of fate events are witnessed (NFR-3.3)

**References:** FR-2.5, NFR-3.3, HC-1

---

### Story 1.8: Petition Status Query Endpoint

As an **Observer**,
I want to query the status of my petition,
So that I can track its progress through the system.

**Acceptance Criteria:**

**Given** I have a valid petition_id
**When** I GET `/api/v1/petitions/{petition_id}`
**Then** the system returns HTTP 200 with:
  - `petition_id`
  - `type`
  - `state`
  - `co_signer_count` (FR-7.4)
  - `created_at`
  - `updated_at`
  - `fate_reason` (if terminal state)
**And** response latency is < 100ms p99 (NFR-1.2)

**Given** an invalid or non-existent petition_id
**When** I query the status
**Then** the system returns HTTP 404 with RFC 7807 error

**References:** FR-7.1, FR-7.4, NFR-1.2, D7

---

---

## Epic 2A: Core Deliberation Protocol (CRITICAL PATH)

**Goal:** Petitions receive collective deliberative judgment from Marquis-rank Archons (happy path)

**FRs Covered:** FR-11.1-11.6, FR-11.11
**NFRs:** NFR-10.1, NFR-10.2, NFR-10.5

---

### Story 2A.1: Deliberation Session Domain Model

As a **developer**,
I want a DeliberationSession aggregate that models the mini-Conclave,
So that deliberation state and transitions are properly encapsulated.

**Acceptance Criteria:**

**Given** no existing deliberation model
**When** I create the DeliberationSession aggregate
**Then** it contains:
  - `session_id` (UUIDv7)
  - `petition_id` (foreign key)
  - `assigned_archons` (array of 3 archon_ids)
  - `phase` (enum: ASSESS, POSITION, CROSS_EXAMINE, VOTE, COMPLETE)
  - `phase_transcripts` (map of phase → transcript hash)
  - `votes` (map of archon_id → disposition)
  - `outcome` (nullable: ACKNOWLEDGE, REFER, ESCALATE)
  - `created_at`, `completed_at`
**And** a database migration creates the `deliberation_sessions` table
**And** domain invariants are enforced:
  - Exactly 3 archons assigned
  - Phases progress in order
  - Outcome requires 2+ matching votes
**And** unit tests verify all invariants

**References:** FR-11.1, FR-11.4

---

### Story 2A.2: Archon Assignment Service

As a **system**,
I want to assign exactly 3 Marquis-rank Archons to deliberate each petition,
So that every petition receives collective judgment.

**Acceptance Criteria:**

**Given** a petition enters RECEIVED state
**When** the deliberation is initiated
**Then** the ArchonPool service selects exactly 3 Archons
**And** selection is deterministic given (petition_id + seed)
**And** selected Archons are from the configured Three Fates pool
**And** the assignment is recorded in the DeliberationSession

**Given** a petition_id that has already been assigned Archons
**When** assignment is attempted again
**Then** the system returns the existing assignment (idempotent)

**References:** FR-11.1, HP-11

---

### Story 2A.3: Deliberation Context Package Builder

As a **system**,
I want to build a context package for each deliberating Archon,
So that they have sufficient information to render judgment.

**Acceptance Criteria:**

**Given** a petition assigned for deliberation
**When** the context package is built
**Then** it contains:
  - Petition text (full)
  - Petition type (GENERAL, CESSATION, etc.)
  - Co-signer count (current)
  - Submitter metadata (anonymized identifier)
  - Submission timestamp
**And** the package is serialized as JSON
**And** the package does NOT include similar petitions (deferred to M2 per Ruling-3)

**References:** FR-11.3, Ruling-3

---

### Story 2A.4: Deliberation Protocol Orchestrator

As a **system**,
I want to orchestrate the 4-phase deliberation protocol,
So that Archons proceed through Assess → Position → Cross-Examine → Vote.

**Acceptance Criteria:**

**Given** a DeliberationSession with 3 assigned Archons
**When** deliberation begins
**Then** the orchestrator executes phases in sequence:

**Phase 1 - ASSESS:**
- Each Archon receives context package
- Each Archon produces independent assessment
- All assessments collected before proceeding

**Phase 2 - POSITION:**
- Each Archon states preferred disposition with rationale
- Positions are sequential (Archon 1 → 2 → 3)
- Each can see previous positions

**Phase 3 - CROSS_EXAMINE:**
- Archons may challenge each other's positions
- Maximum 3 rounds of exchange
- Ends when no Archon raises new challenge

**Phase 4 - VOTE:**
- Each Archon casts final vote: ACKNOWLEDGE, REFER, or ESCALATE
- Votes are simultaneous (no seeing others' votes)

**And** phase transitions are logged
**And** total deliberation completes within 5 minutes p95 (NFR-10.1)

**References:** FR-11.4, NFR-10.1

---

### Story 2A.5: CrewAI Deliberation Adapter

As a **developer**,
I want a CrewAI adapter that executes the deliberation protocol,
So that the Three Fates can deliberate using the AI framework.

**Acceptance Criteria:**

**Given** a DeliberationSession and context package
**When** the CrewAI adapter is invoked
**Then** it:
  - Instantiates 3 CrewAI agents with Archon personas
  - Executes the 4-phase protocol via CrewAI tasks
  - Collects outputs from each phase
  - Returns structured deliberation result
**And** each Archon response completes within 30 seconds p95 (NFR-10.2)
**And** the adapter uses deterministic seeding for reproducibility
**And** the adapter implements the `DeliberationPort` protocol

**References:** FR-11.4, HP-10, NFR-10.2

---

### Story 2A.6: Supermajority Consensus Resolution

As a **system**,
I want to resolve deliberation outcome via supermajority consensus,
So that 2-of-3 Archon agreement determines petition disposition.

**Acceptance Criteria:**

**Given** all 3 Archons have cast votes
**When** consensus is evaluated
**Then** the outcome is determined by:
  - If 2+ votes for ACKNOWLEDGE → outcome = ACKNOWLEDGE
  - If 2+ votes for REFER → outcome = REFER
  - If 2+ votes for ESCALATE → outcome = ESCALATE
  - If no 2+ agreement → no consensus (handled in Epic 2B)
**And** the outcome is recorded in DeliberationSession
**And** the minority vote is preserved for audit

**References:** FR-11.5, FR-11.6

---

### Story 2A.7: Phase-Level Witness Batching

As a **system**,
I want to witness deliberation at phase boundaries (not per-utterance),
So that auditability is maintained without witness volume explosion.

**Acceptance Criteria:**

**Given** a deliberation phase completes
**When** the phase is witnessed
**Then** a single witness event is emitted containing:
  - `session_id`
  - `phase` (ASSESS, POSITION, CROSS_EXAMINE, VOTE)
  - `transcript_hash` (Blake3 hash of full phase transcript)
  - `participating_archons` (array of 3 archon_ids)
  - `start_timestamp`, `end_timestamp`
  - `phase_metadata` (e.g., "positions_converged", "challenges_raised")
**And** the raw transcript is stored as content-addressed artifact
**And** the artifact is referenced by hash in the witness event
**And** 4 witness events are emitted per deliberation (one per phase)

**References:** FR-11.7 (clarified), Ruling-1, NFR-10.4

---

### Story 2A.8: Disposition Emission & Pipeline Routing

As a **system**,
I want to emit the deliberation outcome and route to the appropriate pipeline,
So that petitions proceed to their determined fate.

**Acceptance Criteria:**

**Given** a deliberation reaches consensus
**When** the outcome is finalized
**Then** the petition state transitions: DELIBERATING → [ACKNOWLEDGED|REFERRED|ESCALATED]
**And** a `DeliberationComplete` event is emitted with:
  - `petition_id`
  - `session_id`
  - `outcome`
  - `vote_breakdown` (3 votes)
  - `dissent_present` (boolean)
**And** the petition is routed to the appropriate pipeline:
  - ACKNOWLEDGED → Acknowledgment execution (Epic 3)
  - REFERRED → Knight referral queue (Epic 4)
  - ESCALATED → King escalation queue (Epic 6)

**References:** FR-11.11

---

---

## Epic 2B: Deliberation Edge Cases & Guarantees

**Goal:** Deliberation holds under stress with full auditability

**FRs Covered:** FR-11.7-11.10, FR-11.12
**NFRs:** NFR-10.3, NFR-10.4, NFR-10.6

---

### Story 2B.1: Dissent Recording Service

As a **system**,
I want to record dissenting opinions when deliberation votes are not unanimous,
So that minority perspectives are preserved for audit and governance review.

**Acceptance Criteria:**

**Given** a deliberation completes with a 2-1 vote
**When** the outcome is recorded
**Then** the dissenting Archon's vote and rationale are preserved in:
  - `dissent_archon_id`
  - `dissent_disposition` (what they voted for)
  - `dissent_rationale` (their reasoning text)
**And** the dissent is included in the `DeliberationComplete` event
**And** dissent records are queryable by petition_id and archon_id
**And** the dissent is hash-referenced for integrity

**Given** a deliberation completes with a 3-0 unanimous vote
**When** the outcome is recorded
**Then** no dissent record is created
**And** `dissent_present` flag is set to `false`

**References:** FR-11.8

---

### Story 2B.2: Deliberation Timeout Enforcement

As a **system**,
I want to enforce a 5-minute deliberation timeout with auto-ESCALATE,
So that no petition is held indefinitely in deliberation.

**Acceptance Criteria:**

**Given** a deliberation session has been in progress for 5 minutes (configurable)
**When** the timeout fires
**Then** the deliberation is terminated with outcome = ESCALATE
**And** the petition state transitions: DELIBERATING → ESCALATED
**And** a `DeliberationTimeout` event is emitted with:
  - `session_id`
  - `petition_id`
  - `elapsed_time`
  - `phase_at_timeout` (which phase was active)
  - `reason`: "TIMEOUT_EXCEEDED"
**And** the incomplete transcript is preserved
**And** the timeout is scheduled via the job queue (Story 0.4)

**Given** a deliberation completes before the timeout
**When** consensus is reached
**Then** the scheduled timeout job is cancelled
**And** no timeout event is emitted

**References:** FR-11.9, HC-7, NFR-10.1

---

### Story 2B.3: Deadlock Detection & Auto-Escalation

As a **system**,
I want to detect deliberation deadlock after 3 rounds and auto-ESCALATE,
So that petitions with irreconcilable positions are elevated appropriately.

**Acceptance Criteria:**

**Given** a deliberation reaches the VOTE phase
**When** no supermajority consensus exists (3-way split or persistent 2-1 disagreement)
**Then** a new CROSS_EXAMINE → VOTE round is initiated
**And** the round count is incremented

**Given** 3 voting rounds have completed without consensus
**When** the third round still shows no supermajority
**Then** the deliberation is terminated with outcome = ESCALATE
**And** the petition state transitions: DELIBERATING → ESCALATED
**And** a `DeliberationDeadlock` event is emitted with:
  - `session_id`
  - `petition_id`
  - `round_count`: 3
  - `vote_history` (all 3 rounds of votes)
  - `reason`: "DEADLOCK_MAX_ROUNDS"
**And** all round transcripts are preserved

**References:** FR-11.10

---

### Story 2B.4: Archon Substitution on Failure

As a **system**,
I want to substitute an Archon that fails mid-deliberation,
So that deliberation can complete even if one agent becomes unavailable.

**Acceptance Criteria:**

**Given** a deliberation is in progress
**When** an Archon fails to respond within 30 seconds (individual timeout)
**Then** the Archon is marked as `FAILED` in the session
**And** a substitute Archon is selected from the pool (excluding already-assigned)
**And** the substitute receives:
  - Full context package
  - Transcript of phases completed so far
**And** the substitution completes within 10 seconds (NFR-10.6)
**And** an `ArchonSubstituted` event is emitted

**Given** an Archon fails during the VOTE phase
**When** substitution occurs
**Then** the substitute casts a new vote
**And** the failed Archon's partial vote (if any) is discarded

**Given** 2+ Archons fail simultaneously
**When** substitution is attempted
**Then** the deliberation is terminated with ESCALATE
**And** `reason`: "INSUFFICIENT_ARCHONS"

**References:** NFR-10.6

---

### Story 2B.5: Transcript Preservation & Hash-Referencing

As a **system**,
I want all deliberation transcripts preserved with hash references,
So that the complete deliberation record can be verified for integrity.

**Acceptance Criteria:**

**Given** a deliberation phase completes
**When** the transcript is preserved
**Then** it is stored as a content-addressed blob with:
  - Full text of all utterances in the phase
  - Archon attribution for each utterance
  - Timestamps for each utterance
  - Phase metadata
**And** the blob is stored with its Blake3 hash as the key
**And** the hash is recorded in the phase witness event
**And** 100% of utterances are captured (NFR-10.4)

**Given** a transcript hash from a witness event
**When** I query the content store with that hash
**Then** the original transcript is retrieved
**And** recomputing the hash produces the same value (integrity verified)

**References:** FR-11.7, NFR-10.4

---

### Story 2B.6: Audit Trail Reconstruction

As an **auditor**,
I want to reconstruct the complete deliberation from the event log,
So that any deliberation can be replayed and verified.

**Acceptance Criteria:**

**Given** a completed deliberation session
**When** I query the audit reconstruction service with `session_id`
**Then** I receive a complete timeline:
  - Archon assignment event
  - Phase witness events (4)
  - Transcript content for each phase (retrieved by hash)
  - Dissent record (if any)
  - Final outcome event
**And** the timeline is chronologically ordered
**And** all events have valid witness signatures

**Given** a deliberation that ended in timeout or deadlock
**When** I reconstruct the audit trail
**Then** the partial progress is fully visible
**And** the termination reason is clear

**References:** FR-11.12, NFR-6.5

---

### Story 2B.7: Deliberation Load Testing Harness

As a **quality engineer**,
I want a load testing harness for concurrent deliberations,
So that we can verify the system handles 100+ simultaneous sessions.

**Acceptance Criteria:**

**Given** the load test harness is configured
**When** I run a load test with 100 concurrent deliberations
**Then** all deliberations complete successfully
**And** p95 end-to-end latency remains < 5 minutes (NFR-10.1)
**And** no petition is lost or double-fated
**And** resource utilization metrics are captured
**And** the harness generates a report with:
  - Success rate
  - Latency distribution
  - Resource consumption
  - Failure analysis (if any)

**References:** NFR-10.5, NFR-9.4

---

### Story 2B.8: Deliberation Chaos Testing

As a **quality engineer**,
I want chaos tests for deliberation failure scenarios,
So that we verify graceful handling of faults.

**Acceptance Criteria:**

**Given** the chaos test suite is configured
**When** I run the following failure scenarios:
**Then** each scenario is handled correctly:

**Scenario: Archon timeout mid-phase**
- Inject: One Archon stops responding
- Expected: Substitution occurs, deliberation completes

**Scenario: Deliberation service restart**
- Inject: Kill deliberation service container
- Expected: In-flight deliberations resume from last witness checkpoint

**Scenario: Database connection failure**
- Inject: Sever database connection for 30 seconds
- Expected: Retry policy engages, no data loss

**Scenario: CrewAI API degradation**
- Inject: 500ms latency to CrewAI calls
- Expected: Individual Archon timeouts trigger substitution, not full failure

**And** all chaos scenarios produce audit-friendly logs
**And** the chaos suite is integrated into CI (manual trigger)

**References:** NFR-9.3, NFR-9.5, NFR-3.6

---

---

## Epic 3: Acknowledgment Execution

**Goal:** System can formally acknowledge petitions with appropriate reason codes

**FRs Covered:** FR-3.1-3.6
**NFRs:** NFR-6.1, NFR-6.3

---

### Story 3.1: Acknowledgment Reason Code Enumeration

As a **developer**,
I want an enumerated list of acknowledgment reason codes,
So that all acknowledgments use standardized, auditable reasons.

**Acceptance Criteria:**

**Given** the acknowledgment domain model
**When** I define reason codes
**Then** the following enum values exist:
  - `ADDRESSED`: Concern has been or will be addressed
  - `NOTED`: Input has been recorded for consideration
  - `DUPLICATE`: Petition duplicates an existing or resolved petition
  - `OUT_OF_SCOPE`: Matter falls outside governance jurisdiction
  - `REFUSED`: Petition violates policy or norms
  - `NO_ACTION_WARRANTED`: After review, no action is appropriate
  - `WITHDRAWN`: Petitioner withdrew the petition
  - `EXPIRED`: Referral timeout with no Knight response
**And** the enum is stored in database as `acknowledgment_reason_enum`
**And** the enum is available in the domain model

**References:** FR-3.2

---

### Story 3.2: Acknowledgment Execution Service

As a **system**,
I want to execute acknowledgment when deliberation determines ACKNOWLEDGE fate,
So that petitions receive formal closure with proper documentation.

**Acceptance Criteria:**

**Given** a petition with deliberation outcome = ACKNOWLEDGE
**When** the acknowledgment is executed
**Then** the petition state transitions: DELIBERATING → ACKNOWLEDGED
**And** an `Acknowledgment` record is created with:
  - `petition_id`
  - `reason_code` (from deliberation recommendation)
  - `rationale` (if required by reason code)
  - `acknowledging_archon_ids` (the 2+ who voted ACKNOWLEDGE)
  - `acknowledged_at` timestamp
**And** a `PetitionAcknowledged` event is emitted
**And** the event is witnessed via EventWriterService

**Given** an acknowledgment is attempted on a non-DELIBERATING petition
**When** execution is attempted
**Then** the system rejects with `InvalidStateTransition` exception

**References:** FR-3.1, NFR-6.1

---

### Story 3.3: Rationale Requirement Enforcement

As a **system**,
I want to enforce mandatory rationale for certain reason codes,
So that REFUSED and NO_ACTION_WARRANTED decisions are properly justified.

**Acceptance Criteria:**

**Given** an acknowledgment with reason_code = REFUSED
**When** the acknowledgment is validated
**Then** `rationale` field must be non-empty (min 50 chars)
**And** validation fails if rationale is missing or too short

**Given** an acknowledgment with reason_code = NO_ACTION_WARRANTED
**When** the acknowledgment is validated
**Then** `rationale` field must be non-empty (min 50 chars)
**And** validation fails if rationale is missing or too short

**Given** an acknowledgment with reason_code = ADDRESSED, NOTED, or WITHDRAWN
**When** the acknowledgment is validated
**Then** `rationale` is optional (may be empty)

**And** the rationale is preserved in the acknowledgment record
**And** the rationale is included in the witness event

**References:** FR-3.3, NFR-6.3

---

### Story 3.4: Duplicate Petition Reference

As a **system**,
I want DUPLICATE acknowledgments to reference the original petition,
So that petitioners can track the canonical petition.

**Acceptance Criteria:**

**Given** an acknowledgment with reason_code = DUPLICATE
**When** the acknowledgment is validated
**Then** `reference_petition_id` must be provided
**And** the referenced petition must exist in the database
**And** validation fails if reference is missing or invalid

**Given** a valid DUPLICATE acknowledgment
**When** the acknowledgment is persisted
**Then** the `reference_petition_id` is stored
**And** the petitioner notification includes a link to the referenced petition

**References:** FR-3.4

---

### Story 3.5: Minimum Dwell Time Enforcement

As a **system**,
I want to enforce minimum dwell time before acknowledgment,
So that petitions receive adequate deliberation time.

**Acceptance Criteria:**

**Given** a petition that entered DELIBERATING state
**When** ACKNOWLEDGE outcome is determined
**Then** the system checks elapsed time since state entry
**And** if elapsed time < minimum dwell (30 seconds, configurable)
**Then** the acknowledgment is delayed until dwell time passes

**Given** a petition that has exceeded minimum dwell time
**When** ACKNOWLEDGE outcome is determined
**Then** acknowledgment executes immediately

**Note:** This prevents rushed deliberations while allowing the system to proceed naturally when adequate time has passed.

**References:** FR-3.5

---

### Story 3.6: Acknowledgment Rate Metrics

As a **governance observer**,
I want acknowledgment rate metrics tracked per Archon,
So that deliberation patterns can be monitored for quality.

**Acceptance Criteria:**

**Given** Archons participating in deliberations
**When** petitions are acknowledged
**Then** the system tracks per Archon:
  - Total deliberations participated
  - ACKNOWLEDGE votes cast
  - Acknowledgment rate (ACKNOWLEDGE / total)
**And** metrics are aggregated per time window (hourly, daily, weekly)
**And** metrics are exposed via Prometheus

**Given** an Archon's ACKNOWLEDGE rate exceeds threshold (70%, configurable)
**When** the monitoring system evaluates metrics
**Then** an alert is raised for governance review
**And** the alert includes archon_id and rate

**References:** FR-3.6, PREVENT-7

---

---

## Epic 4: Knight Referral Workflow

**Goal:** Domain experts can review and recommend on referred petitions

**FRs Covered:** FR-4.1-4.7
**NFRs:** NFR-3.4, NFR-4.4, NFR-7.3

---

### Story 4.1: Referral Domain Model & Schema

As a **developer**,
I want a Referral aggregate that models the Knight review workflow,
So that referral state and deadlines are properly tracked.

**Acceptance Criteria:**

**Given** no existing referral model
**When** I create the Referral aggregate
**Then** it contains:
  - `referral_id` (UUIDv7)
  - `petition_id` (foreign key)
  - `realm_id` (routing target)
  - `assigned_knight_id` (nullable until assignment)
  - `status` (enum: PENDING, ASSIGNED, IN_REVIEW, COMPLETED, EXPIRED)
  - `deadline` (timestamp)
  - `extensions_granted` (integer, max 2)
  - `recommendation` (nullable: ACKNOWLEDGE, ESCALATE)
  - `rationale` (text)
  - `created_at`, `completed_at`
**And** a database migration creates the `referrals` table
**And** unit tests verify domain invariants

**References:** FR-4.1, FR-4.2

---

### Story 4.2: Referral Execution Service

As a **system**,
I want to execute referral when deliberation determines REFER fate,
So that petitions are routed to domain expert Knights.

**Acceptance Criteria:**

**Given** a petition with deliberation outcome = REFER
**When** the referral is executed
**Then** the petition state transitions: DELIBERATING → REFERRED
**And** a `Referral` record is created with:
  - `petition_id`
  - `realm_id` (from deliberation recommendation)
  - `deadline` (now + 3 cycles, configurable)
  - `status` = PENDING
**And** a `PetitionReferred` event is emitted with realm_id
**And** the event is witnessed via EventWriterService
**And** a deadline job is scheduled in the job queue

**References:** FR-4.1, FR-4.2

---

### Story 4.3: Knight Decision Package

As a **Knight**,
I want to receive a decision package when assigned a referral,
So that I have sufficient context to review and recommend.

**Acceptance Criteria:**

**Given** a referral is assigned to a Knight
**When** the Knight queries their referral queue
**Then** they receive a decision package containing:
  - Petition text (full)
  - Petition type
  - Submitter metadata (anonymized)
  - Co-signer count
  - Deliberation summary (outcome, vote breakdown)
  - Referring Archons' rationale for REFER
  - Deadline timestamp
  - Extension status (remaining extensions)
**And** the package is available via GET `/api/v1/referrals/{referral_id}`
**And** only the assigned Knight can access the package

**References:** FR-4.3

---

### Story 4.4: Knight Recommendation Submission

As a **Knight**,
I want to submit my recommendation with mandatory rationale,
So that the petition can proceed to its final disposition.

**Acceptance Criteria:**

**Given** I am a Knight with an assigned referral
**When** I POST `/api/v1/referrals/{referral_id}/recommendation` with:
  - `recommendation`: ACKNOWLEDGE or ESCALATE
**Then** the referral status transitions: IN_REVIEW → COMPLETED
**And** the recommendation is recorded
**And** a `ReferralCompleted` event is emitted
**And** the petition proceeds based on recommendation:
  - ACKNOWLEDGE → execute acknowledgment (Epic 3)
  - ESCALATE → route to King escalation queue (Epic 6)

**Given** I submit without rationale or with insufficient rationale
**When** the request is validated
**Then** the system returns HTTP 400 with validation error

**References:** FR-4.6

---

### Story 4.5: Extension Request Handling

As a **Knight**,
I want to request deadline extensions (max 2),
So that I can properly review complex petitions.

**Acceptance Criteria:**

**Given** I have an assigned referral with extensions_granted < 2
**When** I POST `/api/v1/referrals/{referral_id}/extend` with:
  - `reason`: text explaining need for extension
**Then** the deadline is extended by 1 cycle
**And** `extensions_granted` is incremented
**And** a `ReferralExtended` event is emitted
**And** the deadline job is rescheduled

**Given** I have already used 2 extensions
**When** I request another extension
**Then** the system returns HTTP 400 with "MAX_EXTENSIONS_REACHED"

**References:** FR-4.4

---

### Story 4.6: Referral Timeout & Auto-Acknowledge

As a **system**,
I want to auto-ACKNOWLEDGE petitions when referral times out,
So that no petition is indefinitely stuck in referral.

**Acceptance Criteria:**

**Given** a referral deadline has passed
**When** the timeout job fires
**Then** the referral status transitions: (any) → EXPIRED
**And** the petition is acknowledged with:
  - `reason_code` = EXPIRED
  - `rationale` = "Referral to {realm} expired without Knight response"
**And** a `ReferralExpired` event is emitted
**And** a `PetitionAcknowledged` event is emitted
**And** 100% of timeouts fire reliably (NFR-3.4)

**Given** the Knight submits recommendation before timeout
**When** the deadline job fires
**Then** the job is cancelled (no-op)

**References:** FR-4.5, NFR-3.4

---

### Story 4.7: Knight Concurrent Referral Limit

As a **system**,
I want to enforce maximum concurrent referrals per Knight,
So that no Knight is overwhelmed with review workload.

**Acceptance Criteria:**

**Given** a Knight has concurrent referrals = max_concurrent (configurable per realm)
**When** the system attempts to assign another referral to this Knight
**Then** the assignment is deferred to another eligible Knight in the realm
**And** if no eligible Knights available, the referral remains PENDING

**Given** a Knight completes or expires a referral
**When** their concurrent count drops below max
**Then** they become eligible for new assignments

**And** concurrent referral counts are tracked per Knight
**And** the limit is configurable per realm via RealmRegistry

**References:** FR-4.7, NFR-7.3

---

---

## Epic 5: Co-signing & Auto-Escalation

**Goal:** Seekers can collectively support petitions, triggering auto-escalation at thresholds

**FRs Covered:** FR-5.1-5.3, FR-6.1-6.6, FR-10.2, FR-10.3
**NFRs:** NFR-1.3, NFR-1.4, NFR-2.2, NFR-3.5, NFR-5.2

---

### Story 5.1: Co-Sign Domain Model & Schema

As a **developer**,
I want a CoSignRequest aggregate that models petition support,
So that co-signer relationships and counts are properly tracked.

**Acceptance Criteria:**

**Given** no existing co-sign model
**When** I create the CoSignRequest aggregate
**Then** it contains:
  - `co_sign_id` (UUIDv7)
  - `petition_id` (foreign key)
  - `signer_id` (foreign key to identities)
  - `signed_at` (timestamp)
**And** a database migration creates the `co_signs` table
**And** a unique constraint exists on (petition_id, signer_id)
**And** an index exists on petition_id for count queries
**And** unit tests verify domain invariants

**References:** FR-6.2

---

### Story 5.2: Co-Sign Submission Endpoint

As a **Seeker**,
I want to co-sign an active petition,
So that I can add my support to the petitioner's cause.

**Acceptance Criteria:**

**Given** I am an authenticated Seeker
**When** I POST `/api/v1/petitions/{petition_id}/co-sign`
**Then** the system creates a co-sign record
**And** the co-signer count is incremented atomically (FR-6.4)
**And** response includes updated `co_signer_count`
**And** response latency is < 150ms p99 (NFR-1.3)

**Given** I have already co-signed this petition
**When** I attempt to co-sign again
**Then** the system returns HTTP 409 Conflict with "ALREADY_SIGNED"

**Given** the petition is in a terminal state (fated)
**When** I attempt to co-sign
**Then** the system returns HTTP 400 with "PETITION_ALREADY_FATED"

**References:** FR-6.1, FR-6.3, FR-6.4, NFR-1.3

---

### Story 5.3: Identity Verification for Co-Sign

As a **system**,
I want to verify signer identity before accepting co-signs,
So that only legitimate identities can support petitions.

**Acceptance Criteria:**

**Given** a co-sign request with valid authenticated identity
**When** the request is processed
**Then** the signer_id is verified against the identity store
**And** the co-sign is accepted

**Given** a co-sign request with invalid or suspended identity
**When** the request is processed
**Then** the system returns HTTP 403 Forbidden
**And** the co-sign is rejected

**References:** NFR-5.2

---

### Story 5.4: SYBIL-1 Rate Limiting

As a **system**,
I want to apply SYBIL-1 rate limiting per signer,
So that no identity can flood petitions with coordinated co-signs.

**Acceptance Criteria:**

**Given** a signer_id has co-signed petitions
**When** they exceed the rate limit (50 co-signs/hour, configurable)
**Then** subsequent co-signs return HTTP 429 Too Many Requests
**And** the response includes:
  - `Retry-After` header
  - RFC 7807 error with `rate_limit_remaining` extension
**And** rate limit state uses PostgreSQL time-bucket counters (D4)

**Given** a signer's co-sign rate appears coordinated (burst pattern)
**When** the fraud detector evaluates the pattern
**Then** an alert is raised for governance review
**And** the signer may be temporarily blocked pending review

**References:** FR-6.6, HP-9

---

### Story 5.5: Escalation Threshold Checking

As a **system**,
I want to check escalation thresholds on each co-sign,
So that petitions are automatically escalated when thresholds are reached.

**Acceptance Criteria:**

**Given** a CESSATION petition with co_signer_count = 99
**When** the 100th co-sign is processed
**Then** the escalation threshold is detected (100 for CESSATION)
**And** the auto-escalation workflow is triggered

**Given** a GRIEVANCE petition with co_signer_count = 49
**When** the 50th co-sign is processed
**Then** the escalation threshold is detected (50 for GRIEVANCE)
**And** the auto-escalation workflow is triggered

**Given** a GENERAL or COLLABORATION petition
**When** co-signs are processed
**Then** no auto-escalation threshold applies
**And** petition proceeds through normal deliberation

**And** threshold detection latency is < 1 second (NFR-1.4)

**References:** FR-5.2, FR-6.5, FR-10.2, FR-10.3, NFR-1.4

---

### Story 5.6: Auto-Escalation Execution

As a **system**,
I want to execute auto-escalation when co-signer threshold is reached,
So that petitions with collective support bypass deliberation.

**Acceptance Criteria:**

**Given** a petition reaches its escalation threshold
**When** auto-escalation executes
**Then** the petition state transitions: RECEIVED → ESCALATED (bypasses DELIBERATING)
**And** an `EscalationTriggered` event is emitted with:
  - `petition_id`
  - `trigger_type`: "CO_SIGNER_THRESHOLD"
  - `co_signer_count` (at time of trigger)
  - `threshold` (the threshold that was reached)
**And** the event is witnessed via EventWriterService
**And** the petition is routed to King escalation queue

**Given** auto-escalation is triggered
**When** the petition was already in DELIBERATING state
**Then** the deliberation is cancelled gracefully
**And** a `DeliberationCancelled` event is emitted with reason "AUTO_ESCALATED"

**References:** FR-5.1, FR-5.3

---

### Story 5.7: Co-Signer Deduplication Enforcement

As a **system**,
I want zero duplicate co-signatures,
So that co-signer counts accurately reflect unique supporters.

**Acceptance Criteria:**

**Given** concurrent co-sign requests from the same signer for the same petition
**When** both requests are processed
**Then** exactly one co-sign is created (database unique constraint)
**And** the second request receives HTTP 409 Conflict
**And** co_signer_count reflects exactly one signature

**And** deduplication is enforced at database level (unique constraint)
**And** 0 duplicate signatures ever exist (NFR-3.5)

**References:** FR-6.2, NFR-3.5

---

### Story 5.8: Co-Signer Count Scalability

As a **system**,
I want to support 100,000+ co-signers per petition,
So that popular petitions can accumulate mass support.

**Acceptance Criteria:**

**Given** a petition with 100,000 co-signers
**When** count queries are executed
**Then** response latency remains < 100ms p99
**And** co-sign insertion remains < 150ms p99

**Given** load testing with 100k co-signers
**When** the test completes
**Then** all co-signs are persisted correctly
**And** count is accurate
**And** no database timeouts occur

**Implementation Notes:**
- Use materialized count or counter table for read performance
- Batch count updates if needed for write performance

**References:** NFR-2.2

---

---

## Epic 6: King Escalation & Adoption Bridge

**Goal:** Kings can adopt petitions as Motions, bridging external voice to internal governance

**FRs Covered:** FR-5.4-5.8
**NFRs:** NFR-4.5, NFR-8.3

---

### Story 6.1: King Escalation Queue

As a **King**,
I want to access my escalation queue distinct from organic Motions,
So that I can review petitions that require my attention.

**Acceptance Criteria:**

**Given** I am an authenticated King
**When** I GET `/api/v1/kings/{king_id}/escalations`
**Then** I receive a paginated list of escalated petitions assigned to my realm
**And** the list is distinct from my organic Motion queue
**And** each entry includes:
  - `petition_id`
  - `petition_type`
  - `escalation_source` (DELIBERATION, CO_SIGNER_THRESHOLD, KNIGHT_RECOMMENDATION)
  - `co_signer_count`
  - `escalated_at` timestamp
**And** pagination uses keyset cursors (D8)

**Given** no escalations are pending for my realm
**When** I query the escalation queue
**Then** I receive an empty list (not an error)

**References:** FR-5.4

---

### Story 6.2: Escalation Decision Package

As a **King**,
I want to receive a complete decision package for each escalation,
So that I have sufficient context to decide on adoption or acknowledgment.

**Acceptance Criteria:**

**Given** an escalation in my queue
**When** I GET `/api/v1/escalations/{petition_id}`
**Then** I receive a decision package containing:
  - Petition text (full)
  - Petition type
  - Submitter metadata (anonymized)
  - Full co-signer list (paginated)
  - Escalation history:
    - Deliberation transcript (if deliberation occurred)
    - Vote breakdown (if deliberation occurred)
    - Knight recommendation (if referral occurred)
  - Escalation trigger details
**And** the package is only accessible to the assigned King

**References:** FR-5.4

---

### Story 6.3: Petition Adoption (Creates Motion)

As a **King**,
I want to ADOPT an escalated petition and create a Motion,
So that the petition's concern enters the formal governance process.

**Acceptance Criteria:**

**Given** I am reviewing an escalated petition
**When** I POST `/api/v1/escalations/{petition_id}/adopt` with:
  - `motion_title`: title for the new Motion
  - `motion_body`: body text (may include petition text)
  - `adoption_rationale`: why I'm adopting this petition
**Then** a new Motion is created with:
  - `source_petition_ref` pointing to the original petition (FR-5.7)
  - `sponsor_id` = my King identity
  - Motion state = DRAFT (ready for formal introduction)
**And** the petition state remains ESCALATED (terminal)
**And** a `PetitionAdopted` event is emitted
**And** the event is witnessed via EventWriterService

**References:** FR-5.5, FR-5.7

---

### Story 6.4: Adoption Budget Consumption

As a **system**,
I want adoption to consume promotion budget atomically,
So that H1 budget constraints are enforced for adopted Motions.

**Acceptance Criteria:**

**Given** a King has remaining promotion budget
**When** they adopt a petition
**Then** the budget is decremented atomically with Motion creation
**And** the budget consumption is durable (survives restart)
**And** if budget is insufficient, adoption fails with "INSUFFICIENT_BUDGET"

**Given** a King has zero remaining budget
**When** they attempt to adopt a petition
**Then** the system returns HTTP 400 with "INSUFFICIENT_BUDGET"
**And** the petition remains in escalation queue

**And** budget consumption uses existing PromotionBudgetStore
**And** consumption is atomic with Motion creation (same transaction)

**References:** FR-5.6, NFR-4.5, NFR-8.3

---

### Story 6.5: Escalation Acknowledgment by King

As a **King**,
I want to ACKNOWLEDGE an escalation with rationale,
So that I can formally decline adoption while respecting the petitioners.

**Acceptance Criteria:**

**Given** I am reviewing an escalated petition
**When** I POST `/api/v1/escalations/{petition_id}/acknowledge` with:
  - `reason_code`: from acknowledgment enum (ADDRESSED, NOTED, OUT_OF_SCOPE, etc.)
  - `rationale`: mandatory explanation (min 100 chars)
**Then** the petition is acknowledged (uses Epic 3 acknowledgment service)
**And** the acknowledgment records `acknowledged_by_king_id`
**And** a `KingAcknowledgedEscalation` event is emitted
**And** the rationale is preserved for petitioner visibility

**Given** I acknowledge without sufficient rationale
**When** the request is validated
**Then** the system returns HTTP 400 with validation error

**References:** FR-5.8

---

### Story 6.6: Adoption Provenance Immutability

As an **auditor**,
I want adoption provenance to be immutable,
So that the link between Motion and source petition cannot be altered.

**Acceptance Criteria:**

**Given** a Motion created via adoption
**When** any update is attempted on `source_petition_ref`
**Then** the update is rejected with "IMMUTABLE_FIELD"
**And** the original reference remains intact

**Given** a Motion with `source_petition_ref`
**When** the source petition is queried
**Then** the petition shows `adopted_as_motion_id` back-reference

**And** immutability is enforced at database level (trigger or constraint)
**And** provenance is visible in both directions

**References:** FR-5.7, NFR-6.2

---

---

## Epic 7: Observer Engagement

**Goal:** Observers receive notifications, can withdraw petitions, and access mediated deliberation artifacts

**FRs Covered:** FR-7.2, FR-7.3, FR-7.5
**NFRs:** NFR-1.2
**Special Stories (per Ruling-2):** Transcript Access Mediation, Phase Summary Generation

---

### Story 7.1: Status Token for Long-Poll

As an **Observer**,
I want to receive a status_token for efficient long-polling,
So that I can efficiently wait for petition state changes.

**Acceptance Criteria:**

**Given** I query my petition status
**When** the response is returned
**Then** it includes a `status_token` (opaque string)
**And** the token encodes the current state version

**Given** I have a status_token
**When** I GET `/api/v1/petitions/{petition_id}/status?token={status_token}`
**Then** the request blocks until state changes (max 30 seconds)
**And** if state changed, returns new status with new token
**And** if timeout, returns HTTP 304 Not Modified with same token

**And** long-poll connections are efficiently managed (no busy-wait)
**And** response latency on change is < 100ms p99 (NFR-1.2)

**References:** FR-7.2, NFR-1.2

---

### Story 7.2: Fate Assignment Notification

As an **Observer**,
I want to be notified when my petition receives its fate,
So that I know the outcome without polling.

**Acceptance Criteria:**

**Given** I submitted a petition and provided notification preferences
**When** the petition is fated (ACKNOWLEDGED, REFERRED, or ESCALATED)
**Then** I receive a notification containing:
  - `petition_id`
  - `fate` (the terminal state)
  - `fate_reason` (if ACKNOWLEDGED)
  - `fate_timestamp`
  - Link to view full details
**And** notification is delivered via configured channel (email, webhook, in-app)

**Given** I have a long-poll connection open
**When** the petition is fated
**Then** the long-poll returns immediately with the new state

**References:** FR-7.3

---

### Story 7.3: Petition Withdrawal

As an **Observer**,
I want to withdraw my petition before fate assignment,
So that I can cancel my petition if circumstances change.

**Acceptance Criteria:**

**Given** I submitted a petition that is not yet fated
**When** I POST `/api/v1/petitions/{petition_id}/withdraw` with:
  - `reason`: optional explanation
**Then** the petition is acknowledged with:
  - `reason_code` = WITHDRAWN
  - `rationale` = my provided reason (or "Petitioner withdrew")
**And** the petition state transitions to ACKNOWLEDGED
**And** a `PetitionWithdrawn` event is emitted
**And** co-signers are notified of withdrawal

**Given** my petition is already fated
**When** I attempt to withdraw
**Then** the system returns HTTP 400 with "PETITION_ALREADY_FATED"

**Given** I am not the original petitioner
**When** I attempt to withdraw
**Then** the system returns HTTP 403 Forbidden

**References:** FR-7.5

---

### Story 7.4: Transcript Access Mediation Service

As an **Observer**,
I want mediated access to deliberation artifacts,
So that I can understand how my petition was deliberated without ambient transcript access.

**Acceptance Criteria:**

**Given** my petition has completed deliberation
**When** I GET `/api/v1/petitions/{petition_id}/deliberation-summary`
**Then** I receive a mediated summary containing:
  - Deliberation outcome (ACKNOWLEDGE, REFER, ESCALATE)
  - Vote breakdown (2-1 or 3-0, without individual Archon identification)
  - Dissent indicator (boolean: was there a dissenting vote?)
  - Phase summaries (high-level, not raw transcripts)
  - Duration of deliberation
**And** I do NOT receive:
  - Raw transcript text
  - Individual Archon identities
  - Verbatim utterances

**Given** my petition was auto-escalated (bypassed deliberation)
**When** I query deliberation summary
**Then** the response indicates "NO_DELIBERATION" with escalation trigger details

**References:** Ruling-2 (Tiered Transcript Access), Section 13A.8

---

### Story 7.5: Phase Summary Generation

As a **system**,
I want to generate phase summaries for Observer consumption,
So that deliberation transparency is maintained without raw transcript exposure.

**Acceptance Criteria:**

**Given** a deliberation phase completes
**When** the phase summary is generated
**Then** it includes:
  - Phase name (ASSESS, POSITION, CROSS_EXAMINE, VOTE)
  - Phase duration
  - Key themes identified (extracted keywords/topics)
  - Convergence indicator (did positions align?)
  - Challenge count (for CROSS_EXAMINE phase)
**And** the summary is stored alongside the phase witness event
**And** the summary is derived from transcript but contains no verbatim quotes

**Given** an Observer requests deliberation summary
**When** summaries are assembled
**Then** all 4 phase summaries are included in chronological order

**References:** Ruling-2, Section 13A.8

---

### Story 7.6: Governance Transcript Access (Elevated)

As a **High Archon or auditor**,
I want full transcript access for governance review,
So that I can perform quality oversight of deliberations.

**Acceptance Criteria:**

**Given** I have HIGH_ARCHON or AUDITOR role
**When** I GET `/api/v1/deliberations/{session_id}/transcript`
**Then** I receive the complete transcript including:
  - All utterances with Archon attribution
  - Timestamps for each utterance
  - Phase boundaries
  - Raw dissent text
**And** my access is logged for audit purposes

**Given** I have OBSERVER or SEEKER role
**When** I attempt to access full transcript
**Then** the system returns HTTP 403 Forbidden
**And** I am directed to the mediated summary endpoint

**References:** Ruling-2 (Tiered Access), Section 13A.8

---

---

## Epic 8: Legitimacy Metrics & Governance

**Goal:** High Archon can monitor system health and petition responsiveness

**FRs Covered:** FR-8.1-8.5, FR-10.4
**NFRs:** NFR-1.5, NFR-7.1, NFR-7.2, NFR-5.6

---

### Story 8.1: Legitimacy Decay Metric Computation

As a **system**,
I want to compute legitimacy decay metrics per governance cycle,
So that petition responsiveness can be quantified and monitored.

**Acceptance Criteria:**

**Given** a governance cycle completes
**When** the legitimacy metric job runs
**Then** it computes:
  - `total_petitions`: count of petitions received this cycle
  - `fated_petitions`: count of petitions that reached terminal state within SLA
  - `legitimacy_score`: fated_petitions / total_petitions (0.0 to 1.0)
  - `average_time_to_fate`: mean duration from RECEIVED to terminal
  - `median_time_to_fate`: median duration
**And** the metrics are stored in `legitimacy_metrics` table
**And** computation completes within 60 seconds (NFR-1.5)
**And** metrics are exposed via Prometheus

**References:** FR-8.1, FR-8.2, NFR-1.5

---

### Story 8.2: Legitimacy Decay Alerting

As a **system operator**,
I want alerts when legitimacy score drops below threshold,
So that governance health issues are promptly addressed.

**Acceptance Criteria:**

**Given** legitimacy score is computed
**When** the score falls below 0.85 (configurable threshold)
**Then** an alert is raised containing:
  - Current score
  - Threshold breached
  - Cycle identifier
  - Count of stuck petitions
**And** the alert is delivered to configured channels (PagerDuty, Slack, email)
**And** alert severity is WARNING at 0.85, CRITICAL at 0.70

**Given** legitimacy score recovers above threshold
**When** the next cycle computes
**Then** a recovery notification is sent
**And** the alert is auto-resolved

**References:** FR-8.3, NFR-7.2

---

### Story 8.3: Orphan Petition Detection

As a **system**,
I want to identify petitions stuck in RECEIVED state,
So that processing failures are detected and remediated.

**Acceptance Criteria:**

**Given** the orphan detection job runs (daily)
**When** petitions are analyzed
**Then** petitions in RECEIVED state for > 24 hours are flagged as orphans
**And** an `OrphanPetitionsDetected` event is emitted with:
  - Count of orphans
  - List of petition_ids
  - Age of oldest orphan
**And** orphans are visible in the legitimacy dashboard
**And** 100% of orphans are detected (NFR-7.1)

**Given** orphan petitions exist
**When** the alert fires
**Then** operators can manually trigger re-processing
**And** the system attempts to initiate deliberation for each orphan

**References:** FR-8.5, NFR-7.1

---

### Story 8.4: High Archon Legitimacy Dashboard

As a **High Archon**,
I want access to a legitimacy dashboard,
So that I can monitor petition system health and responsiveness.

**Acceptance Criteria:**

**Given** I am authenticated as High Archon
**When** I access GET `/api/v1/governance/legitimacy`
**Then** I receive dashboard data containing:
  - Current cycle legitimacy score
  - Historical trend (last 10 cycles)
  - Petitions by state (count per state)
  - Orphan petition count
  - Average/median time-to-fate
  - Deliberation metrics (consensus rate, timeout rate, deadlock rate)
  - Archon acknowledgment rates (per Archon)
**And** data refreshes every 5 minutes

**Given** I do not have HIGH_ARCHON role
**When** I attempt to access the dashboard
**Then** the system returns HTTP 403 Forbidden

**References:** FR-8.4, NFR-5.6

---

### Story 8.5: META Petition Routing

As a **system**,
I want META petitions (about the petition system itself) routed to High Archon,
So that system-level concerns receive appropriate attention.

**Acceptance Criteria:**

**Given** a petition is submitted with type = META (or detected as meta-concern)
**When** the petition is processed
**Then** it bypasses normal deliberation
**And** it is routed directly to High Archon queue
**And** a `MetaPetitionReceived` event is emitted

**Given** a High Archon reviews a META petition
**When** they decide on disposition
**Then** they can:
  - ACKNOWLEDGE with rationale
  - Create a governance action item
  - Forward to specific governance body

**Note:** META petition detection may use keyword matching or explicit type selection.

**References:** FR-10.4

---

### Story 8.6: Adoption Ratio Monitoring (PREVENT-7)

As a **governance observer**,
I want adoption ratio monitored per realm,
So that excessive petition-to-Motion conversion is detected.

**Acceptance Criteria:**

**Given** Kings are adopting petitions as Motions
**When** the adoption ratio exceeds 50% for a realm (within a cycle)
**Then** an alert is raised for governance review
**And** the alert includes:
  - Realm identifier
  - Adoption count vs escalation count
  - Adopting King identities
  - Trend comparison to previous cycles

**Given** the ratio normalizes below threshold
**When** the next cycle completes
**Then** the alert is auto-resolved

**And** adoption metrics are visible in legitimacy dashboard

**References:** PREVENT-7

---

### Story 8.7: Realm Health Aggregate

As a **developer**,
I want a RealmHealth aggregate that tracks per-realm petition metrics,
So that realm-level health can be monitored and compared.

**Acceptance Criteria:**

**Given** petition activity occurs across realms
**When** metrics are computed
**Then** each realm has:
  - `realm_id`
  - `petitions_received` (this cycle)
  - `petitions_fated` (this cycle)
  - `referrals_pending`
  - `referrals_expired`
  - `escalations_pending`
  - `adoption_rate`
  - `average_referral_duration`
**And** the aggregate is stored in `realm_health` table
**And** the aggregate is queryable via API for governance review

**References:** FR-8.1, HP-7

---

---

## Final Validation Summary

### Story Count by Epic

| Epic | Stories | FRs Covered |
|------|---------|-------------|
| Epic 0: Foundation & Migration | 7 | FR-9.1-9.4 + HPs |
| Epic 1: Petition Intake & State Machine | 8 | FR-1.1-1.7, FR-2.1-2.6, FR-7.1, FR-7.4, FR-10.1 |
| Epic 2A: Core Deliberation Protocol | 8 | FR-11.1-11.6, FR-11.11 |
| Epic 2B: Edge Cases & Guarantees | 8 | FR-11.7-11.10, FR-11.12 |
| Epic 3: Acknowledgment Execution | 6 | FR-3.1-3.6 |
| Epic 4: Knight Referral Workflow | 7 | FR-4.1-4.7 |
| Epic 5: Co-signing & Auto-Escalation | 8 | FR-5.1-5.3, FR-6.1-6.6, FR-10.2, FR-10.3 |
| Epic 6: King Escalation & Adoption | 6 | FR-5.4-5.8 |
| Epic 7: Observer Engagement | 6 | FR-7.2, FR-7.3, FR-7.5 + Ruling-2 |
| Epic 8: Legitimacy Metrics & Governance | 7 | FR-8.1-8.5, FR-10.4 |
| **Total** | **71** | **70 FRs** |

### FR Coverage Verification

**All 70 Functional Requirements are covered:**

- FR-1.x (Petition Intake): 7/7 ✅
- FR-2.x (State Machine): 6/6 ✅
- FR-3.x (Acknowledgment): 6/6 ✅
- FR-4.x (Referral): 7/7 ✅
- FR-5.x (Escalation): 8/8 ✅
- FR-6.x (Co-signer): 6/6 ✅
- FR-7.x (Status/Visibility): 5/5 ✅
- FR-8.x (Legitimacy Decay): 5/5 ✅
- FR-9.x (Migration): 4/4 ✅
- FR-10.x (Petition Types): 4/4 ✅
- FR-11.x (Deliberation): 12/12 ✅

### NFR Coverage Verification

**Critical NFRs addressed in stories:**

- NFR-1.x (Performance): Stories 1.1, 1.8, 5.2, 7.1, 8.1 ✅
- NFR-2.x (Scalability): Stories 1.3, 5.8 ✅
- NFR-3.x (Reliability): Stories 1.3, 1.6, 1.7, 4.6, 5.7 ✅
- NFR-4.x (Durability): Stories 6.4 ✅
- NFR-5.x (Security): Stories 1.4, 5.3, 5.4 ✅
- NFR-6.x (Auditability): Stories 2B.6, 3.2, 6.6 ✅
- NFR-7.x (Operability): Stories 0.4, 8.2, 8.3 ✅
- NFR-8.x (Compatibility): Stories 0.3 ✅
- NFR-9.x (Testability): Stories 2B.7, 2B.8 ✅
- NFR-10.x (Deliberation): Stories 2A.4-2A.7, 2B.1-2B.5 ✅

### Grand Architect Rulings Applied

| Ruling | Implementation |
|--------|----------------|
| Ruling-1: Phase-level witness batching | Story 2A.7 |
| Ruling-2: Tiered transcript access | Stories 7.4, 7.5, 7.6 |
| Ruling-3: Similar petitions deferred to M2 | Story 2A.3 (explicitly excludes) |
| Ruling-4: Epic 2 split into 2A/2B | Epic structure |

### Hidden Prerequisites Addressed

- HP-1: Job Queue → Story 0.4
- HP-2: Content Hashing → Story 0.5
- HP-3: Realm Registry → Story 0.6
- HP-4: Sentinel-to-realm mapping → Story 0.6
- HP-7: Read Model Projections → Story 8.7
- HP-10: CrewAI Integration → Story 0.1, 2A.5
- HP-11: Archon Personas → Story 0.7

### Hardening Controls Addressed

- HC-1: Fate witness requirement → Story 1.7
- HC-4: Rate limiting → Story 1.4
- HC-5: Duplicate detection → Story 0.5
- HC-6: Dead-letter alerting → Story 0.4
- HC-7: Deliberation timeout → Story 2B.2
- PREVENT-7: Adoption ratio alert → Story 8.6

---

**Document Status:** Step 4 Complete - Validated & Ready for Implementation
