#!/usr/bin/env python3
"""Generate Executive Implementation Dossiers from Conclave mandates.

The Executive branch translates Legislative mandates (WHAT) into detailed
requirements for the Administrative branch (WHO does HOW).

All 11 Presidents contribute requirements and constraints from their
portfolio perspective, producing an Executive Implementation Dossier.

Usage:
    python scripts/run_rfp_generator.py --from-conclave _bmad-output/conclave
    python scripts/run_rfp_generator.py --from-ledger _bmad-output/motion-ledger/<session_id>
    python scripts/run_rfp_generator.py --mandate-file <mandate.json>
"""

from __future__ import annotations

import argparse
import asyncio
import glob
import json
import sys
from pathlib import Path
from uuid import UUID

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()


def find_latest_conclave_results() -> Path | None:
    """Find the most recent conclave results file."""
    pattern = "_bmad-output/conclave/conclave-results-*.json"
    files = glob.glob(pattern)
    if not files:
        return None
    return Path(max(files, key=lambda f: Path(f).stat().st_mtime))


def find_latest_ledger_session() -> Path | None:
    """Find the most recent motion ledger session."""
    pattern = "_bmad-output/motion-ledger/*"
    dirs = [d for d in glob.glob(pattern) if Path(d).is_dir()]
    if not dirs:
        return None
    return Path(max(dirs, key=lambda d: Path(d).stat().st_mtime))


def load_presidents() -> list[dict]:
    """Load all 11 Presidents with canonical portfolio IDs."""
    from src.infrastructure.adapters.config.archon_profile_adapter import (
        create_archon_profile_repository,
    )

    repo = create_archon_profile_repository()

    archons_path = Path("docs/archons-base.json")
    with open(archons_path, encoding="utf-8") as f:
        data = json.load(f)
        archons = data.get("archons", data) if isinstance(data, dict) else data

    presidents: list[dict] = []
    for archon in archons:
        if archon.get("branch") != "executive":
            continue
        original_rank = archon.get("original_rank") or archon.get("rank") or ""
        if original_rank != "President":
            continue

        portfolio_id = archon.get("portfolio_id")
        if not portfolio_id:
            continue

        portfolio_label = archon.get("portfolio_label") or archon.get("role") or ""
        profile = repo.get_by_id(UUID(archon["id"]))
        llm_config = profile.llm_config if profile else None

        presidents.append(
            {
                "id": archon["id"],
                "name": archon["name"],
                "portfolio_id": portfolio_id,
                "portfolio_label": portfolio_label,
                "domain": portfolio_label,
                "llm_config": llm_config,
            }
        )

    return presidents


def load_mandates_from_conclave(conclave_path: Path) -> list[dict]:
    """Load passed mandates from conclave results."""
    # First run registrar to get mandates
    from scripts import run_registrar

    ledger_outdir = Path("_bmad-output/motion-ledger")
    mandates_path = run_registrar.register_conclave(conclave_path, ledger_outdir)

    with open(mandates_path, encoding="utf-8") as f:
        data = json.load(f)

    return data.get("mandates", [])


def load_mandates_from_ledger(ledger_path: Path) -> list[dict]:
    """Load mandates from motion ledger."""
    if ledger_path.is_file():
        mandates_file = ledger_path
    else:
        mandates_file = ledger_path / "ratified_mandates.json"

    if not mandates_file.exists():
        raise FileNotFoundError(f"No ratified_mandates.json found at {ledger_path}")

    with open(mandates_file, encoding="utf-8") as f:
        data = json.load(f)

    return data.get("mandates", [])


def load_mandate_from_file(mandate_file: Path) -> dict:
    """Load a single mandate from a JSON file."""
    with open(mandate_file, encoding="utf-8") as f:
        return json.load(f)


