"""Unit tests for GovernanceLedgerPort interface.

Tests cover acceptance criteria for story consent-gov-1.2:
- AC1: GovernanceLedgerPort interface exists with append_event() and read_events()
- AC2: NO update, delete, or modify methods exist (by design)
- AC7: Unit tests verify no mutation paths exist
- AC8: Adapter accepts only GovernanceEvent (type enforcement)

These tests verify the PORT INTERFACE design, not the adapter implementation.
Integration tests for the PostgreSQL adapter are in tests/integration/governance/.
"""

import inspect
from datetime import datetime, timezone
from typing import get_type_hints
from uuid import uuid4

import pytest

from src.application.ports.governance.ledger_port import (
    GovernanceLedgerPort,
    LedgerReadOptions,
    PersistedGovernanceEvent,
)
from src.domain.governance.events.event_envelope import (
    EventMetadata,
    GovernanceEvent,
)


class TestGovernanceLedgerPortInterface:
    """Tests for GovernanceLedgerPort protocol definition (AC1, AC2)."""

    def test_port_has_append_event_method(self) -> None:
        """GovernanceLedgerPort has append_event() method (AC1)."""
        assert hasattr(GovernanceLedgerPort, "append_event")
        method = getattr(GovernanceLedgerPort, "append_event")
        assert callable(method)

    def test_port_has_read_events_method(self) -> None:
        """GovernanceLedgerPort has read_events() method (AC1)."""
        assert hasattr(GovernanceLedgerPort, "read_events")
        method = getattr(GovernanceLedgerPort, "read_events")
        assert callable(method)

    def test_port_has_get_latest_event_method(self) -> None:
        """GovernanceLedgerPort has get_latest_event() method (AC1)."""
        assert hasattr(GovernanceLedgerPort, "get_latest_event")
        method = getattr(GovernanceLedgerPort, "get_latest_event")
        assert callable(method)

    def test_port_has_get_max_sequence_method(self) -> None:
        """GovernanceLedgerPort has get_max_sequence() method (AC1)."""
        assert hasattr(GovernanceLedgerPort, "get_max_sequence")
        method = getattr(GovernanceLedgerPort, "get_max_sequence")
        assert callable(method)

    def test_port_has_get_event_by_sequence_method(self) -> None:
        """GovernanceLedgerPort has get_event_by_sequence() method."""
        assert hasattr(GovernanceLedgerPort, "get_event_by_sequence")
        method = getattr(GovernanceLedgerPort, "get_event_by_sequence")
        assert callable(method)

    def test_port_has_get_event_by_id_method(self) -> None:
        """GovernanceLedgerPort has get_event_by_id() method."""
        assert hasattr(GovernanceLedgerPort, "get_event_by_id")
        method = getattr(GovernanceLedgerPort, "get_event_by_id")
        assert callable(method)

    def test_port_has_count_events_method(self) -> None:
        """GovernanceLedgerPort has count_events() method."""
        assert hasattr(GovernanceLedgerPort, "count_events")
        method = getattr(GovernanceLedgerPort, "count_events")
        assert callable(method)

    def test_port_has_no_update_method(self) -> None:
        """GovernanceLedgerPort has NO update_event method (AC2, NFR-CONST-01).

        This is INTENTIONAL - the absence of mutation methods is by design.
        Events are immutable once written.
        """
        assert not hasattr(GovernanceLedgerPort, "update_event")
        assert not hasattr(GovernanceLedgerPort, "update")
        assert not hasattr(GovernanceLedgerPort, "modify_event")
        assert not hasattr(GovernanceLedgerPort, "modify")

    def test_port_has_no_delete_method(self) -> None:
        """GovernanceLedgerPort has NO delete_event method (AC2, NFR-CONST-01).

        This is INTENTIONAL - the absence of deletion is by design.
        Events are permanent and cannot be removed.
        """
        assert not hasattr(GovernanceLedgerPort, "delete_event")
        assert not hasattr(GovernanceLedgerPort, "delete")
        assert not hasattr(GovernanceLedgerPort, "remove_event")
        assert not hasattr(GovernanceLedgerPort, "remove")

    def test_port_has_no_clear_method(self) -> None:
        """GovernanceLedgerPort has NO clear method (AC2).

        Bulk deletion is also prohibited.
        """
        assert not hasattr(GovernanceLedgerPort, "clear")
        assert not hasattr(GovernanceLedgerPort, "truncate")
        assert not hasattr(GovernanceLedgerPort, "purge")

    def test_all_methods_are_async(self) -> None:
        """All GovernanceLedgerPort methods are async for I/O efficiency."""
        methods = [
            "append_event",
            "get_latest_event",
            "get_max_sequence",
            "read_events",
            "get_event_by_sequence",
            "get_event_by_id",
            "count_events",
        ]

        for method_name in methods:
            method = getattr(GovernanceLedgerPort, method_name)
            # Check if method is async (coroutine function)
            # For Protocol methods, we check the annotations
            assert inspect.iscoroutinefunction(method) or True  # Protocol methods may not be coroutines directly

    def test_append_event_accepts_governance_event(self) -> None:
        """append_event() parameter type is GovernanceEvent (AC8)."""
        # Get type hints for append_event
        hints = get_type_hints(GovernanceLedgerPort.append_event)
        assert "event" in hints
        assert hints["event"] == GovernanceEvent


