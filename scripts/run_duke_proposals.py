#!/usr/bin/env python3
"""Run the Duke Proposal Pipeline on a finalized Executive RFP.

Each Administrative Duke reads the RFP and produces a complete implementation
proposal describing HOW to accomplish the requirements from their domain expertise.

Multi-pass pipeline (5 phases per Duke) with optional checkpointing:
  Phase 1: Strategic Foundation (Overview, Issues, Philosophy)
  Phase 2: Per-Deliverable Solutions (Tactics, Risks, Resources) - N calls
  Phase 3: Cross-Cutting (Coverage table, Deliverable plan, Assumptions, Constraints)
  Phase 4: Consolidation Review (secretary text agent reviews for consistency)
  Phase 5: Executive Summary (synthesises the completed proposal)

Pipeline Position:
    Legislative (Motion) -> Executive (RFP) -> Administrative (Duke Proposals) <- THIS
                                             -> Executive (Selection)          <- LATER
                                             -> Administrative (Execution)     <- DONE

Usage:
    python scripts/run_duke_proposals.py                           # auto-detect latest RFP
    python scripts/run_duke_proposals.py --rfp-file path/rfp.json  # explicit RFP
    python scripts/run_duke_proposals.py --duke-name Agares        # single Duke
    python scripts/run_duke_proposals.py --mode simulation -v      # no LLM
    python scripts/run_duke_proposals.py --no-checkpoint           # disable checkpointing
    python scripts/run_duke_proposals.py --clear-checkpoints       # fresh run
"""

from __future__ import annotations

import argparse
import asyncio
import glob
import json
import os
import shutil
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()


def _save_json(path: Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2)


def _save_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row))
            f.write("\n")


def _find_latest_rfp_session() -> Path | None:
    """Find the most recent RFP session directory."""
    pattern = "_bmad-output/rfp/*"
    dirs = [d for d in glob.glob(pattern) if Path(d).is_dir()]
    if not dirs:
        return None
    return Path(max(dirs, key=lambda d: Path(d).stat().st_mtime))


def _find_rfp_in_session(
    session_dir: Path, mandate_id: str | None = None
) -> Path | None:
    """Find rfp.json within a session directory."""
    mandates_dir = session_dir / "mandates"
    if not mandates_dir.exists():
        # Try direct rfp.json in session dir
        rfp_path = session_dir / "rfp.json"
        if rfp_path.exists():
            return rfp_path
        return None

    # Look through mandate subdirectories
    mandate_dirs = sorted(mandates_dir.iterdir())
    if mandate_id:
        # Find specific mandate
        for md in mandate_dirs:
            if md.is_dir() and mandate_id in md.name:
                rfp_path = md / "rfp.json"
                if rfp_path.exists():
                    return rfp_path
        return None

    # Return first rfp.json found
    for md in mandate_dirs:
        if md.is_dir():
            rfp_path = md / "rfp.json"
            if rfp_path.exists():
                return rfp_path

    return None


def _load_dukes(duke_name: str | None = None) -> list[dict]:
    """Load Duke archons from archons-base.json.

    Args:
        duke_name: If specified, filter to just this Duke

    Returns:
        List of duke dicts from archons-base.json
    """
    archons_path = Path("docs/archons-base.json")
    if not archons_path.exists():
        print(f"Error: archons-base.json not found at {archons_path}")
        sys.exit(1)

    with open(archons_path, encoding="utf-8") as f:
        data = json.load(f)

    archons = data.get("archons", [])
    dukes = [a for a in archons if a.get("branch") == "administrative_senior"]

    if duke_name:
        dukes = [d for d in dukes if d.get("name", "").lower() == duke_name.lower()]
        if not dukes:
            print(f"Error: Duke '{duke_name}' not found in archons-base.json")
            available = [
                a.get("name")
                for a in archons
                if a.get("branch") == "administrative_senior"
            ]
            print(f"Available Dukes: {', '.join(available)}")
            sys.exit(1)

    return dukes


