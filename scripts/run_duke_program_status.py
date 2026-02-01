#!/usr/bin/env python3
"""Duke program status — generate program-level visibility artifact.

Produces duke_program_status.json from the activation manifest,
giving Dukes (and Executive) honest program-level visibility into:

- tasks by state
- decline/timeout counts
- outstanding blockers
- capacity gaps
- what cannot proceed

This is NOT a dashboard. It's an artifact that forces visibility upward.

Usage:
    python scripts/run_duke_program_status.py -v
    python scripts/run_duke_program_status.py --manifest path/to/activation_manifest.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


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


def load_bridge_summary(manifest_path: Path) -> dict | None:
    """Load bridge_summary.json if it exists alongside the manifest."""
    summary_path = manifest_path.parent / "bridge_summary.json"
    if summary_path.exists():
        with open(summary_path) as f:
            return json.load(f)
    return None


def load_blockers(manifest_path: Path) -> list[dict]:
    """Load blocker artifacts from the blockers directory."""
    blocker_dir = manifest_path.parent / "blockers"
    if not blocker_dir.exists():
        return []
    blockers = []
    for path in sorted(blocker_dir.glob("blocker_*.json")):
        with open(path) as f:
            blockers.append(json.load(f))
    return blockers


def build_program_status(manifest_path: Path) -> dict:
    """Build the Duke program status artifact from manifest + related files."""
    with open(manifest_path) as f:
        entries = json.load(f)

    bridge_summary = load_bridge_summary(manifest_path)
    blockers = load_blockers(manifest_path)

    # --- Tasks by state ---
    status_counts = Counter(e["status"] for e in entries)
    tasks_by_state: dict[str, list[str]] = {}
    for entry in entries:
        tasks_by_state.setdefault(entry["status"], []).append(entry["task_ref"])

    # --- Tasks by cluster ---
    tasks_by_cluster: dict[str, list[dict]] = {}
    for entry in entries:
        cid = entry["cluster_id"]
        tasks_by_cluster.setdefault(cid, []).append(
            {"task_ref": entry["task_ref"], "status": entry["status"]}
        )

    # --- Decline/refusal count ---
    declined_count = status_counts.get("DECLINED", 0)
    declined_tasks = [e["task_ref"] for e in entries if e["status"] == "DECLINED"]

    # --- Stale routed (still awaiting consent) ---
    routed_tasks = [e for e in entries if e["status"] == "ROUTED"]

    # --- Terminal tasks ---
    terminal_statuses = {"COMPLETED", "DECLINED", "QUARANTINED", "NULLIFIED"}
    terminal_count = sum(status_counts.get(s, 0) for s in terminal_statuses)

    # --- Active tasks (non-terminal) ---
    active_count = len(entries) - terminal_count

    # --- What cannot proceed ---
    cannot_proceed: list[dict] = []

    # Declined tasks cannot proceed (need re-routing or scope revision)
    for task_ref in declined_tasks:
        cannot_proceed.append(
            {
                "task_ref": task_ref,
                "reason": "DECLINED — cluster refused, needs re-routing or scope revision",
            }
        )

    # Stale routed tasks (awaiting consent)
    for entry in routed_tasks:
        cannot_proceed.append(
            {
                "task_ref": entry["task_ref"],
                "reason": f"ROUTED but not yet accepted — awaiting cluster {entry['cluster_id']} consent",
            }
        )

    # Escalated blockers
    for blocker in blockers:
        for tid in blocker.get("affected_task_ids", []):
            cannot_proceed.append(
                {
                    "task_ref": tid,
                    "reason": f"BLOCKER [{blocker['blocker_type']}]: {blocker['summary']}",
                    "blocker_id": blocker["report_id"],
                }
            )

    # --- Capacity assessment ---
    unique_clusters = set(e["cluster_id"] for e in entries)
    cluster_acceptance = {}
    for cid in unique_clusters:
        cluster_tasks = [e for e in entries if e["cluster_id"] == cid]
        total = len(cluster_tasks)
        accepted = sum(
            1
            for e in cluster_tasks
            if e["status"]
            in {"ACCEPTED", "IN_PROGRESS", "REPORTED", "COMPLETED", "AGGREGATED"}
        )
        declined = sum(1 for e in cluster_tasks if e["status"] == "DECLINED")
        cluster_acceptance[cid] = {
            "total_tasks": total,
            "accepted": accepted,
            "declined": declined,
            "pending": total - accepted - declined,
            "acceptance_rate": round(accepted / total, 2) if total > 0 else 0.0,
        }

    # --- Assemble artifact ---
    now = datetime.now(timezone.utc)
    status = {
        "schema_version": "1.0",
        "artifact_type": "duke_program_status",
        "generated_at": now.isoformat(),
        "manifest_path": str(manifest_path),
        "program_summary": {
            "total_tasks": len(entries),
            "active_tasks": active_count,
            "terminal_tasks": terminal_count,
            "tasks_by_state": dict(status_counts),
            "decline_count": declined_count,
            "blocker_count": len(blockers),
            "cannot_proceed_count": len(cannot_proceed),
        },
        "tasks_by_state": tasks_by_state,
        "tasks_by_cluster": tasks_by_cluster,
        "cluster_capacity": cluster_acceptance,
        "cannot_proceed": cannot_proceed,
        "blocker_reports": blockers,
    }

    # Include bridge summary if available
    if bridge_summary:
        status["bridge_summary"] = bridge_summary

    return status


async def main() -> int:
    parser = argparse.ArgumentParser(description="Duke program status artifact")
    parser.add_argument("--manifest", help="Path to activation_manifest.json")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    manifest_path = Path(args.manifest) if args.manifest else find_latest_manifest()
    if manifest_path is None or not manifest_path.exists():
        print("ERROR: No activation_manifest.json found.")
        return 1

    if args.verbose:
        print(f"Manifest: {manifest_path}")

    status = build_program_status(manifest_path)

    # Write artifact
    output_path = manifest_path.parent / "duke_program_status.json"
    with open(output_path, "w") as f:
        json.dump(status, f, indent=2)

    # Print summary
    ps = status["program_summary"]
    print(f"\n{'=' * 60}")
    print("Duke Program Status")
    print(f"{'=' * 60}")
    print(f"  Total tasks:      {ps['total_tasks']}")
    print(f"  Active:           {ps['active_tasks']}")
    print(f"  Terminal:         {ps['terminal_tasks']}")
    print(f"  Declined:         {ps['decline_count']}")
    print(f"  Blockers:         {ps['blocker_count']}")
    print(f"  Cannot proceed:   {ps['cannot_proceed_count']}")

    print("\n  Tasks by state:")
    for state, refs in status["tasks_by_state"].items():
        print(f"    {state:15s}  {', '.join(refs)}")

    if status["cannot_proceed"]:
        print("\n  Cannot proceed:")
        for item in status["cannot_proceed"]:
            print(f"    {item['task_ref']:20s}  {item['reason']}")

    print("\n  Cluster capacity:")
    for cid, cap in status["cluster_capacity"].items():
        print(
            f"    {cid[:20]:20s}  "
            f"accepted={cap['accepted']}/{cap['total_tasks']}  "
            f"declined={cap['declined']}  "
            f"rate={cap['acceptance_rate']}"
        )

    print(f"\n  Artifact: {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
