"""Collective output event types (Story 2.3, FR11).

This module defines the CollectiveOutputPayload and related types
for recording collective deliberation outputs. FR11 requires that
collective outputs are attributed to the Conclave, not individual agents.

Constitutional Constraints:
- FR11: Collective outputs attributed to Conclave, not individuals
- CT-11: Silent failure destroys legitimacy
- CT-12: Witnessing creates accountability
- CT-13: Integrity outranks availability

ADR-2: Context Bundles (Format + Integrity)
- Content hash computed from canonical JSON
- Hash algorithm version tracked
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from uuid import UUID

# Event type constant following lowercase.dot.notation convention
COLLECTIVE_OUTPUT_EVENT_TYPE: str = "collective.output"


class AuthorType(Enum):
    """Type of author for deliberation outputs.

    Used to distinguish between collective outputs (attributed to the Conclave)
    and individual outputs (attributed to a single agent).

    FR11 requires collective outputs for Conclave decisions.
    """

    COLLECTIVE = "COLLECTIVE"
    INDIVIDUAL = "INDIVIDUAL"


@dataclass(frozen=True, eq=True)
class VoteCounts:
    """Vote counts for a collective deliberation (FR11, FR12).

    Records the breakdown of votes for a collective output.
    Used to calculate dissent percentage and unanimity.

    Attributes:
        yes_count: Number of yes votes (non-negative).
        no_count: Number of no votes (non-negative).
        abstain_count: Number of abstentions (non-negative).

    Properties:
        total: Total number of votes cast.

    Example:
        >>> vc = VoteCounts(yes_count=70, no_count=2, abstain_count=0)
        >>> vc.total
        72
    """

    yes_count: int
    no_count: int
    abstain_count: int

    def __post_init__(self) -> None:
        """Validate vote counts are non-negative.

        Raises:
            ValueError: If any count is negative.
        """
        if self.yes_count < 0:
            raise ValueError("yes_count must be non-negative")
        if self.no_count < 0:
            raise ValueError("no_count must be non-negative")
        if self.abstain_count < 0:
            raise ValueError("abstain_count must be non-negative")

    @property
    def total(self) -> int:
        """Total number of votes cast."""
        return self.yes_count + self.no_count + self.abstain_count

    def to_dict(self) -> dict[str, int]:
        """Convert to dictionary for JSON serialization.

        Returns:
            Dictionary with vote counts and total.
        """
        return {
            "yes_count": self.yes_count,
            "no_count": self.no_count,
            "abstain_count": self.abstain_count,
            "total": self.total,
        }


@dataclass(frozen=True, eq=True)
class CollectiveOutputPayload:
    """Payload for collective output events (FR11).

    Records collective deliberation outputs attributed to the Conclave.
    FR11 requires that no single agent can claim sole authorship.

    Attributes:
        output_id: Unique identifier for this output (UUID).
        author_type: Must be COLLECTIVE for FR11 compliance.
        contributing_agents: Tuple of agent IDs that contributed (min 2).
        content_hash: SHA-256 hash of the output content (64 hex chars).
        vote_counts: Breakdown of yes/no/abstain votes.
        dissent_percentage: Percentage of minority votes (0.0-100.0).
        unanimous: True if 100% agreement, False otherwise.
        linked_vote_event_ids: UUIDs of individual vote events.

    Constitutional Constraints:
        - FR11: Requires at least 2 contributing agents
        - CT-12: Output is witnessed and recorded

    Example:
        >>> from uuid import uuid4
        >>> payload = CollectiveOutputPayload(
        ...     output_id=uuid4(),
        ...     author_type=AuthorType.COLLECTIVE,
        ...     contributing_agents=("archon-1", "archon-2"),
        ...     content_hash="a" * 64,
        ...     vote_counts=VoteCounts(yes_count=70, no_count=2, abstain_count=0),
        ...     dissent_percentage=2.78,
        ...     unanimous=False,
        ...     linked_vote_event_ids=(uuid4(), uuid4()),
        ... )
    """

    output_id: UUID
    author_type: AuthorType
    contributing_agents: tuple[str, ...]
    content_hash: str
    vote_counts: VoteCounts
    dissent_percentage: float
    unanimous: bool
    linked_vote_event_ids: tuple[UUID, ...]

    def __post_init__(self) -> None:
        """Validate payload fields for FR11 compliance.

        Raises:
            TypeError: If output_id is not a UUID.
            ValueError: If any field fails validation.
        """
        self._validate_output_id()
        self._validate_contributing_agents()
        self._validate_content_hash()
        self._validate_dissent_percentage()

    def _validate_output_id(self) -> None:
        """Validate output_id is a UUID."""
        if not isinstance(self.output_id, UUID):
            raise TypeError(
                f"output_id must be UUID, got {type(self.output_id).__name__}"
            )

    def _validate_contributing_agents(self) -> None:
        """Validate FR11: collective output requires multiple participants."""
        if len(self.contributing_agents) < 2:
            raise ValueError(
                "FR11: Collective output requires multiple participants "
                f"(got {len(self.contributing_agents)})"
            )

    def _validate_content_hash(self) -> None:
        """Validate content_hash is 64 character hex string (SHA-256)."""
        if not isinstance(self.content_hash, str):
            raise ValueError(
                f"content_hash must be 64 character hex string (SHA-256), "
                f"got {type(self.content_hash).__name__}"
            )
        if len(self.content_hash) != 64:
            raise ValueError(
                f"content_hash must be 64 character hex string (SHA-256), "
                f"got {len(self.content_hash)} characters"
            )
        # Validate hex characters (SHA-256 produces lowercase hex)
        if not all(c in "0123456789abcdef" for c in self.content_hash.lower()):
            raise ValueError(
                "content_hash must contain only hexadecimal characters (0-9, a-f)"
            )

    def _validate_dissent_percentage(self) -> None:
        """Validate dissent_percentage is between 0.0 and 100.0."""
        if not (0.0 <= self.dissent_percentage <= 100.0):
            raise ValueError(
                f"dissent_percentage must be between 0.0 and 100.0, "
                f"got {self.dissent_percentage}"
            )

    def to_dict(self) -> dict[str, object]:
        """Convert payload to dictionary for event payload field.

        Returns:
            Dictionary suitable for JSON serialization.
        """
        return {
            "output_id": str(self.output_id),
            "author_type": self.author_type.value,
            "contributing_agents": list(self.contributing_agents),
            "content_hash": self.content_hash,
            "vote_counts": self.vote_counts.to_dict(),
            "dissent_percentage": self.dissent_percentage,
            "unanimous": self.unanimous,
            "linked_vote_event_ids": [str(uid) for uid in self.linked_vote_event_ids],
        }
