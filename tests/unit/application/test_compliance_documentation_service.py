"""Unit tests for ComplianceDocumentationService (Story 9.9, NFR31-34).

Tests for the compliance documentation service with mocked dependencies.

Constitutional Constraints:
- NFR31-34: Regulatory compliance documentation requirements
- CT-11: HALT CHECK FIRST on every operation
- CT-12: All compliance events must be witnessed
"""

from datetime import datetime, timezone
from typing import Optional
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.application.services.compliance_documentation_service import (
    COMPLIANCE_DOCUMENTATION_SYSTEM_AGENT_ID,
    ComplianceDocumentationService,
)
from src.domain.errors import SystemHaltedError
from src.domain.models.compliance import (
    ComplianceAssessment,
    ComplianceFramework,
    ComplianceRequirement,
    ComplianceStatus,
)


class TestComplianceDocumentationServiceInit:
    """Tests for ComplianceDocumentationService initialization."""

    def test_service_initialization(self) -> None:
        """Test service initializes with required dependencies."""
        repo = MagicMock()
        writer = MagicMock()
        halt_checker = MagicMock()

        service = ComplianceDocumentationService(
            compliance_repository=repo,
            event_writer=writer,
            halt_checker=halt_checker,
        )

        assert service._repository == repo
        assert service._event_writer == writer
        assert service._halt_checker == halt_checker

    def test_system_agent_id_constant(self) -> None:
        """Test system agent ID constant is set correctly."""
        assert COMPLIANCE_DOCUMENTATION_SYSTEM_AGENT_ID == "system:compliance-documentation"


class TestDocumentAssessment:
    """Tests for document_assessment method."""

    @pytest.fixture
    def mock_repository(self) -> AsyncMock:
        """Create mock compliance repository."""
        repo = AsyncMock()
        repo.save_assessment = AsyncMock()
        repo.exists = AsyncMock(return_value=False)
        return repo

    @pytest.fixture
    def mock_event_writer(self) -> AsyncMock:
        """Create mock event writer."""
        writer = AsyncMock()
        writer.write_event = AsyncMock()
        return writer

    @pytest.fixture
    def mock_halt_checker_not_halted(self) -> AsyncMock:
        """Create mock halt checker (not halted)."""
        checker = AsyncMock()
        checker.is_halted = AsyncMock(return_value=False)
        return checker

    @pytest.fixture
    def mock_halt_checker_halted(self) -> AsyncMock:
        """Create mock halt checker (halted)."""
        checker = AsyncMock()
        checker.is_halted = AsyncMock(return_value=True)
        return checker

    @pytest.fixture
    def sample_requirement(self) -> ComplianceRequirement:
        """Create sample requirement."""
        return ComplianceRequirement(
            requirement_id="NFR31",
            framework=ComplianceFramework.GDPR,
            description="Personal data SHALL be stored separately",
            status=ComplianceStatus.COMPLIANT,
            evidence=("Schema isolation",),
        )

    @pytest.mark.asyncio
    async def test_document_assessment_success(
        self,
        mock_repository: AsyncMock,
        mock_event_writer: AsyncMock,
        mock_halt_checker_not_halted: AsyncMock,
        sample_requirement: ComplianceRequirement,
    ) -> None:
        """Test successful assessment documentation."""
        service = ComplianceDocumentationService(
            compliance_repository=mock_repository,
            event_writer=mock_event_writer,
            halt_checker=mock_halt_checker_not_halted,
        )

        result = await service.document_assessment(
            framework=ComplianceFramework.GDPR,
            requirements=[sample_requirement],
            gaps=[],
            remediation_plan=None,
            framework_version="2016/679",
        )

        assert result.framework == ComplianceFramework.GDPR
        assert len(result.requirements) == 1
        assert result.requirements[0].requirement_id == "NFR31"
        mock_repository.save_assessment.assert_called_once()
        mock_event_writer.write_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_document_assessment_halt_check_first_ct11(
        self,
        mock_repository: AsyncMock,
        mock_event_writer: AsyncMock,
        mock_halt_checker_halted: AsyncMock,
        sample_requirement: ComplianceRequirement,
    ) -> None:
        """Test HALT CHECK FIRST pattern (CT-11)."""
        service = ComplianceDocumentationService(
            compliance_repository=mock_repository,
            event_writer=mock_event_writer,
            halt_checker=mock_halt_checker_halted,
        )

        with pytest.raises(SystemHaltedError):
            await service.document_assessment(
                framework=ComplianceFramework.GDPR,
                requirements=[sample_requirement],
                gaps=[],
            )

        # Repository and event writer should NOT be called
        mock_repository.save_assessment.assert_not_called()
        mock_event_writer.write_event.assert_not_called()

    @pytest.mark.asyncio
    async def test_document_assessment_creates_witnessed_event_ct12(
        self,
        mock_repository: AsyncMock,
        mock_event_writer: AsyncMock,
        mock_halt_checker_not_halted: AsyncMock,
        sample_requirement: ComplianceRequirement,
    ) -> None:
        """Test compliance events are witnessed (CT-12)."""
        service = ComplianceDocumentationService(
            compliance_repository=mock_repository,
            event_writer=mock_event_writer,
            halt_checker=mock_halt_checker_not_halted,
        )

        await service.document_assessment(
            framework=ComplianceFramework.GDPR,
            requirements=[sample_requirement],
            gaps=[],
        )

        # Verify event was written
        mock_event_writer.write_event.assert_called_once()
        call_kwargs = mock_event_writer.write_event.call_args.kwargs
        assert call_kwargs["event_type"] == "compliance.documented"
        assert "payload" in call_kwargs

    @pytest.mark.asyncio
    async def test_document_assessment_with_gaps(
        self,
        mock_repository: AsyncMock,
        mock_event_writer: AsyncMock,
        mock_halt_checker_not_halted: AsyncMock,
    ) -> None:
        """Test assessment with identified gaps."""
        gap_requirement = ComplianceRequirement(
            requirement_id="NFR99",
            framework=ComplianceFramework.GDPR,
            description="Missing requirement",
            status=ComplianceStatus.GAP_IDENTIFIED,
        )

        service = ComplianceDocumentationService(
            compliance_repository=mock_repository,
            event_writer=mock_event_writer,
            halt_checker=mock_halt_checker_not_halted,
        )

        result = await service.document_assessment(
            framework=ComplianceFramework.GDPR,
            requirements=[gap_requirement],
            gaps=["Gap in data handling"],
            remediation_plan="Address in Phase 2",
        )

        assert len(result.gaps) == 1
        assert result.gaps[0] == "Gap in data handling"
        assert result.remediation_plan == "Address in Phase 2"


