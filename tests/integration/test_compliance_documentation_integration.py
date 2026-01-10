"""Integration tests for compliance documentation (Story 9.9, NFR31-34).

Tests the end-to-end compliance documentation flow including:
- API endpoints (GET /v1/compliance)
- Service layer with repository integration
- Witnessed events via EventWriterService
- Initialization of all frameworks

Constitutional Constraints:
- NFR31: Personal data SHALL be stored separately from constitutional events (GDPR)
- NFR32: Retention policy SHALL be published and immutable
- NFR33: System SHALL provide structured audit export in standard format
- NFR34: Third-party attestation interface SHALL be available
- CT-11: HALT CHECK FIRST on every operation
- CT-12: All compliance events must be witnessed
"""

from datetime import datetime, timezone
from typing import AsyncGenerator
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.routes.compliance import router as compliance_router
from src.application.services.compliance_documentation_service import (
    ComplianceDocumentationService,
)
from src.domain.models.compliance import (
    ComplianceAssessment,
    ComplianceFramework,
    ComplianceRequirement,
    ComplianceStatus,
)
from src.infrastructure.stubs.compliance_repository_stub import (
    ComplianceRepositoryStub,
)


# ==============================================================================
# Test Fixtures
# ==============================================================================


@pytest.fixture
def compliance_repository() -> ComplianceRepositoryStub:
    """Create fresh compliance repository stub."""
    repo = ComplianceRepositoryStub()
    repo.clear()
    return repo


@pytest.fixture
def mock_halt_checker_not_halted() -> AsyncMock:
    """Create mock halt checker (not halted)."""
    checker = AsyncMock()
    checker.is_halted = AsyncMock(return_value=False)
    return checker


@pytest.fixture
def mock_event_writer() -> AsyncMock:
    """Create mock event writer."""
    writer = AsyncMock()
    writer.write_event = AsyncMock()
    return writer


@pytest.fixture
def compliance_service(
    compliance_repository: ComplianceRepositoryStub,
    mock_event_writer: AsyncMock,
    mock_halt_checker_not_halted: AsyncMock,
) -> ComplianceDocumentationService:
    """Create compliance documentation service with stubs."""
    return ComplianceDocumentationService(
        compliance_repository=compliance_repository,
        event_writer=mock_event_writer,
        halt_checker=mock_halt_checker_not_halted,
    )


@pytest.fixture
def sample_gdpr_requirement() -> ComplianceRequirement:
    """Create sample GDPR requirement."""
    return ComplianceRequirement(
        requirement_id="NFR31",
        framework=ComplianceFramework.GDPR,
        description="Personal data SHALL be stored separately from constitutional events",
        status=ComplianceStatus.COMPLIANT,
        implementation_reference="src/infrastructure/adapters/persistence/",
        evidence=("patronage_private schema isolation", "No PII in events"),
    )


@pytest.fixture
def sample_eu_ai_act_requirement() -> ComplianceRequirement:
    """Create sample EU AI Act requirement."""
    return ComplianceRequirement(
        requirement_id="EU-AI-ACT-01",
        framework=ComplianceFramework.EU_AI_ACT,
        description="Human oversight for high-risk AI systems",
        status=ComplianceStatus.COMPLIANT,
        implementation_reference="src/application/services/override_service.py",
        evidence=("Human Override Protocol",),
    )


@pytest.fixture
def test_app(compliance_service: ComplianceDocumentationService) -> FastAPI:
    """Create test FastAPI app with compliance routes."""
    from src.api.routes.compliance import get_compliance_service

    app = FastAPI()
    app.include_router(compliance_router)

    # Override the dependency to return our test service
    app.dependency_overrides[get_compliance_service] = lambda: compliance_service

    return app


@pytest.fixture
def test_client(test_app: FastAPI) -> TestClient:
    """Create test client."""
    return TestClient(test_app)


# ==============================================================================
# Repository Integration Tests
# ==============================================================================


