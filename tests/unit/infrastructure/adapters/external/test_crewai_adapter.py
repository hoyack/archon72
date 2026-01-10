"""Unit tests for CrewAI adapter (Story 10-2).

Tests the CrewAI adapter implementation with mocked CrewAI dependencies.
Validates:
- AC1: CrewAI adapter implements AgentOrchestratorProtocol
- AC2: Each archon creates a CrewAI Agent with correct LLM config
- AC3: System prompt from ArchonProfile.system_prompt injected as backstory
- AC4: Tools mapped from ArchonProfile.suggested_tools
- AC5: 72 concurrent agents can be instantiated
- AC6: Unit tests for adapter
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from src.application.ports.agent_orchestrator import (
    AgentOrchestratorProtocol,
    AgentOutput,
    AgentRequest,
    AgentStatus,
    AgentStatusInfo,
    ContextBundle,
)
from src.application.ports.archon_profile_repository import ArchonProfileRepository
from src.domain.errors.agent import AgentInvocationError, AgentNotFoundError
from src.domain.models.archon_profile import ArchonProfile
from src.domain.models.llm_config import LLMConfig, DEFAULT_LLM_CONFIG
from src.infrastructure.adapters.external.crewai_adapter import (
    CrewAIAdapter,
    create_crewai_adapter,
    _get_crewai_llm_string,
    _ensure_api_key,
)


# ===========================================================================
# Fixtures
# ===========================================================================


@pytest.fixture
def sample_archon_profile() -> ArchonProfile:
    """Create a sample ArchonProfile for testing."""
    return ArchonProfile(
        id=UUID("1a4a2056-e2b5-42a7-a338-8b8b67509f1f"),
        name="Paimon",
        aegis_rank="executive_director",
        original_rank="King",
        rank_level=8,
        role="Executive Director of Knowledge and Arts",
        goal="Develop and empower members through wisdom and creative expression",
        backstory="Paimon is the wise king of knowledge...",
        system_prompt="You are Paimon, an executive director...",
        suggested_tools=["insight_tool", "communication_tool"],
        allow_delegation=True,
        attributes={"personality": "wise", "brand_color": "#FFD700"},
        max_members=100,
        max_legions=25,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        llm_config=LLMConfig(
            provider="anthropic",
            model="claude-3-opus-20240229",
            temperature=0.8,
            max_tokens=8192,
            timeout_ms=60000,
        ),
    )


@pytest.fixture
def sample_archon_profile_openai() -> ArchonProfile:
    """Create a sample ArchonProfile with OpenAI config."""
    return ArchonProfile(
        id=UUID("2b5b3067-f3c6-53b8-b449-9c9c78610a2a"),
        name="Belial",
        aegis_rank="executive_director",
        original_rank="King",
        rank_level=8,
        role="Executive Director of Strategy",
        goal="Strategic planning and execution",
        backstory="Belial is the strategic mastermind...",
        system_prompt="You are Belial, an executive director...",
        suggested_tools=["strategy_tool"],
        allow_delegation=True,
        attributes={"personality": "strategic", "brand_color": "#8B0000"},
        max_members=100,
        max_legions=25,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        llm_config=LLMConfig(
            provider="openai",
            model="gpt-4o",
            temperature=0.7,
            max_tokens=4096,
            timeout_ms=30000,
        ),
    )


@pytest.fixture
def mock_profile_repository(
    sample_archon_profile: ArchonProfile,
    sample_archon_profile_openai: ArchonProfile,
) -> MagicMock:
    """Create a mock ArchonProfileRepository."""
    mock_repo = MagicMock(spec=ArchonProfileRepository)

    profiles = {
        sample_archon_profile.id: sample_archon_profile,
        sample_archon_profile_openai.id: sample_archon_profile_openai,
    }
    profiles_by_name = {
        sample_archon_profile.name.lower(): sample_archon_profile,
        sample_archon_profile_openai.name.lower(): sample_archon_profile_openai,
    }

    mock_repo.get_by_id.side_effect = lambda uid: profiles.get(uid)
    mock_repo.get_by_name.side_effect = lambda name: profiles_by_name.get(name.lower())
    mock_repo.count.return_value = 72
    mock_repo.get_all.return_value = list(profiles.values())

    return mock_repo


@pytest.fixture
def sample_context_bundle() -> ContextBundle:
    """Create a sample ContextBundle for testing."""
    return ContextBundle(
        bundle_id=uuid4(),
        topic_id="topic-001",
        topic_content="Should the Conclave adopt a new constitutional amendment?",
        metadata={"priority": "high"},
        created_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def adapter(mock_profile_repository: MagicMock) -> CrewAIAdapter:
    """Create a CrewAIAdapter with mock repository."""
    return CrewAIAdapter(
        profile_repository=mock_profile_repository,
        verbose=False,
    )


# ===========================================================================
# Tests: LLM String Conversion
# ===========================================================================


class TestGetCrewaiLlmString:
    """Tests for _get_crewai_llm_string helper."""

    def test_anthropic_provider(self) -> None:
        """Test Anthropic provider string generation."""
        config = LLMConfig(
            provider="anthropic",
            model="claude-3-opus-20240229",
        )
        result = _get_crewai_llm_string(config)
        assert result == "anthropic/claude-3-opus-20240229"

    def test_openai_provider(self) -> None:
        """Test OpenAI provider string generation."""
        config = LLMConfig(
            provider="openai",
            model="gpt-4o",
        )
        result = _get_crewai_llm_string(config)
        assert result == "openai/gpt-4o"

    def test_google_provider(self) -> None:
        """Test Google provider string generation."""
        config = LLMConfig(
            provider="google",
            model="gemini-pro",
        )
        result = _get_crewai_llm_string(config)
        assert result == "google/gemini-pro"

    def test_local_provider_maps_to_ollama(self) -> None:
        """Test local provider maps to ollama."""
        config = LLMConfig(
            provider="local",
            model="llama2",
            timeout_ms=10000,
        )
        result = _get_crewai_llm_string(config)
        assert result == "ollama/llama2"


# ===========================================================================
# Tests: API Key Handling
# ===========================================================================


class TestEnsureApiKey:
    """Tests for _ensure_api_key helper."""

    def test_warns_when_api_key_missing(
        self,
        sample_archon_profile: ArchonProfile,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test warning logged when API key is not set."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        # Should not raise, just warn
        _ensure_api_key(sample_archon_profile.llm_config)

    def test_no_warning_for_local_provider(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test no warning for local provider without API key."""
        monkeypatch.delenv("LOCAL_LLM_API_KEY", raising=False)
        config = LLMConfig(
            provider="local",
            model="llama2",
            timeout_ms=10000,
        )
        # Should not warn for local provider
        _ensure_api_key(config)


