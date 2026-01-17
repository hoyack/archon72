"""TaskActivationPort - Interface for task activation operations.

Story: consent-gov-2.2: Task Activation Request

This port defines the contract for creating and routing task activation
requests from Earl to Cluster.

Constitutional Guarantees:
- Content MUST pass through Coercion Filter (FR21)
- All Earl→Cluster communication uses async protocol (NFR-INT-01)
- Events emitted via two-phase pattern

References:
- [Source: governance-architecture.md#Filter Pipeline Placement (Locked)]
- [Source: governance-architecture.md#Routing Architecture (Locked)]
"""

from __future__ import annotations

from datetime import timedelta
from typing import Protocol, runtime_checkable
from uuid import UUID

from src.domain.governance.task.task_activation_request import (
    TaskActivationResult,
    TaskStateView,
)
from src.domain.governance.task.task_state import TaskState, TaskStatus


@runtime_checkable
class TaskActivationPort(Protocol):
    """Port for task activation operations.

    This interface defines the contract for creating and managing
    task activation requests. Implementations must:

    1. Create tasks in AUTHORIZED state
    2. Transition through ACTIVATED to ROUTED
    3. Pass content through Coercion Filter
    4. Route to Cluster via async protocol

    Constitutional Guarantee:
    - All content passes through Coercion Filter
    - No bypass path exists for participant messages
    - Events emitted via two-phase pattern
    """

    async def create_activation(
        self,
        earl_id: str,
        cluster_id: str,
        description: str,
        requirements: list[str],
        expected_outcomes: list[str],
        ttl: timedelta | None = None,
    ) -> TaskActivationResult:
        """Create and process a task activation request.

        Flow:
        1. Create task in AUTHORIZED state
        2. Transition to ACTIVATED
        3. Filter content through Coercion Filter
        4. If accepted/transformed: route to Cluster
        5. If rejected: return to Earl for rewrite
        6. If blocked: log violation, do not route

        Args:
            earl_id: ID of the Earl creating the task.
            cluster_id: ID of the Cluster to receive the task.
            description: Task description (subject to filtering).
            requirements: List of requirements (subject to filtering).
            expected_outcomes: Expected deliverables (subject to filtering).
            ttl: Optional TTL override (default 72h per NFR-CONSENT-01).

        Returns:
            TaskActivationResult with filter outcome and routing status.

        Raises:
            ValueError: If required fields are missing or invalid.
        """
        ...

    async def route_to_cluster(
        self,
        task_id: UUID,
        cluster_id: str,
    ) -> bool:
        """Route an activated task to a Cluster.

        This is called after successful filtering to send the
        filtered content to the Cluster via async protocol.

        Args:
            task_id: ID of the task to route.
            cluster_id: ID of the Cluster to receive the task.

        Returns:
            True if routing was successful.

        Raises:
            ValueError: If task is not in a routable state.
        """
        ...

    async def get_task_state(
        self,
        task_id: UUID,
        earl_id: str,
    ) -> TaskStateView:
        """Get current task state for Earl.

        Per FR12, Earl can view task state and history.
        This method verifies Earl ownership before returning.

        Args:
            task_id: ID of the task to retrieve.
            earl_id: ID of the Earl requesting access.

        Returns:
            TaskStateView with current state and metadata.

        Raises:
            UnauthorizedAccessError: If Earl does not own this task.
            TaskNotFoundError: If task does not exist.
        """
        ...

    async def get_task_history(
        self,
        task_id: UUID,
        earl_id: str,
    ) -> list[dict]:
        """Get task event history for Earl.

        Per FR12, Earl can view task state and history.
        Returns all events related to this task.

        Args:
            task_id: ID of the task.
            earl_id: ID of the Earl requesting access.

        Returns:
            List of events related to this task.

        Raises:
            UnauthorizedAccessError: If Earl does not own this task.
            TaskNotFoundError: If task does not exist.
        """
        ...


@runtime_checkable
class TaskStatePort(Protocol):
    """Port for task state operations.

    This interface provides task state persistence and retrieval.
    Used by TaskActivationService for state management.
    """

    async def create_task(
        self,
        earl_id: str,
        cluster_id: str | None,
        ttl: timedelta,
    ) -> TaskState:
        """Create a new task in AUTHORIZED state.

        Args:
            earl_id: ID of the Earl who owns this task.
            cluster_id: Optional Cluster ID (set during routing).
            ttl: Time-to-live for acceptance.

        Returns:
            New TaskState in AUTHORIZED status.
        """
        ...

    async def get_task(self, task_id: UUID) -> TaskState:
        """Get a task by ID.

        Args:
            task_id: ID of the task to retrieve.

        Returns:
            The TaskState.

        Raises:
            TaskNotFoundError: If task does not exist.
        """
        ...

    async def save_task(self, task: TaskState) -> None:
        """Persist a task state.

        Args:
            task: The TaskState to save.
        """
        ...

    async def get_tasks_by_state_and_cluster(
        self,
        status: TaskStatus,
        cluster_id: str,
        limit: int = 100,
    ) -> list[TaskState]:
        """Get tasks in a specific state for a Cluster.

        Used by TaskConsentService to query pending requests.

        Args:
            status: Task status to filter by.
            cluster_id: Cluster ID to filter by.
            limit: Maximum number of results.

        Returns:
            List of TaskState objects matching criteria.
        """
        ...

    async def get_tasks_by_status(
        self,
        status: TaskStatus,
        limit: int = 1000,
    ) -> list[TaskState]:
        """Get all tasks in a specific state across all clusters.

        Used by TaskTimeoutService for timeout processing.
        Returns tasks regardless of which cluster they are assigned to.

        Story: consent-gov-2.5 (Task TTL & Auto-Transitions)

        Args:
            status: Task status to filter by.
            limit: Maximum number of results.

        Returns:
            List of TaskState objects matching the status criteria.
        """
        ...


class UnauthorizedAccessError(Exception):
    """Raised when an actor attempts unauthorized access.

    Per FR12, only the Earl who created a task can view its state.
    """

    def __init__(self, actor_id: str, resource_id: str, message: str | None = None):
        self.actor_id = actor_id
        self.resource_id = resource_id
        super().__init__(
            message or f"Actor {actor_id} is not authorized to access {resource_id}"
        )


class TaskNotFoundError(Exception):
    """Raised when a task is not found."""

    def __init__(self, task_id: UUID):
        self.task_id = task_id
        super().__init__(f"Task {task_id} not found")
