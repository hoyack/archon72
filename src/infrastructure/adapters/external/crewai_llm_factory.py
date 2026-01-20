"""Shared CrewAI LLM factory for consistent adapter initialization.

Retry behavior is handled by individual adapters or CrewAI defaults.
"""

from __future__ import annotations

import os

from crewai import LLM
from structlog import get_logger

from src.domain.models.llm_config import LLMConfig

logger = get_logger(__name__)


def _normalize_provider(provider: str) -> str:
    """Map LLMConfig provider to CrewAI provider prefix."""
    provider_map = {
        "anthropic": "anthropic",
        "openai": "openai",
        "google": "google",
        "local": "ollama",
    }
    return provider_map.get(provider, provider)


def _crewai_model_string(llm_config: LLMConfig) -> str:
    """Convert LLMConfig to CrewAI model string format."""
    provider = _normalize_provider(llm_config.provider)
    return f"{provider}/{llm_config.model}"


def _resolve_ollama_host(llm_config: LLMConfig) -> str:
    """Resolve the Ollama base URL from config or environment."""
    if llm_config.base_url:
        return llm_config.base_url
    return os.environ.get("OLLAMA_HOST", "http://localhost:11434")


def ensure_api_key(llm_config: LLMConfig) -> None:
    """Warn if required API key env var is missing for cloud providers."""
    if llm_config.provider == "local":
        return
    env_var = llm_config.default_api_key_env
    if not os.environ.get(env_var):
        logger.warning(
            "api_key_not_set",
            env_var=env_var,
            provider=llm_config.provider,
        )


def create_crewai_llm(llm_config: LLMConfig) -> LLM | str:
    """Create a CrewAI LLM instance from LLMConfig."""
    ensure_api_key(llm_config)
    model_string = _crewai_model_string(llm_config)
    if llm_config.provider != "local":
        logger.info(
            "crewai_llm_initialized",
            provider=llm_config.provider,
            model=model_string,
            base_url=None,
            per_archon_url=False,
            temperature=llm_config.temperature,
            max_tokens=llm_config.max_tokens,
            timeout_ms=llm_config.timeout_ms,
        )
        return model_string

    llm_kwargs: dict[str, object] = {
        "model": model_string,
        "temperature": llm_config.temperature,
        "max_tokens": llm_config.max_tokens,
        "base_url": _resolve_ollama_host(llm_config),
    }

    logger.info(
        "crewai_llm_initialized",
        provider=llm_config.provider,
        model=model_string,
        base_url=llm_kwargs.get("base_url"),
        per_archon_url=llm_config.base_url is not None,
        temperature=llm_config.temperature,
        max_tokens=llm_config.max_tokens,
        timeout_ms=llm_config.timeout_ms,
    )
    return LLM(**llm_kwargs)


def llm_config_from_model_string(
    model_string: str,
    *,
    temperature: float,
    max_tokens: int,
    timeout_ms: int,
    base_url: str | None = None,
) -> LLMConfig:
    """Create an LLMConfig from a CrewAI model string."""
    provider = "local"
    model = model_string

    if "/" in model_string:
        provider_part, model = model_string.split("/", 1)
        provider = "local" if provider_part == "ollama" else provider_part

    return LLMConfig(
        provider=provider,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout_ms=timeout_ms,
        base_url=base_url,
    )
