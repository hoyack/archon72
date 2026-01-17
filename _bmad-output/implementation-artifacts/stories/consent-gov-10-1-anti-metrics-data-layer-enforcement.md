# Story consent-gov-10.1: Anti-Metrics Data Layer Enforcement

Status: done

---

## Story

As a **governance system**,
I want **anti-metrics enforced at the data layer**,
So that **no collection endpoints exist**.

---

## Acceptance Criteria

1. **AC1:** No participant-level performance metrics stored (FR61)
2. **AC2:** No completion rates per participant calculated (FR62)
3. **AC3:** No engagement or retention tracking (FR63)
4. **AC4:** Collection endpoints do not exist (NFR-CONST-08)
5. **AC5:** Schema validation prevents metric tables
6. **AC6:** Event `constitutional.anti_metrics.enforced` emitted on startup
7. **AC7:** Any metric collection attempt triggers violation
8. **AC8:** Unit tests verify no metric collection paths

---

## Tasks / Subtasks

- [x] **Task 1: Create AntiMetricsGuard** (AC: 1, 2, 3, 7)
  - [x] Create `src/infrastructure/adapters/governance/anti_metrics_guard.py`
  - [x] Intercept any metric storage attempts
  - [x] Block participant-level metrics
  - [x] Emit violation event on attempts

- [x] **Task 2: Implement schema validation** (AC: 5)
  - [x] Define prohibited table patterns
  - [x] Validate schema on startup
  - [x] Block metric table creation
  - [x] Migration guard for new tables

- [x] **Task 3: Implement structural absence** (AC: 4)
  - [x] No `/metrics/participant` endpoint
  - [x] No `/analytics/engagement` endpoint
  - [x] No `/tracking/*` routes
  - [x] API router has no metric paths

- [x] **Task 4: Implement performance metric prevention** (AC: 1)
  - [x] No task completion rates per Cluster
  - [x] No response time tracking per Cluster
  - [x] No quality scores per Cluster
  - [x] Structural absence (no fields exist)

- [x] **Task 5: Implement completion rate prevention** (AC: 2)
  - [x] No calculation of success rates
  - [x] No calculation of failure rates
  - [x] No historical performance tracking
  - [x] No per-participant statistics

- [x] **Task 6: Implement engagement prevention** (AC: 3)
  - [x] No login tracking
  - [x] No session duration tracking
  - [x] No retention metrics
  - [x] No engagement scores

- [x] **Task 7: Emit enforcement event** (AC: 6)
  - [x] Emit on system startup
  - [x] Include guard status
  - [x] Include schema validation result
  - [x] Knight observes enforcement

- [x] **Task 8: Write comprehensive unit tests** (AC: 8)
  - [x] Test no metric storage paths exist
  - [x] Test metric table creation blocked
  - [x] Test metric endpoints don't exist
  - [x] Test violation on collection attempt

---

## Documentation Checklist

- [x] Architecture docs updated (anti-metrics) - in code docstrings
- [x] Prohibited patterns documented - in prohibited_pattern.py
- [x] Constitutional constraint explained - in module docstrings
- [x] N/A - README (internal component)

---

## File List

### Created Files
- `src/domain/governance/antimetrics/__init__.py` - Domain module exports
- `src/domain/governance/antimetrics/prohibited_pattern.py` - ProhibitedPattern enum and pattern lists
- `src/domain/governance/antimetrics/violation.py` - AntiMetricsViolation and AntiMetricsViolationError
- `src/application/ports/governance/anti_metrics_port.py` - Port interfaces (SchemaValidatorPort, EventEmitterPort, AntiMetricsGuardPort)
- `src/infrastructure/adapters/governance/anti_metrics_guard.py` - AntiMetricsGuard implementation
- `tests/unit/domain/governance/antimetrics/__init__.py` - Test package init
- `tests/unit/domain/governance/antimetrics/test_prohibited_patterns.py` - Pattern definition tests
- `tests/unit/domain/governance/antimetrics/test_violation.py` - Violation model tests
- `tests/unit/infrastructure/adapters/governance/test_anti_metrics_guard.py` - Guard implementation tests
- `tests/unit/api/__init__.py` - Test package init
- `tests/unit/api/routes/__init__.py` - Test package init
- `tests/unit/api/routes/test_no_metric_endpoints.py` - Structural absence tests

---

## Change Log

