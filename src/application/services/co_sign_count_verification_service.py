"""Co-sign count verification service (Story 5.8, AC5).

This module implements the CountVerificationService for verifying
consistency between the co_signer_count counter and actual COUNT(*).

Constitutional Constraints:
- NFR-2.2: 100k+ co-signers - counter enables O(1) reads at scale
- AC5: Any discrepancy triggers MEDIUM alert, logged with structured logging
- CT-11: Silent failure destroys legitimacy - discrepancies must be visible

Usage:
    service = CoSignCountVerificationService(session_factory)
    result = await service.verify_count(petition_id)
    if not result.is_consistent:
        # Handle discrepancy (e.g., alert, manual review)
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from structlog import get_logger

from src.application.ports.co_sign_count_verification import CountVerificationResult

if TYPE_CHECKING:
    pass

logger = get_logger()


class CoSignCountVerificationService:
    """Service for verifying co-sign count consistency.

    This service compares the pre-computed co_signer_count column against
    SELECT COUNT(*) FROM co_signs to detect any drift between the counter
    and actual data.

    Constitutional Compliance:
    - NFR-2.2: Supports 100k+ co-signers via counter column
    - AC5: Discrepancy logged with MEDIUM severity
    - CT-11: All operations are logged for accountability

    Attributes:
        _session_factory: SQLAlchemy async session factory for DB access.
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """Initialize the verification service.

        Args:
            session_factory: SQLAlchemy async session factory.
        """
        self._session_factory = session_factory

    async def verify_count(self, petition_id: UUID) -> CountVerificationResult:
        """Verify count consistency for a single petition.

        Executes two queries in sequence:
        1. SELECT co_signer_count FROM petition_submissions WHERE id = ?
        2. SELECT COUNT(*) FROM co_signs WHERE petition_id = ?

        Compares results and logs any discrepancy with WARNING level.

        SQL Pattern:
            -- Query 1: Counter value
            SELECT co_signer_count FROM petition_submissions WHERE id = $1

            -- Query 2: Actual count
            SELECT COUNT(*) FROM co_signs WHERE petition_id = $1

        Args:
            petition_id: The petition to verify.

        Returns:
            CountVerificationResult with comparison details.
        """
        log = logger.bind(petition_id=str(petition_id))

        async with self._session_factory() as session:
            # Get counter value from petition_submissions
            counter_result = await session.execute(
                text("""
                    SELECT co_signer_count
                    FROM petition_submissions
                    WHERE id = :petition_id
                """),
                {"petition_id": petition_id},
            )
            counter_row = counter_result.fetchone()
            counter_value = counter_row[0] if counter_row else 0

            # Get actual count from co_signs table
            actual_result = await session.execute(
                text("""
                    SELECT COUNT(*)
                    FROM co_signs
                    WHERE petition_id = :petition_id
                """),
                {"petition_id": petition_id},
            )
            actual_count = actual_result.scalar() or 0

            # Calculate discrepancy
            is_consistent = counter_value == actual_count
            discrepancy = counter_value - actual_count

            # Log result
            if is_consistent:
                log.debug(
                    "co_sign_count_verified",
                    counter_value=counter_value,
                    actual_count=actual_count,
                    result="consistent",
                )
            else:
                # AC5: Discrepancy triggers MEDIUM alert (WARNING level)
                log.warning(
                    "co_sign_count_discrepancy_detected",
                    counter_value=counter_value,
                    actual_count=actual_count,
                    discrepancy=discrepancy,
                    alert_severity="MEDIUM",
                    result="inconsistent",
                )

            return CountVerificationResult(
                petition_id=petition_id,
                counter_value=counter_value,
                actual_count=actual_count,
                is_consistent=is_consistent,
                discrepancy=discrepancy,
            )

    async def verify_batch(
        self,
        petition_ids: list[UUID],
    ) -> list[CountVerificationResult]:
        """Verify count consistency for multiple petitions.

        Processes each petition sequentially. For very large batches,
        consider batching with progress tracking.

        Args:
            petition_ids: List of petition IDs to verify.

        Returns:
            List of CountVerificationResult, one per petition.
        """
        log = logger.bind(batch_size=len(petition_ids))
        log.info("co_sign_count_batch_verification_started")

        results: list[CountVerificationResult] = []
        inconsistent_count = 0

        for petition_id in petition_ids:
            result = await self.verify_count(petition_id)
            results.append(result)
            if not result.is_consistent:
                inconsistent_count += 1

        log.info(
            "co_sign_count_batch_verification_completed",
            total=len(petition_ids),
            consistent=len(petition_ids) - inconsistent_count,
            inconsistent=inconsistent_count,
        )

        return results
