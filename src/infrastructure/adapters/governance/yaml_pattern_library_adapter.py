"""YAML Pattern Library Adapter - Loads patterns from YAML configuration.

Story: consent-gov-3.4: Coercion Pattern Detection

This adapter implements the PatternLibraryPort by loading patterns from
a YAML configuration file. The pattern library is:
- Versioned for auditability (AC5)
- Loadable from configuration (AC8)
- Deterministic (same version = same patterns) (AC7)

References:
- AC5: Pattern library versioned and auditable
- AC8: Pattern library loadable from configuration
- AC7: Pattern matching is deterministic
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import yaml

from src.application.ports.governance.pattern_library_port import PatternLibraryPort
from src.domain.governance.filter import TransformationRule
from src.domain.governance.filter.coercion_pattern import (
    CoercionPattern,
    PatternCategory,
    PatternLibraryVersion,
    PatternSeverity,
)


class YamlPatternLibraryAdapter(PatternLibraryPort):
    """Loads coercion patterns from YAML configuration.

    This adapter provides:
    - Pattern loading from YAML file (AC8)
    - Version tracking with hash integrity (AC5)
    - Deterministic pattern ordering (AC7)
    - Category and severity filtering

    Usage:
        adapter = YamlPatternLibraryAdapter(Path("config/coercion_patterns.yaml"))
        await adapter.load()

        version = await adapter.get_current_version()
        blocking = await adapter.get_blocking_patterns()
    """

    def __init__(self, config_path: Path) -> None:
        """Initialize the adapter.

        Args:
            config_path: Path to the YAML configuration file.
        """
        self._config_path = config_path
        self._patterns: list[CoercionPattern] = []
        self._version: Optional[PatternLibraryVersion] = None
        self._loaded = False

    async def load(self) -> None:
        """Load patterns from YAML file.

        This method must be called before using the adapter.
        It parses the YAML file and creates CoercionPattern objects.

        Raises:
            FileNotFoundError: If config file doesn't exist
            ValueError: If YAML is invalid or patterns are malformed
        """
        if not self._config_path.exists():
            raise FileNotFoundError(f"Pattern config not found: {self._config_path}")

        with open(self._config_path) as f:
            config = yaml.safe_load(f)

        if not config:
            raise ValueError("Empty pattern configuration")

        if "version" not in config:
            raise ValueError("Pattern configuration missing 'version' field")

        if "patterns" not in config:
            raise ValueError("Pattern configuration missing 'patterns' field")

        # Parse patterns and validate unique IDs
        self._patterns = []
        seen_ids: set[str] = set()
        for pattern_dict in config["patterns"]:
            try:
                pattern = self._parse_pattern(pattern_dict)
                # Validate unique pattern ID
                if pattern.id in seen_ids:
                    raise ValueError(f"Duplicate pattern ID: {pattern.id}")
                seen_ids.add(pattern.id)
                self._patterns.append(pattern)
            except Exception as e:
                pattern_id = pattern_dict.get("id", "unknown")
                raise ValueError(f"Invalid pattern '{pattern_id}': {e}") from e

        # Sort patterns for deterministic ordering (AC7)
        self._patterns = self._sort_patterns(self._patterns)

        # Calculate version hash from all patterns
        patterns_hash = self._calculate_hash()

        self._version = PatternLibraryVersion(
            version=config["version"],
            patterns_hash=patterns_hash,
            pattern_count=len(self._patterns),
            loaded_at=datetime.now(timezone.utc),
        )

        self._loaded = True

    def _parse_pattern(self, pattern_dict: dict) -> CoercionPattern:
        """Parse a single pattern from dict.

        Args:
            pattern_dict: Dictionary from YAML

        Returns:
            CoercionPattern object
        """
        # Parse category
        category_str = pattern_dict.get("category", "")
        try:
            category = PatternCategory(category_str)
        except ValueError:
            raise ValueError(f"Invalid category: {category_str}")

        # Parse severity
        severity_str = pattern_dict.get("severity", "")
        try:
            severity = PatternSeverity(severity_str)
        except ValueError:
            raise ValueError(f"Invalid severity: {severity_str}")

        return CoercionPattern(
            id=pattern_dict.get("id", ""),
            category=category,
            severity=severity,
            pattern=pattern_dict.get("pattern", ""),
            description=pattern_dict.get("description", ""),
            replacement=pattern_dict.get("replacement"),
            rejection_reason=pattern_dict.get("rejection_reason"),
            violation_type=pattern_dict.get("violation_type"),
            case_sensitive=pattern_dict.get("case_sensitive", False),
        )

    def _sort_patterns(self, patterns: list[CoercionPattern]) -> list[CoercionPattern]:
        """Sort patterns for deterministic ordering.

        Ordering:
        1. Severity (BLOCK > REJECT > TRANSFORM)
        2. Category (alphabetical)
        3. Pattern ID (alphabetical)

        This ensures consistent behavior per AC7.
        """
        severity_order = {
            PatternSeverity.BLOCK: 0,
            PatternSeverity.REJECT: 1,
            PatternSeverity.TRANSFORM: 2,
        }

        return sorted(
            patterns,
            key=lambda p: (severity_order[p.severity], p.category.value, p.id),
        )

    def _calculate_hash(self) -> str:
        """Calculate hash of all patterns for integrity verification.

        Returns:
            SHA-256 hash hex string of all pattern fields.
        """
        # Create deterministic string of all patterns
        pattern_strings = []
        for p in self._patterns:
            # Include ALL significant fields for integrity verification
            pattern_str = (
                f"{p.id}|{p.category.value}|{p.severity.value}|{p.pattern}|"
                f"{p.description}|{p.replacement or ''}|{p.rejection_reason or ''}|"
                f"{p.violation_type or ''}|{p.case_sensitive}"
            )
            pattern_strings.append(pattern_str)

        # Join and hash
        combined = "\n".join(pattern_strings)
        return hashlib.sha256(combined.encode()).hexdigest()

    def _ensure_loaded(self) -> None:
        """Ensure patterns are loaded."""
        if not self._loaded:
            raise RuntimeError("Pattern library not loaded. Call load() first.")

    async def get_current_version(self) -> PatternLibraryVersion:
        """Get current version of the pattern library."""
        self._ensure_loaded()
        assert self._version is not None
        return self._version

    async def get_blocking_patterns(self) -> list[CoercionPattern]:
        """Get patterns that result in BLOCKED."""
        self._ensure_loaded()
        return [p for p in self._patterns if p.severity == PatternSeverity.BLOCK]

    async def get_rejection_patterns(self) -> list[CoercionPattern]:
        """Get patterns that result in REJECTED."""
        self._ensure_loaded()
        return [p for p in self._patterns if p.severity == PatternSeverity.REJECT]

    async def get_transformation_patterns(self) -> list[CoercionPattern]:
        """Get patterns for auto-transformation."""
        self._ensure_loaded()
        return [p for p in self._patterns if p.severity == PatternSeverity.TRANSFORM]

    async def get_transformation_rules(self) -> list[TransformationRule]:
        """Get transformation rules for backward compatibility.

        This method converts CoercionPattern to TransformationRule
        for compatibility with the existing CoercionFilterService.
        """
        self._ensure_loaded()
        transform_patterns = await self.get_transformation_patterns()

        # _ensure_loaded guarantees self._version is set
        assert self._version is not None

        rules = []
        for p in transform_patterns:
            rules.append(
                TransformationRule(
                    rule_id=p.id,
                    pattern=p.pattern,
                    replacement=p.replacement or "",
                    description=p.description,
                    category=p.category.value,
                    version=self._version.version,
                )
            )
        return rules

    async def get_all_patterns(self) -> list[CoercionPattern]:
        """Get all patterns in the library."""
        self._ensure_loaded()
        return list(self._patterns)  # Return copy

    async def get_patterns_by_category(
        self,
        category: PatternCategory,
    ) -> list[CoercionPattern]:
        """Get patterns for a specific category."""
        self._ensure_loaded()
        return [p for p in self._patterns if p.category == category]

    async def get_patterns_by_severity(
        self,
        severity: PatternSeverity,
    ) -> list[CoercionPattern]:
        """Get patterns with a specific severity."""
        self._ensure_loaded()
        return [p for p in self._patterns if p.severity == severity]

    async def get_pattern_by_id(
        self,
        pattern_id: str,
    ) -> Optional[CoercionPattern]:
        """Get a specific pattern by ID."""
        self._ensure_loaded()
        for p in self._patterns:
            if p.id == pattern_id:
                return p
        return None

    @property
    def pattern_count(self) -> int:
        """Get total number of patterns."""
        return len(self._patterns)

    @property
    def is_loaded(self) -> bool:
        """Check if patterns are loaded."""
        return self._loaded
