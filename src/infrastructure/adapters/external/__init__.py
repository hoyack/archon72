"""External adapters for third-party integrations.

This package contains adapters for external services and frameworks
like CrewAI for agent orchestration.
"""

from src.infrastructure.adapters.external.administrative_crewai_adapter import (
    AdministrativeCrewAIAdapter,
    create_administrative_proposal_generator,
)
from src.infrastructure.adapters.external.crewai_adapter import (
    CrewAIAdapter,
    create_crewai_adapter,
)
from src.infrastructure.adapters.external.duke_proposal_crewai_adapter import (
    DukeProposalCrewAIAdapter,
    create_duke_proposal_generator,
)
from src.infrastructure.adapters.external.executive_review_crewai_adapter import (
    ExecutiveReviewCrewAIAdapter,
    create_executive_reviewer,
)
from src.infrastructure.adapters.external.in_memory_audit_bus import (
    InMemoryAuditEventBus,
)
from src.infrastructure.adapters.external.planner_crewai_adapter import (
    PlannerCrewAIAdapter,
    create_planner_agent,
)
from src.infrastructure.adapters.external.president_crewai_adapter import (
    PresidentCrewAIAdapter,
    create_president_deliberator,
)
from src.infrastructure.adapters.external.proposal_scorer_crewai_adapter import (
    ProposalScorerCrewAIAdapter,
    create_proposal_scorer,
)
from src.infrastructure.adapters.external.rfp_contributor_crewai_adapter import (
    RFPContributorCrewAIAdapter,
    create_rfp_contributor,
)
from src.infrastructure.adapters.external.secretary_crewai_adapter import (
    SecretaryCrewAIAdapter,
)
from src.infrastructure.adapters.external.tool_execution_adapter import (
    ToolExecutionAdapter,
    create_tool_executor,
)

__all__ = [
    "AdministrativeCrewAIAdapter",
    "create_administrative_proposal_generator",
    "CrewAIAdapter",
    "create_crewai_adapter",
    "DukeProposalCrewAIAdapter",
    "create_duke_proposal_generator",
    "ProposalScorerCrewAIAdapter",
    "create_proposal_scorer",
    "ExecutiveReviewCrewAIAdapter",
    "create_executive_reviewer",
    "InMemoryAuditEventBus",
    "PlannerCrewAIAdapter",
    "create_planner_agent",
    "PresidentCrewAIAdapter",
    "create_president_deliberator",
    "RFPContributorCrewAIAdapter",
    "create_rfp_contributor",
    "SecretaryCrewAIAdapter",
    "create_secretary_agent",
    "ToolExecutionAdapter",
    "create_tool_executor",
]


def create_secretary_agent(
    verbose: bool = False,
) -> SecretaryCrewAIAdapter:
    """Factory function to create a Secretary agent with CrewAI.

    Creates a SecretaryCrewAIAdapter with the default profile configuration.
    The Secretary agent uses Claude Sonnet for accurate extraction.

    Args:
        verbose: Enable verbose CrewAI logging

    Returns:
        Configured SecretaryCrewAIAdapter instance

    Example:
        >>> from src.infrastructure.adapters.external import create_secretary_agent
        >>> from src.application.services.secretary_service import SecretaryService
        >>>
        >>> agent = create_secretary_agent(verbose=True)
        >>> service = SecretaryService(secretary_agent=agent)
        >>> report = await service.process_transcript_enhanced(
        ...     "transcript.md",
        ...     session_id,
        ...     "Conclave Session 1"
        ... )
    """
    from src.domain.models.secretary_agent import create_default_secretary_profile

    profile = create_default_secretary_profile()
    return SecretaryCrewAIAdapter(profile=profile, verbose=verbose)
