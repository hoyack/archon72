"""Governance projections domain models.

This module defines the domain models for governance system projections.
Projections are derived views of ledger state that enable efficient querying.

Story: consent-gov-1.5: Projection Infrastructure

CQRS-Lite Pattern (AD-9):
- Projections are DERIVED from ledger, never authoritative
- Can be rebuilt from ledger replay at any time
- Enable fast reads without replaying all events

Available projection records:
- TaskStateRecord: Task lifecycle state (from executive.task.* events)
- LegitimacyStateRecord: Entity legitimacy bands (from legitimacy.* events)
- PanelRegistryRecord: Prince panel tracking (from judicial.panel.* events)
- PetitionIndexRecord: Exit/dignity petitions (from petition.* events)
- ActorRegistryRecord: Known actors (from actor.* events)

References:
- [Source: _bmad-output/planning-artifacts/governance-architecture.md#Initial Projection Set (Locked)]
"""

from src.domain.governance.projections.actor_registry import ActorRegistryRecord
from src.domain.governance.projections.event_handlers import (
    EVENT_PREFIX_TO_PROJECTION,
    ProjectionUpdate,
    get_affected_projection,
    get_projection_updates,
)
from src.domain.governance.projections.legitimacy_state import LegitimacyStateRecord
from src.domain.governance.projections.panel_registry import PanelRegistryRecord
from src.domain.governance.projections.petition_index import PetitionIndexRecord
from src.domain.governance.projections.task_state import TaskStateRecord

__all__ = [
    # Projection record models
    "TaskStateRecord",
    "LegitimacyStateRecord",
    "PanelRegistryRecord",
    "PetitionIndexRecord",
    "ActorRegistryRecord",
    # Event handlers
    "ProjectionUpdate",
    "get_projection_updates",
    "get_affected_projection",
    "EVENT_PREFIX_TO_PROJECTION",
]
