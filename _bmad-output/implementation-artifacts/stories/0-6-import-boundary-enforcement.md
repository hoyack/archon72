# Story 0.6: Import Boundary Enforcement

Status: done

## Story

As a **developer**,
I want pre-commit hooks that reject cross-layer imports,
So that architectural boundaries are enforced automatically.

## Acceptance Criteria

### AC1: Pre-commit Configuration Installed

**Given** a pre-commit configuration
**When** I run `pre-commit install`
**Then** hooks are installed for:
  - Import boundary checking
  - Python formatting (black)
  - Linting (ruff)
  - Type checking (mypy)

### AC2: Domain Layer Import Violation Detected

**Given** a file in `src/domain/` that imports from `src/infrastructure/`
**When** I attempt to commit
**Then** the commit is rejected
**And** error message explains: "Domain layer cannot import from infrastructure"

### AC3: Allowed Import Direction Passes

**Given** a file in `src/application/` that imports from `src/domain/`
**When** I attempt to commit
**Then** the commit succeeds (allowed import direction)

### AC4: Standalone Import Check Script

**Given** the import boundary rules
**When** I run `scripts/check_imports.py`
**Then** it scans all Python files in `src/`
**And** reports any violations with file:line references
**And** exits with code 1 if violations found
**And** exits with code 0 if no violations

## Tasks / Subtasks

- [x] Task 1: Create import boundary checking script (AC: 4)
  - [x] 1.1 Create `scripts/check_imports.py` using AST-based import analysis
  - [x] 1.2 Define hexagonal layer hierarchy rules (domain < application < infrastructure < api)
  - [x] 1.3 Implement file scanning with violation detection
  - [x] 1.4 Output violations with file:line format
  - [x] 1.5 Return appropriate exit codes (0 = pass, 1 = fail)
  - [x] 1.6 Add unit tests for the import checker in `tests/unit/test_import_boundary.py`

- [x] Task 2: Add pre-commit configuration (AC: 1)
  - [x] 2.1 Add `pre-commit` to dev dependencies in pyproject.toml
  - [x] 2.2 Create `.pre-commit-config.yaml` with hooks:
    - black (formatting)
    - ruff (linting)
    - mypy (type checking)
    - local check_imports.py script
  - [x] 2.3 Run `poetry lock && poetry install` (documented, not executed due to poetry version)
  - [x] 2.4 Document `pre-commit install` in README or Makefile

- [x] Task 3: Add Makefile targets for import checking (AC: 4)
  - [x] 3.1 Add `check-imports` target that runs `scripts/check_imports.py`
  - [x] 3.2 Add `format` target for black formatting
  - [x] 3.3 Update help text to include new targets

- [x] Task 4: Verify hexagonal import rules work (AC: 2, 3)
  - [x] 4.1 Create test file with valid imports (application importing from domain)
  - [x] 4.2 Verify test file with invalid imports is detected (domain importing from infrastructure)
  - [x] 4.3 Run full pre-commit hook check to validate integration
  - [x] 4.4 Verify existing codebase has no import boundary violations

- [x] Task 5: Integration test for pre-commit hooks (AC: 1, 2, 3)
  - [x] 5.1 Create `tests/integration/test_import_boundary_integration.py`
  - [x] 5.2 Test that import boundary check script correctly detects violations
  - [x] 5.3 Test that clean code passes all hooks

## Dev Notes

### Critical Architecture Requirements

**Hexagonal Architecture Import Rules (MEMORIZE):**

From `project-context.md` and `architecture.md`:

```
src/
├── domain/           # Pure business logic, NO infrastructure imports
├── application/      # Use cases, orchestration, ports
├── infrastructure/   # Adapters (Supabase, Redis, HSM)
└── api/              # FastAPI routes, DTOs
```

**Import Direction Rules:**
- `domain/` imports NOTHING from other src layers (may import stdlib, external libs)
- `application/` imports from `domain/` only
- `infrastructure/` implements ports from `application/`, may import `domain/`
- `api/` depends on `application/` services

**Forbidden Import Patterns:**
```python
# NEVER in domain/
from src.infrastructure import ...   # Violation!
from src.application import ...      # Violation!
from src.api import ...              # Violation!

# NEVER in application/
from src.infrastructure import ...   # Violation!
from src.api import ...              # Violation!

# NEVER in infrastructure/
from src.api import ...              # Violation!
```

