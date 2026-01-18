"""Unit tests for override abuse domain events (Story 5.9, FR86-FR87, FP-3).

Tests event payloads, enum values, and signable_content() determinism
for OverrideAbuseRejectedPayload and AnomalyDetectedPayload.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from src.domain.events.override_abuse import (
    ANOMALY_DETECTED_EVENT_TYPE,
    OVERRIDE_ABUSE_REJECTED_EVENT_TYPE,
    AnomalyDetectedPayload,
    AnomalyType,
    OverrideAbuseRejectedPayload,
    ViolationType,
)


class TestViolationType:
    """Tests for ViolationType enum."""

    def test_witness_suppression_value(self) -> None:
        """Test WITNESS_SUPPRESSION enum value."""
        assert ViolationType.WITNESS_SUPPRESSION.value == "WITNESS_SUPPRESSION"

    def test_history_edit_value(self) -> None:
        """Test HISTORY_EDIT enum value (FR87)."""
        assert ViolationType.HISTORY_EDIT.value == "HISTORY_EDIT"

    def test_evidence_destruction_value(self) -> None:
        """Test EVIDENCE_DESTRUCTION enum value (FR87)."""
        assert ViolationType.EVIDENCE_DESTRUCTION.value == "EVIDENCE_DESTRUCTION"

    def test_forbidden_scope_value(self) -> None:
        """Test FORBIDDEN_SCOPE enum value (FR86)."""
        assert ViolationType.FORBIDDEN_SCOPE.value == "FORBIDDEN_SCOPE"

    def test_constitutional_constraint_value(self) -> None:
        """Test CONSTITUTIONAL_CONSTRAINT enum value (FR86)."""
        assert (
            ViolationType.CONSTITUTIONAL_CONSTRAINT.value == "CONSTITUTIONAL_CONSTRAINT"
        )

    def test_all_violation_types_exist(self) -> None:
        """Test all expected violation types are present."""
        expected = {
            "WITNESS_SUPPRESSION",
            "HISTORY_EDIT",
            "EVIDENCE_DESTRUCTION",
            "FORBIDDEN_SCOPE",
            "CONSTITUTIONAL_CONSTRAINT",
        }
        actual = {v.value for v in ViolationType}
        assert actual == expected


class TestAnomalyType:
    """Tests for AnomalyType enum."""

    def test_coordinated_overrides_value(self) -> None:
        """Test COORDINATED_OVERRIDES enum value."""
        assert AnomalyType.COORDINATED_OVERRIDES.value == "COORDINATED_OVERRIDES"

    def test_frequency_spike_value(self) -> None:
        """Test FREQUENCY_SPIKE enum value."""
        assert AnomalyType.FREQUENCY_SPIKE.value == "FREQUENCY_SPIKE"

    def test_pattern_correlation_value(self) -> None:
        """Test PATTERN_CORRELATION enum value."""
        assert AnomalyType.PATTERN_CORRELATION.value == "PATTERN_CORRELATION"

    def test_slow_burn_erosion_value(self) -> None:
        """Test SLOW_BURN_EROSION enum value (CT-9)."""
        assert AnomalyType.SLOW_BURN_EROSION.value == "SLOW_BURN_EROSION"

    def test_all_anomaly_types_exist(self) -> None:
        """Test all expected anomaly types are present."""
        expected = {
            "COORDINATED_OVERRIDES",
            "FREQUENCY_SPIKE",
            "PATTERN_CORRELATION",
            "SLOW_BURN_EROSION",
        }
        actual = {v.value for v in AnomalyType}
        assert actual == expected


class TestOverrideAbuseRejectedPayload:
    """Tests for OverrideAbuseRejectedPayload."""

    def test_event_type_constant(self) -> None:
        """Test event type constant value."""
        assert OVERRIDE_ABUSE_REJECTED_EVENT_TYPE == "override.abuse_rejected"

    def test_create_with_required_fields(self) -> None:
        """Test payload creation with all required fields."""
        rejected_at = datetime(2026, 1, 7, 12, 0, 0, tzinfo=timezone.utc)
        payload = OverrideAbuseRejectedPayload(
            keeper_id="keeper-1",
            scope="history.delete",
            violation_type=ViolationType.HISTORY_EDIT,
            violation_details="FR87: Override scope 'history.delete' attempts to edit event history",
            rejected_at=rejected_at,
        )

        assert payload.keeper_id == "keeper-1"
        assert payload.scope == "history.delete"
        assert payload.violation_type == ViolationType.HISTORY_EDIT
        assert "FR87" in payload.violation_details
        assert payload.rejected_at == rejected_at

    def test_payload_is_frozen(self) -> None:
        """Test that payload is immutable."""
        payload = OverrideAbuseRejectedPayload(
            keeper_id="keeper-1",
            scope="history.delete",
            violation_type=ViolationType.HISTORY_EDIT,
            violation_details="test",
            rejected_at=datetime.now(timezone.utc),
        )

        with pytest.raises(AttributeError):
            payload.keeper_id = "keeper-2"  # type: ignore[misc]

    def test_signable_content_returns_bytes(self) -> None:
        """Test signable_content() returns bytes (CT-12)."""
        payload = OverrideAbuseRejectedPayload(
            keeper_id="keeper-1",
            scope="history.delete",
            violation_type=ViolationType.HISTORY_EDIT,
            violation_details="test",
            rejected_at=datetime(2026, 1, 7, 12, 0, 0, tzinfo=timezone.utc),
        )

        content = payload.signable_content()
        assert isinstance(content, bytes)

    def test_signable_content_is_deterministic(self) -> None:
        """Test signable_content() is deterministic for witnessing (CT-12)."""
        rejected_at = datetime(2026, 1, 7, 12, 0, 0, tzinfo=timezone.utc)

        payload1 = OverrideAbuseRejectedPayload(
            keeper_id="keeper-1",
            scope="history.delete",
            violation_type=ViolationType.HISTORY_EDIT,
            violation_details="test",
            rejected_at=rejected_at,
        )

        payload2 = OverrideAbuseRejectedPayload(
            keeper_id="keeper-1",
            scope="history.delete",
            violation_type=ViolationType.HISTORY_EDIT,
            violation_details="test",
            rejected_at=rejected_at,
        )

        assert payload1.signable_content() == payload2.signable_content()

    def test_signable_content_is_valid_json(self) -> None:
        """Test signable_content() is valid JSON."""
        payload = OverrideAbuseRejectedPayload(
            keeper_id="keeper-1",
            scope="history.delete",
            violation_type=ViolationType.HISTORY_EDIT,
            violation_details="test",
            rejected_at=datetime(2026, 1, 7, 12, 0, 0, tzinfo=timezone.utc),
        )

        content = payload.signable_content()
        parsed = json.loads(content.decode("utf-8"))

        assert parsed["event_type"] == "OverrideAbuseRejected"
        assert parsed["keeper_id"] == "keeper-1"
        assert parsed["scope"] == "history.delete"
        assert parsed["violation_type"] == "HISTORY_EDIT"


class TestAnomalyDetectedPayload:
    """Tests for AnomalyDetectedPayload."""

    def test_event_type_constant(self) -> None:
        """Test event type constant value."""
        assert ANOMALY_DETECTED_EVENT_TYPE == "override.anomaly_detected"

    def test_create_with_required_fields(self) -> None:
        """Test payload creation with all required fields."""
        detected_at = datetime(2026, 1, 7, 12, 0, 0, tzinfo=timezone.utc)
        payload = AnomalyDetectedPayload(
            anomaly_type=AnomalyType.FREQUENCY_SPIKE,
            keeper_ids=("keeper-1", "keeper-2"),
            detection_method="statistical_baseline_deviation",
            confidence_score=0.85,
            time_window_days=90,
            details="Frequency spike detected",
            detected_at=detected_at,
        )

        assert payload.anomaly_type == AnomalyType.FREQUENCY_SPIKE
        assert payload.keeper_ids == ("keeper-1", "keeper-2")
        assert payload.detection_method == "statistical_baseline_deviation"
        assert payload.confidence_score == 0.85
        assert payload.time_window_days == 90
        assert payload.detected_at == detected_at

    def test_payload_is_frozen(self) -> None:
        """Test that payload is immutable."""
        payload = AnomalyDetectedPayload(
            anomaly_type=AnomalyType.FREQUENCY_SPIKE,
            keeper_ids=("keeper-1",),
            detection_method="test",
            confidence_score=0.8,
            time_window_days=90,
            details="test",
            detected_at=datetime.now(timezone.utc),
        )

        with pytest.raises(AttributeError):
            payload.anomaly_type = AnomalyType.SLOW_BURN_EROSION  # type: ignore[misc]

    def test_confidence_score_validation_lower_bound(self) -> None:
        """Test confidence score cannot be below 0.0."""
        with pytest.raises(ValueError, match="confidence_score must be between"):
            AnomalyDetectedPayload(
                anomaly_type=AnomalyType.FREQUENCY_SPIKE,
                keeper_ids=("keeper-1",),
                detection_method="test",
                confidence_score=-0.1,
                time_window_days=90,
                details="test",
                detected_at=datetime.now(timezone.utc),
            )

    def test_confidence_score_validation_upper_bound(self) -> None:
        """Test confidence score cannot exceed 1.0."""
        with pytest.raises(ValueError, match="confidence_score must be between"):
            AnomalyDetectedPayload(
                anomaly_type=AnomalyType.FREQUENCY_SPIKE,
                keeper_ids=("keeper-1",),
                detection_method="test",
                confidence_score=1.1,
                time_window_days=90,
                details="test",
                detected_at=datetime.now(timezone.utc),
            )

    def test_confidence_score_valid_at_boundaries(self) -> None:
        """Test confidence score valid at 0.0 and 1.0."""
        detected_at = datetime.now(timezone.utc)

        # 0.0 is valid
        payload_zero = AnomalyDetectedPayload(
            anomaly_type=AnomalyType.FREQUENCY_SPIKE,
            keeper_ids=("keeper-1",),
            detection_method="test",
            confidence_score=0.0,
            time_window_days=90,
            details="test",
            detected_at=detected_at,
        )
        assert payload_zero.confidence_score == 0.0

        # 1.0 is valid
        payload_one = AnomalyDetectedPayload(
            anomaly_type=AnomalyType.FREQUENCY_SPIKE,
            keeper_ids=("keeper-1",),
            detection_method="test",
            confidence_score=1.0,
            time_window_days=90,
            details="test",
            detected_at=detected_at,
        )
        assert payload_one.confidence_score == 1.0

    def test_signable_content_returns_bytes(self) -> None:
        """Test signable_content() returns bytes (CT-12)."""
        payload = AnomalyDetectedPayload(
            anomaly_type=AnomalyType.FREQUENCY_SPIKE,
            keeper_ids=("keeper-1",),
            detection_method="test",
            confidence_score=0.8,
            time_window_days=90,
            details="test",
            detected_at=datetime(2026, 1, 7, 12, 0, 0, tzinfo=timezone.utc),
        )

        content = payload.signable_content()
        assert isinstance(content, bytes)

    def test_signable_content_is_deterministic(self) -> None:
        """Test signable_content() is deterministic for witnessing (CT-12)."""
        detected_at = datetime(2026, 1, 7, 12, 0, 0, tzinfo=timezone.utc)

        payload1 = AnomalyDetectedPayload(
            anomaly_type=AnomalyType.SLOW_BURN_EROSION,
            keeper_ids=("keeper-1", "keeper-2"),
            detection_method="test",
            confidence_score=0.75,
            time_window_days=365,
            details="Slow-burn erosion detected",
            detected_at=detected_at,
        )

        payload2 = AnomalyDetectedPayload(
            anomaly_type=AnomalyType.SLOW_BURN_EROSION,
            keeper_ids=("keeper-1", "keeper-2"),
            detection_method="test",
            confidence_score=0.75,
            time_window_days=365,
            details="Slow-burn erosion detected",
            detected_at=detected_at,
        )

        assert payload1.signable_content() == payload2.signable_content()

    def test_signable_content_is_valid_json(self) -> None:
        """Test signable_content() is valid JSON."""
        payload = AnomalyDetectedPayload(
            anomaly_type=AnomalyType.COORDINATED_OVERRIDES,
            keeper_ids=("keeper-1", "keeper-2"),
            detection_method="statistical_baseline_deviation",
            confidence_score=0.8,
            time_window_days=90,
            details="Coordinated pattern detected",
            detected_at=datetime(2026, 1, 7, 12, 0, 0, tzinfo=timezone.utc),
        )

        content = payload.signable_content()
        parsed = json.loads(content.decode("utf-8"))

        assert parsed["event_type"] == "AnomalyDetected"
        assert parsed["anomaly_type"] == "COORDINATED_OVERRIDES"
        assert parsed["keeper_ids"] == ["keeper-1", "keeper-2"]
        assert parsed["confidence_score"] == 0.8
