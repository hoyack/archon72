"""Unit tests for ReconstitutionValidationService.

Story: consent-gov-8.3: Reconstitution Validation

Tests the service that validates reconstitution artifacts before allowing
new system instances to be created after cessation.

Constitutional Context:
- FR53: System can validate Reconstitution Artifact before new instance
- FR54: System can reject reconstitution that claims continuity
- FR55: System can reject reconstitution that inherits legitimacy band
"""

from datetime import datetime, timezone
from typing import Optional
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from src.application.services.governance.reconstitution_validation_service import (
    BASELINE_LEGITIMACY_BAND,
    REJECTION_MESSAGES,
    ReconstitutionValidationService,
)
from src.domain.governance.cessation import (
    CessationRecord,
    ReconstitutionArtifact,
    RejectionReason,
    SystemSnapshot,
    ValidationResult,
    ValidationStatus,
)


class MockCessationRecordPort:
    """Mock port for cessation record operations."""

    def __init__(self, record: Optional[CessationRecord] = None) -> None:
        self._record = record

    async def get_record(self) -> Optional[CessationRecord]:
        return self._record

    def set_record(self, record: Optional[CessationRecord]) -> None:
        self._record = record


class MockReconstitutionPort:
    """Mock port for reconstitution validation results."""

    def __init__(self) -> None:
        self._results: dict[UUID, ValidationResult] = {}

    async def store_validation_result(self, result: ValidationResult) -> None:
        self._results[result.artifact_id] = result

    async def get_validation_result(self, artifact_id: UUID) -> Optional[ValidationResult]:
        return self._results.get(artifact_id)


class MockEventEmitter:
    """Mock two-phase event emitter."""

    def __init__(self) -> None:
        self.emitted_intents: list[dict] = []
        self.emitted_commits: list[dict] = []
        self.emitted_failures: list[dict] = []
        self._next_correlation_id = uuid4()

    async def emit_intent(
        self,
        operation_type: str,
        actor_id: str,
        target_entity_id: str,
        intent_payload: dict,
    ) -> UUID:
        self.emitted_intents.append({
            "operation_type": operation_type,
            "actor_id": actor_id,
            "target_entity_id": target_entity_id,
            "payload": intent_payload,
        })
        return self._next_correlation_id

    async def emit_commit(
        self,
        correlation_id: UUID,
        outcome_payload: dict,
    ) -> None:
        self.emitted_commits.append({
            "correlation_id": correlation_id,
            "payload": outcome_payload,
        })

    async def emit_failure(
        self,
        correlation_id: UUID,
        failure_reason: str,
        failure_details: dict,
    ) -> None:
        self.emitted_failures.append({
            "correlation_id": correlation_id,
            "reason": failure_reason,
            "details": failure_details,
        })


class MockTimeAuthority:
    """Mock time authority."""

    def __init__(self, now: datetime = None) -> None:
        self._now = now or datetime.now(timezone.utc)

    def utcnow(self) -> datetime:
        return self._now


@pytest.fixture
def cessation_record() -> CessationRecord:
    """Create a valid cessation record for testing."""
    return CessationRecord(
        record_id=uuid4(),
        trigger_id=uuid4(),
        operator_id=uuid4(),
        created_at=datetime.now(timezone.utc),
        final_ledger_hash="sha256:abc123",
        final_sequence_number=12345,
        system_snapshot=SystemSnapshot(
            active_tasks=0,
            pending_motions=0,
            in_progress_executions=0,
            legitimacy_band="STABLE",
            component_statuses={},
            captured_at=datetime.now(timezone.utc),
        ),
        interrupted_work_ids=[],
        reason="Planned shutdown",
    )


@pytest.fixture
def cessation_port(cessation_record: CessationRecord) -> MockCessationRecordPort:
    """Create mock cessation port with valid record."""
    return MockCessationRecordPort(record=cessation_record)


@pytest.fixture
def reconstitution_port() -> MockReconstitutionPort:
    """Create mock reconstitution port."""
    return MockReconstitutionPort()


@pytest.fixture
def event_emitter() -> MockEventEmitter:
    """Create mock event emitter."""
    return MockEventEmitter()


@pytest.fixture
def time_authority() -> MockTimeAuthority:
    """Create mock time authority."""
    return MockTimeAuthority()


@pytest.fixture
def validation_service(
    cessation_port: MockCessationRecordPort,
    reconstitution_port: MockReconstitutionPort,
    event_emitter: MockEventEmitter,
    time_authority: MockTimeAuthority,
) -> ReconstitutionValidationService:
    """Create validation service with mocks."""
    return ReconstitutionValidationService(
        reconstitution_port=reconstitution_port,
        cessation_port=cessation_port,
        event_emitter=event_emitter,
        time_authority=time_authority,
    )


