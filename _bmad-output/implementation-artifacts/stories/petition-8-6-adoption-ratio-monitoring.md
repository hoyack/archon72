# Story 8.6: Adoption Ratio Monitoring (PREVENT-7)

**Epic:** Epic 8 - Legitimacy Metrics & Governance
**Story ID:** petition-8-6-adoption-ratio-monitoring
**Priority:** P1
**Status:** ready-for-dev

## User Story

As a **governance observer**,
I want adoption ratio monitored per realm,
So that excessive petition-to-Motion conversion is detected.

## Requirements Coverage

### Functional Requirements
- **FR-5.5:** King SHALL be able to ADOPT petition (creates Motion) [P0] - Leverages existing
- **FR-5.6:** Adoption SHALL consume promotion budget (H1 compliance) [P0] - Leverages existing
- **PREVENT-7:** Adoption ratio monitoring to detect excessive conversion

### Non-Functional Requirements
- **NFR-1.5:** Metric computation completes within 60 seconds
- **NFR-4.5:** Adoption budget durable
- **NFR-8.3:** Atomic budget consumption with Motion creation

### Constitutional Triggers
- **CT-11:** "Speech is unlimited. Agenda is scarce." - Petitions are unlimited speech; adoption is scarce
- **CT-12:** Witnessing creates accountability - Adoption ratio alerts are witnessed
- **ASM-7:** Monitor adoption vs organic ratio to detect budget contention

### Threat Mitigations
- **PRE-3:** Budget laundering prevention via adoption ratio monitoring
- **RISK-8:** Budget contention (adoption vs organic) detection
- **ADR-P4:** Budget consumption prevents budget laundering

## Dependencies

### Prerequisites
- Story 6.3: Petition Adoption Creates Motion (complete)
  - `PetitionAdoptionService` with budget consumption
  - `PetitionAdoptedEventPayload` events
- Story 8.1: Legitimacy Decay Metric Computation (complete)
  - `LegitimacyMetrics` model
  - Governance cycle infrastructure
- Story 8.2: Legitimacy Decay Alerting (complete)
  - Alert infrastructure and notification system
- Story 8.4: High Archon Legitimacy Dashboard (complete)
  - Dashboard API infrastructure

### Integration Points
- `PetitionAdoptionService` for adoption event listening
- `LegitimacyMetrics` for cycle management
- `LegitimacyAlertingService` for alert creation
- Prometheus metrics for observability
- High Archon dashboard for visibility

## Acceptance Criteria

### AC1: Adoption Ratio Domain Model

**Given** the system needs to track adoption ratios per realm
**When** adoptions occur within a governance cycle
**Then** an `AdoptionRatioMetrics` model tracks:
  - `realm_id` - Realm identifier
  - `cycle_id` - Governance cycle identifier
  - `escalation_count` - Total petitions escalated to realm this cycle
  - `adoption_count` - Total petitions adopted by realm's King this cycle
  - `adoption_ratio` - adoption_count / escalation_count (0.0 to 1.0)
  - `adopting_kings` - List of King IDs who performed adoptions
  - `computed_at` - When ratio was computed

**Given** a realm has no escalations in a cycle
**When** adoption ratio is computed
**Then** `adoption_ratio` is `None` (no data, not 0)

### AC2: Adoption Ratio Computation Service