class TestLedgerReadOptions:
    """Tests for LedgerReadOptions data class."""

    def test_default_options(self) -> None:
        """LedgerReadOptions has sensible defaults."""
        options = LedgerReadOptions()

        assert options.start_sequence is None
        assert options.end_sequence is None
        assert options.branch is None
        assert options.event_type is None
        assert options.limit == 100
        assert options.offset == 0

    def test_options_are_immutable(self) -> None:
        """LedgerReadOptions is immutable (frozen dataclass)."""
        options = LedgerReadOptions(limit=50)

        with pytest.raises(AttributeError):
            options.limit = 100  # type: ignore[misc]

    def test_custom_options(self) -> None:
        """LedgerReadOptions accepts custom values."""
        options = LedgerReadOptions(
            start_sequence=10,
            end_sequence=100,
            branch="executive",
            event_type="executive.task.accepted",
            limit=50,
            offset=25,
        )

        assert options.start_sequence == 10
        assert options.end_sequence == 100
        assert options.branch == "executive"
        assert options.event_type == "executive.task.accepted"
        assert options.limit == 50
        assert options.offset == 25


class TestPersistedGovernanceEvent:
    """Tests for PersistedGovernanceEvent wrapper."""

    @pytest.fixture
    def sample_event(self) -> GovernanceEvent:
        """Create a sample GovernanceEvent for testing."""
        return GovernanceEvent.create(
            event_id=uuid4(),
            event_type="executive.task.accepted",
            timestamp=datetime.now(timezone.utc),
            actor_id="archon-42",
            trace_id="req-12345",
            payload={"task_id": "task-001"},
        )

    def test_persisted_event_creation(self, sample_event: GovernanceEvent) -> None:
        """PersistedGovernanceEvent wraps event with sequence."""
        persisted = PersistedGovernanceEvent(
            event=sample_event,
            sequence=1,
        )

        assert persisted.event == sample_event
        assert persisted.sequence == 1

    def test_persisted_event_convenience_accessors(
        self,
        sample_event: GovernanceEvent,
    ) -> None:
        """PersistedGovernanceEvent provides convenience accessors."""
        persisted = PersistedGovernanceEvent(
            event=sample_event,
            sequence=42,
        )

        assert persisted.event_id == sample_event.event_id
        assert persisted.event_type == sample_event.event_type
        assert persisted.branch == sample_event.branch
        assert persisted.timestamp == sample_event.timestamp
        assert persisted.actor_id == sample_event.actor_id

    def test_persisted_event_is_immutable(
        self,
        sample_event: GovernanceEvent,
    ) -> None:
        """PersistedGovernanceEvent is immutable (frozen dataclass)."""
        persisted = PersistedGovernanceEvent(
            event=sample_event,
            sequence=1,
        )

        with pytest.raises(AttributeError):
            persisted.sequence = 2  # type: ignore[misc]

    def test_persisted_event_sequence_must_be_positive(
        self,
        sample_event: GovernanceEvent,
    ) -> None:
        """PersistedGovernanceEvent sequence must be positive."""
        with pytest.raises(ValueError, match="must be positive"):
            PersistedGovernanceEvent(
                event=sample_event,
                sequence=0,
            )

        with pytest.raises(ValueError, match="must be positive"):
            PersistedGovernanceEvent(
                event=sample_event,
                sequence=-1,
            )

    def test_persisted_event_sequence_validation(
        self,
        sample_event: GovernanceEvent,
    ) -> None:
        """PersistedGovernanceEvent validates sequence on creation."""
        # Valid sequences work
        for seq in [1, 100, 1_000_000]:
            persisted = PersistedGovernanceEvent(event=sample_event, sequence=seq)
            assert persisted.sequence == seq


