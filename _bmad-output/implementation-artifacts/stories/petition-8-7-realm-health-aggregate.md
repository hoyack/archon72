# Story 8.7: Realm Health Aggregate

**Epic:** Epic 8 - Legitimacy Metrics & Governance
**Story ID:** petition-8-7-realm-health-aggregate
**Priority:** P1
**Status:** ready-for-dev

## User Story

As a **developer**,
I want a RealmHealth aggregate that tracks per-realm petition metrics,
So that realm-level health can be monitored and compared.

## Requirements Coverage

### Functional Requirements
- **FR-8.1:** Realm health metrics tracked per governance cycle

### Hidden Prerequisites
- **HP-7:** Read Model Projections - RealmHealth provides the read model for realm-level petition activity

### Non-Functional Requirements
- **NFR-1.5:** Metric computation completes within 60 seconds
- **NFR-7.1:** Prometheus metrics for realm health monitoring

### Constitutional Triggers
- **CT-11:** "Speech is unlimited. Agenda is scarce." - Track petition flow through realms
- **CT-12:** Witnessing creates accountability - RealmHealth events witnessed

## Dependencies

### Prerequisites
- Story 0.6: Realm Registry & Routing (complete)
  - `Realm` domain model and `CANONICAL_REALM_IDS`
- Story 8.1: Legitimacy Decay Metric Computation (complete)
  - Governance cycle infrastructure
- Story 8.4: High Archon Legitimacy Dashboard (complete)
  - Dashboard API infrastructure
- Story 8.6: Adoption Ratio Monitoring (complete)
  - Adoption metrics per realm

### Integration Points
- `Realm` domain model for realm identifiers
- `LegitimacyMetrics` for cycle management
- High Archon dashboard for visibility
- Prometheus metrics for observability

## Acceptance Criteria

### AC1: RealmHealth Domain Model

**Given** petition activity occurs across realms
**When** metrics are computed
**Then** each realm has a `RealmHealth` aggregate with:
  - `health_id` - Unique identifier for this health record
  - `realm_id` - Realm identifier
  - `cycle_id` - Governance cycle identifier (YYYY-Wnn)
  - `petitions_received` - Petitions received this cycle
  - `petitions_fated` - Petitions that completed Three Fates deliberation
  - `referrals_pending` - Current pending referrals to Knights
  - `referrals_expired` - Referrals that expired without recommendation
  - `escalations_pending` - Petitions awaiting King decision
  - `adoption_rate` - Ratio of adoptions to escalations (from Story 8.6)
  - `average_referral_duration` - Average time from referral to resolution (seconds)
  - `computed_at` - When health was computed (UTC)

**Given** a realm has no activity in a cycle
**When** health is computed
**Then** all counts are 0 and adoption_rate is None

### AC2: RealmHealth Computation Service

**Given** the governance cycle ends or on-demand computation is triggered
**When** `RealmHealthComputeService.compute_for_cycle()` is called
**Then** health metrics are computed for all 9 canonical realms:
  - Queries petition counts by realm
  - Queries referral status by realm
  - Queries escalation status by realm
  - Aggregates average durations
  - Persists to `realm_health` table

**Given** computation completes
**When** results are available
**Then** a `RealmHealthComputed` event is emitted for observability

### AC3: Health Status Derivation

**Given** a RealmHealth record exists
**When** health status is evaluated
**Then** status is derived based on:
  - `HEALTHY`: No pending escalations, referral expiry rate < 10%
  - `ATTENTION`: 1-5 pending escalations OR referral expiry rate 10-20%
  - `DEGRADED`: 6-10 pending escalations OR referral expiry rate > 20%
  - `CRITICAL`: > 10 pending escalations OR adoption rate > 70%

### AC4: RealmHealth API Endpoint

**Given** I have HIGH_ARCHON role
**When** I access GET `/api/v1/governance/dashboard/realm-health`
**Then** I receive health data for all 9 realms with:
  - Current cycle health metrics
  - Derived health status
  - Comparison to previous cycle (delta values)

