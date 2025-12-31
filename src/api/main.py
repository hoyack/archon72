"""FastAPI application entry point for Archon 72."""

from fastapi import FastAPI

from src.api.routes.health import router as health_router

app = FastAPI(
    title="Archon 72 Conclave API",
    description="Constitutional AI Governance System",
    version="0.1.0",
)

app.include_router(health_router)