class TestComplianceRepositoryIntegration:
    """Integration tests for ComplianceRepositoryStub."""

    @pytest.mark.asyncio
    async def test_save_and_retrieve_assessment(
        self,
        compliance_repository: ComplianceRepositoryStub,
        sample_gdpr_requirement: ComplianceRequirement,
    ) -> None:
        """Test saving and retrieving an assessment."""
        assessment = ComplianceAssessment(
            assessment_id="GDPR-ASSESSMENT-001",
            framework=ComplianceFramework.GDPR,
            assessment_date=datetime.now(timezone.utc),
            requirements=(sample_gdpr_requirement,),
        )

        await compliance_repository.save_assessment(assessment)
        retrieved = await compliance_repository.get_assessment("GDPR-ASSESSMENT-001")

        assert retrieved is not None
        assert retrieved.assessment_id == "GDPR-ASSESSMENT-001"
        assert retrieved.framework == ComplianceFramework.GDPR
        assert len(retrieved.requirements) == 1

    @pytest.mark.asyncio
    async def test_get_latest_assessment_returns_most_recent(
        self,
        compliance_repository: ComplianceRepositoryStub,
        sample_gdpr_requirement: ComplianceRequirement,
    ) -> None:
        """Test get_latest_assessment returns most recent for framework."""
        assessment1 = ComplianceAssessment(
            assessment_id="GDPR-ASSESSMENT-001",
            framework=ComplianceFramework.GDPR,
            assessment_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
            requirements=(sample_gdpr_requirement,),
        )
        assessment2 = ComplianceAssessment(
            assessment_id="GDPR-ASSESSMENT-002",
            framework=ComplianceFramework.GDPR,
            assessment_date=datetime(2025, 6, 1, tzinfo=timezone.utc),
            requirements=(sample_gdpr_requirement,),
        )

        await compliance_repository.save_assessment(assessment1)
        await compliance_repository.save_assessment(assessment2)

        latest = await compliance_repository.get_latest_assessment(ComplianceFramework.GDPR)

        assert latest is not None
        assert latest.assessment_id == "GDPR-ASSESSMENT-002"

    @pytest.mark.asyncio
    async def test_get_assessments_by_framework(
        self,
        compliance_repository: ComplianceRepositoryStub,
        sample_gdpr_requirement: ComplianceRequirement,
        sample_eu_ai_act_requirement: ComplianceRequirement,
    ) -> None:
        """Test filtering assessments by framework."""
        gdpr_assessment = ComplianceAssessment(
            assessment_id="GDPR-ASSESSMENT-001",
            framework=ComplianceFramework.GDPR,
            assessment_date=datetime.now(timezone.utc),
            requirements=(sample_gdpr_requirement,),
        )
        eu_ai_act_assessment = ComplianceAssessment(
            assessment_id="EU_AI_ACT-ASSESSMENT-001",
            framework=ComplianceFramework.EU_AI_ACT,
            assessment_date=datetime.now(timezone.utc),
            requirements=(sample_eu_ai_act_requirement,),
        )

        await compliance_repository.save_assessment(gdpr_assessment)
        await compliance_repository.save_assessment(eu_ai_act_assessment)

        gdpr_assessments = await compliance_repository.get_assessments_by_framework(
            ComplianceFramework.GDPR
        )

        assert len(gdpr_assessments) == 1
        assert gdpr_assessments[0].framework == ComplianceFramework.GDPR

    @pytest.mark.asyncio
    async def test_get_requirements_by_status(
        self,
        compliance_repository: ComplianceRepositoryStub,
    ) -> None:
        """Test getting requirements by status."""
        compliant_req = ComplianceRequirement(
            requirement_id="NFR31",
            framework=ComplianceFramework.GDPR,
            description="Compliant requirement",
            status=ComplianceStatus.COMPLIANT,
        )
        gap_req = ComplianceRequirement(
            requirement_id="NFR99",
            framework=ComplianceFramework.GDPR,
            description="Gap requirement",
            status=ComplianceStatus.GAP_IDENTIFIED,
        )
        assessment = ComplianceAssessment(
            assessment_id="GDPR-ASSESSMENT-001",
            framework=ComplianceFramework.GDPR,
            assessment_date=datetime.now(timezone.utc),
            requirements=(compliant_req, gap_req),
        )

        await compliance_repository.save_assessment(assessment)

        gaps = await compliance_repository.get_requirements_by_status(
            ComplianceStatus.GAP_IDENTIFIED
        )

        assert len(gaps) == 1
        assert gaps[0].requirement_id == "NFR99"


# ==============================================================================
# Service Integration Tests
# ==============================================================================


