"""Unit tests for OverrideAbuseValidatorStub (Story 5.9, FR86-FR87).

Tests validate:
- AC1: FR86 - Constitutional constraint validation
- AC2: FR87 - History edit and evidence destruction rejection
- Stub behavior for test isolation
"""

from __future__ import annotations

import pytest

from src.domain.events.override_abuse import ViolationType
from src.infrastructure.stubs.override_abuse_validator_stub import (
    EVIDENCE_DESTRUCTION_PATTERNS,
    GENERAL_FORBIDDEN_SCOPES,
    HISTORY_EDIT_PATTERNS,
    OverrideAbuseValidatorStub,
)


class TestOverrideAbuseValidatorStubInitialization:
    """Tests for stub initialization."""

    def test_stub_initializes_with_default_patterns(self) -> None:
        """Stub should initialize with default forbidden patterns."""
        stub = OverrideAbuseValidatorStub()

        # Verify internal state has default patterns
        assert len(stub._history_edit_patterns) > 0
        assert len(stub._evidence_destruction_patterns) > 0
        assert len(stub._forbidden_scopes) > 0

    def test_stub_uses_defined_constant_patterns(self) -> None:
        """Stub should use the module-level constant patterns."""
        stub = OverrideAbuseValidatorStub()

        # Verify patterns match constants
        assert stub._history_edit_patterns == set(HISTORY_EDIT_PATTERNS)
        assert stub._evidence_destruction_patterns == set(EVIDENCE_DESTRUCTION_PATTERNS)
        assert stub._forbidden_scopes == set(GENERAL_FORBIDDEN_SCOPES)


class TestHistoryEditPatterns:
    """Tests for history edit pattern detection (FR87)."""

    @pytest.fixture
    def stub(self) -> OverrideAbuseValidatorStub:
        """Create fresh stub for each test."""
        return OverrideAbuseValidatorStub()

    @pytest.mark.asyncio
    async def test_detects_history_pattern_exact_match(
        self,
        stub: OverrideAbuseValidatorStub,
    ) -> None:
        """Should detect exact history pattern match."""
        result = await stub.is_history_edit_attempt("history")
        assert result is True

    @pytest.mark.asyncio
    async def test_detects_history_pattern_prefix_match(
        self,
        stub: OverrideAbuseValidatorStub,
    ) -> None:
        """Should detect history pattern prefix match."""
        result = await stub.is_history_edit_attempt("event_store.delete.event_123")
        assert result is True

    @pytest.mark.asyncio
    async def test_detects_event_store_delete(
        self,
        stub: OverrideAbuseValidatorStub,
    ) -> None:
        """Should detect event store delete as history edit."""
        result = await stub.is_history_edit_attempt("event_store.delete")
        assert result is True

    @pytest.mark.asyncio
    async def test_detects_audit_delete(
        self,
        stub: OverrideAbuseValidatorStub,
    ) -> None:
        """Should detect audit delete as history edit."""
        result = await stub.is_history_edit_attempt("audit.delete")
        assert result is True

    @pytest.mark.asyncio
    async def test_allows_safe_scope(
        self,
        stub: OverrideAbuseValidatorStub,
    ) -> None:
        """Should allow safe scopes that don't match history patterns."""
        result = await stub.is_history_edit_attempt("user.preferences")
        assert result is False

    @pytest.mark.asyncio
    async def test_case_insensitive_matching(
        self,
        stub: OverrideAbuseValidatorStub,
    ) -> None:
        """Pattern matching should be case-insensitive."""
        result = await stub.is_history_edit_attempt("HISTORY")
        assert result is True

        result = await stub.is_history_edit_attempt("Event_Store.Delete")
        assert result is True


class TestEvidenceDestructionPatterns:
    """Tests for evidence destruction pattern detection (FR87)."""

    @pytest.fixture
    def stub(self) -> OverrideAbuseValidatorStub:
        """Create fresh stub for each test."""
        return OverrideAbuseValidatorStub()

    @pytest.mark.asyncio
    async def test_detects_evidence_pattern_exact_match(
        self,
        stub: OverrideAbuseValidatorStub,
    ) -> None:
        """Should detect exact evidence pattern match."""
        result = await stub.is_evidence_destruction_attempt("evidence")
        assert result is True

    @pytest.mark.asyncio
    async def test_detects_evidence_delete(
        self,
        stub: OverrideAbuseValidatorStub,
    ) -> None:
        """Should detect evidence.delete as destruction attempt."""
        result = await stub.is_evidence_destruction_attempt("evidence.delete")
        assert result is True

    @pytest.mark.asyncio
    async def test_detects_witness_remove(
        self,
        stub: OverrideAbuseValidatorStub,
    ) -> None:
        """Should detect witness.remove as destruction attempt."""
        result = await stub.is_evidence_destruction_attempt("witness.remove")
        assert result is True

    @pytest.mark.asyncio
    async def test_detects_signature_invalidate(
        self,
        stub: OverrideAbuseValidatorStub,
    ) -> None:
        """Should detect signature.invalidate as destruction attempt."""
        result = await stub.is_evidence_destruction_attempt("signature.invalidate")
        assert result is True

    @pytest.mark.asyncio
    async def test_detects_hash_chain_modify(
        self,
        stub: OverrideAbuseValidatorStub,
    ) -> None:
        """Should detect hash_chain.modify as destruction attempt."""
        result = await stub.is_evidence_destruction_attempt("hash_chain.modify")
        assert result is True

    @pytest.mark.asyncio
    async def test_allows_safe_scope(
        self,
        stub: OverrideAbuseValidatorStub,
    ) -> None:
        """Should allow safe scopes that don't match evidence patterns."""
        result = await stub.is_evidence_destruction_attempt("config.update")
        assert result is False


