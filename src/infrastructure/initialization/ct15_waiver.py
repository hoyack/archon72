"""CT-15 waiver initialization for MVP scope (Story 9.8, SC-4, SR-10).

This module provides constants and initialization logic for the CT-15 waiver.
CT-15 ("Legitimacy requires consent") is waived for MVP as consent mechanisms
require Seeker-facing features that are out of MVP scope.

Constitutional Constraints:
- SC-4: Epic 9 missing consent -> CT-15 deferred to Phase 2
- SR-10: CT-15 waiver documentation -> Must be explicit and tracked
- CT-12: Witnessing creates accountability -> Waiver events witnessed

References:
- _bmad-output/planning-artifacts/epics.md#Story-9.8
- docs/constitutional-implementation-rules.md
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.application.ports.waiver_repository import WaiverRecord

if TYPE_CHECKING:
    from src.application.services.waiver_documentation_service import (
        WaiverDocumentationService,
    )


# CT-15 Waiver Constants (SC-4, SR-10)
CT15_WAIVER_ID: str = "CT-15-MVP-WAIVER"
"""Unique identifier for the CT-15 MVP waiver."""

CT15_STATEMENT: str = "Legitimacy requires consent"
"""Full text of Constitutional Truth 15."""

CT15_WAIVED_DESCRIPTION: str = (
    "Full implementation of consent mechanisms for participant legitimacy. "
    "This includes: Seeker consent capture, Observer acknowledgment flows, "
    "consent verification services, and user profile consent management."
)
"""Description of what specific requirements are waived."""

CT15_RATIONALE: str = (
    "MVP focuses on constitutional infrastructure - the core mechanics that make "
    "the system trustworthy: event store with cryptographic verification, halt and "
    "fork detection, breach and threshold enforcement, override accountability, and "
    "cessation protocols. Consent mechanisms require Seeker-facing features that are "
    "out of MVP scope (Phase 2: Seeker Journey implementation)."
)
"""Detailed rationale for the waiver."""

CT15_TARGET_PHASE: str = "Phase 2 - Seeker Journey"
"""When the waived requirement will be addressed."""


async def initialize_ct15_waiver(
    service: WaiverDocumentationService,
) -> WaiverRecord:
    """Initialize the CT-15 waiver for MVP scope (SC-4, SR-10).

    This function is idempotent - if the waiver already exists, it returns
    the existing waiver without creating a new event.

    Can be called during application startup to ensure the CT-15 waiver
    is properly documented before Epic 9 completion.

    Constitutional Constraints:
    - SC-4: Epic 9 missing consent -> CT-15 deferred to Phase 2
    - SR-10: CT-15 waiver documentation -> Must be explicit
    - CT-11: HALT CHECK FIRST (delegated to service)
    - CT-12: Waiver documentation creates witnessed event

    Args:
        service: WaiverDocumentationService for documenting the waiver.

    Returns:
        WaiverRecord for the CT-15 waiver.

    Raises:
        SystemHaltedError: If system is halted (CT-11).

    Example:
        # During application startup
        waiver = await initialize_ct15_waiver(waiver_service)
        logger.info("CT-15 waiver initialized", waiver_id=waiver.waiver_id)
    """
    return await service.document_waiver(
        waiver_id=CT15_WAIVER_ID,
        ct_id="CT-15",
        ct_statement=CT15_STATEMENT,
        what_is_waived=CT15_WAIVED_DESCRIPTION,
        rationale=CT15_RATIONALE,
        target_phase=CT15_TARGET_PHASE,
    )
