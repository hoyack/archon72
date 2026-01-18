"""Prohibited language scanner stub for testing (Story 9.1, FR55).

Provides in-memory implementation of ProhibitedLanguageScannerProtocol
for unit and integration tests.

Usage:
    stub = ProhibitedLanguageScannerStub()

    # Test with default terms
    result = await stub.scan_content("This has emergence in it")
    assert result.violations_found == True

    # Configure custom terms for specific tests
    stub.set_prohibited_terms(("custom", "terms"))
"""

from __future__ import annotations

from src.application.ports.prohibited_language_scanner import (
    ProhibitedLanguageScannerProtocol,
    ScanResult,
)
from src.domain.models.prohibited_language import (
    DEFAULT_PROHIBITED_TERMS,
    ProhibitedTermsList,
)


class ProhibitedLanguageScannerStub(ProhibitedLanguageScannerProtocol):
    """In-memory stub implementation of ProhibitedLanguageScannerProtocol.

    Performs real NFKC normalization and case-insensitive matching
    against a configurable prohibited terms list.

    Default behavior uses the DEFAULT_PROHIBITED_TERMS from domain models.
    Tests can configure custom terms for specific scenarios.

    Attributes:
        _terms_list: The ProhibitedTermsList used for scanning.
        _detection_method: Method name returned in scan results.
        _scan_count: Number of scans performed (for testing assertions).
        _last_content: Last content scanned (for testing assertions).
    """

    def __init__(
        self,
        terms: tuple[str, ...] | None = None,
        detection_method: str = "nfkc_scan",
    ) -> None:
        """Initialize the scanner stub.

        Args:
            terms: Custom prohibited terms, or None to use defaults.
            detection_method: Method name to return in results.
        """
        if terms is not None:
            self._terms_list = ProhibitedTermsList.from_custom_terms(terms)
        else:
            self._terms_list = ProhibitedTermsList.default()

        self._detection_method = detection_method
        self._scan_count: int = 0
        self._last_content: str | None = None

    # Configuration methods for tests

    def set_prohibited_terms(self, terms: tuple[str, ...]) -> None:
        """Set custom prohibited terms for testing.

        Args:
            terms: Tuple of prohibited terms.
        """
        self._terms_list = ProhibitedTermsList.from_custom_terms(terms)

    def reset_to_defaults(self) -> None:
        """Reset to default prohibited terms."""
        self._terms_list = ProhibitedTermsList.default()

    def set_detection_method(self, method: str) -> None:
        """Set the detection method name for results.

        Args:
            method: Detection method name to return.
        """
        self._detection_method = method

    def reset_counters(self) -> None:
        """Reset scan count and last content for assertions."""
        self._scan_count = 0
        self._last_content = None

    # Accessors for test assertions

    @property
    def scan_count(self) -> int:
        """Get number of scans performed."""
        return self._scan_count

    @property
    def last_content(self) -> str | None:
        """Get last content that was scanned."""
        return self._last_content

    @property
    def terms(self) -> tuple[str, ...]:
        """Get current prohibited terms."""
        return self._terms_list.terms

    # Protocol implementation

    async def scan_content(self, content: str) -> ScanResult:
        """Scan content for prohibited language (FR55, AC2, AC3).

        Performs real NFKC normalization and case-insensitive matching.

        Args:
            content: Text content to scan.

        Returns:
            ScanResult with violations_found and matched_terms.
        """
        # Track for test assertions
        self._scan_count += 1
        self._last_content = content

        # Perform actual scanning with NFKC normalization
        has_violation, matched_terms = self._terms_list.contains_prohibited_term(
            content
        )

        if has_violation:
            return ScanResult.with_violations(
                matched_terms=matched_terms,
                detection_method=self._detection_method,
            )
        else:
            return ScanResult.no_violations(
                detection_method=self._detection_method,
            )

    async def get_prohibited_terms(self) -> tuple[str, ...]:
        """Get the current list of prohibited terms (FR55, AC1).

        Returns:
            Tuple of prohibited terms.
        """
        return self._terms_list.terms


class ConfigurableScannerStub(ProhibitedLanguageScannerProtocol):
    """Configurable scanner stub for fine-grained test control.

    Unlike ProhibitedLanguageScannerStub which performs real scanning,
    this stub allows tests to configure exact return values.

    Useful for:
    - Testing error paths (configure to raise exceptions)
    - Testing specific matched terms (configure exact results)
    - Testing service behavior without real scanning logic
    """

    def __init__(self) -> None:
        """Initialize with default clean responses."""
        self._scan_result: ScanResult | None = None
        self._scan_exception: Exception | None = None
        self._terms: tuple[str, ...] = DEFAULT_PROHIBITED_TERMS
        self._scan_count: int = 0

    # Configuration methods

    def configure_clean_result(self) -> None:
        """Configure to return clean (no violations) results."""
        self._scan_result = ScanResult.no_violations()
        self._scan_exception = None

    def configure_violation(
        self,
        matched_terms: tuple[str, ...],
        detection_method: str = "nfkc_scan",
    ) -> None:
        """Configure to return a violation result.

        Args:
            matched_terms: Terms to include in result.
            detection_method: Detection method name.
        """
        self._scan_result = ScanResult.with_violations(
            matched_terms=matched_terms,
            detection_method=detection_method,
        )
        self._scan_exception = None

    def configure_exception(self, exception: Exception) -> None:
        """Configure to raise an exception on scan.

        Args:
            exception: Exception to raise.
        """
        self._scan_exception = exception
        self._scan_result = None

    def configure_terms(self, terms: tuple[str, ...]) -> None:
        """Configure terms to return from get_prohibited_terms.

        Args:
            terms: Terms to return.
        """
        self._terms = terms

    def reset(self) -> None:
        """Reset to default configuration."""
        self._scan_result = None
        self._scan_exception = None
        self._terms = DEFAULT_PROHIBITED_TERMS
        self._scan_count = 0

    @property
    def scan_count(self) -> int:
        """Get number of scans performed."""
        return self._scan_count

    # Protocol implementation

    async def scan_content(self, content: str) -> ScanResult:
        """Return configured scan result or raise configured exception."""
        self._scan_count += 1

        if self._scan_exception is not None:
            raise self._scan_exception

        if self._scan_result is not None:
            return self._scan_result

        # Default: no violations
        return ScanResult.no_violations()

    async def get_prohibited_terms(self) -> tuple[str, ...]:
        """Return configured prohibited terms."""
        return self._terms
