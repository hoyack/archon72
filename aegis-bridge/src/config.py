"""Configuration settings from environment variables."""

import os
from dataclasses import dataclass
from pathlib import Path

# Load .env file if present
try:
    from dotenv import load_dotenv

    # Look for .env in current dir or parent dir
    env_path = Path(".env")
    if not env_path.exists():
        env_path = Path("../.env")
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass  # dotenv not installed, rely on actual environment


@dataclass(frozen=True)
class SupabaseConfig:
    """Supabase connection configuration."""

    url: str
    service_key: str
    table_petitions: str = "petitions"
    table_realms: str = "realms"


@dataclass(frozen=True)
class Archon72Config:
    """Archon72 API configuration."""

    api_url: str
    timeout_seconds: int = 120  # LLM deliberation can take time
    submit_endpoint: str = "/v1/petition-submissions"


@dataclass(frozen=True)
class ProcessingConfig:
    """Processing behavior configuration."""

    batch_size: int = 100
    max_retries: int = 3
    dry_run: bool = False  # If True, don't actually submit to Archon72


@dataclass(frozen=True)
class Config:
    """Application configuration."""

    supabase: SupabaseConfig
    archon72: Archon72Config
    processing: ProcessingConfig


def load_config() -> Config:
    """Load configuration from environment variables.

    Required environment variables:
        SUPABASE_URL: Supabase project URL
        SUPABASE_SERVICE_KEY: Supabase service role key
        ARCHON72_API_URL: Archon72 API base URL

    Optional environment variables:
        BATCH_SIZE: Number of petitions to process per batch (default: 100)
        MAX_RETRIES: Maximum retry attempts (default: 3)
        DRY_RUN: If "true", don't submit to Archon72 (default: false)

    Returns:
        Config object with all settings.

    Raises:
        ValueError: If required environment variables are missing.
    """
    # Required
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_SERVICE_KEY")
    archon72_url = os.environ.get("ARCHON72_API_URL")

    missing = []
    if not supabase_url:
        missing.append("SUPABASE_URL")
    if not supabase_key:
        missing.append("SUPABASE_SERVICE_KEY")
    if not archon72_url:
        missing.append("ARCHON72_API_URL")

    if missing:
        raise ValueError(f"Missing required environment variables: {', '.join(missing)}")

    # Optional
    batch_size = int(os.environ.get("BATCH_SIZE", "100"))
    max_retries = int(os.environ.get("MAX_RETRIES", "3"))
    dry_run = os.environ.get("DRY_RUN", "false").lower() == "true"

    return Config(
        supabase=SupabaseConfig(
            url=supabase_url,
            service_key=supabase_key,
        ),
        archon72=Archon72Config(
            api_url=archon72_url,
        ),
        processing=ProcessingConfig(
            batch_size=batch_size,
            max_retries=max_retries,
            dry_run=dry_run,
        ),
    )
