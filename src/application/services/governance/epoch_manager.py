"""Epoch Manager Service for Merkle tree epoch lifecycle.

Story: consent-gov-1.7: Merkle Tree Proof-of-Inclusion

This service manages epoch lifecycle including:
- Checking epoch boundaries (events or time-based)
- Creating epochs when boundaries are reached
- Publishing Merkle root events to the ledger

Constitutional Constraints:
- AD-7: Merkle tree proof-of-inclusion
- NFR-CONST-02: Proof-of-inclusion for any entry
- AC6: Merkle root published to ledger at epoch boundaries

References:
- [Source: _bmad-output/planning-artifacts/governance-architecture.md#Proof-of-Inclusion (Locked)]
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING
from uuid import uuid4

from src.application.ports.governance.merkle_tree_port import EpochConfig, EpochInfo
from src.domain.governance.events.hash_algorithms import DEFAULT_ALGORITHM
from src.domain.governance.events.merkle_tree import MerkleTree

if TYPE_CHECKING:
    from src.application.ports.governance.ledger_port import (
        GovernanceLedgerPort,
    )
    from src.domain.ports.time_authority import TimeAuthority


@dataclass
class EpochManagerService:
    """Service for managing Merkle tree epochs.

    This service handles epoch lifecycle:
    1. Check if current sequence triggers epoch boundary
    2. Build Merkle tree from epoch events
    3. Publish root to ledger as governance event

    Attributes:
        ledger_port: Port for reading events and publishing roots.
        time_authority: Injected time authority for timestamps.
        config: Epoch configuration (events per epoch, time-based, etc.).
        _built_epochs: In-memory cache of built epochs.
    """

    ledger_port: GovernanceLedgerPort
    time_authority: TimeAuthority
    config: EpochConfig = field(default_factory=EpochConfig)
    _built_epochs: dict[int, EpochInfo] = field(default_factory=dict)

    def _compute_epoch_id(self, sequence: int) -> int:
        """Compute epoch ID for a given sequence number.

        Args:
            sequence: Ledger sequence number.

        Returns:
            Epoch ID (0-indexed).
        """
        if self.config.events_per_epoch <= 0:
            return 0
        return (sequence - 1) // self.config.events_per_epoch

    def _get_epoch_sequence_range(self, epoch_id: int) -> tuple[int, int]:
        """Get sequence range for an epoch.

        Args:
            epoch_id: Epoch identifier.

        Returns:
            Tuple of (start_sequence, end_sequence) inclusive.
        """
        start = epoch_id * self.config.events_per_epoch + 1
        end = (epoch_id + 1) * self.config.events_per_epoch
        return start, end

    async def check_epoch_boundary(self, current_sequence: int) -> bool:
        """Check if current sequence triggers epoch boundary.

        An epoch boundary is reached when:
        - current_sequence % events_per_epoch == 0

        Args:
            current_sequence: The latest sequence number.

        Returns:
            True if a new epoch should be built.
        """
        if self.config.events_per_epoch <= 0:
            return False

        # Check if we've completed an epoch
        if current_sequence % self.config.events_per_epoch == 0:
            epoch_id = self._compute_epoch_id(current_sequence)
            # Only trigger if epoch not already built
            return epoch_id not in self._built_epochs

        return False

    async def build_epoch(
        self,
        epoch_id: int,
        algorithm: str = DEFAULT_ALGORITHM,
    ) -> EpochInfo:
        """Build Merkle tree for an epoch.

        Reads events from ledger, builds tree, and caches result.
        Does NOT publish to ledger (call publish_epoch_root for that).

        Args:
            epoch_id: Identifier for this epoch.
            algorithm: Hash algorithm for tree construction.

        Returns:
            EpochInfo with computed root and metadata.

        Raises:
            ValueError: If epoch has no events or events are missing.
        """
        from src.application.ports.governance.ledger_port import LedgerReadOptions

        start_sequence, end_sequence = self._get_epoch_sequence_range(epoch_id)

        # Read events in the epoch range
        options = LedgerReadOptions(
            start_sequence=start_sequence,
            end_sequence=end_sequence,
            limit=self.config.events_per_epoch + 10,  # Buffer for safety
        )
        events = await self.ledger_port.read_events(options)

        if not events:
            raise ValueError(
                f"No events found for epoch {epoch_id} "
                f"(sequences {start_sequence}-{end_sequence})"
            )

        # Verify we have all events (no gaps)
        sequences = {e.sequence for e in events}
        expected_end = min(end_sequence, max(sequences))
        for seq in range(start_sequence, expected_end + 1):
            if seq not in sequences:
                raise ValueError(
                    f"Gap in sequence: missing event {seq} in epoch {epoch_id}"
                )

        # Extract event hashes and build tree
        event_hashes = [e.event.hash for e in events if e.event.hash]
        if not event_hashes:
            raise ValueError(f"No hashed events found in epoch {epoch_id}")

        tree = MerkleTree(event_hashes, algorithm)

        # Create epoch info
        epoch_info = EpochInfo(
            epoch_id=epoch_id,
            root_hash=tree.root,
            algorithm=algorithm,
            start_sequence=start_sequence,
            end_sequence=events[-1].sequence,  # Actual end
            event_count=len(events),
            created_at=self.time_authority.now(),
            root_event_id=None,  # Set after publishing
        )

        # Cache the epoch
        self._built_epochs[epoch_id] = epoch_info

        return epoch_info

    async def publish_epoch_root(
        self,
        epoch_info: EpochInfo,
        actor_id: str = "system",
    ) -> EpochInfo:
        """Publish epoch root to ledger as governance event.

        Creates a 'ledger.merkle.root_published' event with the
        epoch root and metadata.

        Args:
            epoch_info: The epoch to publish.
            actor_id: Actor ID for the event (default: 'system').

        Returns:
            Updated EpochInfo with root_event_id set.
        """
        from src.domain.governance.events.event_envelope import (
            EventMetadata,
            GovernanceEvent,
        )
        from src.domain.governance.events.hash_chain import add_hash_to_event

        # Create the root publication event
        event_id = uuid4()
        trace_id = uuid4()

        metadata = EventMetadata(
            event_id=event_id,
            event_type="ledger.merkle.root_published",
            timestamp=self.time_authority.now(),
            actor_id=actor_id,
            schema_version="1.0.0",
            trace_id=trace_id,
        )

        payload = {
            "epoch": epoch_info.epoch_id,
            "merkle_root": epoch_info.root_hash,
            "start_sequence": epoch_info.start_sequence,
            "end_sequence": epoch_info.end_sequence,
            "event_count": epoch_info.event_count,
            "algorithm": epoch_info.algorithm,
        }

        event = GovernanceEvent(metadata=metadata, payload=payload)

        # Get previous hash for chaining
        latest = await self.ledger_port.get_latest_event()
        prev_hash = latest.event.hash if latest else None

        # Add hash to event
        hashed_event = add_hash_to_event(event, prev_hash, epoch_info.algorithm)

        # Persist to ledger
        persisted = await self.ledger_port.append_event(hashed_event)

        # Update epoch info with event ID
        updated_info = EpochInfo(
            epoch_id=epoch_info.epoch_id,
            root_hash=epoch_info.root_hash,
            algorithm=epoch_info.algorithm,
            start_sequence=epoch_info.start_sequence,
            end_sequence=epoch_info.end_sequence,
            event_count=epoch_info.event_count,
            created_at=epoch_info.created_at,
            root_event_id=persisted.event_id,
        )

        # Update cache
        self._built_epochs[epoch_info.epoch_id] = updated_info

        return updated_info

    async def create_epoch_if_needed(
        self,
        current_sequence: int,
        algorithm: str = DEFAULT_ALGORITHM,
        publish: bool = True,
    ) -> EpochInfo | None:
        """Create a new epoch if boundary is reached.

        Convenience method that checks boundary, builds epoch,
        and optionally publishes root.

        Args:
            current_sequence: The latest sequence number.
            algorithm: Hash algorithm for tree construction.
            publish: Whether to publish root to ledger.

        Returns:
            EpochInfo if a new epoch was created, None otherwise.
        """
        if not await self.check_epoch_boundary(current_sequence):
            return None

        epoch_id = self._compute_epoch_id(current_sequence)
        epoch_info = await self.build_epoch(epoch_id, algorithm)

        if publish:
            epoch_info = await self.publish_epoch_root(epoch_info)

        return epoch_info

    def get_epoch_info(self, epoch_id: int) -> EpochInfo | None:
        """Get cached epoch info.

        Args:
            epoch_id: Epoch identifier.

        Returns:
            EpochInfo if built, None otherwise.
        """
        return self._built_epochs.get(epoch_id)

    def get_epoch_for_sequence(self, sequence: int) -> int:
        """Determine which epoch contains a sequence number.

        Args:
            sequence: Ledger sequence number.

        Returns:
            Epoch ID for this sequence.
        """
        return self._compute_epoch_id(sequence)

    def list_epochs(self) -> list[EpochInfo]:
        """List all built epochs.

        Returns:
            List of EpochInfo ordered by epoch_id.
        """
        return sorted(self._built_epochs.values(), key=lambda e: e.epoch_id)

    def get_latest_epoch(self) -> EpochInfo | None:
        """Get the most recently built epoch.

        Returns:
            EpochInfo for latest epoch, or None if no epochs exist.
        """
        if not self._built_epochs:
            return None
        max_id = max(self._built_epochs.keys())
        return self._built_epochs[max_id]

    def get_config(self) -> EpochConfig:
        """Get current epoch configuration.

        Returns:
            Current EpochConfig.
        """
        return self.config

    def update_config(self, config: EpochConfig) -> None:
        """Update epoch configuration.

        Note: Changes only affect future epochs.

        Args:
            config: New configuration settings.
        """
        self.config = config
