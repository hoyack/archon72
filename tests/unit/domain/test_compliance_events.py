"""Unit tests for ComplianceDocumentedEvent domain event (Story 9.9, NFR31-34).

Tests for the ComplianceDocumentedEventPayload and related enums.

Constitutional Constraints:
- NFR31-34: Regulatory compliance documentation requirements
- CT-12: Witnessing creates accountability -> Event must be signable
"""

import json
from datetime import datetime, timezone

import pytest

from src.domain.events.compliance import (
    COMPLIANCE_DOCUMENTED_EVENT_TYPE,
    COMPLIANCE_SYSTEM_AGENT_ID,
    ComplianceDocumentedEventPayload,
    ComplianceFramework,
    ComplianceStatus,
)


class TestComplianceFrameworkEnum:
    """Tests for ComplianceFramework enum."""

    def test_eu_ai_act_value(self) -> None:
        """Test EU_AI_ACT has correct value."""
        assert ComplianceFramework.EU_AI_ACT.value == "EU_AI_ACT"

    def test_nist_ai_rmf_value(self) -> None:
        """Test NIST_AI_RMF has correct value."""
        assert ComplianceFramework.NIST_AI_RMF.value == "NIST_AI_RMF"

    def test_ieee_7001_value(self) -> None:
        """Test IEEE_7001 has correct value."""
        assert ComplianceFramework.IEEE_7001.value == "IEEE_7001"

    def test_gdpr_value(self) -> None:
        """Test GDPR has correct value."""
        assert ComplianceFramework.GDPR.value == "GDPR"

    def test_maestro_value(self) -> None:
        """Test MAESTRO has correct value."""
        assert ComplianceFramework.MAESTRO.value == "MAESTRO"


class TestComplianceStatusEnum:
    """Tests for ComplianceStatus enum."""

    def test_compliant_status_value(self) -> None:
        """Test COMPLIANT status has correct value."""
        assert ComplianceStatus.COMPLIANT.value == "COMPLIANT"

    def test_partial_status_value(self) -> None:
        """Test PARTIAL status has correct value."""
        assert ComplianceStatus.PARTIAL.value == "PARTIAL"

    def test_gap_identified_status_value(self) -> None:
        """Test GAP_IDENTIFIED status has correct value."""
        assert ComplianceStatus.GAP_IDENTIFIED.value == "GAP_IDENTIFIED"

    def test_not_applicable_status_value(self) -> None:
        """Test NOT_APPLICABLE status has correct value."""
        assert ComplianceStatus.NOT_APPLICABLE.value == "NOT_APPLICABLE"


