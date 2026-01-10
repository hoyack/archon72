"""Unit tests for witness anomaly events (Story 6.6, FR116-FR117)."""

from datetime import datetime, timezone
import json
import pytest

from src.domain.events.witness_anomaly import (
    WITNESS_ANOMALY_EVENT_TYPE,
    WITNESS_POOL_DEGRADED_EVENT_TYPE,
    ReviewStatus,
    WitnessAnomalyEventPayload,
    WitnessAnomalyType,
    WitnessPoolDegradedEventPayload,
)


class TestWitnessAnomalyType:
    """Tests for WitnessAnomalyType enum."""

    def test_co_occurrence_value(self) -> None:
        """Test CO_OCCURRENCE enum value."""
        assert WitnessAnomalyType.CO_OCCURRENCE.value == "co_occurrence"

    def test_unavailability_pattern_value(self) -> None:
        """Test UNAVAILABILITY_PATTERN enum value."""
        assert WitnessAnomalyType.UNAVAILABILITY_PATTERN.value == "unavailability_pattern"

    def test_excessive_pairing_value(self) -> None:
        """Test EXCESSIVE_PAIRING enum value."""
        assert WitnessAnomalyType.EXCESSIVE_PAIRING.value == "excessive_pairing"


class TestReviewStatus:
    """Tests for ReviewStatus enum."""

    def test_pending_value(self) -> None:
        """Test PENDING enum value."""
        assert ReviewStatus.PENDING.value == "pending"

    def test_investigating_value(self) -> None:
        """Test INVESTIGATING enum value."""
        assert ReviewStatus.INVESTIGATING.value == "investigating"

    def test_cleared_value(self) -> None:
        """Test CLEARED enum value."""
        assert ReviewStatus.CLEARED.value == "cleared"

    def test_confirmed_value(self) -> None:
        """Test CONFIRMED enum value."""
        assert ReviewStatus.CONFIRMED.value == "confirmed"


