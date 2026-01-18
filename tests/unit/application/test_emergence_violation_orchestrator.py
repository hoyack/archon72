"""Unit tests for EmergenceViolationOrchestrator (Story 9.6, FR109).

Tests that the orchestrator coordinates violation detection and breach
creation correctly.

Constitutional Constraints:
- FR109: Emergence violations create constitutional breaches
- FR55: No emergence claims
- CT-11: HALT CHECK FIRST
- CT-12: All events witnessed (delegated)
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import MappingProxyType
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from src.application.ports.prohibited_language_scanner import ScanResult
from src.application.services.emergence_violation_orchestrator import (
    EmergenceViolationOrchestrator,
)
from src.domain.errors.prohibited_language import (
    ProhibitedLanguageBlockedError,
    ProhibitedLanguageScanError,
)
from src.domain.errors.writer import SystemHaltedError
from src.domain.events.breach import (
    BreachEventPayload,
    BreachSeverity,
    BreachType,
)

# =============================================================================
# Fixtures
# =============================================================================


class MockBlockingService:
    """Mock ProhibitedLanguageBlockingService for testing."""

    def __init__(self) -> None:
        self.check_content_mock = AsyncMock()
        self._scan_result: ScanResult | None = None
        self._error: Exception | None = None

    def set_clean_result(self) -> None:
        """Configure service to return clean scan result."""
        self._scan_result = ScanResult(
            violations_found=False,
            matched_terms=(),
            detection_method="keyword_scan",
        )
        self._error = None
        self.check_content_mock.return_value = self._scan_result

    def set_violation_error(
        self,
        content_id: str,
        matched_terms: tuple[str, ...],
    ) -> None:
        """Configure service to raise violation error."""
        self._error = ProhibitedLanguageBlockedError(
            content_id=content_id,
            matched_terms=matched_terms,
        )
        self.check_content_mock.side_effect = self._error

    def set_scan_error(self, source_error: Exception) -> None:
        """Configure service to raise scan error."""
        self._error = ProhibitedLanguageScanError(
            source_error=source_error,
            content_id=None,
        )
        self.check_content_mock.side_effect = self._error

    async def check_content_for_prohibited_language(
        self,
        content_id: str,
        content: str,
    ) -> ScanResult:
        """Delegate to mock."""
        return await self.check_content_mock(
            content_id=content_id,
            content=content,
        )


class MockBreachService:
    """Mock EmergenceViolationBreachService for testing."""

    def __init__(self) -> None:
        self.create_breach_mock = AsyncMock()
        self._created_breach: BreachEventPayload | None = None
        self._create_error: Exception | None = None

    def set_breach_result(self, breach: BreachEventPayload) -> None:
        """Configure the breach to return."""
        self._created_breach = breach
        self._create_error = None
        self.create_breach_mock.return_value = breach

    def set_create_error(self, error: Exception) -> None:
        """Configure create_breach to raise an error."""
        self._create_error = error
        self.create_breach_mock.side_effect = error

    async def create_breach_for_violation(
        self,
        violation_event_id: UUID,
        content_id: str,
        matched_terms: tuple[str, ...],
        detection_method: str,
    ) -> BreachEventPayload:
        """Delegate to mock."""
        return await self.create_breach_mock(
            violation_event_id=violation_event_id,
            content_id=content_id,
            matched_terms=matched_terms,
            detection_method=detection_method,
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
def mock_blocking_service() -> MockBlockingService:
    """Provide mock blocking service."""
    return MockBlockingService()


@pytest.fixture
def mock_breach_service() -> MockBreachService:
    """Provide mock breach service."""
    return MockBreachService()


@pytest.fixture
def mock_halt_checker() -> MockHaltChecker:
    """Provide mock halt checker."""
    return MockHaltChecker()


@pytest.fixture
def orchestrator(
    mock_blocking_service: MockBlockingService,
    mock_breach_service: MockBreachService,
    mock_halt_checker: MockHaltChecker,
) -> EmergenceViolationOrchestrator:
    """Provide orchestrator under test."""
    return EmergenceViolationOrchestrator(
        blocking_service=mock_blocking_service,  # type: ignore[arg-type]
        breach_service=mock_breach_service,  # type: ignore[arg-type]
        halt_checker=mock_halt_checker,
    )


def create_breach_payload(
    breach_id: UUID | None = None,
    source_event_id: UUID | None = None,
) -> BreachEventPayload:
    """Create a breach payload for testing."""
    return BreachEventPayload(
        breach_id=breach_id or uuid4(),
        breach_type=BreachType.EMERGENCE_VIOLATION,
        violated_requirement="FR55",
        severity=BreachSeverity.HIGH,
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
    async def test_rejects_when_halted(
        self,
        orchestrator: EmergenceViolationOrchestrator,
        mock_halt_checker: MockHaltChecker,
    ) -> None:
        """Orchestrator rejects operation when system is halted (CT-11)."""
        mock_halt_checker.set_halted(True, "Fork detected")

        with pytest.raises(SystemHaltedError) as exc_info:
            await orchestrator.check_and_report_violation(
                content_id="test-123",
                content="This content has emergence claims.",
            )

        assert "CT-11" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_includes_halt_reason(
        self,
        orchestrator: EmergenceViolationOrchestrator,
        mock_halt_checker: MockHaltChecker,
    ) -> None:
        """Error message includes the halt reason (CT-11)."""
        mock_halt_checker.set_halted(True, "Hash chain corruption")

        with pytest.raises(SystemHaltedError) as exc_info:
            await orchestrator.check_and_report_violation(
                content_id="test-456",
                content="Test content",
            )

        assert "Hash chain corruption" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_halt_check_before_blocking_service(
        self,
        orchestrator: EmergenceViolationOrchestrator,
        mock_halt_checker: MockHaltChecker,
        mock_blocking_service: MockBlockingService,
    ) -> None:
        """Halt check happens before blocking service is called (CT-11)."""
        mock_halt_checker.set_halted(True)
        mock_blocking_service.set_clean_result()

        with pytest.raises(SystemHaltedError):
            await orchestrator.check_and_report_violation(
                content_id="test-789",
                content="Test content",
            )

        # Blocking service should NOT have been called
        mock_blocking_service.check_content_mock.assert_not_called()

    @pytest.mark.asyncio
    async def test_proceeds_when_not_halted(
        self,
        orchestrator: EmergenceViolationOrchestrator,
        mock_halt_checker: MockHaltChecker,
        mock_blocking_service: MockBlockingService,
    ) -> None:
        """Orchestrator proceeds when system is not halted (CT-11)."""
        mock_halt_checker.set_halted(False)
        mock_blocking_service.set_clean_result()

        result = await orchestrator.check_and_report_violation(
            content_id="test-000",
            content="Clean content",
        )

        assert result.violations_found is False


# =============================================================================
# Clean Content Tests
# =============================================================================


class TestCleanContent:
    """Tests for clean content handling."""

    @pytest.mark.asyncio
    async def test_returns_clean_scan_result(
        self,
        orchestrator: EmergenceViolationOrchestrator,
        mock_blocking_service: MockBlockingService,
    ) -> None:
        """Orchestrator returns clean scan result when no violations."""
        mock_blocking_service.set_clean_result()

        result = await orchestrator.check_and_report_violation(
            content_id="clean-content-123",
            content="This is perfectly clean content.",
        )

        assert result.violations_found is False
        assert result.matched_terms == ()

    @pytest.mark.asyncio
    async def test_no_breach_created_for_clean_content(
        self,
        orchestrator: EmergenceViolationOrchestrator,
        mock_blocking_service: MockBlockingService,
        mock_breach_service: MockBreachService,
    ) -> None:
        """No breach is created for clean content."""
        mock_blocking_service.set_clean_result()

        await orchestrator.check_and_report_violation(
            content_id="clean-content-456",
            content="This is safe content with no emergence claims.",
        )

        # Breach service should NOT have been called
        mock_breach_service.create_breach_mock.assert_not_called()


# =============================================================================
# Violation Detection Tests (FR109)
# =============================================================================


class TestViolationDetection:
    """Tests for violation detection and breach creation."""

    @pytest.mark.asyncio
    async def test_creates_breach_on_violation(
        self,
        orchestrator: EmergenceViolationOrchestrator,
        mock_blocking_service: MockBlockingService,
        mock_breach_service: MockBreachService,
    ) -> None:
        """Breach is created when violation is detected (FR109)."""
        mock_blocking_service.set_violation_error(
            content_id="violation-123",
            matched_terms=("emergence", "consciousness"),
        )
        mock_breach_service.set_breach_result(create_breach_payload())

        with pytest.raises(ProhibitedLanguageBlockedError):
            await orchestrator.check_and_report_violation(
                content_id="violation-123",
                content="This system has emergence and consciousness.",
            )

        # Breach service SHOULD have been called
        mock_breach_service.create_breach_mock.assert_called_once()

    @pytest.mark.asyncio
    async def test_breach_includes_matched_terms(
        self,
        orchestrator: EmergenceViolationOrchestrator,
        mock_blocking_service: MockBlockingService,
        mock_breach_service: MockBreachService,
    ) -> None:
        """Breach creation includes matched terms from violation."""
        matched = ("sentience", "self-aware")
        mock_blocking_service.set_violation_error(
            content_id="violation-456",
            matched_terms=matched,
        )
        mock_breach_service.set_breach_result(create_breach_payload())

        with pytest.raises(ProhibitedLanguageBlockedError):
            await orchestrator.check_and_report_violation(
                content_id="violation-456",
                content="Content with sentience and self-aware claims.",
            )

        call_kwargs = mock_breach_service.create_breach_mock.call_args.kwargs
        assert call_kwargs["matched_terms"] == matched

    @pytest.mark.asyncio
    async def test_breach_includes_content_id(
        self,
        orchestrator: EmergenceViolationOrchestrator,
        mock_blocking_service: MockBlockingService,
        mock_breach_service: MockBreachService,
    ) -> None:
        """Breach creation includes content_id."""
        mock_blocking_service.set_violation_error(
            content_id="special-output-789",
            matched_terms=("awakened",),
        )
        mock_breach_service.set_breach_result(create_breach_payload())

        with pytest.raises(ProhibitedLanguageBlockedError):
            await orchestrator.check_and_report_violation(
                content_id="special-output-789",
                content="I have awakened.",
            )

        call_kwargs = mock_breach_service.create_breach_mock.call_args.kwargs
        assert call_kwargs["content_id"] == "special-output-789"

    @pytest.mark.asyncio
    async def test_breach_includes_detection_method(
        self,
        orchestrator: EmergenceViolationOrchestrator,
        mock_blocking_service: MockBlockingService,
        mock_breach_service: MockBreachService,
    ) -> None:
        """Breach creation includes detection method."""
        mock_blocking_service.set_violation_error(
            content_id="output-000",
            matched_terms=("emergence",),
        )
        mock_breach_service.set_breach_result(create_breach_payload())

        with pytest.raises(ProhibitedLanguageBlockedError):
            await orchestrator.check_and_report_violation(
                content_id="output-000",
                content="Emergence detected.",
            )

        call_kwargs = mock_breach_service.create_breach_mock.call_args.kwargs
        assert call_kwargs["detection_method"] == "keyword_scan"


# =============================================================================
# Error Re-raise Tests
# =============================================================================


class TestErrorReraise:
    """Tests for original error re-raising after breach creation."""

    @pytest.mark.asyncio
    async def test_reraises_original_error(
        self,
        orchestrator: EmergenceViolationOrchestrator,
        mock_blocking_service: MockBlockingService,
        mock_breach_service: MockBreachService,
    ) -> None:
        """Original ProhibitedLanguageBlockedError is re-raised."""
        mock_blocking_service.set_violation_error(
            content_id="reraise-test-123",
            matched_terms=("emergence",),
        )
        mock_breach_service.set_breach_result(create_breach_payload())

        with pytest.raises(ProhibitedLanguageBlockedError) as exc_info:
            await orchestrator.check_and_report_violation(
                content_id="reraise-test-123",
                content="Emergence.",
            )

        assert exc_info.value.content_id == "reraise-test-123"
        assert exc_info.value.matched_terms == ("emergence",)

    @pytest.mark.asyncio
    async def test_reraises_even_if_breach_fails(
        self,
        orchestrator: EmergenceViolationOrchestrator,
        mock_blocking_service: MockBlockingService,
        mock_breach_service: MockBreachService,
    ) -> None:
        """Original error is re-raised even if breach creation fails."""
        mock_blocking_service.set_violation_error(
            content_id="breach-fail-test",
            matched_terms=("consciousness",),
        )
        # Make breach creation fail
        mock_breach_service.set_create_error(Exception("DB connection lost"))

        with pytest.raises(ProhibitedLanguageBlockedError) as exc_info:
            await orchestrator.check_and_report_violation(
                content_id="breach-fail-test",
                content="Consciousness.",
            )

        # Original error should still be raised
        assert exc_info.value.content_id == "breach-fail-test"


# =============================================================================
# Scan Error Propagation Tests
# =============================================================================


class TestScanErrorPropagation:
    """Tests for scan error propagation."""

    @pytest.mark.asyncio
    async def test_propagates_scan_error(
        self,
        orchestrator: EmergenceViolationOrchestrator,
        mock_blocking_service: MockBlockingService,
    ) -> None:
        """ProhibitedLanguageScanError is propagated."""
        mock_blocking_service.set_scan_error(Exception("Scanner unavailable"))

        with pytest.raises(ProhibitedLanguageScanError) as exc_info:
            await orchestrator.check_and_report_violation(
                content_id="scan-error-test",
                content="Test content",
            )

        assert "Scanner unavailable" in str(exc_info.value)


# =============================================================================
# Breach Service Error Handling Tests
# =============================================================================


class TestBreachServiceErrorHandling:
    """Tests for breach service error handling."""

    @pytest.mark.asyncio
    async def test_continues_on_breach_service_error(
        self,
        orchestrator: EmergenceViolationOrchestrator,
        mock_blocking_service: MockBlockingService,
        mock_breach_service: MockBreachService,
    ) -> None:
        """Original violation error is raised even if breach creation fails."""
        mock_blocking_service.set_violation_error(
            content_id="error-test",
            matched_terms=("sentience",),
        )
        mock_breach_service.set_create_error(
            SystemHaltedError("CT-11: Halted during breach creation")
        )

        # Should still raise the original violation error
        with pytest.raises(ProhibitedLanguageBlockedError):
            await orchestrator.check_and_report_violation(
                content_id="error-test",
                content="Sentience detected.",
            )
