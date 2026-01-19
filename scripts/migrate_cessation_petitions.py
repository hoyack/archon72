#!/usr/bin/env python3
"""Migrate Cessation Petitions (Story 0.3, AC6, FR-9.1).

This script migrates existing Story 7.2 cessation petitions to the new
petition_submissions schema while preserving petition IDs (FR-9.4).

Constitutional Constraints:
- CT-11: Silent failure destroys legitimacy → All migrations logged
- CT-12: Witnessing creates accountability → Audit trail created
- FR-9.1: System SHALL migrate Story 7.2 cessation_petition to CESSATION type
- FR-9.4: System SHALL preserve existing petition_id references

Usage:
    python scripts/migrate_cessation_petitions.py [--dry-run]

Options:
    --dry-run    Show what would be migrated without writing to database

Exit Codes:
    0 - Migration completed successfully
    1 - Migration failed (check logs)
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

# Add project root to path for imports
_project_root = Path(__file__).parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from structlog import get_logger

from src.domain.models.petition import Petition
from src.domain.models.petition_submission import PetitionSubmission
from src.infrastructure.adapters.petition_migration import (
    CESSATION_REALM,
    CessationPetitionAdapter,
)

logger = get_logger()


# =============================================================================
# Migration Result Tracking
# =============================================================================


@dataclass
class MigrationResult:
    """Result of a single petition migration."""

    petition_id: UUID
    success: bool
    error: str | None = None
    co_signer_count: int = 0


@dataclass
class MigrationReport:
    """Summary of migration operation."""

    started_at: datetime
    completed_at: datetime | None = None
    total_petitions: int = 0
    migrated: int = 0
    skipped: int = 0
    failed: int = 0
    results: list[MigrationResult] | None = None
    dry_run: bool = False

    def print_report(self) -> None:
        """Print migration report."""
        duration = (
            (self.completed_at - self.started_at).total_seconds()
            if self.completed_at
            else 0
        )

        print("\n" + "=" * 60)
        print("CESSATION PETITION MIGRATION REPORT")
        print("=" * 60 + "\n")

        mode = "DRY RUN" if self.dry_run else "LIVE"
        print(f"  Mode: {mode}")
        print(f"  Started: {self.started_at.isoformat()}")
        if self.completed_at:
            print(f"  Completed: {self.completed_at.isoformat()}")
            print(f"  Duration: {duration:.2f} seconds")

        print("\n  Results:")
        print(f"    Total petitions found: {self.total_petitions}")
        print(f"    Successfully migrated: {self.migrated}")
        print(f"    Skipped (already migrated): {self.skipped}")
        print(f"    Failed: {self.failed}")

        if self.failed > 0 and self.results:
            print("\n  Failures:")
            for result in self.results:
                if not result.success:
                    print(f"    - {result.petition_id}: {result.error}")

        print("\n" + "-" * 60)

        if self.failed == 0:
            print("[FR-9.1] MIGRATION COMPLETED SUCCESSFULLY")
        else:
            print("[FR-9.1] MIGRATION COMPLETED WITH ERRORS")

        print("-" * 60 + "\n")


# =============================================================================
# Database Operations (Placeholders for Production Implementation)
# =============================================================================


async def get_legacy_petitions() -> list[Petition]:
    """Fetch all cessation petitions from legacy system.

    In production, this would query the event store for all petition events
    and reconstruct Petition objects from the event stream.

    Returns:
        List of Petition objects from Story 7.2 system.

    Note:
        This is a placeholder. Production implementation should:
        1. Connect to event store
        2. Query all petition.created events
        3. Reconstruct Petition state from events
        4. Return list of Petition objects
    """
    logger.info("Fetching legacy petitions from event store")

    # TODO: Implement actual event store query
    # For now, return empty list as this requires production infrastructure
    return []


async def check_already_migrated(petition_id: UUID) -> bool:
    """Check if a petition has already been migrated.

    Args:
        petition_id: The legacy petition ID to check.

    Returns:
        True if already in petition_migration_mapping table.

    Note:
        Production implementation should query petition_migration_mapping table.
    """
    logger.debug("Checking migration status", petition_id=str(petition_id))

    # TODO: Implement database query
    # SELECT 1 FROM petition_migration_mapping WHERE legacy_petition_id = ?
    return False


async def insert_petition_submission(submission: PetitionSubmission) -> None:
    """Insert a new petition submission into the database.

    Args:
        submission: The PetitionSubmission to insert.

    Note:
        Production implementation should use proper database connection.
    """
    logger.info(
        "Inserting petition submission",
        id=str(submission.id),
        type=submission.type.value,
        state=submission.state.value,
        realm=submission.realm,
    )

    # TODO: Implement database insert
    # INSERT INTO petition_submissions (id, type, text, state, ...) VALUES (?, ?, ?, ?, ...)


async def insert_migration_mapping(
    legacy_id: UUID,
    new_id: UUID,
    co_signer_count: int,
) -> None:
    """Record the migration in the mapping table.

    Args:
        legacy_id: Original Story 7.2 petition ID.
        new_id: New petition submission ID (same value per FR-9.4).
        co_signer_count: Number of co-signers at migration time.

    Note:
        Production implementation should use proper database connection.
    """
    logger.info(
        "Recording migration mapping",
        legacy_id=str(legacy_id),
        new_id=str(new_id),
        co_signer_count=co_signer_count,
    )

    # TODO: Implement database insert
    # INSERT INTO petition_migration_mapping (legacy_petition_id, new_submission_id, co_signer_count)
    # VALUES (?, ?, ?)


# =============================================================================
# Migration Logic
# =============================================================================


async def migrate_single_petition(
    petition: Petition,
    dry_run: bool = False,
) -> MigrationResult:
    """Migrate a single petition from Story 7.2 to Story 0.2 schema.

    Args:
        petition: The Story 7.2 Petition to migrate.
        dry_run: If True, don't write to database.

    Returns:
        MigrationResult with success status and details.
    """
    try:
        # Check if already migrated
        if await check_already_migrated(petition.petition_id):
            logger.info(
                "Petition already migrated, skipping",
                petition_id=str(petition.petition_id),
            )
            return MigrationResult(
                petition_id=petition.petition_id,
                success=True,
                error="Already migrated",
                co_signer_count=petition.cosigner_count,
            )

        # Convert to new schema using adapter (FR-9.4: ID preserved)
        submission = CessationPetitionAdapter.to_submission(petition)

        # Verify ID preservation (FR-9.4 critical check)
        if submission.id != petition.petition_id:
            raise ValueError(
                f"FR-9.4 VIOLATION: ID not preserved. "
                f"Legacy: {petition.petition_id}, New: {submission.id}"
            )

        # Verify realm is cessation-realm
        if submission.realm != CESSATION_REALM:
            raise ValueError(
                f"Realm not set correctly. Expected: {CESSATION_REALM}, "
                f"Got: {submission.realm}"
            )

        logger.info(
            "Converted petition",
            petition_id=str(petition.petition_id),
            new_state=submission.state.value,
            co_signer_count=petition.cosigner_count,
            dry_run=dry_run,
        )

        if not dry_run:
            # Insert into petition_submissions
            await insert_petition_submission(submission)

            # Record in mapping table
            await insert_migration_mapping(
                legacy_id=petition.petition_id,
                new_id=submission.id,  # Same value per FR-9.4
                co_signer_count=petition.cosigner_count,
            )

        return MigrationResult(
            petition_id=petition.petition_id,
            success=True,
            co_signer_count=petition.cosigner_count,
        )

    except Exception as e:
        logger.error(
            "Migration failed for petition",
            petition_id=str(petition.petition_id),
            error=str(e),
        )
        return MigrationResult(
            petition_id=petition.petition_id,
            success=False,
            error=str(e),
            co_signer_count=petition.cosigner_count,
        )


async def run_migration(dry_run: bool = False) -> MigrationReport:
    """Run the full migration process.

    Args:
        dry_run: If True, don't write to database.

    Returns:
        MigrationReport with results summary.
    """
    report = MigrationReport(
        started_at=datetime.now(timezone.utc),
        results=[],
        dry_run=dry_run,
    )

    logger.info(
        "Starting cessation petition migration",
        dry_run=dry_run,
    )

    try:
        # Fetch all legacy petitions
        petitions = await get_legacy_petitions()
        report.total_petitions = len(petitions)

        logger.info(
            "Found petitions to migrate",
            count=report.total_petitions,
        )

        # Migrate each petition
        for petition in petitions:
            result = await migrate_single_petition(petition, dry_run=dry_run)
            report.results.append(result)

            if result.success and result.error == "Already migrated":
                report.skipped += 1
            elif result.success:
                report.migrated += 1
            else:
                report.failed += 1

        report.completed_at = datetime.now(timezone.utc)

        logger.info(
            "Migration completed",
            total=report.total_petitions,
            migrated=report.migrated,
            skipped=report.skipped,
            failed=report.failed,
        )

    except Exception as e:
        report.completed_at = datetime.now(timezone.utc)
        logger.error("Migration failed", error=str(e))
        raise

    return report


# =============================================================================
# Main
# =============================================================================


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Migrate Story 7.2 cessation petitions to Story 0.2 schema",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be migrated without writing to database",
    )
    return parser.parse_args()


async def main() -> int:
    """Run the migration and return exit code."""
    args = parse_args()

    print("[FR-9.1] Starting cessation petition migration...")
    if args.dry_run:
        print("  (DRY RUN - no database writes will occur)")

    try:
        report = await run_migration(dry_run=args.dry_run)
        report.print_report()

        return 0 if report.failed == 0 else 1

    except Exception as e:
        logger.error("Migration failed with exception", error=str(e))
        print(f"\n[ERROR] Migration failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
