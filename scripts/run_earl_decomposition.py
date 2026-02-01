#!/usr/bin/env python3
"""Run the Earl Decomposition Bridge.

After run_proposal_selection.py declares WINNER_SELECTED, this script reads
the winning Duke proposal, decomposes its tactics into activation-ready task
drafts, matches them to eligible Aegis Clusters, and optionally calls the
governance activation API to place tasks into the task lifecycle.

Pipeline Position:
    Executive (RFP) -> Administrative (Duke Proposals) -> Executive (Selection)
                                                            |
                                                            v
                                            Earl Decomposition Bridge    <- THIS
                                                            |
                                                            v
                                            Governance (TaskActivation)

Usage:
    python scripts/run_earl_decomposition.py                        # auto-detect
    python scripts/run_earl_decomposition.py --mode simulation -v   # no LLM
    python scripts/run_earl_decomposition.py --tactic-id T-AGAR-003 # single tactic
    python scripts/run_earl_decomposition.py --no-activate          # drafts only
    python scripts/run_earl_decomposition.py --dry-run              # no writes
"""

from __future__ import annotations

import argparse
import asyncio
import glob
import shutil
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()


# ------------------------------------------------------------------
# Auto-detect helpers
# ------------------------------------------------------------------


def _find_latest_rfp_session() -> Path | None:
    """Find the most recent RFP session directory."""
    pattern = "_bmad-output/rfp/*"
    dirs = [d for d in glob.glob(pattern) if Path(d).is_dir()]
    if not dirs:
        return None
    return Path(max(dirs, key=lambda d: Path(d).stat().st_mtime))


def _find_mandate_dir(session_dir: Path, mandate_id: str | None = None) -> Path | None:
    """Find a mandate directory within an RFP session."""
    mandates_dir = session_dir / "mandates"
    if not mandates_dir.exists():
        return session_dir if (session_dir / "rfp.json").exists() else None

    if mandate_id:
        candidate = mandates_dir / mandate_id
        if candidate.exists():
            return candidate
        return None

    # Pick first mandate directory
    mandate_dirs = sorted(
        [d for d in mandates_dir.iterdir() if d.is_dir()],
        key=lambda d: d.stat().st_mtime,
        reverse=True,
    )
    return mandate_dirs[0] if mandate_dirs else None


def _find_selection_result(mandate_dir: Path) -> Path | None:
    """Find selection_result.json under a mandate directory."""
    candidate = mandate_dir / "selection" / "selection_result.json"
    return candidate if candidate.exists() else None


def _find_winning_proposal(
    mandate_dir: Path, winning_duke_name: str
) -> tuple[Path | None, Path | None]:
    """Find proposal .md and .json for the winning Duke.

    Tries exact match first, then prefix match (abbreviation -> full name).
    E.g. "ZEPA" matches "proposal_zepar.md".
    """
    inbox = mandate_dir / "proposals_inbox"
    duke_lower = winning_duke_name.lower()

    # Exact match
    md_path = inbox / f"proposal_{duke_lower}.md"
    json_path = inbox / f"proposal_{duke_lower}.json"
    if md_path.exists():
        return md_path, json_path if json_path.exists() else None

    # Prefix match: abbreviation is 4-char truncation of duke name
    matches = sorted(inbox.glob(f"proposal_{duke_lower}*.md"))
    if matches:
        md_path = matches[0]
        json_path = md_path.with_suffix(".json")
        return md_path, json_path if json_path.exists() else None

    return None, None


def _resolve_winning_duke(selection: dict) -> tuple[str, str, str]:
    """Extract winner info from selection result.

    Returns (proposal_id, duke_name, duke_abbreviation).
    """
    # Try direct fields
    proposal_id = selection.get("winning_proposal_id", "")
    if not proposal_id:
        return ("", "", "")

    # Find duke name from rankings
    duke_name = ""
    duke_abbrev = ""
    for ranking in selection.get("rankings", []):
        if ranking.get("proposal_id") == proposal_id:
            duke_name = ranking.get("duke_name", "")
            duke_abbrev = ranking.get("duke_abbreviation", "")
            break

    # Fallback: try to extract from proposal_id (dprop-agar-xxx -> Agares)
    if not duke_name and "-" in proposal_id:
        parts = proposal_id.split("-")
        if len(parts) >= 2:
            duke_abbrev = parts[1].upper()

    return proposal_id, duke_name, duke_abbrev


