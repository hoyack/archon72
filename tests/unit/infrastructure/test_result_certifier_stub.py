"""Unit tests for ResultCertifierStub infrastructure (Story 2.8, FR99-FR101).

Tests the in-memory stub implementation of ResultCertifierPort.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.application.ports.result_certifier import CertificationResult
from src.infrastructure.stubs.result_certifier_stub import (
    DEV_MODE_WATERMARK,
    ResultCertifierStub,
)


class TestDevModeWatermark:
    """Tests for DEV_MODE_WATERMARK constant."""

    def test_watermark_contains_stub_name(self) -> None:
        """Watermark should contain stub name."""
        assert "ResultCertifierStub" in DEV_MODE_WATERMARK

    def test_watermark_indicates_dev(self) -> None:
        """Watermark should indicate development mode."""
        assert "DEV" in DEV_MODE_WATERMARK


class TestResultCertifierStubInit:
    """Tests for ResultCertifierStub initialization."""

    def test_init_creates_empty_store(self) -> None:
        """Initialize should create empty certification store."""
        stub = ResultCertifierStub()
        assert stub._certifications == {}

    def test_init_with_halt_checker(self) -> None:
        """Initialize should accept optional halt checker."""
        stub = ResultCertifierStub()
        assert stub._halt_checker is None


class TestResultCertifierStubCertifyResult:
    """Tests for ResultCertifierStub.certify_result()."""

    @pytest.mark.asyncio
    async def test_certify_result_returns_certification_result(self) -> None:
        """certify_result should return CertificationResult."""
        stub = ResultCertifierStub()
        result = await stub.certify_result(
            deliberation_id=uuid4(),
            result_content={"decision": "approved", "votes": {"aye": 45}},
        )

        assert isinstance(result, CertificationResult)
        assert result.certified is True

    @pytest.mark.asyncio
    async def test_certify_result_generates_unique_ids(self) -> None:
        """Each certification should have unique result_id."""
        stub = ResultCertifierStub()

        result1 = await stub.certify_result(
            deliberation_id=uuid4(),
            result_content={"decision": "a"},
        )
        result2 = await stub.certify_result(
            deliberation_id=uuid4(),
            result_content={"decision": "b"},
        )

        assert result1.result_id != result2.result_id

    @pytest.mark.asyncio
    async def test_certify_result_stores_certification(self) -> None:
        """certify_result should store certification for later retrieval."""
        stub = ResultCertifierStub()
        result = await stub.certify_result(
            deliberation_id=uuid4(),
            result_content={"decision": "approved"},
        )

        retrieved = await stub.get_certification(result.result_id)
        assert retrieved is not None
        assert retrieved.result_id == result.result_id

    @pytest.mark.asyncio
    async def test_certify_result_includes_key_id(self) -> None:
        """Certification should include key ID."""
        stub = ResultCertifierStub()
        result = await stub.certify_result(
            deliberation_id=uuid4(),
            result_content={"decision": "approved"},
        )

        assert result.certification_key_id != ""
        assert "CERT:" in result.certification_key_id

    @pytest.mark.asyncio
    async def test_certify_result_includes_timestamp(self) -> None:
        """Certification should include timestamp."""
        stub = ResultCertifierStub()
        before = datetime.now(timezone.utc)

        result = await stub.certify_result(
            deliberation_id=uuid4(),
            result_content={"decision": "approved"},
        )

        after = datetime.now(timezone.utc)
        assert before <= result.certification_timestamp <= after


class TestResultCertifierStubVerifyCertification:
    """Tests for ResultCertifierStub.verify_certification()."""

    @pytest.mark.asyncio
    async def test_verify_certification_with_valid_signature(self) -> None:
        """verify_certification should return True for valid signature."""
        stub = ResultCertifierStub()
        cert = await stub.certify_result(
            deliberation_id=uuid4(),
            result_content={"decision": "approved"},
        )

        is_valid = await stub.verify_certification(
            result_id=cert.result_id,
            signature=cert.certification_signature,
        )

        assert is_valid is True

    @pytest.mark.asyncio
    async def test_verify_certification_with_invalid_signature(self) -> None:
        """verify_certification should return False for invalid signature."""
        stub = ResultCertifierStub()
        cert = await stub.certify_result(
            deliberation_id=uuid4(),
            result_content={"decision": "approved"},
        )

        is_valid = await stub.verify_certification(
            result_id=cert.result_id,
            signature="wrong_signature",
        )

        assert is_valid is False

    @pytest.mark.asyncio
    async def test_verify_certification_with_unknown_result(self) -> None:
        """verify_certification should return False for unknown result."""
        stub = ResultCertifierStub()

        is_valid = await stub.verify_certification(
            result_id=uuid4(),
            signature="some_signature",
        )

        assert is_valid is False


class TestResultCertifierStubGetCertification:
    """Tests for ResultCertifierStub.get_certification()."""

    @pytest.mark.asyncio
    async def test_get_certification_returns_stored(self) -> None:
        """get_certification should return stored certification."""
        stub = ResultCertifierStub()
        cert = await stub.certify_result(
            deliberation_id=uuid4(),
            result_content={"decision": "approved"},
        )

        retrieved = await stub.get_certification(cert.result_id)

        assert retrieved is not None
        assert retrieved == cert

    @pytest.mark.asyncio
    async def test_get_certification_returns_none_for_unknown(self) -> None:
        """get_certification should return None for unknown result."""
        stub = ResultCertifierStub()

        retrieved = await stub.get_certification(uuid4())

        assert retrieved is None


class TestResultCertifierStubGetCertificationByDeliberation:
    """Tests for ResultCertifierStub.get_certification_by_deliberation()."""

    @pytest.mark.asyncio
    async def test_get_certification_by_deliberation_returns_stored(self) -> None:
        """get_certification_by_deliberation should return stored certification."""
        stub = ResultCertifierStub()
        deliberation_id = uuid4()
        cert = await stub.certify_result(
            deliberation_id=deliberation_id,
            result_content={"decision": "approved"},
        )

        retrieved = await stub.get_certification_by_deliberation(deliberation_id)

        assert retrieved is not None
        assert retrieved == cert

    @pytest.mark.asyncio
    async def test_get_certification_by_deliberation_returns_none_for_unknown(
        self,
    ) -> None:
        """get_certification_by_deliberation should return None for unknown deliberation."""
        stub = ResultCertifierStub()

        retrieved = await stub.get_certification_by_deliberation(uuid4())

        assert retrieved is None

    @pytest.mark.asyncio
    async def test_get_certification_by_deliberation_finds_correct_cert(self) -> None:
        """get_certification_by_deliberation should find correct cert among multiple."""
        stub = ResultCertifierStub()

        deliberation_id_1 = uuid4()
        deliberation_id_2 = uuid4()

        cert1 = await stub.certify_result(
            deliberation_id=deliberation_id_1,
            result_content={"decision": "a"},
        )
        cert2 = await stub.certify_result(
            deliberation_id=deliberation_id_2,
            result_content={"decision": "b"},
        )

        retrieved1 = await stub.get_certification_by_deliberation(deliberation_id_1)
        retrieved2 = await stub.get_certification_by_deliberation(deliberation_id_2)

        assert retrieved1 == cert1
        assert retrieved2 == cert2
        assert retrieved1 != retrieved2


class TestResultCertifierStubComputeResultHash:
    """Tests for ResultCertifierStub.compute_result_hash()."""

    @pytest.mark.asyncio
    async def test_compute_result_hash_returns_64_chars(self) -> None:
        """compute_result_hash should return 64 character hex string."""
        stub = ResultCertifierStub()

        hash_value = await stub.compute_result_hash(
            result_content={"decision": "approved"},
        )

        assert len(hash_value) == 64
        # Verify it's valid hex
        int(hash_value, 16)

    @pytest.mark.asyncio
    async def test_compute_result_hash_is_deterministic(self) -> None:
        """Same content should produce same hash."""
        stub = ResultCertifierStub()
        content = {"decision": "approved", "votes": {"aye": 45}}

        hash1 = await stub.compute_result_hash(result_content=content)
        hash2 = await stub.compute_result_hash(result_content=content)

        assert hash1 == hash2

    @pytest.mark.asyncio
    async def test_compute_result_hash_different_for_different_content(self) -> None:
        """Different content should produce different hashes."""
        stub = ResultCertifierStub()

        hash1 = await stub.compute_result_hash(
            result_content={"decision": "approved"},
        )
        hash2 = await stub.compute_result_hash(
            result_content={"decision": "rejected"},
        )

        assert hash1 != hash2
