"""Independent Anti-Metrics Verification CLI.

Story: consent-gov-10.2: Anti-Metrics Verification

This module provides a CLI for independent verification of anti-metrics
constraints. Auditors can run this tool without any system access.

Independence Requirements:
- Verification requires NO system cooperation
- All needed data comes from database directly
- Results are reproducible
- Third-party auditable

Usage:
    # From command line
    python -m src.infrastructure.adapters.governance.verification_cli postgres://...

    # With FastAPI app routes
    python -m src.infrastructure.adapters.governance.verification_cli --with-routes

Constitutional Guarantees:
- FR61: No participant-level performance metrics
- FR62: No completion rates per participant
- FR63: No engagement or retention tracking
- NFR-CONST-08: Anti-metrics enforced at data layer
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime, timezone

from src.application.ports.governance.anti_metrics_verification_port import (
    RouteInfo,
    RouteInspectorPort,
    SchemaInspectorPort,
)
from src.application.services.governance.anti_metrics_verification_service import (
    AntiMetricsVerificationService,
)
from src.domain.governance.antimetrics.verification import VerificationStatus
from src.domain.ports.time_authority import TimeAuthorityProtocol


class SystemTimeAuthority(TimeAuthorityProtocol):
    """Time authority that uses system time."""

    def now(self) -> datetime:
        return datetime.now(timezone.utc)

    def utcnow(self) -> datetime:
        return datetime.now(timezone.utc)

    def monotonic(self) -> float:
        import time

        return time.monotonic()


class PostgresSchemaInspector(SchemaInspectorPort):
    """Schema inspector that queries PostgreSQL directly.

    This inspector connects directly to the database and enumerates
    all tables and columns. It does NOT use any application services.
    """

    def __init__(self, database_url: str) -> None:
        """Initialize with database connection string.

        Args:
            database_url: PostgreSQL connection URL
        """
        self._database_url = database_url
        self._connection = None

    async def get_all_tables(self) -> list[str]:
        """Get all table names in the public schema.

        Returns:
            List of table names
        """
        try:
            import asyncpg
        except ImportError:
            raise ImportError(
                "asyncpg is required for database verification. "
                "Install with: pip install asyncpg"
            )

        query = """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """

        conn = await asyncpg.connect(self._database_url)
        try:
            rows = await conn.fetch(query)
            return [row["table_name"] for row in rows]
        finally:
            await conn.close()

    async def get_all_columns(self) -> list[tuple[str, str]]:
        """Get all columns in the public schema.

        Returns:
            List of (table_name, column_name) tuples
        """
        try:
            import asyncpg
        except ImportError:
            raise ImportError(
                "asyncpg is required for database verification. "
                "Install with: pip install asyncpg"
            )

        query = """
            SELECT table_name, column_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
            ORDER BY table_name, column_name
        """

        conn = await asyncpg.connect(self._database_url)
        try:
            rows = await conn.fetch(query)
            return [(row["table_name"], row["column_name"]) for row in rows]
        finally:
            await conn.close()


class StaticRouteInspector(RouteInspectorPort):
    """Route inspector that returns a static list of routes.

    For independent verification, routes are provided as a static list
    since we can't introspect the FastAPI application from outside.
    """

    def __init__(self, routes: list[RouteInfo] | None = None) -> None:
        """Initialize with optional route list.

        Args:
            routes: Static list of routes to check. If None, returns empty.
        """
        self._routes = routes or []

    async def get_all_routes(self) -> list[RouteInfo]:
        """Get all routes.

        Returns:
            Static list of routes provided at init
        """
        return self._routes.copy()


class FastAPIRouteInspector(RouteInspectorPort):
    """Route inspector that introspects FastAPI application.

    This inspector examines the FastAPI application's router
    to enumerate all registered routes.
    """

    def __init__(self, app) -> None:
        """Initialize with FastAPI application.

        Args:
            app: FastAPI application instance
        """
        self._app = app

    async def get_all_routes(self) -> list[RouteInfo]:
        """Get all routes from FastAPI application.

        Returns:
            List of RouteInfo for all routes
        """
        routes: list[RouteInfo] = []

        for route in self._app.routes:
            if hasattr(route, "path") and hasattr(route, "methods"):
                for method in route.methods:
                    routes.append(
                        RouteInfo(
                            method=method,
                            path=route.path,
                            name=getattr(route, "name", None),
                        )
                    )

        return routes


async def verify_anti_metrics_cli(
    database_url: str | None = None,
    routes: list[RouteInfo] | None = None,
    output_file: str | None = None,
    json_output: bool = False,
) -> int:
    """Run anti-metrics verification from CLI.

    Args:
        database_url: PostgreSQL connection URL. If None, skips schema check.
        routes: Optional list of routes to check. If None, skips endpoint check.
        output_file: Optional file to write report to
        json_output: If True, output JSON instead of text

    Returns:
        Exit code: 0 for pass, 1 for fail, 2 for error
    """
    # Print header (suppressed for JSON output)
    if not json_output:
        print("=" * 60)
        print("ANTI-METRICS VERIFICATION CLI")
        print("=" * 60)
        print()

    # Set up inspectors
    if database_url:
        schema_inspector: SchemaInspectorPort = PostgresSchemaInspector(database_url)
        if not json_output:
            print(f"Database: {database_url[:50]}...")
    else:
        # Empty schema for when no database is provided
        class EmptySchemaInspector(SchemaInspectorPort):
            async def get_all_tables(self) -> list[str]:
                return []

            async def get_all_columns(self) -> list[tuple[str, str]]:
                return []

        schema_inspector = EmptySchemaInspector()
        if not json_output:
            print("Database: (not configured - skipping schema verification)")

    route_inspector: RouteInspectorPort = StaticRouteInspector(routes)
    if routes:
        if not json_output:
            print(f"Routes: {len(routes)} routes to check")
    else:
        if not json_output:
            print("Routes: (not configured - skipping endpoint verification)")

    if not json_output:
        print()

    # Create service (no event emitter - independent mode)
    service = AntiMetricsVerificationService(
        schema_inspector=schema_inspector,
        route_inspector=route_inspector,
        event_emitter=None,
        time_authority=SystemTimeAuthority(),
    )

    try:
        # Run verification
        report = await service.verify_all()

        # Generate output
        if json_output:
            import json

            output = json.dumps(
                {
                    "report_id": str(report.report_id),
                    "verified_at": report.verified_at.isoformat(),
                    "overall_status": report.overall_status.value,
                    "total_violations": report.total_violations,
                    "verification_duration_ms": report.verification_duration_ms,
                    "checks": [
                        {
                            "check_type": c.check_type.value,
                            "status": c.status.value,
                            "items_checked": c.items_checked,
                            "violations": list(c.violations_found),
                        }
                        for c in report.checks
                    ],
                },
                indent=2,
            )
        else:
            output = service.generate_report_text(report)

        # Output result
        print(output)

        # Write to file if requested
        if output_file:
            with open(output_file, "w") as f:
                f.write(output)
            print(f"\nReport written to: {output_file}")

        # Return exit code based on status
        if report.overall_status == VerificationStatus.FAIL:
            return 1
        return 0

    except Exception as e:
        print(f"ERROR: {e}")
        return 2


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Anti-Metrics Verification CLI",
        epilog="Run independently to verify system is surveillance-free.",
    )
    parser.add_argument(
        "database_url",
        nargs="?",
        help="PostgreSQL connection URL (e.g., postgres://user:pass@host/db)",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Write report to file",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output JSON format instead of text",
    )
    parser.add_argument(
        "--routes-file",
        help="JSON file containing routes to check",
    )

    args = parser.parse_args()

    # Load routes from file if provided
    routes = None
    if args.routes_file:
        import json

        with open(args.routes_file) as f:
            routes_data = json.load(f)
            routes = [
                RouteInfo(
                    method=r["method"],
                    path=r["path"],
                    name=r.get("name"),
                )
                for r in routes_data
            ]

    # Run verification
    exit_code = asyncio.run(
        verify_anti_metrics_cli(
            database_url=args.database_url,
            routes=routes,
            output_file=args.output,
            json_output=args.json,
        )
    )

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
