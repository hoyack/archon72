"""Unit tests for witness anomaly errors (Story 6.6, FR116-FR117)."""

from datetime import datetime, timezone

from src.domain.errors.constitutional import ConstitutionalViolationError
from src.domain.errors.witness_anomaly import (
    AnomalyScanError,
    WitnessAnomalyError,
    WitnessCollusionSuspectedError,
    WitnessPairExcludedError,
    WitnessPoolDegradedError,
    WitnessUnavailabilityPatternError,
)


class TestWitnessAnomalyErrorHierarchy:
    """Tests for witness anomaly error inheritance."""

    def test_witness_anomaly_error_inherits_constitutional(self) -> None:
        """Test WitnessAnomalyError inherits from ConstitutionalViolationError."""
        assert issubclass(WitnessAnomalyError, ConstitutionalViolationError)

    def test_witness_collusion_suspected_inherits(self) -> None:
        """Test WitnessCollusionSuspectedError inheritance."""
        assert issubclass(WitnessCollusionSuspectedError, WitnessAnomalyError)

    def test_witness_pair_excluded_inherits(self) -> None:
        """Test WitnessPairExcludedError inheritance."""
        assert issubclass(WitnessPairExcludedError, WitnessAnomalyError)

    def test_witness_unavailability_pattern_inherits(self) -> None:
        """Test WitnessUnavailabilityPatternError inheritance."""
        assert issubclass(WitnessUnavailabilityPatternError, WitnessAnomalyError)

    def test_witness_pool_degraded_inherits(self) -> None:
        """Test WitnessPoolDegradedError inheritance."""
        assert issubclass(WitnessPoolDegradedError, WitnessAnomalyError)

    def test_anomaly_scan_error_inherits(self) -> None:
        """Test AnomalyScanError inheritance."""
        assert issubclass(AnomalyScanError, WitnessAnomalyError)


class TestWitnessCollusionSuspectedError:
    """Tests for WitnessCollusionSuspectedError."""

    def test_error_creation(self) -> None:
        """Test error creation with attributes."""
        error = WitnessCollusionSuspectedError(
            witnesses=("witness1", "witness2"),
            confidence=0.85,
        )

        assert error.witnesses == ("witness1", "witness2")
        assert error.confidence == 0.85

    def test_message_contains_fr116(self) -> None:
        """Test error message contains FR116 reference."""
        error = WitnessCollusionSuspectedError(
            witnesses=("witness1", "witness2"),
            confidence=0.85,
        )

        assert "FR116" in str(error)

    def test_message_contains_witnesses(self) -> None:
        """Test error message contains witness IDs."""
        error = WitnessCollusionSuspectedError(
            witnesses=("witness1", "witness2"),
            confidence=0.85,
        )

        assert "witness1" in str(error)
        assert "witness2" in str(error)

    def test_message_contains_confidence(self) -> None:
        """Test error message contains confidence score."""
        error = WitnessCollusionSuspectedError(
            witnesses=("witness1", "witness2"),
            confidence=0.85,
        )

        assert "0.85" in str(error)

    def test_single_witness(self) -> None:
        """Test error with single witness."""
        error = WitnessCollusionSuspectedError(
            witnesses=("witness1",),
            confidence=0.75,
        )

        assert error.witnesses == ("witness1",)


class TestWitnessPairExcludedError:
    """Tests for WitnessPairExcludedError."""

    def test_error_creation(self) -> None:
        """Test error creation with attributes."""
        excluded_until = datetime(2024, 1, 16, 12, 0, 0, tzinfo=timezone.utc)
        error = WitnessPairExcludedError(
            pair_key="witness1:witness2",
            excluded_until=excluded_until,
        )

        assert error.pair_key == "witness1:witness2"
        assert error.excluded_until == excluded_until

    def test_message_contains_fr116(self) -> None:
        """Test error message contains FR116 reference."""
        excluded_until = datetime.now(timezone.utc)
        error = WitnessPairExcludedError(
            pair_key="witness1:witness2",
            excluded_until=excluded_until,
        )

        assert "FR116" in str(error)

    def test_message_contains_pair_key(self) -> None:
        """Test error message contains pair key."""
        excluded_until = datetime.now(timezone.utc)
        error = WitnessPairExcludedError(
            pair_key="witness1:witness2",
            excluded_until=excluded_until,
        )

        assert "witness1:witness2" in str(error)