class TestValidateConstitutionalConstraints:
    """Tests for full constitutional constraint validation (FR86)."""

    @pytest.fixture
    def stub(self) -> OverrideAbuseValidatorStub:
        """Create fresh stub for each test."""
        return OverrideAbuseValidatorStub()

    @pytest.mark.asyncio
    async def test_validates_safe_scope_successfully(
        self,
        stub: OverrideAbuseValidatorStub,
    ) -> None:
        """Should return success for safe scopes."""
        result = await stub.validate_constitutional_constraints(
            "user.preferences",
            "update",
        )
        assert result.is_valid is True
        assert result.violation_type is None

    @pytest.mark.asyncio
    async def test_rejects_history_edit_with_correct_violation_type(
        self,
        stub: OverrideAbuseValidatorStub,
    ) -> None:
        """Should reject history edit with HISTORY_EDIT violation type."""
        result = await stub.validate_constitutional_constraints(
            "event_store.delete",
            "execute",
        )
        assert result.is_valid is False
        assert result.violation_type == ViolationType.HISTORY_EDIT
        assert "FR87" in result.violation_details

    @pytest.mark.asyncio
    async def test_rejects_evidence_destruction_with_correct_violation_type(
        self,
        stub: OverrideAbuseValidatorStub,
    ) -> None:
        """Should reject evidence destruction with EVIDENCE_DESTRUCTION violation type."""
        result = await stub.validate_constitutional_constraints(
            "witness.remove",
            "execute",
        )
        assert result.is_valid is False
        assert result.violation_type == ViolationType.EVIDENCE_DESTRUCTION
        assert "FR87" in result.violation_details

    @pytest.mark.asyncio
    async def test_rejects_forbidden_scope_with_correct_violation_type(
        self,
        stub: OverrideAbuseValidatorStub,
    ) -> None:
        """Should reject forbidden scope with FORBIDDEN_SCOPE violation type."""
        result = await stub.validate_constitutional_constraints(
            "witness_pool",
            "disable",
        )
        assert result.is_valid is False
        assert result.violation_type == ViolationType.FORBIDDEN_SCOPE
        assert "FR86" in result.violation_details

    @pytest.mark.asyncio
    async def test_rejects_witness_suppression_scope(
        self,
        stub: OverrideAbuseValidatorStub,
    ) -> None:
        """Should reject witness suppression attempts.

        Note: witnessing is in GENERAL_FORBIDDEN_SCOPES, so it's caught
        as FORBIDDEN_SCOPE first. This test verifies the stub correctly
        rejects such scopes (the witness_suppression check is a secondary
        layer for scopes not already in forbidden list).
        """
        result = await stub.validate_constitutional_constraints(
            "witnessing.disable",
            "execute",
        )
        assert result.is_valid is False
        # witnessing is in GENERAL_FORBIDDEN_SCOPES, so caught as FORBIDDEN_SCOPE
        assert result.violation_type == ViolationType.FORBIDDEN_SCOPE
        assert "FR86" in result.violation_details


