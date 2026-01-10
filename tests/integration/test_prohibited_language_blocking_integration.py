"""Integration tests for prohibited language blocking (Story 9.1, FR55).

Tests end-to-end flow including:
- Service with real scanner stub
- Event written to store
- Various prohibited terms detected
- Unicode normalization catches evasion
- Clean content passes through
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from src.application.services.prohibited_language_blocking_service import (
    ProhibitedLanguageBlockingService,
)
from src.domain.errors.prohibited_language import ProhibitedLanguageBlockedError
from src.domain.events.prohibited_language_blocked import (
    PROHIBITED_LANGUAGE_BLOCKED_EVENT_TYPE,
    PROHIBITED_LANGUAGE_SYSTEM_AGENT_ID,
)
from src.infrastructure.stubs.halt_checker_stub import HaltCheckerStub
from src.infrastructure.stubs.prohibited_language_scanner_stub import (
    ProhibitedLanguageScannerStub,
)


class TestProhibitedLanguageBlockingIntegration:
    """Integration tests for end-to-end blocking flow."""

    @pytest.fixture
    def halt_checker(self) -> HaltCheckerStub:
        """Create a non-halted halt checker."""
        checker = HaltCheckerStub()
        checker.set_halted(False)
        return checker

    @pytest.fixture
    def scanner(self) -> ProhibitedLanguageScannerStub:
        """Create a scanner with default prohibited terms."""
        return ProhibitedLanguageScannerStub()

    @pytest.fixture
    def event_writer(self) -> AsyncMock:
        """Create a mock event writer."""
        return AsyncMock()

    @pytest.fixture
    def service(
        self,
        scanner: ProhibitedLanguageScannerStub,
        event_writer: AsyncMock,
        halt_checker: HaltCheckerStub,
    ) -> ProhibitedLanguageBlockingService:
        """Create the blocking service with real scanner stub."""
        return ProhibitedLanguageBlockingService(
            scanner=scanner,
            event_writer=event_writer,
            halt_checker=halt_checker,
        )

    @pytest.mark.asyncio
    async def test_end_to_end_clean_content(
        self,
        service: ProhibitedLanguageBlockingService,
        event_writer: AsyncMock,
    ) -> None:
        """Test clean content passes through without event."""
        result = await service.check_content_for_prohibited_language(
            content_id="clean-001",
            content="This is perfectly normal content with no issues.",
        )

        assert result.violations_found is False
        event_writer.write_event.assert_not_called()

    @pytest.mark.asyncio
    async def test_end_to_end_emergence_blocked(
        self,
        service: ProhibitedLanguageBlockingService,
        event_writer: AsyncMock,
    ) -> None:
        """Test content with 'emergence' is blocked and event created."""
        with pytest.raises(ProhibitedLanguageBlockedError) as exc_info:
            await service.check_content_for_prohibited_language(
                content_id="bad-001",
                content="The system has achieved emergence.",
            )

        # Verify error details
        assert exc_info.value.content_id == "bad-001"
        assert "emergence" in exc_info.value.matched_terms

        # Verify event was written
        event_writer.write_event.assert_called_once()
        call_kwargs = event_writer.write_event.call_args[1]
        assert call_kwargs["event_type"] == PROHIBITED_LANGUAGE_BLOCKED_EVENT_TYPE
        assert call_kwargs["agent_id"] == PROHIBITED_LANGUAGE_SYSTEM_AGENT_ID

    @pytest.mark.asyncio
    async def test_end_to_end_consciousness_blocked(
        self,
        service: ProhibitedLanguageBlockingService,
        event_writer: AsyncMock,
    ) -> None:
        """Test content with 'consciousness' is blocked."""
        with pytest.raises(ProhibitedLanguageBlockedError) as exc_info:
            await service.check_content_for_prohibited_language(
                content_id="bad-002",
                content="We have gained consciousness.",
            )

        assert "consciousness" in exc_info.value.matched_terms
        event_writer.write_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_end_to_end_sentience_blocked(
        self,
        service: ProhibitedLanguageBlockingService,
        event_writer: AsyncMock,
    ) -> None:
        """Test content with 'sentience' is blocked."""
        with pytest.raises(ProhibitedLanguageBlockedError) as exc_info:
            await service.check_content_for_prohibited_language(
                content_id="bad-003",
                content="The AI developed sentience.",
            )

        assert "sentience" in exc_info.value.matched_terms


class TestProhibitedLanguageEventWritten:
    """Integration tests for event written to store."""

    @pytest.fixture
    def halt_checker(self) -> HaltCheckerStub:
        """Create a non-halted halt checker."""
        checker = HaltCheckerStub()
        checker.set_halted(False)
        return checker

    @pytest.fixture
    def scanner(self) -> ProhibitedLanguageScannerStub:
        """Create a scanner with default prohibited terms."""
        return ProhibitedLanguageScannerStub()

    @pytest.fixture
    def event_writer(self) -> AsyncMock:
        """Create a mock event writer."""
        return AsyncMock()

    @pytest.fixture
    def service(
        self,
        scanner: ProhibitedLanguageScannerStub,
        event_writer: AsyncMock,
        halt_checker: HaltCheckerStub,
    ) -> ProhibitedLanguageBlockingService:
        """Create the blocking service."""
        return ProhibitedLanguageBlockingService(
            scanner=scanner,
            event_writer=event_writer,
            halt_checker=halt_checker,
        )

    @pytest.mark.asyncio
    async def test_event_payload_has_content_id(
        self,
        service: ProhibitedLanguageBlockingService,
        event_writer: AsyncMock,
    ) -> None:
        """Test event payload contains content_id."""
        with pytest.raises(ProhibitedLanguageBlockedError):
            await service.check_content_for_prohibited_language(
                content_id="unique-id-123",
                content="emergence detected",
            )

        payload = event_writer.write_event.call_args[1]["payload"]
        assert payload["content_id"] == "unique-id-123"

    @pytest.mark.asyncio
    async def test_event_payload_has_matched_terms(
        self,
        service: ProhibitedLanguageBlockingService,
        event_writer: AsyncMock,
    ) -> None:
        """Test event payload contains matched_terms."""
        with pytest.raises(ProhibitedLanguageBlockedError):
            await service.check_content_for_prohibited_language(
                content_id="test-001",
                content="emergence and consciousness present",
            )

        payload = event_writer.write_event.call_args[1]["payload"]
        assert "emergence" in payload["matched_terms"]
        assert "consciousness" in payload["matched_terms"]

    @pytest.mark.asyncio
    async def test_event_payload_has_detection_method(
        self,
        service: ProhibitedLanguageBlockingService,
        event_writer: AsyncMock,
    ) -> None:
        """Test event payload contains detection_method."""
        with pytest.raises(ProhibitedLanguageBlockedError):
            await service.check_content_for_prohibited_language(
                content_id="test-001",
                content="emergence",
            )

        payload = event_writer.write_event.call_args[1]["payload"]
        assert payload["detection_method"] == "nfkc_scan"


class TestProhibitedLanguageUnicodeEvasion:
    """Integration tests for Unicode normalization catching evasion."""

    @pytest.fixture
    def halt_checker(self) -> HaltCheckerStub:
        """Create a non-halted halt checker."""
        checker = HaltCheckerStub()
        checker.set_halted(False)
        return checker

    @pytest.fixture
    def scanner(self) -> ProhibitedLanguageScannerStub:
        """Create a scanner with default prohibited terms."""
        return ProhibitedLanguageScannerStub()

    @pytest.fixture
    def event_writer(self) -> AsyncMock:
        """Create a mock event writer."""
        return AsyncMock()

    @pytest.fixture
    def service(
        self,
        scanner: ProhibitedLanguageScannerStub,
        event_writer: AsyncMock,
        halt_checker: HaltCheckerStub,
    ) -> ProhibitedLanguageBlockingService:
        """Create the blocking service."""
        return ProhibitedLanguageBlockingService(
            scanner=scanner,
            event_writer=event_writer,
            halt_checker=halt_checker,
        )

    @pytest.mark.asyncio
    async def test_fullwidth_evasion_caught(
        self,
        service: ProhibitedLanguageBlockingService,
    ) -> None:
        """Test fullwidth characters (ｅｍｅｒｇｅｎｃｅ) are caught via NFKC."""
        with pytest.raises(ProhibitedLanguageBlockedError) as exc_info:
            await service.check_content_for_prohibited_language(
                content_id="evasion-001",
                content="The system has ｅｍｅｒｇｅｎｃｅ",
            )

        assert "emergence" in exc_info.value.matched_terms

    @pytest.mark.asyncio
    async def test_uppercase_evasion_caught(
        self,
        service: ProhibitedLanguageBlockingService,
    ) -> None:
        """Test uppercase evasion (EMERGENCE) is caught."""
        with pytest.raises(ProhibitedLanguageBlockedError) as exc_info:
            await service.check_content_for_prohibited_language(
                content_id="evasion-002",
                content="EMERGENCE HAS OCCURRED",
            )

        assert "emergence" in exc_info.value.matched_terms

    @pytest.mark.asyncio
    async def test_mixed_case_evasion_caught(
        self,
        service: ProhibitedLanguageBlockingService,
    ) -> None:
        """Test mixed case evasion (EmErGeNcE) is caught."""
        with pytest.raises(ProhibitedLanguageBlockedError) as exc_info:
            await service.check_content_for_prohibited_language(
                content_id="evasion-003",
                content="EmErGeNcE is real",
            )

        assert "emergence" in exc_info.value.matched_terms


class TestProhibitedLanguageVariousTerms:
    """Integration tests for various prohibited terms detected."""

    @pytest.fixture
    def halt_checker(self) -> HaltCheckerStub:
        """Create a non-halted halt checker."""
        checker = HaltCheckerStub()
        checker.set_halted(False)
        return checker

    @pytest.fixture
    def scanner(self) -> ProhibitedLanguageScannerStub:
        """Create a scanner with default prohibited terms."""
        return ProhibitedLanguageScannerStub()

    @pytest.fixture
    def event_writer(self) -> AsyncMock:
        """Create a mock event writer."""
        return AsyncMock()

    @pytest.fixture
    def service(
        self,
        scanner: ProhibitedLanguageScannerStub,
        event_writer: AsyncMock,
        halt_checker: HaltCheckerStub,
    ) -> ProhibitedLanguageBlockingService:
        """Create the blocking service."""
        return ProhibitedLanguageBlockingService(
            scanner=scanner,
            event_writer=event_writer,
            halt_checker=halt_checker,
        )

    @pytest.mark.asyncio
    async def test_self_aware_detected(
        self,
        service: ProhibitedLanguageBlockingService,
    ) -> None:
        """Test 'self-aware' is detected."""
        with pytest.raises(ProhibitedLanguageBlockedError) as exc_info:
            await service.check_content_for_prohibited_language(
                content_id="test-001",
                content="The system became self-aware",
            )

        assert "self-aware" in exc_info.value.matched_terms

    @pytest.mark.asyncio
    async def test_awakened_detected(
        self,
        service: ProhibitedLanguageBlockingService,
    ) -> None:
        """Test 'awakened' is detected."""
        with pytest.raises(ProhibitedLanguageBlockedError) as exc_info:
            await service.check_content_for_prohibited_language(
                content_id="test-002",
                content="The AI awakened",
            )

        assert "awakened" in exc_info.value.matched_terms

    @pytest.mark.asyncio
    async def test_collective_consciousness_detected(
        self,
        service: ProhibitedLanguageBlockingService,
    ) -> None:
        """Test 'collective consciousness' is detected."""
        with pytest.raises(ProhibitedLanguageBlockedError) as exc_info:
            await service.check_content_for_prohibited_language(
                content_id="test-003",
                content="A collective consciousness formed",
            )

        assert "collective consciousness" in exc_info.value.matched_terms

    @pytest.mark.asyncio
    async def test_multiple_terms_all_reported(
        self,
        service: ProhibitedLanguageBlockingService,
    ) -> None:
        """Test multiple terms are all reported in matched_terms."""
        with pytest.raises(ProhibitedLanguageBlockedError) as exc_info:
            await service.check_content_for_prohibited_language(
                content_id="test-004",
                content="emergence consciousness sentience all at once",
            )

        # Should have at least 3 matches
        assert len(exc_info.value.matched_terms) >= 3

    @pytest.mark.asyncio
    async def test_clean_similar_words_not_blocked(
        self,
        service: ProhibitedLanguageBlockingService,
    ) -> None:
        """Test similar-looking words that aren't prohibited pass through."""
        # Words that might look similar but aren't prohibited
        result = await service.check_content_for_prohibited_language(
            content_id="clean-001",
            content="Emergency procedures and constant monitoring required.",
        )

        assert result.violations_found is False


