"""Unit tests for Motion Gates services.

Tests the Motion Seed → Motion pipeline:
- MotionSeed creation and lifecycle
- AdmissionGate validation
- PromotionService King-sponsored transitions
- SeedPoolService management

Per Motion Gates spec (docs/spikes/motion-gates.md):
- Speech is unlimited; Agenda is scarce
- Only Kings can introduce Motions
- Admission Gate validates Motions, not Seeds
"""

from datetime import datetime, timezone

import pytest

from src.application.services.admission_gate_service import (
    AdmissionGateService,
    MotionCandidate,
)
from src.application.services.promotion_service import (
    PromotionService,
)
from src.application.services.seed_pool_service import (
    SeedPoolService,
)
from src.domain.models.motion_seed import (
    KING_IDS,
    KING_REALM_MAP,
    AdmissionRejectReason,
    AdmissionStatus,
    MotionSeed,
    PromotionBudgetTracker,
    PromotionRejectReason,
    SeedImmutabilityError,
    SeedStatus,
    get_king_realm,
    is_king,
    validate_king_realm_match,
)

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def bael_king_id() -> str:
    """Bael - King of Privacy & Discretion Services realm."""
    return "5b8e679b-abb5-41e6-8d17-36531db04757"


@pytest.fixture
def beleth_king_id() -> str:
    """Beleth - King of Relationship Facilitation realm."""
    return "177ee194-ff00-45b7-a3b0-b05e7675e718"


@pytest.fixture
def non_king_id() -> str:
    """A non-King archon ID."""
    return "non-king-archon-12345"


@pytest.fixture
def test_cycle_id() -> str:
    """Test cycle ID for H1 budget tracking."""
    return "conclave-20260118-test"


@pytest.fixture
def sample_seed() -> MotionSeed:
    """Create a sample Motion Seed."""
    return MotionSeed.create(
        seed_text="Establish a framework for privacy-preserving data sharing",
        submitted_by="test-archon-1",
        submitted_by_name="Test Archon",
        proposed_realm="realm_privacy_discretion_services",
        proposed_title="Privacy Framework Proposal",
        source_cycle="conclave-20260117-test",
        source_event="test-extraction",
    )


@pytest.fixture
def admission_gate() -> AdmissionGateService:
    """Create an AdmissionGate service."""
    return AdmissionGateService()


@pytest.fixture
def promotion_service() -> PromotionService:
    """Create a Promotion service."""
    return PromotionService()


@pytest.fixture
def seed_pool(tmp_path) -> SeedPoolService:
    """Create a SeedPool service with temp directory."""
    return SeedPoolService(output_dir=tmp_path / "seed-pool")


# =============================================================================
# King/Realm Mapping Tests
# =============================================================================


class TestKingRealmMapping:
    """Tests for King and Realm mapping functions."""

    def test_nine_kings_defined(self) -> None:
        """There should be exactly 9 Kings."""
        assert len(KING_IDS) == 9

    def test_each_king_has_realm(self) -> None:
        """Each King should have an assigned realm."""
        for king_id in KING_IDS:
            realm = get_king_realm(king_id)
            assert realm is not None
            assert realm.startswith("realm_")

    def test_is_king_valid(self, bael_king_id: str) -> None:
        """is_king should return True for valid King IDs."""
        assert is_king(bael_king_id) is True

    def test_is_king_invalid(self, non_king_id: str) -> None:
        """is_king should return False for non-King IDs."""
        assert is_king(non_king_id) is False

    def test_king_realm_match_valid(self, bael_king_id: str) -> None:
        """validate_king_realm_match should return True for correct realm."""
        assert (
            validate_king_realm_match(bael_king_id, "realm_privacy_discretion_services")
            is True
        )

    def test_king_realm_match_invalid(self, bael_king_id: str) -> None:
        """validate_king_realm_match should return False for wrong realm."""
        assert (
            validate_king_realm_match(bael_king_id, "realm_relationship_facilitation")
            is False
        )


# =============================================================================
# Motion Seed Tests
# =============================================================================


