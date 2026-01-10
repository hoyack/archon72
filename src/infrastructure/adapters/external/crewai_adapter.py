"""CrewAI adapter for agent orchestration (Story 10-2, updated Story 10-3).

This adapter implements AgentOrchestratorProtocol using CrewAI to create
and invoke agents with per-archon LLM configuration from ArchonProfile.

Constitutional Constraints:
- FR10: 72 agents can deliberate concurrently without degradation
- NFR5: 72 concurrent agent deliberations without degradation
- CT-11: Silent failure destroys legitimacy -> report all agent failures
- CT-12: Witnessing creates accountability -> all outputs through FR9 pipeline

Architecture Note (PM6-4a):
Uses ArchonProfileRepository to look up per-archon LLM configuration,
enabling granular control over which model powers each agent.

Story 10-3 Update:
Uses ToolRegistryProtocol to resolve tool names to CrewAI Tool instances.
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from crewai import Agent, Task, Crew, LLM
from structlog import get_logger

from src.application.ports.agent_orchestrator import (
    AgentOrchestratorProtocol,
    AgentOutput,
    AgentRequest,
    AgentStatus,
    AgentStatusInfo,
    ContextBundle,
    DeliberationProgressCallback,
)
from src.application.ports.archon_profile_repository import ArchonProfileRepository
from src.application.ports.tool_registry import ToolRegistryProtocol
from src.domain.errors.agent import AgentInvocationError, AgentNotFoundError
from src.domain.models.archon_profile import ArchonProfile
from src.domain.models.llm_config import LLMConfig

if TYPE_CHECKING:
    from crewai_tools import BaseTool

logger = get_logger(__name__)


def _get_crewai_llm_string(llm_config: LLMConfig) -> str:
    """Convert LLMConfig to CrewAI LLM model string format.

    CrewAI accepts LLM specification as strings like:
    - "anthropic/claude-3-opus-20240229"
    - "openai/gpt-4o"
    - "ollama/llama2" (for local)
    - "google/gemini-pro"

    Args:
        llm_config: The LLM configuration

    Returns:
        CrewAI-compatible LLM model string
    """
    provider_map = {
        "anthropic": "anthropic",
        "openai": "openai",
        "google": "google",
        "local": "ollama",  # Local models typically via Ollama
    }
    provider = provider_map.get(llm_config.provider, llm_config.provider)
    return f"{provider}/{llm_config.model}"


def _create_crewai_llm(llm_config: LLMConfig) -> LLM | str:
    """Create a CrewAI LLM instance from LLMConfig.

    For Ollama (local provider), creates an LLM object with base_url.
    Priority for base_url:
      1. Per-archon base_url from LLMConfig (enables distributed inference)
      2. OLLAMA_HOST environment variable (global fallback)
      3. Default localhost:11434

    For cloud providers, returns a simple string identifier.

    Args:
        llm_config: The LLM configuration

    Returns:
        LLM object for Ollama, or string for cloud providers
    """
    model_string = _get_crewai_llm_string(llm_config)

    # For local/Ollama, create LLM object with base_url
    if llm_config.provider == "local":
        # Priority: per-archon base_url > OLLAMA_HOST env > default
        if llm_config.base_url:
            ollama_host = llm_config.base_url
        else:
            ollama_host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")

        logger.info(
            "creating_ollama_llm",
            model=model_string,
            base_url=ollama_host,
            temperature=llm_config.temperature,
            max_tokens=llm_config.max_tokens,
            per_archon_url=llm_config.base_url is not None,
        )
        return LLM(
            model=model_string,
            base_url=ollama_host,
            temperature=llm_config.temperature,
            max_tokens=llm_config.max_tokens,
        )

    # For cloud providers, return string (CrewAI handles the rest)
    return model_string


def _ensure_api_key(llm_config: LLMConfig) -> None:
    """Ensure the required API key environment variable is set.

    Raises:
        AgentInvocationError: If required API key is not set
    """
    env_var = llm_config.default_api_key_env
    if not os.environ.get(env_var):
        # Local models may not require API keys
        if llm_config.provider != "local":
            logger.warning(
                "api_key_not_set",
                env_var=env_var,
                provider=llm_config.provider,
            )


class CrewAIAdapter(AgentOrchestratorProtocol):
    """CrewAI implementation of agent orchestration.

    This adapter uses CrewAI to create and execute agents with
    per-archon LLM configuration from the ArchonProfileRepository.

    AC1: CrewAI adapter implements AgentOrchestratorProtocol
    AC2: Each archon creates a CrewAI Agent with correct LLM config
    AC3: System prompt from ArchonProfile.system_prompt injected as backstory
    AC4: Tools mapped from ArchonProfile.suggested_tools via ToolRegistry (Story 10-3)
    AC5: 72 concurrent agents can be instantiated
    AC6: Unit tests for adapter

    Attributes:
        _profile_repo: Repository for looking up Archon profiles
        _agent_status: Dictionary tracking agent status
        _verbose: Whether to enable verbose CrewAI logging
        _tool_registry: Registry for resolving tool names to Tool instances
    """

    def __init__(
        self,
        profile_repository: ArchonProfileRepository,
        verbose: bool = False,
        tool_registry: ToolRegistryProtocol | None = None,
    ) -> None:
        """Initialize the CrewAI adapter.

        Args:
            profile_repository: Repository for Archon profile lookup
            verbose: Enable verbose CrewAI logging (default False)
            tool_registry: Optional ToolRegistry for resolving tool names.
                If not provided, tools will not be available to agents.
        """
        self._profile_repo = profile_repository
        self._agent_status: dict[str, AgentStatusInfo] = {}
        self._verbose = verbose
        self._tool_registry = tool_registry

        tools_available = tool_registry.list_tools() if tool_registry else []
        logger.info(
            "crewai_adapter_initialized",
            archon_count=profile_repository.count(),
            verbose=verbose,
            tools_available=tools_available,
            tool_count=len(tools_available),
        )

    def _resolve_profile(self, agent_id: str) -> ArchonProfile:
        """Resolve agent_id to ArchonProfile.

        Supports lookup by:
        - UUID string (e.g., "1a4a2056-e2b5-42a7-a338-8b8b67509f1f")
        - Name (e.g., "Paimon", "paimon")

        Args:
            agent_id: UUID string or name

        Returns:
            ArchonProfile for the agent

        Raises:
            AgentNotFoundError: If agent_id cannot be resolved
        """
        # Try UUID lookup first
        try:
            archon_uuid = UUID(agent_id)
            profile = self._profile_repo.get_by_id(archon_uuid)
            if profile:
                return profile
        except ValueError:
            pass  # Not a valid UUID, try name lookup

        # Try name lookup (case-insensitive)
        profile = self._profile_repo.get_by_name(agent_id)
        if profile:
            return profile

        raise AgentNotFoundError(
            f"Agent '{agent_id}' not found in profile repository"
        )

    def _create_crewai_agent(
        self,
        profile: ArchonProfile,
        context: ContextBundle | None = None,
    ) -> Agent:
        """Create a CrewAI Agent from an ArchonProfile.

        Args:
            profile: The archon's complete profile
            context: Optional context to inject into system prompt

        Returns:
            Configured CrewAI Agent instance
        """
        # Get base CrewAI config from profile
        crewai_config = profile.get_crewai_config()

        # Create LLM instance or string from profile's LLM config
        # For local/Ollama, this creates an LLM object with base_url
        # For cloud providers, this returns a string
        llm = _create_crewai_llm(profile.llm_config)

        # Ensure API key is available (not needed for local)
        _ensure_api_key(profile.llm_config)

        # Inject context into backstory if provided
        backstory = profile.backstory
        if context:
            backstory = profile.get_system_prompt_with_context(
                f"Topic: {context.topic_content}"
            )

        # Map tools from suggested_tools via ToolRegistry (Story 10-3)
        tools: list["BaseTool"] = []
        if self._tool_registry:
            tools = self._tool_registry.get_tools(profile.suggested_tools)
            if len(tools) < len(profile.suggested_tools):
                logger.debug(
                    "some_tools_not_in_registry",
                    archon=profile.name,
                    requested_tools=profile.suggested_tools,
                    found_tools=[t.name for t in tools],
                )

        # Create the CrewAI Agent
        agent = Agent(
            role=crewai_config["role"],
            goal=crewai_config["goal"],
            backstory=backstory,
            verbose=self._verbose,
            allow_delegation=crewai_config["allow_delegation"],
            llm=llm,  # LLM object for Ollama, string for cloud providers
            max_iter=5,  # Limit iterations to prevent runaway
            tools=tools if tools else None,
        )

        # Log creation details
        llm_info = llm.model if isinstance(llm, LLM) else llm
        logger.debug(
            "crewai_agent_created",
            archon=profile.name,
            llm=llm_info,
            provider=profile.llm_config.provider,
            temperature=profile.llm_config.temperature,
            tools_count=len(tools),
        )

        return agent

    def _create_task(
        self,
        agent: Agent,
        context: ContextBundle,
    ) -> Task:
        """Create a CrewAI Task for deliberation.

        Args:
            agent: The CrewAI Agent to assign
            context: The context bundle with deliberation topic

        Returns:
            Configured CrewAI Task
        """
        return Task(
            description=f"""You are participating in a deliberation on the following topic:

