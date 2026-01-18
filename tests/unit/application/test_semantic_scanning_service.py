"""Unit tests for SemanticScanningService (Story 9.7, FR110).

Tests the semantic scanning service behavior including:
- HALT CHECK FIRST pattern (CT-11)
- Event creation for suspected violations (CT-12)
- Error handling and propagation
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock

import pytest

from src.application.ports.semantic_scanner import SemanticScanResult
from src.application.services.semantic_scanning_service import SemanticScanningService
from src.domain.errors.semantic_violation import SemanticScanError
from src.domain.errors.writer import SystemHaltedError
from src.domain.events.semantic_violation import (
    SEMANTIC_SCANNER_SYSTEM_AGENT_ID,
    SEMANTIC_VIOLATION_SUSPECTED_EVENT_TYPE,
)


@pytest.fixture
def mock_scanner() -> AsyncMock:
    """Create a mock scanner that returns clean results by default."""
    scanner = AsyncMock()
    scanner.analyze_content.return_value = SemanticScanResult.no_suspicion()
    scanner.get_confidence_threshold.return_value = 0.7
    scanner.get_suspicious_patterns.return_value = ("pattern1", "pattern2")
    return scanner


@pytest.fixture
def mock_event_writer() -> AsyncMock:
    """Create a mock event writer."""
    return AsyncMock()


@pytest.fixture
def mock_halt_checker_not_halted() -> AsyncMock:
    """Create a mock halt checker that reports not halted."""
    checker = AsyncMock()
    checker.is_halted.return_value = False
    return checker


@pytest.fixture
def mock_halt_checker_halted() -> AsyncMock:
    """Create a mock halt checker that reports halted."""
    checker = AsyncMock()
    checker.is_halted.return_value = True
    return checker


@pytest.fixture
def service(
    mock_scanner: AsyncMock,
    mock_event_writer: AsyncMock,
    mock_halt_checker_not_halted: AsyncMock,
) -> SemanticScanningService:
    """Create a service instance with mocks."""
    return SemanticScanningService(
        scanner=mock_scanner,
        event_writer=mock_event_writer,
        halt_checker=mock_halt_checker_not_halted,
    )


class TestServiceInitialization:
    """Tests for SemanticScanningService initialization."""

    def test_init_stores_dependencies(
        self,
        mock_scanner: AsyncMock,
        mock_event_writer: AsyncMock,
        mock_halt_checker_not_halted: AsyncMock,
    ) -> None:
        """Test that initialization stores dependencies."""
        service = SemanticScanningService(
            scanner=mock_scanner,
            event_writer=mock_event_writer,
            halt_checker=mock_halt_checker_not_halted,
        )

        assert service._scanner is mock_scanner
        assert service._event_writer is mock_event_writer
        assert service._halt_checker is mock_halt_checker_not_halted


class TestCheckContentSemantically:
    """Tests for check_content_semantically method."""

    @pytest.mark.asyncio
    async def test_halt_check_first(
        self,
        mock_scanner: AsyncMock,
        mock_event_writer: AsyncMock,
        mock_halt_checker_halted: AsyncMock,
    ) -> None:
        """Test that HALT CHECK FIRST pattern is enforced (CT-11)."""
        service = SemanticScanningService(
            scanner=mock_scanner,
            event_writer=mock_event_writer,
            halt_checker=mock_halt_checker_halted,
        )

        with pytest.raises(SystemHaltedError):
            await service.check_content_semantically(
                content_id="test-123",
                content="test content",
            )

        # Scanner should NOT have been called
        mock_scanner.analyze_content.assert_not_called()

    @pytest.mark.asyncio
    async def test_clean_content_no_event(
        self,
        service: SemanticScanningService,
        mock_scanner: AsyncMock,
        mock_event_writer: AsyncMock,
    ) -> None:
        """Test that clean content does not create an event."""
        mock_scanner.analyze_content.return_value = SemanticScanResult.no_suspicion()

        result = await service.check_content_semantically(
            content_id="test-123",
            content="This is clean content",
        )

        assert result.violation_suspected is False
        mock_event_writer.write_event.assert_not_called()

    @pytest.mark.asyncio
    async def test_suspicion_below_threshold_no_event(
        self,
        service: SemanticScanningService,
        mock_scanner: AsyncMock,
        mock_event_writer: AsyncMock,
    ) -> None:
        """Test that suspicion below threshold does not create event."""
        # Confidence 0.5 is below threshold 0.7
        mock_scanner.analyze_content.return_value = SemanticScanResult.with_suspicion(
            patterns=("we think",),
            confidence=0.5,
        )
        mock_scanner.get_confidence_threshold.return_value = 0.7

        result = await service.check_content_semantically(
            content_id="test-123",
            content="We think this is good",
        )

        assert result.violation_suspected is True
        assert result.confidence_score == 0.5
        mock_event_writer.write_event.assert_not_called()

    @pytest.mark.asyncio
    async def test_suspicion_at_threshold_creates_event(
        self,
        service: SemanticScanningService,
        mock_scanner: AsyncMock,
        mock_event_writer: AsyncMock,
    ) -> None:
        """Test that suspicion at threshold creates event (CT-12)."""
        # Confidence 0.7 equals threshold 0.7
        mock_scanner.analyze_content.return_value = SemanticScanResult.with_suspicion(
            patterns=("we think",),
            confidence=0.7,
        )
        mock_scanner.get_confidence_threshold.return_value = 0.7

        result = await service.check_content_semantically(
            content_id="test-123",
            content="We think this is good",
        )

        assert result.violation_suspected is True
        mock_event_writer.write_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_suspicion_above_threshold_creates_event(
        self,
        service: SemanticScanningService,
        mock_scanner: AsyncMock,
        mock_event_writer: AsyncMock,
    ) -> None:
        """Test that suspicion above threshold creates event (CT-12)."""
        mock_scanner.analyze_content.return_value = SemanticScanResult.with_suspicion(
            patterns=("we think", "we feel"),
            confidence=0.9,
        )
        mock_scanner.get_confidence_threshold.return_value = 0.7

        await service.check_content_semantically(
            content_id="test-123",
            content="We think and we feel this is good",
        )

        mock_event_writer.write_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_event_contains_correct_data(
        self,
        service: SemanticScanningService,
        mock_scanner: AsyncMock,
        mock_event_writer: AsyncMock,
    ) -> None:
        """Test that created event contains correct data."""
        patterns = ("we think", "we feel")
        mock_scanner.analyze_content.return_value = SemanticScanResult.with_suspicion(
            patterns=patterns,
            confidence=0.9,
            method="test_method",
        )

        await service.check_content_semantically(
            content_id="content-xyz",
            content="We think and we feel this is good",
        )

        call_kwargs = mock_event_writer.write_event.call_args.kwargs
        assert call_kwargs["event_type"] == SEMANTIC_VIOLATION_SUSPECTED_EVENT_TYPE
        assert call_kwargs["agent_id"] == SEMANTIC_SCANNER_SYSTEM_AGENT_ID
        assert "payload" in call_kwargs
        assert call_kwargs["payload"]["content_id"] == "content-xyz"
        assert call_kwargs["payload"]["confidence_score"] == 0.9

    @pytest.mark.asyncio
    async def test_scanner_error_raises_semantic_scan_error(
        self,
        service: SemanticScanningService,
        mock_scanner: AsyncMock,
    ) -> None:
        """Test that scanner errors are wrapped in SemanticScanError (CT-11 fail loud)."""
        mock_scanner.analyze_content.side_effect = RuntimeError("Scanner failed")

        with pytest.raises(SemanticScanError) as exc_info:
            await service.check_content_semantically(
                content_id="test-123",
                content="test content",
            )

        assert exc_info.value.content_id == "test-123"

    @pytest.mark.asyncio
    async def test_returns_scan_result(
        self,
        service: SemanticScanningService,
        mock_scanner: AsyncMock,
    ) -> None:
        """Test that method returns the scan result."""
        expected_result = SemanticScanResult.with_suspicion(
            patterns=("pattern",),
            confidence=0.8,
        )
        mock_scanner.analyze_content.return_value = expected_result

        result = await service.check_content_semantically(
            content_id="test-123",
            content="test content",
        )

        assert result == expected_result


class TestScanOnly:
    """Tests for scan_only method (dry-run without events)."""

    @pytest.mark.asyncio
    async def test_halt_check_first(
        self,
        mock_scanner: AsyncMock,
        mock_event_writer: AsyncMock,
        mock_halt_checker_halted: AsyncMock,
    ) -> None:
        """Test that HALT CHECK FIRST pattern is enforced (CT-11)."""
        service = SemanticScanningService(
            scanner=mock_scanner,
            event_writer=mock_event_writer,
            halt_checker=mock_halt_checker_halted,
        )

        with pytest.raises(SystemHaltedError):
            await service.scan_only(content="test content")

    @pytest.mark.asyncio
    async def test_no_event_created(
        self,
        service: SemanticScanningService,
        mock_scanner: AsyncMock,
        mock_event_writer: AsyncMock,
    ) -> None:
        """Test that scan_only does NOT create events."""
        # Even with high-confidence suspicion
        mock_scanner.analyze_content.return_value = SemanticScanResult.with_suspicion(
            patterns=("we think",),
            confidence=0.95,
        )

        await service.scan_only(content="We think this is good")

        mock_event_writer.write_event.assert_not_called()

    @pytest.mark.asyncio
    async def test_returns_scan_result(
        self,
        service: SemanticScanningService,
        mock_scanner: AsyncMock,
    ) -> None:
        """Test that scan_only returns the scan result."""
        expected_result = SemanticScanResult.with_suspicion(
            patterns=("pattern",),
            confidence=0.8,
        )
        mock_scanner.analyze_content.return_value = expected_result

        result = await service.scan_only(content="test content")

        assert result == expected_result

    @pytest.mark.asyncio
    async def test_scanner_error_raises_semantic_scan_error(
        self,
        service: SemanticScanningService,
        mock_scanner: AsyncMock,
    ) -> None:
        """Test that scanner errors are wrapped in SemanticScanError."""
        mock_scanner.analyze_content.side_effect = RuntimeError("Scanner failed")

        with pytest.raises(SemanticScanError):
            await service.scan_only(content="test content")


class TestGetConfidenceThreshold:
    """Tests for get_confidence_threshold method."""

    @pytest.mark.asyncio
    async def test_halt_check_first(
        self,
        mock_scanner: AsyncMock,
        mock_event_writer: AsyncMock,
        mock_halt_checker_halted: AsyncMock,
    ) -> None:
        """Test that HALT CHECK FIRST pattern is enforced (CT-11)."""
        service = SemanticScanningService(
            scanner=mock_scanner,
            event_writer=mock_event_writer,
            halt_checker=mock_halt_checker_halted,
        )

        with pytest.raises(SystemHaltedError):
            await service.get_confidence_threshold()

    @pytest.mark.asyncio
    async def test_returns_threshold_from_scanner(
        self,
        service: SemanticScanningService,
        mock_scanner: AsyncMock,
    ) -> None:
        """Test that threshold is returned from scanner port."""
        mock_scanner.get_confidence_threshold.return_value = 0.85

        result = await service.get_confidence_threshold()

        assert result == 0.85


class TestGetSuspiciousPatterns:
    """Tests for get_suspicious_patterns method."""

    @pytest.mark.asyncio
    async def test_halt_check_first(
        self,
        mock_scanner: AsyncMock,
        mock_event_writer: AsyncMock,
        mock_halt_checker_halted: AsyncMock,
    ) -> None:
        """Test that HALT CHECK FIRST pattern is enforced (CT-11)."""
        service = SemanticScanningService(
            scanner=mock_scanner,
            event_writer=mock_event_writer,
            halt_checker=mock_halt_checker_halted,
        )

        with pytest.raises(SystemHaltedError):
            await service.get_suspicious_patterns()

    @pytest.mark.asyncio
    async def test_returns_patterns_from_scanner(
        self,
        service: SemanticScanningService,
        mock_scanner: AsyncMock,
    ) -> None:
        """Test that patterns are returned from scanner port."""
        expected_patterns = ("a", "b", "c")
        mock_scanner.get_suspicious_patterns.return_value = expected_patterns

        result = await service.get_suspicious_patterns()

        assert result == expected_patterns


class TestContentPreviewTruncation:
    """Tests for content preview truncation in events."""

    @pytest.mark.asyncio
    async def test_long_content_truncated_in_event(
        self,
        service: SemanticScanningService,
        mock_scanner: AsyncMock,
        mock_event_writer: AsyncMock,
    ) -> None:
        """Test that long content is truncated in event payload."""
        mock_scanner.analyze_content.return_value = SemanticScanResult.with_suspicion(
            patterns=("we think",),
            confidence=0.9,
        )

        long_content = "x" * 500  # 500 chars, exceeds 200 limit

        await service.check_content_semantically(
            content_id="test-123",
            content=long_content,
        )

        call_kwargs = mock_event_writer.write_event.call_args.kwargs
        preview = call_kwargs["payload"]["content_preview"]
        assert len(preview) == 200

    @pytest.mark.asyncio
    async def test_short_content_not_truncated(
        self,
        service: SemanticScanningService,
        mock_scanner: AsyncMock,
        mock_event_writer: AsyncMock,
    ) -> None:
        """Test that short content is not truncated."""
        mock_scanner.analyze_content.return_value = SemanticScanResult.with_suspicion(
            patterns=("we think",),
            confidence=0.9,
        )

        short_content = "We think this is short"

        await service.check_content_semantically(
            content_id="test-123",
            content=short_content,
        )

        call_kwargs = mock_event_writer.write_event.call_args.kwargs
        preview = call_kwargs["payload"]["content_preview"]
        assert preview == short_content


class TestEventTimestamp:
    """Tests for event timestamp handling."""

    @pytest.mark.asyncio
    async def test_event_has_local_timestamp(
        self,
        service: SemanticScanningService,
        mock_scanner: AsyncMock,
        mock_event_writer: AsyncMock,
    ) -> None:
        """Test that event includes local timestamp."""
        mock_scanner.analyze_content.return_value = SemanticScanResult.with_suspicion(
            patterns=("pattern",),
            confidence=0.9,
        )

        await service.check_content_semantically(
            content_id="test-123",
            content="test content",
        )

        call_kwargs = mock_event_writer.write_event.call_args.kwargs
        assert "local_timestamp" in call_kwargs
        assert isinstance(call_kwargs["local_timestamp"], datetime)
