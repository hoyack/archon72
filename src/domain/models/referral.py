"""Referral domain models (Story 4.1, FR-4.1, FR-4.2).

This module defines the domain models for Knight referral workflow:
- ReferralStatus: State machine for referral lifecycle
- ReferralRecommendation: Knight's recommendation options
- Referral: Main referral aggregate with deadline tracking

Constitutional Constraints:
- FR-4.1: Marquis SHALL be able to REFER petition to Knight with realm_id
- FR-4.2: System SHALL assign referral deadline (3 cycles default)
- NFR-3.4: Referral timeout reliability - 100% timeouts fire
- NFR-4.4: Referral deadline persistence - survives scheduler restart

Developer Golden Rules:
1. HALT CHECK FIRST - Check halt state before modifying referrals (writes)
2. WITNESS EVERYTHING - All referral events require attribution
3. FAIL LOUD - Never silently swallow deadline errors
4. READS DURING HALT - Referral queries work during halt (CT-13)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from uuid import UUID


class ReferralStatus(str, Enum):
    """Status states for a referral (FR-4.1, FR-4.2).

    Represents the lifecycle of a Knight referral from creation
    to completion or expiration.

    State Transition Matrix:
    - PENDING -> ASSIGNED, EXPIRED
    - ASSIGNED -> IN_REVIEW, EXPIRED
    - IN_REVIEW -> COMPLETED, EXPIRED
    - COMPLETED -> (terminal)
    - EXPIRED -> (terminal)
    """

    PENDING = "pending"
    """Referral created, awaiting Knight assignment."""

    ASSIGNED = "assigned"
    """Knight has been assigned to review."""

    IN_REVIEW = "in_review"
    """Knight is actively reviewing."""

    COMPLETED = "completed"
    """Knight submitted recommendation."""

    EXPIRED = "expired"
    """Referral deadline passed without recommendation."""

    def is_terminal(self) -> bool:
        """Check if this is a terminal state.

        Returns:
            True if COMPLETED or EXPIRED, False otherwise.
        """
        return self in (ReferralStatus.COMPLETED, ReferralStatus.EXPIRED)

    def can_transition_to(self, target: ReferralStatus) -> bool:
        """Check if transition to target state is valid.

        Args:
            target: The target status to transition to.

        Returns:
            True if the transition is valid, False otherwise.
        """
        valid_transitions: dict[ReferralStatus, set[ReferralStatus]] = {
            ReferralStatus.PENDING: {ReferralStatus.ASSIGNED, ReferralStatus.EXPIRED},
            ReferralStatus.ASSIGNED: {ReferralStatus.IN_REVIEW, ReferralStatus.EXPIRED},
            ReferralStatus.IN_REVIEW: {
                ReferralStatus.COMPLETED,
                ReferralStatus.EXPIRED,
            },
            ReferralStatus.COMPLETED: set(),  # Terminal
            ReferralStatus.EXPIRED: set(),  # Terminal
        }
        return target in valid_transitions.get(self, set())


class ReferralRecommendation(str, Enum):
    """Knight's recommendation options (FR-4.6).

    When a Knight completes their review, they must submit
    one of these recommendations.
    """

    ACKNOWLEDGE = "acknowledge"
    """Recommend acknowledging the petition (routes to Epic 3)."""

    ESCALATE = "escalate"
    """Recommend escalating to King (routes to Epic 6)."""


# Class constants for Referral (defined outside the dataclass to avoid field ordering issues)
REFERRAL_MAX_EXTENSIONS: int = 2
"""Maximum number of deadline extensions allowed (FR-4.4)."""

REFERRAL_DEFAULT_DEADLINE_CYCLES: int = 3
"""Default deadline in cycles (FR-4.2)."""

REFERRAL_DEFAULT_CYCLE_DURATION: timedelta = timedelta(weeks=1)
"""Duration of one cycle (Conclave convenes weekly)."""


@dataclass(frozen=True, eq=True)
class Referral:
    """A Knight referral for petition review (FR-4.1, FR-4.2).

    Represents a petition that has been referred to a domain expert Knight
    for review and recommendation. Tracks the full lifecycle including
    deadline, extensions, and final recommendation.

    Constitutional Constraints:
    - FR-4.1: Marquis REFER with realm_id
    - FR-4.2: 3 cycles default deadline
    - FR-4.4: Max 2 extensions
    - NFR-3.4: 100% timeout reliability
    - NFR-4.4: Deadline survives restart

    Attributes:
        referral_id: Unique identifier for this referral.
        petition_id: Foreign key to the petition being referred.
        realm_id: The realm this referral is routed to.
        assigned_knight_id: Knight assigned to review (nullable until assignment).
        status: Current referral status.
        deadline: When the referral must be completed by (UTC).
        extensions_granted: Number of extensions granted (0-2).
        recommendation: Knight's recommendation (nullable until completed).
        rationale: Knight's rationale for recommendation (nullable).
        created_at: When the referral was created (UTC).
        completed_at: When the referral was completed (UTC, nullable).
    """

    # Required fields
    referral_id: UUID
    petition_id: UUID
    realm_id: UUID
    deadline: datetime
    created_at: datetime

    # Optional/nullable fields
    assigned_knight_id: UUID | None = field(default=None)
    status: ReferralStatus = field(default=ReferralStatus.PENDING)
    extensions_granted: int = field(default=0)
    recommendation: ReferralRecommendation | None = field(default=None)
    rationale: str | None = field(default=None)
    completed_at: datetime | None = field(default=None)

    # Class-level constants (for backwards compatibility)
    MAX_EXTENSIONS: int = field(default=REFERRAL_MAX_EXTENSIONS, init=False, repr=False)
    DEFAULT_DEADLINE_CYCLES: int = field(
        default=REFERRAL_DEFAULT_DEADLINE_CYCLES, init=False, repr=False
    )
    DEFAULT_CYCLE_DURATION: timedelta = field(
        default=REFERRAL_DEFAULT_CYCLE_DURATION, init=False, repr=False
    )

    def __post_init__(self) -> None:
        """Validate referral fields after initialization.

        Raises:
            ValueError: If any field validation fails.
        """
        # Validate extensions_granted range
        if not 0 <= self.extensions_granted <= self.MAX_EXTENSIONS:
            raise ValueError(
                f"extensions_granted must be 0-{self.MAX_EXTENSIONS}, "
                f"got {self.extensions_granted}"
            )

        # Validate deadline is timezone-aware
        if self.deadline.tzinfo is None:
            raise ValueError("deadline must be timezone-aware (UTC)")

        # Validate created_at is timezone-aware
        if self.created_at.tzinfo is None:
            raise ValueError("created_at must be timezone-aware (UTC)")

        # Validate completed_at is timezone-aware if set
        if self.completed_at is not None and self.completed_at.tzinfo is None:
            raise ValueError("completed_at must be timezone-aware (UTC)")

        # Validate recommendation requires COMPLETED status
        if self.recommendation is not None and self.status != ReferralStatus.COMPLETED:
            raise ValueError("recommendation can only be set when status is COMPLETED")

        # Validate recommendation requires rationale
        if self.recommendation is not None and not self.rationale:
            raise ValueError("recommendation requires rationale")

        # Validate COMPLETED status requires recommendation
        if self.status == ReferralStatus.COMPLETED and self.recommendation is None:
            raise ValueError("COMPLETED status requires recommendation")

        # Validate COMPLETED status requires completed_at
        if self.status == ReferralStatus.COMPLETED and self.completed_at is None:
            raise ValueError("COMPLETED status requires completed_at timestamp")

        # Validate assigned_knight_id for non-PENDING statuses
        if self.status not in (ReferralStatus.PENDING, ReferralStatus.EXPIRED):
            if self.assigned_knight_id is None:
                raise ValueError(
                    f"assigned_knight_id required for status {self.status.value}"
                )

    def can_extend(self) -> bool:
        """Check if a deadline extension is possible.

        Extensions are allowed if:
        - extensions_granted < MAX_EXTENSIONS (2)
        - status is ASSIGNED or IN_REVIEW

        Returns:
            True if extension is possible, False otherwise.
        """
        if self.extensions_granted >= self.MAX_EXTENSIONS:
            return False
        return self.status in (ReferralStatus.ASSIGNED, ReferralStatus.IN_REVIEW)

    def can_submit_recommendation(self) -> bool:
        """Check if a recommendation can be submitted.

        Recommendations are allowed if:
        - status is IN_REVIEW
        - assigned_knight_id is set

        Returns:
            True if recommendation is allowed, False otherwise.
        """
        if self.status != ReferralStatus.IN_REVIEW:
            return False
        return self.assigned_knight_id is not None

    def is_expired(self) -> bool:
        """Check if the referral has expired.

        A referral is expired if:
        - status is EXPIRED, OR
        - deadline has passed and status is not COMPLETED

        Returns:
            True if expired, False otherwise.
        """
        if self.status == ReferralStatus.EXPIRED:
            return True
        if self.status == ReferralStatus.COMPLETED:
            return False
        return datetime.now(timezone.utc) > self.deadline

    def with_status(self, new_status: ReferralStatus) -> Referral:
        """Create a new referral with updated status.

        Validates that the state transition is allowed.

        Args:
            new_status: The new status to transition to.

        Returns:
            New Referral instance with updated status.

        Raises:
            ValueError: If the state transition is not allowed.
        """
        if not self.status.can_transition_to(new_status):
            raise ValueError(
                f"Invalid state transition: {self.status.value} -> {new_status.value}"
            )

        return Referral(
            referral_id=self.referral_id,
            petition_id=self.petition_id,
            realm_id=self.realm_id,
            assigned_knight_id=self.assigned_knight_id,
            status=new_status,
            deadline=self.deadline,
            extensions_granted=self.extensions_granted,
            recommendation=self.recommendation,
            rationale=self.rationale,
            created_at=self.created_at,
            completed_at=self.completed_at,
        )

    def with_assignment(self, knight_id: UUID) -> Referral:
        """Create a new referral with Knight assignment.

        Must be in PENDING status. Transitions to ASSIGNED.

        Args:
            knight_id: The Knight's UUID.

        Returns:
            New Referral instance with Knight assigned.

        Raises:
            ValueError: If not in PENDING status.
        """
        if self.status != ReferralStatus.PENDING:
            raise ValueError(
                f"Cannot assign Knight: status must be PENDING, got {self.status.value}"
            )

        return Referral(
            referral_id=self.referral_id,
            petition_id=self.petition_id,
            realm_id=self.realm_id,
            assigned_knight_id=knight_id,
            status=ReferralStatus.ASSIGNED,
            deadline=self.deadline,
            extensions_granted=self.extensions_granted,
            recommendation=None,
            rationale=None,
            created_at=self.created_at,
            completed_at=None,
        )

    def with_extension(self, new_deadline: datetime) -> Referral:
        """Create a new referral with extended deadline.

        Increments extensions_granted and updates deadline.
        Validates that extension is allowed.

        Args:
            new_deadline: The new deadline (must be timezone-aware UTC).

        Returns:
            New Referral instance with extended deadline.

        Raises:
            ValueError: If extension is not allowed or deadline is invalid.
        """
        if not self.can_extend():
            if self.extensions_granted >= self.MAX_EXTENSIONS:
                raise ValueError(
                    f"Cannot extend: max extensions ({self.MAX_EXTENSIONS}) reached"
                )
            raise ValueError(f"Cannot extend: invalid status {self.status.value}")

        if new_deadline.tzinfo is None:
            raise ValueError("new_deadline must be timezone-aware (UTC)")

        if new_deadline <= self.deadline:
            raise ValueError("new_deadline must be after current deadline")

        return Referral(
            referral_id=self.referral_id,
            petition_id=self.petition_id,
            realm_id=self.realm_id,
            assigned_knight_id=self.assigned_knight_id,
            status=self.status,
            deadline=new_deadline,
            extensions_granted=self.extensions_granted + 1,
            recommendation=None,
            rationale=None,
            created_at=self.created_at,
            completed_at=None,
        )

    def with_in_review(self) -> Referral:
        """Create a new referral with IN_REVIEW status.

        Transitions from ASSIGNED to IN_REVIEW.

        Returns:
            New Referral instance with IN_REVIEW status.

        Raises:
            ValueError: If not in ASSIGNED status.
        """
        if self.status != ReferralStatus.ASSIGNED:
            raise ValueError(
                f"Cannot start review: status must be ASSIGNED, got {self.status.value}"
            )

        return Referral(
            referral_id=self.referral_id,
            petition_id=self.petition_id,
            realm_id=self.realm_id,
            assigned_knight_id=self.assigned_knight_id,
            status=ReferralStatus.IN_REVIEW,
            deadline=self.deadline,
            extensions_granted=self.extensions_granted,
            recommendation=None,
            rationale=None,
            created_at=self.created_at,
            completed_at=None,
        )

    def with_recommendation(
        self,
        recommendation: ReferralRecommendation,
        rationale: str,
        completed_at: datetime | None = None,
    ) -> Referral:
        """Create a new referral with Knight's recommendation.

        Completes the referral with the Knight's decision.

        Args:
            recommendation: The Knight's recommendation (ACKNOWLEDGE or ESCALATE).
            rationale: The Knight's rationale (required, must not be empty).
            completed_at: When completed (defaults to now UTC).

        Returns:
            New Referral instance with recommendation recorded.

        Raises:
            ValueError: If recommendation is not allowed.
        """
        if not self.can_submit_recommendation():
            if self.status != ReferralStatus.IN_REVIEW:
                raise ValueError(
                    f"Cannot submit recommendation: status must be IN_REVIEW, "
                    f"got {self.status.value}"
                )
            raise ValueError("Cannot submit recommendation: no Knight assigned")

        if not rationale or not rationale.strip():
            raise ValueError("rationale is required and must not be empty")

        if completed_at is None:
            completed_at = datetime.now(timezone.utc)
        elif completed_at.tzinfo is None:
            raise ValueError("completed_at must be timezone-aware (UTC)")

        return Referral(
            referral_id=self.referral_id,
            petition_id=self.petition_id,
            realm_id=self.realm_id,
            assigned_knight_id=self.assigned_knight_id,
            status=ReferralStatus.COMPLETED,
            deadline=self.deadline,
            extensions_granted=self.extensions_granted,
            recommendation=recommendation,
            rationale=rationale.strip(),
            created_at=self.created_at,
            completed_at=completed_at,
        )

    def with_expired(self) -> Referral:
        """Create a new referral marked as expired.

        Can transition from any non-terminal state.

        Returns:
            New Referral instance with EXPIRED status.

        Raises:
            ValueError: If already in a terminal state.
        """
        if self.status.is_terminal():
            raise ValueError(
                f"Cannot expire: already in terminal state {self.status.value}"
            )

        return Referral(
            referral_id=self.referral_id,
            petition_id=self.petition_id,
            realm_id=self.realm_id,
            assigned_knight_id=self.assigned_knight_id,
            status=ReferralStatus.EXPIRED,
            deadline=self.deadline,
            extensions_granted=self.extensions_granted,
            recommendation=None,
            rationale=None,
            created_at=self.created_at,
            completed_at=datetime.now(timezone.utc),
        )

    @classmethod
    def calculate_default_deadline(
        cls,
        from_time: datetime | None = None,
        cycles: int | None = None,
    ) -> datetime:
        """Calculate the default deadline for a new referral.

        Args:
            from_time: Starting time (defaults to now UTC).
            cycles: Number of cycles (defaults to DEFAULT_DEADLINE_CYCLES).

        Returns:
            The calculated deadline (timezone-aware UTC).
        """
        if from_time is None:
            from_time = datetime.now(timezone.utc)
        if cycles is None:
            cycles = cls.DEFAULT_DEADLINE_CYCLES

        return from_time + (cycles * cls.DEFAULT_CYCLE_DURATION)
