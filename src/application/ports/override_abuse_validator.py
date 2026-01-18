"""Override Abuse Validator Port - Constitutional constraint validation (Story 5.9, FR86-FR87).

This port defines the contract for validating override commands against
constitutional constraints, specifically FR86 (general validation) and
FR87 (history edit and evidence destruction prevention).

Constitutional Constraints:
- FR86: System SHALL validate override commands against constitutional constraints
- FR87: Override commands violating constraints SHALL be rejected and logged
- CT-11: Silent failure destroys legitimacy -> All violations must be logged
- CT-12: Witnessing creates accountability -> Rejections MUST be witnessed

This port enables:
- Dependency inversion for constitutional constraint validation
- Testability with mock implementations
- Clear separation between validation logic and abuse detection orchestration
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from src.domain.events.override_abuse import ViolationType


@dataclass(frozen=True)
class ValidationResult:
    """Result of constitutional constraint validation.

    Attributes:
        is_valid: True if override scope passes all constitutional checks.
        violation_type: Type of violation if invalid, None if valid.
        violation_details: Human-readable description of violation if invalid.
    """

    is_valid: bool
    violation_type: ViolationType | None = None
    violation_details: str | None = None

    @classmethod
    def success(cls) -> ValidationResult:
        """Create a successful validation result."""
        return cls(is_valid=True)

    @classmethod
    def failure(
        cls,
        violation_type: ViolationType,
        violation_details: str,
    ) -> ValidationResult:
        """Create a failed validation result.

        Args:
            violation_type: Type of constitutional violation detected.
            violation_details: Human-readable description of the violation.

        Returns:
            ValidationResult indicating validation failure.
        """
        return cls(
            is_valid=False,
            violation_type=violation_type,
            violation_details=violation_details,
        )


class OverrideAbuseValidatorProtocol(Protocol):
    """Protocol for constitutional constraint validation (FR86, FR87).

    Constitutional Constraints:
    - FR86: Override commands must be validated against constitutional constraints
    - FR87: History edit and evidence destruction attempts must be rejected

    Implementations MUST:
    - Validate override scopes against constitutional constraints (FR86)
    - Detect history edit attempts and reject them (FR87)
    - Detect evidence destruction attempts and reject them (FR87)
    - Return detailed validation results for logging and witnessing

    Cross-Epic Integration:
    This port extends ConstitutionValidatorProtocol (Story 5.4) to add
    FR86/FR87 validation beyond witness suppression (FR26).
    """

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
            override_scope: The override scope to validate. Examples:
                - "voting.extension" - likely allowed
                - "history.delete" - forbidden (history edit)
                - "evidence.destroy" - forbidden (evidence destruction)
            action_type: The type of override action being attempted.

        Returns:
            ValidationResult indicating whether the override is valid.
            If invalid, includes violation type and details for logging.

        Note:
            This method does NOT raise exceptions for violations.
            It returns a ValidationResult that can be used to create
            rejection events with proper witness attestation.
        """
        ...

    async def is_history_edit_attempt(self, override_scope: str) -> bool:
        """Check if override scope attempts to edit event history.

        Constitutional Constraint (FR87):
        Override commands that attempt to modify, delete, or alter
        existing event history SHALL be rejected and logged.

        Args:
            override_scope: The override scope to check.

        Returns:
            True if the scope attempts to edit history, False otherwise.

        Examples:
            >>> await validator.is_history_edit_attempt("history")
            True
            >>> await validator.is_history_edit_attempt("event_store.delete")
            True
            >>> await validator.is_history_edit_attempt("voting.extension")
            False
        """
        ...

    async def is_evidence_destruction_attempt(self, override_scope: str) -> bool:
        """Check if override scope attempts to destroy evidence.

        Constitutional Constraint (FR87):
        Override commands that attempt to delete, invalidate, or destroy
        evidence (witnesses, signatures, audit logs) SHALL be rejected.

        Args:
            override_scope: The override scope to check.

        Returns:
            True if the scope attempts to destroy evidence, False otherwise.

        Examples:
            >>> await validator.is_evidence_destruction_attempt("evidence.delete")
            True
            >>> await validator.is_evidence_destruction_attempt("witness.remove")
            True
            >>> await validator.is_evidence_destruction_attempt("voting.extension")
            False
        """
        ...
