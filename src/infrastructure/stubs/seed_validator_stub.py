"""Seed validator stub (Story 6.9, FR124).

In-memory implementation for testing and development.

Constitutional Constraints:
- FR124: Witness selection randomness SHALL combine hash chain state
         + external entropy source meeting independence criteria
- CT-12: Witnessing creates accountability -> signable audit trail
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from src.application.ports.seed_validator import (
    PredictabilityCheck,
    SeedSourceValidation,
    SeedUsageRecord,
    SeedValidatorProtocol,
)
from src.domain.events.seed_validation import SeedValidationResult


@dataclass
class SeedValidatorStub(SeedValidatorProtocol):
    """In-memory stub for seed validation.

    Stores validation results and usage records for testing.
    Supports configurable responses for different test scenarios.

    FR124: Seed independence verification before use.
    """

    # Storage for seed usage records
    _usage_records: list[SeedUsageRecord] = field(default_factory=list)

    # Configurable source validations
    _source_validations: dict[str, SeedSourceValidation] = field(default_factory=dict)

    # Configurable predictability results
    _predictability_results: dict[str, PredictabilityCheck] = field(default_factory=dict)

    # Default independence status for new sources
    _default_is_independent: bool = True

    # Default predictability status for seeds without specific config
    _default_is_predictable: bool = False

    async def validate_seed_source(
        self,
        source_id: str,
        purpose: str,
    ) -> SeedSourceValidation:
        """Validate a seed source for independence.

        Args:
            source_id: Source to validate.
            purpose: What the seed will be used for.

        Returns:
            Validation result with independence status.
        """
        if source_id in self._source_validations:
            return self._source_validations[source_id]

        # Return default validation
        return SeedSourceValidation(
            source_id=source_id,
            is_independent=self._default_is_independent,
            validation_reason="stub_validation" if self._default_is_independent else "stub_rejection",
            last_verified_at=datetime.now(timezone.utc),
        )

    async def check_predictability(
        self,
        seed_bytes: bytes,
        context: str,
    ) -> PredictabilityCheck:
        """Check if a seed is predictable.

        Args:
            seed_bytes: Seed bytes to check.
            context: Context for the check.

        Returns:
            Predictability check result.
        """
        # Convert bytes to string key
        key = f"{seed_bytes.hex()}:{context}"
        if key in self._predictability_results:
            return self._predictability_results[key]

        # Return result based on default predictability
        if self._default_is_predictable:
            return PredictabilityCheck(
                is_predictable=True,
                predictability_indicators=("default_config",),
                recommendation="Predictable seed (default config)",
            )
        return PredictabilityCheck(
            is_predictable=False,
            predictability_indicators=(),
            recommendation="Seed appears random",
        )

    async def record_seed_usage(
        self,
        seed_hash: str,
        purpose: str,
        source_id: str,
    ) -> None:
        """Record seed usage for audit trail.

        Args:
            seed_hash: Hash of the seed (not the seed itself).
            purpose: Purpose of usage.
            source_id: Source that provided the seed.
        """
        record = SeedUsageRecord(
            seed_hash=seed_hash,
            purpose=purpose,
            source_id=source_id,
            used_at=datetime.now(timezone.utc),
            validation_result=SeedValidationResult.VALID,
        )
        self._usage_records.append(record)

    async def get_seed_audit_trail(
        self,
        purpose: str,
        limit: int = 100,
    ) -> list[SeedUsageRecord]:
        """Get seed usage audit trail.

        Args:
            purpose: Filter by purpose (empty string for all).
            limit: Maximum records to return.

        Returns:
            List of usage records.
        """
        records = self._usage_records
        if purpose:
            records = [r for r in records if r.purpose == purpose]

        # Return most recent first, up to limit
        sorted_records = sorted(records, key=lambda r: r.used_at, reverse=True)
        return sorted_records[:limit]

    # Test helper methods

    def set_source_validation(
        self,
        source_id: str,
        validation: SeedSourceValidation,
    ) -> None:
        """Set validation result for a source.

        Args:
            source_id: Source ID.
            validation: Validation to return.
        """
        self._source_validations[source_id] = validation

    def set_source_independent(
        self,
        source_id: str,
        is_independent: bool,
        validation_reason: str = "test_configuration",
    ) -> None:
        """Set independence status for a source.

        Args:
            source_id: Source ID.
            is_independent: Whether source is independent.
            validation_reason: Reason for validation result.
        """
        self._source_validations[source_id] = SeedSourceValidation(
            source_id=source_id,
            is_independent=is_independent,
            validation_reason=validation_reason,
            last_verified_at=datetime.now(timezone.utc),
        )

    def set_predictability(
        self,
        seed_bytes: bytes,
        context: str,
        is_predictable: bool,
        indicators: tuple[str, ...] = (),
        recommendation: str = "",
    ) -> None:
        """Set predictability result for a seed.

        Args:
            seed_bytes: Seed bytes.
            context: Context.
            is_predictable: Whether seed is predictable.
            indicators: Predictability indicators.
            recommendation: Action recommendation.
        """
        key = f"{seed_bytes.hex()}:{context}"
        self._predictability_results[key] = PredictabilityCheck(
            is_predictable=is_predictable,
            predictability_indicators=indicators,
            recommendation=recommendation or ("Predictable seed" if is_predictable else "Seed appears random"),
        )

    def set_default_independence(self, is_independent: bool) -> None:
        """Set default independence status for new sources.

        Args:
            is_independent: Default independence status.
        """
        self._default_is_independent = is_independent

    def set_default_predictability(self, is_predictable: bool) -> None:
        """Set default predictability status for seeds.

        Args:
            is_predictable: Default predictability status.
        """
        self._default_is_predictable = is_predictable

    def get_usage_records(self) -> list[SeedUsageRecord]:
        """Get all usage records for verification.

        Returns:
            List of all usage records.
        """
        return list(self._usage_records)

    def add_usage_record(self, record: SeedUsageRecord) -> None:
        """Add a usage record directly for testing.

        Args:
            record: Record to add.
        """
        self._usage_records.append(record)

    def clear(self) -> None:
        """Clear all stored data for test isolation."""
        self._usage_records.clear()
        self._source_validations.clear()
        self._predictability_results.clear()
        self._default_is_independent = True
