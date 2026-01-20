"""Unit tests for audit timeline domain models (Story 2B.6).

Tests TimelineEvent, WitnessChainVerification, and AuditTimeline
creation, validation, and serialization.
"""

from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest
from uuid6 import uuid7

from src.domain.models.audit_timeline import (
    AUDIT_TIMELINE_SCHEMA_VERSION,
    BLAKE3_HASH_SIZE,
    AuditTimeline,
    TerminationReason,
    TimelineEvent,
    WitnessChainVerification,
)


class TestTerminationReason:
    """Tests for TerminationReason enum."""

    def test_all_termination_reasons_exist(self) -> None:
        """Verify all expected termination reasons are defined."""
        assert TerminationReason.NORMAL == "NORMAL"
        assert TerminationReason.TIMEOUT == "TIMEOUT"
        assert TerminationReason.DEADLOCK == "DEADLOCK"
        assert TerminationReason.ABORT == "ABORT"

    def test_termination_reason_values(self) -> None:
        """Verify termination reason string values."""
        assert TerminationReason.NORMAL.value == "NORMAL"
        assert TerminationReason.TIMEOUT.value == "TIMEOUT"
        assert TerminationReason.DEADLOCK.value == "DEADLOCK"
        assert TerminationReason.ABORT.value == "ABORT"


class TestTimelineEvent:
    """Tests for TimelineEvent dataclass."""

    def test_create_timeline_event_minimal(self) -> None:
        """Test creating TimelineEvent with minimal fields."""
        event_id = uuid7()
        event_type = "deliberation.phase.witnessed"
        occurred_at = datetime.now(timezone.utc)

        event = TimelineEvent(
            event_id=event_id,
            event_type=event_type,
            occurred_at=occurred_at,
        )

        assert event.event_id == event_id
        assert event.event_type == event_type
        assert event.occurred_at == occurred_at
        assert event.payload == {}
        assert event.witness_hash is None

    def test_create_timeline_event_with_payload(self) -> None:
        """Test creating TimelineEvent with payload."""
        event = TimelineEvent(
            event_id=uuid7(),
            event_type="deliberation.complete",
            occurred_at=datetime.now(timezone.utc),
            payload={"outcome": "ACKNOWLEDGE", "votes": 3},
        )

        assert event.payload["outcome"] == "ACKNOWLEDGE"
        assert event.payload["votes"] == 3

    def test_create_timeline_event_with_witness_hash(self) -> None:
        """Test creating TimelineEvent with witness hash."""
        witness_hash = b"0" * 32  # 32 bytes

        event = TimelineEvent(
            event_id=uuid7(),
            event_type="deliberation.phase.witnessed",
            occurred_at=datetime.now(timezone.utc),
            witness_hash=witness_hash,
        )

        assert event.witness_hash == witness_hash
        assert event.has_witness is True
        assert event.witness_hash_hex == witness_hash.hex()

    def test_timeline_event_empty_event_type_raises(self) -> None:
        """Test that empty event_type raises ValueError."""
        with pytest.raises(ValueError, match="event_type cannot be empty"):
            TimelineEvent(
                event_id=uuid7(),
                event_type="",
                occurred_at=datetime.now(timezone.utc),
            )

    def test_timeline_event_invalid_witness_hash_size_raises(self) -> None:
        """Test that wrong witness_hash size raises ValueError."""
        with pytest.raises(ValueError, match=f"witness_hash must be {BLAKE3_HASH_SIZE} bytes"):
            TimelineEvent(
                event_id=uuid7(),
                event_type="test.event",
                occurred_at=datetime.now(timezone.utc),
                witness_hash=b"too_short",
            )

    def test_timeline_event_witness_hash_hex_none(self) -> None:
        """Test witness_hash_hex returns None when no hash."""
        event = TimelineEvent(
            event_id=uuid7(),
            event_type="test.event",
            occurred_at=datetime.now(timezone.utc),
        )

        assert event.witness_hash_hex is None
        assert event.has_witness is False

    def test_timeline_event_to_dict(self) -> None:
        """Test TimelineEvent serialization."""
        event_id = uuid7()
        occurred_at = datetime.now(timezone.utc)
        witness_hash = b"a" * 32

        event = TimelineEvent(
            event_id=event_id,
            event_type="deliberation.phase.witnessed",
            occurred_at=occurred_at,
            payload={"phase": "ASSESS"},
            witness_hash=witness_hash,
        )

        d = event.to_dict()

        assert d["event_id"] == str(event_id)
        assert d["event_type"] == "deliberation.phase.witnessed"
        assert d["occurred_at"] == occurred_at.isoformat()
        assert d["payload"] == {"phase": "ASSESS"}
        assert d["witness_hash"] == witness_hash.hex()
        assert d["schema_version"] == AUDIT_TIMELINE_SCHEMA_VERSION

    def test_timeline_event_from_dict(self) -> None:
        """Test TimelineEvent deserialization."""
        event_id = uuid7()
        occurred_at = datetime.now(timezone.utc)

        data = {
            "event_id": str(event_id),
            "event_type": "test.event",
            "occurred_at": occurred_at.isoformat(),
            "payload": {"key": "value"},
            "witness_hash": "aa" * 32,  # 64 hex chars
        }

        event = TimelineEvent.from_dict(data)

        assert event.event_id == event_id
        assert event.event_type == "test.event"
        assert event.payload == {"key": "value"}
        assert event.witness_hash == bytes.fromhex("aa" * 32)

    def test_timeline_event_from_dict_missing_event_id_raises(self) -> None:
        """Test from_dict raises on missing event_id."""
        with pytest.raises(ValueError, match="event_id is required"):
            TimelineEvent.from_dict({
                "event_type": "test.event",
                "occurred_at": datetime.now(timezone.utc).isoformat(),
            })

    def test_timeline_event_is_frozen(self) -> None:
        """Test TimelineEvent is immutable."""
        event = TimelineEvent(
            event_id=uuid7(),
            event_type="test.event",
            occurred_at=datetime.now(timezone.utc),
        )

        with pytest.raises(AttributeError):
            event.event_type = "modified"  # type: ignore


