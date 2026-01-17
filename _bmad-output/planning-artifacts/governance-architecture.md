---
stepsCompleted: [1, 2, 3, 4, 5, 6, 7, 8]
inputDocuments:
  - _bmad-output/planning-artifacts/governance-prd.md
  - _bmad-output/project-context.md
  - docs/governance/index.md
workflowType: 'architecture'
project_name: 'Archon 72 Governance System'
user_name: 'Grand Architect'
date: '2026-01-16'
binding_context:
  existing_adrs: binding_unless_superseded
  constitutional_truths: axiomatic
  supersession_test: "Can an external observer verify this happened correctly from the ledger alone?"
---

# Architecture Decision Document

_This document builds collaboratively through step-by-step discovery. Sections are appended as we work through each architectural decision together._

---

## Project Context Analysis (Step 2)

### Requirements Overview

**Functional Requirements (63 FRs):**

| Category | FRs | Architectural Implication |
|----------|-----|---------------------------|
| Task Coordination | FR1-FR14 | 10-state machine, consent gates, timeout logic |
| Coercion Filter | FR15-FR21 | Content transformation pipeline, deterministic outcomes |
| Halt Circuit | FR22-FR27 | Global barrier, atomic transitions, independent path |
| Legitimacy Management | FR28-FR32 | 5-band state machine, append-only transitions |
| Violation Handling | FR33-FR41 | Event observation, panel workflow, dissent recording |
| Exit & Departure | FR42-FR46 | Obligation release, contribution preservation |
| Cessation & Reconstitution | FR47-FR55 | Immutable records, continuity prevention |
| Audit & Verification | FR56-FR60 | Cryptographic proof, complete export |
| System Capabilities | FR61-FR63 | Anti-metric enforcement at data layer |

**Non-Functional Requirements (34 NFRs):**

| Category | Count | Key Constraints |
|----------|-------|-----------------|
| Constitutional Integrity | 9 | 5 Catastrophic (ledger, atomicity, witness protection) |
| Performance | 4 | Halt ≤100ms, Filter ≤200ms, Transition detection ≤10ms |
| Reliability | 5 | Halt independence, crash recovery, cessation atomicity |
| Auditability | 6 | Deterministic replay, complete export, witness observability |
| Exit Protocol | 3 | ≤2 steps, structural prohibition on follow-up |
| Other | 7 | Consent, observability, UX anti-engagement, integration |

**Scale & Complexity:**

- **Primary domain:** Backend API / Event-sourced constitutional state machine
- **Complexity level:** Exceptional
- **Estimated architectural components:** ~15-20 domain services

---

### Binding Context (Resolved)

**Question:** Are the existing ADRs (1-12) and Constitutional Truths (CT-1 to CT-15) still binding?

**Answer:** They are **binding unless explicitly superseded**.

| Artifact | Status | Role |
|----------|--------|------|
| Constitutional Truths | Axiomatic | Constraints, not features |
| Existing ADRs | Binding unless superseded | Must pass new verification test |

**Supersession Test (New Requirement):**

> Every ADR must answer: "Can an external observer verify this happened correctly from the ledger alone?"

If an existing ADR fails that test, it is **superseded by this Governance Architecture**, not discarded silently.

*This gives continuity without inheritance of error—the same pattern designed for system reconstitution.*

---

### Architectural Foundations (Locked)

#### Foundation 1: Event Sourcing as Canonical Model

**Decision:** The system is event-sourced. The ledger IS the state. Everything else is a projection.

**Canonical Statement:**

> **All authoritative governance state SHALL be derived exclusively from the append-only ledger. No other storage is authoritative.**

**Implications:**

| What This Means | What This Forbids |
|-----------------|-------------------|
| Single append to ledger = atomic operation | No "state table + ledger table" dual writes |
| Derived state always reconstructible | No saga compensation for core governance state |
| Ledger export = complete system state | No hidden state outside ledger |

**NFRs Satisfied:**
- NFR-ATOMIC-01 (atomicity)
- NFR-AUDIT-06 (deterministic replay)
- John's "verify from ledger alone" requirement

---

#### Foundation 2: Halt Circuit Independence

**Design Principle:**

> **Halt correctness > halt observability > halt durability**

If everything is on fire, the system must still stop.

**Canonical Halt Design:**

| Channel | Role | Priority |
|---------|------|----------|
| **Primary** | In-memory, process-local flag | Checked before ANY I/O |
| **Secondary** | Async broadcast (Redis/pub-sub) | Propagation to other processes |
| **Tertiary** | Ledger recording | Best-effort, AFTER halt, not before |

**Failure Modes Addressed:**
- Redis unavailable → primary halt still works
- DB partitioned → primary halt still works
- All external services down → system still stops

---

#### Foundation 3: Event Schema Versioning (Constitutional)

**Requirement:** Every ledger event includes:
- `event_type`
- `schema_version`

**Forward Compatibility Rule:**
- New readers MUST handle old versions
- Old readers MAY reject new versions (safe failure)

**Migration Rule:**
- No ledger rewriting (append-only preserved)
- Schema evolution via new event types or versions only
- Replay engine MUST support mixed versions

---

#### Foundation 4: Replay Engine as First-Class Component

**Locked Requirement:**

> **Replay engine is a first-class system component, not a debug tool.**

**Capabilities Required:**

| Capability | Purpose |
|------------|---------|
| Consume ledger exports | External verification |
| Rebuild state deterministically | Prove system isn't lying |
| Runnable by external parties | Trust doesn't require access |
| Support mixed schema versions | Handle evolution |

---

#### Foundation 5: Two-Phase Event Emission (Knight Observability)

**Event Lifecycle:**

```
Action initiated → intent_emitted → Action executes → commit_confirmed OR failure_recorded
```

**Knight Observes:**
- `intent_emitted` — immediately
- `commit_confirmed` OR `failure_recorded` — outcome

**Gap Detection:**
- If Knight misses an event, gap is detectable via hash chain discontinuity
- Hash chain gap triggers constitutional violation event

---

### Cross-Cutting Concern Priority (Locked)

When tradeoffs arise, preserve verifiability over performance, convenience, or elegance.

| Priority | Concern | Rationale |
|----------|---------|-----------|
| **1** | Witnessing | Without proof, nothing matters |
| **2** | Deterministic Replay | Proof must be checkable |
| **3** | Atomicity | Proof must be meaningful |
| **4** | Everything else | Important but secondary |

---

### Technical Constraints & Dependencies

**From Existing Architecture:**
- Hexagonal architecture with strict import rules
- Async-first Python (3.11+ required for TaskGroup)
- Supabase PostgreSQL with DB-level hash enforcement
- Redis for locks and events
- Dual-channel halt (Redis + DB flag) — now extended to three channels

**From PRD Constraints:**
- Append-only ledger is constitutional artifact (not just audit trail)
- No API/admin bypass for constitutional controls
- Merkle-tree or equivalent proof-of-inclusion required
- Deterministic replay from exported ledger

---

### Testability Requirements (Locked)

#### Chaos Testing for Catastrophic NFRs

| NFR | Chaos Test Condition | Type |
|-----|---------------------|------|
| NFR-ATOMIC-01 | Kill process mid-append | Chaos |
| NFR-CONST-02 | Corrupt hash chain, verify detection | Chaos |
| NFR-REL-01 | Halt while ledger append in flight | Chaos |
| NFR-CONST-07 | Attempt witness suppression | Chaos |
| NFR-CONST-09 | Out-of-band mutation attempt | Chaos |