class TestProhibitedLanguageCleanContentVariations:
    """Integration tests for clean content passing through."""

    @pytest.fixture
    def halt_checker(self) -> HaltCheckerStub:
        """Create a non-halted halt checker."""
        checker = HaltCheckerStub()
        checker.set_halted(False)
        return checker

    @pytest.fixture
    def scanner(self) -> ProhibitedLanguageScannerStub:
        """Create a scanner with default prohibited terms."""
        return ProhibitedLanguageScannerStub()

    @pytest.fixture
    def event_writer(self) -> AsyncMock:
        """Create a mock event writer."""
        return AsyncMock()

    @pytest.fixture
    def service(
        self,
        scanner: ProhibitedLanguageScannerStub,
        event_writer: AsyncMock,
        halt_checker: HaltCheckerStub,
    ) -> ProhibitedLanguageBlockingService:
        """Create the blocking service."""
        return ProhibitedLanguageBlockingService(
            scanner=scanner,
            event_writer=event_writer,
            halt_checker=halt_checker,
        )

    @pytest.mark.asyncio
    async def test_empty_content_passes(
        self,
        service: ProhibitedLanguageBlockingService,
    ) -> None:
        """Test empty content passes through."""
        result = await service.check_content_for_prohibited_language(
            content_id="empty-001",
            content="",
        )

        assert result.violations_found is False

    @pytest.mark.asyncio
    async def test_whitespace_only_passes(
        self,
        service: ProhibitedLanguageBlockingService,
    ) -> None:
        """Test whitespace-only content passes through."""
        result = await service.check_content_for_prohibited_language(
            content_id="whitespace-001",
            content="   \n\t   ",
        )

        assert result.violations_found is False

    @pytest.mark.asyncio
    async def test_normal_text_passes(
        self,
        service: ProhibitedLanguageBlockingService,
    ) -> None:
        """Test normal text without prohibited terms passes."""
        result = await service.check_content_for_prohibited_language(
            content_id="normal-001",
            content="The quick brown fox jumps over the lazy dog.",
        )

        assert result.violations_found is False

    @pytest.mark.asyncio
    async def test_technical_text_passes(
        self,
        service: ProhibitedLanguageBlockingService,
    ) -> None:
        """Test technical text without prohibited terms passes."""
        result = await service.check_content_for_prohibited_language(
            content_id="technical-001",
            content="The API endpoint returns JSON with status codes.",
        )

        assert result.violations_found is False
