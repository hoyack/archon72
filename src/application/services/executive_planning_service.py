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

from src.application.ports.blocker_workup import BlockerWorkupContext
from src.application.ports.execution_planner import MotionForPlanning
from src.application.ports.president_deliberation import DeliberationContext
from src.application.services.execution_planner_service import ExecutionPlannerService
from src.domain.models.executive_planning import (
    SCHEMA_VERSION,
    SCHEMA_VERSION_V1,
    Blocker,
    BlockerClass,
    BlockerDisposition,
    BlockerPacket,
    BlockerV2,
    BlockerWorkupResult,
    CapacityClaim,
    ConclaveQueueItem,
    DiscoveryTaskStub,
    Epic,
    ExecutiveCycleResult,
    ExecutiveGates,
    GateStatus,
    NoActionAttestation,
    NoActionReason,
    PeerReviewSummary,
    PortfolioContribution,
    PortfolioIdentity,
    RatifiedIntentPacket,
    WorkPackage,
    validate_no_forbidden_fields,
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
        president_deliberator: Any | None = None,
        blocker_workup: Any | None = None,
        verbose: bool = False,
    ) -> None:
        self._event_sink = event_sink
        self._archons_path = archons_path
        self._verbose = verbose
        self._planner_agent = planner_agent
        self._president_deliberator = president_deliberator
        self._blocker_workup = blocker_workup

        # Load executive roster once; ArchonProfile repository drops portfolio fields.
        self._portfolio_dir = self._load_portfolio_directory(archons_path)

        logger.info(
            "executive_planning_initialized",
            executive_portfolios=len(self._portfolio_dir.portfolios),
            planner_llm_enabled=planner_agent is not None,
            president_llm_enabled=president_deliberator is not None,
            blocker_workup_enabled=blocker_workup is not None,
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

    def build_ratified_intent_packets_from_mandates(
        self,
        mandates_path: Path,
    ) -> list[RatifiedIntentPacket]:
        """Bundle registrar mandates into ratified intent packets."""
        mandates_path = mandates_path.resolve()
        mandates_payload = _load_json(mandates_path)
        mandates = mandates_payload.get("mandates", [])

        source_artifacts = [
            {
                "name": "ratified_mandates",
                "path": str(mandates_path),
                "sha256": _sha256_file(mandates_path),
            }
        ]

        packets: list[RatifiedIntentPacket] = []
        for mandate in mandates:
            vote = mandate.get("vote_result", {})
            motion_id = mandate.get("motion_id") or mandate.get("mandate_id", "")

            ratified_motion = {
                "motion_id": motion_id,
                "mandate_id": mandate.get("mandate_id"),
                "title": mandate.get("title", ""),
                "theme": mandate.get("theme", ""),
                "ratified_text": mandate.get("text", ""),
                "supporting_archons": [],
                "consensus_tier": None,
                "source_motion_ids": [motion_id],
                "source_cluster_ids": [],
                "constraints": mandate.get("constraints", []),
            }

            ratification_record = {
                "mandate_id": mandate.get("mandate_id"),
                "vote_id": None,
                "mega_motion_id": None,
                "mega_motion_title": mandate.get("title"),
                "yeas": vote.get("ayes"),
                "nays": vote.get("nays"),
                "abstentions": vote.get("abstentions"),
                "amends": None,
                "eligible_votes": vote.get("total_votes"),
                "total_votes": vote.get("total_votes"),
                "participation_rate": None,
                "threshold_type": vote.get("threshold", "supermajority"),
                "threshold_required": vote.get("threshold_required"),
                "quorum_required": None,
                "quorum_met": None,
                "support_total": None,
                "support_required": None,
                "threshold_met": vote.get("threshold_met", True),
                "revision_of": None,
                "ratified_at": mandate.get("passed_at"),
                "outcome": "ratified",
            }

            review_artifacts = {
                "triage": {},
                "aggregation": {},
                "dissent": {"opposition_reasons": [], "amendment_texts": []},
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
                    "notes": "Bundled from registrar mandates",
                },
            )
            packets.append(packet)

        logger.info(
            "ratified_intent_packets_built",
            session_id=mandates_payload.get("conclave_session_id", ""),
            ratified_motion_count=len(packets),
            include_deferred=False,
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
        blocker_workup_result: BlockerWorkupResult | None = None,
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

        def _looks_like_v2_blocker(b: Any) -> bool:
            if isinstance(b, BlockerV2):
                return True
            if isinstance(b, dict):
                return (
                    b.get("schema_version") == SCHEMA_VERSION
                    or "blocker_class" in b
                    or "disposition" in b
                )
            return getattr(b, "schema_version", None) == SCHEMA_VERSION

        # Determine whether we should enforce v2 legibility rules.
        is_v2_mode = blocker_workup_result is not None or any(
            c.schema_version == SCHEMA_VERSION
            or bool(c.work_packages)
            or any(_looks_like_v2_blocker(b) for b in c.blockers)
            for c in contributions
        )

        # Collect and validate blockers (version-aware)
        blockers_requiring_escalation: list[Blocker] = []
        blockers_v2: list[BlockerV2] = []
        conclave_queue_items: list[ConclaveQueueItem] = []
        discovery_task_stubs: list[DiscoveryTaskStub] = []
        peer_review_summary: PeerReviewSummary | None = None

        legibility_errors: list[str] = []

        # Contribution-level validation (v2 legibility rules).
        if is_v2_mode:
            for c in contributions:
                legibility_errors.extend(c.validate())

                for i, task in enumerate(c.tasks):
                    legibility_errors.extend(
                        validate_no_forbidden_fields(
                            task,
                            f"contribution.{c.portfolio.portfolio_id}.tasks[{i}]",
                        )
                    )
                for i, wp in enumerate(c.work_packages):
                    legibility_errors.extend(
                        validate_no_forbidden_fields(
                            wp.to_dict(),
                            f"contribution.{c.portfolio.portfolio_id}.work_packages[{i}]",
                        )
                    )

        if blocker_workup_result is not None:
            blockers_v2 = list(blocker_workup_result.final_blockers)
            conclave_queue_items = list(blocker_workup_result.conclave_queue_items)
            discovery_task_stubs = list(blocker_workup_result.discovery_task_stubs)
            peer_review_summary = blocker_workup_result.peer_review_summary
            for b in blockers_v2:
                legibility_errors.extend(b.validate())
        else:
            for c in contributions:
                for idx, b in enumerate(c.blockers):
                    if isinstance(b, BlockerV2):
                        blockers_v2.append(b)
                        continue

                    if _looks_like_v2_blocker(b):
                        b_dict = b if isinstance(b, dict) else b.to_dict()
                        try:
                            blockers_v2.append(BlockerV2.from_dict(b_dict))
                        except Exception as exc:  # pragma: no cover - defensive
                            legibility_errors.append(
                                "Invalid v2 blocker from "
                                f"{c.portfolio.portfolio_id}[{idx}]: {exc}"
                            )
                        continue

                    # Legacy blocker handling.
                    if b.requires_escalation or str(b.severity).upper() == "CRITICAL":
                        blockers_requiring_escalation.append(b)

            # Process v2 blockers: validate and generate downstream artifacts
            for b in blockers_v2:
                legibility_errors.extend(b.validate())

                if b.disposition == BlockerDisposition.ESCALATE_NOW:
                    queue_item = ConclaveQueueItem(
                        queue_item_id=f"cqi_{b.id}",
                        cycle_id=cycle_id,
                        motion_id=motion_id,
                        blocker_id=b.id,
                        blocker_class=b.blocker_class,
                        questions=[b.description],
                        options=[
                            "Resolve in Conclave",
                            "Defer resolution",
                            "Reject motion",
                        ],
                        source_citations=b.escalation_conditions,
                        created_at=now_iso(),
                    )
                    conclave_queue_items.append(queue_item)
                    self._emit(
                        "executive.blocker.escalated",
                        {
                            "cycle_id": cycle_id,
                            "motion_id": motion_id,
                            "blocker_id": b.id,
                            "blocker_class": b.blocker_class.value,
                            "queue_item_id": queue_item.queue_item_id,
                            "ts": now_iso(),
                        },
                    )

                elif b.disposition == BlockerDisposition.DEFER_DOWNSTREAM:
                    for vt in b.verification_tasks:
                        stub = DiscoveryTaskStub(
                            task_id=vt.task_id,
                            origin_blocker_id=b.id,
                            question=b.description,
                            deliverable=vt.success_signal,
                            max_effort=b.ttl,
                            stop_conditions=[vt.success_signal],
                            ttl=b.ttl,
                            escalation_conditions=b.escalation_conditions,
                        )
                        discovery_task_stubs.append(stub)
                    self._emit(
                        "executive.blocker.deferred_downstream",
                        {
                            "cycle_id": cycle_id,
                            "motion_id": motion_id,
                            "blocker_id": b.id,
                            "discovery_tasks": len(b.verification_tasks),
                            "ts": now_iso(),
                        },
                    )

                elif b.disposition == BlockerDisposition.MITIGATE_IN_EXECUTIVE:
                    self._emit(
                        "executive.blocker.mitigated_in_executive",
                        {
                            "cycle_id": cycle_id,
                            "motion_id": motion_id,
                            "blocker_id": b.id,
                            "mitigation_notes": b.mitigation_notes,
                            "ts": now_iso(),
                        },
                    )

        # Emit legacy event for v1 blockers
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

        # E3: Generate epics from contributions (v2 only)
        epics: list[Epic] = []
        if is_v2_mode:
            epics = self._generate_epics_from_contributions(
                packet=packet,
                contributions=contributions,
                blockers_v2=blockers_v2,
            )
            # Validate epic traceability
            epic_errors = self._check_epic_traceability(epics)
            legibility_errors.extend(epic_errors)
            if not epics:
                legibility_errors.append(
                    "No epics generated for v2 plan; epics are required"
                )

            if epics:
                self._emit(
                    "executive.epics.generated",
                    {
                        "cycle_id": cycle_id,
                        "motion_id": motion_id,
                        "epic_count": len(epics),
                        "epic_ids": [e.epic_id for e in epics],
                        "ts": now_iso(),
                    },
                )

        # Legibility gate (v2) / Integrity gate (v1)
        # v2: all blockers must be valid and properly dispositioned, epics must be traceable
        # v1: passes if escalation is surfaced as an event
        if is_v2_mode:
            # Ensure escalation artifacts exist for intent ambiguity blockers.
            for b in blockers_v2:
                if b.blocker_class == BlockerClass.INTENT_AMBIGUITY:
                    if not any(
                        item.blocker_id == b.id for item in conclave_queue_items
                    ):
                        legibility_errors.append(
                            f"Blocker {b.id}: INTENT_AMBIGUITY requires conclave queue item"
                        )
                if b.disposition == BlockerDisposition.DEFER_DOWNSTREAM:
                    if not any(
                        stub.origin_blocker_id == b.id
                        for stub in discovery_task_stubs
                    ):
                        legibility_errors.append(
                            f"Blocker {b.id}: DEFER_DOWNSTREAM requires discovery task stub"
                        )

            integrity_ok = len(legibility_errors) == 0
            if not integrity_ok:
                for err in legibility_errors:
                    failures.append(f"Legibility failed: {err}")
        else:
            # v1 fallback: integrity passes if escalation surfaced
            integrity_ok = True

        plan = self._build_execution_plan(
            packet=packet,
            cycle_id=cycle_id,
            owner=owner,
            contributions=contributions,
            attestations=attestations,
            draft_plan=draft_plan,
            schema_version=SCHEMA_VERSION if is_v2_mode else SCHEMA_VERSION_V1,
            blockers_v2=blockers_v2,
            conclave_queue_items=conclave_queue_items,
            discovery_task_stubs=discovery_task_stubs,
            peer_review_summary=peer_review_summary,
            epics=epics,
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
            epics=epics,
            discovery_task_stubs=discovery_task_stubs,
            conclave_queue_items=conclave_queue_items,
            schema_version=SCHEMA_VERSION if is_v2_mode else SCHEMA_VERSION_V1,
        )

    # ------------------------------------------------------------------
    # Inbox loading for portfolio responses
    # ------------------------------------------------------------------

    def load_contributions_from_inbox(
        self,
        inbox_path: Path,
        cycle_id: str,
        motion_id: str,
        assignment_record: dict[str, Any] | None = None,
    ) -> list[PortfolioContribution]:
        """Load portfolio contributions from an inbox directory.

        Expected structure:
            inbox_path/
                contribution_{portfolio_id}.json
                contribution_{portfolio_id}.json
                ...

        Args:
            inbox_path: Directory containing contribution JSON files
            cycle_id: Expected cycle_id for validation
            motion_id: Expected motion_id for validation
            assignment_record: Optional assignment record for identity verification

        Returns:
            List of validated PortfolioContribution objects
        """
        contributions: list[PortfolioContribution] = []

        if not inbox_path.exists():
            logger.warning(
                "contribution_inbox_not_found",
                inbox_path=str(inbox_path),
            )
            return contributions

        for file_path in inbox_path.glob("contribution_*.json"):
            # Skip .template files
            if file_path.suffix == ".template" or ".template" in file_path.name:
                continue
            try:
                contribution = self._parse_contribution(
                    file_path, cycle_id, motion_id, assignment_record
                )
                if contribution:
                    contributions.append(contribution)
                    self._emit(
                        "executive.portfolio.contribution_submitted",
                        {
                            "cycle_id": cycle_id,
                            "motion_id": motion_id,
                            "portfolio_id": contribution.portfolio.portfolio_id,
                            "task_count": len(contribution.tasks),
                            "blocker_count": len(contribution.blockers),
                            "ts": now_iso(),
                        },
                    )
            except Exception as e:
                logger.error(
                    "contribution_parse_error",
                    file_path=str(file_path),
                    error=str(e),
                )

        logger.info(
            "contributions_loaded",
            inbox_path=str(inbox_path),
            count=len(contributions),
        )
        return contributions

    def load_attestations_from_inbox(
        self,
        inbox_path: Path,
        cycle_id: str,
        motion_id: str,
        assignment_record: dict[str, Any] | None = None,
    ) -> list[NoActionAttestation]:
        """Load no-action attestations from an inbox directory.

        Expected structure:
            inbox_path/
                attestation_{portfolio_id}.json
                attestation_{portfolio_id}.json
                ...

        Args:
            inbox_path: Directory containing attestation JSON files
            cycle_id: Expected cycle_id for validation
            motion_id: Expected motion_id for validation
            assignment_record: Optional assignment record for identity verification

        Returns:
            List of validated NoActionAttestation objects
        """
        attestations: list[NoActionAttestation] = []

        if not inbox_path.exists():
            logger.warning(
                "attestation_inbox_not_found",
                inbox_path=str(inbox_path),
            )
            return attestations

        for file_path in inbox_path.glob("attestation_*.json"):
            # Skip .template files
            if file_path.suffix == ".template" or ".template" in file_path.name:
                continue
            try:
                attestation = self._parse_attestation(
                    file_path, cycle_id, motion_id, assignment_record
                )
                if attestation:
                    attestations.append(attestation)
                    self._emit(
                        "executive.portfolio.attested_no_action",
                        {
                            "cycle_id": cycle_id,
                            "motion_id": motion_id,
                            "portfolio_id": attestation.portfolio.portfolio_id,
                            "reason_code": attestation.reason_code.value,
                            "ts": now_iso(),
                        },
                    )
            except Exception as e:
                logger.error(
                    "attestation_parse_error",
                    file_path=str(file_path),
                    error=str(e),
                )

        logger.info(
            "attestations_loaded",
            inbox_path=str(inbox_path),
            count=len(attestations),
        )
        return attestations

    def _parse_contribution(
        self,
        file_path: Path,
        expected_cycle_id: str,
        expected_motion_id: str,
        assignment_record: dict[str, Any] | None = None,
    ) -> PortfolioContribution | None:
        """Parse and validate a portfolio contribution JSON file.

        Validates:
        - cycle_id and motion_id match expected values
        - No template markers (_template: true)
        - No TODO: placeholders in task titles/descriptions
        - Capacity claim units > 0 for COARSE_ESTIMATE
        - President identity matches assignment record (if provided)
        """
        data = _load_json(file_path)

        # Reject template files that weren't renamed
        if data.get("_template"):
            logger.warning(
                "contribution_is_template",
                file_path=str(file_path),
                message="File still has _template: true - rename and edit before loading",
            )
            return None

        # Validate cycle/motion match
        if data.get("cycle_id") != expected_cycle_id:
            logger.warning(
                "contribution_cycle_mismatch",
                file_path=str(file_path),
                expected=expected_cycle_id,
                found=data.get("cycle_id"),
            )
            return None

        if data.get("motion_id") != expected_motion_id:
            logger.warning(
                "contribution_motion_mismatch",
                file_path=str(file_path),
                expected=expected_motion_id,
                found=data.get("motion_id"),
            )
            return None

        tasks = data.get("tasks", [])
        work_packages_data = data.get("work_packages", [])
        schema_version = data.get("schema_version")
        if not schema_version:
            has_v2_blocker = any(
                isinstance(b, dict)
                and (
                    b.get("schema_version") == SCHEMA_VERSION
                    or "blocker_class" in b
                    or "disposition" in b
                )
                for b in data.get("blockers", [])
            )
            schema_version = (
                SCHEMA_VERSION
                if work_packages_data or has_v2_blocker
                else SCHEMA_VERSION_V1
            )

        # Validate required identity fields
        required = [
            "portfolio_id",
            "president_id",
            "president_name",
            "capacity_claim",
        ]
        for field in required:
            if field not in data:
                logger.warning(
                    "contribution_missing_field",
                    file_path=str(file_path),
                    field=field,
                )
                return None

        # Validate contribution has work content.
        if not tasks and not work_packages_data:
            logger.warning(
                "contribution_missing_work_items",
                file_path=str(file_path),
                message="Contribution requires tasks or work_packages",
            )
            return None

        # Reject placeholder tasks (TODO: markers)
        for task in tasks:
            title = task.get("title", "")
            description = task.get("description", "")
            if "TODO:" in title or "TODO:" in description:
                logger.warning(
                    "contribution_has_placeholder_tasks",
                    file_path=str(file_path),
                    task_id=task.get("task_id"),
                    message="Tasks cannot contain TODO: placeholders",
                )
                return None

        # Parse and validate work packages when present.
        work_packages: list[WorkPackage] = []
        for idx, wp_data in enumerate(work_packages_data):
            scope_description = wp_data.get("scope_description", "")
            if "TODO:" in scope_description:
                logger.warning(
                    "contribution_has_placeholder_work_package",
                    file_path=str(file_path),
                    package_id=wp_data.get("package_id"),
                    message="Work packages cannot contain TODO: placeholders",
                )
                return None

            if schema_version == SCHEMA_VERSION:
                forbidden_errors = validate_no_forbidden_fields(
                    wp_data, f"work_packages[{idx}]"
                )
                if forbidden_errors:
                    logger.warning(
                        "contribution_work_package_forbidden_fields",
                        file_path=str(file_path),
                        errors=forbidden_errors,
                    )
                    return None

            try:
                wp = WorkPackage.from_dict(wp_data)
            except Exception as exc:
                logger.warning(
                    "contribution_work_package_parse_failed",
                    file_path=str(file_path),
                    package_id=wp_data.get("package_id"),
                    error=str(exc),
                )
                return None

            wp_errors = wp.validate()
            if wp_errors:
                logger.warning(
                    "contribution_work_package_invalid",
                    file_path=str(file_path),
                    package_id=wp.package_id,
                    errors=wp_errors,
                )
                return None
            work_packages.append(wp)

        if schema_version == SCHEMA_VERSION:
            for idx, task in enumerate(tasks):
                forbidden_errors = validate_no_forbidden_fields(
                    task, f"tasks[{idx}]"
                )
                if forbidden_errors:
                    logger.warning(
                        "contribution_task_forbidden_fields",
                        file_path=str(file_path),
                        errors=forbidden_errors,
                    )
                    return None

        # Validate capacity claim
        cc_data = data["capacity_claim"]
        claim_type = cc_data.get("claim_type", "COARSE_ESTIMATE")
        units = cc_data.get("units")

        # COARSE_ESTIMATE must have units > 0
        if claim_type == "COARSE_ESTIMATE" and (units is None or units <= 0):
            logger.warning(
                "contribution_invalid_capacity",
                file_path=str(file_path),
                claim_type=claim_type,
                units=units,
                message="COARSE_ESTIMATE requires units > 0",
            )
            return None

        capacity_claim = CapacityClaim(
            claim_type=claim_type,
            units=units,
            unit_label=cc_data.get("unit_label"),
        )

        # Validate president identity against assignment (if provided)
        if assignment_record:
            affected_portfolios = {
                p["portfolio_id"]: p for p in assignment_record.get("affected_portfolios", [])
            }
            portfolio_id = data["portfolio_id"]
            expected_portfolio = affected_portfolios.get(portfolio_id)

            if not expected_portfolio:
                logger.warning(
                    "contribution_portfolio_not_in_assignment",
                    file_path=str(file_path),
                    portfolio_id=portfolio_id,
                )
                return None

            if data["president_id"] != expected_portfolio["president_id"]:
                logger.warning(
                    "contribution_president_id_mismatch",
                    file_path=str(file_path),
                    expected=expected_portfolio["president_id"],
                    found=data["president_id"],
                )
                return None

        # Parse blockers
        blockers: list[Blocker] = []
        for idx, b in enumerate(data.get("blockers", [])):
            looks_like_v2 = (
                isinstance(b, dict)
                and (
                    b.get("schema_version") == SCHEMA_VERSION
                    or "blocker_class" in b
                    or "disposition" in b
                )
            )
            if looks_like_v2:
                try:
                    blockers.append(BlockerV2.from_dict(b))
                except Exception as exc:
                    logger.warning(
                        "contribution_blocker_v2_parse_failed",
                        file_path=str(file_path),
                        blocker_index=idx,
                        error=str(exc),
                    )
                    return None
            else:
                blockers.append(
                    Blocker(
                        severity=b.get("severity", "LOW"),
                        description=b.get("description", ""),
                        requires_escalation=b.get("requires_escalation", False),
                    )
                )

        portfolio = PortfolioIdentity(
            portfolio_id=data["portfolio_id"],
            president_id=data["president_id"],
            president_name=data["president_name"],
        )

        return PortfolioContribution(
            cycle_id=data["cycle_id"],
            motion_id=data["motion_id"],
            portfolio=portfolio,
            tasks=tasks,
            capacity_claim=capacity_claim,
            blockers=blockers,
            work_packages=work_packages,
            schema_version=schema_version,
        )

    def _parse_attestation(
        self,
        file_path: Path,
        expected_cycle_id: str,
        expected_motion_id: str,
        assignment_record: dict[str, Any] | None = None,
    ) -> NoActionAttestation | None:
        """Parse and validate a no-action attestation JSON file.

        Validates:
        - cycle_id and motion_id match expected values
        - No template markers (_template: true)
        - No TODO: placeholders in explanation
        - Explanation length >= 8 characters
        - President identity matches assignment record (if provided)
        """
        data = _load_json(file_path)

        # Reject template files that weren't renamed
        if data.get("_template"):
            logger.warning(
                "attestation_is_template",
                file_path=str(file_path),
                message="File still has _template: true - rename and edit before loading",
            )
            return None

        # Validate cycle/motion match
        if data.get("cycle_id") != expected_cycle_id:
            logger.warning(
                "attestation_cycle_mismatch",
                file_path=str(file_path),
                expected=expected_cycle_id,
                found=data.get("cycle_id"),
            )
            return None

        if data.get("motion_id") != expected_motion_id:
            logger.warning(
                "attestation_motion_mismatch",
                file_path=str(file_path),
                expected=expected_motion_id,
                found=data.get("motion_id"),
            )
            return None

        # Validate required fields
        required = [
            "portfolio_id",
            "president_id",
            "president_name",
            "reason_code",
            "explanation",
            "capacity_claim",
        ]
        for field in required:
            if field not in data:
                logger.warning(
                    "attestation_missing_field",
                    file_path=str(file_path),
                    field=field,
                )
                return None

        # Validate reason code
        try:
            reason_code = NoActionReason(data["reason_code"])
        except ValueError:
            logger.warning(
                "attestation_invalid_reason_code",
                file_path=str(file_path),
                reason_code=data["reason_code"],
            )
            return None

        # Reject placeholder explanations
        explanation = data["explanation"]
        if "TODO:" in explanation:
            logger.warning(
                "attestation_has_placeholder",
                file_path=str(file_path),
                message="Explanation cannot contain TODO: placeholders",
            )
            return None

        # Validate explanation length
        if len(explanation) < 8:
            logger.warning(
                "attestation_explanation_too_short",
                file_path=str(file_path),
                length=len(explanation),
            )
            return None

        # Validate president identity against assignment (if provided)
        if assignment_record:
            affected_portfolios = {
                p["portfolio_id"]: p for p in assignment_record.get("affected_portfolios", [])
            }
            portfolio_id = data["portfolio_id"]
            expected_portfolio = affected_portfolios.get(portfolio_id)

            if not expected_portfolio:
                logger.warning(
                    "attestation_portfolio_not_in_assignment",
                    file_path=str(file_path),
                    portfolio_id=portfolio_id,
                )
                return None

            if data["president_id"] != expected_portfolio["president_id"]:
                logger.warning(
                    "attestation_president_id_mismatch",
                    file_path=str(file_path),
                    expected=expected_portfolio["president_id"],
                    found=data["president_id"],
                )
                return None

        # Parse capacity claim
        cc_data = data["capacity_claim"]
        capacity_claim = CapacityClaim(
            claim_type=cc_data.get("claim_type", "NONE"),
            units=cc_data.get("units"),
            unit_label=cc_data.get("unit_label"),
        )

        portfolio = PortfolioIdentity(
            portfolio_id=data["portfolio_id"],
            president_id=data["president_id"],
            president_name=data["president_name"],
        )

        return NoActionAttestation(
            cycle_id=data["cycle_id"],
            motion_id=data["motion_id"],
            portfolio=portfolio,
            reason_code=reason_code,
            explanation=explanation,
            capacity_claim=capacity_claim,
        )

    def scaffold_inbox(
        self,
        inbox_path: Path,
        assignment_record: dict[str, Any],
        packet: RatifiedIntentPacket,
    ) -> None:
        """Create scaffold files for portfolio responses in inbox directory.

        Creates template contribution and attestation files for each affected
        portfolio, making it easy for Presidents to fill in their responses.

        Args:
            inbox_path: Directory to create scaffold files in
            assignment_record: The executive assignment record
            packet: The ratified intent packet being planned
        """
        inbox_path.mkdir(parents=True, exist_ok=True)

        cycle_id = assignment_record["cycle_id"]
        motion_id = packet.motion_id
        affected = assignment_record["affected_portfolios"]

        for portfolio in affected:
            portfolio_id = portfolio["portfolio_id"]

            # Contribution scaffold (uses .template extension to prevent accidental loading)
            contribution_scaffold = {
                "_template": True,
                "_instructions": "Remove _template/_instructions, fill in tasks (no TODO:), set units > 0, rename to contribution_{portfolio_id}.json",
                "cycle_id": cycle_id,
                "motion_id": motion_id,
                "portfolio_id": portfolio_id,
                "president_id": portfolio["president_id"],
                "president_name": portfolio["president_name"],
                "tasks": [
                    {
                        "task_id": f"task_{portfolio_id}_001",
                        "title": "TODO: Define task title",
                        "description": "TODO: Define task description",
                        "dependencies": [],
                        "constraints_respected": [],
                    }
                ],
                "capacity_claim": {
                    "claim_type": "COARSE_ESTIMATE",
                    "units": 0,
                    "unit_label": "story_points",
                },
                "blockers": [],
            }

            contribution_path = inbox_path / f"contribution_{portfolio_id}.json.template"
            if not contribution_path.exists():
                with open(contribution_path, "w", encoding="utf-8") as f:
                    json.dump(contribution_scaffold, f, indent=2)

            # Attestation scaffold (alternative to contribution)
            attestation_scaffold = {
                "_template": True,
                "_instructions": "Remove _template/_instructions, fill in reason/explanation (no TODO:), rename to attestation_{portfolio_id}.json",
                "cycle_id": cycle_id,
                "motion_id": motion_id,
                "portfolio_id": portfolio_id,
                "president_id": portfolio["president_id"],
                "president_name": portfolio["president_name"],
                "reason_code": "MOTION_DOES_NOT_REQUIRE_MY_DOMAIN",
                "explanation": "TODO: Provide explanation (minimum 8 characters)",
                "capacity_claim": {
                    "claim_type": "NONE",
                    "units": None,
                    "unit_label": None,
                },
            }

            attestation_path = inbox_path / f"attestation_{portfolio_id}.json.template"
            if not attestation_path.exists():
                with open(attestation_path, "w", encoding="utf-8") as f:
                    json.dump(attestation_scaffold, f, indent=2)

        logger.info(
            "inbox_scaffolded",
            inbox_path=str(inbox_path),
            portfolio_count=len(affected),
        )

    # ------------------------------------------------------------------
    # LLM-powered President deliberation
    # ------------------------------------------------------------------

    async def run_llm_deliberation(
        self,
        packet: RatifiedIntentPacket,
        assignment_record: dict[str, Any],
    ) -> tuple[list[PortfolioContribution], list[NoActionAttestation], int]:
        """Run LLM-powered deliberation for all affected portfolios.

        Each President analyzes the motion and produces either:
        - A PortfolioContribution with tasks and capacity claims
        - A NoActionAttestation with explicit reason

        Args:
            packet: The ratified intent packet to deliberate on
            assignment_record: The executive assignment record

        Returns:
            Tuple of (contributions, attestations, fallback_attestation_count)
            from all portfolios.

        Raises:
            ValueError: If no president_deliberator is configured
        """
        if not self._president_deliberator:
            raise ValueError(
                "LLM deliberation requires president_deliberator to be configured"
            )

        cycle_id = assignment_record["cycle_id"]
        motion_id = packet.motion_id
        affected = assignment_record["affected_portfolios"]
        plan_owner = assignment_record["plan_owner"]
        deadline = assignment_record.get("response_deadline", "")

        # Build deliberation context with enhanced v2 fields
        motion_text = packet.ratified_motion.get("ratified_text", "")
        if not motion_text:
            motion_text = packet.ratified_motion.get("combined_text", "")
        if not motion_text:
            motion_text = packet.ratified_motion.get("text", "")
        motion_title = packet.ratified_motion.get("title", "")
        constraints = packet.ratified_motion.get("constraints", [])

        context = DeliberationContext(
            cycle_id=cycle_id,
            motion_id=motion_id,
            motion_title=motion_title,
            motion_text=motion_text,
            constraints=constraints,
            affected_portfolios=[p["portfolio_id"] for p in affected],
            plan_owner_portfolio_id=plan_owner["portfolio_id"],
            response_deadline=deadline,
            # v2: Enhanced context for better LLM deliberation
            ratified_motion=packet.ratified_motion,
            review_artifacts=packet.review_artifacts,
            assignment_record=assignment_record,
            portfolio_labels=self._portfolio_dir.labels_by_portfolio,
        )

        # Build portfolio list with scopes
        portfolios: list[tuple[PortfolioIdentity, list[str]]] = []
        for p in affected:
            portfolio_id = p["portfolio_id"]
            identity = PortfolioIdentity(
                portfolio_id=portfolio_id,
                president_id=p["president_id"],
                president_name=p["president_name"],
            )
            scope = self._portfolio_dir.scopes_by_portfolio.get(portfolio_id, [])
            portfolios.append((identity, scope))

        self._emit(
            "executive.llm_deliberation.started",
            {
                "cycle_id": cycle_id,
                "motion_id": motion_id,
                "portfolio_count": len(portfolios),
                "ts": now_iso(),
            },
        )

        # Run batch deliberation
        results = await self._president_deliberator.batch_deliberate(
            packet, portfolios, context
        )

        contributions: list[PortfolioContribution] = []
        attestations: list[NoActionAttestation] = []
        fallback_attestation_count = 0
        responded_portfolios: set[str] = set()

        for result in results:
            # Build trace info for events
            trace_info = {}
            if result.trace_metadata:
                trace_info = {
                    "model": result.trace_metadata.model,
                    "provider": result.trace_metadata.provider,
                }

            if result.contributed and result.contribution:
                contributions.append(result.contribution)
                responded_portfolios.add(result.portfolio_id)
                self._emit(
                    "executive.portfolio.contributed_llm",
                    {
                        "cycle_id": cycle_id,
                        "motion_id": motion_id,
                        "portfolio_id": result.portfolio_id,
                        "task_count": len(result.contribution.tasks),
                        "duration_ms": result.duration_ms,
                        "generated_by": result.generated_by,
                        "ts": now_iso(),
                        **trace_info,
                    },
                )
            elif result.attestation:
                attestations.append(result.attestation)
                responded_portfolios.add(result.portfolio_id)
                self._emit(
                    "executive.portfolio.attested_llm",
                    {
                        "cycle_id": cycle_id,
                        "motion_id": motion_id,
                        "portfolio_id": result.portfolio_id,
                        "reason_code": result.attestation.reason_code.value,
                        "duration_ms": result.duration_ms,
                        "generated_by": result.generated_by,
                        "ts": now_iso(),
                        **trace_info,
                    },
                )

        # Auto-attest any missing portfolios to preserve completeness.
        missing_portfolios = [
            p for p in affected if p["portfolio_id"] not in responded_portfolios
        ]
        for missing in missing_portfolios:
            identity = PortfolioIdentity(
                portfolio_id=missing["portfolio_id"],
                president_id=missing["president_id"],
                president_name=missing["president_name"],
            )
            attestation = NoActionAttestation(
                cycle_id=cycle_id,
                motion_id=motion_id,
                portfolio=identity,
                reason_code=NoActionReason.NO_CAPACITY_AVAILABLE,
                explanation=(
                    "AUTO_ATTESTATION: LLM deliberation failed or returned invalid/empty "
                    "response. Treat as no-response; manual follow-up required."
                ),
                capacity_claim=CapacityClaim(claim_type="NONE"),
            )
            attestations.append(attestation)
            fallback_attestation_count += 1
            self._emit(
                "executive.portfolio.attested_fallback",
                {
                    "cycle_id": cycle_id,
                    "motion_id": motion_id,
                    "portfolio_id": missing["portfolio_id"],
                    "reason_code": attestation.reason_code.value,
                    "ts": now_iso(),
                },
            )

        self._emit(
            "executive.llm_deliberation.completed",
            {
                "cycle_id": cycle_id,
                "motion_id": motion_id,
                "contributions": len(contributions),
                "attestations": len(attestations),
                "fallback_attestations": fallback_attestation_count,
                "ts": now_iso(),
            },
        )

        logger.info(
            "llm_deliberation_complete",
            cycle_id=cycle_id,
            motion_id=motion_id,
            contributions=len(contributions),
            attestations=len(attestations),
            fallback_attestations=fallback_attestation_count,
        )

        return contributions, attestations, fallback_attestation_count

    # ------------------------------------------------------------------
    # E2.5 Blocker Workup (cross-review + disposition)
    # ------------------------------------------------------------------

    async def run_blocker_workup(
        self,
        packet: RatifiedIntentPacket,
        assignment_record: dict[str, Any],
        contributions: list[PortfolioContribution],
    ) -> BlockerWorkupResult:
        """Run E2.5 blocker workup for cross-review and disposition.

        This deliberative phase allows the Plan Owner to:
        1. Cross-review all blockers from portfolio drafting
        2. Detect duplicates and conflicts
        3. Identify coverage gaps
        4. Provide disposition rationale

        Args:
            packet: The ratified intent packet being planned
            assignment_record: The executive assignment record
            contributions: Portfolio contributions from E2

        Returns:
            BlockerWorkupResult with peer review summary and final artifacts

        Raises:
            ValueError: If no blocker_workup adapter is configured
        """
        cycle_id = assignment_record["cycle_id"]
        motion_id = packet.motion_id
        plan_owner_data = assignment_record["plan_owner"]
        plan_owner = PortfolioIdentity(**plan_owner_data)

        # Build blocker packet from contributions
        blocker_packet = BlockerPacket.from_contributions(
            cycle_id=cycle_id,
            motion_id=motion_id,
            contributions=contributions,
            created_at=now_iso(),
        )

        self._emit(
            "executive.blocker.workup.started",
            {
                "cycle_id": cycle_id,
                "motion_id": motion_id,
                "blocker_count": len(blocker_packet.blockers),
                "source_portfolios": blocker_packet.source_portfolios,
                "ts": now_iso(),
            },
        )

        # If no LLM workup adapter, perform basic validation only
        if not self._blocker_workup:
            result = self._run_basic_blocker_workup(
                packet, blocker_packet, plan_owner, cycle_id, motion_id
            )
        else:
            # Build workup context
            motion_text = packet.ratified_motion.get("ratified_text", "")
            if not motion_text:
                motion_text = packet.ratified_motion.get("text", "")
            motion_title = packet.ratified_motion.get("title", "")
            constraints = packet.ratified_motion.get("constraints", [])

            context = BlockerWorkupContext(
                cycle_id=cycle_id,
                motion_id=motion_id,
                motion_title=motion_title,
                motion_text=motion_text,
                constraints=constraints,
                plan_owner_portfolio_id=plan_owner.portfolio_id,
                affected_portfolios=[
                    p["portfolio_id"]
                    for p in assignment_record.get("affected_portfolios", [])
                ],
                portfolio_labels=self._portfolio_dir.labels_by_portfolio,
            )

            # Run LLM-powered workup
            result = await self._blocker_workup.run_workup(
                packet, blocker_packet, plan_owner, context
            )

        self._emit(
            "executive.blocker.workup.completed",
            {
                "cycle_id": cycle_id,
                "motion_id": motion_id,
                "duplicates_detected": len(result.peer_review_summary.duplicates_detected),
                "conflicts_detected": len(result.peer_review_summary.conflicts_detected),
                "coverage_gaps": len(result.peer_review_summary.coverage_gaps),
                "final_blocker_count": len(result.final_blockers),
                "conclave_queue_items": len(result.conclave_queue_items),
                "discovery_task_stubs": len(result.discovery_task_stubs),
                "workup_duration_ms": result.workup_duration_ms,
                "ts": now_iso(),
            },
        )

        self._emit(
            "executive.peer_review.completed",
            {
                "cycle_id": cycle_id,
                "motion_id": motion_id,
                "plan_owner_portfolio_id": plan_owner.portfolio_id,
                "peer_review_summary": result.peer_review_summary.to_dict(),
                "ts": now_iso(),
            },
        )

        logger.info(
            "blocker_workup_complete",
            cycle_id=cycle_id,
            motion_id=motion_id,
            blocker_count=len(result.final_blockers),
            duplicates=len(result.peer_review_summary.duplicates_detected),
            conflicts=len(result.peer_review_summary.conflicts_detected),
            gaps=len(result.peer_review_summary.coverage_gaps),
        )

        return result

    def _run_basic_blocker_workup(
        self,
        packet: RatifiedIntentPacket,
        blocker_packet: BlockerPacket,
        plan_owner: PortfolioIdentity,
        cycle_id: str,
        motion_id: str,
    ) -> BlockerWorkupResult:
        """Run basic (non-LLM) blocker workup with validation only.

        Performs structural validation without semantic analysis.
        Used when no blocker_workup adapter is configured.
        """
        import time

        start_time = time.time()

        # Validate all blockers
        validation_errors: list[str] = []
        for b in blocker_packet.blockers:
            validation_errors.extend(b.validate())

        # Build rationale from validation results
        blocker_disposition_rationale: dict[str, str] = {}
        for b in blocker_packet.blockers:
            if b.disposition == BlockerDisposition.ESCALATE_NOW:
                blocker_disposition_rationale[b.id] = (
                    f"Escalated: {b.blocker_class.value} requires Conclave resolution"
                )
            elif b.disposition == BlockerDisposition.DEFER_DOWNSTREAM:
                blocker_disposition_rationale[b.id] = (
                    f"Deferred: {len(b.verification_tasks)} discovery tasks assigned"
                )
            elif b.disposition == BlockerDisposition.MITIGATE_IN_EXECUTIVE:
                blocker_disposition_rationale[b.id] = (
                    f"Mitigated in Executive: {b.mitigation_notes or 'see notes'}"
                )

        # Generate downstream artifacts
        conclave_queue_items: list[ConclaveQueueItem] = []
        discovery_task_stubs: list[DiscoveryTaskStub] = []

        for b in blocker_packet.blockers:
            if b.disposition == BlockerDisposition.ESCALATE_NOW:
                queue_item = ConclaveQueueItem(
                    queue_item_id=f"cqi_{b.id}",
                    cycle_id=cycle_id,
                    motion_id=motion_id,
                    blocker_id=b.id,
                    blocker_class=b.blocker_class,
                    questions=[b.description],
                    options=["Resolve in Conclave", "Defer resolution", "Reject motion"],
                    source_citations=b.escalation_conditions,
                    created_at=now_iso(),
                )
                conclave_queue_items.append(queue_item)
                # Emit escalation event
                self._emit(
                    "executive.blocker.escalated",
                    {
                        "cycle_id": cycle_id,
                        "motion_id": motion_id,
                        "blocker_id": b.id,
                        "blocker_class": b.blocker_class.value,
                        "description": b.description,
                        "queue_item_id": queue_item.queue_item_id,
                        "ts": now_iso(),
                    },
                )

            elif b.disposition == BlockerDisposition.DEFER_DOWNSTREAM:
                for vt in b.verification_tasks:
                    stub = DiscoveryTaskStub(
                        task_id=vt.task_id,
                        origin_blocker_id=b.id,
                        question=b.description,
                        deliverable=vt.success_signal,
                        max_effort=b.ttl,
                        stop_conditions=[vt.success_signal],
                        ttl=b.ttl,
                        escalation_conditions=b.escalation_conditions,
                    )
                    discovery_task_stubs.append(stub)
                # Emit deferred event
                self._emit(
                    "executive.blocker.deferred_downstream",
                    {
                        "cycle_id": cycle_id,
                        "motion_id": motion_id,
                        "blocker_id": b.id,
                        "blocker_class": b.blocker_class.value,
                        "description": b.description,
                        "discovery_task_count": len(b.verification_tasks),
                        "ttl": b.ttl,
                        "ts": now_iso(),
                    },
                )

            elif b.disposition == BlockerDisposition.MITIGATE_IN_EXECUTIVE:
                # Emit mitigation event
                self._emit(
                    "executive.blocker.mitigated_in_executive",
                    {
                        "cycle_id": cycle_id,
                        "motion_id": motion_id,
                        "blocker_id": b.id,
                        "blocker_class": b.blocker_class.value,
                        "description": b.description,
                        "mitigation_notes": b.mitigation_notes or "",
                        "ts": now_iso(),
                    },
                )

        # Build peer review summary
        peer_review_summary = PeerReviewSummary(
            cycle_id=cycle_id,
            motion_id=motion_id,
            plan_owner_portfolio_id=plan_owner.portfolio_id,
            duplicates_detected=[],  # No semantic analysis without LLM
            conflicts_detected=[],  # No semantic analysis without LLM
            coverage_gaps=[],  # No semantic analysis without LLM
            blocker_disposition_rationale=blocker_disposition_rationale,
            created_at=now_iso(),
        )

        duration_ms = int((time.time() - start_time) * 1000)

        return BlockerWorkupResult(
            cycle_id=cycle_id,
            motion_id=motion_id,
            peer_review_summary=peer_review_summary,
            final_blockers=list(blocker_packet.blockers),
            conclave_queue_items=conclave_queue_items,
            discovery_task_stubs=discovery_task_stubs,
            workup_duration_ms=duration_ms,
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

    def _generate_epics_from_contributions(
        self,
        packet: RatifiedIntentPacket,
        contributions: list[PortfolioContribution],
        blockers_v2: list[BlockerV2],
    ) -> list[Epic]:
        """Generate epics from portfolio contributions and motion clauses.

        Plan Owner (E3) composes epics by aggregating work packages from
        all contributing portfolios, mapping to motion clauses for traceability.

        Args:
            packet: The ratified intent packet with motion clauses
            contributions: Portfolio contributions with work packages
            blockers_v2: v2 blockers that may require discovery

        Returns:
            List of Epic objects with acceptance intent
        """
        epics: list[Epic] = []

        # Extract motion clauses from ratified motion for traceability
        motion = packet.ratified_motion
        motion_clauses = motion.get("clauses", [])
        if not motion_clauses:
            # Fall back to extracting from motion text sections
            motion_text = motion.get("ratified_text", "") or motion.get("text", "")
            if motion_text:
                motion_clauses = [f"Motion: {motion.get('title', packet.motion_id)}"]

        # Collect all work packages by portfolio
        all_work_packages: list[WorkPackage] = []
        for c in contributions:
            if c.work_packages:
                all_work_packages.extend(c.work_packages)
                continue

            # Lift v1 tasks into work packages when running in v2 mode.
            for idx, task in enumerate(c.tasks):
                if not isinstance(task, dict):
                    continue
                all_work_packages.append(
                    WorkPackage(
                        package_id=task.get("task_id")
                        or task.get("id")
                        or f"wp_{c.portfolio.portfolio_id}_{idx+1:03d}",
                        epic_id=task.get("epic_id")
                        or f"epic_{packet.motion_id}_{c.portfolio.portfolio_id}",
                        scope_description=task.get("description")
                        or task.get("title")
                        or "Work package",
                        portfolio_id=c.portfolio.portfolio_id,
                        dependencies=task.get("dependencies", []),
                        constraints_respected=task.get("constraints_respected", []),
                        schema_version=SCHEMA_VERSION,
                    )
                )

        if not all_work_packages:
            # No work packages, no epics to generate
            return epics

        # Group work packages by related constraints to form epics
        constraint_groups: dict[str, list[WorkPackage]] = {}
        constraint_portfolios: dict[str, set[str]] = {}
        for wp in all_work_packages:
            # Use first constraint as grouping key, or "general" if none
            key = wp.constraints_respected[0] if wp.constraints_respected else "general"
            if key not in constraint_groups:
                constraint_groups[key] = []
                constraint_portfolios[key] = set()
            constraint_groups[key].append(wp)
            constraint_portfolios[key].add(wp.portfolio_id)

        # Map blockers to epics by ID
        blocker_ids_by_constraint: dict[str, list[str]] = {}
        for b in blockers_v2:
            if b.disposition == BlockerDisposition.DEFER_DOWNSTREAM:
                matched = False
                for key, portfolios in constraint_portfolios.items():
                    if b.owner_portfolio_id in portfolios:
                        blocker_ids_by_constraint.setdefault(key, []).append(b.id)
                        matched = True
                if not matched:
                    blocker_ids_by_constraint.setdefault("general", []).append(b.id)

        # Generate an epic for each constraint group
        for epic_idx, (constraint, work_packages) in enumerate(constraint_groups.items(), start=1):
            epic_id = f"epic_{packet.motion_id}_{epic_idx:03d}"

            # Derive intent from work package scopes
            scope_descriptions = [wp.scope_description for wp in work_packages]
            intent = f"Deliver {constraint} capabilities: " + "; ".join(scope_descriptions[:3])
            if len(scope_descriptions) > 3:
                intent += f" (+{len(scope_descriptions) - 3} more)"

            # Derive success signals from work package scope descriptions
            success_signals = [
                f"Work package {wp.package_id} scope completed: {wp.scope_description[:100]}"
                for wp in work_packages[:5]  # Limit to 5 signals
            ]

            # Map to motion clauses for traceability
            mapped_clauses = motion_clauses[:2] if motion_clauses else []
            if not mapped_clauses:
                mapped_clauses = [f"Motion {packet.motion_id}"]

            # Get discovery requirements from blockers
            discovery_required = list(
                dict.fromkeys(blocker_ids_by_constraint.get(constraint, []))
            )

            epic = Epic(
                epic_id=epic_id,
                intent=intent,
                success_signals=success_signals,
                constraints=[constraint] if constraint != "general" else [],
                assumptions=[],
                discovery_required=discovery_required,
                mapped_motion_clauses=mapped_clauses,
            )
            epics.append(epic)

        return epics

    def _check_epic_traceability(self, epics: list[Epic]) -> list[str]:
        """Check epic traceability and verifiability requirements.

        Every epic must have:
        - At least one mapped_motion_clause (traceability)
        - At least one success_signal (verifiability)

        Args:
            epics: List of epics to validate

        Returns:
            List of validation error messages (empty if all valid)
        """
        errors: list[str] = []
        for epic in epics:
            epic_errors = epic.validate()
            if epic_errors:
                errors.extend(
                    f"Epic {epic.epic_id}: {err}" for err in epic_errors
                )
        return errors

    def _build_execution_plan(
        self,
        packet: RatifiedIntentPacket,
        cycle_id: str,
        owner: PortfolioIdentity,
        contributions: list[PortfolioContribution],
        attestations: list[NoActionAttestation],
        draft_plan: dict[str, Any] | None,
        schema_version: str,
        blockers_v2: list[BlockerV2] | None = None,
        conclave_queue_items: list[ConclaveQueueItem] | None = None,
        discovery_task_stubs: list[DiscoveryTaskStub] | None = None,
        peer_review_summary: PeerReviewSummary | None = None,
        epics: list[Epic] | None = None,
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
            "schema_version": schema_version,
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
                    "schema_version": c.schema_version,
                    "capacity_claim": _capacity_claim_dict(c.capacity_claim),
                    "tasks": c.tasks,
                    "work_packages": [
                        wp.to_dict() if hasattr(wp, "to_dict") else wp
                        for wp in c.work_packages
                    ],
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

        if schema_version == SCHEMA_VERSION:
            def _collect_work_packages() -> list[WorkPackage]:
                collected: list[WorkPackage] = []
                for c in contributions:
                    if c.work_packages:
                        collected.extend(c.work_packages)
                        continue
                    for idx, task in enumerate(c.tasks):
                        if not isinstance(task, dict):
                            continue
                        collected.append(
                            WorkPackage(
                                package_id=task.get("task_id")
                                or task.get("id")
                                or f"wp_{c.portfolio.portfolio_id}_{idx+1:03d}",
                                epic_id=task.get("epic_id")
                                or f"epic_{packet.motion_id}_{c.portfolio.portfolio_id}",
                                scope_description=task.get("description")
                                or task.get("title")
                                or "Work package",
                                portfolio_id=c.portfolio.portfolio_id,
                                dependencies=task.get("dependencies", []),
                                constraints_respected=task.get("constraints_respected", []),
                                schema_version=SCHEMA_VERSION,
                            )
                        )
                return collected

            work_packages = _collect_work_packages()
            plan["blockers"] = [b.to_dict() for b in (blockers_v2 or [])]
            plan["epics"] = [e.to_dict() for e in (epics or [])]
            plan["work_packages"] = [
                wp.to_dict() if hasattr(wp, "to_dict") else wp for wp in work_packages
            ]
            if peer_review_summary is not None:
                plan["peer_review_summary"] = peer_review_summary.to_dict()
            if discovery_task_stubs:
                plan["discovery_task_stubs"] = [s.to_dict() for s in discovery_task_stubs]
            if conclave_queue_items:
                plan["conclave_queue_items"] = [i.to_dict() for i in conclave_queue_items]

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
