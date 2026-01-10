"""Integration tests for Concurrent Deliberation (Story 2.2, Task 5).

Tests:
- 72 agents complete without blocking (AC2)
- Resource release after completion (AC3)
- Performance within NFR5 bounds (AC2)
- Halt state respected during concurrent execution

These tests use the AgentOrchestratorStub to simulate real agent behavior
without requiring actual LLM infrastructure.

Constitutional Constraints:
- FR10: 72 agents can deliberate concurrently without degradation
- NFR5: 72 concurrent agent deliberations without degradation
- CT-11: Silent failure destroys legitimacy -> report all failures
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.application.ports.agent_orchestrator import (
    AgentRequest,
    ContextBundle,
)
from src.application.services.concurrent_deliberation_service import (
    ConcurrentDeliberationService,
)
from src.domain.errors.agent import AgentPoolExhaustedError
from src.domain.errors.writer import SystemHaltedError
from src.domain.models.agent_pool import MAX_CONCURRENT_AGENTS, AgentPool
from src.infrastructure.stubs.agent_orchestrator_stub import AgentOrchestratorStub
from src.infrastructure.stubs.halt_checker_stub import HaltCheckerStub


def make_context(topic_id: str | None = None) -> ContextBundle:
    """Create a test context bundle."""
    return ContextBundle(
        bundle_id=uuid4(),
        topic_id=topic_id or f"topic-{uuid4().hex[:8]}",
        topic_content="Integration test deliberation topic",
        metadata=None,
        created_at=datetime.now(timezone.utc),
    )


def make_request(agent_id: str, topic_id: str | None = None) -> AgentRequest:
    """Create a test agent request."""
    return AgentRequest(
        request_id=uuid4(),
        agent_id=agent_id,
        context=make_context(topic_id),
    )


def make_requests(count: int, prefix: str = "archon") -> list[AgentRequest]:
    """Create multiple test agent requests."""
    return [make_request(f"{prefix}-{i}") for i in range(count)]


@pytest.fixture
def orchestrator_stub() -> AgentOrchestratorStub:
    """Create stub orchestrator with fast execution."""
    return AgentOrchestratorStub(latency_ms=1)  # 1ms for fast tests


@pytest.fixture
def halt_checker_normal() -> HaltCheckerStub:
    """Create halt checker that returns not halted."""
    return HaltCheckerStub(force_halted=False)


@pytest.fixture
def halt_checker_halted() -> HaltCheckerStub:
    """Create halt checker that returns halted."""
    return HaltCheckerStub(force_halted=True, halt_reason="Integration test halt")


@pytest.fixture
def agent_pool() -> AgentPool:
    """Create a fresh agent pool."""
    return AgentPool()


class TestConcurrent72Agents:
    """Test 72 concurrent agent deliberations (AC2, FR10)."""

    @pytest.mark.asyncio
    async def test_72_agents_complete_without_blocking(
        self,
        orchestrator_stub: AgentOrchestratorStub,
        halt_checker_normal: HaltCheckerStub,
        agent_pool: AgentPool,
    ) -> None:
        """72 agents can complete concurrently (FR10, AC2)."""
        service = ConcurrentDeliberationService(
            orchestrator=orchestrator_stub,
            halt_checker=halt_checker_normal,
            pool=agent_pool,
        )

        requests = make_requests(72)
        result = await service.invoke_concurrent(requests)

        assert result.success_count == 72
        assert result.failure_count == 0
        assert len(result.outputs) == 72

    @pytest.mark.asyncio
    async def test_all_72_agents_produce_unique_outputs(
        self,
        orchestrator_stub: AgentOrchestratorStub,
        halt_checker_normal: HaltCheckerStub,
        agent_pool: AgentPool,
    ) -> None:
        """Each of 72 agents produces a unique output."""
        service = ConcurrentDeliberationService(
            orchestrator=orchestrator_stub,
            halt_checker=halt_checker_normal,
            pool=agent_pool,
        )

        requests = make_requests(72)
        result = await service.invoke_concurrent(requests)

        # All output IDs should be unique
        output_ids = [o.output_id for o in result.outputs]
        assert len(set(output_ids)) == 72

        # All agent IDs should be present
        agent_ids = {o.agent_id for o in result.outputs}
        expected_ids = {f"archon-{i}" for i in range(72)}
        assert agent_ids == expected_ids

    @pytest.mark.asyncio
    async def test_concurrent_execution_is_faster_than_sequential(
        self,
        orchestrator_stub: AgentOrchestratorStub,
        halt_checker_normal: HaltCheckerStub,
        agent_pool: AgentPool,
    ) -> None:
        """Concurrent execution completes faster than sequential would.

        With 10ms latency and 10 agents:
        - Sequential: ~100ms
        - Concurrent: ~10ms (plus overhead)

        This validates agents don't block each other (AC2).
        """
        # Use longer latency to make timing difference clear
        orchestrator_stub.set_latency(10)

        service = ConcurrentDeliberationService(
            orchestrator=orchestrator_stub,
            halt_checker=halt_checker_normal,
            pool=agent_pool,
        )

        requests = make_requests(10)

        start = time.monotonic()
        result = await service.invoke_concurrent(requests)
        elapsed_ms = (time.monotonic() - start) * 1000

        # Should complete MUCH faster than sequential (10 * 10ms = 100ms)
        # Allow generous overhead but verify it's concurrent
        assert elapsed_ms < 80  # Should be ~10-20ms with overhead
        assert result.success_count == 10


class TestResourceManagement:
    """Test resource management (AC3)."""

    @pytest.mark.asyncio
    async def test_pool_released_after_successful_invocation(
        self,
        orchestrator_stub: AgentOrchestratorStub,
        halt_checker_normal: HaltCheckerStub,
        agent_pool: AgentPool,
    ) -> None:
        """Pool slots are released after completion (AC3)."""
        service = ConcurrentDeliberationService(
            orchestrator=orchestrator_stub,
            halt_checker=halt_checker_normal,
            pool=agent_pool,
        )

        requests = make_requests(50)
        await service.invoke_concurrent(requests)

        # Pool should be fully available after completion
        assert agent_pool.active_count == 0
        assert agent_pool.available_count == MAX_CONCURRENT_AGENTS

    @pytest.mark.asyncio
    async def test_pool_released_after_partial_failure(
        self,
        halt_checker_normal: HaltCheckerStub,
        agent_pool: AgentPool,
    ) -> None:
        """Pool slots released even when some agents fail (AC3)."""
        # Configure some agents to fail
        orchestrator_stub = AgentOrchestratorStub(
            latency_ms=1,
            fail_agents={"archon-2", "archon-5", "archon-8"},
        )

        service = ConcurrentDeliberationService(
            orchestrator=orchestrator_stub,
            halt_checker=halt_checker_normal,
            pool=agent_pool,
        )

        requests = make_requests(10)
        result = await service.invoke_concurrent(requests)

        # Pool should still be fully available
        assert agent_pool.active_count == 0
        assert agent_pool.available_count == MAX_CONCURRENT_AGENTS

        # But we should have failures recorded
        assert result.failure_count == 3
        assert result.success_count == 7

    @pytest.mark.asyncio
    async def test_sequential_batches_can_reuse_pool(
        self,
        orchestrator_stub: AgentOrchestratorStub,
        halt_checker_normal: HaltCheckerStub,
        agent_pool: AgentPool,
    ) -> None:
        """Pool slots can be reused across sequential batches."""
        service = ConcurrentDeliberationService(
            orchestrator=orchestrator_stub,
            halt_checker=halt_checker_normal,
            pool=agent_pool,
        )

        # First batch
        requests1 = make_requests(72, prefix="batch1")
        result1 = await service.invoke_concurrent(requests1)
        assert result1.success_count == 72

        # Second batch - same pool should work
        requests2 = make_requests(72, prefix="batch2")
        result2 = await service.invoke_concurrent(requests2)
        assert result2.success_count == 72

        assert agent_pool.active_count == 0

    @pytest.mark.asyncio
    async def test_exceeding_72_raises_pool_exhausted(
        self,
        orchestrator_stub: AgentOrchestratorStub,
        halt_checker_normal: HaltCheckerStub,
        agent_pool: AgentPool,
    ) -> None:
        """Requesting >72 agents raises AgentPoolExhaustedError."""
        service = ConcurrentDeliberationService(
            orchestrator=orchestrator_stub,
            halt_checker=halt_checker_normal,
            pool=agent_pool,
        )

        requests = make_requests(73)  # One more than limit

        with pytest.raises(AgentPoolExhaustedError, match="FR10"):
            await service.invoke_concurrent(requests)


class TestHaltStateRespected:
    """Test halt state is respected during concurrent execution."""

    @pytest.mark.asyncio
    async def test_halt_prevents_concurrent_invocation(
        self,
        orchestrator_stub: AgentOrchestratorStub,
        halt_checker_halted: HaltCheckerStub,
        agent_pool: AgentPool,
    ) -> None:
        """Halt state prevents concurrent invocation."""
        service = ConcurrentDeliberationService(
            orchestrator=orchestrator_stub,
            halt_checker=halt_checker_halted,
            pool=agent_pool,
        )

        requests = make_requests(10)

        with pytest.raises(SystemHaltedError, match="FR10"):
            await service.invoke_concurrent(requests)

        # Pool should not have been touched
        assert agent_pool.active_count == 0

    @pytest.mark.asyncio
    async def test_halt_prevents_single_invocation(
        self,
        orchestrator_stub: AgentOrchestratorStub,
        halt_checker_halted: HaltCheckerStub,
        agent_pool: AgentPool,
    ) -> None:
        """Halt state prevents single agent invocation."""
        service = ConcurrentDeliberationService(
            orchestrator=orchestrator_stub,
            halt_checker=halt_checker_halted,
            pool=agent_pool,
        )

        request = make_request("archon-1")

        with pytest.raises(SystemHaltedError, match="FR10"):
            await service.invoke_single(request)


class TestPerformanceMetrics:
    """Test performance metrics (NFR5 compliance)."""

    @pytest.mark.asyncio
    async def test_result_includes_timing_info(
        self,
        orchestrator_stub: AgentOrchestratorStub,
        halt_checker_normal: HaltCheckerStub,
        agent_pool: AgentPool,
    ) -> None:
        """Result includes timing information for metrics."""
        service = ConcurrentDeliberationService(
            orchestrator=orchestrator_stub,
            halt_checker=halt_checker_normal,
            pool=agent_pool,
        )

        requests = make_requests(10)
        result = await service.invoke_concurrent(requests)

        assert result.total_ms > 0
        assert result.started_at is not None
        assert result.completed_at is not None
        assert result.completed_at >= result.started_at

    @pytest.mark.asyncio
    async def test_result_includes_batch_id(
        self,
        orchestrator_stub: AgentOrchestratorStub,
        halt_checker_normal: HaltCheckerStub,
        agent_pool: AgentPool,
    ) -> None:
        """Each batch has unique identifier for tracking."""
        service = ConcurrentDeliberationService(
            orchestrator=orchestrator_stub,
            halt_checker=halt_checker_normal,
            pool=agent_pool,
        )

        requests = make_requests(5)
        result1 = await service.invoke_concurrent(requests)
        result2 = await service.invoke_concurrent(requests)

        assert result1.batch_id != result2.batch_id


class TestFailureReporting:
    """Test failure reporting (CT-11)."""

    @pytest.mark.asyncio
    async def test_failures_are_recorded_not_silent(
        self,
        halt_checker_normal: HaltCheckerStub,
        agent_pool: AgentPool,
    ) -> None:
        """Failed agents are recorded, not silently dropped (CT-11)."""
        orchestrator_stub = AgentOrchestratorStub(
            latency_ms=1,
            fail_agents={"archon-3", "archon-7"},
        )

        service = ConcurrentDeliberationService(
            orchestrator=orchestrator_stub,
            halt_checker=halt_checker_normal,
            pool=agent_pool,
        )

        requests = make_requests(10)
        result = await service.invoke_concurrent(requests)

        # Failures should be explicitly recorded
        assert result.failure_count == 2
        assert "archon-3" in result.failed_agents
        assert "archon-7" in result.failed_agents

        # Successes should be recorded
        assert result.success_count == 8

    @pytest.mark.asyncio
    async def test_all_failures_reported(
        self,
        halt_checker_normal: HaltCheckerStub,
        agent_pool: AgentPool,
    ) -> None:
        """Complete failure still reports all agents."""
        fail_agents = {f"archon-{i}" for i in range(10)}
        orchestrator_stub = AgentOrchestratorStub(
            latency_ms=1,
            fail_agents=fail_agents,
        )

        service = ConcurrentDeliberationService(
            orchestrator=orchestrator_stub,
            halt_checker=halt_checker_normal,
            pool=agent_pool,
        )

        requests = make_requests(10)
        result = await service.invoke_concurrent(requests)

        assert result.success_count == 0
        assert result.failure_count == 10
        assert len(result.failed_agents) == 10


class TestPoolStatusMonitoring:
    """Test pool status for operational monitoring."""

    @pytest.mark.asyncio
    async def test_get_pool_status_accurate(
        self,
        orchestrator_stub: AgentOrchestratorStub,
        halt_checker_normal: HaltCheckerStub,
        agent_pool: AgentPool,
    ) -> None:
        """Pool status accurately reflects current state."""
        service = ConcurrentDeliberationService(
            orchestrator=orchestrator_stub,
            halt_checker=halt_checker_normal,
            pool=agent_pool,
        )

        status = service.get_pool_status()

        assert status["active_count"] == 0
        assert status["available_count"] == 72
        assert status["max_concurrent"] == 72
