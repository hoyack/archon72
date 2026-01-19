"""Seed Pool Service - Motion Seed storage and management.

The Seed Pool is the central repository for Motion Seeds before promotion.
It provides:
1. Storage and querying of Seeds
2. Conversion from QueuedMotion to MotionSeed
3. Support for King-driven promotion flow
4. Seed clustering and consolidation

This implements the Motion Gates spec:
- Seeds are unbounded (anyone can submit)
- Seeds don't claim agenda time
- Only Kings can promote Seeds to Motions
- Promoted Seeds remain queryable (I5: no rewrite)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from src.application.services.base import LoggingMixin
from src.domain.models.motion_seed import (
    KING_REALM_MAP,
    MotionSeed,
    SeedCluster,
    SeedStatus,
)
from src.domain.models.secretary import QueuedMotion, RecommendationCluster


@dataclass
class SeedPoolStats:
    """Statistics about the Seed Pool."""

    total_seeds: int = 0
    recorded_seeds: int = 0
    clustered_seeds: int = 0
    promoted_seeds: int = 0
    archived_seeds: int = 0
    total_clusters: int = 0
    seeds_by_realm: dict[str, int] = field(default_factory=dict)


class SeedPoolService(LoggingMixin):
    """Service for managing the Motion Seed pool.

    The Seed Pool stores all Seeds and supports:
    - Adding seeds from Secretary output
    - Querying seeds by status, realm, etc.
    - Converting legacy QueuedMotion to MotionSeed
    - Supporting King promotion flow
    """

    def __init__(self, output_dir: Path | None = None) -> None:
        """Initialize the Seed Pool service.

        Args:
            output_dir: Directory for persisting seed data
        """
        self._init_logger(component="motion_gates")
        self._output_dir = output_dir or Path("_bmad-output/seed-pool")
        self._output_dir.mkdir(parents=True, exist_ok=True)

        # In-memory storage (can be replaced with database)
        self._seeds: dict[str, MotionSeed] = {}
        self._clusters: dict[str, SeedCluster] = {}

        # Load persisted seeds if available
        self._load_persisted_seeds()

    def _load_persisted_seeds(self) -> None:
        """Load seeds from disk if available."""
        seeds_file = self._output_dir / "seeds.json"
        if seeds_file.exists():
            try:
                data = json.loads(seeds_file.read_text())
                log = self._log_operation("load_seeds")
                log.info("seeds_loaded", count=len(data.get("seeds", [])))
            except Exception as e:
                log = self._log_operation("load_seeds")
                log.warning("seeds_load_failed", error=str(e))

    def add_seed(self, seed: MotionSeed) -> MotionSeed:
        """Add a new seed to the pool.

        Per spec A1-A2: Accept and record append-only, no gate rejection.

        Args:
            seed: The Motion Seed to add

        Returns:
            The added seed (with any computed metadata)
        """
        log = self._log_operation("add_seed", seed_id=str(seed.seed_id))

        self._seeds[str(seed.seed_id)] = seed
        log.info("seed_added", submitted_by=seed.submitted_by_name)

        return seed

    def add_seed_from_queued_motion(
        self,
        queued_motion: QueuedMotion,
        source_cycle: str,
    ) -> MotionSeed:
        """Convert a legacy QueuedMotion to a MotionSeed and add it.

        This provides backward compatibility with existing Secretary output.

        H5 CONSTRAINT (Critical for explosion protection):
        This method MUST ONLY create MotionSeed records, NEVER Motion records.
        If this method ever creates Motion artifacts, bypass promotion, or
        touch the admission gate, the combinatorial explosion protection is violated.

        The output is always a Seed that:
        - Has status = RECORDED (not PROMOTED)
        - Has no motion_id
        - Requires King promotion to become a Motion

        Args:
            queued_motion: The QueuedMotion from Secretary
            source_cycle: The source Conclave cycle identifier

        Returns:
            The created MotionSeed (NOT a Motion)
        """
        log = self._log_operation(
            "convert_queued_motion",
            queued_motion_id=str(queued_motion.queued_motion_id),
        )

        # Create seed from queued motion
        seed = MotionSeed.create(
            seed_text=f"{queued_motion.title}\n\n{queued_motion.text}\n\nRationale: {queued_motion.rationale}",
            submitted_by=queued_motion.supporting_archons[0]
            if queued_motion.supporting_archons
            else "secretary",
            submitted_by_name=queued_motion.supporting_archons[0]
            if queued_motion.supporting_archons
            else "Automated Secretary",
            proposed_title=queued_motion.title,
            source_cycle=source_cycle,
            source_event="secretary-extraction",
        )

        # Add support signals from supporting archons
        for archon_name in queued_motion.supporting_archons[1:]:
            seed.add_support(
                signaler_id=archon_name.lower().replace(" ", "_"),
                signaler_name=archon_name,
                signaler_rank="unknown",
                signal_type="support",
            )

        # Store provenance
        seed.metadata["source_queued_motion_id"] = str(queued_motion.queued_motion_id)
        seed.metadata["source_cluster_id"] = (
            str(queued_motion.source_cluster_id)
            if queued_motion.source_cluster_id
            else None
        )
        seed.metadata["original_archon_count"] = queued_motion.original_archon_count
        seed.metadata["consensus_level"] = queued_motion.consensus_level.value

        self._seeds[str(seed.seed_id)] = seed
        log.info(
            "queued_motion_converted",
            seed_id=str(seed.seed_id),
            archon_count=queued_motion.original_archon_count,
        )

        return seed

    def add_seeds_from_cluster(
        self,
        cluster: RecommendationCluster,
        source_cycle: str,
    ) -> list[MotionSeed]:
        """Create seeds from a recommendation cluster.

        Each recommendation in the cluster becomes a separate seed,
        maintaining full provenance.

        H5 CONSTRAINT (Critical for explosion protection):
        This method MUST ONLY create MotionSeed records, NEVER Motion records.
        All output seeds have status = RECORDED and require King promotion.

        Args:
            cluster: The recommendation cluster
            source_cycle: The source Conclave cycle identifier

        Returns:
            List of created MotionSeeds (NOT Motions)
        """
        log = self._log_operation(
            "add_from_cluster",
            cluster_id=str(cluster.cluster_id),
        )

        seeds = []
        for rec in cluster.recommendations:
            seed = MotionSeed.create(
                seed_text=rec.summary,
                submitted_by=rec.source.archon_id,
                submitted_by_name=rec.source.archon_name,
                source_cycle=source_cycle,
                source_event="secretary-extraction",
            )
            seed.source_references.append(str(rec.recommendation_id))
            seed.metadata["recommendation_category"] = rec.category.value
            seed.metadata["recommendation_type"] = rec.recommendation_type.value
            seed.metadata["cluster_id"] = str(cluster.cluster_id)
            seed.metadata["cluster_theme"] = cluster.theme

            self._seeds[str(seed.seed_id)] = seed
            seeds.append(seed)

        log.info(
            "cluster_converted",
            seed_count=len(seeds),
            theme=cluster.theme,
        )

        return seeds

    def get_seed(self, seed_id: str) -> MotionSeed | None:
        """Get a seed by ID."""
        return self._seeds.get(seed_id)

    def get_seeds_by_status(self, status: SeedStatus) -> list[MotionSeed]:
        """Get all seeds with a given status."""
        return [s for s in self._seeds.values() if s.status == status]

    def get_seeds_for_promotion(self) -> list[MotionSeed]:
        """Get seeds eligible for promotion (recorded or clustered)."""
        return [
            s
            for s in self._seeds.values()
            if s.status in (SeedStatus.RECORDED, SeedStatus.CLUSTERED)
        ]

    def get_seeds_by_realm_hint(self, realm_id: str) -> list[MotionSeed]:
        """Get seeds with a proposed realm hint."""
        return [
            s
            for s in self._seeds.values()
            if s.proposed_realm == realm_id
            and s.status in (SeedStatus.RECORDED, SeedStatus.CLUSTERED)
        ]

    def get_promoted_seeds(self) -> list[MotionSeed]:
        """Get all seeds that have been promoted to Motions."""
        return [s for s in self._seeds.values() if s.status == SeedStatus.PROMOTED]

    def cluster_seeds(
        self,
        seed_ids: list[str],
        theme: str,
        description: str,
        created_by: str = "consolidator",
    ) -> SeedCluster | None:
        """Create a cluster from a set of seeds.

        Per spec B1-B3: Clustering is non-binding, preserves originals,
        and includes provenance.

        Args:
            seed_ids: List of seed IDs to cluster
            theme: The cluster theme
            description: Cluster description
            created_by: Who created the cluster

        Returns:
            The created cluster, or None if no valid seeds
        """
        log = self._log_operation(
            "cluster_seeds",
            seed_count=len(seed_ids),
            theme=theme,
        )

        # Get and validate seeds
        seeds = [self._seeds.get(sid) for sid in seed_ids]
        valid_seeds = [s for s in seeds if s is not None]

        if not valid_seeds:
            log.warning("cluster_failed", reason="no_valid_seeds")
            return None

        # Create cluster
        cluster = SeedCluster.create(
            theme=theme,
            description=description,
            seed_refs=seed_ids,
            created_by=created_by,
        )

        # Mark seeds as clustered
        for i, seed in enumerate(valid_seeds):
            seed.mark_clustered(cluster.cluster_id, position=i)

        self._clusters[cluster.cluster_id] = cluster

        log.info(
            "cluster_created",
            cluster_id=cluster.cluster_id,
            seed_count=len(valid_seeds),
        )

        return cluster

    def get_cluster(self, cluster_id: str) -> SeedCluster | None:
        """Get a cluster by ID."""
        return self._clusters.get(cluster_id)

    def get_seeds_for_king(self, king_id: str) -> list[MotionSeed]:
        """Get seeds that might be relevant to a King's realm.

        Returns seeds:
        - With a proposed_realm matching the King's realm
        - That are in RECORDED or CLUSTERED status

        Args:
            king_id: The King's archon ID

        Returns:
            List of seeds relevant to this King
        """
        king_info = KING_REALM_MAP.get(king_id)
        if not king_info:
            return []

        king_realm = king_info["realm_id"]
        return self.get_seeds_by_realm_hint(king_realm)

    def get_stats(self) -> SeedPoolStats:
        """Get statistics about the seed pool."""
        stats = SeedPoolStats()

        for seed in self._seeds.values():
            stats.total_seeds += 1

            if seed.status == SeedStatus.RECORDED:
                stats.recorded_seeds += 1
            elif seed.status == SeedStatus.CLUSTERED:
                stats.clustered_seeds += 1
            elif seed.status == SeedStatus.PROMOTED:
                stats.promoted_seeds += 1
            elif seed.status == SeedStatus.ARCHIVED:
                stats.archived_seeds += 1

            if seed.proposed_realm:
                stats.seeds_by_realm[seed.proposed_realm] = (
                    stats.seeds_by_realm.get(seed.proposed_realm, 0) + 1
                )

        stats.total_clusters = len(self._clusters)

        return stats

    def persist(self) -> Path:
        """Persist seed pool to disk.

        Returns:
            Path to the saved data directory
        """
        log = self._log_operation("persist")

        # Save seeds
        seeds_data = {
            "seeds": [s.to_dict() for s in self._seeds.values()],
            "persisted_at": datetime.now(timezone.utc).isoformat(),
        }
        seeds_file = self._output_dir / "seeds.json"
        seeds_file.write_text(json.dumps(seeds_data, indent=2))

        # Save clusters
        clusters_data = {
            "clusters": [c.to_dict() for c in self._clusters.values()],
            "persisted_at": datetime.now(timezone.utc).isoformat(),
        }
        clusters_file = self._output_dir / "clusters.json"
        clusters_file.write_text(json.dumps(clusters_data, indent=2))

        log.info(
            "pool_persisted",
            seed_count=len(self._seeds),
            cluster_count=len(self._clusters),
        )

        return self._output_dir

    def generate_seed_pool_report(self) -> str:
        """Generate a markdown report of the seed pool.

        Returns:
            Markdown-formatted report
        """
        stats = self.get_stats()

        lines = [
            "# Motion Seed Pool Report",
            "",
            f"**Generated:** {datetime.now(timezone.utc).isoformat()}",
            "",
            "## Summary Statistics",
            "",
            f"- **Total Seeds:** {stats.total_seeds}",
            f"- **Recorded (awaiting promotion):** {stats.recorded_seeds}",
            f"- **Clustered:** {stats.clustered_seeds}",
            f"- **Promoted to Motions:** {stats.promoted_seeds}",
            f"- **Archived:** {stats.archived_seeds}",
            f"- **Total Clusters:** {stats.total_clusters}",
            "",
            "## Seeds by Proposed Realm",
            "",
        ]

        if stats.seeds_by_realm:
            for realm, count in sorted(stats.seeds_by_realm.items()):
                lines.append(f"- {realm}: {count}")
        else:
            lines.append("- No realm hints specified")

        lines.extend(["", "---", "", "## Seeds Available for Promotion", ""])

        promotable_seeds = self.get_seeds_for_promotion()
        if promotable_seeds:
            for seed in promotable_seeds[:20]:  # Limit to first 20
                lines.extend(
                    [
                        f"### {seed.proposed_title or 'Untitled Seed'}",
                        "",
                        f"**Seed ID:** `{seed.seed_id}`",
                        f"**Submitted by:** {seed.submitted_by_name}",
                        f"**Status:** {seed.status.value}",
                        f"**Support signals:** {len(seed.support_signals)}",
                        "",
                        "**Content:**",
                        "",
                        f"> {seed.seed_text[:300]}{'...' if len(seed.seed_text) > 300 else ''}",
                        "",
                        "---",
                        "",
                    ]
                )

            if len(promotable_seeds) > 20:
                lines.append(f"*...and {len(promotable_seeds) - 20} more seeds*")
        else:
            lines.append("No seeds currently available for promotion.")

        return "\n".join(lines)
