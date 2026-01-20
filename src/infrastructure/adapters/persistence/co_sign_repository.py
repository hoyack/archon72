"""PostgreSQL CoSign Repository adapter (Story 5.7, FR-6.2, NFR-3.5).

This module provides the production PostgreSQL implementation of
CoSignRepositoryProtocol for co-signature persistence.

Constitutional Constraints:
- FR-6.2: System SHALL enforce unique constraint (petition_id, signer_id)
- NFR-3.5: 0 duplicate signatures ever exist
- NFR-6.4: Full signer list queryable
- CT-12: Witnessing creates accountability (content hash integrity)
- CT-11: Silent failure destroys legitimacy → All operations logged

Database Table: co_signs (migration 024)
- Unique constraint: uq_co_signs_petition_signer (petition_id, signer_id)
- PostgreSQL error code on violation: 23505 (unique_violation)
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from structlog import get_logger

from src.domain.errors.co_sign import AlreadySignedError, CoSignPetitionNotFoundError

if TYPE_CHECKING:
    pass

logger = get_logger()


class PostgresCoSignRepository:
    """PostgreSQL implementation of CoSignRepository (Story 5.7, FR-6.2, NFR-3.5).

    Uses the co_signs table created by migration 024_create_co_signs_table.sql.

    Constitutional Compliance:
    - FR-6.2: Unique constraint uq_co_signs_petition_signer enforced at DB level
    - NFR-3.5: 0 duplicate signatures - database constraint is ultimate arbiter
    - NFR-6.4: Full signer list queryable via get_signers
    - CT-12: Content hash stored for witness integrity

    Constraint Violation Handling:
    - PostgreSQL error code 23505 (unique_violation) caught and converted
    - AlreadySignedError includes existing signature details for better UX
    - LEGIT-1 logging for fraud pattern analysis

    Attributes:
        _session_factory: SQLAlchemy async session factory for DB access
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """Initialize the PostgreSQL co-sign repository.

        Args:
            session_factory: SQLAlchemy async session factory for DB access.
        """
        self._session_factory = session_factory

    async def create(
        self,
        cosign_id: UUID,
        petition_id: UUID,
        signer_id: UUID,
        signed_at: datetime,
        content_hash: bytes,
        identity_verified: bool = False,
    ) -> int:
        """Create a co-sign record and increment petition co_signer_count.

        Uses the database unique constraint as the ultimate arbiter of
        deduplication (NFR-3.5). On constraint violation, fetches existing
        signature details for enhanced error response.

        SQL Pattern (INSERT):
            INSERT INTO co_signs (
                cosign_id, petition_id, signer_id, signed_at,
                content_hash, identity_verified
            )
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING (SELECT co_signer_count FROM petition_submissions WHERE id = $2)

        On UniqueViolation (23505):
            SELECT cosign_id, signed_at FROM co_signs
            WHERE petition_id = $1 AND signer_id = $2

        Args:
            cosign_id: Unique identifier for this co-signature (UUIDv7).
            petition_id: The petition being co-signed.
            signer_id: The Seeker adding their support.
            signed_at: When the co-signature is recorded (UTC).
            content_hash: BLAKE3 hash for witness integrity (32 bytes).
            identity_verified: Whether signer identity was verified (NFR-5.2).

        Returns:
            The new co_signer_count after increment.

        Raises:
            AlreadySignedError: Unique constraint violation (includes existing signature).
            CoSignPetitionNotFoundError: Petition doesn't exist (FK violation).
        """
        log = logger.bind(
            petition_id=str(petition_id),
            signer_id=str(signer_id),
            cosign_id=str(cosign_id),
        )

        async with self._session_factory() as session:
            try:
                async with session.begin():
                    # Insert co-sign record
                    await session.execute(
                        text("""
                            INSERT INTO co_signs (
                                cosign_id, petition_id, signer_id, signed_at,
                                content_hash, identity_verified
                            )
                            VALUES (
                                :cosign_id, :petition_id, :signer_id, :signed_at,
                                :content_hash, :identity_verified
                            )
                        """),
                        {
                            "cosign_id": cosign_id,
                            "petition_id": petition_id,
                            "signer_id": signer_id,
                            "signed_at": signed_at,
                            "content_hash": content_hash,
                            "identity_verified": identity_verified,
                        },
                    )

                    # Atomically increment co_signer_count and get new value (FR-6.4)
                    result = await session.execute(
                        text("""
                            UPDATE petition_submissions
                            SET co_signer_count = co_signer_count + 1
                            WHERE id = :petition_id
                            RETURNING co_signer_count
                        """),
                        {"petition_id": petition_id},
                    )
                    row = result.fetchone()

                    if row is None:
                        # Petition doesn't exist - should have FK violation first,
                        # but handle as CoSignPetitionNotFoundError
                        raise CoSignPetitionNotFoundError(petition_id)

                    new_count = row[0]

                log.info(
                    "co_sign_created",
                    new_count=new_count,
                    identity_verified=identity_verified,
                )
                return new_count

            except IntegrityError as e:
                # Handle constraint violations
                error_str = str(e.orig) if e.orig else str(e)

                if "unique" in error_str.lower() or "23505" in error_str:
                    # Unique constraint violation - fetch existing signature details
                    log.info(
                        "duplicate_co_sign_attempt",
                        message="LEGIT-1: Duplicate signature blocked by constraint",
                    )

                    existing = await self._get_existing_signature(
                        session, petition_id, signer_id
                    )
                    if existing:
                        existing_id, existing_signed_at = existing
                        raise AlreadySignedError(
                            petition_id=petition_id,
                            signer_id=signer_id,
                            existing_cosign_id=existing_id,
                            signed_at=existing_signed_at,
                        ) from e
                    else:
                        # Constraint fired but can't find existing (race?)
                        raise AlreadySignedError(
                            petition_id=petition_id,
                            signer_id=signer_id,
                        ) from e

                elif "foreign" in error_str.lower() or "23503" in error_str:
                    # FK violation - petition doesn't exist
                    raise CoSignPetitionNotFoundError(petition_id) from e

                else:
                    # Unknown integrity error - re-raise
                    raise

    async def _get_existing_signature(
        self,
        session: AsyncSession,
        petition_id: UUID,
        signer_id: UUID,
    ) -> tuple[UUID, datetime] | None:
        """Fetch existing signature details for error response.

        Args:
            session: Active database session.
            petition_id: The petition to check.
            signer_id: The signer to check.

        Returns:
            Tuple of (cosign_id, signed_at) if exists, None otherwise.
        """
        result = await session.execute(
            text("""
                SELECT cosign_id, signed_at
                FROM co_signs
                WHERE petition_id = :petition_id AND signer_id = :signer_id
            """),
            {"petition_id": petition_id, "signer_id": signer_id},
        )
        row = result.fetchone()
        if row:
            return (row[0], row[1])
        return None

    async def exists(
        self,
        petition_id: UUID,
        signer_id: UUID,
    ) -> bool:
        """Check if a signer has already co-signed a petition.

        Used by service layer for pre-persistence optimization.
        This check is an optimization - the database constraint is
        the ultimate arbiter (NFR-3.5).

        SQL Pattern:
            SELECT 1 FROM co_signs
            WHERE petition_id = $1 AND signer_id = $2
            LIMIT 1

        Args:
            petition_id: The petition to check.
            signer_id: The signer to check.

        Returns:
            True if the signer has already co-signed, False otherwise.
        """
        async with self._session_factory() as session:
            result = await session.execute(
                text("""
                    SELECT 1 FROM co_signs
                    WHERE petition_id = :petition_id AND signer_id = :signer_id
                    LIMIT 1
                """),
                {"petition_id": petition_id, "signer_id": signer_id},
            )
            return result.fetchone() is not None

    async def get_existing(
        self,
        petition_id: UUID,
        signer_id: UUID,
    ) -> tuple[UUID, datetime] | None:
        """Get existing co-sign details if exists (Story 5.7).

        Used by service layer to provide enhanced error messages
        without relying on constraint violation.

        Args:
            petition_id: The petition to check.
            signer_id: The signer to check.

        Returns:
            Tuple of (cosign_id, signed_at) if exists, None otherwise.
        """
        async with self._session_factory() as session:
            return await self._get_existing_signature(session, petition_id, signer_id)

    async def get_count(
        self,
        petition_id: UUID,
    ) -> int:
        """Get the current co-signer count for a petition (O(1) lookup).

        This method reads from petition_submissions.co_signer_count column
        for O(1) performance at scale (NFR-2.2: 100k+ co-signers). The counter
        is atomically incremented on each co-sign INSERT in create().

        IMPORTANT: This returns the counter value, not COUNT(*). For consistency
        verification, use CoSignCountVerificationService.verify_count() which
        compares the counter against SELECT COUNT(*) FROM co_signs.

        SQL Pattern:
            SELECT co_signer_count FROM petition_submissions WHERE id = $1

        Args:
            petition_id: The petition to query.

        Returns:
            Current co_signer_count (0 if petition not found).
        """
        async with self._session_factory() as session:
            result = await session.execute(
                text("""
                    SELECT co_signer_count
                    FROM petition_submissions
                    WHERE id = :petition_id
                """),
                {"petition_id": petition_id},
            )
            row = result.fetchone()
            return row[0] if row else 0

    async def get_signers(
        self,
        petition_id: UUID,
        limit: int = 100,
        offset: int = 0,
    ) -> list[UUID]:
        """Get signer IDs for a petition (NFR-6.4).

        SQL Pattern:
            SELECT signer_id FROM co_signs
            WHERE petition_id = $1
            ORDER BY signed_at ASC
            LIMIT $2 OFFSET $3

        Args:
            petition_id: The petition to query.
            limit: Maximum signers to return.
            offset: Starting offset for pagination.

        Returns:
            List of signer UUIDs ordered by signed_at.
        """
        async with self._session_factory() as session:
            result = await session.execute(
                text("""
                    SELECT signer_id FROM co_signs
                    WHERE petition_id = :petition_id
                    ORDER BY signed_at ASC
                    LIMIT :limit OFFSET :offset
                """),
                {"petition_id": petition_id, "limit": limit, "offset": offset},
            )
            rows = result.fetchall()
            return [row[0] for row in rows]

    async def count_by_signer_since(
        self,
        signer_id: UUID,
        since: datetime,
    ) -> int:
        """Count co-signs by a signer since a timestamp (FR-6.6, SYBIL-1).

        Used for rate limiting detection.

        Args:
            signer_id: The signer to query.
            since: Start of time window.

        Returns:
            Count of co-signs in the window.
        """
        async with self._session_factory() as session:
            result = await session.execute(
                text("""
                    SELECT COUNT(*) FROM co_signs
                    WHERE signer_id = :signer_id
                      AND signed_at >= :since
                """),
                {"signer_id": signer_id, "since": since},
            )
            return result.scalar() or 0
