---
stepsCompleted: ['step-01-init', 'step-02-discovery', 'step-03-vision', 'step-04-personas', 'step-05-functional', 'step-06-nonfunctional', 'step-07-constraints', 'step-08-datamodel', 'step-09-milestones', 'step-10-metrics', 'step-11-scope', 'step-12-signoff']
status: approved
approvedAt: '2026-01-18'
inputDocuments:
  - _bmad-output/planning-artifacts/prd.md
  - _bmad-output/project-context.md
  - _bmad-output/implementation-artifacts/stories/7-2-external-observer-petition.md
  - docs/spikes/motion-gates.md
  - docs/spikes/motion-gates-hardening.md
workflowType: 'prd'
documentCounts:
  existingPRD: 1
  projectContext: 1
  existingImplementation: 1
  spikes: 2
classification:
  projectType: Backend system extension
  domain: AI Governance
  complexity: High
  context: Brownfield (extends existing Archon 72)
elicitationRounds: 2
---

# Product Requirements Document - Petition System

**Author:** Grand Architect
**Date:** 2026-01-18
**Version:** 1.0 (Approved)

---

## 1. Executive Summary

The Petition System extends Archon 72's constitutional governance framework to handle **external claims on attention** - communications from outside the legislative process that demand visibility and response. While Motions represent internal assertions of intent by Kings, Petitions represent claims by Observers, Seekers, and external parties that the system must acknowledge.

**Core Invariant:** *"Silence must be expensive."* Every petition terminates in exactly one of three fates, each witnessed and auditable.

### 1.1 Product Vision Statement

**For** Observers, Seekers, and external parties affected by Archon 72 governance decisions,

**Who** need a guaranteed path to be heard without requiring internal sponsorship,

**The** Petition System **is a** constitutional subsystem for external claims on attention

**That** ensures every petition terminates in a visible, witnessed fate (Acknowledged, Referred, or Escalated)

**Unlike** traditional petition platforms that allow silent drops or infinite deferral,

**Our system** enforces "silence must be expensive" through mandatory fate assignment, legitimacy decay scoring, and auto-escalation triggers that make ignoring petitions constitutionally impossible.

### 1.2 Problem Statement

**The Core Problem:**
Archon 72 currently has no constitutional path for external communications to reach the legislative floor. Motions represent internal intent by Kings, but there is no mechanism for:
- Observers to formally petition for system changes
- Seekers to collectively signal urgency (e.g., cessation requests)
- External parties to claim attention with guaranteed response

**The Consequence:**
Without a petition system, external stakeholders have no recourse. The system can effectively say "we didn't see it" - violating the constitutional principle that legitimacy requires responsiveness.

**The Constitutional Gap:**
- CT-11 establishes that "speech is unlimited; agenda is scarce" but provides no channel for external speech
- CT-12 mandates witnessing all outputs, but external inputs have no formal intake
- CT-13 requires explicit consent, but external parties cannot signal consent to governance actions affecting them

**Story 7.2 Limitation:**
The existing cessation petition (98 tests, dev-complete) handles one specific case but lacks:
- Unified petition type taxonomy
- Marquis/Knight triage workflow
- Legitimacy decay measurement
- King adoption bridge to Motions

### 1.3 Success Criteria (System Level)

| Criterion | Metric | Target |
|-----------|--------|--------|
| **No Silent Loss** | Petitions without fate after max_age | 0% |
| **Fate Witnessed** | Fate transitions with event | 100% |
| **Response Time** | Median time to first fate | < 3 cycles |
| **Legitimacy Score** | Decay metric | > 0.85 |
| **Observer Visibility** | Status queryable | 100% |
| **Story 7.2 Parity** | Existing tests passing | 98/98 |

---

## 2. Discovery & Classification

### 2.1 Project Classification

| Attribute | Value |
|-----------|-------|
| Project Type | Backend system extension |
| Domain | AI Governance / Constitutional Systems |
| Complexity | High |
| Context | Brownfield (extends Archon 72) |
| Integration | Subsumes Story 7.2 (cessation petitions) as CESSATION type |

### 2.2 Advanced Elicitation Summary

Two rounds of advanced elicitation were conducted:

| Category | Count | Key Outputs |
|----------|-------|-------------|
| First Principles Derivations | 5 | Three Fates exhaustiveness proven |
| Pre-mortem Failure Modes | 5 | Flood, Silent Referral, Laundering King, Legitimacy Theater, Cessation Orphan |
| Red Team Hardening Controls | 6 | SYBIL-1, LEGIT-1, CAPTURE-1, REFERRAL-1, META-1, CESSATION-1 |
| Critical Perspective Measures | 5 | REFUSED reason code with mandatory rationale |
| Architecture Decision Records | 7 | P1-P7 covering durability, state machine, timeouts |
| Stakeholder Requirements | 6 | STK-1 through STK-6 |
| Engineering Decisions | 6 | RECEIVED state, clustering, phased dashboard |
| Scenario Validations | 8 | Edge cases validated |
| Comparative Insights | 5 | Systems analyzed for positioning |
| Component Failure Modes | 50 | 10 critical severity |

---

## 3. First Principles Analysis

### 3.1 Irreducible Truths

| ID | Truth | Implication |
|----|-------|-------------|
| T1 | External parties exist who are affected by system decisions | System must have intake channel |
| T2 | Attention is finite; not all claims can become Motions | Triage mechanism required |
| T3 | Silence erodes legitimacy | Every petition must have visible outcome |
| T4 | Only Kings can bind the agenda | Petitions cannot self-promote to Motions |
| T5 | Transparency enables accountability | All fate decisions must be witnessed |

### 3.2 Three Fates Derivation

From T2 (finite attention) and T3 (no silence), exactly three terminal states emerge:

1. **ACKNOWLEDGED** - System has seen and decided no further action warranted
2. **REFERRED** - System routes to domain expert (Knight) for recommendation
3. **ESCALATED** - System elevates to King for mandatory consideration

**Proof of Exhaustiveness:** Any fourth fate would either be:
- A synonym of existing fates (violates parsimony)
- Silent/invisible (violates T3)
- Self-executing (violates T4)

---

## 4. Pre-mortem Analysis

### 4.1 Identified Failure Modes

| ID | Failure Mode | Description | Prevention Control |
|----|--------------|-------------|-------------------|
| PRE-1 | The Flood | Malicious petition spam overwhelms triage | Rate limiting + SYBIL-1 detection |
| PRE-2 | The Silent Referral | Knight referrals expire without action | Timeout clock + auto-acknowledge |
| PRE-3 | The Laundering King | King adopts to launder budget | source_petition_ref mandatory + attribution |
| PRE-4 | The Legitimacy Theater | Metrics gamed while observers suffer | Decay engine + external audit |
| PRE-5 | The Cessation Orphan | 100-signer cessation stuck in limbo | CESSATION type + auto-escalation |

---

## 5. Red Team Hardening Controls

| Control ID | Attack Vector | Mitigation |
|------------|---------------|------------|
| SYBIL-1 | Fake identities flood petitions | Identity verification + rate limiting per verified identity |
| LEGIT-1 | Manufactured consent via bot co-signers | Co-signer dedup + fraud detection patterns |
| CAPTURE-1 | Knight collusion with petitioners | Rotation + conflict-of-interest audit |
| REFERRAL-1 | Infinite referral ping-pong | Max 2 referrals + timeout |
| META-1 | Petition about petition system to deadlock | Meta-petition type + expedited High Archon review |
| CESSATION-1 | Cessation petition buried by hostile Marquis | Auto-escalation at 100 signers (immutable) |

---

## 6. Architecture Decision Records

### ADR-P1: Petition State Durability
- **Decision:** Event-sourced state with append-only log
- **Rationale:** CT-12 (witness everything) compliance
- **Consequences:** Recovery possible; storage grows linearly

### ADR-P2: Three Fates State Machine
- **Decision:** Explicit state machine with transition matrix
- **Rationale:** Prevent illegal transitions; enable audit
- **Consequences:** All transitions validated at domain layer