- 2026-01-17: Initial implementation of anti-metrics data layer enforcement
  - Created ProhibitedPattern enum with 6 pattern types (FR61-63)
  - Defined 12 prohibited table patterns and 13 prohibited column patterns
  - Implemented AntiMetricsGuard with schema validation and violation recording
  - Added 139 unit tests for comprehensive coverage
  - All tests passing

---

## Dev Agent Record

### Implementation Plan

1. Create domain models for prohibited patterns and violations (frozen dataclasses)
2. Create port interfaces for schema validation and event emission
3. Implement AntiMetricsGuard adapter with:
   - Schema validation on startup
   - Table creation blocking
   - Column addition blocking
   - Violation event emission
4. Add structural absence tests to verify no metric endpoints/methods exist

### Completion Notes

**Implementation Summary:**
- Implemented structural absence pattern - methods for storing metrics INTENTIONALLY do not exist
- All 139 tests passing:
  - 58 domain model tests (patterns, violations)
  - 73 guard implementation tests
  - 8 structural absence tests (API endpoints, routes, models)

**Key Design Decisions:**
1. Used frozen dataclasses for immutability (AntiMetricsViolation)
2. No update/delete methods - structural absence enforced by type system
3. Violations are recorded AND blocked (not just logged)
4. Event `constitutional.anti_metrics.enforced` emitted on successful startup validation

**Constitutional Compliance:**
- FR61: No participant-level performance metrics (enforced via pattern blocking)
- FR62: No completion rates per participant (enforced via pattern blocking)
- FR63: No engagement/retention tracking (enforced via pattern blocking)
- NFR-CONST-08: Anti-metrics enforced at data layer (structural absence verified)

---

## Dev Notes

### Key Architectural Decisions

**Why Anti-Metrics?**
```
The system exists to serve, not to surveil:
  - No engagement optimization
  - No retention tracking
  - No performance scoring
  - No participant surveillance

Why structural absence?
  - Policy can be overridden
  - Code can be bypassed
  - Absence cannot be circumvented
  - What doesn't exist can't be used
```

**Data Layer Enforcement:**
```
NFR-CONST-08: Anti-metrics enforced at data layer

Data layer = lowest level:
  - Schema prevents metric tables
  - No columns for metrics
  - No storage paths exist
  - Cannot store what has no place

Why data layer?
  - Application logic can be changed
  - API endpoints can be added
  - Data layer is foundational
  - Hardest to circumvent
```

**Structural Absence Pattern:**
```
Traditional: "Don't track metrics" (policy)
  - Can be ignored
  - Can be "accidentally" implemented
  - Requires ongoing vigilance

Structural: No metrics infrastructure exists
  - No metric tables in schema
  - No metric endpoints in router
  - No metric fields in models
  - Cannot use what doesn't exist

Enforcement:
  - Schema guard prevents table creation
  - Router has no metric routes
  - Models have no metric fields
  - Guard detects and blocks attempts
```

### Domain Models

```python
class ProhibitedPattern(Enum):
    """Patterns that are prohibited by anti-metrics."""
    PARTICIPANT_PERFORMANCE = "participant_performance"
    COMPLETION_RATE = "completion_rate"
    ENGAGEMENT_TRACKING = "engagement_tracking"
    RETENTION_METRICS = "retention_metrics"
    SESSION_TRACKING = "session_tracking"
    RESPONSE_TIME_PER_PARTICIPANT = "response_time_per_participant"


PROHIBITED_TABLE_PATTERNS = [
    r".*_metrics$",
    r".*_performance$",
    r".*_engagement$",
    r".*_retention$",
    r".*_analytics$",
    r"participant_scores",
    r"completion_rates",
    r"session_tracking",
]

PROHIBITED_COLUMN_PATTERNS = [
    r"completion_rate",
    r"success_rate",
    r"failure_rate",
    r"performance_score",
    r"engagement_score",
    r"retention_score",
    r"session_count",
    r"login_count",
]


@dataclass(frozen=True)
class AntiMetricsViolation:
    """Record of anti-metrics violation attempt."""
    violation_id: UUID
    attempted_at: datetime
    pattern: ProhibitedPattern
    attempted_by: str
    description: str


class AntiMetricsViolationError(ValueError):
    """Raised when anti-metrics constraint is violated."""
    pass
```

### Service Implementation Sketch

