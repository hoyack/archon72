"""Unit tests for Event domain entity (Story 1.1, Task 6).

Tests:
- Event entity field validation
- DeletePreventionMixin integration (`.delete()` raises ConstitutionalViolationError)
- No infrastructure imports in Event entity

Constitutional Constraints:
- FR80: Events cannot be deleted
- FR102: Append-only enforcement
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pytest

if TYPE_CHECKING:
    pass


class TestEventEntity:
    """Test Event entity creation and validation."""

    def test_event_creation_with_all_required_fields(self) -> None:
        """Event can be created with all required fields."""
        from src.domain.events.event import Event

        event = Event(
            event_id=uuid4(),
            sequence=1,
            event_type="test.event",
            payload={"key": "value"},
            prev_hash="0" * 64,
            content_hash="abc123",
            signature="sig123",
            witness_id="witness-001",
            witness_signature="witness-sig",
            local_timestamp=datetime.now(timezone.utc),
        )

        assert event.event_type == "test.event"
        assert event.sequence == 1
        assert event.payload == {"key": "value"}
        assert event.witness_id == "witness-001"

    def test_event_creation_with_optional_agent_id(self) -> None:
        """Event can be created with optional agent_id."""
        from src.domain.events.event import Event

        event = Event(
            event_id=uuid4(),
            sequence=1,
            event_type="test.event",
            payload={},
            prev_hash="0" * 64,
            content_hash="abc123",
            signature="sig123",
            witness_id="witness-001",
            witness_signature="witness-sig",
            local_timestamp=datetime.now(timezone.utc),
            agent_id="archon-42",
        )

        assert event.agent_id == "archon-42"

    def test_event_creation_without_agent_id(self) -> None:
        """Event can be created without agent_id (system events)."""
        from src.domain.events.event import Event

        event = Event(
            event_id=uuid4(),
            sequence=1,
            event_type="system.event",
            payload={},
            prev_hash="0" * 64,
            content_hash="abc123",
            signature="sig123",
            witness_id="witness-001",
            witness_signature="witness-sig",
            local_timestamp=datetime.now(timezone.utc),
        )

        assert event.agent_id is None

    def test_event_default_algorithm_versions(self) -> None:
        """Event has default algorithm versions of 1."""
        from src.domain.events.event import Event

        event = Event(
            event_id=uuid4(),
            sequence=1,
            event_type="test.event",
            payload={},
            prev_hash="0" * 64,
            content_hash="abc123",
            signature="sig123",
            witness_id="witness-001",
            witness_signature="witness-sig",
            local_timestamp=datetime.now(timezone.utc),
        )

        assert event.hash_alg_version == 1
        assert event.sig_alg_version == 1

    def test_event_authority_timestamp_is_optional(self) -> None:
        """Event authority_timestamp defaults to None (set by DB)."""
        from src.domain.events.event import Event

        event = Event(
            event_id=uuid4(),
            sequence=1,
            event_type="test.event",
            payload={},
            prev_hash="0" * 64,
            content_hash="abc123",
            signature="sig123",
            witness_id="witness-001",
            witness_signature="witness-sig",
            local_timestamp=datetime.now(timezone.utc),
        )

        assert event.authority_timestamp is None

    def test_event_uuid_field_is_uuid_type(self) -> None:
        """Event event_id is a proper UUID type."""
        from src.domain.events.event import Event

        event_uuid = uuid4()
        event = Event(
            event_id=event_uuid,
            sequence=1,
            event_type="test.event",
            payload={},
            prev_hash="0" * 64,
            content_hash="abc123",
            signature="sig123",
            witness_id="witness-001",
            witness_signature="witness-sig",
            local_timestamp=datetime.now(timezone.utc),
        )

        assert isinstance(event.event_id, UUID)
        assert event.event_id == event_uuid


class TestDeletePreventionMixin:
    """Test DeletePreventionMixin integration (AC5)."""

    def test_event_delete_raises_constitutional_violation_error(self) -> None:
        """Calling delete() on Event raises ConstitutionalViolationError."""
        from src.domain.errors.constitutional import ConstitutionalViolationError
        from src.domain.events.event import Event

        event = Event(
            event_id=uuid4(),
            sequence=1,
            event_type="test.event",
            payload={},
            prev_hash="0" * 64,
            content_hash="abc123",
            signature="sig123",
            witness_id="witness-001",
            witness_signature="witness-sig",
            local_timestamp=datetime.now(timezone.utc),
        )

        with pytest.raises(ConstitutionalViolationError) as exc_info:
            event.delete()

        assert "FR80" in str(exc_info.value)
        assert "prohibited" in str(exc_info.value).lower()

    def test_event_inherits_from_delete_prevention_mixin(self) -> None:
        """Event inherits from DeletePreventionMixin."""
        from src.domain.events.event import Event
        from src.domain.primitives import DeletePreventionMixin

        assert issubclass(Event, DeletePreventionMixin)


class TestEventImportBoundaries:
    """Test import boundary compliance (AC5 - no infrastructure imports)."""

    def test_event_module_has_no_infrastructure_imports(self) -> None:
        """Event module must not import from infrastructure layer."""
        # Import the event module
        import src.domain.events.event as event_module

        # Get all imported modules in the event module
        module_file = event_module.__file__
        assert module_file is not None

        with open(module_file) as f:
            source_code = f.read()

        # Check for forbidden imports
        forbidden_patterns = [
            "from src.infrastructure",
            "import src.infrastructure",
            "from src.application",
            "import src.application",
            "from src.api",
            "import src.api",
        ]

        for pattern in forbidden_patterns:
            assert pattern not in source_code, (
                f"Event module contains forbidden import: {pattern}"
            )

    def test_event_module_has_no_infrastructure_in_sys_modules(self) -> None:
        """Event module should not pull in infrastructure modules."""
        # Clear any cached imports
        modules_before = set(sys.modules.keys())

        # Import Event
        from src.domain.events.event import Event  # noqa: F401

        # Check what new modules were imported
        modules_after = set(sys.modules.keys())
        new_modules = modules_after - modules_before

        # Check no infrastructure modules were imported
        infrastructure_modules = [
            m for m in new_modules
            if "infrastructure" in m or "api" in m
        ]

        assert not infrastructure_modules, (
            f"Event import pulled in forbidden modules: {infrastructure_modules}"
        )


class TestEventExport:
    """Test Event is properly exported from events module."""

    def test_event_is_exported_from_events_module(self) -> None:
        """Event should be exported from src.domain.events."""
        from src.domain.events import Event

        assert Event is not None

    def test_event_is_in_all_list(self) -> None:
        """Event should be in __all__ of events module."""
        import src.domain.events as events_module

        assert hasattr(events_module, "__all__")
        assert "Event" in events_module.__all__


class TestEventImmutability:
    """Test Event is immutable (FR102 - append-only, immutable)."""

    def test_event_is_frozen_dataclass(self) -> None:
        """Event dataclass should be frozen (immutable)."""
        from dataclasses import FrozenInstanceError

        from src.domain.events.event import Event

        event = Event(
            event_id=uuid4(),
            sequence=1,
            event_type="test.event",
            payload={},
            prev_hash="0" * 64,
            content_hash="abc123",
            signature="sig123",
            witness_id="witness-001",
            witness_signature="witness-sig",
            local_timestamp=datetime.now(timezone.utc),
        )

        with pytest.raises(FrozenInstanceError):
            event.event_type = "tampered"

    def test_event_payload_is_immutable(self) -> None:
        """Event payload should be converted to immutable MappingProxyType."""
        from types import MappingProxyType

        from src.domain.events.event import Event

        event = Event(
            event_id=uuid4(),
            sequence=1,
            event_type="test.event",
            payload={"key": "value"},
            prev_hash="0" * 64,
            content_hash="abc123",
            signature="sig123",
            witness_id="witness-001",
            witness_signature="witness-sig",
            local_timestamp=datetime.now(timezone.utc),
        )

        assert isinstance(event.payload, MappingProxyType)

        with pytest.raises(TypeError):
            event.payload["new_key"] = "tampered"  # type: ignore[index]

    def test_event_is_hashable(self) -> None:
        """Event should be hashable (for use in sets/dicts)."""
        from src.domain.events.event import Event

        event = Event(
            event_id=uuid4(),
            sequence=1,
            event_type="test.event",
            payload={},
            prev_hash="0" * 64,
            content_hash="abc123",
            signature="sig123",
            witness_id="witness-001",
            witness_signature="witness-sig",
            local_timestamp=datetime.now(timezone.utc),
        )

        # Should not raise
        event_hash = hash(event)
        assert isinstance(event_hash, int)

        # Can be used in set
        event_set = {event}
        assert event in event_set

    def test_events_with_same_id_are_equal(self) -> None:
        """Events with the same event_id should be equal."""
        from src.domain.events.event import Event

        event_id = uuid4()
        ts = datetime.now(timezone.utc)

        event1 = Event(
            event_id=event_id,
            sequence=1,
            event_type="test.event",
            payload={},
            prev_hash="0" * 64,
            content_hash="abc123",
            signature="sig123",
            witness_id="witness-001",
            witness_signature="witness-sig",
            local_timestamp=ts,
        )

        event2 = Event(
            event_id=event_id,
            sequence=1,
            event_type="test.event",
            payload={},
            prev_hash="0" * 64,
            content_hash="abc123",
            signature="sig123",
            witness_id="witness-001",
            witness_signature="witness-sig",
            local_timestamp=ts,
        )

        assert event1 == event2


class TestEventValidation:
    """Test Event field validation (FR102 - constitutional validation)."""

    def test_invalid_event_id_raises_error(self) -> None:
        """Event creation with invalid event_id raises ConstitutionalViolationError."""
        from src.domain.errors.constitutional import ConstitutionalViolationError
        from src.domain.events.event import Event

        with pytest.raises(ConstitutionalViolationError) as exc_info:
            Event(
                event_id="NOT-A-UUID",  # type: ignore[arg-type]
                sequence=1,
                event_type="test.event",
                payload={},
                prev_hash="0" * 64,
                content_hash="abc123",
                signature="sig123",
                witness_id="witness-001",
                witness_signature="witness-sig",
                local_timestamp=datetime.now(timezone.utc),
            )

        assert "FR102" in str(exc_info.value)
        assert "event_id" in str(exc_info.value)

    def test_negative_sequence_raises_error(self) -> None:
        """Event creation with negative sequence raises ConstitutionalViolationError."""
        from src.domain.errors.constitutional import ConstitutionalViolationError
        from src.domain.events.event import Event

        with pytest.raises(ConstitutionalViolationError) as exc_info:
            Event(
                event_id=uuid4(),
                sequence=-1,
                event_type="test.event",
                payload={},
                prev_hash="0" * 64,
                content_hash="abc123",
                signature="sig123",
                witness_id="witness-001",
                witness_signature="witness-sig",
                local_timestamp=datetime.now(timezone.utc),
            )

        assert "FR102" in str(exc_info.value)
        assert "sequence" in str(exc_info.value)

    def test_empty_event_type_raises_error(self) -> None:
        """Event creation with empty event_type raises ConstitutionalViolationError."""
        from src.domain.errors.constitutional import ConstitutionalViolationError
        from src.domain.events.event import Event

        with pytest.raises(ConstitutionalViolationError) as exc_info:
            Event(
                event_id=uuid4(),
                sequence=1,
                event_type="",
                payload={},
                prev_hash="0" * 64,
                content_hash="abc123",
                signature="sig123",
                witness_id="witness-001",
                witness_signature="witness-sig",
                local_timestamp=datetime.now(timezone.utc),
            )

        assert "FR102" in str(exc_info.value)
        assert "event_type" in str(exc_info.value)

    def test_invalid_payload_type_raises_error(self) -> None:
        """Event creation with non-dict payload raises ConstitutionalViolationError."""
        from src.domain.errors.constitutional import ConstitutionalViolationError
        from src.domain.events.event import Event

        with pytest.raises(ConstitutionalViolationError) as exc_info:
            Event(
                event_id=uuid4(),
                sequence=1,
                event_type="test.event",
                payload="NOT-A-DICT",  # type: ignore[arg-type]
                prev_hash="0" * 64,
                content_hash="abc123",
                signature="sig123",
                witness_id="witness-001",
                witness_signature="witness-sig",
                local_timestamp=datetime.now(timezone.utc),
            )

        assert "FR102" in str(exc_info.value)
        assert "payload" in str(exc_info.value)

    def test_empty_witness_id_raises_error(self) -> None:
        """Event creation with empty witness_id raises ConstitutionalViolationError."""
        from src.domain.errors.constitutional import ConstitutionalViolationError
        from src.domain.events.event import Event

        with pytest.raises(ConstitutionalViolationError) as exc_info:
            Event(
                event_id=uuid4(),
                sequence=1,
                event_type="test.event",
                payload={},
                prev_hash="0" * 64,
                content_hash="abc123",
                signature="sig123",
                witness_id="",
                witness_signature="witness-sig",
                local_timestamp=datetime.now(timezone.utc),
            )

        assert "FR1" in str(exc_info.value)
        assert "witness" in str(exc_info.value).lower()

    def test_empty_witness_signature_raises_error(self) -> None:
        """Event creation with empty witness_signature raises ConstitutionalViolationError."""
        from src.domain.errors.constitutional import ConstitutionalViolationError
        from src.domain.events.event import Event

        with pytest.raises(ConstitutionalViolationError) as exc_info:
            Event(
                event_id=uuid4(),
                sequence=1,
                event_type="test.event",
                payload={},
                prev_hash="0" * 64,
                content_hash="abc123",
                signature="sig123",
                witness_id="witness-001",
                witness_signature="",
                local_timestamp=datetime.now(timezone.utc),
            )

        assert "FR1" in str(exc_info.value)
        assert "witness" in str(exc_info.value).lower()

    def test_invalid_local_timestamp_raises_error(self) -> None:
        """Event creation with invalid local_timestamp raises ConstitutionalViolationError."""
        from src.domain.errors.constitutional import ConstitutionalViolationError
        from src.domain.events.event import Event

        with pytest.raises(ConstitutionalViolationError) as exc_info:
            Event(
                event_id=uuid4(),
                sequence=1,
                event_type="test.event",
                payload={},
                prev_hash="0" * 64,
                content_hash="abc123",
                signature="sig123",
                witness_id="witness-001",
                witness_signature="witness-sig",
                local_timestamp="NOT-A-DATETIME",  # type: ignore[arg-type]
            )

        assert "FR102" in str(exc_info.value)
        assert "local_timestamp" in str(exc_info.value)

    def test_sequence_zero_is_valid(self) -> None:
        """Event with sequence=0 (genesis event) is valid."""
        from src.domain.events.event import Event

        event = Event(
            event_id=uuid4(),
            sequence=0,
            event_type="genesis.event",
            payload={},
            prev_hash="0" * 64,
            content_hash="abc123",
            signature="sig123",
            witness_id="witness-001",
            witness_signature="witness-sig",
            local_timestamp=datetime.now(timezone.utc),
        )

        assert event.sequence == 0
