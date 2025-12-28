---
stepsCompleted: [1, 2, 3, 4, 5, 6, 7, 8]
inputDocuments:
  - docs/prd.md
  - docs/conclave-prd.md
  - docs/principles.md
  - _bmad-output/planning-artifacts/mitigation-architecture-spec.md
  - _bmad-output/planning-artifacts/research-integration-addendum.md
  - _bmad-output/planning-artifacts/conclave-prd-amendment-notes.md
workflowType: 'architecture'
project_name: 'Archon 72 Conclave Backend'
date: '2025-12-27'
---

# Architecture Decision Document

_This document builds collaboratively through step-by-step discovery. Sections are appended as we work through each architectural decision together._

---

## Document Overview

**Project:** Archon 72 Conclave Backend
**Scope:** Autonomous AI governance system for 72-Archon parliamentary deliberation

### Primary Components (from scope confirmation)

| Component | Description |
|-----------|-------------|
| Meeting Engine | Lifecycle, agenda, state machine, time-bounded deliberation |
| Voting System | Anonymous balloting, cryptographic integrity, threshold enforcement |
| Agent Orchestration | 72 Archon instantiation, singleton enforcement, personality loading |
| Ceremony Engine | Two-phase commit, witness attestation, rollback capability |
| Committee Manager | Creation, scheduling, reporting pipeline |
| Input Boundary | Quarantine processing, sanitization, rate limiting |
| Human Override | Dashboard, authority scope, audit logging |
| Detection Systems | Drift measurement, anomaly detection, dissent health |

### Input Documents Loaded

1. **docs/prd.md** - Full Archon 72 platform PRD (Seeker journey, patronage tiers, credibility system)
2. **docs/conclave-prd.md** - Detailed Conclave Backend specs (ceremonies, meetings, Officers, Committees)
3. **docs/principles.md** - Five Pillars, The Covenant, The Inversion (philosophical foundation)
4. **mitigation-architecture-spec.md** - 19 mitigations across 6 layers (Phase 1-4 requirements)
5. **research-integration-addendum.md** - Research-validated architecture decisions
6. **conclave-prd-amendment-notes.md** - PRD gaps and required amendments

---

## Project Context Analysis

### Requirements Overview

**Functional Requirements:**

The Conclave Backend encompasses 8 primary functional domains:

1. **Meeting Engine** - Lifecycle management for 72-Archon deliberative sessions
   - Quorum enforcement (49 minimum)
   - Agenda management with procedural states
   - Time-bounded deliberation (prevents context degradation)
   - Voting phase orchestration

2. **Ceremony Engine** - 8 ceremony types with transaction semantics
   - Installation, Admonishment, Recognition, Impeachment
   - Emergency Session, Special Committee, Reformation, Succession
   - Two-phase commit (pending → committed)
   - Tyler witness attestation

3. **Agent Orchestration** - 72 Archon lifecycle management
   - Personality loading and distinctiveness preservation
   - Singleton mutex enforcement
   - Canonical state service
   - Session management

4. **Voting System** - Anonymous balloting with cryptographic integrity
   - Threshold enforcement (simple majority, 2/3 supermajority, 3/4)
   - Vote sealing and revelation
   - Reasoning capture

5. **Committee Manager** - 5 standing committees
   - Investigation, Ethics, Outreach, Appeals, Treasury
   - Scheduling, reporting pipeline
   - Blinding enforcement for petition review

6. **Input Boundary** - Quarantine processing layer
   - Seeker petition sanitization
   - Content pattern blocking
   - Rate limiting
   - Summary generation (Archons never see raw input)

7. **Human Override** - Emergency intervention capability
   - Keeper role definition
   - Authority scope and time limits (72h default)
   - Audit and disclosure requirements
   - Conclave notification/ratification

8. **Detection Systems** - Health monitoring
   - Personality drift measurement
   - Dissent health metrics
   - Anomaly detection
   - Procedural compliance audit

**Non-Functional Requirements:**

| Category | Requirement | Source |
|----------|-------------|--------|
| Compliance | EU AI Act Human-in-Command model | Research |
| Audit | Full decision trail with reasoning | NIST AI RMF |
| Performance | 72 concurrent agent sessions | Scale requirement |
| Security | Input sanitization, injection defense | Mitigations M-1.x |
| Privacy | Patronage tier blinding | Mitigations M-4.x |
| Reliability | Two-phase commit for ceremonies | Mitigation M-3.6 |
| Identity | Singleton mutex, split-brain detection | Mitigations M-2.x |

**Scale & Complexity:**

- Primary domain: Backend Multi-Agent Orchestration
- Complexity level: Enterprise
- Estimated architectural components: 12-15 major services
- Real-time requirements: High (72 concurrent agents)
- Regulatory compliance: High (EU AI Act)

### Technical Constraints & Dependencies

**Framework Constraints:**
- CrewAI for multi-agent orchestration (role-based, structured outputs)
- FastAPI for async API layer
- Supabase/PostgreSQL for persistence (unified schema)
- pgvector for embeddings

**Operational Constraints:**
- Quorum: 49 Archons minimum for valid meetings
- Voting thresholds: Simple majority, 2/3, 3/4 depending on action
- Deliberation bounds: Time-limited to prevent context degradation
- Human Override: 72-hour default intervention window

