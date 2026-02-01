"""In-memory adapters for governance ports.

Used by the Earl Decomposition Bridge to wire TaskActivationService
without requiring PostgreSQL. These adapters store state in dictionaries
and lists in memory for single-run pipeline execution.

Not for production use — these adapters do not persist across restarts.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

from src.application.ports.governance.coercion_filter_port import MessageType
from src.application.ports.governance.ledger_port import (
    LedgerReadOptions,
    PersistedGovernanceEvent,
)
from src.domain.governance.events.event_envelope import GovernanceEvent
from src.domain.governance.filter import (
    FilteredContent,
    FilterResult,
    FilterVersion,
)
from src.domain.governance.task.task_activation_request import (
    FilteredContent as TaskFilteredContent,
)
from src.domain.governance.task.task_state import TaskState, TaskStatus
from src.domain.ports.time_authority import TimeAuthorityProtocol


class InMemoryTaskStatePort:
    """In-memory task state storage."""

    def __init__(self) -> None:
        self._tasks: dict[UUID, TaskState] = {}

    async def create_task(
        self,
        earl_id: str,
        cluster_id: str | None,
        ttl: timedelta,
    ) -> TaskState:
        task = TaskState.create(
            task_id=uuid4(),
            earl_id=earl_id,
            created_at=datetime.now(timezone.utc),
            ttl=ttl,
        )
        # TaskState.create() always sets cluster_id=None.
        # Override via direct construction to preserve cluster routing.
        if cluster_id is not None:
            task = TaskState(
                task_id=task.task_id,
                earl_id=task.earl_id,
                cluster_id=cluster_id,
                current_status=task.current_status,
                created_at=task.created_at,
                state_entered_at=task.state_entered_at,
                ttl=task.ttl,
            )
        self._tasks[task.task_id] = task
        return task

    async def get_task(self, task_id: UUID) -> TaskState:
        return self._tasks[task_id]

    async def save_task(self, task: TaskState) -> None:
        self._tasks[task.task_id] = task

    async def get_tasks_by_status(
        self,
        status: TaskStatus,
        limit: int = 100,
    ) -> list[TaskState]:
        results = [t for t in self._tasks.values() if t.current_status == status]
        return results[:limit]

    async def get_tasks_by_state_and_cluster(
        self,
        status: TaskStatus,
        cluster_id: str,
        limit: int = 100,
    ) -> list[TaskState]:
        results = [
            t
            for t in self._tasks.values()
            if t.current_status == status and t.cluster_id == cluster_id
        ]
        return results[:limit]

    @property
    def tasks(self) -> dict[UUID, TaskState]:
        """Read-only access to stored tasks for inspection."""
        return dict(self._tasks)


_FILTER_VERSION = FilterVersion(
    major=1, minor=0, patch=0, rules_hash="bridge_passthrough"
)


class PassthroughCoercionFilter:
    """Coercion filter that accepts all content.

    For bridge use only — production deployments must use the real
    CoercionFilterService with pattern libraries.
    """

    async def filter_content(
        self,
        content: str,
        message_type: MessageType,
    ) -> FilterResult:
        filtered = FilteredContent._create(
            content=content,
            original_content=content,
            filter_version=_FILTER_VERSION,
            filtered_at=datetime.now(timezone.utc),
        )
        return FilterResult.accepted(
            content=filtered,
            version=_FILTER_VERSION,
            timestamp=datetime.now(timezone.utc),
            transformations=(),
        )


class InMemoryParticipantMessagePort:
    """In-memory message port that logs sent messages."""

    def __init__(self) -> None:
        self._messages: list[dict[str, Any]] = []

    async def send_to_participant(
        self,
        participant_id: str,
        content: TaskFilteredContent,
        message_type: str,
        metadata: dict[str, Any],
    ) -> bool:
        self._messages.append(
            {
                "participant_id": participant_id,
                "message_type": message_type,
                "metadata": metadata,
                "sent_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        return True

    @property
    def messages(self) -> list[dict[str, Any]]:
        """Read-only access to sent messages for inspection."""
        return list(self._messages)


class InMemoryGovernanceLedger:
    """In-memory append-only ledger."""

    def __init__(self) -> None:
        self._events: list[PersistedGovernanceEvent] = []
        self._next_sequence = 1

    async def append_event(
        self,
        event: GovernanceEvent,
    ) -> PersistedGovernanceEvent:
        persisted = PersistedGovernanceEvent(
            event=event,
            sequence=self._next_sequence,
        )
        self._events.append(persisted)
        self._next_sequence += 1
        return persisted

    async def read_events(
        self,
        options: LedgerReadOptions | None = None,
    ) -> list[PersistedGovernanceEvent]:
        if options is None:
            return list(self._events)
        results = self._events
        if options.branch:
            results = [e for e in results if e.branch == options.branch]
        if options.event_type:
            results = [e for e in results if e.event_type == options.event_type]
        if options.start_sequence:
            results = [e for e in results if e.sequence >= options.start_sequence]
        if options.end_sequence:
            results = [e for e in results if e.sequence <= options.end_sequence]
        offset = options.offset or 0
        limit = options.limit or 100
        return results[offset : offset + limit]

    async def get_latest_sequence(self) -> int:
        return self._next_sequence - 1

    async def get_event_by_id(self, event_id: UUID) -> PersistedGovernanceEvent | None:
        for e in self._events:
            if e.event_id == event_id:
                return e
        return None

    @property
    def events(self) -> list[PersistedGovernanceEvent]:
        """Read-only access to ledger events for inspection."""
        return list(self._events)


class SimpleTimeAuthority(TimeAuthorityProtocol):
    """Simple time authority returning current UTC time."""

    def now(self) -> datetime:
        return datetime.now(timezone.utc)

    def utcnow(self) -> datetime:
        return datetime.now(timezone.utc)

    def monotonic(self) -> float:
        import time

        return time.monotonic()
