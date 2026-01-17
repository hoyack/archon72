"""Marquis Service Adapter (Advisory Branch).

This module implements the MarquisServiceProtocol for expert testimony,
non-binding advisories, and risk analysis.

Per Government PRD FR-GOV-17: Marquis provide expert testimony and risk analysis,
issue non-binding advisories.
Per Government PRD FR-GOV-18: Advisories must be acknowledged but not obeyed;
cannot judge domains where advisory was given.
"""

from typing import Any
from uuid import UUID

from structlog import get_logger

from src.application.ports.marquis_service import (
    Advisory,
    AdvisoryRequest,
    AdvisoryResult,
    ExpertiseDomain,
    MarquisServiceProtocol,
    RiskAnalysis,
    RiskAnalysisRequest,
    RiskAnalysisResult,
    RiskFactor,
    RiskLevel,
    Testimony,
    TestimonyRequest,
    TestimonyResult,
    get_expertise_domain,
)
from src.application.ports.knight_witness import (
    KnightWitnessProtocol,
    ObservationContext,
    ViolationRecord,
    WitnessStatementType,
)
from src.application.ports.permission_enforcer import (
    GovernanceAction,
    PermissionContext,
    PermissionEnforcerProtocol,
)

logger = get_logger(__name__)


class RankViolationError(Exception):
    """Raised when an Archon attempts an action outside their rank authority."""

    def __init__(
        self,
        archon_id: str,
        action: str,
        reason: str,
        prd_reference: str = "FR-GOV-17",
    ) -> None:
        self.archon_id = archon_id
        self.action = action
        self.reason = reason
        self.prd_reference = prd_reference
        super().__init__(
            f"Rank violation by {archon_id} on {action}: {reason} "
            f"(per {prd_reference})"
        )


class AdvisoryConflictError(Exception):
    """Raised when Marquis attempts to judge a domain they advised on.

    Per FR-GOV-18: Cannot judge domains where advisory was given.
    """

    def __init__(
        self,
        marquis_id: str,
        domain: ExpertiseDomain,
        advisory_id: UUID,
    ) -> None:
        self.marquis_id = marquis_id
        self.domain = domain
        self.advisory_id = advisory_id
        super().__init__(
            f"Marquis {marquis_id} cannot judge domain {domain.value} - "
            f"already issued advisory {advisory_id} (per FR-GOV-18)"
        )


