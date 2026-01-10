"""Unit tests for CsvYamlArchonProfileAdapter."""

import tempfile
from pathlib import Path
from uuid import UUID

import pytest
import yaml

from src.infrastructure.adapters.config.archon_profile_adapter import (
    CsvYamlArchonProfileAdapter,
    create_archon_profile_repository,
)
from src.application.ports.archon_profile_repository import (
    ArchonProfileLoadError,
)


# Sample CSV content for testing
SAMPLE_CSV = '''id,name,aegis_rank,original_rank,rank_level,role,goal,backstory,system_prompt,suggested_tools,allow_delegation,attributes,max_members,max_legions,created_at,updated_at
11111111-1111-1111-1111-111111111111,Paimon,executive_director,King,8,Executive Director - Knowledge,Develop members through teaching,"Paimon is wise.","You are Paimon.","[""knowledge_tool"",""communication_tool""]",true,"{""personality"":""Wise"",""brand_color"":""Gold""}",2000000,200,2025-12-21 17:11:45.851966+00,2025-12-21 17:11:45.851966+00
22222222-2222-2222-2222-222222222222,Belial,executive_director,King,8,Executive Director - Talent,Develop members through power,"Belial is powerful.","You are Belial.","[""communication_tool""]",true,"{""personality"":""Proud"",""brand_color"":""Red""}",800000,80,2025-12-21 17:11:45.851966+00,2025-12-21 17:11:45.851966+00
33333333-3333-3333-3333-333333333333,Eligos,senior_director,Duke,7,Senior Director - Intelligence,Develop members through secrets,"Eligos is wise.","You are Eligos.","[""insight_tool"",""communication_tool""]",true,"{""personality"":""Loyal"",""brand_color"":""Rust""}",600000,60,2025-12-21 17:14:52.044145+00,2025-12-21 17:14:52.044145+00
44444444-4444-4444-4444-444444444444,Raum,strategic_director,Earl,4,Strategic Director - Acquisition,Develop members through stealing,"Raum is cunning.","You are Raum.","[""disruption_tool""]",true,"{""personality"":""Cunning""}",300000,30,2025-12-21 17:17:35.510755+00,2025-12-21 17:17:35.510755+00
'''

# Sample YAML content for testing
SAMPLE_YAML = '''
_default:
  provider: anthropic
  model: claude-3-haiku-20240307
  temperature: 0.5
  max_tokens: 2048
  timeout_ms: 30000

_rank_defaults:
  executive_director:
    provider: anthropic
    model: claude-sonnet-4-20250514
    temperature: 0.7
    max_tokens: 4096
    timeout_ms: 60000
  senior_director:
    provider: anthropic
    model: claude-sonnet-4-20250514
    temperature: 0.6
    max_tokens: 4096
    timeout_ms: 45000

# Explicit override for Paimon
11111111-1111-1111-1111-111111111111:
  provider: anthropic
  model: claude-3-opus-20240229
  temperature: 0.8
  max_tokens: 8192
  timeout_ms: 90000
'''