class TestGetCompliancePosture:
    """Tests for get_compliance_posture method."""

    @pytest.fixture
    def mock_repository_with_assessments(self) -> AsyncMock:
        """Create mock repository with pre-existing assessments."""
        repo = AsyncMock()
        repo.get_all_latest_assessments = AsyncMock(
            return_value=(
                ComplianceAssessment(
                    assessment_id="GDPR-ASSESSMENT-001",
                    framework=ComplianceFramework.GDPR,
                    assessment_date=datetime.now(timezone.utc),
                    requirements=(
                        ComplianceRequirement(
                            requirement_id="NFR31",
                            framework=ComplianceFramework.GDPR,
                            description="Test",
                            status=ComplianceStatus.COMPLIANT,
                        ),
                    ),
                ),
                ComplianceAssessment(
                    assessment_id="EU_AI_ACT-ASSESSMENT-002",
                    framework=ComplianceFramework.EU_AI_ACT,
                    assessment_date=datetime.now(timezone.utc),
                    requirements=(
                        ComplianceRequirement(
                            requirement_id="EU-AI-ACT-01",
                            framework=ComplianceFramework.EU_AI_ACT,
                            description="Test",
                            status=ComplianceStatus.PARTIAL,
                        ),
                    ),
                ),
            )
        )
        return repo

    @pytest.mark.asyncio
    async def test_get_compliance_posture_success(
        self,
        mock_repository_with_assessments: AsyncMock,
    ) -> None:
        """Test getting compliance posture."""
        halt_checker = AsyncMock()
        halt_checker.is_halted = AsyncMock(return_value=False)

        service = ComplianceDocumentationService(
            compliance_repository=mock_repository_with_assessments,
            event_writer=AsyncMock(),
            halt_checker=halt_checker,
        )

        result = await service.get_compliance_posture()

        assert ComplianceFramework.GDPR in result
        assert result[ComplianceFramework.GDPR] == ComplianceStatus.COMPLIANT
        assert ComplianceFramework.EU_AI_ACT in result
        assert result[ComplianceFramework.EU_AI_ACT] == ComplianceStatus.PARTIAL

    @pytest.mark.asyncio
    async def test_get_compliance_posture_halt_check_first_ct11(self) -> None:
        """Test HALT CHECK FIRST pattern (CT-11)."""
        halt_checker = AsyncMock()
        halt_checker.is_halted = AsyncMock(return_value=True)

        service = ComplianceDocumentationService(
            compliance_repository=AsyncMock(),
            event_writer=AsyncMock(),
            halt_checker=halt_checker,
        )

        with pytest.raises(SystemHaltedError):
            await service.get_compliance_posture()


