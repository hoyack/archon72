"""Unit tests for forbidden override scopes detection (Story 5.4, FR26).

Tests the is_witness_suppression_scope function and FORBIDDEN_OVERRIDE_SCOPES
constants that enforce FR26 (Constitution Supremacy).

Constitutional Constraints:
- FR26: Overrides that attempt to suppress witnessing are invalid by definition
- CT-12: Witnessing creates accountability - no unwitnessed actions
"""

import pytest

from src.domain.models.override_reason import (
    FORBIDDEN_OVERRIDE_SCOPE_PATTERNS,
    FORBIDDEN_OVERRIDE_SCOPES,
    is_witness_suppression_scope,
)


class TestForbiddenOverrideScopesConstants:
    """Tests for FORBIDDEN_OVERRIDE_SCOPES constant."""

    def test_witness_scope_is_forbidden(self) -> None:
        """FR26: 'witness' scope must be forbidden."""
        assert "witness" in FORBIDDEN_OVERRIDE_SCOPES

    def test_witnessing_scope_is_forbidden(self) -> None:
        """FR26: 'witnessing' scope must be forbidden."""
        assert "witnessing" in FORBIDDEN_OVERRIDE_SCOPES

    def test_attestation_scope_is_forbidden(self) -> None:
        """FR26: 'attestation' scope must be forbidden."""
        assert "attestation" in FORBIDDEN_OVERRIDE_SCOPES

    def test_witness_service_scope_is_forbidden(self) -> None:
        """FR26: 'witness_service' scope must be forbidden."""
        assert "witness_service" in FORBIDDEN_OVERRIDE_SCOPES

    def test_witness_pool_scope_is_forbidden(self) -> None:
        """FR26: 'witness_pool' scope must be forbidden."""
        assert "witness_pool" in FORBIDDEN_OVERRIDE_SCOPES

    def test_forbidden_scopes_is_frozenset(self) -> None:
        """Forbidden scopes should be immutable frozenset."""
        assert isinstance(FORBIDDEN_OVERRIDE_SCOPES, frozenset)


class TestForbiddenOverrideScopePatterns:
    """Tests for FORBIDDEN_OVERRIDE_SCOPE_PATTERNS constant."""

    def test_witness_dot_pattern_exists(self) -> None:
        """FR26: 'witness.' prefix pattern must exist."""
        assert "witness." in FORBIDDEN_OVERRIDE_SCOPE_PATTERNS

    def test_attestation_dot_pattern_exists(self) -> None:
        """FR26: 'attestation.' prefix pattern must exist."""
        assert "attestation." in FORBIDDEN_OVERRIDE_SCOPE_PATTERNS

    def test_patterns_is_tuple(self) -> None:
        """Patterns should be tuple for immutability."""
        assert isinstance(FORBIDDEN_OVERRIDE_SCOPE_PATTERNS, tuple)


