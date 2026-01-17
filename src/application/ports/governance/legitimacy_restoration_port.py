"""Port interface for explicit legitimacy restoration operations.

This module defines the LegitimacyRestorationPort protocol that specifies the
interface for human-acknowledged restoration of legitimacy bands.

Key Principles:
- Restoration requires explicit human acknowledgment (FR30)
- No automatic upward transitions allowed (FR32)
- Only one band up at a time (gradual restoration)
- FAILED state is terminal (reconstitution required)

Constitutional Compliance:
- FR30: Human Operator can acknowledge and execute upward legitimacy transition
- FR31: System can record all legitimacy transitions in append-only ledger
- FR32: System can prevent upward transitions without explicit acknowledgment
- NFR-CONST-04: All transitions logged with timestamp, actor, reason
"""

from datetime import datetime
from typing import Optional, Protocol
from uuid import UUID

from src.domain.governance.legitimacy.restoration_acknowledgment import (
    RestorationAcknowledgment,
    RestorationRequest,
    RestorationResult,
)

# Re-export domain models for convenience
__all__ = [
    "LegitimacyRestorationPort",
    "RestorationAcknowledgment",
    "RestorationRequest",
    "RestorationResult",
]


class LegitimacyRestorationPort(Protocol):
    """Port for explicit legitimacy restoration operations.

    This protocol defines the interface for:
    - Processing restoration requests with human acknowledgment
    - Enforcing one-step-at-a-time constraint
    - Blocking restoration from FAILED (terminal) state
    - Recording acknowledgments in append-only ledger

    Implementations must ensure:
    - Only authorized operators can restore
    - Each restoration is one band at a time
    - All restorations are logged with full context
    - FAILED state cannot be restored (reconstitution required)
    """

    async def request_restoration(
        self,
        request: RestorationRequest,
    ) -> RestorationResult:
        """Request legitimacy restoration with acknowledgment.

        This method:
        1. Verifies operator authorization (Human Operator rank)
        2. Validates target band is exactly one step up
        3. Blocks if current state is FAILED (terminal)
        4. Creates and records acknowledgment
        5. Executes the transition
        6. Emits band_increased event

        Args:
            request: The restoration request with operator, target, reason, evidence.

        Returns:
            RestorationResult indicating success or failure.

        Errors captured in result (not raised):
            - Unauthorized operator
            - Multi-step restoration attempt
            - FAILED state restoration attempt
            - Invalid target band
        """
        ...

    async def get_restoration_history(
        self,
        since: Optional[datetime] = None,
        limit: Optional[int] = None,
    ) -> list[RestorationAcknowledgment]:
        """Get history of restoration acknowledgments.

        Returns acknowledgment records for past restorations.

        Args:
            since: Only return acknowledgments after this time.
            limit: Maximum number of acknowledgments to return.

        Returns:
            List of RestorationAcknowledgment records, oldest first.
        """
        ...

    async def get_acknowledgment(
        self,
        acknowledgment_id: UUID,
    ) -> Optional[RestorationAcknowledgment]:
        """Get a specific acknowledgment by ID.

        Args:
            acknowledgment_id: The unique ID of the acknowledgment.

        Returns:
            The acknowledgment record, or None if not found.
        """
        ...

    async def get_restoration_count(self) -> int:
        """Get total number of successful restorations.

        Returns:
            Count of successful restoration operations.
        """
        ...