### ADR-P3: Referral Timeout
- **Decision:** 3 cycles default + max 2 extensions
- **Rationale:** Balance Knight review time vs. petition aging
- **Consequences:** Hard deadline prevents infinite deferral

### ADR-P4: King Adoption Bridge
- **Decision:** Adoption consumes promotion budget
- **Rationale:** Prevent budget laundering
- **Consequences:** Petitions compete with Seeds for King attention

### ADR-P5: Legitimacy Decay Scoring
- **Decision:** Quantitative responsiveness metric
- **Rationale:** "Silence must be expensive" made measurable
- **Consequences:** Dashboard visibility; potential gaming vector

### ADR-P6: RECEIVED Intermediate State
- **Decision:** Add RECEIVED between intake and first fate
- **Rationale:** Engineering feasibility (async processing)
- **Consequences:** Four visible states (RECEIVED + three fates)

### ADR-P7: Story 7.2 Migration
- **Decision:** Subsume as CESSATION petition type
- **Rationale:** Unified petition handling; preserve 98 tests
- **Consequences:** Migration path; no breaking changes

---

## 7. Stakeholder Requirements

| ID | Stakeholder | Requirement | Priority |
|----|-------------|-------------|----------|
| STK-1 | Observer | "I can see my petition's current state and fate" | P0 |
| STK-2 | Seeker | "I can co-sign petitions that affect me" | P0 |
| STK-3 | Marquis | "I have tools to efficiently triage petitions" | P0 |
| STK-4 | Knight | "I receive referrals with sufficient context" | P1 |
| STK-5 | King | "Escalations are clearly distinguished from organic Motions" | P1 |
| STK-6 | High Archon | "I can audit petition fate decisions" | P1 |

---

## 8. Engineering Decisions

### 8.1 State Model
- **RECEIVED** state added before fate determination
- Enables async processing without violating "no silence" invariant

### 8.2 Clustering Strategy
- Similarity-based clustering for related petitions
- Max cluster size: 50
- Opt-out preserves individual petition autonomy

### 8.3 Decision Package
- Bundled context for Knight/King review
- Includes: petition text, co-signer count, related petitions, submitter history

### 8.4 Dashboard Delivery
- Phase 1: CLI tooling for actors
- Phase 2: Read-only dashboard
- Phase 3: Interactive triage UI

### 8.5 Migration Strategy
- Story 7.2 cessation_petition table preserved
- New unified petitions table
- Dual-write during transition; single-read from new

### 8.6 Polling API
- status_token for long-poll efficiency
- Observers can check petition state without flooding

---

## 9. Scenario Validations

| Scenario | Validates | Outcome |
|----------|-----------|---------|
| S1: 10,000 petitions in 1 hour | Flood resistance | Rate limit + queue backpressure |
| S2: Knight on vacation | Referral timeout | Auto-acknowledge after deadline |
| S3: Petition becomes Motion | Adoption flow | source_petition_ref preserved |
| S4: 100 cessation co-signers | Auto-escalation | CESSATION-1 triggers |
| S5: Petitioner withdraws | WITHDRAWN reason | Valid path; no further action |
| S6: Duplicate petitions | Clustering | Related petitions grouped |
| S7: Meta-petition about system | META-1 handling | Expedited High Archon review |
| S8: All Marquis offline | Fallback | Deputy assignment + auto-referral |

---

## 10. Comparative Analysis

### 10.1 Systems Analyzed
1. We The People (USA petitions)
2. UK Parliament e-petitions
3. Change.org
4. GitHub Issues
5. Jira Service Desk

### 10.2 Unique Strengths
- **Constitutional grounding** (not just workflow)
- **Three Fates guarantee** (no silent drop)
- **King Adoption bridge** (external→internal path)
- **Legitimacy Decay scoring** (self-accountability)
- **Event-sourced audit** (full transparency)

### 10.3 Gaps to Address
- Real-time status updates (implemented via status_token)
- Mobile accessibility (Phase 3+ consideration)
- Multi-language support (future enhancement)

---

## 11. Failure Mode Analysis (FMEA)

### 11.1 Critical Failure Modes (Severity = CRITICAL)

| ID | Component | Failure Mode | Prevention |
|----|-----------|--------------|------------|
| FM-1.4 | Intake | Petition ID collision | UUIDv7 + collision check |
| FM-1.5 | Intake | Silent drop on overflow | Backpressure 503 |
| FM-2.1 | State Machine | Illegal transition | Exhaustive matrix |
| FM-2.3 | State Machine | Double-fate | Atomic CAS |
| FM-2.4 | State Machine | Fate without witness | Same-txn event |
| FM-3.5 | Marquis | Lost assignment | FK + orphan scan |
| FM-4.1 | King Bridge | Budget bypass | Atomic check-consume |
| FM-7.1 | Timeout | Never fires | Persistent job queue |
| FM-8.3 | Escalation | Not witnessed | Same-txn witness |
| FM-9.1 | Co-signers | Duplicate counted | Unique constraint |

### 11.2 Full FMEA Coverage
- 10 components analyzed
- 50 failure modes identified
- 10 critical, 22 high, 13 medium, 5 low severity

---

## 12. Petition Types

| Type | Description | Auto-Escalation | Special Rules |
|------|-------------|-----------------|---------------|
| GENERAL | Standard petition | None | Standard flow |
| CESSATION | Request to halt operation | 100 co-signers | Story 7.2 subsumption |
| GRIEVANCE | Complaint about system/actor | 50 co-signers | Knight must respond |
| COLLABORATION | Request for partnership | None | Referral to relevant realm |

---

## 13. Acknowledgment Reason Codes

| Code | Meaning | Rationale Required |
|------|---------|-------------------|
| OUT_OF_SCOPE | Not within system jurisdiction | No |
| DUPLICATE | Already addressed by another petition | Reference required |
| MALFORMED | Cannot parse petition intent | No |
| NO_ACTION_WARRANTED | Reviewed, no action needed | Yes |
| REFUSED | Explicitly declined | Yes (mandatory) |
| WITHDRAWN | Petitioner withdrew | No |
| EXPIRED | Timeout without Knight action | No |

---

## 13A. Three Fates Deliberation Engine

### 13A.1 Overview

The **Three Fates** are not merely terminal states—they are **three Marquis-rank Archon AI agents** that deliberate on every petition using a **supermajority consensus protocol**. This mini-Conclave ensures that petition disposition reflects collective deliberative judgment rather than unilateral decision.

### 13A.2 Architectural Concept

```
┌─────────────────────────────────────────────────────────────────┐
│                    PETITION RECEIVED                            │
│                          ↓                                      │
│              ┌──────────────────────┐                          │
│              │   Three Fates Pool   │                          │
│              │  (Marquis Archons)   │                          │
│              └──────────────────────┘                          │
│                          ↓                                      │
│    ┌─────────────────────────────────────────────────┐         │
│    │           MINI-CONCLAVE DELIBERATION            │         │
│    │                                                 │         │
│    │  ┌─────────┐  ┌─────────┐  ┌─────────┐        │         │
│    │  │ Fate-1  │  │ Fate-2  │  │ Fate-3  │        │         │
│    │  │(Archon) │  │(Archon) │  │(Archon) │        │         │
│    │  └────┬────┘  └────┬────┘  └────┬────┘        │         │
│    │       │            │            │              │         │
│    │       └────────────┼────────────┘              │         │
│    │                    ↓                           │         │
│    │         SUPERMAJORITY VOTE (2-of-3)           │         │
│    └─────────────────────────────────────────────────┘         │
│                          ↓                                      │
│    ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │
│    │ ACKNOWLEDGE │  │   REFER     │  │  ESCALATE   │          │
│    └─────────────┘  └─────────────┘  └─────────────┘          │
└─────────────────────────────────────────────────────────────────┘
```

### 13A.3 Deliberation Protocol

**Phase 1: Assessment** (Individual)
- Each Fate Archon independently analyzes the petition
- Generates initial assessment with reasoning
- All assessments witnessed per CT-12

**Phase 2: Position Statement** (Sequential)
- Each Archon states preferred disposition
- Provides constitutional and practical rationale
- Cross-references prior similar petitions

