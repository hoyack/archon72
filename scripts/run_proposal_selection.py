#!/usr/bin/env python3
"""Run the Duke Proposal Selection Pipeline.

The 11 Executive Presidents review, score, rank, and deliberate on
Duke implementation proposals to select a winning proposal for execution.

Pipeline Position:
    Legislative (Motion) -> Executive (RFP) -> Administrative (Duke Proposals)
      -> Executive (Proposal Selection) <- THIS
      -> Administrative (Execution)

Usage:
    python scripts/run_proposal_selection.py                            # auto-detect
    python scripts/run_proposal_selection.py --from-rfp-session <path>
    python scripts/run_proposal_selection.py --mode simulation -v
    python scripts/run_proposal_selection.py --max-rounds 2 --top-n 3
    python scripts/run_proposal_selection.py --score-only
"""

from __future__ import annotations

import argparse
import asyncio
import glob
import json
import os
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


# ------------------------------------------------------------------
# Auto-detection helpers
# ------------------------------------------------------------------


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
        rfp_path = session_dir / "rfp.json"
        if rfp_path.exists():
            return rfp_path
        return None

    mandate_dirs = sorted(mandates_dir.iterdir())
    if mandate_id:
        for md in mandate_dirs:
            if md.is_dir() and mandate_id in md.name:
                rfp_path = md / "rfp.json"
                if rfp_path.exists():
                    return rfp_path
        return None

    for md in mandate_dirs:
        if md.is_dir():
            rfp_path = md / "rfp.json"
            if rfp_path.exists():
                return rfp_path

    return None


def _find_proposals_inbox(
    session_dir: Path, mandate_id: str | None = None
) -> Path | None:
    """Find proposals_inbox directory within a session."""
    mandates_dir = session_dir / "mandates"
    if not mandates_dir.exists():
        inbox = session_dir / "proposals_inbox"
        return inbox if inbox.exists() else None

    mandate_dirs = sorted(mandates_dir.iterdir())
    if mandate_id:
        for md in mandate_dirs:
            if md.is_dir() and mandate_id in md.name:
                inbox = md / "proposals_inbox"
                if inbox.exists():
                    return inbox
        return None

    for md in mandate_dirs:
        if md.is_dir():
            inbox = md / "proposals_inbox"
            if inbox.exists():
                return inbox

    return None


def _load_presidents() -> list[dict]:
    """Load Executive President archons from archons-base.json."""
    archons_path = Path("docs/archons-base.json")
    if not archons_path.exists():
        print(f"Error: archons-base.json not found at {archons_path}")
        sys.exit(1)

    with open(archons_path, encoding="utf-8") as f:
        data = json.load(f)

    archons = data.get("archons", [])
    presidents = [a for a in archons if a.get("branch") == "executive"]

    if not presidents:
        print("Error: No Executive branch archons found in archons-base.json")
        sys.exit(1)

    return presidents


def _resolve_paths(args: argparse.Namespace) -> tuple[Path, Path, Path]:
    """Resolve RFP path, proposals inbox path, and output directory.

    Returns:
        Tuple of (rfp_path, proposals_inbox_path, output_dir)
    """
    session_dir: Path | None = None

    if args.from_rfp_session:
        session_dir = args.from_rfp_session
        if not session_dir.exists():
            print(f"Error: Session directory not found: {session_dir}")
            sys.exit(1)
        print(f"Using RFP session: {session_dir}")
    else:
        session_dir = _find_latest_rfp_session()
        if session_dir is None:
            print("Error: No RFP session found.")
            print("Run Executive Pipeline and Duke Proposal Pipeline first.")
            print("Looking for: _bmad-output/rfp/*/")
            sys.exit(1)
        print(f"Auto-detected RFP session: {session_dir}")

    # Find RFP
    rfp_path = _find_rfp_in_session(session_dir, args.mandate_id)
    if rfp_path is None:
        print(f"Error: No rfp.json found in session: {session_dir}")
        sys.exit(1)
    print(f"Found RFP: {rfp_path}")

    # Find proposals inbox
    proposals_inbox = _find_proposals_inbox(session_dir, args.mandate_id)
    if proposals_inbox is None:
        print(f"Error: No proposals_inbox found in session: {session_dir}")
        print("Run the Duke Proposal Pipeline first.")
        sys.exit(1)
    print(f"Found proposals inbox: {proposals_inbox}")

    # Output dir is the mandate directory (parent of proposals_inbox)
    output_dir = proposals_inbox.parent

    return rfp_path.resolve(), proposals_inbox.resolve(), output_dir.resolve()


# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Duke Proposal Selection Pipeline")
    parser.add_argument(
        "--from-rfp-session",
        type=Path,
        default=None,
        help="Path to RFP session directory",
    )
    parser.add_argument(
        "--mandate-id",
        type=str,
        default=None,
        help="Mandate ID (when multiple mandates exist)",
    )
    parser.add_argument(
        "--mode",
        type=str,
        choices=["llm", "simulation"],
        default="llm",
        help="Scoring mode: 'llm' uses LLM, 'simulation' uses deterministic scores (default: llm)",
    )
    parser.add_argument(
        "--max-rounds",
        type=int,
        default=3,
        help="Maximum revision iterations (default: 3)",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=5,
        help="Number of finalists for deliberation (default: 5)",
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
        "--score-only",
        action="store_true",
        help="Stop after scoring (skip deliberation)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    # ------------------------------------------------------------------
    # Resolve paths
    # ------------------------------------------------------------------
    rfp_path, proposals_inbox, output_dir = _resolve_paths(args)

    # ------------------------------------------------------------------
    # Load RFP and proposals
    # ------------------------------------------------------------------
    from src.application.services.proposal_selection_service import (
        ProposalSelectionService,
    )

    rfp = ProposalSelectionService.load_rfp(rfp_path)
    proposals = ProposalSelectionService.load_proposals(proposals_inbox)

    print(f"\nLoaded RFP: {rfp.implementation_dossier_id}")
    print(f"  Mandate: {rfp.mandate_id}")
    print(f"  Status: {rfp.status.value}")
    print(f"\nLoaded {len(proposals)} proposals from inbox")
    for p in proposals:
        print(
            f"  - {p.duke_name} ({p.duke_abbreviation}): "
            f"status={p.status.value}, tactics={p.tactic_count}"
        )

    # ------------------------------------------------------------------
    # Load Presidents
    # ------------------------------------------------------------------
    presidents = _load_presidents()
    print(f"\nPresidents to evaluate: {len(presidents)}")
    for pres in presidents:
        print(f"  - {pres.get('name')}: {pres.get('role')}")

    # ------------------------------------------------------------------
    # Setup events
    # ------------------------------------------------------------------
    events: list[dict] = []

    def event_sink(event_type: str, payload: dict) -> None:
        events.append({"type": event_type, "payload": payload})

    # ------------------------------------------------------------------
    # Build selection context
    # ------------------------------------------------------------------
    from src.application.ports.proposal_selection import SelectionContext

    context = SelectionContext(
        cycle_id=rfp.implementation_dossier_id,
        motion_id=rfp.motion_id if hasattr(rfp, "motion_id") else "",
        rfp_id=rfp.implementation_dossier_id,
        mandate_id=rfp.mandate_id,
        motion_title=rfp.motion_title,
        evaluation_criteria=[],
        iteration_number=1,
        max_iterations=args.max_rounds,
        finalist_count=args.top_n,
    )

    # ------------------------------------------------------------------
    # Read secretary archon IDs (same pattern as run_conclave.py)
    # ------------------------------------------------------------------
    secretary_text_archon_id = os.getenv("SECRETARY_TEXT_ARCHON_ID", "").strip() or None
    secretary_json_archon_id = os.getenv("SECRETARY_JSON_ARCHON_ID", "").strip() or None

    if secretary_text_archon_id:
        print(f"\nSecretary Text Archon: {secretary_text_archon_id}")
    else:
        print(
            "\nWarning: SECRETARY_TEXT_ARCHON_ID not set, utility agents use fallback LLM"
        )
    if secretary_json_archon_id:
        print(f"Secretary JSON Archon: {secretary_json_archon_id}")
    else:
        print("Warning: SECRETARY_JSON_ARCHON_ID not set, JSON repair disabled")

    scorer = None
    use_llm = args.mode == "llm"

    if use_llm:
        try:
            from src.infrastructure.adapters.config.archon_profile_adapter import (
                create_archon_profile_repository,
            )
            from src.infrastructure.adapters.external.proposal_scorer_crewai_adapter import (
                create_proposal_scorer,
            )

            profile_repo = create_archon_profile_repository()
            scorer = create_proposal_scorer(
                profile_repository=profile_repo,
                verbose=args.verbose,
                model=args.model,
                provider=args.provider,
                base_url=args.base_url,
                secretary_text_archon_id=secretary_text_archon_id,
                secretary_json_archon_id=secretary_json_archon_id,
            )
            print(
                f"\nLoaded {profile_repo.count()} Archon profiles"
                " for per-President LLM bindings"
            )
        except ImportError as e:
            print(f"\nWarning: Could not load LLM adapter: {e}")
            print("Falling back to simulation mode")
            use_llm = False

    service = ProposalSelectionService(
        proposal_scorer=scorer,
        event_sink=event_sink,
        verbose=args.verbose,
        top_n_finalists=args.top_n,
        max_rounds=args.max_rounds,
    )

    if use_llm and scorer is not None:
        print("\nRunning selection pipeline via LLM...")
        try:
            result = asyncio.run(
                service.run_selection_pipeline(
                    proposals=proposals,
                    rfp=rfp,
                    presidents=presidents,
                    context=context,
                    score_only=args.score_only,
                )
            )
        except Exception as e:
            print(f"\nLLM pipeline error: {e}")
            print("Falling back to simulation mode...")
            result = service.simulate_selection(
                proposals=proposals,
                rfp=rfp,
                presidents=presidents,
                context=context,
                score_only=args.score_only,
            )
    else:
        print("\nRunning selection pipeline (simulation mode)...")
        result = service.simulate_selection(
            proposals=proposals,
            rfp=rfp,
            presidents=presidents,
            context=context,
            score_only=args.score_only,
        )

    # ------------------------------------------------------------------
    # Save results
    # ------------------------------------------------------------------
    sel_dir = service.save_results(result, proposals, output_dir)

    # Save events
    _save_jsonl(sel_dir / "selection_events.jsonl", events)

    # ------------------------------------------------------------------
    # Print summary
    # ------------------------------------------------------------------
    print("\n" + "=" * 60)
    print("PROPOSAL SELECTION PIPELINE COMPLETE")
    print("=" * 60)
    print(f"Selection ID: {result.selection_id}")
    print(f"RFP: {result.rfp_id}")
    print(f"Mandate: {result.mandate_id}")
    print(f"Status: {result.status.value}")
    print(f"Outcome: {result.outcome.value if result.outcome else 'N/A'}")
    print(f"Winner: {result.winning_proposal_id or 'None'}")
    print(f"Iteration: {result.iteration_number}/{result.max_iterations}")
    print(f"Total scores: {len(result.president_scores)}")
    print(f"Total rankings: {len(result.rankings)}")
    print(f"Mode: {args.mode}")
    print(f"Output saved to: {sel_dir}")

    if result.rankings:
        print("\nTop rankings:")
        # Map proposal IDs to duke names
        proposal_lookup = {p.proposal_id: p for p in proposals}
        for r in result.rankings[:10]:
            prop = proposal_lookup.get(r.proposal_id)
            duke_name = prop.duke_name if prop else "Unknown"
            winner_marker = (
                " <-- WINNER" if r.proposal_id == result.winning_proposal_id else ""
            )
            print(
                f"  #{r.rank}: {duke_name} ({r.proposal_id}) "
                f"mean={r.mean_score:.1f} tier={r.tier.value} "
                f"novelty_bonus={r.novelty_bonus:.2f}{winner_marker}"
            )

    if result.revision_guidance:
        print(
            f"\nRevision guidance issued for {len(result.revision_guidance)} proposals"
        )

    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
