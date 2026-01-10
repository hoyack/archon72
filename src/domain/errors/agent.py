"""Agent-related domain errors for Archon 72 (Story 2.2).

Provides exception classes for agent pool and orchestration failures.
All exceptions inherit from ConclaveError.

Constitutional Constraints:
- FR10: 72 agents can deliberate concurrently without degradation
- CT-11: Silent failure destroys legitimacy -> report all failures
"""

from src.domain.exceptions import ConclaveError


class AgentPoolExhaustedError(ConclaveError):
    """Raised when the agent pool has no available capacity.

    This error indicates that the maximum number of concurrent agents
    (72 as per FR10) are already active and no new agents can be
    acquired.

    Constitutional Note:
        The 72-agent limit is a constitutional constant. This error
        should be rare in production as workload should be scheduled
        to respect this limit.

    Example:
        raise AgentPoolExhaustedError(
            "FR10: Agent pool exhausted - 72/72 agents active"
        )
    """

    pass


class AgentInvocationError(ConclaveError):
    """Raised when an agent invocation fails.

    This error indicates a failure during agent execution. Per CT-11,
    failures must never be silently ignored.

    Attributes captured in message should include:
    - Which agent failed (agent_id)
    - What type of failure occurred
    - Any relevant context

    Example:
        raise AgentInvocationError(
            "Agent archon-42 failed: Connection timeout after 30s"
        )
    """

    pass


class AgentNotFoundError(ConclaveError):
    """Raised when a requested agent is not found.

    This error indicates the agent_id does not correspond to any
    known agent in the pool.

    Example:
        raise AgentNotFoundError(
            "Agent archon-99 not found in pool"
        )
    """

    pass