# ------------------------------------------------------------------
# CLI
# ------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Earl Decomposition Bridge: decompose winning tactics into task activations",
    )

    # Input sources
    parser.add_argument(
        "--selection-file",
        type=Path,
        help="Path to selection_result.json",
    )
    parser.add_argument(
        "--from-selection-dir",
        type=Path,
        help="Directory containing selection_result.json",
    )
    parser.add_argument(
        "--rfp-file",
        type=Path,
        help="Explicit rfp.json path (auto-detect if omitted)",
    )
    parser.add_argument(
        "--proposal-md",
        type=Path,
        help="Explicit winning proposal markdown path",
    )

    # Cluster + routing config
    parser.add_argument(
        "--cluster-dir",
        type=Path,
        default=Path("docs/governance/examples"),
        help="Directory of cluster definition JSON files",
    )
    parser.add_argument(
        "--earl-routing-table",
        type=Path,
        default=Path("configs/admin/earl_routing_table.json"),
        help="Path to earl_routing_table.json",
    )

    # Mode
    parser.add_argument(
        "--mode",
        choices=["llm", "simulation", "auto"],
        default="auto",
        help="Decomposition mode (default: auto)",
    )

    # Filtering
    parser.add_argument(
        "--tactic-id",
        type=str,
        help="Decompose only a single tactic ID",
    )

    # Tuning
    parser.add_argument(
        "--max-tasks-per-tactic",
        type=int,
        default=8,
        help="Max tasks per tactic before explosion flag (default: 8)",
    )
    parser.add_argument(
        "--ttl-hours",
        type=int,
        default=72,
        help="TTL in hours for task activations (default: 72)",
    )
    parser.add_argument(
        "--route-top-k",
        type=int,
        default=1,
        help="Route to top K eligible clusters per task (default: 1)",
    )

    # Activation control
    parser.add_argument(
        "--no-activate",
        action="store_true",
        help="Generate drafts + routing plan but do not call create_activation()",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Do everything except writing outputs and calling activation",
    )

    # Checkpointing
    parser.add_argument(
        "--checkpoint-dir",
        type=Path,
        help="Override checkpoint directory",
    )
    parser.add_argument(
        "--no-checkpoint",
        action="store_true",
        help="Disable checkpointing",
    )
    parser.add_argument(
        "--clear-checkpoints",
        action="store_true",
        help="Delete checkpoint directory before run",
    )

    # Verbose
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )

    return parser


# ------------------------------------------------------------------
# Input resolution
# ------------------------------------------------------------------


def _resolve_paths(
    args: argparse.Namespace,
) -> tuple[Path | None, Path | None, Path | None, Path | None] | int:
    """Resolve mandate_dir, selection_path, rfp_path, proposal_md_path.

    Returns the 4-tuple on success, or an int exit code on failure.
    """
    mandate_dir: Path | None = None
    selection_path: Path | None = args.selection_file
    rfp_path: Path | None = args.rfp_file
    proposal_md_path: Path | None = args.proposal_md

    if args.from_selection_dir:
        selection_path = args.from_selection_dir / "selection_result.json"
        mandate_dir = args.from_selection_dir.parent
    elif selection_path:
        mandate_dir = selection_path.parent.parent
    else:
        session_dir = _find_latest_rfp_session()
        if session_dir is None:
            print(
                "ERROR: No RFP session found. Use --selection-file or --from-selection-dir."
            )
            return 1
        mandate_dir = _find_mandate_dir(session_dir)
        if mandate_dir is None:
            print(f"ERROR: No mandate directory found in {session_dir}")
            return 1
        selection_path = _find_selection_result(mandate_dir)
        if selection_path is None:
            print(f"ERROR: No selection_result.json found in {mandate_dir}/selection/")
            return 1

    if not selection_path or not selection_path.exists():
        print(f"ERROR: Selection result not found: {selection_path}")
        return 1

    if rfp_path is None:
        rfp_path = mandate_dir / "rfp.json" if mandate_dir else None
    if not rfp_path or not rfp_path.exists():
        print(f"ERROR: rfp.json not found: {rfp_path}")
        return 1

    return mandate_dir, selection_path, rfp_path, proposal_md_path


