#!/usr/bin/env python3
"""Run Executive Review (E4) on implementation proposals from Administration.

This stage evaluates implementation proposals and determines:
- Accept and proceed to Earl tasking
- Request revisions from Administration
- Escalate to Conclave for governance-level decisions

Two Feedback Loops:
1. Implementation Loop (frequent): Executive -> Administrative -> Executive
2. Intent Loop (rare): Executive -> Conclave (only for INTENT_AMBIGUITY)

Pipeline Flow:
Executive Pipeline + Administrative Pipeline -> Executive Review
                                             -> plan_acceptance.json (proceed)
                                             -> revision_request.json (iterate)
                                             -> conclave_escalation.json (rare)
"""

from __future__ import annotations

import argparse
import glob
import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

from src.application.services.executive_review_service import (  # noqa: E402
    ExecutiveReviewService,
    now_iso,
)


def find_latest_executive_output() -> Path | None:
    """Find the most recent Executive Pipeline output directory."""
    pattern = "_bmad-output/executive/*"
    dirs = [d for d in glob.glob(pattern) if Path(d).is_dir()]
    if not dirs:
        return None
    return Path(max(dirs, key=lambda d: Path(d).stat().st_mtime))


def find_latest_admin_output() -> Path | None:
    """Find the most recent Administrative Pipeline output directory."""
    pattern = "_bmad-output/administrative/*"
    dirs = [d for d in glob.glob(pattern) if Path(d).is_dir()]
    if not dirs:
        return None
    return Path(max(dirs, key=lambda d: Path(d).stat().st_mtime))


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


def _load_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _create_reviewer(args: argparse.Namespace):
    if args.mode not in ("llm", "auto"):
        return None
    try:
        from src.infrastructure.adapters.config.archon_profile_adapter import (
            create_archon_profile_repository,
        )
        from src.infrastructure.adapters.external.executive_review_crewai_adapter import (
            create_executive_reviewer,
        )

        profile_repo = create_archon_profile_repository()
        reviewer = create_executive_reviewer(
            profile_repository=profile_repo,
            verbose=args.verbose,
        )
        print("  Loaded per-Archon LLM bindings for proposal review")
        return reviewer
    except ImportError as e:
        print(f"  Warning: Could not load LLM reviewer: {e}")
        print("  Falling back to simulation mode")
        return None


def _load_execution_plan(
    service: ExecutiveReviewService, executive_output_path: Path, motion_id: str
) -> tuple[dict | None, dict | None]:
    try:
        plan = service.load_execution_plan(
            executive_output_path=executive_output_path,
            motion_id=motion_id,
        )
        return plan, None
    except FileNotFoundError as e:
        print(f"  Error: {e}")
        return None, {"motion_id": motion_id, "error": str(e)}


def _load_proposals(
    service: ExecutiveReviewService,
    admin_output_path: Path,
    motion_id: str,
    cycle_id: str,
) -> tuple[list[dict] | None, dict | None]:
    try:
        proposals = service.load_implementation_proposals(
            admin_output_path=admin_output_path,
            motion_id=motion_id,
        )
        return proposals, None
    except FileNotFoundError as e:
        print(f"  Error: {e}")
        return None, {"motion_id": motion_id, "cycle_id": cycle_id, "error": str(e)}


def _resolve_iteration_number(session_dir: Path, motion_id: str) -> int:
    iteration_number = 1
    existing_result_path = session_dir / motion_id / "review_result.json"
    if existing_result_path.exists():
        existing_result = _load_json(existing_result_path)
        iteration_number = existing_result.get("iteration_number", 1) + 1
        print(f"  Continuing from iteration {iteration_number - 1}")
    return iteration_number


def _run_review(
    service: ExecutiveReviewService,
    args: argparse.Namespace,
    plan: dict,
    proposals: list[dict],
    resource_summary: dict | None,
    iteration_number: int,
    motion_id: str,
):
    if args.mode in ("llm", "auto") and service._reviewer is not None:
        import asyncio

        print(f"  Running LLM review for {motion_id} (iteration {iteration_number})...")
        try:
            return asyncio.run(
                service.run_review(
                    plan=plan,
                    proposals=proposals,
                    resource_summary=resource_summary,
                    iteration_number=iteration_number,
                )
            )
        except Exception as e:
            print(f"  LLM error: {e}")
            print("  Falling back to simulation mode...")

    if args.mode == "llm":
        print(
            f"  LLM reviewer not configured, using simulation for {motion_id} "
            f"(iteration {iteration_number})..."
        )
    else:
        print(
            f"  Running review (simulation) for {motion_id} "
            f"(iteration {iteration_number})..."
        )

    return service.run_review_simulation(
        plan=plan,
        proposals=proposals,
        resource_summary=resource_summary,
        iteration_number=iteration_number,
    )


def _determine_next_action(result) -> str:
    if result.all_accepted():
        return "proceed_to_earl_tasking"
    if result.max_iterations_reached:
        return "escalate_to_conclave"
    if result.needs_iteration():
        return "iterate_with_administration"
    return "unknown"


