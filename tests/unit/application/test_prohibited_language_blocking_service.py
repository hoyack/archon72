"""Unit tests for ProhibitedLanguageBlockingService (Story 9.1, FR55).

Tests:
- HALT CHECK FIRST pattern (CT-11)
- Clean content passes through
- Prohibited content blocked and event created
- Error raised on block
- Scan error handling (CT-11 fail loud)
"""

from unittest.mock import AsyncMock

import pytest

from src.application.ports.prohibited_language_scanner import ScanResult
from src.application.services.prohibited_language_blocking_service import (
    ProhibitedLanguageBlockingService,
)
from src.domain.errors.prohibited_language import (
    ProhibitedLanguageBlockedError,
    ProhibitedLanguageScanError,
)
from src.domain.errors.writer import SystemHaltedError
from src.domain.events.prohibited_language_blocked import (
    PROHIBITED_LANGUAGE_BLOCKED_EVENT_TYPE,
)


class TestProhibitedLanguageBlockingServiceHaltCheck:
    """Tests for HALT CHECK FIRST pattern (CT-11)."""

    @pytest.fixture
    def halted_checker(self) -> AsyncMock:
        """Create a halt checker that returns halted=True."""
        checker = AsyncMock()
        checker.is_halted.return_value = True
        return checker

    @pytest.fixture
    def not_halted_checker(self) -> AsyncMock:
        """Create a halt checker that returns halted=False."""
        checker = AsyncMock()
        checker.is_halted.return_value = False
        return checker

    @pytest.fixture
    def mock_scanner(self) -> AsyncMock:
        """Create a mock scanner."""
        scanner = AsyncMock()
        scanner.scan_content.return_value = ScanResult.no_violations()
        scanner.get_prohibited_terms.return_value = ("emergence", "consciousness")
        return scanner

    @pytest.fixture
    def mock_event_writer(self) -> AsyncMock:
        """Create a mock event writer."""
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_check_content_halted_raises(
        self,
        halted_checker: AsyncMock,
        mock_scanner: AsyncMock,
        mock_event_writer: AsyncMock,
    ) -> None:
        """Test check_content raises SystemHaltedError when halted."""
        service = ProhibitedLanguageBlockingService(
            scanner=mock_scanner,
            event_writer=mock_event_writer,
            halt_checker=halted_checker,
        )

        with pytest.raises(SystemHaltedError):
            await service.check_content_for_prohibited_language(
                content_id="test-123",
                content="test content",
            )

        # Scanner should not be called when halted
        mock_scanner.scan_content.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_terms_halted_raises(
        self,
        halted_checker: AsyncMock,
        mock_scanner: AsyncMock,
        mock_event_writer: AsyncMock,
    ) -> None:
        """Test get_prohibited_terms raises SystemHaltedError when halted."""
        service = ProhibitedLanguageBlockingService(
            scanner=mock_scanner,
            event_writer=mock_event_writer,
            halt_checker=halted_checker,
        )

        with pytest.raises(SystemHaltedError):
            await service.get_prohibited_terms()

        mock_scanner.get_prohibited_terms.assert_not_called()

    @pytest.mark.asyncio
    async def test_scan_only_halted_raises(
        self,
        halted_checker: AsyncMock,
        mock_scanner: AsyncMock,
        mock_event_writer: AsyncMock,
    ) -> None:
        """Test scan_only raises SystemHaltedError when halted."""
        service = ProhibitedLanguageBlockingService(
            scanner=mock_scanner,
            event_writer=mock_event_writer,
            halt_checker=halted_checker,
        )

        with pytest.raises(SystemHaltedError):
            await service.scan_only("test content")


