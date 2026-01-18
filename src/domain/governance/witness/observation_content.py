"""Observation content structure for Knight witness statements.

Story: consent-gov-6-1: Knight Witness Domain Model

This module defines the factual content structure for observations.
The structure enforces observation-only semantics by design:
- Includes: what, when, who, where (factual)
- Excludes: why, should, severity (judgment)

Constitutional Truths Honored:
- CT-12: Witnessing creates accountability -> All fields are factual
- NFR-CONST-07: Content structure prevents judgment language

References:
    - FR33: Knight can observe all branch actions
    - FR34: Witness statements are observation only, no judgment
    - AC7: Statement includes factual observation content
    - AC8: No interpretation or recommendation in statement
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class ObservationContent:
    """Factual observation content (no judgment).

    Structure enforces observation-only by ONLY including factual fields.
    There are no optional fields for judgment - they don't exist at all.

    Fields included (factual):
        what: Factual description of what was observed
        when: Timestamp of the observed event
        who: Actor ID(s) involved in the observed event
        where: Component/branch identifier where event occurred
        event_type: The type of the observed event
        event_id: Reference to the observed event

    Fields explicitly excluded (judgment - NOT OPTIONAL, NOT PRESENT):
        - why: Interpretation of cause/motive
        - should: Recommendation
        - severity: Judgment of importance
        - recommendation: What to do about it
        - remedy: How to fix it
        - verdict: Conclusion about guilt/innocence
        - finding: Determination of violation

    The Knight's value is in COMPLETENESS and ACCURACY of observation,
    not in interpretation. Interpretation is for Prince panels.

    Example:
        >>> content = ObservationContent(
        ...     what="Task activated without explicit consent from Cluster",
        ...     when=datetime(2026, 1, 17, 10, 30, tzinfo=timezone.utc),
        ...     who=("actor-uuid-1",),  # Tuple for immutability
        ...     where="executive.task_coordination",
        ...     event_type="executive.task.activated",
        ...     event_id=uuid4(),
        ... )
        >>> content.summary
        'At 2026-01-17T10:30:00+00:00, executive.task.activated observed in executive.task_coordination'
    """

    what: str
    """Factual description of what was observed.

    Must be factual only. The WitnessStatementFactory validates
    that this field does not contain judgment language.
    """

    when: datetime
    """Timestamp of the observed event (from the event itself)."""

    who: tuple[str, ...]
    """Actor ID(s) involved in the observed event.

    Tuple (immutable) to support observations involving multiple actors.
    Using tuple instead of list ensures true immutability in frozen dataclass.
    """

    where: str
    """Component/branch identifier where event occurred.

    Format: branch.component (e.g., "executive.task_coordination")
    """

    event_type: str
    """The type of the observed event.

    Format: branch.noun.verb (e.g., "executive.task.activated")
    """

    event_id: UUID
    """Reference to the observed event's unique identifier."""

    @property
    def summary(self) -> str:
        """Human-readable summary of the observation (still factual).

        Returns a concise description of when, what type, and where.
        Does NOT include interpretation or judgment.
        """
        return f"At {self.when.isoformat()}, {self.event_type} observed in {self.where}"

    def __hash__(self) -> int:
        """Hash based on event_id and observation timestamp."""
        return hash((self.event_id, self.when))