@pytest.fixture
def valid_artifact(cessation_record: CessationRecord) -> ReconstitutionArtifact:
    """Create a valid reconstitution artifact."""
    return ReconstitutionArtifact(
        artifact_id=uuid4(),
        cessation_record_id=cessation_record.record_id,
        proposed_legitimacy_band="STABLE",  # Required baseline
        claims_continuity=False,  # Required
        proposed_at=datetime.now(timezone.utc),
        proposer_id=uuid4(),
    )


class TestValidArtifactAccepted:
    """Tests for valid artifact acceptance (AC1, AC6, AC7)."""

    @pytest.mark.asyncio
    async def test_valid_artifact_is_accepted(
        self,
        validation_service: ReconstitutionValidationService,
        valid_artifact: ReconstitutionArtifact,
    ) -> None:
        """Valid artifact passes validation (AC1)."""
        result = await validation_service.validate_artifact(artifact=valid_artifact)

        assert result.status == ValidationStatus.VALID
        assert len(result.rejection_reasons) == 0
        assert len(result.rejection_messages) == 0

    @pytest.mark.asyncio
    async def test_valid_artifact_references_cessation(
        self,
        validation_service: ReconstitutionValidationService,
        valid_artifact: ReconstitutionArtifact,
        cessation_record: CessationRecord,
    ) -> None:
        """Valid artifact must reference cessation record (AC7)."""
        result = await validation_service.validate_artifact(artifact=valid_artifact)

        assert result.status == ValidationStatus.VALID
        assert valid_artifact.cessation_record_id == cessation_record.record_id

    @pytest.mark.asyncio
    async def test_valid_artifact_proposes_baseline(
        self,
        validation_service: ReconstitutionValidationService,
        valid_artifact: ReconstitutionArtifact,
    ) -> None:
        """Valid artifact proposes STABLE (baseline) legitimacy (AC4)."""
        result = await validation_service.validate_artifact(artifact=valid_artifact)

        assert result.status == ValidationStatus.VALID
        assert valid_artifact.proposed_legitimacy_band == "STABLE"


class TestContinuityRejection:
    """Tests for continuity claim rejection (AC2)."""

    @pytest.mark.asyncio
    async def test_continuity_claim_is_rejected(
        self,
        validation_service: ReconstitutionValidationService,
        cessation_record: CessationRecord,
    ) -> None:
        """Artifact claiming continuity is rejected (FR54, AC2)."""
        artifact = ReconstitutionArtifact(
            artifact_id=uuid4(),
            cessation_record_id=cessation_record.record_id,
            proposed_legitimacy_band="STABLE",
            claims_continuity=True,  # INVALID
            proposed_at=datetime.now(timezone.utc),
            proposer_id=uuid4(),
        )

        result = await validation_service.validate_artifact(artifact=artifact)

        assert result.status == ValidationStatus.REJECTED
        assert RejectionReason.CONTINUITY_CLAIM in result.rejection_reasons

    @pytest.mark.asyncio
    async def test_continuity_rejection_has_clear_message(
        self,
        validation_service: ReconstitutionValidationService,
        cessation_record: CessationRecord,
    ) -> None:
        """Continuity rejection includes clear message (AC6)."""
        artifact = ReconstitutionArtifact(
            artifact_id=uuid4(),
            cessation_record_id=cessation_record.record_id,
            proposed_legitimacy_band="STABLE",
            claims_continuity=True,
            proposed_at=datetime.now(timezone.utc),
            proposer_id=uuid4(),
        )

        result = await validation_service.validate_artifact(artifact=artifact)

        assert any(
            "cannot claim continuity" in msg.lower()
            for msg in result.rejection_messages
        )


