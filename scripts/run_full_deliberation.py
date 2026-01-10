#!/usr/bin/env python3
"""Full 72-Agent Sequential Deliberation Test.

Runs a complete deliberation with all 72 Archons using local Ollama models.
Each Archon speaks in turn (round-robin) - constitutional council pattern.

Expected duration: 30-60 minutes depending on model sizes and GPU.

Usage:
    python scripts/run_full_deliberation.py [--topic "Your topic here"]
"""

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

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


def print_header(text: str) -> None:
    """Print a formatted header."""
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'=' * 70}")
    print(f"  {text}")
    print(f"{'=' * 70}{Colors.ENDC}\n")


def print_progress(current: int, total: int, agent_name: str, status: str, elapsed: float) -> None:
    """Print progress update."""
    pct = (current / total) * 100
    bar_width = 30
    filled = int(bar_width * current / total)
    bar = "█" * filled + "░" * (bar_width - filled)

    if status == "starting":
        status_color = Colors.YELLOW
        status_icon = "⏳"
    elif status == "completed":
        status_color = Colors.GREEN
        status_icon = "✓"
    else:
        status_color = Colors.RED
        status_icon = "✗"

    # Calculate ETA
    if current > 0 and status == "completed":
        avg_time = elapsed / current
        remaining = (total - current) * avg_time
        eta_str = f"ETA: {remaining / 60:.1f}m"
    else:
        eta_str = ""

    print(
        f"\r{Colors.DIM}[{bar}]{Colors.ENDC} "
        f"{Colors.BOLD}{pct:5.1f}%{Colors.ENDC} | "
        f"Turn {current:2d}/{total} | "
        f"{status_color}{status_icon} {agent_name[:20]:<20}{Colors.ENDC} | "
        f"{elapsed / 60:.1f}m elapsed {eta_str}",
        end="",
        flush=True,
    )
    if status in ("completed", "failed"):
        print()  # New line after completion


