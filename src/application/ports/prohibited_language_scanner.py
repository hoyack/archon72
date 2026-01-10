"""Prohibited language scanner port interface (Story 9.1, FR55).

Defines the protocol for scanning content for prohibited language.
This enables dependency inversion for the blocking service.

Constitutional Constraints:
- FR55: System outputs never claim emergence, consciousness, etc.
- CT-11: Silent failure destroys legitimacy -> fail loud on scan errors
- CT-12: All blocking events must be witnessed
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ScanResult:
    """Result of scanning content for prohibited language (FR55).

    This immutable result object contains information about any
    prohibited terms found during a content scan.

    Attributes:
        violations_found: True if any prohibited terms were detected.
        matched_terms: Tuple of prohibited terms that were matched.
        detection_method: How the detection was performed (e.g., "nfkc_scan").
    """

    violations_found: bool
    matched_terms: tuple[str, ...]
    detection_method: str

    @classmethod
    def no_violations(cls, detection_method: str = "nfkc_scan") -> ScanResult:
        """Create a clean scan result with no violations.

        Args:
            detection_method: Detection method used.

        Returns:
            ScanResult indicating no violations.
        """
        return cls(
            violations_found=False,
            matched_terms=(),
            detection_method=detection_method,
        )

    @classmethod
    def with_violations(
        cls,
        matched_terms: tuple[str, ...],
        detection_method: str = "nfkc_scan",
    ) -> ScanResult:
        """Create a scan result with violations.

        Args:
            matched_terms: Prohibited terms that were detected.
            detection_method: Detection method used.

        Returns:
            ScanResult indicating violations.

        Raises:
            ValueError: If matched_terms is empty.
        """
        if not matched_terms:
            raise ValueError("FR55: matched_terms cannot be empty for violations")
        return cls(
            violations_found=True,
            matched_terms=matched_terms,
            detection_method=detection_method,
        )

    @property
    def terms_count(self) -> int:
        """Get the number of matched terms."""
        return len(self.matched_terms)


class ProhibitedLanguageScannerProtocol(Protocol):
    """Protocol for prohibited language scanning (FR55).

    This port enables dependency inversion for scanning logic.
    Implementations are responsible for:
    - Maintaining the prohibited terms list
    - Applying NFKC normalization for Unicode evasion defense
    - Performing case-insensitive matching
    - Returning structured scan results

    Constitutional Constraints:
    - FR55: System outputs never claim emergence, consciousness, etc.
    - AC1: Prohibited language list is configurable but immutable at runtime
    - AC3: Scanning includes exact matches, synonyms, NFKC normalization

    Methods:
        scan_content: Scan content for prohibited language.
        get_prohibited_terms: Get current list of prohibited terms.
    """

    async def scan_content(self, content: str) -> ScanResult:
        """Scan content for prohibited language (FR55, AC2, AC3).

        Performs case-insensitive matching with NFKC normalization
        to detect prohibited terms including Unicode evasion attempts.

        Args:
            content: Text content to scan.

        Returns:
            ScanResult with violations_found and matched_terms.

        Note:
            This method does not raise on violations - it returns a result.
            The calling service is responsible for handling violations
            (creating events, raising errors, etc.).
        """
        ...

    async def get_prohibited_terms(self) -> tuple[str, ...]:
        """Get the current list of prohibited terms (FR55, AC1).

        Returns:
            Tuple of prohibited terms (case-insensitive matching applies).

        Note:
            Per AC1, this list is configurable at initialization but
            immutable at runtime. The list should be reviewed quarterly.
        """
        ...
