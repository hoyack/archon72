"""Emergence Violation Breach Service (Story 9.6, FR109).

Creates constitutional breaches for emergence language violations.
Integrates with BreachDeclarationService for witnessed breach events.

Constitutional Constraints:
- FR109: Emergence violations create constitutional breaches
- FR55: No emergence claims (the violated requirement)
- FR31: 7-day escalation timer starts automatically
- CT-11: Silent failure destroys legitimacy -> HALT CHECK FIRST
- CT-12: All breaches witnessed via BreachDeclarationService

Developer Golden Rules:
1. HALT CHECK FIRST - Check halt state before every operation
2. WITNESS EVERYTHING - Delegated to BreachDeclarationService
3. FAIL LOUD - Raise errors for all failures
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from structlog import get_logger

from src.application.ports.halt_checker import HaltChecker
from src.domain.errors.writer import SystemHaltedError
from src.domain.events.breach import (
    BreachEventPayload,
    BreachSeverity,
    BreachType,
)

if TYPE_CHECKING:
    from src.application.services.breach_declaration_service import (
        BreachDeclarationService,
    )

logger = get_logger()

# Violated requirement for all emergence violations (FR55)
EMERGENCE_VIOLATED_REQUIREMENT: str = "FR55"


class EmergenceViolationBreachService:
    """Creates constitutional breaches for emergence violations (FR109).

    This service wraps BreachDeclarationService to provide emergence-specific
    breach creation. When an emergence violation is detected by the
    ProhibitedLanguageBlockingService, this service creates the corresponding
    constitutional breach.

    Constitutional Constraints:
    - FR109: Emergence violations create constitutional breaches
    - FR55: The violated requirement (no emergence claims)
    - FR31: 7-day escalation timer starts automatically (via existing infrastructure)
    - CT-11: HALT CHECK FIRST
    - CT-12: All breaches witnessed via BreachDeclarationService

    Developer Golden Rules:
    1. HALT CHECK FIRST - Every operation checks halt state
    2. WITNESS EVERYTHING - Delegated to BreachDeclarationService
    3. FAIL LOUD - Raise specific errors for failures

    Example:
        service = EmergenceViolationBreachService(
            breach_service=breach_declaration_service,
            halt_checker=halt_checker,
        )

        # When a violation is detected
        breach = await service.create_breach_for_violation(
            violation_event_id=event_id,
            content_id="output-123",
            matched_terms=("emergence", "consciousness"),
            detection_method="keyword_scan",
        )
    """

    def __init__(
        self,
        breach_service: BreachDeclarationService,
        halt_checker: HaltChecker,
    ) -> None:
        """Initialize the Emergence Violation Breach Service.

        Args:
            breach_service: Service for creating witnessed breaches (CT-12).
            halt_checker: Interface to check system halt state (CT-11).
        """
        self._breach_service = breach_service
        self._halt_checker = halt_checker

    async def create_breach_for_violation(
        self,
        violation_event_id: UUID,
        content_id: str,
        matched_terms: tuple[str, ...],
        detection_method: str,
    ) -> BreachEventPayload:
        """Create constitutional breach for emergence violation (FR109).

        This method creates a BreachEvent with type EMERGENCE_VIOLATION
        when prohibited language is detected. The 7-day escalation timer
        starts automatically via the existing breach infrastructure (FR31).

        Constitutional Constraints:
        - FR109: Emergence violations create constitutional breaches
        - FR55: Violated requirement for all emergence violations
        - CT-11: HALT CHECK FIRST
        - CT-12: Event is witnessed (delegated to BreachDeclarationService)

        Args:
            violation_event_id: UUID of the ProhibitedLanguageBlockedEvent.
            content_id: Identifier of the blocked content.
            matched_terms: Terms that triggered the violation.
            detection_method: How violation was detected (e.g., "keyword_scan").

        Returns:
            The created BreachEventPayload.

        Raises:
            SystemHaltedError: If system is halted (CT-11).
            BreachDeclarationError: If breach creation fails.
        """
        log = logger.bind(
            operation="create_breach_for_violation",
            violation_event_id=str(violation_event_id),
            content_id=content_id,
            matched_terms=matched_terms,
            detection_method=detection_method,
        )

        # =====================================================================
        # HALT CHECK FIRST (Developer Golden Rule, CT-11)
        # =====================================================================
        if await self._halt_checker.is_halted():
            reason = await self._halt_checker.get_halt_reason()
            log.critical(
                "emergence_breach_rejected_system_halted",
                halt_reason=reason,
            )
            raise SystemHaltedError(f"CT-11: System is halted: {reason}")

        # =====================================================================
        # Create breach via existing infrastructure (FR109, CT-12)
        # =====================================================================
        log.info(
            "creating_emergence_violation_breach",
            message="FR109: Creating constitutional breach for emergence violation",
        )

        breach = await self._breach_service.declare_breach(
            breach_type=BreachType.EMERGENCE_VIOLATION,
            violated_requirement=EMERGENCE_VIOLATED_REQUIREMENT,
            severity=BreachSeverity.HIGH,  # Page immediately
            details={
                "content_id": content_id,
                "matched_terms": list(matched_terms),
                "detection_method": detection_method,
                "violation_event_id": str(violation_event_id),
            },
            source_event_id=violation_event_id,
        )

        log.warning(
            "fr109_emergence_violation_breach_created",
            breach_id=str(breach.breach_id),
            severity=breach.severity.value,
            message="FR109: Emergence violation recorded as constitutional breach",
        )

        return breach
