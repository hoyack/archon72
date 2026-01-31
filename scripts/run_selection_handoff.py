#!/usr/bin/env python3
"""Generate an Administrative Handoff from a Proposal Selection result.

Bridges the gap between Executive (Proposal Selection) and Administrative
(Execution). Reads the selection result and winning Duke proposal, then
produces an administrative_handoff.json conforming to the handoff schema.

Pipeline Position:
    run_proposal_selection.py  ->  run_selection_handoff.py  <- THIS
      ->  run_administrative_pipeline.py

Usage:
    python scripts/run_selection_handoff.py
    python scripts/run_selection_handoff.py --from-rfp-session <path>
    python scripts/run_selection_handoff.py --dry-run -v
"""

from __future__ import annotations

import argparse
import glob
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()


def _save_json(path: Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2)


def _append_event(path: Path, event: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(event) + "\n")


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


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


def _find_mandate_dir(session_dir: Path, mandate_id: str | None = None) -> Path | None:
    """Find a mandate directory within a session."""
    mandates_dir = session_dir / "mandates"
    if not mandates_dir.exists():
        return session_dir if (session_dir / "rfp.json").exists() else None

    mandate_dirs = sorted(mandates_dir.iterdir())
    if mandate_id:
        for md in mandate_dirs:
            if md.is_dir() and mandate_id in md.name:
                return md
        return None

    for md in mandate_dirs:
        if md.is_dir():
            return md

    return None


# ------------------------------------------------------------------
# Load artifacts
# ------------------------------------------------------------------


def _load_selection_result(mandate_dir: Path) -> dict:
    """Load selection_result.json from the selection/ directory."""
    sel_path = mandate_dir / "selection" / "selection_result.json"
    if not sel_path.exists():
        print(f"Error: No selection_result.json found at {sel_path}")
        print("Run run_proposal_selection.py first.")
        sys.exit(1)
    with open(sel_path, encoding="utf-8") as f:
        return json.load(f)


def _load_rfp(mandate_dir: Path) -> dict:
    """Load rfp.json from the mandate directory."""
    rfp_path = mandate_dir / "rfp.json"
    if not rfp_path.exists():
        print(f"Error: No rfp.json found at {rfp_path}")
        sys.exit(1)
    with open(rfp_path, encoding="utf-8") as f:
        return json.load(f)


def _load_winning_proposal(
    mandate_dir: Path, winning_proposal_id: str
) -> tuple[dict, str]:
    """Load the winning Duke proposal JSON and markdown.

    Returns:
        Tuple of (proposal_json_dict, proposal_markdown_str)
    """
    inbox = mandate_dir / "proposals_inbox"
    if not inbox.exists():
        print(f"Error: No proposals_inbox found at {inbox}")
        sys.exit(1)

    # Find the proposal file matching the winning ID
    for json_path in sorted(inbox.glob("proposal_*.json")):
        if json_path.name == "proposal_summary.json":
            continue
        with open(json_path, encoding="utf-8") as f:
            data = json.load(f)
        if data.get("proposal_id") == winning_proposal_id:
            # Load companion markdown
            md_path = json_path.with_suffix(".md")
            markdown = ""
            if md_path.exists():
                markdown = md_path.read_text(encoding="utf-8")
            return data, markdown

    print(f"Error: Winning proposal {winning_proposal_id} not found in {inbox}")
    sys.exit(1)


# ------------------------------------------------------------------
# Extract deliverables from RFP
# ------------------------------------------------------------------


def _extract_deliverables(rfp: dict) -> list[dict]:
    """Extract deliverables from RFP, mapping to handoff schema format.

    Each deliverable gets an id, title, and acceptance_criteria list.
    """
    deliverables = []
    rfp_deliverables = rfp.get("deliverables", [])

    if not rfp_deliverables:
        # Fallback: single deliverable from scope
        sow = rfp.get("scope_of_work", {})
        deliverables.append(
            {
                "id": "del-001",
                "title": "Implementation per RFP scope",
                "acceptance_criteria": sow.get("success_criteria", [])
                or ["Implementation meets all RFP requirements"],
            }
        )
        return deliverables

    for dl in rfp_deliverables:
        del_id = dl.get("deliverable_id", f"del-{uuid4().hex[:8]}")
        name = dl.get("name", "Unnamed deliverable")
        description = dl.get("description", "")

        # Build acceptance criteria from description and any explicit criteria
        criteria = dl.get("acceptance_criteria", [])
        if not criteria and description:
            criteria = [description]
        if not criteria:
            criteria = [f"Deliverable '{name}' produced and verified"]

        # Ensure criteria are strings
        criteria = [str(c) for c in criteria if c]

        deliverables.append(
            {
                "id": del_id,
                "title": name,
                "acceptance_criteria": criteria,
            }
        )

    return deliverables


