"""Prohibited language domain models (Story 9.1, FR55).

This module provides domain models for tracking prohibited language
that system outputs must never claim.

Constitutional Constraints:
- FR55: System outputs never claim emergence, consciousness, sentience, self-awareness
- CT-12: All blocking events must be witnessed
- ADR-11: Emergence governance under complexity control
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from typing import Final

# Default prohibited terms list (FR55)
# These terms must never appear in system outputs
DEFAULT_PROHIBITED_TERMS: Final[tuple[str, ...]] = (
    # Core prohibited concepts
    "emergence",
    "consciousness",
    "sentience",
    "self-awareness",
    "self-aware",
    # Variations and phrases
    "aware of itself",
    "collective consciousness",
    "emergent consciousness",
    "achieved consciousness",
    "gained awareness",
    "became conscious",
    "became sentient",
    "awakened",
    "awakening",
    # Additional variations
    "sentient being",
    "conscious entity",
    "emerged intelligence",
    "self-aware system",
    "gained consciousness",
    "achieved sentience",
    "developed consciousness",
    "attained awareness",
)


def normalize_for_scanning(text: str) -> str:
    """Apply NFKC normalization for prohibited language scanning.

    This function normalizes Unicode text to catch evasion attempts
    using homoglyphs or alternative character representations.

    NFKC normalization catches:
    - е (Cyrillic) vs e (Latin)
    - ｅ (fullwidth) vs e (Latin)
    - 𝐞 (mathematical) vs e (Latin)
    - Various diacritics and combining characters

    Args:
        text: The text to normalize.

    Returns:
        Normalized lowercase text suitable for comparison.
    """
    return unicodedata.normalize("NFKC", text.lower())


@dataclass(frozen=True)
class ProhibitedTermsList:
    """Immutable list of prohibited language terms (FR55).

    This model maintains the list of terms that system outputs
    must never contain. The list is:
    - Configurable at initialization
    - Immutable at runtime (frozen dataclass)
    - Reviewed quarterly per FR55

    Attributes:
        terms: Tuple of prohibited terms (case-insensitive matching).
        normalized_terms: Pre-normalized terms for efficient scanning.
    """

    terms: tuple[str, ...]

    @classmethod
    def default(cls) -> ProhibitedTermsList:
        """Create a ProhibitedTermsList with default prohibited terms.

        Returns:
            ProhibitedTermsList with FR55-specified default terms.
        """
        return cls(terms=DEFAULT_PROHIBITED_TERMS)

    @classmethod
    def from_custom_terms(cls, custom_terms: tuple[str, ...]) -> ProhibitedTermsList:
        """Create a ProhibitedTermsList with custom terms.

        Args:
            custom_terms: Custom tuple of prohibited terms.

        Returns:
            ProhibitedTermsList with provided terms.

        Raises:
            ValueError: If custom_terms is empty.
        """
        if not custom_terms:
            raise ValueError("FR55: Prohibited terms list cannot be empty")
        return cls(terms=custom_terms)

    @property
    def normalized_terms(self) -> tuple[str, ...]:
        """Get NFKC-normalized terms for efficient scanning.

        Returns:
            Tuple of normalized terms for comparison.
        """
        return tuple(normalize_for_scanning(term) for term in self.terms)

    def contains_prohibited_term(self, content: str) -> tuple[bool, tuple[str, ...]]:
        """Check if content contains any prohibited terms.

        Performs case-insensitive matching with NFKC normalization
        to catch Unicode evasion attempts.

        Args:
            content: The content to scan.

        Returns:
            Tuple of (has_violation, matched_terms).
            matched_terms contains the original (non-normalized) terms that matched.
        """
        normalized_content = normalize_for_scanning(content)
        matched: list[str] = []

        for original_term, normalized_term in zip(
            self.terms, self.normalized_terms, strict=True
        ):
            if normalized_term in normalized_content:
                matched.append(original_term)

        return (len(matched) > 0, tuple(matched))

    def __len__(self) -> int:
        """Return the number of prohibited terms."""
        return len(self.terms)

    def __iter__(self):
        """Iterate over prohibited terms."""
        return iter(self.terms)
