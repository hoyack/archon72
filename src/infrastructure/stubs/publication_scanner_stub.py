"""Publication scanner stub for testing (Story 9.2, FR56).

Provides in-memory implementation of PublicationScannerProtocol
for unit and integration tests.

Usage:
    stub = PublicationScannerStub()

    # Scan a publication
    request = PublicationScanRequest(
        publication_id="pub-123",
        content="Clean content",
        title="My Article",
    )
    result = await stub.scan_publication(request)
    assert result.is_clean == True

    # Configure violation for testing
    stub.configure_next_scan_blocked(("emergence",))
"""

from __future__ import annotations

from datetime import datetime, timezone

from src.application.ports.publication_scanner import (
    PublicationScannerProtocol,
    PublicationScanResult,
)
from src.domain.models.publication import PublicationScanRequest
from src.infrastructure.stubs.prohibited_language_scanner_stub import (
    ProhibitedLanguageScannerStub,
)


class PublicationScannerStub(PublicationScannerProtocol):
    """In-memory stub implementation of PublicationScannerProtocol.

    Uses ProhibitedLanguageScannerStub internally for actual scanning.
    Maintains scan history in-memory for testing assertions.

    Attributes:
        _scanner: ProhibitedLanguageScannerStub for actual content scanning.
        _scan_history: In-memory scan history (publication_id -> list of results).
        _scan_count: Number of scans performed.
        _next_scan_override: Optional override for next scan result.
    """

    def __init__(
        self,
        terms: tuple[str, ...] | None = None,
        detection_method: str = "nfkc_scan",
    ) -> None:
        """Initialize the publication scanner stub.

        Args:
            terms: Custom prohibited terms, or None to use defaults.
            detection_method: Method name to return in results.
        """
        self._scanner = ProhibitedLanguageScannerStub(
            terms=terms,
            detection_method=detection_method,
        )
        self._detection_method = detection_method
        self._scan_history: dict[str, list[PublicationScanResult]] = {}
        self._scan_count: int = 0
        self._next_scan_override: tuple[str, ...] | None = None
        self._force_error: Exception | None = None

    # Configuration methods for tests

    def set_prohibited_terms(self, terms: tuple[str, ...]) -> None:
        """Set custom prohibited terms for testing.

        Args:
            terms: Tuple of prohibited terms.
        """
        self._scanner.set_prohibited_terms(terms)

    def reset_to_defaults(self) -> None:
        """Reset to default prohibited terms."""
        self._scanner.reset_to_defaults()

    def configure_next_scan_blocked(self, matched_terms: tuple[str, ...]) -> None:
        """Configure the next scan to return a blocked result.

        Args:
            matched_terms: Terms to report as matched.
        """
        self._next_scan_override = matched_terms

    def configure_next_scan_clean(self) -> None:
        """Configure the next scan to return a clean result."""
        self._next_scan_override = ()

    def configure_error(self, error: Exception) -> None:
        """Configure the next scan to raise an error.

        Args:
            error: Exception to raise on next scan.
        """
        self._force_error = error

    def reset_configuration(self) -> None:
        """Reset scan configuration to defaults."""
        self._next_scan_override = None
        self._force_error = None

    def reset_counters(self) -> None:
        """Reset scan count and history for assertions."""
        self._scan_count = 0
        self._scan_history.clear()

    # Accessors for test assertions

    @property
    def scan_count(self) -> int:
        """Get number of scans performed."""
        return self._scan_count

    @property
    def terms(self) -> tuple[str, ...]:
        """Get current prohibited terms."""
        return self._scanner.terms

    def get_scan_count_for_publication(self, publication_id: str) -> int:
        """Get scan count for a specific publication.

        Args:
            publication_id: ID of the publication.

        Returns:
            Number of times publication was scanned.
        """
        return len(self._scan_history.get(publication_id, []))

    # Protocol implementation

    async def scan_publication(
        self, request: PublicationScanRequest
    ) -> PublicationScanResult:
        """Scan a publication for prohibited language (FR56).

        Uses ProhibitedLanguageScannerStub internally for actual scanning.

        Args:
            request: The publication scan request.

        Returns:
            PublicationScanResult with status and any matched terms.

        Raises:
            Exception: If configured to raise error.
        """
        self._scan_count += 1
        scanned_at = datetime.now(timezone.utc)

        # Check if error is configured
        if self._force_error is not None:
            error = self._force_error
            self._force_error = None
            raise error

        # Check for override
        if self._next_scan_override is not None:
            matched_terms = self._next_scan_override
            self._next_scan_override = None

            if matched_terms:
                result = PublicationScanResult.blocked(
                    publication_id=request.publication_id,
                    matched_terms=matched_terms,
                    scanned_at=scanned_at,
                    detection_method=self._detection_method,
                )
            else:
                result = PublicationScanResult.clean(
                    publication_id=request.publication_id,
                    scanned_at=scanned_at,
                    detection_method=self._detection_method,
                )
        else:
            # Use real scanner
            scan_result = await self._scanner.scan_content(request.content)

            if scan_result.violations_found:
                result = PublicationScanResult.blocked(
                    publication_id=request.publication_id,
                    matched_terms=scan_result.matched_terms,
                    scanned_at=scanned_at,
                    detection_method=scan_result.detection_method,
                )
            else:
                result = PublicationScanResult.clean(
                    publication_id=request.publication_id,
                    scanned_at=scanned_at,
                    detection_method=scan_result.detection_method,
                )

        # Record in history
        if request.publication_id not in self._scan_history:
            self._scan_history[request.publication_id] = []
        self._scan_history[request.publication_id].append(result)

        return result

    async def get_scan_history(
        self, publication_id: str
    ) -> list[PublicationScanResult]:
        """Get scan history for a publication.

        Args:
            publication_id: ID of the publication.

        Returns:
            List of PublicationScanResult for the publication,
            ordered most recent first.
        """
        history = self._scan_history.get(publication_id, [])
        return list(reversed(history))


