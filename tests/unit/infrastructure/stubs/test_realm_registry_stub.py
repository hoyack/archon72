"""Unit tests for RealmRegistryStub (Story 0.6, HP-3, HP-4).

Tests:
- Pre-population with canonical realms
- get_realm_by_id/name operations
- list_active_realms/list_all_realms
- get_realms_for_sentinel (HP-4)
- get_default_realm
- is_realm_available
- get_realm_knight_capacity
- Testing helper methods
"""

from uuid import uuid4

from src.domain.models.realm import (
    CANONICAL_REALM_IDS,
    Realm,
    RealmStatus,
)
from src.infrastructure.stubs.realm_registry_stub import RealmRegistryStub


class TestRealmRegistryStubInitialization:
    """Test stub initialization and pre-population."""

    def test_default_populates_canonical_realms(self) -> None:
        """Default initialization populates 9 canonical realms."""
        stub = RealmRegistryStub()

        assert stub.get_realm_count() == 9
        assert stub.get_active_realm_count() == 9

    def test_all_canonical_realms_present(self) -> None:
        """All 9 canonical realms are present and queryable by name."""
        stub = RealmRegistryStub()

        for realm_id in CANONICAL_REALM_IDS:
            realm = stub.get_realm_by_name(realm_id)
            assert realm is not None
            assert realm.name == realm_id
            assert realm.status == RealmStatus.ACTIVE

    def test_populate_false_creates_empty_registry(self) -> None:
        """populate_canonical=False creates empty registry."""
        stub = RealmRegistryStub(populate_canonical=False)

        assert stub.get_realm_count() == 0
        assert stub.get_active_realm_count() == 0
        assert stub.list_all_realms() == []


class TestRealmRegistryStubQueries:
    """Test realm query operations."""

    def test_get_realm_by_id_found(self) -> None:
        """get_realm_by_id returns realm when found."""
        stub = RealmRegistryStub()
        all_realms = stub.list_all_realms()
        first_realm = all_realms[0]

        result = stub.get_realm_by_id(first_realm.id)

        assert result is not None
        assert result.id == first_realm.id
        assert result.name == first_realm.name

    def test_get_realm_by_id_not_found(self) -> None:
        """get_realm_by_id returns None when not found."""
        stub = RealmRegistryStub()
        fake_id = uuid4()

        result = stub.get_realm_by_id(fake_id)

        assert result is None

    def test_get_realm_by_name_found(self) -> None:
        """get_realm_by_name returns realm when found."""
        stub = RealmRegistryStub()

        result = stub.get_realm_by_name("realm_privacy_discretion_services")

        assert result is not None
        assert result.name == "realm_privacy_discretion_services"

    def test_get_realm_by_name_not_found(self) -> None:
        """get_realm_by_name returns None when not found."""
        stub = RealmRegistryStub()

        result = stub.get_realm_by_name("fake_realm")

        assert result is None

    def test_list_active_realms(self) -> None:
        """list_active_realms returns only ACTIVE realms sorted by name."""
        stub = RealmRegistryStub()
        # Deactivate one realm
        first_realm = stub.list_all_realms()[0]
        stub.set_realm_status(first_realm.id, RealmStatus.INACTIVE)

        active_realms = stub.list_active_realms()

        assert len(active_realms) == 8
        assert all(r.status == RealmStatus.ACTIVE for r in active_realms)
        # Verify sorted by name
        names = [r.name for r in active_realms]
        assert names == sorted(names)

    def test_list_all_realms_includes_inactive(self) -> None:
        """list_all_realms returns all realms regardless of status."""
        stub = RealmRegistryStub()
        first_realm = stub.list_all_realms()[0]
        stub.set_realm_status(first_realm.id, RealmStatus.INACTIVE)

        all_realms = stub.list_all_realms()

        assert len(all_realms) == 9
        # Verify sorted by name
        names = [r.name for r in all_realms]
        assert names == sorted(names)


