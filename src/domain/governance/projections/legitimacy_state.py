"""Legitimacy state projection domain model.

Story: consent-gov-1.5: Projection Infrastructure

This module defines the domain model for legitimacy state projection records.
Legitimacy states are derived from legitimacy.* events in the ledger.

Legitimacy Band Model:
    FULL ←→ PROVISIONAL ←→ SUSPENDED

    - Downward transitions (decay): Automatic on violations
    - Upward transitions (restoration): Explicit action required

References:
- [Source: _bmad-output/planning-artifacts/governance-architecture.md#Legitimacy State Projection]
- [Source: _bmad-output/planning-artifacts/governance-prd.md#Legitimacy Visibility]
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar


@dataclass(frozen=True)
class LegitimacyStateRecord:
    """Projection record for entity legitimacy bands.

    Derived from legitimacy.* events. Tracks the current legitimacy
    band of entities in the governance system.

    Attributes:
        entity_id: ID of the entity (archon, officer, system component).
        entity_type: Type of entity (archon, officer, system).
        current_band: Current legitimacy band (see VALID_BANDS).
        band_entered_at: When the current band was entered.
        violation_count: Total violation count affecting legitimacy.
        last_violation_at: When the last violation occurred (if any).
        last_restoration_at: When legitimacy was last restored (if any).
        last_event_sequence: Ledger sequence of the last updating event.
        updated_at: When this projection record was last updated.
    """

    # Valid legitimacy bands in descending order
    VALID_BANDS: ClassVar[frozenset[str]] = frozenset(
        {
            "full",
            "provisional",
            "suspended",
        }
    )

    # Band hierarchy (higher number = better legitimacy)
    BAND_LEVELS: ClassVar[dict[str, int]] = {
        "suspended": 0,
        "provisional": 1,
        "full": 2,
    }

    # Automatic downward transitions (decay) on violations
    DECAY_TRANSITIONS: ClassVar[dict[str, str]] = {
        "full": "provisional",
        "provisional": "suspended",
        "suspended": "suspended",  # Already at bottom
    }

    # Explicit upward transitions (restoration)
    RESTORATION_TRANSITIONS: ClassVar[dict[str, str]] = {
        "suspended": "provisional",
        "provisional": "full",
        "full": "full",  # Already at top
    }

    entity_id: str
    entity_type: str
    current_band: str
    band_entered_at: datetime
    violation_count: int
    last_violation_at: datetime | None
    last_restoration_at: datetime | None
    last_event_sequence: int
    updated_at: datetime

    def __post_init__(self) -> None:
        """Validate legitimacy state record fields."""
        if self.current_band not in self.VALID_BANDS:
            raise ValueError(
                f"Invalid legitimacy band '{self.current_band}'. "
                f"Valid bands: {sorted(self.VALID_BANDS)}"
            )
        if self.violation_count < 0:
            raise ValueError(
                f"violation_count must be non-negative, got {self.violation_count}"
            )
        if self.last_event_sequence < 0:
            raise ValueError(
                f"last_event_sequence must be non-negative, got {self.last_event_sequence}"
            )

    @property
    def band_level(self) -> int:
        """Get numeric level of current band.

        Returns:
            Band level (0=suspended, 1=provisional, 2=full).
        """
        return self.BAND_LEVELS[self.current_band]

    def get_decay_band(self) -> str:
        """Get the band after decay (violation).

        Returns:
            The band to transition to on decay.
        """
        return self.DECAY_TRANSITIONS[self.current_band]

    def get_restoration_band(self) -> str:
        """Get the band after restoration.

        Returns:
            The band to transition to on restoration.
        """
        return self.RESTORATION_TRANSITIONS[self.current_band]

    def can_decay(self) -> bool:
        """Check if legitimacy can decay further.

        Returns:
            True if not already at lowest band.
        """
        return self.current_band != "suspended"

    def can_restore(self) -> bool:
        """Check if legitimacy can be restored.

        Returns:
            True if not already at highest band.
        """
        return self.current_band != "full"

    def is_suspended(self) -> bool:
        """Check if entity is suspended.

        Returns:
            True if in suspended band.
        """
        return self.current_band == "suspended"

    def has_full_legitimacy(self) -> bool:
        """Check if entity has full legitimacy.

        Returns:
            True if in full band.
        """
        return self.current_band == "full"
