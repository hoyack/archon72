"""Context Bundle domain errors (Story 2.9, ADR-2).

Domain exceptions for context bundle operations.

ADR-2 Requirements:
- Any agent invocation without a valid bundle signature is rejected
- Any bundle whose as_of_event_seq does not exist in canonical chain is rejected

Constitutional Truths Honored:
- CT-11: Silent failure destroys legitimacy -> Clear error messages
- CT-13: Integrity outranks availability -> Validation failures halt operations
"""

from __future__ import annotations

from src.domain.exceptions import ConclaveError


class ContextBundleError(ConclaveError):
    """Base exception for context bundle errors.

    All context bundle exceptions inherit from this class.
    """

    pass


class InvalidBundleSignatureError(ContextBundleError):
    """Raised when bundle signature verification fails.

    ADR-2 Requirement: Any agent invocation without a valid bundle
    signature is rejected.

    The error message includes the specific ADR reference for traceability.
    """

    ADR_REFERENCE: str = "ADR-2"
    DEFAULT_MESSAGE: str = "ADR-2: Invalid context bundle signature"

    def __init__(
        self,
        message: str | None = None,
        bundle_id: str | None = None,
        expected_key_id: str | None = None,
        provided_key_id: str | None = None,
    ) -> None:
        """Initialize InvalidBundleSignatureError.

        Args:
            message: Optional custom error message. Defaults to ADR-2 message.
            bundle_id: Optional bundle ID for context.
            expected_key_id: Optional expected signing key ID.
            provided_key_id: Optional provided signing key ID.
        """
        self.bundle_id = bundle_id
        self.expected_key_id = expected_key_id
        self.provided_key_id = provided_key_id

        if message is None:
            message = self.DEFAULT_MESSAGE
            if bundle_id:
                message = f"{message} (bundle: {bundle_id})"

        super().__init__(message)


class StaleBundleError(ContextBundleError):
    """Raised when bundle's as_of_event_seq is not in canonical chain.

    ADR-2 Requirement: Any bundle whose as_of_event_seq does not exist
    in canonical chain is rejected.

    This ensures temporal determinism (MA-3) - bundles reference a
    specific point in time that must be valid.
    """

    def __init__(
        self,
        message: str | None = None,
        bundle_id: str | None = None,
        as_of_event_seq: int | None = None,
        current_head_seq: int | None = None,
    ) -> None:
        """Initialize StaleBundleError.

        Args:
            message: Optional custom error message.
            bundle_id: Optional bundle ID for context.
            as_of_event_seq: The sequence number in the bundle.
            current_head_seq: The current head sequence in the chain.
        """
        self.bundle_id = bundle_id
        self.as_of_event_seq = as_of_event_seq
        self.current_head_seq = current_head_seq

        if message is None:
            if as_of_event_seq is not None and current_head_seq is not None:
                message = (
                    f"Bundle references stale sequence {as_of_event_seq} "
                    f"(current head: {current_head_seq})"
                )
            else:
                message = "Bundle references sequence not in canonical chain"
            if bundle_id:
                message = f"{message} (bundle: {bundle_id})"

        super().__init__(message)


class BundleSchemaValidationError(ContextBundleError):
    """Raised when bundle fails JSON Schema validation.

    ADR-2 Requirement: Bundles must be schema-valid.
    This ensures bundles are human-debuggable and correctly structured.
    """

    def __init__(
        self,
        message: str | None = None,
        bundle_id: str | None = None,
        validation_errors: list[str] | None = None,
    ) -> None:
        """Initialize BundleSchemaValidationError.

        Args:
            message: Optional custom error message.
            bundle_id: Optional bundle ID for context.
            validation_errors: Optional list of specific validation errors.
        """
        self.bundle_id = bundle_id
        self.validation_errors = validation_errors or []

        if message is None:
            if self.validation_errors:
                errors_str = "; ".join(self.validation_errors[:3])
                if len(self.validation_errors) > 3:
                    errors_str += f" (+{len(self.validation_errors) - 3} more)"
                message = f"Bundle schema validation failed: {errors_str}"
            else:
                message = "Bundle schema validation failed"
            if bundle_id:
                message = f"{message} (bundle: {bundle_id})"

        super().__init__(message)


class BundleNotFoundError(ContextBundleError):
    """Raised when a referenced bundle cannot be found.

    Used when attempting to verify or retrieve a bundle that
    does not exist in storage.
    """

    def __init__(
        self,
        message: str | None = None,
        bundle_id: str | None = None,
    ) -> None:
        """Initialize BundleNotFoundError.

        Args:
            message: Optional custom error message.
            bundle_id: Optional bundle ID that was not found.
        """
        self.bundle_id = bundle_id

        if message is None:
            if bundle_id:
                message = f"Bundle not found: {bundle_id}"
            else:
                message = "Bundle not found"

        super().__init__(message)


class BundleCreationError(ContextBundleError):
    """Raised when bundle creation fails.

    Generic error for bundle creation failures that don't fit
    other specific categories.
    """

    def __init__(
        self,
        message: str | None = None,
        meeting_id: str | None = None,
        cause: str | None = None,
    ) -> None:
        """Initialize BundleCreationError.

        Args:
            message: Optional custom error message.
            meeting_id: Optional meeting ID for context.
            cause: Optional cause of the error.
        """
        self.meeting_id = meeting_id
        self.cause = cause

        if message is None:
            message = "Bundle creation failed"
            if cause:
                message = f"{message}: {cause}"
            if meeting_id:
                message = f"{message} (meeting: {meeting_id})"

        super().__init__(message)