async def generate_rfp_for_mandate(
    mandate: dict,
    presidents: list[dict],
    rfp_contributor,
    output_dir: Path,
    deliberation_rounds: int,
    verbose: bool,
    session_id: str | None = None,
) -> tuple[Path, str]:
    """Generate a dossier for a single mandate.

    Returns:
        Tuple of (rfp_path, session_id)
    """
    from src.application.services.rfp_generation_service import RFPGenerationService

    events: list[dict] = []

    def event_sink(event_type: str, payload: dict) -> None:
        events.append({"type": event_type, "payload": payload})
        if verbose:
            print(f"  [{event_type}] {payload}")

    service = RFPGenerationService(
        rfp_contributor=rfp_contributor,
        event_sink=event_sink,
        verbose=verbose,
        session_id=session_id,
    )

    mandate_id = mandate.get("mandate_id", mandate.get("motion_id", "unknown"))
    motion_title = mandate.get("title", mandate.get("motion_title", "Untitled"))
    motion_text = mandate.get("text", mandate.get("motion_text", ""))

    print(f"\n{'=' * 60}")
    print(f"Generating Implementation Dossier for: {motion_title}")
    print(f"Mandate ID: {mandate_id}")
    print(f"Session ID: {service.session_id}")
    print(f"{'=' * 60}")

    rfp = await service.generate_rfp(
        mandate_id=mandate_id,
        motion_title=motion_title,
        motion_text=motion_text,
        presidents=presidents,
        business_justification=mandate.get("business_justification", ""),
        strategic_alignment=mandate.get("strategic_alignment", []),
        deliberation_rounds=deliberation_rounds,
        expected_portfolios=[p["portfolio_id"] for p in presidents],
    )

    # Save RFP with session-based structure (events are now passed to save_rfp)
    rfp_path = service.save_rfp(rfp, output_dir, events=events)

    print("\nImplementation Dossier Generated:")
    print(f"  - Functional Requirements: {len(rfp.functional_requirements)}")
    print(f"  - Non-Functional Requirements: {len(rfp.non_functional_requirements)}")
    print(f"  - Constraints: {len(rfp.constraints)}")
    print(f"  - Evaluation Criteria: {len(rfp.evaluation_criteria)}")
    print(f"  - Deliverables: {len(rfp.deliverables)}")
    print(f"  - Contributing Portfolios: {len(rfp.portfolio_contributions)}")
    print(f"  - Unresolved Conflicts: {len(rfp.unresolved_conflicts)}")
    print(f"  - Status: {rfp.status.value}")
    print(f"\nSaved to: {output_dir / service.session_id}")

    return rfp_path, service.session_id