**Phase 3: Cross-Examination** (Interactive)
- Archons may challenge each other's positions
- Maximum 3 deliberation rounds
- Deadlock triggers auto-ESCALATE

**Phase 4: Consensus Vote** (Atomic)
- Each Archon casts vote: ACKNOWLEDGE | REFER | ESCALATE
- Supermajority (2-of-3) determines outcome
- Dissenting opinion recorded for audit

### 13A.4 Disposition Options

| Disposition | Meaning | Next Pipeline Stage |
|-------------|---------|---------------------|
| ACKNOWLEDGE | Petition received, no further action | Terminal (with reason code) |
| REFER | Requires domain expert review | Knight Referral Queue |
| ESCALATE | Significant enough for Realm authority | King Escalation Queue |

### 13A.5 Timeout & Deadlock Handling

| Scenario | Trigger | Resolution |
|----------|---------|------------|
| Deliberation timeout | > 5 minutes elapsed | Auto-ESCALATE |
| Persistent deadlock | 3 rounds, no supermajority | Auto-ESCALATE |
| Archon unavailable | Response timeout > 30 sec | Substitute from pool |

### 13A.6 Constitutional Compliance

- **CT-12**: All deliberation utterances preserved and hash-witnessed at phase boundaries
- **CT-14**: Deliberation ensures every petition terminates in witnessed fate
- **Auditability**: Full transcript preserved for reconstruction

### 13A.7 Witness Architecture (Ruling-1)

**Witness unit = phase, not speech act.**

Each phase (ASSESS, POSITION, CROSS_EXAMINE, VOTE) produces one witness event containing:
- Hash of full transcript for that phase
- Participating Archons
- Start/end timestamps
- Phase outcome metadata (e.g., "positions converged", "dissent present")

**Raw utterances:**
- Stored as content-addressed, immutable artifacts
- Referenced by hash in witness events
- Not individual ledger events

This satisfies FR-11.7 without violating NFR-10.5 (100+ concurrent deliberations).

### 13A.8 Transcript Access Model (Ruling-2)

**Access is tiered, explicit, and non-default.**

| Audience | Access Level |
|----------|--------------|
| Internal system (Knight/Princes) | Full transcripts |
| Petitioner | Phase summaries + final disposition rationale |
| Public observers | No raw transcripts by default |
| Escalated/audited cases | Selective release via mediated process |

**Observers receive:**
- Phase-level witness records
- Vote outcomes
- Dissent presence indicator
- Hash references (proving transcripts exist and are immutable)

**Transcript release** (when permitted):
- Is a deliberate act
- Is logged
- Is attributed
- Is scoped

*Transparency = traceability, not voyeurism.*

---

## 14. Constitutional Alignment

### 14.1 Existing Constitutional Truths Applied

| CT | Truth | Application |
|----|-------|-------------|
| CT-11 | "Speech is unlimited. Agenda is scarce." | Petitions are unlimited speech; adoption is scarce |
| CT-12 | All outputs through witnessing pipeline | All fate transitions witnessed |
| CT-13 | Explicit consent for governance participation | Co-signing is opt-in consent |

### 14.2 New Constitutional Truth Proposed

**CT-14:** *"Silence must be expensive. Every claim on attention terminates in a visible, witnessed fate."*

---

## Appendix A: Glossary

| Term | Definition |
|------|------------|
| Petition | External claim on system attention |
| Motion | Internal assertion of legislative intent |
| Fate | Terminal state of petition (ACKNOWLEDGED/REFERRED/ESCALATED) |
| Observer | Entity submitting petition |
| Seeker | Entity co-signing petition |
| Marquis | First-line triage authority |
| Knight | Domain expert for referral review |
| King | Realm authority; can adopt petitions as Motions |
| Adoption | Conversion of petition to Motion by King |
| Legitimacy Decay | Metric of system responsiveness |

---

## 15. User Personas & Journeys

### 15.1 The Observer (External Petitioner)

**Identity:** An individual or entity outside the legislative process affected by Archon 72 decisions.

**Goals:**
- Submit a formal petition that cannot be silently ignored
- Track petition status through to fate determination
- Receive notification when fate is assigned
- Optionally, have petition adopted as Motion by a King

**Pain Points:**
- No current channel to reach the legislative floor
- Uncertainty whether communication was received
- No visibility into decision process

**Journey:**
```
Compose Petition → Submit via Intake → Receive petition_id
    → Poll status_token → Fate assigned (ACKNOWLEDGED/REFERRED/ESCALATED)
    → If ESCALATED: King must consider
    → If adopted: Motion created with source_petition_ref
```

### 15.2 The Seeker (Co-signer)

**Identity:** An entity who supports an existing petition but is not the original submitter.

**Goals:**
- Find petitions aligned with their concerns
- Add co-signature to amplify signal
- Trigger auto-escalation thresholds (100 for CESSATION, 50 for GRIEVANCE)

**Pain Points:**
- No way to discover existing petitions
- No collective action mechanism
- Individual voice feels powerless

**Journey:**
```
Discover petition (search/browse) → Review petition text
    → Co-sign with identity verification → Receive confirmation
    → Watch co-signer count → Threshold crossed → Auto-escalation triggers
```

### 15.3 The Marquis (First-Line Triage)

**Identity:** Appointed authority responsible for initial petition triage.

**Goals:**
- Efficiently process incoming petitions
- Route to correct fate (ACKNOWLEDGE, REFER, or allow escalation)
- Maintain legitimacy score through responsive handling
- Avoid rubber-stamp syndrome

**Pain Points:**
- High volume during crisis periods
- Unclear jurisdiction boundaries
- Pressure to clear queue vs. thorough review

**Journey:**
```
Receive petition queue → Review petition context
    → Decision: ACKNOWLEDGE (with reason) | REFER (to Knight) | DEFER (wait for co-signers)
    → Assign fate → Event witnessed → Metrics updated
```

### 15.4 The Knight (Domain Expert)

**Identity:** Realm specialist who reviews referred petitions and makes recommendations.

**Goals:**
- Receive referrals with sufficient context
- Provide informed recommendation to King
- Complete review before timeout expires
- Maintain rotation fairness

**Pain Points:**
- Referrals without context
- Too many concurrent referrals
- Timeout pressure
- Capture/collusion accusations

**Journey:**
```
Receive referral notification → Access decision package
    → Review petition + related context → Formulate recommendation
    → Submit recommendation (with rationale) → Return to Marquis/King
    → Request extension if needed (max 2)
```

### 15.5 The King (Realm Authority)

**Identity:** Sovereign of a realm who can adopt petitions as Motions.

**Goals:**
- Receive clearly distinguished escalations (vs. organic Seeds)
- Adopt worthy petitions without budget laundering
- Maintain realm sovereignty
- Preserve petition attribution in Motion

**Pain Points:**
- Escalation flood obscuring organic agenda
- Budget pressure from adoption
- Cross-realm coordination complexity

**Journey:**
```
Receive escalation queue → Review petition + recommendation
    → Decision: ADOPT (consumes budget) | ACKNOWLEDGE (with rationale)
    → If ADOPT: Create Motion with source_petition_ref
    → Event witnessed → Observer notified
```

### 15.6 The High Archon (Constitutional Auditor)

**Identity:** Ultimate authority for constitutional compliance and system health.

**Goals:**
- Audit petition fate decisions
- Monitor legitimacy decay metrics
- Handle meta-petitions about the petition system
- Intervene on constitutional violations

**Pain Points:**
- Metric gaming
- Alert fatigue
- Meta-petition deadlock

**Journey:**
```
Monitor legitimacy dashboard → Review decay alerts
    → Audit individual fate decisions → Identify patterns
    → Intervene if constitutional violation detected
    → Handle META-type petitions directly
```

### 15.7 Journey Summary Matrix

