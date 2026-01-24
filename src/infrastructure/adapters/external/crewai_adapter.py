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
import json
import os
import random
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

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
from src.infrastructure.adapters.external.crewai_llm_factory import create_crewai_llm
from src.optional_deps.crewai import LLM, Agent, Crew, Task

if TYPE_CHECKING:
    from src.optional_deps.crewai import BaseTool

logger = get_logger(__name__)


def _log_safe(log_fn, event: str, **fields) -> None:
    """Log with structured fields, falling back to plain string on TypeError."""
    try:
        log_fn(event, **fields)
    except TypeError:
        log_fn(f"{event} {fields}")


def _get_env_int(name: str, default: int) -> int:
    value = os.getenv(name, "").strip()
    if not value:
        return default
    try:
        return int(float(value))
    except ValueError:
        return default


def _get_env_float(name: str, default: float) -> float:
    value = os.getenv(name, "").strip()
    if not value:
        return default
    try:
        return float(value)
    except ValueError:
        return default


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
        raw_max_concurrent = os.getenv("OLLAMA_MAX_CONCURRENT", "").strip()
        self._llm_max_concurrent_configured = bool(raw_max_concurrent)
        self._llm_max_concurrent = _get_env_int("OLLAMA_MAX_CONCURRENT", 0)
        self._llm_semaphore = (
            asyncio.Semaphore(self._llm_max_concurrent)
            if self._llm_max_concurrent > 0
            else None
        )
        self._retry_max_attempts = max(
            1,
            _get_env_int(
                "OLLAMA_RETRY_MAX_ATTEMPTS",
                _get_env_int("AGENT_TIMEOUT_MAX_ATTEMPTS", 3),
            ),
        )
        self._retry_base_delay = max(
            0.0,
            _get_env_float(
                "OLLAMA_RETRY_BASE_DELAY",
                _get_env_float("AGENT_TIMEOUT_BASE_DELAY_SECONDS", 2.0),
            ),
        )
        self._retry_max_delay = max(
            self._retry_base_delay,
            _get_env_float(
                "OLLAMA_RETRY_MAX_DELAY",
                _get_env_float("AGENT_TIMEOUT_MAX_DELAY_SECONDS", 30.0),
            ),
        )

        tools_available = tool_registry.list_tools() if tool_registry else []
        logger.info(
            "crewai_adapter_initialized",
            archon_count=profile_repository.count(),
            verbose=verbose,
            tools_available=tools_available,
            tool_count=len(tools_available),
            llm_max_concurrent=self._llm_max_concurrent,
            retry_max_attempts=self._retry_max_attempts,
            retry_base_delay_seconds=self._retry_base_delay,
            retry_max_delay_seconds=self._retry_max_delay,
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

        raise AgentNotFoundError(f"Agent '{agent_id}' not found in profile repository")

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

        llm = create_crewai_llm(profile.llm_config)

        # Inject context into backstory if provided
        backstory = profile.backstory
        if context:
            backstory = profile.get_system_prompt_with_context(
                f"Topic: {context.topic_content}"
            )

        # Map tools from suggested_tools via ToolRegistry (Story 10-3)
        tools: list[BaseTool] = []
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
            llm=llm,
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
        self._ensure_llm_semaphore(profile)

        # Update status to BUSY
        self._agent_status[agent_id] = AgentStatusInfo(
            agent_id=agent_id,
            status=AgentStatus.BUSY,
            last_invocation=datetime.now(timezone.utc),
            last_error=None,
        )

        async def _invoke_once() -> str:
            # Create CrewAI agent and task
            agent = self._create_crewai_agent(profile, context)
            task = self._create_task(agent, context)

            # Create a single-agent crew
            crew = Crew(
                agents=[agent],
                tasks=[task],
                verbose=self._verbose,
            )

            async def _run_kickoff() -> Any:
                return await asyncio.wait_for(
                    asyncio.to_thread(crew.kickoff),
                    timeout=profile.llm_config.timeout_ms / 1000.0,
                )

            if self._llm_semaphore:
                async with self._llm_semaphore:
                    return str(await _run_kickoff())

            return str(await _run_kickoff())

        attempt = 1
        retry_delay = 0.0
        while True:
            try:
                content = await _invoke_once()

                # Update status to IDLE
                self._agent_status[agent_id] = AgentStatusInfo(
                    agent_id=agent_id,
                    status=AgentStatus.IDLE,
                    last_invocation=datetime.now(timezone.utc),
                    last_error=None,
                )

                _log_safe(
                    logger.info,
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

            except asyncio.CancelledError:
                raise
            except TimeoutError as exc:
                if attempt >= self._retry_max_attempts:
                    error_msg = (
                        f"Agent {agent_id} timed out after "
                        f"{profile.llm_config.timeout_ms}ms (attempts={attempt})"
                    )
                    self._agent_status[agent_id] = AgentStatusInfo(
                        agent_id=agent_id,
                        status=AgentStatus.FAILED,
                        last_invocation=datetime.now(timezone.utc),
                        last_error=error_msg,
                    )
                    _log_safe(
                        logger.error,
                        "crewai_agent_timeout",
                        agent_id=agent_id,
                        timeout_ms=profile.llm_config.timeout_ms,
                        attempts=attempt,
                    )
                    raise AgentInvocationError(error_msg) from exc

                retry_delay = self._next_retry_delay(retry_delay)
                _log_safe(
                    logger.warning,
                    "crewai_agent_timeout_retry",
                    agent_id=agent_id,
                    timeout_ms=profile.llm_config.timeout_ms,
                    attempt=attempt,
                    retry_delay_seconds=retry_delay,
                )
                await asyncio.sleep(retry_delay)
                attempt += 1
            except Exception as e:
                if self._is_retryable_error(e) and attempt < self._retry_max_attempts:
                    retry_delay = self._next_retry_delay(retry_delay)
                    _log_safe(
                        logger.warning,
                        "crewai_agent_retry",
                        agent_id=agent_id,
                        attempt=attempt,
                        retry_delay_seconds=retry_delay,
                        error=str(e),
                    )
                    await asyncio.sleep(retry_delay)
                    attempt += 1
                    continue

                error_msg = f"Agent {agent_id} failed: {e}"
                self._agent_status[agent_id] = AgentStatusInfo(
                    agent_id=agent_id,
                    status=AgentStatus.FAILED,
                    last_invocation=datetime.now(timezone.utc),
                    last_error=error_msg,
                )
                _log_safe(
                    logger.error,
                    "crewai_agent_failed",
                    agent_id=agent_id,
                    error=str(e),
                )
                raise AgentInvocationError(error_msg) from e

    def _next_retry_delay(self, previous_delay: float) -> float:
        """Decorrelated jitter backoff for retries."""
        if self._retry_base_delay <= 0:
            return 0.0
        if previous_delay <= 0:
            delay = self._retry_base_delay
        else:
            delay = random.uniform(self._retry_base_delay, previous_delay * 3)
        return min(delay, self._retry_max_delay)

    def _ensure_llm_semaphore(self, profile: ArchonProfile) -> None:
        """Initialize a default semaphore for Ollama Cloud if not configured."""
        if self._llm_semaphore is not None or self._llm_max_concurrent_configured:
            return

        base_url = profile.llm_config.base_url or os.getenv("OLLAMA_BASE_URL", "")
        cloud_enabled = os.getenv("OLLAMA_CLOUD_ENABLED", "").lower() == "true"
        uses_cloud = (
            profile.llm_config.provider == "ollama_cloud"
            or cloud_enabled
            or "ollama.com" in base_url
        )
        if not uses_cloud:
            return

        # Default to a conservative limit if not configured.
        self._llm_max_concurrent = 5
        self._llm_semaphore = asyncio.Semaphore(self._llm_max_concurrent)
        _log_safe(
            logger.info,
            "crewai_llm_semaphore_defaulted",
            llm_max_concurrent=self._llm_max_concurrent,
        )

    @staticmethod
    def _is_retryable_error(error: Exception) -> bool:
        """Return True for transient errors worth retrying."""
        if isinstance(error, (ConnectionError, TimeoutError, asyncio.TimeoutError)):
            return True
        message = str(error).lower()
        return any(
            token in message
            for token in (
                "too many concurrent requests",
                "rate limit",
                "429",
                "503",
                "temporarily unavailable",
                "timeout",
                "connection",
                "api connection",
            )
        )

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
            *[self.invoke(req.agent_id, req.context) for req in requests],
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

    async def execute_validation_task(
        self,
        task_type: str,
        validator_archon_id: str,
        vote_payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute a validation task and return structured output."""
        prompt = self._build_validation_prompt(task_type, vote_payload)
        bundle = ContextBundle(
            bundle_id=uuid4(),
            topic_id=f"vote-validate-{task_type}",
            topic_content=prompt,
            metadata={
                "task_type": task_type,
                "validation": "vote",
            },
            created_at=datetime.now(timezone.utc),
        )

        output = await self.invoke(validator_archon_id, bundle)
        parsed = self._parse_json_payload(output.content)

        vote_choice = None
        confidence = 0.0
        if isinstance(parsed, dict):
            vote_choice = parsed.get("vote_choice") or parsed.get("choice")
            confidence = float(parsed.get("confidence", 0.0) or 0.0)

        return {
            "vote_choice": vote_choice,
            "confidence": confidence,
            "raw_response": output.content,
            "parse_success": parsed is not None,
            "metadata": parsed or {},
        }

    async def execute_witness_adjudication(
        self,
        witness_archon_id: str,
        vote_payload: dict[str, Any],
        deliberator_results: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute witness adjudication and return structured output."""
        prompt = self._build_witness_adjudication_prompt(
            vote_payload=vote_payload,
            deliberator_results=deliberator_results,
        )
        bundle = ContextBundle(
            bundle_id=uuid4(),
            topic_id="vote-witness-adjudication",
            topic_content=prompt,
            metadata={
                "validation": "witness_adjudication",
            },
            created_at=datetime.now(timezone.utc),
        )

        output = await self.invoke(witness_archon_id, bundle)
        parsed = self._parse_json_payload(output.content)

        final_vote = None
        retort_flag = False
        if isinstance(parsed, dict):
            final_vote = parsed.get("final_vote") or parsed.get("vote_choice")
            ruling = str(parsed.get("ruling", "")).upper()
            if ruling == "RETORT":
                retort_flag = True
            else:
                retort_flag = bool(parsed.get("retort", False))

        return {
            "final_vote": final_vote,
            "retort": retort_flag,
            "retort_reason": parsed.get("retort_reason") if isinstance(parsed, dict) else None,
            "witness_statement": parsed.get("witness_statement", output.content)
            if isinstance(parsed, dict)
            else output.content,
        }

    @staticmethod
    def _parse_json_payload(content: str) -> dict[str, Any] | None:
        """Parse the first JSON object found in the content.

        Models sometimes return valid JSON followed by extra prose, markdown
        fences, or other text. We need a parser that can extract the first
        JSON object reliably without requiring the entire response to be JSON.
        """
        decoder = json.JSONDecoder()
        for index, char in enumerate(content):
            if char not in ("{", "["):
                continue
            try:
                payload, _end = decoder.raw_decode(content[index:])
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                return payload
        return None

    @staticmethod
    def _build_validation_prompt(task_type: str, vote_payload: dict[str, Any]) -> str:
        """Build prompt for validation tasks."""
        raw_response = vote_payload.get("raw_content", "")
        motion_text = vote_payload.get("motion_text", "")
        motion_title = vote_payload.get("motion_title", "")
        archon_name = vote_payload.get("archon_name", "")

        # IMPORTANT: The first non-empty line selects the deterministic mode
        # defined in docs/archons-base.json. In CONCLAVE VOTE VALIDATION mode,
        # Archons MUST return JSON only: {"choice":"AYE|NAY|ABSTAIN"} with no prose.
        header = "ARCHON 72 CONCLAVE - VOTE VALIDATION\n\n"

        if task_type == "json_validation":
            guidance = (
                "Validate the vote based on structural signals (explicit JSON choice "
                "wins)."
            )
        elif task_type == "witness_confirm":
            guidance = "Independently confirm the vote intent."
        else:
            guidance = "Validate the vote intent from natural language."

        return (
            header
            + f"{guidance}\n"
            + f"ARCHON: {archon_name}\n"
            + f"MOTION: {motion_title}\n"
            + f"MOTION TEXT:\n{motion_text}\n\n"
            + f"RAW RESPONSE:\n{raw_response}\n\n"
            + 'Return JSON only: {"choice":"AYE"} or {"choice":"NAY"} or {"choice":"ABSTAIN"}'
        )

    @staticmethod
    def _build_witness_adjudication_prompt(
        vote_payload: dict[str, Any],
        deliberator_results: dict[str, Any],
    ) -> str:
        """Build prompt for witness adjudication."""
        raw_response = vote_payload.get("raw_content", "")
        motion_title = vote_payload.get("motion_title", "")
        deliberator_json = json.dumps(deliberator_results, ensure_ascii=True)

        return (
            "You are the witness adjudicating a vote validation dispute.\n"
            "Return JSON only (no prose, no markdown).\n"
            f"MOTION: {motion_title}\n"
            f"RAW RESPONSE:\n{raw_response}\n\n"
            f"DELIBERATOR RESULTS:\n{deliberator_json}\n\n"
            "Return JSON only:\n"
            '{\"consensus\": true|false, '
            '\"final_vote\": \"AYE|NAY|ABSTAIN\", '
            '\"ruling\": \"CONFIRMED|RETORT\", '
            '\"retort_reason\": \"\", '
            '\"witness_statement\": \"\"}\n'
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
