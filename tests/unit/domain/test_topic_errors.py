"""Unit tests for Topic error classes (FR15, FR71-73).

Tests error classes for topic diversity violations and rate limiting.
"""


from src.domain.errors.constitutional import ConstitutionalViolationError
from src.domain.errors.topic import (
    TopicDiversityViolationError,
    TopicRateLimitError,
)
from src.domain.exceptions import ConclaveError
from src.domain.models.topic_origin import TopicOriginType


class TestTopicDiversityViolationError:
    """Tests for TopicDiversityViolationError."""

    def test_inherits_from_constitutional_violation(self) -> None:
        """TopicDiversityViolationError is a ConstitutionalViolationError."""
        error = TopicDiversityViolationError(
            origin_type=TopicOriginType.AUTONOMOUS,
            current_percentage=0.35,
        )
        assert isinstance(error, ConstitutionalViolationError)
        assert isinstance(error, ConclaveError)

    def test_error_contains_fr_reference(self) -> None:
        """Error message includes FR73 reference."""
        error = TopicDiversityViolationError(
            origin_type=TopicOriginType.AUTONOMOUS,
            current_percentage=0.35,
        )
        assert "FR73" in str(error)

    def test_error_includes_origin_type_and_percentage(self) -> None:
        """Error message includes origin type and percentage."""
        error = TopicDiversityViolationError(
            origin_type=TopicOriginType.PETITION,
            current_percentage=0.45,
            threshold=0.30,
        )
        error_msg = str(error)
        assert "PETITION" in error_msg or "petition" in error_msg.lower()
        assert "45" in error_msg  # 45%
        assert "30" in error_msg  # 30% threshold

    def test_attributes_accessible(self) -> None:
        """Error attributes are accessible."""
        error = TopicDiversityViolationError(
            origin_type=TopicOriginType.SCHEDULED,
            current_percentage=0.40,
            threshold=0.25,
        )
        assert error.origin_type == TopicOriginType.SCHEDULED
        assert error.current_percentage == 0.40
        assert error.threshold == 0.25


class TestTopicRateLimitError:
    """Tests for TopicRateLimitError."""

    def test_inherits_from_conclave_error(self) -> None:
        """TopicRateLimitError is a ConclaveError."""
        error = TopicRateLimitError(
            source_id="archon-42",
            topics_per_hour=15,
        )
        assert isinstance(error, ConclaveError)
        # Note: Rate limiting is NOT a constitutional violation, just an operational limit
        assert not isinstance(error, ConstitutionalViolationError)

    def test_error_contains_fr_reference(self) -> None:
        """Error message includes FR71 reference."""
        error = TopicRateLimitError(
            source_id="archon-42",
            topics_per_hour=15,
        )
        assert "FR71" in str(error)

    def test_error_includes_source_and_count(self) -> None:
        """Error message includes source ID and topics per hour."""
        error = TopicRateLimitError(
            source_id="petition-system",
            topics_per_hour=12,
            limit=10,
        )
        error_msg = str(error)
        assert "petition-system" in error_msg
        assert "12" in error_msg
        assert "10" in error_msg

    def test_attributes_accessible(self) -> None:
        """Error attributes are accessible."""
        error = TopicRateLimitError(
            source_id="scheduler",
            topics_per_hour=20,
            limit=10,
        )
        assert error.source_id == "scheduler"
        assert error.topics_per_hour == 20
        assert error.limit == 10

    def test_default_limit_is_ten(self) -> None:
        """Default rate limit is 10 per hour."""
        error = TopicRateLimitError(
            source_id="test",
            topics_per_hour=11,
        )
        assert error.limit == 10
