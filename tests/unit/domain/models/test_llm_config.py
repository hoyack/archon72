"""Unit tests for LLMConfig domain model."""

import pytest

from src.domain.models.llm_config import (
    DEFAULT_LLM_CONFIG,
    GPT4O_LLM_CONFIG,
    OPUS_LLM_CONFIG,
    SONNET_LLM_CONFIG,
    LLMConfig,
)


class TestLLMConfig:
    """Tests for LLMConfig dataclass."""

    def test_create_valid_config(self) -> None:
        """Test creating a valid LLM config."""
        config = LLMConfig(
            provider="anthropic",
            model="claude-3-opus",
            temperature=0.7,
            max_tokens=4096,
            timeout_ms=30000,
        )

        assert config.provider == "anthropic"
        assert config.model == "claude-3-opus"
        assert config.temperature == 0.7
        assert config.max_tokens == 4096
        assert config.timeout_ms == 30000
        assert config.api_key_env is None

    def test_create_config_with_api_key_override(self) -> None:
        """Test creating config with custom API key env var."""
        config = LLMConfig(
            provider="openai",
            model="gpt-4o",
            temperature=0.5,
            max_tokens=2048,
            timeout_ms=20000,
            api_key_env="CUSTOM_OPENAI_KEY",
        )

        assert config.api_key_env == "CUSTOM_OPENAI_KEY"
        assert config.default_api_key_env == "CUSTOM_OPENAI_KEY"

    def test_default_api_key_env_anthropic(self) -> None:
        """Test default API key env for Anthropic."""
        config = LLMConfig(provider="anthropic", model="claude-3-opus")
        assert config.default_api_key_env == "ANTHROPIC_API_KEY"

    def test_default_api_key_env_openai(self) -> None:
        """Test default API key env for OpenAI."""
        config = LLMConfig(provider="openai", model="gpt-4o")
        assert config.default_api_key_env == "OPENAI_API_KEY"

    def test_default_api_key_env_google(self) -> None:
        """Test default API key env for Google."""
        config = LLMConfig(provider="google", model="gemini-pro")
        assert config.default_api_key_env == "GOOGLE_API_KEY"

    def test_default_api_key_env_local(self) -> None:
        """Test default API key env for local provider."""
        config = LLMConfig(provider="local", model="llama-3")
        assert config.default_api_key_env == "LOCAL_LLM_API_KEY"

    def test_invalid_temperature_too_high(self) -> None:
        """Test that temperature > 1.0 raises ValueError."""
        with pytest.raises(ValueError, match="temperature must be between"):
            LLMConfig(provider="anthropic", model="test", temperature=1.5)

    def test_invalid_temperature_negative(self) -> None:
        """Test that negative temperature raises ValueError."""
        with pytest.raises(ValueError, match="temperature must be between"):
            LLMConfig(provider="anthropic", model="test", temperature=-0.1)

    def test_invalid_max_tokens_zero(self) -> None:
        """Test that max_tokens=0 raises ValueError."""
        with pytest.raises(ValueError, match="max_tokens must be positive"):
            LLMConfig(provider="anthropic", model="test", max_tokens=0)

    def test_invalid_max_tokens_negative(self) -> None:
        """Test that negative max_tokens raises ValueError."""
        with pytest.raises(ValueError, match="max_tokens must be positive"):
            LLMConfig(provider="anthropic", model="test", max_tokens=-100)

    def test_invalid_timeout_too_low(self) -> None:
        """Test that timeout < 1000ms raises ValueError."""
        with pytest.raises(ValueError, match="timeout_ms must be at least 1000ms"):
            LLMConfig(provider="anthropic", model="test", timeout_ms=500)

    def test_config_is_frozen(self) -> None:
        """Test that LLMConfig is immutable."""
        config = LLMConfig(provider="anthropic", model="test")
        with pytest.raises(AttributeError):
            config.provider = "openai"  # type: ignore

    def test_config_equality(self) -> None:
        """Test that identical configs are equal."""
        config1 = LLMConfig(provider="anthropic", model="test", temperature=0.5)
        config2 = LLMConfig(provider="anthropic", model="test", temperature=0.5)
        assert config1 == config2

    def test_config_inequality(self) -> None:
        """Test that different configs are not equal."""
        config1 = LLMConfig(provider="anthropic", model="test")
        config2 = LLMConfig(provider="openai", model="test")
        assert config1 != config2


class TestPresetConfigs:
    """Tests for preset LLM configurations."""

    def test_default_config(self) -> None:
        """Test DEFAULT_LLM_CONFIG preset."""
        assert DEFAULT_LLM_CONFIG.provider == "anthropic"
        assert DEFAULT_LLM_CONFIG.model == "claude-3-haiku-20240307"
        assert DEFAULT_LLM_CONFIG.temperature == 0.5
        assert DEFAULT_LLM_CONFIG.max_tokens == 2048

    def test_opus_config(self) -> None:
        """Test OPUS_LLM_CONFIG preset."""
        assert OPUS_LLM_CONFIG.provider == "anthropic"
        assert OPUS_LLM_CONFIG.model == "claude-3-opus-20240229"
        assert OPUS_LLM_CONFIG.timeout_ms == 60000

    def test_sonnet_config(self) -> None:
        """Test SONNET_LLM_CONFIG preset."""
        assert SONNET_LLM_CONFIG.provider == "anthropic"
        assert "sonnet" in SONNET_LLM_CONFIG.model

    def test_gpt4o_config(self) -> None:
        """Test GPT4O_LLM_CONFIG preset."""
        assert GPT4O_LLM_CONFIG.provider == "openai"
        assert GPT4O_LLM_CONFIG.model == "gpt-4o"
