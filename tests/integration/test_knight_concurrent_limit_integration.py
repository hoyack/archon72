"""Integration tests for Knight concurrent referral limit (Story 4.7, FR-4.7, NFR-7.3).

Tests end-to-end Knight concurrent limit enforcement using stubs including:
- Eligibility checking with real realm capacity
- Assignment flow with workload tracking
- Deferral when all Knights at capacity
- Re-eligibility after workload decrease

Constitutional Constraints:
- FR-4.7: System SHALL enforce max concurrent referrals per Knight
- NFR-7.3: Referral load balancing - max concurrent per Knight configurable
- CT-12: Every action that affects an Archon must be witnessed
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from src.application.ports.knight_concurrent_limit import (
    AssignmentResult,
    KnightEligibilityResult,
)
from src.domain.errors.knight_concurrent_limit import (
    KnightNotFoundError,
    KnightNotInRealmError,
    ReferralAlreadyAssignedError,
)
from src.domain.models.realm import Realm, RealmStatus
from src.domain.models.referral import Referral, ReferralStatus
from src.infrastructure.stubs.knight_concurrent_limit_stub import (
    KnightConcurrentLimitStub,
)
from src.infrastructure.stubs.knight_registry_stub import KnightRegistryStub
from src.infrastructure.stubs.realm_registry_stub import RealmRegistryStub
from src.infrastructure.stubs.referral_repository_stub import ReferralRepositoryStub


# ═══════════════════════════════════════════════════════════════════════════════
# TEST FIXTURES
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def referral_repo():
    """Create referral repository stub."""
    return ReferralRepositoryStub()


@pytest.fixture
def knight_registry():
    """Create Knight registry stub."""
    return KnightRegistryStub()


@pytest.fixture
def realm_registry():
    """Create realm registry stub."""
    return RealmRegistryStub()


@pytest.fixture
def service(referral_repo, knight_registry, realm_registry):
    """Create KnightConcurrentLimitStub with all stubs."""
    return KnightConcurrentLimitStub(
        referral_repo=referral_repo,
        knight_registry=knight_registry,
        realm_registry=realm_registry,
    )


@pytest.fixture
def test_realm(realm_registry):
    """Create and register a test realm with capacity=2."""
    realm = Realm(
        id=uuid4(),
        name="test_integration_realm",
        display_name="Test Integration Realm",
        knight_capacity=2,
        status=RealmStatus.ACTIVE,
    )
    realm_registry.add_realm(realm)
    return realm


@pytest.fixture
def test_knights(knight_registry, test_realm):
    """Create and register 3 test Knights."""
    knights = [uuid4() for _ in range(3)]
    for knight in knights:
        knight_registry.add_knight(knight, test_realm.id)
    return knights


def create_referral(petition_id: None = None, realm_id: None = None) -> Referral:
    """Helper to create a PENDING referral."""
    now = datetime.now(timezone.utc)
    return Referral(
        referral_id=uuid4(),
        petition_id=petition_id or uuid4(),
        realm_id=realm_id or uuid4(),
        deadline=now + timedelta(weeks=3),
        created_at=now,
        status=ReferralStatus.PENDING,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# ELIGIBILITY CHECK INTEGRATION TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestEligibilityCheckIntegration:
    """Integration tests for Knight eligibility checking."""

    async def test_knight_eligible_with_no_referrals(
        self, service, test_realm, test_knights
    ):
        """Knight with no active referrals is eligible."""
        result = await service.check_knight_eligibility(
            test_knights[0], test_realm.id
        )

        assert result.is_eligible is True
        assert result.current_count == 0
        assert result.max_allowed == 2

    async def test_knight_eligible_below_capacity(
        self, service, referral_repo, test_realm, test_knights
    ):
        """Knight below capacity is eligible."""
        # Give Knight 1 referral (capacity is 2)
        referral = create_referral(realm_id=test_realm.id)
        referral = referral.with_assignment(test_knights[0])
        await referral_repo.save(referral)

        result = await service.check_knight_eligibility(
            test_knights[0], test_realm.id
        )

        assert result.is_eligible is True
        assert result.current_count == 1
        assert result.max_allowed == 2

    async def test_knight_not_eligible_at_capacity(
        self, service, referral_repo, test_realm, test_knights
    ):
        """Knight at capacity is not eligible."""
        # Give Knight 2 referrals (at capacity)
        for i in range(2):
            referral = create_referral(realm_id=test_realm.id)
            referral = referral.with_assignment(test_knights[0])
            await referral_repo.save(referral)

        result = await service.check_knight_eligibility(
            test_knights[0], test_realm.id
        )

        assert result.is_eligible is False
        assert result.current_count == 2
        assert result.max_allowed == 2
        assert "capacity" in result.reason.lower()

    async def test_invalid_knight_raises_error(self, service, test_realm):
        """Invalid Knight ID raises KnightNotFoundError."""
        invalid_knight = uuid4()

        with pytest.raises(KnightNotFoundError):
            await service.check_knight_eligibility(invalid_knight, test_realm.id)

    async def test_knight_in_wrong_realm_raises_error(
        self, service, knight_registry, test_realm
    ):
        """Knight in different realm raises KnightNotInRealmError."""
        # Create Knight in different realm
        other_realm = uuid4()
        knight = uuid4()
        knight_registry.add_knight(knight, other_realm)

        with pytest.raises(KnightNotInRealmError):
            await service.check_knight_eligibility(knight, test_realm.id)


# ═══════════════════════════════════════════════════════════════════════════════
# FIND ELIGIBLE KNIGHTS INTEGRATION TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestFindEligibleKnightsIntegration:
    """Integration tests for finding eligible Knights."""

    async def test_finds_all_eligible_knights(self, service, test_realm, test_knights):
        """Finds all eligible Knights when none have referrals."""
        result = await service.find_eligible_knights(test_realm.id)

        assert len(result) == 3
        assert set(result) == set(test_knights)

    async def test_excludes_knights_at_capacity(
        self, service, referral_repo, test_realm, test_knights
    ):
        """Excludes Knights who are at capacity."""
        # Put knight[0] at capacity
        for i in range(2):
            referral = create_referral(realm_id=test_realm.id)
            referral = referral.with_assignment(test_knights[0])
            await referral_repo.save(referral)

        result = await service.find_eligible_knights(test_realm.id)

        assert len(result) == 2
        assert test_knights[0] not in result
        assert test_knights[1] in result
        assert test_knights[2] in result

    async def test_sorts_by_workload_ascending(
        self, service, referral_repo, test_realm, test_knights
    ):
        """Returns Knights sorted by workload (least loaded first)."""
        # knight[0]: 1 referral
        ref1 = create_referral(realm_id=test_realm.id)
        ref1 = ref1.with_assignment(test_knights[0])
        await referral_repo.save(ref1)

        # knight[1]: 0 referrals (least loaded)
        # knight[2]: 1 referral
        ref2 = create_referral(realm_id=test_realm.id)
        ref2 = ref2.with_assignment(test_knights[2])
        await referral_repo.save(ref2)

        result = await service.find_eligible_knights(test_realm.id)

        assert result[0] == test_knights[1]  # 0 referrals - first

    async def test_returns_empty_when_all_at_capacity(
        self, service, referral_repo, test_realm, test_knights
    ):
        """Returns empty list when all Knights at capacity."""
        # Put all Knights at capacity
        for knight in test_knights:
            for i in range(2):
                referral = create_referral(realm_id=test_realm.id)
                referral = referral.with_assignment(knight)
                await referral_repo.save(referral)

        result = await service.find_eligible_knights(test_realm.id)

        assert len(result) == 0


# ═══════════════════════════════════════════════════════════════════════════════
# ASSIGNMENT INTEGRATION TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestAssignmentIntegration:
    """Integration tests for referral assignment."""

    async def test_assigns_to_least_loaded_knight(
        self, service, referral_repo, test_realm, test_knights
    ):
        """Assigns referral to Knight with lowest workload."""
        # Give knight[0] 1 referral, knight[1] 0
        ref = create_referral(realm_id=test_realm.id)
        ref = ref.with_assignment(test_knights[0])
        await referral_repo.save(ref)

        # Create new referral for assignment
        new_referral = create_referral(realm_id=test_realm.id)
        await referral_repo.save(new_referral)

        result = await service.assign_to_eligible_knight(
            referral_id=new_referral.referral_id,
            realm_id=test_realm.id,
        )

        assert result.success is True
        # Should be assigned to knight[1] (0 referrals) or knight[2] (0 referrals)
        assert result.assigned_knight_id in [test_knights[1], test_knights[2]]

    async def test_uses_preferred_knight_when_eligible(
        self, service, referral_repo, test_realm, test_knights
    ):
        """Uses preferred Knight when they are eligible."""
        referral = create_referral(realm_id=test_realm.id)
        await referral_repo.save(referral)

        result = await service.assign_to_eligible_knight(
            referral_id=referral.referral_id,
            realm_id=test_realm.id,
            preferred_knight_id=test_knights[2],
        )

        assert result.success is True
        assert result.assigned_knight_id == test_knights[2]

    async def test_ignores_preferred_when_at_capacity(
        self, service, referral_repo, test_realm, test_knights
    ):
        """Falls back when preferred Knight is at capacity."""
        # Put preferred at capacity
        for i in range(2):
            ref = create_referral(realm_id=test_realm.id)
            ref = ref.with_assignment(test_knights[2])
            await referral_repo.save(ref)

        referral = create_referral(realm_id=test_realm.id)
        await referral_repo.save(referral)

        result = await service.assign_to_eligible_knight(
            referral_id=referral.referral_id,
            realm_id=test_realm.id,
            preferred_knight_id=test_knights[2],
        )

        assert result.success is True
        assert result.assigned_knight_id != test_knights[2]

    async def test_defers_when_all_at_capacity(
        self, service, referral_repo, test_realm, test_knights
    ):
        """Defers assignment when all Knights at capacity."""
        # Put all Knights at capacity
        for knight in test_knights:
            for i in range(2):
                ref = create_referral(realm_id=test_realm.id)
                ref = ref.with_assignment(knight)
                await referral_repo.save(ref)

        referral = create_referral(realm_id=test_realm.id)
        await referral_repo.save(referral)

        result = await service.assign_to_eligible_knight(
            referral_id=referral.referral_id,
            realm_id=test_realm.id,
        )

        assert result.success is False
        assert result.all_knights_at_capacity is True
        assert "capacity" in result.deferred_reason.lower()

    async def test_referral_status_updated_on_assignment(
        self, service, referral_repo, test_realm, test_knights
    ):
        """Referral transitions to ASSIGNED on successful assignment."""
        referral = create_referral(realm_id=test_realm.id)
        await referral_repo.save(referral)

        result = await service.assign_to_eligible_knight(
            referral_id=referral.referral_id,
            realm_id=test_realm.id,
        )

        assert result.success is True
        assert result.referral.status == ReferralStatus.ASSIGNED
        assert result.referral.assigned_knight_id is not None

    async def test_cannot_reassign_already_assigned_referral(
        self, service, referral_repo, test_realm, test_knights
    ):
        """Cannot assign a referral that's already assigned."""
        referral = create_referral(realm_id=test_realm.id)
        referral = referral.with_assignment(test_knights[0])
        await referral_repo.save(referral)

        with pytest.raises(ReferralAlreadyAssignedError):
            await service.assign_to_eligible_knight(
                referral_id=referral.referral_id,
                realm_id=test_realm.id,
            )


