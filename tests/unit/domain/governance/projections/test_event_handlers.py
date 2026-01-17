"""Unit tests for event-to-projection mapping handlers.

Tests cover acceptance criteria for story consent-gov-1.5:
- AC5: Idempotent event application (handlers produce same output for same input)
- AC8: Comprehensive unit tests for projection behavior
- Deterministic state derivation (NFR-AUDIT-06)
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping
from uuid import UUID, uuid4

import pytest

from src.domain.governance.events.event_envelope import GovernanceEvent
from src.domain.governance.projections.event_handlers import (
    EVENT_PREFIX_TO_PROJECTION,
    ACTOR_EVENT_PREFIX,
    LEGITIMACY_EVENT_PREFIX,
    PANEL_EVENT_PREFIX,
    PETITION_EVENT_PREFIX,
    TASK_EVENT_PREFIX,
    ProjectionUpdate,
    get_affected_projection,
    get_projection_updates,
)


@dataclass(frozen=True)
class MockGovernanceEvent:
    """Mock GovernanceEvent for testing event handlers with non-standard event types.

    The event handlers handle some event types that don't match the strict
    branch.noun.verb validation pattern (e.g., petition.filed, actor.registered).
    This mock allows testing those handlers without validation.
    """

    event_id: UUID
    event_type: str
    timestamp: datetime
    payload: Mapping[str, Any]
    hash: str = ""

    @classmethod
    def create(
        cls,
        event_type: str,
        payload: dict[str, Any],
        event_id: UUID | None = None,
        timestamp: datetime | None = None,
    ) -> "MockGovernanceEvent":
        """Create a mock event for testing."""
        return cls(
            event_id=event_id or uuid4(),
            event_type=event_type,
            timestamp=timestamp or datetime.now(timezone.utc),
            payload=payload,
        )


class TestProjectionUpdateDataclass:
    """Tests for ProjectionUpdate dataclass."""

    def test_projection_update_creation(self) -> None:
        """ProjectionUpdate with valid data creates successfully."""
        update = ProjectionUpdate(
            projection_name="task_states",
            entity_id="task-001",
            update_type="create",
            fields={"current_state": "pending", "task_id": "task-001"},
        )

        assert update.projection_name == "task_states"
        assert update.entity_id == "task-001"
        assert update.update_type == "create"
        assert update.fields["current_state"] == "pending"

    def test_projection_update_is_immutable(self) -> None:
        """ProjectionUpdate is frozen (immutable)."""
        update = ProjectionUpdate(
            projection_name="task_states",
            entity_id="task-001",
            update_type="create",
            fields={"current_state": "pending"},
        )

        with pytest.raises(AttributeError):
            update.projection_name = "other"  # type: ignore[misc]


class TestGetAffectedProjection:
    """Tests for get_affected_projection function."""

    def test_task_event_returns_task_states_projection(self) -> None:
        """executive.task.* events return task_states projection."""
        assert get_affected_projection("executive.task.created") == "task_states"
        assert get_affected_projection("executive.task.accepted") == "task_states"
        assert get_affected_projection("executive.task.completed") == "task_states"

    def test_legitimacy_event_returns_legitimacy_states_projection(self) -> None:
        """legitimacy.* events return legitimacy_states projection."""
        assert get_affected_projection("legitimacy.entity.registered") == "legitimacy_states"
        assert get_affected_projection("legitimacy.band.decayed") == "legitimacy_states"
        assert get_affected_projection("legitimacy.band.restored") == "legitimacy_states"

    def test_panel_event_returns_panel_registry_projection(self) -> None:
        """judicial.panel.* events return panel_registry projection."""
        assert get_affected_projection("judicial.panel.requested") == "panel_registry"
        assert get_affected_projection("judicial.panel.convened") == "panel_registry"
        assert get_affected_projection("judicial.panel.dissolved") == "panel_registry"

    def test_petition_event_returns_petition_index_projection(self) -> None:
        """petition.* events return petition_index projection."""
        assert get_affected_projection("petition.filed") == "petition_index"
        assert get_affected_projection("petition.acknowledged") == "petition_index"
        assert get_affected_projection("petition.resolved") == "petition_index"

    def test_actor_event_returns_actor_registry_projection(self) -> None:
        """actor.* events return actor_registry projection."""
        assert get_affected_projection("actor.registered") == "actor_registry"
        assert get_affected_projection("actor.updated") == "actor_registry"
        assert get_affected_projection("actor.deactivated") == "actor_registry"

    def test_unknown_event_returns_none(self) -> None:
        """Unknown event types return None."""
        assert get_affected_projection("unknown.event.type") is None
        assert get_affected_projection("custom.something.else") is None


class TestEventPrefixToProjectionMapping:
    """Tests for EVENT_PREFIX_TO_PROJECTION constant."""

    def test_mapping_contains_all_prefixes(self) -> None:
        """Mapping contains all expected event prefixes."""
        assert TASK_EVENT_PREFIX in EVENT_PREFIX_TO_PROJECTION
        assert LEGITIMACY_EVENT_PREFIX in EVENT_PREFIX_TO_PROJECTION
        assert PANEL_EVENT_PREFIX in EVENT_PREFIX_TO_PROJECTION
        assert PETITION_EVENT_PREFIX in EVENT_PREFIX_TO_PROJECTION
        assert ACTOR_EVENT_PREFIX in EVENT_PREFIX_TO_PROJECTION

    def test_mapping_values_are_projection_names(self) -> None:
        """Mapping values are correct projection names."""
        assert EVENT_PREFIX_TO_PROJECTION[TASK_EVENT_PREFIX] == "task_states"
        assert EVENT_PREFIX_TO_PROJECTION[LEGITIMACY_EVENT_PREFIX] == "legitimacy_states"
        assert EVENT_PREFIX_TO_PROJECTION[PANEL_EVENT_PREFIX] == "panel_registry"
        assert EVENT_PREFIX_TO_PROJECTION[PETITION_EVENT_PREFIX] == "petition_index"
        assert EVENT_PREFIX_TO_PROJECTION[ACTOR_EVENT_PREFIX] == "actor_registry"


class TestGetProjectionUpdatesTaskEvents:
    """Tests for task event projection updates."""

    def _create_event(self, event_type: str, payload: dict) -> GovernanceEvent:
        """Helper to create a GovernanceEvent."""
        return GovernanceEvent.create(
            event_id=uuid4(),
            event_type=event_type,
            timestamp=datetime.now(timezone.utc),
            actor_id="test-actor",
            trace_id="test-trace",
            payload=payload,
        )

    def test_task_created_produces_create_update(self) -> None:
        """executive.task.created produces create update."""
        event = self._create_event(
            "executive.task.created",
            {"task_id": "task-001", "earl_id": "earl-42", "cluster_id": "cluster-1"},
        )
        now = datetime.now(timezone.utc)

        updates = get_projection_updates(event, sequence=1, now=now)

        assert len(updates) == 1
        update = updates[0]
        assert update.projection_name == "task_states"
        assert update.entity_id == "task-001"
        assert update.update_type == "create"
        assert update.fields["current_state"] == "pending"
        assert update.fields["earl_id"] == "earl-42"
        assert update.fields["last_event_sequence"] == 1

    def test_task_accepted_produces_update(self) -> None:
        """executive.task.accepted produces update."""
        event = self._create_event(
            "executive.task.accepted",
            {"task_id": "task-001"},
        )
        now = datetime.now(timezone.utc)

        updates = get_projection_updates(event, sequence=5, now=now)

        assert len(updates) == 1
        update = updates[0]
        assert update.projection_name == "task_states"
        assert update.entity_id == "task-001"
        assert update.update_type == "update"
        assert update.fields["current_state"] == "accepted"

    def test_task_completed_produces_update(self) -> None:
        """executive.task.completed produces update."""
        event = self._create_event(
            "executive.task.completed",
            {"task_id": "task-001"},
        )
        now = datetime.now(timezone.utc)

        updates = get_projection_updates(event, sequence=10, now=now)

        assert len(updates) == 1
        update = updates[0]
        assert update.fields["current_state"] == "completed"

    def test_task_declined_produces_update(self) -> None:
        """executive.task.declined produces update."""
        event = self._create_event(
            "executive.task.declined",
            {"task_id": "task-001"},
        )
        now = datetime.now(timezone.utc)

        updates = get_projection_updates(event, sequence=5, now=now)

        assert len(updates) == 1
        assert updates[0].fields["current_state"] == "declined"

    def test_task_expired_produces_update(self) -> None:
        """executive.task.expired produces update."""
        event = self._create_event(
            "executive.task.expired",
            {"task_id": "task-001"},
        )
        now = datetime.now(timezone.utc)

        updates = get_projection_updates(event, sequence=5, now=now)

        assert len(updates) == 1
        assert updates[0].fields["current_state"] == "expired"


class TestGetProjectionUpdatesLegitimacyEvents:
    """Tests for legitimacy event projection updates."""

    def _create_event(self, event_type: str, payload: dict) -> GovernanceEvent:
        """Helper to create a GovernanceEvent."""
        return GovernanceEvent.create(
            event_id=uuid4(),
            event_type=event_type,
            timestamp=datetime.now(timezone.utc),
            actor_id="test-actor",
            trace_id="test-trace",
            payload=payload,
        )

    def test_entity_registered_produces_create_update(self) -> None:
        """legitimacy.entity.registered produces create update."""
        event = self._create_event(
            "legitimacy.entity.registered",
            {"entity_id": "archon-42", "entity_type": "archon"},
        )
        now = datetime.now(timezone.utc)

        updates = get_projection_updates(event, sequence=1, now=now)

        assert len(updates) == 1
        update = updates[0]
        assert update.projection_name == "legitimacy_states"
        assert update.entity_id == "archon-42"
        assert update.update_type == "create"
        assert update.fields["current_band"] == "full"
        assert update.fields["violation_count"] == 0

    def test_band_decayed_produces_update(self) -> None:
        """legitimacy.band.decayed produces update."""
        event = self._create_event(
            "legitimacy.band.decayed",
            {"entity_id": "archon-42", "new_band": "provisional", "violation_count": 1},
        )
        now = datetime.now(timezone.utc)

        updates = get_projection_updates(event, sequence=5, now=now)

        assert len(updates) == 1
        update = updates[0]
        assert update.fields["current_band"] == "provisional"
        assert update.fields["violation_count"] == 1

    def test_band_restored_produces_update(self) -> None:
        """legitimacy.band.restored produces update."""
        event = self._create_event(
            "legitimacy.band.restored",
            {"entity_id": "archon-42", "new_band": "full"},
        )
        now = datetime.now(timezone.utc)

        updates = get_projection_updates(event, sequence=10, now=now)

        assert len(updates) == 1
        update = updates[0]
        assert update.fields["current_band"] == "full"


class TestGetProjectionUpdatesPanelEvents:
    """Tests for panel event projection updates."""

    def _create_event(self, event_type: str, payload: dict) -> GovernanceEvent:
        """Helper to create a GovernanceEvent."""
        return GovernanceEvent.create(
            event_id=uuid4(),
            event_type=event_type,
            timestamp=datetime.now(timezone.utc),
            actor_id="test-actor",
            trace_id="test-trace",
            payload=payload,
        )

    def test_panel_requested_produces_create_update(self) -> None:
        """judicial.panel.requested produces create update."""
        panel_id = str(uuid4())
        event = self._create_event(
            "judicial.panel.requested",
            {
                "panel_id": panel_id,
                "violation_id": "violation-1",
                "prince_ids": ["prince-1", "prince-2", "prince-3"],
            },
        )
        now = datetime.now(timezone.utc)

        updates = get_projection_updates(event, sequence=1, now=now)

        assert len(updates) == 1
        update = updates[0]
        assert update.projection_name == "panel_registry"
        assert update.entity_id == panel_id
        assert update.update_type == "create"
        assert update.fields["panel_status"] == "pending"
        assert update.fields["violation_id"] == "violation-1"

    def test_panel_convened_produces_update(self) -> None:
        """judicial.panel.convened produces update."""
        panel_id = str(uuid4())
        event = self._create_event(
            "judicial.panel.convened",
            {"panel_id": panel_id},
        )
        now = datetime.now(timezone.utc)

        updates = get_projection_updates(event, sequence=5, now=now)

        assert len(updates) == 1
        update = updates[0]
        assert update.fields["panel_status"] == "convened"

    def test_panel_finding_issued_produces_update(self) -> None:
        """judicial.panel.finding_issued produces update."""
        panel_id = str(uuid4())
        event = self._create_event(
            "judicial.panel.finding_issued",
            {"panel_id": panel_id, "outcome": "upheld"},
        )
        now = datetime.now(timezone.utc)

        updates = get_projection_updates(event, sequence=10, now=now)

        assert len(updates) == 1
        update = updates[0]
        assert update.fields["panel_status"] == "finding_issued"
        assert update.fields["finding_outcome"] == "upheld"


class TestGetProjectionUpdatesPetitionEvents:
    """Tests for petition event projection updates."""

    def _create_event(self, event_type: str, payload: dict) -> MockGovernanceEvent:
        """Helper to create a MockGovernanceEvent.

        Uses mock because petition.* event types don't match branch.noun.verb validation.
        """
        return MockGovernanceEvent.create(event_type=event_type, payload=payload)

    def test_petition_filed_produces_create_update(self) -> None:
        """petition.filed produces create update."""
        petition_id = str(uuid4())
        event = self._create_event(
            "petition.filed",
            {
                "petition_id": petition_id,
                "petition_type": "exit",
                "subject_entity_id": "archon-42",
                "petitioner_id": "archon-42",
            },
        )
        now = datetime.now(timezone.utc)

        updates = get_projection_updates(event, sequence=1, now=now)

        assert len(updates) == 1
        update = updates[0]
        assert update.projection_name == "petition_index"
        assert update.entity_id == petition_id
        assert update.update_type == "create"
        assert update.fields["current_status"] == "filed"
        assert update.fields["petition_type"] == "exit"

    def test_petition_resolved_produces_update(self) -> None:
        """petition.resolved produces update."""
        petition_id = str(uuid4())
        event = self._create_event(
            "petition.resolved",
            {"petition_id": petition_id, "outcome": "granted"},
        )
        now = datetime.now(timezone.utc)

        updates = get_projection_updates(event, sequence=10, now=now)

        assert len(updates) == 1
        update = updates[0]
        assert update.fields["current_status"] == "resolved"
        assert update.fields["resolution_outcome"] == "granted"


class TestGetProjectionUpdatesActorEvents:
    """Tests for actor event projection updates."""

    def _create_event(self, event_type: str, payload: dict) -> MockGovernanceEvent:
        """Helper to create a MockGovernanceEvent.

        Uses mock because actor.* event types don't match branch.noun.verb validation.
        """
        return MockGovernanceEvent.create(event_type=event_type, payload=payload)

    def test_actor_registered_produces_create_update(self) -> None:
        """actor.registered produces create update."""
        event = self._create_event(
            "actor.registered",
            {
                "actor_id": "archon-42",
                "actor_type": "archon",
                "branch": "legislative",
                "display_name": "Archon 42",
            },
        )
        now = datetime.now(timezone.utc)

        updates = get_projection_updates(event, sequence=1, now=now)

        assert len(updates) == 1
        update = updates[0]
        assert update.projection_name == "actor_registry"
        assert update.entity_id == "archon-42"
        assert update.update_type == "create"
        assert update.fields["actor_type"] == "archon"
        assert update.fields["active"] is True

    def test_actor_deactivated_produces_update(self) -> None:
        """actor.deactivated produces update."""
        event = self._create_event(
            "actor.deactivated",
            {"actor_id": "archon-42"},
        )
        now = datetime.now(timezone.utc)

        updates = get_projection_updates(event, sequence=10, now=now)

        assert len(updates) == 1
        update = updates[0]
        assert update.fields["active"] is False

    def test_actor_reactivated_produces_update(self) -> None:
        """actor.reactivated produces update."""
        event = self._create_event(
            "actor.reactivated",
            {"actor_id": "archon-42"},
        )
        now = datetime.now(timezone.utc)

        updates = get_projection_updates(event, sequence=15, now=now)

        assert len(updates) == 1
        update = updates[0]
        assert update.fields["active"] is True
        assert update.fields["deactivated_at"] is None


class TestGetProjectionUpdatesUnknownEvents:
    """Tests for unknown event types."""

    def _create_event(self, event_type: str, payload: dict) -> MockGovernanceEvent:
        """Helper to create a MockGovernanceEvent."""
        return MockGovernanceEvent.create(event_type=event_type, payload=payload)

    def test_unknown_event_produces_no_updates(self) -> None:
        """Unknown event types produce empty updates list."""
        event = self._create_event(
            "unknown.event.type",
            {"some_field": "some_value"},
        )
        now = datetime.now(timezone.utc)

        updates = get_projection_updates(event, sequence=1, now=now)

        assert updates == []


class TestDeterministicProjectionUpdates:
    """Tests for deterministic state derivation (NFR-AUDIT-06)."""

    def _create_event(
        self,
        event_type: str,
        payload: dict,
        event_id: UUID | None = None,
        timestamp: datetime | None = None,
    ) -> MockGovernanceEvent:
        """Helper to create a MockGovernanceEvent."""
        return MockGovernanceEvent.create(
            event_type=event_type,
            payload=payload,
            event_id=event_id,
            timestamp=timestamp,
        )

    def test_same_event_produces_same_updates(self) -> None:
        """Same event produces identical projection updates (idempotent)."""
        event = self._create_event(
            "executive.task.created",
            {"task_id": "task-001", "earl_id": "earl-42"},
        )
        now = datetime.now(timezone.utc)

        updates1 = get_projection_updates(event, sequence=1, now=now)
        updates2 = get_projection_updates(event, sequence=1, now=now)

        # Compare fields (excluding references)
        assert len(updates1) == len(updates2)
        assert updates1[0].projection_name == updates2[0].projection_name
        assert updates1[0].entity_id == updates2[0].entity_id
        assert updates1[0].update_type == updates2[0].update_type
        assert updates1[0].fields == updates2[0].fields

    def test_updates_include_last_event_sequence(self) -> None:
        """All updates include last_event_sequence for traceability."""
        event = self._create_event(
            "executive.task.created",
            {"task_id": "task-001"},
        )
        now = datetime.now(timezone.utc)

        updates = get_projection_updates(event, sequence=42, now=now)

        assert updates[0].fields["last_event_sequence"] == 42

    def test_updates_include_updated_at(self) -> None:
        """All updates include updated_at timestamp."""
        event = self._create_event(
            "executive.task.created",
            {"task_id": "task-001"},
        )
        now = datetime.now(timezone.utc)

        updates = get_projection_updates(event, sequence=1, now=now)

        assert updates[0].fields["updated_at"] == now