class TestWitnessChainVerification:
    """Tests for WitnessChainVerification dataclass."""

    def test_create_valid_verification(self) -> None:
        """Test creating valid WitnessChainVerification."""
        verification = WitnessChainVerification(
            is_valid=True,
            verified_events=4,
            total_events=4,
        )

        assert verification.is_valid is True
        assert verification.verified_events == 4
        assert verification.total_events == 4
        assert len(verification.broken_links) == 0
        assert len(verification.missing_transcripts) == 0
        assert len(verification.integrity_failures) == 0

    def test_create_invalid_verification_with_broken_links(self) -> None:
        """Test creating verification with broken links."""
        event_id_1 = uuid7()
        event_id_2 = uuid7()

        verification = WitnessChainVerification(
            is_valid=False,
            broken_links=((event_id_1, event_id_2),),
            verified_events=1,
            total_events=4,
        )

        assert verification.is_valid is False
        assert verification.has_broken_links is True
        assert len(verification.broken_links) == 1
        assert verification.broken_links[0] == (event_id_1, event_id_2)

    def test_create_verification_with_missing_transcripts(self) -> None:
        """Test creating verification with missing transcripts."""
        missing_hash = b"0" * 32

        verification = WitnessChainVerification(
            is_valid=False,
            missing_transcripts=(missing_hash,),
            verified_events=3,
            total_events=4,
        )

        assert verification.is_valid is False
        assert verification.has_missing_transcripts is True
        assert len(verification.missing_transcripts) == 1

    def test_create_verification_with_integrity_failures(self) -> None:
        """Test creating verification with integrity failures."""
        failed_hash = b"1" * 32

        verification = WitnessChainVerification(
            is_valid=False,
            integrity_failures=(failed_hash,),
            verified_events=3,
            total_events=4,
        )

        assert verification.is_valid is False
        assert verification.has_integrity_failures is True
        assert len(verification.integrity_failures) == 1

    def test_verification_coverage_full(self) -> None:
        """Test verification_coverage returns 1.0 for full coverage."""
        verification = WitnessChainVerification(
            is_valid=True,
            verified_events=4,
            total_events=4,
        )

        assert verification.verification_coverage == 1.0

    def test_verification_coverage_partial(self) -> None:
        """Test verification_coverage returns correct ratio."""
        verification = WitnessChainVerification(
            is_valid=False,
            verified_events=2,
            total_events=4,
        )

        assert verification.verification_coverage == 0.5

    def test_verification_coverage_zero_total(self) -> None:
        """Test verification_coverage returns 1.0 when total is 0."""
        verification = WitnessChainVerification(
            is_valid=True,
            verified_events=0,
            total_events=0,
        )

        assert verification.verification_coverage == 1.0

    def test_verification_verified_exceeds_total_raises(self) -> None:
        """Test that verified > total raises ValueError."""
        with pytest.raises(ValueError, match="cannot exceed total_events"):
            WitnessChainVerification(
                is_valid=True,
                verified_events=5,
                total_events=4,
            )

    def test_verification_negative_verified_raises(self) -> None:
        """Test that negative verified_events raises ValueError."""
        with pytest.raises(ValueError, match="verified_events must be >= 0"):
            WitnessChainVerification(
                is_valid=True,
                verified_events=-1,
                total_events=4,
            )

    def test_verification_invalid_missing_hash_size_raises(self) -> None:
        """Test that wrong hash size in missing_transcripts raises."""
        with pytest.raises(ValueError, match="missing_transcripts hashes must be"):
            WitnessChainVerification(
                is_valid=False,
                missing_transcripts=(b"short",),
                verified_events=0,
                total_events=4,
            )

    def test_verification_to_dict(self) -> None:
        """Test WitnessChainVerification serialization."""
        event_id_1 = uuid7()
        event_id_2 = uuid7()
        missing_hash = b"a" * 32

        verification = WitnessChainVerification(
            is_valid=False,
            broken_links=((event_id_1, event_id_2),),
            missing_transcripts=(missing_hash,),
            integrity_failures=(),
            verified_events=2,
            total_events=4,
        )

        d = verification.to_dict()

        assert d["is_valid"] is False
        assert len(d["broken_links"]) == 1
        assert d["broken_links"][0] == [str(event_id_1), str(event_id_2)]
        assert d["missing_transcripts"] == [missing_hash.hex()]
        assert d["integrity_failures"] == []
        assert d["verified_events"] == 2
        assert d["total_events"] == 4
        assert d["verification_coverage"] == 0.5
        assert d["schema_version"] == AUDIT_TIMELINE_SCHEMA_VERSION


