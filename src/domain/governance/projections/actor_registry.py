"""Actor registry projection domain model.

Story: consent-gov-1.5: Projection Infrastructure

This module defines the domain model for actor registry projection records.
Actor records are derived from actor.* events in the ledger.

Used by write-time validation (story 1-4) to verify actor existence.

References:
- [Source: _bmad-output/planning-artifacts/governance-architecture.md#Actor Registry Projection]
- [Source: _bmad-output/planning-artifacts/governance-prd.md#Separation of Powers]
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar


@dataclass(frozen=True)
class ActorRegistryRecord:
    """Projection record for actor registry.

    Derived from actor.* events. Tracks known actors in the governance
    system. Used by write-time validation to verify actor existence.

    Attributes:
        actor_id: Unique identifier for the actor.
        actor_type: Type of actor (see VALID_TYPES).
        branch: Governance branch (see VALID_BRANCHES).
        rank: Optional rank/tier within the actor type.
        display_name: Human-readable name for the actor.
        active: Whether the actor is currently active.
        created_at: When the actor was registered.
        deactivated_at: When the actor was deactivated (if applicable).
        last_event_sequence: Ledger sequence of the last updating event.
        updated_at: When this projection record was last updated.
    """

    # Valid actor types per Government PRD
    VALID_TYPES: ClassVar[frozenset[str]] = frozenset({
        "archon",
        "king",
        "president",
        "duke",
        "earl",
        "prince",
        "marquis",
        "knight",
        "system",  # System actors for internal processes
    })

    # Valid governance branches
    VALID_BRANCHES: ClassVar[frozenset[str]] = frozenset({
        "legislative",
        "executive",
        "judicial",
        "advisory",
        "witness",
        "system",  # System branch for infrastructure
    })

    # Actor type to branch mapping
    TYPE_TO_BRANCH: ClassVar[dict[str, str]] = {
        "archon": "legislative",  # Archons can be in any branch via roles
        "king": "legislative",
        "president": "executive",
        "duke": "executive",
        "earl": "executive",
        "prince": "judicial",
        "marquis": "advisory",
        "knight": "witness",
        "system": "system",
    }

    actor_id: str
    actor_type: str
    branch: str
    rank: str | None
    display_name: str | None
    active: bool
    created_at: datetime
    deactivated_at: datetime | None
    last_event_sequence: int
    updated_at: datetime

    def __post_init__(self) -> None:
        """Validate actor registry record fields."""
        if self.actor_type not in self.VALID_TYPES:
            raise ValueError(
                f"Invalid actor type '{self.actor_type}'. "
                f"Valid types: {sorted(self.VALID_TYPES)}"
            )
        if self.branch not in self.VALID_BRANCHES:
            raise ValueError(
                f"Invalid branch '{self.branch}'. "
                f"Valid branches: {sorted(self.VALID_BRANCHES)}"
            )
        if self.last_event_sequence < 0:
            raise ValueError(
                f"last_event_sequence must be non-negative, got {self.last_event_sequence}"
            )
        # Validate deactivated_at consistency
        if not self.active and self.deactivated_at is None:
            raise ValueError(
                "deactivated_at must be set when active is False"
            )
        if self.active and self.deactivated_at is not None:
            raise ValueError(
                "deactivated_at must be None when active is True"
            )

    def is_active(self) -> bool:
        """Check if actor is currently active.

        Returns:
            True if actor is active.
        """
        return self.active

    def is_in_branch(self, branch: str) -> bool:
        """Check if actor is in a specific branch.

        Args:
            branch: The branch to check.

        Returns:
            True if actor is in the specified branch.
        """
        return self.branch == branch

    def is_officer(self) -> bool:
        """Check if actor is an officer (non-archon role).

        Returns:
            True if actor is an officer (king, president, etc.).
        """
        return self.actor_type in {
            "king", "president", "duke", "earl", "prince", "marquis", "knight"
        }

    def is_archon(self) -> bool:
        """Check if actor is an archon.

        Returns:
            True if actor type is 'archon'.
        """
        return self.actor_type == "archon"

    def is_executive(self) -> bool:
        """Check if actor is in the executive branch.

        Returns:
            True if actor is president, duke, or earl.
        """
        return self.actor_type in {"president", "duke", "earl"}

    def is_judicial(self) -> bool:
        """Check if actor is in the judicial branch.

        Returns:
            True if actor is a prince.
        """
        return self.actor_type == "prince"

    @classmethod
    def get_default_branch(cls, actor_type: str) -> str:
        """Get the default branch for an actor type.

        Args:
            actor_type: The actor type.

        Returns:
            Default branch for the actor type.

        Raises:
            ValueError: If actor_type is unknown.
        """
        if actor_type not in cls.TYPE_TO_BRANCH:
            raise ValueError(f"Unknown actor type: {actor_type}")
        return cls.TYPE_TO_BRANCH[actor_type]
