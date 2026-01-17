# Story consent-gov-10.2: Anti-Metrics Verification

Status: done

---

## Story

As an **auditor**,
I want **to verify no metrics are collected**,
So that **I can confirm the anti-surveillance guarantee**.

---

## Acceptance Criteria

1. **AC1:** Audit query confirms no metric tables exist
2. **AC2:** Audit confirms no metric API endpoints exist
3. **AC3:** Periodic verification job runs automatically
4. **AC4:** Event `audit.anti_metrics.verified` emitted after verification
5. **AC5:** Verification detects any violations
6. **AC6:** Verification is independently runnable
7. **AC7:** Clear report of verification results
8. **AC8:** Unit tests for verification

---

## Tasks / Subtasks

- [x] **Task 1: Create AntiMetricsVerificationService** (AC: 1, 2, 5)
  - [x] Create `src/application/services/governance/anti_metrics_verification_service.py`
  - [x] Verify no metric tables
  - [x] Verify no metric endpoints
  - [x] Detect any violations

- [x] **Task 2: Implement schema verification** (AC: 1)
  - [x] Query all table names
  - [x] Check against prohibited patterns
  - [x] Check all column names
  - [x] Report any violations

- [x] **Task 3: Implement endpoint verification** (AC: 2)
  - [x] Enumerate all API routes
  - [x] Check for metric-related routes
  - [x] Check for analytics routes
  - [x] Report any violations

- [x] **Task 4: Implement periodic job** (AC: 3)
  - [x] Schedule verification job
  - [x] Run on configurable interval
  - [x] Log results each run
  - [x] Alert on violations

- [x] **Task 5: Implement verification event** (AC: 4)
  - [x] Emit after each verification
  - [x] Include tables checked
  - [x] Include endpoints checked
  - [x] Include result status

- [x] **Task 6: Implement independent runner** (AC: 6)
  - [x] CLI command for verification
  - [x] Can run standalone
  - [x] No system dependency
  - [x] Works with database directly

- [x] **Task 7: Implement verification report** (AC: 7)
  - [x] Clear pass/fail status
  - [x] List of checks performed
  - [x] Details of any violations
  - [x] Recommendation for remediation

- [x] **Task 8: Write comprehensive unit tests** (AC: 8)
  - [x] Test schema verification
  - [x] Test endpoint verification
  - [x] Test violation detection
  - [x] Test report generation

---

## Documentation Checklist

- [ ] Architecture docs updated (verification process)
- [ ] Auditor guide for verification
- [ ] CLI usage documented
- [ ] N/A - README (internal component)

---

## Dev Notes

### Key Architectural Decisions

**Why Verification?**
```
Trust but verify:
  - Anti-metrics guard should prevent violations
  - Verification confirms prevention worked
  - Auditors can independently check
  - Defense in depth

Verification answers:
  - Are there any metric tables? (Should be: No)
  - Are there any metric endpoints? (Should be: No)
  - Have any violations been recorded?
  - Is the system surveillance-free?
```

**Periodic Verification:**
```
Why periodic?
  - Schema could change (migrations)
  - Code could change (new endpoints)
  - Continuous assurance
  - Early detection

Schedule:
  - Daily minimum
  - After each deployment
  - On demand (CLI)
  - After schema migrations
```

**Independent Verification:**
```
Auditor requirements:
  - Run verification themselves
  - No system trust required
  - Direct database access
  - CLI tool available

Independence means:
  - Verifier brings own tools
  - System cannot hide violations
  - Results are reproducible
  - Third-party auditable
```

### Domain Models

```python
class VerificationCheck(Enum):
    """Type of verification check."""
    SCHEMA_TABLES = "schema_tables"
    SCHEMA_COLUMNS = "schema_columns"
    API_ENDPOINTS = "api_endpoints"
    PROHIBITED_PATTERNS = "prohibited_patterns"


class VerificationStatus(Enum):
    """Status of verification."""
    PASS = "pass"
    FAIL = "fail"


@dataclass(frozen=True)
class CheckResult:
    """Result of a single verification check."""
    check_type: VerificationCheck
    status: VerificationStatus
    items_checked: int
    violations_found: list[str]


@dataclass(frozen=True)
class VerificationReport:
    """Complete verification report."""
    report_id: UUID
    verified_at: datetime
    overall_status: VerificationStatus
    checks: list[CheckResult]
    total_violations: int
    verification_duration_ms: int


class VerificationFailedError(ValueError):
    """Raised when verification finds violations."""
    pass
```

