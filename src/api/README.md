# API Layer

**Purpose:** FastAPI routes and HTTP concerns for Archon 72.

## What Goes Here

- **Routes:** FastAPI endpoint definitions
- **DTOs:** Request/Response data transfer objects
- **Middleware:** HTTP middleware (auth, logging, CORS)
- **Dependencies:** FastAPI dependency injection setup

## Import Rules

| Can Import | Cannot Import |
|------------|---------------|
| `src.application` | `src.infrastructure` (directly) |
| Python stdlib | |
| FastAPI, Pydantic | |

**Note:** Infrastructure adapters are injected via FastAPI's dependency injection system, not imported directly.

## Directory Structure

```
api/
├── __init__.py       # Layer exports
├── README.md         # This file
├── routes/           # FastAPI routers
├── dto/              # Request/Response models
├── middleware/       # HTTP middleware
└── dependencies.py   # DI container setup
```

## Example

```python
# GOOD - API route using application service
from fastapi import APIRouter, Depends
from src.application.services import VotingService

router = APIRouter()

@router.post("/vote")
async def cast_vote(
    request: VoteRequest,
    voting_service: VotingService = Depends(get_voting_service)
):
    await voting_service.cast_vote(request.agent_id, request.decision)
    return {"status": "recorded"}

# BAD - Direct infrastructure import
from src.infrastructure.supabase import client  # NO! Use dependency injection
```

## Anti-Patterns to Avoid

1. **NO business logic** - Domain rules belong in domain layer
2. **NO direct database access** - Use application services
3. **NO infrastructure imports** - Use dependency injection
4. **NO application orchestration** - That belongs in application layer
