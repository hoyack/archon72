#!/usr/bin/env python3
"""Reroute a NEEDS_REROUTE task to the next eligible tool.

After a tool DECLINES or WITHDRAWS, this script:

1. Loads the task state and validates it is NEEDS_REROUTE.
2. Builds the exclusion list from attempt_history.
3. Filters eligible tools (same logic as admin pipeline).
4. Selects the next tool by strategy (round_robin default).
5. Emits a new TAR and updates task state.
6. If no tools remain: marks BLOCKED + escalates to DUKE.

This completes the refusal loop:
  decline -> reroute -> (maybe) decline again -> escalation

Inputs:
- task_state.json (must be in NEEDS_REROUTE state)
- tool_registry.json
- execution_program.json (for task metadata)

Outputs:
- New TAR file
- Updated task_state.json
- Events appended to events.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


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
# Core reroute logic (pure functions, testable)
# ---------------------------------------------------------------------------


def validate_reroute_precondition(task_state: dict[str, Any]) -> None:
    """Verify task is in a reroutable state.

    Raises:
        ValueError: If state is not NEEDS_REROUTE.
    """
    state = task_state.get("state")
    if state != "NEEDS_REROUTE":
        raise ValueError(
            f"Task state is '{state}', expected 'NEEDS_REROUTE'. "
            f"Cannot reroute a task that hasn't been declined."
        )


def build_exclusion_set(task_state: dict[str, Any]) -> set[str]:
    """Build the set of tool IDs to exclude from rerouting.

    Sources:
    - attempt_history[].tool_id (tools already tried)
    - excluded_tools[] (explicit exclusions)
    """
    excluded = set(task_state.get("excluded_tools", []))
    for attempt in task_state.get("attempt_history", []):
        excluded.add(attempt["tool_id"])
    return excluded


def filter_reroute_candidates(
    required_capabilities: list[str],
    tool_class: str,
    registry: dict[str, Any],
    excluded_tool_ids: set[str],
) -> list[dict[str, Any]]:
    """Filter tools eligible for reroute (same as admin pipeline + exclusion).

    Args:
        required_capabilities: Capabilities the task requires.
        tool_class: Required tool class.
        registry: Loaded tool_registry.json.
        excluded_tool_ids: Tool IDs to exclude (already tried).

    Returns:
        List of eligible tool entries, sorted by tool_id for stable ordering.
    """
    required_set = set(required_capabilities)
    candidates = []
    for tool in registry.get("tools", []):
        if tool["tool_id"] in excluded_tool_ids:
            continue
        if tool.get("tool_class") != tool_class:
            continue
        if tool.get("status") != "AVAILABLE":
            continue
        tool_caps = set(tool.get("capabilities", []))
        if required_set <= tool_caps:
            candidates.append(tool)
    # Stable sort by tool_id for round_robin determinism
    candidates.sort(key=lambda t: t["tool_id"])
    return candidates


def select_tool(
    candidates: list[dict[str, Any]],
    strategy: str,
) -> dict[str, Any] | None:
    """Select a tool from candidates by strategy.

    Args:
        candidates: Eligible tools (sorted for round_robin).
        strategy: Selection strategy (round_robin, priority, random).

    Returns:
        Selected tool dict, or None if candidates is empty.
    """
    if not candidates:
        return None

    if strategy == "round_robin":
        return candidates[0]
    if strategy == "random":
        import random

        return random.choice(candidates)
    # priority and unknown strategies fall back to first candidate
    return candidates[0]


def check_max_attempts(
    task_state: dict[str, Any],
) -> bool:
    """Check if max reroute attempts have been reached.

    Returns:
        True if max attempts reached (should escalate instead of reroute).
    """
    policy = task_state.get("reroute_policy", {})
    max_attempts = policy.get("max_attempts", 3)
    attempt_count = task_state.get("attempt_count", 0)
    return attempt_count >= max_attempts


def build_reroute_tar(
    task_state: dict[str, Any],
    program: dict[str, Any],
    selected_tool: dict[str, Any],
    response_hours: int,
) -> dict[str, Any]:
    """Build a new TAR for the rerouted task.

    Args:
        task_state: Current task state.
        program: Execution program for task metadata.
        selected_tool: Tool selected for reroute.
        response_hours: Hours until response deadline.

    Returns:
        TAR dict ready for schema validation and emission.
    """
    ts = utc_now()
    tar_id = f"tar-{uuid4()}"
    task_id = task_state["task_id"]

    # Find task entry in program for metadata
    task_entry = None
    for t in program.get("tasks", []):
        if t["task_id"] == task_id:
            task_entry = t
            break

    if task_entry is None:
        raise ValueError(
            f"Task '{task_id}' not found in program '{program['program_id']}'"
        )

    deadline = (
        datetime.now(timezone.utc) + timedelta(hours=response_hours)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")

    return {
        "schema_version": "1.0",
        "tar_id": tar_id,
        "created_at": ts,
        "references": {
            "program_id": program["program_id"],
            "task_id": task_id,
            "award_id": program["references"]["award_id"],
            "mandate_id": program["references"]["mandate_id"],
        },
        "requester": {
            "earl_id": program["ownership"]["supervising_earl_id"],
            "duke_id": program["ownership"]["duke_id"],
        },
        "task": {
            "title": task_entry["title"],
            "summary": task_entry.get("intent", ""),
            "constraints": task_entry.get("constraints", []),
            "inputs": [
                {
                    "name": "handoff",
                    "type": "json",
                    "ref": f"artifact:handoff-{program['references'].get('award_id', 'unknown')}",
                }
            ],
            "deliverables": [
                {
                    "id": f"deliv-{i + 1}",
                    "title": ac,
                    "acceptance_criteria": [ac],
                }
                for i, ac in enumerate(
                    task_entry.get("acceptance_criteria", ["Meet requirements"])
                )
            ]
            or [
                {
                    "id": "deliv-1",
                    "title": task_entry["title"],
                    "acceptance_criteria": ["Meet requirements"],
                }
            ],
            "success_definition": (
                f"Rerouted task '{task_entry['title']}' completed successfully."
            ),
            "timebox": {"hours": response_hours},
        },
        "targeting": {
            "tool_class": selected_tool["tool_class"],
            "eligible_tools": [selected_tool["tool_id"]],
        },
        "response_requirements": {
            "must_respond": True,
            "response_deadline_iso": deadline,
            "allowed_responses": ["ACCEPT", "DECLINE", "CLARIFY"],
        },
    }


def update_task_state_for_reroute(
    task_state: dict[str, Any],
    new_tar_id: str,
    selected_tool_id: str,
    ts: str,
) -> dict[str, Any]:
    """Update task state after successful reroute.

    Returns a new task state dict (does not mutate input).
    """
    updated = dict(task_state)
    updated["state"] = "ACTIVATION_SENT"
    updated["tar_id"] = new_tar_id
    updated["last_updated_at"] = ts

    attempt_count = updated.get("attempt_count", 0) + 1
    updated["attempt_count"] = attempt_count

    history = list(updated.get("attempt_history", []))
    history.append(
        {
            "tar_id": new_tar_id,
            "tool_id": selected_tool_id,
            "created_at": ts,
        }
    )
    updated["attempt_history"] = history

    excluded = list(updated.get("excluded_tools", []))
    if selected_tool_id not in excluded:
        excluded.append(selected_tool_id)
    updated["excluded_tools"] = excluded

    if "reroute_policy" not in updated:
        updated["reroute_policy"] = {
            "max_attempts": 3,
            "escalate_on_exhaustion": True,
        }

    return updated


def update_task_state_for_exhaustion(
    task_state: dict[str, Any],
    reason: str,
    ts: str,
) -> dict[str, Any]:
    """Update task state when reroute is exhausted (no tools left or max attempts).

    Returns a new task state dict with BLOCKED state and escalation.
    """
    updated = dict(task_state)
    updated["state"] = "BLOCKED"
    updated["last_updated_at"] = ts

    escalations = list(updated.get("escalations", []))
    escalations.append(
        {
            "to": "DUKE",
            "reason": reason,
            "ts": ts,
        }
    )
    updated["escalations"] = escalations

    if "reroute_policy" not in updated:
        updated["reroute_policy"] = {
            "max_attempts": 3,
            "escalate_on_exhaustion": True,
        }

    return updated


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Reroute a NEEDS_REROUTE task to the next eligible tool. "
            "Completes the refusal loop."
        )
    )
    p.add_argument(
        "--task-state",
        required=True,
        help="Path to task_state.json",
    )
    p.add_argument(
        "--program",
        required=True,
        help="Path to execution_program.json",
    )
    p.add_argument(
        "--tool-registry",
        required=True,
        help="Path to tool_registry.json",
    )
    p.add_argument("--out-dir", required=True, help="Output directory")
    p.add_argument(
        "--tool-class",
        choices=["HUMAN_CLUSTER", "DIGITAL_TOOL"],
        default="HUMAN_CLUSTER",
        help="Tool class for reroute (default: HUMAN_CLUSTER)",
    )
    p.add_argument(
        "--required-capabilities",
        type=str,
        default="doc_drafting",
        help="Comma-separated required capabilities (default: doc_drafting)",
    )
    p.add_argument(
        "--response-hours",
        type=int,
        default=8,
        help="Hours until TAR response deadline (default: 8)",
    )
    p.add_argument(
        "--strategy",
        choices=["round_robin", "priority", "random"],
        default="round_robin",
        help="Tool selection strategy (default: round_robin)",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Emit events but write TAR and state under dry_run/",
    )
    p.add_argument("--verbose", "-v", action="store_true")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    out_dir = Path(args.out_dir)
    events_path = out_dir / "events.jsonl"
    ts = utc_now()

    task_state = load_json(Path(args.task_state))
    program = load_json(Path(args.program))
    registry = load_json(Path(args.tool_registry))

    required_capabilities = [
        c.strip()
        for c in args.required_capabilities.split(",")
        if c.strip()
    ]

    # Step 1: Validate precondition
    try:
        validate_reroute_precondition(task_state)
    except ValueError as e:
        print(f"REROUTE REJECTED: {e}", file=sys.stderr)
        return 1

    task_id = task_state["task_id"]
    attempt_count = task_state.get("attempt_count", 0)

    append_event(
        events_path,
        {
            "type": "admin.reroute.started",
            "ts": ts,
            "task_id": task_id,
            "attempt_count": attempt_count,
        },
    )

    # Step 2: Check max attempts
    if check_max_attempts(task_state):
        policy = task_state.get("reroute_policy", {})
        max_attempts = policy.get("max_attempts", 3)
        append_event(
            events_path,
            {
                "type": "admin.reroute.exhausted",
                "ts": ts,
                "task_id": task_id,
                "reason": "MAX_ATTEMPTS_REACHED",
                "max_attempts": max_attempts,
                "tried_tools_count": attempt_count,
            },
        )
        updated = update_task_state_for_exhaustion(
            task_state, "REROUTE_MAX_ATTEMPTS_REACHED", ts
        )

        escalate = policy.get("escalate_on_exhaustion", True)
        if escalate:
            append_event(
                events_path,
                {
                    "type": "admin.escalation.sent",
                    "ts": ts,
                    "task_id": task_id,
                    "escalation_to": "DUKE",
                    "escalation_reason": "REROUTE_MAX_ATTEMPTS_REACHED",
                },
            )

        if not args.dry_run:
            save_json(Path(args.task_state), updated)

        print(f"REROUTE EXHAUSTED: max attempts ({max_attempts}) reached", file=sys.stderr)
        return 1

    # Step 3: Build exclusion set and filter candidates
    excluded = build_exclusion_set(task_state)
    candidates = filter_reroute_candidates(
        required_capabilities=required_capabilities,
        tool_class=args.tool_class,
        registry=registry,
        excluded_tool_ids=excluded,
    )

    if args.verbose:
        print(
            f"  Excluded tools: {sorted(excluded)}"
        )
        print(
            f"  Candidates: {[c['tool_id'] for c in candidates]}"
        )

    # Step 4: Handle exhaustion (no candidates)
    if not candidates:
        append_event(
            events_path,
            {
                "type": "admin.reroute.exhausted",
                "ts": ts,
                "task_id": task_id,
                "reason": "NO_ELIGIBLE_TOOLS",
                "tried_tools_count": len(excluded),
            },
        )

        updated = update_task_state_for_exhaustion(
            task_state, "REROUTE_EXHAUSTED", ts
        )

        policy = task_state.get("reroute_policy", {})
        if policy.get("escalate_on_exhaustion", True):
            append_event(
                events_path,
                {
                    "type": "admin.escalation.sent",
                    "ts": ts,
                    "task_id": task_id,
                    "escalation_to": "DUKE",
                    "escalation_reason": "REROUTE_EXHAUSTED",
                },
            )

        if not args.dry_run:
            save_json(Path(args.task_state), updated)

        print(
            f"REROUTE EXHAUSTED: no eligible tools remain "
            f"(tried {len(excluded)})",
            file=sys.stderr,
        )
        return 1

    # Step 5: Select tool
    selected = select_tool(candidates, args.strategy)
    assert selected is not None  # guaranteed by non-empty candidates

    append_event(
        events_path,
        {
            "type": "admin.reroute.tool_selected",
            "ts": ts,
            "task_id": task_id,
            "selected_tool_id": selected["tool_id"],
            "strategy": args.strategy,
            "candidates_count": len(candidates),
        },
    )

    if args.verbose:
        print(f"  Selected: {selected['tool_id']} (strategy={args.strategy})")

    # Step 6: Build and emit new TAR
    new_tar = build_reroute_tar(
        task_state=task_state,
        program=program,
        selected_tool=selected,
        response_hours=args.response_hours,
    )

    tar_dir = out_dir / ("dry_run" if args.dry_run else "tars")
    tar_path = tar_dir / f"{new_tar['tar_id']}.json"
    save_json(tar_path, new_tar)

    append_event(
        events_path,
        {
            "type": "admin.task.activation_sent",
            "ts": ts,
            "tar_id": new_tar["tar_id"],
            "task_id": task_id,
            "tool_id": selected["tool_id"],
            "tool_class": selected["tool_class"],
            "is_reroute": True,
            "attempt_number": attempt_count + 1,
            "dry_run": args.dry_run,
        },
    )

    # Step 7: Update task state
    updated = update_task_state_for_reroute(
        task_state, new_tar["tar_id"], selected["tool_id"], ts
    )

    if not args.dry_run:
        save_json(Path(args.task_state), updated)

    # Summary
    mode_label = "DRY RUN" if args.dry_run else "ACTIVE"
    print(f"\n{'=' * 60}")
    print(f"TASK REROUTED ({mode_label})")
    print(f"{'=' * 60}")
    print(f"Task: {task_id}")
    print(f"Previous tool: {task_state.get('excluded_tools', ['(first attempt)'])}")
    print(f"New tool: {selected['tool_id']}")
    print(f"Strategy: {args.strategy}")
    print(f"Attempt: {attempt_count + 1}")
    print(f"TAR: {new_tar['tar_id']}")
    print(f"TAR written to: {tar_path}")
    print(f"Events: {events_path}")
    print(f"{'=' * 60}\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
