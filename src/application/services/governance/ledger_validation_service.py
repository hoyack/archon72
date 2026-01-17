"""Ledger Validation Service - Write-time validation orchestrator.

Story: consent-gov-1.4: Write-Time Validation

This service orchestrates all write-time validators to ensure events
are valid before being appended to the ledger. It implements fail-fast
semantics: validation stops on the first error.

Constitutional Principle:
    Write-time prevention is for ledger corruption. Policy violations
    are observer-time concerns (Knight-Witness).

Performance Budget:
    - Event type lookup: ≤1ms
    - Actor lookup: ≤3ms
    - Hash chain verification: ≤50ms
    - State machine resolution: ≤10ms
    - Total (worst case): ≤64ms

References:
    - [Source: _bmad-output/planning-artifacts/governance-architecture.md#Write-Time Prevention (Locked)]
    - AD-12: Write-time prevention
    - NFR-PERF-05: State machine ≤10ms
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from src.domain.governance.errors.validation_errors import WriteTimeValidationError
from src.domain.governance.events.event_envelope import GovernanceEvent

if TYPE_CHECKING:
    from src.application.services.governance.validators.actor_validator import (
        ActorValidator,
    )
    from src.application.services.governance.validators.event_type_validator import (
        EventTypeValidator,
    )
    from src.application.services.governance.validators.hash_chain_validator import (
        HashChainValidator,
    )
    from src.application.services.governance.validators.state_transition_validator import (
        StateTransitionValidator,
    )


@runtime_checkable
class EventValidator(Protocol):
    """Protocol for event validators.

    All validators must implement this async validate method.
    """

    async def validate(self, event: GovernanceEvent) -> None:
        """Validate an event.

        Args:
            event: The GovernanceEvent to validate.

        Raises:
            WriteTimeValidationError: If validation fails.
        """
        ...


@dataclass(frozen=True)
class ValidationResult:
    """Result of validation.

    Attributes:
        is_valid: Whether validation passed.
        error: The validation error if failed, None if passed.
        validator_name: Name of the validator that failed (if any).
    """

    is_valid: bool
    error: WriteTimeValidationError | None = None
    validator_name: str = ""


class LedgerValidationService:
    """Orchestrates write-time validation for governance events.

    Validates events BEFORE they are appended to the ledger.
    Implements fail-fast: stops on first validation error.

    Validators are executed in order of performance (fastest first):
    1. Event type validation (≤1ms) - in-memory lookup
    2. Actor validation (≤3ms) - cached projection
    3. State transition validation (≤10ms) - state machine rules
    4. Hash chain validation (≤50ms) - hash computation

    This ordering minimizes wasted work on invalid events.

    Constitutional Constraint:
        - Write-time validation is for structural integrity
        - Policy violations are detected at observer-time (Knight)
        - Failed validation leaves ledger unchanged

    Example:
        >>> service = LedgerValidationService(
        ...     event_type_validator=EventTypeValidator(),
        ...     actor_validator=ActorValidator(registry),
        ...     hash_chain_validator=HashChainValidator(ledger),
        ...     state_transition_validator=StateTransitionValidator(projection),
        ... )
        >>> await service.validate(event)  # Raises on failure
    """

    def __init__(
        self,
        event_type_validator: "EventTypeValidator",
        actor_validator: "ActorValidator",
        hash_chain_validator: "HashChainValidator",
        state_transition_validator: "StateTransitionValidator",
    ) -> None:
        """Initialize the validation service.

        Args:
            event_type_validator: Validates event types are registered.
            actor_validator: Validates actors are registered.
            hash_chain_validator: Validates hash chain integrity.
            state_transition_validator: Validates state machine transitions.
        """
        # Store validators in performance order (fastest first)
        self._validators: list[tuple[str, EventValidator]] = [
            ("event_type", event_type_validator),
            ("actor", actor_validator),
            ("state_transition", state_transition_validator),
            ("hash_chain", hash_chain_validator),
        ]

    async def validate(self, event: GovernanceEvent) -> None:
        """Validate an event for write-time constraints.

        Runs all validators in sequence, failing fast on first error.

        Args:
            event: The GovernanceEvent to validate.

        Raises:
            WriteTimeValidationError: If any validation fails.
                The specific subclass indicates the failure type:
                - UnknownEventTypeError: Event type not registered
                - UnknownActorError: Actor not registered
                - IllegalStateTransitionError: State machine violation
                - HashChainBreakError: Hash chain integrity violation
        """
        for _name, validator in self._validators:
            await validator.validate(event)

    async def validate_with_result(
        self,
        event: GovernanceEvent,
    ) -> ValidationResult:
        """Validate an event and return a result instead of raising.

        Useful for scenarios where you want to check validity without
        exception handling.

        Args:
            event: The GovernanceEvent to validate.

        Returns:
            ValidationResult with is_valid=True if passed, or
            is_valid=False with the error and validator name if failed.
        """
        for name, validator in self._validators:
            try:
                await validator.validate(event)
            except WriteTimeValidationError as e:
                return ValidationResult(
                    is_valid=False,
                    error=e,
                    validator_name=name,
                )

        return ValidationResult(is_valid=True)

    async def is_valid(self, event: GovernanceEvent) -> bool:
        """Check if an event is valid without raising.

        Args:
            event: The GovernanceEvent to check.

        Returns:
            True if the event passes all validations, False otherwise.
        """
        result = await self.validate_with_result(event)
        return result.is_valid


class NoOpValidationService:
    """No-op validation service for testing or bypass scenarios.

    WARNING: This bypasses ALL write-time validation. Only use for:
    - Unit tests where validation is not the focus
    - Admin replay scenarios with explicit bypass flag
    - Development/debugging (never in production)
    """

    async def validate(self, event: GovernanceEvent) -> None:
        """No-op validation - always passes."""
        pass

    async def validate_with_result(
        self,
        event: GovernanceEvent,
    ) -> ValidationResult:
        """No-op validation - always returns valid."""
        return ValidationResult(is_valid=True)

    async def is_valid(self, event: GovernanceEvent) -> bool:
        """No-op validation - always returns True."""
        return True
