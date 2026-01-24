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
    --motion-text TEXT   Full motion text (inline)
    --motion-file FILE   Load motion text from file (overrides --motion-text)
    --motion-type TYPE   Motion type: constitutional, policy, open (default: open)
    --debate-rounds N    Max debate rounds (default: 3)
    --quick              Quick mode: 1 debate round, shorter timeouts
"""

import argparse
import asyncio
import glob
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

# Disable CrewAI telemetry and force writable storage before CrewAI imports.
os.environ.setdefault("CREWAI_DISABLE_TELEMETRY", "true")
os.environ.setdefault("CREWAI_DISABLE_TRACKING", "true")
os.environ.setdefault("OTEL_SDK_DISABLED", "true")
os.environ.setdefault("CREWAI_TRACING_ENABLED", "false")
os.environ.setdefault("CREWAI_TESTING", "true")
os.environ.setdefault("CREWAI_STORAGE_DIR", "archon72")
os.environ.setdefault("XDG_DATA_HOME", "/tmp/crewai-data")
Path(os.environ["XDG_DATA_HOME"]).mkdir(parents=True, exist_ok=True)

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


def parse_env_bool(name: str, default: bool = False) -> bool:
    """Parse a boolean environment variable."""
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


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
    elif event == "session_progress":
        pct = data.get("percent_complete", 0)
        phase = data.get("phase", "")
        print(f"{Colors.DIM}[{pct:5.1f}%]{Colors.ENDC} {phase}")
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


def find_latest_blockers_summary() -> Path | None:
    """Find the most recent blockers_summary.json file."""
    pattern = "_bmad-output/execution-planner/*/blockers_summary.json"
    files = glob.glob(pattern)
    if not files:
        return None
    return Path(max(files, key=lambda f: Path(f).stat().st_mtime))


def load_blocker_agenda_items(summary_path: Path) -> list[str]:
    """Load Conclave agenda items from an execution planner blockers summary."""
    with open(summary_path, encoding="utf-8") as f:
        data = json.load(f)

    agenda_items = [item for item in data.get("agenda_items", []) if item]
    if agenda_items:
        return agenda_items

    blockers = data.get("blockers", [])
    items = []
    for blocker in blockers:
        if not blocker.get("escalate_to_conclave"):
            continue
        item = blocker.get("suggested_agenda_item") or blocker.get("description")
        if item:
            items.append(item)
    return items


async def run_conclave(args: argparse.Namespace) -> None:  # noqa: C901
    """Run the Conclave session.

    Args:
        args: Parsed command line arguments
    """
    from src.application.services.conclave_service import (
        ArchonProfile,
        ConclaveConfig,
        ConclaveService,
    )
    from src.application.services.motion_queue_service import MotionQueueService
    from src.domain.models.conclave import Motion, MotionType
    from src.infrastructure.adapters.config.archon_profile_adapter import (
        create_archon_profile_repository,
    )
    from src.infrastructure.adapters.external.crewai_adapter import (
        create_crewai_adapter,
    )
    from src.infrastructure.adapters.kafka.audit_publisher import KafkaAuditPublisher
    from src.infrastructure.adapters.witness import create_knight_witness

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
        voting_concurrency=args.voting_concurrency,
    )
    if args.quick:
        config.max_debate_rounds = 1
        config.agent_timeout_seconds = 60

    timeout_override = os.getenv("AGENT_TIMEOUT_SECONDS", "").strip()
    if timeout_override:
        try:
            config.agent_timeout_seconds = max(0, int(float(timeout_override)))
        except ValueError:
            print(
                f"  Invalid AGENT_TIMEOUT_SECONDS={timeout_override!r}; "
                "using default."
            )

    max_attempts = os.getenv("AGENT_TIMEOUT_MAX_ATTEMPTS", "").strip()
    if max_attempts.isdigit():
        config.agent_timeout_max_attempts = max(1, int(max_attempts))

    base_delay = os.getenv("AGENT_TIMEOUT_BASE_DELAY_SECONDS", "").strip()
    if base_delay:
        try:
            config.agent_timeout_backoff_base_seconds = max(0.0, float(base_delay))
        except ValueError:
            print(
                f"  Invalid AGENT_TIMEOUT_BASE_DELAY_SECONDS={base_delay!r}; "
                "using default."
            )

    max_delay = os.getenv("AGENT_TIMEOUT_MAX_DELAY_SECONDS", "").strip()
    if max_delay:
        try:
            config.agent_timeout_backoff_max_seconds = max(0.0, float(max_delay))
        except ValueError:
            print(
                f"  Invalid AGENT_TIMEOUT_MAX_DELAY_SECONDS={max_delay!r}; "
                "using default."
            )

    task_timeout = os.getenv("VOTE_VALIDATION_TASK_TIMEOUT", "").strip()
    if task_timeout:
        try:
            config.task_timeout_seconds = max(1, int(float(task_timeout)))
        except ValueError:
            print(
                f"  Invalid VOTE_VALIDATION_TASK_TIMEOUT={task_timeout!r}; "
                "using default."
            )

    concurrency_label = (
        "unlimited" if config.voting_concurrency <= 0 else str(config.voting_concurrency)
    )
    print(f"  Voting concurrency: {concurrency_label}")

    witness_archon_id = os.getenv("WITNESS_ARCHON_ID", "").strip()
    secretary_text_archon_id = os.getenv("SECRETARY_TEXT_ARCHON_ID", "").strip()
    secretary_json_archon_id = os.getenv("SECRETARY_JSON_ARCHON_ID", "").strip()
    config.secretary_text_archon_id = secretary_text_archon_id or None
    config.secretary_json_archon_id = secretary_json_archon_id or None
    config.witness_archon_id = witness_archon_id or None
    if secretary_text_archon_id and secretary_json_archon_id:
        # Sync vote validation uses secretary consensus only.
        config.vote_validation_archon_ids = [
            secretary_text_archon_id,
            secretary_json_archon_id,
        ]
        max_attempts = os.getenv("VOTE_VALIDATION_MAX_ATTEMPTS", "").strip()
        if max_attempts.isdigit():
            config.vote_validation_max_attempts = max(1, int(max_attempts))

    knight_witness = create_knight_witness(verbose=False)

    validation_dispatcher = None
    reconciliation_service = None
    validation_listener = None
    validation_listener_task: asyncio.Task | None = None
    async_requested = parse_env_bool("ENABLE_ASYNC_VALIDATION", False)
    if async_requested:
        config.async_validation_enabled = True
        config.enable_async_validation = False
        config.kafka_bootstrap_servers = os.getenv(
            "KAFKA_BOOTSTRAP_SERVERS",
            config.kafka_bootstrap_servers,
        )
        config.schema_registry_url = os.getenv(
            "SCHEMA_REGISTRY_URL",
            config.schema_registry_url,
        )
        reconciliation_timeout = os.getenv("RECONCILIATION_TIMEOUT", "").strip()
        if reconciliation_timeout:
            try:
                config.reconciliation_timeout = float(reconciliation_timeout)
            except ValueError:
                print(
                    f"  Invalid RECONCILIATION_TIMEOUT={reconciliation_timeout!r}; "
                    "using default."
                )

    kafka_enabled = parse_env_bool("KAFKA_ENABLED", False)
    config.kafka_enabled = kafka_enabled
    topic_prefix = os.getenv("KAFKA_TOPIC_PREFIX", "").strip()
    if topic_prefix:
        config.kafka_topic_prefix = topic_prefix

    kafka_publisher = None
    if kafka_enabled:
        kafka_publisher = KafkaAuditPublisher(
            bootstrap_servers=config.kafka_bootstrap_servers,
            topic_prefix=config.kafka_topic_prefix,
        )

    # Create Conclave service
    conclave = ConclaveService(
        orchestrator=adapter,
        archon_profiles=archon_profiles,
        config=config,
        knight_witness=knight_witness,
        validation_dispatcher=validation_dispatcher,
        reconciliation_service=reconciliation_service,
        kafka_publisher=kafka_publisher,
    )
    conclave.set_progress_callback(format_progress)

    # Create or resume session
    if args.resume:
        print(f"\n{Colors.BLUE}Resuming from checkpoint...{Colors.ENDC}")
        session = conclave.load_session(Path(args.resume))
        await conclave.resume_pending_validations()
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
    if config.vote_validation_archon_ids:
        print("  Vote validation: enabled")
        print(
            "    Validators: "
            + ", ".join(config.vote_validation_archon_ids)
        )
        print(f"    Max attempts: {config.vote_validation_max_attempts}")
    else:
        print(
            "  Vote validation: disabled "
            "(missing SECRETARY_TEXT_ARCHON_ID or SECRETARY_JSON_ARCHON_ID)"
        )
    if config.async_validation_enabled:
        print("  Async validation: enabled (in-process)")
        print(f"    Kafka bootstrap: {config.kafka_bootstrap_servers}")
        print(f"    Schema registry: {config.schema_registry_url}")
    elif config.enable_async_validation:
        print("  Async validation: enabled (legacy Kafka)")
        print(f"    Kafka bootstrap: {config.kafka_bootstrap_servers}")
        print(f"    Schema registry: {config.schema_registry_url}")
    else:
        print("  Async validation: disabled")
    print(
        f"  Kafka audit: {'enabled' if config.kafka_enabled else 'disabled'}"
    )

    # Build motion plans (queue + blockers unless custom motion specified)
    custom_motion_requested = bool(args.motion or args.motion_text or args.motion_file)
    use_queue = not args.no_queue and not custom_motion_requested
    use_blockers = not args.no_blockers and not custom_motion_requested
    motion_plans: list[dict] = []
    queue_service = MotionQueueService()

    if use_queue:
        queued = queue_service.select_for_conclave(
            max_items=args.queue_max_items,
            min_consensus=args.queue_min_consensus,
        )
        for queued_motion in queued:
            motion = queue_service.promote_to_conclave(
                queued_motion.queued_motion_id,
                session.session_id,
            )
            if motion:
                motion_plans.append(
                    {
                        "source": "queue",
                        "motion": motion,
                        "queued_motion_id": queued_motion.queued_motion_id,
                    }
                )

    if use_blockers:
        blockers_path = Path(args.blockers_path) if args.blockers_path else None
        if blockers_path and blockers_path.is_dir():
            blockers_path = blockers_path / "blockers_summary.json"
        if blockers_path is None:
            blockers_path = find_latest_blockers_summary()
        if blockers_path and blockers_path.exists():
            agenda_items = load_blocker_agenda_items(blockers_path)
            for item in agenda_items:
                motion = Motion.create(
                    motion_type=MotionType.PROCEDURAL,
                    title=f"Blocker Escalation: {item[:60]}",
                    text=f"AGENDA ITEM:\n\n{item}\n",
                    proposer_id="execution_planner",
                    proposer_name="Execution Planner",
                    max_debate_rounds=config.max_debate_rounds,
                )
                motion_plans.append(
                    {"source": "blocker", "motion": motion, "queued_motion_id": None}
                )

    if custom_motion_requested or not motion_plans:
        motion_title = (
            args.motion
            or "Should AI systems be granted limited autonomous decision-making authority?"
        )

        # Load motion text: file takes precedence over inline text
        if args.motion_file:
            motion_file_path = Path(args.motion_file)
            if not motion_file_path.exists():
                print(f"{Colors.RED}Error: Motion file not found: {args.motion_file}{Colors.ENDC}")
                sys.exit(1)
            motion_text = motion_file_path.read_text(encoding="utf-8").strip()
            print(f"{Colors.GREEN}Loaded motion text from: {args.motion_file}{Colors.ENDC}")
        elif args.motion_text:
            motion_text = args.motion_text
        else:
            # Default motion text
            motion_text = (
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

        motion_plans = [
            {
                "source": "custom",
                "motion_type": motion_type,
                "motion_title": motion_title,
                "motion_text": motion_text,
                "queued_motion_id": None,
            }
        ]

    print(f"\n{Colors.BLUE}Motions to be considered:{Colors.ENDC}")
    for idx, plan in enumerate(motion_plans, 1):
        if plan["source"] == "custom":
            print(f"  {idx}. {plan['motion_title']} ({plan['motion_type'].value})")
        else:
            print(f"  {idx}. {plan['motion'].title} ({plan['source']})")

    # Estimate time
    total_turns_per_motion = len(archon_profiles) * (
        config.max_debate_rounds + 1
    )  # debate + voting
    total_turns = total_turns_per_motion * len(motion_plans)
    avg_time_per_turn = 15  # seconds
    estimated_minutes = (total_turns * avg_time_per_turn) / 60

    print(
        f"\n{Colors.YELLOW}Estimated duration: {estimated_minutes:.0f}-{estimated_minutes * 2:.0f} minutes{Colors.ENDC}"
    )
    print(
        f"{Colors.DIM}({total_turns} total turns: {config.max_debate_rounds} debate rounds + 1 voting round per motion){Colors.ENDC}"
    )

    print_header("CONCLAVE IN SESSION")

    try:
        # Phase 1: Call to Order
        await conclave.call_to_order()

        # Phase 2: Roll Call
        await conclave.conduct_roll_call()

        # Phase 3: Move to New Business
        await conclave.advance_to_new_business()

        seconder = archon_profiles[1] if len(archon_profiles) > 1 else archon_profiles[0]

        for idx, plan in enumerate(motion_plans, 1):
            if plan["source"] == "custom":
                proposer = archon_profiles[0]
                await conclave.propose_motion(
                    proposer_id=proposer.id,
                    motion_type=plan["motion_type"],
                    title=plan["motion_title"],
                    text=plan["motion_text"],
                )
            else:
                conclave.add_external_motion(plan["motion"])

            await conclave.second_motion(seconder_id=seconder.id)
            await conclave.conduct_debate()
            await conclave.call_question()
            vote_result = await conclave.conduct_vote()

            queued_motion_id = plan.get("queued_motion_id")
            if queued_motion_id:
                queue_service.mark_voted(
                    queued_motion_id,
                    passed=vote_result.get("passed", False),
                    vote_details=vote_result,
                )

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
    finally:
        if validation_listener:
            validation_listener.stop()
        if validation_listener_task:
            try:
                await validation_listener_task
            except Exception:
                pass


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Run Archon 72 Conclave with formal parliamentary procedure",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run with default motion
  python scripts/run_conclave.py

  # Run with custom motion (inline text)
  python scripts/run_conclave.py --motion "Establish AI ethics committee" --motion-type policy

  # Run with motion text from file (recommended for complex motions)
  python scripts/run_conclave.py --motion "Ethics Framework" --motion-file motions/ethics.md --motion-type constitutional

  # Quick test (1 debate round)
  python scripts/run_conclave.py --quick

  # Resume interrupted session
  python scripts/run_conclave.py --resume _bmad-output/conclave/checkpoint-xxx.json

Motion File Format:
  Motion files should contain the full motion text in plain text or markdown.
  The WHEREAS...BE IT RESOLVED format is recommended for formal motions.
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
        help="Full motion text (inline)",
    )
    parser.add_argument(
        "--motion-file",
        type=str,
        help="Load motion text from file (overrides --motion-text)",
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
    parser.add_argument(
        "--voting-concurrency",
        type=int,
        default=1,
        help="Number of archons that can vote concurrently (default: 1 = sequential, 0 = unlimited)",
    )
    parser.add_argument(
        "--no-queue",
        action="store_true",
        help="Disable loading motions from the motion queue",
    )
    parser.add_argument(
        "--queue-max-items",
        type=int,
        default=5,
        help="Max motion queue items to include (default: 5)",
    )
    parser.add_argument(
        "--queue-min-consensus",
        type=str,
        default="medium",
        choices=["critical", "high", "medium", "low", "single"],
        help="Minimum consensus tier for motion queue items",
    )
    parser.add_argument(
        "--no-blockers",
        action="store_true",
        help="Disable loading blockers from execution planner",
    )
    parser.add_argument(
        "--blockers-path",
        type=str,
        default=None,
        help="Path to blockers_summary.json or execution-planner session dir",
    )

    args = parser.parse_args()

    if args.quick:
        args.debate_rounds = 1

    asyncio.run(run_conclave(args))


if __name__ == "__main__":
    main()
