#!/usr/bin/env python3
"""Earl aggregation — aggregate multi-task results without judgment.

Sprint: Aggregation Without Judgment

This script exercises the aggregation service against the activation
manifest. It groups tasks by deliverable, checks requirement coverage,
detects multi-cluster conflicts, and produces:

- aggregation_result.json (Duke-readable coverage artifact)
- conflict artifact + blocker (if conflicts detected)
- settlement decision: COMPLETED (clean) or escalated (conflicts/gaps)

Usage:
    python scripts/run_earl_aggregation.py -v
    python scripts/run_earl_aggregation.py --manifest path/to/activation_manifest.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from src.application.services.governance.aggregation_service import (
    TaskEntry,
    aggregate_deliverable,
    collect_requirement_ids,
    group_tasks_by_deliverable,
    needs_aggregation,
)
from src.application.services.governance.two_phase_event_emitter import (
    TwoPhaseEventEmitter,
)
from src.application.services.governance.two_phase_execution import TwoPhaseExecution
from src.domain.governance.events.event_envelope import GovernanceEvent
from src.domain.governance.events.schema_versions import CURRENT_SCHEMA_VERSION
from src.domain.models.aggregation import (
    AcceptanceTestResult,
    AggregationDisposition,
    AggregationResult,
    VerificationStatus,
)
from src.domain.models.execution_program import (
    AdminBlockerSeverity,
    AdministrativeBlockerReport,
    BlockerType,
    RequestedAction,
)
from src.infrastructure.adapters.governance.best_effort_evidence_verifier import (
    BestEffortEvidenceVerifier,
)
from src.infrastructure.adapters.governance.in_memory_adapters import (
    InMemoryGovernanceLedger,
    SimpleTimeAuthority,
)


def find_latest_manifest() -> Path | None:
    """Find the most recent activation_manifest.json."""
    bmad_out = Path("_bmad-output/rfp")
    if not bmad_out.exists():
        return None
    sessions = sorted(bmad_out.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
    for session in sessions:
        mandates = session / "mandates"
        if not mandates.exists():
            continue
        for mandate in sorted(
            mandates.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True
        ):
            manifest = mandate / "execution_bridge" / "activation_manifest.json"
            if manifest.exists():
                return manifest
    return None


def _extract_evidence(
    entry: dict[str, Any],
    manifest_dir: Path,
) -> tuple[tuple[str, ...], tuple[AcceptanceTestResult, ...]]:
    """Extract evidence from a manifest entry or its result artifact.

    Evidence sources (checked in order):
    1. Inline: entry["artifact_refs"] and entry["acceptance_test_results"]
    2. Result output: entry["result_output"]["evidence_refs"] etc.
    3. Standalone: execution/tars/tar-{task_ref}.json alongside manifest

    Returns (artifact_refs, acceptance_results) tuples.
    """
    artifact_refs: list[str] = []
    acceptance_results: list[AcceptanceTestResult] = []

    # Source 1: inline on manifest entry
    artifact_refs.extend(entry.get("artifact_refs", []))
    for atr in entry.get("acceptance_test_results", []):
        acceptance_results.append(
            AcceptanceTestResult(
                test=atr.get("test", ""),
                passed=atr.get("passed", False),
                notes=atr.get("notes", ""),
            )
        )

    # Source 2: nested in result_output
    result_output = entry.get("result_output") or {}
    artifact_refs.extend(result_output.get("evidence_refs", []))
    artifact_refs.extend(result_output.get("artifact_refs", []))
    for atr in result_output.get("acceptance_test_results", []):
        acceptance_results.append(
            AcceptanceTestResult(
                test=atr.get("test", ""),
                passed=atr.get("passed", False),
                notes=atr.get("notes", ""),
            )
        )

    # Source 3: standalone task result artifact
    task_ref = entry.get("task_ref", "")
    tar_dir = manifest_dir.parent / "execution" / "tars"
    if tar_dir.exists() and task_ref:
        for tar_file in tar_dir.iterdir():
            if tar_file.suffix == ".json":
                try:
                    tar_data = json.loads(tar_file.read_text())
                    refs = tar_data.get("references", {})
                    if (
                        refs.get("task_id") == task_ref
                        or refs.get("task_ref") == task_ref
                    ):
                        # Extract from TAR deliverables
                        for deliv in tar_data.get("task", {}).get("deliverables", []):
                            if deliv.get("id"):
                                artifact_refs.append(
                                    f"tar:{tar_file.name}:{deliv['id']}"
                                )
                except (json.JSONDecodeError, KeyError):
                    continue

    return tuple(artifact_refs), tuple(acceptance_results)


def load_reportable_tasks(manifest_path: Path) -> list[TaskEntry]:
    """Load tasks that have reached REPORTED or COMPLETED status.

    Extracts evidence (artifact_refs, acceptance_test_results) from
    manifest entries and adjacent result artifacts. Tasks without
    evidence will produce UNVERIFIED disposition during aggregation.
    """
    with open(manifest_path) as f:
        entries = json.load(f)

    reportable_statuses = {"REPORTED", "COMPLETED", "AGGREGATED"}
    tasks: list[TaskEntry] = []
    manifest_dir = manifest_path.parent

    for entry in entries:
        if entry["status"] not in reportable_statuses:
            continue

        artifact_refs, acceptance_results = _extract_evidence(entry, manifest_dir)

        tasks.append(
            TaskEntry(
                task_ref=entry["task_ref"],
                deliverable_id=entry.get("deliverable_id", ""),
                cluster_id=entry.get("cluster_id", ""),
                rfp_requirement_ids=tuple(entry.get("rfp_requirement_ids", [])),
                status=entry["status"],
                artifact_refs=artifact_refs,
                acceptance_results=acceptance_results,
            )
        )

    return tasks


async def _settle_deliverable(
    result: AggregationResult,
    deliverable_id: str,
    group_tasks: list[TaskEntry],
    manifest_path: Path,
    emitter: TwoPhaseEventEmitter,
    ledger: InMemoryGovernanceLedger,
    time_authority: SimpleTimeAuthority,
) -> bool:
    """Settle a single deliverable based on aggregation disposition.

    Returns True if completed, False if escalated.
    """
    now = time_authority.now()

    if result.disposition == AggregationDisposition.COMPLETE:
        async with TwoPhaseExecution(
            emitter=emitter,
            operation_type="aggregation.settlement.complete",
            actor_id="earl-bridge",
            target_entity_id=deliverable_id,
            intent_payload={
                "deliverable_id": deliverable_id,
                "disposition": "COMPLETE",
            },
        ) as execution:
            event = GovernanceEvent.create(
                event_id=uuid4(),
                event_type="executive.deliverable.aggregation_complete",
                timestamp=now,
                actor_id="earl-bridge",
                trace_id=deliverable_id,
                payload={
                    "deliverable_id": deliverable_id,
                    "total_requirements": result.total_requirements,
                    "covered_count": result.covered_count,
                    "contributing_tasks": list(result.contributing_tasks),
                    "contributing_clusters": list(result.contributing_clusters),
                    "disposition": "COMPLETE",
                },
                schema_version=CURRENT_SCHEMA_VERSION,
            )
            await ledger.append_event(event)
            execution.set_result({"disposition": "COMPLETE"})
        print("  Settlement: COMPLETED (all requirements covered)")
        return True

    # Escalation paths — build blocker for each
    if result.disposition == AggregationDisposition.CONFLICTED:
        blocker = _build_conflict_blocker(result, deliverable_id, group_tasks, now)
        event_type = "administrative.aggregation.conflict_escalated"
        payload = {
            "deliverable_id": deliverable_id,
            "conflict_count": len(result.conflicts),
            "conflicted_requirements": [c.req_id for c in result.conflicts],
            "disposition": "CONFLICTED",
        }
        label = "conflict blocker"
    elif result.disposition == AggregationDisposition.UNVERIFIED:
        unverified_reqs = [
            c.req_id for c in result.coverage_map if c.task_refs and not c.has_evidence
        ]
        blocker = AdministrativeBlockerReport(
            report_id=str(uuid4()),
            program_id="program-bridge",
            execution_plan_id="plan-bridge",
            summary=(
                f"Aggregation unverified: {len(unverified_reqs)} "
                f"requirement(s) covered by task metadata but lack "
                f"evidence for deliverable {deliverable_id}. "
                f"Unverified: {', '.join(unverified_reqs)}"
            ),
            blocker_type=BlockerType.REQUIREMENTS_AMBIGUOUS,
            severity=AdminBlockerSeverity.MINOR,
            affected_task_ids=[t.task_ref for t in group_tasks],
            requested_action=RequestedAction.CLARIFY,
            created_at=now.isoformat(),
        )
        event_type = "administrative.aggregation.unverified_escalated"
        payload = {
            "deliverable_id": deliverable_id,
            "unverified_count": len(unverified_reqs),
            "unverified_requirements": unverified_reqs,
            "disposition": "UNVERIFIED",
        }
        label = "evidence gap blocker"
    else:
        blocker = AdministrativeBlockerReport(
            report_id=str(uuid4()),
            program_id="program-bridge",
            execution_plan_id="plan-bridge",
            summary=(
                f"Aggregation incomplete: {len(result.missing_requirements)} "
                f"requirement(s) not covered for deliverable {deliverable_id}. "
                f"Missing: {', '.join(result.missing_requirements)}"
            ),
            blocker_type=BlockerType.REQUIREMENTS_AMBIGUOUS,
            severity=AdminBlockerSeverity.MAJOR,
            affected_task_ids=[t.task_ref for t in group_tasks],
            requested_action=RequestedAction.REVISE_PLAN,
            created_at=now.isoformat(),
        )
        event_type = "administrative.aggregation.incomplete_escalated"
        payload = {
            "deliverable_id": deliverable_id,
            "missing_count": len(result.missing_requirements),
            "missing_requirements": list(result.missing_requirements),
            "disposition": "INCOMPLETE",
        }
        label = "coverage gap blocker"

    # Save blocker and emit event
    blocker_dir = manifest_path.parent / "blockers"
    blocker_dir.mkdir(exist_ok=True)
    blocker_path = blocker_dir / f"blocker_{deliverable_id}.json"
    with open(blocker_path, "w") as f:
        json.dump(blocker.to_dict(), f, indent=2)

    payload["blocker_report_id"] = blocker.report_id
    async with TwoPhaseExecution(
        emitter=emitter,
        operation_type=f"aggregation.settlement.{result.disposition.value.lower()}",
        actor_id="earl-bridge",
        target_entity_id=deliverable_id,
        intent_payload={
            "deliverable_id": deliverable_id,
            "disposition": result.disposition.value,
        },
    ) as execution:
        event = GovernanceEvent.create(
            event_id=uuid4(),
            event_type=event_type,
            timestamp=now,
            actor_id="earl-bridge",
            trace_id=deliverable_id,
            payload=payload,
            schema_version=CURRENT_SCHEMA_VERSION,
        )
        await ledger.append_event(event)
        execution.set_result(
            {"disposition": result.disposition.value, "blocker_id": blocker.report_id}
        )

    print(f"  Settlement: ESCALATED ({label}: {blocker_path})")
    return False


def _build_conflict_blocker(
    result: AggregationResult,
    deliverable_id: str,
    group_tasks: list[TaskEntry],
    now: datetime,
) -> AdministrativeBlockerReport:
    """Build a conflict blocker report."""
    return AdministrativeBlockerReport(
        report_id=str(uuid4()),
        program_id="program-bridge",
        execution_plan_id="plan-bridge",
        summary=(
            f"Aggregation conflict: {len(result.conflicts)} "
            f"requirement(s) covered by multiple clusters for "
            f"deliverable {deliverable_id}. Cannot mechanically "
            f"determine authoritative result."
        ),
        blocker_type=BlockerType.CONSTRAINT_CONFLICT,
        severity=AdminBlockerSeverity.MAJOR,
        affected_task_ids=[t.task_ref for t in group_tasks],
        requested_action=RequestedAction.CLARIFY,
        created_at=now.isoformat(),
    )


def _print_deliverable_report(
    result: AggregationResult,
    group_tasks: list[TaskEntry],
) -> None:
    """Print deliverable aggregation report."""
    print(f"  Tasks: {', '.join(t.task_ref for t in group_tasks)}")
    print(f"  Clusters: {', '.join(sorted({t.cluster_id for t in group_tasks}))}")
    print(f"  Multi-cluster: {needs_aggregation(group_tasks)}")
    print(f"  Total requirements: {result.total_requirements}")
    print(f"  Covered: {result.covered_count}/{result.total_requirements}")
    print(f"  Disposition: {result.disposition.value}")

    if result.missing_requirements:
        print(f"  Missing: {', '.join(result.missing_requirements)}")
    if result.conflicts:
        print(f"  Conflicts: {len(result.conflicts)}")
        for conflict in result.conflicts:
            print(f"    {conflict.req_id}: {conflict.reason}")

    # Evidence and verification summary
    evidenced = [c for c in result.coverage_map if c.has_evidence]
    unevidenced = [c for c in result.coverage_map if c.task_refs and not c.has_evidence]
    all_ev = [e for c in result.coverage_map for e in c.evidence]
    v_ok = sum(
        1 for e in all_ev if e.verification_status == VerificationStatus.VERIFIED_OK
    )
    v_fail = sum(
        1 for e in all_ev if e.verification_status == VerificationStatus.VERIFIED_FAILED
    )
    v_unv = sum(
        1 for e in all_ev if e.verification_status == VerificationStatus.UNVERIFIABLE
    )
    v_na = sum(
        1 for e in all_ev if e.verification_status == VerificationStatus.NOT_ATTEMPTED
    )
    print(f"  Evidence: {len(evidenced)} with proof, {len(unevidenced)} without")
    if all_ev:
        print(
            f"  Verification: {v_ok} ok, {v_unv} unverifiable, "
            f"{v_fail} failed, {v_na} not attempted"
        )


def _print_coverage_map(result: AggregationResult) -> None:
    """Print verbose coverage map with verification status."""
    print("\n  Coverage map:")
    for cov in result.coverage_map:
        multi = " [MULTI-CLUSTER]" if cov.is_multi_cluster else ""
        if not cov.task_refs:
            ev_tag = " [UNCOVERED]"
        elif not cov.evidence:
            ev_tag = " [NO-EVIDENCE]"
        else:
            statuses = {e.verification_status for e in cov.evidence}
            if VerificationStatus.VERIFIED_FAILED in statuses:
                ev_tag = " [VERIFIED_FAILED]"
            elif all(s == VerificationStatus.VERIFIED_OK for s in statuses):
                ev_tag = " [VERIFIED_OK]"
            elif any(s == VerificationStatus.NOT_ATTEMPTED for s in statuses):
                ev_tag = " [NO-EVIDENCE]" if not cov.has_evidence else " [NOT_VERIFIED]"
            else:
                ev_tag = " [UNVERIFIABLE]"
        print(
            f"    {cov.req_id:20s}  "
            f"tasks={', '.join(cov.task_refs):30s}  "
            f"clusters={', '.join(cov.cluster_ids)}{multi}{ev_tag}"
        )


async def process_aggregation(
    manifest_path: Path,
    ledger: InMemoryGovernanceLedger,
    emitter: TwoPhaseEventEmitter,
    time_authority: SimpleTimeAuthority,
    verbose: bool,
) -> int:
    """Run aggregation for all deliverables in the manifest."""
    tasks = load_reportable_tasks(manifest_path)

    if not tasks:
        print("No REPORTED/COMPLETED tasks found in manifest.")
        return 0

    # Wire evidence verifier (best-effort, resolves paths from manifest dir)
    verifier = BestEffortEvidenceVerifier(base_dir=manifest_path.parent)

    groups = group_tasks_by_deliverable(tasks)
    print(f"\nDeliverables to aggregate: {len(groups)}")

    total_completed = 0
    total_escalated = 0

    for deliverable_id, group_tasks in groups.items():
        print(f"\n{'=' * 60}")
        print(f"Deliverable: {deliverable_id}")
        print(f"{'=' * 60}")

        all_req_ids = collect_requirement_ids(group_tasks)
        result = aggregate_deliverable(
            deliverable_id=deliverable_id,
            all_requirement_ids=all_req_ids,
            tasks=group_tasks,
            verifier=verifier,
        )

        _print_deliverable_report(result, group_tasks)

        # Save aggregation artifact
        artifact_dir = manifest_path.parent
        artifact_path = artifact_dir / f"aggregation_{deliverable_id}.json"
        with open(artifact_path, "w") as f:
            json.dump(result.to_dict(), f, indent=2)
        print(f"  Artifact: {artifact_path}")

        # Settlement
        settled = await _settle_deliverable(
            result,
            deliverable_id,
            group_tasks,
            manifest_path,
            emitter,
            ledger,
            time_authority,
        )
        if settled:
            total_completed += 1
        else:
            total_escalated += 1

        if verbose:
            _print_coverage_map(result)

    # Summary
    print(f"\n{'=' * 60}")
    print("Aggregation Summary")
    print(f"{'=' * 60}")
    print(f"  Deliverables processed: {len(groups)}")
    print(f"  Completed:              {total_completed}")
    print(f"  Escalated:              {total_escalated}")
    print(f"  Ledger events:          {len(ledger.events)}")

    if verbose and ledger.events:
        print("\n  Ledger events:")
        for evt in ledger.events:
            print(f"    [{evt.sequence:3d}] {evt.event_type}")

    return 0


async def main() -> int:
    parser = argparse.ArgumentParser(description="Earl aggregation proof")
    parser.add_argument("--manifest", help="Path to activation_manifest.json")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    manifest_path = Path(args.manifest) if args.manifest else find_latest_manifest()
    if manifest_path is None or not manifest_path.exists():
        print("ERROR: No activation_manifest.json found.")
        return 1

    if args.verbose:
        print(f"Manifest: {manifest_path}")

    # Wire governance
    ledger = InMemoryGovernanceLedger()
    time_authority = SimpleTimeAuthority()
    emitter = TwoPhaseEventEmitter(ledger=ledger, time_authority=time_authority)

    return await process_aggregation(
        manifest_path, ledger, emitter, time_authority, args.verbose
    )


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
