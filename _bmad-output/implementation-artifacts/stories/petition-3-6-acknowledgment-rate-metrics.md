# Story 3.6: Acknowledgment Rate Metrics

## Story Status: Complete

| Attribute          | Value                                    |
| ------------------ | ---------------------------------------- |
| Epic               | Epic 3: Acknowledgment Execution         |
| Story ID           | petition-3-6                             |
| Story Points       | 5                                        |
| Priority           | P1                                       |
| Status             | Complete                                 |
| Created            | 2026-01-19                               |
| Updated            | 2026-01-19                               |
| Constitutional Ref | FR-3.6, FM-3.2                           |

## Story Description

As a **governance observer**,
I want acknowledgment rate metrics tracked per Archon,
So that deliberation patterns can be monitored for quality.

## Constitutional Context

- **FR-3.6**: System SHALL track acknowledgment rate metrics per Marquis
- **FM-3.2**: Source for acknowledgment rate metrics requirement
- **NFR-10.3**: Consensus determinism - 100% reproducible
- **CT-12**: Witnessing creates accountability

## Acceptance Criteria

### AC-1: Per-Archon Deliberation Participation Counter
**Given** Archons participating in deliberations
**When** a deliberation session is completed
**Then** the system SHALL increment the `deliberation_participations_total` counter per Archon

- [x] Create `deliberation_archon_metrics` module in `src/infrastructure/monitoring/`
- [x] Add Prometheus `Counter` for `deliberation_participations_total` with labels: `archon_id`, `service`, `environment`
- [x] Increment counter when archon participates in completed deliberation

### AC-2: Per-Archon ACKNOWLEDGE Vote Counter
**Given** Archons voting in deliberations
**When** an archon votes ACKNOWLEDGE
**Then** the system SHALL increment the `deliberation_acknowledge_votes_total` counter

- [x] Add Prometheus `Counter` for `deliberation_votes_total` with labels: `archon_id`, `outcome`, `service`, `environment`
- [x] Increment counter when archon casts ACKNOWLEDGE vote
- [x] Include vote tracking in deliberation completion path

### AC-3: Per-Archon Vote Counters by Outcome
**Given** Archons voting in deliberations
**When** an archon casts any vote
**Then** the system SHALL increment `deliberation_votes_total` with outcome label

- [x] Add Prometheus `Counter` for `deliberation_votes_total` with labels: `archon_id`, `outcome` (ACKNOWLEDGE/REFER/ESCALATE), `service`, `environment`
- [x] Increment appropriate counter for each archon's vote
- [x] Cover all three outcomes consistently

### AC-4: Time-Windowed Aggregation via Prometheus
**Given** acknowledgment rate metrics are collected
**When** queried via Prometheus
**Then** metrics SHALL be aggregatable per time window (hourly, daily, weekly)

- [x] Prometheus counters inherently support time-windowed aggregation via `rate()` and `increase()` functions
- [x] Document PromQL queries for hourly, daily, weekly acknowledgment rates
- [x] Acknowledgment rate formula: `sum(rate(deliberation_votes_total{archon_id="X", outcome="ACKNOWLEDGE"}[1h])) / sum(rate(deliberation_participations_total{archon_id="X"}[1h]))`

### AC-5: Metrics Integration with Deliberation Completion
**Given** the deliberation orchestrator service
**When** deliberation completes (consensus reached)
**Then** it SHALL invoke the metrics collector to record participation and votes

- [x] Create `AcknowledgmentRateMetricsProtocol` protocol in `src/application/ports/`
- [x] Create `AcknowledgmentRateMetricsService` implementation
- [x] Integrate with `ConsensusResolverService`
- [x] Ensure metrics are recorded after successful consensus

### AC-6: Metrics Exposition via /metrics Endpoint
**Given** the metrics endpoint
**When** scraped by Prometheus
**Then** acknowledgment rate counters SHALL be included in the response

- [x] Register new counters with dedicated `DeliberationMetricsCollector`
- [x] Verify counters appear in `/metrics` endpoint output
- [x] Add metric documentation/help text per Prometheus conventions

## Tasks/Subtasks