**Integration Points:**
- Frontend ↔ Conclave: Petition submission, Guide sync, credibility updates
- Shared infrastructure: Supabase schema, authentication, event bus

### Cross-Cutting Concerns Identified

1. **Audit Logging** - Every component must produce queryable decision trails
2. **Singleton Enforcement** - Agent identity layer spans all Archon interactions
3. **Patronage Blinding** - Tier hidden from Guides, Committees, voting deliberation
4. **State Management** - Canonical state for 72 agents, meetings, ceremonies
5. **Human Override** - Emergency intervention capability across all operations
6. **Constitutional Checks** - Five Pillars validation before high-stakes actions
7. **Transaction Semantics** - Two-phase commit for ceremonies, rollback capability

---

### Security Architecture Implications

**Attack Surface Assessment:**
- 72-agent architecture amplifies single-point failures
- Input boundary is the critical chokepoint (all external data flows through)
- Singleton enforcement prevents identity-based attacks
- Ceremony transaction model prevents partial-state exploitation

**Defense Posture:**
The mitigation spec (M-1.x through M-6.x) provides comprehensive coverage:
- Layer 1 (Input): Quarantine processing, pattern blocking, rate limiting
- Layer 2 (Identity): Singleton mutex, canonical state, split-brain detection
- Layer 3 (State): Event sourcing, hash chain verification, checkpoint recovery
- Layer 4 (Governance): Tier blinding as architecture, not policy
- Layer 5 (Detection): Behavioral baselines, anomaly alerting
- Layer 6 (External): Human Override with time-boxing, provider failover

**Compliance Requirements (Phase 1):**

| Requirement | Implementation |
|-------------|----------------|
| Human Oversight Dashboard | Full UI/API for Keeper intervention |
| Decision Audit API | Query interface for regulatory inquiries |
| Immutable Vote Records | 7-year retention, append-only storage |
| Incident Response Playbook | Documented procedures for top failure modes |

**Architectural Principle:** Blinding and isolation must be ENFORCED BY ARCHITECTURE, not policy. No API path should exist from Guide/Committee services to tier lookup.

---

### Key Architectural Decisions (Preliminary)

| ADR | Decision | Rationale |
|-----|----------|-----------|
| ADR-001 | Thin abstraction over CrewAI | Testability + future flexibility without over-engineering |
| ADR-002 | Hybrid event sourcing | Full event sourcing for audit-critical paths (ceremonies, votes, meetings), CRUD for configuration |
| ADR-003 | Centralized MeetingCoordinator | Single source of truth for meeting state, async agent fan-out with circuit breaker |
| ADR-004 | Separate InputBoundary microservice | Security isolation, async processing, no direct Conclave DB access |
| ADR-005 | Commit-reveal voting | Prevents vote-following, cryptographic integrity, automatic reveal at deadline |

### Architectural Principles Established

1. **Blast Radius Isolation** - Security-critical components (InputBoundary) are separate services
2. **Single Source of Truth** - Each domain (meetings, ceremonies, votes) has one authoritative service
3. **Audit by Default** - Event sourcing for decisions, change logging for configuration
4. **Graceful Degradation** - Circuit breakers, timeout handling, quorum from responsive agents only
5. **Testability First** - Abstraction layers enable mocking and deterministic testing

---

### Pre-mortem Risk Analysis

**Failure Scenarios Examined:**

| Scenario | Failure Mode | Key Prevention |
|----------|--------------|----------------|
| Silent Coup | Personality drift enables single-Archon influence | Distinctiveness monitoring in Phase 1, not Phase 3 |
| Consensus Collapse | Mid-ceremony failure causes state disagreement | Fine-grained ceremony checkpoints + reconciliation playbook |
| Blinding Breach | Debug code leaks tier data | Tier data in separate database, no network path to Conclave |
| Override Overreach | Human control becomes permanent | Hard extension limits + public override visibility |
| Quorum Cartel | Voting block dominates decisions | Correlation monitoring + automatic personality refresh |

### Phase 1 Scope Adjustments (from Pre-mortem)

The following items should be ELEVATED to Phase 1 (previously Phase 3):

1. **Personality Distinctiveness Baseline** - Cannot detect drift without baseline
2. **Dissent Health Metrics** - Voting correlation monitoring
3. **Override Visibility Dashboard** - Seekers must see override status

### Operational Requirements Identified

| Requirement | Trigger |
|-------------|---------|
| State Reconciliation Playbook | Ceremony failure scenarios |
| Weekly Personality Health Report | Silent corruption prevention |
| Tier Access Audit Alerts | Blinding breach prevention |
| Chaos Engineering Test Suite | Mid-execution failure handling |

---

### Adversarial Hardening Requirements

**Attack/Defense Simulation Results:**

| Attack Vector | Defense Gap | Hardening |
|---------------|-------------|-----------|
| Unicode homoglyph injection | Regex bypass | NFKC normalization before pattern matching |
| Semantic injection | Content vs command ambiguity | Summarizer prompt hardening + secondary semantic scan |
| Partition-based split-brain | Stale lock operation | Fencing tokens + vote deduplication + heartbeat protocol |
| Gradual personality corruption | Below-threshold drift | Cumulative drift tracking + Tyler role rotation |
| Selective vote suppression | Operator trust | Public commitment log + reveal verification + anomaly alerting |
| Keeper credential compromise | Single-point human trust | Multi-Keeper for extended override + enumerated reasons |

