"""Unit tests for IdentityStoreStub (Story 5.3, NFR-5.2).

Tests the in-memory identity verification stub implementation.

Constitutional Constraints:
- NFR-5.2: Identity verification for co-sign: Required [LEGIT-1]
- LEGIT-1: Manufactured consent via bot co-signers -> verification required
"""

from __future__ import annotations

from uuid import uuid4

from src.application.ports.identity_verification import IdentityStatus
from src.infrastructure.stubs.identity_store_stub import IdentityStoreStub


class TestIdentityStoreStubInitialization:
    """Tests for IdentityStoreStub initialization."""

    def test_stub_starts_empty(self) -> None:
        """Stub should start with no identities."""
        stub = IdentityStoreStub()

        assert stub._valid_identities == set()
        assert stub._suspended_identities == {}

    def test_stub_is_available_by_default(self) -> None:
        """Stub should be available by default."""
        stub = IdentityStoreStub()

        assert stub.is_available() is True


class TestIdentityStoreStubValidIdentities:
    """Tests for valid identity management."""

    def test_add_valid_identity(self) -> None:
        """Can add a valid identity."""
        stub = IdentityStoreStub()
        identity_id = uuid4()

        stub.add_valid_identity(identity_id)

        assert identity_id in stub._valid_identities

    def test_verify_valid_identity_returns_valid_status(self) -> None:
        """Verifying a valid identity returns VALID status."""
        stub = IdentityStoreStub()
        identity_id = uuid4()
        stub.add_valid_identity(identity_id)

        result = stub.verify(identity_id)

        assert result.status == IdentityStatus.VALID
        assert result.identity_id == identity_id
        assert result.is_valid is True
        assert result.suspension_reason is None

    def test_verify_unknown_identity_returns_not_found(self) -> None:
        """Verifying an unknown identity returns NOT_FOUND status."""
        stub = IdentityStoreStub()
        unknown_id = uuid4()

        result = stub.verify(unknown_id)

        assert result.status == IdentityStatus.NOT_FOUND
        assert result.identity_id == unknown_id
        assert result.is_valid is False

    def test_remove_valid_identity(self) -> None:
        """Can remove a valid identity."""
        stub = IdentityStoreStub()
        identity_id = uuid4()
        stub.add_valid_identity(identity_id)

        stub.remove_valid_identity(identity_id)

        assert identity_id not in stub._valid_identities

    def test_remove_nonexistent_identity_no_error(self) -> None:
        """Removing a nonexistent identity doesn't raise error."""
        stub = IdentityStoreStub()
        unknown_id = uuid4()

        # Should not raise
        stub.remove_valid_identity(unknown_id)


class TestIdentityStoreStubSuspendedIdentities:
    """Tests for suspended identity management."""

    def test_suspend_identity(self) -> None:
        """Can suspend an identity."""
        stub = IdentityStoreStub()
        identity_id = uuid4()
        stub.add_valid_identity(identity_id)

        stub.suspend_identity(identity_id, reason="Abuse pattern detected")

        assert identity_id in stub._suspended_identities
        assert stub._suspended_identities[identity_id] == "Abuse pattern detected"

    def test_suspended_takes_precedence_over_valid(self) -> None:
        """Suspended status takes precedence over valid status.

        The stub checks suspended before valid, so an identity can be
        in both sets but will return SUSPENDED status.
        """
        stub = IdentityStoreStub()
        identity_id = uuid4()
        stub.add_valid_identity(identity_id)

        stub.suspend_identity(identity_id)

        # Identity may still be in valid_identities, but verify() returns SUSPENDED
        result = stub.verify(identity_id)
        assert result.status == IdentityStatus.SUSPENDED

    def test_verify_suspended_identity_returns_suspended_status(self) -> None:
        """Verifying a suspended identity returns SUSPENDED status."""
        stub = IdentityStoreStub()
        identity_id = uuid4()
        stub.add_valid_identity(identity_id)
        stub.suspend_identity(identity_id, reason="Bot activity")

        result = stub.verify(identity_id)

        assert result.status == IdentityStatus.SUSPENDED
        assert result.identity_id == identity_id
        assert result.is_valid is False
        assert result.suspension_reason == "Bot activity"

    def test_suspend_identity_without_reason(self) -> None:
        """Can suspend identity without providing reason."""
        stub = IdentityStoreStub()
        identity_id = uuid4()
        stub.add_valid_identity(identity_id)

        stub.suspend_identity(identity_id)

        result = stub.verify(identity_id)
        assert result.status == IdentityStatus.SUSPENDED
        assert result.suspension_reason is None

    def test_unsuspend_identity(self) -> None:
        """Can unsuspend a suspended identity."""
        stub = IdentityStoreStub()
        identity_id = uuid4()
        stub.add_valid_identity(identity_id)
        stub.suspend_identity(identity_id)

        stub.unsuspend_identity(identity_id)

        assert identity_id not in stub._suspended_identities
        assert identity_id in stub._valid_identities

    def test_unsuspend_nonexistent_identity_no_error(self) -> None:
        """Unsuspending a nonexistent identity doesn't raise error."""
        stub = IdentityStoreStub()
        unknown_id = uuid4()

        # Should not raise
        stub.unsuspend_identity(unknown_id)


