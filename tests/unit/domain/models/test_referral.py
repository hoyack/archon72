"""Unit tests for Referral domain model (Story 4.1).

Tests cover:
- ReferralStatus enum and state transitions
- ReferralRecommendation enum
- Referral dataclass creation and validation
- Domain methods: can_extend, can_submit_recommendation, is_expired
- Immutable with_* methods
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from src.domain.models.referral import (
    Referral,
    ReferralRecommendation,
    ReferralStatus,
)


class TestReferralStatus:
    """Tests for ReferralStatus enum."""

    def test_status_values(self) -> None:
        """Test all status values exist."""
        assert ReferralStatus.PENDING.value == "pending"
        assert ReferralStatus.ASSIGNED.value == "assigned"
        assert ReferralStatus.IN_REVIEW.value == "in_review"
        assert ReferralStatus.COMPLETED.value == "completed"
        assert ReferralStatus.EXPIRED.value == "expired"

    def test_is_terminal(self) -> None:
        """Test is_terminal method."""
        assert not ReferralStatus.PENDING.is_terminal()
        assert not ReferralStatus.ASSIGNED.is_terminal()
        assert not ReferralStatus.IN_REVIEW.is_terminal()
        assert ReferralStatus.COMPLETED.is_terminal()
        assert ReferralStatus.EXPIRED.is_terminal()

    def test_can_transition_to_from_pending(self) -> None:
        """Test valid transitions from PENDING."""
        status = ReferralStatus.PENDING
        assert status.can_transition_to(ReferralStatus.ASSIGNED)
        assert status.can_transition_to(ReferralStatus.EXPIRED)
        assert not status.can_transition_to(ReferralStatus.IN_REVIEW)
        assert not status.can_transition_to(ReferralStatus.COMPLETED)
        assert not status.can_transition_to(ReferralStatus.PENDING)

    def test_can_transition_to_from_assigned(self) -> None:
        """Test valid transitions from ASSIGNED."""
        status = ReferralStatus.ASSIGNED
        assert status.can_transition_to(ReferralStatus.IN_REVIEW)
        assert status.can_transition_to(ReferralStatus.EXPIRED)
        assert not status.can_transition_to(ReferralStatus.PENDING)
        assert not status.can_transition_to(ReferralStatus.ASSIGNED)
        assert not status.can_transition_to(ReferralStatus.COMPLETED)

    def test_can_transition_to_from_in_review(self) -> None:
        """Test valid transitions from IN_REVIEW."""
        status = ReferralStatus.IN_REVIEW
        assert status.can_transition_to(ReferralStatus.COMPLETED)
        assert status.can_transition_to(ReferralStatus.EXPIRED)
        assert not status.can_transition_to(ReferralStatus.PENDING)
        assert not status.can_transition_to(ReferralStatus.ASSIGNED)
        assert not status.can_transition_to(ReferralStatus.IN_REVIEW)

    def test_can_transition_to_from_terminal(self) -> None:
        """Test that terminal states cannot transition."""
        for status in [ReferralStatus.COMPLETED, ReferralStatus.EXPIRED]:
            for target in ReferralStatus:
                assert not status.can_transition_to(target)


class TestReferralRecommendation:
    """Tests for ReferralRecommendation enum."""

    def test_recommendation_values(self) -> None:
        """Test all recommendation values exist."""
        assert ReferralRecommendation.ACKNOWLEDGE.value == "acknowledge"
        assert ReferralRecommendation.ESCALATE.value == "escalate"


class TestReferralCreation:
    """Tests for Referral dataclass creation."""

    @pytest.fixture
    def valid_referral_data(self) -> dict:
        """Fixture for valid referral data."""
        now = datetime.now(timezone.utc)
        return {
            "referral_id": uuid4(),
            "petition_id": uuid4(),
            "realm_id": uuid4(),
            "deadline": now + timedelta(weeks=3),
            "created_at": now,
        }

    def test_create_valid_referral(self, valid_referral_data: dict) -> None:
        """Test creating a valid referral with minimal data."""
        referral = Referral(**valid_referral_data)

        assert referral.referral_id == valid_referral_data["referral_id"]
        assert referral.petition_id == valid_referral_data["petition_id"]
        assert referral.realm_id == valid_referral_data["realm_id"]
        assert referral.deadline == valid_referral_data["deadline"]
        assert referral.created_at == valid_referral_data["created_at"]
        assert referral.status == ReferralStatus.PENDING
        assert referral.assigned_knight_id is None
        assert referral.extensions_granted == 0
        assert referral.recommendation is None
        assert referral.rationale is None
        assert referral.completed_at is None

    def test_create_assigned_referral(self, valid_referral_data: dict) -> None:
        """Test creating an assigned referral."""
        knight_id = uuid4()
        referral = Referral(
            **valid_referral_data,
            assigned_knight_id=knight_id,
            status=ReferralStatus.ASSIGNED,
        )

        assert referral.assigned_knight_id == knight_id
        assert referral.status == ReferralStatus.ASSIGNED

    def test_create_completed_referral(self, valid_referral_data: dict) -> None:
        """Test creating a completed referral."""
        knight_id = uuid4()
        completed_at = datetime.now(timezone.utc)
        referral = Referral(
            **valid_referral_data,
            assigned_knight_id=knight_id,
            status=ReferralStatus.COMPLETED,
            recommendation=ReferralRecommendation.ACKNOWLEDGE,
            rationale="Valid petition, should be acknowledged.",
            completed_at=completed_at,
        )

        assert referral.status == ReferralStatus.COMPLETED
        assert referral.recommendation == ReferralRecommendation.ACKNOWLEDGE
        assert referral.rationale == "Valid petition, should be acknowledged."
        assert referral.completed_at == completed_at


class TestReferralValidation:
    """Tests for Referral field validation."""

    @pytest.fixture
    def valid_referral_data(self) -> dict:
        """Fixture for valid referral data."""
        now = datetime.now(timezone.utc)
        return {
            "referral_id": uuid4(),
            "petition_id": uuid4(),
            "realm_id": uuid4(),
            "deadline": now + timedelta(weeks=3),
            "created_at": now,
        }

    def test_invalid_extensions_negative(self, valid_referral_data: dict) -> None:
        """Test that negative extensions_granted is rejected."""
        with pytest.raises(ValueError, match="extensions_granted must be 0-2"):
            Referral(**valid_referral_data, extensions_granted=-1)

    def test_invalid_extensions_exceeds_max(self, valid_referral_data: dict) -> None:
        """Test that extensions_granted > 2 is rejected."""
        with pytest.raises(ValueError, match="extensions_granted must be 0-2"):
            Referral(**valid_referral_data, extensions_granted=3)

    def test_invalid_deadline_not_timezone_aware(
        self, valid_referral_data: dict
    ) -> None:
        """Test that naive deadline is rejected."""
        valid_referral_data["deadline"] = datetime.now()  # No timezone
        with pytest.raises(ValueError, match="deadline must be timezone-aware"):
            Referral(**valid_referral_data)

    def test_invalid_created_at_not_timezone_aware(
        self, valid_referral_data: dict
    ) -> None:
        """Test that naive created_at is rejected."""
        valid_referral_data["created_at"] = datetime.now()  # No timezone
        with pytest.raises(ValueError, match="created_at must be timezone-aware"):
            Referral(**valid_referral_data)

    def test_invalid_completed_at_not_timezone_aware(
        self, valid_referral_data: dict
    ) -> None:
        """Test that naive completed_at is rejected."""
        with pytest.raises(ValueError, match="completed_at must be timezone-aware"):
            Referral(
                **valid_referral_data,
                assigned_knight_id=uuid4(),
                status=ReferralStatus.COMPLETED,
                recommendation=ReferralRecommendation.ACKNOWLEDGE,
                rationale="Test",
                completed_at=datetime.now(),  # No timezone
            )

    def test_invalid_recommendation_without_completed_status(
        self, valid_referral_data: dict
    ) -> None:
        """Test that recommendation without COMPLETED status is rejected."""
        with pytest.raises(
            ValueError, match="recommendation can only be set when status is COMPLETED"
        ):
            Referral(
                **valid_referral_data,
                assigned_knight_id=uuid4(),
                status=ReferralStatus.IN_REVIEW,
                recommendation=ReferralRecommendation.ACKNOWLEDGE,
                rationale="Test",
            )

    def test_invalid_recommendation_without_rationale(
        self, valid_referral_data: dict
    ) -> None:
        """Test that recommendation without rationale is rejected."""
        with pytest.raises(ValueError, match="recommendation requires rationale"):
            Referral(
                **valid_referral_data,
                assigned_knight_id=uuid4(),
                status=ReferralStatus.COMPLETED,
                recommendation=ReferralRecommendation.ACKNOWLEDGE,
                rationale=None,
                completed_at=datetime.now(timezone.utc),
            )

    def test_invalid_completed_without_recommendation(
        self, valid_referral_data: dict
    ) -> None:
        """Test that COMPLETED status without recommendation is rejected."""
        with pytest.raises(
            ValueError, match="COMPLETED status requires recommendation"
        ):
            Referral(
                **valid_referral_data,
                assigned_knight_id=uuid4(),
                status=ReferralStatus.COMPLETED,
                recommendation=None,
                completed_at=datetime.now(timezone.utc),
            )

    def test_invalid_completed_without_completed_at(
        self, valid_referral_data: dict
    ) -> None:
        """Test that COMPLETED status without completed_at is rejected."""
        with pytest.raises(ValueError, match="COMPLETED status requires completed_at"):
            Referral(
                **valid_referral_data,
                assigned_knight_id=uuid4(),
                status=ReferralStatus.COMPLETED,
                recommendation=ReferralRecommendation.ACKNOWLEDGE,
                rationale="Test",
                completed_at=None,
            )

    def test_invalid_assigned_without_knight(self, valid_referral_data: dict) -> None:
        """Test that ASSIGNED status without knight is rejected."""
        with pytest.raises(
            ValueError, match="assigned_knight_id required for status assigned"
        ):
            Referral(
                **valid_referral_data,
                status=ReferralStatus.ASSIGNED,
                assigned_knight_id=None,
            )

    def test_invalid_in_review_without_knight(self, valid_referral_data: dict) -> None:
        """Test that IN_REVIEW status without knight is rejected."""
        with pytest.raises(
            ValueError, match="assigned_knight_id required for status in_review"
        ):
            Referral(
                **valid_referral_data,
                status=ReferralStatus.IN_REVIEW,
                assigned_knight_id=None,
            )


class TestReferralCanExtend:
    """Tests for can_extend method."""

    @pytest.fixture
    def base_referral(self) -> Referral:
        """Fixture for base referral."""
        now = datetime.now(timezone.utc)
        return Referral(
            referral_id=uuid4(),
            petition_id=uuid4(),
            realm_id=uuid4(),
            deadline=now + timedelta(weeks=3),
            created_at=now,
        )

    def test_can_extend_assigned_with_no_extensions(
        self, base_referral: Referral
    ) -> None:
        """Test can_extend returns True for ASSIGNED with 0 extensions."""
        assigned = base_referral.with_assignment(uuid4())
        assert assigned.can_extend()

    def test_can_extend_assigned_with_one_extension(
        self, base_referral: Referral
    ) -> None:
        """Test can_extend returns True for ASSIGNED with 1 extension."""
        assigned = base_referral.with_assignment(uuid4())
        extended = assigned.with_extension(assigned.deadline + timedelta(weeks=1))
        assert extended.can_extend()

    def test_cannot_extend_assigned_with_max_extensions(
        self, base_referral: Referral
    ) -> None:
        """Test can_extend returns False for ASSIGNED with 2 extensions."""
        assigned = base_referral.with_assignment(uuid4())
        extended1 = assigned.with_extension(assigned.deadline + timedelta(weeks=1))
        extended2 = extended1.with_extension(extended1.deadline + timedelta(weeks=1))
        assert not extended2.can_extend()

    def test_can_extend_in_review(self, base_referral: Referral) -> None:
        """Test can_extend returns True for IN_REVIEW."""
        assigned = base_referral.with_assignment(uuid4())
        in_review = assigned.with_in_review()
        assert in_review.can_extend()

    def test_cannot_extend_pending(self, base_referral: Referral) -> None:
        """Test can_extend returns False for PENDING."""
        assert not base_referral.can_extend()

    def test_cannot_extend_completed(self, base_referral: Referral) -> None:
        """Test can_extend returns False for COMPLETED."""
        assigned = base_referral.with_assignment(uuid4())
        in_review = assigned.with_in_review()
        completed = in_review.with_recommendation(
            ReferralRecommendation.ACKNOWLEDGE,
            "Valid petition.",
        )
        assert not completed.can_extend()


class TestReferralCanSubmitRecommendation:
    """Tests for can_submit_recommendation method."""

    @pytest.fixture
    def base_referral(self) -> Referral:
        """Fixture for base referral."""
        now = datetime.now(timezone.utc)
        return Referral(
            referral_id=uuid4(),
            petition_id=uuid4(),
            realm_id=uuid4(),
            deadline=now + timedelta(weeks=3),
            created_at=now,
        )

    def test_can_submit_in_review(self, base_referral: Referral) -> None:
        """Test can_submit_recommendation returns True for IN_REVIEW."""
        assigned = base_referral.with_assignment(uuid4())
        in_review = assigned.with_in_review()
        assert in_review.can_submit_recommendation()

    def test_cannot_submit_pending(self, base_referral: Referral) -> None:
        """Test can_submit_recommendation returns False for PENDING."""
        assert not base_referral.can_submit_recommendation()

    def test_cannot_submit_assigned(self, base_referral: Referral) -> None:
        """Test can_submit_recommendation returns False for ASSIGNED."""
        assigned = base_referral.with_assignment(uuid4())
        assert not assigned.can_submit_recommendation()


class TestReferralIsExpired:
    """Tests for is_expired method."""

    @pytest.fixture
    def base_referral(self) -> Referral:
        """Fixture for base referral."""
        now = datetime.now(timezone.utc)
        return Referral(
            referral_id=uuid4(),
            petition_id=uuid4(),
            realm_id=uuid4(),
            deadline=now + timedelta(weeks=3),
            created_at=now,
        )

    def test_is_expired_status_expired(self, base_referral: Referral) -> None:
        """Test is_expired returns True when status is EXPIRED."""
        expired = base_referral.with_expired()
        assert expired.is_expired()

    def test_is_not_expired_pending_before_deadline(
        self, base_referral: Referral
    ) -> None:
        """Test is_expired returns False before deadline."""
        assert not base_referral.is_expired()

    def test_is_expired_pending_after_deadline(self) -> None:
        """Test is_expired returns True after deadline passes."""
        now = datetime.now(timezone.utc)
        past_deadline = now - timedelta(hours=1)
        referral = Referral(
            referral_id=uuid4(),
            petition_id=uuid4(),
            realm_id=uuid4(),
            deadline=past_deadline,
            created_at=now - timedelta(weeks=3),
        )
        assert referral.is_expired()

    def test_is_not_expired_completed(self, base_referral: Referral) -> None:
        """Test is_expired returns False when COMPLETED."""
        assigned = base_referral.with_assignment(uuid4())
        in_review = assigned.with_in_review()
        completed = in_review.with_recommendation(
            ReferralRecommendation.ACKNOWLEDGE,
            "Valid petition.",
        )
        assert not completed.is_expired()


class TestReferralWithStatus:
    """Tests for with_status method."""

    @pytest.fixture
    def base_referral(self) -> Referral:
        """Fixture for base referral."""
        now = datetime.now(timezone.utc)
        return Referral(
            referral_id=uuid4(),
            petition_id=uuid4(),
            realm_id=uuid4(),
            deadline=now + timedelta(weeks=3),
            created_at=now,
        )

    def test_with_status_valid_transition(self, base_referral: Referral) -> None:
        """Test with_status for valid transition."""
        # PENDING -> EXPIRED is valid
        expired = base_referral.with_status(ReferralStatus.EXPIRED)
        assert expired.status == ReferralStatus.EXPIRED
        assert expired.referral_id == base_referral.referral_id

    def test_with_status_invalid_transition(self, base_referral: Referral) -> None:
        """Test with_status rejects invalid transition."""
        with pytest.raises(ValueError, match="Invalid state transition"):
            base_referral.with_status(ReferralStatus.COMPLETED)

    def test_with_status_returns_new_instance(self, base_referral: Referral) -> None:
        """Test with_status returns a new instance."""
        expired = base_referral.with_status(ReferralStatus.EXPIRED)
        assert expired is not base_referral


class TestReferralWithAssignment:
    """Tests for with_assignment method."""

    @pytest.fixture
    def base_referral(self) -> Referral:
        """Fixture for base referral."""
        now = datetime.now(timezone.utc)
        return Referral(
            referral_id=uuid4(),
            petition_id=uuid4(),
            realm_id=uuid4(),
            deadline=now + timedelta(weeks=3),
            created_at=now,
        )

    def test_with_assignment_valid(self, base_referral: Referral) -> None:
        """Test with_assignment from PENDING."""
        knight_id = uuid4()
        assigned = base_referral.with_assignment(knight_id)

        assert assigned.assigned_knight_id == knight_id
        assert assigned.status == ReferralStatus.ASSIGNED
        assert assigned.referral_id == base_referral.referral_id

    def test_with_assignment_invalid_status(self, base_referral: Referral) -> None:
        """Test with_assignment rejects non-PENDING status."""
        knight_id = uuid4()
        assigned = base_referral.with_assignment(knight_id)

        with pytest.raises(ValueError, match="status must be PENDING"):
            assigned.with_assignment(uuid4())

    def test_with_assignment_returns_new_instance(
        self, base_referral: Referral
    ) -> None:
        """Test with_assignment returns a new instance."""
        assigned = base_referral.with_assignment(uuid4())
        assert assigned is not base_referral


class TestReferralWithExtension:
    """Tests for with_extension method."""

    @pytest.fixture
    def assigned_referral(self) -> Referral:
        """Fixture for assigned referral."""
        now = datetime.now(timezone.utc)
        base = Referral(
            referral_id=uuid4(),
            petition_id=uuid4(),
            realm_id=uuid4(),
            deadline=now + timedelta(weeks=3),
            created_at=now,
        )
        return base.with_assignment(uuid4())

    def test_with_extension_valid(self, assigned_referral: Referral) -> None:
        """Test with_extension from ASSIGNED."""
        new_deadline = assigned_referral.deadline + timedelta(weeks=1)
        extended = assigned_referral.with_extension(new_deadline)

        assert extended.deadline == new_deadline
        assert extended.extensions_granted == 1
        assert extended.status == ReferralStatus.ASSIGNED

    def test_with_extension_second_extension(self, assigned_referral: Referral) -> None:
        """Test second extension."""
        first_deadline = assigned_referral.deadline + timedelta(weeks=1)
        extended1 = assigned_referral.with_extension(first_deadline)

        second_deadline = extended1.deadline + timedelta(weeks=1)
        extended2 = extended1.with_extension(second_deadline)

        assert extended2.extensions_granted == 2
        assert extended2.deadline == second_deadline

    def test_with_extension_max_reached(self, assigned_referral: Referral) -> None:
        """Test with_extension rejects when max extensions reached."""
        deadline1 = assigned_referral.deadline + timedelta(weeks=1)
        extended1 = assigned_referral.with_extension(deadline1)

        deadline2 = extended1.deadline + timedelta(weeks=1)
        extended2 = extended1.with_extension(deadline2)

        with pytest.raises(ValueError, match="max extensions"):
            extended2.with_extension(extended2.deadline + timedelta(weeks=1))

    def test_with_extension_invalid_status(self) -> None:
        """Test with_extension rejects invalid status."""
        now = datetime.now(timezone.utc)
        pending = Referral(
            referral_id=uuid4(),
            petition_id=uuid4(),
            realm_id=uuid4(),
            deadline=now + timedelta(weeks=3),
            created_at=now,
        )

        with pytest.raises(ValueError, match="invalid status"):
            pending.with_extension(pending.deadline + timedelta(weeks=1))

    def test_with_extension_deadline_not_after_current(
        self, assigned_referral: Referral
    ) -> None:
        """Test with_extension rejects deadline not after current."""
        with pytest.raises(ValueError, match="must be after current deadline"):
            assigned_referral.with_extension(
                assigned_referral.deadline - timedelta(days=1)
            )

    def test_with_extension_naive_deadline(self, assigned_referral: Referral) -> None:
        """Test with_extension rejects naive datetime."""
        naive_deadline = datetime.now() + timedelta(weeks=4)
        with pytest.raises(ValueError, match="must be timezone-aware"):
            assigned_referral.with_extension(naive_deadline)


class TestReferralWithInReview:
    """Tests for with_in_review method."""

    @pytest.fixture
    def assigned_referral(self) -> Referral:
        """Fixture for assigned referral."""
        now = datetime.now(timezone.utc)
        base = Referral(
            referral_id=uuid4(),
            petition_id=uuid4(),
            realm_id=uuid4(),
            deadline=now + timedelta(weeks=3),
            created_at=now,
        )
        return base.with_assignment(uuid4())

    def test_with_in_review_valid(self, assigned_referral: Referral) -> None:
        """Test with_in_review from ASSIGNED."""
        in_review = assigned_referral.with_in_review()

        assert in_review.status == ReferralStatus.IN_REVIEW
        assert in_review.assigned_knight_id == assigned_referral.assigned_knight_id

    def test_with_in_review_invalid_status(self) -> None:
        """Test with_in_review rejects non-ASSIGNED status."""
        now = datetime.now(timezone.utc)
        pending = Referral(
            referral_id=uuid4(),
            petition_id=uuid4(),
            realm_id=uuid4(),
            deadline=now + timedelta(weeks=3),
            created_at=now,
        )

        with pytest.raises(ValueError, match="status must be ASSIGNED"):
            pending.with_in_review()


class TestReferralWithRecommendation:
    """Tests for with_recommendation method."""

    @pytest.fixture
    def in_review_referral(self) -> Referral:
        """Fixture for in_review referral."""
        now = datetime.now(timezone.utc)
        base = Referral(
            referral_id=uuid4(),
            petition_id=uuid4(),
            realm_id=uuid4(),
            deadline=now + timedelta(weeks=3),
            created_at=now,
        )
        assigned = base.with_assignment(uuid4())
        return assigned.with_in_review()

    def test_with_recommendation_acknowledge(
        self, in_review_referral: Referral
    ) -> None:
        """Test with_recommendation for ACKNOWLEDGE."""
        completed = in_review_referral.with_recommendation(
            ReferralRecommendation.ACKNOWLEDGE,
            "Valid petition, merits acknowledgment.",
        )

        assert completed.status == ReferralStatus.COMPLETED
        assert completed.recommendation == ReferralRecommendation.ACKNOWLEDGE
        assert completed.rationale == "Valid petition, merits acknowledgment."
        assert completed.completed_at is not None

    def test_with_recommendation_escalate(self, in_review_referral: Referral) -> None:
        """Test with_recommendation for ESCALATE."""
        completed = in_review_referral.with_recommendation(
            ReferralRecommendation.ESCALATE,
            "Complex matter requiring King's attention.",
        )

        assert completed.status == ReferralStatus.COMPLETED
        assert completed.recommendation == ReferralRecommendation.ESCALATE
        assert completed.rationale == "Complex matter requiring King's attention."

    def test_with_recommendation_custom_completed_at(
        self, in_review_referral: Referral
    ) -> None:
        """Test with_recommendation with custom completed_at."""
        custom_time = datetime.now(timezone.utc) - timedelta(hours=1)
        completed = in_review_referral.with_recommendation(
            ReferralRecommendation.ACKNOWLEDGE,
            "Test rationale.",
            completed_at=custom_time,
        )

        assert completed.completed_at == custom_time

    def test_with_recommendation_invalid_status(self) -> None:
        """Test with_recommendation rejects non-IN_REVIEW status."""
        now = datetime.now(timezone.utc)
        base = Referral(
            referral_id=uuid4(),
            petition_id=uuid4(),
            realm_id=uuid4(),
            deadline=now + timedelta(weeks=3),
            created_at=now,
        )
        assigned = base.with_assignment(uuid4())

        with pytest.raises(ValueError, match="status must be IN_REVIEW"):
            assigned.with_recommendation(
                ReferralRecommendation.ACKNOWLEDGE,
                "Test rationale.",
            )

    def test_with_recommendation_empty_rationale(
        self, in_review_referral: Referral
    ) -> None:
        """Test with_recommendation rejects empty rationale."""
        with pytest.raises(ValueError, match="rationale is required"):
            in_review_referral.with_recommendation(
                ReferralRecommendation.ACKNOWLEDGE,
                "",
            )

    def test_with_recommendation_whitespace_rationale(
        self, in_review_referral: Referral
    ) -> None:
        """Test with_recommendation rejects whitespace-only rationale."""
        with pytest.raises(ValueError, match="rationale is required"):
            in_review_referral.with_recommendation(
                ReferralRecommendation.ACKNOWLEDGE,
                "   ",
            )

    def test_with_recommendation_trims_rationale(
        self, in_review_referral: Referral
    ) -> None:
        """Test with_recommendation trims whitespace from rationale."""
        completed = in_review_referral.with_recommendation(
            ReferralRecommendation.ACKNOWLEDGE,
            "  Valid rationale.  ",
        )

        assert completed.rationale == "Valid rationale."


class TestReferralWithExpired:
    """Tests for with_expired method."""

    @pytest.fixture
    def base_referral(self) -> Referral:
        """Fixture for base referral."""
        now = datetime.now(timezone.utc)
        return Referral(
            referral_id=uuid4(),
            petition_id=uuid4(),
            realm_id=uuid4(),
            deadline=now + timedelta(weeks=3),
            created_at=now,
        )

    def test_with_expired_from_pending(self, base_referral: Referral) -> None:
        """Test with_expired from PENDING."""
        expired = base_referral.with_expired()

        assert expired.status == ReferralStatus.EXPIRED
        assert expired.completed_at is not None

    def test_with_expired_from_assigned(self, base_referral: Referral) -> None:
        """Test with_expired from ASSIGNED."""
        assigned = base_referral.with_assignment(uuid4())
        expired = assigned.with_expired()

        assert expired.status == ReferralStatus.EXPIRED

    def test_with_expired_from_in_review(self, base_referral: Referral) -> None:
        """Test with_expired from IN_REVIEW."""
        assigned = base_referral.with_assignment(uuid4())
        in_review = assigned.with_in_review()
        expired = in_review.with_expired()

        assert expired.status == ReferralStatus.EXPIRED

    def test_with_expired_from_completed_rejected(
        self, base_referral: Referral
    ) -> None:
        """Test with_expired rejects from COMPLETED."""
        assigned = base_referral.with_assignment(uuid4())
        in_review = assigned.with_in_review()
        completed = in_review.with_recommendation(
            ReferralRecommendation.ACKNOWLEDGE,
            "Valid petition.",
        )

        with pytest.raises(ValueError, match="already in terminal state"):
            completed.with_expired()

    def test_with_expired_from_expired_rejected(self, base_referral: Referral) -> None:
        """Test with_expired rejects from EXPIRED."""
        expired = base_referral.with_expired()

        with pytest.raises(ValueError, match="already in terminal state"):
            expired.with_expired()


class TestReferralCalculateDefaultDeadline:
    """Tests for calculate_default_deadline class method."""

    def test_calculate_default_deadline_default_params(self) -> None:
        """Test calculate_default_deadline with defaults."""
        before = datetime.now(timezone.utc)
        deadline = Referral.calculate_default_deadline()
        after = datetime.now(timezone.utc)

        # Should be ~3 weeks from now
        expected_min = before + (3 * timedelta(weeks=1))
        expected_max = after + (3 * timedelta(weeks=1))

        assert expected_min <= deadline <= expected_max

    def test_calculate_default_deadline_custom_from_time(self) -> None:
        """Test calculate_default_deadline with custom from_time."""
        from_time = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        deadline = Referral.calculate_default_deadline(from_time=from_time)

        expected = from_time + (3 * timedelta(weeks=1))
        assert deadline == expected

    def test_calculate_default_deadline_custom_cycles(self) -> None:
        """Test calculate_default_deadline with custom cycles."""
        from_time = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        deadline = Referral.calculate_default_deadline(from_time=from_time, cycles=5)

        expected = from_time + (5 * timedelta(weeks=1))
        assert deadline == expected


class TestReferralImmutability:
    """Tests to verify Referral immutability."""

    @pytest.fixture
    def base_referral(self) -> Referral:
        """Fixture for base referral."""
        now = datetime.now(timezone.utc)
        return Referral(
            referral_id=uuid4(),
            petition_id=uuid4(),
            realm_id=uuid4(),
            deadline=now + timedelta(weeks=3),
            created_at=now,
        )

    def test_referral_is_frozen(self, base_referral: Referral) -> None:
        """Test that Referral is frozen (immutable)."""
        with pytest.raises(AttributeError):
            base_referral.status = ReferralStatus.ASSIGNED  # type: ignore

    def test_with_methods_return_new_instances(self, base_referral: Referral) -> None:
        """Test that all with_* methods return new instances."""
        # with_assignment
        assigned = base_referral.with_assignment(uuid4())
        assert assigned is not base_referral

        # with_in_review
        in_review = assigned.with_in_review()
        assert in_review is not assigned

        # with_extension
        extended = in_review.with_extension(in_review.deadline + timedelta(weeks=1))
        assert extended is not in_review

        # with_recommendation
        completed = in_review.with_recommendation(
            ReferralRecommendation.ACKNOWLEDGE,
            "Test rationale.",
        )
        assert completed is not in_review

        # with_expired
        expired = base_referral.with_expired()
        assert expired is not base_referral

        # with_status
        expired2 = base_referral.with_status(ReferralStatus.EXPIRED)
        assert expired2 is not base_referral