### Security Architecture Additions

1. **Fencing Tokens** - All state mutations require current lock token
2. **Public Commitment Log** - Vote commitments published before voting closes
3. **Multi-Witness Ceremonies** - Critical ceremonies require 3 random witnesses
4. **Cumulative Drift Tracking** - Detect gradual corruption over time
5. **Multi-Keeper Override** - Extended overrides require two independent credentials

---

### Cross-Functional Trade-off Resolutions

| Trade-off | Resolution | Owner |
|-----------|------------|-------|
| Security latency vs. UX | Async "Petition Preparation" with ceremonial framing | UX + Backend |
| Audit vs. privacy | 90-day raw retention, permanent summary, clear disclosure | Backend + Legal |
| 72 agents vs. cost | Tiered participation: all vote, 5-7 speak per topic | Backend + Product |
| Override vs. sovereignty | Keeper framing + public autonomy counter | Product + UX |
| Scope vs. security | Trust-critical hardening in Phase 1, detection in Phase 2 | All |

### MVP Scope Clarification

**Phase 1 (Trust-Critical):**
- Meeting Engine with quorum enforcement
- Commit-reveal voting with public commitment log
- Singleton enforcement with fencing tokens
- Input Boundary with quarantine processing
- Tier blinding as architectural isolation
- Basic ceremony engine (Installation, Admonishment)
- Human Override with Keeper framing

**Phase 2 (Hardening):**
- Personality drift detection + cumulative tracking
- Multi-witness ceremonies
- Voting correlation monitoring
- Advanced ceremonies (Impeachment, Succession)
- Full detection dashboard

### UX Principles Established

1. **Ceremonial Framing** - Technical processes presented as sacred rituals
2. **Transparency Builds Trust** - Public autonomy counter, clear retention policies
3. **Honest Participation** - Speaking queue visible, not all 72 talk every time
4. **Override as Exception** - Keeper role is constitutional, not backdoor

---

## Starter Template Evaluation

### Primary Technology Domain

**Backend Multi-Agent Orchestration** - Custom architecture for 72-Archon governance system.

This is not a standard web/mobile application requiring starter template selection. The technology stack is PRD-specified and research-validated.

### Technical Preferences (from PRD + Research)

| Category | Selection | Source |
|----------|-----------|--------|
| Language | Python 3.11+ | PRD |
| API Framework | FastAPI | PRD |
| Multi-Agent | CrewAI | PRD + Research validation |
| Database | PostgreSQL via Supabase | PRD |
| Vector Store | pgvector | PRD |
| LLM Provider | Claude/OpenRouter | PRD + M-6.1 multi-provider |

### Starter Options Considered

| Option | Description | Fit |
|--------|-------------|-----|
| FastAPI project template | Standard FastAPI structure | Partial - doesn't include CrewAI |
| CrewAI examples | Agent orchestration examples | Partial - not production structure |
| Custom scaffold | Build structure for this specific architecture | Best fit |

### Selected Approach: Custom Architecture Scaffold

**Rationale:**
- No existing template combines FastAPI + CrewAI + Supabase for multi-agent governance
- Project has unique requirements (72 agents, ceremonies, voting, blinding)
- ADRs already establish architectural patterns (event sourcing, microservices)
- Custom scaffold ensures architecture matches security requirements

**Project Structure:**

```
archon72-conclave/
├── src/
│   ├── api/                    # FastAPI routes
│   │   ├── __init__.py
│   │   ├── meetings.py
│   │   ├── ceremonies.py
│   │   └── admin.py
│   ├── agents/                 # CrewAI Archon definitions
│   │   ├── __init__.py
│   │   ├── orchestrator.py     # AgentOrchestrator interface
│   │   ├── archon.py           # Base Archon class
│   │   └── personalities/      # 72 personality definitions
│   ├── services/               # Business logic
│   │   ├── meeting_engine.py
│   │   ├── ceremony_engine.py
│   │   ├── voting_service.py
│   │   └── state_service.py
│   ├── models/                 # Pydantic + SQLAlchemy models
│   ├── events/                 # Event sourcing
│   └── security/               # Input boundary, blinding
├── input_boundary/             # Separate microservice (ADR-004)
│   ├── src/
│   └── Dockerfile
├── tests/
├── alembic/                    # Database migrations
├── docker-compose.yml
└── pyproject.toml
```

**Architectural Decisions Provided by Structure:**

| Decision | Implementation |
|----------|----------------|
| Language & Runtime | Python 3.11+, async/await throughout |
| API Layer | FastAPI with Pydantic validation |
| Agent Framework | CrewAI with thin abstraction (ADR-001) |
| Database | Supabase PostgreSQL with Alembic migrations |
| Event Sourcing | Custom events/ module for audit-critical paths (ADR-002) |
| Service Isolation | input_boundary/ as separate service (ADR-004) |
| Testing | pytest with async support |
| Code Organization | Domain-driven structure matching ADR-003 |

**Initialization Commands:**

