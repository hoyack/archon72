"""Tests for AntiMetricsVerificationService.

Story: consent-gov-10.2: Anti-Metrics Verification

These tests verify that:
1. Service verifies no metric tables exist (AC: 1)
2. Service verifies no metric endpoints exist (AC: 2)
3. Service detects violations (AC: 5)
4. Service can run independently (AC: 6)
5. Service generates clear reports (AC: 7)
6. Service has comprehensive tests (AC: 8)
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.application.ports.governance.anti_metrics_verification_port import (
    RouteInfo,
    RouteInspectorPort,
    SchemaInspectorPort,
    VerificationEventEmitterPort,
)
from src.domain.ports.time_authority import TimeAuthorityProtocol
from src.application.services.governance.anti_metrics_verification_service import (
    AntiMetricsVerificationService,
)
from src.domain.governance.antimetrics.verification import (
    CheckResult,
    VerificationCheck,
    VerificationReport,
    VerificationStatus,
)


class FakeTimeAuthority(TimeAuthorityProtocol):
    """Fake time authority for testing."""

    def __init__(self, fixed_time: datetime | None = None) -> None:
        self._fixed_time = fixed_time or datetime.now(timezone.utc)
        self._monotonic_value = 0.0
        self._advance_on_call = 0.0

    def now(self) -> datetime:
        return self._fixed_time

    def utcnow(self) -> datetime:
        result = self._fixed_time
        if self._advance_on_call > 0:
            from datetime import timedelta

            self._fixed_time = self._fixed_time + timedelta(
                milliseconds=self._advance_on_call
            )
        return result

    def monotonic(self) -> float:
        return self._monotonic_value

    def set_advance_on_call(self, milliseconds: float) -> None:
        """Advance time by this amount on each call (for duration testing)."""
        self._advance_on_call = milliseconds


class FakeSchemaInspector(SchemaInspectorPort):
    """Fake schema inspector for testing."""

    def __init__(
        self,
        tables: list[str] | None = None,
        columns: list[tuple[str, str]] | None = None,
    ) -> None:
        self._tables = tables or []
        self._columns = columns or []

    async def get_all_tables(self) -> list[str]:
        return self._tables

    async def get_all_columns(self) -> list[tuple[str, str]]:
        return self._columns


class FakeRouteInspector(RouteInspectorPort):
    """Fake route inspector for testing."""

    def __init__(self, routes: list[RouteInfo] | None = None) -> None:
        self._routes = routes or []

    async def get_all_routes(self) -> list[RouteInfo]:
        return self._routes


class FakeVerificationEventEmitter(VerificationEventEmitterPort):
    """Fake event emitter for testing."""

    def __init__(self) -> None:
        self.emitted_reports: list[VerificationReport] = []

    async def emit_verified(self, report: VerificationReport) -> None:
        self.emitted_reports.append(report)


@pytest.fixture
def time_authority() -> FakeTimeAuthority:
    """Provide fake time authority."""
    return FakeTimeAuthority()


@pytest.fixture
def clean_schema_inspector() -> FakeSchemaInspector:
    """Provide schema inspector that reports no violations."""
    return FakeSchemaInspector(
        tables=["tasks", "clusters", "participants", "events"],
        columns=[
            ("tasks", "id"),
            ("tasks", "created_at"),
            ("tasks", "status"),
            ("clusters", "id"),
            ("clusters", "name"),
        ],
    )


@pytest.fixture
def clean_route_inspector() -> FakeRouteInspector:
    """Provide route inspector with only allowed endpoints."""
    return FakeRouteInspector(
        routes=[
            RouteInfo(method="GET", path="/v1/health", name="health_check"),
            RouteInfo(method="GET", path="/v1/metrics", name="prometheus_metrics"),
            RouteInfo(method="GET", path="/v1/tasks", name="list_tasks"),
            RouteInfo(method="POST", path="/v1/tasks", name="create_task"),
        ]
    )


@pytest.fixture
def event_emitter() -> FakeVerificationEventEmitter:
    """Provide fake event emitter."""
    return FakeVerificationEventEmitter()


@pytest.fixture
def verification_service(
    clean_schema_inspector: FakeSchemaInspector,
    clean_route_inspector: FakeRouteInspector,
    event_emitter: FakeVerificationEventEmitter,
    time_authority: FakeTimeAuthority,
) -> AntiMetricsVerificationService:
    """Provide verification service with clean infrastructure."""
    return AntiMetricsVerificationService(
        schema_inspector=clean_schema_inspector,
        route_inspector=clean_route_inspector,
        event_emitter=event_emitter,
        time_authority=time_authority,
    )


@pytest.fixture
def verification_service_no_emitter(
    clean_schema_inspector: FakeSchemaInspector,
    clean_route_inspector: FakeRouteInspector,
    time_authority: FakeTimeAuthority,
) -> AntiMetricsVerificationService:
    """Provide verification service without event emitter (independent mode)."""
    return AntiMetricsVerificationService(
        schema_inspector=clean_schema_inspector,
        route_inspector=clean_route_inspector,
        event_emitter=None,  # Independent mode
        time_authority=time_authority,
    )


class TestVerifyAll:
    """Tests for verify_all method."""

    @pytest.mark.asyncio
    async def test_clean_system_passes(
        self,
        verification_service: AntiMetricsVerificationService,
    ) -> None:
        """Clean system passes verification (AC: 1, 2)."""
        report = await verification_service.verify_all()

        assert report.overall_status == VerificationStatus.PASS
        assert report.total_violations == 0

    @pytest.mark.asyncio
    async def test_report_contains_all_checks(
        self,
        verification_service: AntiMetricsVerificationService,
    ) -> None:
        """Report includes all verification checks."""
        report = await verification_service.verify_all()

        check_types = {c.check_type for c in report.checks}
        assert VerificationCheck.SCHEMA_TABLES in check_types
        assert VerificationCheck.SCHEMA_COLUMNS in check_types
        assert VerificationCheck.API_ENDPOINTS in check_types

    @pytest.mark.asyncio
    async def test_report_has_valid_metadata(
        self,
        verification_service: AntiMetricsVerificationService,
    ) -> None:
        """Report has valid metadata."""
        verifier_id = uuid4()
        report = await verification_service.verify_all(verifier_id=verifier_id)

        assert report.report_id is not None
        assert report.verified_at is not None
        assert report.verification_duration_ms >= 0
        assert report.verifier_id == verifier_id


class TestTableVerification:
    """Tests for table verification (AC: 1)."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "table_name",
        [
            "cluster_metrics",
            "task_metrics",
            "user_metrics",
            "participant_performance",
            "user_engagement",
            "task_retention",
            "cluster_analytics",
        ],
    )
    async def test_prohibited_table_detected(
        self,
        clean_route_inspector: FakeRouteInspector,
        event_emitter: FakeVerificationEventEmitter,
        time_authority: FakeTimeAuthority,
        table_name: str,
    ) -> None:
        """Prohibited tables are detected (AC: 1, 5)."""
        dirty_schema = FakeSchemaInspector(tables=["tasks", table_name, "clusters"])
        service = AntiMetricsVerificationService(
            schema_inspector=dirty_schema,
            route_inspector=clean_route_inspector,
            event_emitter=event_emitter,
            time_authority=time_authority,
        )

        report = await service.verify_all()

        assert report.overall_status == VerificationStatus.FAIL
        table_check = report.get_check_result(VerificationCheck.SCHEMA_TABLES)
        assert table_check is not None
        assert table_check.status == VerificationStatus.FAIL
        assert len(table_check.violations_found) > 0
        assert any(table_name in v for v in table_check.violations_found)

    @pytest.mark.asyncio
    async def test_verify_tables_returns_violations(
        self,
        clean_route_inspector: FakeRouteInspector,
        event_emitter: FakeVerificationEventEmitter,
        time_authority: FakeTimeAuthority,
    ) -> None:
        """verify_tables returns list of violations."""
        dirty_schema = FakeSchemaInspector(
            tables=["tasks", "cluster_metrics", "user_engagement"]
        )
        service = AntiMetricsVerificationService(
            schema_inspector=dirty_schema,
            route_inspector=clean_route_inspector,
            event_emitter=event_emitter,
            time_authority=time_authority,
        )

        violations = await service.verify_tables()

        assert len(violations) == 2
        assert any("cluster_metrics" in v for v in violations)
        assert any("user_engagement" in v for v in violations)

    @pytest.mark.asyncio
    async def test_multiple_prohibited_tables_all_detected(
        self,
        clean_route_inspector: FakeRouteInspector,
        event_emitter: FakeVerificationEventEmitter,
        time_authority: FakeTimeAuthority,
    ) -> None:
        """All prohibited tables are detected when multiple exist."""
        dirty_schema = FakeSchemaInspector(
            tables=[
                "tasks",
                "cluster_metrics",
                "task_performance",
                "user_engagement",
            ]
        )
        service = AntiMetricsVerificationService(
            schema_inspector=dirty_schema,
            route_inspector=clean_route_inspector,
            event_emitter=event_emitter,
            time_authority=time_authority,
        )

        report = await service.verify_all()

        table_check = report.get_check_result(VerificationCheck.SCHEMA_TABLES)
        assert len(table_check.violations_found) == 3