class TestComplianceServiceIntegration:
    """Integration tests for ComplianceDocumentationService."""

    @pytest.mark.asyncio
    async def test_document_assessment_creates_event(
        self,
        compliance_service: ComplianceDocumentationService,
        mock_event_writer: AsyncMock,
        sample_gdpr_requirement: ComplianceRequirement,
    ) -> None:
        """Test document_assessment creates witnessed event (CT-12)."""
        await compliance_service.document_assessment(
            framework=ComplianceFramework.GDPR,
            requirements=[sample_gdpr_requirement],
            gaps=[],
            framework_version="2016/679",
        )

        mock_event_writer.write_event.assert_called_once()
        call_kwargs = mock_event_writer.write_event.call_args.kwargs
        assert call_kwargs["event_type"] == "compliance.documented"
        assert "payload" in call_kwargs

    @pytest.mark.asyncio
    async def test_document_assessment_saves_to_repository(
        self,
        compliance_service: ComplianceDocumentationService,
        compliance_repository: ComplianceRepositoryStub,
        sample_gdpr_requirement: ComplianceRequirement,
    ) -> None:
        """Test document_assessment persists to repository."""
        assessment = await compliance_service.document_assessment(
            framework=ComplianceFramework.GDPR,
            requirements=[sample_gdpr_requirement],
            gaps=[],
        )

        retrieved = await compliance_repository.get_assessment(assessment.assessment_id)
        assert retrieved is not None
        assert retrieved.assessment_id == assessment.assessment_id

    @pytest.mark.asyncio
    async def test_get_compliance_posture_returns_all_frameworks(
        self,
        compliance_service: ComplianceDocumentationService,
        sample_gdpr_requirement: ComplianceRequirement,
        sample_eu_ai_act_requirement: ComplianceRequirement,
    ) -> None:
        """Test get_compliance_posture returns status for each framework."""
        await compliance_service.document_assessment(
            framework=ComplianceFramework.GDPR,
            requirements=[sample_gdpr_requirement],
            gaps=[],
        )
        await compliance_service.document_assessment(
            framework=ComplianceFramework.EU_AI_ACT,
            requirements=[sample_eu_ai_act_requirement],
            gaps=[],
        )

        posture = await compliance_service.get_compliance_posture()

        assert ComplianceFramework.GDPR in posture
        assert ComplianceFramework.EU_AI_ACT in posture
        assert posture[ComplianceFramework.GDPR] == ComplianceStatus.COMPLIANT
        assert posture[ComplianceFramework.EU_AI_ACT] == ComplianceStatus.COMPLIANT

    @pytest.mark.asyncio
    async def test_get_gaps_returns_gap_requirements(
        self,
        compliance_service: ComplianceDocumentationService,
    ) -> None:
        """Test get_gaps returns only GAP_IDENTIFIED requirements."""
        gap_req = ComplianceRequirement(
            requirement_id="GAP-001",
            framework=ComplianceFramework.GDPR,
            description="A gap",
            status=ComplianceStatus.GAP_IDENTIFIED,
        )
        compliant_req = ComplianceRequirement(
            requirement_id="COMPLIANT-001",
            framework=ComplianceFramework.GDPR,
            description="Compliant",
            status=ComplianceStatus.COMPLIANT,
        )

        await compliance_service.document_assessment(
            framework=ComplianceFramework.GDPR,
            requirements=[gap_req, compliant_req],
            gaps=["Identified gap"],
            remediation_plan="Fix in Q2",
        )

        gaps = await compliance_service.get_gaps()

        assert len(gaps) == 1
        assert gaps[0].requirement_id == "GAP-001"


# ==============================================================================
# API Integration Tests
# ==============================================================================