# ------------------------------------------------------------------
# Load and validate selection + proposal + tactics
# ------------------------------------------------------------------


def _load_and_validate(
    args: argparse.Namespace,
    mandate_dir: Path | None,
    selection_path: Path,
    rfp_path: Path,
    proposal_md_path: Path | None,
) -> tuple[str, str, dict, list, dict, Path] | int:
    """Load selection result, validate winner, find proposal, parse tactics.

    Returns (proposal_id, duke_name, earl_routing, tactics, rfp, selection_path)
    on success, or an int exit code on failure.
    """
    from src.application.services.earl_decomposition_service import (
        EarlDecompositionService,
    )

    selection = EarlDecompositionService.load_selection_result(selection_path)
    outcome = selection.get("outcome", "")

    if outcome != "WINNER_SELECTED":
        print(
            f"ERROR: Selection outcome is '{outcome}', not WINNER_SELECTED. Cannot proceed."
        )
        return 1

    proposal_id, duke_name, duke_abbrev = _resolve_winning_duke(selection)
    if not proposal_id:
        print("ERROR: Could not determine winning proposal from selection result.")
        return 1

    if args.verbose:
        print(f"Winner: {duke_name or duke_abbrev} ({proposal_id})")

    if proposal_md_path is None and mandate_dir:
        proposal_md_path, _ = _find_winning_proposal(
            mandate_dir, duke_name or duke_abbrev
        )
    if not proposal_md_path or not proposal_md_path.exists():
        print(f"ERROR: Winning proposal markdown not found: {proposal_md_path}")
        return 1

    rfp = EarlDecompositionService.load_rfp(rfp_path)
    proposal_md = EarlDecompositionService.load_proposal_markdown(proposal_md_path)

    earl_routing: dict = {}
    if args.earl_routing_table.exists():
        earl_routing = EarlDecompositionService.load_earl_routing_table(
            args.earl_routing_table
        )

    tactics = EarlDecompositionService.parse_tactics_from_markdown(proposal_md)
    if not tactics:
        print("ERROR: No tactics found in winning proposal.")
        return 1

    if args.verbose:
        print(f"Found {len(tactics)} tactics in proposal")

    return (proposal_id, duke_name, earl_routing, tactics, rfp, selection_path)


# ------------------------------------------------------------------
# Decomposer setup
# ------------------------------------------------------------------


def _setup_decomposer(
    args: argparse.Namespace,
    earl_routing: dict,
    checkpoint_dir: Path | None,
) -> object | int:
    """Create the decomposer adapter. Returns adapter or int exit code."""
    from src.infrastructure.adapters.external.tactic_decomposer_simulation_adapter import (
        TacticDecomposerSimulationAdapter,
    )

    decomposer = None
    use_llm = args.mode in ("llm", "auto")

    if use_llm:
        try:
            from src.infrastructure.adapters.config.archon_profile_adapter import (
                create_archon_profile_repository,
            )
            from src.infrastructure.adapters.external.tactic_decomposer_crewai_adapter import (
                create_tactic_decomposer,
            )

            profile_repo = create_archon_profile_repository()
            decomposer = create_tactic_decomposer(
                profile_repository=profile_repo,
                earl_routing_table=earl_routing,
                verbose=args.verbose,
                checkpoint_dir=checkpoint_dir,
            )
            if args.verbose:
                print("Mode: LLM (CrewAI multi-Earl)")
        except ImportError as e:
            if args.verbose:
                print(f"Warning: Could not load LLM adapter: {e}")
            if args.mode == "llm":
                print(f"ERROR: LLM mode requested but adapter unavailable: {e}")
                return 1
            if args.verbose:
                print("Falling back to simulation mode")
        except Exception as e:
            if args.verbose:
                print(f"Warning: Could not initialize LLM adapter: {e}")
            if args.mode == "llm":
                print(f"ERROR: LLM mode failed to initialize: {e}")
                return 1
            if args.verbose:
                print("Falling back to simulation mode")

    if decomposer is None:
        decomposer = TacticDecomposerSimulationAdapter()
        if args.verbose:
            print("Mode: simulation")

    return decomposer


# ------------------------------------------------------------------
# Activation wiring
# ------------------------------------------------------------------


