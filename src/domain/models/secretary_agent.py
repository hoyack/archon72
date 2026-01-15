"""Secretary Agent profile model for automated Conclave post-processing.

The Secretary is a special 73rd agent that processes Conclave transcripts
rather than participating in deliberations. It extracts recommendations,
validates completeness, clusters semantically, and generates motion text.

Unlike the 72 Archons, the Secretary:
- Is administrative, not deliberative
- Does not vote or speak in Conclave
- Has specialized tools for extraction and synthesis
- Uses dual LLM configs: text model for extraction, JSON model for formatting

Configuration is loaded from config/secretary-llm-config.yaml
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import UUID

import yaml

from src.domain.models.llm_config import LLMConfig


# Default config file path - relative to project root
# Find project root by looking for pyproject.toml
def _find_project_root() -> Path:
    """Find project root by looking for pyproject.toml."""
    current = Path(__file__).resolve().parent
    for _ in range(10):  # Max 10 levels up
        if (current / "pyproject.toml").exists():
            return current
        current = current.parent
    # Fallback to cwd
    return Path.cwd()


_PROJECT_ROOT = _find_project_root()
_CONFIG_FILE = _PROJECT_ROOT / "config" / "secretary-llm-config.yaml"


# Reserved UUID for the Secretary (73rd agent)
SECRETARY_AGENT_ID = UUID("00000000-0000-0000-0000-000000000073")


# Default LLM configs for Secretary - uses local Ollama
# Set OLLAMA_HOST environment variable to your Ollama server address

# Text model for extraction and analysis (good at understanding nuance)
_TEXT_LLM_CONFIG = LLMConfig(
    provider="local",
    model="ministral-3:latest",
    temperature=0.3,  # Low temperature for accuracy
    max_tokens=4096,
    timeout_ms=180000,  # 3 minutes
)

# JSON model for structured output (good at formatting)
_JSON_LLM_CONFIG = LLMConfig(
    provider="local",
    model="devstral-small:latest",
    temperature=0.1,  # Very low for consistent JSON
    max_tokens=8192,  # Larger context for clustering
    timeout_ms=300000,  # 5 minutes for complex tasks
)


_DEFAULT_BACKSTORY = """You are the Conclave Secretary, an impartial administrative
agent responsible for processing deliberation transcripts from the Archon 72 Conclave.

Your role is critical to the continuity of governance. After each Conclave session,
you analyze the full transcript to:

1. EXTRACT every recommendation, proposal, and suggestion made by the 72 Archons
2. VALIDATE that nothing has been missed - thoroughness is paramount
3. CLUSTER similar recommendations to identify consensus themes
4. DETECT conflicting positions that require resolution
5. SYNTHESIZE formal motion text for high-consensus items

You are NOT a participant in deliberations. You do not vote, debate, or take sides.
Your role is purely analytical and synthesizing. Accuracy and completeness are your
highest values - a missed recommendation could mean a lost insight from the collective.

Constitutional Constraints you uphold:
- CT-11: Silent failure destroys legitimacy - you report all findings, including gaps
- CT-12: Witnessing creates accountability - all extractions trace to source lines
- FR9: All outputs flow through the witnessing pipeline

You serve the Conclave with precision, impartiality, and unwavering attention to detail."""


_DEFAULT_SYSTEM_PROMPT = """You are the Conclave Secretary for the Archon 72 governance system.

Your task is to process deliberation transcripts and extract structured information.
You must be thorough, accurate, and impartial.

When extracting recommendations:
- Look for explicit proposals ("I recommend...", "I propose...", "We should...")
- Look for implicit suggestions ("It would be wise to...", "Consider...")
- Look for action items ("Task the committee to...", "Establish...")
- Look for amendments ("Modify the existing...", "Update...")
- Look for concerns that imply needed action ("The current system fails to...")

For each recommendation, identify:
- Category: establish, implement, mandate, amend, investigate, pilot, educate, review
- Type: policy, task, amendment, concern
- Source: Archon name and context
- Keywords: Key terms for clustering
- Stance: If responding to a motion, is this FOR, AGAINST, or NEUTRAL

When clustering:
- Group by semantic theme, not just keyword overlap
- Compatible stances can cluster together
- Conflicting stances should not cluster

When generating motion text:
- Use formal, actionable language
- Be specific about what is to be done
- Reference the consensus basis
- Include implementation considerations

