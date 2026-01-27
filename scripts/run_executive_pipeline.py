#!/usr/bin/env python3
"""Run the Executive planning pipeline on ratified intent packets.

This stage forks after ratification:
Review Pipeline -> Ratified Intent Packets -> Executive Mini-Conclave
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

from src.application.services.executive_planning_service import (  # noqa: E402
    ExecutivePlanningService,
    now_iso,
)


def find_latest_review_pipeline_output() -> Path | None:
    pattern = "_bmad-output/review-pipeline/*"
    dirs = [d for d in glob.glob(pattern) if Path(d).is_dir()]
    if not dirs:
        return None
    return Path(max(dirs, key=lambda d: Path(d).stat().st_mtime))


def resolve_role_llm_config(env_var: str):
    archon_id_value = os.environ.get(env_var)
    if not archon_id_value:
        return None

    try:
        archon_id = UUID(archon_id_value)
    except ValueError:
        print(f"Warning: {env_var} is not a valid UUID: {archon_id_value}")
        return None

    from src.infrastructure.adapters.config.archon_profile_adapter import (  # noqa: E402
        create_archon_profile_repository,
    )

    repo = create_archon_profile_repository()
    profile = repo.get_by_id(archon_id)
    if not profile:
        print(f"Warning: {env_var} Archon not found: {archon_id_value}")
        return None

    print(f"Using {env_var}={archon_id_value} ({profile.name})")
    return profile.llm_config


def _save_json(path: Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2)


def _save_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row))
            f.write("\n")


def _parse_list_arg(value: str | None) -> list[str] | None:
    if not value:
        return None
    items = [v.strip() for v in value.split(",") if v.strip()]
    return items or None


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Executive planning pipeline")
    parser.add_argument(
        "review_pipeline_path",
        type=Path,
        nargs="?",
        default=None,
        help="Path to review pipeline output directory (auto-detects if not specified)",
    )
    parser.add_argument(
        "--outdir",
        type=Path,
        default=Path("_bmad-output/executive"),
        help="Base output directory",
    )
    parser.add_argument(
        "--motion-id",
        type=str,
        default=None,
        help="Limit to a single motion_id",
    )
    parser.add_argument(
        "--affected",
        type=str,
        default=None,
        help="Comma-separated affected portfolio_ids (override inference)",
    )
    parser.add_argument(
        "--owner",
        type=str,
        default=None,
        help="Plan owner portfolio_id (override inference)",
    )
    parser.add_argument(
        "--deadline-hours",
        type=int,
        default=24,
        help="Response deadline window in hours",
    )
    parser.add_argument(
        "--include-deferred",
        action="store_true",
        help="Include deferred novel proposals as HIGH-risk inputs",
    )
    parser.add_argument(
        "--draft-from-template",
        action="store_true",
        help="Generate a non-binding draft using the existing template planner",
    )
    parser.add_argument(
        "--real-agent",
        action="store_true",
        help="Enable LLM-powered classification inside the draft generator",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    if args.review_pipeline_path is None:
        args.review_pipeline_path = find_latest_review_pipeline_output()
        if args.review_pipeline_path is None:
            print("Error: No review pipeline output found. Run review pipeline first.")
            print("Looking for: _bmad-output/review-pipeline/*/")
            sys.exit(1)
        print(f"Auto-detected review pipeline output: {args.review_pipeline_path}")

    review_pipeline_path = args.review_pipeline_path
    if not review_pipeline_path.exists():
        print(f"Error: Review pipeline output not found: {review_pipeline_path}")
        sys.exit(1)

    ratification_file = review_pipeline_path / "ratification_results.json"
    if not ratification_file.exists():
        print(f"Error: No ratification_results.json found in: {review_pipeline_path}")
        sys.exit(1)

    planner_agent = None
    if args.real_agent:
        from src.infrastructure.adapters.external import create_planner_agent  # noqa: E402,I001

        print("Initializing LLM-powered planner agent for drafts...")
        llm_config = resolve_role_llm_config("EXECUTION_PLANNER_ARCHON_ID")
        planner_agent = create_planner_agent(verbose=args.verbose, llm_config=llm_config)

    # Use a neutral service to build packets and infer assignments.
    base_service = ExecutivePlanningService(
        planner_agent=planner_agent,
        verbose=args.verbose,
    )

    packets = base_service.build_ratified_intent_packets(
        review_pipeline_path=review_pipeline_path,
        include_deferred=args.include_deferred,
    )
    if args.motion_id:
        packets = [p for p in packets if p.motion_id == args.motion_id]

    if not packets:
        print("No ratified intent packets found for the given inputs.")
        sys.exit(1)

    pipeline_result = json.loads(
        (review_pipeline_path / "pipeline_result.json").read_text(encoding="utf-8")
    )
    session_id = pipeline_result.get("session_id", "unknown-session")
    session_dir = args.outdir / session_id
    session_dir.mkdir(parents=True, exist_ok=True)

    _save_json(session_dir / "ratified-intent-packets.json", [p.to_dict() for p in packets])

    affected_override = _parse_list_arg(args.affected)
    owner_override = args.owner
    deadline = (
        datetime.now(timezone.utc) + timedelta(hours=args.deadline_hours)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")

    cycle_summaries: list[dict] = []
    for packet in packets:
        events: list[dict] = []
        service = ExecutivePlanningService(
            event_sink=lambda event_type, payload, events=events: events.append(
                {"type": event_type, "payload": payload}
            ),
            planner_agent=planner_agent,
            verbose=args.verbose,
        )

        if affected_override and owner_override:
            affected_ids = list(affected_override)
            owner_id = owner_override
        else:
            affected_ids, owner_id = service.infer_assignment(packet)

        if owner_id not in affected_ids:
            affected_ids = [owner_id, *affected_ids]

        assignment = service.run_assignment_session(
            packet=packet,
            affected_portfolio_ids=affected_ids,
            plan_owner_portfolio_id=owner_id,
            response_deadline_iso=deadline,
        )

        draft_plan = None
        if args.draft_from_template:
            draft_plan = service.generate_template_draft(packet, review_pipeline_path)

        # E2 collection is external; we currently proceed with empty responses.
        contributions: list = []
        attestations: list = []
        result = service.integrate_execution_plan(
            packet=packet,
            assignment_record=assignment,
            contributions=contributions,
            attestations=attestations,
            draft_plan=draft_plan,
        )

        motion_dir = session_dir / "motions" / packet.motion_id
        _save_json(motion_dir / "ratified-intent-packet.json", packet.to_dict())
        _save_json(motion_dir / "executive_assignment_record.json", assignment)
        _save_json(motion_dir / "execution_plan.json", result.execution_plan)
        _save_json(motion_dir / "executive_gates.json", result.gates.to_dict())
        _save_jsonl(motion_dir / "executive_events.jsonl", events)

        handoff = {
            "cycle_id": result.cycle_id,
            "motion_id": packet.motion_id,
            "execution_plan_path": str((motion_dir / "execution_plan.json").resolve()),
            "constraints_spotlight": packet.ratified_motion.get("constraints", []),
            "blockers_requiring_escalation": [
                b.to_dict() for b in result.blockers_requiring_escalation
            ],
            "gates": result.gates.to_dict(),
            "created_at": now_iso(),
        }
        _save_json(motion_dir / "execution_plan_handoff.json", handoff)

        cycle_summaries.append(
            {
                "motion_id": packet.motion_id,
                "cycle_id": result.cycle_id,
                "plan_owner": result.plan_owner.to_dict(),
                "gates": result.gates.to_dict(),
                "blockers_requiring_escalation": len(result.blockers_requiring_escalation),
                "motion_dir": str(motion_dir),
            }
        )

    _save_json(session_dir / "executive_cycle_summaries.json", cycle_summaries)

    print("\n" + "=" * 60)
    print("EXECUTIVE PIPELINE COMPLETE")
    print("=" * 60)
    print(f"Session: {session_id}")
    print(f"Ratified motions processed: {len(packets)}")
    failures = sum(
        1 for s in cycle_summaries if "FAIL" in s.get("gates", {}).values()
    )
    print(f"Gate failures: {failures}")
    print(f"Output saved to: {session_dir}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
