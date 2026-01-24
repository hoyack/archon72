"""Integration tests for TaskConstraintService with task operations.

Story: consent-gov-2.7: Role-Specific Task Constraints

These tests validate the integration of constraint enforcement with
existing task services, ensuring separation of powers is maintained.

Tests cover:
- AC1: Earl can only activate tasks (cannot compel or change scope)
- AC2: Cluster can only be activated (not commanded)
- AC5: Earl cannot modify task scope after creation
- AC6: Earl cannot bypass Cluster consent
- AC10: Comprehensive integration tests
"""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.application.ports.governance.task_constraint_port import (
    ConstraintViolationError,
)
from src.application.services.governance.task_constraint_service import (
    TaskConstraintService,
)
from src.domain.governance.task.task_constraint import TaskOperation


class TestEarlConstraintsIntegration:
    """Integration tests for Earl constraint enforcement (AC1, AC5, AC6)."""

    @pytest.fixture
    def mock_event_emitter(self) -> AsyncMock:
        """Create mock event emitter."""
        emitter = AsyncMock()
        emitter.emit = AsyncMock()
        return emitter

    @pytest.fixture
    def constraint_service(
        self, mock_event_emitter: AsyncMock
    ) -> TaskConstraintService:
        """Create constraint service instance."""
        return TaskConstraintService(event_emitter=mock_event_emitter)

    @pytest.mark.asyncio
    async def test_earl_can_activate_ac1(
        self,
        constraint_service: TaskConstraintService,
    ) -> None:
        """Earl can create activation requests (AC1)."""
        # Earl CAN activate
        violation = await constraint_service.validate_operation(
            actor_id=uuid4(),
            actor_role="Earl",
            operation=TaskOperation.CREATE_ACTIVATION,
        )
        assert violation is None

    @pytest.mark.asyncio
    async def test_earl_cannot_compel_ac1(
        self,
        constraint_service: TaskConstraintService,
    ) -> None:
        """Earl cannot compel Cluster to accept (AC1)."""
        # Earl CANNOT accept on behalf of Cluster
        violation = await constraint_service.validate_operation(
            actor_id=uuid4(),
            actor_role="Earl",
            operation=TaskOperation.ACCEPT,
        )
        assert violation is not None
        assert violation.actor_role == "Earl"
        assert violation.attempted_operation == TaskOperation.ACCEPT

    @pytest.mark.asyncio
    async def test_earl_cannot_decline_for_cluster(
        self,
        constraint_service: TaskConstraintService,
    ) -> None:
        """Earl cannot decline on behalf of Cluster."""
        violation = await constraint_service.validate_operation(
            actor_id=uuid4(),
            actor_role="Earl",
            operation=TaskOperation.DECLINE,
        )
        assert violation is not None
        assert violation.constraint_violated == "operation_prohibited"

    @pytest.mark.asyncio
    async def test_earl_cannot_halt_cluster_work(
        self,
        constraint_service: TaskConstraintService,
    ) -> None:
        """Earl cannot halt Cluster's work."""
        violation = await constraint_service.validate_operation(
            actor_id=uuid4(),
            actor_role="Earl",
            operation=TaskOperation.HALT,
        )
        assert violation is not None

    @pytest.mark.asyncio
    async def test_earl_cannot_submit_result_for_cluster(
        self,
        constraint_service: TaskConstraintService,
    ) -> None:
        """Earl cannot submit results on behalf of Cluster."""
        violation = await constraint_service.validate_operation(
            actor_id=uuid4(),
            actor_role="Earl",
            operation=TaskOperation.SUBMIT_RESULT,
        )
        assert violation is not None

    @pytest.mark.asyncio
    async def test_earl_can_view_task_state(
        self,
        constraint_service: TaskConstraintService,
    ) -> None:
        """Earl can view task state."""
        violation = await constraint_service.validate_operation(
            actor_id=uuid4(),
            actor_role="Earl",
            operation=TaskOperation.VIEW_TASK_STATE,
        )
        assert violation is None

    @pytest.mark.asyncio
    async def test_earl_can_view_task_history(
        self,
        constraint_service: TaskConstraintService,
    ) -> None:
        """Earl can view task history."""
        violation = await constraint_service.validate_operation(
            actor_id=uuid4(),
            actor_role="Earl",
            operation=TaskOperation.VIEW_TASK_HISTORY,
        )
        assert violation is None


