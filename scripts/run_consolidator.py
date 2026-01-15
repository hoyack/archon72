#!/usr/bin/env python3
"""Run the Motion Consolidator to reduce motions for sustainable deliberation.

Usage:
    python scripts/run_consolidator.py <motions_checkpoint> [--target N] [--verbose]

Examples:
    # Consolidate 69 motions into ~12 mega-motions
    python scripts/run_consolidator.py _bmad-output/secretary/checkpoints/*_05_motions.json

    # Custom target count
    python scripts/run_consolidator.py _bmad-output/secretary/checkpoints/*_05_motions.json --target 10

    # With verbose LLM logging
    python scripts/run_consolidator.py _bmad-output/secretary/checkpoints/*_05_motions.json --verbose
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
) -> None:
    """Run the motion consolidator."""
    print(f"\n{'='*60}")
    print("MOTION CONSOLIDATOR")
    print(f"{'='*60}")
    print(f"Input: {checkpoint_path}")
    print(f"Target Mega-Motions: {target_count}")
    print(f"Verbose: {verbose}")
    print(f"{'='*60}\n")

    # Initialize consolidator
    consolidator = MotionConsolidatorService(
        verbose=verbose,
        target_count=target_count,
    )

    # Load motions from checkpoint
    motions = consolidator.load_motions_from_checkpoint(checkpoint_path)
    print(f"Loaded {len(motions)} motions from checkpoint")

    # Run consolidation
    print("\nConsolidating motions...")
    result = await consolidator.consolidate(motions)

    # Save results
    output_dir = Path("_bmad-output/consolidator")
    consolidator.save_results(result, output_dir)

    # Print summary
    print(f"\n{'='*60}")
    print("CONSOLIDATION COMPLETE")
    print(f"{'='*60}")
    print(f"Original Motions: {result.original_motion_count}")
    print(f"Mega-Motions Created: {len(result.mega_motions)}")
    print(f"Consolidation Ratio: {result.consolidation_ratio:.1%}")
    print(f"Traceability Complete: {result.traceability_complete}")
    if result.orphaned_motions:
        print(f"Orphaned Motions: {len(result.orphaned_motions)}")
    print(f"\nOutput saved to: {output_dir}")
    print(f"{'='*60}\n")

    # Print mega-motion summary
    print("MEGA-MOTIONS SUMMARY:")
    print("-" * 60)
    for i, mm in enumerate(result.mega_motions, 1):
        tier_emoji = {"high": "🟢", "medium": "🟡", "low": "🔵"}.get(mm.consensus_tier, "⚪")
        print(f"{i:2}. {tier_emoji} {mm.title[:50]}...")
        print(f"    Theme: {mm.theme}")
        print(f"    Archons: {mm.unique_archon_count} | Sources: {len(mm.source_motion_ids)} motions")
        print()


def main():
    parser = argparse.ArgumentParser(
        description="Consolidate Secretary motions into mega-motions",
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

    # Run consolidator
    asyncio.run(run_consolidator(
        args.checkpoint,
        args.target,
        args.verbose,
    ))


if __name__ == "__main__":
    main()