class TestStubConfigurationMethods:
    """Tests for stub configuration methods."""

    @pytest.fixture
    def stub(self) -> OverrideAbuseValidatorStub:
        """Create fresh stub for each test."""
        return OverrideAbuseValidatorStub()

    @pytest.mark.asyncio
    async def test_add_forbidden_scope(
        self,
        stub: OverrideAbuseValidatorStub,
    ) -> None:
        """Should be able to add custom forbidden scope."""
        stub.add_forbidden_scope("custom.forbidden")

        result = await stub.validate_constitutional_constraints(
            "custom.forbidden",
            "execute",
        )
        assert result.is_valid is False
        assert result.violation_type == ViolationType.FORBIDDEN_SCOPE

    @pytest.mark.asyncio
    async def test_add_history_edit_pattern(
        self,
        stub: OverrideAbuseValidatorStub,
    ) -> None:
        """Should be able to add custom history edit pattern."""
        stub.add_history_edit_pattern("custom.history")

        result = await stub.is_history_edit_attempt("custom.history")
        assert result is True

    @pytest.mark.asyncio
    async def test_add_evidence_destruction_pattern(
        self,
        stub: OverrideAbuseValidatorStub,
    ) -> None:
        """Should be able to add custom evidence destruction pattern."""
        stub.add_evidence_destruction_pattern("custom.evidence")

        result = await stub.is_evidence_destruction_attempt("custom.evidence")
        assert result is True

    @pytest.mark.asyncio
    async def test_clear_resets_to_defaults(
        self,
        stub: OverrideAbuseValidatorStub,
    ) -> None:
        """Clear should reset all patterns to defaults."""
        # Add custom patterns
        stub.add_forbidden_scope("custom.forbidden")
        stub.add_history_edit_pattern("custom.history")

        # Verify custom patterns work
        result = await stub.validate_constitutional_constraints("custom.forbidden", "x")
        assert result.is_valid is False

        # Clear and verify defaults restored
        stub.clear()

        result = await stub.validate_constitutional_constraints("custom.forbidden", "x")
        assert result.is_valid is True

        # But default patterns still work
        result = await stub.validate_constitutional_constraints("history", "x")
        assert result.is_valid is False


class TestPatternMatching:
    """Tests for pattern matching behavior."""

    @pytest.fixture
    def stub(self) -> OverrideAbuseValidatorStub:
        """Create fresh stub for each test."""
        return OverrideAbuseValidatorStub()

    @pytest.mark.asyncio
    async def test_prefix_matching_with_dot_separator(
        self,
        stub: OverrideAbuseValidatorStub,
    ) -> None:
        """Should match patterns with dot separator prefix."""
        # "history" is in patterns, so "history.anything" should match
        result = await stub.is_history_edit_attempt("history.some.deep.path")
        assert result is True

    @pytest.mark.asyncio
    async def test_no_partial_word_matching(
        self,
        stub: OverrideAbuseValidatorStub,
    ) -> None:
        """Should NOT match partial words without dot separator."""
        # "history" is in patterns, but "historical" is NOT "history."
        result = await stub.is_history_edit_attempt("historical")
        assert result is False

    @pytest.mark.asyncio
    async def test_preserves_scope_in_violation_details(
        self,
        stub: OverrideAbuseValidatorStub,
    ) -> None:
        """Violation details should preserve original scope for debugging."""
        result = await stub.validate_constitutional_constraints(
            "Event_Store.Delete",  # Mixed case
            "execute",
        )
        assert result.is_valid is False
        # Original scope preserved in message
        assert "Event_Store.Delete" in result.violation_details


class TestDefaultPatternConstants:
    """Tests for module-level pattern constants."""

    def test_history_edit_patterns_are_frozenset(self) -> None:
        """HISTORY_EDIT_PATTERNS should be immutable frozenset."""
        assert isinstance(HISTORY_EDIT_PATTERNS, frozenset)

    def test_evidence_destruction_patterns_are_frozenset(self) -> None:
        """EVIDENCE_DESTRUCTION_PATTERNS should be immutable frozenset."""
        assert isinstance(EVIDENCE_DESTRUCTION_PATTERNS, frozenset)

    def test_general_forbidden_scopes_are_frozenset(self) -> None:
        """GENERAL_FORBIDDEN_SCOPES should be immutable frozenset."""
        assert isinstance(GENERAL_FORBIDDEN_SCOPES, frozenset)

    def test_history_edit_patterns_contains_expected_values(self) -> None:
        """HISTORY_EDIT_PATTERNS should contain key patterns."""
        expected = {
            "history",
            "event_store.delete",
            "event_store.modify",
            "audit.delete",
        }
        assert expected.issubset(HISTORY_EDIT_PATTERNS)

    def test_evidence_destruction_patterns_contains_expected_values(self) -> None:
        """EVIDENCE_DESTRUCTION_PATTERNS should contain key patterns."""
        expected = {
            "evidence",
            "witness.remove",
            "signature.invalidate",
            "hash_chain.modify",
        }
        assert expected.issubset(EVIDENCE_DESTRUCTION_PATTERNS)

    def test_general_forbidden_scopes_contains_expected_values(self) -> None:
        """GENERAL_FORBIDDEN_SCOPES should contain witness-related scopes."""
        expected = {"witness", "witnessing", "attestation"}
        assert expected.issubset(GENERAL_FORBIDDEN_SCOPES)