@pytest.fixture
def temp_files():
    """Create temporary CSV and YAML files for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        csv_path = Path(tmpdir) / "archons.csv"
        yaml_path = Path(tmpdir) / "llm-bindings.yaml"

        csv_path.write_text(SAMPLE_CSV)
        yaml_path.write_text(SAMPLE_YAML)

        yield csv_path, yaml_path


class TestCsvYamlArchonProfileAdapter:
    """Tests for the CSV+YAML adapter."""

    def test_load_profiles_from_files(self, temp_files) -> None:
        """Test loading profiles from CSV and YAML files."""
        csv_path, yaml_path = temp_files
        adapter = CsvYamlArchonProfileAdapter(csv_path, yaml_path)

        assert adapter.count() == 4

    def test_get_by_id(self, temp_files) -> None:
        """Test retrieving profile by UUID."""
        csv_path, yaml_path = temp_files
        adapter = CsvYamlArchonProfileAdapter(csv_path, yaml_path)

        paimon_id = UUID("11111111-1111-1111-1111-111111111111")
        profile = adapter.get_by_id(paimon_id)

        assert profile is not None
        assert profile.name == "Paimon"
        assert profile.aegis_rank == "executive_director"

    def test_get_by_id_not_found(self, temp_files) -> None:
        """Test get_by_id returns None for unknown ID."""
        csv_path, yaml_path = temp_files
        adapter = CsvYamlArchonProfileAdapter(csv_path, yaml_path)

        unknown_id = UUID("99999999-9999-9999-9999-999999999999")
        profile = adapter.get_by_id(unknown_id)

        assert profile is None

    def test_get_by_name(self, temp_files) -> None:
        """Test retrieving profile by name."""
        csv_path, yaml_path = temp_files
        adapter = CsvYamlArchonProfileAdapter(csv_path, yaml_path)

        profile = adapter.get_by_name("Belial")

        assert profile is not None
        assert profile.name == "Belial"

    def test_get_by_name_case_insensitive(self, temp_files) -> None:
        """Test name lookup is case-insensitive."""
        csv_path, yaml_path = temp_files
        adapter = CsvYamlArchonProfileAdapter(csv_path, yaml_path)

        profile = adapter.get_by_name("PAIMON")

        assert profile is not None
        assert profile.name == "Paimon"

    def test_get_by_name_not_found(self, temp_files) -> None:
        """Test get_by_name returns None for unknown name."""
        csv_path, yaml_path = temp_files
        adapter = CsvYamlArchonProfileAdapter(csv_path, yaml_path)

        profile = adapter.get_by_name("UnknownArchon")

        assert profile is None

    def test_get_all_sorted(self, temp_files) -> None:
        """Test get_all returns profiles sorted by rank then name."""
        csv_path, yaml_path = temp_files
        adapter = CsvYamlArchonProfileAdapter(csv_path, yaml_path)

        profiles = adapter.get_all()

        assert len(profiles) == 4
        # Executives first (rank 8), then senior (rank 7), then strategic (rank 4)
        assert profiles[0].rank_level == 8
        assert profiles[1].rank_level == 8
        assert profiles[2].rank_level == 7
        assert profiles[3].rank_level == 4

    def test_get_by_rank(self, temp_files) -> None:
        """Test filtering profiles by rank."""
        csv_path, yaml_path = temp_files
        adapter = CsvYamlArchonProfileAdapter(csv_path, yaml_path)

        executives = adapter.get_by_rank("executive_director")

        assert len(executives) == 2
        assert all(p.aegis_rank == "executive_director" for p in executives)

    def test_get_by_tool(self, temp_files) -> None:
        """Test filtering profiles by tool."""
        csv_path, yaml_path = temp_files
        adapter = CsvYamlArchonProfileAdapter(csv_path, yaml_path)

        with_insight = adapter.get_by_tool("insight_tool")

        assert len(with_insight) == 1
        assert with_insight[0].name == "Eligos"

    def test_get_executives(self, temp_files) -> None:
        """Test retrieving executive directors."""
        csv_path, yaml_path = temp_files
        adapter = CsvYamlArchonProfileAdapter(csv_path, yaml_path)

        executives = adapter.get_executives()

        assert len(executives) == 2
        assert all(p.aegis_rank == "executive_director" for p in executives)

    def test_exists(self, temp_files) -> None:
        """Test checking if archon exists."""
        csv_path, yaml_path = temp_files
        adapter = CsvYamlArchonProfileAdapter(csv_path, yaml_path)

        paimon_id = UUID("11111111-1111-1111-1111-111111111111")
        unknown_id = UUID("99999999-9999-9999-9999-999999999999")

        assert adapter.exists(paimon_id) is True
        assert adapter.exists(unknown_id) is False


class TestLLMConfigResolution:
    """Tests for LLM configuration resolution priority."""

    def test_explicit_archon_config_takes_priority(self, temp_files) -> None:
        """Test that explicit archon config overrides rank defaults."""
        csv_path, yaml_path = temp_files
        adapter = CsvYamlArchonProfileAdapter(csv_path, yaml_path)

        # Paimon has explicit config in YAML
        paimon_id = UUID("11111111-1111-1111-1111-111111111111")
        profile = adapter.get_by_id(paimon_id)

        assert profile is not None
        assert profile.llm_config.model == "claude-3-opus-20240229"
        assert profile.llm_config.temperature == 0.8
        assert profile.llm_config.max_tokens == 8192

    def test_rank_default_used_when_no_explicit(self, temp_files) -> None:
        """Test that rank defaults are used when no explicit config."""
        csv_path, yaml_path = temp_files
        adapter = CsvYamlArchonProfileAdapter(csv_path, yaml_path)

        # Belial is executive_director but no explicit config
        belial_id = UUID("22222222-2222-2222-2222-222222222222")
        profile = adapter.get_by_id(belial_id)

        assert profile is not None
        # Should use executive_director rank default
        assert profile.llm_config.model == "claude-sonnet-4-20250514"
        assert profile.llm_config.temperature == 0.7

    def test_global_default_used_for_unknown_rank(self, temp_files) -> None:
        """Test that global default is used for ranks not in rank_defaults."""
        csv_path, yaml_path = temp_files
        adapter = CsvYamlArchonProfileAdapter(csv_path, yaml_path)

        # Raum is strategic_director - no rank default in our test YAML
        raum_id = UUID("44444444-4444-4444-4444-444444444444")
        profile = adapter.get_by_id(raum_id)

        assert profile is not None
        # Should use global _default
        assert profile.llm_config.model == "claude-3-haiku-20240307"
        assert profile.llm_config.temperature == 0.5

    def test_get_by_provider(self, temp_files) -> None:
        """Test filtering profiles by LLM provider."""
        csv_path, yaml_path = temp_files
        adapter = CsvYamlArchonProfileAdapter(csv_path, yaml_path)

        anthropic_profiles = adapter.get_by_provider("anthropic")

        assert len(anthropic_profiles) == 4  # All use Anthropic in test data


class TestErrorHandling:
    """Tests for error handling."""

    def test_csv_not_found(self) -> None:
        """Test error when CSV file doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yaml_path = Path(tmpdir) / "llm-bindings.yaml"
            yaml_path.write_text(SAMPLE_YAML)

            with pytest.raises(ArchonProfileLoadError, match="File not found"):
                CsvYamlArchonProfileAdapter(
                    Path(tmpdir) / "nonexistent.csv",
                    yaml_path,
                )

    def test_yaml_not_found_uses_defaults(self) -> None:
        """Test that missing YAML file uses default config."""
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "archons.csv"
            csv_path.write_text(SAMPLE_CSV)

            # No YAML file - should use defaults
            adapter = CsvYamlArchonProfileAdapter(
                csv_path,
                Path(tmpdir) / "nonexistent.yaml",
            )

            profile = adapter.get_by_name("Paimon")
            assert profile is not None
            # Should use hardcoded DEFAULT_LLM_CONFIG
            assert profile.llm_config.model == "claude-3-haiku-20240307"


