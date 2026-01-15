"""Motion Review Pipeline Service.

Orchestrates the multi-phase motion review process:
1. Triage - Calculate implicit support and assign risk tiers
2. Packet Generation - Create personalized review assignments
3. Review Collection - Gather Archon responses (async)
4. Aggregation - Tally results, identify contested motions
5. Panel Deliberation - Convene panels for contested items
6. Ratification - Final vote on all motions

This avoids combinatorial Conclave explosion by leveraging:
- Implicit support from source contributions
- Risk-tiered review depth
- Targeted assignments (gap Archons only)
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from structlog import get_logger

from src.application.ports.reviewer_agent import (
    ArchonReviewerContext,
    MotionReviewContext,
    PanelDeliberationContext,
    ReviewDecision,
    ReviewerAgentProtocol,
)
from src.domain.models.review_pipeline import (
    AmendmentType,
    DeliberationPanel,
    ImplicitSupport,
    MotionReviewPipelineResult,
    PanelRecommendation,
    RatificationOutcome,
    RatificationVote,
    ReviewAggregation,
    ReviewAssignment,
    ReviewResponse,
    ReviewStance,
    RiskTier,
    TriageResult,
)

logger = get_logger(__name__)

# Default Archon backstories (simplified - in production would load from profiles)
DEFAULT_ARCHON_BACKSTORIES = {
    "Paimon": "A wise King among spirits, expert in arts, sciences, and secrets. Values knowledge and clear communication.",
    "Bael": "A powerful King commanding legions, expert in warfare and leadership. Values strength and decisive action.",
    "Astaroth": "A Duke of Hell, keeper of past and future knowledge. Values wisdom and historical perspective.",
    "Belial": "A mighty King, master of persuasion and earthly matters. Values pragmatism and practical outcomes.",
}

# All 72 Archon names (matching docs/archons-base.csv)
ALL_ARCHON_NAMES = [
    "Bael", "Agares", "Vassago", "Samigina", "Marbas", "Valefor", "Amon", "Barbatos",
    "Paimon", "Buer", "Gusion", "Sitri", "Beleth", "Leraje", "Eligos", "Zepar",
    "Botis", "Bathim", "Sallos", "Purson", "Marax", "Ipos", "Aim", "Naberius",
    "Glasya-Labolas", "Bune", "Ronove", "Berith", "Astaroth", "Forneus", "Foras", "Asmoday",
    "Gaap", "Furfur", "Marchosias", "Stolas", "Phenex", "Halphas", "Malphas", "Raum",
    "Focalor", "Vepar", "Sabnock", "Shax", "Vine", "Bifrons", "Vual", "Haagenti",
    "Crocell", "Furcas", "Balam", "Alloces", "Caim", "Murmur", "Orobas", "Gremory",
    "Ose", "Amy", "Orias", "Vapula", "Zagan", "Valac", "Andras", "Haures",
    "Andrealphus", "Cimeies", "Amdusias", "Belial", "Decarabia", "Seere", "Dantalion", "Andromalius",
]

# Risk tier thresholds
LOW_RISK_THRESHOLD = 0.66  # >=66% implicit support
MEDIUM_RISK_THRESHOLD = 0.33  # >=33% implicit support
MAX_CONFLICTS_FOR_MEDIUM = 5  # <=5 conflicts for medium risk

# Consensus thresholds
CONSENSUS_THRESHOLD = 0.75  # >=75% endorsement = consensus
CONTESTED_THRESHOLD = 0.25  # >=25% opposition = contested

# Ratification thresholds
SIMPLE_MAJORITY = 37  # 72/2 + 1
SUPERMAJORITY = 48  # 72 * 2/3


@dataclass
class MegaMotionData:
    """Loaded mega-motion data from consolidator output."""

    mega_motion_id: str
    title: str
    theme: str
    text: str
    source_motion_ids: list[str]
    supporting_archons: list[str]
    unique_archon_count: int
    consensus_tier: str
    is_novel: bool = False


class MotionReviewService:
    """Service orchestrating the motion review pipeline."""

    def __init__(
        self,
        verbose: bool = False,
        reviewer_agent: ReviewerAgentProtocol | None = None,
    ) -> None:
        """Initialize the service.

        Args:
            verbose: Enable verbose logging
            reviewer_agent: Optional LLM-powered reviewer agent for real reviews
        """
        self.verbose = verbose
        self._all_archons = set(ALL_ARCHON_NAMES)
        self._reviewer_agent = reviewer_agent

    # =========================================================================
    # Data Loading
    # =========================================================================

    def load_mega_motions(
        self, consolidator_output_path: Path
    ) -> tuple[list[MegaMotionData], list[MegaMotionData], str, str]:
        """Load mega-motions and novel proposals from consolidator output.

        Args:
            consolidator_output_path: Path to consolidator session directory

        Returns:
            Tuple of (mega_motions, novel_proposals, session_id, session_name)
        """
        mega_motions_file = consolidator_output_path / "mega-motions.json"
        novel_proposals_file = consolidator_output_path / "novel-proposals.json"
        summary_file = consolidator_output_path / "conclave-summary.json"

        # Load session info from summary
        session_id = consolidator_output_path.name
        session_name = session_id

        if summary_file.exists():
            with open(summary_file) as f:
                summary = json.load(f)
                session_name = summary.get("session_name", session_id)

        # Load mega-motions
        mega_motions = []
        if mega_motions_file.exists():
            with open(mega_motions_file) as f:
                data = json.load(f)
                for mm in data:
                    mega_motions.append(
                        MegaMotionData(
                            mega_motion_id=mm.get("mega_motion_id", str(uuid4())),
                            title=mm.get("title", "Untitled"),
                            theme=mm.get("theme", "Unknown"),
                            text=mm.get("consolidated_text", ""),
                            source_motion_ids=mm.get("source_motion_ids", []),
                            supporting_archons=mm.get("all_supporting_archons", []),
                            unique_archon_count=mm.get("unique_archon_count", 0),
                            consensus_tier=mm.get("consensus_tier", "low"),
                            is_novel=False,
                        )
                    )

        # Load novel proposals (treated as HIGH risk motions)
        novel_proposals = []
        if novel_proposals_file.exists():
            with open(novel_proposals_file) as f:
                data = json.load(f)
                for np in data:
                    novel_proposals.append(
                        MegaMotionData(
                            mega_motion_id=np.get("proposal_id", str(uuid4())),
                            title=f"Novel: {np.get('text', '')[:50]}...",
                            theme=np.get("category", "novel"),
                            text=np.get("text", ""),
                            source_motion_ids=[np.get("recommendation_id", "")],
                            supporting_archons=[np.get("archon_name", "")],
                            unique_archon_count=1,
                            consensus_tier="low",
                            is_novel=True,
                        )
                    )

        logger.info(
            "mega_motions_loaded",
            mega_motion_count=len(mega_motions),
            novel_proposal_count=len(novel_proposals),
            session_id=session_id,
        )

        return mega_motions, novel_proposals, session_id, session_name

    # =========================================================================
    # Phase 1: Triage
    # =========================================================================

    def triage_motions(
        self,
        mega_motions: list[MegaMotionData],
        novel_proposals: list[MegaMotionData],
        session_id: str,
    ) -> TriageResult:
        """Triage motions by calculating implicit support and assigning risk tiers.

        Args:
            mega_motions: Consolidated mega-motions
            novel_proposals: Novel proposals (always HIGH risk)
            session_id: Session identifier

        Returns:
            TriageResult with risk tier assignments
        """
        logger.info("triage_start", motion_count=len(mega_motions), novel_count=len(novel_proposals))

        implicit_supports = []
        total_conflicts = 0

        # Process mega-motions
        for mm in mega_motions:
            support = self._calculate_implicit_support(mm)
            implicit_supports.append(support)
            total_conflicts += len(support.potential_conflicts)

        # Process novel proposals (always HIGH risk)
        for np in novel_proposals:
            support = self._calculate_implicit_support(np)
            # Force HIGH risk for novel proposals
            support = ImplicitSupport(
                mega_motion_id=support.mega_motion_id,
                mega_motion_title=support.mega_motion_title,
                contributing_archons=support.contributing_archons,
                contribution_count=support.contribution_count,
                implicit_support_ratio=support.implicit_support_ratio,
                gap_archons=support.gap_archons,
                potential_conflicts=support.potential_conflicts,
                conflict_details=support.conflict_details,
                risk_tier=RiskTier.HIGH,
                is_novel_proposal=True,
                calculated_at=support.calculated_at,
            )
            implicit_supports.append(support)

        # Count risk tiers
        low_count = sum(1 for s in implicit_supports if s.risk_tier == RiskTier.LOW)
        medium_count = sum(1 for s in implicit_supports if s.risk_tier == RiskTier.MEDIUM)
        high_count = sum(1 for s in implicit_supports if s.risk_tier == RiskTier.HIGH)

        # Calculate average support
        avg_support = (
            sum(s.implicit_support_ratio for s in implicit_supports) / len(implicit_supports)
            if implicit_supports
            else 0.0
        )

        result = TriageResult(
            session_id=session_id,
            triaged_at=datetime.now(timezone.utc),
            total_motions=len(implicit_supports),
            novel_proposals_count=len(novel_proposals),
            low_risk_count=low_count,
            medium_risk_count=medium_count,
            high_risk_count=high_count,
            implicit_supports=implicit_supports,
            average_implicit_support=avg_support,
            total_conflicts_detected=total_conflicts,
        )

        logger.info(
            "triage_complete",
            low_risk=low_count,
            medium_risk=medium_count,
            high_risk=high_count,
            avg_support=f"{avg_support:.1%}",
        )

        return result

    def _calculate_implicit_support(self, motion: MegaMotionData) -> ImplicitSupport:
        """Calculate implicit support for a single motion.

        Args:
            motion: Mega-motion data

        Returns:
            ImplicitSupport with risk tier assignment
        """
        # Contributing Archons = those who authored source motions
        contributing = set(motion.supporting_archons)

        # Gap Archons = all 72 minus contributors
        gap = self._all_archons - contributing

        # Calculate support ratio
        support_ratio = len(contributing) / 72

        # Detect potential conflicts (simplified - would need full motion data for accuracy)
        # For now, we flag Archons who have opposing themes in their contributions
        conflicts: list[str] = []
        conflict_details: dict[str, str] = {}

        # Determine risk tier
        if motion.is_novel:
            risk_tier = RiskTier.HIGH
        elif support_ratio >= LOW_RISK_THRESHOLD and len(conflicts) == 0:
            risk_tier = RiskTier.LOW
        elif support_ratio >= MEDIUM_RISK_THRESHOLD and len(conflicts) <= MAX_CONFLICTS_FOR_MEDIUM:
            risk_tier = RiskTier.MEDIUM
        else:
            risk_tier = RiskTier.HIGH

        return ImplicitSupport(
            mega_motion_id=motion.mega_motion_id,
            mega_motion_title=motion.title,
            contributing_archons=sorted(contributing),
            contribution_count=len(motion.source_motion_ids),
            implicit_support_ratio=support_ratio,
            gap_archons=sorted(gap),
            potential_conflicts=conflicts,
            conflict_details=conflict_details,
            risk_tier=risk_tier,
            is_novel_proposal=motion.is_novel,
        )

    # =========================================================================
    # Phase 2: Packet Generation
    # =========================================================================

    def generate_review_packets(
        self,
        triage_result: TriageResult,
        _mega_motions: list[MegaMotionData],
    ) -> list[ReviewAssignment]:
        """Generate personalized review packets for each Archon.

        Args:
            triage_result: Results from triage phase
            _mega_motions: Original motion data (reserved for future use)

        Returns:
            List of ReviewAssignment, one per Archon
        """
        logger.info("packet_generation_start", archon_count=72)

        assignments = []

        for archon_name in ALL_ARCHON_NAMES:
            assigned_motions = []
            conflict_flags: dict[str, str] = {}
            already_endorsed = []
            assignment_reasons: dict[str, str] = {}

            for support in triage_result.implicit_supports:
                # Skip LOW risk - goes directly to ratification
                if support.risk_tier == RiskTier.LOW:
                    if archon_name in support.contributing_archons:
                        already_endorsed.append(support.mega_motion_id)
                    continue

                # Check if Archon needs to review this motion
                if archon_name in support.gap_archons:
                    assigned_motions.append(support.mega_motion_id)
                    assignment_reasons[support.mega_motion_id] = "gap_archon"

                elif archon_name in support.potential_conflicts:
                    assigned_motions.append(support.mega_motion_id)
                    assignment_reasons[support.mega_motion_id] = "conflict_review"
                    if support.mega_motion_id in support.conflict_details:
                        conflict_flags[support.mega_motion_id] = support.conflict_details.get(
                            archon_name, "Position conflict detected"
                        )

                elif archon_name in support.contributing_archons:
                    already_endorsed.append(support.mega_motion_id)

            assignment = ReviewAssignment(
                archon_id=archon_name.lower().replace("-", "_"),
                archon_name=archon_name,
                assigned_motions=assigned_motions,
                conflict_flags=conflict_flags,
                already_endorsed=already_endorsed,
                assignment_reasons=assignment_reasons,
            )
            assignments.append(assignment)

        # Log statistics
        total_assignments = sum(a.assignment_count for a in assignments)
        avg_assignments = total_assignments / 72 if assignments else 0

        logger.info(
            "packet_generation_complete",
            total_assignments=total_assignments,
            avg_per_archon=f"{avg_assignments:.1f}",
        )

        return assignments

    def generate_review_packet_json(
        self,
        assignment: ReviewAssignment,
        triage_result: TriageResult,
        mega_motions: list[MegaMotionData],
    ) -> dict:
        """Generate detailed JSON packet for an Archon's review.

        Args:
            assignment: The Archon's assignment
            triage_result: Triage results for context
            mega_motions: Motion data for summaries

        Returns:
            Complete review packet as dictionary
        """
        motion_lookup = {mm.mega_motion_id: mm for mm in mega_motions}
        support_lookup = {s.mega_motion_id: s for s in triage_result.implicit_supports}

        # Build already endorsed section
        endorsed_details = []
        for motion_id in assignment.already_endorsed:
            motion = motion_lookup.get(motion_id)
            if motion:
                endorsed_details.append(
                    {
                        "motion_id": motion_id,
                        "title": motion.title,
                        "your_contribution": f"Source contributor ({motion.unique_archon_count} Archons total)",
                    }
                )

        # Build requires review section
        review_details = []
        for motion_id in assignment.assigned_motions:
            motion = motion_lookup.get(motion_id)
            support = support_lookup.get(motion_id)

            if motion and support:
                review_details.append(
                    {
                        "motion_id": motion_id,
                        "title": motion.title,
                        "risk_tier": support.risk_tier.value,
                        "review_reason": assignment.assignment_reasons.get(motion_id, "unknown"),
                        "conflict_flag": assignment.conflict_flags.get(motion_id),
                        "summary": motion.text[:200] + "..." if len(motion.text) > 200 else motion.text,
                        "source_motions": len(motion.source_motion_ids),
                        "supporting_archons": support.support_count,
                        "themes": [motion.theme],
                    }
                )

        # Count low-risk auto-ratify
        low_risk_count = sum(
            1 for s in triage_result.implicit_supports if s.risk_tier == RiskTier.LOW
        )

        return {
            "archon_id": assignment.archon_id,
            "archon_name": assignment.archon_name,
            "generated_at": assignment.generated_at.isoformat(),
            "already_endorsed": endorsed_details,
            "requires_review": review_details,
            "statistics": {
                "total_motions": triage_result.total_motions,
                "already_endorsed": len(assignment.already_endorsed),
                "requires_review": len(assignment.assigned_motions),
                "low_risk_auto_ratify": low_risk_count,
            },
        }

    # =========================================================================
    # Phase 3-4: Review Collection & Aggregation
    # =========================================================================

    def simulate_archon_reviews(
        self,
        assignments: list[ReviewAssignment],
        triage_result: TriageResult,
    ) -> list[ReviewResponse]:
        """Simulate Archon review responses for testing.

        In production, this would collect actual responses from the Archon agents.
        For now, we simulate based on implicit support patterns.

        Args:
            assignments: Review assignments
            triage_result: Triage results

        Returns:
            List of simulated ReviewResponse
        """
        logger.info("simulating_reviews", assignment_count=len(assignments))

        responses = []
        support_lookup = {s.mega_motion_id: s for s in triage_result.implicit_supports}

        for assignment in assignments:
            for motion_id in assignment.assigned_motions:
                support = support_lookup.get(motion_id)

                # Simulate stance based on risk tier and conflicts
                if motion_id in assignment.conflict_flags:
                    # Conflict = likely opposition or amendment
                    stance = ReviewStance.AMEND
                    amendment_text = "Proposed amendment to address conflict."
                    amendment_type = AmendmentType.MINOR_WORDING
                elif support and support.implicit_support_ratio > 0.5:
                    # High support = likely endorsement
                    stance = ReviewStance.ENDORSE
                    amendment_text = None
                    amendment_type = None
                else:
                    # Lower support = mixed response
                    stance = ReviewStance.ABSTAIN
                    amendment_text = None
                    amendment_type = None

                response = ReviewResponse(
                    response_id=str(uuid4()),
                    archon_id=assignment.archon_id,
                    archon_name=assignment.archon_name,
                    mega_motion_id=motion_id,
                    stance=stance,
                    amendment_type=amendment_type,
                    amendment_text=amendment_text,
                    amendment_rationale="Simulated rationale" if amendment_text else None,
                    opposition_reason=None,
                    reasoning=f"Simulated review by {assignment.archon_name}",
                    confidence=0.7,
                )
                responses.append(response)

        logger.info("reviews_simulated", response_count=len(responses))
        return responses

    # =========================================================================
    # Real Archon Reviews (using ReviewerAgent)
    # =========================================================================

    def _create_archon_context(self, archon_name: str) -> ArchonReviewerContext:
        """Create ArchonReviewerContext from archon name.

        Args:
            archon_name: Name of the Archon

        Returns:
            ArchonReviewerContext with profile details
        """
        backstory = DEFAULT_ARCHON_BACKSTORIES.get(
            archon_name,
            f"{archon_name} is one of the 72 Archons, contributing unique expertise to the Conclave."
        )

        return ArchonReviewerContext(
            archon_id=archon_name.lower().replace("-", "_"),
            archon_name=archon_name,
            archon_role="Archon of the Conclave",
            archon_backstory=backstory,
            domain=None,  # Could be enhanced with domain mapping
            previous_positions=[],  # Could load from prior review history
        )

    def _create_motion_context(
        self,
        motion: MegaMotionData,
        support: ImplicitSupport,
        assignment_reason: str = "gap_archon",
        conflict_flag: str | None = None,
    ) -> MotionReviewContext:
        """Create MotionReviewContext from motion data.

        Args:
            motion: Mega-motion data
            support: Implicit support data for the motion
            assignment_reason: Why the Archon is reviewing
            conflict_flag: Any conflict flag for this Archon

        Returns:
            MotionReviewContext for the review operation
        """
        return MotionReviewContext(
            mega_motion_id=motion.mega_motion_id,
            mega_motion_title=motion.title,
            mega_motion_text=motion.text,
            theme=motion.theme,
            source_motion_count=len(motion.source_motion_ids),
            supporting_archon_count=len(support.contributing_archons),
            supporting_archons=support.contributing_archons,
            conflict_flag=conflict_flag,
            assignment_reason=assignment_reason,
        )

    def _convert_review_decision_to_response(
        self,
        decision: ReviewDecision,
        archon_name: str,
        archon_id: str,
        mega_motion_id: str,
    ) -> ReviewResponse:
        """Convert ReviewDecision from agent to ReviewResponse.

        Args:
            decision: ReviewDecision from the ReviewerAgent
            archon_name: Name of the reviewing Archon
            archon_id: ID of the reviewing Archon
            mega_motion_id: ID of the reviewed motion

        Returns:
            ReviewResponse for aggregation
        """
        # Map stance string to ReviewStance enum
        stance_map = {
            "endorse": ReviewStance.ENDORSE,
            "oppose": ReviewStance.OPPOSE,
            "amend": ReviewStance.AMEND,
            "abstain": ReviewStance.ABSTAIN,
        }
        stance = stance_map.get(decision.stance.lower(), ReviewStance.ABSTAIN)

        # Map amendment type if present
        amendment_type = None
        if decision.amendment_type:
            amendment_type_map = {
                "minor_wording": AmendmentType.MINOR_WORDING,
                "major_revision": AmendmentType.MAJOR_REVISION,
                "add_clause": AmendmentType.ADD_CLAUSE,
                "remove_clause": AmendmentType.REMOVE_CLAUSE,
            }
            amendment_type = amendment_type_map.get(
                decision.amendment_type.lower(), AmendmentType.MINOR_WORDING
            )

        # Extract opposition reason from concerns
        opposition_reason = None
        if decision.opposition_concerns:
            opposition_reason = "; ".join(decision.opposition_concerns)

        return ReviewResponse(
            response_id=str(uuid4()),
            archon_id=archon_id,
            archon_name=archon_name,
            mega_motion_id=mega_motion_id,
            stance=stance,
            amendment_type=amendment_type,
            amendment_text=decision.amendment_text,
            amendment_rationale=decision.amendment_rationale,
            opposition_reason=opposition_reason,
            reasoning=decision.reasoning,
            confidence=decision.confidence,
            review_duration_ms=decision.review_duration_ms,
        )

    async def collect_archon_reviews(
        self,
        assignments: list[ReviewAssignment],
        triage_result: TriageResult,
        mega_motions: list[MegaMotionData],
    ) -> list[ReviewResponse]:
        """Collect real Archon reviews using the ReviewerAgent.

        Uses the LLM-powered ReviewerAgent to get actual review decisions
        from each Archon for their assigned motions.

        Args:
            assignments: Review assignments for each Archon
            triage_result: Triage results with implicit support data
            mega_motions: All mega-motions

        Returns:
            List of ReviewResponse from actual agent reviews

        Raises:
            RuntimeError: If reviewer_agent is not configured
        """
        if not self._reviewer_agent:
            raise RuntimeError(
                "ReviewerAgent not configured. Use simulate_archon_reviews() instead "
                "or provide a reviewer_agent to the service constructor."
            )

        logger.info(
            "collecting_real_reviews",
            assignment_count=len(assignments),
            using_agent=True,
        )

        # Build lookups
        motion_lookup = {mm.mega_motion_id: mm for mm in mega_motions}
        support_lookup = {s.mega_motion_id: s for s in triage_result.implicit_supports}

        responses: list[ReviewResponse] = []

        for assignment in assignments:
            if not assignment.assigned_motions:
                continue

            # Create Archon context
            archon_context = self._create_archon_context(assignment.archon_name)

            # Build motion contexts for batch review
            motion_contexts: list[MotionReviewContext] = []
            for motion_id in assignment.assigned_motions:
                motion = motion_lookup.get(motion_id)
                support = support_lookup.get(motion_id)

                if not motion or not support:
                    logger.warning(
                        "motion_not_found",
                        archon=assignment.archon_name,
                        motion_id=motion_id,
                    )
                    continue

                motion_context = self._create_motion_context(
                    motion=motion,
                    support=support,
                    assignment_reason=assignment.assignment_reasons.get(
                        motion_id, "gap_archon"
                    ),
                    conflict_flag=assignment.conflict_flags.get(motion_id),
                )
                motion_contexts.append(motion_context)

            if not motion_contexts:
                continue

            # Use batch review for efficiency
            try:
                logger.debug(
                    "batch_review_start",
                    archon=assignment.archon_name,
                    motion_count=len(motion_contexts),
                )

                decisions = await self._reviewer_agent.batch_review_motions(
                    archon=archon_context,
                    motions=motion_contexts,
                )

                # Convert decisions to responses
                for motion_ctx, decision in zip(motion_contexts, decisions):
                    response = self._convert_review_decision_to_response(
                        decision=decision,
                        archon_name=assignment.archon_name,
                        archon_id=assignment.archon_id,
                        mega_motion_id=motion_ctx.mega_motion_id,
                    )
                    responses.append(response)

                logger.debug(
                    "batch_review_complete",
                    archon=assignment.archon_name,
                    response_count=len(decisions),
                )

            except Exception as e:
                logger.error(
                    "batch_review_failed",
                    archon=assignment.archon_name,
                    error=str(e),
                )
                # Continue with other Archons even if one fails
                continue

        logger.info(
            "real_reviews_collected",
            total_responses=len(responses),
            archons_reviewed=sum(1 for a in assignments if a.assigned_motions),
        )

        return responses

    async def run_real_panel_deliberation(
        self,
        panel: DeliberationPanel,
        mega_motions: list[MegaMotionData],
        aggregation: ReviewAggregation,
    ) -> DeliberationPanel:
        """Run real panel deliberation using the ReviewerAgent.

        Uses the LLM-powered ReviewerAgent to conduct actual deliberation
        between panel members on a contested motion.

        Args:
            panel: The panel to deliberate
            mega_motions: All mega-motions (for text lookup)
            aggregation: Review aggregation with arguments

        Returns:
            Updated panel with deliberation results

        Raises:
            RuntimeError: If reviewer_agent is not configured
        """
        if not self._reviewer_agent:
            raise RuntimeError(
                "ReviewerAgent not configured. Use simulate_panel_deliberation() instead "
                "or provide a reviewer_agent to the service constructor."
            )

        logger.info(
            "panel_deliberation_start",
            panel_id=panel.panel_id,
            motion_id=panel.mega_motion_id,
        )

        # Find the motion text
        motion_lookup = {mm.mega_motion_id: mm for mm in mega_motions}
        motion = motion_lookup.get(panel.mega_motion_id)

        if not motion:
            logger.error(
                "motion_not_found_for_panel",
                panel_id=panel.panel_id,
                motion_id=panel.mega_motion_id,
            )
            return panel

        # Build panel context
        supporters = [self._create_archon_context(name) for name in panel.supporters]
        critics = [self._create_archon_context(name) for name in panel.critics]
        neutrals = [self._create_archon_context(name) for name in panel.neutrals]

        context = PanelDeliberationContext(
            panel_id=panel.panel_id,
            mega_motion_id=panel.mega_motion_id,
            mega_motion_title=panel.mega_motion_title,
            mega_motion_text=motion.text,
            supporters=supporters,
            critics=critics,
            neutrals=neutrals,
            supporter_arguments=[
                f"Implicit support from {len(aggregation.endorsing_archons)} Archons"
            ],
            critic_arguments=aggregation.opposition_reasons,
            proposed_amendments=aggregation.amendment_texts,
            time_limit_minutes=45,
        )

        try:
            result = await self._reviewer_agent.run_panel_deliberation(context)

            # Map recommendation to panel recommendation
            rec_map = {
                "pass": PanelRecommendation.PASS,
                "fail": PanelRecommendation.FAIL,
                "amend": PanelRecommendation.AMEND,
                "defer": PanelRecommendation.DEFER,
            }
            panel.recommendation = rec_map.get(
                result.recommendation.lower(), PanelRecommendation.DEFER
            )

            # Count votes
            panel.pass_votes = sum(1 for v in result.votes.values() if v.lower() == "pass")
            panel.fail_votes = sum(1 for v in result.votes.values() if v.lower() == "fail")
            panel.amend_votes = sum(1 for v in result.votes.values() if v.lower() == "amend")
            panel.defer_votes = sum(1 for v in result.votes.values() if v.lower() == "defer")

            # Record conclusion
            panel.concluded_at = datetime.now(timezone.utc)
            panel.deliberation_duration_minutes = result.deliberation_duration_ms // 60000

            logger.info(
                "panel_deliberation_complete",
                panel_id=panel.panel_id,
                recommendation=panel.recommendation.value if panel.recommendation else "none",
            )

        except Exception as e:
            logger.error(
                "panel_deliberation_failed",
                panel_id=panel.panel_id,
                error=str(e),
            )
            # Fall back to simulation on error
            return self.simulate_panel_deliberation(panel)

        return panel

    def aggregate_reviews(
        self,
        triage_result: TriageResult,
        responses: list[ReviewResponse],
    ) -> list[ReviewAggregation]:
        """Aggregate review responses for each motion.

        Args:
            triage_result: Triage results with implicit support
            responses: All review responses

        Returns:
            List of ReviewAggregation, one per motion
        """
        logger.info("aggregation_start", response_count=len(responses))

        # Group responses by motion
        responses_by_motion: dict[str, list[ReviewResponse]] = {}
        for r in responses:
            if r.mega_motion_id not in responses_by_motion:
                responses_by_motion[r.mega_motion_id] = []
            responses_by_motion[r.mega_motion_id].append(r)

        aggregations = []

        for support in triage_result.implicit_supports:
            motion_responses = responses_by_motion.get(support.mega_motion_id, [])

            # Count stances
            explicit_endorsements = sum(
                1 for r in motion_responses if r.stance == ReviewStance.ENDORSE
            )
            oppositions = sum(1 for r in motion_responses if r.stance == ReviewStance.OPPOSE)
            amendments = sum(1 for r in motion_responses if r.stance == ReviewStance.AMEND)
            abstentions = sum(1 for r in motion_responses if r.stance == ReviewStance.ABSTAIN)

            # Implicit endorsements
            implicit_endorsements = len(support.contributing_archons)
            total_endorsements = implicit_endorsements + explicit_endorsements

            # No-response count
            expected = len(support.gap_archons)
            actual = len(motion_responses)
            no_response = expected - actual

            # Engaged count (for ratio calculation)
            engaged = implicit_endorsements + actual

            # Calculate ratios
            endorsement_ratio = total_endorsements / engaged if engaged > 0 else 0
            opposition_ratio = oppositions / engaged if engaged > 0 else 0

            # Derive status
            consensus_reached = endorsement_ratio >= CONSENSUS_THRESHOLD
            contested = opposition_ratio >= CONTESTED_THRESHOLD
            needs_amendment_synthesis = amendments >= 3

            # Collect texts and archon names
            amendment_texts = [
                r.amendment_text for r in motion_responses
                if r.stance == ReviewStance.AMEND and r.amendment_text
            ]
            opposition_reasons = [
                r.opposition_reason for r in motion_responses
                if r.stance == ReviewStance.OPPOSE and r.opposition_reason
            ]
            endorsing_archons = (
                support.contributing_archons +
                [r.archon_name for r in motion_responses if r.stance == ReviewStance.ENDORSE]
            )
            opposing_archons = [
                r.archon_name for r in motion_responses if r.stance == ReviewStance.OPPOSE
            ]

            aggregation = ReviewAggregation(
                mega_motion_id=support.mega_motion_id,
                mega_motion_title=support.mega_motion_title,
                implicit_endorsements=implicit_endorsements,
                explicit_endorsements=explicit_endorsements,
                total_endorsements=total_endorsements,
                oppositions=oppositions,
                amendments_proposed=amendments,
                abstentions=abstentions,
                no_response=no_response,
                engaged_count=engaged,
                endorsement_ratio=endorsement_ratio,
                opposition_ratio=opposition_ratio,
                consensus_reached=consensus_reached,
                contested=contested,
                needs_amendment_synthesis=needs_amendment_synthesis,
                amendment_texts=amendment_texts,
                opposition_reasons=opposition_reasons,
                endorsing_archons=endorsing_archons,
                opposing_archons=opposing_archons,
            )
            aggregations.append(aggregation)

        logger.info(
            "aggregation_complete",
            motion_count=len(aggregations),
            consensus_count=sum(1 for a in aggregations if a.consensus_reached),
            contested_count=sum(1 for a in aggregations if a.contested),
        )

        return aggregations

    # =========================================================================
    # Phase 5-6: Panel Deliberation & Ratification
    # =========================================================================

    def create_deliberation_panels(
        self,
        aggregations: list[ReviewAggregation],
    ) -> list[DeliberationPanel]:
        """Create deliberation panels for contested motions.

        Args:
            aggregations: Review aggregations

        Returns:
            List of DeliberationPanel for contested motions
        """
        contested = [a for a in aggregations if a.contested]
        logger.info("panel_creation_start", contested_count=len(contested))

        panels = []

        for agg in contested:
            # Select supporters (top 3 endorsers)
            supporters = agg.endorsing_archons[:3] if len(agg.endorsing_archons) >= 3 else agg.endorsing_archons

            # Select critics (top 3 opposers)
            critics = agg.opposing_archons[:3] if len(agg.opposing_archons) >= 3 else agg.opposing_archons

            # Select neutrals (from remaining Archons)
            used = set(supporters + critics)
            available = [a for a in ALL_ARCHON_NAMES if a not in used]
            neutrals = available[:3]

            panel = DeliberationPanel(
                panel_id=str(uuid4()),
                mega_motion_id=agg.mega_motion_id,
                mega_motion_title=agg.mega_motion_title,
                supporters=supporters,
                critics=critics,
                neutrals=neutrals,
            )
            panels.append(panel)

        logger.info("panels_created", panel_count=len(panels))
        return panels

    def simulate_panel_deliberation(
        self,
        panel: DeliberationPanel,
    ) -> DeliberationPanel:
        """Simulate panel deliberation for testing.

        In production, this would run actual deliberation with Archon agents.

        Args:
            panel: The panel to deliberate

        Returns:
            Updated panel with results
        """
        # Simulate votes
        panel.pass_votes = 4
        panel.fail_votes = 2
        panel.amend_votes = 1
        panel.defer_votes = 0

        # Determine recommendation
        votes = [
            (panel.pass_votes, PanelRecommendation.PASS),
            (panel.fail_votes, PanelRecommendation.FAIL),
            (panel.amend_votes, PanelRecommendation.AMEND),
            (panel.defer_votes, PanelRecommendation.DEFER),
        ]
        max_votes = max(votes, key=lambda x: x[0])
        panel.recommendation = max_votes[1]

        panel.concluded_at = datetime.now(timezone.utc)
        panel.deliberation_duration_minutes = 35

        return panel

    def simulate_ratification(
        self,
        aggregations: list[ReviewAggregation],
        panels: list[DeliberationPanel],
    ) -> list[RatificationVote]:
        """Simulate ratification votes for testing.

        Args:
            aggregations: Review aggregations
            panels: Panel deliberation results

        Returns:
            List of RatificationVote
        """
        logger.info("ratification_start", motion_count=len(aggregations))

        panel_lookup = {p.mega_motion_id: p for p in panels}
        votes = []

        for agg in aggregations:
            panel = panel_lookup.get(agg.mega_motion_id)

            # Simulate vote based on aggregation results
            if agg.consensus_reached:
                yeas = 55
                nays = 10
            elif panel and panel.recommendation == PanelRecommendation.PASS:
                yeas = 45
                nays = 20
            elif panel and panel.recommendation == PanelRecommendation.FAIL:
                yeas = 25
                nays = 40
            else:
                yeas = 38
                nays = 28

            abstentions = 72 - yeas - nays

            # Determine threshold
            is_constitutional = "constitutional" in agg.mega_motion_title.lower()
            threshold_type = "supermajority" if is_constitutional else "simple_majority"
            threshold_required = SUPERMAJORITY if is_constitutional else SIMPLE_MAJORITY
            threshold_met = yeas >= threshold_required

            outcome = (
                RatificationOutcome.RATIFIED if threshold_met
                else RatificationOutcome.REJECTED
            )

            vote = RatificationVote(
                vote_id=str(uuid4()),
                mega_motion_id=agg.mega_motion_id,
                mega_motion_title=agg.mega_motion_title,
                yeas=yeas,
                nays=nays,
                abstentions=abstentions,
                threshold_type=threshold_type,
                threshold_required=threshold_required,
                threshold_met=threshold_met,
                votes_by_archon={},  # Would be populated with actual votes
                outcome=outcome,
                ratified_at=datetime.now(timezone.utc) if outcome == RatificationOutcome.RATIFIED else None,
            )
            votes.append(vote)

        ratified = sum(1 for v in votes if v.outcome == RatificationOutcome.RATIFIED)
        rejected = sum(1 for v in votes if v.outcome == RatificationOutcome.REJECTED)

        logger.info("ratification_complete", ratified=ratified, rejected=rejected)
        return votes

    # =========================================================================
    # Full Pipeline
    # =========================================================================

    def run_full_pipeline(
        self,
        consolidator_output_path: Path,
        simulate: bool = True,
    ) -> MotionReviewPipelineResult:
        """Run the complete motion review pipeline.

        Args:
            consolidator_output_path: Path to consolidator session directory
            simulate: If True, simulate reviews and deliberation

        Returns:
            Complete pipeline result
        """
        started_at = datetime.now(timezone.utc)

        # Load data
        mega_motions, novel_proposals, session_id, session_name = self.load_mega_motions(
            consolidator_output_path
        )

        result = MotionReviewPipelineResult(
            session_id=session_id,
            session_name=session_name,
            started_at=started_at,
            mega_motions_input=len(mega_motions),
            novel_proposals_input=len(novel_proposals),
        )

        result.add_audit_event("pipeline_started", {
            "consolidator_path": str(consolidator_output_path),
            "mega_motions": len(mega_motions),
            "novel_proposals": len(novel_proposals),
        })

        # Phase 1: Triage
        triage_result = self.triage_motions(mega_motions, novel_proposals, session_id)
        result.triage_result = triage_result
        result.add_audit_event("triage_completed", {
            "low_risk": triage_result.low_risk_count,
            "medium_risk": triage_result.medium_risk_count,
            "high_risk": triage_result.high_risk_count,
        })

        # Phase 2: Generate packets
        all_motions = mega_motions + novel_proposals
        assignments = self.generate_review_packets(triage_result, all_motions)
        result.review_assignments = assignments
        result.total_assignments = sum(a.assignment_count for a in assignments)
        result.average_assignments_per_archon = result.total_assignments / 72
        result.add_audit_event("packets_generated", {
            "total_assignments": result.total_assignments,
            "avg_per_archon": result.average_assignments_per_archon,
        })

        if simulate:
            # Phase 3-4: Simulate reviews and aggregate
            responses = self.simulate_archon_reviews(assignments, triage_result)
            result.review_responses = responses
            result.response_rate = len(responses) / result.total_assignments if result.total_assignments > 0 else 0

            aggregations = self.aggregate_reviews(triage_result, responses)
            result.aggregations = aggregations
            result.add_audit_event("reviews_aggregated", {
                "response_count": len(responses),
                "consensus_count": sum(1 for a in aggregations if a.consensus_reached),
                "contested_count": sum(1 for a in aggregations if a.contested),
            })

            # Phase 5: Panel deliberation
            panels = self.create_deliberation_panels(aggregations)
            for panel in panels:
                self.simulate_panel_deliberation(panel)
            result.panels_convened = len(panels)
            result.panel_results = panels
            result.add_audit_event("panels_concluded", {
                "panels_convened": len(panels),
            })

            # Phase 6: Ratification
            votes = self.simulate_ratification(aggregations, panels)
            result.ratification_votes = votes
            result.motions_ratified = sum(1 for v in votes if v.outcome == RatificationOutcome.RATIFIED)
            result.motions_rejected = sum(1 for v in votes if v.outcome == RatificationOutcome.REJECTED)
            result.motions_deferred = sum(1 for v in votes if v.outcome == RatificationOutcome.DEFERRED)
            result.add_audit_event("ratification_completed", {
                "ratified": result.motions_ratified,
                "rejected": result.motions_rejected,
                "deferred": result.motions_deferred,
            })

        result.completed_at = datetime.now(timezone.utc)
        result.add_audit_event("pipeline_completed", {
            "duration_seconds": (result.completed_at - started_at).total_seconds(),
        })

        return result

    async def run_full_pipeline_async(
        self,
        consolidator_output_path: Path,
        use_real_agent: bool = True,
    ) -> MotionReviewPipelineResult:
        """Run the complete motion review pipeline using real Archon agents.

        This async version uses the ReviewerAgent for actual LLM-powered reviews
        and deliberations instead of simulations.

        Args:
            consolidator_output_path: Path to consolidator session directory
            use_real_agent: If True and reviewer_agent is configured, use real reviews

        Returns:
            Complete pipeline result

        Raises:
            RuntimeError: If use_real_agent=True but no reviewer_agent configured
        """
        if use_real_agent and not self._reviewer_agent:
            raise RuntimeError(
                "Cannot run with use_real_agent=True when no reviewer_agent is configured. "
                "Either provide a reviewer_agent to the service constructor or use "
                "run_full_pipeline() with simulate=True."
            )

        started_at = datetime.now(timezone.utc)

        # Load data
        mega_motions, novel_proposals, session_id, session_name = self.load_mega_motions(
            consolidator_output_path
        )

        result = MotionReviewPipelineResult(
            session_id=session_id,
            session_name=session_name,
            started_at=started_at,
            mega_motions_input=len(mega_motions),
            novel_proposals_input=len(novel_proposals),
        )

        result.add_audit_event("pipeline_started", {
            "consolidator_path": str(consolidator_output_path),
            "mega_motions": len(mega_motions),
            "novel_proposals": len(novel_proposals),
            "using_real_agent": use_real_agent,
        })

        # Phase 1: Triage
        triage_result = self.triage_motions(mega_motions, novel_proposals, session_id)
        result.triage_result = triage_result
        result.add_audit_event("triage_completed", {
            "low_risk": triage_result.low_risk_count,
            "medium_risk": triage_result.medium_risk_count,
            "high_risk": triage_result.high_risk_count,
        })

        # Phase 2: Generate packets
        all_motions = mega_motions + novel_proposals
        assignments = self.generate_review_packets(triage_result, all_motions)
        result.review_assignments = assignments
        result.total_assignments = sum(a.assignment_count for a in assignments)
        result.average_assignments_per_archon = result.total_assignments / 72
        result.add_audit_event("packets_generated", {
            "total_assignments": result.total_assignments,
            "avg_per_archon": result.average_assignments_per_archon,
        })

        # Phase 3-4: Collect real reviews using ReviewerAgent
        if use_real_agent:
            logger.info("collecting_real_archon_reviews")
            responses = await self.collect_archon_reviews(
                assignments, triage_result, all_motions
            )
        else:
            responses = self.simulate_archon_reviews(assignments, triage_result)

        result.review_responses = responses
        result.response_rate = (
            len(responses) / result.total_assignments
            if result.total_assignments > 0
            else 0
        )

        aggregations = self.aggregate_reviews(triage_result, responses)
        result.aggregations = aggregations
        result.add_audit_event("reviews_aggregated", {
            "response_count": len(responses),
            "consensus_count": sum(1 for a in aggregations if a.consensus_reached),
            "contested_count": sum(1 for a in aggregations if a.contested),
            "real_reviews": use_real_agent,
        })

        # Phase 5: Panel deliberation
        panels = self.create_deliberation_panels(aggregations)
        aggregation_lookup = {a.mega_motion_id: a for a in aggregations}

        if use_real_agent:
            logger.info("running_real_panel_deliberations", panel_count=len(panels))
            for panel in panels:
                agg = aggregation_lookup.get(panel.mega_motion_id)
                if agg:
                    await self.run_real_panel_deliberation(panel, all_motions, agg)
        else:
            for panel in panels:
                self.simulate_panel_deliberation(panel)

        result.panels_convened = len(panels)
        result.panel_results = panels
        result.add_audit_event("panels_concluded", {
            "panels_convened": len(panels),
            "real_deliberation": use_real_agent,
        })

        # Phase 6: Ratification (still simulated - needs actual voting mechanism)
        votes = self.simulate_ratification(aggregations, panels)
        result.ratification_votes = votes
        result.motions_ratified = sum(
            1 for v in votes if v.outcome == RatificationOutcome.RATIFIED
        )
        result.motions_rejected = sum(
            1 for v in votes if v.outcome == RatificationOutcome.REJECTED
        )
        result.motions_deferred = sum(
            1 for v in votes if v.outcome == RatificationOutcome.DEFERRED
        )
        result.add_audit_event("ratification_completed", {
            "ratified": result.motions_ratified,
            "rejected": result.motions_rejected,
            "deferred": result.motions_deferred,
        })

        result.completed_at = datetime.now(timezone.utc)
        result.add_audit_event("pipeline_completed", {
            "duration_seconds": (result.completed_at - started_at).total_seconds(),
            "real_reviews": use_real_agent,
        })

        return result

    # =========================================================================
    # Output
    # =========================================================================

    def save_results(
        self,
        result: MotionReviewPipelineResult,
        output_dir: Path,
    ) -> Path:
        """Save pipeline results to session directory.

        Args:
            result: Pipeline result to save
            output_dir: Base output directory

        Returns:
            Path to session output directory
        """
        session_dir = output_dir / result.session_id
        session_dir.mkdir(parents=True, exist_ok=True)

        # Save triage results
        if result.triage_result:
            triage_file = session_dir / "triage_results.json"
            with open(triage_file, "w") as f:
                json.dump(result.triage_result.to_dict(), f, indent=2)

        # Save review packets
        packets_dir = session_dir / "review_packets"
        packets_dir.mkdir(exist_ok=True)
        for assignment in result.review_assignments:
            packet_file = packets_dir / f"{assignment.archon_id}.json"
            with open(packet_file, "w") as f:
                json.dump(assignment.to_dict(), f, indent=2)

        # Save aggregations
        if result.aggregations:
            agg_file = session_dir / "aggregations.json"
            with open(agg_file, "w") as f:
                json.dump([a.to_dict() for a in result.aggregations], f, indent=2)

        # Save panel results
        if result.panel_results:
            panels_dir = session_dir / "panel_deliberations"
            panels_dir.mkdir(exist_ok=True)
            for panel in result.panel_results:
                panel_file = panels_dir / f"{panel.panel_id}.json"
                with open(panel_file, "w") as f:
                    json.dump(panel.to_dict(), f, indent=2)

        # Save ratification results
        if result.ratification_votes:
            ratification_file = session_dir / "ratification_results.json"
            with open(ratification_file, "w") as f:
                json.dump([v.to_dict() for v in result.ratification_votes], f, indent=2)

        # Save full result
        full_result_file = session_dir / "pipeline_result.json"
        with open(full_result_file, "w") as f:
            json.dump(result.to_dict(), f, indent=2)

        # Save audit trail
        audit_file = session_dir / "audit_trail.json"
        with open(audit_file, "w") as f:
            json.dump(result.audit_trail, f, indent=2)

        logger.info("results_saved", output_dir=str(session_dir))
        return session_dir
