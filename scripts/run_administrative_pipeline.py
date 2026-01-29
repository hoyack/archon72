#!/usr/bin/env python3
"""Administrative Execution Pipeline.

Inputs:
- administrative_handoff.json
- earl_routing_table.json
- tool_registry.json

Outputs:
- execution_program.json
- task_activation_request.json (one per task)
- events jsonl

Notes:
- This layer does not redesign scope; it routes and activates
  tasks and reports blockers.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

# Known Earl IDs (from archons-base.json, branch=administrative_strategic)
KNOWN_EARL_IDS = frozenset(
    {
        "07fec517-1529-4499-aa55-b0a9faaf47b1",  # Raum
        "78c885cc-c9b0-4b61-bba9-50692b62fc8d",  # Furfur
        "71d8cccb-208f-49cd-a9c2-d7930076da70",  # Marax
        "3836da54-2509-4dc1-be4d-0c321cd66e58",  # Halphas
        "3af355a1-9026-4d4a-9294-9964bf230751",  # Bifrons
        "8bfe38f1-8bed-48fd-8447-fc36aed2a672",  # Andromalius
    }
)


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def append_event(events_path: Path, event: dict[str, Any]) -> None:
    events_path.parent.mkdir(parents=True, exist_ok=True)
    with events_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event) + "\n")


# ---------------------------------------------------------------------------
# A) Route supervising Earl (deterministic)
# ---------------------------------------------------------------------------


def route_earl(
    portfolios: list[str],
    routing_table: dict[str, Any],
) -> tuple[str, str, bool]:
    """Route to a supervising Earl based on portfolio context.

    Args:
        portfolios: Ordered list of portfolio keys from handoff.
        routing_table: Loaded earl_routing_table.json.

    Returns:
        Tuple of (earl_id, matched_portfolio, fallback_used).

    Raises:
        ValueError: If resolved Earl ID is not a known Earl.
    """
    portfolio_to_earl = routing_table.get("portfolio_to_earl", {})
    default_earl_id = routing_table.get("default_earl_id")

    for portfolio in portfolios:
        earl_id = portfolio_to_earl.get(portfolio)
        if earl_id is not None:
            if earl_id not in KNOWN_EARL_IDS:
                raise ValueError(
                    f"Routing table maps portfolio '{portfolio}' to "
                    f"unknown Earl ID: {earl_id}"
                )
            return earl_id, portfolio, False

    # Fallback
    if not default_earl_id:
        raise ValueError("No portfolio matched and no default_earl_id configured")
    if default_earl_id not in KNOWN_EARL_IDS:
        raise ValueError(f"default_earl_id is not a known Earl: {default_earl_id}")
    return default_earl_id, "__default__", True


# ---------------------------------------------------------------------------
# B) Validate eligible tools against registry
# ---------------------------------------------------------------------------


def filter_eligible_tools(
    required_capabilities: list[str],
    tool_class: str,
    registry: dict[str, Any],
) -> list[dict[str, Any]]:
    """Filter tools from registry by class, status, and capabilities.

    Args:
        required_capabilities: Capabilities the task requires.
        tool_class: Required tool class (HUMAN_CLUSTER or DIGITAL_TOOL).
        registry: Loaded tool_registry.json.

    Returns:
        List of matching tool entries.
    """
    required_set = set(required_capabilities)
    matched = []
    for tool in registry.get("tools", []):
        if tool.get("tool_class") != tool_class:
            continue
        if tool.get("status") != "AVAILABLE":
            continue
        tool_caps = set(tool.get("capabilities", []))
        if required_set <= tool_caps:
            matched.append(tool)
    return matched


# ---------------------------------------------------------------------------
# C) Build execution program + emit TARs
# ---------------------------------------------------------------------------


def build_execution_program(
    handoff: dict[str, Any],
    earl_id: str,
    matched_portfolio: str,
    routing_table_version: str,
    eligible_tools: list[dict[str, Any]],
    tool_class: str,
    required_capabilities: list[str],
    response_hours: int,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Build execution_program.json and TAR(s) from handoff.

    Args:
        handoff: Loaded administrative_handoff.json.
        earl_id: Resolved supervising Earl ID.
        matched_portfolio: Portfolio key used for routing.
        routing_table_version: Schema version of routing table.
        eligible_tools: Tools that passed capability filtering.
        tool_class: Tool class for activation.
        required_capabilities: Capabilities required by tasks.
        response_hours: Hours until TAR response deadline.

    Returns:
        Tuple of (execution_program dict, list of TAR dicts).
    """
    refs = handoff["references"]
    work = handoff["work_package"]
    now = utc_now()
    program_id = f"program-{uuid4()}"

    tasks = []
    tars = []

    for deliverable in work["deliverables"]:
        task_id = f"task-{uuid4()}"
        tar_id = f"tar-{uuid4()}"

        eligible_tool_ids = [t["tool_id"] for t in eligible_tools]

        task_entry = {
            "task_id": task_id,
            "title": f"Produce deliverable: {deliverable['title']}",
            "intent": work.get("summary", ""),
            "required_capabilities": list(required_capabilities),
            "acceptance_criteria": deliverable.get("acceptance_criteria", []),
            "constraints": work.get("constraints", {}).get("explicit_exclusions", []),
            "activation": {
                "earl_id": earl_id,
                "target_tool_class": tool_class,
                "eligible_tools": eligible_tool_ids,
                "priority": "NORMAL",
            },
        }
        tasks.append(task_entry)

        deadline = (
            datetime.now(timezone.utc) + timedelta(hours=response_hours)
        ).strftime("%Y-%m-%dT%H:%M:%SZ")

        tar = {
            "schema_version": "1.0",
            "tar_id": tar_id,
            "created_at": now,
            "references": {
                "program_id": program_id,
                "task_id": task_id,
                "award_id": refs["award_id"],
                "mandate_id": refs["mandate_id"],
            },
            "requester": {
                "earl_id": earl_id,
                "duke_id": refs["selected_duke_id"],
            },
            "task": {
                "title": task_entry["title"],
                "summary": work.get("summary", ""),
                "constraints": task_entry["constraints"],
                "inputs": [
                    {
                        "name": "handoff",
                        "type": "json",
                        "ref": f"artifact:handoff-{refs.get('award_id', 'unknown')}",
                    }
                ],
                "deliverables": [
                    {
                        "id": deliverable["id"],
                        "title": deliverable["title"],
                        "acceptance_criteria": deliverable.get(
                            "acceptance_criteria", []
                        ),
                    }
                ],
                "success_definition": (
                    f"Deliverable '{deliverable['title']}' produced and "
                    f"meets all acceptance criteria."
                ),
                "timebox": {"hours": response_hours},
            },
            "targeting": {
                "tool_class": tool_class,
                "eligible_tools": eligible_tool_ids,
            },
            "response_requirements": {
                "must_respond": True,
                "response_deadline_iso": deadline,
                "allowed_responses": ["ACCEPT", "DECLINE", "CLARIFY"],
            },
        }
        tars.append(tar)

    program = {
        "schema_version": "1.0",
        "program_id": program_id,
        "created_at": now,
        "references": {
            "handoff_id": handoff["handoff_id"],
            "award_id": refs["award_id"],
            "rfp_id": refs["rfp_id"],
            "mandate_id": refs["mandate_id"],
        },
        "ownership": {
            "duke_id": refs["selected_duke_id"],
            "supervising_earl_id": earl_id,
            "routing_basis": {
                "routing_table_version": routing_table_version,
                "matched_portfolio": matched_portfolio,
            },
        },
        "status": "ACTIVE",
        "tasks": tasks,
        "capacity_snapshot": {
            "captured_at": now,
            "assumptions": [],
            "declared_constraints": [],
        },
        "blockers": [],
        "events_ref": "events.jsonl",
    }

    return program, tars


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Administrative Execution Pipeline - route awarded work "
            "through Earls to Tools"
        )
    )
    p.add_argument(
        "--handoff",
        required=True,
        help="Path to administrative_handoff.json",
    )
    p.add_argument(
        "--earl-routing",
        required=True,
        help="Path to earl_routing_table.json",
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
        help="Tool class for task activation (default: HUMAN_CLUSTER)",
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
        "--dry-run",
        action="store_true",
        help=(
            "Emit events and execution_program.json but write TARs "
            "under out_dir/dry_run/ instead of activating"
        ),
    )
    p.add_argument("--verbose", "-v", action="store_true")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    out_dir = Path(args.out_dir)
    events_path = out_dir / "events.jsonl"

    # Load inputs
    handoff = load_json(Path(args.handoff))
    routing = load_json(Path(args.earl_routing))
    registry = load_json(Path(args.tool_registry))

    required_capabilities = [
        c.strip() for c in args.required_capabilities.split(",") if c.strip()
    ]

    append_event(events_path, {"type": "admin.program.start", "ts": utc_now()})

    # Step 1: Route Earl
    portfolios = handoff.get("portfolio_context", {}).get("portfolios", [])
    try:
        earl_id, matched_portfolio, fallback_used = route_earl(portfolios, routing)
    except ValueError as e:
        append_event(
            events_path,
            {
                "type": "admin.routing.failed",
                "ts": utc_now(),
                "error": str(e),
            },
        )
        print(f"ROUTING FAILED: {e}", file=sys.stderr)
        return 1

    append_event(
        events_path,
        {
            "type": "admin.routing.assigned",
            "ts": utc_now(),
            "matched_portfolio": matched_portfolio,
            "earl_id": earl_id,
            "fallback_used": fallback_used,
        },
    )
    if args.verbose:
        print(
            f"  Earl routing: {earl_id} "
            f"(portfolio={matched_portfolio}, fallback={fallback_used})"
        )

    # Step 2: Validate tool capabilities
    eligible = filter_eligible_tools(
        required_capabilities=required_capabilities,
        tool_class=args.tool_class,
        registry=registry,
    )

    total_tools = len(registry.get("tools", []))
    append_event(
        events_path,
        {
            "type": "admin.tools.filtered",
            "ts": utc_now(),
            "total_tools": total_tools,
            "eligible_count": len(eligible),
            "tool_class": args.tool_class,
            "required_capabilities": required_capabilities,
        },
    )

    if not eligible:
        append_event(
            events_path,
            {
                "type": "admin.blocker.raised",
                "ts": utc_now(),
                "blocker_type": "CAPABILITY_UNAVAILABLE",
                "tool_class": args.tool_class,
                "required_capabilities": required_capabilities,
                "available_tools": total_tools,
            },
        )
        print(
            f"BLOCKER: No {args.tool_class} tools with capabilities "
            f"{required_capabilities} are AVAILABLE.",
            file=sys.stderr,
        )
        return 1

    if args.verbose:
        print(
            f"  Tools filtered: {len(eligible)}/{total_tools} eligible "
            f"(class={args.tool_class}, caps={required_capabilities})"
        )

    # Step 3: Build execution program + TARs
    program, tars = build_execution_program(
        handoff=handoff,
        earl_id=earl_id,
        matched_portfolio=matched_portfolio,
        routing_table_version=routing.get("schema_version", "unknown"),
        eligible_tools=eligible,
        tool_class=args.tool_class,
        required_capabilities=required_capabilities,
        response_hours=args.response_hours,
    )

    # Save execution program (always)
    save_json(out_dir / "execution_program.json", program)
    append_event(
        events_path,
        {
            "type": "admin.program.created",
            "ts": utc_now(),
            "program_id": program["program_id"],
            "task_count": len(program["tasks"]),
        },
    )

    # Save TARs
    tar_dir = out_dir / ("dry_run" if args.dry_run else "tars")
    for tar in tars:
        tar_path = tar_dir / f"{tar['tar_id']}.json"
        save_json(tar_path, tar)
        append_event(
            events_path,
            {
                "type": "admin.task.activation_sent",
                "ts": utc_now(),
                "tar_id": tar["tar_id"],
                "task_id": tar["references"]["task_id"],
                "tool_class": tar["targeting"]["tool_class"],
                "eligible_tools_count": len(tar["targeting"]["eligible_tools"]),
                "dry_run": args.dry_run,
            },
        )

    # Summary
    mode_label = "DRY RUN" if args.dry_run else "ACTIVE"
    print(f"\n{'=' * 60}")
    print(f"ADMINISTRATIVE PIPELINE COMPLETE ({mode_label})")
    print(f"{'=' * 60}")
    print(f"Program ID: {program['program_id']}")
    print(f"Supervising Earl: {earl_id}")
    print(f"  Routing: portfolio={matched_portfolio}, fallback={fallback_used}")
    print(f"Tasks: {len(tars)}")
    print(f"Eligible tools: {len(eligible)}")
    print(f"TARs written to: {tar_dir}")
    print(f"Events: {events_path}")
    print(f"{'=' * 60}\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
