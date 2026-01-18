"""PatternLibraryPort - Interface for coercion pattern library.

Story: consent-gov-3.4: Coercion Pattern Detection

This port defines the contract for accessing the coercion pattern library.
The pattern library provides versioned, auditable patterns for:
- Blocking patterns (hard violations - BLOCK)
- Rejection patterns (correctable issues - REJECT)
- Transformation rules (auto-fix - TRANSFORM)

Constitutional Guarantees:
- Pattern library is versioned for auditability (AC5)
- Patterns are categorized by severity (AC6)
- Pattern matching is deterministic (AC7)
- Pattern library loadable from configuration (AC8)

References:
- AC5: Pattern library versioned and auditable
- AC6: Patterns categorized by severity
- AC8: Pattern library loadable from configuration
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.governance.filter import TransformationRule
from src.domain.governance.filter.coercion_pattern import (
    CoercionPattern,
    PatternCategory,
    PatternLibraryVersion,
    PatternSeverity,
)


class PatternLibraryPort(ABC):
    """Port for pattern library operations.

    The pattern library provides the rules for filtering:
    - Blocking patterns (hard violations)
    - Rejection patterns (correctable issues)
    - Transformation rules (softening)

    All patterns are versioned for auditability per AC5.

    Constitutional Guarantee:
    - Same pattern library version always returns same patterns
    - Pattern library changes are versioned and logged

    Usage:
        # Get current version
        version = await pattern_library.get_current_version()

        # Get patterns by severity
        blocking = await pattern_library.get_blocking_patterns()
        rejections = await pattern_library.get_rejection_patterns()
        transforms = await pattern_library.get_transformation_patterns()

        # Get all patterns
        all_patterns = await pattern_library.get_all_patterns()
    """

    @abstractmethod
    async def get_current_version(self) -> PatternLibraryVersion:
        """Get current version of the pattern library.

        Returns:
            PatternLibraryVersion with version string, hash, and count.

        Note:
            Version follows semver format (X.Y.Z).
            Hash is calculated from all patterns for integrity verification.
        """
        ...

    @abstractmethod
    async def get_blocking_patterns(self) -> list[CoercionPattern]:
        """Get patterns that result in BLOCKED.

        Returns:
            List of CoercionPattern with severity=BLOCK.

        These are hard violations that cannot be transformed.
        Content matching these patterns MUST NOT be sent.
        """
        ...

    @abstractmethod
    async def get_rejection_patterns(self) -> list[CoercionPattern]:
        """Get patterns that result in REJECTED.

        Returns:
            List of CoercionPattern with severity=REJECT.

        These are correctable issues requiring rewrite.
        Earl must revise content before it can be sent.
        """
        ...

    @abstractmethod
    async def get_transformation_patterns(self) -> list[CoercionPattern]:
        """Get patterns for auto-transformation.

        Returns:
            List of CoercionPattern with severity=TRANSFORM.

        These patterns can be automatically fixed.
        Content is sent after transformation is applied.
        """
        ...

    @abstractmethod
    async def get_transformation_rules(self) -> list[TransformationRule]:
        """Get transformation rules for softening content.

        Returns:
            List of TransformationRule objects for compatibility
            with existing CoercionFilterService.

        Note:
            This method provides backward compatibility with the
            existing filter service. For new code, prefer
            get_transformation_patterns() which returns CoercionPattern.
        """
        ...

    @abstractmethod
    async def get_all_patterns(self) -> list[CoercionPattern]:
        """Get all patterns in the library.

        Returns:
            List of all CoercionPattern objects, sorted by:
            1. Severity (BLOCK first, then REJECT, then TRANSFORM)
            2. Category
            3. Pattern ID

        This deterministic ordering ensures consistent behavior per AC7.
        """
        ...

    @abstractmethod
    async def get_patterns_by_category(
        self,
        category: PatternCategory,
    ) -> list[CoercionPattern]:
        """Get patterns for a specific category.

        Args:
            category: The pattern category to filter by

        Returns:
            List of patterns in that category.
        """
        ...

    @abstractmethod
    async def get_patterns_by_severity(
        self,
        severity: PatternSeverity,
    ) -> list[CoercionPattern]:
        """Get patterns with a specific severity.

        Args:
            severity: The pattern severity to filter by

        Returns:
            List of patterns with that severity.
        """
        ...

    @abstractmethod
    async def get_pattern_by_id(
        self,
        pattern_id: str,
    ) -> CoercionPattern | None:
        """Get a specific pattern by ID.

        Args:
            pattern_id: The unique pattern ID

        Returns:
            The pattern if found, None otherwise.
        """
        ...

    async def match_content(
        self,
        content: str,
    ) -> list[CoercionPattern]:
        """Find all patterns matching content.

        Args:
            content: Content to check

        Returns:
            List of patterns that match, sorted by severity (BLOCK first).

        Note:
            This is a convenience method with a default implementation.
            Subclasses may override for performance optimization.
        """
        all_patterns = await self.get_all_patterns()
        matches = [p for p in all_patterns if p.matches(content)]
        # Sort by severity priority (BLOCK > REJECT > TRANSFORM)
        severity_order = {
            PatternSeverity.BLOCK: 0,
            PatternSeverity.REJECT: 1,
            PatternSeverity.TRANSFORM: 2,
        }
        return sorted(matches, key=lambda p: severity_order[p.severity])

    async def get_highest_severity_match(
        self,
        content: str,
    ) -> CoercionPattern | None:
        """Get the highest severity pattern matching content.

        Args:
            content: Content to check

        Returns:
            The highest severity matching pattern, or None if no match.

        Note:
            This is a convenience method for quick severity determination.
        """
        matches = await self.match_content(content)
        return matches[0] if matches else None
