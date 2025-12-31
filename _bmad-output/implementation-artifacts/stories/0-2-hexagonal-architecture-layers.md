# Story 0.2: Hexagonal Architecture Layers

Status: done

## Story

As a **developer**,
I want a hexagonal architecture scaffold with clear layer boundaries,
So that I can place code in the correct layer without confusion.

## Acceptance Criteria

### AC1: Main Layer Directories

**Given** the project structure
**When** I examine the `src/` directory
**Then** it contains these subdirectories:
  - `src/domain/` (pure business logic, no infrastructure imports)
  - `src/application/` (use cases, ports, orchestration)
  - `src/infrastructure/` (adapters: Supabase, Redis, HSM)
  - `src/api/` (FastAPI routes, DTOs)
**And** each directory contains an `__init__.py` file
**And** each directory contains a `README.md` explaining its purpose

### AC2: Domain Layer Structure

**Given** the domain layer
**When** I examine `src/domain/`
**Then** it contains subdirectories for:
  - `events/` (constitutional event types)
  - `entities/` (domain entities)
  - `value_objects/` (immutable value types)
  - `ports/` (abstract interfaces)
**And** no file in domain imports from infrastructure or api

## Tasks / Subtasks

- [x] Task 1: Create main layer directories with __init__.py (AC: 1)
  - [x] 1.1 Create `src/domain/__init__.py`
  - [x] 1.2 Create `src/application/__init__.py`
  - [x] 1.3 Create `src/infrastructure/__init__.py`
  - [x] 1.4 Create `src/api/__init__.py`

- [x] Task 2: Create layer README.md files (AC: 1)
  - [x] 2.1 Create `src/domain/README.md` with layer purpose and import rules
  - [x] 2.2 Create `src/application/README.md` with layer purpose and import rules
  - [x] 2.3 Create `src/infrastructure/README.md` with layer purpose and import rules
  - [x] 2.4 Create `src/api/README.md` with layer purpose and import rules

- [x] Task 3: Create domain layer subdirectories (AC: 2)
  - [x] 3.1 Create `src/domain/events/__init__.py`
  - [x] 3.2 Create `src/domain/entities/__init__.py`
  - [x] 3.3 Create `src/domain/value_objects/__init__.py`
  - [x] 3.4 Create `src/domain/ports/__init__.py`

- [x] Task 4: Create base exception class (AC: 2)
  - [x] 4.1 Create `src/domain/exceptions.py` with `ConclaveError` base class
  - [x] 4.2 Export from `src/domain/__init__.py`

- [x] Task 5: Verify structure with tests (AC: 1, 2)
  - [x] 5.1 Create `tests/unit/test_architecture.py` to verify structure exists
  - [x] 5.2 Add import boundary test (domain must not import from infrastructure/api)
  - [x] 5.3 Run tests and verify pass

## Dev Notes

### Hexagonal Architecture Import Rules (CRITICAL)

From `project-context.md`:

```
src/
├── domain/           # Pure business logic, NO infrastructure imports
├── application/      # Use cases, orchestration, ports
├── infrastructure/   # Adapters (Supabase, Redis, HSM)
└── api/              # FastAPI routes, DTOs
```

**Import Rules:**
- `domain/` imports NOTHING from other layers (only stdlib and typing)
- `application/` imports from `domain/` only
- `infrastructure/` implements ports from `application/`
- `api/` depends on `application/` services

### Layer Purposes

| Layer | Purpose | Can Import From |
|-------|---------|-----------------|
| `domain` | Pure business logic, domain events, entities, value objects, ports | NOTHING (stdlib only) |
| `application` | Use cases, service orchestration, port definitions | `domain` only |
| `infrastructure` | Concrete adapters (Supabase, Redis, HSM), external integrations | `domain`, `application` |
| `api` | FastAPI routes, DTOs, HTTP concerns | `application` (NOT infrastructure directly) |

### Domain Layer Structure

```
src/domain/
├── __init__.py           # Exports: ConclaveError
├── README.md             # Layer documentation
├── exceptions.py         # Base exception: ConclaveError
├── events/               # Constitutional event types
│   └── __init__.py
├── entities/             # Domain entities
│   └── __init__.py
├── value_objects/        # Immutable value types
│   └── __init__.py
└── ports/                # Abstract interfaces (protocols/ABCs)
    └── __init__.py
```

### ConclaveError Base Class Pattern

From `project-context.md`:

```python
# src/domain/exceptions.py
"""Base exception classes for the Archon 72 domain layer."""

class ConclaveError(Exception):
    """Base exception for all domain errors.

    All domain-specific exceptions MUST inherit from this class.
    This enables consistent error handling across the application.

    Example subclasses (to be added in future stories):
    - QuorumNotMetError
    - SignatureVerificationError
    - SystemHaltedError
    """
    pass
```

### __init__.py Content Guidelines