### Service Implementation Sketch

```python
class AntiMetricsVerificationService:
    """Verifies anti-metrics constraints are enforced.

    Can be run independently by auditors.
    """

    def __init__(
        self,
        schema_inspector: SchemaInspector,
        route_inspector: RouteInspector,
        event_emitter: EventEmitter | None,  # Optional for independent
        time_authority: TimeAuthority,
    ):
        self._schema = schema_inspector
        self._routes = route_inspector
        self._event_emitter = event_emitter
        self._time = time_authority

    async def verify_all(
        self,
        verifier_id: UUID | None = None,
    ) -> VerificationReport:
        """Run complete anti-metrics verification.

        Can be run independently (event_emitter optional).

        Args:
            verifier_id: Optional verifier ID (for logging)

        Returns:
            VerificationReport with all check results
        """
        start = self._time.now()
        checks = []

        # Check schema tables
        table_result = await self._verify_tables()
        checks.append(table_result)

        # Check schema columns
        column_result = await self._verify_columns()
        checks.append(column_result)

        # Check API endpoints
        endpoint_result = await self._verify_endpoints()
        checks.append(endpoint_result)

        end = self._time.now()
        duration_ms = int((end - start).total_seconds() * 1000)

        # Calculate overall status
        total_violations = sum(len(c.violations_found) for c in checks)
        overall = VerificationStatus.PASS if total_violations == 0 else VerificationStatus.FAIL

        report = VerificationReport(
            report_id=uuid4(),
            verified_at=start,
            overall_status=overall,
            checks=checks,
            total_violations=total_violations,
            verification_duration_ms=duration_ms,
        )

        # Emit event if online
        if self._event_emitter and verifier_id:
            await self._event_emitter.emit(
                event_type="audit.anti_metrics.verified",
                actor=str(verifier_id),
                payload={
                    "report_id": str(report.report_id),
                    "verifier_id": str(verifier_id),
                    "verified_at": start.isoformat(),
                    "overall_status": overall.value,
                    "total_violations": total_violations,
                    "checks_performed": len(checks),
                },
            )

        return report

    async def _verify_tables(self) -> CheckResult:
        """Verify no metric tables exist."""
        tables = await self._schema.get_all_tables()
        violations = []

        for table in tables:
            for pattern in PROHIBITED_TABLE_PATTERNS:
                if re.match(pattern, table):
                    violations.append(f"Prohibited table: {table}")

        return CheckResult(
            check_type=VerificationCheck.SCHEMA_TABLES,
            status=VerificationStatus.PASS if not violations else VerificationStatus.FAIL,
            items_checked=len(tables),
            violations_found=violations,
        )

    async def _verify_columns(self) -> CheckResult:
        """Verify no metric columns exist."""
        columns = await self._schema.get_all_columns()
        violations = []

        for table, column in columns:
            for pattern in PROHIBITED_COLUMN_PATTERNS:
                if re.match(pattern, column):
                    violations.append(f"Prohibited column: {table}.{column}")

        return CheckResult(
            check_type=VerificationCheck.SCHEMA_COLUMNS,
            status=VerificationStatus.PASS if not violations else VerificationStatus.FAIL,
            items_checked=len(columns),
            violations_found=violations,
        )

    async def _verify_endpoints(self) -> CheckResult:
        """Verify no metric endpoints exist."""
        endpoints = await self._routes.get_all_routes()
        violations = []

        prohibited_paths = [
            r"^/metrics/",
            r"^/analytics/",
            r"^/tracking/",
            r"^/performance/",
            r"/engagement",
            r"/retention",
        ]

        for endpoint in endpoints:
            for pattern in prohibited_paths:
                if re.match(pattern, endpoint.path):
                    violations.append(f"Prohibited endpoint: {endpoint.method} {endpoint.path}")

        return CheckResult(
            check_type=VerificationCheck.API_ENDPOINTS,
            status=VerificationStatus.PASS if not violations else VerificationStatus.FAIL,
            items_checked=len(endpoints),
            violations_found=violations,
        )

    def generate_report_text(self, report: VerificationReport) -> str:
        """Generate human-readable report text."""
        lines = [
            "=" * 60,
            "ANTI-METRICS VERIFICATION REPORT",
            "=" * 60,
            f"Report ID: {report.report_id}",
            f"Verified At: {report.verified_at.isoformat()}",
            f"Duration: {report.verification_duration_ms}ms",
            f"Overall Status: {report.overall_status.value.upper()}",
            "",
            "-" * 60,
            "CHECKS PERFORMED",
            "-" * 60,
        ]

        for check in report.checks:
            status_mark = "PASS" if check.status == VerificationStatus.PASS else "FAIL"
            lines.append(f"[{status_mark}] {check.check_type.value}")
            lines.append(f"      Items checked: {check.items_checked}")
            if check.violations_found:
                lines.append(f"      Violations: {len(check.violations_found)}")
                for v in check.violations_found:
                    lines.append(f"        - {v}")

        lines.extend([
            "",
            "-" * 60,
            "SUMMARY",
            "-" * 60,
            f"Total violations: {report.total_violations}",
        ])

        if report.total_violations > 0:
            lines.extend([
                "",
                "REMEDIATION REQUIRED:",
                "  1. Remove prohibited tables/columns",
                "  2. Remove prohibited API endpoints",
                "  3. Re-run verification",
            ])
        else:
            lines.append("System is confirmed surveillance-free.")

        lines.append("=" * 60)

        return "\n".join(lines)


# CLI for independent verification
async def verify_anti_metrics_cli(database_url: str) -> None:
    """CLI command for independent verification.

    Can be run by auditors without system access.

    Usage:
        python -m governance.verify_anti_metrics postgres://...
    """
    # Create inspectors directly from database
    schema_inspector = PostgresSchemaInspector(database_url)
    route_inspector = StaticRouteInspector()

    # Create service (no event emitter - independent)
    service = AntiMetricsVerificationService(
        schema_inspector=schema_inspector,
        route_inspector=route_inspector,
        event_emitter=None,
        time_authority=SystemTimeAuthority(),
    )

    # Run verification
    report = await service.verify_all()

    # Print report
    print(service.generate_report_text(report))

    # Exit with appropriate code
    if report.overall_status == VerificationStatus.FAIL:
        sys.exit(1)
    sys.exit(0)
```

