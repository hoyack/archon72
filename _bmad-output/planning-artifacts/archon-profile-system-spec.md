# Archon Profile Configuration System

**Status:** Implemented
**Date:** 2026-01-10
**Related ADR:** ADR-2 (Context Reconstruction + Signature Trust)

---

## Overview

The Archon Profile Configuration System provides per-archon identity and LLM binding configuration for the 72 deliberative agents. This system separates identity data (who the archon is) from operational configuration (which LLM powers it), enabling granular control over each agent's capabilities and behavior.

## Architecture

### Design Principles

1. **Separation of Concerns**: Identity data (CSV) is separate from operational config (YAML)
2. **Per-Archon Granularity**: Each of 72 archons can have unique LLM bindings
3. **Fallback Hierarchy**: Explicit config → Rank defaults → Global defaults
4. **Immutable Profiles**: Loaded once at startup, profiles are frozen dataclasses

### Component Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Configuration Sources                           │
├──────────────────────────────┬──────────────────────────────────────┤
│  docs/archons-base.csv       │  config/archon-llm-bindings.yaml     │
│  ────────────────────────    │  ─────────────────────────────────   │
│  • 72 archon identities      │  • Per-archon LLM configs            │
│  • Names, ranks, backstories │  • Rank-based defaults               │
│  • System prompts            │  • Global fallback                   │
│  • Suggested tools           │  • Provider/model/temperature        │
│  • Attributes JSON           │  • Timeout and token limits          │
└──────────────────────────────┴──────────────────────────────────────┘
                    │                              │
                    └──────────────┬───────────────┘
                                   ▼
              ┌────────────────────────────────────────┐
              │     CsvYamlArchonProfileAdapter        │
              │     ────────────────────────────       │
              │  Implements: ArchonProfileRepository   │
              │  Loads and merges both sources         │
              │  Resolves LLM config with priority     │
              └────────────────────────────────────────┘
                                   │
                                   ▼
              ┌────────────────────────────────────────┐
              │         ArchonProfile (Domain)         │
              │         ─────────────────────          │
              │  Immutable frozen dataclass            │
              │  Contains: identity + llm_config       │
              │  Methods: get_crewai_config()          │
              └────────────────────────────────────────┘
                                   │
                                   ▼
              ┌────────────────────────────────────────┐
              │     AgentOrchestratorProtocol          │
              │     ────────────────────────           │
              │  Uses ArchonProfile to create          │
              │  CrewAI agents with correct config     │
              └────────────────────────────────────────┘
```

---

## Domain Models

### LLMConfig

```python
@dataclass(frozen=True, eq=True)
class LLMConfig:
    provider: LLMProvider      # "anthropic" | "openai" | "google" | "local"
    model: str                 # e.g., "claude-3-opus", "gpt-4o"
    temperature: float = 0.7   # 0.0 - 1.0
    max_tokens: int = 4096
    timeout_ms: int = 30000
    api_key_env: str | None = None  # Override for API key env var
```

**Validation:**
- Temperature: 0.0 ≤ T ≤ 1.0
- Max tokens: > 0
- Timeout: ≥ 1000ms

### ArchonProfile

```python
@dataclass(frozen=True, eq=True)
class ArchonProfile:
    # Identity (from CSV)
    id: UUID
    name: str                    # "Paimon", "Belial", etc.
    aegis_rank: str              # "executive_director", "senior_director", etc.
    original_rank: str           # "King", "Duke", "Marquis", etc.
    rank_level: int              # 8 (King) down to 4 (Knight)
    role: str                    # Functional role description
    goal: str                    # Agent's primary objective
    backstory: str               # Rich narrative background
    system_prompt: str           # CrewAI-compatible prompt
    suggested_tools: list[str]   # Tool identifiers
    allow_delegation: bool
    attributes: dict[str, Any]   # Extended attributes

    # Operational (from YAML)
    llm_config: LLMConfig
```

**Properties:**
- `personality` → Extracted from attributes
- `brand_color` → Extracted from attributes
- `is_executive` → True if executive_director
- `can_delegate` → Based on rank and allow_delegation

**Methods:**
- `get_crewai_config()` → Returns CrewAI Agent constructor dict
- `get_system_prompt_with_context(context)` → Injects runtime context

---

## Port Interface

```python
class ArchonProfileRepository(ABC):
    """Read-only repository for Archon profiles."""

    def get_by_id(self, archon_id: UUID) -> ArchonProfile | None: ...
    def get_by_name(self, name: str) -> ArchonProfile | None: ...
    def get_all(self) -> list[ArchonProfile]: ...
    def get_by_rank(self, aegis_rank: str) -> list[ArchonProfile]: ...
    def get_by_tool(self, tool_name: str) -> list[ArchonProfile]: ...
    def get_by_provider(self, provider: str) -> list[ArchonProfile]: ...
    def get_executives(self) -> list[ArchonProfile]: ...
    def count(self) -> int: ...
    def exists(self, archon_id: UUID) -> bool: ...
