"""Unit tests for Realm domain model (Story 0.6, HP-3, HP-4).

Tests:
- RealmStatus enum values
- Frozen dataclass behavior (immutability)
- Validation constraints (name, display_name, knight_capacity)
- with_status() creates new instance
- with_knight_capacity() creates new instance
- is_active property
- Canonical realm IDs validation
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.domain.models.realm import (
    CANONICAL_REALM_IDS,
    REALM_DISPLAY_NAMES,
    Realm,
    RealmStatus,
    is_canonical_realm,
)


class TestRealmStatus:
    """Test RealmStatus enum."""

    def test_all_values_present(self) -> None:
        """Verify all realm status values exist."""
        assert RealmStatus.ACTIVE.value == "ACTIVE"
        assert RealmStatus.INACTIVE.value == "INACTIVE"
        assert RealmStatus.DEPRECATED.value == "DEPRECATED"

    def test_enum_count(self) -> None:
        """Verify exactly 3 realm statuses."""
        assert len(RealmStatus) == 3


class TestRealm:
    """Test Realm domain model."""

    def test_create_basic_realm(self) -> None:
        """Can create a basic realm."""
        realm_id = uuid4()
        realm = Realm(
            id=realm_id,
            name="test_realm",
            display_name="Test Realm",
            knight_capacity=5,
        )

        assert realm.id == realm_id
        assert realm.name == "test_realm"
        assert realm.display_name == "Test Realm"
        assert realm.knight_capacity == 5
        assert realm.status == RealmStatus.ACTIVE
        assert realm.description is None
        assert realm.created_at is not None
        assert realm.updated_at is not None

    def test_create_full_realm(self) -> None:
        """Can create realm with all fields."""
        realm_id = uuid4()
        created_at = datetime.now(timezone.utc)

        realm = Realm(
            id=realm_id,
            name="full_test_realm",
            display_name="Full Test Realm",
            knight_capacity=10,
            status=RealmStatus.INACTIVE,
            description="A test realm description",
            created_at=created_at,
            updated_at=created_at,
        )

        assert realm.id == realm_id
        assert realm.name == "full_test_realm"
        assert realm.display_name == "Full Test Realm"
        assert realm.knight_capacity == 10
        assert realm.status == RealmStatus.INACTIVE
        assert realm.description == "A test realm description"
        assert realm.created_at == created_at

    def test_frozen_dataclass_immutable(self) -> None:
        """Verify frozen dataclass is immutable."""
        realm = Realm(
            id=uuid4(),
            name="test_realm",
            display_name="Test Realm",
            knight_capacity=5,
        )

        with pytest.raises(AttributeError):
            realm.status = RealmStatus.INACTIVE  # type: ignore[misc]

        with pytest.raises(AttributeError):
            realm.knight_capacity = 10  # type: ignore[misc]

    def test_is_active_property(self) -> None:
        """Test is_active property."""
        active_realm = Realm(
            id=uuid4(),
            name="active_realm",
            display_name="Active Realm",
            knight_capacity=5,
            status=RealmStatus.ACTIVE,
        )
        inactive_realm = Realm(
            id=uuid4(),
            name="inactive_realm",
            display_name="Inactive Realm",
            knight_capacity=5,
            status=RealmStatus.INACTIVE,
        )
        deprecated_realm = Realm(
            id=uuid4(),
            name="deprecated_realm",
            display_name="Deprecated Realm",
            knight_capacity=5,
            status=RealmStatus.DEPRECATED,
        )

        assert active_realm.is_active is True
        assert inactive_realm.is_active is False
        assert deprecated_realm.is_active is False

    def test_with_status_creates_new_instance(self) -> None:
        """with_status() creates new instance with updated status."""
        original = Realm(
            id=uuid4(),
            name="test_realm",
            display_name="Test Realm",
            knight_capacity=5,
            status=RealmStatus.ACTIVE,
        )

        updated = original.with_status(RealmStatus.INACTIVE)

        # Original unchanged
        assert original.status == RealmStatus.ACTIVE
        # New instance has updated status
        assert updated.status == RealmStatus.INACTIVE
        # Same identity
        assert updated.id == original.id
        assert updated.name == original.name
        # Different instances
        assert original is not updated

    def test_with_status_updates_timestamp(self) -> None:
        """with_status() updates the updated_at timestamp."""
        original = Realm(
            id=uuid4(),
            name="test_realm",
            display_name="Test Realm",
            knight_capacity=5,
        )
        original_updated_at = original.updated_at

        updated = original.with_status(RealmStatus.INACTIVE)

        # updated_at should be >= original
        assert updated.updated_at >= original_updated_at
        # created_at should be preserved
        assert updated.created_at == original.created_at

    def test_with_knight_capacity_creates_new_instance(self) -> None:
        """with_knight_capacity() creates new instance with updated capacity."""
        original = Realm(
            id=uuid4(),
            name="test_realm",
            display_name="Test Realm",
            knight_capacity=5,
        )

        updated = original.with_knight_capacity(10)

        # Original unchanged
        assert original.knight_capacity == 5
        # New instance has updated capacity
        assert updated.knight_capacity == 10
        # Same identity
        assert updated.id == original.id
        assert updated.name == original.name
        # Different instances
        assert original is not updated


class TestRealmValidation:
    """Test Realm validation constraints."""

    def test_empty_name_rejected(self) -> None:
        """Validation rejects empty name."""
        with pytest.raises(ValueError, match="cannot be empty"):
            Realm(
                id=uuid4(),
                name="",
                display_name="Test Realm",
                knight_capacity=5,
            )

    def test_oversized_name_rejected(self) -> None:
        """Validation rejects name > 100 chars."""
        oversized_name = "x" * 101

        with pytest.raises(ValueError, match="exceeds maximum length"):
            Realm(
                id=uuid4(),
                name=oversized_name,
                display_name="Test Realm",
                knight_capacity=5,
            )

    def test_max_length_name_accepted(self) -> None:
        """Validation accepts name at max length (100 chars)."""
        max_name = "x" * 100

        realm = Realm(
            id=uuid4(),
            name=max_name,
            display_name="Test Realm",
            knight_capacity=5,
        )

        assert len(realm.name) == 100

    def test_empty_display_name_rejected(self) -> None:
        """Validation rejects empty display_name."""
        with pytest.raises(ValueError, match="cannot be empty"):
            Realm(
                id=uuid4(),
                name="test_realm",
                display_name="",
                knight_capacity=5,
            )

    def test_oversized_display_name_rejected(self) -> None:
        """Validation rejects display_name > 200 chars."""
        oversized_display_name = "x" * 201

        with pytest.raises(ValueError, match="exceeds maximum length"):
            Realm(
                id=uuid4(),
                name="test_realm",
                display_name=oversized_display_name,
                knight_capacity=5,
            )

    def test_knight_capacity_below_minimum_rejected(self) -> None:
        """Validation rejects knight_capacity < 1."""
        with pytest.raises(ValueError, match="at least 1"):
            Realm(
                id=uuid4(),
                name="test_realm",
                display_name="Test Realm",
                knight_capacity=0,
            )

        with pytest.raises(ValueError, match="at least 1"):
            Realm(
                id=uuid4(),
                name="test_realm",
                display_name="Test Realm",
                knight_capacity=-1,
            )

    def test_knight_capacity_above_maximum_rejected(self) -> None:
        """Validation rejects knight_capacity > 100."""
        with pytest.raises(ValueError, match="cannot exceed 100"):
            Realm(
                id=uuid4(),
                name="test_realm",
                display_name="Test Realm",
                knight_capacity=101,
            )

    def test_knight_capacity_at_boundaries_accepted(self) -> None:
        """Validation accepts knight_capacity at min (1) and max (100)."""
        realm_min = Realm(
            id=uuid4(),
            name="min_realm",
            display_name="Min Realm",
            knight_capacity=1,
        )
        realm_max = Realm(
            id=uuid4(),
            name="max_realm",
            display_name="Max Realm",
            knight_capacity=100,
        )

        assert realm_min.knight_capacity == 1
        assert realm_max.knight_capacity == 100

    def test_with_knight_capacity_validates(self) -> None:
        """with_knight_capacity() validates new capacity."""
        realm = Realm(
            id=uuid4(),
            name="test_realm",
            display_name="Test Realm",
            knight_capacity=5,
        )

        with pytest.raises(ValueError, match="at least 1"):
            realm.with_knight_capacity(0)

        with pytest.raises(ValueError, match="cannot exceed 100"):
            realm.with_knight_capacity(101)


class TestCanonicalRealms:
    """Test canonical realm IDs and mappings."""

    def test_nine_canonical_realms_defined(self) -> None:
        """Verify exactly 9 canonical realms are defined."""
        assert len(CANONICAL_REALM_IDS) == 9

    def test_canonical_realm_ids_content(self) -> None:
        """Verify canonical realm IDs match archons-base.json."""
        expected_realms = {
            "realm_privacy_discretion_services",
            "realm_relationship_facilitation",
            "realm_knowledge_skill_development",
            "realm_predictive_analytics_forecasting",
            "realm_character_virtue_development",
            "realm_accurate_guidance_counsel",
            "realm_threat_anomaly_detection",
            "realm_personality_charisma_enhancement",
            "realm_talent_acquisition_team_building",
        }

        assert set(CANONICAL_REALM_IDS) == expected_realms

    def test_all_canonical_realms_have_display_names(self) -> None:
        """Verify all canonical realms have display name mappings."""
        for realm_id in CANONICAL_REALM_IDS:
            assert realm_id in REALM_DISPLAY_NAMES
            assert len(REALM_DISPLAY_NAMES[realm_id]) > 0

    def test_is_canonical_realm_true_for_valid(self) -> None:
        """is_canonical_realm() returns True for canonical realms."""
        for realm_id in CANONICAL_REALM_IDS:
            assert is_canonical_realm(realm_id) is True

    def test_is_canonical_realm_false_for_invalid(self) -> None:
        """is_canonical_realm() returns False for non-canonical realms."""
        assert is_canonical_realm("fake_realm") is False
        assert is_canonical_realm("") is False
        assert is_canonical_realm("REALM_PRIVACY_DISCRETION_SERVICES") is False

    def test_canonical_realms_can_be_created(self) -> None:
        """All canonical realms can be created as Realm objects."""
        for realm_id in CANONICAL_REALM_IDS:
            realm = Realm(
                id=uuid4(),
                name=realm_id,
                display_name=REALM_DISPLAY_NAMES[realm_id],
                knight_capacity=5,
            )
            assert realm.name == realm_id
            assert realm.display_name == REALM_DISPLAY_NAMES[realm_id]


class TestRealmEquality:
    """Test realm equality and hashing."""

    def test_equality_based_on_fields(self) -> None:
        """Verify equality is based on field values."""
        realm_id = uuid4()
        created_at = datetime.now(timezone.utc)

        realm1 = Realm(
            id=realm_id,
            name="test_realm",
            display_name="Test Realm",
            knight_capacity=5,
            created_at=created_at,
            updated_at=created_at,
        )
        realm2 = Realm(
            id=realm_id,
            name="test_realm",
            display_name="Test Realm",
            knight_capacity=5,
            created_at=created_at,
            updated_at=created_at,
        )

        assert realm1 == realm2
        assert hash(realm1) == hash(realm2)

    def test_inequality_for_different_fields(self) -> None:
        """Verify inequality for different field values."""
        realm1 = Realm(
            id=uuid4(),
            name="realm_1",
            display_name="Realm 1",
            knight_capacity=5,
        )
        realm2 = Realm(
            id=uuid4(),
            name="realm_2",
            display_name="Realm 2",
            knight_capacity=5,
        )

        assert realm1 != realm2

    def test_all_statuses_can_be_set(self) -> None:
        """Verify all realm statuses work via with_status()."""
        realm = Realm(
            id=uuid4(),
            name="test_realm",
            display_name="Test Realm",
            knight_capacity=5,
        )

        for status in RealmStatus:
            updated = realm.with_status(status)
            assert updated.status == status
