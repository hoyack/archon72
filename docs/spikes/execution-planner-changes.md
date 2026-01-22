# Execution Planner LLM Config Alignment Spike

**Spike ID:** SPIKE-EP-LLM-ALIGN
**Date:** 2026-01-20
**Status:** IMPLEMENTED (PENDING REVIEW)
**Author:** Development Agent

---

## Executive Summary

The Execution Planner was hard-coded to a legacy local model (`ollama/qwen3:latest`) and ignored the canonical LLM profile source (`docs/archons-base.json`). This caused failures when model names were remapped. We aligned the planner adapter with the existing CrewAI profile pipeline so it resolves its LLM configuration from Archon profiles (with a clear fallback path) and only uses legacy overrides when explicitly provided.

## Why This Change Is Needed

- The planner failed with a missing model error because it used a hard-coded model string that no longer exists.
- Other stages already resolve LLMs through the Archon profile repository and `docs/archons-base.json`.
- A single source of truth for LLM bindings is required to avoid drift across pipelines.

## Current Behavior (Before)

- Planner adapter defaulted to `ollama/qwen3:latest`.
- Base URL defaulted to `OLLAMA_HOST` if set, otherwise localhost.
- No integration with `docs/archons-base.json` or per-profile LLM bindings.

## Desired Behavior (After)

- Planner resolves LLM configuration from Archon profiles in `docs/archons-base.json`.
- Uses the standard CrewAI LLM construction logic (provider mapping, base_url).
- Allows explicit overrides (model/base_url/LLMConfig) when needed.
- Falls back deterministically if no explicit configuration is provided.

## Scope

### In Scope
- Planner adapter alignment with Archon profile LLM configuration.
- Deterministic fallback strategy when no explicit config is provided.
- Consistent CrewAI LLM construction for local and cloud providers.

### Out of Scope
- Changing the Archon profile schema.
- Modifying other pipeline stages or scripts (unless needed for compatibility).

## Proposed Approach

1. Add support for an `LLMConfig` object to the planner adapter.
2. Resolve planner LLM config from `docs/archons-base.json` via the Archon profile repository.
3. Use the same CrewAI LLM creation pattern as other adapters (provider mapping, base_url, tokens).
4. Keep explicit overrides available for ad-hoc runs.
5. Introduce role-based Archon ID overrides via `.env` for scripts that currently use default models.

## Role-Based LLM Overrides (Planned)

### Rationale

Some scripts instantiate single-role agents with default model bindings. To avoid drift and allow dynamic model selection without code changes, we will bind each role to a specific Archon ID via environment variables. The script will resolve the Archon profile and use its LLM config as the source of truth.

### Proposed Env Vars (to add to `.env` and `.env.example`)

```
EXECUTION_PLANNER_ARCHON_ID=
SECRETARY_TEXT_ARCHON_ID=
SECRETARY_JSON_ARCHON_ID=
```

### Resolution Rules

1. If the role-specific env var is set, load that Archon profile and use its `llm_config`.
2. If not set, fall back to existing YAML config for that role (if applicable).
3. If YAML is missing, fall back to current defaults.

### Role-Based Scripts Affected

- `scripts/run_execution_planner.py` (planner role)
- `scripts/run_secretary.py` (secretary text + secretary json roles)

### Role-Based Scripts Not Affected

- `scripts/run_conclave.py` (not role-based; uses full profile repository)

### Notes

- `scripts/run_review_pipeline.py` uses the full Archon roster; it does not map to a single role-based Archon ID.
- The env var approach allows dynamic Archon selection per run without editing YAML or JSON.

## Implementation Tasks

1. Add `LLMConfig` support to `PlannerCrewAIAdapter` constructor.
2. Implement `_resolve_planner_llm_config()` using the Archon profile repository.
3. Add shared helper functions for CrewAI LLM string/model creation.
4. Update `create_planner_agent()` to use profile-backed config with override support.
5. Log resolved model/base_url for traceability.
6. Add role-based Archon ID env lookups in role-based scripts.
7. Extend secretary config loading to accept Archon ID overrides for text/json roles.
8. Update `.env.example` with new role-based Archon ID variables.
9. Add minimal validation/logging for missing/invalid Archon IDs.

## Acceptance Criteria

- Execution Planner runs with `--real-agent` without missing-model errors.
- Planner adapter logs show model/base_url resolved from `docs/archons-base.json`.
- Explicit overrides still work (model/base_url or explicit LLMConfig).
- Role-based scripts honor Archon ID overrides from `.env`.

## Validation Plan

- Run: `python scripts/run_execution_planner.py --real-agent <review_output_dir>`
- Verify in logs:
  - `planner_adapter_initialized` uses a model present in `docs/archons-base.json`.
  - No `model not found` errors from Ollama.
- Confirm results saved under `_bmad-output/execution-planner/<session_id>`.
- Run: `python scripts/run_secretary.py <transcript> --enhanced`
  - Verify logs indicate the selected Archon IDs for text/json roles.

## Risks and Mitigations

- **Risk:** Chosen fallback profile uses a model not present on the local server.
  - **Mitigation:** Ensure `docs/archons-base.json` profiles match deployed model inventory.
- **Risk:** Mixed provider types (cloud/local) require different initialization patterns.
  - **Mitigation:** Use consistent CrewAI LLM creation logic for all providers.
- **Risk:** Env var override points to unknown Archon ID.
  - **Mitigation:** Warn and fall back to existing YAML/default behavior.

## Rollout Notes

- Change is additive and local to the planner adapter.
- No impact on `scripts/run_conclave.py` or other stages unless they import planner adapter.
- Consider adding a future CLI option for choosing the planner profile explicitly.
