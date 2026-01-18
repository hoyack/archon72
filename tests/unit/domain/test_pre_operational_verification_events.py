"""Unit tests for pre-operational verification events (Story 8.5, FR146, NFR35).

Tests for:
- VerificationBypassedPayload construction and signable_content
- PostHaltVerificationStartedPayload construction and signable_content
- VerificationCompletedPayload construction and signable_content
- Event type constants
"""

import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from src.domain.events.pre_operational_verification import (
    POST_HALT_VERIFICATION_STARTED_EVENT_TYPE,
    VERIFICATION_BYPASSED_EVENT_TYPE,
    VERIFICATION_FAILED_EVENT_TYPE,
    VERIFICATION_PASSED_EVENT_TYPE,
    VERIFICATION_SYSTEM_AGENT_ID,
    PostHaltVerificationStartedPayload,
    VerificationBypassedPayload,
    VerificationCompletedPayload,
)


class TestEventTypeConstants:
    """Tests for event type constants."""

    def test_verification_bypassed_event_type(self) -> None:
        """Should have correct bypass event type."""
        assert VERIFICATION_BYPASSED_EVENT_TYPE == "system.verification.bypassed"

    def test_post_halt_verification_started_event_type(self) -> None:
        """Should have correct post-halt started event type."""
        assert (
            POST_HALT_VERIFICATION_STARTED_EVENT_TYPE
            == "system.verification.post_halt_started"
        )

    def test_verification_passed_event_type(self) -> None:
        """Should have correct passed event type."""
        assert VERIFICATION_PASSED_EVENT_TYPE == "system.verification.passed"

    def test_verification_failed_event_type(self) -> None:
        """Should have correct failed event type."""
        assert VERIFICATION_FAILED_EVENT_TYPE == "system.verification.failed"

    def test_system_agent_id(self) -> None:
        """Should have correct system agent ID."""
        assert VERIFICATION_SYSTEM_AGENT_ID == "system.pre_operational_verification"


class TestVerificationBypassedPayload:
    """Tests for VerificationBypassedPayload."""

    def test_create_payload(self) -> None:
        """Should create a valid bypass payload."""
        bypass_id = uuid4()
        now = datetime.now(timezone.utc)

        payload = VerificationBypassedPayload(
            bypass_id=bypass_id,
            failed_checks=("hash_chain", "witness_pool"),
            bypass_reason="Continuous restart bypass",
            bypass_count=2,
            bypass_window_seconds=300,
            max_bypasses_allowed=3,
            bypassed_at=now,
        )

        assert payload.bypass_id == bypass_id
        assert payload.failed_checks == ("hash_chain", "witness_pool")
        assert payload.bypass_reason == "Continuous restart bypass"
        assert payload.bypass_count == 2
        assert payload.bypass_window_seconds == 300
        assert payload.max_bypasses_allowed == 3
        assert payload.bypassed_at == now

    def test_signable_content_deterministic(self) -> None:
        """Should produce deterministic signable content."""
        bypass_id = uuid4()
        now = datetime.now(timezone.utc)

        payload = VerificationBypassedPayload(
            bypass_id=bypass_id,
            failed_checks=("hash_chain", "witness_pool"),
            bypass_reason="Continuous restart bypass",
            bypass_count=2,
            bypass_window_seconds=300,
            max_bypasses_allowed=3,
            bypassed_at=now,
        )

        content1 = payload.signable_content()
        content2 = payload.signable_content()

        assert content1 == content2
        assert isinstance(content1, bytes)

    def test_signable_content_parseable_json(self) -> None:
        """Should produce valid JSON in signable content."""
        bypass_id = uuid4()
        now = datetime.now(timezone.utc)

        payload = VerificationBypassedPayload(
            bypass_id=bypass_id,
            failed_checks=("hash_chain",),
            bypass_reason="Test bypass",
            bypass_count=1,
            bypass_window_seconds=300,
            max_bypasses_allowed=3,
            bypassed_at=now,
        )

        content = payload.signable_content()
        parsed = json.loads(content.decode("utf-8"))

        assert parsed["bypass_id"] == str(bypass_id)
        assert parsed["failed_checks"] == ["hash_chain"]
        assert parsed["bypass_reason"] == "Test bypass"
        assert parsed["bypass_count"] == 1

    def test_to_dict(self) -> None:
        """Should convert to dict for event storage."""
        bypass_id = uuid4()
        now = datetime.now(timezone.utc)

        payload = VerificationBypassedPayload(
            bypass_id=bypass_id,
            failed_checks=("hash_chain", "keeper_keys"),
            bypass_reason="Test bypass",
            bypass_count=1,
            bypass_window_seconds=300,
            max_bypasses_allowed=3,
            bypassed_at=now,
        )

        d = payload.to_dict()

        assert d["bypass_id"] == str(bypass_id)
        assert d["failed_checks"] == ["hash_chain", "keeper_keys"]
        assert d["bypass_reason"] == "Test bypass"
        assert d["bypassed_at"] == now.isoformat()

    def test_payload_is_frozen(self) -> None:
        """Payload should be immutable."""
        payload = VerificationBypassedPayload(
            bypass_id=uuid4(),
            failed_checks=("hash_chain",),
            bypass_reason="Test",
            bypass_count=1,
            bypass_window_seconds=300,
            max_bypasses_allowed=3,
            bypassed_at=datetime.now(timezone.utc),
        )

        with pytest.raises(AttributeError):
            payload.bypass_count = 5  # type: ignore


