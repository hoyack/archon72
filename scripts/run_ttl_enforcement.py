#!/usr/bin/env python3
"""TTL enforcement — prove that silence has consequence.

Exercises the three timeout scenarios from the constitutional framework:

1. Activation TTL (72h):  ROUTED  → DECLINED   (ttl_expired)
2. Acceptance inactivity (48h):  ACCEPTED → IN_PROGRESS (auto_started)
3. Reporting timeout (7d):  IN_PROGRESS → QUARANTINED  (reporting_timeout)

Every timeout emits an explicit event with actor="system" and
penalty_incurred=False. The Golden Rule: Failure is allowed; silence is not.

Usage:
    python scripts/run_ttl_enforcement.py -v
    python scripts/run_ttl_enforcement.py --manifest path/to/activation_manifest.json
    python scripts/run_ttl_enforcement.py --scenario activation -v
    python scripts/run_ttl_enforcement.py --scenario all -v
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from src.application.services.governance.task_timeout_service import (
    TaskTimeoutService,
)
from src.domain.events.breach import BreachType  # CONSTITUTIONAL_CONSTRAINT used
from src.domain.governance.task.task_state import TaskState, TaskStatus
from src.domain.models.pending_escalation import (
    ESCALATION_THRESHOLD_DAYS,
    PendingEscalation,
)
from src.infrastructure.adapters.governance.in_memory_adapters import (
    InMemoryGovernanceLedger,
    InMemoryTaskStatePort,
)
from tests.helpers.fake_time_authority import FakeTimeAuthority


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


def hydrate_manifest_tasks(
    manifest_path: Path,
    task_state_port: InMemoryTaskStatePort,
    time_authority: FakeTimeAuthority,
) -> dict[str, dict]:
    """Load tasks from manifest into in-memory state."""
    with open(manifest_path) as f:
        entries = json.load(f)

    lookup: dict[str, dict] = {}
    now = time_authority.now()

    for entry in entries:
        status_str = entry["status"]
        status_map = {
            "ROUTED": TaskStatus.ROUTED,
            "ACCEPTED": TaskStatus.ACCEPTED,
            "IN_PROGRESS": TaskStatus.IN_PROGRESS,
            "REPORTED": TaskStatus.REPORTED,
        }
        if status_str not in status_map:
            continue

        task_id = uuid4()
        task = TaskState(
            task_id=task_id,
            earl_id="earl-bridge",
            cluster_id=entry["cluster_id"],
            current_status=status_map[status_str],
            created_at=now - timedelta(hours=1),
            state_entered_at=now,  # entered current state "now"
            ttl=timedelta(hours=72),
        )
        task_state_port._tasks[task_id] = task
        entry["_task_id"] = str(task_id)
        lookup[entry["task_ref"]] = entry

    return lookup


def print_section(title: str) -> None:
    """Print a section header."""
    print(f"\n{'=' * 60}")
    print(title)
    print(f"{'=' * 60}")


def print_ledger(ledger: InMemoryGovernanceLedger, since: int = 0) -> None:
    """Print ledger events since a given sequence."""
    new_events = [e for e in ledger.events if e.sequence > since]
    if not new_events:
        print("  (no new events)")
        return
    for evt in new_events:
        payload = evt.event.payload
        penalty = payload.get("penalty_incurred", "n/a")
        reason = payload.get("reason", "")
        print(
            f"  [{evt.sequence:3d}] {evt.event_type:40s} "
            f"actor={evt.event.actor_id:8s}  "
            f"penalty={penalty}  reason={reason}"
        )


async def run_activation_ttl(
    lookup: dict[str, dict],
    task_state_port: InMemoryTaskStatePort,
    ledger: InMemoryGovernanceLedger,
    time_authority: FakeTimeAuthority,
    verbose: bool,
) -> list[str]:
    """Scenario 1: ROUTED tasks age past 72h TTL → auto-DECLINED."""
    print_section("Scenario 1: Activation TTL (72h) — ROUTED → DECLINED")

    routed = {ref: e for ref, e in lookup.items() if e["status"] == "ROUTED"}
    if not routed:
        print("  No ROUTED tasks in manifest.")
        return []

    print(f"  ROUTED tasks: {', '.join(routed.keys())}")
    print(f"  Current time:  {time_authority.now().isoformat()}")

    # Advance 36h — 50% TTL milestone
    time_authority.advance(delta=timedelta(hours=36))
    print("\n  --- Advanced 36h (50% TTL) ---")
    print(f"  Time: {time_authority.now().isoformat()}")
    for ref, entry in routed.items():
        task = await task_state_port.get_task(entry["_task_id_typed"])
        remaining = (task.state_entered_at + task.ttl) - time_authority.now()
        print(f"    {ref}: TTL remaining = {remaining}")

    # Advance to 64.8h — 90% TTL milestone
    time_authority.advance(delta=timedelta(hours=28, minutes=48))
    print("\n  --- Advanced to 64.8h (90% TTL) ---")
    print(f"  Time: {time_authority.now().isoformat()}")
    for ref, entry in routed.items():
        task = await task_state_port.get_task(entry["_task_id_typed"])
        remaining = (task.state_entered_at + task.ttl) - time_authority.now()
        print(f"    {ref}: TTL remaining = {remaining}")

    # Advance past 72h — TTL expired (strict > check, need to overshoot)
    time_authority.advance(delta=timedelta(hours=7, minutes=13))
    print("\n  --- Advanced past 72h (TTL EXPIRED) ---")
    print(f"  Time: {time_authority.now().isoformat()}")

    # Verify TTL expired
    for ref, entry in routed.items():
        task = await task_state_port.get_task(entry["_task_id_typed"])
        expired = task.is_ttl_expired(time_authority.now())
        print(f"    {ref}: is_ttl_expired = {expired}")

    # Run timeout service
    seq_before = len(ledger.events)
    timeout_svc = TaskTimeoutService(
        task_state_port=task_state_port,
        ledger_port=ledger,
        time_authority=time_authority,
    )
    declined_ids = await timeout_svc.process_activation_timeouts()

    print(f"\n  Auto-declined: {len(declined_ids)} tasks")

    # Show state after
    declined_refs = []
    for ref, entry in routed.items():
        task = await task_state_port.get_task(entry["_task_id_typed"])
        print(f"    {ref}: {task.current_status.value} (terminal={task.is_terminal})")
        if task.current_status == TaskStatus.DECLINED:
            declined_refs.append(ref)

    if verbose:
        print("\n  Ledger events:")
        print_ledger(ledger, seq_before)

    return declined_refs


async def run_acceptance_inactivity(
    task_state_port: InMemoryTaskStatePort,
    ledger: InMemoryGovernanceLedger,
    time_authority: FakeTimeAuthority,
    verbose: bool,
) -> int:
    """Scenario 2: ACCEPTED task ages 48h → auto-started."""
    print_section("Scenario 2: Acceptance Inactivity (48h) — ACCEPTED → IN_PROGRESS")

    # Create a fresh ACCEPTED task
    task_id = uuid4()
    now = time_authority.now()
    task = TaskState(
        task_id=task_id,
        earl_id="earl-bridge",
        cluster_id="test-cluster-inactivity",
        current_status=TaskStatus.ACCEPTED,
        created_at=now - timedelta(hours=1),
        state_entered_at=now,
        ttl=timedelta(hours=72),
    )
    task_state_port._tasks[task_id] = task
    print(f"  Created ACCEPTED task: {task_id}")
    print(f"  State entered at:      {now.isoformat()}")

    # Advance 48h
    time_authority.advance(delta=timedelta(hours=48, minutes=1))
    print("\n  --- Advanced 48h 1m (past inactivity threshold) ---")
    print(f"  Time: {time_authority.now().isoformat()}")

    seq_before = len(ledger.events)
    timeout_svc = TaskTimeoutService(
        task_state_port=task_state_port,
        ledger_port=ledger,
        time_authority=time_authority,
    )
    started_ids = await timeout_svc.process_acceptance_timeouts()

    print(f"\n  Auto-started: {len(started_ids)} tasks")
    updated = await task_state_port.get_task(task_id)
    print(f"  New status: {updated.current_status.value}")

    if verbose:
        print("\n  Ledger events:")
        print_ledger(ledger, seq_before)

    return len(started_ids)


async def run_reporting_timeout(
    task_state_port: InMemoryTaskStatePort,
    ledger: InMemoryGovernanceLedger,
    time_authority: FakeTimeAuthority,
    verbose: bool,
) -> int:
    """Scenario 3: IN_PROGRESS task ages 7d → auto-QUARANTINED."""
    print_section("Scenario 3: Reporting Timeout (7d) — IN_PROGRESS → QUARANTINED")

    # Create a fresh IN_PROGRESS task
    task_id = uuid4()
    now = time_authority.now()
    task = TaskState(
        task_id=task_id,
        earl_id="earl-bridge",
        cluster_id="test-cluster-timeout",
        current_status=TaskStatus.IN_PROGRESS,
        created_at=now - timedelta(days=1),
        state_entered_at=now,
        ttl=timedelta(hours=72),
    )
    task_state_port._tasks[task_id] = task
    print(f"  Created IN_PROGRESS task: {task_id}")
    print(f"  State entered at:         {now.isoformat()}")

    # Advance 7 days + 1 minute
    time_authority.advance(delta=timedelta(days=7, minutes=1))
    print("\n  --- Advanced 7d 1m (past reporting timeout) ---")
    print(f"  Time: {time_authority.now().isoformat()}")

    # Check reporting expired
    updated_task = await task_state_port.get_task(task_id)
    print(
        f"  is_reporting_expired: {updated_task.is_reporting_expired(time_authority.now())}"
    )

    seq_before = len(ledger.events)
    timeout_svc = TaskTimeoutService(
        task_state_port=task_state_port,
        ledger_port=ledger,
        time_authority=time_authority,
    )
    quarantined_ids = await timeout_svc.process_reporting_timeouts()

    print(f"\n  Auto-quarantined: {len(quarantined_ids)} tasks")
    updated = await task_state_port.get_task(task_id)
    print(
        f"  New status: {updated.current_status.value} (terminal={updated.is_terminal})"
    )

    if verbose:
        print("\n  Ledger events:")
        print_ledger(ledger, seq_before)

    return len(quarantined_ids)


def run_blocker_aging(time_authority: FakeTimeAuthority, verbose: bool) -> None:
    """Scenario 4: Blocker ages past 7-day threshold → Conclave-eligible."""
    print_section(
        f"Scenario 4: Blocker Aging ({ESCALATION_THRESHOLD_DAYS}d) — PENDING → OVERDUE"
    )

    breach_id = uuid4()
    detection_time = time_authority.now()
    print(f"  Blocker detected at: {detection_time.isoformat()}")

    # Day 0: fresh
    esc = PendingEscalation.from_breach(
        breach_id=breach_id,
        breach_type=BreachType.CONSTITUTIONAL_CONSTRAINT,
        detection_timestamp=detection_time,
        current_time=time_authority.now(),
    )
    print(
        f"\n  Day 0: urgency={esc.urgency_level}  "
        f"days_remaining={esc.days_remaining}  "
        f"hours_remaining={esc.hours_remaining}"
    )

    # Day 4: WARNING
    time_authority.advance(delta=timedelta(days=4))
    esc = PendingEscalation.from_breach(
        breach_id=breach_id,
        breach_type=BreachType.CONSTITUTIONAL_CONSTRAINT,
        detection_timestamp=detection_time,
        current_time=time_authority.now(),
    )
    print(
        f"  Day 4: urgency={esc.urgency_level}  "
        f"days_remaining={esc.days_remaining}  "
        f"hours_remaining={esc.hours_remaining}"
    )

    # Day 6.5: URGENT
    time_authority.advance(delta=timedelta(days=2, hours=12))
    esc = PendingEscalation.from_breach(
        breach_id=breach_id,
        breach_type=BreachType.CONSTITUTIONAL_CONSTRAINT,
        detection_timestamp=detection_time,
        current_time=time_authority.now(),
    )
    print(
        f"  Day 6.5: urgency={esc.urgency_level}  "
        f"days_remaining={esc.days_remaining}  "
        f"hours_remaining={esc.hours_remaining}"
    )

    # Day 7+: OVERDUE
    time_authority.advance(delta=timedelta(hours=13))
    esc = PendingEscalation.from_breach(
        breach_id=breach_id,
        breach_type=BreachType.CONSTITUTIONAL_CONSTRAINT,
        detection_timestamp=detection_time,
        current_time=time_authority.now(),
    )
    print(
        f"  Day 7+: urgency={esc.urgency_level}  "
        f"days_remaining={esc.days_remaining}  "
        f"hours_remaining={esc.hours_remaining}"
    )
    print(f"  is_overdue={esc.is_overdue}  → eligible for Conclave agenda (FR31)")


def update_manifest(
    manifest_path: Path,
    declined_refs: list[str],
    verbose: bool,
) -> None:
    """Update manifest file with auto-declined statuses."""
    if not declined_refs:
        return

    with open(manifest_path) as f:
        entries = json.load(f)

    for entry in entries:
        if entry["task_ref"] in declined_refs:
            entry["status"] = "DECLINED"

    with open(manifest_path, "w") as f:
        json.dump(entries, f, indent=2)

    if verbose:
        print(f"\n  Manifest updated: {manifest_path}")
        for ref in declined_refs:
            print(f"    {ref} → DECLINED (ttl_expired)")


async def main() -> int:
    parser = argparse.ArgumentParser(description="TTL enforcement proof")
    parser.add_argument("--manifest", help="Path to activation_manifest.json")
    parser.add_argument(
        "--scenario",
        choices=["activation", "inactivity", "reporting", "blocker", "all"],
        default="all",
        help="Which timeout scenario to run (default: all)",
    )
    parser.add_argument(
        "--update-manifest",
        action="store_true",
        help="Update manifest file with auto-declined statuses",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    # Wire governance infrastructure
    task_state_port = InMemoryTaskStatePort()
    ledger = InMemoryGovernanceLedger()
    base_time = datetime(2026, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
    time_authority = FakeTimeAuthority(frozen_at=base_time)

    manifest_path = Path(args.manifest) if args.manifest else find_latest_manifest()

    # Hydrate manifest tasks (store typed UUID for lookup)
    lookup: dict[str, dict] = {}
    if manifest_path and manifest_path.exists():
        lookup = hydrate_manifest_tasks(manifest_path, task_state_port, time_authority)
        # Stash typed UUIDs for direct access
        for entry in lookup.values():
            from uuid import UUID as _UUID

            entry["_task_id_typed"] = _UUID(entry["_task_id"])
        if args.verbose:
            print(f"Manifest: {manifest_path}")
            print(f"Hydrated {len(lookup)} active tasks")
    elif args.scenario in ("activation",):
        print("ERROR: No activation_manifest.json found for activation scenario.")
        return 1

    scenarios = (
        [args.scenario]
        if args.scenario != "all"
        else ["activation", "inactivity", "reporting", "blocker"]
    )

    declined_refs: list[str] = []

    for scenario in scenarios:
        if scenario == "activation":
            if not lookup:
                print("\n  Skipping activation — no manifest tasks loaded.")
                continue
            declined_refs = await run_activation_ttl(
                lookup, task_state_port, ledger, time_authority, args.verbose
            )
        elif scenario == "inactivity":
            await run_acceptance_inactivity(
                task_state_port, ledger, time_authority, args.verbose
            )
        elif scenario == "reporting":
            await run_reporting_timeout(
                task_state_port, ledger, time_authority, args.verbose
            )
        elif scenario == "blocker":
            run_blocker_aging(time_authority, args.verbose)

    # Summary
    print_section("Enforcement Summary")
    print(f"  Total ledger events: {len(ledger.events)}")
    print(f"  Time advanced to:    {time_authority.now().isoformat()}")

    # Constitutional guarantees
    system_events = [e for e in ledger.events if e.event.actor_id == "system"]
    penalty_events = [
        e for e in ledger.events if e.event.payload.get("penalty_incurred") is True
    ]
    print("\n  Constitutional guarantees:")
    print(f"    Events with actor='system':         {len(system_events)}")
    print(f"    Events with penalty_incurred=True:  {len(penalty_events)}")
    if penalty_events:
        print("    WARNING: Penalty events found — constitutional violation!")
    else:
        print("    No penalties attributed — constitution upheld.")

    # Event type breakdown
    if args.verbose and ledger.events:
        print("\n  Event type breakdown:")
        from collections import Counter

        counts = Counter(e.event_type for e in ledger.events)
        for etype, count in sorted(counts.items()):
            print(f"    {etype:45s}  {count}")

    # Update manifest if requested
    if args.update_manifest and manifest_path and declined_refs:
        update_manifest(manifest_path, declined_refs, args.verbose)

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
