"""Unit tests for GovernanceEvent and EventMetadata domain models.

Tests cover all acceptance criteria for story consent-gov-1.1:
- AC1: GovernanceEvent with metadata and payload, both immutable
- AC2: Metadata includes all required fields
- AC3: Event type follows branch.noun.verb naming convention
- AC4: Branch derived from event_type at write-time
- AC5: Schema version field present (semver format)
- AC6: Comprehensive unit tests
- AC7: Validation errors raise ConstitutionalViolationError
"""

from datetime import datetime, timezone
from types import MappingProxyType
from uuid import UUID, uuid4

import pytest

from src.domain.errors.constitutional import ConstitutionalViolationError
from src.domain.governance.events.event_envelope import (
    EventMetadata,
    GovernanceEvent,
)
from src.domain.governance.events.event_types import (
    GOVERNANCE_EVENT_TYPES,
    GovernanceEventType,
    derive_branch,
    validate_event_type,
)
from src.domain.governance.events.schema_versions import (
    CURRENT_SCHEMA_VERSION,
    validate_schema_version,
)


class TestEventMetadata:
    """Tests for EventMetadata dataclass (AC2, AC3, AC5, AC7)."""

    def test_valid_metadata_creation(self) -> None:
        """EventMetadata with valid data creates successfully (AC2)."""
        event_id = uuid4()
        timestamp = datetime.now(timezone.utc)

        metadata = EventMetadata(
            event_id=event_id,
            event_type="executive.task.accepted",
            timestamp=timestamp,
            actor_id="archon-42",
            schema_version="1.0.0",
            trace_id="req-12345",
        )

        assert metadata.event_id == event_id
        assert metadata.event_type == "executive.task.accepted"
        assert metadata.timestamp == timestamp
        assert metadata.actor_id == "archon-42"
        assert metadata.schema_version == "1.0.0"
        assert metadata.trace_id == "req-12345"

    def test_metadata_is_immutable(self) -> None:
        """EventMetadata fields cannot be modified after creation (AC1)."""
        metadata = EventMetadata(
            event_id=uuid4(),
            event_type="executive.task.accepted",
            timestamp=datetime.now(timezone.utc),
            actor_id="archon-42",
            schema_version="1.0.0",
            trace_id="req-12345",
        )

        with pytest.raises(AttributeError):
            metadata.event_type = "judicial.panel.convened"  # type: ignore[misc]

    def test_metadata_branch_derived_from_event_type(self) -> None:
        """Branch is derived from event_type.split('.')[0] (AC4)."""
        metadata = EventMetadata(
            event_id=uuid4(),
            event_type="executive.task.accepted",
            timestamp=datetime.now(timezone.utc),
            actor_id="archon-42",
            schema_version="1.0.0",
            trace_id="req-12345",
        )

        assert metadata.branch == "executive"

        # Test with different branches
        judicial_metadata = EventMetadata(
            event_id=uuid4(),
            event_type="judicial.panel.convened",
            timestamp=datetime.now(timezone.utc),
            actor_id="prince-1",
            schema_version="1.0.0",
            trace_id="req-67890",
        )
        assert judicial_metadata.branch == "judicial"

    def test_invalid_event_id_type_raises(self) -> None:
        """Non-UUID event_id raises ConstitutionalViolationError (AC7)."""
        with pytest.raises(ConstitutionalViolationError) as exc_info:
            EventMetadata(
                event_id="not-a-uuid",  # type: ignore[arg-type]
                event_type="executive.task.accepted",
                timestamp=datetime.now(timezone.utc),
                actor_id="archon-42",
                schema_version="1.0.0",
                trace_id="req-12345",
            )

        assert "event_id must be UUID" in str(exc_info.value)

    def test_invalid_event_type_format_raises(self) -> None:
        """Event type not matching branch.noun.verb raises ConstitutionalViolationError (AC3, AC7)."""
        # Missing verb
        with pytest.raises(ConstitutionalViolationError) as exc_info:
            EventMetadata(
                event_id=uuid4(),
                event_type="executive.task",
                timestamp=datetime.now(timezone.utc),
                actor_id="archon-42",
                schema_version="1.0.0",
                trace_id="req-12345",
            )
        assert "branch.noun.verb" in str(exc_info.value)

        # Uppercase characters
        with pytest.raises(ConstitutionalViolationError):
            EventMetadata(
                event_id=uuid4(),
                event_type="Executive.Task.Accepted",
                timestamp=datetime.now(timezone.utc),
                actor_id="archon-42",
                schema_version="1.0.0",
                trace_id="req-12345",
            )

        # Extra segments
        with pytest.raises(ConstitutionalViolationError):
            EventMetadata(
                event_id=uuid4(),
                event_type="executive.task.accepted.extra",
                timestamp=datetime.now(timezone.utc),
                actor_id="archon-42",
                schema_version="1.0.0",
                trace_id="req-12345",
            )

    def test_empty_event_type_raises(self) -> None:
        """Empty event_type raises ConstitutionalViolationError (AC7)."""
        with pytest.raises(ConstitutionalViolationError) as exc_info:
            EventMetadata(
                event_id=uuid4(),
                event_type="",
                timestamp=datetime.now(timezone.utc),
                actor_id="archon-42",
                schema_version="1.0.0",
                trace_id="req-12345",
            )
        assert "non-empty" in str(exc_info.value)

    def test_invalid_timestamp_type_raises(self) -> None:
        """Non-datetime timestamp raises ConstitutionalViolationError (AC7)."""
        with pytest.raises(ConstitutionalViolationError) as exc_info:
            EventMetadata(
                event_id=uuid4(),
                event_type="executive.task.accepted",
                timestamp="2026-01-16T00:00:00Z",  # type: ignore[arg-type]
                actor_id="archon-42",
                schema_version="1.0.0",
                trace_id="req-12345",
            )
        assert "timestamp must be datetime" in str(exc_info.value)

    def test_empty_actor_id_raises(self) -> None:
        """Empty actor_id raises ConstitutionalViolationError (AC7)."""
        with pytest.raises(ConstitutionalViolationError) as exc_info:
            EventMetadata(
                event_id=uuid4(),
                event_type="executive.task.accepted",
                timestamp=datetime.now(timezone.utc),
                actor_id="",
                schema_version="1.0.0",
                trace_id="req-12345",
            )
        assert "actor_id must be non-empty" in str(exc_info.value)

        # Whitespace only
        with pytest.raises(ConstitutionalViolationError):
            EventMetadata(
                event_id=uuid4(),
                event_type="executive.task.accepted",
                timestamp=datetime.now(timezone.utc),
                actor_id="   ",
                schema_version="1.0.0",
                trace_id="req-12345",
            )

    def test_invalid_schema_version_format_raises(self) -> None:
        """Non-semver schema_version raises ConstitutionalViolationError (AC5, AC7)."""
        # Missing patch version
        with pytest.raises(ConstitutionalViolationError) as exc_info:
            EventMetadata(
                event_id=uuid4(),
                event_type="executive.task.accepted",
                timestamp=datetime.now(timezone.utc),
                actor_id="archon-42",
                schema_version="1.0",
                trace_id="req-12345",
            )
        assert "semver format" in str(exc_info.value)

        # Non-numeric
        with pytest.raises(ConstitutionalViolationError):
            EventMetadata(
                event_id=uuid4(),
                event_type="executive.task.accepted",
                timestamp=datetime.now(timezone.utc),
                actor_id="archon-42",
                schema_version="v1.0.0",
                trace_id="req-12345",
            )

    def test_empty_trace_id_raises(self) -> None:
        """Empty trace_id raises ConstitutionalViolationError (AC7)."""
        with pytest.raises(ConstitutionalViolationError) as exc_info:
            EventMetadata(
                event_id=uuid4(),
                event_type="executive.task.accepted",
                timestamp=datetime.now(timezone.utc),
                actor_id="archon-42",
                schema_version="1.0.0",
                trace_id="",
            )
        assert "trace_id must be non-empty" in str(exc_info.value)

    def test_metadata_hash_based_on_event_id(self) -> None:
        """Metadata hash is based on event_id."""
        event_id = uuid4()
        metadata1 = EventMetadata(
            event_id=event_id,
            event_type="executive.task.accepted",
            timestamp=datetime.now(timezone.utc),
            actor_id="archon-42",
            schema_version="1.0.0",
            trace_id="req-12345",
        )
        metadata2 = EventMetadata(
            event_id=event_id,
            event_type="judicial.panel.convened",  # Different type
            timestamp=datetime.now(timezone.utc),
            actor_id="prince-1",
            schema_version="1.0.0",
            trace_id="req-67890",
        )

        assert hash(metadata1) == hash(metadata2)


