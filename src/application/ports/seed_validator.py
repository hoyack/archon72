"""Seed validator port definition (Story 6.9, FR124).

Defines the abstract interface for seed validation operations.
Infrastructure adapters must implement this protocol.

Constitutional Constraints:
- FR124: Seed source independence verification
- NFR22: Witness selection randomness SHALL include external entropy
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from src.domain.events.seed_validation import SeedValidationResult


@dataclass(frozen=True)
class SeedSourceValidation:
    """Result of validating entropy source independence.

    Attributes:
        source_id: The source that was validated.
        is_independent: Whether source meets independence criteria.
        validation_reason: Explanation of validation result.
        last_verified_at: When source was last verified.
    """

    source_id: str
    is_independent: bool
    validation_reason: str
    last_verified_at: Optional[datetime]


@dataclass(frozen=True)
class PredictabilityCheck:
    """Result of checking seed predictability.

    Attributes:
        is_predictable: Whether seed appears predictable.
        predictability_indicators: Detected indicators of predictability.
        recommendation: Action recommendation.
    """

    is_predictable: bool
    predictability_indicators: tuple[str, ...]
    recommendation: str


@dataclass(frozen=True)
class SeedUsageRecord:
    """Record of seed usage for audit trail.

    Attributes:
        seed_hash: Hash of the seed (not the seed itself).
        purpose: What the seed was used for.
        source_id: Source that provided entropy.
        used_at: When the seed was used.
        validation_result: Result of validation.
    """

    seed_hash: str
    purpose: str
    source_id: str
    used_at: datetime
    validation_result: SeedValidationResult


class SeedValidatorProtocol(ABC):
    """Abstract protocol for seed validation operations.

    All seed validator implementations must implement this interface.
    This enables dependency inversion and allows the application layer to
    remain independent of specific validation implementations.

    Constitutional Constraints:
    - FR124: Seed source independence verification
    - NFR22: Witness selection randomness SHALL include external entropy

    Production implementations may include:
    - ExternalSourceValidator: Validates external entropy sources
    - IndependenceAuditor: Audits source independence

    Development/Testing:
    - SeedValidatorStub: Configurable test double
    """

    @abstractmethod
    async def validate_seed_source(
        self,
        source_id: str,
        purpose: str,
    ) -> SeedSourceValidation:
        """Validate entropy source independence (FR124).

        Independence criteria:
        - Source not controlled by system operator
        - Source provides cryptographically secure randomness
        - Source has verifiable public reputation
        - Source freshness can be verified

        Args:
            source_id: Identifier of entropy source.
            purpose: What the seed will be used for.

        Returns:
            SeedSourceValidation with validation result.
        """
        ...

    @abstractmethod
    async def check_predictability(
        self,
        seed_bytes: bytes,
        context: str,
    ) -> PredictabilityCheck:
        """Check if seed appears predictable.

        Predictability checks:
        - No repeating patterns in recent seeds
        - No correlation with system time
        - No correlation with other system state

        Args:
            seed_bytes: The seed bytes to check.
            context: Context for the check.

        Returns:
            PredictabilityCheck with analysis result.
        """
        ...

    @abstractmethod
    async def record_seed_usage(
        self,
        seed_hash: str,
        purpose: str,
        source_id: str,
    ) -> None:
        """Record seed usage for audit trail (CT-12).

        Args:
            seed_hash: Hash of the seed (not the seed itself).
            purpose: What the seed was used for.
            source_id: Source that provided entropy.
        """
        ...

    @abstractmethod
    async def get_seed_audit_trail(
        self,
        purpose: str,
        limit: int = 100,
    ) -> list[SeedUsageRecord]:
        """Get seed usage audit trail for observers.

        Args:
            purpose: Filter by purpose (or empty for all).
            limit: Maximum number of records to return.

        Returns:
            List of seed usage records.
        """
        ...
