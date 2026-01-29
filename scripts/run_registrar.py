#!/usr/bin/env python3
"""Registrar: record passed Conclave motions into the motion ledger."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _save_json(path: Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2)


def _extract_session_id_from_transcript(path: Path) -> str | None:
    match = re.search(r"transcript-([0-9a-f-]{36})-", path.name)
    if not match:
        return None
    return match.group(1)


def _find_latest(path: Path, pattern: str) -> Path | None:
    matches = list(path.glob(pattern))
    if not matches:
        return None
    return max(matches, key=lambda p: p.stat().st_mtime)


def resolve_conclave_source(path: Path) -> Path:
    if path.is_file():
        if path.suffix == ".json":
            return path
        if path.suffix == ".md":
            session_id = _extract_session_id_from_transcript(path)
            if not session_id:
                raise ValueError(f"Could not parse session_id from {path}")
            candidate = _find_latest(
                path.parent, f"conclave-results-{session_id}-*.json"
            )
            if candidate:
                return candidate
            raise ValueError(
                "Conclave results not found. Re-run Conclave to emit "
                "conclave-results-<session_id>-*.json"
            )
        raise ValueError(f"Unsupported file type: {path}")

    if path.is_dir():
        candidate = _find_latest(path, "conclave-results-*.json")
        if candidate:
            return candidate
        candidate = _find_latest(path, "checkpoint-*.json")
        if candidate:
            return candidate
        raise ValueError(f"No conclave-results or checkpoint files found in {path}")

    raise ValueError(f"Path not found: {path}")


def _build_results_from_checkpoint(data: dict) -> dict:
    motions: list[dict] = []
    passed: list[dict] = []
    failed: list[dict] = []
    died_no_second: list[dict] = []
    other: list[dict] = []

    for motion in data.get("motions", []):
        ayes = motion.get("final_ayes") or 0
        nays = motion.get("final_nays") or 0
        abstentions = motion.get("final_abstentions") or 0
        status = motion.get("status", "")
        record = {
            "motion_id": motion.get("motion_id"),
            "motion_type": motion.get("motion_type"),
            "title": motion.get("title"),
            "text": motion.get("text"),
            "status": status,
            "proposer": {
                "id": motion.get("proposer_id"),
                "name": motion.get("proposer_name"),
            },
            "seconder": {
                "id": motion.get("seconder_id"),
                "name": motion.get("seconder_name"),
            },
            "proposed_at": motion.get("proposed_at"),
            "seconded_at": motion.get("seconded_at"),
            "vote_result": {
                "ayes": ayes,
                "nays": nays,
                "abstentions": abstentions,
                "total_votes": ayes + nays + abstentions,
                "threshold": "supermajority",
                "threshold_met": status == "passed",
            },
        }
        motions.append(record)

        if status == "passed":
            passed.append(record)
        elif status == "failed":
            failed.append(record)
        elif motion.get("seconder_id") is None and status == "proposed":
            died_no_second.append(record)
        else:
            other.append(record)

    return {
        "schema_version": "1.0",
        "recorded_at": now_iso(),
        "session_id": data.get("session_id"),
        "session_name": data.get("session_name"),
        "motions": motions,
        "passed_motions": passed,
        "failed_motions": failed,
        "died_no_second": died_no_second,
        "other_motions": other,
    }


def load_conclave_results(path: Path) -> tuple[dict, Path]:
    data = _load_json(path)
    if "passed_motions" in data and "session_id" in data:
        return data, path
    if "motions" in data and "session_id" in data and "transcript" in data:
        results = _build_results_from_checkpoint(data)
        return results, path
    raise ValueError(f"Unrecognized conclave data format: {path}")


def load_ledger(ledger_path: Path) -> dict:
    if ledger_path.exists():
        return _load_json(ledger_path)
    return {"schema_version": "1.0", "updated_at": now_iso(), "entries": []}


def register_conclave(conclave_path: Path, outdir: Path) -> Path:
    source_path = resolve_conclave_source(conclave_path)
    results, results_source = load_conclave_results(source_path)

    session_id = results.get("session_id") or "unknown-session"
    session_name = results.get("session_name") or ""

    mandates = []
    source_artifacts = [
        {
            "name": "conclave_results",
            "path": str(results_source),
            "sha256": _sha256_file(results_source),
        }
    ]

    ledger_dir = outdir
    ledger_dir.mkdir(parents=True, exist_ok=True)
    ledger_path = ledger_dir / "ledger.json"
    ledger = load_ledger(ledger_path)
    existing = {
        (e.get("session_id"), e.get("motion_id")): e for e in ledger.get("entries", [])
    }

    for motion in results.get("passed_motions", []):
        key = (session_id, motion.get("motion_id"))
        prior = existing.get(key)
        mandate_id = prior.get("mandate_id") if prior else f"mandate-{uuid4()}"
        ledger_entry_id = prior.get("ledger_entry_id") if prior else f"ledger-{uuid4()}"

        mandate_path = ledger_dir / "mandates" / f"{mandate_id}.json"
        if mandate_path.exists():
            mandate = _load_json(mandate_path)
        else:
            mandate = {
                "mandate_id": mandate_id,
                "ledger_entry_id": ledger_entry_id,
                "motion_id": motion.get("motion_id"),
                "title": motion.get("title"),
                "text": motion.get("text"),
                "motion_type": motion.get("motion_type"),
                "passed_at": results.get("recorded_at"),
                "session_id": session_id,
                "session_name": session_name,
                "vote_result": motion.get("vote_result", {}),
                "proposer": motion.get("proposer", {}),
                "seconder": motion.get("seconder", {}),
                "source_artifacts": source_artifacts,
            }
            _save_json(mandate_path, mandate)

        mandates.append(mandate)

        if not prior:
            ledger.setdefault("entries", []).append(mandate)

    ledger["updated_at"] = now_iso()
    _save_json(ledger_path, ledger)

    session_dir = ledger_dir / session_id
    ratified_output = {
        "schema_version": "1.0",
        "recorded_at": now_iso(),
        "conclave_session_id": session_id,
        "conclave_session_name": session_name,
        "source_artifacts": source_artifacts,
        "mandates": mandates,
        "failed_motions": results.get("failed_motions", []),
        "died_no_second": results.get("died_no_second", []),
    }
    ratified_path = session_dir / "ratified_mandates.json"
    _save_json(ratified_path, ratified_output)

    return ratified_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Record passed Conclave motions into the motion ledger"
    )
    parser.add_argument(
        "conclave_path",
        type=Path,
        help="Path to conclave results JSON, checkpoint, transcript, or output directory",
    )
    parser.add_argument(
        "--outdir",
        type=Path,
        default=Path("_bmad-output/motion-ledger"),
        help="Base output directory for the motion ledger",
    )
    args = parser.parse_args()

    ratified_path = register_conclave(args.conclave_path, args.outdir)

    print("REGISTRAR COMPLETE")
    print(f"Session: {ratified_path.parent.name}")
    print(f"Ledger: {args.outdir / 'ledger.json'}")
    print(f"Session output: {ratified_path}")


if __name__ == "__main__":
    main()