class TestColumnVerification:
    """Tests for column verification (AC: 1)."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "column_name",
        [
            "completion_rate",
            "success_rate",
            "failure_rate",
            "performance_score",
            "engagement_score",
            "retention_score",
            "session_count",
            "login_count",
        ],
    )
    async def test_prohibited_column_detected(
        self,
        clean_route_inspector: FakeRouteInspector,
        event_emitter: FakeVerificationEventEmitter,
        time_authority: FakeTimeAuthority,
        column_name: str,
    ) -> None:
        """Prohibited columns are detected (AC: 1, 5)."""
        dirty_schema = FakeSchemaInspector(
            tables=["tasks"],
            columns=[
                ("tasks", "id"),
                ("tasks", column_name),
            ],
        )
        service = AntiMetricsVerificationService(
            schema_inspector=dirty_schema,
            route_inspector=clean_route_inspector,
            event_emitter=event_emitter,
            time_authority=time_authority,
        )

        report = await service.verify_all()

        assert report.overall_status == VerificationStatus.FAIL
        column_check = report.get_check_result(VerificationCheck.SCHEMA_COLUMNS)
        assert column_check is not None
        assert column_check.status == VerificationStatus.FAIL
        assert any(column_name in v for v in column_check.violations_found)

    @pytest.mark.asyncio
    async def test_verify_columns_returns_violations(
        self,
        clean_route_inspector: FakeRouteInspector,
        event_emitter: FakeVerificationEventEmitter,
        time_authority: FakeTimeAuthority,
    ) -> None:
        """verify_columns returns list of violations."""
        dirty_schema = FakeSchemaInspector(
            tables=["tasks"],
            columns=[
                ("tasks", "id"),
                ("tasks", "completion_rate"),
                ("tasks", "engagement_score"),
            ],
        )
        service = AntiMetricsVerificationService(
            schema_inspector=dirty_schema,
            route_inspector=clean_route_inspector,
            event_emitter=event_emitter,
            time_authority=time_authority,
        )

        violations = await service.verify_columns()

        assert len(violations) == 2


class TestEndpointVerification:
    """Tests for endpoint verification (AC: 2)."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "endpoint",
        [
            "/v1/metrics/participant/123",
            "/v1/metrics/engagement",
            "/v1/metrics/retention",
            "/v1/analytics/dashboard",
            "/v1/tracking/sessions",
            "/v1/performance/participant/456",
        ],
    )
    async def test_prohibited_endpoint_detected(
        self,
        clean_schema_inspector: FakeSchemaInspector,
        event_emitter: FakeVerificationEventEmitter,
        time_authority: FakeTimeAuthority,
        endpoint: str,
    ) -> None:
        """Prohibited endpoints are detected (AC: 2, 5)."""
        dirty_routes = FakeRouteInspector(
            routes=[
                RouteInfo(method="GET", path="/v1/health"),
                RouteInfo(method="GET", path=endpoint),
            ]
        )
        service = AntiMetricsVerificationService(
            schema_inspector=clean_schema_inspector,
            route_inspector=dirty_routes,
            event_emitter=event_emitter,
            time_authority=time_authority,
        )

        report = await service.verify_all()

        assert report.overall_status == VerificationStatus.FAIL
        endpoint_check = report.get_check_result(VerificationCheck.API_ENDPOINTS)
        assert endpoint_check is not None
        assert endpoint_check.status == VerificationStatus.FAIL
        assert any(endpoint in v for v in endpoint_check.violations_found)

    @pytest.mark.asyncio
    async def test_operational_metrics_endpoint_allowed(
        self,
        clean_schema_inspector: FakeSchemaInspector,
        event_emitter: FakeVerificationEventEmitter,
        time_authority: FakeTimeAuthority,
    ) -> None:
        """Operational /metrics endpoint is allowed (Prometheus)."""
        clean_routes = FakeRouteInspector(
            routes=[
                RouteInfo(method="GET", path="/v1/metrics"),
                RouteInfo(method="GET", path="/metrics"),
            ]
        )
        service = AntiMetricsVerificationService(
            schema_inspector=clean_schema_inspector,
            route_inspector=clean_routes,
            event_emitter=event_emitter,
            time_authority=time_authority,
        )

        report = await service.verify_all()

        endpoint_check = report.get_check_result(VerificationCheck.API_ENDPOINTS)
        assert endpoint_check.status == VerificationStatus.PASS
        assert len(endpoint_check.violations_found) == 0

    @pytest.mark.asyncio
    async def test_health_endpoints_allowed(
        self,
        clean_schema_inspector: FakeSchemaInspector,
        event_emitter: FakeVerificationEventEmitter,
        time_authority: FakeTimeAuthority,
    ) -> None:
        """Health check endpoints are allowed."""
        clean_routes = FakeRouteInspector(
            routes=[
                RouteInfo(method="GET", path="/health"),
                RouteInfo(method="GET", path="/v1/health"),
                RouteInfo(method="GET", path="/readiness"),
                RouteInfo(method="GET", path="/liveness"),
            ]
        )
        service = AntiMetricsVerificationService(
            schema_inspector=clean_schema_inspector,
            route_inspector=clean_routes,
            event_emitter=event_emitter,
            time_authority=time_authority,
        )

        report = await service.verify_all()

        endpoint_check = report.get_check_result(VerificationCheck.API_ENDPOINTS)
        assert endpoint_check.status == VerificationStatus.PASS

    @pytest.mark.asyncio
    async def test_verify_endpoints_returns_violations(
        self,
        clean_schema_inspector: FakeSchemaInspector,
        event_emitter: FakeVerificationEventEmitter,
        time_authority: FakeTimeAuthority,
    ) -> None:
        """verify_endpoints returns list of violations."""
        dirty_routes = FakeRouteInspector(
            routes=[
                RouteInfo(method="GET", path="/v1/metrics/participant/123"),
                RouteInfo(method="GET", path="/v1/analytics/dashboard"),
            ]
        )
        service = AntiMetricsVerificationService(
            schema_inspector=clean_schema_inspector,
            route_inspector=dirty_routes,
            event_emitter=event_emitter,
            time_authority=time_authority,
        )

        violations = await service.verify_endpoints()

        assert len(violations) == 2


