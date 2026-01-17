"""Task event types and event generation for consent-based governance.

Story: consent-gov-2.1: Task State Machine Domain Model

This module defines event types for task state transitions and provides
event generation utilities. All task transitions emit events following
the executive.task.{verb} pattern.

Event Type Pattern: {branch}.{noun}.{verb}
- Branch: executive (tasks belong to executive branch)
- Noun: task
- Verb: Past-tense action describing the transition

Per AC5: All transitions emit events to ledger.
Per governance-architecture.md: Event naming convention is locked.

References:
- [Source: governance-architecture.md#Event Naming Convention]
- [Source: consent-gov-1-1-event-envelope-domain-model.md]
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from src.domain.governance.events.event_envelope import (
    EventMetadata,
    GovernanceEvent,
)
from src.domain.governance.events.schema_versions import CURRENT_SCHEMA_VERSION
from src.domain.governance.task.task_state import TaskState, TaskStatus


# Event type registry for task domain
# Maps TaskStatus → event type string following executive.task.{verb} pattern
TASK_EVENT_TYPES: dict[TaskStatus, str] = {
    TaskStatus.AUTHORIZED: "executive.task.authorized",
    TaskStatus.ACTIVATED: "executive.task.activated",
    TaskStatus.ROUTED: "executive.task.routed",
    TaskStatus.ACCEPTED: "executive.task.accepted",
    TaskStatus.IN_PROGRESS: "executive.task.started",
    TaskStatus.REPORTED: "executive.task.reported",
    TaskStatus.AGGREGATED: "executive.task.aggregated",
    TaskStatus.COMPLETED: "executive.task.completed",
    TaskStatus.DECLINED: "executive.task.declined",
    TaskStatus.QUARANTINED: "executive.task.quarantined",
    TaskStatus.NULLIFIED: "executive.task.nullified",
}


def get_event_type_for_status(status: TaskStatus) -> str:
    """Get the event type string for a task status.

    Args:
        status: The task status to get event type for.

    Returns:
        Event type string in executive.task.{verb} format.

    Raises:
        KeyError: If status is not in TASK_EVENT_TYPES.
    """
    return TASK_EVENT_TYPES[status]


def create_transition_event(
    *,
    task_state: TaskState,
    new_status: TaskStatus,
    transition_time: datetime,
    actor_id: str,
    trace_id: str,
    reason: str = "",
    additional_payload: dict[str, Any] | None = None,
) -> GovernanceEvent:
    """Create a governance event for a task state transition.

    Per AC5: All transitions emit events to ledger via executive.task.{verb} pattern.
    Per AC7: This function generates the event, but does NOT perform the transition.

    Args:
        task_state: The current task state (before transition).
        new_status: The target status for the transition.
        transition_time: When the transition occurs.
        actor_id: ID of the actor performing the transition.
        trace_id: Correlation ID for request tracing.
        reason: Optional reason for the transition.
        additional_payload: Optional additional data for the event payload.

    Returns:
        GovernanceEvent ready to be persisted to the ledger.
    """
    event_type = get_event_type_for_status(new_status)

    # Build event payload with transition metadata
    payload: dict[str, Any] = {
        "task_id": str(task_state.task_id),
        "earl_id": task_state.earl_id,
        "from_status": task_state.current_status.value,
        "to_status": new_status.value,
        "transition_time": transition_time.isoformat(),
    }

    # Add optional fields if present
    if task_state.cluster_id:
        payload["cluster_id"] = task_state.cluster_id

    if reason:
        payload["reason"] = reason

    # Merge additional payload if provided
    if additional_payload:
        payload.update(additional_payload)

    # Create event using factory method
    return GovernanceEvent.create(
        event_id=uuid4(),
        event_type=event_type,
        timestamp=transition_time,
        actor_id=actor_id,
        trace_id=trace_id,
        payload=payload,
        schema_version=CURRENT_SCHEMA_VERSION,
    )


def create_task_created_event(
    *,
    task_state: TaskState,
    created_time: datetime,
    actor_id: str,
    trace_id: str,
    additional_payload: dict[str, Any] | None = None,
) -> GovernanceEvent:
    """Create a governance event for task creation (authorized).

    This is a convenience function for the initial task creation event.

    Args:
        task_state: The newly created task state.
        created_time: When the task was created.
        actor_id: ID of the actor creating the task.
        trace_id: Correlation ID for request tracing.
        additional_payload: Optional additional data for the event payload.

    Returns:
        GovernanceEvent for task creation.
    """
    payload: dict[str, Any] = {
        "task_id": str(task_state.task_id),
        "earl_id": task_state.earl_id,
        "status": TaskStatus.AUTHORIZED.value,
        "created_at": created_time.isoformat(),
        "ttl_seconds": int(task_state.ttl.total_seconds()),
        "inactivity_timeout_seconds": int(task_state.inactivity_timeout.total_seconds()),
        "reporting_timeout_seconds": int(task_state.reporting_timeout.total_seconds()),
    }

    if additional_payload:
        payload.update(additional_payload)

    return GovernanceEvent.create(
        event_id=uuid4(),
        event_type=TASK_EVENT_TYPES[TaskStatus.AUTHORIZED],
        timestamp=created_time,
        actor_id=actor_id,
        trace_id=trace_id,
        payload=payload,
        schema_version=CURRENT_SCHEMA_VERSION,
    )


def create_halt_transition_event(
    *,
    task_state: TaskState,
    halt_reason: str,
    halt_time: datetime,
    actor_id: str,
    trace_id: str,
    halt_context: dict[str, Any] | None = None,
) -> GovernanceEvent | None:
    """Create a governance event for halt-triggered transition.

    Per FR22-FR27: Halt transitions depend on consent state.
    - Pre-consent → nullified (executive.task.nullified)
    - Post-consent → quarantined (executive.task.quarantined)
    - Terminal → None (no transition needed)

    Args:
        task_state: The current task state.
        halt_reason: Reason for the halt.
        halt_time: When the halt occurred.
        actor_id: ID of the actor (usually system) triggering halt.
        trace_id: Correlation ID for request tracing.
        halt_context: Optional context about the halt.

    Returns:
        GovernanceEvent for halt transition, or None if already terminal.
    """
    from src.domain.governance.task.task_state_rules import TaskTransitionRules

    target_status = TaskTransitionRules.get_halt_target(task_state.current_status)
    if target_status is None:
        return None

    payload: dict[str, Any] = {
        "task_id": str(task_state.task_id),
        "earl_id": task_state.earl_id,
        "from_status": task_state.current_status.value,
        "to_status": target_status.value,
        "transition_time": halt_time.isoformat(),
        "reason": halt_reason,
        "halt_triggered": True,
    }

    if task_state.cluster_id:
        payload["cluster_id"] = task_state.cluster_id

    if halt_context:
        payload["halt_context"] = halt_context

    return GovernanceEvent.create(
        event_id=uuid4(),
        event_type=TASK_EVENT_TYPES[target_status],
        timestamp=halt_time,
        actor_id=actor_id,
        trace_id=trace_id,
        payload=payload,
        schema_version=CURRENT_SCHEMA_VERSION,
    )


def create_ttl_expiry_event(
    *,
    task_state: TaskState,
    expiry_time: datetime,
    actor_id: str,
    trace_id: str,
) -> GovernanceEvent:
    """Create a governance event for TTL expiry (auto-decline).

    Per NFR-CONSENT-01: TTL expiration = declined.
    This event records automatic decline due to timeout.

    Args:
        task_state: The current task state (should be pre-consent).
        expiry_time: When the TTL expired.
        actor_id: ID of the actor (usually system timer).
        trace_id: Correlation ID for request tracing.

    Returns:
        GovernanceEvent for TTL expiry decline.
    """
    payload: dict[str, Any] = {
        "task_id": str(task_state.task_id),
        "earl_id": task_state.earl_id,
        "from_status": task_state.current_status.value,
        "to_status": TaskStatus.DECLINED.value,
        "transition_time": expiry_time.isoformat(),
        "reason": "TTL expired without acceptance",
        "ttl_expired": True,
        "ttl_seconds": int(task_state.ttl.total_seconds()),
    }

    if task_state.cluster_id:
        payload["cluster_id"] = task_state.cluster_id

    return GovernanceEvent.create(
        event_id=uuid4(),
        event_type=TASK_EVENT_TYPES[TaskStatus.DECLINED],
        timestamp=expiry_time,
        actor_id=actor_id,
        trace_id=trace_id,
        payload=payload,
        schema_version=CURRENT_SCHEMA_VERSION,
    )
