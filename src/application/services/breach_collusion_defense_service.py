"""Breach collusion defense service (Story 6.8, FR124).

Implements witness collusion investigation workflow, bridging
the Statistics layer (Story 6.6) to the Human layer (ADR-7).

Constitutional Constraints:
- FR124: Witness selection randomness SHALL combine hash chain state +
         external entropy source meeting independence criteria (Randomness Gaming defense)
- CT-9: Attackers are patient - aggregate erosion must be detected
- CT-11: Silent failure destroys legitimacy -> HALT CHECK FIRST
- CT-12: Witnessing creates accountability -> All events witnessed

Developer Golden Rules:
1. HALT CHECK FIRST - Check halt state at every operation boundary
2. WITNESS EVERYTHING - All investigation events must be witnessed
3. FAIL LOUD - Failed event write = investigation failure
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from src.application.ports.breach_repository import BreachRepositoryProtocol
from src.application.ports.collusion_investigator import (
    CollusionInvestigatorProtocol,
    Investigation,
    InvestigationStatus,
)
from src.application.ports.halt_checker import HaltChecker
from src.application.ports.witness_anomaly_detector import (
    WitnessAnomalyDetectorProtocol,
)
from src.domain.errors.collusion import (
    CollusionInvestigationRequiredError,
    InvestigationAlreadyResolvedError,
    InvestigationNotFoundError,
)
from src.domain.errors.writer import SystemHaltedError
from src.domain.events.collusion import (
    CollusionInvestigationTriggeredEventPayload,
    InvestigationResolution,
    InvestigationResolvedEventPayload,
    WitnessPairSuspendedEventPayload,
)


# System agent ID for collusion defense operations
COLLUSION_DEFENSE_SYSTEM_AGENT_ID: str = "system:collusion_defense"

# Default correlation threshold for investigation trigger
DEFAULT_CORRELATION_THRESHOLD: float = 0.8


@dataclass(frozen=True)
class CollusionCheckResult:
    """Result of a collusion check for a witness pair.

    Attributes:
        requires_investigation: True if correlation exceeds threshold.
        investigation_id: ID of triggered investigation (if any).
        correlation_score: Calculated correlation score.
        breach_count: Number of breaches involving the pair.
    """

    requires_investigation: bool
    correlation_score: float
    breach_count: int
    investigation_id: Optional[str] = None


class BreachCollusionDefenseService:
    """Service for witness collusion defense (FR124, ADR-7).

    Implements the Human layer of ADR-7 Aggregate Anomaly Detection,
    managing collusion investigations triggered by statistical anomalies.

    Constitutional Constraint (FR124):
    Witness selection randomness SHALL combine hash chain state +
    external entropy source meeting independence criteria.

    When anomalies indicate potential collusion:
    1. Investigation is triggered, pair is suspended
    2. Pair cannot be selected for witnessing
    3. Human review resolves investigation
    4. Pair is reinstated (cleared) or permanently banned (confirmed)

    Example:
        service = BreachCollusionDefenseService(
            halt_checker=halt_checker,
            investigator=investigator,
            anomaly_detector=anomaly_detector,
            breach_repository=breach_repository,
        )

        # Check for collusion trigger
        result = await service.check_for_collusion_trigger("pair_key")
        if result.requires_investigation:
            print(f"Investigation {result.investigation_id} triggered")

        # Resolve investigation
        await service.resolve_investigation(
            investigation_id="inv-123",
            resolution=InvestigationResolution.CLEARED,
            reason="No evidence found",
            resolved_by="reviewer_1",
        )
    """

    def __init__(
        self,
        halt_checker: HaltChecker,
        investigator: CollusionInvestigatorProtocol,
        anomaly_detector: WitnessAnomalyDetectorProtocol,
        breach_repository: BreachRepositoryProtocol,
        correlation_threshold: float = DEFAULT_CORRELATION_THRESHOLD,
        event_writer: Optional[object] = None,  # Optional EventWriterService
    ) -> None:
        """Initialize the breach collusion defense service.

        Args:
            halt_checker: For HALT CHECK FIRST pattern.
            investigator: For managing investigations.
            anomaly_detector: For querying anomalies and pair exclusion.
            breach_repository: For querying breach history.
            correlation_threshold: Threshold for triggering investigation.
            event_writer: Optional event writer for creating events.
        """
        self._halt_checker = halt_checker
        self._investigator = investigator
        self._anomaly_detector = anomaly_detector
        self._breach_repository = breach_repository
        self._correlation_threshold = correlation_threshold
        self._event_writer = event_writer

    async def check_for_collusion_trigger(
        self,
        pair_key: str,
    ) -> CollusionCheckResult:
        """Check if a witness pair should trigger collusion investigation.

        Constitutional Constraint (FR124):
        Randomness Gaming defense - high correlation indicates
        potential collusion that must be investigated.

        HALT CHECK FIRST (CT-11).

        Args:
            pair_key: Canonical key of the pair to check.

        Returns:
            CollusionCheckResult with investigation trigger status.

        Raises:
            SystemHaltedError: If system is halted.
        """
        # HALT CHECK FIRST (CT-11)
        if await self._halt_checker.is_halted():
            raise SystemHaltedError("System halted")

        # Check if already under investigation
        if await self._investigator.is_pair_under_investigation(pair_key):
            active_investigations = await self._investigator.get_investigations_for_pair(
                pair_key
            )
            active = next(
                (i for i in active_investigations if i.is_active),
                None,
            )
            if active:
                return CollusionCheckResult(
                    requires_investigation=False,  # Already being investigated
                    correlation_score=active.correlation_score,
                    breach_count=len(active.breach_event_ids),
                    investigation_id=active.investigation_id,
                )

        # Get breaches involving this pair
        breaches = await self._breach_repository.get_breaches_by_witness_pair(pair_key)
        breach_ids = tuple(b.breach_id for b in breaches)

        if not breach_ids:
            return CollusionCheckResult(
                requires_investigation=False,
                correlation_score=0.0,
                breach_count=0,
            )

        # Calculate correlation
        correlation = await self._investigator.calculate_correlation(
            pair_key=pair_key,
            breach_ids=breach_ids,
        )

        # Check threshold
        if correlation > self._correlation_threshold:
            # Get anomalies for this pair
            anomalies = await self._anomaly_detector.analyze_co_occurrence(
                window_hours=168,  # 1 week
            )
            anomaly_ids = tuple(
                f"anomaly-{i}"
                for i, a in enumerate(anomalies)
                if pair_key in ":".join(a.affected_witnesses)
            )

            # Trigger investigation
            investigation_id = await self.trigger_investigation(
                pair_key=pair_key,
                anomaly_ids=anomaly_ids if anomaly_ids else ("auto-triggered",),
                breach_ids=breach_ids,
            )

            return CollusionCheckResult(
                requires_investigation=True,
                correlation_score=correlation,
                breach_count=len(breach_ids),
                investigation_id=investigation_id,
            )

        return CollusionCheckResult(
            requires_investigation=False,
            correlation_score=correlation,
            breach_count=len(breach_ids),
        )

    async def trigger_investigation(
        self,
        pair_key: str,
        anomaly_ids: tuple[str, ...],
        breach_ids: tuple[str, ...],
    ) -> str:
        """Trigger a new collusion investigation.

        Creates investigation, suspends pair, and creates events.

        HALT CHECK FIRST (CT-11).

        Args:
            pair_key: Canonical key of the pair to investigate.
            anomaly_ids: IDs of anomalies that triggered this.
            breach_ids: IDs of breach events involving this pair.

        Returns:
            The investigation_id of the created investigation.

        Raises:
            SystemHaltedError: If system is halted.
        """
        # HALT CHECK FIRST (CT-11)
        if await self._halt_checker.is_halted():
            raise SystemHaltedError("System halted")

        # Calculate correlation for the investigation
        correlation = await self._investigator.calculate_correlation(
            pair_key=pair_key,
            breach_ids=breach_ids,
        )

        # Create investigation via port
        investigation_id = await self._investigator.trigger_investigation(
            pair_key=pair_key,
            anomaly_ids=anomaly_ids,
            breach_ids=breach_ids,
        )

        now = datetime.now(timezone.utc)

        # Create investigation triggered event
        triggered_event = CollusionInvestigationTriggeredEventPayload(
            investigation_id=investigation_id,
            witness_pair_key=pair_key,
            triggering_anomalies=anomaly_ids,
            breach_event_ids=breach_ids,
            correlation_score=correlation,
            triggered_at=now,
            triggered_by=COLLUSION_DEFENSE_SYSTEM_AGENT_ID,
        )

        # Create suspension event
        suspended_event = WitnessPairSuspendedEventPayload(
            pair_key=pair_key,
            investigation_id=investigation_id,
            suspension_reason=f"FR124: Collusion investigation - correlation {correlation:.2f}",
            suspended_at=now,
            suspended_by=COLLUSION_DEFENSE_SYSTEM_AGENT_ID,
        )

        # Write events if event writer available
        if self._event_writer is not None:
            # Type checking bypass - service accepts any event payload
            await self._event_writer.write_event(triggered_event)  # type: ignore
            await self._event_writer.write_event(suspended_event)  # type: ignore

        # Exclude pair from selection
        await self._anomaly_detector.exclude_pair(
            pair_key=pair_key,
            duration_hours=0,  # No expiry - manual clearance required
            reason=f"Collusion investigation {investigation_id}",
            confidence=correlation,
        )

        return investigation_id

    async def resolve_investigation(
        self,
        investigation_id: str,
        resolution: InvestigationResolution,
        reason: str,
        resolved_by: str,
    ) -> None:
        """Resolve a collusion investigation.

        CLEARED: Reinstates pair for selection.
        CONFIRMED_COLLUSION: Permanently bans pair.

        HALT CHECK FIRST (CT-11).

        Args:
            investigation_id: ID of the investigation to resolve.
            resolution: CLEARED or CONFIRMED_COLLUSION.
            reason: Explanation for the resolution.
            resolved_by: Attribution of who resolved.

        Raises:
            SystemHaltedError: If system is halted.
            InvestigationNotFoundError: If investigation doesn't exist.
            InvestigationAlreadyResolvedError: If already resolved.
        """
        # HALT CHECK FIRST (CT-11)
        if await self._halt_checker.is_halted():
            raise SystemHaltedError("System halted")

        # Validate investigation exists
        investigation = await self._investigator.get_investigation(investigation_id)
        if investigation is None:
            raise InvestigationNotFoundError(investigation_id=investigation_id)

        if investigation.status != InvestigationStatus.ACTIVE:
            raise InvestigationAlreadyResolvedError(
                investigation_id=investigation_id,
                resolved_at=investigation.resolved_at,
            )

        # Resolve via port
        await self._investigator.resolve_investigation(
            investigation_id=investigation_id,
            resolution=resolution,
            reason=reason,
            resolved_by=resolved_by,
        )

        now = datetime.now(timezone.utc)

        # Handle based on resolution
        if resolution == InvestigationResolution.CLEARED:
            # Reinstate pair
            await self._anomaly_detector.clear_pair_exclusion(investigation.pair_key)

        # Create resolution event
        event = InvestigationResolvedEventPayload(
            investigation_id=investigation_id,
            pair_key=investigation.pair_key,
            resolution=resolution,
            resolution_reason=reason,
            resolved_at=now,
            resolved_by=resolved_by,
            evidence_summary=f"Correlation score: {investigation.correlation_score:.2f}",
        )

        # Write event if event writer available
        if self._event_writer is not None:
            await self._event_writer.write_event(event)  # type: ignore

    async def get_investigation(
        self,
        investigation_id: str,
    ) -> Optional[Investigation]:
        """Get an investigation by ID.

        HALT CHECK FIRST (CT-11).

        Args:
            investigation_id: ID of the investigation.

        Returns:
            The Investigation if found, None otherwise.

        Raises:
            SystemHaltedError: If system is halted.
        """
        # HALT CHECK FIRST (CT-11)
        if await self._halt_checker.is_halted():
            raise SystemHaltedError("System halted")

        return await self._investigator.get_investigation(investigation_id)

    async def list_active_investigations(self) -> list[Investigation]:
        """List all active investigations.

        HALT CHECK FIRST (CT-11).

        Returns:
            List of active investigations.

        Raises:
            SystemHaltedError: If system is halted.
        """
        # HALT CHECK FIRST (CT-11)
        if await self._halt_checker.is_halted():
            raise SystemHaltedError("System halted")

        return await self._investigator.list_active_investigations()

    async def is_pair_under_investigation(self, pair_key: str) -> bool:
        """Check if a pair has an active investigation.

        HALT CHECK FIRST (CT-11).

        Args:
            pair_key: Canonical key of the pair.

        Returns:
            True if the pair has an active investigation.

        Raises:
            SystemHaltedError: If system is halted.
        """
        # HALT CHECK FIRST (CT-11)
        if await self._halt_checker.is_halted():
            raise SystemHaltedError("System halted")

        return await self._investigator.is_pair_under_investigation(pair_key)

    async def get_suspended_pairs(self) -> set[str]:
        """Get all currently suspended pairs.

        HALT CHECK FIRST (CT-11).

        Returns:
            Set of canonical pair keys that are suspended.

        Raises:
            SystemHaltedError: If system is halted.
        """
        # HALT CHECK FIRST (CT-11)
        if await self._halt_checker.is_halted():
            raise SystemHaltedError("System halted")

        return await self._investigator.get_suspended_pairs()

    async def get_permanently_banned_pairs(self) -> set[str]:
        """Get all permanently banned pairs.

        HALT CHECK FIRST (CT-11).

        Returns:
            Set of canonical pair keys that are permanently banned.

        Raises:
            SystemHaltedError: If system is halted.
        """
        # HALT CHECK FIRST (CT-11)
        if await self._halt_checker.is_halted():
            raise SystemHaltedError("System halted")

        return await self._investigator.get_permanently_banned_pairs()

    def _calculate_pair_breach_correlation(
        self,
        pair_breaches: int,
        total_breaches: int,
    ) -> float:
        """Calculate correlation score for a pair.

        Correlation = (breaches with pair) / (total breaches)

        Args:
            pair_breaches: Number of breaches involving the pair.
            total_breaches: Total breaches in the analysis window.

        Returns:
            Correlation score between 0.0 and 1.0.
        """
        if total_breaches == 0:
            return 0.0
        return min(1.0, pair_breaches / total_breaches)