class TestIndependentVerification:
    """Tests for independent verification capability (AC: 6)."""

    @pytest.mark.asyncio
    async def test_works_without_event_emitter(
        self,
        verification_service_no_emitter: AntiMetricsVerificationService,
    ) -> None:
        """Verification works independently without event emitter (AC: 6)."""
        report = await verification_service_no_emitter.verify_all()

        assert report is not None
        assert report.overall_status in [
            VerificationStatus.PASS,
            VerificationStatus.FAIL,
        ]

    @pytest.mark.asyncio
    async def test_verifier_id_optional(
        self,
        verification_service_no_emitter: AntiMetricsVerificationService,
    ) -> None:
        """Verifier ID is optional for independent verification."""
        report = await verification_service_no_emitter.verify_all(verifier_id=None)

        assert report is not None
        assert report.verifier_id is None

    @pytest.mark.asyncio
    async def test_independent_mode_no_event_emission(
        self,
        clean_schema_inspector: FakeSchemaInspector,
        clean_route_inspector: FakeRouteInspector,
        time_authority: FakeTimeAuthority,
    ) -> None:
        """Independent mode does not try to emit events."""
        service = AntiMetricsVerificationService(
            schema_inspector=clean_schema_inspector,
            route_inspector=clean_route_inspector,
            event_emitter=None,
            time_authority=time_authority,
        )

        # Should not raise even with verifier_id
        verifier_id = uuid4()
        report = await service.verify_all(verifier_id=verifier_id)

        assert report is not None


