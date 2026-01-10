# Story 10.4: Archon Selection Service

Status: done

## Story

As a **deliberation coordinator**,
I want a **service that selects relevant archons for a deliberation based on topic characteristics**,
so that **the most appropriate archons participate in each deliberation, leveraging their unique domains, focus areas, and capabilities**.

## Acceptance Criteria

1. **AC1: ArchonSelectionService port interface defined** - A `ArchonSelectorProtocol` ABC in `src/application/ports/` defines the interface for archon selection based on topic matching.

2. **AC2: Topic-to-archon matching algorithm** - The service matches topics to archons using:
   - `suggested_tools` - Archons with relevant tools for the topic
   - `domain` - Archons with matching domain expertise (from attributes)
   - `focus_areas` - Archons with relevant focus areas (from attributes)
   - `capabilities` - Archons with required capabilities (from attributes)

3. **AC3: Selection modes** - Service supports multiple selection modes:
   - `all` - All 72 archons participate (for general deliberations)
   - `relevant` - Only archons matching topic criteria participate
   - `weighted` - All participate but matching archons have priority ordering

4. **AC4: Configurable selection limits** - Service accepts `min_archons` and `max_archons` parameters to constrain selection size.

5. **AC5: Executive inclusion guarantee** - Option to always include at least one executive director (King-rank) in selection for leadership perspective.

6. **AC6: Selection audit trail** - Service returns selection metadata explaining why each archon was selected (matching criteria).

7. **AC7: Unit tests for selection logic** - Comprehensive tests for all selection modes, edge cases, and matching algorithms.

## Tasks / Subtasks

- [x] **Task 1: Create ArchonSelectorProtocol port interface** (AC: 1, 3, 4)
  - [x] Define `ArchonSelectorProtocol` ABC in `src/application/ports/archon_selector.py`
  - [x] Methods: `select(topic: TopicContext, mode: SelectionMode, ...) -> ArchonSelection`
  - [x] Define `TopicContext` dataclass with topic content, keywords, required_tools, domain hints
  - [x] Define `SelectionMode` enum: ALL, RELEVANT, WEIGHTED
  - [x] Define `ArchonSelection` dataclass with selected archons and selection metadata

- [x] **Task 2: Implement topic analysis utilities** (AC: 2)
  - [x] Create keyword extraction from topic content (simple text matching)
  - [x] Create tool requirement inference from topic (rule-based initially)
  - [x] Create domain classification from topic (pattern matching)

- [x] **Task 3: Implement ArchonSelectionService adapter** (AC: 2, 3, 4, 5, 6)
  - [x] Create `src/infrastructure/adapters/selection/archon_selector_adapter.py`
  - [x] Implement `ArchonSelectorProtocol` using `ArchonProfileRepository`
  - [x] Score archons based on: tool match, domain match, focus area match, capability match
  - [x] Implement ALL mode - return all 72 archons
  - [x] Implement RELEVANT mode - return only archons with score > threshold
  - [x] Implement WEIGHTED mode - return all archons sorted by relevance score
  - [x] Enforce min/max limits with intelligent overflow handling
  - [x] Include executive guarantee logic

- [x] **Task 4: Implement selection metadata** (AC: 6)
  - [x] Track why each archon was selected (matching criteria)
  - [x] Include relevance score breakdown in metadata
  - [x] Return selection timestamp and mode used

- [x] **Task 5: Write unit tests** (AC: 7)
  - [x] Test ALL mode returns all archons (tested with 4 archons)
  - [x] Test RELEVANT mode filters appropriately
  - [x] Test WEIGHTED mode ordering by score
  - [x] Test min/max constraints work correctly
  - [x] Test executive inclusion guarantee
  - [x] Test edge case: no archons match criteria (high threshold)
  - [x] Test edge case: all archons match criteria (ALL mode)

## Dev Notes

### Architecture Patterns

**Port-Adapter Pattern:**
- Port: `src/application/ports/archon_selector.py` - defines abstract interface
- Adapter: `src/infrastructure/adapters/selection/archon_selector_adapter.py` - concrete implementation
- Follows hexagonal architecture established in Epic 0

