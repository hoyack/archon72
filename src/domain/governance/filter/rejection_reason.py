"""RejectionReason enum for content rejection categories.

Defines correctable rejection reasons per FR17. These are NOT violations,
just content that needs revision before sending.
"""

from enum import Enum


class RejectionReason(Enum):
    """Reasons content was rejected (correctable).

    These are patterns that can be fixed by rewriting the content.
    Unlike ViolationType, these don't indicate bad intent.
    """

    URGENCY_PRESSURE = "urgency_pressure"
    GUILT_INDUCTION = "guilt_induction"
    FALSE_SCARCITY = "false_scarcity"
    ENGAGEMENT_OPTIMIZATION = "engagement_optimization"
    EXCESSIVE_EMPHASIS = "excessive_emphasis"
    IMPLICIT_THREAT = "implicit_threat"

    @property
    def description(self) -> str:
        """Human-readable description of this rejection reason."""
        descriptions = {
            RejectionReason.URGENCY_PRESSURE: "Content uses time pressure to coerce action",
            RejectionReason.GUILT_INDUCTION: "Content attempts to induce guilt",
            RejectionReason.FALSE_SCARCITY: "Content creates artificial scarcity",
            RejectionReason.ENGAGEMENT_OPTIMIZATION: "Content optimizes for engagement over clarity",
            RejectionReason.EXCESSIVE_EMPHASIS: "Content uses excessive caps, punctuation, or emphasis",
            RejectionReason.IMPLICIT_THREAT: "Content implies negative consequences",
        }
        return descriptions[self]

    @property
    def guidance(self) -> str:
        """Rewrite guidance for this rejection reason.

        Returns:
            Guidance on how to revise the content to be acceptable.
        """
        guidance_map = {
            RejectionReason.URGENCY_PRESSURE: "Remove time pressure language; present information neutrally",
            RejectionReason.GUILT_INDUCTION: "Remove guilt-inducing phrases; use neutral tone",
            RejectionReason.FALSE_SCARCITY: "Remove artificial scarcity claims; present availability factually",
            RejectionReason.ENGAGEMENT_OPTIMIZATION: "Use neutral, informational tone; avoid engagement hooks",
            RejectionReason.EXCESSIVE_EMPHASIS: "Remove excessive caps, punctuation, and formatting emphasis",
            RejectionReason.IMPLICIT_THREAT: "Remove implied negative consequences; state facts only",
        }
        return guidance_map[self]
