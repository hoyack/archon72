"""Unit tests for ResultCertifierPort interface (Story 2.8, FR99-FR101).

Tests the port interface and CertificationResult dataclass.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

import pytest

from src.application.ports.result_certifier import (
    CertificationResult,
    ResultCertifierPort,
)


class TestCertificationResult:
    """Tests for CertificationResult dataclass."""

    def test_create_valid_result(self) -> None:
        """Should create a valid CertificationResult with all fields."""
        result_id = uuid4()
        certification_timestamp = datetime.now(timezone.utc)

        result = CertificationResult(
            certified=True,
            result_id=result_id,
            certification_signature="sig123",
            certification_key_id="CERT:key-001",
            certification_timestamp=certification_timestamp,
        )

        assert result.certified is True
        assert result.result_id == result_id
        assert result.certification_signature == "sig123"
        assert result.certification_key_id == "CERT:key-001"
        assert result.certification_timestamp == certification_timestamp

    def test_result_is_frozen(self) -> None:
        """CertificationResult should be immutable (frozen dataclass)."""
        result = CertificationResult(
            certified=True,
            result_id=uuid4(),
            certification_signature="sig123",
            certification_key_id="CERT:key-001",
            certification_timestamp=datetime.now(timezone.utc),
        )

        with pytest.raises(AttributeError):
            result.certified = False  # type: ignore[misc]

    def test_failed_certification_result(self) -> None:
        """Should allow certified=False for failed certifications."""
        result = CertificationResult(
            certified=False,
            result_id=uuid4(),
            certification_signature="",
            certification_key_id="",
            certification_timestamp=datetime.now(timezone.utc),
        )

        assert result.certified is False


class TestResultCertifierPortProtocol:
    """Tests for ResultCertifierPort protocol definition."""

    def test_protocol_has_certify_result_method(self) -> None:
        """Protocol should define certify_result method."""
        assert hasattr(ResultCertifierPort, "certify_result")

    def test_protocol_has_verify_certification_method(self) -> None:
        """Protocol should define verify_certification method."""
        assert hasattr(ResultCertifierPort, "verify_certification")

    def test_protocol_has_get_certification_method(self) -> None:
        """Protocol should define get_certification method."""
        assert hasattr(ResultCertifierPort, "get_certification")

    def test_protocol_has_compute_result_hash_method(self) -> None:
        """Protocol should define compute_result_hash method."""
        assert hasattr(ResultCertifierPort, "compute_result_hash")


class MockResultCertifier:
    """Mock implementation of ResultCertifierPort for testing."""

    def __init__(self) -> None:
        self._certifications: dict[UUID, CertificationResult] = {}

    async def certify_result(
        self,
        deliberation_id: UUID,
        result_content: dict[str, Any],
    ) -> CertificationResult:
        """Mock certification."""
        result_id = uuid4()
        result = CertificationResult(
            certified=True,
            result_id=result_id,
            certification_signature="mock_signature",
            certification_key_id="CERT:mock-key",
            certification_timestamp=datetime.now(timezone.utc),
        )
        self._certifications[result_id] = result
        return result

    async def verify_certification(
        self,
        result_id: UUID,
        signature: str,
    ) -> bool:
        """Mock verification."""
        if result_id in self._certifications:
            return self._certifications[result_id].certification_signature == signature
        return False

    async def get_certification(
        self,
        result_id: UUID,
    ) -> CertificationResult | None:
        """Mock get certification."""
        return self._certifications.get(result_id)

    async def compute_result_hash(
        self,
        result_content: dict[str, Any],
    ) -> str:
        """Mock hash computation."""
        return "a" * 64


class TestMockResultCertifier:
    """Tests that mock implements the protocol correctly."""

    @pytest.mark.asyncio
    async def test_certify_result_returns_certification_result(self) -> None:
        """certify_result should return CertificationResult."""
        certifier = MockResultCertifier()
        result = await certifier.certify_result(
            deliberation_id=uuid4(),
            result_content={"decision": "approved"},
        )

        assert isinstance(result, CertificationResult)
        assert result.certified is True

    @pytest.mark.asyncio
    async def test_verify_certification_with_valid_signature(self) -> None:
        """verify_certification should return True for valid signature."""
        certifier = MockResultCertifier()
        cert_result = await certifier.certify_result(
            deliberation_id=uuid4(),
            result_content={"decision": "approved"},
        )

        is_valid = await certifier.verify_certification(
            result_id=cert_result.result_id,
            signature=cert_result.certification_signature,
        )

        assert is_valid is True

    @pytest.mark.asyncio
    async def test_verify_certification_with_invalid_signature(self) -> None:
        """verify_certification should return False for invalid signature."""
        certifier = MockResultCertifier()
        cert_result = await certifier.certify_result(
            deliberation_id=uuid4(),
            result_content={"decision": "approved"},
        )

        is_valid = await certifier.verify_certification(
            result_id=cert_result.result_id,
            signature="wrong_signature",
        )

        assert is_valid is False

    @pytest.mark.asyncio
    async def test_get_certification_returns_stored_result(self) -> None:
        """get_certification should return stored certification."""
        certifier = MockResultCertifier()
        cert_result = await certifier.certify_result(
            deliberation_id=uuid4(),
            result_content={"decision": "approved"},
        )

        retrieved = await certifier.get_certification(result_id=cert_result.result_id)

        assert retrieved is not None
        assert retrieved.result_id == cert_result.result_id

    @pytest.mark.asyncio
    async def test_get_certification_returns_none_for_unknown(self) -> None:
        """get_certification should return None for unknown result."""
        certifier = MockResultCertifier()

        retrieved = await certifier.get_certification(result_id=uuid4())

        assert retrieved is None

    @pytest.mark.asyncio
    async def test_compute_result_hash_returns_64_char_string(self) -> None:
        """compute_result_hash should return 64 character hash string."""
        certifier = MockResultCertifier()

        hash_value = await certifier.compute_result_hash(
            result_content={"decision": "approved"},
        )

        assert isinstance(hash_value, str)
        assert len(hash_value) == 64
