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

import pytest
from datetime import datetime, timezone
from uuid import uuid4

from src.domain.models.motion_seed import (
    AdmissionRejectReason,
    AdmissionStatus,
    KING_IDS,
    KING_REALM_MAP,
    MotionSeed,
    RealmAssignment,
    SeedStatus,
    is_king,
    get_king_realm,
    validate_king_realm_match,
)
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
        assert validate_king_realm_match(
            bael_king_id, "realm_privacy_discretion_services"
        ) is True

    def test_king_realm_match_invalid(self, bael_king_id: str) -> None:
        """validate_king_realm_match should return False for wrong realm."""
        assert validate_king_realm_match(
            bael_king_id, "realm_relationship_facilitation"
        ) is False


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

    def test_seed_mark_promoted(self, sample_seed: MotionSeed, bael_king_id: str) -> None:
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
    ) -> None:
        """A King should be able to promote seeds in their realm."""
        result, motion = promotion_service.promote(
            seeds=[sample_seed],
            king_id=bael_king_id,
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
    ) -> None:
        """A non-King should not be able to promote seeds."""
        result, motion = promotion_service.promote(
            seeds=[sample_seed],
            king_id=non_king_id,
            title="Some Motion",
            normative_intent="Some intent",
            constraints="",
            success_criteria="Some criteria",
        )

        assert result.success is False
        assert result.error_code == "NOT_KING"
        assert motion is None

    def test_king_wrong_realm_cannot_promote(
        self,
        promotion_service: PromotionService,
        sample_seed: MotionSeed,
        bael_king_id: str,
    ) -> None:
        """A King should not be able to promote in another King's realm."""
        result, motion = promotion_service.promote(
            seeds=[sample_seed],
            king_id=bael_king_id,
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
    ) -> None:
        """Promotion should mark the seed as promoted."""
        result, motion = promotion_service.promote(
            seeds=[sample_seed],
            king_id=bael_king_id,
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
    ) -> None:
        """Cross-realm motion should require valid co-sponsors."""
        result, motion = promotion_service.promote(
            seeds=[sample_seed],
            king_id=bael_king_id,
            title="Cross-Realm Motion",
            normative_intent="Privacy and relationships",
            constraints="",
            success_criteria="Done",
            co_sponsors=[{
                "king_id": beleth_king_id,
                "realm_id": "realm_relationship_facilitation",
            }],
        )

        assert result.success is True
        assert motion.realm_assignment.is_cross_realm is True
        assert len(motion.realm_assignment.co_sponsors) == 1


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

    def test_get_seeds_for_promotion(
        self, seed_pool: SeedPoolService
    ) -> None:
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
