#!/usr/bin/env python3
"""Run Three Fates Deliberation on Petitions.

This script runs the Three Fates deliberation protocol on petitions
that are in RECEIVED state. It ties together:
1. ArchonAssignmentService - assigns 3 Marquis archons
2. ContextPackageBuilderService - builds deliberation context
3. DeliberationOrchestratorService - runs 4-phase protocol
 4. DispositionEmissionService - routes outcomes

Usage:
    # Process a specific petition by ID
    python scripts/run_petition_deliberation.py --petition-id <UUID>

    # Process all petitions in RECEIVED state
    python scripts/run_petition_deliberation.py --all

    # Dry run (don't execute, just show what would happen)
    python scripts/run_petition_deliberation.py --all --dry-run

Constitutional Constraints:
- FR-11.1: Exactly 3 Marquis-rank Archons assigned
- FR-11.4: 4-phase protocol (ASSESS → POSITION → CROSS_EXAMINE → VOTE)
- FR-11.5: 2-of-3 supermajority for disposition
- AT-1: Every petition terminates in exactly one fate
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from structlog import get_logger

from src.bootstrap.petition_submission import get_petition_submission_repository
from src.domain.models.deliberation_session import DeliberationSession
from src.domain.models.petition_submission import PetitionState
from src.application.services.archon_assignment_service import ArchonAssignmentService
from src.application.services.archon_pool import get_archon_pool_service
from src.application.services.context_package_builder_service import ContextPackageBuilderService

logger = get_logger()


# ANSI colors for terminal output
class Colors:
    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"


def _ensure_crewai_env() -> None:
    """Disable CrewAI telemetry and set writable storage defaults."""
    os.environ.setdefault("CREWAI_DISABLE_TELEMETRY", "true")
    os.environ.setdefault("CREWAI_DISABLE_TRACKING", "true")
    os.environ.setdefault("OTEL_SDK_DISABLED", "true")
    os.environ.setdefault("CREWAI_TRACING_ENABLED", "false")
    os.environ.setdefault("CREWAI_TESTING", "true")
    os.environ.setdefault("CREWAI_STORAGE_DIR", "archon72")
    os.environ.setdefault("XDG_DATA_HOME", "/tmp/crewai-data")
    Path(os.environ["XDG_DATA_HOME"]).mkdir(parents=True, exist_ok=True)


def _get_transcript_store():
    """Resolve a transcript store (Postgres if configured, else in-memory)."""
    if os.environ.get("DATABASE_URL"):
        try:
            from src.bootstrap.database import get_session_factory
            from src.infrastructure.adapters.persistence.transcript_store import (
                PostgresTranscriptStore,
            )

            return PostgresTranscriptStore(session_factory=get_session_factory())
        except Exception as exc:
            logger.error("transcript_store_init_failed", error=str(exc))

    from src.infrastructure.stubs.transcript_store_stub import TranscriptStoreStub

    logger.warning(
        "transcript_store_initialized",
        repository_type="InMemoryStub",
        message="DATABASE_URL not set or init failed - using in-memory transcript store",
    )
    return TranscriptStoreStub()


def _is_deadlock_vote(votes) -> bool:
    """Check if votes are a 1-1-1 split (deadlock)."""
    counts = {}
    for vote in votes.values():
        counts[vote] = counts.get(vote, 0) + 1
    return len(counts) == 3 and all(count == 1 for count in counts.values())


def _extract_dissent_rationale(transcript: str, dissent_archon_id: UUID) -> str:
    """Extract dissenting archon's vote response from the VOTE transcript."""
    marker = f"({dissent_archon_id})"
    lines = transcript.splitlines()
    capture = False
    captured: list[str] = []
    for line in lines:
        if line.startswith("--- Vote from") and marker in line:
            capture = True
            continue
        if capture and line.startswith("--- Vote from"):
            break
        if capture:
            captured.append(line)
    rationale = "\n".join(captured).strip()
    if rationale:
        return rationale
    return "Dissent rationale captured in vote transcript (see witness hash)."