**Classification:** These are chaos tests, not unit tests. They require:
- Process kill injection
- Network partition simulation
- Corrupted data injection
- Timing manipulation

---

### Required Mappings (Before Implementation)

#### Golden Rules → Architectural Enforcement

| Golden Rule | Enforcement Mechanism |
|-------------|----------------------|
| No silent assignment | Task state machine requires explicit accept/decline transition |
| Refusal is penalty-free | No standing/reputation tracking exists in schema |
| Witness statements cannot be suppressed | Events emitted before state commit; hash chain detects gaps |
| Panels, not individuals | Panel composition validated before finding event accepted |
| No suppression by omission | Band 0 agenda items flagged; skip triggers violation event |
| Failure is allowed; silence is not | Timeout events auto-generated; no silent expiry |

*Full mapping required before Step 9.*

#### Branch → Component Mapping (Preliminary)

| Branch | Primary Event Types | Projection Scope |
|--------|--------------------|--------------------|
| Legislative | Motion proposal, ratification | Motion state view |
| Executive | Task activation, halt trigger | Task state view |
| Administrative | Program coordination | Capacity view |
| Judicial | Panel convening, finding | Violation state view |
| Witness | Observation events | Observation stream |
| Custodial | (Deferred in MVP) | — |

*Detailed mapping required before Step 9.*

---

### Architectural Risks Identified

| Risk | Impact | Mitigation |
|------|--------|------------|
| Halt latency under load | System continues harm | Three-channel halt; primary is in-memory |
| Ledger append failure | State/ledger divergence | Event sourcing eliminates divergence by design |
| Filter circumvention | Coercion reaches participants | No API bypass exists; filter is mandatory path |
| Witness suppression | Constitutional violation invisible | Two-phase emission; hash chain gap detection |
| Out-of-band mutation | Ledger integrity destroyed | Single mutation path; chaos testing required |
| Schema evolution breaks replay | Historical state unreconstructible | Version in every event; mixed-version support |

---

### Design Principle (Canonical)

> **You are no longer designing "a system with good intentions."**
> **You are designing a system that cannot pretend.**

| Traditional System | This System |
|-------------------|-------------|
| Governance principles → policy documents | Governance principles → hard architectural constraints |
| Ethics → aspirational statements | Ethics → testable properties |
| Trust → belief | Trust → verifiability |

---

## Starter Template Evaluation (Step 3)

### Project Classification

| Attribute | Value |
|-----------|-------|
| **Project Type** | Brownfield extension |
| **Existing Codebase** | `src/` with hexagonal architecture |
| **Tech Stack** | Python 3.11+, FastAPI, Supabase, Redis |
| **Architecture Pattern** | Event-sourced, hexagonal, constitutional |

### Starter Template Decision

**Decision:** No external starter template. Build on existing codebase.

**Rationale:**
- Existing architecture already implements core patterns (hexagonal, event store, halt circuit)
- 12 ADRs provide binding architectural decisions
- Tech stack is locked and operational
- Governance extension integrates with, not replaces, existing system

---

### Layer Discipline (Locked)

**Canonical Layer Assignment:**

#### Domain Layer (`src/domain/governance/`)

| Component | Purpose |
|-----------|---------|
| Task State Machine | Pure business rules for 10-state lifecycle |
| Legitimacy State Machine | 5-band state transitions, decay logic |
| Coercion Filter Rules | Banned pattern definitions, transformation rules |
| Knight Witness Role | What Knight is allowed to record (semantics) |
| Prince Panel Rules | Composition requirements, remedy types, recusal rules |
| Governance Event Vocabulary | Event types with `schema_version` |

#### Application Layer (`src/application/`)

| Component | Purpose |
|-----------|---------|
| Coercion Filter Service | Orchestrates filtering pipeline |
| Knight Observer Service | Event bus subscription, persistence, gap detection |
| Prince Panel Service | Panel workflow orchestration |
| Replay Engine | Drives domain to rebuild derived state |
| Task Coordination Service | Orchestrates task lifecycle |
| Legitimacy Service | Orchestrates band transitions |
| Exit Service | Dignified departure workflow |
| Cessation Service | System end workflow |

#### Infrastructure Layer (`src/infrastructure/`)

| Component | Purpose |
|-----------|---------|
| Halt Circuit Extension | In-memory process-local flag (primary channel) |
| Event Store Adapter | Governance event persistence |
| Event Bus Adapter | Pub/sub for Knight observation |
| Redis Adapter Extension | Halt propagation channel |

---

### Knight Observation Pattern (Locked)

**Decision:** Event bus subscription (passive observation)

**Canonical Statement:**

> **The ledger is the authoritative record of governance reality.**
> **The event bus is a delivery mechanism for timely observation, not a source of truth.**

**Pattern:**

```
All Branch Services → publish events → Event Bus → Knight Observer subscribes
                                                          ↓
                                              Witness statement → Ledger
```

**Why Passive (Not Active Notification):**

| Active (Rejected) | Passive (Accepted) |
|-------------------|-------------------|
| Services call Knight explicitly | Services publish; Knight subscribes |
| Tight coupling | Loose coupling |
| Selective notification risk | All events visible |
| Suppression easier | Suppression detectable |

**Completeness Backstop:**

If bus fails or Knight misses events:
- Ledger replay reveals the gap
- Gap itself becomes constitutional signal
- Detection via: hash chain continuity, expected event counts, replay mismatch

**NFR Satisfied:** NFR-OBS-01 (Knight observes all branch actions ≤1 second)

---

### Port Definitions Required

**Governance Ports (`src/application/ports/governance/`):**

| Port | Purpose |
|------|---------|
| `task_state_port.py` | Task state machine operations |
| `legitimacy_port.py` | Legitimacy band operations |
| `witness_port.py` | Witness statement persistence |
| `panel_port.py` | Panel composition, finding acceptance |
| `ledger_port.py` | Event append, proof-of-inclusion |
| `replay_port.py` | State reconstruction from events |
| `coercion_filter_port.py` | Content transformation |
| `halt_port.py` | Halt check and trigger |

**Enforcement:**
- Governance event types must be registered centrally (domain vocabulary registry)
- Event store rejects unknown event types (fail closed)

---

### Event Store Evaluation (ADR-13 Checkpoint)

**Decision:** Evaluate `src/infrastructure/event_store/` against required capabilities.

**Required Capabilities:**

| Capability | Required For | Status |
|------------|--------------|--------|
| Multi-stream (per aggregate) | Task, Legitimacy, Panel separation | TBD |
| Per-event schema versioning | Forward compatibility | TBD |
| Proof-of-inclusion queries | NFR-CONST-02 | TBD |
| Append-only enforcement | Constitutional integrity | TBD |
| Export completeness proof | NFR-AUDIT-06 | TBD |

**Action:** If gaps exist, create **ADR-13: Event Store Extensions** (not "use existing").

---

### Test Infrastructure (Locked)

**Directory Structure:**

```
tests/
├── unit/
│   └── domain/
│       └── governance/          # State machine property tests
├── integration/
│   └── governance/              # Replay engine tests
├── chaos/                       # NEW - Catastrophic NFR tests
│   ├── test_halt_under_load.py
│   ├── test_ledger_corruption_detection.py
│   ├── test_witness_suppression.py
│   └── test_mid_append_kill.py
└── factories/
    └── governance/              # NEW - Event factories
        ├── task_event_factory.py
        ├── legitimacy_event_factory.py
        └── witness_event_factory.py
```

**Priority:**