# ═══════════════════════════════════════════════════════════════════════════════
# WORKLOAD TRACKING INTEGRATION TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestWorkloadTrackingIntegration:
    """Integration tests for workload tracking."""

    async def test_get_knight_workload_accurate(
        self, service, referral_repo, test_realm, test_knights
    ):
        """Workload count is accurate."""
        # Add 2 active referrals
        for i in range(2):
            ref = create_referral(realm_id=test_realm.id)
            ref = ref.with_assignment(test_knights[0])
            await referral_repo.save(ref)

        workload = await service.get_knight_workload(test_knights[0])

        assert workload == 2

    async def test_get_realm_workload_summary(
        self, service, referral_repo, test_realm, test_knights
    ):
        """Realm workload summary is accurate."""
        # knight[0]: 2 referrals
        for i in range(2):
            ref = create_referral(realm_id=test_realm.id)
            ref = ref.with_assignment(test_knights[0])
            await referral_repo.save(ref)

        # knight[1]: 1 referral
        ref = create_referral(realm_id=test_realm.id)
        ref = ref.with_assignment(test_knights[1])
        await referral_repo.save(ref)

        # knight[2]: 0 referrals

        summary = await service.get_realm_workload_summary(test_realm.id)

        assert summary[test_knights[0]] == 2
        assert summary[test_knights[1]] == 1
        assert summary[test_knights[2]] == 0