| Actor | Entry Point | Primary Action | Exit Point |
|-------|-------------|----------------|------------|
| Observer | Intake API | Submit petition | Fate notification |
| Seeker | Discovery API | Co-sign | Escalation trigger |
| Marquis | Petition queue | Triage | Fate assignment |
| Knight | Referral inbox | Recommend | Recommendation submitted |
| King | Escalation queue | Adopt/Acknowledge | Motion created |
| High Archon | Dashboard | Audit | Intervention (if needed) |

---

---

## 16. Functional Requirements

### 16.1 Petition Intake (Observer)

| FR ID | Requirement | Priority | Source |
|-------|-------------|----------|--------|
| FR-1.1 | System SHALL accept petition submissions via REST API | P0 | STK-1 |
| FR-1.2 | System SHALL generate UUIDv7 petition_id on submission | P0 | FM-1.4 |
| FR-1.3 | System SHALL validate petition schema (type, text, submitter_id) | P0 | FM-1.2 |
| FR-1.4 | System SHALL return HTTP 503 on queue overflow (no silent drop) | P0 | FM-1.5, I1 |
| FR-1.5 | System SHALL enforce rate limits per submitter_id | P1 | SYBIL-1 |
| FR-1.6 | System SHALL set initial state to RECEIVED | P0 | ADR-P6 |
| FR-1.7 | System SHALL emit PetitionReceived event on successful intake | P0 | CT-12 |

### 16.2 Petition State Machine

| FR ID | Requirement | Priority | Source |
|-------|-------------|----------|--------|
| FR-2.1 | System SHALL enforce valid state transitions only | P0 | FM-2.1, ADR-P2 |
| FR-2.2 | System SHALL support states: RECEIVED, ACKNOWLEDGED, REFERRED, ESCALATED | P0 | ADR-P6 |
| FR-2.3 | System SHALL reject transitions not in transition matrix | P0 | FM-2.1 |
| FR-2.4 | System SHALL use atomic CAS for fate assignment (no double-fate) | P0 | FM-2.3 |
| FR-2.5 | System SHALL emit fate event in same transaction as state update | P0 | FM-2.4 |
| FR-2.6 | System SHALL mark petition as terminal when fate assigned | P0 | Three Fates |

### 16.3 Acknowledgment Handling (Marquis)

| FR ID | Requirement | Priority | Source |
|-------|-------------|----------|--------|
| FR-3.1 | Marquis SHALL be able to ACKNOWLEDGE petition with reason code | P0 | STK-3 |
| FR-3.2 | System SHALL require reason_code from: OUT_OF_SCOPE, DUPLICATE, MALFORMED, NO_ACTION_WARRANTED, REFUSED, WITHDRAWN, EXPIRED | P0 | Reason Codes |
| FR-3.3 | System SHALL require rationale text for REFUSED and NO_ACTION_WARRANTED | P0 | Critical Perspective |
| FR-3.4 | System SHALL require reference_petition_id for DUPLICATE | P1 | Reason Codes |
| FR-3.5 | System SHALL enforce minimum dwell time before ACKNOWLEDGE | P1 | FM-3.1 |
| FR-3.6 | System SHALL track acknowledgment rate metrics per Marquis | P1 | FM-3.2 |

### 16.4 Referral Handling (Knight)

| FR ID | Requirement | Priority | Source |
|-------|-------------|----------|--------|
| FR-4.1 | Marquis SHALL be able to REFER petition to Knight with realm_id | P0 | STK-3 |
| FR-4.2 | System SHALL assign referral deadline (3 cycles default) | P0 | ADR-P3 |
| FR-4.3 | Knight SHALL receive decision package (petition + context) | P0 | STK-4 |
| FR-4.4 | Knight SHALL be able to request extension (max 2) | P1 | ADR-P3 |
| FR-4.5 | System SHALL auto-ACKNOWLEDGE on referral timeout (reason: EXPIRED) | P0 | FM-7.1 |
| FR-4.6 | Knight SHALL submit recommendation with mandatory rationale | P0 | FM-5.2 |
| FR-4.7 | System SHALL enforce max concurrent referrals per Knight | P1 | FM-5.4 |

### 16.5 Escalation Handling (King)

| FR ID | Requirement | Priority | Source |
|-------|-------------|----------|--------|
| FR-5.1 | System SHALL ESCALATE petition when co-signer threshold reached | P0 | CESSATION-1 |
| FR-5.2 | Escalation thresholds: CESSATION=100, GRIEVANCE=50 | P0 | Petition Types |
| FR-5.3 | System SHALL emit EscalationTriggered event with co-signer_count | P0 | FM-8.3 |
| FR-5.4 | King SHALL receive escalation queue distinct from organic Motions | P0 | STK-5 |
| FR-5.5 | King SHALL be able to ADOPT petition (creates Motion) | P0 | ADR-P4 |
| FR-5.6 | Adoption SHALL consume promotion budget (H1 compliance) | P0 | ADR-P4 |
| FR-5.7 | Adopted Motion SHALL include source_petition_ref | P0 | FM-4.2 |
| FR-5.8 | King SHALL be able to ACKNOWLEDGE escalation (with rationale) | P0 | King Journey |

### 16.6 Co-signer Management (Seeker)

| FR ID | Requirement | Priority | Source |
|-------|-------------|----------|--------|
| FR-6.1 | Seeker SHALL be able to co-sign active petition | P0 | STK-2 |
| FR-6.2 | System SHALL enforce unique constraint (petition_id, signer_id) | P0 | FM-9.1 |
| FR-6.3 | System SHALL reject co-sign after fate assignment | P1 | FM-9.4 |
| FR-6.4 | System SHALL increment co-signer count atomically | P0 | FM-9.3 |
| FR-6.5 | System SHALL check escalation threshold on each co-sign | P0 | FR-5.1 |
| FR-6.6 | System SHALL apply SYBIL-1 rate limiting per signer | P1 | SYBIL-1 |

### 16.7 Status & Visibility (Observer)

| FR ID | Requirement | Priority | Source |
|-------|-------------|----------|--------|
| FR-7.1 | Observer SHALL be able to query petition status by petition_id | P0 | STK-1 |
| FR-7.2 | System SHALL return status_token for efficient long-poll | P1 | Engineering Decision |
| FR-7.3 | System SHALL notify Observer on fate assignment | P1 | Observer Journey |
| FR-7.4 | System SHALL expose co-signer count in status response | P0 | Seeker visibility |
| FR-7.5 | Observer SHALL be able to WITHDRAW petition (before fate) | P1 | Reason Codes |

### 16.8 Legitimacy Decay (High Archon)

| FR ID | Requirement | Priority | Source |
|-------|-------------|----------|--------|
| FR-8.1 | System SHALL compute legitimacy decay metric per cycle | P1 | ADR-P5 |
| FR-8.2 | Decay formula: (fated_petitions / total_petitions) within SLA | P1 | ADR-P5 |
| FR-8.3 | System SHALL alert on decay below 0.85 threshold | P1 | Success Criteria |
| FR-8.4 | High Archon SHALL access legitimacy dashboard | P1 | STK-6 |
| FR-8.5 | System SHALL identify petitions stuck in RECEIVED | P1 | FM-2.2 |

### 16.9 Migration & Compatibility

| FR ID | Requirement | Priority | Source |
|-------|-------------|----------|--------|
| FR-9.1 | System SHALL migrate Story 7.2 cessation_petition to CESSATION type | P0 | ADR-P7 |
| FR-9.2 | All 98 existing tests SHALL pass post-migration | P0 | Success Criteria |
| FR-9.3 | System SHALL support dual-write during migration period | P1 | Engineering Decision |
| FR-9.4 | System SHALL preserve existing petition_id references | P0 | FM-9.5 |

### 16.10 Petition Types

| FR ID | Requirement | Priority | Source |
|-------|-------------|----------|--------|
| FR-10.1 | System SHALL support petition types: GENERAL, CESSATION, GRIEVANCE, COLLABORATION | P0 | Petition Types |
| FR-10.2 | CESSATION petitions SHALL auto-escalate at 100 co-signers | P0 | Story 7.2 |
| FR-10.3 | GRIEVANCE petitions SHALL auto-escalate at 50 co-signers | P1 | Petition Types |
| FR-10.4 | META petitions (about petition system) SHALL route to High Archon | P2 | META-1 |

