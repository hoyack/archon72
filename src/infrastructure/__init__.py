"""
Infrastructure layer - External adapters for Archon 72.

This layer contains:
- Supabase adapter (database operations)
- Redis adapter (caching, pub/sub)
- HSM adapter (cryptographic operations)
- External service integrations

IMPORT RULES:
- CAN import from: domain, application
- Implements ports defined in application layer
"""

__all__: list[str] = []
