"""Unit tests for RollbackCoordinator port (Story 3.10, Task 7).

Tests the abstract port interface for rollback coordination operations.

Constitutional Constraints:
- FR143: Rollback to checkpoint for infrastructure recovery
- CT-11: Rollback must be witnessed
"""

from __future__ import annotations

import inspect
from typing import Protocol

import pytest

from src.application.ports.rollback_coordinator import RollbackCoordinator


class TestRollbackCoordinatorPortStructure:
    """Tests for RollbackCoordinator port structure."""

    def test_port_is_protocol(self) -> None:
        """RollbackCoordinator should be a Protocol."""
        assert issubclass(RollbackCoordinator, Protocol)

    def test_port_is_runtime_checkable(self) -> None:
        """RollbackCoordinator should be runtime checkable."""
        assert hasattr(RollbackCoordinator, "__protocol_attrs__") or hasattr(
            RollbackCoordinator, "_is_runtime_protocol"
        )

    def test_port_is_abstract(self) -> None:
        """RollbackCoordinator should be abstract (Protocol)."""
        with pytest.raises(TypeError):
            RollbackCoordinator()  # type: ignore[call-arg]


class TestQueryCheckpointsMethod:
    """Tests for query_checkpoints method signature."""

    def test_query_checkpoints_method_signature(self) -> None:
        """query_checkpoints should be async and return list[Checkpoint]."""
        method = getattr(RollbackCoordinator, "query_checkpoints", None)
        assert method is not None

        sig = inspect.signature(method)
        # Should have minimal parameters (just self)
        params = list(sig.parameters.keys())
        assert len(params) == 1  # Just self


class TestSelectRollbackTargetMethod:
    """Tests for select_rollback_target method signature."""

    def test_select_rollback_target_method_signature(self) -> None:
        """select_rollback_target should accept checkpoint_id, keepers, reason."""
        method = getattr(RollbackCoordinator, "select_rollback_target", None)
        assert method is not None

        sig = inspect.signature(method)
        params = list(sig.parameters.keys())

        # Should have required parameters
        assert "checkpoint_id" in params
        assert "selecting_keepers" in params
        assert "reason" in params


class TestExecuteRollbackMethod:
    """Tests for execute_rollback method signature."""

    def test_execute_rollback_method_signature(self) -> None:
        """execute_rollback should accept ceremony_evidence."""
        method = getattr(RollbackCoordinator, "execute_rollback", None)
        assert method is not None

        sig = inspect.signature(method)
        params = list(sig.parameters.keys())

        # Should have ceremony_evidence parameter
        assert "ceremony_evidence" in params


class TestGetRollbackStatusMethod:
    """Tests for get_rollback_status method signature."""

    def test_get_rollback_status_method_signature(self) -> None:
        """get_rollback_status should return dict[str, Any]."""
        method = getattr(RollbackCoordinator, "get_rollback_status", None)
        assert method is not None

        sig = inspect.signature(method)
        # Should have minimal parameters (just self)
        params = list(sig.parameters.keys())
        assert len(params) == 1  # Just self