class TestProhibitedLanguageBlockingServiceCleanContent:
    """Tests for clean content passing through."""

    @pytest.fixture
    def service(self) -> ProhibitedLanguageBlockingService:
        """Create a service with mocked dependencies."""
        scanner = AsyncMock()
        scanner.scan_content.return_value = ScanResult.no_violations()
        scanner.get_prohibited_terms.return_value = ("emergence",)

        event_writer = AsyncMock()

        halt_checker = AsyncMock()
        halt_checker.is_halted.return_value = False

        return ProhibitedLanguageBlockingService(
            scanner=scanner,
            event_writer=event_writer,
            halt_checker=halt_checker,
        )

    @pytest.mark.asyncio
    async def test_clean_content_returns_result(
        self,
        service: ProhibitedLanguageBlockingService,
    ) -> None:
        """Test clean content returns ScanResult with no violations."""
        result = await service.check_content_for_prohibited_language(
            content_id="clean-123",
            content="This is perfectly clean content.",
        )

        assert result.violations_found is False
        assert len(result.matched_terms) == 0

    @pytest.mark.asyncio
    async def test_clean_content_no_event_created(
        self,
        service: ProhibitedLanguageBlockingService,
    ) -> None:
        """Test clean content does not create an event."""
        await service.check_content_for_prohibited_language(
            content_id="clean-123",
            content="This is perfectly clean content.",
        )

        service._event_writer.write_event.assert_not_called()


class TestProhibitedLanguageBlockingServiceViolations:
    """Tests for content with violations."""

    @pytest.fixture
    def violation_scanner(self) -> AsyncMock:
        """Create a scanner that returns violations."""
        scanner = AsyncMock()
        scanner.scan_content.return_value = ScanResult.with_violations(
            matched_terms=("emergence", "consciousness"),
            detection_method="nfkc_scan",
        )
        return scanner

    @pytest.fixture
    def service(
        self, violation_scanner: AsyncMock
    ) -> ProhibitedLanguageBlockingService:
        """Create a service that detects violations."""
        event_writer = AsyncMock()

        halt_checker = AsyncMock()
        halt_checker.is_halted.return_value = False

        return ProhibitedLanguageBlockingService(
            scanner=violation_scanner,
            event_writer=event_writer,
            halt_checker=halt_checker,
        )

    @pytest.mark.asyncio
    async def test_violation_raises_error(
        self,
        service: ProhibitedLanguageBlockingService,
    ) -> None:
        """Test content with violations raises ProhibitedLanguageBlockedError."""
        with pytest.raises(ProhibitedLanguageBlockedError) as exc_info:
            await service.check_content_for_prohibited_language(
                content_id="bad-123",
                content="This mentions emergence and consciousness.",
            )

        assert exc_info.value.content_id == "bad-123"
        assert "emergence" in exc_info.value.matched_terms
        assert "consciousness" in exc_info.value.matched_terms

    @pytest.mark.asyncio
    async def test_violation_creates_event(
        self,
        service: ProhibitedLanguageBlockingService,
    ) -> None:
        """Test content with violations creates witnessed event (CT-12)."""
        with pytest.raises(ProhibitedLanguageBlockedError):
            await service.check_content_for_prohibited_language(
                content_id="bad-123",
                content="This mentions emergence.",
            )

        service._event_writer.write_event.assert_called_once()
        call_kwargs = service._event_writer.write_event.call_args[1]

        assert call_kwargs["event_type"] == PROHIBITED_LANGUAGE_BLOCKED_EVENT_TYPE
        assert call_kwargs["agent_id"] == "system:prohibited_language_blocker"
        assert "payload" in call_kwargs

    @pytest.mark.asyncio
    async def test_violation_event_payload_content(
        self,
        service: ProhibitedLanguageBlockingService,
    ) -> None:
        """Test event payload contains correct content."""
        with pytest.raises(ProhibitedLanguageBlockedError):
            await service.check_content_for_prohibited_language(
                content_id="bad-123",
                content="Content preview here",
            )

        call_kwargs = service._event_writer.write_event.call_args[1]
        payload = call_kwargs["payload"]

        assert payload["content_id"] == "bad-123"
        assert "emergence" in payload["matched_terms"]
        assert "consciousness" in payload["matched_terms"]
        assert payload["detection_method"] == "nfkc_scan"

    @pytest.mark.asyncio
    async def test_error_includes_fr55_reference(
        self,
        service: ProhibitedLanguageBlockingService,
    ) -> None:
        """Test error message includes FR55 reference."""
        with pytest.raises(ProhibitedLanguageBlockedError) as exc_info:
            await service.check_content_for_prohibited_language(
                content_id="bad-123",
                content="emergence",
            )

        assert "FR55" in str(exc_info.value)


