#!/usr/bin/env python3
"""Run the Execution Planner to transform ratified motions into execution plans.

Usage:
    python scripts/run_execution_planner.py [review_pipeline_path] [options]

Examples:
    # Plan from latest review pipeline output (heuristic mode)
    python scripts/run_execution_planner.py

    # Plan from specific review pipeline session
    python scripts/run_execution_planner.py _bmad-output/review-pipeline/c53dba60-...

    # With verbose logging
    python scripts/run_execution_planner.py --verbose

    # With LLM-powered classification (requires API keys)
    python scripts/run_execution_planner.py --real-agent
"""

import argparse
import asyncio
import glob
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

from src.application.services.execution_planner_service import ExecutionPlannerService


def find_latest_review_pipeline_output() -> Path | None:
    """Find the most recent review pipeline output directory."""
    pattern = "_bmad-output/review-pipeline/*"
    dirs = [d for d in glob.glob(pattern) if Path(d).is_dir()]
    if not dirs:
        return None
    # Return most recently modified
    return Path(max(dirs, key=lambda d: Path(d).stat().st_mtime))


def main():
    parser = argparse.ArgumentParser(
        description="Run Execution Planner on ratified motions",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "review_pipeline_path",
        type=Path,
        nargs="?",
        default=None,
        help="Path to review pipeline output directory (auto-detects if not specified)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging",
    )
    parser.add_argument(
        "--real-agent",
        action="store_true",
        help="Use LLM-powered classification (requires API keys)",
    )

    args = parser.parse_args()

    # Find review pipeline output if not specified
    if args.review_pipeline_path is None:
        args.review_pipeline_path = find_latest_review_pipeline_output()
        if args.review_pipeline_path is None:
            print("Error: No review pipeline output found. Run review pipeline first.")
            print("Looking for: _bmad-output/review-pipeline/*/")
            sys.exit(1)
        print(f"Auto-detected review pipeline output: {args.review_pipeline_path}")

    # Validate path exists
    if not args.review_pipeline_path.exists():
        print(f"Error: Review pipeline output not found: {args.review_pipeline_path}")
        sys.exit(1)

    # Check for ratification results
    ratification_file = args.review_pipeline_path / "ratification_results.json"
    if not ratification_file.exists():
        print(
            f"Error: No ratification_results.json found in: {args.review_pipeline_path}"
        )
        sys.exit(1)

    # Print header
    print(f"\n{'=' * 60}")
    print("EXECUTION PLANNER")
    print(f"{'=' * 60}")
    print(f"Input: {args.review_pipeline_path}")
    print(f"Verbose: {args.verbose}")
    print(f"Mode: {'LLM-powered' if args.real_agent else 'Heuristic'}")
    print(f"{'=' * 60}\n")

    # Initialize service
    planner_agent = None
    if args.real_agent:
        from src.infrastructure.adapters.external import create_planner_agent

        print("Initializing LLM-powered planner agent...")
        planner_agent = create_planner_agent(verbose=args.verbose)

    service = ExecutionPlannerService(
        verbose=args.verbose,
        planner_agent=planner_agent,
    )

    # Run planning pipeline
    if args.real_agent and planner_agent:
        result = asyncio.run(
            service.run_planning_pipeline_async(args.review_pipeline_path)
        )
    else:
        result = service.run_planning_pipeline(args.review_pipeline_path)

    # Save results
    output_dir = Path("_bmad-output/execution-planner")
    session_dir = service.save_results(result, output_dir)

    # Print summary
    print_planning_summary(result, session_dir)


def print_planning_summary(result, session_dir):
    """Print the planning pipeline summary."""
    print(f"\n{'=' * 60}")
    print("PLANNING COMPLETE")
    print(f"{'=' * 60}")
    print(f"Session: {result.session_name}")
    print(f"Session ID: {result.session_id}")

    print("\n--- Summary ---")
    print(f"  Motions processed: {result.total_motions_processed}")
    print(f"  Execution plans generated: {len(result.plans)}")
    print(f"  Total tasks created: {result.total_tasks_generated}")
    print(f"  Blockers identified: {result.total_blockers_identified}")
    print(f"  Blockers requiring Conclave: {result.blockers_requiring_conclave}")

    print("\n--- Pattern Usage ---")
    for pattern_id, count in sorted(
        result.patterns_used.items(), key=lambda x: x[1], reverse=True
    ):
        print(f"  {pattern_id}: {count} motions")

    print(f"\nOutput saved to: {session_dir}")
    print(f"{'=' * 60}\n")

    # Print plan summaries
    print("EXECUTION PLANS:")
    print("-" * 60)
    for i, plan in enumerate(result.plans, 1):
        pattern_emoji = {
            "CONST": "📜",
            "POLICY": "📋",
            "TECH": "🔧",
            "PROC": "📝",
            "RESEARCH": "🔬",
            "ORG": "👥",
            "RESOURCE": "💰",
            "ARCHON": "🤖",
        }.get(plan.classification.primary_pattern, "📄")

        blocker_warning = f" ⚠️ {len(plan.blockers)} blockers" if plan.blockers else ""

        print(
            f"{i:2}. {pattern_emoji} [{plan.classification.primary_pattern}] {plan.motion_title[:45]}..."
        )
        print(
            f"    Tasks: {plan.total_tasks} | Effort: {plan.estimated_total_effort}{blocker_warning}"
        )

        if plan.blockers:
            conclave_count = sum(1 for b in plan.blockers if b.escalate_to_conclave)
            if conclave_count > 0:
                print(f"    🚨 {conclave_count} blocker(s) need Conclave escalation")
        print()

    # Print Conclave escalations
    conclave_blockers = [
        (plan.motion_title, blocker)
        for plan in result.plans
        for blocker in plan.blockers
        if blocker.escalate_to_conclave
    ]

    if conclave_blockers:
        print("\n" + "=" * 60)
        print("CONCLAVE ESCALATIONS (Agenda Items for Next Session)")
        print("=" * 60)
        for i, (motion_title, blocker) in enumerate(conclave_blockers, 1):
            print(f"{i}. {blocker.suggested_agenda_item or blocker.description}")
            print(f"   Motion: {motion_title[:50]}...")
            print()


if __name__ == "__main__":
    main()
