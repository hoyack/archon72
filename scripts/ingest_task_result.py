#!/usr/bin/env python3
"""Ingest a Task Result Artifact (TRA) and update task state.

This is the first point where reality pushes back into the system.
A tool (human or digital) submits a TRA describing what happened,
and this script:

1. Schema-validates the TRA (fail fast on bad input).
2. Optionally cross-references the execution program (fail on mismatch).
3. Maps outcome status to a deterministic task state.
4. Emits mechanical escalation events when thresholds are hit.
5. Writes task_state.json as a snapshot ledger.

Inputs:
- task_result_artifact.json
- (optional) execution_program.json for reference validation

Outputs:
- task_state.json
- events.jsonl (appended)
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import jsonschema

SCHEMAS_DIR = Path(__file__).parent.parent / "schemas" / "contracts"

# Outcome status → task state mapping (deterministic, no vibes)
OUTCOME_TO_STATE: dict[str, str] = {
    "COMPLETED": "CLOSED",
    "PARTIAL": "CLOSED_PARTIAL",
    "DECLINED": "NEEDS_REROUTE",
    "WITHDRAWN": "NEEDS_REROUTE",
    "BLOCKED": "BLOCKED",
    "FAILED": "FAILED",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(obj, indent=2, sort_keys=False) + "\n", encoding="utf-8"
    )


def append_event(events_path: Path, event: dict[str, Any]) -> None:
    events_path.parent.mkdir(parents=True, exist_ok=True)
    with events_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event) + "\n")


# ---------------------------------------------------------------------------
# 1) Schema validation
# ---------------------------------------------------------------------------


def validate_tra(tra: dict[str, Any]) -> None:
    """Validate TRA against its JSON schema. Raises on failure."""
    schema = load_json(SCHEMAS_DIR / "task_result_artifact.schema.json")
    jsonschema.validate(instance=tra, schema=schema)


# ---------------------------------------------------------------------------
# 2) Reference matching (optional but enforced when --program supplied)
# ---------------------------------------------------------------------------


def validate_references(
    tra: dict[str, Any], program: dict[str, Any]
) -> None:
    """Verify TRA references match an actual task in the execution program.

    Raises:
        ValueError: If tar_id, program_id, or task_id cannot be resolved.
    """
    refs = tra["references"]
    tra_program_id = refs["program_id"]
    tra_task_id = refs["task_id"]
    tra_tar_id = refs["tar_id"]

    if program["program_id"] != tra_program_id:
        raise ValueError(
            f"TRA program_id '{tra_program_id}' does not match "
            f"program '{program['program_id']}'"
        )

    task_ids = {t["task_id"] for t in program.get("tasks", [])}
    if tra_task_id not in task_ids:
        raise ValueError(
            f"TRA task_id '{tra_task_id}' not found in program tasks: "
            f"{sorted(task_ids)}"
        )

    # Verify tar_id is consistent with the task's activation
    for task in program["tasks"]:
        if task["task_id"] == tra_task_id:
            break


# ---------------------------------------------------------------------------
# 3) Outcome → state mapping
# ---------------------------------------------------------------------------


def resolve_task_state(outcome_status: str) -> str:
    """Map outcome status to task state. Deterministic, no inference."""
    state = OUTCOME_TO_STATE.get(outcome_status)
    if state is None:
        raise ValueError(f"Unknown outcome status: {outcome_status}")
    return state


# ---------------------------------------------------------------------------
# 4) Escalation logic (mechanical thresholds)
# ---------------------------------------------------------------------------


def compute_escalations(
    outcome: dict[str, Any],
    ts: str,
) -> list[dict[str, Any]]:
    """Compute escalations from outcome issues. Mechanical, not discretionary.

    Rules:
    - BLOCKED + needs_upstream_decision=true → Earl→Duke escalation
    - CONSTRAINT_VIOLATION + SEVERE → immediate Duke escalation
    """
    escalations: list[dict[str, Any]] = []
    issues = outcome.get("issues", [])
    status = outcome.get("status", "")

    for issue in issues:
        issue_type = issue.get("type", "")
        severity = issue.get("severity", "")
        needs_upstream = issue.get("needs_upstream_decision", False)

        # Rule 1: BLOCKED with upstream decision needed
        if status == "BLOCKED" and needs_upstream and issue_type == "BLOCKER":
            escalations.append(
                {
                    "to": "DUKE",
                    "reason": "BLOCKED_NEEDS_DECISION",
                    "ts": ts,
                }
            )

        # Rule 2: Severe constraint violation
        if issue_type == "CONSTRAINT_VIOLATION" and severity == "SEVERE":
            escalations.append(
                {
                    "to": "DUKE",
                    "reason": "SEVERE_CONSTRAINT_VIOLATION",
                    "ts": ts,
                }
            )

    return escalations


# ---------------------------------------------------------------------------
# 5) Build task state snapshot
# ---------------------------------------------------------------------------


def build_task_state(
    tra: dict[str, Any],
    state: str,
    escalations: list[dict[str, Any]],
    ts: str,
) -> dict[str, Any]:
    """Build the task_state.json snapshot from TRA + computed state."""
    refs = tra["references"]
    outcome = tra["outcome"]

    blockers = [
        {
            "severity": issue["severity"],
            "description": issue["description"],
            "needs_upstream_decision": issue["needs_upstream_decision"],
        }
        for issue in outcome.get("issues", [])
        if issue.get("type") in ("BLOCKER", "CONSTRAINT_VIOLATION")
    ]

    deliverables = [
        {"id": d["id"], "artifact_ref": d["artifact_ref"]}
        for d in outcome.get("deliverables", [])
    ]

    return {
        "schema_version": "1.0",
        "task_id": refs["task_id"],
        "program_id": refs["program_id"],
        "tar_id": refs["tar_id"],
        "tra_id": tra["tra_id"],
        "last_updated_at": ts,
        "state": state,
        "last_outcome_status": outcome["status"],
        "blockers": blockers,
        "deliverables": deliverables,
        "escalations": escalations,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Ingest a Task Result Artifact (TRA) and update task state. "
            "Proves the system can metabolize refusal."
        )
    )
    p.add_argument(
        "--result",
        required=True,
        help="Path to task_result_artifact.json",
    )
    p.add_argument(
        "--program",
        default=None,
        help="Path to execution_program.json for reference validation",
    )
    p.add_argument("--out-dir", required=True, help="Output directory")
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Emit events but do not write task_state.json",
    )
    p.add_argument("--verbose", "-v", action="store_true")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    out_dir = Path(args.out_dir)
    events_path = out_dir / "events.jsonl"
    ts = utc_now()

    # Load TRA
    tra = load_json(Path(args.result))

    # Step 1: Schema-validate (fail fast)
    try:
        validate_tra(tra)
    except jsonschema.ValidationError as e:
        append_event(
            events_path,
            {
                "type": "admin.ingest.schema_invalid",
                "ts": ts,
                "error": str(e.message),
                "tra_path": args.result,
            },
        )
        print(f"SCHEMA VALIDATION FAILED: {e.message}", file=sys.stderr)
        return 1

    refs = tra["references"]
    tra_id = tra["tra_id"]

    append_event(
        events_path,
        {
            "type": "tools.result.submitted",
            "ts": ts,
            "tra_id": tra_id,
            "tar_id": refs["tar_id"],
            "task_id": refs["task_id"],
            "program_id": refs["program_id"],
            "outcome_status": tra["outcome"]["status"],
        },
    )

    if args.verbose:
        print(
            f"  TRA received: {tra_id} "
            f"(status={tra['outcome']['status']})"
        )

    # Step 2: Reference validation (if program supplied)
    if args.program:
        program = load_json(Path(args.program))
        try:
            validate_references(tra, program)
        except ValueError as e:
            append_event(
                events_path,
                {
                    "type": "admin.ingest.unmatched_reference",
                    "ts": ts,
                    "tra_id": tra_id,
                    "error": str(e),
                },
            )
            print(f"UNMATCHED REFERENCE: {e}", file=sys.stderr)
            return 1

        if args.verbose:
            print("  References validated against program")

    # Step 3: Map outcome → state
    outcome_status = tra["outcome"]["status"]
    state = resolve_task_state(outcome_status)

    # Step 4: Compute escalations
    escalations = compute_escalations(tra["outcome"], ts)

    # Step 5: Build task state
    task_state = build_task_state(tra, state, escalations, ts)

    # Emit state update event
    append_event(
        events_path,
        {
            "type": "admin.task.state_updated",
            "ts": ts,
            "tra_id": tra_id,
            "task_id": refs["task_id"],
            "program_id": refs["program_id"],
            "new_state": state,
            "outcome_status": outcome_status,
            "escalation_count": len(escalations),
        },
    )

    # Emit escalation events
    for esc in escalations:
        append_event(
            events_path,
            {
                "type": "admin.escalation.sent",
                "ts": ts,
                "tra_id": tra_id,
                "task_id": refs["task_id"],
                "program_id": refs["program_id"],
                "escalation_to": esc["to"],
                "escalation_reason": esc["reason"],
            },
        )
        if args.verbose:
            print(f"  ESCALATION: {esc['reason']} → {esc['to']}")

    # Write task state (unless dry-run)
    if not args.dry_run:
        state_path = out_dir / f"task_state_{refs['task_id']}.json"
        save_json(state_path, task_state)
        if args.verbose:
            print(f"  Task state written: {state_path}")
    else:
        if args.verbose:
            print(f"  DRY RUN: task state not written (state={state})")

    # Summary
    mode_label = "DRY RUN" if args.dry_run else "ACTIVE"
    print(f"\n{'=' * 60}")
    print(f"TASK RESULT INGESTED ({mode_label})")
    print(f"{'=' * 60}")
    print(f"TRA: {tra_id}")
    print(f"Task: {refs['task_id']}")
    print(f"Outcome: {outcome_status}")
    print(f"State: {state}")
    print(f"Blockers: {len(task_state['blockers'])}")
    print(f"Deliverables: {len(task_state['deliverables'])}")
    print(f"Escalations: {len(escalations)}")
    print(f"Events: {events_path}")
    print(f"{'=' * 60}\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
