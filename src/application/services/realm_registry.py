"""Realm registry service implementation (Story 0.6, HP-3, HP-4).

This module implements the RealmRegistryProtocol for querying the realm
registry in the Three Fates petition system.

Constitutional Constraints:
- HP-3: Realm registry for valid petition routing targets
- HP-4: Sentinel-to-realm mapping for petition triage
- NFR-7.3: Knight capacity limits per realm

Usage:
    from src.application.services.realm_registry import RealmRegistryService

    service = RealmRegistryService(supabase_client)
    realm = service.get_realm_by_name("realm_privacy_discretion_services")
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from supabase import Client as SupabaseClient

from src.application.services.base import LoggingMixin
from src.domain.models.realm import Realm, RealmStatus


class RealmRegistryService(LoggingMixin):
    """Supabase implementation of realm registry (Story 0.6, HP-3, HP-4).

    Provides realm lookup and sentinel-to-realm mapping for petition routing.

    Constitutional Constraints:
    - HP-3: Valid routing targets for petitions
    - HP-4: Sentinel-to-realm mapping for triage
    - NFR-7.3: Knight capacity limits

    Attributes:
        _client: Supabase client for database queries.
    """

    def __init__(self, client: SupabaseClient) -> None:
        """Initialize the realm registry service.

        Args:
            client: Supabase client instance.
        """
        self._client = client
        self._init_logger(component="petition")

    @staticmethod
    def _coerce_rows(data: object) -> list[dict[str, Any]]:
        """Normalize Supabase response payloads to a list of row dicts."""
        if not isinstance(data, list):
            return []
        return [row for row in data if isinstance(row, dict)]

    def _row_to_realm(self, row: dict) -> Realm:
        """Convert database row to Realm domain object.

        Args:
            row: Database row dictionary.

        Returns:
            Realm domain object.
        """
        return Realm(
            id=UUID(row["id"]),
            name=row["name"],
            display_name=row["display_name"],
            knight_capacity=row["knight_capacity"],
            status=RealmStatus(row["status"]),
            description=row.get("description"),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def get_realm_by_id(self, realm_id: UUID) -> Realm | None:
        """Retrieve a realm by its UUID.

        Args:
            realm_id: The UUID of the realm to retrieve.

        Returns:
            The Realm if found, None otherwise.
        """
        log = self._log_operation("get_realm_by_id", realm_id=str(realm_id))

        result = (
            self._client.table("realms").select("*").eq("id", str(realm_id)).execute()
        )

        rows = self._coerce_rows(result.data)
        if not rows:
            log.debug("realm_not_found")
            return None

        log.debug("realm_found", name=rows[0]["name"])
        return self._row_to_realm(rows[0])

    def get_realm_by_name(self, name: str) -> Realm | None:
        """Retrieve a realm by its canonical name.

        Constitutional Constraint (HP-3): Valid routing target lookup.

        Args:
            name: Canonical realm name (e.g., "realm_privacy_discretion_services").

        Returns:
            The Realm if found, None otherwise.
        """
        log = self._log_operation("get_realm_by_name", realm_name=name)

        result = self._client.table("realms").select("*").eq("name", name).execute()

        rows = self._coerce_rows(result.data)
        if not rows:
            log.debug("realm_not_found")
            return None

        log.debug("realm_found", realm_id=rows[0]["id"])
        return self._row_to_realm(rows[0])

    def list_active_realms(self) -> list[Realm]:
        """List all active realms in the registry.

        Constitutional Constraint (HP-3): Query all valid routing targets.

        Returns:
            List of Realm objects with status ACTIVE.
        """
        log = self._log_operation("list_active_realms")

        result = (
            self._client.table("realms")
            .select("*")
            .eq("status", RealmStatus.ACTIVE.value)
            .order("name")
            .execute()
        )

        rows = self._coerce_rows(result.data)
        realms = [self._row_to_realm(row) for row in rows]
        log.debug("active_realms_listed", count=len(realms))
        return realms

    def list_all_realms(self) -> list[Realm]:
        """List all realms in the registry regardless of status.

        Returns:
            List of all Realm objects.
        """
        log = self._log_operation("list_all_realms")

        result = self._client.table("realms").select("*").order("name").execute()

        rows = self._coerce_rows(result.data)
        realms = [self._row_to_realm(row) for row in rows]
        log.debug("all_realms_listed", count=len(realms))
        return realms

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
        log = self._log_operation(
            "get_realms_for_sentinel", sentinel_type=sentinel_type
        )

        # Query sentinel_realm_mappings joined with realms
        result = (
            self._client.table("sentinel_realm_mappings")
            .select("realm_id, priority, realms(*)")
            .eq("sentinel_type", sentinel_type)
            .order("priority")
            .execute()
        )

        realms: list[Realm] = []
        for row in self._coerce_rows(result.data):
            realm_data = row.get("realms")
            if (
                isinstance(realm_data, dict)
                and realm_data.get("status") == RealmStatus.ACTIVE.value
            ):
                realms.append(self._row_to_realm(realm_data))

        log.debug("realms_for_sentinel", count=len(realms))
        return realms

    def get_default_realm(self) -> Realm | None:
        """Get the default fallback realm for routing.

        Used when no specific realm mapping exists for a petition.

        Returns:
            The first active realm (by name), or None if no active realms.
        """
        log = self._log_operation("get_default_realm")

        result = (
            self._client.table("realms")
            .select("*")
            .eq("status", RealmStatus.ACTIVE.value)
            .order("name")
            .limit(1)
            .execute()
        )

        rows = self._coerce_rows(result.data)
        if not rows:
            log.warning("no_default_realm_available")
            return None

        realm = self._row_to_realm(rows[0])
        log.debug("default_realm_found", realm_name=realm.name)
        return realm

    def is_realm_available(self, realm_id: UUID) -> bool:
        """Check if a realm is active and available for routing.

        Args:
            realm_id: The UUID of the realm to check.

        Returns:
            True if realm exists and is ACTIVE, False otherwise.
        """
        log = self._log_operation("is_realm_available", realm_id=str(realm_id))

        result = (
            self._client.table("realms")
            .select("status")
            .eq("id", str(realm_id))
            .execute()
        )

        rows = self._coerce_rows(result.data)
        if not rows:
            log.debug("realm_not_found")
            return False

        is_active = rows[0]["status"] == RealmStatus.ACTIVE.value
        log.debug("realm_availability_checked", is_active=is_active)
        return is_active

    def get_realm_knight_capacity(self, realm_id: UUID) -> int | None:
        """Get the knight capacity for a realm.

        Constitutional Constraint (NFR-7.3): Capacity limits for referrals.

        Args:
            realm_id: The UUID of the realm.

        Returns:
            Knight capacity integer if realm exists, None otherwise.
        """
        log = self._log_operation("get_realm_knight_capacity", realm_id=str(realm_id))

        result = (
            self._client.table("realms")
            .select("knight_capacity")
            .eq("id", str(realm_id))
            .execute()
        )

        rows = self._coerce_rows(result.data)
        if not rows:
            log.debug("realm_not_found")
            return None

        capacity = rows[0]["knight_capacity"]
        log.debug("knight_capacity_retrieved", capacity=capacity)
        return capacity
