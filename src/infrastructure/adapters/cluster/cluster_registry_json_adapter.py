"""JSON-file-backed Cluster Registry adapter.

MVP implementation of ClusterRegistryPort that reads Aegis Cluster
definition JSON files from a directory, validates required fields,
and filters by capability tags, availability, and auth level.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.application.ports.tactic_decomposition import (
    ClusterCandidate,
    ClusterRegistryPort,
)

# Auth level ordering for sensitivity gate comparison
_AUTH_LEVEL_RANK: dict[str, int] = {
    "standard": 0,
    "sensitive": 1,
    "restricted": 2,
}


class ClusterRegistryJsonAdapter(ClusterRegistryPort):
    """Reads cluster definitions from a directory of JSON files.

    Each *.json file in the directory should conform to the Aegis Cluster
    schema (docs/governance/schemas/cluster-schema.json). This adapter
    performs lightweight field validation rather than full JSON Schema
    validation to stay dependency-light.
    """

    def __init__(self, cluster_dir: Path, verbose: bool = False) -> None:
        self._cluster_dir = cluster_dir
        self._verbose = verbose
        self._cache: list[ClusterCandidate] | None = None

    def _load_clusters(self) -> list[ClusterCandidate]:
        """Load and validate all cluster JSON files from the directory."""
        if self._cache is not None:
            return self._cache

        candidates: list[ClusterCandidate] = []

        if not self._cluster_dir.is_dir():
            if self._verbose:
                print(f"  [cluster-registry] directory not found: {self._cluster_dir}")
            self._cache = candidates
            return candidates

        for json_path in sorted(self._cluster_dir.glob("*.json")):
            try:
                candidate = self._parse_cluster_file(json_path)
                if candidate is not None:
                    candidates.append(candidate)
            except Exception as exc:
                if self._verbose:
                    print(f"  [cluster-registry] skipping {json_path.name}: {exc}")

        if self._verbose:
            print(f"  [cluster-registry] loaded {len(candidates)} clusters")

        self._cache = candidates
        return candidates

    def _parse_cluster_file(self, path: Path) -> ClusterCandidate | None:
        """Parse a single cluster JSON file into a ClusterCandidate."""
        with open(path, encoding="utf-8") as f:
            data: dict[str, Any] = json.load(f)

        # Validate required top-level fields
        cluster_id = data.get("cluster_id", "")
        status = data.get("status", "")
        if not cluster_id or not status:
            return None

        # Steward
        steward = data.get("steward", {})
        steward_id = steward.get("steward_id", "")
        auth_level = steward.get("auth_level", "standard")
        contact = steward.get("contact", {})

        # Capabilities
        capabilities = data.get("capabilities", {})
        tags = capabilities.get("tags", [])

        # Capacity
        capacity = data.get("capacity", {})
        availability = capacity.get("availability_status", "available")
        max_concurrent = capacity.get("max_concurrent_tasks", 3)

        return ClusterCandidate(
            cluster_id=cluster_id,
            cluster_name=data.get("name", ""),
            steward_id=steward_id,
            capability_tags=list(tags),
            availability_status=availability,
            max_concurrent_tasks=max_concurrent,
            auth_level=auth_level,
            contact_channel=contact.get("channel", ""),
            contact_address=contact.get("address", ""),
        )

    async def find_eligible_clusters(
        self,
        required_tags: list[str],
        sensitivity_level: str = "standard",
    ) -> list[ClusterCandidate]:
        """Find clusters matching capability and availability requirements.

        Filtering rules:
        1. cluster.status must be "active" (implied by availability != retired)
        2. availability_status != "unavailable"
        3. required_tags subset of cluster capability_tags
        4. cluster auth_level >= task sensitivity_level
        """
        all_clusters = self._load_clusters()
        required_set = set(required_tags)
        required_sensitivity_rank = _AUTH_LEVEL_RANK.get(sensitivity_level, 0)
        eligible: list[ClusterCandidate] = []

        for cluster in all_clusters:
            # Filter: unavailable
            if cluster.availability_status == "unavailable":
                continue

            # Filter: capability tags
            cluster_tags = set(cluster.capability_tags)
            if not required_set.issubset(cluster_tags):
                continue

            # Filter: auth level sensitivity gate
            cluster_auth_rank = _AUTH_LEVEL_RANK.get(cluster.auth_level, 0)
            if cluster_auth_rank < required_sensitivity_rank:
                continue

            eligible.append(cluster)

        # Deterministic ordering by cluster_id
        eligible.sort(key=lambda c: c.cluster_id)
        return eligible

    async def get_all_clusters(self) -> list[ClusterCandidate]:
        """Return all loaded clusters."""
        return list(self._load_clusters())