class TestGetGaps:
    """Tests for get_gaps method."""

    @pytest.fixture
    def mock_repository_with_gaps(self) -> AsyncMock:
        """Create mock repository with gap requirements."""
        repo = AsyncMock()
        repo.get_requirements_by_status = AsyncMock(
            return_value=(
                ComplianceRequirement(
                    requirement_id="NFR99",
                    framework=ComplianceFramework.GDPR,
                    description="Missing requirement",
                    status=ComplianceStatus.GAP_IDENTIFIED,
                ),
            )
        )
        return repo

    @pytest.mark.asyncio
    async def test_get_gaps_success(
        self,
        mock_repository_with_gaps: AsyncMock,
    ) -> None:
        """Test getting gaps."""
        halt_checker = AsyncMock()
        halt_checker.is_halted = AsyncMock(return_value=False)

        service = ComplianceDocumentationService(
            compliance_repository=mock_repository_with_gaps,
            event_writer=AsyncMock(),
            halt_checker=halt_checker,
        )

        result = await service.get_gaps()

        assert len(result) == 1
        assert result[0].status == ComplianceStatus.GAP_IDENTIFIED
        mock_repository_with_gaps.get_requirements_by_status.assert_called_once_with(
            ComplianceStatus.GAP_IDENTIFIED
        )

    @pytest.mark.asyncio
    async def test_get_gaps_halt_check_first_ct11(self) -> None:
        """Test HALT CHECK FIRST pattern (CT-11)."""
        halt_checker = AsyncMock()
        halt_checker.is_halted = AsyncMock(return_value=True)

        service = ComplianceDocumentationService(
            compliance_repository=AsyncMock(),
            event_writer=AsyncMock(),
            halt_checker=halt_checker,
        )

        with pytest.raises(SystemHaltedError):
            await service.get_gaps()


class TestGetFrameworkAssessment:
    """Tests for get_framework_assessment method."""

    @pytest.fixture
    def mock_repository_with_latest(self) -> AsyncMock:
        """Create mock repository with latest assessment."""
        repo = AsyncMock()
        repo.get_latest_assessment = AsyncMock(
            return_value=ComplianceAssessment(
                assessment_id="GDPR-ASSESSMENT-001",
                framework=ComplianceFramework.GDPR,
                assessment_date=datetime.now(timezone.utc),
                requirements=(),
            )
        )
        return repo

    @pytest.mark.asyncio
    async def test_get_framework_assessment_success(
        self,
        mock_repository_with_latest: AsyncMock,
    ) -> None:
        """Test getting framework assessment."""
        halt_checker = AsyncMock()
        halt_checker.is_halted = AsyncMock(return_value=False)

        service = ComplianceDocumentationService(
            compliance_repository=mock_repository_with_latest,
            event_writer=AsyncMock(),
            halt_checker=halt_checker,
        )

        result = await service.get_framework_assessment(ComplianceFramework.GDPR)

        assert result is not None
        assert result.framework == ComplianceFramework.GDPR
        mock_repository_with_latest.get_latest_assessment.assert_called_once_with(
            ComplianceFramework.GDPR
        )

    @pytest.mark.asyncio
    async def test_get_framework_assessment_not_found(self) -> None:
        """Test getting framework assessment when none exists."""
        repo = AsyncMock()
        repo.get_latest_assessment = AsyncMock(return_value=None)
        halt_checker = AsyncMock()
        halt_checker.is_halted = AsyncMock(return_value=False)

        service = ComplianceDocumentationService(
            compliance_repository=repo,
            event_writer=AsyncMock(),
            halt_checker=halt_checker,
        )

        result = await service.get_framework_assessment(ComplianceFramework.MAESTRO)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_framework_assessment_halt_check_first_ct11(self) -> None:
        """Test HALT CHECK FIRST pattern (CT-11)."""
        halt_checker = AsyncMock()
        halt_checker.is_halted = AsyncMock(return_value=True)

        service = ComplianceDocumentationService(
            compliance_repository=AsyncMock(),
            event_writer=AsyncMock(),
            halt_checker=halt_checker,
        )

        with pytest.raises(SystemHaltedError):
            await service.get_framework_assessment(ComplianceFramework.GDPR)


