#!/usr/bin/env python3
"""Rollback Cessation Petition Migration (Story 0.3, AC6).

This script rolls back the migration of Story 7.2 cessation petitions,
removing data from petition_submissions and petition_migration_mapping tables.

Constitutional Constraints:
- CT-11: Silent failure destroys legitimacy → All rollbacks logged
- CT-12: Witnessing creates accountability → Audit trail maintained

CAUTION: This script deletes data. Use with care.

Usage:
    python scripts/rollback_cessation_migration.py [--dry-run] [--confirm]

Options:
    --dry-run    Show what would be rolled back without deleting
    --confirm    Required for actual rollback (safety measure)

Exit Codes:
    0 - Rollback completed successfully
    1 - Rollback failed (check logs)
    2 - Missing --confirm flag for non-dry-run
"""

from __future__ import annotations

import argparse
import asyncio
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

logger = get_logger()


# =============================================================================
# Rollback Result Tracking
# =============================================================================


@dataclass
class RollbackResult:
    """Result of rollback operation."""

    submission_id: UUID
    success: bool
    error: str | None = None


@dataclass
class RollbackReport:
    """Summary of rollback operation."""

    started_at: datetime
    completed_at: datetime | None = None
    total_mappings: int = 0
    submissions_deleted: int = 0
    mappings_deleted: int = 0
    failed: int = 0
    dry_run: bool = False

    def print_report(self) -> None:
        """Print rollback report."""
        duration = (
            (self.completed_at - self.started_at).total_seconds()
            if self.completed_at
            else 0
        )

        print("\n" + "=" * 60)
        print("CESSATION PETITION ROLLBACK REPORT")
        print("=" * 60 + "\n")

        mode = "DRY RUN" if self.dry_run else "LIVE"
        print(f"  Mode: {mode}")
        print(f"  Started: {self.started_at.isoformat()}")
        if self.completed_at:
            print(f"  Completed: {self.completed_at.isoformat()}")
            print(f"  Duration: {duration:.2f} seconds")

        print("\n  Results:")
        print(f"    Migration mappings found: {self.total_mappings}")
        print(f"    Petition submissions deleted: {self.submissions_deleted}")
        print(f"    Migration mappings deleted: {self.mappings_deleted}")
        print(f"    Failed: {self.failed}")

        print("\n" + "-" * 60)

        if self.failed == 0:
            print("[AC6] ROLLBACK COMPLETED SUCCESSFULLY")
        else:
            print("[AC6] ROLLBACK COMPLETED WITH ERRORS")

        print("-" * 60 + "\n")


# =============================================================================
# Database Operations (Placeholders for Production Implementation)
# =============================================================================


@dataclass
class MigrationMapping:
    """A record from petition_migration_mapping table."""

    legacy_petition_id: UUID
    new_submission_id: UUID
    migrated_at: datetime
    co_signer_count: int


async def get_all_migration_mappings() -> list[MigrationMapping]:
    """Fetch all migration mappings from database.

    Returns:
        List of MigrationMapping records.

    Note:
        Production implementation should query petition_migration_mapping table.
    """
    logger.info("Fetching all migration mappings")

    # TODO: Implement database query
    # SELECT legacy_petition_id, new_submission_id, migrated_at, co_signer_count
    # FROM petition_migration_mapping
    return []


async def delete_petition_submission(submission_id: UUID) -> bool:
    """Delete a petition submission from database.

    Args:
        submission_id: The submission ID to delete.

    Returns:
        True if deleted successfully.

    Note:
        Production implementation should use proper database connection.
        The CASCADE on FK should handle mapping table cleanup, but we
        do explicit delete for auditability.
    """
    logger.info(
        "Deleting petition submission",
        submission_id=str(submission_id),
    )

    # TODO: Implement database delete
    # DELETE FROM petition_submissions WHERE id = ?
    return True


async def delete_migration_mapping(legacy_id: UUID) -> bool:
    """Delete a migration mapping from database.

    Args:
        legacy_id: The legacy petition ID to delete mapping for.

    Returns:
        True if deleted successfully.

    Note:
        Production implementation should use proper database connection.
    """
    logger.info(
        "Deleting migration mapping",
        legacy_petition_id=str(legacy_id),
    )

    # TODO: Implement database delete
    # DELETE FROM petition_migration_mapping WHERE legacy_petition_id = ?
    return True


