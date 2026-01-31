"""Service for selecting the winning Duke proposal from a field of candidates.

Orchestrates the 6-phase selection pipeline where Executive Presidents
score, rank, and deliberate on Duke implementation proposals.

Phase 1: Load proposals and RFP from disk
Phase 2: Score all proposals (11 Presidents x N proposals)
Phase 3: Detect novelty across the field
Phase 4: Aggregate rankings (pure computation, no LLM)
Phase 5: Deliberate on top-N finalists
Phase 6: Determine outcome (winner / revision / escalation)

Output Structure:
    <mandate_dir>/selection/
    ├── selection_result.json
    ├── selection_result.md
    ├── selection_session_summary.json
    ├── scores/
    │   ├── score_matrix.json
    │   ├── scores_by_president/
    │   │   └── scores_<name>.json
    │   └── scores_by_proposal/
    │       └── scores_<name>.json
    ├── novelty/
    │   ├── novelty_flags.json
    │   └── novelty_flags.md
    ├── deliberation/
    │   ├── panel_deliberation.json
    │   └── panel_deliberation.md
    ├── revisions/
    │   └── round_<N>/
    │       └── feedback_<duke>.json
    └── selection_events.jsonl
"""

from __future__ import annotations

import json
import math
import random
import uuid
from collections import defaultdict
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from src.domain.models.duke_proposal import DukeProposal, ProposalStatus
from src.domain.models.proposal_selection import (
    DukeRevisionGuidance,
    ProposalNovelty,
    ProposalRanking,
    ProposalScore,
    ProposalSelectionResult,
    ProposalTier,
    SelectionDeliberation,
    SelectionHandback,
    SelectionOutcome,
    SelectionStatus,
)
from src.domain.models.rfp import RFPDocument

if TYPE_CHECKING:
    from src.application.ports.proposal_selection import (
        ProposalScorerProtocol,
        SelectionContext,
    )


def now_iso() -> str:
    """Return current UTC time as ISO string."""
    return datetime.now(timezone.utc).isoformat()


# ------------------------------------------------------------------
# Score weights and thresholds
# ------------------------------------------------------------------

SCORE_WEIGHTS: dict[str, float] = {
    "feasibility": 0.20,
    "completeness": 0.25,
    "risk_mitigation": 0.15,
    "resource_efficiency": 0.10,
    "innovation": 0.10,
    "alignment": 0.20,
}

NOVELTY_BONUS_MAX = 0.5
NOVELTY_SCORE_THRESHOLD = 0.7
WINNER_MIN_MEAN = 7.0
VIABLE_MIN_MEAN = 5.0


