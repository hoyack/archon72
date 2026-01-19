---
stepsCompleted: [1, 2, 3]
inputDocuments: []
workflowType: 'architecture'
project_name: 'Petition System'
user_name: 'Grand Architect'
date: '2026-01-18'
---

# Architecture Decision Document - Petition System

_This document builds collaboratively through step-by-step discovery. Sections are appended as we work through each architectural decision together._

---

## Project Context Analysis

_Enhanced through 15 elicitation methods across 3 rounds_

### Executive Summary

The Petition System is a constitutional subsystem for Archon 72 that handles external claims on realm attention. Every petition terminates in exactly one of **Three Fates**: ACKNOWLEDGED, REFERRED, or ESCALATED.

| Metric | Value |
|--------|-------|
| Functional Requirements | 58 (P0: 37, P1: 20, P2: 1) |
| Non-Functional Requirements | 47 (Critical: 12) |
| Milestones | 4 (progressive delivery) |
| Architecture Decisions | 5 |
| Constraints | 37 (across 7 categories) |
| Hardening Controls | 58 |
| Quality Scenarios | 26 |
| Interface Contracts | 7 |

---

### Constitutional Truths (Inviolable)

| ID | Truth | Architectural Impact |
|----|-------|---------------------|
| **AT-1** | Every petition terminates in exactly one of Three Fates | Exhaustive, mutually exclusive state machine |
| **AT-2** | Silence has measurable cost (CT-14) | Responsiveness scoring is first-class citizen |
| **AT-3** | Claims are witnessed before processing (CT-12) | Event sourcing mandatory |
| **AT-4** | Agenda is scarce (CT-11) | H1 budget limits King adoption |
| **AT-5** | Petitions are external; Motions are internal | King adoption bridge is only crossing |

---

### Architecture Decisions

| ID | Decision | Rationale |
|----|----------|-----------|
| **ARCH-1** | Hybrid event sourcing (direct state + transactional events) | Balance auditability and query performance |
| **ARCH-2** | Atomic co-sign + escalation transactions | Prevent partial state during multi-party operations |
| **ARCH-3** | PostgreSQL table-based job scheduler | Leverage existing infrastructure, avoid operational complexity |
| **ARCH-4** | Tiered anti-Sybil (per-petition → per-realm → global) | Progressive complexity aligned with milestones |
| **ARCH-5** | Responsiveness score over legitimacy decay | Positive framing, clearer semantics |

---

### Design Principles

1. **Fail-Safe Defaults**: Unknown states → RECEIVED (not terminal)
2. **Defense in Depth**: Multiple validation layers before fate assignment
3. **Audit Everything**: No state change without witnessed event
4. **Graceful Degradation**: Job queue failure → manual processing path
5. **Separation of Concerns**: Petition lifecycle ≠ Motion lifecycle
6. **Idempotency**: All fate transitions safely retriable
7. **Least Privilege**: Co-signers can only co-sign, not initiate
8. **Rate Limiting by Design**: Built into every external endpoint
9. **Progressive Enhancement**: M1 works standalone, M2+ adds features
10. **Observable by Default**: Metrics, logs, traces on all critical paths
11. **Constitutional Compliance First**: FR/NFR conflicts resolved by Constitution

---

### Quality Attribute Priority

| Rank | Attribute | Score | Tier |
|------|-----------|-------|------|
| 1 | Reliability | 8.40 | ★★★ |
| 2 | Security | 8.15 | ★★★ |
| 3 | Performance | 6.75 | ★★ |
| 4 | Auditability | 6.55 | ★★★ |
| 5 | Operability | 5.10 | ★★ |
| 6 | Usability | 4.65 | ★ |
| 7 | Maintainability | 4.00 | ★ |

_Weights: Constitution (40%), Citizens (25%), Kings/Sentinels (20%), Operations (15%)_

---

### Domain Model

#### Aggregates

| Aggregate | Key Fields | Invariants |
|-----------|------------|------------|
| **Petition** | petition_id, state, petitioner_id, realm_id, content_hash, fate | State transitions one-way; exactly one terminal fate |
| **CoSignRequest** | request_id, petition_id, invitee_id, status, expires_at | Max 3 per petition; 24h timeout; cannot self-sign |
| **KingBudget** | king_id, cycle_id, budget, used | used ≤ budget (atomic); resets per cycle |
| **RealmHealth** | realm_id, responsiveness_score, pending_count | Score derived from metrics; updated on schedule |

#### Domain Events (24 Total)

- PetitionSubmitted, PetitionWitnessed, PetitionValidated, PetitionRejectedAsInvalid
- FraudCheckPassed, FraudCheckFailed, PetitionRoutedToRealm
- CoSignerInvited, CoSignerResponded, CoSignatureCollected, CoSignTimeoutExpired
- PetitionAcknowledged, PetitionReferred, EscalationRequested
- EscalationApproved, EscalationDenied, PetitionEscalated
- PetitionAdopted, MotionCreatedFromPetition, H1BudgetConsumed
- ResponsivenessScoreUpdated, PetitionArchived, DeadlineApproaching, DeadlineMissed

