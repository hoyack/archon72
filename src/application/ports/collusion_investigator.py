"""Collusion investigator port (Story 6.8, FR124).

Defines the protocol for managing collusion investigations, supporting
the human review layer of ADR-7 Aggregate Anomaly Detection.

Constitutional Constraints:
- FR124: Witness selection randomness SHALL combine hash chain state +
         external entropy source meeting independence criteria (Randomness Gaming defense)
- CT-9: Attackers are patient - aggregate erosion must be detected
- CT-11: Silent failure destroys legitimacy
- CT-12: Witnessing creates accountability

ADR-7 Context:
This port supports the Human layer of ADR-7 Aggregate Anomaly Detection.
Investigations are triggered by anomalies from the Statistics layer (Story 6.6)
and require human resolution.
"""

from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Protocol, runtime_checkable

from src.domain.events.collusion import InvestigationResolution


class InvestigationStatus(Enum):
    """Status of a collusion investigation.

    Investigations progress through these states:
    - ACTIVE: Investigation is ongoing
    - CLEARED: Investigation found no evidence, pair reinstated
    - CONFIRMED: Investigation confirmed collusion, pair permanently banned
    """

    ACTIVE = "active"
    """Investigation is ongoing, pair is suspended."""

    CLEARED = "cleared"
    """Investigation found no evidence, pair reinstated."""

    CONFIRMED = "confirmed"
    """Investigation confirmed collusion, pair permanently banned."""


@dataclass(frozen=True)
class Investigation:
    """Record of a collusion investigation.

    Constitutional Constraint (FR124):
    Represents a formal investigation into potential witness collusion.
    Pairs under investigation are suspended from selection.

    Attributes:
        investigation_id: Unique investigation identifier.
        pair_key: Canonical key of the investigated pair.
        status: Current status (ACTIVE, CLEARED, CONFIRMED).
        triggered_at: When the investigation was triggered.
        triggering_anomalies: Anomaly IDs that triggered this investigation.
        breach_event_ids: Related breach events involving this pair.
        correlation_score: Correlation strength (0.0 to 1.0).
        resolved_at: When the investigation was resolved (if applicable).
        resolution: Resolution outcome (if resolved).
        resolved_by: Who resolved the investigation (if resolved).
        resolution_reason: Explanation for the resolution (if resolved).
    """

    investigation_id: str
    pair_key: str
    status: InvestigationStatus
    triggered_at: datetime
    triggering_anomalies: tuple[str, ...]
    breach_event_ids: tuple[str, ...]
    correlation_score: float
    resolved_at: datetime | None = None
    resolution: InvestigationResolution | None = None
    resolved_by: str | None = None
    resolution_reason: str | None = None

    def __post_init__(self) -> None:
        """Validate correlation score is within bounds."""
        if not 0.0 <= self.correlation_score <= 1.0:
            raise ValueError(
                f"correlation_score must be between 0.0 and 1.0, got {self.correlation_score}"
            )

    @property
    def is_active(self) -> bool:
        """Check if investigation is still active."""
        return self.status == InvestigationStatus.ACTIVE

    @property
    def is_resolved(self) -> bool:
        """Check if investigation has been resolved."""
        return self.status in (
            InvestigationStatus.CLEARED,
            InvestigationStatus.CONFIRMED,
        )


