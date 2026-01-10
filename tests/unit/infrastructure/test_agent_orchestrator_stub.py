"""Unit tests for AgentOrchestratorStub (Story 2.2, Task 4).

Tests:
- Stub invocation with simulated latency
- DEV MODE watermark in outputs
- Configurable failure for testing
- Status tracking
- Batch invocation

Constitutional Constraints:
- FR10: 72 agents can deliberate concurrently
- RT-1/ADR-4: Dev mode watermark pattern
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.application.ports.agent_orchestrator import (
    AgentOutput,
    AgentRequest,
    AgentStatus,
    ContextBundle,
)
from src.domain.errors.agent import AgentInvocationError
from src.infrastructure.stubs.agent_orchestrator_stub import (
    DEV_MODE_WATERMARK,
    AgentOrchestratorStub,
)


def make_context() -> ContextBundle:
    """Create a test context bundle."""
    return ContextBundle(
        bundle_id=uuid4(),
        topic_id="test-topic-123",
        topic_content="Test deliberation content",
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


class TestAgentOrchestratorStubInit:
    """Test stub initialization."""

    def test_default_initialization(self) -> None:
        """Stub initializes with default latency."""
        stub = AgentOrchestratorStub()

        assert stub._latency_ms == 100
        assert len(stub._fail_agents) == 0

    def test_custom_latency(self) -> None:
        """Stub accepts custom latency."""
        stub = AgentOrchestratorStub(latency_ms=50)

        assert stub._latency_ms == 50

    def test_custom_fail_agents(self) -> None:
        """Stub accepts fail_agents for testing."""
        stub = AgentOrchestratorStub(fail_agents={"archon-1", "archon-2"})

        assert "archon-1" in stub._fail_agents
        assert "archon-2" in stub._fail_agents


class TestAgentOrchestratorStubInvoke:
    """Test invoke method."""

    @pytest.mark.asyncio
    async def test_invoke_returns_output(self) -> None:
        """Invoke returns AgentOutput."""
        stub = AgentOrchestratorStub(latency_ms=0)  # No delay for fast tests
        context = make_context()

        output = await stub.invoke("archon-1", context)

        assert isinstance(output, AgentOutput)
        assert output.agent_id == "archon-1"

    @pytest.mark.asyncio
    async def test_invoke_includes_dev_mode_watermark(self) -> None:
        """Output includes DEV MODE watermark (RT-1/ADR-4)."""
        stub = AgentOrchestratorStub(latency_ms=0)
        context = make_context()

        output = await stub.invoke("archon-1", context)

        assert DEV_MODE_WATERMARK in output.content
        assert output.content.startswith(DEV_MODE_WATERMARK)

    @pytest.mark.asyncio
    async def test_invoke_includes_topic_in_output(self) -> None:
        """Output references the topic."""
        stub = AgentOrchestratorStub(latency_ms=0)
        context = make_context()

        output = await stub.invoke("archon-1", context)

        assert context.topic_id in output.content

    @pytest.mark.asyncio
    async def test_invoke_content_type_is_text_plain(self) -> None:
        """Output has text/plain content type."""
        stub = AgentOrchestratorStub(latency_ms=0)
        context = make_context()

        output = await stub.invoke("archon-1", context)

        assert output.content_type == "text/plain"

    @pytest.mark.asyncio
    async def test_invoke_increments_count(self) -> None:
        """Invocation count increases."""
        stub = AgentOrchestratorStub(latency_ms=0)
        context = make_context()

        assert stub.get_invocation_count() == 0

        await stub.invoke("archon-1", context)
        assert stub.get_invocation_count() == 1

        await stub.invoke("archon-2", context)
        assert stub.get_invocation_count() == 2

    @pytest.mark.asyncio
    async def test_invoke_fails_for_configured_agent(self) -> None:
        """Invoke raises error for agents in fail_agents set."""
        stub = AgentOrchestratorStub(
            latency_ms=0,
            fail_agents={"archon-fail"},
        )
        context = make_context()

        with pytest.raises(AgentInvocationError, match="archon-fail"):
            await stub.invoke("archon-fail", context)

    @pytest.mark.asyncio
    async def test_invoke_updates_status(self) -> None:
        """Invoke updates agent status."""
        stub = AgentOrchestratorStub(latency_ms=0)
        context = make_context()

        await stub.invoke("archon-1", context)

        status = await stub.get_agent_status("archon-1")
        assert status.status == AgentStatus.IDLE
        assert status.last_invocation is not None
        assert status.last_error is None


class TestAgentOrchestratorStubInvokeBatch:
    """Test invoke_batch method."""

    @pytest.mark.asyncio
    async def test_invoke_batch_returns_all_outputs(self) -> None:
        """Batch invocation returns all outputs."""
        stub = AgentOrchestratorStub(latency_ms=0)
        requests = [make_request(f"archon-{i}") for i in range(3)]

        outputs = await stub.invoke_batch(requests)

        assert len(outputs) == 3
        assert all(isinstance(o, AgentOutput) for o in outputs)

    @pytest.mark.asyncio
    async def test_invoke_batch_all_have_watermark(self) -> None:
        """All batch outputs have DEV MODE watermark."""
        stub = AgentOrchestratorStub(latency_ms=0)
        requests = [make_request(f"archon-{i}") for i in range(3)]

        outputs = await stub.invoke_batch(requests)

        for output in outputs:
            assert DEV_MODE_WATERMARK in output.content

    @pytest.mark.asyncio
    async def test_invoke_batch_fails_if_any_agent_fails(self) -> None:
        """Batch raises error if any agent fails."""
        stub = AgentOrchestratorStub(
            latency_ms=0,
            fail_agents={"archon-1"},
        )
        requests = [
            make_request("archon-0"),
            make_request("archon-1"),  # This one fails
            make_request("archon-2"),
        ]

        with pytest.raises(AgentInvocationError, match="failures"):
            await stub.invoke_batch(requests)


class TestAgentOrchestratorStubGetStatus:
    """Test get_agent_status method."""

    @pytest.mark.asyncio
    async def test_status_unknown_for_new_agent(self) -> None:
        """Unknown agents return UNKNOWN status."""
        stub = AgentOrchestratorStub()

        status = await stub.get_agent_status("archon-never-seen")

        assert status.status == AgentStatus.UNKNOWN
        assert status.last_invocation is None

    @pytest.mark.asyncio
    async def test_status_idle_after_successful_invoke(self) -> None:
        """Status is IDLE after successful invocation."""
        stub = AgentOrchestratorStub(latency_ms=0)
        await stub.invoke("archon-1", make_context())

        status = await stub.get_agent_status("archon-1")

        assert status.status == AgentStatus.IDLE

    @pytest.mark.asyncio
    async def test_status_failed_after_failed_invoke(self) -> None:
        """Status is FAILED after failed invocation."""
        stub = AgentOrchestratorStub(
            latency_ms=0,
            fail_agents={"archon-fail"},
        )

        try:
            await stub.invoke("archon-fail", make_context())
        except AgentInvocationError:
            pass

        status = await stub.get_agent_status("archon-fail")

        assert status.status == AgentStatus.FAILED
        assert status.last_error is not None


class TestAgentOrchestratorStubHelpers:
    """Test helper methods for testing."""

    def test_set_latency(self) -> None:
        """set_latency changes latency."""
        stub = AgentOrchestratorStub(latency_ms=100)

        stub.set_latency(50)

        assert stub._latency_ms == 50

    def test_set_fail_agents(self) -> None:
        """set_fail_agents replaces fail set."""
        stub = AgentOrchestratorStub(fail_agents={"archon-1"})

        stub.set_fail_agents({"archon-2", "archon-3"})

        assert "archon-1" not in stub._fail_agents
        assert "archon-2" in stub._fail_agents
        assert "archon-3" in stub._fail_agents

    def test_add_fail_agent(self) -> None:
        """add_fail_agent adds to fail set."""
        stub = AgentOrchestratorStub()

        stub.add_fail_agent("archon-fail")

        assert "archon-fail" in stub._fail_agents

    def test_remove_fail_agent(self) -> None:
        """remove_fail_agent removes from fail set."""
        stub = AgentOrchestratorStub(fail_agents={"archon-1", "archon-2"})

        stub.remove_fail_agent("archon-1")

        assert "archon-1" not in stub._fail_agents
        assert "archon-2" in stub._fail_agents

    @pytest.mark.asyncio
    async def test_reset_stats(self) -> None:
        """reset_stats clears all tracking."""
        stub = AgentOrchestratorStub(latency_ms=0)
        await stub.invoke("archon-1", make_context())

        stub.reset_stats()

        assert stub.get_invocation_count() == 0
        status = await stub.get_agent_status("archon-1")
        assert status.status == AgentStatus.UNKNOWN


class TestDevModeWatermarkConstant:
    """Test DEV_MODE_WATERMARK constant."""

    def test_watermark_is_dev_mode(self) -> None:
        """Watermark contains 'DEV MODE'."""
        assert "DEV MODE" in DEV_MODE_WATERMARK

    def test_watermark_exported_from_module(self) -> None:
        """Watermark is importable."""
        from src.infrastructure.stubs.agent_orchestrator_stub import DEV_MODE_WATERMARK

        assert DEV_MODE_WATERMARK is not None


class TestAgentOrchestratorStubInvokeSequential:
    """Test invoke_sequential method (sequential round-robin deliberation)."""

    @pytest.mark.asyncio
    async def test_invoke_sequential_returns_all_outputs(self) -> None:
        """Sequential invocation returns all outputs."""
        stub = AgentOrchestratorStub(latency_ms=0)
        requests = [make_request(f"archon-{i}") for i in range(5)]

        outputs = await stub.invoke_sequential(requests)

        assert len(outputs) == 5
        assert all(isinstance(o, AgentOutput) for o in outputs)

    @pytest.mark.asyncio
    async def test_invoke_sequential_all_have_watermark(self) -> None:
        """All sequential outputs have DEV MODE watermark."""
        stub = AgentOrchestratorStub(latency_ms=0)
        requests = [make_request(f"archon-{i}") for i in range(3)]

        outputs = await stub.invoke_sequential(requests)

        for output in outputs:
            assert DEV_MODE_WATERMARK in output.content

    @pytest.mark.asyncio
    async def test_invoke_sequential_continues_on_failure(self) -> None:
        """Sequential continues to next agent if one fails."""
        stub = AgentOrchestratorStub(
            latency_ms=0,
            fail_agents={"archon-1"},  # archon-1 will fail
        )
        requests = [
            make_request("archon-0"),
            make_request("archon-1"),  # This one fails
            make_request("archon-2"),
        ]

        # Should not raise - continues processing
        outputs = await stub.invoke_sequential(requests)

        # Should have 2 successful outputs (archon-0 and archon-2)
        assert len(outputs) == 2
        agent_ids = {o.agent_id for o in outputs}
        assert "archon-0" in agent_ids
        assert "archon-2" in agent_ids
        assert "archon-1" not in agent_ids

    @pytest.mark.asyncio
    async def test_invoke_sequential_raises_if_all_fail(self) -> None:
        """Sequential raises error only if ALL agents fail."""
        stub = AgentOrchestratorStub(
            latency_ms=0,
            fail_agents={"archon-0", "archon-1", "archon-2"},
        )
        requests = [
            make_request("archon-0"),
            make_request("archon-1"),
            make_request("archon-2"),
        ]

        with pytest.raises(AgentInvocationError, match="all.*failed"):
            await stub.invoke_sequential(requests)

    @pytest.mark.asyncio
    async def test_invoke_sequential_progress_callback(self) -> None:
        """Sequential calls progress callback for each agent."""
        stub = AgentOrchestratorStub(latency_ms=0)
        requests = [make_request(f"archon-{i}") for i in range(3)]

        progress_calls: list[tuple[int, int, str, str]] = []

        def track_progress(current: int, total: int, agent_id: str, status: str) -> None:
            progress_calls.append((current, total, agent_id, status))

        await stub.invoke_sequential(requests, on_progress=track_progress)

        # Should have 6 calls: starting + completed for each of 3 agents
        assert len(progress_calls) == 6

        # Check first agent's progress
        assert progress_calls[0] == (1, 3, "archon-0", "starting")
        assert progress_calls[1] == (1, 3, "archon-0", "completed")

        # Check last agent's progress
        assert progress_calls[4] == (3, 3, "archon-2", "starting")
        assert progress_calls[5] == (3, 3, "archon-2", "completed")

    @pytest.mark.asyncio
    async def test_invoke_sequential_progress_callback_on_failure(self) -> None:
        """Progress callback reports 'failed' status on agent failure."""
        stub = AgentOrchestratorStub(
            latency_ms=0,
            fail_agents={"archon-1"},
        )
        requests = [
            make_request("archon-0"),
            make_request("archon-1"),  # Will fail
            make_request("archon-2"),
        ]

        progress_calls: list[tuple[int, int, str, str]] = []

        def track_progress(current: int, total: int, agent_id: str, status: str) -> None:
            progress_calls.append((current, total, agent_id, status))

        await stub.invoke_sequential(requests, on_progress=track_progress)

        # archon-1 should have "failed" status
        archon_1_statuses = [
            status for (_, _, agent_id, status) in progress_calls
            if agent_id == "archon-1"
        ]
        assert "starting" in archon_1_statuses
        assert "failed" in archon_1_statuses

    @pytest.mark.asyncio
    async def test_invoke_sequential_72_agents(self) -> None:
        """Sequential can process 72 agents (FR10 compliance)."""
        stub = AgentOrchestratorStub(latency_ms=0)
        requests = [make_request(f"archon-{i}") for i in range(72)]

        outputs = await stub.invoke_sequential(requests)

        assert len(outputs) == 72

    @pytest.mark.asyncio
    async def test_invoke_sequential_empty_requests(self) -> None:
        """Sequential handles empty request list."""
        stub = AgentOrchestratorStub(latency_ms=0)

        outputs = await stub.invoke_sequential([])

        assert outputs == []


class TestExportedFromPackage:
    """Test stub is exported from package."""

    def test_stub_exported_from_stubs_package(self) -> None:
        """AgentOrchestratorStub exported from infrastructure.stubs."""
        from src.infrastructure.stubs import AgentOrchestratorStub

        assert AgentOrchestratorStub is not None
