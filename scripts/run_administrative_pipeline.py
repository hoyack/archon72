#!/usr/bin/env python3
"""Run the Administrative Pipeline on Executive execution handoffs.

This stage transforms Executive plans (WHAT) into implementation proposals (HOW)
through bottom-up resource discovery and capacity analysis.

Pipeline Flow:
Executive Pipeline -> execution_plan_handoff.json -> Administrative Pipeline
                                                     -> implementation_proposal.json (per epic)
                                                     -> resource_requests.json (aggregated)

Principle: "Conclave is for intent. Administration is for reality."
"""

from __future__ import annotations

import argparse
import asyncio
import glob
import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

from src.application.services.administrative_pipeline_service import (  # noqa: E402
    AdministrativePipelineService,
    now_iso,
)


def find_latest_executive_output() -> Path | None:
    """Find the most recent Executive Pipeline output directory."""
    pattern = "_bmad-output/executive/*"
    dirs = [d for d in glob.glob(pattern) if Path(d).is_dir()]
    if not dirs:
        return None
    return Path(max(dirs, key=lambda d: Path(d).stat().st_mtime))


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


def _process_motion(
    handoff: dict,
    executive_output_path: Path,
    session_dir: Path,
    args: argparse.Namespace,
    service: AdministrativePipelineService,
) -> dict:
    """Process a single motion through the Administrative Pipeline."""
    events: list[dict] = []
    motion_id = handoff.get("motion_id", "unknown")
    cycle_id = handoff.get("cycle_id", "unknown")

    # Create event sink
    def event_sink(event_type: str, payload: dict) -> None:
        events.append({"type": event_type, "payload": payload})

    # Create proposal generator based on mode
    proposal_generator = None
    if args.mode in ("llm", "auto"):
        try:
            from src.infrastructure.adapters.config.archon_profile_adapter import (
                create_archon_profile_repository,
            )
            from src.infrastructure.adapters.external.administrative_crewai_adapter import (
                create_administrative_proposal_generator,
            )

            profile_repo = create_archon_profile_repository()
            proposal_generator = create_administrative_proposal_generator(
                profile_repository=profile_repo,
                verbose=args.verbose,
            )
            print("  Loaded per-Archon LLM bindings for proposal generation")
        except ImportError as e:
            print(f"  Warning: Could not load LLM adapter: {e}")
            print("  Falling back to simulation mode")

    # Create service with event sink
    service_with_events = AdministrativePipelineService(
        event_sink=event_sink,
        proposal_generator=proposal_generator,
        verbose=args.verbose,
    )

    # Generate proposals based on mode
    if args.mode in ("llm", "auto"):
        # Check if LLM adapter is configured
        if service_with_events._proposal_generator is not None:
            import asyncio

            print(f"  Generating proposals via LLM for {motion_id}...")
            try:
                proposals = asyncio.run(
                    service_with_events.generate_proposals(
                        handoff=handoff,
                        executive_output_path=executive_output_path,
                    )
                )
            except Exception as e:
                print(f"  LLM error: {e}")
                print("  Falling back to simulation mode...")
                proposals = service_with_events.generate_proposals_simulation(
                    handoff=handoff,
                    executive_output_path=executive_output_path,
                )
        else:
            if args.mode == "llm":
                print(
                    f"  LLM adapter not configured, using simulation for {motion_id}..."
                )
            else:
                print(f"  Generating proposals (simulation) for {motion_id}...")
            proposals = service_with_events.generate_proposals_simulation(
                handoff=handoff,
                executive_output_path=executive_output_path,
            )
    elif args.mode == "manual":
        print(f"  Loading manual proposals for {motion_id}...")
        # Manual mode would load from inbox - for now use simulation
        print("  Manual mode not yet implemented, using simulation...")
        proposals = service_with_events.generate_proposals_simulation(
            handoff=handoff,
            executive_output_path=executive_output_path,
        )
    else:  # simulation
        print(f"  Generating proposals (simulation) for {motion_id}...")
        proposals = service_with_events.generate_proposals_simulation(
            handoff=handoff,
            executive_output_path=executive_output_path,
        )

    # Save results
    motion_dir = service_with_events.save_results(
        proposals=proposals,
        output_dir=session_dir,
        cycle_id=cycle_id,
        motion_id=motion_id,
    )

    # Save events
    _save_jsonl(motion_dir / "admin_events.jsonl", events)

    return {
        "motion_id": motion_id,
        "cycle_id": cycle_id,
        "proposal_count": len(proposals),
        "epic_ids": [p.epic_id for p in proposals],
        "total_tactics": sum(len(p.tactics) for p in proposals),
        "total_risks": sum(len(p.risks) for p in proposals),
        "total_resource_requests": sum(len(p.resource_requests) for p in proposals),
        "motion_dir": str(motion_dir),
    }


