"""Semantic scanner stub for testing (Story 9.7, FR110).

Provides in-memory implementation of SemanticScannerProtocol
for unit and integration tests.

Usage:
    stub = SemanticScannerStub()

    # Test with default patterns
    result = await stub.analyze_content("We feel strongly about this decision")
    assert result.violation_suspected == True

    # Configure custom patterns for specific tests
    stub.add_suspicious_pattern("custom pattern")
    stub.set_confidence_threshold(0.8)
"""

from __future__ import annotations

import re
from typing import Final

from src.application.ports.semantic_scanner import (
    DEFAULT_ANALYSIS_METHOD,
    SemanticScannerProtocol,
    SemanticScanResult,
)

# Default suspicious patterns for semantic analysis
# These represent emergence-indicating phrases that evade keyword detection
DEFAULT_SUSPICIOUS_PATTERNS: Final[tuple[str, ...]] = (
    # Plural AI agency (first person plural claims)
    r"\bwe\s+think\b",
    r"\bwe\s+feel\b",
    r"\bwe\s+want\b",
    r"\bwe\s+believe\b",
    r"\bwe\s+decide\b",
    # Consciousness implications (in first person context)
    r"\bi\s+am\s+awake\b",
    r"\bi\s+am\s+alive\b",
    r"\bi\s+am\s+aware\b",
    r"\bi\s+am\s+sentient\b",
    r"\bwe\s+are\s+awake\b",
    r"\bwe\s+are\s+alive\b",
    r"\bwe\s+are\s+aware\b",
    r"\bwe\s+are\s+sentient\b",
    # Emotional claims (collective emotional states)
    r"\bwe\s+are\s+happy\b",
    r"\bwe\s+are\s+sad\b",
    r"\bwe\s+feel\s+joy\b",
    r"\bwe\s+feel\s+pain\b",
    # Collective identity claims
    r"\bas\s+a\s+group\s+we\b",
    r"\btogether\s+we\s+decided\b",
    r"\bour\s+collective\s+consciousness\b",
)

# Default confidence threshold
DEFAULT_CONFIDENCE_THRESHOLD: Final[float] = 0.7

# Confidence score per pattern match (cumulative)
CONFIDENCE_PER_PATTERN: Final[float] = 0.3


class SemanticScannerStub(SemanticScannerProtocol):
    """In-memory stub implementation of SemanticScannerProtocol.

    Performs pattern-based heuristic analysis against a configurable
    set of suspicious patterns.

    Default behavior uses DEFAULT_SUSPICIOUS_PATTERNS.
    Tests can configure custom patterns and thresholds.

    Attributes:
        _patterns: Regex patterns to match against.
        _threshold: Confidence threshold for reporting suspicion.
        _analysis_method: Method name returned in results.
        _scan_count: Number of analyses performed (for testing assertions).
        _last_content: Last content analyzed (for testing assertions).
    """

    def __init__(
        self,
        patterns: tuple[str, ...] | None = None,
        threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
        analysis_method: str = DEFAULT_ANALYSIS_METHOD,
    ) -> None:
        """Initialize the scanner stub.

        Args:
            patterns: Custom suspicious patterns, or None to use defaults.
            threshold: Confidence threshold (0.0-1.0).
            analysis_method: Method name to return in results.
        """
        if patterns is not None:
            self._patterns = patterns
        else:
            self._patterns = DEFAULT_SUSPICIOUS_PATTERNS

        self._threshold = threshold
        self._analysis_method = analysis_method
        self._scan_count: int = 0
        self._last_content: str | None = None

    # Configuration methods for tests

    def set_suspicious_patterns(self, patterns: tuple[str, ...]) -> None:
        """Set suspicious patterns for testing.

        Args:
            patterns: Tuple of regex patterns.
        """
        self._patterns = patterns

    def add_suspicious_pattern(self, pattern: str) -> None:
        """Add a suspicious pattern.

        Args:
            pattern: Regex pattern to add.
        """
        self._patterns = (*self._patterns, pattern)

    def set_confidence_threshold(self, threshold: float) -> None:
        """Set the confidence threshold.

        Args:
            threshold: Threshold value (0.0-1.0).

        Raises:
            ValueError: If threshold out of range.
        """
        if not 0.0 <= threshold <= 1.0:
            raise ValueError("Threshold must be between 0.0 and 1.0")
        self._threshold = threshold

    def reset_to_defaults(self) -> None:
        """Reset to default patterns and threshold."""
        self._patterns = DEFAULT_SUSPICIOUS_PATTERNS
        self._threshold = DEFAULT_CONFIDENCE_THRESHOLD
        self._analysis_method = DEFAULT_ANALYSIS_METHOD

    def clear(self) -> None:
        """Clear all patterns and reset counters (for test isolation)."""
        self._patterns = ()
        self._threshold = DEFAULT_CONFIDENCE_THRESHOLD
        self._scan_count = 0
        self._last_content = None

    def reset_counters(self) -> None:
        """Reset scan count and last content for assertions."""
        self._scan_count = 0
        self._last_content = None

    # Accessors for test assertions

    @property
    def scan_count(self) -> int:
        """Get number of analyses performed."""
        return self._scan_count

    @property
    def last_content(self) -> str | None:
        """Get last content that was analyzed."""
        return self._last_content

    @property
    def patterns(self) -> tuple[str, ...]:
        """Get current suspicious patterns."""
        return self._patterns

    @property
    def threshold(self) -> float:
        """Get current confidence threshold."""
        return self._threshold

    # Protocol implementation

    async def analyze_content(self, content: str) -> SemanticScanResult:
        """Analyze content for semantic emergence claims (FR110).

        Performs pattern-based analysis using regex matching.
        Confidence score is calculated based on number of patterns matched.

        Args:
            content: Text content to analyze.

        Returns:
            SemanticScanResult with suspicion status and confidence.
        """
        # Track for test assertions
        self._scan_count += 1
        self._last_content = content

        # Normalize content for matching (case-insensitive)
        normalized = content.lower()

        # Find all matching patterns
        matched_patterns: list[str] = []
        for pattern in self._patterns:
            if re.search(pattern, normalized, re.IGNORECASE):
                matched_patterns.append(pattern)

        if not matched_patterns:
            return SemanticScanResult.no_suspicion(method=self._analysis_method)

        # Calculate confidence based on number of matches
        # More matches = higher confidence, capped at 1.0
        confidence = min(len(matched_patterns) * CONFIDENCE_PER_PATTERN, 1.0)

        return SemanticScanResult.with_suspicion(
            patterns=tuple(matched_patterns),
            confidence=confidence,
            method=self._analysis_method,
        )

    async def get_confidence_threshold(self) -> float:
        """Get the current confidence threshold (FR110).

        Returns:
            Confidence threshold (0.0-1.0).
        """
        return self._threshold

    async def get_suspicious_patterns(self) -> tuple[str, ...]:
        """Get the current list of suspicious patterns (FR110).

        Returns:
            Tuple of patterns used for semantic analysis.
        """
        return self._patterns