class TestGovernanceEvent:
    """Tests for GovernanceEvent dataclass (AC1, AC6)."""

    def _create_valid_metadata(self) -> EventMetadata:
        """Helper to create valid metadata."""
        return EventMetadata(
            event_id=uuid4(),
            event_type="executive.task.accepted",
            timestamp=datetime.now(timezone.utc),
            actor_id="archon-42",
            schema_version="1.0.0",
            trace_id="req-12345",
        )

    def test_valid_event_creation(self) -> None:
        """GovernanceEvent with valid data creates successfully (AC1)."""
        metadata = self._create_valid_metadata()
        payload = {"task_id": "task-001", "accepted_at": "2026-01-16"}

        event = GovernanceEvent(metadata=metadata, payload=payload)

        assert event.metadata == metadata
        assert event.payload["task_id"] == "task-001"

    def test_event_payload_is_immutable(self) -> None:
        """Payload dict is converted to MappingProxyType (AC1)."""
        metadata = self._create_valid_metadata()
        original_payload = {"task_id": "task-001"}

        event = GovernanceEvent(metadata=metadata, payload=original_payload)

        assert isinstance(event.payload, MappingProxyType)

        with pytest.raises(TypeError):
            event.payload["task_id"] = "modified"  # type: ignore[index]

    def test_event_metadata_is_immutable(self) -> None:
        """Event metadata cannot be modified after creation (AC1)."""
        event = GovernanceEvent(
            metadata=self._create_valid_metadata(),
            payload={"task_id": "task-001"},
        )

        with pytest.raises(AttributeError):
            event.metadata = self._create_valid_metadata()  # type: ignore[misc]

    def test_event_convenience_accessors(self) -> None:
        """Event provides convenience accessors for metadata fields."""
        metadata = self._create_valid_metadata()
        event = GovernanceEvent(metadata=metadata, payload={})

        assert event.event_id == metadata.event_id
        assert event.event_type == metadata.event_type
        assert event.branch == metadata.branch
        assert event.timestamp == metadata.timestamp
        assert event.actor_id == metadata.actor_id
        assert event.schema_version == metadata.schema_version
        assert event.trace_id == metadata.trace_id

    def test_branch_derived_from_event_type(self) -> None:
        """Branch is derived from event_type.split('.')[0] (AC4)."""
        metadata = EventMetadata(
            event_id=uuid4(),
            event_type="witness.observation.recorded",
            timestamp=datetime.now(timezone.utc),
            actor_id="knight-furcas",
            schema_version="1.0.0",
            trace_id="req-witness",
        )
        event = GovernanceEvent(metadata=metadata, payload={})

        assert event.branch == "witness"

    def test_invalid_metadata_type_raises(self) -> None:
        """Non-EventMetadata metadata raises ConstitutionalViolationError (AC7)."""
        with pytest.raises(ConstitutionalViolationError) as exc_info:
            GovernanceEvent(
                metadata={"event_id": "uuid"},  # type: ignore[arg-type]
                payload={},
            )
        assert "metadata must be EventMetadata" in str(exc_info.value)

    def test_invalid_payload_type_raises(self) -> None:
        """Non-dict payload raises ConstitutionalViolationError (AC7)."""
        metadata = self._create_valid_metadata()

        with pytest.raises(ConstitutionalViolationError) as exc_info:
            GovernanceEvent(
                metadata=metadata,
                payload=["not", "a", "dict"],  # type: ignore[arg-type]
            )
        assert "payload must be dict" in str(exc_info.value)

    def test_event_hash_based_on_event_id(self) -> None:
        """Event hash is based on event_id."""
        event_id = uuid4()
        metadata1 = EventMetadata(
            event_id=event_id,
            event_type="executive.task.accepted",
            timestamp=datetime.now(timezone.utc),
            actor_id="archon-42",
            schema_version="1.0.0",
            trace_id="req-12345",
        )
        event1 = GovernanceEvent(metadata=metadata1, payload={"key": "value1"})
        event2 = GovernanceEvent(metadata=metadata1, payload={"key": "value2"})

        # Same event_id = same hash
        assert hash(event1) == hash(event2)

    def test_create_factory_method(self) -> None:
        """GovernanceEvent.create() factory method works correctly."""
        event_id = uuid4()
        timestamp = datetime.now(timezone.utc)

        event = GovernanceEvent.create(
            event_id=event_id,
            event_type="consent.task.granted",
            timestamp=timestamp,
            actor_id="archon-42",
            trace_id="req-consent",
            payload={"task_id": "task-001", "granted_to": "archon-42"},
        )

        assert event.event_id == event_id
        assert event.event_type == "consent.task.granted"
        assert event.timestamp == timestamp
        assert event.actor_id == "archon-42"
        assert event.schema_version == CURRENT_SCHEMA_VERSION
        assert event.trace_id == "req-consent"
        assert event.branch == "consent"
        assert event.payload["task_id"] == "task-001"

    def test_create_with_custom_schema_version(self) -> None:
        """GovernanceEvent.create() accepts custom schema version."""
        event = GovernanceEvent.create(
            event_id=uuid4(),
            event_type="executive.task.accepted",
            timestamp=datetime.now(timezone.utc),
            actor_id="archon-42",
            trace_id="req-12345",
            payload={},
            schema_version="2.0.0",
        )

        assert event.schema_version == "2.0.0"

    def test_payload_already_frozen_accepted(self) -> None:
        """Already-frozen payload (MappingProxyType) is accepted."""
        metadata = self._create_valid_metadata()
        frozen_payload = MappingProxyType({"task_id": "task-001"})

        event = GovernanceEvent(metadata=metadata, payload=frozen_payload)

        assert event.payload is frozen_payload