class ConfigurablePublicationScannerStub(PublicationScannerProtocol):
    """Configurable scanner stub for fine-grained test control.

    Unlike PublicationScannerStub which performs real scanning,
    this stub allows tests to configure exact return values.

    Useful for:
    - Testing error paths (configure to raise exceptions)
    - Testing specific results (configure exact outcomes)
    - Testing service behavior without real scanning logic
    """

    def __init__(self) -> None:
        """Initialize with default clean responses."""
        self._scan_result: PublicationScanResult | None = None
        self._scan_exception: Exception | None = None
        self._scan_history: dict[str, list[PublicationScanResult]] = {}
        self._scan_count: int = 0

    # Configuration methods

    def configure_clean_result(
        self,
        publication_id: str = "pub-default",
        detection_method: str = "nfkc_scan",
    ) -> None:
        """Configure to return clean results."""
        self._scan_result = PublicationScanResult.clean(
            publication_id=publication_id,
            scanned_at=datetime.now(timezone.utc),
            detection_method=detection_method,
        )
        self._scan_exception = None

    def configure_blocked_result(
        self,
        publication_id: str = "pub-default",
        matched_terms: tuple[str, ...] = ("emergence",),
        detection_method: str = "nfkc_scan",
    ) -> None:
        """Configure to return blocked results.

        Args:
            publication_id: ID of the publication.
            matched_terms: Terms to include in result.
            detection_method: Detection method name.
        """
        self._scan_result = PublicationScanResult.blocked(
            publication_id=publication_id,
            matched_terms=matched_terms,
            scanned_at=datetime.now(timezone.utc),
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

    def reset(self) -> None:
        """Reset to default configuration."""
        self._scan_result = None
        self._scan_exception = None
        self._scan_history.clear()
        self._scan_count = 0

    @property
    def scan_count(self) -> int:
        """Get number of scans performed."""
        return self._scan_count

    # Protocol implementation

    async def scan_publication(
        self, request: PublicationScanRequest
    ) -> PublicationScanResult:
        """Return configured scan result or raise configured exception."""
        self._scan_count += 1

        if self._scan_exception is not None:
            raise self._scan_exception

        if self._scan_result is not None:
            # Create new result with correct publication_id
            scanned_at = datetime.now(timezone.utc)
            if self._scan_result.is_blocked:
                result = PublicationScanResult.blocked(
                    publication_id=request.publication_id,
                    matched_terms=self._scan_result.matched_terms,
                    scanned_at=scanned_at,
                    detection_method=self._scan_result.detection_method,
                )
            else:
                result = PublicationScanResult.clean(
                    publication_id=request.publication_id,
                    scanned_at=scanned_at,
                    detection_method=self._scan_result.detection_method,
                )
        else:
            # Default: clean result
            result = PublicationScanResult.clean(
                publication_id=request.publication_id,
                scanned_at=datetime.now(timezone.utc),
                detection_method="nfkc_scan",
            )

        # Record in history
        if request.publication_id not in self._scan_history:
            self._scan_history[request.publication_id] = []
        self._scan_history[request.publication_id].append(result)

        return result

    async def get_scan_history(
        self, publication_id: str
    ) -> list[PublicationScanResult]:
        """Return configured scan history."""
        history = self._scan_history.get(publication_id, [])
        return list(reversed(history))
