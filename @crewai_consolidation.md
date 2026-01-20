# CrewAI Adapter Consolidation Plan

## Goal
Make CrewAI adapters consistent in LLM construction, JSON parsing, error handling, and configuration while preserving intentional differences (e.g., Secretary dual-model flow, Planner single-agent flow, Deliberation phase semantics). Improve reliability without changing external behavior unless explicitly desired.

## Inventory (Adapters and Role)
- `src/infrastructure/adapters/external/crewai_adapter.py`
  - Generic archon orchestration (AgentOrchestratorProtocol).
  - Uses `ArchonProfileRepository` + ToolRegistry.
- `src/infrastructure/adapters/external/crewai_deliberation_adapter.py`
  - Three‑Fates phase executor (PhaseExecutorProtocol).
  - Uses Archon profiles per phase.
- `src/infrastructure/adapters/external/reviewer_crewai_adapter.py`
  - Archon review + conflict detection + panel deliberation (ReviewerAgentProtocol).
  - Uses per‑archon LLM bindings.
- `src/infrastructure/adapters/external/planner_crewai_adapter.py`
  - Execution planning (ExecutionPlannerProtocol).
  - Dedicated planner agent (not Archons).
- `src/infrastructure/adapters/external/secretary_crewai_adapter.py`
  - Transcript extraction/validation/clustering/motion generation.
  - Dual‑model strategy: text model + JSON model.

## Usage Touchpoints
- Review pipeline: `scripts/run_review_pipeline.py` → `ReviewerCrewAIAdapter`.
- Execution planner: `scripts/run_execution_planner.py` → `PlannerCrewAIAdapter`.
- Conclave: `scripts/run_conclave.py` and `scripts/run_full_deliberation.py` → `CrewAIAdapter`.
- Secretary: `src/application/services/secretary_service.py` (LLM‑enhanced path) → `SecretaryCrewAIAdapter`.
- Motion consolidator: `src/application/services/motion_consolidator_service.py` uses CrewAI directly with secretary config (JSON model).

## Current Inconsistencies
1. **LLM construction diverges**
   - `crewai_adapter.py` returns **string** for cloud, **LLM object** for local.
   - `reviewer_crewai_adapter.py` and `planner_crewai_adapter.py` always return **LLM objects**.
   - `crewai_deliberation_adapter.py` builds LLMs inline and **does not honor** `base_url` / `OLLAMA_HOST`.
   - `secretary_crewai_adapter.py` uses a separate LLM factory and **dual models**.

2. **Base URL handling differs**
   - Some adapters use per‑archon `base_url` then `OLLAMA_HOST` fallback.
   - Deliberation adapter ignores both.

3. **JSON parsing duplication**
   - Planner and Reviewer implement similar parsing/sanitization.
   - Secretary has more aggressive sanitization + truncation checks.
   - No shared utilities or consistent error strategy.

4. **Config sources and fallbacks vary**
   - Reviewer uses per‑archon config; planner uses dedicated config or fallback model string.
   - Secretary uses its own profile with two model configs.
   - Deliberation uses profiles but a custom inlined LLM creation.

5. **Tooling behavior is not shared**
   - Only `crewai_adapter.py` integrates `ToolRegistryProtocol`.

## Intentional Differences (Keep)
- **Secretary dual‑model**: text + JSON separation is to reduce hallucinated structure, keep extraction high‑quality, and produce structured outputs with more deterministic formatting.
- **Planner dedicated agent**: planner is not an Archon persona; it needs a focused, stable role prompt and a single LLM.
- **Deliberation phase orchestration**: the phase sequencing and concurrency model is specific to the Three‑Fates protocol.

## Consolidation Plan

## To-Do List

### Task Group 1: Shared LLM Factory
1. Define shared `crewai_llm_factory.py` with standardized provider mapping, base_url resolution, and logging.
2. Update `crewai_adapter.py` to use the shared LLM factory.
3. Update `crewai_deliberation_adapter.py` to use the shared LLM factory (respect base_url/OLLAMA_HOST).
4. Update `reviewer_crewai_adapter.py` to use the shared LLM factory.
5. Update `planner_crewai_adapter.py` to use the shared LLM factory and consistent defaults.
6. Update `secretary_crewai_adapter.py` to use the shared LLM factory for both models.
7. Update `motion_consolidator_service.py` to use the shared LLM factory.

