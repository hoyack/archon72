"""Unit tests for shared CrewAI LLM factory."""

from __future__ import annotations

from src.infrastructure.adapters.external.crewai_llm_factory import (
    create_crewai_llm,
    llm_config_from_model_string,
)


def test_llm_config_from_model_string_ollama() -> None:
    """Parse ollama model strings into local LLM configs."""
    config = llm_config_from_model_string(
        "ollama/qwen3:latest",
        temperature=0.2,
        max_tokens=2048,
        timeout_ms=30000,
        base_url="http://localhost:11434",
    )

    assert config.provider == "local"
    assert config.model == "qwen3:latest"
    assert config.temperature == 0.2
    assert config.max_tokens == 2048
    assert config.timeout_ms == 30000
    assert config.base_url == "http://localhost:11434"


def test_llm_config_from_model_string_openai() -> None:
    """Parse cloud model strings into non-local LLM configs."""
    config = llm_config_from_model_string(
        "openai/gpt-4o",
        temperature=0.4,
        max_tokens=4096,
        timeout_ms=30000,
    )

    assert config.provider == "openai"
    assert config.model == "gpt-4o"


def test_create_crewai_llm_returns_model_string() -> None:
    """Ensure CrewAI LLM object is created with normalized model string."""
    import pytest

    pytest.importorskip("litellm")
    config = llm_config_from_model_string(
        "ollama/llama3.2:latest",
        temperature=0.5,
        max_tokens=1024,
        timeout_ms=30000,
    )

    llm = create_crewai_llm(config)
    assert llm.model == "ollama/llama3.2:latest"
