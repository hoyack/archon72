"""Unit tests for FilterDecisionLog domain model.

Story: consent-gov-3.3: Filter Decision Logging

Tests the immutable log entry structure for filter decisions:
- Validation constraints for each decision type
- Content privacy (hashes, not raw content)
- Factory methods for each decision type
- Event payload conversion
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.domain.governance.filter import (
    FilterDecision,
    FilterDecisionLog,
    FilterVersion,
    MessageType,
    RejectionReason,
    TransformationLog,
    ViolationType,
)


class TestTransformationLog:
    """Tests for TransformationLog value object."""

    def test_valid_transformation_log(self) -> None:
        """Valid TransformationLog is created."""
        log = TransformationLog(
            rule_id="urgency-1",
            pattern=r"URGENT",
            original_hash="blake3:abc123",
            replacement_hash="blake3:def456",
        )

        assert log.rule_id == "urgency-1"
        assert log.pattern == r"URGENT"

    def test_rule_id_required(self) -> None:
        """rule_id is required."""
        with pytest.raises(ValueError, match="rule_id is required"):
            TransformationLog(
                rule_id="",
                pattern=r"URGENT",
                original_hash="blake3:abc123",
                replacement_hash="blake3:def456",
            )

    def test_original_hash_required(self) -> None:
        """original_hash is required."""
        with pytest.raises(ValueError, match="original_hash is required"):
            TransformationLog(
                rule_id="urgency-1",
                pattern=r"URGENT",
                original_hash="",
                replacement_hash="blake3:def456",
            )

    def test_replacement_hash_required(self) -> None:
        """replacement_hash is required."""
        with pytest.raises(ValueError, match="replacement_hash is required"):
            TransformationLog(
                rule_id="urgency-1",
                pattern=r"URGENT",
                original_hash="blake3:abc123",
                replacement_hash="",
            )


class TestFilterDecisionLogAccepted:
    """Tests for ACCEPTED decision logs."""

    @pytest.fixture
    def filter_version(self) -> FilterVersion:
        return FilterVersion(major=1, minor=0, patch=0, rules_hash="test_hash")

    @pytest.fixture
    def timestamp(self) -> datetime:
        return datetime(2026, 1, 17, 12, 0, 0, tzinfo=timezone.utc)

    def test_accepted_log_created(
        self, filter_version: FilterVersion, timestamp: datetime
    ) -> None:
        """ACCEPTED log can be created with valid data."""
        log = FilterDecisionLog.for_accepted(
            decision_id=uuid4(),
            input_hash="blake3:abc123def456abc123def456abc123def456abc123def456abc123def456ab12",
            output_hash="blake3:def456abc123def456abc123def456abc123def456abc123def456abc123de34",
            filter_version=filter_version,
            message_type=MessageType.TASK_ACTIVATION,
            earl_id=uuid4(),
            timestamp=timestamp,
        )

        assert log.decision == FilterDecision.ACCEPTED
        assert log.output_hash is not None

    def test_accepted_log_with_transformations(
        self, filter_version: FilterVersion, timestamp: datetime
    ) -> None:
        """ACCEPTED log can include transformations."""
        transformations = (
            TransformationLog(
                rule_id="urgency-1",
                pattern=r"URGENT",
                original_hash="blake3:abc123",
                replacement_hash="blake3:def456",
            ),
        )

        log = FilterDecisionLog.for_accepted(
            decision_id=uuid4(),
            input_hash="blake3:abc123def456abc123def456abc123def456abc123def456abc123def456ab12",
            output_hash="blake3:def456abc123def456abc123def456abc123def456abc123def456abc123de34",
            filter_version=filter_version,
            message_type=MessageType.TASK_ACTIVATION,
            earl_id=uuid4(),
            timestamp=timestamp,
            transformations=transformations,
        )

        assert log.was_transformed
        assert log.transformation_count == 1

    def test_accepted_requires_output_hash(
        self, filter_version: FilterVersion, timestamp: datetime
    ) -> None:
        """ACCEPTED log requires output_hash."""
        with pytest.raises(ValueError, match="ACCEPTED log must include output_hash"):
            FilterDecisionLog(
                decision_id=uuid4(),
                decision=FilterDecision.ACCEPTED,
                input_hash="blake3:abc123",
                output_hash=None,  # Missing
                filter_version=filter_version,
                message_type=MessageType.TASK_ACTIVATION,
                earl_id=uuid4(),
                timestamp=timestamp,
            )

    def test_accepted_cannot_have_rejection_reason(
        self, filter_version: FilterVersion, timestamp: datetime
    ) -> None:
        """ACCEPTED log cannot have rejection_reason."""
        with pytest.raises(ValueError, match="ACCEPTED log cannot have rejection_reason"):
            FilterDecisionLog(
                decision_id=uuid4(),
                decision=FilterDecision.ACCEPTED,
                input_hash="blake3:abc123",
                output_hash="blake3:def456",
                filter_version=filter_version,
                message_type=MessageType.TASK_ACTIVATION,
                earl_id=uuid4(),
                timestamp=timestamp,
                rejection_reason=RejectionReason.URGENCY_PRESSURE,  # Invalid
            )

    def test_accepted_cannot_have_violation_type(
        self, filter_version: FilterVersion, timestamp: datetime
    ) -> None:
        """ACCEPTED log cannot have violation_type."""
        with pytest.raises(ValueError, match="ACCEPTED log cannot have violation_type"):
            FilterDecisionLog(
                decision_id=uuid4(),
                decision=FilterDecision.ACCEPTED,
                input_hash="blake3:abc123",
                output_hash="blake3:def456",
                filter_version=filter_version,
                message_type=MessageType.TASK_ACTIVATION,
                earl_id=uuid4(),
                timestamp=timestamp,
                violation_type=ViolationType.EXPLICIT_THREAT,  # Invalid
            )


class TestFilterDecisionLogRejected:
    """Tests for REJECTED decision logs."""

    @pytest.fixture
    def filter_version(self) -> FilterVersion:
        return FilterVersion(major=1, minor=0, patch=0, rules_hash="test_hash")

    @pytest.fixture
    def timestamp(self) -> datetime:
        return datetime(2026, 1, 17, 12, 0, 0, tzinfo=timezone.utc)

    def test_rejected_log_created(
        self, filter_version: FilterVersion, timestamp: datetime
    ) -> None:
        """REJECTED log can be created with valid data."""
        log = FilterDecisionLog.for_rejected(
            decision_id=uuid4(),
            input_hash="blake3:abc123def456abc123def456abc123def456abc123def456abc123def456ab12",
            filter_version=filter_version,
            message_type=MessageType.TASK_ACTIVATION,
            earl_id=uuid4(),
            timestamp=timestamp,
            rejection_reason=RejectionReason.URGENCY_PRESSURE,
            rejection_guidance="Remove urgency language.",
        )

        assert log.decision == FilterDecision.REJECTED
        assert log.rejection_reason == RejectionReason.URGENCY_PRESSURE
        assert log.output_hash is None

    def test_rejected_requires_rejection_reason(
        self, filter_version: FilterVersion, timestamp: datetime
    ) -> None:
        """REJECTED log requires rejection_reason."""
        with pytest.raises(ValueError, match="REJECTED log must include rejection_reason"):
            FilterDecisionLog(
                decision_id=uuid4(),
                decision=FilterDecision.REJECTED,
                input_hash="blake3:abc123",
                output_hash=None,
                filter_version=filter_version,
                message_type=MessageType.TASK_ACTIVATION,
                earl_id=uuid4(),
                timestamp=timestamp,
                rejection_reason=None,  # Missing
            )

    def test_rejected_cannot_have_output_hash(
        self, filter_version: FilterVersion, timestamp: datetime
    ) -> None:
        """REJECTED log cannot have output_hash."""
        with pytest.raises(ValueError, match="REJECTED log cannot include output_hash"):
            FilterDecisionLog(
                decision_id=uuid4(),
                decision=FilterDecision.REJECTED,
                input_hash="blake3:abc123",
                output_hash="blake3:def456",  # Invalid
                filter_version=filter_version,
                message_type=MessageType.TASK_ACTIVATION,
                earl_id=uuid4(),
                timestamp=timestamp,
                rejection_reason=RejectionReason.URGENCY_PRESSURE,
            )

    def test_rejected_cannot_have_transformations(
        self, filter_version: FilterVersion, timestamp: datetime
    ) -> None:
        """REJECTED log cannot have transformations."""
        transformations = (
            TransformationLog(
                rule_id="urgency-1",
                pattern=r"URGENT",
                original_hash="blake3:abc123",
                replacement_hash="blake3:def456",
            ),
        )

        with pytest.raises(ValueError, match="REJECTED log cannot have transformations"):
            FilterDecisionLog(
                decision_id=uuid4(),
                decision=FilterDecision.REJECTED,
                input_hash="blake3:abc123",
                output_hash=None,
                filter_version=filter_version,
                message_type=MessageType.TASK_ACTIVATION,
                earl_id=uuid4(),
                timestamp=timestamp,
                rejection_reason=RejectionReason.URGENCY_PRESSURE,
                transformations=transformations,  # Invalid
            )


class TestFilterDecisionLogBlocked:
    """Tests for BLOCKED decision logs."""

    @pytest.fixture
    def filter_version(self) -> FilterVersion:
        return FilterVersion(major=1, minor=0, patch=0, rules_hash="test_hash")

    @pytest.fixture
    def timestamp(self) -> datetime:
        return datetime(2026, 1, 17, 12, 0, 0, tzinfo=timezone.utc)

    def test_blocked_log_created(
        self, filter_version: FilterVersion, timestamp: datetime
    ) -> None:
        """BLOCKED log can be created with valid data."""
        log = FilterDecisionLog.for_blocked(
            decision_id=uuid4(),
            input_hash="blake3:abc123def456abc123def456abc123def456abc123def456abc123def456ab12",
            filter_version=filter_version,
            message_type=MessageType.TASK_ACTIVATION,
            earl_id=uuid4(),
            timestamp=timestamp,
            violation_type=ViolationType.EXPLICIT_THREAT,
            violation_details="Content contained explicit threat.",
        )

        assert log.decision == FilterDecision.BLOCKED
        assert log.violation_type == ViolationType.EXPLICIT_THREAT
        assert log.output_hash is None

    def test_blocked_requires_violation_type(
        self, filter_version: FilterVersion, timestamp: datetime
    ) -> None:
        """BLOCKED log requires violation_type."""
        with pytest.raises(ValueError, match="BLOCKED log must include violation_type"):
            FilterDecisionLog(
                decision_id=uuid4(),
                decision=FilterDecision.BLOCKED,
                input_hash="blake3:abc123",
                output_hash=None,
                filter_version=filter_version,
                message_type=MessageType.TASK_ACTIVATION,
                earl_id=uuid4(),
                timestamp=timestamp,
                violation_type=None,  # Missing
            )

    def test_blocked_cannot_have_output_hash(
        self, filter_version: FilterVersion, timestamp: datetime
    ) -> None:
        """BLOCKED log cannot have output_hash."""
        with pytest.raises(ValueError, match="BLOCKED log cannot include output_hash"):
            FilterDecisionLog(
                decision_id=uuid4(),
                decision=FilterDecision.BLOCKED,
                input_hash="blake3:abc123",
                output_hash="blake3:def456",  # Invalid
                filter_version=filter_version,
                message_type=MessageType.TASK_ACTIVATION,
                earl_id=uuid4(),
                timestamp=timestamp,
                violation_type=ViolationType.EXPLICIT_THREAT,
            )

    def test_blocked_cannot_have_transformations(
        self, filter_version: FilterVersion, timestamp: datetime
    ) -> None:
        """BLOCKED log cannot have transformations."""
        transformations = (
            TransformationLog(
                rule_id="urgency-1",
                pattern=r"URGENT",
                original_hash="blake3:abc123",
                replacement_hash="blake3:def456",
            ),
        )

        with pytest.raises(ValueError, match="BLOCKED log cannot have transformations"):
            FilterDecisionLog(
                decision_id=uuid4(),
                decision=FilterDecision.BLOCKED,
                input_hash="blake3:abc123",
                output_hash=None,
                filter_version=filter_version,
                message_type=MessageType.TASK_ACTIVATION,
                earl_id=uuid4(),
                timestamp=timestamp,
                violation_type=ViolationType.EXPLICIT_THREAT,
                transformations=transformations,  # Invalid
            )


class TestInputHashValidation:
    """Tests for input hash validation."""

    @pytest.fixture
    def filter_version(self) -> FilterVersion:
        return FilterVersion(major=1, minor=0, patch=0, rules_hash="test_hash")

    @pytest.fixture
    def timestamp(self) -> datetime:
        return datetime(2026, 1, 17, 12, 0, 0, tzinfo=timezone.utc)

    def test_input_hash_required(
        self, filter_version: FilterVersion, timestamp: datetime
    ) -> None:
        """input_hash is required."""
        with pytest.raises(ValueError, match="input_hash is required"):
            FilterDecisionLog(
                decision_id=uuid4(),
                decision=FilterDecision.ACCEPTED,
                input_hash="",  # Empty
                output_hash="blake3:def456",
                filter_version=filter_version,
                message_type=MessageType.TASK_ACTIVATION,
                earl_id=uuid4(),
                timestamp=timestamp,
            )

    def test_input_hash_must_have_algorithm_prefix(
        self, filter_version: FilterVersion, timestamp: datetime
    ) -> None:
        """input_hash must be prefixed with algorithm."""
        with pytest.raises(ValueError, match="input_hash must be prefixed with algorithm"):
            FilterDecisionLog(
                decision_id=uuid4(),
                decision=FilterDecision.ACCEPTED,
                input_hash="abc123def456",  # No prefix
                output_hash="blake3:def456",
                filter_version=filter_version,
                message_type=MessageType.TASK_ACTIVATION,
                earl_id=uuid4(),
                timestamp=timestamp,
            )

    def test_blake3_prefix_accepted(
        self, filter_version: FilterVersion, timestamp: datetime
    ) -> None:
        """blake3: prefix is accepted."""
        log = FilterDecisionLog.for_accepted(
            decision_id=uuid4(),
            input_hash="blake3:abc123",
            output_hash="blake3:def456",
            filter_version=filter_version,
            message_type=MessageType.TASK_ACTIVATION,
            earl_id=uuid4(),
            timestamp=timestamp,
        )

        assert log.input_hash.startswith("blake3:")

    def test_sha256_prefix_accepted(
        self, filter_version: FilterVersion, timestamp: datetime
    ) -> None:
        """sha256: prefix is accepted."""
        log = FilterDecisionLog.for_accepted(
            decision_id=uuid4(),
            input_hash="sha256:abc123",
            output_hash="sha256:def456",
            filter_version=filter_version,
            message_type=MessageType.TASK_ACTIVATION,
            earl_id=uuid4(),
            timestamp=timestamp,
        )

        assert log.input_hash.startswith("sha256:")


class TestEventPayloadConversion:
    """Tests for to_event_payload conversion."""

    @pytest.fixture
    def filter_version(self) -> FilterVersion:
        return FilterVersion(major=1, minor=0, patch=0, rules_hash="test_hash")

    @pytest.fixture
    def timestamp(self) -> datetime:
        return datetime(2026, 1, 17, 12, 0, 0, tzinfo=timezone.utc)

    def test_accepted_payload_includes_transformations(
        self, filter_version: FilterVersion, timestamp: datetime
    ) -> None:
        """ACCEPTED payload includes transformations."""
        transformations = (
            TransformationLog(
                rule_id="urgency-1",
                pattern=r"URGENT",
                original_hash="blake3:abc123",
                replacement_hash="blake3:def456",
            ),
        )

        log = FilterDecisionLog.for_accepted(
            decision_id=uuid4(),
            input_hash="blake3:input123",
            output_hash="blake3:output456",
            filter_version=filter_version,
            message_type=MessageType.TASK_ACTIVATION,
            earl_id=uuid4(),
            timestamp=timestamp,
            transformations=transformations,
        )

        payload = log.to_event_payload()

        assert payload["decision"] == "accepted"
        assert "transformations" in payload
        assert len(payload["transformations"]) == 1
        assert payload["transformations"][0]["rule_id"] == "urgency-1"

    def test_rejected_payload_includes_reason(
        self, filter_version: FilterVersion, timestamp: datetime
    ) -> None:
        """REJECTED payload includes rejection reason."""
        log = FilterDecisionLog.for_rejected(
            decision_id=uuid4(),
            input_hash="blake3:input123",
            filter_version=filter_version,
            message_type=MessageType.TASK_ACTIVATION,
            earl_id=uuid4(),
            timestamp=timestamp,
            rejection_reason=RejectionReason.URGENCY_PRESSURE,
            rejection_guidance="Remove urgency.",
        )

        payload = log.to_event_payload()

        assert payload["decision"] == "rejected"
        assert payload["rejection_reason"] is not None
        assert payload["rejection_guidance"] == "Remove urgency."

    def test_blocked_payload_includes_violation(
        self, filter_version: FilterVersion, timestamp: datetime
    ) -> None:
        """BLOCKED payload includes violation details."""
        log = FilterDecisionLog.for_blocked(
            decision_id=uuid4(),
            input_hash="blake3:input123",
            filter_version=filter_version,
            message_type=MessageType.TASK_ACTIVATION,
            earl_id=uuid4(),
            timestamp=timestamp,
            violation_type=ViolationType.EXPLICIT_THREAT,
            violation_details="Threat detected.",
        )

        payload = log.to_event_payload()

        assert payload["decision"] == "blocked"
        assert payload["violation_type"] is not None
        assert payload["violation_details"] == "Threat detected."

    def test_payload_never_contains_raw_content(
        self, filter_version: FilterVersion, timestamp: datetime
    ) -> None:
        """Event payload only contains hashes, never raw content."""
        log = FilterDecisionLog.for_accepted(
            decision_id=uuid4(),
            input_hash="blake3:abc123",
            output_hash="blake3:def456",
            filter_version=filter_version,
            message_type=MessageType.TASK_ACTIVATION,
            earl_id=uuid4(),
            timestamp=timestamp,
        )

        payload = log.to_event_payload()

        # Verify only hashes are present, not any raw content fields
        assert "input_hash" in payload
        assert "output_hash" in payload
        assert "raw_content" not in payload
        assert "content" not in payload


class TestImmutability:
    """Tests for immutability of FilterDecisionLog."""

    @pytest.fixture
    def filter_version(self) -> FilterVersion:
        return FilterVersion(major=1, minor=0, patch=0, rules_hash="test_hash")

    @pytest.fixture
    def timestamp(self) -> datetime:
        return datetime(2026, 1, 17, 12, 0, 0, tzinfo=timezone.utc)

    def test_log_is_frozen(
        self, filter_version: FilterVersion, timestamp: datetime
    ) -> None:
        """FilterDecisionLog is immutable (frozen dataclass)."""
        log = FilterDecisionLog.for_accepted(
            decision_id=uuid4(),
            input_hash="blake3:abc123",
            output_hash="blake3:def456",
            filter_version=filter_version,
            message_type=MessageType.TASK_ACTIVATION,
            earl_id=uuid4(),
            timestamp=timestamp,
        )

        with pytest.raises(AttributeError):
            log.decision = FilterDecision.REJECTED  # type: ignore