### Task Group 2: Shared JSON Parsing Utilities
1. Define `crewai_json_utils.py` with common sanitization and parsing helpers.
2. Update `reviewer_crewai_adapter.py` to use shared parsing utilities.
3. Update `planner_crewai_adapter.py` to use shared parsing utilities.
4. Update `secretary_crewai_adapter.py` to use shared parsing utilities with aggressive fallback retained.

### Task Group 3: Logging and Error Consistency
1. Standardize LLM initialization logs across adapters.
2. Standardize JSON parse error logs with adapter + archon/planner context.
3. Add shared retry hooks or document per-adapter retry behavior.

### Task Group 4: Validation and Safety Checks
1. Run review pipeline with `--real-agent` and confirm vote variance.
2. Run execution planner with `--real-agent`.
3. Run conclave quick run to confirm deliberation adapter works.
4. Spot-check secretary JSON outputs and checkpoints.

### Phase 1: Shared LLM Factory
Create `src/infrastructure/adapters/external/crewai_llm_factory.py`:
- `create_crewai_llm(llm_config: LLMConfig) -> LLM | str`
- Normalize provider mapping and `base_url` logic (per‑archon `base_url`, then `OLLAMA_HOST`, then default).
- Standardize for local vs cloud behavior (decide whether to always return LLM object or return strings). Recommended: **always return LLM objects** for consistency and logging.
- Include logging hooks (`model`, `base_url`, `temperature`, `max_tokens`, `provider`).

### Phase 2: Shared JSON Parsing Utilities
Create `src/infrastructure/adapters/external/crewai_json_utils.py`:
- `sanitize_json_string()` for control chars.
- `parse_json_response()` with consistent markdown stripping + trailing comma fix.
- Optional `aggressive_clean()` and `is_truncated()` from Secretary, gated behind a `strict=False` flag.

### Phase 3: Adapter Alignment
Update each adapter to use the shared factory + parser:
- `crewai_adapter.py`: replace `_create_crewai_llm` with factory.
- `reviewer_crewai_adapter.py`: replace `_create_llm_for_config`, `_parse_json_response`.
- `planner_crewai_adapter.py`: replace `_create_crewai_llm`, `_parse_json_response`.
- `crewai_deliberation_adapter.py`: use factory and honor `base_url`/`OLLAMA_HOST`.
- `secretary_crewai_adapter.py`: keep dual‑model strategy but use factory and JSON utils (keep aggressive cleanup path for JSON mode).
- `motion_consolidator_service.py`: use factory with secretary JSON config to avoid a second LLM construction path.

### Phase 4: Output/Telemetry Consistency
- Add a standard log schema for LLM init + invocation errors across adapters.
- Consider writing a shared retry policy for transient LLM failures (configurable per adapter).

## Risks and Mitigations
- **Behavior drift**: changing LLM instantiation might affect response format.
  - Mitigation: run integration checks on review pipeline and planner after changes.
- **Secretary JSON strictness**: moving to shared JSON parsing might reduce resilience.
  - Mitigation: keep Secretary’s aggressive fallback for JSON responses only.
- **Deliberation latency**: changes to LLM setup should keep timeouts/async handling intact.

## Implementation Notes
- Consolidation should be incremental: introduce factory/util first, then update adapters one by one.
- Keep environment variable behavior stable (`OLLAMA_HOST`).
- Preserve existing defaults (planner default model string) unless explicitly changed.

## Validation Plan (manual)
- Run `scripts/run_review_pipeline.py --real-agent` with live LLMs.
- Run `scripts/run_execution_planner.py --real-agent`.
- Run a conclave quick test (`scripts/run_conclave.py --quick`) to ensure deliberation adapter still works.
- Verify Secretary checkpointing and JSON output remains valid.

## Open Questions
- Should all adapters return CrewAI `LLM` objects (recommended) or keep string for cloud providers (current in `crewai_adapter.py`)?
- Should AMEND in review responses influence ratification counts (current is abstain)?
- Do we want a single global JSON strictness mode or per‑adapter modes?
