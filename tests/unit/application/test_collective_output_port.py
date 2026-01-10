"""Unit tests for CollectiveOutputPort interface (Story 2.3, FR11).

Tests the application port interface for collective output storage.

Constitutional Constraints:
- FR11: Collective outputs attributed to Conclave, not individuals
- CT-12: Witnessing creates accountability
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest


class TestStoredCollectiveOutput:
    """Tests for StoredCollectiveOutput dataclass."""

    def test_dataclass_exists(self) -> None:
        """StoredCollectiveOutput should be importable."""
        from src.application.ports.collective_output import StoredCollectiveOutput

        assert StoredCollectiveOutput is not None

    def test_create_stored_output(self) -> None:
        """StoredCollectiveOutput should accept valid fields."""
        from src.application.ports.collective_output import StoredCollectiveOutput

        stored = StoredCollectiveOutput(
            output_id=uuid4(),
            event_sequence=42,
            content_hash="a" * 64,
            stored_at=datetime.now(timezone.utc),
        )
        assert stored.event_sequence == 42
        assert len(stored.content_hash) == 64

    def test_stored_output_is_frozen(self) -> None:
        """StoredCollectiveOutput should be frozen (immutable)."""
        from src.application.ports.collective_output import StoredCollectiveOutput

        stored = StoredCollectiveOutput(
            output_id=uuid4(),
            event_sequence=1,
            content_hash="a" * 64,
            stored_at=datetime.now(timezone.utc),
        )
        with pytest.raises(AttributeError):
            stored.event_sequence = 2  # type: ignore[misc]


class TestCollectiveOutputPort:
    """Tests for CollectiveOutputPort protocol interface."""

    def test_protocol_exists(self) -> None:
        """CollectiveOutputPort should be importable."""
        from src.application.ports.collective_output import CollectiveOutputPort

        assert CollectiveOutputPort is not None

    def test_store_collective_output_method_exists(self) -> None:
        """CollectiveOutputPort should define store_collective_output method."""
        from src.application.ports.collective_output import CollectiveOutputPort

        assert hasattr(CollectiveOutputPort, "store_collective_output")

    def test_get_collective_output_method_exists(self) -> None:
        """CollectiveOutputPort should define get_collective_output method."""
        from src.application.ports.collective_output import CollectiveOutputPort

        assert hasattr(CollectiveOutputPort, "get_collective_output")

    def test_get_linked_vote_events_method_exists(self) -> None:
        """CollectiveOutputPort should define get_linked_vote_events method."""
        from src.application.ports.collective_output import CollectiveOutputPort

        assert hasattr(CollectiveOutputPort, "get_linked_vote_events")

    def test_protocol_is_runtime_checkable(self) -> None:
        """CollectiveOutputPort should be runtime_checkable Protocol."""
        from typing import Protocol

        from src.application.ports.collective_output import CollectiveOutputPort

        # Protocol should be runtime checkable
        assert issubclass(CollectiveOutputPort, Protocol)


class TestCollectiveOutputPortExports:
    """Tests for collective_output port exports."""

    def test_exportable_from_ports_package(self) -> None:
        """Types should be exportable from application.ports."""
        from src.application.ports import (
            CollectiveOutputPort,
            StoredCollectiveOutput,
        )

        assert CollectiveOutputPort is not None
        assert StoredCollectiveOutput is not None
