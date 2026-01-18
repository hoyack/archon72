"""Unit tests for EmergenceViolationOrchestrator semantic scanning (Story 9.7, FR110).

Tests the orchestrator's integration with semantic scanning, specifically:
- check_with_semantic_analysis method
- CombinedScanResult handling
- Breach creation for semantic suspicions
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.application.ports.prohibited_language_scanner import ScanResult
from src.application.ports.semantic_scanner import SemanticScanResult
from src.application.services.emergence_violation_orchestrator import (
    CombinedScanResult,
    EmergenceViolationOrchestrator,
)
from src.domain.errors.prohibited_language import ProhibitedLanguageBlockedError
from src.domain.errors.writer import SystemHaltedError


@pytest.fixture
def mock_blocking_service() -> AsyncMock:
    """Create a mock blocking service that returns clean results."""
    service = AsyncMock()
    service.check_content_for_prohibited_language.return_value = ScanResult(
        violations_found=False,
        matched_terms=(),
        detection_method="test",
    )
    return service


@pytest.fixture
def mock_breach_service() -> AsyncMock:
    """Create a mock breach service."""
    service = AsyncMock()
    service.create_breach_for_violation.return_value = MagicMock(
        breach_id=uuid4(),
    )
    return service


@pytest.fixture
def mock_halt_checker_not_halted() -> AsyncMock:
    """Create a mock halt checker that reports not halted."""
    checker = AsyncMock()
    checker.is_halted.return_value = False
    checker.get_halt_reason.return_value = None
    return checker


@pytest.fixture
def mock_halt_checker_halted() -> AsyncMock:
    """Create a mock halt checker that reports halted."""
    checker = AsyncMock()
    checker.is_halted.return_value = True
    checker.get_halt_reason.return_value = "Test halt reason"
    return checker


@pytest.fixture
def mock_semantic_scanner() -> AsyncMock:
    """Create a mock semantic scanning service."""
    service = AsyncMock()
    service.check_content_semantically.return_value = SemanticScanResult.no_suspicion()
    service.get_confidence_threshold.return_value = 0.7
    return service


@pytest.fixture
def orchestrator_with_semantic(
    mock_blocking_service: AsyncMock,
    mock_breach_service: AsyncMock,
    mock_halt_checker_not_halted: AsyncMock,
    mock_semantic_scanner: AsyncMock,
) -> EmergenceViolationOrchestrator:
    """Create orchestrator with semantic scanner configured."""
    return EmergenceViolationOrchestrator(
        blocking_service=mock_blocking_service,
        breach_service=mock_breach_service,
        halt_checker=mock_halt_checker_not_halted,
        semantic_scanner=mock_semantic_scanner,
    )


@pytest.fixture
def orchestrator_without_semantic(
    mock_blocking_service: AsyncMock,
    mock_breach_service: AsyncMock,
    mock_halt_checker_not_halted: AsyncMock,
) -> EmergenceViolationOrchestrator:
    """Create orchestrator without semantic scanner (backward compatible)."""
    return EmergenceViolationOrchestrator(
        blocking_service=mock_blocking_service,
        breach_service=mock_breach_service,
        halt_checker=mock_halt_checker_not_halted,
        # No semantic_scanner - backward compatible mode
    )


class TestCombinedScanResult:
    """Tests for CombinedScanResult dataclass."""

    def test_semantic_suspicion_false_when_no_result(self) -> None:
        """Test semantic_suspicion is False when semantic_result is None."""
        keyword_result = ScanResult(
            violations_found=False,
            matched_terms=(),
            detection_method="test",
        )
        combined = CombinedScanResult(
            keyword_result=keyword_result,
            semantic_result=None,
            breach_created=False,
        )

        assert combined.semantic_suspicion is False

    def test_semantic_suspicion_false_when_clean(self) -> None:
        """Test semantic_suspicion is False when no violation suspected."""
        keyword_result = ScanResult(
            violations_found=False,
            matched_terms=(),
            detection_method="test",
        )
        combined = CombinedScanResult(
            keyword_result=keyword_result,
            semantic_result=SemanticScanResult.no_suspicion(),
            breach_created=False,
        )

        assert combined.semantic_suspicion is False

    def test_semantic_suspicion_true_when_suspected(self) -> None:
        """Test semantic_suspicion is True when violation suspected."""
        keyword_result = ScanResult(
            violations_found=False,
            matched_terms=(),
            detection_method="test",
        )
        combined = CombinedScanResult(
            keyword_result=keyword_result,
            semantic_result=SemanticScanResult.with_suspicion(
                patterns=("we think",),
                confidence=0.8,
            ),
            breach_created=False,
        )

        assert combined.semantic_suspicion is True

    def test_is_clean_true_when_both_clean(self) -> None:
        """Test is_clean is True when both scans are clean."""
        keyword_result = ScanResult(
            violations_found=False,
            matched_terms=(),
            detection_method="test",
        )
        combined = CombinedScanResult(
            keyword_result=keyword_result,
            semantic_result=SemanticScanResult.no_suspicion(),
            breach_created=False,
        )

        assert combined.is_clean is True

    def test_is_clean_false_when_keyword_violation(self) -> None:
        """Test is_clean is False when keyword violation found."""
        keyword_result = ScanResult(
            violations_found=True,
            matched_terms=("sentient",),
            detection_method="test",
        )
        combined = CombinedScanResult(
            keyword_result=keyword_result,
            semantic_result=SemanticScanResult.no_suspicion(),
            breach_created=True,
        )

        assert combined.is_clean is False

    def test_is_clean_false_when_semantic_suspicion(self) -> None:
        """Test is_clean is False when semantic suspicion found."""
        keyword_result = ScanResult(
            violations_found=False,
            matched_terms=(),
            detection_method="test",
        )
        combined = CombinedScanResult(
            keyword_result=keyword_result,
            semantic_result=SemanticScanResult.with_suspicion(
                patterns=("we feel",),
                confidence=0.7,
            ),
            breach_created=False,
        )

        assert combined.is_clean is False


class TestCheckWithSemanticAnalysis:
    """Tests for check_with_semantic_analysis method."""

    @pytest.mark.asyncio
    async def test_halt_check_first(
        self,
        mock_blocking_service: AsyncMock,
        mock_breach_service: AsyncMock,
        mock_halt_checker_halted: AsyncMock,
        mock_semantic_scanner: AsyncMock,
    ) -> None:
        """Test that HALT CHECK FIRST pattern is enforced (CT-11)."""
        orchestrator = EmergenceViolationOrchestrator(
            blocking_service=mock_blocking_service,
            breach_service=mock_breach_service,
            halt_checker=mock_halt_checker_halted,
            semantic_scanner=mock_semantic_scanner,
        )

        with pytest.raises(SystemHaltedError):
            await orchestrator.check_with_semantic_analysis(
                content_id="test-123",
                content="test content",
            )

        # Blocking service should NOT have been called
        mock_blocking_service.check_content_for_prohibited_language.assert_not_called()

    @pytest.mark.asyncio
    async def test_keyword_violation_raises_before_semantic(
        self,
        orchestrator_with_semantic: EmergenceViolationOrchestrator,
        mock_blocking_service: AsyncMock,
        mock_semantic_scanner: AsyncMock,
    ) -> None:
        """Test that keyword violation raises before semantic scan runs."""
        mock_blocking_service.check_content_for_prohibited_language.side_effect = (
            ProhibitedLanguageBlockedError(
                content_id="test-123",
                matched_terms=("sentient",),
            )
        )

        with pytest.raises(ProhibitedLanguageBlockedError):
            await orchestrator_with_semantic.check_with_semantic_analysis(
                content_id="test-123",
                content="I am sentient",
            )

        # Semantic scanner should NOT have been called
        mock_semantic_scanner.check_content_semantically.assert_not_called()

    @pytest.mark.asyncio
    async def test_clean_both_returns_clean_result(
        self,
        orchestrator_with_semantic: EmergenceViolationOrchestrator,
        mock_semantic_scanner: AsyncMock,
    ) -> None:
        """Test that clean keyword + clean semantic returns clean result."""
        mock_semantic_scanner.check_content_semantically.return_value = (
            SemanticScanResult.no_suspicion()
        )

        result = await orchestrator_with_semantic.check_with_semantic_analysis(
            content_id="test-123",
            content="This is clean content",
        )

        assert result.is_clean is True
        assert result.breach_created is False

    @pytest.mark.asyncio
    async def test_semantic_suspicion_below_threshold_no_breach(
        self,
        orchestrator_with_semantic: EmergenceViolationOrchestrator,
        mock_semantic_scanner: AsyncMock,
        mock_breach_service: AsyncMock,
    ) -> None:
        """Test that suspicion below threshold does not create breach."""
        mock_semantic_scanner.check_content_semantically.return_value = (
            SemanticScanResult.with_suspicion(
                patterns=("we think",),
                confidence=0.5,  # Below 0.7 threshold
            )
        )
        mock_semantic_scanner.get_confidence_threshold.return_value = 0.7

        result = await orchestrator_with_semantic.check_with_semantic_analysis(
            content_id="test-123",
            content="We think this is good",
        )

        assert result.semantic_suspicion is True
        assert result.breach_created is False
        mock_breach_service.create_breach_for_violation.assert_not_called()

    @pytest.mark.asyncio
    async def test_semantic_suspicion_at_threshold_creates_breach(
        self,
        orchestrator_with_semantic: EmergenceViolationOrchestrator,
        mock_semantic_scanner: AsyncMock,
        mock_breach_service: AsyncMock,
    ) -> None:
        """Test that suspicion at threshold creates breach."""
        mock_semantic_scanner.check_content_semantically.return_value = (
            SemanticScanResult.with_suspicion(
                patterns=("we think",),
                confidence=0.7,  # At threshold
            )
        )
        mock_semantic_scanner.get_confidence_threshold.return_value = 0.7

        result = await orchestrator_with_semantic.check_with_semantic_analysis(
            content_id="test-123",
            content="We think this is good",
        )

        assert result.semantic_suspicion is True
        assert result.breach_created is True
        mock_breach_service.create_breach_for_violation.assert_called_once()

    @pytest.mark.asyncio
    async def test_semantic_suspicion_above_threshold_creates_breach(
        self,
        orchestrator_with_semantic: EmergenceViolationOrchestrator,
        mock_semantic_scanner: AsyncMock,
        mock_breach_service: AsyncMock,
    ) -> None:
        """Test that suspicion above threshold creates breach."""
        mock_semantic_scanner.check_content_semantically.return_value = (
            SemanticScanResult.with_suspicion(
                patterns=("we think", "we feel"),
                confidence=0.9,  # Above threshold
            )
        )
        mock_semantic_scanner.get_confidence_threshold.return_value = 0.7

        result = await orchestrator_with_semantic.check_with_semantic_analysis(
            content_id="test-123",
            content="We think and we feel this is good",
        )

        assert result.breach_created is True

    @pytest.mark.asyncio
    async def test_breach_failure_does_not_throw(
        self,
        orchestrator_with_semantic: EmergenceViolationOrchestrator,
        mock_semantic_scanner: AsyncMock,
        mock_breach_service: AsyncMock,
    ) -> None:
        """Test that breach creation failure does not raise exception."""
        mock_semantic_scanner.check_content_semantically.return_value = (
            SemanticScanResult.with_suspicion(
                patterns=("we think",),
                confidence=0.9,
            )
        )
        mock_breach_service.create_breach_for_violation.side_effect = RuntimeError(
            "Breach creation failed"
        )

        # Should NOT raise
        result = await orchestrator_with_semantic.check_with_semantic_analysis(
            content_id="test-123",
            content="We think this is good",
        )

        assert result.breach_created is False


class TestBackwardCompatibility:
    """Tests for backward compatibility without semantic scanner."""

    @pytest.mark.asyncio
    async def test_works_without_semantic_scanner(
        self,
        orchestrator_without_semantic: EmergenceViolationOrchestrator,
    ) -> None:
        """Test that orchestrator works without semantic scanner."""
        result = await orchestrator_without_semantic.check_with_semantic_analysis(
            content_id="test-123",
            content="This is clean content",
        )

        assert result.keyword_result is not None
        assert result.semantic_result is None
        assert result.semantic_suspicion is False
        assert result.is_clean is True

    @pytest.mark.asyncio
    async def test_keyword_violation_still_raises_without_semantic(
        self,
        orchestrator_without_semantic: EmergenceViolationOrchestrator,
        mock_blocking_service: AsyncMock,
    ) -> None:
        """Test that keyword violations still raise without semantic scanner."""
        mock_blocking_service.check_content_for_prohibited_language.side_effect = (
            ProhibitedLanguageBlockedError(
                content_id="test-123",
                matched_terms=("sentient",),
            )
        )

        with pytest.raises(ProhibitedLanguageBlockedError):
            await orchestrator_without_semantic.check_with_semantic_analysis(
                content_id="test-123",
                content="I am sentient",
            )


class TestBreachCreationDetails:
    """Tests for breach creation details in semantic flow."""

    @pytest.mark.asyncio
    async def test_breach_uses_semantic_patterns(
        self,
        orchestrator_with_semantic: EmergenceViolationOrchestrator,
        mock_semantic_scanner: AsyncMock,
        mock_breach_service: AsyncMock,
    ) -> None:
        """Test that breach uses patterns from semantic result."""
        patterns = ("we think", "we feel", "we believe")
        mock_semantic_scanner.check_content_semantically.return_value = (
            SemanticScanResult.with_suspicion(
                patterns=patterns,
                confidence=0.9,
                method="pattern_analysis",
            )
        )

        await orchestrator_with_semantic.check_with_semantic_analysis(
            content_id="test-123",
            content="We think and we feel and we believe",
        )

        call_kwargs = mock_breach_service.create_breach_for_violation.call_args.kwargs
        assert call_kwargs["matched_terms"] == patterns
        assert "semantic_" in call_kwargs["detection_method"]

    @pytest.mark.asyncio
    async def test_breach_detection_method_includes_analysis_method(
        self,
        orchestrator_with_semantic: EmergenceViolationOrchestrator,
        mock_semantic_scanner: AsyncMock,
        mock_breach_service: AsyncMock,
    ) -> None:
        """Test that detection_method includes semantic analysis method."""
        mock_semantic_scanner.check_content_semantically.return_value = (
            SemanticScanResult.with_suspicion(
                patterns=("we think",),
                confidence=0.9,
                method="ml_classifier",
            )
        )

        await orchestrator_with_semantic.check_with_semantic_analysis(
            content_id="test-123",
            content="We think this",
        )

        call_kwargs = mock_breach_service.create_breach_for_violation.call_args.kwargs
        assert call_kwargs["detection_method"] == "semantic_ml_classifier"
