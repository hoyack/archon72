"""Cessation deliberation event payload (Story 7.8, FR135).

This module defines the CessationDeliberationEventPayload and related types
for recording the final deliberation before cessation.

Constitutional Constraints:
- FR135: Before cessation, final deliberation SHALL be recorded and immutable;
         if recording fails, that failure is the final event
- FR12: Dissent percentages visible in every vote tally
- CT-11: Silent failure destroys legitimacy -> Log ALL deliberation details
- CT-12: Witnessing creates accountability -> Deliberation MUST be witnessed
- CT-13: Integrity outranks availability -> HALT if recording fails

Developer Golden Rules:
1. DELIBERATION FIRST - Deliberation event BEFORE cessation event
2. 72 ARCHONS - All 72 must have entries (even abstaining)
3. WITNESS EVERYTHING - CT-12 requires witness attribution
4. FAIL LOUD - Recording failure becomes final event, system HALTs
5. DISSENT VISIBLE - FR12 requires dissent percentage in vote
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from src.domain.events.collective_output import VoteCounts

# Event type constant following lowercase.dot.notation convention
CESSATION_DELIBERATION_EVENT_TYPE: str = "cessation.deliberation"

# Required number of Archons for deliberation
REQUIRED_ARCHON_COUNT: int = 72


class ArchonPosition(Enum):
    """Position choices for cessation deliberation.

    Each Archon must take one of these positions during cessation
    deliberation. All 72 Archons must vote or abstain.

    Constitutional Constraint (FR135):
    All positions must be recorded before cessation.
    """

    SUPPORT_CESSATION = "SUPPORT_CESSATION"
    """Archon supports proceeding with cessation."""

    OPPOSE_CESSATION = "OPPOSE_CESSATION"
    """Archon opposes cessation and wishes to continue operations."""

    ABSTAIN = "ABSTAIN"
    """Archon abstains from voting but is still recorded."""


@dataclass(frozen=True, eq=True)
class ArchonDeliberation:
    """Single Archon's deliberation for cessation (FR135).

    Records an individual Archon's position and reasoning during
    the cessation deliberation. This is immutable once created.

    Constitutional Constraints:
    - FR135: Each Archon's reasoning must be captured
    - CT-12: Witnessing creates accountability

    Attributes:
        archon_id: Unique identifier for the Archon.
        position: SUPPORT_CESSATION, OPPOSE_CESSATION, or ABSTAIN.
        reasoning: Text of reasoning (may be empty for abstain).
        statement_timestamp: UTC timestamp when statement was made.
    """

    archon_id: str
    position: ArchonPosition
    reasoning: str
    statement_timestamp: datetime

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization.

        Returns:
            Dictionary representation for event payload.
        """
        return {
            "archon_id": self.archon_id,
            "position": self.position.value,
            "reasoning": self.reasoning,
            "statement_timestamp": self.statement_timestamp.isoformat(),
        }


