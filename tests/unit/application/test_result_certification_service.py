"""Unit tests for ResultCertificationService application service (Story 2.8, FR99-FR101, FR141-FR142).

Tests the application service that orchestrates result certification and procedural record generation.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import pytest

from src.application.ports.procedural_record_generator import ProceduralRecordData
from src.application.ports.result_certifier import CertificationResult
from src.application.services.result_certification_service import (
    CertifyResultInput,
    CertifyResultOutput,
    ResultCertificationService,
)
from src.domain.errors.writer import SystemHaltedError


class MockHaltChecker:
    """Mock halt checker for testing."""

    def __init__(self, halted: bool = False) -> None:
        self._halted = halted

    async def is_halted(self) -> bool:
        return self._halted

    def set_halted(self, halted: bool) -> None:
        self._halted = halted


class MockResultCertifier:
    """Mock result certifier for testing."""

    def __init__(self) -> None:
        self._certifications: dict[str, CertificationResult] = {}
        self._hashes: dict[str, str] = {}

    async def certify_result(
        self,
        deliberation_id: Any,
        result_content: dict[str, Any],
    ) -> CertificationResult:
        result_id = uuid4()
        result = CertificationResult(
            certified=True,
            result_id=result_id,
            certification_signature="mock_sig_" + str(result_id)[:8],
            certification_key_id="CERT:mock-key",
            certification_timestamp=datetime.now(timezone.utc),
        )
        self._certifications[str(result_id)] = result
        self._hashes[str(result_id)] = "a" * 64
        return result

    async def verify_certification(
        self,
        result_id: Any,
        signature: str,
    ) -> bool:
        cert = self._certifications.get(str(result_id))
        if cert is None:
            return False
        return cert.certification_signature == signature

    async def get_certification(
        self,
        result_id: Any,
    ) -> CertificationResult | None:
        return self._certifications.get(str(result_id))

    async def compute_result_hash(
        self,
        result_content: dict[str, Any],
    ) -> str:
        return "a" * 64


class MockProceduralRecordGenerator:
    """Mock procedural record generator for testing."""

    def __init__(self) -> None:
        self._records: dict[str, ProceduralRecordData] = {}

    async def generate_record(
        self,
        deliberation_id: Any,
    ) -> ProceduralRecordData:
        record_id = uuid4()
        data = ProceduralRecordData(
            record_id=record_id,
            deliberation_id=deliberation_id,
            agenda_items=["Mock Agenda"],
            participant_ids=["mock-agent"],
            vote_summary={"aye": 10},
            timeline_events=[],
            decisions=["Mock Decision"],
            record_hash="b" * 64,
            signature="mock_record_sig",
        )
        self._records[str(record_id)] = data
        return data

    async def get_record(
        self,
        record_id: Any,
    ) -> ProceduralRecordData | None:
        return self._records.get(str(record_id))

    async def verify_record(
        self,
        record_id: Any,
    ) -> bool:
        return str(record_id) in self._records


class TestResultCertificationServiceInit:
    """Tests for ResultCertificationService initialization."""

    def test_init_with_all_dependencies(self) -> None:
        """Should initialize with all required dependencies."""
        halt_checker = MockHaltChecker()
        certifier = MockResultCertifier()
        record_generator = MockProceduralRecordGenerator()

        service = ResultCertificationService(
            halt_checker=halt_checker,
            certifier=certifier,
            record_generator=record_generator,
        )

        assert service._halt_checker is halt_checker
        assert service._certifier is certifier
        assert service._record_generator is record_generator

    def test_init_raises_for_none_halt_checker(self) -> None:
        """Should raise TypeError if halt_checker is None."""
        with pytest.raises(TypeError, match="halt_checker is required"):
            ResultCertificationService(
                halt_checker=None,  # type: ignore[arg-type]
                certifier=MockResultCertifier(),
                record_generator=MockProceduralRecordGenerator(),
            )

    def test_init_raises_for_none_certifier(self) -> None:
        """Should raise TypeError if certifier is None."""
        with pytest.raises(TypeError, match="certifier is required"):
            ResultCertificationService(
                halt_checker=MockHaltChecker(),
                certifier=None,  # type: ignore[arg-type]
                record_generator=MockProceduralRecordGenerator(),
            )

    def test_init_raises_for_none_record_generator(self) -> None:
        """Should raise TypeError if record_generator is None."""
        with pytest.raises(TypeError, match="record_generator is required"):
            ResultCertificationService(
                halt_checker=MockHaltChecker(),
                certifier=MockResultCertifier(),
                record_generator=None,  # type: ignore[arg-type]
            )


class TestResultCertificationServiceCertifyDeliberationResult:
    """Tests for ResultCertificationService.certify_deliberation_result()."""

    @pytest.mark.asyncio
    async def test_certify_result_returns_output(self) -> None:
        """certify_deliberation_result should return CertifyResultOutput."""
        service = ResultCertificationService(
            halt_checker=MockHaltChecker(),
            certifier=MockResultCertifier(),
            record_generator=MockProceduralRecordGenerator(),
        )

        input_data = CertifyResultInput(
            deliberation_id=uuid4(),
            result_content={"decision": "approved"},
            participant_count=72,
            result_type="vote",
        )

        result = await service.certify_deliberation_result(input_data)

        assert isinstance(result, CertifyResultOutput)
        assert result.certification is not None
        assert result.certification.certified is True

    @pytest.mark.asyncio
    async def test_certify_result_raises_when_halted(self) -> None:
        """certify_deliberation_result should raise SystemHaltedError when halted."""
        halt_checker = MockHaltChecker(halted=True)
        service = ResultCertificationService(
            halt_checker=halt_checker,
            certifier=MockResultCertifier(),
            record_generator=MockProceduralRecordGenerator(),
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
    async def test_certify_result_includes_result_hash(self) -> None:
        """Certification should include result_hash."""
        service = ResultCertificationService(
            halt_checker=MockHaltChecker(),
            certifier=MockResultCertifier(),
            record_generator=MockProceduralRecordGenerator(),
        )

        input_data = CertifyResultInput(
            deliberation_id=uuid4(),
            result_content={"decision": "approved"},
            participant_count=72,
            result_type="vote",
        )

        result = await service.certify_deliberation_result(input_data)

        assert result.result_hash is not None
        assert len(result.result_hash) == 64


class TestResultCertificationServiceVerifyResultCertification:
    """Tests for ResultCertificationService.verify_result_certification()."""

    @pytest.mark.asyncio
    async def test_verify_returns_true_for_valid(self) -> None:
        """verify_result_certification should return True for valid certification."""
        service = ResultCertificationService(
            halt_checker=MockHaltChecker(),
            certifier=MockResultCertifier(),
            record_generator=MockProceduralRecordGenerator(),
        )

        # First certify
        input_data = CertifyResultInput(
            deliberation_id=uuid4(),
            result_content={"decision": "approved"},
            participant_count=72,
            result_type="vote",
        )
        cert_result = await service.certify_deliberation_result(input_data)

        # Then verify
        is_valid = await service.verify_result_certification(
            result_id=cert_result.certification.result_id,
            signature=cert_result.certification.certification_signature,
        )

        assert is_valid is True

    @pytest.mark.asyncio
    async def test_verify_returns_false_for_invalid(self) -> None:
        """verify_result_certification should return False for invalid signature."""
        service = ResultCertificationService(
            halt_checker=MockHaltChecker(),
            certifier=MockResultCertifier(),
            record_generator=MockProceduralRecordGenerator(),
        )

        # First certify
        input_data = CertifyResultInput(
            deliberation_id=uuid4(),
            result_content={"decision": "approved"},
            participant_count=72,
            result_type="vote",
        )
        cert_result = await service.certify_deliberation_result(input_data)

        # Then verify with wrong signature
        is_valid = await service.verify_result_certification(
            result_id=cert_result.certification.result_id,
            signature="wrong_signature",
        )

        assert is_valid is False

    @pytest.mark.asyncio
    async def test_verify_raises_when_halted(self) -> None:
        """verify_result_certification should raise SystemHaltedError when halted."""
        halt_checker = MockHaltChecker(halted=True)
        service = ResultCertificationService(
            halt_checker=halt_checker,
            certifier=MockResultCertifier(),
            record_generator=MockProceduralRecordGenerator(),
        )

        with pytest.raises(SystemHaltedError):
            await service.verify_result_certification(
                result_id=uuid4(),
                signature="some_signature",
            )


class TestResultCertificationServiceGenerateProceduralRecord:
    """Tests for ResultCertificationService.generate_procedural_record()."""

    @pytest.mark.asyncio
    async def test_generate_record_returns_data(self) -> None:
        """generate_procedural_record should return ProceduralRecordData."""
        service = ResultCertificationService(
            halt_checker=MockHaltChecker(),
            certifier=MockResultCertifier(),
            record_generator=MockProceduralRecordGenerator(),
        )

        result = await service.generate_procedural_record(
            deliberation_id=uuid4(),
        )

        assert isinstance(result, ProceduralRecordData)
        assert result.record_hash is not None

    @pytest.mark.asyncio
    async def test_generate_record_raises_when_halted(self) -> None:
        """generate_procedural_record should raise SystemHaltedError when halted."""
        halt_checker = MockHaltChecker(halted=True)
        service = ResultCertificationService(
            halt_checker=halt_checker,
            certifier=MockResultCertifier(),
            record_generator=MockProceduralRecordGenerator(),
        )

        with pytest.raises(SystemHaltedError):
            await service.generate_procedural_record(deliberation_id=uuid4())


class TestResultCertificationServiceVerifyProceduralRecord:
    """Tests for ResultCertificationService.verify_procedural_record()."""

    @pytest.mark.asyncio
    async def test_verify_record_returns_true_for_valid(self) -> None:
        """verify_procedural_record should return True for valid record."""
        service = ResultCertificationService(
            halt_checker=MockHaltChecker(),
            certifier=MockResultCertifier(),
            record_generator=MockProceduralRecordGenerator(),
        )

        # First generate
        record = await service.generate_procedural_record(
            deliberation_id=uuid4(),
        )

        # Then verify
        is_valid = await service.verify_procedural_record(
            record_id=record.record_id,
        )

        assert is_valid is True

    @pytest.mark.asyncio
    async def test_verify_record_returns_false_for_unknown(self) -> None:
        """verify_procedural_record should return False for unknown record."""
        service = ResultCertificationService(
            halt_checker=MockHaltChecker(),
            certifier=MockResultCertifier(),
            record_generator=MockProceduralRecordGenerator(),
        )

        is_valid = await service.verify_procedural_record(
            record_id=uuid4(),
        )

        assert is_valid is False

    @pytest.mark.asyncio
    async def test_verify_record_raises_when_halted(self) -> None:
        """verify_procedural_record should raise SystemHaltedError when halted."""
        halt_checker = MockHaltChecker(halted=True)
        service = ResultCertificationService(
            halt_checker=halt_checker,
            certifier=MockResultCertifier(),
            record_generator=MockProceduralRecordGenerator(),
        )

        with pytest.raises(SystemHaltedError):
            await service.verify_procedural_record(record_id=uuid4())


class TestResultCertificationServiceGetCertification:
    """Tests for ResultCertificationService.get_certification()."""

    @pytest.mark.asyncio
    async def test_get_certification_returns_stored(self) -> None:
        """get_certification should return stored certification."""
        service = ResultCertificationService(
            halt_checker=MockHaltChecker(),
            certifier=MockResultCertifier(),
            record_generator=MockProceduralRecordGenerator(),
        )

        # First certify
        input_data = CertifyResultInput(
            deliberation_id=uuid4(),
            result_content={"decision": "approved"},
            participant_count=72,
            result_type="vote",
        )
        cert_result = await service.certify_deliberation_result(input_data)

        # Then retrieve
        cert = await service.get_certification(cert_result.certification.result_id)

        assert cert is not None
        assert cert.result_id == cert_result.certification.result_id

    @pytest.mark.asyncio
    async def test_get_certification_returns_none_for_unknown(self) -> None:
        """get_certification should return None for unknown result."""
        service = ResultCertificationService(
            halt_checker=MockHaltChecker(),
            certifier=MockResultCertifier(),
            record_generator=MockProceduralRecordGenerator(),
        )

        cert = await service.get_certification(uuid4())

        assert cert is None