# ===========================================================================
# Tests: Adapter Initialization
# ===========================================================================


class TestCrewAIAdapterInit:
    """Tests for CrewAIAdapter initialization."""

    def test_implements_protocol(self, adapter: CrewAIAdapter) -> None:
        """AC1: Adapter implements AgentOrchestratorProtocol."""
        assert isinstance(adapter, AgentOrchestratorProtocol)

    def test_initializes_with_repository(
        self,
        mock_profile_repository: MagicMock,
    ) -> None:
        """Test adapter initializes with profile repository."""
        adapter = CrewAIAdapter(
            profile_repository=mock_profile_repository,
            verbose=True,
        )
        assert adapter._profile_repo is mock_profile_repository
        assert adapter._verbose is True

    def test_initializes_with_tool_registry(
        self,
        mock_profile_repository: MagicMock,
    ) -> None:
        """Test adapter initializes with tool registry."""
        from src.application.ports.tool_registry import ToolRegistryProtocol

        mock_tool_registry = MagicMock(spec=ToolRegistryProtocol)
        mock_tool_registry.list_tools.return_value = ["insight_tool", "communication_tool"]

        adapter = CrewAIAdapter(
            profile_repository=mock_profile_repository,
            tool_registry=mock_tool_registry,
        )

        assert adapter._tool_registry is mock_tool_registry


# ===========================================================================
# Tests: Profile Resolution
# ===========================================================================