class TestMotionSeed:
    """Tests for MotionSeed domain model."""

    def test_create_seed(self, sample_seed: MotionSeed) -> None:
        """Seeds should be created with RECORDED status."""
        assert sample_seed.status == SeedStatus.RECORDED
        assert sample_seed.seed_id is not None
        assert sample_seed.seed_text is not None

    def test_seed_add_support(self, sample_seed: MotionSeed) -> None:
        """Seeds can receive non-binding support signals."""
        signal = sample_seed.add_support(
            signaler_id="supporter-1",
            signaler_name="Supporter One",
            signaler_rank="director",
            signal_type="support",
        )

        assert len(sample_seed.support_signals) == 1
        assert signal.signaler_name == "Supporter One"

    def test_seed_mark_clustered(self, sample_seed: MotionSeed) -> None:
        """Seeds can be marked as clustered."""
        sample_seed.mark_clustered("cluster-123", position=0)

        assert sample_seed.status == SeedStatus.CLUSTERED
        assert sample_seed.cluster_id == "cluster-123"

    def test_seed_mark_promoted(
        self, sample_seed: MotionSeed, bael_king_id: str
    ) -> None:
        """Seeds can be marked as promoted."""
        sample_seed.mark_promoted("motion-123", king_id=bael_king_id)

        assert sample_seed.status == SeedStatus.PROMOTED
        assert sample_seed.promoted_to_motion_id == "motion-123"
        assert sample_seed.promoted_by == bael_king_id

    def test_seed_serialization(self, sample_seed: MotionSeed) -> None:
        """Seeds should serialize to dict correctly."""
        data = sample_seed.to_dict()

        assert "seed_id" in data
        assert "seed_text" in data
        assert "status" in data
        assert data["status"] == "recorded"


# =============================================================================
# Admission Gate Tests
# =============================================================================


