"""Unit tests for Advisory Conflict Detection Service.

Tests for FR-GOV-18: Marquis cannot judge domains where advisory was given.

Test coverage:
- AC1: Conflict detection
- AC2: Prince panel exclusion
- AC3: Participation violation witnessing
- AC4: Topic overlap detection
- AC5: Conflict resolution path (escalation)
- AC6: Conflict audit trail
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, create_autospec
from uuid import uuid4

import pytest

from src.application.ports.advisory_acknowledgment import AdvisoryWindow
from src.application.ports.knight_witness import (
    KnightWitnessProtocol,
    WitnessStatement,
    WitnessStatementType,
)
from src.application.services.advisory_conflict_detection_service import (
    AdvisoryConflict,
    AdvisoryConflictDetectionService,
    AdvisoryConflictViolation,
    AuditEventType,
    ConflictAuditEntry,
    ConflictDetectionConfig,
    ConflictDetectionRequest,
    ConflictResolution,
    PanelFormationRequest,
    ParticipationCheckRequest,
    TopicOverlap,
    ViolationSeverity,
)

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def mock_knight_witness() -> MagicMock:
    """Create a mock Knight witness service."""
    mock = create_autospec(KnightWitnessProtocol)
    mock.observe.return_value = WitnessStatement.create(
        statement_type=WitnessStatementType.BRANCH_VIOLATION,
        description="Test witness statement",
        roles_involved=["test_archon"],
    )
    mock.record_violation.return_value = mock.observe.return_value
    mock.trigger_acknowledgment.return_value = MagicMock()
    return mock


@pytest.fixture
def config() -> ConflictDetectionConfig:
    """Create test configuration."""
    return ConflictDetectionConfig(
        overlap_threshold=0.6,
        exclusion_automatic=True,
        violation_severity=ViolationSeverity.MAJOR,
        escalation_enabled=True,
    )


@pytest.fixture
def service(
    config: ConflictDetectionConfig,
    mock_knight_witness: MagicMock,
) -> AdvisoryConflictDetectionService:
    """Create service with mock dependencies."""
    return AdvisoryConflictDetectionService(
        advisory_service=None,  # Use internal storage
        knight_witness=mock_knight_witness,
        config=config,
    )


@pytest.fixture
def sample_advisory_window() -> AdvisoryWindow:
    """Create a sample advisory window."""
    return AdvisoryWindow.create(
        marquis_id="orias",
        advisory_id=uuid4(),
        topic="quantum computing security",
        timestamp=datetime.now(timezone.utc),
    )


# =============================================================================
# AC1: CONFLICT DETECTION TESTS
# =============================================================================


class TestConflictDetection:
    """Tests for AC1: Conflict detection."""

    @pytest.mark.asyncio
    async def test_detect_conflict_exact_match(
        self,
        service: AdvisoryConflictDetectionService,
        sample_advisory_window: AdvisoryWindow,
    ) -> None:
        """Test conflict detection with exact topic match."""
        service.register_advisory_window(sample_advisory_window)

        result = await service.detect_conflicts(
            ConflictDetectionRequest(
                marquis_id="orias",
                judgment_topic="quantum computing security",
            )
        )

        assert result.has_conflict is True
        assert len(result.conflicts) == 1
        assert result.can_judge is False
        assert "FR-GOV-18" in result.reason

    @pytest.mark.asyncio
    async def test_no_conflict_different_topic(
        self,
        service: AdvisoryConflictDetectionService,
        sample_advisory_window: AdvisoryWindow,
    ) -> None:
        """Test no conflict with completely different topic."""
        service.register_advisory_window(sample_advisory_window)

        result = await service.detect_conflicts(
            ConflictDetectionRequest(
                marquis_id="orias",
                judgment_topic="biodiversity assessment",
            )
        )

        assert result.has_conflict is False
        assert len(result.conflicts) == 0
        assert result.can_judge is True

    @pytest.mark.asyncio
    async def test_conflict_logged_with_advisory_reference(
        self,
        service: AdvisoryConflictDetectionService,
        sample_advisory_window: AdvisoryWindow,
    ) -> None:
        """Test conflict is logged with advisory reference per AC1."""
        service.register_advisory_window(sample_advisory_window)

        result = await service.detect_conflicts(
            ConflictDetectionRequest(
                marquis_id="orias",
                judgment_topic="quantum computing security",
            )
        )

        conflict = result.conflicts[0]
        assert conflict.advisory_id == sample_advisory_window.advisory_id
        assert conflict.advisory_topic == sample_advisory_window.topic

    @pytest.mark.asyncio
    async def test_no_conflict_for_different_marquis(
        self,
        service: AdvisoryConflictDetectionService,
        sample_advisory_window: AdvisoryWindow,
    ) -> None:
        """Test no conflict for a different Marquis."""
        service.register_advisory_window(sample_advisory_window)

        result = await service.detect_conflicts(
            ConflictDetectionRequest(
                marquis_id="bael",  # Different Marquis
                judgment_topic="quantum computing security",
            )
        )

        assert result.has_conflict is False
        assert result.can_judge is True


# =============================================================================
# AC2: PRINCE PANEL EXCLUSION TESTS
# =============================================================================


class TestPrincePanelExclusion:
    """Tests for AC2: Prince panel exclusion."""

    @pytest.mark.asyncio
    async def test_conflicted_prince_excluded(
        self,
        service: AdvisoryConflictDetectionService,
        sample_advisory_window: AdvisoryWindow,
    ) -> None:
        """Test conflicted Prince is excluded from panel."""
        service.register_advisory_window(sample_advisory_window)

        result = await service.form_unconflicted_panel(
            PanelFormationRequest(
                judgment_topic="quantum computing security",
                available_princes=["orias", "bael", "paimon"],
            )
        )

        assert result.success is True
        assert "orias" not in result.panel
        assert "orias" in result.excluded
        assert "bael" in result.panel
        assert "paimon" in result.panel

    @pytest.mark.asyncio
    async def test_alternative_princes_selected(
        self,
        service: AdvisoryConflictDetectionService,
        sample_advisory_window: AdvisoryWindow,
    ) -> None:
        """Test alternative Princes are selected when one is excluded."""
        service.register_advisory_window(sample_advisory_window)

        result = await service.form_unconflicted_panel(
            PanelFormationRequest(
                judgment_topic="quantum computing security",
                available_princes=["orias", "bael"],
            )
        )

        assert result.success is True
        assert len(result.panel) == 1
        assert result.panel[0] == "bael"

    @pytest.mark.asyncio
    async def test_multiple_exclusions(
        self,
        service: AdvisoryConflictDetectionService,
    ) -> None:
        """Test multiple Princes can be excluded."""
        # Create windows for multiple Princes
        service.register_advisory_window(
            AdvisoryWindow.create(
                marquis_id="orias",
                advisory_id=uuid4(),
                topic="quantum computing",
                timestamp=datetime.now(timezone.utc),
            )
        )
        service.register_advisory_window(
            AdvisoryWindow.create(
                marquis_id="bael",
                advisory_id=uuid4(),
                topic="quantum security",
                timestamp=datetime.now(timezone.utc),
            )
        )

        result = await service.form_unconflicted_panel(
            PanelFormationRequest(
                judgment_topic="quantum computing security",
                available_princes=["orias", "bael", "paimon"],
            )
        )

        assert result.success is True
        assert len(result.excluded) == 2
        assert "orias" in result.excluded
        assert "bael" in result.excluded
        assert result.panel == ["paimon"]


# =============================================================================
# AC3: PARTICIPATION VIOLATION WITNESSING TESTS
# =============================================================================


class TestParticipationViolationWitnessing:
    """Tests for AC3: Participation violation witnessing."""

    @pytest.mark.asyncio
    async def test_violation_triggered_on_participation(
        self,
        service: AdvisoryConflictDetectionService,
        sample_advisory_window: AdvisoryWindow,
    ) -> None:
        """Test violation is triggered when conflicted Marquis attempts participation."""
        service.register_advisory_window(sample_advisory_window)

        result = await service.check_participation(
            ParticipationCheckRequest(
                marquis_id="orias",
                judgment_topic="quantum computing security",
                action="evaluate_compliance",
            )
        )

        assert result.allowed is False
        assert result.violation is not None
        assert "FR-GOV-18" in result.reason

    @pytest.mark.asyncio
    async def test_judgment_invalidated(
        self,
        service: AdvisoryConflictDetectionService,
        sample_advisory_window: AdvisoryWindow,
    ) -> None:
        """Test attempted judgment is invalidated per AC3."""
        service.register_advisory_window(sample_advisory_window)

        result = await service.check_participation(
            ParticipationCheckRequest(
                marquis_id="orias",
                judgment_topic="quantum computing security",
                action="issue_finding",
            )
        )

        assert result.violation.invalidated is True

    @pytest.mark.asyncio
    async def test_violation_severity_major(
        self,
        service: AdvisoryConflictDetectionService,
        sample_advisory_window: AdvisoryWindow,
    ) -> None:
        """Test violation severity is MAJOR per AC3."""
        service.register_advisory_window(sample_advisory_window)

        result = await service.check_participation(
            ParticipationCheckRequest(
                marquis_id="orias",
                judgment_topic="quantum computing security",
                action="evaluate_compliance",
            )
        )

        assert result.violation.severity == ViolationSeverity.MAJOR

    @pytest.mark.asyncio
    async def test_violation_witnessed_by_knight(
        self,
        service: AdvisoryConflictDetectionService,
        sample_advisory_window: AdvisoryWindow,
        mock_knight_witness: MagicMock,
    ) -> None:
        """Test violation is witnessed by Knight per CT-12."""
        service.register_advisory_window(sample_advisory_window)

        await service.check_participation(
            ParticipationCheckRequest(
                marquis_id="orias",
                judgment_topic="quantum computing security",
                action="evaluate_compliance",
            )
        )

        # Verify Knight recorded the violation
        assert mock_knight_witness.record_violation.called

    @pytest.mark.asyncio
    async def test_allowed_participation_when_no_conflict(
        self,
        service: AdvisoryConflictDetectionService,
    ) -> None:
        """Test participation is allowed when no conflict exists."""
        result = await service.check_participation(
            ParticipationCheckRequest(
                marquis_id="orias",
                judgment_topic="quantum computing security",
                action="evaluate_compliance",
            )
        )

        assert result.allowed is True
        assert result.violation is None


# =============================================================================
# AC4: TOPIC OVERLAP DETECTION TESTS
# =============================================================================


class TestTopicOverlapDetection:
    """Tests for AC4: Topic overlap detection."""

    @pytest.mark.asyncio
    async def test_exact_match_overlap(
        self,
        service: AdvisoryConflictDetectionService,
    ) -> None:
        """Test exact match gives overlap score of 1.0."""
        overlap = service._calculate_topic_overlap(
            "quantum computing",
            "quantum computing",
        )

        assert overlap.overlap_score == 1.0
        assert overlap.is_conflict is True

    @pytest.mark.asyncio
    async def test_contains_match_overlap(
        self,
        service: AdvisoryConflictDetectionService,
    ) -> None:
        """Test contains match gives high overlap score."""
        overlap = service._calculate_topic_overlap(
            "quantum",
            "quantum computing security",
        )

        assert overlap.overlap_score == 0.85
        assert overlap.is_conflict is True

    @pytest.mark.asyncio
    async def test_keyword_overlap(
        self,
        service: AdvisoryConflictDetectionService,
    ) -> None:
        """Test keyword overlap calculation."""
        overlap = service._calculate_topic_overlap(
            "quantum computing risks",
            "quantum computing security",
        )

        assert overlap.overlap_score >= 0.5
        assert "quantum" in overlap.matching_keywords
        assert "computing" in overlap.matching_keywords

    @pytest.mark.asyncio
    async def test_no_overlap(
        self,
        service: AdvisoryConflictDetectionService,
    ) -> None:
        """Test no overlap for unrelated topics."""
        overlap = service._calculate_topic_overlap(
            "quantum computing",
            "biodiversity conservation",
        )

        assert overlap.overlap_score < 0.6
        assert overlap.is_conflict is False

    @pytest.mark.asyncio
    async def test_case_insensitive(
        self,
        service: AdvisoryConflictDetectionService,
    ) -> None:
        """Test topic comparison is case insensitive."""
        overlap = service._calculate_topic_overlap(
            "Quantum Computing",
            "quantum computing",
        )

        assert overlap.is_conflict is True

    @pytest.mark.asyncio
    async def test_configurable_threshold(
        self,
        mock_knight_witness: MagicMock,
    ) -> None:
        """Test overlap threshold is configurable."""
        config = ConflictDetectionConfig(overlap_threshold=0.9)
        service = AdvisoryConflictDetectionService(
            knight_witness=mock_knight_witness,
            config=config,
        )

        # With high threshold, partial keyword match shouldn't trigger conflict
        overlap = service._calculate_topic_overlap(
            "quantum computing risks",
            "quantum security assessment",
        )

        # Only 1 word in common out of 5 total = 0.2 < 0.9
        assert overlap.is_conflict is False


# =============================================================================
# AC5: CONFLICT RESOLUTION PATH TESTS
# =============================================================================


class TestConflictResolutionPath:
    """Tests for AC5: Conflict resolution path (escalation)."""

    @pytest.mark.asyncio
    async def test_escalation_when_all_princes_conflicted(
        self,
        service: AdvisoryConflictDetectionService,
        mock_knight_witness: MagicMock,
    ) -> None:
        """Test escalation to Conclave when all Princes are conflicted."""
        # Create conflicts for all available Princes
        service.register_advisory_window(
            AdvisoryWindow.create(
                marquis_id="orias",
                advisory_id=uuid4(),
                topic="quantum computing",
                timestamp=datetime.now(timezone.utc),
            )
        )
        service.register_advisory_window(
            AdvisoryWindow.create(
                marquis_id="bael",
                advisory_id=uuid4(),
                topic="quantum security",
                timestamp=datetime.now(timezone.utc),
            )
        )

        result = await service.form_unconflicted_panel(
            PanelFormationRequest(
                judgment_topic="quantum computing security",
                available_princes=["orias", "bael"],  # Both conflicted
            )
        )

        assert result.success is False
        assert result.escalated is True
        assert len(result.excluded) == 2
        assert "Escalating to Conclave" in result.reason

    @pytest.mark.asyncio
    async def test_conflict_pattern_documented(
        self,
        service: AdvisoryConflictDetectionService,
    ) -> None:
        """Test conflict pattern is documented per AC5."""
        # Create conflicts for all available Princes
        service.register_advisory_window(
            AdvisoryWindow.create(
                marquis_id="orias",
                advisory_id=uuid4(),
                topic="quantum computing",
                timestamp=datetime.now(timezone.utc),
            )
        )

        await service.form_unconflicted_panel(
            PanelFormationRequest(
                judgment_topic="quantum computing",
                available_princes=["orias"],
            )
        )

        # Check audit trail documents the escalation
        audit = await service.get_full_audit_trail()
        escalation_entries = [
            e for e in audit if e.event_type == AuditEventType.ESCALATED
        ]
        assert len(escalation_entries) == 1
        assert "conflicted_princes" in escalation_entries[0].details

    @pytest.mark.asyncio
    async def test_escalation_witnessed(
        self,
        service: AdvisoryConflictDetectionService,
        mock_knight_witness: MagicMock,
    ) -> None:
        """Test escalation is witnessed by Knight."""
        service.register_advisory_window(
            AdvisoryWindow.create(
                marquis_id="orias",
                advisory_id=uuid4(),
                topic="quantum computing",
                timestamp=datetime.now(timezone.utc),
            )
        )

        await service.form_unconflicted_panel(
            PanelFormationRequest(
                judgment_topic="quantum computing",
                available_princes=["orias"],
            )
        )

        # Verify Knight observed and triggered acknowledgment
        assert mock_knight_witness.observe.called
        assert mock_knight_witness.trigger_acknowledgment.called


# =============================================================================
# AC6: CONFLICT AUDIT TRAIL TESTS
# =============================================================================


class TestConflictAuditTrail:
    """Tests for AC6: Conflict audit trail."""

    @pytest.mark.asyncio
    async def test_audit_includes_original_advisory(
        self,
        service: AdvisoryConflictDetectionService,
        sample_advisory_window: AdvisoryWindow,
    ) -> None:
        """Test audit includes original advisory with topic and date per AC6."""
        service.register_advisory_window(sample_advisory_window)

        await service.detect_conflicts(
            ConflictDetectionRequest(
                marquis_id="orias",
                judgment_topic="quantum computing security",
            )
        )

        audit = await service.get_full_audit_trail()
        assert len(audit) >= 1
        detected_entry = next(
            (e for e in audit if e.event_type == AuditEventType.DETECTED),
            None,
        )
        assert detected_entry is not None
        assert detected_entry.advisory_topic == sample_advisory_window.topic

    @pytest.mark.asyncio
    async def test_audit_includes_judgment_request(
        self,
        service: AdvisoryConflictDetectionService,
        sample_advisory_window: AdvisoryWindow,
    ) -> None:
        """Test audit includes judgment request with topic per AC6."""
        service.register_advisory_window(sample_advisory_window)

        await service.detect_conflicts(
            ConflictDetectionRequest(
                marquis_id="orias",
                judgment_topic="quantum computing security",
            )
        )

        audit = await service.get_full_audit_trail()
        detected_entry = audit[0]
        assert detected_entry.judgment_topic == "quantum computing security"

    @pytest.mark.asyncio
    async def test_audit_includes_conflict_detection_result(
        self,
        service: AdvisoryConflictDetectionService,
        sample_advisory_window: AdvisoryWindow,
    ) -> None:
        """Test audit includes conflict detection result per AC6."""
        service.register_advisory_window(sample_advisory_window)

        await service.detect_conflicts(
            ConflictDetectionRequest(
                marquis_id="orias",
                judgment_topic="quantum computing security",
            )
        )

        audit = await service.get_full_audit_trail()
        detected_entry = audit[0]
        assert "overlap_score" in detected_entry.details

    @pytest.mark.asyncio
    async def test_audit_includes_action_taken(
        self,
        service: AdvisoryConflictDetectionService,
        sample_advisory_window: AdvisoryWindow,
    ) -> None:
        """Test audit includes action taken (exclusion, violation, escalation) per AC6."""
        service.register_advisory_window(sample_advisory_window)

        # Trigger exclusion
        await service.form_unconflicted_panel(
            PanelFormationRequest(
                judgment_topic="quantum computing security",
                available_princes=["orias", "bael"],
            )
        )

        audit = await service.get_audit_by_marquis("orias")
        exclusion_entry = next(
            (e for e in audit if e.event_type == AuditEventType.EXCLUDED),
            None,
        )
        assert exclusion_entry is not None

    @pytest.mark.asyncio
    async def test_get_audit_by_conflict(
        self,
        service: AdvisoryConflictDetectionService,
        sample_advisory_window: AdvisoryWindow,
    ) -> None:
        """Test retrieving audit by conflict ID."""
        service.register_advisory_window(sample_advisory_window)

        result = await service.detect_conflicts(
            ConflictDetectionRequest(
                marquis_id="orias",
                judgment_topic="quantum computing security",
            )
        )

        conflict_id = result.conflicts[0].conflict_id
        audit = await service.get_conflict_audit(conflict_id)
        assert len(audit) >= 1
        assert all(e.conflict_id == conflict_id for e in audit)

    @pytest.mark.asyncio
    async def test_get_audit_by_topic(
        self,
        service: AdvisoryConflictDetectionService,
        sample_advisory_window: AdvisoryWindow,
    ) -> None:
        """Test retrieving audit by judgment topic."""
        service.register_advisory_window(sample_advisory_window)

        await service.detect_conflicts(
            ConflictDetectionRequest(
                marquis_id="orias",
                judgment_topic="quantum computing security",
            )
        )

        audit = await service.get_audit_by_topic("quantum computing security")
        assert len(audit) >= 1


# =============================================================================
# DOMAIN MODEL TESTS
# =============================================================================


class TestDomainModels:
    """Tests for domain model behavior."""

    def test_topic_overlap_immutability(self) -> None:
        """Test TopicOverlap is immutable."""
        overlap = TopicOverlap(
            overlap_score=0.8,
            advisory_topic="test",
            judgment_topic="test",
            is_conflict=True,
        )
        with pytest.raises(AttributeError):
            overlap.overlap_score = 0.5  # type: ignore

    def test_advisory_conflict_immutability(self) -> None:
        """Test AdvisoryConflict is immutable."""
        conflict = AdvisoryConflict.create(
            marquis_id="orias",
            advisory_id=uuid4(),
            advisory_topic="test",
            judgment_topic="test",
            overlap=TopicOverlap(0.8, "test", "test", True),
        )
        with pytest.raises(AttributeError):
            conflict.marquis_id = "bael"  # type: ignore

    def test_advisory_conflict_with_resolution(self) -> None:
        """Test AdvisoryConflict.with_resolution creates new instance."""
        conflict = AdvisoryConflict.create(
            marquis_id="orias",
            advisory_id=uuid4(),
            advisory_topic="test",
            judgment_topic="test",
            overlap=TopicOverlap(0.8, "test", "test", True),
            resolution=ConflictResolution.EXCLUDED,
        )

        violated = conflict.with_resolution(ConflictResolution.VIOLATED)
        assert violated.resolution == ConflictResolution.VIOLATED
        assert conflict.resolution == ConflictResolution.EXCLUDED

    def test_conflict_violation_severity_default(self) -> None:
        """Test violation defaults to MAJOR severity."""
        conflict = AdvisoryConflict.create(
            marquis_id="orias",
            advisory_id=uuid4(),
            advisory_topic="test",
            judgment_topic="test",
            overlap=TopicOverlap(0.8, "test", "test", True),
        )
        violation = AdvisoryConflictViolation.create(
            conflict=conflict,
            attempted_action="evaluate_compliance",
        )
        assert violation.severity == ViolationSeverity.MAJOR

    def test_conflict_audit_entry_serialization(self) -> None:
        """Test ConflictAuditEntry serialization."""
        entry = ConflictAuditEntry.create(
            event_type=AuditEventType.DETECTED,
            marquis_id="orias",
            judgment_topic="test",
            advisory_topic="advisory test",
            conflict_id=uuid4(),
            details={"overlap_score": 0.8},
        )
        data = entry.to_dict()
        assert "entry_id" in data
        assert "event_type" in data
        assert data["event_type"] == "detected"


# =============================================================================
# KNIGHT WITNESS INTEGRATION TESTS
# =============================================================================


class TestKnightWitnessIntegration:
    """Tests for Knight witness integration per CT-12."""

    @pytest.mark.asyncio
    async def test_conflict_detection_witnessed(
        self,
        service: AdvisoryConflictDetectionService,
        sample_advisory_window: AdvisoryWindow,
        mock_knight_witness: MagicMock,
    ) -> None:
        """Test conflict detection is witnessed by Knight."""
        service.register_advisory_window(sample_advisory_window)

        await service.detect_conflicts(
            ConflictDetectionRequest(
                marquis_id="orias",
                judgment_topic="quantum computing security",
            )
        )

        assert mock_knight_witness.observe.called

    @pytest.mark.asyncio
    async def test_service_works_without_knight(self) -> None:
        """Test service works without Knight witness (for testing)."""
        service = AdvisoryConflictDetectionService(knight_witness=None)
        window = AdvisoryWindow.create(
            marquis_id="orias",
            advisory_id=uuid4(),
            topic="quantum computing",
            timestamp=datetime.now(timezone.utc),
        )
        service.register_advisory_window(window)

        result = await service.detect_conflicts(
            ConflictDetectionRequest(
                marquis_id="orias",
                judgment_topic="quantum computing",
            )
        )

        assert result.has_conflict is True


# =============================================================================
# STATISTICS TESTS
# =============================================================================


class TestStatistics:
    """Tests for statistics reporting."""

    @pytest.mark.asyncio
    async def test_get_conflict_stats(
        self,
        service: AdvisoryConflictDetectionService,
        sample_advisory_window: AdvisoryWindow,
    ) -> None:
        """Test statistics gathering."""
        service.register_advisory_window(sample_advisory_window)

        await service.detect_conflicts(
            ConflictDetectionRequest(
                marquis_id="orias",
                judgment_topic="quantum computing security",
            )
        )

        await service.check_participation(
            ParticipationCheckRequest(
                marquis_id="orias",
                judgment_topic="quantum computing security",
                action="test",
            )
        )

        stats = await service.get_conflict_stats()
        assert stats["total_conflicts"] >= 1
        assert stats["total_violations"] >= 1
        assert stats["audit_entries"] >= 1


# =============================================================================
# QUERY TESTS
# =============================================================================


class TestQueries:
    """Tests for query methods."""

    @pytest.mark.asyncio
    async def test_get_conflict_by_id(
        self,
        service: AdvisoryConflictDetectionService,
        sample_advisory_window: AdvisoryWindow,
    ) -> None:
        """Test retrieving conflict by ID."""
        service.register_advisory_window(sample_advisory_window)

        result = await service.detect_conflicts(
            ConflictDetectionRequest(
                marquis_id="orias",
                judgment_topic="quantum computing security",
            )
        )

        conflict_id = result.conflicts[0].conflict_id
        conflict = await service.get_conflict(conflict_id)
        assert conflict is not None
        assert conflict.marquis_id == "orias"

    @pytest.mark.asyncio
    async def test_get_conflicts_by_marquis(
        self,
        service: AdvisoryConflictDetectionService,
        sample_advisory_window: AdvisoryWindow,
    ) -> None:
        """Test retrieving all conflicts for a Marquis."""
        service.register_advisory_window(sample_advisory_window)

        await service.detect_conflicts(
            ConflictDetectionRequest(
                marquis_id="orias",
                judgment_topic="quantum computing security",
            )
        )

        conflicts = await service.get_conflicts_by_marquis("orias")
        assert len(conflicts) == 1

    @pytest.mark.asyncio
    async def test_get_violations_by_marquis(
        self,
        service: AdvisoryConflictDetectionService,
        sample_advisory_window: AdvisoryWindow,
    ) -> None:
        """Test retrieving all violations for a Marquis."""
        service.register_advisory_window(sample_advisory_window)

        await service.check_participation(
            ParticipationCheckRequest(
                marquis_id="orias",
                judgment_topic="quantum computing security",
                action="test",
            )
        )

        violations = await service.get_violations_by_marquis("orias")
        assert len(violations) == 1


# =============================================================================
# CONFIGURATION TESTS
# =============================================================================


class TestConfiguration:
    """Tests for configuration handling."""

    def test_default_config_values(self) -> None:
        """Test default configuration values."""
        config = ConflictDetectionConfig()
        assert config.overlap_threshold == 0.6
        assert config.exclusion_automatic is True
        assert config.violation_severity == ViolationSeverity.MAJOR
        assert config.escalation_enabled is True

    @pytest.mark.asyncio
    async def test_escalation_disabled(
        self,
        mock_knight_witness: MagicMock,
    ) -> None:
        """Test escalation can be disabled."""
        config = ConflictDetectionConfig(escalation_enabled=False)
        service = AdvisoryConflictDetectionService(
            knight_witness=mock_knight_witness,
            config=config,
        )

        service.register_advisory_window(
            AdvisoryWindow.create(
                marquis_id="orias",
                advisory_id=uuid4(),
                topic="quantum computing",
                timestamp=datetime.now(timezone.utc),
            )
        )

        result = await service.form_unconflicted_panel(
            PanelFormationRequest(
                judgment_topic="quantum computing",
                available_princes=["orias"],  # Only conflicted Prince
            )
        )

        # Without escalation disabled, it returns success=True with empty panel
        # (escalation flag is False, but no error escalation happens)
        assert result.escalated is False
        assert len(result.excluded) == 1
        assert "orias" in result.excluded