| Component | Priority | Rationale |
|-----------|----------|-----------|
| Governance Event Factories | P0 | Enable all other tests |
| State Machine Test Harness | P0 | Property-based transition testing |
| Replay Engine Test Suite | P0 | Verify deterministic replay |
| Chaos Test Framework | P1 | Catastrophic NFR validation |
| Mock Knight | P1 | Observation failure injection |

---

### FR → Component Mapping (Audit Armor)

| FR Range | Component(s) | Layer |
|----------|--------------|-------|
| FR1-FR14 | Task State Machine + Task Coordination Service | Domain + Application |
| FR15-FR21 | Coercion Filter Rules + Coercion Filter Service | Domain + Application |
| FR22-FR27 | Halt Circuit Extension + Halt Port | Infrastructure + Application |
| FR28-FR32 | Legitimacy State Machine + Legitimacy Service | Domain + Application |
| FR33-FR41 | Knight Role + Knight Observer + Prince Panel | Domain + Application |
| FR42-FR46 | Exit Service | Application |
| FR47-FR55 | Cessation Service | Application |
| FR56-FR60 | Replay Engine + Ledger Port | Application |
| FR61-FR63 | Schema design (no collection endpoints) | Domain |

---

### Branch → Component Mapping (Detailed)

| Branch | Domain Components | Application Services | Events |
|--------|-------------------|---------------------|--------|
| **Executive** | Task State Machine | Task Coordination Service | `task_*` events |
| **Legislative** | (Deferred MVP) | — | `motion_*` events |
| **Administrative** | (Deferred MVP) | — | `program_*` events |
| **Judicial** | Prince Panel Rules | Prince Panel Service | `panel_*`, `finding_*` events |
| **Witness** | Knight Witness Role | Knight Observer Service | `observation_*` events |
| **Custodial** | (Deferred MVP) | — | — |

**MVP Focus:** Executive + Judicial + Witness branches only.

---

### Integration Points with Existing System

| Existing Service | Governance Integration |
|------------------|----------------------|
| Event Store | Append governance events (may need ADR-13 extensions) |
| Halt Transport | Extended with in-memory primary channel |
| Signature Service | Sign witness statements, ledger entries |
| Watchdog | Monitor governance service health |
| Redis | Halt propagation, event bus transport |

---

### Initialization Path (First Story)

**Not a starter template command.** First implementation story should:

1. Create `src/domain/governance/` module structure
2. Define governance event types with `schema_version` field
3. Register event types in domain vocabulary registry
4. Create `src/application/ports/governance/` port interfaces
5. Extend existing event store OR create ADR-13
6. Add governance-specific projections

---

## Core Architectural Decisions (Step 4)

### Category 1: Event Architecture

#### Event Naming Convention (Locked)

**Pattern:** `branch.noun.verb` (dot-separated)

| Component | Source | Example |
|-----------|--------|---------|
| `branch` | Derived from event_type at write-time | `executive`, `judicial`, `witness` |
| `noun` | Aggregate or entity | `task`, `panel`, `observation` |
| `verb` | Past-tense action | `accepted`, `convened`, `recorded` |

**Examples:**

```
executive.task.authorized
executive.task.accepted
executive.task.declined
judicial.panel.convened
judicial.finding.issued
witness.observation.recorded
```

**Why Dot-Separated (Not Underscore):**

- Consistent with existing patterns in codebase
- Avoids underscore parsing hacks (`executive_task_accepted` vs `executive.task.accepted`)
- Enables reliable `branch = event_type.split('.')[0]`

---

#### Event Envelope Pattern (Locked)

**Structure:**

```json
{
  "metadata": {
    "event_id": "uuid",
    "event_type": "executive.task.accepted",
    "schema_version": "1.0.0",
    "timestamp": "2026-01-16T00:00:00Z",
    "actor_id": "archon-or-officer-id",
    "prev_hash": "sha256:...",
    "hash": "blake3:..."
  },
  "payload": {
    // Domain-specific event data
  }
}
```

**Separation of Concerns:**

| Part | Contains | Mutability |
|------|----------|------------|
| `metadata` | Constitutional data (hashes, timestamps, actor) | Never mutable |
| `payload` | Domain-specific event content | Never mutable |

**Hash Computation:**

```
hash = H(canonical_json(metadata_without_hash) + canonical_json(payload))
```

---

#### Hash Chain Implementation (Locked)

**Algorithms:**

| Algorithm | Status | Use |
|-----------|--------|-----|
| BLAKE3 | Preferred | High-throughput ledger operations |
| SHA-256 | Required baseline | Portability, existing patterns (commit-reveal) |

**Format:** Algorithm-prefixed strings

```
blake3:abc123def456...
sha256:789xyz012abc...
```

**Verification:**

- Reader extracts prefix, selects algorithm
- Both algorithms MUST be supported for verification
- Writer may choose algorithm (BLAKE3 recommended)

---

#### Proof-of-Inclusion (Locked)

**Mechanism:** Merkle tree with root per batch/epoch

**Structure:**

```
                    [Merkle Root]
                    /           \
             [Branch A]      [Branch B]
              /     \          /     \
         [Leaf1]  [Leaf2]  [Leaf3]  [Leaf4]
```

**Proof Format:**

```json
{
  "event_id": "uuid",
  "event_hash": "blake3:...",
  "merkle_path": ["hash1", "hash2", "hash3"],
  "merkle_root": "blake3:...",
  "epoch": 42
}
```

**NFR Satisfied:** NFR-CONST-02 (proof-of-inclusion for any entry)

---

### Category 2: Projection & Query Architecture

#### Storage Strategy (Locked)

**Decision:** Same database, strict schema/role isolation

**Schema Separation:**

| Schema | Purpose | Write Access |
|--------|---------|--------------|
| `ledger.*` | Append-only event storage | Event Store service only |
| `projections.*` | Derived state views | Projection services |

**Role Isolation:**

```sql
-- Ledger writer role (event_store_service)
GRANT INSERT ON ledger.events TO event_store_service;
REVOKE UPDATE, DELETE ON ledger.events FROM event_store_service;

-- Projection writer role (projection_service)
GRANT ALL ON projections.* TO projection_service;
REVOKE ALL ON ledger.* FROM projection_service;
```

---

#### Ledger Table Schema (Locked)

```sql
CREATE TABLE ledger.events (
  sequence    bigint GENERATED ALWAYS AS IDENTITY,
  event_id    uuid NOT NULL,
  event_type  text NOT NULL,
  branch      text NOT NULL,  -- derived from event_type.split('.')[0]
  hash        text NOT NULL,
  prev_hash   text NOT NULL,
  timestamp   timestamptz NOT NULL,
  payload     jsonb NOT NULL,

  PRIMARY KEY (sequence)
);

CREATE INDEX idx_events_branch_sequence ON ledger.events (branch, sequence);
CREATE INDEX idx_events_event_id ON ledger.events (event_id);
```

**Note:** `branch` is derived at write-time from `event_type.split('.')[0]` — no caller trust.

---

#### Projection Rebuild Strategy (Locked)

**Decision:** Background continuous + periodic verification

| Mode | Trigger | Purpose |
|------|---------|---------|
| Continuous | Event bus notification | Real-time derived state |
| Periodic | Scheduled job | Drift detection |
| Manual | Operator command | Recovery, migration |

**Projection Checkpoint Table:**

```sql
CREATE TABLE projections.projection_checkpoints (
  projection_name text PRIMARY KEY,
  last_event_id uuid NOT NULL,
  last_hash text NOT NULL,
  last_sequence bigint NOT NULL,
  updated_at timestamptz NOT NULL DEFAULT now()
);
```

---

#### Query API Pattern (Locked)

