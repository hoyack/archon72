"""PostgreSQL Merkle Tree Adapter.

Story: consent-gov-1.7: Merkle Tree Proof-of-Inclusion

This adapter implements the MerkleTreePort for PostgreSQL storage
using the ledger.merkle_epochs table.

Constitutional Constraints:
- AD-7: Merkle tree proof-of-inclusion
- NFR-CONST-02: Proof-of-inclusion for any entry
- NFR-AUDIT-06: External verification possible
- FR57: Cryptographic proof of completeness

Architectural Notes:
- Epoch roots are stored in ledger.merkle_epochs
- Proofs are generated on-demand by rebuilding tree from ledger
- verify_proof() is pure computation (no database access)

References:
- [Source: _bmad-output/planning-artifacts/governance-architecture.md#Proof-of-Inclusion (Locked)]
- [Source: migrations/011_create_merkle_epochs_table.sql]
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any
from uuid import UUID

from structlog import get_logger

from src.application.ports.governance.ledger_port import LedgerReadOptions
from src.application.ports.governance.merkle_tree_port import (
    EpochInfo,
    MerkleTreePort,
)
from src.domain.governance.events.hash_algorithms import DEFAULT_ALGORITHM
from src.domain.governance.events.merkle_tree import (
    MerkleProof,
    MerkleTree,
    MerkleVerificationResult,
    verify_merkle_proof,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from src.application.ports.governance.ledger_port import GovernanceLedgerPort

logger = get_logger(__name__)


class PostgresMerkleTreeAdapter(MerkleTreePort):
    """PostgreSQL implementation of MerkleTreePort.

    Uses ledger.merkle_epochs table for epoch root storage and
    ledger.governance_events for proof generation.

    Constitutional Guarantee:
    - Any event can have proof generated (AD-7)
    - Proofs are independently verifiable (NFR-CONST-02)
    - Epoch roots are published to ledger (AC6)
    """

    def __init__(
        self,
        session_factory: "async_sessionmaker[AsyncSession]",
        ledger_port: "GovernanceLedgerPort",
        verbose: bool = False,
    ) -> None:
        """Initialize the PostgreSQL Merkle tree adapter.

        Args:
            session_factory: SQLAlchemy async session factory.
            ledger_port: Port for reading events from ledger.
            verbose: Enable verbose logging for debugging.
        """
        self._session_factory = session_factory
        self._ledger_port = ledger_port
        self._verbose = verbose

        if self._verbose:
            logger.debug("postgres_merkle_tree_adapter_initialized")

    async def build_epoch(
        self,
        epoch_id: int,
        start_sequence: int,
        end_sequence: int,
        algorithm: str = DEFAULT_ALGORITHM,
    ) -> EpochInfo:
        """Build Merkle tree for an epoch and persist the root.

        Reads events from the ledger for the given sequence range,
        builds the Merkle tree, and persists the root.

        Args:
            epoch_id: Identifier for this epoch.
            start_sequence: First event sequence to include.
            end_sequence: Last event sequence to include.
            algorithm: Hash algorithm for tree construction.

        Returns:
            EpochInfo with the computed root and metadata.

        Raises:
            ValueError: If sequence range is invalid or events missing.
        """
        if start_sequence > end_sequence:
            raise ValueError(
                f"Invalid sequence range: start ({start_sequence}) > end ({end_sequence})"
            )

        # Read events from ledger
        options = LedgerReadOptions(
            start_sequence=start_sequence,
            end_sequence=end_sequence,
            limit=end_sequence - start_sequence + 10,  # Buffer
        )
        events = await self._ledger_port.read_events(options)

        if not events:
            raise ValueError(
                f"No events found for epoch {epoch_id} "
                f"(sequences {start_sequence}-{end_sequence})"
            )

        # Verify we have all events (no gaps)
        sequences = {e.sequence for e in events}
        actual_end = min(end_sequence, max(sequences))
        for seq in range(start_sequence, actual_end + 1):
            if seq not in sequences:
                raise ValueError(
                    f"Gap in sequence: missing event {seq} in epoch {epoch_id}"
                )

        # Extract event hashes and build tree
        event_hashes = [e.event.hash for e in events if e.event.hash]
        if not event_hashes:
            raise ValueError(f"No hashed events found in epoch {epoch_id}")

        tree = MerkleTree(event_hashes, algorithm)
        now = datetime.now(timezone.utc)

        # Persist epoch to database
        async with self._session_factory() as session:
            from sqlalchemy import text

            insert_sql = text("""
                INSERT INTO ledger.merkle_epochs (
                    epoch_id,
                    root_hash,
                    algorithm,
                    start_sequence,
                    end_sequence,
                    event_count,
                    created_at
                ) VALUES (
                    :epoch_id,
                    :root_hash,
                    :algorithm,
                    :start_sequence,
                    :end_sequence,
                    :event_count,
                    :created_at
                )
                ON CONFLICT (epoch_id) DO UPDATE SET
                    root_hash = EXCLUDED.root_hash,
                    algorithm = EXCLUDED.algorithm,
                    start_sequence = EXCLUDED.start_sequence,
                    end_sequence = EXCLUDED.end_sequence,
                    event_count = EXCLUDED.event_count,
                    created_at = EXCLUDED.created_at
                RETURNING epoch_id
            """)

            await session.execute(
                insert_sql,
                {
                    "epoch_id": epoch_id,
                    "root_hash": tree.root,
                    "algorithm": algorithm,
                    "start_sequence": start_sequence,
                    "end_sequence": events[-1].sequence,
                    "event_count": len(events),
                    "created_at": now,
                },
            )

            await session.commit()

        if self._verbose:
            logger.info(
                "merkle_epoch_built",
                epoch_id=epoch_id,
                root_hash=tree.root,
                event_count=len(events),
            )

        return EpochInfo(
            epoch_id=epoch_id,
            root_hash=tree.root,
            algorithm=algorithm,
            start_sequence=start_sequence,
            end_sequence=events[-1].sequence,
            event_count=len(events),
            created_at=now,
            root_event_id=None,
        )

    async def generate_proof(
        self,
        event_id: UUID,
    ) -> MerkleProof:
        """Generate inclusion proof for a specific event.

        Looks up the event, determines its epoch, and generates
        the Merkle proof.

        Args:
            event_id: UUID of the event to prove.

        Returns:
            MerkleProof that can be verified independently.

        Raises:
            ValueError: If event not found or epoch not built.
        """
        # Find the event
        event = await self._ledger_port.get_event_by_id(event_id)
        if event is None:
            raise ValueError(f"Event not found: {event_id}")

        return await self.generate_proof_by_sequence(event.sequence)

    async def generate_proof_by_sequence(
        self,
        sequence: int,
    ) -> MerkleProof:
        """Generate inclusion proof for an event by sequence number.

        Args:
            sequence: Ledger sequence number of the event.

        Returns:
            MerkleProof that can be verified independently.

        Raises:
            ValueError: If sequence not found or epoch not built.
        """
        # Find the event
        event = await self._ledger_port.get_event_by_sequence(sequence)
        if event is None:
            raise ValueError(f"Event not found at sequence: {sequence}")

        # Find the epoch containing this sequence
        epoch_id = await self.get_epoch_for_sequence(sequence)
        if epoch_id is None:
            raise ValueError(
                f"No epoch built for sequence {sequence}. "
                f"Build epoch first before generating proofs."
            )

        # Get epoch info
        epoch_info = await self.get_epoch_info(epoch_id)
        if epoch_info is None:
            raise ValueError(f"Epoch {epoch_id} not found")

        # Rebuild tree from epoch events to generate proof
        options = LedgerReadOptions(
            start_sequence=epoch_info.start_sequence,
            end_sequence=epoch_info.end_sequence,
            limit=epoch_info.event_count + 10,
        )
        events = await self._ledger_port.read_events(options)

        # Build tree
        event_hashes = [e.event.hash for e in events if e.event.hash]
        tree = MerkleTree(event_hashes, epoch_info.algorithm)

        # Find leaf index for this event
        leaf_index = -1
        for i, e in enumerate(events):
            if e.sequence == sequence:
                leaf_index = i
                break

        if leaf_index < 0:
            raise ValueError(f"Event {sequence} not in epoch {epoch_id}")

        # Generate proof
        proof = tree.generate_proof(
            leaf_index=leaf_index,
            event_id=event.event_id,
            epoch=epoch_id,
        )

        if self._verbose:
            logger.debug(
                "merkle_proof_generated",
                event_id=str(event.event_id),
                sequence=sequence,
                epoch=epoch_id,
            )

        return proof

    async def get_epoch_root(
        self,
        epoch_id: int,
    ) -> str | None:
        """Get published Merkle root for an epoch.

        Args:
            epoch_id: Identifier for the epoch.

        Returns:
            Algorithm-prefixed root hash, or None if epoch not built.
        """
        epoch_info = await self.get_epoch_info(epoch_id)
        return epoch_info.root_hash if epoch_info else None

    async def get_epoch_info(
        self,
        epoch_id: int,
    ) -> EpochInfo | None:
        """Get full information about an epoch.

        Args:
            epoch_id: Identifier for the epoch.

        Returns:
            EpochInfo with root and metadata, or None if not built.
        """
        async with self._session_factory() as session:
            from sqlalchemy import text

            query = text("""
                SELECT
                    epoch_id,
                    root_hash,
                    algorithm,
                    start_sequence,
                    end_sequence,
                    event_count,
                    created_at,
                    root_event_id
                FROM ledger.merkle_epochs
                WHERE epoch_id = :epoch_id
            """)

            result = await session.execute(query, {"epoch_id": epoch_id})
            row = result.fetchone()

            if row is None:
                return None

            return self._row_to_epoch_info(row)

    async def get_epoch_for_sequence(
        self,
        sequence: int,
    ) -> int | None:
        """Determine which epoch contains a given sequence number.

        Args:
            sequence: Ledger sequence number.

        Returns:
            Epoch ID containing this sequence, or None if not in any epoch.
        """
        async with self._session_factory() as session:
            from sqlalchemy import text

            query = text("""
                SELECT epoch_id
                FROM ledger.merkle_epochs
                WHERE :sequence >= start_sequence
                  AND :sequence <= end_sequence
                LIMIT 1
            """)

            result = await session.execute(query, {"sequence": sequence})
            row = result.fetchone()

            return row[0] if row else None

    async def list_epochs(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> list[EpochInfo]:
        """List all built epochs.

        Args:
            limit: Maximum number of epochs to return.
            offset: Number of epochs to skip.

        Returns:
            List of EpochInfo ordered by epoch_id ascending.
        """
        async with self._session_factory() as session:
            from sqlalchemy import text

            query = text("""
                SELECT
                    epoch_id,
                    root_hash,
                    algorithm,
                    start_sequence,
                    end_sequence,
                    event_count,
                    created_at,
                    root_event_id
                FROM ledger.merkle_epochs
                ORDER BY epoch_id ASC
                LIMIT :limit OFFSET :offset
            """)

            result = await session.execute(
                query, {"limit": limit, "offset": offset}
            )
            rows = result.fetchall()

            return [self._row_to_epoch_info(row) for row in rows]

    async def get_latest_epoch(self) -> EpochInfo | None:
        """Get the most recently built epoch.

        Returns:
            EpochInfo for the latest epoch, or None if no epochs exist.
        """
        async with self._session_factory() as session:
            from sqlalchemy import text

            query = text("""
                SELECT
                    epoch_id,
                    root_hash,
                    algorithm,
                    start_sequence,
                    end_sequence,
                    event_count,
                    created_at,
                    root_event_id
                FROM ledger.merkle_epochs
                ORDER BY epoch_id DESC
                LIMIT 1
            """)

            result = await session.execute(query)
            row = result.fetchone()

            if row is None:
                return None

            return self._row_to_epoch_info(row)

    def verify_proof(
        self,
        proof: MerkleProof,
    ) -> MerkleVerificationResult:
        """Verify a Merkle proof (no async - pure computation).

        This method requires no database access and can be used by
        external verifiers directly.

        Args:
            proof: The MerkleProof to verify.

        Returns:
            MerkleVerificationResult with verification details.
        """
        return verify_merkle_proof(proof)

    def _row_to_epoch_info(
        self,
        row: tuple[Any, ...],
    ) -> EpochInfo:
        """Convert a database row to an EpochInfo.

        Args:
            row: Database row tuple.

        Returns:
            EpochInfo instance.
        """
        (
            epoch_id,
            root_hash,
            algorithm,
            start_sequence,
            end_sequence,
            event_count,
            created_at,
            root_event_id,
        ) = row

        # Ensure timestamp is timezone-aware
        if isinstance(created_at, datetime) and created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)

        return EpochInfo(
            epoch_id=epoch_id,
            root_hash=root_hash,
            algorithm=algorithm,
            start_sequence=start_sequence,
            end_sequence=end_sequence,
            event_count=event_count,
            created_at=created_at,
            root_event_id=(
                root_event_id
                if isinstance(root_event_id, UUID)
                else UUID(str(root_event_id))
                if root_event_id
                else None
            ),
        )