class TestEventTypes:
    """Tests for event type validation and registry (AC3)."""

    def test_validate_event_type_valid_format(self) -> None:
        """Valid event types pass validation."""
        # Standard format
        validate_event_type("executive.task.accepted")
        validate_event_type("judicial.panel.convened")
        validate_event_type("witness.observation.recorded")

        # With underscore in verb
        validate_event_type("executive.task.reminder_sent")
        validate_event_type("legitimacy.band.decayed")

    def test_validate_event_type_invalid_format(self) -> None:
        """Invalid event types raise ConstitutionalViolationError."""
        # Missing verb
        with pytest.raises(ConstitutionalViolationError):
            validate_event_type("executive.task")

        # Too many segments
        with pytest.raises(ConstitutionalViolationError):
            validate_event_type("executive.task.accepted.extra")

        # Uppercase
        with pytest.raises(ConstitutionalViolationError):
            validate_event_type("Executive.Task.Accepted")

        # Numbers
        with pytest.raises(ConstitutionalViolationError):
            validate_event_type("executive.task2.accepted")

        # Hyphens instead of underscores
        with pytest.raises(ConstitutionalViolationError):
            validate_event_type("executive.task.reminder-sent")

    def test_validate_event_type_strict_mode(self) -> None:
        """Strict mode only allows known event types."""
        # Known type passes
        validate_event_type("executive.task.accepted", strict=True)

        # Unknown type fails in strict mode
        with pytest.raises(ConstitutionalViolationError) as exc_info:
            validate_event_type("custom.event.type", strict=True)
        assert "Unknown event type" in str(exc_info.value)

        # Unknown type passes in non-strict mode (default)
        validate_event_type("custom.event.type")  # No error

    def test_derive_branch(self) -> None:
        """derive_branch extracts first segment of event_type."""
        assert derive_branch("executive.task.accepted") == "executive"
        assert derive_branch("judicial.panel.convened") == "judicial"
        assert derive_branch("witness.observation.recorded") == "witness"
        assert derive_branch("filter.message.blocked") == "filter"
        assert derive_branch("consent.task.granted") == "consent"
        assert derive_branch("legitimacy.band.decayed") == "legitimacy"

    def test_governance_event_types_frozenset(self) -> None:
        """GOVERNANCE_EVENT_TYPES is a frozenset of all enum values."""
        assert isinstance(GOVERNANCE_EVENT_TYPES, frozenset)
        assert "executive.task.accepted" in GOVERNANCE_EVENT_TYPES
        assert "judicial.panel.convened" in GOVERNANCE_EVENT_TYPES

        # All enum values are in the frozenset
        for event_type in GovernanceEventType:
            assert event_type.value in GOVERNANCE_EVENT_TYPES

    def test_governance_event_type_enum_values(self) -> None:
        """GovernanceEventType enum has expected values."""
        assert (
            GovernanceEventType.EXECUTIVE_TASK_ACCEPTED.value
            == "executive.task.accepted"
        )
        assert (
            GovernanceEventType.JUDICIAL_PANEL_CONVENED.value
            == "judicial.panel.convened"
        )
        assert (
            GovernanceEventType.WITNESS_OBSERVATION_RECORDED.value
            == "witness.observation.recorded"
        )