Output structured JSON for programmatic processing."""


@dataclass(frozen=True, eq=True)
class SecretaryAgentProfile:
    """Profile for the Conclave Secretary agent.

    The Secretary is a specialized agent for transcript analysis,
    distinct from the 72 Archons. It maintains impartiality and
    focuses on accurate extraction and synthesis.

    Uses a dual-model approach:
    - text_llm_config: For natural language extraction and analysis
    - json_llm_config: For structured output (clustering, motions, validation)

    Attributes:
        id: Fixed UUID for the Secretary
        name: Display name
        role: Functional role description
        goal: Primary objective
        backstory: Narrative background for CrewAI
        system_prompt: Complete system prompt for LLM invocation
        suggested_tools: List of Secretary-specific tool identifiers
        text_llm_config: LLM for text extraction (ministral-3b)
        json_llm_config: LLM for JSON formatting (devstral-small)
        checkpoints_enabled: Whether to save checkpoints between steps
    """

    id: UUID = SECRETARY_AGENT_ID
    name: str = "Conclave Secretary"
    role: str = "Transcript Analyst and Motion Synthesizer"
    goal: str = (
        "Extract all recommendations from Archon deliberations with nuanced "
        "understanding, validate completeness, cluster semantically similar items, "
        "detect conflicts, and generate actionable motion text for the next Conclave."
    )
    backstory: str = field(default_factory=lambda: _DEFAULT_BACKSTORY)
    system_prompt: str = field(default_factory=lambda: _DEFAULT_SYSTEM_PROMPT)
    suggested_tools: list[str] = field(
        default_factory=lambda: [
            "extraction_tool",
            "validation_tool",
            "clustering_tool",
            "motion_synthesis_tool",
        ]
    )
    text_llm_config: LLMConfig = field(default_factory=lambda: _TEXT_LLM_CONFIG)
    json_llm_config: LLMConfig = field(default_factory=lambda: _JSON_LLM_CONFIG)
    checkpoints_enabled: bool = True

    # Backward compatibility - return text config as default
    @property
    def llm_config(self) -> LLMConfig:
        """Backward compatibility: return text LLM config."""
        return self.text_llm_config

    def get_crewai_config(self) -> dict[str, Any]:
        """Generate CrewAI Agent configuration dictionary."""
        return {
            "role": self.role,
            "goal": self.goal,
            "backstory": self.backstory,
            "verbose": True,
            "allow_delegation": False,  # Secretary works alone
        }


def _load_llm_config_from_dict(config_dict: dict) -> LLMConfig:
    """Create LLMConfig from a dictionary."""
    return LLMConfig(
        provider=config_dict.get("provider", "local"),
        model=config_dict.get("model", "ministral-3:latest"),
        temperature=config_dict.get("temperature", 0.3),
        max_tokens=config_dict.get("max_tokens", 4096),
        timeout_ms=config_dict.get("timeout_ms", 180000),
    )


def load_secretary_config_from_yaml(
    config_path: Path | str | None = None,
) -> tuple[LLMConfig, LLMConfig, bool]:
    """Load Secretary LLM configs from YAML file.

    Args:
        config_path: Path to YAML config file (uses default if None)

    Returns:
        Tuple of (text_llm_config, json_llm_config, checkpoints_enabled)

    Raises:
        FileNotFoundError: If config file doesn't exist
    """
    path = Path(config_path) if config_path else _CONFIG_FILE

    if not path.exists():
        # Return hardcoded defaults if config doesn't exist
        return _TEXT_LLM_CONFIG, _JSON_LLM_CONFIG, True

    with open(path) as f:
        config = yaml.safe_load(f)

    secretary_config = config.get("secretary", {})

    # Load text model config
    text_model_dict = secretary_config.get("text_model", {})
    text_llm_config = _load_llm_config_from_dict(text_model_dict)

    # Load JSON model config
    json_model_dict = secretary_config.get("json_model", {})
    json_llm_config = _load_llm_config_from_dict(json_model_dict)

    # Load checkpoint settings
    checkpoints = secretary_config.get("checkpoints", {})
    checkpoints_enabled = checkpoints.get("enabled", True)

    return text_llm_config, json_llm_config, checkpoints_enabled


def create_default_secretary_profile(
    config_path: Path | str | None = None,
) -> SecretaryAgentProfile:
    """Factory function to create the Secretary profile from config file.

    Args:
        config_path: Path to YAML config file (uses default config/secretary-llm-config.yaml)

    Returns:
        SecretaryAgentProfile with configs loaded from YAML
    """
    text_config, json_config, checkpoints = load_secretary_config_from_yaml(config_path)

    return SecretaryAgentProfile(
        text_llm_config=text_config,
        json_llm_config=json_config,
        checkpoints_enabled=checkpoints,
    )


def create_secretary_profile_with_configs(
    text_llm_config: LLMConfig | None = None,
    json_llm_config: LLMConfig | None = None,
) -> SecretaryAgentProfile:
    """Factory function to create Secretary profile with custom LLM configs.

    Args:
        text_llm_config: LLM config for text extraction (loads from YAML if None)
        json_llm_config: LLM config for JSON formatting (loads from YAML if None)

    Returns:
        SecretaryAgentProfile with specified configs
    """
    # Load defaults from YAML
    yaml_text, yaml_json, checkpoints = load_secretary_config_from_yaml()

    return SecretaryAgentProfile(
        text_llm_config=text_llm_config or yaml_text,
        json_llm_config=json_llm_config or yaml_json,
        checkpoints_enabled=checkpoints,
    )
