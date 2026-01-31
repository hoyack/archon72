#!/usr/bin/env python3
"""Result submission proof — submit a result or problem report for an ACCEPTED task.

Reads the activation manifest, hydrates governance state,
transitions ACCEPTED → IN_PROGRESS, then exercises TaskResultService
to submit a result (IN_PROGRESS → REPORTED) or a problem report
(stays IN_PROGRESS).

Usage:
    # Submit a "blocked" problem report (minimum viable result)
    python scripts/run_result_submission.py --task-ref TASK-ZEPA-001a --action problem --category blocked --description "Waiting on cluster-43 security review"

    # Submit a completed result
    python scripts/run_result_submission.py --task-ref TASK-ZEPA-001a --action result --output '{"status": "complete", "artifact_ref": "D-CONF-001-v1"}'

    # List ACCEPTED tasks ready for work
    python scripts/run_result_submission.py --action list
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID, uuid4

from src.application.ports.governance.task_result_port import ProblemCategory
from src.application.services.governance.task_result_service import TaskResultService
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


async def hydrate_workable_tasks(
    manifest_path: Path,
    task_state_port: InMemoryTaskStatePort,
) -> dict[str, dict]:
    """Load ACCEPTED and IN_PROGRESS tasks from manifest into in-memory task state.

    Returns a lookup of task_ref -> manifest entry (with injected task_id).
    """
    with open(manifest_path) as f:
        entries = json.load(f)

    status_map = {
        "ACCEPTED": TaskStatus.ACCEPTED,
        "IN_PROGRESS": TaskStatus.IN_PROGRESS,
    }

    lookup: dict[str, dict] = {}
    for entry in entries:
        task_status = status_map.get(entry["status"])
        if task_status is None:
            continue

        task_id = uuid4()
        cluster_id = entry["cluster_id"]

        task = TaskState(
            task_id=task_id,
            earl_id="earl-bridge",
            cluster_id=cluster_id,
            current_status=task_status,
            created_at=datetime.now(timezone.utc) - timedelta(minutes=10),
            state_entered_at=datetime.now(timezone.utc) - timedelta(minutes=2),
            ttl=timedelta(hours=72),
        )
        task_state_port._tasks[task_id] = task

        entry["_task_id"] = str(task_id)
        lookup[entry["task_ref"]] = entry

    return lookup


async def start_work(
    task_id: UUID,
    cluster_id: str,
    task_state_port: InMemoryTaskStatePort,
    time_authority: SimpleTimeAuthority,
) -> TaskState:
    """Transition a task from ACCEPTED → IN_PROGRESS.

    This is the "start work" step before result submission.
    No dedicated service exists for this transition — it's a
    direct state machine operation.
    """
    task = await task_state_port.get_task(task_id)
    now = time_authority.now()
    new_task = task.transition(
        new_status=TaskStatus.IN_PROGRESS,
        transition_time=now,
        actor_id=cluster_id,
    )
    await task_state_port.save_task(new_task)
    return new_task


async def handle_submit_result(
    args: argparse.Namespace,
    task_id: UUID,
    cluster_id: str,
    result_svc: TaskResultService,
) -> str:
    """Submit a completed result and return new manifest status."""
    print("\n--- Step 2: Submit result (IN_PROGRESS → REPORTED) ---")
    try:
        output = json.loads(args.output)
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON in --output: {e}")
        raise SystemExit(1) from e

    submission = await result_svc.submit_result(
        task_id=task_id, cluster_id=cluster_id, output=output
    )

    print(f"\n{'=' * 60}")
    print(f"Result Submission: {args.task_ref}")
    print(f"{'=' * 60}")
    print(f"  Success:    {submission.success}")
    print(f"  New Status: {submission.new_status}")
    print(f"  Message:    {submission.message}")
    print(f"  Output:     {json.dumps(submission.result.output, indent=2)}")
    return "REPORTED"


async def handle_submit_problem(
    args: argparse.Namespace,
    task_id: UUID,
    cluster_id: str,
    result_svc: TaskResultService,
) -> str:
    """Submit a problem report and return new manifest status."""
    print("\n--- Step 2: Submit problem report (IN_PROGRESS → IN_PROGRESS) ---")
    category = ProblemCategory(args.category)

    submission = await result_svc.submit_problem_report(
        task_id=task_id,
        cluster_id=cluster_id,
        category=category,
        description=args.description,
    )

    print(f"\n{'=' * 60}")
    print(f"Problem Report: {args.task_ref}")
    print(f"{'=' * 60}")
    print(f"  Success:    {submission.success}")
    print(f"  New Status: {submission.new_status}")
    print(f"  Message:    {submission.message}")
    print(f"  Category:   {submission.result.category.value}")
    print(f"  Description: {submission.result.description}")
    return "IN_PROGRESS"


def update_manifest(
    manifest_path: Path, task_ref: str, new_status: str, verbose: bool
) -> None:
    """Update the manifest file with new task status."""
    with open(manifest_path) as f:
        all_entries = json.load(f)

    for e in all_entries:
        if e["task_ref"] == task_ref:
            e["status"] = new_status

    with open(manifest_path, "w") as f:
        json.dump(all_entries, f, indent=2)

    if verbose:
        print(f"\nManifest updated: {manifest_path} ({task_ref} → {new_status})")


async def main() -> int:
    parser = argparse.ArgumentParser(description="Result submission proof")
    parser.add_argument("--task-ref", help="Task reference (e.g., TASK-ZEPA-001a)")
    parser.add_argument(
        "--action",
        choices=["result", "problem", "list"],
        required=True,
        help="Submission action to perform",
    )
    parser.add_argument(
        "--output",
        help='JSON string for result output (e.g., \'{"status": "complete"}\')',
        default='{"status": "blocked", "blocker": "pending_review"}',
    )
    parser.add_argument(
        "--category",
        choices=[c.value for c in ProblemCategory],
        default="blocked",
        help="Problem category (for --action problem)",
    )
    parser.add_argument(
        "--description",
        help="Problem description (for --action problem)",
        default="Task blocked — awaiting upstream dependency",
    )
    parser.add_argument(
        "--manifest", help="Path to activation_manifest.json (auto-detect if omitted)"
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    # Find manifest
    manifest_path = Path(args.manifest) if args.manifest else find_latest_manifest()
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
        ledger=ledger, time_authority=time_authority
    )
    result_svc = TaskResultService(
        task_state_port=task_state_port,
        ledger_port=ledger,
        two_phase_emitter=two_phase_emitter,
        time_authority=time_authority,
    )

    # Hydrate ACCEPTED and IN_PROGRESS tasks from manifest
    lookup = await hydrate_workable_tasks(manifest_path, task_state_port)
    if args.verbose:
        print(f"Hydrated {len(lookup)} workable tasks from manifest")

    # --- Action: list ---
    if args.action == "list":
        return _handle_list(lookup)

    # --- Action: result / problem ---
    if not args.task_ref:
        print("ERROR: --task-ref required for result/problem")
        return 1
    if args.task_ref not in lookup:
        print(
            f"ERROR: {args.task_ref} not found in manifest (or not ACCEPTED/IN_PROGRESS)"
        )
        print(f"Available: {', '.join(sorted(lookup.keys()))}")
        return 1

    entry = lookup[args.task_ref]
    task_id = UUID(entry["_task_id"])
    cluster_id = entry["cluster_id"]

    if args.verbose:
        print(f"\nTask:    {args.task_ref}")
        print(f"Cluster: {cluster_id}")
        print(f"Status:  {entry['status']}")
        print(f"Action:  {args.action}")

    # Step 1: Ensure task is IN_PROGRESS
    current_task = await task_state_port.get_task(task_id)
    if current_task.current_status == TaskStatus.ACCEPTED:
        print("\n--- Step 1: Start work (ACCEPTED → IN_PROGRESS) ---")
        ip = await start_work(task_id, cluster_id, task_state_port, time_authority)
        print(f"  Task state: {ip.current_status.value}")
    elif current_task.current_status == TaskStatus.IN_PROGRESS:
        print("\n--- Step 1: Already IN_PROGRESS (skipped) ---")
    else:
        print(f"ERROR: Task is in {current_task.current_status.value} — cannot submit")
        return 1

    # Step 2: Submit
    if args.action == "result":
        new_status = await handle_submit_result(args, task_id, cluster_id, result_svc)
    else:
        new_status = await handle_submit_problem(args, task_id, cluster_id, result_svc)

    # Show ledger events
    if args.verbose and ledger.events:
        print(f"\nGovernance ledger ({len(ledger.events)} events):")
        for evt in ledger.events:
            print(f"  [{evt.sequence}] {evt.event_type}  actor={evt.actor_id}")

    update_manifest(manifest_path, args.task_ref, new_status, args.verbose)
    return 0


def _handle_list(lookup: dict[str, dict]) -> int:
    """Print workable tasks and return exit code."""
    if not lookup:
        print("No ACCEPTED or IN_PROGRESS tasks in manifest.")
        print(
            "Run consent first: python scripts/run_cluster_consent.py --action accept ..."
        )
        return 0
    print("\nWorkable tasks (ACCEPTED / IN_PROGRESS):")
    for ref, entry in lookup.items():
        print(f"  {ref}  [{entry['status']}]")
        print(f"    cluster: {entry['cluster_id']}")
        print(f"    deliverable: {entry['deliverable_id']}")
        print(f"    requirements: {', '.join(entry['rfp_requirement_ids'])}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