def _print_review_outcome(result, max_iterations: int) -> None:
    if result.all_accepted():
        print(f"  ACCEPTED: All {result.accepted_count} proposal(s) approved")
    elif result.revision_count > 0:
        print(
            f"  REVISIONS: {result.revision_count} proposal(s) need revision "
            f"(iteration {result.iteration_number}/{max_iterations})"
        )
    if result.escalation_count > 0:
        print(f"  ESCALATIONS: {result.escalation_count} escalation(s) to Conclave")


def _process_motion(
    motion_id: str,
    executive_output_path: Path,
    admin_output_path: Path,
    session_dir: Path,
    args: argparse.Namespace,
) -> dict:
    """Process a single motion through Executive Review."""
    events: list[dict] = []

    # Create event sink
    def event_sink(event_type: str, payload: dict) -> None:
        events.append({"type": event_type, "payload": payload})

    # Create reviewer based on mode
    reviewer = _create_reviewer(args)

    # Create service with event sink
    service = ExecutiveReviewService(
        event_sink=event_sink,
        reviewer=reviewer,
        max_iterations=args.max_iterations,
        verbose=args.verbose,
    )

    # Load execution plan
    plan, error = _load_execution_plan(service, executive_output_path, motion_id)
    if error:
        return error
    if plan is None:
        return {"motion_id": motion_id, "error": "Execution plan missing"}

    cycle_id = plan.get("cycle_id", "unknown")

    # Load implementation proposals
    proposals, error = _load_proposals(service, admin_output_path, motion_id, cycle_id)
    if error:
        return error

    if not proposals:
        print(f"  No proposals found for motion {motion_id}")
        return {
            "motion_id": motion_id,
            "cycle_id": cycle_id,
            "error": "No proposals found",
        }

    # Load resource summary (optional)
    resource_summary = service.load_resource_summary(
        admin_output_path=admin_output_path,
        motion_id=motion_id,
    )

    # Determine iteration number from existing results
    iteration_number = _resolve_iteration_number(session_dir, motion_id)

    # Run review based on mode
    # Note: LLM adapters not yet implemented - both 'llm' and 'auto' currently fall back to simulation
    result = _run_review(
        service,
        args,
        plan,
        proposals,
        resource_summary,
        iteration_number,
        motion_id,
    )

    # Save results
    motion_dir = service.save_results(
        result=result,
        output_dir=session_dir,
    )

    # Save events
    _save_jsonl(motion_dir / "review_events.jsonl", events)

    # Determine next action
    next_action = _determine_next_action(result)

    summary = {
        "motion_id": motion_id,
        "cycle_id": cycle_id,
        "review_id": result.review_id,
        "iteration_number": result.iteration_number,
        "total_proposals": result.total_proposals,
        "accepted": result.accepted_count,
        "revisions_requested": result.revision_count,
        "escalations": result.escalation_count,
        "all_accepted": result.all_accepted(),
        "needs_iteration": result.needs_iteration(),
        "max_iterations_reached": result.max_iterations_reached,
        "next_action": next_action,
        "motion_dir": str(motion_dir),
    }

    # Print outcome
    _print_review_outcome(result, args.max_iterations)

    return summary


def _resolve_executive_output(args: argparse.Namespace) -> Path:
    if args.executive_output_path is None:
        args.executive_output_path = find_latest_executive_output()
        if args.executive_output_path is None:
            print("Error: No Executive Pipeline output found.")
            print("Run Executive Pipeline first or specify path explicitly.")
            print("Looking for: _bmad-output/executive/*/")
            sys.exit(1)
        print(f"Auto-detected Executive output: {args.executive_output_path}")

    executive_output_path = args.executive_output_path.resolve()
    if not executive_output_path.exists():
        print(f"Error: Executive output not found: {executive_output_path}")
        sys.exit(1)
    return executive_output_path


def _resolve_admin_output(
    args: argparse.Namespace, executive_output_path: Path
) -> Path:
    if args.admin_output_path is None:
        session_id = executive_output_path.name
        admin_path = Path("_bmad-output/administrative") / session_id
        if admin_path.exists():
            args.admin_output_path = admin_path
        else:
            args.admin_output_path = find_latest_admin_output()

        if args.admin_output_path is None:
            print("Error: No Administrative Pipeline output found.")
            print("Run Administrative Pipeline first or specify path explicitly.")
            print("Looking for: _bmad-output/administrative/*/")
            sys.exit(1)
        print(f"Auto-detected Administrative output: {args.admin_output_path}")

    admin_output_path = args.admin_output_path.resolve()
    if not admin_output_path.exists():
        print(f"Error: Administrative output not found: {admin_output_path}")
        sys.exit(1)
    return admin_output_path


def _collect_motion_ids(admin_output_path: Path, motion_id: str | None) -> list[str]:
    if motion_id:
        return [motion_id]
    motion_ids: list[str] = []
    for motion_dir in admin_output_path.iterdir():
        if motion_dir.is_dir() and (motion_dir / "pipeline_summary.json").exists():
            motion_ids.append(motion_dir.name)
    return motion_ids