# ═══════════════════════════════════════════════════════════════════════════════
# RE-ELIGIBILITY INTEGRATION TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestReEligibilityIntegration:
    """Integration tests for Knight re-eligibility after workload changes."""

    async def test_knight_becomes_eligible_after_completion(
        self, service, referral_repo, test_realm, test_knights
    ):
        """Knight becomes eligible when their workload decreases."""
        # Put knight at capacity
        refs = []
        for i in range(2):
            ref = create_referral(realm_id=test_realm.id)
            ref = ref.with_assignment(test_knights[0])
            await referral_repo.save(ref)
            refs.append(ref)

        # Verify at capacity
        result = await service.check_knight_eligibility(
            test_knights[0], test_realm.id
        )
        assert result.is_eligible is False

        # Complete one referral (simulate by transitioning to COMPLETED)
        completed = refs[0].with_in_review().with_recommendation(
            recommendation=__import__("src.domain.models.referral", fromlist=["ReferralRecommendation"]).ReferralRecommendation.ACKNOWLEDGE,
            rationale="Test completion",
        )
        await referral_repo.update(completed)

        # Now Knight should be eligible again
        result = await service.check_knight_eligibility(
            test_knights[0], test_realm.id
        )
        assert result.is_eligible is True
        assert result.current_count == 1


# ═══════════════════════════════════════════════════════════════════════════════
# FAIR DISTRIBUTION INTEGRATION TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestFairDistributionIntegration:
    """Integration tests for fair referral distribution."""

    async def test_consecutive_assignments_distribute_fairly(
        self, service, referral_repo, test_realm, test_knights
    ):
        """Multiple assignments distribute across Knights."""
        assignments = []

        # Assign 4 referrals (capacity 2 x 3 Knights = 6 max)
        for i in range(4):
            referral = create_referral(realm_id=test_realm.id)
            await referral_repo.save(referral)
            result = await service.assign_to_eligible_knight(
                referral_id=referral.referral_id,
                realm_id=test_realm.id,
            )
            assert result.success is True
            assignments.append(result.assigned_knight_id)

        # Check distribution - no Knight should have more than 2
        summary = await service.get_realm_workload_summary(test_realm.id)
        for knight_id, count in summary.items():
            assert count <= 2, f"Knight {knight_id} has {count} referrals, max is 2"

        # At least 2 different Knights should have received assignments
        unique_knights = set(assignments)
        assert len(unique_knights) >= 2