**Given** I do not have HIGH_ARCHON role
**When** I attempt to access realm health data
**Then** the system returns HTTP 403 Forbidden

### AC5: Prometheus Metrics

**Given** realm health monitoring is operational
**When** metrics are computed
**Then** Prometheus metrics are updated:
  - `realm_health_petitions_received{realm="X"}` (gauge)
  - `realm_health_petitions_fated{realm="X"}` (gauge)
  - `realm_health_referrals_pending{realm="X"}` (gauge)
  - `realm_health_escalations_pending{realm="X"}` (gauge)
  - `realm_health_status{realm="X",status="Y"}` (gauge, 1 for current status)
  - `realm_health_computation_duration_seconds` (histogram)

### AC6: Database Persistence

**Given** realm health is computed
**When** persisted
**Then** data is stored in `realm_health` table with:
  - Primary key on (health_id)
  - Unique constraint on (realm_id, cycle_id)
  - Indexes for efficient querying by realm and cycle

## Technical Design

### Domain Model

```python
@dataclass(frozen=True)
class RealmHealth:
    """Realm health aggregate (Story 8.7, HP-7).

    Tracks per-realm petition metrics for governance monitoring.
    Provides the read model projection for realm-level health.

    Constitutional Constraints:
    - HP-7: Read model projections for realm health
    - CT-11: Track petition flow (speech vs agenda)
    - CT-12: Witnessing creates accountability

    Attributes:
        health_id: Unique identifier for this health record
        realm_id: Realm identifier (from CANONICAL_REALM_IDS)
        cycle_id: Governance cycle identifier (YYYY-Wnn)
        petitions_received: Petitions received in this realm this cycle
        petitions_fated: Petitions that completed Three Fates deliberation
        referrals_pending: Current pending Knight referrals
        referrals_expired: Referrals that expired without recommendation
        escalations_pending: Petitions awaiting King decision
        adoption_rate: adoptions / escalations (None if no escalations)
        average_referral_duration_seconds: Mean referral processing time
        computed_at: When health was computed (UTC)
    """

    health_id: UUID
    realm_id: str
    cycle_id: str
    petitions_received: int
    petitions_fated: int
    referrals_pending: int
    referrals_expired: int
    escalations_pending: int
    adoption_rate: float | None
    average_referral_duration_seconds: int | None
    computed_at: datetime
```

### Health Status Enum

```python
class RealmHealthStatus(Enum):
    """Health status for a realm (Story 8.7).

    Statuses:
        HEALTHY: Normal operation
        ATTENTION: Minor issues requiring monitoring
        DEGRADED: Significant issues affecting operation
        CRITICAL: Severe issues requiring immediate attention
    """
    HEALTHY = "HEALTHY"
    ATTENTION = "ATTENTION"
    DEGRADED = "DEGRADED"
    CRITICAL = "CRITICAL"
```

### Repository Port

```python
class RealmHealthRepositoryProtocol(Protocol):
    """Repository for realm health data (Story 8.7)."""

    async def save_health(self, health: RealmHealth) -> None:
        """Save realm health record."""
        ...

    async def get_by_realm_cycle(
        self, realm_id: str, cycle_id: str
    ) -> RealmHealth | None:
        """Get health for a realm/cycle."""
        ...

    async def get_all_for_cycle(self, cycle_id: str) -> list[RealmHealth]:
        """Get health for all realms in a cycle."""
        ...

    async def get_previous_cycle(
        self, realm_id: str, current_cycle_id: str
    ) -> RealmHealth | None:
        """Get previous cycle health for trend comparison."""
        ...
```

### Database Schema

