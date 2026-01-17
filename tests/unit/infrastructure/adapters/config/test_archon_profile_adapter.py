"""Unit tests for JsonYamlArchonProfileAdapter."""

import json
import tempfile
from pathlib import Path
from uuid import UUID

import pytest

from src.infrastructure.adapters.config.archon_profile_adapter import (
    JsonYamlArchonProfileAdapter,
    CsvYamlArchonProfileAdapter,  # Backwards compatibility alias
    create_archon_profile_repository,
)
from src.application.ports.archon_profile_repository import (
    ArchonProfileLoadError,
)


# Sample JSON content for testing
SAMPLE_JSON = {
    "archons": [
        {
            "id": "11111111-1111-1111-1111-111111111111",
            "name": "Paimon",
            "aegis_rank": "executive_director",
            "original_rank": "King",
            "rank_level": 8,
            "branch": "legislative",
            "role": "Executive Director - Knowledge",
            "goal": "Develop members through teaching",
            "backstory": "Paimon is wise.",
            "system_prompt": "You are Paimon.",
            "suggested_tools": ["knowledge_tool", "communication_tool"],
            "allow_delegation": True,
            "attributes": {"personality": "Wise", "brand_color": "Gold"},
            "max_members": 2000000,
            "max_legions": 200,
            "created_at": "2025-12-21T17:11:45.851966",
            "updated_at": "2025-12-21T17:11:45.851966",
        },
        {
            "id": "22222222-2222-2222-2222-222222222222",
            "name": "Belial",
            "aegis_rank": "executive_director",
            "original_rank": "King",
            "rank_level": 8,
            "branch": "legislative",
            "role": "Executive Director - Talent",
            "goal": "Develop members through power",
            "backstory": "Belial is powerful.",
            "system_prompt": "You are Belial.",
            "suggested_tools": ["communication_tool"],
            "allow_delegation": True,
            "attributes": {"personality": "Proud", "brand_color": "Red"},
            "max_members": 800000,
            "max_legions": 80,
            "created_at": "2025-12-21T17:11:45.851966",
            "updated_at": "2025-12-21T17:11:45.851966",
        },
        {
            "id": "33333333-3333-3333-3333-333333333333",
            "name": "Eligos",
            "aegis_rank": "senior_director",
            "original_rank": "Duke",
            "rank_level": 7,
            "branch": "administrative",
            "role": "Senior Director - Intelligence",
            "goal": "Develop members through secrets",
            "backstory": "Eligos is wise.",
            "system_prompt": "You are Eligos.",
            "suggested_tools": ["insight_tool", "communication_tool"],
            "allow_delegation": True,
            "attributes": {"personality": "Loyal", "brand_color": "Rust"},
            "max_members": 600000,
            "max_legions": 60,
            "created_at": "2025-12-21T17:14:52.044145",
            "updated_at": "2025-12-21T17:14:52.044145",
        },
        {
            "id": "44444444-4444-4444-4444-444444444444",
            "name": "Raum",
            "aegis_rank": "strategic_director",
            "original_rank": "Earl",
            "rank_level": 4,
            "branch": "administrative",
            "role": "Strategic Director - Acquisition",
            "goal": "Develop members through stealing",
            "backstory": "Raum is cunning.",
            "system_prompt": "You are Raum.",
            "suggested_tools": ["disruption_tool"],
            "allow_delegation": True,
            "attributes": {"personality": "Cunning"},
            "max_members": 300000,
            "max_legions": 30,
            "created_at": "2025-12-21T17:17:35.510755",
            "updated_at": "2025-12-21T17:17:35.510755",
        },
        {
            "id": "55555555-5555-5555-5555-555555555555",
            "name": "Furcas",
            "aegis_rank": "strategic_director",
            "original_rank": "Knight",
            "rank_level": 4,
            "branch": "witness",
            "role": "Knight-Witness - Observer",
            "goal": "Observe and record all proceedings",
            "backstory": "Furcas is the eternal witness.",
            "system_prompt": "You are Furcas, the Knight-Witness.",
            "suggested_tools": ["witness_tool"],
            "allow_delegation": False,
            "attributes": {"personality": "Observant"},
            "max_members": 200000,
            "max_legions": 20,
            "created_at": "2025-12-21T17:17:35.510755",
            "updated_at": "2025-12-21T17:17:35.510755",
        },
    ]
}

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
    """Create temporary JSON and YAML files for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        json_path = Path(tmpdir) / "archons.json"
        yaml_path = Path(tmpdir) / "llm-bindings.yaml"

        json_path.write_text(json.dumps(SAMPLE_JSON))
        yaml_path.write_text(SAMPLE_YAML)

        yield json_path, yaml_path


class TestJsonYamlArchonProfileAdapter:
    """Tests for the JSON+YAML adapter."""

    def test_load_profiles_from_files(self, temp_files) -> None:
        """Test loading profiles from JSON and YAML files."""
        json_path, yaml_path = temp_files
        adapter = JsonYamlArchonProfileAdapter(json_path, yaml_path)

        assert adapter.count() == 5

    def test_get_by_id(self, temp_files) -> None:
        """Test retrieving profile by UUID."""
        json_path, yaml_path = temp_files
        adapter = JsonYamlArchonProfileAdapter(json_path, yaml_path)

        paimon_id = UUID("11111111-1111-1111-1111-111111111111")
        profile = adapter.get_by_id(paimon_id)

        assert profile is not None
        assert profile.name == "Paimon"
        assert profile.aegis_rank == "executive_director"

    def test_get_by_id_not_found(self, temp_files) -> None:
        """Test get_by_id returns None for unknown ID."""
        json_path, yaml_path = temp_files
        adapter = JsonYamlArchonProfileAdapter(json_path, yaml_path)

        unknown_id = UUID("99999999-9999-9999-9999-999999999999")
        profile = adapter.get_by_id(unknown_id)

        assert profile is None

    def test_get_by_name(self, temp_files) -> None:
        """Test retrieving profile by name."""
        json_path, yaml_path = temp_files
        adapter = JsonYamlArchonProfileAdapter(json_path, yaml_path)

        profile = adapter.get_by_name("Belial")

        assert profile is not None
        assert profile.name == "Belial"

    def test_get_by_name_case_insensitive(self, temp_files) -> None:
        """Test name lookup is case-insensitive."""
        json_path, yaml_path = temp_files
        adapter = JsonYamlArchonProfileAdapter(json_path, yaml_path)

        profile = adapter.get_by_name("PAIMON")

        assert profile is not None
        assert profile.name == "Paimon"

    def test_get_by_name_not_found(self, temp_files) -> None:
        """Test get_by_name returns None for unknown name."""
        json_path, yaml_path = temp_files
        adapter = JsonYamlArchonProfileAdapter(json_path, yaml_path)

        profile = adapter.get_by_name("UnknownArchon")

        assert profile is None

    def test_get_all_sorted(self, temp_files) -> None:
        """Test get_all returns profiles sorted by rank then name."""
        json_path, yaml_path = temp_files
        adapter = JsonYamlArchonProfileAdapter(json_path, yaml_path)

        profiles = adapter.get_all()

        assert len(profiles) == 5
        # Executives first (rank 8), then senior (rank 7), then strategic (rank 4)
        assert profiles[0].rank_level == 8
        assert profiles[1].rank_level == 8
        assert profiles[2].rank_level == 7
        assert profiles[3].rank_level == 4
        assert profiles[4].rank_level == 4

    def test_get_by_rank(self, temp_files) -> None:
        """Test filtering profiles by rank."""
        json_path, yaml_path = temp_files
        adapter = JsonYamlArchonProfileAdapter(json_path, yaml_path)

        executives = adapter.get_by_rank("executive_director")

        assert len(executives) == 2
        assert all(p.aegis_rank == "executive_director" for p in executives)

    def test_get_by_tool(self, temp_files) -> None:
        """Test filtering profiles by tool."""
        json_path, yaml_path = temp_files
        adapter = JsonYamlArchonProfileAdapter(json_path, yaml_path)

        with_insight = adapter.get_by_tool("insight_tool")

        assert len(with_insight) == 1
        assert with_insight[0].name == "Eligos"

    def test_get_executives(self, temp_files) -> None:
        """Test retrieving executive directors."""
        json_path, yaml_path = temp_files
        adapter = JsonYamlArchonProfileAdapter(json_path, yaml_path)

        executives = adapter.get_executives()

        assert len(executives) == 2
        assert all(p.aegis_rank == "executive_director" for p in executives)

    def test_exists(self, temp_files) -> None:
        """Test checking if archon exists."""
        json_path, yaml_path = temp_files
        adapter = JsonYamlArchonProfileAdapter(json_path, yaml_path)

        paimon_id = UUID("11111111-1111-1111-1111-111111111111")
        unknown_id = UUID("99999999-9999-9999-9999-999999999999")

        assert adapter.exists(paimon_id) is True
        assert adapter.exists(unknown_id) is False


class TestGovernanceFeatures:
    """Tests for governance branch features."""

    def test_get_by_branch(self, temp_files) -> None:
        """Test filtering profiles by governance branch."""
        json_path, yaml_path = temp_files
        adapter = JsonYamlArchonProfileAdapter(json_path, yaml_path)

        legislative = adapter.get_by_branch("legislative")

        assert len(legislative) == 2
        assert all(p.branch == "legislative" for p in legislative)

    def test_get_by_branch_empty(self, temp_files) -> None:
        """Test get_by_branch returns empty list for unknown branch."""
        json_path, yaml_path = temp_files
        adapter = JsonYamlArchonProfileAdapter(json_path, yaml_path)

        unknown = adapter.get_by_branch("unknown_branch")

        assert unknown == []

    def test_get_witness(self, temp_files) -> None:
        """Test retrieving the Knight-Witness (Furcas)."""
        json_path, yaml_path = temp_files
        adapter = JsonYamlArchonProfileAdapter(json_path, yaml_path)

        witness = adapter.get_witness()

        assert witness is not None
        assert witness.name == "Furcas"
        assert witness.branch == "witness"

    def test_get_all_names(self, temp_files) -> None:
        """Test retrieving all archon names in canonical order."""
        json_path, yaml_path = temp_files
        adapter = JsonYamlArchonProfileAdapter(json_path, yaml_path)

        names = adapter.get_all_names()

        assert len(names) == 5
        # First two should be executives (rank 8, alphabetically sorted)
        assert names[0] in ["Belial", "Paimon"]
        assert names[1] in ["Belial", "Paimon"]

    def test_profile_governance_properties(self, temp_files) -> None:
        """Test governance properties on profile instances."""
        json_path, yaml_path = temp_files
        adapter = JsonYamlArchonProfileAdapter(json_path, yaml_path)

        paimon = adapter.get_by_name("Paimon")
        furcas = adapter.get_by_name("Furcas")

        assert paimon is not None
        assert paimon.is_legislative is True
        assert paimon.is_witness is False
        assert "introduce_motion" in paimon.governance_permissions

        assert furcas is not None
        assert furcas.is_witness is True
        assert furcas.is_legislative is False
        assert "observe_all" in furcas.governance_permissions
        assert "no_propose" in furcas.governance_constraints


class TestLLMConfigResolution:
    """Tests for LLM configuration resolution priority."""

    def test_explicit_archon_config_takes_priority(self, temp_files) -> None:
        """Test that explicit archon config overrides rank defaults."""
        json_path, yaml_path = temp_files
        adapter = JsonYamlArchonProfileAdapter(json_path, yaml_path)

        # Paimon has explicit config in YAML
        paimon_id = UUID("11111111-1111-1111-1111-111111111111")
        profile = adapter.get_by_id(paimon_id)

        assert profile is not None
        assert profile.llm_config.model == "claude-3-opus-20240229"
        assert profile.llm_config.temperature == 0.8
        assert profile.llm_config.max_tokens == 8192

    def test_rank_default_used_when_no_explicit(self, temp_files) -> None:
        """Test that rank defaults are used when no explicit config."""
        json_path, yaml_path = temp_files
        adapter = JsonYamlArchonProfileAdapter(json_path, yaml_path)

        # Belial is executive_director but no explicit config
        belial_id = UUID("22222222-2222-2222-2222-222222222222")
        profile = adapter.get_by_id(belial_id)

        assert profile is not None
        # Should use executive_director rank default
        assert profile.llm_config.model == "claude-sonnet-4-20250514"
        assert profile.llm_config.temperature == 0.7

    def test_global_default_used_for_unknown_rank(self, temp_files) -> None:
        """Test that global default is used for ranks not in rank_defaults."""
        json_path, yaml_path = temp_files
        adapter = JsonYamlArchonProfileAdapter(json_path, yaml_path)

        # Raum is strategic_director - no rank default in our test YAML
        raum_id = UUID("44444444-4444-4444-4444-444444444444")
        profile = adapter.get_by_id(raum_id)

        assert profile is not None
        # Should use global _default
        assert profile.llm_config.model == "claude-3-haiku-20240307"
        assert profile.llm_config.temperature == 0.5

    def test_get_by_provider(self, temp_files) -> None:
        """Test filtering profiles by LLM provider."""
        json_path, yaml_path = temp_files
        adapter = JsonYamlArchonProfileAdapter(json_path, yaml_path)

        anthropic_profiles = adapter.get_by_provider("anthropic")

        assert len(anthropic_profiles) == 5  # All use Anthropic in test data


class TestErrorHandling:
    """Tests for error handling."""

    def test_json_not_found(self) -> None:
        """Test error when JSON file doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yaml_path = Path(tmpdir) / "llm-bindings.yaml"
            yaml_path.write_text(SAMPLE_YAML)

            with pytest.raises(ArchonProfileLoadError, match="File not found"):
                JsonYamlArchonProfileAdapter(
                    Path(tmpdir) / "nonexistent.json",
                    yaml_path,
                )

    def test_yaml_not_found_uses_defaults(self) -> None:
        """Test that missing YAML file uses default config."""
        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = Path(tmpdir) / "archons.json"
            json_path.write_text(json.dumps(SAMPLE_JSON))

            # No YAML file - should use defaults
            adapter = JsonYamlArchonProfileAdapter(
                json_path,
                Path(tmpdir) / "nonexistent.yaml",
            )

            profile = adapter.get_by_name("Paimon")
            assert profile is not None
            # Should use hardcoded DEFAULT_LLM_CONFIG
            assert profile.llm_config.model == "claude-3-haiku-20240307"


