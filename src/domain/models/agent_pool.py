"""Agent Pool domain model for Archon 72 (Story 2.2, FR10).

Manages the pool of 72 concurrent agent slots. This is a domain model
that tracks which agents are currently active.

Constitutional Constraints:
- FR10: 72 agents can deliberate concurrently without degradation
- NFR5: 72 concurrent agent deliberations without degradation
- CT-11: Silent failure destroys legitimacy -> track all acquisitions

Note:
    This domain model uses mutable state intentionally because the pool
    represents transient runtime state, not persisted constitutional state.
    The pool is NOT frozen because agents are acquired and released.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from structlog import get_logger

from src.domain.errors.agent import AgentPoolExhaustedError

logger = get_logger()

# Constitutional constant: Maximum concurrent agents (FR10)
MAX_CONCURRENT_AGENTS: int = 72


@dataclass
class AgentPool:
    """Pool of concurrent agent slots.

    Manages the 72 concurrent agent slots as required by FR10.
    Agents must be acquired before invocation and released after.

    Note:
        This is a mutable domain model because it tracks transient
        runtime state. Use thread-safe patterns (asyncio locks) when
        using in concurrent contexts.

    Attributes:
        max_concurrent: Maximum number of concurrent agents (default 72).
        _active_agents: Set of currently active agent IDs.
    """

    max_concurrent: int = MAX_CONCURRENT_AGENTS
    _active_agents: set[str] = field(default_factory=set)

    @property
    def active_count(self) -> int:
        """Return the number of currently active agents."""
        return len(self._active_agents)

    @property
    def available_count(self) -> int:
        """Return the number of available agent slots."""
        return self.max_concurrent - self.active_count

    @property
    def is_exhausted(self) -> bool:
        """Return True if no agent slots are available."""
        return self.active_count >= self.max_concurrent

    @property
    def active_agents(self) -> frozenset[str]:
        """Return immutable view of currently active agent IDs."""
        return frozenset(self._active_agents)

    def acquire(self, agent_id: str) -> bool:
        """Acquire a slot for the given agent.

        This method attempts to acquire a slot in the pool for the
        specified agent. If the agent is already active or the pool
        is exhausted, appropriate action is taken.

        Args:
            agent_id: The ID of the agent to acquire a slot for.

        Returns:
            True if the slot was acquired, False if agent already active.

        Raises:
            AgentPoolExhaustedError: If the pool has no available slots.
        """
        # Check if already active (idempotent - return success)
        if agent_id in self._active_agents:
            logger.debug(
                "agent_already_active",
                agent_id=agent_id,
            )
            return False

        # Check capacity
        if self.is_exhausted:
            logger.warning(
                "agent_pool_exhausted",
                agent_id=agent_id,
                active_count=self.active_count,
                max_concurrent=self.max_concurrent,
            )
            raise AgentPoolExhaustedError(
                f"FR10: Agent pool exhausted - {self.active_count}/"
                f"{self.max_concurrent} agents active"
            )

        # Acquire slot
        self._active_agents.add(agent_id)
        logger.debug(
            "agent_acquired",
            agent_id=agent_id,
            active_count=self.active_count,
        )
        return True

    def release(self, agent_id: str) -> bool:
        """Release the slot for the given agent.

        This method releases the slot held by the specified agent,
        making it available for reuse.

        Args:
            agent_id: The ID of the agent to release.

        Returns:
            True if the slot was released, False if agent was not active.
        """
        if agent_id not in self._active_agents:
            logger.debug(
                "agent_not_active",
                agent_id=agent_id,
            )
            return False

        self._active_agents.discard(agent_id)
        logger.debug(
            "agent_released",
            agent_id=agent_id,
            active_count=self.active_count,
        )
        return True

    def is_active(self, agent_id: str) -> bool:
        """Check if an agent is currently active.

        Args:
            agent_id: The ID of the agent to check.

        Returns:
            True if the agent is active, False otherwise.
        """
        return agent_id in self._active_agents

    def reset(self) -> int:
        """Reset the pool, releasing all agents.

        This is primarily for testing. In production, agents should
        be released individually.

        Returns:
            The number of agents that were released.
        """
        released_count = len(self._active_agents)
        self._active_agents.clear()
        logger.info(
            "agent_pool_reset",
            released_count=released_count,
        )
        return released_count

    def try_acquire_batch(self, agent_ids: list[str]) -> tuple[bool, str | None]:
        """Attempt to acquire slots for multiple agents atomically.

        Either all agents are acquired or none are. This prevents
        partial allocations.

        Args:
            agent_ids: List of agent IDs to acquire slots for.

        Returns:
            Tuple of (success, first_failure_reason).
            If success is False, first_failure_reason explains why.
        """
        # Check if any agents are already active
        already_active = [aid for aid in agent_ids if aid in self._active_agents]
        if already_active:
            return (False, f"Agents already active: {already_active[:3]}...")

        # Check capacity for all agents
        unique_agents = set(agent_ids)
        if self.active_count + len(unique_agents) > self.max_concurrent:
            return (
                False,
                f"FR10: Would exceed pool capacity "
                f"({self.active_count} + {len(unique_agents)} > {self.max_concurrent})",
            )

        # Acquire all
        for agent_id in unique_agents:
            self._active_agents.add(agent_id)

        logger.info(
            "batch_agents_acquired",
            agent_count=len(unique_agents),
            active_count=self.active_count,
        )
        return (True, None)

    def release_batch(self, agent_ids: list[str]) -> int:
        """Release slots for multiple agents.

        Args:
            agent_ids: List of agent IDs to release.

        Returns:
            Number of agents actually released (excludes those not active).
        """
        released_count = 0
        for agent_id in agent_ids:
            if agent_id in self._active_agents:
                self._active_agents.discard(agent_id)
                released_count += 1

        logger.info(
            "batch_agents_released",
            released_count=released_count,
            active_count=self.active_count,
        )
        return released_count
