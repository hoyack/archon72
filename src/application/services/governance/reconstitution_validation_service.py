"""ReconstitutionValidationService for validating new system instances.

Story: consent-gov-8.3: Reconstitution Validation

This service validates reconstitution artifacts before new system instances
can be created after cessation. It enforces that:

1. Artifacts reference a valid cessation record
2. Artifacts do NOT claim continuity with previous instance (FR54)
3. Artifacts do NOT inherit legitimacy band (FR55)

Why These Restrictions?
- Cessation is permanent for that instance
- New instance is a distinct constitutional entity
- Trust cannot be inherited
- Legitimacy must be earned through operation

Constitutional Context:
- FR53: System can validate Reconstitution Artifact before new instance
- FR54: System can reject reconstitution that claims continuity
- FR55: System can reject reconstitution that inherits legitimacy band
"""

from typing import Protocol
from uuid import UUID

from src.application.ports.governance.two_phase_emitter_port import (
    TwoPhaseEventEmitterPort,
)
from src.application.ports.time_authority import TimeAuthorityProtocol
from src.domain.governance.cessation import (
    CessationRecord,
    ReconstitutionArtifact,
    RejectionReason,
    ValidationResult,
    ValidationStatus,
)

# Baseline legitimacy for new instances - must be STABLE
BASELINE_LEGITIMACY_BAND = "STABLE"


# Human-readable rejection messages (AC6)
REJECTION_MESSAGES = {
    RejectionReason.CONTINUITY_CLAIM: (
        "New instance cannot claim continuity with ceased system. "
        "Each system instance is a distinct constitutional entity."
    ),
    RejectionReason.LEGITIMACY_INHERITANCE: (
        "New instance cannot inherit legitimacy from previous instance. "
        "Legitimacy must be earned through operation, not claimed."
    ),
    RejectionReason.MISSING_CESSATION_REFERENCE: (
        "Reconstitution artifact must reference the cessation record "
        "of the previous instance to acknowledge its end."
    ),
    RejectionReason.INVALID_ARTIFACT_STRUCTURE: (
        "Reconstitution artifact has invalid structure. "
        "All required fields must be present and valid."
    ),
}


class CessationRecordPort(Protocol):
    """Port for cessation record operations."""

    async def get_record(self) -> CessationRecord | None:
        """Get cessation record if exists."""
        ...


class ReconstitutionPort(Protocol):
    """Port for reconstitution validation operations."""

    async def store_validation_result(
        self,
        result: ValidationResult,
    ) -> None:
        """Store validation result."""
        ...

    async def get_validation_result(
        self,
        artifact_id: UUID,
    ) -> ValidationResult | None:
        """Get validation result for artifact."""
        ...


class ReconstitutionValidationService:
    """Validates reconstitution artifacts before new instance creation.

    This service checks that reconstitution artifacts comply with
    constitutional requirements:

    1. Must reference a valid cessation record
    2. Cannot claim continuity with previous instance (FR54)
    3. Cannot inherit legitimacy band (FR55)
    4. Must propose STABLE (baseline) legitimacy

    Example:
        >>> service = ReconstitutionValidationService(...)
        >>> result = await service.validate_artifact(artifact)
        >>> if result.is_valid:
        ...     # Proceed with new instance creation
        ...     pass
        >>> else:
        ...     # Handle rejection reasons
        ...     for msg in result.rejection_messages:
        ...         print(msg)

    Constitutional Context:
        - FR53: Validation before new instance
        - FR54: Reject continuity claims
        - FR55: Reject legitimacy inheritance
    """

    def __init__(
        self,
        reconstitution_port: ReconstitutionPort,
        cessation_port: CessationRecordPort,
        event_emitter: TwoPhaseEventEmitterPort,
        time_authority: TimeAuthorityProtocol,
    ) -> None:
        """Initialize ReconstitutionValidationService.

        Args:
            reconstitution_port: Port for validation result persistence.
            cessation_port: Port for cessation record queries.
            event_emitter: Port for two-phase events.
            time_authority: TimeAuthority for timestamps.
        """
        self._reconstitution = reconstitution_port
        self._cessation = cessation_port
        self._event_emitter = event_emitter
        self._time = time_authority

    async def validate_artifact(
        self,
        artifact: ReconstitutionArtifact,
    ) -> ValidationResult:
        """Validate reconstitution artifact.

        Checks:
        1. Artifact references a valid cessation record
        2. Artifact does not claim continuity (FR54)
        3. Artifact does not inherit legitimacy (FR55)

        Args:
            artifact: The reconstitution artifact to validate.

        Returns:
            ValidationResult with status and any rejection reasons.
            If result.is_valid is True, new instance can proceed.
            If result.is_valid is False, check rejection_messages.
        """
        now = self._time.utcnow()
        rejection_reasons: list[RejectionReason] = []
        rejection_messages: list[str] = []

        # Emit intent
        correlation_id = await self._event_emitter.emit_intent(
            operation_type="constitutional.reconstitution.validated",
            actor_id=str(artifact.proposer_id),
            target_entity_id=str(artifact.artifact_id),
            intent_payload={
                "artifact_id": str(artifact.artifact_id),
                "proposed_legitimacy_band": artifact.proposed_legitimacy_band,
                "claims_continuity": artifact.claims_continuity,
                "proposed_at": artifact.proposed_at.isoformat(),
            },
        )

        # Check for continuity claims (FR54, AC2)
        if artifact.claims_continuity:
            rejection_reasons.append(RejectionReason.CONTINUITY_CLAIM)
            rejection_messages.append(
                REJECTION_MESSAGES[RejectionReason.CONTINUITY_CLAIM]
            )

        # Check for legitimacy inheritance (FR55, AC3)
        if artifact.proposed_legitimacy_band != BASELINE_LEGITIMACY_BAND:
            rejection_reasons.append(RejectionReason.LEGITIMACY_INHERITANCE)
            rejection_messages.append(
                REJECTION_MESSAGES[RejectionReason.LEGITIMACY_INHERITANCE]
            )

        # Check for cessation reference (AC7)
        if artifact.cessation_record_id is None:
            rejection_reasons.append(RejectionReason.MISSING_CESSATION_REFERENCE)
            rejection_messages.append(
                REJECTION_MESSAGES[RejectionReason.MISSING_CESSATION_REFERENCE]
            )
        else:
            # Verify cessation record exists
            cessation = await self._cessation.get_record()
            if cessation is None or cessation.record_id != artifact.cessation_record_id:
                rejection_reasons.append(RejectionReason.MISSING_CESSATION_REFERENCE)
                rejection_messages.append("Referenced cessation record does not exist.")

        # Determine result status
        status = (
            ValidationStatus.VALID
            if not rejection_reasons
            else ValidationStatus.REJECTED
        )

        result = ValidationResult(
            artifact_id=artifact.artifact_id,
            status=status,
            rejection_reasons=rejection_reasons,
            rejection_messages=rejection_messages,
            validated_at=now,
        )

        # Store result
        await self._reconstitution.store_validation_result(result)

        # Emit commit with outcome
        await self._event_emitter.emit_commit(
            correlation_id=correlation_id,
            outcome_payload={
                "artifact_id": str(artifact.artifact_id),
                "status": status.value,
                "rejection_count": len(rejection_reasons),
                "rejection_reasons": [r.value for r in rejection_reasons],
                "validated_at": now.isoformat(),
            },
        )

        return result
