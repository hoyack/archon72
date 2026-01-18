"""Unit tests for Separation Domain Errors (Story 8.2, FR52).

Tests the domain error classes for separation violations.
"""

from src.domain.errors.constitutional import ConstitutionalViolationError
from src.domain.errors.separation import (
    ConstitutionalToOperationalError,
    OperationalToEventStoreError,
    SeparationViolationError,
)


class TestSeparationViolationError:
    """Test base SeparationViolationError."""

    def test_inherits_from_constitutional_violation(self) -> None:
        """Test SeparationViolationError inherits from ConstitutionalViolationError."""
        assert issubclass(SeparationViolationError, ConstitutionalViolationError)

    def test_can_instantiate_with_message(self) -> None:
        """Test error can be instantiated with a message."""
        error = SeparationViolationError("Test separation violation")
        assert str(error) == "Test separation violation"


class TestOperationalToEventStoreError:
    """Test OperationalToEventStoreError."""

    def test_inherits_from_separation_violation(self) -> None:
        """Test OperationalToEventStoreError inherits from SeparationViolationError."""
        assert issubclass(OperationalToEventStoreError, SeparationViolationError)

    def test_instantiation_with_data_type(self) -> None:
        """Test error with data_type parameter."""
        error = OperationalToEventStoreError(data_type="uptime_recorded")
        assert "uptime_recorded" in str(error)

    def test_instantiation_stores_data_type(self) -> None:
        """Test data_type is accessible as attribute."""
        error = OperationalToEventStoreError(data_type="latency_measured")
        assert error.data_type == "latency_measured"

    def test_error_message_describes_violation(self) -> None:
        """Test error message describes the FR52 violation."""
        error = OperationalToEventStoreError(data_type="error_logged")
        message = str(error)
        assert "operational" in message.lower() or "FR52" in message

    def test_intended_target_stored(self) -> None:
        """Test intended_target is stored."""
        error = OperationalToEventStoreError(
            data_type="uptime", intended_target="event_store"
        )
        assert error.intended_target == "event_store"

    def test_correct_target_stored(self) -> None:
        """Test correct_target is stored."""
        error = OperationalToEventStoreError(
            data_type="uptime", correct_target="prometheus"
        )
        assert error.correct_target == "prometheus"


class TestConstitutionalToOperationalError:
    """Test ConstitutionalToOperationalError."""

    def test_inherits_from_separation_violation(self) -> None:
        """Test ConstitutionalToOperationalError inherits from SeparationViolationError."""
        assert issubclass(ConstitutionalToOperationalError, SeparationViolationError)

    def test_instantiation_with_data_type(self) -> None:
        """Test error with data_type parameter."""
        error = ConstitutionalToOperationalError(data_type="vote_cast")
        assert "vote_cast" in str(error)

    def test_instantiation_stores_data_type(self) -> None:
        """Test data_type is accessible as attribute."""
        error = ConstitutionalToOperationalError(data_type="halt_triggered")
        assert error.data_type == "halt_triggered"

    def test_error_message_describes_violation(self) -> None:
        """Test error message describes the violation."""
        error = ConstitutionalToOperationalError(data_type="deliberation_output")
        message = str(error)
        assert "constitutional" in message.lower() or "FR52" in message

    def test_intended_target_stored(self) -> None:
        """Test intended_target is stored."""
        error = ConstitutionalToOperationalError(
            data_type="vote", intended_target="prometheus"
        )
        assert error.intended_target == "prometheus"

    def test_correct_target_stored(self) -> None:
        """Test correct_target is stored."""
        error = ConstitutionalToOperationalError(
            data_type="vote", correct_target="event_store"
        )
        assert error.correct_target == "event_store"
