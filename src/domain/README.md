# Domain Layer

**Purpose:** Pure business logic for Archon 72 Constitutional AI Governance System.

## What Goes Here

- **Entities:** Domain objects with identity (Archon, Meeting, Vote, Deliberation)
- **Value Objects:** Immutable types without identity (AgentId, Hash, Signature)
- **Events:** Constitutional domain events (VoteCast, MeetingConvened, HaltTriggered)
- **Ports:** Abstract interfaces (protocols/ABCs) for infrastructure
- **Exceptions:** Domain-specific exception hierarchy

## Import Rules

| Can Import | Cannot Import |
|------------|---------------|
| Python stdlib | `src.application` |
| `typing` module | `src.infrastructure` |
| | `src.api` |

**CRITICAL:** This layer must have ZERO dependencies on other layers. Only Python standard library and typing imports are allowed.

## Directory Structure

```
domain/
├── __init__.py       # Exports ConclaveError
├── README.md         # This file
├── exceptions.py     # Base exception: ConclaveError
├── events/           # Constitutional event types
├── entities/         # Domain entities
├── value_objects/    # Immutable value types
└── ports/            # Abstract interfaces
```

## Anti-Patterns to Avoid

1. **NO database imports** - SQLAlchemy, Supabase, etc. belong in infrastructure
2. **NO HTTP/API imports** - FastAPI, requests, etc. belong in api/infrastructure
3. **NO external service imports** - Redis, message queues, etc. belong in infrastructure
4. **NO framework-specific code** - Keep it pure Python

## Example

```python
# GOOD - Pure domain logic
from typing import Protocol
from dataclasses import dataclass

@dataclass(frozen=True)
class AgentId:
    value: str

class EventStore(Protocol):
    async def append(self, event: DomainEvent) -> None: ...

# BAD - Infrastructure leak
from supabase import Client  # NO! This belongs in infrastructure
```