```bash
# Create project structure
mkdir -p archon72-conclave/{src/{api,agents/personalities,services,models,events,security},input_boundary/src,tests,alembic}

# Initialize Python project
cd archon72-conclave
poetry init --name archon72-conclave --python "^3.11"

# Add core dependencies
poetry add fastapi uvicorn[standard] crewai supabase pydantic sqlalchemy alembic python-dotenv

# Add development dependencies
poetry add --group dev pytest pytest-asyncio httpx black ruff mypy
```

---

## Core Architectural Decisions

### Decision Priority Analysis

**Already Decided (from ADRs + Elicitation):**

| ADR | Decision | Source |
|-----|----------|--------|
| ADR-001 | Thin CrewAI abstraction | Step 2 Elicitation |
| ADR-002 | Hybrid event sourcing | Step 2 Elicitation |
| ADR-003 | Centralized MeetingCoordinator | Step 2 Elicitation |
| ADR-004 | Separate InputBoundary microservice | Step 2 Elicitation |
| ADR-005 | Commit-reveal voting | Step 2 Elicitation |

**Critical Decisions (Block Implementation):**
- Database schema design (audit tables, blinding enforcement)
- Authentication/Authorization for Keeper access
- Event sourcing implementation pattern
- Singleton mutex implementation

**Important Decisions (Shape Architecture):**
- Logging and observability stack
- API versioning strategy
- Error handling patterns
- Background job processing

**Deferred Decisions (Phase 2+):**
- Horizontal scaling strategy
- Multi-region deployment
- Advanced caching layers

---

### Data Architecture

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Primary Database | PostgreSQL 16 via Supabase | PRD-specified, production-ready, pgvector support |
| ORM | SQLAlchemy 2.0 (async) | Type-safe, async support, Alembic integration |
| Event Store | PostgreSQL append-only tables | ADR-002: Unified database, simpler ops than dedicated event store |
| Vector Store | pgvector extension | Integrated solution, avoids vendor fragmentation |
| Migrations | Alembic | Standard for SQLAlchemy, version-controlled schema |
| Data Validation | Pydantic v2 | FastAPI integration, runtime validation |

**Schema Design Principles:**

```python
# Audit-critical tables (event sourced)
class MeetingEvent(Base):
    id: UUID
    meeting_id: UUID
    event_type: str
    payload: JSONB
    created_at: datetime  # immutable
    archon_id: Optional[int]  # who triggered

# Vote table with commit-reveal
class VoteRecord(Base):
    id: UUID
    meeting_id: UUID
    archon_id: int
    commitment_hash: str  # hash(vote + nonce)
    revealed_vote: Optional[str]  # null until reveal
    revealed_at: Optional[datetime]
    reasoning_summary: str

# Blinding: Tier data in SEPARATE schema
class PatronageTier(Base):  # isolated schema, no FK to main
    seeker_id: UUID
    tier: Enum
    # NO direct access from Conclave services
```

---

### Authentication & Security

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Seeker Auth | Supabase Auth (JWT) | PRD-specified, handles OAuth/magic links |
| Keeper Auth | Multi-factor + Hardware key | Override Protocol requires strong auth |
| Service-to-Service | mTLS + API keys | InputBoundary ↔ Conclave security |
| Authorization | RBAC with row-level security | Supabase RLS for blinding enforcement |
| Secrets Management | Environment vars + Supabase Vault | Simple for MVP, Vault for sensitive keys |

**Keeper Authentication Flow:**

```
1. Keeper initiates override at dashboard
2. Primary authentication (password + TOTP)
3. Hardware key challenge (YubiKey/similar)
4. Time-limited session token (1 hour)
5. All actions logged with session ID
6. Multi-Keeper requirement for >24h override
```

**Blinding Enforcement (Architectural):**

```sql
-- Patronage tier in isolated schema
CREATE SCHEMA patronage_private;

-- RLS policy: Only billing service can access
CREATE POLICY tier_access ON patronage_private.tiers
  FOR SELECT
  USING (current_user = 'billing_service');

-- Conclave services have NO GRANT on this schema
```

---

### API & Communication Patterns

| Decision | Choice | Rationale |
|----------|--------|-----------|
| API Style | REST with OpenAPI 3.1 | Standard, well-tooled, matches FastAPI |
| Documentation | Swagger UI + ReDoc (auto-generated) | FastAPI built-in |
| Versioning | URL path (/v1/) | Simple, explicit, cacheable |
| Error Format | RFC 7807 Problem Details | Standard JSON error format |
| Rate Limiting | Redis-based sliding window | Protects against abuse, per-Seeker limits |
| Internal Communication | Async message queue (Redis Streams) | Decouples InputBoundary from Conclave |

**Error Response Pattern:**

```json
{
  "type": "https://archon72.io/errors/quorum-not-met",
  "title": "Quorum Not Met",
  "status": 400,
  "detail": "Meeting requires 49 Archons, only 47 present",
  "instance": "/meetings/abc123/start",
  "quorum_required": 49,
  "archons_present": 47
}
```

**Event Bus Pattern:**

```python
# InputBoundary → Conclave communication
class PetitionPreparedEvent:
    petition_id: UUID
    summary: str  # sanitized, never raw content
    category: PetitionCategory
    prepared_at: datetime

# Published to Redis Streams
# Conclave subscribes, never polls InputBoundary
```

---