class TestClusterConstraintsIntegration:
    """Integration tests for Cluster constraint enforcement (AC2)."""

    @pytest.fixture
    def mock_event_emitter(self) -> AsyncMock:
        """Create mock event emitter."""
        emitter = AsyncMock()
        emitter.emit = AsyncMock()
        return emitter

    @pytest.fixture
    def constraint_service(
        self, mock_event_emitter: AsyncMock
    ) -> TaskConstraintService:
        """Create constraint service instance."""
        return TaskConstraintService(event_emitter=mock_event_emitter)

    @pytest.mark.asyncio
    async def test_cluster_can_accept_ac2(
        self,
        constraint_service: TaskConstraintService,
    ) -> None:
        """Cluster can accept activation requests (AC2)."""
        violation = await constraint_service.validate_operation(
            actor_id=uuid4(),
            actor_role="Cluster",
            operation=TaskOperation.ACCEPT,
        )
        assert violation is None

    @pytest.mark.asyncio
    async def test_cluster_can_decline_ac2(
        self,
        constraint_service: TaskConstraintService,
    ) -> None:
        """Cluster can decline activation requests."""
        violation = await constraint_service.validate_operation(
            actor_id=uuid4(),
            actor_role="Cluster",
            operation=TaskOperation.DECLINE,
        )
        assert violation is None

    @pytest.mark.asyncio
    async def test_cluster_can_halt_own_work(
        self,
        constraint_service: TaskConstraintService,
    ) -> None:
        """Cluster can halt their own in-progress work."""
        violation = await constraint_service.validate_operation(
            actor_id=uuid4(),
            actor_role="Cluster",
            operation=TaskOperation.HALT,
        )
        assert violation is None

    @pytest.mark.asyncio
    async def test_cluster_can_submit_result(
        self,
        constraint_service: TaskConstraintService,
    ) -> None:
        """Cluster can submit task results."""
        violation = await constraint_service.validate_operation(
            actor_id=uuid4(),
            actor_role="Cluster",
            operation=TaskOperation.SUBMIT_RESULT,
        )
        assert violation is None

    @pytest.mark.asyncio
    async def test_cluster_can_submit_problem(
        self,
        constraint_service: TaskConstraintService,
    ) -> None:
        """Cluster can submit problem reports."""
        violation = await constraint_service.validate_operation(
            actor_id=uuid4(),
            actor_role="Cluster",
            operation=TaskOperation.SUBMIT_PROBLEM,
        )
        assert violation is None

    @pytest.mark.asyncio
    async def test_cluster_cannot_self_assign_ac2(
        self,
        constraint_service: TaskConstraintService,
    ) -> None:
        """Cluster cannot create activations / self-assign (AC2)."""
        violation = await constraint_service.validate_operation(
            actor_id=uuid4(),
            actor_role="Cluster",
            operation=TaskOperation.CREATE_ACTIVATION,
        )
        assert violation is not None
        assert violation.actor_role == "Cluster"


