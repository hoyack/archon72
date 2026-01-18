"""Unit tests for contribution preservation domain models.

Story: consent-gov-7.3: Contribution Preservation

Tests for:
- ContributionType enum
- ContributionRecord frozen dataclass
- PreservationResult frozen dataclass
- PII-free attribution enforcement

Constitutional Truths Tested:
- FR45: Contribution history preserved on exit
- NFR-INT-02: Public data only, no PII
- Ledger immutability: No deletion or modification
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from src.domain.governance.exit.contribution_record import ContributionRecord
from src.domain.governance.exit.contribution_type import ContributionType
from src.domain.governance.exit.preservation_result import PreservationResult

# =============================================================================
# ContributionType Tests
# =============================================================================


class TestContributionType:
    """Tests for ContributionType enum."""

    def test_task_completed_value(self) -> None:
        """TASK_COMPLETED has expected value."""
        assert ContributionType.TASK_COMPLETED.value == "task_completed"

    def test_task_reported_value(self) -> None:
        """TASK_REPORTED has expected value."""
        assert ContributionType.TASK_REPORTED.value == "task_reported"

    def test_deliberation_participated_value(self) -> None:
        """DELIBERATION_PARTICIPATED has expected value."""
        assert (
            ContributionType.DELIBERATION_PARTICIPATED.value
            == "deliberation_participated"
        )

    def test_str_representation(self) -> None:
        """String representation returns enum value."""
        assert str(ContributionType.TASK_COMPLETED) == "task_completed"
        assert str(ContributionType.TASK_REPORTED) == "task_reported"
        assert (
            str(ContributionType.DELIBERATION_PARTICIPATED)
            == "deliberation_participated"
        )

    def test_all_contribution_types(self) -> None:
        """All expected contribution types exist."""
        expected = {"TASK_COMPLETED", "TASK_REPORTED", "DELIBERATION_PARTICIPATED"}
        actual = {ct.name for ct in ContributionType}
        assert actual == expected


# =============================================================================
# ContributionRecord Tests
# =============================================================================


class TestContributionRecord:
    """Tests for ContributionRecord frozen dataclass."""

    @pytest.fixture
    def valid_record(self) -> ContributionRecord:
        """Create a valid contribution record."""
        return ContributionRecord(
            record_id=uuid4(),
            cluster_id=uuid4(),
            task_id=uuid4(),
            contribution_type=ContributionType.TASK_COMPLETED,
            contributed_at=datetime.now(timezone.utc),
            preserved_at=None,
            result_hash="abc123def456",
        )

    def test_valid_record_creation(self, valid_record: ContributionRecord) -> None:
        """Valid contribution record can be created."""
        assert valid_record.record_id is not None
        assert valid_record.cluster_id is not None
        assert valid_record.task_id is not None
        assert valid_record.contribution_type == ContributionType.TASK_COMPLETED
        assert valid_record.contributed_at is not None
        assert valid_record.preserved_at is None
        assert valid_record.result_hash == "abc123def456"

    def test_preserved_record(self) -> None:
        """Record with preserved_at set."""
        now = datetime.now(timezone.utc)
        record = ContributionRecord(
            record_id=uuid4(),
            cluster_id=uuid4(),
            task_id=uuid4(),
            contribution_type=ContributionType.TASK_REPORTED,
            contributed_at=now,
            preserved_at=now,
            result_hash="hash123",
        )
        assert record.preserved_at == now
        assert record.is_preserved is True

    def test_not_preserved_record(self, valid_record: ContributionRecord) -> None:
        """Record without preserved_at is not preserved."""
        assert valid_record.preserved_at is None
        assert valid_record.is_preserved is False

    def test_frozen_immutability(self, valid_record: ContributionRecord) -> None:
        """ContributionRecord is immutable (frozen)."""
        with pytest.raises(FrozenInstanceError):
            valid_record.cluster_id = uuid4()  # type: ignore

    def test_invalid_record_id_type(self) -> None:
        """Invalid record_id type raises ValueError."""
        with pytest.raises(ValueError, match="record_id must be UUID"):
            ContributionRecord(
                record_id="not-a-uuid",  # type: ignore
                cluster_id=uuid4(),
                task_id=uuid4(),
                contribution_type=ContributionType.TASK_COMPLETED,
                contributed_at=datetime.now(timezone.utc),
                preserved_at=None,
                result_hash="hash123",
            )

    def test_invalid_cluster_id_type(self) -> None:
        """Invalid cluster_id type raises ValueError."""
        with pytest.raises(ValueError, match="cluster_id must be UUID"):
            ContributionRecord(
                record_id=uuid4(),
                cluster_id="not-a-uuid",  # type: ignore
                task_id=uuid4(),
                contribution_type=ContributionType.TASK_COMPLETED,
                contributed_at=datetime.now(timezone.utc),
                preserved_at=None,
                result_hash="hash123",
            )

    def test_invalid_task_id_type(self) -> None:
        """Invalid task_id type raises ValueError."""
        with pytest.raises(ValueError, match="task_id must be UUID"):
            ContributionRecord(
                record_id=uuid4(),
                cluster_id=uuid4(),
                task_id="not-a-uuid",  # type: ignore
                contribution_type=ContributionType.TASK_COMPLETED,
                contributed_at=datetime.now(timezone.utc),
                preserved_at=None,
                result_hash="hash123",
            )

    def test_invalid_contribution_type(self) -> None:
        """Invalid contribution_type raises ValueError."""
        with pytest.raises(
            ValueError, match="contribution_type must be ContributionType"
        ):
            ContributionRecord(
                record_id=uuid4(),
                cluster_id=uuid4(),
                task_id=uuid4(),
                contribution_type="invalid",  # type: ignore
                contributed_at=datetime.now(timezone.utc),
                preserved_at=None,
                result_hash="hash123",
            )

    def test_invalid_contributed_at_type(self) -> None:
        """Invalid contributed_at type raises ValueError."""
        with pytest.raises(ValueError, match="contributed_at must be datetime"):
            ContributionRecord(
                record_id=uuid4(),
                cluster_id=uuid4(),
                task_id=uuid4(),
                contribution_type=ContributionType.TASK_COMPLETED,
                contributed_at="not-a-datetime",  # type: ignore
                preserved_at=None,
                result_hash="hash123",
            )

    def test_invalid_preserved_at_type(self) -> None:
        """Invalid preserved_at type raises ValueError."""
        with pytest.raises(ValueError, match="preserved_at must be datetime or None"):
            ContributionRecord(
                record_id=uuid4(),
                cluster_id=uuid4(),
                task_id=uuid4(),
                contribution_type=ContributionType.TASK_COMPLETED,
                contributed_at=datetime.now(timezone.utc),
                preserved_at="not-a-datetime",  # type: ignore
                result_hash="hash123",
            )

    def test_invalid_result_hash_type(self) -> None:
        """Invalid result_hash type raises ValueError."""
        with pytest.raises(ValueError, match="result_hash must be str"):
            ContributionRecord(
                record_id=uuid4(),
                cluster_id=uuid4(),
                task_id=uuid4(),
                contribution_type=ContributionType.TASK_COMPLETED,
                contributed_at=datetime.now(timezone.utc),
                preserved_at=None,
                result_hash=12345,  # type: ignore
            )

    def test_empty_result_hash(self) -> None:
        """Empty result_hash raises ValueError."""
        with pytest.raises(ValueError, match="result_hash must not be empty"):
            ContributionRecord(
                record_id=uuid4(),
                cluster_id=uuid4(),
                task_id=uuid4(),
                contribution_type=ContributionType.TASK_COMPLETED,
                contributed_at=datetime.now(timezone.utc),
                preserved_at=None,
                result_hash="",
            )

    def test_whitespace_result_hash(self) -> None:
        """Whitespace-only result_hash raises ValueError."""
        with pytest.raises(ValueError, match="result_hash must not be empty"):
            ContributionRecord(
                record_id=uuid4(),
                cluster_id=uuid4(),
                task_id=uuid4(),
                contribution_type=ContributionType.TASK_COMPLETED,
                contributed_at=datetime.now(timezone.utc),
                preserved_at=None,
                result_hash="   ",
            )


class TestContributionRecordPIIFree:
    """Tests ensuring ContributionRecord has no PII fields (NFR-INT-02)."""

    @pytest.fixture
    def contribution(self) -> ContributionRecord:
        """Create a contribution record."""
        return ContributionRecord(
            record_id=uuid4(),
            cluster_id=uuid4(),
            task_id=uuid4(),
            contribution_type=ContributionType.TASK_COMPLETED,
            contributed_at=datetime.now(timezone.utc),
            preserved_at=None,
            result_hash="hash123",
        )

    def test_no_cluster_name_field(self, contribution: ContributionRecord) -> None:
        """ContributionRecord has no cluster_name field (no PII)."""
        assert not hasattr(contribution, "cluster_name")

    def test_no_cluster_email_field(self, contribution: ContributionRecord) -> None:
        """ContributionRecord has no cluster_email field (no PII)."""
        assert not hasattr(contribution, "cluster_email")

    def test_no_cluster_phone_field(self, contribution: ContributionRecord) -> None:
        """ContributionRecord has no cluster_phone field (no PII)."""
        assert not hasattr(contribution, "cluster_phone")

    def test_no_cluster_contact_field(self, contribution: ContributionRecord) -> None:
        """ContributionRecord has no cluster_contact field (no PII)."""
        assert not hasattr(contribution, "cluster_contact")

    def test_cluster_id_is_uuid(self, contribution: ContributionRecord) -> None:
        """Attribution uses UUID only (pseudonymous)."""
        assert isinstance(contribution.cluster_id, UUID)

    def test_task_id_is_uuid(self, contribution: ContributionRecord) -> None:
        """Task reference uses UUID only."""
        assert isinstance(contribution.task_id, UUID)


# =============================================================================
# PreservationResult Tests
# =============================================================================


class TestPreservationResult:
    """Tests for PreservationResult frozen dataclass."""

    @pytest.fixture
    def valid_result(self) -> PreservationResult:
        """Create a valid preservation result."""
        return PreservationResult(
            cluster_id=uuid4(),
            contributions_preserved=5,
            task_ids=tuple(uuid4() for _ in range(5)),
            preserved_at=datetime.now(timezone.utc),
        )

    def test_valid_result_creation(self, valid_result: PreservationResult) -> None:
        """Valid preservation result can be created."""
        assert valid_result.cluster_id is not None
        assert valid_result.contributions_preserved == 5
        assert len(valid_result.task_ids) == 5
        assert valid_result.preserved_at is not None

    def test_has_contributions_true(self, valid_result: PreservationResult) -> None:
        """has_contributions returns True when contributions exist."""
        assert valid_result.has_contributions is True

    def test_has_contributions_false(self) -> None:
        """has_contributions returns False when no contributions."""
        result = PreservationResult(
            cluster_id=uuid4(),
            contributions_preserved=0,
            task_ids=(),
            preserved_at=datetime.now(timezone.utc),
        )
        assert result.has_contributions is False

    def test_unique_tasks(self) -> None:
        """unique_tasks counts distinct task IDs."""
        task_id_1 = uuid4()
        task_id_2 = uuid4()
        # Same task appears twice
        result = PreservationResult(
            cluster_id=uuid4(),
            contributions_preserved=3,
            task_ids=(task_id_1, task_id_2, task_id_1),
            preserved_at=datetime.now(timezone.utc),
        )
        assert result.unique_tasks == 2

    def test_frozen_immutability(self, valid_result: PreservationResult) -> None:
        """PreservationResult is immutable (frozen)."""
        with pytest.raises(FrozenInstanceError):
            valid_result.contributions_preserved = 10  # type: ignore

    def test_invalid_cluster_id_type(self) -> None:
        """Invalid cluster_id type raises ValueError."""
        with pytest.raises(ValueError, match="cluster_id must be UUID"):
            PreservationResult(
                cluster_id="not-a-uuid",  # type: ignore
                contributions_preserved=0,
                task_ids=(),
                preserved_at=datetime.now(timezone.utc),
            )

    def test_invalid_contributions_preserved_type(self) -> None:
        """Invalid contributions_preserved type raises ValueError."""
        with pytest.raises(ValueError, match="contributions_preserved must be int"):
            PreservationResult(
                cluster_id=uuid4(),
                contributions_preserved="five",  # type: ignore
                task_ids=(),
                preserved_at=datetime.now(timezone.utc),
            )

    def test_negative_contributions_preserved(self) -> None:
        """Negative contributions_preserved raises ValueError."""
        with pytest.raises(
            ValueError, match="contributions_preserved must be non-negative"
        ):
            PreservationResult(
                cluster_id=uuid4(),
                contributions_preserved=-1,
                task_ids=(),
                preserved_at=datetime.now(timezone.utc),
            )

    def test_invalid_task_ids_type(self) -> None:
        """Invalid task_ids type raises ValueError."""
        with pytest.raises(ValueError, match="task_ids must be tuple"):
            PreservationResult(
                cluster_id=uuid4(),
                contributions_preserved=0,
                task_ids=[uuid4()],  # type: ignore
                preserved_at=datetime.now(timezone.utc),
            )

    def test_invalid_task_id_in_tuple(self) -> None:
        """Invalid task_id in tuple raises ValueError."""
        with pytest.raises(ValueError, match=r"task_ids\[0\] must be UUID"):
            PreservationResult(
                cluster_id=uuid4(),
                contributions_preserved=1,
                task_ids=("not-a-uuid",),  # type: ignore
                preserved_at=datetime.now(timezone.utc),
            )

    def test_invalid_preserved_at_type(self) -> None:
        """Invalid preserved_at type raises ValueError."""
        with pytest.raises(ValueError, match="preserved_at must be datetime"):
            PreservationResult(
                cluster_id=uuid4(),
                contributions_preserved=0,
                task_ids=(),
                preserved_at="not-a-datetime",  # type: ignore
            )


class TestPreservationResultNoScrubbing:
    """Tests ensuring PreservationResult has no scrubbing fields (AC7)."""

    @pytest.fixture
    def result(self) -> PreservationResult:
        """Create a preservation result."""
        return PreservationResult(
            cluster_id=uuid4(),
            contributions_preserved=5,
            task_ids=tuple(uuid4() for _ in range(5)),
            preserved_at=datetime.now(timezone.utc),
        )

    def test_no_contributions_deleted_field(self, result: PreservationResult) -> None:
        """PreservationResult has no contributions_deleted field."""
        assert not hasattr(result, "contributions_deleted")

    def test_no_contributions_scrubbed_field(self, result: PreservationResult) -> None:
        """PreservationResult has no contributions_scrubbed field."""
        assert not hasattr(result, "contributions_scrubbed")

    def test_no_contributions_modified_field(self, result: PreservationResult) -> None:
        """PreservationResult has no contributions_modified field."""
        assert not hasattr(result, "contributions_modified")