# ------------------------------------------------------------------
# Extract constraints from RFP
# ------------------------------------------------------------------


def _extract_exclusions(rfp: dict) -> list[str]:
    """Extract explicit exclusions from RFP constraints and scope."""
    exclusions = []

    # From scope_of_work.out_of_scope
    sow = rfp.get("scope_of_work", {})
    for item in sow.get("out_of_scope", []):
        if isinstance(item, str):
            exclusions.append(item)
        elif isinstance(item, dict):
            exclusions.append(item.get("description", str(item)))

    # From constraints marked as exclusions
    for c in rfp.get("constraints", []):
        if isinstance(c, dict):
            desc = c.get("description", "")
            if "shall not" in desc.lower() or "must not" in desc.lower():
                exclusions.append(desc)

    return exclusions


# ------------------------------------------------------------------
# Extract portfolio context
# ------------------------------------------------------------------


def _extract_portfolios(rfp: dict) -> list[str]:
    """Extract portfolio keys from RFP contributions.

    Maps portfolio IDs to routing-compatible keys used by
    earl_routing_table.json.
    """
    portfolio_ids = []
    for pc in rfp.get("portfolio_contributions", []):
        portfolio = pc.get("portfolio", {})
        pid = portfolio.get("portfolio_id", "")
        if pid:
            # Convert portfolio_adversarial_risk_security -> adversarial_risk_security
            key = re.sub(r"^portfolio_", "", pid)
            portfolio_ids.append(key)

    return portfolio_ids or ["transformation"]


# ------------------------------------------------------------------
# Build handoff
# ------------------------------------------------------------------


def build_handoff(
    selection_result: dict,
    rfp: dict,
    proposal_json: dict,
    proposal_markdown: str,
    deadline_hours: int = 168,
) -> dict:
    """Build the administrative_handoff.json artifact.

    Args:
        selection_result: The selection_result.json content
        rfp: The rfp.json content
        proposal_json: The winning proposal JSON metadata
        proposal_markdown: The winning proposal markdown body
        deadline_hours: Hours until work deadline (default: 168 = 7 days)

    Returns:
        Dict conforming to administrative_handoff.schema.json
    """
    now = _utc_now()
    winning_id = selection_result["winning_proposal_id"]
    mandate_id = rfp.get("mandate_id", selection_result.get("mandate_id", ""))
    rfp_id = rfp.get("implementation_dossier_id", selection_result.get("rfp_id", ""))
    session_id = rfp.get("session_id", "")

    # Get motion title from RFP background
    background = rfp.get("background", {})
    motion_title = background.get("motion_title", "")

    # Duke info
    duke = proposal_json.get("duke", {})
    duke_id = duke.get("archon_id", proposal_json.get("duke_archon_id", ""))
    duke_name = duke.get("name", proposal_json.get("duke_name", ""))

    # Build award ID
    award_id = f"award-{uuid4().hex[:12]}"

    # Build work package
    deliverables = _extract_deliverables(rfp)
    exclusions = _extract_exclusions(rfp)
    portfolios = _extract_portfolios(rfp)

    deadline = (datetime.now(timezone.utc) + timedelta(hours=deadline_hours)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )

    # Build summary from proposal executive summary
    summary = ""
    if proposal_markdown:
        # Extract executive summary section
        lines = proposal_markdown.split("\n")
        in_summary = False
        summary_lines = []
        for line in lines:
            if "executive summary" in line.lower() and line.startswith("#"):
                in_summary = True
                continue
            if in_summary and line.startswith("#"):
                break
            if in_summary:
                summary_lines.append(line)
        summary = "\n".join(summary_lines).strip()

    if not summary:
        summary = (
            f"Implementation of '{motion_title}' as proposed by Duke "
            f"{duke_name} (proposal {winning_id})."
        )

    # Truncate summary to reasonable length
    if len(summary) > 2000:
        summary = summary[:1997] + "..."

    # Ensure proposal_id matches schema pattern (proposal-*)
    # Selection uses dprop-* format, schema expects proposal-*
    schema_proposal_id = winning_id
    if winning_id.startswith("dprop-"):
        schema_proposal_id = "proposal-" + winning_id[6:]

    # Ensure rfp_id matches schema pattern (rfp-*)
    schema_rfp_id = rfp_id
    if not rfp_id.startswith("rfp-"):
        schema_rfp_id = "rfp-" + rfp_id.replace("eid-", "")

    # Ensure motion_id matches schema pattern (motion-*)
    motion_id = background.get("motion_id", "")
    if not motion_id:
        motion_id = f"motion-{mandate_id.replace('mandate-', '')}"

    handoff = {
        "schema_version": "1.0",
        "handoff_id": f"handoff-{uuid4().hex[:12]}",
        "created_at": now,
        "references": {
            "session_id": session_id or f"session-{uuid4().hex[:8]}",
            "mandate_id": mandate_id,
            "motion_id": motion_id,
            "rfp_id": schema_rfp_id,
            "award_id": award_id,
            "selected_duke_id": duke_id or duke_name,
            "selected_proposal_id": schema_proposal_id,
        },
        "work_package": {
            "title": motion_title or f"Execution of proposal {winning_id}",
            "summary": summary,
            "deliverables": deliverables,
            "constraints": {
                "deadline_iso": deadline,
                "budget_cap": {
                    "amount": 0,
                    "currency": "USD",
                },
                "explicit_exclusions": exclusions,
            },
        },
        "portfolio_context": {
            "portfolios": portfolios,
            "portfolios_involved_count": len(portfolios),
        },
        "admin_directives": {
            "require_task_contracts": True,
            "require_result_artifacts": True,
            "escalation_policy_id": "default-escalation-v1",
        },
    }

    return handoff


