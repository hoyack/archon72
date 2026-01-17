"""Unit tests for FilterResult value object.

Tests AC1: Filter outcomes defined.
Tests AC4: Filter version tracked.
Tests AC5: Content transformation rules.
Tests AC6: Rejection reasons.
Tests AC7: Violation types.
Tests AC8: Immutable value objects.
"""

import pytest
from datetime import datetime
from dataclasses import FrozenInstanceError

from src.domain.governance.filter.filter_decision import FilterDecision
from src.domain.governance.filter.filter_result import FilterResult
from src.domain.governance.filter.filter_version import FilterVersion
from src.domain.governance.filter.filtered_content import FilteredContent
from src.domain.governance.filter.rejection_reason import RejectionReason
from src.domain.governance.filter.violation_type import ViolationType
from src.domain.governance.filter.transformation import Transformation


class TestFilterResult:
    """Unit tests for FilterResult value object."""

    @pytest.fixture
    def filter_version(self) -> FilterVersion:
        """Create a test filter version."""
        return FilterVersion(
            major=1,
            minor=0,
            patch=0,
            rules_hash="abc123def456",
        )

    @pytest.fixture
    def filtered_content(self, filter_version: FilterVersion) -> FilteredContent:
        """Create test filtered content."""
        return FilteredContent._create(
            content="Hello, participant",
            original_content="HELLO! participant",
            filter_version=filter_version,
            filtered_at=datetime.now(),
        )

    def test_accepted_result_is_sendable(
        self, filtered_content: FilteredContent, filter_version: FilterVersion
    ) -> None:
        """ACCEPTED results are sendable."""
        result = FilterResult.accepted(
            content=filtered_content,
            version=filter_version,
            timestamp=datetime.now(),
        )

        assert result.is_sendable()
        assert result.decision == FilterDecision.ACCEPTED

    def test_rejected_result_not_sendable(
        self, filter_version: FilterVersion
    ) -> None:
        """REJECTED results are not sendable."""
        result = FilterResult.rejected(
            reason=RejectionReason.URGENCY_PRESSURE,
            version=filter_version,
            timestamp=datetime.now(),
        )

        assert not result.is_sendable()
        assert result.decision == FilterDecision.REJECTED

    def test_blocked_result_not_sendable(
        self, filter_version: FilterVersion
    ) -> None:
        """BLOCKED results are not sendable."""
        result = FilterResult.blocked(
            violation=ViolationType.EXPLICIT_THREAT,
            version=filter_version,
            timestamp=datetime.now(),
        )

        assert not result.is_sendable()
        assert result.decision == FilterDecision.BLOCKED

    def test_accepted_result_has_content(
        self, filtered_content: FilteredContent, filter_version: FilterVersion
    ) -> None:
        """ACCEPTED results include content."""
        result = FilterResult.accepted(
            content=filtered_content,
            version=filter_version,
            timestamp=datetime.now(),
        )

        assert result.content is not None
        assert result.content.content == "Hello, participant"

    def test_accepted_result_tracks_transformations(
        self, filtered_content: FilteredContent, filter_version: FilterVersion
    ) -> None:
        """ACCEPTED results include transformation details (AC5)."""
        transformations = (
            Transformation(
                pattern_matched="URGENT",
                original_text="HELLO!",
                replacement_text="Hello,",
                rule_id="remove_urgency_caps",
            ),
        )

        result = FilterResult.accepted(
            content=filtered_content,
            version=filter_version,
            timestamp=datetime.now(),
            transformations=transformations,
        )

        assert result.was_transformed
        assert result.transformation_count == 1
        assert result.transformations[0].rule_id == "remove_urgency_caps"

    def test_rejected_result_has_reason(
        self, filter_version: FilterVersion
    ) -> None:
        """REJECTED results include reason and guidance (AC6)."""
        result = FilterResult.rejected(
            reason=RejectionReason.URGENCY_PRESSURE,
            version=filter_version,
            timestamp=datetime.now(),
        )

        assert result.rejection_reason == RejectionReason.URGENCY_PRESSURE
        assert result.rejection_guidance is not None
        assert "time pressure" in result.rejection_guidance.lower()

    def test_blocked_result_has_violation(
        self, filter_version: FilterVersion
    ) -> None:
        """BLOCKED results include violation details (AC7)."""
        result = FilterResult.blocked(
            violation=ViolationType.EXPLICIT_THREAT,
            version=filter_version,
            timestamp=datetime.now(),
            details="Content contained explicit threat to participant",
        )

        assert result.violation_type == ViolationType.EXPLICIT_THREAT
        assert result.violation_details is not None

    def test_filter_result_immutable(
        self, filtered_content: FilteredContent, filter_version: FilterVersion
    ) -> None:
        """FilterResult is immutable (AC8)."""
        result = FilterResult.accepted(
            content=filtered_content,
            version=filter_version,
            timestamp=datetime.now(),
        )

        with pytest.raises(FrozenInstanceError):
            result.decision = FilterDecision.BLOCKED  # type: ignore

    def test_accepted_without_content_raises(
        self, filter_version: FilterVersion
    ) -> None:
        """ACCEPTED result without content raises ValueError."""
        with pytest.raises(ValueError, match="ACCEPTED result must include content"):
            FilterResult(
                decision=FilterDecision.ACCEPTED,
                version=filter_version,
                timestamp=datetime.now(),
                content=None,
            )

    def test_rejected_without_reason_raises(
        self, filter_version: FilterVersion
    ) -> None:
        """REJECTED result without reason raises ValueError."""
        with pytest.raises(ValueError, match="REJECTED result must include rejection_reason"):
            FilterResult(
                decision=FilterDecision.REJECTED,
                version=filter_version,
                timestamp=datetime.now(),
            )

    def test_blocked_without_violation_raises(
        self, filter_version: FilterVersion
    ) -> None:
        """BLOCKED result without violation raises ValueError."""
        with pytest.raises(ValueError, match="BLOCKED result must include violation_type"):
            FilterResult(
                decision=FilterDecision.BLOCKED,
                version=filter_version,
                timestamp=datetime.now(),
            )

    def test_accepted_with_rejection_reason_raises(
        self, filtered_content: FilteredContent, filter_version: FilterVersion
    ) -> None:
        """ACCEPTED result with rejection_reason raises ValueError."""
        with pytest.raises(ValueError, match="ACCEPTED result cannot have rejection_reason"):
            FilterResult(
                decision=FilterDecision.ACCEPTED,
                version=filter_version,
                timestamp=datetime.now(),
                content=filtered_content,
                rejection_reason=RejectionReason.URGENCY_PRESSURE,
            )

    def test_accepted_with_violation_type_raises(
        self, filtered_content: FilteredContent, filter_version: FilterVersion
    ) -> None:
        """ACCEPTED result with violation_type raises ValueError."""
        with pytest.raises(ValueError, match="ACCEPTED result cannot have violation_type"):
            FilterResult(
                decision=FilterDecision.ACCEPTED,
                version=filter_version,
                timestamp=datetime.now(),
                content=filtered_content,
                violation_type=ViolationType.DECEPTION,
            )

    def test_filter_result_tracks_version(
        self, filtered_content: FilteredContent, filter_version: FilterVersion
    ) -> None:
        """FilterResult tracks filter version (AC4)."""
        result = FilterResult.accepted(
            content=filtered_content,
            version=filter_version,
            timestamp=datetime.now(),
        )

        assert result.version == filter_version
        assert str(result.version) == "1.0.0"

    def test_filter_result_tracks_timestamp(
        self, filtered_content: FilteredContent, filter_version: FilterVersion
    ) -> None:
        """FilterResult tracks timestamp."""
        now = datetime.now()
        result = FilterResult.accepted(
            content=filtered_content,
            version=filter_version,
            timestamp=now,
        )

        assert result.timestamp == now