class TestRealmRegistryStubSentinelMapping:
    """Test sentinel-to-realm mapping (HP-4)."""

    def test_get_realms_for_sentinel_empty(self) -> None:
        """get_realms_for_sentinel returns empty list when no mapping."""
        stub = RealmRegistryStub()

        result = stub.get_realms_for_sentinel("unknown_sentinel")

        assert result == []

    def test_get_realms_for_sentinel_single_mapping(self) -> None:
        """get_realms_for_sentinel returns mapped realms."""
        stub = RealmRegistryStub()
        privacy_realm = stub.get_realm_by_name("realm_privacy_discretion_services")
        stub.add_sentinel_mapping("privacy", privacy_realm.id, priority=0)

        result = stub.get_realms_for_sentinel("privacy")

        assert len(result) == 1
        assert result[0].name == "realm_privacy_discretion_services"

    def test_get_realms_for_sentinel_priority_order(self) -> None:
        """get_realms_for_sentinel returns realms ordered by priority."""
        stub = RealmRegistryStub()
        realm1 = stub.get_realm_by_name("realm_privacy_discretion_services")
        realm2 = stub.get_realm_by_name("realm_threat_anomaly_detection")

        # Add with different priorities (lower = higher priority)
        stub.add_sentinel_mapping("security", realm2.id, priority=0)
        stub.add_sentinel_mapping("security", realm1.id, priority=10)

        result = stub.get_realms_for_sentinel("security")

        assert len(result) == 2
        assert result[0].name == "realm_threat_anomaly_detection"  # priority 0
        assert result[1].name == "realm_privacy_discretion_services"  # priority 10

    def test_get_realms_for_sentinel_excludes_inactive(self) -> None:
        """get_realms_for_sentinel excludes inactive realms."""
        stub = RealmRegistryStub()
        privacy_realm = stub.get_realm_by_name("realm_privacy_discretion_services")
        stub.add_sentinel_mapping("privacy", privacy_realm.id, priority=0)

        # Deactivate the realm
        stub.set_realm_status(privacy_realm.id, RealmStatus.INACTIVE)

        result = stub.get_realms_for_sentinel("privacy")

        assert result == []


class TestRealmRegistryStubAvailability:
    """Test realm availability and capacity operations."""

    def test_get_default_realm_returns_first_active(self) -> None:
        """get_default_realm returns first active realm by name."""
        stub = RealmRegistryStub()

        result = stub.get_default_realm()

        assert result is not None
        assert result.status == RealmStatus.ACTIVE
        # Should be first alphabetically
        all_active = stub.list_active_realms()
        assert result.name == all_active[0].name

    def test_get_default_realm_empty_registry(self) -> None:
        """get_default_realm returns None when no active realms."""
        stub = RealmRegistryStub(populate_canonical=False)

        result = stub.get_default_realm()

        assert result is None

    def test_is_realm_available_active(self) -> None:
        """is_realm_available returns True for active realms."""
        stub = RealmRegistryStub()
        realm = stub.list_all_realms()[0]

        result = stub.is_realm_available(realm.id)

        assert result is True

    def test_is_realm_available_inactive(self) -> None:
        """is_realm_available returns False for inactive realms."""
        stub = RealmRegistryStub()
        realm = stub.list_all_realms()[0]
        stub.set_realm_status(realm.id, RealmStatus.INACTIVE)

        result = stub.is_realm_available(realm.id)

        assert result is False

    def test_is_realm_available_not_found(self) -> None:
        """is_realm_available returns False for non-existent realms."""
        stub = RealmRegistryStub()

        result = stub.is_realm_available(uuid4())

        assert result is False

    def test_get_realm_knight_capacity(self) -> None:
        """get_realm_knight_capacity returns capacity for existing realm."""
        stub = RealmRegistryStub()
        realm = stub.list_all_realms()[0]

        result = stub.get_realm_knight_capacity(realm.id)

        assert result == 5  # Default capacity

    def test_get_realm_knight_capacity_not_found(self) -> None:
        """get_realm_knight_capacity returns None for non-existent realm."""
        stub = RealmRegistryStub()

        result = stub.get_realm_knight_capacity(uuid4())

        assert result is None


class TestRealmRegistryStubHelpers:
    """Test stub helper methods for testing."""

    def test_add_realm(self) -> None:
        """add_realm adds a new realm to the registry."""
        stub = RealmRegistryStub(populate_canonical=False)
        new_realm = Realm(
            id=uuid4(),
            name="custom_realm",
            display_name="Custom Realm",
            knight_capacity=10,
        )

        stub.add_realm(new_realm)

        assert stub.get_realm_count() == 1
        assert stub.get_realm_by_name("custom_realm") == new_realm
        assert stub.get_realm_by_id(new_realm.id) == new_realm

    def test_remove_realm(self) -> None:
        """remove_realm removes a realm from the registry."""
        stub = RealmRegistryStub()
        realm = stub.list_all_realms()[0]
        initial_count = stub.get_realm_count()

        result = stub.remove_realm(realm.id)

        assert result is True
        assert stub.get_realm_count() == initial_count - 1
        assert stub.get_realm_by_id(realm.id) is None

    def test_remove_realm_not_found(self) -> None:
        """remove_realm returns False when realm not found."""
        stub = RealmRegistryStub()

        result = stub.remove_realm(uuid4())

        assert result is False

    def test_set_realm_status(self) -> None:
        """set_realm_status updates realm status."""
        stub = RealmRegistryStub()
        realm = stub.list_all_realms()[0]

        result = stub.set_realm_status(realm.id, RealmStatus.DEPRECATED)

        assert result is True
        updated = stub.get_realm_by_id(realm.id)
        assert updated.status == RealmStatus.DEPRECATED

    def test_set_knight_capacity(self) -> None:
        """set_knight_capacity updates realm knight capacity."""
        stub = RealmRegistryStub()
        realm = stub.list_all_realms()[0]

        result = stub.set_knight_capacity(realm.id, 20)

        assert result is True
        updated = stub.get_realm_by_id(realm.id)
        assert updated.knight_capacity == 20

    def test_clear(self) -> None:
        """clear() removes all realms and operations."""
        stub = RealmRegistryStub()
        stub.get_realm_by_name("realm_privacy_discretion_services")  # Record operation

        stub.clear()

        assert stub.get_realm_count() == 0
        assert stub.get_operation_count() == 0

    def test_clear_operations(self) -> None:
        """clear_operations() clears only operation history."""
        stub = RealmRegistryStub()
        stub.get_realm_by_name("realm_privacy_discretion_services")

        stub.clear_operations()

        assert stub.get_realm_count() == 9  # Realms preserved
        assert stub.get_operation_count() == 0