class TestIdentityStoreStubAvailability:
    """Tests for service availability simulation."""

    def test_set_unavailable(self) -> None:
        """Can set service as unavailable."""
        stub = IdentityStoreStub()

        stub.set_available(False)

        assert stub.is_available() is False

    def test_verify_when_unavailable_returns_service_unavailable(self) -> None:
        """Verifying when unavailable returns SERVICE_UNAVAILABLE status."""
        stub = IdentityStoreStub()
        identity_id = uuid4()
        stub.add_valid_identity(identity_id)
        stub.set_available(False)

        result = stub.verify(identity_id)

        assert result.status == IdentityStatus.SERVICE_UNAVAILABLE
        assert result.identity_id == identity_id
        assert result.is_valid is False

    def test_restore_availability(self) -> None:
        """Can restore service availability."""
        stub = IdentityStoreStub()
        stub.set_available(False)

        stub.set_available(True)

        assert stub.is_available() is True


class TestIdentityStoreStubReset:
    """Tests for stub reset functionality."""

    def test_reset_clears_all_data(self) -> None:
        """Reset clears all stored data."""
        stub = IdentityStoreStub()
        identity1 = uuid4()
        identity2 = uuid4()
        stub.add_valid_identity(identity1)
        stub.suspend_identity(identity2)
        stub.set_available(False)

        stub.reset()

        assert stub._valid_identities == set()
        assert stub._suspended_identities == {}
        assert stub.is_available() is True


class TestIdentityVerificationResultProperties:
    """Tests for IdentityVerificationResult properties."""

    def test_is_valid_true_for_valid_status(self) -> None:
        """is_valid returns True for VALID status."""
        stub = IdentityStoreStub()
        identity_id = uuid4()
        stub.add_valid_identity(identity_id)

        result = stub.verify(identity_id)

        assert result.is_valid is True

    def test_is_valid_false_for_not_found(self) -> None:
        """is_valid returns False for NOT_FOUND status."""
        stub = IdentityStoreStub()
        identity_id = uuid4()

        result = stub.verify(identity_id)

        assert result.is_valid is False

    def test_is_valid_false_for_suspended(self) -> None:
        """is_valid returns False for SUSPENDED status."""
        stub = IdentityStoreStub()
        identity_id = uuid4()
        stub.add_valid_identity(identity_id)
        stub.suspend_identity(identity_id)

        result = stub.verify(identity_id)

        assert result.is_valid is False

    def test_is_valid_false_for_service_unavailable(self) -> None:
        """is_valid returns False for SERVICE_UNAVAILABLE status."""
        stub = IdentityStoreStub()
        identity_id = uuid4()
        stub.set_available(False)

        result = stub.verify(identity_id)

        assert result.is_valid is False
