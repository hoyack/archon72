#!/usr/bin/env python3
"""Award Pipeline.

Inputs:
- RFP output (run_rfp_generator.py)
- Duke proposals output (run_duke_proposals.py)

Outputs:
- award_decision.json
- administrative_handoff.json
- events jsonl

Notes:
- Gates are: traceability, feasibility, clarity, consentability.
- Peer review triggers are mechanical (cross-portfolio > 2,
  unresolved conflicts present, etc.).
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def save_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def append_event(events_path: Path, event: dict[str, Any]) -> None:
    events_path.parent.mkdir(parents=True, exist_ok=True)
    with events_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event) + "\n")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Award Pipeline - evaluate Duke proposals against RFP and award work"
    )
    p.add_argument(
        "--rfp",
        required=True,
        help="Path to rfp output json (implementation dossier)",
    )
    p.add_argument(
        "--proposals-dir",
        required=True,
        help="Directory containing duke proposals output",
    )
    p.add_argument("--out-dir", required=True, help="Output directory")
    p.add_argument(
        "--mode", choices=["auto", "llm", "manual"], default="auto"
    )
    p.add_argument("--verbose", action="store_true")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    out_dir = Path(args.out_dir)
    events_path = out_dir / "events.jsonl"

    append_event(
        events_path, {"type": "award.evaluation.started", "ts": utc_now()}
    )

    # TODO:
    # 1) load rfp
    # 2) load proposals
    # 3) compute rubric scores + gates
    # 4) enforce: any FAIL => no AWARD
    # 5) emit award_decision.json + administrative_handoff.json

    append_event(
        events_path,
        {"type": "award.evaluation.not_implemented", "ts": utc_now()},
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