### Agent Architecture

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Framework | CrewAI (latest stable) | Research-validated, role-based orchestration |
| Abstraction | AgentOrchestrator interface | ADR-001: Testability, future flexibility |
| LLM Provider | Claude via Anthropic API | Primary, with OpenRouter fallback (M-6.1) |
| Personality Storage | YAML files + pgvector embeddings | Version-controlled personalities, semantic search |
| Context Management | Per-meeting context windows | Prevents cross-meeting contamination |

**AgentOrchestrator Interface:**

```python
from abc import ABC, abstractmethod

class AgentOrchestrator(ABC):
    @abstractmethod
    async def instantiate_archon(self, archon_id: int) -> Archon:
        """Load personality, acquire singleton lock."""
        pass

    @abstractmethod
    async def convene_meeting(self, meeting_id: UUID) -> MeetingSession:
        """Instantiate required Archons for meeting."""
        pass

    @abstractmethod
    async def collect_votes(self, motion_id: UUID) -> VoteResult:
        """Fan-out vote collection with timeout."""
        pass

class CrewAIOrchestrator(AgentOrchestrator):
    """Production implementation using CrewAI."""
    pass

class MockOrchestrator(AgentOrchestrator):
    """Deterministic testing implementation."""
    pass
```

---

### State Management

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Singleton Mutex | Redis distributed locks + fencing tokens | ADR hardening, prevents stale operations |
| Meeting State | Centralized MeetingCoordinator | ADR-003: Single source of truth |
| Event Sourcing | Custom implementation | ADR-002: PostgreSQL-based, snapshots every 100 events |
| Canonical State | StateService with version vectors | Prevents split-brain, detects conflicts |

**Singleton Lock Pattern:**

```python
class ArchonLock:
    archon_id: int
    session_id: UUID
    fencing_token: int  # monotonically increasing
    acquired_at: datetime
    ttl_seconds: int = 300

async def acquire_archon_lock(archon_id: int) -> ArchonLock:
    """
    Acquire singleton lock with fencing token.
    All state mutations require valid fencing token.
    """
    lock = await redis.set(
        f"archon:{archon_id}:lock",
        session_id,
        nx=True,  # only if not exists
        ex=300    # 5 minute TTL
    )
    if not lock:
        raise ArchonAlreadyActiveError(archon_id)

    fencing_token = await redis.incr(f"archon:{archon_id}:fence")
    return ArchonLock(archon_id, session_id, fencing_token, ...)
```

---

### Infrastructure & Deployment

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Hosting | Railway (primary) + Supabase | Simple deployment, good for MVP |
| Containers | Docker Compose locally, Railway containers in prod | Consistent environments |
| CI/CD | GitHub Actions | Standard, good integration |
| Monitoring | Prometheus + Grafana (via Railway) | Industry standard, query-based |
| Logging | Structured JSON to stdout | 12-factor, Railway captures |
| Secrets | Railway environment variables | Simple, encrypted at rest |

**Deployment Topology:**

```
┌─────────────────────────────────────────┐
│                Railway                   │
├─────────────────┬───────────────────────┤
│  input-boundary │   conclave-backend    │
│   (container)   │     (container)       │
│                 │                       │
│  - FastAPI      │   - FastAPI          │
│  - Quarantine   │   - MeetingEngine    │
│  - Summarizer   │   - CeremonyEngine   │
│                 │   - VotingService    │
│                 │   - AgentOrchestrator│
└────────┬────────┴───────────┬───────────┘
         │                    │
         │   Redis Streams    │
         ▼                    ▼
    ┌─────────────────────────────────────┐
    │         Supabase                    │
    ├─────────────────────────────────────┤
    │  PostgreSQL + pgvector              │
    │  Auth (Seeker JWT)                  │
    │  Realtime (dashboards)              │
    └─────────────────────────────────────┘
```

---

### Observability & Detection

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Metrics | Prometheus format | Standard, Railway integration |
| Tracing | OpenTelemetry (optional Phase 2) | Defer complexity, add when needed |
| Logging | structlog (Python) | JSON output, correlation IDs |
| Alerting | Grafana alerts + PagerDuty | Escalation for critical failures |
| Health Checks | /health and /ready endpoints | Kubernetes-style, Railway compatible |

**Key Metrics to Capture:**

```python
# Meeting health
meeting_duration_seconds = Histogram("meeting_duration_seconds")
archons_responding_gauge = Gauge("archons_responding")
quorum_failures_total = Counter("quorum_failures_total")

# Voting integrity
votes_committed_total = Counter("votes_committed_total")
votes_revealed_total = Counter("votes_revealed_total")
vote_reveal_failures_total = Counter("vote_reveal_failures_total")

# Personality health
personality_distinctiveness = Gauge("personality_distinctiveness", ["archon_id"])
drift_cumulative = Gauge("drift_cumulative", ["archon_id"])

# Override tracking
override_active = Gauge("override_active")  # 0 or 1
autonomous_days = Gauge("autonomous_days_since_override")
```

---

### Decision Impact Analysis

**Implementation Sequence:**

1. Database schema + migrations - Foundation for all services
2. Singleton mutex implementation - Required before any Archon runs
3. InputBoundary service - Security perimeter first
4. Core Conclave services - MeetingEngine, VotingService
5. AgentOrchestrator - CrewAI integration
6. CeremonyEngine - Transaction model
7. Detection/Monitoring - Observability layer