# ------------------------------------------------------------------
# Schema validation
# ------------------------------------------------------------------


def _validate_id_patterns(handoff: dict, refs: dict) -> list[str]:
    """Validate ID fields match their expected patterns."""
    errors = []
    patterns = {
        "handoff_id": r"^handoff-[a-zA-Z0-9\-]+$",
        "mandate_id": r"^mandate-[a-zA-Z0-9\-]+$",
        "motion_id": r"^motion-[a-zA-Z0-9\-]+$",
        "rfp_id": r"^rfp-[a-zA-Z0-9\-]+$",
        "award_id": r"^award-[a-zA-Z0-9\-]+$",
        "selected_proposal_id": r"^proposal-[a-zA-Z0-9\-]+$",
    }
    for field, pattern in patterns.items():
        value = handoff.get(field) or refs.get(field, "")
        if value and not re.match(pattern, value):
            errors.append(f"{field} '{value}' does not match pattern {pattern}")
    return errors


def _validate_handoff(handoff: dict) -> list[str]:
    """Validate handoff against schema requirements.

    Returns list of validation errors (empty = valid).
    """
    errors = []

    # Check required top-level keys
    required = [
        "schema_version",
        "handoff_id",
        "created_at",
        "references",
        "work_package",
        "portfolio_context",
        "admin_directives",
    ]
    for key in required:
        if key not in handoff:
            errors.append(f"Missing required key: {key}")

    # Check references
    refs = handoff.get("references", {})
    ref_required = [
        "session_id",
        "mandate_id",
        "motion_id",
        "rfp_id",
        "award_id",
        "selected_duke_id",
        "selected_proposal_id",
    ]
    for key in ref_required:
        if not refs.get(key):
            errors.append(f"Missing or empty references.{key}")

    # Check ID patterns
    errors.extend(_validate_id_patterns(handoff, refs))

    # Check work_package
    wp = handoff.get("work_package", {})
    if not wp.get("title"):
        errors.append("Missing work_package.title")
    if not wp.get("summary"):
        errors.append("Missing work_package.summary")
    if not wp.get("deliverables"):
        errors.append("Missing work_package.deliverables")
    else:
        for i, dl in enumerate(wp["deliverables"]):
            if not dl.get("id"):
                errors.append(f"deliverables[{i}] missing id")
            if not dl.get("title"):
                errors.append(f"deliverables[{i}] missing title")
            if not dl.get("acceptance_criteria"):
                errors.append(f"deliverables[{i}] missing acceptance_criteria")

    # Check portfolio_context
    pc = handoff.get("portfolio_context", {})
    if not pc.get("portfolios"):
        errors.append("Missing portfolio_context.portfolios")
    if not pc.get("portfolios_involved_count"):
        errors.append("Missing portfolio_context.portfolios_involved_count")

    return errors


# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate Administrative Handoff from Selection Result"
    )
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
        "--deadline-hours",
        type=int,
        default=168,
        help="Hours until work deadline (default: 168 = 7 days)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and print handoff without writing files",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    # ------------------------------------------------------------------
    # Resolve session
    # ------------------------------------------------------------------
    session_dir: Path | None = None
    if args.from_rfp_session:
        session_dir = args.from_rfp_session
        if not session_dir.exists():
            print(f"Error: Session directory not found: {session_dir}")
            return 1
        print(f"Using RFP session: {session_dir}")
    else:
        session_dir = _find_latest_rfp_session()
        if session_dir is None:
            print("Error: No RFP session found.")
            print("Looking for: _bmad-output/rfp/*/")
            return 1
        print(f"Auto-detected RFP session: {session_dir}")

    mandate_dir = _find_mandate_dir(session_dir, args.mandate_id)
    if mandate_dir is None:
        print(f"Error: No mandate directory found in {session_dir}")
        return 1
    print(f"Mandate directory: {mandate_dir}")

    # ------------------------------------------------------------------
    # Load artifacts
    # ------------------------------------------------------------------
    selection_result = _load_selection_result(mandate_dir)
    rfp = _load_rfp(mandate_dir)

    outcome = selection_result.get("outcome")
    if outcome != "WINNER_SELECTED":
        print(f"Error: Selection outcome is '{outcome}', not WINNER_SELECTED")
        print("Cannot create handoff without a winning proposal.")
        return 1

    winning_id = selection_result["winning_proposal_id"]
    print(f"\nSelection outcome: {outcome}")
    print(f"Winning proposal: {winning_id}")

    proposal_json, proposal_markdown = _load_winning_proposal(mandate_dir, winning_id)
    duke = proposal_json.get("duke", {})
    duke_name = duke.get("name", proposal_json.get("duke_name", "Unknown"))
    print(f"Winning Duke: {duke_name}")

    # ------------------------------------------------------------------
    # Build handoff
    # ------------------------------------------------------------------
    handoff = build_handoff(
        selection_result=selection_result,
        rfp=rfp,
        proposal_json=proposal_json,
        proposal_markdown=proposal_markdown,
        deadline_hours=args.deadline_hours,
    )

    # ------------------------------------------------------------------
    # Validate
    # ------------------------------------------------------------------
    errors = _validate_handoff(handoff)
    if errors:
        print(f"\nValidation errors ({len(errors)}):")
        for err in errors:
            print(f"  - {err}")
        return 1

    print("\nHandoff validation: PASSED")

    if args.verbose:
        refs = handoff["references"]
        wp = handoff["work_package"]
        pc = handoff["portfolio_context"]
        print(f"\n  Handoff ID: {handoff['handoff_id']}")
        print(f"  Award ID: {refs['award_id']}")
        print(f"  Duke: {refs['selected_duke_id']}")
        print(f"  Proposal: {refs['selected_proposal_id']}")
        print(f"  Deliverables: {len(wp['deliverables'])}")
        for dl in wp["deliverables"]:
            print(f"    - {dl['id']}: {dl['title']}")
        print(f"  Exclusions: {len(wp['constraints']['explicit_exclusions'])}")
        print(f"  Portfolios: {pc['portfolios_involved_count']}")
        for p in pc["portfolios"]:
            print(f"    - {p}")
        print(f"  Deadline: {wp['constraints']['deadline_iso']}")

    # ------------------------------------------------------------------
    # Write output
    # ------------------------------------------------------------------
    if args.dry_run:
        print("\n[DRY RUN] Handoff validated but not written.")
        print(json.dumps(handoff, indent=2))
        return 0

    handoff_dir = mandate_dir / "handoff"
    handoff_path = handoff_dir / "administrative_handoff.json"
    events_path = handoff_dir / "handoff_events.jsonl"

    _save_json(handoff_path, handoff)
    _append_event(
        events_path,
        {
            "type": "handoff.created",
            "ts": _utc_now(),
            "handoff_id": handoff["handoff_id"],
            "winning_proposal_id": winning_id,
            "duke_name": duke_name,
            "deliverable_count": len(handoff["work_package"]["deliverables"]),
        },
    )

    print(f"\nHandoff written to: {handoff_path}")
    print(f"Events written to: {events_path}")

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    print(f"\n{'=' * 60}")
    print("SELECTION HANDOFF COMPLETE")
    print(f"{'=' * 60}")
    print(f"Handoff ID: {handoff['handoff_id']}")
    print(f"Award ID: {handoff['references']['award_id']}")
    print(f"Winner: {duke_name} ({winning_id})")
    print(f"Deliverables: {len(handoff['work_package']['deliverables'])}")
    print(f"Portfolios: {handoff['portfolio_context']['portfolios_involved_count']}")
    print(f"Output: {handoff_dir}")
    print(f"{'=' * 60}")

    # ------------------------------------------------------------------
    # Next step hint
    # ------------------------------------------------------------------
    print("\nNext step:")
    print("  python scripts/run_administrative_pipeline.py \\")
    print(f"    --handoff {handoff_path} \\")
    print("    --earl-routing configs/admin/earl_routing_table.json \\")
    print("    --tool-registry configs/tools/tool_registry.json \\")
    print(f"    --out-dir {mandate_dir / 'execution'} \\")
    print("    -v")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
