"""Tests for Executive pipeline CLI (v2 mode handling)."""

import tempfile
from pathlib import Path

# Import the CLI functions to test
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from scripts.run_executive_pipeline import (
    check_manual_artifacts_exist,
    resolve_president_deliberator_config,
)


class TestCheckManualArtifactsExist:
    """Test manual artifact detection for auto mode."""

    def test_returns_false_for_nonexistent_directory(self):
        """Should return False if inbox directory doesn't exist."""
        result = check_manual_artifacts_exist(Path("/nonexistent/path"))
        assert result is False

    def test_returns_false_for_empty_directory(self):
        """Should return False if inbox is empty."""
        with tempfile.TemporaryDirectory() as tmpdir:
            inbox = Path(tmpdir)
            result = check_manual_artifacts_exist(inbox)
            assert result is False

    def test_returns_true_for_contribution_file(self):
        """Should return True if contribution file exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            inbox = Path(tmpdir)
            (inbox / "contribution_portfolio_tech.json").write_text("{}")
            result = check_manual_artifacts_exist(inbox)
            assert result is True

    def test_returns_true_for_attestation_file(self):
        """Should return True if attestation file exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            inbox = Path(tmpdir)
            (inbox / "attestation_portfolio_gov.json").write_text("{}")
            result = check_manual_artifacts_exist(inbox)
            assert result is True

    def test_returns_false_for_unrelated_files(self):
        """Should return False if only unrelated files exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            inbox = Path(tmpdir)
            (inbox / "random_file.json").write_text("{}")
            (inbox / "scaffold_portfolio_tech.json").write_text("{}")
            result = check_manual_artifacts_exist(inbox)
            assert result is False


class TestResolvePresidentDeliberatorConfig:
    """Test environment variable config resolution."""

    def test_returns_none_when_no_env_vars(self, monkeypatch):
        """Should return None when no environment variables are set."""
        monkeypatch.delenv("PRESIDENT_DELIBERATOR_MODEL", raising=False)
        monkeypatch.delenv("PRESIDENT_DELIBERATOR_ARCHON_ID", raising=False)
        result = resolve_president_deliberator_config()
        assert result is None

    def test_parses_ollama_model(self, monkeypatch):
        """Should parse ollama/ prefixed model string."""
        monkeypatch.setenv("PRESIDENT_DELIBERATOR_MODEL", "ollama/qwen3:latest")
        result = resolve_president_deliberator_config()
        assert result is not None
        assert result.provider == "ollama"
        assert result.model == "qwen3:latest"
        assert result.temperature == 0.3

    def test_parses_openai_model(self, monkeypatch):
        """Should parse openai/ prefixed model string."""
        monkeypatch.setenv("PRESIDENT_DELIBERATOR_MODEL", "openai/gpt-4")
        result = resolve_president_deliberator_config()
        assert result is not None
        assert result.provider == "openai"
        assert result.model == "gpt-4"

    def test_parses_anthropic_model(self, monkeypatch):
        """Should parse anthropic/ prefixed model string."""
        monkeypatch.setenv("PRESIDENT_DELIBERATOR_MODEL", "anthropic/claude-3-opus")
        result = resolve_president_deliberator_config()
        assert result is not None
        assert result.provider == "anthropic"
        assert result.model == "claude-3-opus"

    def test_defaults_to_ollama_for_unqualified_model(self, monkeypatch):
        """Should default to ollama for unqualified model names."""
        monkeypatch.setenv("PRESIDENT_DELIBERATOR_MODEL", "llama3.3:latest")
        result = resolve_president_deliberator_config()
        assert result is not None
        assert result.provider == "ollama"
        assert result.model == "llama3.3:latest"

    def test_respects_temperature_override(self, monkeypatch):
        """Should use PRESIDENT_DELIBERATOR_TEMPERATURE if set."""
        monkeypatch.setenv("PRESIDENT_DELIBERATOR_MODEL", "ollama/qwen3:latest")
        monkeypatch.setenv("PRESIDENT_DELIBERATOR_TEMPERATURE", "0.7")
        result = resolve_president_deliberator_config()
        assert result is not None
        assert result.temperature == 0.7