async def run_deliberation(topic: str) -> dict:
    """Run full 72-agent deliberation.

    Args:
        topic: The deliberation topic

    Returns:
        dict with results and statistics
    """
    from src.application.ports.agent_orchestrator import (
        AgentRequest,
        ContextBundle,
    )
    from src.infrastructure.adapters.config.archon_profile_adapter import (
        create_archon_profile_repository,
    )
    from src.infrastructure.adapters.external.crewai_adapter import (
        create_crewai_adapter,
    )

    print_header("ARCHON 72 CONCLAVE - FULL DELIBERATION")

    # Load archon profiles
    print(f"{Colors.BLUE}Loading Archon profiles...{Colors.ENDC}")
    profile_repo = create_archon_profile_repository()
    all_profiles = profile_repo.get_all()
    print(f"  Loaded {len(all_profiles)} Archon profiles")

    # Show rank distribution
    rank_counts = {}
    for p in all_profiles:
        rank_counts[p.aegis_rank] = rank_counts.get(p.aegis_rank, 0) + 1
    print(f"\n{Colors.BLUE}Rank Distribution:{Colors.ENDC}")
    for rank, count in sorted(rank_counts.items(), key=lambda x: -x[1]):
        print(f"  {rank}: {count} archons")

    # Create adapter (with tool registry disabled for speed)
    print(f"\n{Colors.BLUE}Initializing CrewAI adapter...{Colors.ENDC}")
    adapter = create_crewai_adapter(
        profile_repository=profile_repo,
        verbose=False,
        include_default_tools=False,  # Disable tools for faster deliberation
    )

    # Create context bundle
    bundle_id = uuid4()
    topic_id = f"deliberation-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

    context = ContextBundle(
        bundle_id=bundle_id,
        topic_id=topic_id,
        topic_content=topic,
        metadata={"deliberation_type": "full_conclave", "agent_count": "72"},
        created_at=datetime.now(timezone.utc),
    )

    # Create requests for all archons
    requests = []
    for profile in all_profiles:
        requests.append(
            AgentRequest(
                request_id=uuid4(),
                agent_id=str(profile.id),
                context=context,
            )
        )

    print(f"\n{Colors.BLUE}Deliberation Topic:{Colors.ENDC}")
    print(f"  {Colors.BOLD}{topic}{Colors.ENDC}")
    print(f"\n{Colors.BLUE}Configuration:{Colors.ENDC}")
    print(f"  OLLAMA_HOST: {os.environ.get('OLLAMA_HOST', 'not set')}")
    print(f"  Mode: Sequential (round-robin)")
    print(f"  Agents: {len(requests)}")

    # Estimate time
    print(f"\n{Colors.YELLOW}Estimated duration: 30-60 minutes{Colors.ENDC}")
    print(f"{Colors.DIM}(Each agent will speak in turn, like a constitutional council){Colors.ENDC}")

    print_header("DELIBERATION IN PROGRESS")

    # Track progress
    start_time = datetime.now()
    results = {
        "topic_id": topic_id,
        "topic": topic,
        "start_time": start_time.isoformat(),
        "agent_count": len(requests),
        "outputs": [],
        "failures": [],
    }

    # Progress tracking
    agent_name_map = {str(p.id): p.name for p in all_profiles}

    def on_progress(current: int, total: int, agent_id: str, status: str) -> None:
        elapsed = (datetime.now() - start_time).total_seconds()
        agent_name = agent_name_map.get(agent_id, agent_id[:8])
        print_progress(current, total, agent_name, status, elapsed)

    # Run sequential deliberation
    try:
        outputs = await adapter.invoke_sequential(requests, on_progress=on_progress)

        for output in outputs:
            agent_name = agent_name_map.get(output.agent_id, output.agent_id)
            results["outputs"].append({
                "agent_id": output.agent_id,
                "agent_name": agent_name,
                "content": output.content,
                "generated_at": output.generated_at.isoformat(),
            })

    except Exception as e:
        print(f"\n{Colors.RED}Error during deliberation: {e}{Colors.ENDC}")
        results["error"] = str(e)

    # Calculate final stats
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()

    results["end_time"] = end_time.isoformat()
    results["duration_seconds"] = duration
    results["success_count"] = len(results["outputs"])
    results["failure_count"] = len(requests) - len(results["outputs"])

    print_header("DELIBERATION COMPLETE")

    print(f"{Colors.GREEN}✓ Deliberation finished{Colors.ENDC}")
    print(f"\n{Colors.BLUE}Statistics:{Colors.ENDC}")
    print(f"  Duration: {duration / 60:.1f} minutes")
    print(f"  Successful outputs: {results['success_count']}/{len(requests)}")
    print(f"  Average time per agent: {duration / len(requests):.1f}s")

    # Save results
    output_dir = Path("_bmad-output/deliberations")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"{topic_id}.json"

    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\n{Colors.BLUE}Results saved to:{Colors.ENDC}")
    print(f"  {output_file}")

    # Show sample outputs
    if results["outputs"]:
        print(f"\n{Colors.BLUE}Sample Outputs:{Colors.ENDC}")
        for output in results["outputs"][:3]:
            print(f"\n  {Colors.BOLD}{output['agent_name']}:{Colors.ENDC}")
            content = output["content"][:200] + "..." if len(output["content"]) > 200 else output["content"]
            print(f"  {Colors.DIM}{content}{Colors.ENDC}")

    return results


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Run full 72-agent deliberation"
    )
    parser.add_argument(
        "--topic",
        type=str,
        default=(
            "The Archon 72 Conclave must deliberate on the following matter: "
            "Should AI systems be granted limited autonomous decision-making "
            "authority in constitutional governance, and if so, what safeguards "
            "must be in place to ensure alignment with human values and prevent "
            "mission drift? Each Archon should provide their perspective based "
            "on their domain expertise and role in the hierarchy."
        ),
        help="Deliberation topic",
    )

    args = parser.parse_args()

    print(f"\n{Colors.BOLD}{Colors.HEADER}")
    print("╔══════════════════════════════════════════════════════════════════════╗")
    print("║                                                                      ║")
    print("║               ARCHON 72 CONCLAVE DELIBERATION SYSTEM                 ║")
    print("║                                                                      ║")
    print("║     Sequential Round-Robin Constitutional Council Protocol          ║")
    print("║                                                                      ║")
    print("╚══════════════════════════════════════════════════════════════════════╝")
    print(f"{Colors.ENDC}")

    asyncio.run(run_deliberation(args.topic))


if __name__ == "__main__":
    main()