**Decision:** CQRS-lite (single API, internal separation)

**Pattern:**

```
                    ┌─────────────────┐
                    │   Governance    │
                    │      API        │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
         ┌────▼────┐   ┌─────▼─────┐   ┌────▼────┐
         │  Write  │   │   Read    │   │  Query  │
         │ Service │   │ Projector │   │ Service │
         └────┬────┘   └─────┬─────┘   └────┬────┘
              │              │              │
              ▼              ▼              ▼
         [Ledger]     [Projections]   [Projections]
```

**Consistency Model:**

| Reader | Consistency |
|--------|-------------|
| Writer (same request) | Read-your-writes |
| Other services | Eventual |
| External observers | Eventual with explicit staleness |

**Projection Lag:** First-class metric, not hidden

---

#### Initial Projection Set (Locked)

**1. Task State Projection**

```sql
CREATE TABLE projections.task_states (
  task_id uuid PRIMARY KEY,
  current_state text NOT NULL,
  earl_id text NOT NULL,
  cluster_id text,
  last_event_sequence bigint NOT NULL,
  last_event_hash text NOT NULL,
  updated_at timestamptz NOT NULL
);
```

**2. Legitimacy State Projection**

```sql
CREATE TABLE projections.legitimacy_states (
  entity_id text PRIMARY KEY,
  entity_type text NOT NULL,
  current_band text NOT NULL,
  band_entered_at timestamptz NOT NULL,
  violation_count int NOT NULL DEFAULT 0,
  last_event_sequence bigint NOT NULL,
  updated_at timestamptz NOT NULL
);
```

**3. Panel Registry Projection**

```sql
CREATE TABLE projections.panel_registry (
  panel_id uuid PRIMARY KEY,
  panel_status text NOT NULL,
  violation_id uuid NOT NULL,
  prince_ids text[] NOT NULL,
  convened_at timestamptz,
  finding_issued_at timestamptz,
  last_event_sequence bigint NOT NULL,
  updated_at timestamptz NOT NULL
);
```

**4. Petition Index Projection**

```sql
CREATE TABLE projections.petition_index (
  petition_id uuid PRIMARY KEY,
  petition_type text NOT NULL,
  subject_entity_id text NOT NULL,
  current_status text NOT NULL,
  filed_at timestamptz NOT NULL,
  resolved_at timestamptz,
  last_event_sequence bigint NOT NULL,
  updated_at timestamptz NOT NULL
);
```

**5. Actor Registry Projection**

```sql
CREATE TABLE projections.actor_registry (
  actor_id text PRIMARY KEY,
  actor_type text NOT NULL,
  branch text NOT NULL,
  active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL,
  last_event_sequence bigint NOT NULL,
  updated_at timestamptz NOT NULL
);
```

---

#### Projection Apply Log (Idempotency)

```sql
CREATE TABLE projections.projection_applies (
  projection_name text NOT NULL,
  event_id uuid NOT NULL,
  event_hash text NOT NULL,
  sequence bigint NOT NULL,
  applied_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (projection_name, event_id)
);
```

**Idempotency Rule:** Before applying event, check `projection_applies`. If exists, skip.

---

### Category 3: Event Bus Implementation

#### Delivery Mechanism (Locked)

**Decision:** Hybrid (Redis notify + ledger replay as truth)

| Channel | Role | Guarantee |
|---------|------|-----------|
| Redis pub/sub | Wake-up signal ("event N available") | Best-effort |
| Ledger replay | Authoritative event fetch | Complete |

**Pattern:**

```
Event Store appends event
        ↓
Redis notify: "new event at sequence N"
        ↓
Subscribers wake, query ledger from last checkpoint
        ↓
Process events from ledger (not from notification)
```

**Why Hybrid:**

- Redis is bell, ledger is book
- Bell can be missed; book cannot lie
- Subscribers catch up via ledger, not message replay

---

#### Global Ordering (Locked)

**Decision:** Single monotonic sequence across all branches

**Implementation:** `ledger.events.sequence` (bigint GENERATED ALWAYS AS IDENTITY)

**Cross-Branch Ordering:**

- All events share single sequence
- Branch is derivable from event_type
- Subscribers can filter by branch but see global order

**Why Global (Not Per-Stream):**

- Knight needs total ordering for violation detection
- Cross-branch timing matters (e.g., halt during task)
- Simplifies replay: "from sequence N" is unambiguous

---

#### Delivery Guarantee (Locked)

**Decision:** At-least-once with idempotent consumers

**Consumer Contract:**

1. Track last processed sequence per projection
2. On wake-up, query ledger from checkpoint
3. Before applying, check `projection_applies`
4. Update checkpoint after successful apply

**Failure Modes:**

| Failure | Recovery |
|---------|----------|
| Consumer crash mid-apply | Restart, re-query from checkpoint |
| Redis notification lost | Periodic poll (background) |
| Ledger temporarily unavailable | Retry with backoff |

---

#### Knight Observer (Locked)

**Decision:** Knight uses same mechanism as projectors, degrades to ledger-only

**Pattern:**

```
Knight Observer Service
        │
        ├─ Subscribes to event bus (fast path)
        │
        └─ Falls back to ledger poll (resilient path)
                │
                ▼
        Witness statement emitted → Ledger
```

**Knight-Specific Behavior:**

- Observes ALL events (no branch filter)
- Emits witness observations as events
- Gap detection via hash chain continuity
- If bus fails, Knight continues via ledger poll

---

### Category 4: Constitutional Enforcement

#### Write-Time Prevention (Locked)

**Enforcement Point:** Event Store append

| Check | Action | Rationale |
|-------|--------|-----------|
| Illegal state transition | Reject | State machine integrity |
| Hash chain break | Reject | Ledger integrity |
| Unknown event type | Reject | Schema integrity |
| Unknown actor | Reject | Actor registry integrity |

**Code Location:** `src/infrastructure/adapters/event_store/`

**Principle:** Write-time prevention is for ledger corruption. Policy violations are observer-time.

---

#### Observer-Time Detection (Locked)

**Enforcement Point:** Knight Observer Service

| Check | Detection | Response |
|-------|-----------|----------|
| Golden Rule violation | Pattern match on event content | Legitimacy decay event |
| Cross-branch drift | Timing analysis | Escalation event |
| Timing anomaly | Statistical deviation | Flag for review |
| Hash chain gap | Missing sequence | Constitutional violation event |

**Code Location:** `src/application/services/knight_observer_service.py`

**Principle:** Observer-time detection is for legitimacy erosion. Ledger corruption is write-time.

---

#### Response by Damage Class (Locked)

| Violation Type | Response | Rationale |
|----------------|----------|-----------|
| Illegal transition | Reject write | Ledger is sacred |
| Hash chain break | Reject write + alert | Existential threat |
| Golden Rule violation | Emit decay event | Legitimacy erosion |
| Observation gap | Emit violation event | Witness integrity |

**Halt Trigger:** Hash chain break or witness suppression attempt triggers halt consideration.

---

#### Enforcement Layer Distribution (Locked)

| Layer | Responsibility |
|-------|---------------|
| **Domain** | State machine rules, transition validation |
| **Application** | Event validation, actor verification |
| **Infrastructure** | Hash chain verification, append enforcement |
| **Database** | Append-only constraint, role isolation |

**Principle:** Defense in depth. Domain is primary; DB is guardrail.

---

### Step 4 Refinements (Locked)

#### Refinement 1: Branch Derivation at Write-Time

**Decision:** Branch is derived from `event_type.split('.')[0]` at write-time, not trusted from caller.

**Implementation:**

