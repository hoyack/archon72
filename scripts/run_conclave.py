#!/usr/bin/env python3
"""Archon 72 Conclave Runner.

Runs a formal Conclave meeting with parliamentary procedure:
- Call to order and roll call
- Motion proposal, seconding, debate, and voting
- Rank-ordered speaking (Kings first)
- Supermajority (2/3) voting threshold
- Checkpoint/resume for multi-day sessions

Expected duration: Several hours to days depending on motions.

Usage:
    python scripts/run_conclave.py [options]

Options:
    --session NAME       Session name (default: auto-generated)
    --resume FILE        Resume from checkpoint file
    --motion TITLE       Motion title for new business
    --motion-text TEXT   Full motion text
    --motion-type TYPE   Motion type: constitutional, policy, open (default: open)
    --debate-rounds N    Max debate rounds (default: 3)
    --quick              Quick mode: 1 debate round, shorter timeouts
"""

import argparse
import asyncio
import os
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

# Load environment variables
load_dotenv()


# ANSI color codes for terminal output
class Colors:
    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"


def print_banner() -> None:
    """Print the Conclave banner."""
    print(f"\n{Colors.BOLD}{Colors.HEADER}")
    print("+" + "=" * 70 + "+")
    print("|" + " " * 70 + "|")
    print("|" + "ARCHON 72 CONCLAVE".center(70) + "|")
    print("|" + "Formal Parliamentary Assembly".center(70) + "|")
    print("|" + " " * 70 + "|")
    print("+" + "=" * 70 + "+")
    print(f"{Colors.ENDC}")


def print_header(text: str) -> None:
    """Print a formatted header."""
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'=' * 70}")
    print(f"  {text}")
    print(f"{'=' * 70}{Colors.ENDC}\n")


def print_phase(phase: str) -> None:
    """Print phase indicator."""
    print(f"\n{Colors.BOLD}{Colors.YELLOW}>>> {phase.upper()}{Colors.ENDC}\n")


def format_progress(event: str, message: str, data: dict) -> None:
    """Format and print progress updates."""
    if event == "phase_change":
        print_phase(message)
    elif event == "motion_proposed":
        print(f"{Colors.GREEN}[MOTION]{Colors.ENDC} {message}")
        print(f"         Type: {data.get('type', 'unknown')}")
        print(f"         Proposer: {data.get('proposer', 'unknown')}")
    elif event == "motion_seconded":
        print(f"{Colors.GREEN}[SECONDED]{Colors.ENDC} {message}")
    elif event == "debate_round_start":
        print(
            f"\n{Colors.BLUE}[DEBATE]{Colors.ENDC} Round {data.get('round')}/{data.get('max_rounds')}"
        )
        print("-" * 50)
    elif event == "archon_speaking":
        archon = data.get("archon", "Unknown")
        rank = data.get("rank", "unknown")
        progress = data.get("progress", "?/?")
        print(f"  {Colors.DIM}[{progress}]{Colors.ENDC} {archon} ({rank})")
    elif event == "archon_voting":
        archon = data.get("archon", "Unknown")
        progress = data.get("progress", "?/?")
        print(f"  {Colors.DIM}[{progress}]{Colors.ENDC} {archon} voting...")
    elif event == "vote_complete":
        passed = data.get("passed", False)
        status = (
            f"{Colors.GREEN}PASSED{Colors.ENDC}"
            if passed
            else f"{Colors.RED}FAILED{Colors.ENDC}"
        )
        print(f"\n{Colors.BOLD}[VOTE RESULT]{Colors.ENDC} {status}")
        print(f"  AYE: {data.get('ayes', 0)}")
        print(f"  NAY: {data.get('nays', 0)}")
        print(f"  ABSTAIN: {data.get('abstentions', 0)}")
    elif event == "checkpoint_saved":
        print(
            f"{Colors.DIM}[CHECKPOINT]{Colors.ENDC} Saved to {data.get('checkpoint_file')}"
        )
    elif event == "session_adjourned":
        print(f"\n{Colors.GREEN}[ADJOURNED]{Colors.ENDC} Session ended")
        print(f"  Duration: {data.get('duration_minutes', 0):.1f} minutes")
        print(f"  Motions passed: {data.get('motions_passed', 0)}")
        print(f"  Motions failed: {data.get('motions_failed', 0)}")
    else:
        print(f"{Colors.DIM}[{event}]{Colors.ENDC} {message}")


