"""Task state machine domain module for consent-based governance.

Story: consent-gov-2.1: Task State Machine Domain Model
Story: consent-gov-2.2: Task Activation Request

This module implements the task state machine with defined transitions
for consent-based coordination and dignity-preserving workflows.

Constitutional Truths Honored:
- CT-11: Silent failure destroys legitimacy → Invalid transitions raise errors
- CT-12: Witnessing creates accountability → All transitions emit events
- Golden Rule: No silent assignment → Explicit accept/decline transitions

Task States (11 total):
- Pre-consent: authorized, activated, routed
- Post-consent: accepted, in_progress, reported, aggregated
- Terminal: completed, declined, quarantined, nullified

References:
- [Source: governance-architecture.md#Task State Projection]
- [Source: government-epics.md#GOV-2-1]
"""

from src.domain.governance.task.problem_report import ProblemCategory, ProblemReport
from src.domain.governance.task.task_activation_request import (
    FilteredContent,
    FilterOutcome,
    RoutingStatus,
    TaskActivationRequest,
    TaskActivationResult,
    TaskStateView,
)
from src.domain.governance.task.task_events import (
    TASK_EVENT_TYPES,
    create_transition_event,
)
from src.domain.governance.task.task_result import TaskResult
from src.domain.governance.task.task_state import (
    IllegalStateTransitionError,
    TaskState,
    TaskStatus,
)
from src.domain.governance.task.task_state_rules import TaskTransitionRules

__all__ = [
    # Task state machine (Story 2-1)
    "TaskStatus",
    "TaskState",
    "TaskTransitionRules",
    "IllegalStateTransitionError",
    "TASK_EVENT_TYPES",
    "create_transition_event",
    # Task activation (Story 2-2)
    "TaskActivationRequest",
    "TaskActivationResult",
    "TaskStateView",
    "FilteredContent",
    "FilterOutcome",
    "RoutingStatus",
    # Task result (Story 2-4)
    "TaskResult",
    "ProblemCategory",
    "ProblemReport",
]
