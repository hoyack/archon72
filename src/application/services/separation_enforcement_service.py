"""Separation Enforcement Service - FR52 Operational-Constitutional Separation.

This service enforces the separation between operational metrics and
constitutional events. It validates write targets and prevents violations.

Constitutional Constraint (FR52):
- Operational metrics NEVER enter event store
- Constitutional events NEVER go to operational storage
- This is a HARD separation - violations raise errors immediately

Usage:
    validator = SeparationValidatorStub()
    service = SeparationEnforcementService(validator)

    # Validate before writing
    result = service.validate_write_target("uptime_recorded", WriteTarget.PROMETHEUS)
    if not result.valid:
        raise OperationalToEventStoreError(...)

    # Or use assert for fail-fast
    service.assert_not_event_store("uptime_recorded")  # Raises if operational
"""

from dataclasses import dataclass
from enum import Enum

from src.application.ports.separation_validator import (
    DataClassification,
    SeparationValidatorPort,
)
from src.domain.errors.separation import OperationalToEventStoreError
from src.infrastructure.stubs.separation_validator_stub import SeparationValidatorStub


class WriteTarget(Enum):
    """Target storage for data writes.

    Determines where data should be stored based on its classification.
    """

    EVENT_STORE = "event_store"  # Constitutional events only
    PROMETHEUS = "prometheus"  # Operational metrics
    OPERATIONAL_DB = "operational_db"  # Operational logs/state


@dataclass(frozen=True)
class ValidationResult:
    """Result of a write target validation.

    Attributes:
        valid: True if the write target is correct for the data type.
        reason: Human-readable explanation of the validation result.
    """

    valid: bool
    reason: str


class SeparationEnforcementService:
    """Service for enforcing operational-constitutional separation (FR52).

    This service validates that data is routed to the correct storage:
    - Constitutional events → Event Store
    - Operational metrics → Prometheus/Operational DB

    Violations are treated as constitutional errors and raise immediately.
    """

    def __init__(self, validator: SeparationValidatorPort) -> None:
        """Initialize the service with a separation validator.

        Args:
            validator: Port implementation for classifying data types.
        """
        self._validator = validator

    def validate_write_target(
        self, data_type: str, target: WriteTarget
    ) -> ValidationResult:
        """Validate that a data type is being written to the correct target.

        Args:
            data_type: The type identifier for the data being written.
            target: The intended storage target.

        Returns:
            ValidationResult indicating if the write is allowed.
        """
        classification = self._validator.classify_data(data_type)

        # Constitutional data MUST go to event store
        if classification == DataClassification.CONSTITUTIONAL:
            if target == WriteTarget.EVENT_STORE:
                return ValidationResult(
                    valid=True,
                    reason=f"Constitutional event '{data_type}' correctly "
                    f"routed to event store",
                )
            return ValidationResult(
                valid=False,
                reason=f"FR52 Violation: Constitutional event '{data_type}' "
                f"cannot be written to {target.value}. Must use event store.",
            )

        # Operational data MUST go to Prometheus or operational DB
        if classification == DataClassification.OPERATIONAL:
            if target in (WriteTarget.PROMETHEUS, WriteTarget.OPERATIONAL_DB):
                return ValidationResult(
                    valid=True,
                    reason=f"Operational data '{data_type}' correctly "
                    f"routed to {target.value}",
                )
            return ValidationResult(
                valid=False,
                reason=f"FR52 Violation: Operational data '{data_type}' "
                f"cannot be written to event store. Must use Prometheus.",
            )

        # Unknown types are rejected from event store (fail-safe)
        if target == WriteTarget.EVENT_STORE:
            return ValidationResult(
                valid=False,
                reason=f"Unknown data type '{data_type}' cannot be written to "
                f"event store. Only known constitutional types allowed.",
            )

        # Unknown types to operational storage is allowed (lenient)
        return ValidationResult(
            valid=True,
            reason=f"Unknown data type '{data_type}' allowed to {target.value}",
        )

    def assert_not_event_store(self, data_type: str) -> None:
        """Assert that a data type is constitutional (allowed in event store).

        This is a fail-fast check to use before writing to event store.
        Raises an error if the data type is operational or unknown.

        Args:
            data_type: The type identifier to check.

        Raises:
            OperationalToEventStoreError: If data type is not constitutional.
        """
        classification = self._validator.classify_data(data_type)

        if classification != DataClassification.CONSTITUTIONAL:
            raise OperationalToEventStoreError(
                data_type=data_type,
                intended_target="event_store",
                correct_target="prometheus",
            )

    def get_constitutional_event_types(self) -> set[str]:
        """Get all constitutional event types allowed in event store.

        Returns:
            Set of event type strings permitted in the event store.
        """
        return self._validator.get_allowed_event_types()

    def get_operational_metric_types(self) -> set[str]:
        """Get all operational metric types (forbidden in event store).

        Returns:
            Set of operational metric type strings.
        """
        # Access the stub's OPERATIONAL_TYPES constant
        if isinstance(self._validator, SeparationValidatorStub):
            return set(self._validator.OPERATIONAL_TYPES)
        # For other implementations, return known operational types
        return {
            "uptime_recorded",
            "latency_measured",
            "error_logged",
            "error_rate",
            "request_counted",
            "request_duration",
            "service_start",
            "service_stop",
            "health_check",
        }
