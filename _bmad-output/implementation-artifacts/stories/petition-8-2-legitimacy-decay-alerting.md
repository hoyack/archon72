# Story 8.2: Legitimacy Decay Alerting

**Epic:** Epic 8 - Legitimacy Metrics & Governance
**Story ID:** petition-8-2-legitimacy-decay-alerting
**Priority:** P1
**Status:** ready

## User Story

As a **system operator**,
I want alerts when legitimacy score drops below threshold,
So that governance health issues are promptly addressed.

## Requirements Coverage

### Functional Requirements
- **FR-8.3:** System SHALL alert on decay below 0.85 threshold

### Non-Functional Requirements
- **NFR-7.2:** Legitimacy decay alerting - Alert at < 0.85 threshold

### Constitutional Triggers
- **CT-12:** Witnessing creates accountability - Alert events are witnessed

## Dependencies

### Prerequisites
- ✅ Story 8.1: Legitimacy Decay Metric Computation (complete)
  - `LegitimacyMetrics` domain model
  - `LegitimacyMetricsComputationService`
  - `legitimacy_metrics` table with scores

### Integration Points
- Event system for alert emission
- External alerting channels (PagerDuty, Slack, email)
- Configuration system for thresholds

## Acceptance Criteria

### AC1: Alert Triggering on Low Score

**Given** legitimacy score is computed
**When** the score falls below 0.85 (configurable threshold)
**Then** a `LegitimacyAlertTriggered` event is emitted containing:
  - `cycle_id` - The affected cycle identifier
  - `current_score` - The legitimacy score that triggered the alert
  - `threshold` - The threshold that was breached (0.85 or 0.70)
  - `severity` - Alert severity ("WARNING" or "CRITICAL")
  - `stuck_petition_count` - Count of petitions not fated within SLA
  - `triggered_at` - Timestamp when alert was raised

**And** alert severity is:
  - `WARNING` when score is < 0.85 and >= 0.70
  - `CRITICAL` when score is < 0.70

### AC2: Multi-Channel Alert Delivery

**Given** a `LegitimacyAlertTriggered` event is emitted
**When** the alert delivery service processes the event
**Then** the alert is delivered to all configured channels:
  - **PagerDuty:** For on-call engineers (CRITICAL only)
  - **Slack:** To #governance-alerts channel
  - **Email:** To governance-alerts@archon72.org distribution list

**And** delivery failures are logged with retry mechanism
**And** delivery status is tracked per channel

### AC3: Alert Recovery Notification

**Given** an active legitimacy alert exists
**And** legitimacy score recovers above the threshold
**When** the next cycle's metrics are computed
**Then** a `LegitimacyAlertRecovered` event is emitted containing:
  - `cycle_id` - The recovery cycle identifier
  - `current_score` - The recovered legitimacy score
  - `previous_score` - The score that triggered the alert
  - `alert_duration` - How long the system was in alert state
  - `recovered_at` - Timestamp when alert was resolved

**And** a recovery notification is sent to the same channels
**And** the alert state is cleared

### AC4: Alert State Management

**Given** the system tracks alert state
**When** multiple cycles breach the threshold consecutively
**Then** only ONE alert is active at a time
**And** subsequent breaches update the existing alert (no duplicate alerts)
**And** the alert includes cumulative duration in alert state

**Given** the score fluctuates around the threshold (e.g., 0.849 → 0.851 → 0.848)
**When** within a 24-hour window
**Then** hysteresis logic prevents alert flapping:
  - Recovery requires score >= threshold + 0.02 (e.g., >= 0.87 for 0.85 threshold)
  - Alert re-trigger requires 2 consecutive cycles below threshold

### AC5: Configurable Thresholds

**Given** alert thresholds are configurable
**When** configured via environment variables or config file
**Then** the following settings are supported:
  - `LEGITIMACY_WARNING_THRESHOLD` (default: 0.85)
  - `LEGITIMACY_CRITICAL_THRESHOLD` (default: 0.70)
  - `ALERT_HYSTERESIS_BUFFER` (default: 0.02)
  - `ALERT_FLAP_DETECTION_WINDOW` (default: 24 hours)

**And** invalid thresholds are rejected (e.g., WARNING < CRITICAL)

### AC6: Alert Observability

