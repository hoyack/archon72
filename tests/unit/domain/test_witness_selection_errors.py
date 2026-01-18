"""Unit tests for witness selection domain errors (FR59, FR60, FR61, FR117).

Tests all witness selection error classes.
"""

from datetime import datetime, timezone

from src.domain.errors.constitutional import ConstitutionalViolationError
from src.domain.errors.witness_selection import (
    AllWitnessesPairExhaustedError,
    EntropyUnavailableError,
    InsufficientWitnessPoolError,
    WitnessPairRotationViolationError,
    WitnessSelectionError,
    WitnessSelectionVerificationError,
)


class TestWitnessSelectionErrorHierarchy:
    """Tests for error inheritance hierarchy."""

    def test_witness_selection_error_is_constitutional_violation(self) -> None:
        """WitnessSelectionError inherits from ConstitutionalViolationError."""
        assert issubclass(WitnessSelectionError, ConstitutionalViolationError)

    def test_entropy_unavailable_error_is_selection_error(self) -> None:
        """EntropyUnavailableError inherits from WitnessSelectionError."""
        assert issubclass(EntropyUnavailableError, WitnessSelectionError)

    def test_pair_rotation_violation_error_is_selection_error(self) -> None:
        """WitnessPairRotationViolationError inherits from WitnessSelectionError."""
        assert issubclass(WitnessPairRotationViolationError, WitnessSelectionError)

    def test_verification_error_is_selection_error(self) -> None:
        """WitnessSelectionVerificationError inherits from WitnessSelectionError."""
        assert issubclass(WitnessSelectionVerificationError, WitnessSelectionError)

    def test_insufficient_pool_error_is_selection_error(self) -> None:
        """InsufficientWitnessPoolError inherits from WitnessSelectionError."""
        assert issubclass(InsufficientWitnessPoolError, WitnessSelectionError)

    def test_exhausted_error_is_selection_error(self) -> None:
        """AllWitnessesPairExhaustedError inherits from WitnessSelectionError."""
        assert issubclass(AllWitnessesPairExhaustedError, WitnessSelectionError)


class TestEntropyUnavailableError:
    """Tests for EntropyUnavailableError (FR61, NFR57)."""

    def test_message_includes_fr61(self) -> None:
        """Error message mentions FR61."""
        error = EntropyUnavailableError()

        assert "FR61" in str(error)

    def test_message_mentions_external_entropy(self) -> None:
        """Error message mentions external entropy."""
        error = EntropyUnavailableError()

        assert "External entropy unavailable" in str(error)

    def test_message_mentions_halt(self) -> None:
        """Error message mentions halt requirement."""
        error = EntropyUnavailableError()

        assert "halted" in str(error).lower()

    def test_source_identifier_in_message(self) -> None:
        """Source identifier appears in message."""
        error = EntropyUnavailableError(source_identifier="random.org")

        assert "random.org" in str(error)

    def test_reason_in_message(self) -> None:
        """Reason appears in message."""
        error = EntropyUnavailableError(reason="Connection timeout")

        assert "Connection timeout" in str(error)

    def test_attributes_stored(self) -> None:
        """Attributes are stored on error."""
        error = EntropyUnavailableError(
            source_identifier="test-source",
            reason="test-reason",
        )

        assert error.source_identifier == "test-source"
        assert error.reason == "test-reason"


class TestWitnessPairRotationViolationError:
    """Tests for WitnessPairRotationViolationError (FR60)."""

    def test_message_includes_fr60(self) -> None:
        """Error message mentions FR60."""
        error = WitnessPairRotationViolationError(
            pair_key="WITNESS:a:WITNESS:b",
            last_appearance=datetime.now(timezone.utc),
        )

        assert "FR60" in str(error)

    def test_message_mentions_24_hours(self) -> None:
        """Error message mentions 24-hour window."""
        error = WitnessPairRotationViolationError(
            pair_key="WITNESS:a:WITNESS:b",
            last_appearance=datetime.now(timezone.utc),
        )

        assert "24 hours" in str(error)

    def test_pair_key_in_message(self) -> None:
        """Pair key appears in message."""
        error = WitnessPairRotationViolationError(
            pair_key="WITNESS:abc:WITNESS:xyz",
            last_appearance=datetime.now(timezone.utc),
        )

        assert "WITNESS:abc:WITNESS:xyz" in str(error)

    def test_attributes_stored(self) -> None:
        """Attributes are stored on error."""
        now = datetime.now(timezone.utc)
        error = WitnessPairRotationViolationError(
            pair_key="test-key",
            last_appearance=now,
        )

        assert error.pair_key == "test-key"
        assert error.last_appearance == now


