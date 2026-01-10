"""Seed validation service (Story 6.9, FR124).

This service orchestrates seed validation operations including
source independence verification and predictability checks.

Constitutional Constraints:
- FR124: Seed source independence verification
- NFR22: Witness selection randomness SHALL include external entropy
- CT-11: Silent failure destroys legitimacy -> HALT CHECK FIRST
- CT-12: Witnessing creates accountability -> All validations logged

Architecture Pattern:
    SeedValidationService orchestrates FR124 compliance:

    validate_and_get_seed(purpose):
      ├─ halt_checker.is_halted()           # HALT FIRST rule
      ├─ entropy_source.get_entropy()       # Get external entropy
      ├─ validator.validate_seed_source()   # Check independence
      ├─ validator.check_predictability()   # Check predictability
      └─ If validation fails:
           ├─ Create SeedRejectedEvent
           └─ Raise appropriate error
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

import structlog

from src.application.ports.entropy_source import EntropySourceProtocol
from src.application.ports.halt_checker import HaltChecker
from src.application.ports.seed_validator import (
    SeedUsageRecord,
    SeedValidatorProtocol,
)
from src.domain.errors.topic_manipulation import (
    PredictableSeedError,
    SeedSourceDependenceError,
)
from src.domain.errors.writer import SystemHaltedError
from src.domain.events.seed_validation import (
    SeedRejectedEventPayload,
    SeedValidationEventPayload,
    SeedValidationResult,
)

logger = structlog.get_logger()


@dataclass
class ValidatedSeed:
    """A validated seed ready for use.

    Attributes:
        seed_bytes: The validated seed bytes.
        seed_hash: Hash of the seed for audit trail.
        source_id: Source that provided entropy.
        validation_id: Unique identifier for this validation.
        validation_event: Event documenting the validation.
    """

    seed_bytes: bytes
    seed_hash: str
    source_id: str
    validation_id: str
    validation_event: SeedValidationEventPayload


class SeedValidationService:
    """Application service for seed validation (FR124).

    This service provides the primary interface for:
    - Validating entropy source independence (AC4)
    - Checking seed predictability (AC4)
    - Creating audit trail for seed usage (AC4)

    HALT FIRST Rule:
        Every operation checks halt state before proceeding.
        Never retry after SystemHaltedError.

    Attributes:
        _halt_checker: Interface for checking halt state.
        _validator: Interface for seed validation.
        _entropy_source: Interface for external entropy.
    """

    def __init__(
        self,
        halt_checker: HaltChecker,
        validator: SeedValidatorProtocol,
        entropy_source: EntropySourceProtocol,
    ) -> None:
        """Initialize the service with required dependencies.

        Args:
            halt_checker: Interface for checking halt state.
            validator: Interface for seed validation.
            entropy_source: Interface for external entropy.

        Raises:
            TypeError: If any required dependency is None.
        """
        if halt_checker is None:
            raise TypeError("halt_checker is required")
        if validator is None:
            raise TypeError("validator is required")
        if entropy_source is None:
            raise TypeError("entropy_source is required")

        self._halt_checker = halt_checker
        self._validator = validator
        self._entropy_source = entropy_source

    async def validate_and_get_seed(
        self,
        purpose: str,
    ) -> ValidatedSeed:
        """Validate and get a seed for the specified purpose (AC4).

        FR124: Witness selection randomness SHALL combine hash chain state
               + external entropy source meeting independence criteria.

        Flow:
            1. HALT CHECK (fail fast if halted)
            2. Get entropy from external source
            3. Validate source independence
            4. Check for predictability
            5. If any validation fails: create event, raise error
            6. Create validation event and record usage
            7. Return validated seed

        Args:
            purpose: What the seed will be used for.

        Returns:
            ValidatedSeed with validated seed bytes.

        Raises:
            SystemHaltedError: If system is halted (HALT FIRST rule).
            SeedSourceDependenceError: If source independence check fails.
            PredictableSeedError: If seed appears predictable.
        """
        # HALT FIRST - Check before any operation
        if await self._halt_checker.is_halted():
            logger.warning(
                "seed_validation_blocked_halted",
                seed_purpose=purpose,
            )
            raise SystemHaltedError("System halted - cannot validate seed")

        validation_id = str(uuid4())

        # Get entropy from external source
        source_id = await self._entropy_source.get_source_identifier()
        try:
            seed_bytes = await self._entropy_source.get_entropy()
        except Exception as e:
            # Create rejection event for entropy failure
            rejection_event = SeedRejectedEventPayload(
                rejection_id=str(uuid4()),
                seed_purpose=purpose,
                rejection_reason=f"Entropy unavailable: {e}",
                attempted_source=source_id,
                rejected_at=datetime.now(timezone.utc),
            )

            logger.error(
                "entropy_source_failed",
                seed_purpose=purpose,
                source_id=source_id,
                error=str(e),
            )

            # Note: Per AC4, failed validation triggers alert not halt
            # But entropy failure is critical - we still raise
            raise

        # Validate source independence (FR124)
        source_validation = await self._validator.validate_seed_source(
            source_id,
            purpose,
        )

        if not source_validation.is_independent:
            # Create rejection event
            rejection_event = SeedRejectedEventPayload(
                rejection_id=str(uuid4()),
                seed_purpose=purpose,
                rejection_reason=source_validation.validation_reason,
                attempted_source=source_id,
                rejected_at=datetime.now(timezone.utc),
            )

            logger.warning(
                "seed_source_not_independent",
                seed_purpose=purpose,
                source_id=source_id,
                validation_reason=source_validation.validation_reason,
            )

            raise SeedSourceDependenceError(
                seed_purpose=purpose,
                failed_source=source_id,
            )

        # Check for predictability
        predictability = await self._validator.check_predictability(
            seed_bytes,
            context=purpose,
        )

        if predictability.is_predictable:
            # Create rejection event
            rejection_event = SeedRejectedEventPayload(
                rejection_id=str(uuid4()),
                seed_purpose=purpose,
                rejection_reason=predictability.recommendation,
                attempted_source=source_id,
                rejected_at=datetime.now(timezone.utc),
            )

            logger.warning(
                "seed_predictable_detected",
                seed_purpose=purpose,
                source_id=source_id,
                indicators=predictability.predictability_indicators,
            )

            raise PredictableSeedError(
                seed_purpose=purpose,
                predictability_reason=predictability.recommendation,
            )

        # All validations passed - create success event
        seed_hash = hashlib.sha256(seed_bytes).hexdigest()
        validation_event = SeedValidationEventPayload(
            validation_id=validation_id,
            seed_purpose=purpose,
            entropy_source_id=source_id,
            independence_verified=True,
            validation_result=SeedValidationResult.VALID,
            validated_at=datetime.now(timezone.utc),
        )

        # Record usage for audit trail (CT-12)
        await self._validator.record_seed_usage(
            seed_hash=seed_hash,
            purpose=purpose,
            source_id=source_id,
        )

        logger.info(
            "seed_validation_success",
            validation_id=validation_id,
            seed_purpose=purpose,
            source_id=source_id,
            seed_hash=seed_hash[:16] + "...",  # Truncate for logging
        )

        return ValidatedSeed(
            seed_bytes=seed_bytes,
            seed_hash=seed_hash,
            source_id=source_id,
            validation_id=validation_id,
            validation_event=validation_event,
        )

    async def get_seed_audit_trail(
        self,
        purpose: str = "",
        limit: int = 100,
    ) -> list[SeedUsageRecord]:
        """Get seed usage audit trail for observers (AC4).

        Flow:
            1. HALT CHECK (fail fast if halted)
            2. Query audit trail from validator
            3. Return records

        Args:
            purpose: Filter by purpose (empty for all).
            limit: Maximum number of records.

        Returns:
            List of seed usage records.

        Raises:
            SystemHaltedError: If system is halted (HALT FIRST rule).
        """
        # HALT FIRST - Check before any operation
        if await self._halt_checker.is_halted():
            logger.warning("audit_trail_query_blocked_halted")
            raise SystemHaltedError("System halted - cannot query audit trail")

        records = await self._validator.get_seed_audit_trail(
            purpose=purpose,
            limit=limit,
        )

        logger.debug(
            "seed_audit_trail_queried",
            purpose=purpose,
            record_count=len(records),
        )

        return records