```python
class AntiMetricsGuard:
    """Enforces anti-metrics at data layer.

    Structural absence pattern:
    - No metric tables allowed
    - No metric columns allowed
    - No metric endpoints allowed
    - Collection attempts trigger violations
    """

    def __init__(
        self,
        schema_validator: SchemaValidator,
        event_emitter: EventEmitter,
        time_authority: TimeAuthority,
    ):
        self._schema = schema_validator
        self._event_emitter = event_emitter
        self._time = time_authority

    async def enforce_on_startup(self) -> None:
        """Enforce anti-metrics on system startup.

        Validates schema has no metric tables.
        Emits enforcement event.
        """
        now = self._time.now()

        # Validate schema
        violations = await self._schema.check_for_metric_tables()

        if violations:
            raise AntiMetricsViolationError(
                f"Schema contains prohibited metric tables: {violations}"
            )

        # Emit enforcement event
        await self._event_emitter.emit(
            event_type="constitutional.anti_metrics.enforced",
            actor="system",
            payload={
                "enforced_at": now.isoformat(),
                "schema_valid": True,
                "prohibited_patterns_checked": len(PROHIBITED_TABLE_PATTERNS),
            },
        )

    async def check_table_creation(
        self,
        table_name: str,
    ) -> None:
        """Check if table creation violates anti-metrics.

        Args:
            table_name: Name of table being created

        Raises:
            AntiMetricsViolationError: If table is prohibited
        """
        for pattern in PROHIBITED_TABLE_PATTERNS:
            if re.match(pattern, table_name):
                await self._record_violation(
                    pattern=ProhibitedPattern.PARTICIPANT_PERFORMANCE,
                    attempted_by="migration",
                    description=f"Attempted to create metric table: {table_name}",
                )
                raise AntiMetricsViolationError(
                    f"Cannot create metric table: {table_name}"
                )

    async def check_column_addition(
        self,
        table_name: str,
        column_name: str,
    ) -> None:
        """Check if column addition violates anti-metrics.

        Args:
            table_name: Table the column is being added to
            column_name: Name of column being added

        Raises:
            AntiMetricsViolationError: If column is prohibited
        """
        for pattern in PROHIBITED_COLUMN_PATTERNS:
            if re.match(pattern, column_name):
                await self._record_violation(
                    pattern=ProhibitedPattern.PARTICIPANT_PERFORMANCE,
                    attempted_by="migration",
                    description=f"Attempted to add metric column: {table_name}.{column_name}",
                )
                raise AntiMetricsViolationError(
                    f"Cannot add metric column: {column_name}"
                )

    async def _record_violation(
        self,
        pattern: ProhibitedPattern,
        attempted_by: str,
        description: str,
    ) -> None:
        """Record and emit violation event."""
        now = self._time.now()

        violation = AntiMetricsViolation(
            violation_id=uuid4(),
            attempted_at=now,
            pattern=pattern,
            attempted_by=attempted_by,
            description=description,
        )

        await self._event_emitter.emit(
            event_type="constitutional.violation.anti_metrics",
            actor=attempted_by,
            payload={
                "violation_id": str(violation.violation_id),
                "pattern": pattern.value,
                "description": description,
                "attempted_at": now.isoformat(),
            },
        )

    # These methods do NOT exist (structural absence):
    # async def store_participant_performance(self, ...): ...
    # async def calculate_completion_rate(self, ...): ...
    # async def track_engagement(self, ...): ...


# API router explicitly has no metric endpoints
class GovernanceRouter:
    """API routes for governance.

    EXPLICITLY NO METRIC ENDPOINTS.
    """

    # Routes that DO NOT exist:
    # /metrics/participant/{id}
    # /analytics/engagement
    # /tracking/sessions
    # /performance/scores

    @router.get("/health")
    async def health_check(self) -> dict:
        """Health check endpoint."""
        return {"status": "healthy"}

    # Notice: No metric-related endpoints defined
```

### Event Patterns

```python
# Anti-metrics enforced
{
    "event_type": "constitutional.anti_metrics.enforced",
    "actor": "system",
    "payload": {
        "enforced_at": "2026-01-16T00:00:00Z",
        "schema_valid": true,
        "prohibited_patterns_checked": 8
    }
}

# Anti-metrics violation
{
    "event_type": "constitutional.violation.anti_metrics",
    "actor": "migration",
    "payload": {
        "violation_id": "uuid",
        "pattern": "participant_performance",
        "description": "Attempted to create metric table: cluster_metrics",
        "attempted_at": "2026-01-16T00:00:00Z"
    }
}
```

### Test Patterns

