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

__all__: list[str] = ["ConclaveError"]
