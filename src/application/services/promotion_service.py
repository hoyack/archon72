"""Promotion Service for Seed → Motion transitions.

The Promotion Service handles the formal introduction of Motions by Kings.
This is the only path from Motion Seed to Motion:

    Seed Pool → King selects & sponsors → Promotion Service → Admission Gate → Agenda Queue

Key Constraints (from Motion Gates spec):
- C1: Promotion occurs only via formal introduction by a King within a valid realm
- C2: On promotion, create Motion record, link source_seed_refs, emit event
- C3: Promotion does not imply admission (gate still applies)
- I5: Promotion does not rewrite Seeds (Seeds remain intact and queryable)

Constitutional Constraints:
- I1: No Silent Loss - all attempts recorded
- FR9: All outputs through witnessing pipeline
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from src.application.ports.promotion_budget_store import PromotionBudgetStore
from src.application.services.base import LoggingMixin
from src.application.stubs.budget_store_stub import InMemoryBudgetStore
from src.domain.models.motion_seed import (
    KING_REALM_MAP,
    MotionSeed,
    PromotionBudgetTracker,
    PromotionRejectReason,
    RealmAssignment,
    get_king_realm,
    is_king,
    validate_king_realm_match,
)


@dataclass
class PromotionResult:
    """Result of a promotion attempt."""

    success: bool
    motion_id: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    seed_refs: list[str] = field(default_factory=list)
    promoted_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "motion_id": self.motion_id,
            "error_code": self.error_code,
            "error_message": self.error_message,
            "seed_refs": self.seed_refs,
            "promoted_at": self.promoted_at.isoformat() if self.promoted_at else None,
        }


@dataclass
class MotionFromPromotion:
    """A Motion created from promotion of Seed(s).

    This is the output of promotion - a Motion candidate ready for the Admission Gate.
    """

    motion_id: str
    title: str
    realm_assignment: RealmAssignment
    normative_intent: str  # WHAT - required
    constraints: str  # WHAT-level guardrails
    success_criteria: str  # Required
    submitted_at: datetime
    source_seed_refs: list[str]  # Seed IDs for provenance
    promoted_by: str  # King ID who promoted
    promoted_at: datetime

    # Optional co-sponsors for cross-realm
    co_sponsors: list[dict[str, str]] = field(default_factory=list)

    # Metadata
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "motion_id": self.motion_id,
            "title": self.title,
            "realm_assignment": self.realm_assignment.to_dict(),
            "normative_intent": self.normative_intent,
            "constraints": self.constraints,
            "success_criteria": self.success_criteria,
            "submitted_at": self.submitted_at.isoformat(),
            "source_seed_refs": self.source_seed_refs,
            "promoted_by": self.promoted_by,
            "promoted_at": self.promoted_at.isoformat(),
            "co_sponsors": self.co_sponsors,
            "metadata": self.metadata,
        }

    def to_candidate_dict(self) -> dict[str, Any]:
        """Convert to MotionCandidate-compatible dict for Admission Gate."""
        return {
            "motion_id": self.motion_id,
            "title": self.title,
            "realm_assignment": self.realm_assignment.to_dict(),
            "normative_intent": self.normative_intent,
            "constraints": self.constraints,
            "success_criteria": self.success_criteria,
            "submitted_at": self.submitted_at,
            "source_seed_refs": self.source_seed_refs,
            "co_sponsors": self.co_sponsors,
            "metadata": self.metadata,
        }


class _LegacyTrackerAdapter:
    """Adapts legacy PromotionBudgetTracker to PromotionBudgetStore protocol."""

    def __init__(self, tracker: PromotionBudgetTracker):
        self._tracker = tracker

    def can_promote(self, king_id: str, cycle_id: str, count: int = 1) -> bool:
        return self._tracker.can_promote(king_id, cycle_id, count)

    def consume(self, king_id: str, cycle_id: str, count: int = 1) -> int:
        usage = self._tracker.consume(king_id, cycle_id, count)
        return usage.used

    def get_usage(self, king_id: str, cycle_id: str) -> int:
        usage = self._tracker.get_usage(king_id, cycle_id)
        return usage.used

    def get_budget(self, king_id: str) -> int:
        return self._tracker.get_king_budget(king_id)


class PromotionService(LoggingMixin):
    """Service for promoting Motion Seeds to Motions.

    The Promotion Service is the only path from Seed to Motion.
    It enforces:
    - Only Kings can promote
    - King must own the primary realm
    - Cross-realm requires co-sponsors
    - Seeds are not modified (new Motion artifact is created)
    - H1: King promotion budgets per cycle

    The growth equation becomes:
        O(kings × promotion_budget) = O(9 × 3) = 27 max motions per cycle

    Budget Store Options (P1-P4):
    - InMemoryBudgetStore: For testing only (resets on restart)
    - FileBudgetStore: For production single-node (persistent, atomic)
    - RedisBudgetStore: For horizontal scaling (atomic via Lua script)
    """

    def __init__(
        self,
        budget_store: PromotionBudgetStore | None = None,
        budget_tracker: PromotionBudgetTracker | None = None,  # Legacy compat
    ) -> None:
        """Initialize the Promotion service.

        Args:
            budget_store: Budget store implementing PromotionBudgetStore protocol.
                         Preferred for production - supports FileBudgetStore, RedisBudgetStore.
            budget_tracker: Legacy budget tracker (deprecated, for backward compatibility).
                           If budget_store is provided, this is ignored.
        """
        self._init_logger(component="motion_gates")

        # Prefer new budget_store, fall back to legacy tracker
        if budget_store is not None:
            self._budget_store: PromotionBudgetStore = budget_store
            self._legacy_tracker = None
        elif budget_tracker is not None:
            # Wrap legacy tracker in adapter
            self._budget_store = _LegacyTrackerAdapter(budget_tracker)
            self._legacy_tracker = budget_tracker
        else:
            # Default: in-memory store for tests
            self._budget_store = InMemoryBudgetStore()
            self._legacy_tracker = None

    @property
    def budget_tracker(self) -> PromotionBudgetTracker | None:
        """Get the legacy budget tracker for backward compatibility."""
        return self._legacy_tracker

    @property
    def budget_store(self) -> PromotionBudgetStore:
        """Get the budget store."""
        return self._budget_store

    def promote(
        self,
        seeds: list[MotionSeed],
        king_id: str,
        title: str,
        normative_intent: str,
        constraints: str,
        success_criteria: str,
        cycle_id: str,  # Required for H1 budget tracking
        realm_id: str | None = None,
        co_sponsors: list[dict[str, str]] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> tuple[PromotionResult, MotionFromPromotion | None]:
        """Promote one or more Seeds to a Motion.

        Args:
            seeds: List of Seeds to promote (at least one required)
            king_id: ID of the King sponsoring the Motion
            title: Motion title
            normative_intent: WHAT - the normative intent
            constraints: WHAT-level guardrails
            success_criteria: Success criteria
            cycle_id: The cycle identifier (required for H1 budget tracking)
            realm_id: Primary realm (defaults to King's realm)
            co_sponsors: List of co-sponsor dicts for cross-realm
            metadata: Optional metadata

        Returns:
            Tuple of (PromotionResult, MotionFromPromotion or None)
        """
        log = self._log_operation(
            "promote",
            king_id=king_id,
            seed_count=len(seeds),
            cycle_id=cycle_id,
        )
        log.info("promotion_started")

        # Validate at least one seed
        if not seeds:
            log.warning("promotion_failed", reason="no_seeds")
            return (
                PromotionResult(
                    success=False,
                    error_code=PromotionRejectReason.NO_SEEDS.value,
                    error_message="At least one Seed is required for promotion",
                ),
                None,
            )

        # H1: Check promotion budget before proceeding
        if not self._budget_store.can_promote(king_id, cycle_id, count=1):
            used = self._budget_store.get_usage(king_id, cycle_id)
            budget = self._budget_store.get_budget(king_id)
            log.warning(
                "promotion_failed",
                reason="budget_exceeded",
                budget=budget,
                used=used,
            )
            return (
                PromotionResult(
                    success=False,
                    error_code=PromotionRejectReason.PROMOTION_BUDGET_EXCEEDED.value,
                    error_message=(
                        f"King {king_id} has exhausted promotion budget for cycle {cycle_id}: "
                        f"used {used}/{budget}"
                    ),
                ),
                None,
            )

        # Validate king standing
        if not is_king(king_id):
            log.warning("promotion_failed", reason="not_king")
            return (
                PromotionResult(
                    success=False,
                    error_code="NOT_KING",
                    error_message=f"Sponsor {king_id} is not a King. Only Kings may introduce Motions.",
                ),
                None,
            )

        # Determine realm
        king_realm = get_king_realm(king_id)
        primary_realm = realm_id or king_realm

        if primary_realm != king_realm:
            log.warning("promotion_failed", reason="wrong_realm")
            return (
                PromotionResult(
                    success=False,
                    error_code="WRONG_REALM",
                    error_message=f"King {king_id} owns realm {king_realm}, cannot sponsor in {primary_realm}",
                ),
                None,
            )

        # Get King info
        king_info = KING_REALM_MAP.get(king_id, {})
        king_name = king_info.get("name", "Unknown King")

        # Create realm assignment
        realm_assignment = RealmAssignment(
            primary_realm=primary_realm,
            primary_sponsor_id=king_id,
            primary_sponsor_name=king_name,
        )

        # Add co-sponsors if cross-realm
        validated_cosponsors = []
        if co_sponsors:
            for cosponsor in co_sponsors:
                cosponsor_id = cosponsor.get("king_id")
                cosponsor_realm = cosponsor.get("realm_id")

                if not is_king(cosponsor_id):
                    log.warning(
                        "promotion_failed",
                        reason="invalid_cosponsor",
                        cosponsor_id=cosponsor_id,
                    )
                    return (
                        PromotionResult(
                            success=False,
                            error_code="INVALID_COSPONSOR",
                            error_message=f"Co-sponsor {cosponsor_id} is not a King",
                        ),
                        None,
                    )

                if not validate_king_realm_match(cosponsor_id, cosponsor_realm):
                    log.warning(
                        "promotion_failed",
                        reason="cosponsor_wrong_realm",
                        cosponsor_id=cosponsor_id,
                        cosponsor_realm=cosponsor_realm,
                    )
                    return (
                        PromotionResult(
                            success=False,
                            error_code="COSPONSOR_WRONG_REALM",
                            error_message=f"Co-sponsor {cosponsor_id} does not own realm {cosponsor_realm}",
                        ),
                        None,
                    )

                cosponsor_info = KING_REALM_MAP.get(cosponsor_id, {})
                realm_assignment.add_cosponsor(
                    king_id=cosponsor_id,
                    king_name=cosponsor_info.get("name", "Unknown King"),
                    realm_id=cosponsor_realm,
                )
                validated_cosponsors.append(cosponsor)

        # H1: Consume promotion budget (all validations passed)
        new_used = self._budget_store.consume(king_id, cycle_id, count=1)
        budget = self._budget_store.get_budget(king_id)
        log.debug(
            "budget_consumed",
            king_id=king_id,
            cycle_id=cycle_id,
            remaining=budget - new_used,
        )

        # Generate motion ID
        motion_id = f"motion-{uuid4().hex[:12]}"
        now = datetime.now(timezone.utc)

        # Collect seed refs
        seed_refs = [str(seed.seed_id) for seed in seeds]

        # Create Motion from promotion
        motion = MotionFromPromotion(
            motion_id=motion_id,
            title=title,
            realm_assignment=realm_assignment,
            normative_intent=normative_intent,
            constraints=constraints,
            success_criteria=success_criteria,
            submitted_at=now,
            source_seed_refs=seed_refs,
            promoted_by=king_id,
            promoted_at=now,
            co_sponsors=validated_cosponsors,
            metadata=metadata or {},
        )

        # Mark seeds as promoted (but don't modify their content - I5)
        for seed in seeds:
            seed.mark_promoted(motion_id=motion_id, king_id=king_id)

        result = PromotionResult(
            success=True,
            motion_id=motion_id,
            seed_refs=seed_refs,
            promoted_at=now,
        )

        log.info(
            "promotion_completed",
            motion_id=motion_id,
            seed_count=len(seeds),
            cross_realm=realm_assignment.is_cross_realm,
        )

        return result, motion

    def promote_single(
        self,
        seed: MotionSeed,
        king_id: str,
        cycle_id: str,
        title: str | None = None,
        normative_intent: str | None = None,
        constraints: str = "",
        success_criteria: str | None = None,
    ) -> tuple[PromotionResult, MotionFromPromotion | None]:
        """Convenience method to promote a single Seed.

        Uses seed's proposed values as defaults where available.

        Args:
            seed: The Seed to promote
            king_id: ID of the King sponsoring
            cycle_id: The cycle identifier (required for H1 budget tracking)
            title: Motion title (defaults to seed's proposed_title)
            normative_intent: WHAT intent (defaults to seed text)
            constraints: WHAT-level guardrails
            success_criteria: Success criteria

        Returns:
            Tuple of (PromotionResult, MotionFromPromotion or None)
        """
        return self.promote(
            seeds=[seed],
            king_id=king_id,
            cycle_id=cycle_id,
            title=title or seed.proposed_title or "Untitled Motion",
            normative_intent=normative_intent or seed.seed_text,
            constraints=constraints,
            success_criteria=success_criteria
            or "Motion successfully ratified and implemented",
            realm_id=seed.proposed_realm,
        )

    def promote_cluster(
        self,
        seeds: list[MotionSeed],
        king_id: str,
        cycle_id: str,
        title: str,
        normative_intent: str,
        constraints: str,
        success_criteria: str,
        realm_id: str | None = None,
    ) -> tuple[PromotionResult, MotionFromPromotion | None]:
        """Promote a cluster of related Seeds to a single Motion.

        Args:
            seeds: List of Seeds in the cluster
            king_id: ID of the King sponsoring
            cycle_id: The cycle identifier (required for H1 budget tracking)
            title: Motion title
            normative_intent: Unified WHAT intent for the cluster
            constraints: WHAT-level guardrails
            success_criteria: Success criteria
            realm_id: Primary realm (defaults to King's realm)

        Returns:
            Tuple of (PromotionResult, MotionFromPromotion or None)
        """
        log = self._log_operation(
            "promote_cluster",
            king_id=king_id,
            cycle_id=cycle_id,
            seed_count=len(seeds),
        )
        log.info("cluster_promotion_started")

        result, motion = self.promote(
            seeds=seeds,
            king_id=king_id,
            cycle_id=cycle_id,
            title=title,
            normative_intent=normative_intent,
            constraints=constraints,
            success_criteria=success_criteria,
            realm_id=realm_id,
            metadata={"promotion_type": "cluster", "seed_count": len(seeds)},
        )

        if result.success:
            log.info(
                "cluster_promotion_completed",
                motion_id=result.motion_id,
            )
        else:
            log.warning(
                "cluster_promotion_failed",
                error_code=result.error_code,
            )

        return result, motion