```python
class TestAntiMetricsGuard:
    """Unit tests for anti-metrics guard."""

    async def test_startup_enforcement(
        self,
        anti_metrics_guard: AntiMetricsGuard,
        clean_schema: Schema,
    ):
        """Anti-metrics enforced on startup."""
        await anti_metrics_guard.enforce_on_startup()
        # Should not raise

    async def test_metric_table_blocked(
        self,
        anti_metrics_guard: AntiMetricsGuard,
    ):
        """Metric table creation is blocked."""
        with pytest.raises(AntiMetricsViolationError):
            await anti_metrics_guard.check_table_creation(
                table_name="cluster_metrics"
            )

    async def test_metric_column_blocked(
        self,
        anti_metrics_guard: AntiMetricsGuard,
    ):
        """Metric column addition is blocked."""
        with pytest.raises(AntiMetricsViolationError):
            await anti_metrics_guard.check_column_addition(
                table_name="clusters",
                column_name="completion_rate",
            )

    async def test_enforcement_event_emitted(
        self,
        anti_metrics_guard: AntiMetricsGuard,
        event_capture: EventCapture,
    ):
        """Enforcement event is emitted."""
        await anti_metrics_guard.enforce_on_startup()

        event = event_capture.get_last("constitutional.anti_metrics.enforced")
        assert event is not None


class TestNoMetricStorage:
    """Tests ensuring no metric storage paths exist."""

    def test_no_performance_storage_method(
        self,
        anti_metrics_guard: AntiMetricsGuard,
    ):
        """No performance storage method exists."""
        assert not hasattr(anti_metrics_guard, "store_participant_performance")
        assert not hasattr(anti_metrics_guard, "save_metrics")

    def test_no_completion_rate_method(
        self,
        anti_metrics_guard: AntiMetricsGuard,
    ):
        """No completion rate calculation method exists."""
        assert not hasattr(anti_metrics_guard, "calculate_completion_rate")
        assert not hasattr(anti_metrics_guard, "compute_success_rate")

    def test_no_engagement_tracking_method(
        self,
        anti_metrics_guard: AntiMetricsGuard,
    ):
        """No engagement tracking method exists."""
        assert not hasattr(anti_metrics_guard, "track_engagement")
        assert not hasattr(anti_metrics_guard, "record_session")


class TestNoMetricEndpoints:
    """Tests ensuring no metric API endpoints exist."""

    async def test_no_metrics_endpoint(
        self,
        client: TestClient,
    ):
        """No /metrics endpoint exists."""
        response = await client.get("/metrics/participant/test")
        assert response.status_code == 404

    async def test_no_analytics_endpoint(
        self,
        client: TestClient,
    ):
        """No /analytics endpoint exists."""
        response = await client.get("/analytics/engagement")
        assert response.status_code == 404

    async def test_no_tracking_endpoint(
        self,
        client: TestClient,
    ):
        """No /tracking endpoint exists."""
        response = await client.get("/tracking/sessions")
        assert response.status_code == 404


class TestProhibitedPatterns:
    """Tests for prohibited pattern detection."""

    @pytest.mark.parametrize("table_name", [
        "cluster_metrics",
        "task_performance",
        "user_engagement",
        "session_retention",
        "cluster_analytics",
        "participant_scores",
        "completion_rates",
    ])
    async def test_prohibited_table_detected(
        self,
        anti_metrics_guard: AntiMetricsGuard,
        table_name: str,
    ):
        """Prohibited table names are detected."""
        with pytest.raises(AntiMetricsViolationError):
            await anti_metrics_guard.check_table_creation(table_name)

    @pytest.mark.parametrize("column_name", [
        "completion_rate",
        "success_rate",
        "failure_rate",
        "performance_score",
        "engagement_score",
    ])
    async def test_prohibited_column_detected(
        self,
        anti_metrics_guard: AntiMetricsGuard,
        column_name: str,
    ):
        """Prohibited column names are detected."""
        with pytest.raises(AntiMetricsViolationError):
            await anti_metrics_guard.check_column_addition(
                table_name="any_table",
                column_name=column_name,
            )
```

### Dependencies

- **Depends on:** consent-gov-1-1 (event infrastructure)
- **Enables:** consent-gov-10-2 (verification)

### References

- FR61: System can coordinate tasks without storing participant-level performance metrics
- FR62: System can complete task workflows without calculating completion rates per participant
- FR63: System can operate without engagement or retention tracking
- NFR-CONST-08: Anti-metrics are enforced at data layer; collection endpoints do not exist
