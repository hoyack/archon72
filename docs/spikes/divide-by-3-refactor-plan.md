# Divide-By-3 Refactor Plan (Dynamic Archon Count)

## Goal
Make the system’s Archon count configurable (and divisible by 3 by policy), so runtime behavior is driven by configuration rather than hard-coded `72`. The configuration should be sourced from `docs/archons-base.json` today and be ready to switch to a database-backed source in the future.

## Scope
- Replace hard-coded `72` in runtime logic with a central, dynamic source of truth.
- Make counts derived from Archon profile data (JSON now, DB later).
- Update validation, thresholds, and computed ratios to use the dynamic count.
- Keep existing behavior when count remains 72.

## Non-Goals
- Changing constitutional policy wording in docs.
- Designing the entire DB schema or implementing the DB adapter now.
- Rewriting all docs that mention “72” for historical or conceptual reasons.

## Current Hard-Coded Hotspots (must be refactored)
Runtime enforcement and validation:
- `src/domain/events/cessation_deliberation.py` (REQUIRED_ARCHON_COUNT = 72)
- `src/application/services/final_deliberation_service.py` (exact 72 check)
- `src/domain/events/deliberation_recording_failed.py` (MAX_ARCHON_COUNT = 72)
- `src/api/models/observer.py` (min/max length 72; `le=72`)
- `src/domain/models/agent_pool.py` + `src/application/services/concurrent_deliberation_service.py` (MAX_CONCURRENT_AGENTS = 72)

Ratification/review math:
- `src/application/services/motion_review_service.py` (support ratio, abstentions, averages, quorum defaults)
- `src/domain/models/review_pipeline.py` (participation rate, ratio comments)

Session defaults / selection:
- `src/domain/models/conclave.py` (expected_participants default 72)
- `src/application/ports/archon_selector.py` (DEFAULT_MAX_ARCHONS = 72)

Tests and fixtures:
- `tests/chaos/cessation/test_cessation_chaos.py` (72-specific generator)
- `tests/chaos/cessation/test_edge_cases.py` (asserts for 72)
- `tests/load/test_conclave_async_load.py` (env default 72)

## Architecture Direction (Dynamic Configuration)

### 1) Centralize the Archon Count
Introduce a single source of truth that can be injected where needed.

Proposed interface:
- `ArchonCountProvider` (new, application layer)
  - `get_total_archons() -> int`
  - `get_required_archons_for_cessation() -> int` (defaults to total)

Implementations:
- `ProfileBasedArchonCountProvider` (reads from Archon profile repository)
- `StaticArchonCountProvider` (tests / local overrides)

### 2) Make Archon Profiles the Root Source
Today: `docs/archons-base.json` is canonical. Tomorrow: database.

Plan:
- Keep `ArchonProfileRepository` as the abstraction.
- Add a database-backed adapter later (read-only at first).
- `ArchonCountProvider` should use repository counts (e.g., `repository.count()`).

### 3) Configuration for “Divisible by 3”
Add a validation rule for the configured count:
- `total_archons % 3 == 0`
- If not, error early at startup (or fail health check).

## Proposed Refactor Steps

### Phase 0: Prep and Inventory
- Add a new spike checklist to track every `72` usage and classify as:
  - Runtime logic (must change)
  - Docs/branding (leave)
  - Example data (optional)
- Confirm which runtime paths *must* enforce exact count vs “at least” or “max”.

### Phase 1: Introduce ArchonCountProvider
- Create `src/application/ports/archon_count.py` (new).
- Add default provider in app wiring (likely in `src/api/startup.py` or the DI container).
- Provide a test stub provider for deterministic tests.

### Phase 2: Replace Hard-Coded 72 in Core Domain Paths
Refactor to use the provider or a derived constant:
- Cessation domain:
  - `REQUIRED_ARCHON_COUNT` should be injected or set at runtime.
  - Update `FinalDeliberationService` to validate against provider.
  - Update failure payload validation to use provider max.
- Concurrency:
  - Replace `MAX_CONCURRENT_AGENTS` with dynamic count.
  - Ensure semaphore and pool size use the same count source.

### Phase 3: Update Review/Ratification Math
Use dynamic count for:
- Support ratio denominators.
- Quorum and supermajority thresholds derived from `total_archons`.
- Abstention calculation: `total - yeas - nays - amends`.
- Average assignment metrics.

### Phase 4: Update API and DTO Validations
For Pydantic models:
- Replace `min_length=72` / `max_length=72` with `min_length=total_archons`.
- Replace `le=72` with `le=total_archons`.
Approach: use custom validators in response models that access injected config.

### Phase 5: Tests and Fixtures
- Update generators to accept `total_archons` and assert against it.
- Parameterize tests via provider or env var.
- Keep defaults at 72 to avoid massive test rewrites now.

### Phase 6: Prepare for Database-Backed Profiles
Define a minimal DB adapter contract:
- `archon_profiles` table (read-only)
  - `id`, `name`, `rank_level`, `branch`, `llm_config`, `system_prompt`, etc.
- Add a repository adapter stub that reads from DB (no writes).
- Document migration path for `docs/archons-base.json` -> DB.

## Edge Cases / Decisions Needed
- **Cessation requirement**: Should cessation require all active archons, or the configured total? (If DB allows disabled archons, define “active archons” vs “total”.)
- **Quorum math**: For odd counts, use `ceil(total/2)` or `floor(total/2)+1`?
- **Selection defaults**: `DEFAULT_MAX_ARCHONS` should become `provider.get_total_archons()`.
- **Compat**: Ensure archon name list used in review pipeline comes from repository, not hardcoded.