async def run_conclave(args: argparse.Namespace) -> None:
    """Run the Conclave session.

    Args:
        args: Parsed command line arguments
    """
    from src.application.services.conclave_service import (
        ArchonProfile,
        ConclaveConfig,
        ConclaveService,
    )
    from src.domain.models.conclave import MotionType
    from src.infrastructure.adapters.config.archon_profile_adapter import (
        create_archon_profile_repository,
    )
    from src.infrastructure.adapters.external.crewai_adapter import (
        create_crewai_adapter,
    )

    print_banner()
    print_header("INITIALIZING CONCLAVE")

    # Load archon profiles
    print(f"{Colors.BLUE}Loading Archon profiles...{Colors.ENDC}")
    profile_repo = create_archon_profile_repository()
    all_profiles = profile_repo.get_all()
    print(f"  Loaded {len(all_profiles)} Archon profiles")

    # Convert to ConclaveService format
    archon_profiles = [
        ArchonProfile(
            id=str(p.id),
            name=p.name,
            aegis_rank=p.aegis_rank,
            domain=p.domain or p.role,  # Fall back to role if domain not set
        )
        for p in all_profiles
    ]

    # Show rank distribution
    rank_counts: dict[str, int] = {}
    for p in archon_profiles:
        rank_counts[p.aegis_rank] = rank_counts.get(p.aegis_rank, 0) + 1
    print(f"\n{Colors.BLUE}Rank Distribution:{Colors.ENDC}")
    for rank, count in sorted(rank_counts.items(), key=lambda x: -x[1]):
        print(f"  {rank}: {count} archons")

    # Create CrewAI adapter
    print(f"\n{Colors.BLUE}Initializing CrewAI adapter...{Colors.ENDC}")
    adapter = create_crewai_adapter(
        profile_repository=profile_repo,
        verbose=False,
        include_default_tools=False,
    )

    # Configure Conclave
    config = ConclaveConfig(
        max_debate_rounds=args.debate_rounds,
        checkpoint_interval_minutes=5,
    )
    if args.quick:
        config.max_debate_rounds = 1
        config.agent_timeout_seconds = 60

    # Create Conclave service
    conclave = ConclaveService(
        orchestrator=adapter,
        archon_profiles=archon_profiles,
        config=config,
    )
    conclave.set_progress_callback(format_progress)

    # Create or resume session
    if args.resume:
        print(f"\n{Colors.BLUE}Resuming from checkpoint...{Colors.ENDC}")
        session = conclave.load_session(Path(args.resume))
        print(f"  Session: {session.session_name}")
        print(f"  Phase: {session.current_phase.value}")
    else:
        session_name = (
            args.session or f"conclave-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        )
        print(f"\n{Colors.BLUE}Creating new session...{Colors.ENDC}")
        session = conclave.create_session(session_name)
        print(f"  Session: {session_name}")

    print(f"\n{Colors.BLUE}Configuration:{Colors.ENDC}")
    print(f"  OLLAMA_HOST: {os.environ.get('OLLAMA_HOST', 'not set')}")
    print(f"  Max debate rounds: {config.max_debate_rounds}")
    print(f"  Supermajority threshold: {config.supermajority_threshold:.1%}")

    # Determine motion details
    motion_title = (
        args.motion
        or "Should AI systems be granted limited autonomous decision-making authority?"
    )
    motion_text = args.motion_text or (
        "WHEREAS AI systems have demonstrated increasing capability in complex reasoning tasks; and "
        "WHEREAS the Archon 72 Conclave serves as a constitutional governance body; "
        "BE IT RESOLVED that the Conclave shall deliberate on establishing a framework for "
        "limited autonomous decision-making authority for AI systems, subject to: "
        "(1) Constitutional safeguards ensuring alignment with human values; "
        "(2) Mandatory human oversight for high-stakes decisions; "
        "(3) Transparent audit trails for all autonomous actions; "
        "(4) Regular review and amendment procedures."
    )
    motion_type_str = args.motion_type.lower() if args.motion_type else "open"
    motion_type = {
        "constitutional": MotionType.CONSTITUTIONAL,
        "policy": MotionType.POLICY,
        "procedural": MotionType.PROCEDURAL,
        "open": MotionType.OPEN,
    }.get(motion_type_str, MotionType.OPEN)

    print(f"\n{Colors.BLUE}Motion to be considered:{Colors.ENDC}")
    print(f"  Title: {motion_title}")
    print(f"  Type: {motion_type.value}")
    print(f"  Text: {motion_text[:200]}...")

    # Estimate time
    total_turns = len(archon_profiles) * config.max_debate_rounds + len(
        archon_profiles
    )  # debate + voting
    avg_time_per_turn = 15  # seconds
    estimated_minutes = (total_turns * avg_time_per_turn) / 60

    print(
        f"\n{Colors.YELLOW}Estimated duration: {estimated_minutes:.0f}-{estimated_minutes * 2:.0f} minutes{Colors.ENDC}"
    )
    print(
        f"{Colors.DIM}({total_turns} total turns: {config.max_debate_rounds} debate rounds + 1 voting round){Colors.ENDC}"
    )

    print_header("CONCLAVE IN SESSION")

    try:
        # Phase 1: Call to Order
        await conclave.call_to_order()

        # Phase 2: Roll Call
        await conclave.conduct_roll_call()

        # Phase 3: Move to New Business
        await conclave.advance_to_new_business()

        # Phase 4: Propose Motion
        # First archon (by rank) proposes
        proposer = archon_profiles[0]
        await conclave.propose_motion(
            proposer_id=proposer.id,
            motion_type=motion_type,
            title=motion_title,
            text=motion_text,
        )

        # Phase 5: Second Motion
        # Second archon (by rank) seconds
        seconder = archon_profiles[1]
        await conclave.second_motion(seconder_id=seconder.id)

        # Phase 6: Debate
        await conclave.conduct_debate()

        # Phase 7: Call the Question
        await conclave.call_question()

        # Phase 8: Vote
        await conclave.conduct_vote()

        # Phase 9: Adjourn
        await conclave.adjourn()

        # Save transcript
        transcript_path = conclave.save_transcript()
        print(f"\n{Colors.GREEN}Transcript saved:{Colors.ENDC} {transcript_path}")

        # Print summary
        summary = conclave.get_session_summary()
        print_header("CONCLAVE SUMMARY")
        print(f"  Session: {summary['session_name']}")
        print(f"  Duration: {summary['duration_minutes']:.1f} minutes")
        print(
            f"  Archons present: {summary['present_archons']}/{summary['total_archons']}"
        )
        print(
            f"  Motions: {summary['motions_count']} ({summary['passed_motions']} passed, {summary['failed_motions']} failed)"
        )
        print(f"  Total votes cast: {summary['total_votes_cast']}")
        print(f"  Transcript entries: {summary['transcript_entries']}")

    except KeyboardInterrupt:
        print(
            f"\n{Colors.YELLOW}[INTERRUPTED]{Colors.ENDC} Session interrupted by user"
        )
        checkpoint_path = conclave.save_checkpoint()
        print(f"  Session checkpointed to: {checkpoint_path}")
        print(
            f"  Resume with: python scripts/run_conclave.py --resume {checkpoint_path}"
        )
    except Exception as e:
        print(f"\n{Colors.RED}[ERROR]{Colors.ENDC} {e}")
        import traceback

        traceback.print_exc()
        # Try to save checkpoint
        try:
            checkpoint_path = conclave.save_checkpoint()
            print(f"  Emergency checkpoint: {checkpoint_path}")
        except Exception:
            pass
        raise


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Run Archon 72 Conclave with formal parliamentary procedure",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run with default motion
  python scripts/run_conclave.py

  # Run with custom motion
  python scripts/run_conclave.py --motion "Establish AI ethics committee" --motion-type policy

  # Quick test (1 debate round)
  python scripts/run_conclave.py --quick

  # Resume interrupted session
  python scripts/run_conclave.py --resume _bmad-output/conclave/checkpoint-xxx.json
""",
    )
    parser.add_argument(
        "--session",
        type=str,
        help="Session name (default: auto-generated)",
    )
    parser.add_argument(
        "--resume",
        type=str,
        help="Resume from checkpoint file",
    )
    parser.add_argument(
        "--motion",
        type=str,
        help="Motion title for new business",
    )
    parser.add_argument(
        "--motion-text",
        type=str,
        help="Full motion text",
    )
    parser.add_argument(
        "--motion-type",
        type=str,
        choices=["constitutional", "policy", "procedural", "open"],
        default="open",
        help="Motion type (default: open)",
    )
    parser.add_argument(
        "--debate-rounds",
        type=int,
        default=3,
        help="Max debate rounds (default: 3)",
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Quick mode: 1 debate round, shorter timeouts",
    )

    args = parser.parse_args()

    if args.quick:
        args.debate_rounds = 1

    asyncio.run(run_conclave(args))


if __name__ == "__main__":
    main()
