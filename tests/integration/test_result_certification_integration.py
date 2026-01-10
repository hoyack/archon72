"""Integration tests for Result Certification (Story 2.8, FR99-FR101, FR141-FR142).

End-to-end integration tests for the result certification system.
Tests the full flow from certification to verification.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.application.services.result_certification_service import (
    CertifyResultInput,
    ResultCertificationService,
)
from src.domain.errors.writer import SystemHaltedError
from src.domain.events.certified_result import (
    CERTIFIED_RESULT_EVENT_TYPE,
    CertifiedResultPayload,
)
from src.domain.events.procedural_record import (
    PROCEDURAL_RECORD_EVENT_TYPE,
)
from src.infrastructure.stubs.halt_checker_stub import HaltCheckerStub
from src.infrastructure.stubs.procedural_record_generator_stub import (
    ProceduralRecordGeneratorStub,
)
from src.infrastructure.stubs.result_certifier_stub import ResultCertifierStub


class TestResultCertificationIntegration:
    """Integration tests for FR99-FR101: Result Certification."""

    @pytest.fixture
    def service(self) -> ResultCertificationService:
        """Create service with real stubs."""
        return ResultCertificationService(
            halt_checker=HaltCheckerStub(),
            certifier=ResultCertifierStub(),
            record_generator=ProceduralRecordGeneratorStub(),
        )

    @pytest.mark.asyncio
    async def test_ac1_certified_result_event_created_when_deliberation_concludes(
        self,
        service: ResultCertificationService,
    ) -> None:
        """AC1: CertifiedResultEvent is created when deliberation concludes."""
        # Given a deliberation concludes
        deliberation_id = uuid4()
        result_content = {
            "outcome": "approved",
            "motion_id": str(uuid4()),
            "vote_counts": {"aye": 45, "nay": 20, "abstain": 7},
        }

        # When the result is final
        input_data = CertifyResultInput(
            deliberation_id=deliberation_id,
            result_content=result_content,
            participant_count=72,
            result_type="vote",
        )
        output = await service.certify_deliberation_result(input_data)

        # Then a CertifiedResultEvent is created
        assert output.certification is not None
        assert output.certification.certified is True
        assert output.certification.result_id is not None

    @pytest.mark.asyncio
    async def test_ac1_certification_signed_by_system_key(
        self,
        service: ResultCertificationService,
    ) -> None:
        """AC1: Certification is signed by the system's certification key."""
        input_data = CertifyResultInput(
            deliberation_id=uuid4(),
            result_content={"decision": "approved"},
            participant_count=72,
            result_type="vote",
        )
        output = await service.certify_deliberation_result(input_data)

        # Should have certification key ID
        assert output.certification.certification_key_id != ""
        assert "CERT:" in output.certification.certification_key_id

    @pytest.mark.asyncio
    async def test_ac1_certification_includes_required_fields(
        self,
        service: ResultCertificationService,
    ) -> None:
        """AC1: Certification includes result_hash, participant_count, certification_timestamp."""
        input_data = CertifyResultInput(
            deliberation_id=uuid4(),
            result_content={"decision": "approved"},
            participant_count=72,
            result_type="vote",
        )
        output = await service.certify_deliberation_result(input_data)

        # result_hash
        assert output.result_hash is not None
        assert len(output.result_hash) == 64

        # certification_timestamp
        assert output.certification.certification_timestamp is not None
        assert isinstance(output.certification.certification_timestamp, datetime)

    @pytest.mark.asyncio
    async def test_ac2_certification_signature_can_be_verified(
        self,
        service: ResultCertificationService,
    ) -> None:
        """AC2: Certification signature can be verified."""
        # Given a certified result
        input_data = CertifyResultInput(
            deliberation_id=uuid4(),
            result_content={"decision": "approved"},
            participant_count=72,
            result_type="vote",
        )
        output = await service.certify_deliberation_result(input_data)

        # When I query it
        is_valid = await service.verify_result_certification(
            result_id=output.certification.result_id,
            signature=output.certification.certification_signature,
        )

        # Then the certification signature can be verified
        assert is_valid is True

    @pytest.mark.asyncio
    async def test_ac2_result_content_matches_result_hash(
        self,
    ) -> None:
        """AC2: Result content matches the result_hash."""
        certifier = ResultCertifierStub()
        result_content = {"decision": "approved", "votes": {"aye": 45}}

        # Compute hash
        hash1 = await certifier.compute_result_hash(result_content)

        # Same content should produce same hash
        hash2 = await certifier.compute_result_hash(result_content)

        assert hash1 == hash2
        assert len(hash1) == 64

    @pytest.mark.asyncio
    async def test_hash_mismatch_detected_for_different_content(
        self,
    ) -> None:
        """Hash mismatch detected when content differs."""
        certifier = ResultCertifierStub()

        hash1 = await certifier.compute_result_hash({"decision": "approved"})
        hash2 = await certifier.compute_result_hash({"decision": "rejected"})

        assert hash1 != hash2


