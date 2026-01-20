"""Identity store stub for testing (Story 5.3, NFR-5.2).

This module provides an in-memory implementation of IdentityStoreProtocol
for testing identity verification without external dependencies.

Constitutional Constraints:
- NFR-5.2: Identity verification for co-sign: Required [LEGIT-1]
- LEGIT-1: Prevents manufactured consent via bot co-signers

Developer Golden Rules:
1. VERIFY BEFORE WRITE - Check identity before any state changes
2. FAIL LOUD - Reject invalid identities, don't auto-create
3. TEST ISOLATION - Reset state between tests
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from src.application.ports.identity_verification import (
    IdentityStatus,
    IdentityStoreProtocol,
    IdentityVerificationResult,
)


class IdentityStoreStub(IdentityStoreProtocol):
    """In-memory identity store for testing (Story 5.3, NFR-5.2).

    Simulates an identity store with:
    - Set of valid (active) identities
    - Set of suspended identities with optional reasons
    - Availability toggle for testing service unavailability

    Usage:
        store = IdentityStoreStub()

        # Add valid identities
        store.add_valid_identity(UUID("..."))

        # Suspend an identity
        store.suspend_identity(UUID("..."), reason="Abuse detected")

        # Simulate service unavailability
        store.set_available(False)

        # Verify an identity
        result = store.verify(signer_id)
    """

    def __init__(self) -> None:
        """Initialize empty identity store."""
        self._valid_identities: set[UUID] = set()
        self._suspended_identities: dict[UUID, str | None] = {}
        self._available: bool = True

    def verify(self, identity_id: UUID) -> IdentityVerificationResult:
        """Verify an identity exists and is active (NFR-5.2).

        Args:
            identity_id: The UUID of the identity to verify.

        Returns:
            IdentityVerificationResult with appropriate status:
            - VALID if identity exists and is active
            - SUSPENDED if identity is suspended
            - NOT_FOUND if identity doesn't exist
            - SERVICE_UNAVAILABLE if store is unavailable
        """
        now = datetime.now(tz=timezone.utc)

        # Check service availability first
        if not self._available:
            return IdentityVerificationResult(
                identity_id=identity_id,
                status=IdentityStatus.SERVICE_UNAVAILABLE,
                verified_at=now,
                details="Identity store is temporarily unavailable",
            )

        # Check if suspended
        if identity_id in self._suspended_identities:
            reason = self._suspended_identities[identity_id]
            return IdentityVerificationResult(
                identity_id=identity_id,
                status=IdentityStatus.SUSPENDED,
                verified_at=now,
                suspension_reason=reason,
                details=f"Identity suspended: {reason}"
                if reason
                else "Identity suspended",
            )

        # Check if valid
        if identity_id in self._valid_identities:
            return IdentityVerificationResult(
                identity_id=identity_id,
                status=IdentityStatus.VALID,
                verified_at=now,
                details="Identity verified successfully",
            )

        # Not found
        return IdentityVerificationResult(
            identity_id=identity_id,
            status=IdentityStatus.NOT_FOUND,
            verified_at=now,
            details="Identity not found in identity store",
        )

    def is_available(self) -> bool:
        """Check if identity service is available.

        Returns:
            True if service can process verification requests.
        """
        return self._available

    # ========================================
    # Test helper methods
    # ========================================

    def add_valid_identity(self, identity_id: UUID) -> None:
        """Add a valid identity to the store.

        Args:
            identity_id: The UUID of the identity to add.

        Note:
            If identity was previously suspended, it remains suspended.
            Call unsuspend_identity() to reactivate.
        """
        self._valid_identities.add(identity_id)

    def remove_valid_identity(self, identity_id: UUID) -> None:
        """Remove a valid identity from the store.

        Args:
            identity_id: The UUID of the identity to remove.
        """
        self._valid_identities.discard(identity_id)

    def suspend_identity(self, identity_id: UUID, reason: str | None = None) -> None:
        """Suspend an identity.

        Args:
            identity_id: The UUID of the identity to suspend.
            reason: Optional reason for suspension.

        Note:
            Suspended identities are checked BEFORE valid identities,
            so suspending a valid identity will result in SUSPENDED status.
        """
        self._suspended_identities[identity_id] = reason

    def unsuspend_identity(self, identity_id: UUID) -> None:
        """Unsuspend an identity.

        Args:
            identity_id: The UUID of the identity to unsuspend.
        """
        self._suspended_identities.pop(identity_id, None)

    def set_available(self, available: bool) -> None:
        """Set service availability.

        Args:
            available: True if service should be available.
        """
        self._available = available

    def reset(self) -> None:
        """Reset all state for test isolation.

        Clears all valid identities, suspended identities,
        and resets availability to True.
        """
        self._valid_identities.clear()
        self._suspended_identities.clear()
        self._available = True

    def get_valid_count(self) -> int:
        """Get count of valid identities.

        Returns:
            Number of valid identities in the store.
        """
        return len(self._valid_identities)

    def get_suspended_count(self) -> int:
        """Get count of suspended identities.

        Returns:
            Number of suspended identities in the store.
        """
        return len(self._suspended_identities)

    def is_valid(self, identity_id: UUID) -> bool:
        """Check if identity is valid (not suspended, not missing).

        Args:
            identity_id: The UUID to check.

        Returns:
            True if identity is valid and not suspended.
        """
        return (
            identity_id in self._valid_identities
            and identity_id not in self._suspended_identities
        )


# Singleton instance for dependency injection
_identity_store_stub: IdentityStoreStub | None = None


def get_identity_store_stub() -> IdentityStoreStub:
    """Get the singleton identity store stub.

    Returns:
        The shared IdentityStoreStub instance.
    """
    global _identity_store_stub
    if _identity_store_stub is None:
        _identity_store_stub = IdentityStoreStub()
    return _identity_store_stub


def reset_identity_store_stub() -> None:
    """Reset the singleton identity store stub.

    Creates a new instance, clearing all state.
    Should be called in test fixtures.
    """
    global _identity_store_stub
    _identity_store_stub = IdentityStoreStub()


def set_identity_store_stub(stub: IdentityStoreStub) -> None:
    """Set the singleton identity store stub.

    Args:
        stub: The IdentityStoreStub instance to use.

    Note:
        Used for test injection with custom stub configuration.
    """
    global _identity_store_stub
    _identity_store_stub = stub
