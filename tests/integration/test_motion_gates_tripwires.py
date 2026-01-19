"""H2: Boundary Tripwire Integration Tests for Motion Gates.

These tests verify the fundamental boundaries of the Motion Gates system:
1. Seeds never become Motions without King promotion
2. Budget is consumed on each promotion
3. Admission Gate only processes Motions (not Seeds)
4. Growth is bounded by O(kings × promotion_budget)

Per the Motion Gates Hardening Spec (H2):
> If any test fails, the explosion protection is compromised.
"""

from datetime import datetime, timezone

from src.application.services.admission_gate_service import (
    AdmissionGateService,
    MotionCandidate,
)
from src.application.services.promotion_service import PromotionService
from src.application.services.seed_pool_service import SeedPoolService
from src.domain.models.motion_seed import (
    DEFAULT_KING_PROMOTION_BUDGET,
    KING_IDS,
    KING_REALM_MAP,
    MotionSeed,
    PromotionBudgetTracker,
    SeedStatus,
    get_king_realm,
)

# =============================================================================
# H2 Tripwire Test 1: Seeds never touch Motion creation path directly
# =============================================================================


class TestSeedMotionBoundary:
    """Verify that Seeds cannot become Motions without King promotion."""

    def test_seed_creation_never_creates_motion(self) -> None:
        """Creating Seeds should never create Motion records.

        Tripwire: If this fails, Seeds are bypassing the promotion gate.
        """
        # Create many seeds
        seeds = []
        for i in range(100):
            seed = MotionSeed.create(
                seed_text=f"Seed proposal {i}",
                submitted_by=f"archon-{i}",
                submitted_by_name=f"Archon {i}",
            )
            seeds.append(seed)

        # Verify none are promoted
        for seed in seeds:
            assert seed.status == SeedStatus.RECORDED
            assert seed.promoted_to_motion_id is None
            assert seed.promoted_at is None
            assert seed.promoted_by is None

    def test_seed_pool_operations_dont_promote(self, tmp_path) -> None:
        """SeedPool operations (add, cluster, query) never promote to Motion.

        Tripwire: If this fails, SeedPool is leaking into Motion creation.
        """
        pool = SeedPoolService(output_dir=tmp_path / "pool")

        # Add seeds
        seeds = []
        for i in range(50):
            seed = MotionSeed.create(
                seed_text=f"Pool seed {i}",
                submitted_by=f"archon-{i}",
                submitted_by_name=f"Archon {i}",
            )
            pool.add_seed(seed)
            seeds.append(seed)

        # Cluster some seeds
        pool.cluster_seeds(
            seed_ids=[str(seeds[0].seed_id), str(seeds[1].seed_id)],
            theme="Test Theme",
            description="Test cluster",
        )

        # Query seeds
        promotable = pool.get_seeds_for_promotion()
        stats = pool.get_stats()

        # Verify no promotions occurred (seeds are promotable but not promoted)
        assert len(promotable) > 0, "Seeds should be available for promotion"
        assert stats.promoted_seeds == 0
        for seed in seeds:
            assert seed.status in (SeedStatus.RECORDED, SeedStatus.CLUSTERED)
            assert seed.promoted_to_motion_id is None


# =============================================================================
# H2 Tripwire Test 2: Promotion consumes King budget
# =============================================================================


