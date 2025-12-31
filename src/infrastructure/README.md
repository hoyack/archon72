# Infrastructure Layer

**Purpose:** External adapters and integrations for Archon 72.

## What Goes Here

- **Database Adapters:** Supabase/PostgreSQL implementations
- **Cache Adapters:** Redis implementations
- **HSM Adapters:** Hardware Security Module integrations
- **External APIs:** Third-party service clients
- **Message Queues:** Pub/sub implementations

## Import Rules

| Can Import | Cannot Import |
|------------|---------------|
| `src.domain` | `src.api` |
| `src.application` | |
| External libraries | |
| Python stdlib | |

## Directory Structure

```
infrastructure/
├── __init__.py       # Layer exports
├── README.md         # This file
├── supabase/         # Supabase adapter
├── redis/            # Redis adapter
├── hsm/              # HSM adapter (software stub initially)
└── adapters/         # Other external adapters
```

## Key Principle: Implement Ports

This layer provides **concrete implementations** of the abstract ports defined in domain/application layers.

## Example

```python
# GOOD - Implementing a domain port
from src.domain.ports import EventStore
from src.domain.events import DomainEvent
from supabase import Client

class SupabaseEventStore(EventStore):
    def __init__(self, client: Client):
        self._client = client

    async def append(self, event: DomainEvent) -> None:
        await self._client.table("events").insert(event.to_dict()).execute()

# This adapter can be injected where EventStore port is needed
```

## Anti-Patterns to Avoid

1. **NO business logic** - Domain rules belong in domain layer
2. **NO HTTP routing** - API concerns belong in api layer
3. **NO use case orchestration** - That belongs in application layer
