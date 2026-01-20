"""Escalation threshold checking service (Story 5.5, FR-5.1, FR-5.2, FR-6.5).

This module implements escalation threshold checking for the Three Fates
petition system, detecting when co-signer counts reach escalation thresholds.

Constitutional Constraints:
- FR-5.1: System SHALL ESCALATE petition when co-signer threshold reached [P0]
- FR-5.2: Escalation thresholds: CESSATION=100, GRIEVANCE=50 [P0]
- FR-6.5: System SHALL check escalation threshold on each co-sign [P0]
- FR-10.2: CESSATION petitions SHALL auto-escalate at 100 co-signers [P0]
- FR-10.3: GRIEVANCE petitions SHALL auto-escalate at 50 co-signers [P1]
- NFR-1.4: Threshold detection latency < 1 second
- CON-5: CESSATION auto-escalation threshold is immutable (100)

Developer Golden Rules:
1. DETECTION ONLY - This service detects thresholds; escalation execution is separate (Story 5.6)
2. PURE CALCULATION - No database writes, just compare count vs threshold
3. TYPE-BASED - Different petition types have different thresholds (or none)
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from structlog import get_logger

from src.application.ports.escalation_threshold import (
    EscalationThresholdCheckerProtocol,
    EscalationThresholdResult,
)

if TYPE_CHECKING:
    from src.domain.models.petition_submission import PetitionType

logger = get_logger(__name__)

# Default thresholds (CON-5: CESSATION=100 is immutable default)
DEFAULT_CESSATION_THRESHOLD = 100
DEFAULT_GRIEVANCE_THRESHOLD = 50


class EscalationThresholdService:
    """Service for checking escalation thresholds (Story 5.5, FR-6.5).

    Implements the EscalationThresholdCheckerProtocol for detecting when
    a petition's co-signer count reaches its escalation threshold.

    Constitutional Constraints:
    - FR-5.1: Detects when threshold is reached [P0]
    - FR-5.2: Uses correct thresholds per type [P0]
    - CON-5: CESSATION threshold defaults to 100 (immutable)

    Threshold Table:
    | Petition Type | Threshold | Source |
    |---------------|-----------|--------|
    | CESSATION | 100 | FR-10.2, CON-5 |
    | GRIEVANCE | 50 | FR-10.3 |
    | GENERAL | None | No auto-escalation |
    | COLLABORATION | None | No auto-escalation |

    Example:
        >>> service = EscalationThresholdService()
        >>> result = service.check_threshold(PetitionType.CESSATION, 100)
        >>> result.threshold_reached
        True
        >>> result.threshold_value
        100
    """

    def __init__(
        self,
        cessation_threshold: int | None = None,
        grievance_threshold: int | None = None,
    ) -> None:
        """Initialize the escalation threshold service.

        Args:
            cessation_threshold: Optional override for CESSATION threshold.
                               Defaults to env var CESSATION_ESCALATION_THRESHOLD or 100.
            grievance_threshold: Optional override for GRIEVANCE threshold.
                               Defaults to env var GRIEVANCE_ESCALATION_THRESHOLD or 50.
        """
        # Load from env vars with fallback to defaults
        self._cessation_threshold = cessation_threshold or int(
            os.environ.get("CESSATION_ESCALATION_THRESHOLD", DEFAULT_CESSATION_THRESHOLD)
        )
        self._grievance_threshold = grievance_threshold or int(
            os.environ.get("GRIEVANCE_ESCALATION_THRESHOLD", DEFAULT_GRIEVANCE_THRESHOLD)
        )

        logger.info(
            "Escalation threshold service initialized",
            cessation_threshold=self._cessation_threshold,
            grievance_threshold=self._grievance_threshold,
        )

    @property
    def cessation_threshold(self) -> int:
        """Get the CESSATION escalation threshold (CON-5: default 100)."""
        return self._cessation_threshold

    @property
    def grievance_threshold(self) -> int:
        """Get the GRIEVANCE escalation threshold (default 50)."""
        return self._grievance_threshold

    def get_threshold_for_type(
        self,
        petition_type: PetitionType,
    ) -> int | None:
        """Get the escalation threshold for a petition type.

        Args:
            petition_type: The type of petition.

        Returns:
            The threshold value, or None if the type has no threshold.

        Example:
            >>> service.get_threshold_for_type(PetitionType.CESSATION)
            100
            >>> service.get_threshold_for_type(PetitionType.GENERAL)
            None
        """
        from src.domain.models.petition_submission import PetitionType as PT

        if petition_type == PT.CESSATION:
            return self._cessation_threshold
        if petition_type == PT.GRIEVANCE:
            return self._grievance_threshold
        # GENERAL and COLLABORATION have no threshold
        return None

    def check_threshold(
        self,
        petition_type: PetitionType,
        co_signer_count: int,
    ) -> EscalationThresholdResult:
        """Check if co-signer count has reached escalation threshold.

        This is a pure calculation with no side effects.
        The check occurs AFTER co-sign persistence but BEFORE event emission.

        Args:
            petition_type: The type of petition (CESSATION, GRIEVANCE, etc.).
            co_signer_count: The current co-signer count (after this co-sign).

        Returns:
            EscalationThresholdResult with threshold detection info.

        Example:
            >>> result = service.check_threshold(PetitionType.CESSATION, 100)
            >>> result.threshold_reached
            True
            >>> result.threshold_value
            100
        """
        threshold = self.get_threshold_for_type(petition_type)

        # Determine if threshold is reached
        threshold_reached = threshold is not None and co_signer_count >= threshold

        result = EscalationThresholdResult(
            threshold_reached=threshold_reached,
            threshold_value=threshold,
            petition_type=petition_type.value,
            current_count=co_signer_count,
        )

        if threshold_reached:
            logger.info(
                "Escalation threshold reached",
                petition_type=petition_type.value,
                threshold=threshold,
                current_count=co_signer_count,
            )
        else:
            logger.debug(
                "Threshold check complete",
                petition_type=petition_type.value,
                threshold=threshold,
                current_count=co_signer_count,
                threshold_reached=False,
            )

        return result


# Verify protocol compliance at module load time
def _verify_protocol() -> None:
    """Verify EscalationThresholdService implements the protocol."""
    from src.domain.models.petition_submission import PetitionType

    service: EscalationThresholdCheckerProtocol = EscalationThresholdService()
    # Test that methods exist and have correct signatures
    _ = service.check_threshold(PetitionType.CESSATION, 100)
    _ = service.get_threshold_for_type(PetitionType.CESSATION)
    _ = service.cessation_threshold
    _ = service.grievance_threshold


# Run verification on import
_verify_protocol()
