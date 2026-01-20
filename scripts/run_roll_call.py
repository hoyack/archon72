#!/usr/bin/env python3
"""Archon 72 Roll Call - LLM Configuration Test.

Tests each Archon's LLM configuration by sending a simple "Who goes there?"
prompt to verify that the LLM can be instantiated and respond correctly.
Useful for diagnosing which Archons have broken LLM configurations.

Usage:
    python scripts/run_roll_call.py [options]

Options:
    --archon NAME        Test a specific archon by name
    --limit N            Test only first N archons (default: all)
    --timeout SEC        Timeout per archon in seconds (default: 60)
    --delay SEC          Delay between each archon in seconds (default: 2)
    --verbose            Show full responses from archons
    --parallel           Run tests in parallel (default: sequential)
"""

import argparse
import asyncio
import os
import sys
import time
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


def print_banner() -> None:
    """Print the Roll Call banner."""
    print(f"\n{Colors.BOLD}{Colors.HEADER}")
    print("+" + "=" * 70 + "+")
    print("|" + " " * 70 + "|")
    print("|" + "ARCHON 72 ROLL CALL".center(70) + "|")
    print("|" + "LLM Configuration Test".center(70) + "|")
    print("|" + " " * 70 + "|")
    print("+" + "=" * 70 + "+")
    print(f"{Colors.ENDC}")


def print_header(text: str) -> None:
    """Print a formatted header."""
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'=' * 70}")
    print(f"  {text}")
    print(f"{'=' * 70}{Colors.ENDC}\n")


async def test_archon(
    adapter,
    profile,
    timeout_seconds: int = 60,
) -> dict:
    """Test a single archon's LLM configuration.

    Args:
        adapter: The CrewAI adapter
        profile: The archon profile to test
        timeout_seconds: Timeout for the test

    Returns:
        Dictionary with test results
    """
    from uuid import uuid4

    from src.application.ports.agent_orchestrator import ContextBundle

    start_time = time.time()
    result = {
        "name": profile.name,
        "id": str(profile.id),
        "rank": profile.aegis_rank,
        "provider": profile.llm_config.provider,
        "model": profile.llm_config.model,
        "base_url": profile.llm_config.base_url,
        "success": False,
        "error": None,
        "response": None,
        "duration_seconds": 0,
    }

    try:
        # Create a simple test context
        context = ContextBundle(
            bundle_id=uuid4(),
            topic_id="roll-call-test",
            topic_content=(
                "WHO GOES THERE?\n\n"
                "You are being tested for LLM configuration. "
                "Please respond with:\n"
                "1. Your name\n"
                "2. Your rank\n"
                "3. A brief statement of your domain or specialty\n\n"
                "Keep your response under 100 words."
            ),
            metadata=None,
            created_at=datetime.now(),
        )

        # Invoke the agent
        output = await asyncio.wait_for(
            adapter.invoke(str(profile.id), context),
            timeout=timeout_seconds,
        )

        result["success"] = True
        result["response"] = output.content
        result["duration_seconds"] = time.time() - start_time

    except TimeoutError:
        result["error"] = f"Timeout after {timeout_seconds}s"
        result["duration_seconds"] = time.time() - start_time
    except Exception as e:
        result["error"] = str(e)
        result["duration_seconds"] = time.time() - start_time

    return result


