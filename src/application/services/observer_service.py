"""Observer application service (Story 4.1, Task 5; Story 4.2, Task 7; Story 4.3, Task 3; Story 4.5, Task 3; Story 4.6, Task 4; Story 4.9, Task 5; Story 7.5, Task 3).

Provides observer access to events without authentication.

Constitutional Constraints:
- FR42: Read-only access indefinitely after cessation
- FR44: All read operations are public (no auth required)
- FR46: Query interface supports date range and event type filtering
- FR64: Verification bundles for offline verification
- FR88: Query for state as of any sequence number or timestamp
- FR89: Historical queries return hash chain proof to current head
- FR136: Merkle proof SHALL be included in event query responses when requested
- FR137: Observers SHALL be able to verify event inclusion without downloading full chain
- FR138: Weekly checkpoint anchors SHALL be published at consistent intervals
- CT-13: Reads allowed during halt (per Story 3.5) AND indefinitely after cessation (Story 7.5)
- RT-5: 99.9% uptime SLA with external monitoring (Story 4.9)
- ADR-8: Observer Consistency + Genesis Anchor - checkpoint fallback
"""

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from src.application.dtos.observer import (
    CheckpointAnchor,
    HashChainProof,
    HashChainProofEntry,
    MerkleProof,
    MerkleProofEntry,
)
from src.application.ports.event_store import EventStorePort
from src.application.ports.halt_checker import HaltChecker
from src.domain.errors.event_store import EventNotFoundError
from src.domain.events import Event
from src.domain.events.hash_utils import GENESIS_HASH

if TYPE_CHECKING:
    from src.application.ports.checkpoint_repository import CheckpointRepository
    from src.application.ports.freeze_checker import FreezeCheckerProtocol
    from src.application.services.merkle_tree_service import MerkleTreeService
    from src.domain.models.ceased_status_header import CessationDetails
    from src.domain.models.checkpoint import Checkpoint


@dataclass
class ChainVerificationResultDTO:
    """Result of chain verification operation."""

    start_sequence: int
    end_sequence: int
    is_valid: bool
    first_invalid_sequence: int | None = None
    error_message: str | None = None
    verified_count: int = 0


