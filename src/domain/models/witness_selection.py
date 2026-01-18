"""Witness selection domain models (FR59, FR61).

Provides domain models for verifiable witness selection including
selection records and seed combination.

Constitutional Constraints:
- FR59: Witness selection uses verifiable randomness seeded from hash chain
- FR61: External entropy source required
- CT-12: Witnessing creates accountability - selection must be verifiable
"""

from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from src.domain.models.signable import SignableContent

# Selection algorithm version for reproducibility
# External observers MUST be able to verify selection by re-running algorithm
SELECTION_ALGORITHM_VERSION = "1.0.0"


@dataclass(frozen=True)
class WitnessSelectionSeed:
    """Combined seed for verifiable witness selection (FR59, FR61).

    Constitutional Constraint (FR59):
    System SHALL select witnesses using verifiable randomness seeded
    from previous hash chain state.

    Constitutional Constraint (FR61):
    External entropy source required (NFR22).

    The seed combines external entropy with hash chain state to ensure:
    1. Unpredictability (from external entropy)
    2. Determinism given inputs (for verification)
    3. Binding to event sequence (from hash chain)

    Attributes:
        external_entropy: Bytes from external source (FR61)
        chain_hash: Latest hash chain value (FR59)
        combined_seed: SHA-256(external_entropy || chain_hash)
    """

    external_entropy: bytes
    chain_hash: str
    combined_seed: bytes

    @classmethod
    def combine(cls, external: bytes, chain_hash: str) -> WitnessSelectionSeed:
        """Combine external entropy with hash chain for verifiable seed.

        Combination method (v1.0.0):
        1. Concatenate: external_entropy || chain_hash.encode('utf-8')
        2. SHA-256 hash the concatenation
        3. Result is the combined seed

        This ensures:
        - Different external entropy → different seed
        - Different chain state → different seed
        - Deterministic given same inputs

        Args:
            external: External entropy bytes (minimum 32 bytes recommended)
            chain_hash: Latest hash chain value (64 hex characters)

        Returns:
            WitnessSelectionSeed with combined seed.
        """
        data = external + chain_hash.encode("utf-8")
        combined = hashlib.sha256(data).digest()

        return cls(
            external_entropy=external,
            chain_hash=chain_hash,
            combined_seed=combined,
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize seed for storage/transmission."""
        return {
            "external_entropy": base64.b64encode(self.external_entropy).decode("utf-8"),
            "chain_hash": self.chain_hash,
            "combined_seed": base64.b64encode(self.combined_seed).decode("utf-8"),
        }


@dataclass(frozen=True)
class WitnessSelectionRecord:
    """Record of a verifiable witness selection (FR59).

    Contains all information needed for external observers to verify
    that witness selection was fair and deterministic.

    Constitutional Constraint (FR59):
    Selection record MUST include seed, source, and selected witness
    to enable verification by re-running algorithm.

    Constitutional Constraint (CT-12):
    Witnessing creates accountability - selection must be auditable.

    Attributes:
        random_seed: Combined entropy + hash chain seed (bytes)
        seed_source: Source identifier (e.g., "external:random.org+chain:abc123")
        selected_witness_id: The selected witness ID
        pool_snapshot: Ordered list of available witnesses at selection time
        algorithm_version: Selection algorithm version for reproducibility
        selected_at: UTC timestamp of selection
    """

    random_seed: bytes
    seed_source: str
    selected_witness_id: str
    pool_snapshot: tuple[str, ...] = field(default_factory=tuple)
    algorithm_version: str = SELECTION_ALGORITHM_VERSION
    selected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def verify_selection(self) -> bool:
        """Verify that selection is consistent with recorded data.

        Re-runs the deterministic selection algorithm with the recorded
        seed and pool snapshot, comparing the result to the recorded
        selected witness.

        Returns:
            True if computed selection matches recorded selection.

        Raises:
            ValueError: If pool_snapshot is empty.
        """
        if not self.pool_snapshot:
            raise ValueError("Cannot verify selection: empty pool snapshot")

        # Re-run deterministic selection algorithm
        computed_witness = deterministic_select(self.random_seed, self.pool_snapshot)
        return computed_witness == self.selected_witness_id

    def to_dict(self) -> dict[str, Any]:
        """Serialize record for storage/transmission."""
        return {
            "random_seed": base64.b64encode(self.random_seed).decode("utf-8"),
            "seed_source": self.seed_source,
            "selected_witness_id": self.selected_witness_id,
            "pool_snapshot": list(self.pool_snapshot),
            "algorithm_version": self.algorithm_version,
            "selected_at": self.selected_at.isoformat(),
        }

    def signable_content(self) -> SignableContent:
        """Get signable content for witnessing (CT-12).

        Returns content suitable for cryptographic signing,
        binding the selection to the constitutional record.
        """
        content = (
            f"witness_selection:"
            f"seed={base64.b64encode(self.random_seed).decode('utf-8')},"
            f"selected={self.selected_witness_id},"
            f"pool_size={len(self.pool_snapshot)},"
            f"algorithm={self.algorithm_version},"
            f"at={self.selected_at.isoformat()}"
        )
        return SignableContent(content.encode("utf-8"))


def deterministic_select(seed: bytes, pool: tuple[str, ...]) -> str:
    """Select witness deterministically from pool given seed.

    Algorithm (v1.0.0):
    1. Take first 8 bytes of seed
    2. Convert to unsigned big-endian integer
    3. Compute index = seed_int % len(pool)
    4. Return pool[index]

    This is verifiable: anyone with seed + pool can recompute selection.

    Args:
        seed: Combined seed bytes (at least 8 bytes required)
        pool: Ordered tuple of witness IDs

    Returns:
        Selected witness ID from pool.

    Raises:
        ValueError: If pool is empty or seed too short.
    """
    if not pool:
        raise ValueError("Cannot select from empty pool")
    if len(seed) < 8:
        raise ValueError("Seed must be at least 8 bytes")

    seed_int = int.from_bytes(seed[:8], "big")
    index = seed_int % len(pool)
    return pool[index]