class TestBackwardsCompatibility:
    """Tests for backwards compatibility."""

    def test_csv_alias_exists(self) -> None:
        """Test that CsvYamlArchonProfileAdapter is an alias."""
        assert CsvYamlArchonProfileAdapter is JsonYamlArchonProfileAdapter


class TestAttributeParsing:
    """Tests for JSON attribute parsing."""

    def test_parse_personality_from_attributes(self, temp_files) -> None:
        """Test personality is extracted from attributes."""
        json_path, yaml_path = temp_files
        adapter = JsonYamlArchonProfileAdapter(json_path, yaml_path)

        profile = adapter.get_by_name("Paimon")

        assert profile is not None
        assert profile.personality == "Wise"

    def test_parse_brand_color_from_attributes(self, temp_files) -> None:
        """Test brand_color is extracted from attributes."""
        json_path, yaml_path = temp_files
        adapter = JsonYamlArchonProfileAdapter(json_path, yaml_path)

        profile = adapter.get_by_name("Paimon")

        assert profile is not None
        assert profile.brand_color == "Gold"

    def test_parse_tools_list(self, temp_files) -> None:
        """Test suggested_tools is parsed as list."""
        json_path, yaml_path = temp_files
        adapter = JsonYamlArchonProfileAdapter(json_path, yaml_path)

        profile = adapter.get_by_name("Paimon")

        assert profile is not None
        assert profile.suggested_tools == ["knowledge_tool", "communication_tool"]