class TestComplianceAPIIntegration:
    """Integration tests for compliance API endpoints."""

    @pytest.mark.asyncio
    async def test_get_compliance_posture_endpoint(
        self,
        test_client: TestClient,
        compliance_service: ComplianceDocumentationService,
        sample_gdpr_requirement: ComplianceRequirement,
    ) -> None:
        """Test GET /v1/compliance returns compliance posture."""
        # First document an assessment
        await compliance_service.document_assessment(
            framework=ComplianceFramework.GDPR,
            requirements=[sample_gdpr_requirement],
            gaps=[],
        )

        response = test_client.get("/v1/compliance")

        assert response.status_code == 200
        data = response.json()
        assert "posture" in data
        assert "total_frameworks" in data
        assert data["total_frameworks"] == 1

    def test_get_compliance_posture_empty_returns_empty(
        self,
        test_client: TestClient,
    ) -> None:
        """Test GET /v1/compliance returns empty when no assessments."""
        response = test_client.get("/v1/compliance")

        assert response.status_code == 200
        data = response.json()
        assert data["posture"] == {}
        # No assessed_frameworks key in response model - use total_frameworks
        assert data["total_frameworks"] == 0

    @pytest.mark.asyncio
    async def test_get_frameworks_list_endpoint(
        self,
        test_client: TestClient,
        compliance_service: ComplianceDocumentationService,
        sample_gdpr_requirement: ComplianceRequirement,
    ) -> None:
        """Test GET /v1/compliance/frameworks returns list."""
        await compliance_service.document_assessment(
            framework=ComplianceFramework.GDPR,
            requirements=[sample_gdpr_requirement],
            gaps=[],
        )

        response = test_client.get("/v1/compliance/frameworks")

        assert response.status_code == 200
        data = response.json()
        assert "assessments" in data
        assert len(data["assessments"]) == 1
        assert data["assessments"][0]["framework"] == "GDPR"

    @pytest.mark.asyncio
    async def test_get_framework_assessment_endpoint(
        self,
        test_client: TestClient,
        compliance_service: ComplianceDocumentationService,
        sample_gdpr_requirement: ComplianceRequirement,
    ) -> None:
        """Test GET /v1/compliance/frameworks/{framework} returns assessment."""
        await compliance_service.document_assessment(
            framework=ComplianceFramework.GDPR,
            requirements=[sample_gdpr_requirement],
            gaps=[],
        )

        response = test_client.get("/v1/compliance/frameworks/GDPR")

        assert response.status_code == 200
        data = response.json()
        assert data["framework"] == "GDPR"
        assert data["overall_status"] == "COMPLIANT"
        assert len(data["requirements"]) == 1

    def test_get_framework_assessment_not_found(
        self,
        test_client: TestClient,
    ) -> None:
        """Test GET /v1/compliance/frameworks/{framework} returns 404 when not found."""
        response = test_client.get("/v1/compliance/frameworks/MAESTRO")

        assert response.status_code == 404
        data = response.json()
        # FastAPI returns the detail dict directly
        assert "detail" in data
        assert data["detail"]["title"] == "Framework Not Assessed"
        assert data["detail"]["status"] == 404

    @pytest.mark.asyncio
    async def test_get_gaps_endpoint(
        self,
        test_client: TestClient,
        compliance_service: ComplianceDocumentationService,
    ) -> None:
        """Test GET /v1/compliance/gaps returns gap requirements."""
        gap_req = ComplianceRequirement(
            requirement_id="GAP-001",
            framework=ComplianceFramework.GDPR,
            description="A gap",
            status=ComplianceStatus.GAP_IDENTIFIED,
        )

        await compliance_service.document_assessment(
            framework=ComplianceFramework.GDPR,
            requirements=[gap_req],
            gaps=["Gap identified"],
        )

        response = test_client.get("/v1/compliance/gaps")

        assert response.status_code == 200
        data = response.json()
        assert "gaps" in data
        assert len(data["gaps"]) == 1
        assert data["gaps"][0]["requirement_id"] == "GAP-001"

    def test_get_gaps_empty(self, test_client: TestClient) -> None:
        """Test GET /v1/compliance/gaps returns empty when no gaps."""
        response = test_client.get("/v1/compliance/gaps")

        assert response.status_code == 200
        data = response.json()
        assert data["gaps"] == []


# ==============================================================================
# Initialization Integration Tests
# ==============================================================================


