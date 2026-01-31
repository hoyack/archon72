#!/usr/bin/env python3
"""Diagnose and fix blocked RFP sessions.

Loads a blocked RFP session, identifies failed contributions, re-runs only
those Presidents, replaces the failed contributions in-place, and
re-finalizes the RFP.

Usage:
    python scripts/unblock_rfp.py --session-dir _bmad-output/rfp/rfp_f35d55a37c3e
    python scripts/unblock_rfp.py --session-dir ... --diagnose
    python scripts/unblock_rfp.py --session-dir ... --relax-lint
    python scripts/unblock_rfp.py --session-dir ... --max-attempts 5
    python scripts/unblock_rfp.py --session-dir ... --model qwen3:latest --provider ollama
    python scripts/unblock_rfp.py --session-dir ... --mode simulation
    python scripts/unblock_rfp.py --session-dir ... --dump-raw
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

from src.domain.models.rfp import (  # noqa: E402
    ContributionStatus,
    PortfolioContribution,
    RFPDocument,
)

# ---------------------------------------------------------------------------
# Failure classification
# ---------------------------------------------------------------------------

FAILURE_CATEGORIES = {
    "lint": [
        "lint violation",
        "mechanism-specific term",
        "branch or role reference",
        "branch assignment",
        "governance construct",
        "quantitative constraint",
        "constitutional lint",
    ],
    "empty": [
        "empty contribution",
        "empty response",
        "no requirements",
        "no content",
    ],
    "parse": [
        "json parse error",
        "parse failure",
        "could not parse",
    ],
    "timeout": [
        "timeout",
        "timed out",
        "temporarily unavailable",
        "connection error",
    ],
}


def classify_failure(contrib: PortfolioContribution) -> str:
    """Categorize failure type from contribution status and reason."""
    if contrib.status != ContributionStatus.FAILED:
        return "ok"

    reason = (contrib.failure_reason or "").lower()
    summary = (contrib.contribution_summary or "").lower()
    combined = f"{reason} {summary}"

    for category, keywords in FAILURE_CATEGORIES.items():
        if any(kw in combined for kw in keywords):
            return category

    return "unknown"


# ---------------------------------------------------------------------------
# Session loading
# ---------------------------------------------------------------------------


def _find_mandate_dir(session_dir: Path, mandate_id: str | None) -> Path:
    """Locate the mandate directory inside a session dir.

    If *mandate_id* is given, use it directly.  Otherwise pick the only
    mandate dir present (or error if there are multiple).
    """
    mandates_root = session_dir / "mandates"
    if not mandates_root.is_dir():
        raise FileNotFoundError(f"No mandates/ directory found in {session_dir}")

    if mandate_id:
        candidate = mandates_root / mandate_id
        if not candidate.is_dir():
            raise FileNotFoundError(f"Mandate directory not found: {candidate}")
        return candidate

    mandate_dirs = [d for d in mandates_root.iterdir() if d.is_dir()]
    if len(mandate_dirs) == 1:
        return mandate_dirs[0]
    if not mandate_dirs:
        raise FileNotFoundError(f"No mandate directories in {mandates_root}")
    raise ValueError(
        f"Multiple mandates found in {mandates_root}: "
        f"{[d.name for d in mandate_dirs]}. "
        "Specify --mandate-id to select one."
    )


def load_session(
    session_dir: Path,
    mandate_id: str | None = None,
) -> tuple[dict, list[PortfolioContribution], Path]:
    """Load rfp.json and contribution files from a session directory.

    Returns:
        (rfp_data_dict, list_of_contributions, mandate_dir_path)
    """
    mandate_dir = _find_mandate_dir(session_dir, mandate_id)

    rfp_path = mandate_dir / "rfp.json"
    if not rfp_path.exists():
        raise FileNotFoundError(f"rfp.json not found at {rfp_path}")

    with open(rfp_path, encoding="utf-8") as f:
        rfp_data = json.load(f)

    contributions_dir = mandate_dir / "contributions"
    contributions: list[PortfolioContribution] = []

    if contributions_dir.is_dir():
        for cpath in sorted(contributions_dir.glob("contribution_*.json")):
            with open(cpath, encoding="utf-8") as f:
                cdata = json.load(f)
            contributions.append(PortfolioContribution.from_dict(cdata))

    # Fall back to inline contributions if no files found
    if not contributions and rfp_data.get("portfolio_contributions"):
        for cdata in rfp_data["portfolio_contributions"]:
            contributions.append(PortfolioContribution.from_dict(cdata))

    return rfp_data, contributions, mandate_dir


# ---------------------------------------------------------------------------
# Diagnosis
# ---------------------------------------------------------------------------


def diagnose(
    rfp_data: dict,
    contributions: list[PortfolioContribution],
) -> list[PortfolioContribution]:
    """Print status report for all contributions, return failed ones."""
    status_str = rfp_data.get("status", "unknown")
    mandate_id = rfp_data.get("mandate_id", "unknown")
    title = rfp_data.get("background", {}).get("motion_title", "Untitled")

    print("\nSession diagnosis")
    print(f"  Mandate:  {mandate_id}")
    print(f"  Title:    {title}")
    print(f"  Status:   {status_str}")
    print(f"  Contributions: {len(contributions)}")
    print()

    failed: list[PortfolioContribution] = []
    for contrib in contributions:
        category = classify_failure(contrib)
        status_label = contrib.status.value.upper()
        marker = "  OK " if category == "ok" else " FAIL"

        line = f"  [{marker}] {contrib.president_name:<20s}  {status_label:<12s}"
        if category != "ok":
            reason_short = (contrib.failure_reason or "no reason")[:60]
            line += f"  ({category}: {reason_short})"
            failed.append(contrib)
        else:
            fr = len(contrib.functional_requirements)
            nfr = len(contrib.non_functional_requirements)
            c = len(contrib.constraints)
            line += f"  FR={fr} NFR={nfr} C={c}"

        print(line)

    print()
    if failed:
        print(f"  {len(failed)} failed contribution(s) need re-running.")
    else:
        print("  All contributions are healthy.")

    return failed


# ---------------------------------------------------------------------------
# President lookup
# ---------------------------------------------------------------------------


def find_president_for_contribution(
    contrib: PortfolioContribution,
    presidents: list[dict],
) -> dict | None:
    """Match a failed contribution back to its President data."""
    for p in presidents:
        if p["portfolio_id"] == contrib.portfolio_id:
            return p
        if p["name"] == contrib.president_name:
            return p
    return None


# ---------------------------------------------------------------------------
# Re-run failed contributions
# ---------------------------------------------------------------------------


async def rerun_failed_contributions(
    failed: list[PortfolioContribution],
    presidents: list[dict],
    rfp_data: dict,
    rfp_contributor,
    max_attempts: int,
    events: list[dict],
    verbose: bool,
    dump_raw: bool,
    mandate_dir: Path,
) -> list[PortfolioContribution]:
    """Re-run only failed Presidents through the adapter.

    Returns list of new contributions (successful or still failed).
    """
    import os

    background = rfp_data.get("background", {})
    mandate_id = rfp_data.get("mandate_id", "unknown")
    motion_title = background.get("motion_title", "")
    motion_text = background.get("motion_text", "")

    # Temporarily override retry env var
    old_val = os.environ.get("RFP_CONTRIBUTION_RETRIES")
    os.environ["RFP_CONTRIBUTION_RETRIES"] = str(max_attempts)

    new_contributions: list[PortfolioContribution] = []

    for contrib in failed:
        president = find_president_for_contribution(contrib, presidents)
        if not president:
            print(
                f"  WARNING: No president found for {contrib.president_name}, skipping"
            )
            new_contributions.append(contrib)
            continue

        print(f"  Re-running {president['name']}...")
        events.append(
            {
                "type": "unblock_contribution_retried",
                "payload": {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "president_name": president["name"],
                    "portfolio_id": president["portfolio_id"],
                    "original_failure": contrib.failure_reason or "",
                },
            }
        )

        try:
            new_contrib = await rfp_contributor.generate_contribution(
                mandate_id=mandate_id,
                motion_title=motion_title,
                motion_text=motion_text,
                portfolio_id=president["portfolio_id"],
                president_name=president["name"],
                portfolio_domain=president.get("domain", ""),
                president_id=president.get("id", ""),
                existing_contributions=[],
            )
            new_contrib.portfolio_label = president.get("portfolio_label", "")

            if dump_raw:
                debug_path = (
                    mandate_dir
                    / "contributions"
                    / f"debug_{president['portfolio_id']}.txt"
                )
                debug_path.parent.mkdir(parents=True, exist_ok=True)
                with open(debug_path, "w", encoding="utf-8") as f:
                    f.write(json.dumps(new_contrib.to_dict(), indent=2))

            if new_contrib.status == ContributionStatus.FAILED:
                print(f"    STILL FAILED: {new_contrib.failure_reason or 'unknown'}")
                events.append(
                    {
                        "type": "unblock_contribution_failed",
                        "payload": {
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "president_name": president["name"],
                            "portfolio_id": president["portfolio_id"],
                            "failure_reason": new_contrib.failure_reason or "",
                        },
                    }
                )
            else:
                fr = len(new_contrib.functional_requirements)
                nfr = len(new_contrib.non_functional_requirements)
                print(f"    SUCCESS: FR={fr} NFR={nfr}")
                events.append(
                    {
                        "type": "unblock_contribution_succeeded",
                        "payload": {
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "president_name": president["name"],
                            "portfolio_id": president["portfolio_id"],
                            "functional_requirements": fr,
                            "non_functional_requirements": nfr,
                        },
                    }
                )

            new_contributions.append(new_contrib)

        except Exception as exc:
            print(f"    ERROR: {exc}")
            events.append(
                {
                    "type": "unblock_contribution_failed",
                    "payload": {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "president_name": president["name"],
                        "portfolio_id": president["portfolio_id"],
                        "failure_reason": str(exc),
                    },
                }
            )
            new_contributions.append(contrib)

    # Restore env var
    if old_val is None:
        os.environ.pop("RFP_CONTRIBUTION_RETRIES", None)
    else:
        os.environ["RFP_CONTRIBUTION_RETRIES"] = old_val

    return new_contributions


def _simulate_failed_contributions(
    failed: list[PortfolioContribution],
    presidents: list[dict],
    rfp_data: dict,
    events: list[dict],
) -> list[PortfolioContribution]:
    """Use simulation mode to replace failed contributions (no LLM)."""
    from src.application.services.rfp_generation_service import RFPGenerationService

    background = rfp_data.get("background", {})
    motion_title = background.get("motion_title", "")
    mandate_id = rfp_data.get("mandate_id", "unknown")

    # Build a temporary RFP for the simulation helper
    tmp_rfp = RFPDocument.create(
        mandate_id=mandate_id,
        motion_title=motion_title,
        motion_text=background.get("motion_text", ""),
    )

    # Only simulate the failed presidents
    failed_portfolio_ids = {c.portfolio_id for c in failed}
    failed_presidents = [
        p for p in presidents if p["portfolio_id"] in failed_portfolio_ids
    ]

    service = RFPGenerationService()
    simulated = service._simulate_contributions(tmp_rfp, failed_presidents)

    for sim in simulated:
        events.append(
            {
                "type": "unblock_contribution_succeeded",
                "payload": {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "president_name": sim.president_name,
                    "portfolio_id": sim.portfolio_id,
                    "functional_requirements": len(sim.functional_requirements),
                    "non_functional_requirements": len(sim.non_functional_requirements),
                    "mode": "simulation",
                },
            }
        )

    return simulated


# ---------------------------------------------------------------------------
# Rebuild RFP
# ---------------------------------------------------------------------------


def rebuild_rfp(
    rfp_data: dict,
    all_contributions: list[PortfolioContribution],
    expected_portfolios: list[str],
) -> RFPDocument:
    """Create fresh RFPDocument, add all contributions, synthesize, finalize."""
    from src.application.services.rfp_generation_service import RFPGenerationService

    background = rfp_data.get("background", {})

    rfp = RFPDocument.create(
        mandate_id=rfp_data["mandate_id"],
        motion_title=background.get("motion_title", ""),
        motion_text=background.get("motion_text", ""),
    )

    # Preserve original metadata
    rfp.implementation_dossier_id = rfp_data.get(
        "implementation_dossier_id", rfp.implementation_dossier_id
    )
    rfp.created_at = rfp_data.get("created_at", rfp.created_at)
    rfp.business_justification = background.get("business_justification", "")
    rfp.strategic_alignment = background.get("strategic_alignment", [])
    rfp.executive_scope_disclaimer = rfp_data.get(
        "executive_scope_disclaimer", rfp.executive_scope_disclaimer
    )

    # Add all contributions (successful originals + new replacements)
    for contrib in all_contributions:
        rfp.add_contribution(contrib)

    # Run synthesis pipeline
    service = RFPGenerationService()
    service._basic_synthesis(rfp, all_contributions)
    service._derive_scope(rfp)
    service._add_default_terms(rfp)

    # Clear stale FAILED entries from open_questions before finalize
    rfp.open_questions = [q for q in rfp.open_questions if not q.startswith("FAILED:")]

    rfp.finalize(expected_portfolios=expected_portfolios)

    return rfp


# ---------------------------------------------------------------------------
# Save updated session
# ---------------------------------------------------------------------------


def save_updated_rfp(
    rfp: RFPDocument,
    contributions: list[PortfolioContribution],
    mandate_dir: Path,
    session_id: str,
    events: list[dict],
) -> None:
    """Write rfp.json, rfp.md, contribution files, and append events."""
    from src.application.services.rfp_generation_service import (
        SCHEMA_VERSION,
        RFPGenerationService,
    )

    # Save rfp.json
    rfp_path = mandate_dir / "rfp.json"
    rfp_dict = {
        "schema_version": SCHEMA_VERSION,
        "session_id": session_id,
        **rfp.to_dict(),
    }
    with open(rfp_path, "w", encoding="utf-8") as f:
        json.dump(rfp_dict, f, indent=2)

    # Save rfp.md
    service = RFPGenerationService()
    md_path = mandate_dir / "rfp.md"
    service._save_rfp_markdown(rfp, md_path)

    # Save contribution files
    contributions_dir = mandate_dir / "contributions"
    contributions_dir.mkdir(parents=True, exist_ok=True)
    for contrib in contributions:
        contrib_dict = contrib.to_dict()
        contrib_data = {
            "schema_version": SCHEMA_VERSION,
            "session_id": session_id,
            "mandate_id": rfp.mandate_id,
            **contrib_dict,
        }
        cpath = contributions_dir / f"contribution_{contrib.portfolio_id}.json"
        with open(cpath, "w", encoding="utf-8") as f:
            json.dump(contrib_data, f, indent=2)

    # Append events to rfp_events.jsonl
    events_path = mandate_dir / "rfp_events.jsonl"
    with open(events_path, "a", encoding="utf-8") as f:
        for event in events:
            f.write(json.dumps(event) + "\n")

    print(f"\n  Saved: {rfp_path}")
    print(f"  Saved: {md_path}")
    print(f"  Events appended: {events_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Diagnose and fix blocked RFP sessions",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        "--session-dir",
        type=Path,
        required=True,
        help="Path to the RFP session directory (e.g., _bmad-output/rfp/rfp_f35d55a37c3e)",
    )
    parser.add_argument(
        "--mandate-id",
        type=str,
        default=None,
        help="Mandate ID to process (auto-detected if only one mandate in session)",
    )
    parser.add_argument(
        "--diagnose",
        action="store_true",
        help="Print diagnostic report only, do not re-run",
    )
    parser.add_argument(
        "--relax-lint",
        action="store_true",
        help="Skip constitutional lint checks when re-running contributions",
    )
    parser.add_argument(
        "--max-attempts",
        type=int,
        default=3,
        help="Maximum retry attempts per failed President (default: 3)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Override LLM model for re-runs (e.g., 'qwen3:latest')",
    )
    parser.add_argument(
        "--provider",
        type=str,
        default=None,
        help="Override LLM provider (e.g., 'ollama', 'openai')",
    )
    parser.add_argument(
        "--base-url",
        type=str,
        default=None,
        help="Override LLM base URL (e.g., 'http://localhost:11434')",
    )
    parser.add_argument(
        "--mode",
        type=str,
        choices=["llm", "simulation"],
        default="llm",
        help="Mode: 'llm' re-runs with LLM, 'simulation' uses test templates",
    )
    parser.add_argument(
        "--dump-raw",
        action="store_true",
        help="Save debug output for re-run contributions",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    if not args.session_dir.is_dir():
        print(f"Error: Session directory not found: {args.session_dir}")
        sys.exit(1)

    # ---- Load session ----
    print(f"Loading session: {args.session_dir}")
    rfp_data, contributions, mandate_dir = load_session(
        args.session_dir, args.mandate_id
    )

    # ---- Diagnose ----
    failed = diagnose(rfp_data, contributions)

    if args.diagnose:
        sys.exit(0 if not failed else 1)

    if not failed:
        print("Nothing to fix - all contributions are healthy.")
        sys.exit(0)

    # ---- Load presidents ----
    from scripts.run_rfp_generator import load_presidents

    presidents = load_presidents()
    expected_portfolios = [p["portfolio_id"] for p in presidents]

    # ---- Unblock events ----
    events: list[dict] = [
        {
            "type": "unblock_started",
            "payload": {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "session_dir": str(args.session_dir),
                "mandate_id": rfp_data.get("mandate_id", "unknown"),
                "failed_count": len(failed),
                "failed_presidents": [c.president_name for c in failed],
                "mode": args.mode,
                "relax_lint": args.relax_lint,
                "max_attempts": args.max_attempts,
            },
        }
    ]

    # ---- Re-run failed contributions ----
    session_id = rfp_data.get("session_id", args.session_dir.name)

    if args.mode == "simulation":
        print("\nRe-running failed contributions in SIMULATION mode...")
        new_contributions = _simulate_failed_contributions(
            failed, presidents, rfp_data, events
        )
    else:
        # Initialize the RFP contributor adapter
        from src.infrastructure.adapters.config.archon_profile_adapter import (
            create_archon_profile_repository,
        )
        from src.infrastructure.adapters.external import create_rfp_contributor

        print("\nInitializing RFP contributor for re-runs...")
        profile_repo = create_archon_profile_repository()
        rfp_contributor = create_rfp_contributor(
            profile_repository=profile_repo,
            verbose=args.verbose,
            model=args.model,
            provider=args.provider,
            base_url=args.base_url,
            lint_enabled=not args.relax_lint,
        )

        print(f"Re-running {len(failed)} failed contribution(s)...")
        new_contributions = asyncio.run(
            rerun_failed_contributions(
                failed=failed,
                presidents=presidents,
                rfp_data=rfp_data,
                rfp_contributor=rfp_contributor,
                max_attempts=args.max_attempts,
                events=events,
                verbose=args.verbose,
                dump_raw=args.dump_raw,
                mandate_dir=mandate_dir,
            )
        )

    # ---- Merge: keep successful originals, swap in new for failed ----
    failed_portfolio_ids = {c.portfolio_id for c in failed}
    new_by_portfolio = {c.portfolio_id: c for c in new_contributions}

    merged: list[PortfolioContribution] = []
    for contrib in contributions:
        if contrib.portfolio_id in failed_portfolio_ids:
            replacement = new_by_portfolio.get(contrib.portfolio_id)
            if replacement:
                merged.append(replacement)
            else:
                merged.append(contrib)
        else:
            merged.append(contrib)

    # ---- Rebuild and finalize ----
    print("\nRebuilding RFP from merged contributions...")
    rfp = rebuild_rfp(rfp_data, merged, expected_portfolios)

    events.append(
        {
            "type": "unblock_finalized",
            "payload": {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "status": rfp.status.value,
                "functional_requirements": len(rfp.functional_requirements),
                "non_functional_requirements": len(rfp.non_functional_requirements),
                "constraints": len(rfp.constraints),
                "deliverables": len(rfp.deliverables),
            },
        }
    )

    # ---- Save ----
    print("\nSaving updated session...")
    save_updated_rfp(rfp, merged, mandate_dir, session_id, events)

    # ---- Summary ----
    still_failed = [c for c in merged if c.status == ContributionStatus.FAILED]

    print(f"\n{'=' * 60}")
    print("UNBLOCK COMPLETE")
    print(f"{'=' * 60}")
    print(f"  Status:     {rfp.status.value}")
    print(f"  FR:         {len(rfp.functional_requirements)}")
    print(f"  NFR:        {len(rfp.non_functional_requirements)}")
    print(f"  Constraints: {len(rfp.constraints)}")
    if still_failed:
        print(f"  Still failed: {len(still_failed)}")
        for c in still_failed:
            print(f"    - {c.president_name}: {c.failure_reason or 'unknown'}")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    main()
