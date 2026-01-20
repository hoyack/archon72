"""Escalation threshold checking port (Story 5.5, FR-5.1, FR-5.2, FR-6.5).

This module defines the protocol for checking co-signer escalation thresholds
in the Three Fates petition system.

Constitutional Constraints:
- FR-5.1: System SHALL ESCALATE petition when co-signer threshold reached [P0]
- FR-5.2: Escalation thresholds: CESSATION=100, GRIEVANCE=50 [P0]
- FR-6.5: System SHALL check escalation threshold on each co-sign [P0]
- FR-10.2: CESSATION petitions SHALL auto-escalate at 100 co-signers [P0]
- FR-10.3: GRIEVANCE petitions SHALL auto-escalate at 50 co-signers [P1]
- NFR-1.4: Threshold detection latency < 1 second
- CON-5: CESSATION auto-escalation threshold is immutable (100)

Developer Golden Rules:
1. DETECTION ONLY - This port detects thresholds; escalation execution is separate (Story 5.6)
2. PURE CALCULATION - No database writes, just compare count vs threshold
3. TYPE-BASED - Different petition types have different thresholds (or none)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from src.domain.models.petition_submission import PetitionType


@dataclass(frozen=True)
class EscalationThresholdResult:
    """Result of checking escalation threshold (Story 5.5, FR-6.5).

    Constitutional Constraints:
    - FR-5.1: threshold_reached indicates escalation should trigger
    - FR-5.2: threshold_value reflects type-specific threshold
    - CON-5: CESSATION threshold is 100 by default

    Attributes:
        threshold_reached: True if current_count >= threshold_value.
        threshold_value: The threshold for this petition type, or None if no threshold.
        petition_type: The type of petition being checked.
        current_count: The current co-signer count (after this co-sign).
    """

    threshold_reached: bool
    threshold_value: int | None
    petition_type: str
    current_count: int

    @property
    def has_threshold(self) -> bool:
        """Check if this petition type has a threshold.

        Returns:
            True if threshold_value is not None.
        """
        return self.threshold_value is not None


@runtime_checkable
class EscalationThresholdCheckerProtocol(Protocol):
    """Protocol for checking escalation thresholds (Story 5.5, FR-6.5).

    Constitutional Constraints:
    - FR-5.1: SHALL detect when threshold is reached [P0]
    - FR-5.2: SHALL use correct thresholds per type [P0]
    - FR-6.5: SHALL check on each co-sign [P0]
    - NFR-1.4: Detection latency < 1 second

    Implementation Requirements:
    - CESSATION threshold: 100 (FR-10.2, CON-5)
    - GRIEVANCE threshold: 50 (FR-10.3)
    - GENERAL/COLLABORATION: No threshold (returns None)
    """

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
            >>> checker = EscalationThresholdService()
            >>> result = checker.check_threshold(PetitionType.CESSATION, 100)
            >>> result.threshold_reached
            True
            >>> result.threshold_value
            100
        """
        ...

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
            >>> checker.get_threshold_for_type(PetitionType.CESSATION)
            100
            >>> checker.get_threshold_for_type(PetitionType.GENERAL)
            None
        """
        ...

    @property
    def cessation_threshold(self) -> int:
        """Get the CESSATION escalation threshold (CON-5: default 100)."""
        ...

    @property
    def grievance_threshold(self) -> int:
        """Get the GRIEVANCE escalation threshold (default 50)."""
        ...