**Given** adoption events are emitted when Kings adopt petitions
**When** the cycle ends or on-demand computation is triggered
**Then** `AdoptionRatioComputeService` computes:
  - Count of escalations per realm (petitions in ESCALATED state destined for realm)
  - Count of adoptions per realm (adoptions created by realm's Kings)
  - Ratio calculation
  - List of adopting King identifiers

**Given** the service computes metrics
**When** completed
**Then** results are persisted and available for alerting

### AC3: Adoption Ratio Alert Threshold

**Given** Kings are adopting petitions as Motions
**When** the adoption ratio exceeds **50%** for a realm (within a cycle)
**Then** an `AdoptionRatioAlert` is raised containing:
  - `alert_id` - Unique alert identifier
  - `realm_id` - Realm identifier
  - `cycle_id` - Governance cycle
  - `adoption_count` - Number of adoptions
  - `escalation_count` - Number of escalations
  - `adoption_ratio` - The computed ratio
  - `threshold` - The threshold that was exceeded (0.50)
  - `adopting_kings` - List of King IDs who adopted
  - `trend_delta` - Comparison to previous cycle (if available)
  - `severity` - WARN if 50-70%, CRITICAL if >70%

**Given** an alert is raised
**Then** a `AdoptionRatioExceeded` event is emitted and witnessed (CT-12)

### AC4: Alert Auto-Resolution

**Given** an adoption ratio alert exists for a realm
**When** the next cycle completes with adoption ratio below threshold
**Then** the alert is auto-resolved
**And** an `AdoptionRatioNormalized` event is emitted
**And** the resolution timestamp is recorded

**Given** the ratio remains above threshold
**When** the next cycle completes
**Then** the alert remains active
**And** trend data is updated (escalating/stable/declining)

### AC5: Adoption Metrics in Dashboard

**Given** the High Archon legitimacy dashboard exists (Story 8.4)
**When** adoption ratio data is available
**Then** the dashboard includes:
  - Per-realm adoption ratio (current cycle)
  - Trend comparison to previous cycle (delta)
  - Active adoption ratio alerts
  - Adopting King breakdown per realm

**Given** I have HIGH_ARCHON role
**When** I access GET `/api/v1/governance/dashboard/adoption-ratios`
**Then** I receive adoption ratio data for all realms

**Given** I do not have HIGH_ARCHON role
**When** I attempt to access adoption ratio data
**Then** the system returns HTTP 403 Forbidden

### AC6: Prometheus Metrics

**Given** adoption ratio monitoring is operational
**When** metrics are computed or alerts fire
**Then** Prometheus metrics are updated:
  - `adoption_ratio_by_realm{realm="X"}` (gauge) - Current adoption ratio
  - `adoption_ratio_alerts_active` (gauge) - Count of active alerts
  - `adoption_ratio_alerts_total{severity="WARN|CRITICAL"}` (counter)
  - `adoption_ratio_computation_duration_seconds` (histogram)

**And** structured logs capture ratio computation and alert decisions

## Technical Design

### Domain Models

#### AdoptionRatioMetrics

```python
@dataclass(frozen=True)
class AdoptionRatioMetrics:
    """Adoption ratio metrics per realm per cycle (Story 8.6, PREVENT-7).

    Tracks the ratio of adopted petitions to escalated petitions for a realm
    within a governance cycle. Used to detect excessive adoption patterns.

    Constitutional Requirements:
    - PREVENT-7: Alert when adoption ratio > 50%
    - ASM-7: Monitor adoption vs organic ratio
    - CT-11: Adoption is scarce resource (like agenda)

    Attributes:
        metrics_id: Unique identifier for this metrics record
        realm_id: Realm identifier
        cycle_id: Governance cycle (format: YYYY-Wnn)
        escalation_count: Petitions escalated to this realm
        adoption_count: Petitions adopted by this realm's King
        adoption_ratio: adoption_count / escalation_count (None if no escalations)
        adopting_kings: List of King UUIDs who performed adoptions
        computed_at: When these metrics were computed
    """

    metrics_id: UUID
    realm_id: str
    cycle_id: str
    escalation_count: int
    adoption_count: int
    adoption_ratio: float | None
    adopting_kings: list[UUID]
    computed_at: datetime

    @classmethod
    def compute(
        cls,
        realm_id: str,
        cycle_id: str,
        escalation_count: int,
        adoption_count: int,
        adopting_kings: list[UUID],
    ) -> AdoptionRatioMetrics:
        """Compute adoption ratio metrics for a realm/cycle."""
        ratio = None if escalation_count == 0 else adoption_count / escalation_count

        return cls(
            metrics_id=uuid4(),
            realm_id=realm_id,
            cycle_id=cycle_id,
            escalation_count=escalation_count,
            adoption_count=adoption_count,
            adoption_ratio=ratio,
            adopting_kings=adopting_kings,
            computed_at=datetime.now(timezone.utc),
        )

    def exceeds_threshold(self, threshold: float = 0.50) -> bool:
        """Check if adoption ratio exceeds alert threshold (PREVENT-7)."""
        if self.adoption_ratio is None:
            return False
        return self.adoption_ratio > threshold

    def severity(self) -> str | None:
        """Get alert severity based on adoption ratio."""
        if self.adoption_ratio is None or self.adoption_ratio <= 0.50:
            return None
        elif self.adoption_ratio <= 0.70:
            return "WARN"
        else:
            return "CRITICAL"
```

#### AdoptionRatioAlert

```python
@dataclass(frozen=True)
class AdoptionRatioAlert:
    """Alert for excessive adoption ratio (Story 8.6, PREVENT-7).

    Raised when a realm's adoption ratio exceeds the 50% threshold.

    Attributes:
        alert_id: Unique alert identifier
        realm_id: Realm with excessive adoption ratio
        cycle_id: Governance cycle when detected
        adoption_count: Number of adoptions
        escalation_count: Number of escalations
        adoption_ratio: The computed ratio
        threshold: Threshold that was exceeded (0.50)
        adopting_kings: Kings who performed adoptions
        severity: WARN (50-70%) or CRITICAL (>70%)
        trend_delta: Change from previous cycle (positive = increasing)
        created_at: When alert was created
        resolved_at: When alert was resolved (if applicable)
        status: ACTIVE or RESOLVED
    """

    alert_id: UUID
    realm_id: str
    cycle_id: str
    adoption_count: int
    escalation_count: int
    adoption_ratio: float
    threshold: float
    adopting_kings: list[UUID]
    severity: str  # "WARN" or "CRITICAL"
    trend_delta: float | None  # Difference from previous cycle
    created_at: datetime
    resolved_at: datetime | None
    status: str  # "ACTIVE" or "RESOLVED"
```

#### Event Payloads

```python
@dataclass(frozen=True)
class AdoptionRatioExceededEventPayload:
    """Event when adoption ratio exceeds threshold (CT-12 witnessed)."""

    event_id: UUID
    alert_id: UUID
    realm_id: str
    cycle_id: str
    adoption_ratio: float
    threshold: float
    severity: str
    adopting_kings: list[str]  # UUID strings for JSON serialization
    occurred_at: datetime

    def to_dict(self) -> dict:
        """Serialize for event store."""
        return {
            "schema_version": "1.0.0",
            "event_id": str(self.event_id),
            "alert_id": str(self.alert_id),
            "realm_id": self.realm_id,
            "cycle_id": self.cycle_id,
            "adoption_ratio": self.adoption_ratio,
            "threshold": self.threshold,
            "severity": self.severity,
            "adopting_kings": self.adopting_kings,
            "occurred_at": self.occurred_at.isoformat(),
        }


@dataclass(frozen=True)
class AdoptionRatioNormalizedEventPayload:
    """Event when adoption ratio returns to normal (CT-12 witnessed)."""

    event_id: UUID
    alert_id: UUID
    realm_id: str
    cycle_id: str
    new_adoption_ratio: float
    normalized_at: datetime

    def to_dict(self) -> dict:
        """Serialize for event store."""
        return {
            "schema_version": "1.0.0",
            "event_id": str(self.event_id),
            "alert_id": str(self.alert_id),
            "realm_id": self.realm_id,
            "cycle_id": self.cycle_id,
            "new_adoption_ratio": self.new_adoption_ratio,
            "normalized_at": self.normalized_at.isoformat(),
        }
```

### Repository Port

```python
class AdoptionRatioRepositoryProtocol(Protocol):
    """Repository for adoption ratio metrics and alerts (Story 8.6)."""

    async def save_metrics(self, metrics: AdoptionRatioMetrics) -> None:
        """Save adoption ratio metrics."""
        ...

    async def get_metrics_by_realm_cycle(
        self, realm_id: str, cycle_id: str
    ) -> AdoptionRatioMetrics | None:
        """Get metrics for a realm/cycle."""
        ...

    async def get_previous_cycle_metrics(
        self, realm_id: str, current_cycle_id: str
    ) -> AdoptionRatioMetrics | None:
        """Get metrics for the previous cycle (for trend comparison)."""
        ...

    async def get_all_realms_current_cycle(
        self, cycle_id: str
    ) -> list[AdoptionRatioMetrics]:
        """Get metrics for all realms in a cycle."""
        ...

    async def save_alert(self, alert: AdoptionRatioAlert) -> None:
        """Save or update an adoption ratio alert."""
        ...

    async def get_active_alert(self, realm_id: str) -> AdoptionRatioAlert | None:
        """Get active alert for a realm (if any)."""
        ...

    async def get_all_active_alerts(self) -> list[AdoptionRatioAlert]:
        """Get all active adoption ratio alerts."""
        ...

    async def resolve_alert(self, alert_id: UUID, resolved_at: datetime) -> None:
        """Mark an alert as resolved."""
        ...
```

### Service Layer

#### AdoptionRatioComputeService

```python
class AdoptionRatioComputeService:
    """Computes adoption ratios per realm per cycle (Story 8.6, PREVENT-7).

    This service:
    1. Queries escalation count per realm for cycle
    2. Queries adoption count per realm for cycle
    3. Computes ratio and identifies adopting Kings
    4. Persists metrics
    5. Triggers alerting if threshold exceeded
    """

    def __init__(
        self,
        adoption_ratio_repo: AdoptionRatioRepositoryProtocol,
        petition_repo: PetitionSubmissionRepositoryProtocol,
        alerting_service: AdoptionRatioAlertingService,
        event_writer: EventWriterService,
    ) -> None:
        ...

    async def compute_for_cycle(self, cycle_id: str) -> list[AdoptionRatioMetrics]:
        """Compute adoption ratios for all realms in a cycle.

        Args:
            cycle_id: Governance cycle to compute (e.g., "2026-W04")

        Returns:
            List of AdoptionRatioMetrics for all realms with activity.
        """
        ...

    async def compute_for_realm(
        self, realm_id: str, cycle_id: str
    ) -> AdoptionRatioMetrics:
        """Compute adoption ratio for a specific realm/cycle."""
        ...
```

#### AdoptionRatioAlertingService

```python
class AdoptionRatioAlertingService:
    """Manages adoption ratio alerts (Story 8.6, PREVENT-7).

    This service:
    1. Evaluates metrics against threshold (50%)
    2. Creates new alerts when threshold exceeded
    3. Resolves alerts when ratio normalizes
    4. Emits witnessed events (CT-12)
    5. Updates Prometheus metrics
    """

    THRESHOLD = 0.50  # 50% adoption ratio triggers alert

    async def evaluate_metrics(
        self, metrics: AdoptionRatioMetrics
    ) -> AdoptionRatioAlert | None:
        """Evaluate metrics and create/update alerts as needed.

        Args:
            metrics: Computed adoption ratio metrics

        Returns:
            New or updated alert if threshold exceeded, None otherwise.
        """
        ...

    async def check_for_resolution(
        self, realm_id: str, new_metrics: AdoptionRatioMetrics
    ) -> bool:
        """Check if active alert should be resolved.

        Args:
            realm_id: Realm to check
            new_metrics: Latest computed metrics

        Returns:
            True if alert was resolved, False otherwise.
        """
        ...
```

### API Endpoints

#### GET /api/v1/governance/dashboard/adoption-ratios

```python
@router.get("/governance/dashboard/adoption-ratios")
async def get_adoption_ratios(
    high_archon_id: UUID = Depends(get_high_archon_id),
    cycle_id: Optional[str] = Query(default=None, description="Cycle ID, defaults to current"),
) -> AdoptionRatioDashboardResponse:
    """Get adoption ratio data for dashboard.

    Requires HIGH_ARCHON role (FR-10.4).

    Returns:
        AdoptionRatioDashboardResponse with per-realm metrics and alerts.
    """
    pass
```

#### Response Model

```python
class AdoptionRatioRealmSummary(BaseModel):
    """Adoption ratio summary for a single realm."""

    realm_id: str
    cycle_id: str
    escalation_count: int
    adoption_count: int
    adoption_ratio: Optional[float]
    trend_delta: Optional[float]
    adopting_kings: list[str]
    status: str  # "HEALTHY", "WARN", "CRITICAL", "NO_DATA"
    has_active_alert: bool


class AdoptionRatioDashboardResponse(BaseModel):
    """Dashboard response for adoption ratios."""

    cycle_id: str
    realms: list[AdoptionRatioRealmSummary]
    active_alerts: list[AdoptionRatioAlertSummary]
    total_escalations: int
    total_adoptions: int
    overall_ratio: Optional[float]
```

### Database Schema

```sql
-- Migration 034: Adoption ratio monitoring tables
-- Story 8.6: PREVENT-7

-- Table: adoption_ratio_metrics
-- Tracks adoption ratios per realm per cycle

CREATE TABLE IF NOT EXISTS adoption_ratio_metrics (
    metrics_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    realm_id TEXT NOT NULL,
    cycle_id TEXT NOT NULL,
    escalation_count INTEGER NOT NULL DEFAULT 0,
    adoption_count INTEGER NOT NULL DEFAULT 0,
    adoption_ratio DECIMAL(5, 4),  -- NULL if no escalations
    adopting_kings UUID[] NOT NULL DEFAULT '{}',
    computed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT unique_realm_cycle UNIQUE (realm_id, cycle_id)
);

-- Index for cycle queries
CREATE INDEX idx_adoption_ratio_cycle ON adoption_ratio_metrics(cycle_id);

-- Index for realm queries
CREATE INDEX idx_adoption_ratio_realm ON adoption_ratio_metrics(realm_id);

-- Table: adoption_ratio_alerts
-- Tracks alerts for excessive adoption ratios

CREATE TABLE IF NOT EXISTS adoption_ratio_alerts (
    alert_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    realm_id TEXT NOT NULL,
    cycle_id TEXT NOT NULL,
    adoption_count INTEGER NOT NULL,
    escalation_count INTEGER NOT NULL,
    adoption_ratio DECIMAL(5, 4) NOT NULL,
    threshold DECIMAL(5, 4) NOT NULL DEFAULT 0.5000,
    adopting_kings UUID[] NOT NULL DEFAULT '{}',
    severity TEXT NOT NULL CHECK (severity IN ('WARN', 'CRITICAL')),
    trend_delta DECIMAL(5, 4),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMPTZ,
    status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'RESOLVED'))
);

-- Index for active alerts
CREATE INDEX idx_adoption_alerts_active ON adoption_ratio_alerts(realm_id)
    WHERE status = 'ACTIVE';

-- Index for resolved alerts (for history)
CREATE INDEX idx_adoption_alerts_resolved ON adoption_ratio_alerts(resolved_at DESC)
    WHERE status = 'RESOLVED';
```

## Testing Strategy

### Unit Tests (Target: 30+ tests)

1. **Domain Model Tests** (8 tests)
   - AdoptionRatioMetrics creation
   - Ratio computation with zero escalations (None)
   - Ratio computation with normal data
   - exceeds_threshold() logic
   - severity() calculation (None, WARN, CRITICAL)
   - AdoptionRatioAlert creation
   - Event payload serialization
   - Frozen dataclass immutability

2. **Compute Service Tests** (10 tests)
   - compute_for_cycle with no data
   - compute_for_cycle with single realm
   - compute_for_cycle with multiple realms
   - compute_for_realm with no escalations
   - compute_for_realm with normal ratio
   - compute_for_realm with high ratio
   - Multiple adopting Kings tracked
   - Metrics persistence called
   - Alerting service triggered
   - Error handling for repository failures

3. **Alerting Service Tests** (8 tests)
   - No alert for ratio below threshold
   - WARN alert for 50-70% ratio
   - CRITICAL alert for >70% ratio
   - Existing alert updated (not duplicated)
   - Alert resolved when ratio normalizes
   - AdoptionRatioExceeded event emitted
   - AdoptionRatioNormalized event emitted
   - Trend delta computed from previous cycle

4. **API Route Tests** (6 tests)
   - GET adoption-ratios success
   - GET adoption-ratios requires HIGH_ARCHON
   - GET adoption-ratios with custom cycle_id
   - GET adoption-ratios empty data handling
   - GET adoption-ratios includes active alerts
   - Response model validation

### Integration Tests (Target: 10+ tests)

1. **End-to-End Flow** (4 tests)
   - Adoption event → ratio computation → alert creation
   - Multiple adoptions same cycle → ratio update
   - Ratio normalization → alert resolution
   - Dashboard displays correct data

2. **Database Integration** (3 tests)
   - Metrics persistence and retrieval
   - Alert persistence and status update
   - Concurrent writes handling

3. **Event Integration** (3 tests)
   - AdoptionRatioExceeded witnessed
   - AdoptionRatioNormalized witnessed
   - Prometheus metrics updated

## Configuration

### Environment Variables

```bash
# Adoption ratio monitoring configuration
ADOPTION_RATIO_THRESHOLD=0.50
ADOPTION_RATIO_WARN_THRESHOLD=0.50
ADOPTION_RATIO_CRITICAL_THRESHOLD=0.70
```

## Prometheus Metrics

```python
# Gauges
adoption_ratio_by_realm = Gauge(
    "adoption_ratio_by_realm",
    "Current adoption ratio by realm",
    ["realm"],
)
adoption_ratio_alerts_active = Gauge(
    "adoption_ratio_alerts_active",
    "Count of active adoption ratio alerts",
)

# Counters
adoption_ratio_alerts_total = Counter(
    "adoption_ratio_alerts_total",
    "Total adoption ratio alerts raised",
    ["severity"],
)

# Histograms
adoption_ratio_computation_duration = Histogram(
    "adoption_ratio_computation_duration_seconds",
    "Duration of adoption ratio computation",
)
```

## Success Criteria

### Functional Completeness
- [ ] AdoptionRatioMetrics domain model created
- [ ] AdoptionRatioAlert domain model created
- [ ] Event payloads implemented
- [ ] Compute service operational
- [ ] Alerting service operational
- [ ] Dashboard endpoint functional
- [ ] Migration applied

### Non-Functional Compliance
- [ ] **PREVENT-7:** Adoption ratio > 50% triggers alert
- [ ] **ASM-7:** Adoption vs organic ratio monitored
- [ ] **CT-12:** All events witnessed
- [ ] Unit test coverage > 90%
- [ ] Integration tests cover all scenarios

### Constitutional Compliance
- [ ] **CT-11:** Adoption recognized as scarce resource
- [ ] **CT-12:** Events witnessed and immutable
- [ ] **ADR-P4:** Budget laundering pattern detected via ratio

## Implementation Tasks

### Phase 1: Domain Models (1 hour)
1. Create `AdoptionRatioMetrics` dataclass
2. Create `AdoptionRatioAlert` dataclass
3. Create event payloads
4. Unit tests for domain models

### Phase 2: Repository (1 hour)
5. Create `AdoptionRatioRepositoryProtocol`
6. Create stub implementation
7. Create migration 034
8. Repository unit tests

### Phase 3: Services (2 hours)
9. Implement `AdoptionRatioComputeService`
10. Implement `AdoptionRatioAlertingService`
11. Integrate with event writer
12. Service unit tests

### Phase 4: API & Dashboard (1 hour)
13. Add GET `/api/v1/governance/dashboard/adoption-ratios`
14. Create API models
15. API unit tests

### Phase 5: Metrics & Events (1 hour)
16. Add Prometheus metrics
17. Integrate event emission
18. Structured logging
19. Integration tests

## Notes

- PREVENT-7 is about detecting when Kings are "rubber-stamping" escalated petitions
- High adoption ratio (>50%) suggests petitions are bypassing normal governance
- Alert threshold is 50% with WARN severity, 70%+ is CRITICAL
- Trend comparison helps identify escalating patterns
- Dashboard provides visibility but doesn't block adoptions
- Auto-resolution prevents stale alerts when behavior normalizes

## Related Stories

- **Story 6.3:** Petition Adoption Creates Motion (adoption infrastructure)
- **Story 8.1:** Legitimacy Decay Metric Computation (cycle management)
- **Story 8.2:** Legitimacy Decay Alerting (alerting pattern)
- **Story 8.4:** High Archon Legitimacy Dashboard (dashboard integration)
- **Story 8.7:** Realm Health Aggregate (realm-level metrics)

---

**Story Status:** Ready for Implementation
**Risk Level:** Low (builds on existing adoption and alerting infrastructure)