@runtime_checkable
class CollusionInvestigatorProtocol(Protocol):
    """Protocol for collusion investigation management (FR124).

    Constitutional Constraint (FR124):
    Witness selection randomness SHALL combine hash chain state +
    external entropy source meeting independence criteria.

    When anomalies indicate potential collusion, this protocol manages
    the investigation lifecycle:
    1. Trigger investigation → pair is suspended
    2. Investigation is active → pair cannot be selected
    3. Resolution (cleared or confirmed) → pair reinstated or banned

    Implementations must:
    1. Create and track investigations
    2. Manage pair suspension during active investigations
    3. Handle investigation resolution
    4. Calculate correlation scores for breach patterns
    5. Provide investigation history for audit

    Example:
        investigator: CollusionInvestigatorProtocol = ...

        # Trigger investigation
        investigation_id = await investigator.trigger_investigation(
            pair_key="witness_a:witness_b",
            anomaly_ids=("anomaly-1", "anomaly-2"),
            breach_ids=("breach-1", "breach-2"),
        )

        # Check if pair is under investigation
        if await investigator.is_pair_under_investigation("witness_a:witness_b"):
            # Skip this pair in selection
            ...

        # Resolve investigation
        await investigator.resolve_investigation(
            investigation_id=investigation_id,
            resolution=InvestigationResolution.CLEARED,
            reason="No evidence of collusion found",
            resolved_by="human_reviewer_1",
        )
    """

    @abstractmethod
    async def trigger_investigation(
        self,
        pair_key: str,
        anomaly_ids: tuple[str, ...],
        breach_ids: tuple[str, ...],
    ) -> str:
        """Trigger a new collusion investigation.

        Creates a new investigation and suspends the pair from
        witness selection until the investigation is resolved.

        Args:
            pair_key: Canonical key of the pair to investigate.
            anomaly_ids: IDs of anomalies that triggered this investigation.
            breach_ids: IDs of breach events involving this pair.

        Returns:
            The investigation_id of the newly created investigation.

        Raises:
            CollusionDefenseError: If investigation cannot be created.
        """
        ...

    @abstractmethod
    async def get_investigation(
        self,
        investigation_id: str,
    ) -> Investigation | None:
        """Retrieve an investigation by ID.

        Args:
            investigation_id: ID of the investigation to retrieve.

        Returns:
            The Investigation if found, None otherwise.
        """
        ...

    @abstractmethod
    async def list_active_investigations(self) -> list[Investigation]:
        """List all currently active investigations.

        Returns:
            List of investigations with ACTIVE status,
            sorted by triggered_at (oldest first).
        """
        ...

    @abstractmethod
    async def resolve_investigation(
        self,
        investigation_id: str,
        resolution: InvestigationResolution,
        reason: str,
        resolved_by: str,
    ) -> None:
        """Resolve an investigation.

        Concludes the investigation with the given resolution:
        - CLEARED: Pair is reinstated for selection
        - CONFIRMED_COLLUSION: Pair is permanently banned

        Args:
            investigation_id: ID of the investigation to resolve.
            resolution: CLEARED or CONFIRMED_COLLUSION.
            reason: Explanation for the resolution.
            resolved_by: Attribution of who resolved the investigation.

        Raises:
            InvestigationNotFoundError: If investigation does not exist.
            InvestigationAlreadyResolvedError: If already resolved.
        """
        ...

    @abstractmethod
    async def is_pair_under_investigation(self, pair_key: str) -> bool:
        """Check if a pair has an active investigation.

        Args:
            pair_key: Canonical key of the pair to check.

        Returns:
            True if the pair has an ACTIVE investigation, False otherwise.
        """
        ...

    @abstractmethod
    async def calculate_correlation(
        self,
        pair_key: str,
        breach_ids: tuple[str, ...],
    ) -> float:
        """Calculate correlation score for a pair across breaches.

        Calculates how strongly a witness pair is correlated with
        breach events. High correlation (>0.8) triggers investigation.

        Correlation = (breaches involving pair) / (total breaches in window)

        Args:
            pair_key: Canonical key of the pair to analyze.
            breach_ids: IDs of all breach events in the analysis window.

        Returns:
            Correlation score between 0.0 and 1.0.
        """
        ...

    @abstractmethod
    async def get_permanently_banned_pairs(self) -> set[str]:
        """Get all permanently banned pairs.

        Returns pairs that have been confirmed for collusion
        and are permanently excluded from selection.

        Returns:
            Set of canonical pair keys that are permanently banned.
        """
        ...

    @abstractmethod
    async def get_suspended_pairs(self) -> set[str]:
        """Get all currently suspended pairs.

        Returns pairs that are suspended pending investigation.
        These pairs should be skipped in witness selection.

        Returns:
            Set of canonical pair keys that are currently suspended.
        """
        ...

    @abstractmethod
    async def get_investigations_for_pair(
        self,
        pair_key: str,
    ) -> list[Investigation]:
        """Get all investigations for a specific pair.

        Includes both active and resolved investigations for audit.

        Args:
            pair_key: Canonical key of the pair.

        Returns:
            List of all investigations involving this pair,
            sorted by triggered_at (newest first).
        """
        ...