def _build_deadlock_consensus(session, votes):
    """Create a consensus result for a deadlock-triggered auto-ESCALATE."""
    from src.domain.models.consensus_result import (
        CONSENSUS_ALGORITHM_VERSION,
        ConsensusResult,
        ConsensusStatus,
    )
    from src.domain.models.deliberation_session import DeliberationOutcome

    vote_distribution: dict[str, int] = {}
    for vote in votes.values():
        vote_distribution[vote.value] = vote_distribution.get(vote.value, 0) + 1

    return ConsensusResult(
        session_id=session.session_id,
        petition_id=session.petition_id,
        status=ConsensusStatus.NOT_REACHED,
        winning_outcome=DeliberationOutcome.ESCALATE.value,
        vote_distribution=vote_distribution,
        majority_archon_ids=(),
        dissent_archon_id=None,
        algorithm_version=CONSENSUS_ALGORITHM_VERSION,
    )


def _json_safe(value):
    """Convert objects into JSON-serializable structures."""
    from enum import Enum
    from datetime import datetime

    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, bytes):
        return value.hex()
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {
            _json_safe(key): _json_safe(val)
            for key, val in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _map_disposition_to_state(outcome) -> PetitionState:
    """Map a disposition outcome to a petition state."""
    from src.domain.events.disposition import DispositionOutcome

    if outcome == DispositionOutcome.ACKNOWLEDGE:
        return PetitionState.ACKNOWLEDGED
    if outcome == DispositionOutcome.REFER:
        return PetitionState.REFERRED
    if outcome == DispositionOutcome.ESCALATE:
        return PetitionState.ESCALATED
    if outcome == DispositionOutcome.DEFER:
        return PetitionState.DEFERRED
    if outcome == DispositionOutcome.NO_RESPONSE:
        return PetitionState.NO_RESPONSE
    raise ValueError(f"Unsupported disposition outcome: {outcome}")


def _write_deliberation_output(payload: dict, petition_id: UUID, session_id: UUID) -> Path:
    """Write deliberation events and metadata to a durable JSON file."""
    output_dir = Path("_bmad-output/petition-deliberations")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"petition-{petition_id}-session-{session_id}.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    return output_file


class _ArchonAssignmentRepositoryAdapter:
    """Adapter to satisfy ArchonAssignmentService repository interface."""

    def __init__(self, submission_repo):
        self._repo = submission_repo

    async def get_by_id(self, petition_id: UUID):
        get_by_id = getattr(self._repo, "get_by_id", None)
        if get_by_id is not None:
            return await get_by_id(petition_id)
        return await self._repo.get(petition_id)

    async def update(self, petition) -> None:
        update_state = getattr(self._repo, "update_state", None)
        if update_state is None:
            raise AttributeError(
                "Petition repository missing update_state required for assignment"
            )
        try:
            await update_state(petition.id, petition.state, petition.fate_reason)
        except TypeError:
            await update_state(petition.id, petition.state)


def print_header(text: str) -> None:
    """Print a formatted header."""
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'=' * 70}")
    print(f"  {text}")
    print(f"{'=' * 70}{Colors.ENDC}\n")


async def get_petition(petition_id: UUID):
    """Fetch a petition by ID."""
    repo = get_petition_submission_repository()
    return await repo.get(petition_id)


async def get_received_petitions(limit: int = 10):
    """Fetch petitions in RECEIVED state."""
    repo = get_petition_submission_repository()
    petitions, total = await repo.list_by_state(PetitionState.RECEIVED, limit=limit)
    return petitions, total