class TestAdmissionGate:
    """Tests for AdmissionGate service."""

    def test_valid_motion_admitted(
        self, admission_gate: AdmissionGateService, bael_king_id: str
    ) -> None:
        """A valid motion should be admitted."""
        candidate = MotionCandidate(
            motion_id="motion-test-1",
            title="Privacy Framework Motion",
            realm_assignment={
                "primary_realm": "realm_privacy_discretion_services",
                "primary_sponsor_id": bael_king_id,
                "primary_sponsor_name": "Bael",
            },
            normative_intent="The Conclave SHALL establish a framework for privacy-preserving data operations",
            constraints="Must not compromise individual privacy rights",
            success_criteria="Framework documented and adopted by all realms",
            submitted_at=datetime.now(timezone.utc),
            source_seed_refs=["seed-1", "seed-2"],
        )

        record = admission_gate.evaluate(candidate)

        assert record.status == AdmissionStatus.ADMITTED
        assert len(record.rejection_reasons) == 0

    def test_missing_title_rejected(
        self, admission_gate: AdmissionGateService, bael_king_id: str
    ) -> None:
        """Motion missing title should be rejected."""
        candidate = MotionCandidate(
            motion_id="motion-test-2",
            title="",  # Empty title
            realm_assignment={
                "primary_realm": "realm_privacy_discretion_services",
                "primary_sponsor_id": bael_king_id,
            },
            normative_intent="Some intent",
            constraints="",
            success_criteria="Some criteria",
            submitted_at=datetime.now(timezone.utc),
            source_seed_refs=[],
        )

        record = admission_gate.evaluate(candidate)

        assert record.status == AdmissionStatus.REJECTED
        assert AdmissionRejectReason.MISSING_TITLE in record.rejection_reasons

    def test_non_king_sponsor_rejected(
        self, admission_gate: AdmissionGateService, non_king_id: str
    ) -> None:
        """Motion with non-King sponsor should be rejected."""
        candidate = MotionCandidate(
            motion_id="motion-test-3",
            title="Some Motion",
            realm_assignment={
                "primary_realm": "realm_privacy_discretion_services",
                "primary_sponsor_id": non_king_id,  # Not a King
            },
            normative_intent="Some intent",
            constraints="",
            success_criteria="Some criteria",
            submitted_at=datetime.now(timezone.utc),
            source_seed_refs=[],
        )

        record = admission_gate.evaluate(candidate)

        assert record.status == AdmissionStatus.REJECTED
        assert AdmissionRejectReason.SPONSOR_NOT_KING in record.rejection_reasons

    def test_wrong_realm_rejected(
        self, admission_gate: AdmissionGateService, bael_king_id: str
    ) -> None:
        """Motion with King sponsoring wrong realm should be rejected."""
        candidate = MotionCandidate(
            motion_id="motion-test-4",
            title="Some Motion",
            realm_assignment={
                "primary_realm": "realm_relationship_facilitation",  # Beleth's realm, not Bael's
                "primary_sponsor_id": bael_king_id,
            },
            normative_intent="Some intent",
            constraints="",
            success_criteria="Some criteria",
            submitted_at=datetime.now(timezone.utc),
            source_seed_refs=[],
        )

        record = admission_gate.evaluate(candidate)

        assert record.status == AdmissionStatus.REJECTED
        assert AdmissionRejectReason.SPONSOR_WRONG_REALM in record.rejection_reasons

    def test_how_in_normative_intent_rejected(
        self, admission_gate: AdmissionGateService, bael_king_id: str
    ) -> None:
        """Motion with HOW content in normative_intent should be rejected."""
        candidate = MotionCandidate(
            motion_id="motion-test-5",
            title="Technical Motion",
            realm_assignment={
                "primary_realm": "realm_privacy_discretion_services",
                "primary_sponsor_id": bael_king_id,
            },
            normative_intent="Implement a REST API endpoint at /api/v1/privacy using JSON format",  # Contains HOW
            constraints="",
            success_criteria="API deployed",
            submitted_at=datetime.now(timezone.utc),
            source_seed_refs=[],
        )

        record = admission_gate.evaluate(candidate)

        assert record.status == AdmissionStatus.REJECTED
        assert AdmissionRejectReason.HOW_IN_NORMATIVE_INTENT in record.rejection_reasons

    def test_ambiguous_terms_rejected(
        self, admission_gate: AdmissionGateService, bael_king_id: str
    ) -> None:
        """Motion with ambiguous terms should be rejected."""
        candidate = MotionCandidate(
            motion_id="motion-test-6",
            title="Vague Motion",
            realm_assignment={
                "primary_realm": "realm_privacy_discretion_services",
                "primary_sponsor_id": bael_king_id,
            },
            normative_intent="Do something about privacy as needed and TBD",  # Ambiguous
            constraints="",
            success_criteria="Somehow improved",
            submitted_at=datetime.now(timezone.utc),
            source_seed_refs=[],
        )

        record = admission_gate.evaluate(candidate)

        assert record.status == AdmissionStatus.REJECTED
        assert AdmissionRejectReason.AMBIGUOUS_SCOPE in record.rejection_reasons

    def test_h4_cross_realm_escalation(
        self, admission_gate: AdmissionGateService
    ) -> None:
        """H4: Motions spanning 4+ realms require escalation."""
        # Get 4 different Kings for cross-realm motion
        king_ids = list(KING_IDS)[:4]
        primary_king = king_ids[0]
        primary_realm = get_king_realm(primary_king)

        # Create co-sponsors for 3 additional realms (4 total)
        co_sponsors = []
        for king_id in king_ids[1:4]:
            co_sponsors.append(
                {
                    "king_id": king_id,
                    "realm_id": get_king_realm(king_id),
                }
            )

        candidate = MotionCandidate(
            motion_id="motion-cross-realm",
            title="Multi-Realm Motion",
            realm_assignment={
                "primary_realm": primary_realm,
                "primary_sponsor_id": primary_king,
                "primary_sponsor_name": KING_REALM_MAP[primary_king]["name"],
            },
            normative_intent="The Conclave SHALL coordinate across all realms",
            constraints="Must respect realm sovereignty",
            success_criteria="Cross-realm coordination achieved",
            submitted_at=datetime.now(timezone.utc),
            source_seed_refs=["seed-1"],
            co_sponsors=co_sponsors,
        )

        record = admission_gate.evaluate(candidate)

        # Should be rejected due to escalation requirement
        assert record.status == AdmissionStatus.REJECTED
        assert AdmissionRejectReason.EXCESSIVE_REALM_SPAN in record.rejection_reasons
        assert record.requires_escalation is True
        assert record.escalation_realm_count == 4

    def test_h4_three_realms_no_escalation(
        self, admission_gate: AdmissionGateService
    ) -> None:
        """H4: Motions with 3 realms should NOT require escalation (just warning)."""
        king_ids = list(KING_IDS)[:3]
        primary_king = king_ids[0]
        primary_realm = get_king_realm(primary_king)

        # Create co-sponsors for 2 additional realms (3 total)
        co_sponsors = []
        for king_id in king_ids[1:3]:
            co_sponsors.append(
                {
                    "king_id": king_id,
                    "realm_id": get_king_realm(king_id),
                }
            )

        candidate = MotionCandidate(
            motion_id="motion-three-realm",
            title="Three-Realm Motion",
            realm_assignment={
                "primary_realm": primary_realm,
                "primary_sponsor_id": primary_king,
                "primary_sponsor_name": KING_REALM_MAP[primary_king]["name"],
            },
            normative_intent="The Conclave SHALL coordinate across three realms",
            constraints="Must respect realm sovereignty",
            success_criteria="Coordination achieved",
            submitted_at=datetime.now(timezone.utc),
            source_seed_refs=["seed-1"],
            co_sponsors=co_sponsors,
        )

        record = admission_gate.evaluate(candidate)

        # Should be admitted but with warning
        assert record.status == AdmissionStatus.ADMITTED
        assert record.requires_escalation is False
        assert (
            len(record.warnings) > 0
        )  # Should have warning about approaching threshold


