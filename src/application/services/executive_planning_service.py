"""Executive planning service (Executive mini-conclave pipeline).

This stage creates a branch-correct fork after ratification:
- Intake ratified intent packets (WHAT)
- Assign plan ownership + affected portfolios
- Collect explicit contributions/attestations
- Integrate execution plans with completeness/integrity/visibility gates
"""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from structlog import get_logger

from src.application.ports.execution_planner import MotionForPlanning
from src.application.services.execution_planner_service import ExecutionPlannerService
from src.domain.models.executive_planning import (
    Blocker,
    ExecutiveCycleResult,
    ExecutiveGates,
    GateStatus,
    NoActionAttestation,
    PortfolioContribution,
    PortfolioIdentity,
    RatifiedIntentPacket,
)

logger = get_logger(__name__)

ISO = "%Y-%m-%dT%H:%M:%SZ"
DEFAULT_ARCHONS_PATH = Path("docs/archons-base.json")


def now_iso() -> str:
    """UTC timestamp in a stable, sortable format."""
    return datetime.now(timezone.utc).strftime(ISO)


def _sha256_file(path: Path) -> str:
    """Compute a file's SHA-256 checksum."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_json(path: Path) -> Any:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@dataclass(frozen=True)
class PortfolioDirectory:
    """Executive portfolio roster + scopes loaded from docs JSON."""

    portfolios: list[PortfolioIdentity]
    scopes_by_portfolio: dict[str, list[str]]
    labels_by_portfolio: dict[str, str]
    names_by_portfolio: dict[str, str]


class ExecutivePlanningService:
    """Implements E0/E1/E2/E3 with explicit governance gates."""

    def __init__(
        self,
        event_sink: Callable[[str, dict[str, Any]], None] | None = None,
        archons_path: Path = DEFAULT_ARCHONS_PATH,
        planner_agent: Any | None = None,
        verbose: bool = False,
    ) -> None:
        self._event_sink = event_sink
        self._archons_path = archons_path
        self._verbose = verbose
        self._planner_agent = planner_agent

        # Load executive roster once; ArchonProfile repository drops portfolio fields.
        self._portfolio_dir = self._load_portfolio_directory(archons_path)

        logger.info(
            "executive_planning_initialized",
            executive_portfolios=len(self._portfolio_dir.portfolios),
            planner_llm_enabled=planner_agent is not None,
        )

    # ------------------------------------------------------------------
    # Ratified Intent Packet bundling
    # ------------------------------------------------------------------

    def build_ratified_intent_packets(
        self,
        review_pipeline_path: Path,
        consolidator_path: Path | None = None,
        include_deferred: bool = False,
    ) -> list[RatifiedIntentPacket]:
        """Bundle review+consolidator artifacts into ratified intent packets."""
        review_pipeline_path = review_pipeline_path.resolve()

        pipeline_result_path = review_pipeline_path / "pipeline_result.json"
        ratification_path = review_pipeline_path / "ratification_results.json"
        aggregations_path = review_pipeline_path / "aggregations.json"
        triage_path = review_pipeline_path / "triage_results.json"
        audit_path = review_pipeline_path / "audit_trail.json"

        pipeline_result = _load_json(pipeline_result_path)
        session_id = pipeline_result.get("session_id")
        if not session_id:
            raise ValueError("pipeline_result.json missing session_id")

        if consolidator_path is None:
            consolidator_path = (
                review_pipeline_path.parent.parent / "consolidator" / session_id
            )

        mega_motions_path = consolidator_path / "mega-motions.json"
        deferred_path = consolidator_path / "deferred-novel-proposals.json"

        ratifications = _load_json(ratification_path)
        aggregations = {a["mega_motion_id"]: a for a in _load_json(aggregations_path)}
        triage_lookup = {
            m["mega_motion_id"]: m for m in _load_json(triage_path)["motions"]
        }

        mega_lookup: dict[str, dict[str, Any]] = {}
        if mega_motions_path.exists():
            for mm in _load_json(mega_motions_path):
                mega_lookup[mm["mega_motion_id"]] = mm

        deferred_lookup: dict[str, dict[str, Any]] = {}
        if include_deferred and deferred_path.exists():
            for dp in _load_json(deferred_path):
                deferred_lookup[dp["proposal_id"]] = dp

        # Prefer latest ratified entry per motion (revisions supersede initial votes).
        ratified_by_motion: dict[str, dict[str, Any]] = {}
        for vote in ratifications:
            if vote.get("outcome") != "ratified":
                continue
            motion_id = vote["mega_motion_id"]
            prior = ratified_by_motion.get(motion_id)
            if not prior or vote.get("ratified_at", "") > prior.get("ratified_at", ""):
                ratified_by_motion[motion_id] = vote

        source_artifacts = []
        for name, path in [
            ("pipeline_result", pipeline_result_path),
            ("ratification_results", ratification_path),
            ("aggregations", aggregations_path),
            ("triage_results", triage_path),
            ("audit_trail", audit_path),
            ("mega_motions", mega_motions_path),
        ]:
            if path.exists():
                source_artifacts.append(
                    {
                        "name": name,
                        "path": str(path),
                        "sha256": _sha256_file(path),
                    }
                )

        packets: list[RatifiedIntentPacket] = []
        for motion_id, vote in ratified_by_motion.items():
            mega = mega_lookup.get(motion_id, {})
            deferred = deferred_lookup.get(motion_id, {})
            aggregation = aggregations.get(motion_id, {})
            triage = triage_lookup.get(motion_id, {})

            ratified_text = (
                vote.get("revised_motion_text")
                or mega.get("consolidated_text")
                or deferred.get("proposal_text")
                or ""
            )

            ratified_motion = {
                "motion_id": motion_id,
                "title": vote.get("mega_motion_title") or mega.get("title") or "",
                "theme": mega.get("theme") or deferred.get("theme") or "",
                "ratified_text": ratified_text,
                "supporting_archons": mega.get("all_supporting_archons", []),
                "consensus_tier": mega.get("consensus_tier"),
                "source_motion_ids": mega.get("source_motion_ids", []),
                "source_cluster_ids": mega.get("source_cluster_ids", []),
                # Placeholder field for downstream spotlighting.
                "constraints": [],
            }

            ratification_record = {
                k: vote.get(k)
                for k in (
                    "vote_id",
                    "mega_motion_id",
                    "mega_motion_title",
                    "yeas",
                    "nays",
                    "abstentions",
                    "amends",
                    "eligible_votes",
                    "total_votes",
                    "participation_rate",
                    "threshold_type",
                    "threshold_required",
                    "quorum_required",
                    "quorum_met",
                    "support_total",
                    "support_required",
                    "threshold_met",
                    "revision_of",
                    "ratified_at",
                    "outcome",
                )
            }

            review_artifacts = {
                "triage": triage,
                "aggregation": aggregation,
                "dissent": {
                    "opposition_reasons": aggregation.get("opposition_reasons", []),
                    "amendment_texts": aggregation.get("amendment_texts", []),
                },
            }

            packet = RatifiedIntentPacket(
                packet_id=f"rip_{uuid.uuid4().hex[:12]}",
                created_at=now_iso(),
                motion_id=motion_id,
                ratified_motion=ratified_motion,
                ratification_record=ratification_record,
                review_artifacts=review_artifacts,
                provenance={
                    "source_artifacts": source_artifacts,
                    "notes": "Bundled from review-pipeline + consolidator artifacts",
                },
            )

            packets.append(packet)

        logger.info(
            "ratified_intent_packets_built",
            session_id=session_id,
            ratified_motion_count=len(packets),
            include_deferred=include_deferred,
        )
        return packets

    # ------------------------------------------------------------------
    # Executive roster helpers
    # ------------------------------------------------------------------

    def executive_portfolios(self) -> list[PortfolioIdentity]:
        return list(self._portfolio_dir.portfolios)

    def portfolio_labels(self) -> dict[str, str]:
        return dict(self._portfolio_dir.labels_by_portfolio)

    def infer_assignment(
        self,
        packet: RatifiedIntentPacket,
        max_portfolios: int = 4,
    ) -> tuple[list[str], str]:
        """Infer affected portfolios and a plan owner from intent text."""
        text = " ".join(
            [
                packet.ratified_motion.get("title", ""),
                packet.ratified_motion.get("theme", ""),
                packet.ratified_motion.get("ratified_text", ""),
            ]
        ).lower()

        scores: list[tuple[int, str]] = []
        for portfolio in self._portfolio_dir.portfolios:
            scope_terms = self._portfolio_dir.scopes_by_portfolio.get(
                portfolio.portfolio_id, []
            )
            score = sum(1 for term in scope_terms if term.lower() in text)
            if score > 0:
                scores.append((score, portfolio.portfolio_id))

        # Fall back to a reasonable default if no matches were found.
        if not scores:
            default_owner = "portfolio_technical_solutions"
            affected = [default_owner, "portfolio_resource_discovery"]
            return affected, default_owner

        scores.sort(reverse=True)
        owner = scores[0][1]

        affected = [pid for _, pid in scores[:max_portfolios]]
        if owner not in affected:
            affected.insert(0, owner)

        # Always include Resource Discovery for capacity visibility if present.
        if (
            "portfolio_resource_discovery" in self._portfolio_dir.labels_by_portfolio
            and "portfolio_resource_discovery" not in affected
        ):
            affected.append("portfolio_resource_discovery")

        return affected, owner

    # ------------------------------------------------------------------
    # E0/E1/E2/E3 procedural governance
    # ------------------------------------------------------------------

    def open_cycle(self, motion_id: str) -> str:
        cycle_id = f"exec_{uuid.uuid4().hex[:12]}"
        self._emit(
            "executive.cycle.opened",
            {"cycle_id": cycle_id, "motion_id": motion_id, "ts": now_iso()},
        )
        return cycle_id

    def run_assignment_session(
        self,
        packet: RatifiedIntentPacket,
        affected_portfolio_ids: list[str],
        plan_owner_portfolio_id: str,
        response_deadline_iso: str,
    ) -> dict[str, Any]:
        affected = [
            p
            for p in self._portfolio_dir.portfolios
            if p.portfolio_id in set(affected_portfolio_ids)
        ]
        if not affected:
            raise ValueError("No affected portfolios identified; cannot proceed.")

        owner = next(
            (p for p in affected if p.portfolio_id == plan_owner_portfolio_id), None
        )
        if not owner:
            raise ValueError("Plan owner must be one of the affected portfolios.")

        cycle_id = self.open_cycle(packet.motion_id)
        record = {
            "cycle_id": cycle_id,
            "created_at": now_iso(),
            "motion_id": packet.motion_id,
            "plan_owner": owner.to_dict(),
            "affected_portfolios": [p.to_dict() for p in affected],
            "response_deadline": response_deadline_iso,
            "gates": {
                "completeness": "REQUIRED",
                "integrity": "REQUIRED",
                "visibility": "REQUIRED",
            },
        }

        self._emit(
            "executive.plan.owner_assigned",
            {"cycle_id": cycle_id, "owner": owner.to_dict()},
        )
        self._emit("executive.assignment.issued", record)
        return record

    def collect_responses(
        self,
        cycle_id: str,
        motion_id: str,
        affected: list[PortfolioIdentity],
        contributions: list[PortfolioContribution],
        attestations: list[NoActionAttestation],
        missing_as_event: bool = True,
    ) -> tuple[list[PortfolioContribution], list[NoActionAttestation], list[str]]:
        responded: set[str] = set()
        for c in contributions:
            responded.add(c.portfolio.portfolio_id)
        for a in attestations:
            responded.add(a.portfolio.portfolio_id)

        missing = [p.portfolio_id for p in affected if p.portfolio_id not in responded]
        if missing and missing_as_event:
            for portfolio_id in missing:
                self._emit(
                    "executive.portfolio.no_response",
                    {
                        "cycle_id": cycle_id,
                        "motion_id": motion_id,
                        "portfolio_id": portfolio_id,
                        "ts": now_iso(),
                    },
                )

        return contributions, attestations, missing

    def integrate_execution_plan(
        self,
        packet: RatifiedIntentPacket,
        assignment_record: dict[str, Any],
        contributions: list[PortfolioContribution],
        attestations: list[NoActionAttestation],
        draft_plan: dict[str, Any] | None = None,
    ) -> ExecutiveCycleResult:
        motion_id = packet.motion_id
        cycle_id = assignment_record["cycle_id"]
        owner = PortfolioIdentity(**assignment_record["plan_owner"])
        affected = [PortfolioIdentity(**p) for p in assignment_record["affected_portfolios"]]

        _, _, missing = self.collect_responses(
            cycle_id, motion_id, affected, contributions, attestations
        )
        completeness_ok = len(missing) == 0

        failures: list[str] = []
        if not completeness_ok:
            failures.append(f"Completeness failed: missing responses from {missing}")

        def _has_capacity_claim(obj: PortfolioContribution | NoActionAttestation) -> bool:
            cc = getattr(obj, "capacity_claim", None)
            return cc is not None and getattr(cc, "claim_type", None) is not None

        visibility_ok = all(_has_capacity_claim(c) for c in contributions) and all(
            _has_capacity_claim(a) for a in attestations
        )
        if not visibility_ok:
            failures.append("Visibility failed: missing capacity claim(s)")

        blockers_requiring_escalation: list[Blocker] = []
        for c in contributions:
            for b in c.blockers:
                if b.requires_escalation or b.severity.upper() == "CRITICAL":
                    blockers_requiring_escalation.append(b)

        if blockers_requiring_escalation:
            self._emit(
                "executive.blocker.raised",
                {
                    "cycle_id": cycle_id,
                    "motion_id": motion_id,
                    "count": len(blockers_requiring_escalation),
                    "blockers": [b.to_dict() for b in blockers_requiring_escalation],
                    "ts": now_iso(),
                },
            )

        # Integrity currently passes if escalation is surfaced as an event.
        integrity_ok = True

        plan = self._build_execution_plan(
            packet=packet,
            cycle_id=cycle_id,
            owner=owner,
            contributions=contributions,
            attestations=attestations,
            draft_plan=draft_plan,
        )

        gates = ExecutiveGates(
            completeness=GateStatus.PASS if completeness_ok else GateStatus.FAIL,
            integrity=GateStatus.PASS if integrity_ok else GateStatus.FAIL,
            visibility=GateStatus.PASS if visibility_ok else GateStatus.FAIL,
            failures=failures,
        )

        self._emit(
            "executive.plan.integrated",
            {
                "cycle_id": cycle_id,
                "motion_id": motion_id,
                "gates": gates.to_dict(),
                "ts": now_iso(),
            },
        )

        return ExecutiveCycleResult(
            cycle_id=cycle_id,
            motion_id=motion_id,
            plan_owner=owner,
            contributions=contributions,
            attestations=attestations,
            blockers_requiring_escalation=blockers_requiring_escalation,
            execution_plan=plan,
            gates=gates,
        )

    # ------------------------------------------------------------------
    # Draft planning wrapper (templates as proposal scaffold only)
    # ------------------------------------------------------------------

    def generate_template_draft(
        self,
        packet: RatifiedIntentPacket,
        review_pipeline_path: Path,
    ) -> dict[str, Any]:
        """Generate a draft plan using existing template planner (non-binding)."""
        planner = ExecutionPlannerService(planner_agent=self._planner_agent)

        motion_for_planning = self._packet_to_motion_for_planning(
            packet, review_pipeline_path
        )
        plan = planner.generate_execution_plan(motion_for_planning)

        draft = plan.to_dict()
        draft["draft_source"] = {
            "type": "template_bootstrap",
            "note": (
                "Draft generated from templates; Executive portfolio artifacts "
                "remain the authoritative plan inputs."
            ),
        }
        return draft

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_execution_plan(
        self,
        packet: RatifiedIntentPacket,
        cycle_id: str,
        owner: PortfolioIdentity,
        contributions: list[PortfolioContribution],
        attestations: list[NoActionAttestation],
        draft_plan: dict[str, Any] | None,
    ) -> dict[str, Any]:
        def _capacity_claim_dict(cc: Any) -> dict[str, Any]:
            if cc is None:
                return {"claim_type": None, "units": None, "unit_label": None}
            if hasattr(cc, "to_dict"):
                return cc.to_dict()
            return {
                "claim_type": getattr(cc, "claim_type", None),
                "units": getattr(cc, "units", None),
                "unit_label": getattr(cc, "unit_label", None),
            }

        plan: dict[str, Any] = {
            "cycle_id": cycle_id,
            "motion_id": packet.motion_id,
            "plan_owner": owner.to_dict(),
            "intent_provenance": {
                "packet_id": packet.packet_id,
                "ratification_record": packet.ratification_record,
                "review_artifacts": packet.review_artifacts,
                "provenance": packet.provenance,
            },
            "portfolio_contributions": [],
            "no_action_attestations": [],
            "draft_source": None,
        }

        if draft_plan is not None:
            plan["draft_source"] = {
                "type": "template_bootstrap",
                "note": (
                    "Draft used as proposal only; final plan is integrated from "
                    "explicit portfolio responses."
                ),
            }
            plan["draft_plan"] = draft_plan

        for c in contributions:
            plan["portfolio_contributions"].append(
                {
                    "portfolio": c.portfolio.to_dict(),
                    "capacity_claim": _capacity_claim_dict(c.capacity_claim),
                    "tasks": c.tasks,
                    "blockers": [b.to_dict() for b in c.blockers],
                }
            )

        for a in attestations:
            plan["no_action_attestations"].append(
                {
                    "portfolio": a.portfolio.to_dict(),
                    "reason_code": a.reason_code.value,
                    "explanation": a.explanation,
                    "capacity_claim": _capacity_claim_dict(a.capacity_claim),
                }
            )

        return plan

    def _packet_to_motion_for_planning(
        self,
        packet: RatifiedIntentPacket,
        review_pipeline_path: Path,
    ) -> MotionForPlanning:
        ratification = packet.ratification_record
        motion = packet.ratified_motion

        # Theme and supporting archons live in consolidator artifacts.
        theme = motion.get("theme", "")
        supporting_archons = motion.get("supporting_archons", [])

        return MotionForPlanning(
            motion_id=packet.motion_id,
            motion_title=motion.get("title", ""),
            motion_text=motion.get("ratified_text", ""),
            ratified_at=ratification.get("ratified_at", ""),
            yeas=int(ratification.get("yeas") or 0),
            nays=int(ratification.get("nays") or 0),
            abstentions=int(ratification.get("abstentions") or 0),
            source_archons=list(supporting_archons),
            theme=theme,
        )

    def _load_portfolio_directory(self, archons_path: Path) -> PortfolioDirectory:
        data = _load_json(archons_path)
        archons = data.get("archons", [])

        portfolios: list[PortfolioIdentity] = []
        scopes_by_portfolio: dict[str, list[str]] = {}
        labels_by_portfolio: dict[str, str] = {}
        names_by_portfolio: dict[str, str] = {}

        for archon in archons:
            if archon.get("branch") != "executive":
                continue
            portfolio_id = archon.get("portfolio_id")
            if not portfolio_id:
                continue

            pid = str(portfolio_id)
            identity = PortfolioIdentity(
                portfolio_id=pid,
                president_id=str(archon["id"]),
                president_name=str(archon["name"]),
            )
            portfolios.append(identity)

            scopes_by_portfolio[pid] = list(archon.get("portfolio_scope", []))
            labels_by_portfolio[pid] = str(archon.get("portfolio_label", pid))
            names_by_portfolio[pid] = str(archon.get("name", pid))

        return PortfolioDirectory(
            portfolios=sorted(portfolios, key=lambda p: p.portfolio_id),
            scopes_by_portfolio=scopes_by_portfolio,
            labels_by_portfolio=labels_by_portfolio,
            names_by_portfolio=names_by_portfolio,
        )

    def _emit(self, event_type: str, payload: dict[str, Any]) -> None:
        logger.info("executive_event", event_type=event_type, **payload)
        if self._event_sink:
            self._event_sink(event_type, payload)