class TestSchemaVersions:
    """Tests for schema version validation (AC5)."""

    def test_current_schema_version_is_valid(self) -> None:
        """CURRENT_SCHEMA_VERSION is valid semver."""
        validate_schema_version(CURRENT_SCHEMA_VERSION)  # No error

    def test_validate_schema_version_valid(self) -> None:
        """Valid semver versions pass validation."""
        validate_schema_version("1.0.0")
        validate_schema_version("2.1.3")
        validate_schema_version("0.0.1")
        validate_schema_version("10.20.30")

    def test_validate_schema_version_invalid(self) -> None:
        """Invalid semver versions raise ConstitutionalViolationError."""
        # Missing patch
        with pytest.raises(ConstitutionalViolationError):
            validate_schema_version("1.0")

        # Missing minor and patch
        with pytest.raises(ConstitutionalViolationError):
            validate_schema_version("1")

        # With 'v' prefix
        with pytest.raises(ConstitutionalViolationError):
            validate_schema_version("v1.0.0")

        # With pre-release suffix
        with pytest.raises(ConstitutionalViolationError):
            validate_schema_version("1.0.0-alpha")

        # Non-numeric
        with pytest.raises(ConstitutionalViolationError):
            validate_schema_version("one.two.three")

    def test_validate_schema_version_non_string_raises(self) -> None:
        """Non-string schema version raises ConstitutionalViolationError."""
        with pytest.raises(ConstitutionalViolationError) as exc_info:
            validate_schema_version(100)  # type: ignore[arg-type]
        assert "must be string" in str(exc_info.value)