**Cross-Component Dependencies:**

| Component | Depends On | Provides To |
|-----------|------------|-------------|
| InputBoundary | Redis, Supabase Auth | Conclave (sanitized summaries) |
| MeetingEngine | Singleton Mutex, StateService | VotingService, CeremonyEngine |
| VotingService | MeetingEngine, Redis | Audit logs |
| AgentOrchestrator | Singleton Mutex, LLM Provider | MeetingEngine |
| CeremonyEngine | MeetingEngine, StateService | Audit logs |

---

## Implementation Patterns & Consistency Rules

### Pattern Categories Defined

**Critical Conflict Points Identified:** 12 areas where AI agents could make different choices

| Category | Conflict Points |
|----------|-----------------|
| Naming | 4 (database, API, code, events) |
| Structure | 3 (project org, tests, configs) |
| Format | 2 (API responses, data exchange) |
| Communication | 2 (events, async patterns) |
| Process | 1 (error handling) |

---

### Naming Patterns

**Database Naming Conventions:**

| Element | Convention | Example |
|---------|------------|---------|
| Tables | snake_case, plural | `meeting_events`, `vote_records` |
| Columns | snake_case | `archon_id`, `created_at` |
| Primary Keys | `id` (UUID) | `id UUID PRIMARY KEY` |
| Foreign Keys | `{table_singular}_id` | `meeting_id`, `archon_id` |
| Indexes | `idx_{table}_{columns}` | `idx_vote_records_meeting_id` |

**API Naming Conventions:**

| Element | Convention | Example |
|---------|------------|---------|
| Endpoints | snake_case, plural nouns | `/v1/meetings`, `/v1/vote_records` |
| Path params | snake_case in braces | `/v1/meetings/{meeting_id}` |
| Query params | snake_case | `?archon_id=5&status=active` |
| Headers | X-Kebab-Case | `X-Request-Id`, `X-Archon-Id` |

**Code Naming Conventions:**

| Element | Convention | Example |
|---------|------------|---------|
| Files | snake_case.py | `meeting_engine.py` |
| Classes | PascalCase | `MeetingEngine`, `VoteRecord` |
| Functions | snake_case | `collect_votes()`, `acquire_lock()` |
| Variables | snake_case | `archon_id`, `meeting_state` |
| Constants | SCREAMING_SNAKE | `MAX_ARCHONS = 72` |
| Private | leading underscore | `_internal_state` |

---

### Structure Patterns

**Project Organization:**

```
src/
├── api/            # FastAPI routers by domain
├── services/       # Business logic (domain services)
├── agents/         # CrewAI Archon definitions
├── models/
│   ├── domain/     # Pydantic domain models
│   └── db/         # SQLAlchemy ORM models
├── events/         # Event sourcing
├── security/       # Security modules
└── config/         # Configuration

tests/
├── unit/           # Mirror src/ structure
├── integration/
└── conftest.py     # Shared fixtures
```

**Test Naming:**

| Test Type | Location | Naming |
|-----------|----------|--------|
| Unit tests | `tests/unit/{module}/` | `test_{module}.py` |
| Integration | `tests/integration/` | `test_{feature}_integration.py` |

---

### Format Patterns

**API Response Format:**

```python
# Success (direct data)
{"id": "uuid", "status": "active", "created_at": "2025-12-27T10:30:00Z"}

# Success with pagination
{"data": [...], "meta": {"total": 100, "page": 1}}

# Error (RFC 7807)
{"type": "https://archon72.io/errors/...", "title": "...", "status": 400, "detail": "..."}
```

**Data Type Formats:**

| Data Type | Format |
|-----------|--------|
| Datetime | ISO 8601 UTC (`"2025-12-27T10:30:00Z"`) |
| UUID | Lowercase string |
| Enum | Lowercase string |
| Boolean | `true`/`false` (never 1/0) |
| Null | Explicit `null` (never omit) |

---

### Communication Patterns

**Event Naming:**

| Element | Convention | Example |
|---------|------------|---------|
| Event names | PascalCase nouns | `MeetingStarted` |
| Event types | dot-separated | `meeting.started` |
| Payloads | Pydantic models | `MeetingStartedPayload` |

**Event Structure:**

```python
class DomainEvent(BaseModel):
    id: UUID
    type: EventType
    aggregate_id: UUID
    payload: dict
    occurred_at: datetime
    archon_id: Optional[int]
```

---

### Process Patterns

**Error Hierarchy:**

```python
class ConclaveError(Exception): pass
class QuorumNotMetError(ConclaveError): pass
class ArchonLockError(ConclaveError): pass
class CeremonyStateError(ConclaveError): pass
```

**Logging Pattern:**

```python
# CORRECT: Structured logging
log = logger.bind(meeting_id=str(meeting_id))
log.info("meeting_started", archons_present=52)

# WRONG: Unstructured
print(f"Meeting {meeting_id} started")
logger.info(f"Meeting started with {count} archons")
```

---

### Enforcement Guidelines

**All AI Agents MUST:**