class TestProhibitedLanguageBlockingServiceScanError:
    """Tests for scan error handling (CT-11 fail loud)."""

    @pytest.fixture
    def failing_scanner(self) -> AsyncMock:
        """Create a scanner that raises an exception."""
        scanner = AsyncMock()
        scanner.scan_content.side_effect = RuntimeError("Scanner failed")
        return scanner

    @pytest.fixture
    def service(self, failing_scanner: AsyncMock) -> ProhibitedLanguageBlockingService:
        """Create a service with a failing scanner."""
        event_writer = AsyncMock()

        halt_checker = AsyncMock()
        halt_checker.is_halted.return_value = False

        return ProhibitedLanguageBlockingService(
            scanner=failing_scanner,
            event_writer=event_writer,
            halt_checker=halt_checker,
        )

    @pytest.mark.asyncio
    async def test_scan_error_raises_scan_error(
        self,
        service: ProhibitedLanguageBlockingService,
    ) -> None:
        """Test scanner exception raises ProhibitedLanguageScanError."""
        with pytest.raises(ProhibitedLanguageScanError) as exc_info:
            await service.check_content_for_prohibited_language(
                content_id="test-123",
                content="content",
            )

        assert exc_info.value.content_id == "test-123"
        assert isinstance(exc_info.value.source_error, RuntimeError)

    @pytest.mark.asyncio
    async def test_scan_only_error_raises_scan_error(
        self,
        service: ProhibitedLanguageBlockingService,
    ) -> None:
        """Test scan_only scanner exception raises ProhibitedLanguageScanError."""
        with pytest.raises(ProhibitedLanguageScanError):
            await service.scan_only("content")


class TestProhibitedLanguageBlockingServiceScanOnly:
    """Tests for scan_only method (preview/dry-run)."""

    @pytest.fixture
    def service_with_violation(self) -> ProhibitedLanguageBlockingService:
        """Create a service that returns violations."""
        scanner = AsyncMock()
        scanner.scan_content.return_value = ScanResult.with_violations(
            matched_terms=("emergence",),
            detection_method="nfkc_scan",
        )

        event_writer = AsyncMock()

        halt_checker = AsyncMock()
        halt_checker.is_halted.return_value = False

        return ProhibitedLanguageBlockingService(
            scanner=scanner,
            event_writer=event_writer,
            halt_checker=halt_checker,
        )

    @pytest.mark.asyncio
    async def test_scan_only_returns_violations(
        self,
        service_with_violation: ProhibitedLanguageBlockingService,
    ) -> None:
        """Test scan_only returns result without raising error."""
        result = await service_with_violation.scan_only("content with emergence")

        assert result.violations_found is True
        assert "emergence" in result.matched_terms

    @pytest.mark.asyncio
    async def test_scan_only_no_event_created(
        self,
        service_with_violation: ProhibitedLanguageBlockingService,
    ) -> None:
        """Test scan_only does not create event even with violations."""
        await service_with_violation.scan_only("content with emergence")

        service_with_violation._event_writer.write_event.assert_not_called()


class TestProhibitedLanguageBlockingServiceGetTerms:
    """Tests for get_prohibited_terms method."""

    @pytest.fixture
    def service(self) -> ProhibitedLanguageBlockingService:
        """Create a service with expected terms."""
        scanner = AsyncMock()
        scanner.get_prohibited_terms.return_value = (
            "emergence",
            "consciousness",
            "sentience",
        )

        event_writer = AsyncMock()

        halt_checker = AsyncMock()
        halt_checker.is_halted.return_value = False

        return ProhibitedLanguageBlockingService(
            scanner=scanner,
            event_writer=event_writer,
            halt_checker=halt_checker,
        )

    @pytest.mark.asyncio
    async def test_get_terms_returns_tuple(
        self,
        service: ProhibitedLanguageBlockingService,
    ) -> None:
        """Test get_prohibited_terms returns tuple from scanner."""
        terms = await service.get_prohibited_terms()

        assert terms == ("emergence", "consciousness", "sentience")
        service._scanner.get_prohibited_terms.assert_called_once()