class TestVerificationReport:
    """Tests for verification report generation (AC: 7)."""

    @pytest.mark.asyncio
    async def test_report_text_includes_header(
        self,
        verification_service: AntiMetricsVerificationService,
    ) -> None:
        """Report text includes header section (AC: 7)."""
        report = await verification_service.verify_all()
        text = verification_service.generate_report_text(report)

        assert "ANTI-METRICS VERIFICATION REPORT" in text
        assert "Report ID:" in text
        assert "Verified At:" in text
        assert "Duration:" in text

    @pytest.mark.asyncio
    async def test_report_text_includes_checks(
        self,
        verification_service: AntiMetricsVerificationService,
    ) -> None:
        """Report text includes check results (AC: 7)."""
        report = await verification_service.verify_all()
        text = verification_service.generate_report_text(report)

        assert "CHECKS PERFORMED" in text
        assert "schema_tables" in text
        assert "schema_columns" in text
        assert "api_endpoints" in text

    @pytest.mark.asyncio
    async def test_report_text_includes_summary(
        self,
        verification_service: AntiMetricsVerificationService,
    ) -> None:
        """Report text includes summary (AC: 7)."""
        report = await verification_service.verify_all()
        text = verification_service.generate_report_text(report)

        assert "SUMMARY" in text
        assert "Total violations:" in text

    @pytest.mark.asyncio
    async def test_clean_report_says_surveillance_free(
        self,
        verification_service: AntiMetricsVerificationService,
    ) -> None:
        """Clean report confirms system is surveillance-free."""
        report = await verification_service.verify_all()
        text = verification_service.generate_report_text(report)

        assert "surveillance-free" in text.lower()

    @pytest.mark.asyncio
    async def test_violation_report_includes_remediation(
        self,
        clean_route_inspector: FakeRouteInspector,
        event_emitter: FakeVerificationEventEmitter,
        time_authority: FakeTimeAuthority,
    ) -> None:
        """Violation report includes remediation steps."""
        dirty_schema = FakeSchemaInspector(tables=["cluster_metrics"])
        service = AntiMetricsVerificationService(
            schema_inspector=dirty_schema,
            route_inspector=clean_route_inspector,
            event_emitter=event_emitter,
            time_authority=time_authority,
        )

        report = await service.verify_all()
        text = service.generate_report_text(report)

        assert "REMEDIATION REQUIRED" in text
        assert "Remove prohibited" in text

    @pytest.mark.asyncio
    async def test_report_text_includes_verifier_id_when_present(
        self,
        verification_service: AntiMetricsVerificationService,
    ) -> None:
        """Report text includes verifier ID when present."""
        verifier_id = uuid4()
        report = await verification_service.verify_all(verifier_id=verifier_id)
        text = verification_service.generate_report_text(report)

        assert "Verifier ID:" in text
        assert str(verifier_id) in text


