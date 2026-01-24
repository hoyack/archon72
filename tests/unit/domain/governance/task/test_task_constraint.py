"""Unit tests for TaskConstraint domain model.

Story: consent-gov-2.7: Role-Specific Task Constraints

These tests validate the domain model for task constraints, including
the ConstraintRule value object and role-operation mappings.

Tests cover:
- AC1: Earl can only activate tasks (cannot compel or change scope)
- AC2: Cluster can only be activated (not commanded)
- AC3: Role constraints validated at operation time
"""

from __future__ import annotations

import pytest


class TestConstraintRule:
    """Tests for ConstraintRule value object."""

    def test_constraint_rule_can_be_imported(self) -> None:
        """ConstraintRule can be imported from domain."""
        from src.domain.governance.task.task_constraint import ConstraintRule

        assert ConstraintRule is not None

    def test_constraint_rule_creation(self) -> None:
        """ConstraintRule can be created with required fields."""
        from src.domain.governance.task.task_constraint import ConstraintRule

        rule = ConstraintRule(
            rule_id="earl_no_compel",
            description="Earl cannot compel Cluster to accept",
            prd_reference="FR14",
            severity="major",
        )

        assert rule.rule_id == "earl_no_compel"
        assert rule.description == "Earl cannot compel Cluster to accept"
        assert rule.prd_reference == "FR14"
        assert rule.severity == "major"

    def test_constraint_rule_is_frozen(self) -> None:
        """ConstraintRule is immutable (frozen)."""
        from src.domain.governance.task.task_constraint import ConstraintRule

        rule = ConstraintRule(
            rule_id="test",
            description="Test rule",
            prd_reference="FR14",
            severity="minor",
        )

        with pytest.raises(AttributeError):
            rule.rule_id = "changed"  # type: ignore[misc]


class TestRoleConstraints:
    """Tests for role-specific constraint definitions."""

    def test_earl_constraints_can_be_imported(self) -> None:
        """Earl constraints can be imported from domain."""
        from src.domain.governance.task.task_constraint import EARL_CONSTRAINTS

        assert EARL_CONSTRAINTS is not None
        assert isinstance(EARL_CONSTRAINTS, dict)

    def test_cluster_constraints_can_be_imported(self) -> None:
        """Cluster constraints can be imported from domain."""
        from src.domain.governance.task.task_constraint import CLUSTER_CONSTRAINTS

        assert CLUSTER_CONSTRAINTS is not None
        assert isinstance(CLUSTER_CONSTRAINTS, dict)

    def test_earl_can_create_activation(self) -> None:
        """Earl is allowed to create activation requests (AC1)."""
        from src.domain.governance.task.task_constraint import (
            EARL_CONSTRAINTS,
            TaskOperation,
        )

        allowed = EARL_CONSTRAINTS.get("allowed_operations", frozenset())
        assert TaskOperation.CREATE_ACTIVATION in allowed

    def test_earl_can_view_task_state(self) -> None:
        """Earl is allowed to view task state."""
        from src.domain.governance.task.task_constraint import (
            EARL_CONSTRAINTS,
            TaskOperation,
        )

        allowed = EARL_CONSTRAINTS.get("allowed_operations", frozenset())
        assert TaskOperation.VIEW_TASK_STATE in allowed

    def test_earl_can_view_task_history(self) -> None:
        """Earl is allowed to view task history."""
        from src.domain.governance.task.task_constraint import (
            EARL_CONSTRAINTS,
            TaskOperation,
        )

        allowed = EARL_CONSTRAINTS.get("allowed_operations", frozenset())
        assert TaskOperation.VIEW_TASK_HISTORY in allowed

    def test_earl_cannot_accept(self) -> None:
        """Earl is prohibited from accepting (cannot compel - AC1)."""
        from src.domain.governance.task.task_constraint import (
            EARL_CONSTRAINTS,
            TaskOperation,
        )

        prohibited = EARL_CONSTRAINTS.get("prohibited_operations", frozenset())
        assert TaskOperation.ACCEPT in prohibited

    def test_earl_cannot_decline(self) -> None:
        """Earl is prohibited from declining on behalf of Cluster."""
        from src.domain.governance.task.task_constraint import (
            EARL_CONSTRAINTS,
            TaskOperation,
        )

        prohibited = EARL_CONSTRAINTS.get("prohibited_operations", frozenset())
        assert TaskOperation.DECLINE in prohibited

    def test_cluster_can_accept(self) -> None:
        """Cluster is allowed to accept (AC2)."""
        from src.domain.governance.task.task_constraint import (
            CLUSTER_CONSTRAINTS,
            TaskOperation,
        )

        allowed = CLUSTER_CONSTRAINTS.get("allowed_operations", frozenset())
        assert TaskOperation.ACCEPT in allowed

    def test_cluster_can_decline(self) -> None:
        """Cluster is allowed to decline."""
        from src.domain.governance.task.task_constraint import (
            CLUSTER_CONSTRAINTS,
            TaskOperation,
        )

        allowed = CLUSTER_CONSTRAINTS.get("allowed_operations", frozenset())
        assert TaskOperation.DECLINE in allowed

    def test_cluster_can_halt(self) -> None:
        """Cluster is allowed to halt in-progress tasks."""
        from src.domain.governance.task.task_constraint import (
            CLUSTER_CONSTRAINTS,
            TaskOperation,
        )

        allowed = CLUSTER_CONSTRAINTS.get("allowed_operations", frozenset())
        assert TaskOperation.HALT in allowed

    def test_cluster_cannot_create_activation(self) -> None:
        """Cluster is prohibited from creating activations (cannot be commanded - AC2)."""
        from src.domain.governance.task.task_constraint import (
            CLUSTER_CONSTRAINTS,
            TaskOperation,
        )

        prohibited = CLUSTER_CONSTRAINTS.get("prohibited_operations", frozenset())
        assert TaskOperation.CREATE_ACTIVATION in prohibited