class TestComplianceDocumentedEventPayload:
    """Tests for ComplianceDocumentedEventPayload dataclass."""

    @pytest.fixture
    def valid_payload(self) -> ComplianceDocumentedEventPayload:
        """Create a valid payload for testing."""
        return ComplianceDocumentedEventPayload(
            compliance_id="EU_AI_ACT-ASSESSMENT-a1b2c3d4",
            framework=ComplianceFramework.EU_AI_ACT,
            framework_version="2024/1689",
            assessment_date=datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
            status=ComplianceStatus.COMPLIANT,
            findings=("Human oversight implemented", "Transparency requirements met"),
            remediation_plan=None,
            next_review_date=None,
            documented_by=COMPLIANCE_SYSTEM_AGENT_ID,
        )

    def test_payload_creation_success(self, valid_payload: ComplianceDocumentedEventPayload) -> None:
        """Test successful payload creation with all fields."""
        assert valid_payload.compliance_id == "EU_AI_ACT-ASSESSMENT-a1b2c3d4"
        assert valid_payload.framework == ComplianceFramework.EU_AI_ACT
        assert valid_payload.framework_version == "2024/1689"
        assert valid_payload.status == ComplianceStatus.COMPLIANT
        assert len(valid_payload.findings) == 2
        assert valid_payload.remediation_plan is None
        assert valid_payload.documented_by == COMPLIANCE_SYSTEM_AGENT_ID

    def test_payload_is_immutable(self, valid_payload: ComplianceDocumentedEventPayload) -> None:
        """Test payload is immutable (frozen dataclass)."""
        with pytest.raises(AttributeError):
            valid_payload.compliance_id = "different-id"  # type: ignore

    def test_payload_equality(self) -> None:
        """Test two payloads with same values are equal."""
        timestamp = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        payload1 = ComplianceDocumentedEventPayload(
            compliance_id="TEST-ASSESSMENT",
            framework=ComplianceFramework.GDPR,
            framework_version="2016/679",
            assessment_date=timestamp,
            status=ComplianceStatus.COMPLIANT,
            findings=("Test finding",),
            documented_by="system:test",
        )
        payload2 = ComplianceDocumentedEventPayload(
            compliance_id="TEST-ASSESSMENT",
            framework=ComplianceFramework.GDPR,
            framework_version="2016/679",
            assessment_date=timestamp,
            status=ComplianceStatus.COMPLIANT,
            findings=("Test finding",),
            documented_by="system:test",
        )
        assert payload1 == payload2

    def test_payload_validation_empty_compliance_id(self) -> None:
        """Test validation fails for empty compliance_id."""
        with pytest.raises(ValueError, match="compliance_id is required"):
            ComplianceDocumentedEventPayload(
                compliance_id="",
                framework=ComplianceFramework.EU_AI_ACT,
                framework_version="2024/1689",
                assessment_date=datetime.now(timezone.utc),
                status=ComplianceStatus.COMPLIANT,
                documented_by="system:test",
            )

    def test_payload_validation_empty_framework_version(self) -> None:
        """Test validation fails for empty framework_version."""
        with pytest.raises(ValueError, match="framework_version is required"):
            ComplianceDocumentedEventPayload(
                compliance_id="TEST-ASSESSMENT",
                framework=ComplianceFramework.EU_AI_ACT,
                framework_version="",
                assessment_date=datetime.now(timezone.utc),
                status=ComplianceStatus.COMPLIANT,
                documented_by="system:test",
            )

    def test_payload_validation_empty_documented_by(self) -> None:
        """Test validation fails for empty documented_by."""
        with pytest.raises(ValueError, match="documented_by is required"):
            ComplianceDocumentedEventPayload(
                compliance_id="TEST-ASSESSMENT",
                framework=ComplianceFramework.EU_AI_ACT,
                framework_version="2024/1689",
                assessment_date=datetime.now(timezone.utc),
                status=ComplianceStatus.COMPLIANT,
                documented_by="",
            )


class TestComplianceDocumentedEventPayloadToDict:
    """Tests for ComplianceDocumentedEventPayload.to_dict() method."""

    def test_to_dict_contains_all_fields(self) -> None:
        """Test to_dict includes all required fields."""
        payload = ComplianceDocumentedEventPayload(
            compliance_id="EU_AI_ACT-ASSESSMENT-a1b2c3d4",
            framework=ComplianceFramework.EU_AI_ACT,
            framework_version="2024/1689",
            assessment_date=datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
            status=ComplianceStatus.COMPLIANT,
            findings=("Finding 1", "Finding 2"),
            remediation_plan="Address in Q2",
            next_review_date=datetime(2025, 6, 1, 0, 0, 0, tzinfo=timezone.utc),
            documented_by="system:test",
        )
        result = payload.to_dict()

        assert result["compliance_id"] == "EU_AI_ACT-ASSESSMENT-a1b2c3d4"
        assert result["framework"] == "EU_AI_ACT"
        assert result["framework_version"] == "2024/1689"
        assert result["assessment_date"] == "2025-01-01T00:00:00+00:00"
        assert result["status"] == "COMPLIANT"
        assert result["findings"] == ["Finding 1", "Finding 2"]
        assert result["remediation_plan"] == "Address in Q2"
        assert result["next_review_date"] == "2025-06-01T00:00:00+00:00"
        assert result["documented_by"] == "system:test"

    def test_to_dict_handles_none_optional_fields(self) -> None:
        """Test to_dict handles None for optional fields."""
        payload = ComplianceDocumentedEventPayload(
            compliance_id="TEST-ASSESSMENT",
            framework=ComplianceFramework.NIST_AI_RMF,
            framework_version="1.0",
            assessment_date=datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
            status=ComplianceStatus.PARTIAL,
            findings=(),
            remediation_plan=None,
            next_review_date=None,
            documented_by="system:test",
        )
        result = payload.to_dict()

        assert result["remediation_plan"] is None
        assert result["next_review_date"] is None
        assert result["findings"] == []

    def test_to_dict_is_json_serializable(self) -> None:
        """Test to_dict output can be serialized to JSON."""
        payload = ComplianceDocumentedEventPayload(
            compliance_id="TEST-ASSESSMENT",
            framework=ComplianceFramework.IEEE_7001,
            framework_version="2021",
            assessment_date=datetime(2025, 6, 15, 12, 30, 0, tzinfo=timezone.utc),
            status=ComplianceStatus.GAP_IDENTIFIED,
            findings=("Gap 1", "Gap 2"),
            remediation_plan="Fix gaps",
            documented_by="system:test",
        )
        result = payload.to_dict()

        # Should not raise
        json_str = json.dumps(result)
        assert json_str is not None
        assert len(json_str) > 0


