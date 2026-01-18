"""Semantic scanner port interface (Story 9.7, FR110).

Defines the protocol for semantic analysis of content to detect
emergence claims that evade keyword-based detection.

Constitutional Constraints:
- FR110: Secondary semantic scanning beyond keyword matching
- FR55: System outputs never claim emergence, consciousness, etc.
- CT-11: Silent failure destroys legitimacy -> fail loud on scan errors
- CT-12: All suspected violations must be witnessed
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Protocol

# Default confidence threshold for semantic scanning
DEFAULT_ANALYSIS_METHOD: Final[str] = "pattern_analysis"


@dataclass(frozen=True)
class SemanticScanResult:
    """Result of semantic content analysis (FR110).

    This immutable result object contains information about any
    suspected violations found during semantic analysis.

    Note: This represents SUSPECTED violations based on pattern-based
    heuristics. Unlike keyword scanning which is deterministic,
    semantic analysis is probabilistic and may require human review.

    Attributes:
        violation_suspected: True if patterns suggest emergence claims.
        suspected_patterns: Patterns that triggered suspicion.
        confidence_score: Analysis confidence (0.0-1.0).
        analysis_method: How the analysis was performed.
    """

    violation_suspected: bool
    suspected_patterns: tuple[str, ...]
    confidence_score: float
    analysis_method: str

    @classmethod
    def no_suspicion(cls, method: str = DEFAULT_ANALYSIS_METHOD) -> SemanticScanResult:
        """Create a clean scan result with no suspicions.

        Args:
            method: Analysis method used.

        Returns:
            SemanticScanResult indicating no violations suspected.
        """
        return cls(
            violation_suspected=False,
            suspected_patterns=(),
            confidence_score=0.0,
            analysis_method=method,
        )

    @classmethod
    def with_suspicion(
        cls,
        patterns: tuple[str, ...],
        confidence: float,
        method: str = DEFAULT_ANALYSIS_METHOD,
    ) -> SemanticScanResult:
        """Create a scan result with suspected violations.

        Args:
            patterns: Patterns that triggered suspicion.
            confidence: Analysis confidence (0.0-1.0).
            method: Analysis method used.

        Returns:
            SemanticScanResult indicating suspected violations.

        Raises:
            ValueError: If patterns is empty or confidence out of range.
        """
        if not patterns:
            raise ValueError("FR110: patterns cannot be empty for suspicions")
        if not 0.0 <= confidence <= 1.0:
            raise ValueError("FR110: confidence must be between 0.0 and 1.0")
        return cls(
            violation_suspected=True,
            suspected_patterns=patterns,
            confidence_score=confidence,
            analysis_method=method,
        )

    @property
    def pattern_count(self) -> int:
        """Get the number of suspected patterns."""
        return len(self.suspected_patterns)


class SemanticScannerProtocol(Protocol):
    """Protocol for semantic content analysis (FR110).

    This port enables dependency inversion for semantic analysis logic.
    Implementations are responsible for:
    - Maintaining suspicious pattern definitions
    - Applying pattern-based heuristics for detection
    - Returning structured results with confidence scores
    - Managing confidence thresholds

    Constitutional Constraints:
    - FR110: Secondary semantic scanning beyond keyword matching
    - FR55: No emergence claims (base requirement)

    Detection Approach (Pattern-Based Heuristics):
    1. Plural AI agency: "we think", "we feel", "we want", "we believe"
    2. Consciousness implications: "awake", "alive", "aware", "sentient"
    3. Emotional claims: "we are happy", "we are sad", "we feel joy"
    4. Collective identity: "as a group we", "together we decided"

    Why Patterns Over LLM:
    - Deterministic, testable results
    - No LLM cost/latency for every scan
    - Clear audit trail of what triggered suspicion
    - LLM could be added later as tertiary check if needed
    """

    async def analyze_content(self, content: str) -> SemanticScanResult:
        """Analyze content for semantic emergence claims (FR110).

        Performs pattern-based analysis to detect emergence claims
        that might evade keyword scanning.

        Args:
            content: Text content to analyze.

        Returns:
            SemanticScanResult with suspicion status and confidence.

        Note:
            This method does not raise on suspicions - it returns a result.
            The calling service is responsible for handling suspected
            violations (creating events, etc.).
        """
        ...

    async def get_confidence_threshold(self) -> float:
        """Get the current confidence threshold (FR110).

        Content with confidence_score >= threshold triggers
        suspected violation events.

        Returns:
            Confidence threshold (0.0-1.0).

        Note:
            Default threshold is 0.7 - balancing detection vs false positives.
        """
        ...

    async def get_suspicious_patterns(self) -> tuple[str, ...]:
        """Get the current list of suspicious patterns (FR110).

        Returns:
            Tuple of patterns used for semantic analysis.

        Note:
            These patterns are configurable at initialization but
            immutable at runtime (like prohibited terms in keyword scanning).
        """
        ...