class TestProfileResolution:
    """Tests for agent_id to ArchonProfile resolution."""

    def test_resolves_by_uuid(
        self,
        adapter: CrewAIAdapter,
        sample_archon_profile: ArchonProfile,
    ) -> None:
        """Test resolution by UUID string."""
        profile = adapter._resolve_profile(str(sample_archon_profile.id))
        assert profile.name == "Paimon"

    def test_resolves_by_name(
        self,
        adapter: CrewAIAdapter,
        sample_archon_profile: ArchonProfile,
    ) -> None:
        """Test resolution by name."""
        profile = adapter._resolve_profile("Paimon")
        assert profile.id == sample_archon_profile.id

    def test_resolves_by_name_case_insensitive(
        self,
        adapter: CrewAIAdapter,
        sample_archon_profile: ArchonProfile,
    ) -> None:
        """Test resolution by name is case-insensitive."""
        profile = adapter._resolve_profile("paimon")
        assert profile.name == "Paimon"

    def test_raises_not_found_for_unknown(
        self,
        adapter: CrewAIAdapter,
    ) -> None:
        """Test AgentNotFoundError for unknown agent."""
        with pytest.raises(AgentNotFoundError):
            adapter._resolve_profile("unknown-agent")


# ===========================================================================
# Tests: CrewAI Agent Creation
# ===========================================================================


class TestCrewAIAgentCreation:
    """Tests for CrewAI Agent creation from ArchonProfile."""

    @patch("src.infrastructure.adapters.external.crewai_adapter.Agent")
    def test_creates_agent_with_correct_config(
        self,
        mock_agent_class: MagicMock,
        adapter: CrewAIAdapter,
        sample_archon_profile: ArchonProfile,
    ) -> None:
        """AC2: Agent created with correct LLM config."""
        mock_agent_class.return_value = MagicMock()

        agent = adapter._create_crewai_agent(sample_archon_profile)

        mock_agent_class.assert_called_once()
        call_kwargs = mock_agent_class.call_args.kwargs

        assert call_kwargs["role"] == sample_archon_profile.role
        assert call_kwargs["goal"] == sample_archon_profile.goal
        assert call_kwargs["llm"] == "anthropic/claude-3-opus-20240229"
        assert call_kwargs["allow_delegation"] is True
        assert call_kwargs["verbose"] is False

    @patch("src.infrastructure.adapters.external.crewai_adapter.Agent")
    def test_injects_backstory_from_profile(
        self,
        mock_agent_class: MagicMock,
        adapter: CrewAIAdapter,
        sample_archon_profile: ArchonProfile,
    ) -> None:
        """AC3: System prompt injected as backstory."""
        mock_agent_class.return_value = MagicMock()

        adapter._create_crewai_agent(sample_archon_profile)

        call_kwargs = mock_agent_class.call_args.kwargs
        # Without context, uses backstory directly
        assert call_kwargs["backstory"] == sample_archon_profile.backstory

    @patch("src.infrastructure.adapters.external.crewai_adapter.Agent")
    def test_injects_context_into_backstory(
        self,
        mock_agent_class: MagicMock,
        adapter: CrewAIAdapter,
        sample_archon_profile: ArchonProfile,
        sample_context_bundle: ContextBundle,
    ) -> None:
        """AC3: Context injected into backstory when provided."""
        mock_agent_class.return_value = MagicMock()

        adapter._create_crewai_agent(sample_archon_profile, sample_context_bundle)

        call_kwargs = mock_agent_class.call_args.kwargs
        assert "Topic:" in call_kwargs["backstory"]
        assert sample_context_bundle.topic_content in call_kwargs["backstory"]

    @patch("src.infrastructure.adapters.external.crewai_adapter.Agent")
    def test_maps_tools_from_registry(
        self,
        mock_agent_class: MagicMock,
        mock_profile_repository: MagicMock,
        sample_archon_profile: ArchonProfile,
    ) -> None:
        """AC4: Tools mapped from suggested_tools via ToolRegistry."""
        from src.application.ports.tool_registry import ToolRegistryProtocol

        mock_insight_tool = MagicMock()
        mock_insight_tool.name = "insight_tool"
        mock_agent_class.return_value = MagicMock()

        mock_tool_registry = MagicMock(spec=ToolRegistryProtocol)
        mock_tool_registry.list_tools.return_value = ["insight_tool"]
        mock_tool_registry.get_tools.return_value = [mock_insight_tool]

        adapter = CrewAIAdapter(
            profile_repository=mock_profile_repository,
            tool_registry=mock_tool_registry,
        )

        adapter._create_crewai_agent(sample_archon_profile)

        # Verify get_tools was called with the profile's suggested_tools
        mock_tool_registry.get_tools.assert_called_once_with(sample_archon_profile.suggested_tools)

        call_kwargs = mock_agent_class.call_args.kwargs
        assert mock_insight_tool in call_kwargs["tools"]


# ===========================================================================
# Tests: Single Agent Invocation
# ===========================================================================