```sql
-- Migration 035: Realm health aggregate table
-- Story 8.7: HP-7

CREATE TABLE IF NOT EXISTS realm_health (
    health_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    realm_id TEXT NOT NULL,
    cycle_id TEXT NOT NULL,
    petitions_received INTEGER NOT NULL DEFAULT 0,
    petitions_fated INTEGER NOT NULL DEFAULT 0,
    referrals_pending INTEGER NOT NULL DEFAULT 0,
    referrals_expired INTEGER NOT NULL DEFAULT 0,
    escalations_pending INTEGER NOT NULL DEFAULT 0,
    adoption_rate DECIMAL(5, 4),
    average_referral_duration_seconds INTEGER,
    computed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT unique_realm_cycle UNIQUE (realm_id, cycle_id)
);

-- Index for cycle queries (dashboard)
CREATE INDEX idx_realm_health_cycle ON realm_health(cycle_id);

-- Index for realm queries (per-realm history)
CREATE INDEX idx_realm_health_realm ON realm_health(realm_id);
```

## Testing Strategy

### Unit Tests (Target: 25+ tests)

1. **Domain Model Tests** (8 tests)
   - RealmHealth creation
   - All fields populated correctly
   - Immutability (frozen dataclass)
   - health_status() calculation
   - is_healthy() helper
   - Adoption rate None handling
   - Edge case: all zeros
   - Edge case: critical thresholds

2. **Compute Service Tests** (10 tests)
   - compute_for_cycle with no data
   - compute_for_cycle with single realm
   - compute_for_cycle with all 9 realms
   - compute_for_realm with activity
   - compute_for_realm with no activity
   - Average duration calculation
   - Adoption rate integration
   - Repository save called
   - Event emitted on completion
   - Error handling

3. **API Route Tests** (7 tests)
   - GET realm-health success
   - GET realm-health requires HIGH_ARCHON
   - GET realm-health with cycle parameter
   - GET realm-health empty data handling
   - GET realm-health includes all 9 realms
   - Previous cycle comparison included
   - Response model validation

### Integration Tests (Target: 8+ tests)

1. **End-to-End Flow** (3 tests)
   - Petition activity → health computation
   - Multi-realm aggregation
   - Dashboard displays all realms

2. **Database Integration** (3 tests)
   - Health persistence and retrieval
   - Unique constraint enforcement
   - Previous cycle lookup

3. **Event Integration** (2 tests)
   - RealmHealthComputed witnessed
   - Prometheus metrics updated

## Implementation Tasks

### Phase 1: Domain Models
1. Create `RealmHealth` dataclass in `src/domain/models/realm_health.py`
2. Create `RealmHealthStatus` enum
3. Create event payloads in `src/domain/events/realm_health.py`
4. Unit tests for domain models

### Phase 2: Repository Layer
5. Create `RealmHealthRepositoryProtocol` in `src/application/ports/`
6. Create stub implementation in `src/infrastructure/stubs/`
7. Create migration 035 for `realm_health` table

### Phase 3: Service Layer
8. Create `RealmHealthComputeService` in `src/application/services/`
9. Integrate with existing petition/referral queries
10. Add event emission
11. Service unit tests

### Phase 4: API Layer
12. Add GET `/api/v1/governance/dashboard/realm-health` endpoint
13. Create API models in `src/api/models/realm_health.py`
14. API route tests

### Phase 5: Observability
15. Add Prometheus metrics
16. Integration tests
17. Update documentation

## Success Criteria

### Functional Completeness
- [ ] RealmHealth domain model created
- [ ] RealmHealthStatus enum created
- [ ] Event payloads implemented
- [ ] Compute service operational
- [ ] Dashboard endpoint functional
- [ ] Migration applied

### Non-Functional Compliance
- [ ] **HP-7:** Read model projections operational
- [ ] **CT-12:** Events witnessed
- [ ] Unit test coverage > 90%
- [ ] Integration tests cover all scenarios

## Related Stories

- **Story 0.6:** Realm Registry & Routing (realm infrastructure)
- **Story 8.1:** Legitimacy Decay Metric Computation (cycle infrastructure)
- **Story 8.4:** High Archon Legitimacy Dashboard (dashboard integration)
- **Story 8.6:** Adoption Ratio Monitoring (adoption rate source)

---

**Story Status:** Ready for Implementation
**Risk Level:** Low (builds on existing realm and metrics infrastructure)
