"""Unit tests for ConcurrentDeliberationService (Story 2.2, Task 3).

Tests:
- HALT FIRST pattern enforcement
- Concurrent invocation with pool management
- Resource release after completion
- Failure reporting (CT-11)
- Performance metrics logging

Constitutional Constraints:
- FR10: 72 agents can deliberate concurrently without degradation
- CT-11: Silent failure destroys legitimacy -> report all failures
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.application.ports.agent_orchestrator import (
    AgentOutput,
    AgentRequest,
    ContextBundle,
)
from src.application.services.concurrent_deliberation_service import (
    ConcurrentDeliberationService,
    ConcurrentResult,
)
from src.domain.errors.agent import AgentPoolExhaustedError
from src.domain.errors.writer import SystemHaltedError
from src.domain.models.agent_pool import AgentPool


def make_context() -> ContextBundle:
    """Create a test context bundle."""
    return ContextBundle(
        bundle_id=uuid4(),
        topic_id="test-topic",
        topic_content="Test content",
        metadata=None,
        created_at=datetime.now(timezone.utc),
    )


def make_request(agent_id: str) -> AgentRequest:
    """Create a test agent request."""
    return AgentRequest(
        request_id=uuid4(),
        agent_id=agent_id,
        context=make_context(),
    )


def make_output(agent_id: str, request_id: uuid4) -> AgentOutput:
    """Create a test agent output."""
    return AgentOutput(
        output_id=uuid4(),
        agent_id=agent_id,
        request_id=request_id,
        content="Test output",
        content_type="text/plain",
        generated_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def mock_orchestrator() -> AsyncMock:
    """Create a mock agent orchestrator."""
    mock = AsyncMock()

    async def invoke_side_effect(agent_id: str, context: ContextBundle) -> AgentOutput:
        return AgentOutput(
            output_id=uuid4(),
            agent_id=agent_id,
            request_id=uuid4(),
            content=f"Output from {agent_id}",
            content_type="text/plain",
            generated_at=datetime.now(timezone.utc),
        )

    mock.invoke.side_effect = invoke_side_effect
    return mock


@pytest.fixture
def mock_halt_checker() -> AsyncMock:
    """Create a mock halt checker that returns not halted."""
    mock = AsyncMock()
    mock.is_halted.return_value = False
    mock.get_halt_reason.return_value = None
    return mock


@pytest.fixture
def mock_halt_checker_halted() -> AsyncMock:
    """Create a mock halt checker that returns halted."""
    mock = AsyncMock()
    mock.is_halted.return_value = True
    mock.get_halt_reason.return_value = "System integrity check failed"
    return mock


class TestConcurrentDeliberationServiceInit:
    """Test service initialization."""

    def test_initialization_with_defaults(
        self,
        mock_orchestrator: AsyncMock,
        mock_halt_checker: AsyncMock,
    ) -> None:
        """Service initializes with default pool."""
        service = ConcurrentDeliberationService(
            orchestrator=mock_orchestrator,
            halt_checker=mock_halt_checker,
        )

        assert service.available_capacity == 72
        assert service.active_count == 0

    def test_initialization_with_custom_pool(
        self,
        mock_orchestrator: AsyncMock,
        mock_halt_checker: AsyncMock,
    ) -> None:
        """Service initializes with custom pool."""
        pool = AgentPool(max_concurrent=10)
        service = ConcurrentDeliberationService(
            orchestrator=mock_orchestrator,
            halt_checker=mock_halt_checker,
            pool=pool,
        )

        assert service.available_capacity == 10


class TestConcurrentInvocation:
    """Test invoke_concurrent method."""

    @pytest.mark.asyncio
    async def test_invoke_concurrent_success(
        self,
        mock_orchestrator: AsyncMock,
        mock_halt_checker: AsyncMock,
    ) -> None:
        """Concurrent invocation succeeds with all agents."""
        service = ConcurrentDeliberationService(
            orchestrator=mock_orchestrator,
            halt_checker=mock_halt_checker,
        )

        requests = [make_request(f"archon-{i}") for i in range(3)]
        result = await service.invoke_concurrent(requests)

        assert isinstance(result, ConcurrentResult)
        assert result.success_count == 3
        assert result.failure_count == 0
        assert len(result.outputs) == 3

    @pytest.mark.asyncio
    async def test_invoke_concurrent_checks_halt_first(
        self,
        mock_orchestrator: AsyncMock,
        mock_halt_checker_halted: AsyncMock,
    ) -> None:
        """Concurrent invocation checks halt state first."""
        service = ConcurrentDeliberationService(
            orchestrator=mock_orchestrator,
            halt_checker=mock_halt_checker_halted,
        )

        requests = [make_request("archon-1")]

        with pytest.raises(SystemHaltedError, match="FR10"):
            await service.invoke_concurrent(requests)

        # Orchestrator should never be called
        mock_orchestrator.invoke.assert_not_called()

    @pytest.mark.asyncio
    async def test_invoke_concurrent_releases_pool_on_success(
        self,
        mock_orchestrator: AsyncMock,
        mock_halt_checker: AsyncMock,
    ) -> None:
        """Pool slots are released after successful invocation."""
        pool = AgentPool(max_concurrent=10)
        service = ConcurrentDeliberationService(
            orchestrator=mock_orchestrator,
            halt_checker=mock_halt_checker,
            pool=pool,
        )

        requests = [make_request(f"archon-{i}") for i in range(5)]
        await service.invoke_concurrent(requests)

        # Pool should be empty after completion
        assert pool.active_count == 0
        assert pool.available_count == 10

    @pytest.mark.asyncio
    async def test_invoke_concurrent_releases_pool_on_failure(
        self,
        mock_halt_checker: AsyncMock,
    ) -> None:
        """Pool slots are released even when invocation fails."""
        mock_orchestrator = AsyncMock()
        mock_orchestrator.invoke.side_effect = Exception("Agent error")

        pool = AgentPool(max_concurrent=10)
        service = ConcurrentDeliberationService(
            orchestrator=mock_orchestrator,
            halt_checker=mock_halt_checker,
            pool=pool,
        )

        requests = [make_request(f"archon-{i}") for i in range(3)]
        result = await service.invoke_concurrent(requests)

        # Pool should still be empty after completion
        assert pool.active_count == 0
        assert result.failure_count == 3
        assert result.success_count == 0

    @pytest.mark.asyncio
    async def test_invoke_concurrent_reports_partial_failures(
        self,
        mock_halt_checker: AsyncMock,
    ) -> None:
        """Partial failures are reported in result (CT-11)."""
        mock_orchestrator = AsyncMock()
        call_count = 0

        async def invoke_with_failures(
            agent_id: str, context: ContextBundle
        ) -> AgentOutput:
            nonlocal call_count
            call_count += 1
            if call_count % 2 == 0:
                raise Exception(f"Agent {agent_id} failed")
            return AgentOutput(
                output_id=uuid4(),
                agent_id=agent_id,
                request_id=uuid4(),
                content="Success",
                content_type="text/plain",
                generated_at=datetime.now(timezone.utc),
            )

        mock_orchestrator.invoke.side_effect = invoke_with_failures

        service = ConcurrentDeliberationService(
            orchestrator=mock_orchestrator,
            halt_checker=mock_halt_checker,
        )

        requests = [make_request(f"archon-{i}") for i in range(4)]
        result = await service.invoke_concurrent(requests)

        # Half should fail (every 2nd call)
        assert result.success_count == 2
        assert result.failure_count == 2
        assert len(result.failed_agents) == 2

    @pytest.mark.asyncio
    async def test_invoke_concurrent_pool_exhaustion(
        self,
        mock_orchestrator: AsyncMock,
        mock_halt_checker: AsyncMock,
    ) -> None:
        """Pool exhaustion raises AgentPoolExhaustedError."""
        pool = AgentPool(max_concurrent=2)
        service = ConcurrentDeliberationService(
            orchestrator=mock_orchestrator,
            halt_checker=mock_halt_checker,
            pool=pool,
        )

        requests = [make_request(f"archon-{i}") for i in range(5)]

        with pytest.raises(AgentPoolExhaustedError):
            await service.invoke_concurrent(requests)


class TestInvokeSingle:
    """Test invoke_single method."""

    @pytest.mark.asyncio
    async def test_invoke_single_success(
        self,
        mock_orchestrator: AsyncMock,
        mock_halt_checker: AsyncMock,
    ) -> None:
        """Single invocation succeeds."""
        service = ConcurrentDeliberationService(
            orchestrator=mock_orchestrator,
            halt_checker=mock_halt_checker,
        )

        request = make_request("archon-1")
        output = await service.invoke_single(request)

        assert isinstance(output, AgentOutput)
        assert output.agent_id == "archon-1"

    @pytest.mark.asyncio
    async def test_invoke_single_checks_halt_first(
        self,
        mock_orchestrator: AsyncMock,
        mock_halt_checker_halted: AsyncMock,
    ) -> None:
        """Single invocation checks halt state first."""
        service = ConcurrentDeliberationService(
            orchestrator=mock_orchestrator,
            halt_checker=mock_halt_checker_halted,
        )

        request = make_request("archon-1")

        with pytest.raises(SystemHaltedError, match="FR10"):
            await service.invoke_single(request)

    @pytest.mark.asyncio
    async def test_invoke_single_releases_pool_on_success(
        self,
        mock_orchestrator: AsyncMock,
        mock_halt_checker: AsyncMock,
    ) -> None:
        """Pool slot is released after single invocation."""
        pool = AgentPool(max_concurrent=5)
        service = ConcurrentDeliberationService(
            orchestrator=mock_orchestrator,
            halt_checker=mock_halt_checker,
            pool=pool,
        )

        request = make_request("archon-1")
        await service.invoke_single(request)

        assert pool.active_count == 0

    @pytest.mark.asyncio
    async def test_invoke_single_releases_pool_on_failure(
        self,
        mock_halt_checker: AsyncMock,
    ) -> None:
        """Pool slot is released even when single invocation fails."""
        mock_orchestrator = AsyncMock()
        mock_orchestrator.invoke.side_effect = Exception("Agent error")

        pool = AgentPool(max_concurrent=5)
        service = ConcurrentDeliberationService(
            orchestrator=mock_orchestrator,
            halt_checker=mock_halt_checker,
            pool=pool,
        )

        request = make_request("archon-1")

        from src.domain.errors.agent import AgentInvocationError

        with pytest.raises(AgentInvocationError):
            await service.invoke_single(request)

        # Pool should be empty after failure
        assert pool.active_count == 0


class TestConcurrentResult:
    """Test ConcurrentResult dataclass."""

    def test_result_properties(self) -> None:
        """Result computes properties correctly."""
        outputs = (
            make_output("archon-1", uuid4()),
            make_output("archon-2", uuid4()),
        )
        result = ConcurrentResult(
            batch_id=uuid4(),
            outputs=outputs,
            failed_agents=("archon-3",),
            total_ms=100,
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
        )

        assert result.success_count == 2
        assert result.failure_count == 1
        assert result.total_count == 3

    def test_result_is_frozen(self) -> None:
        """ConcurrentResult is immutable."""
        result = ConcurrentResult(
            batch_id=uuid4(),
            outputs=(),
            failed_agents=(),
            total_ms=0,
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
        )

        with pytest.raises(AttributeError):
            result.total_ms = 999  # type: ignore[misc]


class TestPoolStatus:
    """Test pool status monitoring."""

    def test_get_pool_status(
        self,
        mock_orchestrator: AsyncMock,
        mock_halt_checker: AsyncMock,
    ) -> None:
        """Pool status returns correct values."""
        pool = AgentPool(max_concurrent=72)
        pool.acquire("archon-1")
        pool.acquire("archon-2")

        service = ConcurrentDeliberationService(
            orchestrator=mock_orchestrator,
            halt_checker=mock_halt_checker,
            pool=pool,
        )

        status = service.get_pool_status()

        assert status["active_count"] == 2
        assert status["available_count"] == 70
        assert status["max_concurrent"] == 72


class TestNoInfrastructureImports:
    """Verify service has no infrastructure imports."""

    def test_service_no_infrastructure_imports(self) -> None:
        """concurrent_deliberation_service.py has no infrastructure imports."""
        import ast
        from pathlib import Path

        file_path = Path("src/application/services/concurrent_deliberation_service.py")
        source = file_path.read_text()
        tree = ast.parse(source)

        forbidden_modules = [
            "src.infrastructure",
            "sqlalchemy",
            "redis",
            "supabase",
            "crewai",
        ]

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    for forbidden in forbidden_modules:
                        assert not alias.name.startswith(forbidden), (
                            f"Forbidden import: {alias.name}"
                        )
            elif isinstance(node, ast.ImportFrom) and node.module:
                for forbidden in forbidden_modules:
                    assert not node.module.startswith(forbidden), (
                        f"Forbidden import: {node.module}"
                    )