### 16.11 Three Fates Deliberation

| FR ID | Requirement | Priority | Source |
|-------|-------------|----------|--------|
| FR-11.1 | System SHALL assign exactly 3 Marquis-rank Archons from Three Fates pool to deliberate each petition | P0 | Section 13A |
| FR-11.2 | System SHALL initiate mini-Conclave deliberation session when petition enters RECEIVED state | P0 | Section 13A |
| FR-11.3 | System SHALL provide deliberation context package (petition, type, co-signer count, similar petitions) to each Fate Archon | P0 | Section 13A |
| FR-11.4 | Deliberation SHALL follow structured protocol: Assess → Position → Cross-Examine → Vote | P0 | Section 13A |
| FR-11.5 | System SHALL require supermajority consensus (2-of-3 Archons) for disposition decision | P0 | Section 13A |
| FR-11.6 | Fate Archons SHALL vote for exactly one disposition: ACKNOWLEDGE, REFER, or ESCALATE | P0 | Section 13A |
| FR-11.7 | System SHALL preserve ALL deliberation utterances (hash-referenced) with ledger witnessing at phase boundaries per CT-12 | P0 | CT-12, Ruling-1 |
| FR-11.8 | System SHALL record dissenting opinion when vote is not unanimous | P0 | Auditability |
| FR-11.9 | System SHALL enforce deliberation timeout (5 minutes default) with auto-ESCALATE on expiry | P0 | Section 13A.5 |
| FR-11.10 | System SHALL auto-ESCALATE after 3 deliberation rounds without supermajority (deadlock) | P0 | Section 13A.5 |
| FR-11.11 | System SHALL route petition to appropriate pipeline based on deliberation outcome | P0 | Section 13A.4 |
| FR-11.12 | System SHALL preserve complete deliberation transcript for audit reconstruction | P0 | NFR-6.5 |

### 16.12 Functional Requirements Summary

| Group | FRs | P0 | P1 | P2 |
|-------|-----|----|----|----|
| Intake | 7 | 6 | 1 | 0 |
| State Machine | 6 | 6 | 0 | 0 |
| Acknowledgment | 6 | 3 | 3 | 0 |
| Referral | 7 | 4 | 3 | 0 |
| Escalation | 8 | 7 | 1 | 0 |
| Co-signer | 6 | 4 | 2 | 0 |
| Status | 5 | 2 | 3 | 0 |
| Legitimacy | 5 | 0 | 5 | 0 |
| Migration | 4 | 3 | 1 | 0 |
| Types | 4 | 2 | 1 | 1 |
| **Deliberation** | **12** | **12** | **0** | **0** |
| **Total** | **70** | **49** | **20** | **1** |

---

---

## 17. Non-Functional Requirements

### 17.1 Performance

| NFR ID | Requirement | Target | Measurement |
|--------|-------------|--------|-------------|
| NFR-1.1 | Petition intake latency | p99 < 200ms | API response time |
| NFR-1.2 | Status query latency | p99 < 100ms | API response time |
| NFR-1.3 | Co-sign processing | p99 < 150ms | Transaction time |
| NFR-1.4 | Escalation trigger detection | < 1 second from threshold | Event timestamp delta |
| NFR-1.5 | Legitimacy metric computation | < 60 seconds per cycle | Batch job duration |

### 17.2 Scalability

| NFR ID | Requirement | Target | Measurement |
|--------|-------------|--------|-------------|
| NFR-2.1 | Concurrent petitions in RECEIVED | 10,000+ | Load test |
| NFR-2.2 | Co-signers per petition | 100,000+ | Stress test |
| NFR-2.3 | Petitions per cycle | 1,000+ | Throughput test |
| NFR-2.4 | Horizontal scaling | Stateless API nodes | Architecture review |
| NFR-2.5 | Database connection pooling | 100 connections per node | Config verification |

### 17.3 Reliability

| NFR ID | Requirement | Target | Source |
|--------|-------------|--------|--------|
| NFR-3.1 | No silent petition loss | 0 lost petitions | FM-1.5, I1 |
| NFR-3.2 | Fate assignment atomicity | 100% single-fate | FM-2.3 |
| NFR-3.3 | Event witnessing | 100% fate events persisted | FM-2.4 |
| NFR-3.4 | Referral timeout reliability | 100% timeouts fire | FM-7.1 |
| NFR-3.5 | Co-signer deduplication | 0 duplicate signatures | FM-9.1 |
| NFR-3.6 | System availability | 99.9% uptime | SLA |

### 17.4 Durability

| NFR ID | Requirement | Target | Source |
|--------|-------------|--------|--------|
| NFR-4.1 | Petition state durability | Survives process restart | ADR-P1 |
| NFR-4.2 | Event log durability | Append-only, no deletion | CT-12 |
| NFR-4.3 | Co-signer list durability | No truncation before archive | FM-9.5 |
| NFR-4.4 | Referral deadline persistence | Survives scheduler restart | FM-7.1 |
| NFR-4.5 | Budget consumption durability | Atomic with promotion | ADR-P4, H1 |

### 17.5 Security

| NFR ID | Requirement | Target | Source |
|--------|-------------|--------|--------|
| NFR-5.1 | Rate limiting per identity | Configurable per type | SYBIL-1 |
| NFR-5.2 | Identity verification for co-sign | Required | LEGIT-1 |
| NFR-5.3 | Input sanitization | All petition text sanitized | FM-1.2 |
| NFR-5.4 | Role-based access control | Actor-appropriate endpoints | Personas |
| NFR-5.5 | Audit log immutability | Hash chain integrity | FM-6.2 |
| NFR-5.6 | Legitimacy metrics visibility | Internal-only by default | FM-6.5 |

### 17.6 Auditability

| NFR ID | Requirement | Target | Source |
|--------|-------------|--------|--------|
| NFR-6.1 | All fate transitions witnessed | Event with actor, timestamp, reason | CT-12 |
| NFR-6.2 | Adoption provenance | source_petition_ref immutable | FM-4.2 |
| NFR-6.3 | Rationale preservation | REFUSED/NO_ACTION rationale stored | FR-3.3 |
| NFR-6.4 | Co-signer attribution | Full signer list queryable | STK-6 |
| NFR-6.5 | State history reconstruction | Full replay from event log | ADR-P1 |

### 17.7 Operability

| NFR ID | Requirement | Target | Source |
|--------|-------------|--------|--------|
| NFR-7.1 | Orphan petition detection | Daily sweep identifies stuck petitions | FM-2.2 |
| NFR-7.2 | Legitimacy decay alerting | Alert at < 0.85 threshold | FR-8.3 |
| NFR-7.3 | Referral load balancing | Max concurrent per Knight configurable | FM-5.4 |
| NFR-7.4 | Queue depth monitoring | Backpressure before overflow | FM-1.5 |
| NFR-7.5 | Timeout job monitoring | Heartbeat on scheduler | FM-7.1 |

### 17.8 Compatibility

| NFR ID | Requirement | Target | Source |
|--------|-------------|--------|--------|
| NFR-8.1 | Story 7.2 test compatibility | 98/98 tests pass | FR-9.2 |
| NFR-8.2 | Existing petition_id preservation | No ID changes | FR-9.4 |
| NFR-8.3 | Motion Gates integration | Uses existing promotion budget | ADR-P4 |
| NFR-8.4 | EventWriterService integration | Same witness pipeline | CT-12 |
| NFR-8.5 | API versioning | /v1/ prefix for new endpoints | API design |

### 17.9 Testability

| NFR ID | Requirement | Target | Source |
|--------|-------------|--------|--------|
| NFR-9.1 | Unit test coverage | > 90% for domain logic | Quality gate |
| NFR-9.2 | Integration test coverage | All state transitions | ADR-P2 |
| NFR-9.3 | FMEA scenario coverage | All 10 critical failure modes | FMEA |
| NFR-9.4 | Load test harness | Simulates 10k petition flood | S1 |
| NFR-9.5 | Chaos testing | Scheduler crash recovery | FM-7.1 |

### 17.10 Deliberation Performance

