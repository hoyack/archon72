"""Witness selection domain events (FR59, FR60).

Provides event payloads for witness selection events.

Constitutional Constraints:
- FR59: Selection events include seed, source, and selected witness
- FR60: Pair rotation events track rotation enforcement
- CT-12: All events support witnessing and accountability
"""

from __future__ import annotations

import base64
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from src.domain.models.signable import SignableContent


# Event type constants
WITNESS_SELECTION_EVENT_TYPE = "witness.selection"
WITNESS_PAIR_ROTATION_EVENT_TYPE = "witness.pair_rotation"


@dataclass(frozen=True)
class WitnessSelectionEventPayload:
    """Event payload for witness selection (FR59).

    Records all information needed to verify that witness selection
    was fair and deterministic.

    Constitutional Constraint (FR59):
    Selection events MUST include seed, source, and selected witness
    to enable external verification.

    Attributes:
        random_seed: Base64 encoded combined seed
        seed_source: Source identifier (e.g., "external:random.org+chain:abc123")
        selected_witness_id: The selected witness ID
        pool_size: Number of available witnesses at selection time
        algorithm_version: Selection algorithm version for reproducibility
        selected_at: UTC timestamp of selection
    """

    random_seed: str  # Base64 encoded
    seed_source: str
    selected_witness_id: str
    pool_size: int
    algorithm_version: str
    selected_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def to_dict(self) -> dict[str, Any]:
        """Serialize payload for event writing."""
        return {
            "random_seed": self.random_seed,
            "seed_source": self.seed_source,
            "selected_witness_id": self.selected_witness_id,
            "pool_size": self.pool_size,
            "algorithm_version": self.algorithm_version,
            "selected_at": self.selected_at.isoformat(),
        }

    def signable_content(self) -> SignableContent:
        """Get signable content for witnessing (CT-12).

        Returns content suitable for cryptographic signing.
        """
        content = (
            f"witness_selection_event:"
            f"seed={self.random_seed[:32]}...,"  # Truncate for signable
            f"selected={self.selected_witness_id},"
            f"pool_size={self.pool_size},"
            f"algorithm={self.algorithm_version},"
            f"at={self.selected_at.isoformat()}"
        )
        return SignableContent(content.encode("utf-8"))

    @classmethod
    def from_seed_bytes(
        cls,
        seed: bytes,
        seed_source: str,
        selected_witness_id: str,
        pool_size: int,
        algorithm_version: str,
        selected_at: datetime | None = None,
    ) -> WitnessSelectionEventPayload:
        """Create payload from raw seed bytes.

        Convenience factory that handles base64 encoding.

        Args:
            seed: Raw seed bytes
            seed_source: Source identifier
            selected_witness_id: The selected witness ID
            pool_size: Number of available witnesses
            algorithm_version: Selection algorithm version
            selected_at: Timestamp (defaults to now)

        Returns:
            WitnessSelectionEventPayload with encoded seed.
        """
        return cls(
            random_seed=base64.b64encode(seed).decode("utf-8"),
            seed_source=seed_source,
            selected_witness_id=selected_witness_id,
            pool_size=pool_size,
            algorithm_version=algorithm_version,
            selected_at=selected_at or datetime.now(timezone.utc),
        )


@dataclass(frozen=True)
class WitnessPairRotationEventPayload:
    """Event payload for witness pair rotation tracking (FR60).

    Records pair rotation enforcement decisions for audit.

    Constitutional Constraint (FR60):
    No witness pair SHALL appear consecutively more than once per 24-hour period.

    Attributes:
        pair_key: Canonical pair key (e.g., "WITNESS:abc:WITNESS:xyz")
        witness_a_id: First witness ID
        witness_b_id: Second witness ID
        last_pair_time: When pair last appeared (None if first time)
        excluded_from_selection: True if pair was excluded due to FR60
        event_at: UTC timestamp of this event
    """

    pair_key: str
    witness_a_id: str
    witness_b_id: str
    last_pair_time: datetime | None
    excluded_from_selection: bool
    event_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def to_dict(self) -> dict[str, Any]:
        """Serialize payload for event writing."""
        return {
            "pair_key": self.pair_key,
            "witness_a_id": self.witness_a_id,
            "witness_b_id": self.witness_b_id,
            "last_pair_time": (
                self.last_pair_time.isoformat() if self.last_pair_time else None
            ),
            "excluded_from_selection": self.excluded_from_selection,
            "event_at": self.event_at.isoformat(),
        }

    def signable_content(self) -> SignableContent:
        """Get signable content for witnessing (CT-12).

        Returns content suitable for cryptographic signing.
        """
        content = (
            f"witness_pair_rotation:"
            f"pair={self.pair_key},"
            f"excluded={self.excluded_from_selection},"
            f"at={self.event_at.isoformat()}"
        )
        return SignableContent(content.encode("utf-8"))
