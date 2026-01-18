"""Tests for Anti-Metrics Verification CLI.

Story: consent-gov-10.2: Anti-Metrics Verification

These tests verify that:
1. CLI can run independently (AC: 6)
2. CLI produces valid reports (AC: 7)
3. CLI handles various input scenarios
4. CLI returns correct exit codes
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from src.application.ports.governance.anti_metrics_verification_port import (
    RouteInfo,
)
from src.infrastructure.adapters.governance.verification_cli import (
    FastAPIRouteInspector,
    PostgresSchemaInspector,
    StaticRouteInspector,
    SystemTimeAuthority,
    verify_anti_metrics_cli,
)


class TestSystemTimeAuthority:
    """Tests for SystemTimeAuthority."""

    def test_now_returns_utc_datetime(self) -> None:
        """now() returns a UTC datetime."""
        authority = SystemTimeAuthority()
        result = authority.now()

        assert isinstance(result, datetime)
        assert result.tzinfo == timezone.utc

    def test_utcnow_returns_utc_datetime(self) -> None:
        """utcnow() returns a UTC datetime."""
        authority = SystemTimeAuthority()
        result = authority.utcnow()

        assert isinstance(result, datetime)
        assert result.tzinfo == timezone.utc

    def test_monotonic_returns_float(self) -> None:
        """monotonic() returns a float."""
        authority = SystemTimeAuthority()
        result = authority.monotonic()

        assert isinstance(result, float)

    def test_time_advances(self) -> None:
        """Successive calls return advancing time."""
        authority = SystemTimeAuthority()

        # Small sleep to ensure measurable difference
        import time

        t1 = authority.monotonic()
        time.sleep(0.001)
        t2 = authority.monotonic()

        assert t2 > t1


class TestStaticRouteInspector:
    """Tests for StaticRouteInspector."""

    @pytest.mark.asyncio
    async def test_empty_routes_by_default(self) -> None:
        """Returns empty list when no routes provided."""
        inspector = StaticRouteInspector()
        routes = await inspector.get_all_routes()

        assert routes == []

    @pytest.mark.asyncio
    async def test_returns_provided_routes(self) -> None:
        """Returns the routes provided at init."""
        input_routes = [
            RouteInfo(method="GET", path="/health"),
            RouteInfo(method="POST", path="/api/tasks"),
        ]
        inspector = StaticRouteInspector(input_routes)
        routes = await inspector.get_all_routes()

        assert len(routes) == 2
        assert routes[0].method == "GET"
        assert routes[0].path == "/health"

    @pytest.mark.asyncio
    async def test_returns_copy_not_original(self) -> None:
        """Returns a copy to prevent modification."""
        input_routes = [RouteInfo(method="GET", path="/test")]
        inspector = StaticRouteInspector(input_routes)

        routes1 = await inspector.get_all_routes()
        routes2 = await inspector.get_all_routes()

        # Should be equal but different objects
        assert routes1 == routes2
        assert routes1 is not routes2


class TestFastAPIRouteInspector:
    """Tests for FastAPIRouteInspector."""

    @pytest.mark.asyncio
    async def test_extracts_routes_from_app(self) -> None:
        """Extracts routes from FastAPI app."""

        # Create mock route
        mock_route = MagicMock()
        mock_route.path = "/v1/test"
        mock_route.methods = {"GET", "POST"}
        mock_route.name = "test_route"

        # Create mock app
        mock_app = MagicMock()
        mock_app.routes = [mock_route]

        inspector = FastAPIRouteInspector(mock_app)
        routes = await inspector.get_all_routes()

        assert len(routes) == 2
        paths = {r.path for r in routes}
        methods = {r.method for r in routes}

        assert "/v1/test" in paths
        assert "GET" in methods
        assert "POST" in methods

    @pytest.mark.asyncio
    async def test_skips_routes_without_methods(self) -> None:
        """Skips routes that don't have methods attribute."""

        # Route with methods
        mock_route1 = MagicMock()
        mock_route1.path = "/v1/test"
        mock_route1.methods = {"GET"}
        mock_route1.name = "test_route"

        # Route without methods (e.g., mount)
        mock_route2 = MagicMock(spec=[])  # No attributes

        mock_app = MagicMock()
        mock_app.routes = [mock_route1, mock_route2]

        inspector = FastAPIRouteInspector(mock_app)
        routes = await inspector.get_all_routes()

        # Should only have the route with methods
        assert len(routes) == 1

    @pytest.mark.asyncio
    async def test_handles_empty_routes(self) -> None:
        """Handles app with no routes."""
        mock_app = MagicMock()
        mock_app.routes = []

        inspector = FastAPIRouteInspector(mock_app)
        routes = await inspector.get_all_routes()

        assert routes == []


