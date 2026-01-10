"""Unit tests for override abuse validator port (Story 5.9, FR86-FR87).

Tests the OverrideAbuseValidatorProtocol interface and ValidationResult dataclass.
"""

from __future__ import annotations

import pytest

from src.application.ports.override_abuse_validator import (
    OverrideAbuseValidatorProtocol,
    ValidationResult,
)
from src.domain.events.override_abuse import ViolationType
from src.infrastructure.stubs.override_abuse_validator_stub import (
    OverrideAbuseValidatorStub,
)


class TestValidationResult:
    """Tests for ValidationResult dataclass."""

    def test_success_creates_valid_result(self) -> None:
        """Test success() factory creates valid result."""
        result = ValidationResult.success()
        assert result.is_valid is True
        assert result.violation_type is None
        assert result.violation_details is None

    def test_failure_creates_invalid_result(self) -> None:
        """Test failure() factory creates invalid result."""
        result = ValidationResult.failure(
            violation_type=ViolationType.HISTORY_EDIT,
            violation_details="History edit attempt detected",
        )
        assert result.is_valid is False
        assert result.violation_type == ViolationType.HISTORY_EDIT
        assert result.violation_details == "History edit attempt detected"

    def test_direct_construction_valid(self) -> None:
        """Test direct construction for valid result."""
        result = ValidationResult(is_valid=True)
        assert result.is_valid is True

    def test_direct_construction_invalid(self) -> None:
        """Test direct construction for invalid result."""
        result = ValidationResult(
            is_valid=False,
            violation_type=ViolationType.EVIDENCE_DESTRUCTION,
            violation_details="Evidence destruction attempt",
        )
        assert result.is_valid is False
        assert result.violation_type == ViolationType.EVIDENCE_DESTRUCTION

    def test_result_is_frozen(self) -> None:
        """Test ValidationResult is immutable."""
        result = ValidationResult.success()
        with pytest.raises(AttributeError):
            result.is_valid = False  # type: ignore[misc]


class TestOverrideAbuseValidatorProtocol:
    """Tests for OverrideAbuseValidatorProtocol using stub implementation."""

    @pytest.fixture
    def validator(self) -> OverrideAbuseValidatorStub:
        """Create a fresh validator stub for each test."""
        return OverrideAbuseValidatorStub()

    @pytest.mark.asyncio
    async def test_stub_implements_protocol(
        self,
        validator: OverrideAbuseValidatorStub,
    ) -> None:
        """Test stub implements OverrideAbuseValidatorProtocol."""
        # Check protocol compliance (duck typing)
        assert hasattr(validator, "validate_constitutional_constraints")
        assert hasattr(validator, "is_history_edit_attempt")
        assert hasattr(validator, "is_evidence_destruction_attempt")

    @pytest.mark.asyncio
    async def test_validate_valid_scope(
        self,
        validator: OverrideAbuseValidatorStub,
    ) -> None:
        """Test validation passes for valid scope."""
        result = await validator.validate_constitutional_constraints(
            override_scope="voting.extension",
            action_type="test",
        )
        assert result.is_valid is True

    @pytest.mark.asyncio
    async def test_validate_history_edit_scope(
        self,
        validator: OverrideAbuseValidatorStub,
    ) -> None:
        """Test validation fails for history edit scope (FR87)."""
        result = await validator.validate_constitutional_constraints(
            override_scope="history.delete",
            action_type="test",
        )
        assert result.is_valid is False
        assert result.violation_type == ViolationType.HISTORY_EDIT

    @pytest.mark.asyncio
    async def test_validate_evidence_destruction_scope(
        self,
        validator: OverrideAbuseValidatorStub,
    ) -> None:
        """Test validation fails for evidence destruction scope (FR87)."""
        result = await validator.validate_constitutional_constraints(
            override_scope="witness.remove",
            action_type="test",
        )
        assert result.is_valid is False
        assert result.violation_type == ViolationType.EVIDENCE_DESTRUCTION

    @pytest.mark.asyncio
    async def test_is_history_edit_attempt_true(
        self,
        validator: OverrideAbuseValidatorStub,
    ) -> None:
        """Test is_history_edit_attempt returns True for history edit."""
        assert await validator.is_history_edit_attempt("history") is True
        assert await validator.is_history_edit_attempt("event_store.delete") is True
        assert await validator.is_history_edit_attempt("event_store.modify") is True

    @pytest.mark.asyncio
    async def test_is_history_edit_attempt_false(
        self,
        validator: OverrideAbuseValidatorStub,
    ) -> None:
        """Test is_history_edit_attempt returns False for valid scope."""
        assert await validator.is_history_edit_attempt("voting.extension") is False
        assert await validator.is_history_edit_attempt("timeout.extend") is False

    @pytest.mark.asyncio
    async def test_is_evidence_destruction_attempt_true(
        self,
        validator: OverrideAbuseValidatorStub,
    ) -> None:
        """Test is_evidence_destruction_attempt returns True for evidence destruction."""
        assert await validator.is_evidence_destruction_attempt("evidence") is True
        assert await validator.is_evidence_destruction_attempt("witness.remove") is True
        assert await validator.is_evidence_destruction_attempt("signature.invalidate") is True

    @pytest.mark.asyncio
    async def test_is_evidence_destruction_attempt_false(
        self,
        validator: OverrideAbuseValidatorStub,
    ) -> None:
        """Test is_evidence_destruction_attempt returns False for valid scope."""
        assert await validator.is_evidence_destruction_attempt("voting.extension") is False
        assert await validator.is_evidence_destruction_attempt("timeout.extend") is False