Each `__init__.py` should:
1. Have a docstring explaining the layer's purpose
2. Define `__all__` for explicit exports
3. Keep imports minimal (only what's needed for re-export)

Example for `src/domain/__init__.py`:
```python
"""
Domain layer - Pure business logic for Archon 72.

This layer contains:
- Domain entities (Archon, Meeting, Vote, etc.)
- Value objects (immutable types)
- Domain events (constitutional events)
- Ports (abstract interfaces)
- Domain exceptions

CRITICAL: This layer must NOT import from application, infrastructure, or api.
Only stdlib and typing imports are allowed.
"""

from src.domain.exceptions import ConclaveError

__all__ = ["ConclaveError"]
```

### README.md Content for Each Layer

Each README should include:
1. Layer purpose (1-2 sentences)
2. What goes here (bullet list)
3. Import rules (what CAN and CANNOT be imported)
4. Example contents
5. Anti-patterns to avoid

### Previous Story Learnings (Story 0.1)

From the completed Story 0.1:
- `src/__init__.py` already exists with `__version__ = "0.1.0"`
- `src/py.typed` already exists (PEP 561 marker)
- Poetry environment is configured with Python 3.12.12
- Test structure is `tests/unit/` with `conftest.py`

**Files NOT to modify:**
- `src/__init__.py` (already has __version__)
- `src/py.typed` (already exists)
- `pyproject.toml` (no changes needed for this story)

### Test Structure for Architecture Validation

```python
# tests/unit/test_architecture.py
"""Tests to verify hexagonal architecture structure."""

import ast
import os
from pathlib import Path

def test_main_layers_exist():
    """Verify all main layer directories exist."""
    src = Path("src")
    layers = ["domain", "application", "infrastructure", "api"]
    for layer in layers:
        assert (src / layer).is_dir(), f"Missing layer: {layer}"
        assert (src / layer / "__init__.py").is_file()
        assert (src / layer / "README.md").is_file()

def test_domain_subdirectories_exist():
    """Verify domain layer has required subdirectories."""
    domain = Path("src/domain")
    subdirs = ["events", "entities", "value_objects", "ports"]
    for subdir in subdirs:
        assert (domain / subdir).is_dir()
        assert (domain / subdir / "__init__.py").is_file()

def test_domain_has_no_infrastructure_imports():
    """Verify domain layer does not import from infrastructure or api."""
    domain_files = list(Path("src/domain").rglob("*.py"))
    forbidden = ["from src.infrastructure", "from src.api",
                 "import src.infrastructure", "import src.api"]

    for py_file in domain_files:
        content = py_file.read_text()
        for forbidden_import in forbidden:
            assert forbidden_import not in content, \
                f"{py_file} contains forbidden import: {forbidden_import}"

def test_conclave_error_exists():
    """Verify base exception class is defined."""
    from src.domain.exceptions import ConclaveError
    assert issubclass(ConclaveError, Exception)
```

### Project Structure After Completion

```
archon72/
├── pyproject.toml
├── poetry.lock
├── README.md
├── .gitignore
├── src/
│   ├── __init__.py           # (existing) __version__
│   ├── py.typed              # (existing) PEP 561
│   ├── domain/
│   │   ├── __init__.py       # NEW
│   │   ├── README.md         # NEW
│   │   ├── exceptions.py     # NEW - ConclaveError
│   │   ├── events/
│   │   │   └── __init__.py   # NEW
│   │   ├── entities/
│   │   │   └── __init__.py   # NEW
│   │   ├── value_objects/
│   │   │   └── __init__.py   # NEW
│   │   └── ports/
│   │       └── __init__.py   # NEW
│   ├── application/
│   │   ├── __init__.py       # NEW
│   │   └── README.md         # NEW
│   ├── infrastructure/
│   │   ├── __init__.py       # NEW
│   │   └── README.md         # NEW
│   └── api/
│       ├── __init__.py       # NEW
│       └── README.md         # NEW
└── tests/
    ├── unit/
    │   ├── test_smoke.py     # (existing)
    │   └── test_architecture.py  # NEW
    └── ...
```

### References

- [Source: _bmad-output/project-context.md#Hexagonal Architecture Layers]
- [Source: _bmad-output/project-context.md#Import Rules]
- [Source: _bmad-output/planning-artifacts/epics.md#Story 0.2]
- [Source: _bmad-output/implementation-artifacts/stories/0-1-project-scaffold-and-dependencies.md#File List]

---

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

- All 26 tests pass (6 architecture + 20 smoke tests)
- Poetry virtualenv with Python 3.12.12

### Completion Notes List

1. Created all 4 main layer directories (domain, application, infrastructure, api) with proper `__init__.py` files containing docstrings, `__all__` exports, and clear import rules
2. Created comprehensive README.md for each layer with purpose, import rules, anti-patterns, and examples
3. Created domain subdirectories (events, entities, value_objects, ports) with `__init__.py` files
4. Created `ConclaveError` base exception class in `src/domain/exceptions.py`
5. Created `tests/unit/test_architecture.py` with 6 tests validating structure and import boundaries
6. All tests passing - structure is verified and import boundaries are enforced

### File List

_Files created:_
- `src/domain/__init__.py`
- `src/domain/README.md`
- `src/domain/exceptions.py`
- `src/domain/events/__init__.py`
- `src/domain/entities/__init__.py`
- `src/domain/value_objects/__init__.py`
- `src/domain/ports/__init__.py`
- `src/application/__init__.py`
- `src/application/README.md`
- `src/infrastructure/__init__.py`
- `src/infrastructure/README.md`
- `src/api/__init__.py`
- `src/api/README.md`
- `tests/unit/test_architecture.py`