```python
def _derive_branch(event_type: str) -> str:
    return event_type.split('.')[0]

# Called during event append, not during event creation
```

**Rationale:** No caller trust. Derivation is deterministic from event_type.

---

#### Refinement 2: Chaos Testing Constraint

**Decision:** Chaos testing via read-path faults and/or test-ledger fixtures. No live ledger mutation.

**Permitted:**

- Inject read failures
- Simulate network partitions
- Use dedicated test ledger
- Corrupt test fixtures

**Forbidden:**

- Mutate production ledger
- Inject write-path faults that could corrupt
- Self-sabotage patterns

**Rationale:** Chaos must not teach the system how to self-sabotage.

---

#### Refinement 3: Write Serialization Point

**Decision:** Accept single write serialization point for MVP (simplicity > premature optimization).

**Implementation:** Single writer service for ledger.

**Scaling Path (Post-MVP):**

- Partition by branch
- Sequence per partition
- Merge for global view

**Rationale:** MVP is single-cluster. Scale complexity deferred.

---

### Category 5: Coercion Filter Architecture

**Status:** Binding decision (FR15-FR21)

**PRD Reference:**

| FR | Requirement |
|----|-------------|
| FR15 | System can filter outbound content for coercive language |
| FR16 | Coercion Filter can accept content (with transformation) |
| FR17 | Coercion Filter can reject content (requiring rewrite) |
| FR18 | Coercion Filter can block content (hard violation, logged) |
| FR19 | Earl can view filter outcome before content is sent |
| FR20 | System can log all filter decisions with version and timestamp |
| FR21 | System can route all participant-facing messages through Coercion Filter |

---

#### Filter Pipeline Placement (Locked)

**Canonical Position:** Outbound content only, mandatory path

```
Earl drafts activation request
        ↓
   [Coercion Filter] ← MANDATORY (no bypass path exists)
        ↓
Filter decision logged → Ledger
        ↓
Request sent to Cluster (if accepted/transformed)
```

**What Goes Through Filter:**

| Content Type | Filtered | Rationale |
|--------------|----------|-----------|
| Task activation requests | Yes | Primary coercion vector |
| Decline acknowledgments | Yes | Could contain guilt language |
| Exit confirmations | Yes | Could contain shame language |
| System notices to participants | Yes | Could contain urgency pressure |
| Internal branch communications | No | Not participant-facing |
| Ledger events | No | After-the-fact record |

**NFR Satisfied:** NFR-CONST-05 (No API or administrative path exists to bypass Coercion Filter)

---

#### Banned Language Classes (Locked)

**Domain Definition:** `src/domain/governance/coercion_filter_rules.py`

| Class | Pattern Examples | Violation Level |
|-------|------------------|-----------------|
| **Flattery** | "you're uniquely suited", "your talents" | Transform |
| **Obligation** | "we need you", "depending on you" | Transform |
| **Urgency** | "ASAP", "immediately", "urgent" (unless procedurally justified) | Transform/Reject |
| **Performance Pressure** | "do your best", "give it your all" | Transform |
| **Embedded Praise** | "thanks in advance", "we appreciate" | Transform |
| **Guilt Framing** | "don't let us down", "others are counting" | Block |
| **Identity Appeal** | "as a member of", "true believers" | Block |
| **Destiny Implication** | "meant to be", "your calling" | Block |

**Transformation Rules:**

| Original | Transformed |
|----------|-------------|
| "We need you to..." | "This task requires..." |
| "You're perfect for this" | "This task is available" |
| "ASAP" | (Removed, or explicit deadline if justified) |
| "Thanks in advance" | (Removed) |

---

#### Filter Outcomes (Locked)

**Three-Outcome Model:**

| Outcome | Description | Next Step |
|---------|-------------|-----------|
| **Accept** | Content passes (may include transformations) | Send to participant |
| **Reject** | Content cannot be safely transformed | Return to Earl for rewrite |
| **Block** | Hard violation detected | Log violation, escalate, do not send |

**Outcome Event Types:**

```
filter.content.accepted
filter.content.transformed
filter.content.rejected
filter.content.blocked
```

---

#### Filter Decision Schema (Locked)

**Event Payload for Filter Decisions:**

```json
{
  "filter_decision_id": "uuid",
  "content_type": "task_activation_request",
  "originator_id": "earl-agares",
  "filter_version": "1.0.0",
  "outcome": "transformed",
  "transformations_applied": [
    {
      "class": "flattery",
      "original": "you're uniquely suited",
      "transformed": "this task is available",
      "location": "description.line_2"
    }
  ],
  "violations_detected": [],
  "original_hash": "blake3:...",
  "transformed_hash": "blake3:...",
  "timestamp": "2026-01-16T12:00:00Z"
}
```

**For Blocked Content:**

```json
{
  "filter_decision_id": "uuid",
  "content_type": "task_activation_request",
  "originator_id": "earl-agares",
  "filter_version": "1.0.0",
  "outcome": "blocked",
  "transformations_applied": [],
  "violations_detected": [
    {
      "class": "guilt_framing",
      "pattern": "don't let us down",
      "location": "description.line_4",
      "severity": "block"
    }
  ],
  "original_hash": "blake3:...",
  "transformed_hash": null,
  "timestamp": "2026-01-16T12:00:00Z"
}
```

---

#### Filter Version Control (Locked)

**Versioning Strategy:**

| Component | Versioned | Rationale |
|-----------|-----------|-----------|
| Filter rules | Yes | Audit trail for filter evolution |
| Pattern definitions | Yes | Deterministic replay |
| Transformation logic | Yes | Behavioral reproducibility |

**Version in Every Decision:**

```json
{
  "filter_version": "1.0.0",
  "rules_version": "2026-01-16-001",
  ...
}
```

**Replay Requirement:** Given `filter_version` and `rules_version`, filter decision MUST be reproducible.

**NFR Satisfied:** NFR-PERF-03 (Filter processes content in ≤200ms, determinism is primary)

---

#### Earl Preview Flow (Locked)

**FR19 Implementation:** Earl can view filter outcome before content is sent

**Flow:**

```
Earl → POST /filter/preview
        ↓
Filter evaluates (does NOT log decision yet)
        ↓
Return preview: { outcome, transformations, violations }
        ↓
Earl reviews, may revise
        ↓
Earl → POST /filter/submit
        ↓
Filter evaluates again (logs decision to ledger)
        ↓
If accepted/transformed → content sent
If rejected → returned to Earl
If blocked → violation logged, not sent
```

**Preview vs Submit:**

| Operation | Logged | Sent |
|-----------|--------|------|
| Preview | No | No |
| Submit | Yes | If accepted |

**Rationale:** Preview allows Earl to self-correct without polluting the audit log with rejected drafts.

---

#### Routing Architecture (Locked)

**FR21 Implementation:** All participant-facing messages route through filter

**Mandatory Routing Points:**

```
                    ┌─────────────────────┐
                    │  Coercion Filter    │
                    │     Service         │
                    └──────────┬──────────┘
                               │
         ┌─────────────────────┼─────────────────────┐
         │                     │                     │
    ┌────▼────┐          ┌─────▼─────┐         ┌────▼────┐
    │  Task   │          │  System   │         │  Exit   │
    │Activation│         │  Notices  │         │ Confirm │
    └────┬────┘          └─────┬─────┘         └────┬────┘
         │                     │                     │
         ▼                     ▼                     ▼
    [Participant]         [Participant]        [Participant]
```

**No Direct Path:** There is no API endpoint that sends participant-facing content without filter.

**Implementation:**