class TestRealmRegistryStubOperationTracking:
    """Test operation tracking for test assertions."""

    def test_operations_tracked(self) -> None:
        """All operations are tracked."""
        stub = RealmRegistryStub()
        stub.clear_operations()

        realm = stub.get_realm_by_name("realm_privacy_discretion_services")
        stub.get_realm_by_id(realm.id)
        stub.list_active_realms()
        stub.is_realm_available(realm.id)

        assert stub.get_operation_count() == 4

    def test_get_operations_by_type(self) -> None:
        """get_operations_by_type filters operations."""
        stub = RealmRegistryStub()
        stub.clear_operations()

        stub.get_realm_by_name("realm_privacy_discretion_services")
        stub.get_realm_by_name("realm_threat_anomaly_detection")
        stub.list_active_realms()

        name_ops = stub.get_operations_by_type("get_realm_by_name")
        assert len(name_ops) == 2

    def test_was_realm_queried(self) -> None:
        """was_realm_queried checks if realm was queried by ID."""
        stub = RealmRegistryStub()
        stub.clear_operations()

        realm = stub.get_realm_by_name("realm_privacy_discretion_services")
        stub.get_realm_by_id(realm.id)

        assert stub.was_realm_queried(realm.id) is True
        assert stub.was_realm_queried(uuid4()) is False

    def test_was_realm_name_queried(self) -> None:
        """was_realm_name_queried checks if realm was queried by name."""
        stub = RealmRegistryStub()
        stub.clear_operations()

        stub.get_realm_by_name("realm_privacy_discretion_services")

        assert stub.was_realm_name_queried("realm_privacy_discretion_services") is True
        assert stub.was_realm_name_queried("fake_realm") is False


class TestRealmRegistryStubSentinelMappingHelpers:
    """Test sentinel mapping helper methods."""

    def test_add_sentinel_mapping(self) -> None:
        """add_sentinel_mapping adds a new mapping."""
        stub = RealmRegistryStub()
        realm = stub.get_realm_by_name("realm_privacy_discretion_services")

        stub.add_sentinel_mapping("test_sentinel", realm.id, priority=5)

        result = stub.get_realms_for_sentinel("test_sentinel")
        assert len(result) == 1
        assert result[0].id == realm.id

    def test_remove_sentinel_mapping(self) -> None:
        """remove_sentinel_mapping removes a mapping."""
        stub = RealmRegistryStub()
        realm = stub.get_realm_by_name("realm_privacy_discretion_services")
        stub.add_sentinel_mapping("test_sentinel", realm.id)

        result = stub.remove_sentinel_mapping("test_sentinel", realm.id)

        assert result is True
        assert stub.get_realms_for_sentinel("test_sentinel") == []

    def test_remove_sentinel_mapping_not_found(self) -> None:
        """remove_sentinel_mapping returns False when not found."""
        stub = RealmRegistryStub()

        result = stub.remove_sentinel_mapping("nonexistent", uuid4())

        assert result is False

    def test_clear_sentinel_mappings_specific(self) -> None:
        """clear_sentinel_mappings clears specific sentinel type."""
        stub = RealmRegistryStub()
        realm = stub.get_realm_by_name("realm_privacy_discretion_services")
        stub.add_sentinel_mapping("type1", realm.id)
        stub.add_sentinel_mapping("type2", realm.id)

        stub.clear_sentinel_mappings("type1")

        assert stub.get_realms_for_sentinel("type1") == []
        assert len(stub.get_realms_for_sentinel("type2")) == 1

    def test_clear_sentinel_mappings_all(self) -> None:
        """clear_sentinel_mappings() clears all mappings."""
        stub = RealmRegistryStub()
        realm = stub.get_realm_by_name("realm_privacy_discretion_services")
        stub.add_sentinel_mapping("type1", realm.id)
        stub.add_sentinel_mapping("type2", realm.id)

        stub.clear_sentinel_mappings()

        assert stub.get_realms_for_sentinel("type1") == []
        assert stub.get_realms_for_sentinel("type2") == []