### Import Checker Implementation Pattern

```python
#!/usr/bin/env python3
"""Check hexagonal architecture import boundaries."""
import ast
import sys
from pathlib import Path
from typing import List, Tuple

# Layer hierarchy: lower number = more inner layer
LAYER_HIERARCHY = {
    "domain": 0,      # Core, innermost
    "application": 1, # Use cases
    "infrastructure": 2,  # Adapters
    "api": 3,         # External interface
}

# Allowed imports: layer can only import from layers with LOWER numbers
# Exception: infrastructure can import from application (for ports)

def check_import_boundaries(src_dir: Path) -> List[Tuple[str, int, str]]:
    """Return list of (file, line, violation_message) tuples."""
    violations = []

    for py_file in src_dir.rglob("*.py"):
        # Determine this file's layer
        relative = py_file.relative_to(src_dir)
        parts = relative.parts
        if not parts:
            continue

        file_layer = parts[0]  # domain, application, infrastructure, api
        if file_layer not in LAYER_HIERARCHY:
            continue

        file_level = LAYER_HIERARCHY[file_layer]

        # Parse and check imports
        try:
            tree = ast.parse(py_file.read_text())
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                # Check import target
                module = get_import_module(node)
                if module and module.startswith("src."):
                    target_layer = module.split(".")[1]
                    if target_layer in LAYER_HIERARCHY:
                        target_level = LAYER_HIERARCHY[target_layer]

                        # Check violation: importing from higher-level layer
                        if target_level > file_level:
                            violations.append((
                                str(py_file),
                                node.lineno,
                                f"{file_layer} layer cannot import from {target_layer}"
                            ))

    return violations
```

### Pre-commit Configuration Pattern

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/psf/black
    rev: 24.3.0
    hooks:
      - id: black
        language_version: python3.11

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.3.0
    hooks:
      - id: ruff
        args: [--fix]

  - repo: local
    hooks:
      - id: mypy
        name: mypy
        entry: poetry run mypy
        language: system
        types: [python]
        args: [--strict, src/]
        pass_filenames: false

      - id: check-imports
        name: check import boundaries
        entry: python scripts/check_imports.py
        language: system
        types: [python]
        pass_filenames: false
```

### pyproject.toml Addition

```toml
[tool.poetry.group.dev.dependencies]
# Add to existing dev dependencies:
pre-commit = ">=3.5.0"
```

### Makefile Additions

```makefile
# Check import boundaries
check-imports:
	python scripts/check_imports.py

# Format code
format:
	poetry run black src/ tests/
	poetry run ruff check --fix src/ tests/

# Run pre-commit on all files
pre-commit:
	poetry run pre-commit run --all-files
```

### Previous Story Learnings (Story 0.5)

From Story 0.5 completion:
- Testcontainers work well for integration tests
- All 89 tests currently passing
- Docker check in Makefile is good pattern for external deps
- Poetry workflow: `poetry lock && poetry install` for dependency updates

### Current Project Structure

```
src/
├── api/                          # API layer
│   ├── routes/
│   │   ├── health.py
│   │   └── __init__.py
│   ├── models/
│   │   ├── health.py
│   │   └── __init__.py
│   ├── main.py
│   └── __init__.py
├── application/                  # Application layer
│   ├── ports/
│   │   ├── hsm.py               # HSM port interface
│   │   └── __init__.py
│   └── __init__.py
├── domain/                       # Domain layer
│   ├── errors/
│   │   ├── hsm.py
│   │   └── __init__.py
│   ├── models/
│   │   ├── signable.py          # Signable content model
│   │   └── __init__.py
│   ├── entities/
│   ├── value_objects/
│   ├── events/
│   ├── ports/
│   ├── exceptions.py
│   └── __init__.py
├── infrastructure/               # Infrastructure layer
│   ├── adapters/
│   │   ├── security/
│   │   │   ├── hsm_dev.py       # Dev HSM implementation
│   │   │   ├── hsm_cloud.py     # Cloud HSM stub
│   │   │   ├── hsm_factory.py   # HSM factory
│   │   │   └── __init__.py
│   │   └── __init__.py
│   └── __init__.py
└── __init__.py
```

### Existing Scripts

- `scripts/constitutional_lint.py` - Already exists, checks for forbidden constitutional terms

### Testing Notes

**Unit Tests for Import Checker:**
```python
# tests/unit/test_import_boundary.py
import pytest
from scripts.check_imports import check_import_boundaries, LAYER_HIERARCHY

