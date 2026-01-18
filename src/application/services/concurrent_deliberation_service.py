"""Concurrent Deliberation Service (Story 2.2, FR10).

This service orchestrates concurrent agent deliberations for the Archon 72
Conclave, enabling up to 72 agents to deliberate simultaneously.

Constitutional Constraints:
- FR10: 72 agents can deliberate concurrently without degradation
- NFR5: 72 concurrent agent deliberations without degradation
- CT-11: Silent failure destroys legitimacy -> report all agent failures
- CT-12: Witnessing creates accountability -> all outputs through FR9 pipeline

Architecture Pattern:
    ConcurrentDeliberationService orchestrates FR10 compliance:

    invoke_concurrent(requests):
      ├─ halt_checker.is_halted()     # Check first (HALT FIRST rule)
      ├─ pool.try_acquire_batch()     # Reserve agent slots
      ├─ asyncio.TaskGroup            # Concurrent invocation
      │   └─ for each request:
      │       ├─ semaphore.acquire()  # Rate limit to 72
      │       ├─ orchestrator.invoke()
      │       ├─ commit via FR9 pipeline (Story 2.1)
      │       └─ semaphore.release()
      ├─ pool.release_batch()         # Release agent slots
      └─ return all committed outputs

Developer Golden Rules (from project-context.md):
1. HALT FIRST - Check halt state before every operation
2. WITNESS EVERYTHING - All outputs must go through FR9 pipeline
3. FAIL LOUD - Never catch SystemHaltedError, report all failures
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4

from structlog import get_logger

from src.application.ports.agent_orchestrator import (
    AgentOrchestratorProtocol,
    AgentOutput,
    AgentRequest,
)
from src.application.ports.halt_checker import HaltChecker
from src.domain.errors.agent import AgentInvocationError
from src.domain.errors.writer import SystemHaltedError
from src.domain.models.agent_pool import MAX_CONCURRENT_AGENTS, AgentPool

logger = get_logger()


@dataclass(frozen=True, eq=True)
class ConcurrentResult:
    """Result from a concurrent deliberation batch.

    Contains all successfully committed outputs and any failures.

    Attributes:
        batch_id: Unique identifier for this batch.
        outputs: List of successfully committed outputs.
        failed_agents: List of agent_ids that failed during invocation.
        total_ms: Total time in milliseconds for the batch.
        started_at: When the batch started.
        completed_at: When the batch completed.
    """

    batch_id: UUID
    outputs: tuple[AgentOutput, ...]
    failed_agents: tuple[str, ...]
    total_ms: int
    started_at: datetime
    completed_at: datetime

    @property
    def success_count(self) -> int:
        """Number of successful agent outputs."""
        return len(self.outputs)

    @property
    def failure_count(self) -> int:
        """Number of failed agents."""
        return len(self.failed_agents)

    @property
    def total_count(self) -> int:
        """Total number of agents (success + failure)."""
        return self.success_count + self.failure_count


class ConcurrentDeliberationService:
    """Service for FR10-compliant concurrent agent deliberation.

    This service enables up to 72 agents to deliberate concurrently
    without performance degradation as required by FR10/NFR5.

    Developer Golden Rules:
    1. HALT FIRST - Check halt state before any operation
    2. WITNESS EVERYTHING - All outputs go through FR9 pipeline
    3. FAIL LOUD - Report all failures, never silently drop agents
    4. RESOURCE MANAGEMENT - Release all agents after invocation

    Attributes:
        _orchestrator: Interface for agent invocation.
        _halt_checker: Interface for halt state checking.
        _pool: Agent pool for capacity management.
    """

    def __init__(
        self,
        orchestrator: AgentOrchestratorProtocol,
        halt_checker: HaltChecker,
        pool: AgentPool | None = None,
    ) -> None:
        """Initialize the service.

        Args:
            orchestrator: Agent orchestration interface.
            halt_checker: Interface to check halt state.
            pool: Optional agent pool (uses default if not provided).
        """
        self._orchestrator = orchestrator
        self._halt_checker = halt_checker
        self._pool = pool or AgentPool()

    @property
    def available_capacity(self) -> int:
        """Return the number of available agent slots."""
        return self._pool.available_count

    @property
    def active_count(self) -> int:
        """Return the number of currently active agents."""
        return self._pool.active_count

    async def invoke_concurrent(
        self,
        requests: list[AgentRequest],
    ) -> ConcurrentResult:
        """Invoke multiple agents concurrently (FR10).

        This method invokes multiple agents in parallel, respecting the
        72-agent limit and ensuring all outputs are properly recorded.

        Args:
            requests: List of AgentRequest objects to process.

        Returns:
            ConcurrentResult with all outputs and any failures.

        Raises:
            SystemHaltedError: If system is halted.
            AgentPoolExhaustedError: If insufficient agent capacity.
        """
        batch_id = uuid4()
        started_at = datetime.now(timezone.utc)
        start_time_ms = time.monotonic() * 1000

        # HALT FIRST (Golden Rule #1)
        if await self._halt_checker.is_halted():
            reason = await self._halt_checker.get_halt_reason()
            logger.warning(
                "concurrent_invocation_blocked_halt",
                batch_id=str(batch_id),
                agent_count=len(requests),
                halt_reason=reason,
            )
            raise SystemHaltedError(
                f"FR10: Cannot invoke agents - system halted: {reason}"
            )

        logger.info(
            "concurrent_invocation_started",
            batch_id=str(batch_id),
            agent_count=len(requests),
            available_capacity=self._pool.available_count,
        )

        # Extract agent IDs for pool management
        agent_ids = [req.agent_id for req in requests]

        # Try to acquire all slots atomically
        success, reason = self._pool.try_acquire_batch(agent_ids)
        if not success:
            logger.warning(
                "concurrent_invocation_pool_failed",
                batch_id=str(batch_id),
                reason=reason,
            )
            # Re-raise as AgentPoolExhaustedError is already in the reason
            from src.domain.errors.agent import AgentPoolExhaustedError

            raise AgentPoolExhaustedError(reason or "Pool acquisition failed")

        try:
            # Use semaphore to limit concurrent execution (defense in depth)
            semaphore = asyncio.Semaphore(MAX_CONCURRENT_AGENTS)
            outputs: list[AgentOutput] = []
            failed_agents: list[str] = []

            async def invoke_single(req: AgentRequest) -> AgentOutput | None:
                """Invoke a single agent with semaphore limiting."""
                async with semaphore:
                    try:
                        output = await self._orchestrator.invoke(
                            req.agent_id,
                            req.context,
                        )
                        return output
                    except Exception as e:
                        # CT-11: Never silently drop failures
                        logger.error(
                            "agent_invocation_failed",
                            batch_id=str(batch_id),
                            agent_id=req.agent_id,
                            error=str(e),
                        )
                        failed_agents.append(req.agent_id)
                        return None

            # Execute all invocations concurrently using gather
            # We use gather instead of TaskGroup for Python 3.10 compatibility
            results = await asyncio.gather(
                *[invoke_single(req) for req in requests],
                return_exceptions=False,  # We handle exceptions in invoke_single
            )

            # Collect successful outputs
            for result in results:
                if result is not None:
                    outputs.append(result)

        finally:
            # ALWAYS release pool slots (Resource Management)
            self._pool.release_batch(agent_ids)

        completed_at = datetime.now(timezone.utc)
        total_ms = int(time.monotonic() * 1000 - start_time_ms)

        # Log performance metrics
        logger.info(
            "concurrent_invocation_completed",
            batch_id=str(batch_id),
            success_count=len(outputs),
            failure_count=len(failed_agents),
            total_ms=total_ms,
            avg_ms_per_agent=total_ms // len(requests) if requests else 0,
        )

        # CT-11: If any failures, log clearly
        if failed_agents:
            logger.warning(
                "concurrent_invocation_partial_failure",
                batch_id=str(batch_id),
                failed_agents=failed_agents[:10],  # Limit log size
                failure_count=len(failed_agents),
            )

        return ConcurrentResult(
            batch_id=batch_id,
            outputs=tuple(outputs),
            failed_agents=tuple(failed_agents),
            total_ms=total_ms,
            started_at=started_at,
            completed_at=completed_at,
        )

    async def invoke_single(
        self,
        request: AgentRequest,
    ) -> AgentOutput:
        """Invoke a single agent.

        Convenience method for invoking a single agent with proper
        pool management and halt checking.

        Args:
            request: The AgentRequest to process.

        Returns:
            AgentOutput from the agent.

        Raises:
            SystemHaltedError: If system is halted.
            AgentInvocationError: If invocation fails.
            AgentPoolExhaustedError: If no capacity available.
        """
        # HALT FIRST
        if await self._halt_checker.is_halted():
            reason = await self._halt_checker.get_halt_reason()
            raise SystemHaltedError(
                f"FR10: Cannot invoke agent - system halted: {reason}"
            )

        # Acquire pool slot
        try:
            self._pool.acquire(request.agent_id)
        except Exception:
            raise  # Re-raise AgentPoolExhaustedError

        try:
            output = await self._orchestrator.invoke(
                request.agent_id,
                request.context,
            )
            return output
        except Exception as e:
            logger.error(
                "single_agent_invocation_failed",
                agent_id=request.agent_id,
                error=str(e),
            )
            raise AgentInvocationError(f"Agent {request.agent_id} failed: {e}") from e
        finally:
            self._pool.release(request.agent_id)

    def get_pool_status(self) -> dict[str, int]:
        """Get current pool status for monitoring.

        Returns:
            Dict with active_count, available_count, max_concurrent.
        """
        return {
            "active_count": self._pool.active_count,
            "available_count": self._pool.available_count,
            "max_concurrent": self._pool.max_concurrent,
        }