| NFR ID | Requirement | Target | Measurement |
|--------|-------------|--------|-------------|
| NFR-10.1 | Deliberation end-to-end latency | p95 < 5 minutes | Session duration |
| NFR-10.2 | Individual Archon response time | p95 < 30 seconds | Per-utterance latency |
| NFR-10.3 | Consensus determinism | 100% reproducible given same inputs | Replay test |
| NFR-10.4 | Witness completeness | 100% utterances witnessed | Audit gap detection |
| NFR-10.5 | Concurrent deliberations | 100+ simultaneous sessions | Load test |
| NFR-10.6 | Archon substitution latency | < 10 seconds on failure | Failover test |

**Critical NFRs:** NFR-10.1 (deliberation latency), NFR-10.3 (determinism), NFR-10.4 (witness completeness)

### 17.11 Non-Functional Requirements Summary

| Group | NFRs | Critical |
|-------|------|----------|
| Performance | 5 | NFR-1.4 (escalation detection) |
| Scalability | 5 | NFR-2.2 (co-signer volume) |
| Reliability | 6 | NFR-3.1, NFR-3.2, NFR-3.3 (core invariants) |
| Durability | 5 | NFR-4.1, NFR-4.2 (state + events) |
| Security | 6 | NFR-5.1, NFR-5.2 (anti-Sybil) |
| Auditability | 5 | NFR-6.1 (witnessed fates) |
| Operability | 5 | NFR-7.1 (orphan detection) |
| Compatibility | 5 | NFR-8.1 (test parity) |
| Testability | 5 | NFR-9.3 (FMEA coverage) |
| **Deliberation** | **6** | **NFR-10.1, NFR-10.3, NFR-10.4** |
| **Total** | **53** | **15 critical** |

---

---

## 18. Constraints, Assumptions & Dependencies

### 18.1 Constraints

| ID | Constraint | Type | Source |
|----|------------|------|--------|
| CON-1 | Petitions cannot self-promote to Motions | Constitutional | T4, Three Fates |
| CON-2 | Every petition must terminate in exactly one fate | Constitutional | CT-14 |
| CON-3 | All fate transitions must be witnessed | Constitutional | CT-12 |
| CON-4 | King adoption consumes promotion budget | Architectural | ADR-P4, H1 |
| CON-5 | CESSATION auto-escalation threshold is immutable (100) | Functional | CESSATION-1 |
| CON-6 | Referral timeout max 3 cycles + 2 extensions | Operational | ADR-P3 |
| CON-7 | Story 7.2 tests must pass post-migration | Compatibility | FR-9.2 |
| CON-8 | No silent petition loss (I1 invariant) | Constitutional | I1, FM-1.5 |
| CON-9 | REFUSED acknowledgment requires mandatory rationale | Policy | Critical Perspective |
| CON-10 | Co-signer uniqueness per petition enforced | Data Integrity | FM-9.1 |

### 18.2 Assumptions

| ID | Assumption | Risk if False | Mitigation |
|----|------------|---------------|------------|
| ASM-1 | Kings will review escalations in timely manner | Legitimacy decay | Dashboard alerts, decay scoring |
| ASM-2 | Identity verification sufficient for Sybil prevention | Manufactured consent | Fraud detection patterns |
| ASM-3 | 3-cycle referral timeout is acceptable to Knights | Rushed reviews | Extension mechanism (max 2) |
| ASM-4 | Observers accept ACKNOWLEDGED as valid fate | Trust erosion | Transparent reason codes, rationale |
| ASM-5 | Marquis capacity sufficient for petition volume | Bottleneck | Deputy fallback, auto-referral |
| ASM-6 | Event-sourced storage scales linearly | Storage cost | Archival policy, cold storage |
| ASM-7 | Existing promotion budget model applies to adoption | Budget contention | Monitor adoption vs organic ratio |
| ASM-8 | UUIDv7 collision probability negligible | Duplicate petitions | Collision check on insert |

### 18.3 Dependencies

| ID | Dependency | Type | Status | Impact if Unavailable |
|----|------------|------|--------|----------------------|
| DEP-1 | EventWriterService | Internal | Exists | Cannot witness fate transitions |
| DEP-2 | PromotionBudgetStore | Internal | Exists (H1) | Cannot enforce adoption budget |
| DEP-3 | Story 7.2 petition infrastructure | Internal | Complete | Must rebuild cessation from scratch |
| DEP-4 | Supabase PostgreSQL | External | Active | No persistence |
| DEP-5 | Redis (optional) | External | Available | Fall back to file-based scheduler |
| DEP-6 | King/Knight/Marquis role definitions | Internal | Partial | Cannot assign actors |
| DEP-7 | Realm assignment infrastructure | Internal | Exists | Cannot route referrals |
| DEP-8 | UUIDv7 library | External | Standard | Use UUIDv4 with timestamp prefix |

### 18.4 Integration Points

| Integration | Direction | Protocol | Notes |
|-------------|-----------|----------|-------|
| Petition Intake API | Inbound | REST | New /v1/petitions endpoint |
| Status Query API | Inbound | REST | New /v1/petitions/{id}/status |
| Co-sign API | Inbound | REST | New /v1/petitions/{id}/cosign |
| EventWriterService | Outbound | Internal | Existing witness pipeline |
| PromotionService | Outbound | Internal | For King adoption (budget) |
| Notification Service | Outbound | Internal | Observer fate notification (P1) |
| Scheduler Service | Internal | Job Queue | Referral timeout jobs |

### 18.5 Risk Register

| ID | Risk | Probability | Impact | Mitigation |
|----|------|-------------|--------|------------|
| RISK-1 | Petition flood overwhelms system | Medium | High | Rate limiting, backpressure |
| RISK-2 | Sybil attack manufactures escalation | Medium | High | Identity verification, fraud detection |
| RISK-3 | Knight vacation causes mass expiry | Low | Medium | Deputy assignment, alerts |
| RISK-4 | King ignores escalation queue | Low | High | Dashboard urgency, decay metrics |
| RISK-5 | Story 7.2 migration breaks tests | Medium | High | Dual-write, incremental migration |
| RISK-6 | Legitimacy decay metric gamed | Medium | Medium | External audit, hash chain |
| RISK-7 | Meta-petition deadlock | Low | Medium | High Archon direct handling |
| RISK-8 | Budget contention (adoption vs organic) | Medium | Medium | Separate adoption budget pool (future) |

---

---

## 19. Data Model & API Specification

### 19.1 Core Entities

#### Petition
```
Petition
├── petition_id: UUID (PK, UUIDv7)
├── petition_type: ENUM (GENERAL, CESSATION, GRIEVANCE, COLLABORATION, META)
├── state: ENUM (RECEIVED, ACKNOWLEDGED, REFERRED, ESCALATED)
├── submitter_id: UUID (FK → Identity)
├── petition_text: TEXT (max 10,000 chars)
├── proposed_realm: VARCHAR (optional)
├── submitted_at: TIMESTAMP
├── fate_at: TIMESTAMP (nullable, set when terminal)
├── version: INT (optimistic locking)
└── metadata: JSONB
```

#### PetitionFate
```
PetitionFate
├── fate_id: UUID (PK)
├── petition_id: UUID (FK → Petition)
├── fate_type: ENUM (ACKNOWLEDGED, REFERRED, ESCALATED)
├── reason_code: VARCHAR (for ACKNOWLEDGED)
├── rationale: TEXT (nullable, required for REFUSED/NO_ACTION)
├── reference_petition_id: UUID (nullable, for DUPLICATE)
├── assigned_by: UUID (FK → Actor)
├── assigned_at: TIMESTAMP
└── witnessed_event_id: UUID (FK → Event)
```

#### Referral
```
Referral
├── referral_id: UUID (PK)
├── petition_id: UUID (FK → Petition)
├── referred_to_knight_id: UUID (FK → Knight)
├── referred_by_marquis_id: UUID (FK → Marquis)
├── realm_id: VARCHAR
├── deadline: TIMESTAMP
├── extensions_used: INT (default 0, max 2)
├── status: ENUM (PENDING, COMPLETED, EXPIRED)
├── recommendation: TEXT (nullable)
├── recommendation_at: TIMESTAMP (nullable)
└── created_at: TIMESTAMP
```

