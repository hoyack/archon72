"""Restoration acknowledgment domain models for explicit legitimacy restoration.

This module defines the domain models used for human-acknowledged
legitimacy band restoration operations.

Key Principles:
- Restoration requires explicit human acknowledgment (FR30)
- No automatic upward transitions allowed (FR32)
- Reason and evidence are mandatory
- All acknowledgments are immutable records

Constitutional Compliance:
- FR30: Human Operator can acknowledge and execute upward legitimacy transition
- FR31: System can record all legitimacy transitions in append-only ledger
- FR32: System can prevent upward transitions without explicit acknowledgment
- NFR-CONST-04: All transitions logged with timestamp, actor, reason
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from src.domain.governance.legitimacy.legitimacy_band import LegitimacyBand
from src.domain.governance.legitimacy.legitimacy_state import LegitimacyState


@dataclass(frozen=True)
class RestorationAcknowledgment:
    """Acknowledgment record for legitimacy restoration.

    This immutable record captures the human operator's explicit
    acknowledgment for an upward legitimacy transition.

    Attributes:
        acknowledgment_id: Unique identifier for this acknowledgment.
        operator_id: UUID of the human operator acknowledging.
        from_band: The band before restoration.
        to_band: The band after restoration.
        reason: Human-readable explanation for restoration.
        evidence: Supporting evidence for the restoration decision.
        acknowledged_at: When the acknowledgment was recorded.
    """

    acknowledgment_id: UUID
    operator_id: UUID
    from_band: LegitimacyBand
    to_band: LegitimacyBand
    reason: str
    evidence: str
    acknowledged_at: datetime

    def __post_init__(self) -> None:
        """Validate acknowledgment record."""
        if not self.reason or not self.reason.strip():
            raise ValueError("Reason is required for restoration acknowledgment")
        if not self.evidence or not self.evidence.strip():
            raise ValueError("Evidence is required for restoration acknowledgment")
        # Restoration must be upward (lower severity)
        if self.to_band.severity >= self.from_band.severity:
            raise ValueError(
                f"Restoration must be upward: {self.from_band.value} → {self.to_band.value} "
                f"(severity {self.from_band.severity} → {self.to_band.severity})"
            )

    @property
    def severity_improvement(self) -> int:
        """Get the improvement in severity (positive = better).

        Returns:
            The number of severity levels improved (positive integer).
        """
        return self.from_band.severity - self.to_band.severity

    @property
    def is_single_step(self) -> bool:
        """Check if this is a single step restoration.

        Returns:
            True if the restoration is exactly one band up.
        """
        return self.severity_improvement == 1


@dataclass(frozen=True)
class RestorationRequest:
    """Request to restore legitimacy band.

    Attributes:
        operator_id: UUID of the operator making the request.
        target_band: The band to restore to.
        reason: Explanation for why restoration is warranted.
        evidence: Supporting evidence (audit ID, resolved issues, etc.).
    """

    operator_id: UUID
    target_band: LegitimacyBand
    reason: str
    evidence: str

    def __post_init__(self) -> None:
        """Validate request parameters."""
        if not self.reason or not self.reason.strip():
            raise ValueError("Reason is required for restoration request")
        if not self.evidence or not self.evidence.strip():
            raise ValueError("Evidence is required for restoration request")


@dataclass(frozen=True)
class RestorationResult:
    """Result of a restoration attempt.

    Attributes:
        success: True if restoration was successful.
        new_state: The new legitimacy state (if successful).
        acknowledgment: The recorded acknowledgment (if successful).
        error: Error message (if unsuccessful).
    """

    success: bool
    new_state: LegitimacyState | None
    acknowledgment: RestorationAcknowledgment | None
    error: str | None

    @classmethod
    def succeeded(
        cls,
        new_state: LegitimacyState,
        acknowledgment: RestorationAcknowledgment,
    ) -> "RestorationResult":
        """Create a successful restoration result.

        Args:
            new_state: The new legitimacy state after restoration.
            acknowledgment: The recorded acknowledgment.

        Returns:
            RestorationResult indicating success.
        """
        return cls(
            success=True,
            new_state=new_state,
            acknowledgment=acknowledgment,
            error=None,
        )

    @classmethod
    def failed(cls, error: str) -> "RestorationResult":
        """Create a failed restoration result.

        Args:
            error: Description of why restoration failed.

        Returns:
            RestorationResult indicating failure.
        """
        return cls(
            success=False,
            new_state=None,
            acknowledgment=None,
            error=error,
        )
