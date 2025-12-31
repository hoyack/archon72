"""
API layer - FastAPI routes and HTTP concerns for Archon 72.

This layer contains:
- FastAPI route definitions
- Request/Response DTOs
- HTTP middleware
- API versioning

IMPORT RULES:
- CAN import from: application
- CANNOT import from: infrastructure directly
- Uses dependency injection for infrastructure adapters
"""

__all__: list[str] = []