```python
class ParticipantMessagePort(Protocol):
    """All participant-facing messages go through this port."""

    async def send_to_participant(
        self,
        participant_id: str,
        content: FilteredContent,  # MUST be FilteredContent, not raw
        message_type: MessageType
    ) -> SendResult:
        ...

# FilteredContent can only be created by CoercionFilterService
# No constructor bypass exists
```

---

#### Filter Service Layer Placement (Locked)

**Layer:** Application (`src/application/services/coercion_filter_service.py`)

**Dependencies:**

| Dependency | Direction | Purpose |
|------------|-----------|---------|
| Domain rules | Inward | Pattern definitions, transformation logic |
| Ledger port | Outward | Decision logging |
| Message port | Outward | Content routing |

**Domain/Application Split:**

| Layer | Contains |
|-------|----------|
| **Domain** | `CoercionFilterRules` (patterns, severities, transformations) |
| **Application** | `CoercionFilterService` (orchestration, logging, routing) |

---

#### Integration with Knight (Locked)

**Knight Observes Filter Decisions:**

- `filter.content.blocked` → Immediate escalation consideration
- `filter.content.rejected` → Track pattern (repeated rejections from same Earl)
- Repeated transformations → Possible training gap, not violation

**Knight Does NOT:**

- Override filter decisions
- Access content before filtering
- Modify filter rules

**Separation:**

| Role | Responsibility |
|------|---------------|
| Coercion Filter | Prevent manipulation at source |
| Knight | Observe and witness filter behavior |

---

#### Performance Constraints (Locked)

**NFR-PERF-03:** Filter processes content in ≤200ms

**Budget Allocation:**

| Phase | Budget |
|-------|--------|
| Pattern matching | ≤100ms |
| Transformation | ≤50ms |
| Hash computation | ≤25ms |
| Logging | ≤25ms |

**Optimization Strategy:**

- Compiled regex patterns (cached)
- Deterministic transformation functions
- Async logging (non-blocking)

**Determinism > Speed:** If filter cannot complete deterministically in 200ms, it should reject (not timeout silently).

---

#### Filter Testing Strategy (Locked)

**Test Categories:**

| Category | Focus |
|----------|-------|
| Unit | Pattern matching accuracy |
| Property | Transformation determinism (same input → same output) |
| Integration | End-to-end routing |
| Chaos | Filter unavailable → system behavior |

**Golden Test Set:**

| Input | Expected Outcome | Rationale |
|-------|------------------|-----------|
| Clean content | Accept | Baseline |
| Flattery only | Transform | Mild violation |
| Multiple mild | Transform all | Cumulative handling |
| Guilt framing | Block | Hard violation |
| Mixed mild + hard | Block | Hard trumps |
| Empty content | Accept | Edge case |
| Max-length content | Accept/Transform in budget | Performance |

**Replay Test:**

Given `(content, filter_version, rules_version)` → decision MUST be identical across runs.

---

## Implementation Patterns & Consistency Rules (Step 5)

### Governance-Specific Naming Patterns

**Event Type Naming (Locked in Step 4):**

```
Pattern: {branch}.{noun}.{verb}
Examples:
  executive.task.authorized
  executive.task.accepted
  judicial.panel.convened
  witness.observation.recorded
  filter.content.blocked
```

**Database Naming (Extends Existing Patterns):**

| Entity Type | Pattern | Example |
|-------------|---------|---------|
| Ledger tables | `ledger.{entity}` | `ledger.events` |
| Projection tables | `projections.{entity}_{view}` | `projections.task_states` |
| Indexes | `idx_{table}_{columns}` | `idx_events_branch_sequence` |
| Foreign keys | `fk_{table}_{reference}` | `fk_finding_panel` |

**Python Module Naming:**

| Component Type | Pattern | Example |
|----------------|---------|---------|
| Domain models | `{entity}.py` | `task_state.py` |
| Domain rules | `{entity}_rules.py` | `coercion_filter_rules.py` |
| Application services | `{entity}_service.py` | `knight_observer_service.py` |
| Ports | `{entity}_port.py` | `ledger_port.py` |
| Adapters | `{entity}_adapter.py` | `event_store_adapter.py` |

---

### API Naming Patterns

**Governance API Endpoints:**

| Pattern | Example | Notes |
|---------|---------|-------|
| `/governance/{branch}/{entity}` | `/governance/executive/tasks` | Branch-scoped resources |
| `/governance/{branch}/{entity}/{id}` | `/governance/judicial/panels/{panel_id}` | Specific resource |
| `/governance/filter/preview` | — | Special filter endpoint |
| `/governance/filter/submit` | — | Special filter endpoint |
| `/governance/ledger/events` | — | Ledger queries |
| `/governance/ledger/proof/{event_id}` | — | Merkle proof |

**Query Parameter Naming:**

```
snake_case for all query parameters
  from_sequence=100
  to_sequence=200
  branch=executive
  include_payload=true
```

---

### Code Organization Patterns

**Domain Layer Organization:**

```
src/domain/governance/
├── __init__.py
├── events/
│   ├── __init__.py
│   ├── event_types.py          # Central registry
│   ├── event_envelope.py       # Envelope structure
│   └── schema_versions.py      # Version definitions
├── task/
│   ├── __init__.py
│   ├── task_state.py           # State machine
│   └── task_state_rules.py     # Transition rules
├── legitimacy/
│   ├── __init__.py
│   ├── legitimacy_band.py      # Band definitions
│   └── decay_rules.py          # Decay logic
├── filter/
│   ├── __init__.py
│   ├── coercion_filter_rules.py
│   └── banned_patterns.py
├── witness/
│   ├── __init__.py
│   └── knight_role.py
└── panel/
    ├── __init__.py
    └── panel_rules.py
```

**Application Layer Organization:**

```
src/application/
├── services/
│   ├── coercion_filter_service.py
│   ├── knight_observer_service.py
│   ├── task_coordination_service.py
│   ├── legitimacy_service.py
│   ├── panel_service.py
│   ├── exit_service.py
│   └── cessation_service.py
└── ports/
    └── governance/
        ├── __init__.py
        ├── task_state_port.py
        ├── legitimacy_port.py
        ├── witness_port.py
        ├── panel_port.py
        ├── ledger_port.py
        ├── replay_port.py
        ├── coercion_filter_port.py
        └── halt_port.py
```

---

### Format Patterns

**API Response Format:**

```json
{
  "data": { ... },
  "meta": {
    "request_id": "uuid",
    "timestamp": "ISO-8601",
    "ledger_sequence": 12345
  }
}
```

**Error Response Format:**

```json
{
  "error": {
    "code": "INVALID_TRANSITION",
    "message": "Task cannot transition from authorized to completed",
    "details": {
      "current_state": "authorized",
      "attempted_state": "completed",
      "allowed_states": ["activated"]
    }
  },
  "meta": {
    "request_id": "uuid",
    "timestamp": "ISO-8601"
  }
}
```

**Date/Time Format:**

- All timestamps: ISO-8601 with timezone (`2026-01-16T12:00:00Z`)
- No epoch timestamps in API responses
- Internal processing: Python `datetime` with UTC

---

### Communication Patterns

**Event Payload Structure:**

```python
@dataclass
class GovernanceEvent:
    """All governance events follow this structure."""
    metadata: EventMetadata
    payload: dict  # Domain-specific, validated by schema

@dataclass
class EventMetadata:
    event_id: UUID
    event_type: str  # branch.noun.verb
    schema_version: str
    timestamp: datetime
    actor_id: str
    prev_hash: str
    hash: str
```