class TestInvoke:
    """Tests for single agent invocation."""

    @pytest.mark.asyncio
    @patch("src.infrastructure.adapters.external.crewai_adapter.Crew")
    @patch("src.infrastructure.adapters.external.crewai_adapter.Agent")
    @patch("src.infrastructure.adapters.external.crewai_adapter.Task")
    async def test_invoke_returns_agent_output(
        self,
        mock_task_class: MagicMock,
        mock_agent_class: MagicMock,
        mock_crew_class: MagicMock,
        adapter: CrewAIAdapter,
        sample_archon_profile: ArchonProfile,
        sample_context_bundle: ContextBundle,
    ) -> None:
        """Test invoke returns AgentOutput with content."""
        mock_crew = MagicMock()
        mock_crew.kickoff.return_value = "This is my deliberation response"
        mock_crew_class.return_value = mock_crew

        output = await adapter.invoke(
            agent_id=str(sample_archon_profile.id),
            context=sample_context_bundle,
        )

        assert isinstance(output, AgentOutput)
        assert output.agent_id == str(sample_archon_profile.id)
        assert output.content == "This is my deliberation response"
        assert output.content_type == "text/plain"

    @pytest.mark.asyncio
    @patch("src.infrastructure.adapters.external.crewai_adapter.Crew")
    @patch("src.infrastructure.adapters.external.crewai_adapter.Agent")
    @patch("src.infrastructure.adapters.external.crewai_adapter.Task")
    async def test_invoke_updates_status_to_busy_then_idle(
        self,
        mock_task_class: MagicMock,
        mock_agent_class: MagicMock,
        mock_crew_class: MagicMock,
        adapter: CrewAIAdapter,
        sample_archon_profile: ArchonProfile,
        sample_context_bundle: ContextBundle,
    ) -> None:
        """Test invoke updates agent status correctly."""
        mock_crew = MagicMock()
        mock_crew.kickoff.return_value = "Response"
        mock_crew_class.return_value = mock_crew

        agent_id = str(sample_archon_profile.id)

        await adapter.invoke(agent_id=agent_id, context=sample_context_bundle)

        status = await adapter.get_agent_status(agent_id)
        assert status.status == AgentStatus.IDLE
        assert status.last_error is None

    @pytest.mark.asyncio
    async def test_invoke_raises_not_found_for_unknown_agent(
        self,
        adapter: CrewAIAdapter,
        sample_context_bundle: ContextBundle,
    ) -> None:
        """Test invoke raises AgentNotFoundError for unknown agent."""
        with pytest.raises(AgentNotFoundError):
            await adapter.invoke(
                agent_id="unknown-agent",
                context=sample_context_bundle,
            )

    @pytest.mark.asyncio
    @patch("src.infrastructure.adapters.external.crewai_adapter.Crew")
    @patch("src.infrastructure.adapters.external.crewai_adapter.Agent")
    @patch("src.infrastructure.adapters.external.crewai_adapter.Task")
    async def test_invoke_handles_timeout(
        self,
        mock_task_class: MagicMock,
        mock_agent_class: MagicMock,
        mock_crew_class: MagicMock,
        mock_profile_repository: MagicMock,
        sample_context_bundle: ContextBundle,
    ) -> None:
        """Test invoke handles timeout and updates status to FAILED."""
        import time

        # Create profile with very short timeout
        profile = ArchonProfile(
            id=UUID("3c6c4178-a4d7-64c9-c560-0d0d89721a3a"),
            name="SlowAgent",
            aegis_rank="director",
            original_rank="Marquis",
            rank_level=6,
            role="Test Agent",
            goal="Testing",
            backstory="Test",
            system_prompt="Test",
            suggested_tools=[],
            allow_delegation=False,
            attributes={},
            max_members=10,
            max_legions=5,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            llm_config=LLMConfig(
                provider="anthropic",
                model="claude-3-haiku-20240307",
                timeout_ms=1000,  # 1 second timeout
            ),
        )
        mock_profile_repository.get_by_name.side_effect = lambda n: profile if n.lower() == "slowagent" else None

        # Make crew.kickoff block longer than timeout (synchronous sleep)
        def slow_kickoff():
            time.sleep(5)
            return "Response"

        mock_crew = MagicMock()
        mock_crew.kickoff = slow_kickoff
        mock_crew_class.return_value = mock_crew

        adapter = CrewAIAdapter(profile_repository=mock_profile_repository)

        with pytest.raises(AgentInvocationError) as exc_info:
            await adapter.invoke(
                agent_id="SlowAgent",
                context=sample_context_bundle,
            )

        assert "timed out" in str(exc_info.value)

    @pytest.mark.asyncio
    @patch("src.infrastructure.adapters.external.crewai_adapter.Crew")
    @patch("src.infrastructure.adapters.external.crewai_adapter.Agent")
    @patch("src.infrastructure.adapters.external.crewai_adapter.Task")
    async def test_invoke_handles_crew_exception(
        self,
        mock_task_class: MagicMock,
        mock_agent_class: MagicMock,
        mock_crew_class: MagicMock,
        adapter: CrewAIAdapter,
        sample_archon_profile: ArchonProfile,
        sample_context_bundle: ContextBundle,
    ) -> None:
        """Test invoke handles exceptions and updates status to FAILED."""
        mock_crew = MagicMock()
        mock_crew.kickoff.side_effect = RuntimeError("LLM API Error")
        mock_crew_class.return_value = mock_crew

        agent_id = str(sample_archon_profile.id)

        with pytest.raises(AgentInvocationError) as exc_info:
            await adapter.invoke(
                agent_id=agent_id,
                context=sample_context_bundle,
            )

        assert "LLM API Error" in str(exc_info.value)

        status = await adapter.get_agent_status(agent_id)
        assert status.status == AgentStatus.FAILED
        assert "LLM API Error" in status.last_error


