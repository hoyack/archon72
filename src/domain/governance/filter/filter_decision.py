"""FilterDecision enum for coercion filter outcomes.

Defines the three possible outcomes of content filtering per FR16-FR18:
- ACCEPTED: Content can be sent (possibly with transformations)
- REJECTED: Content requires rewrite before sending
- BLOCKED: Hard violation, content cannot be sent
"""

from enum import Enum


class FilterDecision(Enum):
    """Outcome of content filtering.

    Per FR16-FR18, the Coercion Filter can:
    - Accept content (with optional transformations)
    - Reject content (requiring Earl to rewrite)
    - Block content (hard violation, logged)
    """

    ACCEPTED = "accepted"
    REJECTED = "rejected"
    BLOCKED = "blocked"

    @property
    def description(self) -> str:
        """Human-readable description of this decision.

        Returns:
            Description explaining what this decision means.
        """
        descriptions = {
            FilterDecision.ACCEPTED: "Content can be sent to participant (possibly with transformations applied)",
            FilterDecision.REJECTED: "Content requires rewrite before sending - not a violation, just needs revision",
            FilterDecision.BLOCKED: "Hard violation detected - content cannot be sent under any circumstance",
        }
        return descriptions[self]

    @property
    def is_sendable(self) -> bool:
        """Whether content with this decision can be sent to participants.

        Returns:
            True only for ACCEPTED decisions.
        """
        return self == FilterDecision.ACCEPTED

    @property
    def requires_action(self) -> bool:
        """Whether this decision requires follow-up action.

        Returns:
            True for REJECTED (rewrite) and BLOCKED (investigation).
        """
        return self in (FilterDecision.REJECTED, FilterDecision.BLOCKED)
