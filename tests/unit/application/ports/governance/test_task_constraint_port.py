"""Unit tests for TaskConstraintPort interface.

Story: consent-gov-2.7: Role-Specific Task Constraints

These tests validate the port interface for task constraint enforcement,
ensuring role-specific operations are properly validated.

Tests cover:
- AC3: Role constraints validated at operation time
- AC4: Constraint violations logged and rejected
"""

from __future__ import annotations

from typing import Protocol
from uuid import uuid4

import pytest


class TestTaskConstraintPort:
    """Tests for TaskConstraintPort interface definition."""

    def test_constraint_port_can_be_imported(self) -> None:
        """TaskConstraintPort can be imported from governance ports."""
        from src.application.ports.governance.task_constraint_port import (
            TaskConstraintPort,
        )

        assert TaskConstraintPort is not None

    def test_constraint_violation_can_be_imported(self) -> None:
        """ConstraintViolation can be imported from governance ports."""
        from src.application.ports.governance.task_constraint_port import (
            ConstraintViolation,
        )

        assert ConstraintViolation is not None

    def test_task_operation_enum_can_be_imported(self) -> None:
        """TaskOperation enum can be imported from governance ports."""
        from src.application.ports.governance.task_constraint_port import (
            TaskOperation,
        )

        assert TaskOperation is not None


class TestConstraintViolation:
    """Tests for ConstraintViolation data class."""

    def test_constraint_violation_creation(self) -> None:
        """ConstraintViolation can be created with required fields."""
        from src.application.ports.governance.task_constraint_port import (
            ConstraintViolation,
            TaskOperation,
        )

        violation = ConstraintViolation(
            actor_id=uuid4(),
            actor_role="Earl",
            attempted_operation=TaskOperation.ACCEPT,
            constraint_violated="operation_not_allowed",
            message="Earl cannot perform accept",
        )

        assert violation.actor_role == "Earl"
        assert violation.attempted_operation == TaskOperation.ACCEPT
        assert violation.constraint_violated == "operation_not_allowed"
        assert "Earl cannot perform accept" in violation.message

    def test_constraint_violation_is_frozen(self) -> None:
        """ConstraintViolation is immutable (frozen)."""
        from src.application.ports.governance.task_constraint_port import (
            ConstraintViolation,
            TaskOperation,
        )

        violation = ConstraintViolation(
            actor_id=uuid4(),
            actor_role="Earl",
            attempted_operation=TaskOperation.ACCEPT,
            constraint_violated="operation_not_allowed",
            message="Earl cannot perform accept",
        )

        with pytest.raises(AttributeError):
            violation.actor_role = "Duke"  # type: ignore[misc]

    def test_constraint_violation_with_task_id(self) -> None:
        """ConstraintViolation can include optional task_id."""
        from src.application.ports.governance.task_constraint_port import (
            ConstraintViolation,
            TaskOperation,
        )

        task_id = uuid4()
        violation = ConstraintViolation(
            actor_id=uuid4(),
            actor_role="Earl",
            attempted_operation=TaskOperation.ACCEPT,
            constraint_violated="operation_not_allowed",
            message="Earl cannot perform accept",
            task_id=task_id,
        )

        assert violation.task_id == task_id


class TestTaskOperation:
    """Tests for TaskOperation enum."""

    def test_earl_operations_exist(self) -> None:
        """Earl operations are defined in TaskOperation."""
        from src.application.ports.governance.task_constraint_port import (
            TaskOperation,
        )

        # Earl can do these
        assert TaskOperation.CREATE_ACTIVATION is not None
        assert TaskOperation.VIEW_TASK_STATE is not None
        assert TaskOperation.VIEW_TASK_HISTORY is not None

    def test_cluster_operations_exist(self) -> None:
        """Cluster operations are defined in TaskOperation."""
        from src.application.ports.governance.task_constraint_port import (
            TaskOperation,
        )

        # Cluster can do these
        assert TaskOperation.ACCEPT is not None
        assert TaskOperation.DECLINE is not None
        assert TaskOperation.HALT is not None
        assert TaskOperation.SUBMIT_RESULT is not None
        assert TaskOperation.SUBMIT_PROBLEM is not None

    def test_system_operations_exist(self) -> None:
        """System operations are defined in TaskOperation."""
        from src.application.ports.governance.task_constraint_port import (
            TaskOperation,
        )

        # System can do these
        assert TaskOperation.AUTO_DECLINE is not None
        assert TaskOperation.AUTO_START is not None
        assert TaskOperation.AUTO_QUARANTINE is not None
        assert TaskOperation.SEND_REMINDER is not None

    def test_operations_have_string_values(self) -> None:
        """TaskOperation values are snake_case strings."""
        from src.application.ports.governance.task_constraint_port import (
            TaskOperation,
        )

        assert TaskOperation.CREATE_ACTIVATION.value == "create_activation"
        assert TaskOperation.ACCEPT.value == "accept"
        assert TaskOperation.DECLINE.value == "decline"


class TestTaskConstraintPortProtocol:
    """Tests for TaskConstraintPort protocol methods."""

    def test_port_is_protocol(self) -> None:
        """TaskConstraintPort is a Protocol."""
        from src.application.ports.governance.task_constraint_port import (
            TaskConstraintPort,
        )

        assert hasattr(TaskConstraintPort, "__protocol_attrs__") or issubclass(
            TaskConstraintPort, Protocol
        )

    def test_port_is_runtime_checkable(self) -> None:
        """TaskConstraintPort is runtime checkable."""
        from src.application.ports.governance.task_constraint_port import (
            TaskConstraintPort,
        )

        # Runtime checkable protocols can be used with isinstance
        # This verifies the @runtime_checkable decorator is applied
        assert hasattr(TaskConstraintPort, "_is_runtime_protocol")

    def test_validate_operation_method_exists(self) -> None:
        """TaskConstraintPort has validate_operation method."""
        from src.application.ports.governance.task_constraint_port import (
            TaskConstraintPort,
        )

        # Protocol should define validate_operation
        assert hasattr(TaskConstraintPort, "validate_operation")

    def test_require_valid_operation_method_exists(self) -> None:
        """TaskConstraintPort has require_valid_operation method."""
        from src.application.ports.governance.task_constraint_port import (
            TaskConstraintPort,
        )

        # Protocol should define require_valid_operation
        assert hasattr(TaskConstraintPort, "require_valid_operation")


class TestConstraintViolationError:
    """Tests for ConstraintViolationError exception."""

    def test_constraint_violation_error_can_be_imported(self) -> None:
        """ConstraintViolationError can be imported."""
        from src.application.ports.governance.task_constraint_port import (
            ConstraintViolationError,
        )

        assert ConstraintViolationError is not None

    def test_constraint_violation_error_contains_violation(self) -> None:
        """ConstraintViolationError contains the violation details."""
        from src.application.ports.governance.task_constraint_port import (
            ConstraintViolation,
            ConstraintViolationError,
            TaskOperation,
        )

        violation = ConstraintViolation(
            actor_id=uuid4(),
            actor_role="Earl",
            attempted_operation=TaskOperation.ACCEPT,
            constraint_violated="operation_not_allowed",
            message="Earl cannot perform accept",
        )

        error = ConstraintViolationError(violation)

        assert error.violation == violation
        assert "Earl cannot perform accept" in str(error)

    def test_constraint_violation_error_is_exception(self) -> None:
        """ConstraintViolationError is an Exception."""
        from src.application.ports.governance.task_constraint_port import (
            ConstraintViolationError,
        )

        assert issubclass(ConstraintViolationError, Exception)
