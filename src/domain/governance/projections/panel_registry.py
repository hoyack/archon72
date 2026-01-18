"""Panel registry projection domain model.

Story: consent-gov-1.5: Projection Infrastructure

This module defines the domain model for panel registry projection records.
Panel records are derived from judicial.panel.* events in the ledger.

Panel Lifecycle:
    pending → convened → deliberating → finding_issued → dissolved

References:
- [Source: _bmad-output/planning-artifacts/governance-architecture.md#Panel Registry Projection]
- [Source: _bmad-output/planning-artifacts/governance-prd.md#Prince Panel Adjudication]
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar
from uuid import UUID


@dataclass(frozen=True)
class PanelRegistryRecord:
    """Projection record for Prince panel tracking.

    Derived from judicial.panel.* events. Tracks Prince panels convened
    to adjudicate violations in the governance system.

    Attributes:
        panel_id: Unique identifier for the panel.
        panel_status: Current panel status (see VALID_STATUSES).
        violation_id: ID of the violation being adjudicated.
        prince_ids: Tuple of Prince IDs serving on the panel.
        petitioner_id: ID of the entity that petitioned for the panel.
        convened_at: When the panel was convened (if convened).
        finding_issued_at: When the finding was issued (if issued).
        finding_outcome: Outcome of the finding (if issued).
        last_event_sequence: Ledger sequence of the last updating event.
        updated_at: When this projection record was last updated.
    """

    # Valid panel statuses in lifecycle order
    VALID_STATUSES: ClassVar[frozenset[str]] = frozenset(
        {
            "pending",
            "convened",
            "deliberating",
            "finding_issued",
            "dissolved",
        }
    )

    # Valid finding outcomes
    VALID_OUTCOMES: ClassVar[frozenset[str]] = frozenset(
        {
            "upheld",
            "overturned",
            "remanded",
        }
    )

    # Status transitions that are allowed
    ALLOWED_TRANSITIONS: ClassVar[dict[str, frozenset[str]]] = {
        "pending": frozenset({"convened", "dissolved"}),
        "convened": frozenset({"deliberating", "dissolved"}),
        "deliberating": frozenset({"finding_issued", "dissolved"}),
        "finding_issued": frozenset({"dissolved"}),
        "dissolved": frozenset(),  # Terminal state
    }

    panel_id: UUID
    panel_status: str
    violation_id: UUID
    prince_ids: tuple[str, ...]
    petitioner_id: str | None
    convened_at: datetime | None
    finding_issued_at: datetime | None
    finding_outcome: str | None
    last_event_sequence: int
    updated_at: datetime

    def __post_init__(self) -> None:
        """Validate panel registry record fields."""
        if self.panel_status not in self.VALID_STATUSES:
            raise ValueError(
                f"Invalid panel status '{self.panel_status}'. "
                f"Valid statuses: {sorted(self.VALID_STATUSES)}"
            )
        if (
            self.finding_outcome is not None
            and self.finding_outcome not in self.VALID_OUTCOMES
        ):
            raise ValueError(
                f"Invalid finding outcome '{self.finding_outcome}'. "
                f"Valid outcomes: {sorted(self.VALID_OUTCOMES)}"
            )
        if len(self.prince_ids) == 0:
            raise ValueError("prince_ids must not be empty")
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
        allowed = self.ALLOWED_TRANSITIONS.get(self.panel_status, frozenset())
        return new_status in allowed

    def is_active(self) -> bool:
        """Check if panel is still active.

        Returns:
            True if panel has not been dissolved.
        """
        return self.panel_status != "dissolved"

    def has_finding(self) -> bool:
        """Check if panel has issued a finding.

        Returns:
            True if finding has been issued.
        """
        return self.finding_outcome is not None

    def is_deliberating(self) -> bool:
        """Check if panel is currently deliberating.

        Returns:
            True if panel is in deliberating status.
        """
        return self.panel_status == "deliberating"

    @property
    def panel_size(self) -> int:
        """Get number of Princes on the panel.

        Returns:
            Number of Prince IDs.
        """
        return len(self.prince_ids)
