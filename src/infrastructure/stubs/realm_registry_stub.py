"""Realm registry stub implementation (Story 0.6, HP-3, HP-4).

This module provides an in-memory stub implementation of
RealmRegistryProtocol for development and testing purposes.

Constitutional Constraints:
- HP-3: Realm registry for valid petition routing targets
- HP-4: Sentinel-to-realm mapping for petition triage
- NFR-7.3: Knight capacity limits per realm

Testing Features:
- Pre-populated with canonical realms
- Operation tracking for assertions
- Configurable realm states
- Sentinel mapping configuration
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4

from src.application.ports.realm_registry import RealmRegistryProtocol
from src.domain.models.realm import (
    CANONICAL_REALM_IDS,
    REALM_DISPLAY_NAMES,
    Realm,
    RealmStatus,
)


def _utc_now() -> datetime:
    """Return current UTC time with timezone info."""
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class RealmOperation:
    """Record of a realm registry operation for test assertions.

    Attributes:
        operation: The operation name (get_realm_by_id, list_active_realms, etc.)
        params: Dictionary of operation parameters
        result: The operation result
        timestamp: When the operation occurred
    """

    operation: str
    params: dict
    result: object
    timestamp: datetime


class RealmRegistryStub(RealmRegistryProtocol):
    """In-memory stub implementation of RealmRegistryProtocol.

    This stub provides a fully functional in-memory realm registry
    for testing without requiring a database connection.

    Constitutional Compliance:
    - HP-3: Valid routing targets (populated with canonical realms)
    - HP-4: Sentinel-to-realm mapping (configurable)
    - NFR-7.3: Knight capacity tracking

    Testing Features:
    - Track all operations for assertions
    - Configure realm states
    - Configure sentinel mappings
    - Pre-populated with 9 canonical realms

    Attributes:
        _realms: Dictionary of realm_id -> Realm
        _realms_by_name: Dictionary of realm_name -> Realm
        _sentinel_mappings: Dictionary of sentinel_type -> list[tuple[realm_id, priority]]
        _operations: List of RealmOperation records
    """

    def __init__(self, populate_canonical: bool = True) -> None:
        """Initialize the stub.

        Args:
            populate_canonical: If True, pre-populate with 9 canonical realms.
                              Defaults to True for convenience.
        """
        self._realms: dict[UUID, Realm] = {}
        self._realms_by_name: dict[str, Realm] = {}
        self._sentinel_mappings: dict[str, list[tuple[UUID, int]]] = {}
        self._operations: list[RealmOperation] = []

        if populate_canonical:
            self._populate_canonical_realms()

    def _populate_canonical_realms(self) -> None:
        """Pre-populate with the 9 canonical realms from archons-base.json."""
        for name in CANONICAL_REALM_IDS:
            realm = Realm(
                id=uuid4(),
                name=name,
                display_name=REALM_DISPLAY_NAMES.get(name, name),
                knight_capacity=5,
                status=RealmStatus.ACTIVE,
                description=f"Canonical realm: {name}",
                created_at=_utc_now(),
                updated_at=_utc_now(),
            )
            self._realms[realm.id] = realm
            self._realms_by_name[realm.name] = realm

    def _record_operation(
        self, operation: str, params: dict, result: object
    ) -> None:
        """Record an operation for test assertions."""
        self._operations.append(
            RealmOperation(
                operation=operation,
                params=params,
                result=result,
                timestamp=_utc_now(),
            )
        )

    # Protocol implementation

    def get_realm_by_id(self, realm_id: UUID) -> Realm | None:
        """Retrieve a realm by its UUID."""
        result = self._realms.get(realm_id)
        self._record_operation(
            "get_realm_by_id",
            {"realm_id": str(realm_id)},
            result,
        )
        return result

    def get_realm_by_name(self, name: str) -> Realm | None:
        """Retrieve a realm by its canonical name."""
        result = self._realms_by_name.get(name)
        self._record_operation(
            "get_realm_by_name",
            {"name": name},
            result,
        )
        return result

    def list_active_realms(self) -> list[Realm]:
        """List all active realms in the registry."""
        result = sorted(
            [r for r in self._realms.values() if r.status == RealmStatus.ACTIVE],
            key=lambda r: r.name,
        )
        self._record_operation("list_active_realms", {}, result)
        return result

    def list_all_realms(self) -> list[Realm]:
        """List all realms in the registry regardless of status."""
        result = sorted(self._realms.values(), key=lambda r: r.name)
        self._record_operation("list_all_realms", {}, result)
        return result

    def get_realms_for_sentinel(self, sentinel_type: str) -> list[Realm]:
        """Get realms mapped to a sentinel type for petition triage."""
        mappings = self._sentinel_mappings.get(sentinel_type, [])
        # Sort by priority, then get realms
        sorted_mappings = sorted(mappings, key=lambda x: x[1])
        result = []
        for realm_id, _ in sorted_mappings:
            realm = self._realms.get(realm_id)
            if realm and realm.status == RealmStatus.ACTIVE:
                result.append(realm)

        self._record_operation(
            "get_realms_for_sentinel",
            {"sentinel_type": sentinel_type},
            result,
        )
        return result

    def get_default_realm(self) -> Realm | None:
        """Get the default fallback realm for routing."""
        active_realms = self.list_active_realms()
        result = active_realms[0] if active_realms else None
        self._record_operation("get_default_realm", {}, result)
        return result

    def is_realm_available(self, realm_id: UUID) -> bool:
        """Check if a realm is active and available for routing."""
        realm = self._realms.get(realm_id)
        result = realm is not None and realm.status == RealmStatus.ACTIVE
        self._record_operation(
            "is_realm_available",
            {"realm_id": str(realm_id)},
            result,
        )
        return result

    def get_realm_knight_capacity(self, realm_id: UUID) -> int | None:
        """Get the knight capacity for a realm."""
        realm = self._realms.get(realm_id)
        result = realm.knight_capacity if realm else None
        self._record_operation(
            "get_realm_knight_capacity",
            {"realm_id": str(realm_id)},
            result,
        )
        return result

    # Testing helper methods

    def clear(self) -> None:
        """Clear all realms, mappings, and operations."""
        self._realms.clear()
        self._realms_by_name.clear()
        self._sentinel_mappings.clear()
        self._operations.clear()

    def clear_operations(self) -> None:
        """Clear operation history only."""
        self._operations.clear()

    def add_realm(self, realm: Realm) -> None:
        """Add a realm to the registry.

        Args:
            realm: The Realm to add.
        """
        self._realms[realm.id] = realm
        self._realms_by_name[realm.name] = realm

    def remove_realm(self, realm_id: UUID) -> bool:
        """Remove a realm from the registry.

        Args:
            realm_id: The UUID of the realm to remove.

        Returns:
            True if realm was removed, False if not found.
        """
        realm = self._realms.pop(realm_id, None)
        if realm:
            self._realms_by_name.pop(realm.name, None)
            return True
        return False

    def set_realm_status(self, realm_id: UUID, status: RealmStatus) -> bool:
        """Update a realm's status.

        Args:
            realm_id: The UUID of the realm.
            status: The new status.

        Returns:
            True if realm was updated, False if not found.
        """
        realm = self._realms.get(realm_id)
        if realm:
            updated_realm = realm.with_status(status)
            self._realms[realm_id] = updated_realm
            self._realms_by_name[realm.name] = updated_realm
            return True
        return False

    def set_knight_capacity(self, realm_id: UUID, capacity: int) -> bool:
        """Update a realm's knight capacity.

        Args:
            realm_id: The UUID of the realm.
            capacity: The new capacity.

        Returns:
            True if realm was updated, False if not found.
        """
        realm = self._realms.get(realm_id)
        if realm:
            updated_realm = realm.with_knight_capacity(capacity)
            self._realms[realm_id] = updated_realm
            self._realms_by_name[realm.name] = updated_realm
            return True
        return False

    def add_sentinel_mapping(
        self, sentinel_type: str, realm_id: UUID, priority: int = 0
    ) -> None:
        """Add a sentinel-to-realm mapping.

        Args:
            sentinel_type: The sentinel type/category.
            realm_id: The UUID of the realm to map.
            priority: Priority (lower = higher priority). Default 0.
        """
        if sentinel_type not in self._sentinel_mappings:
            self._sentinel_mappings[sentinel_type] = []
        self._sentinel_mappings[sentinel_type].append((realm_id, priority))

    def remove_sentinel_mapping(self, sentinel_type: str, realm_id: UUID) -> bool:
        """Remove a sentinel-to-realm mapping.

        Args:
            sentinel_type: The sentinel type.
            realm_id: The realm UUID to unmap.

        Returns:
            True if mapping was removed, False if not found.
        """
        if sentinel_type not in self._sentinel_mappings:
            return False

        original_len = len(self._sentinel_mappings[sentinel_type])
        self._sentinel_mappings[sentinel_type] = [
            (rid, pri)
            for rid, pri in self._sentinel_mappings[sentinel_type]
            if rid != realm_id
        ]
        return len(self._sentinel_mappings[sentinel_type]) < original_len

    def clear_sentinel_mappings(self, sentinel_type: str | None = None) -> None:
        """Clear sentinel mappings.

        Args:
            sentinel_type: If specified, clear only this type. Otherwise clear all.
        """
        if sentinel_type:
            self._sentinel_mappings.pop(sentinel_type, None)
        else:
            self._sentinel_mappings.clear()

    def get_operations(self) -> list[RealmOperation]:
        """Get list of all operations."""
        return self._operations.copy()

    def get_operation_count(self) -> int:
        """Get count of operations."""
        return len(self._operations)

    def get_operations_by_type(self, operation: str) -> list[RealmOperation]:
        """Get operations filtered by operation name."""
        return [op for op in self._operations if op.operation == operation]

    def was_realm_queried(self, realm_id: UUID) -> bool:
        """Check if a specific realm was ever queried by ID."""
        return any(
            op.operation == "get_realm_by_id"
            and op.params.get("realm_id") == str(realm_id)
            for op in self._operations
        )

    def was_realm_name_queried(self, name: str) -> bool:
        """Check if a specific realm was ever queried by name."""
        return any(
            op.operation == "get_realm_by_name" and op.params.get("name") == name
            for op in self._operations
        )

    def get_realm_count(self) -> int:
        """Get total number of realms in registry."""
        return len(self._realms)

    def get_active_realm_count(self) -> int:
        """Get count of active realms."""
        return len([r for r in self._realms.values() if r.status == RealmStatus.ACTIVE])
