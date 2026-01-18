"""Anti-Metrics Verification Service.

Story: consent-gov-10.2: Anti-Metrics Verification

This service verifies anti-metrics constraints are enforced.
Can be run independently by auditors.

Purpose:
    Trust but verify:
    - Anti-metrics guard should prevent violations
    - Verification confirms prevention worked
    - Auditors can independently check
    - Defense in depth

Verification Answers:
    - Are there any metric tables? (Should be: No)
    - Are there any metric endpoints? (Should be: No)
    - Have any violations been recorded?
    - Is the system surveillance-free?

Constitutional Guarantees:
- FR61: No participant-level performance metrics
- FR62: No completion rates per participant
- FR63: No engagement or retention tracking
- NFR-CONST-08: Anti-metrics enforced at data layer
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from src.application.ports.governance.anti_metrics_verification_port import (
    RouteInfo,
    RouteInspectorPort,
    SchemaInspectorPort,
    VerificationEventEmitterPort,
)
from src.application.ports.time_authority import TimeAuthorityProtocol
from src.domain.governance.antimetrics import (
    PROHIBITED_COLUMN_PATTERNS,
    PROHIBITED_TABLE_PATTERNS,
)
from src.domain.governance.antimetrics.verification import (
    CheckResult,
    VerificationCheck,
    VerificationReport,
    VerificationStatus,
)

if TYPE_CHECKING:
    pass


# Additional prohibited endpoint patterns
# These detect metric-related API routes that should not exist
PROHIBITED_ENDPOINT_PATTERNS: list[str] = [
    r"^/v\d+/metrics/participant",  # Participant metrics
    r"^/v\d+/metrics/engagement",  # Engagement metrics
    r"^/v\d+/metrics/retention",  # Retention metrics
    r"^/v\d+/metrics/performance",  # Performance metrics (individual)
    r"^/v\d+/analytics/",  # Analytics routes
    r"^/v\d+/tracking/",  # Tracking routes
    r"^/v\d+/performance/participant",  # Performance per participant
    r"/engagement$",  # Engagement endpoints
    r"/retention$",  # Retention endpoints
    r"/participant[_-]metrics",  # Participant metrics variants
    r"/user[_-]activity",  # User activity tracking
    r"/session[_-]tracking",  # Session tracking
]

# Allowed operational endpoints (not participant metrics)
# These are explicitly allowed and should NOT be flagged
ALLOWED_OPERATIONAL_PATTERNS: list[str] = [
    r"^/v\d+/metrics$",  # Prometheus metrics endpoint (operational)
    r"^/metrics$",  # Root metrics endpoint (operational)
    r"/health",  # Health checks
    r"/readiness",  # Readiness probes
    r"/liveness",  # Liveness probes
]


class AntiMetricsVerificationService:
    """Service for verifying anti-metrics constraints.

    Can be run independently by auditors.

    Usage (Online - with events):
        service = AntiMetricsVerificationService(
            schema_inspector=schema_inspector,
            route_inspector=route_inspector,
            event_emitter=event_emitter,
            time_authority=time_authority,
        )
        report = await service.verify_all(verifier_id=verifier.id)

    Usage (Independent - no events):
        service = AntiMetricsVerificationService(
            schema_inspector=schema_inspector,
            route_inspector=route_inspector,
            event_emitter=None,  # No event emission
            time_authority=time_authority,
        )
        report = await service.verify_all()

    Constitutional Reference:
        NFR-CONST-08: Anti-metrics are enforced at data layer;
        collection endpoints do not exist.
    """

    def __init__(
        self,
        schema_inspector: SchemaInspectorPort,
        route_inspector: RouteInspectorPort,
        event_emitter: VerificationEventEmitterPort | None,
        time_authority: TimeAuthorityProtocol,
    ) -> None:
        """Initialize the verification service.

        Args:
            schema_inspector: Port for inspecting database schema
            route_inspector: Port for inspecting API routes
            event_emitter: Optional port for emitting events (None for independent)
            time_authority: Authority for timestamps (not datetime.now())
        """
        self._schema = schema_inspector
        self._routes = route_inspector
        self._event_emitter = event_emitter
        self._time = time_authority

    async def verify_all(
        self,
        verifier_id: UUID | None = None,
    ) -> VerificationReport:
        """Run complete anti-metrics verification.

        Checks:
        1. Schema tables for prohibited patterns
        2. Schema columns for prohibited patterns
        3. API endpoints for prohibited routes

        Args:
            verifier_id: Optional ID of verifier (for audit trail)

        Returns:
            VerificationReport with all check results
        """
        start = self._time.utcnow()
        checks: list[CheckResult] = []

        # Check schema tables
        table_result = await self._verify_tables()
        checks.append(table_result)

        # Check schema columns
        column_result = await self._verify_columns()
        checks.append(column_result)

        # Check API endpoints
        endpoint_result = await self._verify_endpoints()
        checks.append(endpoint_result)

        end = self._time.utcnow()
        duration_ms = int((end - start).total_seconds() * 1000)

        # Calculate overall status
        total_violations = sum(len(c.violations_found) for c in checks)
        overall = (
            VerificationStatus.PASS
            if total_violations == 0
            else VerificationStatus.FAIL
        )

        report = VerificationReport(
            report_id=uuid4(),
            verified_at=start,
            overall_status=overall,
            checks=tuple(checks),
            total_violations=total_violations,
            verification_duration_ms=duration_ms,
            verifier_id=verifier_id,
        )

        # Emit event if online
        if self._event_emitter and verifier_id:
            await self._event_emitter.emit_verified(report)

        return report

    async def verify_tables(self) -> list[str]:
        """Verify no prohibited metric tables exist.

        Returns:
            List of violations (empty if clean)
        """
        result = await self._verify_tables()
        return list(result.violations_found)

    async def verify_columns(self) -> list[str]:
        """Verify no prohibited metric columns exist.

        Returns:
            List of violations (empty if clean)
        """
        result = await self._verify_columns()
        return list(result.violations_found)

    async def verify_endpoints(self) -> list[str]:
        """Verify no prohibited metric endpoints exist.

        Returns:
            List of violations (empty if clean)
        """
        result = await self._verify_endpoints()
        return list(result.violations_found)

    async def _verify_tables(self) -> CheckResult:
        """Verify no metric tables exist.

        Returns:
            CheckResult with table verification details
        """
        tables = await self._schema.get_all_tables()
        violations: list[str] = []

        for table in tables:
            for pattern in PROHIBITED_TABLE_PATTERNS:
                if re.match(pattern, table, re.IGNORECASE):
                    violations.append(f"Prohibited table: {table}")
                    break  # Only report once per table

        return CheckResult(
            check_type=VerificationCheck.SCHEMA_TABLES,
            status=(
                VerificationStatus.PASS if not violations else VerificationStatus.FAIL
            ),
            items_checked=len(tables),
            violations_found=tuple(violations),
        )

    async def _verify_columns(self) -> CheckResult:
        """Verify no metric columns exist.

        Returns:
            CheckResult with column verification details
        """
        columns = await self._schema.get_all_columns()
        violations: list[str] = []

        for table, column in columns:
            for pattern in PROHIBITED_COLUMN_PATTERNS:
                if re.match(pattern, column, re.IGNORECASE):
                    violations.append(f"Prohibited column: {table}.{column}")
                    break  # Only report once per column

        return CheckResult(
            check_type=VerificationCheck.SCHEMA_COLUMNS,
            status=(
                VerificationStatus.PASS if not violations else VerificationStatus.FAIL
            ),
            items_checked=len(columns),
            violations_found=tuple(violations),
        )

    async def _verify_endpoints(self) -> CheckResult:
        """Verify no metric endpoints exist.

        Checks all API routes for prohibited patterns while
        allowing legitimate operational endpoints.

        Returns:
            CheckResult with endpoint verification details
        """
        routes = await self._routes.get_all_routes()
        violations: list[str] = []

        for route in routes:
            # Skip if it's an allowed operational endpoint
            if self._is_allowed_operational(route):
                continue

            # Check against prohibited patterns
            for pattern in PROHIBITED_ENDPOINT_PATTERNS:
                if re.match(pattern, route.path, re.IGNORECASE):
                    violations.append(
                        f"Prohibited endpoint: {route.method} {route.path}"
                    )
                    break  # Only report once per route

        return CheckResult(
            check_type=VerificationCheck.API_ENDPOINTS,
            status=(
                VerificationStatus.PASS if not violations else VerificationStatus.FAIL
            ),
            items_checked=len(routes),
            violations_found=tuple(violations),
        )

    def _is_allowed_operational(self, route: RouteInfo) -> bool:
        """Check if route is an allowed operational endpoint.

        Operational endpoints (Prometheus, health checks) are
        explicitly allowed and should not be flagged.

        Args:
            route: The route to check

        Returns:
            True if route is allowed, False otherwise
        """
        for pattern in ALLOWED_OPERATIONAL_PATTERNS:
            if re.match(pattern, route.path, re.IGNORECASE):
                return True
        return False

    def generate_report_text(self, report: VerificationReport) -> str:
        """Generate human-readable report text.

        Args:
            report: The verification report to format

        Returns:
            Human-readable text report with:
            - Header with report metadata
            - Check results with pass/fail status
            - Summary with total violations
            - Remediation recommendations if violations found
        """
        lines = [
            "=" * 60,
            "ANTI-METRICS VERIFICATION REPORT",
            "=" * 60,
            f"Report ID: {report.report_id}",
            f"Verified At: {report.verified_at.isoformat()}",
            f"Duration: {report.verification_duration_ms}ms",
            f"Overall Status: {report.overall_status.value.upper()}",
        ]

        if report.verifier_id:
            lines.append(f"Verifier ID: {report.verifier_id}")

        lines.extend(
            [
                "",
                "-" * 60,
                "CHECKS PERFORMED",
                "-" * 60,
            ]
        )

        for check in report.checks:
            status_mark = "PASS" if check.status == VerificationStatus.PASS else "FAIL"
            lines.append(f"[{status_mark}] {check.check_type.value}")
            lines.append(f"      Items checked: {check.items_checked}")
            if check.violations_found:
                lines.append(f"      Violations: {len(check.violations_found)}")
                for violation in check.violations_found:
                    lines.append(f"        - {violation}")

        lines.extend(
            [
                "",
                "-" * 60,
                "SUMMARY",
                "-" * 60,
                f"Total violations: {report.total_violations}",
            ]
        )

        if report.total_violations > 0:
            lines.extend(
                [
                    "",
                    "REMEDIATION REQUIRED:",
                    "  1. Remove prohibited tables/columns from database",
                    "  2. Remove prohibited API endpoints from router",
                    "  3. Re-run verification to confirm compliance",
                    "  4. Consider how this violation occurred",
                ]
            )
        else:
            lines.append("System is confirmed surveillance-free.")

        lines.append("=" * 60)

        return "\n".join(lines)