**Given** alerting is operational
**When** alerts are triggered or recovered
**Then** Prometheus metrics are updated:
  - `legitimacy_alerts_triggered_total` (counter, labeled by severity)
  - `legitimacy_alerts_active` (gauge, 0 or 1)
  - `legitimacy_alert_duration_seconds` (histogram)
  - `legitimacy_alert_delivery_failures_total` (counter, labeled by channel)

**And** alert history is queryable via API

## Technical Design

### Domain Models

#### Alert Event Models

```python
@dataclass(frozen=True)
class LegitimacyAlertTriggered:
    """Alert event when legitimacy score drops below threshold."""
    event_id: UUID
    cycle_id: str  # e.g., "2026-W04"
    current_score: Decimal
    threshold: Decimal
    severity: AlertSeverity
    stuck_petition_count: int
    triggered_at: datetime

@dataclass(frozen=True)
class LegitimacyAlertRecovered:
    """Alert event when legitimacy score recovers above threshold."""
    event_id: UUID
    cycle_id: str
    current_score: Decimal
    previous_score: Decimal
    alert_duration: timedelta
    recovered_at: datetime

class AlertSeverity(StrEnum):
    """Alert severity levels."""
    WARNING = "WARNING"   # Score < 0.85
    CRITICAL = "CRITICAL" # Score < 0.70
```

#### Alert State Model

```python
@dataclass
class LegitimacyAlertState:
    """Tracks current alert state to prevent flapping."""
    alert_id: UUID
    is_active: bool
    severity: AlertSeverity
    triggered_at: datetime
    last_updated: datetime
    consecutive_breaches: int
    alert_history: List[Tuple[datetime, Decimal]]  # Timestamp, score
```

### Service Layer

#### LegitimacyAlertingService

```python
class LegitimacyAlertingService:
    """Service for legitimacy decay alerting logic."""

    def check_and_alert(
        self,
        metrics: LegitimacyMetrics,
        previous_alert_state: Optional[LegitimacyAlertState]
    ) -> Tuple[Optional[LegitimacyAlertTriggered], Optional[LegitimacyAlertRecovered]]:
        """
        Check if alert should be triggered or recovered.

        Returns: (trigger_event, recovery_event)
        """
        # Check for alert trigger
        # Check for recovery with hysteresis
        # Apply flap detection
        pass

    def determine_severity(self, score: Decimal) -> Optional[AlertSeverity]:
        """Determine alert severity based on score."""
        if score < self.critical_threshold:
            return AlertSeverity.CRITICAL
        elif score < self.warning_threshold:
            return AlertSeverity.WARNING
        return None

    def count_stuck_petitions(self, cycle_id: str) -> int:
        """Count petitions that didn't reach terminal state within SLA."""
        # Query petitions from cycle that are still in RECEIVED or DELIBERATING
        pass
```

#### AlertDeliveryService

```python
class AlertDeliveryService:
    """Service for delivering alerts to external channels."""

    async def deliver_alert(
        self,
        alert: LegitimacyAlertTriggered,
        channels: List[AlertChannel]
    ) -> Dict[AlertChannel, DeliveryStatus]:
        """Deliver alert to all configured channels."""
        pass

    async def deliver_recovery(
        self,
        recovery: LegitimacyAlertRecovered,
        channels: List[AlertChannel]
    ) -> Dict[AlertChannel, DeliveryStatus]:
        """Deliver recovery notification."""
        pass

class AlertChannel(StrEnum):
    PAGERDUTY = "pagerduty"
    SLACK = "slack"
    EMAIL = "email"
```

### Database Schema

#### Alert State Table (Optional - for persistence)

```sql
-- Table: legitimacy_alert_state
-- Tracks current alert state across service restarts

CREATE TABLE IF NOT EXISTS legitimacy_alert_state (
    alert_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    is_active BOOLEAN NOT NULL,
    severity TEXT NOT NULL CHECK (severity IN ('WARNING', 'CRITICAL')),
    triggered_at TIMESTAMPTZ NOT NULL,
    last_updated TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    consecutive_breaches INT NOT NULL DEFAULT 1,

    -- Single row constraint (only one alert state at a time)
    CONSTRAINT single_alert_state CHECK (alert_id = alert_id)
);

-- Ensure only one row exists
CREATE UNIQUE INDEX idx_single_alert_state ON legitimacy_alert_state ((true));
```