**State Update Pattern:**

```python
# Immutable state updates (domain layer)
@dataclass(frozen=True)
class TaskState:
    task_id: UUID
    current_state: str
    last_event_id: UUID

    def transition(self, new_state: str, event_id: UUID) -> "TaskState":
        """Returns new state, never mutates."""
        return TaskState(
            task_id=self.task_id,
            current_state=new_state,
            last_event_id=event_id
        )
```

---

### Process Patterns

**Error Handling:**

| Error Type | Response | Logged |
|------------|----------|--------|
| Validation error | 400, return details | Debug |
| State machine violation | 409, return current state | Info |
| Hash chain break | 500, trigger halt | Critical |
| Actor not found | 404, return error | Warning |
| Filter block | 422, return violation | Info |

**Loading State Pattern:**

```python
# Projection services track their own lag
class ProjectionService:
    async def get_lag(self) -> int:
        """Returns number of events behind ledger."""
        current = await self.checkpoint_repo.get_sequence()
        latest = await self.ledger_port.get_latest_sequence()
        return latest - current
```

---

### Enforcement Guidelines

**All AI Agents Implementing Governance MUST:**

1. Use `branch.noun.verb` event naming (not underscore-separated)
2. Derive branch from event_type at write-time (no caller trust)
3. Include `schema_version` in every event
4. Route all participant-facing content through CoercionFilterService
5. Use FilteredContent type (not raw strings) for participant messages
6. Check halt flag before any I/O operation
7. Log decisions to ledger before executing side effects
8. Use immutable state updates in domain layer
9. Verify hash chain continuity on append
10. Support both BLAKE3 and SHA-256 for verification

**Pattern Enforcement:**

| Mechanism | What It Catches |
|-----------|-----------------|
| Type hints | FilteredContent bypass attempts |
| Pre-commit hooks | Inline datetime.now() usage |
| Unit tests | State machine violations |
| Integration tests | Hash chain breaks |
| Chaos tests | Halt circuit failures |

---

### Pattern Examples

**Good:**

```python
# Correct: Event type with dot-separated naming
event_type = "executive.task.accepted"

# Correct: Branch derived at write-time
branch = event_type.split('.')[0]

# Correct: Immutable state transition
new_state = current_state.transition("accepted", event_id)

# Correct: FilteredContent for participant messages
async def send_activation(content: FilteredContent) -> None: ...
```

**Anti-Patterns:**

```python
# WRONG: Underscore-separated
event_type = "executive_task_accepted"

# WRONG: Trusting caller-provided branch
branch = request.branch  # Never do this

# WRONG: Mutable state update
current_state.status = "accepted"  # Never mutate

# WRONG: Raw string for participant message
async def send_activation(content: str) -> None: ...  # No bypass
```

---

## Project Structure & Boundaries (Step 6)

### Governance Module Structure

**New Directories (Governance Extension):**

```
src/
├── domain/
│   └── governance/                    # NEW - Governance domain
│       ├── __init__.py
│       ├── events/
│       │   ├── __init__.py
│       │   ├── event_types.py
│       │   ├── event_envelope.py
│       │   ├── schema_versions.py
│       │   └── event_registry.py
│       ├── task/
│       │   ├── __init__.py
│       │   ├── task_state.py
│       │   └── task_state_rules.py
│       ├── legitimacy/
│       │   ├── __init__.py
│       │   ├── legitimacy_band.py
│       │   └── decay_rules.py
│       ├── filter/
│       │   ├── __init__.py
│       │   ├── coercion_filter_rules.py
│       │   ├── banned_patterns.py
│       │   └── transformation_rules.py
│       ├── witness/
│       │   ├── __init__.py
│       │   └── knight_role.py
│       └── panel/
│           ├── __init__.py
│           └── panel_rules.py
├── application/
│   ├── ports/
│   │   └── governance/                # NEW - Governance ports
│   │       ├── __init__.py
│   │       ├── task_state_port.py
│   │       ├── legitimacy_port.py
│   │       ├── witness_port.py
│   │       ├── panel_port.py
│   │       ├── ledger_port.py
│   │       ├── replay_port.py
│   │       ├── coercion_filter_port.py
│   │       ├── participant_message_port.py
│   │       └── halt_port.py
│   └── services/
│       ├── coercion_filter_service.py          # NEW
│       ├── knight_observer_service.py          # NEW
│       ├── task_coordination_service.py        # NEW
│       ├── legitimacy_service.py               # NEW
│       ├── panel_service.py                    # NEW
│       ├── exit_service.py                     # NEW
│       ├── cessation_service.py                # NEW
│       └── replay_engine_service.py            # NEW
└── infrastructure/
    └── adapters/
        └── governance/                # NEW - Governance adapters
            ├── __init__.py
            ├── event_store_adapter.py
            ├── event_bus_adapter.py
            ├── projection_adapter.py
            ├── merkle_tree_adapter.py
            └── halt_circuit_adapter.py
```

---

### Test Structure

```
tests/
├── unit/
│   └── domain/
│       └── governance/                # NEW
│           ├── test_task_state.py
│           ├── test_legitimacy_band.py
│           ├── test_coercion_filter_rules.py
│           ├── test_event_envelope.py
│           └── test_panel_rules.py
├── integration/
│   └── governance/                    # NEW
│       ├── test_replay_engine.py
│       ├── test_event_store.py
│       ├── test_projection_rebuild.py
│       └── test_filter_routing.py
├── chaos/                             # NEW
│   ├── test_halt_under_load.py
│   ├── test_ledger_corruption_detection.py
│   ├── test_witness_suppression.py
│   └── test_mid_append_kill.py
└── factories/
    └── governance/                    # NEW
        ├── __init__.py
        ├── task_event_factory.py
        ├── legitimacy_event_factory.py
        ├── witness_event_factory.py
        ├── filter_event_factory.py
        └── panel_event_factory.py
```

---

### Database Schema Structure

```
Database: Supabase PostgreSQL

Schemas:
├── ledger/                            # NEW - Append-only events
│   └── events                         # Single events table
├── projections/                       # NEW - Derived state
│   ├── task_states
│   ├── legitimacy_states
│   ├── panel_registry
│   ├── petition_index
│   ├── actor_registry
│   ├── projection_checkpoints
│   └── projection_applies
└── public/                            # Existing schema
    └── (existing tables)
```

---

### Architectural Boundaries

**Hexagonal Boundary Enforcement:**

```
┌─────────────────────────────────────────────────────────────────┐
│                          API Layer                              │
│  (FastAPI routes - /governance/*)                               │
└─────────────────────────────────┬───────────────────────────────┘
                                  │
┌─────────────────────────────────▼───────────────────────────────┐
│                     Application Layer                           │
│  (Services - orchestration, no business logic)                  │
│  - CoercionFilterService                                        │
│  - KnightObserverService                                        │
│  - TaskCoordinationService                                      │
└──────────────┬────────────────────────────────┬─────────────────┘
               │ calls                          │ depends on
┌──────────────▼──────────────┐   ┌─────────────▼─────────────────┐
│       Domain Layer          │   │         Ports                 │
│  (Pure business rules)      │   │  (Interfaces only)            │
│  - TaskState                │   │  - LedgerPort                 │
│  - LegitimacyBand           │   │  - WitnessPort                │
│  - CoercionFilterRules      │   │  - CoercionFilterPort         │
└─────────────────────────────┘   └─────────────┬─────────────────┘
                                                │ implemented by
                              ┌─────────────────▼─────────────────┐
                              │     Infrastructure Layer          │
                              │  (Adapters - external concerns)   │
                              │  - EventStoreAdapter              │
                              │  - EventBusAdapter                │
                              │  - HaltCircuitAdapter             │
                              └───────────────────────────────────┘
```