#### CoSigner
```
CoSigner
├── cosign_id: UUID (PK)
├── petition_id: UUID (FK → Petition)
├── signer_id: UUID (FK → Identity)
├── signed_at: TIMESTAMP
└── UNIQUE(petition_id, signer_id)
```

#### Adoption
```
Adoption
├── adoption_id: UUID (PK)
├── petition_id: UUID (FK → Petition)
├── motion_id: UUID (FK → Motion)
├── adopted_by_king_id: UUID (FK → King)
├── budget_consumed: BOOLEAN
├── adopted_at: TIMESTAMP
└── witnessed_event_id: UUID (FK → Event)
```

#### LegitimacyMetric
```
LegitimacyMetric
├── metric_id: UUID (PK)
├── cycle_id: VARCHAR
├── total_petitions: INT
├── fated_within_sla: INT
├── decay_score: DECIMAL(5,4)
├── computed_at: TIMESTAMP
└── alert_triggered: BOOLEAN
```

### 19.2 State Transition Matrix

| FROM / TO | RECEIVED | ACKNOWLEDGED | REFERRED | ESCALATED |
|-----------|----------|--------------|----------|-----------|
| (initial) | ✓ | ✗ | ✗ | ✗ |
| RECEIVED | ✗ | ✓ | ✓ | ✓ |
| ACKNOWLEDGED | ✗ | ✗ | ✗ | ✗ |
| REFERRED | ✗ | ✓ | ✗ | ✓ |
| ESCALATED | ✗ | ✓ | ✗ | ✗ |

### 19.3 API Endpoints

| Method | Endpoint | Actor | Description |
|--------|----------|-------|-------------|
| POST | /v1/petitions | Observer | Submit new petition |
| GET | /v1/petitions/{id}/status | Observer | Query petition status |
| POST | /v1/petitions/{id}/cosign | Seeker | Add co-signature |
| POST | /v1/petitions/{id}/acknowledge | Marquis | Acknowledge petition |
| POST | /v1/petitions/{id}/refer | Marquis | Refer to Knight |
| POST | /v1/referrals/{id}/recommend | Knight | Submit recommendation |
| POST | /v1/referrals/{id}/extend | Knight | Request extension |
| POST | /v1/petitions/{id}/adopt | King | Adopt as Motion |
| DELETE | /v1/petitions/{id} | Observer | Withdraw petition |

### 19.4 API Details

#### POST /v1/petitions (Submit)
```json
Request: { "petition_type", "petition_text", "proposed_realm?", "metadata?" }
Response: { "petition_id", "state": "RECEIVED", "submitted_at", "status_token" }
Errors: 400, 429, 503
```

#### GET /v1/petitions/{id}/status
```json
Response: { "petition_id", "state", "petition_type", "co_signer_count", "fate?", "status_token" }
```

#### POST /v1/petitions/{id}/cosign
```json
Request: { "signer_id" }
Response: { "cosign_id", "co_signer_count", "escalation_triggered" }
Errors: 400, 409, 429
```

#### POST /v1/petitions/{id}/acknowledge
```json
Request: { "reason_code", "rationale?", "reference_petition_id?" }
Response: { "petition_id", "state": "ACKNOWLEDGED", "fate_id", "witnessed_event_id" }
```

#### POST /v1/petitions/{id}/refer
```json
Request: { "knight_id", "realm_id" }
Response: { "petition_id", "state": "REFERRED", "referral_id", "deadline" }
```

#### POST /v1/petitions/{id}/adopt
```json
Request: { "title", "normative_intent", "constraints", "success_criteria" }
Response: { "adoption_id", "motion_id", "source_petition_ref", "budget_consumed" }
Errors: 400, 403
```

---

---

## 20. Milestones & Release Planning

### 20.1 Release Strategy

The Petition System will be delivered in **4 milestones**, progressing from core infrastructure to full constitutional compliance.

### 20.2 Milestone 1: Foundation (P0 Core)

**Goal:** Establish petition intake, state machine, and basic acknowledgment flow.

| Deliverable | FRs Covered | NFRs Covered |
|-------------|-------------|--------------|
| Petition domain model | FR-2.1, FR-2.2 | NFR-4.1 |
| Petition intake API | FR-1.1 - FR-1.7 | NFR-1.1, NFR-3.1 |
| State machine with transitions | FR-2.3 - FR-2.6 | NFR-3.2 |
| Basic acknowledge flow (Marquis) | FR-3.1 - FR-3.3 | NFR-6.1 |
| Event witnessing integration | FR-2.5 | NFR-3.3, NFR-6.1 |
| Story 7.2 migration prep | FR-9.4 | NFR-8.2 |

**Exit Criteria:**
- Petition can be submitted and receives RECEIVED state
- Marquis can ACKNOWLEDGE with reason code
- All state transitions emit witnessed events
- No silent petition loss (FM-1.5 test)

### 20.3 Milestone 2: Referral & Escalation

**Goal:** Complete the Three Fates with referral workflow and auto-escalation.

| Deliverable | FRs Covered | NFRs Covered |
|-------------|-------------|--------------|
| Referral flow (Marquis → Knight) | FR-4.1 - FR-4.3 | NFR-3.4 |
| Referral timeout mechanism | FR-4.5 | NFR-4.4, NFR-7.5 |
| Knight recommendation API | FR-4.6 | NFR-6.3 |
| Extension mechanism | FR-4.4 | - |
| Co-signer management | FR-6.1 - FR-6.5 | NFR-3.5 |
| Auto-escalation triggers | FR-5.1 - FR-5.3 | NFR-1.4 |
| CESSATION type integration | FR-10.2 | NFR-8.1 |

**Exit Criteria:**
- Referral deadline fires reliably (FM-7.1 test)
- 100 co-signers triggers CESSATION escalation
- Knight can submit recommendation with rationale
- Story 7.2 tests pass (98/98)

### 20.4 Milestone 3: King Adoption & Visibility

**Goal:** Enable petition-to-Motion conversion and Observer visibility.

| Deliverable | FRs Covered | NFRs Covered |
|-------------|-------------|--------------|
| King escalation queue | FR-5.4 | - |
| Adoption API | FR-5.5 - FR-5.8 | NFR-6.2 |
| Budget integration | FR-5.6 | NFR-4.5, NFR-8.3 |
| Status query API | FR-7.1, FR-7.4 | NFR-1.2 |
| Long-poll status_token | FR-7.2 | - |
| Withdraw petition flow | FR-7.5 | - |
| GRIEVANCE type | FR-10.3 | - |

**Exit Criteria:**
- King can adopt petition, Motion created with source_petition_ref
- Adoption consumes promotion budget (H1 compliance)
- Observer can track petition to fate
- No double-fate possible (FM-2.3 test)

### 20.5 Milestone 4: Hardening & Metrics

**Goal:** Full constitutional compliance with legitimacy tracking and anti-gaming.

| Deliverable | FRs Covered | NFRs Covered |
|-------------|-------------|--------------|
| Rate limiting (SYBIL-1) | FR-1.5, FR-6.6 | NFR-5.1, NFR-5.2 |
| Legitimacy decay engine | FR-8.1 - FR-8.5 | NFR-7.2 |
| Orphan petition detection | - | NFR-7.1 |
| Backpressure (503) | FR-1.4 | NFR-7.4 |
| Knight load balancing | FR-4.7 | NFR-7.3 |
| Acknowledgment rate metrics | FR-3.5, FR-3.6 | - |
| META petition routing | FR-10.4 | - |
| Chaos testing | - | NFR-9.5 |

**Exit Criteria:**
- Legitimacy decay computed per cycle
- Alert fires at < 0.85 threshold
- Rate limiting prevents Sybil flood
- All 10 critical FMEA scenarios pass

### 20.6 Milestone Summary

