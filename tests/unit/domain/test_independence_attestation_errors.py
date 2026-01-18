"""Unit tests for Independence Attestation error classes (FR98, FR133).

Tests the error classes for annual Keeper independence attestation:
- IndependenceAttestationError
- AttestationDeadlineMissedError
- DuplicateIndependenceAttestationError
- InvalidIndependenceSignatureError
- CapabilitySuspendedError

Constitutional Constraints Tested:
- FR133: Annual independence attestation requirement
- CT-11: Silent failure destroys legitimacy (clear error messages)
"""

from __future__ import annotations


class TestIndependenceAttestationError:
    """Tests for IndependenceAttestationError base class."""

    def test_is_exception(self) -> None:
        """Test base class is an Exception."""
        from src.domain.errors.independence_attestation import (
            IndependenceAttestationError,
        )

        error = IndependenceAttestationError("Test error")
        assert isinstance(error, Exception)

    def test_message_preserved(self) -> None:
        """Test error message is preserved."""
        from src.domain.errors.independence_attestation import (
            IndependenceAttestationError,
        )

        error = IndependenceAttestationError("Custom message")
        assert str(error) == "Custom message"


class TestAttestationDeadlineMissedError:
    """Tests for AttestationDeadlineMissedError."""

    def test_inherits_from_base(self) -> None:
        """Test inherits from IndependenceAttestationError."""
        from src.domain.errors.independence_attestation import (
            AttestationDeadlineMissedError,
            IndependenceAttestationError,
        )

        error = AttestationDeadlineMissedError("KEEPER:alice", "2026-02-14")
        assert isinstance(error, IndependenceAttestationError)

    def test_fr133_in_message(self) -> None:
        """Test FR133 reference in error message."""
        from src.domain.errors.independence_attestation import (
            AttestationDeadlineMissedError,
        )

        error = AttestationDeadlineMissedError("KEEPER:alice", "2026-02-14")
        assert "FR133" in str(error)

    def test_keeper_id_in_message(self) -> None:
        """Test keeper_id is included in message."""
        from src.domain.errors.independence_attestation import (
            AttestationDeadlineMissedError,
        )

        error = AttestationDeadlineMissedError("KEEPER:bob", "2026-02-14")
        assert "KEEPER:bob" in str(error)

    def test_deadline_in_message(self) -> None:
        """Test deadline is included in message."""
        from src.domain.errors.independence_attestation import (
            AttestationDeadlineMissedError,
        )

        error = AttestationDeadlineMissedError("KEEPER:alice", "2026-02-14T00:00:00Z")
        assert "2026-02-14" in str(error)

    def test_attributes_stored(self) -> None:
        """Test attributes are accessible."""
        from src.domain.errors.independence_attestation import (
            AttestationDeadlineMissedError,
        )

        error = AttestationDeadlineMissedError("KEEPER:alice", "2026-02-14")
        assert error.keeper_id == "KEEPER:alice"
        assert error.deadline == "2026-02-14"


class TestDuplicateIndependenceAttestationError:
    """Tests for DuplicateIndependenceAttestationError."""

    def test_inherits_from_base(self) -> None:
        """Test inherits from IndependenceAttestationError."""
        from src.domain.errors.independence_attestation import (
            DuplicateIndependenceAttestationError,
            IndependenceAttestationError,
        )

        error = DuplicateIndependenceAttestationError("KEEPER:alice", 2026)
        assert isinstance(error, IndependenceAttestationError)

    def test_fr133_in_message(self) -> None:
        """Test FR133 reference in error message."""
        from src.domain.errors.independence_attestation import (
            DuplicateIndependenceAttestationError,
        )

        error = DuplicateIndependenceAttestationError("KEEPER:alice", 2026)
        assert "FR133" in str(error)

    def test_year_in_message(self) -> None:
        """Test year is included in message."""
        from src.domain.errors.independence_attestation import (
            DuplicateIndependenceAttestationError,
        )

        error = DuplicateIndependenceAttestationError("KEEPER:alice", 2026)
        assert "2026" in str(error)

    def test_attributes_stored(self) -> None:
        """Test attributes are accessible."""
        from src.domain.errors.independence_attestation import (
            DuplicateIndependenceAttestationError,
        )

        error = DuplicateIndependenceAttestationError("KEEPER:bob", 2025)
        assert error.keeper_id == "KEEPER:bob"
        assert error.year == 2025


class TestInvalidIndependenceSignatureError:
    """Tests for InvalidIndependenceSignatureError."""

    def test_inherits_from_base(self) -> None:
        """Test inherits from IndependenceAttestationError."""
        from src.domain.errors.independence_attestation import (
            IndependenceAttestationError,
            InvalidIndependenceSignatureError,
        )

        error = InvalidIndependenceSignatureError("KEEPER:alice")
        assert isinstance(error, IndependenceAttestationError)

    def test_fr133_in_message(self) -> None:
        """Test FR133 reference in error message."""
        from src.domain.errors.independence_attestation import (
            InvalidIndependenceSignatureError,
        )

        error = InvalidIndependenceSignatureError("KEEPER:alice")
        assert "FR133" in str(error)

    def test_default_reason(self) -> None:
        """Test default reason is used."""
        from src.domain.errors.independence_attestation import (
            InvalidIndependenceSignatureError,
        )

        error = InvalidIndependenceSignatureError("KEEPER:alice")
        assert "verification failed" in str(error)

    def test_custom_reason(self) -> None:
        """Test custom reason is used."""
        from src.domain.errors.independence_attestation import (
            InvalidIndependenceSignatureError,
        )

        error = InvalidIndependenceSignatureError("KEEPER:alice", "key expired")
        assert "key expired" in str(error)


class TestCapabilitySuspendedError:
    """Tests for CapabilitySuspendedError."""

    def test_inherits_from_base(self) -> None:
        """Test inherits from IndependenceAttestationError."""
        from src.domain.errors.independence_attestation import (
            CapabilitySuspendedError,
            IndependenceAttestationError,
        )

        error = CapabilitySuspendedError("KEEPER:alice")
        assert isinstance(error, IndependenceAttestationError)

    def test_fr133_in_message(self) -> None:
        """Test FR133 reference in error message."""
        from src.domain.errors.independence_attestation import (
            CapabilitySuspendedError,
        )

        error = CapabilitySuspendedError("KEEPER:alice")
        assert "FR133" in str(error)

    def test_default_capability(self) -> None:
        """Test default capability is override."""
        from src.domain.errors.independence_attestation import (
            CapabilitySuspendedError,
        )

        error = CapabilitySuspendedError("KEEPER:alice")
        assert "override" in str(error)

    def test_custom_capability(self) -> None:
        """Test custom capability is used."""
        from src.domain.errors.independence_attestation import (
            CapabilitySuspendedError,
        )

        error = CapabilitySuspendedError("KEEPER:alice", "execute")
        assert "execute" in str(error)

    def test_attributes_stored(self) -> None:
        """Test attributes are accessible."""
        from src.domain.errors.independence_attestation import (
            CapabilitySuspendedError,
        )

        error = CapabilitySuspendedError("KEEPER:bob", "override")
        assert error.keeper_id == "KEEPER:bob"
        assert error.capability == "override"