# ===========================================================================
# Tests: Batch Invocation
# ===========================================================================


class TestInvokeBatch:
    """Tests for batch agent invocation."""

    @pytest.mark.asyncio
    @patch("src.infrastructure.adapters.external.crewai_adapter.Crew")
    @patch("src.infrastructure.adapters.external.crewai_adapter.Agent")
    @patch("src.infrastructure.adapters.external.crewai_adapter.Task")
    async def test_invoke_batch_executes_concurrently(
        self,
        mock_task_class: MagicMock,
        mock_agent_class: MagicMock,
        mock_crew_class: MagicMock,
        adapter: CrewAIAdapter,
        sample_archon_profile: ArchonProfile,
        sample_archon_profile_openai: ArchonProfile,
        sample_context_bundle: ContextBundle,
    ) -> None:
        """AC5: Test batch invocation with concurrent execution."""
        mock_crew = MagicMock()
        mock_crew.kickoff.return_value = "Deliberation response"
        mock_crew_class.return_value = mock_crew

        requests = [
            AgentRequest(
                request_id=uuid4(),
                agent_id=str(sample_archon_profile.id),
                context=sample_context_bundle,
            ),
            AgentRequest(
                request_id=uuid4(),
                agent_id=str(sample_archon_profile_openai.id),
                context=sample_context_bundle,
            ),
        ]

        outputs = await adapter.invoke_batch(requests)

        assert len(outputs) == 2
        assert all(isinstance(o, AgentOutput) for o in outputs)

    @pytest.mark.asyncio
    @patch("src.infrastructure.adapters.external.crewai_adapter.Crew")
    @patch("src.infrastructure.adapters.external.crewai_adapter.Agent")
    @patch("src.infrastructure.adapters.external.crewai_adapter.Task")
    async def test_invoke_batch_raises_on_partial_failure(
        self,
        mock_task_class: MagicMock,
        mock_agent_class: MagicMock,
        mock_crew_class: MagicMock,
        adapter: CrewAIAdapter,
        sample_archon_profile: ArchonProfile,
        sample_context_bundle: ContextBundle,
    ) -> None:
        """Test batch raises AgentInvocationError on partial failure."""
        mock_crew = MagicMock()
        # First call succeeds, second fails
        mock_crew.kickoff.side_effect = [
            "Response 1",
            RuntimeError("API Error"),
        ]
        mock_crew_class.return_value = mock_crew

        requests = [
            AgentRequest(
                request_id=uuid4(),
                agent_id=str(sample_archon_profile.id),
                context=sample_context_bundle,
            ),
            AgentRequest(
                request_id=uuid4(),
                agent_id=str(sample_archon_profile.id),
                context=sample_context_bundle,
            ),
        ]

        with pytest.raises(AgentInvocationError) as exc_info:
            await adapter.invoke_batch(requests)

        assert "1 failures" in str(exc_info.value)


# ===========================================================================
# Tests: Agent Status
# ===========================================================================