#### Alert History Table

```sql
-- Table: legitimacy_alert_history
-- Historical record of all alerts for analysis

CREATE TABLE IF NOT EXISTS legitimacy_alert_history (
    history_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cycle_id TEXT NOT NULL,
    event_type TEXT NOT NULL CHECK (event_type IN ('TRIGGERED', 'RECOVERED')),
    severity TEXT CHECK (severity IN ('WARNING', 'CRITICAL')),
    score DECIMAL(5, 4) NOT NULL,
    threshold DECIMAL(5, 4),
    stuck_petition_count INT,
    alert_duration_seconds INT,  -- NULL for TRIGGERED events
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index for querying alert history
CREATE INDEX idx_alert_history_cycle ON legitimacy_alert_history(cycle_id);
CREATE INDEX idx_alert_history_occurred ON legitimacy_alert_history(occurred_at DESC);
```

### Integration with Story 8.1

The alerting service integrates with the metrics computation service:

```python
# In LegitimacyMetricsComputationService

async def compute_and_alert(self, cycle_id: str) -> LegitimacyMetrics:
    """Compute metrics and check for alerts."""

    # 1. Compute metrics (Story 8.1)
    metrics = await self.compute_metrics(cycle_id)

    # 2. Check alert conditions (Story 8.2)
    previous_state = await self.alert_state_repo.get_current_state()
    trigger_event, recovery_event = self.alerting_service.check_and_alert(
        metrics, previous_state
    )

    # 3. Emit alert events if needed
    if trigger_event:
        await self.event_writer.write_event(trigger_event)
        await self.alert_delivery.deliver_alert(trigger_event, channels)

    if recovery_event:
        await self.event_writer.write_event(recovery_event)
        await self.alert_delivery.deliver_recovery(recovery_event, channels)

    return metrics
```

## Testing Strategy

### Unit Tests (Target: 30+ tests)

1. **Alert Condition Detection** (8 tests)
   - Test WARNING triggered at score = 0.849
   - Test CRITICAL triggered at score = 0.699
   - Test no alert when score >= 0.85
   - Test severity escalation (WARNING → CRITICAL)
   - Test severity de-escalation (CRITICAL → WARNING → recovered)
   - Test exact boundary conditions (0.85, 0.70)
   - Test stuck petition count computation
   - Test invalid threshold configuration

2. **Hysteresis & Flap Detection** (6 tests)
   - Test recovery requires threshold + buffer (0.87 for 0.85)
   - Test flapping prevention (alternating scores)
   - Test consecutive breach counting
   - Test 24-hour flap window enforcement
   - Test recovery after sustained improvement
   - Test multiple cycles in alert state

3. **Alert State Management** (5 tests)
   - Test single active alert constraint
   - Test alert state persistence across cycles
   - Test alert update on consecutive breach
   - Test alert clearing on recovery
   - Test alert duration calculation

4. **Event Emission** (4 tests)
   - Test `LegitimacyAlertTriggered` event structure
   - Test `LegitimacyAlertRecovered` event structure
   - Test event includes all required fields
   - Test event witnessing (CT-12 compliance)

5. **Channel Delivery** (7 tests)
   - Test PagerDuty delivery for CRITICAL only
   - Test Slack delivery for all severities
   - Test email delivery for all severities
   - Test delivery failure logging
   - Test retry mechanism on failure
   - Test delivery status tracking
   - Test channel configuration

### Integration Tests (Target: 15+ tests)

1. **End-to-End Alert Flow** (5 tests)
   - Test metrics computation → alert trigger → delivery
   - Test alert recovery flow
   - Test multi-cycle alert persistence
   - Test alert escalation (WARNING → CRITICAL)
   - Test alert history recording

2. **Database Integration** (4 tests)
   - Test alert state persistence
   - Test alert history insertion
   - Test single alert state constraint
   - Test alert state queries

3. **Event System Integration** (3 tests)
   - Test alert events written to event store
   - Test event witnessing with Blake3 hash
   - Test event ordering guarantees

4. **Configuration Integration** (3 tests)
   - Test threshold configuration from env vars
   - Test hysteresis configuration
   - Test channel configuration

### Mock vs Real Dependencies

- **Mock:** External alert channels (PagerDuty, Slack, email) in unit tests
- **Real:** Database, event system in integration tests
- **Stub:** Alert delivery service with in-memory tracking