class TestPostHaltVerificationStartedPayload:
    """Tests for PostHaltVerificationStartedPayload."""

    def test_create_payload(self) -> None:
        """Should create a valid post-halt started payload."""
        verification_id = uuid4()
        halt_cleared = datetime.now(timezone.utc) - timedelta(minutes=5)
        started = datetime.now(timezone.utc)

        payload = PostHaltVerificationStartedPayload(
            verification_id=verification_id,
            halt_reason="Fork detected",
            halt_cleared_at=halt_cleared,
            verification_started_at=started,
        )

        assert payload.verification_id == verification_id
        assert payload.halt_reason == "Fork detected"
        assert payload.halt_cleared_at == halt_cleared
        assert payload.verification_started_at == started

    def test_default_checks_to_run(self) -> None:
        """Should have default checks to run."""
        payload = PostHaltVerificationStartedPayload(
            verification_id=uuid4(),
            halt_reason="Test halt",
            halt_cleared_at=datetime.now(timezone.utc),
            verification_started_at=datetime.now(timezone.utc),
        )

        expected_checks = (
            "halt_state",
            "hash_chain",
            "checkpoint_anchors",
            "keeper_keys",
            "witness_pool",
            "replica_sync",
        )
        assert payload.checks_to_run == expected_checks

    def test_signable_content_deterministic(self) -> None:
        """Should produce deterministic signable content."""
        verification_id = uuid4()
        halt_cleared = datetime.now(timezone.utc)
        started = datetime.now(timezone.utc)

        payload = PostHaltVerificationStartedPayload(
            verification_id=verification_id,
            halt_reason="Fork detected",
            halt_cleared_at=halt_cleared,
            verification_started_at=started,
        )

        content1 = payload.signable_content()
        content2 = payload.signable_content()

        assert content1 == content2
        assert isinstance(content1, bytes)

    def test_signable_content_parseable_json(self) -> None:
        """Should produce valid JSON in signable content."""
        verification_id = uuid4()
        halt_cleared = datetime.now(timezone.utc)
        started = datetime.now(timezone.utc)

        payload = PostHaltVerificationStartedPayload(
            verification_id=verification_id,
            halt_reason="Fork detected",
            halt_cleared_at=halt_cleared,
            verification_started_at=started,
        )

        content = payload.signable_content()
        parsed = json.loads(content.decode("utf-8"))

        assert parsed["verification_id"] == str(verification_id)
        assert parsed["halt_reason"] == "Fork detected"
        assert "checks_to_run" in parsed

    def test_to_dict(self) -> None:
        """Should convert to dict for event storage."""
        verification_id = uuid4()
        halt_cleared = datetime.now(timezone.utc)
        started = datetime.now(timezone.utc)

        payload = PostHaltVerificationStartedPayload(
            verification_id=verification_id,
            halt_reason="Test halt",
            halt_cleared_at=halt_cleared,
            verification_started_at=started,
        )

        d = payload.to_dict()

        assert d["verification_id"] == str(verification_id)
        assert d["halt_reason"] == "Test halt"
        assert d["halt_cleared_at"] == halt_cleared.isoformat()
        assert d["verification_started_at"] == started.isoformat()

    def test_payload_is_frozen(self) -> None:
        """Payload should be immutable."""
        payload = PostHaltVerificationStartedPayload(
            verification_id=uuid4(),
            halt_reason="Test",
            halt_cleared_at=datetime.now(timezone.utc),
            verification_started_at=datetime.now(timezone.utc),
        )

        with pytest.raises(AttributeError):
            payload.halt_reason = "Modified"  # type: ignore


