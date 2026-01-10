# Story 10.3: Tool Registry for Archons

Status: done

## Story

As a **system integrator**,
I want a **tool registry that maps tool names to CrewAI Tool instances**,
so that **archons can invoke domain-specific tools during deliberation based on their suggested_tools configuration**.

## Acceptance Criteria

1. **AC1: ToolRegistry port interface defined** - A `ToolRegistry` protocol/ABC in `src/application/ports/` defines the interface for tool registration and lookup.

2. **AC2: All 9 archon tools implemented** - Tool implementations exist for all 9 tool types found in archons-base.csv:
   - `insight_tool` - Analytical capabilities for pattern recognition and insight generation
   - `communication_tool` - Inter-agent communication and messaging capabilities
   - `disruption_tool` - Challenge assumptions and introduce alternative viewpoints
   - `knowledge_retrieval_tool` - Access to knowledge bases and information retrieval
   - `creation_tool` - Content generation and creative output capabilities
   - `transaction_tool` - Transaction handling and workflow management
   - `relationship_tool` - Relationship mapping and social network analysis
   - `logistics_tool` - Resource allocation and coordination capabilities
   - `wellness_tool` - Agent health monitoring and self-assessment

3. **AC3: CrewAI BaseTool subclass pattern** - Each tool inherits from CrewAI's `BaseTool` with proper `name`, `description`, and `_run` method implementation.

4. **AC4: CrewAIAdapter integration** - The `CrewAIAdapter` uses `ToolRegistry` to resolve `suggested_tools` from `ArchonProfile` to actual `Tool` instances.

5. **AC5: Stub implementations for development** - Initial tool implementations are stubs that log invocation and return placeholder responses (real implementations in future stories).

6. **AC6: Unit tests for tool registry** - Unit tests verify tool registration, lookup, and CrewAI integration patterns.

## Tasks / Subtasks

- [ ] **Task 1: Create ToolRegistry port interface** (AC: 1)
  - [ ] Define `ToolRegistryProtocol` ABC in `src/application/ports/tool_registry.py`
  - [ ] Methods: `get_tool(name: str) -> Tool | None`, `get_tools(names: list[str]) -> list[Tool]`, `list_tools() -> list[str]`, `register_tool(name: str, tool: Tool) -> None`
  - [ ] Include docstrings with constitutional constraints (CT-11: no silent failures)

- [ ] **Task 2: Implement stub tools** (AC: 2, 3, 5)
  - [ ] Create `src/infrastructure/adapters/tools/__init__.py`
  - [ ] Create `src/infrastructure/adapters/tools/archon_tools.py` with 9 tool classes
  - [ ] Each tool: subclass `BaseTool`, implement `_run`, return stub response with tool name and input logged
  - [ ] Use Pydantic `args_schema` for input validation where appropriate

- [ ] **Task 3: Implement ToolRegistry adapter** (AC: 1, 2)
  - [ ] Create `src/infrastructure/adapters/tools/tool_registry_adapter.py`
  - [ ] Implement `ToolRegistryProtocol` with in-memory dict storage
  - [ ] Factory function `create_tool_registry()` pre-registers all 9 archon tools
  - [ ] Log tool registration and lookup for observability

- [ ] **Task 4: Integrate with CrewAIAdapter** (AC: 4)
  - [ ] Update `CrewAIAdapter.__init__` to accept `ToolRegistry` instead of `dict[str, Any]`
  - [ ] Update `_create_crewai_agent` to resolve tools via registry
  - [ ] Update factory function `create_crewai_adapter` to create registry if not provided

- [ ] **Task 5: Write unit tests** (AC: 6)
  - [ ] Test `ToolRegistryProtocol` compliance
  - [ ] Test each tool's `_run` method returns expected stub response
  - [ ] Test `get_tool` returns None for unknown tools
  - [ ] Test `get_tools` handles mixed valid/invalid names
  - [ ] Test CrewAI integration (tool assignment to Agent)

## Dev Notes

### Architecture Patterns

