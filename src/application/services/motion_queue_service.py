"""Motion Queue Service - Bridges Secretary output to Conclave input.

Manages the queue of motions generated from Secretary analysis,
handles endorsements, and formats motions for next Conclave agenda.

Key responsibilities:
1. Store and retrieve queued motions
2. Process endorsements from Archons
3. Format motions for Conclave agenda
4. Track motion lifecycle (pending → promoted → voted)

Constitutional Constraints:
- CT-11: Silent failure destroys legitimacy -> log all operations
- CT-12: Witnessing creates accountability -> full traceability
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from src.domain.models.conclave import (
    AgendaItem,
    ConclavePhase,
    Motion,
    MotionType,
)
from src.domain.models.secretary import (
    QueuedMotion,
    QueuedMotionStatus,
    SecretaryReport,
)

logger = logging.getLogger(__name__)


class MotionQueueService:
    """Manages the motion queue between Conclaves.

    The queue persists across sessions and tracks:
    - Motions generated from Secretary analysis
    - Endorsements received between Conclaves
    - Promotion to Conclave agenda
    """

    def __init__(self, queue_dir: Path | None = None):
        """Initialize the Motion Queue service.

        Args:
            queue_dir: Directory for queue persistence
        """
        self._queue_dir = queue_dir or Path("_bmad-output/motion-queue")
        self._queue_dir.mkdir(parents=True, exist_ok=True)

        self._queue_file = self._queue_dir / "active-queue.json"
        self._archive_dir = self._queue_dir / "archive"
        self._archive_dir.mkdir(exist_ok=True)

        # Load existing queue
        self._queue: list[QueuedMotion] = self._load_queue()

    # =========================================================================
    # Queue Management
    # =========================================================================

    def _load_queue(self) -> list[QueuedMotion]:
        """Load queue from persistent storage."""
        if not self._queue_file.exists():
            return []

        try:
            with open(self._queue_file) as f:
                data = json.load(f)
            return [self._deserialize_motion(m) for m in data.get("motions", [])]
        except Exception as e:
            logger.error(f"Failed to load queue: {e}")
            return []

    def _save_queue(self) -> None:
        """Persist queue to storage."""
        data = {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "motion_count": len(self._queue),
            "motions": [self._serialize_motion(m) for m in self._queue],
        }

        with open(self._queue_file, "w") as f:
            json.dump(data, f, indent=2, default=str)

        logger.debug(f"Saved queue with {len(self._queue)} motions")

    def _serialize_motion(self, motion: QueuedMotion) -> dict:
        """Serialize a QueuedMotion to dict."""
        return {
            "queued_motion_id": str(motion.queued_motion_id),
            "status": motion.status.value,
            "title": motion.title,
            "text": motion.text,
            "rationale": motion.rationale,
            "source_cluster_id": str(motion.source_cluster_id)
            if motion.source_cluster_id
            else None,
            "source_cluster_theme": motion.source_cluster_theme,
            "original_archon_count": motion.original_archon_count,
            "consensus_level": motion.consensus_level.value,
            "supporting_archons": motion.supporting_archons,
            "source_session_id": str(motion.source_session_id)
            if motion.source_session_id
            else None,
            "source_session_name": motion.source_session_name,
            "endorsements": motion.endorsements,
            "endorsement_count": motion.endorsement_count,
            "created_at": motion.created_at.isoformat(),
            "promoted_at": motion.promoted_at.isoformat()
            if motion.promoted_at
            else None,
            "target_conclave_id": str(motion.target_conclave_id)
            if motion.target_conclave_id
            else None,
        }

    def _deserialize_motion(self, data: dict) -> QueuedMotion:
        """Deserialize a dict to QueuedMotion."""
        from src.domain.models.secretary import ConsensusLevel

        return QueuedMotion(
            queued_motion_id=UUID(data["queued_motion_id"]),
            status=QueuedMotionStatus(data["status"]),
            title=data["title"],
            text=data["text"],
            rationale=data["rationale"],
            source_cluster_id=UUID(data["source_cluster_id"])
            if data.get("source_cluster_id")
            else None,
            source_cluster_theme=data.get("source_cluster_theme", ""),
            original_archon_count=data["original_archon_count"],
            consensus_level=ConsensusLevel(data["consensus_level"]),
            supporting_archons=data.get("supporting_archons", []),
            source_session_id=UUID(data["source_session_id"])
            if data.get("source_session_id")
            else None,
            source_session_name=data.get("source_session_name", ""),
            endorsements=data.get("endorsements", []),
            endorsement_count=data.get("endorsement_count", 0),
            created_at=datetime.fromisoformat(data["created_at"]),
            promoted_at=datetime.fromisoformat(data["promoted_at"])
            if data.get("promoted_at")
            else None,
            target_conclave_id=UUID(data["target_conclave_id"])
            if data.get("target_conclave_id")
            else None,
        )

    # =========================================================================
    # Queue Operations
    # =========================================================================

    def import_from_report(self, report: SecretaryReport) -> int:
        """Import motions from a Secretary report into the queue.

        Args:
            report: SecretaryReport containing motion_queue

        Returns:
            Number of motions imported
        """
        imported = 0

        for motion in report.motion_queue:
            # Check for duplicates (same source cluster)
            existing = self._find_by_cluster(motion.source_cluster_id)
            if existing:
                logger.debug(
                    f"Skipping duplicate motion from cluster {motion.source_cluster_id}"
                )
                continue

            self._queue.append(motion)
            imported += 1

        if imported > 0:
            self._save_queue()
            logger.info(f"Imported {imported} motions from report {report.report_id}")

        return imported

    def _find_by_cluster(self, cluster_id: UUID | None) -> QueuedMotion | None:
        """Find a queued motion by source cluster ID."""
        if not cluster_id:
            return None

        for motion in self._queue:
            if motion.source_cluster_id == cluster_id:
                return motion
        return None

    def get_motion(self, motion_id: UUID) -> QueuedMotion | None:
        """Get a motion by ID."""
        for motion in self._queue:
            if motion.queued_motion_id == motion_id:
                return motion
        return None

    def get_all_pending(self) -> list[QueuedMotion]:
        """Get all pending motions."""
        return [
            m
            for m in self._queue
            if m.status in (QueuedMotionStatus.PENDING, QueuedMotionStatus.ENDORSED)
        ]

    def get_queue_summary(self) -> dict:
        """Get summary statistics for the queue."""
        by_status = {}
        by_consensus = {}

        for motion in self._queue:
            status = motion.status.value
            by_status[status] = by_status.get(status, 0) + 1

            level = motion.consensus_level.value
            by_consensus[level] = by_consensus.get(level, 0) + 1

        return {
            "total_motions": len(self._queue),
            "by_status": by_status,
            "by_consensus": by_consensus,
            "pending_count": len(self.get_all_pending()),
        }

    # =========================================================================
    # Endorsement Processing
    # =========================================================================

    def endorse_motion(
        self,
        motion_id: UUID,
        archon_id: str,  # noqa: ARG002 - reserved for future audit trail
        archon_name: str,
    ) -> bool:
        """Add an endorsement to a queued motion.

        Args:
            motion_id: UUID of the motion to endorse
            archon_id: ID of the endorsing Archon
            archon_name: Name of the endorsing Archon

        Returns:
            True if endorsement was added, False if already endorsed or not found
        """
        motion = self.get_motion(motion_id)
        if not motion:
            logger.warning(f"Motion {motion_id} not found for endorsement")
            return False

        if archon_name in motion.endorsements:
            logger.debug(f"{archon_name} already endorsed motion {motion_id}")
            return False

        if archon_name in motion.supporting_archons:
            logger.debug(f"{archon_name} was original supporter of motion {motion_id}")
            return False

        motion.add_endorsement(archon_name)
        self._save_queue()

        logger.info(
            f"{archon_name} endorsed motion '{motion.title}' (now {motion.endorsement_count} endorsements)"
        )
        return True

    # =========================================================================
    # Conclave Integration
    # =========================================================================

    def format_for_conclave(
        self,
        motion: QueuedMotion,
        proposer_id: str = "secretary",
        proposer_name: str = "Automated Secretary",
    ) -> Motion:
        """Format a queued motion as a Conclave Motion object.

        Args:
            motion: The QueuedMotion to format
            proposer_id: ID of the proposer (default: secretary)
            proposer_name: Name of the proposer

        Returns:
            Motion object ready for Conclave session
        """
        # Build motion text with provenance
        full_text = f"""{motion.text}