async def run_roll_call(args: argparse.Namespace) -> None:  # noqa: C901
    """Run the roll call test.

    Args:
        args: Parsed command line arguments
    """
    from src.infrastructure.adapters.config.archon_profile_adapter import (
        create_archon_profile_repository,
    )
    from src.infrastructure.adapters.external.crewai_adapter import (
        create_crewai_adapter,
    )

    print_banner()
    print_header("INITIALIZING ROLL CALL")

    # Load archon profiles
    print(f"{Colors.BLUE}Loading Archon profiles...{Colors.ENDC}")
    profile_repo = create_archon_profile_repository()
    all_profiles = profile_repo.get_all()
    print(f"  Loaded {len(all_profiles)} Archon profiles")

    # Filter profiles if specific archon requested
    if args.archon:
        all_profiles = [
            p for p in all_profiles if p.name.lower() == args.archon.lower()
        ]
        if not all_profiles:
            print(f"{Colors.RED}Error: Archon '{args.archon}' not found{Colors.ENDC}")
            sys.exit(1)
        print(f"  Testing specific archon: {args.archon}")

    # Apply limit
    if args.limit and args.limit > 0:
        all_profiles = all_profiles[: args.limit]
        print(f"  Limited to first {args.limit} archons")

    # Show configuration
    print(f"\n{Colors.BLUE}Configuration:{Colors.ENDC}")
    print(f"  OLLAMA_HOST: {os.environ.get('OLLAMA_HOST', 'not set')}")
    print(f"  Timeout per archon: {args.timeout}s")
    print(f"  Delay between tests: {args.delay}s")
    print(f"  Mode: {'parallel' if args.parallel else 'sequential'}")
    print(f"  Archons to test: {len(all_profiles)}")

    # Show LLM configuration summary
    print(f"\n{Colors.BLUE}LLM Configuration Summary:{Colors.ENDC}")
    provider_counts: dict[str, int] = {}
    model_counts: dict[str, int] = {}
    for p in all_profiles:
        provider_counts[p.llm_config.provider] = (
            provider_counts.get(p.llm_config.provider, 0) + 1
        )
        model_counts[p.llm_config.model] = model_counts.get(p.llm_config.model, 0) + 1

    for provider, count in sorted(provider_counts.items()):
        print(f"  {provider}: {count} archons")

    print(f"\n{Colors.BLUE}Models in use:{Colors.ENDC}")
    for model, count in sorted(model_counts.items(), key=lambda x: -x[1]):
        print(f"  {model}: {count} archons")

    # Create CrewAI adapter
    print(f"\n{Colors.BLUE}Initializing CrewAI adapter...{Colors.ENDC}")
    adapter = create_crewai_adapter(
        profile_repository=profile_repo,
        verbose=args.verbose,
        include_default_tools=False,
    )

    print_header("ROLL CALL IN PROGRESS")

    results: list[dict] = []
    success_count = 0
    failure_count = 0

    if args.parallel:
        # Run all tests in parallel
        print(f"{Colors.YELLOW}Running {len(all_profiles)} tests in parallel...{Colors.ENDC}\n")
        tasks = [
            test_archon(adapter, p, args.timeout) for p in all_profiles
        ]
        results = await asyncio.gather(*tasks)

        for result in results:
            if result["success"]:
                success_count += 1
                status = f"{Colors.GREEN}PRESENT{Colors.ENDC}"
            else:
                failure_count += 1
                status = f"{Colors.RED}FAILED{Colors.ENDC}"

            print(
                f"\n  [{status}] {result['name']} ({result['rank']}) - "
                f"{result['provider']}/{result['model']} - {result['duration_seconds']:.1f}s"
            )
            if result["error"]:
                print(f"  {Colors.RED}ERROR:{Colors.ENDC} {result['error']}")
            if result["response"]:
                # Show full response, indented
                print(f"  {Colors.CYAN}RESPONSE:{Colors.ENDC}")
                for line in result["response"].split("\n"):
                    print(f"    {line}")
    else:
        # Run tests sequentially with progress
        for i, profile in enumerate(all_profiles, 1):
            progress = f"{i}/{len(all_profiles)}"
            print(
                f"\n{'=' * 70}\n"
                f"  [{Colors.DIM}{progress}{Colors.ENDC}] Testing {Colors.BOLD}{profile.name}{Colors.ENDC} "
                f"({profile.aegis_rank})\n"
                f"  Model: {profile.llm_config.provider}/{profile.llm_config.model}"
            )
            if profile.llm_config.base_url:
                print(f"  Base URL: {profile.llm_config.base_url}")
            print()

            result = await test_archon(adapter, profile, args.timeout)
            results.append(result)

            if result["success"]:
                success_count += 1
                print(
                    f"  [{Colors.GREEN}PRESENT{Colors.ENDC}] {profile.name} responded in "
                    f"{result['duration_seconds']:.1f}s"
                )
                print(f"\n  {Colors.CYAN}RESPONSE:{Colors.ENDC}")
                for line in result["response"].split("\n"):
                    print(f"    {line}")
            else:
                failure_count += 1
                print(
                    f"  [{Colors.RED}FAILED{Colors.ENDC}] {profile.name} after "
                    f"{result['duration_seconds']:.1f}s"
                )
                print(f"\n  {Colors.RED}ERROR:{Colors.ENDC} {result['error']}")

            # Rate limiting delay between tests (skip after last one)
            if args.delay > 0 and i < len(all_profiles):
                print(f"\n  {Colors.DIM}Waiting {args.delay}s before next test...{Colors.ENDC}")
                await asyncio.sleep(args.delay)

    # Print summary
    print_header("ROLL CALL SUMMARY")

    total = len(results)
    success_pct = (success_count / total * 100) if total > 0 else 0

    if success_count == total:
        status_color = Colors.GREEN
        status_text = "ALL PRESENT"
    elif success_count == 0:
        status_color = Colors.RED
        status_text = "ALL FAILED"
    else:
        status_color = Colors.YELLOW
        status_text = "PARTIAL"

    print(f"  Status: {status_color}{Colors.BOLD}{status_text}{Colors.ENDC}")
    print(f"  Present: {Colors.GREEN}{success_count}{Colors.ENDC}/{total} ({success_pct:.1f}%)")
    print(f"  Failed: {Colors.RED}{failure_count}{Colors.ENDC}/{total}")

    # List failed archons
    if failure_count > 0:
        print(f"\n{Colors.RED}Failed Archons:{Colors.ENDC}")
        for result in results:
            if not result["success"]:
                print(
                    f"  - {result['name']} ({result['rank']}): "
                    f"{result['provider']}/{result['model']}"
                )
                print(f"    Error: {result['error']}")
                if result.get("base_url"):
                    print(f"    Base URL: {result['base_url']}")

    # Show provider/model failure breakdown
    if failure_count > 0:
        print(f"\n{Colors.YELLOW}Failure Breakdown:{Colors.ENDC}")
        failure_by_model: dict[str, list[str]] = {}
        for result in results:
            if not result["success"]:
                key = f"{result['provider']}/{result['model']}"
                if key not in failure_by_model:
                    failure_by_model[key] = []
                failure_by_model[key].append(result["name"])

        for model, archons in sorted(failure_by_model.items(), key=lambda x: -len(x[1])):
            print(f"  {model}: {len(archons)} failures")
            if len(archons) <= 5:
                print(f"    Archons: {', '.join(archons)}")


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Test Archon LLM configurations with a roll call",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test all archons (sequential, 2s delay between each)
  python scripts/run_roll_call.py

  # Test specific archon
  python scripts/run_roll_call.py --archon Paimon

  # Test first 10 archons with 5 second delay
  python scripts/run_roll_call.py --limit 10 --delay 5

  # No delay between tests (faster but may overwhelm API)
  python scripts/run_roll_call.py --delay 0

  # Run in parallel with longer timeout (no delay in parallel mode)
  python scripts/run_roll_call.py --parallel --timeout 120

  # Verbose output showing responses
  python scripts/run_roll_call.py --verbose --limit 5
""",
    )
    parser.add_argument(
        "--archon",
        type=str,
        help="Test a specific archon by name",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Test only first N archons (default: all)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=60,
        help="Timeout per archon in seconds (default: 60)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=2.0,
        help="Delay between each archon in seconds (default: 2)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show full responses from archons",
    )
    parser.add_argument(
        "--parallel",
        action="store_true",
        help="Run tests in parallel (default: sequential)",
    )

    args = parser.parse_args()
    asyncio.run(run_roll_call(args))


if __name__ == "__main__":
    main()