class TestWitnessAnomalyEventPayload:
    """Tests for WitnessAnomalyEventPayload."""

    def test_create_with_all_fields(self) -> None:
        """Test creation with all fields."""
        now = datetime.now(timezone.utc)
        payload = WitnessAnomalyEventPayload(
            anomaly_type=WitnessAnomalyType.CO_OCCURRENCE,
            affected_witnesses=("witness1", "witness2"),
            confidence_score=0.85,
            detection_window_hours=168,
            occurrence_count=15,
            expected_count=5.0,
            detected_at=now,
            review_status=ReviewStatus.PENDING,
            details="High co-occurrence detected",
        )

        assert payload.anomaly_type == WitnessAnomalyType.CO_OCCURRENCE
        assert payload.affected_witnesses == ("witness1", "witness2")
        assert payload.confidence_score == 0.85
        assert payload.detection_window_hours == 168
        assert payload.occurrence_count == 15
        assert payload.expected_count == 5.0
        assert payload.detected_at == now
        assert payload.review_status == ReviewStatus.PENDING
        assert payload.details == "High co-occurrence detected"

    def test_create_with_default_review_status(self) -> None:
        """Test creation with default review status."""
        now = datetime.now(timezone.utc)
        payload = WitnessAnomalyEventPayload(
            anomaly_type=WitnessAnomalyType.UNAVAILABILITY_PATTERN,
            affected_witnesses=("witness1",),
            confidence_score=0.75,
            detection_window_hours=72,
            occurrence_count=10,
            expected_count=2.0,
            detected_at=now,
        )

        assert payload.review_status == ReviewStatus.PENDING
        assert payload.details == ""

    def test_confidence_score_validation_above_one(self) -> None:
        """Test that confidence_score > 1.0 raises ValueError."""
        now = datetime.now(timezone.utc)
        with pytest.raises(ValueError, match="confidence_score must be between 0.0 and 1.0"):
            WitnessAnomalyEventPayload(
                anomaly_type=WitnessAnomalyType.CO_OCCURRENCE,
                affected_witnesses=("witness1", "witness2"),
                confidence_score=1.5,
                detection_window_hours=168,
                occurrence_count=15,
                expected_count=5.0,
                detected_at=now,
            )

    def test_confidence_score_validation_below_zero(self) -> None:
        """Test that confidence_score < 0.0 raises ValueError."""
        now = datetime.now(timezone.utc)
        with pytest.raises(ValueError, match="confidence_score must be between 0.0 and 1.0"):
            WitnessAnomalyEventPayload(
                anomaly_type=WitnessAnomalyType.CO_OCCURRENCE,
                affected_witnesses=("witness1", "witness2"),
                confidence_score=-0.1,
                detection_window_hours=168,
                occurrence_count=15,
                expected_count=5.0,
                detected_at=now,
            )

    def test_detection_window_hours_validation(self) -> None:
        """Test that detection_window_hours <= 0 raises ValueError."""
        now = datetime.now(timezone.utc)
        with pytest.raises(ValueError, match="detection_window_hours must be positive"):
            WitnessAnomalyEventPayload(
                anomaly_type=WitnessAnomalyType.CO_OCCURRENCE,
                affected_witnesses=("witness1", "witness2"),
                confidence_score=0.8,
                detection_window_hours=0,
                occurrence_count=15,
                expected_count=5.0,
                detected_at=now,
            )

    def test_occurrence_count_validation(self) -> None:
        """Test that occurrence_count < 0 raises ValueError."""
        now = datetime.now(timezone.utc)
        with pytest.raises(ValueError, match="occurrence_count must be non-negative"):
            WitnessAnomalyEventPayload(
                anomaly_type=WitnessAnomalyType.CO_OCCURRENCE,
                affected_witnesses=("witness1", "witness2"),
                confidence_score=0.8,
                detection_window_hours=168,
                occurrence_count=-1,
                expected_count=5.0,
                detected_at=now,
            )

    def test_expected_count_validation(self) -> None:
        """Test that expected_count < 0 raises ValueError."""
        now = datetime.now(timezone.utc)
        with pytest.raises(ValueError, match="expected_count must be non-negative"):
            WitnessAnomalyEventPayload(
                anomaly_type=WitnessAnomalyType.CO_OCCURRENCE,
                affected_witnesses=("witness1", "witness2"),
                confidence_score=0.8,
                detection_window_hours=168,
                occurrence_count=15,
                expected_count=-1.0,
                detected_at=now,
            )

    def test_signable_content_determinism(self) -> None:
        """Test signable_content returns deterministic bytes."""
        now = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        payload = WitnessAnomalyEventPayload(
            anomaly_type=WitnessAnomalyType.CO_OCCURRENCE,
            affected_witnesses=("witness1", "witness2"),
            confidence_score=0.85,
            detection_window_hours=168,
            occurrence_count=15,
            expected_count=5.0,
            detected_at=now,
            review_status=ReviewStatus.PENDING,
            details="Test",
        )

        # Call twice
        content1 = payload.signable_content()
        content2 = payload.signable_content()

        assert content1 == content2
        assert isinstance(content1, bytes)

    def test_signable_content_json_format(self) -> None:
        """Test signable_content returns valid JSON."""
        now = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        payload = WitnessAnomalyEventPayload(
            anomaly_type=WitnessAnomalyType.CO_OCCURRENCE,
            affected_witnesses=("witness1", "witness2"),
            confidence_score=0.85,
            detection_window_hours=168,
            occurrence_count=15,
            expected_count=5.0,
            detected_at=now,
        )

        content = payload.signable_content()
        parsed = json.loads(content.decode("utf-8"))

        assert parsed["event_type"] == WITNESS_ANOMALY_EVENT_TYPE
        assert parsed["anomaly_type"] == "co_occurrence"
        assert parsed["affected_witnesses"] == ["witness1", "witness2"]
        assert parsed["confidence_score"] == 0.85

    def test_to_dict(self) -> None:
        """Test to_dict serialization."""
        now = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        payload = WitnessAnomalyEventPayload(
            anomaly_type=WitnessAnomalyType.CO_OCCURRENCE,
            affected_witnesses=("witness1", "witness2"),
            confidence_score=0.85,
            detection_window_hours=168,
            occurrence_count=15,
            expected_count=5.0,
            detected_at=now,
        )

        result = payload.to_dict()

        assert result["anomaly_type"] == "co_occurrence"
        assert result["affected_witnesses"] == ["witness1", "witness2"]
        assert result["confidence_score"] == 0.85
        assert result["detection_window_hours"] == 168
        assert result["occurrence_count"] == 15
        assert result["expected_count"] == 5.0

    def test_chi_square_value_calculation(self) -> None:
        """Test chi_square_value property calculation."""
        now = datetime.now(timezone.utc)
        payload = WitnessAnomalyEventPayload(
            anomaly_type=WitnessAnomalyType.CO_OCCURRENCE,
            affected_witnesses=("witness1", "witness2"),
            confidence_score=0.85,
            detection_window_hours=168,
            occurrence_count=15,
            expected_count=5.0,
            detected_at=now,
        )

        # Chi-square = (15 - 5)^2 / 5 = 100 / 5 = 20
        assert payload.chi_square_value == 20.0

    def test_chi_square_value_zero_expected(self) -> None:
        """Test chi_square_value with zero expected returns infinity."""
        now = datetime.now(timezone.utc)
        payload = WitnessAnomalyEventPayload(
            anomaly_type=WitnessAnomalyType.CO_OCCURRENCE,
            affected_witnesses=("witness1", "witness2"),
            confidence_score=0.85,
            detection_window_hours=168,
            occurrence_count=5,
            expected_count=0.0,
            detected_at=now,
        )

        assert payload.chi_square_value == float("inf")

    def test_chi_square_value_zero_both(self) -> None:
        """Test chi_square_value with zero expected and zero observed returns 0."""
        now = datetime.now(timezone.utc)
        payload = WitnessAnomalyEventPayload(
            anomaly_type=WitnessAnomalyType.CO_OCCURRENCE,
            affected_witnesses=("witness1", "witness2"),
            confidence_score=0.5,
            detection_window_hours=168,
            occurrence_count=0,
            expected_count=0.0,
            detected_at=now,
        )

        assert payload.chi_square_value == 0.0

    def test_frozen_dataclass(self) -> None:
        """Test that payload is immutable."""
        now = datetime.now(timezone.utc)
        payload = WitnessAnomalyEventPayload(
            anomaly_type=WitnessAnomalyType.CO_OCCURRENCE,
            affected_witnesses=("witness1", "witness2"),
            confidence_score=0.85,
            detection_window_hours=168,
            occurrence_count=15,
            expected_count=5.0,
            detected_at=now,
        )

        with pytest.raises(AttributeError):
            payload.confidence_score = 0.5  # type: ignore