class ObserverService:
    """Application service for observer operations.

    Provides observer access to events without authentication.
    Per FR44: All read operations are public.
    Per CT-13: Reads allowed during halt (Story 3.5).
    Per FR136-FR138: Merkle proofs for O(log n) verification.

    This service acts as a facade over the EventStorePort,
    providing a clean interface for the observer API layer.
    """

    def __init__(
        self,
        event_store: EventStorePort,
        halt_checker: HaltChecker,
        checkpoint_repo: Optional["CheckpointRepository"] = None,
        merkle_service: Optional["MerkleTreeService"] = None,
        freeze_checker: Optional["FreezeCheckerProtocol"] = None,
    ) -> None:
        """Initialize observer service.

        Args:
            event_store: Port for event store operations.
            halt_checker: Port for checking halt state.
                Note: Reads are allowed during halt, so this is
                primarily for informational purposes.
            checkpoint_repo: Port for checkpoint repository operations (optional).
                Required for Merkle proof generation (Story 4.6).
            merkle_service: Service for Merkle tree operations (optional).
                Required for Merkle proof generation (Story 4.6).
            freeze_checker: Port for checking cessation state (optional).
                Required for cessation status in responses (Story 7.5).
        """
        self._event_store = event_store
        self._halt_checker = halt_checker
        self._checkpoint_repo = checkpoint_repo
        self._merkle_service = merkle_service
        self._freeze_checker = freeze_checker

    async def get_events(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[Event], int]:
        """Get events with pagination.

        Per FR44: This is a public read operation, no auth required.
        Per CT-13: Reads are allowed during halt (Story 3.5).

        Args:
            limit: Maximum number of events to return (default 100).
            offset: Number of events to skip (default 0).

        Returns:
            Tuple of (events, total_count).
            - events: List of Event entities for this page.
            - total_count: Total number of events in the store.

        Note:
            Events are returned ordered by sequence number,
            which is the authoritative ordering (Story 1.5).
        """
        # Per CT-13: Reads are ALWAYS allowed, even during halt
        # We do NOT check halt state for read operations

        # Get total count
        total = await self._event_store.count_events()

        # Get max sequence to determine range
        max_seq = await self._event_store.get_max_sequence()

        # Calculate sequence range for this page
        # Sequences are 1-based
        start_seq = offset + 1
        end_seq = min(start_seq + limit - 1, max_seq)

        # If start is beyond max, return empty
        if start_seq > max_seq or max_seq == 0:
            return [], total

        # Get events in the sequence range
        events = await self._event_store.get_events_by_sequence_range(
            start=start_seq,
            end=end_seq,
        )

        return events, total

    async def get_events_filtered(
        self,
        limit: int = 100,
        offset: int = 0,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        event_types: list[str] | None = None,
    ) -> tuple[list[Event], int]:
        """Get events with optional filters (FR46).

        Per FR44: This is a public read operation, no auth required.
        Per CT-13: Reads are allowed during halt.
        Per FR46: Supports date range and event type filtering.

        Filters combine with AND logic:
        - Date range filters on authority_timestamp
        - Event types use OR within the list (any of the types match)
        - Date + types combine with AND (must match date AND be one of the types)

        Args:
            limit: Maximum number of events to return (default 100).
            offset: Number of events to skip (default 0).
            start_date: Filter events from this timestamp (inclusive).
            end_date: Filter events until this timestamp (inclusive).
            event_types: Filter by event types (OR within list).

        Returns:
            Tuple of (events, total_count).
            - events: List of Event entities matching filters.
            - total_count: Total number of events matching filters.

        Note:
            Events are returned ordered by sequence number,
            which is the authoritative ordering (Story 1.5).
        """
        # Per CT-13: Reads are ALWAYS allowed, even during halt
        # We do NOT check halt state for read operations

        # Get total count for pagination
        total = await self._event_store.count_events_filtered(
            start_date=start_date,
            end_date=end_date,
            event_types=event_types,
        )

        # Get filtered events
        events = await self._event_store.get_events_filtered(
            limit=limit,
            offset=offset,
            start_date=start_date,
            end_date=end_date,
            event_types=event_types,
        )

        return events, total

    async def get_event_by_id(self, event_id: UUID) -> Event | None:
        """Get single event by ID.

        Per FR44: This is a public read operation, no auth required.
        Per CT-13: Reads are allowed during halt.

        Args:
            event_id: The UUID of the event to retrieve.

        Returns:
            The Event if found, None otherwise.
        """
        # No halt check for reads
        return await self._event_store.get_event_by_id(event_id)

    async def get_event_by_sequence(self, sequence: int) -> Event | None:
        """Get single event by sequence number.

        Per FR44: This is a public read operation, no auth required.
        Per CT-13: Reads are allowed during halt.

        Sequence number is the authoritative ordering mechanism
        (Story 1.5, FR7).

        Args:
            sequence: The sequence number of the event.

        Returns:
            The Event if found, None otherwise.
        """
        # No halt check for reads
        return await self._event_store.get_event_by_sequence(sequence)

    async def verify_chain(
        self,
        start: int,
        end: int,
    ) -> ChainVerificationResultDTO:
        """Verify hash chain integrity for a range of events (FR64).

        Per FR64: Verification bundles for offline verification.
        Per FR44: This is a public read operation, no auth required.
        Per CT-13: Reads are allowed during halt.

        Verifies:
        1. prev_hash of event N matches content_hash of event N-1
        2. For sequence 1, prev_hash must equal GENESIS_HASH

        Args:
            start: First sequence number to verify.
            end: Last sequence number to verify.

        Returns:
            ChainVerificationResultDTO with verification results.
        """
        # No halt check for reads

        # Validate inputs
        if start < 1:
            return ChainVerificationResultDTO(
                start_sequence=start,
                end_sequence=end,
                is_valid=False,
                error_message="Start sequence must be >= 1",
            )
        if end < start:
            return ChainVerificationResultDTO(
                start_sequence=start,
                end_sequence=end,
                is_valid=False,
                error_message="End sequence must be >= start sequence",
            )

        # Get events in range
        events = await self._event_store.get_events_by_sequence_range(start, end)

        if not events:
            return ChainVerificationResultDTO(
                start_sequence=start,
                end_sequence=end,
                is_valid=True,
                verified_count=0,
            )

        verified_count = 0

        for i, event in enumerate(events):
            # Check sequence continuity
            expected_seq = start + i
            if event.sequence != expected_seq:
                return ChainVerificationResultDTO(
                    start_sequence=start,
                    end_sequence=end,
                    is_valid=False,
                    first_invalid_sequence=expected_seq,
                    error_message=f"Missing sequence {expected_seq}",
                    verified_count=verified_count,
                )

            # For first event in range, check prev_hash
            if i == 0:
                if event.sequence == 1:
                    # Genesis event: prev_hash must be GENESIS_HASH
                    if event.prev_hash != GENESIS_HASH:
                        return ChainVerificationResultDTO(
                            start_sequence=start,
                            end_sequence=end,
                            is_valid=False,
                            first_invalid_sequence=1,
                            error_message=(
                                f"Genesis event prev_hash mismatch. "
                                f"Expected {GENESIS_HASH}, got {event.prev_hash}"
                            ),
                            verified_count=0,
                        )
                else:
                    # Need previous event to verify chain link
                    prev_event = await self._event_store.get_event_by_sequence(
                        event.sequence - 1
                    )
                    if prev_event is None:
                        return ChainVerificationResultDTO(
                            start_sequence=start,
                            end_sequence=end,
                            is_valid=False,
                            first_invalid_sequence=event.sequence,
                            error_message=(
                                f"Cannot verify sequence {event.sequence}: "
                                f"previous event {event.sequence - 1} not found"
                            ),
                            verified_count=0,
                        )
                    if event.prev_hash != prev_event.content_hash:
                        return ChainVerificationResultDTO(
                            start_sequence=start,
                            end_sequence=end,
                            is_valid=False,
                            first_invalid_sequence=event.sequence,
                            error_message=(
                                f"Hash chain broken at sequence {event.sequence}. "
                                f"prev_hash does not match previous content_hash"
                            ),
                            verified_count=0,
                        )
            else:
                # Verify chain link with previous event in range
                prev_event = events[i - 1]
                if event.prev_hash != prev_event.content_hash:
                    return ChainVerificationResultDTO(
                        start_sequence=start,
                        end_sequence=end,
                        is_valid=False,
                        first_invalid_sequence=event.sequence,
                        error_message=(
                            f"Hash chain broken at sequence {event.sequence}. "
                            f"prev_hash does not match previous content_hash"
                        ),
                        verified_count=verified_count,
                    )

            verified_count += 1

        return ChainVerificationResultDTO(
            start_sequence=start,
            end_sequence=end,
            is_valid=True,
            verified_count=verified_count,
        )

    # =========================================================================
    # Historical Query Methods (Story 4.5, Task 3 - FR88, FR89)
    # =========================================================================

    async def get_events_as_of(
        self,
        as_of_sequence: int,
        limit: int = 100,
        offset: int = 0,
        include_proof: bool = False,
    ) -> tuple[list[Event], int, HashChainProof | None]:
        """Get events as of a specific sequence number (FR88).

        Returns events with sequence <= as_of_sequence, excluding
        any events that were appended after that point.

        If include_proof is True, generates hash chain proof from
        as_of_sequence to current head (FR89).

        Per FR44: This is a public read operation, no auth required.
        Per CT-13: Reads are allowed during halt.
        Per FR88: Query for state as of any sequence number.
        Per FR89: Include hash chain proof to current head.

        Args:
            as_of_sequence: Maximum sequence number to include.
            limit: Maximum events to return.
            offset: Number of events to skip.
            include_proof: Whether to include hash chain proof.

        Returns:
            Tuple of (events, total_count, optional_proof).

        Raises:
            EventNotFoundError: If as_of_sequence doesn't exist.
        """
        # Per CT-13: Reads are ALWAYS allowed, even during halt

        # Verify as_of_sequence exists
        as_of_event = await self._event_store.get_event_by_sequence(as_of_sequence)
        if as_of_event is None:
            raise EventNotFoundError(f"Sequence {as_of_sequence} not found")

        # Get events up to as_of_sequence
        events = await self._event_store.get_events_up_to_sequence(
            max_sequence=as_of_sequence,
            limit=limit,
            offset=offset,
        )

        # Get count for pagination
        total = await self._event_store.count_events_up_to_sequence(as_of_sequence)

        # Generate proof if requested
        proof = None
        if include_proof:
            proof = await self._generate_hash_chain_proof(as_of_sequence)

        return events, total, proof

    async def _generate_hash_chain_proof(
        self,
        from_sequence: int,
    ) -> HashChainProof:
        """Generate hash chain proof from sequence to current head.

        The proof contains the chain of (sequence, content_hash, prev_hash)
        entries that connect the queried point to the current head.

        Per FR89: Historical queries SHALL return hash chain proof
        connecting queried state to current head.

        Args:
            from_sequence: Starting sequence for proof.

        Returns:
            HashChainProof connecting from_sequence to head.

        Raises:
            EventNotFoundError: If no events exist in the store.
        """
        # Get current head
        head_event = await self._event_store.get_latest_event()
        if head_event is None:
            raise EventNotFoundError("No events in store")

        # Get all events from from_sequence to head
        proof_events = await self._event_store.get_events_by_sequence_range(
            start=from_sequence,
            end=head_event.sequence,
        )

        # Build proof chain
        chain = [
            HashChainProofEntry(
                sequence=e.sequence,
                content_hash=e.content_hash,
                prev_hash=e.prev_hash,
            )
            for e in proof_events
        ]

        return HashChainProof(
            from_sequence=from_sequence,
            to_sequence=head_event.sequence,
            chain=chain,
            current_head_hash=head_event.content_hash,
        )

    async def get_events_as_of_timestamp(
        self,
        as_of_timestamp: datetime,
        limit: int = 100,
        offset: int = 0,
        include_proof: bool = False,
    ) -> tuple[list[Event], int, int, HashChainProof | None]:
        """Get events as of a specific timestamp (FR88).

        Finds the last event before the given timestamp and returns
        all events up to that point.

        Per FR44: This is a public read operation, no auth required.
        Per CT-13: Reads are allowed during halt.
        Per FR88: Query for state as of any timestamp.

        Args:
            as_of_timestamp: Query state as of this timestamp.
            limit: Maximum events to return.
            offset: Number of events to skip.
            include_proof: Whether to include hash chain proof.

        Returns:
            Tuple of (events, total_count, resolved_sequence, optional_proof).
            resolved_sequence is the sequence that corresponds to the timestamp.
        """
        # Per CT-13: Reads are ALWAYS allowed, even during halt

        # Find sequence for timestamp
        resolved_sequence = await self._event_store.find_sequence_for_timestamp(
            as_of_timestamp
        )

        if resolved_sequence is None:
            # No events before timestamp
            return [], 0, 0, None

        events, total, proof = await self.get_events_as_of(
            as_of_sequence=resolved_sequence,
            limit=limit,
            offset=offset,
            include_proof=include_proof,
        )

        return events, total, resolved_sequence, proof

    # =========================================================================
    # Merkle Proof Methods (Story 4.6, Task 4 - FR136, FR137, FR138)
    # =========================================================================

    async def _generate_merkle_proof(
        self,
        sequence: int,
    ) -> MerkleProof | None:
        """Generate Merkle proof for a specific event sequence (FR136).

        Generates a Merkle proof that allows O(log n) verification of
        event inclusion in a checkpoint. Returns None if the event is
        in the pending interval (not yet checkpointed).

        Per FR136: Merkle proof SHALL be included in event query responses
        when requested.
        Per FR137: Observers SHALL be able to verify event inclusion without
        downloading the full chain.

        Args:
            sequence: Event sequence number to generate proof for.

        Returns:
            MerkleProof for the event, or None if in pending interval.
        """
        if self._checkpoint_repo is None or self._merkle_service is None:
            return None

        # Find checkpoint containing this sequence
        checkpoint = await self._checkpoint_repo.get_checkpoint_for_sequence(sequence)
        if checkpoint is None:
            # Event is in pending interval (not yet checkpointed)
            return None

        # Get the event to verify
        event = await self._event_store.get_event_by_sequence(sequence)
        if event is None:
            return None

        # Get all events in the checkpoint to build Merkle tree
        events = await self._event_store.get_events_by_sequence_range(
            start=1,  # From genesis to checkpoint
            end=checkpoint.event_sequence,
        )

        if not events:
            return None

        # Extract content hashes as leaves
        leaves = [e.content_hash for e in events]

        # Generate proof using MerkleTreeService
        # The index is (sequence - 1) since sequences are 1-based
        proof_path = self._merkle_service.generate_proof(
            leaves=leaves,
            index=sequence - 1,
        )

        # Build MerkleProof response model
        path_entries = [
            MerkleProofEntry(
                level=entry.level,
                position=entry.position,
                sibling_hash=entry.sibling_hash,
            )
            for entry in proof_path
        ]

        return MerkleProof(
            event_sequence=sequence,
            event_hash=event.content_hash,
            checkpoint_sequence=checkpoint.event_sequence,
            checkpoint_root=checkpoint.anchor_hash,
            path=path_entries,
            tree_size=len(leaves),
        )

    async def get_events_with_merkle_proof(
        self,
        as_of_sequence: int,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[Event], int, MerkleProof | None, HashChainProof | None]:
        """Get events with Merkle proof when available (FR136, FR137).

        Returns events up to as_of_sequence with a Merkle proof if the
        sequence is in a checkpointed interval. Falls back to hash chain
        proof for events in the pending interval.

        Per FR136: Merkle proof SHALL be included when requested.
        Per FR137: Merkle proof enables O(log n) verification.

        Args:
            as_of_sequence: Maximum sequence number to include.
            limit: Maximum events to return.
            offset: Number of events to skip.

        Returns:
            Tuple of (events, total_count, merkle_proof, hash_chain_proof).
            - merkle_proof: Set if event is in checkpointed interval.
            - hash_chain_proof: Set if event is in pending interval.
        """
        # Verify as_of_sequence exists
        as_of_event = await self._event_store.get_event_by_sequence(as_of_sequence)
        if as_of_event is None:
            raise EventNotFoundError(f"Sequence {as_of_sequence} not found")

        # Get events up to as_of_sequence
        events = await self._event_store.get_events_up_to_sequence(
            max_sequence=as_of_sequence,
            limit=limit,
            offset=offset,
        )

        # Get count for pagination
        total = await self._event_store.count_events_up_to_sequence(as_of_sequence)

        # Try to generate Merkle proof first
        merkle_proof = await self._generate_merkle_proof(as_of_sequence)

        # If no Merkle proof (pending interval), fall back to hash chain
        hash_chain_proof = None
        if merkle_proof is None:
            hash_chain_proof = await self._generate_hash_chain_proof(as_of_sequence)

        return events, total, merkle_proof, hash_chain_proof

    async def list_checkpoints(
        self,
        limit: int = 10,
        offset: int = 0,
    ) -> tuple[list["Checkpoint"], int]:
        """List checkpoint anchors with pagination (FR138).

        Returns checkpoints ordered by event_sequence descending
        (most recent first).

        Per FR138: Weekly checkpoint anchors SHALL be published at
        consistent intervals.

        Args:
            limit: Maximum checkpoints to return.
            offset: Number to skip.

        Returns:
            Tuple of (checkpoints, total_count).
        """
        if self._checkpoint_repo is None:
            return [], 0

        return await self._checkpoint_repo.list_checkpoints(limit=limit, offset=offset)

    async def get_checkpoint_for_sequence(
        self,
        sequence: int,
    ) -> Optional["Checkpoint"]:
        """Get checkpoint containing a specific event sequence.

        Finds the checkpoint whose interval contains the given sequence.
        Returns None if the sequence is in the pending interval.

        Args:
            sequence: Event sequence number.

        Returns:
            Checkpoint containing the sequence, or None if pending.
        """
        if self._checkpoint_repo is None:
            return None

        return await self._checkpoint_repo.get_checkpoint_for_sequence(sequence)

    # =========================================================================
    # Health & SLA Methods (Story 4.9, Task 5 - RT-5, ADR-8)
    # =========================================================================

    async def check_database_health(self) -> None:
        """Check database connectivity (RT-5).

        Per RT-5: External monitoring requires health checks.
        Per CT-11: Health status must be accurate.

        Executes a simple count query to verify database connectivity.
        Raises exception if database is unavailable.

        Raises:
            Exception: If database is unavailable.
        """
        await self._event_store.count_events()

    async def get_last_checkpoint_sequence(self) -> int | None:
        """Get sequence number of last checkpoint anchor (RT-5).

        Per RT-5: Provides checkpoint info for health/fallback.
        Per ADR-8: Checkpoint anchors for fallback verification.

        Returns:
            Last checkpoint sequence, or None if no checkpoints.
        """
        if self._checkpoint_repo is None:
            return None

        checkpoints, _ = await self._checkpoint_repo.list_checkpoints(limit=1, offset=0)
        if not checkpoints:
            return None

        return checkpoints[0].event_sequence

    async def get_genesis_anchor_hash(self) -> str:
        """Get genesis anchor hash for root verification (ADR-8).

        Per ADR-8: Genesis anchor verification works during API outage.
        The genesis hash is the foundation of the hash chain.

        Returns:
            Genesis anchor content hash (64 zeros for genesis).
        """
        # Genesis hash is always GENESIS_HASH (64 zeros)
        # This represents the "previous hash" of the first event
        return GENESIS_HASH

    async def get_checkpoint_count(self) -> int:
        """Get total number of checkpoint anchors (RT-5).

        Per RT-5: Provides checkpoint count for fallback info.

        Returns:
            Number of checkpoints available.
        """
        if self._checkpoint_repo is None:
            return 0

        _, total = await self._checkpoint_repo.list_checkpoints(limit=1, offset=0)
        return total

    async def get_checkpoint_timestamp(self, sequence: int) -> datetime | None:
        """Get timestamp of checkpoint at given sequence (RT-5).

        Per RT-5: Used for calculating checkpoint age in metrics.

        Args:
            sequence: Checkpoint sequence number.

        Returns:
            Checkpoint timestamp, or None if not found.
        """
        if self._checkpoint_repo is None:
            return None

        checkpoint = await self._checkpoint_repo.get_checkpoint_for_sequence(sequence)
        if checkpoint is None:
            return None

        return checkpoint.timestamp

    async def get_latest_checkpoint(self) -> CheckpointAnchor | None:
        """Get latest checkpoint anchor (RT-5, ADR-8).

        Per RT-5: Fallback to checkpoint anchor when API unavailable.
        Per ADR-8: Checkpoint anchors for offline verification.

        Returns:
            Latest checkpoint as CheckpointAnchor model, or None if no checkpoints.
        """
        if self._checkpoint_repo is None:
            return None

        checkpoints, _ = await self._checkpoint_repo.list_checkpoints(limit=1, offset=0)
        if not checkpoints:
            return None

        cp = checkpoints[0]
        return CheckpointAnchor(
            checkpoint_id=cp.checkpoint_id,
            sequence_start=1,  # All checkpoints start from genesis
            sequence_end=cp.event_sequence,
            merkle_root=cp.anchor_hash,
            created_at=cp.timestamp,
            anchor_type=cp.anchor_type
            if cp.anchor_type in ("genesis", "rfc3161", "pending")
            else "pending",
            anchor_reference=None,
            event_count=cp.event_sequence,
        )

    # =========================================================================
    # Cessation Status Methods (Story 7.5, Task 3 - FR42, CT-13)
    # =========================================================================

    async def is_system_ceased(self) -> bool:
        """Check if the system has permanently ceased (FR42).

        Per FR42: Read-only access indefinitely after cessation.
        Per CT-13: Reads are ALWAYS allowed, even after cessation.

        This method is for informational purposes to include status
        in responses. It does NOT block any operations.

        Returns:
            True if system has permanently ceased, False otherwise.
        """
        if self._freeze_checker is None:
            return False
        return await self._freeze_checker.is_frozen()

    async def get_cessation_details(self) -> Optional["CessationDetails"]:
        """Get details about the cessation state (FR42).

        Returns full cessation details including ceased_at timestamp,
        final_sequence_number, and reason. Used for including in
        API responses to inform observers.

        Per CT-11: Silent failure destroys legitimacy -> observers
        must know when they're reading from a ceased system.

        Returns:
            CessationDetails if system is ceased, None otherwise.
        """
        if self._freeze_checker is None:
            return None
        return await self._freeze_checker.get_freeze_details()

    async def get_cessation_status_for_response(self) -> dict | None:
        """Get cessation status formatted for API responses (AC5).

        Returns a dictionary suitable for including in API responses
        as cessation_info. Only returns data if system is ceased.

        Per AC5: CeasedStatusHeader SHALL be included in all read
        responses after cessation.

        Returns:
            Dictionary with cessation info if ceased, None otherwise.
            Dictionary format:
            {
                "system_status": "CEASED",
                "ceased_at": "ISO timestamp",
                "final_sequence_number": int,
                "cessation_reason": "reason string"
            }
        """
        details = await self.get_cessation_details()
        if details is None:
            return None

        return {
            "system_status": "CEASED",
            "ceased_at": details.ceased_at.isoformat(),
            "final_sequence_number": details.final_sequence_number,
            "cessation_reason": details.reason,
        }