async def _run_activation(service: object, args: argparse.Namespace) -> None:
    """Wire up TaskActivationService and call activate_all."""
    try:
        from src.application.services.governance.task_activation_service import (
            TaskActivationService,
        )
        from src.application.services.governance.two_phase_event_emitter import (
            TwoPhaseEventEmitter,
        )
        from src.infrastructure.adapters.governance.in_memory_adapters import (
            InMemoryGovernanceLedger,
            InMemoryParticipantMessagePort,
            InMemoryTaskStatePort,
            PassthroughCoercionFilter,
            SimpleTimeAuthority,
        )

        ledger = InMemoryGovernanceLedger()
        task_state_port = InMemoryTaskStatePort()
        activation_svc = TaskActivationService(
            task_state_port=task_state_port,
            coercion_filter=PassthroughCoercionFilter(),
            participant_message_port=InMemoryParticipantMessagePort(),
            ledger_port=ledger,
            two_phase_emitter=TwoPhaseEventEmitter(
                ledger=ledger,
                time_authority=SimpleTimeAuthority(),
            ),
        )
        await service.activate_all(task_activation_service=activation_svc)
    except Exception as e:
        if args.verbose:
            print(f"  [bridge] activation wiring failed: {e}")
        await service.activate_all(task_activation_service=None)


# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------


async def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    # --- Resolve inputs ---
    resolved = _resolve_paths(args)
    if isinstance(resolved, int):
        return resolved
    mandate_dir, selection_path, rfp_path, proposal_md_path = resolved

    loaded = _load_and_validate(
        args, mandate_dir, selection_path, rfp_path, proposal_md_path
    )
    if isinstance(loaded, int):
        return loaded
    (proposal_id, duke_name, earl_routing, tactics, rfp, selection_path) = loaded

    from src.application.services.earl_decomposition_service import (
        EarlDecompositionService,
    )

    # --- Checkpointing ---
    checkpoint_dir: Path | None = None
    if not args.no_checkpoint:
        checkpoint_dir = args.checkpoint_dir or (
            mandate_dir / "execution_bridge" / "checkpoints" if mandate_dir else None
        )
        if args.clear_checkpoints and checkpoint_dir and checkpoint_dir.exists():
            shutil.rmtree(checkpoint_dir)
            if args.verbose:
                print(f"Cleared checkpoints: {checkpoint_dir}")

    # --- Set up decomposer ---
    decomposer = _setup_decomposer(args, earl_routing, checkpoint_dir)
    if isinstance(decomposer, int):
        return decomposer

    # --- Set up cluster registry ---
    from src.infrastructure.adapters.cluster.cluster_registry_json_adapter import (
        ClusterRegistryJsonAdapter,
    )

    cluster_registry = ClusterRegistryJsonAdapter(
        cluster_dir=args.cluster_dir,
        verbose=args.verbose,
    )

    # --- Create service ---
    service = EarlDecompositionService(
        decomposer=decomposer,
        cluster_registry=cluster_registry,
        earl_routing_table=earl_routing,
        max_tasks_per_tactic=args.max_tasks_per_tactic,
        ttl_hours=args.ttl_hours,
        route_top_k=args.route_top_k,
        checkpoint_dir=checkpoint_dir,
        verbose=args.verbose,
    )

    # --- Run pipeline ---
    service._emit("bridge.started", {
        "selection_file": str(selection_path),
        "proposal_id": proposal_id,
        "duke_name": duke_name,
    })
    service._emit("bridge.loaded_selection", {
        "outcome": "WINNER_SELECTED",
        "winning_proposal_id": proposal_id,
    })
    service._emit("bridge.loaded_proposal", {"tactic_count": len(tactics)})
    service._summary.winning_duke_name = duke_name

    task_drafts = await service.decompose_all(
        tactics=tactics,
        rfp=rfp,
        proposal_id=proposal_id,
        tactic_filter=args.tactic_id,
    )

    if args.verbose:
        print(f"Produced {len(task_drafts)} task drafts")

    await service.route_all()

    if not args.no_activate and not args.dry_run:
        await _run_activation(service, args)

    service._emit("bridge.complete", {"total_drafts": len(task_drafts)})

    if not args.dry_run and mandate_dir:
        service.save_outputs(mandate_dir)

    service.print_summary()

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
