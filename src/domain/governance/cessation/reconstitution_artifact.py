"""Reconstitution artifact domain model for system lifecycle management.

Story: consent-gov-8.3: Reconstitution Validation

This module defines the domain models for reconstitution artifacts that
propose new system instances after cessation.

Reconstitution Artifact is:
- Immutable (frozen dataclass)
- References cessation record of previous instance
- Declares proposed legitimacy band (must be STABLE)
- Declares whether it claims continuity (must be false)

Why These Restrictions?
- Cessation is permanent for that instance
- New instance cannot inherit trust
- Continuity claims are false
- Legitimacy must be earned fresh

Constitutional Context:
- FR53: System can validate Reconstitution Artifact before new instance
- FR54: System can reject reconstitution that claims continuity
- FR55: System can reject reconstitution that inherits legitimacy band
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID


class ValidationStatus(Enum):
    """Status of reconstitution validation.

    Attributes:
        VALID: Artifact passes all validation rules.
        REJECTED: Artifact violates one or more validation rules.
    """

    VALID = "valid"
    REJECTED = "rejected"


class RejectionReason(Enum):
    """Reason for reconstitution rejection.

    Each reason maps to a specific validation rule violation.

    Attributes:
        CONTINUITY_CLAIM: Artifact claims continuity with previous instance (FR54).
        LEGITIMACY_INHERITANCE: Artifact tries to inherit legitimacy band (FR55).
        MISSING_CESSATION_REFERENCE: Artifact doesn't reference cessation record.
        INVALID_ARTIFACT_STRUCTURE: Artifact has invalid or malformed structure.
    """

    CONTINUITY_CLAIM = "continuity_claim"
    LEGITIMACY_INHERITANCE = "legitimacy_inheritance"
    MISSING_CESSATION_REFERENCE = "missing_cessation_reference"
    INVALID_ARTIFACT_STRUCTURE = "invalid_artifact_structure"


@dataclass(frozen=True)
class ReconstitutionArtifact:
    """Artifact proposing new system instance after cessation.

    Must be validated before new instance can start. A valid artifact:
    - References the cessation record of the previous instance
    - Does NOT claim continuity with the previous instance
    - Proposes STABLE (baseline) legitimacy band only

    Attributes:
        artifact_id: Unique identifier for this artifact.
        cessation_record_id: Reference to previous instance's cessation record.
            Can be None (which will cause validation rejection).
        proposed_legitimacy_band: The legitimacy band proposed for new instance.
            Must be "STABLE" for validation to pass.
        claims_continuity: Whether this artifact claims continuity with previous
            instance. Must be False for validation to pass.
        proposed_at: Timestamp when this artifact was created.
        proposer_id: Identifier of who is proposing this new instance.

    Example:
        >>> from uuid import uuid4
        >>> from datetime import datetime, timezone
        >>> artifact = ReconstitutionArtifact(
        ...     artifact_id=uuid4(),
        ...     cessation_record_id=uuid4(),  # Reference to cessation
        ...     proposed_legitimacy_band="STABLE",  # Must be baseline
        ...     claims_continuity=False,  # Cannot claim continuity
        ...     proposed_at=datetime.now(timezone.utc),
        ...     proposer_id=uuid4(),
        ... )

    Constitutional Context:
        - FR53: Artifact is validated before new instance
        - FR54: claims_continuity=True causes rejection
        - FR55: proposed_legitimacy_band != "STABLE" causes rejection
    """

    artifact_id: UUID
    """Unique identifier for this reconstitution artifact."""

    cessation_record_id: Optional[UUID]
    """Reference to the cessation record of the previous instance.

    Must be provided and valid for artifact to pass validation.
    None indicates missing reference (will be rejected).
    """

    proposed_legitimacy_band: str
    """The legitimacy band proposed for the new instance.

    Must be "STABLE" (baseline) for validation to pass.
    New instances cannot inherit higher bands from previous instance.
    """

    claims_continuity: bool
    """Whether this artifact claims continuity with previous instance.

    Must be False for validation to pass. New instances are distinct
    constitutional entities - they cannot claim to be the "same" system.
    """

    proposed_at: datetime
    """Timestamp when this artifact was created."""

    proposer_id: UUID
    """Identifier of who is proposing this new instance."""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for JSON/event payloads.

        Returns:
            Dictionary representation suitable for JSON serialization.
        """
        return {
            "artifact_id": str(self.artifact_id),
            "cessation_record_id": str(self.cessation_record_id) if self.cessation_record_id else None,
            "proposed_legitimacy_band": self.proposed_legitimacy_band,
            "claims_continuity": self.claims_continuity,
            "proposed_at": self.proposed_at.isoformat(),
            "proposer_id": str(self.proposer_id),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ReconstitutionArtifact":
        """Deserialize from dictionary.

        Args:
            data: Dictionary from to_dict() or event payload.

        Returns:
            Reconstructed ReconstitutionArtifact.
        """
        cessation_id = data.get("cessation_record_id")
        return cls(
            artifact_id=UUID(data["artifact_id"]),
            cessation_record_id=UUID(cessation_id) if cessation_id else None,
            proposed_legitimacy_band=data["proposed_legitimacy_band"],
            claims_continuity=data["claims_continuity"],
            proposed_at=datetime.fromisoformat(data["proposed_at"]),
            proposer_id=UUID(data["proposer_id"]),
        )


@dataclass(frozen=True)
class ValidationResult:
    """Result of reconstitution artifact validation.

    Captures the outcome of validating a reconstitution artifact,
    including any rejection reasons and human-readable messages.

    Attributes:
        artifact_id: The artifact that was validated.
        status: VALID or REJECTED.
        rejection_reasons: List of RejectionReason enums (empty if valid).
        rejection_messages: Human-readable explanations (empty if valid).
        validated_at: Timestamp when validation occurred.

    Example:
        >>> result = ValidationResult(
        ...     artifact_id=uuid4(),
        ...     status=ValidationStatus.VALID,
        ...     rejection_reasons=[],
        ...     rejection_messages=[],
        ...     validated_at=datetime.now(timezone.utc),
        ... )
        >>> result.is_valid
        True

    Constitutional Context:
        - Implements FR53 validation result
        - Clear messages for FR54/FR55 rejections (AC6)
    """

    artifact_id: UUID
    """The artifact that was validated."""

    status: ValidationStatus
    """Validation outcome: VALID or REJECTED."""

    rejection_reasons: list[RejectionReason]
    """List of reasons for rejection (empty if valid)."""

    rejection_messages: list[str]
    """Human-readable explanations for each rejection."""

    validated_at: datetime
    """Timestamp when validation occurred."""

    @property
    def is_valid(self) -> bool:
        """Check if validation passed.

        Returns:
            True if status is VALID, False otherwise.
        """
        return self.status == ValidationStatus.VALID

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for JSON/event payloads.

        Returns:
            Dictionary representation suitable for JSON serialization.
        """
        return {
            "artifact_id": str(self.artifact_id),
            "status": self.status.value,
            "rejection_reasons": [r.value for r in self.rejection_reasons],
            "rejection_messages": self.rejection_messages,
            "validated_at": self.validated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ValidationResult":
        """Deserialize from dictionary.

        Args:
            data: Dictionary from to_dict() or event payload.

        Returns:
            Reconstructed ValidationResult.
        """
        return cls(
            artifact_id=UUID(data["artifact_id"]),
            status=ValidationStatus(data["status"]),
            rejection_reasons=[RejectionReason(r) for r in data["rejection_reasons"]],
            rejection_messages=data["rejection_messages"],
            validated_at=datetime.fromisoformat(data["validated_at"]),
        )