## Rollout Strategy
- Stepwise refactor with compatibility defaults to 72.
- Add a startup log: “archon_count=__” and validation of divisibility by 3.
- Add a health check metric: `configured_archon_count`.

## Acceptance Criteria
- Changing the archon count in config (JSON now, DB later) updates:
  - Concurrency limits
  - Cessation validation rules
  - Ratification thresholds and ratios
  - API schema validation
- All tests pass with default 72.
- System fails fast if count is not divisible by 3.

## Implementation Notes (Future Work)
- When DB is introduced, avoid duplication: JSON should be a seed, DB becomes canonical.
- Ensure caching of profile data; re-fetch only on reload or explicit refresh.
- Consider a “profile version” or “archon_count_version” for traceability.

## Wiring Points (Hexagonal Architecture)
Goal: keep domain pure, introduce new ports, and wire adapters at the composition root.

### New Port(s)
- `ArchonCountProvider` (application layer port)
  - Lives under `src/application/ports/`.
  - Consumed by application services and API models (via service layer), never by domain.

### Adapters
- **Config/Profile-backed adapter**:
  - Implement in `src/infrastructure/adapters/config/`.
  - Uses `ArchonProfileRepository.count()` to derive total archons.
  - No domain imports inside adapter (only ports / shared DTOs).
- **DB-backed adapter (future)**:
  - Implement in `src/infrastructure/adapters/db/`.
  - Conforms to `ArchonProfileRepository` and optionally a direct `ArchonCountProvider`.

### Composition Root (where to wire)
Use a single wiring location to bind ports to adapters:
- `src/api/startup.py` (or the existing DI module, if present).
- Construct `ArchonProfileRepository` first.
- Construct `ArchonCountProvider` using the repository.
- Inject provider into application services or route factories.

### Example Wiring Flow (Hexagonal)
1. **Infrastructure Adapter Selection**  
   - If DB configured → instantiate DB adapter for `ArchonProfileRepository`.  
   - Else → instantiate JSON adapter (`docs/archons-base.json`).

2. **Port Binding**  
   - `archon_profile_repository: ArchonProfileRepository = adapter`
   - `archon_count_provider: ArchonCountProvider = ProfileBasedArchonCountProvider(archon_profile_repository)`

3. **Application Service Construction**  
   - Services that need counts accept `ArchonCountProvider`.
   - Other services use repository directly for names/profiles.

4. **API Layer**  
   - Route handlers receive services via dependency injection.
   - Avoid using adapters directly in routes; depend on ports/services only.

### Domain Boundary Rules
- Domain models must not import `ArchonCountProvider` or repository ports.
- Domain constants should be replaced with parameters passed from services.
- Validation that depends on counts should live in application layer or
  at construction time of domain objects (via injected values).

### Suggested Injection Targets
- `FinalDeliberationService`: accept `ArchonCountProvider`.
- `ConcurrentDeliberationService`: accept a configured `AgentPool` size or provider.
- `MotionReviewService`: accept `ArchonCountProvider` (for ratios/quorum math).
- API response validators: use provider-driven validation via service layer helpers.

## `scripts/run_conclave.py` + CrewAI Adapter Alignment
The Conclave runner is a composition root and must follow hexagonal boundaries.

### Composition Root Responsibilities
- Instantiate **one** `ArchonProfileRepository` and reuse it everywhere:
  - `create_crewai_adapter(profile_repository=profile_repo, ...)`
  - `ArchonCountProvider(profile_repo)` for dynamic count
  - `ConclaveService(..., archon_profiles=..., config=...)`
- Derive `total_archons` from repository count (not a hard-coded 72).
- Ensure Conclave estimates and prints use `len(archon_profiles)` or provider count.

### CrewAI Instantiation Methodology (Consistency Rule)
All CrewAI usage should be isolated to **infrastructure adapters**:
- **Application layer** depends only on ports (never creates Crew/Agent/Task directly).
- **Adapter layer** creates CrewAI `Agent`, `Task`, and `Crew` objects.
- Use a shared factory or helper when possible to keep:
  - LLM config resolution consistent (via `crewai_llm_factory` + profile repo)
  - timeouts/retries consistent across adapters
  - structured JSON parsing helpers (e.g., `crewai_json_utils`)

Recommended alignment steps:
1. **Standardize adapter factories**
   - Ensure every CrewAI adapter accepts `profile_repository` (if applicable)
     and uses it as the canonical LLM config source.
2. **Unify Crew instantiation patterns**
   - Single-agent Crew for single-agent tasks (current pattern).
   - Use a small helper (e.g., `create_single_agent_crew(agent, task, verbose)`).
3. **Avoid script-level Crew usage**
   - `scripts/run_conclave.py` should only build adapters/services, never direct
     `Crew` / `Agent` / `Task` objects.
4. **Dynamic count awareness**
   - CrewAI adapters should log the active `archon_count` via repository.count()
     and respect `ArchonCountProvider` when selecting/restricting agents.

### Adapter Review Targets (for alignment)
- `src/infrastructure/adapters/external/crewai_adapter.py`
- `src/infrastructure/adapters/external/planner_crewai_adapter.py`
- `src/infrastructure/adapters/external/president_crewai_adapter.py`
- `src/infrastructure/adapters/external/reviewer_crewai_adapter.py`
- `src/infrastructure/adapters/external/secretary_crewai_adapter.py`
