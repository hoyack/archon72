"""Constitution Supremacy Validator Service (Story 5.4, FR26, PM-4).

This service validates override commands against constitutional constraints,
specifically enforcing FR26 (Constitution Supremacy) which prohibits
overrides that attempt to suppress witnessing.

Constitutional Constraints:
- FR26: Overrides that attempt to suppress witnessing are invalid by definition
- CT-12: Witnessing creates accountability - no unwitnessed actions
- PM-4: Cross-epic FR ownership - Epic 1 enforces witnessing, Epic 5 validates

Architecture Pattern:
    This service is injected into OverrideService to add a validation layer
    BEFORE override events are written. If validation fails, the override
    is rejected before any event is logged.

    Override Request
         │
         ▼
    ConstitutionSupremacyValidator  ← THIS SERVICE
         │ (pass if valid scope)
         ▼
    OverrideService (logs event)
         │
         ▼
    AtomicEventWriter (witnesses event)
"""

from __future__ import annotations

from structlog import get_logger

from src.application.ports.constitution_validator import ConstitutionValidatorProtocol
from src.domain.errors.override import WitnessSuppressionAttemptError
from src.domain.models.override_reason import is_witness_suppression_scope

logger = get_logger()


class ConstitutionSupremacyValidator(ConstitutionValidatorProtocol):
    """Validates override commands against constitutional constraints (FR26).

    Constitutional Constraint (FR26):
    Overrides that attempt to suppress witnessing are invalid by definition.
    This validator detects and rejects such attempts.

    Cross-Epic Requirement (PM-4):
    This validator is the Epic 5 enforcement of FR26.
    It protects the witnessing guarantees established by Epic 1
    (AtomicEventWriter) from being bypassed through override scopes.

    The validator:
    1. Checks override scope against forbidden patterns
    2. Rejects witness suppression attempts with WitnessSuppressionAttemptError
    3. Logs all rejection attempts for accountability

    Thread Safety:
        This service is stateless and thread-safe.
    """

    async def validate_override_scope(self, scope: str) -> None:
        """Validate that override scope does not suppress witnessing.

        Constitutional Constraint (FR26):
        This method enforces constitution supremacy by rejecting any
        override scope that would disable or suppress the witnessing
        mechanism.

        Args:
            scope: Override scope to validate.

        Raises:
            WitnessSuppressionAttemptError: If scope attempts to suppress
                witnessing. Error message includes "FR26" reference.

        Returns:
            None if scope is valid (does not suppress witnessing).
        """
        log = logger.bind(
            operation="validate_override_scope",
            scope=scope,
        )

        if is_witness_suppression_scope(scope):
            log.warning(
                "witness_suppression_attempt_rejected",
                fr_ref="FR26",
                message="Override scope targets witnessing system - REJECTED",
            )
            raise WitnessSuppressionAttemptError(
                scope=scope,
                message="FR26: Constitution supremacy - witnessing cannot be suppressed",
            )

        log.debug(
            "override_scope_validated",
            message="Override scope is valid (does not suppress witnessing)",
        )
