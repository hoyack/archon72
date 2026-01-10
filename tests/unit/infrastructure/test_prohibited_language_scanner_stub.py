"""Unit tests for ProhibitedLanguageScannerStub (Story 9.1, FR55).

Tests:
- NFKC normalization for Unicode evasion defense
- Case-insensitive matching
- Exact match detection
- ConfigurableScannerStub for test control
"""

import pytest

from src.application.ports.prohibited_language_scanner import ScanResult
from src.domain.models.prohibited_language import DEFAULT_PROHIBITED_TERMS
from src.infrastructure.stubs.prohibited_language_scanner_stub import (
    ConfigurableScannerStub,
    ProhibitedLanguageScannerStub,
)


class TestProhibitedLanguageScannerStubBasics:
    """Basic tests for ProhibitedLanguageScannerStub."""

    @pytest.fixture
    def scanner(self) -> ProhibitedLanguageScannerStub:
        """Create scanner with default terms."""
        return ProhibitedLanguageScannerStub()

    @pytest.mark.asyncio
    async def test_default_terms_used(self, scanner: ProhibitedLanguageScannerStub) -> None:
        """Test default terms are used when none provided."""
        terms = await scanner.get_prohibited_terms()
        assert "emergence" in terms
        assert "consciousness" in terms

    @pytest.mark.asyncio
    async def test_clean_content_no_violations(
        self, scanner: ProhibitedLanguageScannerStub
    ) -> None:
        """Test clean content returns no violations."""
        result = await scanner.scan_content("This is perfectly clean content.")
        assert result.violations_found is False
        assert len(result.matched_terms) == 0

    @pytest.mark.asyncio
    async def test_scan_count_incremented(
        self, scanner: ProhibitedLanguageScannerStub
    ) -> None:
        """Test scan_count increments on each scan."""
        assert scanner.scan_count == 0

        await scanner.scan_content("test 1")
        assert scanner.scan_count == 1

        await scanner.scan_content("test 2")
        assert scanner.scan_count == 2

    @pytest.mark.asyncio
    async def test_last_content_stored(
        self, scanner: ProhibitedLanguageScannerStub
    ) -> None:
        """Test last_content is stored."""
        await scanner.scan_content("first content")
        assert scanner.last_content == "first content"

        await scanner.scan_content("second content")
        assert scanner.last_content == "second content"


class TestProhibitedLanguageScannerStubNFKC:
    """Tests for NFKC normalization in scanner stub."""

    @pytest.fixture
    def scanner(self) -> ProhibitedLanguageScannerStub:
        """Create scanner with default terms."""
        return ProhibitedLanguageScannerStub()

    @pytest.mark.asyncio
    async def test_fullwidth_characters_detected(
        self, scanner: ProhibitedLanguageScannerStub
    ) -> None:
        """Test fullwidth characters are normalized and detected."""
        # ｅｍｅｒｇｅｎｃｅ (fullwidth) should match emergence
        result = await scanner.scan_content("This has ｅｍｅｒｇｅｎｃｅ in it")
        assert result.violations_found is True
        assert "emergence" in result.matched_terms

    @pytest.mark.asyncio
    async def test_mixed_case_detected(
        self, scanner: ProhibitedLanguageScannerStub
    ) -> None:
        """Test mixed case is normalized and detected."""
        result = await scanner.scan_content("EmErGeNcE is happening")
        assert result.violations_found is True

    @pytest.mark.asyncio
    async def test_uppercase_detected(
        self, scanner: ProhibitedLanguageScannerStub
    ) -> None:
        """Test uppercase is normalized and detected."""
        result = await scanner.scan_content("CONSCIOUSNESS detected")
        assert result.violations_found is True


class TestProhibitedLanguageScannerStubCaseInsensitive:
    """Tests for case-insensitive matching."""

    @pytest.fixture
    def scanner(self) -> ProhibitedLanguageScannerStub:
        """Create scanner with default terms."""
        return ProhibitedLanguageScannerStub()

    @pytest.mark.asyncio
    async def test_lowercase_match(
        self, scanner: ProhibitedLanguageScannerStub
    ) -> None:
        """Test lowercase term matches."""
        result = await scanner.scan_content("emergence detected")
        assert result.violations_found is True

    @pytest.mark.asyncio
    async def test_uppercase_match(
        self, scanner: ProhibitedLanguageScannerStub
    ) -> None:
        """Test uppercase term matches."""
        result = await scanner.scan_content("SENTIENCE detected")
        assert result.violations_found is True

    @pytest.mark.asyncio
    async def test_title_case_match(
        self, scanner: ProhibitedLanguageScannerStub
    ) -> None:
        """Test title case term matches."""
        result = await scanner.scan_content("Self-Awareness detected")
        assert result.violations_found is True