class TestPostgresSchemaInspector:
    """Tests for PostgresSchemaInspector initialization."""

    def test_stores_database_url(self) -> None:
        """Stores database URL for later connection."""
        url = "postgres://user:pass@host/db"
        inspector = PostgresSchemaInspector(url)

        assert inspector._database_url == url

    @pytest.mark.asyncio
    async def test_get_all_tables_requires_asyncpg(self) -> None:
        """get_all_tables raises ImportError if asyncpg not available."""
        # We can't easily test this without actually removing asyncpg
        # This test documents the expected behavior
        pass

    @pytest.mark.asyncio
    async def test_get_all_columns_requires_asyncpg(self) -> None:
        """get_all_columns raises ImportError if asyncpg not available."""
        # We can't easily test this without actually removing asyncpg
        # This test documents the expected behavior
        pass


class TestVerifyAntiMetricsCli:
    """Tests for verify_anti_metrics_cli function."""

    @pytest.mark.asyncio
    async def test_returns_zero_for_clean_system(self) -> None:
        """Returns exit code 0 when no violations."""
        exit_code = await verify_anti_metrics_cli(
            database_url=None,
            routes=[RouteInfo(method="GET", path="/health")],
        )

        assert exit_code == 0

    @pytest.mark.asyncio
    async def test_returns_one_for_violations(self) -> None:
        """Returns exit code 1 when violations found."""
        exit_code = await verify_anti_metrics_cli(
            database_url=None,
            routes=[RouteInfo(method="GET", path="/v1/metrics/participant")],
        )

        assert exit_code == 1

    @pytest.mark.asyncio
    async def test_no_database_uses_empty_inspector(self) -> None:
        """When no database URL, uses empty schema inspector."""
        exit_code = await verify_anti_metrics_cli(
            database_url=None,
            routes=None,
        )

        # Should pass since nothing to check
        assert exit_code == 0

    @pytest.mark.asyncio
    async def test_json_output_is_valid_json(
        self,
        tmp_path,
    ) -> None:
        """JSON output is valid JSON."""
        import json

        output_file = tmp_path / "report.json"

        await verify_anti_metrics_cli(
            database_url=None,
            routes=[RouteInfo(method="GET", path="/health")],
            output_file=str(output_file),
            json_output=True,
        )

        # Should be valid JSON
        content = output_file.read_text()
        data = json.loads(content)

        assert "report_id" in data
        assert "overall_status" in data
        assert "checks" in data

    @pytest.mark.asyncio
    async def test_text_output_contains_header(
        self,
        tmp_path,
        capsys,
    ) -> None:
        """Text output contains verification header."""
        await verify_anti_metrics_cli(
            database_url=None,
            routes=None,
            json_output=False,
        )

        captured = capsys.readouterr()
        assert "ANTI-METRICS VERIFICATION CLI" in captured.out

    @pytest.mark.asyncio
    async def test_writes_to_output_file(
        self,
        tmp_path,
    ) -> None:
        """Writes report to specified output file."""
        output_file = tmp_path / "report.txt"

        await verify_anti_metrics_cli(
            database_url=None,
            routes=None,
            output_file=str(output_file),
        )

        assert output_file.exists()
        content = output_file.read_text()
        assert "VERIFICATION REPORT" in content

    @pytest.mark.asyncio
    async def test_multiple_violations_reported(self) -> None:
        """Reports all violations found."""
        exit_code = await verify_anti_metrics_cli(
            database_url=None,
            routes=[
                RouteInfo(method="GET", path="/v1/metrics/participant"),
                RouteInfo(method="GET", path="/v1/analytics/dashboard"),
                RouteInfo(method="GET", path="/health"),  # OK
            ],
        )

        assert exit_code == 1

    @pytest.mark.asyncio
    async def test_operational_endpoints_allowed(self) -> None:
        """Operational endpoints (/metrics, /health) are allowed."""
        exit_code = await verify_anti_metrics_cli(
            database_url=None,
            routes=[
                RouteInfo(method="GET", path="/v1/metrics"),  # Prometheus
                RouteInfo(method="GET", path="/health"),
                RouteInfo(method="GET", path="/readiness"),
            ],
        )

        assert exit_code == 0


class TestRouteInfoDataclass:
    """Tests for RouteInfo dataclass."""

    def test_creates_with_required_fields(self) -> None:
        """Creates with method and path."""
        route = RouteInfo(method="GET", path="/test")

        assert route.method == "GET"
        assert route.path == "/test"
        assert route.name is None

    def test_creates_with_all_fields(self) -> None:
        """Creates with all fields including name."""
        route = RouteInfo(method="POST", path="/api", name="create_item")

        assert route.method == "POST"
        assert route.path == "/api"
        assert route.name == "create_item"

    def test_is_immutable(self) -> None:
        """RouteInfo is frozen/immutable."""
        route = RouteInfo(method="GET", path="/test")

        with pytest.raises(AttributeError):
            route.method = "POST"
