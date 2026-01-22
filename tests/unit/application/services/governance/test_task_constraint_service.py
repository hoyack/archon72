"""Unit tests for TaskConstraintService.

Story: consent-gov-2.7: Role-Specific Task Constraints

These tests validate the service implementation for task constraint enforcement,
including constraint validation, violation events, and error messages.

Tests cover:
- AC3: Role constraints validated at operation time
- AC4: Constraint violations logged and rejected
- AC7: Constraint validation uses rank-matrix.yaml
- AC8: Violations emit executive.task.constraint_violated event
- AC9: Clear error messages indicate which constraint was violated
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest


class TestTaskConstraintServiceImport:
    """Tests for TaskConstraintService imports."""

    def test_service_can_be_imported(self) -> None:
        """TaskConstraintService can be imported from governance services."""
        from src.application.services.governance.task_constraint_service import (
            TaskConstraintService,
        )

        assert TaskConstraintService is not None


class TestTaskConstraintServiceCreation:
    """Tests for TaskConstraintService instantiation."""

    @pytest.fixture
    def mock_event_emitter(self) -> AsyncMock:
        """Create mock event emitter."""
        emitter = AsyncMock()
        emitter.emit = AsyncMock()
        return emitter

    @pytest.fixture
    def mock_permission_matrix(self) -> MagicMock:
        """Create mock permission matrix."""
        matrix = MagicMock()
        return matrix

    def test_service_creation_minimal(
        self,
        mock_event_emitter: AsyncMock,
    ) -> None:
        """Service can be created with minimal dependencies."""
        from src.application.services.governance.task_constraint_service import (
            TaskConstraintService,
        )

        service = TaskConstraintService(event_emitter=mock_event_emitter)
        assert service is not None

    def test_service_creation_with_permission_matrix(
        self,
        mock_event_emitter: AsyncMock,
        mock_permission_matrix: MagicMock,
    ) -> None:
        """Service can be created with permission matrix."""
        from src.application.services.governance.task_constraint_service import (
            TaskConstraintService,
        )

        service = TaskConstraintService(
            event_emitter=mock_event_emitter,
            permission_matrix=mock_permission_matrix,
        )
        assert service is not None


class TestValidateOperation:
    """Tests for validate_operation method."""

    @pytest.fixture
    def mock_event_emitter(self) -> AsyncMock:
        """Create mock event emitter."""
        emitter = AsyncMock()
        emitter.emit = AsyncMock()
        return emitter

    @pytest.fixture
    def service(self, mock_event_emitter: AsyncMock) -> Any:
        """Create service instance."""
        from src.application.services.governance.task_constraint_service import (
            TaskConstraintService,
        )

        return TaskConstraintService(event_emitter=mock_event_emitter)

    @pytest.mark.asyncio
    async def test_earl_can_create_activation(self, service: Any) -> None:
        """Earl can create activation - returns None (AC3)."""
        from src.domain.governance.task.task_constraint import TaskOperation

        result = await service.validate_operation(
            actor_id=uuid4(),
            actor_role="Earl",
            operation=TaskOperation.CREATE_ACTIVATION,
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_earl_cannot_accept_returns_violation(self, service: Any) -> None:
        """Earl cannot accept - returns ConstraintViolation (AC3, AC4)."""
        from src.application.ports.governance.task_constraint_port import (
            ConstraintViolation,
        )
        from src.domain.governance.task.task_constraint import TaskOperation

        result = await service.validate_operation(
            actor_id=uuid4(),
            actor_role="Earl",
            operation=TaskOperation.ACCEPT,
        )

        assert result is not None
        assert isinstance(result, ConstraintViolation)
        assert result.actor_role == "Earl"
        assert result.attempted_operation == TaskOperation.ACCEPT

    @pytest.mark.asyncio
    async def test_cluster_can_accept(self, service: Any) -> None:
        """Cluster can accept - returns None (AC2)."""
        from src.domain.governance.task.task_constraint import TaskOperation

        result = await service.validate_operation(
            actor_id=uuid4(),
            actor_role="Cluster",
            operation=TaskOperation.ACCEPT,
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_cluster_cannot_create_returns_violation(self, service: Any) -> None:
        """Cluster cannot create activation - returns violation (AC2)."""
        from src.application.ports.governance.task_constraint_port import (
            ConstraintViolation,
        )
        from src.domain.governance.task.task_constraint import TaskOperation

        result = await service.validate_operation(
            actor_id=uuid4(),
            actor_role="Cluster",
            operation=TaskOperation.CREATE_ACTIVATION,
        )

        assert result is not None
        assert isinstance(result, ConstraintViolation)
        assert result.actor_role == "Cluster"

    @pytest.mark.asyncio
    async def test_violation_includes_task_id(self, service: Any) -> None:
        """Violation includes task_id when provided."""
        from src.domain.governance.task.task_constraint import TaskOperation

        task_id = uuid4()
        result = await service.validate_operation(
            actor_id=uuid4(),
            actor_role="Earl",
            operation=TaskOperation.ACCEPT,
            task_id=task_id,
        )

        assert result is not None
        assert result.task_id == task_id


class TestRequireValidOperation:
    """Tests for require_valid_operation method."""

    @pytest.fixture
    def mock_event_emitter(self) -> AsyncMock:
        """Create mock event emitter."""
        emitter = AsyncMock()
        emitter.emit = AsyncMock()
        return emitter

    @pytest.fixture
    def service(self, mock_event_emitter: AsyncMock) -> Any:
        """Create service instance."""
        from src.application.services.governance.task_constraint_service import (
            TaskConstraintService,
        )

        return TaskConstraintService(event_emitter=mock_event_emitter)

    @pytest.mark.asyncio
    async def test_allowed_operation_no_error(self, service: Any) -> None:
        """Allowed operation does not raise error."""
        from src.domain.governance.task.task_constraint import TaskOperation

        # Should not raise
        await service.require_valid_operation(
            actor_id=uuid4(),
            actor_role="Earl",
            operation=TaskOperation.CREATE_ACTIVATION,
        )

    @pytest.mark.asyncio
    async def test_prohibited_operation_raises_error(self, service: Any) -> None:
        """Prohibited operation raises ConstraintViolationError (AC4)."""
        from src.application.ports.governance.task_constraint_port import (
            ConstraintViolationError,
        )
        from src.domain.governance.task.task_constraint import TaskOperation

        with pytest.raises(ConstraintViolationError) as exc_info:
            await service.require_valid_operation(
                actor_id=uuid4(),
                actor_role="Earl",
                operation=TaskOperation.ACCEPT,
            )

        assert exc_info.value.violation.actor_role == "Earl"
        assert exc_info.value.violation.attempted_operation == TaskOperation.ACCEPT


class TestViolationEvents:
    """Tests for violation event emission."""

    @pytest.fixture
    def mock_event_emitter(self) -> AsyncMock:
        """Create mock event emitter."""
        emitter = AsyncMock()
        emitter.emit = AsyncMock()
        return emitter

    @pytest.fixture
    def service(self, mock_event_emitter: AsyncMock) -> Any:
        """Create service instance."""
        from src.application.services.governance.task_constraint_service import (
            TaskConstraintService,
        )

        return TaskConstraintService(event_emitter=mock_event_emitter)

    @pytest.mark.asyncio
    async def test_violation_emits_event(
        self,
        service: Any,
        mock_event_emitter: AsyncMock,
    ) -> None:
        """Constraint violation emits event (AC8)."""
        from src.domain.governance.task.task_constraint import TaskOperation

        await service.validate_operation(
            actor_id=uuid4(),
            actor_role="Earl",
            operation=TaskOperation.ACCEPT,
        )

        mock_event_emitter.emit.assert_called_once()

    @pytest.mark.asyncio
    async def test_violation_event_type_correct(
        self,
        service: Any,
        mock_event_emitter: AsyncMock,
    ) -> None:
        """Violation event has correct type (AC8)."""
        from src.domain.governance.task.task_constraint import TaskOperation

        await service.validate_operation(
            actor_id=uuid4(),
            actor_role="Earl",
            operation=TaskOperation.ACCEPT,
        )

        call_args = mock_event_emitter.emit.call_args
        assert call_args is not None
        assert (
            call_args.kwargs.get("event_type") == "executive.task.constraint_violated"
        )

    @pytest.mark.asyncio
    async def test_violation_event_payload(
        self,
        service: Any,
        mock_event_emitter: AsyncMock,
    ) -> None:
        """Violation event contains required payload fields (AC8)."""
        from src.domain.governance.task.task_constraint import TaskOperation

        actor_id = uuid4()
        await service.validate_operation(
            actor_id=actor_id,
            actor_role="Earl",
            operation=TaskOperation.ACCEPT,
        )

        call_args = mock_event_emitter.emit.call_args
        payload = call_args.kwargs.get("payload", {})

        assert payload.get("actor_id") == str(actor_id)
        assert payload.get("actor_role") == "Earl"
        assert payload.get("attempted_operation") == "accept"
        assert "constraint_violated" in payload
        assert "message" in payload

    @pytest.mark.asyncio
    async def test_allowed_operation_no_event(
        self,
        service: Any,
        mock_event_emitter: AsyncMock,
    ) -> None:
        """Allowed operation does not emit event."""
        from src.domain.governance.task.task_constraint import TaskOperation

        await service.validate_operation(
            actor_id=uuid4(),
            actor_role="Earl",
            operation=TaskOperation.CREATE_ACTIVATION,
        )

        mock_event_emitter.emit.assert_not_called()


class TestErrorMessages:
    """Tests for error message quality."""

    @pytest.fixture
    def mock_event_emitter(self) -> AsyncMock:
        """Create mock event emitter."""
        emitter = AsyncMock()
        emitter.emit = AsyncMock()
        return emitter

    @pytest.fixture
    def service(self, mock_event_emitter: AsyncMock) -> Any:
        """Create service instance."""
        from src.application.services.governance.task_constraint_service import (
            TaskConstraintService,
        )

        return TaskConstraintService(event_emitter=mock_event_emitter)

    @pytest.mark.asyncio
    async def test_violation_message_includes_role(self, service: Any) -> None:
        """Violation message includes the role (AC9)."""
        from src.domain.governance.task.task_constraint import TaskOperation

        result = await service.validate_operation(
            actor_id=uuid4(),
            actor_role="Earl",
            operation=TaskOperation.ACCEPT,
        )

        assert result is not None
        assert "Earl" in result.message

    @pytest.mark.asyncio
    async def test_violation_message_includes_operation(self, service: Any) -> None:
        """Violation message includes the operation (AC9)."""
        from src.domain.governance.task.task_constraint import TaskOperation

        result = await service.validate_operation(
            actor_id=uuid4(),
            actor_role="Earl",
            operation=TaskOperation.ACCEPT,
        )

        assert result is not None
        assert "accept" in result.message.lower()


class TestGetAllowedOperations:
    """Tests for get_allowed_operations method."""

    @pytest.fixture
    def mock_event_emitter(self) -> AsyncMock:
        """Create mock event emitter."""
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_event_emitter: AsyncMock) -> Any:
        """Create service instance."""
        from src.application.services.governance.task_constraint_service import (
            TaskConstraintService,
        )

        return TaskConstraintService(event_emitter=mock_event_emitter)

    @pytest.mark.asyncio
    async def test_earl_allowed_operations(self, service: Any) -> None:
        """Get allowed operations for Earl (AC7)."""
        from src.domain.governance.task.task_constraint import TaskOperation

        result = await service.get_allowed_operations("Earl")

        assert TaskOperation.CREATE_ACTIVATION in result
        assert TaskOperation.VIEW_TASK_STATE in result
        assert TaskOperation.VIEW_TASK_HISTORY in result
        assert TaskOperation.ACCEPT not in result

    @pytest.mark.asyncio
    async def test_cluster_allowed_operations(self, service: Any) -> None:
        """Get allowed operations for Cluster (AC7)."""
        from src.domain.governance.task.task_constraint import TaskOperation

        result = await service.get_allowed_operations("Cluster")

        assert TaskOperation.ACCEPT in result
        assert TaskOperation.DECLINE in result
        assert TaskOperation.HALT in result
        assert TaskOperation.CREATE_ACTIVATION not in result


class TestGetProhibitedOperations:
    """Tests for get_prohibited_operations method."""

    @pytest.fixture
    def mock_event_emitter(self) -> AsyncMock:
        """Create mock event emitter."""
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_event_emitter: AsyncMock) -> Any:
        """Create service instance."""
        from src.application.services.governance.task_constraint_service import (
            TaskConstraintService,
        )

        return TaskConstraintService(event_emitter=mock_event_emitter)

    @pytest.mark.asyncio
    async def test_earl_prohibited_operations(self, service: Any) -> None:
        """Get prohibited operations for Earl (AC7)."""
        from src.domain.governance.task.task_constraint import TaskOperation

        result = await service.get_prohibited_operations("Earl")

        assert TaskOperation.ACCEPT in result
        assert TaskOperation.DECLINE in result
        assert TaskOperation.HALT in result
        assert TaskOperation.CREATE_ACTIVATION not in result

    @pytest.mark.asyncio
    async def test_cluster_prohibited_operations(self, service: Any) -> None:
        """Get prohibited operations for Cluster (AC7)."""
        from src.domain.governance.task.task_constraint import TaskOperation

        result = await service.get_prohibited_operations("Cluster")

        assert TaskOperation.CREATE_ACTIVATION in result
        assert TaskOperation.ACCEPT not in result
