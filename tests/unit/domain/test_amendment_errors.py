"""Unit tests for amendment visibility errors (Story 6.7, FR126-FR128)."""

from datetime import datetime, timedelta, timezone
import pytest

from src.domain.errors.amendment import (
    AmendmentError,
    AmendmentHistoryProtectionError,
    AmendmentImpactAnalysisMissingError,
    AmendmentNotFoundError,
    AmendmentVisibilityIncompleteError,
)
from src.domain.errors.constitutional import ConstitutionalViolationError


class TestAmendmentError:
    """Tests for AmendmentError base class."""

    def test_inherits_from_constitutional_violation_error(self) -> None:
        """Test that AmendmentError inherits from ConstitutionalViolationError."""
        assert issubclass(AmendmentError, ConstitutionalViolationError)


class TestAmendmentVisibilityIncompleteError:
    """Tests for AmendmentVisibilityIncompleteError (FR126)."""

    def test_create_with_message(self) -> None:
        """Test error creation includes FR126 reference."""
        now = datetime.now(timezone.utc)
        votable_from = now + timedelta(days=10)

        error = AmendmentVisibilityIncompleteError(
            amendment_id="AMD-001",
            days_remaining=10,
            votable_from=votable_from,
        )

        assert error.amendment_id == "AMD-001"
        assert error.days_remaining == 10
        assert error.votable_from == votable_from
        assert "FR126" in str(error)
        assert "10 days remaining" in str(error)

    def test_inherits_from_amendment_error(self) -> None:
        """Test that error inherits from AmendmentError."""
        assert issubclass(AmendmentVisibilityIncompleteError, AmendmentError)


class TestAmendmentImpactAnalysisMissingError:
    """Tests for AmendmentImpactAnalysisMissingError (FR127)."""

    def test_create_with_affected_guarantees(self) -> None:
        """Test error creation with affected guarantees."""
        error = AmendmentImpactAnalysisMissingError(
            amendment_id="AMD-002",
            affected_guarantees=("CT-11", "FR126"),
        )

        assert error.amendment_id == "AMD-002"
        assert error.affected_guarantees == ("CT-11", "FR126")
        assert "FR127" in str(error)
        assert "impact analysis" in str(error)

    def test_create_without_affected_guarantees(self) -> None:
        """Test error creation without specific guarantees."""
        error = AmendmentImpactAnalysisMissingError(
            amendment_id="AMD-003",
        )

        assert error.amendment_id == "AMD-003"
        assert error.affected_guarantees == ()
        assert "FR127" in str(error)
        assert "core guarantees" in str(error)

    def test_inherits_from_amendment_error(self) -> None:
        """Test that error inherits from AmendmentError."""
        assert issubclass(AmendmentImpactAnalysisMissingError, AmendmentError)


class TestAmendmentHistoryProtectionError:
    """Tests for AmendmentHistoryProtectionError (FR128)."""

    def test_create_with_amendment_id(self) -> None:
        """Test error creation includes FR128 reference."""
        error = AmendmentHistoryProtectionError(
            amendment_id="AMD-004",
        )

        assert error.amendment_id == "AMD-004"
        assert "FR128" in str(error)
        assert "unreviewable" in str(error)

    def test_inherits_from_amendment_error(self) -> None:
        """Test that error inherits from AmendmentError."""
        assert issubclass(AmendmentHistoryProtectionError, AmendmentError)


class TestAmendmentNotFoundError:
    """Tests for AmendmentNotFoundError."""

    def test_create_with_amendment_id(self) -> None:
        """Test error creation with amendment ID."""
        error = AmendmentNotFoundError(
            amendment_id="AMD-005",
        )

        assert error.amendment_id == "AMD-005"
        assert "AMD-005" in str(error)
        assert "not found" in str(error)

    def test_inherits_from_amendment_error(self) -> None:
        """Test that error inherits from AmendmentError."""
        assert issubclass(AmendmentNotFoundError, AmendmentError)
