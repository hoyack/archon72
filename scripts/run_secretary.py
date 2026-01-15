#!/usr/bin/env python3
"""Run the Secretary to process a Conclave transcript.

Usage:
    python scripts/run_secretary.py <transcript_path> [--enhanced] [--verbose]

Examples:
    # Regex-based extraction (fast, deterministic)
    python scripts/run_secretary.py _bmad-output/conclave/transcript-xxx.md

    # LLM-enhanced extraction (nuanced, thorough)
    python scripts/run_secretary.py _bmad-output/conclave/transcript-xxx.md --enhanced

    # With verbose CrewAI logging
    python scripts/run_secretary.py _bmad-output/conclave/transcript-xxx.md --enhanced --verbose
"""

import argparse
import asyncio
import sys
from pathlib import Path
from uuid import uuid4

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

from src.application.services.secretary_service import SecretaryService, SecretaryConfig


def parse_session_info_from_path(transcript_path: Path) -> tuple[str, str]:
    """Extract session ID and name from transcript filename."""
    # Filename format: transcript-{uuid}-{timestamp}.md
    name = transcript_path.stem
    parts = name.split("-")

    if len(parts) >= 6:
        # Extract UUID from parts 1-5 (indices 1,2,3,4,5)
        session_id = "-".join(parts[1:6])
        timestamp = "-".join(parts[6:]) if len(parts) > 6 else ""
        session_name = f"Conclave {timestamp}" if timestamp else "Conclave Session"
    else:
        session_id = str(uuid4())
        session_name = "Conclave Session"

    return session_id, session_name


async def run_enhanced(
    transcript_path: Path,
    session_id: str,
    session_name: str,
    verbose: bool = False,
) -> None:
    """Run Secretary with LLM enhancement."""
    from src.infrastructure.adapters.external import create_secretary_agent
    from src.domain.models.secretary_agent import load_secretary_config_from_yaml, _CONFIG_FILE
    from uuid import UUID

    # Verify YAML config loading
    print(f"\n{'='*60}")
    print("SECRETARY - Configuration Check")
    print(f"{'='*60}")
    print(f"Config file: {_CONFIG_FILE}")
    print(f"Config exists: {_CONFIG_FILE.exists()}")

    text_config, json_config, checkpoints = load_secretary_config_from_yaml()
    print(f"\nText Model: {text_config.provider}/{text_config.model}")
    print(f"  Temperature: {text_config.temperature}")
    print(f"  Max tokens: {text_config.max_tokens}")
    print(f"\nJSON Model: {json_config.provider}/{json_config.model}")
    print(f"  Temperature: {json_config.temperature}")
    print(f"  Max tokens: {json_config.max_tokens}")
    print(f"\nCheckpoints: {'enabled' if checkpoints else 'disabled'}")
    print(f"{'='*60}")

    print(f"\n{'='*60}")
    print("SECRETARY - LLM-Enhanced Processing")
    print(f"{'='*60}")
    print(f"Transcript: {transcript_path}")
    print(f"Session: {session_name}")
    print(f"Mode: CrewAI-powered extraction")
    print(f"{'='*60}\n")

    # Create the agent
    agent = create_secretary_agent(verbose=verbose)

    # Create service with agent
    config = SecretaryConfig()
    service = SecretaryService(config=config, secretary_agent=agent)

    # Process transcript
    try:
        session_uuid = UUID(session_id)
    except ValueError:
        session_uuid = uuid4()

    report = await service.process_transcript_enhanced(
        transcript_path=transcript_path,
        session_id=session_uuid,
        session_name=session_name,
    )

    # Save and display results
    output_dir = service.save_report(report)

    print(f"\n{'='*60}")
    print("SECRETARY REPORT COMPLETE")
    print(f"{'='*60}")
    print(f"Speeches Analyzed: {report.total_speeches_analyzed}")
    print(f"Recommendations Extracted: {report.total_recommendations_extracted}")
    print(f"Clusters Formed: {len(report.clusters)}")
    print(f"Motions Queued: {len(report.motion_queue)}")
    print(f"Tasks Identified: {len(report.task_registry)}")
    print(f"Conflicts Detected: {len(report.conflict_report)}")
    print(f"Processing Time: {report.processing_duration_seconds:.2f}s")
    print(f"\nOutput saved to: {output_dir}")
    print(f"{'='*60}\n")

    # Print motion queue summary
    if report.motion_queue:
        print("\nMOTION QUEUE FOR NEXT CONCLAVE:")
        print("-" * 40)
        for i, motion in enumerate(report.motion_queue, 1):
            print(f"{i}. {motion.title}")
            print(f"   Consensus: {motion.consensus_level.value} ({motion.original_archon_count} Archons)")
            print(f"   Supporters: {', '.join(motion.supporting_archons[:3])}{'...' if len(motion.supporting_archons) > 3 else ''}")
            print()