class TestComplianceInitializationIntegration:
    """Integration tests for compliance initialization."""

    @pytest.mark.asyncio
    async def test_initialize_gdpr_compliance(
        self,
        compliance_service: ComplianceDocumentationService,
    ) -> None:
        """Test GDPR compliance initialization."""
        from src.infrastructure.initialization.compliance_init import (
            initialize_gdpr_compliance,
        )

        assessment = await initialize_gdpr_compliance(compliance_service)

        assert assessment.framework == ComplianceFramework.GDPR
        assert len(assessment.requirements) == 4  # NFR31-34
        assert assessment.overall_status == ComplianceStatus.COMPLIANT

    @pytest.mark.asyncio
    async def test_initialize_eu_ai_act_compliance(
        self,
        compliance_service: ComplianceDocumentationService,
    ) -> None:
        """Test EU AI Act compliance initialization."""
        from src.infrastructure.initialization.compliance_init import (
            initialize_eu_ai_act_compliance,
        )

        assessment = await initialize_eu_ai_act_compliance(compliance_service)

        assert assessment.framework == ComplianceFramework.EU_AI_ACT
        assert len(assessment.requirements) == 3  # Human oversight, transparency, audit trail
        assert assessment.overall_status == ComplianceStatus.COMPLIANT

    @pytest.mark.asyncio
    async def test_initialize_nist_ai_rmf_compliance(
        self,
        compliance_service: ComplianceDocumentationService,
    ) -> None:
        """Test NIST AI RMF compliance initialization."""
        from src.infrastructure.initialization.compliance_init import (
            initialize_nist_ai_rmf_compliance,
        )

        assessment = await initialize_nist_ai_rmf_compliance(compliance_service)

        assert assessment.framework == ComplianceFramework.NIST_AI_RMF
        assert len(assessment.requirements) == 4  # GOVERN, MAP, MEASURE, MANAGE
        assert assessment.overall_status == ComplianceStatus.COMPLIANT

    @pytest.mark.asyncio
    async def test_initialize_ieee_7001_compliance(
        self,
        compliance_service: ComplianceDocumentationService,
    ) -> None:
        """Test IEEE 7001 compliance initialization."""
        from src.infrastructure.initialization.compliance_init import (
            initialize_ieee_7001_compliance,
        )

        assessment = await initialize_ieee_7001_compliance(compliance_service)

        assert assessment.framework == ComplianceFramework.IEEE_7001
        assert len(assessment.requirements) == 3  # Traceability, versioning, verification
        assert assessment.overall_status == ComplianceStatus.COMPLIANT

    @pytest.mark.asyncio
    async def test_initialize_all_compliance_documentation(
        self,
        compliance_service: ComplianceDocumentationService,
    ) -> None:
        """Test initializing all compliance frameworks."""
        from src.infrastructure.initialization.compliance_init import (
            initialize_all_compliance_documentation,
        )

        assessments = await initialize_all_compliance_documentation(compliance_service)

        assert len(assessments) == 4
        frameworks = {a.framework for a in assessments}
        assert ComplianceFramework.GDPR in frameworks
        assert ComplianceFramework.EU_AI_ACT in frameworks
        assert ComplianceFramework.NIST_AI_RMF in frameworks
        assert ComplianceFramework.IEEE_7001 in frameworks

    @pytest.mark.asyncio
    async def test_initialization_creates_witnessed_events(
        self,
        compliance_service: ComplianceDocumentationService,
        mock_event_writer: AsyncMock,
    ) -> None:
        """Test initialization creates witnessed events for each framework (CT-12)."""
        from src.infrastructure.initialization.compliance_init import (
            initialize_all_compliance_documentation,
        )

        await initialize_all_compliance_documentation(compliance_service)

        # Should have called write_event 4 times (one per framework)
        assert mock_event_writer.write_event.call_count == 4


# ==============================================================================
# Constitutional Constraint Tests
# ==============================================================================


