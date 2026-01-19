"""Realm registry port for petition routing (Story 0.6, HP-3, HP-4).

This module defines the abstract interface for realm registry operations
in the Three Fates petition system.

Constitutional Constraints:
- HP-3: Realm registry for valid petition routing targets
- HP-4: Sentinel-to-realm mapping for petition triage
- NFR-7.3: Knight capacity limits per realm

Developer Golden Rules:
1. ACTIVE REALMS ONLY - Routing only to active realms
2. CAPACITY AWARE - Respect knight_capacity limits
3. DETERMINISTIC - Same sentinel type maps to same realm(s)
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from src.domain.models.realm import Realm


class RealmRegistryProtocol(Protocol):
    """Protocol for realm registry operations (Story 0.6, HP-3, HP-4).

    Defines the contract for querying the realm registry for petition
    routing and sentinel-to-realm mapping.

    Constitutional Constraints:
    - HP-3: Valid routing targets for petitions
    - HP-4: Sentinel-to-realm mapping for triage
    - NFR-7.3: Knight capacity limits

    Methods:
        get_realm_by_id: Retrieve realm by UUID
        get_realm_by_name: Retrieve realm by canonical name
        list_active_realms: List all active realms
        get_realms_for_sentinel: Get realms for a sentinel type (HP-4)
        get_default_realm: Get fallback realm for routing
    """

    def get_realm_by_id(self, realm_id: UUID) -> Realm | None:
        """Retrieve a realm by its UUID.

        Args:
            realm_id: The UUID of the realm to retrieve.

        Returns:
            The Realm if found, None otherwise.
        """
        ...

    def get_realm_by_name(self, name: str) -> Realm | None:
        """Retrieve a realm by its canonical name.

        Constitutional Constraint (HP-3): Valid routing target lookup.

        Args:
            name: Canonical realm name (e.g., "realm_privacy_discretion_services").

        Returns:
            The Realm if found, None otherwise.
        """
        ...

    def list_active_realms(self) -> list[Realm]:
        """List all active realms in the registry.

        Constitutional Constraint (HP-3): Query all valid routing targets.

        Returns:
            List of Realm objects with status ACTIVE.
        """
        ...

    def list_all_realms(self) -> list[Realm]:
        """List all realms in the registry regardless of status.

        Returns:
            List of all Realm objects.
        """
        ...

    def get_realms_for_sentinel(self, sentinel_type: str) -> list[Realm]:
        """Get realms mapped to a sentinel type for petition triage.

        Constitutional Constraint (HP-4): Sentinel-to-realm mapping.

        Returns realms ordered by priority (lowest priority number first).
        Only active realms are returned.

        Args:
            sentinel_type: The sentinel type/category (e.g., "privacy", "security").

        Returns:
            List of Realm objects mapped to this sentinel type, ordered by priority.
            Empty list if no mapping exists.
        """
        ...

    def get_default_realm(self) -> Realm | None:
        """Get the default fallback realm for routing.

        Used when no specific realm mapping exists for a petition.

        Returns:
            The first active realm (by name), or None if no active realms.
        """
        ...

    def is_realm_available(self, realm_id: UUID) -> bool:
        """Check if a realm is active and available for routing.

        Args:
            realm_id: The UUID of the realm to check.

        Returns:
            True if realm exists and is ACTIVE, False otherwise.
        """
        ...

    def get_realm_knight_capacity(self, realm_id: UUID) -> int | None:
        """Get the knight capacity for a realm.

        Constitutional Constraint (NFR-7.3): Capacity limits for referrals.

        Args:
            realm_id: The UUID of the realm.

        Returns:
            Knight capacity integer if realm exists, None otherwise.
        """
        ...
