"""Seed validation domain events (Story 6.9, FR124).

This module defines event payloads for seed validation and rejection,
supporting the randomness gaming defense.

Constitutional Constraints:
- FR124: Witness selection randomness SHALL combine hash chain state
         + external entropy source meeting independence criteria

Constitutional Truths Honored:
- CT-11: Silent failure destroys legitimacy -> Events surface validation
- CT-12: Witnessing creates accountability -> signable_content() for audit
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

# Event type constants for use in Event.event_type
SEED_VALIDATION_EVENT_TYPE = "seed.validation"
SEED_REJECTED_EVENT_TYPE = "seed.rejected"


class SeedValidationResult(str, Enum):
    """Results of seed validation.

    Used to categorize validation outcomes for audit and decision-making.

    FR124: Seed must pass independence verification before use.
    """

    VALID = "valid"
    PREDICTABLE_REJECTED = "predictable_rejected"
    SOURCE_DEPENDENT = "source_dependent"
    ENTROPY_UNAVAILABLE = "entropy_unavailable"


@dataclass(frozen=True)
class SeedValidationEventPayload:
    """Payload for seed validation events (FR124).

    Created when a seed is validated before use in system operations.
    Records the validation result for audit trail.

    FR124: Witness selection randomness SHALL combine hash chain state
           + external entropy source meeting independence criteria.

    Attributes:
        validation_id: Unique identifier for this validation.
        seed_purpose: What the seed will be used for.
        entropy_source_id: Source that provided the entropy.
        independence_verified: Whether source independence was verified.
        validation_result: Outcome of validation.
        validated_at: When validation occurred.

    Raises:
        ValueError: If required fields are empty.
    """

    validation_id: str
    seed_purpose: str
    entropy_source_id: str
    independence_verified: bool
    validation_result: SeedValidationResult
    validated_at: datetime

    def __post_init__(self) -> None:
        """Validate fields after initialization.

        Raises:
            ValueError: If validation fails.
        """
        if not isinstance(self.validation_id, str) or not self.validation_id.strip():
            raise ValueError(
                "FR124: SeedValidationEventPayload validation failed - "
                "validation_id must be non-empty string"
            )
        if not isinstance(self.seed_purpose, str) or not self.seed_purpose.strip():
            raise ValueError(
                "FR124: SeedValidationEventPayload validation failed - "
                "seed_purpose must be non-empty string"
            )

    def to_dict(self) -> dict[str, Any]:
        """Convert to serializable dictionary.

        Returns:
            Dictionary representation suitable for JSON serialization.
        """
        return {
            "validation_id": self.validation_id,
            "seed_purpose": self.seed_purpose,
            "entropy_source_id": self.entropy_source_id,
            "independence_verified": self.independence_verified,
            "validation_result": self.validation_result.value,
            "validated_at": self.validated_at.isoformat(),
        }

    def signable_content(self) -> bytes:
        """Get deterministic bytes for signing (CT-12).

        Returns canonical JSON encoding for cryptographic signing,
        ensuring witnessing creates accountability.

        Returns:
            Deterministic bytes representation for signing.
        """
        canonical = {
            "validation_id": self.validation_id,
            "seed_purpose": self.seed_purpose,
            "entropy_source_id": self.entropy_source_id,
            "independence_verified": self.independence_verified,
            "validation_result": self.validation_result.value,
            "validated_at": self.validated_at.isoformat(),
        }
        return json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")


@dataclass(frozen=True)
class SeedRejectedEventPayload:
    """Payload for seed rejection events (FR124).

    Created when a seed fails validation and is rejected.
    Important for audit trail of randomness gaming defense.

    FR124: Predictable seeds or dependent sources are rejected
           to prevent manipulation of witness selection.

    Attributes:
        rejection_id: Unique identifier for this rejection.
        seed_purpose: What the seed would have been used for.
        rejection_reason: Why the seed was rejected.
        attempted_source: Source that provided the rejected entropy.
        rejected_at: When rejection occurred.

    Raises:
        ValueError: If required fields are empty.
    """

    rejection_id: str
    seed_purpose: str
    rejection_reason: str
    attempted_source: str
    rejected_at: datetime

    def __post_init__(self) -> None:
        """Validate fields after initialization.

        Raises:
            ValueError: If validation fails.
        """
        if not isinstance(self.rejection_id, str) or not self.rejection_id.strip():
            raise ValueError(
                "FR124: SeedRejectedEventPayload validation failed - "
                "rejection_id must be non-empty string"
            )

    def to_dict(self) -> dict[str, Any]:
        """Convert to serializable dictionary.

        Returns:
            Dictionary representation suitable for JSON serialization.
        """
        return {
            "rejection_id": self.rejection_id,
            "seed_purpose": self.seed_purpose,
            "rejection_reason": self.rejection_reason,
            "attempted_source": self.attempted_source,
            "rejected_at": self.rejected_at.isoformat(),
        }

    def signable_content(self) -> bytes:
        """Get deterministic bytes for signing (CT-12).

        Returns:
            Deterministic bytes representation for signing.
        """
        canonical = {
            "rejection_id": self.rejection_id,
            "seed_purpose": self.seed_purpose,
            "rejection_reason": self.rejection_reason,
            "attempted_source": self.attempted_source,
            "rejected_at": self.rejected_at.isoformat(),
        }
        return json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")