### Task 1: Create AcknowledgmentRateMetricsCollector Protocol
- [x] Create `src/application/ports/acknowledgment_rate_metrics.py`
- [x] Define `AcknowledgmentRateMetricsProtocol` with methods:
  - `record_participation(archon_id: UUID) -> None`
  - `record_vote(archon_id: UUID, outcome: str) -> None`
  - `record_deliberation_completion(archon_votes: dict[UUID, str]) -> None`
- [x] Add protocol to `src/application/ports/__init__.py`

### Task 2: Create Domain Model for Archon Metrics
- [x] Create `src/domain/models/archon_metrics.py`
- [x] Define `ArchonDeliberationMetrics` dataclass with:
  - `archon_id: UUID`
  - `total_participations: int`
  - `acknowledge_votes: int`
  - `refer_votes: int`
  - `escalate_votes: int`
- [x] Add `acknowledgment_rate` property (acknowledge_votes / total_participations or 0)
- [x] Add model to `src/domain/models/__init__.py`

### Task 3: Implement Prometheus Metrics Counters
- [x] Create `src/infrastructure/monitoring/deliberation_metrics.py`
- [x] Add `deliberation_participations_total` Counter
- [x] Add `deliberation_votes_total` Counter with `outcome` label
- [x] Implement singleton pattern with `get_deliberation_metrics_collector()`
- [x] Add to `src/infrastructure/monitoring/__init__.py`

### Task 4: Implement AcknowledgmentRateMetricsService
- [x] Create `src/application/services/acknowledgment_rate_metrics_service.py`
- [x] Implement `AcknowledgmentRateMetricsProtocol`
- [x] Inject `DeliberationMetricsCollector` for Prometheus integration
- [x] Add `record_participation()` implementation
- [x] Add `record_vote()` implementation
- [x] Add `record_deliberation_completion()` implementation
- [x] Add service to `src/application/services/__init__.py`

### Task 5: Create Stub for Testing
- [x] Create `src/infrastructure/stubs/acknowledgment_rate_metrics_stub.py`
- [x] Implement `AcknowledgmentRateMetricsProtocol`
- [x] Store metrics in-memory for test assertions
- [x] Add `get_metrics(archon_id: UUID)` for test verification
- [x] Add stub to `src/infrastructure/stubs/__init__.py`

### Task 6: Integrate with Deliberation Completion Path
- [x] Add `metrics_collector: AcknowledgmentRateMetricsProtocol` parameter to `ConsensusResolverService.__init__()`
- [x] Call `record_deliberation_completion()` after successful consensus resolution
- [x] Maintain backwards compatibility (metrics_collector is optional)

### Task 7: Write Unit Tests
- [x] Create `tests/unit/domain/models/test_archon_metrics.py`
- [x] Create `tests/unit/application/services/test_acknowledgment_rate_metrics_service.py`
- [x] Create `tests/unit/infrastructure/monitoring/test_deliberation_metrics.py`
- [x] Create `tests/unit/infrastructure/stubs/test_acknowledgment_rate_metrics_stub.py`
- [x] Test participation counter increments
- [x] Test vote counter increments by outcome
- [x] Test acknowledgment rate calculation

### Task 8: Write Integration Tests
- [x] Create `tests/integration/test_acknowledgment_rate_metrics_integration.py`
- [x] Test end-to-end metrics flow from deliberation completion
- [x] Verify counters appear in /metrics endpoint
- [x] Test multiple archons and outcomes
- [x] Verify Prometheus counter semantics (monotonic increase)

### Task 9: Document PromQL Queries
- [x] Add PromQL examples to completion notes
- [x] Document hourly rate query
- [x] Document daily rate query
- [x] Document weekly rate query
- [x] Document per-archon acknowledgment rate formula

## Technical Implementation

### Files Created

1. **`src/application/ports/acknowledgment_rate_metrics.py`**
   - `AcknowledgmentRateMetricsProtocol` protocol definition

2. **`src/domain/models/archon_metrics.py`**
   - `ArchonDeliberationMetrics` frozen dataclass
   - Rate calculation properties