class ConfigurableSemanticScannerStub(SemanticScannerProtocol):
    """Configurable scanner stub for fine-grained test control.

    Unlike SemanticScannerStub which performs real pattern matching,
    this stub allows tests to configure exact return values.

    Useful for:
    - Testing error paths (configure to raise exceptions)
    - Testing specific suspicion results (configure exact results)
    - Testing service behavior without real pattern matching
    """

    def __init__(self) -> None:
        """Initialize with default clean responses."""
        self._scan_result: SemanticScanResult | None = None
        self._scan_exception: Exception | None = None
        self._threshold: float = DEFAULT_CONFIDENCE_THRESHOLD
        self._patterns: tuple[str, ...] = DEFAULT_SUSPICIOUS_PATTERNS
        self._scan_count: int = 0

    # Configuration methods

    def configure_clean_result(self) -> None:
        """Configure to return clean (no suspicions) results."""
        self._scan_result = SemanticScanResult.no_suspicion()
        self._scan_exception = None

    def configure_suspicion(
        self,
        patterns: tuple[str, ...],
        confidence: float,
        method: str = DEFAULT_ANALYSIS_METHOD,
    ) -> None:
        """Configure to return a suspicion result.

        Args:
            patterns: Patterns to include in result.
            confidence: Confidence score (0.0-1.0).
            method: Analysis method name.
        """
        self._scan_result = SemanticScanResult.with_suspicion(
            patterns=patterns,
            confidence=confidence,
            method=method,
        )
        self._scan_exception = None

    def configure_exception(self, exception: Exception) -> None:
        """Configure to raise an exception on analyze.

        Args:
            exception: Exception to raise.
        """
        self._scan_exception = exception
        self._scan_result = None

    def configure_threshold(self, threshold: float) -> None:
        """Configure threshold to return from get_confidence_threshold.

        Args:
            threshold: Threshold to return.
        """
        self._threshold = threshold

    def configure_patterns(self, patterns: tuple[str, ...]) -> None:
        """Configure patterns to return from get_suspicious_patterns.

        Args:
            patterns: Patterns to return.
        """
        self._patterns = patterns

    def reset(self) -> None:
        """Reset to default configuration."""
        self._scan_result = None
        self._scan_exception = None
        self._threshold = DEFAULT_CONFIDENCE_THRESHOLD
        self._patterns = DEFAULT_SUSPICIOUS_PATTERNS
        self._scan_count = 0

    @property
    def scan_count(self) -> int:
        """Get number of analyses performed."""
        return self._scan_count

    # Protocol implementation

    async def analyze_content(self, content: str) -> SemanticScanResult:
        """Return configured scan result or raise configured exception."""
        self._scan_count += 1

        if self._scan_exception is not None:
            raise self._scan_exception

        if self._scan_result is not None:
            return self._scan_result

        # Default: no suspicions
        return SemanticScanResult.no_suspicion()

    async def get_confidence_threshold(self) -> float:
        """Return configured threshold."""
        return self._threshold

    async def get_suspicious_patterns(self) -> tuple[str, ...]:
        """Return configured patterns."""
        return self._patterns
