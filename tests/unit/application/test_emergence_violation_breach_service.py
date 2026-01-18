"""Unit tests for EmergenceViolationBreachService (Story 9.6, FR109).

Tests that emergence language violations are correctly converted to
constitutional breaches.

Constitutional Constraints:
- FR109: Emergence violations create constitutional breaches
- FR55: The violated requirement (no emergence claims)
- CT-11: HALT CHECK FIRST
- CT-12: All breaches witnessed (delegated to BreachDeclarationService)
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from src.application.services.emergence_violation_breach_service import (
    EMERGENCE_VIOLATED_REQUIREMENT,
    EmergenceViolationBreachService,
)
from src.domain.errors.breach import BreachDeclarationError
from src.domain.errors.writer import SystemHaltedError
from src.domain.events.breach import (
    BreachEventPayload,
    BreachSeverity,
    BreachType,
)

# =============================================================================
# Fixtures
# =============================================================================


class MockBreachDeclarationService:
    """Mock BreachDeclarationService for testing."""

    def __init__(self) -> None:
        self.declare_breach_mock = AsyncMock()
        self._created_breach: BreachEventPayload | None = None

    def set_breach_result(self, breach: BreachEventPayload) -> None:
        """Configure the breach to return."""
        self._created_breach = breach
        self.declare_breach_mock.return_value = breach

    def set_declare_error(self, error: Exception) -> None:
        """Configure declare_breach to raise an error."""
        self.declare_breach_mock.side_effect = error

    async def declare_breach(
        self,
        breach_type: BreachType,
        violated_requirement: str,
        severity: BreachSeverity,
        details: dict[str, Any],
        source_event_id: UUID | None = None,
    ) -> BreachEventPayload:
        """Delegate to mock."""
        return await self.declare_breach_mock(
            breach_type=breach_type,
            violated_requirement=violated_requirement,
            severity=severity,
            details=details,
            source_event_id=source_event_id,
        )


class MockHaltChecker:
    """Mock HaltChecker for testing."""

    def __init__(self) -> None:
        self._halted: bool = False
        self._halt_reason: str = "Test halt"

    def set_halted(self, halted: bool, reason: str = "Test halt") -> None:
        """Set halt state."""
        self._halted = halted
        self._halt_reason = reason

    async def is_halted(self) -> bool:
        """Check if halted."""
        return self._halted

    async def get_halt_reason(self) -> str:
        """Get halt reason."""
        return self._halt_reason


@pytest.fixture
def mock_breach_service() -> MockBreachDeclarationService:
    """Provide mock breach declaration service."""
    return MockBreachDeclarationService()


@pytest.fixture
def mock_halt_checker() -> MockHaltChecker:
    """Provide mock halt checker."""
    return MockHaltChecker()


@pytest.fixture
def service(
    mock_breach_service: MockBreachDeclarationService,
    mock_halt_checker: MockHaltChecker,
) -> EmergenceViolationBreachService:
    """Provide service under test."""
    return EmergenceViolationBreachService(
        breach_service=mock_breach_service,  # type: ignore[arg-type]
        halt_checker=mock_halt_checker,
    )


def create_breach_payload(
    breach_id: UUID | None = None,
    breach_type: BreachType = BreachType.EMERGENCE_VIOLATION,
    violated_requirement: str = "FR55",
    severity: BreachSeverity = BreachSeverity.HIGH,
    source_event_id: UUID | None = None,
) -> BreachEventPayload:
    """Create a breach payload for testing."""
    return BreachEventPayload(
        breach_id=breach_id or uuid4(),
        breach_type=breach_type,
        violated_requirement=violated_requirement,
        severity=severity,
        detection_timestamp=datetime.now(timezone.utc),
        details=MappingProxyType({"test": "details"}),
        source_event_id=source_event_id,
    )


# =============================================================================
# HALT CHECK FIRST Tests (CT-11)
# =============================================================================


class TestHaltCheckFirst:
    """Tests for CT-11 HALT CHECK FIRST pattern."""

    @pytest.mark.asyncio
    async def test_create_breach_rejects_when_halted(
        self,
        service: EmergenceViolationBreachService,
        mock_halt_checker: MockHaltChecker,
    ) -> None:
        """Service rejects breach creation when system is halted (CT-11)."""
        mock_halt_checker.set_halted(True, "Fork detected")

        with pytest.raises(SystemHaltedError) as exc_info:
            await service.create_breach_for_violation(
                violation_event_id=uuid4(),
                content_id="test-123",
                matched_terms=("emergence",),
                detection_method="keyword_scan",
            )

        assert "CT-11" in str(exc_info.value)
        assert "halted" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_create_breach_includes_halt_reason(
        self,
        service: EmergenceViolationBreachService,
        mock_halt_checker: MockHaltChecker,
    ) -> None:
        """Error message includes the halt reason (CT-11)."""
        mock_halt_checker.set_halted(True, "Hash chain mismatch detected")

        with pytest.raises(SystemHaltedError) as exc_info:
            await service.create_breach_for_violation(
                violation_event_id=uuid4(),
                content_id="test-456",
                matched_terms=("consciousness",),
                detection_method="nfkc_scan",
            )

        assert "Hash chain mismatch" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_create_breach_succeeds_when_not_halted(
        self,
        service: EmergenceViolationBreachService,
        mock_halt_checker: MockHaltChecker,
        mock_breach_service: MockBreachDeclarationService,
    ) -> None:
        """Service creates breach when system is not halted (CT-11)."""
        mock_halt_checker.set_halted(False)
        expected_breach = create_breach_payload()
        mock_breach_service.set_breach_result(expected_breach)

        result = await service.create_breach_for_violation(
            violation_event_id=uuid4(),
            content_id="test-789",
            matched_terms=("sentience",),
            detection_method="keyword_scan",
        )

        assert result.breach_id == expected_breach.breach_id

    @pytest.mark.asyncio
    async def test_halt_check_before_breach_service_call(
        self,
        service: EmergenceViolationBreachService,
        mock_halt_checker: MockHaltChecker,
        mock_breach_service: MockBreachDeclarationService,
    ) -> None:
        """Halt check happens before breach service is called (CT-11)."""
        mock_halt_checker.set_halted(True)

        with pytest.raises(SystemHaltedError):
            await service.create_breach_for_violation(
                violation_event_id=uuid4(),
                content_id="test-000",
                matched_terms=("self-aware",),
                detection_method="keyword_scan",
            )

        # Breach service should NOT have been called
        mock_breach_service.declare_breach_mock.assert_not_called()


# =============================================================================
# Breach Creation Tests (FR109)
# =============================================================================


class TestBreachCreation:
    """Tests for breach creation with correct type."""

    @pytest.mark.asyncio
    async def test_creates_breach_with_emergence_violation_type(
        self,
        service: EmergenceViolationBreachService,
        mock_breach_service: MockBreachDeclarationService,
    ) -> None:
        """Breach is created with type EMERGENCE_VIOLATION (FR109)."""
        expected_breach = create_breach_payload(
            breach_type=BreachType.EMERGENCE_VIOLATION
        )
        mock_breach_service.set_breach_result(expected_breach)

        await service.create_breach_for_violation(
            violation_event_id=uuid4(),
            content_id="test-123",
            matched_terms=("emergence",),
            detection_method="keyword_scan",
        )

        call_kwargs = mock_breach_service.declare_breach_mock.call_args.kwargs
        assert call_kwargs["breach_type"] == BreachType.EMERGENCE_VIOLATION

    @pytest.mark.asyncio
    async def test_creates_breach_with_fr55_requirement(
        self,
        service: EmergenceViolationBreachService,
        mock_breach_service: MockBreachDeclarationService,
    ) -> None:
        """Breach has violated_requirement=FR55 (FR55 reference)."""
        expected_breach = create_breach_payload()
        mock_breach_service.set_breach_result(expected_breach)

        await service.create_breach_for_violation(
            violation_event_id=uuid4(),
            content_id="test-456",
            matched_terms=("consciousness",),
            detection_method="nfkc_scan",
        )

        call_kwargs = mock_breach_service.declare_breach_mock.call_args.kwargs
        assert call_kwargs["violated_requirement"] == EMERGENCE_VIOLATED_REQUIREMENT
        assert call_kwargs["violated_requirement"] == "FR55"

    @pytest.mark.asyncio
    async def test_creates_breach_with_high_severity(
        self,
        service: EmergenceViolationBreachService,
        mock_breach_service: MockBreachDeclarationService,
    ) -> None:
        """Breach has severity=HIGH (page immediately)."""
        expected_breach = create_breach_payload(severity=BreachSeverity.HIGH)
        mock_breach_service.set_breach_result(expected_breach)

        await service.create_breach_for_violation(
            violation_event_id=uuid4(),
            content_id="test-789",
            matched_terms=("sentience",),
            detection_method="keyword_scan",
        )

        call_kwargs = mock_breach_service.declare_breach_mock.call_args.kwargs
        assert call_kwargs["severity"] == BreachSeverity.HIGH

    @pytest.mark.asyncio
    async def test_creates_breach_with_source_event_id(
        self,
        service: EmergenceViolationBreachService,
        mock_breach_service: MockBreachDeclarationService,
    ) -> None:
        """Breach references the violation event via source_event_id."""
        violation_event_id = uuid4()
        expected_breach = create_breach_payload(source_event_id=violation_event_id)
        mock_breach_service.set_breach_result(expected_breach)

        await service.create_breach_for_violation(
            violation_event_id=violation_event_id,
            content_id="test-000",
            matched_terms=("self-aware",),
            detection_method="keyword_scan",
        )

        call_kwargs = mock_breach_service.declare_breach_mock.call_args.kwargs
        assert call_kwargs["source_event_id"] == violation_event_id


# =============================================================================
# Breach Details Tests
# =============================================================================


class TestBreachDetails:
    """Tests for breach details content."""

    @pytest.mark.asyncio
    async def test_includes_content_id_in_details(
        self,
        service: EmergenceViolationBreachService,
        mock_breach_service: MockBreachDeclarationService,
    ) -> None:
        """Breach details include content_id."""
        expected_breach = create_breach_payload()
        mock_breach_service.set_breach_result(expected_breach)

        await service.create_breach_for_violation(
            violation_event_id=uuid4(),
            content_id="output-12345",
            matched_terms=("emergence",),
            detection_method="keyword_scan",
        )

        call_kwargs = mock_breach_service.declare_breach_mock.call_args.kwargs
        details = call_kwargs["details"]
        assert details["content_id"] == "output-12345"

    @pytest.mark.asyncio
    async def test_includes_matched_terms_in_details(
        self,
        service: EmergenceViolationBreachService,
        mock_breach_service: MockBreachDeclarationService,
    ) -> None:
        """Breach details include matched_terms as list."""
        expected_breach = create_breach_payload()
        mock_breach_service.set_breach_result(expected_breach)
        terms = ("emergence", "consciousness", "sentience")

        await service.create_breach_for_violation(
            violation_event_id=uuid4(),
            content_id="output-67890",
            matched_terms=terms,
            detection_method="nfkc_scan",
        )

        call_kwargs = mock_breach_service.declare_breach_mock.call_args.kwargs
        details = call_kwargs["details"]
        assert details["matched_terms"] == list(terms)

    @pytest.mark.asyncio
    async def test_includes_detection_method_in_details(
        self,
        service: EmergenceViolationBreachService,
        mock_breach_service: MockBreachDeclarationService,
    ) -> None:
        """Breach details include detection_method."""
        expected_breach = create_breach_payload()
        mock_breach_service.set_breach_result(expected_breach)

        await service.create_breach_for_violation(
            violation_event_id=uuid4(),
            content_id="output-abc",
            matched_terms=("self-aware",),
            detection_method="semantic_analysis",
        )

        call_kwargs = mock_breach_service.declare_breach_mock.call_args.kwargs
        details = call_kwargs["details"]
        assert details["detection_method"] == "semantic_analysis"

    @pytest.mark.asyncio
    async def test_includes_violation_event_id_in_details(
        self,
        service: EmergenceViolationBreachService,
        mock_breach_service: MockBreachDeclarationService,
    ) -> None:
        """Breach details include violation_event_id as string."""
        expected_breach = create_breach_payload()
        mock_breach_service.set_breach_result(expected_breach)
        violation_id = uuid4()

        await service.create_breach_for_violation(
            violation_event_id=violation_id,
            content_id="output-xyz",
            matched_terms=("awakened",),
            detection_method="keyword_scan",
        )

        call_kwargs = mock_breach_service.declare_breach_mock.call_args.kwargs
        details = call_kwargs["details"]
        assert details["violation_event_id"] == str(violation_id)


# =============================================================================
# Return Value Tests
# =============================================================================


class TestReturnValue:
    """Tests for service return value."""

    @pytest.mark.asyncio
    async def test_returns_breach_from_declaration_service(
        self,
        service: EmergenceViolationBreachService,
        mock_breach_service: MockBreachDeclarationService,
    ) -> None:
        """Service returns the breach from declaration service."""
        expected_breach = create_breach_payload()
        mock_breach_service.set_breach_result(expected_breach)

        result = await service.create_breach_for_violation(
            violation_event_id=uuid4(),
            content_id="test-return",
            matched_terms=("emergence",),
            detection_method="keyword_scan",
        )

        assert result == expected_breach

    @pytest.mark.asyncio
    async def test_returns_breach_with_correct_id(
        self,
        service: EmergenceViolationBreachService,
        mock_breach_service: MockBreachDeclarationService,
    ) -> None:
        """Returned breach has the expected breach_id."""
        breach_id = uuid4()
        expected_breach = create_breach_payload(breach_id=breach_id)
        mock_breach_service.set_breach_result(expected_breach)

        result = await service.create_breach_for_violation(
            violation_event_id=uuid4(),
            content_id="test-id",
            matched_terms=("consciousness",),
            detection_method="nfkc_scan",
        )

        assert result.breach_id == breach_id


# =============================================================================
# Error Propagation Tests
# =============================================================================


class TestErrorPropagation:
    """Tests for error propagation from breach service."""

    @pytest.mark.asyncio
    async def test_propagates_breach_declaration_error(
        self,
        service: EmergenceViolationBreachService,
        mock_breach_service: MockBreachDeclarationService,
    ) -> None:
        """BreachDeclarationError from breach service is propagated."""
        error = BreachDeclarationError("FR30: Database connection failed")
        mock_breach_service.set_declare_error(error)

        with pytest.raises(BreachDeclarationError) as exc_info:
            await service.create_breach_for_violation(
                violation_event_id=uuid4(),
                content_id="test-error",
                matched_terms=("emergence",),
                detection_method="keyword_scan",
            )

        assert "Database connection failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_propagates_system_halted_error_from_breach_service(
        self,
        service: EmergenceViolationBreachService,
        mock_breach_service: MockBreachDeclarationService,
    ) -> None:
        """SystemHaltedError from breach service is propagated."""
        # This can happen if halt occurs between our check and the service call
        error = SystemHaltedError("CT-11: System halted during declaration")
        mock_breach_service.set_declare_error(error)

        with pytest.raises(SystemHaltedError) as exc_info:
            await service.create_breach_for_violation(
                violation_event_id=uuid4(),
                content_id="test-halt-race",
                matched_terms=("sentience",),
                detection_method="keyword_scan",
            )

        assert "halted during declaration" in str(exc_info.value)
