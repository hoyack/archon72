"""Task state projection domain model.

Story: consent-gov-1.5: Projection Infrastructure

This module defines the domain model for task state projection records.
Task states are derived from executive.task.* events in the ledger.

Task State Machine:
    pending → authorized → activated → accepted → completed
                                    ↘ declined
                         ↘ expired

References:
- [Source: _bmad-output/planning-artifacts/governance-architecture.md#Task State Projection]
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar
from uuid import UUID


@dataclass(frozen=True)
class TaskStateRecord:
    """Projection record for task lifecycle state.

    Derived from executive.task.* events. Tracks the current state of
    governance tasks as they move through their lifecycle.

    Attributes:
        task_id: Unique identifier for the task.
        current_state: Current task state (see VALID_STATES).
        earl_id: ID of the Earl assigned to execute the task.
        cluster_id: Optional cluster grouping for related tasks.
        task_type: Optional type classification of the task.
        created_at: When the task was first created.
        state_entered_at: When the current state was entered.
        last_event_sequence: Ledger sequence of the last updating event.
        last_event_hash: Hash of the last updating event.
        updated_at: When this projection record was last updated.
    """

    # Valid task states in lifecycle order
    VALID_STATES: ClassVar[frozenset[str]] = frozenset(
        {
            "pending",
            "authorized",
            "activated",
            "accepted",
            "completed",
            "declined",
            "expired",
        }
    )

    # State transitions that are allowed
    ALLOWED_TRANSITIONS: ClassVar[dict[str, frozenset[str]]] = {
        "pending": frozenset({"authorized"}),
        "authorized": frozenset({"activated", "expired"}),
        "activated": frozenset({"accepted", "declined", "expired"}),
        "accepted": frozenset({"completed"}),
        "completed": frozenset(),  # Terminal state
        "declined": frozenset(),  # Terminal state
        "expired": frozenset(),  # Terminal state
    }

    task_id: UUID
    current_state: str
    earl_id: str
    cluster_id: str | None
    task_type: str | None
    created_at: datetime
    state_entered_at: datetime
    last_event_sequence: int
    last_event_hash: str
    updated_at: datetime

    def __post_init__(self) -> None:
        """Validate task state record fields."""
        if self.current_state not in self.VALID_STATES:
            raise ValueError(
                f"Invalid task state '{self.current_state}'. "
                f"Valid states: {sorted(self.VALID_STATES)}"
            )
        if self.last_event_sequence < 0:
            raise ValueError(
                f"last_event_sequence must be non-negative, got {self.last_event_sequence}"
            )

    def can_transition_to(self, new_state: str) -> bool:
        """Check if transition to new_state is allowed.

        Args:
            new_state: The state to transition to.

        Returns:
            True if the transition is allowed, False otherwise.
        """
        allowed = self.ALLOWED_TRANSITIONS.get(self.current_state, frozenset())
        return new_state in allowed

    def is_terminal(self) -> bool:
        """Check if task is in a terminal state.

        Returns:
            True if task cannot transition further.
        """
        return len(self.ALLOWED_TRANSITIONS.get(self.current_state, frozenset())) == 0

    def is_active(self) -> bool:
        """Check if task is in an active (non-terminal) state.

        Returns:
            True if task can still transition.
        """
        return not self.is_terminal()
