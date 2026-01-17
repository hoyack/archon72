"""Petition index projection domain model.

Story: consent-gov-1.5: Projection Infrastructure

This module defines the domain model for petition index projection records.
Petition records are derived from petition.* events in the ledger.

Petition Lifecycle:
    filed → acknowledged → under_review → resolved

References:
- [Source: _bmad-output/planning-artifacts/governance-architecture.md#Petition Index Projection]
- [Source: _bmad-output/planning-artifacts/governance-prd.md#Dignified Exit]
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar
from uuid import UUID


@dataclass(frozen=True)
class PetitionIndexRecord:
    """Projection record for petition tracking.

    Derived from petition.* events. Tracks petitions for exit,
    dignity restoration, and other formal requests.

    Attributes:
        petition_id: Unique identifier for the petition.
        petition_type: Type of petition (see VALID_TYPES).
        subject_entity_id: ID of the entity the petition concerns.
        petitioner_id: ID of the entity filing the petition.
        current_status: Current status (see VALID_STATUSES).
        filed_at: When the petition was filed.
        acknowledged_at: When the petition was acknowledged (if ack'd).
        resolved_at: When the petition was resolved (if resolved).
        resolution_outcome: Outcome of resolution (if resolved).
        last_event_sequence: Ledger sequence of the last updating event.
        updated_at: When this projection record was last updated.
    """

    # Valid petition types
    VALID_TYPES: ClassVar[frozenset[str]] = frozenset({
        "exit",
        "dignity_restoration",
        "review",
        "reconsideration",
    })

    # Valid petition statuses in lifecycle order
    VALID_STATUSES: ClassVar[frozenset[str]] = frozenset({
        "filed",
        "acknowledged",
        "under_review",
        "resolved",
    })

    # Valid resolution outcomes
    VALID_OUTCOMES: ClassVar[frozenset[str]] = frozenset({
        "granted",
        "denied",
        "withdrawn",
    })

    # Status transitions that are allowed
    ALLOWED_TRANSITIONS: ClassVar[dict[str, frozenset[str]]] = {
        "filed": frozenset({"acknowledged", "resolved"}),  # Can be immediately resolved (withdrawn)
        "acknowledged": frozenset({"under_review", "resolved"}),
        "under_review": frozenset({"resolved"}),
        "resolved": frozenset(),  # Terminal state
    }

    petition_id: UUID
    petition_type: str
    subject_entity_id: str
    petitioner_id: str
    current_status: str
    filed_at: datetime
    acknowledged_at: datetime | None
    resolved_at: datetime | None
    resolution_outcome: str | None
    last_event_sequence: int
    updated_at: datetime

    def __post_init__(self) -> None:
        """Validate petition index record fields."""
        if self.petition_type not in self.VALID_TYPES:
            raise ValueError(
                f"Invalid petition type '{self.petition_type}'. "
                f"Valid types: {sorted(self.VALID_TYPES)}"
            )
        if self.current_status not in self.VALID_STATUSES:
            raise ValueError(
                f"Invalid petition status '{self.current_status}'. "
                f"Valid statuses: {sorted(self.VALID_STATUSES)}"
            )
        if self.resolution_outcome is not None and self.resolution_outcome not in self.VALID_OUTCOMES:
            raise ValueError(
                f"Invalid resolution outcome '{self.resolution_outcome}'. "
                f"Valid outcomes: {sorted(self.VALID_OUTCOMES)}"
            )
        if self.last_event_sequence < 0:
            raise ValueError(
                f"last_event_sequence must be non-negative, got {self.last_event_sequence}"
            )

    def can_transition_to(self, new_status: str) -> bool:
        """Check if transition to new_status is allowed.

        Args:
            new_status: The status to transition to.

        Returns:
            True if the transition is allowed, False otherwise.
        """
        allowed = self.ALLOWED_TRANSITIONS.get(self.current_status, frozenset())
        return new_status in allowed

    def is_pending(self) -> bool:
        """Check if petition is still pending (not resolved).

        Returns:
            True if petition has not been resolved.
        """
        return self.current_status != "resolved"

    def is_resolved(self) -> bool:
        """Check if petition has been resolved.

        Returns:
            True if petition is resolved.
        """
        return self.current_status == "resolved"

    def was_granted(self) -> bool:
        """Check if petition was granted.

        Returns:
            True if resolved with 'granted' outcome.
        """
        return self.resolution_outcome == "granted"

    def is_exit_petition(self) -> bool:
        """Check if this is an exit petition.

        Returns:
            True if petition type is 'exit'.
        """
        return self.petition_type == "exit"
