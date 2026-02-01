#!/usr/bin/env python3
"""Earl settlement — accept, aggregate, or escalate a REPORTED task.

Exercises the settlement boundary where "a result exists" becomes
"the system acknowledged what it means."

Settlement decisions:
  accept    — REPORTED → COMPLETED (result is sufficient, single-cluster)
  aggregate — REPORTED → AGGREGATED (needs cross-cluster merge or review)
  escalate  — stays REPORTED, emits blocker event for Duke visibility

Usage:
    # Accept a reported result (direct completion)
    python scripts/run_earl_settlement.py --task-ref TASK-ZEPA-001a --decision accept

    # Mark for aggregation (multi-cluster or needs review)
    python scripts/run_earl_settlement.py --task-ref TASK-ZEPA-001a --decision aggregate

    # Escalate with blocker reason
    python scripts/run_earl_settlement.py --task-ref TASK-ZEPA-001a --decision escalate \\
        --blocker-type REQUIREMENTS_AMBIGUOUS --blocker-summary "Deliverable scope unclear"

    # List REPORTED tasks
    python scripts/run_earl_settlement.py --decision list
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID, uuid4

from src.application.services.governance.two_phase_event_emitter import (
    TwoPhaseEventEmitter,
)
from src.application.services.governance.two_phase_execution import TwoPhaseExecution
from src.domain.governance.events.event_envelope import GovernanceEvent
from src.domain.governance.events.schema_versions import CURRENT_SCHEMA_VERSION
from src.domain.governance.task.task_state import TaskState, TaskStatus
from src.domain.models.execution_program import (
    AdminBlockerSeverity,
    AdministrativeBlockerReport,
    BlockerType,
    RequestedAction,
)
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


def hydrate_reported_tasks(
    manifest_path: Path,
    task_state_port: InMemoryTaskStatePort,
) -> dict[str, dict]:
    """Load REPORTED tasks from manifest into in-memory task state."""
    with open(manifest_path) as f:
        entries = json.load(f)

    lookup: dict[str, dict] = {}
    for entry in entries:
        if entry["status"] != "REPORTED":
            continue

        task_id = uuid4()
        cluster_id = entry["cluster_id"]

        task = TaskState(
            task_id=task_id,
            earl_id="earl-bridge",
            cluster_id=cluster_id,
            current_status=TaskStatus.REPORTED,
            created_at=datetime.now(timezone.utc) - timedelta(minutes=30),
            state_entered_at=datetime.now(timezone.utc) - timedelta(minutes=5),
            ttl=timedelta(hours=72),
        )
        task_state_port._tasks[task_id] = task

        entry["_task_id"] = str(task_id)
        lookup[entry["task_ref"]] = entry

    return lookup


async def settle_accept(
    task_id: UUID,
    cluster_id: str,
    task_ref: str,
    task_state_port: InMemoryTaskStatePort,
    ledger: InMemoryGovernanceLedger,
    emitter: TwoPhaseEventEmitter,
    time_authority: SimpleTimeAuthority,
) -> str:
    """Accept result: REPORTED → COMPLETED."""
    async with TwoPhaseExecution(
        emitter=emitter,
        operation_type="task.settlement.accept",
        actor_id="earl-bridge",
        target_entity_id=str(task_id),
        intent_payload={"decision": "accept", "task_ref": task_ref},
    ) as execution:
        task = await task_state_port.get_task(task_id)
        now = time_authority.now()

        new_task = task.transition(
            new_status=TaskStatus.COMPLETED,
            transition_time=now,
            actor_id="earl-bridge",
        )
        await task_state_port.save_task(new_task)

        event = GovernanceEvent.create(
            event_id=uuid4(),
            event_type="executive.task.completed",
            timestamp=now,
            actor_id="earl-bridge",
            trace_id=str(task_id),
            payload={
                "task_id": str(task_id),
                "cluster_id": cluster_id,
                "task_ref": task_ref,
                "settlement_decision": "accept",
                "completed_at": now.isoformat(),
            },
            schema_version=CURRENT_SCHEMA_VERSION,
        )
        await ledger.append_event(event)
        execution.set_result({"new_status": "completed"})

    return "COMPLETED"


async def settle_aggregate(
    task_id: UUID,
    cluster_id: str,
    task_ref: str,
    task_state_port: InMemoryTaskStatePort,
    ledger: InMemoryGovernanceLedger,
    emitter: TwoPhaseEventEmitter,
    time_authority: SimpleTimeAuthority,
) -> str:
    """Mark for aggregation: REPORTED → AGGREGATED."""
    async with TwoPhaseExecution(
        emitter=emitter,
        operation_type="task.settlement.aggregate",
        actor_id="earl-bridge",
        target_entity_id=str(task_id),
        intent_payload={"decision": "aggregate", "task_ref": task_ref},
    ) as execution:
        task = await task_state_port.get_task(task_id)
        now = time_authority.now()

        new_task = task.transition(
            new_status=TaskStatus.AGGREGATED,
            transition_time=now,
            actor_id="earl-bridge",
        )
        await task_state_port.save_task(new_task)

        event = GovernanceEvent.create(
            event_id=uuid4(),
            event_type="executive.task.aggregated",
            timestamp=now,
            actor_id="earl-bridge",
            trace_id=str(task_id),
            payload={
                "task_id": str(task_id),
                "cluster_id": cluster_id,
                "task_ref": task_ref,
                "settlement_decision": "aggregate",
                "aggregated_at": now.isoformat(),
            },
            schema_version=CURRENT_SCHEMA_VERSION,
        )
        await ledger.append_event(event)
        execution.set_result({"new_status": "aggregated"})

    return "AGGREGATED"


async def settle_escalate(
    task_id: UUID,
    cluster_id: str,
    task_ref: str,
    blocker_type: str,
    blocker_summary: str,
    manifest_path: Path,
    ledger: InMemoryGovernanceLedger,
    emitter: TwoPhaseEventEmitter,
    time_authority: SimpleTimeAuthority,
) -> str:
    """Escalate: stays REPORTED, emits blocker event for Duke."""
    async with TwoPhaseExecution(
        emitter=emitter,
        operation_type="task.settlement.escalate",
        actor_id="earl-bridge",
        target_entity_id=str(task_id),
        intent_payload={"decision": "escalate", "task_ref": task_ref},
    ) as execution:
        now = time_authority.now()

        # Create blocker report artifact
        blocker = AdministrativeBlockerReport(
            report_id=str(uuid4()),
            program_id="program-bridge",
            execution_plan_id="plan-bridge",
            summary=blocker_summary,
            blocker_type=BlockerType(blocker_type),
            severity=AdminBlockerSeverity.MAJOR,
            affected_task_ids=[task_ref],
            requested_action=RequestedAction.CLARIFY,
            created_at=now.isoformat(),
        )

        # Save blocker artifact alongside manifest
        blocker_dir = manifest_path.parent / "blockers"
        blocker_dir.mkdir(exist_ok=True)
        blocker_path = blocker_dir / f"blocker_{task_ref}.json"
        with open(blocker_path, "w") as f:
            json.dump(blocker.to_dict(), f, indent=2)

        # Emit escalation event
        event = GovernanceEvent.create(
            event_id=uuid4(),
            event_type="administrative.blocker.escalated",
            timestamp=now,
            actor_id="earl-bridge",
            trace_id=str(task_id),
            payload={
                "task_id": str(task_id),
                "cluster_id": cluster_id,
                "task_ref": task_ref,
                "settlement_decision": "escalate",
                "blocker_report_id": blocker.report_id,
                "blocker_type": blocker_type,
                "blocker_summary": blocker_summary,
                "blocker_artifact": str(blocker_path),
                "escalated_at": now.isoformat(),
            },
            schema_version=CURRENT_SCHEMA_VERSION,
        )
        await ledger.append_event(event)
        execution.set_result({"escalated": True, "blocker_id": blocker.report_id})

    # Task stays REPORTED — escalation doesn't change state
    return "REPORTED"


def _handle_list(lookup: dict[str, dict]) -> int:
    """Print REPORTED tasks and return exit code."""
    if not lookup:
        print("No REPORTED tasks in manifest.")
        return 0
    print("\nREPORTED tasks awaiting settlement:")
    for ref, entry in lookup.items():
        print(f"  {ref}")
        print(f"    cluster: {entry['cluster_id']}")
        print(f"    deliverable: {entry['deliverable_id']}")
        print(f"    requirements: {', '.join(entry['rfp_requirement_ids'])}")
    return 0


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
    parser = argparse.ArgumentParser(description="Earl settlement proof")
    parser.add_argument("--task-ref", help="Task reference (e.g., TASK-ZEPA-001a)")
    parser.add_argument(
        "--decision",
        choices=["accept", "aggregate", "escalate", "list"],
        required=True,
        help="Settlement decision",
    )
    parser.add_argument(
        "--blocker-type",
        choices=[bt.value for bt in BlockerType],
        default="REQUIREMENTS_AMBIGUOUS",
        help="Blocker type (for --decision escalate)",
    )
    parser.add_argument(
        "--blocker-summary",
        default="Settlement escalated — requires Duke review",
        help="Blocker description (for --decision escalate)",
    )
    parser.add_argument("--manifest", help="Path to activation_manifest.json")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    # Find manifest
    manifest_path = Path(args.manifest) if args.manifest else find_latest_manifest()
    if manifest_path is None or not manifest_path.exists():
        print("ERROR: No activation_manifest.json found.")
        return 1

    if args.verbose:
        print(f"Manifest: {manifest_path}")

    # Wire governance
    task_state_port = InMemoryTaskStatePort()
    ledger = InMemoryGovernanceLedger()
    time_authority = SimpleTimeAuthority()
    emitter = TwoPhaseEventEmitter(ledger=ledger, time_authority=time_authority)

    # Hydrate REPORTED tasks
    lookup = hydrate_reported_tasks(manifest_path, task_state_port)
    if args.verbose:
        print(f"Hydrated {len(lookup)} REPORTED tasks from manifest")

    if args.decision == "list":
        return _handle_list(lookup)

    # Validate task-ref
    if not args.task_ref:
        print("ERROR: --task-ref required for accept/aggregate/escalate")
        return 1
    if args.task_ref not in lookup:
        print(f"ERROR: {args.task_ref} not found in manifest (or not REPORTED)")
        print(f"Available: {', '.join(sorted(lookup.keys()))}")
        return 1

    entry = lookup[args.task_ref]
    task_id = UUID(entry["_task_id"])
    cluster_id = entry["cluster_id"]

    if args.verbose:
        print(f"\nTask:     {args.task_ref}")
        print(f"Cluster:  {cluster_id}")
        print(f"Decision: {args.decision}")

    # Execute settlement
    if args.decision == "accept":
        new_status = await settle_accept(
            task_id,
            cluster_id,
            args.task_ref,
            task_state_port,
            ledger,
            emitter,
            time_authority,
        )
    elif args.decision == "aggregate":
        new_status = await settle_aggregate(
            task_id,
            cluster_id,
            args.task_ref,
            task_state_port,
            ledger,
            emitter,
            time_authority,
        )
    else:
        new_status = await settle_escalate(
            task_id,
            cluster_id,
            args.task_ref,
            args.blocker_type,
            args.blocker_summary,
            manifest_path,
            ledger,
            emitter,
            time_authority,
        )

    # Print settlement result
    print(f"\n{'=' * 60}")
    print(f"Settlement: {args.task_ref}")
    print(f"{'=' * 60}")
    print(f"  Decision:   {args.decision}")
    print(f"  New Status: {new_status}")

    # Show ledger events
    if args.verbose and ledger.events:
        print(f"\nGovernance ledger ({len(ledger.events)} events):")
        for evt in ledger.events:
            print(f"  [{evt.sequence}] {evt.event_type}  actor={evt.actor_id}")

    # Update manifest
    update_manifest(manifest_path, args.task_ref, new_status, args.verbose)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
