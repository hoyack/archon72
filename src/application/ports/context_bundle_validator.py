"""Context Bundle Validator port definition (Story 2.9, ADR-2).

Defines the abstract interface for context bundle validation.
This port enables signature verification, schema validation,
and freshness checks for context bundles.

ADR-2 Requirements:
- Receivers verify signature BEFORE parsing/using bundle
- Invalid bundles are rejected with "ADR-2: Invalid context bundle signature"
- Any bundle whose as_of_event_seq does not exist in canonical chain is rejected

Constitutional Constraints:
- CT-11: Silent failure destroys legitimacy -> Clear validation errors
- CT-13: Integrity outranks availability -> Validation before use
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from src.domain.models.context_bundle import ContextBundlePayload


@dataclass(frozen=True, eq=True)
class BundleValidationResult:
    """Result of bundle validation operation.

    Attributes:
        valid: Whether the validation passed.
        bundle_id: ID of the validated bundle.
        error_code: Error code if validation failed (e.g., "INVALID_SIGNATURE").
        error_message: Human-readable error description.
    """

    valid: bool
    bundle_id: str | None
    error_code: str | None = None
    error_message: str | None = None

    def __post_init__(self) -> None:
        """Validate result state."""
        if not self.valid and self.error_message is None:
            raise ValueError("error_message required when valid=False")


@dataclass(frozen=True, eq=True)
class FreshnessCheckResult:
    """Result of bundle freshness check.

    Attributes:
        fresh: Whether the bundle's as_of_event_seq is valid.
        as_of_event_seq: The sequence number from the bundle.
        current_head_seq: The current head sequence in the chain.
        error_message: Error description if stale.
    """

    fresh: bool
    as_of_event_seq: int
    current_head_seq: int
    error_message: str | None = None

    def __post_init__(self) -> None:
        """Validate result state."""
        if not self.fresh and self.error_message is None:
            raise ValueError("error_message required when fresh=False")


class ContextBundleValidatorPort(ABC):
    """Abstract interface for context bundle validation.

    All context bundle validator implementations must implement this interface.
    This enables dependency inversion and allows the application layer
    to remain independent of specific validation implementations.

    ADR-2 Requirements:
    - Signature MUST be verified BEFORE parsing/using content
    - Invalid signature = "ADR-2: Invalid context bundle signature"
    - Bundle must pass JSON Schema validation
    - as_of_event_seq must exist in canonical chain

    Note:
        This port defines the abstract interface. Infrastructure adapters
        (e.g., ContextBundleValidatorStub) implement this protocol with
        specific validation logic.
    """

    @abstractmethod
    async def validate_signature(
        self,
        bundle: ContextBundlePayload,
    ) -> BundleValidationResult:
        """Validate bundle signature.

        ADR-2 Critical: This MUST be called BEFORE using bundle content.
        Invalid bundles are rejected with "ADR-2: Invalid context bundle signature".

        Args:
            bundle: The bundle to validate.

        Returns:
            BundleValidationResult indicating if signature is valid.
        """
        ...

    @abstractmethod
    async def validate_schema(
        self,
        bundle: ContextBundlePayload,
    ) -> BundleValidationResult:
        """Validate bundle against JSON Schema.

        Ensures bundle has all required fields and correct types.

        Args:
            bundle: The bundle to validate.

        Returns:
            BundleValidationResult indicating if schema is valid.
        """
        ...

    @abstractmethod
    async def validate_freshness(
        self,
        bundle: ContextBundlePayload,
        current_head_seq: int,
    ) -> FreshnessCheckResult:
        """Validate bundle is not stale.

        ADR-2 Requirement: Any bundle whose as_of_event_seq does not exist
        in canonical chain is rejected.

        Args:
            bundle: The bundle to validate.
            current_head_seq: The current head sequence in the event chain.

        Returns:
            FreshnessCheckResult indicating if bundle is fresh.
        """
        ...

    @abstractmethod
    async def validate_all(
        self,
        bundle: ContextBundlePayload,
        current_head_seq: int,
    ) -> BundleValidationResult:
        """Perform all validations on a bundle.

        Runs signature, schema, and freshness validation in correct order
        (signature first per ADR-2).

        Args:
            bundle: The bundle to validate.
            current_head_seq: The current head sequence in the event chain.

        Returns:
            BundleValidationResult with combined validation status.
        """
        ...