class TestIntegration:
    """Integration tests for the complete event envelope."""

    def test_full_event_lifecycle(self) -> None:
        """Test creating a complete governance event."""
        # Create event using factory
        event = GovernanceEvent.create(
            event_id=uuid4(),
            event_type="consent.task.granted",
            timestamp=datetime.now(timezone.utc),
            actor_id="archon-42",
            trace_id="req-consent-001",
            payload={
                "task_id": "task-deploy-v2",
                "granted_to": "archon-42",
                "conditions": ["within_business_hours", "no_prod_access"],
            },
        )

        # Verify all fields accessible
        assert isinstance(event.event_id, UUID)
        assert event.event_type == "consent.task.granted"
        assert event.branch == "consent"
        assert event.actor_id == "archon-42"
        assert event.schema_version == CURRENT_SCHEMA_VERSION
        assert event.payload["task_id"] == "task-deploy-v2"

        # Verify immutability
        with pytest.raises(TypeError):
            event.payload["new_key"] = "value"  # type: ignore[index]

    def test_all_known_event_types_create_valid_events(self) -> None:
        """All known event types can be used to create valid events."""
        for event_type in GovernanceEventType:
            event = GovernanceEvent.create(
                event_id=uuid4(),
                event_type=event_type.value,
                timestamp=datetime.now(timezone.utc),
                actor_id="test-actor",
                trace_id="test-trace",
                payload={},
            )

            expected_branch = event_type.value.split(".")[0]
            assert event.branch == expected_branch