class TestSystemConstraintsIntegration:
    """Integration tests for system operations."""

    @pytest.fixture
    def mock_event_emitter(self) -> AsyncMock:
        """Create mock event emitter."""
        emitter = AsyncMock()
        emitter.emit = AsyncMock()
        return emitter

    @pytest.fixture
    def constraint_service(
        self, mock_event_emitter: AsyncMock
    ) -> TaskConstraintService:
        """Create constraint service instance."""
        return TaskConstraintService(event_emitter=mock_event_emitter)

    @pytest.mark.asyncio
    async def test_system_can_auto_decline(
        self,
        constraint_service: TaskConstraintService,
    ) -> None:
        """System can auto-decline on TTL expiry."""
        violation = await constraint_service.validate_operation(
            actor_id=uuid4(),
            actor_role="system",
            operation=TaskOperation.AUTO_DECLINE,
        )
        assert violation is None

    @pytest.mark.asyncio
    async def test_system_can_auto_start(
        self,
        constraint_service: TaskConstraintService,
    ) -> None:
        """System can auto-start after acceptance."""
        violation = await constraint_service.validate_operation(
            actor_id=uuid4(),
            actor_role="system",
            operation=TaskOperation.AUTO_START,
        )
        assert violation is None

    @pytest.mark.asyncio
    async def test_system_can_auto_quarantine(
        self,
        constraint_service: TaskConstraintService,
    ) -> None:
        """System can auto-quarantine on halt."""
        violation = await constraint_service.validate_operation(
            actor_id=uuid4(),
            actor_role="system",
            operation=TaskOperation.AUTO_QUARANTINE,
        )
        assert violation is None

    @pytest.mark.asyncio
    async def test_system_can_send_reminder(
        self,
        constraint_service: TaskConstraintService,
    ) -> None:
        """System can send reminder notifications."""
        violation = await constraint_service.validate_operation(
            actor_id=uuid4(),
            actor_role="system",
            operation=TaskOperation.SEND_REMINDER,
        )
        assert violation is None


class TestViolationEventIntegration:
    """Integration tests for violation event emission (AC8)."""

    @pytest.fixture
    def mock_event_emitter(self) -> AsyncMock:
        """Create mock event emitter."""
        emitter = AsyncMock()
        emitter.emit = AsyncMock()
        return emitter

    @pytest.fixture
    def constraint_service(
        self, mock_event_emitter: AsyncMock
    ) -> TaskConstraintService:
        """Create constraint service instance."""
        return TaskConstraintService(event_emitter=mock_event_emitter)

    @pytest.mark.asyncio
    async def test_earl_accept_violation_emits_event(
        self,
        constraint_service: TaskConstraintService,
        mock_event_emitter: AsyncMock,
    ) -> None:
        """Earl attempting accept emits violation event (AC8)."""
        actor_id = uuid4()
        task_id = uuid4()

        await constraint_service.validate_operation(
            actor_id=actor_id,
            actor_role="Earl",
            operation=TaskOperation.ACCEPT,
            task_id=task_id,
        )

        # Verify event was emitted
        mock_event_emitter.emit.assert_called_once()
        call_kwargs = mock_event_emitter.emit.call_args.kwargs

        assert call_kwargs["event_type"] == "executive.task.constraint_violated"
        assert call_kwargs["actor"] == str(actor_id)
        payload = call_kwargs["payload"]
        assert payload["actor_role"] == "Earl"
        assert payload["attempted_operation"] == "accept"
        assert payload["task_id"] == str(task_id)

    @pytest.mark.asyncio
    async def test_cluster_create_violation_emits_event(
        self,
        constraint_service: TaskConstraintService,
        mock_event_emitter: AsyncMock,
    ) -> None:
        """Cluster attempting create_activation emits violation event (AC8)."""
        actor_id = uuid4()

        await constraint_service.validate_operation(
            actor_id=actor_id,
            actor_role="Cluster",
            operation=TaskOperation.CREATE_ACTIVATION,
        )

        # Verify event was emitted
        mock_event_emitter.emit.assert_called_once()
        call_kwargs = mock_event_emitter.emit.call_args.kwargs
        payload = call_kwargs["payload"]

        assert payload["actor_role"] == "Cluster"
        assert payload["attempted_operation"] == "create_activation"

    @pytest.mark.asyncio
    async def test_knight_can_observe_violation_events(
        self,
        constraint_service: TaskConstraintService,
        mock_event_emitter: AsyncMock,
    ) -> None:
        """Knight can observe all violation events (via event stream)."""
        # First, trigger a violation
        await constraint_service.validate_operation(
            actor_id=uuid4(),
            actor_role="Earl",
            operation=TaskOperation.ACCEPT,
        )

        # Verify event was emitted (Knight would subscribe to this)
        mock_event_emitter.emit.assert_called_once()
        call_kwargs = mock_event_emitter.emit.call_args.kwargs
        assert call_kwargs["event_type"] == "executive.task.constraint_violated"


