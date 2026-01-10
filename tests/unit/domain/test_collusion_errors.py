"""Unit tests for collusion defense domain errors (Story 6.8, FR124).

Tests CollusionDefenseError and related exceptions.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.domain.errors.collusion import (
    CollusionDefenseError,
    CollusionInvestigationRequiredError,
    InvestigationAlreadyResolvedError,
    InvestigationNotFoundError,
    WitnessPairPermanentlyBannedError,
    WitnessPairSuspendedError,
)
from src.domain.errors.constitutional import ConstitutionalViolationError


class TestCollusionDefenseError:
    """Tests for CollusionDefenseError base class."""

    def test_inheritance(self) -> None:
        """Test that CollusionDefenseError inherits from ConstitutionalViolationError."""
        error = CollusionDefenseError("Test error")
        assert isinstance(error, ConstitutionalViolationError)

    def test_message(self) -> None:
        """Test error message."""
        error = CollusionDefenseError("Test error message")
        assert str(error) == "Test error message"


class TestCollusionInvestigationRequiredError:
    """Tests for CollusionInvestigationRequiredError."""

    def test_attributes(self) -> None:
        """Test error attributes."""
        error = CollusionInvestigationRequiredError(
            pair_key="witness_a:witness_b",
            correlation_score=0.85,
        )

        assert error.pair_key == "witness_a:witness_b"
        assert error.correlation_score == 0.85

    def test_message_format(self) -> None:
        """Test error message format includes FR124."""
        error = CollusionInvestigationRequiredError(
            pair_key="witness_a:witness_b",
            correlation_score=0.85,
        )

        assert "FR124" in str(error)
        assert "witness_a:witness_b" in str(error)
        assert "0.85" in str(error)

    def test_inheritance(self) -> None:
        """Test inheritance from CollusionDefenseError."""
        error = CollusionInvestigationRequiredError(
            pair_key="witness_a:witness_b",
            correlation_score=0.85,
        )
        assert isinstance(error, CollusionDefenseError)


class TestWitnessPairSuspendedError:
    """Tests for WitnessPairSuspendedError."""

    def test_attributes(self) -> None:
        """Test error attributes."""
        error = WitnessPairSuspendedError(
            pair_key="witness_a:witness_b",
            investigation_id="inv-123",
        )

        assert error.pair_key == "witness_a:witness_b"
        assert error.investigation_id == "inv-123"

    def test_message_format(self) -> None:
        """Test error message format includes FR124."""
        error = WitnessPairSuspendedError(
            pair_key="witness_a:witness_b",
            investigation_id="inv-123",
        )

        assert "FR124" in str(error)
        assert "witness_a:witness_b" in str(error)
        assert "inv-123" in str(error)


class TestInvestigationNotFoundError:
    """Tests for InvestigationNotFoundError."""

    def test_attributes(self) -> None:
        """Test error attributes."""
        error = InvestigationNotFoundError(investigation_id="inv-123")
        assert error.investigation_id == "inv-123"

    def test_message_format(self) -> None:
        """Test error message format."""
        error = InvestigationNotFoundError(investigation_id="inv-123")
        assert "inv-123" in str(error)
        assert "not found" in str(error)


class TestInvestigationAlreadyResolvedError:
    """Tests for InvestigationAlreadyResolvedError."""

    def test_attributes_with_timestamp(self) -> None:
        """Test error attributes with resolved_at timestamp."""
        now = datetime.now(timezone.utc)
        error = InvestigationAlreadyResolvedError(
            investigation_id="inv-123",
            resolved_at=now,
        )

        assert error.investigation_id == "inv-123"
        assert error.resolved_at == now

    def test_attributes_without_timestamp(self) -> None:
        """Test error attributes without resolved_at timestamp."""
        error = InvestigationAlreadyResolvedError(
            investigation_id="inv-123",
        )

        assert error.investigation_id == "inv-123"
        assert error.resolved_at is None

    def test_message_format(self) -> None:
        """Test error message format."""
        error = InvestigationAlreadyResolvedError(investigation_id="inv-123")
        assert "inv-123" in str(error)
        assert "already resolved" in str(error)


class TestWitnessPairPermanentlyBannedError:
    """Tests for WitnessPairPermanentlyBannedError."""

    def test_attributes(self) -> None:
        """Test error attributes."""
        error = WitnessPairPermanentlyBannedError(
            pair_key="witness_a:witness_b",
            investigation_id="inv-123",
        )

        assert error.pair_key == "witness_a:witness_b"
        assert error.investigation_id == "inv-123"

    def test_message_format(self) -> None:
        """Test error message format includes FR124."""
        error = WitnessPairPermanentlyBannedError(
            pair_key="witness_a:witness_b",
            investigation_id="inv-123",
        )

        assert "FR124" in str(error)
        assert "permanently banned" in str(error)
        assert "witness_a:witness_b" in str(error)
        assert "inv-123" in str(error)