# =============================================================================
# Promotion Service Tests
# =============================================================================


class TestPromotionService:
    """Tests for PromotionService."""

    def test_king_can_promote(
        self,
        promotion_service: PromotionService,
        sample_seed: MotionSeed,
        bael_king_id: str,
        test_cycle_id: str,
    ) -> None:
        """A King should be able to promote seeds in their realm."""
        result, motion = promotion_service.promote(
            seeds=[sample_seed],
            king_id=bael_king_id,
            cycle_id=test_cycle_id,
            title="Privacy Framework Motion",
            normative_intent="The Conclave SHALL establish privacy protections",
            constraints="Must preserve individual rights",
            success_criteria="Framework adopted",
        )

        assert result.success is True
        assert motion is not None
        assert motion.motion_id is not None
        assert motion.realm_assignment.primary_sponsor_id == bael_king_id

    def test_non_king_cannot_promote(
        self,
        promotion_service: PromotionService,
        sample_seed: MotionSeed,
        non_king_id: str,
        test_cycle_id: str,
    ) -> None:
        """A non-King should not be able to promote seeds."""
        result, motion = promotion_service.promote(
            seeds=[sample_seed],
            king_id=non_king_id,
            cycle_id=test_cycle_id,
            title="Some Motion",
            normative_intent="Some intent",
            constraints="",
            success_criteria="Some criteria",
        )

        assert result.success is False
        assert "king" in result.error_code.lower()  # NOT_KING or not_king
        assert motion is None

    def test_king_wrong_realm_cannot_promote(
        self,
        promotion_service: PromotionService,
        sample_seed: MotionSeed,
        bael_king_id: str,
        test_cycle_id: str,
    ) -> None:
        """A King should not be able to promote in another King's realm."""
        result, motion = promotion_service.promote(
            seeds=[sample_seed],
            king_id=bael_king_id,
            cycle_id=test_cycle_id,
            title="Some Motion",
            normative_intent="Some intent",
            constraints="",
            success_criteria="Some criteria",
            realm_id="realm_relationship_facilitation",  # Beleth's realm
        )

        assert result.success is False
        assert result.error_code == "WRONG_REALM"
        assert motion is None

    def test_promotion_marks_seed(
        self,
        promotion_service: PromotionService,
        sample_seed: MotionSeed,
        bael_king_id: str,
        test_cycle_id: str,
    ) -> None:
        """Promotion should mark the seed as promoted."""
        result, motion = promotion_service.promote(
            seeds=[sample_seed],
            king_id=bael_king_id,
            cycle_id=test_cycle_id,
            title="Privacy Motion",
            normative_intent="Establish privacy",
            constraints="",
            success_criteria="Done",
        )

        assert sample_seed.status == SeedStatus.PROMOTED
        assert sample_seed.promoted_to_motion_id == motion.motion_id

    def test_cross_realm_with_cosponsors(
        self,
        promotion_service: PromotionService,
        sample_seed: MotionSeed,
        bael_king_id: str,
        beleth_king_id: str,
        test_cycle_id: str,
    ) -> None:
        """Cross-realm motion should require valid co-sponsors."""
        result, motion = promotion_service.promote(
            seeds=[sample_seed],
            king_id=bael_king_id,
            cycle_id=test_cycle_id,
            title="Cross-Realm Motion",
            normative_intent="Privacy and relationships",
            constraints="",
            success_criteria="Done",
            co_sponsors=[
                {
                    "king_id": beleth_king_id,
                    "realm_id": "realm_relationship_facilitation",
                }
            ],
        )

        assert result.success is True
        assert motion.realm_assignment.is_cross_realm is True
        assert len(motion.realm_assignment.co_sponsors) == 1

    # H1: King Promotion Budget Tests
    def test_h1_budget_enforcement(
        self,
        bael_king_id: str,
        test_cycle_id: str,
    ) -> None:
        """H1: King promotion budget should be enforced per cycle."""
        # Create service with budget of 2 per King
        tracker = PromotionBudgetTracker(default_budget=2)
        service = PromotionService(budget_tracker=tracker)

        # First two promotions should succeed
        for i in range(2):
            seed = MotionSeed.create(
                seed_text=f"Seed {i}",
                submitted_by="archon",
                submitted_by_name="Test Archon",
                proposed_realm="realm_privacy_discretion_services",
            )
            result, motion = service.promote(
                seeds=[seed],
                king_id=bael_king_id,
                cycle_id=test_cycle_id,
                title=f"Motion {i}",
                normative_intent="Test intent",
                constraints="",
                success_criteria="Done",
            )
            assert result.success is True, f"Promotion {i} should succeed"

        # Third promotion should fail - budget exceeded
        seed = MotionSeed.create(
            seed_text="Seed 3",
            submitted_by="archon",
            submitted_by_name="Test Archon",
            proposed_realm="realm_privacy_discretion_services",
        )
        result, motion = service.promote(
            seeds=[seed],
            king_id=bael_king_id,
            cycle_id=test_cycle_id,
            title="Motion 3",
            normative_intent="Test intent",
            constraints="",
            success_criteria="Done",
        )
        assert result.success is False
        assert (
            result.error_code == PromotionRejectReason.PROMOTION_BUDGET_EXCEEDED.value
        )

    def test_h1_budget_resets_per_cycle(
        self,
        bael_king_id: str,
    ) -> None:
        """H1: Budget should reset for each new cycle."""
        tracker = PromotionBudgetTracker(default_budget=1)
        service = PromotionService(budget_tracker=tracker)

        # Exhaust budget in cycle 1
        seed1 = MotionSeed.create(
            seed_text="Seed 1",
            submitted_by="archon",
            submitted_by_name="Test Archon",
            proposed_realm="realm_privacy_discretion_services",
        )
        result, _ = service.promote(
            seeds=[seed1],
            king_id=bael_king_id,
            cycle_id="cycle-1",
            title="Motion 1",
            normative_intent="Intent",
            constraints="",
            success_criteria="Done",
        )
        assert result.success is True

        # Next promotion in cycle-1 should fail
        seed2 = MotionSeed.create(
            seed_text="Seed 2",
            submitted_by="archon",
            submitted_by_name="Test Archon",
            proposed_realm="realm_privacy_discretion_services",
        )
        result, _ = service.promote(
            seeds=[seed2],
            king_id=bael_king_id,
            cycle_id="cycle-1",
            title="Motion 2",
            normative_intent="Intent",
            constraints="",
            success_criteria="Done",
        )
        assert result.success is False

        # New cycle should have fresh budget
        seed3 = MotionSeed.create(
            seed_text="Seed 3",
            submitted_by="archon",
            submitted_by_name="Test Archon",
            proposed_realm="realm_privacy_discretion_services",
        )
        result, _ = service.promote(
            seeds=[seed3],
            king_id=bael_king_id,
            cycle_id="cycle-2",  # Different cycle
            title="Motion 3",
            normative_intent="Intent",
            constraints="",
            success_criteria="Done",
        )
        assert result.success is True


