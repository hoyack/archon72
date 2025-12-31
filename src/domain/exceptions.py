"""Base exception classes for the Archon 72 domain layer."""


class ConclaveError(Exception):
    """Base exception for all domain errors.

    All domain-specific exceptions MUST inherit from this class.
    This enables consistent error handling across the application.

    Example subclasses (to be added in future stories):
    - QuorumNotMetError
    - SignatureVerificationError
    - SystemHaltedError
    - HashChainBrokenError
    - WitnessValidationError
    """

    def __init__(self, message: str = "") -> None:
        """Initialize the exception with an optional message.

        Args:
            message: Human-readable error description.
        """
        super().__init__(message)
