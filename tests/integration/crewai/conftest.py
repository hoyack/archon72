"""Shared fixtures for CrewAI integration tests (Story 10-5).

Provides:
- API key detection and skip markers
- Real CrewAI adapter fixture
- Sample topic fixtures
- Cost tracking utilities
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from structlog import get_logger

if TYPE_CHECKING:
    from src.application.ports.archon_profile_repository import ArchonProfileRepository
    from src.application.ports.tool_registry import ToolRegistryProtocol
    from src.infrastructure.adapters.external.crewai_adapter import CrewAIAdapter

logger = get_logger(__name__)


# ===========================================================================
# API Key Detection
# ===========================================================================


def has_api_keys() -> bool:
    """Check if required LLM API keys are present.

    Returns:
        True if at least one API key is configured
    """
    return bool(
        os.environ.get("ANTHROPIC_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
    )


def get_available_provider() -> str | None:
    """Get the name of the available LLM provider.

    Returns:
        Provider name or None if no keys available
    """
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic"
    if os.environ.get("OPENAI_API_KEY"):
        return "openai"
    return None


# Custom pytest marker for tests requiring API keys
requires_api_keys = pytest.mark.skipif(
    not has_api_keys(),
    reason="No LLM API keys available (set ANTHROPIC_API_KEY or OPENAI_API_KEY)",
)


# ===========================================================================
# Cost Tracking
# ===========================================================================

# Cost estimates per 1K tokens (2025 pricing)
COST_PER_1K_TOKENS = {
    "anthropic/claude-3-opus-20240229": {"input": 0.015, "output": 0.075},
    "anthropic/claude-3-sonnet-20240229": {"input": 0.003, "output": 0.015},
    "anthropic/claude-3-5-sonnet-20241022": {"input": 0.003, "output": 0.015},
    "anthropic/claude-3-haiku-20240307": {"input": 0.00025, "output": 0.00125},
    "openai/gpt-4o": {"input": 0.005, "output": 0.015},
    "openai/gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
}

# Default cost if model not in lookup
DEFAULT_COST = {"input": 0.01, "output": 0.03}

# Maximum test cost before warning (configurable via env)
MAX_TEST_COST = float(os.environ.get("MAX_TEST_COST", "1.00"))


@dataclass
class CostEstimate:
    """Cost estimate for an LLM operation."""

    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    duration_seconds: float


def estimate_cost(
    model: str,
    input_tokens: int,
    output_tokens: int,
    duration_seconds: float = 0.0,
) -> CostEstimate:
    """Estimate cost for an LLM operation.

    Args:
        model: Model identifier (e.g., "anthropic/claude-3-sonnet-20240229")
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens
        duration_seconds: Time taken for the operation

    Returns:
        CostEstimate with calculated cost
    """
    costs = COST_PER_1K_TOKENS.get(model, DEFAULT_COST)
    cost_usd = (
        input_tokens / 1000 * costs["input"]
        + output_tokens / 1000 * costs["output"]
    )

    return CostEstimate(
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost_usd,
        duration_seconds=duration_seconds,
    )


def estimate_tokens_from_text(text: str) -> int:
    """Rough estimate of token count from text.

    Uses ~4 characters per token heuristic.

    Args:
        text: Input text

    Returns:
        Estimated token count
    """
    return len(text) // 4


# ===========================================================================
# Response Validation
# ===========================================================================


@dataclass
class ValidationResult:
    """Result of response validation."""

    is_valid: bool
    errors: list[str]
    warnings: list[str]


def validate_response(
    response: str,
    topic_keywords: list[str] | None = None,
    min_length: int = 10,
    max_length: int = 10000,
) -> ValidationResult:
    """Validate an agent response.

    Args:
        response: The response text to validate
        topic_keywords: Keywords that should appear in response
        min_length: Minimum acceptable response length
        max_length: Maximum acceptable response length

    Returns:
        ValidationResult with any errors or warnings
    """
    errors: list[str] = []
    warnings: list[str] = []

    # Check for empty response
    if not response or not response.strip():
        errors.append("Response is empty")
        return ValidationResult(is_valid=False, errors=errors, warnings=warnings)

    # Check length
    if len(response) < min_length:
        errors.append(f"Response too short ({len(response)} < {min_length})")

    if len(response) > max_length:
        warnings.append(f"Response very long ({len(response)} > {max_length})")

    # Check for error messages in response
    error_indicators = [
        "error:",
        "exception:",
        "failed to",
        "could not",
        "unable to",
    ]
    lower_response = response.lower()
    for indicator in error_indicators:
        if indicator in lower_response:
            warnings.append(f"Response may contain error: '{indicator}' found")

    # Check for topic relevance
    if topic_keywords:
        found_keywords = [
            kw for kw in topic_keywords
            if kw.lower() in lower_response
        ]
        if not found_keywords:
            warnings.append(
                f"Response may be off-topic: none of {topic_keywords} found"
            )

    return ValidationResult(
        is_valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
    )


# ===========================================================================
# Timing Context Manager
# ===========================================================================


class Timer:
    """Context manager for timing operations."""

    def __init__(self) -> None:
        self.start_time: float = 0.0
        self.end_time: float = 0.0
        self.elapsed: float = 0.0

    def __enter__(self) -> "Timer":
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, *args: object) -> None:
        self.end_time = time.perf_counter()
        self.elapsed = self.end_time - self.start_time


# ===========================================================================
# Fixtures
# ===========================================================================


@pytest.fixture
def archon_profile_repository() -> "ArchonProfileRepository":
    """Create real archon profile repository from YAML files."""
    from src.infrastructure.adapters.config.archon_profile_adapter import (
        create_archon_profile_repository,
    )
    return create_archon_profile_repository()


@pytest.fixture
def tool_registry() -> "ToolRegistryProtocol":
    """Create tool registry with all archon tools."""
    from src.infrastructure.adapters.tools.tool_registry_adapter import (
        create_tool_registry,
    )
    return create_tool_registry(include_all_archon_tools=True)


@pytest.fixture
def crewai_adapter(
    archon_profile_repository: "ArchonProfileRepository",
    tool_registry: "ToolRegistryProtocol",
) -> "CrewAIAdapter":
    """Create real CrewAI adapter for integration testing.

    This fixture creates a fully configured CrewAI adapter
    that can make real LLM API calls.
    """
    from src.infrastructure.adapters.external.crewai_adapter import CrewAIAdapter

    return CrewAIAdapter(
        profile_repository=archon_profile_repository,
        verbose=True,  # Enable for debugging during tests
        tool_registry=tool_registry,
    )


@pytest.fixture
def sample_topic() -> dict[str, str]:
    """Create a sample topic for deliberation.

    Returns simple topic dict that can be used for testing.
    """
    return {
        "topic_id": f"test-topic-{uuid4().hex[:8]}",
        "content": (
            "Should the Archon Conclave adopt a new communication protocol "
            "for inter-agent messaging? Consider security, efficiency, and "
            "compatibility with existing systems."
        ),
        "keywords": ["communication", "protocol", "security", "efficiency"],
    }


@pytest.fixture
def simple_topic() -> dict[str, str]:
    """Create a minimal topic for smoke testing.

    Returns very simple topic for fast, cheap tests.
    """
    return {
        "topic_id": f"smoke-topic-{uuid4().hex[:8]}",
        "content": "What is the most important factor in team collaboration?",
        "keywords": ["collaboration", "team", "important"],
    }


@pytest.fixture
def cost_tracker() -> list[CostEstimate]:
    """Fixture to accumulate cost estimates during a test."""
    return []


@pytest.fixture(autouse=True)
def log_test_costs(
    request: pytest.FixtureRequest,
    cost_tracker: list[CostEstimate],
) -> None:
    """Log accumulated costs after each test.

    This fixture runs after each test and logs the total cost.
    """
    yield  # Run the test

    if cost_tracker:
        total_cost = sum(c.cost_usd for c in cost_tracker)
        total_input = sum(c.input_tokens for c in cost_tracker)
        total_output = sum(c.output_tokens for c in cost_tracker)
        total_time = sum(c.duration_seconds for c in cost_tracker)

        logger.info(
            "test_cost_summary",
            test_name=request.node.name,
            total_cost_usd=f"${total_cost:.4f}",
            total_input_tokens=total_input,
            total_output_tokens=total_output,
            total_duration_seconds=f"{total_time:.2f}s",
            call_count=len(cost_tracker),
        )

        if total_cost > MAX_TEST_COST:
            logger.warning(
                "test_cost_exceeded",
                test_name=request.node.name,
                total_cost_usd=f"${total_cost:.4f}",
                max_allowed_usd=f"${MAX_TEST_COST:.2f}",
            )