class TestLegitimacyRejection:
    """Tests for legitimacy inheritance rejection (AC3)."""

    @pytest.mark.asyncio
    async def test_non_baseline_legitimacy_is_rejected(
        self,
        validation_service: ReconstitutionValidationService,
        cessation_record: CessationRecord,
    ) -> None:
        """Artifact with non-STABLE legitimacy is rejected (FR55, AC3)."""
        artifact = ReconstitutionArtifact(
            artifact_id=uuid4(),
            cessation_record_id=cessation_record.record_id,
            proposed_legitimacy_band="COMPROMISED",  # INVALID - must be STABLE
            claims_continuity=False,
            proposed_at=datetime.now(timezone.utc),
            proposer_id=uuid4(),
        )

        result = await validation_service.validate_artifact(artifact=artifact)

        assert result.status == ValidationStatus.REJECTED
        assert RejectionReason.LEGITIMACY_INHERITANCE in result.rejection_reasons

    @pytest.mark.asyncio
    async def test_strained_legitimacy_is_rejected(
        self,
        validation_service: ReconstitutionValidationService,
        cessation_record: CessationRecord,
    ) -> None:
        """Even STRAINED is rejected (must be STABLE)."""
        artifact = ReconstitutionArtifact(
            artifact_id=uuid4(),
            cessation_record_id=cessation_record.record_id,
            proposed_legitimacy_band="STRAINED",  # INVALID
            claims_continuity=False,
            proposed_at=datetime.now(timezone.utc),
            proposer_id=uuid4(),
        )

        result = await validation_service.validate_artifact(artifact=artifact)

        assert result.status == ValidationStatus.REJECTED
        assert RejectionReason.LEGITIMACY_INHERITANCE in result.rejection_reasons

    @pytest.mark.asyncio
    async def test_legitimacy_rejection_has_clear_message(
        self,
        validation_service: ReconstitutionValidationService,
        cessation_record: CessationRecord,
    ) -> None:
        """Legitimacy rejection includes clear message (AC6)."""
        artifact = ReconstitutionArtifact(
            artifact_id=uuid4(),
            cessation_record_id=cessation_record.record_id,
            proposed_legitimacy_band="ERODING",
            claims_continuity=False,
            proposed_at=datetime.now(timezone.utc),
            proposer_id=uuid4(),
        )

        result = await validation_service.validate_artifact(artifact=artifact)

        assert any(
            "cannot inherit legitimacy" in msg.lower()
            for msg in result.rejection_messages
        )


class TestMissingCessationReference:
    """Tests for missing cessation reference rejection."""

    @pytest.mark.asyncio
    async def test_missing_cessation_reference_is_rejected(
        self,
        validation_service: ReconstitutionValidationService,
    ) -> None:
        """Artifact without cessation reference is rejected."""
        artifact = ReconstitutionArtifact(
            artifact_id=uuid4(),
            cessation_record_id=None,  # MISSING
            proposed_legitimacy_band="STABLE",
            claims_continuity=False,
            proposed_at=datetime.now(timezone.utc),
            proposer_id=uuid4(),
        )

        result = await validation_service.validate_artifact(artifact=artifact)

        assert result.status == ValidationStatus.REJECTED
        assert RejectionReason.MISSING_CESSATION_REFERENCE in result.rejection_reasons

    @pytest.mark.asyncio
    async def test_invalid_cessation_reference_is_rejected(
        self,
        validation_service: ReconstitutionValidationService,
    ) -> None:
        """Artifact with invalid cessation reference is rejected."""
        artifact = ReconstitutionArtifact(
            artifact_id=uuid4(),
            cessation_record_id=uuid4(),  # Non-existent record
            proposed_legitimacy_band="STABLE",
            claims_continuity=False,
            proposed_at=datetime.now(timezone.utc),
            proposer_id=uuid4(),
        )

        result = await validation_service.validate_artifact(artifact=artifact)

        assert result.status == ValidationStatus.REJECTED
        assert RejectionReason.MISSING_CESSATION_REFERENCE in result.rejection_reasons

    @pytest.mark.asyncio
    async def test_missing_reference_has_clear_message(
        self,
        validation_service: ReconstitutionValidationService,
    ) -> None:
        """Missing reference rejection includes clear message (AC6)."""
        artifact = ReconstitutionArtifact(
            artifact_id=uuid4(),
            cessation_record_id=None,
            proposed_legitimacy_band="STABLE",
            claims_continuity=False,
            proposed_at=datetime.now(timezone.utc),
            proposer_id=uuid4(),
        )

        result = await validation_service.validate_artifact(artifact=artifact)

        assert any(
            "cessation record" in msg.lower() or "cessation reference" in msg.lower()
            for msg in result.rejection_messages
        )