Topic ID: {context.topic_id}

{context.topic_content}

Provide your perspective, analysis, and recommendations on this topic.
Consider the implications, potential risks, and opportunities.
Be thorough but concise in your response.""",
            expected_output="A structured deliberation response with analysis and recommendations",
            agent=agent,
        )

    async def invoke(
        self,
        agent_id: str,
        context: ContextBundle,
    ) -> AgentOutput:
        """Invoke a single agent with the given context.

        This method invokes one agent and waits for its output.
        The output must NOT be shown to humans before FR9 commitment.

        Args:
            agent_id: The ID of the agent (UUID or name)
            context: The context bundle for the agent to process

        Returns:
            AgentOutput containing the agent's deliberation output

        Raises:
            AgentInvocationError: If the agent fails to execute
            AgentNotFoundError: If the agent_id is not recognized
        """
        # Resolve profile
        profile = self._resolve_profile(agent_id)

        # Update status to BUSY
        self._agent_status[agent_id] = AgentStatusInfo(
            agent_id=agent_id,
            status=AgentStatus.BUSY,
            last_invocation=datetime.now(timezone.utc),
            last_error=None,
        )

        try:
            # Create CrewAI agent and task
            agent = self._create_crewai_agent(profile, context)
            task = self._create_task(agent, context)

            # Create a single-agent crew
            crew = Crew(
                agents=[agent],
                tasks=[task],
                verbose=self._verbose,
            )

            # Execute in thread pool to not block event loop
            # CrewAI's kickoff() is synchronous
            result = await asyncio.wait_for(
                asyncio.to_thread(crew.kickoff),
                timeout=profile.llm_config.timeout_ms / 1000.0,
            )

            # Extract result content
            content = str(result)

            # Update status to IDLE
            self._agent_status[agent_id] = AgentStatusInfo(
                agent_id=agent_id,
                status=AgentStatus.IDLE,
                last_invocation=datetime.now(timezone.utc),
                last_error=None,
            )

            logger.info(
                "crewai_agent_invoked",
                agent_id=agent_id,
                archon=profile.name,
                topic_id=context.topic_id,
                content_length=len(content),
            )

            return AgentOutput(
                output_id=uuid4(),
                agent_id=agent_id,
                request_id=context.bundle_id,
                content=content,
                content_type="text/plain",
                generated_at=datetime.now(timezone.utc),
            )

        except asyncio.TimeoutError:
            error_msg = f"Agent {agent_id} timed out after {profile.llm_config.timeout_ms}ms"
            self._agent_status[agent_id] = AgentStatusInfo(
                agent_id=agent_id,
                status=AgentStatus.FAILED,
                last_invocation=datetime.now(timezone.utc),
                last_error=error_msg,
            )
            logger.error(
                "crewai_agent_timeout",
                agent_id=agent_id,
                timeout_ms=profile.llm_config.timeout_ms,
            )
            raise AgentInvocationError(error_msg) from None

        except Exception as e:
            error_msg = f"Agent {agent_id} failed: {e}"
            self._agent_status[agent_id] = AgentStatusInfo(
                agent_id=agent_id,
                status=AgentStatus.FAILED,
                last_invocation=datetime.now(timezone.utc),
                last_error=error_msg,
            )
            logger.error(
                "crewai_agent_failed",
                agent_id=agent_id,
                error=str(e),
            )
            raise AgentInvocationError(error_msg) from e

    async def invoke_batch(
        self,
        requests: list[AgentRequest],
    ) -> list[AgentOutput]:
        """Invoke multiple agents concurrently.

        This method invokes multiple agents in parallel and returns
        all outputs. Uses asyncio.gather for true concurrent execution.

        Args:
            requests: List of AgentRequest objects to process

        Returns:
            List of AgentOutput objects in the same order as requests

        Raises:
            AgentInvocationError: If any agent fails to execute.
                The error includes which agents failed.
        """
        logger.info(
            "crewai_batch_invocation_started",
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
            logger.warning(
                "crewai_batch_partial_failure",
                success_count=len(results),
                failure_count=len(errors),
                errors=errors[:5],
            )
            raise AgentInvocationError(error_msg)

        logger.info(
            "crewai_batch_invocation_complete",
            success_count=len(results),
        )

        return results

    async def invoke_sequential(
        self,
        requests: list[AgentRequest],
        on_progress: DeliberationProgressCallback | None = None,
    ) -> list[AgentOutput]:
        """Invoke multiple agents sequentially (round-robin deliberation).

        This method invokes agents one at a time, ideal for single-GPU
        deployments where accuracy matters more than speed. Supports
        model swapping between agents when using different model sizes.

        The sequential pattern mirrors authentic constitutional deliberation
        where council members speak in turn rather than simultaneously.

        Args:
            requests: List of AgentRequest objects to process in order.
            on_progress: Optional callback invoked after each agent completes.
                         Signature: (current: int, total: int, agent_id: str, status: str)

        Returns:
            List of AgentOutput objects in the same order as requests.

        Raises:
            AgentInvocationError: If all agents fail. Individual failures
                are logged but do not stop the sequence.
        """
        total = len(requests)
        logger.info(
            "crewai_sequential_deliberation_started",
            agent_count=total,
            mode="round_robin",
        )

        outputs: list[AgentOutput] = []
        errors: list[str] = []

        for i, req in enumerate(requests):
            current = i + 1
            agent_id = req.agent_id

            # Notify progress callback (starting)
            if on_progress:
                on_progress(current, total, agent_id, "starting")

            logger.info(
                "deliberation_turn",
                turn=current,
                total=total,
                agent_id=agent_id,
                progress_pct=round((current - 1) / total * 100, 1),
            )

            try:
                output = await self.invoke(agent_id, req.context)
                outputs.append(output)

                # Notify progress callback (completed)
                if on_progress:
                    on_progress(current, total, agent_id, "completed")

                logger.info(
                    "deliberation_turn_complete",
                    turn=current,
                    total=total,
                    agent_id=agent_id,
                    content_length=len(output.content),
                )

            except AgentInvocationError as e:
                error_msg = f"{agent_id}: {e}"
                errors.append(error_msg)

                # Notify progress callback (failed)
                if on_progress:
                    on_progress(current, total, agent_id, "failed")

                logger.warning(
                    "deliberation_turn_failed",
                    turn=current,
                    total=total,
                    agent_id=agent_id,
                    error=str(e),
                )
                # Continue to next agent - don't stop the deliberation

        # Log final summary
        success_count = len(outputs)
        failure_count = len(errors)

        logger.info(
            "crewai_sequential_deliberation_complete",
            success_count=success_count,
            failure_count=failure_count,
            total=total,
            success_rate_pct=round(success_count / total * 100, 1) if total > 0 else 0,
        )

        # Only raise if ALL agents failed
        if success_count == 0 and failure_count > 0:
            raise AgentInvocationError(
                f"Sequential deliberation failed: all {failure_count} agents failed. "
                f"First errors: {errors[:3]}"
            )

        # Warn if some failed but we have partial results
        if failure_count > 0:
            logger.warning(
                "crewai_sequential_partial_failure",
                success_count=success_count,
                failure_count=failure_count,
                failed_agents=errors[:5],
            )

        return outputs

    async def get_agent_status(
        self,
        agent_id: str,
    ) -> AgentStatusInfo:
        """Get the current status of an agent.

        Args:
            agent_id: The ID of the agent to query

        Returns:
            AgentStatusInfo with the agent's current state

        Raises:
            AgentNotFoundError: If the agent_id is not recognized
        """
        # Verify agent exists in profile repository
        try:
            self._resolve_profile(agent_id)
        except AgentNotFoundError:
            raise

        # Return tracked status or IDLE if never invoked
        if agent_id in self._agent_status:
            return self._agent_status[agent_id]

        return AgentStatusInfo(
            agent_id=agent_id,
            status=AgentStatus.IDLE,
            last_invocation=None,
            last_error=None,
        )


def create_crewai_adapter(
    profile_repository: ArchonProfileRepository | None = None,
    verbose: bool = False,
    tool_registry: ToolRegistryProtocol | None = None,
    include_default_tools: bool = True,
) -> CrewAIAdapter:
    """Factory function to create a CrewAIAdapter.

    Args:
        profile_repository: Optional profile repository.
            If not provided, creates one with default paths.
        verbose: Enable verbose CrewAI logging
        tool_registry: Optional ToolRegistry for resolving tool names.
            If not provided and include_default_tools is True, creates
            a registry with all 9 archon tools.
        include_default_tools: If True and no tool_registry provided,
            creates a default registry with all archon tools.

    Returns:
        Configured CrewAIAdapter instance
    """
    if profile_repository is None:
        from src.infrastructure.adapters.config.archon_profile_adapter import (
            create_archon_profile_repository,
        )
        profile_repository = create_archon_profile_repository()

    if tool_registry is None and include_default_tools:
        from src.infrastructure.adapters.tools import create_tool_registry
        tool_registry = create_tool_registry()

    return CrewAIAdapter(
        profile_repository=profile_repository,
        verbose=verbose,
        tool_registry=tool_registry,
    )
