"""CSV + YAML adapter for Archon profile repository.

This adapter loads Archon identity data from CSV (docs/archons-base.csv)
and merges it with LLM configuration from YAML (config/archon-llm-bindings.yaml)
to produce complete ArchonProfile instances.
"""

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID

import yaml
from structlog import get_logger

from src.application.ports.archon_profile_repository import (
    ArchonProfileRepository,
    ArchonProfileLoadError,
)
from src.domain.models.archon_profile import ArchonProfile
from src.domain.models.llm_config import LLMConfig, DEFAULT_LLM_CONFIG


logger = get_logger(__name__)


class CsvYamlArchonProfileAdapter(ArchonProfileRepository):
    """Adapter that loads Archon profiles from CSV with YAML LLM bindings.

    This implementation:
    1. Loads identity data from a CSV file (name, backstory, system_prompt, etc.)
    2. Loads LLM configurations from a YAML file (provider, model, temperature, etc.)
    3. Merges them into complete ArchonProfile instances
    4. Supports rank-based defaults and per-archon overrides

    The CSV is the source of truth for identity; YAML is for operational config.
    """

    def __init__(
        self,
        csv_path: Path | str,
        llm_config_path: Path | str,
    ) -> None:
        """Initialize the adapter with file paths.

        Args:
            csv_path: Path to the archons CSV file
            llm_config_path: Path to the LLM bindings YAML file

        Raises:
            ArchonProfileLoadError: If files cannot be loaded or parsed
        """
        self._csv_path = Path(csv_path)
        self._llm_config_path = Path(llm_config_path)

        # Load and cache profiles at initialization
        self._profiles: dict[UUID, ArchonProfile] = {}
        self._profiles_by_name: dict[str, ArchonProfile] = {}
        self._load_profiles()

    def _load_profiles(self) -> None:
        """Load and merge CSV identities with YAML LLM configs."""
        # Load LLM configurations first
        llm_configs = self._load_llm_configs()

        # Load CSV identities and merge with LLM configs
        identities = self._load_csv_identities()

        for archon_id, identity in identities.items():
            llm_config = self._resolve_llm_config(
                archon_id=archon_id,
                aegis_rank=identity["aegis_rank"],
                llm_configs=llm_configs,
            )

            profile = ArchonProfile(
                id=archon_id,
                name=identity["name"],
                aegis_rank=identity["aegis_rank"],
                original_rank=identity["original_rank"],
                rank_level=identity["rank_level"],
                role=identity["role"],
                goal=identity["goal"],
                backstory=identity["backstory"],
                system_prompt=identity["system_prompt"],
                suggested_tools=identity["suggested_tools"],
                allow_delegation=identity["allow_delegation"],
                attributes=identity["attributes"],
                max_members=identity["max_members"],
                max_legions=identity["max_legions"],
                created_at=identity["created_at"],
                updated_at=identity["updated_at"],
                llm_config=llm_config,
            )

            self._profiles[archon_id] = profile
            self._profiles_by_name[profile.name.lower()] = profile

        logger.info(
            "archon_profiles_loaded",
            count=len(self._profiles),
            csv_path=str(self._csv_path),
            llm_config_path=str(self._llm_config_path),
        )

    def _load_csv_identities(self) -> dict[UUID, dict[str, Any]]:
        """Load archon identity data from CSV file."""
        if not self._csv_path.exists():
            raise ArchonProfileLoadError(
                source=str(self._csv_path),
                reason="File not found",
            )

        identities: dict[UUID, dict[str, Any]] = {}

        try:
            with open(self._csv_path, newline="", encoding="utf-8") as csvfile:
                reader = csv.DictReader(csvfile)

                for row in reader:
                    archon_id = UUID(row["id"])

                    # Parse JSON fields
                    suggested_tools = self._parse_json_field(
                        row.get("suggested_tools", "[]")
                    )
                    attributes = self._parse_json_field(row.get("attributes", "{}"))

                    # Parse timestamps
                    created_at = self._parse_timestamp(row.get("created_at", ""))
                    updated_at = self._parse_timestamp(row.get("updated_at", ""))

                    identities[archon_id] = {
                        "name": row["name"],
                        "aegis_rank": row["aegis_rank"],
                        "original_rank": row["original_rank"],
                        "rank_level": int(row["rank_level"]),
                        "role": row["role"],
                        "goal": row["goal"],
                        "backstory": row["backstory"],
                        "system_prompt": row["system_prompt"],
                        "suggested_tools": suggested_tools,
                        "allow_delegation": row.get("allow_delegation", "").lower()
                        == "true",
                        "attributes": attributes,
                        "max_members": int(row.get("max_members", 0)),
                        "max_legions": int(row.get("max_legions", 0)),
                        "created_at": created_at,
                        "updated_at": updated_at,
                    }

        except (csv.Error, KeyError, ValueError) as e:
            raise ArchonProfileLoadError(
                source=str(self._csv_path),
                reason=str(e),
            ) from e

        return identities

    def _load_llm_configs(self) -> dict[str, Any]:
        """Load LLM configuration from YAML file."""
        if not self._llm_config_path.exists():
            logger.warning(
                "llm_config_not_found",
                path=str(self._llm_config_path),
                message="Using default LLM config for all archons",
            )
            return {"_default": self._llm_config_to_dict(DEFAULT_LLM_CONFIG)}

        try:
            with open(self._llm_config_path, encoding="utf-8") as f:
                config = yaml.safe_load(f)
                return config or {}

        except yaml.YAMLError as e:
            raise ArchonProfileLoadError(
                source=str(self._llm_config_path),
                reason=str(e),
            ) from e

    def _resolve_llm_config(
        self,
        archon_id: UUID,
        aegis_rank: str,
        llm_configs: dict[str, Any],
    ) -> LLMConfig:
        """Resolve LLM config with priority: archon > rank_default > default."""
        archon_id_str = str(archon_id)

        # Priority 1: Explicit archon configuration
        if archon_id_str in llm_configs:
            return self._dict_to_llm_config(llm_configs[archon_id_str])

        # Priority 2: Rank-based default
        rank_defaults = llm_configs.get("_rank_defaults", {})
        if aegis_rank in rank_defaults:
            return self._dict_to_llm_config(rank_defaults[aegis_rank])

        # Priority 3: Global default
        if "_default" in llm_configs:
            return self._dict_to_llm_config(llm_configs["_default"])

        # Fallback to hardcoded default
        return DEFAULT_LLM_CONFIG

    def _dict_to_llm_config(self, config_dict: dict[str, Any]) -> LLMConfig:
        """Convert a dictionary to LLMConfig instance."""
        return LLMConfig(
            provider=config_dict.get("provider", "anthropic"),
            model=config_dict.get("model", "claude-3-haiku-20240307"),
            temperature=float(config_dict.get("temperature", 0.5)),
            max_tokens=int(config_dict.get("max_tokens", 2048)),
            timeout_ms=int(config_dict.get("timeout_ms", 30000)),
            api_key_env=config_dict.get("api_key_env"),
            base_url=config_dict.get("base_url"),
        )

    def _llm_config_to_dict(self, config: LLMConfig) -> dict[str, Any]:
        """Convert LLMConfig instance to dictionary."""
        return {
            "provider": config.provider,
            "model": config.model,
            "temperature": config.temperature,
            "max_tokens": config.max_tokens,
            "timeout_ms": config.timeout_ms,
            "api_key_env": config.api_key_env,
            "base_url": config.base_url,
        }

    def _parse_json_field(self, value: str) -> Any:
        """Parse a JSON field from CSV, handling empty values."""
        if not value or value.strip() == "":
            return {}
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            logger.warning("json_parse_failed", value=value[:100])
            return {}

    def _parse_timestamp(self, value: str) -> datetime:
        """Parse timestamp from CSV, with fallback to now."""
        if not value:
            return datetime.now()
        try:
            # Handle PostgreSQL timestamp format with timezone
            if "+" in value:
                value = value.split("+")[0].strip()
            return datetime.fromisoformat(value)
        except ValueError:
            return datetime.now()

    # =========================================================================
    # ArchonProfileRepository interface implementation
    # =========================================================================

    def get_by_id(self, archon_id: UUID) -> ArchonProfile | None:
        """Retrieve an Archon profile by its unique identifier."""
        return self._profiles.get(archon_id)

    def get_by_name(self, name: str) -> ArchonProfile | None:
        """Retrieve an Archon profile by name (case-insensitive)."""
        return self._profiles_by_name.get(name.lower())

    def get_all(self) -> list[ArchonProfile]:
        """Retrieve all Archon profiles, sorted by rank then name."""
        return sorted(
            self._profiles.values(),
            key=lambda p: (-p.rank_level, p.name),
        )

    def get_by_rank(self, aegis_rank: str) -> list[ArchonProfile]:
        """Retrieve all Archons of a specific rank."""
        return [p for p in self._profiles.values() if p.aegis_rank == aegis_rank]

    def get_by_tool(self, tool_name: str) -> list[ArchonProfile]:
        """Retrieve all Archons that have a specific tool."""
        return [p for p in self._profiles.values() if tool_name in p.suggested_tools]

    def get_by_provider(self, provider: str) -> list[ArchonProfile]:
        """Retrieve all Archons bound to a specific LLM provider."""
        return [
            p for p in self._profiles.values() if p.llm_config.provider == provider
        ]

    def get_executives(self) -> list[ArchonProfile]:
        """Retrieve all executive director (King) Archons."""
        return self.get_by_rank("executive_director")

    def count(self) -> int:
        """Return the total number of Archon profiles."""
        return len(self._profiles)

    def exists(self, archon_id: UUID) -> bool:
        """Check if an Archon with the given ID exists."""
        return archon_id in self._profiles


def create_archon_profile_repository(
    csv_path: Path | str | None = None,
    llm_config_path: Path | str | None = None,
) -> ArchonProfileRepository:
    """Factory function to create an ArchonProfileRepository.

    Uses default paths if not specified:
    - CSV: docs/archons-base.csv
    - YAML: config/archon-llm-bindings.yaml

    Args:
        csv_path: Optional path to archons CSV
        llm_config_path: Optional path to LLM config YAML

    Returns:
        Configured ArchonProfileRepository instance
    """
    # Determine project root (assumes this file is in src/infrastructure/adapters/config/)
    project_root = Path(__file__).parent.parent.parent.parent.parent

    csv_path = csv_path or project_root / "docs" / "archons-base.csv"
    llm_config_path = llm_config_path or project_root / "config" / "archon-llm-bindings.yaml"

    return CsvYamlArchonProfileAdapter(
        csv_path=csv_path,
        llm_config_path=llm_config_path,
    )
