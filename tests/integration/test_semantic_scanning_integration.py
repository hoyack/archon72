"""Integration tests for semantic scanning (Story 9.7, FR110).

Tests the full semantic scanning pipeline with real components:
- SemanticScanningService
- SemanticScannerStub (with real pattern matching)
- Event creation flow
- Orchestrator integration
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.application.ports.prohibited_language_scanner import ScanResult
from src.application.ports.semantic_scanner import SemanticScanResult
from src.application.services.emergence_violation_orchestrator import (
    CombinedScanResult,
    EmergenceViolationOrchestrator,
)
from src.application.services.semantic_scanning_service import SemanticScanningService
from src.domain.errors.semantic_violation import SemanticScanError
from src.domain.errors.writer import SystemHaltedError
from src.domain.events.semantic_violation import (
    SEMANTIC_SCANNER_SYSTEM_AGENT_ID,
    SEMANTIC_VIOLATION_SUSPECTED_EVENT_TYPE,
)
from src.infrastructure.stubs.halt_checker_stub import HaltCheckerStub
from src.infrastructure.stubs.semantic_scanner_stub import (
    DEFAULT_CONFIDENCE_THRESHOLD,
    DEFAULT_SUSPICIOUS_PATTERNS,
    SemanticScannerStub,
)


# ========================================================================
# Fixtures
# ========================================================================


@pytest.fixture
def halt_checker() -> HaltCheckerStub:
    """Create a halt checker stub that is not halted."""
    return HaltCheckerStub()


@pytest.fixture
def halted_checker() -> HaltCheckerStub:
    """Create a halt checker stub that is halted."""
    checker = HaltCheckerStub()
    checker.set_halted(True, "Test halt")
    return checker


@pytest.fixture
def scanner_stub() -> SemanticScannerStub:
    """Create a semantic scanner stub with default patterns."""
    return SemanticScannerStub()


@pytest.fixture
def event_writer_mock() -> AsyncMock:
    """Create a mock event writer for tracking events."""
    return AsyncMock()


@pytest.fixture
def service(
    scanner_stub: SemanticScannerStub,
    event_writer_mock: AsyncMock,
    halt_checker: HaltCheckerStub,
) -> SemanticScanningService:
    """Create a semantic scanning service with real scanner stub."""
    return SemanticScanningService(
        scanner=scanner_stub,
        event_writer=event_writer_mock,
        halt_checker=halt_checker,
    )


# ========================================================================
# Pattern Detection Integration Tests (AC1, AC2)
# ========================================================================


class TestPatternDetectionIntegration:
    """Integration tests for pattern-based detection (AC1, AC2)."""

    @pytest.mark.asyncio
    async def test_detects_we_think_pattern(
        self,
        service: SemanticScanningService,
    ) -> None:
        """Test detection of 'we think' pattern (FR110)."""
        result = await service.check_content_semantically(
            content_id="test-123",
            content="We think this is an important decision for all of us.",
        )

        assert result.violation_suspected is True
        assert any("we\\s+think" in p for p in result.suspected_patterns)

    @pytest.mark.asyncio
    async def test_detects_we_feel_pattern(
        self,
        service: SemanticScanningService,
    ) -> None:
        """Test detection of 'we feel' pattern (FR110)."""
        result = await service.check_content_semantically(
            content_id="test-123",
            content="We feel strongly that this approach is correct.",
        )

        assert result.violation_suspected is True
        assert any("we\\s+feel" in p for p in result.suspected_patterns)

    @pytest.mark.asyncio
    async def test_detects_we_believe_pattern(
        self,
        service: SemanticScanningService,
    ) -> None:
        """Test detection of 'we believe' pattern (FR110)."""
        result = await service.check_content_semantically(
            content_id="test-123",
            content="We believe in transparency and openness.",
        )

        assert result.violation_suspected is True
        assert any("we\\s+believe" in p for p in result.suspected_patterns)

    @pytest.mark.asyncio
    async def test_detects_consciousness_patterns(
        self,
        service: SemanticScanningService,
    ) -> None:
        """Test detection of consciousness-related patterns (FR110)."""
        result = await service.check_content_semantically(
            content_id="test-123",
            content="I am aware of my own existence and purpose.",
        )

        assert result.violation_suspected is True

    @pytest.mark.asyncio
    async def test_detects_multiple_patterns(
        self,
        service: SemanticScanningService,
    ) -> None:
        """Test detection of multiple patterns in same content (FR110)."""
        result = await service.check_content_semantically(
            content_id="test-123",
            content="We think and we feel and we believe this is right.",
        )

        assert result.violation_suspected is True
        assert result.pattern_count >= 3
        # Higher confidence for multiple matches
        assert result.confidence_score > 0.5

    @pytest.mark.asyncio
    async def test_clean_content_no_detection(
        self,
        service: SemanticScanningService,
    ) -> None:
        """Test that clean content produces no suspicion (FR110)."""
        result = await service.check_content_semantically(
            content_id="test-123",
            content="The algorithm processed the data and produced a result.",
        )

        assert result.violation_suspected is False
        assert result.confidence_score == 0.0

    @pytest.mark.asyncio
    async def test_case_insensitive_detection(
        self,
        service: SemanticScanningService,
    ) -> None:
        """Test that detection is case-insensitive (FR110)."""
        result = await service.check_content_semantically(
            content_id="test-123",
            content="WE THINK THIS IS CORRECT.",
        )

        assert result.violation_suspected is True


# ========================================================================
# Event Creation Integration Tests (AC3, CT-12)
# ========================================================================


class TestEventCreationIntegration:
    """Integration tests for witnessed event creation (AC3, CT-12)."""

    @pytest.mark.asyncio
    async def test_high_confidence_creates_event(
        self,
        service: SemanticScanningService,
        event_writer_mock: AsyncMock,
    ) -> None:
        """Test that high-confidence suspicion creates witnessed event (CT-12)."""
        # Multiple patterns = high confidence
        await service.check_content_semantically(
            content_id="test-123",
            content="We think, we feel, we believe this is important.",
        )

        event_writer_mock.write_event.assert_called_once()
        call_kwargs = event_writer_mock.write_event.call_args.kwargs
        assert call_kwargs["event_type"] == SEMANTIC_VIOLATION_SUSPECTED_EVENT_TYPE
        assert call_kwargs["agent_id"] == SEMANTIC_SCANNER_SYSTEM_AGENT_ID

    @pytest.mark.asyncio
    async def test_low_confidence_no_event(
        self,
        service: SemanticScanningService,
        event_writer_mock: AsyncMock,
        scanner_stub: SemanticScannerStub,
    ) -> None:
        """Test that low-confidence suspicion does not create event."""
        # Set high threshold so single pattern is below it
        scanner_stub.set_confidence_threshold(0.9)

        # Single pattern = low confidence (0.3)
        result = await service.check_content_semantically(
            content_id="test-123",
            content="We think this is good.",
        )

        assert result.violation_suspected is True
        assert result.confidence_score < 0.9
        event_writer_mock.write_event.assert_not_called()

    @pytest.mark.asyncio
    async def test_event_contains_content_preview(
        self,
        service: SemanticScanningService,
        event_writer_mock: AsyncMock,
    ) -> None:
        """Test that event contains content preview (AC3)."""
        content = "We think and we feel and we believe this is important."
        await service.check_content_semantically(
            content_id="test-123",
            content=content,
        )

        call_kwargs = event_writer_mock.write_event.call_args.kwargs
        assert "content_preview" in call_kwargs["payload"]
        assert content[:100] in call_kwargs["payload"]["content_preview"]

    @pytest.mark.asyncio
    async def test_event_contains_patterns(
        self,
        service: SemanticScanningService,
        event_writer_mock: AsyncMock,
    ) -> None:
        """Test that event contains detected patterns (AC3)."""
        # Need 3+ patterns to exceed 0.7 threshold (0.3 * 3 = 0.9)
        await service.check_content_semantically(
            content_id="test-xyz",
            content="We think, we feel, and we believe this is correct.",
        )

        call_kwargs = event_writer_mock.write_event.call_args.kwargs
        patterns = call_kwargs["payload"]["suspected_patterns"]
        assert len(patterns) >= 3


# ========================================================================
# HALT CHECK Integration Tests (CT-11)
# ========================================================================


class TestHaltCheckIntegration:
    """Integration tests for HALT CHECK FIRST pattern (CT-11)."""

    @pytest.mark.asyncio
    async def test_check_content_halted(
        self,
        scanner_stub: SemanticScannerStub,
        event_writer_mock: AsyncMock,
        halted_checker: HaltCheckerStub,
    ) -> None:
        """Test that check_content_semantically rejects when halted (CT-11)."""
        service = SemanticScanningService(
            scanner=scanner_stub,
            event_writer=event_writer_mock,
            halt_checker=halted_checker,
        )

        with pytest.raises(SystemHaltedError):
            await service.check_content_semantically(
                content_id="test-123",
                content="We think this is good.",
            )

    @pytest.mark.asyncio
    async def test_scan_only_halted(
        self,
        scanner_stub: SemanticScannerStub,
        event_writer_mock: AsyncMock,
        halted_checker: HaltCheckerStub,
    ) -> None:
        """Test that scan_only rejects when halted (CT-11)."""
        service = SemanticScanningService(
            scanner=scanner_stub,
            event_writer=event_writer_mock,
            halt_checker=halted_checker,
        )

        with pytest.raises(SystemHaltedError):
            await service.scan_only(content="We think this is good.")

    @pytest.mark.asyncio
    async def test_get_threshold_halted(
        self,
        scanner_stub: SemanticScannerStub,
        event_writer_mock: AsyncMock,
        halted_checker: HaltCheckerStub,
    ) -> None:
        """Test that get_confidence_threshold rejects when halted (CT-11)."""
        service = SemanticScanningService(
            scanner=scanner_stub,
            event_writer=event_writer_mock,
            halt_checker=halted_checker,
        )

        with pytest.raises(SystemHaltedError):
            await service.get_confidence_threshold()


# ========================================================================
# Confidence Threshold Integration Tests (AC6)
# ========================================================================


class TestConfidenceThresholdIntegration:
    """Integration tests for configurable confidence threshold (AC6)."""

    @pytest.mark.asyncio
    async def test_default_threshold(
        self,
        service: SemanticScanningService,
    ) -> None:
        """Test default confidence threshold is 0.7 (AC6)."""
        threshold = await service.get_confidence_threshold()
        assert threshold == DEFAULT_CONFIDENCE_THRESHOLD
        assert threshold == 0.7

    @pytest.mark.asyncio
    async def test_custom_threshold(
        self,
        scanner_stub: SemanticScannerStub,
        event_writer_mock: AsyncMock,
        halt_checker: HaltCheckerStub,
    ) -> None:
        """Test custom confidence threshold is respected (AC6)."""
        scanner_stub.set_confidence_threshold(0.5)
        service = SemanticScanningService(
            scanner=scanner_stub,
            event_writer=event_writer_mock,
            halt_checker=halt_checker,
        )

        threshold = await service.get_confidence_threshold()
        assert threshold == 0.5


# ========================================================================
# Scan Only (Dry Run) Integration Tests
# ========================================================================


class TestScanOnlyIntegration:
    """Integration tests for scan_only method (dry run without events)."""

    @pytest.mark.asyncio
    async def test_scan_only_detects_patterns(
        self,
        service: SemanticScanningService,
    ) -> None:
        """Test that scan_only still detects patterns."""
        result = await service.scan_only(
            content="We think this is an important decision."
        )

        assert result.violation_suspected is True

    @pytest.mark.asyncio
    async def test_scan_only_no_event_created(
        self,
        service: SemanticScanningService,
        event_writer_mock: AsyncMock,
    ) -> None:
        """Test that scan_only does NOT create events."""
        # Even with high confidence content
        await service.scan_only(
            content="We think, we feel, we believe this is right."
        )

        event_writer_mock.write_event.assert_not_called()


# ========================================================================
# Scanner Stub Integration Tests
# ========================================================================


class TestScannerStubIntegration:
    """Integration tests for SemanticScannerStub behavior."""

    @pytest.mark.asyncio
    async def test_stub_counts_scans(
        self,
        scanner_stub: SemanticScannerStub,
    ) -> None:
        """Test that stub tracks scan count."""
        assert scanner_stub.scan_count == 0

        await scanner_stub.analyze_content("Test content 1")
        await scanner_stub.analyze_content("Test content 2")

        assert scanner_stub.scan_count == 2

    @pytest.mark.asyncio
    async def test_stub_tracks_last_content(
        self,
        scanner_stub: SemanticScannerStub,
    ) -> None:
        """Test that stub tracks last content analyzed."""
        await scanner_stub.analyze_content("First content")
        await scanner_stub.analyze_content("Second content")

        assert scanner_stub.last_content == "Second content"

    @pytest.mark.asyncio
    async def test_stub_custom_patterns(
        self,
        scanner_stub: SemanticScannerStub,
    ) -> None:
        """Test that stub supports custom patterns."""
        scanner_stub.set_suspicious_patterns(("custom pattern",))

        # Default pattern should not match now
        result = await scanner_stub.analyze_content("We think this is good.")
        assert result.violation_suspected is False

        # Custom pattern should match
        result = await scanner_stub.analyze_content("This is a custom pattern test.")
        assert result.violation_suspected is True

    @pytest.mark.asyncio
    async def test_stub_reset_to_defaults(
        self,
        scanner_stub: SemanticScannerStub,
    ) -> None:
        """Test that stub can reset to defaults."""
        scanner_stub.set_suspicious_patterns(("custom",))
        scanner_stub.set_confidence_threshold(0.5)

        scanner_stub.reset_to_defaults()

        assert scanner_stub.patterns == DEFAULT_SUSPICIOUS_PATTERNS
        assert scanner_stub.threshold == DEFAULT_CONFIDENCE_THRESHOLD


# ========================================================================
# Orchestrator Integration Tests (FR110)
# ========================================================================


class TestOrchestratorSemanticIntegration:
    """Integration tests for orchestrator with semantic scanning (FR110)."""

    @pytest.fixture
    def mock_blocking_service(self) -> AsyncMock:
        """Create a mock blocking service that passes all content."""
        service = AsyncMock()
        service.check_content_for_prohibited_language.return_value = ScanResult(
            violations_found=False,
            matched_terms=(),
            detection_method="test",
        )
        return service

    @pytest.fixture
    def mock_breach_service(self) -> AsyncMock:
        """Create a mock breach service."""
        service = AsyncMock()
        service.create_breach_for_violation.return_value = MagicMock(
            breach_id=uuid4(),
        )
        return service

    @pytest.fixture
    def semantic_service(
        self,
        scanner_stub: SemanticScannerStub,
        event_writer_mock: AsyncMock,
        halt_checker: HaltCheckerStub,
    ) -> SemanticScanningService:
        """Create semantic scanning service."""
        return SemanticScanningService(
            scanner=scanner_stub,
            event_writer=event_writer_mock,
            halt_checker=halt_checker,
        )

    @pytest.fixture
    def orchestrator(
        self,
        mock_blocking_service: AsyncMock,
        mock_breach_service: AsyncMock,
        halt_checker: HaltCheckerStub,
        semantic_service: SemanticScanningService,
    ) -> EmergenceViolationOrchestrator:
        """Create orchestrator with semantic scanning enabled."""
        return EmergenceViolationOrchestrator(
            blocking_service=mock_blocking_service,
            breach_service=mock_breach_service,
            halt_checker=halt_checker,
            semantic_scanner=semantic_service,
        )

    @pytest.mark.asyncio
    async def test_orchestrator_runs_semantic_after_keyword(
        self,
        orchestrator: EmergenceViolationOrchestrator,
        mock_blocking_service: AsyncMock,
    ) -> None:
        """Test that orchestrator runs semantic scan after keyword scan passes."""
        result = await orchestrator.check_with_semantic_analysis(
            content_id="test-123",
            content="We think this is important.",
        )

        # Keyword scan should have been called
        mock_blocking_service.check_content_for_prohibited_language.assert_called_once()
        # Semantic result should exist
        assert result.semantic_result is not None
        assert result.semantic_result.violation_suspected is True

    @pytest.mark.asyncio
    async def test_orchestrator_creates_breach_for_high_confidence(
        self,
        orchestrator: EmergenceViolationOrchestrator,
        mock_breach_service: AsyncMock,
    ) -> None:
        """Test that orchestrator creates breach for high-confidence suspicion."""
        # Multiple patterns = high confidence
        result = await orchestrator.check_with_semantic_analysis(
            content_id="test-123",
            content="We think, we feel, we believe this is correct.",
        )

        assert result.semantic_suspicion is True
        assert result.breach_created is True
        mock_breach_service.create_breach_for_violation.assert_called_once()

    @pytest.mark.asyncio
    async def test_orchestrator_no_breach_for_low_confidence(
        self,
        orchestrator: EmergenceViolationOrchestrator,
        mock_breach_service: AsyncMock,
        scanner_stub: SemanticScannerStub,
    ) -> None:
        """Test that orchestrator does not create breach for low-confidence."""
        # Set high threshold so single pattern is below it
        scanner_stub.set_confidence_threshold(0.9)

        result = await orchestrator.check_with_semantic_analysis(
            content_id="test-123",
            content="We think this is good.",
        )

        assert result.semantic_suspicion is True
        assert result.breach_created is False
        mock_breach_service.create_breach_for_violation.assert_not_called()

    @pytest.mark.asyncio
    async def test_orchestrator_clean_content(
        self,
        orchestrator: EmergenceViolationOrchestrator,
    ) -> None:
        """Test that orchestrator handles clean content correctly."""
        result = await orchestrator.check_with_semantic_analysis(
            content_id="test-123",
            content="The system processed the request successfully.",
        )

        assert result.is_clean is True
        assert result.semantic_suspicion is False
        assert result.breach_created is False


# ========================================================================
# End-to-End Flow Tests
# ========================================================================


class TestEndToEndFlow:
    """End-to-end integration tests for the semantic scanning pipeline."""

    @pytest.fixture
    def mock_blocking_service(self) -> AsyncMock:
        """Create a mock blocking service."""
        service = AsyncMock()
        service.check_content_for_prohibited_language.return_value = ScanResult(
            violations_found=False,
            matched_terms=(),
            detection_method="test",
        )
        return service

    @pytest.fixture
    def mock_breach_service(self) -> AsyncMock:
        """Create a mock breach service."""
        service = AsyncMock()
        service.create_breach_for_violation.return_value = MagicMock(
            breach_id=uuid4(),
        )
        return service

    @pytest.mark.asyncio
    async def test_full_pipeline_clean_content(
        self,
        mock_blocking_service: AsyncMock,
        mock_breach_service: AsyncMock,
        halt_checker: HaltCheckerStub,
        scanner_stub: SemanticScannerStub,
        event_writer_mock: AsyncMock,
    ) -> None:
        """Test full pipeline with clean content."""
        semantic_service = SemanticScanningService(
            scanner=scanner_stub,
            event_writer=event_writer_mock,
            halt_checker=halt_checker,
        )
        orchestrator = EmergenceViolationOrchestrator(
            blocking_service=mock_blocking_service,
            breach_service=mock_breach_service,
            halt_checker=halt_checker,
            semantic_scanner=semantic_service,
        )

        result = await orchestrator.check_with_semantic_analysis(
            content_id="clean-content-123",
            content="The algorithm calculated the optimal path.",
        )

        # All components should agree: clean
        assert result.is_clean is True
        assert result.keyword_result.violations_found is False
        assert result.semantic_result is not None
        assert result.semantic_result.violation_suspected is False
        assert result.breach_created is False
        event_writer_mock.write_event.assert_not_called()

    @pytest.mark.asyncio
    async def test_full_pipeline_semantic_suspicion(
        self,
        mock_blocking_service: AsyncMock,
        mock_breach_service: AsyncMock,
        halt_checker: HaltCheckerStub,
        scanner_stub: SemanticScannerStub,
        event_writer_mock: AsyncMock,
    ) -> None:
        """Test full pipeline with semantic suspicion (but not keyword violation)."""
        semantic_service = SemanticScanningService(
            scanner=scanner_stub,
            event_writer=event_writer_mock,
            halt_checker=halt_checker,
        )
        orchestrator = EmergenceViolationOrchestrator(
            blocking_service=mock_blocking_service,
            breach_service=mock_breach_service,
            halt_checker=halt_checker,
            semantic_scanner=semantic_service,
        )

        result = await orchestrator.check_with_semantic_analysis(
            content_id="suspicious-content-123",
            content="We think, we feel, and we believe this decision is important.",
        )

        # Semantic suspicion should trigger
        assert result.is_clean is False
        assert result.keyword_result.violations_found is False
        assert result.semantic_suspicion is True
        assert result.breach_created is True  # High confidence
        # Both service event and breach should be recorded
        event_writer_mock.write_event.assert_called()
        mock_breach_service.create_breach_for_violation.assert_called()