class TestProceduralRecordIntegration:
    """Integration tests for FR141-FR142: Procedural Records."""

    @pytest.fixture
    def service(self) -> ResultCertificationService:
        """Create service with real stubs."""
        return ResultCertificationService(
            halt_checker=HaltCheckerStub(),
            certifier=ResultCertifierStub(),
            record_generator=ProceduralRecordGeneratorStub(),
        )

    @pytest.mark.asyncio
    async def test_ac3_procedural_record_generated_on_completion(
        self,
        service: ResultCertificationService,
    ) -> None:
        """AC3: Procedural record is generated when deliberation completes."""
        # Given procedural record generation
        # When a deliberation completes
        deliberation_id = uuid4()

        # Then a procedural record is generated
        record = await service.generate_procedural_record(
            deliberation_id=deliberation_id,
        )

        assert record is not None
        assert record.deliberation_id == deliberation_id

    @pytest.mark.asyncio
    async def test_ac3_procedural_record_includes_required_fields(
        self,
        service: ResultCertificationService,
    ) -> None:
        """AC3: Procedural record includes agenda, participants, votes, timeline, decisions."""
        deliberation_id = uuid4()
        record = await service.generate_procedural_record(
            deliberation_id=deliberation_id,
        )

        # agenda (now tuple per CT-12 immutability)
        assert record.agenda_items is not None
        assert isinstance(record.agenda_items, tuple)

        # participants (now tuple per CT-12 immutability)
        assert record.participant_ids is not None
        assert isinstance(record.participant_ids, tuple)

        # votes (now MappingProxyType per CT-12 immutability)
        assert record.vote_summary is not None
        # MappingProxyType is a Mapping, check for dict-like behavior
        assert hasattr(record.vote_summary, "__getitem__")

        # timeline (now tuple per CT-12 immutability)
        assert record.timeline_events is not None
        assert isinstance(record.timeline_events, tuple)

        # decisions (now tuple per CT-12 immutability)
        assert record.decisions is not None
        assert isinstance(record.decisions, tuple)

    @pytest.mark.asyncio
    async def test_ac3_procedural_record_is_signed(
        self,
        service: ResultCertificationService,
    ) -> None:
        """AC3: Procedural record is signed."""
        deliberation_id = uuid4()
        record = await service.generate_procedural_record(
            deliberation_id=deliberation_id,
        )

        assert record.signature is not None
        assert record.signature != ""

    @pytest.mark.asyncio
    async def test_ac3_procedural_record_can_be_verified(
        self,
        service: ResultCertificationService,
    ) -> None:
        """AC3: Procedural record signature can be verified."""
        deliberation_id = uuid4()
        record = await service.generate_procedural_record(
            deliberation_id=deliberation_id,
        )

        is_valid = await service.verify_procedural_record(
            record_id=record.record_id,
        )

        assert is_valid is True


class TestHaltStateBlocking:
    """Integration tests for HALT state blocking certification operations."""

    @pytest.mark.asyncio
    async def test_halt_state_blocks_certification(self) -> None:
        """HALT state blocks certification operations."""
        halt_checker = HaltCheckerStub(force_halted=True)
        service = ResultCertificationService(
            halt_checker=halt_checker,
            certifier=ResultCertifierStub(),
            record_generator=ProceduralRecordGeneratorStub(),
        )

        input_data = CertifyResultInput(
            deliberation_id=uuid4(),
            result_content={"decision": "approved"},
            participant_count=72,
            result_type="vote",
        )

        with pytest.raises(SystemHaltedError):
            await service.certify_deliberation_result(input_data)

    @pytest.mark.asyncio
    async def test_halt_state_blocks_verification(self) -> None:
        """HALT state blocks verification operations."""
        halt_checker = HaltCheckerStub(force_halted=True)
        service = ResultCertificationService(
            halt_checker=halt_checker,
            certifier=ResultCertifierStub(),
            record_generator=ProceduralRecordGeneratorStub(),
        )

        with pytest.raises(SystemHaltedError):
            await service.verify_result_certification(
                result_id=uuid4(),
                signature="any",
            )

    @pytest.mark.asyncio
    async def test_halt_state_blocks_procedural_record_generation(self) -> None:
        """HALT state blocks procedural record generation."""
        halt_checker = HaltCheckerStub(force_halted=True)
        service = ResultCertificationService(
            halt_checker=halt_checker,
            certifier=ResultCertifierStub(),
            record_generator=ProceduralRecordGeneratorStub(),
        )

        with pytest.raises(SystemHaltedError):
            await service.generate_procedural_record(deliberation_id=uuid4())

    @pytest.mark.asyncio
    async def test_halt_state_blocks_record_verification(self) -> None:
        """HALT state blocks procedural record verification."""
        halt_checker = HaltCheckerStub(force_halted=True)
        service = ResultCertificationService(
            halt_checker=halt_checker,
            certifier=ResultCertifierStub(),
            record_generator=ProceduralRecordGeneratorStub(),
        )

        with pytest.raises(SystemHaltedError):
            await service.verify_procedural_record(record_id=uuid4())