class TestMultipleRejections:
    """Tests for artifacts with multiple violations."""

    @pytest.mark.asyncio
    async def test_multiple_violations_all_reported(
        self,
        validation_service: ReconstitutionValidationService,
    ) -> None:
        """All violations are reported, not just the first."""
        artifact = ReconstitutionArtifact(
            artifact_id=uuid4(),
            cessation_record_id=None,  # INVALID 1
            proposed_legitimacy_band="FAILED",  # INVALID 2
            claims_continuity=True,  # INVALID 3
            proposed_at=datetime.now(timezone.utc),
            proposer_id=uuid4(),
        )

        result = await validation_service.validate_artifact(artifact=artifact)

        assert result.status == ValidationStatus.REJECTED
        assert len(result.rejection_reasons) == 3
        assert RejectionReason.CONTINUITY_CLAIM in result.rejection_reasons
        assert RejectionReason.LEGITIMACY_INHERITANCE in result.rejection_reasons
        assert RejectionReason.MISSING_CESSATION_REFERENCE in result.rejection_reasons


class TestEventEmission:
    """Tests for two-phase event emission (AC5)."""

    @pytest.mark.asyncio
    async def test_validated_event_emitted_on_success(
        self,
        validation_service: ReconstitutionValidationService,
        valid_artifact: ReconstitutionArtifact,
        event_emitter: MockEventEmitter,
    ) -> None:
        """Validated event is emitted on success (AC5)."""
        await validation_service.validate_artifact(artifact=valid_artifact)

        assert len(event_emitter.emitted_commits) == 1
        commit = event_emitter.emitted_commits[0]
        assert "validated" in event_emitter.emitted_intents[0]["operation_type"]

    @pytest.mark.asyncio
    async def test_rejected_event_emitted_on_failure(
        self,
        validation_service: ReconstitutionValidationService,
        cessation_record: CessationRecord,
        event_emitter: MockEventEmitter,
    ) -> None:
        """Rejected event is emitted on failure (AC5)."""
        artifact = ReconstitutionArtifact(
            artifact_id=uuid4(),
            cessation_record_id=cessation_record.record_id,
            proposed_legitimacy_band="STABLE",
            claims_continuity=True,  # INVALID
            proposed_at=datetime.now(timezone.utc),
            proposer_id=uuid4(),
        )

        await validation_service.validate_artifact(artifact=artifact)

        # Rejection still emits commit (successful rejection)
        assert len(event_emitter.emitted_commits) == 1

    @pytest.mark.asyncio
    async def test_event_includes_artifact_id(
        self,
        validation_service: ReconstitutionValidationService,
        valid_artifact: ReconstitutionArtifact,
        event_emitter: MockEventEmitter,
    ) -> None:
        """Event payload includes artifact ID."""
        await validation_service.validate_artifact(artifact=valid_artifact)

        intent = event_emitter.emitted_intents[0]
        assert "artifact_id" in intent["payload"]


class TestResultPersistence:
    """Tests for validation result persistence."""

    @pytest.mark.asyncio
    async def test_validation_result_is_stored(
        self,
        validation_service: ReconstitutionValidationService,
        valid_artifact: ReconstitutionArtifact,
        reconstitution_port: MockReconstitutionPort,
    ) -> None:
        """Validation result is stored in port."""
        result = await validation_service.validate_artifact(artifact=valid_artifact)

        stored = await reconstitution_port.get_validation_result(valid_artifact.artifact_id)
        assert stored is not None
        assert stored.artifact_id == valid_artifact.artifact_id
        assert stored.status == result.status


class TestBaselineLegitimacyConstant:
    """Tests for baseline legitimacy constant."""

    def test_baseline_is_stable(self) -> None:
        """Baseline legitimacy band is STABLE."""
        assert BASELINE_LEGITIMACY_BAND == "STABLE"


class TestRejectionMessagesConstant:
    """Tests for rejection messages dictionary."""

    def test_continuity_message_is_clear(self) -> None:
        """Continuity rejection message is human-readable."""
        msg = REJECTION_MESSAGES[RejectionReason.CONTINUITY_CLAIM]
        assert "continuity" in msg.lower()
        assert len(msg) > 20  # Substantive message

    def test_legitimacy_message_is_clear(self) -> None:
        """Legitimacy rejection message is human-readable."""
        msg = REJECTION_MESSAGES[RejectionReason.LEGITIMACY_INHERITANCE]
        assert "legitimacy" in msg.lower()
        assert len(msg) > 20

    def test_missing_cessation_message_is_clear(self) -> None:
        """Missing cessation message is human-readable."""
        msg = REJECTION_MESSAGES[RejectionReason.MISSING_CESSATION_REFERENCE]
        assert "cessation" in msg.lower()
        assert len(msg) > 20

    def test_invalid_structure_message_is_clear(self) -> None:
        """Invalid structure message is human-readable."""
        msg = REJECTION_MESSAGES[RejectionReason.INVALID_ARTIFACT_STRUCTURE]
        assert "invalid" in msg.lower() or "structure" in msg.lower()
        assert len(msg) > 20