def test_valid_import_domain_to_stdlib():
    """Domain can import from standard library."""
    ...

def test_violation_domain_imports_infrastructure():
    """Domain importing infrastructure should be detected."""
    ...

def test_valid_application_imports_domain():
    """Application can import from domain."""
    ...
```

**Integration Test:**
```python
# tests/integration/test_precommit_hooks.py
import subprocess
import pytest

@pytest.mark.integration
def test_import_check_script_runs():
    """Verify check_imports.py runs without errors on clean codebase."""
    result = subprocess.run(
        ["python", "scripts/check_imports.py"],
        capture_output=True,
        text=True
    )
    assert result.returncode == 0, f"Import check failed: {result.stderr}"
```

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 0.6]
- [Source: _bmad-output/project-context.md#Hexagonal Architecture Layers]
- [Source: _bmad-output/planning-artifacts/architecture.md#Project Structure]
- [Source: _bmad-output/implementation-artifacts/stories/0-5-integration-test-framework.md#Dev Agent Record]
- [Source: pyproject.toml - existing dev dependencies and tool configs]
- [Source: Makefile - existing targets to extend]

---

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

N/A - No significant debug issues encountered

### Completion Notes List

- **Task 1**: Created `scripts/check_imports.py` with AST-based import analysis. Implements hexagonal layer hierarchy (domain=0, application=1, infrastructure=2, api=3). Same-layer imports allowed, cross-layer imports checked against ALLOWED_IMPORTS rules. Refactored to extract helper functions (`_get_file_layer`, `_parse_file`, `_check_import_violation`) to reduce complexity. All 27 unit tests pass.

- **Task 2**: Added `pre-commit>=3.5.0` to pyproject.toml dev dependencies. Created `.pre-commit-config.yaml` with hooks for black (formatting), ruff (linting), mypy (type checking), and custom check-imports script.

- **Task 3**: Added Makefile targets: `check-imports` (runs import boundary checker), `format` (black + ruff fix), `pre-commit` (runs all hooks), `pre-commit-install` (installs git hooks). Updated help text.

- **Task 4**: Verified import boundary detection works correctly. Created temporary violation file in domain/ importing from infrastructure/ - correctly detected. Clean codebase passes with exit code 0.

- **Task 5**: Created `tests/integration/test_import_boundary_integration.py` with subprocess-based tests for the check_imports.py script. Tests cover clean codebase, violation detection, valid imports, file:line reporting, and violation counting.

### File List

**New Files:**
- `scripts/check_imports.py` - Hexagonal architecture import boundary checker (179 lines)
- `.pre-commit-config.yaml` - Pre-commit hooks configuration
- `tests/unit/test_import_boundary.py` - 27 unit tests for import checker
- `tests/integration/test_import_boundary_integration.py` - 6 integration tests for script

**Modified Files:**
- `pyproject.toml` - Added pre-commit>=3.5.0 to dev dependencies
- `Makefile` - Added check-imports, format, pre-commit, pre-commit-install targets

### Change Log

- 2026-01-06: Story 0.6 implementation complete
  - Implemented AST-based import boundary checking script
  - Hexagonal architecture rules: domain imports nothing, application imports domain, infrastructure imports domain+application, api imports application+domain
  - Pre-commit hooks configured for black, ruff, mypy, and import checking
  - Makefile targets for easy developer workflow
  - 27 unit tests + 6 integration tests, all passing
  - Existing codebase has zero import boundary violations

- 2026-01-06: Code Review - Fixes Applied
  - Fixed integration test file to use PROJECT_ROOT constant (removed conftest dependency issue)
  - Added missing test for API layer importing from infrastructure violation
  - Fixed Makefile consistency: all targets now use `python3 -m` instead of mixed `poetry run`
  - Fixed pre-commit config: check-imports hook uses entry/args pattern for consistency
  - Total tests now: 28 unit + 6 integration = 34 tests passing
  - Code Review: APPROVED
