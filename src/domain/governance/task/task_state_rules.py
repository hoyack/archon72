"""Task state transition rules for consent-based governance.

Story: consent-gov-2.1: Task State Machine Domain Model

This module defines the valid state transitions for the task state machine.
Transition rules are implemented as frozen data structures for O(1) lookup
and immutability.

State Transition Diagram:
```
                    authorized
                        │
                        ▼
                    activated
                        │
                        ▼
                      routed ──────────────► declined (TTL)
                        │                       ▲
                        ▼                       │
                    accepted ─────────────────────┘ (explicit decline)
                        │
                        ▼
                   in_progress ──────────────► quarantined (timeout/issue)
                        │
                        ▼
                     reported
                        │
                        ▼
                    aggregated
                        │
                        ▼
                    completed

HALT TRANSITIONS (any pre-consent state → nullified)
HALT TRANSITIONS (any post-consent state → quarantined)
```

Consent Gates:
- routed → accepted: REQUIRES explicit Cluster acceptance
- routed → declined: explicit decline OR TTL expiry

References:
- [Source: governance-architecture.md#Task State Projection]
"""

from __future__ import annotations

from typing import ClassVar

from src.domain.governance.task.task_state import TaskStatus


class TaskTransitionRules:
    """Defines valid state transitions for the task state machine.

    Per AC7: Transition rules defined in separate TaskTransitionRules class.
    Per AC4: O(1) lookup for NFR-PERF-05 (≤10ms resolution).

    This class provides static methods for transition validation using
    pre-computed lookup tables. No instantiation required.

    The transition rules encode:
    1. Normal lifecycle flow (authorized → ... → completed)
    2. Consent gates (routed → accepted requires explicit acceptance)
    3. Decline paths (explicit decline or TTL expiry)
    4. Halt transitions (pre-consent → nullified, post-consent → quarantined)

    Attributes:
        VALID_TRANSITIONS: Mapping of current state → allowed next states.
        CONSENT_GATE_STATES: States that require explicit consent to leave.
        PRE_CONSENT_HALT_TARGET: State for halt during pre-consent.
        POST_CONSENT_HALT_TARGET: State for halt during post-consent.
    """

    # Pre-computed transition lookup table (O(1) validation)
    # Per AC4: NFR-PERF-05 requires ≤10ms resolution
    VALID_TRANSITIONS: ClassVar[dict[TaskStatus, frozenset[TaskStatus]]] = {
        TaskStatus.AUTHORIZED: frozenset({
            TaskStatus.ACTIVATED,
            TaskStatus.NULLIFIED,  # Halt (pre-consent) per FR22-FR27
        }),
        TaskStatus.ACTIVATED: frozenset({
            TaskStatus.ROUTED,
            TaskStatus.NULLIFIED,  # Halt (pre-consent)
        }),
        TaskStatus.ROUTED: frozenset({
            TaskStatus.ACCEPTED,    # Explicit acceptance
            TaskStatus.DECLINED,    # Explicit decline OR TTL expiry
            TaskStatus.NULLIFIED,   # Halt (pre-consent)
        }),
        TaskStatus.ACCEPTED: frozenset({
            TaskStatus.IN_PROGRESS,
            TaskStatus.DECLINED,    # Changed mind before starting
            TaskStatus.QUARANTINED, # Halt (post-consent)
        }),
        TaskStatus.IN_PROGRESS: frozenset({
            TaskStatus.REPORTED,
            TaskStatus.QUARANTINED, # Timeout or halt
        }),
        TaskStatus.REPORTED: frozenset({
            TaskStatus.AGGREGATED,
            TaskStatus.COMPLETED,   # Direct completion for single-cluster
        }),
        TaskStatus.AGGREGATED: frozenset({TaskStatus.COMPLETED}),
        # Terminal states - no transitions out
        TaskStatus.COMPLETED: frozenset(),
        TaskStatus.DECLINED: frozenset(),
        TaskStatus.QUARANTINED: frozenset(),
        TaskStatus.NULLIFIED: frozenset(),
    }

    # States that represent consent gates (require explicit action to pass)
    CONSENT_GATE_STATES: ClassVar[frozenset[TaskStatus]] = frozenset({
        TaskStatus.ROUTED,  # Must accept or decline explicitly
    })

    # Halt target for pre-consent states
    PRE_CONSENT_HALT_TARGET: ClassVar[TaskStatus] = TaskStatus.NULLIFIED

    # Halt target for post-consent states
    POST_CONSENT_HALT_TARGET: ClassVar[TaskStatus] = TaskStatus.QUARANTINED

    @classmethod
    def is_valid_transition(
        cls,
        current: TaskStatus,
        target: TaskStatus,
    ) -> bool:
        """Check if transition from current to target is valid.

        O(1) lookup for NFR-PERF-05 compliance.

        Args:
            current: Current task status.
            target: Target task status.

        Returns:
            True if transition is allowed, False otherwise.
        """
        allowed = cls.VALID_TRANSITIONS.get(current, frozenset())
        return target in allowed

    @classmethod
    def get_allowed_transitions(
        cls,
        current: TaskStatus,
    ) -> frozenset[TaskStatus]:
        """Get the set of allowed transitions from current state.

        Args:
            current: Current task status.

        Returns:
            Frozenset of allowed target states (empty for terminal states).
        """
        return cls.VALID_TRANSITIONS.get(current, frozenset())

    @classmethod
    def is_consent_gate(cls, status: TaskStatus) -> bool:
        """Check if status is a consent gate state.

        Consent gates require explicit acceptance or decline.

        Args:
            status: Task status to check.

        Returns:
            True if status is a consent gate.
        """
        return status in cls.CONSENT_GATE_STATES

    @classmethod
    def get_halt_target(cls, current: TaskStatus) -> TaskStatus | None:
        """Get the appropriate halt target state for current status.

        Per FR22-FR27: Halt transitions depend on consent state.
        - Pre-consent → nullified (task can be cancelled cleanly)
        - Post-consent → quarantined (work was in progress)
        - Terminal → None (already finished)

        Args:
            current: Current task status.

        Returns:
            Target status for halt, or None if already terminal.
        """
        if current.is_terminal:
            return None
        if current.is_pre_consent:
            return cls.PRE_CONSENT_HALT_TARGET
        if current.is_post_consent:
            return cls.POST_CONSENT_HALT_TARGET
        return None

    @classmethod
    def can_decline(cls, current: TaskStatus) -> bool:
        """Check if task can transition to declined from current state.

        Decline is allowed from:
        - routed (explicit decline or TTL expiry)
        - accepted (changed mind before starting work)

        Args:
            current: Current task status.

        Returns:
            True if decline is allowed.
        """
        return TaskStatus.DECLINED in cls.get_allowed_transitions(current)

    @classmethod
    def is_normal_flow_transition(
        cls,
        current: TaskStatus,
        target: TaskStatus,
    ) -> bool:
        """Check if transition is part of normal happy-path flow.

        Normal flow: authorized → activated → routed → accepted →
                     in_progress → reported → aggregated → completed

        This excludes:
        - Decline transitions
        - Halt transitions (quarantined, nullified)

        Args:
            current: Current task status.
            target: Target task status.

        Returns:
            True if transition is part of normal flow.
        """
        normal_flow = {
            TaskStatus.AUTHORIZED: TaskStatus.ACTIVATED,
            TaskStatus.ACTIVATED: TaskStatus.ROUTED,
            TaskStatus.ROUTED: TaskStatus.ACCEPTED,
            TaskStatus.ACCEPTED: TaskStatus.IN_PROGRESS,
            TaskStatus.IN_PROGRESS: TaskStatus.REPORTED,
            TaskStatus.REPORTED: TaskStatus.AGGREGATED,
            TaskStatus.AGGREGATED: TaskStatus.COMPLETED,
        }
        # Also allow direct completion from REPORTED (single-cluster)
        if current == TaskStatus.REPORTED and target == TaskStatus.COMPLETED:
            return True
        return normal_flow.get(current) == target
