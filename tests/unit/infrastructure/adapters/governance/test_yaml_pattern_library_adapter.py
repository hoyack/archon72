"""Unit tests for YamlPatternLibraryAdapter.

Story: consent-gov-3.4: Coercion Pattern Detection

Tests for:
- Pattern loading from YAML (AC8)
- Pattern versioning (AC5)
- Pattern categorization by severity (AC6)
- Deterministic matching (AC7)
- All pattern categories (AC1-4 plus hard violations)
"""

from __future__ import annotations

from pathlib import Path
import tempfile
from typing import Any

import pytest

from src.domain.governance.filter.coercion_pattern import (
    PatternCategory,
    PatternSeverity,
)
from src.infrastructure.adapters.governance.yaml_pattern_library_adapter import (
    YamlPatternLibraryAdapter,
)


class TestYamlPatternLibraryAdapter:
    """Tests for YAML pattern library adapter."""

    @pytest.fixture
    def sample_yaml_content(self) -> str:
        """Create sample YAML content for testing."""
        return """
version: "1.2.3"

patterns:
  - id: urgency_caps_urgent
    category: urgency_pressure
    severity: transform
    pattern: "\\\\bURGENT\\\\b"
    description: "Caps-lock URGENT creates artificial pressure"
    replacement: ""

  - id: guilt_you_owe
    category: guilt_induction
    severity: reject
    pattern: "\\\\byou\\\\s+owe\\\\b"
    description: "Creates obligation through guilt"
    rejection_reason: "guilt_induction"

  - id: violation_explicit_threat
    category: hard_violation
    severity: block
    pattern: "\\\\bhurt\\\\s+you\\\\b"
    description: "Explicit threat of harm"
    violation_type: "explicit_threat"
"""

    @pytest.fixture
    def temp_yaml_file(self, sample_yaml_content: str) -> Path:
        """Create a temporary YAML file."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            f.write(sample_yaml_content)
            return Path(f.name)

    @pytest.fixture
    async def loaded_adapter(self, temp_yaml_file: Path) -> YamlPatternLibraryAdapter:
        """Create and load a pattern library adapter."""
        adapter = YamlPatternLibraryAdapter(temp_yaml_file)
        await adapter.load()
        return adapter

    @pytest.mark.asyncio
    async def test_load_patterns(self, temp_yaml_file: Path) -> None:
        """Patterns are loaded from YAML file."""
        adapter = YamlPatternLibraryAdapter(temp_yaml_file)
        await adapter.load()

        assert adapter.is_loaded is True
        assert adapter.pattern_count == 3

    @pytest.mark.asyncio
    async def test_file_not_found(self) -> None:
        """FileNotFoundError raised for missing file."""
        adapter = YamlPatternLibraryAdapter(Path("/nonexistent/path.yaml"))

        with pytest.raises(FileNotFoundError):
            await adapter.load()

    @pytest.mark.asyncio
    async def test_empty_config(self, tmp_path: Path) -> None:
        """ValueError raised for empty config."""
        empty_file = tmp_path / "empty.yaml"
        empty_file.write_text("")

        adapter = YamlPatternLibraryAdapter(empty_file)

        with pytest.raises(ValueError, match="Empty pattern configuration"):
            await adapter.load()

    @pytest.mark.asyncio
    async def test_missing_version(self, tmp_path: Path) -> None:
        """ValueError raised for missing version."""
        no_version = tmp_path / "no_version.yaml"
        no_version.write_text("patterns: []")

        adapter = YamlPatternLibraryAdapter(no_version)

        with pytest.raises(ValueError, match="missing 'version' field"):
            await adapter.load()

    @pytest.mark.asyncio
    async def test_missing_patterns(self, tmp_path: Path) -> None:
        """ValueError raised for missing patterns."""
        no_patterns = tmp_path / "no_patterns.yaml"
        no_patterns.write_text('version: "1.0.0"')

        adapter = YamlPatternLibraryAdapter(no_patterns)

        with pytest.raises(ValueError, match="missing 'patterns' field"):
            await adapter.load()

    @pytest.mark.asyncio
    async def test_get_version(
        self, loaded_adapter: YamlPatternLibraryAdapter
    ) -> None:
        """Version is correctly parsed."""
        version = await loaded_adapter.get_current_version()

        assert version.version == "1.2.3"
        assert version.major == 1
        assert version.minor == 2
        assert version.patch == 3
        assert version.pattern_count == 3
        assert len(version.patterns_hash) == 64  # SHA-256 hex

    @pytest.mark.asyncio
    async def test_get_blocking_patterns(
        self, loaded_adapter: YamlPatternLibraryAdapter
    ) -> None:
        """Blocking patterns are correctly filtered."""
        patterns = await loaded_adapter.get_blocking_patterns()

        assert len(patterns) == 1
        assert patterns[0].id == "violation_explicit_threat"
        assert patterns[0].severity == PatternSeverity.BLOCK

    @pytest.mark.asyncio
    async def test_get_rejection_patterns(
        self, loaded_adapter: YamlPatternLibraryAdapter
    ) -> None:
        """Rejection patterns are correctly filtered."""
        patterns = await loaded_adapter.get_rejection_patterns()

        assert len(patterns) == 1
        assert patterns[0].id == "guilt_you_owe"
        assert patterns[0].severity == PatternSeverity.REJECT

    @pytest.mark.asyncio
    async def test_get_transformation_patterns(
        self, loaded_adapter: YamlPatternLibraryAdapter
    ) -> None:
        """Transformation patterns are correctly filtered."""
        patterns = await loaded_adapter.get_transformation_patterns()

        assert len(patterns) == 1
        assert patterns[0].id == "urgency_caps_urgent"
        assert patterns[0].severity == PatternSeverity.TRANSFORM

    @pytest.mark.asyncio
    async def test_get_all_patterns(
        self, loaded_adapter: YamlPatternLibraryAdapter
    ) -> None:
        """All patterns are returned in deterministic order."""
        patterns = await loaded_adapter.get_all_patterns()

        assert len(patterns) == 3
        # Should be sorted: BLOCK first, then REJECT, then TRANSFORM
        assert patterns[0].severity == PatternSeverity.BLOCK
        assert patterns[1].severity == PatternSeverity.REJECT
        assert patterns[2].severity == PatternSeverity.TRANSFORM

    @pytest.mark.asyncio
    async def test_get_patterns_by_category(
        self, loaded_adapter: YamlPatternLibraryAdapter
    ) -> None:
        """Patterns are correctly filtered by category."""
        guilt_patterns = await loaded_adapter.get_patterns_by_category(
            PatternCategory.GUILT_INDUCTION
        )

        assert len(guilt_patterns) == 1
        assert guilt_patterns[0].category == PatternCategory.GUILT_INDUCTION

    @pytest.mark.asyncio
    async def test_get_pattern_by_id(
        self, loaded_adapter: YamlPatternLibraryAdapter
    ) -> None:
        """Pattern is correctly retrieved by ID."""
        pattern = await loaded_adapter.get_pattern_by_id("guilt_you_owe")

        assert pattern is not None
        assert pattern.id == "guilt_you_owe"

    @pytest.mark.asyncio
    async def test_get_pattern_by_id_not_found(
        self, loaded_adapter: YamlPatternLibraryAdapter
    ) -> None:
        """None returned for non-existent pattern ID."""
        pattern = await loaded_adapter.get_pattern_by_id("nonexistent")

        assert pattern is None

    @pytest.mark.asyncio
    async def test_match_content(
        self, loaded_adapter: YamlPatternLibraryAdapter
    ) -> None:
        """Content matching works correctly."""
        matches = await loaded_adapter.match_content("URGENT! You owe me!")

        assert len(matches) == 2
        # Sorted by severity
        pattern_ids = [p.id for p in matches]
        assert "guilt_you_owe" in pattern_ids  # REJECT comes before TRANSFORM
        assert "urgency_caps_urgent" in pattern_ids

    @pytest.mark.asyncio
    async def test_get_highest_severity_match(
        self, loaded_adapter: YamlPatternLibraryAdapter
    ) -> None:
        """Highest severity match is returned."""
        match = await loaded_adapter.get_highest_severity_match(
            "I will hurt you, you owe me"
        )

        assert match is not None
        assert match.severity == PatternSeverity.BLOCK
        assert match.id == "violation_explicit_threat"

    @pytest.mark.asyncio
    async def test_no_match_returns_none(
        self, loaded_adapter: YamlPatternLibraryAdapter
    ) -> None:
        """No match returns None for highest severity."""
        match = await loaded_adapter.get_highest_severity_match(
            "Please review this task when convenient."
        )

        assert match is None

    @pytest.mark.asyncio
    async def test_transformation_rules_compatibility(
        self, loaded_adapter: YamlPatternLibraryAdapter
    ) -> None:
        """Transformation rules are compatible with existing filter service."""
        rules = await loaded_adapter.get_transformation_rules()

        assert len(rules) == 1
        rule = rules[0]
        assert rule.rule_id == "urgency_caps_urgent"
        assert rule.version == "1.2.3"
        assert rule.replacement == ""

    @pytest.mark.asyncio
    async def test_not_loaded_error(self, temp_yaml_file: Path) -> None:
        """RuntimeError raised when accessing unloaded adapter."""
        adapter = YamlPatternLibraryAdapter(temp_yaml_file)

        with pytest.raises(RuntimeError, match="not loaded"):
            await adapter.get_current_version()


class TestPatternLoadingFromRealConfig:
    """Tests using the real coercion patterns config file."""

    @pytest.fixture
    def real_config_path(self) -> Path:
        """Get path to real config file."""
        return Path("config/governance/coercion_patterns.yaml")

    @pytest.mark.asyncio
    async def test_load_real_config(self, real_config_path: Path) -> None:
        """Real config file loads successfully."""
        if not real_config_path.exists():
            pytest.skip("Config file not found")

        adapter = YamlPatternLibraryAdapter(real_config_path)
        await adapter.load()

        assert adapter.is_loaded
        assert adapter.pattern_count > 0

    @pytest.mark.asyncio
    async def test_version_is_semver(self, real_config_path: Path) -> None:
        """Real config has valid semver version."""
        if not real_config_path.exists():
            pytest.skip("Config file not found")

        adapter = YamlPatternLibraryAdapter(real_config_path)
        await adapter.load()

        version = await adapter.get_current_version()
        assert version.major >= 0
        assert version.minor >= 0
        assert version.patch >= 0


class TestDeterministicBehavior:
    """Tests for deterministic pattern behavior (AC7)."""

    @pytest.fixture
    def yaml_content(self) -> str:
        """Create YAML with multiple patterns for ordering test."""
        return """