```

---

## Configuration Files

### docs/archons-base.csv

Source of truth for Archon identity. Based on the Ars Goetia mythological framework.

**Columns:**
| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| name | string | Archon name (Paimon, Belial, etc.) |
| aegis_rank | string | Network hierarchy position |
| original_rank | string | Traditional Goetic rank |
| rank_level | int | Numeric rank (4-8) |
| role | string | Functional role |
| goal | string | Primary objective |
| backstory | text | Rich narrative |
| system_prompt | text | CrewAI-compatible prompt |
| suggested_tools | JSON array | Tool identifiers |
| allow_delegation | boolean | Can delegate tasks |
| attributes | JSON object | Extended attributes |

### config/archon-llm-bindings.yaml

Per-archon LLM configuration with fallback hierarchy.

```yaml
# Global default (lowest priority)
_default:
  provider: anthropic
  model: claude-3-haiku-20240307
  temperature: 0.5
  max_tokens: 2048

# Rank-based defaults (medium priority)
_rank_defaults:
  executive_director:
    provider: anthropic
    model: claude-sonnet-4-20250514
    temperature: 0.7
    max_tokens: 4096
  senior_director:
    provider: anthropic
    model: claude-sonnet-4-20250514
    temperature: 0.6
    max_tokens: 4096

# Per-archon overrides (highest priority)
1a4a2056-e2b5-42a7-a338-8b8b67509f1f:  # Paimon
  provider: anthropic
  model: claude-3-opus-20240229
  temperature: 0.8
  max_tokens: 8192
```

---

## LLM Config Resolution Priority

1. **Explicit UUID match** in YAML → Use that config
2. **Rank default** (`_rank_defaults.<aegis_rank>`) → Use rank config
3. **Global default** (`_default`) → Use default config
4. **Hardcoded fallback** → DEFAULT_LLM_CONFIG constant

---

## Usage Examples

### Load Repository

```python
from src.infrastructure.adapters.config import create_archon_profile_repository

repo = create_archon_profile_repository()
assert repo.count() == 72
```

### Get Archon by Name

```python
paimon = repo.get_by_name("Paimon")
print(f"LLM: {paimon.llm_config.model}")  # claude-3-opus-20240229
print(f"Temp: {paimon.llm_config.temperature}")  # 0.8
```

### Filter by Rank

```python
executives = repo.get_executives()
# Returns 9 King-rank archons (Paimon, Belial, Beleth, etc.)
```

### Filter by Tool

```python
analysts = repo.get_by_tool("insight_tool")
# Returns archons with insight_tool in suggested_tools
```

### Generate CrewAI Config

```python
crewai_config = paimon.get_crewai_config()
# Returns: {
#   "role": "Executive Director...",
#   "goal": "Develop members...",
#   "backstory": "Paimon is...",
#   "verbose": True,
#   "allow_delegation": True
# }
```

---

## File Locations

| File | Purpose |
|------|---------|
| `src/domain/models/llm_config.py` | LLMConfig dataclass |
| `src/domain/models/archon_profile.py` | ArchonProfile dataclass |
| `src/application/ports/archon_profile_repository.py` | Repository port |
| `src/infrastructure/adapters/config/archon_profile_adapter.py` | CSV+YAML adapter |
| `docs/archons-base.csv` | 72 archon identities |
| `config/archon-llm-bindings.yaml` | Per-archon LLM configs |

---

## Constitutional Alignment

| Requirement | How Addressed |
|-------------|---------------|
| FR9 (72 concurrent agents) | All 72 profiles loadable |
| FR10 (Agent deliberation) | CrewAI config generation |
| NFR5 (72 concurrent without degradation) | Profiles are immutable, no runtime allocation |
| CT-14 (Complexity budget) | Simple YAML config, no dynamic loading |

---

## Testing

- **Unit tests:** 65 tests covering all models and adapter
- **Integration tests:** Load real archons-base.csv with 72 entries
- **Location:** `tests/unit/domain/models/`, `tests/unit/infrastructure/adapters/config/`

---

## Future Considerations

1. **Hot-reload:** Currently profiles are loaded once at startup. Consider file-watching for development.
2. **Database-backed:** For production, may want to store LLM configs in database for A/B testing.
3. **Personality distinctiveness (M-2.3):** Add behavioral fingerprinting to validate archon differentiation.
4. **Cost tracking:** Add per-archon cost tracking based on LLM usage.
