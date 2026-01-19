# CrewAI Three Fates Deliberation Spike
# Validates multi-agent orchestration for petition deliberation
#
# Story: petition-0-1-crewai-multi-agent-feasibility-spike
# Status: PRELIMINARY GO (pending Python 3.11+ environment)
# Report: docs/spikes/crewai-three-fates-spike.md

from .agents import (
    ATROPOS_PERSONA,
    CLOTHO_PERSONA,
    LACHESIS_PERSONA,
    Disposition,
    FatePersona,
    create_mock_three_fates,
    create_three_fates,
)
from .crew import DeliberationCrew, DeliberationResult, create_deliberation_crew
from .tasks import (
    create_assessment_task,
    create_deliberation_tasks,
    create_position_task,
    create_vote_task,
    execute_mock_deliberation,
    extract_disposition,
)

__all__ = [
    # Personas
    "FatePersona",
    "CLOTHO_PERSONA",
    "LACHESIS_PERSONA",
    "ATROPOS_PERSONA",
    "Disposition",
    # Agent creation
    "create_three_fates",
    "create_mock_three_fates",
    # Crew orchestration
    "DeliberationCrew",
    "DeliberationResult",
    "create_deliberation_crew",
    # Tasks
    "create_assessment_task",
    "create_position_task",
    "create_vote_task",
    "create_deliberation_tasks",
    # Utilities
    "execute_mock_deliberation",
    "extract_disposition",
]
