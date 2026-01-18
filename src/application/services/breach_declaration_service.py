"""Breach Declaration Service (Story 6.1, FR30).

This service manages the declaration and querying of constitutional breaches.
All breach events are witnessed before being stored.

Constitutional Constraints:
- FR30: Breach declarations SHALL create constitutional events with
        breach_type, violated_requirement, detection_timestamp
- CT-11: Silent failure destroys legitimacy -> HALT CHECK FIRST
- CT-12: Witnessing creates accountability -> All breaches MUST be witnessed
- CT-13: Integrity outranks availability -> Availability may be sacrificed

Developer Golden Rules:
1. HALT CHECK FIRST - Check halt state before every operation
2. WITNESS EVERYTHING - All breach events must be witnessed
3. FAIL LOUD - Never silently swallow breach detection
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import MappingProxyType
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from structlog import get_logger

from src.application.ports.breach_repository import BreachRepositoryProtocol
from src.application.ports.halt_checker import HaltChecker
from src.domain.errors.breach import BreachDeclarationError, BreachQueryError
from src.domain.errors.writer import SystemHaltedError
from src.domain.events.breach import (
    BREACH_DECLARED_EVENT_TYPE,
    BreachEventPayload,
    BreachSeverity,
    BreachType,
)

if TYPE_CHECKING:
    from src.application.services.event_writer_service import EventWriterService

logger = get_logger()

# System agent ID for breach declaration events
BREACH_DECLARATION_SYSTEM_AGENT_ID: str = "breach_declaration_system"


class BreachDeclarationService:
    """Manages constitutional breach declarations (FR30).

    This service provides:
    1. Breach declaration with witnessed events (FR30, CT-12)
    2. Breach querying with filtering (FR30)
    3. Halt-aware operations (CT-11)

    Constitutional Constraints:
    - FR30: Breach declarations create events with breach_type,
            violated_requirement, detection_timestamp
    - CT-11: HALT CHECK FIRST at every operation
    - CT-12: All breach events MUST be witnessed

    Developer Golden Rules:
    1. HALT CHECK FIRST - Every operation checks halt state
    2. WITNESS EVERYTHING - All events are witnessed via EventWriterService
    3. FAIL LOUD - Raise specific errors for failures
    """

    def __init__(
        self,
        breach_repository: BreachRepositoryProtocol,
        event_writer: EventWriterService,
        halt_checker: HaltChecker,
    ) -> None:
        """Initialize the Breach Declaration Service.

        Args:
            breach_repository: Repository for breach storage and queries.
            event_writer: Service for writing witnessed events (CT-12).
            halt_checker: Interface to check system halt state (CT-11).
        """
        self._repository = breach_repository
        self._event_writer = event_writer
        self._halt_checker = halt_checker

    async def declare_breach(
        self,
        breach_type: BreachType,
        violated_requirement: str,
        severity: BreachSeverity,
        details: dict[str, Any],
        source_event_id: UUID | None = None,
    ) -> BreachEventPayload:
        """Declare a constitutional breach (FR30).

        Creates a breach event, witnesses it, and stores it for querying.

        Constitutional Constraints:
        - FR30: Creates event with breach_type, violated_requirement, detection_timestamp
        - CT-11: HALT CHECK FIRST
        - CT-12: Event is witnessed via EventWriterService

        Args:
            breach_type: Category of the constitutional violation.
            violated_requirement: The FR/CT/NFR violated (e.g., "FR30", "CT-11").
            severity: Alert severity level.
            details: Additional context about the breach.
            source_event_id: Optional ID of the event that triggered this breach.

        Returns:
            The created BreachEventPayload.

        Raises:
            SystemHaltedError: If system is halted (CT-11).
            BreachDeclarationError: If declaration fails.
        """
        log = logger.bind(
            operation="declare_breach",
            breach_type=breach_type.value,
            violated_requirement=violated_requirement,
            severity=severity.value,
        )

        # =====================================================================
        # HALT CHECK FIRST (Developer Golden Rule, CT-11)
        # =====================================================================
        if await self._halt_checker.is_halted():
            reason = await self._halt_checker.get_halt_reason()
            log.critical(
                "breach_declaration_rejected_system_halted",
                halt_reason=reason,
            )
            raise SystemHaltedError(f"CT-11: System is halted: {reason}")

        # =====================================================================
        # Create breach payload (FR30)
        # =====================================================================
        breach_id = uuid4()
        detection_timestamp = datetime.now(timezone.utc)

        payload = BreachEventPayload(
            breach_id=breach_id,
            breach_type=breach_type,
            violated_requirement=violated_requirement,
            severity=severity,
            detection_timestamp=detection_timestamp,
            details=MappingProxyType(details),
            source_event_id=source_event_id,
        )

        log = log.bind(breach_id=str(breach_id))

        try:
            # =================================================================
            # Write witnessed event (CT-12)
            # =================================================================
            event_payload: dict[str, Any] = {
                "breach_id": str(payload.breach_id),
                "breach_type": payload.breach_type.value,
                "violated_requirement": payload.violated_requirement,
                "severity": payload.severity.value,
                "detection_timestamp": payload.detection_timestamp.isoformat(),
                "details": payload.details,
            }
            if payload.source_event_id is not None:
                event_payload["source_event_id"] = str(payload.source_event_id)

            await self._event_writer.write_event(
                event_type=BREACH_DECLARED_EVENT_TYPE,
                payload=event_payload,
                agent_id=BREACH_DECLARATION_SYSTEM_AGENT_ID,
                local_timestamp=detection_timestamp,
            )

            # =================================================================
            # Save to repository for queries
            # =================================================================
            await self._repository.save(payload)

            log.info(
                "breach_declared",
                message="Constitutional breach declared and witnessed",
            )

            return payload

        except SystemHaltedError:
            # Re-raise halt errors directly
            raise

        except Exception as e:
            log.error(
                "breach_declaration_failed",
                error=str(e),
            )
            raise BreachDeclarationError(f"FR30: Failed to declare breach: {e}") from e

    async def get_breach_by_id(self, breach_id: UUID) -> BreachEventPayload | None:
        """Retrieve a specific breach by ID.

        Constitutional Constraint (CT-11):
        HALT CHECK FIRST - System halt is checked before query.

        Args:
            breach_id: The unique identifier of the breach.

        Returns:
            The breach event payload if found, None otherwise.

        Raises:
            SystemHaltedError: If system is halted (CT-11).
            BreachQueryError: If query fails.
        """
        log = logger.bind(
            operation="get_breach_by_id",
            breach_id=str(breach_id),
        )

        # =====================================================================
        # HALT CHECK FIRST (Developer Golden Rule, CT-11)
        # =====================================================================
        if await self._halt_checker.is_halted():
            reason = await self._halt_checker.get_halt_reason()
            log.critical(
                "breach_query_rejected_system_halted",
                halt_reason=reason,
            )
            raise SystemHaltedError(f"CT-11: System is halted: {reason}")

        try:
            result = await self._repository.get_by_id(breach_id)
            log.info(
                "breach_retrieved",
                found=result is not None,
            )
            return result

        except SystemHaltedError:
            raise

        except Exception as e:
            log.error(
                "breach_query_failed",
                error=str(e),
            )
            raise BreachQueryError(
                f"FR30: Failed to retrieve breach {breach_id}: {e}"
            ) from e

    async def list_all_breaches(self) -> list[BreachEventPayload]:
        """Retrieve all breach events.

        Constitutional Constraint (CT-11):
        HALT CHECK FIRST - System halt is checked before query.

        Returns:
            List of all stored breach events.

        Raises:
            SystemHaltedError: If system is halted (CT-11).
            BreachQueryError: If query fails.
        """
        log = logger.bind(operation="list_all_breaches")

        # =====================================================================
        # HALT CHECK FIRST (Developer Golden Rule, CT-11)
        # =====================================================================
        if await self._halt_checker.is_halted():
            reason = await self._halt_checker.get_halt_reason()
            log.critical(
                "breach_list_rejected_system_halted",
                halt_reason=reason,
            )
            raise SystemHaltedError(f"CT-11: System is halted: {reason}")

        try:
            results = await self._repository.list_all()
            log.info(
                "breaches_listed",
                count=len(results),
            )
            return results

        except SystemHaltedError:
            raise

        except Exception as e:
            log.error(
                "breach_list_failed",
                error=str(e),
            )
            raise BreachQueryError(f"FR30: Failed to list breaches: {e}") from e

    async def filter_breaches(
        self,
        breach_type: BreachType | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[BreachEventPayload]:
        """Filter breach events by type and/or date range (FR30).

        Constitutional Constraint (CT-11):
        HALT CHECK FIRST - System halt is checked before query.

        Args:
            breach_type: Optional breach type filter.
            start_date: Optional start of date range (inclusive).
            end_date: Optional end of date range (inclusive).

        Returns:
            List of breach events matching the filters.
            If no filters provided, returns all breaches.

        Raises:
            SystemHaltedError: If system is halted (CT-11).
            BreachQueryError: If query fails.
        """
        log = logger.bind(
            operation="filter_breaches",
            breach_type=breach_type.value if breach_type else None,
            start_date=start_date.isoformat() if start_date else None,
            end_date=end_date.isoformat() if end_date else None,
        )

        # =====================================================================
        # HALT CHECK FIRST (Developer Golden Rule, CT-11)
        # =====================================================================
        if await self._halt_checker.is_halted():
            reason = await self._halt_checker.get_halt_reason()
            log.critical(
                "breach_filter_rejected_system_halted",
                halt_reason=reason,
            )
            raise SystemHaltedError(f"CT-11: System is halted: {reason}")

        try:
            # Determine which repository method to use based on filters
            if (
                breach_type is not None
                and start_date is not None
                and end_date is not None
            ):
                # Both type and date range
                results = await self._repository.filter_by_type_and_date(
                    breach_type=breach_type,
                    start=start_date,
                    end=end_date,
                )
            elif breach_type is not None:
                # Type only
                results = await self._repository.filter_by_type(breach_type)
            elif start_date is not None and end_date is not None:
                # Date range only
                results = await self._repository.filter_by_date_range(
                    start=start_date,
                    end=end_date,
                )
            else:
                # No filters - return all
                results = await self._repository.list_all()

            log.info(
                "breaches_filtered",
                count=len(results),
            )
            return results

        except SystemHaltedError:
            raise

        except Exception as e:
            log.error(
                "breach_filter_failed",
                error=str(e),
            )
            raise BreachQueryError(f"FR30: Failed to filter breaches: {e}") from e

    async def count_unacknowledged_breaches(self, window_days: int = 90) -> int:
        """Count unacknowledged breaches within a rolling window.

        This supports Story 6.3's cessation trigger: >10 unacknowledged
        breaches in 90 days triggers cessation consideration.

        Constitutional Constraint (CT-11):
        HALT CHECK FIRST - System halt is checked before query.

        Args:
            window_days: Rolling window in days (default: 90).

        Returns:
            Count of unacknowledged breaches in the window.

        Raises:
            SystemHaltedError: If system is halted (CT-11).
            BreachQueryError: If query fails.
        """
        log = logger.bind(
            operation="count_unacknowledged_breaches",
            window_days=window_days,
        )

        # =====================================================================
        # HALT CHECK FIRST (Developer Golden Rule, CT-11)
        # =====================================================================
        if await self._halt_checker.is_halted():
            reason = await self._halt_checker.get_halt_reason()
            log.critical(
                "breach_count_rejected_system_halted",
                halt_reason=reason,
            )
            raise SystemHaltedError(f"CT-11: System is halted: {reason}")

        try:
            count = await self._repository.count_unacknowledged_in_window(window_days)
            log.info(
                "unacknowledged_breaches_counted",
                count=count,
            )
            return count

        except SystemHaltedError:
            raise

        except Exception as e:
            log.error(
                "breach_count_failed",
                error=str(e),
            )
            raise BreachQueryError(
                f"FR30: Failed to count unacknowledged breaches: {e}"
            ) from e
