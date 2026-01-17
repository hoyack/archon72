"""Panel finding domain model.

Story: consent-gov-6-4: Prince Panel Domain Model

Defines the PanelFinding value object representing a formal finding
from a Prince Panel.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Optional
from uuid import UUID

from src.domain.governance.panel.determination import Determination
from src.domain.governance.panel.remedy_type import RemedyType
from src.domain.governance.panel.dissent import Dissent


@dataclass(frozen=True, eq=True)
class PanelFinding:
    """Formal finding from a Prince Panel.

    A finding represents the panel's determination after reviewing a
    witness statement. It includes the determination, any remedy (if
    violation found), the majority rationale, and any dissent (FR39).

    Attributes:
        finding_id: Unique identifier for this finding
        panel_id: UUID of the panel that issued this finding
        statement_id: UUID of the witness statement reviewed
        determination: Panel's determination (violation/no_violation/insufficient)
        remedy: Remedy type if violation found, None otherwise
        majority_rationale: Explanation of the majority decision
        dissent: Minority dissent if any members disagreed
        issued_at: When the finding was issued
        voting_record: Record of how each member voted

    Example:
        >>> finding = PanelFinding(
        ...     finding_id=uuid4(),
        ...     panel_id=uuid4(),
        ...     statement_id=uuid4(),
        ...     determination=Determination.VIOLATION_FOUND,
        ...     remedy=RemedyType.CORRECTION,
        ...     majority_rationale="Evidence clearly shows violation.",
        ...     dissent=Dissent(
        ...         dissenting_member_ids=[uuid4()],
        ...         rationale="I disagree because...",
        ...     ),
        ...     issued_at=datetime.now(timezone.utc),
        ...     voting_record={uuid1: "violation", uuid2: "violation", uuid3: "no_violation"},
        ... )
    """

    finding_id: UUID
    """Unique identifier for this finding."""

    panel_id: UUID
    """UUID of the panel that issued this finding."""

    statement_id: UUID
    """UUID of the witness statement being reviewed."""

    determination: Determination
    """Panel's determination."""

    remedy: Optional[RemedyType]
    """Remedy type if violation found, None otherwise.

    Only set when determination is VIOLATION_FOUND.
    """

    majority_rationale: str
    """Explanation of the majority decision."""

    dissent: Optional[Dissent]
    """Minority dissent if any members disagreed.

    None if the decision was unanimous.
    Preserved per FR39 - cannot be suppressed.
    """

    issued_at: datetime
    """When the finding was issued."""

    voting_record: Dict[UUID, str]
    """Record of how each member voted.

    Maps member_id → vote string (e.g., "violation", "no_violation").
    Provides audit trail for the decision.
    """

    def __hash__(self) -> int:
        """Hash based on finding_id (unique identifier)."""
        return hash(self.finding_id)