class TestConstitutionalConstraints:
    """Tests verifying constitutional constraints are enforced."""

    @pytest.mark.asyncio
    async def test_ct11_halt_check_first_document_assessment(
        self,
        compliance_repository: ComplianceRepositoryStub,
        mock_event_writer: AsyncMock,
        sample_gdpr_requirement: ComplianceRequirement,
    ) -> None:
        """Test CT-11: HALT CHECK FIRST on document_assessment."""
        from src.domain.errors import SystemHaltedError

        halted_checker = AsyncMock()
        halted_checker.is_halted = AsyncMock(return_value=True)

        service = ComplianceDocumentationService(
            compliance_repository=compliance_repository,
            event_writer=mock_event_writer,
            halt_checker=halted_checker,
        )

        with pytest.raises(SystemHaltedError):
            await service.document_assessment(
                framework=ComplianceFramework.GDPR,
                requirements=[sample_gdpr_requirement],
                gaps=[],
            )

        # Event should NOT be written when halted
        mock_event_writer.write_event.assert_not_called()

    @pytest.mark.asyncio
    async def test_ct11_halt_check_first_get_posture(
        self,
        compliance_repository: ComplianceRepositoryStub,
        mock_event_writer: AsyncMock,
    ) -> None:
        """Test CT-11: HALT CHECK FIRST on get_compliance_posture."""
        from src.domain.errors import SystemHaltedError

        halted_checker = AsyncMock()
        halted_checker.is_halted = AsyncMock(return_value=True)

        service = ComplianceDocumentationService(
            compliance_repository=compliance_repository,
            event_writer=mock_event_writer,
            halt_checker=halted_checker,
        )

        with pytest.raises(SystemHaltedError):
            await service.get_compliance_posture()

    @pytest.mark.asyncio
    async def test_ct12_compliance_events_witnessed(
        self,
        compliance_service: ComplianceDocumentationService,
        mock_event_writer: AsyncMock,
        sample_gdpr_requirement: ComplianceRequirement,
    ) -> None:
        """Test CT-12: Compliance documentation creates witnessed events."""
        await compliance_service.document_assessment(
            framework=ComplianceFramework.GDPR,
            requirements=[sample_gdpr_requirement],
            gaps=[],
        )

        mock_event_writer.write_event.assert_called_once()
        call_kwargs = mock_event_writer.write_event.call_args.kwargs
        assert call_kwargs["event_type"] == "compliance.documented"
        assert call_kwargs["agent_id"] == "system:compliance-documentation"


# ==============================================================================
# NFR31-34 Verification Tests
# ==============================================================================


class TestNFR31To34Verification:
    """Tests verifying NFR31-34 requirements are documented."""

    @pytest.mark.asyncio
    async def test_nfr31_gdpr_separation_documented(
        self,
        compliance_service: ComplianceDocumentationService,
    ) -> None:
        """Test NFR31: GDPR data separation is documented."""
        from src.infrastructure.initialization.compliance_init import (
            NFR31_REQUIREMENT,
            initialize_gdpr_compliance,
        )

        assessment = await initialize_gdpr_compliance(compliance_service)

        nfr31 = next(
            (r for r in assessment.requirements if r.requirement_id == "NFR31"),
            None,
        )
        assert nfr31 is not None
        assert nfr31.status == ComplianceStatus.COMPLIANT
        assert "patronage_private schema isolation" in nfr31.evidence

    @pytest.mark.asyncio
    async def test_nfr32_retention_policy_documented(
        self,
        compliance_service: ComplianceDocumentationService,
    ) -> None:
        """Test NFR32: Retention policy is documented."""
        from src.infrastructure.initialization.compliance_init import (
            initialize_gdpr_compliance,
        )

        assessment = await initialize_gdpr_compliance(compliance_service)

        nfr32 = next(
            (r for r in assessment.requirements if r.requirement_id == "NFR32"),
            None,
        )
        assert nfr32 is not None
        assert nfr32.status == ComplianceStatus.COMPLIANT
        # Evidence includes CT-13 reference
        assert any("Append-only event store" in e for e in nfr32.evidence)

    @pytest.mark.asyncio
    async def test_nfr33_audit_export_documented(
        self,
        compliance_service: ComplianceDocumentationService,
    ) -> None:
        """Test NFR33: Structured audit export is documented."""
        from src.infrastructure.initialization.compliance_init import (
            initialize_gdpr_compliance,
        )

        assessment = await initialize_gdpr_compliance(compliance_service)

        nfr33 = next(
            (r for r in assessment.requirements if r.requirement_id == "NFR33"),
            None,
        )
        assert nfr33 is not None
        assert nfr33.status == ComplianceStatus.COMPLIANT
        assert "Regulatory reporting export endpoint" in nfr33.evidence

    @pytest.mark.asyncio
    async def test_nfr34_attestation_interface_documented(
        self,
        compliance_service: ComplianceDocumentationService,
    ) -> None:
        """Test NFR34: Third-party attestation interface is documented."""
        from src.infrastructure.initialization.compliance_init import (
            initialize_gdpr_compliance,
        )

        assessment = await initialize_gdpr_compliance(compliance_service)

        nfr34 = next(
            (r for r in assessment.requirements if r.requirement_id == "NFR34"),
            None,
        )
        assert nfr34 is not None
        assert nfr34.status == ComplianceStatus.COMPLIANT
        assert "Observer API public read access" in nfr34.evidence
