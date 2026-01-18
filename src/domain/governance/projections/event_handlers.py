"""Event-to-projection mapping for governance projections.

Story: consent-gov-1.5: Projection Infrastructure

This module defines the mapping from governance event types to projection
updates. Each event type specifies how it affects projection state.

Event Type Convention: branch.noun.verb
- branch: legislative, executive, judicial, advisory, witness, system
- noun: task, legitimacy, panel, petition, actor
- verb: created, updated, activated, completed, etc.

Deterministic State Derivation (NFR-AUDIT-06):
- Same events applied in same order produce identical projection state
- Handlers are pure functions (no side effects beyond projection updates)
- All state changes are derived from event payload

References:
- [Source: _bmad-output/planning-artifacts/governance-architecture.md#Event Type Vocabulary]
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.domain.governance.events.event_envelope import GovernanceEvent


# Event type prefixes for routing
TASK_EVENT_PREFIX = "executive.task."
LEGITIMACY_EVENT_PREFIX = "legitimacy."
PANEL_EVENT_PREFIX = "judicial.panel."
PETITION_EVENT_PREFIX = "petition."
ACTOR_EVENT_PREFIX = "actor."


@dataclass(frozen=True)
class ProjectionUpdate:
    """Describes an update to a projection from an event.

    Attributes:
        projection_name: Name of the projection to update.
        entity_id: ID of the entity being updated (task_id, entity_id, etc.).
        update_type: Type of update (create, update, delete).
        fields: Dict of field names to new values.
    """

    projection_name: str
    entity_id: str
    update_type: str  # "create", "update", "delete"
    fields: dict[str, Any]


def get_projection_updates(
    event: GovernanceEvent,
    sequence: int,
    now: datetime,
) -> list[ProjectionUpdate]:
    """Determine projection updates for an event.

    This is the main routing function that maps events to projection updates.
    Returns a list because one event may update multiple projections.

    Args:
        event: The governance event to process.
        sequence: The ledger sequence number.
        now: Current timestamp for updated_at fields.

    Returns:
        List of ProjectionUpdate instances describing updates to make.
    """
    event_type = event.event_type
    updates: list[ProjectionUpdate] = []

    # Route to appropriate handler based on event type prefix
    if event_type.startswith(TASK_EVENT_PREFIX):
        updates.extend(_handle_task_event(event, sequence, now))
    elif event_type.startswith(LEGITIMACY_EVENT_PREFIX):
        updates.extend(_handle_legitimacy_event(event, sequence, now))
    elif event_type.startswith(PANEL_EVENT_PREFIX):
        updates.extend(_handle_panel_event(event, sequence, now))
    elif event_type.startswith(PETITION_EVENT_PREFIX):
        updates.extend(_handle_petition_event(event, sequence, now))
    elif event_type.startswith(ACTOR_EVENT_PREFIX):
        updates.extend(_handle_actor_event(event, sequence, now))

    return updates


# =============================================================================
# Task Event Handlers
# =============================================================================


def _handle_task_event(
    event: GovernanceEvent,
    sequence: int,
    now: datetime,
) -> list[ProjectionUpdate]:
    """Handle executive.task.* events."""
    event_type = event.event_type
    payload = dict(event.payload)
    task_id = payload.get("task_id", "")

    updates = []

    if event_type == "executive.task.created":
        updates.append(
            ProjectionUpdate(
                projection_name="task_states",
                entity_id=str(task_id),
                update_type="create",
                fields={
                    "task_id": task_id,
                    "current_state": "pending",
                    "earl_id": payload.get("earl_id", ""),
                    "cluster_id": payload.get("cluster_id"),
                    "task_type": payload.get("task_type"),
                    "created_at": event.timestamp,
                    "state_entered_at": event.timestamp,
                    "last_event_sequence": sequence,
                    "last_event_hash": event.hash,
                    "updated_at": now,
                },
            )
        )
    elif event_type == "executive.task.authorized":
        updates.append(
            ProjectionUpdate(
                projection_name="task_states",
                entity_id=str(task_id),
                update_type="update",
                fields={
                    "current_state": "authorized",
                    "state_entered_at": event.timestamp,
                    "last_event_sequence": sequence,
                    "last_event_hash": event.hash,
                    "updated_at": now,
                },
            )
        )
    elif event_type == "executive.task.activated":
        updates.append(
            ProjectionUpdate(
                projection_name="task_states",
                entity_id=str(task_id),
                update_type="update",
                fields={
                    "current_state": "activated",
                    "state_entered_at": event.timestamp,
                    "last_event_sequence": sequence,
                    "last_event_hash": event.hash,
                    "updated_at": now,
                },
            )
        )
    elif event_type == "executive.task.accepted":
        updates.append(
            ProjectionUpdate(
                projection_name="task_states",
                entity_id=str(task_id),
                update_type="update",
                fields={
                    "current_state": "accepted",
                    "state_entered_at": event.timestamp,
                    "last_event_sequence": sequence,
                    "last_event_hash": event.hash,
                    "updated_at": now,
                },
            )
        )
    elif event_type == "executive.task.completed":
        updates.append(
            ProjectionUpdate(
                projection_name="task_states",
                entity_id=str(task_id),
                update_type="update",
                fields={
                    "current_state": "completed",
                    "state_entered_at": event.timestamp,
                    "last_event_sequence": sequence,
                    "last_event_hash": event.hash,
                    "updated_at": now,
                },
            )
        )
    elif event_type == "executive.task.declined":
        updates.append(
            ProjectionUpdate(
                projection_name="task_states",
                entity_id=str(task_id),
                update_type="update",
                fields={
                    "current_state": "declined",
                    "state_entered_at": event.timestamp,
                    "last_event_sequence": sequence,
                    "last_event_hash": event.hash,
                    "updated_at": now,
                },
            )
        )
    elif event_type == "executive.task.expired":
        updates.append(
            ProjectionUpdate(
                projection_name="task_states",
                entity_id=str(task_id),
                update_type="update",
                fields={
                    "current_state": "expired",
                    "state_entered_at": event.timestamp,
                    "last_event_sequence": sequence,
                    "last_event_hash": event.hash,
                    "updated_at": now,
                },
            )
        )

    return updates


# =============================================================================
# Legitimacy Event Handlers
# =============================================================================


def _handle_legitimacy_event(
    event: GovernanceEvent,
    sequence: int,
    now: datetime,
) -> list[ProjectionUpdate]:
    """Handle legitimacy.* events."""
    event_type = event.event_type
    payload = dict(event.payload)
    entity_id = payload.get("entity_id", "")

    updates = []

    if event_type == "legitimacy.entity.registered":
        updates.append(
            ProjectionUpdate(
                projection_name="legitimacy_states",
                entity_id=entity_id,
                update_type="create",
                fields={
                    "entity_id": entity_id,
                    "entity_type": payload.get("entity_type", "unknown"),
                    "current_band": "full",  # Start with full legitimacy
                    "band_entered_at": event.timestamp,
                    "violation_count": 0,
                    "last_violation_at": None,
                    "last_restoration_at": None,
                    "last_event_sequence": sequence,
                    "updated_at": now,
                },
            )
        )
    elif event_type == "legitimacy.band.decayed":
        new_band = payload.get("new_band", "provisional")
        updates.append(
            ProjectionUpdate(
                projection_name="legitimacy_states",
                entity_id=entity_id,
                update_type="update",
                fields={
                    "current_band": new_band,
                    "band_entered_at": event.timestamp,
                    "violation_count": payload.get("violation_count", 0),
                    "last_violation_at": event.timestamp,
                    "last_event_sequence": sequence,
                    "updated_at": now,
                },
            )
        )
    elif event_type == "legitimacy.band.restored":
        new_band = payload.get("new_band", "provisional")
        updates.append(
            ProjectionUpdate(
                projection_name="legitimacy_states",
                entity_id=entity_id,
                update_type="update",
                fields={
                    "current_band": new_band,
                    "band_entered_at": event.timestamp,
                    "last_restoration_at": event.timestamp,
                    "last_event_sequence": sequence,
                    "updated_at": now,
                },
            )
        )

    return updates


# =============================================================================
# Panel Event Handlers
# =============================================================================


def _handle_panel_event(
    event: GovernanceEvent,
    sequence: int,
    now: datetime,
) -> list[ProjectionUpdate]:
    """Handle judicial.panel.* events."""
    event_type = event.event_type
    payload = dict(event.payload)
    panel_id = payload.get("panel_id", "")

    updates = []

    if event_type == "judicial.panel.requested":
        updates.append(
            ProjectionUpdate(
                projection_name="panel_registry",
                entity_id=str(panel_id),
                update_type="create",
                fields={
                    "panel_id": panel_id,
                    "panel_status": "pending",
                    "violation_id": payload.get("violation_id"),
                    "prince_ids": payload.get("prince_ids", []),
                    "petitioner_id": payload.get("petitioner_id"),
                    "convened_at": None,
                    "finding_issued_at": None,
                    "finding_outcome": None,
                    "last_event_sequence": sequence,
                    "updated_at": now,
                },
            )
        )
    elif event_type == "judicial.panel.convened":
        updates.append(
            ProjectionUpdate(
                projection_name="panel_registry",
                entity_id=str(panel_id),
                update_type="update",
                fields={
                    "panel_status": "convened",
                    "convened_at": event.timestamp,
                    "last_event_sequence": sequence,
                    "updated_at": now,
                },
            )
        )
    elif event_type == "judicial.panel.deliberating":
        updates.append(
            ProjectionUpdate(
                projection_name="panel_registry",
                entity_id=str(panel_id),
                update_type="update",
                fields={
                    "panel_status": "deliberating",
                    "last_event_sequence": sequence,
                    "updated_at": now,
                },
            )
        )
    elif event_type == "judicial.panel.finding_issued":
        updates.append(
            ProjectionUpdate(
                projection_name="panel_registry",
                entity_id=str(panel_id),
                update_type="update",
                fields={
                    "panel_status": "finding_issued",
                    "finding_issued_at": event.timestamp,
                    "finding_outcome": payload.get("outcome"),
                    "last_event_sequence": sequence,
                    "updated_at": now,
                },
            )
        )
    elif event_type == "judicial.panel.dissolved":
        updates.append(
            ProjectionUpdate(
                projection_name="panel_registry",
                entity_id=str(panel_id),
                update_type="update",
                fields={
                    "panel_status": "dissolved",
                    "last_event_sequence": sequence,
                    "updated_at": now,
                },
            )
        )

    return updates


# =============================================================================
# Petition Event Handlers
# =============================================================================


def _handle_petition_event(
    event: GovernanceEvent,
    sequence: int,
    now: datetime,
) -> list[ProjectionUpdate]:
    """Handle petition.* events."""
    event_type = event.event_type
    payload = dict(event.payload)
    petition_id = payload.get("petition_id", "")

    updates = []

    if event_type == "petition.filed":
        updates.append(
            ProjectionUpdate(
                projection_name="petition_index",
                entity_id=str(petition_id),
                update_type="create",
                fields={
                    "petition_id": petition_id,
                    "petition_type": payload.get("petition_type", "review"),
                    "subject_entity_id": payload.get("subject_entity_id", ""),
                    "petitioner_id": payload.get("petitioner_id", ""),
                    "current_status": "filed",
                    "filed_at": event.timestamp,
                    "acknowledged_at": None,
                    "resolved_at": None,
                    "resolution_outcome": None,
                    "last_event_sequence": sequence,
                    "updated_at": now,
                },
            )
        )
    elif event_type == "petition.acknowledged":
        updates.append(
            ProjectionUpdate(
                projection_name="petition_index",
                entity_id=str(petition_id),
                update_type="update",
                fields={
                    "current_status": "acknowledged",
                    "acknowledged_at": event.timestamp,
                    "last_event_sequence": sequence,
                    "updated_at": now,
                },
            )
        )
    elif event_type == "petition.under_review":
        updates.append(
            ProjectionUpdate(
                projection_name="petition_index",
                entity_id=str(petition_id),
                update_type="update",
                fields={
                    "current_status": "under_review",
                    "last_event_sequence": sequence,
                    "updated_at": now,
                },
            )
        )
    elif event_type == "petition.resolved":
        updates.append(
            ProjectionUpdate(
                projection_name="petition_index",
                entity_id=str(petition_id),
                update_type="update",
                fields={
                    "current_status": "resolved",
                    "resolved_at": event.timestamp,
                    "resolution_outcome": payload.get("outcome"),
                    "last_event_sequence": sequence,
                    "updated_at": now,
                },
            )
        )

    return updates


# =============================================================================
# Actor Event Handlers
# =============================================================================


def _handle_actor_event(
    event: GovernanceEvent,
    sequence: int,
    now: datetime,
) -> list[ProjectionUpdate]:
    """Handle actor.* events."""
    event_type = event.event_type
    payload = dict(event.payload)
    actor_id = payload.get("actor_id", "")

    updates = []

    if event_type == "actor.registered":
        updates.append(
            ProjectionUpdate(
                projection_name="actor_registry",
                entity_id=actor_id,
                update_type="create",
                fields={
                    "actor_id": actor_id,
                    "actor_type": payload.get("actor_type", "archon"),
                    "branch": payload.get("branch", "legislative"),
                    "rank": payload.get("rank"),
                    "display_name": payload.get("display_name"),
                    "active": True,
                    "created_at": event.timestamp,
                    "deactivated_at": None,
                    "last_event_sequence": sequence,
                    "updated_at": now,
                },
            )
        )
    elif event_type == "actor.updated":
        updates.append(
            ProjectionUpdate(
                projection_name="actor_registry",
                entity_id=actor_id,
                update_type="update",
                fields={
                    "rank": payload.get("rank"),
                    "display_name": payload.get("display_name"),
                    "last_event_sequence": sequence,
                    "updated_at": now,
                },
            )
        )
    elif event_type == "actor.deactivated":
        updates.append(
            ProjectionUpdate(
                projection_name="actor_registry",
                entity_id=actor_id,
                update_type="update",
                fields={
                    "active": False,
                    "deactivated_at": event.timestamp,
                    "last_event_sequence": sequence,
                    "updated_at": now,
                },
            )
        )
    elif event_type == "actor.reactivated":
        updates.append(
            ProjectionUpdate(
                projection_name="actor_registry",
                entity_id=actor_id,
                update_type="update",
                fields={
                    "active": True,
                    "deactivated_at": None,
                    "last_event_sequence": sequence,
                    "updated_at": now,
                },
            )
        )

    return updates


# =============================================================================
# Projection Name Mappings
# =============================================================================

# Map event type prefixes to projection names
EVENT_PREFIX_TO_PROJECTION: dict[str, str] = {
    TASK_EVENT_PREFIX: "task_states",
    LEGITIMACY_EVENT_PREFIX: "legitimacy_states",
    PANEL_EVENT_PREFIX: "panel_registry",
    PETITION_EVENT_PREFIX: "petition_index",
    ACTOR_EVENT_PREFIX: "actor_registry",
}


def get_affected_projection(event_type: str) -> str | None:
    """Get the projection name affected by an event type.

    Args:
        event_type: The event type (e.g., "executive.task.created").

    Returns:
        Projection name, or None if event type doesn't affect any projection.
    """
    for prefix, projection in EVENT_PREFIX_TO_PROJECTION.items():
        if event_type.startswith(prefix):
            return projection
    return None