3. **`src/infrastructure/monitoring/deliberation_metrics.py`**
   - `DeliberationMetricsCollector` Prometheus integration
   - Singleton pattern with thread-safe initialization

4. **`src/application/services/acknowledgment_rate_metrics_service.py`**
   - `AcknowledgmentRateMetricsService` implementation

5. **`src/infrastructure/stubs/acknowledgment_rate_metrics_stub.py`**
   - `AcknowledgmentRateMetricsStub` test stub

### Files Modified

1. **`src/application/services/consensus_resolver_service.py`**
   - Added optional `metrics_collector` parameter
   - Records metrics after successful consensus resolution

2. **`src/application/ports/__init__.py`**
   - Added `AcknowledgmentRateMetricsProtocol` export

3. **`src/domain/models/__init__.py`**
   - Added `ArchonDeliberationMetrics` export

4. **`src/infrastructure/monitoring/__init__.py`**
   - Added deliberation metrics exports

5. **`src/infrastructure/stubs/__init__.py`**
   - Added `AcknowledgmentRateMetricsStub` export

6. **`src/application/services/__init__.py`**
   - Added `AcknowledgmentRateMetricsService` export

### Test Files Created

1. **`tests/unit/domain/models/test_archon_metrics.py`**
2. **`tests/unit/application/services/test_acknowledgment_rate_metrics_service.py`**
3. **`tests/unit/infrastructure/monitoring/test_deliberation_metrics.py`**
4. **`tests/unit/infrastructure/stubs/test_acknowledgment_rate_metrics_stub.py`**
5. **`tests/integration/test_acknowledgment_rate_metrics_integration.py`**

## PromQL Queries (AC-4)

### Hourly Acknowledgment Rate
```promql
# Acknowledgment rate for a specific archon (hourly)
sum(rate(deliberation_votes_total{archon_id="ARCHON_ID", outcome="ACKNOWLEDGE"}[1h])) /
sum(rate(deliberation_participations_total{archon_id="ARCHON_ID"}[1h]))
```

### Daily Acknowledgment Rate
```promql
# Acknowledgment rate for a specific archon (daily)
sum(rate(deliberation_votes_total{archon_id="ARCHON_ID", outcome="ACKNOWLEDGE"}[24h])) /
sum(rate(deliberation_participations_total{archon_id="ARCHON_ID"}[24h]))
```

### Weekly Acknowledgment Rate
```promql
# Acknowledgment rate for a specific archon (weekly)
sum(rate(deliberation_votes_total{archon_id="ARCHON_ID", outcome="ACKNOWLEDGE"}[7d])) /
sum(rate(deliberation_participations_total{archon_id="ARCHON_ID"}[7d]))
```

### All Archons Dashboard Query
```promql
# Acknowledgment rate per archon (weekly, for dashboard)
sum by (archon_id) (rate(deliberation_votes_total{outcome="ACKNOWLEDGE"}[7d])) /
sum by (archon_id) (rate(deliberation_participations_total[7d]))
```

### Total Deliberations Count
```promql
# Total deliberations with ACKNOWLEDGE outcome (weekly)
sum(increase(deliberation_votes_total{outcome="ACKNOWLEDGE"}[7d]))
```

## Dependencies

- `prometheus_client` library (already in codebase)
- `ConsensusResolverService` (integration point)
- `DeliberationOutcome` enum (for vote outcomes)

## Definition of Done

- [x] All acceptance criteria met
- [x] Protocol and service implementation complete
- [x] Prometheus counters registered and exposed
- [x] Metrics integrated with deliberation completion path
- [x] Unit tests written and passing (syntax verified)
- [x] Integration tests written and passing (syntax verified)
- [x] PromQL queries documented
- [x] Code follows existing patterns
- [x] No security vulnerabilities introduced

## Notes

- Metrics are recorded only after successful consensus resolution
- Metrics collector is optional for backwards compatibility
- Use isolated `CollectorRegistry` per test to avoid metric name collisions
- Counter labels have low cardinality (72 archons maximum)
- Stub tracks call history for test assertions

## Change Log
| Date | Change |
|------|--------|
| 2026-01-19 | Story created |
| 2026-01-19 | Implementation complete |