async def delete_submissions_by_mapping() -> int:
    """Delete all petition submissions that were created by migration.

    This uses a single query for efficiency:
    DELETE FROM petition_submissions
    WHERE id IN (SELECT new_submission_id FROM petition_migration_mapping)

    Returns:
        Number of rows deleted.

    Note:
        Production implementation should use proper database connection.
    """
    logger.info("Deleting all migrated petition submissions")

    # TODO: Implement database delete
    # DELETE FROM petition_submissions
    # WHERE id IN (SELECT new_submission_id FROM petition_migration_mapping)
    return 0


async def delete_all_migration_mappings() -> int:
    """Delete all migration mappings.

    Returns:
        Number of rows deleted.

    Note:
        Production implementation should use proper database connection.
    """
    logger.info("Deleting all migration mappings")

    # TODO: Implement database delete
    # DELETE FROM petition_migration_mapping
    return 0


# =============================================================================
# Rollback Logic
# =============================================================================


async def run_rollback(dry_run: bool = False) -> RollbackReport:
    """Run the full rollback process.

    The rollback:
    1. Fetches all migration mappings
    2. Deletes corresponding petition_submissions
    3. Deletes migration mappings
    4. Reports results

    Args:
        dry_run: If True, don't delete from database.

    Returns:
        RollbackReport with results summary.
    """
    report = RollbackReport(
        started_at=datetime.now(timezone.utc),
        dry_run=dry_run,
    )

    logger.info(
        "Starting cessation petition rollback",
        dry_run=dry_run,
    )

    try:
        # Fetch all mappings first to know what to delete
        mappings = await get_all_migration_mappings()
        report.total_mappings = len(mappings)

        logger.info(
            "Found migration mappings to rollback",
            count=report.total_mappings,
        )

        if report.total_mappings == 0:
            logger.info("No migration mappings found, nothing to rollback")
            report.completed_at = datetime.now(timezone.utc)
            return report

        if dry_run:
            # In dry run, just report what would be deleted
            for mapping in mappings:
                logger.info(
                    "Would delete",
                    submission_id=str(mapping.new_submission_id),
                    legacy_id=str(mapping.legacy_petition_id),
                    migrated_at=mapping.migrated_at.isoformat(),
                    co_signer_count=mapping.co_signer_count,
                )
            report.submissions_deleted = len(mappings)
            report.mappings_deleted = len(mappings)
        else:
            # Actual deletion - use efficient batch deletes
            # Step 1: Delete petition submissions
            # (FK cascade would also delete mappings, but we do explicit for audit)
            submissions_deleted = await delete_submissions_by_mapping()
            report.submissions_deleted = submissions_deleted

            logger.info(
                "Deleted petition submissions",
                count=submissions_deleted,
            )

            # Step 2: Delete migration mappings
            # (May already be gone from cascade, but explicit for safety)
            mappings_deleted = await delete_all_migration_mappings()
            report.mappings_deleted = mappings_deleted

            logger.info(
                "Deleted migration mappings",
                count=mappings_deleted,
            )

        report.completed_at = datetime.now(timezone.utc)

        logger.info(
            "Rollback completed",
            submissions_deleted=report.submissions_deleted,
            mappings_deleted=report.mappings_deleted,
            failed=report.failed,
        )

    except Exception as e:
        report.completed_at = datetime.now(timezone.utc)
        report.failed += 1
        logger.error("Rollback failed", error=str(e))
        raise

    return report


# =============================================================================
# Main
# =============================================================================


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Rollback Story 7.2 cessation petition migration",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be rolled back without deleting",
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Required for actual rollback (safety measure)",
    )
    return parser.parse_args()


async def main() -> int:
    """Run the rollback and return exit code."""
    args = parse_args()

    print("[AC6] Starting cessation petition rollback...")

    # Safety check: require --confirm for non-dry-run
    if not args.dry_run and not args.confirm:
        print("\n[ERROR] Rollback requires --confirm flag for safety.")
        print("        Use --dry-run to see what would be deleted.")
        print("        Use --confirm to actually delete data.")
        return 2

    if args.dry_run:
        print("  (DRY RUN - no database deletes will occur)")
    else:
        print("  WARNING: This will DELETE data from the database!")
        print("  Legacy petitions in event store are NOT affected.")

    try:
        report = await run_rollback(dry_run=args.dry_run)
        report.print_report()

        return 0 if report.failed == 0 else 1

    except Exception as e:
        logger.error("Rollback failed with exception", error=str(e))
        print(f"\n[ERROR] Rollback failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
