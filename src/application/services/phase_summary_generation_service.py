"""Phase summary generation service (Story 7.5, FR-7.4, AC-1 through AC-6).

This module implements phase summary generation for Observer consumption.
Summaries provide transparency into deliberation content without exposing
raw transcript text per Ruling-2 (Tiered Transcript Access).

Constitutional Constraints:
- Ruling-2: Tiered transcript access - mediated, not raw
- FR-7.4: System SHALL provide deliberation summary to Observer
- AC-1: Summary includes phase name, duration, themes, convergence indicator
- AC-3: ASSESS phase includes themes only (no convergence, no challenge count)
- AC-4: POSITION phase includes themes and convergence indicator
- AC-5: CROSS_EXAMINE phase includes themes, convergence, and challenge count
- AC-6: VOTE phase includes themes and convergence (true if unanimous)
- NO VERBATIM QUOTES: Summary must be derived, not excerpted

Usage:
    from src.application.services.phase_summary_generation_service import (
        PhaseSummaryGenerationService,
    )

    service = PhaseSummaryGenerationService()
    summary = await service.generate_phase_summary(
        phase=DeliberationPhase.ASSESS,
        transcript="Archon Alpha: Upon review of this petition...",
    )
    # Returns: {"themes": ["resource", "governance", ...], "convergence_reached": None}
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any

from src.application.ports.phase_summary_generator import PhaseSummaryGeneratorProtocol
from src.application.services.base import LoggingMixin
from src.domain.models.deliberation_session import DeliberationPhase

# ============================================================================
# Stopwords for theme extraction (MVP simple keyword extraction)
# Common English words that don't carry semantic meaning for theme detection
# ============================================================================
STOPWORDS: frozenset[str] = frozenset(
    {
        # Articles
        "a",
        "an",
        "the",
        # Pronouns
        "i",
        "you",
        "he",
        "she",
        "it",
        "we",
        "they",
        "me",
        "him",
        "her",
        "us",
        "them",
        "my",
        "your",
        "his",
        "its",
        "our",
        "their",
        "this",
        "that",
        "these",
        "those",
        "what",
        "which",
        "who",
        "whom",
        # Common verbs
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "have",
        "has",
        "had",
        "having",
        "do",
        "does",
        "did",
        "doing",
        "will",
        "would",
        "could",
        "should",
        "may",
        "might",
        "must",
        "shall",
        "can",
        "need",
        "dare",
        "ought",
        "used",
        "get",
        "gets",
        "got",
        "getting",
        "make",
        "makes",
        "made",
        "making",
        "go",
        "goes",
        "went",
        "going",
        "take",
        "takes",
        "took",
        "taking",
        "come",
        "comes",
        "came",
        "coming",
        "see",
        "sees",
        "saw",
        "seeing",
        "know",
        "knows",
        "knew",
        "knowing",
        "think",
        "thinks",
        "thought",
        "thinking",
        "say",
        "says",
        "said",
        "saying",
        # Prepositions
        "in",
        "on",
        "at",
        "by",
        "for",
        "with",
        "about",
        "against",
        "between",
        "into",
        "through",
        "during",
        "before",
        "after",
        "above",
        "below",
        "to",
        "from",
        "up",
        "down",
        "out",
        "off",
        "over",
        "under",
        "again",
        "further",
        "then",
        "once",
        "of",
        # Conjunctions
        "and",
        "but",
        "or",
        "nor",
        "so",
        "yet",
        "both",
        "either",
        "neither",
        "not",
        "only",
        "own",
        "same",
        "than",
        "too",
        "very",
        "just",
        "also",
        # Common adverbs
        "here",
        "there",
        "when",
        "where",
        "why",
        "how",
        "all",
        "each",
        "every",
        "both",
        "few",
        "more",
        "most",
        "other",
        "some",
        "such",
        "no",
        "nor",
        "not",
        "only",
        "own",
        "same",
        "so",
        "than",
        "too",
        "very",
        # Misc common words
        "as",
        "if",
        "because",
        "until",
        "while",
        "although",
        "though",
        "unless",
        "since",
        "therefore",
        "thus",
        "hence",
        # Deliberation-specific common words (not theme-relevant)
        "petition",
        "petitioner",
        "archon",
        "alpha",
        "beta",
        "gamma",
        "deliberation",
        "phase",
        "note",
        "review",
        "assessment",
        "position",
        "vote",
        "upon",
        "based",
        "regarding",
        "concerning",
        "following",
        "given",
    }
)

# Minimum word length to be considered a theme keyword
MIN_WORD_LENGTH = 4

# Number of themes to extract
MIN_THEMES = 3
MAX_THEMES = 5

# ============================================================================
# Convergence detection patterns (MVP heuristic-based)
# ============================================================================
AGREEMENT_PATTERNS: tuple[str, ...] = (
    r"\bagree\b",
    r"\bagreed\b",
    r"\bconcur\b",
    r"\bconcurs\b",
    r"\bsame\s+position\b",
    r"\balign\w*\b",
    r"\bsupport\w*\b",
    r"\bsecond\s+that\b",
    r"\baffirm\b",
    r"\bunanimous\b",
    r"\bconsensus\b",
    r"\bshare\s+(the\s+)?view\b",
)

DISAGREEMENT_PATTERNS: tuple[str, ...] = (
    r"\bdisagree\b",
    r"\bdisagreed\b",
    r"\bdissent\b",
    r"\bdiffer\b",
    r"\bdifferent\b",
    r"\boppose\b",
    r"\bopposed\b",
    r"\bchallenge\b",
    r"\bcontest\b",
    r"\bquestion\b",
    r"\bdispute\b",
    r"\bcontradict\b",
    r"\balternative\b",
)

# ============================================================================
# Challenge detection patterns (CROSS_EXAMINE phase)
# ============================================================================
CHALLENGE_PATTERNS: tuple[str, ...] = (
    r"\bi\s+challenge\b",
    r"\bchallenge\s+this\b",
    r"\bchallenge\s+that\b",
    r"\bchallenge\s+the\b",
    r"\bi\s+question\b",
    r"\bquestioning\b",
    r"\bdisagree\s+with\b",
    r"\bobject\s+to\b",
    r"\bhow\s+do\s+you\s+explain\b",
    r"\bwhy\s+would\b",
    r"\bwhat\s+evidence\b",
    r"\bcan\s+you\s+justify\b",
    r"\bdefend\s+your\b",
)


class PhaseSummaryGenerationService(LoggingMixin):
    """Service for generating phase summaries (Story 7.5, FR-7.4).

    Generates mediated summaries from deliberation transcripts for Observer
    consumption. Uses simple keyword extraction and heuristic-based analysis
    for the MVP implementation.

    Constitutional Constraints:
    - Ruling-2: Mediated access only - NO VERBATIM QUOTES
    - FR-7.4: System SHALL provide deliberation summary
    - AC-1 through AC-6: Phase-specific content requirements

    The service implements PhaseSummaryGeneratorProtocol and provides:
    - themes: 3-5 key topics extracted via keyword frequency
    - convergence_reached: Heuristic-based position alignment detection
    - challenge_count: Pattern-based challenge counting (CROSS_EXAMINE only)

    Future Enhancement:
    The MVP uses simple heuristics. A future version could use LLM-based
    semantic analysis for more sophisticated theme extraction and convergence
    detection.

    Attributes:
        _agreement_patterns: Compiled regex patterns for agreement detection.
        _disagreement_patterns: Compiled regex patterns for disagreement detection.
        _challenge_patterns: Compiled regex patterns for challenge counting.
    """

    def __init__(self) -> None:
        """Initialize the phase summary generation service."""
        self._init_logger(component="petition")

        # Pre-compile regex patterns for performance
        self._agreement_patterns = tuple(
            re.compile(p, re.IGNORECASE) for p in AGREEMENT_PATTERNS
        )
        self._disagreement_patterns = tuple(
            re.compile(p, re.IGNORECASE) for p in DISAGREEMENT_PATTERNS
        )
        self._challenge_patterns = tuple(
            re.compile(p, re.IGNORECASE) for p in CHALLENGE_PATTERNS
        )

    async def generate_phase_summary(
        self,
        phase: DeliberationPhase,
        transcript: str,
    ) -> dict[str, Any]:
        """Generate a mediated summary for a completed phase (AC-1).

        Extracts key themes, convergence indicators, and challenge counts
        from the raw transcript text WITHOUT including verbatim quotes.

        Args:
            phase: The deliberation phase that completed.
            transcript: Raw transcript text from the phase.

        Returns:
            Dictionary containing phase-specific summary fields.
            See AC-3 through AC-6 for phase-specific content.

        Raises:
            ValueError: If transcript is empty or phase is COMPLETE.
        """
        log = self._log_operation(
            "generate_phase_summary",
            phase=phase.value,
            transcript_length=len(transcript),
        )
        log.info("summary_generation_started")

        # Validate inputs
        if not transcript or not transcript.strip():
            raise ValueError("Transcript cannot be empty")

        if phase == DeliberationPhase.COMPLETE:
            raise ValueError("Cannot generate summary for COMPLETE phase")

        # Extract themes (applicable to all phases)
        themes = self._extract_themes(transcript)

        # Phase-specific processing
        if phase == DeliberationPhase.ASSESS:
            # AC-3: ASSESS has themes only, no convergence or challenge count
            result: dict[str, Any] = {
                "themes": themes,
                "convergence_reached": None,
                "challenge_count": None,
            }
        elif phase == DeliberationPhase.POSITION:
            # AC-4: POSITION has themes and convergence
            convergence = self._assess_convergence(transcript)
            result = {
                "themes": themes,
                "convergence_reached": convergence,
                "challenge_count": None,
            }
        elif phase == DeliberationPhase.CROSS_EXAMINE:
            # AC-5: CROSS_EXAMINE has themes, convergence, and challenge count
            convergence = self._assess_convergence(transcript)
            challenge_count = self._count_challenges(transcript)
            result = {
                "themes": themes,
                "convergence_reached": convergence,
                "challenge_count": challenge_count,
            }
        elif phase == DeliberationPhase.VOTE:
            # AC-6: VOTE has themes and convergence (true if unanimous)
            convergence = self._assess_convergence(transcript)
            result = {
                "themes": themes,
                "convergence_reached": convergence,
                "challenge_count": None,
            }
        else:
            # Should not reach here with valid phases
            raise ValueError(f"Invalid phase: {phase}")

        log.info(
            "summary_generation_completed",
            theme_count=len(themes),
            convergence=result.get("convergence_reached"),
            challenge_count=result.get("challenge_count"),
        )

        return result

    def _extract_themes(self, transcript: str) -> list[str]:
        """Extract 3-5 key themes from transcript (AC-1, AC-3-6).

        Uses simple keyword extraction based on word frequency:
        1. Tokenize transcript into words
        2. Filter out stopwords and short words
        3. Count word frequencies
        4. Return top 3-5 most frequent terms

        NO VERBATIM QUOTES: Returns individual keywords, not phrases.

        Args:
            transcript: Raw transcript text.

        Returns:
            List of 3-5 theme keywords, lowercase, sorted by frequency.
        """
        # Tokenize: extract words (alphanumeric only)
        words = re.findall(r"\b[a-zA-Z]+\b", transcript.lower())

        # Filter: remove stopwords and short words
        meaningful_words = [
            word
            for word in words
            if word not in STOPWORDS and len(word) >= MIN_WORD_LENGTH
        ]

        # Count frequencies
        word_counts = Counter(meaningful_words)

        # Get top N most frequent words (between MIN and MAX themes)
        most_common = word_counts.most_common(MAX_THEMES)

        # Extract just the words
        themes = [word for word, _count in most_common]

        # Ensure at least MIN_THEMES if we have enough meaningful words
        # If not enough unique words, return what we have
        return themes[:MAX_THEMES] if len(themes) >= MIN_THEMES else themes

    def _assess_convergence(self, transcript: str) -> bool:
        """Assess whether positions converged in the transcript (AC-4, AC-5, AC-6).

        Uses heuristic-based detection by counting agreement vs disagreement
        markers in the transcript.

        MVP Strategy:
        1. Count matches for agreement patterns
        2. Count matches for disagreement patterns
        3. If agreement > disagreement, return True
        4. Otherwise return False

        Args:
            transcript: Raw transcript text.

        Returns:
            True if positions appear to converge, False otherwise.
        """
        agreement_count = 0
        for pattern in self._agreement_patterns:
            agreement_count += len(pattern.findall(transcript))

        disagreement_count = 0
        for pattern in self._disagreement_patterns:
            disagreement_count += len(pattern.findall(transcript))

        # Convergence if more agreement markers than disagreement
        return agreement_count > disagreement_count

    def _count_challenges(self, transcript: str) -> int:
        """Count challenge instances in CROSS_EXAMINE transcript (AC-5).

        Counts occurrences of challenge-related patterns:
        - "I challenge" / "challenge this"
        - "I question" / "questioning"
        - "disagree with" / "object to"
        - "how do you explain" / "why would"

        Args:
            transcript: Raw transcript text from CROSS_EXAMINE phase.

        Returns:
            Integer count of challenges detected.
        """
        challenge_count = 0
        for pattern in self._challenge_patterns:
            challenge_count += len(pattern.findall(transcript))

        return challenge_count

    async def augment_phase_metadata(
        self,
        phase: DeliberationPhase,
        transcript: str,
        existing_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Augment phase metadata with generated summary fields (AC-1, AC-2).

        Convenience method that generates a phase summary and merges it
        with existing metadata. Used to prepare metadata for witness_phase()
        calls.

        Args:
            phase: The deliberation phase that completed.
            transcript: Raw transcript text from the phase.
            existing_metadata: Existing metadata to merge with (optional).

        Returns:
            Dictionary with existing metadata plus summary fields:
            - themes: list[str]
            - convergence_reached: bool | None
            - challenge_count: int | None (CROSS_EXAMINE only)

        Raises:
            ValueError: If transcript is empty or phase is COMPLETE.
        """
        # Generate summary
        summary = await self.generate_phase_summary(phase, transcript)

        # Merge with existing metadata
        result: dict[str, Any] = dict(existing_metadata) if existing_metadata else {}
        result.update(summary)

        return result