**Scoring Algorithm:**
```python
def calculate_relevance_score(profile: ArchonProfile, topic: TopicContext) -> float:
    score = 0.0

    # Tool match (highest weight - explicit capability)
    for tool in topic.required_tools:
        if tool in profile.suggested_tools:
            score += 0.4

    # Domain match (medium weight)
    if profile.domain and topic.domain_hint:
        if profile.domain.lower() in topic.domain_hint.lower():
            score += 0.25

    # Focus area match (medium weight)
    if profile.focus_areas and topic.keywords:
        for keyword in topic.keywords:
            if keyword.lower() in profile.focus_areas.lower():
                score += 0.15

    # Capability match (lower weight)
    if profile.capabilities and topic.required_capabilities:
        for cap in topic.required_capabilities:
            if cap.lower() in profile.capabilities.lower():
                score += 0.1

    return min(score, 1.0)  # Cap at 1.0
```

**Constitutional Constraints:**
- FR10: 72 agents can deliberate concurrently - selection must work efficiently for full roster
- NFR5: No performance degradation - scoring algorithm must be O(n) for 72 archons
- CT-11: Silent failure destroys legitimacy - log all selection decisions

### Source Tree Components

```
src/
├── application/
│   └── ports/
│       └── archon_selector.py         # NEW: Port interface
└── infrastructure/
    └── adapters/
        └── selection/                  # NEW: Selection directory
            ├── __init__.py
            └── archon_selector_adapter.py

tests/
└── unit/
    └── infrastructure/
        └── adapters/
            └── selection/              # NEW: Selection tests
                ├── __init__.py
                └── test_archon_selector.py
```

### Data Classes

```python
@dataclass(frozen=True)
class TopicContext:
    topic_id: str
    content: str
    keywords: list[str]
    required_tools: list[str]
    domain_hint: str | None
    required_capabilities: list[str]

class SelectionMode(Enum):
    ALL = "all"
    RELEVANT = "relevant"
    WEIGHTED = "weighted"

@dataclass(frozen=True)
class ArchonSelectionMetadata:
    archon_id: UUID
    archon_name: str
    relevance_score: float
    matched_tools: list[str]
    matched_domain: bool
    matched_focus: bool
    matched_capabilities: list[str]

@dataclass(frozen=True)
class ArchonSelection:
    archons: list[ArchonProfile]
    metadata: list[ArchonSelectionMetadata]
    mode: SelectionMode
    selected_at: datetime
    total_candidates: int
    min_requested: int
    max_requested: int
```

### Testing Standards

- Follow pytest patterns from existing tests
- Use `@pytest.fixture` for mock ArchonProfileRepository with varied profiles
- Test with controlled archon data (not full 72) for predictable assertions
- Minimum: one test per selection mode, plus edge cases

### Project Structure Notes

- Selection adapters separate from external adapters (different concern)
- Uses ArchonProfileRepository port - does not depend on concrete adapter
- Import paths comply with import-linter contracts

### References

- [Source: src/domain/models/archon_profile.py:108-120] - domain, focus_areas, capabilities properties
- [Source: src/application/ports/archon_profile_repository.py] - get_by_tool, get_all methods
- [Source: _bmad-output/planning-artifacts/archon-profile-system-spec.md#Filter by Tool] - Example usage
- [Source: _bmad-output/planning-artifacts/architecture.md#Concurrent Agent Execution] - 72 agent scalability requirements

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

- Initial test run: 30 passed, 1 failed (min/max validation edge case)
- Fixed test to pass min_archons=0 with max_archons=0
- Final test run: 31 passed

### Completion Notes List

1. Created `ArchonSelectorProtocol` ABC with `TopicContext`, `SelectionMode`, `ArchonSelectionMetadata`, and `ArchonSelection` dataclasses
2. Implemented scoring algorithm with configurable weights: tool (0.4), domain (0.25), focus area (0.15), capability (0.1)
3. Implemented three selection modes: ALL, RELEVANT (with threshold), WEIGHTED (sorted by relevance)
4. Added executive inclusion guarantee with automatic insertion at appropriate relevance position
5. Comprehensive unit test suite covering all acceptance criteria

### File List

**Created:**
- `src/application/ports/archon_selector.py` - Port interface with protocol, dataclasses, and constants
- `src/infrastructure/adapters/selection/__init__.py` - Package exports
- `src/infrastructure/adapters/selection/archon_selector_adapter.py` - Adapter implementation
- `tests/unit/infrastructure/adapters/selection/__init__.py` - Test package
- `tests/unit/infrastructure/adapters/selection/test_archon_selector.py` - 31 unit tests

**Modified:**
- `src/application/ports/__init__.py` - Added archon_selector exports
