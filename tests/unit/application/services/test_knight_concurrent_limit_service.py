"""Unit tests for KnightConcurrentLimitService (Story 4.7, FR-4.7, NFR-7.3).

Tests Knight concurrent referral limit enforcement including:
- Eligibility checking based on realm capacity
- Finding eligible Knights with workload sorting
- Assignment to least-loaded Knights
- Deferral when all Knights at capacity
- Event emission for assignments and deferrals

Constitutional Constraints:
- FR-4.7: System SHALL enforce max concurrent referrals per Knight
- NFR-7.3: Referral load balancing - max concurrent per Knight configurable
- CT-12: Every action that affects an Archon must be witnessed
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.application.ports.knight_concurrent_limit import (
    AssignmentResult,
    KnightEligibilityResult,
)
from src.application.services.knight_concurrent_limit_service import (
    KnightConcurrentLimitService,
)
from src.domain.errors.knight_concurrent_limit import (
    KnightAtCapacityError,
    KnightNotFoundError,
    KnightNotInRealmError,
    ReferralAlreadyAssignedError,
)
from src.domain.models.realm import Realm, RealmStatus
from src.domain.models.referral import Referral, ReferralStatus


# ═══════════════════════════════════════════════════════════════════════════════
# TEST FIXTURES
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def realm_id():
    """Generate a test realm UUID."""
    return uuid4()


@pytest.fixture
def knight_id():
    """Generate a test Knight UUID."""
    return uuid4()


@pytest.fixture
def referral_id():
    """Generate a test referral UUID."""
    return uuid4()


@pytest.fixture
def petition_id():
    """Generate a test petition UUID."""
    return uuid4()


@pytest.fixture
def realm(realm_id):
    """Create a test Realm with knight_capacity=3."""
    return Realm(
        id=realm_id,
        name="test_realm",
        display_name="Test Realm",
        knight_capacity=3,
        status=RealmStatus.ACTIVE,
    )


@pytest.fixture
def referral(referral_id, petition_id, realm_id):
    """Create a test Referral in PENDING status."""
    now = datetime.now(timezone.utc)
    return Referral(
        referral_id=referral_id,
        petition_id=petition_id,
        realm_id=realm_id,
        deadline=now + timedelta(weeks=3),
        created_at=now,
        status=ReferralStatus.PENDING,
    )


@pytest.fixture
def mock_referral_repo():
    """Create mock referral repository."""
    return AsyncMock()


@pytest.fixture
def mock_knight_registry():
    """Create mock Knight registry."""
    return AsyncMock()


@pytest.fixture
def mock_realm_registry():
    """Create mock realm registry."""
    return MagicMock()


@pytest.fixture
def mock_event_writer():
    """Create mock event writer."""
    return AsyncMock()


@pytest.fixture
def mock_hash_service():
    """Create mock hash service."""
    mock = MagicMock()
    mock.hash_text.return_value = b"fakehash12345678901234567890123456789012"
    return mock


@pytest.fixture
def service(
    mock_referral_repo,
    mock_knight_registry,
    mock_realm_registry,
    mock_event_writer,
    mock_hash_service,
):
    """Create KnightConcurrentLimitService with mocked dependencies."""
    return KnightConcurrentLimitService(
        referral_repo=mock_referral_repo,
        knight_registry=mock_knight_registry,
        realm_registry=mock_realm_registry,
        event_writer=mock_event_writer,
        hash_service=mock_hash_service,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# CHECK KNIGHT ELIGIBILITY TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestCheckKnightEligibility:
    """Tests for check_knight_eligibility method."""

    async def test_eligible_when_below_capacity(
        self, service, knight_id, realm_id, realm, mock_knight_registry, mock_realm_registry, mock_referral_repo
    ):
        """Knight is eligible when current count < knight_capacity."""
        # Arrange
        mock_knight_registry.is_knight.return_value = True
        mock_knight_registry.get_knight_realm.return_value = realm_id
        mock_realm_registry.get_realm_by_id.return_value = realm
        mock_referral_repo.count_active_by_knight.return_value = 1  # Below capacity of 3

        # Act
        result = await service.check_knight_eligibility(knight_id, realm_id)

        # Assert
        assert result.is_eligible is True
        assert result.current_count == 1
        assert result.max_allowed == 3
        assert result.reason is None

    async def test_not_eligible_at_capacity(
        self, service, knight_id, realm_id, realm, mock_knight_registry, mock_realm_registry, mock_referral_repo
    ):
        """Knight not eligible when current count >= knight_capacity."""
        # Arrange
        mock_knight_registry.is_knight.return_value = True
        mock_knight_registry.get_knight_realm.return_value = realm_id
        mock_realm_registry.get_realm_by_id.return_value = realm
        mock_referral_repo.count_active_by_knight.return_value = 3  # At capacity

        # Act
        result = await service.check_knight_eligibility(knight_id, realm_id)

        # Assert
        assert result.is_eligible is False
        assert result.current_count == 3
        assert result.max_allowed == 3
        assert result.reason is not None
        assert "At capacity" in result.reason

    async def test_raises_knight_not_found_error(
        self, service, knight_id, realm_id, mock_knight_registry
    ):
        """Raises KnightNotFoundError for invalid Knight."""
        # Arrange
        mock_knight_registry.is_knight.return_value = False

        # Act & Assert
        with pytest.raises(KnightNotFoundError) as exc_info:
            await service.check_knight_eligibility(knight_id, realm_id)
        assert exc_info.value.knight_id == knight_id

    async def test_raises_knight_not_in_realm_error(
        self, service, knight_id, realm_id, mock_knight_registry
    ):
        """Raises KnightNotInRealmError when Knight is in different realm."""
        # Arrange
        other_realm = uuid4()
        mock_knight_registry.is_knight.return_value = True
        mock_knight_registry.get_knight_realm.return_value = other_realm

        # Act & Assert
        with pytest.raises(KnightNotInRealmError) as exc_info:
            await service.check_knight_eligibility(knight_id, realm_id)
        assert exc_info.value.knight_id == knight_id
        assert exc_info.value.realm_id == realm_id
        assert exc_info.value.actual_realm_id == other_realm


# ═══════════════════════════════════════════════════════════════════════════════
# FIND ELIGIBLE KNIGHTS TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestFindEligibleKnights:
    """Tests for find_eligible_knights method."""

    async def test_returns_eligible_knights_sorted_by_workload(
        self, service, realm_id, realm, mock_knight_registry, mock_realm_registry, mock_referral_repo
    ):
        """Returns eligible Knights sorted by workload ascending."""
        # Arrange
        knight1 = uuid4()  # workload 2
        knight2 = uuid4()  # workload 0
        knight3 = uuid4()  # workload 1

        mock_realm_registry.get_realm_by_id.return_value = realm
        mock_knight_registry.get_knights_in_realm.return_value = [knight1, knight2, knight3]

        # Configure workloads
        async def get_count(kid):
            return {knight1: 2, knight2: 0, knight3: 1}[kid]
        mock_referral_repo.count_active_by_knight.side_effect = get_count

        # Act
        result = await service.find_eligible_knights(realm_id)

        # Assert
        assert len(result) == 3
        assert result[0] == knight2  # Lowest workload first
        assert result[1] == knight3
        assert result[2] == knight1

    async def test_excludes_knights_at_capacity(
        self, service, realm_id, realm, mock_knight_registry, mock_realm_registry, mock_referral_repo
    ):
        """Excludes Knights who have reached capacity."""
        # Arrange
        knight1 = uuid4()  # workload 3 (at capacity)
        knight2 = uuid4()  # workload 1 (eligible)

        mock_realm_registry.get_realm_by_id.return_value = realm
        mock_knight_registry.get_knights_in_realm.return_value = [knight1, knight2]

        async def get_count(kid):
            return {knight1: 3, knight2: 1}[kid]
        mock_referral_repo.count_active_by_knight.side_effect = get_count

        # Act
        result = await service.find_eligible_knights(realm_id)

        # Assert
        assert len(result) == 1
        assert result[0] == knight2

    async def test_respects_limit_parameter(
        self, service, realm_id, realm, mock_knight_registry, mock_realm_registry, mock_referral_repo
    ):
        """Respects the limit parameter."""
        # Arrange
        knights = [uuid4() for _ in range(5)]

        mock_realm_registry.get_realm_by_id.return_value = realm
        mock_knight_registry.get_knights_in_realm.return_value = knights
        mock_referral_repo.count_active_by_knight.return_value = 0

        # Act
        result = await service.find_eligible_knights(realm_id, limit=2)

        # Assert
        assert len(result) == 2

    async def test_returns_empty_when_no_eligible_knights(
        self, service, realm_id, realm, mock_knight_registry, mock_realm_registry, mock_referral_repo
    ):
        """Returns empty list when all Knights are at capacity."""
        # Arrange
        knight1 = uuid4()
        knight2 = uuid4()

        mock_realm_registry.get_realm_by_id.return_value = realm
        mock_knight_registry.get_knights_in_realm.return_value = [knight1, knight2]
        mock_referral_repo.count_active_by_knight.return_value = 3  # All at capacity

        # Act
        result = await service.find_eligible_knights(realm_id)

        # Assert
        assert len(result) == 0


# ═══════════════════════════════════════════════════════════════════════════════
# ASSIGN TO ELIGIBLE KNIGHT TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestAssignToEligibleKnight:
    """Tests for assign_to_eligible_knight method."""

    async def test_assigns_to_least_loaded_knight(
        self, service, referral, realm, mock_referral_repo, mock_knight_registry, mock_realm_registry, mock_event_writer, mock_hash_service
    ):
        """Assigns referral to Knight with lowest workload."""
        # Arrange
        knight1 = uuid4()  # workload 2
        knight2 = uuid4()  # workload 0

        mock_referral_repo.get_by_id.return_value = referral
        mock_realm_registry.get_realm_by_id.return_value = realm
        mock_knight_registry.get_knights_in_realm.return_value = [knight1, knight2]
        mock_knight_registry.is_knight.return_value = True

        async def get_count(kid):
            return {knight1: 2, knight2: 0}[kid]
        mock_referral_repo.count_active_by_knight.side_effect = get_count

        # Act
        result = await service.assign_to_eligible_knight(
            referral_id=referral.referral_id,
            realm_id=referral.realm_id,
        )

        # Assert
        assert result.success is True
        assert result.assigned_knight_id == knight2  # Lowest workload
        assert result.referral is not None
        mock_referral_repo.update.assert_called_once()
        mock_event_writer.write.assert_called_once()

    async def test_uses_preferred_knight_when_eligible(
        self, service, referral, realm, mock_referral_repo, mock_knight_registry, mock_realm_registry, mock_event_writer, mock_hash_service
    ):
        """Uses preferred Knight if eligible."""
        # Arrange
        preferred = uuid4()
        other = uuid4()

        mock_referral_repo.get_by_id.return_value = referral
        mock_realm_registry.get_realm_by_id.return_value = realm
        mock_knight_registry.is_knight.return_value = True
        mock_knight_registry.get_knight_realm.return_value = referral.realm_id
        mock_knight_registry.get_knights_in_realm.return_value = [preferred, other]
        mock_referral_repo.count_active_by_knight.return_value = 1  # Both eligible

        # Act
        result = await service.assign_to_eligible_knight(
            referral_id=referral.referral_id,
            realm_id=referral.realm_id,
            preferred_knight_id=preferred,
        )

        # Assert
        assert result.success is True
        assert result.assigned_knight_id == preferred

    async def test_falls_back_when_preferred_at_capacity(
        self, service, referral, realm, mock_referral_repo, mock_knight_registry, mock_realm_registry, mock_event_writer, mock_hash_service
    ):
        """Falls back to other Knights when preferred is at capacity."""
        # Arrange
        preferred = uuid4()
        other = uuid4()

        mock_referral_repo.get_by_id.return_value = referral
        mock_realm_registry.get_realm_by_id.return_value = realm
        mock_knight_registry.is_knight.return_value = True
        mock_knight_registry.get_knight_realm.return_value = referral.realm_id
        mock_knight_registry.get_knights_in_realm.return_value = [preferred, other]

        async def get_count(kid):
            return {preferred: 3, other: 1}[kid]  # Preferred at capacity
        mock_referral_repo.count_active_by_knight.side_effect = get_count

        # Act
        result = await service.assign_to_eligible_knight(
            referral_id=referral.referral_id,
            realm_id=referral.realm_id,
            preferred_knight_id=preferred,
        )

        # Assert
        assert result.success is True
        assert result.assigned_knight_id == other

    async def test_defers_when_all_at_capacity(
        self, service, referral, realm, mock_referral_repo, mock_knight_registry, mock_realm_registry, mock_event_writer, mock_hash_service
    ):
        """Defers assignment when all Knights at capacity."""
        # Arrange
        knight1 = uuid4()
        knight2 = uuid4()

        mock_referral_repo.get_by_id.return_value = referral
        mock_realm_registry.get_realm_by_id.return_value = realm
        mock_knight_registry.get_knights_in_realm.return_value = [knight1, knight2]
        mock_referral_repo.count_active_by_knight.return_value = 3  # All at capacity

        # Act
        result = await service.assign_to_eligible_knight(
            referral_id=referral.referral_id,
            realm_id=referral.realm_id,
        )

        # Assert
        assert result.success is False
        assert result.all_knights_at_capacity is True
        assert result.deferred_reason is not None
        assert "at capacity" in result.deferred_reason.lower()
        mock_event_writer.write.assert_called_once()  # Deferral event

    async def test_raises_referral_already_assigned_error(
        self, service, referral, realm_id, mock_referral_repo
    ):
        """Raises error when referral already assigned."""
        # Arrange
        assigned_knight = uuid4()
        assigned_referral = Referral(
            referral_id=referral.referral_id,
            petition_id=referral.petition_id,
            realm_id=referral.realm_id,
            deadline=referral.deadline,
            created_at=referral.created_at,
            status=ReferralStatus.ASSIGNED,
            assigned_knight_id=assigned_knight,
        )
        mock_referral_repo.get_by_id.return_value = assigned_referral

        # Act & Assert
        with pytest.raises(ReferralAlreadyAssignedError) as exc_info:
            await service.assign_to_eligible_knight(
                referral_id=referral.referral_id,
                realm_id=realm_id,
            )
        assert exc_info.value.referral_id == referral.referral_id
        assert exc_info.value.assigned_knight_id == assigned_knight

    async def test_emits_assignment_event_with_witness_hash(
        self, service, referral, realm, mock_referral_repo, mock_knight_registry, mock_realm_registry, mock_event_writer, mock_hash_service
    ):
        """Emits assignment event with witness hash (CT-12)."""
        # Arrange
        knight = uuid4()
        mock_referral_repo.get_by_id.return_value = referral
        mock_realm_registry.get_realm_by_id.return_value = realm
        mock_knight_registry.get_knights_in_realm.return_value = [knight]
        mock_referral_repo.count_active_by_knight.return_value = 0

        # Act
        await service.assign_to_eligible_knight(
            referral_id=referral.referral_id,
            realm_id=referral.realm_id,
        )

        # Assert
        mock_hash_service.hash_text.assert_called_once()
        mock_event_writer.write.assert_called_once()
        event_dict = mock_event_writer.write.call_args[0][0]
        assert "witness_hash" in event_dict
        assert event_dict["witness_hash"].startswith("blake3:")
        assert event_dict["event_type"] == "petition.referral.assigned"

    async def test_emits_deferral_event_with_witness_hash(
        self, service, referral, realm, mock_referral_repo, mock_knight_registry, mock_realm_registry, mock_event_writer, mock_hash_service
    ):
        """Emits deferral event with witness hash (CT-12)."""
        # Arrange
        mock_referral_repo.get_by_id.return_value = referral
        mock_realm_registry.get_realm_by_id.return_value = realm
        mock_knight_registry.get_knights_in_realm.return_value = [uuid4()]
        mock_referral_repo.count_active_by_knight.return_value = 3  # At capacity

        # Act
        await service.assign_to_eligible_knight(
            referral_id=referral.referral_id,
            realm_id=referral.realm_id,
        )

        # Assert
        mock_event_writer.write.assert_called_once()
        event_dict = mock_event_writer.write.call_args[0][0]
        assert "witness_hash" in event_dict
        assert event_dict["event_type"] == "petition.referral.deferred"
        assert "total_knights" in event_dict
        assert "knights_at_capacity" in event_dict


# ═══════════════════════════════════════════════════════════════════════════════
# GET KNIGHT WORKLOAD TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestGetKnightWorkload:
    """Tests for get_knight_workload method."""

    async def test_returns_active_referral_count(
        self, service, knight_id, mock_referral_repo
    ):
        """Returns count of active referrals for Knight."""
        # Arrange
        mock_referral_repo.count_active_by_knight.return_value = 5

        # Act
        result = await service.get_knight_workload(knight_id)

        # Assert
        assert result == 5
        mock_referral_repo.count_active_by_knight.assert_called_once_with(knight_id)


# ═══════════════════════════════════════════════════════════════════════════════
# GET REALM WORKLOAD SUMMARY TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestGetRealmWorkloadSummary:
    """Tests for get_realm_workload_summary method."""

    async def test_returns_workload_for_all_knights(
        self, service, realm_id, realm, mock_knight_registry, mock_realm_registry, mock_referral_repo
    ):
        """Returns workload summary for all Knights in realm."""
        # Arrange
        knight1 = uuid4()
        knight2 = uuid4()
        knight3 = uuid4()

        mock_realm_registry.get_realm_by_id.return_value = realm
        mock_knight_registry.get_knights_in_realm.return_value = [knight1, knight2, knight3]

        async def get_count(kid):
            return {knight1: 1, knight2: 2, knight3: 0}[kid]
        mock_referral_repo.count_active_by_knight.side_effect = get_count

        # Act
        result = await service.get_realm_workload_summary(realm_id)

        # Assert
        assert len(result) == 3
        assert result[knight1] == 1
        assert result[knight2] == 2
        assert result[knight3] == 0