## Configuration

### Environment Variables

```bash
# Alert thresholds
LEGITIMACY_WARNING_THRESHOLD=0.85
LEGITIMACY_CRITICAL_THRESHOLD=0.70
ALERT_HYSTERESIS_BUFFER=0.02
ALERT_FLAP_DETECTION_WINDOW_HOURS=24

# Alert channels
ALERT_PAGERDUTY_ENABLED=true
ALERT_PAGERDUTY_API_KEY=<secret>
ALERT_SLACK_ENABLED=true
ALERT_SLACK_WEBHOOK_URL=<secret>
ALERT_EMAIL_ENABLED=true
ALERT_EMAIL_RECIPIENTS=governance-alerts@archon72.org
```

## Migration

**Migration 031: Create alert state and history tables**

- Create `legitimacy_alert_state` table
- Create `legitimacy_alert_history` table
- Add indexes for efficient querying

## Prometheus Metrics

```python
# Counters
legitimacy_alerts_triggered_total{severity="WARNING|CRITICAL"}
legitimacy_alert_delivery_failures_total{channel="pagerduty|slack|email"}

# Gauges
legitimacy_alerts_active  # 0 or 1

# Histograms
legitimacy_alert_duration_seconds{severity="WARNING|CRITICAL"}
```

## API Endpoints (Future - Story 8.4)

```
GET /api/v1/governance/legitimacy/alerts
  → Returns alert history

GET /api/v1/governance/legitimacy/alerts/current
  → Returns current alert state (if active)
```

## Success Criteria

### Functional Completeness
- [ ] Alerts trigger at correct thresholds (0.85, 0.70)
- [ ] Alert severity correctly determined
- [ ] Recovery notifications sent when score improves
- [ ] Hysteresis prevents flapping
- [ ] Multi-channel delivery works

### Non-Functional Compliance
- [ ] **NFR-7.2:** Alert delivery within 1 minute of trigger
- [ ] Unit test coverage > 90%
- [ ] Integration tests cover all scenarios
- [ ] No false positives from flapping

### Constitutional Compliance
- [ ] **CT-12:** Alert events are witnessed and immutable
- [ ] **FR-8.3:** Alert at < 0.85 threshold

## Implementation Tasks

### Phase 1: Domain Models & Core Logic (2-3 hours)
1. Create `LegitimacyAlertTriggered` event model
2. Create `LegitimacyAlertRecovered` event model
3. Create `LegitimacyAlertState` domain model
4. Implement `LegitimacyAlertingService` core logic
5. Implement severity determination
6. Implement hysteresis logic
7. Implement flap detection
8. Unit tests (30+ tests)

### Phase 2: Database & Persistence (1-2 hours)
9. Create migration 031 (alert tables)
10. Implement `AlertStateRepository`
11. Implement `AlertHistoryRepository`
12. Integration tests for persistence

### Phase 3: Event Emission & Delivery (2-3 hours)
13. Integrate with `EventWriterService`
14. Implement `AlertDeliveryService` protocol
15. Implement stub delivery service (in-memory)
16. Implement channel configuration
17. Integration tests for delivery

### Phase 4: Metrics & Observability (1 hour)
18. Add Prometheus metrics
19. Add structured logging
20. Verify metrics emission

### Phase 5: Integration with Story 8.1 (1 hour)
21. Update `LegitimacyMetricsComputationService` to call alerting
22. End-to-end integration tests
23. Verify alert flow from metrics computation

**Estimated Total: 7-10 hours**

## Notes

- Alert channel implementations (PagerDuty, Slack, email) can be stubbed initially
- Real channel integrations can be added incrementally
- Alert delivery is asynchronous - failures should not block metrics computation
- Consider rate limiting alert notifications (e.g., max 1 per hour per severity)
- Alert history retention policy: Keep 90 days of history

## Related Stories

- **Story 8.1:** Legitimacy Decay Metric Computation (prerequisite)
- **Story 8.3:** Orphan Petition Detection (similar alerting pattern)
- **Story 8.4:** High Archon Legitimacy Dashboard (will display alert status)

---

**Story Status:** Ready for Implementation
**Estimated Effort:** 7-10 hours
**Risk Level:** Low (well-defined alerting pattern)
