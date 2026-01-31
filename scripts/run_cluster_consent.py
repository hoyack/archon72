#!/usr/bin/env python3
"""Cluster consent proof — accept or decline a ROUTED task.

Reads the activation manifest, hydrates governance state from it,
then exercises TaskConsentService.accept_task() or decline_task()
on a specific task activation.

Usage:
    # Accept TASK-ZEPA-001a
    python scripts/run_cluster_consent.py --task-ref TASK-ZEPA-001a --action accept

    # Decline TASK-ZEPA-001a
    python scripts/run_cluster_consent.py --task-ref TASK-ZEPA-001a --action decline

    # List pending tasks for a cluster
    python scripts/run_cluster_consent.py --cluster-id a1b2c3d4-4201-4a01-b001-000000000042 --action list
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID, uuid4

from src.application.services.governance.task_consent_service import (
    TaskConsentService,
)
from src.application.services.governance.two_phase_event_emitter import (
    TwoPhaseEventEmitter,
)
from src.domain.governance.task.task_state import TaskState, TaskStatus
from src.infrastructure.adapters.governance.in_memory_adapters import (
    InMemoryGovernanceLedger,
    InMemoryTaskStatePort,
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


async def hydrate_tasks(
    manifest_path: Path,
    task_state_port: InMemoryTaskStatePort,
) -> dict[str, dict]:
    """Load ROUTED tasks from manifest into in-memory task state.

    Returns a lookup of task_ref -> manifest entry (with injected task_id).
    """
    with open(manifest_path) as f:
        entries = json.load(f)

    lookup: dict[str, dict] = {}
    for entry in entries:
        if entry["status"] != "ROUTED":
            continue

        task_id = uuid4()
        cluster_id = entry["cluster_id"]

        # Create task directly in ROUTED state with cluster_id set
        task = TaskState(
            task_id=task_id,
            earl_id="earl-bridge",
            cluster_id=cluster_id,
            current_status=TaskStatus.ROUTED,
            created_at=datetime.now(timezone.utc) - timedelta(minutes=5),
            state_entered_at=datetime.now(timezone.utc) - timedelta(minutes=1),
            ttl=timedelta(hours=72),
        )
        task_state_port._tasks[task_id] = task

        entry["_task_id"] = str(task_id)
        lookup[entry["task_ref"]] = entry

    return lookup


async def main() -> int:
    parser = argparse.ArgumentParser(description="Cluster consent proof")
    parser.add_argument(
        "--task-ref",
        help="Task reference (e.g., TASK-ZEPA-001a)",
    )
    parser.add_argument(
        "--cluster-id",
        help="Cluster ID for listing pending tasks",
    )
    parser.add_argument(
        "--action",
        choices=["accept", "decline", "list"],
        required=True,
        help="Consent action to perform",
    )
    parser.add_argument(
        "--manifest",
        help="Path to activation_manifest.json (auto-detect if omitted)",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    # Find manifest
    if args.manifest:
        manifest_path = Path(args.manifest)
    else:
        manifest_path = find_latest_manifest()

    if manifest_path is None or not manifest_path.exists():
        print("ERROR: No activation_manifest.json found. Run the bridge first.")
        return 1

    if args.verbose:
        print(f"Manifest: {manifest_path}")

    # Wire governance services with in-memory adapters
    task_state_port = InMemoryTaskStatePort()
    ledger = InMemoryGovernanceLedger()
    time_authority = SimpleTimeAuthority()
    two_phase_emitter = TwoPhaseEventEmitter(
        ledger=ledger,
        time_authority=time_authority,
    )

    consent_svc = TaskConsentService(
        task_state_port=task_state_port,
        ledger_port=ledger,
        two_phase_emitter=two_phase_emitter,
        time_authority=time_authority,
    )

    # Hydrate ROUTED tasks from manifest
    lookup = await hydrate_tasks(manifest_path, task_state_port)

    if args.verbose:
        print(f"Hydrated {len(lookup)} ROUTED tasks from manifest")

    # --- Action: list ---
    if args.action == "list":
        cluster_id = args.cluster_id
        if not cluster_id:
            # Show all clusters with pending tasks
            clusters: dict[str, list[str]] = {}
            for ref, entry in lookup.items():
                cid = entry["cluster_id"]
                clusters.setdefault(cid, []).append(ref)
            print("\nPending tasks by cluster:")
            for cid, refs in clusters.items():
                print(f"  {cid}")
                for ref in refs:
                    print(f"    - {ref}")
            return 0

        pending = await consent_svc.get_pending_requests(cluster_id)
        if not pending:
            print(f"No pending tasks for cluster {cluster_id}")
            return 0
        print(f"\nPending tasks for {cluster_id}:")
        for p in pending:
            print(f"  task_id={p.task_id}  ttl_remaining={p.ttl_remaining}")
        return 0

    # --- Action: accept / decline ---
    if not args.task_ref:
        print("ERROR: --task-ref required for accept/decline")
        return 1

    if args.task_ref not in lookup:
        print(f"ERROR: {args.task_ref} not found in manifest (or not ROUTED)")
        print(f"Available: {', '.join(sorted(lookup.keys()))}")
        return 1

    entry = lookup[args.task_ref]
    task_id = UUID(entry["_task_id"])
    cluster_id = entry["cluster_id"]

    if args.verbose:
        print(f"\nTask:    {args.task_ref}")
        print(f"Cluster: {cluster_id}")
        print(f"Action:  {args.action}")

    if args.action == "accept":
        result = await consent_svc.accept_task(task_id=task_id, cluster_id=cluster_id)
    else:
        result = await consent_svc.decline_task(task_id=task_id, cluster_id=cluster_id)

    # Print result
    print(f"\n{'=' * 60}")
    print(f"Consent Result: {args.task_ref}")
    print(f"{'=' * 60}")
    print(f"  Success:    {result.success}")
    print(f"  Operation:  {result.operation}")
    print(f"  Task State: {result.task_state.current_status.value}")
    print(f"  Message:    {result.message}")

    # Show ledger events
    events = ledger.events
    if args.verbose and events:
        print(f"\nGovernance ledger ({len(events)} events):")
        for evt in events:
            print(f"  [{evt.sequence}] {evt.event_type}  actor={evt.actor_id}")

    # Update manifest file with new status
    with open(manifest_path) as f:
        all_entries = json.load(f)

    for e in all_entries:
        if e["task_ref"] == args.task_ref:
            e["status"] = result.task_state.current_status.value.upper()

    with open(manifest_path, "w") as f:
        json.dump(all_entries, f, indent=2)

    if args.verbose:
        print(f"\nManifest updated: {manifest_path}")

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