async def run_deliberation_on_petition(petition, dry_run: bool = False):
    """Run Three Fates deliberation on a single petition."""
    log = logger.bind(petition_id=str(petition.id))

    print(f"\n{Colors.BLUE}Processing petition: {petition.id}{Colors.ENDC}")
    print(f"  Type: {petition.type.value}")
    print(f"  Realm: {petition.realm}")
    print(f"  Text preview: {petition.text[:100]}...")

    # Step 1: Assign Archons (FR-11.1)
    print(f"\n{Colors.YELLOW}Step 1: Assigning 3 Marquis Archons...{Colors.ENDC}")

    archon_pool = get_archon_pool_service()
    petition_repo_impl = get_petition_submission_repository()
    petition_repo = _ArchonAssignmentRepositoryAdapter(petition_repo_impl)

    if dry_run:
        assigned_archons = archon_pool.select_archons(petition.id)
        print("  Assigned Archons:")
        for i, archon in enumerate(assigned_archons, 1):
            print(f"    {i}. {archon.name} ({archon.title}) - {archon.id}")
        print(f"\n{Colors.YELLOW}[DRY RUN] Would proceed with deliberation{Colors.ENDC}")
        return True

    assigned_archons = None
    session = None

    if petition.state == PetitionState.DELIBERATING:
        assigned_archons = archon_pool.select_archons(petition.id)
        session = DeliberationSession.create(
            petition_id=petition.id,
            assigned_archons=tuple(a.id for a in assigned_archons),
        )
    else:
        assignment_service = ArchonAssignmentService(
            archon_pool=archon_pool,
            petition_repository=petition_repo,
        )
        assignment_result = await assignment_service.assign_archons(petition.id)
        assigned_archons = assignment_result.assigned_archons
        session = assignment_result.session
        refreshed = await petition_repo_impl.get(petition.id)
        if refreshed is not None:
            petition = refreshed
        else:
            log.warning("petition_refresh_failed", message="Using stale petition state")

    print("  Assigned Archons:")
    for i, archon in enumerate(assigned_archons, 1):
        print(f"    {i}. {archon.name} ({archon.title}) - {archon.id}")

    # Step 2: Create Deliberation Session
    print(f"\n{Colors.YELLOW}Step 2: Creating deliberation session...{Colors.ENDC}")

    print(f"  Session ID: {session.session_id}")
    print(f"  Phase: {session.phase.value}")

    # Step 3: Build Context Package (FR-11.3)
    print(f"\n{Colors.YELLOW}Step 3: Building context package...{Colors.ENDC}")

    context_builder = ContextPackageBuilderService()
    package = context_builder.build_package(petition, session)
    print(f"  Package hash: {package.content_hash[:16]}...")
    print(f"  Schema version: {package.schema_version}")

    # Step 4: Run Deliberation Orchestrator (FR-11.4)
    print(f"\n{Colors.YELLOW}Step 4: Running deliberation protocol...{Colors.ENDC}")
    print(f"  Protocol: ASSESS → POSITION → CROSS_EXAMINE → VOTE")

    try:
        _ensure_crewai_env()

        from src.application.services.archon_substitution_service import (
            ArchonSubstitutionService,
        )
        from src.application.services.consensus_resolver_service import (
            ConsensusResolverService,
        )
        from src.application.services.deadlock_handler_service import (
            DeadlockHandlerService,
        )
        from src.application.services.deliberation_orchestrator_service import (
            DeliberationOrchestratorService,
        )
        from src.application.services.deliberation_timeout_service import (
            DeliberationTimeoutService,
        )
        from src.application.services.disposition_emission_service import (
            DispositionEmissionService,
        )
        from src.application.services.dissent_recorder_service import (
            DissentRecorderService,
        )
        from src.application.services.phase_summary_generation_service import (
            PhaseSummaryGenerationService,
        )
        from src.application.services.phase_witness_batching_service import (
            PhaseWitnessBatchingService,
        )
        from src.domain.models.deliberation_session import DeliberationOutcome
        from src.infrastructure.adapters.external.crewai_deliberation_adapter import (
            create_crewai_deliberation_adapter,
        )
        from src.infrastructure.stubs.job_scheduler_stub import JobSchedulerStub

        executor = create_crewai_deliberation_adapter(verbose=True, timeout_seconds=120)
        timeout_handler = DeliberationTimeoutService(job_scheduler=JobSchedulerStub())
        deadlock_handler = DeadlockHandlerService()
        substitution_handler = ArchonSubstitutionService(archon_pool=archon_pool)

        orchestrator = DeliberationOrchestratorService(
            executor=executor,
            timeout_handler=timeout_handler,
            deadlock_handler=deadlock_handler,
            substitution_handler=substitution_handler,
        )

        session, deliberation_result = orchestrator.orchestrate(session, package)

        print(f"\n{Colors.GREEN}Deliberation Complete!{Colors.ENDC}")
        print(f"  Outcome: {deliberation_result.outcome.value}")

        # Step 5: Witness transcripts at phase boundaries (FR-11.7)
        print(f"\n{Colors.YELLOW}Step 5: Witnessing phase transcripts...{Colors.ENDC}")
        transcript_store = _get_transcript_store()
        witness_events = []
        witness_service = PhaseWitnessBatchingService(transcript_store=transcript_store)
        summary_service = PhaseSummaryGenerationService()

        for phase_result in deliberation_result.phase_results:
            try:
                metadata = await summary_service.augment_phase_metadata(
                    phase=phase_result.phase,
                    transcript=phase_result.transcript,
                    existing_metadata=phase_result.phase_metadata,
                )
            except Exception as exc:
                log.warning(
                    "phase_summary_failed",
                    phase=phase_result.phase.value,
                    error=str(exc),
                )
                metadata = dict(phase_result.phase_metadata)

            witness_event = await witness_service.witness_phase(
                session=session,
                phase=phase_result.phase,
                transcript=phase_result.transcript,
                metadata=metadata,
                start_timestamp=phase_result.started_at,
                end_timestamp=phase_result.completed_at,
            )
            witness_events.append(witness_event)
            if not session.phase.is_terminal():
                session = session.with_transcript(
                    phase_result.phase, witness_event.transcript_hash
                )
            print(
                f"  {phase_result.phase.value}: witness {witness_event.transcript_hash_hex[:16]}..."
            )

        # Step 6: Resolve consensus + disposition routing (FR-11.5, FR-11.11)
        print(f"\n{Colors.YELLOW}Step 6: Resolving consensus & routing disposition...{Colors.ENDC}")
        consensus = None
        disposition_result = None
        is_deadlock = False
        if deliberation_result.is_aborted:
            print(
                f"{Colors.YELLOW}  Deliberation aborted: {deliberation_result.abort_reason}. "
                "Auto-ESCALATE will be applied without consensus routing."
                f"{Colors.ENDC}"
            )
        else:
            is_deadlock = (
                deliberation_result.outcome == DeliberationOutcome.ESCALATE
                and _is_deadlock_vote(deliberation_result.votes)
            )

            consensus_resolver = ConsensusResolverService()
            if is_deadlock:
                consensus = _build_deadlock_consensus(session, deliberation_result.votes)
                print(
                    "  Deadlock detected (1-1-1). Auto-ESCALATE applied for routing."
                )
            else:
                consensus = consensus_resolver.resolve_consensus(
                    session, deliberation_result.votes
                )

            dissent_recorder = DissentRecorderService()
            if consensus.has_dissent and consensus.dissent_archon_id:
                vote_phase = next(
                    (
                        phase
                        for phase in deliberation_result.phase_results
                        if phase.phase.value == "VOTE"
                    ),
                    None,
                )
                rationale = (
                    _extract_dissent_rationale(
                        vote_phase.transcript, consensus.dissent_archon_id
                    )
                    if vote_phase is not None
                    else "Dissent rationale captured in vote transcript (missing phase reference)."
                )
                await dissent_recorder.record_dissent(session, consensus, rationale)

            disposition_service = DispositionEmissionService()
            disposition_result = await disposition_service.emit_disposition(
                session=session,
                consensus=consensus,
                petition=petition,
            )

            print(
                f"  Routed to pipeline: {disposition_result.routing_event.pipeline.value}"
            )
            print(
                f"  Pending disposition ID: {disposition_result.routing_event.event_id}"
            )

        # Step 7: Update petition disposition in database
        print(f"\n{Colors.YELLOW}Step 7: Updating petition disposition...{Colors.ENDC}")
        petition_update = {"success": False}
        petition_repo = get_petition_submission_repository()
        target_state = (
            _map_disposition_to_state(disposition_result.deliberation_event.outcome)
            if disposition_result is not None
            else PetitionState.ESCALATED
        )
        try:
            assign_fate = getattr(petition_repo, "assign_fate_cas", None)
            if callable(assign_fate):
                updated_petition = await assign_fate(
                    submission_id=petition.id,
                    expected_state=PetitionState.DELIBERATING,
                    new_state=target_state,
                    escalation_source="DELIBERATION"
                    if target_state == PetitionState.ESCALATED
                    else None,
                    escalated_to_realm=petition.realm
                    if target_state == PetitionState.ESCALATED
                    else None,
                )
                petition = updated_petition
            else:
                await petition_repo.update_state(petition.id, target_state)
                petition = await petition_repo.get(petition.id) or petition

            petition_update = {
                "success": True,
                "new_state": petition.state.value,
            }
            print(f"  Petition state updated: {petition.state.value}")
        except Exception as exc:
            log.error("petition_disposition_update_failed", error=str(exc))
            petition_update = {"success": False, "error": str(exc)}
            print(
                f"{Colors.RED}Petition state update failed: {exc}{Colors.ENDC}"
            )

        # Step 8: Emit deliberation events to file
        print(f"\n{Colors.YELLOW}Step 8: Writing deliberation events...{Colors.ENDC}")
        output_payload = {
            "petition_id": str(petition.id),
            "session_id": str(session.session_id),
            "petition_type": petition.type.value,
            "petition_realm": petition.realm,
            "assigned_archons": [
                {"id": str(archon.id), "name": archon.name, "title": archon.title}
                for archon in assigned_archons
            ],
            "context_package": {
                "content_hash": package.content_hash,
                "schema_version": package.schema_version,
            },
            "deliberation": {
                "started_at": deliberation_result.started_at.isoformat(),
                "completed_at": deliberation_result.completed_at.isoformat(),
                "outcome": deliberation_result.outcome.value,
                "votes": {
                    str(archon_id): outcome.value
                    for archon_id, outcome in deliberation_result.votes.items()
                },
                "phase_results": [
                    {
                        "phase": phase_result.phase.value,
                        "transcript_hash": phase_result.transcript_hash.hex(),
                        "participants": [
                            str(archon_id)
                            for archon_id in phase_result.participants
                        ],
                        "started_at": phase_result.started_at.isoformat(),
                        "completed_at": phase_result.completed_at.isoformat(),
                        "duration_ms": phase_result.duration_ms,
                        "metadata": _json_safe(phase_result.phase_metadata),
                    }
                    for phase_result in deliberation_result.phase_results
                ],
                "deadlock": is_deadlock,
                "timed_out": session.timed_out,
                "aborted": deliberation_result.is_aborted,
                "abort_reason": deliberation_result.abort_reason,
            },
            "consensus": _json_safe(consensus.to_dict()) if consensus else None,
            "events": _json_safe(
                {
                    **(
                        {
                            "deliberation_complete": disposition_result.deliberation_event.to_dict(),
                            "pipeline_routing": disposition_result.routing_event.to_dict(),
                        }
                        if disposition_result
                        else {}
                    ),
                    **(
                        {
                            "deliberation_aborted": {
                                "reason": deliberation_result.abort_reason
                            }
                        }
                        if deliberation_result.is_aborted
                        else {}
                    ),
                }
            ),
            "witness_events": [_json_safe(event.to_dict()) for event in witness_events],
            "petition_update": petition_update,
            "transcript_store": type(transcript_store).__name__,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

        output_file = _write_deliberation_output(
            output_payload, petition.id, session.session_id
        )
        print(f"  Event file: {output_file}")

        return deliberation_result

    except ImportError as e:
        print(f"\n{Colors.RED}CrewAI import failed: {e}{Colors.ENDC}")
        print(
            f"{Colors.YELLOW}If CrewAI is installed, check API keys or Ollama settings.{Colors.ENDC}"
        )
        return None
    except Exception as e:
        log.error("deliberation_failed", error=str(e))
        print(f"\n{Colors.RED}Deliberation failed: {e}{Colors.ENDC}")
        return None


async def main(args):
    """Main entry point."""
    print_header("THREE FATES PETITION DELIBERATION")

    if args.petition_id:
        # Process specific petition
        petition_id = UUID(args.petition_id)
        petition = await get_petition(petition_id)

        if petition is None:
            print(f"{Colors.RED}Petition not found: {petition_id}{Colors.ENDC}")
            return 1

        if petition.state != PetitionState.RECEIVED:
            print(
                f"{Colors.YELLOW}Warning: Petition is in {petition.state.value} state, not RECEIVED{Colors.ENDC}"
            )
            if petition.state != PetitionState.DELIBERATING and not args.force:
                print("Use --force to process anyway")
                return 1

        result = await run_deliberation_on_petition(petition, dry_run=args.dry_run)
        return 0 if result else 1

    elif args.all:
        # Process all RECEIVED petitions
        petitions, total = await get_received_petitions(limit=args.limit)

        print(f"Found {total} petitions in RECEIVED state (processing up to {args.limit})")

        if not petitions:
            print(f"{Colors.YELLOW}No petitions to process{Colors.ENDC}")
            return 0

        results = []
        for petition in petitions:
            result = await run_deliberation_on_petition(petition, dry_run=args.dry_run)
            results.append(result)

        # Summary
        print_header("DELIBERATION SUMMARY")
        successful = sum(1 for r in results if r is not None)
        print(f"  Processed: {len(results)}")
        print(f"  Successful: {successful}")
        print(f"  Failed: {len(results) - successful}")

        return 0

    else:
        print("Specify --petition-id <UUID> or --all")
        return 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run Three Fates deliberation on petitions",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--petition-id",
        type=str,
        help="UUID of specific petition to process",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Process all petitions in RECEIVED state",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum petitions to process (default: 10)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would happen without executing",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Process petition even if not in RECEIVED state",
    )

    args = parser.parse_args()

    sys.exit(asyncio.run(main(args)))