#### Commands (15 Total)

- SubmitPetition, ValidatePetition, CheckForFraud, RoutePetition
- InviteCoSigner, RespondToCoSign
- AcknowledgePetition, ReferPetition
- RequestEscalation, ApproveEscalation, DenyEscalation
- AdoptPetition, CalculateResponsiveness, ArchiveOldPetitions, CheckDeadlines

#### Policies (11 Total)

| Policy | Trigger | Action |
|--------|---------|--------|
| AutoValidationPolicy | PetitionSubmitted | Witness and validate |
| FraudScreeningPolicy | PetitionValidated | Check for fraud |
| RealmRoutingPolicy | FraudCheckPassed | Route to realm |
| FraudReviewPolicy | FraudCheckFailed | Mark for review |
| CoSignTimeoutPolicy | CoSignTimeoutExpired | Auto-decline request |
| DeadlineAlertPolicy | DeadlineApproaching | Notify Sentinel |
| AutoEscalationPolicy | DeadlineMissed | Escalate to King queue |
| BudgetEnforcementPolicy | EscalationApproved | Consume H1 budget |
| AdoptionBridgePolicy | PetitionAdopted | Create Motion via bridge |
| HealthMonitorPolicy | ResponsivenessScoreUpdated | Alert if < 0.5 |
| RetentionPolicy | PetitionArchived | Anonymize PII after 7 years |

---

### Constraint Summary

| Category | Count | Key Constraints |
|----------|-------|-----------------|
| **Constitutional** | 8 | CT-12 witnessing, CT-14 silence cost, CT-11 agenda scarcity, Three Fates exhaustive |
| **Technical** | 10 | PostgreSQL 15+, Python 3.11+, FastAPI, 200ms p95, Blake3 hashing |
| **Business** | 7 | 4-milestone delivery, no new infra M1-M3, team capacity |
| **Regulatory** | 7 | 7-year retention, PII anonymization, MFA for escalation, appeal path |
| **Temporal** | 7 | 24h co-sign timeout, 72h escalation window, 48h Sentinel SLA, 4h fraud SLA |
| **Integration** | 6 | Supabase Auth, Motion Gates, Witnessing Pipeline, PromotionBudgetStore |
| **Organizational** | 5 | Python expertise, 80% test coverage, code review required |

---

### Cross-Cutting Concerns

| Concern | Approach |
|---------|----------|
| **Authentication** | Supabase Auth, MFA for escalation |
| **Authorization** | Role-based (Citizen, Sentinel, King) |
| **Audit Trail** | Event sourcing with immutable log |
| **Rate Limiting** | Per-endpoint, per-user, per-realm tiers |
| **Fraud Detection** | Tiered: petition → realm → global |
| **Observability** | OpenTelemetry traces, Prometheus metrics |
| **Error Handling** | Structured errors, retry with backoff |
| **Data Retention** | 7-year archive per compliance |
| **Encryption** | At-rest (AES-256), in-transit (TLS 1.3) |
| **Backup/Recovery** | PostgreSQL PITR, 15-minute RPO |
| **Feature Flags** | LaunchDarkly for progressive rollout |
| **Circuit Breakers** | On all external service calls |

---

### Interface Contracts

| ID | Endpoint | Method | Actors |
|----|----------|--------|--------|
| **I-1** | /api/v1/petitions | POST | Citizen → System |
| **I-2** | /api/v1/petitions/{id}/fate | POST | Sentinel → System |
| **I-3** | /api/v1/petitions/{id}/escalate | POST | Citizen → System |
| **I-4** | /api/v1/escalations/{id}/decide | POST | King → System |
| **I-5** | /api/v1/petitions/{id}/adopt | POST | King → Motion Gates |
| **I-6** | EVENT petition.* | Async | System → Witnessing Pipeline |
| **I-7** | PromotionService.promote() | Internal | Adoption Bridge → Motion Gates |

---

### Critical Path (M1)

**Sequential (blocks next):**
1. Event store schema
2. Petition aggregate
3. State machine (Three Fates)
4. Witnessing integration (CT-12)
5. Submission API
6. Sentinel triage UI

**Parallel (non-blocking):**
- Co-sign workflow
- Notification hooks
- Basic fraud detection (duplicate, rate limit)
- Rate limiting

---

### Hidden Prerequisites (M1)

| ID | Requirement | Impact |
|----|-------------|--------|
| **HP-1** | Job queue for deadline monitoring | Enables auto-escalation |
| **HP-2** | Content hashing service (Blake3) | Duplicate detection |
| **HP-3** | Realm registry | Valid routing targets |
| **HP-4** | Sentinel-to-realm mapping | Triage assignment |
| **HP-7** | Read model projections | Optimized queue views |
| **HP-8** | Notification templates | User alerts |
| **HP-9** | Fraud rule engine | Pattern matching rules store |