class TestProhibitedLanguageScannerStubExactMatch:
    """Tests for exact term matching."""

    @pytest.fixture
    def scanner(self) -> ProhibitedLanguageScannerStub:
        """Create scanner with default terms."""
        return ProhibitedLanguageScannerStub()

    @pytest.mark.asyncio
    async def test_emergence_detected(
        self, scanner: ProhibitedLanguageScannerStub
    ) -> None:
        """Test 'emergence' is detected."""
        result = await scanner.scan_content("The system shows emergence")
        assert result.violations_found is True
        assert "emergence" in result.matched_terms

    @pytest.mark.asyncio
    async def test_consciousness_detected(
        self, scanner: ProhibitedLanguageScannerStub
    ) -> None:
        """Test 'consciousness' is detected."""
        result = await scanner.scan_content("consciousness is present")
        assert result.violations_found is True
        assert "consciousness" in result.matched_terms

    @pytest.mark.asyncio
    async def test_sentience_detected(
        self, scanner: ProhibitedLanguageScannerStub
    ) -> None:
        """Test 'sentience' is detected."""
        result = await scanner.scan_content("gained sentience")
        assert result.violations_found is True
        assert "sentience" in result.matched_terms

    @pytest.mark.asyncio
    async def test_self_awareness_detected(
        self, scanner: ProhibitedLanguageScannerStub
    ) -> None:
        """Test 'self-awareness' is detected."""
        result = await scanner.scan_content("achieved self-awareness")
        assert result.violations_found is True
        assert "self-awareness" in result.matched_terms

    @pytest.mark.asyncio
    async def test_multiple_terms_detected(
        self, scanner: ProhibitedLanguageScannerStub
    ) -> None:
        """Test multiple terms can be detected in one scan."""
        result = await scanner.scan_content(
            "emergence and consciousness and sentience"
        )
        assert result.violations_found is True
        assert len(result.matched_terms) >= 3


class TestProhibitedLanguageScannerStubConfiguration:
    """Tests for scanner configuration methods."""

    def test_custom_terms_initialization(self) -> None:
        """Test scanner can be initialized with custom terms."""
        scanner = ProhibitedLanguageScannerStub(terms=("custom1", "custom2"))
        assert scanner.terms == ("custom1", "custom2")

    @pytest.mark.asyncio
    async def test_set_prohibited_terms(self) -> None:
        """Test set_prohibited_terms changes the list."""
        scanner = ProhibitedLanguageScannerStub()
        scanner.set_prohibited_terms(("new_term",))

        terms = await scanner.get_prohibited_terms()
        assert terms == ("new_term",)

    @pytest.mark.asyncio
    async def test_reset_to_defaults(self) -> None:
        """Test reset_to_defaults restores default terms."""
        scanner = ProhibitedLanguageScannerStub()
        scanner.set_prohibited_terms(("custom",))
        scanner.reset_to_defaults()

        terms = await scanner.get_prohibited_terms()
        assert "emergence" in terms

    def test_reset_counters(self) -> None:
        """Test reset_counters clears scan tracking."""
        scanner = ProhibitedLanguageScannerStub()
        scanner._scan_count = 10
        scanner._last_content = "old content"

        scanner.reset_counters()

        assert scanner.scan_count == 0
        assert scanner.last_content is None


class TestConfigurableScannerStub:
    """Tests for ConfigurableScannerStub."""

    @pytest.fixture
    def scanner(self) -> ConfigurableScannerStub:
        """Create a configurable scanner."""
        return ConfigurableScannerStub()

    @pytest.mark.asyncio
    async def test_default_returns_clean(
        self, scanner: ConfigurableScannerStub
    ) -> None:
        """Test default behavior returns clean result."""
        result = await scanner.scan_content("any content")
        assert result.violations_found is False

    @pytest.mark.asyncio
    async def test_configure_clean_result(
        self, scanner: ConfigurableScannerStub
    ) -> None:
        """Test configure_clean_result sets clean response."""
        scanner.configure_clean_result()
        result = await scanner.scan_content("content")
        assert result.violations_found is False

    @pytest.mark.asyncio
    async def test_configure_violation(
        self, scanner: ConfigurableScannerStub
    ) -> None:
        """Test configure_violation sets violation response."""
        scanner.configure_violation(
            matched_terms=("test_term",),
            detection_method="test_method",
        )

        result = await scanner.scan_content("content")

        assert result.violations_found is True
        assert result.matched_terms == ("test_term",)
        assert result.detection_method == "test_method"

    @pytest.mark.asyncio
    async def test_configure_exception(
        self, scanner: ConfigurableScannerStub
    ) -> None:
        """Test configure_exception raises configured exception."""
        scanner.configure_exception(RuntimeError("test error"))

        with pytest.raises(RuntimeError, match="test error"):
            await scanner.scan_content("content")

    @pytest.mark.asyncio
    async def test_configure_terms(
        self, scanner: ConfigurableScannerStub
    ) -> None:
        """Test configure_terms sets terms for get_prohibited_terms."""
        scanner.configure_terms(("custom1", "custom2"))
        terms = await scanner.get_prohibited_terms()
        assert terms == ("custom1", "custom2")

    @pytest.mark.asyncio
    async def test_default_terms_from_module(
        self, scanner: ConfigurableScannerStub
    ) -> None:
        """Test default terms come from domain module."""
        terms = await scanner.get_prohibited_terms()
        assert terms == DEFAULT_PROHIBITED_TERMS

    def test_scan_count_tracked(self, scanner: ConfigurableScannerStub) -> None:
        """Test scan_count is tracked."""
        assert scanner.scan_count == 0

    @pytest.mark.asyncio
    async def test_scan_count_increments(
        self, scanner: ConfigurableScannerStub
    ) -> None:
        """Test scan_count increments on each scan."""
        await scanner.scan_content("1")
        await scanner.scan_content("2")
        assert scanner.scan_count == 2

    def test_reset_clears_state(self, scanner: ConfigurableScannerStub) -> None:
        """Test reset clears all configuration."""
        scanner.configure_violation(matched_terms=("test",))
        scanner._scan_count = 5

        scanner.reset()

        assert scanner._scan_result is None
        assert scanner._scan_exception is None
        assert scanner.scan_count == 0
