"""Shared CrewAI LLM factory for consistent adapter initialization.

Retry behavior is handled by individual adapters or CrewAI defaults.
"""

from __future__ import annotations

import os
import threading

from structlog import get_logger

from src.domain.models.llm_config import LLMConfig
from src.optional_deps.crewai import LLM

logger = get_logger(__name__)

_GLOBAL_LLM_SEMAPHORE: threading.Semaphore | None = None
_GLOBAL_LLM_SEMAPHORE_LIMIT: int | None = None


def _get_global_llm_semaphore() -> threading.Semaphore | None:
    """Return a global semaphore for throttling LLM calls if configured."""
    limit = os.getenv("CREWAI_LLM_GLOBAL_CONCURRENCY", "").strip()
    if not limit:
        return None
    try:
        value = int(limit)
    except ValueError:
        logger.warning("invalid_llm_global_concurrency", value=limit)
        return None
    if value <= 0:
        return None

    global _GLOBAL_LLM_SEMAPHORE, _GLOBAL_LLM_SEMAPHORE_LIMIT
    if _GLOBAL_LLM_SEMAPHORE is None or value != _GLOBAL_LLM_SEMAPHORE_LIMIT:
        _GLOBAL_LLM_SEMAPHORE = threading.Semaphore(value)
        _GLOBAL_LLM_SEMAPHORE_LIMIT = value
    return _GLOBAL_LLM_SEMAPHORE


class _ThrottledLLM:
    """Wrapper to throttle LLM calls with a semaphore."""

    def __init__(self, llm: LLM | object, semaphore: threading.Semaphore) -> None:
        self._llm = llm
        self._semaphore = semaphore

    def call(self, *args, **kwargs):
        with self._semaphore:
            return self._llm.call(*args, **kwargs)

    def __getattr__(self, name: str):
        return getattr(self._llm, name)


def _normalize_provider(provider: str) -> str:
    """Map LLMConfig provider to CrewAI provider prefix."""
    provider_map = {
        "anthropic": "anthropic",
        "openai": "openai",
        "google": "google",
        "local": "ollama",
        "ollama_cloud": "ollama",
    }
    return provider_map.get(provider, provider)


def _crewai_model_string(llm_config: LLMConfig) -> str:
    """Convert LLMConfig to CrewAI model string format."""
    provider = _normalize_provider(llm_config.provider)
    return f"{provider}/{llm_config.model}"


def _resolve_base_url(llm_config: LLMConfig) -> str | None:
    """Resolve base URL for providers that support custom endpoints."""
    if llm_config.base_url:
        return llm_config.base_url
    env_base_url = os.environ.get("OLLAMA_BASE_URL")
    if env_base_url:
        return env_base_url
    if (
        llm_config.provider == "ollama_cloud"
        or os.environ.get("OLLAMA_CLOUD_ENABLED", "").lower() == "true"
    ):
        return "https://ollama.com"
    if llm_config.provider == "local":
        return os.environ.get("OLLAMA_HOST", "http://localhost:11434")
    return None


def _is_ollama_cloud(llm_config: LLMConfig, base_url: str | None) -> bool:
    """Detect whether Ollama Cloud should be used."""
    if llm_config.provider == "ollama_cloud":
        return True
    if os.environ.get("OLLAMA_CLOUD_ENABLED", "").lower() == "true":
        return True
    if base_url and "ollama.com" in base_url:
        return True
    return False


def ensure_api_key(llm_config: LLMConfig) -> None:
    """Warn if required API key env var is missing for cloud providers."""
    base_url = _resolve_base_url(llm_config)
    is_ollama_cloud = _is_ollama_cloud(llm_config, base_url)
    if llm_config.provider == "local" and not is_ollama_cloud:
        return
    env_var = llm_config.api_key_env or (
        "OLLAMA_API_KEY" if is_ollama_cloud else llm_config.default_api_key_env
    )
    if not os.environ.get(env_var):
        logger.warning(
            "api_key_not_set",
            env_var=env_var,
            provider=llm_config.provider,
        )


def create_crewai_llm(llm_config: LLMConfig) -> LLM | object:
    """Create a CrewAI LLM instance from LLMConfig."""
    model_string = _crewai_model_string(llm_config)
    base_url = _resolve_base_url(llm_config)
    is_ollama_cloud = _is_ollama_cloud(llm_config, base_url)
    ensure_api_key(llm_config)
    llm_kwargs: dict[str, object] = {
        "model": model_string,
        "temperature": llm_config.temperature,
        "max_tokens": llm_config.max_tokens,
    }
    if base_url is not None:
        llm_kwargs["base_url"] = base_url
    if is_ollama_cloud:
        env_var = llm_config.api_key_env or "OLLAMA_API_KEY"
        llm_kwargs["api_key"] = os.environ.get(env_var)

    logger.info(
        "crewai_llm_initialized",
        provider=llm_config.provider,
        model=model_string,
        base_url=base_url,
        per_archon_url=llm_config.base_url is not None,
        ollama_cloud=is_ollama_cloud,
        temperature=llm_config.temperature,
        max_tokens=llm_config.max_tokens,
        timeout_ms=llm_config.timeout_ms,
    )
    try:
        llm = LLM(**llm_kwargs)
    except ImportError as exc:
        logger.warning(
            "crewai_llm_fallback",
            error=str(exc),
            model=model_string,
        )

        class _FallbackLLM:
            def __init__(self, model: str, base_url: str | None) -> None:
                self.model = model
                self.base_url = base_url

        llm = _FallbackLLM(model_string, base_url)

    semaphore = _get_global_llm_semaphore()
    if semaphore:
        logger.info(
            "crewai_llm_throttled",
            max_concurrency=_GLOBAL_LLM_SEMAPHORE_LIMIT,
        )
        return _ThrottledLLM(llm, semaphore)

    return llm


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