# =============================================================================
# H3: Seed Immutability Tests
# =============================================================================


class TestSeedImmutability:
    """H3: Tests for Seed immutability after promotion."""

    def test_h3_seed_text_immutable_after_promotion(
        self, sample_seed: MotionSeed, bael_king_id: str
    ) -> None:
        """H3: seed_text cannot be modified after promotion."""
        sample_seed.mark_promoted("motion-1", bael_king_id)

        with pytest.raises(SeedImmutabilityError) as exc_info:
            sample_seed.seed_text = "Modified text"

        assert exc_info.value.field_name == "seed_text"
        assert "promotion" in exc_info.value.message.lower()

    def test_h3_submitted_by_immutable_after_promotion(
        self, sample_seed: MotionSeed, bael_king_id: str
    ) -> None:
        """H3: submitted_by cannot be modified after promotion."""
        sample_seed.mark_promoted("motion-1", bael_king_id)

        with pytest.raises(SeedImmutabilityError) as exc_info:
            sample_seed.submitted_by = "different-archon"

        assert exc_info.value.field_name == "submitted_by"

    def test_h3_submitted_at_immutable_after_promotion(
        self, sample_seed: MotionSeed, bael_king_id: str
    ) -> None:
        """H3: submitted_at cannot be modified after promotion."""
        sample_seed.mark_promoted("motion-1", bael_king_id)

        with pytest.raises(SeedImmutabilityError) as exc_info:
            sample_seed.submitted_at = datetime.now(timezone.utc)

        assert exc_info.value.field_name == "submitted_at"

    def test_h3_source_references_immutable_after_promotion(
        self, sample_seed: MotionSeed, bael_king_id: str
    ) -> None:
        """H3: source_references cannot be modified after promotion."""
        sample_seed.mark_promoted("motion-1", bael_king_id)

        with pytest.raises(SeedImmutabilityError) as exc_info:
            sample_seed.source_references = ["fake-reference"]

        assert exc_info.value.field_name == "source_references"

    def test_h3_fields_mutable_before_promotion(self, sample_seed: MotionSeed) -> None:
        """H3: Fields should be mutable before promotion."""
        # These should not raise
        sample_seed.seed_text = "Updated text"
        sample_seed.submitted_by = "new-archon"
        sample_seed.source_references = ["new-ref"]

        assert sample_seed.seed_text == "Updated text"
        assert sample_seed.submitted_by == "new-archon"
        assert sample_seed.source_references == ["new-ref"]

    def test_h3_source_references_inplace_mutation_blocked_after_promotion(
        self, sample_seed: MotionSeed, bael_king_id: str
    ) -> None:
        """H3: In-place list mutation on source_references blocked after promotion.

        This catches the bypass where seed.source_references.append() would
        mutate the live list without triggering the setter guard.
        """
        sample_seed._source_references = ["original-ref"]
        sample_seed.mark_promoted("motion-1", bael_king_id)

        # After promotion, source_references returns a tuple (immutable)
        refs = sample_seed.source_references
        assert isinstance(refs, tuple), (
            "Must return tuple after promotion to prevent mutation"
        )
        assert refs == ("original-ref",)

        # Attempting to append should fail (tuples don't have append)
        with pytest.raises(AttributeError):
            refs.append("bypass-attempt")  # type: ignore

    def test_h3_add_source_reference_blocked_after_promotion(
        self, sample_seed: MotionSeed, bael_king_id: str
    ) -> None:
        """H3: add_source_reference() method blocked after promotion."""
        sample_seed.mark_promoted("motion-1", bael_king_id)

        with pytest.raises(SeedImmutabilityError) as exc_info:
            sample_seed.add_source_reference("new-ref")

        assert exc_info.value.field_name == "source_references"

    def test_h3_add_source_reference_works_before_promotion(
        self, sample_seed: MotionSeed
    ) -> None:
        """H3: add_source_reference() works before promotion."""
        sample_seed.add_source_reference("ref-1")
        sample_seed.add_source_reference("ref-2")

        assert "ref-1" in sample_seed.source_references
        assert "ref-2" in sample_seed.source_references