class TestWitnessPoolDegradedEventPayload:
    """Tests for WitnessPoolDegradedEventPayload."""

    def test_create_with_all_fields(self) -> None:
        """Test creation with all fields."""
        now = datetime.now(timezone.utc)
        payload = WitnessPoolDegradedEventPayload(
            available_witnesses=8,
            minimum_required=12,
            operation_type="high_stakes",
            is_blocking=True,
            degraded_at=now,
            excluded_witnesses=("witness1", "witness2"),
            reason="Pool below minimum due to anomaly exclusions",
        )

        assert payload.available_witnesses == 8
        assert payload.minimum_required == 12
        assert payload.operation_type == "high_stakes"
        assert payload.is_blocking is True
        assert payload.degraded_at == now
        assert payload.excluded_witnesses == ("witness1", "witness2")
        assert payload.reason == "Pool below minimum due to anomaly exclusions"

    def test_create_with_defaults(self) -> None:
        """Test creation with default values."""
        now = datetime.now(timezone.utc)
        payload = WitnessPoolDegradedEventPayload(
            available_witnesses=10,
            minimum_required=12,
            operation_type="high_stakes",
            is_blocking=False,
            degraded_at=now,
        )

        assert payload.excluded_witnesses == ()
        assert payload.reason == ""

    def test_available_witnesses_validation(self) -> None:
        """Test that available_witnesses < 0 raises ValueError."""
        now = datetime.now(timezone.utc)
        with pytest.raises(ValueError, match="available_witnesses must be non-negative"):
            WitnessPoolDegradedEventPayload(
                available_witnesses=-1,
                minimum_required=12,
                operation_type="high_stakes",
                is_blocking=True,
                degraded_at=now,
            )

    def test_minimum_required_validation(self) -> None:
        """Test that minimum_required <= 0 raises ValueError."""
        now = datetime.now(timezone.utc)
        with pytest.raises(ValueError, match="minimum_required must be positive"):
            WitnessPoolDegradedEventPayload(
                available_witnesses=8,
                minimum_required=0,
                operation_type="high_stakes",
                is_blocking=True,
                degraded_at=now,
            )

    def test_signable_content_determinism(self) -> None:
        """Test signable_content returns deterministic bytes."""
        now = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        payload = WitnessPoolDegradedEventPayload(
            available_witnesses=8,
            minimum_required=12,
            operation_type="high_stakes",
            is_blocking=True,
            degraded_at=now,
        )

        content1 = payload.signable_content()
        content2 = payload.signable_content()

        assert content1 == content2
        assert isinstance(content1, bytes)

    def test_signable_content_json_format(self) -> None:
        """Test signable_content returns valid JSON."""
        now = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        payload = WitnessPoolDegradedEventPayload(
            available_witnesses=8,
            minimum_required=12,
            operation_type="high_stakes",
            is_blocking=True,
            degraded_at=now,
        )

        content = payload.signable_content()
        parsed = json.loads(content.decode("utf-8"))

        assert parsed["event_type"] == WITNESS_POOL_DEGRADED_EVENT_TYPE
        assert parsed["available_witnesses"] == 8
        assert parsed["minimum_required"] == 12
        assert parsed["is_blocking"] is True

    def test_to_dict(self) -> None:
        """Test to_dict serialization."""
        now = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        payload = WitnessPoolDegradedEventPayload(
            available_witnesses=8,
            minimum_required=12,
            operation_type="high_stakes",
            is_blocking=True,
            degraded_at=now,
            excluded_witnesses=("witness1",),
        )

        result = payload.to_dict()

        assert result["available_witnesses"] == 8
        assert result["minimum_required"] == 12
        assert result["operation_type"] == "high_stakes"
        assert result["is_blocking"] is True
        assert result["excluded_witnesses"] == ["witness1"]

    def test_effective_count_property(self) -> None:
        """Test effective_count property calculation."""
        now = datetime.now(timezone.utc)
        payload = WitnessPoolDegradedEventPayload(
            available_witnesses=10,
            minimum_required=12,
            operation_type="high_stakes",
            is_blocking=True,
            degraded_at=now,
            excluded_witnesses=("witness1", "witness2"),
        )

        assert payload.effective_count == 8  # 10 - 2

    def test_effective_count_no_excluded(self) -> None:
        """Test effective_count with no excluded witnesses."""
        now = datetime.now(timezone.utc)
        payload = WitnessPoolDegradedEventPayload(
            available_witnesses=10,
            minimum_required=12,
            operation_type="high_stakes",
            is_blocking=True,
            degraded_at=now,
        )

        assert payload.effective_count == 10

    def test_frozen_dataclass(self) -> None:
        """Test that payload is immutable."""
        now = datetime.now(timezone.utc)
        payload = WitnessPoolDegradedEventPayload(
            available_witnesses=8,
            minimum_required=12,
            operation_type="high_stakes",
            is_blocking=True,
            degraded_at=now,
        )

        with pytest.raises(AttributeError):
            payload.available_witnesses = 10  # type: ignore


class TestEventTypeConstants:
    """Tests for event type constants."""

    def test_witness_anomaly_event_type(self) -> None:
        """Test WITNESS_ANOMALY_EVENT_TYPE constant."""
        assert WITNESS_ANOMALY_EVENT_TYPE == "witness.anomaly"

    def test_witness_pool_degraded_event_type(self) -> None:
        """Test WITNESS_POOL_DEGRADED_EVENT_TYPE constant."""
        assert WITNESS_POOL_DEGRADED_EVENT_TYPE == "witness.pool_degraded"
