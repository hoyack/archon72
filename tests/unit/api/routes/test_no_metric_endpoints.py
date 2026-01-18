"""Tests verifying structural absence of metric endpoints.

Story: consent-gov-10.1: Anti-Metrics Data Layer Enforcement
Task 3: Implement structural absence (no metric endpoints)

These tests verify that:
1. No /metrics/participant endpoint exists (AC: 4)
2. No /analytics/engagement endpoint exists (AC: 4)
3. No /tracking/* routes exist (AC: 4)
4. API router has no metric paths (AC: 4)

This is STRUCTURAL ABSENCE - we're testing that things DON'T exist.
The test is important because it documents the constitutional constraint
and will fail if someone accidentally adds these endpoints.
"""

from pathlib import Path

import pytest


class TestNoParticipantMetricEndpoints:
    """Tests verifying no participant metric endpoints exist.

    Per NFR-CONST-08: Anti-metrics are enforced at data layer;
    collection endpoints do not exist.
    """

    def test_no_participant_metrics_route_file(self) -> None:
        """No dedicated participant metrics route file exists."""
        routes_dir = Path("src/api/routes")
        assert routes_dir.exists(), "Routes directory should exist"

        # These files must NOT exist
        prohibited_files = [
            "participant_metrics.py",
            "cluster_metrics.py",
            "user_metrics.py",
            "engagement.py",
            "retention.py",
            "analytics.py",
            "tracking.py",
            "session_tracking.py",
            "activity.py",
        ]

        for filename in prohibited_files:
            filepath = routes_dir / filename
            assert not filepath.exists(), (
                f"Prohibited route file exists: {filepath}\n"
                f"NFR-CONST-08 forbids metric collection endpoints"
            )

    def test_no_metrics_participant_in_route_paths(self) -> None:
        """No /metrics/participant route defined in any route file."""
        routes_dir = Path("src/api/routes")
        assert routes_dir.exists(), "Routes directory should exist"

        prohibited_patterns = [
            "/metrics/participant",
            "/metrics/cluster",
            "/metrics/user",
            "/analytics/engagement",
            "/analytics/retention",
            "/tracking/",
            "/sessions/",
            "/activity/",
            "/performance/scores",
            "/engagement/",
            "/retention/",
        ]

        for route_file in routes_dir.glob("*.py"):
            if route_file.name.startswith("__"):
                continue

            content = route_file.read_text()

            for pattern in prohibited_patterns:
                assert pattern not in content, (
                    f"Found prohibited route pattern '{pattern}' in {route_file.name}\n"
                    f"NFR-CONST-08 forbids metric collection endpoints"
                )

    def test_routes_init_has_no_metric_routers(self) -> None:
        """Routes __init__ does not export metric-related routers."""
        init_file = Path("src/api/routes/__init__.py")
        assert init_file.exists(), "Routes __init__.py should exist"

        content = init_file.read_text()

        prohibited_exports = [
            "participant_metrics_router",
            "engagement_router",
            "retention_router",
            "analytics_router",
            "tracking_router",
            "session_router",
            "activity_router",
        ]

        for export in prohibited_exports:
            assert export not in content, (
                f"Found prohibited router export '{export}' in routes/__init__.py\n"
                f"NFR-CONST-08 forbids metric collection endpoints"
            )

    def test_existing_metrics_is_operational_only(self) -> None:
        """The existing /v1/metrics endpoint is for operational metrics only.

        This endpoint is allowed because it exposes Prometheus operational
        metrics (uptime, latency, errors) - NOT participant-level metrics.
        """
        metrics_file = Path("src/api/routes/metrics.py")
        if not metrics_file.exists():
            return  # No metrics file is also acceptable

        content = metrics_file.read_text()

        # Verify it documents it's for operational metrics
        assert (
            "operational metrics" in content.lower() or "prometheus" in content.lower()
        ), "metrics.py should document it's for operational/Prometheus metrics only"

        # Verify no participant metric patterns
        participant_patterns = [
            "participant",
            "completion_rate",
            "engagement_score",
            "retention_score",
            "session_count",
            "login_count",
        ]

        for pattern in participant_patterns:
            assert pattern not in content, (
                f"Found prohibited participant metric pattern '{pattern}' in metrics.py\n"
                f"metrics.py should only expose operational metrics"
            )


class TestNoMetricModelsInAPI:
    """Tests verifying no metric-related API models exist."""

    def test_no_metric_models_file(self) -> None:
        """No dedicated metric models file exists."""
        models_dir = Path("src/api/models")
        if not models_dir.exists():
            return  # No models directory is fine

        prohibited_files = [
            "participant_metrics.py",
            "engagement.py",
            "retention.py",
            "analytics.py",
            "tracking.py",
            "performance_metrics.py",
        ]

        for filename in prohibited_files:
            filepath = models_dir / filename
            assert not filepath.exists(), (
                f"Prohibited models file exists: {filepath}\n"
                f"NFR-CONST-08 forbids metric collection"
            )

    def test_no_metric_fields_in_api_models(self) -> None:
        """No metric-related fields in existing API models."""
        models_dir = Path("src/api/models")
        if not models_dir.exists():
            return  # No models directory is fine

        prohibited_fields = [
            "completion_rate",
            "success_rate",
            "failure_rate",
            "engagement_score",
            "retention_score",
            "performance_score",
            "session_count",
            "login_count",
            "activity_score",
        ]

        for model_file in models_dir.glob("*.py"):
            if model_file.name.startswith("__"):
                continue

            content = model_file.read_text()

            for field in prohibited_fields:
                # Skip if it's in a comment or docstring context
                # Simple heuristic: check if it appears as a field definition
                if f"{field}:" in content or f"{field} =" in content:
                    pytest.fail(
                        f"Found prohibited field pattern '{field}' in {model_file.name}\n"
                        f"NFR-CONST-08 forbids metric collection"
                    )


class TestStructuralAbsenceInCode:
    """Tests verifying structural absence in codebase."""

    def test_no_metric_storage_functions(self) -> None:
        """No metric storage functions exist in services."""
        services_dir = Path("src/application/services")
        if not services_dir.exists():
            return  # Services directory should exist

        prohibited_functions = [
            "store_participant_metrics",
            "save_engagement_score",
            "update_retention_metrics",
            "record_session",
            "track_activity",
            "calculate_completion_rate",
            "compute_performance_score",
        ]

        for service_file in services_dir.rglob("*.py"):
            if service_file.name.startswith("__"):
                continue

            content = service_file.read_text()

            for func_name in prohibited_functions:
                # Check for function definitions
                if f"def {func_name}" in content or f"async def {func_name}" in content:
                    pytest.fail(
                        f"Found prohibited function '{func_name}' in {service_file}\n"
                        f"NFR-CONST-08 forbids metric collection"
                    )

    def test_no_metric_tables_in_migrations(self) -> None:
        """No metric tables defined in migration files."""
        migrations_dir = Path("migrations")
        if not migrations_dir.exists():
            return  # No migrations directory is fine

        prohibited_tables = [
            "participant_metrics",
            "engagement_scores",
            "retention_metrics",
            "session_tracking",
            "performance_scores",
            "activity_log",
            "login_history",
            "completion_rates",
        ]

        for migration_file in migrations_dir.glob("*.sql"):
            content = migration_file.read_text().lower()

            for table in prohibited_tables:
                if f"create table {table}" in content:
                    pytest.fail(
                        f"Found prohibited table '{table}' in {migration_file.name}\n"
                        f"NFR-CONST-08 forbids metric storage"
                    )
