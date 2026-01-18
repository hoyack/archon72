"""Public cessation triggers service (Story 7.7, FR134).

This service provides public access to cessation trigger conditions.
It reads from the constitutional threshold registry and caches results.

Constitutional Constraints:
- FR134: Public documentation of cessation trigger conditions
- FR33: Threshold definitions SHALL be constitutional, not operational
- CT-11: Silent failure destroys legitimacy -> Service must be reliable
- CT-13: Integrity outranks availability -> Cache must not serve stale data

Developer Golden Rules:
1. REGISTRY SOURCE OF TRUTH - All thresholds from CONSTITUTIONAL_THRESHOLD_REGISTRY
2. PUBLIC READ - No authentication required
3. CACHE INVALIDATION - Cache invalidated on threshold change events
4. READ-ONLY SURVIVES - This endpoint MUST work after cessation

Usage:
    from src.application.services.public_triggers_service import PublicTriggersService

    # Create service (typically via dependency injection)
    service = PublicTriggersService()

    # Get all trigger conditions
    conditions = service.get_trigger_conditions()

    # Get single trigger condition by type
    condition = service.get_trigger_condition("breach_threshold")
"""

from __future__ import annotations

from datetime import datetime, timezone

import structlog

from src.domain.models.cessation_trigger_condition import (
    CessationTriggerCondition,
    CessationTriggerConditionSet,
)

logger = structlog.get_logger(__name__)


class PublicTriggersService:
    """Service for public access to cessation trigger conditions (FR134).

    This service provides read-only access to cessation trigger conditions.
    All threshold values are sourced from CONSTITUTIONAL_THRESHOLD_REGISTRY.

    The service caches the trigger conditions for performance but
    invalidates the cache when threshold change events occur.

    Constitutional Constraint (FR134):
    Public documentation of cessation trigger conditions SHALL include
    all automatic trigger types with their thresholds and descriptions.

    Constitutional Constraint (CT-11):
    Silent failure destroys legitimacy. This service MUST return
    accurate data or raise an exception - never silently return stale data.

    Attributes:
        _cached_conditions: Cached CessationTriggerConditionSet.
        _cache_timestamp: When the cache was last refreshed.

    Example:
        >>> service = PublicTriggersService()
        >>> conditions = service.get_trigger_conditions()
        >>> len(conditions.conditions)
        5
    """

    def __init__(self) -> None:
        """Initialize the public triggers service.

        Creates the service with an empty cache that will be populated
        on first access.
        """
        self._cached_conditions: CessationTriggerConditionSet | None = None
        self._cache_timestamp: datetime | None = None
        self._log = logger.bind(service="public_triggers_service")

    def get_trigger_conditions(
        self, *, include_json_ld: bool = False
    ) -> CessationTriggerConditionSet:
        """Get all cessation trigger conditions (FR134).

        Returns the complete set of trigger conditions with version
        metadata. Results are cached for performance.

        Constitutional Constraint (FR134):
        All cessation trigger conditions SHALL be publicly documented.

        Args:
            include_json_ld: If True, returned data includes JSON-LD context
                            for semantic interoperability.

        Returns:
            CessationTriggerConditionSet with all trigger conditions.

        Example:
            >>> service = PublicTriggersService()
            >>> conditions = service.get_trigger_conditions()
            >>> len(conditions.conditions)
            5
        """
        if self._cached_conditions is None:
            self._refresh_cache()

        assert self._cached_conditions is not None  # For type checker
        self._log.debug(
            "trigger_conditions_accessed",
            condition_count=len(self._cached_conditions.conditions),
            cache_age_seconds=(
                (datetime.now(timezone.utc) - self._cache_timestamp).total_seconds()
                if self._cache_timestamp
                else 0
            ),
        )

        return self._cached_conditions

    def get_trigger_condition(
        self, trigger_type: str
    ) -> CessationTriggerCondition | None:
        """Get a specific trigger condition by type (FR134).

        Looks up a single trigger condition by its trigger_type identifier.

        Args:
            trigger_type: The trigger_type to look up (e.g., "breach_threshold").

        Returns:
            The CessationTriggerCondition if found, None otherwise.

        Example:
            >>> service = PublicTriggersService()
            >>> condition = service.get_trigger_condition("breach_threshold")
            >>> condition.threshold
            10
        """
        conditions = self.get_trigger_conditions()
        result = conditions.get_condition(trigger_type)

        if result is None:
            self._log.debug(
                "trigger_condition_not_found",
                trigger_type=trigger_type,
            )
        else:
            self._log.debug(
                "trigger_condition_accessed",
                trigger_type=trigger_type,
                threshold=result.threshold,
            )

        return result

    def invalidate_cache(self) -> None:
        """Invalidate the cached trigger conditions.

        Called when a threshold change event is detected.
        The next call to get_trigger_conditions() will refresh from registry.

        Constitutional Constraint (CT-11):
        Silent failure destroys legitimacy. Cache invalidation ensures
        we never serve stale data after threshold changes.
        """
        self._cached_conditions = None
        self._cache_timestamp = None
        self._log.info("trigger_conditions_cache_invalidated")

    def _refresh_cache(self) -> None:
        """Refresh the cached trigger conditions from registry.

        Loads fresh data from CONSTITUTIONAL_THRESHOLD_REGISTRY.

        Constitutional Constraint (FR33):
        Threshold definitions SHALL be constitutional, not operational.
        This method reads from the constitutional registry.
        """
        self._cached_conditions = CessationTriggerConditionSet.from_registry()
        self._cache_timestamp = datetime.now(timezone.utc)
        self._log.info(
            "trigger_conditions_cache_refreshed",
            condition_count=len(self._cached_conditions.conditions),
            schema_version=self._cached_conditions.schema_version,
            constitution_version=self._cached_conditions.constitution_version,
        )

    def get_cache_status(self) -> dict[str, object]:
        """Get cache status for monitoring.

        Returns dict with cache_populated, cache_age_seconds, condition_count.

        Returns:
            Dict with cache status information.
        """
        if self._cached_conditions is None:
            return {
                "cache_populated": False,
                "cache_age_seconds": None,
                "condition_count": 0,
            }

        cache_age = (
            (datetime.now(timezone.utc) - self._cache_timestamp).total_seconds()
            if self._cache_timestamp
            else 0
        )

        return {
            "cache_populated": True,
            "cache_age_seconds": cache_age,
            "condition_count": len(self._cached_conditions.conditions),
        }
