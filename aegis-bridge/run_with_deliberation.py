#!/usr/bin/env python3
"""Run Aegis Bridge batch and then deliberate each submitted petition.

This script:
1) Pulls latest pending petitions from Supabase (Aegis Bridge batch)
2) Submits them to Archon72
3) Runs scripts/run_petition_deliberation.py per successful submission
4) Extracts and prints the disposition for each deliberation

Processing is sequential (one petition at a time).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

# Ensure aegis-bridge src is importable even when run from repo root
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from src.clients.archon72 import Archon72Client  # noqa: E402
from src.clients.supabase import SupabaseClient  # noqa: E402
from src.config import load_config  # noqa: E402
from src.extractor import PetitionExtractor  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("aegis-bridge-deliberation")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Process pending petitions and run deliberations",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Dry run mode - don't submit to Archon72",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=None,
        help="Override batch size (default: from env or 100)",
    )
    parser.add_argument(
        "--force-deliberation",
        action="store_true",
        help="Force deliberation even if petition state is not RECEIVED",
    )
    return parser.parse_args()


def _find_latest_deliberation_file(repo_root: Path, petition_id: str) -> Path | None:
    output_dir = repo_root / "_bmad-output" / "petition-deliberations"
    pattern = f"petition-{petition_id}-session-*.json"
    matches = list(output_dir.glob(pattern))
    if not matches:
        return None
    return max(matches, key=lambda p: p.stat().st_mtime)


def _extract_disposition(payload: dict[str, Any]) -> str | None:
    deliberation = payload.get("deliberation", {})
    outcome = deliberation.get("outcome")
    if outcome:
        return outcome
    events = payload.get("events", {})
    return events.get("deliberation_complete", {}).get("outcome")


def _run_deliberation(repo_root: Path, petition_id: str, force: bool) -> str | None:
    script = repo_root / "scripts" / "run_petition_deliberation.py"
    cmd = [sys.executable, str(script), "--petition-id", petition_id]
    if force:
        cmd.append("--force")

    logger.info("Starting deliberation for petition %s", petition_id)
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        logger.error(
            "Deliberation failed for %s (exit=%s)\n%s",
            petition_id,
            result.returncode,
            result.stderr.strip(),
        )
        return None

    output_file = _find_latest_deliberation_file(repo_root, petition_id)
    if output_file is None:
        logger.error("No deliberation output file found for %s", petition_id)
        return None

    try:
        payload = output_file.read_text(encoding="utf-8")
        data = json.loads(payload)
    except Exception as exc:  # noqa: BLE001 - surface parsing issues
        logger.error("Failed to read deliberation output for %s: %s", petition_id, exc)
        return None

    disposition = _extract_disposition(data)
    logger.info(
        "Deliberation complete: petition=%s disposition=%s file=%s",
        petition_id,
        disposition,
        output_file,
    )
    return disposition


async def main() -> int:
    args = parse_args()

    # Override config via env to match main.py behavior
    if args.dry_run:
        os.environ["DRY_RUN"] = "true"
    if args.batch_size:
        os.environ["BATCH_SIZE"] = str(args.batch_size)

    try:
        config = load_config()
    except ValueError as exc:
        logger.error("Configuration error: %s", exc)
        return 1

    supabase = SupabaseClient(config.supabase)
    archon72 = Archon72Client(config.archon72)
    extractor = PetitionExtractor(supabase, archon72, config.processing)

    logger.info("Fetching latest petitions...")
    batch = await extractor.process_batch()
    if batch.total == 0:
        logger.info("No petitions to process")
        return 0

    repo_root = SCRIPT_DIR.parent

    # Process sequentially (one at a time)
    for result in batch.results:
        if not result.success or not result.archon72_petition_id:
            continue
        if config.processing.dry_run:
            logger.info(
                "[DRY RUN] Skipping deliberation for %s",
                result.archon72_petition_id,
            )
            continue
        _run_deliberation(
            repo_root, result.archon72_petition_id, args.force_deliberation
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
