"""Domain errors for Archon 72.

Provides specific exception classes for different failure scenarios.
All exceptions inherit from ConclaveError.
"""

from src.domain.errors.hsm import HSMError, HSMModeViolationError, HSMNotConfiguredError

__all__: list[str] = ["HSMError", "HSMNotConfiguredError", "HSMModeViolationError"]
