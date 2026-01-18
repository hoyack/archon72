"""Unit tests for ArchonProfile domain model."""

from datetime import datetime
from uuid import uuid4

import pytest

from src.domain.models.archon_profile import AEGIS_RANKS, ArchonProfile
from src.domain.models.llm_config import DEFAULT_LLM_CONFIG, LLMConfig


def create_test_profile(**overrides) -> ArchonProfile:
    """Factory to create test ArchonProfile instances."""
    defaults = {
        "id": uuid4(),
        "name": "TestArchon",
        "aegis_rank": "senior_director",
        "original_rank": "Duke",
        "rank_level": 7,
        "role": "Test Role",
        "goal": "Test Goal",
        "backstory": "Test Backstory",
        "system_prompt": "You are TestArchon.",
        "suggested_tools": ["insight_tool", "communication_tool"],
        "allow_delegation": True,
        "attributes": {
            "personality": "Wise, Cunning",
            "brand_color": "Silver",
            "energy_type": "Analytical",
            "domain": "Test Domain",
            "focus_areas": "Testing, Development",
            "capabilities": "Test Capabilities",
        },
        "max_members": 100000,
        "max_legions": 10,
        "created_at": datetime.now(),
        "updated_at": datetime.now(),
        "llm_config": DEFAULT_LLM_CONFIG,
    }
    defaults.update(overrides)
    return ArchonProfile(**defaults)


class TestArchonProfile:
    """Tests for ArchonProfile dataclass."""

    def test_create_valid_profile(self) -> None:
        """Test creating a valid archon profile."""
        profile = create_test_profile(name="Paimon")

        assert profile.name == "Paimon"
        assert profile.aegis_rank == "senior_director"
        assert profile.rank_level == 7
        assert profile.llm_config == DEFAULT_LLM_CONFIG

    def test_all_aegis_ranks_valid(self) -> None:
        """Test that all defined ranks are valid."""
        for rank in AEGIS_RANKS:
            profile = create_test_profile(aegis_rank=rank)
            assert profile.aegis_rank == rank

    def test_invalid_aegis_rank(self) -> None:
        """Test that invalid aegis_rank raises ValueError."""
        with pytest.raises(ValueError, match="Invalid aegis_rank"):
            create_test_profile(aegis_rank="invalid_rank")

    def test_invalid_rank_level_too_low(self) -> None:
        """Test that rank_level < 4 raises ValueError."""
        with pytest.raises(ValueError, match="rank_level must be between"):
            create_test_profile(rank_level=3)

    def test_invalid_rank_level_too_high(self) -> None:
        """Test that rank_level > 8 raises ValueError."""
        with pytest.raises(ValueError, match="rank_level must be between"):
            create_test_profile(rank_level=9)

    def test_profile_is_frozen(self) -> None:
        """Test that ArchonProfile is immutable."""
        profile = create_test_profile()
        with pytest.raises(AttributeError):
            profile.name = "NewName"  # type: ignore


class TestArchonProfileProperties:
    """Tests for ArchonProfile computed properties."""

    def test_personality_property(self) -> None:
        """Test personality extraction from attributes."""
        profile = create_test_profile(attributes={"personality": "Wise, Cunning"})
        assert profile.personality == "Wise, Cunning"

    def test_personality_missing(self) -> None:
        """Test personality when not in attributes."""
        profile = create_test_profile(attributes={})
        assert profile.personality is None

    def test_brand_color_property(self) -> None:
        """Test brand_color extraction from attributes."""
        profile = create_test_profile(attributes={"brand_color": "Gold"})
        assert profile.brand_color == "Gold"

    def test_energy_type_property(self) -> None:
        """Test energy_type extraction from attributes."""
        profile = create_test_profile(attributes={"energy_type": "Dynamic"})
        assert profile.energy_type == "Dynamic"

    def test_domain_property(self) -> None:
        """Test domain extraction from attributes."""
        profile = create_test_profile(attributes={"domain": "Command Center"})
        assert profile.domain == "Command Center"

    def test_focus_areas_property(self) -> None:
        """Test focus_areas extraction from attributes."""
        profile = create_test_profile(attributes={"focus_areas": "Education, Research"})
        assert profile.focus_areas == "Education, Research"

    def test_capabilities_property(self) -> None:
        """Test capabilities extraction from attributes."""
        profile = create_test_profile(
            attributes={"capabilities": "Scientific Education"}
        )
        assert profile.capabilities == "Scientific Education"


