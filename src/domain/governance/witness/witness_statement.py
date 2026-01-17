"""Witness statement domain model.

Story: consent-gov-6-1: Knight Witness Domain Model

This module defines the immutable witness statement structure.
Statements are neutral observations that cannot be modified or deleted.

Constitutional Truths Honored:
- CT-12: Witnessing creates accountability -> All statements attributable
- NFR-CONST-07: Statements cannot be suppressed by any role

Suppression Prevention Design:
1. Immutability: frozen dataclass, no setters
2. No delete: WitnessPort interface has no delete method
3. No modify: WitnessPort interface has no modify method
4. Hash chain: Gap detection reveals missing statements

References:
    - FR33: Knight can observe all branch actions
    - FR34: Witness statements are observation only, no judgment
    - NFR-CONST-07: Statements cannot be suppressed by any role
    - AC3: Witness statements are observation only, no judgment
    - AC4: Statements cannot be suppressed by any role
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from src.domain.governance.witness.observation_type import ObservationType
from src.domain.governance.witness.observation_content import ObservationContent


@dataclass(frozen=True, eq=True)
class WitnessStatement:
    """Immutable witness statement from Knight.

    Represents a neutral observation of governance activity.
    Contains facts only - no judgment, no recommendation.

    Cannot be modified or deleted once created (NFR-CONST-07).
    The WitnessPort interface intentionally has no delete or modify methods.

    Attributes:
        statement_id: Unique identifier for this statement.
        observation_type: Category of observation (factual, not judgmental).
        content: Factual observation content (what, when, who, where).
        observed_at: When Knight observed (may differ from event time).
        hash_chain_position: Position in statement chain for gap detection.

    Intentionally excluded (no judgment fields):
        - severity: That's judgment
        - recommendation: That's advice
        - violation: That's conclusion
        - remedy: That's prescription
        - finding: That's determination
        - verdict: That's judgment

    Example:
        >>> statement = WitnessStatement(
        ...     statement_id=uuid4(),
        ...     observation_type=ObservationType.BRANCH_ACTION,
        ...     content=ObservationContent(
        ...         what="Task state changed from AUTHORIZED to ACTIVATED",
        ...         when=datetime.now(timezone.utc),
        ...         who=["actor-uuid-1"],
        ...         where="executive.task_coordination",
        ...         event_type="executive.task.activated",
        ...         event_id=uuid4(),
        ...     ),
        ...     observed_at=datetime.now(timezone.utc),
        ...     hash_chain_position=42,
        ... )
    """

    statement_id: UUID
    """Unique identifier for this witness statement."""

    observation_type: ObservationType
    """Category of observation.

    Note: This is for categorization/routing, NOT judgment.
    Even POTENTIAL_VIOLATION is just observation of patterns.
    """

    content: ObservationContent
    """Factual observation content.

    Contains only factual fields (what, when, who, where).
    No judgment fields exist in this structure.
    """

    observed_at: datetime
    """When Knight observed this event.

    May differ from content.when (the event's timestamp) due to
    observation lag, async processing, etc.
    """

    hash_chain_position: int
    """Position in the witness statement chain.

    Used for gap detection. If statements 41 and 43 exist but 42
    is missing, Knight can detect the gap and record it.
    """

    def __hash__(self) -> int:
        """Hash based on statement_id (unique identifier)."""
        return hash(self.statement_id)