class TestWitnessSelectionVerificationError:
    """Tests for WitnessSelectionVerificationError (FR59)."""

    def test_message_includes_fr59(self) -> None:
        """Error message mentions FR59."""
        error = WitnessSelectionVerificationError(
            expected_witness="WITNESS:expected",
            computed_witness="WITNESS:computed",
        )

        assert "FR59" in str(error)

    def test_message_mentions_verification_failed(self) -> None:
        """Error message mentions verification failure."""
        error = WitnessSelectionVerificationError(
            expected_witness="WITNESS:expected",
            computed_witness="WITNESS:computed",
        )

        assert "verification failed" in str(error).lower()

    def test_witnesses_in_message(self) -> None:
        """Witness IDs appear in message."""
        error = WitnessSelectionVerificationError(
            expected_witness="WITNESS:expected",
            computed_witness="WITNESS:computed",
        )

        assert "WITNESS:expected" in str(error)
        assert "WITNESS:computed" in str(error)

    def test_attributes_stored(self) -> None:
        """Attributes are stored on error."""
        error = WitnessSelectionVerificationError(
            expected_witness="WITNESS:expected",
            computed_witness="WITNESS:computed",
        )

        assert error.expected_witness == "WITNESS:expected"
        assert error.computed_witness == "WITNESS:computed"


class TestInsufficientWitnessPoolError:
    """Tests for InsufficientWitnessPoolError (FR117)."""

    def test_message_includes_fr117(self) -> None:
        """Error message mentions FR117."""
        error = InsufficientWitnessPoolError(
            available=5,
            minimum_required=12,
        )

        assert "FR117" in str(error)

    def test_message_includes_counts(self) -> None:
        """Error message includes available and required counts."""
        error = InsufficientWitnessPoolError(
            available=5,
            minimum_required=12,
        )

        assert "5" in str(error)
        assert "12" in str(error)

    def test_operation_type_in_message(self) -> None:
        """Operation type appears in message."""
        error = InsufficientWitnessPoolError(
            available=5,
            minimum_required=12,
            operation_type="high-stakes",
        )

        assert "high-stakes" in str(error)

    def test_attributes_stored(self) -> None:
        """Attributes are stored on error."""
        error = InsufficientWitnessPoolError(
            available=5,
            minimum_required=12,
            operation_type="test-op",
        )

        assert error.available == 5
        assert error.minimum_required == 12
        assert error.operation_type == "test-op"


class TestAllWitnessesPairExhaustedError:
    """Tests for AllWitnessesPairExhaustedError (FR60)."""

    def test_message_includes_fr60(self) -> None:
        """Error message mentions FR60."""
        error = AllWitnessesPairExhaustedError(
            pool_size=10,
            attempts_made=10,
        )

        assert "FR60" in str(error)

    def test_message_mentions_rotation(self) -> None:
        """Error message mentions rotation."""
        error = AllWitnessesPairExhaustedError(
            pool_size=10,
            attempts_made=10,
        )

        assert "rotation" in str(error).lower()

    def test_pool_size_in_message(self) -> None:
        """Pool size appears in message."""
        error = AllWitnessesPairExhaustedError(
            pool_size=15,
            attempts_made=15,
        )

        assert "15" in str(error)

    def test_attributes_stored(self) -> None:
        """Attributes are stored on error."""
        error = AllWitnessesPairExhaustedError(
            pool_size=10,
            attempts_made=10,
        )

        assert error.pool_size == 10
        assert error.attempts_made == 10