class TestEventEmission:
    """Tests for verification event emission (AC: 4)."""

    @pytest.mark.asyncio
    async def test_event_emitted_with_verifier_id(
        self,
        verification_service: AntiMetricsVerificationService,
        event_emitter: FakeVerificationEventEmitter,
    ) -> None:
        """Event is emitted when verifier_id provided (AC: 4)."""
        verifier_id = uuid4()
        await verification_service.verify_all(verifier_id=verifier_id)

        assert len(event_emitter.emitted_reports) == 1
        emitted_report = event_emitter.emitted_reports[0]
        assert emitted_report.verifier_id == verifier_id

    @pytest.mark.asyncio
    async def test_no_event_without_verifier_id(
        self,
        verification_service: AntiMetricsVerificationService,
        event_emitter: FakeVerificationEventEmitter,
    ) -> None:
        """No event is emitted without verifier_id."""
        await verification_service.verify_all(verifier_id=None)

        assert len(event_emitter.emitted_reports) == 0


class TestViolationDetection:
    """Tests for violation detection (AC: 5)."""

    @pytest.mark.asyncio
    async def test_mixed_violations_all_detected(
        self,
        event_emitter: FakeVerificationEventEmitter,
        time_authority: FakeTimeAuthority,
    ) -> None:
        """Violations across all check types are detected."""
        dirty_schema = FakeSchemaInspector(
            tables=["cluster_metrics"],
            columns=[("tasks", "completion_rate")],
        )
        dirty_routes = FakeRouteInspector(
            routes=[RouteInfo(method="GET", path="/v1/analytics/dashboard")]
        )
        service = AntiMetricsVerificationService(
            schema_inspector=dirty_schema,
            route_inspector=dirty_routes,
            event_emitter=event_emitter,
            time_authority=time_authority,
        )

        report = await service.verify_all()

        assert report.overall_status == VerificationStatus.FAIL
        assert report.total_violations == 3

        # All check types should have failures
        for check in report.checks:
            assert check.status == VerificationStatus.FAIL

    @pytest.mark.asyncio
    async def test_partial_violations_detected(
        self,
        clean_route_inspector: FakeRouteInspector,
        event_emitter: FakeVerificationEventEmitter,
        time_authority: FakeTimeAuthority,
    ) -> None:
        """Partial violations (only tables) still result in FAIL."""
        dirty_schema = FakeSchemaInspector(
            tables=["cluster_metrics"],
            columns=[("tasks", "id")],  # Clean columns
        )
        service = AntiMetricsVerificationService(
            schema_inspector=dirty_schema,
            route_inspector=clean_route_inspector,
            event_emitter=event_emitter,
            time_authority=time_authority,
        )

        report = await service.verify_all()

        assert report.overall_status == VerificationStatus.FAIL
        assert report.total_violations == 1

        table_check = report.get_check_result(VerificationCheck.SCHEMA_TABLES)
        assert table_check.status == VerificationStatus.FAIL

        column_check = report.get_check_result(VerificationCheck.SCHEMA_COLUMNS)
        assert column_check.status == VerificationStatus.PASS


