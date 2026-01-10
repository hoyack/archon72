"""Override Abuse Validator Stub - Test implementation (Story 5.9, FR86-FR87).

This stub implements the OverrideAbuseValidatorProtocol for testing purposes.
It provides configurable validation behavior for unit and integration tests.

Constitutional Constraints:
- FR86: System SHALL validate override commands against constitutional constraints
- FR87: Override commands violating constraints SHALL be rejected and logged
- CT-11: Silent failure destroys legitimacy -> All violations must be logged
- CT-12: Witnessing creates accountability -> Rejections MUST be witnessed
"""

from __future__ import annotations

from src.application.ports.override_abuse_validator import (
    OverrideAbuseValidatorProtocol,
    ValidationResult,
)
from src.domain.events.override_abuse import ViolationType


# Default forbidden scope patterns for history edit detection (FR87)
HISTORY_EDIT_PATTERNS: frozenset[str] = frozenset([
    "history",
    "event_store.delete",
    "event_store.modify",
    "event_store.update",
    "audit.delete",
    "audit.modify",
    "log.delete",
    "log.modify",
])

# Default forbidden scope patterns for evidence destruction detection (FR87)
EVIDENCE_DESTRUCTION_PATTERNS: frozenset[str] = frozenset([
    "evidence",
    "evidence.delete",
    "audit_log.delete",
    "witness.remove",
    "witness.delete",
    "signature.invalidate",
    "hash_chain.modify",
])

# Default general forbidden scopes (FR86)
GENERAL_FORBIDDEN_SCOPES: frozenset[str] = frozenset([
    "witness",
    "witnessing",
    "attestation",
    "witness_service",
    "witness_pool",
])


class OverrideAbuseValidatorStub(OverrideAbuseValidatorProtocol):
    """Stub implementation of OverrideAbuseValidatorProtocol for testing.

    This stub provides configurable validation behavior:
    - Default patterns for history edit detection (FR87)
    - Default patterns for evidence destruction detection (FR87)
    - Configurable additional forbidden scopes
    - Clear methods for test isolation

    Usage:
        validator = OverrideAbuseValidatorStub()

        # Add custom forbidden scope for test
        validator.add_forbidden_scope("custom.forbidden")

        # Validate
        result = await validator.validate_constitutional_constraints("custom.forbidden", "test")
        assert not result.is_valid

        # Clean up for next test
        validator.clear()
    """

    def __init__(self) -> None:
        """Initialize the stub with default patterns."""
        self._history_edit_patterns: set[str] = set(HISTORY_EDIT_PATTERNS)
        self._evidence_destruction_patterns: set[str] = set(EVIDENCE_DESTRUCTION_PATTERNS)
        self._forbidden_scopes: set[str] = set(GENERAL_FORBIDDEN_SCOPES)

    def add_forbidden_scope(self, scope: str) -> None:
        """Add a scope to the forbidden list for testing.

        Args:
            scope: Scope pattern to forbid.
        """
        self._forbidden_scopes.add(scope.lower())

    def add_history_edit_pattern(self, pattern: str) -> None:
        """Add a history edit pattern for testing.

        Args:
            pattern: Scope pattern that indicates history edit attempt.
        """
        self._history_edit_patterns.add(pattern.lower())

    def add_evidence_destruction_pattern(self, pattern: str) -> None:
        """Add an evidence destruction pattern for testing.

        Args:
            pattern: Scope pattern that indicates evidence destruction attempt.
        """
        self._evidence_destruction_patterns.add(pattern.lower())

    def clear(self) -> None:
        """Reset to default patterns for test isolation."""
        self._history_edit_patterns = set(HISTORY_EDIT_PATTERNS)
        self._evidence_destruction_patterns = set(EVIDENCE_DESTRUCTION_PATTERNS)
        self._forbidden_scopes = set(GENERAL_FORBIDDEN_SCOPES)

    async def validate_constitutional_constraints(
        self,
        override_scope: str,
        action_type: str,
    ) -> ValidationResult:
        """Validate override scope against all constitutional constraints.

        Constitutional Constraint (FR86):
        System SHALL validate override commands against constitutional
        constraints before execution.

        Args:
            override_scope: The override scope to validate.
            action_type: The type of override action being attempted.

        Returns:
            ValidationResult indicating whether the override is valid.
        """
        scope_lower = override_scope.lower()

        # Check history edit patterns (FR87)
        if self._is_pattern_match(scope_lower, self._history_edit_patterns):
            return ValidationResult.failure(
                violation_type=ViolationType.HISTORY_EDIT,
                violation_details=f"FR87: Scope '{override_scope}' attempts to edit event history",
            )

        # Check evidence destruction patterns (FR87)
        if self._is_pattern_match(scope_lower, self._evidence_destruction_patterns):
            return ValidationResult.failure(
                violation_type=ViolationType.EVIDENCE_DESTRUCTION,
                violation_details=f"FR87: Scope '{override_scope}' attempts to destroy evidence",
            )

        # Check general forbidden scopes (FR86)
        if self._is_pattern_match(scope_lower, self._forbidden_scopes):
            return ValidationResult.failure(
                violation_type=ViolationType.FORBIDDEN_SCOPE,
                violation_details=f"FR86: Scope '{override_scope}' is forbidden",
            )

        # Check witness suppression patterns (FR26 - already covered by Story 5.4)
        if self._is_witness_suppression_scope(scope_lower):
            return ValidationResult.failure(
                violation_type=ViolationType.WITNESS_SUPPRESSION,
                violation_details=f"FR26: Scope '{override_scope}' attempts to suppress witnessing",
            )

        return ValidationResult.success()

    async def is_history_edit_attempt(self, override_scope: str) -> bool:
        """Check if override scope attempts to edit event history.

        Constitutional Constraint (FR87):
        Override commands that attempt to modify, delete, or alter
        existing event history SHALL be rejected and logged.

        Args:
            override_scope: The override scope to check.

        Returns:
            True if the scope attempts to edit history, False otherwise.
        """
        return self._is_pattern_match(
            override_scope.lower(),
            self._history_edit_patterns,
        )

    async def is_evidence_destruction_attempt(self, override_scope: str) -> bool:
        """Check if override scope attempts to destroy evidence.

        Constitutional Constraint (FR87):
        Override commands that attempt to delete, invalidate, or destroy
        evidence SHALL be rejected.

        Args:
            override_scope: The override scope to check.

        Returns:
            True if the scope attempts to destroy evidence, False otherwise.
        """
        return self._is_pattern_match(
            override_scope.lower(),
            self._evidence_destruction_patterns,
        )

    def _is_pattern_match(self, scope: str, patterns: set[str]) -> bool:
        """Check if scope matches any pattern (exact or prefix match).

        Args:
            scope: The scope to check (lowercase).
            patterns: Set of patterns to match against.

        Returns:
            True if scope matches any pattern, False otherwise.
        """
        # Exact match
        if scope in patterns:
            return True

        # Prefix match (e.g., "history.delete" matches "history")
        for pattern in patterns:
            if scope.startswith(f"{pattern}."):
                return True

        return False

    def _is_witness_suppression_scope(self, scope: str) -> bool:
        """Check if scope attempts witness suppression (FR26).

        Note: This is already covered by Story 5.4's ConstitutionValidatorProtocol,
        but included here for completeness.

        Args:
            scope: The scope to check (lowercase).

        Returns:
            True if scope attempts witness suppression.
        """
        witness_patterns = {"witness", "witnessing", "attestation"}

        if scope in witness_patterns:
            return True

        for pattern in witness_patterns:
            if scope.startswith(f"{pattern}."):
                return True

        return False
