"""Earl Decomposition Service — the bridge orchestrator.

Reads the winning Duke proposal from the executive pipeline, decomposes
its tactics into activation-ready TaskDrafts, matches tasks to eligible
Aegis Clusters, and optionally calls TaskActivationService.create_activation()
to place tasks into the governance lifecycle.

This service does NOT create a new consent system, tool registry, or state
machine. It bridges two existing systems:
  - Executive Pipeline artifacts (file-based)
  - Governance Layer ports (TaskActivationService)
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from src.application.ports.tactic_decomposition import (
    ClusterRegistryPort,
    DecompositionContext,
    TacticContext,
    TacticDecomposerProtocol,
)
from src.domain.models.earl_decomposition import (
    ActivationManifestEntry,
    BridgeSummary,
    DecompositionStatus,
    TacticDecompositionEntry,
    TaskDraft,
    check_provenance_mapping,
    detect_overlap,
    lint_task_draft,
)

# Regex for parsing tactic blocks from Duke proposal Markdown
_TACTIC_HEADER_RE = re.compile(
    r"^###\s+(T-[A-Z]{3,5}-\d{1,4}):\s*(.+)$", re.MULTILINE
)
_FIELD_RE = re.compile(r"^\s*-\s+\*\*(\w[\w\s]*):\*\*\s*(.+)$", re.MULTILINE)

# Regex for extracting FR/NFR IDs from text
_REQ_ID_RE = re.compile(r"\b((?:FR|NFR)-[A-Z]{2,8}-\d{1,4})\b", re.IGNORECASE)

DEFAULT_MAX_TASKS_PER_TACTIC = 8
DEFAULT_TTL_HOURS = 72
DEFAULT_ROUTE_TOP_K = 1


class EarlDecompositionService:
    """Orchestrates the Earl Decomposition Bridge.

    Lifecycle:
    1. load_inputs()       — read selection, proposal, RFP
    2. decompose_all()     — iterate tactics, produce TaskDrafts
    3. route_all()         — match tasks to clusters
    4. activate_all()      — call create_activation() (optional)
    5. save_outputs()      — write execution_bridge/ artifacts
    """

    def __init__(
        self,
        decomposer: TacticDecomposerProtocol,
        cluster_registry: ClusterRegistryPort,
        earl_routing_table: dict[str, Any] | None = None,
        max_tasks_per_tactic: int = DEFAULT_MAX_TASKS_PER_TACTIC,
        ttl_hours: int = DEFAULT_TTL_HOURS,
        route_top_k: int = DEFAULT_ROUTE_TOP_K,
        checkpoint_dir: Path | None = None,
        verbose: bool = False,
    ) -> None:
        self._decomposer = decomposer
        self._cluster_registry = cluster_registry
        self._earl_routing_table = earl_routing_table or {}
        self._max_tasks = max_tasks_per_tactic
        self._ttl_hours = ttl_hours
        self._route_top_k = route_top_k
        self._checkpoint_dir = checkpoint_dir
        self._verbose = verbose

        # State accumulated during pipeline
        self._events: list[dict[str, Any]] = []
        self._task_drafts: list[TaskDraft] = []
        self._tactic_entries: list[TacticDecompositionEntry] = []
        self._activation_entries: list[ActivationManifestEntry] = []
        self._summary = BridgeSummary()

    # ------------------------------------------------------------------
    # Event helpers
    # ------------------------------------------------------------------

    def _emit(self, event_type: str, payload: dict[str, Any] | None = None) -> None:
        event = {
            "event_type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "payload": payload or {},
        }
        self._events.append(event)
        if self._verbose:
            print(f"  [event] {event_type}")

    # ------------------------------------------------------------------
    # Input loading
    # ------------------------------------------------------------------

    @staticmethod
    def load_selection_result(path: Path) -> dict[str, Any]:
        """Load selection_result.json."""
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    @staticmethod
    def load_rfp(rfp_path: Path) -> dict[str, Any]:
        """Load rfp.json as raw dict (avoids tight coupling to RFPDocument)."""
        with open(rfp_path, encoding="utf-8") as f:
            return json.load(f)

    @staticmethod
    def load_proposal_markdown(md_path: Path) -> str:
        """Load winning proposal Markdown."""
        return md_path.read_text(encoding="utf-8")

    @staticmethod
    def load_earl_routing_table(path: Path) -> dict[str, Any]:
        """Load earl_routing_table.json."""
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    # ------------------------------------------------------------------
    # Tactic parsing from Markdown
    # ------------------------------------------------------------------

    @staticmethod
    def parse_tactics_from_markdown(markdown: str) -> list[TacticContext]:
        """Extract tactic blocks from Duke proposal Markdown.

        Parses ### T-XXXX-NNN: Title headers and their field lists.
        """
        tactics: list[TacticContext] = []

        # Split on tactic headers
        headers = list(_TACTIC_HEADER_RE.finditer(markdown))
        for idx, match in enumerate(headers):
            tactic_id = match.group(1)
            title = match.group(2).strip()

            # Extract the block text between this header and the next
            start = match.end()
            end = headers[idx + 1].start() if idx + 1 < len(headers) else len(markdown)
            block = markdown[start:end]

            # Parse fields
            fields: dict[str, str] = {}
            for field_match in _FIELD_RE.finditer(block):
                key = field_match.group(1).strip().lower()
                val = field_match.group(2).strip()
                fields[key] = val

            tactics.append(
                TacticContext(
                    tactic_id=tactic_id,
                    title=title,
                    description=fields.get("description", title),
                    deliverable_id=fields.get("deliverable", ""),
                    prerequisites=fields.get("prerequisites", ""),
                    dependencies=fields.get("dependencies", ""),
                    duration=fields.get("estimated duration", ""),
                    owner=fields.get("owner", ""),
                    rationale=fields.get("rationale", ""),
                )
            )

        return tactics

    # ------------------------------------------------------------------
    # RFP context helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_deliverable_info(
        rfp: dict[str, Any], deliverable_id: str
    ) -> tuple[str, list[str]]:
        """Get deliverable name and acceptance criteria from RFP."""
        for d in rfp.get("deliverables", []):
            if d.get("deliverable_id") == deliverable_id:
                return (
                    d.get("name", ""),
                    d.get("acceptance_criteria", []),
                )
        return ("", [])

    @staticmethod
    def _extract_related_requirement_ids(
        rfp: dict[str, Any],
    ) -> tuple[list[str], list[str]]:
        """Extract all FR and NFR IDs from RFP."""
        fr_ids = [
            fr.get("req_id", "")
            for fr in rfp.get("requirements", {}).get("functional", [])
            if fr.get("req_id")
        ]
        nfr_ids = [
            nfr.get("req_id", "")
            for nfr in rfp.get("requirements", {}).get("non_functional", [])
            if nfr.get("req_id")
        ]
        return fr_ids, nfr_ids

    @staticmethod
    def _extract_constraints(rfp: dict[str, Any]) -> list[str]:
        """Extract constraint descriptions from RFP."""
        return [
            f"{c.get('constraint_id', '')}: {c.get('description', '')}"
            for c in rfp.get("constraints", [])
            if c.get("description")
        ]

    # ------------------------------------------------------------------
    # Checkpointing
    # ------------------------------------------------------------------

    def _checkpoint_path(self, tactic_id: str, suffix: str) -> Path | None:
        if self._checkpoint_dir is None:
            return None
        self._checkpoint_dir.mkdir(parents=True, exist_ok=True)
        return self._checkpoint_dir / f"{tactic_id}.{suffix}"

    def _save_checkpoint(
        self, tactic_id: str, suffix: str, content: str | list[dict[str, Any]]
    ) -> None:
        path = self._checkpoint_path(tactic_id, suffix)
        if path is None:
            return
        if isinstance(content, str):
            path.write_text(content, encoding="utf-8")
        else:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(content, f, indent=2)
        if self._verbose:
            print(f"    [checkpoint] saved {tactic_id}.{suffix}")

    def _load_checkpoint(
        self, tactic_id: str, suffix: str
    ) -> list[dict[str, Any]] | None:
        path = self._checkpoint_path(tactic_id, suffix)
        if path is not None and path.exists():
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list) and data:
                    if self._verbose:
                        print(f"    [checkpoint] loaded {tactic_id}.{suffix}")
                    return data
            except (json.JSONDecodeError, OSError):
                pass
        return None

    # ------------------------------------------------------------------
    # Earl resolution
    # ------------------------------------------------------------------

    def _resolve_earl_id(self, tactic: TacticContext) -> str:
        """Resolve earl_id from routing table based on tactic domain.

        Falls back to default_earl_id if no portfolio match.
        """
        default = self._earl_routing_table.get(
            "default_earl_id", "00000000-0000-0000-0000-000000000000"
        )
        # For MVP, use default earl for all tasks.
        # Future: map tactic owner/domain to portfolio_to_earl table.
        return default

    # ------------------------------------------------------------------
    # Core pipeline
    # ------------------------------------------------------------------

    async def decompose_all(
        self,
        tactics: list[TacticContext],
        rfp: dict[str, Any],
        proposal_id: str,
        tactic_filter: str | None = None,
    ) -> list[TaskDraft]:
        """Decompose all tactics into TaskDrafts.

        Args:
            tactics: Parsed tactic contexts from the winning proposal.
            rfp: Raw RFP dict.
            proposal_id: Winning proposal ID.
            tactic_filter: If set, only decompose this tactic ID.

        Returns:
            List of valid TaskDrafts.
        """
        rfp_id = rfp.get("implementation_dossier_id", "")
        mandate_id = rfp.get("mandate_id", "")
        fr_ids, nfr_ids = self._extract_related_requirement_ids(rfp)
        constraints = self._extract_constraints(rfp)

        self._summary.rfp_id = rfp_id
        self._summary.mandate_id = mandate_id
        self._summary.proposal_id = proposal_id

        filtered_tactics = tactics
        if tactic_filter:
            filtered_tactics = [t for t in tactics if t.tactic_id == tactic_filter]

        self._summary.total_tactics = len(filtered_tactics)

        for tactic in filtered_tactics:
            self._emit("bridge.tactic.decomposition_started", {
                "tactic_id": tactic.tactic_id,
                "title": tactic.title,
            })

            entry = TacticDecompositionEntry(
                tactic_id=tactic.tactic_id,
                tactic_title=tactic.title,
                status=DecompositionStatus.COMPLETED,
            )

            # Check checkpoint
            cached = self._load_checkpoint(tactic.tactic_id, "task_drafts.json")
            if cached is not None:
                drafts = [TaskDraft.from_dict(d) for d in cached]
            else:
                # Build decomposition context
                del_name, del_ac = self._extract_deliverable_info(
                    rfp, tactic.deliverable_id
                )
                context = DecompositionContext(
                    tactic=tactic,
                    rfp_id=rfp_id,
                    mandate_id=mandate_id,
                    proposal_id=proposal_id,
                    deliverable_name=del_name,
                    deliverable_acceptance_criteria=del_ac,
                    related_fr_ids=fr_ids,
                    related_nfr_ids=nfr_ids,
                    constraints=constraints,
                )

                try:
                    raw_drafts = await self._decomposer.decompose_tactic(context)
                except Exception as exc:
                    if self._verbose:
                        print(f"  [{tactic.tactic_id}] decomposition FAILED: {exc}")
                    entry.status = DecompositionStatus.FAILED
                    entry.failure_reason = str(exc)
                    entry.events.append("bridge.tactic.decomposition_failed")
                    self._emit("bridge.tactic.decomposition_failed", {
                        "tactic_id": tactic.tactic_id,
                        "error": str(exc),
                    })
                    self._tactic_entries.append(entry)
                    continue

                drafts = [TaskDraft.from_dict(d) for d in raw_drafts]

                # Save checkpoint
                self._save_checkpoint(
                    tactic.tactic_id,
                    "task_drafts.json",
                    [d.to_dict() for d in drafts],
                )

            # --- Lint pass ---
            valid_drafts: list[TaskDraft] = []
            for draft in drafts:
                violations = lint_task_draft(draft)
                if violations:
                    if self._verbose:
                        print(
                            f"    [{draft.task_ref}] lint FAIL: "
                            f"{'; '.join(violations)}"
                        )
                else:
                    valid_drafts.append(draft)

                # Provenance check (soft)
                prov_events = check_provenance_mapping(draft)
                for pe in prov_events:
                    self._emit("bridge.provenance.weak_mapping", {
                        "task_ref": draft.task_ref,
                        "detail": pe,
                    })
                    self._summary.weak_provenance += 1
                    entry.events.append("bridge.provenance.weak_mapping")

            # --- Tactic-level checks ---
            if not valid_drafts:
                entry.status = DecompositionStatus.AMBIGUOUS
                entry.failure_reason = "No valid TaskDrafts after lint"
                entry.events.append("bridge.decomposition.ambiguous_tactic")
                self._emit("bridge.decomposition.ambiguous_tactic", {
                    "tactic_id": tactic.tactic_id,
                })
                self._summary.ambiguous_tactics += 1
                self._tactic_entries.append(entry)
                continue

            if len(valid_drafts) > self._max_tasks:
                entry.status = DecompositionStatus.REVIEW_REQUIRED
                entry.failure_reason = (
                    f"Task explosion: {len(valid_drafts)} > {self._max_tasks}"
                )
                entry.events.append("bridge.decomposition.excessive_scope")
                self._emit("bridge.decomposition.excessive_scope", {
                    "tactic_id": tactic.tactic_id,
                    "count": len(valid_drafts),
                    "max": self._max_tasks,
                })
                self._summary.explosion_review += 1
                # Do not trim — surface the issue
                self._tactic_entries.append(entry)
                continue

            # Overlap detection
            overlaps = detect_overlap(valid_drafts)
            if overlaps:
                entry.status = DecompositionStatus.OVERLAP_REVIEW
                entry.events.append("bridge.decomposition.overlap_detected")
                self._emit("bridge.decomposition.overlap_detected", {
                    "tactic_id": tactic.tactic_id,
                    "overlapping_pairs": overlaps,
                })
                self._summary.overlap_review += 1
                # Execution may proceed; overlap is visible

            entry.task_refs = [d.task_ref for d in valid_drafts]
            self._task_drafts.extend(valid_drafts)

            self._emit("bridge.tactic.decomposition_completed", {
                "tactic_id": tactic.tactic_id,
                "task_count": len(valid_drafts),
            })
            self._tactic_entries.append(entry)

        self._summary.total_task_drafts = len(self._task_drafts)
        return self._task_drafts

    async def route_all(self) -> list[ActivationManifestEntry]:
        """Match each TaskDraft to eligible clusters.

        Populates activation_entries with routing decisions.
        """
        for draft in self._task_drafts:
            candidates = await self._cluster_registry.find_eligible_clusters(
                required_tags=draft.capability_tags,
            )

            if not candidates:
                self._emit("bridge.routing.no_eligible_cluster", {
                    "task_ref": draft.task_ref,
                    "required_tags": draft.capability_tags,
                })
                self._summary.no_eligible_cluster += 1
                self._activation_entries.append(
                    ActivationManifestEntry(
                        task_ref=draft.task_ref,
                        parent_tactic_id=draft.parent_tactic_id,
                        deliverable_id=draft.deliverable_id,
                        rfp_requirement_ids=_extract_req_ids(draft.requirements),
                        status="BLOCKED_BY_CAPABILITY",
                        routing_block_reason="No eligible cluster",
                    )
                )
                continue

            # Select top-k clusters
            selected = candidates[: self._route_top_k]

            for cluster in selected:
                self._activation_entries.append(
                    ActivationManifestEntry(
                        task_ref=draft.task_ref,
                        parent_tactic_id=draft.parent_tactic_id,
                        deliverable_id=draft.deliverable_id,
                        rfp_requirement_ids=_extract_req_ids(draft.requirements),
                        cluster_id=cluster.cluster_id,
                        status="PENDING_ACTIVATION",
                    )
                )

            self._emit("bridge.task.routing_completed", {
                "task_ref": draft.task_ref,
                "cluster_ids": [c.cluster_id for c in selected],
            })

        return self._activation_entries

    async def activate_all(
        self,
        task_activation_service: Any | None = None,
    ) -> None:
        """Call create_activation() for each routed task.

        Args:
            task_activation_service: The governance TaskActivationService.
                If None, activations are skipped (equivalent to --no-activate).
        """
        if task_activation_service is None:
            if self._verbose:
                print("  [bridge] --no-activate: skipping activation calls")
            return

        draft_lookup = {d.task_ref: d for d in self._task_drafts}
        ttl = timedelta(hours=self._ttl_hours)

        for entry in self._activation_entries:
            if entry.status != "PENDING_ACTIVATION":
                continue

            draft = draft_lookup.get(entry.task_ref)
            if draft is None:
                continue

            earl_id = self._resolve_earl_id(
                TacticContext(
                    tactic_id=draft.parent_tactic_id,
                    title="",
                    description="",
                )
            )

            self._summary.activations_attempted += 1

            try:
                result = await task_activation_service.create_activation(
                    earl_id=earl_id,
                    cluster_id=entry.cluster_id,
                    description=draft.description,
                    requirements=list(draft.requirements),
                    expected_outcomes=list(draft.expected_outcomes),
                    ttl=ttl,
                )
                if result.success:
                    entry.activation_id = str(result.filter_decision_id)
                    entry.status = "ROUTED"
                    self._summary.activations_created += 1
                    self._emit("bridge.task.activation_created", {
                        "task_ref": entry.task_ref,
                        "cluster_id": entry.cluster_id,
                        "activation_id": entry.activation_id,
                    })
                else:
                    entry.status = "ACTIVATION_FAILED"
                    entry.routing_block_reason = result.message
                    self._summary.activations_failed += 1
                    self._emit("bridge.task.activation_failed", {
                        "task_ref": entry.task_ref,
                        "cluster_id": entry.cluster_id,
                        "reason": result.message,
                    })
            except Exception as exc:
                entry.status = "ACTIVATION_FAILED"
                entry.routing_block_reason = str(exc)
                self._summary.activations_failed += 1
                self._emit("bridge.task.activation_failed", {
                    "task_ref": entry.task_ref,
                    "cluster_id": entry.cluster_id,
                    "reason": str(exc),
                })

    # ------------------------------------------------------------------
    # Output writing
    # ------------------------------------------------------------------

    def save_outputs(self, output_dir: Path) -> Path:
        """Write all bridge artifacts to execution_bridge/."""
        bridge_dir = output_dir / "execution_bridge"
        bridge_dir.mkdir(parents=True, exist_ok=True)

        self._summary.created_at = datetime.now(timezone.utc).isoformat()

        # task_drafts.json
        _save_json(
            bridge_dir / "task_drafts.json",
            [d.to_dict() for d in self._task_drafts],
        )

        # routing_plan.json (decomposition manifest)
        _save_json(
            bridge_dir / "routing_plan.json",
            [e.to_dict() for e in self._tactic_entries],
        )

        # activation_manifest.json
        _save_json(
            bridge_dir / "activation_manifest.json",
            [e.to_dict() for e in self._activation_entries],
        )

        # bridge_summary.json
        _save_json(bridge_dir / "bridge_summary.json", self._summary.to_dict())

        # bridge_events.jsonl (append-only)
        events_path = bridge_dir / "bridge_events.jsonl"
        with open(events_path, "a", encoding="utf-8") as f:
            for event in self._events:
                f.write(json.dumps(event) + "\n")

        if self._verbose:
            print(f"  [bridge] outputs saved to {bridge_dir}")

        return bridge_dir

    def print_summary(self) -> None:
        """Print a human-readable summary to stdout."""
        s = self._summary
        print("\nEarl Decomposition Bridge Summary")
        print(f"  Tactics processed:     {s.total_tactics}")
        print(f"  Task drafts created:   {s.total_task_drafts}")
        print(f"  Activations created:   {s.activations_created}")
        print(f"  Activations failed:    {s.activations_failed}")
        if s.ambiguous_tactics:
            print(f"  Ambiguous tactics:     {s.ambiguous_tactics}")
        if s.no_eligible_cluster:
            print(f"  No eligible cluster:   {s.no_eligible_cluster}")
        if s.capacity_blocked:
            print(f"  Capacity blocked:      {s.capacity_blocked}")
        if s.explosion_review:
            print(f"  Explosion review:      {s.explosion_review}")
        if s.overlap_review:
            print(f"  Overlap review:        {s.overlap_review}")
        if s.weak_provenance:
            print(f"  Weak provenance:       {s.weak_provenance}")


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _save_json(path: Path, data: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def _extract_req_ids(requirements: list[str]) -> list[str]:
    """Extract FR/NFR IDs from requirement text."""
    ids: list[str] = []
    for req in requirements:
        ids.extend(_REQ_ID_RE.findall(req))
    return list(dict.fromkeys(ids))  # dedupe preserving order