**Port-Adapter Pattern:**
- Port: `src/application/ports/tool_registry.py` - defines abstract interface
- Adapter: `src/infrastructure/adapters/tools/tool_registry_adapter.py` - concrete implementation
- This follows the hexagonal architecture established in Epic 0 (Story 0-2)

**CrewAI Tool Pattern:**
```python
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

class InsightToolInput(BaseModel):
    query: str = Field(..., description="The query to analyze")

class InsightTool(BaseTool):
    name: str = "insight_tool"
    description: str = "Analyze patterns and generate insights"
    args_schema: type[BaseModel] = InsightToolInput

    def _run(self, query: str) -> str:
        # Stub implementation
        return f"[STUB] Insight analysis for: {query}"
```

**Constitutional Constraints:**
- CT-11: Silent failure destroys legitimacy - tools MUST log all invocations and errors
- CT-12: Witnessing creates accountability - tool outputs may flow through FR9 pipeline
- NFR5: 72 concurrent agents - tools must be stateless and thread-safe

### Source Tree Components

```
src/
├── application/
│   └── ports/
│       └── tool_registry.py          # NEW: Port interface
└── infrastructure/
    └── adapters/
        ├── tools/                      # NEW: Tools directory
        │   ├── __init__.py
        │   ├── archon_tools.py        # 9 tool implementations
        │   └── tool_registry_adapter.py
        └── external/
            └── crewai_adapter.py      # UPDATE: Use ToolRegistry

tests/
└── unit/
    └── infrastructure/
        └── adapters/
            └── tools/                  # NEW: Tool tests
                ├── __init__.py
                ├── test_archon_tools.py
                └── test_tool_registry.py
```

### Testing Standards

- Follow pytest patterns from existing tests (e.g., `tests/unit/infrastructure/adapters/external/test_crewai_adapter.py`)
- Use `@pytest.fixture` for tool registry setup
- Mock CrewAI Tool base class behavior where needed
- Minimum coverage: all 9 tools have at least one test each

### Project Structure Notes

- Tools directory mirrors the `external/` adapter structure
- Import paths must comply with import-linter contracts (domain layer purity)
- Tools are infrastructure concerns, not domain models

### Dependencies

- `crewai>=0.80.0` already in pyproject.toml
- `crewai.tools.BaseTool` for tool base class
- `pydantic.BaseModel` for input schemas (already available via crewai dependency)

### References

- [Source: _bmad-output/planning-artifacts/archon-profile-system-spec.md#Usage Examples] - ArchonProfile.suggested_tools usage
- [Source: src/infrastructure/adapters/external/crewai_adapter.py:195-206] - Current tool_registry placeholder implementation
- [Source: docs/archons-base.csv] - 9 unique tool names in suggested_tools column
- [Source: _bmad-output/planning-artifacts/architecture.md#Port-and-Adapter Pattern] - Hexagonal architecture guidance
- [External: https://docs.crewai.com/en/learn/create-custom-tools] - CrewAI custom tool documentation

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

None

### Completion Notes List

- Fixed import path: `BaseTool` is in `crewai_tools`, not `crewai.tools`
- Updated existing CrewAIAdapter tests to use mock `ToolRegistryProtocol` instead of dict
- All 83 tests passing (54 new + 29 existing)

### File List

**New Files Created:**
- `src/application/ports/tool_registry.py` - ToolRegistryProtocol port interface
- `src/infrastructure/adapters/tools/__init__.py` - Tools module init
- `src/infrastructure/adapters/tools/archon_tools.py` - 9 stub tool implementations
- `src/infrastructure/adapters/tools/tool_registry_adapter.py` - ToolRegistryAdapter
- `tests/unit/infrastructure/adapters/tools/__init__.py` - Tests module init
- `tests/unit/infrastructure/adapters/tools/test_archon_tools.py` - 32 tool tests
- `tests/unit/infrastructure/adapters/tools/test_tool_registry.py` - 22 registry tests

**Modified Files:**
- `src/application/ports/__init__.py` - Added ToolRegistryProtocol export
- `src/infrastructure/adapters/external/crewai_adapter.py` - Updated to use ToolRegistryProtocol
- `tests/unit/infrastructure/adapters/external/test_crewai_adapter.py` - Updated 2 tests for new interface