class TestDomainModels:
    """Tests for domain models."""

    def test_check_result_pass_requires_no_violations(self) -> None:
        """PASS status requires no violations."""
        result = CheckResult(
            check_type=VerificationCheck.SCHEMA_TABLES,
            status=VerificationStatus.PASS,
            items_checked=10,
            violations_found=(),
        )
        assert result.status == VerificationStatus.PASS

    def test_check_result_fail_requires_violations(self) -> None:
        """FAIL status requires violations."""
        result = CheckResult(
            check_type=VerificationCheck.SCHEMA_TABLES,
            status=VerificationStatus.FAIL,
            items_checked=10,
            violations_found=("violation1",),
        )
        assert result.status == VerificationStatus.FAIL

    def test_check_result_validates_status_consistency(self) -> None:
        """CheckResult validates status/violations consistency."""
        with pytest.raises(ValueError, match="Cannot have PASS status with violations"):
            CheckResult(
                check_type=VerificationCheck.SCHEMA_TABLES,
                status=VerificationStatus.PASS,
                items_checked=10,
                violations_found=("violation1",),
            )

        with pytest.raises(
            ValueError, match="Cannot have FAIL status without violations"
        ):
            CheckResult(
                check_type=VerificationCheck.SCHEMA_TABLES,
                status=VerificationStatus.FAIL,
                items_checked=10,
                violations_found=(),
            )

    def test_verification_report_validates_total_violations(self) -> None:
        """VerificationReport validates total_violations consistency."""
        with pytest.raises(ValueError, match="does not match sum"):
            VerificationReport(
                report_id=uuid4(),
                verified_at=datetime.now(timezone.utc),
                overall_status=VerificationStatus.FAIL,
                checks=(
                    CheckResult(
                        check_type=VerificationCheck.SCHEMA_TABLES,
                        status=VerificationStatus.FAIL,
                        items_checked=10,
                        violations_found=("v1", "v2"),
                    ),
                ),
                total_violations=5,  # Wrong!
                verification_duration_ms=100,
            )

    def test_verification_report_validates_overall_status(self) -> None:
        """VerificationReport validates overall_status consistency."""
        with pytest.raises(
            ValueError, match="Cannot have PASS overall status with failed"
        ):
            VerificationReport(
                report_id=uuid4(),
                verified_at=datetime.now(timezone.utc),
                overall_status=VerificationStatus.PASS,  # Wrong!
                checks=(
                    CheckResult(
                        check_type=VerificationCheck.SCHEMA_TABLES,
                        status=VerificationStatus.FAIL,
                        items_checked=10,
                        violations_found=("v1",),
                    ),
                ),
                total_violations=1,
                verification_duration_ms=100,
            )

    def test_verification_report_get_check_result(self) -> None:
        """VerificationReport.get_check_result works correctly."""
        report = VerificationReport(
            report_id=uuid4(),
            verified_at=datetime.now(timezone.utc),
            overall_status=VerificationStatus.PASS,
            checks=(
                CheckResult(
                    check_type=VerificationCheck.SCHEMA_TABLES,
                    status=VerificationStatus.PASS,
                    items_checked=10,
                    violations_found=(),
                ),
                CheckResult(
                    check_type=VerificationCheck.SCHEMA_COLUMNS,
                    status=VerificationStatus.PASS,
                    items_checked=20,
                    violations_found=(),
                ),
            ),
            total_violations=0,
            verification_duration_ms=100,
        )

        table_check = report.get_check_result(VerificationCheck.SCHEMA_TABLES)
        assert table_check is not None
        assert table_check.items_checked == 10

        column_check = report.get_check_result(VerificationCheck.SCHEMA_COLUMNS)
        assert column_check is not None
        assert column_check.items_checked == 20

        # Non-existent check
        endpoint_check = report.get_check_result(VerificationCheck.API_ENDPOINTS)
        assert endpoint_check is None

    def test_verification_report_has_violations(self) -> None:
        """VerificationReport.has_violations works correctly."""
        clean_report = VerificationReport(
            report_id=uuid4(),
            verified_at=datetime.now(timezone.utc),
            overall_status=VerificationStatus.PASS,
            checks=(
                CheckResult(
                    check_type=VerificationCheck.SCHEMA_TABLES,
                    status=VerificationStatus.PASS,
                    items_checked=10,
                    violations_found=(),
                ),
            ),
            total_violations=0,
            verification_duration_ms=100,
        )
        assert clean_report.has_violations() is False

        dirty_report = VerificationReport(
            report_id=uuid4(),
            verified_at=datetime.now(timezone.utc),
            overall_status=VerificationStatus.FAIL,
            checks=(
                CheckResult(
                    check_type=VerificationCheck.SCHEMA_TABLES,
                    status=VerificationStatus.FAIL,
                    items_checked=10,
                    violations_found=("v1",),
                ),
            ),
            total_violations=1,
            verification_duration_ms=100,
        )
        assert dirty_report.has_violations() is True
