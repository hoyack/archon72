"""Unit tests for co-sign domain errors (Story 5.2).

Tests for:
- AlreadySignedError (FR-6.2, NFR-3.5)
- CoSignPetitionNotFoundError (FR-6.1)
- CoSignPetitionFatedError (FR-6.3)
"""

from uuid import uuid4

import pytest

from src.domain.errors import (
    AlreadySignedError,
    CoSignError,
    CoSignPetitionFatedError,
    CoSignPetitionNotFoundError,
)
from src.domain.errors.constitutional import ConstitutionalViolationError


class TestCoSignError:
    """Tests for base CoSignError class."""

    def test_cosign_error_inherits_from_constitutional_violation(self) -> None:
        """CoSignError should inherit from ConstitutionalViolationError."""
        assert issubclass(CoSignError, ConstitutionalViolationError)

    def test_cosign_error_can_be_instantiated(self) -> None:
        """CoSignError should be instantiable with a message."""
        error = CoSignError("test message")
        assert str(error) == "test message"


class TestAlreadySignedError:
    """Tests for AlreadySignedError (FR-6.2, NFR-3.5)."""

    def test_inherits_from_cosign_error(self) -> None:
        """AlreadySignedError should inherit from CoSignError."""
        assert issubclass(AlreadySignedError, CoSignError)

    def test_stores_petition_id(self) -> None:
        """Error should store petition_id attribute."""
        petition_id = uuid4()
        signer_id = uuid4()
        error = AlreadySignedError(petition_id, signer_id)
        assert error.petition_id == petition_id

    def test_stores_signer_id(self) -> None:
        """Error should store signer_id attribute."""
        petition_id = uuid4()
        signer_id = uuid4()
        error = AlreadySignedError(petition_id, signer_id)
        assert error.signer_id == signer_id

    def test_message_includes_fr_reference(self) -> None:
        """Error message should include FR-6.2/NFR-3.5 reference."""
        petition_id = uuid4()
        signer_id = uuid4()
        error = AlreadySignedError(petition_id, signer_id)
        assert "FR-6.2/NFR-3.5" in str(error)

    def test_message_includes_petition_id(self) -> None:
        """Error message should include petition_id."""
        petition_id = uuid4()
        signer_id = uuid4()
        error = AlreadySignedError(petition_id, signer_id)
        assert str(petition_id) in str(error)

    def test_message_includes_signer_id(self) -> None:
        """Error message should include signer_id."""
        petition_id = uuid4()
        signer_id = uuid4()
        error = AlreadySignedError(petition_id, signer_id)
        assert str(signer_id) in str(error)

    def test_message_indicates_already_signed(self) -> None:
        """Error message should indicate already signed."""
        petition_id = uuid4()
        signer_id = uuid4()
        error = AlreadySignedError(petition_id, signer_id)
        assert "already co-signed" in str(error)


class TestCoSignPetitionNotFoundError:
    """Tests for CoSignPetitionNotFoundError (FR-6.1)."""

    def test_inherits_from_cosign_error(self) -> None:
        """CoSignPetitionNotFoundError should inherit from CoSignError."""
        assert issubclass(CoSignPetitionNotFoundError, CoSignError)

    def test_stores_petition_id(self) -> None:
        """Error should store petition_id attribute."""
        petition_id = uuid4()
        error = CoSignPetitionNotFoundError(petition_id)
        assert error.petition_id == petition_id

    def test_message_includes_fr_reference(self) -> None:
        """Error message should include FR-6.1 reference."""
        petition_id = uuid4()
        error = CoSignPetitionNotFoundError(petition_id)
        assert "FR-6.1" in str(error)

    def test_message_includes_petition_id(self) -> None:
        """Error message should include petition_id."""
        petition_id = uuid4()
        error = CoSignPetitionNotFoundError(petition_id)
        assert str(petition_id) in str(error)

    def test_message_indicates_not_found(self) -> None:
        """Error message should indicate not found."""
        petition_id = uuid4()
        error = CoSignPetitionNotFoundError(petition_id)
        assert "not found" in str(error)


class TestCoSignPetitionFatedError:
    """Tests for CoSignPetitionFatedError (FR-6.3)."""

    def test_inherits_from_cosign_error(self) -> None:
        """CoSignPetitionFatedError should inherit from CoSignError."""
        assert issubclass(CoSignPetitionFatedError, CoSignError)

    def test_stores_petition_id(self) -> None:
        """Error should store petition_id attribute."""
        petition_id = uuid4()
        error = CoSignPetitionFatedError(petition_id, "ACKNOWLEDGED")
        assert error.petition_id == petition_id

    def test_stores_terminal_state(self) -> None:
        """Error should store terminal_state attribute."""
        petition_id = uuid4()
        error = CoSignPetitionFatedError(petition_id, "ACKNOWLEDGED")
        assert error.terminal_state == "ACKNOWLEDGED"

    def test_message_includes_fr_reference(self) -> None:
        """Error message should include FR-6.3 reference."""
        petition_id = uuid4()
        error = CoSignPetitionFatedError(petition_id, "ACKNOWLEDGED")
        assert "FR-6.3" in str(error)

    def test_message_includes_petition_id(self) -> None:
        """Error message should include petition_id."""
        petition_id = uuid4()
        error = CoSignPetitionFatedError(petition_id, "ACKNOWLEDGED")
        assert str(petition_id) in str(error)

    def test_message_includes_terminal_state(self) -> None:
        """Error message should include terminal state."""
        petition_id = uuid4()
        error = CoSignPetitionFatedError(petition_id, "REFERRED")
        assert "REFERRED" in str(error)

    def test_message_indicates_fate_assigned(self) -> None:
        """Error message should indicate fate assignment."""
        petition_id = uuid4()
        error = CoSignPetitionFatedError(petition_id, "ESCALATED")
        assert "already has fate" in str(error)

    def test_message_indicates_cosigning_not_permitted(self) -> None:
        """Error message should indicate co-signing not permitted."""
        petition_id = uuid4()
        error = CoSignPetitionFatedError(petition_id, "ACKNOWLEDGED")
        assert "Co-signing is not permitted" in str(error)

    @pytest.mark.parametrize(
        "terminal_state",
        ["ACKNOWLEDGED", "REFERRED", "ESCALATED"],
    )
    def test_accepts_all_three_fates(self, terminal_state: str) -> None:
        """Error should accept all Three Fates terminal states."""
        petition_id = uuid4()
        error = CoSignPetitionFatedError(petition_id, terminal_state)
        assert error.terminal_state == terminal_state
        assert terminal_state in str(error)