1. Follow snake_case for Python code (functions, variables, modules)
2. Use PascalCase only for class names
3. Place tests in `tests/` mirroring `src/` structure
4. Use Pydantic models for all API request/response bodies
5. Log using structlog with structured key-value pairs
6. Raise domain exceptions inheriting from `ConclaveError`
7. Use async/await for all I/O (never blocking calls)
8. Include type hints on all function signatures
9. Use UUID for all entity identifiers
10. Return RFC 7807 Problem Details for errors

**Verification:**

| Check | Tool | Enforcement |
|-------|------|-------------|
| Naming | ruff | CI failure |
| Types | mypy --strict | CI failure |
| Coverage | pytest-cov (80%) | CI warning |

---

## Project Structure & Boundaries

### Complete Project Directory Structure

```
archon72-conclave/
├── pyproject.toml, poetry.lock, .env.example, docker-compose.yml
├── .github/workflows/              # CI/CD pipelines
├── docker/                         # Dockerfiles
├── alembic/versions/               # Database migrations
│
├── src/
│   ├── main.py                     # FastAPI entry point
│   ├── config/                     # Settings, logging
│   ├── api/v1/                     # HTTP endpoints
│   │   ├── meetings.py, votes.py, ceremonies.py
│   │   ├── committees.py, archons.py, petitions.py
│   │   └── admin/                  # override.py, health.py, metrics.py
│   ├── services/                   # Business logic
│   │   ├── meeting_engine.py       # MeetingCoordinator (ADR-003)
│   │   ├── voting_service.py       # Commit-reveal (ADR-005)
│   │   ├── ceremony_engine.py      # Two-phase commit
│   │   ├── committee_service.py
│   │   ├── state_service.py
│   │   └── override_service.py
│   ├── agents/                     # LLM orchestration
│   │   ├── orchestrator.py         # Abstract interface (ADR-001)
│   │   ├── crewai_orchestrator.py  # Production impl
│   │   ├── mock_orchestrator.py    # Testing impl
│   │   ├── officers/               # 8 officer specializations
│   │   └── personalities/          # 72 YAML files
│   ├── models/
│   │   ├── domain/                 # Pydantic models
│   │   ├── db/                     # SQLAlchemy ORM
│   │   └── events/                 # Event type definitions
│   ├── events/                     # Event sourcing (ADR-002)
│   │   ├── store.py, publisher.py, subscriber.py, snapshots.py
│   └── security/
│       ├── mutex.py                # Singleton locks + fencing
│       ├── blinding.py             # Tier blinding
│       ├── auth.py, keeper.py
│
├── input_boundary/                 # Separate microservice (ADR-004)
│   ├── src/
│   │   ├── services/
│   │   │   ├── quarantine.py       # M-1.1
│   │   │   ├── pattern_blocker.py  # M-1.2
│   │   │   ├── rate_limiter.py     # M-1.3
│   │   │   └── summarizer.py
│   │   └── publishers/
│
├── tests/
│   ├── conftest.py, factories/
│   ├── unit/services/, unit/agents/, unit/security/
│   ├── integration/
│   └── e2e/
│
├── scripts/                        # Utilities
└── docs/runbooks/                  # Operational runbooks
```

### Architectural Boundaries

**Service Boundaries:**

```
┌──────────────────────────────────────────────────┐
│  EXTERNAL                                         │
│  Seekers ──► input_boundary (Quarantine)         │
│              │                                    │
│              │ Redis Streams                      │
│              ▼                                    │
│  Keeper ────► src/ (Conclave Backend)            │
└──────────────────────────────────────────────────┘
```