class TestGetAllAssessments:
    """Tests for get_all_assessments method."""

    @pytest.mark.asyncio
    async def test_get_all_assessments_success(self) -> None:
        """Test getting all assessments."""
        repo = AsyncMock()
        repo.get_all_latest_assessments = AsyncMock(
            return_value=(
                ComplianceAssessment(
                    assessment_id="GDPR-001",
                    framework=ComplianceFramework.GDPR,
                    assessment_date=datetime.now(timezone.utc),
                    requirements=(),
                ),
            )
        )
        halt_checker = AsyncMock()
        halt_checker.is_halted = AsyncMock(return_value=False)

        service = ComplianceDocumentationService(
            compliance_repository=repo,
            event_writer=AsyncMock(),
            halt_checker=halt_checker,
        )

        result = await service.get_all_assessments()

        assert len(result) == 1
        assert result[0].framework == ComplianceFramework.GDPR

    @pytest.mark.asyncio
    async def test_get_all_assessments_halt_check_first_ct11(self) -> None:
        """Test HALT CHECK FIRST pattern (CT-11)."""
        halt_checker = AsyncMock()
        halt_checker.is_halted = AsyncMock(return_value=True)

        service = ComplianceDocumentationService(
            compliance_repository=AsyncMock(),
            event_writer=AsyncMock(),
            halt_checker=halt_checker,
        )

        with pytest.raises(SystemHaltedError):
            await service.get_all_assessments()


class TestAssessmentExists:
    """Tests for assessment_exists method."""

    @pytest.mark.asyncio
    async def test_assessment_exists_true(self) -> None:
        """Test assessment_exists returns True when exists."""
        repo = AsyncMock()
        repo.exists = AsyncMock(return_value=True)
        halt_checker = AsyncMock()
        halt_checker.is_halted = AsyncMock(return_value=False)

        service = ComplianceDocumentationService(
            compliance_repository=repo,
            event_writer=AsyncMock(),
            halt_checker=halt_checker,
        )

        result = await service.assessment_exists("TEST-ID")

        assert result is True
        repo.exists.assert_called_once_with("TEST-ID")

    @pytest.mark.asyncio
    async def test_assessment_exists_false(self) -> None:
        """Test assessment_exists returns False when not exists."""
        repo = AsyncMock()
        repo.exists = AsyncMock(return_value=False)
        halt_checker = AsyncMock()
        halt_checker.is_halted = AsyncMock(return_value=False)

        service = ComplianceDocumentationService(
            compliance_repository=repo,
            event_writer=AsyncMock(),
            halt_checker=halt_checker,
        )

        result = await service.assessment_exists("NONEXISTENT-ID")

        assert result is False

    @pytest.mark.asyncio
    async def test_assessment_exists_halt_check_first_ct11(self) -> None:
        """Test HALT CHECK FIRST pattern (CT-11)."""
        halt_checker = AsyncMock()
        halt_checker.is_halted = AsyncMock(return_value=True)

        service = ComplianceDocumentationService(
            compliance_repository=AsyncMock(),
            event_writer=AsyncMock(),
            halt_checker=halt_checker,
        )

        with pytest.raises(SystemHaltedError):
            await service.assessment_exists("TEST-ID")
