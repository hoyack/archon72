#!/usr/bin/env python3
"""Run the Executive planning pipeline on ratified intent packets.

This stage forks after ratification:
Review Pipeline -> Ratified Intent Packets -> Executive Mini-Conclave

v2: Updated to support --mode {manual,llm,auto} for President deliberation.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys
import warnings
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

from src.application.services.executive_planning_service import (  # noqa: E402
    ExecutivePlanningService,
    now_iso,
)
from src.domain.models.executive_planning import SCHEMA_VERSION  # noqa: E402
from src.domain.models.llm_config import LLMConfig  # noqa: E402


def find_latest_review_pipeline_output() -> Path | None:
    pattern = "_bmad-output/review-pipeline/*"
    dirs = [d for d in glob.glob(pattern) if Path(d).is_dir()]
    if not dirs:
        return None
    return Path(max(dirs, key=lambda d: Path(d).stat().st_mtime))


def resolve_role_llm_config(env_var: str) -> LLMConfig | None:
    """Resolve LLM config from Archon ID environment variable.

    Args:
        env_var: Environment variable name containing the Archon UUID

    Returns:
        LLMConfig from the Archon profile, or None if not configured
    """
    archon_id_value = os.environ.get(env_var)
    if not archon_id_value:
        return None

    try:
        archon_id = UUID(archon_id_value)
    except ValueError:
        print(f"Warning: {env_var} is not a valid UUID: {archon_id_value}")
        return None

    from src.infrastructure.adapters.config.archon_profile_adapter import (  # noqa: E402
        create_archon_profile_repository,
    )

    repo = create_archon_profile_repository()
    profile = repo.get_by_id(archon_id)
    if not profile:
        print(f"Warning: {env_var} Archon not found: {archon_id_value}")
        return None

    print(f"Using {env_var}={archon_id_value} ({profile.name})")
    return profile.llm_config


def resolve_president_deliberator_config() -> LLMConfig | None:
    """Resolve President deliberator LLM config from environment.

    Priority:
    1. PRESIDENT_DELIBERATOR_MODEL + optional PRESIDENT_DELIBERATOR_TEMPERATURE
    2. PRESIDENT_DELIBERATOR_ARCHON_ID (legacy)

    Returns:
        LLMConfig for President deliberation, or None if not configured
    """
    # v2: Direct model/temperature specification takes priority
    model = os.environ.get("PRESIDENT_DELIBERATOR_MODEL")
    if model:
        temperature = float(os.environ.get("PRESIDENT_DELIBERATOR_TEMPERATURE", "0.3"))
        # Determine provider from model string
        if model.startswith("ollama/"):
            provider = "ollama"
            model_name = model[7:]  # Remove "ollama/" prefix
        elif model.startswith("openai/"):
            provider = "openai"
            model_name = model[7:]  # Remove "openai/" prefix
        elif model.startswith("anthropic/"):
            provider = "anthropic"
            model_name = model[10:]  # Remove "anthropic/" prefix
        else:
            # Default to ollama for unqualified model names
            provider = "ollama"
            model_name = model

        print(f"Using PRESIDENT_DELIBERATOR_MODEL={model} (temperature={temperature})")
        return LLMConfig(
            provider=provider,
            model=model_name,
            temperature=temperature,
            max_tokens=4096,
            timeout_ms=60000,
        )

    # Legacy: Archon ID-based configuration
    return resolve_role_llm_config("PRESIDENT_DELIBERATOR_ARCHON_ID")


def check_manual_artifacts_exist(inbox_dir: Path) -> bool:
    """Check if manual artifacts exist in the inbox directory.

    Args:
        inbox_dir: Path to the inbox directory

    Returns:
        True if any contribution or attestation files exist
    """
    if not inbox_dir.exists():
        return False

    # Look for contribution_*.json or attestation_*.json files
    contributions = list(inbox_dir.glob("contribution_*.json"))
    attestations = list(inbox_dir.glob("attestation_*.json"))
    return len(contributions) > 0 or len(attestations) > 0


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


def _parse_list_arg(value: str | None) -> list[str] | None:
    if not value:
        return None
    items = [v.strip() for v in value.split(",") if v.strip()]
    return items or None


def _resolve_assignment(
    service: ExecutivePlanningService,
    packet,
    affected_override: list[str] | None,
    owner_override: str | None,
    deadline: str,
    args,
    motion_dir: Path,
) -> dict:
    if affected_override and owner_override:
        affected_ids = list(affected_override)
        owner_id = owner_override
    else:
        affected_ids, owner_id = service.infer_assignment(packet)

    if owner_id not in affected_ids:
        affected_ids = [owner_id, *affected_ids]

    existing_assignment_path = motion_dir / "executive_assignment_record.json"
    if args.continue_cycle and existing_assignment_path.exists():
        with open(existing_assignment_path, encoding="utf-8") as f:
            assignment = json.load(f)
        print(f"  Continuing cycle: {assignment['cycle_id']}")
        return assignment

    return service.run_assignment_session(
        packet=packet,
        affected_portfolio_ids=affected_ids,
        plan_owner_portfolio_id=owner_id,
        response_deadline_iso=deadline,
    )


def _resolve_draft_plan(
    service: ExecutivePlanningService,
    args,
    packet,
    review_pipeline_path: Path,
):
    if not args.draft_from_template:
        return None
    return service.generate_template_draft(packet, review_pipeline_path)


def _determine_effective_mode(args, inbox_dir: Path, president_deliberator) -> str:
    effective_mode = args.mode
    if effective_mode != "auto":
        return effective_mode

    if check_manual_artifacts_exist(inbox_dir):
        effective_mode = "manual"
        print(f"  Auto mode: Found manual artifacts in {inbox_dir}")
    elif president_deliberator:
        effective_mode = "llm"
        print("  Auto mode: No manual artifacts found, using LLM deliberation")
    else:
        effective_mode = "none"
        print(
            "  Auto mode: No manual artifacts and no LLM configured, skipping deliberation"
        )
    return effective_mode


def _run_llm_deliberation(
    service: ExecutivePlanningService,
    inbox_dir: Path,
    packet,
    assignment: dict,
):
    import asyncio

    print("  Running LLM-powered President deliberation...")
    contributions, attestations, fallback_count = asyncio.run(
        service.run_llm_deliberation(packet, assignment)
    )
    print(
        f"  LLM deliberation: {len(contributions)} contributions, {len(attestations)} attestations"
    )
    inbox_dir.mkdir(parents=True, exist_ok=True)
    for contrib in contributions:
        contrib_path = inbox_dir / f"contribution_{contrib.portfolio.portfolio_id}.json"
        with open(contrib_path, "w", encoding="utf-8") as f:
            json.dump(contrib.to_dict(), f, indent=2)
    for attest in attestations:
        attest_path = inbox_dir / f"attestation_{attest.portfolio.portfolio_id}.json"
        with open(attest_path, "w", encoding="utf-8") as f:
            json.dump(attest.to_dict(), f, indent=2)
    return contributions, attestations, fallback_count


def _load_manual_responses(
    service: ExecutivePlanningService,
    inbox_dir: Path,
    assignment: dict,
    packet,
):
    contributions = service.load_contributions_from_inbox(
        inbox_dir,
        assignment["cycle_id"],
        packet.motion_id,
        assignment_record=assignment,
    )
    attestations = service.load_attestations_from_inbox(
        inbox_dir,
        assignment["cycle_id"],
        packet.motion_id,
        assignment_record=assignment,
    )
    print(
        f"  Loaded {len(contributions)} contributions, {len(attestations)} attestations from inbox"
    )
    return contributions, attestations


def _run_blocker_workup(
    service: ExecutivePlanningService,
    packet,
    assignment: dict,
    contributions: list,
    blocker_workup,
    motion_dir: Path,
):
    import asyncio

    all_blockers = [
        blocker
        for contrib in contributions
        for blocker in getattr(contrib, "blockers", [])
    ]
    has_v2_blockers = any(
        getattr(blocker, "schema_version", None) == SCHEMA_VERSION
        or hasattr(blocker, "blocker_class")
        for blocker in all_blockers
    )

    if has_v2_blockers:
        print(f"  Running E2.5 blocker workup on {len(all_blockers)} blockers...")
        result = asyncio.run(
            service.run_blocker_workup(packet, assignment, contributions)
        )
        _save_json(
            motion_dir / "blocker_workup_result.json",
            result.to_dict(),
        )
        _save_json(
            motion_dir / "peer_review_summary.json",
            result.peer_review_summary.to_dict(),
        )
        _save_json(
            motion_dir / "conclave_queue_items.json",
            [i.to_dict() for i in result.conclave_queue_items],
        )
        _save_json(
            motion_dir / "discovery_task_stubs.json",
            [s.to_dict() for s in result.discovery_task_stubs],
        )
        return result

    if all_blockers:
        print("  Blockers detected but none are v2; skipping E2.5 blocker workup")
    return None


def _build_handoff(
    packet,
    result,
    motion_dir: Path,
    blocker_workup_result,
) -> dict:
    handoff = {
        "schema_version": result.schema_version,
        "cycle_id": result.cycle_id,
        "motion_id": packet.motion_id,
        "motion_title": packet.ratified_motion.get("title", ""),
        "motion_text": packet.ratified_motion.get("ratified_text", ""),
        "execution_plan_path": str((motion_dir / "execution_plan.json").resolve()),
        "constraints_spotlight": packet.ratified_motion.get("constraints", []),
        "blockers_requiring_escalation": [
            b.to_dict() for b in result.blockers_requiring_escalation
        ],
        "conclave_queue_items": [i.to_dict() for i in result.conclave_queue_items],
        "discovery_task_stubs": [s.to_dict() for s in result.discovery_task_stubs],
        "gates": result.gates.to_dict(),
        "created_at": now_iso(),
    }
    if blocker_workup_result is not None:
        handoff["peer_review_summary"] = (
            blocker_workup_result.peer_review_summary.to_dict()
        )
    return handoff


def _handle_deprecated_flags(args) -> None:
    if args.scaffold_inbox:
        warnings.warn(
            "--scaffold-inbox is deprecated. It is kept for debugging purposes only.",
            DeprecationWarning,
            stacklevel=2,
        )
        print("Warning: --scaffold-inbox is deprecated and kept for debugging only.")

    if args.load_inbox:
        warnings.warn(
            "--load-inbox is deprecated. Use --mode=manual instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        print("Warning: --load-inbox is deprecated. Use --mode=manual instead.")
        if args.mode == "auto":
            args.mode = "manual"

    if args.llm_deliberation:
        warnings.warn(
            "--llm-deliberation is deprecated. Use --mode=llm instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        print("Warning: --llm-deliberation is deprecated. Use --mode=llm instead.")
        if args.mode == "auto":
            args.mode = "llm"


def _resolve_review_pipeline_path(args) -> Path:
    if args.review_pipeline_path is None:
        args.review_pipeline_path = find_latest_review_pipeline_output()
        if args.review_pipeline_path is None:
            print("Error: No review pipeline output found. Run review pipeline first.")
            print("Looking for: _bmad-output/review-pipeline/*/")
            sys.exit(1)
        print(f"Auto-detected review pipeline output: {args.review_pipeline_path}")

    review_pipeline_path = args.review_pipeline_path
    if not review_pipeline_path.exists():
        print(f"Error: Review pipeline output not found: {review_pipeline_path}")
        sys.exit(1)

    ratification_file = review_pipeline_path / "ratification_results.json"
    if not ratification_file.exists():
        print(f"Error: No ratification_results.json found in: {review_pipeline_path}")
        sys.exit(1)

    return review_pipeline_path


def _resolve_mandates_path(path: Path) -> Path:
    if path.is_file():
        return path
    if path.is_dir():
        candidate = path / "ratified_mandates.json"
        if candidate.exists():
            return candidate
        matches = list(path.glob("ratified_mandates.json"))
        if matches:
            return matches[0]
    raise ValueError(f"ratified_mandates.json not found in {path}")


def _load_mandate_session_id(path: Path) -> str:
    data = json.loads(path.read_text(encoding="utf-8"))
    return (
        data.get("conclave_session_id") or data.get("session_id") or "unknown-session"
    )


def _init_planner_agent(args):
    if not args.real_agent:
        return None

    from src.infrastructure.adapters.external import create_planner_agent  # noqa: E402,I001

    print("Initializing LLM-powered planner agent for drafts...")
    llm_config = resolve_role_llm_config("EXECUTION_PLANNER_ARCHON_ID")
    return create_planner_agent(verbose=args.verbose, llm_config=llm_config)


def _init_president_deliberator(args):
    if args.mode not in ("llm", "auto"):
        return None

    from src.infrastructure.adapters.config.archon_profile_adapter import (  # noqa: E402,I001
        create_archon_profile_repository,
    )
    from src.infrastructure.adapters.external import create_president_deliberator  # noqa: E402,I001

    print("Initializing LLM-powered President deliberator with per-Archon bindings...")
    profile_repo = create_archon_profile_repository()
    llm_config = resolve_president_deliberator_config()
    deliberator = create_president_deliberator(
        profile_repository=profile_repo,
        verbose=args.verbose,
        llm_config=llm_config,
    )
    print(
        f"  Loaded {profile_repo.count()} Archon profiles for per-President LLM bindings"
    )
    return deliberator


def _init_blocker_workup(args):
    if not args.llm_blocker_workup:
        return None

    from src.infrastructure.adapters.external.blocker_workup_crewai_adapter import (  # noqa: E402,I001
        create_blocker_workup,
    )

    print("Initializing LLM-powered blocker workup...")
    llm_config = resolve_president_deliberator_config()
    return create_blocker_workup(verbose=args.verbose, llm_config=llm_config)


def _load_packets(base_service, review_pipeline_path: Path, args) -> list:
    packets = base_service.build_ratified_intent_packets(
        review_pipeline_path=review_pipeline_path,
        include_deferred=args.include_deferred,
    )
    if args.motion_id:
        packets = [p for p in packets if p.motion_id == args.motion_id]
    if not packets:
        print("No ratified intent packets found for the given inputs.")
        sys.exit(1)
    return packets


def _prepare_session_dir(review_pipeline_path: Path, outdir: Path, packets: list):
    pipeline_result = json.loads(
        (review_pipeline_path / "pipeline_result.json").read_text(encoding="utf-8")
    )
    session_id = pipeline_result.get("session_id", "unknown-session")
    session_dir = outdir / session_id
    session_dir.mkdir(parents=True, exist_ok=True)

    _save_json(
        session_dir / "ratified-intent-packets.json", [p.to_dict() for p in packets]
    )
    return session_id, session_dir


def _print_pipeline_summary(
    session_id: str,
    packets: list,
    args,
    cycle_summaries: list[dict],
    session_dir: Path,
    failures: int,
) -> None:
    print("\n" + "=" * 60)
    print("EXECUTIVE PIPELINE COMPLETE")
    print("=" * 60)
    print(f"Session: {session_id}")
    print(f"Ratified motions processed: {len(packets)}")
    print(f"Deliberation mode: {args.mode}")
    print(f"Gate failures: {failures}")
    if args.scaffold_inbox:
        print("Inbox scaffolds created - Presidents can now fill in responses")
    if args.mode in ("manual", "llm", "auto"):
        total_contributions = sum(
            s.get("contributions_count", 0) for s in cycle_summaries
        )
        total_attestations = sum(
            s.get("attestations_count", 0) for s in cycle_summaries
        )
        total_fallbacks = sum(
            s.get("fallback_attestations_count", 0) for s in cycle_summaries
        )
        print(f"Total contributions: {total_contributions}")
        print(f"Total attestations: {total_attestations}")
        print(f"Fallback attestations: {total_fallbacks}")
    if args.llm_blocker_workup:
        print("Blocker workup: enabled")
    print(f"Output saved to: {session_dir}")
    print("=" * 60 + "\n")


def _enforce_gate_requirements(
    args, failures: int, cycle_summaries: list[dict]
) -> None:
    fallback_total = sum(
        s.get("fallback_attestations_count", 0) for s in cycle_summaries
    )
    if args.require_gates and (failures > 0 or fallback_total > 0):
        print(
            f"ERROR: {failures} motion(s) failed gate checks. "
            f"Fallback attestations: {fallback_total}. Handoff blocked."
        )
        print(
            "Fix missing responses, blockers, or fallback attestations "
            "before proceeding to Administration."
        )
        sys.exit(1)


def _process_motion(
    packet,
    session_dir: Path,
    review_pipeline_path: Path,
    args,
    planner_agent,
    president_deliberator,
    blocker_workup,
    affected_override: list[str] | None,
    owner_override: str | None,
    deadline: str,
) -> dict:
    """Process a single motion through the Executive pipeline."""
    events: list[dict] = []
    service = ExecutivePlanningService(
        event_sink=lambda event_type, payload, events=events: events.append(
            {"type": event_type, "payload": payload}
        ),
        planner_agent=planner_agent,
        president_deliberator=president_deliberator,
        blocker_workup=blocker_workup,
        verbose=args.verbose,
    )
    motion_dir = session_dir / "motions" / packet.motion_id
    assignment = _resolve_assignment(
        service=service,
        packet=packet,
        affected_override=affected_override,
        owner_override=owner_override,
        deadline=deadline,
        args=args,
        motion_dir=motion_dir,
    )
    draft_plan = _resolve_draft_plan(
        service=service,
        args=args,
        packet=packet,
        review_pipeline_path=review_pipeline_path,
    )

    inbox_dir = motion_dir / "inbox"
    if args.scaffold_inbox:
        service.scaffold_inbox(inbox_dir, assignment, packet)
        print(f"  Scaffolded inbox: {inbox_dir}")

    contributions: list = []
    attestations: list = []
    fallback_attestations_count = 0

    effective_mode = _determine_effective_mode(
        args=args,
        inbox_dir=inbox_dir,
        president_deliberator=president_deliberator,
    )

    if effective_mode == "llm" and president_deliberator:
        contributions, attestations, fallback_attestations_count = (
            _run_llm_deliberation(
                service=service,
                inbox_dir=inbox_dir,
                packet=packet,
                assignment=assignment,
            )
        )
    elif effective_mode == "manual" and inbox_dir.exists():
        contributions, attestations = _load_manual_responses(
            service=service,
            inbox_dir=inbox_dir,
            assignment=assignment,
            packet=packet,
        )

    blocker_workup_result = None
    if args.llm_blocker_workup and blocker_workup and contributions:
        blocker_workup_result = _run_blocker_workup(
            service=service,
            packet=packet,
            assignment=assignment,
            contributions=contributions,
            blocker_workup=blocker_workup,
            motion_dir=motion_dir,
        )

    result = service.integrate_execution_plan(
        packet=packet,
        assignment_record=assignment,
        contributions=contributions,
        attestations=attestations,
        draft_plan=draft_plan,
        blocker_workup_result=blocker_workup_result,
    )

    _save_json(motion_dir / "ratified-intent-packet.json", packet.to_dict())
    _save_json(motion_dir / "executive_assignment_record.json", assignment)
    _save_json(motion_dir / "execution_plan.json", result.execution_plan)
    _save_json(motion_dir / "executive_gates.json", result.gates.to_dict())
    _save_jsonl(motion_dir / "executive_events.jsonl", events)
    handoff = _build_handoff(
        packet=packet,
        result=result,
        motion_dir=motion_dir,
        blocker_workup_result=blocker_workup_result,
    )
    _save_json(motion_dir / "execution_plan_handoff.json", handoff)

    return {
        "motion_id": packet.motion_id,
        "cycle_id": result.cycle_id,
        "schema_version": result.schema_version,
        "plan_owner": result.plan_owner.to_dict(),
        "gates": result.gates.to_dict(),
        "blockers_requiring_escalation": len(result.blockers_requiring_escalation),
        "conclave_queue_items": len(result.conclave_queue_items),
        "discovery_task_stubs": len(result.discovery_task_stubs),
        "contributions_count": len(contributions),
        "attestations_count": len(attestations),
        "fallback_attestations_count": fallback_attestations_count,
        "motion_dir": str(motion_dir),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Executive planning pipeline")
    parser.add_argument(
        "review_pipeline_path",
        type=Path,
        nargs="?",
        default=None,
        help="Path to review pipeline output directory (auto-detects if not specified)",
    )
    parser.add_argument(
        "--from-ledger",
        type=Path,
        default=None,
        help="Path to ratified_mandates.json or its containing directory",
    )
    parser.add_argument(
        "--from-conclave",
        type=Path,
        default=None,
        help="Path to conclave results JSON, transcript, checkpoint, or output directory",
    )
    parser.add_argument(
        "--ledger-outdir",
        type=Path,
        default=Path("_bmad-output/motion-ledger"),
        help="Override motion ledger output directory when using --from-conclave",
    )
    parser.add_argument(
        "--outdir",
        type=Path,
        default=Path("_bmad-output/executive"),
        help="Base output directory",
    )
    parser.add_argument(
        "--motion-id",
        type=str,
        default=None,
        help="Limit to a single motion_id",
    )
    parser.add_argument(
        "--affected",
        type=str,
        default=None,
        help="Comma-separated affected portfolio_ids (override inference)",
    )
    parser.add_argument(
        "--owner",
        type=str,
        default=None,
        help="Plan owner portfolio_id (override inference)",
    )
    parser.add_argument(
        "--deadline-hours",
        type=int,
        default=24,
        help="Response deadline window in hours",
    )
    parser.add_argument(
        "--include-deferred",
        action="store_true",
        help="Include deferred novel proposals as HIGH-risk inputs",
    )
    parser.add_argument(
        "--draft-from-template",
        action="store_true",
        help="Generate a non-binding draft using the existing template planner",
    )
    parser.add_argument(
        "--real-agent",
        action="store_true",
        help="Enable LLM-powered classification inside the draft generator",
    )
    parser.add_argument(
        "--mode",
        type=str,
        choices=["manual", "llm", "auto"],
        default="auto",
        help="Deliberation mode: 'manual' loads from inbox, 'llm' uses LLM, 'auto' uses LLM when no manual artifacts exist (default: auto)",
    )
    parser.add_argument(
        "--scaffold-inbox",
        action="store_true",
        help="[DEPRECATED] Create scaffold files for Presidents to fill in responses (use for debugging only)",
    )
    parser.add_argument(
        "--load-inbox",
        action="store_true",
        help="[DEPRECATED] Use --mode=manual instead. Load contributions/attestations from inbox directory",
    )
    parser.add_argument(
        "--continue-cycle",
        action="store_true",
        help="Continue from existing assignment (use stored cycle_id instead of creating new)",
    )
    parser.add_argument(
        "--require-gates",
        action="store_true",
        help="Require all gates to pass before emitting handoff (exit 1 if failed)",
    )
    parser.add_argument(
        "--llm-deliberation",
        action="store_true",
        help="[DEPRECATED] Use --mode=llm instead. Use LLM-powered President deliberation",
    )
    parser.add_argument(
        "--llm-blocker-workup",
        action="store_true",
        help="Enable E2.5 LLM-powered blocker workup (classifies blockers, assigns dispositions)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()
    _handle_deprecated_flags(args)

    review_pipeline_path: Path | None = None
    mandates_path: Path | None = None
    if args.from_ledger and args.from_conclave:
        print("Error: --from-ledger and --from-conclave cannot be used together.")
        sys.exit(1)

    if args.from_ledger:
        mandates_path = _resolve_mandates_path(args.from_ledger)
    elif args.from_conclave:
        from scripts import run_registrar  # noqa: E402

        print("Running Registrar to produce ratified mandates...")
        mandates_path = run_registrar.register_conclave(
            args.from_conclave, args.ledger_outdir
        )
    else:
        review_pipeline_path = _resolve_review_pipeline_path(args)
    planner_agent = _init_planner_agent(args)
    president_deliberator = _init_president_deliberator(args)
    blocker_workup = _init_blocker_workup(args)

    base_service = ExecutivePlanningService(
        planner_agent=planner_agent,
        verbose=args.verbose,
    )
    if mandates_path is not None:
        packets = base_service.build_ratified_intent_packets_from_mandates(
            mandates_path=mandates_path
        )
        session_id = _load_mandate_session_id(mandates_path)
        session_dir = args.outdir / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        _save_json(
            session_dir / "ratified-intent-packets.json",
            [p.to_dict() for p in packets],
        )
        review_pipeline_path = mandates_path
    else:
        packets = _load_packets(
            base_service=base_service,
            review_pipeline_path=review_pipeline_path,
            args=args,
        )
        session_id, session_dir = _prepare_session_dir(
            review_pipeline_path=review_pipeline_path,
            outdir=args.outdir,
            packets=packets,
        )

    affected_override = _parse_list_arg(args.affected)
    owner_override = args.owner
    deadline = (
        datetime.now(timezone.utc) + timedelta(hours=args.deadline_hours)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")

    cycle_summaries: list[dict] = []
    for packet in packets:
        summary = _process_motion(
            packet=packet,
            session_dir=session_dir,
            review_pipeline_path=review_pipeline_path,
            args=args,
            planner_agent=planner_agent,
            president_deliberator=president_deliberator,
            blocker_workup=blocker_workup,
            affected_override=affected_override,
            owner_override=owner_override,
            deadline=deadline,
        )
        cycle_summaries.append(summary)

    _save_json(session_dir / "executive_cycle_summaries.json", cycle_summaries)

    # Count gate failures
    failures = sum(1 for s in cycle_summaries if "FAIL" in s.get("gates", {}).values())

    _print_pipeline_summary(
        session_id=session_id,
        packets=packets,
        args=args,
        cycle_summaries=cycle_summaries,
        session_dir=session_dir,
        failures=failures,
    )
    _enforce_gate_requirements(args, failures, cycle_summaries)


if __name__ == "__main__":
    main()