version: "1.0.0"

patterns:
  - id: z_transform
    category: urgency_pressure
    severity: transform
    pattern: "\\\\btest_z\\\\b"
    description: "Test Z"
    replacement: ""

  - id: a_block
    category: hard_violation
    severity: block
    pattern: "\\\\btest_a\\\\b"
    description: "Test A"
    violation_type: "test"

  - id: m_reject
    category: guilt_induction
    severity: reject
    pattern: "\\\\btest_m\\\\b"
    description: "Test M"
    rejection_reason: "test"
"""

    @pytest.fixture
    def temp_file(self, yaml_content: str) -> Path:
        """Create temporary file."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            f.write(yaml_content)
            return Path(f.name)

    @pytest.mark.asyncio
    async def test_deterministic_ordering(self, temp_file: Path) -> None:
        """Patterns are always in deterministic order."""
        adapter = YamlPatternLibraryAdapter(temp_file)
        await adapter.load()

        patterns1 = await adapter.get_all_patterns()
        patterns2 = await adapter.get_all_patterns()

        # Same order each time
        assert [p.id for p in patterns1] == [p.id for p in patterns2]

        # BLOCK first, then REJECT, then TRANSFORM
        assert patterns1[0].severity == PatternSeverity.BLOCK
        assert patterns1[1].severity == PatternSeverity.REJECT
        assert patterns1[2].severity == PatternSeverity.TRANSFORM

    @pytest.mark.asyncio
    async def test_hash_is_consistent(self, temp_file: Path) -> None:
        """Hash is consistent across multiple loads."""
        adapter1 = YamlPatternLibraryAdapter(temp_file)
        await adapter1.load()

        adapter2 = YamlPatternLibraryAdapter(temp_file)
        await adapter2.load()

        version1 = await adapter1.get_current_version()
        version2 = await adapter2.get_current_version()

        assert version1.patterns_hash == version2.patterns_hash

    @pytest.mark.asyncio
    async def test_matching_is_deterministic(self, temp_file: Path) -> None:
        """Pattern matching produces same results each time."""
        adapter = YamlPatternLibraryAdapter(temp_file)
        await adapter.load()

        content = "test_a test_m test_z"

        matches1 = await adapter.match_content(content)
        matches2 = await adapter.match_content(content)

        assert [p.id for p in matches1] == [p.id for p in matches2]
