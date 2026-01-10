"""Collusion investigator stub (Story 6.8, FR124).

In-memory stub implementation for testing and development.

Constitutional Constraints:
- FR124: Witness selection randomness SHALL combine hash chain state +
         external entropy source meeting independence criteria (Randomness Gaming defense)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from src.application.ports.collusion_investigator import (
    CollusionInvestigatorProtocol,
    Investigation,
    InvestigationStatus,
)
from src.domain.errors.collusion import (
    InvestigationAlreadyResolvedError,
    InvestigationNotFoundError,
)
from src.domain.events.collusion import InvestigationResolution


class CollusionInvestigatorStub(CollusionInvestigatorProtocol):
    """In-memory stub for CollusionInvestigatorProtocol.

    Provides a simple implementation for testing that stores
    investigations in memory.

    Example:
        stub = CollusionInvestigatorStub()
        investigation_id = await stub.trigger_investigation(
            pair_key="witness_a:witness_b",
            anomaly_ids=("anomaly-1",),
            breach_ids=("breach-1",),
        )
    """

    def __init__(self) -> None:
        """Initialize the stub with empty storage."""
        self._investigations: dict[str, Investigation] = {}
        self._pair_to_active_investigation: dict[str, str] = {}
        self._permanently_banned: set[str] = set()

    async def trigger_investigation(
        self,
        pair_key: str,
        anomaly_ids: tuple[str, ...],
        breach_ids: tuple[str, ...],
    ) -> str:
        """Trigger a new collusion investigation.

        Args:
            pair_key: Canonical key of the pair to investigate.
            anomaly_ids: IDs of anomalies that triggered this.
            breach_ids: IDs of breach events involving this pair.

        Returns:
            The investigation_id of the newly created investigation.
        """
        investigation_id = str(uuid4())
        now = datetime.now(timezone.utc)

        # Calculate correlation (simple: len(breach_ids) / 10, capped at 1.0)
        correlation = min(1.0, len(breach_ids) / 10.0)

        investigation = Investigation(
            investigation_id=investigation_id,
            pair_key=pair_key,
            status=InvestigationStatus.ACTIVE,
            triggered_at=now,
            triggering_anomalies=anomaly_ids,
            breach_event_ids=breach_ids,
            correlation_score=correlation,
        )

        self._investigations[investigation_id] = investigation
        self._pair_to_active_investigation[pair_key] = investigation_id

        return investigation_id

    async def get_investigation(
        self,
        investigation_id: str,
    ) -> Optional[Investigation]:
        """Retrieve an investigation by ID.

        Args:
            investigation_id: ID of the investigation to retrieve.

        Returns:
            The Investigation if found, None otherwise.
        """
        return self._investigations.get(investigation_id)

    async def list_active_investigations(self) -> list[Investigation]:
        """List all currently active investigations.

        Returns:
            List of investigations with ACTIVE status,
            sorted by triggered_at (oldest first).
        """
        active = [
            inv for inv in self._investigations.values()
            if inv.status == InvestigationStatus.ACTIVE
        ]
        return sorted(active, key=lambda i: i.triggered_at)

    async def resolve_investigation(
        self,
        investigation_id: str,
        resolution: InvestigationResolution,
        reason: str,
        resolved_by: str,
    ) -> None:
        """Resolve an investigation.

        Args:
            investigation_id: ID of the investigation to resolve.
            resolution: CLEARED or CONFIRMED_COLLUSION.
            reason: Explanation for the resolution.
            resolved_by: Attribution of who resolved.

        Raises:
            InvestigationNotFoundError: If investigation does not exist.
            InvestigationAlreadyResolvedError: If already resolved.
        """
        investigation = self._investigations.get(investigation_id)
        if investigation is None:
            raise InvestigationNotFoundError(investigation_id=investigation_id)

        if investigation.status != InvestigationStatus.ACTIVE:
            raise InvestigationAlreadyResolvedError(
                investigation_id=investigation_id,
                resolved_at=investigation.resolved_at,
            )

        now = datetime.now(timezone.utc)

        # Determine new status
        new_status = (
            InvestigationStatus.CONFIRMED
            if resolution == InvestigationResolution.CONFIRMED_COLLUSION
            else InvestigationStatus.CLEARED
        )

        # Create updated investigation
        updated = Investigation(
            investigation_id=investigation_id,
            pair_key=investigation.pair_key,
            status=new_status,
            triggered_at=investigation.triggered_at,
            triggering_anomalies=investigation.triggering_anomalies,
            breach_event_ids=investigation.breach_event_ids,
            correlation_score=investigation.correlation_score,
            resolved_at=now,
            resolution=resolution,
            resolved_by=resolved_by,
            resolution_reason=reason,
        )

        self._investigations[investigation_id] = updated

        # Update pair mapping
        if investigation.pair_key in self._pair_to_active_investigation:
            if self._pair_to_active_investigation[investigation.pair_key] == investigation_id:
                del self._pair_to_active_investigation[investigation.pair_key]

        # If confirmed, add to permanently banned
        if resolution == InvestigationResolution.CONFIRMED_COLLUSION:
            self._permanently_banned.add(investigation.pair_key)

    async def is_pair_under_investigation(self, pair_key: str) -> bool:
        """Check if a pair has an active investigation.

        Args:
            pair_key: Canonical key of the pair to check.

        Returns:
            True if the pair has an ACTIVE investigation.
        """
        return pair_key in self._pair_to_active_investigation

    async def calculate_correlation(
        self,
        pair_key: str,
        breach_ids: tuple[str, ...],
    ) -> float:
        """Calculate correlation score for a pair across breaches.

        Simple implementation: correlation = len(breach_ids) / 10, capped at 1.0

        Args:
            pair_key: Canonical key of the pair.
            breach_ids: IDs of all breach events in the window.

        Returns:
            Correlation score between 0.0 and 1.0.
        """
        if not breach_ids:
            return 0.0
        return min(1.0, len(breach_ids) / 10.0)

    async def get_permanently_banned_pairs(self) -> set[str]:
        """Get all permanently banned pairs.

        Returns:
            Set of canonical pair keys that are permanently banned.
        """
        return set(self._permanently_banned)

    async def get_suspended_pairs(self) -> set[str]:
        """Get all currently suspended pairs.

        Returns:
            Set of canonical pair keys that are currently suspended.
        """
        return set(self._pair_to_active_investigation.keys())

    async def get_investigations_for_pair(
        self,
        pair_key: str,
    ) -> list[Investigation]:
        """Get all investigations for a specific pair.

        Args:
            pair_key: Canonical key of the pair.

        Returns:
            List of all investigations involving this pair,
            sorted by triggered_at (newest first).
        """
        investigations = [
            inv for inv in self._investigations.values()
            if inv.pair_key == pair_key
        ]
        return sorted(investigations, key=lambda i: i.triggered_at, reverse=True)

    def clear(self) -> None:
        """Clear all data (for testing)."""
        self._investigations.clear()
        self._pair_to_active_investigation.clear()
        self._permanently_banned.clear()