---
**Provenance:**
- Derived from {motion.original_archon_count} Archon recommendations
- Source Conclave: {motion.source_session_name}
- Endorsements: {motion.endorsement_count}
- Original Supporters: {", ".join(motion.supporting_archons)}
"""

        if motion.endorsements:
            full_text += f"- Additional Endorsers: {', '.join(motion.endorsements)}\n"

        return Motion.create(
            motion_type=MotionType.POLICY,
            title=motion.title,
            text=full_text,
            proposer_id=proposer_id,
            proposer_name=proposer_name,
        )

    def format_as_agenda_item(
        self,
        motion: QueuedMotion,
    ) -> AgendaItem:
        """Format a queued motion as a Conclave AgendaItem.

        Args:
            motion: The QueuedMotion to format

        Returns:
            AgendaItem for Conclave agenda
        """
        description = (
            f"Motion derived from {motion.original_archon_count} Archon recommendations "
            f"in {motion.source_session_name}. "
            f"Consensus level: {motion.consensus_level.value}. "
            f"Additional endorsements: {motion.endorsement_count}."
        )

        return AgendaItem.create(
            phase=ConclavePhase.NEW_BUSINESS,
            title=motion.title,
            description=description,
            presenter_id="secretary",
            presenter_name="Automated Secretary",
        )

    def generate_agenda_items(
        self,
        max_items: int = 5,
        min_consensus: str = "medium",
    ) -> list[AgendaItem]:
        """Generate agenda items from the queue for next Conclave.

        Args:
            max_items: Maximum number of items to include
            min_consensus: Minimum consensus level (critical, high, medium, low)

        Returns:
            List of AgendaItems sorted by priority
        """
        # Map string to level order for comparison
        level_order = ["critical", "high", "medium", "low", "single"]
        min_index = level_order.index(min_consensus)

        # Filter by status and consensus
        eligible = [
            m
            for m in self._queue
            if m.status in (QueuedMotionStatus.PENDING, QueuedMotionStatus.ENDORSED)
            and level_order.index(m.consensus_level.value) <= min_index
        ]

        # Sort by priority:
        # 1. Endorsement count (descending)
        # 2. Original archon count (descending)
        # 3. Consensus level (descending)
        eligible.sort(
            key=lambda m: (
                -m.endorsement_count,
                -m.original_archon_count,
                -level_order.index(m.consensus_level.value),
            )
        )

        # Take top N
        selected = eligible[:max_items]

        return [self.format_as_agenda_item(m) for m in selected]

    def promote_to_conclave(
        self,
        motion_id: UUID,
        target_conclave_id: UUID,
    ) -> Motion | None:
        """Promote a queued motion to a Conclave session.

        Args:
            motion_id: UUID of the motion to promote
            target_conclave_id: UUID of the target Conclave

        Returns:
            The formatted Motion, or None if not found
        """
        motion = self.get_motion(motion_id)
        if not motion:
            logger.warning(f"Motion {motion_id} not found for promotion")
            return None

        # Update status
        motion.status = QueuedMotionStatus.PROMOTED
        motion.promoted_at = datetime.now(timezone.utc)
        motion.target_conclave_id = target_conclave_id

        self._save_queue()

        logger.info(
            f"Promoted motion '{motion.title}' to Conclave {target_conclave_id}"
        )

        return self.format_for_conclave(motion)

    # =========================================================================
    # Lifecycle Management
    # =========================================================================

    def mark_voted(
        self,
        motion_id: UUID,
        passed: bool,
        vote_details: dict | None = None,
    ) -> None:
        """Mark a motion as having been voted on.

        Args:
            motion_id: UUID of the voted motion
            passed: Whether the motion passed
            vote_details: Optional vote count details
        """
        motion = self.get_motion(motion_id)
        if not motion:
            return

        # Archive the motion
        archive_data = {
            **self._serialize_motion(motion),
            "voted_at": datetime.now(timezone.utc).isoformat(),
            "passed": passed,
            "vote_details": vote_details,
        }

        archive_file = self._archive_dir / f"{motion_id}.json"
        with open(archive_file, "w") as f:
            json.dump(archive_data, f, indent=2)

        # Remove from active queue
        self._queue = [m for m in self._queue if m.queued_motion_id != motion_id]
        self._save_queue()

        status = "PASSED" if passed else "FAILED"
        logger.info(f"Archived motion '{motion.title}' - {status}")

    def defer_motion(
        self,
        motion_id: UUID,
        reason: str = "",
    ) -> bool:
        """Defer a motion to a later Conclave.

        Args:
            motion_id: UUID of the motion to defer
            reason: Optional reason for deferral

        Returns:
            True if deferred, False if not found
        """
        motion = self.get_motion(motion_id)
        if not motion:
            return False

        motion.status = QueuedMotionStatus.DEFERRED
        self._save_queue()

        logger.info(f"Deferred motion '{motion.title}': {reason}")
        return True

    def withdraw_motion(
        self,
        motion_id: UUID,
        reason: str = "",
    ) -> bool:
        """Withdraw a motion from the queue.

        Args:
            motion_id: UUID of the motion to withdraw
            reason: Optional reason for withdrawal

        Returns:
            True if withdrawn, False if not found
        """
        motion = self.get_motion(motion_id)
        if not motion:
            return False

        motion.status = QueuedMotionStatus.WITHDRAWN
        self._save_queue()

        logger.info(f"Withdrew motion '{motion.title}': {reason}")
        return True
