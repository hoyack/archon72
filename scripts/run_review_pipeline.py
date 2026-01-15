#!/usr/bin/env python3
"""Run the Motion Review Pipeline to process consolidated mega-motions.

Usage:
    python scripts/run_review_pipeline.py [consolidator_output_path] [options]

Examples:
    # Full pipeline with simulation (default)
    python scripts/run_review_pipeline.py

    # Triage only (no simulation)
    python scripts/run_review_pipeline.py --triage-only

    # Specific consolidator session
    python scripts/run_review_pipeline.py _bmad-output/consolidator/c53dba60-...

    # With verbose logging
    python scripts/run_review_pipeline.py --verbose

    # With real LLM-powered Archon reviews (requires API keys)
    python scripts/run_review_pipeline.py --real-agent
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

from src.application.services.motion_review_service import MotionReviewService


def find_latest_consolidator_output() -> Path | None:
    """Find the most recent consolidator output directory."""
    pattern = "_bmad-output/consolidator/*"
    dirs = [d for d in glob.glob(pattern) if Path(d).is_dir()]
    if not dirs:
        return None
    # Return most recently modified
    return Path(max(dirs, key=lambda d: Path(d).stat().st_mtime))


def create_reviewer_agent(verbose: bool = False):
    """Create a ReviewerCrewAIAdapter with per-Archon LLM bindings.

    This loads the ArchonProfileRepository which provides each Archon
    with their specific LLM configuration from archon-llm-bindings.yaml.
    Local models use Ollama via OLLAMA_HOST environment variable.
    """
    try:
        from src.infrastructure.adapters.config.archon_profile_adapter import (
            CsvYamlArchonProfileAdapter,
        )
        from src.infrastructure.adapters.external.reviewer_crewai_adapter import (
            create_reviewer_agent as create_agent,
        )

        # Load profile repository with per-Archon LLM configs
        profile_repo = CsvYamlArchonProfileAdapter(
            csv_path="docs/archons-base.csv",
            llm_config_path="config/archon-llm-bindings.yaml",
        )

        return create_agent(
            profile_repository=profile_repo,
            verbose=verbose,
        )
    except ImportError as e:
        print(f"Warning: Could not create ReviewerAgent: {e}")
        print("Make sure crewai and anthropic packages are installed.")
        return None
    except FileNotFoundError as e:
        print(f"Warning: Config files not found: {e}")
        print("Falling back to default LLM configuration.")
        # Try without profile repository (will use default LLM)
        try:
            from src.infrastructure.adapters.external.reviewer_crewai_adapter import (
                create_reviewer_agent as create_agent,
            )
            return create_agent(verbose=verbose)
        except ImportError:
            return None


async def run_async_pipeline(service, consolidator_path, output_dir):
    """Run the async pipeline with real agent reviews."""
    result = await service.run_full_pipeline_async(
        consolidator_path,
        use_real_agent=True,
    )
    session_dir = service.save_results(result, output_dir)
    return result, session_dir


def main():
    parser = argparse.ArgumentParser(
        description="Run Motion Review Pipeline on consolidated mega-motions",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "consolidator_path",
        type=Path,
        nargs="?",
        default=None,
        help="Path to consolidator output directory (auto-detects if not specified)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging",
    )
    parser.add_argument(
        "--triage-only",
        action="store_true",
        help="Run only Phase 1 (triage) without simulation",
    )
    parser.add_argument(
        "--no-simulate",
        action="store_true",
        help="Skip review simulation (produces triage + packets only)",
    )
    parser.add_argument(
        "--real-agent",
        action="store_true",
        help="Use real LLM-powered Archon reviews (requires API keys)",
    )

    args = parser.parse_args()

    # Find consolidator output if not specified
    if args.consolidator_path is None:
        args.consolidator_path = find_latest_consolidator_output()
        if args.consolidator_path is None:
            print("Error: No consolidator output found. Run consolidator first.")
            print("Looking for: _bmad-output/consolidator/*/")
            sys.exit(1)
        print(f"Auto-detected consolidator output: {args.consolidator_path}")

    # Validate path exists
    if not args.consolidator_path.exists():
        print(f"Error: Consolidator output not found: {args.consolidator_path}")
        sys.exit(1)

    # Create reviewer agent if using real reviews
    reviewer_agent = None
    if args.real_agent:
        print("Initializing ReviewerAgent for real LLM-powered reviews...")
        print("Loading per-Archon LLM bindings from archon-llm-bindings.yaml...")
        reviewer_agent = create_reviewer_agent(verbose=args.verbose)
        if reviewer_agent is None:
            print("Error: Could not create ReviewerAgent. Falling back to simulation.")
            args.real_agent = False
        else:
            print("Per-Archon LLM bindings loaded successfully.")

    # Print header
    print(f"\n{'='*60}")
    print("MOTION REVIEW PIPELINE")
    print(f"{'='*60}")
    print(f"Input: {args.consolidator_path}")
    print(f"Verbose: {args.verbose}")
    print(f"Triage Only: {args.triage_only}")
    print(f"Real Agent: {args.real_agent}")
    print(f"Simulate Reviews: {not args.no_simulate and not args.triage_only and not args.real_agent}")
    print(f"{'='*60}\n")

    # Initialize service
    service = MotionReviewService(verbose=args.verbose, reviewer_agent=reviewer_agent)

    # Load data
    mega_motions, novel_proposals, session_id, session_name = service.load_mega_motions(
        args.consolidator_path
    )

    print(f"Session: {session_name}")
    print(f"Session ID: {session_id}")
    print(f"Mega-motions loaded: {len(mega_motions)}")
    print(f"Novel proposals loaded: {len(novel_proposals)}")

    if args.triage_only:
        # Run triage only
        print("\n--- Phase 1: Triage ---")
        triage_result = service.triage_motions(mega_motions, novel_proposals, session_id)

        print(f"\nTriage Results:")
        print(f"  Total motions: {triage_result.total_motions}")
        print(f"  LOW risk (fast-track): {triage_result.low_risk_count}")
        print(f"  MEDIUM risk (targeted review): {triage_result.medium_risk_count}")
        print(f"  HIGH risk (panel deliberation): {triage_result.high_risk_count}")
        print(f"  Average implicit support: {triage_result.average_implicit_support:.1%}")
        print(f"  Conflicts detected: {triage_result.total_conflicts_detected}")

        print("\n--- Motion Risk Breakdown ---")
        for i, support in enumerate(triage_result.implicit_supports, 1):
            tier_emoji = {"low": "🟢", "medium": "🟡", "high": "🔴"}[support.risk_tier.value]
            print(f"{i:2}. {tier_emoji} [{support.risk_tier.value.upper():6}] {support.mega_motion_title[:45]}...")
            print(f"    Implicit support: {support.implicit_support_ratio:.0%} ({support.support_count}/72)")
            print(f"    Gap Archons: {support.gap_count}")
            if support.is_novel_proposal:
                print(f"    ⚠️  Novel proposal - requires full deliberation")
            print()

    elif args.real_agent:
        # Run async pipeline with real agent
        print("\nRunning full pipeline with real Archon agents...")
        output_dir = Path("_bmad-output/review-pipeline")

        result, session_dir = asyncio.run(
            run_async_pipeline(service, args.consolidator_path, output_dir)
        )

        # Print summary
        print_pipeline_summary(result, session_dir, real_agent=True)

    else:
        # Run full pipeline with simulation
        print("\nRunning full pipeline with simulated reviews...")
        simulate = not args.no_simulate

        result = service.run_full_pipeline(
            args.consolidator_path,
            simulate=simulate,
        )

        # Save results
        output_dir = Path("_bmad-output/review-pipeline")
        session_dir = service.save_results(result, output_dir)

        # Print summary
        print_pipeline_summary(result, session_dir, real_agent=False)


def print_pipeline_summary(result, session_dir, real_agent: bool = False):
    """Print the pipeline summary."""
    print(f"\n{'='*60}")
    print("PIPELINE COMPLETE")
    print(f"{'='*60}")
    print(f"Session: {result.session_name}")
    print(f"Session ID: {result.session_id}")
    print(f"Mode: {'Real Agent Reviews' if real_agent else 'Simulated Reviews'}")

    if result.triage_result:
        print(f"\n--- Phase 1: Triage ---")
        print(f"  LOW risk (fast-track): {result.triage_result.low_risk_count}")
        print(f"  MEDIUM risk (targeted review): {result.triage_result.medium_risk_count}")
        print(f"  HIGH risk (panel deliberation): {result.triage_result.high_risk_count}")

    print(f"\n--- Phase 2: Packet Generation ---")
    print(f"  Total assignments: {result.total_assignments}")
    print(f"  Avg per Archon: {result.average_assignments_per_archon:.1f}")

    if result.review_responses:
        print(f"\n--- Phase 3-4: Review & Aggregation ---")
        print(f"  Responses collected: {len(result.review_responses)}")
        print(f"  Response rate: {result.response_rate:.0%}")
        consensus_count = sum(1 for a in result.aggregations if a.consensus_reached)
        contested_count = sum(1 for a in result.aggregations if a.contested)
        print(f"  Consensus reached: {consensus_count}")
        print(f"  Contested: {contested_count}")

        print(f"\n--- Phase 5: Panel Deliberation ---")
        print(f"  Panels convened: {result.panels_convened}")

        print(f"\n--- Phase 6: Ratification ---")
        print(f"  Motions ratified: {result.motions_ratified}")
        print(f"  Motions rejected: {result.motions_rejected}")
        print(f"  Motions deferred: {result.motions_deferred}")

    print(f"\nOutput saved to: {session_dir}")
    print(f"{'='*60}\n")

    # Print motion status summary
    if result.ratification_votes:
        print("RATIFICATION RESULTS:")
        print("-" * 60)
        for i, vote in enumerate(result.ratification_votes, 1):
            outcome_emoji = {
                "ratified": "✅",
                "rejected": "❌",
                "deferred": "⏸️",
            }[vote.outcome.value]
            print(f"{i:2}. {outcome_emoji} {vote.mega_motion_title[:45]}...")
            print(f"    Yeas: {vote.yeas} | Nays: {vote.nays} | Abstain: {vote.abstentions}")
            print(f"    Threshold: {vote.threshold_type} ({vote.threshold_required}) - {'MET' if vote.threshold_met else 'NOT MET'}")
            print()


if __name__ == "__main__":
    main()
