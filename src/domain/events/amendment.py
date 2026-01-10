"""Amendment visibility event payloads (Story 6.7, FR126-FR128).

This module defines event payloads for constitutional amendment visibility:
- AmendmentProposedEventPayload: When an amendment is submitted (14-day visibility starts)
- AmendmentVoteBlockedEventPayload: When a vote is blocked due to incomplete visibility
- AmendmentRejectedEventPayload: When an amendment is rejected (FR128 history protection)

Constitutional Constraints:
- FR126: Constitutional amendment proposals SHALL be publicly visible minimum 14 days before vote
- FR127: Amendments affecting core guarantees SHALL require published impact analysis
         ("reduces visibility? raises silence probability? weakens irreversibility?")
- FR128: Amendments making previous amendments unreviewable are constitutionally prohibited
- CT-11: Silent failure destroys legitimacy -> HALT OVER DEGRADE
- CT-12: Witnessing creates accountability -> All amendment events MUST be witnessed
- CT-15: Legitimacy requires consent -> 14-day period ensures informed consent

Developer Golden Rules:
1. HALT CHECK FIRST - Check halt state before any operation
2. WITNESS EVERYTHING - All amendment events must be witnessed
3. FAIL LOUD - Failed event write = operation failure

ADR-6 Context (Amendment, Ceremony, and Convention Tier):
- Tier 2 (Constitutional): 14 days visibility, 3 Keepers + witness, 24h cooling
- Tier 3 (Convention): 14 days visibility, supermajority + external, 7d cooling
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

# Visibility period in days (FR126)
VISIBILITY_PERIOD_DAYS: int = 14

# Event type constants for amendment visibility
AMENDMENT_PROPOSED_EVENT_TYPE: str = "amendment.proposed"
AMENDMENT_VOTE_BLOCKED_EVENT_TYPE: str = "amendment.vote_blocked"
AMENDMENT_REJECTED_EVENT_TYPE: str = "amendment.rejected"


class AmendmentType(Enum):
    """Amendment tier types per ADR-6.

    Tier 2 and Tier 3 amendments both require the 14-day visibility period.
    Tier 1 (Operational) changes do not go through this process.
    """

    TIER_2_CONSTITUTIONAL = "tier_2_constitutional"
    """Schema changes, ADR amendments. Requires 3 Keepers + witness, 24h cooling."""

    TIER_3_CONVENTION = "tier_3_convention"
    """Fundamental constitutional changes. Requires supermajority + external, 7d cooling."""


class AmendmentStatus(Enum):
    """Status of an amendment proposal through the visibility process.

    Represents the lifecycle of an amendment from proposal through voting.
    """

    PROPOSED = "proposed"
    """Initial state when amendment is submitted."""

    VISIBILITY_PERIOD = "visibility_period"
    """Amendment is in the 14-day public visibility period (FR126)."""

    VOTABLE = "votable"
    """Visibility period complete, ready for vote."""

    VOTING = "voting"
    """Vote is in progress."""

    APPROVED = "approved"
    """Amendment was approved by required quorum."""

    REJECTED = "rejected"
    """Amendment was rejected during vote or validation."""


@dataclass(frozen=True, eq=True)
class AmendmentImpactAnalysis:
    """Impact analysis for core guarantee amendments (FR127).

    FR127 requires amendments affecting core guarantees to answer:
    - "reduces visibility?" - Does this reduce transparency
    - "raises silence probability?" - Does this increase chance of silent failures
    - "weakens irreversibility?" - Does this weaken append-only/immutable guarantees

    The analysis must be published alongside the amendment for the full
    14-day visibility period.

    Attributes:
        reduces_visibility: FR127 question 1 - Does this reduce transparency.
        raises_silence_probability: FR127 question 2 - Does this increase silent failure chance.
        weakens_irreversibility: FR127 question 3 - Does this weaken immutability.
        analysis_text: Human-readable explanation of the analysis (min 50 chars).
        analyzed_by: Attribution of who performed the analysis.
        analyzed_at: When the analysis was completed (UTC).
    """

    reduces_visibility: bool
    raises_silence_probability: bool
    weakens_irreversibility: bool
    analysis_text: str
    analyzed_by: str
    analyzed_at: datetime

    def __post_init__(self) -> None:
        """Validate analysis completeness."""
        if not self.analysis_text or len(self.analysis_text) < 50:
            raise ValueError(
                f"analysis_text must be at least 50 characters, got {len(self.analysis_text or '')}"
            )
        if not self.analyzed_by:
            raise ValueError("analyzed_by must be provided for attribution")

    def to_dict(self) -> dict[str, Any]:
        """Serialize analysis for storage/transmission.

        Returns:
            Dictionary representation of the impact analysis.
        """
        return {
            "reduces_visibility": self.reduces_visibility,
            "raises_silence_probability": self.raises_silence_probability,
            "weakens_irreversibility": self.weakens_irreversibility,
            "analysis_text": self.analysis_text,
            "analyzed_by": self.analyzed_by,
            "analyzed_at": self.analyzed_at.isoformat(),
        }


@dataclass(frozen=True, eq=True)
class AmendmentProposedEventPayload:
    """Payload for amendment proposal events (FR126, FR127, ADR-6).

    An AmendmentProposedEventPayload is created when a constitutional amendment
    is submitted. This starts the 14-day visibility period (FR126) during which
    the amendment must be publicly visible before any vote can occur.

    Constitutional Constraints:
    - FR126: Amendment proposals SHALL be publicly visible minimum 14 days before vote
    - FR127: Core guarantee amendments require impact analysis
    - CT-11: Silent failure destroys legitimacy
    - CT-12: Witnessing creates accountability
    - CT-15: Legitimacy requires consent

    Attributes:
        amendment_id: Unique identifier for this amendment.
        amendment_type: Constitutional tier (Tier 2 or Tier 3 per ADR-6).
        title: Brief description of the amendment.
        summary: Full amendment text/summary.
        proposed_at: When the amendment was submitted (UTC).
        visible_from: When visibility period started (same as proposed_at).
        votable_from: When vote can occur (14 days after visible_from, FR126).
        proposer_id: Who submitted the amendment (attribution).
        is_core_guarantee: True if this affects core constitutional guarantees.
        impact_analysis: Required if is_core_guarantee is True (FR127).
        affected_guarantees: Which constitutional guarantees are affected.
    """

    amendment_id: str
    amendment_type: AmendmentType
    title: str
    summary: str
    proposed_at: datetime
    visible_from: datetime
    votable_from: datetime
    proposer_id: str
    is_core_guarantee: bool
    affected_guarantees: tuple[str, ...] = field(default_factory=tuple)
    impact_analysis: AmendmentImpactAnalysis | None = None

    def __post_init__(self) -> None:
        """Validate amendment proposal.

        Validates:
        - amendment_id is non-empty
        - title is non-empty
        - summary is non-empty
        - proposer_id is non-empty
        - votable_from is 14 days after visible_from
        - impact_analysis is provided if is_core_guarantee is True
        """
        if not self.amendment_id:
            raise ValueError("amendment_id must be non-empty")
        if not self.title:
            raise ValueError("title must be non-empty")
        if not self.summary:
            raise ValueError("summary must be non-empty")
        if not self.proposer_id:
            raise ValueError("proposer_id must be non-empty")

        # Validate 14-day visibility period (FR126)
        expected_votable = self.visible_from + timedelta(days=VISIBILITY_PERIOD_DAYS)
        # Allow 1 second tolerance for floating point datetime issues
        if abs((self.votable_from - expected_votable).total_seconds()) > 1:
            raise ValueError(
                f"FR126: votable_from must be {VISIBILITY_PERIOD_DAYS} days after visible_from"
            )

        # FR127: Core guarantees require impact analysis
        if self.is_core_guarantee and self.impact_analysis is None:
            raise ValueError(
                "FR127: Core guarantee amendments require impact analysis"
            )

    def signable_content(self) -> bytes:
        """Return canonical content for witnessing (CT-12).

        Constitutional Constraint (CT-12):
        Witnessing creates accountability. This method provides
        the canonical bytes to sign for witness verification.

        The content is JSON-serialized with sorted keys to ensure
        deterministic output regardless of Python dict ordering.

        Returns:
            UTF-8 encoded bytes of canonical JSON representation.
        """
        payload = {
            "event_type": AMENDMENT_PROPOSED_EVENT_TYPE,
            "amendment_id": self.amendment_id,
            "amendment_type": self.amendment_type.value,
            "title": self.title,
            "summary": self.summary,
            "proposed_at": self.proposed_at.isoformat(),
            "visible_from": self.visible_from.isoformat(),
            "votable_from": self.votable_from.isoformat(),
            "proposer_id": self.proposer_id,
            "is_core_guarantee": self.is_core_guarantee,
            "affected_guarantees": list(self.affected_guarantees),
        }
        if self.impact_analysis is not None:
            payload["impact_analysis"] = self.impact_analysis.to_dict()

        return json.dumps(payload, sort_keys=True).encode("utf-8")

    def to_dict(self) -> dict[str, Any]:
        """Serialize payload for storage/transmission.

        Returns:
            Dictionary representation of the payload.
        """
        result: dict[str, Any] = {
            "amendment_id": self.amendment_id,
            "amendment_type": self.amendment_type.value,
            "title": self.title,
            "summary": self.summary,
            "proposed_at": self.proposed_at.isoformat(),
            "visible_from": self.visible_from.isoformat(),
            "votable_from": self.votable_from.isoformat(),
            "proposer_id": self.proposer_id,
            "is_core_guarantee": self.is_core_guarantee,
            "affected_guarantees": list(self.affected_guarantees),
        }
        if self.impact_analysis is not None:
            result["impact_analysis"] = self.impact_analysis.to_dict()
        return result

    @property
    def days_until_votable(self) -> int:
        """Calculate days remaining until vote can occur.

        Returns:
            Days remaining, or 0 if already votable.
        """
        from datetime import timezone

        now = datetime.now(timezone.utc)
        if now >= self.votable_from:
            return 0
        return (self.votable_from - now).days + 1


@dataclass(frozen=True, eq=True)
class AmendmentVoteBlockedEventPayload:
    """Payload for amendment vote blocked events (FR126).

    An AmendmentVoteBlockedEventPayload is created when a vote is attempted
    on an amendment before the 14-day visibility period is complete.
    This event is witnessed to provide accountability (CT-12).

    Constitutional Constraints:
    - FR126: Votes blocked if visibility period incomplete
    - CT-11: Silent failure destroys legitimacy
    - CT-12: Witnessing creates accountability

    Attributes:
        amendment_id: The amendment that was blocked.
        blocked_reason: Why the vote was blocked (includes FR126 reference).
        days_remaining: Days until the amendment becomes votable.
        votable_from: When the amendment will be votable (UTC).
        blocked_at: When the vote attempt was blocked (UTC).
    """

    amendment_id: str
    blocked_reason: str
    days_remaining: int
    votable_from: datetime
    blocked_at: datetime

    def __post_init__(self) -> None:
        """Validate blocked event."""
        if not self.amendment_id:
            raise ValueError("amendment_id must be non-empty")
        if not self.blocked_reason:
            raise ValueError("blocked_reason must be non-empty")
        if self.days_remaining < 0:
            raise ValueError(
                f"days_remaining must be non-negative, got {self.days_remaining}"
            )

    def signable_content(self) -> bytes:
        """Return canonical content for witnessing (CT-12).

        Constitutional Constraint (CT-12):
        Witnessing creates accountability. This method provides
        the canonical bytes to sign for witness verification.

        Returns:
            UTF-8 encoded bytes of canonical JSON representation.
        """
        return json.dumps(
            {
                "event_type": AMENDMENT_VOTE_BLOCKED_EVENT_TYPE,
                "amendment_id": self.amendment_id,
                "blocked_reason": self.blocked_reason,
                "days_remaining": self.days_remaining,
                "votable_from": self.votable_from.isoformat(),
                "blocked_at": self.blocked_at.isoformat(),
            },
            sort_keys=True,
        ).encode("utf-8")

    def to_dict(self) -> dict[str, Any]:
        """Serialize payload for storage/transmission.

        Returns:
            Dictionary representation of the payload.
        """
        return {
            "amendment_id": self.amendment_id,
            "blocked_reason": self.blocked_reason,
            "days_remaining": self.days_remaining,
            "votable_from": self.votable_from.isoformat(),
            "blocked_at": self.blocked_at.isoformat(),
        }


@dataclass(frozen=True, eq=True)
class AmendmentRejectedEventPayload:
    """Payload for amendment rejection events (FR128).

    An AmendmentRejectedEventPayload is created when an amendment is rejected
    during validation, typically for FR128 history protection violations.
    This event is witnessed to provide accountability (CT-12).

    Constitutional Constraints:
    - FR128: Amendments making previous amendments unreviewable are prohibited
    - CT-11: Silent failure destroys legitimacy
    - CT-12: Witnessing creates accountability

    Attributes:
        amendment_id: The amendment that was rejected.
        rejection_reason: Why the amendment was rejected (includes FR reference).
        rejected_at: When the rejection occurred (UTC).
    """

    amendment_id: str
    rejection_reason: str
    rejected_at: datetime

    def __post_init__(self) -> None:
        """Validate rejected event."""
        if not self.amendment_id:
            raise ValueError("amendment_id must be non-empty")
        if not self.rejection_reason:
            raise ValueError("rejection_reason must be non-empty")

    def signable_content(self) -> bytes:
        """Return canonical content for witnessing (CT-12).

        Constitutional Constraint (CT-12):
        Witnessing creates accountability. This method provides
        the canonical bytes to sign for witness verification.

        Returns:
            UTF-8 encoded bytes of canonical JSON representation.
        """
        return json.dumps(
            {
                "event_type": AMENDMENT_REJECTED_EVENT_TYPE,
                "amendment_id": self.amendment_id,
                "rejection_reason": self.rejection_reason,
                "rejected_at": self.rejected_at.isoformat(),
            },
            sort_keys=True,
        ).encode("utf-8")

    def to_dict(self) -> dict[str, Any]:
        """Serialize payload for storage/transmission.

        Returns:
            Dictionary representation of the payload.
        """
        return {
            "amendment_id": self.amendment_id,
            "rejection_reason": self.rejection_reason,
            "rejected_at": self.rejected_at.isoformat(),
        }