def init_rfp_contributor(args):
    """Initialize the RFP contributor adapter."""
    if args.mode == "simulation":
        return None

    from src.infrastructure.adapters.config.archon_profile_adapter import (
        create_archon_profile_repository,
    )
    from src.infrastructure.adapters.external import create_rfp_contributor

    print("Initializing RFP contributor with per-President LLM bindings...")
    profile_repo = create_archon_profile_repository()

    if args.provider:
        print(f"  Provider override: {args.provider}")
    if args.model:
        print(f"  Model override: {args.model}")
    if args.base_url:
        print(f"  Base URL override: {args.base_url}")

    return create_rfp_contributor(
        profile_repository=profile_repo,
        verbose=args.verbose,
        model=args.model,
        provider=args.provider,
        base_url=args.base_url,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate RFP documents from Conclave mandates",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # Input sources (mutually exclusive)
    input_group = parser.add_mutually_exclusive_group()
    input_group.add_argument(
        "--from-conclave",
        type=Path,
        default=None,
        help="Path to conclave results JSON or conclave output directory",
    )
    input_group.add_argument(
        "--from-ledger",
        type=Path,
        default=None,
        help="Path to motion ledger session directory or ratified_mandates.json",
    )
    input_group.add_argument(
        "--mandate-file",
        type=Path,
        default=None,
        help="Path to a single mandate JSON file",
    )

    parser.add_argument(
        "--mandate-id",
        type=str,
        default=None,
        help="Filter to a single mandate ID",
    )
    parser.add_argument(
        "--outdir",
        type=Path,
        default=Path("_bmad-output/rfp"),
        help="Output directory for RFP documents",
    )
    parser.add_argument(
        "--mode",
        type=str,
        choices=["llm", "simulation"],
        default="llm",
        help="Mode: 'llm' uses LLM-powered generation, 'simulation' uses templates",
    )
    parser.add_argument(
        "--deliberation-rounds",
        type=int,
        default=0,
        help="Number of deliberation rounds (0 = no deliberation, just contributions)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Override LLM model for all Presidents (e.g., 'llama3.2:latest')",
    )
    parser.add_argument(
        "--provider",
        type=str,
        default=None,
        help="Override LLM provider for all Presidents (e.g., 'ollama', 'openai', 'anthropic')",
    )
    parser.add_argument(
        "--base-url",
        type=str,
        default=None,
        help="Override LLM base URL for all Presidents (e.g., 'http://localhost:11434')",
    )

    args = parser.parse_args()

    # Resolve input source
    mandates: list[dict] = []

    if args.from_conclave:
        print(f"Loading mandates from Conclave: {args.from_conclave}")
        mandates = load_mandates_from_conclave(args.from_conclave)
    elif args.from_ledger:
        print(f"Loading mandates from Ledger: {args.from_ledger}")
        mandates = load_mandates_from_ledger(args.from_ledger)
    elif args.mandate_file:
        print(f"Loading mandate from file: {args.mandate_file}")
        mandates = [load_mandate_from_file(args.mandate_file)]
    else:
        # Auto-detect latest source
        conclave_results = find_latest_conclave_results()
        ledger_session = find_latest_ledger_session()

        if ledger_session and (
            not conclave_results
            or ledger_session.stat().st_mtime > conclave_results.stat().st_mtime
        ):
            print(f"Auto-detected ledger session: {ledger_session}")
            mandates = load_mandates_from_ledger(ledger_session)
        elif conclave_results:
            print(f"Auto-detected conclave results: {conclave_results}")
            mandates = load_mandates_from_conclave(conclave_results)
        else:
            print(
                "Error: No input source found. Specify --from-conclave, --from-ledger, or --mandate-file"
            )
            sys.exit(1)

    if not mandates:
        print("No mandates found to process.")
        sys.exit(1)

    # Filter by mandate ID if specified
    if args.mandate_id:
        mandates = [
            m
            for m in mandates
            if m.get("mandate_id") == args.mandate_id
            or m.get("motion_id") == args.mandate_id
        ]
        if not mandates:
            print(f"No mandate found with ID: {args.mandate_id}")
            sys.exit(1)

    print(f"\nFound {len(mandates)} mandate(s) to process")

    # Load Presidents
    presidents = load_presidents()
    print(f"Loaded {len(presidents)} Presidents for contribution")
    for p in presidents:
        label = p.get("portfolio_label") or p.get("domain") or ""
        label_display = f"{label} / {p['portfolio_id']}" if label else p["portfolio_id"]
        print(f"  - {p['name']} ({label_display})")

    # Initialize RFP contributor
    rfp_contributor = init_rfp_contributor(args)

    # Generate RFPs
    args.outdir.mkdir(parents=True, exist_ok=True)
    rfp_paths = []
    session_id = None  # Share session across all mandates

    for mandate in mandates:
        rfp_path, session_id = asyncio.run(
            generate_rfp_for_mandate(
                mandate=mandate,
                presidents=presidents,
                rfp_contributor=rfp_contributor,
                output_dir=args.outdir,
                deliberation_rounds=args.deliberation_rounds,
                verbose=args.verbose,
                session_id=session_id,  # Reuse session for all mandates
            )
        )
        rfp_paths.append(rfp_path)

    # Print summary
    print(f"\n{'=' * 60}")
    print("RFP GENERATION COMPLETE")
    print(f"{'=' * 60}")
    print(f"Session ID: {session_id}")
    print(f"Mandates processed: {len(mandates)}")
    print(f"RFPs generated: {len(rfp_paths)}")
    print(f"Mode: {args.mode}")
    print(f"Deliberation rounds: {args.deliberation_rounds}")
    print(f"Output directory: {args.outdir}/{session_id}")
    print(f"{'=' * 60}\n")

    # List generated RFPs
    print("Generated RFPs:")
    for rfp_path in rfp_paths:
        print(f"  - {rfp_path}")


if __name__ == "__main__":
    main()