class TestPromotionBudgetConsumption:
    """Verify that each promotion consumes budget."""

    def test_promotion_consumes_king_budget(self) -> None:
        """Each successful promotion must decrement the King's budget.

        Tripwire: If budget doesn't decrement, explosion protection fails.
        """
        king_id = list(KING_IDS)[0]
        realm_id = get_king_realm(king_id)
        cycle_id = "test-cycle"

        tracker = PromotionBudgetTracker(default_budget=5)
        service = PromotionService(budget_tracker=tracker)

        # Track budget before
        initial_usage = tracker.get_usage(king_id, cycle_id)
        assert initial_usage.used == 0
        assert initial_usage.remaining == 5

        # Promote 3 seeds
        for i in range(3):
            seed = MotionSeed.create(
                seed_text=f"Budget test seed {i}",
                submitted_by="archon",
                submitted_by_name="Test Archon",
                proposed_realm=realm_id,
            )
            result, _ = service.promote(
                seeds=[seed],
                king_id=king_id,
                cycle_id=cycle_id,
                title=f"Motion {i}",
                normative_intent="Test intent",
                constraints="",
                success_criteria="Done",
            )
            assert result.success is True

        # Verify budget consumed
        final_usage = tracker.get_usage(king_id, cycle_id)
        assert final_usage.used == 3
        assert final_usage.remaining == 2

    def test_budget_blocks_excess_promotions(self) -> None:
        """Budget exhaustion must block further promotions.

        Tripwire: If this fails, kings can create unlimited motions.
        """
        king_id = list(KING_IDS)[0]
        realm_id = get_king_realm(king_id)
        cycle_id = "test-cycle"

        # Budget of exactly 2
        tracker = PromotionBudgetTracker(default_budget=2)
        service = PromotionService(budget_tracker=tracker)

        # Exhaust budget
        for i in range(2):
            seed = MotionSeed.create(
                seed_text=f"Seed {i}",
                submitted_by="archon",
                submitted_by_name="Test Archon",
                proposed_realm=realm_id,
            )
            result, _ = service.promote(
                seeds=[seed],
                king_id=king_id,
                cycle_id=cycle_id,
                title=f"Motion {i}",
                normative_intent="Intent",
                constraints="",
                success_criteria="Done",
            )
            assert result.success is True

        # Third promotion MUST fail
        seed = MotionSeed.create(
            seed_text="Excess seed",
            submitted_by="archon",
            submitted_by_name="Test Archon",
            proposed_realm=realm_id,
        )
        result, motion = service.promote(
            seeds=[seed],
            king_id=king_id,
            cycle_id=cycle_id,
            title="Excess Motion",
            normative_intent="Intent",
            constraints="",
            success_criteria="Done",
        )
        assert result.success is False
        assert motion is None
        assert "budget" in result.error_code.lower()


# =============================================================================
# H2 Tripwire Test 3: Admission Gate receives only Motions
# =============================================================================


class TestAdmissionGateBoundary:
    """Verify Admission Gate only processes Motion candidates."""

    def test_admission_gate_requires_motion_candidate(self) -> None:
        """Gate must receive MotionCandidate, not MotionSeed.

        Tripwire: If Seeds pass through gate, the separation is broken.
        """
        gate = AdmissionGateService()

        # This should be a MotionCandidate, not a MotionSeed
        king_id = list(KING_IDS)[0]
        candidate = MotionCandidate(
            motion_id="motion-test",
            title="Test Motion",
            realm_assignment={
                "primary_realm": get_king_realm(king_id),
                "primary_sponsor_id": king_id,
                "primary_sponsor_name": KING_REALM_MAP[king_id]["name"],
            },
            normative_intent="The Conclave SHALL establish standards",
            constraints="None",
            success_criteria="Standards adopted",
            submitted_at=datetime.now(timezone.utc),
            source_seed_refs=["seed-1"],
        )

        record = gate.evaluate(candidate)

        # Gate processed the Motion candidate
        assert record is not None
        assert record.motion_id == "motion-test"

    def test_gate_validates_king_standing(self) -> None:
        """Gate must verify Motion has valid King sponsor.

        Tripwire: If non-Kings can sponsor, the King gate is bypassed.
        """
        gate = AdmissionGateService()

        # Try with non-king sponsor
        candidate = MotionCandidate(
            motion_id="motion-invalid",
            title="Invalid Motion",
            realm_assignment={
                "primary_realm": "realm_privacy_discretion_services",
                "primary_sponsor_id": "not-a-king-id",
                "primary_sponsor_name": "Fake King",
            },
            normative_intent="Some intent",
            constraints="",
            success_criteria="Some criteria",
            submitted_at=datetime.now(timezone.utc),
            source_seed_refs=[],
        )

        record = gate.evaluate(candidate)

        # Must be rejected - non-king sponsor
        assert record.standing_valid is False
        assert len(record.rejection_reasons) > 0


# =============================================================================
# H2 Tripwire Test 4: Combinatorial growth is bounded
# =============================================================================


