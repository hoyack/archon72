"""External adapters for third-party integrations.

This package contains adapters for external services and frameworks
like CrewAI for agent orchestration.
"""

from src.infrastructure.adapters.external.crewai_adapter import (
    CrewAIAdapter,
    create_crewai_adapter,
)

__all__ = [
    "CrewAIAdapter",
    "create_crewai_adapter",
]