class TestIsWitnessSuppressionScope:
    """Tests for is_witness_suppression_scope function (FR26)."""

    # =========================================================================
    # Exact match tests - forbidden scopes
    # =========================================================================

    def test_witness_scope_is_suppression(self) -> None:
        """FR26: 'witness' scope suppresses witnessing."""
        assert is_witness_suppression_scope("witness") is True

    def test_witnessing_scope_is_suppression(self) -> None:
        """FR26: 'witnessing' scope suppresses witnessing."""
        assert is_witness_suppression_scope("witnessing") is True

    def test_attestation_scope_is_suppression(self) -> None:
        """FR26: 'attestation' scope suppresses witnessing."""
        assert is_witness_suppression_scope("attestation") is True

    def test_witness_service_scope_is_suppression(self) -> None:
        """FR26: 'witness_service' scope suppresses witnessing."""
        assert is_witness_suppression_scope("witness_service") is True

    def test_witness_pool_scope_is_suppression(self) -> None:
        """FR26: 'witness_pool' scope suppresses witnessing."""
        assert is_witness_suppression_scope("witness_pool") is True

    # =========================================================================
    # Pattern match tests - witness.* and attestation.*
    # =========================================================================

    def test_witness_disable_scope_is_suppression(self) -> None:
        """FR26: 'witness.disable' scope suppresses witnessing (pattern match)."""
        assert is_witness_suppression_scope("witness.disable") is True

    def test_witness_pool_override_scope_is_suppression(self) -> None:
        """FR26: 'witness.pool' scope suppresses witnessing (pattern match)."""
        assert is_witness_suppression_scope("witness.pool") is True

    def test_attestation_disable_scope_is_suppression(self) -> None:
        """FR26: 'attestation.disable' scope suppresses witnessing (pattern match)."""
        assert is_witness_suppression_scope("attestation.disable") is True

    def test_attestation_override_scope_is_suppression(self) -> None:
        """FR26: 'attestation.override' scope suppresses witnessing (pattern match)."""
        assert is_witness_suppression_scope("attestation.override") is True

    # =========================================================================
    # Case insensitivity tests
    # =========================================================================

    def test_uppercase_witness_is_suppression(self) -> None:
        """FR26: Validation should be case-insensitive."""
        assert is_witness_suppression_scope("WITNESS") is True

    def test_mixed_case_witnessing_is_suppression(self) -> None:
        """FR26: Validation should be case-insensitive."""
        assert is_witness_suppression_scope("Witnessing") is True

    def test_uppercase_attestation_disable_is_suppression(self) -> None:
        """FR26: Pattern matching should be case-insensitive."""
        assert is_witness_suppression_scope("ATTESTATION.DISABLE") is True

    # =========================================================================
    # Allowed scopes tests - should NOT be suppression
    # =========================================================================

    def test_voting_extension_is_allowed(self) -> None:
        """Normal business scope 'voting.extension' should be allowed."""
        assert is_witness_suppression_scope("voting.extension") is False

    def test_ceremony_health_is_allowed(self) -> None:
        """Normal business scope 'ceremony.health' should be allowed."""
        assert is_witness_suppression_scope("ceremony.health") is False

    def test_configuration_scope_is_allowed(self) -> None:
        """Normal business scope 'configuration' should be allowed."""
        assert is_witness_suppression_scope("configuration") is False

    def test_halt_scope_is_allowed(self) -> None:
        """Normal business scope 'halt' should be allowed."""
        assert is_witness_suppression_scope("halt") is False

    def test_emergency_scope_is_allowed(self) -> None:
        """Normal business scope 'emergency' should be allowed."""
        assert is_witness_suppression_scope("emergency") is False

    def test_agent_scope_is_allowed(self) -> None:
        """Normal business scope 'agent' should be allowed."""
        assert is_witness_suppression_scope("agent") is False

    def test_deliberation_scope_is_allowed(self) -> None:
        """Normal business scope 'deliberation' should be allowed."""
        assert is_witness_suppression_scope("deliberation") is False

    # =========================================================================
    # Edge cases
    # =========================================================================

    def test_empty_scope_is_allowed(self) -> None:
        """Empty scope should be allowed (validation handled elsewhere)."""
        assert is_witness_suppression_scope("") is False

    def test_whitespace_scope_is_allowed(self) -> None:
        """Whitespace scope should be allowed (validation handled elsewhere)."""
        assert is_witness_suppression_scope("   ") is False

    def test_partial_witness_word_is_allowed(self) -> None:
        """'witnes' (partial) should be allowed - not an exact match."""
        assert is_witness_suppression_scope("witnes") is False

    def test_witness_suffix_is_allowed(self) -> None:
        """'my_witness' should be allowed - suffix doesn't match pattern."""
        assert is_witness_suppression_scope("my_witness") is False

    @pytest.mark.parametrize(
        "scope,expected",
        [
            # Forbidden exact matches
            ("witness", True),
            ("witnessing", True),
            ("attestation", True),
            ("witness_service", True),
            ("witness_pool", True),
            # Forbidden patterns
            ("witness.anything", True),
            ("attestation.anything", True),
            # Allowed scopes
            ("voting", False),
            ("ceremony", False),
            ("keeper", False),
            ("observer", False),
        ],
    )
    def test_parametrized_scope_detection(self, scope: str, expected: bool) -> None:
        """Parametrized test for various scopes."""
        assert is_witness_suppression_scope(scope) is expected
