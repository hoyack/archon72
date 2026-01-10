"""Keeper signature errors (FR68-FR70).

Provides specific exception classes for Keeper signature failures.

Constitutional Constraints:
- FR68: Override commands require cryptographic signature from registered Keeper key
- FR69: Keeper keys must be generated through witnessed ceremony
- FR70: Every override must record full authorization chain

Constitutional Truths Honored:
- CT-11: Silent failure destroys legitimacy -> Signature failures MUST raise explicit errors
- CT-12: Witnessing creates accountability -> Invalid signatures must be logged and rejected
"""

from __future__ import annotations

from src.domain.exceptions import ConclaveError


class KeeperSignatureError(ConclaveError):
    """Base class for Keeper signature errors (FR68-FR70).

    All Keeper signature-related exceptions inherit from this class.
    This enables consistent error handling for signature operations.
    """

    pass


class InvalidKeeperSignatureError(KeeperSignatureError):
    """FR68: Invalid Keeper signature - signature verification failed.

    Raised when:
    - Signature does not match the signable content
    - Signature format is invalid
    - Signature key doesn't match the claimed key_id

    The error message MUST include "FR68: Invalid Keeper signature"
    to comply with acceptance criteria AC2.
    """

    pass


class KeeperKeyNotFoundError(KeeperSignatureError):
    """FR68: No active key found for Keeper.

    Raised when:
    - Keeper has no keys registered
    - Keeper has keys but none are currently active
    - Keeper ID doesn't exist in the registry

    This error indicates the Keeper cannot sign because they
    have no valid key, not that a signature is invalid.
    """

    pass


class KeeperKeyExpiredError(KeeperSignatureError):
    """FR68: Keeper key was valid but has since expired.

    Raised when:
    - Attempting to sign with a key that is no longer active
    - Verifying a signature against a key that was not active
      at the time of signing

    This is distinct from KeeperKeyNotFoundError because the
    key exists but is no longer valid for the operation.
    """

    pass


class KeeperKeyAlreadyExistsError(KeeperSignatureError):
    """FR68: Attempting to register a duplicate key_id.

    Raised when trying to register a key with a key_id that
    already exists in the registry. Key IDs must be unique.
    """

    pass
