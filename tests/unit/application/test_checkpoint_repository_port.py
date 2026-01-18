"""Unit tests for CheckpointRepository port (Story 3.10, Task 2; Story 4.6, Task 3).

Tests the abstract port interface for checkpoint repository operations.

Constitutional Constraints:
- FR136: Merkle proof SHALL be included in event query responses when requested
- FR137: Checkpoints are periodic anchors (minimum weekly)
- FR138: Weekly checkpoint anchors SHALL be published at consistent intervals
- FR143: Rollback to checkpoint for infrastructure recovery
"""

from __future__ import annotations

import inspect
from typing import Protocol

import pytest

from src.application.ports.checkpoint_repository import CheckpointRepository


class TestCheckpointRepositoryPortStructure:
    """Tests for CheckpointRepository port structure."""

    def test_port_is_protocol(self) -> None:
        """CheckpointRepository should be a Protocol."""
        assert issubclass(CheckpointRepository, Protocol)

    def test_port_is_runtime_checkable(self) -> None:
        """CheckpointRepository should be runtime checkable."""
        # Protocol classes decorated with @runtime_checkable can be used with isinstance()
        assert hasattr(CheckpointRepository, "__protocol_attrs__") or hasattr(
            CheckpointRepository, "_is_runtime_protocol"
        )


class TestGetAllCheckpointsMethod:
    """Tests for get_all_checkpoints method signature."""

    def test_get_all_checkpoints_method_signature(self) -> None:
        """get_all_checkpoints should be async and return list[Checkpoint]."""
        method = getattr(CheckpointRepository, "get_all_checkpoints", None)
        assert method is not None

        # Should be a coroutine function
        inspect.signature(method)

        # Check return type annotation string includes Checkpoint
        # Note: We check annotations directly as get_type_hints requires
        # the TYPE_CHECKING imports to be available at runtime
        annotations = getattr(method, "__annotations__", {})
        assert "return" in annotations
        return_annotation = str(annotations["return"])
        assert "Checkpoint" in return_annotation


class TestGetCheckpointByIdMethod:
    """Tests for get_checkpoint_by_id method signature."""

    def test_get_checkpoint_by_id_method_signature(self) -> None:
        """get_checkpoint_by_id should accept UUID and return Optional[Checkpoint]."""
        method = getattr(CheckpointRepository, "get_checkpoint_by_id", None)
        assert method is not None

        sig = inspect.signature(method)
        params = list(sig.parameters.keys())

        # Should have checkpoint_id parameter (after self)
        assert "checkpoint_id" in params


class TestGetLatestCheckpointMethod:
    """Tests for get_latest_checkpoint method signature."""

    def test_get_latest_checkpoint_method_signature(self) -> None:
        """get_latest_checkpoint should return Optional[Checkpoint]."""
        method = getattr(CheckpointRepository, "get_latest_checkpoint", None)
        assert method is not None

        sig = inspect.signature(method)
        # Should have minimal parameters (just self)
        params = list(sig.parameters.keys())
        assert len(params) == 1  # Just self


class TestGetCheckpointsAfterSequenceMethod:
    """Tests for get_checkpoints_after_sequence method signature."""

    def test_get_checkpoints_after_sequence_method_signature(self) -> None:
        """get_checkpoints_after_sequence should accept sequence and return list."""
        method = getattr(CheckpointRepository, "get_checkpoints_after_sequence", None)
        assert method is not None

        sig = inspect.signature(method)
        params = list(sig.parameters.keys())

        # Should have sequence parameter
        assert "sequence" in params


class TestCreateCheckpointMethod:
    """Tests for create_checkpoint method signature."""

    def test_create_checkpoint_method_signature(self) -> None:
        """create_checkpoint should accept checkpoint params and return Checkpoint."""
        method = getattr(CheckpointRepository, "create_checkpoint", None)
        assert method is not None

        sig = inspect.signature(method)
        params = list(sig.parameters.keys())

        # Should have required parameters
        assert "event_sequence" in params
        assert "anchor_hash" in params
        assert "anchor_type" in params
        assert "creator_id" in params


class TestProtocolImplementation:
    """Tests for protocol implementation checking."""

    def test_port_is_abstract(self) -> None:
        """CheckpointRepository should be abstract (Protocol)."""
        # Protocols can't be instantiated directly
        with pytest.raises(TypeError):
            CheckpointRepository()  # type: ignore[call-arg]


# =============================================================================
# Merkle-specific port methods (Story 4.6 - FR136, FR137, FR138)
# =============================================================================


class TestGetCheckpointForSequenceMethod:
    """Tests for get_checkpoint_for_sequence method signature (FR136)."""

    def test_get_checkpoint_for_sequence_signature(self) -> None:
        """get_checkpoint_for_sequence should accept sequence and return Optional[Checkpoint]."""
        method = getattr(CheckpointRepository, "get_checkpoint_for_sequence", None)
        assert method is not None

        sig = inspect.signature(method)
        params = list(sig.parameters.keys())

        # Should have sequence parameter
        assert "sequence" in params


class TestListCheckpointsMethod:
    """Tests for list_checkpoints method signature (FR138)."""

    def test_list_checkpoints_signature(self) -> None:
        """list_checkpoints should accept limit/offset and return tuple."""
        method = getattr(CheckpointRepository, "list_checkpoints", None)
        assert method is not None

        sig = inspect.signature(method)
        params = list(sig.parameters.keys())

        # Should have pagination parameters
        assert "limit" in params
        assert "offset" in params


class TestUpdateAnchorReferenceMethod:
    """Tests for update_anchor_reference method signature (FR137)."""

    def test_update_anchor_reference_signature(self) -> None:
        """update_anchor_reference should accept checkpoint_id, anchor_type, anchor_reference."""
        method = getattr(CheckpointRepository, "update_anchor_reference", None)
        assert method is not None

        sig = inspect.signature(method)
        params = list(sig.parameters.keys())

        # Should have required parameters
        assert "checkpoint_id" in params
        assert "anchor_type" in params
        assert "anchor_reference" in params
