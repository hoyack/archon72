"""Dissent domain model.

Story: consent-gov-6-4: Prince Panel Domain Model

Defines the Dissent value object for minority opinions in panel findings.
Dissent is preserved per FR39 - it cannot be overruled, suppressed, or hidden.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, eq=True)
class Dissent:
    """Minority dissent in a panel finding.

    Represents the minority opinion when panel members disagree with
    the majority determination. Dissent is preserved per FR39.

    Dissent is NOT:
      - Overruled
      - Suppressed
      - Hidden

    Dissent IS:
      - Recorded alongside finding
      - Visible to observers
      - Part of official record
      - Valuable for appeals/review

    Attributes:
        dissenting_member_ids: UUIDs of members who dissented
        rationale: Explanation of the dissenting view

    Example:
        >>> dissent = Dissent(
        ...     dissenting_member_ids=[uuid4()],
        ...     rationale="I disagree because the evidence was inconclusive.",
        ... )
    """

    dissenting_member_ids: list[UUID]
    """UUIDs of members who dissented from the majority."""

    rationale: str
    """Explanation of the dissenting view."""

    def __hash__(self) -> int:
        """Hash based on dissenting members and rationale."""
        return hash((tuple(self.dissenting_member_ids), self.rationale))
