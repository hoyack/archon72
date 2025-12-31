"""
API routes for Archon 72.

This module contains all FastAPI router definitions.
Routes are organized by domain concern.

Available routers:
- health: Health check endpoints
"""

from src.api.routes.health import router as health_router

__all__: list[str] = ["health_router"]
