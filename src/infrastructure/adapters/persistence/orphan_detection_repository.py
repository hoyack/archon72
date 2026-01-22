"""Orphan detection repository adapter (Story 8.3, FR-8.5).

This module provides persistence operations for orphan petition detection
results, supporting historical trend analysis and dashboard visibility.

Constitutional Constraints:
- FR-8.5: System SHALL identify petitions stuck in RECEIVED state
- NFR-7.1: 100% of orphans must be detected
- AC6: Comprehensive audit trail for governance actions

Tables:
- orphan_detection_runs: Detection scan execution records
- orphaned_petitions: Individual orphaned petitions per scan

Developer Golden Rules:
1. FAIL LOUD - Never silently swallow persistence errors
2. READS DURING HALT - Read operations allowed during halt (CT-13)
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Protocol
from uuid import UUID

from src.domain.models.orphan_petition_detection import (
    OrphanPetitionDetectionResult,
    OrphanPetitionInfo,
)

logger = logging.getLogger(__name__)


class DatabaseConnectionPort(Protocol):
    """Port for database connection operations."""

    def execute(self, query: str, params: tuple) -> None:
        """Execute a query with parameters."""
        ...

    def fetchall(self, query: str, params: tuple) -> list[tuple]:
        """Fetch all rows from a query."""
        ...

    def fetchone(self, query: str, params: tuple) -> tuple | None:
        """Fetch one row from a query."""
        ...


class OrphanDetectionRepository:
    """Repository for orphan detection persistence (Story 8.3, FR-8.5).

    Provides operations for storing and querying orphan petition detection
    results for historical analysis and dashboard visibility.

    Constitutional Requirements:
    - FR-8.5: Track orphan detection results
    - AC6: Comprehensive audit trail

    Attributes:
        db_connection: Database connection for queries
    """

    def __init__(self, db_connection: DatabaseConnectionPort):
        """Initialize repository with database connection.

        Args:
            db_connection: Database connection for persistence operations
        """
        self.db_connection = db_connection

    def save_detection_result(
        self, detection_result: OrphanPetitionDetectionResult
    ) -> None:
        """Save orphan detection result to database (FR-8.5).

        Stores detection run summary and individual orphaned petitions
        for historical tracking and dashboard visibility.

        Args:
            detection_result: Detection result to persist

        Raises:
            Exception: If persistence fails (FAIL LOUD)
        """
        logger.info(
            "Saving orphan detection result",
            extra={
                "detection_id": str(detection_result.detection_id),
                "orphan_count": detection_result.total_orphans,
            },
        )

        # Insert detection run summary
        run_query = """
            INSERT INTO orphan_detection_runs (
                detection_id,
                detected_at,
                threshold_hours,
                orphan_count,
                oldest_orphan_age_hours
            ) VALUES (%s, %s, %s, %s, %s)
        """

        run_params = (
            detection_result.detection_id,
            detection_result.detected_at,
            detection_result.threshold_hours,
            detection_result.total_orphans,
            detection_result.oldest_orphan_age_hours,
        )

        self.db_connection.execute(run_query, run_params)

        # Insert individual orphaned petitions
        if detection_result.orphan_petitions:
            orphan_query = """
                INSERT INTO orphaned_petitions (
                    detection_id,
                    petition_id,
                    petition_created_at,
                    age_hours,
                    petition_type,
                    co_signer_count
                ) VALUES (%s, %s, %s, %s, %s, %s)
            """

            for orphan in detection_result.orphan_petitions:
                orphan_params = (
                    detection_result.detection_id,
                    orphan.petition_id,
                    orphan.created_at,
                    orphan.age_hours,
                    orphan.petition_type,
                    orphan.co_signer_count,
                )
                self.db_connection.execute(orphan_query, orphan_params)

        logger.info(
            "Orphan detection result saved",
            extra={
                "detection_id": str(detection_result.detection_id),
                "orphan_count": detection_result.total_orphans,
            },
        )

    def mark_as_reprocessed(
        self,
        detection_id: UUID,
        petition_ids: list[UUID],
        reprocessed_by: str,
    ) -> None:
        """Mark orphaned petitions as reprocessed (FR-8.5).

        Updates reprocessing tracking fields for operator visibility.

        Args:
            detection_id: UUID of detection run
            petition_ids: List of petition IDs that were reprocessed
            reprocessed_by: Operator/agent who triggered reprocessing

        Raises:
            Exception: If update fails (FAIL LOUD)
        """
        logger.info(
            "Marking orphans as reprocessed",
            extra={
                "detection_id": str(detection_id),
                "petition_count": len(petition_ids),
                "reprocessed_by": reprocessed_by,
            },
        )

        query = """
            UPDATE orphaned_petitions
            SET reprocessed = TRUE,
                reprocessed_at = NOW(),
                reprocessed_by = %s
            WHERE detection_id = %s
              AND petition_id = ANY(%s)
        """

        params = (
            reprocessed_by,
            detection_id,
            [str(pid) for pid in petition_ids],
        )

        self.db_connection.execute(query, params)

        logger.info(
            "Orphans marked as reprocessed",
            extra={
                "detection_id": str(detection_id),
                "petition_count": len(petition_ids),
            },
        )

    def get_latest_detection_run(self) -> OrphanPetitionDetectionResult | None:
        """Get the most recent orphan detection run (FR-8.5).

        Returns:
            Latest detection result, or None if no runs exist.
        """
        run_query = """
            SELECT detection_id, detected_at, threshold_hours,
                   orphan_count, oldest_orphan_age_hours
            FROM orphan_detection_runs
            ORDER BY detected_at DESC
            LIMIT 1
        """

        run_row = self.db_connection.fetchone(run_query, ())
        if not run_row:
            return None

        detection_id, detected_at, threshold_hours, orphan_count, oldest_age = run_row

        # Fetch individual orphans for this run
        orphan_query = """
            SELECT petition_id, petition_created_at, age_hours, petition_type, co_signer_count
            FROM orphaned_petitions
            WHERE detection_id = %s
            ORDER BY age_hours DESC
        """

        orphan_rows = self.db_connection.fetchall(orphan_query, (detection_id,))

        orphan_infos = [
            OrphanPetitionInfo(
                petition_id=UUID(row[0]),
                created_at=row[1],
                age_hours=float(row[2]),
                petition_type=row[3],
                co_signer_count=row[4],
            )
            for row in orphan_rows
        ]

        return OrphanPetitionDetectionResult(
            detection_id=UUID(detection_id),
            detected_at=detected_at,
            threshold_hours=float(threshold_hours),
            orphan_petitions=tuple(orphan_infos),
            total_orphans=orphan_count,
            oldest_orphan_age_hours=float(oldest_age) if oldest_age else None,
        )

    def get_orphan_count(self) -> int:
        """Get current orphan count from latest detection run (FR-8.5).

        Returns:
            Number of orphans in the latest detection, or 0 if no runs.
        """
        query = """
            SELECT orphan_count
            FROM orphan_detection_runs
            ORDER BY detected_at DESC
            LIMIT 1
        """

        row = self.db_connection.fetchone(query, ())
        return row[0] if row else 0

    def get_detection_history(
        self, limit: int = 30
    ) -> list[OrphanPetitionDetectionResult]:
        """Get historical orphan detection results (FR-8.5).

        Args:
            limit: Maximum number of historical runs to return (default: 30)

        Returns:
            List of detection results, ordered by detected_at DESC.
        """
        query = """
            SELECT detection_id, detected_at, threshold_hours,
                   orphan_count, oldest_orphan_age_hours
            FROM orphan_detection_runs
            ORDER BY detected_at DESC
            LIMIT %s
        """

        rows = self.db_connection.fetchall(query, (limit,))

        results = []
        for row in rows:
            detection_id, detected_at, threshold_hours, orphan_count, oldest_age = row

            # Note: For historical queries, we skip loading individual orphans
            # to optimize query performance. Use get_latest_detection_run()
            # for full detail on the most recent run.

            results.append(
                OrphanPetitionDetectionResult(
                    detection_id=UUID(detection_id),
                    detected_at=detected_at,
                    threshold_hours=float(threshold_hours),
                    orphan_petitions=tuple(),  # Empty for historical summary
                    total_orphans=orphan_count,
                    oldest_orphan_age_hours=float(oldest_age) if oldest_age else None,
                )
            )

        return results
