"""Agent Orchestrator port definition (Story 2.2, FR10).

Defines the abstract interface for agent orchestration. This port enables
72 concurrent agent deliberations as required by the Archon 72 Conclave.

Architecture Note (PM6-4):
This port was identified as a missing abstraction needed to complete
the portability boundary. Implementing this port allows:
- CrewAI to be replaced with other orchestration frameworks
- Testing without real LLM invocations
- Consistent interface for all agent operations

Constitutional Constraints:
- FR10: 72 agents can deliberate concurrently without degradation
- NFR5: 72 concurrent agent deliberations without degradation
- CT-11: Silent failure destroys legitimacy -> report all agent failures
- CT-12: Witnessing creates accountability -> all outputs through FR9 pipeline
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Callable
from uuid import UUID

# Re-export AgentStatus from domain layer for backward compatibility
from src.domain.models.agent_status import AgentStatus

__all__ = [
    "AgentStatus",
    "DeliberationMode",
    "ContextBundle",
    "AgentRequest",
    "AgentOutput",
    "AgentStatusInfo",
    "AgentOrchestratorProtocol",
    "DeliberationProgressCallback",
]


class DeliberationMode(Enum):
    """Mode for agent deliberation execution.

    PARALLEL: All agents deliberate concurrently (requires multi-GPU fleet).
              Best for: Production with ample GPU resources, time-critical decisions.

    SEQUENTIAL: Agents deliberate one at a time in round-robin fashion.
                Best for: Single GPU setups, accuracy over speed, testing.
                Supports model swapping between agents if needed.
    """

    PARALLEL = "parallel"
    SEQUENTIAL = "sequential"


# Type alias for progress callbacks during sequential deliberation
DeliberationProgressCallback = Callable[[int, int, str, str], None]


@dataclass(frozen=True, eq=True)
class ContextBundle:
    """Context bundle for agent invocation.

    Contains all the information an agent needs to perform deliberation.
    Context bundles are immutable and must be isolated per agent.

    Attributes:
        bundle_id: Unique identifier for this context bundle.
        topic_id: The deliberation topic ID.
        topic_content: The topic text/content for deliberation.
        metadata: Additional context metadata (optional).
        created_at: When this bundle was created.
    """

    bundle_id: UUID
    topic_id: str
    topic_content: str
    metadata: dict[str, str] | None
    created_at: datetime


@dataclass(frozen=True, eq=True)
class AgentRequest:
    """Request to invoke an agent for deliberation.

    Each request contains the agent identifier and the context
    bundle to process. Requests are immutable.

    Attributes:
        request_id: Unique identifier for this request.
        agent_id: The ID of the agent to invoke (e.g., "archon-1").
        context: The context bundle for the agent to process.
    """

    request_id: UUID
    agent_id: str
    context: ContextBundle


@dataclass(frozen=True, eq=True)
class AgentOutput:
    """Output from an agent deliberation.

    Contains the agent's deliberation output before FR9 commitment.
    This output must be passed through the FR9 pipeline before
    becoming viewable.

    Attributes:
        output_id: Unique identifier for this output.
        agent_id: The ID of the agent that produced the output.
        request_id: The ID of the request that triggered this output.
        content: The raw deliberation output content.
        content_type: MIME type of the content (e.g., "text/plain").
        generated_at: When the output was generated.
    """

    output_id: UUID
    agent_id: str
    request_id: UUID
    content: str
    content_type: str
    generated_at: datetime


@dataclass(frozen=True, eq=True)
class AgentStatusInfo:
    """Detailed status information for an agent.

    Attributes:
        agent_id: The ID of the agent.
        status: Current status of the agent.
        last_invocation: When the agent was last invoked.
        last_error: Last error message if status is FAILED.
    """

    agent_id: str
    status: AgentStatus
    last_invocation: datetime | None
    last_error: str | None


class AgentOrchestratorProtocol(ABC):
    """Abstract interface for agent orchestration.

    All agent orchestration implementations must implement this interface.
    This enables dependency inversion and allows the application layer
    to remain independent of specific orchestration implementations
    (e.g., CrewAI, LangChain, custom solutions).

    Constitutional Constraints:
    - FR10: Must support 72 concurrent agent instances
    - NFR5: No performance degradation with 72 concurrent agents
    - CT-11: Must report all failures, never silently drop agents
    - CT-12: All outputs must be traceable for FR9 pipeline

    Note:
        This port defines the abstract interface. Infrastructure adapters
        (e.g., CrewAIAdapter, AgentOrchestratorStub) implement this
        protocol with specific orchestration logic.
    """

    @abstractmethod
    async def invoke(
        self,
        agent_id: str,
        context: ContextBundle,
    ) -> AgentOutput:
        """Invoke a single agent with the given context.

        This method invokes one agent and waits for its output.
        The output must NOT be shown to humans before FR9 commitment.

        Args:
            agent_id: The ID of the agent to invoke (e.g., "archon-1").
            context: The context bundle for the agent to process.

        Returns:
            AgentOutput containing the agent's deliberation output.

        Raises:
            AgentInvocationError: If the agent fails to execute.
            SystemHaltedError: If the system is halted (caller should check).
        """
        ...

    @abstractmethod
    async def invoke_batch(
        self,
        requests: list[AgentRequest],
    ) -> list[AgentOutput]:
        """Invoke multiple agents concurrently.

        This method invokes multiple agents in parallel and returns
        all outputs. The implementation must ensure:
        - Context isolation between agents
        - No agent blocks another's execution
        - All failures are reported (CT-11: no silent drops)

        Args:
            requests: List of AgentRequest objects to process.

        Returns:
            List of AgentOutput objects in the same order as requests.

        Raises:
            AgentInvocationError: If any agent fails to execute.
                The error should include which agents failed.
            SystemHaltedError: If the system is halted (caller should check).
        """
        ...

    @abstractmethod
    async def invoke_sequential(
        self,
        requests: list[AgentRequest],
        on_progress: DeliberationProgressCallback | None = None,
    ) -> list[AgentOutput]:
        """Invoke multiple agents sequentially (round-robin deliberation).

        This method invokes agents one at a time, waiting for each to complete
        before moving to the next. This pattern is ideal for:
        - Single GPU deployments where model swapping may be needed
        - Accuracy-focused deliberations where time is not critical
        - Testing and development with limited resources

        The sequential pattern mirrors authentic constitutional deliberation
        where council members speak in turn rather than simultaneously.

        Args:
            requests: List of AgentRequest objects to process in order.
            on_progress: Optional callback invoked after each agent completes.
                         Signature: (current: int, total: int, agent_id: str, status: str)

        Returns:
            List of AgentOutput objects in the same order as requests.

        Raises:
            AgentInvocationError: If any agent fails to execute.
                Individual failures are logged but do not stop the sequence.
                The error includes which agents failed.
            SystemHaltedError: If the system is halted (caller should check).
        """
        ...

    @abstractmethod
    async def get_agent_status(
        self,
        agent_id: str,
    ) -> AgentStatusInfo:
        """Get the current status of an agent.

        Args:
            agent_id: The ID of the agent to query.

        Returns:
            AgentStatusInfo with the agent's current state.

        Raises:
            AgentNotFoundError: If the agent_id is not recognized.
        """
        ...
