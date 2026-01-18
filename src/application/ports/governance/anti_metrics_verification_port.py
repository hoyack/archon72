"""Anti-Metrics Verification Port - Interface for verification operations.

Story: consent-gov-10.2: Anti-Metrics Verification

This port defines the contract for anti-metrics verification.
Implementations MUST:
1. Query all table names for prohibited patterns
2. Query all column names for prohibited patterns
3. Enumerate all API routes for prohibited endpoints
4. Generate human-readable reports
5. Support independent (offline) verification

Constitutional Guarantees:
- FR61: No participant-level performance metrics
- FR62: No completion rates per participant
- FR63: No engagement or retention tracking
- NFR-CONST-08: Anti-metrics enforced at data layer
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, runtime_checkable
from uuid import UUID

if TYPE_CHECKING:
    from src.domain.governance.antimetrics.verification import (
        VerificationReport,
    )


@dataclass(frozen=True)
class RouteInfo:
    """Information about an API route.

    Attributes:
        method: HTTP method (GET, POST, etc.)
        path: URL path pattern
        name: Route name/identifier
    """

    method: str
    path: str
    name: str | None = None


@runtime_checkable
class SchemaInspectorPort(Protocol):
    """Port for inspecting database schema.

    Used by verification service to enumerate tables and columns
    for anti-metrics pattern checking.
    """

    async def get_all_tables(self) -> list[str]:
        """Get all table names in the database.

        Returns:
            List of table names (public schema).
        """
        ...

    async def get_all_columns(self) -> list[tuple[str, str]]:
        """Get all columns in the database.

        Returns:
            List of (table_name, column_name) tuples.
        """
        ...


@runtime_checkable
class RouteInspectorPort(Protocol):
    """Port for inspecting API routes.

    Used by verification service to enumerate routes
    for anti-metrics endpoint checking.
    """

    async def get_all_routes(self) -> list[RouteInfo]:
        """Get all registered API routes.

        Returns:
            List of RouteInfo objects.
        """
        ...


@runtime_checkable
class VerificationEventEmitterPort(Protocol):
    """Port for emitting verification events.

    Optional - used when verification runs online (not independent).
    """

    async def emit_verified(
        self,
        report: VerificationReport,
    ) -> None:
        """Emit audit.anti_metrics.verified event.

        Args:
            report: The verification report to emit
        """
        ...


@runtime_checkable
class AntiMetricsVerificationPort(Protocol):
    """Port for anti-metrics verification operations.

    This port defines the contract for verifying anti-metrics constraints.
    Implementations support both online (integrated) and independent
    (auditor-runnable) verification modes.

    Purpose:
        Trust but verify:
        - Anti-metrics guard should prevent violations
        - Verification confirms prevention worked
        - Auditors can independently check
        - Defense in depth
    """

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
        ...

    async def verify_tables(self) -> list[str]:
        """Verify no prohibited metric tables exist.

        Returns:
            List of violations (empty if clean)
        """
        ...

    async def verify_columns(self) -> list[str]:
        """Verify no prohibited metric columns exist.

        Returns:
            List of violations (empty if clean)
        """
        ...

    async def verify_endpoints(self) -> list[str]:
        """Verify no prohibited metric endpoints exist.

        Returns:
            List of violations (empty if clean)
        """
        ...

    def generate_report_text(self, report: VerificationReport) -> str:
        """Generate human-readable report text.

        Args:
            report: The verification report to format

        Returns:
            Human-readable text report
        """
        ...