class TestAuditTimeline:
    """Tests for AuditTimeline dataclass."""

    @pytest.fixture
    def archons(self) -> tuple[UUID, UUID, UUID]:
        """Create test archon UUIDs."""
        return (uuid7(), uuid7(), uuid7())

    @pytest.fixture
    def base_timeline_kwargs(self, archons: tuple[UUID, UUID, UUID]) -> dict:
        """Create base kwargs for AuditTimeline."""
        return {
            "session_id": uuid7(),
            "petition_id": uuid7(),
            "events": (),
            "assigned_archons": archons,
            "outcome": "ACKNOWLEDGE",
            "termination_reason": TerminationReason.NORMAL,
            "started_at": datetime.now(timezone.utc),
        }

    def test_create_minimal_audit_timeline(
        self, base_timeline_kwargs: dict
    ) -> None:
        """Test creating AuditTimeline with minimal fields."""
        timeline = AuditTimeline(**base_timeline_kwargs)

        assert timeline.session_id == base_timeline_kwargs["session_id"]
        assert timeline.petition_id == base_timeline_kwargs["petition_id"]
        assert timeline.events == ()
        assert timeline.outcome == "ACKNOWLEDGE"
        assert timeline.termination_reason == TerminationReason.NORMAL
        assert timeline.completed_at is None
        assert timeline.witness_chain_valid is False
        assert timeline.transcripts == {}
        assert timeline.dissent_record is None
        assert timeline.substitutions == ()

    def test_create_audit_timeline_with_events(
        self, base_timeline_kwargs: dict
    ) -> None:
        """Test creating AuditTimeline with events."""
        events = (
            TimelineEvent(
                event_id=uuid7(),
                event_type="deliberation.session.created",
                occurred_at=datetime.now(timezone.utc),
            ),
            TimelineEvent(
                event_id=uuid7(),
                event_type="deliberation.phase.witnessed",
                occurred_at=datetime.now(timezone.utc) + timedelta(seconds=10),
            ),
        )

        timeline = AuditTimeline(
            **{**base_timeline_kwargs, "events": events}
        )

        assert timeline.event_count == 2
        assert timeline.events[0].event_type == "deliberation.session.created"

    def test_create_audit_timeline_with_transcripts(
        self, base_timeline_kwargs: dict
    ) -> None:
        """Test creating AuditTimeline with transcripts."""
        transcripts = {
            "ASSESS": "Archon-1: ...\nArchon-2: ...",
            "POSITION": "Archon-1: I vote ACKNOWLEDGE...",
            "CROSS_EXAMINE": None,  # Missing transcript
            "VOTE": "Final votes recorded",
        }

        timeline = AuditTimeline(
            **{**base_timeline_kwargs, "transcripts": transcripts}
        )

        assert timeline.get_transcript("ASSESS") == "Archon-1: ...\nArchon-2: ..."
        assert timeline.get_transcript("CROSS_EXAMINE") is None
        assert timeline.get_transcript("NONEXISTENT") is None

    def test_create_audit_timeline_with_dissent(
        self, base_timeline_kwargs: dict
    ) -> None:
        """Test creating AuditTimeline with dissent record."""
        dissent_record = {
            "dissent_archon_id": str(uuid7()),
            "dissent_disposition": "REFER",
            "majority_disposition": "ACKNOWLEDGE",
            "rationale_hash": "a" * 64,
        }

        timeline = AuditTimeline(
            **{**base_timeline_kwargs, "dissent_record": dissent_record}
        )

        assert timeline.has_dissent is True
        assert timeline.dissent_record == dissent_record

    def test_create_audit_timeline_with_substitutions(
        self, base_timeline_kwargs: dict
    ) -> None:
        """Test creating AuditTimeline with substitution records."""
        substitutions = (
            {
                "failed_archon_id": str(uuid7()),
                "substitute_archon_id": str(uuid7()),
                "phase_at_failure": "CROSS_EXAMINE",
                "failure_reason": "RESPONSE_TIMEOUT",
            },
        )

        timeline = AuditTimeline(
            **{**base_timeline_kwargs, "substitutions": substitutions}
        )

        assert timeline.has_substitutions is True
        assert len(timeline.substitutions) == 1

    def test_audit_timeline_wrong_archon_count_raises(
        self, base_timeline_kwargs: dict
    ) -> None:
        """Test that wrong archon count raises ValueError."""
        with pytest.raises(ValueError, match="exactly 3 UUIDs"):
            AuditTimeline(
                **{**base_timeline_kwargs, "assigned_archons": (uuid7(), uuid7())}
            )

    def test_audit_timeline_duplicate_archons_raises(
        self, base_timeline_kwargs: dict
    ) -> None:
        """Test that duplicate archons raises ValueError."""
        archon = uuid7()
        with pytest.raises(ValueError, match="must be unique"):
            AuditTimeline(
                **{**base_timeline_kwargs, "assigned_archons": (archon, archon, uuid7())}
            )

    def test_audit_timeline_invalid_outcome_raises(
        self, base_timeline_kwargs: dict
    ) -> None:
        """Test that invalid outcome raises ValueError."""
        with pytest.raises(ValueError, match="outcome must be one of"):
            AuditTimeline(
                **{**base_timeline_kwargs, "outcome": "INVALID"}
            )

    def test_audit_timeline_duration_seconds(
        self, base_timeline_kwargs: dict
    ) -> None:
        """Test duration_seconds calculation."""
        started_at = datetime.now(timezone.utc)
        completed_at = started_at + timedelta(seconds=300)  # 5 minutes

        timeline = AuditTimeline(
            **{
                **base_timeline_kwargs,
                "started_at": started_at,
                "completed_at": completed_at,
            }
        )

        assert timeline.duration_seconds == 300.0

    def test_audit_timeline_duration_seconds_not_completed(
        self, base_timeline_kwargs: dict
    ) -> None:
        """Test duration_seconds returns None when not completed."""
        timeline = AuditTimeline(**base_timeline_kwargs)

        assert timeline.duration_seconds is None

    def test_audit_timeline_is_normal_completion(
        self, base_timeline_kwargs: dict
    ) -> None:
        """Test is_normal_completion for NORMAL termination."""
        timeline = AuditTimeline(**base_timeline_kwargs)

        assert timeline.is_normal_completion is True
        assert timeline.was_forced_escalation is False

    def test_audit_timeline_was_forced_escalation_timeout(
        self, base_timeline_kwargs: dict
    ) -> None:
        """Test was_forced_escalation for TIMEOUT termination."""
        timeline = AuditTimeline(
            **{
                **base_timeline_kwargs,
                "termination_reason": TerminationReason.TIMEOUT,
                "outcome": "ESCALATE",
            }
        )

        assert timeline.is_normal_completion is False
        assert timeline.was_forced_escalation is True

    def test_audit_timeline_was_forced_escalation_deadlock(
        self, base_timeline_kwargs: dict
    ) -> None:
        """Test was_forced_escalation for DEADLOCK termination."""
        timeline = AuditTimeline(
            **{
                **base_timeline_kwargs,
                "termination_reason": TerminationReason.DEADLOCK,
                "outcome": "ESCALATE",
            }
        )

        assert timeline.is_normal_completion is False
        assert timeline.was_forced_escalation is True

    def test_audit_timeline_was_forced_escalation_abort(
        self, base_timeline_kwargs: dict
    ) -> None:
        """Test was_forced_escalation for ABORT termination."""
        timeline = AuditTimeline(
            **{
                **base_timeline_kwargs,
                "termination_reason": TerminationReason.ABORT,
                "outcome": "ESCALATE",
            }
        )

        assert timeline.is_normal_completion is False
        assert timeline.was_forced_escalation is True

    def test_audit_timeline_get_events_by_type(
        self, base_timeline_kwargs: dict
    ) -> None:
        """Test filtering events by type."""
        events = (
            TimelineEvent(
                event_id=uuid7(),
                event_type="deliberation.phase.witnessed",
                occurred_at=datetime.now(timezone.utc),
            ),
            TimelineEvent(
                event_id=uuid7(),
                event_type="deliberation.phase.witnessed",
                occurred_at=datetime.now(timezone.utc) + timedelta(seconds=10),
            ),
            TimelineEvent(
                event_id=uuid7(),
                event_type="deliberation.complete",
                occurred_at=datetime.now(timezone.utc) + timedelta(seconds=20),
            ),
        )

        timeline = AuditTimeline(**{**base_timeline_kwargs, "events": events})

        phase_events = timeline.get_events_by_type("deliberation.phase.witnessed")
        assert len(phase_events) == 2

        complete_events = timeline.get_events_by_type("deliberation.complete")
        assert len(complete_events) == 1

        missing_events = timeline.get_events_by_type("nonexistent")
        assert len(missing_events) == 0

    def test_audit_timeline_to_dict(
        self, base_timeline_kwargs: dict
    ) -> None:
        """Test AuditTimeline serialization."""
        started_at = datetime.now(timezone.utc)
        completed_at = started_at + timedelta(seconds=300)

        timeline = AuditTimeline(
            **{
                **base_timeline_kwargs,
                "started_at": started_at,
                "completed_at": completed_at,
                "witness_chain_valid": True,
                "transcripts": {"ASSESS": "content"},
            }
        )

        d = timeline.to_dict()

        assert d["session_id"] == str(base_timeline_kwargs["session_id"])
        assert d["petition_id"] == str(base_timeline_kwargs["petition_id"])
        assert d["outcome"] == "ACKNOWLEDGE"
        assert d["termination_reason"] == "NORMAL"
        assert d["started_at"] == started_at.isoformat()
        assert d["completed_at"] == completed_at.isoformat()
        assert d["witness_chain_valid"] is True
        assert d["transcripts"] == {"ASSESS": "content"}
        assert d["event_count"] == 0
        assert d["duration_seconds"] == 300.0
        assert d["has_dissent"] is False
        assert d["has_substitutions"] is False
        assert d["was_forced_escalation"] is False
        assert d["schema_version"] == AUDIT_TIMELINE_SCHEMA_VERSION

    def test_audit_timeline_is_frozen(
        self, base_timeline_kwargs: dict
    ) -> None:
        """Test AuditTimeline is immutable."""
        timeline = AuditTimeline(**base_timeline_kwargs)

        with pytest.raises(AttributeError):
            timeline.outcome = "REFER"  # type: ignore


