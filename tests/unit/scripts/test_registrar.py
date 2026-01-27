from __future__ import annotations

import json
from pathlib import Path

from scripts.run_registrar import register_conclave


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def test_registrar_does_not_overwrite_existing_mandate(tmp_path: Path) -> None:
    conclave_results = {
        "schema_version": "1.0",
        "recorded_at": "2026-01-27T00:00:00Z",
        "session_id": "session-123",
        "session_name": "Conclave session",
        "passed_motions": [
            {
                "motion_id": "motion-1",
                "motion_type": "policy",
                "title": "Test Motion",
                "text": "WHEREAS ... BE IT RESOLVED ...",
                "vote_result": {
                    "ayes": 72,
                    "nays": 0,
                    "abstentions": 0,
                    "total_votes": 72,
                    "threshold": "supermajority",
                    "threshold_met": True,
                },
                "proposer": {"id": "archon-1", "name": "Paimon"},
                "seconder": {"id": "archon-2", "name": "Bael"},
            }
        ],
    }
    conclave_path = tmp_path / "conclave-results.json"
    _write_json(conclave_path, conclave_results)

    ledger_dir = tmp_path / "ledger"
    mandate_id = "mandate-existing"
    existing_mandate = {
        "mandate_id": mandate_id,
        "ledger_entry_id": "ledger-existing",
        "motion_id": "motion-1",
        "title": "Existing Title",
        "text": "Do not overwrite me",
        "session_id": "session-123",
    }
    _write_json(ledger_dir / "mandates" / f"{mandate_id}.json", existing_mandate)
    _write_json(
        ledger_dir / "ledger.json",
        {
            "schema_version": "1.0",
            "updated_at": "2026-01-27T00:00:00Z",
            "entries": [
                {
                    "mandate_id": mandate_id,
                    "ledger_entry_id": "ledger-existing",
                    "motion_id": "motion-1",
                    "session_id": "session-123",
                }
            ],
        },
    )

    ratified_path = register_conclave(conclave_path, ledger_dir)
    assert ratified_path.exists()

    mandate_path = ledger_dir / "mandates" / f"{mandate_id}.json"
    assert mandate_path.exists()
    assert json.loads(mandate_path.read_text(encoding="utf-8")) == existing_mandate
