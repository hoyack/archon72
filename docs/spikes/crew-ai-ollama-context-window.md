# CrewAI + Ollama (Cloud) Context Window Notes

This document captures how context size and token limits work in this repo, what is configurable today via `docs/archons-base.json`, and what small plumbing changes would unlock larger *context windows* (not just larger outputs) when using Ollama Cloud through CrewAI/LiteLLM.

## Terminology (important)

- **Context window**: how much text the model can *read* (prompt + history). For Ollama this is typically controlled by `num_ctx`.
- **Output tokens**: how much text the model can *write back* (completion). In this repo this is configured as `llm_config.max_tokens` and (via LiteLLM->Ollama) maps to `num_predict`.

Raising `max_tokens` does **not** increase the context window; it only allows longer outputs.

## Current State In This Repo

### Where per-Archon limits live

- `docs/archons-base.json` includes `llm_config` for **all 72 Archons** (provider/model/temperature/max_tokens/timeout/base_url).
- `config/archon-llm-bindings.yaml` exists, but in practice `docs/archons-base.json` already has per-archon `llm_config`, so JSON is the main source of truth for these runs.

### What is currently configurable (JSON-only)

- You can change **output length** per Archon via:
  - `docs/archons-base.json` -> `archons[].llm_config.max_tokens`
- Observed distribution (Jan 2026 snapshot):
  - min `max_tokens`: ~1900
  - max `max_tokens`: 20000
  - majority are in the ~2k-4k band

### What is NOT currently configurable (without code)

There is **no** way today to set an Ollama context window (`num_ctx`) per Archon because:
- `src/domain/models/llm_config.py` has no `num_ctx` (or general "extra params") field.
- `src/infrastructure/adapters/config/archon_profile_adapter.py` only deserializes the known LLMConfig fields.
- `src/application/llm/crewai_llm_factory.py` only passes `temperature`, `max_tokens`, and (optionally) `base_url`/`api_key` into `crewai.LLM(...)`.

So the effective context window comes from **Ollama Cloud defaults** (or server-side model defaults).

## How Requests Flow (where context gets spent)

High-level path:

1. Conclave builds a big prompt (motion text + digests + recent contributions).
2. `src/infrastructure/adapters/external/crewai_adapter.py` creates a CrewAI `Agent` and `Task`.
3. `src/application/llm/crewai_llm_factory.py` builds `crewai.LLM(...)` (LiteLLM-backed).
4. LiteLLM sends an Ollama-style request. For Ollama:
   - `max_tokens` becomes `num_predict` (output tokens).
   - `num_ctx` *could* be passed (context window), but we currently don't.

### Biggest current "free context" win: prompt duplication

Today we effectively send the full topic content twice:

- `CrewAIAdapter._create_crewai_agent()` injects the topic into the agent backstory via `ArchonProfile.get_system_prompt_with_context(...)`.
- `CrewAIAdapter._create_task()` also includes the full `context.topic_content` again in the task description.

Removing that duplication increases *effective usable context* without changing any model limits.

Files:
- `src/infrastructure/adapters/external/crewai_adapter.py`
  - context injected into backstory in `_create_crewai_agent(...)`
  - context included again in `_create_task(...)`

## Ollama Cloud: What We Know About Context Size

CrewAI's own model-context mapping is incomplete for many "ollama/*" model strings, but LiteLLM does have max token hints for at least some of our models:

- `ollama/gpt-oss:120b-cloud`: `max_input_tokens=131072`
- `ollama/deepseek-v3.1:671b-cloud`: `max_input_tokens=163840`

Many of the other cloud model strings in `docs/archons-base.json` are not mapped in the current LiteLLM `model_cost` table, so we should assume "unknown until tested" for those.

## Options To Increase Context Window

### Option 1 (no-code): reduce prompt size / duplication

Best immediate levers without changing any model settings:
- Remove duplicate inclusion of `context.topic_content` (backstory + task) in the CrewAI adapter.
- Keep Conclave prompts compact:
  - Conclave already uses debate digests + truncated recent entries; keep those truncations tight.
  - Avoid embedding huge boilerplate in motions unless the test requires it.

This does not increase the theoretical model window, but increases the *available* budget for the useful parts of the prompt.

### Option 2 (code): support `num_ctx` end-to-end

Minimal plumbing plan:

1. Extend `src/domain/models/llm_config.py` with an optional field:
   - either `num_ctx: int | None = None`
   - or a generic `extra_params: dict[str, object] = field(default_factory=dict)`
2. Extend `src/infrastructure/adapters/config/archon_profile_adapter.py` to deserialize it from:
   - `docs/archons-base.json` `llm_config` blocks and/or YAML overrides
3. Pass it through in `src/application/llm/crewai_llm_factory.py`:
   - when using Ollama (`provider in {"local","ollama_cloud"}`), include `num_ctx=<value>` in `LLM(...)` kwargs.

Why this works:
- LiteLLM's Ollama adapter supports `num_ctx`.
- CrewAI's `LLM` forwards unknown kwargs to LiteLLM.

### Option 3 (code): global env override (useful for experiments)

Instead of encoding `num_ctx` per-archon, add an env override (repo-defined) like:
- `OLLAMA_NUM_CTX=32768`

Then `create_crewai_llm(...)` can inject `num_ctx` for all Ollama-backed models during tests.

## Testing Strategy (recommended)

1. **Measure baseline prompt sizes**
   - Pick a representative debate prompt and vote prompt and estimate token size (or at least character size).
2. **Turn on larger context window (if implemented)**
   - Start with something moderate (e.g., `num_ctx=16384`), then step up.
3. **Confirm stability under concurrency**
   - Larger `num_ctx` often increases latency/memory pressure; combined with 72 agents, this can increase timeouts and "empty response" events.
   - Keep an eye on `OLLAMA_MAX_CONCURRENT` and retry settings in `src/infrastructure/adapters/external/crewai_adapter.py`.
4. **Regression check**
   - Ensure vote parsing stays stable (short, clean JSON line first).

## Practical Guidance

- If the goal is "Archons see more debate history", increasing `num_ctx` helps, but so does:
  - eliminating duplicate prompt injection
  - improving compaction (Secretary digests) and keeping entry previews short
- If the goal is "Archons write more", increase `max_tokens`, but be aware:
  - longer outputs increase the chance of protocol violations (especially in vote mode)
  - longer outputs cost more time and can amplify empty-response / timeout behavior