class TestValidOutcomes:
    """Test valid outcome values for AuditTimeline."""

    @pytest.fixture
    def base_kwargs(self) -> dict:
        """Create base kwargs for AuditTimeline."""
        return {
            "session_id": uuid7(),
            "petition_id": uuid7(),
            "events": (),
            "assigned_archons": (uuid7(), uuid7(), uuid7()),
            "termination_reason": TerminationReason.NORMAL,
            "started_at": datetime.now(timezone.utc),
        }

    def test_acknowledge_outcome_valid(self, base_kwargs: dict) -> None:
        """Test ACKNOWLEDGE is valid outcome."""
        timeline = AuditTimeline(**{**base_kwargs, "outcome": "ACKNOWLEDGE"})
        assert timeline.outcome == "ACKNOWLEDGE"

    def test_refer_outcome_valid(self, base_kwargs: dict) -> None:
        """Test REFER is valid outcome."""
        timeline = AuditTimeline(**{**base_kwargs, "outcome": "REFER"})
        assert timeline.outcome == "REFER"

    def test_escalate_outcome_valid(self, base_kwargs: dict) -> None:
        """Test ESCALATE is valid outcome."""
        timeline = AuditTimeline(**{**base_kwargs, "outcome": "ESCALATE"})
        assert timeline.outcome == "ESCALATE"