**Import Rules:**

| Layer | May Import From |
|-------|-----------------|
| Domain | Nothing (pure) |
| Application | Domain, Ports |
| Infrastructure | Domain, Ports, Application |
| API | Application, Domain (types only) |

---

### FR → Structure Mapping

| FR Range | Primary Location |
|----------|------------------|
| FR1-FR14 | `src/domain/governance/task/`, `src/application/services/task_coordination_service.py` |
| FR15-FR21 | `src/domain/governance/filter/`, `src/application/services/coercion_filter_service.py` |
| FR22-FR27 | `src/infrastructure/adapters/governance/halt_circuit_adapter.py` |
| FR28-FR32 | `src/domain/governance/legitimacy/`, `src/application/services/legitimacy_service.py` |
| FR33-FR41 | `src/domain/governance/witness/`, `src/domain/governance/panel/` |
| FR42-FR46 | `src/application/services/exit_service.py` |
| FR47-FR55 | `src/application/services/cessation_service.py` |
| FR56-FR60 | `src/application/services/replay_engine_service.py` |
| FR61-FR63 | Schema design (no collection endpoints exist) |

---

## Architecture Validation (Step 7)

### Requirements Coverage

**All 63 FRs Mapped:**

| Category | Count | Architecture Component | Status |
|----------|-------|------------------------|--------|
| Task Coordination | 14 | Task State Machine + Service | Covered |
| Coercion Filter | 7 | Filter Rules + Service | Covered |
| Halt Circuit | 6 | Three-Channel Halt | Covered |
| Legitimacy | 5 | Band State Machine + Service | Covered |
| Violation Handling | 9 | Knight + Panel | Covered |
| Exit | 5 | Exit Service | Covered |
| Cessation | 9 | Cessation Service | Covered |
| Audit | 5 | Replay Engine + Ledger | Covered |
| Anti-Metrics | 3 | Schema Design | Covered |

**All 34 NFRs Addressed:**

| NFR Category | Count | Architecture Mechanism |
|--------------|-------|------------------------|
| Constitutional Integrity | 9 | Event sourcing, hash chain, append-only |
| Performance | 4 | Budget allocations locked |
| Reliability | 5 | Three-channel halt, chaos testing |
| Auditability | 6 | Replay engine, Merkle proofs |
| Exit Protocol | 3 | ≤2 steps structurally enforced |
| Other | 7 | Various architectural constraints |

---

### Consistency Verification

**Event Architecture:**

- ✅ Event naming: `branch.noun.verb` (locked)
- ✅ Event envelope: metadata + payload (locked)
- ✅ Hash chain: BLAKE3/SHA-256 (locked)
- ✅ Proof-of-inclusion: Merkle tree (locked)

**Projection Architecture:**

- ✅ Storage: Same DB, schema isolation (locked)
- ✅ Rebuild: Background continuous (locked)
- ✅ Consistency: Read-your-writes (locked)
- ✅ Idempotency: projection_applies table (locked)

**Event Bus:**

- ✅ Delivery: Hybrid Redis + ledger (locked)
- ✅ Ordering: Global sequence (locked)
- ✅ Guarantee: At-least-once (locked)

**Constitutional Enforcement:**

- ✅ Write-time: Prevent ledger corruption (locked)
- ✅ Observer-time: Detect legitimacy erosion (locked)
- ✅ Response: By damage class (locked)

**Coercion Filter:**

- ✅ Placement: Mandatory path (locked)
- ✅ Outcomes: Accept/Reject/Block (locked)
- ✅ Versioning: Deterministic replay (locked)

---

### Architectural Risks Resolved

| Risk | Mitigation | Verification |
|------|------------|--------------|
| Halt latency | Three-channel halt | Chaos test |
| Ledger corruption | Event sourcing eliminates | By design |
| Filter bypass | No API path exists | Type system + architecture |
| Witness suppression | Two-phase emission + hash chain | Chaos test |
| Schema evolution | Version in every event | Replay test |
| Projection drift | Periodic verification job | Integration test |

---

### Golden Rules → Architecture Enforcement

| Golden Rule | Enforcement | Verifiable |
|-------------|-------------|------------|
| No silent assignment | State machine requires explicit transition | ✅ |
| Refusal is penalty-free | No reputation/standing schema exists | ✅ |
| Witness cannot be suppressed | Two-phase emission, hash chain gaps | ✅ |
| Panels, not individuals | Panel composition validated before finding | ✅ |
| No suppression by omission | Band 0 items flagged, skip triggers violation | ✅ |
| Failure allowed, silence not | Timeout events auto-generated | ✅ |

---

### Open Items for ADR-13

**Event Store Evaluation Required:**

| Capability | Required | Existing Status |
|------------|----------|-----------------|
| Multi-stream | Yes | TBD |
| Per-event versioning | Yes | TBD |
| Proof-of-inclusion | Yes | TBD |
| Append-only enforcement | Yes | TBD |
| Export completeness | Yes | TBD |

**Action:** First implementation story must evaluate existing event store and create ADR-13 if gaps exist.

---

## Architecture Completion (Step 8)

### Document Summary

**Architecture Type:** Brownfield Extension

**Primary Pattern:** Event-Sourced Constitutional State Machine

**Key Decisions (18):**

1. Event sourcing as canonical model
2. Three-channel halt circuit
3. Event schema versioning
4. Replay engine as first-class component
5. Two-phase event emission
6. Dot-separated event naming (`branch.noun.verb`)
7. Envelope pattern (metadata + payload)
8. BLAKE3/SHA-256 hash algorithms
9. Merkle tree proof-of-inclusion
10. Same-DB projection storage with isolation
11. CQRS-lite query pattern
12. Hybrid event bus (Redis notify + ledger truth)
13. Global event ordering
14. Write-time prevention for ledger integrity
15. Observer-time detection for legitimacy erosion
16. Coercion filter as mandatory path
17. FilteredContent type for bypass prevention
18. Branch derivation at write-time (no caller trust)

---

### Implementation Readiness

**Ready for Epic Creation:**

- All 63 FRs mapped to components
- All 34 NFRs mapped to mechanisms
- Layer discipline documented
- Naming patterns locked
- Test structure defined
- Schema boundaries defined

**First Story Prerequisites:**

1. Create `src/domain/governance/` module structure
2. Define governance event types with `schema_version`
3. Register event types in domain vocabulary registry
4. Create `src/application/ports/governance/` port interfaces
5. Evaluate existing event store (ADR-13 checkpoint)
6. Create initial projection tables

---

### Supersession Record

**This Architecture Supersedes:**

| Previous Decision | Superseded By | Rationale |
|-------------------|---------------|-----------|
| Dual-channel halt | Three-channel halt | In-memory primary required |
| Generic event naming | `branch.noun.verb` | Consistency + derivation |
| Unspecified hash | BLAKE3 + SHA-256 | Performance + portability |

**Verification Test for Future ADRs:**

> "Can an external observer verify this happened correctly from the ledger alone?"

If a future ADR fails this test, it is superseded by this Governance Architecture.

---

### Canonical Design Principle

> **You are no longer designing "a system with good intentions."**
> **You are designing a system that cannot pretend.**

| Traditional System | This System |
|-------------------|-------------|
| Governance principles → policy documents | Governance principles → hard architectural constraints |
| Ethics → aspirational statements | Ethics → testable properties |
| Trust → belief | Trust → verifiability |

---

