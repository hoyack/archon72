"""Waiver documentation service for constitutional waivers (Story 9.8, SC-4, SR-10).

This service coordinates waiver documentation, persistence, and event creation.
All waiver operations create witnessed constitutional events.

Constitutional Constraints:
- SC-4: Epic 9 missing consent -> CT-15 deferred to Phase 2
- SR-10: CT-15 waiver documentation -> Must be explicit and tracked
- CT-11: Silent failure destroys legitimacy -> HALT CHECK FIRST
- CT-12: Witnessing creates accountability -> All waiver events witnessed

Developer Golden Rules:
1. HALT CHECK FIRST - Check halt state before every operation
2. WITNESS EVERYTHING - Waiver documentation creates witnessed events
3. FAIL LOUD - Never silently swallow waiver errors
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from src.application.ports.halt_checker import HaltChecker
from src.application.ports.waiver_repository import (
    WaiverRecord,
    WaiverRepositoryProtocol,
)
from src.domain.errors import SystemHaltedError
from src.domain.events.waiver import (
    WAIVER_DOCUMENTED_EVENT_TYPE,
    WAIVER_SYSTEM_AGENT_ID,
    WaiverDocumentedEventPayload,
    WaiverStatus,
)

if TYPE_CHECKING:
    from src.application.services.event_writer_service import EventWriterService


# System agent ID for waiver documentation service
WAIVER_DOCUMENTATION_SYSTEM_AGENT_ID: str = WAIVER_SYSTEM_AGENT_ID


class WaiverDocumentationService:
    """Service for documenting constitutional waivers (Story 9.8, SC-4, SR-10).

    This service provides operations for creating, retrieving, and managing
    constitutional waivers. All operations are witnessed via the EventWriterService.

    Constitutional Constraints:
    - SC-4: Epic 9 missing consent -> CT-15 deferred to Phase 2
    - SR-10: CT-15 waiver documentation -> Must be explicit
    - CT-11: HALT CHECK FIRST on every operation
    - CT-12: All waiver events must be witnessed

    Example:
        service = WaiverDocumentationService(
            waiver_repository=repo,
            event_writer=writer,
            halt_checker=halt_checker,
        )

        waiver = await service.document_waiver(
            waiver_id="CT-15-MVP-WAIVER",
            ct_id="CT-15",
            ct_statement="Legitimacy requires consent",
            what_is_waived="Full consent mechanism implementation",
            rationale="MVP focuses on constitutional infrastructure",
            target_phase="Phase 2 - Seeker Journey",
        )
    """

    def __init__(
        self,
        waiver_repository: WaiverRepositoryProtocol,
        event_writer: EventWriterService,
        halt_checker: HaltChecker,
    ) -> None:
        """Initialize the waiver documentation service.

        Args:
            waiver_repository: Repository for waiver persistence.
            event_writer: Service for creating witnessed events.
            halt_checker: Interface for checking halt state.
        """
        self._repository = waiver_repository
        self._event_writer = event_writer
        self._halt_checker = halt_checker

    async def document_waiver(
        self,
        waiver_id: str,
        ct_id: str,
        ct_statement: str,
        what_is_waived: str,
        rationale: str,
        target_phase: str,
        documented_by: str = WAIVER_DOCUMENTATION_SYSTEM_AGENT_ID,
    ) -> WaiverRecord:
        """Document a constitutional waiver (SC-4, SR-10).

        Creates a new waiver record and writes a witnessed event.
        If a waiver with the same ID already exists, returns the existing waiver
        without creating a new event (idempotent).

        Constitutional Constraints:
        - CT-11: HALT CHECK FIRST
        - CT-12: Waiver documentation creates witnessed event

        Args:
            waiver_id: Unique identifier for the waiver.
            ct_id: Constitutional Truth being waived (e.g., "CT-15").
            ct_statement: Full text of the CT being waived.
            what_is_waived: Description of waived requirement.
            rationale: Detailed reason for the waiver.
            target_phase: When the requirement will be addressed.
            documented_by: Agent/system documenting the waiver.

        Returns:
            WaiverRecord for the documented waiver.

        Raises:
            SystemHaltedError: If system is halted (CT-11).
        """
        # HALT CHECK FIRST (CT-11)
        if await self._halt_checker.is_halted():
            raise SystemHaltedError("System halted - cannot document waiver")

        # Check if waiver already exists (idempotent)
        existing = await self._repository.get_waiver(waiver_id)
        if existing is not None:
            return existing

        # Create waiver record
        documented_at = datetime.now(timezone.utc)
        waiver = WaiverRecord(
            waiver_id=waiver_id,
            constitutional_truth_id=ct_id,
            constitutional_truth_statement=ct_statement,
            what_is_waived=what_is_waived,
            rationale=rationale,
            target_phase=target_phase,
            status=WaiverStatus.ACTIVE,
            documented_at=documented_at,
            documented_by=documented_by,
        )

        # Save to repository
        await self._repository.save_waiver(waiver)

        # Create witnessed event (CT-12)
        event_payload = WaiverDocumentedEventPayload(
            waiver_id=waiver_id,
            constitutional_truth_id=ct_id,
            constitutional_truth_statement=ct_statement,
            what_is_waived=what_is_waived,
            rationale=rationale,
            target_phase=target_phase,
            status=WaiverStatus.ACTIVE,
            documented_at=documented_at,
            documented_by=documented_by,
        )

        await self._event_writer.write_event(
            event_type=WAIVER_DOCUMENTED_EVENT_TYPE,
            payload=event_payload.to_dict(),
            agent_id=documented_by,
        )

        return waiver

    async def get_waiver(self, waiver_id: str) -> WaiverRecord | None:
        """Retrieve a waiver by its ID.

        Constitutional Constraints:
        - CT-11: HALT CHECK FIRST

        Args:
            waiver_id: Unique waiver identifier.

        Returns:
            WaiverRecord if found, None otherwise.

        Raises:
            SystemHaltedError: If system is halted (CT-11).
        """
        # HALT CHECK FIRST (CT-11)
        if await self._halt_checker.is_halted():
            raise SystemHaltedError("System halted - cannot retrieve waiver")

        return await self._repository.get_waiver(waiver_id)

    async def get_all_waivers(self) -> tuple[WaiverRecord, ...]:
        """Retrieve all documented waivers.

        Constitutional Constraints:
        - CT-11: HALT CHECK FIRST

        Returns:
            Tuple of all WaiverRecords.

        Raises:
            SystemHaltedError: If system is halted (CT-11).
        """
        # HALT CHECK FIRST (CT-11)
        if await self._halt_checker.is_halted():
            raise SystemHaltedError("System halted - cannot retrieve waivers")

        return await self._repository.get_all_waivers()

    async def get_active_waivers(self) -> tuple[WaiverRecord, ...]:
        """Retrieve only active waivers.

        Constitutional Constraints:
        - CT-11: HALT CHECK FIRST

        Returns:
            Tuple of active WaiverRecords.

        Raises:
            SystemHaltedError: If system is halted (CT-11).
        """
        # HALT CHECK FIRST (CT-11)
        if await self._halt_checker.is_halted():
            raise SystemHaltedError("System halted - cannot retrieve active waivers")

        return await self._repository.get_active_waivers()

    async def waiver_exists(self, waiver_id: str) -> bool:
        """Check if a waiver exists.

        Constitutional Constraints:
        - CT-11: HALT CHECK FIRST

        Args:
            waiver_id: Unique waiver identifier.

        Returns:
            True if the waiver exists, False otherwise.

        Raises:
            SystemHaltedError: If system is halted (CT-11).
        """
        # HALT CHECK FIRST (CT-11)
        if await self._halt_checker.is_halted():
            raise SystemHaltedError("System halted - cannot check waiver existence")

        return await self._repository.exists(waiver_id)