class TestConstraintViolationErrorIntegration:
    """Integration tests for ConstraintViolationError handling (AC4)."""

    @pytest.fixture
    def mock_event_emitter(self) -> AsyncMock:
        """Create mock event emitter."""
        emitter = AsyncMock()
        emitter.emit = AsyncMock()
        return emitter

    @pytest.fixture
    def constraint_service(
        self, mock_event_emitter: AsyncMock
    ) -> TaskConstraintService:
        """Create constraint service instance."""
        return TaskConstraintService(event_emitter=mock_event_emitter)

    @pytest.mark.asyncio
    async def test_require_valid_operation_raises_on_violation(
        self,
        constraint_service: TaskConstraintService,
    ) -> None:
        """require_valid_operation raises ConstraintViolationError (AC4)."""
        with pytest.raises(ConstraintViolationError) as exc_info:
            await constraint_service.require_valid_operation(
                actor_id=uuid4(),
                actor_role="Earl",
                operation=TaskOperation.ACCEPT,
            )

        assert exc_info.value.violation.actor_role == "Earl"
        assert "accept" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_exception_contains_clear_message_ac9(
        self,
        constraint_service: TaskConstraintService,
    ) -> None:
        """ConstraintViolationError contains clear message (AC9)."""
        with pytest.raises(ConstraintViolationError) as exc_info:
            await constraint_service.require_valid_operation(
                actor_id=uuid4(),
                actor_role="Earl",
                operation=TaskOperation.ACCEPT,
            )

        error = exc_info.value
        # Message should clearly indicate role and operation
        assert "Earl" in error.violation.message
        assert "accept" in error.violation.message.lower()


class TestSeparationOfPowersIntegration:
    """Integration tests verifying separation of powers enforcement."""

    @pytest.fixture
    def mock_event_emitter(self) -> AsyncMock:
        """Create mock event emitter."""
        emitter = AsyncMock()
        emitter.emit = AsyncMock()
        return emitter

    @pytest.fixture
    def constraint_service(
        self, mock_event_emitter: AsyncMock
    ) -> TaskConstraintService:
        """Create constraint service instance."""
        return TaskConstraintService(event_emitter=mock_event_emitter)

    @pytest.mark.asyncio
    async def test_earl_cluster_separation(
        self,
        constraint_service: TaskConstraintService,
    ) -> None:
        """Earl and Cluster have distinct, non-overlapping task operations."""
        earl_allowed = await constraint_service.get_allowed_operations("Earl")
        cluster_allowed = await constraint_service.get_allowed_operations("Cluster")

        # Verify no overlap except for read operations
        earl_write_ops = {
            op
            for op in earl_allowed
            if op
            not in {TaskOperation.VIEW_TASK_STATE, TaskOperation.VIEW_TASK_HISTORY}
        }
        cluster_ops = set(cluster_allowed)

        # Earl's write operations should not overlap with Cluster operations
        overlap = earl_write_ops & cluster_ops
        assert len(overlap) == 0, f"Unexpected overlap: {overlap}"

    @pytest.mark.asyncio
    async def test_consent_flow_enforced(
        self,
        constraint_service: TaskConstraintService,
    ) -> None:
        """Consent flow is enforced: Earl activates, Cluster accepts/declines."""
        # Step 1: Earl can create activation
        earl_violation = await constraint_service.validate_operation(
            actor_id=uuid4(),
            actor_role="Earl",
            operation=TaskOperation.CREATE_ACTIVATION,
        )
        assert earl_violation is None

        # Step 2: Cluster must be the one to accept/decline
        cluster_accept = await constraint_service.validate_operation(
            actor_id=uuid4(),
            actor_role="Cluster",
            operation=TaskOperation.ACCEPT,
        )
        assert cluster_accept is None

        # Step 3: Earl cannot bypass this
        earl_accept = await constraint_service.validate_operation(
            actor_id=uuid4(),
            actor_role="Earl",
            operation=TaskOperation.ACCEPT,
        )
        assert earl_accept is not None