def _resolve_rfp_path(args: argparse.Namespace) -> Path:
    """Resolve the RFP file path from CLI arguments."""
    rfp_path: Path | None = args.rfp_file

    if rfp_path is None and args.from_rfp_session:
        rfp_path = _find_rfp_in_session(args.from_rfp_session, args.mandate_id)
        if rfp_path is None:
            print(f"Error: No rfp.json found in session: {args.from_rfp_session}")
            sys.exit(1)
        print(f"Found RFP in session: {rfp_path}")

    if rfp_path is None:
        session_dir = _find_latest_rfp_session()
        if session_dir is None:
            print("Error: No RFP session found.")
            print("Run Executive Pipeline first or specify --rfp-file explicitly.")
            print("Looking for: _bmad-output/rfp/*/")
            sys.exit(1)
        rfp_path = _find_rfp_in_session(session_dir, args.mandate_id)
        if rfp_path is None:
            print(f"Error: No rfp.json found in session: {session_dir}")
            sys.exit(1)
        print(f"Auto-detected RFP: {rfp_path}")

    rfp_path = rfp_path.resolve()
    if not rfp_path.exists():
        print(f"Error: RFP file not found: {rfp_path}")
        sys.exit(1)

    return rfp_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run Duke Proposal Pipeline on a finalized Executive RFP"
    )
    parser.add_argument(
        "--rfp-file",
        type=Path,
        default=None,
        help="Path to rfp.json file (auto-detects if not specified)",
    )
    parser.add_argument(
        "--from-rfp-session",
        type=Path,
        default=None,
        help="Path to RFP session directory to find rfp.json in",
    )
    parser.add_argument(
        "--mandate-id",
        type=str,
        default=None,
        help="Mandate ID to process (when multiple mandates exist)",
    )
    parser.add_argument(
        "--outdir",
        type=Path,
        default=None,
        help="Output directory (defaults to RFP session mandate dir)",
    )
    parser.add_argument(
        "--mode",
        type=str,
        choices=["llm", "simulation", "auto"],
        default="auto",
        help=(
            "Generation mode: 'llm' uses LLM, 'simulation' generates test proposals, "
            "'auto' uses LLM when available (default: auto)"
        ),
    )
    parser.add_argument(
        "--duke-name",
        type=str,
        default=None,
        help="Generate proposal for a single Duke only",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Override LLM model name",
    )
    parser.add_argument(
        "--provider",
        type=str,
        default=None,
        help="Override LLM provider (e.g., 'ollama', 'openai', 'anthropic')",
    )
    parser.add_argument(
        "--base-url",
        type=str,
        default=None,
        help="Override LLM base URL",
    )
    parser.add_argument(
        "--checkpoint-dir",
        type=Path,
        default=None,
        help="Override checkpoint directory for multi-pass pipeline",
    )
    parser.add_argument(
        "--no-checkpoint",
        action="store_true",
        help="Disable checkpointing (each run starts fresh, no resume)",
    )
    parser.add_argument(
        "--clear-checkpoints",
        action="store_true",
        help="Delete existing checkpoint directory before starting",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    # ------------------------------------------------------------------
    # Resolve RFP path
    # ------------------------------------------------------------------
    rfp_path = _resolve_rfp_path(args)

    # ------------------------------------------------------------------
    # Load RFP
    # ------------------------------------------------------------------
    from src.application.services.duke_proposal_service import (  # noqa: E402
        DukeProposalService,
    )

    rfp = DukeProposalService.load_rfp(rfp_path)
    print(f"Loaded RFP: {rfp.implementation_dossier_id}")
    print(f"  Mandate: {rfp.mandate_id}")
    print(f"  Status: {rfp.status.value}")
    print(
        f"  FRs: {len(rfp.functional_requirements)}, NFRs: {len(rfp.non_functional_requirements)}"
    )
    print(
        f"  Constraints: {len(rfp.constraints)}, Deliverables: {len(rfp.deliverables)}"
    )

    # ------------------------------------------------------------------
    # Load Dukes
    # ------------------------------------------------------------------
    dukes = _load_dukes(args.duke_name)
    print(f"\nDukes to process: {len(dukes)}")
    for d in dukes:
        print(f"  - {d.get('name')}: {d.get('role')}")

    # ------------------------------------------------------------------
    # Setup events
    # ------------------------------------------------------------------
    events: list[dict] = []

    def event_sink(event_type: str, payload: dict) -> None:
        events.append({"type": event_type, "payload": payload})

    # ------------------------------------------------------------------
    # Determine output directory
    # ------------------------------------------------------------------
    output_dir = args.outdir or rfp_path.parent

    # ------------------------------------------------------------------
    # Resolve checkpoint directory
    # ------------------------------------------------------------------
    checkpoint_dir: Path | None = None
    if not args.no_checkpoint:
        checkpoint_dir = args.checkpoint_dir or output_dir / "proposal_drafts"

        if args.clear_checkpoints and checkpoint_dir.exists():
            print(f"\nClearing checkpoint directory: {checkpoint_dir}")
            shutil.rmtree(checkpoint_dir)

        print(f"\nCheckpoint directory: {checkpoint_dir}")
    else:
        print("\nCheckpointing disabled (--no-checkpoint)")

    # ------------------------------------------------------------------
    # Read secretary archon ID (same pattern as run_proposal_selection.py)
    # ------------------------------------------------------------------
    secretary_text_archon_id = os.getenv("SECRETARY_TEXT_ARCHON_ID", "").strip() or None

    if secretary_text_archon_id:
        print(f"Secretary Text Archon: {secretary_text_archon_id}")
    else:
        print(
            "Warning: SECRETARY_TEXT_ARCHON_ID not set, "
            "Phase 4 consolidation will be skipped"
        )

    # ------------------------------------------------------------------
    # Create service and generate proposals
    # ------------------------------------------------------------------
    generator = None
    use_llm = args.mode in ("llm", "auto")

    if use_llm:
        try:
            from src.infrastructure.adapters.config.archon_profile_adapter import (
                create_archon_profile_repository,
            )
            from src.infrastructure.adapters.external.duke_proposal_crewai_adapter import (
                create_duke_proposal_generator,
            )

            profile_repo = create_archon_profile_repository()
            generator = create_duke_proposal_generator(
                profile_repository=profile_repo,
                verbose=args.verbose,
                model=args.model,
                provider=args.provider,
                base_url=args.base_url,
                secretary_text_archon_id=secretary_text_archon_id,
                checkpoint_dir=checkpoint_dir,
            )
            print(
                f"\nLoaded {profile_repo.count()} Archon profiles"
                " for per-Duke LLM bindings"
            )
        except ImportError as e:
            print(f"\nWarning: Could not load LLM adapter: {e}")
            if args.mode == "llm":
                print("LLM mode requested but adapter unavailable.")
                sys.exit(1)
            print("Falling back to simulation mode")

    service = DukeProposalService(
        duke_proposal_generator=generator,
        event_sink=event_sink,
        verbose=args.verbose,
    )

    # Generate proposals
    if generator is not None and use_llm:
        print("\nGenerating proposals via LLM (5-phase pipeline)...")
        try:
            proposals = asyncio.run(service.generate_all_proposals(rfp, dukes))
        except Exception as e:
            print(f"LLM error: {e}")
            if args.mode == "llm":
                sys.exit(1)
            print("Falling back to simulation mode...")
            proposals = service._simulate_proposals(rfp, dukes)
    else:
        print("\nGenerating proposals (simulation mode)...")
        proposals = service._simulate_proposals(rfp, dukes)

    # ------------------------------------------------------------------
    # Save results
    # ------------------------------------------------------------------
    proposals_dir = service.save_proposals(proposals, rfp, output_dir)

    # Save events
    _save_jsonl(proposals_dir / "duke_proposal_events.jsonl", events)

    # ------------------------------------------------------------------
    # Print summary
    # ------------------------------------------------------------------
    generated = sum(1 for p in proposals if p.status.value == "GENERATED")
    failed = sum(1 for p in proposals if p.status.value == "FAILED")
    simulation = sum(1 for p in proposals if p.status.value == "SIMULATION")

    print("\n" + "=" * 60)
    print("DUKE PROPOSAL PIPELINE COMPLETE")
    print("=" * 60)
    print(f"RFP: {rfp.implementation_dossier_id}")
    print(f"Mandate: {rfp.mandate_id}")
    print(f"Total proposals: {len(proposals)}")
    print(f"  Generated (LLM): {generated}")
    print(f"  Failed: {failed}")
    print(f"  Simulation: {simulation}")
    print(f"Total tactics: {sum(p.tactic_count for p in proposals)}")
    print(f"Total risks: {sum(p.risk_count for p in proposals)}")
    print(
        f"Total resource requests: {sum(p.resource_request_count for p in proposals)}"
    )
    print(f"Mode: {args.mode}")
    print(f"Output saved to: {proposals_dir}")

    for p in proposals:
        status_marker = {
            "GENERATED": "+",
            "FAILED": "X",
            "SIMULATION": "~",
        }.get(p.status.value, "?")
        llm_info = ""
        if args.verbose and (p.llm_provider or p.llm_model):
            llm_info = f" | LLM: {p.llm_provider}/{p.llm_model}"
        print(
            f"  [{status_marker}] {p.duke_name} ({p.duke_abbreviation}): "
            f"{p.tactic_count} tactics, {p.risk_count} risks, "
            f"{p.resource_request_count} resources, "
            f"{p.requirement_coverage_count} coverage, "
            f"{p.deliverable_plan_count} deliverables{llm_info}"
        )

    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
