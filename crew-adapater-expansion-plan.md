CrewAI Adapter Expansion Plan

Goal
- Expand per-archon configuration in `docs/archons-base-2.json` to include LLM/CrewAI adapter settings (provider, model, temperature, max_tokens, timeout, base_url, api_key_env) so each Archon can be bound to a specific LLM endpoint (Ollama or cloud).

Current Integration Points
- `src/domain/models/llm_config.py` defines the canonical fields: provider, model, temperature, max_tokens, timeout_ms, api_key_env, base_url.
- `src/infrastructure/adapters/external/crewai_adapter.py` and `src/infrastructure/adapters/external/reviewer_crewai_adapter.py` map `LLMConfig` to CrewAI LLM (Ollama if provider == local, otherwise provider/model string).
- `src/infrastructure/adapters/config/archon_profile_adapter.py` currently loads LLM bindings from `config/archon-llm-bindings.yaml` and applies them to profiles.

Proposed Data Source
- `docs/archons-base-2.json` now contains `llm_config` for every Archon (including `base_url` for Ollama). This makes the per-archon CrewAI binding part of the tracked profile definition.
- JSON is retained for consistency with `docs/archons-base.json`. It is editable and diffable; no runtime DB dependency.

Interface Plan (Code Wiring)
1) Update `ArchonProfileAdapter` to accept an optional `llm_config_source` policy:
   - `json` (load `llm_config` from `docs/archons-base-2.json`)
   - `yaml` (current `config/archon-llm-bindings.yaml` behavior)
   - `merge` (json defaults, yaml overrides, and per-archon explicit overrides win)
2) When loading from JSON:
   - Map `archon["llm_config"]` to `LLMConfig` fields directly.
   - Validate fields using `LLMConfig` (provider allowed values, temperature range, timeout minimum).
3) Keep the existing YAML path to allow ops overrides without touching the canonical profile file.

Provider Flexibility
- `provider` supports at least: `local`, `openai`, `anthropic`, `google` (per `LLMConfig`).
- `local` maps to Ollama in the CrewAI adapters and uses `base_url` when provided; otherwise it falls back to `OLLAMA_HOST`.
- `openai` and `anthropic` use standard CrewAI provider strings and rely on `OPENAI_API_KEY`/`ANTHROPIC_API_KEY` (or `api_key_env` override).

CrewAI Adapter Expectations
- `crewai_adapter.py` already uses `LLMConfig` to create the correct LLM instance or provider/model string.
- `base_url` should be passed through only for `provider == "local"` or when a custom endpoint is required.

Operational Notes
- If the repo prefers a separate, more human-friendly override file, keep JSON as the source of truth and allow YAML overrides in `config/archon-llm-bindings.yaml`.
- Ensure any future migration step does not change the existing `docs/archons-base.json` file so it remains a stable baseline.

Next Steps
1) Add load/merge option to `ArchonProfileAdapter` (JSON source + YAML override).
2) Add a small validation check in adapter logs to flag missing or malformed `llm_config` entries.
3) Re-run a CrewAI smoke test with `provider: local` and `base_url` to confirm Ollama binding is wired.