class TestEndToEndCertificationFlow:
    """End-to-end integration tests for complete certification flow."""

    @pytest.mark.asyncio
    async def test_end_to_end_certification_flow(self) -> None:
        """Complete end-to-end certification flow works correctly."""
        service = ResultCertificationService(
            halt_checker=HaltCheckerStub(),
            certifier=ResultCertifierStub(),
            record_generator=ProceduralRecordGeneratorStub(),
        )

        # 1. Certify a deliberation result
        deliberation_id = uuid4()
        input_data = CertifyResultInput(
            deliberation_id=deliberation_id,
            result_content={
                "outcome": "approved",
                "motion_id": str(uuid4()),
                "vote_counts": {"aye": 45, "nay": 20, "abstain": 7},
            },
            participant_count=72,
            result_type="vote",
        )
        cert_output = await service.certify_deliberation_result(input_data)

        # 2. Verify the certification
        is_valid = await service.verify_result_certification(
            result_id=cert_output.certification.result_id,
            signature=cert_output.certification.certification_signature,
        )
        assert is_valid is True

        # 3. Generate procedural record
        record = await service.generate_procedural_record(
            deliberation_id=deliberation_id,
        )

        # 4. Verify procedural record
        record_valid = await service.verify_procedural_record(
            record_id=record.record_id,
        )
        assert record_valid is True

        # 5. Retrieve certification
        retrieved_cert = await service.get_certification(
            cert_output.certification.result_id,
        )
        assert retrieved_cert is not None
        assert retrieved_cert.result_id == cert_output.certification.result_id

    @pytest.mark.asyncio
    async def test_multiple_deliberations_certified_independently(self) -> None:
        """Multiple deliberations can be certified independently."""
        service = ResultCertificationService(
            halt_checker=HaltCheckerStub(),
            certifier=ResultCertifierStub(),
            record_generator=ProceduralRecordGeneratorStub(),
        )

        # Certify multiple deliberations
        results = []
        for i in range(3):
            input_data = CertifyResultInput(
                deliberation_id=uuid4(),
                result_content={"decision": f"decision_{i}"},
                participant_count=72,
                result_type="vote",
            )
            output = await service.certify_deliberation_result(input_data)
            results.append(output)

        # All should have unique result_ids
        result_ids = [r.certification.result_id for r in results]
        assert len(set(result_ids)) == 3

        # All should be independently verifiable
        for output in results:
            is_valid = await service.verify_result_certification(
                result_id=output.certification.result_id,
                signature=output.certification.certification_signature,
            )
            assert is_valid is True

    @pytest.mark.asyncio
    async def test_invalid_signature_rejected(self) -> None:
        """Invalid certification signatures are rejected."""
        service = ResultCertificationService(
            halt_checker=HaltCheckerStub(),
            certifier=ResultCertifierStub(),
            record_generator=ProceduralRecordGeneratorStub(),
        )

        # Certify a result
        input_data = CertifyResultInput(
            deliberation_id=uuid4(),
            result_content={"decision": "approved"},
            participant_count=72,
            result_type="vote",
        )
        output = await service.certify_deliberation_result(input_data)

        # Try to verify with wrong signature
        is_valid = await service.verify_result_certification(
            result_id=output.certification.result_id,
            signature="completely_wrong_signature",
        )

        assert is_valid is False


class TestDomainEventPayloads:
    """Tests for domain event payloads integration."""

    def test_certified_result_payload_can_be_created(self) -> None:
        """CertifiedResultPayload can be created with valid data."""
        payload = CertifiedResultPayload(
            result_id=uuid4(),
            deliberation_id=uuid4(),
            result_hash="a" * 64,
            participant_count=72,
            certification_timestamp=datetime.now(timezone.utc),
            certification_key_id="CERT:key-001",
            result_type="vote",
        )

        assert payload.participant_count == 72
        assert payload.result_type == "vote"

    def test_certified_result_event_type_is_correct(self) -> None:
        """CERTIFIED_RESULT_EVENT_TYPE has correct value."""
        assert CERTIFIED_RESULT_EVENT_TYPE == "deliberation.result.certified"

    def test_procedural_record_event_type_is_correct(self) -> None:
        """PROCEDURAL_RECORD_EVENT_TYPE has correct value."""
        assert PROCEDURAL_RECORD_EVENT_TYPE == "deliberation.record.procedural"
