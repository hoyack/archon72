# Application Layer

**Purpose:** Use cases and service orchestration for Archon 72.

## What Goes Here

- **Use Cases:** Application-specific business rules and workflows
- **Services:** Orchestration of domain objects and ports
- **Commands/Queries:** CQRS handlers for system operations
- **Port Definitions:** Abstract interfaces that infrastructure implements

## Import Rules

| Can Import | Cannot Import |
|------------|---------------|
| `src.domain` | `src.infrastructure` |
| Python stdlib | `src.api` |
| `typing` module | External libraries |

## Directory Structure

```
application/
├── __init__.py       # Layer exports
├── README.md         # This file
├── services/         # Application services
├── use_cases/        # Use case implementations
└── ports/            # Port definitions (if not in domain)
```

## Anti-Patterns to Avoid

1. **NO concrete infrastructure** - Use ports/interfaces, not implementations
2. **NO HTTP concerns** - Request/response handling belongs in api layer
3. **NO direct database access** - Use repository ports
4. **NO external API calls** - Use adapter ports

## Example

```python
# GOOD - Application service using ports
from src.domain.ports import EventStore
from src.domain.events import VoteCast

class VotingService:
    def __init__(self, event_store: EventStore):
        self._event_store = event_store

    async def cast_vote(self, agent_id: str, decision: bool) -> None:
        event = VoteCast(agent_id=agent_id, decision=decision)
        await self._event_store.append(event)

# BAD - Direct infrastructure usage
from supabase import Client  # NO! Use a port instead
```