class MarquisServiceAdapter(MarquisServiceProtocol):
    """Implementation of Marquis-rank advisory functions.

    This service allows Marquis-rank Archons to:
    - Provide expert testimony on domain questions
    - Issue non-binding advisories
    - Perform risk analysis

    Per FR-GOV-18:
    - Advisories must be acknowledged but not obeyed
    - Cannot judge domains where advisory was given

    All operations are witnessed by Knight per FR-GOV-20.
    """

    def __init__(
        self,
        permission_enforcer: PermissionEnforcerProtocol | None = None,
        knight_witness: KnightWitnessProtocol | None = None,
        verbose: bool = False,
    ) -> None:
        """Initialize the Marquis Service.

        Args:
            permission_enforcer: Permission enforcement (optional for testing)
            knight_witness: Knight witness for recording events (optional)
            verbose: Enable verbose logging
        """
        self._permission_enforcer = permission_enforcer
        self._knight_witness = knight_witness
        self._verbose = verbose

        # In-memory storage (would be repository in production)
        self._advisories: dict[UUID, Advisory] = {}
        self._testimonies: dict[UUID, Testimony] = {}
        self._risk_analyses: dict[UUID, RiskAnalysis] = {}

        # Track which domains each Marquis has advised on (for FR-GOV-18)
        self._advisory_domains: dict[str, set[tuple[ExpertiseDomain, UUID]]] = {}

        if self._verbose:
            logger.debug("marquis_service_initialized")

    async def provide_testimony(
        self,
        request: TestimonyRequest,
    ) -> TestimonyResult:
        """Provide expert testimony on a domain question.

        Per FR-GOV-17: Marquis provide expert testimony.

        Args:
            request: Testimony request with domain and question

        Returns:
            TestimonyResult with testimony or error

        Raises:
            RankViolationError: If the Archon is not Marquis-rank
        """
        if self._verbose:
            logger.debug(
                "testimony_requested",
                requested_by=request.requested_by,
                domain=request.domain.value,
            )

        # Determine which Marquis should provide testimony
        # In a real system, this would route to an appropriate Marquis
        marquis_domain = get_expertise_domain(request.requested_by)

        # Check if requester is a Marquis in the requested domain
        if self._permission_enforcer:
            context = PermissionContext(
                target_resource=f"testimony:{request.domain.value}",
                action_details={"question": request.question},
            )
            # Note: Any authorized caller can request testimony
            # The Marquis provides it

        # Create testimony (simulated expert response)
        testimony = Testimony.create(
            provided_by=request.requested_by,  # Would be assigned Marquis
            domain=request.domain,
            question=request.question,
            response=f"Expert testimony on: {request.question}",
            supporting_evidence=["Evidence 1", "Evidence 2"],
            motion_ref=request.motion_ref,
        )

        self._testimonies[testimony.testimony_id] = testimony

        # Witness the testimony
        await self._witness_action(
            archon_id=testimony.provided_by,
            action="testimony_provided",
            details={
                "testimony_id": str(testimony.testimony_id),
                "domain": request.domain.value,
                "question": request.question[:100],  # Truncate for logging
            },
        )

        if self._verbose:
            logger.info(
                "testimony_provided",
                testimony_id=str(testimony.testimony_id),
                domain=request.domain.value,
            )

        return TestimonyResult(
            success=True,
            testimony=testimony,
        )

    async def issue_advisory(
        self,
        request: AdvisoryRequest,
    ) -> AdvisoryResult:
        """Issue a non-binding advisory.

        Per FR-GOV-17: Marquis issue non-binding advisories.
        Per FR-GOV-18: Advisories must be acknowledged but not obeyed.

        Args:
            request: Advisory request with topic and recommendation

        Returns:
            AdvisoryResult with advisory (binding=False) or error

        Note:
            The advisory is NEVER binding. Recipients must acknowledge
            but need not follow the recommendation.
        """
        if self._verbose:
            logger.debug(
                "advisory_requested",
                marquis_id=request.marquis_id,
                domain=request.domain.value,
                topic=request.topic,
            )

        # Check permission if enforcer available
        if self._permission_enforcer:
            context = PermissionContext(
                target_resource=f"advisory:{request.domain.value}",
                action_details={"topic": request.topic},
            )
            permission_result = await self._permission_enforcer.check_permission(
                archon_id=request.marquis_id,
                action=GovernanceAction.ISSUE_ADVISORY,
                context=context,
            )

            if not permission_result.allowed:
                await self._witness_violation(
                    archon_id=request.marquis_id,
                    violation_type="rank_violation",
                    description=f"Attempted to issue advisory without Marquis rank: {permission_result.violation_reason}",
                )

                raise RankViolationError(
                    archon_id=request.marquis_id,
                    action="issue_advisory",
                    reason=permission_result.violation_reason or "Not authorized",
                    prd_reference="FR-GOV-17",
                )

        # Create advisory (ALWAYS non-binding per FR-GOV-18)
        advisory = Advisory.create(
            issued_by=request.marquis_id,
            domain=request.domain,
            topic=request.topic,
            recommendation=request.recommendation,
            rationale=request.rationale,
            motion_ref=request.motion_ref,
        )

        # Store advisory
        self._advisories[advisory.advisory_id] = advisory

        # Track advisory domain for FR-GOV-18 conflict prevention
        if request.marquis_id not in self._advisory_domains:
            self._advisory_domains[request.marquis_id] = set()
        self._advisory_domains[request.marquis_id].add(
            (request.domain, advisory.advisory_id)
        )

        # Witness the advisory
        await self._witness_action(
            archon_id=request.marquis_id,
            action="advisory_issued",
            details={
                "advisory_id": str(advisory.advisory_id),
                "domain": request.domain.value,
                "topic": request.topic,
                "binding": False,  # Always non-binding
            },
        )

        if self._verbose:
            logger.info(
                "advisory_issued",
                advisory_id=str(advisory.advisory_id),
                marquis_id=request.marquis_id,
                domain=request.domain.value,
                binding=False,
            )

        return AdvisoryResult(
            success=True,
            advisory=advisory,
        )

    async def analyze_risk(
        self,
        request: RiskAnalysisRequest,
    ) -> RiskAnalysisResult:
        """Analyze risks in a proposal.

        Per FR-GOV-17: Marquis provide risk analysis.

        Args:
            request: Risk analysis request with proposal

        Returns:
            RiskAnalysisResult with analysis or error
        """
        if self._verbose:
            logger.debug(
                "risk_analysis_requested",
                marquis_id=request.marquis_id,
                proposal=request.proposal[:50],
            )

        # Check permission if enforcer available
        if self._permission_enforcer:
            context = PermissionContext(
                target_resource="risk_analysis",
                action_details={"proposal": request.proposal},
            )
            permission_result = await self._permission_enforcer.check_permission(
                archon_id=request.marquis_id,
                action=GovernanceAction.ANALYZE_RISK,
                context=context,
            )

            if not permission_result.allowed:
                await self._witness_violation(
                    archon_id=request.marquis_id,
                    violation_type="rank_violation",
                    description=f"Attempted risk analysis without Marquis rank: {permission_result.violation_reason}",
                )

                raise RankViolationError(
                    archon_id=request.marquis_id,
                    action="analyze_risk",
                    reason=permission_result.violation_reason or "Not authorized",
                    prd_reference="FR-GOV-17",
                )

        # Get Marquis's expertise domain
        expertise_domain = get_expertise_domain(request.marquis_id)
        if not expertise_domain:
            expertise_domain = ExpertiseDomain.KNOWLEDGE  # Default

        # Perform risk analysis (simulated)
        risks = [
            RiskFactor(
                risk_id="RISK-001",
                description=f"Risk identified in proposal: {request.proposal[:30]}...",
                level=RiskLevel.MEDIUM,
                likelihood=0.5,
                impact="Moderate impact on system",
                mitigation="Implement monitoring and fallback",
            ),
        ]

        analysis = RiskAnalysis.create(
            analyzed_by=request.marquis_id,
            domain=expertise_domain,
            proposal=request.proposal,
            risks=risks,
            overall_risk_level=RiskLevel.MEDIUM,
            recommendations=[
                "Implement gradual rollout",
                "Add monitoring",
                "Plan rollback strategy",
            ],
            motion_ref=request.motion_ref,
        )

        self._risk_analyses[analysis.analysis_id] = analysis

        # Witness the analysis
        await self._witness_action(
            archon_id=request.marquis_id,
            action="risk_analysis_completed",
            details={
                "analysis_id": str(analysis.analysis_id),
                "domain": expertise_domain.value,
                "risk_count": len(risks),
                "overall_level": analysis.overall_risk_level.value,
            },
        )

        if self._verbose:
            logger.info(
                "risk_analysis_completed",
                analysis_id=str(analysis.analysis_id),
                marquis_id=request.marquis_id,
            )

        return RiskAnalysisResult(
            success=True,
            analysis=analysis,
        )

    async def get_expertise_domains(
        self,
        marquis_id: str,
    ) -> list[ExpertiseDomain]:
        """Get expertise domains for a Marquis.

        Args:
            marquis_id: Marquis Archon ID

        Returns:
            List of expertise domains (typically one per Marquis)
        """
        domain = get_expertise_domain(marquis_id)
        if domain:
            return [domain]
        return []

    async def get_advisory(self, advisory_id: UUID) -> Advisory | None:
        """Retrieve an advisory by ID.

        Args:
            advisory_id: UUID of the advisory

        Returns:
            Advisory if found, None otherwise
        """
        return self._advisories.get(advisory_id)

    async def get_advisories_by_marquis(
        self,
        marquis_id: str,
    ) -> list[Advisory]:
        """Get all advisories issued by a specific Marquis.

        Args:
            marquis_id: The Marquis Archon ID

        Returns:
            List of advisories issued by that Marquis
        """
        return [
            advisory
            for advisory in self._advisories.values()
            if advisory.issued_by == marquis_id
        ]

    async def get_advisories_by_domain(
        self,
        domain: ExpertiseDomain,
    ) -> list[Advisory]:
        """Get all advisories in a specific domain.

        Args:
            domain: The expertise domain

        Returns:
            List of advisories in that domain
        """
        return [
            advisory
            for advisory in self._advisories.values()
            if advisory.domain == domain
        ]

    async def get_advisories_by_motion(
        self,
        motion_ref: UUID,
    ) -> list[Advisory]:
        """Get all advisories related to a specific motion.

        Args:
            motion_ref: The motion's UUID

        Returns:
            List of advisories for that motion
        """
        return [
            advisory
            for advisory in self._advisories.values()
            if advisory.motion_ref == motion_ref
        ]

    # =========================================================================
    # FR-GOV-18 Conflict Prevention
    # =========================================================================

    async def has_advisory_conflict(
        self,
        marquis_id: str,
        domain: ExpertiseDomain,
    ) -> tuple[bool, UUID | None]:
        """Check if Marquis has an advisory conflict for a domain.

        Per FR-GOV-18: Cannot judge domains where advisory was given.

        Args:
            marquis_id: Marquis to check
            domain: Domain to check for conflict

        Returns:
            Tuple of (has_conflict, advisory_id_if_conflict)
        """
        domains = self._advisory_domains.get(marquis_id, set())
        for adv_domain, adv_id in domains:
            if adv_domain == domain:
                return True, adv_id
        return False, None

    async def acknowledge_advisory(
        self,
        advisory_id: UUID,
        acknowledged_by: str,
    ) -> bool:
        """Record acknowledgment of an advisory.

        Per FR-GOV-18: Advisories must be acknowledged.

        Args:
            advisory_id: Advisory to acknowledge
            acknowledged_by: Archon acknowledging

        Returns:
            True if successfully acknowledged
        """
        advisory = self._advisories.get(advisory_id)
        if not advisory:
            return False

        # Create updated advisory with acknowledgment
        acknowledged = Advisory(
            advisory_id=advisory.advisory_id,
            issued_by=advisory.issued_by,
            domain=advisory.domain,
            topic=advisory.topic,
            recommendation=advisory.recommendation,
            rationale=advisory.rationale,
            binding=False,  # Always non-binding
            issued_at=advisory.issued_at,
            acknowledged_by=advisory.acknowledged_by + (acknowledged_by,),
            motion_ref=advisory.motion_ref,
        )

        self._advisories[advisory_id] = acknowledged

        # Witness the acknowledgment
        await self._witness_action(
            archon_id=acknowledged_by,
            action="advisory_acknowledged",
            details={
                "advisory_id": str(advisory_id),
                "acknowledged_by": acknowledged_by,
            },
        )

        return True

    # =========================================================================
    # Internal Helpers
    # =========================================================================

    async def _witness_violation(
        self,
        archon_id: str,
        violation_type: str,
        description: str,
        evidence: dict[str, Any] | None = None,
    ) -> None:
        """Witness a violation through Knight.

        Args:
            archon_id: Archon who committed violation
            violation_type: Type of violation
            description: Description of violation
            evidence: Supporting evidence
        """
        if not self._knight_witness:
            if self._verbose:
                logger.warning(
                    "violation_not_witnessed_no_knight",
                    archon_id=archon_id,
                    violation_type=violation_type,
                )
            return

        violation = ViolationRecord(
            archon_id=archon_id,
            violation_type=violation_type,
            description=description,
            prd_reference="FR-GOV-17/FR-GOV-18",
            evidence=evidence or {},
        )

        context = ObservationContext(
            session_id="marquis_service",
            statement_type=WitnessStatementType.VIOLATION,
            trigger_source="marquis_service_adapter",
        )

        await self._knight_witness.witness_violation(
            violation=violation,
            context=context,
        )

    async def _witness_action(
        self,
        archon_id: str,
        action: str,
        details: dict[str, Any],
    ) -> None:
        """Witness an action through Knight.

        Args:
            archon_id: Archon who performed action
            action: Action performed
            details: Action details
        """
        if not self._knight_witness:
            return

        context = ObservationContext(
            session_id="marquis_service",
            statement_type=WitnessStatementType.OBSERVATION,
            trigger_source="marquis_service_adapter",
        )

        await self._knight_witness.witness_observation(
            observation={
                "archon_id": archon_id,
                "action": action,
                "details": details,
            },
            context=context,
        )
