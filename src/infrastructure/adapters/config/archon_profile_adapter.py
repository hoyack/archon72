"""JSON + YAML adapter for Archon profile repository.

This adapter loads Archon identity data from JSON (docs/archons-base.json)
and merges it with LLM configuration from YAML (config/archon-llm-bindings.yaml)
to produce complete ArchonProfile instances.

Aligned with Government PRD (docs/new-requirements.md):
- Branch assignments per separation of powers
- Governance permissions per rank
- Knight-Witness (Furcas) as special observer
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID

import yaml
from structlog import get_logger

from src.application.ports.archon_profile_repository import (
    ArchonProfileLoadError,
    ArchonProfileRepository,
)
from src.domain.models.archon_profile import RANK_TO_BRANCH, ArchonProfile
from src.domain.models.llm_config import DEFAULT_LLM_CONFIG, LLMConfig

logger = get_logger(__name__)


class JsonYamlArchonProfileAdapter(ArchonProfileRepository):
    """Adapter that loads Archon profiles from JSON with YAML LLM bindings.

    This implementation:
    1. Loads identity data from a JSON file (name, backstory, system_prompt, branch, etc.)
    2. Loads LLM configurations from a YAML file (provider, model, temperature, etc.)
    3. Merges them into complete ArchonProfile instances
    4. Supports rank-based defaults and per-archon overrides

    The JSON is the source of truth for identity and governance; YAML is for operational config.

    Per Government PRD (docs/new-requirements.md):
    - Branch assignments define separation of powers
    - Governance permissions/constraints derived from branch
    - Knight-Witness (Furcas) is queryable via get_witness()
    """

    def __init__(
        self,
        json_path: Path | str,
        llm_config_path: Path | str,
    ) -> None:
        """Initialize the adapter with file paths.

        Args:
            json_path: Path to the archons JSON file
            llm_config_path: Path to the LLM bindings YAML file

        Raises:
            ArchonProfileLoadError: If files cannot be loaded or parsed
        """
        self._json_path = Path(json_path)
        self._llm_config_path = Path(llm_config_path)

        # Load and cache profiles at initialization
        self._profiles: dict[UUID, ArchonProfile] = {}
        self._profiles_by_name: dict[str, ArchonProfile] = {}
        self._profiles_by_branch: dict[str, list[ArchonProfile]] = {}
        self._witness: ArchonProfile | None = None
        self._load_profiles()

    def _load_profiles(self) -> None:
        """Load and merge JSON identities with YAML LLM configs."""
        # Load LLM configurations first
        llm_configs = self._load_llm_configs()

        # Load JSON identities and merge with LLM configs
        identities = self._load_json_identities()

        for archon_id, identity in identities.items():
            llm_config = self._resolve_llm_config(
                archon_id=archon_id,
                aegis_rank=identity["aegis_rank"],
                llm_configs=llm_configs,
            )

            # Determine branch: use JSON value or derive from rank
            branch = identity.get("branch", "")
            if not branch:
                branch = RANK_TO_BRANCH.get(identity["original_rank"], "")

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
                branch=branch,
                llm_config=llm_config,
            )

            self._profiles[archon_id] = profile
            self._profiles_by_name[profile.name.lower()] = profile

            # Index by branch
            if branch not in self._profiles_by_branch:
                self._profiles_by_branch[branch] = []
            self._profiles_by_branch[branch].append(profile)

            # Track witness (Furcas)
            if branch == "witness":
                self._witness = profile

        logger.info(
            "archon_profiles_loaded",
            count=len(self._profiles),
            json_path=str(self._json_path),
            llm_config_path=str(self._llm_config_path),
            branches=list(self._profiles_by_branch.keys()),
            witness=self._witness.name if self._witness else None,
        )

    def _load_json_identities(self) -> dict[UUID, dict[str, Any]]:
        """Load archon identity data from JSON file."""
        if not self._json_path.exists():
            raise ArchonProfileLoadError(
                source=str(self._json_path),
                reason="File not found",
            )

        identities: dict[UUID, dict[str, Any]] = {}

        try:
            with open(self._json_path, encoding="utf-8") as jsonfile:
                data = json.load(jsonfile)

                # Handle both array format and object with "archons" key
                archons = data.get("archons", data) if isinstance(data, dict) else data

                for archon in archons:
                    archon_id = UUID(archon["id"])

                    # Get timestamps with fallback
                    created_at = self._parse_timestamp(archon.get("created_at", ""))
                    updated_at = self._parse_timestamp(archon.get("updated_at", ""))

                    identities[archon_id] = {
                        "name": archon["name"],
                        "aegis_rank": archon["aegis_rank"],
                        "original_rank": archon.get(
                            "original_rank", archon.get("rank", "")
                        ),
                        "rank_level": int(archon["rank_level"]),
                        "branch": archon.get("branch", ""),
                        "role": archon["role"],
                        "goal": archon["goal"],
                        "backstory": archon["backstory"],
                        "system_prompt": archon["system_prompt"],
                        "suggested_tools": archon.get("suggested_tools", []),
                        "allow_delegation": archon.get("allow_delegation", True),
                        "attributes": archon.get("attributes", {}),
                        "max_members": int(archon.get("max_members", 0)),
                        "max_legions": int(archon.get("max_legions", 0)),
                        "created_at": created_at,
                        "updated_at": updated_at,
                    }

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            raise ArchonProfileLoadError(
                source=str(self._json_path),
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
        return [p for p in self._profiles.values() if p.llm_config.provider == provider]

    def get_executives(self) -> list[ArchonProfile]:
        """Retrieve all executive director (King) Archons."""
        return self.get_by_rank("executive_director")

    def count(self) -> int:
        """Return the total number of Archon profiles."""
        return len(self._profiles)

    def exists(self, archon_id: UUID) -> bool:
        """Check if an Archon with the given ID exists."""
        return archon_id in self._profiles

    def get_by_branch(self, branch: str) -> list[ArchonProfile]:
        """Retrieve all Archons in a specific governance branch."""
        return self._profiles_by_branch.get(branch, [])

    def get_witness(self) -> ArchonProfile | None:
        """Retrieve the Knight-Witness (Furcas)."""
        return self._witness

    def get_all_names(self) -> list[str]:
        """Retrieve all Archon names in canonical order."""
        return [p.name for p in self.get_all()]


# Backwards compatibility alias
CsvYamlArchonProfileAdapter = JsonYamlArchonProfileAdapter


def create_archon_profile_repository(
    json_path: Path | str | None = None,
    llm_config_path: Path | str | None = None,
) -> ArchonProfileRepository:
    """Factory function to create an ArchonProfileRepository.

    Uses default paths if not specified:
    - JSON: docs/archons-base.json (single source of truth for all 72 Archons)
    - YAML: config/archon-llm-bindings.yaml

    Args:
        json_path: Optional path to archons JSON file
        llm_config_path: Optional path to LLM config YAML

    Returns:
        Configured ArchonProfileRepository instance
    """
    # Determine project root (assumes this file is in src/infrastructure/adapters/config/)
    project_root = Path(__file__).parent.parent.parent.parent.parent

    json_path = json_path or project_root / "docs" / "archons-base.json"
    llm_config_path = (
        llm_config_path or project_root / "config" / "archon-llm-bindings.yaml"
    )

    return JsonYamlArchonProfileAdapter(
        json_path=json_path,
        llm_config_path=llm_config_path,
    )