### Event Pattern

```python
# Anti-metrics verified
{
    "event_type": "audit.anti_metrics.verified",
    "actor": "verifier-uuid",
    "payload": {
        "report_id": "uuid",
        "verifier_id": "uuid",
        "verified_at": "2026-01-16T00:00:00Z",
        "overall_status": "pass",
        "total_violations": 0,
        "checks_performed": 3
    }
}
```

### Test Patterns

```python
class TestAntiMetricsVerificationService:
    """Unit tests for anti-metrics verification service."""

    async def test_clean_system_passes(
        self,
        verification_service: AntiMetricsVerificationService,
        clean_schema: Schema,
    ):
        """Clean system passes verification."""
        report = await verification_service.verify_all()

        assert report.overall_status == VerificationStatus.PASS
        assert report.total_violations == 0

    async def test_metric_table_detected(
        self,
        verification_service: AntiMetricsVerificationService,
        schema_with_metric_table: Schema,
    ):
        """Metric table is detected."""
        report = await verification_service.verify_all()

        assert report.overall_status == VerificationStatus.FAIL
        table_check = next(
            c for c in report.checks
            if c.check_type == VerificationCheck.SCHEMA_TABLES
        )
        assert len(table_check.violations_found) > 0

    async def test_metric_endpoint_detected(
        self,
        verification_service: AntiMetricsVerificationService,
        router_with_metric_endpoint: Router,
    ):
        """Metric endpoint is detected."""
        report = await verification_service.verify_all()

        assert report.overall_status == VerificationStatus.FAIL
        endpoint_check = next(
            c for c in report.checks
            if c.check_type == VerificationCheck.API_ENDPOINTS
        )
        assert len(endpoint_check.violations_found) > 0

    async def test_verification_event_emitted(
        self,
        verification_service: AntiMetricsVerificationService,
        verifier: Verifier,
        event_capture: EventCapture,
    ):
        """Verification event is emitted."""
        await verification_service.verify_all(
            verifier_id=verifier.id,
        )

        event = event_capture.get_last("audit.anti_metrics.verified")
        assert event is not None


class TestIndependentVerification:
    """Tests for independent verification capability."""

    async def test_works_without_event_emitter(
        self,
        verification_service_no_emitter: AntiMetricsVerificationService,
    ):
        """Verification works independently (no event emitter)."""
        report = await verification_service_no_emitter.verify_all()

        assert report is not None
        assert report.overall_status in [VerificationStatus.PASS, VerificationStatus.FAIL]

    async def test_report_is_human_readable(
        self,
        verification_service: AntiMetricsVerificationService,
    ):
        """Report text is human readable."""
        report = await verification_service.verify_all()
        text = verification_service.generate_report_text(report)

        assert "ANTI-METRICS VERIFICATION REPORT" in text
        assert "CHECKS PERFORMED" in text
        assert "SUMMARY" in text


class TestPeriodicVerification:
    """Tests for periodic verification job."""

    async def test_job_runs_on_schedule(
        self,
        verification_job: VerificationJob,
        scheduler: FakeScheduler,
    ):
        """Verification job runs on schedule."""
        # Advance time
        await scheduler.advance(days=1)

        # Should have run
        assert verification_job.run_count >= 1

    async def test_job_logs_results(
        self,
        verification_job: VerificationJob,
        log_capture: LogCapture,
    ):
        """Verification job logs results."""
        await verification_job.run()

        assert any("anti_metrics" in log.lower() for log in log_capture.logs)


class TestViolationDetection:
    """Tests for violation detection."""

    @pytest.mark.parametrize("table_name", [
        "cluster_metrics",
        "user_performance",
        "engagement_tracking",
    ])
    async def test_prohibited_table_detected(
        self,
        verification_service: AntiMetricsVerificationService,
        schema_with_table,
        table_name: str,
    ):
        """Prohibited tables are detected."""
        schema_with_table.add_table(table_name)

        report = await verification_service.verify_all()

        assert report.overall_status == VerificationStatus.FAIL
        assert any(table_name in v for check in report.checks for v in check.violations_found)

    @pytest.mark.parametrize("endpoint", [
        "/metrics/participant/123",
        "/analytics/engagement",
        "/tracking/sessions",
    ])
    async def test_prohibited_endpoint_detected(
        self,
        verification_service: AntiMetricsVerificationService,
        router_with_endpoint,
        endpoint: str,
    ):
        """Prohibited endpoints are detected."""
        router_with_endpoint.add_route(endpoint)

        report = await verification_service.verify_all()

        assert report.overall_status == VerificationStatus.FAIL
```

### Dependencies

- **Depends on:** consent-gov-10-1 (anti-metrics enforcement)
- **Enables:** Independent audit of anti-surveillance guarantee

### References

- NFR-CONST-08: Anti-metrics are enforced at data layer; collection endpoints do not exist

---

## File List

### Domain Layer
- `src/domain/governance/antimetrics/verification.py` - Domain models (CheckResult, VerificationReport, VerificationCheck, VerificationStatus)

### Application Layer
- `src/application/ports/governance/anti_metrics_verification_port.py` - Port protocol for verification
- `src/application/services/governance/anti_metrics_verification_service.py` - Verification service implementation
- `src/application/services/governance/periodic_verification_job.py` - Periodic job scheduler

### Infrastructure Layer
- `src/infrastructure/adapters/governance/verification_cli.py` - CLI for independent verification

### Tests
- `tests/unit/domain/governance/antimetrics/test_verification.py` - Domain model tests
- `tests/unit/application/services/governance/test_anti_metrics_verification_service.py` - Service tests
- `tests/unit/application/services/governance/test_periodic_verification_job.py` - Periodic job tests
- `tests/unit/infrastructure/adapters/governance/test_verification_cli.py` - CLI tests
