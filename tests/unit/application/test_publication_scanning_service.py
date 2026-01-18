"""Unit tests for PublicationScanningService (Story 9.2, FR56).

Tests:
- HALT CHECK FIRST pattern (CT-11)
- Clean publication scan
- Blocked publication scan
- Event creation and witnessing (CT-12)
- Batch scanning
- Scan history
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from src.application.ports.prohibited_language_scanner import ScanResult
from src.application.services.publication_scanning_service import (
    PublicationScanningService,
)
from src.domain.errors.publication import (
    PublicationBlockedError,
    PublicationScanError,
)
from src.domain.errors.writer import SystemHaltedError
from src.domain.events.publication_scan import (
    PUBLICATION_BLOCKED_EVENT_TYPE,
    PUBLICATION_SCANNED_EVENT_TYPE,
    PUBLICATION_SCANNER_SYSTEM_AGENT_ID,
)
from src.domain.models.publication import PublicationScanRequest


@pytest.fixture
def mock_scanner() -> AsyncMock:
    """Create mock scanner port."""
    scanner = AsyncMock()
    scanner.scan_content.return_value = ScanResult.no_violations()
    return scanner


@pytest.fixture
def mock_event_writer() -> AsyncMock:
    """Create mock event writer."""
    writer = AsyncMock()
    writer.write_event.return_value = None
    return writer


@pytest.fixture
def mock_halt_checker() -> AsyncMock:
    """Create mock halt checker."""
    checker = AsyncMock()
    checker.is_halted.return_value = False
    return checker


@pytest.fixture
def service(
    mock_scanner: AsyncMock,
    mock_event_writer: AsyncMock,
    mock_halt_checker: AsyncMock,
) -> PublicationScanningService:
    """Create service with mock dependencies."""
    return PublicationScanningService(
        scanner=mock_scanner,
        event_writer=mock_event_writer,
        halt_checker=mock_halt_checker,
    )


@pytest.fixture
def sample_request() -> PublicationScanRequest:
    """Create sample scan request."""
    return PublicationScanRequest(
        publication_id="pub-123",
        content="Clean content here",
        title="Test Article",
    )


class TestHaltCheckFirst:
    """Tests for HALT CHECK FIRST pattern (CT-11)."""

    @pytest.mark.asyncio
    async def test_scan_checks_halt_state(
        self,
        service: PublicationScanningService,
        mock_halt_checker: AsyncMock,
        sample_request: PublicationScanRequest,
    ) -> None:
        """Test scan checks halt state first."""
        await service.scan_for_pre_publish(sample_request)

        mock_halt_checker.is_halted.assert_called_once()

    @pytest.mark.asyncio
    async def test_scan_raises_when_halted(
        self,
        service: PublicationScanningService,
        mock_halt_checker: AsyncMock,
        sample_request: PublicationScanRequest,
    ) -> None:
        """Test scan raises SystemHaltedError when system is halted."""
        mock_halt_checker.is_halted.return_value = True

        with pytest.raises(SystemHaltedError):
            await service.scan_for_pre_publish(sample_request)

    @pytest.mark.asyncio
    async def test_batch_scan_checks_halt_first(
        self,
        service: PublicationScanningService,
        mock_halt_checker: AsyncMock,
    ) -> None:
        """Test batch scan checks halt state first."""
        mock_halt_checker.is_halted.return_value = True
        requests = [
            PublicationScanRequest(
                publication_id=f"pub-{i}",
                content="Content",
                title=f"Title {i}",
            )
            for i in range(3)
        ]

        with pytest.raises(SystemHaltedError):
            await service.batch_scan_publications(requests)


class TestCleanPublicationScan:
    """Tests for clean publication scans."""

    @pytest.mark.asyncio
    async def test_clean_content_returns_clean_result(
        self,
        service: PublicationScanningService,
        mock_scanner: AsyncMock,
        sample_request: PublicationScanRequest,
    ) -> None:
        """Test clean content returns clean result."""
        mock_scanner.scan_content.return_value = ScanResult.no_violations()

        result = await service.scan_for_pre_publish(sample_request)

        assert result.is_clean is True
        assert result.is_blocked is False
        assert result.publication_id == sample_request.publication_id
        assert result.matched_terms == ()

    @pytest.mark.asyncio
    async def test_clean_scan_writes_scanned_event(
        self,
        service: PublicationScanningService,
        mock_scanner: AsyncMock,
        mock_event_writer: AsyncMock,
        sample_request: PublicationScanRequest,
    ) -> None:
        """Test clean scan writes PUBLICATION_SCANNED event (CT-12)."""
        mock_scanner.scan_content.return_value = ScanResult.no_violations()

        await service.scan_for_pre_publish(sample_request)

        mock_event_writer.write_event.assert_called_once()
        call_kwargs = mock_event_writer.write_event.call_args.kwargs
        assert call_kwargs["event_type"] == PUBLICATION_SCANNED_EVENT_TYPE
        assert call_kwargs["agent_id"] == PUBLICATION_SCANNER_SYSTEM_AGENT_ID

    @pytest.mark.asyncio
    async def test_clean_scan_event_payload_is_correct(
        self,
        service: PublicationScanningService,
        mock_scanner: AsyncMock,
        mock_event_writer: AsyncMock,
        sample_request: PublicationScanRequest,
    ) -> None:
        """Test clean scan event payload contains correct data."""
        mock_scanner.scan_content.return_value = ScanResult.no_violations()

        await service.scan_for_pre_publish(sample_request)

        call_kwargs = mock_event_writer.write_event.call_args.kwargs
        payload = call_kwargs["payload"]
        assert payload["publication_id"] == sample_request.publication_id
        assert payload["title"] == sample_request.title
        assert payload["scan_result"] == "clean"
        assert payload["matched_terms"] == []


class TestBlockedPublicationScan:
    """Tests for blocked publication scans."""

    @pytest.mark.asyncio
    async def test_prohibited_content_raises_blocked_error(
        self,
        service: PublicationScanningService,
        mock_scanner: AsyncMock,
        sample_request: PublicationScanRequest,
    ) -> None:
        """Test prohibited content raises PublicationBlockedError."""
        mock_scanner.scan_content.return_value = ScanResult.with_violations(
            matched_terms=("emergence",)
        )

        with pytest.raises(PublicationBlockedError) as exc_info:
            await service.scan_for_pre_publish(sample_request)

        assert exc_info.value.publication_id == sample_request.publication_id
        assert exc_info.value.title == sample_request.title
        assert "emergence" in exc_info.value.matched_terms

    @pytest.mark.asyncio
    async def test_blocked_scan_writes_blocked_event(
        self,
        service: PublicationScanningService,
        mock_scanner: AsyncMock,
        mock_event_writer: AsyncMock,
        sample_request: PublicationScanRequest,
    ) -> None:
        """Test blocked scan writes PUBLICATION_BLOCKED event (CT-12)."""
        mock_scanner.scan_content.return_value = ScanResult.with_violations(
            matched_terms=("emergence", "consciousness")
        )

        with pytest.raises(PublicationBlockedError):
            await service.scan_for_pre_publish(sample_request)

        mock_event_writer.write_event.assert_called_once()
        call_kwargs = mock_event_writer.write_event.call_args.kwargs
        assert call_kwargs["event_type"] == PUBLICATION_BLOCKED_EVENT_TYPE

    @pytest.mark.asyncio
    async def test_blocked_scan_event_contains_matched_terms(
        self,
        service: PublicationScanningService,
        mock_scanner: AsyncMock,
        mock_event_writer: AsyncMock,
        sample_request: PublicationScanRequest,
    ) -> None:
        """Test blocked scan event contains matched terms."""
        mock_scanner.scan_content.return_value = ScanResult.with_violations(
            matched_terms=("emergence", "consciousness")
        )

        with pytest.raises(PublicationBlockedError):
            await service.scan_for_pre_publish(sample_request)

        call_kwargs = mock_event_writer.write_event.call_args.kwargs
        payload = call_kwargs["payload"]
        assert payload["scan_result"] == "blocked"
        assert "emergence" in payload["matched_terms"]
        assert "consciousness" in payload["matched_terms"]

    @pytest.mark.asyncio
    async def test_blocked_error_message_includes_fr56(
        self,
        service: PublicationScanningService,
        mock_scanner: AsyncMock,
        sample_request: PublicationScanRequest,
    ) -> None:
        """Test blocked error message references FR56."""
        mock_scanner.scan_content.return_value = ScanResult.with_violations(
            matched_terms=("emergence",)
        )

        with pytest.raises(PublicationBlockedError) as exc_info:
            await service.scan_for_pre_publish(sample_request)

        assert "FR56" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_multiple_terms_all_captured(
        self,
        service: PublicationScanningService,
        mock_scanner: AsyncMock,
        sample_request: PublicationScanRequest,
    ) -> None:
        """Test multiple matched terms are all captured."""
        terms = ("emergence", "consciousness", "sentience")
        mock_scanner.scan_content.return_value = ScanResult.with_violations(
            matched_terms=terms
        )

        with pytest.raises(PublicationBlockedError) as exc_info:
            await service.scan_for_pre_publish(sample_request)

        assert exc_info.value.terms_count == 3
        for term in terms:
            assert term in exc_info.value.matched_terms


class TestScanErrors:
    """Tests for scan error handling."""

    @pytest.mark.asyncio
    async def test_scanner_error_raises_scan_error(
        self,
        service: PublicationScanningService,
        mock_scanner: AsyncMock,
        sample_request: PublicationScanRequest,
    ) -> None:
        """Test scanner exception raises PublicationScanError (CT-11)."""
        mock_scanner.scan_content.side_effect = RuntimeError("Scanner failed")

        with pytest.raises(PublicationScanError) as exc_info:
            await service.scan_for_pre_publish(sample_request)

        assert exc_info.value.publication_id == sample_request.publication_id
        assert "FR56" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_scan_error_preserves_original_exception(
        self,
        service: PublicationScanningService,
        mock_scanner: AsyncMock,
        sample_request: PublicationScanRequest,
    ) -> None:
        """Test PublicationScanError preserves original exception."""
        original_error = RuntimeError("Original error")
        mock_scanner.scan_content.side_effect = original_error

        with pytest.raises(PublicationScanError) as exc_info:
            await service.scan_for_pre_publish(sample_request)

        assert exc_info.value.source_error is original_error

    @pytest.mark.asyncio
    async def test_scan_error_records_in_history(
        self,
        service: PublicationScanningService,
        mock_scanner: AsyncMock,
        sample_request: PublicationScanRequest,
    ) -> None:
        """Test scan errors are recorded in history."""
        mock_scanner.scan_content.side_effect = RuntimeError("Failed")

        with pytest.raises(PublicationScanError):
            await service.scan_for_pre_publish(sample_request)

        history = await service.get_scan_history(sample_request.publication_id)
        assert len(history) == 1
        assert history[0].is_error is True


class TestBatchScanning:
    """Tests for batch publication scanning."""

    @pytest.mark.asyncio
    async def test_batch_scan_returns_all_results(
        self,
        service: PublicationScanningService,
        mock_scanner: AsyncMock,
    ) -> None:
        """Test batch scan returns results for all publications."""
        mock_scanner.scan_content.return_value = ScanResult.no_violations()
        requests = [
            PublicationScanRequest(
                publication_id=f"pub-{i}",
                content=f"Content {i}",
                title=f"Title {i}",
            )
            for i in range(5)
        ]

        results = await service.batch_scan_publications(requests)

        assert len(results) == 5
        for i, result in enumerate(results):
            assert result.publication_id == f"pub-{i}"

    @pytest.mark.asyncio
    async def test_batch_scan_continues_on_block(
        self,
        service: PublicationScanningService,
        mock_scanner: AsyncMock,
    ) -> None:
        """Test batch scan continues processing after a block."""
        # First and third will be clean, second will be blocked
        mock_scanner.scan_content.side_effect = [
            ScanResult.no_violations(),
            ScanResult.with_violations(matched_terms=("emergence",)),
            ScanResult.no_violations(),
        ]
        requests = [
            PublicationScanRequest(
                publication_id=f"pub-{i}",
                content=f"Content {i}",
                title=f"Title {i}",
            )
            for i in range(3)
        ]

        results = await service.batch_scan_publications(requests)

        assert len(results) == 3
        assert results[0].is_clean is True
        assert results[1].is_blocked is True
        assert results[2].is_clean is True

    @pytest.mark.asyncio
    async def test_batch_scan_with_empty_list(
        self,
        service: PublicationScanningService,
    ) -> None:
        """Test batch scan with empty list returns empty results."""
        results = await service.batch_scan_publications([])

        assert results == []

    @pytest.mark.asyncio
    async def test_batch_scan_creates_event_per_publication(
        self,
        service: PublicationScanningService,
        mock_scanner: AsyncMock,
        mock_event_writer: AsyncMock,
    ) -> None:
        """Test batch scan creates an event for each publication."""
        mock_scanner.scan_content.return_value = ScanResult.no_violations()
        requests = [
            PublicationScanRequest(
                publication_id=f"pub-{i}",
                content=f"Content {i}",
                title=f"Title {i}",
            )
            for i in range(3)
        ]

        await service.batch_scan_publications(requests)

        assert mock_event_writer.write_event.call_count == 3


class TestScanHistory:
    """Tests for scan history tracking."""

    @pytest.mark.asyncio
    async def test_history_records_clean_scans(
        self,
        service: PublicationScanningService,
        mock_scanner: AsyncMock,
        sample_request: PublicationScanRequest,
    ) -> None:
        """Test clean scans are recorded in history."""
        mock_scanner.scan_content.return_value = ScanResult.no_violations()

        await service.scan_for_pre_publish(sample_request)

        history = await service.get_scan_history(sample_request.publication_id)
        assert len(history) == 1
        assert history[0].is_clean is True

    @pytest.mark.asyncio
    async def test_history_records_blocked_scans(
        self,
        service: PublicationScanningService,
        mock_scanner: AsyncMock,
        sample_request: PublicationScanRequest,
    ) -> None:
        """Test blocked scans are recorded in history."""
        mock_scanner.scan_content.return_value = ScanResult.with_violations(
            matched_terms=("emergence",)
        )

        with pytest.raises(PublicationBlockedError):
            await service.scan_for_pre_publish(sample_request)

        history = await service.get_scan_history(sample_request.publication_id)
        assert len(history) == 1
        assert history[0].is_blocked is True

    @pytest.mark.asyncio
    async def test_history_returns_most_recent_first(
        self,
        service: PublicationScanningService,
        mock_scanner: AsyncMock,
    ) -> None:
        """Test history returns most recent scan first."""
        mock_scanner.scan_content.side_effect = [
            ScanResult.no_violations(),
            ScanResult.with_violations(matched_terms=("emergence",)),
        ]
        request = PublicationScanRequest(
            publication_id="pub-123",
            content="Content",
            title="Title",
        )

        # First scan - clean
        await service.scan_for_pre_publish(request)

        # Second scan - blocked
        mock_scanner.scan_content.side_effect = None
        mock_scanner.scan_content.return_value = ScanResult.with_violations(
            matched_terms=("emergence",)
        )
        with pytest.raises(PublicationBlockedError):
            await service.scan_for_pre_publish(request)

        history = await service.get_scan_history("pub-123")
        assert len(history) == 2
        assert history[0].is_blocked is True  # Most recent first
        assert history[1].is_clean is True

    @pytest.mark.asyncio
    async def test_history_empty_for_unknown_publication(
        self,
        service: PublicationScanningService,
    ) -> None:
        """Test empty history for unknown publication."""
        history = await service.get_scan_history("unknown-pub")

        assert history == []

    @pytest.mark.asyncio
    async def test_clear_history(
        self,
        service: PublicationScanningService,
        mock_scanner: AsyncMock,
        sample_request: PublicationScanRequest,
    ) -> None:
        """Test clear_history removes all history."""
        mock_scanner.scan_content.return_value = ScanResult.no_violations()
        await service.scan_for_pre_publish(sample_request)

        service.clear_history()

        history = await service.get_scan_history(sample_request.publication_id)
        assert history == []


class TestProtocolImplementation:
    """Tests for PublicationScannerProtocol implementation."""

    @pytest.mark.asyncio
    async def test_scan_publication_delegates_to_scan_for_pre_publish(
        self,
        service: PublicationScanningService,
        mock_scanner: AsyncMock,
        sample_request: PublicationScanRequest,
    ) -> None:
        """Test scan_publication delegates to scan_for_pre_publish."""
        mock_scanner.scan_content.return_value = ScanResult.no_violations()

        result = await service.scan_publication(sample_request)

        assert result.is_clean is True
        assert result.publication_id == sample_request.publication_id