@dataclass(frozen=True, eq=True)
class CessationDeliberationEventPayload:
    """Payload for cessation deliberation events (FR135).

    Records the complete final deliberation before cessation including
    all 72 Archon votes, reasoning, and timing information.

    This event MUST be witnessed (CT-12) and is immutable after creation.

    Constitutional Constraints:
    - FR135: Final deliberation SHALL be recorded and immutable
    - FR12: Dissent percentage visible in vote tally
    - CT-11: Silent failure destroys legitimacy -> All details logged
    - CT-12: Witnessing creates accountability -> Must be witnessed

    Attributes:
        deliberation_id: Unique identifier for this deliberation.
        deliberation_started_at: When deliberation began (UTC).
        deliberation_ended_at: When deliberation concluded (UTC).
        vote_recorded_at: When final vote tally was locked (UTC).
        duration_seconds: Total deliberation duration in seconds.
        archon_deliberations: All 72 Archon deliberations (must be exactly 72).
        vote_counts: Breakdown of yes/no/abstain votes.
        dissent_percentage: Percentage of non-majority votes (FR12).
    """

    deliberation_id: UUID
    deliberation_started_at: datetime
    deliberation_ended_at: datetime
    vote_recorded_at: datetime
    duration_seconds: int
    archon_deliberations: tuple[ArchonDeliberation, ...]
    vote_counts: VoteCounts
    dissent_percentage: float

    def __post_init__(self) -> None:
        """Validate payload fields for FR135 compliance.

        Raises:
            ValueError: If any field fails validation.
        """
        self._validate_archon_count()
        self._validate_vote_counts_match_positions()
        self._validate_dissent_percentage()
        self._validate_duration()

    def _validate_archon_count(self) -> None:
        """Validate exactly 72 Archons are present (FR135)."""
        count = len(self.archon_deliberations)
        if count != REQUIRED_ARCHON_COUNT:
            raise ValueError(
                f"FR135: Cessation deliberation requires exactly 72 Archon entries, "
                f"got {count}"
            )

    def _validate_vote_counts_match_positions(self) -> None:
        """Validate vote counts match the actual positions in deliberations."""
        actual_yes = sum(
            1
            for d in self.archon_deliberations
            if d.position == ArchonPosition.SUPPORT_CESSATION
        )
        actual_no = sum(
            1
            for d in self.archon_deliberations
            if d.position == ArchonPosition.OPPOSE_CESSATION
        )
        actual_abstain = sum(
            1 for d in self.archon_deliberations if d.position == ArchonPosition.ABSTAIN
        )

        if (
            actual_yes != self.vote_counts.yes_count
            or actual_no != self.vote_counts.no_count
            or actual_abstain != self.vote_counts.abstain_count
        ):
            raise ValueError(
                f"vote counts must match deliberation positions: "
                f"expected ({actual_yes}, {actual_no}, {actual_abstain}), "
                f"got ({self.vote_counts.yes_count}, {self.vote_counts.no_count}, "
                f"{self.vote_counts.abstain_count})"
            )

    def _validate_dissent_percentage(self) -> None:
        """Validate dissent percentage is between 0 and 100."""
        if not (0.0 <= self.dissent_percentage <= 100.0):
            raise ValueError(
                f"dissent_percentage must be between 0 and 100, "
                f"got {self.dissent_percentage}"
            )

    def _validate_duration(self) -> None:
        """Validate duration is non-negative."""
        if self.duration_seconds < 0:
            raise ValueError(
                f"duration_seconds must be non-negative, got {self.duration_seconds}"
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
        content: dict[str, Any] = {
            "archon_deliberations": [d.to_dict() for d in self.archon_deliberations],
            "deliberation_ended_at": self.deliberation_ended_at.isoformat(),
            "deliberation_id": str(self.deliberation_id),
            "deliberation_started_at": self.deliberation_started_at.isoformat(),
            "dissent_percentage": self.dissent_percentage,
            "duration_seconds": self.duration_seconds,
            "vote_counts": self.vote_counts.to_dict(),
            "vote_recorded_at": self.vote_recorded_at.isoformat(),
        }

        return json.dumps(content, sort_keys=True, ensure_ascii=False).encode("utf-8")

    def to_dict(self) -> dict[str, Any]:
        """Convert payload to dict for event storage.

        Returns:
            Dict representation suitable for EventWriterService.write_event().
        """
        return {
            "deliberation_id": str(self.deliberation_id),
            "deliberation_started_at": self.deliberation_started_at.isoformat(),
            "deliberation_ended_at": self.deliberation_ended_at.isoformat(),
            "vote_recorded_at": self.vote_recorded_at.isoformat(),
            "duration_seconds": self.duration_seconds,
            "archon_deliberations": [d.to_dict() for d in self.archon_deliberations],
            "vote_counts": self.vote_counts.to_dict(),
            "dissent_percentage": self.dissent_percentage,
        }