# =============================================================================
# Seed Pool Tests
# =============================================================================


class TestSeedPool:
    """Tests for SeedPoolService."""

    def test_add_seed(
        self, seed_pool: SeedPoolService, sample_seed: MotionSeed
    ) -> None:
        """Seeds can be added to the pool."""
        added = seed_pool.add_seed(sample_seed)

        assert added.seed_id == sample_seed.seed_id
        assert seed_pool.get_seed(str(sample_seed.seed_id)) is not None

    def test_get_seeds_for_promotion(self, seed_pool: SeedPoolService) -> None:
        """Can retrieve seeds available for promotion."""
        seed1 = MotionSeed.create(
            seed_text="Seed 1",
            submitted_by="archon-1",
            submitted_by_name="Archon 1",
        )
        seed2 = MotionSeed.create(
            seed_text="Seed 2",
            submitted_by="archon-2",
            submitted_by_name="Archon 2",
        )

        seed_pool.add_seed(seed1)
        seed_pool.add_seed(seed2)

        promotable = seed_pool.get_seeds_for_promotion()
        assert len(promotable) == 2

    def test_promoted_seeds_excluded_from_promotion(
        self, seed_pool: SeedPoolService, bael_king_id: str
    ) -> None:
        """Promoted seeds should not appear in promotable list."""
        seed = MotionSeed.create(
            seed_text="Test seed",
            submitted_by="archon-1",
            submitted_by_name="Archon 1",
        )
        seed_pool.add_seed(seed)
        seed.mark_promoted("motion-1", bael_king_id)

        promotable = seed_pool.get_seeds_for_promotion()
        assert len(promotable) == 0

    def test_get_seeds_for_king(
        self, seed_pool: SeedPoolService, bael_king_id: str
    ) -> None:
        """Can get seeds relevant to a King's realm."""
        seed1 = MotionSeed.create(
            seed_text="Privacy seed",
            submitted_by="archon-1",
            submitted_by_name="Archon 1",
            proposed_realm="realm_privacy_discretion_services",
        )
        seed2 = MotionSeed.create(
            seed_text="Relationship seed",
            submitted_by="archon-2",
            submitted_by_name="Archon 2",
            proposed_realm="realm_relationship_facilitation",
        )

        seed_pool.add_seed(seed1)
        seed_pool.add_seed(seed2)

        bael_seeds = seed_pool.get_seeds_for_king(bael_king_id)
        assert len(bael_seeds) == 1
        assert bael_seeds[0].proposed_realm == "realm_privacy_discretion_services"

    def test_get_stats(self, seed_pool: SeedPoolService) -> None:
        """Can get pool statistics."""
        seed1 = MotionSeed.create(
            seed_text="Seed 1",
            submitted_by="archon-1",
            submitted_by_name="Archon 1",
        )
        seed2 = MotionSeed.create(
            seed_text="Seed 2",
            submitted_by="archon-2",
            submitted_by_name="Archon 2",
        )
        seed2.mark_archived()

        seed_pool.add_seed(seed1)
        seed_pool.add_seed(seed2)

        stats = seed_pool.get_stats()
        assert stats.total_seeds == 2
        assert stats.recorded_seeds == 1
        assert stats.archived_seeds == 1

    def test_cluster_seeds(self, seed_pool: SeedPoolService) -> None:
        """Can cluster related seeds."""
        seed1 = MotionSeed.create(
            seed_text="Privacy idea 1",
            submitted_by="archon-1",
            submitted_by_name="Archon 1",
        )
        seed2 = MotionSeed.create(
            seed_text="Privacy idea 2",
            submitted_by="archon-2",
            submitted_by_name="Archon 2",
        )

        seed_pool.add_seed(seed1)
        seed_pool.add_seed(seed2)

        cluster = seed_pool.cluster_seeds(
            seed_ids=[str(seed1.seed_id), str(seed2.seed_id)],
            theme="Privacy Improvements",
            description="Cluster of privacy-related seeds",
        )

        assert cluster is not None
        assert len(cluster.seed_refs) == 2
        assert seed1.status == SeedStatus.CLUSTERED
        assert seed2.status == SeedStatus.CLUSTERED