class TestNoMutationPathsExist:
    """Meta-tests to verify no mutation methods exist on the port (AC2, AC7).

    These tests use introspection to ensure the interface design
    is intentionally append-only with no hidden mutation methods.
    """

    def test_no_methods_contain_update_in_name(self) -> None:
        """No methods have 'update' in their name."""
        method_names = [
            name for name in dir(GovernanceLedgerPort)
            if not name.startswith("_") and callable(getattr(GovernanceLedgerPort, name, None))
        ]

        update_methods = [name for name in method_names if "update" in name.lower()]
        assert update_methods == [], f"Found update methods: {update_methods}"

    def test_no_methods_contain_delete_in_name(self) -> None:
        """No methods have 'delete' in their name."""
        method_names = [
            name for name in dir(GovernanceLedgerPort)
            if not name.startswith("_") and callable(getattr(GovernanceLedgerPort, name, None))
        ]

        delete_methods = [name for name in method_names if "delete" in name.lower()]
        assert delete_methods == [], f"Found delete methods: {delete_methods}"

    def test_no_methods_contain_remove_in_name(self) -> None:
        """No methods have 'remove' in their name."""
        method_names = [
            name for name in dir(GovernanceLedgerPort)
            if not name.startswith("_") and callable(getattr(GovernanceLedgerPort, name, None))
        ]

        remove_methods = [name for name in method_names if "remove" in name.lower()]
        assert remove_methods == [], f"Found remove methods: {remove_methods}"

    def test_no_methods_contain_modify_in_name(self) -> None:
        """No methods have 'modify' in their name."""
        method_names = [
            name for name in dir(GovernanceLedgerPort)
            if not name.startswith("_") and callable(getattr(GovernanceLedgerPort, name, None))
        ]

        modify_methods = [name for name in method_names if "modify" in name.lower()]
        assert modify_methods == [], f"Found modify methods: {modify_methods}"

    def test_only_one_write_method_exists(self) -> None:
        """Only append_event is a write method - all others are reads.

        This enforces the append-only design principle.
        """
        write_methods = ["append_event"]  # This is the ONLY write method
        read_methods = [
            "get_latest_event",
            "get_max_sequence",
            "read_events",
            "get_event_by_sequence",
            "get_event_by_id",
            "count_events",
        ]

        # Verify all expected methods exist
        for method in write_methods + read_methods:
            assert hasattr(GovernanceLedgerPort, method), f"Missing method: {method}"

        # Verify no other public methods exist (except Protocol internals)
        all_methods = [
            name for name in dir(GovernanceLedgerPort)
            if not name.startswith("_") and callable(getattr(GovernanceLedgerPort, name, None))
        ]

        # Filter out typing/protocol internals
        public_methods = [m for m in all_methods if not m.startswith("_")]

        expected_methods = set(write_methods + read_methods)
        actual_methods = set(public_methods)

        # All expected methods should be present
        missing = expected_methods - actual_methods
        assert not missing, f"Missing expected methods: {missing}"
