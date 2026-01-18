"""Unit tests for ReconstitutionArtifact domain model.

Story: consent-gov-8.3: Reconstitution Validation

Tests the domain model for reconstitution artifacts that propose new
system instances after cessation.

Constitutional Context:
- FR53: System can validate Reconstitution Artifact before new instance
- FR54: System can reject reconstitution that claims continuity
- FR55: System can reject reconstitution that inherits legitimacy band
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.domain.governance.cessation.reconstitution_artifact import (
    ReconstitutionArtifact,
    RejectionReason,
    ValidationResult,
    ValidationStatus,
)


class TestReconstitutionArtifact:
    """Tests for ReconstitutionArtifact domain model."""

    def test_create_valid_artifact(self) -> None:
        """Valid artifact can be created with all required fields."""
        cessation_id = uuid4()
        proposer_id = uuid4()
        now = datetime.now(timezone.utc)

        artifact = ReconstitutionArtifact(
            artifact_id=uuid4(),
            cessation_record_id=cessation_id,
            proposed_legitimacy_band="STABLE",
            claims_continuity=False,
            proposed_at=now,
            proposer_id=proposer_id,
        )

        assert artifact.cessation_record_id == cessation_id
        assert artifact.proposed_legitimacy_band == "STABLE"
        assert artifact.claims_continuity is False
        assert artifact.proposer_id == proposer_id

    def test_artifact_is_immutable(self) -> None:
        """Artifact is a frozen dataclass (immutable)."""
        artifact = ReconstitutionArtifact(
            artifact_id=uuid4(),
            cessation_record_id=uuid4(),
            proposed_legitimacy_band="STABLE",
            claims_continuity=False,
            proposed_at=datetime.now(timezone.utc),
            proposer_id=uuid4(),
        )

        with pytest.raises(Exception):  # FrozenInstanceError
            artifact.claims_continuity = True  # type: ignore

    def test_artifact_requires_artifact_id(self) -> None:
        """Artifact requires a unique identifier."""
        artifact = ReconstitutionArtifact(
            artifact_id=uuid4(),
            cessation_record_id=uuid4(),
            proposed_legitimacy_band="STABLE",
            claims_continuity=False,
            proposed_at=datetime.now(timezone.utc),
            proposer_id=uuid4(),
        )

        assert artifact.artifact_id is not None

    def test_artifact_cessation_record_can_be_none(self) -> None:
        """Artifact can have None cessation_record_id (for validation to reject)."""
        artifact = ReconstitutionArtifact(
            artifact_id=uuid4(),
            cessation_record_id=None,  # Missing reference
            proposed_legitimacy_band="STABLE",
            claims_continuity=False,
            proposed_at=datetime.now(timezone.utc),
            proposer_id=uuid4(),
        )

        assert artifact.cessation_record_id is None

    def test_artifact_serialization_to_dict(self) -> None:
        """Artifact can be serialized to dictionary."""
        artifact_id = uuid4()
        cessation_id = uuid4()
        proposer_id = uuid4()
        now = datetime.now(timezone.utc)

        artifact = ReconstitutionArtifact(
            artifact_id=artifact_id,
            cessation_record_id=cessation_id,
            proposed_legitimacy_band="STABLE",
            claims_continuity=False,
            proposed_at=now,
            proposer_id=proposer_id,
        )

        data = artifact.to_dict()

        assert data["artifact_id"] == str(artifact_id)
        assert data["cessation_record_id"] == str(cessation_id)
        assert data["proposed_legitimacy_band"] == "STABLE"
        assert data["claims_continuity"] is False
        assert data["proposer_id"] == str(proposer_id)

    def test_artifact_deserialization_from_dict(self) -> None:
        """Artifact can be deserialized from dictionary."""
        artifact_id = uuid4()
        cessation_id = uuid4()
        proposer_id = uuid4()
        now = datetime.now(timezone.utc)

        data = {
            "artifact_id": str(artifact_id),
            "cessation_record_id": str(cessation_id),
            "proposed_legitimacy_band": "STABLE",
            "claims_continuity": False,
            "proposed_at": now.isoformat(),
            "proposer_id": str(proposer_id),
        }

        artifact = ReconstitutionArtifact.from_dict(data)

        assert artifact.artifact_id == artifact_id
        assert artifact.cessation_record_id == cessation_id
        assert artifact.proposed_legitimacy_band == "STABLE"
        assert artifact.claims_continuity is False

    def test_artifact_serialization_with_none_cessation(self) -> None:
        """Artifact serialization handles None cessation_record_id."""
        artifact = ReconstitutionArtifact(
            artifact_id=uuid4(),
            cessation_record_id=None,
            proposed_legitimacy_band="STABLE",
            claims_continuity=False,
            proposed_at=datetime.now(timezone.utc),
            proposer_id=uuid4(),
        )

        data = artifact.to_dict()
        assert data["cessation_record_id"] is None

        restored = ReconstitutionArtifact.from_dict(data)
        assert restored.cessation_record_id is None


class TestValidationStatus:
    """Tests for ValidationStatus enum."""

    def test_valid_status(self) -> None:
        """VALID status indicates successful validation."""
        assert ValidationStatus.VALID.value == "valid"

    def test_rejected_status(self) -> None:
        """REJECTED status indicates validation failure."""
        assert ValidationStatus.REJECTED.value == "rejected"


class TestRejectionReason:
    """Tests for RejectionReason enum."""

    def test_continuity_claim_reason(self) -> None:
        """CONTINUITY_CLAIM reason for continuity violations."""
        assert RejectionReason.CONTINUITY_CLAIM.value == "continuity_claim"

    def test_legitimacy_inheritance_reason(self) -> None:
        """LEGITIMACY_INHERITANCE reason for band inheritance violations."""
        assert RejectionReason.LEGITIMACY_INHERITANCE.value == "legitimacy_inheritance"

    def test_missing_cessation_reference_reason(self) -> None:
        """MISSING_CESSATION_REFERENCE reason for missing reference."""
        assert (
            RejectionReason.MISSING_CESSATION_REFERENCE.value
            == "missing_cessation_reference"
        )

    def test_invalid_artifact_structure_reason(self) -> None:
        """INVALID_ARTIFACT_STRUCTURE reason for malformed artifacts."""
        assert (
            RejectionReason.INVALID_ARTIFACT_STRUCTURE.value
            == "invalid_artifact_structure"
        )


class TestValidationResult:
    """Tests for ValidationResult domain model."""

    def test_create_valid_result(self) -> None:
        """Valid result has VALID status and no rejections."""
        artifact_id = uuid4()
        now = datetime.now(timezone.utc)

        result = ValidationResult(
            artifact_id=artifact_id,
            status=ValidationStatus.VALID,
            rejection_reasons=[],
            rejection_messages=[],
            validated_at=now,
        )

        assert result.status == ValidationStatus.VALID
        assert len(result.rejection_reasons) == 0
        assert len(result.rejection_messages) == 0

    def test_create_rejected_result(self) -> None:
        """Rejected result has REJECTED status and reasons."""
        artifact_id = uuid4()
        now = datetime.now(timezone.utc)

        result = ValidationResult(
            artifact_id=artifact_id,
            status=ValidationStatus.REJECTED,
            rejection_reasons=[RejectionReason.CONTINUITY_CLAIM],
            rejection_messages=["Cannot claim continuity with ceased system"],
            validated_at=now,
        )

        assert result.status == ValidationStatus.REJECTED
        assert RejectionReason.CONTINUITY_CLAIM in result.rejection_reasons
        assert len(result.rejection_messages) == 1

    def test_result_is_immutable(self) -> None:
        """ValidationResult is a frozen dataclass (immutable)."""
        result = ValidationResult(
            artifact_id=uuid4(),
            status=ValidationStatus.VALID,
            rejection_reasons=[],
            rejection_messages=[],
            validated_at=datetime.now(timezone.utc),
        )

        with pytest.raises(Exception):  # FrozenInstanceError
            result.status = ValidationStatus.REJECTED  # type: ignore

    def test_result_multiple_rejection_reasons(self) -> None:
        """Result can have multiple rejection reasons."""
        result = ValidationResult(
            artifact_id=uuid4(),
            status=ValidationStatus.REJECTED,
            rejection_reasons=[
                RejectionReason.CONTINUITY_CLAIM,
                RejectionReason.LEGITIMACY_INHERITANCE,
                RejectionReason.MISSING_CESSATION_REFERENCE,
            ],
            rejection_messages=[
                "Cannot claim continuity",
                "Cannot inherit legitimacy",
                "Must reference cessation record",
            ],
            validated_at=datetime.now(timezone.utc),
        )

        assert len(result.rejection_reasons) == 3
        assert len(result.rejection_messages) == 3

    def test_result_serialization_to_dict(self) -> None:
        """ValidationResult can be serialized to dictionary."""
        artifact_id = uuid4()
        now = datetime.now(timezone.utc)

        result = ValidationResult(
            artifact_id=artifact_id,
            status=ValidationStatus.REJECTED,
            rejection_reasons=[RejectionReason.CONTINUITY_CLAIM],
            rejection_messages=["Cannot claim continuity"],
            validated_at=now,
        )

        data = result.to_dict()

        assert data["artifact_id"] == str(artifact_id)
        assert data["status"] == "rejected"
        assert data["rejection_reasons"] == ["continuity_claim"]
        assert data["rejection_messages"] == ["Cannot claim continuity"]

    def test_result_deserialization_from_dict(self) -> None:
        """ValidationResult can be deserialized from dictionary."""
        artifact_id = uuid4()
        now = datetime.now(timezone.utc)

        data = {
            "artifact_id": str(artifact_id),
            "status": "rejected",
            "rejection_reasons": ["continuity_claim", "legitimacy_inheritance"],
            "rejection_messages": ["msg1", "msg2"],
            "validated_at": now.isoformat(),
        }

        result = ValidationResult.from_dict(data)

        assert result.artifact_id == artifact_id
        assert result.status == ValidationStatus.REJECTED
        assert len(result.rejection_reasons) == 2

    def test_result_is_valid_property(self) -> None:
        """Result has is_valid property for convenience."""
        valid_result = ValidationResult(
            artifact_id=uuid4(),
            status=ValidationStatus.VALID,
            rejection_reasons=[],
            rejection_messages=[],
            validated_at=datetime.now(timezone.utc),
        )

        rejected_result = ValidationResult(
            artifact_id=uuid4(),
            status=ValidationStatus.REJECTED,
            rejection_reasons=[RejectionReason.CONTINUITY_CLAIM],
            rejection_messages=["msg"],
            validated_at=datetime.now(timezone.utc),
        )

        assert valid_result.is_valid is True
        assert rejected_result.is_valid is False
