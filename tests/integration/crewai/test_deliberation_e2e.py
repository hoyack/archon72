"""End-to-end deliberation tests with real LLM calls (Story 10-5).

These tests validate the complete deliberation pipeline:
- Topic submission -> ArchonSelection -> LLM invocation -> Output validation

IMPORTANT: These tests require LLM API keys to run.
Tests are automatically skipped if no API keys are configured.

Run with:
    make test-integration-crewai

Or directly:
    pytest tests/integration/crewai/ -v
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.application.ports.agent_orchestrator import (
    AgentOutput,
    AgentRequest,
    ContextBundle,
)
from src.application.ports.archon_selector import SelectionMode, TopicContext
from src.infrastructure.adapters.external.crewai_adapter import CrewAIAdapter
from src.infrastructure.adapters.selection.archon_selector_adapter import (
    create_archon_selector,
)

from .conftest import (
    CostEstimate,
    Timer,
    estimate_cost,
    estimate_tokens_from_text,
    requires_api_keys,
    validate_response,
)

# ===========================================================================
# Helpers
# ===========================================================================


def create_context_bundle(topic: dict[str, str]) -> ContextBundle:
    """Create a ContextBundle from a topic dict."""
    return ContextBundle(
        bundle_id=uuid4(),
        topic_id=topic["topic_id"],
        topic_content=topic["content"],
        metadata=None,
        created_at=datetime.now(timezone.utc),
    )


# ===========================================================================
# Single Agent Tests
# ===========================================================================


@requires_api_keys
@pytest.mark.integration
class TestSingleAgentDeliberation:
    """Tests for single agent deliberation."""

    @pytest.mark.asyncio
    async def test_single_agent_produces_output(
        self,
        crewai_adapter: CrewAIAdapter,
        simple_topic: dict[str, str],
        cost_tracker: list[CostEstimate],
    ) -> None:
        """Verify a single agent can produce deliberation output.

        AC5: Each agent produces non-empty output.
        """
        context = create_context_bundle(simple_topic)

        # Use first available archon
        agent_name = "Paimon"  # Executive director

        with Timer() as timer:
            output = await crewai_adapter.invoke(agent_name, context)

        # Validate output
        assert isinstance(output, AgentOutput)
        assert output.content is not None
        assert len(output.content) > 0
        assert output.agent_id == agent_name

        # Validate response quality
        validation = validate_response(
            output.content,
            topic_keywords=simple_topic.get("keywords"),
        )
        assert validation.is_valid, f"Response validation failed: {validation.errors}"

        # Track costs
        input_tokens = estimate_tokens_from_text(simple_topic["content"])
        output_tokens = estimate_tokens_from_text(output.content)
        cost_tracker.append(
            estimate_cost(
                model="anthropic/claude-3-5-sonnet-20241022",  # Default model
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                duration_seconds=timer.elapsed,
            )
        )

    @pytest.mark.asyncio
    async def test_different_archons_have_unique_perspectives(
        self,
        crewai_adapter: CrewAIAdapter,
        sample_topic: dict[str, str],
        cost_tracker: list[CostEstimate],
    ) -> None:
        """Verify different archons provide distinct outputs.

        Different archons should bring their unique expertise and perspective.
        """
        context = create_context_bundle(sample_topic)

        # Invoke two different archons
        archons = ["Paimon", "Barbatos"]  # Different domains

        outputs = []
        for archon in archons:
            with Timer() as timer:
                output = await crewai_adapter.invoke(archon, context)
            outputs.append(output)

            # Track costs
            input_tokens = estimate_tokens_from_text(sample_topic["content"])
            output_tokens = estimate_tokens_from_text(output.content)
            cost_tracker.append(
                estimate_cost(
                    model="anthropic/claude-3-5-sonnet-20241022",
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    duration_seconds=timer.elapsed,
                )
            )

        # Both should have valid outputs
        assert len(outputs) == 2
        assert all(len(o.content) > 0 for o in outputs)

        # Outputs should be different (not identical)
        assert outputs[0].content != outputs[1].content


# ===========================================================================
# Multi-Agent Batch Tests
# ===========================================================================


@requires_api_keys
@pytest.mark.integration
class TestMultiAgentDeliberation:
    """Tests for multi-agent concurrent deliberation."""

    @pytest.mark.asyncio
    async def test_batch_invocation_returns_all_outputs(
        self,
        crewai_adapter: CrewAIAdapter,
        archon_profile_repository,
        sample_topic: dict[str, str],
        cost_tracker: list[CostEstimate],
    ) -> None:
        """Verify batch invocation returns output for all agents.

        AC2: Full pipeline validation with multiple agents.
        AC3: Configurable agent count.
        """
        context = create_context_bundle(sample_topic)

        # Get a few archons
        archons = archon_profile_repository.get_all()[:3]
        assert len(archons) >= 3, "Need at least 3 archons for this test"

        # Create batch requests
        requests = [
            AgentRequest(
                request_id=uuid4(),
                agent_id=str(archon.id),
                context=context,
            )
            for archon in archons
        ]

        with Timer() as timer:
            outputs = await crewai_adapter.invoke_batch(requests)

        # All should return outputs
        assert len(outputs) == len(requests)

        # Validate each output
        for output in outputs:
            assert isinstance(output, AgentOutput)
            assert len(output.content) > 0

            # Track costs
            input_tokens = estimate_tokens_from_text(sample_topic["content"])
            output_tokens = estimate_tokens_from_text(output.content)
            cost_tracker.append(
                estimate_cost(
                    model="anthropic/claude-3-5-sonnet-20241022",
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    duration_seconds=timer.elapsed / len(outputs),
                )
            )


# ===========================================================================
# Selection Integration Tests
# ===========================================================================


@requires_api_keys
@pytest.mark.integration
class TestSelectionWithDeliberation:
    """Tests for archon selection integrated with deliberation."""

    @pytest.mark.asyncio
    async def test_relevant_selection_deliberates_successfully(
        self,
        crewai_adapter: CrewAIAdapter,
        archon_profile_repository,
        cost_tracker: list[CostEstimate],
    ) -> None:
        """Verify RELEVANT selection produces valid deliberation.

        Tests full pipeline: Topic -> Selection -> Deliberation -> Output
        """
        # Create topic context for selection
        topic = TopicContext(
            topic_id=f"selection-test-{uuid4().hex[:8]}",
            content=(
                "How should the network optimize inter-agent communication "
                "to reduce latency and improve consensus building?"
            ),
            keywords=["communication", "consensus", "latency"],
            required_tools=["communication_tool"],
            domain_hint="communications",
            required_capabilities=["diplomatic communication"],
        )

        # Use selector to find relevant archons
        selector = create_archon_selector(profile_repository=archon_profile_repository)

        selection = selector.select(
            topic=topic,
            mode=SelectionMode.RELEVANT,
            min_archons=1,
            max_archons=3,
            relevance_threshold=0.1,
        )

        # Should have selected some archons
        assert len(selection.archons) > 0

        # Create context bundle for deliberation
        context = ContextBundle(
            bundle_id=uuid4(),
            topic_id=topic.topic_id,
            topic_content=topic.content,
            metadata=None,
            created_at=datetime.now(timezone.utc),
        )

        # Invoke the selected archons
        requests = [
            AgentRequest(
                request_id=uuid4(),
                agent_id=str(archon.id),
                context=context,
            )
            for archon in selection.archons
        ]

        with Timer() as timer:
            outputs = await crewai_adapter.invoke_batch(requests)

        # All selected archons should produce output
        assert len(outputs) == len(selection.archons)

        for output in outputs:
            # Validate response quality
            validation = validate_response(
                output.content,
                topic_keywords=topic.keywords,
            )
            assert validation.is_valid, (
                f"Response validation failed: {validation.errors}"
            )

            # Track costs
            input_tokens = estimate_tokens_from_text(topic.content)
            output_tokens = estimate_tokens_from_text(output.content)
            cost_tracker.append(
                estimate_cost(
                    model="anthropic/claude-3-5-sonnet-20241022",
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    duration_seconds=timer.elapsed / len(outputs),
                )
            )


# ===========================================================================
# Smoke Test
# ===========================================================================


@requires_api_keys
@pytest.mark.integration
@pytest.mark.smoke
class TestSmoke:
    """Quick smoke tests for CI validation.

    AC7: Smoke test with 1-3 agents, simple topic, < 30 seconds.
    """

    @pytest.mark.asyncio
    @pytest.mark.timeout(60)  # 60 second timeout
    async def test_smoke_deliberation(
        self,
        crewai_adapter: CrewAIAdapter,
        simple_topic: dict[str, str],
        cost_tracker: list[CostEstimate],
    ) -> None:
        """Quick validation that deliberation works.

        This test uses 2 agents with a simple topic for fast,
        cheap validation in CI pipelines.
        """
        context = create_context_bundle(simple_topic)

        # Use only 2 archons for smoke test
        archons = ["Paimon", "Barbatos"]

        requests = [
            AgentRequest(
                request_id=uuid4(),
                agent_id=archon,
                context=context,
            )
            for archon in archons
        ]

        with Timer() as timer:
            outputs = await crewai_adapter.invoke_batch(requests)

        # Basic validation
        assert len(outputs) == 2
        assert all(len(o.content) > 0 for o in outputs)

        # Track costs
        for output in outputs:
            cost_tracker.append(
                estimate_cost(
                    model="anthropic/claude-3-5-sonnet-20241022",
                    input_tokens=estimate_tokens_from_text(simple_topic["content"]),
                    output_tokens=estimate_tokens_from_text(output.content),
                    duration_seconds=timer.elapsed / 2,
                )
            )


# ===========================================================================
# Load Test
# ===========================================================================


@requires_api_keys
@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.load
class TestLoad:
    """Load tests for 72 concurrent agents.

    AC8: Load test with all 72 agents to validate NFR5.

    WARNING: This test is expensive! Estimated cost: $0.50-2.00 per run.
    Only run when explicitly needed.
    """

    @pytest.mark.asyncio
    @pytest.mark.timeout(300)  # 5 minute timeout
    async def test_load_72_concurrent_agents(
        self,
        crewai_adapter: CrewAIAdapter,
        archon_profile_repository,
        simple_topic: dict[str, str],
        cost_tracker: list[CostEstimate],
    ) -> None:
        """Validate 72 concurrent agent deliberations.

        This test validates:
        - FR10: 72 agents can deliberate concurrently
        - NFR5: No performance degradation
        - CT-11: No silent failures

        Note: Uses simple topic to minimize cost.
        """
        context = create_context_bundle(simple_topic)

        # Get all 72 archons
        all_archons = archon_profile_repository.get_all()
        assert len(all_archons) >= 72, f"Expected 72 archons, got {len(all_archons)}"

        # Create requests for all archons
        requests = [
            AgentRequest(
                request_id=uuid4(),
                agent_id=str(archon.id),
                context=context,
            )
            for archon in all_archons[:72]  # Limit to 72
        ]

        # Invoke all 72 concurrently
        with Timer() as timer:
            outputs = await crewai_adapter.invoke_batch(requests)

        # All 72 should return outputs (CT-11: no silent failures)
        assert len(outputs) == 72, f"Expected 72 outputs, got {len(outputs)}"

        # Validate all outputs are non-empty
        for i, output in enumerate(outputs):
            assert isinstance(output, AgentOutput), f"Output {i} is not AgentOutput"
            assert len(output.content) > 0, f"Output {i} is empty"

        # Performance check: Total time should be reasonable
        # With concurrent execution, should complete faster than 72 * single_agent_time
        # Expect ~30-60 seconds for all 72 with good parallelism
        assert timer.elapsed < 180, f"Load test too slow: {timer.elapsed:.1f}s"

        # Track aggregate cost
        total_input = estimate_tokens_from_text(simple_topic["content"]) * 72
        total_output = sum(estimate_tokens_from_text(o.content) for o in outputs)
        cost_tracker.append(
            estimate_cost(
                model="anthropic/claude-3-5-sonnet-20241022",
                input_tokens=total_input,
                output_tokens=total_output,
                duration_seconds=timer.elapsed,
            )
        )