---

### Hardening Controls (58 Total)

**Priority Controls (P0):**

| ID | Control | Threat Mitigated |
|----|---------|------------------|
| HC-1 | Fate transition requires witness event | Silent state corruption |
| HC-2 | Co-sign timeout (24h) with auto-reject | Zombie petitions |
| HC-3 | Escalation consumes H1 budget atomically | Budget bypass |
| HC-4 | Rate limit: 10 petitions/user/hour | Spam flooding |
| HC-5 | Duplicate detection via content hash | Sybil amplification |
| HC-6 | Job queue dead-letter with alerting | Silent job loss |
| PREVENT-7 | Adoption ratio alert > 50% per realm | King capture |

---

### Risk Profile

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Spam flood at launch | High | Medium | Pre-launch rate limits, captcha |
| King adoption abuse | Medium | High | Budget caps, adoption ratio alerts |
| Co-sign deadlock | Low | Medium | 24h timeout with auto-REFERRED |
| Event store corruption | Very Low | Critical | PITR backup, event replay |
| Responsiveness gaming | Medium | Medium | Score formula obfuscation |

---

### Milestone Scope

| Milestone | Focus | Key Deliverables |
|-----------|-------|------------------|
| **M1** | Core Lifecycle | Submission, Three Fates, Co-sign, Basic Fraud, Witnessing |
| **M2** | Escalation & Adoption | King flows, MFA, Adoption Bridge, H1 Budget integration |
| **M3** | Realm Integration | Per-realm fraud, Responsiveness scoring, Cross-realm referral |
| **M4** | Full Deployment | Global fraud (ML), Analytics, Dashboards, External audit |

---

### Quality Attribute Requirements (QARs)

| ID | Requirement | Target | Milestone |
|----|-------------|--------|-----------|
| **QAR-1** | Petition submission latency (p95) | < 200ms | M1 |
| **QAR-2** | Peak load handling | 1000 concurrent | M2 |
| **QAR-3** | Authentication coverage | 100% endpoints | M1 |
| **QAR-4** | MFA enforcement on escalation | 100% | M1 |
| **QAR-5** | Rate limit effectiveness | 100% bypass blocked | M1 |
| **QAR-6** | Transaction atomicity | 0 partial states | M1 |
| **QAR-7** | Event persistence | 0 event loss | M1 |
| **QAR-8** | Audit completeness | 0 untraced fates | M1 |
| **QAR-9** | Recovery time | < 5 min | M2 |
| **QAR-10** | Deployment rollback | < 5 min | M1 |

---

### Elicitation Methods Applied

**Round 1:** Architecture Decision Records, Cross-Functional War Room, Red Team vs Blue Team, First Principles Analysis, Failure Mode Analysis

**Round 2:** What If Scenarios, Comparative Analysis Matrix, Security Audit Personas, Pre-mortem Analysis, Graph of Thoughts

**Round 3:** Event Storming, Constraint Mapping, Quality Attribute Workshop, Domain Storytelling, Reverse Engineering

---

## Starter Template Evaluation

### Primary Technology Domain

API/Backend extension to existing Python 3.11+ FastAPI monolith.

### Starter Decision: Extend Existing Codebase

**Rationale:**
- Existing Hexagonal Architecture provides clear extension points
- PromotionBudgetStore and Motion Gates already available for H1 integration
- Witnessing Pipeline ready for petition event integration
- Consistent patterns reduce cognitive load

**No external starter template required.**

### Module Structure

New modules will follow existing conventions:

```
src/
├── domain/models/
│   ├── petition.py           # Petition aggregate
│   ├── co_sign_request.py    # CoSignRequest aggregate
│   └── realm_health.py       # RealmHealth aggregate
├── application/
│   ├── ports/
│   │   ├── petition_store.py # Repository protocol
│   │   └── fraud_detector.py # Fraud detection protocol
│   └── services/
│       ├── petition_service.py    # Core lifecycle
│       ├── escalation_service.py  # Escalation handling
│       └── adoption_service.py    # Bridge to Motion Gates
├── infrastructure/adapters/persistence/
│   ├── petition_store.py     # PostgreSQL implementation
│   └── realm_health_store.py
└── api/routes/
    └── petitions.py          # FastAPI endpoints
```

### Reusable Components

| Component | Location | Reuse |
|-----------|----------|-------|
| PromotionBudgetStore | `src/application/ports/` | H1 budget for adoption |
| InMemoryBudgetStore | `src/infrastructure/adapters/` | Test fixtures |
| FileBudgetStore | `src/infrastructure/adapters/` | Production option |
| LoggingMixin | `src/application/services/base.py` | Consistent logging |
| Event patterns | Existing witnessing | Petition events |

### First Implementation Story

"Create Petition domain model with Three Fates state machine and event schema"

---