def _write_pipeline_summary(
    session_dir: Path,
    session_id: str,
    args: argparse.Namespace,
    summaries: list[dict],
) -> tuple[dict, bool]:
    total_accepted = sum(s.get("accepted", 0) for s in summaries if "error" not in s)
    total_revisions = sum(
        s.get("revisions_requested", 0) for s in summaries if "error" not in s
    )
    total_escalations = sum(
        s.get("escalations", 0) for s in summaries if "error" not in s
    )
    all_accepted = all(
        s.get("all_accepted", False) for s in summaries if "error" not in s
    )
    has_errors = any("error" in s for s in summaries)

    pipeline_summary = {
        "session_id": session_id,
        "created_at": now_iso(),
        "mode": args.mode,
        "max_iterations": args.max_iterations,
        "motions_reviewed": len(summaries),
        "total_proposals_accepted": total_accepted,
        "total_revisions_requested": total_revisions,
        "total_escalations": total_escalations,
        "all_accepted": all_accepted,
        "motion_summaries": summaries,
    }
    _save_json(session_dir / "review_pipeline_summary.json", pipeline_summary)
    return (
        {
            "total_accepted": total_accepted,
            "total_revisions": total_revisions,
            "total_escalations": total_escalations,
            "all_accepted": all_accepted,
        },
        has_errors,
    )


def _print_pipeline_summary(
    session_id: str,
    summaries: list[dict],
    totals: dict,
    args: argparse.Namespace,
    session_dir: Path,
) -> None:
    print("\n" + "=" * 60)
    print("EXECUTIVE REVIEW COMPLETE")
    print("=" * 60)
    print(f"Session: {session_id}")
    print(f"Motions reviewed: {len(summaries)}")
    print(f"Proposals accepted: {totals['total_accepted']}")
    print(f"Revisions requested: {totals['total_revisions']}")
    print(f"Escalations to Conclave: {totals['total_escalations']}")
    print(f"Mode: {args.mode}")
    print(f"Max iterations: {args.max_iterations}")
    print(f"Output saved to: {session_dir}")

    if totals["all_accepted"]:
        print("\nSTATUS: ALL PROPOSALS ACCEPTED - Proceed to Earl tasking")
    elif totals["total_escalations"] > 0:
        print("\nSTATUS: ESCALATIONS REQUIRED - Conclave review needed")
    elif totals["total_revisions"] > 0:
        print("\nSTATUS: REVISIONS NEEDED - Iterate with Administration")

    print("=" * 60 + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run Executive Review (E4) on implementation proposals"
    )
    parser.add_argument(
        "executive_output_path",
        type=Path,
        nargs="?",
        default=None,
        help="Path to Executive Pipeline output directory (auto-detects if not specified)",
    )
    parser.add_argument(
        "admin_output_path",
        type=Path,
        nargs="?",
        default=None,
        help="Path to Administrative Pipeline output directory (auto-detects if not specified)",
    )
    parser.add_argument(
        "--outdir",
        type=Path,
        default=Path("_bmad-output/executive-review"),
        help="Base output directory",
    )
    parser.add_argument(
        "--motion-id",
        type=str,
        default=None,
        help="Limit to a single motion_id",
    )
    parser.add_argument(
        "--mode",
        type=str,
        choices=["manual", "llm", "auto", "simulation"],
        default="auto",
        help=(
            "Review mode: 'manual' for human review, "
            "'llm' uses LLM, 'auto' uses LLM when available, "
            "'simulation' generates test reviews (default: auto)"
        ),
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=3,
        help="Maximum iterations before forced escalation (default: 3)",
    )
    parser.add_argument(
        "--require-acceptance",
        action="store_true",
        help="Exit 1 if any revisions are requested",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    executive_output_path = _resolve_executive_output(args)
    admin_output_path = _resolve_admin_output(args, executive_output_path)

    motion_ids = _collect_motion_ids(admin_output_path, args.motion_id)
    if not motion_ids:
        print("No motions found to review.")
        sys.exit(1)

    session_id = executive_output_path.name
    session_dir = args.outdir / session_id
    session_dir.mkdir(parents=True, exist_ok=True)

    print(f"\nReviewing {len(motion_ids)} motion(s)...")

    summaries: list[dict] = []
    for motion_id in motion_ids:
        print(f"\nReviewing motion: {motion_id}")

        summary = _process_motion(
            motion_id=motion_id,
            executive_output_path=executive_output_path,
            admin_output_path=admin_output_path,
            session_dir=session_dir,
            args=args,
        )
        summaries.append(summary)

    totals, has_errors = _write_pipeline_summary(
        session_dir, session_id, args, summaries
    )
    _print_pipeline_summary(session_id, summaries, totals, args, session_dir)

    if args.require_acceptance and (totals["total_revisions"] > 0 or has_errors):
        print("ERROR: Acceptance required but revisions exist. Review blocked.")
        sys.exit(1)


if __name__ == "__main__":
    main()
