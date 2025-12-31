"""HSM-related domain exceptions.

These exceptions are raised by HSM implementations when cryptographic
operations fail or when security constraints are violated.

RT-1 Pattern: HSMModeViolationError is raised when:
- Dev mode watermark appears in production
- Prod mode watermark appears in development
- HSM mode doesn't match environment expectations
"""

from src.domain.exceptions import ConclaveError


class HSMError(ConclaveError):
    """Base exception for HSM-related errors.

    All HSM-specific exceptions inherit from this class.
    """

    pass


class HSMNotConfiguredError(HSMError):
    """Raised when production HSM is required but not configured.

    This is a critical security safeguard that prevents the system
    from operating in production mode without proper key custody.

    AC3 Requirement: Production mode MUST fail without real HSM.
    """

    def __init__(self, message: str = "Production HSM not configured") -> None:
        """Initialize with default message for production HSM failure."""
        super().__init__(message)


class HSMModeViolationError(HSMError):
    """Raised when HSM mode doesn't match expected environment.

    RT-1 Pattern Enforcement:
    - Detects dev signatures in production environment
    - Detects prod signatures in development environment
    - Detects HSM mode swap attacks

    This is a CRITICAL security violation that should trigger a system halt.
    """

    def __init__(
        self, message: str = "HSM mode violation detected", expected: str = "", actual: str = ""
    ) -> None:
        """Initialize with mode mismatch details.

        Args:
            message: Error description.
            expected: Expected HSM mode.
            actual: Actual HSM mode detected.
        """
        if expected and actual:
            message = f"{message}: expected {expected}, got {actual}"
        super().__init__(message)
        self.expected = expected
        self.actual = actual


class HSMKeyNotFoundError(HSMError):
    """Raised when the requested signing key is not found.

    This can occur when:
    - No keys have been generated yet
    - The specified key_id doesn't exist
    - Keys have been rotated and old key is no longer available
    """

    def __init__(self, key_id: str = "") -> None:
        """Initialize with key identifier.

        Args:
            key_id: The key ID that was not found.
        """
        message = f"HSM key not found: {key_id}" if key_id else "No HSM key available"
        super().__init__(message)
        self.key_id = key_id