class TestWitnessUnavailabilityPatternError:
    """Tests for WitnessUnavailabilityPatternError."""

    def test_error_creation(self) -> None:
        """Test error creation with attributes."""
        error = WitnessUnavailabilityPatternError(
            witness_ids=("witness1", "witness2", "witness3"),
            unavailable_count=15,
        )

        assert error.witness_ids == ("witness1", "witness2", "witness3")
        assert error.unavailable_count == 15

    def test_message_contains_fr116(self) -> None:
        """Test error message contains FR116 reference."""
        error = WitnessUnavailabilityPatternError(
            witness_ids=("witness1",),
            unavailable_count=10,
        )

        assert "FR116" in str(error)

    def test_message_contains_witness_ids(self) -> None:
        """Test error message contains witness IDs."""
        error = WitnessUnavailabilityPatternError(
            witness_ids=("witness1", "witness2"),
            unavailable_count=10,
        )

        assert "witness1" in str(error)
        assert "witness2" in str(error)

    def test_message_contains_unavailable_count(self) -> None:
        """Test error message contains unavailable count."""
        error = WitnessUnavailabilityPatternError(
            witness_ids=("witness1",),
            unavailable_count=15,
        )

        assert "15" in str(error)


class TestWitnessPoolDegradedError:
    """Tests for WitnessPoolDegradedError."""

    def test_error_creation(self) -> None:
        """Test error creation with attributes."""
        error = WitnessPoolDegradedError(
            available=8,
            minimum_required=12,
            excluded_count=2,
            operation_type="high_stakes",
        )

        assert error.available == 8
        assert error.minimum_required == 12
        assert error.excluded_count == 2
        assert error.operation_type == "high_stakes"

    def test_error_creation_with_defaults(self) -> None:
        """Test error creation with default values."""
        error = WitnessPoolDegradedError(
            available=8,
            minimum_required=12,
        )

        assert error.excluded_count == 0
        assert error.operation_type == "high_stakes"

    def test_message_contains_fr117(self) -> None:
        """Test error message contains FR117 reference."""
        error = WitnessPoolDegradedError(
            available=8,
            minimum_required=12,
        )

        assert "FR117" in str(error)

    def test_message_contains_available(self) -> None:
        """Test error message contains available count."""
        error = WitnessPoolDegradedError(
            available=8,
            minimum_required=12,
        )

        assert "8" in str(error)

    def test_message_contains_minimum_required(self) -> None:
        """Test error message contains minimum required."""
        error = WitnessPoolDegradedError(
            available=8,
            minimum_required=12,
        )

        assert "12" in str(error)

    def test_message_contains_operation_type(self) -> None:
        """Test error message contains operation type."""
        error = WitnessPoolDegradedError(
            available=8,
            minimum_required=12,
            operation_type="high_stakes",
        )

        assert "high_stakes" in str(error)


class TestAnomalyScanError:
    """Tests for AnomalyScanError."""

    def test_error_creation_with_reason(self) -> None:
        """Test error creation with reason."""
        error = AnomalyScanError(reason="Database connection failed")

        assert error.reason == "Database connection failed"
        assert error.scan_type is None

    def test_error_creation_with_scan_type(self) -> None:
        """Test error creation with scan type."""
        error = AnomalyScanError(
            reason="Analysis timed out",
            scan_type="co_occurrence",
        )

        assert error.reason == "Analysis timed out"
        assert error.scan_type == "co_occurrence"

    def test_message_contains_reason(self) -> None:
        """Test error message contains reason."""
        error = AnomalyScanError(reason="Test failure reason")

        assert "Test failure reason" in str(error)

    def test_message_contains_scan_type_when_provided(self) -> None:
        """Test error message contains scan type when provided."""
        error = AnomalyScanError(
            reason="Analysis failed",
            scan_type="unavailability",
        )

        assert "unavailability" in str(error)

    def test_message_without_scan_type(self) -> None:
        """Test error message format without scan type."""
        error = AnomalyScanError(reason="Generic failure")

        message = str(error)
        assert "Anomaly scan failed" in message
        assert "Generic failure" in message