class TestAttributeParsing:
    """Tests for CSV attribute parsing."""

    def test_parse_personality_from_attributes(self, temp_files) -> None:
        """Test personality is extracted from attributes JSON."""
        csv_path, yaml_path = temp_files
        adapter = CsvYamlArchonProfileAdapter(csv_path, yaml_path)

        profile = adapter.get_by_name("Paimon")

        assert profile is not None
        assert profile.personality == "Wise"

    def test_parse_brand_color_from_attributes(self, temp_files) -> None:
        """Test brand_color is extracted from attributes JSON."""
        csv_path, yaml_path = temp_files
        adapter = CsvYamlArchonProfileAdapter(csv_path, yaml_path)

        profile = adapter.get_by_name("Paimon")

        assert profile is not None
        assert profile.brand_color == "Gold"

    def test_parse_tools_list(self, temp_files) -> None:
        """Test suggested_tools is parsed as list."""
        csv_path, yaml_path = temp_files
        adapter = CsvYamlArchonProfileAdapter(csv_path, yaml_path)

        profile = adapter.get_by_name("Paimon")

        assert profile is not None
        assert profile.suggested_tools == ["knowledge_tool", "communication_tool"]


class TestIntegrationWithRealData:
    """Integration tests using actual archons-base.csv if available."""

    @pytest.mark.skipif(
        not Path("docs/archons-base.csv").exists(),
        reason="archons-base.csv not found",
    )
    def test_load_real_archons_csv(self) -> None:
        """Test loading the real archons CSV file."""
        csv_path = Path("docs/archons-base.csv")
        yaml_path = Path("config/archon-llm-bindings.yaml")

        adapter = CsvYamlArchonProfileAdapter(csv_path, yaml_path)

        # Should have all 72 archons
        assert adapter.count() == 72

        # Check a known archon
        paimon = adapter.get_by_name("Paimon")
        assert paimon is not None
        assert paimon.aegis_rank == "executive_director"

    @pytest.mark.skipif(
        not Path("docs/archons-base.csv").exists(),
        reason="archons-base.csv not found",
    )
    def test_factory_function(self) -> None:
        """Test the factory function with real data."""
        repo = create_archon_profile_repository()

        assert repo.count() == 72