def run_regex(
    transcript_path: Path,
    session_id: str,
    session_name: str,
) -> None:
    """Run Secretary with regex-based extraction."""
    from uuid import UUID

    print(f"\n{'='*60}")
    print("SECRETARY - Regex-Based Processing")
    print(f"{'='*60}")
    print(f"Transcript: {transcript_path}")
    print(f"Session: {session_name}")
    print(f"Mode: Deterministic regex extraction")
    print(f"{'='*60}\n")

    # Create service without agent
    config = SecretaryConfig()
    service = SecretaryService(config=config)

    # Process transcript
    try:
        session_uuid = UUID(session_id)
    except ValueError:
        session_uuid = uuid4()

    report = service.process_transcript(
        transcript_path=transcript_path,
        session_id=session_uuid,
        session_name=session_name,
    )

    # Save and display results
    output_dir = service.save_report(report)

    print(f"\n{'='*60}")
    print("SECRETARY REPORT COMPLETE")
    print(f"{'='*60}")
    print(f"Speeches Analyzed: {report.total_speeches_analyzed}")
    print(f"Recommendations Extracted: {report.total_recommendations_extracted}")
    print(f"Clusters Formed: {len(report.clusters)}")
    print(f"Motions Queued: {len(report.motion_queue)}")
    print(f"Tasks Identified: {len(report.task_registry)}")
    print(f"Conflicts Detected: {len(report.conflict_report)}")
    print(f"Processing Time: {report.processing_duration_seconds:.2f}s")
    print(f"\nOutput saved to: {output_dir}")
    print(f"{'='*60}\n")

    # Print motion queue summary
    if report.motion_queue:
        print("\nMOTION QUEUE FOR NEXT CONCLAVE:")
        print("-" * 40)
        for i, motion in enumerate(report.motion_queue, 1):
            print(f"{i}. {motion.title}")
            print(f"   Consensus: {motion.consensus_level.value} ({motion.original_archon_count} Archons)")
            print(f"   Supporters: {', '.join(motion.supporting_archons[:3])}{'...' if len(motion.supporting_archons) > 3 else ''}")
            print()


def main():
    parser = argparse.ArgumentParser(
        description="Run the Secretary to process a Conclave transcript",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "transcript",
        type=Path,
        help="Path to the Conclave transcript markdown file",
    )
    parser.add_argument(
        "--enhanced",
        action="store_true",
        help="Use LLM-enhanced extraction (requires ANTHROPIC_API_KEY)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose CrewAI logging",
    )
    parser.add_argument(
        "--session-name",
        type=str,
        default=None,
        help="Override the session name",
    )

    args = parser.parse_args()

    # Validate transcript exists
    if not args.transcript.exists():
        print(f"Error: Transcript not found: {args.transcript}")
        sys.exit(1)

    # Parse session info
    session_id, session_name = parse_session_info_from_path(args.transcript)
    if args.session_name:
        session_name = args.session_name

    # Run appropriate mode
    if args.enhanced:
        asyncio.run(run_enhanced(
            args.transcript,
            session_id,
            session_name,
            args.verbose,
        ))
    else:
        run_regex(args.transcript, session_id, session_name)


if __name__ == "__main__":
    main()