class TestConstraintValidation:
    """Tests for constraint validation logic."""

    def test_is_operation_allowed_function_exists(self) -> None:
        """is_operation_allowed function exists in domain."""
        from src.domain.governance.task.task_constraint import is_operation_allowed

        assert callable(is_operation_allowed)

    def test_is_operation_allowed_earl_create(self) -> None:
        """Earl can create activation (returns True)."""
        from src.domain.governance.task.task_constraint import (
            TaskOperation,
            is_operation_allowed,
        )

        result = is_operation_allowed("Earl", TaskOperation.CREATE_ACTIVATION)
        assert result is True

    def test_is_operation_allowed_earl_accept(self) -> None:
        """Earl cannot accept (returns False - AC1)."""
        from src.domain.governance.task.task_constraint import (
            TaskOperation,
            is_operation_allowed,
        )

        result = is_operation_allowed("Earl", TaskOperation.ACCEPT)
        assert result is False

    def test_is_operation_allowed_cluster_accept(self) -> None:
        """Cluster can accept (returns True - AC2)."""
        from src.domain.governance.task.task_constraint import (
            TaskOperation,
            is_operation_allowed,
        )

        result = is_operation_allowed("Cluster", TaskOperation.ACCEPT)
        assert result is True

    def test_is_operation_allowed_cluster_create(self) -> None:
        """Cluster cannot create activation (returns False - AC2)."""
        from src.domain.governance.task.task_constraint import (
            TaskOperation,
            is_operation_allowed,
        )

        result = is_operation_allowed("Cluster", TaskOperation.CREATE_ACTIVATION)
        assert result is False

    def test_is_operation_prohibited_function_exists(self) -> None:
        """is_operation_prohibited function exists in domain."""
        from src.domain.governance.task.task_constraint import is_operation_prohibited

        assert callable(is_operation_prohibited)

    def test_is_operation_prohibited_earl_accept(self) -> None:
        """Earl is explicitly prohibited from accept."""
        from src.domain.governance.task.task_constraint import (
            TaskOperation,
            is_operation_prohibited,
        )

        result = is_operation_prohibited("Earl", TaskOperation.ACCEPT)
        assert result is True

    def test_is_operation_prohibited_earl_create(self) -> None:
        """Earl is not prohibited from create (allowed)."""
        from src.domain.governance.task.task_constraint import (
            TaskOperation,
            is_operation_prohibited,
        )

        result = is_operation_prohibited("Earl", TaskOperation.CREATE_ACTIVATION)
        assert result is False


class TestGetConstraintViolationReason:
    """Tests for get_constraint_violation_reason function."""

    def test_function_exists(self) -> None:
        """get_constraint_violation_reason function exists."""
        from src.domain.governance.task.task_constraint import (
            get_constraint_violation_reason,
        )

        assert callable(get_constraint_violation_reason)

    def test_returns_none_for_allowed_operation(self) -> None:
        """Returns None when operation is allowed."""
        from src.domain.governance.task.task_constraint import (
            TaskOperation,
            get_constraint_violation_reason,
        )

        result = get_constraint_violation_reason(
            "Earl", TaskOperation.CREATE_ACTIVATION
        )
        assert result is None

    def test_returns_reason_for_prohibited_operation(self) -> None:
        """Returns reason string when operation is prohibited (AC9)."""
        from src.domain.governance.task.task_constraint import (
            TaskOperation,
            get_constraint_violation_reason,
        )

        result = get_constraint_violation_reason("Earl", TaskOperation.ACCEPT)
        assert result is not None
        assert isinstance(result, str)
        assert "Earl" in result or "accept" in result.lower()

    def test_returns_reason_for_not_allowed_operation(self) -> None:
        """Returns reason for operation not in allowed set."""
        from src.domain.governance.task.task_constraint import (
            TaskOperation,
            get_constraint_violation_reason,
        )

        result = get_constraint_violation_reason(
            "Cluster", TaskOperation.CREATE_ACTIVATION
        )
        assert result is not None
        assert isinstance(result, str)