| Boundary | Access | Auth |
|----------|--------|------|
| input_boundary | Seekers | Seeker JWT |
| /v1/meetings, /votes | Public read | Seeker JWT |
| /v1/admin/* | Keepers only | MFA + Hardware key |
| Redis Streams | Services | mTLS |

**Data Boundaries:**

| Schema | Access | Contents |
|--------|--------|----------|
| `public` | All services | Meetings, votes, ceremonies |
| `patronage_private` | Billing ONLY | Seeker tier (blinded) |
| `audit` | Append-only | Event logs |

### Requirements to Structure Mapping

| Requirement | Primary Location |
|-------------|------------------|
| Meeting Engine | `src/services/meeting_engine.py` |
| Voting System | `src/services/voting_service.py` |
| Ceremony Engine | `src/services/ceremony_engine.py` |
| Agent Orchestration | `src/agents/` |
| Input Boundary | `input_boundary/src/` |
| Human Override | `src/api/v1/admin/override.py` |
| Singleton Mutex | `src/security/mutex.py` |
| Event Sourcing | `src/events/` |
| Blinding | `src/security/blinding.py` |

### Data Flow

```
Seeker Petition
      │
      ▼
input_boundary (quarantine) ──► Reject if blocked
      │
      │ Redis Streams (sanitized summary)
      ▼
Conclave Backend
      │
      ▼
Investigation Committee ──► Meeting Agenda
      │
      ▼
MeetingEngine ──► Deliberation ──► Vote Collection
      │
      ▼
Event Store (audit) ──► Decision Record
```

---

## Architecture Validation Results

### Coherence Validation ✅

| Check | Status | Notes |
|-------|--------|-------|
| FastAPI + CrewAI | ✅ | Both async-first |
| SQLAlchemy + Supabase | ✅ | Standard PostgreSQL |
| Event sourcing + CRUD | ✅ | ADR-002 boundaries |
| Redis + PostgreSQL | ✅ | Standard pairing |
| All patterns align | ✅ | Python conventions |

**No contradictory decisions found.**

### Requirements Coverage ✅

**PRD Coverage:**

| Requirement | Location | Status |
|-------------|----------|--------|
| 72 Archon instantiation | `src/agents/` | ✅ |
| Meeting lifecycle + quorum | `src/services/meeting_engine.py` | ✅ |
| Voting (3 thresholds) | `src/services/voting_service.py` | ✅ |
| 8 Ceremonies | `src/services/ceremony_engine.py` | ✅ |
| 5 Committees | `src/services/committee_service.py` | ✅ |
| 8 Officers | `src/agents/officers/` | ✅ |
| Input sanitization | `input_boundary/` | ✅ |

**Mitigation Coverage:**

| Mitigation | Location | Status |
|------------|----------|--------|
| M-1.x Input Boundary | `input_boundary/services/` | ✅ |
| M-2.x Singleton | `src/security/mutex.py` | ✅ |
| M-4.x Blinding | `src/security/blinding.py` + DB | ✅ |
| M-6.2 Human Override | `src/services/override_service.py` | ✅ |

### Implementation Readiness ✅

| Element | Documented | Versioned | Examples |
|---------|------------|-----------|----------|
| Database | ✅ | ✅ PostgreSQL 16 | ✅ |
| ORM | ✅ | ✅ SQLAlchemy 2.0 | ✅ |
| API | ✅ | ✅ FastAPI | ✅ |
| Agent | ✅ | ✅ CrewAI | ✅ |
| Events | ✅ | N/A | ✅ |
| Patterns | ✅ | N/A | ✅ |

### Gap Analysis

**Critical Gaps:** None

**Important Gaps (non-blocking):**
- Database indexes: Define in first migration
- Personality YAML schema: Create in Epic 1
- Redis config details: Add to deployment story

### Architecture Completeness Checklist

- [x] Requirements analyzed
- [x] 5 ADRs documented
- [x] Technology stack specified
- [x] Naming conventions established
- [x] Structure patterns defined
- [x] Project structure complete
- [x] Boundaries established
- [x] Integration points mapped

### Readiness Assessment

**Status:** READY FOR IMPLEMENTATION
**Confidence:** HIGH

**Strengths:**
1. 6-layer security architecture
2. Clear service boundaries
3. Event sourcing for audit
4. Research-validated choices
5. Extensive adversarial analysis

**Implementation Sequence:**
1. Project scaffold + dependencies
2. Database schema + migrations
3. Singleton mutex
4. InputBoundary service
5. Core Conclave services
6. AgentOrchestrator
7. CeremonyEngine
8. Detection/Monitoring

---

## Architecture Completion Summary

### Workflow Completion

**Architecture Decision Workflow:** COMPLETED ✅
**Total Steps Completed:** 8
**Date Completed:** 2025-12-27
**Document Location:** `_bmad-output/planning-artifacts/architecture.md`

### Final Architecture Deliverables

**Complete Architecture Document:**
- 5 ADRs with trade-offs and rationale
- 10 enforcement guidelines for AI agents
- Complete project structure (40+ files mapped)
- 19 mitigations integrated across 6 security layers
- Comprehensive validation with zero critical gaps

**Implementation Ready Foundation:**
- 25+ architectural decisions documented
- 12 pattern categories defined
- 8 primary services specified
- All PRD requirements mapped to structure

**AI Agent Implementation Guide:**
- Technology stack: Python 3.11+, FastAPI, CrewAI, Supabase
- Naming conventions: snake_case code, PascalCase classes
- Error handling: ConclaveError hierarchy + RFC 7807
- Logging: structlog with structured key-value pairs
- Async patterns: asyncio throughout, never blocking

### Implementation Handoff

**For AI Agents:**
This architecture document is your complete guide for implementing Archon 72 Conclave Backend. Follow all decisions, patterns, and structures exactly as documented.

**First Implementation Priority:**

```bash
mkdir -p archon72-conclave && cd archon72-conclave
poetry init --name archon72-conclave --python "^3.11"
poetry add fastapi uvicorn[standard] crewai supabase pydantic sqlalchemy alembic redis structlog
```

**Development Sequence:**
1. Project scaffold + dependencies
2. Database schema + migrations (with blinding isolation)
3. Singleton mutex (`src/security/mutex.py`)
4. InputBoundary service (separate microservice)
5. Core Conclave services (MeetingEngine, VotingService)
6. AgentOrchestrator (CrewAI integration)
7. CeremonyEngine (two-phase commit)
8. Detection/Monitoring

### Quality Assurance Checklist

**✅ Architecture Coherence**
- [x] All decisions work together without conflicts
- [x] Technology choices are compatible
- [x] Patterns support the architectural decisions

**✅ Requirements Coverage**
- [x] All PRD functional requirements supported
- [x] All 19 mitigations architecturally addressed
- [x] EU AI Act compliance via Human Override

**✅ Implementation Readiness**
- [x] Decisions specific and actionable
- [x] Patterns prevent agent conflicts
- [x] Structure complete and unambiguous

---

**Architecture Status:** READY FOR IMPLEMENTATION ✅

**Next Phase:** Begin implementation using the architectural decisions and patterns documented herein.

---

_Architecture Decision Document Complete._
