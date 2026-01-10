"""LLM configuration model for per-archon model binding.

This module defines the configuration structure for binding specific
LLM providers and models to individual Archons, enabling granular
control over which model powers each agent's deliberations.
"""

from dataclasses import dataclass
from typing import Literal

# Supported LLM providers
LLMProvider = Literal["anthropic", "openai", "google", "local"]


@dataclass(frozen=True, eq=True)
class LLMConfig:
    """Per-archon LLM binding configuration.

    Each Archon can be bound to a specific LLM provider and model,
    allowing for granular control over capabilities, costs, and
    personality fidelity across the 72-agent collective.

    Attributes:
        provider: The LLM provider (anthropic, openai, google, local)
        model: The specific model identifier (e.g., claude-3-opus, gpt-4o)
        temperature: Sampling temperature (0.0 = deterministic, 1.0 = creative)
        max_tokens: Maximum tokens in response
        timeout_ms: Request timeout in milliseconds
        api_key_env: Optional override for API key environment variable name.
                     If None, uses provider default (e.g., ANTHROPIC_API_KEY)
        base_url: Optional base URL for the LLM API endpoint.
                  For local/Ollama, this specifies the Ollama server address.
                  If None for local provider, falls back to OLLAMA_HOST env var.
                  Enables per-archon server assignment for distributed inference.
    """

    provider: LLMProvider
    model: str
    temperature: float = 0.7
    max_tokens: int = 4096
    timeout_ms: int = 30000
    api_key_env: str | None = None
    base_url: str | None = None

    def __post_init__(self) -> None:
        """Validate configuration values."""
        if not 0.0 <= self.temperature <= 1.0:
            raise ValueError(
                f"temperature must be between 0.0 and 1.0, got {self.temperature}"
            )
        if self.max_tokens < 1:
            raise ValueError(f"max_tokens must be positive, got {self.max_tokens}")
        if self.timeout_ms < 1000:
            raise ValueError(
                f"timeout_ms must be at least 1000ms, got {self.timeout_ms}"
            )

    @property
    def default_api_key_env(self) -> str:
        """Return the default environment variable name for the API key."""
        env_map = {
            "anthropic": "ANTHROPIC_API_KEY",
            "openai": "OPENAI_API_KEY",
            "google": "GOOGLE_API_KEY",
            "local": "LOCAL_LLM_API_KEY",
        }
        return self.api_key_env or env_map.get(self.provider, "LLM_API_KEY")


# Pre-defined configurations for common use cases
DEFAULT_LLM_CONFIG = LLMConfig(
    provider="anthropic",
    model="claude-3-haiku-20240307",
    temperature=0.5,
    max_tokens=2048,
    timeout_ms=30000,
)

OPUS_LLM_CONFIG = LLMConfig(
    provider="anthropic",
    model="claude-3-opus-20240229",
    temperature=0.7,
    max_tokens=4096,
    timeout_ms=60000,
)

SONNET_LLM_CONFIG = LLMConfig(
    provider="anthropic",
    model="claude-sonnet-4-20250514",
    temperature=0.7,
    max_tokens=4096,
    timeout_ms=45000,
)

GPT4O_LLM_CONFIG = LLMConfig(
    provider="openai",
    model="gpt-4o",
    temperature=0.7,
    max_tokens=4096,
    timeout_ms=30000,
)

# =============================================================================
# Local LLM Configurations (Ollama)
# =============================================================================
# These use provider="local" which maps to Ollama in the CrewAI adapter.
# Model names must match exactly what Ollama reports via `ollama list`.
# Set OLLAMA_HOST environment variable to your Ollama server address.

MINISTRAL_LLM_CONFIG = LLMConfig(
    provider="local",
    model="ministral-3:latest",
    temperature=0.7,
    max_tokens=4096,
    timeout_ms=60000,  # Local models may need more time
)

QWEN3_LLM_CONFIG = LLMConfig(
    provider="local",
    model="qwen3:latest",
    temperature=0.7,
    max_tokens=4096,
    timeout_ms=60000,
)

GEMMA3_LLM_CONFIG = LLMConfig(
    provider="local",
    model="gemma3:4b",
    temperature=0.7,
    max_tokens=2048,
    timeout_ms=45000,
)

LLAMA32_LLM_CONFIG = LLMConfig(
    provider="local",
    model="llama3.2:latest",
    temperature=0.7,
    max_tokens=4096,
    timeout_ms=60000,
)

GPT_OSS_LLM_CONFIG = LLMConfig(
    provider="local",
    model="gpt-oss:20b",
    temperature=0.7,
    max_tokens=4096,
    timeout_ms=90000,  # Larger model needs more time
)
