"""Unit tests for topic manipulation domain errors (Story 6.9, FR118, FR124).

Tests for TopicManipulationDefenseError, DailyRateLimitExceededError,
PredictableSeedError, and SeedSourceDependenceError.

Constitutional Constraints:
- FR118: External topic rate limiting
- FR124: Seed independence verification
"""

import pytest

from src.domain.errors.topic_manipulation import (
    DailyRateLimitExceededError,
    PredictableSeedError,
    SeedSourceDependenceError,
    TopicManipulationDefenseError,
)
from src.domain.exceptions import ConclaveError
from src.domain.errors.constitutional import ConstitutionalViolationError


class TestTopicManipulationDefenseError:
    """Tests for TopicManipulationDefenseError base class."""

    def test_inherits_from_conclave_error(self) -> None:
        """Test TopicManipulationDefenseError inherits from ConclaveError."""
        error = TopicManipulationDefenseError("Test error")
        assert isinstance(error, ConclaveError)

    def test_message_preserved(self) -> None:
        """Test error message is preserved."""
        error = TopicManipulationDefenseError("Defense triggered")
        assert str(error) == "Defense triggered"

    def test_is_not_constitutional_violation(self) -> None:
        """Test base error is NOT a constitutional violation."""
        error = TopicManipulationDefenseError("Test")
        assert not isinstance(error, ConstitutionalViolationError)


class TestDailyRateLimitExceededError:
    """Tests for DailyRateLimitExceededError (FR118)."""

    def test_inherits_from_topic_manipulation_defense_error(self) -> None:
        """Test DailyRateLimitExceededError inherits from base class."""
        error = DailyRateLimitExceededError(
            source_id="src-123",
            topics_today=11,
            daily_limit=10,
        )
        assert isinstance(error, TopicManipulationDefenseError)

    def test_message_includes_fr118(self) -> None:
        """Test error message includes FR118 reference."""
        error = DailyRateLimitExceededError(
            source_id="external-api",
            topics_today=12,
            daily_limit=10,
        )
        assert "FR118" in str(error)

    def test_message_includes_source_id(self) -> None:
        """Test error message includes source_id."""
        error = DailyRateLimitExceededError(
            source_id="petition-portal",
            topics_today=15,
            daily_limit=10,
        )
        assert "petition-portal" in str(error)

    def test_message_includes_counts(self) -> None:
        """Test error message includes topic counts."""
        error = DailyRateLimitExceededError(
            source_id="src-123",
            topics_today=11,
            daily_limit=10,
        )
        message = str(error)
        assert "11" in message
        assert "10" in message

    def test_attributes_accessible(self) -> None:
        """Test error attributes are accessible."""
        error = DailyRateLimitExceededError(
            source_id="test-source",
            topics_today=13,
            daily_limit=10,
        )
        assert error.source_id == "test-source"
        assert error.topics_today == 13
        assert error.daily_limit == 10


class TestPredictableSeedError:
    """Tests for PredictableSeedError (FR124)."""

    def test_inherits_from_constitutional_violation_error(self) -> None:
        """Test PredictableSeedError is a constitutional violation."""
        error = PredictableSeedError(
            seed_purpose="witness_selection",
            predictability_reason="Sequential pattern detected",
        )
        assert isinstance(error, ConstitutionalViolationError)

    def test_message_includes_fr124(self) -> None:
        """Test error message includes FR124 reference."""
        error = PredictableSeedError(
            seed_purpose="lottery",
            predictability_reason="Repeating bytes",
        )
        assert "FR124" in str(error)

    def test_message_includes_purpose(self) -> None:
        """Test error message includes seed purpose."""
        error = PredictableSeedError(
            seed_purpose="witness_selection",
            predictability_reason="All zeros",
        )
        assert "witness_selection" in str(error)

    def test_message_includes_reason(self) -> None:
        """Test error message includes predictability reason."""
        error = PredictableSeedError(
            seed_purpose="test",
            predictability_reason="Correlated with system time",
        )
        assert "Correlated with system time" in str(error)

    def test_attributes_accessible(self) -> None:
        """Test error attributes are accessible."""
        error = PredictableSeedError(
            seed_purpose="deliberation_random",
            predictability_reason="Low entropy",
        )
        assert error.seed_purpose == "deliberation_random"
        assert error.predictability_reason == "Low entropy"


class TestSeedSourceDependenceError:
    """Tests for SeedSourceDependenceError (FR124)."""

    def test_inherits_from_constitutional_violation_error(self) -> None:
        """Test SeedSourceDependenceError is a constitutional violation."""
        error = SeedSourceDependenceError(
            seed_purpose="witness_selection",
            failed_source="internal-prng",
        )
        assert isinstance(error, ConstitutionalViolationError)

    def test_message_includes_fr124(self) -> None:
        """Test error message includes FR124 reference."""
        error = SeedSourceDependenceError(
            seed_purpose="test",
            failed_source="compromised-source",
        )
        assert "FR124" in str(error)

    def test_message_includes_purpose(self) -> None:
        """Test error message includes seed purpose."""
        error = SeedSourceDependenceError(
            seed_purpose="witness_selection",
            failed_source="test-source",
        )
        assert "witness_selection" in str(error)

    def test_message_indicates_independence_failure(self) -> None:
        """Test error message indicates independence verification failed."""
        error = SeedSourceDependenceError(
            seed_purpose="test",
            failed_source="dependent-source",
        )
        message = str(error).lower()
        assert "independence" in message or "verification failed" in message

    def test_attributes_accessible(self) -> None:
        """Test error attributes are accessible."""
        error = SeedSourceDependenceError(
            seed_purpose="randomizer",
            failed_source="untrusted-api",
        )
        assert error.seed_purpose == "randomizer"
        assert error.failed_source == "untrusted-api"
