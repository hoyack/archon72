"""
Smoke tests to verify all critical dependencies are installed correctly.

These tests confirm that:
1. Python 3.11+ is installed (required for asyncio.TaskGroup)
2. All core dependencies are importable
3. Async functionality is available
4. Project version is accessible

Run with: poetry run pytest tests/unit/test_smoke.py -v
"""

import sys

import pytest


class TestPythonVersion:
    """Verify Python version requirements."""

    def test_python_311_or_higher(self) -> None:
        """Python 3.11+ is required for asyncio.TaskGroup support."""
        assert sys.version_info >= (3, 11), (
            f"Python 3.11+ required for asyncio.TaskGroup, "
            f"got {sys.version_info.major}.{sys.version_info.minor}"
        )

    def test_taskgroup_available(self) -> None:
        """asyncio.TaskGroup must be available (Python 3.11+ feature)."""
        import asyncio

        assert hasattr(asyncio, "TaskGroup"), "asyncio.TaskGroup not available"


class TestCoreFramework:
    """Verify core framework dependencies."""

    def test_fastapi_import(self) -> None:
        """FastAPI must be importable."""
        from fastapi import FastAPI

        app = FastAPI()
        assert app is not None

    def test_pydantic_v2(self) -> None:
        """Pydantic v2 must be installed (required for FastAPI integration)."""
        import pydantic

        major_version = int(pydantic.VERSION.split(".")[0])
        assert major_version >= 2, f"Pydantic v2 required, got {pydantic.VERSION}"

    def test_uvicorn_import(self) -> None:
        """Uvicorn must be importable."""
        import uvicorn

        assert uvicorn is not None


class TestMultiAgentOrchestration:
    """Verify CrewAI for 72-agent orchestration (ADR-2)."""

    def test_crewai_core_imports(self) -> None:
        """CrewAI core classes must be importable."""
        from crewai import Agent, Crew, Task

        assert Agent is not None
        assert Task is not None
        assert Crew is not None


class TestDatabaseAndEventStore:
    """Verify database dependencies for Event Store (ADR-1)."""

    def test_sqlalchemy_async(self) -> None:
        """SQLAlchemy 2.0+ async mode must be available."""
        from sqlalchemy import __version__ as sa_version
        from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

        major_version = int(sa_version.split(".")[0])
        assert major_version >= 2, f"SQLAlchemy 2.0+ required, got {sa_version}"
        assert AsyncSession is not None
        assert create_async_engine is not None

    def test_supabase_import(self) -> None:
        """Supabase client must be importable."""
        from supabase import create_client

        assert create_client is not None

    def test_alembic_import(self) -> None:
        """Alembic must be importable for migrations."""
        from alembic import command, config

        assert command is not None
        assert config is not None


class TestHaltTransport:
    """Verify Redis for dual-channel halt transport (ADR-3)."""

    def test_redis_async_import(self) -> None:
        """Redis async client must be importable."""
        from redis.asyncio import Redis

        assert Redis is not None


class TestAsyncHttp:
    """Verify async HTTP client."""

    def test_httpx_async_import(self) -> None:
        """httpx async client must be importable."""
        from httpx import AsyncClient

        assert AsyncClient is not None


class TestConstitutionalWitnessing:
    """Verify structured logging for constitutional witnessing."""

    def test_structlog_import(self) -> None:
        """structlog must be importable."""
        import structlog

        logger = structlog.get_logger()
        assert logger is not None

    def test_structlog_configuration(self) -> None:
        """structlog can be bound with context."""
        import structlog

        logger = structlog.get_logger()
        bound_logger = logger.bind(agent_id="archon-1", operation="test")
        assert bound_logger is not None


class TestHsmSigning:
    """Verify cryptography for HSM signing (ADR-4)."""

    def test_cryptography_hashes(self) -> None:
        """Cryptography hash algorithms must be available."""
        from cryptography.hazmat.primitives import hashes

        assert hashes.SHA256 is not None
        assert hashes.SHA384 is not None
        assert hashes.SHA512 is not None

    def test_cryptography_ecdsa(self) -> None:
        """ECDSA signing must be available."""
        from cryptography.hazmat.primitives.asymmetric import ec

        assert ec.ECDSA is not None
        assert ec.SECP384R1 is not None


class TestPropertyBasedTesting:
    """Verify hypothesis for constitutional invariant testing."""

    def test_hypothesis_import(self) -> None:
        """hypothesis must be importable."""
        from hypothesis import given, strategies

        assert given is not None
        assert strategies is not None


class TestProjectVersion:
    """Verify project metadata is accessible."""

    def test_version_accessible(self) -> None:
        """Project version must be accessible from src package."""
        from src import __version__

        assert __version__ is not None
        assert isinstance(__version__, str)
        assert len(__version__) > 0

    def test_version_format(self) -> None:
        """Version must be in semver format."""
        from src import __version__

        parts = __version__.split(".")
        assert len(parts) >= 2, f"Version must be semver format, got {__version__}"


class TestAsyncCapabilities:
    """Verify async/await functionality."""

    @pytest.mark.asyncio
    async def test_async_function_runs(self) -> None:
        """Basic async function execution must work."""
        import asyncio

        result = await asyncio.sleep(0, result="success")
        assert result == "success"

    @pytest.mark.asyncio
    async def test_taskgroup_execution(self) -> None:
        """asyncio.TaskGroup must execute tasks correctly."""
        import asyncio

        results: list[int] = []

        async def add_result(value: int) -> None:
            await asyncio.sleep(0)
            results.append(value)

        async with asyncio.TaskGroup() as tg:
            tg.create_task(add_result(1))
            tg.create_task(add_result(2))
            tg.create_task(add_result(3))

        assert sorted(results) == [1, 2, 3]
