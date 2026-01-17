"""Unit tests for verification result domain models.

Story: consent-gov-9.3: Independent Verification

Tests:
- VerificationStatus enum
- IssueType enum
- DetectedIssue model
- VerificationResult model
- VerificationFailedError
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.domain.governance.audit.verification_result import (
    VerificationStatus,
    IssueType,
    DetectedIssue,
    VerificationResult,
    VerificationFailedError,
)


class TestVerificationStatus:
    """Tests for VerificationStatus enum."""

    def test_valid_status(self) -> None:
        """VerificationStatus has VALID state."""
        status = VerificationStatus.VALID
        assert status.value == "valid"

    def test_invalid_status(self) -> None:
        """VerificationStatus has INVALID state."""
        status = VerificationStatus.INVALID
        assert status.value == "invalid"

    def test_partial_status(self) -> None:
        """VerificationStatus has PARTIAL state."""
        status = VerificationStatus.PARTIAL
        assert status.value == "partial"

    def test_all_statuses_defined(self) -> None:
        """All expected statuses are defined."""
        assert hasattr(VerificationStatus, "VALID")
        assert hasattr(VerificationStatus, "INVALID")
        assert hasattr(VerificationStatus, "PARTIAL")


class TestIssueType:
    """Tests for IssueType enum."""

    def test_hash_mismatch_type(self) -> None:
        """IssueType has HASH_MISMATCH."""
        issue = IssueType.HASH_MISMATCH
        assert issue.value == "hash_mismatch"

    def test_sequence_gap_type(self) -> None:
        """IssueType has SEQUENCE_GAP."""
        issue = IssueType.SEQUENCE_GAP
        assert issue.value == "sequence_gap"

    def test_broken_link_type(self) -> None:
        """IssueType has BROKEN_LINK."""
        issue = IssueType.BROKEN_LINK
        assert issue.value == "broken_link"

    def test_merkle_mismatch_type(self) -> None:
        """IssueType has MERKLE_MISMATCH."""
        issue = IssueType.MERKLE_MISMATCH
        assert issue.value == "merkle_mismatch"

    def test_state_mismatch_type(self) -> None:
        """IssueType has STATE_MISMATCH."""
        issue = IssueType.STATE_MISMATCH
        assert issue.value == "state_mismatch"

    def test_all_issue_types_defined(self) -> None:
        """All expected issue types are defined."""
        assert hasattr(IssueType, "HASH_MISMATCH")
        assert hasattr(IssueType, "SEQUENCE_GAP")
        assert hasattr(IssueType, "BROKEN_LINK")
        assert hasattr(IssueType, "MERKLE_MISMATCH")
        assert hasattr(IssueType, "STATE_MISMATCH")


class TestDetectedIssue:
    """Tests for DetectedIssue domain model."""

    def test_create_detected_issue_with_all_fields(self) -> None:
        """DetectedIssue can be created with all fields."""
        event_id = uuid4()
        issue = DetectedIssue(
            issue_type=IssueType.HASH_MISMATCH,
            event_id=event_id,
            sequence_number=42,
            description="Hash mismatch at event 42",
            expected="abc123",
            actual="xyz789",
        )

        assert issue.issue_type == IssueType.HASH_MISMATCH
        assert issue.event_id == event_id
        assert issue.sequence_number == 42
        assert issue.description == "Hash mismatch at event 42"
        assert issue.expected == "abc123"
        assert issue.actual == "xyz789"

    def test_create_detected_issue_with_optional_fields_none(self) -> None:
        """DetectedIssue accepts None for optional fields."""
        issue = DetectedIssue(
            issue_type=IssueType.MERKLE_MISMATCH,
            event_id=None,
            sequence_number=None,
            description="Merkle root mismatch",
            expected="expected_root",
            actual="actual_root",
        )

        assert issue.event_id is None
        assert issue.sequence_number is None

    def test_detected_issue_is_frozen(self) -> None:
        """DetectedIssue is immutable."""
        issue = DetectedIssue(
            issue_type=IssueType.SEQUENCE_GAP,
            event_id=None,
            sequence_number=5,
            description="Gap at sequence 5",
            expected="5",
            actual="6",
        )

        with pytest.raises(AttributeError):
            issue.description = "Modified"  # type: ignore

    def test_detected_issue_to_dict(self) -> None:
        """DetectedIssue can be converted to dictionary."""
        event_id = uuid4()
        issue = DetectedIssue(
            issue_type=IssueType.BROKEN_LINK,
            event_id=event_id,
            sequence_number=10,
            description="Broken link at event 10",
            expected="prev_hash_123",
            actual="wrong_hash_456",
        )

        result = issue.to_dict()

        assert result["issue_type"] == "broken_link"
        assert result["event_id"] == str(event_id)
        assert result["sequence_number"] == 10
        assert result["description"] == "Broken link at event 10"
        assert result["expected"] == "prev_hash_123"
        assert result["actual"] == "wrong_hash_456"

    def test_detected_issue_to_dict_with_none_values(self) -> None:
        """DetectedIssue.to_dict handles None values."""
        issue = DetectedIssue(
            issue_type=IssueType.STATE_MISMATCH,
            event_id=None,
            sequence_number=None,
            description="State could not be derived",
            expected="Valid state",
            actual="None",
        )

        result = issue.to_dict()

        assert result["event_id"] is None
        assert result["sequence_number"] is None


class TestVerificationResult:
    """Tests for VerificationResult domain model."""

    def test_create_valid_verification_result(self) -> None:
        """VerificationResult can be created with valid ledger results."""
        verification_id = uuid4()
        verified_at = datetime.now(timezone.utc)

        result = VerificationResult(
            verification_id=verification_id,
            verified_at=verified_at,
            status=VerificationStatus.VALID,
            hash_chain_valid=True,
            merkle_valid=True,
            sequence_complete=True,
            state_replay_valid=True,
            issues=[],
            total_events_verified=100,
        )

        assert result.verification_id == verification_id
        assert result.verified_at == verified_at
        assert result.status == VerificationStatus.VALID
        assert result.hash_chain_valid is True
        assert result.merkle_valid is True
        assert result.sequence_complete is True
        assert result.state_replay_valid is True
        assert result.issues == []
        assert result.total_events_verified == 100

    def test_create_invalid_verification_result(self) -> None:
        """VerificationResult can represent invalid ledger."""
        issue = DetectedIssue(
            issue_type=IssueType.HASH_MISMATCH,
            event_id=uuid4(),
            sequence_number=5,
            description="Tampered event",
            expected="abc",
            actual="xyz",
        )

        result = VerificationResult(
            verification_id=uuid4(),
            verified_at=datetime.now(timezone.utc),
            status=VerificationStatus.INVALID,
            hash_chain_valid=False,
            merkle_valid=True,
            sequence_complete=True,
            state_replay_valid=True,
            issues=[issue],
            total_events_verified=100,
        )

        assert result.status == VerificationStatus.INVALID
        assert result.hash_chain_valid is False
        assert len(result.issues) == 1

    def test_create_partial_verification_result(self) -> None:
        """VerificationResult can represent partial verification."""
        result = VerificationResult(
            verification_id=uuid4(),
            verified_at=datetime.now(timezone.utc),
            status=VerificationStatus.PARTIAL,
            hash_chain_valid=True,
            merkle_valid=False,
            sequence_complete=True,
            state_replay_valid=True,
            issues=[
                DetectedIssue(
                    issue_type=IssueType.MERKLE_MISMATCH,
                    event_id=None,
                    sequence_number=None,
                    description="Merkle root mismatch",
                    expected="root_a",
                    actual="root_b",
                )
            ],
            total_events_verified=50,
        )

        assert result.status == VerificationStatus.PARTIAL
        assert result.merkle_valid is False

    def test_verification_result_is_frozen(self) -> None:
        """VerificationResult is immutable."""
        result = VerificationResult(
            verification_id=uuid4(),
            verified_at=datetime.now(timezone.utc),
            status=VerificationStatus.VALID,
            hash_chain_valid=True,
            merkle_valid=True,
            sequence_complete=True,
            state_replay_valid=True,
            issues=[],
            total_events_verified=10,
        )

        with pytest.raises(AttributeError):
            result.status = VerificationStatus.INVALID  # type: ignore

    def test_verification_result_negative_events_rejected(self) -> None:
        """VerificationResult rejects negative total_events_verified."""
        with pytest.raises(ValueError, match="non-negative"):
            VerificationResult(
                verification_id=uuid4(),
                verified_at=datetime.now(timezone.utc),
                status=VerificationStatus.VALID,
                hash_chain_valid=True,
                merkle_valid=True,
                sequence_complete=True,
                state_replay_valid=True,
                issues=[],
                total_events_verified=-1,
            )

    def test_verification_result_to_dict(self) -> None:
        """VerificationResult can be converted to dictionary."""
        verification_id = uuid4()
        verified_at = datetime.now(timezone.utc)
        event_id = uuid4()

        issue = DetectedIssue(
            issue_type=IssueType.SEQUENCE_GAP,
            event_id=event_id,
            sequence_number=5,
            description="Gap detected",
            expected="5",
            actual="6",
        )

        result = VerificationResult(
            verification_id=verification_id,
            verified_at=verified_at,
            status=VerificationStatus.INVALID,
            hash_chain_valid=True,
            merkle_valid=True,
            sequence_complete=False,
            state_replay_valid=True,
            issues=[issue],
            total_events_verified=100,
        )

        dict_result = result.to_dict()

        assert dict_result["verification_id"] == str(verification_id)
        assert dict_result["verified_at"] == verified_at.isoformat()
        assert dict_result["status"] == "invalid"
        assert dict_result["hash_chain_valid"] is True
        assert dict_result["merkle_valid"] is True
        assert dict_result["sequence_complete"] is False
        assert dict_result["state_replay_valid"] is True
        assert dict_result["total_events_verified"] == 100
        assert len(dict_result["issues"]) == 1
        assert dict_result["issues"][0]["issue_type"] == "sequence_gap"

    def test_verification_result_is_valid_property(self) -> None:
        """VerificationResult.is_valid property works correctly."""
        valid_result = VerificationResult(
            verification_id=uuid4(),
            verified_at=datetime.now(timezone.utc),
            status=VerificationStatus.VALID,
            hash_chain_valid=True,
            merkle_valid=True,
            sequence_complete=True,
            state_replay_valid=True,
            issues=[],
            total_events_verified=10,
        )

        invalid_result = VerificationResult(
            verification_id=uuid4(),
            verified_at=datetime.now(timezone.utc),
            status=VerificationStatus.INVALID,
            hash_chain_valid=False,
            merkle_valid=True,
            sequence_complete=True,
            state_replay_valid=True,
            issues=[],
            total_events_verified=10,
        )

        assert valid_result.is_valid is True
        assert invalid_result.is_valid is False

    def test_verification_result_has_issues_property(self) -> None:
        """VerificationResult.has_issues property works correctly."""
        no_issues = VerificationResult(
            verification_id=uuid4(),
            verified_at=datetime.now(timezone.utc),
            status=VerificationStatus.VALID,
            hash_chain_valid=True,
            merkle_valid=True,
            sequence_complete=True,
            state_replay_valid=True,
            issues=[],
            total_events_verified=10,
        )

        with_issues = VerificationResult(
            verification_id=uuid4(),
            verified_at=datetime.now(timezone.utc),
            status=VerificationStatus.INVALID,
            hash_chain_valid=False,
            merkle_valid=True,
            sequence_complete=True,
            state_replay_valid=True,
            issues=[
                DetectedIssue(
                    issue_type=IssueType.HASH_MISMATCH,
                    event_id=None,
                    sequence_number=None,
                    description="Test",
                    expected="a",
                    actual="b",
                )
            ],
            total_events_verified=10,
        )

        assert no_issues.has_issues is False
        assert with_issues.has_issues is True

    def test_verification_result_issues_by_type(self) -> None:
        """VerificationResult.issues_by_type returns filtered issues."""
        issues = [
            DetectedIssue(
                issue_type=IssueType.HASH_MISMATCH,
                event_id=uuid4(),
                sequence_number=1,
                description="Hash 1",
                expected="a",
                actual="b",
            ),
            DetectedIssue(
                issue_type=IssueType.SEQUENCE_GAP,
                event_id=uuid4(),
                sequence_number=5,
                description="Gap",
                expected="5",
                actual="6",
            ),
            DetectedIssue(
                issue_type=IssueType.HASH_MISMATCH,
                event_id=uuid4(),
                sequence_number=10,
                description="Hash 2",
                expected="c",
                actual="d",
            ),
        ]

        result = VerificationResult(
            verification_id=uuid4(),
            verified_at=datetime.now(timezone.utc),
            status=VerificationStatus.INVALID,
            hash_chain_valid=False,
            merkle_valid=True,
            sequence_complete=False,
            state_replay_valid=True,
            issues=issues,
            total_events_verified=100,
        )

        hash_issues = result.issues_by_type(IssueType.HASH_MISMATCH)
        gap_issues = result.issues_by_type(IssueType.SEQUENCE_GAP)
        merkle_issues = result.issues_by_type(IssueType.MERKLE_MISMATCH)

        assert len(hash_issues) == 2
        assert len(gap_issues) == 1
        assert len(merkle_issues) == 0


class TestVerificationFailedError:
    """Tests for VerificationFailedError."""

    def test_error_can_be_raised(self) -> None:
        """VerificationFailedError can be raised."""
        with pytest.raises(VerificationFailedError, match="tampering detected"):
            raise VerificationFailedError("tampering detected")

    def test_error_is_value_error(self) -> None:
        """VerificationFailedError is a ValueError."""
        error = VerificationFailedError("test")
        assert isinstance(error, ValueError)

    def test_error_with_result(self) -> None:
        """VerificationFailedError can include result reference."""
        result = VerificationResult(
            verification_id=uuid4(),
            verified_at=datetime.now(timezone.utc),
            status=VerificationStatus.INVALID,
            hash_chain_valid=False,
            merkle_valid=True,
            sequence_complete=True,
            state_replay_valid=True,
            issues=[],
            total_events_verified=10,
        )

        error = VerificationFailedError("Verification failed", result=result)

        assert error.result is result
        assert error.result.status == VerificationStatus.INVALID