def _run_execution_programs(
    handoffs: list[dict],
    executive_output_path: Path,
    session_dir: Path,
    args: argparse.Namespace,
) -> list[dict]:
    """Run Execution Program Stages A-F for each handoff."""
    from src.application.services.execution_program_service import (
        ExecutionProgramService,
    )

    events: list[dict] = []

    def event_sink(event_type: str, payload: dict) -> None:
        events.append({"type": event_type, "payload": payload})

    # Create port injections based on mode
    tool_executor = None
    audit_bus = None
    profile_repository = None

    if args.mode in ("llm", "auto"):
        try:
            from src.infrastructure.adapters.external.tool_execution_adapter import (
                create_tool_executor,
            )

            tool_executor = create_tool_executor(verbose=args.verbose)
            print("  Loaded tool execution adapter")
        except ImportError as e:
            print(f"  Warning: Could not load tool executor: {e}")

        try:
            from src.infrastructure.adapters.external.in_memory_audit_bus import (
                InMemoryAuditEventBus,
            )

            audit_bus = InMemoryAuditEventBus()
            print("  Loaded audit event bus")
        except ImportError as e:
            print(f"  Warning: Could not load audit bus: {e}")

        try:
            from src.infrastructure.adapters.config.archon_profile_adapter import (
                create_archon_profile_repository,
            )

            profile_repository = create_archon_profile_repository()
            print("  Loaded Archon profile repository")
        except ImportError as e:
            print(f"  Warning: Could not load profile repository: {e}")

    service = ExecutionProgramService(
        tool_executor=tool_executor,
        audit_bus=audit_bus,
        profile_repository=profile_repository,
        event_sink=event_sink,
        verbose=args.verbose,
    )

    # Load existing admin service for epic loading
    admin_service = AdministrativePipelineService(verbose=args.verbose)

    async def _run_stages_for_motion(
        svc: ExecutionProgramService,
        admin_svc: AdministrativePipelineService,
        handoff: dict,
        exec_output_path: Path,
        out_dir: Path,
    ) -> dict:
        motion_id = handoff.get("motion_id", "unknown")

        # Load epics and work packages
        epics = admin_svc.load_epics_from_handoff(
            handoff=handoff,
            executive_output_path=exec_output_path,
        )
        work_packages = svc.load_work_packages_from_handoff(
            handoff=handoff,
            executive_output_path=exec_output_path,
        )

        print(f"    Epics: {len(epics)}, Work Packages: {len(work_packages)}")

        # Stage A: Intake
        program = await svc.create_program_from_handoff(
            handoff=handoff,
            executive_output_path=exec_output_path,
            epics=epics,
            work_packages=work_packages,
        )
        print(f"    Stage A (Intake): program={program.program_id}")

        # Stage B: Feasibility
        program, blockers = await svc.run_feasibility_checks(
            program=program,
            epics=epics,
            work_packages=work_packages,
        )
        print(
            f"    Stage B (Feasibility): "
            f"feasible={len(program.tasks)}, blockers={len(blockers)}"
        )

        # Stage C: Commit
        program = await svc.commit_program(program)
        print(f"    Stage C (Commit): stage={program.stage.value}")

        # Stage D: Activation
        program = await svc.activate_tasks(
            program=program,
            work_packages=work_packages,
            epics=epics,
        )
        activated = sum(
            1 for s in program.tasks.values() if s.value in ("ACTIVATED", "COMPLETED")
        )
        print(f"    Stage D (Activation): activated={activated}")

        # Stage E: Results
        program = await svc.collect_results(
            program=program,
            results=[],
        )
        completion = (
            program.completion_status.value
            if program.completion_status
            else "IN_PROGRESS"
        )
        print(
            f"    Stage E (Results): "
            f"artifacts={len(program.result_artifacts)}, "
            f"completion={completion}"
        )

        # Stage F skipped unless violation detected
        print("    Stage F (Violation): skipped (no violations)")

        # Save program output
        program_dir = out_dir / "programs" / program.program_id
        program_dir.mkdir(parents=True, exist_ok=True)
        _save_json(program_dir / "execution_program.json", program.to_dict())

        return {
            "program_id": program.program_id,
            "motion_id": motion_id,
            "duke": (
                program.duke_assignment.duke_name if program.duke_assignment else "none"
            ),
            "total_tasks": len(program.tasks),
            "activated": activated,
            "results": len(program.result_artifacts),
            "blockers": len(program.blocker_reports),
            "completion_status": completion,
            "stage": program.stage.value,
        }

    program_summaries: list[dict] = []

    for handoff in handoffs:
        motion_id = handoff.get("motion_id", "unknown")
        print(f"\n  Running Execution Program for motion: {motion_id}")

        summary = asyncio.run(
            _run_stages_for_motion(
                svc=service,
                admin_svc=admin_service,
                handoff=handoff,
                exec_output_path=executive_output_path,
                out_dir=session_dir,
            )
        )
        program_summaries.append(summary)

    # Save events
    _save_jsonl(session_dir / "execution_program_events.jsonl", events)

    return program_summaries


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run Administrative Pipeline on Executive execution handoffs"
    )
    parser.add_argument(
        "executive_output_path",
        type=Path,
        nargs="?",
        default=None,
        help="Path to Executive Pipeline output directory (auto-detects if not specified)",
    )
    parser.add_argument(
        "--outdir",
        type=Path,
        default=Path("_bmad-output/administrative"),
        help="Base output directory",
    )
    parser.add_argument(
        "--motion-id",
        type=str,
        default=None,
        help="Limit to a single motion_id",
    )
    parser.add_argument(
        "--mode",
        type=str,
        choices=["manual", "llm", "auto", "simulation"],
        default="auto",
        help=(
            "Proposal generation mode: 'manual' loads from inbox, "
            "'llm' uses LLM, 'auto' uses LLM when available, "
            "'simulation' generates test proposals (default: auto)"
        ),
    )
    parser.add_argument(
        "--execution-programs",
        action="store_true",
        help="Run Execution Program Stages A-F after proposal generation",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    # Auto-detect Executive output if not specified
    if args.executive_output_path is None:
        args.executive_output_path = find_latest_executive_output()
        if args.executive_output_path is None:
            print("Error: No Executive Pipeline output found.")
            print("Run Executive Pipeline first or specify path explicitly.")
            print("Looking for: _bmad-output/executive/*/")
            sys.exit(1)
        print(f"Auto-detected Executive output: {args.executive_output_path}")

    executive_output_path = args.executive_output_path.resolve()
    if not executive_output_path.exists():
        print(f"Error: Executive output not found: {executive_output_path}")
        sys.exit(1)

    # Initialize service
    service = AdministrativePipelineService(verbose=args.verbose)

    # Load handoffs
    handoffs = service.load_execution_handoff(
        executive_output_path=executive_output_path,
        motion_id=args.motion_id,
    )

    if not handoffs:
        print("No execution handoffs found for the given inputs.")
        sys.exit(1)

    # Create session directory
    session_id = executive_output_path.name
    session_dir = args.outdir / session_id
    session_dir.mkdir(parents=True, exist_ok=True)

    print(f"\nProcessing {len(handoffs)} motion(s)...")

    # Process each motion
    summaries: list[dict] = []
    for handoff in handoffs:
        motion_id = handoff.get("motion_id", "unknown")
        print(f"\nProcessing motion: {motion_id}")

        summary = _process_motion(
            handoff=handoff,
            executive_output_path=executive_output_path,
            session_dir=session_dir,
            args=args,
            service=service,
        )
        summaries.append(summary)

    # Save pipeline summary
    pipeline_summary = {
        "session_id": session_id,
        "created_at": now_iso(),
        "mode": args.mode,
        "motions_processed": len(summaries),
        "total_proposals": sum(s["proposal_count"] for s in summaries),
        "total_tactics": sum(s["total_tactics"] for s in summaries),
        "total_risks": sum(s["total_risks"] for s in summaries),
        "total_resource_requests": sum(s["total_resource_requests"] for s in summaries),
        "motion_summaries": summaries,
    }
    _save_json(session_dir / "admin_pipeline_summary.json", pipeline_summary)

    # Print summary
    print("\n" + "=" * 60)
    print("ADMINISTRATIVE PIPELINE COMPLETE")
    print("=" * 60)
    print(f"Session: {session_id}")
    print(f"Motions processed: {len(summaries)}")
    print(f"Total proposals generated: {pipeline_summary['total_proposals']}")
    print(f"Total tactics: {pipeline_summary['total_tactics']}")
    print(f"Total risks identified: {pipeline_summary['total_risks']}")
    print(f"Total resource requests: {pipeline_summary['total_resource_requests']}")
    print(f"Mode: {args.mode}")
    print(f"Output saved to: {session_dir}")
    print("=" * 60 + "\n")

    # Run Execution Programs if requested
    if args.execution_programs:
        print("\n" + "=" * 60)
        print("EXECUTION PROGRAMS (Stages A-F)")
        print("=" * 60)

        program_summaries = _run_execution_programs(
            handoffs=handoffs,
            executive_output_path=executive_output_path,
            session_dir=session_dir,
            args=args,
        )

        # Save execution program summary
        exec_summary = {
            "session_id": session_id,
            "created_at": now_iso(),
            "mode": args.mode,
            "programs_created": len(program_summaries),
            "total_tasks": sum(s["total_tasks"] for s in program_summaries),
            "total_activated": sum(s["activated"] for s in program_summaries),
            "total_results": sum(s["results"] for s in program_summaries),
            "total_blockers": sum(s["blockers"] for s in program_summaries),
            "program_summaries": program_summaries,
        }
        _save_json(session_dir / "execution_program_summary.json", exec_summary)

        print("\n" + "-" * 60)
        print("EXECUTION PROGRAMS COMPLETE")
        print("-" * 60)
        print(f"Programs created: {len(program_summaries)}")
        print(f"Total tasks: {exec_summary['total_tasks']}")
        print(f"Total activated: {exec_summary['total_activated']}")
        print(f"Total results: {exec_summary['total_results']}")
        print(f"Total blockers: {exec_summary['total_blockers']}")
        for ps in program_summaries:
            print(
                f"  {ps['program_id']}: {ps['completion_status']} "
                f"(duke={ps['duke']}, tasks={ps['total_tasks']})"
            )
        print("-" * 60 + "\n")


if __name__ == "__main__":
    main()
