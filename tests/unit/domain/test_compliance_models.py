"""Unit tests for compliance domain models (Story 9.9, NFR31-34).

Tests for ComplianceRequirement, ComplianceAssessment, FrameworkMapping,
and helper functions.

Constitutional Constraints:
- NFR31-34: Regulatory compliance documentation requirements
"""

from datetime import datetime, timezone

import pytest

from src.domain.models.compliance import (
    ComplianceAssessment,
    ComplianceFramework,
    ComplianceRequirement,
    ComplianceStatus,
    FrameworkMapping,
    generate_assessment_id,
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


class TestComplianceRequirement:
    """Tests for ComplianceRequirement dataclass."""

    @pytest.fixture
    def valid_requirement(self) -> ComplianceRequirement:
        """Create a valid requirement for testing."""
        return ComplianceRequirement(
            requirement_id="NFR31",
            framework=ComplianceFramework.GDPR,
            description="Personal data SHALL be stored separately",
            status=ComplianceStatus.COMPLIANT,
            implementation_reference="src/infrastructure/adapters/persistence/",
            evidence=("patronage_private schema isolation", "No PII in events"),
        )

    def test_requirement_creation_success(
        self, valid_requirement: ComplianceRequirement
    ) -> None:
        """Test successful requirement creation with all fields."""
        assert valid_requirement.requirement_id == "NFR31"
        assert valid_requirement.framework == ComplianceFramework.GDPR
        assert valid_requirement.description == "Personal data SHALL be stored separately"
        assert valid_requirement.status == ComplianceStatus.COMPLIANT
        assert valid_requirement.implementation_reference == "src/infrastructure/adapters/persistence/"
        assert len(valid_requirement.evidence) == 2

    def test_requirement_is_immutable(
        self, valid_requirement: ComplianceRequirement
    ) -> None:
        """Test requirement is immutable (frozen dataclass)."""
        with pytest.raises(AttributeError):
            valid_requirement.requirement_id = "NFR99"  # type: ignore

    def test_requirement_equality(self) -> None:
        """Test two requirements with same values are equal."""
        req1 = ComplianceRequirement(
            requirement_id="NFR31",
            framework=ComplianceFramework.GDPR,
            description="Test requirement",
            status=ComplianceStatus.COMPLIANT,
        )
        req2 = ComplianceRequirement(
            requirement_id="NFR31",
            framework=ComplianceFramework.GDPR,
            description="Test requirement",
            status=ComplianceStatus.COMPLIANT,
        )
        assert req1 == req2

    def test_requirement_validation_empty_id(self) -> None:
        """Test validation fails for empty requirement_id."""
        with pytest.raises(ValueError, match="requirement_id is required"):
            ComplianceRequirement(
                requirement_id="",
                framework=ComplianceFramework.GDPR,
                description="Test requirement",
                status=ComplianceStatus.COMPLIANT,
            )

    def test_requirement_validation_empty_description(self) -> None:
        """Test validation fails for empty description."""
        with pytest.raises(ValueError, match="description is required"):
            ComplianceRequirement(
                requirement_id="NFR31",
                framework=ComplianceFramework.GDPR,
                description="",
                status=ComplianceStatus.COMPLIANT,
            )

    def test_requirement_default_evidence(self) -> None:
        """Test requirement has empty tuple for evidence by default."""
        req = ComplianceRequirement(
            requirement_id="NFR31",
            framework=ComplianceFramework.GDPR,
            description="Test requirement",
            status=ComplianceStatus.COMPLIANT,
        )
        assert req.evidence == ()

    def test_requirement_to_dict(self, valid_requirement: ComplianceRequirement) -> None:
        """Test to_dict contains all fields."""
        result = valid_requirement.to_dict()

        assert result["requirement_id"] == "NFR31"
        assert result["framework"] == "GDPR"
        assert result["description"] == "Personal data SHALL be stored separately"
        assert result["status"] == "COMPLIANT"
        assert result["implementation_reference"] == "src/infrastructure/adapters/persistence/"
        assert result["evidence"] == [
            "patronage_private schema isolation",
            "No PII in events",
        ]


class TestComplianceAssessment:
    """Tests for ComplianceAssessment dataclass."""

    @pytest.fixture
    def valid_assessment(self) -> ComplianceAssessment:
        """Create a valid assessment for testing."""
        return ComplianceAssessment(
            assessment_id="GDPR-ASSESSMENT-a1b2c3d4",
            framework=ComplianceFramework.GDPR,
            assessment_date=datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
            requirements=(
                ComplianceRequirement(
                    requirement_id="NFR31",
                    framework=ComplianceFramework.GDPR,
                    description="Data separation",
                    status=ComplianceStatus.COMPLIANT,
                ),
            ),
            gaps=(),
            remediation_plan=None,
        )

    def test_assessment_creation_success(
        self, valid_assessment: ComplianceAssessment
    ) -> None:
        """Test successful assessment creation with all fields."""
        assert valid_assessment.assessment_id == "GDPR-ASSESSMENT-a1b2c3d4"
        assert valid_assessment.framework == ComplianceFramework.GDPR
        assert valid_assessment.assessment_date.year == 2025
        assert len(valid_assessment.requirements) == 1
        assert valid_assessment.gaps == ()
        assert valid_assessment.remediation_plan is None

    def test_assessment_is_immutable(self, valid_assessment: ComplianceAssessment) -> None:
        """Test assessment is immutable (frozen dataclass)."""
        with pytest.raises(AttributeError):
            valid_assessment.assessment_id = "DIFFERENT-ID"  # type: ignore

    def test_assessment_validation_empty_id(self) -> None:
        """Test validation fails for empty assessment_id."""
        with pytest.raises(ValueError, match="assessment_id is required"):
            ComplianceAssessment(
                assessment_id="",
                framework=ComplianceFramework.GDPR,
                assessment_date=datetime.now(timezone.utc),
                requirements=(),
            )

    def test_assessment_overall_status_compliant(self) -> None:
        """Test overall_status is COMPLIANT when all requirements compliant."""
        assessment = ComplianceAssessment(
            assessment_id="TEST-ASSESSMENT",
            framework=ComplianceFramework.GDPR,
            assessment_date=datetime.now(timezone.utc),
            requirements=(
                ComplianceRequirement(
                    requirement_id="NFR31",
                    framework=ComplianceFramework.GDPR,
                    description="Test 1",
                    status=ComplianceStatus.COMPLIANT,
                ),
                ComplianceRequirement(
                    requirement_id="NFR32",
                    framework=ComplianceFramework.GDPR,
                    description="Test 2",
                    status=ComplianceStatus.COMPLIANT,
                ),
            ),
        )
        assert assessment.overall_status == ComplianceStatus.COMPLIANT

    def test_assessment_overall_status_gap_identified(self) -> None:
        """Test overall_status is GAP_IDENTIFIED when any requirement has gap."""
        assessment = ComplianceAssessment(
            assessment_id="TEST-ASSESSMENT",
            framework=ComplianceFramework.GDPR,
            assessment_date=datetime.now(timezone.utc),
            requirements=(
                ComplianceRequirement(
                    requirement_id="NFR31",
                    framework=ComplianceFramework.GDPR,
                    description="Test 1",
                    status=ComplianceStatus.COMPLIANT,
                ),
                ComplianceRequirement(
                    requirement_id="NFR32",
                    framework=ComplianceFramework.GDPR,
                    description="Test 2",
                    status=ComplianceStatus.GAP_IDENTIFIED,
                ),
            ),
        )
        assert assessment.overall_status == ComplianceStatus.GAP_IDENTIFIED

    def test_assessment_overall_status_partial(self) -> None:
        """Test overall_status is PARTIAL when some are partial."""
        assessment = ComplianceAssessment(
            assessment_id="TEST-ASSESSMENT",
            framework=ComplianceFramework.GDPR,
            assessment_date=datetime.now(timezone.utc),
            requirements=(
                ComplianceRequirement(
                    requirement_id="NFR31",
                    framework=ComplianceFramework.GDPR,
                    description="Test 1",
                    status=ComplianceStatus.COMPLIANT,
                ),
                ComplianceRequirement(
                    requirement_id="NFR32",
                    framework=ComplianceFramework.GDPR,
                    description="Test 2",
                    status=ComplianceStatus.PARTIAL,
                ),
            ),
        )
        assert assessment.overall_status == ComplianceStatus.PARTIAL

    def test_assessment_overall_status_empty_requirements(self) -> None:
        """Test overall_status is NOT_APPLICABLE when no requirements."""
        assessment = ComplianceAssessment(
            assessment_id="TEST-ASSESSMENT",
            framework=ComplianceFramework.GDPR,
            assessment_date=datetime.now(timezone.utc),
            requirements=(),
        )
        assert assessment.overall_status == ComplianceStatus.NOT_APPLICABLE

    def test_assessment_overall_status_compliant_and_na(self) -> None:
        """Test overall_status is COMPLIANT when all are compliant or N/A."""
        assessment = ComplianceAssessment(
            assessment_id="TEST-ASSESSMENT",
            framework=ComplianceFramework.GDPR,
            assessment_date=datetime.now(timezone.utc),
            requirements=(
                ComplianceRequirement(
                    requirement_id="NFR31",
                    framework=ComplianceFramework.GDPR,
                    description="Test 1",
                    status=ComplianceStatus.COMPLIANT,
                ),
                ComplianceRequirement(
                    requirement_id="NFR32",
                    framework=ComplianceFramework.GDPR,
                    description="Test 2",
                    status=ComplianceStatus.NOT_APPLICABLE,
                ),
            ),
        )
        assert assessment.overall_status == ComplianceStatus.COMPLIANT

    def test_assessment_to_dict(self, valid_assessment: ComplianceAssessment) -> None:
        """Test to_dict contains all fields."""
        result = valid_assessment.to_dict()

        assert result["assessment_id"] == "GDPR-ASSESSMENT-a1b2c3d4"
        assert result["framework"] == "GDPR"
        assert result["assessment_date"] == "2025-01-01T00:00:00+00:00"
        assert len(result["requirements"]) == 1
        assert result["overall_status"] == "COMPLIANT"
        assert result["gaps"] == []
        assert result["remediation_plan"] is None


class TestFrameworkMapping:
    """Tests for FrameworkMapping dataclass."""

    @pytest.fixture
    def valid_mapping(self) -> FrameworkMapping:
        """Create a valid mapping for testing."""
        return FrameworkMapping(
            mapping_id="MAPPING-001",
            capability="Human Override Protocol",
            framework_requirements={
                ComplianceFramework.EU_AI_ACT: ("EU-AI-ACT-01",),
                ComplianceFramework.NIST_AI_RMF: ("NIST-GOVERN",),
            },
            implementation_reference="src/application/services/override_service.py",
        )

    def test_mapping_creation_success(self, valid_mapping: FrameworkMapping) -> None:
        """Test successful mapping creation."""
        assert valid_mapping.mapping_id == "MAPPING-001"
        assert valid_mapping.capability == "Human Override Protocol"
        assert len(valid_mapping.framework_requirements) == 2
        assert valid_mapping.implementation_reference == "src/application/services/override_service.py"

    def test_mapping_is_immutable(self, valid_mapping: FrameworkMapping) -> None:
        """Test mapping is immutable (frozen dataclass)."""
        with pytest.raises(AttributeError):
            valid_mapping.mapping_id = "DIFFERENT-ID"  # type: ignore

    def test_mapping_validation_empty_id(self) -> None:
        """Test validation fails for empty mapping_id."""
        with pytest.raises(ValueError, match="mapping_id is required"):
            FrameworkMapping(
                mapping_id="",
                capability="Test capability",
                framework_requirements={},
                implementation_reference="src/test.py",
            )

    def test_mapping_validation_empty_capability(self) -> None:
        """Test validation fails for empty capability."""
        with pytest.raises(ValueError, match="capability is required"):
            FrameworkMapping(
                mapping_id="MAPPING-001",
                capability="",
                framework_requirements={},
                implementation_reference="src/test.py",
            )

    def test_mapping_validation_empty_impl_reference(self) -> None:
        """Test validation fails for empty implementation_reference."""
        with pytest.raises(ValueError, match="implementation_reference is required"):
            FrameworkMapping(
                mapping_id="MAPPING-001",
                capability="Test capability",
                framework_requirements={},
                implementation_reference="",
            )

    def test_mapping_to_dict(self, valid_mapping: FrameworkMapping) -> None:
        """Test to_dict contains all fields."""
        result = valid_mapping.to_dict()

        assert result["mapping_id"] == "MAPPING-001"
        assert result["capability"] == "Human Override Protocol"
        assert result["framework_requirements"]["EU_AI_ACT"] == ["EU-AI-ACT-01"]
        assert result["framework_requirements"]["NIST_AI_RMF"] == ["NIST-GOVERN"]
        assert result["implementation_reference"] == "src/application/services/override_service.py"


class TestGenerateAssessmentId:
    """Tests for generate_assessment_id function."""

    def test_generates_unique_ids(self) -> None:
        """Test generates unique IDs for same framework."""
        id1 = generate_assessment_id(ComplianceFramework.EU_AI_ACT)
        id2 = generate_assessment_id(ComplianceFramework.EU_AI_ACT)
        assert id1 != id2

    def test_includes_framework_prefix(self) -> None:
        """Test generated ID includes framework prefix."""
        id1 = generate_assessment_id(ComplianceFramework.EU_AI_ACT)
        assert id1.startswith("EU_AI_ACT-ASSESSMENT-")

        id2 = generate_assessment_id(ComplianceFramework.GDPR)
        assert id2.startswith("GDPR-ASSESSMENT-")

    def test_has_correct_format(self) -> None:
        """Test generated ID has expected format."""
        id1 = generate_assessment_id(ComplianceFramework.NIST_AI_RMF)
        parts = id1.split("-")
        assert parts[0] == "NIST_AI_RMF"
        assert parts[1] == "ASSESSMENT"
        assert len(parts[2]) == 8  # Short UUID