class TestVerificationCompletedPayload:
    """Tests for VerificationCompletedPayload."""

    def test_create_passed_payload(self) -> None:
        """Should create a valid passed payload."""
        verification_id = uuid4()
        completed = datetime.now(timezone.utc)

        payload = VerificationCompletedPayload(
            verification_id=verification_id,
            status="passed",
            check_count=6,
            failure_count=0,
            failed_check_names=(),
            duration_ms=150.5,
            is_post_halt=False,
            completed_at=completed,
        )

        assert payload.verification_id == verification_id
        assert payload.status == "passed"
        assert payload.check_count == 6
        assert payload.failure_count == 0
        assert payload.failed_check_names == ()
        assert payload.duration_ms == 150.5
        assert payload.is_post_halt is False

    def test_create_failed_payload(self) -> None:
        """Should create a valid failed payload."""
        verification_id = uuid4()
        completed = datetime.now(timezone.utc)

        payload = VerificationCompletedPayload(
            verification_id=verification_id,
            status="failed",
            check_count=6,
            failure_count=2,
            failed_check_names=("hash_chain", "witness_pool"),
            duration_ms=200.0,
            is_post_halt=True,
            completed_at=completed,
        )

        assert payload.status == "failed"
        assert payload.failure_count == 2
        assert payload.failed_check_names == ("hash_chain", "witness_pool")
        assert payload.is_post_halt is True

    def test_signable_content_deterministic(self) -> None:
        """Should produce deterministic signable content."""
        verification_id = uuid4()
        completed = datetime.now(timezone.utc)

        payload = VerificationCompletedPayload(
            verification_id=verification_id,
            status="passed",
            check_count=6,
            failure_count=0,
            failed_check_names=(),
            duration_ms=150.5,
            is_post_halt=False,
            completed_at=completed,
        )

        content1 = payload.signable_content()
        content2 = payload.signable_content()

        assert content1 == content2

    def test_to_dict(self) -> None:
        """Should convert to dict for event storage."""
        verification_id = uuid4()
        completed = datetime.now(timezone.utc)

        payload = VerificationCompletedPayload(
            verification_id=verification_id,
            status="bypassed",
            check_count=6,
            failure_count=1,
            failed_check_names=("keeper_keys",),
            duration_ms=100.0,
            is_post_halt=False,
            completed_at=completed,
        )

        d = payload.to_dict()

        assert d["verification_id"] == str(verification_id)
        assert d["status"] == "bypassed"
        assert d["check_count"] == 6
        assert d["failure_count"] == 1
        assert d["failed_check_names"] == ["keeper_keys"]
        assert d["completed_at"] == completed.isoformat()

    def test_payload_is_frozen(self) -> None:
        """Payload should be immutable."""
        payload = VerificationCompletedPayload(
            verification_id=uuid4(),
            status="passed",
            check_count=6,
            failure_count=0,
            failed_check_names=(),
            duration_ms=100.0,
            is_post_halt=False,
            completed_at=datetime.now(timezone.utc),
        )

        with pytest.raises(AttributeError):
            payload.status = "failed"  # type: ignore