class TestCombinatorialGrowthBound:
    """Verify growth is bounded by O(kings × promotion_budget)."""

    def test_combinatorial_growth_bounded(self) -> None:
        """Given N seeds, max Motions ≤ kings × budget per cycle.

        Tripwire: If this fails, the explosion protection is broken.
        """
        cycle_id = "bounded-cycle"

        # Use default budget
        tracker = PromotionBudgetTracker(default_budget=DEFAULT_KING_PROMOTION_BUDGET)
        service = PromotionService(budget_tracker=tracker)

        # Calculate max possible motions
        num_kings = len(KING_IDS)
        max_motions = num_kings * DEFAULT_KING_PROMOTION_BUDGET

        # Create MANY more seeds than max motions
        num_seeds = max_motions * 10
        seeds_per_king = {}

        for i, king_id in enumerate(KING_IDS):
            realm_id = get_king_realm(king_id)
            seeds_per_king[king_id] = []
            for j in range(num_seeds // num_kings):
                seed = MotionSeed.create(
                    seed_text=f"Seed {i}-{j}",
                    submitted_by="archon",
                    submitted_by_name="Test Archon",
                    proposed_realm=realm_id,
                )
                seeds_per_king[king_id].append(seed)

        # Try to promote all seeds (many will fail due to budget)
        total_promotions = 0
        for king_id, seeds in seeds_per_king.items():
            realm_id = get_king_realm(king_id)
            for seed in seeds:
                result, _ = service.promote(
                    seeds=[seed],
                    king_id=king_id,
                    cycle_id=cycle_id,
                    title="Test Motion",
                    normative_intent="Intent",
                    constraints="",
                    success_criteria="Done",
                )
                if result.success:
                    total_promotions += 1

        # CRITICAL: Total promotions must be bounded
        assert total_promotions <= max_motions, (
            f"Explosion protection failed: {total_promotions} motions created, "
            f"max allowed is {max_motions}"
        )

        # Verify we hit the expected ceiling
        assert total_promotions == max_motions, (
            f"Expected exactly {max_motions} motions, got {total_promotions}"
        )

    def test_growth_equation_verified(self) -> None:
        """Verify the growth equation: O(kings × promotion_budget).

        Formula: max_motions = |KING_IDS| × DEFAULT_KING_PROMOTION_BUDGET
        Expected: 9 kings × 3 budget = 27 max motions per cycle
        """
        num_kings = len(KING_IDS)
        budget = DEFAULT_KING_PROMOTION_BUDGET
        max_motions = num_kings * budget

        # Verify constants match spec
        assert num_kings == 9, "Must have exactly 9 Kings"
        assert budget == 3, "Default budget should be 3"
        assert max_motions == 27, "Max motions per cycle should be 27"


# =============================================================================
# H5 Tripwire Test: Backward Compatibility Shim
# =============================================================================


class TestBackwardCompatibilityShim:
    """H5: Verify backward compat shim only creates Seeds, never Motions."""

    def test_h5_queued_motion_shim_creates_only_seeds(self, tmp_path) -> None:
        """add_seed_from_queued_motion must only create Seeds, not Motions.

        Tripwire: If this creates Motion records, explosion protection is violated.
        """
        from uuid import uuid4

        from src.domain.models.secretary import ConsensusLevel, QueuedMotion

        pool = SeedPoolService(output_dir=tmp_path / "pool")

        # Create a QueuedMotion (legacy format)
        queued_motion = QueuedMotion(
            queued_motion_id=uuid4(),
            title="Legacy Motion from Secretary",
            text="This is a motion extracted by the Secretary",
            rationale="High consensus among archons",
            supporting_archons=["Archon Alpha", "Archon Beta", "Archon Gamma"],
            original_archon_count=3,
            consensus_level=ConsensusLevel.MEDIUM,  # 3 archons = MEDIUM level
        )

        # Use the backward compat shim
        seed = pool.add_seed_from_queued_motion(
            queued_motion=queued_motion,
            source_cycle="legacy-cycle-1",
        )

        # CRITICAL ASSERTIONS (H5 compliance):
        # 1. Output is a MotionSeed, not a Motion
        assert isinstance(seed, MotionSeed)

        # 2. Status is RECORDED (not PROMOTED)
        assert seed.status == SeedStatus.RECORDED

        # 3. No motion_id set
        assert seed.promoted_to_motion_id is None

        # 4. No promotion timestamp
        assert seed.promoted_at is None

        # 5. No promoting King
        assert seed.promoted_by is None

        # 6. Seed text preserved
        assert queued_motion.title in seed.seed_text
        assert queued_motion.text in seed.seed_text

        # 7. Provenance tracked
        assert seed.metadata.get("source_queued_motion_id") == str(
            queued_motion.queued_motion_id
        )

    def test_h5_cluster_shim_creates_only_seeds(self, tmp_path) -> None:
        """add_seeds_from_cluster must only create Seeds, not Motions.

        Tripwire: If this creates Motion records, explosion protection is violated.
        """
        from src.domain.models.secretary import (
            ExtractedRecommendation,
            RecommendationCategory,
            RecommendationCluster,
            RecommendationType,
            SourceReference,
        )

        pool = SeedPoolService(output_dir=tmp_path / "pool")

        # Create extracted recommendations for the cluster
        rec1 = ExtractedRecommendation.create(
            source=SourceReference.create(
                archon_id="archon-1",
                archon_name="Archon One",
                archon_rank="Senator",
                line_number=1,
                timestamp=datetime.now(timezone.utc),
                raw_text="Implement privacy controls",
            ),
            category=RecommendationCategory.IMPLEMENT,
            recommendation_type=RecommendationType.POLICY,
            summary="Implement privacy controls",
            keywords=["privacy", "controls"],
        )

        rec2 = ExtractedRecommendation.create(
            source=SourceReference.create(
                archon_id="archon-2",
                archon_name="Archon Two",
                archon_rank="Senator",
                line_number=2,
                timestamp=datetime.now(timezone.utc),
                raw_text="Add data encryption",
            ),
            category=RecommendationCategory.IMPLEMENT,
            recommendation_type=RecommendationType.POLICY,
            summary="Add data encryption",
            keywords=["encryption", "data"],
        )

        # Create a recommendation cluster
        cluster = RecommendationCluster.create(
            theme="Privacy Improvements",
            canonical_summary="Improve privacy through controls and encryption",
            category=RecommendationCategory.IMPLEMENT,
            recommendation_type=RecommendationType.POLICY,
            keywords=["privacy", "encryption", "controls"],
        )
        cluster.add_recommendation(rec1)
        cluster.add_recommendation(rec2)

        # Use the cluster shim
        seeds = pool.add_seeds_from_cluster(
            cluster=cluster,
            source_cycle="cluster-cycle-1",
        )

        # CRITICAL ASSERTIONS (H5 compliance):
        assert len(seeds) == 2

        for seed in seeds:
            # 1. Output is a MotionSeed
            assert isinstance(seed, MotionSeed)

            # 2. Status is RECORDED
            assert seed.status == SeedStatus.RECORDED

            # 3. No motion association
            assert seed.promoted_to_motion_id is None
            assert seed.promoted_at is None
            assert seed.promoted_by is None

        # 4. Pool stats show no promotions
        stats = pool.get_stats()
        assert stats.promoted_seeds == 0


# =============================================================================
# End-to-End Integration Test
# =============================================================================


class TestMotionGatesEndToEnd:
    """End-to-end test of the complete Motion Gates pipeline."""

    def test_full_pipeline_seed_to_motion(self, tmp_path) -> None:
        """Test complete flow: Seed → Pool → King Promotion → Motion.

        This validates the entire integration works correctly.
        """
        # Setup
        pool = SeedPoolService(output_dir=tmp_path / "pool")
        tracker = PromotionBudgetTracker()
        promotion = PromotionService(budget_tracker=tracker)
        gate = AdmissionGateService()

        king_id = list(KING_IDS)[0]
        realm_id = get_king_realm(king_id)
        cycle_id = "e2e-cycle"

        # Step 1: Create and add seeds to pool
        seed = MotionSeed.create(
            seed_text="Establish privacy standards for data handling",
            submitted_by="archon-1",
            submitted_by_name="Test Archon",
            proposed_realm=realm_id,
            proposed_title="Privacy Standards Motion",
        )
        pool.add_seed(seed)

        # Verify seed is in pool
        assert pool.get_seed(str(seed.seed_id)) is not None
        assert seed.status == SeedStatus.RECORDED

        # Step 2: King promotes the seed
        result, motion = promotion.promote(
            seeds=[seed],
            king_id=king_id,
            cycle_id=cycle_id,
            title="Privacy Standards Motion",
            normative_intent="The Conclave SHALL establish privacy standards",
            constraints="Must not compromise usability",
            success_criteria="Standards adopted by all realms",
        )

        # Verify promotion succeeded
        assert result.success is True
        assert motion is not None
        assert seed.status == SeedStatus.PROMOTED
        assert seed.promoted_to_motion_id == motion.motion_id

        # Step 3: Motion goes through admission gate
        candidate = MotionCandidate(
            motion_id=motion.motion_id,
            title=motion.title,
            realm_assignment=motion.realm_assignment.to_dict(),
            normative_intent=motion.normative_intent,
            constraints=motion.constraints,
            success_criteria=motion.success_criteria,
            submitted_at=motion.submitted_at,
            source_seed_refs=motion.source_seed_refs,
        )

        record = gate.evaluate(candidate)

        # Verify admission
        assert record.status.value == "admitted"
        assert record.structural_valid is True
        assert record.standing_valid is True
        assert record.content_valid is True

        # Step 4: Verify budget consumed
        usage = tracker.get_usage(king_id, cycle_id)
        assert usage.used == 1
        assert usage.remaining == DEFAULT_KING_PROMOTION_BUDGET - 1


# =============================================================================
# P3 Tripwire Test: Concurrency Atomicity
# =============================================================================


class TestConcurrencyAtomicity:
    """P3: Verify budget consumption is atomic under concurrent promotion attempts."""

    def test_p3_concurrent_promotions_respect_budget(self, tmp_path) -> None:
        """With budget=3, 10 concurrent promotions should yield exactly 3 successes.

        Tripwire: If more than 3 succeed, atomicity is broken and explosion protection fails.
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed

        from src.infrastructure.adapters.persistence.budget_store import (
            InMemoryBudgetStore,
        )

        # Use in-memory store with threading lock (test atomicity)
        store = InMemoryBudgetStore(default_budget=3)
        service = PromotionService(budget_store=store)

        king_id = list(KING_IDS)[0]
        realm_id = get_king_realm(king_id)
        cycle_id = "concurrent-test-cycle"

        def attempt_promotion(attempt_id: int) -> bool:
            """Attempt a single promotion, return True if successful."""
            seed = MotionSeed.create(
                seed_text=f"Concurrent seed {attempt_id}",
                submitted_by="archon",
                submitted_by_name="Test Archon",
                proposed_realm=realm_id,
            )
            result, _ = service.promote(
                seeds=[seed],
                king_id=king_id,
                cycle_id=cycle_id,
                title=f"Concurrent Motion {attempt_id}",
                normative_intent="Test intent",
                constraints="",
                success_criteria="Done",
            )
            return result.success

        # Spawn 10 concurrent promotion attempts
        num_attempts = 10
        results = []

        with ThreadPoolExecutor(max_workers=num_attempts) as executor:
            futures = [
                executor.submit(attempt_promotion, i) for i in range(num_attempts)
            ]
            for future in as_completed(futures):
                results.append(future.result())

        # Count successes and failures
        successes = sum(1 for r in results if r)
        failures = sum(1 for r in results if not r)

        # CRITICAL ASSERTION (P3 compliance):
        # Exactly 3 should succeed (budget), 7 should fail
        assert successes == 3, (
            f"Atomicity violation: {successes} promotions succeeded, "
            f"expected exactly 3 (budget). Explosion protection may be compromised."
        )
        assert failures == 7, f"Expected 7 failures, got {failures}"

    def test_p3_file_store_concurrent_atomicity(self, tmp_path) -> None:
        """P3: FileBudgetStore maintains atomicity under concurrent access.

        Tripwire: Verifies file locking prevents race conditions.
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed

        from src.infrastructure.adapters.persistence.budget_store import (
            FileBudgetStore,
            PromotionBudgetExceededError,
        )

        # Use file-backed store
        store = FileBudgetStore(
            ledger_dir=tmp_path / "budget-ledger",
            default_budget=3,
        )
        service = PromotionService(budget_store=store)

        king_id = list(KING_IDS)[0]
        realm_id = get_king_realm(king_id)
        cycle_id = "file-concurrent-cycle"

        def attempt_promotion(attempt_id: int) -> bool:
            """Attempt a single promotion, return True if successful."""
            seed = MotionSeed.create(
                seed_text=f"File concurrent seed {attempt_id}",
                submitted_by="archon",
                submitted_by_name="Test Archon",
                proposed_realm=realm_id,
            )
            try:
                result, _ = service.promote(
                    seeds=[seed],
                    king_id=king_id,
                    cycle_id=cycle_id,
                    title=f"File Concurrent Motion {attempt_id}",
                    normative_intent="Test intent",
                    constraints="",
                    success_criteria="Done",
                )
                return result.success
            except PromotionBudgetExceededError:
                # Race condition: passed can_promote but lost the consume race
                # This is correct atomicity behavior
                return False

        # Spawn 10 concurrent promotion attempts
        num_attempts = 10
        results = []

        with ThreadPoolExecutor(max_workers=num_attempts) as executor:
            futures = [
                executor.submit(attempt_promotion, i) for i in range(num_attempts)
            ]
            for future in as_completed(futures):
                results.append(future.result())

        successes = sum(1 for r in results if r)

        # CRITICAL ASSERTION: File store must also enforce atomicity
        assert successes == 3, (
            f"FileBudgetStore atomicity violation: {successes} promotions succeeded, "
            f"expected exactly 3. File locking may be broken."
        )

        # Verify persisted state matches
        final_usage = store.get_usage(king_id, cycle_id)
        assert final_usage == 3, f"Persisted usage should be 3, got {final_usage}"

    def test_p2_file_store_survives_restart(self, tmp_path) -> None:
        """P2: Budget usage persists across store instances (simulated restart).

        Tripwire: If 4th promotion succeeds after 'restart', persistence is broken.
        """
        from src.infrastructure.adapters.persistence.budget_store import (
            FileBudgetStore,
        )

        ledger_dir = tmp_path / "restart-test-ledger"
        king_id = list(KING_IDS)[0]
        realm_id = get_king_realm(king_id)
        cycle_id = "restart-test-cycle"

        # First "session" - use 3 promotions (exhaust budget)
        store1 = FileBudgetStore(ledger_dir=ledger_dir, default_budget=3)
        service1 = PromotionService(budget_store=store1)

        for i in range(3):
            seed = MotionSeed.create(
                seed_text=f"Pre-restart seed {i}",
                submitted_by="archon",
                submitted_by_name="Test Archon",
                proposed_realm=realm_id,
            )
            result, _ = service1.promote(
                seeds=[seed],
                king_id=king_id,
                cycle_id=cycle_id,
                title=f"Pre-restart Motion {i}",
                normative_intent="Test",
                constraints="",
                success_criteria="Done",
            )
            assert result.success is True

        # "Restart" - create new store instance pointing to same ledger
        store2 = FileBudgetStore(ledger_dir=ledger_dir, default_budget=3)
        service2 = PromotionService(budget_store=store2)

        # Attempt 4th promotion - MUST fail (budget exhausted before restart)
        seed = MotionSeed.create(
            seed_text="Post-restart seed",
            submitted_by="archon",
            submitted_by_name="Test Archon",
            proposed_realm=realm_id,
        )
        result, _ = service2.promote(
            seeds=[seed],
            king_id=king_id,
            cycle_id=cycle_id,
            title="Post-restart Motion",
            normative_intent="Test",
            constraints="",
            success_criteria="Done",
        )

        # CRITICAL ASSERTION (P2 compliance):
        # 4th promotion must fail - budget persisted across restart
        assert result.success is False, (
            "Persistence violation: 4th promotion succeeded after restart. "
            "Budget was not persisted to disk."
        )
        assert "budget" in result.error_code.lower()
