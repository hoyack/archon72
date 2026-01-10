"""Stub Agent Orchestrator for Story 2.2 - simulates agent invocation.

This stub allows testing and development without requiring a real LLM/CrewAI.

Pattern (RT-1/ADR-4):
All outputs include [DEV MODE] watermark prefix to distinguish from
production outputs, following the same pattern as DevHSM.

WARNING: This stub is for development/testing only.
Production must use the real CrewAI adapter.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from uuid import uuid4

from structlog import get_logger

from src.application.ports.agent_orchestrator import (
    AgentOrchestratorProtocol,
    AgentOutput,
    AgentRequest,
    AgentStatus,
    AgentStatusInfo,
    ContextBundle,
)
from src.domain.errors.agent import AgentInvocationError

logger = get_logger()

# Dev mode watermark prefix (matches DevHSM pattern)
DEV_MODE_WATERMARK = "[DEV MODE] "


class AgentOrchestratorStub(AgentOrchestratorProtocol):
    """Stub implementation of agent orchestration for development.

    WARNING: NOT FOR PRODUCTION USE.

    This implementation:
    - Simulates agent deliberation with configurable latency
    - Returns deterministic outputs for testing
    - Includes [DEV MODE] watermark in all outputs
    - Logs warnings about stub usage
    - Tracks agent status for testing

    AC1 (partial): Simulates 72 concurrent agent support via async
    AC2 (partial): No real blocking - all async with configurable delay

    Attributes:
        _latency_ms: Simulated latency per invocation in milliseconds.
        _fail_agents: Set of agent IDs that should fail (for testing).
        _agent_status: Dictionary tracking agent status.
        _invocation_count: Total invocations for metrics.
    """

    def __init__(
        self,
        latency_ms: int = 100,
        fail_agents: set[str] | None = None,
    ) -> None:
        """Initialize the stub orchestrator.

        Args:
            latency_ms: Simulated latency in milliseconds (default 100ms).
            fail_agents: Set of agent IDs that should fail (for testing).
        """
        self._latency_ms = latency_ms
        self._fail_agents = fail_agents or set()
        self._agent_status: dict[str, AgentStatusInfo] = {}
        self._invocation_count = 0

        # Log warning about stub usage
        logger.warning(
            "agent_orchestrator_stub_active",
            message="Using stub agent orchestrator - NOT FOR PRODUCTION",
            latency_ms=latency_ms,
        )

    async def invoke(
        self,
        agent_id: str,
        context: ContextBundle,
    ) -> AgentOutput:
        """Stub: Simulate agent invocation with delay.

        Simulates a real agent invocation by waiting for the configured
        latency, then returning a deterministic output with DEV MODE watermark.

        Args:
            agent_id: The ID of the agent to invoke.
            context: The context bundle for the agent.

        Returns:
            AgentOutput with simulated deliberation output.

        Raises:
            AgentInvocationError: If agent_id is in fail_agents set.
        """
        self._invocation_count += 1

        # Update status to BUSY
        self._agent_status[agent_id] = AgentStatusInfo(
            agent_id=agent_id,
            status=AgentStatus.BUSY,
            last_invocation=datetime.now(timezone.utc),
            last_error=None,
        )

        # Simulate latency (non-blocking)
        await asyncio.sleep(self._latency_ms / 1000.0)

        # Check if this agent should fail (for testing error handling)
        if agent_id in self._fail_agents:
            self._agent_status[agent_id] = AgentStatusInfo(
                agent_id=agent_id,
                status=AgentStatus.FAILED,
                last_invocation=datetime.now(timezone.utc),
                last_error=f"Stub: Agent {agent_id} configured to fail",
            )
            raise AgentInvocationError(
                f"Stub: Agent {agent_id} configured to fail for testing"
            )

        # Generate deterministic output with DEV MODE watermark
        output_id = uuid4()
        content = (
            f"{DEV_MODE_WATERMARK}"
            f"Deliberation output from {agent_id} "
            f"regarding topic '{context.topic_id}': "
            f"[STUB RESPONSE - This is a simulated output for development. "
            f"In production, this would contain actual agent deliberation.]"
        )

        # Update status to IDLE
        self._agent_status[agent_id] = AgentStatusInfo(
            agent_id=agent_id,
            status=AgentStatus.IDLE,
            last_invocation=datetime.now(timezone.utc),
            last_error=None,
        )

        logger.debug(
            "stub_agent_invoked",
            agent_id=agent_id,
            topic_id=context.topic_id,
            latency_ms=self._latency_ms,
            output_id=str(output_id),
        )

        return AgentOutput(
            output_id=output_id,
            agent_id=agent_id,
            request_id=context.bundle_id,  # Use bundle_id as request tracking
            content=content,
            content_type="text/plain",
            generated_at=datetime.now(timezone.utc),
        )

    async def invoke_batch(
        self,
        requests: list[AgentRequest],
    ) -> list[AgentOutput]:
        """Stub: Simulate batch invocation with concurrent execution.

        Invokes all agents concurrently using asyncio.gather.

        Args:
            requests: List of AgentRequest objects.

        Returns:
            List of AgentOutput objects in same order as requests.

        Raises:
            AgentInvocationError: If any agent fails.
        """
        logger.info(
            "stub_batch_invocation_started",
            agent_count=len(requests),
        )

        # Execute all invocations concurrently
        outputs = await asyncio.gather(
            *[
                self.invoke(req.agent_id, req.context)
                for req in requests
            ],
            return_exceptions=True,
        )

        # Process results
        results: list[AgentOutput] = []
        errors: list[str] = []

        for i, output in enumerate(outputs):
            if isinstance(output, BaseException):
                errors.append(f"{requests[i].agent_id}: {output}")
            elif isinstance(output, AgentOutput):
                results.append(output)

        if errors:
            error_msg = f"Batch invocation had {len(errors)} failures: {errors[:3]}"
            logger.warning("stub_batch_partial_failure", errors=errors[:5])
            raise AgentInvocationError(error_msg)

        logger.info(
            "stub_batch_invocation_complete",
            success_count=len(results),
        )

        return results

    async def get_agent_status(
        self,
        agent_id: str,
    ) -> AgentStatusInfo:
        """Stub: Return tracked agent status.

        Args:
            agent_id: The ID of the agent to query.

        Returns:
            AgentStatusInfo for the agent.

        Raises:
            AgentNotFoundError: If agent has never been invoked.
        """
        if agent_id not in self._agent_status:
            # Return UNKNOWN for agents we haven't seen
            return AgentStatusInfo(
                agent_id=agent_id,
                status=AgentStatus.UNKNOWN,
                last_invocation=None,
                last_error=None,
            )

        return self._agent_status[agent_id]

    # Test helper methods

    def set_latency(self, latency_ms: int) -> None:
        """Test helper: Change simulated latency.

        Args:
            latency_ms: New latency in milliseconds.
        """
        self._latency_ms = latency_ms

    def set_fail_agents(self, agent_ids: set[str]) -> None:
        """Test helper: Set agents that should fail.

        Args:
            agent_ids: Set of agent IDs that should raise errors.
        """
        self._fail_agents = agent_ids

    def add_fail_agent(self, agent_id: str) -> None:
        """Test helper: Add a single agent to fail set.

        Args:
            agent_id: Agent ID to add to fail set.
        """
        self._fail_agents.add(agent_id)

    def remove_fail_agent(self, agent_id: str) -> None:
        """Test helper: Remove an agent from fail set.

        Args:
            agent_id: Agent ID to remove from fail set.
        """
        self._fail_agents.discard(agent_id)

    def get_invocation_count(self) -> int:
        """Test helper: Get total invocation count.

        Returns:
            Number of times invoke() was called.
        """
        return self._invocation_count

    def reset_stats(self) -> None:
        """Test helper: Reset all statistics and status tracking."""
        self._agent_status.clear()
        self._invocation_count = 0
        logger.debug("stub_stats_reset")
