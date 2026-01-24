"""Shared CrewAI LLM factory for infrastructure adapters.

Thin wrapper around the application-layer factory to keep layering clean.
"""

from src.application.llm.crewai_llm_factory import (
    create_crewai_llm,
    ensure_api_key,
    llm_config_from_model_string,
)

__all__ = [
    "create_crewai_llm",
    "ensure_api_key",
    "llm_config_from_model_string",
]