class ProposalSelectionService:
    """Service orchestrating the 6-phase proposal selection pipeline."""

    def __init__(
        self,
        proposal_scorer: ProposalScorerProtocol | None = None,
        event_sink: Callable[[str, dict], None] | None = None,
        verbose: bool = False,
        top_n_finalists: int = 5,
        max_rounds: int = 3,
    ) -> None:
        self._scorer = proposal_scorer
        self._event_sink = event_sink or (lambda t, p: None)
        self._verbose = verbose
        self._top_n_finalists = top_n_finalists
        self._max_rounds = max_rounds

    def _emit(self, event_type: str, payload: dict) -> None:
        self._event_sink(event_type, {"timestamp": now_iso(), **payload})

    # ------------------------------------------------------------------
    # Phase 1: Load proposals and RFP
    # ------------------------------------------------------------------

    @staticmethod
    def load_proposals(proposals_inbox_dir: Path) -> list[DukeProposal]:
        """Load Duke proposals from the proposals_inbox directory.

        Reads each proposal_<name>.json sidecar and pairs it with
        the corresponding .md file for the full proposal body.

        Args:
            proposals_inbox_dir: Path to proposals_inbox/ directory

        Returns:
            List of DukeProposal objects
        """
        proposals: list[DukeProposal] = []

        for json_path in sorted(proposals_inbox_dir.glob("proposal_*.json")):
            if json_path.name in ("proposal_summary.json",):
                continue
            with open(json_path, encoding="utf-8") as f:
                data = json.load(f)
            proposal = DukeProposal.from_dict(data)

            # Load markdown body if not already present
            if not proposal.proposal_markdown:
                md_path = json_path.with_suffix(".md")
                if md_path.exists():
                    with open(md_path, encoding="utf-8") as f:
                        proposal.proposal_markdown = f.read()

            proposals.append(proposal)

        return proposals

    @staticmethod
    def load_rfp(rfp_path: Path) -> RFPDocument:
        """Load and deserialize an RFP document from disk."""
        with open(rfp_path, encoding="utf-8") as f:
            data = json.load(f)
        return RFPDocument.from_dict(data)

    # ------------------------------------------------------------------
    # Phase 2: Score all proposals
    # ------------------------------------------------------------------

    async def score_all_proposals(
        self,
        proposals: list[DukeProposal],
        presidents: list[dict[str, Any]],
        context: SelectionContext,
    ) -> list[ProposalScore]:
        """Have all Presidents score all proposals.

        Sequential per-President to avoid connection storms on rate-limited
        endpoints.

        Args:
            proposals: Duke proposals to score
            presidents: List of president dicts from archons-base.json
            context: Selection pipeline context

        Returns:
            Flat list of all ProposalScore objects (|presidents| x |proposals|)
        """
        if self._scorer is None:
            raise RuntimeError("No proposal scorer configured")

        self._emit(
            "selection.scoring_started",
            {
                "president_count": len(presidents),
                "proposal_count": len(proposals),
                "total_scores": len(presidents) * len(proposals),
            },
        )

        all_scores: list[ProposalScore] = []

        for i, president in enumerate(presidents):
            pres_name = president.get("name", "Unknown")
            pres_role = president.get("role", "")
            pres_backstory = president.get("backstory", "")

            if self._verbose:
                print(
                    f"  [{i + 1}/{len(presidents)}] "
                    f"President {pres_name} scoring {len(proposals)} proposals..."
                )

            scores = await self._scorer.batch_score_proposals(
                president_name=pres_name,
                president_role=pres_role,
                president_backstory=pres_backstory,
                proposals=proposals,
                context=context,
            )

            for score in scores:
                self._emit(
                    "selection.score_recorded",
                    {
                        "president_name": score.president_name,
                        "proposal_id": score.proposal_id,
                        "overall_score": score.overall_score,
                    },
                )

            all_scores.extend(scores)

        self._emit(
            "selection.scoring_complete",
            {"total_scores": len(all_scores)},
        )

        return all_scores

    # ------------------------------------------------------------------
    # Phase 3: Novelty detection
    # ------------------------------------------------------------------

    async def detect_novelty(
        self,
        proposals: list[DukeProposal],
        context: SelectionContext,
    ) -> list[ProposalNovelty]:
        """Detect novelty across the field of proposals.

        Args:
            proposals: All Duke proposals
            context: Selection pipeline context

        Returns:
            List of ProposalNovelty (one per proposal)
        """
        if self._scorer is None:
            raise RuntimeError("No proposal scorer configured")

        novelty = await self._scorer.detect_novelty(proposals, context)

        self._emit(
            "selection.novelty_complete",
            {
                "total_proposals": len(proposals),
                "novel_count": sum(
                    1 for n in novelty if n.novelty_score >= NOVELTY_SCORE_THRESHOLD
                ),
            },
        )

        return novelty

    # ------------------------------------------------------------------
    # Phase 4: Aggregate rankings (pure computation)
    # ------------------------------------------------------------------

    def aggregate_rankings(
        self,
        scores: list[ProposalScore],
        novelty: list[ProposalNovelty],
        proposals: list[DukeProposal],
    ) -> list[ProposalRanking]:
        """Compute aggregated rankings from individual scores.

        Uses weighted dimension means, z-score normalization per-President,
        and novelty bonus.

        Args:
            scores: All individual ProposalScore objects
            novelty: Novelty assessments for each proposal
            proposals: The original proposals (for ID reference)

        Returns:
            List of ProposalRanking sorted by rank (1 = best)
        """
        # Group scores by proposal
        scores_by_proposal: dict[str, list[ProposalScore]] = defaultdict(list)
        for score in scores:
            scores_by_proposal[score.proposal_id].append(score)

        # Z-score normalization per President
        scores_by_president: dict[str, list[ProposalScore]] = defaultdict(list)
        for score in scores:
            scores_by_president[score.president_name].append(score)

        president_stats: dict[str, tuple[float, float]] = {}
        for pres_name, pres_scores in scores_by_president.items():
            values = [s.overall_score for s in pres_scores]
            mean = sum(values) / len(values) if values else 0.0
            variance = (
                sum((v - mean) ** 2 for v in values) / len(values)
                if len(values) > 1
                else 0.0
            )
            stddev = math.sqrt(variance) if variance > 0 else 1.0
            president_stats[pres_name] = (mean, stddev)

        # Build novelty lookup
        novelty_lookup: dict[str, ProposalNovelty] = {n.proposal_id: n for n in novelty}

        # Compute rankings
        rankings: list[ProposalRanking] = []
        proposal_ids = {p.proposal_id for p in proposals}

        for proposal_id in proposal_ids:
            prop_scores = scores_by_proposal.get(proposal_id, [])
            if not prop_scores:
                continue

            # Normalize scores per-President
            normalized_overall: list[float] = []
            for s in prop_scores:
                mean, stddev = president_stats.get(s.president_name, (0.0, 1.0))
                z = (s.overall_score - mean) / stddev if stddev > 0 else 0.0
                # Map z-score back to 0-10 scale (mean=5, stddev=2)
                normalized = max(0.0, min(10.0, 5.0 + z * 2.0))
                normalized_overall.append(normalized)

            raw_overall = [s.overall_score for s in prop_scores]

            mean_score = sum(raw_overall) / len(raw_overall)
            sorted_scores = sorted(raw_overall)
            n = len(sorted_scores)
            median_score = (
                sorted_scores[n // 2]
                if n % 2 == 1
                else (sorted_scores[n // 2 - 1] + sorted_scores[n // 2]) / 2.0
            )
            min_score = min(raw_overall)
            max_score = max(raw_overall)
            variance = (
                sum((v - mean_score) ** 2 for v in raw_overall) / len(raw_overall)
                if len(raw_overall) > 1
                else 0.0
            )
            stddev_score = math.sqrt(variance)

            # Per-dimension means
            dim_names = [
                "feasibility",
                "completeness",
                "risk_mitigation",
                "resource_efficiency",
                "innovation",
                "alignment",
            ]
            dim_means: dict[str, float] = {}
            for dim in dim_names:
                vals = [getattr(s, dim) for s in prop_scores]
                dim_means[dim] = sum(vals) / len(vals) if vals else 0.0

            # Novelty bonus
            nov = novelty_lookup.get(proposal_id)
            novelty_bonus = 0.0
            if nov and nov.novelty_score >= NOVELTY_SCORE_THRESHOLD:
                novelty_bonus = min(
                    NOVELTY_BONUS_MAX,
                    nov.novelty_score * NOVELTY_BONUS_MAX,
                )

            # Supporters (score >= 7) and critics (score < 5)
            supporters = [
                s.president_name for s in prop_scores if s.overall_score >= 7.0
            ]
            critics = [s.president_name for s in prop_scores if s.overall_score < 5.0]

            # Tier assignment
            adjusted_mean = mean_score + novelty_bonus
            if adjusted_mean >= WINNER_MIN_MEAN:
                tier = ProposalTier.FINALIST
            elif adjusted_mean >= VIABLE_MIN_MEAN:
                tier = ProposalTier.CONTENDER
            else:
                tier = ProposalTier.BELOW_THRESHOLD

            rankings.append(
                ProposalRanking(
                    proposal_id=proposal_id,
                    mean_score=mean_score,
                    median_score=median_score,
                    min_score=min_score,
                    max_score=max_score,
                    stddev_score=stddev_score,
                    mean_feasibility=dim_means["feasibility"],
                    mean_completeness=dim_means["completeness"],
                    mean_risk_mitigation=dim_means["risk_mitigation"],
                    mean_resource_efficiency=dim_means["resource_efficiency"],
                    mean_innovation=dim_means["innovation"],
                    mean_alignment=dim_means["alignment"],
                    novelty_bonus=novelty_bonus,
                    tier=tier,
                    supporters=supporters,
                    critics=critics,
                )
            )

        # Sort by adjusted mean (mean_score + novelty_bonus) descending
        rankings.sort(key=lambda r: r.mean_score + r.novelty_bonus, reverse=True)

        # Assign ranks
        for i, ranking in enumerate(rankings):
            ranking.rank = i + 1

        self._emit(
            "selection.aggregation_complete",
            {
                "total_rankings": len(rankings),
                "finalists": sum(
                    1 for r in rankings if r.tier == ProposalTier.FINALIST
                ),
                "contenders": sum(
                    1 for r in rankings if r.tier == ProposalTier.CONTENDER
                ),
            },
        )

        return rankings

    # ------------------------------------------------------------------
    # Phase 5: Deliberation
    # ------------------------------------------------------------------

    async def deliberate(
        self,
        rankings: list[ProposalRanking],
        proposals: list[DukeProposal],
        presidents: list[dict[str, Any]],
        context: SelectionContext,
    ) -> SelectionDeliberation:
        """Run panel deliberation on top-N finalists.

        Args:
            rankings: Sorted rankings from aggregation
            proposals: All Duke proposals
            presidents: List of president dicts
            context: Selection pipeline context

        Returns:
            SelectionDeliberation with recommendation and votes
        """
        if self._scorer is None:
            raise RuntimeError("No proposal scorer configured")

        # Select top-N finalists
        top_n = min(self._top_n_finalists, len(rankings))
        finalist_rankings = rankings[:top_n]
        finalist_ids = {r.proposal_id for r in finalist_rankings}
        finalist_proposals = [p for p in proposals if p.proposal_id in finalist_ids]

        # Build rankings summary for context
        summary_lines: list[str] = []
        for r in finalist_rankings:
            summary_lines.append(
                f"#{r.rank}: {r.proposal_id} "
                f"(mean={r.mean_score:.1f}, tier={r.tier.value}, "
                f"novelty_bonus={r.novelty_bonus:.2f})"
            )
        rankings_summary = "\n".join(summary_lines)

        panelist_names = [p.get("name", "") for p in presidents]
        panelist_roles = [p.get("role", "") for p in presidents]
        panelist_backstories = [p.get("backstory", "") for p in presidents]

        deliberation = await self._scorer.run_deliberation(
            panelist_names=panelist_names,
            panelist_roles=panelist_roles,
            panelist_backstories=panelist_backstories,
            finalist_proposals=finalist_proposals,
            rankings_summary=rankings_summary,
            context=context,
        )

        self._emit(
            "selection.deliberation_complete",
            {
                "finalist_count": len(finalist_proposals),
                "recommended_winner": deliberation.recommended_winner_id,
            },
        )

        return deliberation

    # ------------------------------------------------------------------
    # Phase 6: Determine outcome
    # ------------------------------------------------------------------

    def determine_outcome(
        self,
        rankings: list[ProposalRanking],
        deliberation: SelectionDeliberation | None,
        iteration: int,
        max_iterations: int,
    ) -> tuple[SelectionOutcome, str]:
        """Decide the selection outcome.

        Decision logic:
        - Panel recommends winner AND mean_overall >= 7.0 -> WINNER_SELECTED
        - mean_overall < 5.0 for all -> NO_VIABLE_PROPOSAL
        - Unresolved concerns AND round < max_rounds -> REVISION_NEEDED
        - round >= max_rounds and no winner -> ESCALATE_TO_CONCLAVE

        Args:
            rankings: Sorted proposal rankings
            deliberation: Panel deliberation result (None if score-only)
            iteration: Current iteration number
            max_iterations: Maximum allowed iterations

        Returns:
            Tuple of (outcome, winning_proposal_id or empty string)
        """
        if not rankings:
            return SelectionOutcome.NO_VIABLE_PROPOSAL, ""

        top = rankings[0]

        # Check if all proposals are below viable threshold
        all_below_viable = all(
            r.mean_score + r.novelty_bonus < VIABLE_MIN_MEAN for r in rankings
        )
        if all_below_viable:
            self._emit(
                "selection.outcome",
                {"outcome": "NO_VIABLE_PROPOSAL", "reason": "all_below_threshold"},
            )
            return SelectionOutcome.NO_VIABLE_PROPOSAL, ""

        # If deliberation occurred, check recommendation
        if deliberation and deliberation.recommended_winner_id:
            # Find the recommended winner's ranking
            winner_ranking = next(
                (
                    r
                    for r in rankings
                    if r.proposal_id == deliberation.recommended_winner_id
                ),
                None,
            )
            if winner_ranking and (
                winner_ranking.mean_score + winner_ranking.novelty_bonus
                >= WINNER_MIN_MEAN
            ):
                self._emit(
                    "selection.outcome",
                    {
                        "outcome": "WINNER_SELECTED",
                        "winner": deliberation.recommended_winner_id,
                    },
                )
                return (
                    SelectionOutcome.WINNER_SELECTED,
                    deliberation.recommended_winner_id,
                )

        # Check if top proposal clears threshold even without deliberation
        if top.mean_score + top.novelty_bonus >= WINNER_MIN_MEAN:
            if deliberation is None:
                # Score-only mode, no deliberation
                self._emit(
                    "selection.outcome",
                    {
                        "outcome": "WINNER_SELECTED",
                        "winner": top.proposal_id,
                        "mode": "score_only",
                    },
                )
                return SelectionOutcome.WINNER_SELECTED, top.proposal_id

        # Revision or escalation
        if iteration >= max_iterations:
            self._emit(
                "selection.outcome",
                {
                    "outcome": "ESCALATE_TO_CONCLAVE",
                    "reason": "max_iterations_reached",
                },
            )
            return SelectionOutcome.ESCALATE_TO_CONCLAVE, ""

        self._emit(
            "selection.outcome",
            {
                "outcome": "REVISION_NEEDED",
                "iteration": iteration,
            },
        )
        return SelectionOutcome.REVISION_NEEDED, ""

    # ------------------------------------------------------------------
    # Build revision guidance
    # ------------------------------------------------------------------

    def build_revision_guidance(
        self,
        rankings: list[ProposalRanking],
        scores: list[ProposalScore],
        proposals: list[DukeProposal],
    ) -> list[DukeRevisionGuidance]:
        """Build revision guidance for proposals that need improvement.

        Generates feedback for CONTENDER and BELOW_THRESHOLD proposals.

        Args:
            rankings: Proposal rankings
            scores: All individual scores
            proposals: All proposals

        Returns:
            List of DukeRevisionGuidance for non-finalist proposals
        """
        proposal_lookup = {p.proposal_id: p for p in proposals}
        scores_by_proposal: dict[str, list[ProposalScore]] = defaultdict(list)
        for s in scores:
            scores_by_proposal[s.proposal_id].append(s)

        guidance_list: list[DukeRevisionGuidance] = []

        for ranking in rankings:
            if ranking.tier == ProposalTier.FINALIST:
                continue

            proposal = proposal_lookup.get(ranking.proposal_id)
            if not proposal:
                continue

            prop_scores = scores_by_proposal.get(ranking.proposal_id, [])

            # Collect all weaknesses from critics
            all_weaknesses: list[str] = []
            for s in prop_scores:
                all_weaknesses.extend(s.weaknesses)

            # Identify weak dimensions
            dim_names = [
                "feasibility",
                "completeness",
                "risk_mitigation",
                "resource_efficiency",
                "innovation",
                "alignment",
            ]
            improvement_areas: list[str] = []
            for dim in dim_names:
                mean_dim = getattr(ranking, f"mean_{dim}", 0.0)
                if mean_dim < 5.0:
                    improvement_areas.append(f"{dim}: mean score {mean_dim:.1f}/10")

            guidance = DukeRevisionGuidance(
                proposal_id=ranking.proposal_id,
                duke_name=proposal.duke_name,
                critical_weaknesses=list(set(all_weaknesses))[:10],
                improvement_areas=improvement_areas,
                required_changes=[f"Improve {dim}" for dim in improvement_areas[:5]],
                revision_constraints=[
                    "Must not change proposal scope",
                    "Must address all critical weaknesses",
                ],
            )
            guidance_list.append(guidance)

        return guidance_list

    # ------------------------------------------------------------------
    # Full pipeline
    # ------------------------------------------------------------------

    async def run_selection_pipeline(
        self,
        proposals: list[DukeProposal],
        rfp: RFPDocument,
        presidents: list[dict[str, Any]],
        context: SelectionContext,
        score_only: bool = False,
    ) -> ProposalSelectionResult:
        """Run the full 6-phase selection pipeline.

        Args:
            proposals: Duke proposals to evaluate
            rfp: The source RFP document
            presidents: List of president dicts
            context: Selection pipeline context
            score_only: If True, stop after scoring (skip deliberation)

        Returns:
            ProposalSelectionResult with all artifacts
        """
        selection_id = f"sel-{uuid.uuid4().hex[:12]}"

        self._emit(
            "selection.started",
            {
                "selection_id": selection_id,
                "rfp_id": rfp.implementation_dossier_id,
                "proposal_count": len(proposals),
                "president_count": len(presidents),
            },
        )

        # Filter to only GENERATED or SIMULATION proposals
        viable = [
            p
            for p in proposals
            if p.status in (ProposalStatus.GENERATED, ProposalStatus.SIMULATION)
        ]

        self._emit(
            "selection.proposals_loaded",
            {
                "total": len(proposals),
                "viable": len(viable),
            },
        )

        result = ProposalSelectionResult(
            selection_id=selection_id,
            rfp_id=rfp.implementation_dossier_id,
            mandate_id=rfp.mandate_id,
            created_at=now_iso(),
            iteration_number=context.iteration_number,
            max_iterations=context.max_iterations,
        )

        # Phase 2: Score
        result.status = SelectionStatus.SCORING
        scores = await self.score_all_proposals(viable, presidents, context)
        result.president_scores = scores

        # Phase 3: Novelty
        result.status = SelectionStatus.NOVELTY_ANALYSIS
        novelty = await self.detect_novelty(viable, context)
        result.novelty_assessments = novelty

        # Phase 4: Aggregate
        result.status = SelectionStatus.AGGREGATION
        rankings = self.aggregate_rankings(scores, novelty, viable)
        result.rankings = rankings

        # Phase 5: Deliberation (optional)
        deliberation: SelectionDeliberation | None = None
        if not score_only:
            result.status = SelectionStatus.DELIBERATION
            deliberation = await self.deliberate(rankings, viable, presidents, context)
            result.deliberation = deliberation

        # Phase 6: Outcome
        outcome, winner_id = self.determine_outcome(
            rankings,
            deliberation,
            context.iteration_number,
            context.max_iterations,
        )
        result.outcome = outcome
        result.winning_proposal_id = winner_id

        if outcome == SelectionOutcome.REVISION_NEEDED:
            result.status = SelectionStatus.REVISION_REQUESTED
            result.revision_guidance = self.build_revision_guidance(
                rankings, scores, viable
            )
        elif outcome == SelectionOutcome.ESCALATE_TO_CONCLAVE:
            result.status = SelectionStatus.ESCALATED
        else:
            result.status = SelectionStatus.DECIDED

        self._emit(
            "selection.complete",
            {
                "selection_id": selection_id,
                "outcome": outcome.value,
                "winner": winner_id,
            },
        )

        return result

    # ------------------------------------------------------------------
    # Simulation mode
    # ------------------------------------------------------------------

    def simulate_selection(
        self,
        proposals: list[DukeProposal],
        rfp: RFPDocument,
        presidents: list[dict[str, Any]],
        context: SelectionContext,
        score_only: bool = False,
    ) -> ProposalSelectionResult:
        """Produce deterministic selection results without LLM.

        Derives scores from proposal metadata (tactic_count, coverage,
        risk_count, etc.) to produce a plausible ranking.

        Args:
            proposals: Duke proposals to evaluate
            rfp: The source RFP document
            presidents: List of president dicts
            context: Selection pipeline context
            score_only: If True, skip deliberation simulation

        Returns:
            ProposalSelectionResult with simulated scores
        """
        selection_id = f"sel-sim-{uuid.uuid4().hex[:12]}"

        self._emit(
            "selection.started",
            {
                "selection_id": selection_id,
                "mode": "simulation",
                "proposal_count": len(proposals),
            },
        )

        viable = [
            p
            for p in proposals
            if p.status in (ProposalStatus.GENERATED, ProposalStatus.SIMULATION)
        ]

        # Generate deterministic scores from metadata
        rng = random.Random(42)
        all_scores: list[ProposalScore] = []
        all_novelty: list[ProposalNovelty] = []

        for proposal in viable:
            # Base quality derived from metadata counts
            base_quality = min(
                9.0,
                5.0
                + proposal.tactic_count * 0.3
                + proposal.risk_count * 0.2
                + proposal.requirement_coverage_count * 0.1,
            )

            for president in presidents:
                pres_name = president.get("name", "Unknown")
                # Add per-president variation
                variation = rng.uniform(-1.0, 1.0)

                feas = max(1.0, min(10.0, base_quality + rng.uniform(-0.5, 0.5)))
                comp = max(1.0, min(10.0, base_quality + rng.uniform(-0.5, 0.5)))
                risk = max(1.0, min(10.0, base_quality - 0.5 + rng.uniform(-0.5, 0.5)))
                reso = max(1.0, min(10.0, base_quality - 0.3 + rng.uniform(-0.5, 0.5)))
                inno = max(1.0, min(10.0, base_quality - 0.2 + rng.uniform(-1.0, 1.0)))
                alig = max(1.0, min(10.0, base_quality + 0.2 + rng.uniform(-0.5, 0.5)))

                overall = (
                    feas * SCORE_WEIGHTS["feasibility"]
                    + comp * SCORE_WEIGHTS["completeness"]
                    + risk * SCORE_WEIGHTS["risk_mitigation"]
                    + reso * SCORE_WEIGHTS["resource_efficiency"]
                    + inno * SCORE_WEIGHTS["innovation"]
                    + alig * SCORE_WEIGHTS["alignment"]
                ) + variation

                overall = max(1.0, min(10.0, overall))

                score = ProposalScore(
                    president_name=pres_name,
                    proposal_id=proposal.proposal_id,
                    feasibility=round(feas, 1),
                    completeness=round(comp, 1),
                    risk_mitigation=round(risk, 1),
                    resource_efficiency=round(reso, 1),
                    innovation=round(inno, 1),
                    alignment=round(alig, 1),
                    overall_score=round(overall, 1),
                    confidence=round(rng.uniform(0.6, 0.9), 2),
                    reasoning=f"Simulation score for {proposal.duke_name} by {pres_name}",
                    strengths=[f"{proposal.duke_name} domain expertise"],
                    weaknesses=[],
                )
                all_scores.append(score)

            # Novelty based on innovation potential
            novelty_val = min(1.0, rng.uniform(0.2, 0.8))
            all_novelty.append(
                ProposalNovelty(
                    proposal_id=proposal.proposal_id,
                    novelty_score=round(novelty_val, 2),
                    category="creative" if novelty_val > 0.6 else "",
                    novelty_reason=f"Simulation novelty for {proposal.duke_name}",
                    novel_elements=[],
                )
            )

        # Aggregate rankings
        rankings = self.aggregate_rankings(all_scores, all_novelty, viable)

        # Simulate deliberation
        deliberation: SelectionDeliberation | None = None
        if not score_only and rankings:
            top = rankings[0]
            finalist_ids = [r.proposal_id for r in rankings[: self._top_n_finalists]]
            votes = {p.get("name", ""): top.proposal_id for p in presidents}
            deliberation = SelectionDeliberation(
                finalist_proposal_ids=finalist_ids,
                recommended_winner_id=top.proposal_id,
                recommendation_rationale=(
                    f"Simulation: {top.proposal_id} ranked #1 with "
                    f"mean score {top.mean_score:.1f}"
                ),
                votes=votes,
            )

        # Determine outcome
        outcome, winner_id = self.determine_outcome(
            rankings,
            deliberation,
            context.iteration_number,
            context.max_iterations,
        )

        result = ProposalSelectionResult(
            selection_id=selection_id,
            status=SelectionStatus.DECIDED,
            outcome=outcome,
            winning_proposal_id=winner_id,
            rankings=rankings,
            president_scores=all_scores,
            novelty_assessments=all_novelty,
            deliberation=deliberation,
            iteration_number=context.iteration_number,
            max_iterations=context.max_iterations,
            rfp_id=rfp.implementation_dossier_id,
            mandate_id=rfp.mandate_id,
            created_at=now_iso(),
        )

        self._emit(
            "selection.complete",
            {
                "selection_id": selection_id,
                "mode": "simulation",
                "outcome": outcome.value,
                "winner": winner_id,
            },
        )

        return result

    # ------------------------------------------------------------------
    # Save results
    # ------------------------------------------------------------------

    def save_results(
        self,
        result: ProposalSelectionResult,
        proposals: list[DukeProposal],
        output_dir: Path,
    ) -> Path:
        """Save full selection results to disk.

        Args:
            result: The selection result to save
            proposals: All proposals (for cross-reference)
            output_dir: Base mandate directory

        Returns:
            Path to the selection/ directory
        """
        sel_dir = output_dir / "selection"
        sel_dir.mkdir(parents=True, exist_ok=True)

        # Main result JSON
        self._save_json(sel_dir / "selection_result.json", result.to_dict())

        # Main result Markdown
        md_content = self._render_result_markdown(result, proposals)
        with open(sel_dir / "selection_result.md", "w", encoding="utf-8") as f:
            f.write(md_content)

        # Session summary
        summary = self._build_session_summary(result, proposals)
        self._save_json(sel_dir / "selection_session_summary.json", summary)

        # Scores
        self._save_scores(result, sel_dir)

        # Novelty
        self._save_novelty(result, sel_dir)

        # Deliberation
        if result.deliberation:
            self._save_deliberation(result, sel_dir, proposals)

        # Revision guidance
        if result.revision_guidance:
            self._save_revisions(result, sel_dir)

        return sel_dir

    def _save_json(self, path: Path, obj: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(obj, f, indent=2)

    def _save_scores(self, result: ProposalSelectionResult, sel_dir: Path) -> None:
        scores_dir = sel_dir / "scores"
        scores_dir.mkdir(parents=True, exist_ok=True)

        # Full score matrix
        matrix: dict[str, Any] = {
            "artifact_type": "score_matrix",
            "total_scores": len(result.president_scores),
            "scores": [s.to_dict() for s in result.president_scores],
        }
        self._save_json(scores_dir / "score_matrix.json", matrix)

        # Scores by president
        by_pres_dir = scores_dir / "scores_by_president"
        by_pres_dir.mkdir(parents=True, exist_ok=True)
        pres_groups: dict[str, list[dict]] = defaultdict(list)
        for s in result.president_scores:
            pres_groups[s.president_name].append(s.to_dict())
        for pres_name, pres_scores in pres_groups.items():
            fname = f"scores_{pres_name.lower()}.json"
            self._save_json(by_pres_dir / fname, pres_scores)

        # Scores by proposal
        by_prop_dir = scores_dir / "scores_by_proposal"
        by_prop_dir.mkdir(parents=True, exist_ok=True)
        prop_groups: dict[str, list[dict]] = defaultdict(list)
        for s in result.president_scores:
            # Extract duke name from proposal_id (dprop-<abbrev>-...)
            prop_groups[s.proposal_id].append(s.to_dict())
        for prop_id, prop_scores in prop_groups.items():
            # Use a sanitized filename from proposal_id
            safe_name = prop_id.replace("/", "_").replace(" ", "_")
            fname = f"scores_{safe_name}.json"
            self._save_json(by_prop_dir / fname, prop_scores)

    def _save_novelty(self, result: ProposalSelectionResult, sel_dir: Path) -> None:
        novelty_dir = sel_dir / "novelty"
        novelty_dir.mkdir(parents=True, exist_ok=True)

        novelty_data = {
            "artifact_type": "novelty_flags",
            "assessments": [n.to_dict() for n in result.novelty_assessments],
        }
        self._save_json(novelty_dir / "novelty_flags.json", novelty_data)

        # Markdown summary
        lines: list[str] = ["# Novelty Flags\n"]
        for n in result.novelty_assessments:
            flag = "*" if n.novelty_score >= NOVELTY_SCORE_THRESHOLD else " "
            lines.append(
                f"- [{flag}] **{n.proposal_id}**: "
                f"score={n.novelty_score:.2f}, category={n.category or 'none'}"
            )
            if n.novelty_reason:
                lines.append(f"  - {n.novelty_reason}")
        with open(novelty_dir / "novelty_flags.md", "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

    def _save_deliberation(
        self,
        result: ProposalSelectionResult,
        sel_dir: Path,
        proposals: list[DukeProposal],
    ) -> None:
        delib_dir = sel_dir / "deliberation"
        delib_dir.mkdir(parents=True, exist_ok=True)

        if result.deliberation:
            self._save_json(
                delib_dir / "panel_deliberation.json",
                result.deliberation.to_dict(),
            )

            # Markdown
            d = result.deliberation
            lines: list[str] = [
                "# Panel Deliberation\n",
                f"**Recommended Winner:** {d.recommended_winner_id}\n",
                f"**Rationale:** {d.recommendation_rationale}\n",
            ]
            if d.arguments_for:
                lines.append("## Arguments For")
                for pid, args in d.arguments_for.items():
                    lines.append(f"\n### {pid}")
                    for arg in args:
                        lines.append(f"- {arg}")
            if d.arguments_against:
                lines.append("\n## Arguments Against")
                for pid, args in d.arguments_against.items():
                    lines.append(f"\n### {pid}")
                    for arg in args:
                        lines.append(f"- {arg}")
            if d.dissenting_opinions:
                lines.append("\n## Dissenting Opinions")
                for opinion in d.dissenting_opinions:
                    lines.append(f"- {opinion}")
            if d.votes:
                lines.append("\n## Votes")
                for voter, vote in d.votes.items():
                    lines.append(f"- **{voter}**: {vote}")

            with open(delib_dir / "panel_deliberation.md", "w", encoding="utf-8") as f:
                f.write("\n".join(lines))

    def _save_revisions(self, result: ProposalSelectionResult, sel_dir: Path) -> None:
        rev_dir = sel_dir / "revisions" / f"round_{result.iteration_number}"
        rev_dir.mkdir(parents=True, exist_ok=True)

        for guidance in result.revision_guidance:
            fname = f"feedback_{guidance.duke_name.lower()}.json"
            self._save_json(rev_dir / fname, guidance.to_dict())

        # Save handback
        handback = SelectionHandback(
            revision_guidance=result.revision_guidance,
            global_constraints=[
                "Must not change proposal scope",
                "Must address all critical weaknesses",
            ],
            focus_areas=[
                g.improvement_areas[0]
                for g in result.revision_guidance
                if g.improvement_areas
            ],
            winning_score_threshold=WINNER_MIN_MEAN,
        )
        self._save_json(rev_dir / "handback.json", handback.to_dict())

    def _build_session_summary(
        self,
        result: ProposalSelectionResult,
        proposals: list[DukeProposal],
    ) -> dict[str, Any]:
        return {
            "artifact_type": "selection_session_summary",
            "selection_id": result.selection_id,
            "rfp_id": result.rfp_id,
            "mandate_id": result.mandate_id,
            "status": result.status.value,
            "outcome": result.outcome.value if result.outcome else None,
            "winning_proposal_id": result.winning_proposal_id,
            "iteration_number": result.iteration_number,
            "max_iterations": result.max_iterations,
            "total_proposals_evaluated": len(proposals),
            "total_scores": len(result.president_scores),
            "total_rankings": len(result.rankings),
            "top_5": [
                {
                    "rank": r.rank,
                    "proposal_id": r.proposal_id,
                    "mean_score": r.mean_score,
                    "tier": r.tier.value,
                    "novelty_bonus": r.novelty_bonus,
                }
                for r in result.rankings[:5]
            ],
            "created_at": result.created_at,
        }

    def _render_result_markdown(
        self,
        result: ProposalSelectionResult,
        proposals: list[DukeProposal],
    ) -> str:
        proposal_lookup = {p.proposal_id: p for p in proposals}
        lines: list[str] = [
            "# Proposal Selection Result\n",
            f"**Selection ID:** {result.selection_id}",
            f"**RFP ID:** {result.rfp_id}",
            f"**Mandate ID:** {result.mandate_id}",
            f"**Status:** {result.status.value}",
            f"**Outcome:** {result.outcome.value if result.outcome else 'N/A'}",
            f"**Winning Proposal:** {result.winning_proposal_id or 'None'}",
            f"**Iteration:** {result.iteration_number}/{result.max_iterations}",
            f"**Created:** {result.created_at}\n",
            "## Rankings\n",
            "| Rank | Duke | Proposal ID | Mean | Tier | Novelty Bonus |",
            "|------|------|-------------|------|------|---------------|",
        ]

        for r in result.rankings:
            prop = proposal_lookup.get(r.proposal_id)
            duke_name = prop.duke_name if prop else "Unknown"
            lines.append(
                f"| {r.rank} | {duke_name} | {r.proposal_id} | "
                f"{r.mean_score:.1f} | {r.tier.value} | "
                f"{r.novelty_bonus:.2f} |"
            )

        if result.deliberation:
            lines.append("\n## Deliberation")
            lines.append(
                f"**Recommended Winner:** {result.deliberation.recommended_winner_id}"
            )
            lines.append(
                f"**Rationale:** {result.deliberation.recommendation_rationale}"
            )

        if result.revision_guidance:
            lines.append("\n## Revision Guidance")
            for g in result.revision_guidance:
                lines.append(f"\n### {g.duke_name} ({g.proposal_id})")
                if g.critical_weaknesses:
                    lines.append("**Critical Weaknesses:**")
                    for w in g.critical_weaknesses:
                        lines.append(f"- {w}")
                if g.improvement_areas:
                    lines.append("**Improvement Areas:**")
                    for a in g.improvement_areas:
                        lines.append(f"- {a}")

        lines.append("")
        return "\n".join(lines)