class TestComplianceDocumentedEventPayloadSignableContent:
    """Tests for ComplianceDocumentedEventPayload.signable_content() method (CT-12)."""

    def test_signable_content_returns_bytes(self) -> None:
        """Test signable_content returns bytes."""
        payload = ComplianceDocumentedEventPayload(
            compliance_id="TEST-ASSESSMENT",
            framework=ComplianceFramework.EU_AI_ACT,
            framework_version="2024/1689",
            assessment_date=datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
            status=ComplianceStatus.COMPLIANT,
            documented_by="system:test",
        )
        result = payload.signable_content()
        assert isinstance(result, bytes)

    def test_signable_content_is_deterministic(self) -> None:
        """Test signable_content produces same output for same input."""
        timestamp = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        payload1 = ComplianceDocumentedEventPayload(
            compliance_id="TEST-ASSESSMENT",
            framework=ComplianceFramework.EU_AI_ACT,
            framework_version="2024/1689",
            assessment_date=timestamp,
            status=ComplianceStatus.COMPLIANT,
            documented_by="system:test",
        )
        payload2 = ComplianceDocumentedEventPayload(
            compliance_id="TEST-ASSESSMENT",
            framework=ComplianceFramework.EU_AI_ACT,
            framework_version="2024/1689",
            assessment_date=timestamp,
            status=ComplianceStatus.COMPLIANT,
            documented_by="system:test",
        )
        assert payload1.signable_content() == payload2.signable_content()

    def test_signable_content_differs_for_different_payloads(self) -> None:
        """Test signable_content differs when payload differs."""
        timestamp = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        payload1 = ComplianceDocumentedEventPayload(
            compliance_id="ASSESSMENT-1",
            framework=ComplianceFramework.EU_AI_ACT,
            framework_version="2024/1689",
            assessment_date=timestamp,
            status=ComplianceStatus.COMPLIANT,
            documented_by="system:test",
        )
        payload2 = ComplianceDocumentedEventPayload(
            compliance_id="ASSESSMENT-2",  # Different ID
            framework=ComplianceFramework.EU_AI_ACT,
            framework_version="2024/1689",
            assessment_date=timestamp,
            status=ComplianceStatus.COMPLIANT,
            documented_by="system:test",
        )
        assert payload1.signable_content() != payload2.signable_content()


class TestComplianceEventTypeConstants:
    """Tests for event type constants."""

    def test_event_type_constant_value(self) -> None:
        """Test event type constant has expected value."""
        assert COMPLIANCE_DOCUMENTED_EVENT_TYPE == "compliance.documented"

    def test_system_agent_id_constant_value(self) -> None:
        """Test system agent ID constant has expected value."""
        assert COMPLIANCE_SYSTEM_AGENT_ID == "system:compliance-documentation"
