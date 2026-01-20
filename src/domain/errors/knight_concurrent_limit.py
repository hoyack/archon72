"""Knight concurrent limit errors (Story 4.7, FR-4.7).

This module defines errors for Knight concurrent referral limit enforcement.

Constitutional Constraints:
- FR-4.7: System SHALL enforce max concurrent referrals per Knight
- NFR-7.3: Referral load balancing - max concurrent per Knight configurable
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uuid import UUID


@dataclass(frozen=True)
class KnightAtCapacityError(Exception):
    """Raised when a Knight has reached max concurrent referrals (FR-4.7).

    This error indicates that the specified Knight cannot accept new
    referrals because they are at their realm's knight_capacity limit.

    Attributes:
        knight_id: The Knight's archon UUID.
        current_count: Current number of active referrals.
        max_allowed: Maximum allowed by realm's knight_capacity.
        realm_id: The realm imposing the limit.
    """

    knight_id: UUID
    current_count: int
    max_allowed: int
    realm_id: UUID

    def __str__(self) -> str:
        return (
            f"Knight {self.knight_id} at capacity: "
            f"{self.current_count}/{self.max_allowed} referrals "
            f"in realm {self.realm_id}"
        )


@dataclass(frozen=True)
class NoEligibleKnightsError(Exception):
    """Raised when no Knights in a realm can accept new referrals.

    This error indicates that all Knights in the realm have reached
    their capacity limits. The referral should remain PENDING.

    Attributes:
        realm_id: The realm with no eligible Knights.
        total_knights: Total number of Knights in the realm.
        knights_at_capacity: Number of Knights at capacity.
    """

    realm_id: UUID
    total_knights: int
    knights_at_capacity: int

    def __str__(self) -> str:
        return (
            f"No eligible Knights in realm {self.realm_id}: "
            f"{self.knights_at_capacity}/{self.total_knights} at capacity"
        )


@dataclass(frozen=True)
class KnightNotFoundError(Exception):
    """Raised when a Knight cannot be found.

    Attributes:
        knight_id: The Knight's archon UUID that was not found.
    """

    knight_id: UUID

    def __str__(self) -> str:
        return f"Knight not found: {self.knight_id}"


@dataclass(frozen=True)
class KnightNotInRealmError(Exception):
    """Raised when a Knight is not assigned to the specified realm.

    Attributes:
        knight_id: The Knight's archon UUID.
        realm_id: The realm the Knight is not in.
        actual_realm_id: The realm the Knight is actually in (if any).
    """

    knight_id: UUID
    realm_id: UUID
    actual_realm_id: UUID | None = None

    def __str__(self) -> str:
        if self.actual_realm_id:
            return (
                f"Knight {self.knight_id} is not in realm {self.realm_id}, "
                f"actually in realm {self.actual_realm_id}"
            )
        return f"Knight {self.knight_id} is not assigned to realm {self.realm_id}"


@dataclass(frozen=True)
class ReferralAlreadyAssignedError(Exception):
    """Raised when trying to assign a referral that's already assigned.

    Attributes:
        referral_id: The referral UUID.
        assigned_knight_id: The Knight already assigned.
    """

    referral_id: UUID
    assigned_knight_id: UUID

    def __str__(self) -> str:
        return (
            f"Referral {self.referral_id} already assigned to "
            f"Knight {self.assigned_knight_id}"
        )