class TestGetAgentStatus:
    """Tests for agent status retrieval."""

    @pytest.mark.asyncio
    async def test_returns_idle_for_never_invoked(
        self,
        adapter: CrewAIAdapter,
        sample_archon_profile: ArchonProfile,
    ) -> None:
        """Test returns IDLE status for agent never invoked."""
        status = await adapter.get_agent_status(str(sample_archon_profile.id))

        assert status.status == AgentStatus.IDLE
        assert status.last_invocation is None
        assert status.last_error is None

    @pytest.mark.asyncio
    async def test_raises_not_found_for_unknown_agent(
        self,
        adapter: CrewAIAdapter,
    ) -> None:
        """Test raises AgentNotFoundError for unknown agent."""
        with pytest.raises(AgentNotFoundError):
            await adapter.get_agent_status("unknown-agent")


# ===========================================================================
# Tests: Factory Function
# ===========================================================================


class TestCreateCrewAIAdapter:
    """Tests for create_crewai_adapter factory."""

    def test_creates_adapter_with_provided_repository(
        self,
        mock_profile_repository: MagicMock,
    ) -> None:
        """Test factory uses provided repository."""
        adapter = create_crewai_adapter(
            profile_repository=mock_profile_repository,
            verbose=True,
        )

        assert adapter._profile_repo is mock_profile_repository
        assert adapter._verbose is True

    @patch("src.infrastructure.adapters.config.archon_profile_adapter.create_archon_profile_repository")
    def test_creates_default_repository_if_not_provided(
        self,
        mock_create_repo: MagicMock,
    ) -> None:
        """Test factory creates default repository if not provided."""
        mock_repo = MagicMock()
        mock_repo.count.return_value = 72
        mock_create_repo.return_value = mock_repo

        adapter = create_crewai_adapter()

        mock_create_repo.assert_called_once()
        assert adapter._profile_repo is mock_repo


# ===========================================================================
# Tests: 72 Concurrent Agents
# ===========================================================================


class TestConcurrentAgents:
    """Tests for 72 concurrent agent support."""

    @pytest.mark.asyncio
    @patch("src.infrastructure.adapters.external.crewai_adapter.Crew")
    @patch("src.infrastructure.adapters.external.crewai_adapter.Agent")
    @patch("src.infrastructure.adapters.external.crewai_adapter.Task")
    async def test_can_invoke_72_agents_concurrently(
        self,
        mock_task_class: MagicMock,
        mock_agent_class: MagicMock,
        mock_crew_class: MagicMock,
    ) -> None:
        """AC5: Test 72 concurrent agents can be instantiated."""
        # Create 72 mock profiles
        profiles = {}
        profiles_by_name = {}

        for i in range(72):
            profile_id = uuid4()
            profile = ArchonProfile(
                id=profile_id,
                name=f"Archon{i:02d}",
                aegis_rank="director" if i > 9 else "executive_director",
                original_rank="Marquis" if i > 9 else "King",
                rank_level=6 if i > 9 else 8,
                role=f"Director {i}",
                goal="Deliberate",
                backstory=f"Archon {i} backstory",
                system_prompt=f"You are Archon {i}",
                suggested_tools=[],
                allow_delegation=False,
                attributes={},
                max_members=10,
                max_legions=5,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
                llm_config=DEFAULT_LLM_CONFIG,
            )
            profiles[profile_id] = profile
            profiles_by_name[profile.name.lower()] = profile

        mock_repo = MagicMock(spec=ArchonProfileRepository)
        mock_repo.get_by_id.side_effect = lambda uid: profiles.get(uid)
        mock_repo.get_by_name.side_effect = lambda n: profiles_by_name.get(n.lower())
        mock_repo.count.return_value = 72

        mock_crew = MagicMock()
        mock_crew.kickoff.return_value = "Response"
        mock_crew_class.return_value = mock_crew

        adapter = CrewAIAdapter(profile_repository=mock_repo)

        context = ContextBundle(
            bundle_id=uuid4(),
            topic_id="topic-72",
            topic_content="Test 72 concurrent agents",
            metadata=None,
            created_at=datetime.now(timezone.utc),
        )

        requests = [
            AgentRequest(
                request_id=uuid4(),
                agent_id=profile.name,
                context=context,
            )
            for profile in profiles.values()
        ]

        outputs = await adapter.invoke_batch(requests)

        assert len(outputs) == 72
        assert all(isinstance(o, AgentOutput) for o in outputs)