class TestIntegrationWithRealData:
    """Integration tests using actual archons-base.json if available."""

    @pytest.mark.skipif(
        not Path("docs/archons-base.json").exists(),
        reason="archons-base.json not found",
    )
    def test_load_real_archons_json(self) -> None:
        """Test loading the real archons JSON file."""
        json_path = Path("docs/archons-base.json")
        yaml_path = Path("config/archon-llm-bindings.yaml")

        adapter = JsonYamlArchonProfileAdapter(json_path, yaml_path)

        # Should have all 72 archons
        assert adapter.count() == 72

        # Check a known archon
        paimon = adapter.get_by_name("Paimon")
        assert paimon is not None
        assert paimon.aegis_rank == "executive_director"
        assert paimon.branch == "legislative"

    @pytest.mark.skipif(
        not Path("docs/archons-base.json").exists(),
        reason="archons-base.json not found",
    )
    def test_factory_function(self) -> None:
        """Test the factory function with real data."""
        repo = create_archon_profile_repository()

        assert repo.count() == 72

    @pytest.mark.skipif(
        not Path("docs/archons-base.json").exists(),
        reason="archons-base.json not found",
    )
    def test_witness_in_real_data(self) -> None:
        """Test that Furcas is the witness in real data."""
        repo = create_archon_profile_repository()

        witness = repo.get_witness()
        assert witness is not None
        assert witness.name == "Furcas"
        assert witness.branch == "witness"

    @pytest.mark.skipif(
        not Path("docs/archons-base.json").exists(),
        reason="archons-base.json not found",
    )
    def test_all_branches_present(self) -> None:
        """Test that all governance branches are represented."""
        repo = create_archon_profile_repository()

        for branch in ["legislative", "executive", "administrative", "judicial", "advisory", "witness"]:
            profiles = repo.get_by_branch(branch)
            assert len(profiles) > 0, f"No archons in {branch} branch"