| Milestone | Focus | FRs | Critical NFRs | Dependencies |
|-----------|-------|-----|---------------|--------------|
| M1 | Foundation | 19 | 6 | EventWriterService |
| M2 | Referral & Escalation | 17 | 5 | Scheduler, Story 7.2 |
| M3 | Adoption & Visibility | 12 | 4 | PromotionService |
| M4 | Hardening & Metrics | 10 | 6 | Redis (optional) |
| **Total** | | **58** | **21** | |

### 20.7 Dependency Graph

```
M1: Foundation
    ↓
M2: Referral & Escalation ←── Story 7.2 Migration
    ↓
M3: Adoption & Visibility ←── PromotionService (H1)
    ↓
M4: Hardening & Metrics
```

---

---

## 21. Success Metrics & KPIs

### 21.1 Constitutional Metrics (Must-Have)

| Metric | Definition | Target | Alert Threshold |
|--------|------------|--------|-----------------|
| **Silent Loss Rate** | Petitions without fate after max_age / Total petitions | 0% | > 0% |
| **Witness Coverage** | Fate transitions with witnessed event / Total fate transitions | 100% | < 100% |
| **Double-Fate Rate** | Petitions with > 1 fate record / Total fated petitions | 0% | > 0% |
| **Legitimacy Score** | Petitions fated within SLA / Total petitions per cycle | > 0.85 | < 0.85 |

### 21.2 Operational Metrics (Health Indicators)

| Metric | Definition | Target | Alert Threshold |
|--------|------------|--------|-----------------|
| **Intake Latency (p99)** | 99th percentile petition submission time | < 200ms | > 500ms |
| **Fate Assignment Latency** | Median time from RECEIVED to fate | < 3 cycles | > 5 cycles |
| **Referral Expiry Rate** | Referrals expired (EXPIRED) / Total referrals | < 10% | > 25% |
| **Orphan Petition Count** | Petitions in RECEIVED > 2 cycles | 0 | > 10 |
| **Queue Depth** | Petitions in RECEIVED state | < 1000 | > 5000 |

### 21.3 Actor Performance Metrics

| Actor | Metric | Definition | Target |
|-------|--------|------------|--------|
| **Marquis** | Triage Rate | Petitions processed per cycle | > 50 |
| **Marquis** | Rubber-stamp Score | ACKNOWLEDGEDs < 1 cycle / Total ACKNOWLEDGEDs | < 20% |
| **Knight** | Recommendation Rate | Referrals completed / Total referrals assigned | > 90% |
| **Knight** | Extension Usage | Extensions requested / Total referrals | < 30% |
| **King** | Escalation Response | Escalations addressed / Total escalations | 100% |
| **King** | Adoption Rate | Adoptions / Total escalations | (informational) |

### 21.4 Co-signer & Escalation Metrics

| Metric | Definition | Target |
|--------|------------|--------|
| **Co-sign Velocity** | Co-signatures per hour (peak) | Monitor |
| **Escalation Trigger Rate** | Auto-escalations / Total petitions | Monitor |
| **Sybil Detection Rate** | Blocked co-signs (SYBIL-1) / Total co-sign attempts | < 5% |
| **CESSATION Escalation Time** | Time from submission to 100 co-signers | Monitor |

### 21.5 Test Coverage Metrics

| Metric | Target | Gate |
|--------|--------|------|
| Unit test coverage (domain) | > 90% | M1 |
| Integration test coverage | All state transitions | M2 |
| FMEA scenario coverage | 10/10 critical | M4 |
| Story 7.2 test parity | 98/98 | M2 |
| Load test (10k petitions) | Pass | M4 |

### 21.6 Dashboard Requirements

| Phase | Milestone | Capabilities |
|-------|-----------|--------------|
| Phase 1 | M1-M2 | CLI: petition-stats, legitimacy-check |
| Phase 2 | M3 | Read-only: queue, performance, trends |
| Phase 3 | M4 | Full: alerting, drill-down, audit viewer |

---

---

## 22. Out of Scope & Future Considerations

### 22.1 Explicitly Out of Scope (This PRD)

| Item | Reason | Future Consideration |
|------|--------|---------------------|
| Mobile app for petition submission | Phase 3+ UI concern | Post-M4 enhancement |
| Multi-language petition support | Internationalization scope | Future PRD |
| Public petition discovery portal | Privacy/security implications | Requires separate analysis |
| Anonymous petition submission | Conflicts with SYBIL-1 controls | Constitutional review needed |
| Petition amendment after submission | Complicates state machine | May revisit post-M2 |
| Cross-system petition federation | Inter-Archon communication | Future architecture |
| AI-assisted petition drafting | CrewAI integration scope | Separate initiative |
| Petition clustering ML model | Simple similarity sufficient for M1-M4 | Post-M4 enhancement |
| Real-time WebSocket notifications | Long-poll sufficient initially | Phase 3+ |
| Separate adoption budget pool | Uses existing H1 budget | Monitor contention first |

### 22.2 Deferred to Future Milestones

| Item | Target Milestone | Notes |
|------|------------------|-------|
| Interactive triage UI | Post-M4 | Dashboard Phase 3 |
| Petition archival policy | Post-M4 | Storage optimization |
| Knight rotation algorithm | Post-M4 | CAPTURE-1 enhancement |
| Marquis deputy auto-assignment | Post-M4 | FM-3.4 mitigation |
| External audit API | Post-M4 | Third-party verification |

### 22.3 Open Questions

| ID | Question | Owner | Resolution Needed By |
|----|----------|-------|---------------------|
| OQ-1 | Should COLLABORATION petitions have escalation threshold? | Grand Architect | M2 |
| OQ-2 | What is max petition text length (currently 10k chars)? | Product | M1 |
| OQ-3 | Should Kings see petition submitter identity before adoption? | Constitutional | M3 |
| OQ-4 | How long before RECEIVED petitions become orphans (2 cycles proposed)? | Operations | M1 |
| OQ-5 | Should legitimacy decay be public or internal-only? | High Archon | M4 |

### 22.4 Future Enhancements (Backlog)

| Enhancement | Value | Complexity | Priority |
|-------------|-------|------------|----------|
| Petition templates by type | Reduce malformed submissions | Low | Medium |
| Co-signer notification on fate | Seeker engagement | Medium | Medium |
| Petition similarity search | Reduce duplicates | High | Low |
| Realm-specific escalation thresholds | Customization | Medium | Low |
| Petition impact scoring | Prioritization aid | High | Low |
| Integration with external identity providers | Broader Observer base | High | Future |

### 22.5 Constitutional Amendments (May Require)

| Amendment | Trigger | Process |
|-----------|---------|---------|
| CT-14 adoption | PRD approval | High Archon ratification |
| Petition-specific budget pool | Adoption contention > 30% | Motion required |
| Fourth fate (e.g., ARCHIVED) | Storage pressure | Constitutional review |
| Meta-petition escalation path | META-1 deadlock | Emergency procedure |

---

---

## 23. Sign-off & Approval

### 23.1 Document Summary

| Attribute | Value |
|-----------|-------|
| Document | Petition System PRD |
| Version | 1.0 |
| Status | **APPROVED** |
| Author | Grand Architect |
| Approved | 2026-01-18 |

### 23.2 Scope Summary

| Category | Count |
|----------|-------|
| Functional Requirements | 70 (49 P0, 20 P1, 1 P2) |
| Non-Functional Requirements | 53 (15 critical) |
| Failure Modes Analyzed | 50 (10 critical) |
| Milestones | 4 |
| API Endpoints | 9 |

**Amendment 13A (2026-01-19):** Added Three Fates Deliberation Engine (+12 FRs, +6 NFRs)

### 23.3 Constitutional Contribution

**CT-14 (Proposed):** *"Silence must be expensive. Every claim on attention terminates in a visible, witnessed fate."*

### 23.4 Next Steps

1. Create Architecture Document (`/bmad:bmm:workflows:create-architecture`)
2. Generate Epics & Stories (`/bmad:bmm:workflows:create-epics-and-stories`)
3. Plan Story 7.2 Migration
4. Begin M1: Foundation Sprint

---

**PRD APPROVED - Ready for Architecture Phase**