class TestArchonProfileRankHelpers:
    """Tests for rank-related helper methods."""

    def test_is_executive_true(self) -> None:
        """Test is_executive for executive_director."""
        profile = create_test_profile(
            aegis_rank="executive_director",
            rank_level=8,
        )
        assert profile.is_executive is True

    def test_is_executive_false(self) -> None:
        """Test is_executive for non-executive ranks."""
        profile = create_test_profile(
            aegis_rank="senior_director",
            rank_level=7,
        )
        assert profile.is_executive is False

    def test_is_senior_true(self) -> None:
        """Test is_senior for senior_director."""
        profile = create_test_profile(
            aegis_rank="senior_director",
            rank_level=7,
        )
        assert profile.is_senior is True

    def test_is_senior_false(self) -> None:
        """Test is_senior for non-senior ranks."""
        profile = create_test_profile(
            aegis_rank="director",
            rank_level=6,
        )
        assert profile.is_senior is False

    def test_can_delegate_executive(self) -> None:
        """Test can_delegate for executive with allow_delegation=True."""
        profile = create_test_profile(
            aegis_rank="executive_director",
            rank_level=8,
            allow_delegation=True,
        )
        assert profile.can_delegate is True

    def test_can_delegate_low_rank(self) -> None:
        """Test can_delegate for low rank (< 5) returns False."""
        profile = create_test_profile(
            aegis_rank="strategic_director",
            rank_level=4,
            allow_delegation=True,
        )
        assert profile.can_delegate is False

    def test_can_delegate_disabled(self) -> None:
        """Test can_delegate when allow_delegation=False."""
        profile = create_test_profile(
            aegis_rank="executive_director",
            rank_level=8,
            allow_delegation=False,
        )
        assert profile.can_delegate is False


class TestArchonProfileCrewAI:
    """Tests for CrewAI integration methods."""

    def test_get_crewai_config(self) -> None:
        """Test CrewAI configuration generation."""
        profile = create_test_profile(
            role="Strategic Director",
            goal="Develop members through teaching",
            backstory="Ancient entity with vast knowledge",
            allow_delegation=True,
        )

        config = profile.get_crewai_config()

        assert config["role"] == "Strategic Director"
        assert config["goal"] == "Develop members through teaching"
        assert config["backstory"] == "Ancient entity with vast knowledge"
        assert config["verbose"] is True
        assert config["allow_delegation"] is True

    def test_get_system_prompt_without_context(self) -> None:
        """Test system prompt generation without additional context."""
        profile = create_test_profile(
            system_prompt="You are TestArchon, a wise entity."
        )

        prompt = profile.get_system_prompt_with_context()

        assert prompt == "You are TestArchon, a wise entity."

    def test_get_system_prompt_with_context(self) -> None:
        """Test system prompt generation with additional context."""
        profile = create_test_profile(
            system_prompt="You are TestArchon, a wise entity."
        )

        prompt = profile.get_system_prompt_with_context(
            context="The user is asking about philosophy."
        )

        assert "You are TestArchon, a wise entity." in prompt
        assert "CURRENT CONTEXT:" in prompt
        assert "The user is asking about philosophy." in prompt


class TestArchonProfileWithLLMConfig:
    """Tests for ArchonProfile with various LLM configurations."""

    def test_profile_with_custom_llm_config(self) -> None:
        """Test profile with custom LLM configuration."""
        custom_llm = LLMConfig(
            provider="openai",
            model="gpt-4o",
            temperature=0.8,
            max_tokens=8192,
            timeout_ms=60000,
        )

        profile = create_test_profile(llm_config=custom_llm)

        assert profile.llm_config.provider == "openai"
        assert profile.llm_config.model == "gpt-4o"
        assert profile.llm_config.temperature == 0.8
        assert profile.llm_config.max_tokens == 8192

    def test_profile_default_llm_config(self) -> None:
        """Test that profile uses DEFAULT_LLM_CONFIG by default."""
        profile = create_test_profile()
        assert profile.llm_config == DEFAULT_LLM_CONFIG
