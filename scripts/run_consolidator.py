#!/usr/bin/env python3
"""Run the Motion Consolidator to reduce motions for sustainable deliberation.

Usage:
    python scripts/run_consolidator.py <motions_checkpoint> [options]

Examples:
    # Full consolidation with all analysis vectors
    python scripts/run_consolidator.py

    # Basic consolidation only (no novelty, summary, or acronyms)
    python scripts/run_consolidator.py --basic

    # Custom target count
    python scripts/run_consolidator.py --target 10

    # Skip specific analysis
    python scripts/run_consolidator.py --no-novelty --no-summary

    # With verbose LLM logging
    python scripts/run_consolidator.py --verbose
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

from src.application.services.motion_consolidator_service import (
    MotionConsolidatorService,
)


def find_latest_motions_checkpoint() -> Path | None:
    """Find the most recent motions checkpoint file."""
    pattern = "_bmad-output/secretary/checkpoints/*_05_motions.json"
    files = glob.glob(pattern)
    if not files:
        return None
    # Return most recently modified
    return Path(max(files, key=lambda f: Path(f).stat().st_mtime))


async def run_consolidator(
    checkpoint_path: Path,
    target_count: int,
    verbose: bool,
    run_novelty: bool,
    run_summary: bool,
    run_acronyms: bool,
) -> None:
    """Run the motion consolidator with full analysis."""
    print(f"\n{'=' * 60}")
    print("MOTION CONSOLIDATOR")
    print(f"{'=' * 60}")
    print(f"Input: {checkpoint_path}")
    print(f"Target Mega-Motions: {target_count}")
    print(f"Novelty Detection: {'Enabled' if run_novelty else 'Disabled'}")
    print(f"Conclave Summary: {'Enabled' if run_summary else 'Disabled'}")
    print(f"Acronym Registry: {'Enabled' if run_acronyms else 'Disabled'}")
    print(f"Verbose: {verbose}")
    print(f"{'=' * 60}\n")

    # Initialize consolidator
    consolidator = MotionConsolidatorService(
        verbose=verbose,
        target_count=target_count,
    )

    # Run full consolidation
    print("Running full consolidation...")
    result = await consolidator.consolidate_full(
        motions_checkpoint=checkpoint_path,
        run_novelty=run_novelty,
        run_summary=run_summary,
        run_acronyms=run_acronyms,
    )

    # Save results to session-based directory
    output_dir = Path("_bmad-output/consolidator")
    session_dir = consolidator.save_full_results(result, output_dir)

    # Print summary
    print(f"\n{'=' * 60}")
    print("CONSOLIDATION COMPLETE")
    print(f"{'=' * 60}")
    print(f"Session: {result.session_name}")
    print(f"Session ID: {result.session_id}")
    print("\n--- Consolidation ---")
    print(f"Original Motions: {result.consolidation.original_motion_count}")
    print(f"Mega-Motions Created: {len(result.consolidation.mega_motions)}")
    print(f"Consolidation Ratio: {result.consolidation.consolidation_ratio:.1%}")
    print(f"Traceability Complete: {result.consolidation.traceability_complete}")
    if result.consolidation.orphaned_motions:
        print(f"Orphaned Motions: {len(result.consolidation.orphaned_motions)}")

    if result.novel_proposals:
        print("\n--- Novelty Detection ---")
        print(f"Novel Proposals Found: {len(result.novel_proposals)}")
        categories = {}
        for p in result.novel_proposals:
            categories[p.category] = categories.get(p.category, 0) + 1
        for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
            print(f"  {cat}: {count}")

    if result.conclave_summary:
        print("\n--- Conclave Summary ---")
        print(f"Key Themes: {len(result.conclave_summary.key_themes)}")
        print(f"Areas of Consensus: {len(result.conclave_summary.areas_of_consensus)}")
        print(
            f"Points of Contention: {len(result.conclave_summary.points_of_contention)}"
        )

    if result.acronym_registry:
        print("\n--- Acronym Registry ---")
        print(f"Acronyms Catalogued: {len(result.acronym_registry)}")
        top_acronyms = result.acronym_registry[:5]
        for a in top_acronyms:
            print(f"  {a.acronym}: {a.full_form} ({a.usage_count}x)")

    print(f"\nOutput saved to: {session_dir}")
    print(f"{'=' * 60}\n")

    # Print mega-motion summary
    print("MEGA-MOTIONS SUMMARY:")
    print("-" * 60)
    for i, mm in enumerate(result.consolidation.mega_motions, 1):
        tier_emoji = {"high": "🟢", "medium": "🟡", "low": "🔵"}.get(
            mm.consensus_tier, "⚪"
        )
        print(f"{i:2}. {tier_emoji} {mm.title[:50]}...")
        print(f"    Theme: {mm.theme}")
        print(
            f"    Archons: {mm.unique_archon_count} | Sources: {len(mm.source_motion_ids)} motions"
        )
        print()

    # Print novel proposals if any
    if result.novel_proposals:
        print("\nNOVEL PROPOSALS (Top 5):")
        print("-" * 60)
        for i, p in enumerate(result.novel_proposals[:5], 1):
            score_bar = "█" * int(p.novelty_score * 10) + "░" * (
                10 - int(p.novelty_score * 10)
            )
            print(f"{i}. [{p.category.upper()}] {score_bar} ({p.novelty_score:.0%})")
            print(f"   Archon: {p.archon_name}")
            print(f"   {p.text[:100]}...")
            print(f"   Why: {p.novelty_reason[:80]}...")
            print()


def main():
    parser = argparse.ArgumentParser(
        description="Consolidate Secretary motions into mega-motions with full analysis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "checkpoint",
        type=Path,
        nargs="?",
        default=None,
        help="Path to *_05_motions.json checkpoint (auto-detects if not specified)",
    )
    parser.add_argument(
        "--target",
        "-t",
        type=int,
        default=12,
        help="Target number of mega-motions (default: 12)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose LLM logging",
    )
    parser.add_argument(
        "--basic",
        action="store_true",
        help="Run basic consolidation only (skip novelty, summary, acronyms)",
    )
    parser.add_argument(
        "--no-novelty",
        action="store_true",
        help="Skip novelty detection",
    )
    parser.add_argument(
        "--no-summary",
        action="store_true",
        help="Skip conclave summary generation",
    )
    parser.add_argument(
        "--no-acronyms",
        action="store_true",
        help="Skip acronym registry extraction",
    )

    args = parser.parse_args()

    # Find checkpoint if not specified
    if args.checkpoint is None:
        args.checkpoint = find_latest_motions_checkpoint()
        if args.checkpoint is None:
            print("Error: No motions checkpoint found. Run Secretary first.")
            print("Looking for: _bmad-output/secretary/checkpoints/*_05_motions.json")
            sys.exit(1)
        print(f"Auto-detected checkpoint: {args.checkpoint}")

    # Validate checkpoint exists
    if not args.checkpoint.exists():
        print(f"Error: Checkpoint not found: {args.checkpoint}")
        sys.exit(1)

    # Determine which analyses to run
    if args.basic:
        run_novelty = False
        run_summary = False
        run_acronyms = False
    else:
        run_novelty = not args.no_novelty
        run_summary = not args.no_summary
        run_acronyms = not args.no_acronyms

    # Run consolidator
    asyncio.run(
        run_consolidator(
            args.checkpoint,
            args.target,
            args.verbose,
            run_novelty,
            run_summary,
            run_acronyms,
        )
    )


if __name__ == "__main__":
    main()
